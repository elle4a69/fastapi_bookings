"""Synthetic regression tests for the authoritative booking command."""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.core.state_machine import BookingStatus
from app.models import (
    AuditLog,
    Booking,
    BookingSlotAllocation,
    BookingResourceAllocation,
    Client,
    Location,
    OutboxEvent,
    Provider,
    ProviderWorkDay,
    Resource,
    Service,
    ServiceProvider,
    ServiceResourceRequirement,
    Tenant,
)
from app.models.location import LocationProvider, LocationService
from app.schemas.booking import BookingCreate, PublicBookingCreate, PublicBookingReceipt
from app.services.booking_creation_service import (
    BookingCommandError,
    _resource_candidates_query,
    create_authoritative_booking,
)
from app.services.scheduling_service import compute_availability


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
    audit_details = json.loads(audit.details)
    assert set(audit_details) == {
        "status",
        "source",
        "request_fingerprint_version",
        "request_fingerprint",
    }
    assert audit_details["status"] == "pending"
    assert audit_details["source"] == "public_booking"
    assert audit_details["request_fingerprint_version"] == 1
    assert len(audit_details["request_fingerprint"]) == 64
    event = (
        db_session.query(OutboxEvent)
        .filter_by(tenant_id=data["tenant"].id, type="booking.created")
        .one()
    )
    assert set(event.data()) == {
        "id",
        "provider_id",
        "service_id",
        "start_time",
        "end_time",
        "status",
    }


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


def test_idempotency_key_reuse_with_changed_command_is_rejected(
    db_session, booking_command_setup
):
    data = booking_command_setup
    key = f"immutable-{uuid4()}"
    command = _command(data, idempotency_key=key, notes="original synthetic note")
    first = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=command,
    )

    with pytest.raises(BookingCommandError) as error:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(
                data,
                idempotency_key=key,
                notes="different synthetic note",
            ),
        )

    assert error.value.status_code == 409
    assert db_session.query(Booking).filter_by(id=first.id).one().notes == command.notes


def test_idempotent_contact_replay_uses_stable_identifier_not_display_name(
    db_session, booking_command_setup
):
    data = booking_command_setup
    data["client"].email = "stable-identity@example.invalid"
    db_session.flush()
    command = _command(
        data,
        client_id=None,
        client_name="Synthetic Alternate Display Name",
        client_email="STABLE-IDENTITY@example.invalid",
        client_phone=None,
        idempotency_key=f"contact-replay-{uuid4()}",
    )

    first = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=command,
    )
    replay = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=command,
    )

    assert replay.id == first.id


def test_idempotent_replay_uses_immutable_fingerprint_after_domain_changes(
    db_session, booking_command_setup
):
    data = booking_command_setup
    data["client"].email = "stable-original@example.invalid"
    db_session.commit()
    command = _command(
        data,
        client_id=None,
        client_name=data["client"].name,
        client_email=data["client"].email,
        client_phone=data["client"].phone,
        idempotency_key=f"immutable-fingerprint-{uuid4()}",
    )
    first = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=command,
    )
    db_session.commit()

    data["provider"].active = False
    data["service"].active = False
    data["service"].duration = 75
    data["location"].active = False
    data["client"].active = False
    data["client"].name = "Synthetic Changed Name"
    data["client"].email = "changed@example.invalid"
    data["client"].phone = "+61 499 000 999"
    db_session.query(LocationProvider).filter_by(
        tenant_id=data["tenant"].id,
        location_id=data["location"].id,
        provider_id=data["provider"].id,
    ).delete()
    db_session.query(LocationService).filter_by(
        tenant_id=data["tenant"].id,
        location_id=data["location"].id,
        service_id=data["service"].id,
    ).delete()
    db_session.commit()

    replay = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=command,
    )
    assert replay.id == first.id
    with pytest.raises(BookingCommandError) as changed:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=command.model_copy(update={"notes": "changed synthetic command"}),
        )
    assert changed.value.status_code == 409
    with pytest.raises(BookingCommandError) as malformed_change:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=command.model_copy(update={"client_phone": "not-a-phone"}),
        )
    assert malformed_change.value.status_code == 409


