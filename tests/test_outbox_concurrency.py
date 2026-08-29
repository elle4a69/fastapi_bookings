"""Comprehensive test suite for Outbox Delivery & Concurrency remediation (Work Package D).

Validates:
- DEL-001: Atomic concurrency-safe claiming (20 concurrent workers on 1 event -> exactly 1 winner)
- DEL-001: Expired lease recovery (crashed worker lease expires, second worker re-claims)
- DEL-002: Worker lifecycle decoupling and graceful lease release on shutdown
- DEL-003: Exponential backoff with jitter and dead-lettering after max attempts
- DEL-003: Unknown event type and missing tenant quarantining
- SEC-005: Privacy-safe structured error codes and PII/secret redaction in failure records
- Multi-tenant isolation: Poison job for Tenant A does not block Tenant B events
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

import pytest
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.tenant import Tenant
from app.models.user import User
from app.models.webhook import WebhookRegistration, WebhookDelivery
from app.models.outbox import OutboxEvent
from app.services.outbox_worker import (
    claim_outbox_events,
    process_pending_outbox_events,
    release_active_leases,
    compute_next_retry,
    categorize_error,
    sanitize_message,
)
from app.core.security import get_password_hash


@pytest.fixture
def outbox_test_tenants(db_session):
    """Seed two isolated tenants for multi-tenant outbox tests."""
    tenant_a = Tenant(name="Outbox Tenant Alpha", subdomain="outbox-alpha", created_at=datetime.now(timezone.utc))
    tenant_b = Tenant(name="Outbox Tenant Beta", subdomain="outbox-beta", created_at=datetime.now(timezone.utc))
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()
    db_session.refresh(tenant_a)
    db_session.refresh(tenant_b)

    return {"tenant_a": tenant_a, "tenant_b": tenant_b}


# ============================================================================
# DEL-001: 20 Concurrent Workers Claiming a Single Event
# ============================================================================

def to_utc(dt: datetime) -> datetime:
    """Normalize datetime to UTC aware datetime."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def test_twenty_concurrent_workers_claim_single_event_exactly_one_wins():
    """Verify 20 concurrent threads/workers attempting to claim a single event result in exactly 1 winner.
    
    Uses a temporary SQLite database with WAL mode to ensure multi-threaded concurrency safety.
    """
    import tempfile
    import os

    fd, db_path = tempfile.mkstemp(suffix="_concurrency.db")
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30.0},
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.exec_driver_sql("PRAGMA busy_timeout=30000")

    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed 1 single pending event
    init_db = TestSession()
    event = OutboxEvent(
        tenant_id=1,
        type="booking.created",
        payload=json.dumps({"booking_id": 999, "action": "send_notification"}),
        status="PENDING",
    )
    init_db.add(event)
    init_db.commit()
    event_id = event.id
    init_db.close()

    num_workers = 20
    claimed_results = []

    def worker_claim_attempt(worker_idx: int):
        worker_id = f"worker-{worker_idx}"
        db = TestSession()
        try:
            claimed = claim_outbox_events(
                db=db,
                worker_id=worker_id,
                batch_size=10,
                lease_seconds=60,
                max_retries=5,
            )
            return worker_id, len(claimed), [e.id for e in claimed]
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_claim_attempt, i) for i in range(num_workers)]
        for f in futures:
            claimed_results.append(f.result())

    # Exactly 1 worker must have claimed the event
    total_claims = sum(count for _, count, _ in claimed_results)
    winning_workers = [w_id for w_id, count, _ in claimed_results if count > 0]

    assert total_claims == 1, f"Expected exactly 1 claim across 20 workers, got {total_claims}: {claimed_results}"
    assert len(winning_workers) == 1

    # Verify DB state: event is in PROCESSING status leased to the winner
    verify_db = TestSession()
    saved_event = verify_db.query(OutboxEvent).filter_by(id=event_id).first()
    assert saved_event.status == "PROCESSING"
    assert saved_event.leased_by == winning_workers[0]
    assert saved_event.lease_expires_at is not None
    assert to_utc(saved_event.lease_expires_at) > datetime.now(timezone.utc)
    verify_db.close()

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    try:
        os.remove(db_path)
    except Exception:
        pass


