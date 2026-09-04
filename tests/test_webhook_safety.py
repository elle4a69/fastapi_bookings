"""Regression coverage for tenant-safe, non-leaking outbound webhooks."""

import asyncio
import hashlib
import hmac
import socket
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.security import create_access_token
from app.models.outbox import OutboxEvent
from app.models.tenant import Tenant
from app.models.user import User
from app.models.webhook import WebhookDelivery, WebhookRegistration
from app.models import webhook as webhook_model
from app.schemas.webhook import WebhookCreate, WebhookUpdate
from app.services import outbox_worker
from app.services.outbox_service import create_outbox_event


SECRET_A = "a" * 32
SECRET_B = "b" * 32


def _admin_headers(db_session, subdomain: str, login: str):
    tenant = Tenant(name=f"{subdomain} tenant", subdomain=subdomain)
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, login=login, password_hash="test", role="owner")
    db_session.add(user)
    db_session.commit()
    return tenant, {"X-Tenant": subdomain, "X-Token": create_access_token({"sub": str(user.id)})}


def test_webhook_crud_is_tenant_scoped_and_secret_is_write_only(client, db_session):
    tenant_a, headers_a = _admin_headers(db_session, "hooks-a", "hooks_a_owner")
    tenant_b, _ = _admin_headers(db_session, "hooks-b", "hooks_b_owner")
    other = WebhookRegistration(
        tenant_id=tenant_b.id,
        event="booking.created",
        target_url="https://8.8.8.8/hooks-b",
        secret=SECRET_B,
    )
    db_session.add(other)
    db_session.commit()

    created = client.post("/api/admin/webhooks", headers=headers_a, json={
        "event": "booking.created", "target_url": "https://8.8.8.8/hooks-a", "secret": SECRET_A,
    })
    assert created.status_code == 201
    assert SECRET_A not in created.text
    body = created.json()["data"]
    assert body["has_secret"] is True and "secret" not in body

    listed = client.get("/api/admin/webhooks", headers=headers_a)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["data"]] == [body["id"]]
    assert client.put(f"/api/admin/webhooks/{other.id}", headers=headers_a, json={"is_active": False}).status_code == 404
    assert client.delete(f"/api/admin/webhooks/{other.id}", headers=headers_a).status_code == 404

    updated = client.put(f"/api/admin/webhooks/{body['id']}", headers=headers_a, json={"is_active": False})
    assert updated.status_code == 200 and "secret" not in updated.json()["data"]
    hook = db_session.query(WebhookRegistration).filter(WebhookRegistration.id == body["id"]).one()
    assert hook.secret == SECRET_A
    with pytest.raises(ValidationError):
        WebhookUpdate(secret="")
    assert client.post(f"/api/admin/webhooks/{body['id']}/rotate-secret", headers=headers_a, json={"secret": SECRET_B}).status_code == 200
    db_session.refresh(hook)
    assert hook.secret == SECRET_B
    with pytest.raises(ValidationError):
        WebhookCreate(event="booking.created", target_url="https://127.0.0.1/hook", secret=SECRET_B)


class _FakeResponse:
    def __init__(self, status=200):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError("http failure")


class _FakeSession:
    calls = []
    response_status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _FakeResponse(self.response_status)