def test_replay_without_one_valid_versioned_fingerprint_fails_closed(
    db_session, booking_command_setup
):
    data = booking_command_setup
    command = _command(data, idempotency_key=f"legacy-fingerprint-{uuid4()}")
    booking = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=command,
    )
    audit = db_session.query(AuditLog).filter_by(
        tenant_id=data["tenant"].id,
        action="booking.created",
        target_type="booking",
        target_id=booking.id,
    ).one()
    duplicate = AuditLog(
        tenant_id=data["tenant"].id,
        action="booking.created",
        target_type="booking",
        target_id=booking.id,
        details=audit.details,
    )
    db_session.add(duplicate)
    db_session.flush()
    with pytest.raises(BookingCommandError) as duplicate_error:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=command,
        )
    assert duplicate_error.value.status_code == 409
    db_session.delete(duplicate)
    db_session.flush()

    audit.details = json.dumps({"status": "pending", "source": "public_booking"})
    db_session.flush()

    with pytest.raises(BookingCommandError) as missing:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=command,
        )
    assert missing.value.status_code == 409


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


def test_conflicting_phone_and_email_clients_fail_without_partial_rows(
    db_session, booking_command_setup
):
    data = booking_command_setup
    other = Client(
        tenant_id=data["tenant"].id,
        name="Synthetic Other Contact",
        email="other-contact@example.invalid",
        active=True,
    )
    db_session.add(other)
    db_session.commit()
    initial = {
        "clients": db_session.query(Client).count(),
        "bookings": db_session.query(Booking).count(),
        "events": db_session.query(OutboxEvent).count(),
        "audits": db_session.query(AuditLog).count(),
    }

    with pytest.raises(BookingCommandError) as conflict:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(
                data,
                client_id=None,
                client_phone=data["client"].phone,
                client_email=other.email,
            ),
        )
    assert conflict.value.status_code == 409
    with pytest.raises(BookingCommandError) as id_conflict:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(
                data,
                client_id=data["client"].id,
                client_phone=None,
                client_email=other.email,
            ),
        )
    assert id_conflict.value.status_code == 409
    assert initial == {
        "clients": db_session.query(Client).count(),
        "bookings": db_session.query(Booking).count(),
        "events": db_session.query(OutboxEvent).count(),
        "audits": db_session.query(AuditLog).count(),
    }


@pytest.mark.parametrize("duplicate_field", ["phone", "email"])
def test_duplicate_contact_identity_fails_closed_even_when_one_match_is_inactive(
    db_session, booking_command_setup, duplicate_field
):
    data = booking_command_setup
    data["client"].email = "duplicate@example.invalid"
    duplicate = Client(
        tenant_id=data["tenant"].id,
        name="Synthetic Inactive Duplicate",
        email=data["client"].email if duplicate_field == "email" else None,
        phone="0411 222 333" if duplicate_field == "phone" else None,
        active=False,
    )
    db_session.add(duplicate)
    db_session.commit()
    initial_bookings = db_session.query(Booking).count()

    overrides = {
        "client_id": None,
        "client_name": "Synthetic Ambiguous Contact",
        "client_phone": data["client"].phone if duplicate_field == "phone" else None,
        "client_email": data["client"].email if duplicate_field == "email" else None,
    }
    with pytest.raises(BookingCommandError) as ambiguous:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(data, **overrides),
        )
    assert ambiguous.value.status_code == 409
    assert db_session.query(Booking).count() == initial_bookings


def test_inactive_client_is_rejected_by_id_and_contact(db_session, booking_command_setup):
    data = booking_command_setup
    data["client"].active = False
    data["client"].email = "inactive-synthetic@example.invalid"
    db_session.commit()

    with pytest.raises(BookingCommandError) as by_id:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(data),
        )
    assert by_id.value.status_code == 403

    initial_clients = db_session.query(Client).count()
    with pytest.raises(BookingCommandError) as by_contact:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(
                data,
                client_id=None,
                client_name=data["client"].name,
                client_phone=data["client"].phone,
            ),
        )
    assert by_contact.value.status_code == 403
    assert db_session.query(Client).count() == initial_clients

    with pytest.raises(BookingCommandError) as by_email:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(
                data,
                client_id=None,
                client_name=data["client"].name,
                client_phone=None,
                client_email="INACTIVE-SYNTHETIC@example.invalid",
            ),
        )
    assert by_email.value.status_code == 403
    assert db_session.query(Client).count() == initial_clients


def test_missing_location_resolves_one_compatible_location_and_rejects_ambiguity(
    db_session, booking_command_setup
):
    data = booking_command_setup
    booking = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=_command(data, location_id=None),
    )
    assert booking.location_id == data["location"].id

    second_location = Location(
        tenant_id=data["tenant"].id,
        name="Synthetic Second Compatible Location",
        active=True,
    )
    db_session.add(second_location)
    db_session.flush()
    db_session.add_all(
        [
            LocationProvider(
                tenant_id=data["tenant"].id,
                location_id=second_location.id,
                provider_id=data["provider"].id,
            ),
            LocationService(
                tenant_id=data["tenant"].id,
                location_id=second_location.id,
                service_id=data["service"].id,
            ),
        ]
    )
    db_session.flush()

    with pytest.raises(BookingCommandError) as error:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(
                data,
                location_id=None,
                start_time=data["start"] + timedelta(days=1),
                end_time=data["start"] + timedelta(days=1, minutes=60),
            ),
        )
    assert error.value.status_code == 400
    assert "location is required" in error.value.detail.lower()


