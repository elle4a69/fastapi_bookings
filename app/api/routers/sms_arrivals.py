import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db
from ...models.tenant import Tenant
from ...models.user import User
from ...models.sms_arrival import SmsArrivalSession
from ...models.sms_outbox import SmsConversationEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sms/arrivals", tags=["sms-arrivals"])

@router.post("/public/{token}/arrive", status_code=status.HTTP_200_OK)
async def client_arrive(
    token: str,
    db: Session = Depends(get_db)
):
    """Public endpoint for customer self-arrival confirmation."""
    arrival = db.query(SmsArrivalSession).filter(SmsArrivalSession.token == token).first()
    if not arrival:
        raise HTTPException(status_code=404, detail="Arrival session token is invalid or expired.")

    # Idempotent arrival marking
    if not arrival.arrived_at:
        arrival.arrived_at = datetime.now(timezone.utc)
        
        # Log event in the conversation
        event = SmsConversationEvent(
            conversation_id=arrival.conversation_id,
            type="customer_arrived",
            meta={"booking_id": arrival.booking_id}
        )
        db.add(event)
        db.commit()
        logger.info(f"Customer self-arrival registered for booking_id={arrival.booking_id}")
        
    return {"status": "success", "booking_id": arrival.booking_id, "arrived_at": arrival.arrived_at}

@router.post("/{arrival_id}/acknowledge", status_code=status.HTTP_200_OK)
async def acknowledge_arrival(
    arrival_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    _admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin endpoint to acknowledge client arrival and stop notifications."""
    arrival = db.query(SmsArrivalSession).filter(SmsArrivalSession.id == arrival_id).first()
    if not arrival:
        raise HTTPException(status_code=404, detail="Arrival session not found.")

    arrival.acknowledged_at = datetime.now(timezone.utc)
    
    # Log event
    event = SmsConversationEvent(
        conversation_id=arrival.conversation_id,
        type="arrival_acknowledged",
        meta={"booking_id": arrival.booking_id}
    )
    db.add(event)
    db.commit()
    
    return {"status": "success", "acknowledged_at": arrival.acknowledged_at}
