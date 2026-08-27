import secrets
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ...models.sms_arrival import SmsArrivalSession
from ...models.sms_conversation import SmsConversation
from ...models.sms_outbox import SmsConversationEvent
from ...services.outbox_service import create_outbox_event

logger = logging.getLogger(__name__)

def create_arrival_session(
    db: Session,
    tenant_id: int,
    conversation_id: int,
    booking_id: int
) -> SmsArrivalSession:
    """Create a unique self-arrival session for a booking."""
    token = secrets.token_urlsafe(16)
    
    session = SmsArrivalSession(
        conversation_id=conversation_id,
        booking_id=booking_id,
        token=token,
        created_at=datetime.now(timezone.utc)
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    logger.info(f"Created arrival session token for booking_id={booking_id}")
    return session

def get_active_arrival_sessions(db: Session, tenant_id: int) -> list:
    """Return all arrived but unacknowledged arrival sessions for the dashboard."""
    return db.query(SmsArrivalSession).join(
        SmsConversation, SmsArrivalSession.conversation_id == SmsConversation.id
    ).filter(
        SmsConversation.tenant_id == tenant_id,
        SmsArrivalSession.arrived_at.isnot(None),
        SmsArrivalSession.acknowledged_at.is_(None)
    ).all()

def process_repeated_arrival_alerts(db: Session) -> None:
    """Find all active arrival sessions that have arrived but not acknowledged,
    and trigger a repeated notification alert if at least 60 seconds have elapsed
    since arrival (or since the last alert was triggered)."""
    now = datetime.now(timezone.utc)
    
    sessions = db.query(SmsArrivalSession).filter(
        SmsArrivalSession.arrived_at.isnot(None),
        SmsArrivalSession.acknowledged_at.is_(None)
    ).all()
    
    for session in sessions:
        arrived_at = session.arrived_at
        if arrived_at.tzinfo is None:
            arrived_at = arrived_at.replace(tzinfo=timezone.utc)
        
        elapsed_since_arrival = (now - arrived_at).total_seconds()
        
        # Search for the most recent SmsConversationEvent of type "arrival_alert_triggered"
        last_event = db.query(SmsConversationEvent).filter(
            SmsConversationEvent.conversation_id == session.conversation_id,
            SmsConversationEvent.type == "arrival_alert_triggered"
        ).order_by(SmsConversationEvent.created_at.desc()).first()
        
        should_trigger = False
        if last_event is None:
            if elapsed_since_arrival >= 60.0:
                should_trigger = True
        else:
            last_event_created_at = last_event.created_at
            if last_event_created_at.tzinfo is None:
                last_event_created_at = last_event_created_at.replace(tzinfo=timezone.utc)
            elapsed_since_last_event = (now - last_event_created_at).total_seconds()
            if elapsed_since_last_event >= 60.0:
                should_trigger = True
                
        if should_trigger:
            # 1. Create SmsConversationEvent of type "arrival_alert_triggered"
            event = SmsConversationEvent(
                conversation_id=session.conversation_id,
                type="arrival_alert_triggered",
                meta={
                    "booking_id": session.booking_id,
                    "arrived_at": arrived_at.isoformat(),
                    "triggered_at": now.isoformat()
                }
            )
            db.add(event)
            
            # 2. Call create_outbox_event
            payload = {
                "booking_id": session.booking_id,
                "conversation_id": session.conversation_id,
                "arrived_at": arrived_at.isoformat(),
                "token": session.token
            }
            tenant_id = None
            if session.conversation:
                tenant_id = session.conversation.tenant_id
            
            create_outbox_event(db, "arrival.alert", payload, tenant_id=tenant_id)
            db.commit()
            logger.info(f"Triggered repeated arrival alert for booking_id={session.booking_id}")

