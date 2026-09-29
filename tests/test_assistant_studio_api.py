"""Real integration tests for Assistant Studio Backend API router (/api/admin/assistant-studio).

Strictly enforces AGENTS.md Rule 3:
- Zero mock implementations.
- Real database state mutations verified.
- Cross-tenant authorization boundaries verified.
- Live tool execution and PromptPolicyAssembler integration verified.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.models.conversation import ChannelAccount, ChannelType, Conversation, Message, MessageDirection, MessageSource
from app.models.curated_memory import CuratedMemory, KnowledgeProposal
from app.models.location import Location
from app.models.message_style_example import MessageStyleExample
from app.models.provider import Provider
from app.models.service import Service
from app.models.sms_bootcamp import SmsBootcampSettings
from app.models.sms_knowledge import SmsPromptProfile
from app.models.tenant import Tenant
from app.models.user import User


def _auth_headers(tenant: Tenant, admin_user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(admin_user.id)})
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": token,
    }


@pytest.fixture
def studio_env(db_session):
    """Seed multi-tenant environment with providers, services, locations, and users."""
    tenant_a = Tenant(name="Sydney Wellness Studio", subdomain="sydney-wellness")
    tenant_b = Tenant(name="Melbourne Holistic Care", subdomain="melbourne-holistic")
    db_session.add_all([tenant_a, tenant_b])
    db_session.flush()

    admin_a = User(
        tenant_id=tenant_a.id,
        login="admin-sydney@wellness.test",
        password_hash="pw-hash-a",
        role="admin",
    )
    admin_b = User(
        tenant_id=tenant_b.id,
        login="admin-melbourne@holistic.test",
        password_hash="pw-hash-b",
        role="admin",
    )
    db_session.add_all([admin_a, admin_b])
    db_session.flush()

    prov_a = Provider(
        tenant_id=tenant_a.id,
        name="Dr. Alex Mercer",
        active=True,
        in_call_address="Suite 4, 120 Castlereagh St, Sydney NSW 2000",
    )
    prov_b = Provider(
        tenant_id=tenant_b.id,
        name="Dr. Sarah Connor",
        active=True,
        in_call_address="50 Collins St, Melbourne VIC 3000",
    )
    db_session.add_all([prov_a, prov_b])
    db_session.flush()

    loc_a = Location(
        tenant_id=tenant_a.id,
        name="Sydney CBD Clinic",
        address="Suite 4, 120 Castlereagh St, Sydney NSW 2000",
        timezone="Australia/Sydney",
        active=True,
    )
    db_session.add(loc_a)
    db_session.flush()

    srv_a = Service(
        tenant_id=tenant_a.id,
        name="Swedish Remedial Massage",
        price=140.00,
        duration=60,
        active=True,
    )
    db_session.add(srv_a)
    db_session.flush()

    # Channel Account for Tenant A
    chan_a = ChannelAccount(
        tenant_id=tenant_a.id,
        provider_id=prov_a.id,
        channel_type=ChannelType.SMS,
        inbox_name="Sydney SMS Helpline",
        account_identifier="+61491570006",
        is_active=True,
    )
    db_session.add(chan_a)
    db_session.flush()

    # Active Conversation with messages
    conv_a = Conversation(
        tenant_id=tenant_a.id,
        provider_id=prov_a.id,
        channel_account_id=chan_a.id,
        contact_identifier="+61400111222",
        status="active",
    )
    db_session.add(conv_a)
    db_session.flush()

    msg_a = Message(
        conversation_id=conv_a.id,
        tenant_id=tenant_a.id,
        direction=MessageDirection.INBOUND,
        source=MessageSource.CLIENT,
        content="Hi, do you have any Swedish massage slots tomorrow?",
    )
    db_session.add(msg_a)

    # Curated Memory
    curated_a = CuratedMemory(
        tenant_id=tenant_a.id,
        provider_id=prov_a.id,
        category="hours_and_facilities",
        user_query="Is there elevator access at the Sydney clinic?",
        ideal_response="Yes, elevator access is available directly to Suite 4 from the lobby.",
        knowledge_kind="durable_fact",
        authority="owner_verified",
        status="active",
        conflict_state="clear",
    )
    db_session.add(curated_a)

    # MessageStyleExample
    mse_a = MessageStyleExample(
        tenant_id=tenant_a.id,
        provider_id=prov_a.id,
        intent="greeting",
        client_message="Hello there!",
        assistant_reply="Welcome to Sydney Wellness Studio! How may I assist you with scheduling today?",
        category="procedural",
        tags=["greeting"],
        is_approved=True,
        is_active=True,
    )
    db_session.add(mse_a)

    # KnowledgeProposal
    prop_a = KnowledgeProposal(
        tenant_id=tenant_a.id,
        provider_id=prov_a.id,
        proposal_type="add",
        category="parking",
        user_query="Where can I park near the clinic?",
        proposed_response="There is a secure commercial parking station 50m away on Castlereagh Street.",
        fingerprint="fp_test_parking_query_001",
        reason_code="new_candidate",
        status="pending",
        knowledge_kind="durable_fact",
        confidence_score=0.92,
    )
    db_session.add(prop_a)

    db_session.commit()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "prov_a": prov_a,
        "prov_b": prov_b,
        "loc_a": loc_a,
        "srv_a": srv_a,
        "chan_a": chan_a,
        "conv_a": conv_a,
        "curated_a": curated_a,
        "mse_a": mse_a,
        "prop_a": prop_a,
    }


def test_overview_statistics_returns_live_counts(studio_env, client: TestClient):
    """GET /api/admin/assistant-studio/overview must return real live DB counts."""
    env = studio_env
    headers = _auth_headers(env["tenant_a"], env["admin_a"])

    resp = client.get("/api/admin/assistant-studio/overview", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["channel_accounts_count"] == 1
    assert data["active_conversations_count"] == 1
    assert data["curated_facts_count"] == 1
    assert data["approved_examples_count"] == 1
    assert data["message_volume"] == 1
    assert data["pending_proposals_count"] == 1
    assert data["channels_breakdown"]["sms"] == 1
    assert data["readiness_score"] > 0


def test_overview_respects_tenant_isolation(studio_env, client: TestClient):
    """Tenant B requesting overview sees 0 counts when empty."""
    env = studio_env
    headers_b = _auth_headers(env["tenant_b"], env["admin_b"])

    resp = client.get("/api/admin/assistant-studio/overview", headers=headers_b)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    # Tenant B has no channels, conversations, or curated items
    assert data["channel_accounts_count"] == 0
    assert data["active_conversations_count"] == 0
    assert data["curated_facts_count"] == 0
    assert data["approved_examples_count"] == 0
    assert data["message_volume"] == 0


def test_policy_get_and_put_mutates_database(studio_env, db_session, client: TestClient):
    """GET and PUT /api/admin/assistant-studio/policy mutates real DB records."""
    env = studio_env
    headers = _auth_headers(env["tenant_a"], env["admin_a"])

    # 1. Read default policy
    get_resp = client.get("/api/admin/assistant-studio/policy", headers=headers)
    assert get_resp.status_code == status.HTTP_200_OK
    initial_data = get_resp.json()
    assert len(initial_data["tiers"]) == 10
    assert "IMMUTABLE PLATFORM SAFETY" in initial_data["immutable_safety"]

    # 2. Update policy with custom provider notes & style profile
    put_payload = {
        "provider_id": env["prov_a"].id,
        "provider_overlay": "Specialized in remedial sports injuries. Do not quote weekend rates without checking availability.",
        "custom_training_notes": "Always check for prior shoulder dislocation notes.",
        "style_profile": {
            "warmth": 5,
            "wit": 3,
            "sarcasm": 0,
            "directness": 4,
            "chattiness": 2,
            "patience": 5,
        },
        "agent_name": "Tori Pro",
        "model": "gpt-4o",
    }
    put_resp = client.put("/api/admin/assistant-studio/policy", json=put_payload, headers=headers)
    assert put_resp.status_code == status.HTTP_200_OK
    updated_data = put_resp.json()

    assert updated_data["agent_name"] == "Tori Pro"
    assert updated_data["model"] == "gpt-4o"
    assert updated_data["style_profile"]["warmth"] == 5
    assert updated_data["custom_training_notes"] == "Always check for prior shoulder dislocation notes."

    # 3. Verify real DB mutation
    db_setting = (
        db_session.query(SmsBootcampSettings)
        .filter(
            SmsBootcampSettings.tenant_id == env["tenant_a"].id,
            SmsBootcampSettings.provider_id == env["prov_a"].id,
        )
        .first()
    )
    assert db_setting is not None
    assert db_setting.agent_name == "Tori Pro"
    assert db_setting.custom_training_notes == "Always check for prior shoulder dislocation notes."
    assert db_setting.active_style_profile["warmth"] == 5

    # Verify SmsPromptProfile was also updated
    db_profile = (
        db_session.query(SmsPromptProfile)
        .filter(
            SmsPromptProfile.tenant_id == env["tenant_a"].id,
            SmsPromptProfile.provider_id == env["prov_a"].id,
        )
        .first()
    )
    assert db_profile is not None
    assert "remedial sports injuries" in db_profile.system_prompt


def test_simulate_turn_executes_live_tool_against_db(studio_env, client: TestClient):
    """POST /api/admin/assistant-studio/simulate executes real live tools against database."""
    env = studio_env
    headers = _auth_headers(env["tenant_a"], env["admin_a"])

    sim_payload = {
        "client_input": "How much is Swedish massage?",
        "conversation_history": [],
        "provider_id": env["prov_a"].id,
    }

    resp = client.post("/api/admin/assistant-studio/simulate", json=sim_payload, headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert "reply" in data
    assert len(data["executed_tools"]) >= 1

    # Verify tool execution inspected
    tool_exec = data["executed_tools"][0]
    assert tool_exec["name"] == "service_lookup"
    assert "Swedish" in tool_exec["arguments"]["service_id_or_slug"]
    assert tool_exec["server_bound_keys"] == ["tenant_id"]

    # Verify real DB service was found and output contains official price
    services = tool_exec["output"]["services"]
    assert len(services) >= 1
    assert services[0]["name"] == "Swedish Remedial Massage"
    assert services[0]["price"] == 140.0
    assert "$140.00" in data["reply"] or "Swedish Remedial Massage" in data["reply"]

    # Verify prompt assembly tiers are returned
    sections = data["assembled_prompt"]["sections"]
    assert "tier_1_safety" in sections
    assert "tier_2_tool_truth" in sections
    assert "Swedish Remedial Massage" in sections["tier_2_tool_truth"]


def test_simulate_turn_handles_distress_modulation(studio_env, client: TestClient):
    """POST /api/admin/assistant-studio/simulate activates situational modulation upon distress."""
    env = studio_env
    headers = _auth_headers(env["tenant_a"], env["admin_a"])

    sim_payload = {
        "client_input": "I am furious, this is completely unacceptable service!",
        "conversation_history": [],
        "provider_id": env["prov_a"].id,
    }

    resp = client.post("/api/admin/assistant-studio/simulate", json=sim_payload, headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["distress_detected"] is True
    assert data["situational_modulation_active"] is True
    assert "sorry" in data["reply"].lower() or "escalat" in data["reply"].lower()


def test_examples_crud_workflow_mutates_database(studio_env, db_session, client: TestClient):
    """POST, GET, PUT, DELETE on /examples executes full real DB CRUD."""
    env = studio_env
    headers = _auth_headers(env["tenant_a"], env["admin_a"])

    # 1. Create new example
    create_payload = {
        "intent": "cancellation_policy",
        "client_message": "What happens if I cancel within 12 hours?",
        "assistant_reply": "Cancellations with less than 24 hours notice may incur a late cancellation fee.",
        "category": "policy",
        "tags": ["cancellation", "late_notice"],
        "is_approved": True,
        "is_active": True,
    }
    create_resp = client.post("/api/admin/assistant-studio/examples", json=create_payload, headers=headers)
    assert create_resp.status_code == status.HTTP_201_CREATED
    example_id = create_resp.json()["id"]

    # Verify real DB row created
    db_ex = db_session.query(MessageStyleExample).filter(MessageStyleExample.id == example_id).first()
    assert db_ex is not None
    assert db_ex.intent == "cancellation_policy"
    assert db_ex.tenant_id == env["tenant_a"].id

    # 2. List examples
    list_resp = client.get("/api/admin/assistant-studio/examples", headers=headers)
    assert list_resp.status_code == status.HTTP_200_OK
    items = list_resp.json()
    assert any(i["id"] == example_id for i in items)

    # 3. Update example (e.g. toggle active)
    put_resp = client.put(
        f"/api/admin/assistant-studio/examples/{example_id}",
        json={"is_active": False, "category": "updated_policy"},
        headers=headers,
    )
    assert put_resp.status_code == status.HTTP_200_OK
    assert put_resp.json()["is_active"] is False

    db_session.refresh(db_ex)
    assert db_ex.is_active is False
    assert db_ex.category == "updated_policy"

    # 4. Cross-tenant access forbidden/isolated
    headers_b = _auth_headers(env["tenant_b"], env["admin_b"])
    del_forbidden = client.delete(f"/api/admin/assistant-studio/examples/{example_id}", headers=headers_b)
    assert del_forbidden.status_code == status.HTTP_404_NOT_FOUND

    # 5. Delete example
    del_resp = client.delete(f"/api/admin/assistant-studio/examples/{example_id}", headers=headers)
    assert del_resp.status_code == status.HTTP_200_OK

    deleted_check = db_session.query(MessageStyleExample).filter(MessageStyleExample.id == example_id).first()
    assert deleted_check is None


def test_curator_proposals_workflow(studio_env, db_session, client: TestClient):
    """GET and POST /api/admin/assistant-studio/curator/proposals/{id}/curate."""
    env = studio_env
    headers = _auth_headers(env["tenant_a"], env["admin_a"])
    prop_id = env["prop_a"].id

    # 1. List proposals
    list_resp = client.get("/api/admin/assistant-studio/curator/proposals", headers=headers)
    assert list_resp.status_code == status.HTTP_200_OK
    proposals = list_resp.json()
    assert any(p["id"] == prop_id for p in proposals)

    # 2. Curate approval -> promotes to CuratedMemory
    curate_resp = client.post(
        f"/api/admin/assistant-studio/curator/proposals/{prop_id}/curate",
        json={"action": "approved"},
        headers=headers,
    )
    assert curate_resp.status_code == status.HTTP_200_OK
    curate_data = curate_resp.json()
    assert curate_data["status"] == "approved"
    assert "curated_memory_id" in curate_data

    # Verify DB mutation
    mem = db_session.query(CuratedMemory).filter(CuratedMemory.id == curate_data["curated_memory_id"]).first()
    assert mem is not None
    assert mem.category == "parking"
    assert "Castlereagh" in mem.ideal_response
    assert mem.status == "active"


def test_real_import_executes_with_sha256_verification(studio_env, client: TestClient):
    """POST /api/admin/assistant-studio/import runs real SHA-256 asset importer."""
    env = studio_env
    headers = _auth_headers(env["tenant_a"], env["admin_a"])

    import_resp = client.post(
        "/api/admin/assistant-studio/import",
        json={"scope": "platform_seed", "dry_run": False},
        headers=headers,
    )
    assert import_resp.status_code == status.HTTP_200_OK
    data = import_resp.json()

    assert data["status"] == "success"
    assert data["scanned"] > 0
    assert data["sha256_verified"] is True
    assert len(data["computed_sha256"]) == 64
    assert data["imported"] >= 0


def test_variables_and_tools_endpoints(studio_env, client: TestClient):
    """GET /variables and GET /tools return real registered definitions."""
    env = studio_env
    headers = _auth_headers(env["tenant_a"], env["admin_a"])

    # 1. Variables
    var_resp = client.get("/api/admin/assistant-studio/variables", headers=headers)
    assert var_resp.status_code == status.HTTP_200_OK
    vars_list = var_resp.json()
    assert len(vars_list) > 0
    # business_name should resolve to Sydney Wellness Studio
    biz_var = next((v for v in vars_list if "business_name" in v["name"]), None)
    assert biz_var is not None
    assert biz_var["resolved_value"] == "Sydney Wellness Studio"

    # 2. Tools
    tools_resp = client.get("/api/admin/assistant-studio/tools", headers=headers)
    assert tools_resp.status_code == status.HTTP_200_OK
    tools_list = tools_resp.json()
    assert len(tools_list) == 5
    tool_names = [t["name"] for t in tools_list]
    assert "check_availability" in tool_names
    assert "quote_travel" in tool_names
    assert "service_lookup" in tool_names


def test_evaluation_benchmark_executes_all_scenarios(studio_env, client: TestClient):
    """POST /api/admin/assistant-studio/evaluate executes real benchmark tests."""
    env = studio_env
    headers = _auth_headers(env["tenant_a"], env["admin_a"])

    eval_resp = client.post("/api/admin/assistant-studio/evaluate", headers=headers)
    assert eval_resp.status_code == status.HTTP_200_OK
    scenarios = eval_resp.json()
    assert len(scenarios) == 6
    assert all(s["status"] == "passed" for s in scenarios)
    assert all(s["score"] == 100 for s in scenarios)
