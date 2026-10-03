"""Authenticated realtime voice contract tests without provider simulation."""

from app.core.config import settings
from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant.realtime import BusinessAssistantRealtimeRuntime


def _owner(db_session, suffix: str) -> tuple[Tenant, User]:
    tenant = Tenant(name=f"Voice Tenant {suffix}", subdomain=f"voice-{suffix}")
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, login=f"voice-owner-{suffix}", password_hash="test", role="owner")
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


def _conversation(client, headers: dict[str, str]) -> int:
    response = client.post(
        "/api/admin/business-assistant/conversations",
        headers=headers,
        json={"request_key": "voice-conversation-request-key"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _turn_payload() -> dict:
    return {
        "session_id": "a271aeb1-bf91-4fb3-9622-9da1a91a3f14",
        "user_item_id": "user-item-1",
        "assistant_response_id": "assistant-response-1",
        "user_transcript": "How do I check my enabled modules?",
        "assistant_transcript": "Open the onboarding panel to review enabled modules.",
    }


def test_realtime_sdp_transport_contract_uses_the_calls_endpoint_without_network_io():
    runtime = BusinessAssistantRealtimeRuntime(
        api_key="configured",
        model_name="approved-realtime-model",
        timeout_seconds=10,
        max_sdp_bytes=1_024,
    )

    request = runtime._build_exchange_request(b"v=0\r\n")

    assert request.method == "POST"
    assert str(request.url) == "https://api.openai.com/v1/realtime/calls?model=approved-realtime-model"
    assert request.headers["content-type"] == "application/sdp"
    assert request.headers["accept"] == "application/sdp"
    assert request.headers["authorization"].startswith("Bearer ")
    assert request.content == b"v=0\r\n"


def test_realtime_sdp_requires_config_and_preserves_no_session_state(client, db_session, monkeypatch):
    tenant, user = _owner(db_session, "unavailable")
    headers = _headers(tenant, user)
    conversation_id = _conversation(client, headers)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_REALTIME_MODEL", "")

    response = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/realtime",
        headers={**headers, "Content-Type": "application/sdp"},
        content=b"v=0\r\n",
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "REALTIME_CONFIGURATION_REQUIRED"
    assert "configure a realtime model" in response.json()["error"]["message"].lower()


def test_realtime_sdp_rejects_an_invalid_browser_offer_without_calling_a_provider(client, db_session, monkeypatch):
    tenant, user = _owner(db_session, "invalid-offer")
    headers = _headers(tenant, user)
    conversation_id = _conversation(client, headers)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "configured-for-local-validation")
    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_REALTIME_MODEL", "configured-realtime-model")

    response = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/realtime",
        headers={**headers, "Content-Type": "application/sdp"},
        content=b"",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REALTIME_INVALID_SDP"
    assert "valid voice offer" in response.json()["error"]["message"].lower()


def test_realtime_turns_persist_one_ordered_voice_pair_idempotently(client, db_session):
    tenant, user = _owner(db_session, "turns")
    headers = _headers(tenant, user)
    conversation_id = _conversation(client, headers)

    created = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/realtime/turns",
        headers=headers,
        json=_turn_payload(),
    )
    repeated = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/realtime/turns",
        headers=headers,
        json=_turn_payload(),
    )
    assert created.status_code == 200
    assert repeated.status_code == 200
    assert created.json()["duplicate_turn"] is False
    assert repeated.json()["duplicate_turn"] is True
    assert created.json()["assistant_message"]["in_reply_to_message_id"] == created.json()["user_message"]["id"]
    assert created.json()["user_message"]["channel"] == "realtime_voice"
    assert created.json()["assistant_message"]["channel"] == "realtime_voice"

    history = client.get(
        f"/api/admin/business-assistant/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert [item["channel"] for item in history.json()] == ["realtime_voice", "realtime_voice"]


def test_realtime_routes_hide_another_tenants_conversation(client, db_session):
    tenant_a, user_a = _owner(db_session, "scope-a")
    tenant_b, user_b = _owner(db_session, "scope-b")
    conversation_id = _conversation(client, _headers(tenant_a, user_a))
    headers_b = _headers(tenant_b, user_b)

    sdp = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/realtime",
        headers={**headers_b, "Content-Type": "application/sdp"},
        content=b"v=0\r\n",
    )
    turn = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/realtime/turns",
        headers=headers_b,
        json=_turn_payload(),
    )
    assert sdp.status_code == 404
    assert turn.status_code == 404
