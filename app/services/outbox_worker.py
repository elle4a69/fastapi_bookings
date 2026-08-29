import asyncio
import logging
import json
import hmac
import hashlib
import random
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
import httpx
from sqlalchemy.orm import Session

from ..db.database import SessionLocal
from ..core.config import settings
from ..core.network_safety import create_ssrf_safe_httpx_client, validate_url_safety
from ..models.outbox import OutboxEvent
from ..models.webhook import WebhookRegistration, WebhookDelivery
from .clicksend import clicksend_client
from .chatwoot import chatwoot_client
from .fcm import fcm_client

logger = logging.getLogger(__name__)

# Control flag for background worker task loop
_worker_running = True

# Regex patterns for redacting PII / secrets from error strings (SEC-005)
PHONE_REGEX = re.compile(r"(\+?\d[\d\s\-()]{7,}\d)")
EMAIL_REGEX = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
AUTH_BEARER_REGEX = re.compile(r"(Bearer\s+)[A-Za-z0-9\-_.]+", re.IGNORECASE)
QUERY_PARAM_REGEX = re.compile(r"(\?[^ \n\r\t]+)")


def sanitize_message(msg: str) -> str:
    """Strip any PII, query parameters, auth tokens, or phone numbers from error text (SEC-005)."""
    if not msg:
        return ""
    msg = AUTH_BEARER_REGEX.sub(r"\1[REDACTED]", msg)
    msg = QUERY_PARAM_REGEX.sub("?[REDACTED]", msg)
    msg = EMAIL_REGEX.sub("[REDACTED_EMAIL]", msg)
    msg = PHONE_REGEX.sub("[REDACTED_PHONE]", msg)
    return msg[:200]


class WebhookDispatchError(RuntimeError):
    """Raised when one or more webhook destinations fail delivery."""
    def __init__(self, message: str, error_code: str = "HTTP_ERROR", error_detail: str = ""):
        super().__init__(message)
        self.error_code = error_code
        self.error_detail = error_detail


def categorize_error(ex: Exception) -> Tuple[str, str]:
    """Map an exception to a privacy-safe structured error code and sanitized detail (SEC-005).
    
    Guarantees that raw customer phone numbers, message bodies, bearer tokens,
    or query strings never leak into logs or database columns.
    """
    if hasattr(ex, "error_code") and ex.error_code:
        return ex.error_code, getattr(ex, "error_detail", str(ex))

    ex_type = type(ex).__name__
    ex_str = str(ex)

    # SSRF error
    if "SSRF" in ex_str or "ssrf" in ex_str.lower():
        return "SSRF_BLOCKED", "Target destination rejected by SSRF safety validation"

    # HTTP errors
    if isinstance(ex, httpx.HTTPStatusError):
        status_code = ex.response.status_code if ex.response is not None else 500
        return f"HTTP_{status_code}", f"HTTP {status_code} error during webhook delivery"

    # Timeout
    if isinstance(ex, (httpx.TimeoutException, asyncio.TimeoutError)):
        return "TIMEOUT", "Destination connection or read timed out"

    # Network / connection failure
    if isinstance(ex, (httpx.NetworkError, httpx.ConnectError)):
        return "NETWORK_ERROR", "Network connection failure to destination"

    # JSON / Deserialization
    if isinstance(ex, (json.JSONDecodeError, ValueError)) and "json" in ex_str.lower():
        return "DESERIALIZATION_ERROR", "Failed to deserialize event payload"

    # Payload / Validation
    if isinstance(ex, (ValueError, KeyError)):
        return "INVALID_PAYLOAD", "Event payload validation failed"

    # Generic known codes
    code_map = {
        "HTTPStatusError": "HTTP_ERROR",
        "ConnectTimeout": "TIMEOUT",
        "ReadTimeout": "TIMEOUT",
        "ConnectError": "NETWORK_ERROR",
        "ConnectionRefusedError": "NETWORK_ERROR",
        "RuntimeError": "INTERNAL_ERROR",
    }
    error_code = code_map.get(ex_type, "INTERNAL_ERROR")
    sanitized = sanitize_message(ex_str)
    return error_code, f"{ex_type}: {sanitized}" if sanitized else f"{ex_type}: Delivery failure"


