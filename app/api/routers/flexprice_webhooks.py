"""Flexprice billing webhook endpoint for incoming provider events."""

import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.platform_billing import WebhookIngestResponse
from app.services.platform_billing.webhook_verifier import webhook_verifier
from app.services.platform_billing.projection_service import projection_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/flexprice", tags=["billing-webhooks"])


@router.post("", response_model=WebhookIngestResponse, status_code=status.HTTP_200_OK)
@router.post("/", response_model=WebhookIngestResponse, status_code=status.HTTP_200_OK, include_in_schema=False)
async def receive_flexprice_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_flexprice_signature: Optional[str] = Header(None, alias="X-Flexprice-Signature"),
) -> WebhookIngestResponse:
    """Receive and verify raw-body webhook notifications from Flexprice.

    Guarantees:
    - Cryptographic HMAC-SHA256 signature verification over exact raw request body.
    - SHA-256 digest hashing before database insertion (no secrets/PII stored).
    - Idempotent inbox deduplication: duplicate events are recorded and returned safely.
    - Out-of-order event resilience: stale events cannot overwrite current subscription projections.
    """
    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty webhook request body",
        )

    # 1. Verify HMAC Signature
    is_valid = webhook_verifier.verify_signature(
        raw_body=raw_body,
        signature_header=x_flexprice_signature,
    )
    if not is_valid:
        logger.warning("Rejected Flexprice webhook: signature mismatch or missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # 2. Parse JSON payload
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        logger.warning("Rejected Flexprice webhook: invalid JSON (%s)", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    # 3. Extract event ID and type
    event_id = str(payload.get("event_id") or payload.get("id") or "")
    if not event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing event_id in webhook payload",
        )
    event_type = str(payload.get("event_type") or payload.get("type") or "subscription.updated")

    # 4. Atomically record in ProviderEventInbox (idempotent)
    inbox_event, is_new = projection_service.record_inbox_event(
        db=db,
        external_event_id=event_id,
        event_type=event_type,
        raw_body=raw_body,
        verified=True,
    )

    if not is_new and inbox_event.processing_status == "processed":
        return WebhookIngestResponse(
            status="success",
            event_id=event_id,
            message="Event previously received and processed",
            action_taken="deduplicated",
        )

    # 5. Process subscription event projection
    result = projection_service.process_subscription_event(
        db=db,
        inbox_event=inbox_event,
        event_data=payload,
    )

    action = result.get("status", "processed")
    return WebhookIngestResponse(
        status="success",
        event_id=event_id,
        message=f"Event processed with result: {action}",
        action_taken=action,
    )
