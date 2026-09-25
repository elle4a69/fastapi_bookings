"""End-to-End Upgrade Verification Suite for Phases 11 to 14 (Spec 108).

Verifies all Spec 108 Completion Criteria:
- Criterion 1 (Explicit Teaching): Provider answers info request in Messages -> answer is curated and retrievable via knowledge_gateway without second approval.
- Criterion 2 (Bootcamp to Production): Provider teaches agent in Bootcamp (source="bootcamp") -> same provider's production retrieval uses it.
- Criterion 3 (Isolation): Provider B in same tenant cannot retrieve Provider A's private fact unless explicitly tenant-shared.
- Criterion 4 (Behavioural Learning): Provider draft edit captures behavioural evidence.
- Criterion 5 (Temporal Supersession): Explicit changed fact marks old fact superseded in PostgreSQL and enqueues supersession in projection ledger.
- Criterion 6 (Operational Truth Wins): Live booking / availability operational state overrides graph context in prompt precedence (Spec 53).
- Criterion 7 (Bounded Scale): 100+ knowledge items produce strictly bounded context (<= 5 facts, 3 behaviours, 2 examples).
- Criterion 8 (Graph Rebuild): Graph can be reconstructed from PostgreSQL using knowledge_rebuild_service.
- Criterion 9 (Redis Loss): Flushed/offline Redis still permits successful retrieval via Graphiti/PostgreSQL fallback.
- Criterion 10 (PostgreSQL Authority): PostgreSQL remains authoritative source of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch
import pytest
from fastapi import status
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.config import settings
from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User
from app.models.provider import Provider
from app.models.service import Service
from app.models.curated_memory import CuratedMemory, KnowledgeProposal
from app.models.learning_event import LearningEvent
from app.models.knowledge_projection import KnowledgeGraphProjection
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_bootcamp import (
    SmsBootcampConversation,
    SmsBootcampMessage,
    SmsBootcampRun,
    SmsBootcampSettings,
)
from app.models.sms_knowledge import SmsKnowledgeEntry
from app.services.knowledge.types import (
    Authority,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeScope,
    RetrievalQuery,
    RetrievalResult,
)
from app.services.knowledge.gateway import knowledge_gateway
from app.services.knowledge.curator import unified_curator
from app.services.knowledge.rebuild import knowledge_rebuild_service
from app.services.knowledge.cache import clear_in_memory_cache
from app.services.sms.prompt_builder import UnifiedPromptBuilder


def _auth_headers(tenant: Tenant, admin_user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(admin_user.id)})
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": token,
    }


@pytest.fixture
def cutover_fixture(db_session):
    """Setup multi-tenant, multi-provider fixture for Phase 11-14 verification."""
    clear_in_memory_cache()

    tenant_a = Tenant(name="Cutover Dental", subdomain="cutover-dental")
    tenant_b = Tenant(name="Cutover Physio", subdomain="cutover-physio")
    db_session.add_all([tenant_a, tenant_b])
    db_session.flush()

    admin_a = User(
        tenant_id=tenant_a.id,
        login="admin-cutover-a@example.com",
        password_hash="synthetic-pass-a",
        role="admin",
    )
    admin_b = User(
        tenant_id=tenant_b.id,
        login="admin-cutover-b@example.com",
        password_hash="synthetic-pass-b",
        role="admin",
    )
    db_session.add_all([admin_a, admin_b])
    db_session.flush()

    prov_a1 = Provider(tenant_id=tenant_a.id, name="Dr. Alex Carter", active=True)
    prov_a2 = Provider(tenant_id=tenant_a.id, name="Dr. Beatrice Vane", active=True)
    prov_b = Provider(tenant_id=tenant_b.id, name="Dr. Bryan Smith", active=True)
    db_session.add_all([prov_a1, prov_a2, prov_b])
    db_session.flush()

    sms_acc_a1 = SmsAccount(
        tenant_id=tenant_a.id,
        provider_id=prov_a1.id,
        sender_address="+61400111222",
        display_name="Line 1",
        transport_type="simulator",
        is_enabled=True,
        ai_enabled=True,
        ai_mode="autopilot",
    )
    db_session.add(sms_acc_a1)
    db_session.flush()

    conv_a1 = SmsConversation(
        tenant_id=tenant_a.id,
        provider_id=prov_a1.id,
        sms_account_id=sms_acc_a1.id,
        customer_address="+61499888777",
        state="needs-review",
        unread_count=1,
    )
    db_session.add(conv_a1)
    db_session.commit()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "prov_a1": prov_a1,
        "prov_a2": prov_a2,
        "prov_b": prov_b,
        "sms_acc_a1": sms_acc_a1,
        "conv_a1": conv_a1,
    }


# =============================================================================
# Criterion 1 (Explicit Teaching): Messages Info Request Auto-Curated
# =============================================================================
def test_criterion_1_explicit_teaching_in_messages(client, cutover_fixture, db_session):
    """Provider answers info request in Messages -> answer is curated and retrievable

    via knowledge_gateway without second approval (Spec 108 Criterion 1).
    Also verifies NO duplicate write to SmsKnowledgeEntry (Phase 12 / Spec 27).
    """
    t_a = cutover_fixture["tenant_a"]
    admin_a = cutover_fixture["admin_a"]
    p_a1 = cutover_fixture["prov_a1"]
    conv = cutover_fixture["conv_a1"]
    headers = _auth_headers(t_a, admin_a)

    ske_count_before = db_session.query(SmsKnowledgeEntry).count()

    response = client.post(
        f"/api/admin/sms/conversations/{conv.id}/answer-info-request?auto_curate=true",
        json={
            "question": "Do you provide nitrous oxide sedation for anxious patients?",
            "answer": "Yes, nitrous oxide happy gas sedation is available for anxious patients upon request.",
            "category": "services",
        },
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "success"
    assert data["curated_memory_id"] is not None

    # Verify no duplicate write to legacy SmsKnowledgeEntry
    assert db_session.query(SmsKnowledgeEntry).count() == ske_count_before

    # Verify CuratedMemory exists with status 'active' without requiring a second review
    mem = db_session.query(CuratedMemory).filter(CuratedMemory.id == data["curated_memory_id"]).one()
    assert mem.status == "active"
    assert mem.tenant_id == t_a.id
    assert mem.provider_id == p_a1.id
    assert "nitrous oxide" in mem.ideal_response.lower()

    # Verify KnowledgeGraphProjection ledger outbox entry created
    proj = (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.curated_memory_id == mem.id)
        .first()
    )
    assert proj is not None
    assert proj.status == "pending"
    assert proj.projection_type == "upsert_fact"

    # Verify immediately retrievable via Knowledge Gateway
    query = RetrievalQuery(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        query="Can I get nitrous oxide sedation?",
    )
    res = knowledge_gateway.retrieve(query, db=db_session)
    assert res is not None
    assert any("nitrous oxide" in f.lower() for f in res.facts)


# =============================================================================
# Criterion 2 (Bootcamp to Production): Bootcamp Teaching Retrievable in Production
# =============================================================================
def test_criterion_2_bootcamp_teaching_retrievable_in_production(client, cutover_fixture, db_session):
    """Provider teaches agent in Bootcamp (source='bootcamp') -> same provider's

    production retrieval uses it (Spec 108 Criterion 2).
    """
    t_a = cutover_fixture["tenant_a"]
    admin_a = cutover_fixture["admin_a"]
    p_a1 = cutover_fixture["prov_a1"]
    headers = _auth_headers(t_a, admin_a)

    # Create Bootcamp Run & Conversation
    run = SmsBootcampRun(
        id=str(uuid.uuid4()),
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        status="running",
        selected_personas=["persona-anxious"],
    )
    db_session.add(run)
    db_session.flush()

    bootcamp_conv = SmsBootcampConversation(
        id=str(uuid.uuid4()),
        run_id=run.id,
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        persona_id="persona-anxious",
        persona_name="Anxious Alex",
        status="handoff",
        needs_handoff=True,
        handoff_reason="What parking options are available at the clinic?",
    )
    db_session.add(bootcamp_conv)

    msg_customer = SmsBootcampMessage(
        id=str(uuid.uuid4()),
        conversation_id=bootcamp_conv.id,
        tenant_id=t_a.id,
        role="persona",
        text="What parking options are available at the clinic?",
    )
    db_session.add(msg_customer)
    db_session.commit()

    # Provider responds to info request in Bootcamp
    resp = client.post(
        f"/api/admin/sms/bootcamp/conversations/{bootcamp_conv.id}/information-request/respond",
        json={
            "information": "Underground secure visitor parking is free for the first 2 hours on Level B1.",
        },
        headers=headers,
    )
    assert resp.status_code == status.HTTP_200_OK

    # Verify LearningEvent has source='bootcamp'
    event = (
        db_session.query(LearningEvent)
        .filter(LearningEvent.conversation_id == bootcamp_conv.id)
        .order_by(LearningEvent.created_at.desc())
        .first()
    )
    assert event is not None
    assert event.source == "bootcamp"
    assert event.status == "processed"

    # Verify production retrieval for this provider immediately retrieves the taught parking fact
    prod_query = RetrievalQuery(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        query="Where do I park my car for the appointment?",
    )
    prod_result = knowledge_gateway.retrieve(prod_query, db=db_session)
    assert any("underground" in f.lower() or "parking" in f.lower() for f in prod_result.facts)


# =============================================================================
# Criterion 3 (Isolation): Provider B Cannot Retrieve Provider A's Private Fact
# =============================================================================
def test_criterion_3_provider_and_tenant_isolation(cutover_fixture, db_session):
    """Provider B in same tenant cannot retrieve Provider A's private fact

    unless explicitly tenant-shared (Spec 108 Criterion 3).
    """
    t_a = cutover_fixture["tenant_a"]
    p_a1 = cutover_fixture["prov_a1"]
    p_a2 = cutover_fixture["prov_a2"]
    now = datetime.now(timezone.utc)

    # 1. Provider A private fact
    mem_private_a = CuratedMemory(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        category="specialty",
        user_query="What is Dr. Alex's special laser certification?",
        ideal_response="Dr. Alex is uniquely certified in Fotona LightWalker laser treatments.",
        knowledge_kind="durable_fact",
        authority="owner_verified",
        status="active",
        conflict_state="clear",
        created_at=now,
    )

    # 2. Tenant shared fact (provider_id is None)
    mem_shared = CuratedMemory(
        tenant_id=t_a.id,
        provider_id=None,
        category="general",
        user_query="What is the clinic wifi password?",
        ideal_response="Guest wifi is 'CutoverGuest2026' available throughout the waiting lounge.",
        knowledge_kind="durable_fact",
        authority="owner_verified",
        status="active",
        conflict_state="clear",
        created_at=now,
    )
    db_session.add_all([mem_private_a, mem_shared])
    db_session.commit()
    knowledge_gateway.invalidate(t_a.id, p_a1.id)
    knowledge_gateway.invalidate(t_a.id, p_a2.id)

    # Provider A retrieves both private and shared facts
    q_a = RetrievalQuery(tenant_id=t_a.id, provider_id=p_a1.id, query="Tell me about laser certification and wifi")
    res_a = knowledge_gateway.retrieve(q_a, db=db_session)
    assert any("fotona" in f.lower() for f in res_a.facts)
    assert any("wifi" in f.lower() for f in res_a.facts)

    # Provider B in same tenant CANNOT retrieve Provider A's private fact
    q_b = RetrievalQuery(tenant_id=t_a.id, provider_id=p_a2.id, query="Tell me about laser certification and wifi")
    res_b = knowledge_gateway.retrieve(q_b, db=db_session)
    assert not any("fotona" in f.lower() for f in res_b.facts)  # Strict provider isolation!
    assert any("wifi" in f.lower() for f in res_b.facts)       # Shared fact accessible


# =============================================================================
# Criterion 4 (Behavioural Learning): Provider Draft Edit Captures Behavioural Evidence
# =============================================================================
def test_criterion_4_behavioural_learning_from_draft_edits(cutover_fixture, db_session):
    """Provider draft edit captures behavioural evidence without prompt pollution (Spec 108 Criterion 4)."""
    t_a = cutover_fixture["tenant_a"]
    p_a1 = cutover_fixture["prov_a1"]

    # 1. Minor / incidental edit -> NOOP classification
    incidental_event = LearningEvent(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        event_type="draft_edit",
        source="production_messages",
        customer_message="Hi can I come by today?",
        original_ai_content="Yes, we have availability today.",
        human_content="Yes! We have availability today.",
        status="pending",
        diff_payload={"ratio": 0.96, "original_length": 32, "new_length": 33},
        created_at=datetime.now(timezone.utc),
    )
    decision_incidental = unified_curator.process_learning_event(db_session, incidental_event)
    assert decision_incidental.action == "NOOP"
    assert decision_incidental.retained_as_evidence is True

    # 2. Material draft edit -> Behavioural evidence proposal created
    material_event = LearningEvent(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        event_type="draft_edit",
        source="production_messages",
        customer_message="How painful is the root canal treatment?",
        original_ai_content="The procedure is quite manageable with local anesthesia.",
        human_content="Root canal treatments here are virtually painless! We apply a gentle numbing gel before any injection so you will barely feel a pinch.",
        status="pending",
        diff_payload={"ratio": 0.35, "original_length": 55, "new_length": 140},
        created_at=datetime.now(timezone.utc),
    )
    decision_material = unified_curator.process_learning_event(db_session, material_event)
    assert decision_material.action == "EVIDENCE"
    assert decision_material.classification == "material"

    # Proposal created for curator review with style category
    proposal = db_session.query(KnowledgeProposal).filter(KnowledgeProposal.id == decision_material.proposal_id).one()
    assert proposal.category == "style"
    assert proposal.knowledge_kind == "style_example"
    assert proposal.authority == "draft_edit_signal"


# =============================================================================
# Criterion 5 (Temporal Supersession): Old Fact Marked Superseded & Enqueued
# =============================================================================
def test_criterion_5_temporal_supersession(cutover_fixture, db_session):
    """Explicit changed fact marks old fact superseded in PostgreSQL and

    enqueues supersession in projection ledger (Spec 108 Criterion 5).
    """
    t_a = cutover_fixture["tenant_a"]
    p_a1 = cutover_fixture["prov_a1"]

    # 1. Initial fact
    event_initial = LearningEvent(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        event_type="knowledge_answer",
        source="production_messages",
        customer_message="What is your cancellation policy?",
        human_content="Appointments must be cancelled at least 24 hours in advance to avoid a fee.",
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    decision_1 = unified_curator.process_learning_event(db_session, event_initial)
    mem_1 = db_session.query(CuratedMemory).filter(CuratedMemory.id == decision_1.memory_id).one()
    assert mem_1.status == "active"

    # 2. Provider changes policy to 48 hours notice
    event_supersede = LearningEvent(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        event_type="knowledge_answer",
        source="production_messages",
        customer_message="What is your cancellation policy?",
        human_content="Appointments must be cancelled at least 48 hours in advance due to high demand.",
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    decision_2 = unified_curator.process_learning_event(db_session, event_supersede)
    db_session.refresh(mem_1)

    # Verify old fact is superseded in PostgreSQL
    assert mem_1.status == "superseded"

    # Verify new memory links to old memory via supersedes_id
    mem_2 = db_session.query(CuratedMemory).filter(CuratedMemory.id == decision_2.memory_id).one()
    assert mem_2.status == "active"
    assert mem_2.supersedes_id == mem_1.id

    # Verify supersession projection enqueued
    supersede_proj = (
        db_session.query(KnowledgeGraphProjection)
        .filter(
            KnowledgeGraphProjection.curated_memory_id == mem_2.id,
            KnowledgeGraphProjection.projection_type == "supersede_fact",
        )
        .first()
    )
    assert supersede_proj is not None
    assert supersede_proj.status == "pending"

    # Verify live retrieval returns the updated 48h policy, NOT the 24h policy
    query = RetrievalQuery(tenant_id=t_a.id, provider_id=p_a1.id, query="What is your cancellation policy?")
    res = knowledge_gateway.retrieve(query, db=db_session)
    assert any("48 hours" in f for f in res.facts)
    assert not any("24 hours" in f for f in res.facts)


# =============================================================================
# Criterion 6 (Operational Truth Wins): Operational State Precedes Knowledge
# =============================================================================
def test_criterion_6_operational_truth_wins_precedence(cutover_fixture, db_session):
    """Live booking / availability operational state overrides graph context

    in prompt precedence (Spec 53, 54 / Spec 108 Criterion 6).
    """
    t_a = cutover_fixture["tenant_a"]
    p_a1 = cutover_fixture["prov_a1"]

    # Graph retrieval result states: standard fee $120
    retrieval_res = RetrievalResult(
        facts=["Standard dental consultation is $120."],
        behavioural_rules=["Maintain a cheerful, professional tone."],
        examples=[],
    )

    # Live authoritative operational configuration states: standard fee $150
    live_service = Service(
        tenant_id=t_a.id,
        name="Standard Dental Consultation",
        price=150.0,
        duration=30,
        active=True,
    )
    db_session.add(live_service)
    db_session.commit()

    builder = (
        UnifiedPromptBuilder(tenant_id=t_a.id, provider_id=p_a1.id)
        .with_core_safety()
        .with_structured_config(provider=p_a1, services=[live_service])
        .with_retrieval_result(retrieval_res)
        .with_spec_54(True)
    )

    prompt_str = builder.build_system_prompt()
    assert "--- CURRENT APPLICATION / TOOL TRUTH ---" in prompt_str
    assert "--- CURATED FACTUAL CONTEXT ---" in prompt_str

    # Layer 2 (Application/Tool Truth) MUST appear BEFORE Layer 6 (Curated Factual Context)
    idx_app_truth = prompt_str.index("--- CURRENT APPLICATION / TOOL TRUTH ---")
    idx_knowledge = prompt_str.index("--- CURATED FACTUAL CONTEXT ---")
    assert idx_app_truth < idx_knowledge, "Live operational truth must win over graph knowledge in prompt precedence!"

    # In discrete messages payload, Layer 2 message must precede Layer 6 message
    messages = builder.build_messages_payload(discrete_system_messages=True)
    roles_content = [m["content"] for m in messages]
    idx_msg_app_truth = next(i for i, c in enumerate(roles_content) if "Available Services & Pricing:" in c)
    idx_msg_knowledge = next(i for i, c in enumerate(roles_content) if "Factual Context:" in c)
    assert idx_msg_app_truth < idx_msg_knowledge


# =============================================================================
# Criterion 7 (Bounded Scale): 100+ Knowledge Items Capped Strictly
# =============================================================================
def test_criterion_7_bounded_scale(cutover_fixture, db_session):
    """100+ knowledge items produce strictly bounded context

    (<= 5 facts, 3 behaviours, 2 examples) (Spec 48 / Spec 108 Criterion 7).
    """
    t_a = cutover_fixture["tenant_a"]
    p_a1 = cutover_fixture["prov_a1"]
    now = datetime.now(timezone.utc)

    # Seed 60 facts
    for i in range(60):
        db_session.add(
            CuratedMemory(
                tenant_id=t_a.id,
                provider_id=p_a1.id,
                category="facts",
                user_query=f"Scale query {i}",
                ideal_response=f"Clinic scale fact item number {i} regarding treatments and policies.",
                knowledge_kind="durable_fact",
                authority="owner_verified",
                status="active",
                conflict_state="clear",
                created_at=now,
            )
        )

    # Seed 30 behavioural rules
    for i in range(30):
        db_session.add(
            CuratedMemory(
                tenant_id=t_a.id,
                provider_id=p_a1.id,
                category="tone",
                user_query=f"Tone query {i}",
                ideal_response=f"Behavioural rule {i}: Be polite and respectful at all times.",
                knowledge_kind="response_guidance",
                authority="owner_verified",
                status="active",
                conflict_state="clear",
                created_at=now,
            )
        )

    # Seed 20 style examples
    for i in range(20):
        db_session.add(
            CuratedMemory(
                tenant_id=t_a.id,
                provider_id=p_a1.id,
                category="example",
                user_query=f"Example query {i}",
                ideal_response=f"Style example {i}: Example phrasing for booking appointment.",
                knowledge_kind="style_example",
                authority="owner_verified",
                status="active",
                conflict_state="clear",
                created_at=now,
            )
        )
    db_session.commit()
    knowledge_gateway.invalidate(t_a.id, p_a1.id)

    query = RetrievalQuery(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        query="Clinic treatments, tone, and booking examples",
    )
    res = knowledge_gateway.retrieve(query, db=db_session)

    # Must be bounded strictly by limits
    assert len(res.facts) <= settings.KNOWLEDGE_FACTS_LIMIT
    assert len(res.facts) <= 5
    assert len(res.behavioural_rules) <= settings.KNOWLEDGE_BEHAVIOUR_LIMIT
    assert len(res.behavioural_rules) <= 3
    assert len(res.examples) <= settings.KNOWLEDGE_EXAMPLES_LIMIT
    assert len(res.examples) <= 2


# =============================================================================
# Criterion 8 (Graph Rebuild): Reconstruct Projections from PostgreSQL
# =============================================================================
def test_criterion_8_graph_rebuild_from_postgresql(cutover_fixture, db_session):
    """Graph can be reconstructed from PostgreSQL using knowledge_rebuild_service

    (Spec 56, 58, 60 / Spec 108 Criterion 8).
    """
    t_a = cutover_fixture["tenant_a"]
    p_a1 = cutover_fixture["prov_a1"]
    now = datetime.now(timezone.utc)

    # Clear existing projections
    db_session.query(KnowledgeGraphProjection).filter(
        KnowledgeGraphProjection.tenant_id == t_a.id
    ).delete()
    db_session.commit()

    # Create 3 CuratedMemories
    for i in range(3):
        db_session.add(
            CuratedMemory(
                tenant_id=t_a.id,
                provider_id=p_a1.id,
                category="rebuild_test",
                user_query=f"Rebuild query {i}",
                ideal_response=f"Rebuild fact {i} from ground truth.",
                knowledge_kind="durable_fact",
                authority="owner_verified",
                status="active",
                conflict_state="clear",
                created_at=now,
            )
        )
    db_session.commit()

    # Run rebuild backfill
    stats = knowledge_rebuild_service.backfill_curated_memories(
        db=db_session,
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        dry_run=False,
    )
    assert stats["scanned"] >= 3
    assert stats["projected"] >= 3

    # Verify projections reconstructed in ledger
    projs = (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.tenant_id == t_a.id)
        .all()
    )
    assert len(projs) >= 3
    assert all(p.status == "pending" for p in projs)


# =============================================================================
# Criterion 9 (Redis Loss): Retrieval Survives Complete Redis Flush / Outage
# =============================================================================
def test_criterion_9_redis_loss_tolerance(cutover_fixture, db_session):
    """Flushed/offline Redis still permits successful retrieval via

    Graphiti/PostgreSQL fallback (Spec 51, 98 / Spec 108 Criterion 9).
    """
    t_a = cutover_fixture["tenant_a"]
    p_a1 = cutover_fixture["prov_a1"]
    now = datetime.now(timezone.utc)

    db_session.add(
        CuratedMemory(
            tenant_id=t_a.id,
            provider_id=p_a1.id,
            category="emergency",
            user_query="What to do in a dental emergency?",
            ideal_response="For severe dental trauma, call our emergency hotline directly on 1800-DENTAL.",
            knowledge_kind="durable_fact",
            authority="owner_verified",
            status="active",
            conflict_state="clear",
            created_at=now,
        )
    )
    db_session.commit()
    knowledge_gateway.invalidate(t_a.id, p_a1.id)

    # Simulate complete Redis failure
    with patch("app.services.knowledge.cache.get_redis_client", side_effect=RedisConnectionError("Redis connection refused")):
        query = RetrievalQuery(
            tenant_id=t_a.id,
            provider_id=p_a1.id,
            query="dental emergency",
        )
        res = knowledge_gateway.retrieve(query, db=db_session)
        assert res is not None
        assert any("emergency hotline" in f.lower() for f in res.facts)


# =============================================================================
# Criterion 10 (PostgreSQL Authority): PostgreSQL Remains Authoritative Truth
# =============================================================================
def test_criterion_10_postgresql_authority(cutover_fixture, db_session):
    """PostgreSQL remains authoritative source of truth: mutations root in PostgreSQL

    before external projection or caching (Spec 83 / Spec 108 Criterion 10).
    """
    t_a = cutover_fixture["tenant_a"]
    p_a1 = cutover_fixture["prov_a1"]

    event = LearningEvent(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        event_type="knowledge_answer",
        source="production_messages",
        customer_message="Do you provide child dental benefits?",
        human_content="Yes, we bulk bill eligible children under the Child Dental Benefits Schedule (CDBS).",
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    decision = unified_curator.process_learning_event(db_session, event)

    # 1. State recorded in PostgreSQL CuratedMemory
    mem = db_session.query(CuratedMemory).filter(CuratedMemory.id == decision.memory_id).one()
    assert mem.id is not None
    assert mem.status == "active"
    assert "Child Dental Benefits Schedule" in mem.ideal_response

    # 2. State recorded in PostgreSQL KnowledgeGraphProjection ledger
    proj = (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.curated_memory_id == mem.id)
        .one()
    )
    assert proj.status == "pending"
    assert proj.projection_type == "upsert_fact"

    # 3. PostgreSQL query returns authoritative item directly
    query = RetrievalQuery(
        tenant_id=t_a.id,
        provider_id=p_a1.id,
        query="child dental benefits",
    )
    res = knowledge_gateway.retrieve(query, db=db_session)
    assert any("child dental benefits" in f.lower() for f in res.facts)
