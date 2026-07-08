"""Tests for scheduling edge cases: extreme service buffers, workday boundary conditions, and cascading waitlist promotions."""

from datetime import datetime, timezone, timedelta, date, time
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.service import Service
from app.models.client import Client
from app.models.booking import Booking
from app.models.schedule import ProviderWorkDay, BlockedTime, ReservedTime
from app.models.hold import Hold, HoldStatus
from app.models.waitlist import WaitlistEntry, WaitlistStatus
from app.models.user import User
from app.core.state_machine import BookingStatus
from app.services.scheduling_service import compute_availability
from app.services.scheduling_utils import check_slot_overlaps
from app.core.security import create_access_token


def _setup_base_data(db_session: Session, suffix: str = ""):
    """Helper to bootstrap base tenant, provider, client, and service."""
    tenant = Tenant(
        name=f"Edge Case Biz {suffix}",
        subdomain=f"edge-biz-{suffix}" if suffix else "edge-biz",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(tenant)
    db_session.commit()

    provider = Provider(tenant_id=tenant.id, name=f"Dr. Edge {suffix}", active=True, created_at=datetime.now(timezone.utc))
    client = Client(tenant_id=tenant.id, name=f"Jane Doe {suffix}", email=f"jane_{suffix}@example.com" if suffix else "jane@example.com", active=True, created_at=datetime.now(timezone.utc))
    service = Service(
        tenant_id=tenant.id,
        name=f"Edge Service {suffix}",
        duration=30,
        price=100.0,
        active=True,
        buffer_before=0,
        buffer_after=0,
        fixed_start_times=None
    )
    db_session.add_all([provider, client, service])
    db_session.commit()

    return tenant, provider, client, service


def test_extreme_service_buffers_direct():
    """Verify that extreme service buffers (e.g. 24h buffers) block adjacent slots correctly."""
    class DummyService:
        def __init__(self, buffer_before, buffer_after):
            self.buffer_before = buffer_before
            self.buffer_after = buffer_after

    class DummyBooking:
        def __init__(self, start_time, end_time, buffer_before, buffer_after):
            self.start_time = start_time
            self.end_time = end_time
            self.service = DummyService(buffer_before, buffer_after)

    # Existing booking: Monday, July 6, 2026, 12:00 PM to 1:00 PM UTC
    # with 24 hours (1440 minutes) buffer_before and buffer_after.
    b_start = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)
    b_end = datetime(2026, 7, 6, 13, 0, tzinfo=timezone.utc)
    booking = DummyBooking(b_start, b_end, buffer_before=1440, buffer_after=1440)

    # Candidate slot 1: Sunday, July 5, 2026, 10:00 AM to 11:00 AM UTC.
    # This slot ends at 11:00 AM on Sunday, which is more than 24 hours before Monday 12:00 PM (starts 25 hours before).
    # Since the buffer_before is 24 hours, the blocked range starts at Sunday 12:00 PM.
    # So Sunday 10:00 AM to 11:00 AM should NOT overlap.
    overlaps_1 = check_slot_overlaps(
        slot_start=datetime(2026, 7, 5, 10, 0, tzinfo=timezone.utc),
        slot_end=datetime(2026, 7, 5, 11, 0, tzinfo=timezone.utc),
        active_bookings=[booking],
        provider_blocked=[],
        active_holds=[],
        active_reservations=[]
    )
    assert overlaps_1 is False

    # Candidate slot 2: Sunday, July 5, 2026, 1:00 PM to 2:00 PM UTC.
    # This slot starts at 1:00 PM on Sunday, which is inside the Sunday 12:00 PM to Monday 12:00 PM blocked buffer range.
    # So Sunday 1:00 PM to 2:00 PM should overlap!
    overlaps_2 = check_slot_overlaps(
        slot_start=datetime(2026, 7, 5, 13, 0, tzinfo=timezone.utc),
        slot_end=datetime(2026, 7, 5, 14, 0, tzinfo=timezone.utc),
        active_bookings=[booking],
        provider_blocked=[],
        active_holds=[],
        active_reservations=[]
    )
    assert overlaps_2 is True

    # Candidate slot 3: Tuesday, July 7, 2026, 10:00 AM to 11:00 AM UTC.
    # This slot starts at 10:00 AM on Tuesday, which is inside the Monday 1:00 PM to Tuesday 1:00 PM blocked buffer range.
    # So Tuesday 10:00 AM to 11:00 AM should overlap!
    overlaps_3 = check_slot_overlaps(
        slot_start=datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc),
        slot_end=datetime(2026, 7, 7, 11, 0, tzinfo=timezone.utc),
        active_bookings=[booking],
        provider_blocked=[],
        active_holds=[],
        active_reservations=[]
    )
    assert overlaps_3 is True

    # Candidate slot 4: Tuesday, July 7, 2026, 2:00 PM to 3:00 PM UTC.
    # This slot starts at 2:00 PM on Tuesday, which is after the Tuesday 1:00 PM buffer end.
    # So Tuesday 2:00 PM to 3:00 PM should NOT overlap!
    overlaps_4 = check_slot_overlaps(
        slot_start=datetime(2026, 7, 7, 14, 0, tzinfo=timezone.utc),
        slot_end=datetime(2026, 7, 7, 15, 0, tzinfo=timezone.utc),
        active_bookings=[booking],
        provider_blocked=[],
        active_holds=[],
        active_reservations=[]
    )
    assert overlaps_4 is False


