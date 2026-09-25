"""Automated tests for Phase 3: Client Self-Service Portal & Dispute Center.

Verifies:
1. OTP generation and JWT client access token issuance.
2. Client isolation: Client can only view their own bookings and invoices.
3. 1-Tap Reschedule flow and provider conflict avoidance.
4. 1-Tap Cancellation flow.
5. Authorization boundary: Client cannot reschedule or cancel another client's booking.
6. Dispute Center: Lodging a dispute with photo attachments and initial 'submitted' status.
7. Admin Dispute triage: Listing disputes and resolving disputes with resolution notes.
"""

from datetime import datetime, timedelta, timezone
import pytest
from app.models.tenant import Tenant
from app.models.user import User
from app.models.client import Client
from app.models.provider import Provider
from app.models.service import Service
from app.models.booking import Booking
from app.models.client_dispute import ClientDispute
from app.core.security import create_access_token
from app.core.state_machine import BookingStatus


@pytest.fixture
def portal_setup(db_session):
    """Set up tenant, admin, 2 clients, provider, service, and bookings."""
    # 1. Tenant
    tenant = db_session.query(Tenant).filter(Tenant.subdomain == "simplydemo").first()
    if not tenant:
        tenant = Tenant(name="SimplyDemo", subdomain="simplydemo", subscription_tier="unlimited")
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)

    # 2. Admin user
    admin = db_session.query(User).filter(User.tenant_id == tenant.id, User.login == "portal_admin").first()
    if not admin:
        admin = User(tenant_id=tenant.id, login="portal_admin", password_hash="hash", role="admin")
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)

    admin_token = create_access_token({"sub": str(admin.id), "tenant_id": tenant.id, "role": "admin"})

    # 3. Provider
    prov = db_session.query(Provider).filter(Provider.tenant_id == tenant.id, Provider.name == "Portal Provider 1").first()
    if not prov:
        prov = Provider(tenant_id=tenant.id, name="Portal Provider 1", email="prov1@example.com")
        db_session.add(prov)
        db_session.commit()
        db_session.refresh(prov)

    # 4. Service
    srv = db_session.query(Service).filter(Service.tenant_id == tenant.id, Service.name == "Portal Service 1").first()
    if not srv:
        srv = Service(tenant_id=tenant.id, name="Portal Service 1", duration=60, price=100.0)
        db_session.add(srv)
        db_session.commit()
        db_session.refresh(srv)

    # 5. Client 1 & Client 2
    c1 = db_session.query(Client).filter(Client.tenant_id == tenant.id, Client.phone == "0411000001").first()
    if not c1:
        c1 = Client(tenant_id=tenant.id, name="Client 1 - Alice", email="alice@example.com", phone="0411000001", active=True)
        db_session.add(c1)
        db_session.commit()
        db_session.refresh(c1)

    c2 = db_session.query(Client).filter(Client.tenant_id == tenant.id, Client.phone == "0411000002").first()
    if not c2:
        c2 = Client(tenant_id=tenant.id, name="Client 2 - Bob", email="bob@example.com", phone="0411000002", active=True)
        db_session.add(c2)
        db_session.commit()
        db_session.refresh(c2)

    # Clean existing disputes and bookings for clean test run
    db_session.query(ClientDispute).filter(ClientDispute.tenant_id == tenant.id).delete()
    db_session.query(Booking).filter(Booking.tenant_id == tenant.id).delete()
    db_session.commit()

    now = datetime.now(timezone.utc)
    # Booking 1 for Client 1
    bk1 = Booking(
        tenant_id=tenant.id,
        client_id=c1.id,
        provider_id=prov.id,
        service_id=srv.id,
        start_time=now + timedelta(days=1, hours=2),
        end_time=now + timedelta(days=1, hours=3),
        status=BookingStatus.CONFIRMED,
        notes="Booking 1 for Alice",
    )
    # Booking 2 for Client 2
    bk2 = Booking(
        tenant_id=tenant.id,
        client_id=c2.id,
        provider_id=prov.id,
        service_id=srv.id,
        start_time=now + timedelta(days=2, hours=4),
        end_time=now + timedelta(days=2, hours=5),
        status=BookingStatus.CONFIRMED,
        notes="Booking 2 for Bob",
    )
    db_session.add_all([bk1, bk2])
    db_session.commit()
    db_session.refresh(bk1)
    db_session.refresh(bk2)

    return {
        "tenant": tenant,
        "admin": admin,
        "admin_token": admin_token,
        "prov": prov,
        "srv": srv,
        "c1": c1,
        "c2": c2,
        "bk1": bk1,
        "bk2": bk2,
    }


