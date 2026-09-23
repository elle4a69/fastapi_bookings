"""Public booking routes.

This router exposes the intended public booking endpoint under
/api/public/bookings. The final booking submission is the sole contention
point and follows an atomic first-valid-submission-wins model.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_public_tenant, get_db
from ...models.tenant import Tenant
from ...schemas.booking import BookingCreate, BookingResponse
from ...services.booking_creation_service import (
    BookingCommandError,
    create_authoritative_booking,
)

router = APIRouter(prefix="/api/public", tags=["public-bookings"])


@router.post("/bookings", response_model=BookingResponse)
def create_public_booking(
    booking_in: BookingCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Create a pending booking using the authoritative booking command.

    The command revalidates the exact live slot and persists the booking,
    allocations, audit record, and outbox event in one transaction.
    """
    try:
        booking = create_authoritative_booking(
            db,
            tenant_id=tenant.id,
            command=booking_in,
        )
    except BookingCommandError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return {"ok": True, "data": booking}

