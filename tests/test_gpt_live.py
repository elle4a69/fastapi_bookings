"""Contract coverage for the isolated, server-authorised GPT-Live integration."""

import json

import httpx

from app.core.security import create_access_token
from app.db.database import Base
from app.models.onboarding import OnboardingAuditLog, OnboardingPlan, OnboardingStep
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant.gpt_live.runtime import (
    GPTLiveRuntime,
    load_session_config,
    sanitize_gpt_live_session_payload,
)


def _owner(db_session, suffix: str) -> tuple[Tenant, User]:
    tenant = Tenant(name=f"GPT Live Tenant {suffix}", subdomain=f"gpt-live-{suffix}")
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, login=f"gpt-live-owner-{suffix}", password_hash="test", role="owner")
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
        json={"request_key": "gpt-live-conversation"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_runtime_posts_exact_config_in_a_json_webrtc_session_request():
    captured: dict[str, object] = {}

    def send(request: httpx.Request, _timeout: float) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "session": {"id": "live_opaque_session"},
                "transport": {"type": "webrtc", "sdp": "v=0\r\no=answer\r\n"},
            },
            request=request,
        )

    runtime = GPTLiveRuntime(
        api_key="server-only-key",
        timeout_seconds=5,
        max_sdp_bytes=10_000,
        request_sender=send,
    )
    session = runtime.create_session("v=0\r\no=offer\r\n")

    assert session.session_id == "live_opaque_session"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.openai.com/v1/live/sessions"
    assert captured["body"] == {
        "session": sanitize_gpt_live_session_payload(load_session_config()),
        "transport": {"type": "webrtc", "sdp": "v=0\r\no=offer\r\n"},
    }
    assert captured["headers"]["authorization"] == "Bearer server-only-key"


def test_session_config_preserves_the_approved_gpt_live_models_and_delegation():
    config = load_session_config()
    assert config["model"] == "gpt-live-1"
    assert config["audio"] == {"output": {"voice": "gleam"}}
    assert "tools" not in config
    assert config["delegation"]["type"] == "responses"
    assert config["delegation"]["responses"]["model"] == "gpt-5.6-terra"
    assert config["delegation"]["responses"]["tools"] == [{"type": "web_search"}]
    assert config["delegation"]["responses"]["parallel_tool_calls"] is False


def test_runtime_preserves_safe_provider_diagnostics_without_exposing_provider_body():
    def send(request: httpx.Request, _timeout: float) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"x-request-id": "req_provider_123"},
            json={
                "error": {
                    "code": "insufficient_permissions",
                    "message": "A message that must not be forwarded to the browser.",
                }
            },
            request=request,
        )

    runtime = GPTLiveRuntime(
        api_key="server-only-key",
        timeout_seconds=5,
        max_sdp_bytes=10_000,
        request_sender=send,
    )

    try:
        runtime.create_session("v=0\r\no=offer\r\n")
    except Exception as exc:
        assert exc.__class__.__name__ == "GPTLiveProviderUnavailableError"
        assert exc.provider_status == 403
        assert exc.provider_code == "insufficient_permissions"
        assert exc.provider_request_id == "req_provider_123"
        assert "must not" not in str(exc)
    else:
        raise AssertionError("Expected the provider request to fail.")


def test_gpt_live_route_requires_owned_conversation_and_returns_no_credential(client, db_session, monkeypatch):
    tenant, owner = _owner(db_session, "owner")
    headers = _headers(tenant, owner)
    conversation_id = _conversation(client, headers)

    class Runtime:
        def create_session(self, sdp: str):
            assert sdp == "v=0\r\no=offer\r\n"
            return type("Session", (), {"session_id": "live_opaque", "sdp": "v=0\r\no=answer\r\n"})()

    monkeypatch.setattr(
        "app.services.business_assistant.gpt_live.router.get_gpt_live_runtime",
        lambda: Runtime(),
    )
    response = client.post(
        f"/api/admin/gpt-live/conversations/{conversation_id}/sessions",
        headers=headers,
        json={"sdp": "v=0\r\no=offer\r\n"},
    )

    assert response.status_code == 201
    assert response.json() == {"session_id": "live_opaque", "sdp": "v=0\r\no=answer\r\n"}
    assert "key" not in response.text.lower()


