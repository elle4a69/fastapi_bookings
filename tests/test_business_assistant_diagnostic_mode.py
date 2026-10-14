"""Comprehensive test suite for Business Assistant Diagnostic Mode and Real Assistant Error Logging.

Tests cover:
1. GET & PATCH /api/admin/business-assistant/diagnostic-mode (tenant and user scoped).
2. GET /api/admin/business-assistant/errors (tenant scoped, sanitized, filtered).
3. POST /api/admin/business-assistant/conversations/{id}/client-state (snapshot & error log creation).
4. Real diagnostic_report tool execution executing live 8-step runbook (ZERO MOCKS).
5. Dual prompt configuration in build_gpt_live_session_config (diagnostic vs standard).
6. Telemetry and PII / credential scrubbing in assistant error logging.
"""

import pytest
from app.core.security import create_access_token
from app.models.business_assistant import AssistantErrorLog, BusinessAssistantClientSnapshot, BusinessAssistantDiagnosticSetting
from app.models.tenant import Tenant
from app.models.user import User
from app.services.business_assistant.gpt_live.runtime import (
    GPT_LIVE_APP_INSTRUCTIONS,
    GPT_LIVE_DIAGNOSTIC_INSTRUCTIONS,
    TERRA_DIAGNOSTIC_INSTRUCTIONS,
    build_gpt_live_session_config,
)
from app.services.business_assistant.service import BusinessAssistantService


def _create_tenant_and_user(db_session, suffix: str) -> tuple[Tenant, User]:
    tenant = Tenant(name=f"Diag Tenant {suffix}", subdomain=f"diag-{suffix.lower()}")
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, login=f"diag-owner-{suffix.lower()}", password_hash="hash", role="owner")
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _auth_headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


