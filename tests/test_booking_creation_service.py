"""Synthetic regression tests for the authoritative booking command."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.state_machine import BookingStatus
from app.models import (
    AuditLog,
    Booking,
    BookingSlotAllocation,
    Client,
    Location,
    OutboxEvent,
    Provider,
    ProviderWorkDay,
    Service,
    ServiceProvider,
    ServiceResourceRequirement,
    Tenant,
)
from app.models.location import LocationProvider, LocationService
from app.schemas.booking import BookingCreate
from app.services.booking_creation_service import (
    BookingCommandError,
    create_authoritative_booking,
)


@pytest.fixture
def booking_command_setup(db_session):
    suffix = uuid4().hex[:8]
    tenant = Tenant(name=f"Synthetic Booking Tenant {suffix}", subdomain=f"booking-{suffix}")
    db_session.add(tenant)
    db_session.flush()

    provider = Provider(tenant_id=tenant.id, name="Synthetic Provider", active=True)
    service = Service(
        tenant_id=tenant.id,
        name="Synthetic Service",
        duration=60,
        active=True,
        price=100,
    )
    location = Location(tenant_id=tenant.id, name="Synthetic Location", active=True)
    client = Client(
        tenant_id=tenant.id,
        name="Synthetic Existing Client",
        phone="+61 411 222 333",
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

    target = (datetime.now(timezone.utc) + timedelta(days=7)).replace(
        hour=10,
        minute=0,
        second=0,
        microsecond=0,
    )
    db_session.add(
        ProviderWorkDay(
            tenant_id=tenant.id,
            provider_id=provider.id,
            weekday=target.weekday(),
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
        "start": target,
    }


def _command(data, **overrides):
    values = {
        "client_id": data["client"].id,
        "provider_id": data["provider"].id,
        "service_id": data["service"].id,
        "location_id": data["location"].id,
        "start_time": data["start"],
        "end_time": data["start"] + timedelta(minutes=data["service"].duration),
        "idempotency_key": f"synthetic-booking-{uuid4()}",
    }
    values.update(overrides)
    return BookingCreate(**values)


def test_command_creates_pending_booking_allocations_event_and_audit(
    db_session, booking_command_setup
):
    data = booking_command_setup
    booking = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=_command(data),
    )

    assert booking.status == BookingStatus.PENDING
    assert booking.end_time - booking.start_time == timedelta(minutes=60)
    assert db_session.query(BookingSlotAllocation).filter_by(booking_id=booking.id).count() == 6
    assert (
        db_session.query(OutboxEvent)
        .filter_by(tenant_id=data["tenant"].id, type="booking.created")
        .count()
        == 1
    )
    audit = db_session.query(AuditLog).filter_by(
        tenant_id=data["tenant"].id,
        action="booking.created",
        target_id=booking.id,
    ).one()
    assert audit.user_id is None
    assert "pending" in audit.details


def test_same_tenant_idempotent_replay_creates_no_new_rows(db_session, booking_command_setup):
    data = booking_command_setup
    command = _command(data, idempotency_key=f"same-tenant-{uuid4()}")
    first = create_authoritative_booking(db_session, tenant_id=data["tenant"].id, command=command)
    counts = {
        "clients": db_session.query(Client).count(),
        "bookings": db_session.query(Booking).count(),
        "slots": db_session.query(BookingSlotAllocation).count(),
        "events": db_session.query(OutboxEvent).count(),
        "audits": db_session.query(AuditLog).count(),
    }

    replay = create_authoritative_booking(db_session, tenant_id=data["tenant"].id, command=command)

    assert replay.id == first.id
    assert counts == {
        "clients": db_session.query(Client).count(),
        "bookings": db_session.query(Booking).count(),
        "slots": db_session.query(BookingSlotAllocation).count(),
        "events": db_session.query(OutboxEvent).count(),
        "audits": db_session.query(AuditLog).count(),
    }


def test_cross_tenant_ids_and_global_key_collision_fail_without_partial_rows(
    db_session, booking_command_setup
):
    data = booking_command_setup
    key = f"cross-tenant-{uuid4()}"
    create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=_command(data, idempotency_key=key),
    )

    other = Tenant(name="Synthetic Other Tenant", subdomain=f"other-{uuid4().hex[:8]}")
    db_session.add(other)
    db_session.commit()
    before = (db_session.query(Client).count(), db_session.query(Booking).count())

    with pytest.raises(BookingCommandError) as cross_id:
        create_authoritative_booking(
            db_session,
            tenant_id=other.id,
            command=_command(data, idempotency_key=f"foreign-ids-{uuid4()}"),
        )
    assert cross_id.value.status_code == 404

    with pytest.raises(BookingCommandError) as collision:
        create_authoritative_booking(
            db_session,
            tenant_id=other.id,
            command=_command(
                data,
                client_id=None,
                client_name="Synthetic Other Customer",
                client_phone="0411 555 666",
                idempotency_key=key,
            ),
        )
    assert collision.value.status_code == 409
    assert before == (db_session.query(Client).count(), db_session.query(Booking).count())


def test_incompatible_location_and_provider_fail_closed(db_session, booking_command_setup):
    data = booking_command_setup
    other_provider = Provider(
        tenant_id=data["tenant"].id,
        name="Synthetic Ineligible Provider",
        active=True,
    )
    other_location = Location(
        tenant_id=data["tenant"].id,
        name="Synthetic Ineligible Location",
        active=True,
    )
    db_session.add_all([other_provider, other_location])
    db_session.commit()

    with pytest.raises(BookingCommandError) as provider_error:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(data, provider_id=other_provider.id),
        )
    assert provider_error.value.status_code == 400

    with pytest.raises(BookingCommandError) as location_error:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(data, location_id=other_location.id),
        )
    assert location_error.value.status_code == 400


def test_stale_or_wrong_duration_slot_rolls_back_new_client(db_session, booking_command_setup):
    data = booking_command_setup
    initial_clients = db_session.query(Client).count()

    with pytest.raises(BookingCommandError) as duration_error:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(
                data,
                client_id=None,
                client_name="Synthetic Unsaved Customer",
                client_phone="0411 777 888",
                end_time=data["start"] + timedelta(minutes=30),
            ),
        )
    assert duration_error.value.status_code == 400
    assert db_session.query(Client).count() == initial_clients

    with pytest.raises(BookingCommandError) as stale_error:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(
                data,
                client_id=None,
                client_name="Synthetic Unsaved Customer",
                client_phone="0411 777 888",
                start_time=data["start"].replace(minute=7),
                end_time=data["start"].replace(minute=7) + timedelta(minutes=60),
            ),
        )
    assert stale_error.value.status_code == 409
    assert db_session.query(Client).count() == initial_clients


def test_missing_resource_rejects_without_partial_client(db_session, booking_command_setup):
    data = booking_command_setup
    db_session.add(
        ServiceResourceRequirement(
            service_id=data["service"].id,
            resource_type="synthetic-unavailable-room",
            quantity=1,
        )
    )
    db_session.commit()
    initial_clients = db_session.query(Client).count()

    with pytest.raises(BookingCommandError) as error:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(
                data,
                client_id=None,
                client_name="Synthetic Resource Customer",
                client_phone="0411 888 999",
            ),
        )
    assert error.value.status_code == 409
    assert db_session.query(Client).count() == initial_clients
    assert db_session.query(Booking).filter_by(tenant_id=data["tenant"].id).count() == 0


def test_phone_matching_is_canonical_and_does_not_duplicate_client(
    db_session, booking_command_setup
):
    data = booking_command_setup
    initial_clients = db_session.query(Client).count()
    booking = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=_command(
            data,
            client_id=None,
            client_name="Different Display Name",
            client_phone="0411 222 333",
        ),
    )
    assert booking.client_id == data["client"].id
    assert db_session.query(Client).count() == initial_clients


def test_public_api_contract_returns_real_pending_status(client, booking_command_setup):
    data = booking_command_setup
    command = _command(data)
    response = client.post(
        "/api/public/bookings",
        json=command.model_dump(mode="json"),
        headers={"X-Tenant": data["tenant"].subdomain},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "pending"
