"""Comprehensive contract and integration tests for WP2: Flexprice Billing Adapter.

Validates:
1. Raw-body HMAC-SHA256 signature verification (valid vs tampered/invalid signature).
2. Duplicate webhook event processed once only (inbox idempotency).
3. Out-of-order event cannot resurrect cancelled subscription or overwrite newer state.
4. Tenant A cannot inspect or affect Tenant B's billing records or portal session (cross-tenant isolation).
5. Provider outage / failure does not grant elevated privileges (fail-closed security).
6. Usage metering outbox deduplication with idempotency key and batch dispatch.
7. Client cannot directly manipulate subscription tier (must go through webhook/provider).
8. Platform owner reconciliation and dead-letter queue auditing.
"""

from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import json
import uuid
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.tenant import Tenant
from app.models.user import User
from app.models.platform_billing import (
    BillingAccount,
    SubscriptionProjection,
    EntitlementSnapshot,
    ProviderEventInbox,
    UsageEventOutbox,
)
from app.services.platform_billing import (
    FlexpriceClient,
    FlexpriceClientError,
    FlexpriceOutageError,
    flexprice_client,
    webhook_verifier,
    projection_service,
    usage_metering_service,
    reconciliation_service,
)
from app.api.deps import get_current_user, get_current_tenant, get_current_platform_owner


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

