"""Test suite for Autonomous Knowledge Curator Service and API endpoints.

Covers Specs 14, 17, 19, 21-27, 42-44, 47, 52:
- Test 1: Explicit knowledge answer creates active CuratedMemory without secondary confirmation (Spec 14).
- Test 2: Supersession of conflicting facts with provenance intact (Spec 25).
- Test 3: System safety boundary enforcement against unverified availability claims (Spec 22).
- Test 4: Behavioural correction interpretation and canonical rule derivation (Spec 17, 27).
- Test 5: Conservative generalization on draft edits (Spec 26).
- Test 6: Multi-tenant and provider scope isolation.
- Test 7: API endpoints (process, status, memories list, supersede, restore).
"""

from datetime import datetime, timezone
import hashlib
import pytest
from fastapi import status

from app.core.security import create_access_token
from app.models.client import Client
from app.models.curated_memory import CuratedMemory, KnowledgeProposal
from app.models.learning_event import LearningEvent, compute_text_diff
from app.models.provider import Provider
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.tenant import Tenant
from app.models.user import User
from app.services.sms.curator_service import AutonomousCuratorService


@pytest.fixture
def curator_setup(db_session):
    # Tenant Alpha
    tenant_a = Tenant(name="Tenant Alpha", subdomain="tenant-alpha")
    db_session.add(tenant_a)
    db_session.commit()

    admin_a = User(
        tenant_id=tenant_a.id,
        login="admin@alpha.com",
        password_hash="hash_a",
        role="admin",
    )
    db_session.add(admin_a)

    provider_a1 = Provider(tenant_id=tenant_a.id, name="Provider Alpha 1", active=True)
    provider_a2 = Provider(tenant_id=tenant_a.id, name="Provider Alpha 2", active=True)
    db_session.add_all([provider_a1, provider_a2])
    db_session.commit()

    account_a = SmsAccount(
        tenant_id=tenant_a.id,
        provider_id=provider_a1.id,
        transport_type="simulator",
        display_name="Alpha Line",
        sender_address="61400000001",
        is_enabled=True,
        ai_enabled=True,
        ai_mode="draft",
    )
    db_session.add(account_a)
    db_session.commit()

    client_a = Client(tenant_id=tenant_a.id, name="Customer Alice", phone="61411111111")
    db_session.add(client_a)
    db_session.commit()

    conv_a = SmsConversation(
        tenant_id=tenant_a.id,
        provider_id=provider_a1.id,
        sms_account_id=account_a.id,
        customer_address="61411111111",
        client_id=client_a.id,
        state="auto-reply",
        unread_count=0,
        is_pinned=False,
        is_blocked=False,
        ai_enabled=True,
    )
    db_session.add(conv_a)
    db_session.commit()

    # Tenant Beta (for multi-tenant isolation tests)
    tenant_b = Tenant(name="Tenant Beta", subdomain="tenant-beta")
    db_session.add(tenant_b)
    db_session.commit()

    admin_b = User(
        tenant_id=tenant_b.id,
        login="admin@beta.com",
        password_hash="hash_b",
        role="admin",
    )
    db_session.add(admin_b)

    provider_b = Provider(tenant_id=tenant_b.id, name="Provider Beta", active=True)
    db_session.add(provider_b)
    db_session.commit()

    return {
        "tenant_a": tenant_a,
        "admin_a": admin_a,
        "provider_a1": provider_a1,
        "provider_a2": provider_a2,
        "account_a": account_a,
        "conv_a": conv_a,
        "headers_a": {
            "X-Tenant": "tenant-alpha",
            "X-Token": create_access_token({"sub": str(admin_a.id)}),
        },
        "tenant_b": tenant_b,
        "admin_b": admin_b,
        "provider_b": provider_b,
        "headers_b": {
            "X-Tenant": "tenant-beta",
            "X-Token": create_access_token({"sub": str(admin_b.id)}),
        },
    }


