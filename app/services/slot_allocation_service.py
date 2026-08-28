"""Slot allocation service.

Manages durable 15-minute discrete slot allocations for confirmed bookings.
Enforces database-level concurrency protection by inserting slot allocation rows
with a unique constraint on (provider_id, slot_start).
Provides audit and repair facilities for slot allocation backfill integrity.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Set, Tuple, Optional, Dict, Any
import logging
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.booking import Booking
from ..models.booking_slot_allocation import BookingSlotAllocation
from ..core.state_machine import BookingStatus

logger = logging.getLogger(__name__)

SLOT_GRANULARITY_MINUTES = 15
DEFAULT_MIN_BUFFER_MINUTES = 15


class SlotAllocationIntegrityError(Exception):
    """Raised when slot allocation audit or repair detects unresolvable collisions or malformed data."""
    pass


@dataclass
class SlotAllocationAuditResult:
    """Aggregated, privacy-safe metrics for slot allocation audit and repair."""
    scanned_bookings: int = 0
    fully_allocated_bookings: int = 0
    repaired_bookings: int = 0
    malformed_records: int = 0
    collision_conflicts: int = 0
    incomplete_allocations: int = 0
    errors: List[str] = field(default_factory=list)
    is_valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scanned_bookings": self.scanned_bookings,
            "fully_allocated_bookings": self.fully_allocated_bookings,
            "repaired_bookings": self.repaired_bookings,
            "malformed_records": self.malformed_records,
            "collision_conflicts": self.collision_conflicts,
            "incomplete_allocations": self.incomplete_allocations,
            "error_count": len(self.errors),
            "is_valid": self.is_valid,
        }


def is_slot_allocation_conflict(exc: IntegrityError) -> bool:
    """Determine whether an IntegrityError was caused specifically by a slot allocation or active booking unique constraint collision.

    Supports PostgreSQL (inspecting psycopg2/asyncpg driver diagnostics and constraint names)
    and SQLite (inspecting unique constraint message formats).
    """
    orig = getattr(exc, "orig", None)

    # 1. PostgreSQL driver diagnostics
    if orig is not None:
        diag = getattr(orig, "diag", None)
        if diag is not None:
            constraint_name = getattr(diag, "constraint_name", None)
            if constraint_name in ("uq_provider_slot_allocation", "uq_active_bookings"):
                return True
        pgcode = getattr(orig, "pgcode", None)
        if pgcode == "23505":  # PostgreSQL unique_violation code
            orig_msg = str(orig).lower()
            if "uq_provider_slot_allocation" in orig_msg or "booking_slot_allocations" in orig_msg or "uq_active_bookings" in orig_msg:
                return True

    # 2. SQLite error strings & general exception text
    err_str = str(exc).lower()
    if "uq_provider_slot_allocation" in err_str or "uq_active_bookings" in err_str:
        return True
    if "booking_slot_allocations.provider_id" in err_str and "booking_slot_allocations.slot_start" in err_str:
        return True
    if "unique constraint failed: booking_slot_allocations" in err_str:
        return True

    return False


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


def audit_and_repair_slot_allocations(
    db: Session,
    dry_run: bool = True,
) -> SlotAllocationAuditResult:
    """Audit and optionally repair slot allocations for all active non-cancelled bookings.

    Performs exhaustive checks:
    - Calculates expected discrete 15-minute slot timestamps covering duration and buffers.
    - Detects missing, incomplete, or corrupted allocations.
    - Detects historical collisions and malformed timestamps.
    - Uses strictly parameterized SQL for safe execution across PostgreSQL and SQLite.
    - Reports privacy-safe aggregate counts only (zero PII).
    - If dry_run=False and unresolvable errors/collisions exist, rolls back and raises SlotAllocationIntegrityError.
    """
    result = SlotAllocationAuditResult()

    # 1. Fetch active non-cancelled bookings using parameterized query
    query = text(
        """
        SELECT b.id, b.tenant_id, b.provider_id, b.service_id, b.start_time, b.end_time,
               s.buffer_before, s.buffer_after
        FROM bookings b
        LEFT JOIN services s ON b.service_id = s.id
        WHERE CAST(b.status AS VARCHAR) NOT IN ('CANCELLED', 'cancelled')
        ORDER BY b.id ASC
        """
    )
    rows = db.execute(query).fetchall()

    seen_allocations: Dict[Tuple[int, datetime], int] = {}  # (provider_id, slot_start) -> booking_id

    for row in rows:
        result.scanned_bookings += 1
        b_id = row[0]
        t_id = row[1]
        p_id = row[2]
        s_id = row[3]
        raw_start = row[4]
        raw_end = row[5]
        buf_before = row[6] if row[6] is not None else DEFAULT_MIN_BUFFER_MINUTES
        buf_after = row[7] if row[7] is not None else DEFAULT_MIN_BUFFER_MINUTES

        # Check for malformed or missing timestamps
        if not raw_start or not raw_end:
            result.malformed_records += 1
            result.errors.append(f"Booking ID {b_id}: missing start_time or end_time.")
            result.is_valid = False
            continue

        try:
            if isinstance(raw_start, str):
                start_dt = datetime.fromisoformat(raw_start)
            else:
                start_dt = raw_start

            if isinstance(raw_end, str):
                end_dt = datetime.fromisoformat(raw_end)
            else:
                end_dt = raw_end

            if start_dt >= end_dt:
                raise ValueError("start_time must be earlier than end_time")

            expected_slots = generate_slot_timestamps(start_dt, end_dt, buf_before, buf_after)
        except Exception as exc:
            result.malformed_records += 1
            result.errors.append(f"Booking ID {b_id}: unparseable or invalid timestamps ({type(exc).__name__}).")
            result.is_valid = False
            continue

        # Check for historical slot collisions among active bookings
        booking_has_collision = False
        for slot in expected_slots:
            slot_utc = normalize_to_utc(slot)
            alloc_key = (p_id, slot_utc)
            if alloc_key in seen_allocations:
                other_b_id = seen_allocations[alloc_key]
                result.collision_conflicts += 1
                result.errors.append(
                    f"Collision detected for provider_id={p_id} at slot {slot_utc.isoformat()} between Booking ID {other_b_id} and Booking ID {b_id}."
                )
                result.is_valid = False
                booking_has_collision = True
            else:
                seen_allocations[alloc_key] = b_id

        # Query existing slot allocations for this booking
        alloc_query = text(
            """
            SELECT id, tenant_id, provider_id, slot_start
            FROM booking_slot_allocations
            WHERE booking_id = :booking_id
            ORDER BY slot_start ASC
            """
        )
        existing_allocs = db.execute(alloc_query, {"booking_id": b_id}).fetchall()

        # Compare existing allocations against expected allocations
        existing_slot_set: Set[datetime] = set()
        has_metadata_mismatch = False

        for a in existing_allocs:
            a_tenant_id = a[1]
            a_provider_id = a[2]
            a_slot_start = a[3]

            if isinstance(a_slot_start, str):
                a_dt = normalize_to_utc(datetime.fromisoformat(a_slot_start))
            else:
                a_dt = normalize_to_utc(a_slot_start)

            existing_slot_set.add(a_dt)
            if a_tenant_id != t_id or a_provider_id != p_id:
                has_metadata_mismatch = True

        expected_slot_set = {normalize_to_utc(s) for s in expected_slots}

        if existing_slot_set == expected_slot_set and not has_metadata_mismatch:
            result.fully_allocated_bookings += 1
        else:
            result.incomplete_allocations += 1
            if not dry_run and not booking_has_collision:
                # Atomically delete invalid/incomplete allocations and insert the exact expected set
                del_stmt = text("DELETE FROM booking_slot_allocations WHERE booking_id = :booking_id")
                db.execute(del_stmt, {"booking_id": b_id})

                now_utc = datetime.now(timezone.utc)
                ins_stmt = text(
                    """
                    INSERT INTO booking_slot_allocations (tenant_id, booking_id, provider_id, slot_start, created_at)
                    VALUES (:tenant_id, :booking_id, :provider_id, :slot_start, :created_at)
                    """
                )
                for slot in expected_slots:
                    db.execute(
                        ins_stmt,
                        {
                            "tenant_id": t_id,
                            "booking_id": b_id,
                            "provider_id": p_id,
                            "slot_start": normalize_to_utc(slot),
                            "created_at": now_utc,
                        },
                    )
                result.repaired_bookings += 1

    if not dry_run:
        if not result.is_valid:
            db.rollback()
            raise SlotAllocationIntegrityError(
                f"Slot allocation integrity repair aborted: {len(result.errors)} errors detected. Details: {'; '.join(result.errors[:5])}"
            )
        db.commit()

    return result


def backfill_slot_allocations(db: Session) -> int:
    """Legacy backfill entrypoint delegating to audit_and_repair_slot_allocations."""
    res = audit_and_repair_slot_allocations(db, dry_run=False)
    return res.repaired_bookings
