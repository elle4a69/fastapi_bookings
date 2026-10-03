import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)

def create_signature(payload: dict, secret: str) -> str:
    raw_body = json.dumps(payload).encode("utf-8")
    mac = hmac.new(secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"

def test_chatwoot_webhook_invalid_signature(monkeypatch):
    monkeypatch.setattr(settings, "CHATWOOT_WEBHOOK_SECRET", "test_secret")
    payload = {"event": "message_created", "message_type": "incoming"}
    response = client.post("/webhooks/chatwoot", json=payload, headers={"x-chatwoot-signature": "invalid"})
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid webhook signature"

def test_chatwoot_webhook_missing_signature():
    payload = {"event": "message_created", "message_type": "incoming"}
    response = client.post("/webhooks/chatwoot", json=payload)
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid webhook signature"

def test_chatwoot_webhook_event_ignored(monkeypatch):
    monkeypatch.setattr(settings, "CHATWOOT_WEBHOOK_SECRET", "test_secret")
    payload = {"event": "conversation_created"}
    sig = create_signature(payload, "test_secret")
    # need to pass raw body exactly as serialized by testclient
    response = client.post(
        "/webhooks/chatwoot",
        content=json.dumps(payload).encode("utf-8"),
        headers={"x-chatwoot-signature": sig}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "event_ignored"}

def test_chatwoot_webhook_direction_ignored(monkeypatch):
    monkeypatch.setattr(settings, "CHATWOOT_WEBHOOK_SECRET", "test_secret")
    payload = {"event": "message_created", "message_type": "outgoing"}
    sig = create_signature(payload, "test_secret")
    response = client.post(
        "/webhooks/chatwoot",
        content=json.dumps(payload).encode("utf-8"),
        headers={"x-chatwoot-signature": sig}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "direction_ignored"}

def test_chatwoot_webhook_human_handling_assignee(monkeypatch):
    monkeypatch.setattr(settings, "CHATWOOT_WEBHOOK_SECRET", "test_secret")
    payload = {
        "event": "message_created",
        "message_type": "incoming",
        "conversation": {"assignee_id": 1, "status": "open"}
    }
    sig = create_signature(payload, "test_secret")
    response = client.post(
        "/webhooks/chatwoot",
        content=json.dumps(payload).encode("utf-8"),
        headers={"x-chatwoot-signature": sig}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "human_handling"}

def test_chatwoot_webhook_human_handling_resolved(monkeypatch):
    monkeypatch.setattr(settings, "CHATWOOT_WEBHOOK_SECRET", "test_secret")
    payload = {
        "event": "message_created",
        "message_type": "incoming",
        "conversation": {"status": "resolved"}
    }
    sig = create_signature(payload, "test_secret")
    response = client.post(
        "/webhooks/chatwoot",
        content=json.dumps(payload).encode("utf-8"),
        headers={"x-chatwoot-signature": sig}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "human_handling"}

def test_chatwoot_webhook_queued(monkeypatch):
    monkeypatch.setattr(settings, "CHATWOOT_WEBHOOK_SECRET", "test_secret")
    payload = {
        "event": "message_created",
        "message_type": "incoming",
        "conversation": {"status": "open"},
        "account": {"id": 1},
        "inbox": {"id": 2},
        "sender": {"phone_number": "+1234567890"},
        "content": "Hello"
    }
    sig = create_signature(payload, "test_secret")
    response = client.post(
        "/webhooks/chatwoot",
        content=json.dumps(payload).encode("utf-8"),
        headers={"x-chatwoot-signature": sig}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "queued"}