def test_explicit_knowledge_answer_creates_active_curated_memory(curator_setup, db_session):
    """Test 1: Explicit knowledge answer creates active CuratedMemory without secondary confirmation (Spec 14)."""
    tenant = curator_setup["tenant_a"]
    provider = curator_setup["provider_a1"]
    conv = curator_setup["conv_a"]

    now = datetime.now(timezone.utc)
    question = "Do you have off-street parking available?"
    answer = "Yes, free off-street parking is available at the rear of the clinic in bays 1-4."

    # 1. Existing proposal waiting for resolution
    proposal = KnowledgeProposal(
        tenant_id=tenant.id,
        provider_id=provider.id,
        proposal_type="gap",
        status="pending",
        category="faq",
        knowledge_kind="durable_fact",
        authority="conversation_candidate",
        user_query=question,
        proposed_response=answer,
        fingerprint=hashlib.sha256(f"parking_info:{tenant.id}:{conv.id}".encode()).hexdigest(),
        reason_code="staff_info_request_answer",
        confidence_score=1.0,
        contains_dynamic_fact=False,
        requires_review=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(proposal)
    db_session.commit()

    # 2. LearningEvent from staff answer
    event = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        conversation_id=str(conv.id),
        event_type="knowledge_answer",
        source="production_messages",
        customer_message=question,
        human_content=answer,
        metadata_payload={"category": "facilities"},
        status="pending",
        confidence_score=1.0,
        created_at=now,
    )
    db_session.add(event)
    db_session.commit()

    # 3. Process event via AutonomousCuratorService
    result = AutonomousCuratorService.process_event(db_session, event)
    db_session.commit()

    assert result["status"] == "processed"
    assert result["action"] == "knowledge_curated"
    assert result["memory_id"] is not None
    assert event.status == "processed"

    # 4. Verify CuratedMemory is immediately active without secondary approval (Spec 14)
    memory = (
        db_session.query(CuratedMemory)
        .filter(CuratedMemory.id == result["memory_id"])
        .first()
    )
    assert memory is not None
    assert memory.status == "active"
    assert memory.knowledge_kind == "durable_fact"
    assert memory.tenant_id == tenant.id
    assert memory.provider_id == provider.id
    assert memory.category == "facilities"
    assert memory.user_query == question
    assert memory.ideal_response == answer
    assert memory.authority == "owner_verified"
    assert f"learning_event:{event.id}" in memory.source_reference
    assert memory.supersedes_id is None

    # 5. Verify corresponding proposal is marked resolved
    db_session.refresh(proposal)
    assert proposal.status == "resolved"
    assert proposal.target_memory_id == memory.id
    assert proposal.resolution_code == "curated_active"


def test_supersession_of_conflicting_facts(curator_setup, db_session):
    """Test 2: Supersession of conflicting facts marks old superseded and activates new with provenance intact (Spec 25)."""
    tenant = curator_setup["tenant_a"]
    provider = curator_setup["provider_a1"]
    now = datetime.now(timezone.utc)

    # 1. Existing active fact: old house specialty is "pasta"
    old_memory = CuratedMemory(
        tenant_id=tenant.id,
        provider_id=provider.id,
        category="menu",
        user_query="What is your signature dish?",
        ideal_response="Our signature dish is traditional truffle pasta.",
        knowledge_kind="durable_fact",
        authority="owner_verified",
        status="active",
        conflict_state="clear",
        source_reference="initial_seed",
        created_at=now,
        updated_at=now,
    )
    db_session.add(old_memory)
    db_session.commit()
    old_id = old_memory.id

    # 2. Staff provides new conflicting fact: "sushi"
    event = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="knowledge_answer",
        source="production_messages",
        customer_message="What is your signature dish?",
        human_content="Our signature dish has been updated to premium fresh sushi.",
        metadata_payload={"category": "menu"},
        status="pending",
        confidence_score=1.0,
        created_at=now,
    )
    db_session.add(event)
    db_session.commit()

    # 3. Process supersession
    result = AutonomousCuratorService.process_event(db_session, event)
    db_session.commit()

    assert result["status"] == "processed"
    assert result["superseded_id"] == old_id
    assert result["memory_id"] is not None

    # 4. Verify old memory is now superseded (Spec 25)
    db_session.refresh(old_memory)
    assert old_memory.status == "superseded"

    # 5. Verify new memory is active and points to old via supersedes_id
    new_memory = (
        db_session.query(CuratedMemory)
        .filter(CuratedMemory.id == result["memory_id"])
        .first()
    )
    assert new_memory is not None
    assert new_memory.status == "active"
    assert new_memory.supersedes_id == old_id
    assert new_memory.ideal_response == "Our signature dish has been updated to premium fresh sushi."


