"""Booking state machine definitions.

This module defines the possible states for a booking and helper
functions to validate transitions between states. Keeping state
transitions centralized helps enforce business rules consistently
throughout the application.
"""

from enum import Enum
from typing import Dict, List


class BookingStatus(str, Enum):
    """Enumeration of booking statuses."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


# Define allowed state transitions. Keys are current statuses and values
# are lists of statuses that are permitted to follow.
ALLOWED_TRANSITIONS: Dict[BookingStatus, List[BookingStatus]] = {
    BookingStatus.PENDING: [BookingStatus.CONFIRMED, BookingStatus.CANCELLED, BookingStatus.RESCHEDULED],
    BookingStatus.CONFIRMED: [BookingStatus.CANCELLED, BookingStatus.COMPLETED, BookingStatus.NO_SHOW, BookingStatus.RESCHEDULED],
    BookingStatus.CANCELLED: [],
    BookingStatus.COMPLETED: [],
    BookingStatus.NO_SHOW: [],
    BookingStatus.RESCHEDULED: [BookingStatus.CONFIRMED, BookingStatus.CANCELLED],
}


def is_valid_transition(current_status: BookingStatus, next_status: BookingStatus) -> bool:
    """Return True if ``next_status`` is a valid transition from ``current_status``."""
    return next_status in ALLOWED_TRANSITIONS.get(current_status, [])