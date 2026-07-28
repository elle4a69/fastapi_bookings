import pytest
from datetime import datetime, timedelta, timezone
from fastapi import status

from app.models.tenant import Tenant
from app.models.service import Service
from app.models.provider import Provider
from app.models.schedule import ProviderWorkDay
from app.services.scheduling_service import compute_availability

@pytest.fixture
def test_data(db_session):
    # Create tenant
    tenant = Tenant(name="Tenant Schedule", subdomain="tenant-sched", max_advance_days=30)
    db_session.add(tenant)
    db_session.commit()

    # Create service
    service = Service(tenant_id=tenant.id, name="Consult", duration=30, active=True)
    db_session.add(service)
    db_session.commit()

    # Providers: prov_standard (follows company hours), prov_ignore (ignores company hours)
    prov_standard = Provider(tenant_id=tenant.id, name="Prov Standard", active=True, ignore_company_hours=False)
    prov_ignore = Provider(tenant_id=tenant.id, name="Prov Ignore", active=True, ignore_company_hours=True)
    db_session.add_all([prov_standard, prov_ignore])
    db_session.commit()

    return {
        "tenant": tenant,
        "service": service,
        "prov_standard": prov_standard,
        "prov_ignore": prov_ignore
    }

def test_ignore_company_hours(db_session, test_data):
    # Set Monday (weekday=0) as company-wide workday
    company_workday = ProviderWorkDay(
        tenant_id=test_data["tenant"].id,
        provider_id=None,
        weekday=0, # Monday
        start_time="09:00",
        end_time="17:00",
        is_working=True
    )
    # Set Tuesday (weekday=1) as prov_ignore specific workday
    ignore_workday = ProviderWorkDay(
        tenant_id=test_data["tenant"].id,
        provider_id=test_data["prov_ignore"].id,
        weekday=1, # Tuesday
        start_time="09:00",
        end_time="17:00",
        is_working=True
    )
    db_session.add_all([company_workday, ignore_workday])
    db_session.commit()

    # Query availability for Monday
    # Find next Monday
    today = datetime.now(timezone.utc).date()
    monday = today + timedelta(days=(0 - today.weekday()) % 7)
    # If next Monday is today, push to next week
    if monday == today:
        monday += timedelta(days=7)
    
    start_monday = datetime.combine(monday, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_monday = start_monday + timedelta(hours=23)

    # 1. Standard provider should have availability on Monday (from company hours)
    slots_standard = compute_availability(
        db_session,
        service=test_data["service"],
        provider=test_data["prov_standard"],
        start_time=start_monday,
        end_time=end_monday
    )
    assert len(slots_standard) > 0

    # 2. Ignore provider should NOT have availability on Monday (ignored company hours, has no specific Monday hours)
    slots_ignore_monday = compute_availability(
        db_session,
        service=test_data["service"],
        provider=test_data["prov_ignore"],
        start_time=start_monday,
        end_time=end_monday
    )
    assert len(slots_ignore_monday) == 0

    # 3. Ignore provider should have availability on Tuesday
    tuesday = monday + timedelta(days=1)
    start_tuesday = datetime.combine(tuesday, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_tuesday = start_tuesday + timedelta(hours=23)

    slots_ignore_tuesday = compute_availability(
        db_session,
        service=test_data["service"],
        provider=test_data["prov_ignore"],
        start_time=start_tuesday,
        end_time=end_tuesday
    )
    assert len(slots_ignore_tuesday) > 0

def test_max_advance_days_capping(db_session, test_data):
    # Set Wednesday as daily workday for prov_standard
    company_workday = ProviderWorkDay(
        tenant_id=test_data["tenant"].id,
        provider_id=test_data["prov_standard"].id,
        weekday=2, # Wednesday
        start_time="09:00",
        end_time="17:00",
        is_working=True
    )
    db_session.add(company_workday)
    db_session.commit()

    # Query availability for a long range: next 45 days
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(days=45)

    # 1. Capped by Tenant max_advance_days (30 days)
    slots_tenant_cap = compute_availability(
        db_session,
        service=test_data["service"],
        provider=test_data["prov_standard"],
        start_time=start_time,
        end_time=end_time
    )
    max_days_allowed = start_time + timedelta(days=30)
    for slot in slots_tenant_cap:
        slot_start = datetime.fromisoformat(slot["start_time"])
        assert slot_start <= max_days_allowed

    # 2. Capped by Service-specific max_advance_days (e.g. 5 days)
    test_data["service"].max_advance_days = 5
    db_session.commit()

    slots_service_cap = compute_availability(
        db_session,
        service=test_data["service"],
        provider=test_data["prov_standard"],
        start_time=start_time,
        end_time=end_time
    )
    max_days_allowed_service = start_time + timedelta(days=5)
    for slot in slots_service_cap:
        slot_start = datetime.fromisoformat(slot["start_time"])
        assert slot_start <= max_days_allowed_service
