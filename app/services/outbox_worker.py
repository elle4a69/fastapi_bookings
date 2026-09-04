import asyncio
import logging
import json
import hmac
import hashlib
import traceback
import ipaddress
import socket
import uuid
from datetime import datetime, timedelta, timezone
import aiohttp
from aiohttp.abc import AbstractResolver
from sqlalchemy.orm import Session

from ..db.database import SessionLocal
from ..core.config import settings
from ..models.outbox import OutboxEvent
from ..models.webhook import WebhookDelivery, decrypt_webhook_secret
from ..schemas.webhook import validate_webhook_target_url
from .clicksend import clicksend_client
from .chatwoot import chatwoot_client
from .fcm import fcm_client

logger = logging.getLogger(__name__)

# Control flag for background worker task loop
_worker_running = True
WEBHOOK_DELIVERY_LEASE = timedelta(minutes=2)


class WebhookDeliveryError(Exception):
    """Safe error used to retry an outbox event without leaking webhook data."""


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

async def start_outbox_worker():
    """Start the outbox processing loop."""
    global _worker_running
    _worker_running = True
    logger.info("Outbox worker background loop starting...")
    
    while _worker_running:
        try:
            from ..core.telemetry import tracer
            with tracer.start_as_current_span("process_pending_outbox_events"):
                await process_pending_outbox_events()
        except Exception as e:
            logger.error(f"Error in outbox processing loop: {str(e)}\n{traceback.format_exc()}")
            
        try:
            from ..core.telemetry import tracer
            with tracer.start_as_current_span("process_pending_sms_outbound_jobs"):
                from .sms.outbox_worker import process_pending_sms_outbound_jobs
                await process_pending_sms_outbound_jobs()
        except Exception as e:
            logger.error(f"Error in SMS outbound processing loop: {str(e)}\n{traceback.format_exc()}")
        
        # Poll every settings.OUTBOX_POLL_INTERVAL seconds
        await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL)

async def stop_outbox_worker(task: asyncio.Task):
    """Gracefully stop the outbox worker task."""
    global _worker_running
    logger.info("Stopping outbox worker background loop...")
    _worker_running = False
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

