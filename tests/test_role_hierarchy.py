"""Tests for 3-Tier Internal Role Hierarchy & Provider Self-Service.

Verifies:
1. Owner has full administrative and commercial access (modules, business settings, user creation, processor config).
2. Manager has operational management capabilities (bookings, services) but is strictly forbidden from
   module toggles, business profile changes, billing/processor settings, and creating owner accounts.
3. Provider is restricted to self-service:
   - Calendar / bookings queries are automatically scoped strictly to the linked provider_id.
   - Provider cannot view or modify another provider's bookings.
   - Provider can access and update their own working hours and schedule.
   - Provider cannot access global business profile, billing, or module toggles.
"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi import status

from app.models.tenant import Tenant
from app.models.user import User
from app.models.provider import Provider
from app.models.service import Service
from app.models.client import Client
from app.models.booking import Booking
from app.models.schedule import ProviderWorkDay
from app.core.security import create_access_token
from app.core.state_machine import BookingStatus


@pytest.fixture
def hierarchy_setup(db_session):
    """Set up a tenant with Owner, Manager, Provider 1, and Provider 2 accounts."""
    tenant = Tenant(
        name="Hierarchy Test Health",
        subdomain="hierarchy-clinic",
        subscription_tier="growth",
        addon_quota=3,
        enabled_modules=["providers", "bookings", "calendar"],
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    # 1. Owner User
    owner = User(
        tenant_id=tenant.id,
        login="clinic_owner",
        password_hash="fake_hash",
        role="owner",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(owner)

    # 2. Manager User
    manager = User(
        tenant_id=tenant.id,
        login="clinic_manager",
        password_hash="fake_hash",
        role="manager",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(manager)

    # 3. Provider 1 and User
    prov1 = Provider(
        tenant_id=tenant.id,
        name="Dr. Provider 1",
        email="provider1@test.com",
        phone="+15550000001",
        active=True,
    )
    db_session.add(prov1)
    db_session.commit()
    db_session.refresh(prov1)

    user_prov1 = User(
        tenant_id=tenant.id,
        login="provider_1",
        password_hash="fake_hash",
        role="provider",
        provider_id=prov1.id,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user_prov1)

    # 4. Provider 2 and User
    prov2 = Provider(
        tenant_id=tenant.id,
        name="Dr. Provider 2",
        email="provider2@test.com",
        phone="+15550000002",
        active=True,
    )
    db_session.add(prov2)
    db_session.commit()
    db_session.refresh(prov2)

    user_prov2 = User(
        tenant_id=tenant.id,
        login="provider_2",
        password_hash="fake_hash",
        role="provider",
        provider_id=prov2.id,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user_prov2)

    # 5. Service & Client
    service = Service(
        tenant_id=tenant.id,
        name="Standard Consultation",
        duration=60,
        price=120.0,
        active=True,
    )
    db_session.add(service)

    client = Client(
        tenant_id=tenant.id,
        name="Client Test 1",
        phone="+15551234567",
        email="client1@test.com",
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(service)
    db_session.refresh(client)

    # 6. Bookings for each provider
    now = datetime.now(timezone.utc)
    booking1 = Booking(
        tenant_id=tenant.id,
        provider_id=prov1.id,
        service_id=service.id,
        client_id=client.id,
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=3),
        status=BookingStatus.CONFIRMED,
    )
    booking2 = Booking(
        tenant_id=tenant.id,
        provider_id=prov2.id,
        service_id=service.id,
        client_id=client.id,
        start_time=now + timedelta(hours=4),
        end_time=now + timedelta(hours=5),
        status=BookingStatus.CONFIRMED,
    )
    db_session.add(booking1)
    db_session.add(booking2)

    # 7. Workday for Provider 1
    workday1 = ProviderWorkDay(
        tenant_id=tenant.id,
        provider_id=prov1.id,
        weekday=0,
        start_time="09:00",
        end_time="17:00",
        is_working=True,
    )
    db_session.add(workday1)

    db_session.commit()
    db_session.refresh(owner)
    db_session.refresh(manager)
    db_session.refresh(user_prov1)
    db_session.refresh(user_prov2)
    db_session.refresh(booking1)
    db_session.refresh(booking2)

    def auth_headers(user):
        token = create_access_token({"sub": str(user.id), "role": user.role, "provider_id": user.provider_id})
        return {"X-Tenant": tenant.subdomain, "X-Token": token}

    return {
        "tenant": tenant,
        "owner": owner,
        "manager": manager,
        "user_prov1": user_prov1,
        "user_prov2": user_prov2,
        "prov1": prov1,
        "prov2": prov2,
        "service": service,
        "client": client,
        "booking1": booking1,
        "booking2": booking2,
        "owner_headers": auth_headers(owner),
        "manager_headers": auth_headers(manager),
        "prov1_headers": auth_headers(user_prov1),
        "prov2_headers": auth_headers(user_prov2),
    }


def test_owner_full_access(client, hierarchy_setup):
    """Owner has full access to all endpoints."""
    headers = hierarchy_setup["owner_headers"]

    # 1. Can toggle modules
    res = client.post(
        "/api/admin/tenant/modules/toggle",
        json={"module_key": "sms_assistant", "enabled": True},
        headers=headers,
    )
    assert res.status_code == status.HTTP_200_OK

    # 2. Can update business profile
    res = client.put(
        "/api/admin/business-profile",
        json={"name": "Owner Updated Clinic"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["data"]["name"] == "Owner Updated Clinic"

    # 3. Can see all bookings
    res = client.get("/api/admin/bookings", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()["data"]
    assert len(data) >= 2

    # 4. Can create payment processor config
    res = client.post(
        "/api/admin/payment-processor/configs",
        json={"provider": "stripe", "enabled": True},
        headers=headers,
    )
    assert res.status_code == status.HTTP_201_CREATED

    # 5. Can create a new manager user
    res = client.post(
        "/api/admin/users",
        json={
            "company": hierarchy_setup["tenant"].subdomain,
            "login": "new_manager",
            "password": "password123",
            "role": "manager",
        },
        headers=headers,
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["data"]["role"] == "manager"


def test_manager_permissions_and_boundaries(client, hierarchy_setup):
    """Manager can manage bookings/services but is forbidden from module toggles and billing."""
    headers = hierarchy_setup["manager_headers"]

    # 1. Manager CAN list all bookings
    res = client.get("/api/admin/bookings", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()["data"]) >= 2

    # 2. Manager CAN create services
    res = client.post(
        "/api/admin/services",
        json={"name": "Manager Added Service", "duration": 45, "price": 80.0},
        headers=headers,
    )
    assert res.status_code == status.HTTP_200_OK

    # 3. Manager is FORBIDDEN from toggling modules (403 Forbidden)
    res = client.post(
        "/api/admin/tenant/modules/toggle",
        json={"module_key": "sms_assistant", "enabled": True},
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 4. Manager is FORBIDDEN from updating tenant subscription tier (403 Forbidden)
    res = client.put(
        "/api/admin/tenant/modules/tier",
        json={"tier": "unlimited"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 5. Manager is FORBIDDEN from updating global business profile (403 Forbidden)
    res = client.put(
        "/api/admin/business-profile",
        json={"name": "Manager Attempted Change"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 6. Manager is FORBIDDEN from creating owner accounts (403 Forbidden)
    res = client.post(
        "/api/admin/users",
        json={
            "company": hierarchy_setup["tenant"].subdomain,
            "login": "rogue_owner",
            "password": "password123",
            "role": "owner",
        },
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 7. Manager is FORBIDDEN from creating payment processor configs (403 Forbidden)
    res = client.post(
        "/api/admin/payment-processor/configs",
        json={"provider": "paypal", "enabled": True},
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_provider_scoped_bookings_and_isolation(client, hierarchy_setup):
    """Provider can only view their own bookings and cannot view another provider's bookings."""
    headers1 = hierarchy_setup["prov1_headers"]
    headers2 = hierarchy_setup["prov2_headers"]
    b1_id = hierarchy_setup["booking1"].id
    b2_id = hierarchy_setup["booking2"].id

    # 1. Provider 1 listing bookings only sees their own booking
    res = client.get("/api/admin/bookings", headers=headers1)
    assert res.status_code == status.HTTP_200_OK
    booking_ids = [b["id"] for b in res.json()["data"]]
    assert b1_id in booking_ids
    assert b2_id not in booking_ids

    # 2. If Provider 1 passes ?provider_id=Provider 2, query is STILL scoped strictly to Provider 1
    res = client.get(f"/api/admin/bookings?provider_id={hierarchy_setup['prov2'].id}", headers=headers1)
    assert res.status_code == status.HTTP_200_OK
    booking_ids = [b["id"] for b in res.json()["data"]]
    assert b2_id not in booking_ids

    # 3. Provider 1 can get their own booking by ID
    res = client.get(f"/api/admin/bookings/{b1_id}", headers=headers1)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["data"]["id"] == b1_id

    # 4. Provider 1 CANNOT view Provider 2's booking (returns 404)
    res = client.get(f"/api/admin/bookings/{b2_id}", headers=headers1)
    assert res.status_code == status.HTTP_404_NOT_FOUND

    # 5. Provider 1 CANNOT modify Provider 2's booking
    res = client.put(f"/api/admin/bookings/{b2_id}", json={"notes": "Hacked"}, headers=headers1)
    assert res.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}

    # 6. Provider 1 can mark their own booking in progress and completed
    res = client.post(f"/api/admin/bookings/{b1_id}/start", headers=headers1)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["data"]["status"] == BookingStatus.IN_PROGRESS.value

    res = client.post(f"/api/admin/bookings/{b1_id}/complete", headers=headers1)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["data"]["status"] == BookingStatus.COMPLETED.value