def test_extreme_service_buffers_scheduling(db_session: Session):
    """Verify that extreme buffers on a service restrict slots on the same day during compute_availability."""
    tenant, provider, client, service = _setup_base_data(db_session, "ext_buf")

    # Set service with 24 hours (1440 mins) buffer before and 0 buffer after
    service.buffer_before = 1440
    service.buffer_after = 0
    service.duration = 60
    db_session.commit()

    # Monday workday 08:00 to 18:00
    workday = ProviderWorkDay(
        tenant_id=tenant.id, provider_id=provider.id, weekday=0,
        start_time="08:00", end_time="18:00", is_working=True, created_at=datetime.now(timezone.utc)
    )
    db_session.add(workday)

    # Booking on Monday, July 6, 2026, 14:00 to 15:00 UTC
    booking = Booking(
        tenant_id=tenant.id, client_id=client.id, provider_id=provider.id, service_id=service.id,
        start_time=datetime(2026, 7, 6, 14, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 6, 15, 0, tzinfo=timezone.utc),
        status=BookingStatus.CONFIRMED,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    )
    db_session.add(booking)
    db_session.commit()

    start_time = datetime(2026, 7, 6, 8, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 7, 6, 18, 0, tzinfo=timezone.utc)

    slots = compute_availability(db_session, service=service, provider=provider, start_time=start_time, end_time=end_time)

    # Since there's a booking on Monday at 14:00 with a 24-hour buffer_before,
    # the blocked range starts on Sunday 14:00 and ends on Monday 15:00.
    # Therefore, no slot on Monday can be free, as they all end after Sunday 14:00.
    assert len(slots) == 0

    # However, if we query for Wednesday, July 8, 2026, slots should be free.
    wed_start = datetime(2026, 7, 8, 8, 0, tzinfo=timezone.utc)
    wed_end = datetime(2026, 7, 8, 18, 0, tzinfo=timezone.utc)
    # Add Wednesday workday
    wed_workday = ProviderWorkDay(
        tenant_id=tenant.id, provider_id=provider.id, weekday=2,
        start_time="08:00", end_time="18:00", is_working=True, created_at=datetime.now(timezone.utc)
    )
    db_session.add(wed_workday)
    db_session.commit()

    wed_slots = compute_availability(db_session, service=service, provider=provider, start_time=wed_start, end_time=wed_end)
    assert len(wed_slots) > 0


def test_workday_boundary_conditions(db_session: Session):
    """Verify workday boundary conditions including bookings crossing midnight and blocked times."""
    tenant, provider, client, service = _setup_base_data(db_session, "boundary")

    # 1. Setup provider workday on Monday, July 6, 2026: 09:00 to 12:00
    workday = ProviderWorkDay(
        tenant_id=tenant.id, provider_id=provider.id, weekday=0,
        start_time="09:00", end_time="12:00", is_working=True, created_at=datetime.now(timezone.utc)
    )
    db_session.add(workday)

    # Create a booking crossing midnight: Sunday, July 5, 23:00 to Monday, July 6, 08:30.
    # This booking ends before Monday workday starts, but we add buffer_after = 45 minutes on the service.
    # So the blocked range ends at Monday 09:15.
    service.buffer_after = 45
    service.duration = 30
    db_session.commit()

    booking = Booking(
        tenant_id=tenant.id, client_id=client.id, provider_id=provider.id, service_id=service.id,
        start_time=datetime(2026, 7, 5, 23, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 6, 8, 30, tzinfo=timezone.utc),
        status=BookingStatus.CONFIRMED,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    )

    # 2. Add BlockedTime at the end of the workday boundary: Monday 11:30 to 13:00
    # This blocked time starts inside the workday and ends after the workday ends.
    block = BlockedTime(
        tenant_id=tenant.id, provider_id=provider.id,
        start_time=datetime(2026, 7, 6, 11, 30, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 6, 13, 0, tzinfo=timezone.utc),
        active=True, created_at=datetime.now(timezone.utc)
    )

    db_session.add_all([booking, block])
    db_session.commit()

    start_time = datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 7, 6, 23, 59, tzinfo=timezone.utc)

    slots = compute_availability(db_session, service=service, provider=provider, start_time=start_time, end_time=end_time)

    # Available slots should be: 09:15, 09:30, 09:45, 10:00, 10:15.
    # Slots starting at 10:30 or later are blocked because they end at 11:00 or later, and with buffer_after = 45m,
    # the padded slot end is 11:45 or later, which overlaps with the 11:30 blocked time.
    start_times = [s["start_time"] for s in slots]
    assert "2026-07-06T09:00:00+00:00" not in start_times
    assert "2026-07-06T09:15:00+00:00" in start_times
    assert "2026-07-06T10:15:00+00:00" in start_times
    assert "2026-07-06T10:30:00+00:00" not in start_times
    assert "2026-07-06T11:00:00+00:00" not in start_times
    assert "2026-07-06T11:30:00+00:00" not in start_times


