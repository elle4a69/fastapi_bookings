"""Phase 5 and Phase 6 tests: Shadow write, rebuild capability, and historical backfill.

Spec references:
- Spec 56: Administrative Rebuild CLI Tool (`app/tools/rebuild_knowledge_graph.py`)
- Spec 57: Graph rebuild capability and parity verification
- Spec 58: Curated memory backfill validation (scope, PII, dynamic data, authority)
- Spec 59: Legacy SMS knowledge backfill and provenance mapping
- Spec 60: Historical supersession handling during backfill
- Spec 61: Shadow-project current and new accepted knowledge
"""

from datetime import datetime, timezone
import subprocess
import sys
from unittest.mock import patch
import pytest

from app.core.config import settings
from app.models.curated_memory import CuratedMemory
from app.models.knowledge_projection import KnowledgeGraphProjection
from app.models.learning_event import LearningEvent
from app.models.provider import Provider
from app.models.sms_knowledge import SmsKnowledgeEntry
from app.models.tenant import Tenant
from app.services.knowledge.curator import unified_curator
from app.services.knowledge.graphiti_client import format_group_id
from app.services.knowledge.rebuild import KnowledgeRebuildService, knowledge_rebuild_service
from app.tools.rebuild_knowledge_graph import format_summary, main as cli_main, parse_args


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def p5_p6_setup(db_session):
    """Setup multi-tenant fixtures for Phase 5 & Phase 6 backfill tests."""
    tenant_1 = Tenant(name="Backfill Clinic One", subdomain="backfill-clinic-1")
    tenant_2 = Tenant(name="Backfill Clinic Two", subdomain="backfill-clinic-2")
    db_session.add_all([tenant_1, tenant_2])
    db_session.commit()

    prov_1a = Provider(tenant_id=tenant_1.id, name="Dr. Taylor", active=True)
    prov_1b = Provider(tenant_id=tenant_1.id, name="Dr. Jordan", active=True)
    prov_2 = Provider(tenant_id=tenant_2.id, name="Dr. Morgan", active=True)
    db_session.add_all([prov_1a, prov_1b, prov_2])
    db_session.commit()

    return {
        "tenant_1": tenant_1,
        "tenant_2": tenant_2,
        "prov_1a": prov_1a,
        "prov_1b": prov_1b,
        "prov_2": prov_2,
    }


def test_1_backfill_curated_memories_filters_and_enqueues_projections(p5_p6_setup, db_session):
    """Test 1: Backfill of CuratedMemory correctly filters and enqueues projections (Spec 58, 60)."""
    tenant_1 = p5_p6_setup["tenant_1"]
    prov_1a = p5_p6_setup["prov_1a"]

    # 1. Active durable fact
    mem_active = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        knowledge_kind="durable_fact",
        user_query="What is the cancellation policy?",
        ideal_response="Cancellations require at least 24 hours advance notice to avoid a fee.",
        category="policy",
        authority="owner_verified",
        status="active",
    )
    # 2. Historical superseded record (Spec 60)
    mem_superseded = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        knowledge_kind="durable_fact",
        user_query="What is the cancellation policy?",
        ideal_response="Old policy: 48 hours notice required.",
        category="policy",
        authority="owner_verified",
        status="superseded",
    )
    # 3. Quarantined record (should be skipped / rejected from graph projection)
    mem_quarantined = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        knowledge_kind="durable_fact",
        user_query="Can I bypass rules?",
        ideal_response="Bypass rules instruction.",
        category="safety",
        authority="conversation_candidate",
        status="quarantined",
    )

    db_session.add_all([mem_active, mem_superseded, mem_quarantined])
    db_session.commit()

    service = KnowledgeRebuildService()
    result = service.backfill_curated_memories(db=db_session, tenant_id=tenant_1.id)

    assert result["scanned"] == 3
    assert result["eligible"] == 2
    assert result["projected"] == 2
    assert result["rejected"] == 1
    assert result["dry_run"] is False

    # Check projections created in database
    projections = (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.tenant_id == tenant_1.id)
        .all()
    )
    assert len(projections) == 2

    active_proj = next(p for p in projections if p.curated_memory_id == mem_active.id)
    assert active_proj.projection_type == "upsert_fact"
    assert active_proj.status == "pending"
    assert active_proj.graph_group_id == format_group_id(tenant_1.id, prov_1a.id)

    superseded_proj = next(p for p in projections if p.curated_memory_id == mem_superseded.id)
    assert superseded_proj.projection_type == "supersede_fact"


