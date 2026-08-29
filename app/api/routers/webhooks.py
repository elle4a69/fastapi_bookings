"""Webhook registration CRUD routes.

Administrators register outbound webhook endpoints here. When a
booking event fires (e.g. booking.created, booking.confirmed) the
outbox worker will POST to each active webhook whose event field
matches and belongs to the same tenant. The optional secret is used
to sign the payload body with HMAC-SHA256 so the receiving server can
verify the request.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db, DatabaseId
from ...models.webhook import WebhookRegistration
from ...schemas.webhook import (
    WebhookCreate,
    WebhookCreateResponse,
    WebhookListResponse,
    WebhookOut,
    WebhookResponse,
    WebhookUpdate,
)

router = APIRouter(prefix="/api/admin/webhooks", tags=["webhooks"])

SUPPORTED_EVENTS = {
    "booking.created",
    "booking.confirmed",
    "booking.cancelled",
    "booking.completed",
    "booking.rescheduled",
    "booking.no_show",
    "client.created",
}


@router.get("", response_model=WebhookListResponse)
def list_webhooks(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> dict:
    """Return all registered webhooks for the authenticated tenant."""
    hooks = (
        db.query(WebhookRegistration)
        .filter(WebhookRegistration.tenant_id == current_user.tenant_id)
        .order_by(WebhookRegistration.id)
        .all()
    )
    return {"ok": True, "data": hooks}


@router.get("/{webhook_id}", response_model=WebhookResponse)
def get_webhook(
    webhook_id: DatabaseId,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> dict:
    """Retrieve a single webhook registration scoped to the authenticated tenant."""
    hook = (
        db.query(WebhookRegistration)
        .filter(
            WebhookRegistration.id == webhook_id,
            WebhookRegistration.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"ok": True, "data": hook}


@router.post("", response_model=WebhookCreateResponse, status_code=status.HTTP_201_CREATED)
def create_webhook(
    webhook_in: WebhookCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> dict:
    """Register a new outbound webhook endpoint for the authenticated tenant."""
    if webhook_in.event not in SUPPORTED_EVENTS:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "UNKNOWN_EVENT", "message": f"Unsupported event. Choose from: {sorted(SUPPORTED_EVENTS)}"},
        )
    hook = WebhookRegistration(tenant_id=current_user.tenant_id, **webhook_in.model_dump())
    db.add(hook)
    db.commit()
    db.refresh(hook)
    return {"ok": True, "data": hook}


@router.put("/{webhook_id}", response_model=WebhookResponse)
def update_webhook(
    webhook_id: DatabaseId,
    webhook_in: WebhookUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> dict:
    """Update a webhook registration for the authenticated tenant."""
    hook = (
        db.query(WebhookRegistration)
        .filter(
            WebhookRegistration.id == webhook_id,
            WebhookRegistration.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if webhook_in.event is not None and webhook_in.event not in SUPPORTED_EVENTS:
        raise HTTPException(status_code=400, detail={"error_code": "UNKNOWN_EVENT", "message": "Unsupported event"})
    for field, value in webhook_in.model_dump(exclude_unset=True).items():
        setattr(hook, field, value)
    db.commit()
    db.refresh(hook)
    return {"ok": True, "data": hook}


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_webhook(
    webhook_id: DatabaseId,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> None:
    """Delete a webhook registration for the authenticated tenant."""
    hook = (
        db.query(WebhookRegistration)
        .filter(
            WebhookRegistration.id == webhook_id,
            WebhookRegistration.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    db.delete(hook)
    db.commit()


@router.get("/events", tags=["webhooks"])
def list_supported_events(_admin=Depends(get_current_admin)) -> dict:
    """Return the list of event types available for webhook subscription."""
    return {"ok": True, "data": sorted(SUPPORTED_EVENTS)}

