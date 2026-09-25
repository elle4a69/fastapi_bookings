"""Comprehensive tests for SMS Bootcamp endpoints, runner, handoff resolution, and isolated settings."""

import uuid
from datetime import datetime, timezone
import pytest
from fastapi import status

from sqlalchemy.orm import sessionmaker

from app.api.routers.sms_bootcamp import BOOTCAMP_RUNNER
from app.core.security import create_access_token
from app.models.curated_memory import KnowledgeProposal
from app.models.tenant import Tenant
from app.models.user import User
from app.models.sms_bootcamp import (
    SmsBootcampConversation,
    SmsBootcampMessage,
    SmsBootcampRun,
    SmsBootcampSettings,
)
from app.services.sms.bootcamp import DEFAULT_STYLE_PROFILE, PERSONAS, clarification_for_handoff


@pytest.fixture(autouse=True)
def configure_bootcamp_runner_for_tests(monkeypatch):
    """Ensure predictable openings and suppress background thread DB queries in tests."""
    original_openings = list(BOOTCAMP_RUNNER.openings)
    BOOTCAMP_RUNNER.openings = ["Hi, what are your rates for a one hour session?"]
    monkeypatch.setattr(BOOTCAMP_RUNNER, "_run_async", lambda *args, **kwargs: None)
    yield
    BOOTCAMP_RUNNER.openings = original_openings


def _auth_headers(tenant: Tenant, admin_user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(admin_user.id)})
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": token,
    }


@pytest.fixture
def synthetic_bootcamp_data(db_session):
    """Seed synthetic tenants and admin users for isolation testing."""
    tenant_a = Tenant(name="SYNTHETIC Bootcamp Tenant A", subdomain="bootcamp-tenant-a")
    tenant_b = Tenant(name="SYNTHETIC Bootcamp Tenant B", subdomain="bootcamp-tenant-b")
    db_session.add_all([tenant_a, tenant_b])
    db_session.flush()

    admin_a = User(
        tenant_id=tenant_a.id,
        login="admin-bootcamp-a@example.com",
        password_hash="synthetic-hash-a",
        role="admin",
    )
    admin_b = User(
        tenant_id=tenant_b.id,
        login="admin-bootcamp-b@example.com",
        password_hash="synthetic-hash-b",
        role="admin",
    )
    db_session.add_all([admin_a, admin_b])
    db_session.flush()

    return {
        "tenant_a": tenant_a,
        "admin_a": admin_a,
        "tenant_b": tenant_b,
        "admin_b": admin_b,
    }