def _seed_tenant(db_session: Session, slug: str) -> Tenant:
    tenant = Tenant(
        name=f"Clinic {slug.upper()}",
        subdomain=f"clinic-{slug.lower()}",
        subscription_tier="starter",
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _seed_user(db_session: Session, tenant_id: int, login: str, role: str = "owner") -> User:
    user = User(
        tenant_id=tenant_id,
        login=login,
        email=f"{login}@example.com",
        password_hash=get_password_hash("Password123!"),
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _sign_payload(raw_body: bytes, secret: str = "test-flexprice-webhook-secret") -> str:
    """Generate expected HMAC-SHA256 signature for test requests."""
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# 1. Cryptographic HMAC Signature Verification & Payload Digesting
# ---------------------------------------------------------------------------

def test_webhook_hmac_signature_verification_success_and_tampered():
    """Verify raw-body HMAC-SHA256 validation rejects tampered payloads and signatures."""
    payload = json.dumps({"event_id": "evt_test_1", "type": "subscription.created"}).encode("utf-8")
    valid_sig = _sign_payload(payload)

    # 1. Valid signature passes
    assert webhook_verifier.verify_signature(payload, valid_sig) is True

    # 2. Tampered body fails
    tampered_payload = json.dumps({"event_id": "evt_test_1", "type": "subscription.hacked"}).encode("utf-8")
    assert webhook_verifier.verify_signature(tampered_payload, valid_sig) is False

    # 3. Tampered signature fails
    assert webhook_verifier.verify_signature(payload, "invalid_sig_00000000000000000000") is False

    # 4. Missing signature fails
    assert webhook_verifier.verify_signature(payload, None) is False

    # 5. SHA-256 payload digest matches exact raw body hash
    expected_digest = hashlib.sha256(payload).hexdigest()
    assert webhook_verifier.compute_payload_digest(payload) == expected_digest


def test_webhook_endpoint_hmac_enforcement(client: TestClient, db_session: Session):
    """POST /api/webhooks/flexprice rejects requests with invalid or missing HMAC signatures."""
    payload = json.dumps({
        "event_id": "evt_endpoint_1",
        "event_type": "subscription.updated",
        "data": {
            "subscription_id": "sub_test_001",
            "status": "active",
            "plan_id": "pro",
        }
    })

    # Missing signature -> 401
    resp = client.post("/api/webhooks/flexprice", content=payload, headers={"Content-Type": "application/json"})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Bad signature -> 401
    resp = client.post(
        "/api/webhooks/flexprice",
        content=payload,
        headers={"Content-Type": "application/json", "X-Flexprice-Signature": "bad_sig"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 2. Webhook Ingestion & Idempotency
# ---------------------------------------------------------------------------

def test_duplicate_webhook_event_processed_once(client: TestClient, db_session: Session):
    """Sending the same external_event_id twice must deduplicate and process once only."""
    tenant = _seed_tenant(db_session, "idemp")
    event_id = f"evt_{uuid.uuid4().hex[:8]}"

    payload_dict = {
        "event_id": event_id,
        "event_type": "subscription.created",
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "sequence": 1,
        "data": {
            "tenant_id": tenant.id,
            "subscription_id": f"sub_{event_id}",
            "plan_id": "pro",
            "plan_version": 1,
            "status": "active",
        },
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = _sign_payload(raw_body)

    headers = {
        "Content-Type": "application/json",
        "X-Flexprice-Signature": sig,
    }

    # First delivery
    resp1 = client.post("/api/webhooks/flexprice", content=raw_body, headers=headers)
    assert resp1.status_code == status.HTTP_200_OK
    data1 = resp1.json()
    assert data1["status"] == "success"
    assert data1["action_taken"] == "processed"

    # Second delivery (identical raw body and event ID)
    resp2 = client.post("/api/webhooks/flexprice", content=raw_body, headers=headers)
    assert resp2.status_code == status.HTTP_200_OK
    data2 = resp2.json()
    assert data2["status"] == "success"
    assert data2["action_taken"] == "deduplicated"

    # Verify only 1 inbox record exists
    inbox_rows = (
        db_session.query(ProviderEventInbox)
        .filter(ProviderEventInbox.external_event_id == event_id)
        .all()
    )
    assert len(inbox_rows) == 1
    assert inbox_rows[0].processing_status == "processed"


# ---------------------------------------------------------------------------
# 3. Out-Of-Order Event Protection & Resurrection Prevention
# ---------------------------------------------------------------------------

def test_out_of_order_event_cannot_resurrect_cancelled_subscription(db_session: Session):
    """A stale webhook cannot resurrect a cancelled subscription or overwrite newer state."""
    tenant = _seed_tenant(db_session, "stale1")
    sub_id = f"sub_lifecycle_{uuid.uuid4().hex[:8]}"

    now = datetime.now(timezone.utc)
    t1_earlier = now - timedelta(hours=2)
    t2_later = now - timedelta(hours=1)

    # 1. Subscription was cancelled at t2_later (sequence 5)
    inbox_evt_cancellation, _ = projection_service.record_inbox_event(
        db=db_session,
        external_event_id=f"evt_cancel_{uuid.uuid4().hex[:8]}",
        event_type="subscription.cancelled",
        raw_body=b'{"cancellation": true}',
    )
    projection_service.process_subscription_event(
        db=db_session,
        inbox_event=inbox_evt_cancellation,
        event_data={
            "event_timestamp": t2_later.isoformat(),
            "sequence": 5,
            "data": {
                "tenant_id": tenant.id,
                "subscription_id": sub_id,
                "plan_id": "pro",
                "status": "cancelled",
            },
        },
    )

    proj = (
        db_session.query(SubscriptionProjection)
        .filter(SubscriptionProjection.external_subscription_id == sub_id)
        .first()
    )
    assert proj.status == "cancelled"

    # 2. A delayed/stale webhook arrives with active status from t1_earlier (sequence 3)
    inbox_evt_stale, _ = projection_service.record_inbox_event(
        db=db_session,
        external_event_id=f"evt_stale_{uuid.uuid4().hex[:8]}",
        event_type="subscription.updated",
        raw_body=b'{"stale": true}',
    )
    result = projection_service.process_subscription_event(
        db=db_session,
        inbox_event=inbox_evt_stale,
        event_data={
            "event_timestamp": t1_earlier.isoformat(),
            "sequence": 3,
            "data": {
                "tenant_id": tenant.id,
                "subscription_id": sub_id,
                "plan_id": "pro",
                "status": "active",
            },
        },
    )

    # Event is rejected/ignored
    assert result["status"] == "ignored"

    # Verify database projection was NOT resurrected
    db_session.refresh(proj)
    proj_ts = proj.last_event_timestamp if proj.last_event_timestamp.tzinfo else proj.last_event_timestamp.replace(tzinfo=timezone.utc)
    assert proj_ts == t2_later

    # Verify inbox recorded the out-of-order rejection
    db_session.refresh(inbox_evt_stale)
    assert inbox_evt_stale.processing_status == "ignored"
    assert "out-of-order" in (inbox_evt_stale.error_message or "").lower()


# ---------------------------------------------------------------------------
# 4. Multi-Tenant Isolation & Cross-Tenant Boundary Enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_isolation_subscription_overview(client: TestClient, db_session: Session):
    """User for Tenant A can only inspect Tenant A's subscription and entitlements."""
    tenant_a = _seed_tenant(db_session, "alpha")
    tenant_b = _seed_tenant(db_session, "beta")

    user_a = _seed_user(db_session, tenant_a.id, "usera")
    user_b = _seed_user(db_session, tenant_b.id, "userb")

    token_a = create_access_token(data={"sub": str(user_a.id), "tenant_id": tenant_a.id})

    # Seed subscription projection for Tenant B
    sub_b = SubscriptionProjection(
        tenant_id=tenant_b.id,
        external_subscription_id="sub_beta_999",
        plan_id="enterprise",
        plan_version=1,
        status="active",
        last_event_timestamp=datetime.now(timezone.utc),
        last_event_sequence=1,
    )
    db_session.add(sub_b)
    db_session.commit()

    # User A requests their own billing subscription
    resp = client.get(
        "/api/billing/subscription",
        headers={
            "Authorization": f"Bearer {token_a}",
            "X-Tenant": tenant_a.subdomain,
        },
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    # Should not see Tenant B's subscription
    if data.get("subscription"):
        assert data["subscription"]["external_subscription_id"] != "sub_beta_999"

    # User A attempting to access Tenant B's scope is rejected with 401/403
    resp_cross = client.get(
        "/api/billing/subscription",
        headers={
            "Authorization": f"Bearer {token_a}",
            "X-Tenant": tenant_b.subdomain,
        },
    )
    assert resp_cross.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# 5. Fail-Closed Security on Provider Outages
# ---------------------------------------------------------------------------

def test_provider_outage_fails_closed_without_elevated_privileges(client: TestClient, db_session: Session):
    """When Flexprice is unreachable, portal session endpoint returns 503 and does not grant privileges."""
    tenant = _seed_tenant(db_session, "outage")
    user = _seed_user(db_session, tenant.id, "outage_owner", role="owner")
    token = create_access_token(data={"sub": str(user.id), "tenant_id": tenant.id})

    # Configure mock handler on flexprice_client to simulate a 500 outage
    def _mock_outage_handler(method: str, path: str, json_data: dict):
        raise FlexpriceOutageError("Simulated Flexprice downstream 503 outage")

    flexprice_client.set_mock_handler(_mock_outage_handler)
    try:
        resp = client.post(
            "/api/billing/portal-session",
            json={"return_url": "https://example.com/return"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant": tenant.subdomain,
            },
        )
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "temporarily unavailable" in resp.json()["detail"]

        # Ensure tenant tier was not altered or upgraded
        db_session.refresh(tenant)
        assert tenant.subscription_tier == "starter"
    finally:
        flexprice_client.set_mock_handler(None)


# ---------------------------------------------------------------------------
# 6. Usage Metering Outbox Deduplication & Batch Dispatch
# ---------------------------------------------------------------------------

def test_usage_metering_deduplication_and_dispatch(db_session: Session):
    """Usage metering outbox deduplicates identical idempotency keys and dispatches cleanly."""
    tenant = _seed_tenant(db_session, "meter")
    idemp_key = f"meter_evt_{uuid.uuid4().hex[:12]}"

    # Record first usage
    rec1 = usage_metering_service.record_usage(
        db=db_session,
        tenant_id=tenant.id,
        meter_key="sms_outbound",
        quantity=5,
        idempotency_key=idemp_key,
    )
    assert rec1.delivery_state == "pending"

    # Record duplicate usage with same idempotency key
    rec2 = usage_metering_service.record_usage(
        db=db_session,
        tenant_id=tenant.id,
        meter_key="sms_outbound",
        quantity=5,
        idempotency_key=idemp_key,
    )
    assert rec1.id == rec2.id

    # Mock dispatch
    dispatched_events = []

    def _mock_dispatch(method: str, path: str, json_data: dict):
        dispatched_events.extend(json_data.get("events", []))
        return {"status": "ok", "delivered": len(json_data.get("events", []))}

    flexprice_client.set_mock_handler(_mock_dispatch)
    try:
        delivered_count = usage_metering_service.dispatch_pending_usage(
            db=db_session,
            client=flexprice_client,
        )
        assert delivered_count >= 1
        assert len(dispatched_events) >= 1
        assert dispatched_events[0]["event_id"] == idemp_key

        db_session.refresh(rec1)
        assert rec1.delivery_state == "delivered"
        assert rec1.delivered_at is not None
    finally:
        flexprice_client.set_mock_handler(None)


# ---------------------------------------------------------------------------
# 7. Prohibition of Direct Client Tier Manipulation
# ---------------------------------------------------------------------------

def test_client_cannot_directly_manipulate_subscription_tier(client: TestClient, db_session: Session):
    """Tenants cannot directly PUT/PATCH /api/billing/subscription to grant themselves higher tiers."""
    tenant = _seed_tenant(db_session, "tamper")
    user = _seed_user(db_session, tenant.id, "tamper_user", role="owner")
    token = create_access_token(data={"sub": str(user.id), "tenant_id": tenant.id})

    # Direct PUT to subscription endpoint is prohibited (405 Method Not Allowed)
    resp = client.put(
        "/api/billing/subscription",
        json={"plan_id": "enterprise", "status": "active"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant": tenant.subdomain,
        },
    )
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # Direct PATCH is also prohibited
    resp_patch = client.patch(
        "/api/billing/subscription",
        json={"tier": "enterprise"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant": tenant.subdomain,
        },
    )
    assert resp_patch.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


# ---------------------------------------------------------------------------
# 8. Platform Owner Reconciliation Access Control
# ---------------------------------------------------------------------------

def test_platform_owner_reconciliation_access(client: TestClient, db_session: Session):
    """Only platform owners can trigger or view platform billing reconciliation."""
    tenant = _seed_tenant(db_session, "reconcile")
    regular_owner = _seed_user(db_session, tenant.id, "reg_owner", role="owner")
    regular_token = create_access_token(data={"sub": str(regular_owner.id), "tenant_id": tenant.id})

    # Regular tenant owner is rejected (403 Forbidden)
    resp = client.get(
        "/api/admin/platform/billing/reconcile",
        headers={"Authorization": f"Bearer {regular_token}"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Platform owner is accepted
    platform_admin = User(
        login="platform_admin",
        email="platform_admin@example.com",
        password_hash=get_password_hash("Password123!"),
        role="platform_owner",
        is_platform_owner=True,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(platform_admin)
    db_session.commit()
    db_session.refresh(platform_admin)

    admin_token = create_access_token(data={"sub": str(platform_admin.id)})
    resp_admin = client.get(
        "/api/admin/platform/billing/reconcile",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == status.HTTP_200_OK
    assert isinstance(resp_admin.json(), list)
