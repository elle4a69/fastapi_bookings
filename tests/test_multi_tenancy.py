"""Tests for tenant isolation and routing boundary verification."""

from datetime import datetime, timezone
from fastapi import status
from app.models.tenant import Tenant
from app.models.user import User
from app.models.service import Service
from app.core.security import create_access_token

def test_tenant_separation_via_headers(client, db_session):
    """Verify that creating data under one tenant is completely invisible to another tenant."""
    # 1. Create two tenants
    tenant_a = Tenant(name="Tenant A", subdomain="tenant-a", created_at=datetime.now(timezone.utc))
    tenant_b = Tenant(name="Tenant B", subdomain="tenant-b", created_at=datetime.now(timezone.utc))
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    # 2. Create users/admins for each tenant
    p_hash = "fake_password_hash_value"
    user_a = User(tenant_id=tenant_a.id, login="owner_a", password_hash=p_hash, role="owner", created_at=datetime.now(timezone.utc))
    user_b = User(tenant_id=tenant_b.id, login="owner_b", password_hash=p_hash, role="owner", created_at=datetime.now(timezone.utc))
    db_session.add_all([user_a, user_b])
    db_session.commit()

    # Generate JWT tokens
    token_a = create_access_token({"sub": str(user_a.id)})
    token_b = create_access_token({"sub": str(user_b.id)})

    # 3. Create service in Tenant A via client
    # POST /api/admin/services
    service_payload = {
        "name": "Service A",
        "description": "Tenant A service",
        "duration": 45,
        "price": 100.0,
        "active": True,
        "buffer_before": 0,
        "buffer_after": 0,
        "fixed_start_times": None
    }
    
    headers_a = {
        "X-Tenant": "tenant-a",
        "X-Token": token_a
    }
    
    response = client.post("/api/admin/services", json=service_payload, headers=headers_a)
    assert response.status_code == status.HTTP_200_OK, response.text
    created_service_id = response.json()["data"]["id"]

    # 4. Check listing services for Tenant A (using header)
    resp_list_a = client.get("/api/admin/services", headers={"X-Tenant": "tenant-a"})
    assert resp_list_a.status_code == status.HTTP_200_OK
    services_a = resp_list_a.json()["data"]
    assert len(services_a) == 1
    assert services_a[0]["name"] == "Service A"

    # 5. Check listing services for Tenant B (using query param instead of header)
    resp_list_b = client.get("/api/admin/services?tenant=tenant-b")
    assert resp_list_b.status_code == status.HTTP_200_OK
    services_b = resp_list_b.json()["data"]
    assert len(services_b) == 0

    # 6. Check isolation: Tenant B trying to access Tenant A's service ID directly (should 404)
    resp_direct_b = client.get(f"/api/admin/services/{created_service_id}", headers={"X-Tenant": "tenant-b"})
    assert resp_direct_b.status_code == status.HTTP_404_NOT_FOUND


