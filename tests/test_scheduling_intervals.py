"""Tests for scheduling intervals, overrides, and availability wrappers."""

from datetime import datetime, timezone, date, time
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.service import Service
from app.models.client import Client
from app.models.schedule import ProviderWorkDay, ProviderSpecialDay

from app.services.scheduling_service import compute_availability
from app.services.availability_service import get_available_slots


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


def test_weekly_workday_intervals(db_session):
    """Verify that weekly workday rules correctly determine available slots."""
    tenant, provider, client, service = _setup_base_data(db_session)

    # Monday weekday=0. Set work day from 09:00 to 11:00 (allowing slots: 09:00, 09:15, 09:30, 09:45, 10:00, 10:15, 10:30)
    workday = ProviderWorkDay(
        tenant_id=tenant.id,
        provider_id=provider.id,
        weekday=0,
        start_time="09:00",
        end_time="11:00",
        is_working=True,
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(workday)
    db_session.commit()

    # Query for Monday, July 6, 2026 (weekday=0)
    start_time = datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 7, 6, 23, 59, tzinfo=timezone.utc)

    slots = compute_availability(
        db_session,
        service=service,
        provider=provider,
        start_time=start_time,
        end_time=end_time
    )

    # Expected slots:
    # 09:00-09:30, 09:15-09:45, 09:30-10:00, 09:45-10:15, 10:00-10:30, 10:15-10:45, 10:30-11:00
    assert len(slots) == 7
    assert slots[0]["start_time"] == "2026-07-06T09:00:00+00:00"
    assert slots[-1]["start_time"] == "2026-07-06T10:30:00+00:00"


def test_special_day_holiday_overrides(db_session):
    """Verify that provider-specific and company-wide special days override weekly schedules."""
    tenant, provider, client, service = _setup_base_data(db_session)

    # 1. Setup default Monday workday
    workday = ProviderWorkDay(
        tenant_id=tenant.id, provider_id=provider.id, weekday=0,
        start_time="09:00", end_time="11:00", is_working=True, created_at=datetime.now(timezone.utc)
    )
    db_session.add(workday)

    # 2. Add company-wide holiday on July 6 (provider_id is None, is_working=False)
    holiday = ProviderSpecialDay(
        tenant_id=tenant.id, provider_id=None, date=date(2026, 7, 6),
        is_working=False, reason="National Day", created_at=datetime.now(timezone.utc)
    )
    db_session.add(holiday)
    db_session.commit()

    start_time = datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 7, 6, 23, 59, tzinfo=timezone.utc)

    # Company closed -> should have 0 slots
    slots = compute_availability(db_session, service=service, provider=provider, start_time=start_time, end_time=end_time)
    assert len(slots) == 0

    # Remove company holiday, add provider-specific holiday instead
    db_session.delete(holiday)
    prov_holiday = ProviderSpecialDay(
        tenant_id=tenant.id, provider_id=provider.id, date=date(2026, 7, 6),
        is_working=False, reason="Sick Leave", created_at=datetime.now(timezone.utc)
    )
    db_session.add(prov_holiday)
    db_session.commit()

    slots = compute_availability(db_session, service=service, provider=provider, start_time=start_time, end_time=end_time)
    assert len(slots) == 0


def test_fixed_start_times(db_session):
    """Verify that fixed start times on service are strictly scanned."""
    tenant, provider, client, service = _setup_base_data(db_session)

    service.fixed_start_times = "09:00,10:30"
    service.duration = 60  # 1 hour
    db_session.commit()

    # Monday workday 09:00 - 12:00
    workday = ProviderWorkDay(
        tenant_id=tenant.id, provider_id=provider.id, weekday=0,
        start_time="09:00", end_time="12:00", is_working=True, created_at=datetime.now(timezone.utc)
    )
    db_session.add(workday)
    db_session.commit()

    start_time = datetime(2026, 7, 6, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 7, 6, 23, 59, tzinfo=timezone.utc)

    slots = compute_availability(db_session, service=service, provider=provider, start_time=start_time, end_time=end_time)

    # Only 09:00 (ends 10:00) and 10:30 (ends 11:30) should be available.
    # Standard sliding 15-min intervals are completely bypassed.
    assert len(slots) == 2
    start_times = [s["start_time"] for s in slots]
    assert "2026-07-06T09:00:00+00:00" in start_times
    assert "2026-07-06T10:30:00+00:00" in start_times


def test_availability_service_wrapper(db_session):
    """Verify that get_available_slots wrapper functions correctly."""
    tenant, provider, client, service = _setup_base_data(db_session)

    # Monday workday 09:00 - 10:00
    workday = ProviderWorkDay(
        tenant_id=tenant.id, provider_id=provider.id, weekday=0,
        start_time="09:00", end_time="10:00", is_working=True, created_at=datetime.now(timezone.utc)
    )
    db_session.add(workday)
    db_session.commit()

    target_date = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)

    slots = get_available_slots(
        db_session,
        service_duration=30,
        provider_id=provider.id,
        date=target_date
    )

    # Expect: 09:00-09:30, 09:15-09:45, 09:30-10:00 (3 slots)
    assert len(slots) == 3
    assert slots[0]["start"].isoformat() == "2026-07-06T09:00:00+00:00"
    assert slots[-1]["start"].isoformat() == "2026-07-06T09:30:00+00:00"