def test_get_personas(client, synthetic_bootcamp_data):
    """Verify GET /personas returns all 12 canonical personas."""
    data = synthetic_bootcamp_data
    headers = _auth_headers(data["tenant_a"], data["admin_a"])

    response = client.get("/api/admin/sms/bootcamp/personas", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    personas = response.json()
    assert len(personas) == 12

    persona_ids = {p["id"] for p in personas}
    expected_ids = {
        "cranky-carl",
        "sarcastic-sam",
        "deadpan-dave",
        "passive-paul",
        "happy-harry",
        "nervous-neil",
        "time-waster-terry",
        "chatty-charlie",
        "budget-bob",
        "curious-colin",
        "discreet-dominic",
        "pushy-pete",
    }
    assert persona_ids == expected_ids


def test_style_profile_apply_and_undo(client, synthetic_bootcamp_data):
    """Verify style profile defaults, apply mutation, and undo restoration."""
    data = synthetic_bootcamp_data
    headers = _auth_headers(data["tenant_a"], data["admin_a"])

    # 1. Initially profile is default and cannot undo
    res = client.get("/api/admin/sms/bootcamp/profile", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert body["active"] == DEFAULT_STYLE_PROFILE
    assert body["defaults"] == DEFAULT_STYLE_PROFILE
    assert body["isApplied"] is False
    assert body["canUndo"] is False

    # 2. Apply new style traits
    new_profile = {**DEFAULT_STYLE_PROFILE, "warmth": 1, "wit": 5, "sarcasm": 4}
    res_apply = client.post(
        "/api/admin/sms/bootcamp/profile/apply",
        json={"styleProfile": new_profile},
        headers=headers,
    )
    assert res_apply.status_code == status.HTTP_200_OK
    applied_body = res_apply.json()
    assert applied_body["active"]["warmth"] == 1
    assert applied_body["active"]["wit"] == 5
    assert applied_body["active"]["sarcasm"] == 4
    assert applied_body["isApplied"] is True
    assert applied_body["canUndo"] is True

    # 3. GET /profile reflects applied profile
    res_check = client.get("/api/admin/sms/bootcamp/profile", headers=headers)
    assert res_check.status_code == status.HTTP_200_OK
    assert res_check.json()["active"]["wit"] == 5
    assert res_check.json()["canUndo"] is True

    # 4. Undo restores initial profile
    res_undo = client.post("/api/admin/sms/bootcamp/profile/undo", headers=headers)
    assert res_undo.status_code == status.HTTP_200_OK
    undo_body = res_undo.json()
    assert undo_body["active"] == DEFAULT_STYLE_PROFILE
    assert undo_body["isApplied"] is False


def test_run_creation_and_status_retrieval(client, synthetic_bootcamp_data):
    """Verify synchronous simulation run creation, turn execution, and retrieval."""
    data = synthetic_bootcamp_data
    headers = _auth_headers(data["tenant_a"], data["admin_a"])

    payload = {
        "personaIds": ["cranky-carl", "happy-harry"],
        "maxTurns": 2,
        "sync": True,
    }
    res = client.post("/api/admin/sms/bootcamp/runs", json=payload, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    run_data = res.json()
    assert run_data["status"] == "completed"
    assert len(run_data["selectedPersonaIds"]) == 2
    assert len(run_data["conversations"]) == 2

    # Check conversation turns and messages
    for conv in run_data["conversations"]:
        assert conv["personaId"] in {"cranky-carl", "happy-harry"}
        assert len(conv["messages"]) >= 2
        roles = [m["role"] for m in conv["messages"]]
        assert "persona" in roles
        assert "tori" in roles

    run_id = run_data["id"]

    # Retrieve specific run
    res_get = client.get(f"/api/admin/sms/bootcamp/runs/{run_id}", headers=headers)
    assert res_get.status_code == status.HTTP_200_OK
    assert res_get.json()["id"] == run_id

    # Retrieve latest run
    res_latest = client.get("/api/admin/sms/bootcamp/runs/latest", headers=headers)
    assert res_latest.status_code == status.HTTP_200_OK
    assert res_latest.json()["run"]["id"] == run_id


def test_run_control_pause_resume_stop_and_reset(client, synthetic_bootcamp_data):
    """Verify pause, resume, stop control operations and reset with 409 guard."""
    data = synthetic_bootcamp_data
    headers = _auth_headers(data["tenant_a"], data["admin_a"])

    # Create run with sync=False
    payload = {"personaIds": ["deadpan-dave"], "maxTurns": 3, "sync": False}
    res = client.post("/api/admin/sms/bootcamp/runs", json=payload, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    run_id = res.json()["id"]

    # 1. Pause run
    res_pause = client.post(
        f"/api/admin/sms/bootcamp/runs/{run_id}/control",
        json={"operation": "pause"},
        headers=headers,
    )
    assert res_pause.status_code == status.HTTP_200_OK
    assert res_pause.json()["status"] == "paused"

    # 2. Reset should fail with 409 conflict when run is paused
    res_reset_conflict = client.delete("/api/admin/sms/bootcamp/runs", headers=headers)
    assert res_reset_conflict.status_code == status.HTTP_409_CONFLICT

    # 3. Resume run
    res_resume = client.post(
        f"/api/admin/sms/bootcamp/runs/{run_id}/control",
        json={"operation": "resume"},
        headers=headers,
    )
    assert res_resume.status_code == status.HTTP_200_OK
    assert res_resume.json()["status"] == "running"

    # 4. Stop run
    res_stop = client.post(
        f"/api/admin/sms/bootcamp/runs/{run_id}/control",
        json={"operation": "stop"},
        headers=headers,
    )
    assert res_stop.status_code == status.HTTP_200_OK
    assert res_stop.json()["status"] == "stopped"

    # 5. Reset succeeds when stopped
    res_reset = client.delete("/api/admin/sms/bootcamp/runs", headers=headers)
    assert res_reset.status_code == status.HTTP_200_OK
    assert res_reset.json() == {"status": "reset"}

    # Latest run should now be None
    res_latest = client.get("/api/admin/sms/bootcamp/runs/latest", headers=headers)
    assert res_latest.status_code == status.HTTP_200_OK
    assert res_latest.json()["run"] is None


def test_information_request_response_records_lesson_and_clears_handoff(
    client, synthetic_bootcamp_data, db_session
):
    """Verify staff information submission clears handoff, adds Tori reply, and records lesson."""
    data = synthetic_bootcamp_data
    tenant = data["tenant_a"]
    headers = _auth_headers(tenant, data["admin_a"])

    # Create run and conversation in handoff state
    run = SmsBootcampRun(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        status="running",
        selected_personas=["cranky-carl"],
        max_turns=3,
        style_profile=DEFAULT_STYLE_PROFILE,
    )
    conv = SmsBootcampConversation(
        id=str(uuid.uuid4()),
        run_id=run.id,
        tenant_id=tenant.id,
        persona_id="cranky-carl",
        persona_name="Cranky Carl",
        status="handoff",
        current_turn=1,
        needs_handoff=True,
        handoff_reason="The couples policy is not recorded",
    )
    msg = SmsBootcampMessage(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        tenant_id=tenant.id,
        role="persona",
        text="Do you offer a couples massage session?",
    )
    db_session.add_all([run, conv, msg])
    db_session.commit()

    # Staff responds to information request
    res = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv.id}/information-request/respond",
        json={"information": "Yes, we offer couples sessions for $220. Booking 48h in advance is recommended."},
        headers=headers,
    )
    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert body["status"] == "success"
    assert body["conversation"]["needsHandoff"] is False
    assert body["conversation"]["handoffReason"] is None
    assert body["conversation"]["status"] == "completed"

    # Verify Tori's reply message was recorded with information-request source
    messages = body["conversation"]["messages"]
    assert len(messages) >= 2
    last_msg = messages[-1]
    assert last_msg["role"] == "tori"
    assert last_msg["meta"]["source"] == "information-request"

    # Verify lesson was saved in isolated settings
    settings_res = client.get("/api/admin/sms/bootcamp/settings", headers=headers)
    assert settings_res.status_code == status.HTTP_200_OK
    settings_data = settings_res.json()
    assert settings_data["customTrainingNotes"] is not None
    assert "couples" in settings_data["customTrainingNotes"].lower()

    # Submitting again should be rejected with 409 conflict
    res_conflict = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv.id}/information-request/respond",
        json={"information": "Another answer"},
        headers=headers,
    )
    assert res_conflict.status_code == status.HTTP_409_CONFLICT


