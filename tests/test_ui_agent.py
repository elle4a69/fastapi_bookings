"""Tests for the tenant-isolated UI Agent router and SSE stream."""

import json
from unittest.mock import patch

from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User


def _owner(db_session, suffix: str) -> tuple[Tenant, User]:
    tenant = Tenant(name=f"UI Agent Tenant {suffix}", subdomain=f"ui-agent-{suffix}")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        tenant_id=tenant.id,
        login=f"ui-agent-owner-{suffix}",
        password_hash="test",
        role="owner",
    )
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


def test_ui_agent_requires_authenticated_tenant_user(client, db_session):
    # Missing tenant header entirely -> 400
    res_no_tenant = client.post(
        "/api/admin/ui-agent/chat",
        json={
            "session_id": "test-session-1",
            "message": "Click button",
            "page_state": {"path": "/admin/catalog/services", "elements": []},
        },
    )
    assert res_no_tenant.status_code == 400

    # With tenant header but missing auth token -> 401
    tenant, _ = _owner(db_session, "auth-check")
    res_no_token = client.post(
        "/api/admin/ui-agent/chat",
        headers={"X-Tenant": tenant.subdomain},
        json={
            "session_id": "test-session-1",
            "message": "Click button",
            "page_state": {"path": "/admin/catalog/services", "elements": []},
        },
    )
    assert res_no_token.status_code == 401


def test_ui_agent_sync_chat_execution(client, db_session):
    tenant, user = _owner(db_session, "sync")
    headers = _headers(tenant, user)

    payload = {
        "session_id": "test-sync-1",
        "message": "Please navigate to /admin/catalog/services",
        "page_state": {
            "path": "/admin/dashboard",
            "title": "Dashboard",
            "routes": ["/admin/catalog/services"],
            "elements": [
                {"ref": "btn-services", "tag": "button", "label": "Services"},
            ],
        },
    }

    res = client.post("/api/admin/ui-agent/chat", headers=headers, json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "say" in data
    assert "actions" in data
    assert isinstance(data["actions"], list)


def test_ui_agent_sse_stream_chat(client, db_session):
    tenant, user = _owner(db_session, "stream")
    headers = _headers(tenant, user)

    payload = {
        "session_id": "test-stream-1",
        "message": "Click the add service button",
        "page_state": {
            "path": "/admin/catalog/services",
            "title": "Services",
            "elements": [
                {"ref": "add-srv-btn", "tag": "button", "label": "Add Service"},
            ],
        },
    }

    res = client.post("/api/admin/ui-agent/chat/stream", headers=headers, json=payload)
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    # Parse SSE stream chunks
    lines = res.text.strip().split("\n\n")
    events = []
    for chunk in lines:
        for line in chunk.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

    assert any(ev.get("type") in ("delta", "result") for ev in events)
    result_ev = next((ev for ev in events if ev.get("type") == "result"), None)
    assert result_ev is not None
    assert "say" in result_ev
    assert "actions" in result_ev


def test_ui_agent_session_final_and_timeline_lifecycle(client, db_session):
    tenant, user = _owner(db_session, "lifecycle")
    headers = _headers(tenant, user)
    session_id = "test-lifecycle-1"

    # 1. Chat turn
    client.post(
        "/api/admin/ui-agent/chat",
        headers=headers,
        json={
            "session_id": session_id,
            "message": "Inspect form",
            "page_state": {"path": "/admin/catalog/services", "elements": []},
        },
    )

    # 2. Save final execution results
    res_final = client.post(
        f"/api/admin/ui-agent/sessions/{session_id}/final",
        headers=headers,
        json={
            "results": [{"action": {"type": "click", "ref": "btn1"}, "ok": True}],
            "path": "/admin/catalog/services",
        },
    )
    assert res_final.status_code == 200
    assert res_final.json()["ok"] is True

    # 3. Retrieve timeline
    res_tl = client.get(
        f"/api/admin/ui-agent/sessions/{session_id}/timeline",
        headers=headers,
    )
    assert res_tl.status_code == 200
    tl_data = res_tl.json()
    assert tl_data["session_id"] == session_id
    assert len(tl_data["timeline"]) >= 2

    # 4. Delete session
    res_del = client.delete(
        f"/api/admin/ui-agent/sessions/{session_id}",
        headers=headers,
    )
    assert res_del.status_code == 200
    assert res_del.json()["ok"] is True


def test_ui_agent_multi_tenant_isolation(client, db_session):
    tenant_a, user_a = _owner(db_session, "tenant-a")
    tenant_b, user_b = _owner(db_session, "tenant-b")

    headers_a = _headers(tenant_a, user_a)
    headers_b = _headers(tenant_b, user_b)
    shared_session_id = "session-iso-123"

    # Tenant A chats
    client.post(
        "/api/admin/ui-agent/chat",
        headers=headers_a,
        json={
            "session_id": shared_session_id,
            "message": "Confidential Tenant A request",
            "page_state": {"path": "/admin/secret-a", "elements": []},
        },
    )

    # Tenant B inspects same session_id
    res_b = client.get(
        f"/api/admin/ui-agent/sessions/{shared_session_id}/timeline",
        headers=headers_b,
    )
    assert res_b.status_code == 200
    # Tenant B must see empty timeline due to tenant scoping
    assert res_b.json()["timeline"] == []


def test_ui_agent_voice_providers_and_session(client, db_session):
    tenant, user = _owner(db_session, "voice")
    headers = _headers(tenant, user)

    # 1. Check voice providers endpoint
    res_prov = client.get("/api/admin/ui-agent/voice/providers", headers=headers)
    assert res_prov.status_code == 200
    prov_data = res_prov.json()
    assert "openai" in prov_data
    assert "xai" in prov_data

    # 2. Check OpenAI live session rejects invalid voice
    res_bad_voice = client.post(
        "/api/admin/ui-agent/voice/openai/session",
        headers=headers,
        json={"sdp": "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n", "voice": "non_existent_voice"},
    )
    assert res_bad_voice.status_code in (400, 503)

    # 3. Check xAI token endpoint requires auth
    res_unauth = client.post("/api/admin/ui-agent/voice/xai/token")
    assert res_unauth.status_code in (400, 401)