# ============================================================================
# DEL-001: Expired Lease Recovery
# ============================================================================

@pytest.mark.asyncio
async def test_expired_lease_recovery_by_second_worker(db_session):
    """Verify that if a worker crashes and leaves an expired lease, a second worker successfully re-claims it."""
    # Seed an event that is currently in PROCESSING with an expired lease
    now = datetime.now(timezone.utc)
    stale_expiry = now - timedelta(minutes=10)

    stale_event = OutboxEvent(
        tenant_id=1,
        type="SEND_SMS",
        payload=json.dumps({"to": "+15550001111", "body": "Hello Stale Lease"}),
        status="PROCESSING",
        leased_by="crashed-worker-dead-pid",
        lease_expires_at=stale_expiry,
        attempt_count=0,
    )
    db_session.add(stale_event)
    db_session.commit()
    db_session.refresh(stale_event)

    # Worker 2 processes pending outbox events
    with patch("app.services.clicksend.clicksend_client.send_sms") as mock_send_sms:
        mock_send_sms.return_value = {"status": "success"}
        processed_count = await process_pending_outbox_events(
            db=db_session,
            worker_id="recovery-worker-2",
        )

    assert processed_count == 1
    db_session.refresh(stale_event)
    assert stale_event.status == "PROCESSED"
    assert stale_event.processed is True
    assert stale_event.leased_by is None
    assert stale_event.lease_expires_at is None
    mock_send_sms.assert_called_once()


# ============================================================================
# DEL-003: Exponential Backoff, Retry Timing, and Dead-Lettering
# ============================================================================

