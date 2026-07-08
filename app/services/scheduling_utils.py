"""Utility functions for the scheduling engine.

All files are kept strictly under 250 lines to comply with workspace policies.
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone, time
from typing import Tuple, List, Any


def parse_working_hours(
    current_date,
    start_str: str | None,
    end_str: str | None,
) -> Tuple[datetime, datetime]:
    """Parse and build timezone-aware UTC working start/end datetimes."""
    if start_str:
        h, m = map(int, start_str.split(':'))
        working_start = datetime.combine(current_date, time(h, m)).replace(tzinfo=timezone.utc)
    else:
        working_start = datetime.combine(current_date, time(0, 0)).replace(tzinfo=timezone.utc)

    if end_str:
        h, m = map(int, end_str.split(':'))
        working_end = datetime.combine(current_date, time(h, m)).replace(tzinfo=timezone.utc)
    else:
        working_end = datetime.combine(current_date, time(23, 59, 59)).replace(tzinfo=timezone.utc)

    return working_start, working_end


def check_slot_overlaps(
    slot_start: datetime,
    slot_end: datetime,
    active_bookings: List[Any],
    provider_blocked: List[Any],
    active_holds: List[Any],
    active_reservations: List[Any],
    new_buffer_before: int = 0,
    new_buffer_after: int = 0,
) -> bool:
    """Check if a time slot overlaps with active bookings, blocked periods, holds, or reservations."""
    padded_slot_start = slot_start - timedelta(minutes=new_buffer_before)
    padded_slot_end = slot_end + timedelta(minutes=new_buffer_after)

    # 1. Check overlaps with Bookings (considering buffer_before and buffer_after)
    for b in active_bookings:
        b_start = b.start_time
        if b_start.tzinfo is None:
            b_start = b_start.replace(tzinfo=timezone.utc)
        b_end = b.end_time
        if b_end.tzinfo is None:
            b_end = b_end.replace(tzinfo=timezone.utc)

        buf_before = b.service.buffer_before if (b.service and b.service.buffer_before) else 0
        buf_after = b.service.buffer_after if (b.service and b.service.buffer_after) else 0
        blocked_start = b_start - timedelta(minutes=buf_before)
        blocked_end = b_end + timedelta(minutes=buf_after)

        if blocked_start < padded_slot_end and blocked_end > padded_slot_start:
            return True

    # 2. Check overlaps with BlockedTime
    for bt in provider_blocked:
        bt_start = bt.start_time
        if bt_start.tzinfo is None:
            bt_start = bt_start.replace(tzinfo=timezone.utc)
        bt_end = bt.end_time
        if bt_end.tzinfo is None:
            bt_end = bt_end.replace(tzinfo=timezone.utc)
        if bt_start < padded_slot_end and bt_end > padded_slot_start:
            return True

    # 3. Check overlaps with unexpired Hold
    for h in active_holds:
        h_start = h.start_time
        if h_start.tzinfo is None:
            h_start = h_start.replace(tzinfo=timezone.utc)
        h_end = h.end_time
        if h_end.tzinfo is None:
            h_end = h_end.replace(tzinfo=timezone.utc)
        if h_start < padded_slot_end and h_end > padded_slot_start:
            return True

    # 4. Check overlaps with unexpired ReservedTime
    for r in active_reservations:
        r_start = r.start_time
        if r_start.tzinfo is None:
            r_start = r_start.replace(tzinfo=timezone.utc)
        r_end = r.end_time
        if r_end.tzinfo is None:
            r_end = r_end.replace(tzinfo=timezone.utc)
        if r_start < padded_slot_end and r_end > padded_slot_start:
            return True

    return False