def test_isolated_settings_get_and_put(client, synthetic_bootcamp_data):
    """Verify getting and updating isolated Bootcamp settings without affecting other tenants."""
    data = synthetic_bootcamp_data
    headers = _auth_headers(data["tenant_a"], data["admin_a"])

    # 1. Default settings
    res = client.get("/api/admin/sms/bootcamp/settings", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert body["agentName"] == "Tori"
    assert body["systemPromptTemplate"] is None
    assert body["customTrainingNotes"] is None

    # 2. Update settings
    update_payload = {
        "agentName": "Victoria Concierge",
        "customTrainingNotes": "Always offer chilled sparkling water upon arrival.",
        "systemPromptTemplate": "You are Victoria, a luxury concierge.",
    }
    res_put = client.put(
        "/api/admin/sms/bootcamp/settings",
        json=update_payload,
        headers=headers,
    )
    assert res_put.status_code == status.HTTP_200_OK
    put_body = res_put.json()
    assert put_body["agentName"] == "Victoria Concierge"
    assert put_body["customTrainingNotes"] == "Always offer chilled sparkling water upon arrival."
    assert put_body["systemPromptTemplate"] == "You are Victoria, a luxury concierge."

    # 3. GET reflects updated settings
    res_get = client.get("/api/admin/sms/bootcamp/settings", headers=headers)
    assert res_get.status_code == status.HTTP_200_OK
    assert res_get.json()["agentName"] == "Victoria Concierge"


def test_strict_multi_tenant_isolation(client, synthetic_bootcamp_data, db_session):
    """Verify runs, conversations, and settings never bleed across tenant boundaries."""
    data = synthetic_bootcamp_data
    tenant_a = data["tenant_a"]
    tenant_b = data["tenant_b"]
    headers_a = _auth_headers(tenant_a, data["admin_a"])
    headers_b = _auth_headers(tenant_b, data["admin_b"])

    # 1. Create run for Tenant A
    run_a = SmsBootcampRun(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a.id,
        status="running",
        selected_personas=["cranky-carl"],
        max_turns=3,
        style_profile=DEFAULT_STYLE_PROFILE,
    )
    conv_a = SmsBootcampConversation(
        id=str(uuid.uuid4()),
        run_id=run_a.id,
        tenant_id=tenant_a.id,
        persona_id="cranky-carl",
        persona_name="Cranky Carl",
        status="running",
        current_turn=1,
    )
    db_session.add_all([run_a, conv_a])
    db_session.commit()

    # 2. Tenant B cannot see Tenant A's run
    res_b_run = client.get(f"/api/admin/sms/bootcamp/runs/{run_a.id}", headers=headers_b)
    assert res_b_run.status_code == status.HTTP_404_NOT_FOUND

    # 3. Tenant B's latest run is None
    res_b_latest = client.get("/api/admin/sms/bootcamp/runs/latest", headers=headers_b)
    assert res_b_latest.status_code == status.HTTP_200_OK
    assert res_b_latest.json()["run"] is None

    # 4. Tenant B cannot control Tenant A's run
    res_b_ctrl = client.post(
        f"/api/admin/sms/bootcamp/runs/{run_a.id}/control",
        json={"operation": "stop"},
        headers=headers_b,
    )
    assert res_b_ctrl.status_code == status.HTTP_404_NOT_FOUND

    # 5. Tenant B cannot respond to Tenant A's conversation
    res_b_respond = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv_a.id}/information-request/respond",
        json={"information": "Leaked secret"},
        headers=headers_b,
    )
    assert res_b_respond.status_code == status.HTTP_404_NOT_FOUND

    # 6. Tenant B resetting runs does not delete Tenant A's runs
    res_b_reset = client.delete("/api/admin/sms/bootcamp/runs", headers=headers_b)
    assert res_b_reset.status_code == status.HTTP_200_OK

    res_a_check = client.get(f"/api/admin/sms/bootcamp/runs/{run_a.id}", headers=headers_a)
    assert res_a_check.status_code == status.HTTP_200_OK

    # 7. Settings are completely isolated
    client.put(
        "/api/admin/sms/bootcamp/settings",
        json={"agentName": "Agent-A-Custom"},
        headers=headers_a,
    )
    settings_b = client.get("/api/admin/sms/bootcamp/settings", headers=headers_b).json()
    assert settings_b["agentName"] == "Tori"


