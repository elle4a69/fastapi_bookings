import logging
"""Public booking routes.

This router exposes the intended public booking endpoint under
/api/public/bookings. The final booking submission is the sole contention
point and follows an atomic first-confirmed-submission-wins model.
"""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import get_public_tenant, get_db
from ...models.tenant import Tenant
from ...core.state_machine import BookingStatus
from ...models import Service, Provider, Client, Location, BlockedTime, ReservedTime
from ...models.booking import Booking as BookingModel
from ...schemas.booking import BookingCreate, BookingResponse
from ...services import scheduling_service, slot_allocation_service
from ...services.outbox_service import create_outbox_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["public-bookings"])


@router.post("/bookings", response_model=BookingResponse)
def create_public_booking(
    booking_in: BookingCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Create a public booking using atomic first-confirmed-submission-wins.

    Public bookings are created with status `pending`. Re-checks live
    availability and buffers inside a single transaction with row locking.
    """
    # 0. Check idempotency key if provided
    if booking_in.idempotency_key:
        existing_booking = (
            db.query(BookingModel)
            .filter(
                BookingModel.tenant_id == tenant.id,
                BookingModel.idempotency_key == booking_in.idempotency_key,
            )
            .first()
        )
        if existing_booking:
            return {"ok": True, "data": existing_booking}

    # 1. Enforce UTC timezone awareness and minimum lead time (30 min)
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

    now_utc = datetime.now(timezone.utc)
    if start_time < now_utc + timedelta(minutes=30):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bookings must be made at least 30 minutes in advance.",
        )

    # 2. Verify service belongs to active tenant
    service_obj = db.query(Service).filter(
        Service.id == booking_in.service_id,
        Service.tenant_id == tenant.id,
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
            Provider.tenant_id == tenant.id,
            Provider.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if not provider_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    if not provider_obj.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider is not active")

    # 4. Verify provider eligibility for service
    if service_obj.providers:
        provider_ids = {sp.provider_id for sp in service_obj.providers}
        if booking_in.provider_id not in provider_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provider is not eligible for this service",
            )

    # 5. Resolve or verify client belonging to active tenant
    client_obj = None
    if booking_in.client_id is not None:
        client_obj = db.query(Client).filter(
            Client.id == booking_in.client_id,
            Client.tenant_id == tenant.id,
            Client.deleted_at.is_(None)
        ).first()
        if not client_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    elif booking_in.client_email or booking_in.client_phone or booking_in.client_name:
        if booking_in.client_email:
            client_obj = db.query(Client).filter(
                Client.tenant_id == tenant.id,
                Client.email == booking_in.client_email.strip().lower(),
                Client.deleted_at.is_(None)
            ).first()
        if not client_obj and booking_in.client_phone:
            client_obj = db.query(Client).filter(
                Client.tenant_id == tenant.id,
                Client.phone == booking_in.client_phone.strip(),
                Client.deleted_at.is_(None)
            ).first()
        if not client_obj:
            client_name = (booking_in.client_name or "").strip() or (booking_in.client_email.split('@')[0] if booking_in.client_email else "Guest Client")
            client_obj = Client(
                tenant_id=tenant.id,
                name=client_name,
                email=booking_in.client_email.strip().lower() if booking_in.client_email else None,
                phone=booking_in.client_phone.strip() if booking_in.client_phone else None,
                active=True,
                management_approval_required=False
            )
            db.add(client_obj)
            db.flush()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client identification (client_id or client_name/email/phone) is required."
        )

    if client_obj.management_approval_required:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client requires management approval before booking.",
        )

    # 6. Verify location (if provided) belongs to active tenant
    location_obj = None
    if booking_in.location_id:
        location_obj = db.query(Location).filter(
            Location.id == booking_in.location_id,
            Location.tenant_id == tenant.id
        ).first()
        if not location_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

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
                detail="The requested time slot is no longer available. Please choose another time.",
            )

    # 8. Check BlockedTime and ReservedTime
    blocked_time = (
        db.query(BlockedTime)
        .filter(
            BlockedTime.tenant_id == tenant.id,
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

    # 9. Verify resource availability
    resources = scheduling_service.find_available_resources(
        db,
        service=service_obj,
        start_time=start_time,
        end_time=end_time,
        provider=provider_obj,
        location=location_obj,
    )
    if resources is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Required resources are not available for this time slot.",
        )

    # 10. Atomic single-transaction booking, slot allocation, and resource reservation
    booking_data = booking_in.model_dump(exclude={"client_name", "client_email", "client_phone"})
    booking_data["client_id"] = client_obj.id
    booking_data["status"] = BookingStatus.PENDING
    booking_data["tenant_id"] = tenant.id
    booking_data["start_time"] = start_time
    booking_data["end_time"] = end_time

    booking = BookingModel(**booking_data)
    db.add(booking)
    db.flush()

    try:
        # Create durable slot allocations with database-level unique constraint on (provider_id, slot_start)
        slot_allocation_service.create_allocations_for_booking(
            db, booking=booking, buffer_before=buf_before, buffer_after=buf_after
        )

        # Allocate required resources
        scheduling_service.allocate_resources(db, booking=booking, commit=False)

        # Enqueue transactional outbox event
        payload = {
            "id": booking.id,
            "client_id": booking.client_id,
            "provider_id": booking.provider_id,
            "service_id": booking.service_id,
            "start_time": booking.start_time.isoformat() if booking.start_time else None,
            "end_time": booking.end_time.isoformat() if booking.end_time else None,
            "status": booking.status,
        }
        create_outbox_event(db, "booking.created", payload, tenant_id=tenant.id)

        # Commit entire atomic transaction
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if booking_in.idempotency_key:
            existing = (
                db.query(BookingModel)
                .filter(
                    BookingModel.tenant_id == tenant.id,
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
            "Unrelated database integrity error during public booking creation (tenant_id=%s, booking_id=%s): %s",
            tenant.id,
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
            "Unexpected error during public booking creation transaction (tenant_id=%s, booking_id=%s): %s",
            tenant.id,
            booking.id,
            exc,
            exc_info=True,
        )
        raise

    db.refresh(booking)
    return {"ok": True, "data": booking}