def test_diagnostic_mode_get_and_patch(client, db_session):
    """Verify GET and PATCH /api/admin/business-assistant/diagnostic-mode with tenant/user isolation."""
    tenant1, user1 = _create_tenant_and_user(db_session, "user1")
    tenant2, user2 = _create_tenant_and_user(db_session, "user2")

    headers1 = _auth_headers(tenant1, user1)
    headers2 = _auth_headers(tenant2, user2)

    # 1. Default for tenant1/user1 is False
    res = client.get("/api/admin/business-assistant/diagnostic-mode", headers=headers1)
    assert res.status_code == 200
    assert res.json()["enabled"] is False
    assert res.json()["diagnostic_mode"] is False

    # 2. Enable diagnostic mode for tenant1/user1
    res = client.patch(
        "/api/admin/business-assistant/diagnostic-mode",
        headers=headers1,
        json={"enabled": True},
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is True
    assert res.json()["diagnostic_mode"] is True

    # 3. GET reflects updated state for tenant1/user1
    res = client.get("/api/admin/business-assistant/diagnostic-mode", headers=headers1)
    assert res.status_code == 200
    assert res.json()["enabled"] is True
    assert res.json()["diagnostic_mode"] is True

    # 4. Tenant2/user2 remains isolated and False
    res = client.get("/api/admin/business-assistant/diagnostic-mode", headers=headers2)
    assert res.status_code == 200
    assert res.json()["enabled"] is False
    assert res.json()["diagnostic_mode"] is False

    # 5. Disable diagnostic mode for tenant1/user1
    res = client.patch(
        "/api/admin/business-assistant/diagnostic-mode",
        headers=headers1,
        json={"enabled": False},
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is False
    assert res.json()["diagnostic_mode"] is False


def test_client_snapshot_and_error_logging(client, db_session):
    """Verify POST /conversations/{id}/client-state records snapshot and error log."""
    tenant, user = _create_tenant_and_user(db_session, "snapshot")
    headers = _auth_headers(tenant, user)

    # Create a conversation
    conv_res = client.post(
        "/api/admin/business-assistant/conversations",
        headers=headers,
        json={"title": "Diagnostic Test Conv", "request_key": "diag-conv-1"},
    )
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # 1. Post a healthy client state snapshot
    snap_res = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/client-state",
        headers=headers,
        json={
            "client_status": "connected",
            "webrtc_state": "local_livekit",
            "metadata_json": {"latency_ms": 42},
        },
    )
    assert snap_res.status_code == 200
    assert snap_res.json()["status"] == "ok"

    # 2. Post a state with an error message containing sensitive data (Bearer token, sk- key, email)
    sensitive_msg = "Connection failed sk-proj-1234567890abcdef12345678 with Bearer secrettoken123 and test@example.com"
    snap_res2 = client.post(
        f"/api/admin/business-assistant/conversations/{conv_id}/client-state",
        headers=headers,
        json={
            "client_status": "error",
            "webrtc_state": "direct_gpt_live",
            "last_error": sensitive_msg,
            "metadata_json": {"attempt": 3},
        },
    )
    assert snap_res2.status_code == 200
    assert snap_res2.json()["status"] == "ok"

    # 3. Query GET /api/admin/business-assistant/errors
    errs_res = client.get("/api/admin/business-assistant/errors", headers=headers)
    assert errs_res.status_code == 200
    errors = errs_res.json()
    assert len(errors) >= 1

    last_err = errors[0]
    assert last_err["source"] == "client_webrtc"
    assert last_err["error_code"] == "CLIENT_ERROR"
    assert last_err["conversation_id"] == conv_id
    # Assert scrubbing: secret tokens and emails are sanitized
    assert "sk-proj-" not in last_err["message"]
    assert "secrettoken123" not in last_err["message"]
    assert "[REDACTED_KEY]" in last_err["message"]
    assert "[REDACTED_TOKEN]" in last_err["message"]
    assert "[REDACTED_EMAIL]" in last_err["message"]


def test_errors_tenant_scoping(client, db_session):
    """Verify assistant error logs are strictly scoped by tenant."""
    tenantA, userA = _create_tenant_and_user(db_session, "tenantA")
    tenantB, userB = _create_tenant_and_user(db_session, "tenantB")

    serviceA = BusinessAssistantService(db_session, tenantA.id, userA.id)
    serviceB = BusinessAssistantService(db_session, tenantB.id, userB.id)

    serviceA.record_assistant_error(
        source="unit_test",
        error_code="TENANT_A_ERR",
        message="Failure on tenant A",
    )
    serviceB.record_assistant_error(
        source="unit_test",
        error_code="TENANT_B_ERR",
        message="Failure on tenant B",
    )

    headersA = _auth_headers(tenantA, userA)
    headersB = _auth_headers(tenantB, userB)

    resA = client.get("/api/admin/business-assistant/errors", headers=headersA)
    assert resA.status_code == 200
    codesA = [e["error_code"] for e in resA.json()]
    assert "TENANT_A_ERR" in codesA
    assert "TENANT_B_ERR" not in codesA

    resB = client.get("/api/admin/business-assistant/errors", headers=headersB)
    assert resB.status_code == 200
    codesB = [e["error_code"] for e in resB.json()]
    assert "TENANT_B_ERR" in codesB
    assert "TENANT_A_ERR" not in codesB


def test_diagnostic_report_tool_executes_runbook(db_session):
    """Verify diagnostic_report executes live 8-step runbook and returns structured report."""
    tenant, user = _create_tenant_and_user(db_session, "runbook")
    service = BusinessAssistantService(db_session, tenant.id, user.id)

    report_output = service.run_diagnostic_report()
    assert isinstance(report_output, dict)

    # Verify structured runbook sections
    assert "verdict" in report_output
    assert "summary" in report_output
    assert "working" in report_output
    assert "not_working" in report_output
    assert "cannot_do" in report_output
    assert "next_step" in report_output
    assert "details" in report_output

    details = report_output["details"]
    assert "step_1_session" in details
    assert "step_2_tool_inventory" in details
    assert "step_3_tool_log" in details
    assert "step_4_ui_state" in details
    assert "step_5_navigation" in details
    assert "step_6_onboarding" in details
    assert "step_7_errors_concurrency" in details
    assert "step_8_permissions" in details

    # Verify live checks were performed
    assert details["step_8_permissions"]["user_id"] == user.id
    assert details["step_8_permissions"]["role"] == "owner"
    assert details["step_8_permissions"]["has_settings_write"] is True
    assert details["step_1_session"]["active_sessions_tenant"] == 0


def test_dual_prompt_configuration():
    """Verify dual prompts for standard vs diagnostic mode."""
    # Standard Mode
    cfg_std = build_gpt_live_session_config(diagnostic_mode=False)
    assert "tools" not in cfg_std
    tool_names_std = [t["name"] for t in cfg_std["delegation"]["responses"]["tools"] if t.get("type") == "function"]
    assert "diagnostic_report" not in tool_names_std

    # Diagnostic Mode
    cfg_diag = build_gpt_live_session_config(diagnostic_mode=True)
    assert "tools" not in cfg_diag
    assert cfg_diag["instructions"] == GPT_LIVE_DIAGNOSTIC_INSTRUCTIONS
    assert "DIAGNOSTIC MODE" in cfg_diag["instructions"]
    tool_names_diag = [t["name"] for t in cfg_diag["delegation"]["responses"]["tools"] if t.get("type") == "function"]
    assert "diagnostic_report" in tool_names_diag

    # Verify Terra instructions constants exist and contain correct mode guidance
    assert "8-step runbook" in TERRA_DIAGNOSTIC_INSTRUCTIONS
    assert "Verdict" in TERRA_DIAGNOSTIC_INSTRUCTIONS


def test_diagnostic_report_tool_creates_conversation_message(db_session):
    """Verify execute_tool with name='diagnostic_report' persists structured 8-step Markdown in conversation_messages."""
    from app.models.business_assistant import BusinessAssistantMessage

    tenant, user = _create_tenant_and_user(db_session, "msgdiag")
    service = BusinessAssistantService(db_session, tenant.id, user.id)

    # Create conversation
    conv = service.create_conversation(title="Diagnostic Session")

    # Execute diagnostic_report tool
    res = service.execute_tool(
        conversation_id=conv.id,
        name="diagnostic_report",
        arguments={"include_tool_log": True},
    )

    assert res.get("status") == "ok"
    assert "report" in res

    # Verify a message was persisted into conversation_messages
    messages = (
        db_session.query(BusinessAssistantMessage)
        .filter(BusinessAssistantMessage.conversation_id == conv.id)
        .all()
    )
    assert len(messages) == 1
    msg = messages[0]
    assert msg.role == "business_assistant"
    assert msg.channel == "realtime_voice"
    assert "### System Diagnostic Report" in msg.content
    assert "**Verdict**:" in msg.content
    assert "#### Working Subsystems" in msg.content
    assert "#### Issues & Degradations" in msg.content
    assert "#### Operating Boundaries" in msg.content
    assert "#### Recommended Next Steps" in msg.content
    assert "<details>" in msg.content
    assert "<summary>Full 8-Step Runbook Details</summary>" in msg.content


