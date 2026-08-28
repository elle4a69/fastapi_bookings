import pytest
from datetime import datetime, timezone
from fastapi import status
from app.models.tenant import Tenant
from app.models.user import User
from app.models.checkout import PaymentProcessorConfig
from app.core.security import create_access_token

@pytest.fixture
def setup_processor_data(db_session):
    tenant_a = Tenant(name="Tenant A", subdomain="proc-a", created_at=datetime.now(timezone.utc))
    tenant_b = Tenant(name="Tenant B", subdomain="proc-b", created_at=datetime.now(timezone.utc))
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    admin_a = User(tenant_id=tenant_a.id, login="admin@proc-a.com", password_hash="hash", role="admin")
    admin_b = User(tenant_id=tenant_b.id, login="admin@proc-b.com", password_hash="hash", role="admin")
    db_session.add_all([admin_a, admin_b])
    db_session.commit()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
    }

def test_payment_processor_configs_lifecycle_and_isolation(client, setup_processor_data, db_session):
    tenant_a = setup_processor_data["tenant_a"]
    tenant_b = setup_processor_data["tenant_b"]
    admin_a = setup_processor_data["admin_a"]
    admin_b = setup_processor_data["admin_b"]

    headers_a = {"X-Tenant": tenant_a.subdomain, "X-Token": create_access_token({"sub": str(admin_a.id)})}
    headers_b = {"X-Tenant": tenant_b.subdomain, "X-Token": create_access_token({"sub": str(admin_b.id)})}

    # 1. Initially empty for Tenant A
    resp = client.get("/api/admin/payment-processor/configs", headers=headers_a)
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert resp.json() == []

    # 2. Create Stripe config for Tenant A
    stripe_payload = {
        "provider": "stripe",
        "enabled": True,
        "display_name": "Stripe",
        "public_key": "pk_test_123",
        "config_json": '{"secret_key": "sk_test_123"}'
    }
    resp = client.post("/api/admin/payment-processor/configs", json=stripe_payload, headers=headers_a)
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    config_a_id = resp.json()["id"]
    assert resp.json()["provider"] == "stripe"
    assert resp.json()["public_key"] == "pk_test_123"

    # 3. Verify Tenant B sees nothing (tenant isolation)
    resp_b = client.get("/api/admin/payment-processor/configs", headers=headers_b)
    assert resp_b.status_code == status.HTTP_200_OK, resp_b.text
    assert len(resp_b.json()) == 0

    # 4. Update Stripe config for Tenant A
    update_payload = {
        "enabled": False,
        "public_key": "pk_test_456"
    }
    resp = client.put(f"/api/admin/payment-processor/configs/{config_a_id}", json=update_payload, headers=headers_a)
    assert resp.status_code == status.HTTP_200_OK, resp.text
    assert resp.json()["enabled"] is False
    assert resp.json()["public_key"] == "pk_test_456"

    # 5. Tenant B cannot update Tenant A's config (404)
    resp = client.put(f"/api/admin/payment-processor/configs/{config_a_id}", json=update_payload, headers=headers_b)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
