"""Public booking routes.

This router exposes the intended public booking endpoint under
/api/public/bookings.  The older admin-prefixed compatibility route remains
in bookings.py, but front-end clients should use this router.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_company, get_db
from ...core.state_machine import BookingStatus
from ...models import Service
from ...models.booking import Booking as BookingModel
from ...schemas.booking import BookingCreate, BookingResponse
from ...services import scheduling_service

router = APIRouter(prefix="/api/public", tags=["public-bookings"])


@router.post("/bookings", response_model=BookingResponse)
def create_public_booking(
    booking_in: BookingCreate,
    db: Session = Depends(get_db),
    company: str = Depends(get_current_company),
) -> dict:
    """Create a public booking awaiting provider/admin approval.

    Public bookings are created with status `pending`. An admin/staff user
    must later approve the booking with `/api/admin/bookings/{id}/confirm`.
    """
    booking_data = booking_in.dict()
    booking_data["status"] = BookingStatus.PENDING

    if booking_in.provider_id:
        service_obj = db.query(Service).filter(Service.id == booking_in.service_id).first()
        if service_obj and service_obj.providers:
            provider_ids = {sp.provider_id for sp in service_obj.providers}
            if booking_in.provider_id not in provider_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Provider is not eligible for this service",
                )

    booking = BookingModel(**booking_data)
    db.add(booking)
    db.commit()
    db.refresh(booking)

    try:
        scheduling_service.allocate_resources(db, booking=booking, commit=True)
    except HTTPException as exc:
        db.delete(booking)
        db.commit()
        raise exc

    return {"ok": True, "data": booking}
