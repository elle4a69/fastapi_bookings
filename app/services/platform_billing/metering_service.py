"""Usage metering service for recording and dispatching consumption events."""

from datetime import datetime, timezone
import logging
from typing import List, Optional
import uuid
from sqlalchemy.orm import Session

from app.models.platform_billing import UsageEventOutbox
from app.services.platform_billing.flexprice_client import FlexpriceClient, flexprice_client

logger = logging.getLogger(__name__)


class UsageMeteringService:
    """Records metered usage and dispatches batches to external billing provider."""

    @classmethod
    def record_usage(
        cls,
        db: Session,
        tenant_id: int,
        meter_key: str,
        quantity: int = 1,
        idempotency_key: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
    ) -> UsageEventOutbox:
        """Record a metered usage event in the outbox with idempotency guarantees.

        Args:
            db: Database session.
            tenant_id: Internal tenant ID incurring the usage.
            meter_key: Meter identifier (e.g. 'sms_outbound', 'ai_tokens').
            quantity: Units consumed.
            idempotency_key: Unique key. If None, a unique UUID key is generated.
            occurred_at: Occurrence timestamp. Defaults to UTC now.

        Returns:
            The created or pre-existing UsageEventOutbox record.
        """
        key = idempotency_key or f"usage:{tenant_id}:{meter_key}:{uuid.uuid4()}"

        existing = (
            db.query(UsageEventOutbox)
            .filter(UsageEventOutbox.idempotency_key == key)
            .first()
        )
        if existing:
            logger.info("Duplicate usage record detected with idempotency_key=%s", key)
            return existing

        now = datetime.now(timezone.utc)
        record = UsageEventOutbox(
            tenant_id=tenant_id,
            idempotency_key=key,
            meter_key=meter_key,
            quantity=quantity,
            occurred_at=occurred_at or now,
            delivery_state="pending",
            retry_count=0,
            created_at=now,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @classmethod
    def dispatch_pending_usage(
        cls,
        db: Session,
        client: Optional[FlexpriceClient] = None,
        batch_size: int = 50,
    ) -> int:
        """Dispatch a batch of pending usage events to Flexprice.

        Args:
            db: Database session.
            client: FlexpriceClient instance. Defaults to singleton.
            batch_size: Maximum records per batch.

        Returns:
            Number of successfully dispatched records.
        """
        api_client = client or flexprice_client
        pending_events: List[UsageEventOutbox] = (
            db.query(UsageEventOutbox)
            .filter(UsageEventOutbox.delivery_state == "pending")
            .order_by(UsageEventOutbox.id.asc())
            .limit(batch_size)
            .all()
        )

        if not pending_events:
            return 0

        batch_payload = [
            {
                "event_id": event.idempotency_key,
                "external_customer_id": f"tenant_{event.tenant_id}",
                "event_name": event.meter_key,
                "properties": {"quantity": event.quantity},
                "timestamp": event.occurred_at.isoformat(),
            }
            for event in pending_events
        ]

        try:
            api_client.send_usage_events(batch_payload)
            now = datetime.now(timezone.utc)
            for event in pending_events:
                event.delivery_state = "delivered"
                event.delivered_at = now
            db.commit()
            return len(pending_events)
        except Exception as exc:
            logger.error("Failed to dispatch usage events batch: %s", exc)
            for event in pending_events:
                event.retry_count += 1
                if event.retry_count >= 5:
                    event.delivery_state = "failed"
            db.commit()
            raise


usage_metering_service = UsageMeteringService()
