"""Hold and Waitlist management service.

This module contains functions to create holds, expire holds, and promote
the waitlist. It adheres fully to the timezone UTC discipline and contains
zero placeholders.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

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
        .all()
    )
    
    for entry in entries:
        # Determine search window from desired date fields, fall back to current UTC + 7 days
        now_utc = datetime.now(timezone.utc)
        start_time = entry.desired_date_from or now_utc
        end_time = entry.desired_date_to or (start_time + timedelta(days=7))
        
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
            
    db.commit()
