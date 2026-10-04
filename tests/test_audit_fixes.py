import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.tenant import Tenant
from app.models.user import User
from app.models.service import Service
from app.models.provider import Provider
from app.models.client import Client
from app.models.waitlist import WaitlistEntry, WaitlistStatus
from app.models.schedule import ProviderWorkDay
from app.core.security import create_access_token
from app.services.scheduling_utils import check_slot_overlaps

def test_decimal_format_validation(client: TestClient, db_session: Session):
    """Verify that price and deposit_amount are saved and returned as Decimals."""
    tenant = Tenant(name="Decimal Biz", subdomain="decimal-biz")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    user = User(
        tenant_id=tenant.id,
        login="owner_dec",
        password_hash="fake",
        role="owner",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"X-Tenant": "decimal-biz", "X-Token": token}

    # Create Service via API
    service_payload = {
        "name": "Decimal Service",
        "description": "High precision service",
        "duration": 60,
        "price": 100.50,
        "active": True,
        "deposit_amount": 25.75,
    }
    response = client.post("/api/admin/services", json=service_payload, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    # Check that price and deposit_amount are serialized correctly
    assert float(data["price"]) == 100.50
    assert float(data["deposit_amount"]) == 25.75

    # Check database object type
    db_service = db_session.query(Service).filter(Service.id == data["id"]).first()
    assert isinstance(db_service.price, Decimal)
    assert isinstance(db_service.deposit_amount, Decimal)


def test_public_booking_timezone_and_serialization(client: TestClient, db_session: Session):
    """Verify public booking creation logic and correct serialization of BookingResponse."""
    tenant = Tenant(name="Public Booking Biz", subdomain="pub-biz")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    service = Service(
        tenant_id=tenant.id,
        name="Consult Service",
        duration=30,
        price=Decimal("50.00"),
        active=True
    )
    provider = Provider(
        tenant_id=tenant.id,
        name="Doctor Public",
        active=True
    )
    db_session.add_all([service, provider])
    db_session.commit()

    start_time = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=30)

    payload = {
        "service_id": service.id,
        "provider_id": provider.id,
        "client_name": "Public Client",
        "client_email": "pubclient@example.com",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
    }

    token = create_access_token({"sub": "pub-biz"})
    headers = {"X-Tenant": "pub-biz", "X-Token": token}
    response = client.post("/api/public/bookings", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    booking_data = response.json()
    assert booking_data["ok"] is True
    assert "data" in booking_data
    assert booking_data["data"]["status"] == "pending"
    assert booking_data["data"]["service_id"] == service.id
    assert booking_data["data"]["provider_id"] == provider.id


def test_buffer_aware_overlap_checks(db_session: Session):
    """Verify that buffer-aware overlaps check slots correctly with prep and cleanup buffers."""
    class DummyService:
        def __init__(self, buffer_before, buffer_after):
            self.buffer_before = buffer_before
            self.buffer_after = buffer_after

    class DummyBooking:
        def __init__(self, start_time, end_time, service):
            self.start_time = start_time
            self.end_time = end_time
            self.service = service

    service_a = DummyService(buffer_before=15, buffer_after=15)
    booking_exist = DummyBooking(
        start_time=datetime(2026, 7, 9, 10, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc),
        service=service_a
    )

    # Candidate slot: 11:00 to 12:00.
    # The existing booking ends at 11:00, but has buffer_after = 15 mins (blocked until 11:15).
    # This slot starts at 11:00. Padded or unpadded, it should overlap with the existing booking's buffer.
    overlaps = check_slot_overlaps(
        slot_start=datetime(2026, 7, 9, 11, 0, tzinfo=timezone.utc),
        slot_end=datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc),
        active_bookings=[booking_exist],
        provider_blocked=[],
        active_reservations=[]
    )
    assert overlaps is True

    # Candidate slot: 11:15 to 12:15.
    # Existing booking ends at 11:00 + 15 mins buffer = 11:15.
    # New slot starts at 11:15, with new_buffer_before = 10 mins (padded range starts at 11:05).
    # Since padded range starts at 11:05, and existing booking's blocked range ends at 11:15, it should overlap!
    overlaps_new_buffer = check_slot_overlaps(
        slot_start=datetime(2026, 7, 9, 11, 15, tzinfo=timezone.utc),
        slot_end=datetime(2026, 7, 9, 12, 15, tzinfo=timezone.utc),
        active_bookings=[booking_exist],
        provider_blocked=[],
        active_reservations=[],
        new_buffer_before=10,
        new_buffer_after=10
    )
    assert overlaps_new_buffer is True

    # Candidate slot: 11:30 to 12:30.
    # Existing booking ends at 11:00 + 15 mins buffer = 11:15.
    # New slot starts at 11:30, with new_buffer_before=10 mins (padded range starts at 11:20).
    # 11:20 is after 11:15, so no overlap!
    no_overlaps = check_slot_overlaps(
        slot_start=datetime(2026, 7, 9, 11, 30, tzinfo=timezone.utc),
        slot_end=datetime(2026, 7, 9, 12, 30, tzinfo=timezone.utc),
        active_bookings=[booking_exist],
        provider_blocked=[],
        active_reservations=[],
        new_buffer_before=10,
        new_buffer_after=10
    )
    assert no_overlaps is False


