"""Security and Isolation Hardening Verification Suite.

Validates the 5 critical security and tenant isolation remediations:
1. Chatwoot AgentBot account ID mapping to internal tenant ID
2. Website public chat transcript endpoint tenant-scoped HMAC protection
3. Public timeline company-wide workdays query scoped to current_tenant.id
4. Admin GDPR consent query isolation scoped to current_tenant.id
5. Booking idempotency key composite constraint scoped to (tenant_id, idempotency_key)
"""

from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.db.database import Base, get_db
from app.db.async_session import get_async_db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.client import Client
from app.models.provider import Provider
from app.models.service import Service
from app.models.schedule import ProviderWorkDay, ProviderSpecialDay
from app.models.general_systems import GdprConsent
from app.models.booking import Booking, BookingStatus
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_chatwoot import SmsChatwootBinding
from app.core.config import settings
from app.core.security import create_access_token
from app.api.routers.website import generate_chat_session_token
from app.api.routers.chatwoot_agentbot import resolve_chatwoot_tenant


@pytest_asyncio.fixture
async def async_test_db():
    """Provides an isolated in-memory SQLite database session for async router testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


# ─── Fix 1: Chatwoot AgentBot Account Mapping ─────────────────────────────────

@pytest.mark.asyncio
async def test_chatwoot_account_mapping_resolves_authentic_tenant(async_test_db):
    """Chatwoot account ID must resolve to the authentic internal tenant ID via resolve_chatwoot_tenant."""
    t1 = Tenant(name="Tenant One", subdomain="tenant-one", chatwoot_account_id=101)
    t2 = Tenant(name="Tenant Two", subdomain="tenant-two", chatwoot_account_id=202)
    async_test_db.add_all([t1, t2])
    await async_test_db.commit()

    # 1. Query with account_id 101 resolves to t1.id
    res_id_1, _, _ = await resolve_chatwoot_tenant(async_test_db, account_id=101)
    assert res_id_1 == t1.id

    # 2. Query with account_id 202 resolves to t2.id
    res_id_2, _, _ = await resolve_chatwoot_tenant(async_test_db, account_id=202)
    assert res_id_2 == t2.id

    # 3. SmsChatwootBinding takes precedence if configured
    p = Provider(tenant_id=t2.id, name="Dr. Binding", active=True)
    async_test_db.add(p)
    await async_test_db.flush()

    binding = SmsChatwootBinding(
        tenant_id=t2.id,
        provider_id=p.id,
        chatwoot_account_id=505,
        chatwoot_inbox_id=606,
        chatwoot_base_url="https://app.chatwoot.com",
        _chatwoot_api_token="test_token",
        is_enabled=True,
    )
    async_test_db.add(binding)
    await async_test_db.commit()

    res_binding_tenant, res_provider, binding_obj = await resolve_chatwoot_tenant(
        async_test_db, account_id=505, inbox_id=606
    )
    assert res_binding_tenant == t2.id
    assert res_provider == p.id
    assert binding_obj is not None


@pytest.mark.asyncio
async def test_chatwoot_agentbot_resolved_curation_uses_mapped_tenant(async_test_db):
    """Resolved conversation event must curate against resolved internal tenant_id, not raw Chatwoot account_id."""
    tenant = Tenant(name="Alpha Clinic", subdomain="alphaclinic", chatwoot_account_id=9999)
    async_test_db.add(tenant)
    await async_test_db.commit()

    async def override_get_async_db():
        yield async_test_db

    app.dependency_overrides[get_async_db] = override_get_async_db
    try:
        headers = {"X-Chatwoot-Token": settings.CHATWOOT_WEBHOOK_SECRET} if getattr(settings, "CHATWOOT_WEBHOOK_SECRET", "") else {}
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            payload = {
                "event": "conversation_resolved",
                "conversation": {
                    "id": 555,
                    "status": "resolved",
                },
                "account": {
                    "id": 9999,
                },
                "transcript": [
                    {"sender": "customer", "text": "I need to book a session"},
                    {"sender": "agent", "text": "Sure, here are available slots"},
                ],
            }
            resp = await ac.post("/api/v1/chatwoot/webhook", json=payload, headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "handled"
            assert data["action"] == "conversation_curation_enqueued"
            assert data["conversation_id"] == 555
            assert data["account_id"] == 9999
            # Crucial security assertion: tenant_id MUST be the authentic internal tenant.id, NOT 9999!
            assert data["tenant_id"] == tenant.id
            assert data["tenant_id"] != 9999
    finally:
        app.dependency_overrides.pop(get_async_db, None)


@pytest.mark.asyncio
async def test_chatwoot_agentbot_unmapped_account_in_production(async_test_db, monkeypatch):
    """In production mode, unmapped Chatwoot account must be rejected."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    async def override_get_async_db():
        yield async_test_db

    app.dependency_overrides[get_async_db] = override_get_async_db
    try:
        headers = {"X-Chatwoot-Token": settings.CHATWOOT_WEBHOOK_SECRET} if getattr(settings, "CHATWOOT_WEBHOOK_SECRET", "") else {}
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            payload = {
                "event": "conversation_resolved",
                "conversation": {
                    "id": 666,
                    "status": "resolved",
                },
                "account": {
                    "id": 77777,  # Non-existent account
                },
                "transcript": [{"sender": "customer", "text": "hello"}],
            }
            resp = await ac.post("/api/v1/chatwoot/webhook", json=payload, headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ignored"
            assert data["reason"] == "unmapped_chatwoot_account"
    finally:
        app.dependency_overrides.pop(get_async_db, None)


# ─── Fix 2: Website Chat Transcript Endpoint Security ─────────────────────────

def test_website_chat_transcript_requires_valid_hmac_token(client, db_session):
    """Public chat transcript endpoint must enforce tenant-scoped HMAC token verification."""
    tenant = Tenant(name="Glow Spa", subdomain="glowspa")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    # 1. Start a chat conversation via POST /api/public/website/chat
    chat_payload = {
        "tenant_id": tenant.id,
        "visitor_name": "Alice Visitor",
        "visitor_contact": "alice@example.com",
        "message": "What treatments do you offer?",
    }
    post_resp = client.post(
        "/api/public/website/chat",
        json=chat_payload,
        headers={"X-Tenant": "glowspa"},
    )
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data["ok"] is True
    conv_id = post_data["conversation_id"]
    session_token = post_data.get("session_token")
    assert session_token is not None
    assert len(session_token) == 64  # SHA256 hex string

    # 2. Attempt GET without token -> 403 Forbidden
    get_no_token = client.get(
        f"/api/public/website/chat/{conv_id}",
        headers={"X-Tenant": "glowspa"},
    )
    assert get_no_token.status_code == 403
    err_body = get_no_token.json()
    assert not err_body.get("ok", True)
    assert "Invalid or missing" in err_body["error"]["message"]

    # 3. Attempt GET with forged / tampered token -> 403 Forbidden
    get_bad_token = client.get(
        f"/api/public/website/chat/{conv_id}?token=bad_forged_token_12345",
        headers={"X-Tenant": "glowspa"},
    )
    assert get_bad_token.status_code == 403

    # 4. Attempt GET with valid token in query param -> 200 OK
    get_valid_query = client.get(
        f"/api/public/website/chat/{conv_id}?token={session_token}",
        headers={"X-Tenant": "glowspa"},
    )
    assert get_valid_query.status_code == 200
    assert get_valid_query.json()["ok"] is True
    assert len(get_valid_query.json()["messages"]) >= 1

    # 5. Attempt GET with valid token in X-Chat-Session-Token header -> 200 OK
    get_valid_header = client.get(
        f"/api/public/website/chat/{conv_id}",
        headers={"X-Tenant": "glowspa", "X-Chat-Session-Token": session_token},
    )
    assert get_valid_header.status_code == 200
    assert get_valid_header.json()["ok"] is True

    # 6. Verify cross-tenant token isolation:
    # A token generated for tenant A cannot access a conversation in tenant B
    other_tenant = Tenant(name="Other Studio", subdomain="otherstudio")
    db_session.add(other_tenant)
    db_session.commit()
    db_session.refresh(other_tenant)

    other_token = generate_chat_session_token(other_tenant.id, conv_id)
    get_cross_token = client.get(
        f"/api/public/website/chat/{conv_id}?token={other_token}",
        headers={"X-Tenant": "glowspa"},
    )
    assert get_cross_token.status_code == 403


def test_website_chat_transcript_accessible_by_tenant_admin(client, db_session):
    """Tenant admin with valid JWT X-Token can inspect chat transcripts."""
    tenant = Tenant(name="Salon Lux", subdomain="salonlux")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    admin_user = User(
        tenant_id=tenant.id,
        login="admin_lux",
        password_hash="hashed_pw_test",
        role="admin",
    )
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(admin_user)

    admin_token = create_access_token(data={"sub": str(admin_user.id)})

    p = Provider(tenant_id=tenant.id, name="Admin Provider", active=True)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    # Create conversation directly in DB
    conv = SmsConversation(
        tenant_id=tenant.id,
        provider_id=p.id,
        customer_address="web_guest_123",
        source="web_chat",
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    msg = SmsMessage(
        tenant_id=tenant.id,
        provider_id=p.id,
        conversation_id=conv.id,
        body="Hello admin",
        direction="inbound",
        author_type="customer",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(msg)
    db_session.commit()

    resp = client.get(
        f"/api/public/website/chat/{conv.id}",
        headers={"X-Tenant": "salonlux", "X-Token": admin_token},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert len(resp.json()["messages"]) == 1


# ─── Fix 3: Public Timeline Company-Wide Workdays Scoped to Tenant ────────────

def test_public_timeline_workdays_strictly_scoped_to_current_tenant(client, db_session):
    """Company-wide default workdays (provider_id IS NULL) must not leak across tenants."""
    # Tenant 1: Monday workday 08:00 - 16:00
    t1 = Tenant(name="Tenant One", subdomain="tenant1")
    # Tenant 2: Tuesday workday 10:00 - 18:00
    t2 = Tenant(name="Tenant Two", subdomain="tenant2")
    db_session.add_all([t1, t2])
    db_session.commit()
    db_session.refresh(t1)
    db_session.refresh(t2)

    p1 = Provider(tenant_id=t1.id, name="Dr. One", active=True)
    p2 = Provider(tenant_id=t2.id, name="Dr. Two", active=True)
    db_session.add_all([p1, p2])
    db_session.commit()
    db_session.refresh(p1)
    db_session.refresh(p2)

    # Company-wide workday for Tenant 1 (provider_id is NULL)
    cw1 = ProviderWorkDay(
        tenant_id=t1.id,
        provider_id=None,
        weekday=0,  # Monday
        start_time="08:00",
        end_time="16:00",
        is_working=True,
    )
    # Company-wide workday for Tenant 2 (provider_id is NULL)
    cw2 = ProviderWorkDay(
        tenant_id=t2.id,
        provider_id=None,
        weekday=1,  # Tuesday
        start_time="10:00",
        end_time="18:00",
        is_working=True,
    )
    db_session.add_all([cw1, cw2])
    db_session.commit()

    # Query schedule for p1 under Tenant 1
    resp_t1 = client.get(
        f"/api/public/timeline/schedule/{p1.id}",
        headers={"X-Tenant": "tenant1"},
    )
    assert resp_t1.status_code == 200
    data_t1 = resp_t1.json()["data"]
    workdays_t1 = data_t1["workdays"]
    assert len(workdays_t1) == 1
    assert workdays_t1[0]["weekday"] == 0
    assert workdays_t1[0]["start_time"] == "08:00"
    # Ensure Tenant 2's workday is NOT present
    assert not any(w["weekday"] == 1 for w in workdays_t1)

    # Query schedule for p2 under Tenant 2
    resp_t2 = client.get(
        f"/api/public/timeline/schedule/{p2.id}",
        headers={"X-Tenant": "tenant2"},
    )
    assert resp_t2.status_code == 200
    data_t2 = resp_t2.json()["data"]
    workdays_t2 = data_t2["workdays"]
    assert len(workdays_t2) == 1
    assert workdays_t2[0]["weekday"] == 1
    assert workdays_t2[0]["start_time"] == "10:00"
    # Ensure Tenant 1's workday is NOT present
    assert not any(w["weekday"] == 0 for w in workdays_t2)

    # Cross-tenant query: querying p1 under Tenant 2 must return 404
    resp_cross = client.get(
        f"/api/public/timeline/schedule/{p1.id}",
        headers={"X-Tenant": "tenant2"},
    )
    assert resp_cross.status_code == 404


# ─── Fix 4: Admin GDPR Consent Isolation ──────────────────────────────────────

def test_admin_gdpr_consents_strictly_scoped_to_current_tenant(client, db_session):
    """Admin GDPR consent endpoints must never leak records across tenants."""
    t1 = Tenant(name="Tenant Alpha", subdomain="alpha")
    t2 = Tenant(name="Tenant Beta", subdomain="beta")
    db_session.add_all([t1, t2])
    db_session.commit()
    db_session.refresh(t1)
    db_session.refresh(t2)

    admin1 = User(tenant_id=t1.id, login="admin_alpha", password_hash="pw1", role="admin")
    admin2 = User(tenant_id=t2.id, login="admin_beta", password_hash="pw2", role="admin")
    db_session.add_all([admin1, admin2])
    db_session.commit()
    db_session.refresh(admin1)
    db_session.refresh(admin2)

    token1 = create_access_token(data={"sub": str(admin1.id)})
    token2 = create_access_token(data={"sub": str(admin2.id)})

    c1 = Client(tenant_id=t1.id, name="Client One", email="c1@alpha.com")
    c2 = Client(tenant_id=t2.id, name="Client Two", email="c2@beta.com")
    db_session.add_all([c1, c2])
    db_session.commit()
    db_session.refresh(c1)
    db_session.refresh(c2)

    # Record consent for Client 1
    resp_c1 = client.post(
        "/api/public/gdpr-consent",
        json={
            "client_id": c1.id,
            "consent_type": "gdpr",
            "is_approved": True,
            "ip_address": "1.1.1.1",
        },
    )
    assert resp_c1.status_code == 201

    # Record consent for Client 2
    resp_c2 = client.post(
        "/api/public/gdpr-consent",
        json={
            "client_id": c2.id,
            "consent_type": "marketing",
            "is_approved": True,
            "ip_address": "2.2.2.2",
        },
    )
    assert resp_c2.status_code == 201

    # Admin 1 lists consents: must only see Client 1 consent
    resp_list1 = client.get(
        "/api/admin/gdpr-consents",
        headers={"X-Tenant": "alpha", "X-Token": token1},
    )
    assert resp_list1.status_code == 200
    items1 = resp_list1.json()["data"]
    assert len(items1) == 1
    assert items1[0]["client_id"] == c1.id
    assert items1[0]["consent_type"] == "gdpr"

    # Admin 2 lists consents: must only see Client 2 consent
    resp_list2 = client.get(
        "/api/admin/gdpr-consents",
        headers={"X-Tenant": "beta", "X-Token": token2},
    )
    assert resp_list2.status_code == 200
    items2 = resp_list2.json()["data"]
    assert len(items2) == 1
    assert items2[0]["client_id"] == c2.id
    assert items2[0]["consent_type"] == "marketing"

    # Admin 1 attempts to query consents for Client 2 (from tenant 2): must return empty list
    resp_cross = client.get(
        f"/api/admin/gdpr-consents/{c2.id}",
        headers={"X-Tenant": "alpha", "X-Token": token1},
    )
    assert resp_cross.status_code == 200
    assert len(resp_cross.json()["data"]) == 0


# ─── Fix 5: Tenant-Scoped Booking Idempotency Key ─────────────────────────────

def test_booking_idempotency_scoped_per_tenant(client, db_session):
    """The same idempotency key used in two different tenants must succeed without conflict."""
    t1 = Tenant(name="Tenant Foo", subdomain="foo")
    t2 = Tenant(name="Tenant Bar", subdomain="bar")
    db_session.add_all([t1, t2])
    db_session.commit()
    db_session.refresh(t1)
    db_session.refresh(t2)

    p1 = Provider(tenant_id=t1.id, name="Prov Foo", active=True)
    p2 = Provider(tenant_id=t2.id, name="Prov Bar", active=True)
    s1 = Service(tenant_id=t1.id, name="Svc Foo", duration=60, price=100.0, active=True)
    s2 = Service(tenant_id=t2.id, name="Svc Bar", duration=60, price=100.0, active=True)
    c1 = Client(tenant_id=t1.id, name="Client Foo", email="foo@test.com")
    c2 = Client(tenant_id=t2.id, name="Client Bar", email="bar@test.com")
    db_session.add_all([p1, p2, s1, s2, c1, c2])
    db_session.commit()
    db_session.refresh(p1)
    db_session.refresh(p2)
    db_session.refresh(s1)
    db_session.refresh(s2)
    db_session.refresh(c1)
    db_session.refresh(c2)

    shared_idempotency_key = "idemp-unique-client-order-999"
    start = datetime.now(timezone.utc) + timedelta(days=2)
    end = start + timedelta(minutes=60)

    # 1. Create booking in Tenant 1 with shared_idempotency_key
    b1 = Booking(
        tenant_id=t1.id,
        client_id=c1.id,
        provider_id=p1.id,
        service_id=s1.id,
        start_time=start,
        end_time=end,
        status=BookingStatus.CONFIRMED,
        idempotency_key=shared_idempotency_key,
    )
    db_session.add(b1)
    db_session.commit()
    db_session.refresh(b1)
    assert b1.id is not None

    # 2. Create booking in Tenant 2 with the exact same shared_idempotency_key
    # Prior to the fix, this would fail with unique constraint violation on idempotency_key!
    b2 = Booking(
        tenant_id=t2.id,
        client_id=c2.id,
        provider_id=p2.id,
        service_id=s2.id,
        start_time=start,
        end_time=end,
        status=BookingStatus.CONFIRMED,
        idempotency_key=shared_idempotency_key,
    )
    db_session.add(b2)
    db_session.commit()
    db_session.refresh(b2)
    assert b2.id is not None
    assert b1.id != b2.id
    assert b1.idempotency_key == b2.idempotency_key

    # 3. Inserting a duplicate booking within the SAME tenant with the same idempotency key
    # must fail with IntegrityError (enforcing composite constraint)
    nested = db_session.begin_nested()
    b1_dup = Booking(
        tenant_id=t1.id,
        client_id=c1.id,
        provider_id=p1.id,
        service_id=s1.id,
        start_time=start + timedelta(days=1),
        end_time=end + timedelta(days=1),
        status=BookingStatus.CONFIRMED,
        idempotency_key=shared_idempotency_key,
    )
    db_session.add(b1_dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    nested.rollback()