@pytest.mark.asyncio
async def test_backoff_retry_timing_and_dead_lettering(db_session, outbox_test_tenants):
    """Verify deterministic exponential backoff under a fake clock and dead-lettering after max retries."""
    tenant_a = outbox_test_tenants["tenant_a"]

    # Webhook registration that will fail with 500
    hook = WebhookRegistration(
        tenant_id=tenant_a.id,
        event="booking.created",
        target_url="https://example.com/fail-hook",
        is_active=True,
    )
    event = OutboxEvent(
        tenant_id=tenant_a.id,
        type="booking.created",
        payload=json.dumps({"booking_id": 404}),
        status="PENDING",
    )
    db_session.add_all([hook, event])
    db_session.commit()
    db_session.refresh(event)

    t0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)

    # Mock failing HTTP request
    async def mock_post_fail(*args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        http_err = httpx.HTTPStatusError("500 Internal Server Error", request=MagicMock(), response=mock_resp)
        mock_resp.raise_for_status = MagicMock(side_effect=http_err)
        raise http_err

    with patch("httpx.AsyncClient.post", new=mock_post_fail), \
         patch("app.core.network_safety.validate_url_safety", return_value=(True, None)):

        # --- Attempt 1 at t0 ---
        await process_pending_outbox_events(db=db_session, now=t0, max_retries=5)
        db_session.refresh(event)
        assert event.attempt_count == 1
        assert event.status == "FAILED"
        assert event.next_attempt_at is not None
        next_attempt_1 = to_utc(event.next_attempt_at)
        assert next_attempt_1 >= t0 + timedelta(seconds=2)

        # --- Attempt at t0 + 1s (before next_attempt_at) -> must NOT be claimed ---
        t_early = t0 + timedelta(seconds=1)
        count_early = await process_pending_outbox_events(db=db_session, now=t_early, max_retries=5)
        assert count_early == 0
        db_session.refresh(event)
        assert event.attempt_count == 1  # Unchanged

        # --- Attempt 2 at next_attempt_1 + 1s -> must be claimed and fail again ---
        t_retry_2 = next_attempt_1 + timedelta(seconds=1)
        await process_pending_outbox_events(db=db_session, now=t_retry_2, max_retries=5)
        db_session.refresh(event)
        assert event.attempt_count == 2
        assert event.status == "FAILED"
        next_attempt_2 = to_utc(event.next_attempt_at)
        assert next_attempt_2 >= t_retry_2 + timedelta(seconds=4)

        # --- Run attempts 3, 4, and 5 ---
        t_retry_3 = next_attempt_2 + timedelta(seconds=1)
        await process_pending_outbox_events(db=db_session, now=t_retry_3, max_retries=5)
        db_session.refresh(event)
        assert event.attempt_count == 3

        t_retry_4 = to_utc(event.next_attempt_at) + timedelta(seconds=1)
        await process_pending_outbox_events(db=db_session, now=t_retry_4, max_retries=5)
        db_session.refresh(event)
        assert event.attempt_count == 4

        t_retry_5 = to_utc(event.next_attempt_at) + timedelta(seconds=1)
        await process_pending_outbox_events(db=db_session, now=t_retry_5, max_retries=5)
        db_session.refresh(event)
        assert event.attempt_count == 5

        # --- Dead-Letter State: Status is FAILED and next_attempt_at is cleared ---
        assert event.status == "FAILED"
        assert event.next_attempt_at is None
        assert event.error_code == "HTTP_500"

        # --- Far future attempt: Must NEVER be claimed again ---
        t_future = t0 + timedelta(days=365)
        count_future = await process_pending_outbox_events(db=db_session, now=t_future, max_retries=5)
        assert count_future == 0
        db_session.refresh(event)
        assert event.attempt_count == 5  # Still dead-lettered

        # --- Far future attempt: Must NEVER be claimed again ---
        t_future = t0 + timedelta(days=365)
        count_future = await process_pending_outbox_events(db=db_session, now=t_future, max_retries=5)
        assert count_future == 0
        db_session.refresh(event)
        assert event.attempt_count == 5  # Still dead-lettered


# ============================================================================
# DEL-003: Unknown Event Type & Missing Tenant Quarantining
# ============================================================================

@pytest.mark.asyncio
async def test_unknown_event_type_quarantined_not_processed(db_session, outbox_test_tenants):
    """Verify unknown outbox event types are quarantined with structured error code and never marked processed."""
    tenant_a = outbox_test_tenants["tenant_a"]

    unknown_event = OutboxEvent(
        tenant_id=tenant_a.id,
        type="billing.invoice.reconciled.v99",
        payload=json.dumps({"invoice_id": "inv_123"}),
        status="PENDING",
    )
    db_session.add(unknown_event)
    db_session.commit()
    db_session.refresh(unknown_event)

    processed_count = await process_pending_outbox_events(db=db_session)
    assert processed_count == 0

    db_session.refresh(unknown_event)
    assert unknown_event.status == "QUARANTINED"
    assert unknown_event.error_code == "UNKNOWN_EVENT_TYPE"
    assert "Unknown outbox event type" in (unknown_event.error_detail or "")
    assert unknown_event.processed is False
    assert unknown_event.leased_by is None
    assert unknown_event.lease_expires_at is None
    assert unknown_event.next_attempt_at is None


@pytest.mark.asyncio
async def test_missing_tenant_domain_event_quarantined(db_session):
    """Verify domain webhook events missing tenant_id are quarantined instead of broadcast."""
    orphan_event = OutboxEvent(
        tenant_id=None,
        type="booking.created",
        payload=json.dumps({"booking_id": 555}),
        status="PENDING",
    )
    db_session.add(orphan_event)
    db_session.commit()
    db_session.refresh(orphan_event)

    await process_pending_outbox_events(db=db_session)

    db_session.refresh(orphan_event)
    assert orphan_event.status == "QUARANTINED"
    assert orphan_event.error_code == "MISSING_TENANT_ID"
    assert "missing required tenant_id" in (orphan_event.error_detail or "")


# ============================================================================
# SEC-005: Privacy Redaction and Structured Error Codes
# ============================================================================

def test_categorize_error_and_sanitize_privacy():
    """Verify exception mapper redacts phone numbers, bearer tokens, query parameters, and emails."""
    # 1. SSRF error
    ssrf_err = ValueError("SSRF protection blocked request to http://169.254.169.254/latest/meta-data")
    code, detail = categorize_error(ssrf_err)
    assert code == "SSRF_BLOCKED"
    assert "169.254" not in detail

    # 2. HTTP error
    mock_resp = MagicMock()
    mock_resp.status_code = 502
    http_err = httpx.HTTPStatusError("502 Bad Gateway", request=MagicMock(), response=mock_resp)
    code, detail = categorize_error(http_err)
    assert code == "HTTP_502"
    assert "502" in detail

    # 3. Timeout
    timeout_err = httpx.ConnectTimeout("Connection to https://example.com/api?token=secret123 timed out")
    code, detail = categorize_error(timeout_err)
    assert code == "TIMEOUT"
    assert "secret123" not in detail

    # 4. Network error
    net_err = httpx.ConnectError("Failed to connect")
    code, detail = categorize_error(net_err)
    assert code == "NETWORK_ERROR"

    # 5. Sanitizer helper directly
    raw_leak = "Failed sending to +15559876543 for user alice@alpha.com with Bearer eyJhbGciOiJIUzI1NiIsIn and url https://target.com/hook?key=topsecret"
    sanitized = sanitize_message(raw_leak)
    assert "+15559876543" not in sanitized
    assert "alice@alpha.com" not in sanitized
    assert "eyJhbGciOiJIUzI1NiIsIn" not in sanitized
    assert "topsecret" not in sanitized
    assert "[REDACTED_PHONE]" in sanitized
    assert "[REDACTED_EMAIL]" in sanitized
    assert "Bearer [REDACTED]" in sanitized
    assert "?[REDACTED]" in sanitized


@pytest.mark.asyncio
async def test_failure_records_contain_only_privacy_safe_structured_data(db_session, outbox_test_tenants):
    """Verify OutboxEvent and WebhookDelivery failure fields never store raw customer PII or tokens."""
    tenant_a = outbox_test_tenants["tenant_a"]

    hook = WebhookRegistration(
        tenant_id=tenant_a.id,
        event="client.created",
        target_url="https://example.com/sensitive-hook",
        secret="whsec_secret_abc123",
        is_active=True,
    )
    event = OutboxEvent(
        tenant_id=tenant_a.id,
        type="client.created",
        payload=json.dumps({"client_phone": "+15550009999", "client_email": "client@example.com", "token": "secret_token_val"}),
        status="PENDING",
    )
    db_session.add_all([hook, event])
    db_session.commit()
    db_session.refresh(event)

    async def mock_post_leak(*args, **kwargs):
        raise ValueError("Failed delivering customer +15550009999 client@example.com token secret_token_val")

    with patch("httpx.AsyncClient.post", new=mock_post_leak), \
         patch("app.core.network_safety.validate_url_safety", return_value=(True, None)):
        await process_pending_outbox_events(db=db_session)

    db_session.refresh(event)
    assert event.status == "FAILED"
    assert event.error_code is not None

    # Verify no PII leaked into OutboxEvent error fields
    assert "+15550009999" not in (event.error_detail or "")
    assert "client@example.com" not in (event.error_detail or "")
    assert "+15550009999" not in (event.error_log or "")

    # Verify no PII leaked into WebhookDelivery error fields
    delivery = db_session.query(WebhookDelivery).filter_by(outbox_event_id=event.id).first()
    if delivery and delivery.error_message:
        assert "+15550009999" not in delivery.error_message
        assert "client@example.com" not in delivery.error_message


# ============================================================================
# Multi-Tenant Isolation: Poison Job Isolation
# ============================================================================

@pytest.mark.asyncio
async def test_poison_job_for_tenant_a_does_not_block_tenant_b(db_session, outbox_test_tenants):
    """Verify a crashing/poison job for Tenant A does not abort or block Tenant B events in the same batch."""
    tenant_a = outbox_test_tenants["tenant_a"]
    tenant_b = outbox_test_tenants["tenant_b"]

    # Hook for Tenant A (will fail)
    hook_a = WebhookRegistration(
        tenant_id=tenant_a.id,
        event="booking.created",
        target_url="https://example.com/tenant-a-poison",
        is_active=True,
    )
    # Hook for Tenant B (will succeed)
    hook_b = WebhookRegistration(
        tenant_id=tenant_b.id,
        event="booking.created",
        target_url="https://example.com/tenant-b-healthy",
        is_active=True,
    )
    event_a_poison = OutboxEvent(
        tenant_id=tenant_a.id,
        type="booking.created",
        payload=json.dumps({"booking_id": 1}),
        status="PENDING",
    )
    event_b_healthy = OutboxEvent(
        tenant_id=tenant_b.id,
        type="booking.created",
        payload=json.dumps({"booking_id": 2}),
        status="PENDING",
    )

    db_session.add_all([hook_a, hook_b, event_a_poison, event_b_healthy])
    db_session.commit()
    db_session.refresh(event_a_poison)
    db_session.refresh(event_b_healthy)

    async def mock_post_conditional(self, url, *args, **kwargs):
        if "tenant-a-poison" in url:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            http_err = httpx.HTTPStatusError("500 Poison Crash", request=MagicMock(), response=mock_resp)
            mock_resp.raise_for_status = MagicMock(side_effect=http_err)
            raise http_err
        else:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

    with patch("httpx.AsyncClient.post", new=mock_post_conditional), \
         patch("app.core.network_safety.validate_url_safety", return_value=(True, None)):
        processed_count = await process_pending_outbox_events(db=db_session)

    # Tenant B was successfully processed
    assert processed_count == 1

    db_session.refresh(event_a_poison)
    db_session.refresh(event_b_healthy)

    # Tenant A failed
    assert event_a_poison.status == "FAILED"
    assert event_a_poison.attempt_count == 1

    # Tenant B succeeded
    assert event_b_healthy.status == "PROCESSED"
    assert event_b_healthy.processed is True

    # Deliveries
    delivery_a = db_session.query(WebhookDelivery).filter_by(outbox_event_id=event_a_poison.id).first()
    assert delivery_a.status == "FAILED"

    delivery_b = db_session.query(WebhookDelivery).filter_by(outbox_event_id=event_b_healthy.id).first()
    assert delivery_b.status == "SUCCESS"


# ============================================================================
# DEL-002: Worker Lifecycle & Graceful Lease Release
# ============================================================================

def test_release_active_leases_on_shutdown(db_session):
    """Verify release_active_leases resets all in-flight PROCESSING events for worker back to PENDING."""
    worker_id = "worker-to-be-shutdown"

    event1 = OutboxEvent(
        tenant_id=1,
        type="SEND_SMS",
        payload=json.dumps({"to": "+15551112222", "body": "msg 1"}),
        status="PROCESSING",
        leased_by=worker_id,
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
    )
    event2 = OutboxEvent(
        tenant_id=1,
        type="SEND_SMS",
        payload=json.dumps({"to": "+15551112223", "body": "msg 2"}),
        status="PROCESSING",
        leased_by=worker_id,
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
    )
    other_worker_event = OutboxEvent(
        tenant_id=1,
        type="SEND_SMS",
        payload=json.dumps({"to": "+15551112224", "body": "msg 3"}),
        status="PROCESSING",
        leased_by="other-worker-staying-alive",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
    )

    db_session.add_all([event1, event2, other_worker_event])
    db_session.commit()

    released_count = release_active_leases(db=db_session, worker_id=worker_id)
    assert released_count == 2

    db_session.refresh(event1)
    db_session.refresh(event2)
    db_session.refresh(other_worker_event)

    # Worker's leases are returned to PENDING
    assert event1.status == "PENDING"
    assert event1.leased_by is None
    assert event1.lease_expires_at is None

    assert event2.status == "PENDING"
    assert event2.leased_by is None
    assert event2.lease_expires_at is None

    # Other worker's lease remains undisturbed
    assert other_worker_event.status == "PROCESSING"
    assert other_worker_event.leased_by == "other-worker-staying-alive"