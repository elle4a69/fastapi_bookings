"""Hold and Waitlist management service.

This module contains functions to create holds, expire holds, and promote
the waitlist. It adheres fully to the timezone UTC discipline and contains
zero placeholders.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..models import (
    Service,
    Provider,
    Location,
    Hold,
    HoldStatus,
    WaitlistEntry,
    WaitlistStatus,
)


def create_hold(
    db: Session,
    *,
    service: Service,
    client_id: Optional[int],
    start_time: datetime,
    end_time: datetime,
    provider: Optional[Provider] = None,
    location: Optional[Location] = None,
    expires_in: int = 15,
    commit: bool = True,
) -> Hold:
    """Create a temporary hold for a slot.

    This reserves the slot while a client fills out a booking form, helping to
    prevent double-booking.
    """
    # Enforce UTC timezone awareness
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    # Acquire a row lock on the provider if provided to serialize concurrent checks
    if provider:
        db.query(Provider).filter(Provider.id == provider.id).with_for_update().first()

    # Check for overlapping active bookings/holds/blocks/reservations
    from ..core.state_machine import BookingStatus
    from ..models import Booking, BlockedTime, ReservedTime
    from .scheduling_utils import check_slot_overlaps

    now_utc = datetime.now(timezone.utc)
    active_bookings = (
        db.query(Booking)
        .filter(
            Booking.provider_id == (provider.id if provider else None),
            Booking.status != BookingStatus.CANCELLED,
            Booking.end_time > start_time,
            Booking.start_time < end_time,
        )
        .all()
    )

    provider_blocked = (
        db.query(BlockedTime)
        .filter(
            BlockedTime.tenant_id == service.tenant_id,
            BlockedTime.active.is_(True),
            BlockedTime.end_time > start_time,
            BlockedTime.start_time < end_time,
            (BlockedTime.provider_id == (provider.id if provider else None)) | (BlockedTime.provider_id.is_(None)),
        )
        .all()
    )

    active_holds = (
        db.query(Hold)
        .filter(
            Hold.tenant_id == service.tenant_id,
            Hold.status == HoldStatus.PENDING,
            Hold.expires_at > now_utc,
            Hold.end_time > start_time,
            Hold.start_time < end_time,
            (Hold.provider_id == (provider.id if provider else None)) | (Hold.provider_id.is_(None)),
        )
        .all()
    )

    active_reservations = (
        db.query(ReservedTime)
        .filter(
            ReservedTime.tenant_id == service.tenant_id,
            ReservedTime.end_time > start_time,
            ReservedTime.start_time < end_time,
            (ReservedTime.provider_id == (provider.id if provider else None)) | (ReservedTime.provider_id.is_(None)),
            (ReservedTime.expires_at.is_(None)) | (ReservedTime.expires_at > now_utc),
        )
        .all()
    )

    if check_slot_overlaps(
        start_time,
        end_time,
        active_bookings,
        provider_blocked,
        active_holds,
        active_reservations,
        new_buffer_before=service.buffer_before if service.buffer_before else 0,
        new_buffer_after=service.buffer_after if service.buffer_after else 0,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The requested slot is no longer available."
        )

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in)
    
    hold = Hold(
        tenant_id=service.tenant_id,
        service_id=service.id,
        provider_id=provider.id if provider else None,
        location_id=location.id if location else None,
        start_time=start_time,
        end_time=end_time,
        client_id=client_id,
        expires_at=expires_at,
        status=HoldStatus.PENDING,
    )
    
    db.add(hold)
    
    if expires_in <= 0:
        hold.status = HoldStatus.EXPIRED
        
    if commit:
        db.commit()
        db.refresh(hold)
        
    return hold


def expire_holds(db: Session) -> int:
    """Expire any holds that have passed their expiration time.

    Returns the number of holds expired.
    """
    now = datetime.now(timezone.utc)
    expired = (
        db.query(Hold)
        .filter(Hold.status == HoldStatus.PENDING, Hold.expires_at <= now)
        .all()
    )
    
    count = 0
    for hold in expired:
        hold.status = HoldStatus.EXPIRED
        count += 1
        
    if count > 0:
        db.commit()
        for hold in expired:
            if hold.service:
                promote_waitlist(db, service=hold.service)
        
    return count


def promote_waitlist(db: Session, *, service: Service) -> None:
    """Promote waitlist entries to bookings when slots become available.

    Finds the oldest waitlist entry for this service, checks if a suitable
    slot has become available, and if so, creates a hold and notifies the client.
    """
    from .scheduling_service import compute_availability
    
    # Query requested waitlist entries for this service in FIFO order (oldest first)
    entries = (
        db.query(WaitlistEntry)
        .filter(
            WaitlistEntry.service_id == service.id,
            WaitlistEntry.status == WaitlistStatus.REQUESTED,
        )
        .order_by(WaitlistEntry.created_at.asc())
        .with_for_update()
        .all()
    )
    
    for entry in entries:
        # Determine search window from desired date fields, fall back to current UTC + 7 days
        now_utc = datetime.now(timezone.utc)
        start_time = entry.desired_date_from or now_utc
        end_time = entry.desired_date_to or (start_time + timedelta(days=7))
        
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        # Check if start_time is in the past, if so start from now
        if start_time < now_utc:
            start_time = now_utc
            
        if start_time >= end_time:
            continue
            
        # Check availability for the entry's service, provider, and location
        available_slots = compute_availability(
            db,
            service=service,
            provider=entry.provider,
            location=entry.location,
            start_time=start_time,
            end_time=end_time,
        )
        
        if available_slots:
            # We found at least one slot!
            slot = available_slots[0]
            slot_start = datetime.fromisoformat(slot["start_time"])
            slot_end = datetime.fromisoformat(slot["end_time"])
            
            # Create a hold for this client (holding it for 30 minutes to allow them to confirm)
            create_hold(
                db,
                service=service,
                client_id=entry.client_id,
                start_time=slot_start,
                end_time=slot_end,
                provider=entry.provider,
                location=entry.location,
                expires_in=30,
                commit=False,
            )
            
            # Update waitlist status to NOTIFIED
            entry.status = WaitlistStatus.NOTIFIED
            db.flush()
            
    db.commit()