def test_event_snapshots_tenant_recipients_and_delivery_is_deduplicated(db_session, monkeypatch):
    tenant_a, _ = _admin_headers(db_session, "delivery-a", "delivery_a_owner")
    tenant_b, _ = _admin_headers(db_session, "delivery-b", "delivery_b_owner")
    db_session.add_all([
        WebhookRegistration(tenant_id=tenant_a.id, event="booking.created", target_url="https://8.8.8.8/a", secret=SECRET_A),
        WebhookRegistration(tenant_id=tenant_b.id, event="booking.created", target_url="https://8.8.8.8/b", secret=SECRET_B),
    ])
    db_session.commit()
    event = create_outbox_event(db_session, "booking.created", {"booking": 7}, tenant_id=tenant_a.id)
    db_session.commit()
    db_session.refresh(event)
    deliveries = db_session.query(WebhookDelivery).filter(WebhookDelivery.outbox_event_id == event.id).all()
    assert len(deliveries) == 1 and deliveries[0].tenant_id == tenant_a.id
    assert SECRET_A not in deliveries[0].encrypted_signing_secret

    _FakeSession.calls = []
    monkeypatch.setattr(outbox_worker.aiohttp, "TCPConnector", lambda **_kwargs: object())
    monkeypatch.setattr(outbox_worker.aiohttp, "ClientSession", lambda **_kwargs: _FakeSession())
    monkeypatch.setattr(outbox_worker, "validate_webhook_target_url", lambda _url: _url)
    asyncio.run(outbox_worker.dispatch_outbound_webhooks(db_session, event=event, payload={"booking": 7}))
    asyncio.run(outbox_worker.dispatch_outbound_webhooks(db_session, event=event, payload={"booking": 7}))
    assert len(_FakeSession.calls) == 1
    url, request = _FakeSession.calls[0]
    assert url == "https://8.8.8.8/a" and request["allow_redirects"] is False
    expected = hmac.new(SECRET_A.encode(), request["data"].encode(), hashlib.sha256).hexdigest()
    assert request["headers"]["X-Webhook-Signature"] == f"v1={expected}"
    assert '"version":"v1"' in request["data"]
    assert db_session.query(WebhookDelivery).one().status == "PROCESSED"


def test_resolver_rejects_mixed_or_rebound_private_answers(monkeypatch):
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: answers)
    with pytest.raises(outbox_worker.WebhookDeliveryError):
        asyncio.run(outbox_worker.PublicAddressResolver().resolve("rebound.example", 443))


def test_tenantless_unsnapshotted_domain_event_is_quarantined(db_session):
    event = OutboxEvent(type="booking.created", payload="{}", status="PENDING", processed=False)
    db_session.add(event)
    db_session.commit()
    asyncio.run(outbox_worker.process_pending_outbox_events(db_session))
    db_session.refresh(event)
    assert event.status == "QUARANTINED"
    assert event.error_log == "WEBHOOK_TENANT_CONTEXT_MISSING"


def test_claim_is_atomic_and_snapshot_survives_registration_changes(db_session, monkeypatch):
    tenant, _ = _admin_headers(db_session, "terminal-a", "terminal_a_owner")
    hook = WebhookRegistration(tenant_id=tenant.id, event="booking.created", target_url="https://8.8.8.8/a", secret=SECRET_A)
    db_session.add(hook)
    db_session.commit()
    event = create_outbox_event(db_session, "booking.created", {}, tenant_id=tenant.id)
    db_session.commit()
    delivery = db_session.query(WebhookDelivery).filter(WebhookDelivery.outbox_event_id == event.id).one()
    assert outbox_worker._claim_webhook_delivery(db_session, delivery.id) is not None
    assert outbox_worker._claim_webhook_delivery(db_session, delivery.id) is None

    db_session.query(WebhookDelivery).filter(WebhookDelivery.id == delivery.id).update({
        WebhookDelivery.status: "PENDING",
        WebhookDelivery.lease_token: None,
        WebhookDelivery.lease_expires_at: None,
    }, synchronize_session=False)
    db_session.expire_all()
    # The event-time encrypted recipient snapshot must remain independent of
    # subsequent endpoint rotations, disablement, and deletion.
    hook.secret = SECRET_B
    hook.is_active = False
    db_session.delete(hook)
    db_session.commit()
    _FakeSession.calls = []
    monkeypatch.setattr(outbox_worker.aiohttp, "TCPConnector", lambda **_kwargs: object())
    monkeypatch.setattr(outbox_worker.aiohttp, "ClientSession", lambda **_kwargs: _FakeSession())
    monkeypatch.setattr(outbox_worker, "validate_webhook_target_url", lambda _url: _url)
    asyncio.run(outbox_worker.dispatch_outbound_webhooks(db_session, event=event, payload={}))
    db_session.refresh(delivery)
    assert delivery.status == "PROCESSED"
    request = _FakeSession.calls[0][1]
    expected = hmac.new(SECRET_A.encode(), request["data"].encode(), hashlib.sha256).hexdigest()
    assert request["headers"]["X-Webhook-Signature"] == f"v1={expected}"


