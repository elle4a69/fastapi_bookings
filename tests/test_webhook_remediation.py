"""Comprehensive test suite for Webhook & Network Security remediation (Work Package C).

Validates:
- TEN-001: Tenant-scoped outbound webhook dispatch (no cross-tenant event leakage)
- TEN-002: Tenant-scoped webhook CRUD operations (Tenant B cannot read/modify/delete Tenant A hooks)
- TEN-003: Webhook signing secret masking (secrets never exposed in list/get/update responses)
- SEC-004: Strict SSRF protection (loopback, private, link-local, cloud metadata, multicast, broadcast rejected)
- DEL-004: Multi-destination fanout idempotency & retry tracking (only failed destinations are retried)
- DEL-003: Unknown event type quarantining
"""

import json
import hmac
import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
import httpx
from fastapi import status

from app.models.tenant import Tenant
from app.models.user import User
from app.models.webhook import WebhookRegistration, WebhookDelivery
from app.models.outbox import OutboxEvent
from app.core.security import get_password_hash
from app.core.network_safety import is_ip_allowed, validate_url_safety, assert_safe_url
from app.services.outbox_worker import process_pending_outbox_events, dispatch_outbound_webhooks


@pytest.fixture
def webhook_test_data(db_session):
    """Seed two isolated tenants and admin users."""
    tenant_a = Tenant(name="Tenant Alpha", subdomain="tenant-alpha", created_at=datetime.now(timezone.utc))
    tenant_b = Tenant(name="Tenant Beta", subdomain="tenant-beta", created_at=datetime.now(timezone.utc))
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()
    db_session.refresh(tenant_a)
    db_session.refresh(tenant_b)

    p_hash = get_password_hash("StrongSecretPassword123!")

    admin_a = User(tenant_id=tenant_a.id, login="admin_a@alpha.com", password_hash=p_hash, role="admin")
    admin_b = User(tenant_id=tenant_b.id, login="admin_b@beta.com", password_hash=p_hash, role="admin")

    db_session.add_all([admin_a, admin_b])
    db_session.commit()
    db_session.refresh(admin_a)
    db_session.refresh(admin_b)

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
    }


def _auth_headers(tenant_subdomain: str, user_id: int, role: str = "admin") -> dict:
    from app.core.security import create_access_token
    token = create_access_token({"sub": str(user_id), "role": role})
    return {
        "X-Tenant": tenant_subdomain,
        "X-Token": token,
    }


# ============================================================================
# TEN-002 & TEN-003: Tenant-Scoped CRUD and Secret Masking Tests
# ============================================================================

