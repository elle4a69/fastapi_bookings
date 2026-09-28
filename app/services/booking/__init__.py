"""Booking domain services module.

Provides:
- 5-segment operational window calculation (operational_window.py)
- Backward-chaining availability search (availability_service.py)
- Atomic operational slot allocation (slot_allocation_service.py)
"""

from .operational_window import (
    OperationalWindow,
    OperationalSegment,
    OperationalWindowCalculator,
    get_operational_window_calculator,
    normalize_to_utc,
)
from .availability_service import (
    get_available_slots,
    evaluate_outcall_day_slots,
)
from .slot_allocation_service import (
    SLOT_GRANULARITY_MINUTES,
    DEFAULT_MIN_BUFFER_MINUTES,
    SlotAllocationIntegrityError,
    SlotAllocationAuditResult,
    is_slot_allocation_conflict,
    generate_slot_timestamps,
    generate_operational_slot_timestamps,
    create_allocations_for_booking,
    release_allocations_for_booking,
    reschedule_allocations_for_booking,
    audit_and_repair_slot_allocations,
    backfill_slot_allocations,
)
from .itinerary_service import (
    recalculate_provider_itinerary,
    get_provider_itinerary_conflicts,
    resolve_provider_shift,
)

__all__ = [
    "OperationalWindow",
    "OperationalSegment",
    "OperationalWindowCalculator",
    "get_operational_window_calculator",
    "normalize_to_utc",
    "get_available_slots",
    "evaluate_outcall_day_slots",
    "SLOT_GRANULARITY_MINUTES",
    "DEFAULT_MIN_BUFFER_MINUTES",
    "SlotAllocationIntegrityError",
    "SlotAllocationAuditResult",
    "is_slot_allocation_conflict",
    "generate_slot_timestamps",
    "generate_operational_slot_timestamps",
    "create_allocations_for_booking",
    "release_allocations_for_booking",
    "reschedule_allocations_for_booking",
    "audit_and_repair_slot_allocations",
    "backfill_slot_allocations",
    "recalculate_provider_itinerary",
    "get_provider_itinerary_conflicts",
    "resolve_provider_shift",
]