def test_failure_uses_generic_error_and_retry_state_without_logging_secrets(db_session, monkeypatch, caplog):
    tenant, _ = _admin_headers(db_session, "failure-a", "failure_a_owner")
    target = "https://8.8.8.8/private-path"
    hook = WebhookRegistration(tenant_id=tenant.id, event="booking.created", target_url=target, secret=SECRET_A)
    db_session.add(hook)
    db_session.commit()
    event = create_outbox_event(db_session, "booking.created", {"sensitive": "payload"}, tenant_id=tenant.id)
    db_session.commit()
    _FakeSession.response_status = 500
    monkeypatch.setattr(outbox_worker.aiohttp, "TCPConnector", lambda **_kwargs: object())
    monkeypatch.setattr(outbox_worker.aiohttp, "ClientSession", lambda **_kwargs: _FakeSession())
    monkeypatch.setattr(outbox_worker, "validate_webhook_target_url", lambda _url: _url)
    with pytest.raises(outbox_worker.WebhookDeliveryError):
        asyncio.run(outbox_worker.dispatch_outbound_webhooks(db_session, event=event, payload={"sensitive": "payload"}))
    delivery = db_session.query(WebhookDelivery).filter(WebhookDelivery.outbox_event_id == event.id).one()
    assert delivery.status == "FAILED" and delivery.error_code == "WEBHOOK_DELIVERY_FAILED"
    assert delivery.next_attempt_at is not None
    assert SECRET_A not in caplog.text and target not in caplog.text and "payload" not in caplog.text
    _FakeSession.response_status = 200


def test_remediation_migration_does_not_copy_plaintext_signing_secret():
    migration = Path("alembic/versions/f2c0b8d9e7a1_add_webhook_delivery_safety.py").read_text(encoding="utf-8")
    assert 'branch_labels = ("webhook_safety_remediation",)' in migration
    assert 'sa.Column("encrypted_signing_secret"' in migration
    assert 'sa.Column("signing_secret"' not in migration


def test_snapshot_cipher_is_domain_separated_and_fails_closed_in_production(monkeypatch):
    encrypted = webhook_model.encrypt_webhook_secret(SECRET_A)
    assert SECRET_A not in encrypted
    assert webhook_model.decrypt_webhook_secret(encrypted) == SECRET_A
    monkeypatch.setattr(webhook_model.settings, "APP_ENV", "production")
    monkeypatch.setattr(webhook_model.settings, "SECRET_KEY", "changeme")
    with pytest.raises(RuntimeError):
        webhook_model.encrypt_webhook_secret(SECRET_A)


def test_legacy_active_null_secret_is_skipped_without_rolling_back_event(db_session):
    tenant, _ = _admin_headers(db_session, "legacy-secret", "legacy_secret_owner")
    db_session.add(WebhookRegistration(
        tenant_id=tenant.id,
        event="booking.created",
        target_url="https://8.8.8.8/legacy",
        secret=None,
        is_active=True,
    ))
    db_session.commit()
    event = create_outbox_event(db_session, "booking.created", {"booking": 9}, tenant_id=tenant.id)
    db_session.commit()
    assert event.id is not None and event.webhook_snapshot_at is not None
    assert db_session.query(WebhookDelivery).filter(WebhookDelivery.outbox_event_id == event.id).count() == 0
