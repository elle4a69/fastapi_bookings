"""Public booking routes.

This router exposes the intended public booking endpoint under
/api/public/bookings. The final booking submission is the sole contention
point and follows an atomic first-valid-submission-wins model.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_public_tenant, get_db
from ...models.tenant import Tenant
from ...schemas.booking import BookingCreate, PublicBookingResponse
from ...services.booking_creation_service import (
    BookingCommandError,
    create_authoritative_booking,
)

router = APIRouter(prefix="/api/public", tags=["public-bookings"])
logger = logging.getLogger(__name__)


@router.post("/bookings", response_model=PublicBookingResponse)
def create_public_booking(
    booking_in: BookingCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Create a pending booking using the authoritative booking command.

    The command revalidates the exact live slot and persists the booking,
    allocations, audit record, and outbox event in one transaction.
    """
    if booking_in.client_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Public bookings require customer contact details, not client_id.",
        )

    try:
        booking = create_authoritative_booking(
            db,
            tenant_id=tenant.id,
            command=booking_in,
        )
        db.commit()
        db.refresh(booking)
    except BookingCommandError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as exc:
        db.rollback()
        logger.error(
            "public_booking_commit_failed tenant_id=%s error_type=%s",
            tenant.id,
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="Unable to create booking.") from None
    return {"ok": True, "data": booking}

