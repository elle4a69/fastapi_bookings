"""Synthetic safety tests for tenant-scoped booking command receipts."""

import hashlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Index, Integer, MetaData, String, Table, create_engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from app.core.config import settings
from app.models import (
    AuditLog,
    Booking,
    BookingCommandReceipt,
    BookingSlotAllocation,
    Client,
    Location,
    OutboxEvent,
    Provider,
    ProviderWorkDay,
    Service,
    ServiceProvider,
    Tenant,
)
from app.models.location import LocationProvider, LocationService
from app.schemas.booking import BookingCreate
from app.services import booking_creation_service
from app.services.booking_creation_service import (
    BookingCommandError,
    _canonical_command_bytes,
    create_authoritative_booking,
)


def _domain(db_session, suffix: str) -> dict:
    tenant = Tenant(name=f"Synthetic Receipt {suffix}", subdomain=f"receipt-{suffix}")
    db_session.add(tenant)
    db_session.flush()
    provider = Provider(tenant_id=tenant.id, name=f"Provider {suffix}", active=True)
    service = Service(
        tenant_id=tenant.id,
        name=f"Service {suffix}",
        duration=60,
        active=True,
        price=100,
    )
    location = Location(tenant_id=tenant.id, name=f"Location {suffix}", active=True)
    client = Client(
        tenant_id=tenant.id,
        name=f"Client {suffix}",
        email=f"client-{suffix}@example.invalid",
        phone="0411 222 333",
        active=True,
    )
    db_session.add_all([provider, service, location, client])
    db_session.flush()
    db_session.add_all(
        [
            ServiceProvider(
                tenant_id=tenant.id,
                service_id=service.id,
                provider_id=provider.id,
            ),
            LocationProvider(
                tenant_id=tenant.id,
                location_id=location.id,
                provider_id=provider.id,
            ),
            LocationService(
                tenant_id=tenant.id,
                location_id=location.id,
                service_id=service.id,
            ),
        ]
    )
    start = (datetime.now(timezone.utc) + timedelta(days=8)).replace(
        hour=10,
        minute=0,
        second=0,
        microsecond=0,
    )
    db_session.add(
        ProviderWorkDay(
            tenant_id=tenant.id,
            provider_id=provider.id,
            weekday=start.weekday(),
            start_time="09:00",
            end_time="17:00",
            is_working=True,
        )
    )
    db_session.commit()
    return {
        "tenant": tenant,
        "provider": provider,
        "service": service,
        "location": location,
        "client": client,
        "start": start,
    }


def _command(data: dict, *, key: str | None, **updates) -> BookingCreate:
    values = {
        "client_id": data["client"].id,
        "provider_id": data["provider"].id,
        "service_id": data["service"].id,
        "location_id": data["location"].id,
        "start_time": data["start"],
        "end_time": data["start"] + timedelta(minutes=data["service"].duration),
        "idempotency_key": key,
    }
    values.update(updates)
    return BookingCreate(**values)


def _row_counts(db_session) -> dict:
    return {
        "bookings": db_session.query(Booking).count(),
        "receipts": db_session.query(BookingCommandReceipt).count(),
        "slots": db_session.query(BookingSlotAllocation).count(),
        "outbox": db_session.query(OutboxEvent).count(),
        "audits": db_session.query(AuditLog).count(),
    }


def test_receipt_hmac_is_not_plain_digest_and_audit_is_not_replay_authority(db_session):
    data = _domain(db_session, uuid4().hex[:8])
    command = _command(
        data,
        key="synthetic-low-entropy-key",
        notes="synthetic-private-receipt-marker",
    )
    booking = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=command,
    )
    db_session.commit()

    receipt = db_session.query(BookingCommandReceipt).filter_by(
        tenant_id=data["tenant"].id,
        booking_id=booking.id,
    ).one()
    plain_digest = hashlib.sha256(
        _canonical_command_bytes(tenant_id=data["tenant"].id, command=command)
    ).hexdigest()
    assert receipt.request_hmac != plain_digest
    assert "synthetic-private-receipt-marker" not in receipt.request_hmac

    audit = db_session.query(AuditLog).filter_by(
        tenant_id=data["tenant"].id,
        action="booking.created",
        target_id=booking.id,
    ).one()
    assert json.loads(audit.details) == {"status": "pending", "source": "public_booking"}
    db_session.delete(audit)
    db_session.add(
        AuditLog(
            tenant_id=data["tenant"].id,
            action="booking.created",
            target_type="booking",
            target_id=booking.id,
            details=json.dumps(
                {
                    "source": "public_booking",
                    "request_fingerprint": "0" * 64,
                    "request_fingerprint_version": 999,
                }
            ),
        )
    )
    db_session.commit()
    before = _row_counts(db_session)

    replay = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=command,
    )
    assert replay.id == booking.id
    assert _row_counts(db_session) == before


