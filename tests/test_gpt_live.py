"""Contract coverage for the isolated, server-authorised GPT-Live integration."""

import json

import httpx

from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant.gpt_live.runtime import GPTLiveRuntime, load_session_config


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
        "session": load_session_config(),
        "transport": {"type": "webrtc", "sdp": "v=0\r\no=offer\r\n"},
    }
    assert captured["headers"]["authorization"] == "Bearer server-only-key"


def test_session_config_preserves_the_approved_gpt_live_models_and_delegation():
    config = load_session_config()
    assert config["model"] == "gpt-live-1"
    assert config["audio"] == {"output": {"voice": "gleam"}}
    assert config["delegation"]["type"] == "responses"
    assert config["delegation"]["responses"]["model"] == "gpt-5.6-terra"
    assert config["delegation"]["responses"]["parallel_tool_calls"] is False
    assert config["delegation"]["responses"]["tools"] == [{"type": "web_search"}]


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
