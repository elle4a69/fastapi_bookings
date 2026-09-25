"""Tests for Chatwoot AgentBot webhook and handoff service."""

import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.services.messaging.chatwoot_handoff import handoff_to_human, send_bot_message
from app.api.routers.chatwoot_agentbot import requires_human_handoff


@pytest.mark.asyncio
async def test_handoff_to_human_with_note():
    """Test handoff_to_human patches conversation status and sends private note."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        calls.append({
            "method": request.method,
            "path": request.url.path,
            "json": json.loads(request.content),
            "headers": dict(request.headers),
        })
        if request.method == "PATCH":
            return httpx.Response(200, json={"id": 42, "status": "open"})
        elif request.method == "POST":
            return httpx.Response(200, json={"id": 101, "private": True})
        return httpx.Response(400)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await handoff_to_human(
            chatwoot_base_url="https://app.chatwoot.com",
            api_access_token="fake_token",
            account_id=1,
            conversation_id=42,
            note="Customer requested human support",
            client=client,
        )

        assert result["status"] == "success"
        assert result["conversation_id"] == 42
        assert result["conversation_status"] == "open"
        assert result["note_sent"] is True
        assert len(calls) == 2

        # Check PATCH request
        assert calls[0]["method"] == "PATCH"
        assert "/accounts/1/conversations/42" in calls[0]["path"]
        assert calls[0]["json"] == {"status": "open"}
        assert calls[0]["headers"]["api_access_token"] == "fake_token"

        # Check POST note request
        assert calls[1]["method"] == "POST"
        assert "/accounts/1/conversations/42/messages" in calls[1]["path"]
        assert calls[1]["json"]["private"] is True
        assert calls[1]["json"]["content"] == "Customer requested human support"
        assert calls[1]["json"]["message_type"] == "outgoing"


@pytest.mark.asyncio
async def test_handoff_to_human_without_note():
    """Test handoff_to_human without note only executes PATCH."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        calls.append(request.method)
        return httpx.Response(200, json={"id": 42, "status": "open"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await handoff_to_human(
            chatwoot_base_url="https://app.chatwoot.com",
            api_access_token="fake_token",
            account_id=1,
            conversation_id=42,
            note=None,
            client=client,
        )

        assert result["status"] == "success"
        assert result["note_sent"] is False
        assert len(calls) == 1
        assert calls[0] == "PATCH"


@pytest.mark.asyncio
async def test_send_bot_message():
    """Test sending an outbound bot message."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        calls.append({
            "path": request.url.path,
            "json": json.loads(request.content),
        })
        return httpx.Response(200, json={"id": 202, "content": "Welcome!"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await send_bot_message(
            chatwoot_base_url="https://app.chatwoot.com",
            api_access_token="fake_token",
            account_id=1,
            conversation_id=42,
            content="Welcome to our booking service!",
            client=client,
        )

        assert result["id"] == 202
        assert len(calls) == 1
        assert calls[0]["json"]["content"] == "Welcome to our booking service!"
        assert calls[0]["json"]["message_type"] == "outgoing"


def test_requires_human_handoff_detection():
    """Test regex pattern detection for human handoff."""
    assert requires_human_handoff("I want to speak with a human please") is True
    assert requires_human_handoff("Can I talk to an agent?") is True
    assert requires_human_handoff("Please transfer me to a real person") is True
    assert requires_human_handoff("I need live support") is True
    assert requires_human_handoff("Please escalate this issue") is True
    assert requires_human_handoff("Connect me with customer service") is True

    # Automated agent booking queries should NOT trigger handoff
    assert requires_human_handoff("What times are available for haircut?") is False
    assert requires_human_handoff("Book a 60-minute massage on Friday at 3pm") is False
    assert requires_human_handoff("How much does an out-call visit cost?") is False
    assert requires_human_handoff("") is False
    assert requires_human_handoff(None) is False


def test_chatwoot_agentbot_webhook_ignored_events():
    """Test that non-message_created or staff messages are ignored."""
    client = TestClient(app)

    # 1. Non-message_created event
    resp = client.post(
        "/api/v1/chatwoot/webhook",
        json={
            "event": "conversation_status_changed",
            "conversation": {"id": 1},
            "account": {"id": 1},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"

    # 2. Outgoing message
    resp = client.post(
        "/api/v1/chatwoot/webhook",
        json={
            "event": "message_created",
            "message_type": "outgoing",
            "conversation": {"id": 1},
            "account": {"id": 1},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"

    # 3. Staff user message
    resp = client.post(
        "/api/v1/chatwoot/webhook",
        json={
            "event": "message_created",
            "message_type": "incoming",
            "sender": {"id": 99, "type": "user"},
            "conversation": {"id": 1},
            "account": {"id": 1},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    assert resp.json()["reason"] == "staff_message"


def test_chatwoot_agentbot_webhook_agent_execution():
    """Test webhook routing regular inquiry to agent execution."""
    client = TestClient(app)
    resp = client.post(
        "/api/v1/chatwoot/webhook",
        json={
            "event": "message_created",
            "message_type": "incoming",
            "content": "Can I book a consultation tomorrow at 10am?",
            "sender": {"id": 5, "type": "contact"},
            "conversation": {"id": 10},
            "account": {"id": 1},
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "handled"
    assert data["action"] == "agent_execution"
    assert data["conversation_id"] == 10
    assert data["content"] == "Can I book a consultation tomorrow at 10am?"


def test_chatwoot_agentbot_webhook_human_handoff(monkeypatch):
    """Test webhook detecting handoff request and invoking handoff service."""
    handoff_called = []
    bot_message_called = []

    async def fake_handoff(*args, **kwargs):
        handoff_called.append(kwargs)
        return {"status": "success", "conversation_status": "open"}

    async def fake_bot_message(*args, **kwargs):
        bot_message_called.append(kwargs)
        return {"id": 123}

    import app.api.routers.chatwoot_agentbot as cb_module
    monkeypatch.setattr(cb_module, "handoff_to_human", fake_handoff)
    monkeypatch.setattr(cb_module, "send_bot_message", fake_bot_message)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chatwoot/webhook",
        headers={
            "X-Chatwoot-Api-Token": "test_token_123",
            "X-Chatwoot-Base-Url": "https://chat.example.com",
        },
        json={
            "event": "message_created",
            "message_type": "incoming",
            "content": "I want to speak with a human agent right now",
            "sender": {"id": 5, "type": "contact"},
            "conversation": {"id": 10},
            "account": {"id": 1},
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "handled"
    assert data["action"] == "human_handoff"
    assert data["conversation_id"] == 10
    assert len(handoff_called) == 1
    assert len(bot_message_called) == 1


def test_chatwoot_agentbot_webhook_missing_fields():
    """Test webhook rejects payloads with missing required fields with HTTP 422."""
    client = TestClient(app)

    # Missing conversation and account
    resp1 = client.post("/api/v1/chatwoot/webhook", json={"event": "message_created"})
    assert resp1.status_code == 422

    # Missing event
    resp2 = client.post(
        "/api/v1/chatwoot/webhook",
        json={"conversation": {"id": 1}, "account": {"id": 1}},
    )
    assert resp2.status_code == 422

    # Missing conversation.id
    resp3 = client.post(
        "/api/v1/chatwoot/webhook",
        json={"event": "message_created", "conversation": {}, "account": {"id": 1}},
    )
    assert resp3.status_code == 422


def test_chatwoot_agentbot_webhook_bot_echoes():
    """Test that bot echoes ('agent_bot' or 'bot' sender types) are ignored to prevent infinite loops."""
    client = TestClient(app)

    for sender_type in ("agent_bot", "bot"):
        resp = client.post(
            "/api/v1/chatwoot/webhook",
            json={
                "event": "message_created",
                "message_type": "incoming",
                "content": "Hello customer, how can I help?",
                "sender": {"id": 88, "type": sender_type},
                "conversation": {"id": 10},
                "account": {"id": 1},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ignored"
        assert data["reason"] == "bot_message"


def test_chatwoot_agentbot_webhook_secret_auth(monkeypatch):
    """Test webhook secret authentication when CHATWOOT_WEBHOOK_SECRET is configured."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "CHATWOOT_WEBHOOK_SECRET", "super_secret_token_abc")
    client = TestClient(app)

    valid_payload = {
        "event": "message_created",
        "message_type": "incoming",
        "content": "Check availability",
        "conversation": {"id": 10},
        "account": {"id": 1},
    }

    # 1. Missing token -> 401
    resp_missing = client.post("/api/v1/chatwoot/webhook", json=valid_payload)
    assert resp_missing.status_code == 401

    # 2. Invalid token -> 401
    resp_invalid = client.post(
        "/api/v1/chatwoot/webhook?token=wrong_token",
        json=valid_payload,
    )
    assert resp_invalid.status_code == 401

    # 3. Valid token in query param -> 200
    resp_query = client.post(
        "/api/v1/chatwoot/webhook?token=super_secret_token_abc",
        json=valid_payload,
    )
    assert resp_query.status_code == 200
    assert resp_query.json()["status"] == "handled"

    # 4. Valid token in X-Chatwoot-Token header -> 200
    resp_header = client.post(
        "/api/v1/chatwoot/webhook",
        headers={"X-Chatwoot-Token": "super_secret_token_abc"},
        json=valid_payload,
    )
    assert resp_header.status_code == 200
    assert resp_header.json()["status"] == "handled"


def test_chatwoot_agentbot_handoff_error_resilience(monkeypatch):
    """Test that an error in the Chatwoot API during handoff does not crash the webhook."""
    async def failing_handoff(*args, **kwargs):
        raise RuntimeError("Chatwoot connection dropped")

    import app.api.routers.chatwoot_agentbot as cb_module
    monkeypatch.setattr(cb_module, "handoff_to_human", failing_handoff)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chatwoot/webhook",
        headers={"X-Chatwoot-Api-Token": "test_token"},
        json={
            "event": "message_created",
            "message_type": "incoming",
            "content": "Speak to representative",
            "conversation": {"id": 50},
            "account": {"id": 1},
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "handled"
    assert data["action"] == "human_handoff"
    assert data["handoff_details"] is None


@pytest.mark.asyncio
async def test_handoff_to_human_http_error():
    """Test handoff_to_human raises HTTPStatusError when Chatwoot responds with 403."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await handoff_to_human(
                chatwoot_base_url="https://app.chatwoot.com",
                api_access_token="invalid",
                account_id=1,
                conversation_id=42,
                client=client,
            )


@pytest.mark.asyncio
async def test_send_bot_message_http_error():
    """Test send_bot_message raises HTTPStatusError when Chatwoot responds with 500."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Error")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await send_bot_message(
                chatwoot_base_url="https://app.chatwoot.com",
                api_access_token="tok",
                account_id=1,
                conversation_id=42,
                content="test",
                client=client,
            )

