"""Booking management routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_company, get_db, get_current_tenant
from ...models.tenant import Tenant
from ...core.pagination import paginate_query, pagination_params
from ...core.state_machine import BookingStatus, is_valid_transition
from ...services import scheduling_service
from ...models.booking import Booking as BookingModel
from ...models import Service
from ...services.outbox_service import create_outbox_event
from ...schemas.booking import (
    Booking,
    BookingCreate,
    BookingListResponse,
    BookingResponse,
    BookingUpdate,
)


router = APIRouter()


@router.get("/bookings", response_model=BookingListResponse, tags=["bookings"])
def list_bookings(
    params: dict = Depends(pagination_params),
    status_filter: Optional[BookingStatus] = Query(None, description="Filter by status"),
    client_id: Optional[int] = Query(None, description="Filter by client id"),
    provider_id: Optional[int] = Query(None, description="Filter by provider id"),
    date_from: Optional[datetime] = Query(None, description="Filter bookings starting after this date"),
    date_to: Optional[datetime] = Query(None, description="Filter bookings starting before this date"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Return a paginated list of bookings with optional filters."""
    query = db.query(BookingModel).filter(BookingModel.tenant_id == current_user.tenant_id)
    if status_filter:
        query = query.filter(BookingModel.status == status_filter)
    if client_id:
        query = query.filter(BookingModel.client_id == client_id)
    if provider_id:
        query = query.filter(BookingModel.provider_id == provider_id)
    if date_from:
        query = query.filter(BookingModel.start_time >= date_from)
    if date_to:
        query = query.filter(BookingModel.start_time <= date_to)
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/bookings", response_model=BookingResponse, tags=["bookings"])
def create_booking(
    booking_in: BookingCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a new booking as an admin."""
    # Validate provider eligibility for the service, if provided
    if booking_in.provider_id:
        # Fetch the service to inspect provider assignments
        service_obj = db.query(Service).filter(
            Service.id == booking_in.service_id,
            Service.tenant_id == current_user.tenant_id
        ).first()
        if service_obj and service_obj.providers:
            provider_ids = {sp.provider_id for sp in service_obj.providers}
            if booking_in.provider_id not in provider_ids:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider is not eligible for this service")
    booking = BookingModel(tenant_id=current_user.tenant_id, **booking_in.dict())
    db.add(booking)
    db.commit()
    db.refresh(booking)
    # Allocate resources if needed
    try:
        scheduling_service.allocate_resources(db, booking=booking, commit=True)
    except HTTPException as exc:
        # Remove the booking if resources cannot be allocated
        db.delete(booking)
        db.commit()
        raise exc
    
    payload = {
        "id": booking.id,
        "client_id": booking.client_id,
        "provider_id": booking.provider_id,
        "service_id": booking.service_id,
        "start_time": booking.start_time.isoformat() if booking.start_time else None,
        "end_time": booking.end_time.isoformat() if booking.end_time else None,
        "status": booking.status
    }
    create_outbox_event(db, "booking.created", payload)
    db.commit()
    return {"ok": True, "data": booking}


@router.post("/public/bookings", response_model=BookingResponse, tags=["bookings"])
def create_public_booking(
    booking_in: BookingCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> dict:
    """Create a new booking via the public widget.

    Public bookings are always created with ``pending`` status. They do not
    require an authenticated user but must supply a valid public token.
    """
    booking_data = booking_in.dict()
    booking_data["status"] = BookingStatus.PENDING
    # Validate provider eligibility if provided
    if booking_in.provider_id:
        service_obj = db.query(Service).filter(
            Service.id == booking_in.service_id,
            Service.tenant_id == tenant.id
        ).first()
        if service_obj and service_obj.providers:
            provider_ids = {sp.provider_id for sp in service_obj.providers}
            if booking_in.provider_id not in provider_ids:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider is not eligible for this service")
    booking = BookingModel(tenant_id=tenant.id, **booking_data)
    db.add(booking)
    db.commit()
    db.refresh(booking)
    try:
        scheduling_service.allocate_resources(db, booking=booking, commit=True)
    except HTTPException as exc:
        db.delete(booking)
        db.commit()
        raise exc

    payload = {
        "id": booking.id,
        "client_id": booking.client_id,
        "provider_id": booking.provider_id,
        "service_id": booking.service_id,
        "start_time": booking.start_time.isoformat() if booking.start_time else None,
        "end_time": booking.end_time.isoformat() if booking.end_time else None,
        "status": booking.status
    }
    create_outbox_event(db, "booking.created", payload, tenant_id=tenant.subdomain)
    db.commit()
    return {"ok": True, "data": booking}


@router.get("/bookings/{booking_id}", response_model=BookingResponse, tags=["bookings"])
def get_booking(booking_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_admin)) -> dict:
    """Retrieve a booking by its ID."""
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id, BookingModel.tenant_id == current_user.tenant_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return {"ok": True, "data": booking}


@router.put("/bookings/{booking_id}", response_model=BookingResponse, tags=["bookings"])
def update_booking(
    booking_id: int,
    booking_in: BookingUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update a booking's basic details (not state transitions)."""
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id, BookingModel.tenant_id == current_user.tenant_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    update_data = booking_in.dict(exclude_unset=True)
    # Validate status transitions if provided
    if "status" in update_data:
        new_status = update_data["status"]
        if not is_valid_transition(booking.status, new_status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition from {booking.status} to {new_status}",
            )
    for field, value in update_data.items():
        setattr(booking, field, value)
    db.commit()
    db.refresh(booking)
    return {"ok": True, "data": booking}


@router.post("/bookings/{booking_id}/confirm", response_model=BookingResponse, tags=["bookings"])
def confirm_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Confirm a pending booking."""
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id, BookingModel.tenant_id == current_user.tenant_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if not is_valid_transition(booking.status, BookingStatus.CONFIRMED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status transition")
    booking.status = BookingStatus.CONFIRMED
    payload = {
        "id": booking.id,
        "client_id": booking.client_id,
        "provider_id": booking.provider_id,
        "service_id": booking.service_id,
        "start_time": booking.start_time.isoformat() if booking.start_time else None,
        "end_time": booking.end_time.isoformat() if booking.end_time else None,
        "status": booking.status
    }
    create_outbox_event(db, "booking.confirmed", payload)
    db.commit()
    db.refresh(booking)
    return {"ok": True, "data": booking}


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse, tags=["bookings"])
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Cancel a booking."""
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id, BookingModel.tenant_id == current_user.tenant_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if not is_valid_transition(booking.status, BookingStatus.CANCELLED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status transition")
    # Update status and release resources
    booking.status = BookingStatus.CANCELLED
    # Release any allocated resources since the booking will no longer take place
    scheduling_service.release_resources(db, booking=booking, commit=False)
    payload = {
        "id": booking.id,
        "client_id": booking.client_id,
        "provider_id": booking.provider_id,
        "service_id": booking.service_id,
        "start_time": booking.start_time.isoformat() if booking.start_time else None,
        "end_time": booking.end_time.isoformat() if booking.end_time else None,
        "status": booking.status
    }
    create_outbox_event(db, "booking.cancelled", payload)
    db.commit()
    db.refresh(booking)
    return {"ok": True, "data": booking}


@router.post("/bookings/{booking_id}/complete", response_model=BookingResponse, tags=["bookings"])
def complete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Mark a booking as completed."""
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id, BookingModel.tenant_id == current_user.tenant_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if not is_valid_transition(booking.status, BookingStatus.COMPLETED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status transition")
    booking.status = BookingStatus.COMPLETED
    # Resources can be considered released at the time the booking is completed
    scheduling_service.release_resources(db, booking=booking, commit=False)
    payload = {
        "id": booking.id,
        "client_id": booking.client_id,
        "provider_id": booking.provider_id,
        "service_id": booking.service_id,
        "start_time": booking.start_time.isoformat() if booking.start_time else None,
        "end_time": booking.end_time.isoformat() if booking.end_time else None,
        "status": booking.status
    }
    create_outbox_event(db, "booking.completed", payload)
    db.commit()
    db.refresh(booking)
    return {"ok": True, "data": booking}


@router.post("/bookings/{booking_id}/noshow", response_model=BookingResponse, tags=["bookings"])
def noshow_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Mark a booking as no‑show."""
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id, BookingModel.tenant_id == current_user.tenant_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if not is_valid_transition(booking.status, BookingStatus.NO_SHOW):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status transition")
    booking.status = BookingStatus.NO_SHOW
    # Release resources on no-show to free up capacity
    scheduling_service.release_resources(db, booking=booking, commit=False)
    payload = {
        "id": booking.id,
        "client_id": booking.client_id,
        "provider_id": booking.provider_id,
        "service_id": booking.service_id,
        "start_time": booking.start_time.isoformat() if booking.start_time else None,
        "end_time": booking.end_time.isoformat() if booking.end_time else None,
        "status": booking.status
    }
    create_outbox_event(db, "booking.no_show", payload)
    db.commit()
    db.refresh(booking)
    return {"ok": True, "data": booking}


@router.post("/bookings/{booking_id}/reschedule", response_model=BookingResponse, tags=["bookings"])
def reschedule_booking(
    booking_id: int,
    new_start: datetime,
    new_end: datetime,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Reschedule a booking to a new time.

    This endpoint transitions the booking to ``rescheduled`` status and
    updates the start and end times. The booking must be in a state
    that allows rescheduling.
    """
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id, BookingModel.tenant_id == current_user.tenant_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if not is_valid_transition(booking.status, BookingStatus.RESCHEDULED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status transition")
    # Change status and release/allocate resources
    booking.status = BookingStatus.RESCHEDULED
    # Release old resources
    scheduling_service.release_resources(db, booking=booking, commit=False)
    # Update times
    booking.start_time = new_start
    booking.end_time = new_end
    db.commit()
    db.refresh(booking)
    # Attempt to allocate resources for the new time
    try:
        scheduling_service.allocate_resources(db, booking=booking, commit=True)
    except HTTPException as exc:
        # If allocation fails revert the time change and status
        # Note: we do not re-add old resources; they were released; but we need to restore time/resources; for simplicity, mark booking cancelled
        booking.status = BookingStatus.CANCELLED
        db.commit()
        db.refresh(booking)
        raise exc
    
    payload = {
        "id": booking.id,
        "client_id": booking.client_id,
        "provider_id": booking.provider_id,
        "service_id": booking.service_id,
        "start_time": booking.start_time.isoformat() if booking.start_time else None,
        "end_time": booking.end_time.isoformat() if booking.end_time else None,
        "status": booking.status
    }
    create_outbox_event(db, "booking.rescheduled", payload)
    db.commit()
    return {"ok": True, "data": booking}