def test_scoped_reset_and_schedule_endpoints(client: TestClient, db_session: Session):
    """Verify that password-reset and admin schedule endpoints are properly scoped and tenant-isolated."""
    tenant_a = Tenant(name="Tenant A", subdomain="tenant-a")
    tenant_b = Tenant(name="Tenant B", subdomain="tenant-b")
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    user_a = User(tenant_id=tenant_a.id, login="admin_a", password_hash="fake", role="admin", created_at=datetime.now(timezone.utc))
    user_b = User(tenant_id=tenant_b.id, login="admin_b", password_hash="fake", role="admin", created_at=datetime.now(timezone.utc))
    db_session.add_all([user_a, user_b])
    db_session.commit()

    token_a = create_access_token({"sub": str(user_a.id)})

    provider_a = Provider(tenant_id=tenant_a.id, name="Prov A", active=True)
    provider_b = Provider(tenant_id=tenant_b.id, name="Prov B", active=True)
    db_session.add_all([provider_a, provider_b])
    db_session.commit()

    # 1. Test password-reset request scoping
    client_a = Client(tenant_id=tenant_a.id, email="client@example.com", name="Client A")
    db_session.add(client_a)
    db_session.commit()

    reset_payload = {"email": "client@example.com", "password": "newpassword"}
    response = client.post(
        "/api/public/clients/password-reset/request",
        json=reset_payload,
        headers={"X-Tenant": "tenant-a"}
    )
    assert response.status_code == 200

    # 2. Test admin schedule tenant validation (cross-tenant creation should raise 403)
    workday_payload = {
        "provider_id": provider_b.id,  # Provider B belongs to tenant B
        "weekday": 1,
        "start_time": "09:00",
        "end_time": "17:00",
        "is_working": True
    }
    # Admin A trying to assign workday to Provider B (cross-tenant)
    response = client.post(
        "/api/admin/schedule/workdays",
        json=workday_payload,
        headers={"X-Tenant": "tenant-a", "X-Token": token_a}
    )
    assert response.status_code == 403

    # Admin A assigning workday to Provider A (same tenant)
    workday_payload["provider_id"] = provider_a.id
    response = client.post(
        "/api/admin/schedule/workdays",
        json=workday_payload,
        headers={"X-Tenant": "tenant-a", "X-Token": token_a}
    )
    assert response.status_code == 201


