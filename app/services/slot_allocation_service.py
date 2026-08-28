"""Slot allocation service.

Manages durable 15-minute discrete slot allocations for confirmed bookings.
Enforces database-level concurrency protection by inserting slot allocation rows
with a unique constraint on (provider_id, slot_start).
"""

from datetime import datetime, timezone, timedelta
from typing import List
from sqlalchemy.orm import Session

from ..models.booking import Booking
from ..models.booking_slot_allocation import BookingSlotAllocation
from ..core.state_machine import BookingStatus


SLOT_GRANULARITY_MINUTES = 15
DEFAULT_MIN_BUFFER_MINUTES = 15


def normalize_to_utc(dt: datetime) -> datetime:
    """Normalize datetime to timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def generate_slot_timestamps(
    start_time: datetime,
    end_time: datetime,
    buffer_before: int = DEFAULT_MIN_BUFFER_MINUTES,
    buffer_after: int = DEFAULT_MIN_BUFFER_MINUTES,
) -> List[datetime]:
    """Generate discrete 15-minute slot start timestamps covering the booking interval and buffers.

    The total blocked interval spans [start_time - buffer_before, end_time + buffer_after).
    Every 15-minute slice within this interval is mapped to its slot start timestamp.
    """
    start_utc = normalize_to_utc(start_time)
    end_utc = normalize_to_utc(end_time)

    buf_before = max(DEFAULT_MIN_BUFFER_MINUTES, buffer_before or 0)
    buf_after = max(DEFAULT_MIN_BUFFER_MINUTES, buffer_after or 0)

    blocked_start = start_utc - timedelta(minutes=buf_before)
    blocked_end = end_utc + timedelta(minutes=buf_after)

    # Align blocked_start down to nearest 15-minute boundary
    minute_bucket = (blocked_start.minute // SLOT_GRANULARITY_MINUTES) * SLOT_GRANULARITY_MINUTES
    current_slot = blocked_start.replace(minute=minute_bucket, second=0, microsecond=0)

    slots: List[datetime] = []
    while current_slot < blocked_end:
        slots.append(current_slot)
        current_slot += timedelta(minutes=SLOT_GRANULARITY_MINUTES)

    return slots


def create_allocations_for_booking(
    db: Session,
    booking: Booking,
    buffer_before: int = DEFAULT_MIN_BUFFER_MINUTES,
    buffer_after: int = DEFAULT_MIN_BUFFER_MINUTES,
) -> List[BookingSlotAllocation]:
    """Generate and add slot allocation rows for a confirmed booking."""
    slot_times = generate_slot_timestamps(
        start_time=booking.start_time,
        end_time=booking.end_time,
        buffer_before=buffer_before,
        buffer_after=buffer_after,
    )

    allocations: List[BookingSlotAllocation] = []
    for slot_time in slot_times:
        allocation = BookingSlotAllocation(
            tenant_id=booking.tenant_id,
            booking_id=booking.id,
            provider_id=booking.provider_id,
            slot_start=slot_time,
        )
        db.add(allocation)
        allocations.append(allocation)

    return allocations


def release_allocations_for_booking(db: Session, booking_id: int) -> int:
    """Release all slot allocations associated with a booking (e.g. upon cancellation)."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if booking and hasattr(booking, "slot_allocations"):
        booking.slot_allocations.clear()

    deleted_count = (
        db.query(BookingSlotAllocation)
        .filter(BookingSlotAllocation.booking_id == booking_id)
        .delete(synchronize_session="fetch")
    )
    return deleted_count


def reschedule_allocations_for_booking(
    db: Session,
    booking: Booking,
    new_start: datetime,
    new_end: datetime,
    buffer_before: int = DEFAULT_MIN_BUFFER_MINUTES,
    buffer_after: int = DEFAULT_MIN_BUFFER_MINUTES,
) -> List[BookingSlotAllocation]:
    """Atomically release old slot allocations and create new ones for a rescheduled booking."""
    release_allocations_for_booking(db, booking.id)
    db.flush()

    booking.start_time = normalize_to_utc(new_start)
    booking.end_time = normalize_to_utc(new_end)

    return create_allocations_for_booking(
        db,
        booking=booking,
        buffer_before=buffer_before,
        buffer_after=buffer_after,
    )


def backfill_slot_allocations(db: Session) -> int:
    """Backfill slot allocations for existing non-cancelled bookings that lack them."""
    active_bookings = (
        db.query(Booking)
        .filter(Booking.status != BookingStatus.CANCELLED)
        .all()
    )

    created_total = 0
    for booking in active_bookings:
        existing = (
            db.query(BookingSlotAllocation)
            .filter(BookingSlotAllocation.booking_id == booking.id)
            .first()
        )
        if not existing:
            buf_before = booking.service.buffer_before if booking.service else DEFAULT_MIN_BUFFER_MINUTES
            buf_after = booking.service.buffer_after if booking.service else DEFAULT_MIN_BUFFER_MINUTES
            allocs = create_allocations_for_booking(db, booking, buf_before, buf_after)
            created_total += len(allocs)

    if created_total > 0:
        db.commit()

    return created_total
