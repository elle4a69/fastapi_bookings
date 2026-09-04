import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..deps import get_current_admin, get_current_company, get_db, get_current_tenant, get_public_tenant, DatabaseId
from ...models.tenant import Tenant
from ...core.pagination import paginate_query, pagination_params
from ...core.state_machine import BookingStatus, is_valid_transition
from ...services import scheduling_service, slot_allocation_service
from ...models.booking import Booking as BookingModel
from ...models import Service, Provider, Client, Location, BlockedTime, ReservedTime
from ...services.outbox_service import create_outbox_event
from ...schemas.booking import (
    Booking,
    BookingCreate,
    BookingListResponse,
    BookingResponse,
    BookingUpdate,
    BookingReschedule,
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
    query = db.query(BookingModel).options(
        joinedload(BookingModel.client),
        joinedload(BookingModel.provider),
        joinedload(BookingModel.service),
        joinedload(BookingModel.location)
    ).filter(BookingModel.tenant_id == current_user.tenant_id)
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
    query = query.order_by(BookingModel.id.desc())
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/bookings", response_model=BookingResponse, tags=["bookings"])
def create_booking(
    booking_in: BookingCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a new booking as an admin using atomic first-submit-wins."""
    # 0. Check idempotency key if provided
    if booking_in.idempotency_key:
        existing_booking = (
            db.query(BookingModel)
            .filter(
                BookingModel.tenant_id == current_user.tenant_id,
                BookingModel.idempotency_key == booking_in.idempotency_key,
            )
            .first()
        )
        if existing_booking:
            return {"ok": True, "data": existing_booking}

    # 1. Enforce UTC timezone awareness
    start_time = booking_in.start_time
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    end_time = booking_in.end_time
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    if start_time >= end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking start time must be before end time.",
        )

    # 2. Verify service belongs to active tenant
    service_obj = db.query(Service).filter(
        Service.id == booking_in.service_id,
        Service.tenant_id == current_user.tenant_id,
        Service.deleted_at.is_(None)
    ).first()
    if not service_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    if not service_obj.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Service is not active")

    # 3. Lock and verify provider belongs to active tenant
    provider_obj = (
        db.query(Provider)
        .filter(
            Provider.id == booking_in.provider_id,
            Provider.tenant_id == current_user.tenant_id,
            Provider.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if not provider_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    if not provider_obj.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider is not active")

    # 4. Verify client belongs to active tenant
    client_obj = db.query(Client).filter(
        Client.id == booking_in.client_id,
        Client.tenant_id == current_user.tenant_id,
        Client.deleted_at.is_(None)
    ).first()
    if not client_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    # 5. Verify location (if provided) belongs to active tenant
    location_obj = None
    if booking_in.location_id:
        location_obj = db.query(Location).filter(
            Location.id == booking_in.location_id,
            Location.tenant_id == current_user.tenant_id
        ).first()
        if not location_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # 6. Validate provider eligibility for the service
    if service_obj.providers:
        provider_ids = {sp.provider_id for sp in service_obj.providers}
        if booking_in.provider_id not in provider_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider is not eligible for this service")

    # 7. Atomic Conflict & Buffer Validation
    buf_before = max(15, service_obj.buffer_before if service_obj.buffer_before else 0)
    buf_after = max(15, service_obj.buffer_after if service_obj.buffer_after else 0)
    padded_start = start_time - timedelta(minutes=buf_before)
    padded_end = end_time + timedelta(minutes=buf_after)

    active_bookings = (
        db.query(BookingModel)
        .filter(
            BookingModel.provider_id == provider_obj.id,
            BookingModel.status != BookingStatus.CANCELLED,
            BookingModel.start_time < padded_end,
            BookingModel.end_time > padded_start,
        )
        .all()
    )

    for b in active_bookings:
        b_start = b.start_time.replace(tzinfo=timezone.utc) if b.start_time.tzinfo is None else b.start_time
        b_end = b.end_time.replace(tzinfo=timezone.utc) if b.end_time.tzinfo is None else b.end_time
        b_buf_before = max(15, b.service.buffer_before) if (b.service and b.service.buffer_before) else 0
        b_buf_after = max(15, b.service.buffer_after) if (b.service and b.service.buffer_after) else 0
        b_blocked_start = b_start - timedelta(minutes=b_buf_before)
        b_blocked_end = b_end + timedelta(minutes=b_buf_after)

        if b_blocked_start < end_time and b_blocked_end > start_time:
            if booking_in.idempotency_key and b.idempotency_key == booking_in.idempotency_key:
                return {"ok": True, "data": b}
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The requested time slot is no longer available.",
            )

    # 8. Check BlockedTime
    blocked_time = (
        db.query(BlockedTime)
        .filter(
            BlockedTime.tenant_id == current_user.tenant_id,
            BlockedTime.active.is_(True),
            (BlockedTime.provider_id == provider_obj.id) | (BlockedTime.provider_id.is_(None)),
            BlockedTime.start_time < end_time,
            BlockedTime.end_time > start_time,
        )
        .first()
    )
    if blocked_time:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The requested time slot is blocked by provider schedule.",
        )

    # 9. Atomic single-transaction booking, slot allocation, and resource reservation
    booking_dict = booking_in.model_dump(exclude={"client_name", "client_email", "client_phone"})
    booking_dict["start_time"] = start_time
    booking_dict["end_time"] = end_time

    booking = BookingModel(tenant_id=current_user.tenant_id, **booking_dict)
    db.add(booking)
    db.flush()

    try:
        slot_allocation_service.create_allocations_for_booking(
            db, booking=booking, buffer_before=buf_before, buffer_after=buf_after
        )
        scheduling_service.allocate_resources(db, booking=booking, commit=False)

        payload = {
            "id": booking.id,
            "client_id": booking.client_id,
            "provider_id": booking.provider_id,
            "service_id": booking.service_id,
            "start_time": booking.start_time.isoformat() if booking.start_time else None,
            "end_time": booking.end_time.isoformat() if booking.end_time else None,
            "status": booking.status,
        }
        create_outbox_event(db, "booking.created", payload, tenant_id=current_user.tenant_id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if booking_in.idempotency_key:
            existing = (
                db.query(BookingModel)
                .filter(
                    BookingModel.tenant_id == current_user.tenant_id,
                    BookingModel.idempotency_key == booking_in.idempotency_key,
                )
                .first()
            )
            if existing:
                return {"ok": True, "data": existing}
        if slot_allocation_service.is_slot_allocation_conflict(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The requested time slot or buffer has just been booked. Please select another available time.",
            )
        logger.error(
            "Unrelated database integrity error during admin booking creation (tenant_id=%s, booking_id=%s): %s",
            current_user.tenant_id,
            booking.id,
            exc,
            exc_info=True,
        )
        raise
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(
            "Unexpected error during admin booking creation transaction (tenant_id=%s, booking_id=%s): %s",
            current_user.tenant_id,
            booking.id,
            exc,
            exc_info=True,
        )
        raise

    db.refresh(booking)
    return {"ok": True, "data": booking}


@router.get("/bookings/{booking_id}", response_model=BookingResponse, tags=["bookings"])
def get_booking(booking_id: DatabaseId, db: Session = Depends(get_db), current_user = Depends(get_current_admin)) -> dict:
    """Retrieve a booking by its ID."""
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id, BookingModel.tenant_id == current_user.tenant_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return {"ok": True, "data": booking}


@router.put("/bookings/{booking_id}", response_model=BookingResponse, tags=["bookings"])
def update_booking(
    booking_id: DatabaseId,
    booking_in: BookingUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update a booking's basic details (not state transitions)."""
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id, BookingModel.tenant_id == current_user.tenant_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    update_data = booking_in.model_dump(exclude_unset=True)
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
    booking_id: DatabaseId,
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
    create_outbox_event(db, "booking.confirmed", payload, tenant_id=booking.tenant_id)
    db.commit()
    db.refresh(booking)
    return {"ok": True, "data": booking}


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse, tags=["bookings"])
def cancel_booking(
    booking_id: DatabaseId,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Cancel a booking."""
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id, BookingModel.tenant_id == current_user.tenant_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if not is_valid_transition(booking.status, BookingStatus.CANCELLED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status transition")
    # Update status and release slot allocations and resources
    booking.status = BookingStatus.CANCELLED
    slot_allocation_service.release_allocations_for_booking(db, booking.id)
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
    create_outbox_event(db, "booking.cancelled", payload, tenant_id=booking.tenant_id)
    db.commit()
    db.refresh(booking)
    return {"ok": True, "data": booking}


@router.post("/bookings/{booking_id}/complete", response_model=BookingResponse, tags=["bookings"])
def complete_booking(
    booking_id: DatabaseId,
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
    create_outbox_event(db, "booking.completed", payload, tenant_id=booking.tenant_id)
    db.commit()
    db.refresh(booking)
    return {"ok": True, "data": booking}


@router.post("/bookings/{booking_id}/noshow", response_model=BookingResponse, tags=["bookings"])
def noshow_booking(
    booking_id: DatabaseId,
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
    create_outbox_event(db, "booking.no_show", payload, tenant_id=booking.tenant_id)
    db.commit()
    db.refresh(booking)
    return {"ok": True, "data": booking}


@router.post("/bookings/{booking_id}/reschedule", response_model=BookingResponse, tags=["bookings"])
def reschedule_booking(
    booking_id: DatabaseId,
    reschedule_in: BookingReschedule,
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
    # Validate lead time for rescheduled time
    now_utc = datetime.now(timezone.utc)
    new_start_utc = reschedule_in.new_start.replace(tzinfo=timezone.utc) if reschedule_in.new_start.tzinfo is None else reschedule_in.new_start
    if new_start_utc < now_utc + timedelta(minutes=30):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bookings must be scheduled at least 30 minutes in advance.",
        )

    # Change status and atomically update slot allocations and resources
    booking.status = BookingStatus.RESCHEDULED
    buf_before = max(15, booking.service.buffer_before if booking.service else 15)
    buf_after = max(15, booking.service.buffer_after if booking.service else 15)

    try:
        slot_allocation_service.reschedule_allocations_for_booking(
            db,
            booking=booking,
            new_start=reschedule_in.new_start,
            new_end=reschedule_in.new_end,
            buffer_before=buf_before,
            buffer_after=buf_after,
        )
        scheduling_service.release_resources(db, booking=booking, commit=False)
        scheduling_service.allocate_resources(db, booking=booking, commit=False)

        payload = {
            "id": booking.id,
            "client_id": booking.client_id,
            "provider_id": booking.provider_id,
            "service_id": booking.service_id,
            "start_time": booking.start_time.isoformat() if booking.start_time else None,
            "end_time": booking.end_time.isoformat() if booking.end_time else None,
            "status": booking.status,
        }
        create_outbox_event(db, "booking.rescheduled", payload, tenant_id=current_user.tenant_id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if slot_allocation_service.is_slot_allocation_conflict(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The requested new time slot is no longer available. Please select another time.",
            )
        logger.error(
            "Unrelated database integrity error during booking reschedule (tenant_id=%s, booking_id=%s): %s",
            current_user.tenant_id,
            booking.id,
            exc,
            exc_info=True,
        )
        raise
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(
            "Unexpected error during booking reschedule transaction (tenant_id=%s, booking_id=%s): %s",
            current_user.tenant_id,
            booking.id,
            exc,
            exc_info=True,
        )
        raise

    db.refresh(booking)
    return {"ok": True, "data": booking}
