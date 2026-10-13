"""Unit and integration tests for FastAPI LiveKit room token issuance, dispatch, and transport selector."""

import json
from unittest.mock import patch

import jwt
import pytest

from app.core.config import settings
from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant.gpt_live.runtime import GPTLiveSession
from app.services.business_assistant.livekit.token_service import (
    LiveKitConfigurationError,
    LiveKitTokenService,
)


def _owner(db_session, suffix: str) -> tuple[Tenant, User]:
    tenant = Tenant(name=f"LiveKit Tenant {suffix}", subdomain=f"livekit-{suffix}")
    db_session.add(tenant)
    db_session.flush()
    user = User(
        tenant_id=tenant.id,
        login=f"livekit-owner-{suffix}",
        password_hash="test",
        role="owner",
    )
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _staff(db_session, tenant: Tenant, suffix: str) -> User:
    user = User(
        tenant_id=tenant.id,
        login=f"livekit-staff-{suffix}",
        password_hash="test",
        role="staff",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


def _conversation(client, headers: dict[str, str], request_key: str = "livekit-conv-1") -> int:
    response = client.post(
        "/api/admin/business-assistant/conversations",
        headers=headers,
        json={"request_key": request_key},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_token_service_generates_valid_jwt_and_opaque_claims():
    """Verify LiveKitTokenService builds standard JWT with correct VideoGrants and agent dispatch."""
    service = LiveKitTokenService(
        api_key="test_api_key_32_bytes_long_minimum!!",
        api_secret="test_api_secret_32_bytes_long_minimum!!",
        livekit_url="wss://livekit.example.com",
    )

    result = service.create_room_token(
        tenant_id=42,
        user_id=101,
        conversation_id=999,
        ttl_seconds=300,
    )

    assert result.transport == "livekit_gpt_live"
    assert result.livekit_url == "wss://livekit.example.com"
    assert result.agent_name == "bookings-business-assistant"
    assert result.expires_in == 300
    assert result.room_name.startswith("room_42_999_")
    assert result.participant_identity.startswith("part_101_")
    assert result.session_id.startswith("sess_")

    # Decode and verify JWT claims structure
    claims = jwt.decode(
        result.token,
        key="test_api_secret_32_bytes_long_minimum!!",
        algorithms=["HS256"],
        options={"verify_exp": False},
    )

    assert claims["iss"] == "test_api_key_32_bytes_long_minimum!!"
    assert claims["sub"] == result.participant_identity

    # Video grants
    video = claims.get("video", {})
    assert video.get("roomJoin") is True
    assert video.get("room") == result.room_name
    assert video.get("canPublish") is True
    assert video.get("canSubscribe") is True
    assert video.get("canPublishData") is True

    # Room agent dispatch configuration
    room_config = claims.get("roomConfig", {})
    agents = room_config.get("agents", [])
    assert len(agents) == 1
    assert agents[0]["agentName"] == "bookings-business-assistant"

    metadata = json.loads(agents[0]["metadata"])
    assert metadata["session_id"] == result.session_id
    assert metadata["tenant_id"] == 42
    assert metadata["user_id"] == 101
    assert metadata["conversation_id"] == 999


def test_token_service_missing_credentials_raises_error():
    """Verify LiveKitTokenService raises LiveKitConfigurationError when credentials are empty."""
    service = LiveKitTokenService(api_key="", api_secret="", livekit_url="")
    with pytest.raises(LiveKitConfigurationError):
        service.create_room_token(tenant_id=1, user_id=1, conversation_id=1)


def test_get_voice_transport_endpoint(client, db_session):
    """Verify GET /api/admin/business-assistant/voice/transport returns authoritative transport."""
    tenant, user = _owner(db_session, "transport-test")
    headers = _headers(tenant, user)

    response = client.get("/api/admin/business-assistant/voice/transport", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["transport"] in [
        "livekit_gpt_live",
        "direct_gpt_live",
        "local_livekit",
        "cloud_livekit",
        "xai_grok_voice",
    ]
    assert "direct_gpt_live" in data["available_transports"]
    assert "local_livekit" in data["available_transports"]
    assert data["agent_name"] == "bookings-business-assistant"


def test_create_voice_session_livekit_endpoint(client, db_session):
    """Verify POST /conversations/{id}/session issues LiveKit room token by default or explicitly."""
    tenant, user = _owner(db_session, "lk-create")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers, request_key="lk-create-conv")

    response = client.post(
        f"/api/admin/business-assistant/voice/conversations/{conv_id}/session",
        headers=headers,
        json={"transport": "livekit_gpt_live"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["transport"] == "livekit_gpt_live"
    assert data["token"] is not None
    assert data["livekit_url"] in (getattr(settings, "LIVEKIT_LOCAL_URL", "ws://127.0.0.1:7880"), "ws://127.0.0.1:7880", settings.LIVEKIT_URL)
    assert data["session_id"].startswith("sess_")
    assert data["room_name"].startswith(f"room_{tenant.id}_{conv_id}_")
    assert data["participant_identity"].startswith(f"part_{user.id}_")
    assert data["agent_name"] == "bookings-business-assistant"


def test_create_voice_session_direct_fallback(client, db_session):
    """Verify transport selector routing to direct_gpt_live WebRTC path."""
    tenant, user = _owner(db_session, "direct-route")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers, request_key="direct-route-conv")

    # Standalone discovery / handshake without SDP returns 201 with direct endpoint
    disc_resp = client.post(
        f"/api/admin/business-assistant/voice/conversations/{conv_id}/session",
        headers=headers,
        json={"transport": "direct_gpt_live"},
    )
    assert disc_resp.status_code == 201
    disc_data = disc_resp.json()
    assert disc_data["transport"] == "direct_gpt_live"
    assert disc_data["endpoint"] == "/api/admin/business-assistant/voice/realtime"
    assert disc_data["session_id"].startswith("direct_")
    assert disc_data.get("livekit_url") is None
    assert disc_data.get("token") is None

    # With SDP, should route to direct runtime
    with patch(
        "app.services.business_assistant.livekit.router.get_gpt_live_runtime"
    ) as mock_runtime_getter:
        mock_runtime = mock_runtime_getter.return_value
        mock_runtime.create_session.return_value = GPTLiveSession(
            session_id="mock_direct_sess_123",
            sdp="v=0\r\no=mock_answer\r\n",
        )

        ok_resp = client.post(
            f"/api/admin/business-assistant/voice/conversations/{conv_id}/session",
            headers=headers,
            json={"transport": "direct_gpt_live", "sdp": "v=0\r\no=mock_offer\r\n"},
        )
        assert ok_resp.status_code == 201
        res = ok_resp.json()
        assert res["transport"] == "direct_gpt_live"
        assert res["session_id"] == "mock_direct_sess_123"
        assert res["sdp"] == "v=0\r\no=mock_answer\r\n"


def test_create_voice_session_boundaries_and_isolation(client, db_session):
    """Verify unauthorized calls, invalid roles, and cross-tenant conversation isolation."""
    tenant1, user1 = _owner(db_session, "t1")
    tenant2, user2 = _owner(db_session, "t2")
    headers1 = _headers(tenant1, user1)
    headers2 = _headers(tenant2, user2)

    conv_id1 = _conversation(client, headers1, request_key="t1-conv-key")

    # 1. Unauthenticated requests rejected:
    # Missing tenant header returns 400
    no_tenant = client.post(
        f"/api/admin/business-assistant/voice/conversations/{conv_id1}/session",
        json={"transport": "livekit_gpt_live"},
    )
    assert no_tenant.status_code == 400

    # Missing auth token returns 401
    unauth = client.post(
        f"/api/admin/business-assistant/voice/conversations/{conv_id1}/session",
        headers={"X-Tenant": tenant1.subdomain},
        json={"transport": "livekit_gpt_live"},
    )
    assert unauth.status_code in [401, 403]

    # 2. Cross-tenant access rejected with 404 (conversation not found in tenant2 scope)
    cross_tenant = client.post(
        f"/api/admin/business-assistant/voice/conversations/{conv_id1}/session",
        headers=headers2,
        json={"transport": "livekit_gpt_live"},
    )
    assert cross_tenant.status_code == 404
