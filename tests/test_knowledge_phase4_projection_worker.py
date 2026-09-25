"""Phase 4 tests for Graphiti canonical graph projection service, episode builder, and projection worker.

Spec references:
- Sections 28–36: Canonical graph projection ledger, Graphiti episode builder with ontology and provenance
- Sections 67–69: Graphiti projection worker, leasing, exponential backoff (Spec 68), and dead_letter transitions (Spec 69)
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import MagicMock, patch
import pytest

from app.models.curated_memory import CuratedMemory
from app.models.knowledge_projection import KnowledgeGraphProjection
from app.models.learning_event import LearningEvent
from app.models.provider import Provider
from app.models.tenant import Tenant
from app.services.knowledge.graphiti_client import format_group_id
from app.services.knowledge.projection_service import (
    EdgeType,
    EntityConcept,
    ONTOLOGY_EDGE_TYPES,
    ONTOLOGY_ENTITY_CONCEPTS,
    ProjectionService,
    projection_service,
)
from app.services.knowledge.projection_worker import (
    ProjectionWorker,
    process_pending_projections_worker,
    start_projection_worker_loop,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def mock_graphiti_offline(monkeypatch):
    """Ensure Phase 4 unit tests run without live Graphiti/OpenAI dispatch."""
    import app.services.knowledge.graphiti_client as gc
    monkeypatch.setattr(gc, "ping_neo4j", lambda: False)
    monkeypatch.setattr(gc, "_graphiti_instance", None)


@pytest.fixture
def p4_setup(db_session):
    """Setup multi-tenant fixtures for Phase 4 projection tests."""
    tenant_1 = Tenant(name="Acme Health", subdomain="acme-phase4-test")
    tenant_2 = Tenant(name="Zen Wellness", subdomain="zen-phase4-test")
    db_session.add_all([tenant_1, tenant_2])
    db_session.commit()

    prov_1 = Provider(tenant_id=tenant_1.id, name="Tori", active=True)
    prov_2 = Provider(tenant_id=tenant_2.id, name="Marcus", active=True)
    db_session.add_all([prov_1, prov_2])
    db_session.commit()

    return {
        "tenant_1": tenant_1,
        "tenant_2": tenant_2,
        "prov_1": prov_1,
        "prov_2": prov_2,
    }


def test_1_worker_claims_and_projects_pending_projections(p4_setup, db_session):
    """Test 1: Worker claims and projects pending KnowledgeGraphProjection records to Graphiti."""
    tenant_1 = p4_setup["tenant_1"]
    prov_1 = p4_setup["prov_1"]

    memory = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1.id,
        knowledge_kind="durable_fact",
        user_query="Where can I park when visiting?",
        ideal_response="Free two-hour street parking is available directly in front of the clinic.",
        category="parking situation",
        authority="curator:2.0",
        status="active",
    )
    db_session.add(memory)
    db_session.commit()

    projection = KnowledgeGraphProjection(
        tenant_id=tenant_1.id,
        provider_id=prov_1.id,
        curated_memory_id=memory.id,
        projection_type="fact",
        graph_group_id=format_group_id(tenant_1.id, prov_1.id),
        status="pending",
        projection_version="2.0",
    )
    db_session.add(projection)
    db_session.commit()

    worker = ProjectionWorker(worker_id="test-proj-worker-1", batch_size=10, max_retries=5)
    summary = worker.process_batch(db=db_session)

    assert summary["claimed"] == 1
    assert summary["projected"] == 1
    assert summary["retried"] == 0
    assert summary["dead_letter"] == 0

    # Reload projection from DB
    db_session.refresh(projection)
    assert projection.status == "projected"
    assert projection.projected_at is not None
    assert projection.graph_episode_uuid is not None
    assert projection.lease_owner is None
    assert projection.lease_expires_at is None
    assert projection.attempt_count == 0


def test_2_provenance_metadata_and_group_id_formatting(p4_setup, db_session):
    """Test 2: Provenance metadata and graph group ID formatting strictly adhere to Specs 33 & 34."""
    tenant_1 = p4_setup["tenant_1"]
    prov_1 = p4_setup["prov_1"]

    event = LearningEvent(
        tenant_id=tenant_1.id,
        provider_id=prov_1.id,
        event_type="explicit_knowledge_answer",
        source="bootcamp",
        customer_message="What are your cancellation policies?",
        human_content="We require 24 hours notice for cancellations.",
        status="processed",
    )
    db_session.add(event)
    db_session.commit()

    memory = CuratedMemory(
        tenant_id=tenant_1.id,
        provider_id=prov_1.id,
        knowledge_kind="durable_fact",
        user_query="What are your cancellation policies?",
        ideal_response="We require 24 hours notice for cancellations.",
        category="cancellation",
        authority="curator:2.0",
        status="active",
    )
    db_session.add(memory)
    db_session.commit()

    projection = KnowledgeGraphProjection(
        tenant_id=tenant_1.id,
        provider_id=prov_1.id,
        learning_event_id=event.id,
        curated_memory_id=memory.id,
        projection_type="fact",
        graph_group_id=format_group_id(tenant_1.id, prov_1.id),
        status="pending",
    )
    db_session.add(projection)
    db_session.commit()

    # Spec 33: Provenance string verification
    source_desc = projection_service.build_source_description(projection, memory, event)
    prov_data = json.loads(source_desc)

    assert prov_data["tenant_id"] == tenant_1.id
    assert prov_data["provider_id"] == prov_1.id
    assert prov_data["learning_event_id"] == event.id
    assert prov_data["curated_memory_id"] == memory.id
    assert prov_data["authority"] == "curator:2.0"
    assert prov_data["source"] == "bootcamp"
    assert "created_at" in prov_data

    # Spec 34: Group ID formatting verification
    assert format_group_id(tenant_1.id, prov_1.id) == f"tenant:{tenant_1.id}:provider:{prov_1.id}"
    assert format_group_id(tenant_1.id, None) == f"tenant:{tenant_1.id}:shared"

    # Human-readable episode name verification
    episode_name = projection_service.build_episode_name(projection, memory, event)
    assert f"provider:{prov_1.name}" in episode_name
    assert "cancellation" in episode_name
    assert "[Fact]" in episode_name


def test_3_idempotency_deterministic_episode_uuid(p4_setup, db_session):
    """Test 3: Idempotency (re-processing the same projection produces same episode ID without duplicate nodes)."""
    tenant_1 = p4_setup["tenant_1"]
    prov_1 = p4_setup["prov_1"]

    projection = KnowledgeGraphProjection(
        tenant_id=tenant_1.id,
        provider_id=prov_1.id,
        curated_memory_id=101,
        learning_event_id="evt-abc-123",
        projection_type="fact",
        graph_group_id=format_group_id(tenant_1.id, prov_1.id),
        status="pending",
    )
    db_session.add(projection)
    db_session.commit()

    # Spec 32: Deterministic UUID computation
    uuid_1 = projection_service.compute_episode_uuid(projection)
    uuid_2 = projection_service.compute_episode_uuid(projection)
    assert uuid_1 == uuid_2
    assert len(uuid_1) == 36

    # Test that re-projecting returns the identical episode ID
    ep_1 = projection_service.project_to_graphiti(projection)
    ep_2 = projection_service.project_to_graphiti(projection)
    assert ep_1 == ep_2
    assert ep_1 == uuid_1


def test_4_concurrency_and_stale_lease_recovery(p4_setup, db_session):
    """Test 4: Concurrency and stale lease recovery (stale processing projection claimed after lease expiry)."""
    tenant_1 = p4_setup["tenant_1"]
    prov_1 = p4_setup["prov_1"]

    now = utc_now()
    stale_projection = KnowledgeGraphProjection(
        tenant_id=tenant_1.id,
        provider_id=prov_1.id,
        curated_memory_id=202,
        projection_type="fact",
        graph_group_id=format_group_id(tenant_1.id, prov_1.id),
        status="processing",
        lease_owner="crashed-worker-uuid",
        lease_expires_at=now - timedelta(minutes=5),
    )
    db_session.add(stale_projection)
    db_session.commit()

    summary = process_pending_projections_worker(
        db=db_session,
        batch_size=10,
        worker_id="active-worker-uuid",
    )

    assert summary["claimed"] == 1
    assert summary["projected"] == 1
    assert summary["retried"] == 0
    assert summary["dead_letter"] == 0

    db_session.refresh(stale_projection)
    assert stale_projection.status == "projected"
    assert stale_projection.projected_at is not None
    assert stale_projection.lease_owner is None
    assert stale_projection.lease_expires_at is None


def test_5_failure_retry_with_exponential_backoff(p4_setup, db_session, monkeypatch):
    """Test 5: Graphiti/Neo4j failure handling: enters retry with exponential backoff on transient errors."""
    tenant_1 = p4_setup["tenant_1"]

    projection = KnowledgeGraphProjection(
        tenant_id=tenant_1.id,
        curated_memory_id=303,
        projection_type="fact",
        graph_group_id=format_group_id(tenant_1.id, None),
        status="pending",
    )
    db_session.add(projection)
    db_session.commit()

    # Simulate transient Graphiti / Neo4j failure
    def mock_failing_project(*args, **kwargs):
        raise RuntimeError("Neo4j transient connection timeout")

    monkeypatch.setattr(projection_service, "project_to_graphiti", mock_failing_project)

    before_run = utc_now()
    summary = process_pending_projections_worker(
        db=db_session,
        batch_size=10,
        max_retries=5,
    )

    assert summary["claimed"] == 1
    assert summary["projected"] == 0
    assert summary["retried"] == 1
    assert summary["dead_letter"] == 0

    db_session.refresh(projection)
    assert projection.status == "retry"
    assert projection.attempt_count == 1
    assert "Neo4j transient connection timeout" in (projection.last_error or "")
    assert projection.lease_owner is None
    assert projection.lease_expires_at is None

    # Spec 68: Exponential backoff for attempt 1: 10 * (2 ** 1) = 20s
    assert projection.next_attempt_at is not None
    next_attempt = projection.next_attempt_at
    if next_attempt.tzinfo is None:
        next_attempt = next_attempt.replace(tzinfo=timezone.utc)
    assert next_attempt >= before_run + timedelta(seconds=19)


def test_6_max_retry_exhaustion_transitions_to_dead_letter(p4_setup, db_session, monkeypatch):
    """Test 6: Max retry exhaustion transitions projection to dead_letter."""
    tenant_1 = p4_setup["tenant_1"]
    now = utc_now()

    # Projection already attempted 4 times; next retry is ready now
    projection = KnowledgeGraphProjection(
        tenant_id=tenant_1.id,
        curated_memory_id=404,
        projection_type="fact",
        graph_group_id=format_group_id(tenant_1.id, None),
        status="retry",
        attempt_count=4,
        next_attempt_at=now - timedelta(seconds=5),
    )
    db_session.add(projection)
    db_session.commit()

    # 5th consecutive failure
    def mock_failing_project(*args, **kwargs):
        raise ConnectionError("Persistent network route unreachable")

    monkeypatch.setattr(projection_service, "project_to_graphiti", mock_failing_project)

    summary = process_pending_projections_worker(
        db=db_session,
        batch_size=10,
        max_retries=5,
    )

    assert summary["claimed"] == 1
    assert summary["projected"] == 0
    assert summary["retried"] == 0
    assert summary["dead_letter"] == 1

    db_session.refresh(projection)
    assert projection.status == "dead_letter"
    assert projection.attempt_count == 5
    assert "Persistent network route unreachable" in (projection.last_error or "")
    assert projection.next_attempt_at is None
    assert projection.lease_owner is None
    assert projection.lease_expires_at is None


def test_7_multi_tenant_and_provider_isolation(p4_setup, db_session):
    """Test 7: Multi-tenant and provider isolation (projections partitioned into distinct groups)."""
    tenant_1 = p4_setup["tenant_1"]
    prov_1 = p4_setup["prov_1"]
    tenant_2 = p4_setup["tenant_2"]
    prov_2 = p4_setup["prov_2"]

    # Projection for Tenant 1 / Provider 1
    proj_1 = KnowledgeGraphProjection(
        tenant_id=tenant_1.id,
        provider_id=prov_1.id,
        curated_memory_id=501,
        projection_type="fact",
        graph_group_id=format_group_id(tenant_1.id, prov_1.id),
        status="pending",
    )

    # Projection for Tenant 2 / Provider 2
    proj_2 = KnowledgeGraphProjection(
        tenant_id=tenant_2.id,
        provider_id=prov_2.id,
        curated_memory_id=502,
        projection_type="behavioural_rule",
        graph_group_id=format_group_id(tenant_2.id, prov_2.id),
        status="pending",
    )
    db_session.add_all([proj_1, proj_2])
    db_session.commit()

    summary = process_pending_projections_worker(db=db_session, batch_size=10)
    assert summary["claimed"] == 2
    assert summary["projected"] == 2

    db_session.refresh(proj_1)
    db_session.refresh(proj_2)

    assert proj_1.graph_group_id == f"tenant:{tenant_1.id}:provider:{prov_1.id}"
    assert proj_2.graph_group_id == f"tenant:{tenant_2.id}:provider:{prov_2.id}"
    assert proj_1.graph_episode_uuid != proj_2.graph_episode_uuid

    # Defense-in-depth: Mismatched tenant memory must be rejected
    mismatched_memory = CuratedMemory(
        tenant_id=tenant_2.id,  # Belongs to tenant 2
        provider_id=prov_2.id,
        knowledge_kind="durable_fact",
        user_query="What is your privacy policy?",
        ideal_response="Tenant 2 private data",
        category="security",
        status="active",
    )
    db_session.add(mismatched_memory)
    db_session.commit()

    with pytest.raises(ValueError, match="Tenant.*mismatch|Tenant boundary violation"):
        projection_service.project_to_graphiti(
            projection=proj_1,  # Belongs to tenant 1
            memory=mismatched_memory,
        )


@pytest.mark.asyncio
async def test_8_worker_loop_startup_and_clean_shutdown():
    """Test 8: Worker runner clean startup and shutdown via stop event."""
    stop_event = asyncio.Event()
    worker = ProjectionWorker(batch_size=5, max_retries=3)

    task = asyncio.create_task(
        start_projection_worker_loop(
            interval_seconds=0.1,
            stop_event=stop_event,
            worker=worker,
        )
    )

    # Let the loop run briefly
    await asyncio.sleep(0.2)
    assert not task.done()

    # Trigger clean shutdown
    stop_event.set()
    await asyncio.wait_for(task, timeout=2.0)
    assert task.done()


def test_ontological_concepts_and_edge_types():
    """Test ontological concepts and edge types defined in Spec 36."""
    expected_entities = [
        "Provider",
        "Tenant",
        "Preference",
        "Behaviour",
        "Policy",
        "Boundary",
        "Example",
    ]
    for ent in expected_entities:
        assert ent in ONTOLOGY_ENTITY_CONCEPTS
        assert hasattr(EntityConcept, ent.upper())

    expected_edges = [
        "PREFERS",
        "AVOIDS",
        "APPLIES_WHEN",
        "HAS_BOUNDARY",
        "SUPERSEDES",
        "SUPPORTED_BY",
    ]
    for edge in expected_edges:
        assert edge in ONTOLOGY_EDGE_TYPES
        assert hasattr(EdgeType, edge)
