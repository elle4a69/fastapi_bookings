import asyncio
import logging
import json
import hmac
import hashlib
import ipaddress
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
import aiohttp
from aiohttp.abc import AbstractResolver
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..db.database import SessionLocal
from ..core.config import settings
from ..models.outbox import OutboxEvent
from ..models.webhook import WebhookDelivery, decrypt_webhook_secret
from ..schemas.webhook import validate_webhook_target_url

logger = logging.getLogger(__name__)

WEBHOOK_DELIVERY_LEASE = timedelta(minutes=2)
OUTBOX_PENDING_STATUSES = ("PENDING", "RETRY")
OUTBOX_STATUS_PROCESSING = "PROCESSING"
OUTBOX_STATUS_SUCCEEDED = "SUCCEEDED"
OUTBOX_STATUS_QUARANTINED = "QUARANTINED"
OUTBOX_STATUS_DEAD_LETTER = "DEAD_LETTER"

ERROR_PAYLOAD_INVALID = "PAYLOAD_INVALID"
ERROR_EVENT_TYPE_UNSUPPORTED = "EVENT_TYPE_UNSUPPORTED"
ERROR_PROVIDER_DELIVERY_FAILED = "PROVIDER_DELIVERY_FAILED"
ERROR_WEBHOOK_DELIVERY_FAILED = "WEBHOOK_DELIVERY_FAILED"
ERROR_ATTEMPTS_EXHAUSTED = "ATTEMPTS_EXHAUSTED"
WEBHOOK_EVENT_TYPES = frozenset(
    {
        "booking.created",
        "booking.updated",
        "booking.confirmed",
        "booking.cancelled",
        "booking.completed",
        "booking.no_show",
        "booking.rescheduled",
        "booking.status_changed",
        "booking.resource_allocated",
        "client.created",
        "client.updated",
        "client.deleted",
    }
)


class WebhookDeliveryError(Exception):
    """Safe error used to retry an outbox event without leaking webhook data."""


class WebhookRoundIncomplete(WebhookDeliveryError):
    def __init__(self, *, next_attempt_at: datetime | None, made_attempt: bool, terminal: bool):
        self.next_attempt_at = next_attempt_at
        self.made_attempt = made_attempt
        self.terminal = terminal
        super().__init__("Webhook delivery round incomplete")


class PermanentOutboxError(Exception):
    """A privacy-safe structural failure that must be quarantined."""

    def __init__(self, error_code: str):
        self.error_code = error_code
        super().__init__(error_code)


@dataclass(frozen=True)
class OutboxClaim:
    id: int
    status: str
    tenant_id: int | None
    type: str
    payload: str
    created_at: datetime
    webhook_snapshot_at: datetime | None
    idempotency_key: str
    lease_owner: str
    lease_token: str
    lease_expires_at: datetime
    retry_count: int
    attempt_count: int
    max_attempts: int


@dataclass(frozen=True)
class WebhookDeliveryClaim:
    id: int
    target_url: str
    encrypted_signing_secret: str
    idempotency_key: str
    attempt_count: int
    max_attempts: int
    lease_owner: str
    lease_token: str
    lease_expires_at: datetime


