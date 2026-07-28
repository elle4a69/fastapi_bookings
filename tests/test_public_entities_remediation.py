import pytest
from datetime import datetime, timezone
from fastapi import status
from app.models.tenant import Tenant
from app.models.service import Service
from app.models.category import Category, ServiceCategory
from app.models.location import Location
from app.models.provider import Provider
from app.core.security import create_access_token

def test_public_entities_tenant_isolation(client, db_session):
    # 1. Create two tenants
    tenant_a = Tenant(name="Tenant A", subdomain="tenant-a", created_at=datetime.now(timezone.utc))
    tenant_b = Tenant(name="Tenant B", subdomain="tenant-b", created_at=datetime.now(timezone.utc))
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    # 2. Create services for each tenant
    service_a = Service(tenant_id=tenant_a.id, name="Service A", duration=30, active=True)
    service_b = Service(tenant_id=tenant_b.id, name="Service B", duration=30, active=True)
    db_session.add_all([service_a, service_b])
    db_session.commit()

    # 3. Create categories and link them
    cat_a = Category(tenant_id=tenant_a.id, name="Category A", active=True)
    cat_b = Category(tenant_id=tenant_b.id, name="Category B", active=True)
    db_session.add_all([cat_a, cat_b])
    db_session.commit()

    link_a = ServiceCategory(tenant_id=tenant_a.id, service_id=service_a.id, category_id=cat_a.id)
    link_b = ServiceCategory(tenant_id=tenant_b.id, service_id=service_b.id, category_id=cat_b.id)
    db_session.add_all([link_a, link_b])
    db_session.commit()

    # Generate public access tokens encoding subdomain
    token_a = create_access_token({"sub": "tenant-a"})
    token_b = create_access_token({"sub": "tenant-b"})

    # 4. Test Service Listing for Tenant A
    headers_a = {"X-Tenant": "tenant-a", "X-Token": token_a}
    response_services = client.get("/api/public/services", headers=headers_a)
    assert response_services.status_code == status.HTTP_200_OK, response_services.text
    data = response_services.json()
    assert data["ok"] is True
    assert len(data["data"]) == 1
    assert data["data"][0]["name"] == "Service A"

    # Test Service Listing for Tenant B
    headers_b = {"X-Tenant": "tenant-b", "X-Token": token_b}
    response_services_b = client.get("/api/public/services", headers=headers_b)
    assert response_services_b.status_code == status.HTTP_200_OK
    assert len(response_services_b.json()["data"]) == 1
    assert response_services_b.json()["data"][0]["name"] == "Service B"

    # 5. Test Categories listing isolation
    response_cats = client.get("/api/public/categories", headers=headers_a)
    assert response_cats.status_code == status.HTTP_200_OK
    cats_data = response_cats.json()
    assert len(cats_data) == 1
    assert cats_data[0]["name"] == "Category A"

    # 6. Test missing Token returns 401
    headers_missing_token = {"X-Tenant": "tenant-a"}
    response_missing = client.get("/api/public/services", headers=headers_missing_token)
    assert response_missing.status_code == status.HTTP_401_UNAUTHORIZED
    assert response_missing.json()["ok"] is False
    assert response_missing.json()["error"]["code"] == "UNAUTHORIZED"

    # 7. Test invalid Tenant returns 404
    headers_invalid_tenant = {"X-Tenant": "nonexistent", "X-Token": token_a}
    response_invalid = client.get("/api/public/services", headers=headers_invalid_tenant)
    assert response_invalid.status_code == status.HTTP_404_NOT_FOUND
    assert response_invalid.json()["error"]["code"] == "NOT_FOUND"

def test_readiness_check(client):
    response = client.get("/ready")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"ok": True}
