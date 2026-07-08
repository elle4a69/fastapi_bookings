import asyncio
import logging
import json
import hmac
import hashlib
import traceback
from datetime import datetime
import httpx
from sqlalchemy.orm import Session

from ..db.database import SessionLocal
from ..models.outbox import OutboxEvent
from ..models.webhook import WebhookRegistration
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
            await process_pending_outbox_events()
        except Exception as e:
            logger.error(f"Error in outbox processing loop: {str(e)}\n{traceback.format_exc()}")
        
        # Poll every 5 seconds
        await asyncio.sleep(5.0)

async def stop_outbox_worker(task: asyncio.Task):
    """Gracefully stop the outbox worker task."""
    global _worker_running
    logger.info("Stopping outbox worker background loop...")
    _worker_running = False
    try:
        await asyncio.wait_for(task, timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning("Outbox worker task shutdown timed out. Cancelling task.")
        task.cancel()
    except Exception as e:
        logger.error(f"Error during outbox worker shutdown: {str(e)}")

async def process_pending_outbox_events(db: Session = None):
    """Fetch and dispatch outstanding OutboxEvents."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    try:
        # Fetch pending or failed events with less than 5 retries
        events = db.query(OutboxEvent).filter(
            OutboxEvent.status.in_(["PENDING", "FAILED"]),
            OutboxEvent.retry_count < 5
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
                elif any(event.type.startswith(prefix) for prefix in ["booking.", "client.", "hold."]):
                    await dispatch_outbound_webhooks(db, event.type, payload)
                
                else:
                    logger.warning(f"Unknown outbox event type: {event.type}. Marking as processed.")

                # Success
                event.status = "PROCESSED"
                event.processed = True # legacy compatibility
                event.processed_at = datetime.utcnow()
                db.commit()
                logger.info(f"Successfully processed outbox event {event.id}")
                
            except Exception as ex:
                db.rollback()
                event.retry_count += 1
                event.status = "FAILED"
                event.error_log = f"{str(ex)}\n{traceback.format_exc()}"
                db.commit()
                logger.error(f"Failed to process outbox event {event.id} (attempt {event.retry_count}): {str(ex)}")

    finally:
        if should_close:
            db.close()

async def dispatch_outbound_webhooks(db: Session, event_type: str, payload: dict):
    """Find active webhook registrations for the event and dispatch POST requests."""
    webhooks = db.query(WebhookRegistration).filter(
        WebhookRegistration.event == event_type,
        WebhookRegistration.is_active == True
    ).all()
    
    if not webhooks:
        return

    body = json.dumps(payload)
    
    async with httpx.AsyncClient() as client:
        for hook in webhooks:
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Event": event_type
            }
            # HMAC-SHA256 signature if secret is registered
            if hook.secret:
                sig = hmac.new(hook.secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest()
                headers["X-Webhook-Signature"] = sig

            try:
                logger.info(f"Dispatching webhook event {event_type} to {hook.target_url}")
                response = await client.post(hook.target_url, content=body, headers=headers, timeout=10.0)
                response.raise_for_status()
            except Exception as ex:
                logger.error(f"Webhook dispatch to {hook.target_url} failed: {str(ex)}")
                raise
