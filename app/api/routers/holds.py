"""Holds API routes.

These endpoints allow clients to temporarily reserve a slot while
completing the booking form.  Holds prevent double‑booking by
ensuring that other clients cannot book the same slot until the hold
expires or is confirmed/cancelled.  Only public (unauthenticated)
token is required to create and manage holds.  Admin endpoints may
list and manage holds for administrative purposes.
"""

from datetime import datetime
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models import Service, Provider, Location, Hold, HoldStatus, Booking, Client
from ...schemas.hold import HoldCreate, HoldOut, HoldConfirm
from ...services import scheduling_service
# ServiceProvider is not used here but retained for future extensions.
from ...core.state_machine import BookingStatus

router = APIRouter(prefix="/api/public/holds", tags=["holds"])


@router.post("", response_model=HoldOut)
def create_hold_endpoint(
    payload: HoldCreate,
    db: Session = Depends(get_db),
) -> HoldOut:
    """Create a new hold for a slot.

    The caller provides the service, start/end times and optional
    provider, location and client identifiers.  A hold expires after
    the provided ``expires_at`` timestamp.
    """
    service = db.query(Service).filter(Service.id == payload.service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    provider = None
    if payload.provider_id:
        provider = db.query(Provider).filter(Provider.id == payload.provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
    location = None
    if payload.location_id:
        location = db.query(Location).filter(Location.id == payload.location_id).first()
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")
    hold = scheduling_service.create_hold(
        db,
        service=service,
        client_id=payload.client_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        provider=provider,
        location=location,
        expires_in=int((payload.expires_at - datetime.utcnow()).total_seconds() / 60),
    )
    return HoldOut.from_orm(hold)


@router.post("/{hold_id}/confirm", response_model=Any)
def confirm_hold_endpoint(
    hold_id: int = Path(..., description="ID of the hold to confirm"),
    payload: HoldConfirm | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Convert a hold into a booking and allocate resources.

    This endpoint creates a new booking using the details recorded
    within the hold.  The booking is initially created with status
    ``pending``.  Resources are allocated via the scheduling service.  If
    allocation fails, the hold remains pending and an HTTP error is
    raised.  On success, the hold is marked as confirmed.

    Args:
        hold_id: Identifier of the hold to confirm.
        payload: Optional payload containing client or additional
            information (unused in this simplified implementation).
        db: Injected database session.

    Returns:
        The newly created booking as a serialisable Pydantic model.
    """
    hold = db.query(Hold).filter(Hold.id == hold_id).first()
    if not hold:
        raise HTTPException(status_code=404, detail="Hold not found")
    if hold.status != HoldStatus.PENDING:
        raise HTTPException(status_code=400, detail="Hold cannot be confirmed")
    # Resolve service and provider
    service = hold.service
    provider = hold.provider
    location = hold.location
    # If no provider was specified in the hold, choose the first eligible provider
    if provider is None:
        # Determine eligible providers via service-provider assignments
        if service.providers:
            provider = service.providers[0].provider
        else:
            # Fallback to any provider active
            provider = db.query(Provider).filter(Provider.active.is_(True)).first()
            if not provider:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No provider available for this service")
    # Ensure a client exists for the booking.  A hold may be created without a
    # client_id (e.g. anonymous hold).  In that case try to create or
    # look up a client using provided client_details.  If no client
    # information is available raise an error.
    client_id = hold.client_id
    # If hold has no client and payload provides client_details, create a new client
    if client_id is None:
        details = payload.client_details if payload else None
        if details:
            name = details.get("name") if isinstance(details, dict) else None
            email = details.get("email") if isinstance(details, dict) else None
            phone = details.get("phone") if isinstance(details, dict) else None
            # Attempt to find an existing client by email or phone
            client_obj = None
            if email:
                client_obj = db.query(Client).filter(
                    Client.email == email,
                    Client.tenant_id == hold.tenant_id
                ).first()
            if not client_obj and phone:
                client_obj = db.query(Client).filter(
                    Client.phone == phone,
                    Client.tenant_id == hold.tenant_id
                ).first()
            if client_obj is None:
                client_obj = Client(tenant_id=hold.tenant_id, name=name, email=email, phone=phone)
                db.add(client_obj)
                db.commit()
                db.refresh(client_obj)
            client_id = client_obj.id
            # Update the hold's client_id to reflect this new or existing client
            hold.client_id = client_id
            db.commit()
            db.refresh(hold)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client information is required to confirm this hold",
            )
    # Build booking data
    booking = Booking(
        tenant_id=hold.tenant_id,
        client_id=client_id,
        provider_id=provider.id,
        service_id=service.id,
        location_id=location.id if location else None,
        start_time=hold.start_time,
        end_time=hold.end_time,
        status=BookingStatus.PENDING,
    )
    # Persist booking
    db.add(booking)
    db.commit()
    db.refresh(booking)
    # Allocate resources
    try:
        scheduling_service.allocate_resources(db, booking=booking, commit=True)
    except HTTPException as exc:
        # Clean up the created booking if allocation fails
        db.delete(booking)
        db.commit()
        raise exc
    # Mark hold as confirmed
    hold.status = HoldStatus.CONFIRMED
    db.commit()
    db.refresh(hold)
    return {"ok": True, "data": booking}


@router.delete("/{hold_id}", response_model=HoldOut)
def cancel_hold_endpoint(
    hold_id: int = Path(..., description="ID of the hold to cancel"),
    db: Session = Depends(get_db),
) -> HoldOut:
    """Cancel (delete) a hold.

    Cancelling a hold frees the slot so that other clients can book it.
    """
    hold = db.query(Hold).filter(Hold.id == hold_id).first()
    if not hold:
        raise HTTPException(status_code=404, detail="Hold not found")
    if hold.status == HoldStatus.CONFIRMED:
        raise HTTPException(status_code=400, detail="Hold already confirmed")
    hold.status = HoldStatus.EXPIRED
    db.commit()
    db.refresh(hold)
    return HoldOut.from_orm(hold)