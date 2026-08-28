"""Tests for slot allocation audit and repair integrity."""

from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Tenant, Service, Provider, Client, Booking, BookingSlotAllocation
from app.core.state_machine import BookingStatus
from app.services.slot_allocation_service import (
    audit_and_repair_slot_allocations,
    SlotAllocationIntegrityError,
    generate_slot_timestamps,
)


@pytest.fixture
def repair_test_setup(db_session: Session):
    """Setup test data for slot allocation repair tests."""
    tenant = db_session.query(Tenant).filter(Tenant.subdomain == "repair-test").first()
    if not tenant:
        tenant = Tenant(name="Repair Test Tenant", subdomain="repair-test")
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)

    client_obj = db_session.query(Client).filter(Client.email == "repair-client@example.com", Client.tenant_id == tenant.id).first()
    if not client_obj:
        client_obj = Client(
            name="Repair Client",
            email="repair-client@example.com",
            phone="+15559990000",
            tenant_id=tenant.id,
        )
        db_session.add(client_obj)
        db_session.commit()
        db_session.refresh(client_obj)

    provider = db_session.query(Provider).filter(Provider.name == "Repair Provider", Provider.tenant_id == tenant.id).first()
    if not provider:
        provider = Provider(name="Repair Provider", tenant_id=tenant.id, active=True, ignore_company_hours=True)
        db_session.add(provider)
        db_session.commit()
        db_session.refresh(provider)

    service = db_session.query(Service).filter(Service.name == "Repair Service", Service.tenant_id == tenant.id).first()
    if not service:
        service = Service(
            name="Repair Service",
            duration=30,
            price=60.0,
            tenant_id=tenant.id,
            active=True,
            buffer_before=15,
            buffer_after=15,
        )
        db_session.add(service)
        db_session.commit()
        db_session.refresh(service)

    return {
        "tenant": tenant,
        "client": client_obj,
        "provider": provider,
        "service": service,
    }


