import json
from sqlalchemy.orm import Session
from ..models.outbox import OutboxEvent

def create_outbox_event(db: Session, event_type: str, payload: dict, tenant_id: str = None) -> OutboxEvent:
    """Helper function to enqueue an outbox event."""
    event = OutboxEvent(
        tenant_id=tenant_id,
        type=event_type,
        payload=json.dumps(payload),
        status="PENDING",
        processed=False
    )
    db.add(event)
    return event