class PublicAddressResolver(AbstractResolver):
    """Resolve an outbound webhook hostname once and pin the TCP connection.

    ``aiohttp`` uses these returned addresses directly while retaining the
    original URL hostname for HTTPS certificate validation and SNI.  This
    prevents a second DNS lookup from turning a public registration into an
    internal-address request between validation and connection.
    """

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_UNSPEC):
        try:
            answers = socket.getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise WebhookDeliveryError("Webhook destination resolution failed") from exc

        records = []
        for answer_family, socktype, proto, _canonname, sockaddr in answers:
            address = sockaddr[0]
            try:
                if not ipaddress.ip_address(address).is_global:
                    raise WebhookDeliveryError("Webhook destination is not publicly routable")
            except ValueError as exc:
                raise WebhookDeliveryError("Webhook destination resolution was invalid") from exc
            records.append(
                {
                    "hostname": host,
                    "host": address,
                    "port": port,
                    "family": answer_family,
                    "proto": proto,
                    "flags": 0,
                }
            )
        if not records:
            raise WebhookDeliveryError("Webhook destination resolution returned no addresses")
        return records

    async def close(self) -> None:
        return None

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def retry_delay_seconds(
    retry_number: int,
    *,
    base_seconds: float,
    maximum_seconds: float,
    jitter_ratio: float,
    jitter_value: float,
) -> float:
    """Return bounded exponential backoff with deterministic injectable jitter."""
    exponent = max(0, retry_number - 1)
    unjittered = min(maximum_seconds, base_seconds * (2 ** exponent))
    bounded_jitter = min(1.0, max(0.0, jitter_value))
    multiplier = 1.0 - jitter_ratio + (2.0 * jitter_ratio * bounded_jitter)
    return min(maximum_seconds, max(0.0, unjittered * multiplier))


def stable_retry_jitter(idempotency_key: str, retry_number: int) -> float:
    material = f"{idempotency_key}:{retry_number}".encode("utf-8")
    value = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
    return value / ((1 << 64) - 1)


def _claim_statement(now: datetime):
    eligible = or_(
        and_(
            OutboxEvent.status.in_(OUTBOX_PENDING_STATUSES),
            OutboxEvent.attempt_count < OutboxEvent.max_attempts,
            or_(OutboxEvent.next_attempt_at.is_(None), OutboxEvent.next_attempt_at <= now),
        ),
        and_(
            OutboxEvent.status == OUTBOX_STATUS_PROCESSING,
            OutboxEvent.lease_expires_at <= now,
            OutboxEvent.attempt_count < OutboxEvent.max_attempts,
        ),
    )
    return (
        select(OutboxEvent)
        .where(eligible)
        .order_by(
            OutboxEvent.next_attempt_at.asc().nullsfirst(),
            OutboxEvent.created_at.asc(),
            OutboxEvent.id.asc(),
        )
        .limit(1)
        .with_for_update(skip_locked=True)
    )


def _claim_clock(db: Session, fallback: datetime) -> datetime:
    if db.get_bind().dialect.name == "postgresql":
        return db.execute(select(func.clock_timestamp())).scalar_one()
    return fallback


def claim_next_outbox_event(
    db: Session,
    *,
    worker_id: str,
    now: datetime,
) -> OutboxClaim | None:
    """Atomically claim one due event using PostgreSQL row locking.

    ``FOR UPDATE SKIP LOCKED`` ensures multiple worker processes never own the
    same live lease. The claim is committed before external delivery so a
    crashed process can be recovered after ``lease_expires_at``.
    """
    now = _claim_clock(db, now)
    exhausted = or_(
        and_(
            OutboxEvent.status.in_(OUTBOX_PENDING_STATUSES),
            OutboxEvent.attempt_count >= OutboxEvent.max_attempts,
        ),
        and_(
            OutboxEvent.status == OUTBOX_STATUS_PROCESSING,
            OutboxEvent.lease_expires_at <= now,
            OutboxEvent.attempt_count >= OutboxEvent.max_attempts,
        ),
    )
    db.query(OutboxEvent).filter(exhausted).update(
        {
            OutboxEvent.status: OUTBOX_STATUS_DEAD_LETTER,
            OutboxEvent.processed: True,
            OutboxEvent.processed_at: now,
            OutboxEvent.terminal_at: now,
            OutboxEvent.error_code: ERROR_ATTEMPTS_EXHAUSTED,
            OutboxEvent.lease_owner: None,
            OutboxEvent.lease_token: None,
            OutboxEvent.lease_expires_at: None,
            OutboxEvent.next_attempt_at: None,
        },
        synchronize_session=False,
    )
    db.commit()

    event = db.execute(_claim_statement(now)).scalars().first()
    if event is None:
        db.rollback()
        return None

    event.status = OUTBOX_STATUS_PROCESSING
    event.lease_owner = worker_id
    event.lease_token = str(uuid.uuid4())
    event.lease_expires_at = now + timedelta(seconds=settings.OUTBOX_LEASE_SECONDS)
    event.next_attempt_at = None
    event.dispatch_started_at = now
    event.attempt_count += 1
    event.error_code = None
    db.flush()
    claim = OutboxClaim(
        id=event.id,
        status=event.status,
        tenant_id=event.tenant_id,
        type=event.type,
        payload=event.payload,
        created_at=event.created_at,
        webhook_snapshot_at=event.webhook_snapshot_at,
        idempotency_key=event.idempotency_key,
        lease_owner=event.lease_owner,
        lease_token=event.lease_token,
        lease_expires_at=event.lease_expires_at,
        retry_count=event.retry_count,
        attempt_count=event.attempt_count,
        max_attempts=event.max_attempts,
    )
    db.commit()
    return claim