def test_missing_allocation_repair(repair_test_setup, db_session: Session):
    """Test that active bookings with zero slot allocations are detected and repaired."""
    tenant = repair_test_setup["tenant"]
    client_obj = repair_test_setup["client"]
    provider = repair_test_setup["provider"]
    service = repair_test_setup["service"]

    start_dt = (datetime.now(timezone.utc) + timedelta(days=20)).replace(hour=10, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=30)

    booking = Booking(
        tenant_id=tenant.id,
        client_id=client_obj.id,
        provider_id=provider.id,
        service_id=service.id,
        start_time=start_dt,
        end_time=end_dt,
        status=BookingStatus.PENDING,
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    # 1. Dry run detects incomplete/missing allocations
    dry_result = audit_and_repair_slot_allocations(db_session, dry_run=True)
    assert dry_result.incomplete_allocations >= 1
    assert dry_result.is_valid is True

    # 2. Real repair creates the missing allocations
    repair_result = audit_and_repair_slot_allocations(db_session, dry_run=False)
    assert repair_result.repaired_bookings >= 1
    assert repair_result.is_valid is True

    db_session.expire_all()
    allocs = (
        db_session.query(BookingSlotAllocation)
        .filter(BookingSlotAllocation.booking_id == booking.id)
        .all()
    )
    # 30m duration + 15m buffer_before + 15m buffer_after = 60m / 15m = 4 slots
    assert len(allocs) == 4


def test_incomplete_allocation_repair(repair_test_setup, db_session: Session):
    """Test that active bookings with partially missing or corrupt allocations are repaired."""
    tenant = repair_test_setup["tenant"]
    client_obj = repair_test_setup["client"]
    provider = repair_test_setup["provider"]
    service = repair_test_setup["service"]

    start_dt = (datetime.now(timezone.utc) + timedelta(days=21)).replace(hour=14, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=30)

    booking = Booking(
        tenant_id=tenant.id,
        client_id=client_obj.id,
        provider_id=provider.id,
        service_id=service.id,
        start_time=start_dt,
        end_time=end_dt,
        status=BookingStatus.PENDING,
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    # Insert only 1 out of 4 expected allocations
    partial_alloc = BookingSlotAllocation(
        tenant_id=tenant.id,
        booking_id=booking.id,
        provider_id=provider.id,
        slot_start=start_dt,
    )
    db_session.add(partial_alloc)
    db_session.commit()

    # Dry run detects incomplete allocations
    dry_res = audit_and_repair_slot_allocations(db_session, dry_run=True)
    assert dry_res.incomplete_allocations >= 1

    # Repair completes the set
    repair_res = audit_and_repair_slot_allocations(db_session, dry_run=False)
    assert repair_res.repaired_bookings >= 1

    db_session.expire_all()
    allocs = (
        db_session.query(BookingSlotAllocation)
        .filter(BookingSlotAllocation.booking_id == booking.id)
        .all()
    )
    assert len(allocs) == 4


def test_collision_detection_and_abort(repair_test_setup, db_session: Session):
    """Test that overlapping active historical bookings are detected as collisions and abort repair."""
    tenant = repair_test_setup["tenant"]
    client_obj = repair_test_setup["client"]
    provider = repair_test_setup["provider"]
    service = repair_test_setup["service"]

    start_dt = (datetime.now(timezone.utc) + timedelta(days=22)).replace(hour=9, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=30)

    # Booking 1: 09:00 - 09:30
    b1 = Booking(
        tenant_id=tenant.id,
        client_id=client_obj.id,
        provider_id=provider.id,
        service_id=service.id,
        start_time=start_dt,
        end_time=end_dt,
        status=BookingStatus.PENDING,
    )
    # Booking 2: 09:15 - 09:45 (overlapping)
    b2 = Booking(
        tenant_id=tenant.id,
        client_id=client_obj.id,
        provider_id=provider.id,
        service_id=service.id,
        start_time=start_dt + timedelta(minutes=15),
        end_time=end_dt + timedelta(minutes=15),
        status=BookingStatus.PENDING,
    )
    db_session.add_all([b1, b2])
    db_session.commit()

    # Dry run reports collision conflict
    dry_res = audit_and_repair_slot_allocations(db_session, dry_run=True)
    assert dry_res.collision_conflicts >= 1
    assert dry_res.is_valid is False

    # Non-dry run raises SlotAllocationIntegrityError and aborts
    with pytest.raises(SlotAllocationIntegrityError):
        audit_and_repair_slot_allocations(db_session, dry_run=False)


def test_malformed_datetime_detection_and_abort(repair_test_setup, db_session: Session):
    """Test that corrupt/inverted start/end timestamps are flagged as malformed and abort repair."""
    tenant = repair_test_setup["tenant"]
    client_obj = repair_test_setup["client"]
    provider = repair_test_setup["provider"]
    service = repair_test_setup["service"]

    start_dt = (datetime.now(timezone.utc) + timedelta(days=23)).replace(hour=12, minute=0, second=0, microsecond=0)
    # Inverted: end_time before start_time
    end_dt = start_dt - timedelta(minutes=30)

    b_corrupt = Booking(
        tenant_id=tenant.id,
        client_id=client_obj.id,
        provider_id=provider.id,
        service_id=service.id,
        start_time=start_dt,
        end_time=end_dt,
        status=BookingStatus.PENDING,
    )
    db_session.add(b_corrupt)
    db_session.commit()

    # Dry run detects malformed record
    dry_res = audit_and_repair_slot_allocations(db_session, dry_run=True)
    assert dry_res.malformed_records >= 1
    assert dry_res.is_valid is False

    # Repair aborts
    with pytest.raises(SlotAllocationIntegrityError):
        audit_and_repair_slot_allocations(db_session, dry_run=False)


def test_idempotent_repeat_execution(repair_test_setup, db_session: Session):
    """Test that multiple runs of audit and repair produce consistent, idempotent results."""
    tenant = repair_test_setup["tenant"]
    client_obj = repair_test_setup["client"]
    provider = repair_test_setup["provider"]
    service = repair_test_setup["service"]

    start_dt = (datetime.now(timezone.utc) + timedelta(days=24)).replace(hour=16, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=30)

    booking = Booking(
        tenant_id=tenant.id,
        client_id=client_obj.id,
        provider_id=provider.id,
        service_id=service.id,
        start_time=start_dt,
        end_time=end_dt,
        status=BookingStatus.PENDING,
    )
    db_session.add(booking)
    db_session.commit()

    # First run repairs booking
    res1 = audit_and_repair_slot_allocations(db_session, dry_run=False)
    assert res1.is_valid is True

    # Second run finds everything fully allocated
    res2 = audit_and_repair_slot_allocations(db_session, dry_run=False)
    assert res2.is_valid is True
    assert res2.repaired_bookings == 0
    assert res2.incomplete_allocations == 0