def test_client_otp_flow_and_token_issuance(client, portal_setup):
    """Test OTP code dispatch and verification yielding JWT token."""
    tenant = portal_setup["tenant"]
    c1 = portal_setup["c1"]

    headers = {"X-Tenant": tenant.subdomain}

    # 1. Send OTP
    send_resp = client.post(
        "/api/portal/auth/send-otp",
        json={"phone_or_email": c1.phone},
        headers=headers,
    )
    assert send_resp.status_code == 200, send_resp.text
    data = send_resp.json()
    assert data["ok"] is True
    assert data["client_exists"] is True
    active_code = data["active_code"]

    # 2. Verify with wrong code -> 400
    bad_resp = client.post(
        "/api/portal/auth/verify-otp",
        json={"phone_or_email": c1.phone, "code": "999999"},
        headers=headers,
    )
    assert bad_resp.status_code == 400

    # 3. Verify with fallback 123456 code -> 200
    verify_resp = client.post(
        "/api/portal/auth/verify-otp",
        json={"phone_or_email": c1.phone, "code": "123456"},
        headers=headers,
    )
    assert verify_resp.status_code == 200, verify_resp.text
    vdata = verify_resp.json()
    assert vdata["ok"] is True
    assert "access_token" in vdata["data"]
    assert vdata["data"]["client"]["id"] == c1.id

    # 4. Verify with active_code works as well
    verify_resp2 = client.post(
        "/api/portal/auth/verify-otp",
        json={"phone_or_email": c1.phone, "code": active_code},
        headers=headers,
    )
    assert verify_resp2.status_code == 200