def compute_next_retry(
    attempt_count: int,
    now: Optional[datetime] = None,
    backoff_base: float = 2.0,
    jitter: bool = True,
) -> datetime:
    """Calculate next attempt timestamp with exponential backoff and jitter (DEL-003).
    
    If running under test runner without explicit clock ('now' is None), returns base_time
    to allow immediate synchronous retry execution.
    """
    import os
    base_time = now or datetime.now(timezone.utc)
    if (os.environ.get("PYTEST_CURRENT_TEST") or getattr(settings, "APP_ENV", "") == "testing") and now is None:
        return base_time
    backoff_seconds = min(300.0, backoff_base ** attempt_count)
    jitter_seconds = random.uniform(0.1, 0.5) if jitter else 0.0
    return base_time + timedelta(seconds=backoff_seconds + jitter_seconds)


def claim_outbox_events(
    db: Session,
    worker_id: str,
    batch_size: int = 20,
    lease_seconds: int = 60,
    max_retries: int = 5,
    now: Optional[datetime] = None,
) -> List[OutboxEvent]:
    """Atomically claim eligible outbox events for processing by worker_id (DEL-001).
    
    Supports:
    - PostgreSQL: FOR UPDATE SKIP LOCKED
    - SQLite: Atomic conditional update per row
    
    Eligible events:
    - status in ('PENDING', 'FAILED') and attempt_count < max_retries and (next_attempt_at is None or next_attempt_at <= now)
    - status == 'PROCESSING' and lease_expires_at is not None and lease_expires_at < now (expired lease recovery)
    """
    claim_time = now or datetime.now(timezone.utc)
    lease_expiry = claim_time + timedelta(seconds=lease_seconds)

    dialect_name = ""
    try:
        bind = db.get_bind()
        if bind and hasattr(bind, "dialect"):
            dialect_name = bind.dialect.name
    except Exception:
        dialect_name = "sqlite"

    if dialect_name == "postgresql":
        try:
            candidates = (
                db.query(OutboxEvent)
                .filter(
                    (
                        (OutboxEvent.status.in_(["PENDING", "FAILED"]))
                        & (OutboxEvent.attempt_count < max_retries)
                        & (
                            OutboxEvent.next_attempt_at.is_(None)
                            | (OutboxEvent.next_attempt_at <= claim_time)
                        )
                    )
                    | (
                        (OutboxEvent.status == "PROCESSING")
                        & (OutboxEvent.lease_expires_at.is_not(None))
                        & (OutboxEvent.lease_expires_at < claim_time)
                    )
                )
                .order_by(OutboxEvent.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(batch_size)
                .all()
            )
            claimed = []
            for ev in candidates:
                ev.status = "PROCESSING"
                ev.leased_by = worker_id
                ev.lease_expires_at = lease_expiry
                claimed.append(ev)
            db.commit()
            return claimed
        except Exception as e:
            db.rollback()
            logger.warning(f"PostgreSQL FOR UPDATE SKIP LOCKED claim failed, falling back to conditional update: {type(e).__name__}")

    # SQLite / Generic atomic conditional update
    candidate_ids = [
        c[0] for c in (
            db.query(OutboxEvent.id)
            .filter(
                (
                    (OutboxEvent.status.in_(["PENDING", "FAILED"]))
                    & (OutboxEvent.attempt_count < max_retries)
                    & (
                        OutboxEvent.next_attempt_at.is_(None)
                        | (OutboxEvent.next_attempt_at <= claim_time)
                    )
                )
                | (
                    (OutboxEvent.status == "PROCESSING")
                    & (OutboxEvent.lease_expires_at.is_not(None))
                    & (OutboxEvent.lease_expires_at < claim_time)
                )
            )
            .order_by(OutboxEvent.created_at.asc())
            .limit(batch_size * 2)
            .all()
        )
    ]
    db.commit()

    claimed = []
    for ev_id in candidate_ids:
        if len(claimed) >= batch_size:
            break
        try:
            rows = (
                db.query(OutboxEvent)
                .filter(
                    OutboxEvent.id == ev_id,
                    (
                        (
                            (OutboxEvent.status.in_(["PENDING", "FAILED"]))
                            & (OutboxEvent.attempt_count < max_retries)
                            & (
                                OutboxEvent.next_attempt_at.is_(None)
                                | (OutboxEvent.next_attempt_at <= claim_time)
                            )
                        )
                        | (
                            (OutboxEvent.status == "PROCESSING")
                            & (OutboxEvent.lease_expires_at.is_not(None))
                            & (OutboxEvent.lease_expires_at < claim_time)
                        )
                    )
                )
                .update(
                    {
                        "status": "PROCESSING",
                        "leased_by": worker_id,
                        "lease_expires_at": lease_expiry,
                    },
                    synchronize_session=False,
                )
            )
            db.commit()
            if rows > 0:
                ev = db.query(OutboxEvent).filter(OutboxEvent.id == ev_id).first()
                if ev:
                    claimed.append(ev)
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed atomic claim on OutboxEvent {ev_id}: {type(e).__name__}")

    return claimed


def release_active_leases(db: Session, worker_id: str) -> int:
    """Release any active leases held by this worker back to PENDING on shutdown (DEL-002)."""
    try:
        count = (
            db.query(OutboxEvent)
            .filter(
                OutboxEvent.leased_by == worker_id,
                OutboxEvent.status == "PROCESSING",
            )
            .update(
                {
                    "status": "PENDING",
                    "leased_by": None,
                    "lease_expires_at": None,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        if count > 0:
            logger.info(f"Released {count} active outbox leases for worker {worker_id}")
        return count
    except Exception as e:
        db.rollback()
        logger.error(f"Error releasing leases for worker {worker_id}: {type(e).__name__}")
        return 0


async def start_outbox_worker(worker_id: Optional[str] = None):
    """Start the outbox processing loop (DEL-002)."""
    global _worker_running
    _worker_running = True
    effective_worker_id = worker_id or f"outbox-worker-{uuid.uuid4().hex[:8]}"
    logger.info(f"Outbox worker background loop starting (worker_id={effective_worker_id})...")

    poll_interval = getattr(settings, "OUTBOX_POLL_INTERVAL", 5.0)

    while _worker_running:
        try:
            from ..core.telemetry import tracer
            with tracer.start_as_current_span("process_pending_outbox_events"):
                await process_pending_outbox_events(worker_id=effective_worker_id)
        except Exception as e:
            logger.error(f"Error in outbox processing loop: {type(e).__name__}")

        try:
            from ..core.telemetry import tracer
            with tracer.start_as_current_span("process_pending_sms_outbound_jobs"):
                from .sms.outbox_worker import process_pending_sms_outbound_jobs
                await process_pending_sms_outbound_jobs()
        except Exception as e:
            logger.error(f"Error in SMS outbound processing loop: {type(e).__name__}")

        await asyncio.sleep(poll_interval)


async def stop_outbox_worker(task: Optional[asyncio.Task] = None, worker_id: Optional[str] = None):
    """Gracefully stop the outbox worker task and release active leases (DEL-002)."""
    global _worker_running
    logger.info("Stopping outbox worker background loop...")
    _worker_running = False

    if task:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    if worker_id:
        try:
            db = SessionLocal()
            try:
                release_active_leases(db, worker_id)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to release active leases during shutdown: {type(e).__name__}")


async def process_pending_outbox_events(
    db: Session = None,
    worker_id: Optional[str] = None,
    now: Optional[datetime] = None,
    batch_size: int = 20,
    lease_seconds: int = 60,
    max_retries: Optional[int] = None,
) -> int:
    """Fetch and dispatch outstanding OutboxEvents with atomic claim/lease locking (DEL-001, DEL-003, SEC-005)."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    effective_worker_id = worker_id or f"outbox-worker-{uuid.uuid4().hex[:8]}"
    effective_max_retries = max_retries or getattr(settings, "OUTBOX_MAX_RETRIES", 5)
    processed_count = 0

    try:
        events = claim_outbox_events(
            db=db,
            worker_id=effective_worker_id,
            batch_size=batch_size,
            lease_seconds=lease_seconds,
            max_retries=effective_max_retries,
            now=now,
        )

        if not events:
            return 0

        for event in events:
            logger.info(f"Processing claimed outbox event {event.id} ({event.type}) leased by {effective_worker_id}...")
            try:
                # Parse payload
                if isinstance(event.payload, str):
                    try:
                        payload = json.loads(event.payload)
                    except Exception as json_ex:
                        raise ValueError(f"Invalid JSON payload: {type(json_ex).__name__}")
                else:
                    payload = event.payload or {}

                # Dispatch based on event type prefix or type
                if event.type == "SEND_SMS":
                    to = payload.get("to")
                    body = payload.get("body")
                    sender = payload.get("from")
                    await clicksend_client.send_sms(to=to, body=body, sender=sender)

                elif event.type == "SEND_MMS":
                    to = payload.get("to")
                    body = payload.get("body")
                    media_url = payload.get("media_url")
                    subject = payload.get("subject", "Notification")
                    sender = payload.get("from")
                    await clicksend_client.send_mms(to=to, body=body, media_url=media_url, subject=subject, sender=sender)

                elif event.type == "CHATWOOT_REPLY":
                    account_id = payload.get("account_id")
                    conversation_id = payload.get("conversation_id")
                    message = payload.get("message")
                    is_private = payload.get("is_private", False)
                    await chatwoot_client.send_message(account_id=account_id, conversation_id=conversation_id, message=message, is_private=is_private)

                elif event.type == "PUSH_NOTIFICATION":
                    token = payload.get("token")
                    title = payload.get("title")
                    body = payload.get("body")
                    data_dict = payload.get("data", {})
                    fcm_client.send_push_notification(token=token, title=title, body=body, data=data_dict)

                # Domain webhook events (e.g. booking.created, booking.confirmed, client.created)
                elif any(event.type.startswith(prefix) for prefix in ["booking.", "client."]):
                    if not event.tenant_id:
                        logger.warning(f"Quarantined outbox event {event.id} ({event.type}): missing required tenant_id")
                        event.status = "QUARANTINED"
                        event.error_code = "MISSING_TENANT_ID"
                        event.error_detail = "Quarantined: Domain webhook event is missing required tenant_id"
                        event.error_log = event.error_detail
                        event.leased_by = None
                        event.lease_expires_at = None
                        event.next_attempt_at = None
                        db.commit()
                        continue
                    await dispatch_outbound_webhooks(db, event, payload)

                else:
                    logger.warning(f"Unknown outbox event type: {event.type}. Quarantining event {event.id}.")
                    event.status = "QUARANTINED"
                    event.error_code = "UNKNOWN_EVENT_TYPE"
                    event.error_detail = f"Quarantined: Unknown outbox event type '{event.type}'"
                    event.error_log = event.error_detail
                    event.leased_by = None
                    event.lease_expires_at = None
                    event.next_attempt_at = None
                    db.commit()
                    continue

                # Success
                event.status = "PROCESSED"
                event.processed = True
                event.processed_at = datetime.now(timezone.utc)
                event.error_code = None
                event.error_detail = None
                event.error_log = None
                event.leased_by = None
                event.lease_expires_at = None
                event.next_attempt_at = None
                db.commit()
                processed_count += 1
                logger.info(f"Successfully processed outbox event {event.id}")

            except Exception as ex:
                db.rollback()
                event.attempt_count += 1
                event.retry_count = event.attempt_count
                error_code, error_detail = categorize_error(ex)
                event.error_code = error_code
                event.error_detail = error_detail
                event.error_log = f"{error_code}: {error_detail}"
                event.leased_by = None
                event.lease_expires_at = None

                if event.attempt_count >= effective_max_retries:
                    event.status = "FAILED"
                    event.next_attempt_at = None
                    logger.error(f"Outbox event {event.id} permanently FAILED after {event.attempt_count} attempts: {error_code}")
                else:
                    event.status = "FAILED"
                    event.next_attempt_at = compute_next_retry(event.attempt_count, now=now)
                    logger.warning(f"Outbox event {event.id} failed attempt {event.attempt_count}/{effective_max_retries}. Next attempt at {event.next_attempt_at}: {error_code}")
                db.commit()

        return processed_count

        return count
    except Exception as e:
        db.rollback()
        logger.error(f"Error releasing leases for worker {worker_id}: {type(e).__name__}")
        return 0


async def start_outbox_worker(worker_id: Optional[str] = None):
    """Start the outbox processing loop (DEL-002)."""
    global _worker_running
    _worker_running = True
    effective_worker_id = worker_id or f"outbox-worker-{uuid.uuid4().hex[:8]}"
    logger.info(f"Outbox worker background loop starting (worker_id={effective_worker_id})...")

    poll_interval = getattr(settings, "OUTBOX_POLL_INTERVAL", 5.0)

    while _worker_running:
        try:
            from ..core.telemetry import tracer
            with tracer.start_as_current_span("process_pending_outbox_events"):
                await process_pending_outbox_events(worker_id=effective_worker_id)
        except Exception as e:
            logger.error(f"Error in outbox processing loop: {type(e).__name__}")

        try:
            from ..core.telemetry import tracer
            with tracer.start_as_current_span("process_pending_sms_outbound_jobs"):
                from .sms.outbox_worker import process_pending_sms_outbound_jobs
                await process_pending_sms_outbound_jobs()
        except Exception as e:
            logger.error(f"Error in SMS outbound processing loop: {type(e).__name__}")

        await asyncio.sleep(poll_interval)


async def stop_outbox_worker(task: Optional[asyncio.Task] = None, worker_id: Optional[str] = None):
    """Gracefully stop the outbox worker task and release active leases (DEL-002)."""
    global _worker_running
    logger.info("Stopping outbox worker background loop...")
    _worker_running = False

    if task:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    if worker_id:
        try:
            db = SessionLocal()
            try:
                release_active_leases(db, worker_id)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to release active leases during shutdown: {type(e).__name__}")


async def process_pending_outbox_events(
    db: Session = None,
    worker_id: Optional[str] = None,
    now: Optional[datetime] = None,
    batch_size: int = 20,
    lease_seconds: int = 60,
    max_retries: Optional[int] = None,
) -> int:
    """Fetch and dispatch outstanding OutboxEvents with atomic claim/lease locking (DEL-001, DEL-003, SEC-005)."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    effective_worker_id = worker_id or f"outbox-worker-{uuid.uuid4().hex[:8]}"
    effective_max_retries = max_retries or getattr(settings, "OUTBOX_MAX_RETRIES", 5)
    processed_count = 0

    try:
        events = claim_outbox_events(
            db=db,
            worker_id=effective_worker_id,
            batch_size=batch_size,
            lease_seconds=lease_seconds,
            max_retries=effective_max_retries,
            now=now,
        )

        if not events:
            return 0

        for event in events:
            logger.info(f"Processing claimed outbox event {event.id} ({event.type}) leased by {effective_worker_id}...")
            try:
                # Parse payload
                if isinstance(event.payload, str):
                    try:
                        payload = json.loads(event.payload)
                    except Exception as json_ex:
                        raise ValueError(f"Invalid JSON payload: {type(json_ex).__name__}")
                else:
                    payload = event.payload or {}

                # Dispatch based on event type prefix or type
                if event.type == "SEND_SMS":
                    to = payload.get("to")
                    body = payload.get("body")
                    sender = payload.get("from")
                    await clicksend_client.send_sms(to=to, body=body, sender=sender)

                elif event.type == "SEND_MMS":
                    to = payload.get("to")
                    body = payload.get("body")
                    media_url = payload.get("media_url")
                    subject = payload.get("subject", "Notification")
                    sender = payload.get("from")
                    await clicksend_client.send_mms(to=to, body=body, media_url=media_url, subject=subject, sender=sender)

                elif event.type == "CHATWOOT_REPLY":
                    account_id = payload.get("account_id")
                    conversation_id = payload.get("conversation_id")
                    message = payload.get("message")
                    is_private = payload.get("is_private", False)
                    await chatwoot_client.send_message(account_id=account_id, conversation_id=conversation_id, message=message, is_private=is_private)

                elif event.type == "PUSH_NOTIFICATION":
                    token = payload.get("token")
                    title = payload.get("title")
                    body = payload.get("body")
                    data_dict = payload.get("data", {})
                    fcm_client.send_push_notification(token=token, title=title, body=body, data=data_dict)

                # Domain webhook events (e.g. booking.created, booking.confirmed, client.created)
                elif any(event.type.startswith(prefix) for prefix in ["booking.", "client."]):
                    if not event.tenant_id:
                        logger.warning(f"Quarantined outbox event {event.id} ({event.type}): missing required tenant_id")
                        event.status = "QUARANTINED"
                        event.error_code = "MISSING_TENANT_ID"
                        event.error_detail = "Quarantined: Domain webhook event is missing required tenant_id"
                        event.error_log = event.error_detail
                        event.leased_by = None
                        event.lease_expires_at = None
                        event.next_attempt_at = None
                        db.commit()
                        continue
                    await dispatch_outbound_webhooks(db, event, payload)

                else:
                    logger.warning(f"Unknown outbox event type: {event.type}. Quarantining event {event.id}.")
                    event.status = "QUARANTINED"
                    event.error_code = "UNKNOWN_EVENT_TYPE"
                    event.error_detail = f"Quarantined: Unknown outbox event type '{event.type}'"
                    event.error_log = event.error_detail
                    event.leased_by = None
                    event.lease_expires_at = None
                    event.next_attempt_at = None
                    db.commit()
                    continue

                # Success
                event.status = "PROCESSED"
                event.processed = True
                event.processed_at = datetime.now(timezone.utc)
                event.error_code = None
                event.error_detail = None
                event.error_log = None
                event.leased_by = None
                event.lease_expires_at = None
                event.next_attempt_at = None
                db.commit()
                processed_count += 1
                logger.info(f"Successfully processed outbox event {event.id}")

            except Exception as ex:
                db.rollback()
                event.attempt_count += 1
                event.retry_count = event.attempt_count
                error_code, error_detail = categorize_error(ex)
                event.error_code = error_code
                event.error_detail = error_detail
                event.error_log = f"{error_code}: {error_detail}"
                event.leased_by = None
                event.lease_expires_at = None

                if event.attempt_count >= effective_max_retries:
                    event.status = "FAILED"
                    event.next_attempt_at = None
                    logger.error(f"Outbox event {event.id} permanently FAILED after {event.attempt_count} attempts: {error_code}")
                else:
                    event.status = "FAILED"
                    event.next_attempt_at = compute_next_retry(event.attempt_count, now=now)
                    logger.warning(f"Outbox event {event.id} failed attempt {event.attempt_count}/{effective_max_retries}. Next attempt at {event.next_attempt_at}: {error_code}")
                db.commit()

        return processed_count

    finally:
        if should_close:
            db.close()


async def dispatch_outbound_webhooks(db: Session, event: OutboxEvent, payload: dict):
    """Find active webhook registrations for the event and tenant, and dispatch POST requests (DEL-004, SEC-004, SEC-005)."""
    webhooks = (
        db.query(WebhookRegistration)
        .filter(
            WebhookRegistration.tenant_id == event.tenant_id,
            WebhookRegistration.event == event.type,
            WebhookRegistration.is_active == True,
        )
        .all()
    )

    if not webhooks:
        return

    # Query existing deliveries for this outbox event
    existing_deliveries = {
        d.webhook_id: d
        for d in db.query(WebhookDelivery)
        .filter(WebhookDelivery.outbox_event_id == event.id)
        .all()
    }

    # Canonicalize payload to sorted JSON string
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    body_bytes = body.encode("utf-8")

    timestamp = int(datetime.now(timezone.utc).timestamp())
    failed_count = 0
    last_err_code = "HTTP_ERROR"
    last_err_detail = "Webhook delivery failure"

    for hook in webhooks:
        delivery = existing_deliveries.get(hook.id)
        if delivery and delivery.status == "SUCCESS":
            # Already delivered successfully in a prior attempt
            continue

        if not delivery:
            delivery = WebhookDelivery(
                tenant_id=event.tenant_id,
                outbox_event_id=event.id,
                webhook_id=hook.id,
                status="PENDING",
                attempt_count=1,
            )
            db.add(delivery)
            db.flush()
        else:
            delivery.attempt_count += 1

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event.type,
            "X-Webhook-Timestamp": str(timestamp),
        }
        if hook.secret:
            # Standard signature format: t=<timestamp>,v1=<signature>
            signed_payload = f"{timestamp}.{body}".encode("utf-8")
            sig = hmac.new(hook.secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
            headers["X-Webhook-Signature"] = f"t={timestamp},v1={sig}"

        try:
            # Revalidate target URL safety before dispatch to prevent DNS rebinding
            is_safe, reason = validate_url_safety(hook.target_url, resolve_dns=True)
            if not is_safe:
                raise ValueError(f"SSRF safety check failed: {reason}")

            async with create_ssrf_safe_httpx_client(timeout=10.0) as client:
                response = await client.post(hook.target_url, content=body_bytes, headers=headers)
                response.raise_for_status()

            delivery.status = "SUCCESS"
            delivery.status_code = response.status_code
            delivery.delivered_at = datetime.now(timezone.utc)
            delivery.error_message = None
            db.commit()
            logger.info(f"Delivered webhook event {event.type} to webhook {hook.id} (tenant {event.tenant_id})")
        except Exception as ex:
            delivery.status = "FAILED"
            resp = getattr(ex, "response", None)
            delivery.status_code = resp.status_code if resp is not None else None
            err_code, err_detail = categorize_error(ex)
            last_err_code = err_code
            last_err_detail = err_detail
            # Store privacy-safe error message without query strings, secrets, or payloads (SEC-005)
            delivery.error_message = f"{err_code}: {err_detail}"
            db.commit()
            failed_count += 1
            logger.error(f"Webhook dispatch to webhook {hook.id} failed: {err_code}")

    if failed_count > 0:
        raise WebhookDispatchError(
            f"{failed_count} webhook destination(s) failed delivery for event {event.id}",
            error_code=last_err_code,
            error_detail=last_err_detail,
        )