def test_passive_waitlist_on_cancellation(client: TestClient, db_session: Session):
    """Verify that cancelling a booking cancels cleanly without triggering unauthorized hold creation."""
    # Setup Tenant, Service, Provider, Location
    tenant = Tenant(name="Promo Biz", subdomain="promo-biz")
    db_session.add(tenant)
    db_session.commit()

    service = Service(tenant_id=tenant.id, name="Yoga", duration=60, price=Decimal("15.00"), active=True)
    provider = Provider(tenant_id=tenant.id, name="Yogi Bear", active=True)
    db_session.add_all([service, provider])
    db_session.commit()

    # Add workdays so scheduling search works
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    wd = ProviderWorkDay(tenant_id=tenant.id, provider_id=provider.id, weekday=tomorrow.weekday(), start_time="08:00", end_time="20:00", is_working=True)
    db_session.add(wd)
    db_session.commit()

    # Create client
    client_obj = Client(tenant_id=tenant.id, name="Waitlister", email="waitlist@example.com")
    db_session.add(client_obj)
    db_session.commit()

    # Create Waitlist Entry for this client
    entry = WaitlistEntry(
        tenant_id=tenant.id,
        client_id=client_obj.id,
        service_id=service.id,
        provider_id=provider.id,
        status=WaitlistStatus.REQUESTED,
        desired_date_from=tomorrow.replace(hour=8, minute=0, second=0, microsecond=0),
        desired_date_to=tomorrow.replace(hour=20, minute=0, second=0, microsecond=0),
        created_at=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    db_session.add(entry)
    db_session.commit()

    user = User(tenant_id=tenant.id, login="owner_promo", password_hash="fake", role="owner")
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"X-Tenant": "promo-biz", "X-Token": token}

    # Create booking that takes up the slot
    from app.models.booking import Booking as BookingModel
    from app.core.state_machine import BookingStatus

    booking = BookingModel(
        tenant_id=tenant.id,
        client_id=client_obj.id,
        provider_id=provider.id,
        service_id=service.id,
        start_time=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
        end_time=tomorrow.replace(hour=11, minute=0, second=0, microsecond=0),
        status=BookingStatus.PENDING
    )
    db_session.add(booking)
    db_session.commit()

    # Cancel booking via API
    response = client.post(f"/api/admin/bookings/{booking.id}/cancel", headers=headers)
    assert response.status_code == 200, response.text

    # After cancellation, booking is CANCELLED and waitlist entry remains safe passive record
    db_session.refresh(booking)
    assert booking.status == BookingStatus.CANCELLED
    db_session.refresh(entry)
    assert entry.status == WaitlistStatus.REQUESTED


def test_booking_reschedule_with_body_payload(client: TestClient, db_session: Session):
    """Verify rescheduling a booking via JSON body payload containing new_start and new_end."""
    tenant = Tenant(name="Reschedule Biz", subdomain="reschedule-biz")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    user = User(tenant_id=tenant.id, login="owner_resched", password_hash="fake", role="owner", created_at=datetime.now(timezone.utc))
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"X-Tenant": "reschedule-biz", "X-Token": token}

    client_obj = Client(tenant_id=tenant.id, name="Rescheduler Client", email="resched@example.com")
    service = Service(tenant_id=tenant.id, name="Coaching", duration=60, price=Decimal("50.00"), active=True)
    provider = Provider(tenant_id=tenant.id, name="Coach Carter", active=True)
    db_session.add_all([client_obj, service, provider])
    db_session.commit()

    # Add workday for provider
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    wd = ProviderWorkDay(tenant_id=tenant.id, provider_id=provider.id, weekday=tomorrow.weekday(), start_time="08:00", end_time="20:00", is_working=True)
    db_session.add(wd)
    db_session.commit()

    # Create active booking
    from app.models.booking import Booking as BookingModel
    from app.core.state_machine import BookingStatus

    booking = BookingModel(
        tenant_id=tenant.id,
        client_id=client_obj.id,
        provider_id=provider.id,
        service_id=service.id,
        start_time=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
        end_time=tomorrow.replace(hour=11, minute=0, second=0, microsecond=0),
        status=BookingStatus.CONFIRMED
    )
    db_session.add(booking)
    db_session.commit()

    # Reschedule payload
    resched_payload = {
        "new_start": tomorrow.replace(hour=14, minute=0, second=0, microsecond=0).isoformat(),
        "new_end": tomorrow.replace(hour=15, minute=0, second=0, microsecond=0).isoformat()
    }

    # Execute reschedule
    response = client.post(
        f"/api/admin/bookings/{booking.id}/reschedule",
        json=resched_payload,
        headers=headers
    )
    assert response.status_code == 200, response.text
    res = response.json()
    assert res["ok"] is True
    assert res["data"]["status"] == BookingStatus.RESCHEDULED.value
    assert "14:00" in res["data"]["start_time"]