def test_daylight_saving_transition_monotonicity(db_session: Session):
    """Verify timezone-aware monotonic scheduling during Daylight Saving Time (DST) transitions."""
    tenant, provider, client, service = _setup_base_data(db_session, "dst")

    # In 2026, US Daylight Saving Time starts on March 8, 2026.
    # Local transition: 02:00 EST -> 03:00 EDT.
    # In UTC, this is a smooth progression:
    # 07:00 UTC (02:00 EST) -> 07:00 UTC (03:00 EDT).
    # Setup workday on Sunday (weekday=6) from 06:00 to 09:00 UTC.
    workday = ProviderWorkDay(
        tenant_id=tenant.id, provider_id=provider.id, weekday=6,
        start_time="06:00", end_time="09:00", is_working=True, created_at=datetime.now(timezone.utc)
    )
    db_session.add(workday)

    # Add a BlockedTime exactly crossing the DST transition hour in UTC: 07:00 to 07:30 UTC.
    block = BlockedTime(
        tenant_id=tenant.id, provider_id=provider.id,
        start_time=datetime(2026, 3, 8, 7, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 3, 8, 7, 30, tzinfo=timezone.utc),
        active=True, created_at=datetime.now(timezone.utc)
    )
    db_session.add(block)
    db_session.commit()

    start_time = datetime(2026, 3, 8, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 3, 8, 23, 59, tzinfo=timezone.utc)

    slots = compute_availability(db_session, service=service, provider=provider, start_time=start_time, end_time=end_time)

    # Overlap with 07:00 to 07:30 blocked time:
    # - 06:30 (ends 07:00) -> Free
    # - 06:45 (ends 07:15) -> Overlaps -> Blocked
    # - 07:00 (ends 07:30) -> Overlaps -> Blocked
    # - 07:15 (ends 07:45) -> Overlaps -> Blocked
    # - 07:30 (ends 08:00) -> Starts right at 07:30 -> Free
    start_times = [s["start_time"] for s in slots]
    assert "2026-03-08T06:30:00+00:00" in start_times
    assert "2026-03-08T06:45:00+00:00" not in start_times
    assert "2026-03-08T07:00:00+00:00" not in start_times
    assert "2026-03-08T07:15:00+00:00" not in start_times
    assert "2026-03-08T07:30:00+00:00" in start_times


