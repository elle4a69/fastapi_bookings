import pytest
from app.models.tenant import Tenant
from app.models.user import User
from app.models.client import Client
from app.models.provider import Provider
from app.models.service import Service
from app.models.location import Location
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_arrival import SmsArrivalSession
from app.core.security import create_access_token
from scripts.seed_clean_numbered_data import seed_numbered_mock_data


def test_seed_clean_numbered_mock_data(db_session):
    """Verify that seed_numbered_mock_data creates clean numbered traceable entities."""
    result = seed_numbered_mock_data(db=db_session, reset_existing=False)
    assert result["success"] is True
    assert len(result["providers"]) == 2
    assert len(result["services"]) == 5
    assert len(result["clients"]) == 5
    assert len(result["locations"]) == 2
    assert len(result["packages"]) == 2
    assert len(result["resources"]) == 3
    assert len(result["addons"]) == 3
    assert len(result["products"]) == 3

    # Check entities in DB
    p1 = db_session.query(Provider).filter(Provider.name.like("Provider 1%")).first()
    assert p1 is not None

    s1 = db_session.query(Service).filter(Service.name.like("Service 1%")).first()
    assert s1 is not None
    assert s1.duration == 60

    c1 = db_session.query(Client).filter(Client.name.like("Client 1%")).first()
    assert c1 is not None
    assert c1.phone == "0411000001"

    loc1 = db_session.query(Location).filter(Location.name.like("Location 1%")).first()
    assert loc1 is not None


def test_seed_scenarios_endpoint(client, db_session):
    """Verify POST /api/admin/sms/conversations/seed-scenarios endpoint."""
    # Ensure tenant and admin user
    tenant = db_session.query(Tenant).filter(Tenant.subdomain == "simplydemo").first()
    if not tenant:
        tenant = Tenant(name="SimplyDemo", subdomain="simplydemo")
        db_session.add(tenant)
        db_session.commit()

    admin = db_session.query(User).filter(User.tenant_id == tenant.id, User.login == "admin").first()
    if not admin:
        admin = User(tenant_id=tenant.id, login="admin", password_hash="hash", role="admin")
        db_session.add(admin)
        db_session.commit()

    token = create_access_token({"sub": str(admin.id)})
    headers = {
        "X-Token": token,
        "X-Tenant": tenant.subdomain
    }

    # Call seed-scenarios
    resp = client.post(
        "/api/admin/sms/conversations/seed-scenarios",
        json={"clear_existing": True},
        headers=headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["scenarios_count"] == 16
    assert data["conversations_count"] == 5
    assert data["arrivals_count"] >= 3
    assert data["drafts_count"] >= 5

    # Verify messages created
    messages = db_session.query(SmsMessage).filter(SmsMessage.tenant_id == tenant.id).all()
    assert len(messages) >= 16

    # Verify arrival sessions created
    arrivals = db_session.query(SmsArrivalSession).all()
    assert len(arrivals) >= 3

    # Check conversation list endpoint sees these conversations
    convs_resp = client.get("/api/admin/sms/conversations", headers=headers)
    assert convs_resp.status_code == 200
    conv_list = convs_resp.json()
    assert len(conv_list) >= 5


def test_run_seed_wrapper(db_session, monkeypatch):
    """Verify run_seed.run() returns clean numbered data."""
    import run_seed
    monkeypatch.setattr(run_seed, "SessionLocal", lambda: db_session)
    res = run_seed.run()
    assert res["success"] is True
    assert len(res["providers"]) == 2
    assert len(res["services"]) == 5