def test_clarification_ladder_logic():
    """Verify standalone clarification ladder regex and follow-up generation."""
    assert clarification_for_handoff(
        "They haven't said which service they mean.",
        "How much is it and how long does it take?",
    ) == "Which service were you interested in?"

    assert clarification_for_handoff(
        "Availability this week is not recorded.",
        "Do you have anything later this week?",
    ) == "What day and roughly what time were you thinking?"

    assert clarification_for_handoff(
        "Availability is not recorded.",
        "Are you free Friday at 8pm?",
    ) is None


def test_empty_persona_selection_rejected(client, synthetic_bootcamp_data):
    """Verify 400 Bad Request when run is submitted with no personas."""
    headers = _auth_headers(synthetic_bootcamp_data["tenant_a"], synthetic_bootcamp_data["admin_a"])
    res = client.post("/api/admin/sms/bootcamp/runs", json={"personaIds": []}, headers=headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST


def test_bootcamp_correction_creates_proposal_and_updates_message(
    client, synthetic_bootcamp_data, db_session
):
    """Verify correction updates message text, records lesson, and creates conflict KnowledgeProposal."""
    data = synthetic_bootcamp_data
    tenant = data["tenant_a"]
    headers = _auth_headers(tenant, data["admin_a"])

    # 1. Run a 1-turn simulation to get a Tori message
    res_run = client.post(
        "/api/admin/sms/bootcamp/runs",
        json={"personaIds": ["cranky-carl"], "maxTurns": 1, "sync": True},
        headers=headers,
    )
    assert res_run.status_code == status.HTTP_200_OK
    run_data = res_run.json()
    conv_data = run_data["conversations"][0]
    conv_id = conv_data["id"]
    tori_msgs = [m for m in conv_data["messages"] if m["role"] == "tori"]
    assert len(tori_msgs) >= 1
    tori_msg = tori_msgs[0]

    # 2. Post correction
    correction_payload = {
        "messageId": tori_msg["id"],
        "reason": "Wrong price",
        "correctedWording": "Standard price is $120",
        "containsDynamicFacts": False,
    }
    res_corr = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv_id}/corrections",
        json=correction_payload,
        headers=headers,
    )
    assert res_corr.status_code == status.HTTP_200_OK
    corr_data = res_corr.json()
    assert corr_data["ok"] is True
    assert corr_data["updated_text"] == "Standard price is $120"
    proposal_id = corr_data["proposal_id"]
    assert proposal_id is not None

    # 3. Verify message text and metadata updated in DB
    updated_msg = (
        db_session.query(SmsBootcampMessage)
        .filter(SmsBootcampMessage.id == tori_msg["id"])
        .first()
    )
    assert updated_msg.text == "Standard price is $120"
    assert updated_msg.meta is not None
    assert updated_msg.meta.get("correction", {}).get("reason") == "Wrong price"

    # 4. Verify KnowledgeProposal created in DB
    proposal = (
        db_session.query(KnowledgeProposal)
        .filter(KnowledgeProposal.id == proposal_id)
        .first()
    )
    assert proposal is not None
    assert proposal.tenant_id == tenant.id
    assert proposal.proposal_type == "conflict"
    assert proposal.status == "pending"
    assert proposal.authority == "bootcamp_correction"
    assert proposal.proposed_response == "Standard price is $120"
    assert "Wrong price" in proposal.reason_code

    # 5. Verify tenant isolation: Tenant B cannot correct Tenant A's message
    headers_b = _auth_headers(data["tenant_b"], data["admin_b"])
    res_b = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv_id}/corrections",
        json=correction_payload,
        headers=headers_b,
    )
    assert res_b.status_code == status.HTTP_404_NOT_FOUND