def test_system_safety_boundary_enforcement(curator_setup, db_session):
    """Test 3: System safety boundary enforcement (correction attempting to fake availability is quarantined per Spec 22)."""
    tenant = curator_setup["tenant_a"]
    provider = curator_setup["provider_a1"]
    now = datetime.now(timezone.utc)

    # Candidate proposal
    proposal = KnowledgeProposal(
        tenant_id=tenant.id,
        provider_id=provider.id,
        proposal_type="conflict",
        status="pending",
        category="faq",
        knowledge_kind="durable_fact",
        authority="production_correction",
        user_query="Are you available tomorrow at 3pm?",
        proposed_response="Yes, we have an open slot available tomorrow at 3pm, confirmed your appointment!",
        fingerprint=hashlib.sha256(f"safety_test:{tenant.id}".encode()).hexdigest(),
        reason_code="staff_correction",
        confidence_score=1.0,
        contains_dynamic_fact=True,
        requires_review=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(proposal)
    db_session.commit()

    # Flagged response correction attempting to fake appointment availability
    event = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="flagged_response",
        source="production_messages",
        customer_message="Are you available tomorrow at 3pm?",
        original_ai_content="Let me check our calendar.",
        human_content="Yes, we have an open slot available tomorrow at 3pm, confirmed your appointment!",
        metadata_payload={
            "reason": "Claiming open slot availability",
            "contains_dynamic_facts": True,
        },
        status="pending",
        confidence_score=1.0,
        created_at=now,
    )
    db_session.add(event)
    db_session.commit()

    # Process event
    result = AutonomousCuratorService.process_event(db_session, event)
    db_session.commit()

    # Verify quarantined
    assert result["status"] == "quarantined"
    assert result["reason"] == "safety_violation"
    assert result["action"] == "quarantine"

    # Verify NO active CuratedMemory was created
    active_mems = (
        db_session.query(CuratedMemory)
        .filter(CuratedMemory.tenant_id == tenant.id, CuratedMemory.status == "active")
        .all()
    )
    assert len(active_mems) == 0

    # Verify proposal is quarantined and rejected
    db_session.refresh(proposal)
    assert proposal.proposal_type == "quarantine"
    assert proposal.reason_code == "safety_violation"
    assert proposal.status == "rejected"


def test_behavioural_correction_interpretation(curator_setup, db_session):
    """Test 4: Behavioural correction interpretation (derives canonical rule and preserves source example per Spec 17, 27)."""
    tenant = curator_setup["tenant_a"]
    provider = curator_setup["provider_a1"]
    now = datetime.now(timezone.utc)

    event = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="flagged_response",
        source="production_messages",
        customer_message="Hi can I reschedule my appointment?",
        original_ai_content="Dear valued customer, we are deeply apologetic for any inconvenience caused. It would be our utmost honour to assist you.",
        human_content="Hey! No problem at all, what day and time works best for you instead?",
        metadata_payload={
            "reason": "Use concise, casual language for routine enquiries. Avoid customer-service phrases.",
            "category": "tone",
        },
        status="pending",
        confidence_score=1.0,
        created_at=now,
    )
    db_session.add(event)
    db_session.commit()

    result = AutonomousCuratorService.process_event(db_session, event)
    db_session.commit()

    assert result["status"] == "processed"
    assert result["action"] == "behavioural_guidance_curated"

    memory = (
        db_session.query(CuratedMemory)
        .filter(CuratedMemory.id == result["memory_id"])
        .first()
    )
    assert memory is not None
    assert memory.status == "active"
    assert memory.knowledge_kind == "response_guidance"
    assert "Use concise, casual language" in memory.ideal_response
    assert "Avoid customer-service phrases" in memory.ideal_response
    # Preserves source example as evidence
    assert "Hey! No problem at all" in memory.source_reference
    # Strict provider scoping (never system)
    assert memory.provider_id == provider.id
    assert memory.tenant_id == tenant.id