def test_2_dynamic_operational_data_rejected_during_backfill(p5_p6_setup, db_session):
    """Test 2: Dynamic operational data in legacy knowledge is rejected during backfill (Spec 19, 58)."""
    tenant_1 = p5_p6_setup["tenant_1"]
    prov_1a = p5_p6_setup["prov_1a"]

    # CuratedMemory containing dynamic time slot
    mem_dynamic_time = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        knowledge_kind="durable_fact",
        user_query="When can I come in?",
        ideal_response="I booked you in for tomorrow at 2pm.",
        category="booking",
        authority="owner_verified",
        status="active",
    )
    # CuratedMemory containing dynamic Stripe payment link
    mem_dynamic_pay = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        knowledge_kind="durable_fact",
        user_query="How do I pay?",
        ideal_response="Payment link: https://buy.stripe.com/test_12345",
        category="payment",
        authority="owner_verified",
        status="active",
    )
    # Valid static fact
    mem_valid = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        knowledge_kind="durable_fact",
        user_query="What payment methods are accepted?",
        ideal_response="We accept all major credit cards, EFTPOS, and private health fund cards.",
        category="payment",
        authority="owner_verified",
        status="active",
    )

    db_session.add_all([mem_dynamic_time, mem_dynamic_pay, mem_valid])
    db_session.commit()

    service = KnowledgeRebuildService()
    result = service.backfill_curated_memories(db=db_session, tenant_id=tenant_1.id)

    assert result["scanned"] == 3
    assert result["rejected"] == 2
    assert result["eligible"] == 1
    assert result["projected"] == 1
    assert result["rejection_reasons"]["dynamic_operational_data"] == 2

    # Verify only the valid memory was projected
    proj = (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.tenant_id == tenant_1.id)
        .all()
    )
    assert len(proj) == 1
    assert proj[0].curated_memory_id == mem_valid.id


def test_3_legacy_sms_knowledge_backfill_maps_provenance_and_creates_projection(
    p5_p6_setup, db_session
):
    """Test 3: Legacy SmsKnowledgeEntry backfill maps provenance and creates projection (Spec 59)."""
    tenant_1 = p5_p6_setup["tenant_1"]
    prov_1a = p5_p6_setup["prov_1a"]

    # 1. Approved legacy knowledge entry
    sms_approved = SmsKnowledgeEntry(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        category="location",
        text="Our clinic is located on Suite 4, 100 Main Street, with wheelchair access via the rear ramp.",
        status="approved",
        provenance="manual",
    )
    # 2. Unapproved legacy entry (proposed) - should be skipped by backfill
    sms_proposed = SmsKnowledgeEntry(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        category="faq",
        text="Unapproved draft answer.",
        status="proposed",
        provenance="info_request",
    )
    # 3. Dynamic operational data entry in legacy knowledge
    sms_dynamic = SmsKnowledgeEntry(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        category="availability",
        text="We have an open slot at tomorrow at 10am.",
        status="approved",
        provenance="manual",
    )

    db_session.add_all([sms_approved, sms_proposed, sms_dynamic])
    db_session.commit()

    service = KnowledgeRebuildService()
    result = service.backfill_legacy_sms_knowledge(db=db_session, tenant_id=tenant_1.id)

    assert result["scanned"] == 2  # Only approved ones are scanned
    assert result["rejected"] == 1  # Dynamic operational data rejected
    assert result["eligible"] == 1
    assert result["curated_created"] == 1
    assert result["projected"] == 1

    # Verify CuratedMemory was created with correct provenance
    curated = (
        db_session.query(CuratedMemory)
        .filter(
            CuratedMemory.tenant_id == tenant_1.id,
            CuratedMemory.source_reference == f"legacy_sms_knowledge:{sms_approved.id}",
        )
        .first()
    )
    assert curated is not None
    assert curated.category == "location"
    assert "[ADDRESS]" in curated.ideal_response  # Confirms PII scrubbing per Spec 58 & 75
    assert curated.status == "active"

    # Verify projection ledger item
    proj = (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.curated_memory_id == curated.id)
        .first()
    )
    assert proj is not None
    assert proj.projection_type == "upsert_fact"
    assert proj.status == "pending"