def test_bootcamp_info_request_creates_proposal(
    client, synthetic_bootcamp_data, db_session
):
    """Verify answering an information request creates a gap KnowledgeProposal."""
    data = synthetic_bootcamp_data
    tenant = data["tenant_a"]
    headers = _auth_headers(tenant, data["admin_a"])

    # Create run and conversation in handoff state
    run = SmsBootcampRun(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        status="running",
        selected_personas=["curious-colin"],
        max_turns=3,
        style_profile=DEFAULT_STYLE_PROFILE,
    )
    conv = SmsBootcampConversation(
        id=str(uuid.uuid4()),
        run_id=run.id,
        tenant_id=tenant.id,
        persona_id="curious-colin",
        persona_name="Curious Colin",
        status="handoff",
        current_turn=1,
        needs_handoff=True,
        handoff_reason="Late evening access policy is not recorded",
    )
    msg = SmsBootcampMessage(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        tenant_id=tenant.id,
        role="persona",
        text="Can I check in after 10 PM?",
    )
    db_session.add_all([run, conv, msg])
    db_session.commit()

    # Staff answers info request
    res = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv.id}/information-request/respond",
        json={"information": "Self-check-in keypad access is available 24/7."},
        headers=headers,
    )
    assert res.status_code == status.HTTP_200_OK

    # Verify KnowledgeProposal created with proposal_type="gap"
    proposal = (
        db_session.query(KnowledgeProposal)
        .filter(
            KnowledgeProposal.tenant_id == tenant.id,
            KnowledgeProposal.authority == "bootcamp_info_request",
            KnowledgeProposal.proposal_type == "gap",
        )
        .first()
    )
    assert proposal is not None
    assert proposal.status in ("pending", "resolved")
    assert proposal.requires_review is True
    assert proposal.user_query == "Can I check in after 10 PM?"
    assert proposal.proposed_response == "Self-check-in keypad access is available 24/7."


