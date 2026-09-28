"""Slot allocation service (compatibility re-export).

All functionality has been elevated to app.services.booking.slot_allocation_service
to support Phase 3 5-segment operational windows:
[Inbound Operational Travel] -> [Pre-Buffer] -> [Client Service] -> [Post-Buffer] -> [Onward Operational Travel]
"""

from .booking.slot_allocation_service import (
    SLOT_GRANULARITY_MINUTES,
    DEFAULT_MIN_BUFFER_MINUTES,
    SlotAllocationIntegrityError,
    SlotAllocationAuditResult,
    is_slot_allocation_conflict,
    normalize_to_utc,
    generate_slot_timestamps,
    generate_operational_slot_timestamps,
    create_allocations_for_booking,
    release_allocations_for_booking,
    reschedule_allocations_for_booking,
    audit_and_repair_slot_allocations,
    backfill_slot_allocations,
)

__all__ = [
    "SLOT_GRANULARITY_MINUTES",
    "DEFAULT_MIN_BUFFER_MINUTES",
    "SlotAllocationIntegrityError",
    "SlotAllocationAuditResult",
    "is_slot_allocation_conflict",
    "normalize_to_utc",
    "generate_slot_timestamps",
    "generate_operational_slot_timestamps",
    "create_allocations_for_booking",
    "release_allocations_for_booking",
    "reschedule_allocations_for_booking",
    "audit_and_repair_slot_allocations",
    "backfill_slot_allocations",
]
