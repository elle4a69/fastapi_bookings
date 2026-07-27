import pytest
from datetime import datetime, timezone
from fastapi import status
from app.models.tenant import Tenant
from app.models.user import User
from app.core.security import create_access_token

@pytest.fixture
def setup_tenants(db_session):
    # Create tenant A
    tenant_a = Tenant(name="Tenant A", subdomain="tenant-a")
    db_session.add(tenant_a)
    db_session.commit()

    # Create admin user for Tenant A
    admin_a = User(tenant_id=tenant_a.id, login="admin@a.com", password_hash="hash", role="admin")
    db_session.add(admin_a)
    db_session.commit()

    # Create tokens
    token_admin_a = create_access_token({"sub": str(admin_a.id)})
    
    return {
        "tenant_a": tenant_a,
        "admin_a": admin_a,
        "token_a": token_admin_a
    }

def test_package_tenant_scoping_on_post(client, setup_tenants):
    headers = {"X-Tenant": "tenant-a", "X-Token": setup_tenants["token_a"]}
    
    package_payload = {
        "name": "Remediation Package",
        "description": "Fuzzer fix verification package",
        "price": 150.0,
        "active": True
    }
    
    # 1. Create a service package -> should succeed and populate tenant_id
    response = client.post("/api/admin/packages", json=package_payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json()["name"] == "Remediation Package"
    
    # 2. Get packages list -> should return 1 package
    response_list = client.get("/api/admin/packages", headers=headers)
    assert response_list.status_code == status.HTTP_200_OK
    assert len(response_list.json()) == 1

def test_plugin_state_tenant_scoping_on_post(client, setup_tenants):
    headers = {"X-Tenant": "tenant-a", "X-Token": setup_tenants["token_a"]}
    
    payload = {
        "name": "remediation-feature",
        "is_enabled": True
    }
    
    # 1. Upsert plugin state -> should succeed and use tenant_id from active user context
    response = client.post("/api/admin/plugin-states", json=payload, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["data"]["name"] == "remediation-feature"
    assert response.json()["data"]["is_enabled"] is True

def test_provider_endpoints_not_found_remediation(client, setup_tenants):
    headers = {"X-Tenant": "tenant-a", "X-Token": setup_tenants["token_a"]}
    
    # 1. PUT to non-existent provider -> should return 404 Not Found
    payload = {
        "name": "Non-existent Doc",
        "email": "notfound@doc.com",
        "active": True
    }
    response_put = client.put("/api/admin/providers/prov-9999", json=payload, headers=headers)
    assert response_put.status_code == status.HTTP_404_NOT_FOUND
    
    # 2. DELETE non-existent provider -> should return 404 Not Found
    response_del = client.delete("/api/admin/providers/prov-9999", headers=headers)
    assert response_del.status_code == status.HTTP_404_NOT_FOUND