def test_resource_lock_query_is_deterministic_and_scope_bound(
    db_session, booking_command_setup
):
    data = booking_command_setup
    statement = _resource_candidates_query(
        db_session,
        tenant_id=data["tenant"].id,
        resource_type="synthetic-room",
        location_id=data["location"].id,
    ).statement
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "resources.tenant_id" in sql
    assert "resources.type" in sql
    assert "resources.location_id" in sql
    assert "ORDER BY resources.id" in sql
    assert sql.rstrip().endswith("FOR UPDATE")


def test_shared_capacity_one_resource_allows_only_one_provider(
    db_session, booking_command_setup
):
    data = booking_command_setup
    second_provider = Provider(
        tenant_id=data["tenant"].id,
        name="Synthetic Second Provider",
        active=True,
    )
    resource = Resource(
        tenant_id=data["tenant"].id,
        name="Synthetic Shared Room",
        type="synthetic-shared-room",
        location_id=data["location"].id,
        capacity=1,
        active=True,
    )
    db_session.add_all([second_provider, resource])
    db_session.flush()
    db_session.add_all(
        [
            ServiceProvider(
                tenant_id=data["tenant"].id,
                service_id=data["service"].id,
                provider_id=second_provider.id,
            ),
            LocationProvider(
                tenant_id=data["tenant"].id,
                location_id=data["location"].id,
                provider_id=second_provider.id,
            ),
            ProviderWorkDay(
                tenant_id=data["tenant"].id,
                provider_id=second_provider.id,
                weekday=data["start"].weekday(),
                start_time="09:00",
                end_time="17:00",
                is_working=True,
            ),
            ServiceResourceRequirement(
                service_id=data["service"].id,
                resource_type=resource.type,
                quantity=1,
            ),
        ]
    )
    db_session.flush()
    db_session.expire(data["service"], ["resource_requirements"])

    first = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=_command(data),
    )
    with pytest.raises(BookingCommandError) as error:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(data, provider_id=second_provider.id),
        )

    assert error.value.status_code == 409
    assert (
        db_session.query(BookingResourceAllocation)
        .filter_by(resource_id=resource.id, booking_id=first.id)
        .count()
        == 1
    )


def test_locationless_resource_search_uses_global_resources_only(
    db_session, booking_command_setup
):
    data = booking_command_setup
    global_resource = Resource(
        tenant_id=data["tenant"].id,
        name="Synthetic Global Resource",
        type="synthetic-scope-check",
        location_id=None,
        capacity=1,
        active=True,
    )
    local_resource = Resource(
        tenant_id=data["tenant"].id,
        name="Synthetic Local Resource",
        type="synthetic-scope-check",
        location_id=data["location"].id,
        capacity=1,
        active=True,
    )
    db_session.add_all([global_resource, local_resource])
    db_session.flush()

    candidates = _resource_candidates_query(
        db_session,
        tenant_id=data["tenant"].id,
        resource_type="synthetic-scope-check",
        location_id=None,
    ).all()

    assert [resource.id for resource in candidates] == [global_resource.id]


def test_minimum_buffer_is_revalidated_and_persisted_consistently(
    db_session, booking_command_setup
):
    data = booking_command_setup
    data["service"].buffer_before = 0
    data["service"].buffer_after = 0
    db_session.flush()
    create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=_command(data),
    )

    adjacent_start = data["start"] + timedelta(minutes=data["service"].duration)
    with pytest.raises(BookingCommandError) as buffered:
        create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(
                data,
                start_time=adjacent_start,
                end_time=adjacent_start + timedelta(minutes=data["service"].duration),
            ),
        )
    assert buffered.value.status_code == 409

    # Each booking owns a 15-minute buffer, so adjacent commands need a
    # 30-minute gap between appointment intervals.
    safe_start = adjacent_start + timedelta(minutes=30)
    second = create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=_command(
            data,
            start_time=safe_start,
            end_time=safe_start + timedelta(minutes=data["service"].duration),
        ),
    )
    assert second.start_time == safe_start


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Shared availability discovery does not yet apply the booking command's "
        "minimum 15-minute buffer policy."
    ),
)
def test_availability_does_not_advertise_a_slot_rejected_by_minimum_buffer(
    db_session, booking_command_setup
):
    data = booking_command_setup
    data["service"].buffer_before = 0
    data["service"].buffer_after = 0
    db_session.flush()
    create_authoritative_booking(
        db_session,
        tenant_id=data["tenant"].id,
        command=_command(data),
    )
    adjacent_start = data["start"] + timedelta(minutes=data["service"].duration)
    slots = compute_availability(
        db_session,
        service=data["service"],
        provider=data["provider"],
        location=data["location"],
        start_time=data["start"].replace(hour=0),
        end_time=data["start"].replace(hour=23, minute=59),
    )
    advertised_starts = {
        datetime.fromisoformat(slot["start_time"]).astimezone(timezone.utc)
        for slot in slots
    }
    assert adjacent_start not in advertised_starts


