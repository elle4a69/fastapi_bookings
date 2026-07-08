"""Tests for public authentication model, X-Token requirements, and multi-service availability search."""

from datetime import datetime, timezone, date
from fastapi import status
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User
from app.models.service import Service
from app.models.provider import Provider
from app.models.category import Category, ServiceCategory
from app.models.schedule import ProviderWorkDay
from app.core.security import create_access_token


def test_public_endpoints_require_x_token(client, db_session: Session):
    """Verify that the updated public endpoints enforce X-Token authentication."""
    # Create tenant
    tenant = Tenant(name="Test Biz", subdomain="test-biz", created_at=datetime.now(timezone.utc))
    db_session.add(tenant)
    db_session.commit()

    # 1. Missing X-Token header -> FastAPI returns 422 Unprocessable Entity
    headers_missing_token = {
        "X-Tenant": "test-biz"
    }
    
    # Check GET /api/public/ui-config
    response = client.get("/api/public/ui-config", headers=headers_missing_token)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Check GET /api/public/additional-fields
    response = client.get("/api/public/additional-fields", headers=headers_missing_token)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Check POST /api/public/search-availability
    query_payload = {
        "date_from": "2026-07-06T00:00:00Z",
        "date_to": "2026-07-06T23:59:59Z"
    }
    response = client.post("/api/public/search-availability", json=query_payload, headers=headers_missing_token)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. Invalid X-Token header -> returns 401 Unauthorized
    headers_invalid_token = {
        "X-Tenant": "test-biz",
        "X-Token": "invalid_jwt_token_here"
    }
    response = client.get("/api/public/ui-config", headers=headers_invalid_token)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # 3. Valid X-Token -> returns 200 OK
    valid_token = create_access_token({"sub": "test-biz"})
    headers_valid = {
        "X-Tenant": "test-biz",
        "X-Token": valid_token
    }
    response = client.get("/api/public/ui-config", headers=headers_valid)
    assert response.status_code == status.HTTP_200_OK


def test_multi_service_availability_search(client, db_session: Session):
    """Verify that multi-service availability search queries all active tenant services and standardizes slot schema."""
    # 1. Setup tenant, provider, and active services
    tenant = Tenant(name="Search Biz", subdomain="search-biz", created_at=datetime.now(timezone.utc))
    db_session.add(tenant)
    db_session.commit()

    provider = Provider(tenant_id=tenant.id, name="Dr. Alex", active=True, created_at=datetime.now(timezone.utc))
    service_a = Service(
        tenant_id=tenant.id,
        name="Service A",
        duration=30,
        price=50.0,
        active=True
    )
    service_b = Service(
        tenant_id=tenant.id,
        name="Service B",
        duration=30,
        price=75.0,
        active=True
    )
    # inactive service that should not be returned
    service_inactive = Service(
        tenant_id=tenant.id,
        name="Service Inactive",
        duration=30,
        price=100.0,
        active=False
    )
    db_session.add_all([provider, service_a, service_b, service_inactive])
    db_session.commit()

    # 2. Assign Service A to Category A
    category = Category(name="Category A", created_at=datetime.now(timezone.utc))
    db_session.add(category)
    db_session.commit()

    service_cat = ServiceCategory(service_id=service_a.id, category_id=category.id)
    db_session.add(service_cat)
    db_session.commit()

    # 3. Set weekly workday on Monday from 09:00 to 10:00 (allows slots 09:00, 09:15, 09:30)
    workday = ProviderWorkDay(
        tenant_id=tenant.id,
        provider_id=provider.id,
        weekday=0, # Monday
        start_time="09:00",
        end_time="10:00",
        is_working=True,
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(workday)
    db_session.commit()

    # Generate token
    valid_token = create_access_token({"sub": "search-biz"})
    headers = {
        "X-Tenant": "search-biz",
        "X-Token": valid_token
    }

    # Query window: Monday, July 6, 2026 (weekday=0)
    query_payload = {
        "date_from": "2026-07-06T00:00:00Z",
        "date_to": "2026-07-06T23:59:59Z"
    }

    # Case A: Search without service_id, filtered by Category A
    payload_cat = dict(query_payload)
    payload_cat["category_id"] = category.id
    
    response = client.post("/api/public/search-availability", json=payload_cat, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    
    # Should only return Service A slots (not Service B)
    # Expected slots for Service A: 09:00-09:30, 09:15-09:45, 09:30-10:00 (3 slots)
    assert len(data) == 3
    for slot in data:
        assert slot["service"] == {"id": service_a.id, "name": service_a.name}
        # Check timezone awareness in ISO string format
        assert slot["start_time"].endswith("+00:00") or slot["start_time"].endswith("Z")

    # Case B: Search without service_id, no category filter
    response_all = client.post("/api/public/search-availability", json=query_payload, headers=headers)
    assert response_all.status_code == status.HTTP_200_OK
    data_all = response_all.json()["data"]

    # Should return both Service A (3 slots) and Service B (3 slots) = 6 slots
    assert len(data_all) == 6
    services_returned = [slot["service"]["id"] for slot in data_all]
    assert services_returned.count(service_a.id) == 3
    assert services_returned.count(service_b.id) == 3
    assert service_inactive.id not in services_returned