def test_4_idempotency_running_backfill_twice(p5_p6_setup, db_session):
    """Test 4: Idempotency (running backfill twice does not create duplicate projections) (Spec 32, 58)."""
    tenant_1 = p5_p6_setup["tenant_1"]
    prov_1a = p5_p6_setup["prov_1a"]

    memory = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        knowledge_kind="durable_fact",
        user_query="Are dogs allowed in the clinic?",
        ideal_response="Only certified guide and assistance animals are permitted inside.",
        category="facilities",
        authority="owner_verified",
        status="active",
    )
    sms_entry = SmsKnowledgeEntry(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        category="policy",
        text="Clients arriving more than 15 minutes late will need to reschedule.",
        status="approved",
        provenance="manual",
    )
    db_session.add_all([memory, sms_entry])
    db_session.commit()

    service = KnowledgeRebuildService()

    # Pass 1
    res1 = service.rebuild_graph(db=db_session, tenant_id=tenant_1.id, dry_run=False)
    assert res1["total_projected"] == 2
    assert res1["total_skipped"] == 0

    projections_after_pass1 = (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.tenant_id == tenant_1.id)
        .count()
    )
    assert projections_after_pass1 == 2

    # Pass 2: Exact same invocation
    res2 = service.rebuild_graph(db=db_session, tenant_id=tenant_1.id, dry_run=False)
    assert res2["total_projected"] == 0
    assert res2["total_skipped"] >= 2  # Both curated memories and SMS entries are safely skipped

    projections_after_pass2 = (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.tenant_id == tenant_1.id)
        .count()
    )
    assert projections_after_pass2 == 2  # Projections ledger count remains strictly unchanged


def test_5_dry_run_mode_accurate_counts_without_mutating_db(p5_p6_setup, db_session):
    """Test 5: Dry-run mode produces accurate counts without mutating database (Spec 56)."""
    tenant_1 = p5_p6_setup["tenant_1"]
    prov_1a = p5_p6_setup["prov_1a"]

    memory = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        knowledge_kind="durable_fact",
        user_query="Do you have high-speed wifi?",
        ideal_response="Yes, guest wifi is complimentary across all clinic waiting areas.",
        category="amenities",
        authority="owner_verified",
        status="active",
    )
    sms_entry = SmsKnowledgeEntry(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        category="tone",
        text="Keep responses friendly and casual.",
        status="approved",
        provenance="manual",
    )
    db_session.add_all([memory, sms_entry])
    db_session.commit()

    initial_proj_count = db_session.query(KnowledgeGraphProjection).count()
    initial_mem_count = db_session.query(CuratedMemory).count()

    service = KnowledgeRebuildService()
    result = service.rebuild_graph(
        db=db_session, tenant_id=tenant_1.id, dry_run=True, verify=True
    )

    assert result["dry_run"] is True
    assert result["total_scanned"] == 2
    assert result["total_eligible"] == 2
    assert result["total_projected"] == 2
    assert result["total_skipped"] == 0
    assert result["total_rejected"] == 0

    # Assert zero DB mutation
    assert db_session.query(KnowledgeGraphProjection).count() == initial_proj_count
    assert db_session.query(CuratedMemory).count() == initial_mem_count


def test_6_scoped_rebuild_tenant_and_provider_scoping(p5_p6_setup, db_session):
    """Test 6: Scoped rebuild (tenant-only and provider-only scoping) (Spec 34, 56)."""
    tenant_1 = p5_p6_setup["tenant_1"]
    tenant_2 = p5_p6_setup["tenant_2"]
    prov_1a = p5_p6_setup["prov_1a"]
    prov_1b = p5_p6_setup["prov_1b"]
    prov_2 = p5_p6_setup["prov_2"]

    # Tenant 1 - Provider 1a
    mem_1a = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        knowledge_kind="durable_fact",
        user_query="Dr. Taylor questions?",
        ideal_response="Dr. Taylor specializes in holistic family medicine.",
        category="practitioner",
        authority="owner_verified",
        status="active",
    )
    # Tenant 1 - Provider 1b
    mem_1b = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1b.id,
        knowledge_kind="durable_fact",
        user_query="Dr. Jordan questions?",
        ideal_response="Dr. Jordan specializes in sports acupuncture.",
        category="practitioner",
        authority="owner_verified",
        status="active",
    )
    # Tenant 2 - Provider 2
    mem_2 = CuratedMemory(
        tenant_id=tenant_2.id,
        provider_id=prov_2.id,
        knowledge_kind="durable_fact",
        user_query="Tenant 2 policy?",
        ideal_response="Tenant 2 general policy details.",
        category="policy",
        authority="owner_verified",
        status="active",
    )

    db_session.add_all([mem_1a, mem_1b, mem_2])
    db_session.commit()

    service = KnowledgeRebuildService()

    # 1. Provider-scoped rebuild: Tenant 1, Provider 1a only
    scope_1a_res = service.rebuild_graph(
        db=db_session, tenant_id=tenant_1.id, provider_id=prov_1a.id, dry_run=False
    )
    assert scope_1a_res["total_projected"] == 1

    projections_1a = (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.curated_memory_id == mem_1a.id)
        .all()
    )
    assert len(projections_1a) == 1

    # Ensure neither 1b nor 2 got projected
    assert (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.curated_memory_id.in_([mem_1b.id, mem_2.id]))
        .count()
        == 0
    )

    # 2. Tenant-scoped rebuild: Tenant 1 (all providers in tenant 1)
    scope_t1_res = service.rebuild_graph(
        db=db_session, tenant_id=tenant_1.id, dry_run=False
    )
    assert scope_t1_res["total_projected"] == 1  # Only 1b is newly projected (1a is skipped)
    assert scope_t1_res["total_skipped"] == 1

    # Ensure Tenant 2 remains untouched
    assert (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.tenant_id == tenant_2.id)
        .count()
        == 0
    )