def test_command_preserves_outer_transaction_work_before_and_after_success(
    db_session, booking_command_setup
):
    data = booking_command_setup
    before = Client(
        tenant_id=data["tenant"].id,
        name="Synthetic Caller Work Before",
        active=True,
    )
    db_session.add(before)
    original_commit = db_session.commit
    original_rollback = db_session.rollback
    with patch.object(db_session, "commit", wraps=original_commit) as commit_spy, patch.object(
        db_session, "rollback", wraps=original_rollback
    ) as rollback_spy:
        booking = create_authoritative_booking(
            db_session,
            tenant_id=data["tenant"].id,
            command=_command(data),
        )
        after = Client(
            tenant_id=data["tenant"].id,
            name="Synthetic Caller Work After",
            active=True,
        )
        db_session.add(after)
        db_session.flush()
        assert commit_spy.call_count == 0
        assert rollback_spy.call_count == 0

    original_commit()
    assert db_session.query(Booking).filter_by(id=booking.id).one()
    assert db_session.query(Client).filter_by(id=before.id).one()
    assert db_session.query(Client).filter_by(id=after.id).one()


def test_command_failure_rolls_back_only_savepoint_and_preserves_caller_work(
    db_session, booking_command_setup
):
    data = booking_command_setup
    before = Client(
        tenant_id=data["tenant"].id,
        name="Synthetic Failure Caller Work Before",
        active=True,
    )
    db_session.add(before)
    original_commit = db_session.commit
    original_rollback = db_session.rollback
    with patch.object(db_session, "commit", wraps=original_commit) as commit_spy, patch.object(
        db_session, "rollback", wraps=original_rollback
    ) as rollback_spy, patch(
        "app.services.booking_creation_service.create_outbox_event",
        side_effect=RuntimeError("synthetic structural failure"),
    ):
        with pytest.raises(BookingCommandError) as error:
            create_authoritative_booking(
                db_session,
                tenant_id=data["tenant"].id,
                command=_command(
                    data,
                    client_id=None,
                    client_name="Synthetic Rolled Back Command Client",
                    client_email="rolled-back-command@example.invalid",
                    client_phone=None,
                ),
            )
        assert error.value.status_code == 500
        after = Client(
            tenant_id=data["tenant"].id,
            name="Synthetic Failure Caller Work After",
            active=True,
        )
        db_session.add(after)
        db_session.flush()
        assert commit_spy.call_count == 0
        assert rollback_spy.call_count == 0

    original_commit()
    assert db_session.query(Client).filter_by(id=before.id).one()
    assert db_session.query(Client).filter_by(id=after.id).one()
    assert (
        db_session.query(Client)
        .filter_by(email="rolled-back-command@example.invalid")
        .first()
        is None
    )
    assert db_session.query(Booking).filter_by(tenant_id=data["tenant"].id).count() == 0


def test_public_route_commits_only_after_command_returns(monkeypatch, booking_command_setup):
    from app.api.routers import public_bookings

    data = booking_command_setup
    command = PublicBookingCreate(
        client_name=data["client"].name,
        client_phone=data["client"].phone,
        provider_id=data["provider"].id,
        service_id=data["service"].id,
        location_id=data["location"].id,
        start_time=data["start"],
        end_time=data["start"] + timedelta(minutes=data["service"].duration),
        idempotency_key=f"public-commit-{uuid4()}",
    )
    fake_db = MagicMock()
    returned = SimpleNamespace(
        id=99,
        provider_id=data["provider"].id,
        service_id=data["service"].id,
        location_id=data["location"].id,
        start_time=data["start"],
        end_time=data["start"] + timedelta(minutes=data["service"].duration),
        status=BookingStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )

    def fake_command(db, *, tenant_id, command):
        assert db is fake_db
        assert tenant_id == data["tenant"].id
        fake_db.commit.assert_not_called()
        return returned

    monkeypatch.setattr(public_bookings, "create_authoritative_booking", fake_command)
    result = public_bookings.create_public_booking(
        command,
        db=fake_db,
        tenant=data["tenant"],
    )

    fake_db.commit.assert_called_once_with()
    fake_db.refresh.assert_not_called()
    assert fake_db.method_calls == [call.commit()]
    assert isinstance(result["data"], PublicBookingReceipt)
    assert result["data"].id == returned.id


