"""Availability calculation service (compatibility re-export).

All functionality has been elevated to app.services.booking.availability_service
to support Phase 3 5-segment operational windows:
[Inbound Operational Travel] -> [Pre-Buffer] -> [Client Service] -> [Post-Buffer] -> [Onward Operational Travel]
"""

from .booking.availability_service import (
    get_available_slots,
    evaluate_outcall_day_slots,
)

__all__ = [
    "get_available_slots",
    "evaluate_outcall_day_slots",
]
