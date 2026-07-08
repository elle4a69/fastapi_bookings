import json
import logging
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..deps import get_db
from ...core.config import settings
from ...core.state_machine import BookingStatus, is_valid_transition
from ...models.booking import Booking as BookingModel
from ...services.outbox_service import create_outbox_event
from ...services.stripe_service import stripe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["stripe"])

@router.post("/checkout/deposit-session")
def create_deposit_session(
    booking_id: int,
    amount_cents: int,
    success_url: str,
    cancel_url: str,
    db: Session = Depends(get_db)
) -> dict:
    """Create a Stripe Checkout Session for a booking deposit."""
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    session = stripe_service.create_checkout_session(
        booking_id=booking.id,
        amount_cents=amount_cents,
        success_url=success_url,
        cancel_url=cancel_url
    )
    return {"ok": True, "data": {"session_id": session.id, "url": session.url}}

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe Webhook endpoint."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        if not settings.STRIPE_WEBHOOK_SECRET:
            logger.warning("STRIPE_WEBHOOK_SECRET not configured. Signature verification bypassed!")
            event = json.loads(payload)
        else:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
    except ValueError as e:
        logger.error(f"Invalid payload: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    logger.info(f"Received Stripe webhook event: {event_type}")

    if event_type == "checkout.session.completed":
        metadata = data_object.get("metadata", {})
        booking_id_str = metadata.get("booking_id")
        tenant_id = metadata.get("tenant_id")
        
        if booking_id_str:
            booking_id = int(booking_id_str)
            booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
            if booking:
                logger.info(f"Stripe deposit payment completed for Booking {booking_id}. Confirming booking.")
                if is_valid_transition(booking.status, BookingStatus.CONFIRMED):
                    booking.status = BookingStatus.CONFIRMED
                    
                    # Notify customer via ClickSend SMS
                    sms_payload = {
                        "to": booking.client.phone if booking.client and booking.client.phone else "+61411111111",
                        "body": f"Hi {booking.client.name if booking.client else 'Customer'}, your deposit has been received and booking #{booking.id} is now CONFIRMED!"
                    }
                    create_outbox_event(db, "SEND_SMS", sms_payload, tenant_id=tenant_id)
                    
                    # Outbox event for the confirmed state
                    booking_payload = {
                        "id": booking.id,
                        "client_id": booking.client_id,
                        "provider_id": booking.provider_id,
                        "service_id": booking.service_id,
                        "status": booking.status
                    }
                    create_outbox_event(db, "booking.confirmed", booking_payload, tenant_id=tenant_id)
                    db.commit()
                else:
                    logger.warning(f"Booking {booking_id} status transition from {booking.status} to CONFIRMED is invalid.")

    elif event_type in ["invoice.payment_failed", "charge.failed"]:
        metadata = data_object.get("metadata", {})
        booking_id_str = metadata.get("booking_id")
        tenant_id = metadata.get("tenant_id")
        
        if booking_id_str:
            booking_id = int(booking_id_str)
            booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
            if booking:
                logger.info(f"Stripe payment failed for Booking {booking_id}. Cancelling booking.")
                if is_valid_transition(booking.status, BookingStatus.CANCELLED):
                    booking.status = BookingStatus.CANCELLED
                    
                    # Notify customer
                    sms_payload = {
                        "to": booking.client.phone if booking.client and booking.client.phone else "+61411111111",
                        "body": f"Hi {booking.client.name if booking.client else 'Customer'}, your deposit payment for booking #{booking.id} failed. The booking has been cancelled."
                    }
                    create_outbox_event(db, "SEND_SMS", sms_payload, tenant_id=tenant_id)
                    
                    booking_payload = {
                        "id": booking.id,
                        "client_id": booking.client_id,
                        "status": booking.status
                    }
                    create_outbox_event(db, "booking.cancelled", booking_payload, tenant_id=tenant_id)
                    db.commit()

    return {"ok": True}