@pytest.mark.parametrize("unavailable_secret", ["", "changeme", "short-secret"])
def test_unavailable_hmac_secret_fails_before_mutation(
    db_session,
    monkeypatch,
    unavailable_secret,
):
    data = _domain(db_session, uuid4().hex[:8])
    command = _command(data, key=f"secret-required-{uuid4()}")
    before = _row_counts(db_session)
    monkeypatch.setattr(settings, "SECRET_KEY", unavailable_secret)

    with pytest.raises(BookingCommandError) as error:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=command,
        )

    assert error.value.status_code == 503
    assert _row_counts(db_session) == before


def test_same_key_is_independent_across_tenants(db_session):
    left = _domain(db_session, f"left-{uuid4().hex[:6]}")
    right = _domain(db_session, f"right-{uuid4().hex[:6]}")
    key = f"shared-tenant-key-{uuid4()}"
    left_command = _command(left, key=key)
    right_command = _command(right, key=key)

    left_booking = create_authoritative_booking(
        db_session,
        tenant_id=left["tenant"].id,
        command=left_command,
    )
    right_booking = create_authoritative_booking(
        db_session,
        tenant_id=right["tenant"].id,
        command=right_command,
    )
    db_session.commit()

    assert left_booking.id != right_booking.id
    receipts = db_session.query(BookingCommandReceipt).filter_by(
        idempotency_key=key
    ).all()
    assert {receipt.tenant_id for receipt in receipts} == {
        left["tenant"].id,
        right["tenant"].id,
    }
    assert create_authoritative_booking(
        db_session,
        tenant_id=left["tenant"].id,
        command=left_command,
    ).id == left_booking.id
    assert create_authoritative_booking(
        db_session,
        tenant_id=right["tenant"].id,
        command=right_command,
    ).id == right_booking.id


def test_integrity_loser_returns_only_exact_winner_and_rolls_back_provisional_rows(
    db_session,
    monkeypatch,
):
    data = _domain(db_session, uuid4().hex[:8])
    command = _command(data, key=f"synthetic-race-{uuid4()}")
    winner = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=command,
    )
    db_session.commit()
    before = _row_counts(db_session)

    real_resolver = booking_creation_service._resolve_idempotent_replay
    calls = 0

    def simulate_stale_first_read(db, *, tenant_id, command):
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return real_resolver(db, tenant_id=tenant_id, command=command)

    monkeypatch.setattr(
        booking_creation_service,
        "_resolve_idempotent_replay",
        simulate_stale_first_read,
    )
    monkeypatch.setattr(
        booking_creation_service,
        "_revalidate_exact_slot",
        lambda *args, **kwargs: None,
    )

    replay = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=command,
    )
    assert replay.id == winner.id
    assert calls == 2
    assert _row_counts(db_session) == before


def test_stored_email_whitespace_is_canonical_and_ambiguous_duplicates_fail(db_session):
    data = _domain(db_session, uuid4().hex[:8])
    data["client"].email = "  SPACED-SYNTHETIC@example.invalid  "
    data["client"].phone = None
    db_session.commit()
    before_clients = db_session.query(Client).count()
    command = _command(
        data,
        key=f"email-space-{uuid4()}",
        client_id=None,
        client_name=data["client"].name,
        client_email="spaced-synthetic@example.invalid",
        client_phone=None,
    )

    booking = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=command,
    )
    assert booking.client_id == data["client"].id
    assert db_session.query(Client).count() == before_clients
    db_session.rollback()

    duplicate = Client(
        tenant_id=data["tenant"].id,
        name="Synthetic Inactive Spaced Duplicate",
        email=" spaced-synthetic@example.invalid ",
        active=False,
    )
    db_session.add(duplicate)
    db_session.commit()
    with pytest.raises(BookingCommandError) as ambiguous:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=command.model_copy(
                update={"idempotency_key": f"email-ambiguous-{uuid4()}"}
            ),
        )
    assert ambiguous.value.status_code == 409