def test_gpt_live_route_rejects_cross_tenant_conversation(client, db_session):
    owner_tenant, owner = _owner(db_session, "first")
    conversation_id = _conversation(client, _headers(owner_tenant, owner))
    other_tenant, other_owner = _owner(db_session, "second")

    response = client.post(
        f"/api/admin/gpt-live/conversations/{conversation_id}/sessions",
        headers=_headers(other_tenant, other_owner),
        json={"sdp": "v=0\r\no=offer\r\n"},
    )
    assert response.status_code == 404


def test_build_gpt_live_session_config_includes_onboarding_tools_and_ui_instructions():
    from app.services.business_assistant.gpt_live.runtime import build_gpt_live_session_config

    config = build_gpt_live_session_config()
    assert "tools" not in config
    assert "directly connected to the user's live web application" not in config["instructions"]
    assert "stage_fields" not in config["instructions"]
    terra = config["delegation"]["responses"]["instructions"]
    assert "directly connected to the user's live web application" in terra
    assert "stage_fields" in terra
    assert "single `stage_fields` call" in terra

    del_tools = config["delegation"]["responses"]["tools"]
    del_names = [t.get("name") for t in del_tools if t.get("type") == "function"]
    assert "stage_fields" in del_names
    assert "validate_form" in del_names
    assert "commit_save" in del_names
    assert "highlight_field" in del_names
    assert "navigate_route" in del_names
    assert "get_onboarding_status" in del_names
    assert "list_services" in del_names
    assert "read_system_settings" in del_names
    assert any(t.get("type") == "web_search" for t in del_tools)
    assert config["delegation"]["responses"]["tool_choice"] == "auto"


def test_service_execute_tool_executes_onboarding_tools_via_onboarding_gateway(client, db_session):
    Base.metadata.create_all(bind=db_session.get_bind())
    owner_tenant, owner = _owner(db_session, "onboarding-exec")
    headers = _headers(owner_tenant, owner)
    conv_id = _conversation(client, headers)

    # 1. Test get_onboarding_status over realtime tool route
    status_res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/tools",
        headers=headers,
        json={"name": "get_onboarding_status", "arguments": {}},
    )
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "ok"
    assert "plan_summary" in status_data["result"]

    # 2. Test stage_fields over realtime tool route
    stage_res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/tools",
        headers=headers,
        json={
            "name": "stage_fields",
            "arguments": {
                "step_id": "step_1_identity",
                "fields": {"business_name": "Lumina Direct Salon"},
            },
        },
    )
    assert stage_res.status_code == 200
    stage_data = stage_res.json()
    assert stage_data["status"] == "ok"
    assert stage_data["result"]["receipt_state"] == "fields_staged"


def test_build_create_request_sanitizes_outbound_payload_strictly():
    from app.services.business_assistant.gpt_live.runtime import (
        _ALLOWED_DELEGATION_RESPONSES_KEYS,
        _ALLOWED_GPT_LIVE_SESSION_KEYS,
        build_gpt_live_session_config,
    )

    full_config = build_gpt_live_session_config()
    # Intentionally inject invalid top-level keys that OpenAI rejects as unknown_parameter
    full_config["native_tools"] = ["dummy"]
    full_config["delegated_model"] = "gpt-5"
    full_config["temperature"] = 0.8
    full_config["modalities"] = ["audio"]

    runtime = GPTLiveRuntime(
        api_key="server-only-key",
        timeout_seconds=5,
        max_sdp_bytes=10_000,
    )
    request = runtime._build_create_request("v=0\r\no=offer\r\n", session_config=full_config)
    body = json.loads(request.content)

    assert "session" in body
    assert "transport" in body
    session = body["session"]

    # 1. Verify strict allowlist of top-level session keys (no session.tools or custom parameters)
    assert set(session.keys()) == _ALLOWED_GPT_LIVE_SESSION_KEYS
    assert "tools" not in session
    assert "native_tools" not in session
    assert "delegated_model" not in session
    assert "temperature" not in session
    assert "modalities" not in session
    assert "voice" not in session
    assert session["audio"] == {"output": {"voice": "gleam"}}

    # 2. Verify delegation responses tools are strictly formatted
    delegation = session["delegation"]
    responses = delegation["responses"]
    assert set(responses.keys()).issubset(_ALLOWED_DELEGATION_RESPONSES_KEYS)

    tools = responses["tools"]
    assert len(tools) > 0
    for tool in tools:
        if tool.get("type") == "web_search":
            assert set(tool.keys()) == {"type"}
        else:
            assert tool["type"] == "function"
            assert isinstance(tool["name"], str)
            assert isinstance(tool["description"], str)
            assert isinstance(tool["parameters"], dict)
            assert set(tool.keys()) == {"type", "name", "description", "parameters"}


