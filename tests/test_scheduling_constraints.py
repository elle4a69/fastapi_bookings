"""Tests for scheduling constraints: blocked time, holds, reservations, and buffers."""

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.service import Service
from app.models.client import Client
from app.models.booking import Booking
from app.models.schedule import ProviderWorkDay, BlockedTime, ReservedTime
from app.models.hold import Hold, HoldStatus
from app.core.state_machine import BookingStatus

from app.services.scheduling_service import compute_availability


def _setup_base_data(db_session: Session):
    """Helper to bootstrap base tenant, provider, client, and service."""
    tenant = Tenant(name="Scheduling Biz", subdomain="sched-biz", created_at=datetime.now(timezone.utc))
    db_session.add(tenant)
    db_session.commit()

    provider = Provider(tenant_id=tenant.id, name="Dr. Alex", active=True, created_at=datetime.now(timezone.utc))
    client = Client(tenant_id=tenant.id, name="John Doe", email="john@example.com", active=True, created_at=datetime.now(timezone.utc))
    service = Service(
        tenant_id=tenant.id,
        name="Consultation",
        duration=30,
        price=50.0,
        active=True,
        buffer_before=0,
        buffer_after=0,
        fixed_start_times=None
    )
    db_session.add_all([provider, client, service])
    db_session.commit()

    return tenant, provider, client, service


def test_constraints_blocking_slots(db_session):
    """Verify BlockedTime, unexpired Hold, and ReservedTime prevent slots from being booked."""
    tenant, provider, client, service = _setup_base_data(db_session)

    # Monday workday 09:00 - 11:00 (7 slots)
    workday = ProviderWorkDay(
        tenant_id=tenant.id, provider_id=provider.id, weekday=0,
        start_time="09:00", end_time="11:00", is_working=True, created_at=datetime.now(timezone.utc)
    )
    db_session.add(workday)
    db_session.commit()

    # 1. Add BlockedTime at 09:00-09:30
    block = BlockedTime(
        tenant_id=tenant.id, provider_id=provider.id,
        start_time=datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 6, 9, 30, tzinfo=timezone.utc),
        active=True, created_at=datetime.now(timezone.utc)
    )
    # 2. Add unexpired Hold at 09:45-10:15
    hold = Hold(
        tenant_id=tenant.id, service_id=service.id, provider_id=provider.id,
        start_time=datetime(2026, 7, 6, 9, 45, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 6, 10, 15, tzinfo=timezone.utc),
        status=HoldStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        created_at=datetime.now(timezone.utc)
    )
    # 3. Add ReservedTime at 10:30-11:00
    reservation = ReservedTime(
        tenant_id=tenant.id, provider_id=provider.id,
        start_time=datetime(2026, 7, 6, 10, 30, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 6, 11, 0, tzinfo=timezone.utc),
        expires_at=None, created_at=datetime.now(timezone.utc)
    )
    db_session.add_all([block, hold, reservation])
    db_session.commit()

    start_time = datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 7, 6, 23, 59, tzinfo=timezone.utc)

    slots = compute_availability(db_session, service=service, provider=provider, start_time=start_time, end_time=end_time)

    # No slot should be completely free:
    # 09:00, 09:15 overlaps with block
    # 09:30 overlaps with hold (9:45-10:15)
    # 09:45 overlaps with hold
    # 10:00 overlaps with hold
    # 10:15 overlaps with reservation (10:30-11:00)
    # 10:30 overlaps with reservation
    assert len(slots) == 0


def test_service_buffers(db_session):
    """Verify that buffer before/after on existing bookings blocks adjacent slots."""
    tenant, provider, client, service = _setup_base_data(db_session)

    # Update service buffers: buffer_before=15, buffer_after=15
    service.buffer_before = 15
    service.buffer_after = 15
    db_session.commit()

    # Monday workday 09:00 - 11:00
    workday = ProviderWorkDay(
        tenant_id=tenant.id, provider_id=provider.id, weekday=0,
        start_time="09:00", end_time="11:00", is_working=True, created_at=datetime.now(timezone.utc)
    )
    db_session.add(workday)

    # Booking at 09:45 to 10:15
    booking = Booking(
        tenant_id=tenant.id, client_id=client.id, provider_id=provider.id, service_id=service.id,
        start_time=datetime(2026, 7, 6, 9, 45, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 6, 10, 15, tzinfo=timezone.utc),
        status=BookingStatus.CONFIRMED,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    )
    db_session.add(booking)
    db_session.commit()

    start_time = datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 7, 6, 23, 59, tzinfo=timezone.utc)

    slots = compute_availability(db_session, service=service, provider=provider, start_time=start_time, end_time=end_time)

    # Booking with buffer_before=15 and buffer_after=15 means 09:30 to 10:30 is blocked.
    # Candidates starting at:
    # 09:00 (ends 09:30) -> Free!
    # 09:15 (ends 09:45) -> Overlaps with 09:30-10:30 block -> Blocked
    # 09:30 (ends 10:00) -> Overlaps -> Blocked
    # 10:30 (ends 11:00) -> Free! (starts right at 10:30, after 10:30 blocked end)
    # Let's assert we have exactly 2 free slots: 09:00-09:30 and 10:30-11:00.
    start_times = [s["start_time"] for s in slots]
    assert len(slots) == 2
    assert "2026-07-06T09:00:00+00:00" in start_times
    assert "2026-07-06T10:30:00+00:00" in start_times
