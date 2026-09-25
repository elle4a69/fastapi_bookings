"""Comprehensive tests for Codex Resident Autonomous Agent.

Tests status baseline, deep audit, remediation planning, approval gate enforcement,
safe fix execution, and AI advisory with web research capabilities.
"""

from datetime import datetime, timezone
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.models.tenant import Tenant
from app.models.user import User
from app.models.sms_outbox import SmsOutboundJob
from app.models.sms_message import SmsMessage
from app.models.sms_conversation import SmsConversation
from app.core.security import create_access_token
from app.services.resident_agent import (
    resident_agent_engine,
    remediation_planner,
    safe_fix_executor,
    event_broker,
    web_researcher,
    skill_library,
    sentinel_scheduler,
    alert_dispatcher,
    stress_fuzzer,
    tech_radar,
)


@pytest.fixture
def resident_agent_admin(db_session):
    """Fixture providing an owner user and valid admin headers."""
    tenant = Tenant(
        name="Resident Agent Studio",
        subdomain="resident-agent-tenant",
        subscription_tier="growth",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    admin_user = User(
        tenant_id=tenant.id,
        login="resident_admin",
        password_hash="test_hash",
        role="owner",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(admin_user)

    token = create_access_token({"sub": str(admin_user.id)})
    headers = {
        "X-Tenant": tenant.subdomain,
        "X-Token": token,
    }
    return tenant, admin_user, headers


def test_resident_agent_status_endpoint(client, resident_agent_admin):
    """Verify GET /api/admin/resident-agent/status returns structured health and baseline data."""
    _, _, headers = resident_agent_admin

    response = client.get("/api/admin/resident-agent/status", headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "health_score" in data
    assert isinstance(data["health_score"], int)
    assert 0 <= data["health_score"] <= 100
    assert data["status"] in {"HEALTHY", "DEGRADED", "CRITICAL"}
    assert "telemetry_baseline" in data
    assert "outbox_status" in data
    assert "chatwoot_status" in data
    assert "active_issues" in data
    assert isinstance(data["active_issues"], list)


def test_resident_agent_audit_endpoint(client, resident_agent_admin):
    """Verify POST /api/admin/resident-agent/audit triggers a deep audit across all subsystems."""
    _, _, headers = resident_agent_admin

    response = client.post("/api/admin/resident-agent/audit", headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "health_score" in data
    assert "code_audit" in data
    assert "telemetry_audit" in data
    assert "total_active_issues" in data
    assert data["code_audit"]["passed"] is True or False


def test_resident_agent_plan_fix_endpoint(client, resident_agent_admin):
    """Verify POST /api/admin/resident-agent/plan-fix generates a structured plan with RCA and diffs."""
    _, _, headers = resident_agent_admin

    payload = {
        "issue_id": "ISSUE-SMS-001",
        "issue_title": "Reset Failed SMS Jobs",
        "category": "sms_outbox",
        "context": {"description": "Multiple jobs failed due to transient carrier timeouts."},
    }

    response = client.post("/api/admin/resident-agent/plan-fix", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK

    plan = response.json()
    assert plan["issue_id"] == "ISSUE-SMS-001"
    assert "plan_id" in plan
    assert "root_cause_analysis" in plan
    assert len(plan["root_cause_analysis"]) > 10
    assert "proposed_modifications" in plan
    assert isinstance(plan["proposed_modifications"], list)
    assert len(plan["proposed_modifications"]) >= 1
    assert "diff" in plan["proposed_modifications"][0]
    assert "verification_steps" in plan
    assert "rollback_steps" in plan
    assert plan["requires_approval"] is True


def test_resident_agent_execute_fix_enforces_approval_gate(client, resident_agent_admin):
    """Verify POST /api/admin/resident-agent/execute-fix strictly rejects unapproved plans."""
    _, _, headers = resident_agent_admin

    # First generate a plan
    plan_res = client.post(
        "/api/admin/resident-agent/plan-fix",
        json={"issue_id": "ISSUE-TEL-001"},
        headers=headers,
    )
    assert plan_res.status_code == status.HTTP_200_OK
    plan_id = plan_res.json()["plan_id"]

    # Attempt to execute with approved=False -> must return 400 Bad Request
    unapproved_payload = {
        "plan_id": plan_id,
        "approved": False,
        "simulate_only": False,
    }
    reject_res = client.post("/api/admin/resident-agent/execute-fix", json=unapproved_payload, headers=headers)
    assert reject_res.status_code == status.HTTP_400_BAD_REQUEST
    error_msg = reject_res.json().get("detail") or reject_res.json().get("error", {}).get("message", "")
    assert "approval" in error_msg.lower()

    # Now execute with explicit approved=True -> must succeed
    approved_payload = {
        "plan_id": plan_id,
        "approved": True,
        "simulate_only": True,
    }
    exec_res = client.post("/api/admin/resident-agent/execute-fix", json=approved_payload, headers=headers)
    assert exec_res.status_code == status.HTTP_200_OK
    exec_data = exec_res.json()
    assert exec_data["success"] is True
    assert exec_data["status"] == "EXECUTED"


def test_resident_agent_advisory_endpoint(client, resident_agent_admin):
    """Verify POST /api/admin/resident-agent/advisory returns architectural recommendations."""
    _, _, headers = resident_agent_admin

    payload = {
        "prompt": "How can we optimize SMS outbox concurrency and prevent message double-sends?",
        "enable_web_research": True,
        "domain": "twilio",
    }

    response = client.post("/api/admin/resident-agent/advisory", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["prompt"] == payload["prompt"]
    assert "advisory_markdown" in data
    assert len(data["advisory_markdown"]) > 20
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)
    assert len(data["recommendations"]) > 0


@pytest.mark.asyncio
async def test_event_broker_publish_and_history():
    """Verify event broker records events and maintains event history."""
    event = await event_broker.publish(
        event_type="thought",
        data="Autonomous reasoning step verified in test suite.",
        title="Unit Test Event",
    )
    assert event["type"] == "thought"
    assert event["title"] == "Unit Test Event"

    history = event_broker.get_recent_history(limit=10)
    assert any(ev["title"] == "Unit Test Event" for ev in history)


def test_skill_library_discovery_and_surgical_read(client, resident_agent_admin):
    """Verify find_relevant_skills discovers skills and read_skill loads SKILL.md on demand."""
    _, _, headers = resident_agent_admin

    # Direct service tests
    skills = skill_library.find_relevant_skills(query="fastapi async", top_k=3)
    assert isinstance(skills, list)
    if skills:
        assert "skill_id" in skills[0]
        assert "name" in skills[0]
        assert "description" in skills[0]
        assert "path" in skills[0]

        # Test on-demand surgical read
        content = skill_library.read_skill(skills[0]["skill_id"])
        assert isinstance(content, str)
        assert len(content) > 10

    # API endpoints
    search_res = client.get("/api/admin/resident-agent/skills?query=fastapi&top_k=2", headers=headers)
    assert search_res.status_code == status.HTTP_200_OK
    api_skills = search_res.json()
    assert isinstance(api_skills, list)

    if api_skills:
        skill_id = api_skills[0]["skill_id"]
        detail_res = client.get(f"/api/admin/resident-agent/skills/{skill_id}", headers=headers)
        assert detail_res.status_code == status.HTTP_200_OK
        detail_data = detail_res.json()
        assert detail_data["skill_id"] == skill_id
        assert len(detail_data["content"]) > 10


@pytest.mark.asyncio
async def test_stress_fuzzer_race_condition_simulation(db_session):
    """Verify concurrency fuzzer enforces single-winner lock integrity with zero double-bookings."""
    fuzz_report = await stress_fuzzer.run_race_condition_test(
        db=db_session,
        concurrency=10,
    )

    assert fuzz_report["concurrency_tested"] == 10
    assert fuzz_report["successful_bookings"] == 1
    assert fuzz_report["conflicts_prevented"] == 9
    assert fuzz_report["double_bookings_occurred"] == 0
    assert fuzz_report["double_bookings_prevented_pct"] == 100.0
    assert fuzz_report["transactional_integrity_verified"] is True
    assert fuzz_report["avg_latency_ms"] >= 0.0


def test_stress_fuzzer_endpoint(client, resident_agent_admin):
    """Verify POST /api/admin/resident-agent/fuzz/race-condition endpoint."""
    _, _, headers = resident_agent_admin

    response = client.post(
        "/api/admin/resident-agent/fuzz/race-condition",
        json={"concurrency": 6},
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["concurrency_tested"] == 6
    assert data["successful_bookings"] == 1
    assert data["conflicts_prevented"] == 5
    assert data["double_bookings_prevented_pct"] == 100.0
    assert data["transactional_integrity_verified"] is True


def test_remote_action_approval_execution(client, resident_agent_admin):
    """Verify POST /api/admin/resident-agent/remote-action approves and executes remediation."""
    _, _, headers = resident_agent_admin

    # 1. Create a plan to approve
    plan_res = client.post(
        "/api/admin/resident-agent/plan-fix",
        json={"issue_id": "ISSUE-TEL-001"},
        headers=headers,
    )
    assert plan_res.status_code == status.HTTP_200_OK
    plan_id = plan_res.json()["plan_id"]

    # 2. Test invalid command rejection
    bad_cmd_res = client.post(
        "/api/admin/resident-agent/remote-action",
        json={"command": "INVALID_CMD_FORMAT"},
        headers=headers,
    )
    assert bad_cmd_res.status_code == status.HTTP_400_BAD_REQUEST

    # 3. Test structured command APPROVE <plan_id>
    remote_res = client.post(
        "/api/admin/resident-agent/remote-action",
        json={"command": f"APPROVE {plan_id}"},
        headers=headers,
    )
    assert remote_res.status_code == status.HTTP_200_OK
    data = remote_res.json()
    assert data["success"] is True
    assert data["action"] == "approve"
    assert data["plan_id"] == plan_id


def test_tech_radar_endpoint(client, resident_agent_admin):
    """Verify GET /api/admin/resident-agent/tech-radar returns market benchmarks."""
    _, _, headers = resident_agent_admin

    response = client.get("/api/admin/resident-agent/tech-radar", headers=headers)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "our_platform" in data
    assert "competitors" in data
    assert len(data["competitors"]) >= 2
    competitor_names = [c["name"] for c in data["competitors"]]
    assert "Fresha" in competitor_names
    assert "Calendly" in competitor_names

    assert "feature_gap_matrix" in data
    assert "expansion_proposals" in data
    assert "retention_strategies" in data


@pytest.mark.asyncio
async def test_sentinel_scheduler_sweep(db_session):
    """Verify autonomous sentinel sweep audits subsystems cleanly."""
    sweep_res = await sentinel_scheduler.run_sweep(db=db_session)
    assert "sweep_id" in sweep_res
    assert "status" in sweep_res
    assert "subsystems" in sweep_res
    assert "sms_outbox" in sweep_res["subsystems"]
    assert "chatwoot" in sweep_res["subsystems"]
    assert "database" in sweep_res["subsystems"]
    assert sweep_res["subsystems"]["database"]["healthy"] is True

