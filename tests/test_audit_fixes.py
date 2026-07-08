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
from app.models.hold import Hold, HoldStatus
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


def test_hold_timezone_and_serialization(client: TestClient, db_session: Session):
    """Verify hold timezone creation logic and correct serialization of BookingResponse on confirmation."""
    tenant = Tenant(name="Hold Biz", subdomain="hold-biz")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    service = Service(
        tenant_id=tenant.id,
        name="Hold Service",
        duration=30,
        price=Decimal("50.00"),
        active=True
    )
    provider = Provider(
        tenant_id=tenant.id,
        name="Hold Provider",
        active=True
    )
    db_session.add_all([service, provider])
    db_session.commit()

    # Timezone-aware timestamp for expires_at (expires in 15 minutes)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()

    payload = {
        "service_id": service.id,
        "provider_id": provider.id,
        "start_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "end_time": (datetime.now(timezone.utc) + timedelta(hours=1, minutes=30)).isoformat(),
        "expires_at": expires_at,
    }

    # Create hold
    token = create_access_token({"sub": "hold-biz"})
    headers = {"X-Tenant": "hold-biz", "X-Token": token}
    response = client.post("/api/public/holds", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    hold_data = response.json()
    assert hold_data["status"] == "pending"

    # Confirm hold (requires client info)
    client_obj = Client(tenant_id=tenant.id, name="Test Client", email="test@example.com")
    db_session.add(client_obj)
    db_session.commit()

    confirm_payload = {
        "hold_id": hold_data['id'],
        "client_details": {
            "name": "Test Client",
            "email": "test@example.com"
        }
    }
    confirm_response = client.post(
        f"/api/public/holds/{hold_data['id']}/confirm",
        json=confirm_payload,
        headers=headers
    )
    assert confirm_response.status_code == 200, confirm_response.text
    confirm_data = confirm_response.json()
    assert confirm_data["ok"] is True
    assert "data" in confirm_data
    assert confirm_data["data"]["status"] == "pending"


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
        active_holds=[],
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
        active_holds=[],
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
        active_holds=[],
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


def test_auto_promotion_on_cancellation(client: TestClient, db_session: Session):
    """Verify that cancelling a booking triggers promotion of the waitlist."""
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

    user = User(tenant_id=tenant.id, login="owner_promo", password_hash="fake", role="owner", created_at=datetime.now(timezone.utc))
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

    # After cancellation, waitlist entry should be enqueued and promoted to NOTIFIED status
    db_session.refresh(entry)
    assert entry.status == WaitlistStatus.NOTIFIED

    # Check that a hold was created for the waitlist promotion
    hold = db_session.query(Hold).filter(Hold.client_id == client_obj.id).first()
    assert hold is not None
    assert hold.status == HoldStatus.PENDING


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