@pytest.mark.parametrize(
    "selection",
    [
        {"addon_ids": [987654321], "product_ids": []},
        {"addon_ids": [], "product_ids": [987654321]},
    ],
)
def test_public_route_rejects_nonempty_commercial_selections_without_mutation(
    client,
    db_session,
    selection,
):
    data = _domain(db_session, uuid4().hex[:8])
    command = _command(
        data,
        key=f"commercial-selection-{uuid4()}",
        client_id=None,
        client_name=data["client"].name,
        client_email=data["client"].email,
        client_phone=None,
    )
    payload = command.model_dump(mode="json", exclude={"client_id"}) | selection
    before = _row_counts(db_session)

    response = client.post(
        "/api/public/bookings",
        json=payload,
        headers={"X-Tenant": data["tenant"].subdomain},
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == (
        "Public booking request contains unsupported fields."
    )
    assert "987654321" not in response.text
    assert _row_counts(db_session) == before


def test_receipt_schema_compiles_tenant_booking_integrity_for_postgresql():
    sql = str(
        CreateTable(BookingCommandReceipt.__table__).compile(
            dialect=postgresql.dialect()
        )
    )
    assert "FOREIGN KEY(tenant_id, booking_id)" in sql
    assert "REFERENCES bookings (tenant_id, id) ON DELETE CASCADE" in sql
    assert "UNIQUE (tenant_id, idempotency_key)" in sql
    assert "UNIQUE (booking_id)" in sql


def test_receipt_migration_upgrade_and_downgrade_in_disposable_sqlite():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "b6c2d4e8f0a1_add_booking_command_receipts.py"
    )
    spec = importlib.util.spec_from_file_location(
        "synthetic_booking_receipt_migration",
        migration_path,
    )
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "d7e8f9a0b1c2"

    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    bookings = Table(
        "bookings",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        Column("idempotency_key", String, nullable=True),
    )
    Index(
        "ix_bookings_idempotency_key",
        bookings.c.idempotency_key,
        unique=True,
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = inspect(connection)
        assert "booking_command_receipts" in inspector.get_table_names()
        assert {item["name"] for item in inspector.get_unique_constraints("bookings")} == {
            "uq_bookings_tenant_id_id",
            "uq_bookings_tenant_idempotency_key",
        }
        foreign_keys = inspector.get_foreign_keys("booking_command_receipts")
        assert foreign_keys[0]["constrained_columns"] == ["tenant_id", "booking_id"]
        assert foreign_keys[0]["referred_columns"] == ["tenant_id", "id"]

        connection.execute(
            text(
                "INSERT INTO bookings (id, tenant_id, idempotency_key) VALUES "
                "(1, 1, 'shared'), (2, 2, 'shared'), (3, 1, NULL), (4, 1, NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO booking_command_receipts "
                "(id, tenant_id, booking_id, idempotency_key, fingerprint_version, request_hmac, created_at) "
                "VALUES (1, 1, 1, 'shared', 1, :request_hmac, CURRENT_TIMESTAMP)"
            ),
            {"request_hmac": "a" * 64},
        )
        savepoint = connection.begin_nested()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO booking_command_receipts "
                    "(id, tenant_id, booking_id, idempotency_key, fingerprint_version, request_hmac, created_at) "
                    "VALUES (2, 2, 1, 'mismatch', 1, :request_hmac, CURRENT_TIMESTAMP)"
                ),
                {"request_hmac": "b" * 64},
            )
        savepoint.rollback()

        connection.execute(text("DELETE FROM booking_command_receipts"))
        connection.execute(text("DELETE FROM bookings WHERE id = 2"))
        migration.downgrade()
        inspector = inspect(connection)
        assert "booking_command_receipts" not in inspector.get_table_names()
        assert inspector.get_indexes("bookings") == [
            {
                "name": "ix_bookings_idempotency_key",
                "column_names": ["idempotency_key"],
                "unique": 1,
                "dialect_options": {},
            }
        ]
    engine.dispose()