def test_provider_self_service_portal(client, hierarchy_setup):
    """Provider can view their profile, bookings, and view/update their schedule."""
    headers = hierarchy_setup["prov1_headers"]

    # 1. GET /api/admin/provider/me
    res = client.get("/api/admin/provider/me", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    body = res.json()["data"]
    assert body["provider"]["name"] == "Dr. Provider 1"
    assert "upcoming_stats" in body

    # 2. GET /api/admin/provider/me/bookings
    res = client.get("/api/admin/provider/me/bookings", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    bookings = res.json()["data"]
    assert any(b["id"] == hierarchy_setup["booking1"].id for b in bookings)
    assert all(b["id"] != hierarchy_setup["booking2"].id for b in bookings)

    # 3. GET /api/admin/provider/me/schedule
    res = client.get("/api/admin/provider/me/schedule", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    schedule = res.json()["data"]
    assert "workdays" in schedule

    # 4. PUT /api/admin/provider/me/schedule (update hours)
    update_payload = {
        "weekly_schedule": {
            "monday": {"is_working": True, "start_time": "08:30", "end_time": "16:30", "recurring": True},
            "tuesday": {"is_working": True, "start_time": "08:30", "end_time": "16:30", "recurring": True},
        },
        "workdays": [
            {"weekday": 0, "start_time": "08:30", "end_time": "16:30", "is_working": True},
        ],
    }
    res = client.put("/api/admin/provider/me/schedule", json=update_payload, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["ok"] is True


def test_provider_forbidden_from_admin_endpoints(client, hierarchy_setup):
    """Provider cannot access module toggles, business settings, or user management."""
    headers = hierarchy_setup["prov1_headers"]

    # 1. Module toggles -> 403
    res = client.post(
        "/api/admin/tenant/modules/toggle",
        json={"module_key": "locations", "enabled": True},
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 2. Business profile update -> 403
    res = client.put(
        "/api/admin/business-profile",
        json={"name": "Attempted By Provider"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 3. User creation -> 403
    res = client.post(
        "/api/admin/users",
        json={
            "company": hierarchy_setup["tenant"].subdomain,
            "login": "provider_created_user",
            "password": "password123",
            "role": "provider",
        },
        headers=headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