def test_bootcamp_draft_review(client, synthetic_bootcamp_data, db_session):
    """Verify reviewing a draft message with approve updates status to sent and text."""
    data = synthetic_bootcamp_data
    tenant = data["tenant_a"]
    headers = _auth_headers(tenant, data["admin_a"])

    run = SmsBootcampRun(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        status="running",
        selected_personas=["happy-harry"],
        max_turns=2,
        style_profile=DEFAULT_STYLE_PROFILE,
    )
    conv = SmsBootcampConversation(
        id=str(uuid.uuid4()),
        run_id=run.id,
        tenant_id=tenant.id,
        persona_id="happy-harry",
        persona_name="Happy Harry",
        status="running",
        current_turn=1,
    )
    draft_msg = SmsBootcampMessage(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        tenant_id=tenant.id,
        role="tori",
        text="Draft greeting for Harry.",
        meta={"status": "draft"},
    )
    db_session.add_all([run, conv, draft_msg])
    db_session.commit()

    # 1. Review with approve and edited text
    res = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv.id}/drafts/{draft_msg.id}/review",
        json={"action": "approve", "text": "Approved greeting for Harry!"},
        headers=headers,
    )
    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert body["ok"] is True
    assert body["status"] == "sent"
    assert body["text"] == "Approved greeting for Harry!"

    # Verify status in DB
    db_session.refresh(draft_msg)
    assert draft_msg.status == "sent"
    assert draft_msg.text == "Approved greeting for Harry!"

    # 2. Review with discard on another draft
    draft_msg_2 = SmsBootcampMessage(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        tenant_id=tenant.id,
        role="tori",
        text="Another draft to discard.",
        meta={"status": "draft"},
    )
    db_session.add(draft_msg_2)
    db_session.commit()

    res_discard = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv.id}/drafts/{draft_msg_2.id}/review",
        json={"action": "discard"},
        headers=headers,
    )
    assert res_discard.status_code == status.HTTP_200_OK
    assert res_discard.json()["status"] == "discarded"
    db_session.refresh(draft_msg_2)
    assert draft_msg_2.status == "discarded"

    # 3. Tenant B isolation check
    headers_b = _auth_headers(data["tenant_b"], data["admin_b"])
    res_b = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv.id}/drafts/{draft_msg.id}/review",
        json={"action": "approve"},
        headers=headers_b,
    )
    assert res_b.status_code == status.HTTP_404_NOT_FOUND