def test_tenant_webhook_crud_isolation_and_secret_masking(client, webhook_test_data, db_session):
    """Verify Tenant A and B have completely isolated webhook CRUD and secrets are masked."""
    tenant_a = webhook_test_data["tenant_a"]
    tenant_b = webhook_test_data["tenant_b"]
    admin_a = webhook_test_data["admin_a"]
    admin_b = webhook_test_data["admin_b"]

    headers_a = _auth_headers(tenant_a.subdomain, admin_a.id)
    headers_b = _auth_headers(tenant_b.subdomain, admin_b.id)

    # 1. Tenant A creates a webhook with secret
    create_payload_a = {
        "event": "booking.created",
        "target_url": "https://example.com/webhook-a",
        "secret": "super_secret_alpha_signing_key_12345",
        "is_active": True,
    }
    resp_create_a = client.post("/api/admin/webhooks", json=create_payload_a, headers=headers_a)
    assert resp_create_a.status_code == status.HTTP_201_CREATED
    data_create_a = resp_create_a.json()["data"]
    webhook_a_id = data_create_a["id"]
    assert data_create_a["has_secret"] is True
    assert data_create_a["secret_last4"] == "2345"
    assert data_create_a["secret"] == "super_secret_alpha_signing_key_12345"  # returned once on create

    # 2. Tenant B creates a webhook
    create_payload_b = {
        "event": "booking.created",
        "target_url": "https://example.com/webhook-b",
        "secret": "beta_key_6789",
        "is_active": True,
    }
    resp_create_b = client.post("/api/admin/webhooks", json=create_payload_b, headers=headers_b)
    assert resp_create_b.status_code == status.HTTP_201_CREATED
    webhook_b_id = resp_create_b.json()["data"]["id"]

    # 3. Tenant A lists webhooks -> only sees Webhook A, and secret is NEVER in list
    resp_list_a = client.get("/api/admin/webhooks", headers=headers_a)
    assert resp_list_a.status_code == status.HTTP_200_OK
    items_a = resp_list_a.json()["data"]
    assert len(items_a) == 1
    assert items_a[0]["id"] == webhook_a_id
    assert items_a[0]["target_url"] == "https://example.com/webhook-a"
    assert items_a[0]["has_secret"] is True
    assert items_a[0]["secret_last4"] == "2345"
    assert "secret" not in items_a[0] or items_a[0].get("secret") is None

    # 4. Tenant B lists webhooks -> only sees Webhook B
    resp_list_b = client.get("/api/admin/webhooks", headers=headers_b)
    assert resp_list_b.status_code == status.HTTP_200_OK
    items_b = resp_list_b.json()["data"]
    assert len(items_b) == 1
    assert items_b[0]["id"] == webhook_b_id
    assert items_b[0]["target_url"] == "https://example.com/webhook-b"

    # 5. Tenant B attempts to GET Tenant A's webhook -> 404
    resp_get_cross = client.get(f"/api/admin/webhooks/{webhook_a_id}", headers=headers_b)
    assert resp_get_cross.status_code == status.HTTP_404_NOT_FOUND

    # 6. Tenant A gets own webhook -> 200, secret is masked
    resp_get_a = client.get(f"/api/admin/webhooks/{webhook_a_id}", headers=headers_a)
    assert resp_get_a.status_code == status.HTTP_200_OK
    data_get_a = resp_get_a.json()["data"]
    assert data_get_a["id"] == webhook_a_id
    assert data_get_a["has_secret"] is True
    assert data_get_a["secret_last4"] == "2345"
    assert "secret" not in data_get_a or data_get_a.get("secret") is None

    # 7. Tenant B attempts to UPDATE Tenant A's webhook -> 404
    resp_put_cross = client.put(
        f"/api/admin/webhooks/{webhook_a_id}",
        json={"is_active": False},
        headers=headers_b,
    )
    assert resp_put_cross.status_code == status.HTTP_404_NOT_FOUND

    # 8. Tenant A updates own webhook -> 200, secret is masked in update response
    resp_put_a = client.put(
        f"/api/admin/webhooks/{webhook_a_id}",
        json={"is_active": False},
        headers=headers_a,
    )
    assert resp_put_a.status_code == status.HTTP_200_OK
    assert resp_put_a.json()["data"]["is_active"] is False
    assert "secret" not in resp_put_a.json()["data"] or resp_put_a.json()["data"].get("secret") is None

    # 9. Tenant B attempts to DELETE Tenant A's webhook -> 404
    resp_del_cross = client.delete(f"/api/admin/webhooks/{webhook_a_id}", headers=headers_b)
    assert resp_del_cross.status_code == status.HTTP_404_NOT_FOUND

    # 10. Tenant A deletes own webhook -> 204
    resp_del_a = client.delete(f"/api/admin/webhooks/{webhook_a_id}", headers=headers_a)
    assert resp_del_a.status_code == status.HTTP_204_NO_CONTENT

    # Verification: Webhook A is deleted
    assert db_session.query(WebhookRegistration).filter_by(id=webhook_a_id).first() is None
    # Webhook B is still intact
    assert db_session.query(WebhookRegistration).filter_by(id=webhook_b_id).first() is not None


# ============================================================================
# SEC-004: SSRF Safety Tests
# ============================================================================

@pytest.mark.parametrize("disallowed_url", [
    "http://127.0.0.1/webhook",
    "http://127.0.0.2:8080/callback",
    "http://localhost/webhook",
    "http://localhost:8000/api",
    "http://sub.localhost/webhook",
    "http://169.254.169.254/latest/meta-data/",
    "http://169.254.169.254:80/meta",
    "http://100.100.100.200/latest/meta-data",
    "http://metadata.google.internal/computeMetadata/v1/",
    "http://metadata.internal/meta",
    "http://instance-data/latest/meta-data/",
    "http://10.0.0.1/webhook",
    "http://10.255.255.254/webhook",
    "http://172.16.0.1/webhook",
    "http://172.31.255.255/webhook",
    "http://192.168.1.1/webhook",
    "http://192.168.0.254/webhook",
    "http://0.0.0.0/webhook",
    "http://255.255.255.255/webhook",
    "http://100.64.0.1/webhook",  # CGNAT
    "http://[::1]/webhook",
    "http://[fe80::1]/webhook",
    "http://[fc00::1]/webhook",
    "http://[fd00:ec2::254]/latest/meta-data",  # AWS IPv6 metadata
    "http://[::ffff:127.0.0.1]/webhook",
    "http://[::ffff:10.0.0.1]/webhook",
    "http://[::ffff:169.254.169.254]/webhook",
    "file:///etc/passwd",
    "gopher://127.0.0.1:6379/_test",
    "ftp://example.com/webhook",
])
def test_ssrf_urls_rejected_by_core_validator(disallowed_url):
    """Ensure core network safety utility rejects all internal, loopback, private, and metadata targets."""
    is_safe, reason = validate_url_safety(disallowed_url, resolve_dns=False)
    assert is_safe is False
    assert reason is not None

    with pytest.raises(ValueError):
        assert_safe_url(disallowed_url, resolve_dns=False)