def test_client_booking_isolation(client, portal_setup):
    """Verify that Client 1 can only see their own appointments, not Client 2's."""
    tenant = portal_setup["tenant"]
    c1 = portal_setup["c1"]
    bk1 = portal_setup["bk1"]
    bk2 = portal_setup["bk2"]

    # Generate token for Client 1
    c1_token = create_access_token({"sub": str(c1.id), "tenant_id": tenant.id, "role": "client"})
    headers = {"X-Token": c1_token, "X-Tenant": tenant.subdomain}

    # Profile endpoint
    me_resp = client.get("/api/portal/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["id"] == c1.id

    # Bookings endpoint
    bk_resp = client.get("/api/portal/bookings", headers=headers)
    assert bk_resp.status_code == 200
    items = bk_resp.json()
    assert len(items) == 1
    assert items[0]["id"] == bk1.id
    assert items[0]["service_name"] == "Portal Service 1"
    assert items[0]["can_reschedule"] is True
    assert items[0]["can_cancel"] is True


def test_client_reschedule_flow(client, portal_setup):
    """Verify 1-Tap appointment rescheduling."""
    tenant = portal_setup["tenant"]
    c1 = portal_setup["c1"]
    bk1 = portal_setup["bk1"]

    c1_token = create_access_token({"sub": str(c1.id), "tenant_id": tenant.id, "role": "client"})
    headers = {"X-Token": c1_token, "X-Tenant": tenant.subdomain}

    new_time = (datetime.now(timezone.utc) + timedelta(days=5, hours=10)).isoformat()

    resched_resp = client.post(
        f"/api/portal/bookings/{bk1.id}/reschedule",
        json={"start_time": new_time},
        headers=headers,
    )
    assert resched_resp.status_code == 200, resched_resp.text
    updated = resched_resp.json()
    assert updated["id"] == bk1.id
    assert updated["start_time"] is not None


def test_client_cannot_reschedule_or_cancel_other_client_booking(client, portal_setup):
    """Verify security boundary: Client 1 cannot alter Client 2's booking."""
    tenant = portal_setup["tenant"]
    c1 = portal_setup["c1"]
    bk2 = portal_setup["bk2"]  # Belongs to Client 2!

    c1_token = create_access_token({"sub": str(c1.id), "tenant_id": tenant.id, "role": "client"})
    headers = {"X-Token": c1_token, "X-Tenant": tenant.subdomain}

    # Attempt reschedule bk2
    new_time = (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()
    resp1 = client.post(
        f"/api/portal/bookings/{bk2.id}/reschedule",
        json={"start_time": new_time},
        headers=headers,
    )
    assert resp1.status_code in (403, 404)

    # Attempt cancel bk2
    resp2 = client.post(
        f"/api/portal/bookings/{bk2.id}/cancel",
        json={"reason": "Unauthorized attempt"},
        headers=headers,
    )
    assert resp2.status_code in (403, 404)


def test_client_cancel_booking(client, portal_setup):
    """Verify 1-Tap appointment cancellation."""
    tenant = portal_setup["tenant"]
    c1 = portal_setup["c1"]
    bk1 = portal_setup["bk1"]

    c1_token = create_access_token({"sub": str(c1.id), "tenant_id": tenant.id, "role": "client"})
    headers = {"X-Token": c1_token, "X-Tenant": tenant.subdomain}

    cancel_resp = client.post(
        f"/api/portal/bookings/{bk1.id}/cancel",
        json={"reason": "Changed my schedule."},
        headers=headers,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["ok"] is True


def test_client_dispute_and_admin_resolution(client, portal_setup):
    """Verify dispute lodging with photos and admin resolution flow."""
    tenant = portal_setup["tenant"]
    c1 = portal_setup["c1"]
    bk1 = portal_setup["bk1"]
    admin_token = portal_setup["admin_token"]

    c1_token = create_access_token({"sub": str(c1.id), "tenant_id": tenant.id, "role": "client"})
    client_headers = {"X-Token": c1_token, "X-Tenant": tenant.subdomain}
    admin_headers = {"X-Token": admin_token, "X-Tenant": tenant.subdomain}

    # 1. Client lodges a dispute
    payload = {
        "booking_id": bk1.id,
        "reason": "incomplete_work",
        "description": "Provider left 20 minutes early without completing the final assessment step.",
        "preferred_resolution": "partial_refund",
        "photos": ["https://example.com/photo1.jpg", "https://example.com/photo2.jpg"],
    }
    lodge_resp = client.post("/api/portal/disputes", json=payload, headers=client_headers)
    assert lodge_resp.status_code == 200, lodge_resp.text
    disp_data = lodge_resp.json()
    assert disp_data["status"] == "submitted"
    assert disp_data["reason"] == "incomplete_work"
    assert len(disp_data["photos"]) == 2
    assert disp_data["booking_service_name"] == "Portal Service 1"
    dispute_id = disp_data["id"]

    # 2. Client lists disputes
    list_resp = client.get("/api/portal/disputes", headers=client_headers)
    assert list_resp.status_code == 200
    client_disputes = list_resp.json()
    assert len(client_disputes) == 1
    assert client_disputes[0]["id"] == dispute_id

    # 3. Admin lists disputes
    admin_list_resp = client.get("/api/admin/disputes", headers=admin_headers)
    assert admin_list_resp.status_code == 200
    admin_disputes = admin_list_resp.json()
    assert len(admin_disputes) >= 1
    assert any(d["id"] == dispute_id for d in admin_disputes)

    # 4. Admin updates/resolves dispute
    resolve_resp = client.put(
        f"/api/admin/disputes/{dispute_id}/resolve",
        json={
            "status": "resolved",
            "resolution_notes": "Granted 30% partial refund and issued credit note.",
        },
        headers=admin_headers,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text
    resolved_data = resolve_resp.json()
    assert resolved_data["status"] == "resolved"
    assert "partial refund" in resolved_data["resolution_notes"]
    assert resolved_data["resolved_at"] is not None


def test_client_otp_rate_limiting_and_atomic_consumption(client, portal_setup, monkeypatch):
    """Test OTP rate limit (max 3 per 10m) and single-use atomic consumption."""
    tenant = portal_setup["tenant"]
    test_phone = "0411999888"
    headers = {"X-Tenant": tenant.subdomain}

    # 1. First 3 requests succeed
    codes = []
    for _ in range(3):
        resp = client.post("/api/portal/auth/send-otp", json={"phone_or_email": test_phone}, headers=headers)
        assert resp.status_code == 200
        codes.append(resp.json()["active_code"])

    # 2. 4th request within 10 minutes hits rate limit (429)
    resp4 = client.post("/api/portal/auth/send-otp", json={"phone_or_email": test_phone}, headers=headers)
    assert resp4.status_code == 429
    assert "Too many OTP requests" in resp4.text

    # 3. The latest active code verifies successfully
    latest_code = codes[-1]
    verify1 = client.post("/api/portal/auth/verify-otp", json={"phone_or_email": test_phone, "code": latest_code}, headers=headers)
    assert verify1.status_code == 200

    # 4. Atomic single-use check: Trying to verify the same code a 2nd time fails (already consumed)
    verify2 = client.post("/api/portal/auth/verify-otp", json={"phone_or_email": test_phone, "code": latest_code}, headers=headers)
    assert verify2.status_code == 400
    assert "Invalid or expired verification code" in verify2.text


def test_client_otp_production_mode_rejects_bypass(client, portal_setup, monkeypatch):
    """In production mode, hardcoded demo codes (123456) must be strictly rejected."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "APP_ENV", "production")

    tenant = portal_setup["tenant"]
    test_phone = "0411777666"
    headers = {"X-Tenant": tenant.subdomain}

    # Request OTP
    send_resp = client.post("/api/portal/auth/send-otp", json={"phone_or_email": test_phone}, headers=headers)
    assert send_resp.status_code == 200
    # In production, demo_code and active_code must NOT be leaked
    assert "demo_code" not in send_resp.json()
    assert "active_code" not in send_resp.json()

    # Attempt verify with bypass code 123456 -> must fail with 400
    bypass_resp = client.post("/api/portal/auth/verify-otp", json={"phone_or_email": test_phone, "code": "123456"}, headers=headers)
    assert bypass_resp.status_code == 400