def test_idor_notification_template_isolated_by_tenant(client: TestClient, db_session: Session):
    """Verify two tenants can each create notification template with identical code without collision."""
    t1 = Tenant(name="Tenant One", subdomain="t1-notif")
    t2 = Tenant(name="Tenant Two", subdomain="t2-notif")
    db_session.add_all([t1, t2])
    db_session.commit()
    db_session.refresh(t1)
    db_session.refresh(t2)

    u1 = User(tenant_id=t1.id, login="admin_t1", password_hash="fake", role="owner", created_at=datetime.now(timezone.utc))
    u2 = User(tenant_id=t2.id, login="admin_t2", password_hash="fake", role="owner", created_at=datetime.now(timezone.utc))
    db_session.add_all([u1, u2])
    db_session.commit()

    tok1 = create_access_token({"sub": str(u1.id)})
    tok2 = create_access_token({"sub": str(u2.id)})
    h1 = {"X-Tenant": "t1-notif", "X-Token": tok1}
    h2 = {"X-Tenant": "t2-notif", "X-Token": tok2}

    payload = {
        "code": "appointment_reminder",
        "name": "Appointment Reminder",
        "channel": "email",
        "subject": "Your reminder",
        "body": "Hello {{name}}",
        "locale": "en",
        "active": True,
    }

    r1 = client.post("/api/admin/notification-templates", json=payload, headers=h1)
    assert r1.status_code == 200, r1.text

    # Tenant 2 can create same code without 409
    r2 = client.post("/api/admin/notification-templates", json=payload, headers=h2)
    assert r2.status_code == 200, r2.text

    # Duplicate in same tenant gives 409
    r3 = client.post("/api/admin/notification-templates", json=payload, headers=h1)
    assert r3.status_code == 409


def test_idor_package_step_isolation(client: TestClient, db_session: Session):
    """Verify package step routes reject cross-tenant manipulation and cross-tenant services."""
    from app.models.package import ServicePackage, PackageStep

    t1 = Tenant(name="T1 Pkg", subdomain="t1-pkg")
    t2 = Tenant(name="T2 Pkg", subdomain="t2-pkg")
    db_session.add_all([t1, t2])
    db_session.commit()
    db_session.refresh(t1)
    db_session.refresh(t2)

    u1 = User(tenant_id=t1.id, login="admin_t1_p", password_hash="fake", role="owner", created_at=datetime.now(timezone.utc))
    u2 = User(tenant_id=t2.id, login="admin_t2_p", password_hash="fake", role="owner", created_at=datetime.now(timezone.utc))
    s1 = Service(tenant_id=t1.id, name="S1", duration=30, price=Decimal("10.00"), active=True)
    s2 = Service(tenant_id=t2.id, name="S2", duration=30, price=Decimal("20.00"), active=True)
    pkg1 = ServicePackage(tenant_id=t1.id, name="Pkg 1", price=Decimal("50.00"), active=True)
    pkg2 = ServicePackage(tenant_id=t2.id, name="Pkg 2", price=Decimal("60.00"), active=True)
    db_session.add_all([u1, u2, s1, s2, pkg1, pkg2])
    db_session.commit()

    step1 = PackageStep(package_id=pkg1.id, service_id=s1.id, order=1, offset_days=0, price=Decimal("10.00"), active=True)
    db_session.add(step1)
    db_session.commit()

    tok2 = create_access_token({"sub": str(u2.id)})
    h2 = {"X-Tenant": "t2-pkg", "X-Token": tok2}

    # Tenant 2 cannot update Tenant 1's step
    r = client.put(f"/api/admin/packages/steps/{step1.id}", json={"package_id": pkg2.id, "service_id": s2.id, "order": 2, "offset_days": 0, "active": True}, headers=h2)
    assert r.status_code == 404

    # Tenant 2 cannot delete Tenant 1's step
    r = client.delete(f"/api/admin/packages/steps/{step1.id}", headers=h2)
    assert r.status_code == 404

    # Tenant 2 cannot add Tenant 1's service to Tenant 2's package
    r = client.post(f"/api/admin/packages/{pkg2.id}/steps", json={"package_id": pkg2.id, "service_id": s1.id, "order": 1, "offset_days": 0, "active": True}, headers=h2)
    assert r.status_code == 404


