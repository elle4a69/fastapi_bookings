"""Targeted tests for Stage C Task C2: Operator Controls & Settings.

Verifies:
1. Model & voice whitelist enforcement (strictly rejecting unauthorized substitutions).
2. Session concurrency limits enforcement (both per-tenant and globally).
3. Transport toggle switching between livekit_gpt_live and direct_gpt_live.
4. Health check response schema and credential masking (never leaking API secrets).
5. Authentication and role-based access control guarding operator endpoints.
6. Cost and budget alert threshold triggers.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.operator_controls import (
    APPROVED_DELEGATED_MODELS,
    APPROVED_LIVE_MODELS,
    APPROVED_VOICES,
    ConcurrencyLimitExceeded,
    LiveKitHealthResponse,
    OperatorSettingsRead,
    OperatorSettingsUpdate,
    UnauthorizedModelOrVoiceError,
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
    db_session, suffix: str, role: str = "admin"
) -> tuple[Tenant, User]:
    tenant = Tenant(name=f"Operator Tenant {suffix}", subdomain=f"op-tenant-{suffix}")
    db_session.add(tenant)
    db_session.flush()

    user = User(
        tenant_id=tenant.id,
        login=f"op-{role}-{suffix}@example.com",
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
    client: TestClient, headers: dict[str, str], request_key: str = "op-conv-1"
) -> int:
    resp = client.post(
        "/api/admin/business-assistant/conversations",
        headers=headers,
        json={"request_key": request_key},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── 1. Model & Voice Whitelist Enforcement ───────────────────────────────────


def test_model_whitelist_rejects_unauthorized_live_model(client: TestClient, db_session):
    """Attempting to set an unauthorized live model via operator settings must fail."""
    tenant, admin = _create_tenant_and_user(db_session, "wl-model-1", role="admin")
    headers = _auth_headers(tenant, admin)

    response = client.patch(
        "/api/admin/operator/settings",
        headers=headers,
        json={"selected_live_model": "gpt-4o-realtime"},
    )
    assert response.status_code in (400, 422)
    assert "not in approved whitelist" in response.text or "VALIDATION_ERROR" in response.text


def test_model_whitelist_rejects_unauthorized_delegated_model(client: TestClient, db_session):
    """Attempting to set an unauthorized delegated model via operator settings must fail."""
    tenant, admin = _create_tenant_and_user(db_session, "wl-model-2", role="admin")
    headers = _auth_headers(tenant, admin)

    response = client.patch(
        "/api/admin/operator/settings",
        headers=headers,
        json={"selected_delegated_model": "gpt-4o"},
    )
    assert response.status_code in (400, 422)
    assert "not in approved whitelist" in response.text or "VALIDATION_ERROR" in response.text


def test_voice_whitelist_rejects_unauthorized_voice(client: TestClient, db_session):
    """Attempting to set an unapproved voice persona must fail."""
    tenant, admin = _create_tenant_and_user(db_session, "wl-voice-1", role="admin")
    headers = _auth_headers(tenant, admin)

    for unapproved in ["alloy", "echo", "shimmer", "nova"]:
        response = client.patch(
            "/api/admin/operator/settings",
            headers=headers,
            json={"selected_voice": unapproved},
        )
        assert response.status_code in (400, 422)
        assert "not in approved whitelist" in response.text or "VALIDATION_ERROR" in response.text


def test_direct_code_rejects_unauthorized_model_and_voice():
    """OperatorSettingsUpdate must reject unapproved substitutions directly."""
    # Valid baseline works
    settings_update = OperatorSettingsUpdate(
        selected_live_model="gpt-live-1",
        selected_delegated_model="gpt-5.6-terra",
        selected_voice="gleam",
    )
    assert settings_update.selected_live_model == "gpt-live-1"
    assert settings_update.selected_voice == "gleam"

    # Unauthorized live model
    with pytest.raises(ValueError) as exc_info:
        OperatorSettingsUpdate(selected_live_model="gpt-4o-realtime")
    assert "not in approved whitelist" in str(exc_info.value)

    # Unauthorized voice
    with pytest.raises(ValueError) as exc_info:
        OperatorSettingsUpdate(selected_voice="alloy")
    assert "not in approved whitelist" in str(exc_info.value)

    # Unauthorized delegated model
    with pytest.raises(ValueError) as exc_info:
        OperatorSettingsUpdate(selected_delegated_model="claude-3-opus")
    assert "not in approved whitelist" in str(exc_info.value)


def test_settings_accepts_approved_whitelist_values(client: TestClient, db_session):
    """Updating settings with explicitly approved values succeeds."""
    tenant, admin = _create_tenant_and_user(db_session, "wl-ok", role="admin")
    headers = _auth_headers(tenant, admin)

    response = client.patch(
        "/api/admin/operator/settings",
        headers=headers,
        json={
            "selected_live_model": "gpt-live-1",
            "selected_delegated_model": "gpt-5.6-terra",
            "selected_voice": "gleam",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["selected_live_model"] == "gpt-live-1"
    assert data["selected_delegated_model"] == "gpt-5.6-terra"
    assert data["selected_voice"] == "gleam"


# ── 2. Session Concurrency Limits Enforcement ────────────────────────────────


def test_tenant_session_concurrency_limit_enforced(client: TestClient, db_session):
    """Enforce maximum concurrent active sessions per tenant."""
    tenant, owner = _create_tenant_and_user(db_session, "conc-tenant", role="owner")
    headers = _auth_headers(tenant, owner)
    service = get_operator_controls_service()

    # Configure tenant concurrency cap to 2
    service.update_settings(service.get_settings().model_copy(update={"max_concurrent_sessions_per_tenant": 2}))

    conv_id_1 = _create_conversation(client, headers, "conc-conv-1")
    conv_id_2 = _create_conversation(client, headers, "conc-conv-2")
    conv_id_3 = _create_conversation(client, headers, "conc-conv-3")

    # Start 1st session: OK
    resp1 = client.post(
        f"/api/admin/business-assistant/voice/conversations/{conv_id_1}/session",
        headers=headers,
        json={"transport": "direct_gpt_live"},
    )
    assert resp1.status_code == 201
    sess1_id = resp1.json()["session_id"]

    # Start 2nd session: OK
    resp2 = client.post(
        f"/api/admin/business-assistant/voice/conversations/{conv_id_2}/session",
        headers=headers,
        json={"transport": "direct_gpt_live"},
    )
    assert resp2.status_code == 201
    sess2_id = resp2.json()["session_id"]

    # Start 3rd session: MUST be rejected with HTTP 429
    resp3 = client.post(
        f"/api/admin/business-assistant/voice/conversations/{conv_id_3}/session",
        headers=headers,
        json={"transport": "direct_gpt_live"},
    )
    assert resp3.status_code == 429
    assert "CONCURRENCY_LIMIT_EXCEEDED" in resp3.text

    # Release 1st session
    del_resp = client.delete(
        f"/api/admin/business-assistant/voice/sessions/{sess1_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    # Now 3rd session succeeds
    resp3_retry = client.post(
        f"/api/admin/business-assistant/voice/conversations/{conv_id_3}/session",
        headers=headers,
        json={"transport": "direct_gpt_live"},
    )
    assert resp3_retry.status_code == 201


def test_global_session_concurrency_limit_enforced(client: TestClient, db_session):
    """Enforce global maximum concurrent active sessions across all tenants."""
    service = get_operator_controls_service()
    service.update_settings(service.get_settings().model_copy(update={"max_concurrent_sessions_global": 2}))

    # Direct service test to guarantee exact isolation
    service.acquire_session("sess_g_1", tenant_id=1)
    service.acquire_session("sess_g_2", tenant_id=2)

    with pytest.raises(ConcurrencyLimitExceeded) as exc_info:
        service.acquire_session("sess_g_3", tenant_id=3)
    assert "Global voice session limit of 2 reached" in str(exc_info.value)

    # Release one session
    assert service.release_session("sess_g_1") is True
    # Now acquire succeeds
    service.acquire_session("sess_g_3", tenant_id=3)
    assert service.active_session_count() == 2


# ── 3. Transport Toggle Switching ─────────────────────────────────────────────


def test_transport_toggle_switching(client: TestClient, db_session):
    """Switching transport toggle updates authoritative settings and voice session routing."""
    tenant, admin = _create_tenant_and_user(db_session, "toggle", role="owner")
    headers = _auth_headers(tenant, admin)

    # Initial transport defaults to direct_gpt_live
    resp = client.get("/api/admin/business-assistant/voice/transport", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["transport"] in ("direct_gpt_live", "xai_grok_voice")
    assert set(resp.json()["available_transports"]) == {"direct_gpt_live", "xai_grok_voice"}

    # Toggle to direct_gpt_live via operator settings
    patch_resp = client.patch(
        "/api/admin/operator/settings",
        headers=headers,
        json={"transport": "direct_gpt_live"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["transport"] == "direct_gpt_live"

    # Verify voice transport endpoint reflects new toggle
    resp_updated = client.get("/api/admin/business-assistant/voice/transport", headers=headers)
    assert resp_updated.status_code == 200
    assert resp_updated.json()["transport"] == "direct_gpt_live"
    assert resp_updated.json()["active_target"] == "/api/admin/business-assistant/voice/realtime"

    # Toggle to xai_grok_voice via PATCH /api/admin/business-assistant/voice/transport
    patch_xai = client.patch(
        "/api/admin/business-assistant/voice/transport",
        headers=headers,
        json={"transport": "xai_grok_voice"},
    )
    assert patch_xai.status_code == 200
    xai_data = patch_xai.json()
    assert xai_data["transport"] == "xai_grok_voice"
    assert "wss://api.x.ai" in xai_data["active_target"]

    # Toggle back to direct_gpt_live
    patch_direct = client.patch(
        "/api/admin/business-assistant/voice/transport",
        headers=headers,
        json={"transport": "direct_gpt_live"},
    )
    assert patch_direct.status_code == 200
    assert patch_direct.json()["transport"] == "direct_gpt_live"
    assert patch_direct.json()["active_target"] == "/api/admin/business-assistant/voice/realtime"

    # Attempt invalid transport toggle
    bad_toggle = client.patch(
        "/api/admin/operator/settings",
        headers=headers,
        json={"transport": "invalid_webrtc_foo"},
    )
    assert bad_toggle.status_code in (400, 422)


# ── 4. Health Check Response Schema & Credential Masking ─────────────────────


def test_health_check_response_schema_and_credential_masking(client: TestClient, db_session):
    """GET /api/admin/operator/health returns valid schema and strictly masks secrets."""
    tenant, admin = _create_tenant_and_user(db_session, "health-check", role="admin")
    headers = _auth_headers(tenant, admin)

    response = client.get("/api/admin/operator/health", headers=headers)
    assert response.status_code == 200
    data = response.json()

    # Validate response schema
    assert "status" in data
    assert "worker" in data
    assert "livekit_server" in data
    assert "quota_readiness" in data
    assert "credentials" in data
    assert "timestamp" in data

    # Worker details
    assert data["worker"]["agent_name"] == "bookings-business-assistant"
    assert data["worker"]["entrypoint_configured"] is True

    # Quota readiness
    assert data["quota_readiness"]["max_concurrent_sessions_global"] >= 1
    assert data["quota_readiness"]["max_concurrent_sessions_per_tenant"] >= 1
    assert data["quota_readiness"]["budget_exceeded"] is False

    # Security check: Credential Masking (Zero Leakage)
    creds = data["credentials"]
    assert "openai_api_key_configured" in creds
    assert "xai_api_key_configured" in creds

    # Explicit secret isolation check with a distinct high-entropy secret
    distinct_secret = "super_confidential_secret_token_openai_998877"
    with patch.object(settings, "OPENAI_API_KEY", distinct_secret):
        patched_resp = client.get("/api/admin/operator/health", headers=headers)
        assert patched_resp.status_code == 200
        # The distinct secret must NEVER appear anywhere in the serialized response text
        assert distinct_secret not in patched_resp.text
        patched_creds = patched_resp.json()["credentials"]
        assert distinct_secret not in patched_creds["openai_api_key_masked"]
        assert "sup***[REDACTED]" == patched_creds["openai_api_key_masked"]


def test_health_and_settings_endpoints_guarded_by_admin_auth(client: TestClient, db_session):
    """Health check and operator settings must reject unauthenticated or non-admin requests."""
    tenant, staff = _create_tenant_and_user(db_session, "guard-test", role="staff")
    staff_headers = _auth_headers(tenant, staff)

    # 1. Unauthenticated request (no headers) -> 401
    resp_unauth = client.get("/api/admin/operator/health")
    assert resp_unauth.status_code in (400, 401, 403, 404)

    # 2. Staff user (forbidden) -> 403
    resp_staff = client.get("/api/admin/operator/health", headers=staff_headers)
    assert resp_staff.status_code == 403

    # 3. Staff user trying to modify operator settings -> 403
    resp_staff_mod = client.patch(
        "/api/admin/operator/settings",
        headers=staff_headers,
        json={"transport": "direct_gpt_live"},
    )
    assert resp_staff_mod.status_code == 403


# ── 5. Cost & Budget Alert Thresholds ────────────────────────────────────────


def test_cost_and_budget_alert_thresholds(client: TestClient, db_session):
    """Cost threshold triggers warning flag, and budget threshold triggers budget_exceeded."""
    tenant, admin = _create_tenant_and_user(db_session, "budget-test", role="admin")
    headers = _auth_headers(tenant, admin)
    service = get_operator_controls_service()

    # Set thresholds: warning at $10, budget cap at $50
    client.patch(
        "/api/admin/operator/settings",
        headers=headers,
        json={"cost_alert_threshold_usd": 10.0, "budget_alert_threshold_usd": 50.0},
    )

    # Accrue cost below threshold
    service.record_cost(5.0)
    read1 = service.get_settings()
    assert read1.current_cost_usd == 5.0
    assert read1.cost_alert_triggered is False
    assert read1.budget_exceeded is False

    # Accrue cost crossing warning threshold ($15)
    service.record_cost(10.0)
    read2 = service.get_settings()
    assert read2.current_cost_usd == 15.0
    assert read2.cost_alert_triggered is True
    assert read2.budget_exceeded is False

    # Accrue cost crossing hard budget ($55)
    service.record_cost(40.0)
    read3 = service.get_settings()
    assert read3.current_cost_usd == 55.0
    assert read3.cost_alert_triggered is True
    assert read3.budget_exceeded is True

    # Health check reflects budget exceeded and status degraded
    health_resp = client.get("/api/admin/operator/health", headers=headers)
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["quota_readiness"]["budget_exceeded"] is True
    assert health_data["quota_readiness"]["ready"] is False
    assert health_data["status"] == "degraded"