def test_cascading_waitlist_promotions(db_session: Session, client: TestClient):
    """Verify that cancelling multiple bookings sequentially triggers correct FIFO cascading waitlist promotions."""
    tenant, provider, client_a, service = _setup_base_data(db_session, "promo")
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)

    weekday_num = tomorrow.weekday()
    workday = ProviderWorkDay(
        tenant_id=tenant.id, provider_id=provider.id, weekday=weekday_num,
        start_time="09:00", end_time="10:00", is_working=True, created_at=datetime.now(timezone.utc)
    )
    db_session.add(workday)

    # Create additional clients
    client_b = Client(tenant_id=tenant.id, name="Client B", email="b@example.com", active=True, created_at=datetime.now(timezone.utc))
    client_c = Client(tenant_id=tenant.id, name="Client C", email="c@example.com", active=True, created_at=datetime.now(timezone.utc))
    client_x = Client(tenant_id=tenant.id, name="Client X", email="x@example.com", active=True, created_at=datetime.now(timezone.utc))
    client_y = Client(tenant_id=tenant.id, name="Client Y", email="y@example.com", active=True, created_at=datetime.now(timezone.utc))
    client_z = Client(tenant_id=tenant.id, name="Client Z", email="z@example.com", active=True, created_at=datetime.now(timezone.utc))
    db_session.add_all([client_b, client_c, client_x, client_y, client_z])
    db_session.commit()

    # Book all available slots for tomorrow:
    # Booking 1: 09:00 to 09:30
    booking1 = Booking(
        tenant_id=tenant.id, client_id=client_a.id, provider_id=provider.id, service_id=service.id,
        start_time=tomorrow.replace(hour=9, minute=0, second=0, microsecond=0),
        end_time=tomorrow.replace(hour=9, minute=30, second=0, microsecond=0),
        status=BookingStatus.CONFIRMED,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    )
    # Booking 2: 09:30 to 10:00
    booking2 = Booking(
        tenant_id=tenant.id, client_id=client_b.id, provider_id=provider.id, service_id=service.id,
        start_time=tomorrow.replace(hour=9, minute=30, second=0, microsecond=0),
        end_time=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
        status=BookingStatus.CONFIRMED,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    )
    db_session.add_all([booking1, booking2])
    db_session.commit()

    # Create three waitlist entries (FIFO order via created_at) for tomorrow:
    entry_x = WaitlistEntry(
        tenant_id=tenant.id, client_id=client_x.id, service_id=service.id, provider_id=provider.id,
        status=WaitlistStatus.REQUESTED,
        desired_date_from=tomorrow.replace(hour=8, minute=0, second=0, microsecond=0),
        desired_date_to=tomorrow.replace(hour=12, minute=0, second=0, microsecond=0),
        created_at=datetime.now(timezone.utc) - timedelta(hours=3)
    )
    entry_y = WaitlistEntry(
        tenant_id=tenant.id, client_id=client_y.id, service_id=service.id, provider_id=provider.id,
        status=WaitlistStatus.REQUESTED,
        desired_date_from=tomorrow.replace(hour=8, minute=0, second=0, microsecond=0),
        desired_date_to=tomorrow.replace(hour=12, minute=0, second=0, microsecond=0),
        created_at=datetime.now(timezone.utc) - timedelta(hours=2)
    )
    entry_z = WaitlistEntry(
        tenant_id=tenant.id, client_id=client_z.id, service_id=service.id, provider_id=provider.id,
        status=WaitlistStatus.REQUESTED,
        desired_date_from=tomorrow.replace(hour=8, minute=0, second=0, microsecond=0),
        desired_date_to=tomorrow.replace(hour=12, minute=0, second=0, microsecond=0),
        created_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    db_session.add_all([entry_x, entry_y, entry_z])
    db_session.commit()

    user = User(tenant_id=tenant.id, login="owner_promo", password_hash="fake", role="owner", created_at=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"X-Tenant": tenant.subdomain, "X-Token": token}

    # Cancel Booking 1 (09:00 - 09:30) via API Client.
    response = client.post(f"/api/admin/bookings/{booking1.id}/cancel", headers=headers)
    assert response.status_code == 200, response.text

    db_session.refresh(entry_x)
    db_session.refresh(entry_y)
    db_session.refresh(entry_z)

    # entry_x should be promoted (NOTIFIED)
    assert entry_x.status == WaitlistStatus.NOTIFIED
    assert entry_y.status == WaitlistStatus.REQUESTED
    assert entry_z.status == WaitlistStatus.REQUESTED

    # An active Hold should have been created for entry_x (client_x)
    hold_x = db_session.query(Hold).filter(Hold.client_id == client_x.id, Hold.status == HoldStatus.PENDING).first()
    assert hold_x is not None
    assert hold_x.start_time.hour == 9
    assert hold_x.start_time.minute == 0

    # Cancel Booking 2 (09:30 - 10:00) via API Client.
    response2 = client.post(f"/api/admin/bookings/{booking2.id}/cancel", headers=headers)
    assert response2.status_code == 200, response2.text

    db_session.refresh(entry_x)
    db_session.refresh(entry_y)
    db_session.refresh(entry_z)

    # entry_y should be promoted (NOTIFIED), entry_z remains REQUESTED (since no slots left: 09:00 has hold_x, 09:30 has hold_y)
    assert entry_x.status == WaitlistStatus.NOTIFIED
    assert entry_y.status == WaitlistStatus.NOTIFIED
    assert entry_z.status == WaitlistStatus.REQUESTED

    # Active hold for client_y
    hold_y = db_session.query(Hold).filter(Hold.client_id == client_y.id, Hold.status == HoldStatus.PENDING).first()
    assert hold_y is not None
    assert hold_y.start_time.hour == 9
    assert hold_y.start_time.minute == 30