async def process_pending_outbox_events(db: Session = None):
    """Fetch and dispatch outstanding OutboxEvents."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    try:
        # Fetch pending or failed events with less than settings.OUTBOX_MAX_RETRIES retries
        events = db.query(OutboxEvent).filter(
            OutboxEvent.status.in_(["PENDING", "FAILED"]),
            OutboxEvent.retry_count < settings.OUTBOX_MAX_RETRIES
        ).order_by(OutboxEvent.created_at.asc()).limit(20).all()
        
        if not events:
            return

        for event in events:
            logger.info(f"Processing outbox event {event.id} ({event.type})...")
            try:
                # Parse payload
                payload = json.loads(event.payload)
                
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
                
                # If it's a domain webhook event (e.g. booking.created, booking.confirmed)
                elif any(event.type.startswith(prefix) for prefix in ["booking.", "client."]):
                    # Tenant-less historical domain events cannot be safely
                    # delivered: selecting a registration without a tenant
                    # would cross the tenant boundary.
                    if event.tenant_id is None:
                        event.status = "QUARANTINED"
                        event.processed = True
                        event.processed_at = datetime.now(timezone.utc)
                        event.error_log = "WEBHOOK_TENANT_CONTEXT_MISSING"
                        db.commit()
                        logger.warning("Quarantined tenant-less outbox event id=%s type=%s", event.id, event.type)
                        continue
                    if event.webhook_snapshot_at is None:
                        event.status = "QUARANTINED"
                        event.processed = True
                        event.processed_at = datetime.now(timezone.utc)
                        event.error_log = "WEBHOOK_SNAPSHOT_MISSING"
                        db.commit()
                        logger.warning("Quarantined unsnapshotted outbox event id=%s type=%s", event.id, event.type)
                        continue
                    await dispatch_outbound_webhooks(
                        db,
                        event=event,
                        payload=payload,
                    )
                
                else:
                    logger.warning(f"Unknown outbox event type: {event.type}. Marking as processed.")

                # Success
                event.status = "PROCESSED"
                event.processed = True # legacy compatibility
                event.processed_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"Successfully processed outbox event {event.id}")
                
            except Exception as ex:
                db.rollback()
                event.retry_count += 1
                event.status = "FAILED"
                # Error messages and tracebacks can contain remote URLs,
                # request material, or provider responses. Persist a safe,
                # non-sensitive diagnostic instead.
                event.error_log = "Delivery failed; inspect safe operational telemetry."
                db.commit()
                logger.error("Failed to process outbox event id=%s attempt=%s", event.id, event.retry_count)

    finally:
        if should_close:
            db.close()

def _claim_webhook_delivery(db: Session, delivery_id: int) -> WebhookDelivery | None:
    """Atomically lease one snapshotted destination across all workers."""
    now = datetime.now(timezone.utc)
    lease_token = str(uuid.uuid4())
    retryable = (
        ((WebhookDelivery.status == "PENDING") | (WebhookDelivery.status == "FAILED"))
        & ((WebhookDelivery.next_attempt_at.is_(None)) | (WebhookDelivery.next_attempt_at <= now))
    ) | (
        (WebhookDelivery.status == "DISPATCHING")
        & (WebhookDelivery.lease_expires_at < now)
    )
    claimed = db.query(WebhookDelivery).filter(
        WebhookDelivery.id == delivery_id,
        retryable,
    ).update(
        {
            WebhookDelivery.status: "DISPATCHING",
            WebhookDelivery.attempt_count: WebhookDelivery.attempt_count + 1,
            WebhookDelivery.lease_token: lease_token,
            WebhookDelivery.lease_expires_at: now + WEBHOOK_DELIVERY_LEASE,
            WebhookDelivery.next_attempt_at: None,
            WebhookDelivery.error_code: None,
        },
        synchronize_session=False,
    )
    if not claimed:
        return None
    db.flush()
    return db.query(WebhookDelivery).filter(
        WebhookDelivery.id == delivery_id,
        WebhookDelivery.lease_token == lease_token,
    ).first()


def _canonical_webhook_body(event: OutboxEvent, payload: dict, sent_at: datetime) -> str:
    envelope = {
        "version": "v1",
        "event": {
            "id": event.id,
            "type": event.type,
            "tenant_id": event.tenant_id,
            "occurred_at": event.created_at.astimezone(timezone.utc).isoformat(),
        },
        "sent_at": sent_at.astimezone(timezone.utc).isoformat(),
        "data": payload,
    }
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


async def dispatch_outbound_webhooks(
    db: Session,
    *,
    event: OutboxEvent,
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
    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        trust_env=False,
    ) as client:
        for candidate in deliveries:
            delivery = _claim_webhook_delivery(db, candidate.id)
            if delivery is None:
                continue
            sent_at = datetime.now(timezone.utc)
            body = _canonical_webhook_body(event, payload, sent_at)
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Version": "v1",
                "X-Webhook-Event": event.type,
                "X-Webhook-Event-Id": str(event.id),
                "X-Webhook-Timestamp": sent_at.isoformat(),
            }
            signing_secret = decrypt_webhook_secret(delivery.encrypted_signing_secret)
            sig = hmac.new(signing_secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest()
            headers["X-Webhook-Signature"] = f"v1={sig}"

            try:
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
                delivery.status = "PROCESSED"
                delivery.delivered_at = datetime.now(timezone.utc)
                delivery.error_code = None
                delivery.lease_token = None
                delivery.lease_expires_at = None
                db.flush()
            except Exception:
                delivery.status = "FAILED"
                delivery.error_code = "WEBHOOK_DELIVERY_FAILED"
                delivery.lease_token = None
                delivery.lease_expires_at = None
                delivery.next_attempt_at = datetime.now(timezone.utc) + timedelta(
                    seconds=min(300, 2 ** min(delivery.attempt_count, 8)),
                )
                # The caller records the outbox retry after catching this
                # exception.  Persist the destination-specific retry state
                # first so that its rollback cannot erase the lease outcome.
                db.commit()
                logger.error("Webhook delivery failed for event id=%s delivery id=%s", event.id, delivery.id)
                raise WebhookDeliveryError("Webhook delivery failed")