def _owned_update(db: Session, event: OutboxClaim, values: dict) -> bool:
    updated = (
        db.query(OutboxEvent)
        .filter(
            OutboxEvent.id == event.id,
            OutboxEvent.status == OUTBOX_STATUS_PROCESSING,
            OutboxEvent.lease_token == event.lease_token,
        )
        .update(values, synchronize_session=False)
    )
    db.commit()
    return updated == 1


async def _dispatch_claimed_event(db: Session, event: OutboxClaim, payload: dict):
    if event.type in WEBHOOK_EVENT_TYPES:
        if event.tenant_id is None:
            raise PermanentOutboxError("WEBHOOK_TENANT_CONTEXT_MISSING")
        if event.webhook_snapshot_at is None:
            raise PermanentOutboxError("WEBHOOK_SNAPSHOT_MISSING")
        await dispatch_outbound_webhooks(db, event=event, payload=payload)
        return None
    raise LookupError(ERROR_EVENT_TYPE_UNSUPPORTED)


def _quarantine_claimed_event(
    db: Session,
    event: OutboxClaim,
    *,
    now: datetime,
    error_code: str,
) -> bool:
    return _owned_update(
        db,
        event,
        {
            OutboxEvent.status: OUTBOX_STATUS_QUARANTINED,
            OutboxEvent.processed: True,
            OutboxEvent.processed_at: now,
            OutboxEvent.terminal_at: now,
            OutboxEvent.error_code: error_code,
            OutboxEvent.lease_owner: None,
            OutboxEvent.lease_token: None,
            OutboxEvent.lease_expires_at: None,
        },
    )


def _retry_claimed_event(
    db: Session,
    event: OutboxClaim,
    *,
    now: datetime,
    error_code: str,
    jitter_value: float,
    not_before: datetime | None = None,
) -> bool:
    retry_count = event.retry_count + 1
    is_terminal = event.attempt_count >= event.max_attempts
    next_attempt_at = None
    if not is_terminal:
        delay = retry_delay_seconds(
            retry_count,
            base_seconds=settings.OUTBOX_RETRY_BASE_SECONDS,
            maximum_seconds=settings.OUTBOX_RETRY_MAX_SECONDS,
            jitter_ratio=settings.OUTBOX_RETRY_JITTER_RATIO,
            jitter_value=jitter_value,
        )
        next_attempt_at = now + timedelta(seconds=delay)
        if not_before is not None and _aware(not_before) > _aware(next_attempt_at):
            next_attempt_at = _aware(not_before)
    return _owned_update(
        db,
        event,
        {
            OutboxEvent.status: OUTBOX_STATUS_DEAD_LETTER if is_terminal else "RETRY",
            OutboxEvent.retry_count: retry_count,
            OutboxEvent.processed: is_terminal,
            OutboxEvent.processed_at: now if is_terminal else None,
            OutboxEvent.terminal_at: now if is_terminal else None,
            OutboxEvent.next_attempt_at: next_attempt_at,
            OutboxEvent.error_code: error_code,
            OutboxEvent.lease_owner: None,
            OutboxEvent.lease_token: None,
            OutboxEvent.lease_expires_at: None,
        },
    )