def test_cross_tenant_token_rejection(client, db_session):
    """Verify that requests with mismatched tenant header and user token are blocked."""
    # 1. Create two tenants
    tenant_a = Tenant(name="Tenant A", subdomain="tenant-a", created_at=datetime.now(timezone.utc))
    tenant_b = Tenant(name="Tenant B", subdomain="tenant-b", created_at=datetime.now(timezone.utc))
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    # 2. Create owner user for tenant A
    user_a = User(
        tenant_id=tenant_a.id,
        login="owner_a",
        password_hash="fake_password_hash_value",
        role="owner",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(user_a)
    db_session.commit()

    token_a = create_access_token({"sub": str(user_a.id)})

    # Try to execute admin operation under Tenant B using Tenant A's token
    service_payload = {
        "name": "Service B",
        "description": "Service attempted in B",
        "duration": 30,
        "price": 50.0,
        "active": True
    }
    
    # We pass Tenant B in X-Tenant, but User A's token in X-Token
    headers_mismatched = {
        "X-Tenant": "tenant-b",
        "X-Token": token_a
    }
    
    response = client.post("/api/admin/services", json=service_payload, headers=headers_mismatched)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "User not found in this tenant" in response.json()["detail"]


def test_missing_or_invalid_tenant(client):
    """Verify endpoint behavior with missing or non-existent tenant subdomain context."""
    # 1. Missing tenant context entirely
    response_missing = client.get("/api/admin/services")
    assert response_missing.status_code == status.HTTP_400_BAD_REQUEST
    assert "Tenant subdomain is missing" in response_missing.json()["detail"]

    # 2. Non-existent tenant slug
    response_invalid = client.get("/api/admin/services", headers={"X-Tenant": "non-existent"})
    assert response_invalid.status_code == status.HTTP_404_NOT_FOUND
    assert "Tenant 'non-existent' not found" in response_invalid.json()["detail"]


def test_admin_booking_scoping(client, db_session):
    """Verify that admin of Tenant A cannot view or modify Tenant B's bookings."""
    # 1. Create two tenants
    tenant_a = Tenant(name="Tenant A", subdomain="tenant-a", created_at=datetime.now(timezone.utc))
    tenant_b = Tenant(name="Tenant B", subdomain="tenant-b", created_at=datetime.now(timezone.utc))
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    # 2. Create admin users
    p_hash = "fake_password_hash_value"
    user_a = User(tenant_id=tenant_a.id, login="owner_a", password_hash=p_hash, role="owner", created_at=datetime.now(timezone.utc))
    user_b = User(tenant_id=tenant_b.id, login="owner_b", password_hash=p_hash, role="owner", created_at=datetime.now(timezone.utc))
    db_session.add_all([user_a, user_b])
    db_session.commit()

    # Generate JWT tokens
    token_a = create_access_token({"sub": str(user_a.id)})
    token_b = create_access_token({"sub": str(user_b.id)})

    # Create Service, Provider and Booking in Tenant A
    service_a = Service(tenant_id=tenant_a.id, name="Consult", price=50.0, duration=30)
    db_session.add(service_a)
    db_session.commit()

    from app.models.provider import Provider as ProviderModel
    provider_a = ProviderModel(tenant_id=tenant_a.id, name="Provider A", email="providera@example.com")
    db_session.add(provider_a)
    db_session.commit()

    from app.models.booking import Booking as BookingModel
    from app.models.client import Client as ClientModel
    client_a = ClientModel(tenant_id=tenant_a.id, name="Client A", email="clienta@example.com")
    db_session.add(client_a)
    db_session.commit()

    booking_a = BookingModel(
        tenant_id=tenant_a.id,
        client_id=client_a.id,
        provider_id=provider_a.id,
        service_id=service_a.id,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        status="pending"
    )
    db_session.add(booking_a)
    db_session.commit()

    # Admin B tries to list bookings - should not see booking A
    headers_b = {"X-Tenant": "tenant-b", "X-Token": token_b}
    response_list = client.get("/api/admin/bookings", headers=headers_b)
    assert response_list.status_code == status.HTTP_200_OK
    assert len(response_list.json()["data"]) == 0

    # Admin B tries to retrieve booking A directly - should 404
    response_get = client.get(f"/api/admin/bookings/{booking_a.id}", headers=headers_b)
    assert response_get.status_code == status.HTTP_404_NOT_FOUND


def test_client_portal_registration_and_login_scoping(client, db_session):
    """Verify that client registrations/logins are scoped strictly by tenant."""
    # 1. Create two tenants
    tenant_a = Tenant(name="Tenant A", subdomain="tenant-a", created_at=datetime.now(timezone.utc))
    tenant_b = Tenant(name="Tenant B", subdomain="tenant-b", created_at=datetime.now(timezone.utc))
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    # 2. Register a client on Tenant A
    register_payload = {
        "email": "client@example.com",
        "password": "password123",
        "name": "Jane Client",
        "phone": "555-5555",
        "accept_terms": True,
        "accept_privacy": True
    }
    headers_a = {"X-Tenant": "tenant-a"}
    response = client.post("/api/public/clients/register", json=register_payload, headers=headers_a)
    assert response.status_code == status.HTTP_200_OK

    # 3. Try to login on Tenant B with the same email - should fail
    login_payload = {
        "email": "client@example.com",
        "password": "password123"
    }
    headers_b = {"X-Tenant": "tenant-b"}
    response_login = client.post("/api/public/clients/login", json=login_payload, headers=headers_b)
    assert response_login.status_code == status.HTTP_401_UNAUTHORIZED
