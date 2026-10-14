"""Tests for Direct Voice Transport Modes: Direct WebRTC (GPT-Live) and xAI Grok Voice.

Verifies:
1. Operator controls and voice transport endpoints expose available direct transports:
   ['direct_gpt_live', 'xai_grok_voice'].
2. Runtime toggle between:
   - Direct WebRTC ('direct_gpt_live'): Session endpoint returns standalone direct WebRTC endpoint.
   - xAI Grok Voice ('xai_grok_voice'): Session endpoint returns xAI Realtime relay endpoint.
3. Strict rejection of decommissioned LiveKit transports ('local_livekit', 'cloud_livekit', 'livekit_gpt_live').
4. Validation and error handling:
   - Rejection of invalid transport strings.
   - 503 error if xAI mode is selected without XAI_API_KEY.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.operator_controls import (
    get_operator_controls_service,
)
from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture(autouse=True)
def reset_operator_state():
    """Reset operator controls singleton state before each test."""
    service = get_operator_controls_service()
    service.reset_state_for_tests()
    yield
    service.reset_state_for_tests()


def _create_tenant_and_user(
    db_session, suffix: str, role: str = "owner"
) -> tuple[Tenant, User]:
    tenant = Tenant(name=f"Toggle Tenant {suffix}", subdomain=f"toggle-{suffix}")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        tenant_id=tenant.id,
        login=f"toggle-{role}-{suffix}@example.com",
        password_hash="test",
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(tenant)
    db_session.refresh(user)
    return tenant, user


def _auth_headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id), "tenant_id": tenant.id}),
    }


def _create_conversation(
    client: TestClient, headers: dict[str, str], request_key: str = "toggle-conv-1"
) -> int:
    resp = client.post(
        "/api/admin/business-assistant/conversations",
        headers=headers,
        json={"request_key": request_key},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_voice_transport_get_endpoint_returns_modes_and_targets(client: TestClient, db_session):
    """GET /api/admin/business-assistant/voice/transport returns available direct modes and targets."""
    tenant, owner = _create_tenant_and_user(db_session, "get-modes")
    headers = _auth_headers(tenant, owner)

    resp = client.get("/api/admin/business-assistant/voice/transport", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert set(data["available_transports"]) == {"direct_gpt_live", "xai_grok_voice"}
    assert "agent_name" in data
    assert "active_target" in data


def test_voice_transport_patch_mode_direct_gpt_live(client: TestClient, db_session):
    """Switching to direct_gpt_live routes session endpoint to direct WebRTC without LiveKit server."""
    tenant, owner = _create_tenant_and_user(db_session, "direct-mode")
    headers = _auth_headers(tenant, owner)
    conv_id = _create_conversation(client, headers, "conv-direct")

    # 1. Patch transport to direct_gpt_live
    patch_resp = client.patch(
        "/api/admin/business-assistant/voice/transport",
        headers=headers,
        json={"transport": "direct_gpt_live"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["transport"] == "direct_gpt_live"
    assert patch_resp.json()["active_target"] == "/api/admin/business-assistant/voice/realtime"

    # 2. Call session endpoint WITHOUT SDP (standalone discovery / handshake)
    sess_resp = client.post(
        f"/api/admin/business-assistant/voice/conversations/{conv_id}/session",
        headers=headers,
        json={},
    )
    assert sess_resp.status_code == 201
    sess_data = sess_resp.json()
    assert sess_data["transport"] == "direct_gpt_live"
    assert sess_data["endpoint"] == "/api/admin/business-assistant/voice/realtime"
    assert sess_data["session_id"].startswith("direct_")
    # Must NOT return LiveKit room URL
    assert sess_data.get("livekit_url") is None
    assert sess_data.get("token") is None


def test_voice_transport_rejects_decommissioned_livekit_transports(client: TestClient, db_session):
    """Attempting to set or request decommissioned livekit transports returns 400."""
    tenant, owner = _create_tenant_and_user(db_session, "decomm-mode")
    headers = _auth_headers(tenant, owner)
    conv_id = _create_conversation(client, headers, "conv-decomm")

    for decomm_transport in ("local_livekit", "cloud_livekit", "livekit_gpt_live"):
        # PATCH transport should reject
        patch_resp = client.patch(
            "/api/admin/business-assistant/voice/transport",
            headers=headers,
            json={"transport": decomm_transport},
        )
        assert patch_resp.status_code in (400, 422)

        # POST session with decommissioned transport should reject
        sess_resp = client.post(
            f"/api/admin/business-assistant/voice/conversations/{conv_id}/session",
            headers=headers,
            json={"transport": decomm_transport},
        )
        assert sess_resp.status_code == 400
        assert "DECOMMISSIONED_TRANSPORT" in sess_resp.text


def test_voice_transport_rejects_invalid_mode(client: TestClient, db_session):
    """Invalid transport mode must return 400 or 422."""
    tenant, owner = _create_tenant_and_user(db_session, "bad-mode")
    headers = _auth_headers(tenant, owner)

    resp = client.patch(
        "/api/admin/business-assistant/voice/transport",
        headers=headers,
        json={"transport": "unsupported_unknown_transport"},
    )
    assert resp.status_code in (400, 422)


def test_voice_transport_xai_mode_missing_credentials_fails_gracefully(client: TestClient, db_session):
    """If xai_grok_voice is selected but XAI_API_KEY is empty, returns 503."""
    tenant, owner = _create_tenant_and_user(db_session, "missing-xai")
    headers = _auth_headers(tenant, owner)
    conv_id = _create_conversation(client, headers, "conv-noxai")

    # Set xai_grok_voice mode
    patch_resp = client.patch(
        "/api/admin/business-assistant/voice/transport",
        headers=headers,
        json={"transport": "xai_grok_voice"},
    )
    assert patch_resp.status_code == 200

    # With XAI_API_KEY cleared, session creation returns 503
    with patch.object(settings, "XAI_API_KEY", ""):
        sess_resp = client.post(
            f"/api/admin/business-assistant/voice/conversations/{conv_id}/session",
            headers=headers,
            json={},
        )
        assert sess_resp.status_code == 503
        assert "XAI_CONFIGURATION_REQUIRED" in sess_resp.text


def test_voice_transport_xai_grok_voice_and_token_endpoint(client: TestClient, db_session):
    """Switching to xai_grok_voice returns xAI Realtime WebSocket configuration."""
    tenant, owner = _create_tenant_and_user(db_session, "xai-mode")
    headers = _auth_headers(tenant, owner)
    conv_id = _create_conversation(client, headers, "conv-xai")

    # 1. Test token endpoint
    token_resp = client.get("/api/admin/business-assistant/realtime/xai-token", headers=headers)
    assert token_resp.status_code == 200
    token_data = token_resp.json()
    assert "agent_id" in token_data
    assert "url" in token_data
    assert "relay_url" in token_data

    # 2. Patch transport to xai_grok_voice
    patch_resp = client.patch(
        "/api/admin/business-assistant/voice/transport",
        headers=headers,
        json={"transport": "xai_grok_voice"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["transport"] == "xai_grok_voice"

    # 3. Create session with xai_grok_voice (with synthetic key present)
    with patch.object(settings, "XAI_API_KEY", "xai-test-key-12345"):
        sess_resp = client.post(
            f"/api/admin/business-assistant/voice/conversations/{conv_id}/session",
            headers=headers,
            json={},
        )
        assert sess_resp.status_code == 201
        sess_data = sess_resp.json()
        assert sess_data["transport"] == "xai_grok_voice"
        assert "wss://api.x.ai" in sess_data["livekit_url"]
        assert sess_data["endpoint"] == "/api/admin/business-assistant/voice/realtime/xai-ws"


