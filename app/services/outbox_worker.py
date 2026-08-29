import asyncio
import logging
import json
import hmac
import hashlib
import traceback
from datetime import datetime, timezone
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
            logger.error(f"Error in outbox processing loop: {type(e).__name__}")
            
        try:
            from ..core.telemetry import tracer
            with tracer.start_as_current_span("process_pending_sms_outbound_jobs"):
                from .sms.outbox_worker import process_pending_sms_outbound_jobs
                await process_pending_sms_outbound_jobs()
        except Exception as e:
            logger.error(f"Error in SMS outbound processing loop: {type(e).__name__}")
        
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
                payload = json.loads(event.payload) if isinstance(event.payload, str) else event.payload
                
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
                
                # If it's a domain webhook event (e.g. booking.created, booking.confirmed, client.created)
                elif any(event.type.startswith(prefix) for prefix in ["booking.", "client."]):
                    if not event.tenant_id:
                        logger.warning(f"Quarantined outbox event {event.id} ({event.type}): missing required tenant_id")
                        event.status = "QUARANTINED"
                        event.error_log = "Quarantined: Domain webhook event is missing required tenant_id"
                        db.commit()
                        continue
                    await dispatch_outbound_webhooks(db, event, payload)
                
                else:
                    logger.warning(f"Unknown outbox event type: {event.type}. Quarantining event {event.id}.")
                    event.status = "QUARANTINED"
                    event.error_log = f"Quarantined: Unknown outbox event type '{event.type}'"
                    db.commit()
                    continue

                # Success
                event.status = "PROCESSED"
                event.processed = True  # legacy compatibility
                event.processed_at = datetime.now(timezone.utc)
                event.error_log = None
                db.commit()
                logger.info(f"Successfully processed outbox event {event.id}")
                
            except Exception as ex:
                db.rollback()
                event.retry_count += 1
                event.status = "FAILED"
                event.error_log = f"Processing error: {type(ex).__name__} - {str(ex)[:200]}"
                db.commit()
                logger.error(f"Failed to process outbox event {event.id} (attempt {event.retry_count}): {type(ex).__name__}")

    finally:
        if should_close:
            db.close()

async def dispatch_outbound_webhooks(db: Session, event: OutboxEvent, payload: dict):
    """Find active webhook registrations for the event and tenant, and dispatch POST requests.
    
    Tracks per-destination delivery status in WebhookDelivery to guarantee idempotency
    and retry only failed destinations.
    """
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
            # Store privacy-safe error message without query strings, secrets, or payloads
            delivery.error_message = f"{type(ex).__name__}: {str(ex)[:200]}"
            db.commit()
            failed_count += 1
            logger.error(f"Webhook dispatch to webhook {hook.id} failed: {type(ex).__name__}")

    if failed_count > 0:
        raise RuntimeError(f"{failed_count} webhook destination(s) failed delivery for event {event.id}")

