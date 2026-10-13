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
    session_config = client.get(
        f"/api/admin/business-assistant/conversations/{conversation_id}/realtime/session",
        headers=headers_b,
    )
    assert sdp.status_code == 404
    assert turn.status_code == 404
    assert session_config.status_code == 404


def test_realtime_session_config_returns_instructions_and_all_tool_schemas(client, db_session):
    tenant, user = _owner(db_session, "session-config")
    headers = _headers(tenant, user)
    conversation_id = _conversation(client, headers)

    response = client.get(
        f"/api/admin/business-assistant/conversations/{conversation_id}/realtime/session",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "instructions" in data
    assert "Tool selection rules" in data["instructions"]
    assert "navigate_route and nothing else" in data["instructions"]
    assert "(GPT-4o)" not in data["instructions"]
    assert "tools" in data
    from app.services.business_assistant.tool_registry import VOICE_BUSINESS_ASSISTANT_TOOLS
    assert len(data["tools"]) == len(VOICE_BUSINESS_ASSISTANT_TOOLS)

    tool_names = {tool["name"] for tool in data["tools"]}
    assert "navigate_route" in tool_names
    assert "highlight_field" in tool_names
    assert "stage_fields" in tool_names
    assert "validate_form" in tool_names
    assert "commit_save" in tool_names
    assert "diagnostic_report" in tool_names
    assert "activate_business_rule" in tool_names
    assert "list_services" in tool_names
    assert "list_providers" in tool_names
    assert "check_slot_availability" in tool_names
    assert "read_system_settings" in tool_names

    # Excluded duplicate and unneeded tools in voice
    for excluded in ("navigate_show", "save_form", "prepare_fields", "fill_form", "read_status", "confirm_business_rule"):
        assert excluded not in tool_names

    for tool in data["tools"]:
        assert tool["type"] == "function"
        assert isinstance(tool["name"], str) and tool["name"]
        assert isinstance(tool["description"], str)
        assert isinstance(tool["parameters"], dict)


def test_realtime_tools_safeguards_against_cascades_and_loops(client, db_session):
    tenant, user = _owner(db_session, "safeguards")
    headers = _headers(tenant, user)
    conversation_id = _conversation(client, headers)

    # 1. navigate_route executes and returns terminal status and directive
    nav_res = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/realtime/tools",
        headers=headers,
        json={"name": "navigate_route", "arguments": {"route": "/admin/clients"}},
    )
    assert nav_res.status_code == 200
    nav_data = nav_res.json()
    assert nav_data["status"] == "ok"
    assert nav_data["result"]["terminal"] is True
    assert "conclude" in nav_data["result"]["directive"].lower() or "completed" in nav_data["result"]["directive"].lower()

    # 2. First diagnostic_report succeeds
    diag_res1 = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/realtime/tools",
        headers=headers,
        json={"name": "diagnostic_report", "arguments": {}},
    )
    assert diag_res1.status_code == 200
    assert diag_res1.json()["status"] == "ok"

    # 3. Immediate second diagnostic_report within 15s is throttled
    diag_res2 = client.post(
        f"/api/admin/business-assistant/conversations/{conversation_id}/realtime/tools",
        headers=headers,
        json={"name": "diagnostic_report", "arguments": {}},
    )
    assert diag_res2.status_code == 200
    diag2_data = diag_res2.json()
    assert diag2_data["result"]["throttled"] is True
    assert diag2_data["result"]["verdict"] == "Cached"

    # 4. Rapid-fire barrage of calls triggers burst protection rate limit (max 20 calls per 3s)
    burst_res = None
    for _ in range(19):
        burst_res = client.post(
            f"/api/admin/business-assistant/conversations/{conversation_id}/realtime/tools",
            headers=headers,
            json={"name": "read_product_help", "arguments": {"topic": "general"}},
        )
    assert burst_res.status_code == 200
    assert burst_res.json()["status"] == "rejected"
    assert "rate limit exceeded" in burst_res.json()["reason"].lower()


def test_onboarding_tools_allow_rapid_burst_sequence(client, db_session):
    """Verify onboarding tools (stage_fields, validate_form, commit_save, etc.) are permitted
    in rapid succession without being blocked by general 4-call burst limits."""
    tenant, user = _owner(db_session, "burst_onboarding")
    headers = _headers(tenant, user)
    conversation_id = _conversation(client, headers)

    # Execute 6 rapid onboarding status calls in immediate succession
    for _ in range(6):
        res = client.post(
            f"/api/admin/business-assistant/conversations/{conversation_id}/realtime/tools",
            headers=headers,
            json={"name": "get_onboarding_status", "arguments": {"include_facts": True}},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "rate limit exceeded" not in (data.get("reason") or "").lower()