def _defer_claimed_event(
    db: Session,
    event: OutboxClaim,
    *,
    next_attempt_at: datetime,
) -> bool:
    return _owned_update(
        db,
        event,
        {
            OutboxEvent.status: "RETRY",
            OutboxEvent.next_attempt_at: next_attempt_at,
            OutboxEvent.error_code: "WEBHOOK_DELIVERY_PENDING",
            OutboxEvent.lease_owner: None,
            OutboxEvent.lease_token: None,
            OutboxEvent.lease_expires_at: None,
        },
    )


def _dead_letter_claimed_event(db: Session, event: OutboxClaim, *, now: datetime) -> bool:
    return _owned_update(
        db,
        event,
        {
            OutboxEvent.status: OUTBOX_STATUS_DEAD_LETTER,
            OutboxEvent.processed: True,
            OutboxEvent.processed_at: now,
            OutboxEvent.terminal_at: now,
            OutboxEvent.next_attempt_at: None,
            OutboxEvent.error_code: "WEBHOOK_DELIVERY_DEAD_LETTER",
            OutboxEvent.lease_owner: None,
            OutboxEvent.lease_token: None,
            OutboxEvent.lease_expires_at: None,
        },
    )


async def _wait_for_next_poll(stop_event: asyncio.Event) -> None:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=settings.OUTBOX_POLL_INTERVAL)
    except asyncio.TimeoutError:
        pass


