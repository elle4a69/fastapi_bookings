from __future__ import annotations

import logging
from typing import Optional
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_db
from ...core.config import settings
from ...services.payment_service import payment_service

logger = logging.getLogger(__name__)


class WebhookAckResponse(BaseModel):
    ok: bool


router = APIRouter(prefix="/api/v1", tags=["stripe"])


@router.post("/checkout/deposit-session")
def create_deposit_session(
    booking_id: int,
    success_url: str,
    cancel_url: str,
    amount_cents: Optional[int] = None,
    tenant_id: Optional[int] = None,
    db: Session = Depends(get_db)
) -> dict:
    """Create a Stripe Checkout Session for a booking deposit with server-authoritative pricing."""
    result = payment_service.create_deposit_checkout_session(
        db=db,
        booking_id=booking_id,
        success_url=success_url,
        cancel_url=cancel_url,
        tenant_id=tenant_id,
        client_amount_cents=amount_cents,
    )
    return {"ok": True, "data": result}


@router.post("/webhooks/stripe", response_model=WebhookAckResponse)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe Webhook endpoint.

    Fails closed (HTTP 503) if webhook secret is unconfigured.
    Requires and verifies Stripe-Signature header (HTTP 400 on failure).
    Reconciles booking state transitions idempotently and atomically.
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET is not configured. Failing closed.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook secret is not configured"
        )

    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        logger.error("Missing Stripe-Signature header.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header"
        )

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook verification failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Webhook verification failed: {str(e)}")

    payment_service.process_stripe_webhook(db, event)
    return WebhookAckResponse(ok=True)

