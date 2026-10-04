"""Atomic Operational Slot Allocation Service.

Manages durable 15-minute discrete slot allocations for confirmed bookings.
Supports Phase 3 5-segment operational windows:
[Inbound Operational Travel] -> [Pre-Buffer] -> [Client Service] -> [Post-Buffer] -> [Onward Operational Travel]

Enforces database-level concurrency protection by inserting slot allocation rows
with a unique constraint on (provider_id, slot_start).
Visible booking start_time and end_time remain the client appointment window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Set, Tuple, Optional, Dict, Any
import logging
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models.booking import Booking
from ...models.booking_slot_allocation import BookingSlotAllocation
from ...models.provider import Provider
from ...models.service import Service
from ...core.state_machine import BookingStatus
from .operational_window import (
    OperationalWindow,
    get_operational_window_calculator,
    normalize_to_utc,
)

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
    """Determine whether an IntegrityError was caused specifically by a slot allocation or active booking unique constraint collision."""
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


def generate_operational_slot_timestamps(
    operational_window_start: datetime,
    operational_window_end: datetime,
) -> List[datetime]:
    """Generate discrete 15-minute slot start timestamps covering an operational window.

    Aligns operational_window_start down to the nearest 15-minute boundary and produces
    slot slices until reaching or exceeding operational_window_end.
    """
    start_utc = normalize_to_utc(operational_window_start)
    end_utc = normalize_to_utc(operational_window_end)

    # Align start down to nearest 15-minute bucket
    minute_bucket = (start_utc.minute // SLOT_GRANULARITY_MINUTES) * SLOT_GRANULARITY_MINUTES
    current_slot = start_utc.replace(minute=minute_bucket, second=0, microsecond=0)

    slots: List[datetime] = []
    while current_slot < end_utc:
        slots.append(current_slot)
        current_slot += timedelta(minutes=SLOT_GRANULARITY_MINUTES)

    return slots


def generate_slot_timestamps(
    start_time: datetime,
    end_time: datetime,
    buffer_before: int = DEFAULT_MIN_BUFFER_MINUTES,
    buffer_after: int = DEFAULT_MIN_BUFFER_MINUTES,
    operational_window_start: Optional[datetime] = None,
    operational_window_end: Optional[datetime] = None,
) -> List[datetime]:
    """Generate discrete 15-minute slot start timestamps covering booking interval and buffers.

    If operational_window_start and operational_window_end are supplied, delegates to
    generate_operational_slot_timestamps to cover the full 5-segment operational window.
    """
    if operational_window_start is not None and operational_window_end is not None:
        return generate_operational_slot_timestamps(operational_window_start, operational_window_end)

    start_utc = normalize_to_utc(start_time)
    end_utc = normalize_to_utc(end_time)

    buf_before = max(DEFAULT_MIN_BUFFER_MINUTES, buffer_before or 0)
    buf_after = max(DEFAULT_MIN_BUFFER_MINUTES, buffer_after or 0)

    blocked_start = start_utc - timedelta(minutes=buf_before)
    blocked_end = end_utc + timedelta(minutes=buf_after)

    return generate_operational_slot_timestamps(blocked_start, blocked_end)


def _resolve_surrounding_bookings(
    db: Session,
    provider_id: int,
    booking_start: datetime,
    booking_end: datetime,
    exclude_booking_id: Optional[int] = None,
) -> Tuple[Optional[Booking], Optional[Booking]]:
    """Find immediate preceding and succeeding active bookings on the same calendar day."""
    start_utc = normalize_to_utc(booking_start)
    end_utc = normalize_to_utc(booking_end)

    day_start = start_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = start_utc.replace(hour=23, minute=59, second=59, microsecond=999999)

    query = (
        db.query(Booking)
        .filter(
            Booking.provider_id == provider_id,
            Booking.status != BookingStatus.CANCELLED,
            Booking.start_time >= day_start,
            Booking.start_time <= day_end,
        )
    )
    if exclude_booking_id is not None:
        query = query.filter(Booking.id != exclude_booking_id)

    day_bookings = query.order_by(Booking.start_time.asc()).all()

    prev_b: Optional[Booking] = None
    next_b: Optional[Booking] = None

    for b in day_bookings:
        b_start = normalize_to_utc(b.start_time)
        b_end = normalize_to_utc(b.end_time)
        if b_end <= start_utc:
            prev_b = b
        elif b_start >= end_utc and next_b is None:
            next_b = b

    return prev_b, next_b


def create_allocations_for_booking(
    db: Session,
    booking: Booking,
    buffer_before: int = DEFAULT_MIN_BUFFER_MINUTES,
    buffer_after: int = DEFAULT_MIN_BUFFER_MINUTES,
    operational_window_start: Optional[datetime] = None,
    operational_window_end: Optional[datetime] = None,
    inbound_travel_minutes: Optional[float] = None,
    outbound_travel_minutes: Optional[float] = None,
) -> List[BookingSlotAllocation]:
    """Generate and add slot allocation rows for a confirmed booking.

    For out-call bookings, dynamically locks discrete 15-minute slot slices spanning the
    entire 5-segment operational window (operational_window_start to operational_window_end).
    Enforces Canonical Ownership Rule: When preceding booking A exists, A's onward journey
    is superseded by this booking's inbound journey (destination owns inbound leg).
    """
    is_outcall = getattr(booking, "service_mode", None) == "out_call"

    if operational_window_start is not None and operational_window_end is not None:
        slot_times = generate_operational_slot_timestamps(
            operational_window_start=operational_window_start,
            operational_window_end=operational_window_end,
        )
    elif is_outcall:
        provider = booking.provider or db.query(Provider).filter(Provider.id == booking.provider_id).first()
        service = booking.service or db.query(Service).filter(Service.id == booking.service_id).first()

        prev_b, next_b = _resolve_surrounding_bookings(
            db,
            provider_id=booking.provider_id,
            booking_start=booking.start_time,
            booking_end=booking.end_time,
            exclude_booking_id=booking.id,
        )

        prev_loc = None
        if prev_b:
            prev_loc = prev_b.service_address or prev_b.client_suburb or getattr(provider, "in_call_address", None)
            # Canonical Ownership Rule: trim preceding booking's return-to-base allocations
            # because the destination booking owns the inbound leg (A -> B).
            prev_post_buf = getattr(prev_b.service, "outcall_buffer_after", 0) if (prev_b.service and prev_b.service_mode == "out_call") else (prev_b.service.buffer_after if prev_b.service else 15)
            trim_boundary = normalize_to_utc(prev_b.end_time) + timedelta(minutes=prev_post_buf)
            db.query(BookingSlotAllocation).filter(
                BookingSlotAllocation.booking_id == prev_b.id,
                BookingSlotAllocation.slot_start > trim_boundary,
            ).delete(synchronize_session="fetch")

        next_loc = None
        if next_b:
            next_loc = next_b.service_address or next_b.client_suburb or getattr(provider, "in_call_address", None)

        calc = get_operational_window_calculator()
        dest = booking.service_address or booking.client_suburb or getattr(provider, "in_call_address", None)

        window = calc.calculate_window(
            provider=provider,
            service=service,
            client_start=booking.start_time,
            client_end=booking.end_time,
            service_mode="out_call",
            destination=dest,
            previous_location=prev_loc,
            next_location=next_loc,
            inbound_travel_override=inbound_travel_minutes,
            outbound_travel_override=outbound_travel_minutes,
        )

        slot_times = generate_operational_slot_timestamps(
            operational_window_start=window.operational_window_start,
            operational_window_end=window.operational_window_end,
        )
    else:
        # Standard In-Call Path: 100% backward-compatible
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
    operational_window_start: Optional[datetime] = None,
    operational_window_end: Optional[datetime] = None,
) -> List[BookingSlotAllocation]:
    """Atomically release old slot allocations and create new ones for a rescheduled booking."""
    release_allocations_for_booking(db, booking.id)
    db.flush()

    booking.start_time = normalize_to_utc(new_start)
    booking.end_time = normalize_to_utc(new_end)

    allocations = create_allocations_for_booking(
        db,
        booking=booking,
        buffer_before=buffer_before,
        buffer_after=buffer_after,
        operational_window_start=operational_window_start,
        operational_window_end=operational_window_end,
    )
    db.flush()
    return allocations


def audit_and_repair_slot_allocations(
    db: Session,
    dry_run: bool = True,
) -> SlotAllocationAuditResult:
    """Audit and optionally repair slot allocations for all active non-cancelled bookings."""
    result = SlotAllocationAuditResult()

    query = text(
        """
        SELECT b.id, b.tenant_id, b.provider_id, b.service_id, b.start_time, b.end_time,
               s.buffer_before, s.buffer_after, b.service_mode
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
        service_mode = row[8] if len(row) > 8 else "in_call"

        if not raw_start or not raw_end:
            result.malformed_records += 1
            result.errors.append(f"Booking ID {b_id}: missing start_time or end_time.")
            result.is_valid = False
            continue

        try:
            start_dt = datetime.fromisoformat(raw_start) if isinstance(raw_start, str) else raw_start
            end_dt = datetime.fromisoformat(raw_end) if isinstance(raw_end, str) else raw_end

            if start_dt >= end_dt:
                raise ValueError("start_time must be earlier than end_time")

            expected_slots = generate_slot_timestamps(start_dt, end_dt, buf_before, buf_after)
        except Exception as exc:
            result.malformed_records += 1
            result.errors.append(f"Booking ID {b_id}: unparseable or invalid timestamps ({type(exc).__name__}).")
            result.is_valid = False
            continue

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

        alloc_query = text(
            """
            SELECT id, tenant_id, provider_id, slot_start
            FROM booking_slot_allocations
            WHERE booking_id = :booking_id
            ORDER BY slot_start ASC
            """
        )
        existing_allocs = db.execute(alloc_query, {"booking_id": b_id}).fetchall()

        existing_slot_set: Set[datetime] = set()
        has_metadata_mismatch = False

        for a in existing_allocs:
            a_tenant_id = a[1]
            a_provider_id = a[2]
            a_slot_start = a[3]

            a_dt = normalize_to_utc(datetime.fromisoformat(a_slot_start) if isinstance(a_slot_start, str) else a_slot_start)
            existing_slot_set.add(a_dt)
            if a_tenant_id != t_id or a_provider_id != p_id:
                has_metadata_mismatch = True

        expected_slot_set = {normalize_to_utc(s) for s in expected_slots}

        if existing_slot_set == expected_slot_set and not has_metadata_mismatch:
            result.fully_allocated_bookings += 1
        else:
            result.incomplete_allocations += 1
            if not dry_run and not booking_has_collision:
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
