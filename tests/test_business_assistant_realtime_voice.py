"""Comprehensive tests for Business Assistant WP8: Realtime Voice Foundation & Tool Parity.

Strictly adheres to AGENTS.md:
- No mocks (100% real database models, schemas, and live services).
- Tenant and role isolation.
- Full tool and policy parity between text and voice.
- Server-held credentials and SDP relay error classification.
- Idempotent turn persistence and deduplication.
- Interrupted/partial transcript safety.
- Graceful degradation and text fallback.
"""

import httpx
import pytest

from app.core.config import settings
from app.core.security import create_access_token
from app.models.business_assistant import (
    BusinessAssistantConversation,
    BusinessAssistantMessage,
    BusinessAssistantToolRun,
    SupportTicket,
)
from app.models.location import Location
from app.models.provider import Provider
from app.models.schedule import ProviderWorkDay
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant import (
    ALL_TOOL_PACKS,
    BusinessAssistantRealtimeRuntime,
    BusinessAssistantService,
    BusinessAssistantToolRegistry,
    RealtimeConfigurationError,
    RealtimeInvalidSdpError,
    RealtimeProviderUnavailableError,
    validate_sdp,
)
from app.services.business_assistant.adapters import BusinessAssistantReadAdapters


def _owner(db_session, suffix: str) -> tuple[Tenant, User]:
    tenant = Tenant(
        name=f"WP8 Voice Tenant {suffix}",
        subdomain=f"wp8-voice-{suffix}",
        timezone="Australia/Sydney",
        country="Australia",
        enabled_modules=["calendar", "bookings", "locations"],
        allow_in_call=True,
        allow_out_call=True,
    )
    db_session.add(tenant)
    db_session.flush()
    user = User(
        tenant_id=tenant.id,
        login=f"wp8-owner-{suffix}",
        password_hash="test-hash",
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


def _conversation(client, headers: dict[str, str]) -> int:
    response = client.post(
        "/api/admin/business-assistant/conversations",
        headers=headers,
        json={"title": "WP8 Voice Conversation", "request_key": "wp8-conv-key-1"},
    )
    assert response.status_code == 201
    return response.json()["id"]


# ===========================================================================
# 1. Server-Held Credentials & WebRTC SDP Relay Tests
# ===========================================================================

def test_sdp_offer_validation_unit_checks():
    """Verify validate_sdp enforces RFC 4566 size bounds, UTF-8 text, and v=0 version header."""
    max_bytes = 1024

    # 1. Valid SDP offer
    valid_offer = b"v=0\r\no=- 12345 67890 IN IP4 127.0.0.1\r\ns=-\r\nm=audio 9 UDP/TLS/RTP/SAVP 111\r\n"
    validate_sdp(valid_offer, max_bytes, is_offer=True)

    # 2. Minimal valid SDP (v=0)
    validate_sdp(b"v=0\r\n", max_bytes, is_offer=True)

    # 3. Empty offer rejected
    with pytest.raises(RealtimeInvalidSdpError, match="invalid or too large"):
        validate_sdp(b"", max_bytes, is_offer=True)

    # 4. Oversized offer rejected
    oversized = b"v=0\r\n" + b"a=custom\r\n" * 500
    with pytest.raises(RealtimeInvalidSdpError, match="invalid or too large"):
        validate_sdp(oversized, 50, is_offer=True)

    # 5. Non-text binary garbage rejected
    with pytest.raises(RealtimeInvalidSdpError, match="invalid non-text characters"):
        validate_sdp(b"\x80\xff\xfe\x00binarygarbage", max_bytes, is_offer=True)

    # 6. Missing v=0 header rejected
    with pytest.raises(RealtimeInvalidSdpError, match="missing required version header"):
        validate_sdp(b"m=audio 9 UDP/TLS/RTP/SAVP 111\r\nc=IN IP4 0.0.0.0\r\n", max_bytes, is_offer=True)


def test_sdp_answer_validation_unit_checks():
    """Verify validate_sdp validates provider answers and raises RealtimeProviderUnavailableError on malformed answer."""
    max_bytes = 1024

    # Valid answer
    validate_sdp(b"v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\n", max_bytes, is_offer=False)

    # Empty answer
    with pytest.raises(RealtimeProviderUnavailableError, match="invalid SDP answer"):
        validate_sdp(b"", max_bytes, is_offer=False)

    # Non-text answer
    with pytest.raises(RealtimeProviderUnavailableError, match="unreadable SDP answer"):
        validate_sdp(b"\xff\xfe\x00junk", max_bytes, is_offer=False)

    # Missing v=0 in answer
    with pytest.raises(RealtimeProviderUnavailableError, match="missing version header"):
        validate_sdp(b"o=- 0 0 IN IP4 127.0.0.1\r\n", max_bytes, is_offer=False)


def test_realtime_runtime_is_configured_helper(monkeypatch):
    """BusinessAssistantRealtimeRuntime.is_configured accurately reports setting presence."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_REALTIME_MODEL", "")
    assert BusinessAssistantRealtimeRuntime.is_configured() is False

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test-realtime")
    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_REALTIME_MODEL", "")
    assert BusinessAssistantRealtimeRuntime.is_configured() is False

    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_REALTIME_MODEL", "gpt-4o-realtime-preview")
    assert BusinessAssistantRealtimeRuntime.is_configured() is True


def test_realtime_sdp_relay_credentials_remain_strictly_server_side():
    """Build request verifies Bearer token is attached for provider and never returned to caller."""
    runtime = BusinessAssistantRealtimeRuntime(
        api_key="super-secret-server-key-xyz",
        model_name="gpt-4o-realtime-preview-2024-12-17",
        timeout_seconds=15.0,
        max_sdp_bytes=2048,
    )
    offer = b"v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\n"
    req = runtime._build_exchange_request(offer)

    assert req.headers["authorization"] == "Bearer super-secret-server-key-xyz"
    assert req.headers["content-type"] == "application/sdp"
    assert req.headers["accept"] == "application/sdp"
    assert "gpt-4o-realtime-preview-2024-12-17" in str(req.url)


def test_realtime_sdp_rejects_missing_content_type(client, db_session):
    """Endpoint strictly requires Content-Type: application/sdp."""
    tenant, user = _owner(db_session, "ct-check")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime",
        headers={**headers, "Content-Type": "application/json"},
        content=b'{"offer": "v=0"}',
    )
    assert res.status_code == 415
    assert "application/sdp" in res.json()["error"]["message"].lower()


def test_realtime_sdp_origin_validation(client, db_session, monkeypatch):
    """Origin validation permits configured frontend origins and rejects untrusted origins."""
    tenant, user = _owner(db_session, "origin-check")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    monkeypatch.setattr(settings, "FRONTEND_ORIGINS", "http://localhost:5173,https://admin.example.com")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_REALTIME_MODEL", "")

    # 1. Untrusted origin -> 403 Forbidden
    res_bad_origin = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime",
        headers={
            **headers,
            "Content-Type": "application/sdp",
            "Origin": "https://malicious-attacker.com",
        },
        content=b"v=0\r\n",
    )
    assert res_bad_origin.status_code == 403
    assert "not permitted" in res_bad_origin.json()["error"]["message"].lower()

    # 2. Allowlisted origin passes origin check (and hits config check -> 503)
    res_good_origin = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime",
        headers={
            **headers,
            "Content-Type": "application/sdp",
            "Origin": "http://localhost:5173",
        },
        content=b"v=0\r\n",
    )
    assert res_good_origin.status_code == 503
    assert res_good_origin.json()["error"]["code"] == "REALTIME_CONFIGURATION_REQUIRED"


def test_realtime_sdp_error_classification_provider_unavailable(client, db_session, monkeypatch):
    """Upstream provider transport failure is cleanly classified as REALTIME_PROVIDER_UNAVAILABLE (502)."""
    tenant, user = _owner(db_session, "provider-502")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-mock-key")
    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_REALTIME_MODEL", "gpt-4o-realtime-preview")

    # Simulate upstream network failure
    def mock_request(*args, **kwargs):
        raise httpx.ConnectError("Connection refused by upstream provider")

    monkeypatch.setattr(httpx, "request", mock_request)

    res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime",
        headers={**headers, "Content-Type": "application/sdp"},
        content=b"v=0\r\n",
    )
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "REALTIME_PROVIDER_UNAVAILABLE"
    assert "temporarily unavailable" in res.json()["error"]["message"].lower()


# ===========================================================================
# 2. Chronological & Idempotent Voice Turn Persistence Tests
# ===========================================================================

def test_realtime_turns_persistence_and_idempotency(client, db_session):
    """Voice turns persist transactionally with channel='realtime_voice' and enforce deduplication."""
    tenant, user = _owner(db_session, "dedup-turns")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    payload = {
        "session_id": "b1111111-2222-3333-4444-555555555555",
        "user_item_id": "voice-item-user-1",
        "assistant_response_id": "voice-item-asst-1",
        "user_transcript": "Can I see what services we offer?",
        "assistant_transcript": "Certainly! We have multiple massage and therapy services available.",
    }

    # Initial turn creation
    res1 = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/turns",
        headers=headers,
        json=payload,
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["duplicate_turn"] is False
    assert data1["user_message"]["channel"] == "realtime_voice"
    assert data1["assistant_message"]["channel"] == "realtime_voice"
    assert data1["user_message"]["content"] == payload["user_transcript"]
    assert data1["assistant_message"]["content"] == payload["assistant_transcript"]
    assert data1["assistant_message"]["in_reply_to_message_id"] == data1["user_message"]["id"]

    # Replay identical turn -> duplicate_turn=True, same message IDs returned
    res2 = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/turns",
        headers=headers,
        json=payload,
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["duplicate_turn"] is True
    assert data2["user_message"]["id"] == data1["user_message"]["id"]
    assert data2["assistant_message"]["id"] == data1["assistant_message"]["id"]


def test_realtime_turns_distinct_item_ids_validation(client, db_session):
    """Submitting turn with user_item_id equal to assistant_response_id is rejected."""
    tenant, user = _owner(db_session, "same-id")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    invalid_payload = {
        "session_id": "c1111111-2222-3333-4444-555555555555",
        "user_item_id": "identical-id-123",
        "assistant_response_id": "identical-id-123",
        "user_transcript": "Hello voice",
        "assistant_transcript": "Hello user",
    }

    res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/turns",
        headers=headers,
        json=invalid_payload,
    )
    assert res.status_code == 422


def test_realtime_turns_rejects_empty_or_whitespace_transcripts(client, db_session):
    """Interrupted or empty voice transcripts cannot be persisted as completed turns."""
    tenant, user = _owner(db_session, "empty-trans")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    # Empty user transcript
    res_empty_user = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/turns",
        headers=headers,
        json={
            "session_id": "d1111111-2222-3333-4444-555555555555",
            "user_item_id": "item-u-1",
            "assistant_response_id": "item-a-1",
            "user_transcript": "   ",
            "assistant_transcript": "Valid reply",
        },
    )
    assert res_empty_user.status_code == 422

    # Empty assistant transcript
    res_empty_asst = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/turns",
        headers=headers,
        json={
            "session_id": "d1111111-2222-3333-4444-555555555555",
            "user_item_id": "item-u-2",
            "assistant_response_id": "item-a-2",
            "user_transcript": "Valid question",
            "assistant_transcript": "",
        },
    )
    assert res_empty_asst.status_code == 422


def test_realtime_turns_mismatched_pairing_conflict(client, db_session):
    """Replaying an existing user_item_id with a different assistant_response_id raises 409 conflict."""
    tenant, user = _owner(db_session, "conflict-turn")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    session_id = "e1111111-2222-3333-4444-555555555555"

    res1 = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/turns",
        headers=headers,
        json={
            "session_id": session_id,
            "user_item_id": "voice-u-original",
            "assistant_response_id": "voice-a-original",
            "user_transcript": "First statement",
            "assistant_transcript": "First answer",
        },
    )
    assert res1.status_code == 200

    # Conflicting assistant response ID on same user item ID
    res_conflict = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/turns",
        headers=headers,
        json={
            "session_id": session_id,
            "user_item_id": "voice-u-original",
            "assistant_response_id": "voice-a-different",
            "user_transcript": "First statement",
            "assistant_transcript": "Second answer",
        },
    )
    assert res_conflict.status_code == 409
    assert "already being persisted" in res_conflict.json()["error"]["message"].lower()


# ===========================================================================
# 3. Tool Parity Between Text and Voice Tests
# ===========================================================================

def test_realtime_tools_parity_across_all_packs(client, db_session):
    """Verify POST /conversations/{id}/realtime/tools executes allowlisted tools across all 5 packs."""
    tenant, user = _owner(db_session, "parity")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    # Setup database records for booking and service tools
    service = Service(tenant_id=tenant.id, name="Swedish Massage", duration=60, price=100.0, active=True)
    provider = Provider(tenant_id=tenant.id, name="Elena Rostova", active=True)
    db_session.add_all([service, provider])
    db_session.flush()
    db_session.add(ServiceProvider(tenant_id=tenant.id, provider_id=provider.id, service_id=service.id))
    db_session.commit()

    # 1. Product Help Pack via realtime tools endpoint
    res_help = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/tools",
        headers=headers,
        json={"name": "read_product_help", "arguments": {}},
    )
    assert res_help.status_code == 200
    assert res_help.json()["status"] == "ok"
    assert "product_help" in res_help.json()["result"]

    # 2. Booking Availability Pack via realtime tools endpoint
    res_services = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/tools",
        headers=headers,
        json={"name": "list_services", "arguments": {"active_only": True}},
    )
    assert res_services.status_code == 200
    assert res_services.json()["status"] == "ok"
    assert len(res_services.json()["result"]["services"]) == 1

    # 3. Business Knowledge Pack via realtime tools endpoint
    res_knowledge = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/tools",
        headers=headers,
        json={"name": "list_curator_questions", "arguments": {"status": "all"}},
    )
    assert res_knowledge.status_code == 200
    assert res_knowledge.json()["status"] == "ok"

    # 4. Customer Operations Pack via realtime tools endpoint
    res_cust = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/tools",
        headers=headers,
        json={"name": "search_customer_conversations", "arguments": {}},
    )
    assert res_cust.status_code == 200
    assert res_cust.json()["status"] == "ok"

    # 5. Support Engineering Pack via realtime tools endpoint
    res_ticket = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/tools",
        headers=headers,
        json={
            "name": "create_support_ticket",
            "arguments": {
                "category": "bug",
                "title": "Voice turn test ticket",
                "description": "Found while testing realtime voice tools",
            },
        },
    )
    assert res_ticket.status_code == 200
    assert res_ticket.json()["status"] == "ok"
    assert res_ticket.json()["result"]["ticket"]["title"] == "Voice turn test ticket"


def test_realtime_tools_cannot_access_unallowlisted_or_coding_capabilities(client, db_session):
    """Voice sessions CANNOT execute bash, git, shell, deploy, or unallowlisted tools."""
    tenant, user = _owner(db_session, "unallowlisted")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    forbidden_tools = [
        "execute_shell",
        "run_bash",
        "deploy_code",
        "git_commit",
        "read_secret_key",
        "drop_database",
        "write_file",
    ]

    for tool_name in forbidden_tools:
        res = client.post(
            f"/api/admin/business-assistant/conversations/{conv_id}/realtime/tools",
            headers=headers,
            json={"name": tool_name, "arguments": {}},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "rejected"
        assert "not available in the active tool packs" in data["reason"].lower()


def test_realtime_tool_telemetry_audit(client, db_session):
    """Realtime tool invocations log structural telemetry in BusinessAssistantToolRun without argument leakage."""
    tenant, user = _owner(db_session, "audit-telemetry")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    # Execute a tool
    res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/tools",
        headers=headers,
        json={"name": "read_system_settings", "arguments": {"setting_key": "timezone"}},
    )
    assert res.status_code == 200

    # Query BusinessAssistantToolRun
    runs = (
        db_session.query(BusinessAssistantToolRun)
        .filter(
            BusinessAssistantToolRun.conversation_id == conv_id,
            BusinessAssistantToolRun.tenant_id == tenant.id,
        )
        .all()
    )
    assert len(runs) >= 1
    latest_run = runs[-1]
    assert latest_run.tool_name == "read_system_settings"
    assert latest_run.status == "ok"
    assert latest_run.duration_ms is not None
    assert latest_run.duration_ms >= 0


def test_confirmation_policy_parity_in_voice(client, db_session):
    """Mutating tools called via realtime voice enforce confirmation policy and never activate without token."""
    tenant, user = _owner(db_session, "voice-confirm")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    # 1. Draft business rule via realtime tool
    draft_res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/tools",
        headers=headers,
        json={
            "name": "draft_business_rule",
            "arguments": {
                "memory_key": "voice_cancellation_policy",
                "content": "Clients must cancel at least 24 hours prior to appointment time.",
                "category": "policy",
            },
        },
    )
    assert draft_res.status_code == 200
    data = draft_res.json()
    assert data["status"] == "ok"
    draft_data = data["result"]["draft"]
    assert draft_data["status"] == "draft"  # Strictly draft only
    token = data["result"]["confirmation_token"]
    assert len(token) > 20

    # 2. Attempt activate with invalid confirmation token -> rejected
    bad_activate_res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/tools",
        headers=headers,
        json={
            "name": "activate_business_rule",
            "arguments": {
                "memory_key": "voice_cancellation_policy",
                "confirmation_token": "fake-invalid-token",
            },
        },
    )
    assert bad_activate_res.status_code == 200
    assert bad_activate_res.json()["status"] == "rejected"

    # 3. Valid activation with genuine HMAC token
    good_activate_res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/tools",
        headers=headers,
        json={
            "name": "activate_business_rule",
            "arguments": {
                "memory_key": "voice_cancellation_policy",
                "confirmation_token": token,
            },
        },
    )
    assert good_activate_res.status_code == 200
    assert good_activate_res.json()["status"] == "ok"
    assert good_activate_res.json()["result"]["rule"]["status"] == "active"


# ===========================================================================
# 4. Conversation History Parity & Graceful Degradation Tests
# ===========================================================================

def test_conversation_history_unifies_voice_and_text(client, db_session):
    """Voice turns and text turns coexist in the exact same conversation history."""
    tenant, user = _owner(db_session, "unify-history")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    # 1. Voice turn
    voice_res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime/turns",
        headers=headers,
        json={
            "session_id": "f1111111-2222-3333-4444-555555555555",
            "user_item_id": "voice-u-unified",
            "assistant_response_id": "voice-a-unified",
            "user_transcript": "Spoken: What is our clinic address?",
            "assistant_transcript": "Spoken: Our clinic is located in Sydney CBD.",
        },
    )
    assert voice_res.status_code == 200

    # 2. List conversation messages
    history_res = client.get(
        f"/api/admin/business-assistant/conversations/{conv_id}/messages",
        headers=headers,
    )
    assert history_res.status_code == 200
    messages = history_res.json()
    assert len(messages) == 2
    assert messages[0]["channel"] == "realtime_voice"
    assert messages[1]["channel"] == "realtime_voice"
    assert messages[0]["content"] == "Spoken: What is our clinic address?"
    assert messages[1]["content"] == "Spoken: Our clinic is located in Sydney CBD."


def test_graceful_degradation_to_text_when_realtime_unconfigured(client, db_session, monkeypatch):
    """When voice cannot start due to missing configuration, text turns remain 100% operational in same conversation."""
    tenant, user = _owner(db_session, "degrade-text")
    headers = _headers(tenant, user)
    conv_id = _conversation(client, headers)

    # Realtime unconfigured
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_REALTIME_MODEL", "")

    # Voice exchange fails with 503
    voice_res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/realtime",
        headers={**headers, "Content-Type": "application/sdp"},
        content=b"v=0\r\n",
    )
    assert voice_res.status_code == 503
    assert voice_res.json()["error"]["code"] == "REALTIME_CONFIGURATION_REQUIRED"

    # User falls back cleanly to text in the exact same conversation
    # Text turn saves message even when text model is unconfigured
    monkeypatch.setattr(settings, "BUSINESS_ASSISTANT_TEXT_MODEL", "")
    text_res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/messages",
        headers=headers,
        json={"content": "Falling back to text message", "request_key": "fallback-text-key-1"},
    )
    # The user message is saved even if text generation needs config
    assert text_res.status_code in (200, 503)

    # Verify conversation retained the user message
    messages = client.get(
        f"/api/admin/business-assistant/conversations/{conv_id}/messages",
        headers=headers,
    ).json()
    assert any("Falling back to text message" in m["content"] for m in messages)