def test_ssrf_registration_rejected_via_api(client, webhook_test_data):
    """Ensure attempts to register private/loopback/cloud metadata targets via API are rejected."""
    tenant_a = webhook_test_data["tenant_a"]
    admin_a = webhook_test_data["admin_a"]
    headers_a = _auth_headers(tenant_a.subdomain, admin_a.id)

    ssrf_targets = [
        "http://127.0.0.1/webhook",
        "http://localhost:8000/hook",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/hook",
        "http://192.168.1.1/hook",
        "http://[::1]/hook",
        "http://[fe80::1]/hook",
    ]

    for target in ssrf_targets:
        resp = client.post(
            "/api/admin/webhooks",
            json={"event": "booking.created", "target_url": target},
            headers=headers_a,
        )
        assert resp.status_code in (422, status.HTTP_400_BAD_REQUEST)


# ============================================================================
# TEN-001: Tenant-Scoped Outbox Webhook Dispatch Tests
# ============================================================================

@pytest.mark.asyncio
async def test_tenant_scoped_outbox_webhook_dispatch(db_session, webhook_test_data):
    """Ensure domain events dispatch only to the owning tenant's webhooks with HMAC signature."""
    tenant_a = webhook_test_data["tenant_a"]
    tenant_b = webhook_test_data["tenant_b"]

    # Register webhook for Tenant A
    hook_a = WebhookRegistration(
        tenant_id=tenant_a.id,
        event="booking.created",
        target_url="https://example.com/tenant-a-webhook",
        secret="whsec_alpha_key_999",
        is_active=True,
    )
    # Register webhook for Tenant B for the exact same event
    hook_b = WebhookRegistration(
        tenant_id=tenant_b.id,
        event="booking.created",
        target_url="https://example.com/tenant-b-webhook",
        secret="whsec_beta_key_888",
        is_active=True,
    )
    db_session.add_all([hook_a, hook_b])
    db_session.commit()
    db_session.refresh(hook_a)
    db_session.refresh(hook_b)

    # Enqueue outbox event belonging strictly to Tenant A
    payload_a = {"booking_id": 101, "client_name": "Alice Smith"}
    event_a = OutboxEvent(
        tenant_id=tenant_a.id,
        type="booking.created",
        payload=json.dumps(payload_a),
        status="PENDING",
    )
    db_session.add(event_a)
    db_session.commit()
    db_session.refresh(event_a)

    dispatched_calls = []

    # Mock httpx.AsyncClient.post
    async def mock_post(self, url, *args, **kwargs):
        content = kwargs.get("content")
        headers = kwargs.get("headers", {})
        dispatched_calls.append({"url": url, "content": content, "headers": headers})
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    with patch("httpx.AsyncClient.post", new=mock_post), \
         patch("app.core.network_safety.validate_url_safety", return_value=(True, None)):
        await process_pending_outbox_events(db=db_session)

    # Verify event status is PROCESSED
    db_session.refresh(event_a)
    assert event_a.status == "PROCESSED"
    assert event_a.processed is True

    # Check dispatched calls: ONLY Tenant A's webhook was called!
    assert len(dispatched_calls) == 1
    call = dispatched_calls[0]
    assert call["url"] == "https://example.com/tenant-a-webhook"

    # Verify HMAC-SHA256 signature format and correctness
    sig_header = call["headers"].get("X-Webhook-Signature")
    ts_header = call["headers"].get("X-Webhook-Timestamp")
    assert sig_header is not None
    assert ts_header is not None
    assert sig_header.startswith(f"t={ts_header},v1=")

    expected_sig = hmac.new(
        b"whsec_alpha_key_999",
        f"{ts_header}.{call['content'].decode('utf-8')}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert sig_header == f"t={ts_header},v1={expected_sig}"

    # Verify WebhookDelivery record exists for Tenant A's webhook
    delivery = db_session.query(WebhookDelivery).filter_by(outbox_event_id=event_a.id).first()
    assert delivery is not None
    assert delivery.tenant_id == tenant_a.id
    assert delivery.webhook_id == hook_a.id
    assert delivery.status == "SUCCESS"


@pytest.mark.asyncio
async def test_null_tenant_outbox_event_quarantined(db_session):
    """Ensure domain webhook events missing tenant_id are quarantined and never broadcast."""
    legacy_event = OutboxEvent(
        tenant_id=None,
        type="booking.created",
        payload=json.dumps({"booking_id": 999}),
        status="PENDING",
    )
    db_session.add(legacy_event)
    db_session.commit()
    db_session.refresh(legacy_event)

    dispatched = []
    async def mock_post(self, url, *args, **kwargs):
        dispatched.append(url)
        return MagicMock(status_code=200)

    with patch("httpx.AsyncClient.post", new=mock_post):
        await process_pending_outbox_events(db=db_session)

    db_session.refresh(legacy_event)
    assert legacy_event.status == "QUARANTINED"
    assert "missing required tenant_id" in (legacy_event.error_log or "")
    assert len(dispatched) == 0


# ============================================================================
# DEL-004: Partial Fanout & Retry Idempotency Tests
# ============================================================================

@pytest.mark.asyncio
async def test_partial_fanout_retry_contacts_only_failed_destination(db_session, webhook_test_data):
    """Ensure when one destination fails and one succeeds, retry only contacts the failed destination."""
    tenant_a = webhook_test_data["tenant_a"]

    # Register two webhooks for Tenant A
    hook_1 = WebhookRegistration(
        tenant_id=tenant_a.id,
        event="booking.created",
        target_url="https://example.com/dest-1-success",
        is_active=True,
    )
    hook_2 = WebhookRegistration(
        tenant_id=tenant_a.id,
        event="booking.created",
        target_url="https://example.com/dest-2-fail-then-succeed",
        is_active=True,
    )
    db_session.add_all([hook_1, hook_2])
    db_session.commit()
    db_session.refresh(hook_1)
    db_session.refresh(hook_2)

    event = OutboxEvent(
        tenant_id=tenant_a.id,
        type="booking.created",
        payload=json.dumps({"booking_id": 202}),
        status="PENDING",
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    attempt_1_calls = []

    # Attempt 1: hook_1 succeeds, hook_2 fails with 500 error
    async def mock_post_attempt_1(self, url, *args, **kwargs):
        attempt_1_calls.append(url)
        mock_resp = MagicMock()
        if "dest-1-success" in url:
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            return mock_resp
        else:
            mock_resp.status_code = 500
            http_err = httpx.HTTPStatusError("500 Internal Server Error", request=MagicMock(), response=mock_resp)
            mock_resp.raise_for_status = MagicMock(side_effect=http_err)
            raise http_err

    with patch("httpx.AsyncClient.post", new=mock_post_attempt_1), \
         patch("app.core.network_safety.validate_url_safety", return_value=(True, None)):
        await process_pending_outbox_events(db=db_session)

    # Check attempt 1 results:
    # Both destinations attempted
    assert len(attempt_1_calls) == 2
    assert "https://example.com/dest-1-success" in attempt_1_calls
    assert "https://example.com/dest-2-fail-then-succeed" in attempt_1_calls

    db_session.refresh(event)
    assert event.status == "FAILED"
    assert event.retry_count == 1

    deliveries_1 = {d.webhook_id: d for d in db_session.query(WebhookDelivery).filter_by(outbox_event_id=event.id).all()}
    assert deliveries_1[hook_1.id].status == "SUCCESS"
    assert deliveries_1[hook_2.id].status == "FAILED"
    assert deliveries_1[hook_2.id].attempt_count == 1

    # Attempt 2 (Retry): hook_2 now succeeds. hook_1 MUST NOT be called!
    attempt_2_calls = []

    async def mock_post_attempt_2(self, url, *args, **kwargs):
        attempt_2_calls.append(url)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    with patch("httpx.AsyncClient.post", new=mock_post_attempt_2), \
         patch("app.core.network_safety.validate_url_safety", return_value=(True, None)):
        await process_pending_outbox_events(db=db_session)

    # Check attempt 2 results:
    # ONLY destination 2 was called! Destination 1 was safely skipped!
    assert attempt_2_calls == ["https://example.com/dest-2-fail-then-succeed"]

    db_session.refresh(event)
    assert event.status == "PROCESSED"

    deliveries_2 = {d.webhook_id: d for d in db_session.query(WebhookDelivery).filter_by(outbox_event_id=event.id).all()}
    assert deliveries_2[hook_1.id].status == "SUCCESS"
    assert deliveries_2[hook_2.id].status == "SUCCESS"
    assert deliveries_2[hook_2.id].attempt_count == 2


# ============================================================================
# DEL-003: Unknown Event Type Quarantining Tests
# ============================================================================

@pytest.mark.asyncio
async def test_unknown_outbox_event_quarantined(db_session, webhook_test_data):
    """Ensure unknown outbox event types are quarantined instead of marked processed."""
    tenant_a = webhook_test_data["tenant_a"]

    unknown_event = OutboxEvent(
        tenant_id=tenant_a.id,
        type="unknown.event.lifecycle",
        payload=json.dumps({"some_data": 123}),
        status="PENDING",
    )
    db_session.add(unknown_event)
    db_session.commit()
    db_session.refresh(unknown_event)

    await process_pending_outbox_events(db=db_session)

    db_session.refresh(unknown_event)
    assert unknown_event.status == "QUARANTINED"
    assert "Unknown outbox event type" in (unknown_event.error_log or "")
