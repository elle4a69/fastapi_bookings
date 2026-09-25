"""Phase 3 tests for Curator background worker, leasing, retries, and multi-tenant isolation.

Spec references:
- Sections 30, 31: Automatic background worker infrastructure
- Sections 70, 71, 72, 73: Worker leasing, exponential backoff, retry exhaustion, multi-tenant isolation
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch
import pytest

from app.models.curated_memory import CuratedMemory
from app.models.knowledge_projection import KnowledgeGraphProjection
from app.models.learning_event import LearningEvent
from app.models.provider import Provider
from app.models.tenant import Tenant
from app.services.knowledge.curator_worker import (
    CuratorWorker,
    process_pending_learning_events_worker,
    start_curator_worker_loop,
    utc_now,
)
from app.services.knowledge.curator import unified_curator


@pytest.fixture
def p3_setup(db_session):
    """Setup multi-tenant fixtures for Phase 3 worker tests."""
    tenant_1 = Tenant(name="Alpha Clinic", subdomain="alpha-worker-test")
    tenant_2 = Tenant(name="Beta Health", subdomain="beta-worker-test")
    db_session.add_all([tenant_1, tenant_2])
    db_session.commit()

    prov_1 = Provider(tenant_id=tenant_1.id, name="Dr. Alpha", active=True)
    prov_2 = Provider(tenant_id=tenant_2.id, name="Dr. Beta", active=True)
    db_session.add_all([prov_1, prov_2])
    db_session.commit()

    return {
        "tenant_1": tenant_1,
        "tenant_2": tenant_2,
        "prov_1": prov_1,
        "prov_2": prov_2,
    }


def test_worker_claims_and_processes_pending_events_automatically(p3_setup, db_session):
    """Test 1: Worker claims and processes pending learning events automatically."""
    tenant_1 = p3_setup["tenant_1"]
    prov_1 = p3_setup["prov_1"]

    event = LearningEvent(
        tenant_id=tenant_1.id,
        provider_id=prov_1.id,
        event_type="explicit_knowledge_answer",
        source="production_messages",
        customer_message="What is your street address?",
        human_content="We are located at 456 Elm Street, Suite 200.",
        status="pending",
        metadata_payload={"category": "location"},
    )
    db_session.add(event)
    db_session.commit()

    worker = CuratorWorker(worker_id="test-worker-1", batch_size=10, max_retries=5)
    summary = worker.process_batch(db=db_session)

    assert summary["claimed"] == 1
    assert summary["processed"] == 1
    assert summary["failed"] == 0
    assert summary["retried"] == 0

    # Reload event
    db_session.refresh(event)
    assert event.status == "processed"
    assert event.processed_at is not None
    assert event.lease_owner is None
    assert event.lease_expires_at is None
    assert event.attempt_count == 0

    # Verify curated memory created
    mem = (
        db_session.query(CuratedMemory)
        .filter(CuratedMemory.tenant_id == tenant_1.id, CuratedMemory.status == "active")
        .first()
    )
    assert mem is not None
    assert "[ADDRESS]" in mem.ideal_response

    # Verify projection ledger enqueued
    proj = (
        db_session.query(KnowledgeGraphProjection)
        .filter(KnowledgeGraphProjection.learning_event_id == event.id)
        .first()
    )
    assert proj is not None
    assert proj.status == "pending"
    assert proj.curated_memory_id == mem.id


def test_concurrency_and_stale_lease_recovery(p3_setup, db_session):
    """Test 2: Concurrency & lease expiry (stale processing event is re-claimed after lease expiry)."""
    tenant_1 = p3_setup["tenant_1"]
    prov_1 = p3_setup["prov_1"]

    now = utc_now()
    # Event leased by an old worker whose lease has expired
    stale_event = LearningEvent(
        tenant_id=tenant_1.id,
        provider_id=prov_1.id,
        event_type="explicit_knowledge_answer",
        source="production_messages",
        customer_message="Do you accept walk-ins?",
        human_content="Walk-ins are accepted between 9am and 11am daily.",
        status="processing",
        lease_owner="crashed-worker-999",
        lease_expires_at=now - timedelta(minutes=5),
        metadata_payload={"category": "hours"},
    )
    db_session.add(stale_event)
    db_session.commit()

    summary = process_pending_learning_events_worker(
        db=db_session,
        batch_size=10,
        worker_id="active-worker-2",
    )

    assert summary["claimed"] == 1
    assert summary["processed"] == 1

    db_session.refresh(stale_event)
    assert stale_event.status == "processed"
    assert stale_event.processed_at is not None
    assert stale_event.lease_owner is None
    assert stale_event.lease_expires_at is None


def test_failure_retry_with_exponential_backoff(p3_setup, db_session, monkeypatch):
    """Test 3: Failure retry with exponential backoff (next_attempt_at and attempt_count)."""
    tenant_1 = p3_setup["tenant_1"]

    event = LearningEvent(
        tenant_id=tenant_1.id,
        event_type="explicit_knowledge_answer",
        source="production_messages",
        customer_message="What is the refund policy?",
        human_content="Full refunds are available within 30 days.",
        status="pending",
        metadata_payload={"category": "refunds"},
    )
    db_session.add(event)
    db_session.commit()

    # Simulate temporary failure during curation
    def mock_failing_process(*args, **kwargs):
        raise RuntimeError("Temporary graph service timeout")

    monkeypatch.setattr(unified_curator, "process_learning_event", mock_failing_process)

    before_run = utc_now()
    summary = process_pending_learning_events_worker(db=db_session, batch_size=10, max_retries=5)

    assert summary["claimed"] == 1
    assert summary["processed"] == 0
    assert summary["retried"] == 1
    assert summary["failed"] == 0

    db_session.refresh(event)
    assert event.status == "retry"
    assert event.attempt_count == 1
    assert "Temporary graph service timeout" in (event.last_error or "")
    assert event.lease_owner is None
    assert event.lease_expires_at is None
    # Exponential backoff for attempt 1: 10 * (2 ** 1) = 20 seconds
    assert event.next_attempt_at is not None
    next_attempt = event.next_attempt_at
    if next_attempt.tzinfo is None:
        next_attempt = next_attempt.replace(tzinfo=timezone.utc)
    assert next_attempt >= before_run + timedelta(seconds=19)


def test_max_retry_exhaustion_marks_failed(p3_setup, db_session, monkeypatch):
    """Test 4: Max retry exhaustion marks event failed."""
    tenant_1 = p3_setup["tenant_1"]
    now = utc_now()

    # Event already attempted 4 times, next attempt is ready
    event = LearningEvent(
        tenant_id=tenant_1.id,
        event_type="explicit_knowledge_answer",
        source="production_messages",
        customer_message="What are your weekend hours?",
        human_content="We are open Saturdays 9am-1pm.",
        status="retry",
        attempt_count=4,
        next_attempt_at=now - timedelta(seconds=10),
        metadata_payload={"category": "hours"},
    )
    db_session.add(event)
    db_session.commit()

    # Simulate 5th consecutive failure
    def mock_failing_process(*args, **kwargs):
        raise ConnectionError("Persistent network outage")

    monkeypatch.setattr(unified_curator, "process_learning_event", mock_failing_process)

    summary = process_pending_learning_events_worker(
        db=db_session,
        batch_size=10,
        max_retries=5,
    )

    assert summary["claimed"] == 1
    assert summary["processed"] == 0
    assert summary["failed"] == 1
    assert summary["retried"] == 0

    db_session.refresh(event)
    assert event.status == "failed"
    assert event.attempt_count == 5
    assert "Persistent network outage" in (event.last_error or "")
    assert event.lease_owner is None
    assert event.lease_expires_at is None
    assert event.next_attempt_at is None


def test_multi_tenant_safety_and_defense_in_depth(p3_setup, db_session):
    """Test 5: Multi-tenant safety and defense-in-depth isolation."""
    tenant_1 = p3_setup["tenant_1"]
    prov_1 = p3_setup["prov_1"]
    tenant_2 = p3_setup["tenant_2"]
    prov_2 = p3_setup["prov_2"]

    # Event for Tenant 1
    event_t1 = LearningEvent(
        tenant_id=tenant_1.id,
        provider_id=prov_1.id,
        event_type="explicit_knowledge_answer",
        source="production_messages",
        customer_message="Do you provide acupuncture?",
        human_content="Yes, Dr. Alpha provides clinical acupuncture.",
        status="pending",
        metadata_payload={"category": "services"},
    )

    # Event for Tenant 2
    event_t2 = LearningEvent(
        tenant_id=tenant_2.id,
        provider_id=prov_2.id,
        event_type="explicit_knowledge_answer",
        source="production_messages",
        customer_message="Do you offer telehealth?",
        human_content="Yes, Dr. Beta provides telehealth consultations.",
        status="pending",
        metadata_payload={"category": "telehealth"},
    )

    db_session.add_all([event_t1, event_t2])
    db_session.commit()

    # Test direct tenant mismatch defense-in-depth on unified_curator
    with pytest.raises(ValueError, match="Tenant mismatch"):
        unified_curator.process_learning_event(
            db_session, event_t1, expected_tenant_id=tenant_2.id
        )

    # Worker processing processes each event in its own tenant context
    summary = process_pending_learning_events_worker(db=db_session, batch_size=20)
    assert summary["claimed"] == 2
    assert summary["processed"] == 2
    assert summary["failed"] == 0

    # Ensure curated memories are strictly partitioned
    mem_t1 = (
        db_session.query(CuratedMemory)
        .filter(CuratedMemory.tenant_id == tenant_1.id, CuratedMemory.status == "active")
        .all()
    )
    mem_t2 = (
        db_session.query(CuratedMemory)
        .filter(CuratedMemory.tenant_id == tenant_2.id, CuratedMemory.status == "active")
        .all()
    )

    assert len(mem_t1) == 1
    assert "acupuncture" in mem_t1[0].ideal_response
    assert mem_t1[0].provider_id == prov_1.id

    assert len(mem_t2) == 1
    assert "telehealth" in mem_t2[0].ideal_response
    assert mem_t2[0].provider_id == prov_2.id


@pytest.mark.asyncio
async def test_worker_loop_startup_and_clean_shutdown():
    """Test 6: Worker loop startup and clean shutdown via stop_event."""
    stop_event = asyncio.Event()

    call_count = 0

    class MockWorker:
        worker_id = "mock-loop-worker"

        def process_batch(self, db=None):
            nonlocal call_count
            call_count += 1
            return {"claimed": 0, "processed": 0, "failed": 0, "retried": 0}

    worker = MockWorker()

    # Start loop in background task
    task = asyncio.create_task(
        start_curator_worker_loop(
            interval_seconds=0.05,
            stop_event=stop_event,
            worker=worker,
        )
    )

    # Let the loop execute at least one iteration
    await asyncio.sleep(0.12)

    # Signal stop
    stop_event.set()

    # Await clean shutdown without timeout
    await asyncio.wait_for(task, timeout=1.0)

    assert task.done()
    assert not task.cancelled()
    assert call_count >= 1
