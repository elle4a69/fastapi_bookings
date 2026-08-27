import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Client, Payment
from app.models.tenant import Tenant
from app.models.user import User
from app.models.checkout import PaymentProcessorConfig

@pytest.fixture(autouse=True)
def seed_base_data(db_session: Session):
    """Seed base Tenant and Admin User needed by all tests."""
    tenant = Tenant(id=1, name="Simply Demo", subdomain="simplydemo")
    db_session.add(tenant)
    db_session.commit()
    
    admin = User(
        id=1,
        tenant_id=tenant.id,
        login="admin@test.com",
        role="admin",
        password_hash="mock-hash"
    )
    db_session.add(admin)
    db_session.commit()

def test_requirements_literal_route_precedence(client: TestClient, db_session: Session):
    """Verify GET /api/admin/resources/requirements has correct routing precedence."""
    headers = {"X-Token": "mock-admin-token", "X-Tenant": "simplydemo"}
    res = client.get("/api/admin/resources/requirements", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_client_search_endpoint(client: TestClient, db_session: Session):
    """Verify search client by email endpoint."""
    headers = {"X-Token": "mock-admin-token", "X-Tenant": "simplydemo"}
    
    # Create test client
    test_client = Client(
        tenant_id=1,
        name="GDPR Search Test",
        email="gdpr-test@example.com",
        active=True
    )
    db_session.add(test_client)
    db_session.commit()
    db_session.refresh(test_client)
    
    res = client.get("/api/admin/clients/search?email=gdpr-test@example.com", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["data"]["email"] == "gdpr-test@example.com"
    assert data["data"]["name"] == "GDPR Search Test"

def test_refund_payment_endpoint(client: TestClient, db_session: Session):
    """Verify payment refund POST endpoint."""
    headers = {"X-Token": "mock-admin-token", "X-Tenant": "simplydemo"}
    
    # Create test payment
    payment = Payment(
        tenant_id=1,
        booking_id=1,
        amount=100.0,
        currency="USD",
        status="pending"
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)
    
    res = client.post(f"/api/admin/payments/{payment.id}/refund", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["data"]["status"] == "refunded"

def test_finance_processors_bridge(client: TestClient, db_session: Session):
    """Verify /finance/processors GET and PUT bridge endpoints."""
    headers = {"X-Token": "mock-admin-token", "X-Tenant": "simplydemo"}
    
    # GET first (should return defaults)
    res = client.get("/api/admin/finance/processors", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["currency"] == "USD"
    assert "stripe" in data["processors"]
    assert "paypal" in data["processors"]
    assert "offline" in data["processors"]
    
    # PUT to update configurations
    payload = {
        "currency": "USD",
        "processors": {
            "stripe": {
                "enabled": True,
                "public_key": "pk_test_stripe",
                "secret_key": "sk_test_stripe"
            },
            "paypal": {
                "enabled": False,
                "client_id": "paypal_client",
                "client_secret": "paypal_secret"
            },
            "offline": {
                "enabled": True,
                "instructions": "Pay in person"
            }
        }
    }
    res_put = client.put("/api/admin/finance/processors", json=payload, headers=headers)
    assert res_put.status_code == 200
    data_put = res_put.json()
    assert data_put["processors"]["stripe"]["enabled"] is True
    assert data_put["processors"]["stripe"]["public_key"] == "pk_test_stripe"
    assert data_put["processors"]["stripe"]["secret_key"] == "sk_test_stripe"
    assert data_put["processors"]["offline"]["instructions"] == "Pay in person"
    
    # Verify in DB
    stripe_cfg = db_session.query(PaymentProcessorConfig).filter(
        PaymentProcessorConfig.tenant_id == 1,
        PaymentProcessorConfig.provider == "stripe"
    ).first()
    assert stripe_cfg is not None
    assert stripe_cfg.enabled is True
    assert stripe_cfg.public_key == "pk_test_stripe"
