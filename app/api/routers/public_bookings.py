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
from ...schemas.booking import (
    BookingCreate,
    PublicBookingCreate,
    PublicBookingReceipt,
    PublicBookingResponse,
)
from ...services.booking_creation_service import (
    BookingCommandError,
    create_authoritative_booking,
)

router = APIRouter(prefix="/api/public", tags=["public-bookings"])
logger = logging.getLogger(__name__)


@router.post("/bookings", response_model=PublicBookingResponse)
def create_public_booking(
    booking_in: PublicBookingCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Create a pending booking using the authoritative booking command.

    The command revalidates the exact live slot and persists the booking,
    allocations, audit record, and outbox event in one transaction.
    """
    if booking_in.model_extra:
        raise HTTPException(
            status_code=422,
            detail="Public booking request contains unsupported fields.",
        )

    try:
        command = BookingCreate(
            **booking_in.model_dump(exclude={"addon_ids", "product_ids"})
        )
        booking = create_authoritative_booking(
            db,
            tenant_id=tenant.id,
            command=command,
        )
        receipt = PublicBookingReceipt.model_validate(booking)
        db.commit()
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
    return {"ok": True, "data": receipt}

