import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from ..core.config import settings
from ..models.outbox import OutboxEvent
from ..models.webhook import WebhookDelivery, WebhookRegistration, encrypt_webhook_secret

logger = logging.getLogger(__name__)

def create_outbox_event(db: Session, event_type: str, payload: dict, tenant_id: Optional[int] = None) -> OutboxEvent:
    """Helper function to enqueue an outbox event."""
    enqueued_at = datetime.now(timezone.utc)
    event = OutboxEvent(
        tenant_id=tenant_id,
        type=event_type,
        payload=json.dumps(payload),
        status="PENDING",
        processed=False,
        idempotency_key=f"outbox:{uuid.uuid4()}",
        max_attempts=settings.OUTBOX_MAX_RETRIES,
        created_at=enqueued_at,
        next_attempt_at=enqueued_at,
    )
    db.add(event)
    if tenant_id is not None and event_type.startswith(("booking.", "client.")):
        db.flush()
        hooks = db.query(WebhookRegistration).filter(
            WebhookRegistration.tenant_id == tenant_id,
            WebhookRegistration.event == event_type,
            WebhookRegistration.is_active.is_(True),
        ).all()
        for hook in hooks:
            if not hook.secret or not hook.secret.strip():
                # Legacy registrations may predate the mandatory write-only
                # secret contract.  They are deterministically skipped rather
                # than failing the domain transaction or sending unsigned.
                logger.warning("webhook_registration_skipped_unsigned")
                continue
            db.add(WebhookDelivery(
                outbox_event_id=event.id,
                webhook_id=hook.id,
                tenant_id=tenant_id,
                target_url=hook.target_url,
                encrypted_signing_secret=encrypt_webhook_secret(hook.secret),
                idempotency_key=f"webhook:{event.id}:{hook.id}",
                status="PENDING",
                max_attempts=settings.OUTBOX_MAX_RETRIES,
                next_attempt_at=enqueued_at,
            ))
        event.webhook_snapshot_at = datetime.now(timezone.utc)
    return event