def test_idor_service_resource_requirement_isolation(client: TestClient, db_session: Session):
    """Verify service resource requirement routes enforce tenant isolation."""
    from app.models.resource import ServiceResourceRequirement

    t1 = Tenant(name="T1 Res", subdomain="t1-res")
    t2 = Tenant(name="T2 Res", subdomain="t2-res")
    db_session.add_all([t1, t2])
    db_session.commit()
    db_session.refresh(t1)
    db_session.refresh(t2)

    u1 = User(tenant_id=t1.id, login="admin_t1_r", password_hash="fake", role="owner", created_at=datetime.now(timezone.utc))
    u2 = User(tenant_id=t2.id, login="admin_t2_r", password_hash="fake", role="owner", created_at=datetime.now(timezone.utc))
    s1 = Service(tenant_id=t1.id, name="S1", duration=30, price=Decimal("10.00"), active=True)
    db_session.add_all([u1, u2, s1])
    db_session.commit()

    req1 = ServiceResourceRequirement(service_id=s1.id, resource_type="room", quantity=1)
    db_session.add(req1)
    db_session.commit()

    tok2 = create_access_token({"sub": str(u2.id)})
    h2 = {"X-Tenant": "t2-res", "X-Token": tok2}

    # Tenant 2 cannot create requirement for Tenant 1's service
    r = client.post("/api/admin/resources/requirements", json={"service_id": s1.id, "resource_type": "chair", "quantity": 1}, headers=h2)
    assert r.status_code == 404

    # Tenant 2 cannot delete Tenant 1's requirement
    r = client.delete(f"/api/admin/resources/requirements/{req1.id}", headers=h2)
    assert r.status_code == 404


def test_idor_admin_diagnostics_tenant_scoped(client: TestClient, db_session: Session):
    """Verify admin diagnostics returns entity counts strictly for the requesting admin's tenant."""
    t1 = Tenant(name="T1 Diag", subdomain="t1-diag")
    t2 = Tenant(name="T2 Diag", subdomain="t2-diag")
    db_session.add_all([t1, t2])
    db_session.commit()
    db_session.refresh(t1)
    db_session.refresh(t2)

    u1 = User(tenant_id=t1.id, login="admin_t1_d", password_hash="fake", role="owner", created_at=datetime.now(timezone.utc))
    u2 = User(tenant_id=t2.id, login="admin_t2_d", password_hash="fake", role="owner", created_at=datetime.now(timezone.utc))
    
    # 3 services in t1, 1 service in t2
    for i in range(3):
        db_session.add(Service(tenant_id=t1.id, name=f"S1-{i}", duration=30, price=Decimal("10.00"), active=True))
    db_session.add(Service(tenant_id=t2.id, name="S2-0", duration=30, price=Decimal("10.00"), active=True))
    db_session.add_all([u1, u2])
    db_session.commit()

    tok1 = create_access_token({"sub": str(u1.id)})
    h1 = {"X-Tenant": "t1-diag", "X-Token": tok1}

    r1 = client.get("/api/admin/system/diagnostics", headers=h1)
    assert r1.status_code == 200
    counts1 = r1.json()["counts"]
    assert counts1["services"] == 3