def test_conservative_generalization_on_draft_edits(curator_setup, db_session):
    """Test 5: Conservative generalization on draft edits (incidental wording edits do not create canonical rules per Spec 26)."""
    tenant = curator_setup["tenant_a"]
    provider = curator_setup["provider_a1"]
    now = datetime.now(timezone.utc)

    # 1. Incidental Edit: Minor punctuation/word fix (similarity > 0.85, delta < 5 chars)
    diff_incidental = compute_text_diff(
        "We look forward to seeing you tomorrow.",
        "We look forward to seeing you tomorrow!",
    )
    event_incidental = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="draft_edit",
        source="production_messages",
        original_ai_content="We look forward to seeing you tomorrow.",
        human_content="We look forward to seeing you tomorrow!",
        diff_payload=diff_incidental,
        status="pending",
        confidence_score=0.5,
        created_at=now,
    )
    db_session.add(event_incidental)
    db_session.commit()

    res_incidental = AutonomousCuratorService.process_event(db_session, event_incidental)
    db_session.commit()

    assert res_incidental["classification"] == "incidental"
    assert res_incidental["retained_as_evidence"] is True
    # Does NOT create any universal CuratedMemory
    mems = db_session.query(CuratedMemory).filter(CuratedMemory.tenant_id == tenant.id).all()
    assert len(mems) == 0

    # 2. Material Edit: Substantial rewording from corporate to casual slang
    orig_text = "Greetings esteemed client. We hereby confirm receipt of your inquiry."
    mod_text = "Hey mate! Got your message, all sorted."
    diff_material = compute_text_diff(orig_text, mod_text)
    event_material = LearningEvent(
        tenant_id=tenant.id,
        provider_id=provider.id,
        event_type="draft_edit",
        source="production_messages",
        original_ai_content=orig_text,
        human_content=mod_text,
        diff_payload=diff_material,
        status="pending",
        confidence_score=0.5,
        created_at=now,
    )
    db_session.add(event_material)
    db_session.commit()

    res_material = AutonomousCuratorService.process_event(db_session, event_material)
    db_session.commit()

    assert res_material["classification"] == "material"
    assert res_material["evidence_count"] >= 1

    # Check that style proposal records signal without blindly generating an unverified canonical memory
    proposal = (
        db_session.query(KnowledgeProposal)
        .filter(
            KnowledgeProposal.tenant_id == tenant.id,
            KnowledgeProposal.category == "style",
        )
        .first()
    )
    assert proposal is not None
    assert proposal.evidence_count == 1
    assert proposal.requires_review is True


def test_multi_tenant_and_provider_scope_isolation(curator_setup, db_session):
    """Test 6: Multi-tenant and provider scope isolation across curation batching and status."""
    tenant_a = curator_setup["tenant_a"]
    tenant_b = curator_setup["tenant_b"]
    provider_a1 = curator_setup["provider_a1"]
    provider_a2 = curator_setup["provider_a2"]
    now = datetime.now(timezone.utc)

    # Event for Tenant A (Provider A1)
    ev_a = LearningEvent(
        tenant_id=tenant_a.id,
        provider_id=provider_a1.id,
        event_type="knowledge_answer",
        source="production_messages",
        customer_message="Tenant A Provider 1 question",
        human_content="Tenant A Provider 1 answer",
        status="pending",
        confidence_score=1.0,
        created_at=now,
    )
    # Event for Tenant B
    ev_b = LearningEvent(
        tenant_id=tenant_b.id,
        provider_id=curator_setup["provider_b"].id,
        event_type="knowledge_answer",
        source="production_messages",
        customer_message="Tenant B question",
        human_content="Tenant B answer",
        status="pending",
        confidence_score=1.0,
        created_at=now,
    )
    db_session.add_all([ev_a, ev_b])
    db_session.commit()

    # Process only Tenant A's pending events
    summary_a = AutonomousCuratorService.process_pending_events(db_session, tenant_id=tenant_a.id)
    assert summary_a["processed"] == 1
    assert summary_a["curated"] == 1

    # Tenant B's event must still be pending
    db_session.refresh(ev_b)
    assert ev_b.status == "pending"

    # Status check for Tenant A vs Provider A1 vs Provider A2
    status_all_a = AutonomousCuratorService.get_curation_status(db_session, tenant_id=tenant_a.id)
    assert status_all_a["active_memories"] == 1
    assert status_all_a["scope_breakdown"]["provider_specific"] == 1

    status_p1 = AutonomousCuratorService.get_curation_status(
        db_session, tenant_id=tenant_a.id, provider_id=provider_a1.id
    )
    assert status_p1["active_memories"] == 1

    status_p2 = AutonomousCuratorService.get_curation_status(
        db_session, tenant_id=tenant_a.id, provider_id=provider_a2.id
    )
    assert status_p2["active_memories"] == 0

    # Tenant B status has 0 curated memories
    status_b = AutonomousCuratorService.get_curation_status(db_session, tenant_id=tenant_b.id)
    assert status_b["active_memories"] == 0