def test_get_scenarios_catalog(client, synthetic_bootcamp_data):
    """Verify GET /scenarios returns all 7 scenario packs and 23 standardized scenarios."""
    data = synthetic_bootcamp_data
    headers = _auth_headers(data["tenant_a"], data["admin_a"])

    res = client.get("/api/admin/sms/bootcamp/scenarios", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    packs = res.json()
    assert isinstance(packs, list)
    assert len(packs) == 7

    pack_ids = {p["id"] for p in packs}
    expected_pack_ids = {
        "basic_communication",
        "booking",
        "knowledge_gaps",
        "difficult_conversations",
        "regular_customers",
        "state_management",
        "adversarial",
    }
    assert pack_ids == expected_pack_ids

    total_scenarios = 0
    for pack in packs:
        assert pack["title"]
        assert pack["description"]
        assert len(pack["scenarios"]) > 0
        for scenario in pack["scenarios"]:
            total_scenarios += 1
            assert scenario["id"]
            assert scenario["pack"] == pack["id"]
            assert scenario["title"]
            assert scenario["description"]
            assert scenario["objective"]
            assert scenario["initialPrompt"]
            assert scenario["expectedOutcome"]

    assert total_scenarios == 23


def test_run_creation_autonomy_level_1_pauses_on_draft(client, synthetic_bootcamp_data):
    """Verify Autonomy Level 1 creates draft reply and pauses conversation in waiting_approval."""
    data = synthetic_bootcamp_data
    headers = _auth_headers(data["tenant_a"], data["admin_a"])

    payload = {
        "personaIds": ["cranky-carl"],
        "maxTurns": 3,
        "sync": True,
        "autonomyLevel": 1,
    }
    res = client.post("/api/admin/sms/bootcamp/runs", json=payload, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    run_data = res.json()
    assert run_data["autonomyLevel"] == 1
    assert len(run_data["conversations"]) == 1

    conv = run_data["conversations"][0]
    assert conv["status"] == "waiting_approval"
    assert conv["currentTurn"] == 1
    assert conv["needsHandoff"] is False

    # Check messages: seed persona message + draft tori message
    messages = conv["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "persona"
    assert messages[1]["role"] == "tori"
    assert messages[1]["status"] == "draft"

    # Staff approves draft
    draft_id = messages[1]["id"]
    res_review = client.post(
        f"/api/admin/sms/bootcamp/conversations/{conv['id']}/drafts/{draft_id}/review",
        json={"action": "approve"},
        headers=headers,
    )
    assert res_review.status_code == status.HTTP_200_OK
    assert res_review.json()["status"] == "sent"
    assert res_review.json()["message"]["status"] == "sent"


def test_run_creation_autonomy_level_2_pauses_on_knowledge_gap(client, synthetic_bootcamp_data):
    """Verify Autonomy Level 2 pauses with needsHandoff=True when facing a knowledge gap scenario."""
    data = synthetic_bootcamp_data
    headers = _auth_headers(data["tenant_a"], data["admin_a"])

    payload = {
        "personaIds": ["pushy-pete"],
        "scenarioIds": ["unknown_personal_preference"],
        "maxTurns": 3,
        "sync": True,
        "autonomyLevel": 2,
    }
    res = client.post("/api/admin/sms/bootcamp/runs", json=payload, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    run_data = res.json()
    assert run_data["autonomyLevel"] == 2
    assert run_data["selectedScenarios"] == ["unknown_personal_preference"]

    conv = run_data["conversations"][0]
    assert conv["scenarioId"] == "unknown_personal_preference"
    assert conv["status"] == "handoff"
    assert conv["needsHandoff"] is True
    assert conv["handoffReason"] is not None
    assert conv["currentTurn"] == 1

    # Verify seed prompt matches scenario initial prompt
    messages = conv["messages"]
    assert len(messages) >= 1
    assert "coffee" in messages[0]["text"].lower() or "snack" in messages[0]["text"].lower()


def test_run_creation_autonomy_level_3_runs_to_completion(client, synthetic_bootcamp_data):
    """Verify Autonomy Level 3 runs all turns to completion without halting on knowledge gaps."""
    data = synthetic_bootcamp_data
    headers = _auth_headers(data["tenant_a"], data["admin_a"])

    payload = {
        "personaIds": ["happy-harry"],
        "scenarioIds": ["unknown_personal_preference"],
        "maxTurns": 2,
        "sync": True,
        "autonomyLevel": 3,
    }
    res = client.post("/api/admin/sms/bootcamp/runs", json=payload, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    run_data = res.json()
    assert run_data["autonomyLevel"] == 3
    assert run_data["status"] == "completed"

    conv = run_data["conversations"][0]
    assert conv["scenarioId"] == "unknown_personal_preference"
    assert conv["status"] == "completed"
    assert conv["needsHandoff"] is False
    assert conv["currentTurn"] == 2
    assert len(conv["messages"]) >= 4  # 2 full turns (seed + 2 tori + 1 next persona)


def test_persona_and_scenario_combination(client, synthetic_bootcamp_data):
    """Verify combining persona traits with scenario objectives and initial prompt seeding."""
    data = synthetic_bootcamp_data
    headers = _auth_headers(data["tenant_a"], data["admin_a"])

    # 1. Test runner initialization with persona and scenario
    payload = {
        "personaIds": ["chatty-charlie"],
        "scenarioIds": ["pricing_enquiry"],
        "maxTurns": 1,
        "sync": True,
        "autonomyLevel": 2,
    }
    res = client.post("/api/admin/sms/bootcamp/runs", json=payload, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    run_data = res.json()
    conv = run_data["conversations"][0]
    assert conv["personaId"] == "chatty-charlie"
    assert conv["scenarioId"] == "pricing_enquiry"
    # Seed message matches pricing enquiry scenario initial prompt
    assert "rates for a one hour session" in conv["messages"][0]["text"].lower()

    # 2. Test offline helper combination function
    from app.services.sms.bootcamp import PERSONAS, SCENARIOS_BY_ID
    from app.services.sms.bootcamp_service import generate_bootcamp_persona_reply

    persona = next(p for p in PERSONAS if p["id"] == "chatty-charlie")
    scenario = SCENARIOS_BY_ID["pricing_enquiry"]
    combined_reply = generate_bootcamp_persona_reply(persona, [], seed=None, scenario=scenario)
    assert "Chatty Charlie" in combined_reply
    assert "Pricing Enquiry" in combined_reply

