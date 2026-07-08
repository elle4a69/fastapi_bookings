"""Security and fuzzing tests for FastAPI Bookings.

Tests boundary conditions, input validation, SQL injection attempts,
past date parameters, extreme timezone offsets, malformed payloads,
and cross-tenant isolation enforcement.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from fastapi import status

from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.service import Service
from app.models.client import Client
from app.models.location import Location
from app.models.user import User
from app.core.security import create_access_token


@pytest.fixture
def base_security_data(db_session):
    """Fixture to set up isolation test context across two tenants (Tenant A and Tenant B)."""
    p_hash = "fake_password_hash_value"
    
    # 1. Create Tenants
    tenant_a = Tenant(name="Tenant A", subdomain="tenant-a", created_at=datetime.now(timezone.utc))
    tenant_b = Tenant(name="Tenant B", subdomain="tenant-b", created_at=datetime.now(timezone.utc))
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()
    
    # 2. Create Owner Users
    user_a = User(tenant_id=tenant_a.id, login="owner_a", password_hash=p_hash, role="owner", created_at=datetime.now(timezone.utc))
    user_b = User(tenant_id=tenant_b.id, login="owner_b", password_hash=p_hash, role="owner", created_at=datetime.now(timezone.utc))
    db_session.add_all([user_a, user_b])
    db_session.commit()
    
    # 3. Generate Auth Tokens
    token_a = create_access_token({"sub": str(user_a.id)})
    token_b = create_access_token({"sub": str(user_b.id)})
    
    # Public Client/Subdomain Tokens
    token_public_a = create_access_token({"sub": "tenant-a"})
    token_public_b = create_access_token({"sub": "tenant-b"})
    
    # 4. Create Providers
    provider_a = Provider(tenant_id=tenant_a.id, name="Provider A", active=True, created_at=datetime.now(timezone.utc))
    provider_b = Provider(tenant_id=tenant_b.id, name="Provider B", active=True, created_at=datetime.now(timezone.utc))
    db_session.add_all([provider_a, provider_b])
    db_session.commit()
    
    # 5. Create Services
    service_a = Service(
        tenant_id=tenant_a.id, name="Service A", duration=30, price=50.0, active=True,
        buffer_before=0, buffer_after=0, fixed_start_times=None
    )
    service_b = Service(
        tenant_id=tenant_b.id, name="Service B", duration=60, price=100.0, active=True,
        buffer_before=0, buffer_after=0, fixed_start_times=None
    )
    db_session.add_all([service_a, service_b])
    db_session.commit()
    
    # 6. Create Locations
    location_a = Location(tenant_id=tenant_a.id, name="Location A", address="123 Street A", timezone="UTC")
    location_b = Location(tenant_id=tenant_b.id, name="Location B", address="456 Street B", timezone="UTC")
    db_session.add_all([location_a, location_b])
    db_session.commit()
    
    # 7. Create Clients
    client_a = Client(tenant_id=tenant_a.id, name="Client A", email="clienta@example.com", active=True, created_at=datetime.now(timezone.utc))
    client_b = Client(tenant_id=tenant_b.id, name="Client B", email="clientb@example.com", active=True, created_at=datetime.now(timezone.utc))
    db_session.add_all([client_a, client_b])
    db_session.commit()
    
    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_a": user_a,
        "user_b": user_b,
        "token_a": token_a,
        "token_b": token_b,
        "token_public_a": token_public_a,
        "token_public_b": token_public_b,
        "provider_a": provider_a,
        "provider_b": provider_b,
        "service_a": service_a,
        "service_b": service_b,
        "location_a": location_a,
        "location_b": location_b,
        "client_a": client_a,
        "client_b": client_b,
    }


def test_sql_injection_availability(client, base_security_data):
    """Test SQL injection inputs in availability endpoint GET parameters."""
    data = base_security_data
    headers = {"X-Tenant": "tenant-a", "X-Token": data["token_public_a"]}
    
    # Common SQL Injection inputs
    sql_payloads = [
        "1' OR '1'='1",
        "1 UNION SELECT 1, 2, 3",
        "1; DROP TABLE services; --",
        "' OR 1=1 --",
    ]
    
    # 1. Test service_id validation parameter
    for payload in sql_payloads:
        response = client.get(
            "/api/public/availability",
            params={
                "service_id": payload,
                "provider_id": data["provider_a"].id,
                "date": "2026-07-09T00:00:00Z"
            },
            headers=headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Test provider_id validation parameter
    for payload in sql_payloads:
        response = client.get(
            "/api/public/availability",
            params={
                "service_id": data["service_a"].id,
                "provider_id": payload,
                "date": "2026-07-09T00:00:00Z"
            },
            headers=headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. Test date validation parameter
    for payload in sql_payloads:
        response = client.get(
            "/api/public/availability",
            params={
                "service_id": data["service_a"].id,
                "provider_id": data["provider_a"].id,
                "date": payload
            },
            headers=headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_sql_injection_search_availability(client, base_security_data):
    """Test SQL injection inputs in search-availability POST payload."""
    data = base_security_data
    headers = {"X-Tenant": "tenant-a", "X-Token": data["token_public_a"]}
    
    sql_payloads = [
        "1' OR '1'='1",
        "1; DROP TABLE services; --",
    ]
    
    # 1. Test service_id as SQL injection string in query payload
    for payload in sql_payloads:
        response = client.post(
            "/api/public/search-availability",
            json={
                "service_id": payload,
                "date_from": "2026-07-09T00:00:00Z",
                "date_to": "2026-07-16T00:00:00Z"
            },
            headers=headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Test desired_time parameter (which allows string input)
    # The application should parameterize ORM queries, so the payload
    # shouldn't execute or crash the database session.
    response = client.post(
        "/api/public/search-availability",
        json={
            "service_id": data["service_a"].id,
            "desired_time": "' OR 1=1; DROP TABLE services; --",
            "date_from": "2026-07-09T00:00:00Z",
            "date_to": "2026-07-16T00:00:00Z"
        },
        headers=headers
    )
    assert response.status_code == status.HTTP_200_OK


def test_sql_injection_tenant_headers(client, base_security_data):
    """Test SQL injection inputs in custom headers."""
    data = base_security_data
    
    sql_headers = [
        "' OR '1'='1",
        "tenant-a' OR 1=1 --",
        "tenant-a; DROP TABLE tenants; --",
    ]
    
    for x_tenant in sql_headers:
        response = client.get(
            "/api/public/availability",
            params={
                "service_id": data["service_a"].id,
                "provider_id": data["provider_a"].id,
                "date": "2026-07-09T00:00:00Z"
            },
            headers={
                "X-Tenant": x_tenant,
                "X-Token": data["token_public_a"]
            }
        )
        # Should return 404/401 because SQLAlchemy escapes SQL strings literally,
        # so it looks for a tenant with subdomain matching the SQL fragment exactly.
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_401_UNAUTHORIZED]


def test_negative_pricing_and_duration_validation(client, base_security_data):
    """Test negative pricing, duration, and group sizes in service creation/updating."""
    data = base_security_data
    headers = {
        "X-Tenant": "tenant-a",
        "X-Token": data["token_a"]
    }

    # 1. Negative duration should be rejected (duration ge=1)
    payload_negative_duration = {
        "name": "Negative Duration Service",
        "duration": -10,
        "price": 50.0
    }
    response = client.post("/api/admin/services", json=payload_negative_duration, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    payload_zero_duration = {
        "name": "Zero Duration Service",
        "duration": 0,
        "price": 50.0
    }
    response = client.post("/api/admin/services", json=payload_zero_duration, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Negative min_group_size / max_group_size should be rejected (ge=1)
    payload_invalid_group_size = {
        "name": "Invalid Group Size",
        "duration": 30,
        "price": 50.0,
        "min_group_size": -5
    }
    response = client.post("/api/admin/services", json=payload_invalid_group_size, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. Test negative price and negative deposit amount
    payload_negative_price = {
        "name": "Negative Price Service",
        "duration": 30,
        "price": -100.0,
        "deposit_amount": -10.0
    }
    response = client.post("/api/admin/services", json=payload_negative_price, headers=headers)
    
    # Verify that the server either validation blocks it or gracefully executes it (e.g. 200 OK or 422)
    # without returning 500 error.
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]
    
    if response.status_code == status.HTTP_200_OK:
        service_id = response.json()["data"]["id"]
        # Ensure we can update it to positive values successfully
        resp_update = client.put(
            f"/api/admin/services/{service_id}",
            json={"price": 45.0, "deposit_amount": 0.0},
            headers=headers
        )
        assert resp_update.status_code == status.HTTP_200_OK


def test_past_dates_availability(client, base_security_data):
    """Test availability and search endpoints with past dates."""
    data = base_security_data
    headers = {"X-Tenant": "tenant-a", "X-Token": data["token_public_a"]}
    
    # 1. GET availability in the past
    past_date = "2000-01-01T09:00:00Z"
    response = client.get(
        "/api/public/availability",
        params={
            "service_id": data["service_a"].id,
            "provider_id": data["provider_a"].id,
            "date": past_date
        },
        headers=headers
    )
    # Past queries should return empty slots list but not error out
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"] == []

    # 2. POST search-availability with past dates
    response_search = client.post(
        "/api/public/search-availability",
        json={
            "service_id": data["service_a"].id,
            "date_from": "2010-01-01T00:00:00Z",
            "date_to": "2010-01-07T00:00:00Z"
        },
        headers=headers
    )
    assert response_search.status_code == status.HTTP_200_OK
    assert len(response_search.json()["data"]) == 0


def test_extreme_timezone_offsets(client, base_security_data):
    """Test timezone offsets that are extreme or invalid (+24:00, -24:00, +14:00, -12:00)."""
    data = base_security_data
    headers = {"X-Tenant": "tenant-a", "X-Token": data["token_public_a"]}
    
    # 1. Invalid extreme offsets (+24:00, -24:00) should fail datetime validation (422)
    invalid_offsets = [
        "2026-07-09T10:00:00+24:00",
        "2026-07-09T10:00:00-24:00",
        "2026-07-09T10:00:00+25:00",
    ]
    
    for offset in invalid_offsets:
        # GET availability
        resp_get = client.get(
            "/api/public/availability",
            params={
                "service_id": data["service_a"].id,
                "provider_id": data["provider_a"].id,
                "date": offset
            },
            headers=headers
        )
        assert resp_get.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # POST search-availability
        resp_post = client.post(
            "/api/public/search-availability",
            json={
                "service_id": data["service_a"].id,
                "date_from": offset,
                "date_to": "2026-07-16T10:00:00Z"
            },
            headers=headers
        )
        assert resp_post.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Maximum valid extreme offsets (+14:00, -12:00) should be parsed and processed successfully
    valid_extreme_offsets = [
        "2026-07-09T10:00:00+14:00",
        "2026-07-09T10:00:00-12:00",
    ]
    for offset in valid_extreme_offsets:
        resp_get = client.get(
            "/api/public/availability",
            params={
                "service_id": data["service_a"].id,
                "provider_id": data["provider_a"].id,
                "date": offset
            },
            headers=headers
        )
        assert resp_get.status_code == status.HTTP_200_OK


def test_malformed_payloads_fuzzing(client, base_security_data):
    """Test malformed payloads, payload bloating, and incorrect type formats."""
    data = base_security_data
    headers = {"X-Tenant": "tenant-a", "X-Token": data["token_public_a"]}

    # 1. Payload Bloating: very large string input
    huge_string = "A" * 100_000
    response_bloated = client.post(
        "/api/public/search-availability",
        json={
            "service_id": data["service_a"].id,
            "desired_time": huge_string,
            "date_from": "2026-07-09T00:00:00Z",
            "date_to": "2026-07-16T00:00:00Z"
        },
        headers=headers
    )
    # The endpoint should not crash. Status code should not be 500.
    assert response_bloated.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR

    # 2. Incorrect Type format: passing nested structures where primitives are expected
    response_wrong_type = client.post(
        "/api/public/search-availability",
        json={
            "service_id": {"nested": [1, 2, 3]},
            "date_from": "2026-07-09T00:00:00Z"
        },
        headers=headers
    )
    assert response_wrong_type.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. Completely invalid JSON syntax (HTTP bad request / unprocessable content)
    response_invalid_json = client.post(
        "/api/public/search-availability",
        content="{service_id: 'abc'",
        headers={
            "X-Tenant": "tenant-a",
            "X-Token": data["token_public_a"],
            "Content-Type": "application/json"
        }
    )
    assert response_invalid_json.status_code in [
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_422_UNPROCESSABLE_ENTITY
    ]


def test_cross_tenant_isolation_attempts(client, base_security_data):
    """Test cross-tenant data access attempts, ensuring strict tenant boundaries."""
    data = base_security_data

    # Tenant contexts and headers
    headers_a = {"X-Tenant": "tenant-a", "X-Token": data["token_a"]}
    headers_b = {"X-Tenant": "tenant-b", "X-Token": data["token_b"]}
    public_headers_a = {"X-Tenant": "tenant-a", "X-Token": data["token_public_a"]}
    public_headers_b = {"X-Tenant": "tenant-b", "X-Token": data["token_public_b"]}

    # 1. Tenant A owner tries to access Tenant B's service details directly (should return 404)
    resp_get_service = client.get(f"/api/admin/services/{data['service_b'].id}", headers=headers_a)
    assert resp_get_service.status_code == status.HTTP_404_NOT_FOUND

    # 2. Tenant A owner tries to update Tenant B's service details (should return 404)
    resp_put_service = client.put(
        f"/api/admin/services/{data['service_b'].id}",
        json={"name": "Hacked Service Name"},
        headers=headers_a
    )
    assert resp_put_service.status_code == status.HTTP_404_NOT_FOUND

    # 3. Tenant A owner tries to delete Tenant B's service (should return 404)
    resp_delete_service = client.delete(f"/api/admin/services/{data['service_b'].id}", headers=headers_a)
    assert resp_delete_service.status_code == status.HTTP_404_NOT_FOUND

    # 4. Tenant A public availability search using Tenant B's service ID (should return 404)
    resp_public_availability = client.get(
        "/api/public/availability",
        params={
            "service_id": data["service_b"].id,
            "provider_id": data["provider_a"].id,
            "date": "2026-07-09T09:00:00Z"
        },
        headers=public_headers_a
    )
    assert resp_public_availability.status_code == status.HTTP_404_NOT_FOUND

    # 5. Tenant A public availability search using Tenant B's provider ID (should return 404)
    resp_public_availability_prov = client.get(
        "/api/public/availability",
        params={
            "service_id": data["service_a"].id,
            "provider_id": data["provider_b"].id,
            "date": "2026-07-09T09:00:00Z"
        },
        headers=public_headers_a
    )
    assert resp_public_availability_prov.status_code == status.HTTP_404_NOT_FOUND

    # 6. Tenant A POST search-availability using Tenant B's service ID (should return 404)
    resp_search_b = client.post(
        "/api/public/search-availability",
        json={
            "service_id": data["service_b"].id,
            "date_from": "2026-07-09T00:00:00Z"
        },
        headers=public_headers_a
    )
    assert resp_search_b.status_code == status.HTTP_404_NOT_FOUND

    # 7. Try to book Tenant B's service/provider under Tenant A public booking endpoint (should fail)
    resp_booking = client.post(
        "/api/public/bookings",
        json={
            "client_id": data["client_a"].id,
            "provider_id": data["provider_b"].id,  # Tenant B provider
            "service_id": data["service_a"].id,
            "start_time": "2026-07-09T10:00:00Z",
            "end_time": "2026-07-09T10:30:00Z"
        },
        headers=public_headers_a
    )
    # The provider is not eligible/registered for Tenant A or doesn't exist in Tenant A context.
    # Should return either 400 Bad Request or 404 Not Found.
    assert resp_booking.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]