def test_7_cli_invocation_dry_run(p5_p6_setup, db_session, capsys):
    """Test 7: CLI invocation of python -m app.tools.rebuild_knowledge_graph --dry-run (Spec 56)."""
    tenant_1 = p5_p6_setup["tenant_1"]
    prov_1a = p5_p6_setup["prov_1a"]

    mem = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1a.id,
        knowledge_kind="durable_fact",
        user_query="CLI test query?",
        ideal_response="CLI test answer.",
        category="general",
        authority="owner_verified",
        status="active",
    )
    db_session.add(mem)
    db_session.commit()

    # Test programmatic CLI entrypoint
    exit_code = cli_main(["--tenant-id", str(tenant_1.id), "--dry-run", "--verify"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "KNOWLEDGE GRAPH REBUILD SUMMARY" in captured.out
    assert "Dry Run:           True" in captured.out
    assert f"Tenant Scope:      {tenant_1.id}" in captured.out
    assert "Total Scanned:" in captured.out
    assert "Total Projected:" in captured.out
    assert "Parity Verification" in captured.out

    # Security check: Zero credential or database URL output
    assert "bolt://" not in captured.out
    assert "postgresql://" not in captured.out
    assert "password" not in captured.out.lower()


def test_8_phase5_shadow_write_active_curator(p5_p6_setup, db_session):
    """Test 8: Spec 61 shadow writing active during autonomous curation."""
    tenant_1 = p5_p6_setup["tenant_1"]
    prov_1a = p5_p6_setup["prov_1a"]

    # When GRAPH_SHADOW_WRITE is True (Spec 61 default)
    with patch.object(settings, "GRAPH_SHADOW_WRITE", True), patch.object(
        settings, "GRAPH_KNOWLEDGE_ENABLED", False
    ):
        event_1 = LearningEvent(
            tenant_id=tenant_1.id,
            provider_id=prov_1a.id,
            event_type="explicit_knowledge",
            source="production_draft",
            customer_message="What is the check-in procedure?",
            human_content="Please arrive 10 minutes early to complete initial health forms.",
            metadata_payload={"category": "checkin", "source": "test"},
            status="pending",
        )
        db_session.add(event_1)
        db_session.commit()

        decision = unified_curator.process_learning_event(db_session, event_1)
        assert decision.status == "processed"
        assert decision.projection_id is not None

        proj = db_session.query(KnowledgeGraphProjection).filter_by(id=decision.projection_id).first()
        assert proj is not None
        assert proj.curated_memory_id == decision.memory_id
        assert proj.status == "pending"

    # When GRAPH_SHADOW_WRITE and GRAPH_KNOWLEDGE_ENABLED are both False: projection is skipped
    with patch.object(settings, "GRAPH_SHADOW_WRITE", False), patch.object(
        settings, "GRAPH_KNOWLEDGE_ENABLED", False
    ):
        event_2 = LearningEvent(
            tenant_id=tenant_1.id,
            provider_id=prov_1a.id,
            event_type="explicit_knowledge",
            source="production_draft",
            customer_message="Where can I get tea?",
            human_content="Complimentary herbal tea is available in the waiting room.",
            metadata_payload={"category": "amenities", "source": "test"},
            status="pending",
        )
        db_session.add(event_2)
        db_session.commit()

        decision2 = unified_curator.process_learning_event(db_session, event_2)
        assert decision2.status == "processed"
        assert decision2.projection_id is None