async def start_outbox_worker(stop_event: asyncio.Event | None = None):
    """Run the explicit generic outbox worker process loop.

    Web applications do not invoke this function. Deployments start it as a
    separate process with ``python -m app.worker generic``.
    """
    stop_event = stop_event or asyncio.Event()
    worker_id = f"worker:{uuid.uuid4()}"
    logger.info("outbox_worker_started")
    
    while not stop_event.is_set():
        try:
            from ..core.telemetry import tracer
            with tracer.start_as_current_span("process_pending_outbox_events"):
                await process_pending_outbox_events(worker_id=worker_id, stop_event=stop_event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("outbox_poll_failed")
            
        # Poll every settings.OUTBOX_POLL_INTERVAL seconds
        await _wait_for_next_poll(stop_event)


async def start_sms_outbox_worker(stop_event: asyncio.Event | None = None):
    """Run the existing SMS queue as its own explicitly selected process role."""
    stop_event = stop_event or asyncio.Event()
    logger.info("sms_outbox_worker_started")
    while not stop_event.is_set():
        try:
            from ..core.telemetry import tracer
            from .sms.outbox_worker import process_pending_sms_outbound_jobs

            with tracer.start_as_current_span("process_pending_sms_outbound_jobs"):
                await process_pending_sms_outbound_jobs()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("sms_outbox_poll_failed")
        await _wait_for_next_poll(stop_event)

async def process_pending_outbox_events(
    db: Session = None,
    *,
    worker_id: str | None = None,
    clock: Callable[[], datetime] = _utcnow,
    jitter: Callable[[], float] | None = None,
    stop_event: asyncio.Event | None = None,
):
    """Claim and dispatch a bounded number of events without sharing ownership.

    Only registered domain webhooks are deliverable from this queue. Legacy
    generic provider action types are quarantined because those provider APIs
    cannot enforce the persisted idempotency key.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    try:
        owner = worker_id or f"worker:{uuid.uuid4()}"
        for _ in range(settings.OUTBOX_BATCH_SIZE):
            if stop_event is not None and stop_event.is_set():
                break
            event = claim_next_outbox_event(db, worker_id=owner, now=clock())
            if event is None:
                break
            try:
                payload = json.loads(event.payload)
                if not isinstance(payload, dict):
                    raise json.JSONDecodeError("payload is not an object", event.payload, 0)
                await _dispatch_claimed_event(db, event, payload)
                completed = _owned_update(
                    db,
                    event,
                    {
                        OutboxEvent.status: OUTBOX_STATUS_SUCCEEDED,
                        OutboxEvent.processed: True,
                        OutboxEvent.processed_at: clock(),
                        OutboxEvent.terminal_at: clock(),
                        OutboxEvent.error_code: None,
                        OutboxEvent.lease_owner: None,
                        OutboxEvent.lease_token: None,
                        OutboxEvent.lease_expires_at: None,
                    },
                )
                logger.info("outbox_event_processed" if completed else "outbox_lease_lost_after_delivery")
            except asyncio.CancelledError:
                db.rollback()
                # Keep the committed lease until expiry. Cancellation can race
                # a remote acknowledgement, so immediate release is unsafe.
                raise
            except (json.JSONDecodeError, UnicodeError):
                db.rollback()
                _quarantine_claimed_event(db, event, now=clock(), error_code=ERROR_PAYLOAD_INVALID)
                logger.warning("outbox_event_quarantined", extra={"error_code": ERROR_PAYLOAD_INVALID})
            except LookupError:
                db.rollback()
                _quarantine_claimed_event(db, event, now=clock(), error_code=ERROR_EVENT_TYPE_UNSUPPORTED)
                logger.warning("outbox_event_quarantined", extra={"error_code": ERROR_EVENT_TYPE_UNSUPPORTED})
            except PermanentOutboxError as exc:
                db.rollback()
                _quarantine_claimed_event(db, event, now=clock(), error_code=exc.error_code)
                logger.warning("outbox_event_quarantined", extra={"error_code": exc.error_code})
            except WebhookRoundIncomplete as exc:
                db.rollback()
                now = clock()
                if exc.terminal:
                    _dead_letter_claimed_event(db, event, now=now)
                elif exc.made_attempt:
                    retry_number = event.retry_count + 1
                    jitter_value = jitter() if jitter is not None else stable_retry_jitter(
                        event.idempotency_key, retry_number
                    )
                    _retry_claimed_event(
                        db,
                        event,
                        now=now,
                        error_code=ERROR_WEBHOOK_DELIVERY_FAILED,
                        jitter_value=jitter_value,
                        not_before=exc.next_attempt_at,
                    )
                else:
                    _defer_claimed_event(
                        db,
                        event,
                        next_attempt_at=exc.next_attempt_at or now,
                    )
                logger.warning("webhook_delivery_round_incomplete")
            except Exception as exc:
                db.rollback()
                code = ERROR_WEBHOOK_DELIVERY_FAILED if isinstance(exc, WebhookDeliveryError) else ERROR_PROVIDER_DELIVERY_FAILED
                retry_number = event.retry_count + 1
                jitter_value = jitter() if jitter is not None else stable_retry_jitter(
                    event.idempotency_key, retry_number
                )
                _retry_claimed_event(db, event, now=clock(), error_code=code, jitter_value=jitter_value)
                logger.error("outbox_event_delivery_failed", extra={"error_code": code})

    finally:
        if should_close:
            db.close()

def _claim_webhook_delivery(
    db: Session, delivery_id: int, *, worker_id: str = "worker:direct"
) -> WebhookDeliveryClaim | None:
    """Atomically lease one snapshotted destination across all workers."""
    now = datetime.now(timezone.utc)
    lease_token = str(uuid.uuid4())
    db.query(WebhookDelivery).filter(
        WebhookDelivery.status == "PROCESSING",
        WebhookDelivery.lease_expires_at < now,
        WebhookDelivery.attempt_count >= WebhookDelivery.max_attempts,
    ).update(
        {
            WebhookDelivery.status: "DEAD_LETTER",
            WebhookDelivery.error_code: ERROR_ATTEMPTS_EXHAUSTED,
            WebhookDelivery.terminal_at: now,
            WebhookDelivery.lease_owner: None,
            WebhookDelivery.lease_token: None,
            WebhookDelivery.lease_expires_at: None,
            WebhookDelivery.next_attempt_at: None,
        },
        synchronize_session=False,
    )
    db.commit()
    retryable = (
        ((WebhookDelivery.status == "PENDING") | (WebhookDelivery.status == "RETRY"))
        & (WebhookDelivery.attempt_count < WebhookDelivery.max_attempts)
        & ((WebhookDelivery.next_attempt_at.is_(None)) | (WebhookDelivery.next_attempt_at <= now))
    ) | (
        (WebhookDelivery.status == "PROCESSING")
        & (WebhookDelivery.lease_expires_at < now)
        & (WebhookDelivery.attempt_count < WebhookDelivery.max_attempts)
    )
    claimed = db.query(WebhookDelivery).filter(
        WebhookDelivery.id == delivery_id,
        retryable,
    ).update(
        {
            WebhookDelivery.status: "PROCESSING",
            WebhookDelivery.attempt_count: WebhookDelivery.attempt_count + 1,
            WebhookDelivery.lease_owner: worker_id,
            WebhookDelivery.lease_token: lease_token,
            WebhookDelivery.lease_expires_at: now + WEBHOOK_DELIVERY_LEASE,
            WebhookDelivery.next_attempt_at: None,
            WebhookDelivery.error_code: None,
        },
        synchronize_session=False,
    )
    if not claimed:
        db.rollback()
        return None
    row = db.query(
        WebhookDelivery.id,
        WebhookDelivery.target_url,
        WebhookDelivery.encrypted_signing_secret,
        WebhookDelivery.idempotency_key,
        WebhookDelivery.attempt_count,
        WebhookDelivery.max_attempts,
        WebhookDelivery.lease_owner,
        WebhookDelivery.lease_token,
        WebhookDelivery.lease_expires_at,
    ).filter(
        WebhookDelivery.id == delivery_id,
        WebhookDelivery.lease_token == lease_token,
    ).one()
    claim = WebhookDeliveryClaim(
        id=row.id,
        target_url=row.target_url,
        encrypted_signing_secret=row.encrypted_signing_secret,
        idempotency_key=row.idempotency_key,
        attempt_count=row.attempt_count,
        max_attempts=row.max_attempts,
        lease_owner=row.lease_owner,
        lease_token=row.lease_token,
        lease_expires_at=row.lease_expires_at,
    )
    db.commit()
    return claim


def _canonical_webhook_body(event: OutboxClaim, payload: dict) -> str:
    envelope = {
        "version": "v1",
        "event": {
            "id": event.id,
            "type": event.type,
            "tenant_id": event.tenant_id,
            "occurred_at": _aware(event.created_at).astimezone(timezone.utc).isoformat(),
        },
        "data": payload,
    }
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


async def dispatch_outbound_webhooks(
    db: Session,
    *,
    event: OutboxClaim,
    payload: dict,
) -> None:
    """Deliver immutable recipients created with the domain event."""
    deliveries = db.query(WebhookDelivery).filter(
        WebhookDelivery.outbox_event_id == event.id,
        WebhookDelivery.tenant_id == event.tenant_id,
    ).all()
    resolver = PublicAddressResolver()
    connector = aiohttp.TCPConnector(resolver=resolver, use_dns_cache=False, ssl=True)
    timeout = aiohttp.ClientTimeout(total=10.0)
    made_attempt = False
    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        trust_env=False,
    ) as client:
        for candidate in deliveries:
            delivery = _claim_webhook_delivery(
                db, candidate.id, worker_id=event.lease_owner or "worker:unknown"
            )
            if delivery is None:
                continue
            made_attempt = True
            delivery_lease_token = delivery.lease_token
            attempt_number = delivery.attempt_count

            try:
                stable_timestamp = _aware(event.created_at).astimezone(timezone.utc).isoformat()
                body = _canonical_webhook_body(event, payload)
                headers = {
                    "Content-Type": "application/json",
                    "X-Webhook-Version": "v1",
                    "X-Webhook-Event": event.type,
                    "X-Webhook-Event-Id": str(event.id),
                    "X-Webhook-Timestamp": stable_timestamp,
                    "X-Webhook-Delivery-Id": delivery.idempotency_key,
                    "Idempotency-Key": delivery.idempotency_key,
                }
                signing_secret = decrypt_webhook_secret(delivery.encrypted_signing_secret)
                sig = hmac.new(
                    signing_secret.encode("utf-8"),
                    body.encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
                headers["X-Webhook-Signature"] = f"v1={sig}"
                # Resolve and validate immediately before each connection to
                # reject destinations changed to internal addresses since
                # registration. Redirect following remains disabled above.
                validate_webhook_target_url(delivery.target_url)
                async with client.post(
                    delivery.target_url,
                    data=body,
                    headers=headers,
                    allow_redirects=False,
                ) as response:
                    if 300 <= response.status < 400:
                        raise WebhookDeliveryError("Webhook destination redirected the request")
                    response.raise_for_status()
                updated = db.query(WebhookDelivery).filter(
                    WebhookDelivery.id == delivery.id,
                    WebhookDelivery.status == "PROCESSING",
                    WebhookDelivery.lease_token == delivery_lease_token,
                ).update(
                    {
                        WebhookDelivery.status: "SUCCEEDED",
                        WebhookDelivery.delivered_at: datetime.now(timezone.utc),
                        WebhookDelivery.terminal_at: datetime.now(timezone.utc),
                        WebhookDelivery.error_code: None,
                        WebhookDelivery.lease_owner: None,
                        WebhookDelivery.lease_token: None,
                        WebhookDelivery.lease_expires_at: None,
                        WebhookDelivery.next_attempt_at: None,
                    },
                    synchronize_session=False,
                )
                db.commit()
                if updated != 1:
                    raise WebhookDeliveryError("Webhook delivery lease was lost")
            except asyncio.CancelledError:
                db.rollback()
                raise
            except Exception:
                db.rollback()
                db.query(WebhookDelivery).filter(
                    WebhookDelivery.id == delivery.id,
                    WebhookDelivery.status == "PROCESSING",
                    WebhookDelivery.lease_token == delivery_lease_token,
                ).update(
                    {
                        WebhookDelivery.status: "DEAD_LETTER" if attempt_number >= delivery.max_attempts else "RETRY",
                        WebhookDelivery.error_code: "WEBHOOK_DELIVERY_FAILED",
                        WebhookDelivery.terminal_at: datetime.now(timezone.utc) if attempt_number >= delivery.max_attempts else None,
                        WebhookDelivery.lease_owner: None,
                        WebhookDelivery.lease_token: None,
                        WebhookDelivery.lease_expires_at: None,
                        WebhookDelivery.next_attempt_at: None if attempt_number >= delivery.max_attempts else datetime.now(timezone.utc) + timedelta(
                            seconds=min(300, 2 ** min(attempt_number, 8)),
                        ),
                    },
                    synchronize_session=False,
                )
                db.commit()
                logger.error("webhook_delivery_failed")
                continue

    remaining = db.query(WebhookDelivery).filter(
        WebhookDelivery.outbox_event_id == event.id,
        WebhookDelivery.tenant_id == event.tenant_id,
        WebhookDelivery.status != "SUCCEEDED",
    ).all()
    if remaining:
        terminal = any(delivery.status == "DEAD_LETTER" for delivery in remaining)
        due_times = [
            candidate
            for delivery in remaining
            for candidate in (delivery.next_attempt_at, delivery.lease_expires_at)
            if candidate is not None
        ]
        raise WebhookRoundIncomplete(
            next_attempt_at=max(due_times) if due_times else None,
            made_attempt=made_attempt,
            terminal=terminal,
        )
