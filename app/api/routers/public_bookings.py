"""Public booking routes.

This router exposes the intended public booking endpoint under
/api/public/bookings.  The older admin-prefixed compatibility route remains
in bookings.py, but front-end clients should use this router.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_public_tenant, get_db
from ...models.tenant import Tenant
from ...core.state_machine import BookingStatus
from ...models import Service, Provider, Client, Location
from ...models.booking import Booking as BookingModel
from ...schemas.booking import BookingCreate, BookingResponse
from ...services import scheduling_service

router = APIRouter(prefix="/api/public", tags=["public-bookings"])


@router.post("/bookings", response_model=BookingResponse)
def create_public_booking(
    booking_in: BookingCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Create a public booking awaiting provider/admin approval.

    Public bookings are created with status `pending`. An admin/staff user
    must later approve the booking with `/api/admin/bookings/{id}/confirm`.
    """
    # 1. Verify service belongs to active tenant
    service_obj = db.query(Service).filter(
        Service.id == booking_in.service_id,
        Service.tenant_id == tenant.id,
        Service.deleted_at.is_(None)
    ).first()
    if not service_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    # 2. Verify provider belongs to active tenant
    provider_obj = db.query(Provider).filter(
        Provider.id == booking_in.provider_id,
        Provider.tenant_id == tenant.id,
        Provider.deleted_at.is_(None)
    ).first()
    if not provider_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    # 3. Verify client belongs to active tenant
    client_obj = db.query(Client).filter(
        Client.id == booking_in.client_id,
        Client.tenant_id == tenant.id,
        Client.deleted_at.is_(None)
    ).first()
    if not client_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    # 4. Verify location (if provided) belongs to active tenant
    if booking_in.location_id:
        location_obj = db.query(Location).filter(
            Location.id == booking_in.location_id,
            Location.tenant_id == tenant.id
        ).first()
        if not location_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # 5. Verify provider eligibility
    if service_obj.providers:
        provider_ids = {sp.provider_id for sp in service_obj.providers}
        if booking_in.provider_id not in provider_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider is not eligible for this service",
            )

    booking_data = booking_in.dict()
    booking_data["status"] = BookingStatus.PENDING
    booking_data["tenant_id"] = tenant.id

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