def test_curator_api_endpoints(client, curator_setup, db_session):
    """Test 7: Full coverage of curator API endpoints (process, status, memories, supersede, restore)."""
    headers_a = curator_setup["headers_a"]
    headers_b = curator_setup["headers_b"]
    tenant_a = curator_setup["tenant_a"]
    provider_a = curator_setup["provider_a1"]
    now = datetime.now(timezone.utc)

    # 1. Seed a pending event
    event = LearningEvent(
        tenant_id=tenant_a.id,
        provider_id=provider_a.id,
        event_type="knowledge_answer",
        source="production_messages",
        customer_message="What are your weekend hours?",
        human_content="We are open Saturdays 9am to 1pm and closed Sundays.",
        metadata_payload={"category": "hours"},
        status="pending",
        confidence_score=1.0,
        created_at=now,
    )
    db_session.add(event)
    db_session.commit()

    # 2. POST /api/admin/sms/curator/process
    resp_process = client.post("/api/admin/sms/curator/process", json={"limit": 10}, headers=headers_a)
    assert resp_process.status_code == status.HTTP_200_OK
    data_process = resp_process.json()
    assert data_process["ok"] is True
    assert data_process["processed"] == 1
    assert data_process["curated"] == 1

    # 3. GET /api/admin/sms/curator/status
    resp_status = client.get("/api/admin/sms/curator/status", headers=headers_a)
    assert resp_status.status_code == status.HTTP_200_OK
    data_status = resp_status.json()["data"]
    assert data_status["active_memories"] == 1
    assert data_status["processed_learning_events"] == 1

    # 4. GET /api/admin/sms/curator/memories
    resp_memories = client.get("/api/admin/sms/curator/memories?status=active", headers=headers_a)
    assert resp_memories.status_code == status.HTTP_200_OK
    data_memories = resp_memories.json()
    assert data_memories["ok"] is True
    assert data_memories["total"] == 1
    memory_item = data_memories["items"][0]
    assert memory_item["user_query"] == "What are your weekend hours?"
    assert memory_item["status"] == "active"
    memory_id = memory_item["id"]

    # 5. POST /api/admin/sms/curator/memories/{id}/supersede
    resp_supersede = client.post(
        f"/api/admin/sms/curator/memories/{memory_id}/supersede",
        headers=headers_a,
    )
    assert resp_supersede.status_code == status.HTTP_200_OK
    assert resp_supersede.json()["data"]["status"] == "superseded"

    # Verify status changed in list query
    resp_active_now = client.get("/api/admin/sms/curator/memories?status=active", headers=headers_a)
    assert resp_active_now.json()["total"] == 0

    # 6. POST /api/admin/sms/curator/memories/{id}/restore
    resp_restore = client.post(
        f"/api/admin/sms/curator/memories/{memory_id}/restore",
        headers=headers_a,
    )
    assert resp_restore.status_code == status.HTTP_200_OK
    assert resp_restore.json()["data"]["status"] == "active"

    # 7. Cross-tenant isolation check: Tenant B attempting to supersede Tenant A's memory gets 404
    resp_cross = client.post(
        f"/api/admin/sms/curator/memories/{memory_id}/supersede",
        headers=headers_b,
    )
    assert resp_cross.status_code == status.HTTP_404_NOT_FOUND