def test_public_route_commit_failure_rolls_back_command_rows(
    db_session, booking_command_setup, monkeypatch
):
    from app.api.routers import public_bookings

    data = booking_command_setup
    command = PublicBookingCreate(
        client_name="Synthetic Commit Failure",
        client_email="commit-failure@example.invalid",
        provider_id=data["provider"].id,
        service_id=data["service"].id,
        location_id=data["location"].id,
        start_time=data["start"],
        end_time=data["start"] + timedelta(minutes=data["service"].duration),
        idempotency_key=f"commit-failure-{uuid4()}",
    )
    original_commit = db_session.commit

    def fail_commit():
        raise RuntimeError("synthetic commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(HTTPException) as failure:
        public_bookings.create_public_booking(
            command,
            db=db_session,
            tenant=data["tenant"],
        )
    assert failure.value.status_code == 500
    assert db_session.query(Booking).count() == 0
    assert db_session.query(OutboxEvent).count() == 0
    assert db_session.query(AuditLog).count() == 0
    monkeypatch.setattr(db_session, "commit", original_commit)


def test_public_api_contract_returns_real_pending_status(client, booking_command_setup):
    data = booking_command_setup
    command = _command(
        data,
        client_id=None,
        client_name=data["client"].name,
        client_phone=data["client"].phone,
    )
    payload = command.model_dump(mode="json", exclude={"client_id"})
    payload.update({"addon_ids": [], "product_ids": []})
    response = client.post(
        "/api/public/bookings",
        json=payload,
        headers={"X-Tenant": data["tenant"].subdomain},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "pending"
    assert set(body["data"]) == {
        "id",
        "provider_id",
        "service_id",
        "location_id",
        "start_time",
        "end_time",
        "status",
        "created_at",
    }


def test_public_route_rejects_client_id_and_openapi_response_is_redacted(
    client, booking_command_setup, caplog
):
    data = booking_command_setup
    marker = "synthetic-secret-client-id-marker"
    payload = _command(data).model_dump(mode="json")
    payload["client_id"] = marker
    response = client.post(
        "/api/public/bookings",
        json=payload,
        headers={"X-Tenant": data["tenant"].subdomain},
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"] == {}
    assert marker not in response.text
    assert marker not in caplog.text

    document = client.get("/openapi.json").json()
    operation = document["paths"]["/api/public/bookings"]["post"]
    request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    request_schema = document["components"]["schemas"][request_ref.rsplit("/", 1)[-1]]
    assert "client_id" not in request_schema["properties"]
    assert request_schema["additionalProperties"] is False
    response_schema = document["components"]["schemas"]["PublicBookingReceipt"]
    forbidden = {"client_id", "client", "client_name", "client_email", "client_phone", "notes", "idempotency_key"}
    assert forbidden.isdisjoint(response_schema["properties"])


def test_unexpected_failure_returns_generic_body_and_never_logs_sensitive_values(
    client,
    booking_command_setup,
    monkeypatch,
    caplog,
):
    from app.services import booking_creation_service

    data = booking_command_setup
    marker = "synthetic-private-note-and-key"

    def fail_outbox(*args, **kwargs):
        raise RuntimeError(marker)

    monkeypatch.setattr(booking_creation_service, "create_outbox_event", fail_outbox)
    command = _command(
        data,
        client_id=None,
        client_name="Synthetic Private Customer",
        client_email="private-synthetic@example.invalid",
        client_phone="0411 900 001",
        notes=marker,
        idempotency_key=marker,
    )
    response = client.post(
        "/api/public/bookings",
        json=command.model_dump(mode="json", exclude={"client_id"}),
        headers={"X-Tenant": data["tenant"].subdomain},
    )

    assert response.status_code == 500
    assert response.json()["error"]["message"] == "Unable to create booking."
    assert marker not in response.text
    assert marker not in caplog.text
    assert "private-synthetic@example.invalid" not in caplog.text
