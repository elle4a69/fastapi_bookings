"""Scheduling service engine.

This is the central scheduling engine. It calculates provider availability and routes
all resource allocation and hold actions to highly cohesive submodule services.
All file sizes are strictly kept under 250 lines to comply with workspace policies.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, time
from typing import List, Optional

from sqlalchemy.orm import Session

from ..models import (
    Service,
    Provider,
    Location,
    Booking,
    BlockedTime,
    ProviderWorkDay,
    ProviderSpecialDay,
    ReservedTime,
    Hold,
    HoldStatus,
)
from ..core.state_machine import BookingStatus

# Expose refactored submodule functions for backwards compatibility and clean routing
from .resource_service import (
    find_available_resources,
    allocate_resources,
    release_resources,
)
from .hold_service import (
    create_hold,
    expire_holds,
    promote_waitlist,
)

# Import extracted utility functions to keep file under 250 lines
from .scheduling_utils import parse_working_hours, check_slot_overlaps


def compute_availability(
    db: Session,
    *,
    service: Service,
    provider: Optional[Provider] = None,
    location: Optional[Location] = None,
    start_time: datetime,
    end_time: datetime,
    desired_duration: Optional[int] = None,
) -> List[dict]:
    """Compute available timezone-aware UTC slots for a service.

    Scans day-by-day in the UTC search window [start_time, end_time] and returns
    all valid time slots matching provider working rules, overrides, and resource availability.
    """
    # Enforce UTC timezone-awareness on search window boundaries
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    # Step 1: Gather candidate providers
    providers: List[Provider] = []
    if provider:
        providers = [provider]
    else:
        # Use explicit service-provider associations if they exist
        if service.providers:
            providers = [sp.provider for sp in service.providers]
        else:
            # Fallback to all active providers belonging to the same tenant
            providers = (
                db.query(Provider)
                .filter(Provider.tenant_id == service.tenant_id, Provider.active.is_(True))
                .all()
            )

    results: List[dict] = []

    # Step 2: Loop day-by-day from start_time.date() to end_time.date()
    current_date = start_time.date()
    end_date = end_time.date()

    while current_date <= end_date:
        for prov in providers:
            if not prov.active:
                continue

            # Step 3: Check ProviderSpecialDay overrides and ProviderWorkDay weekly schedules
            special_day = (
                db.query(ProviderSpecialDay)
                .filter(
                    ProviderSpecialDay.tenant_id == prov.tenant_id,
                    ProviderSpecialDay.date == current_date,
                    ProviderSpecialDay.provider_id == prov.id,
                )
                .first()
            )
            if not special_day:
                special_day = (
                    db.query(ProviderSpecialDay)
                    .filter(
                        ProviderSpecialDay.tenant_id == prov.tenant_id,
                        ProviderSpecialDay.date == current_date,
                        ProviderSpecialDay.provider_id.is_(None),
                    )
                    .first()
                )

            working_start = None
            working_end = None
            is_working_day = False

            if special_day:
                if special_day.is_working:
                    is_working_day = True
                    working_start, working_end = parse_working_hours(
                        current_date, special_day.start_time, special_day.end_time
                    )
            else:
                # Check normal weekly workday rules
                weekday_num = current_date.weekday()
                work_day = (
                    db.query(ProviderWorkDay)
                    .filter(
                        ProviderWorkDay.tenant_id == prov.tenant_id,
                        ProviderWorkDay.weekday == weekday_num,
                        ProviderWorkDay.provider_id == prov.id,
                    )
                    .first()
                )
                if not work_day:
                    work_day = (
                        db.query(ProviderWorkDay)
                        .filter(
                            ProviderWorkDay.tenant_id == prov.tenant_id,
                            ProviderWorkDay.weekday == weekday_num,
                            ProviderWorkDay.provider_id.is_(None),
                        )
                        .first()
                    )

                if work_day and work_day.is_working:
                    is_working_day = True
                    working_start, working_end = parse_working_hours(
                        current_date, work_day.start_time, work_day.end_time
                    )

            if not is_working_day or working_start is None or working_end is None:
                continue

            # Step 4: Clamp the identified working window to the search window [start_time, end_time]
            working_start = max(working_start, start_time)
            working_end = min(working_end, end_time)

            if working_start >= working_end:
                continue

            # Step 5: Determine candidate slot starts
            duration_minutes = desired_duration or service.duration
            if duration_minutes <= 0:
                continue
            duration = timedelta(minutes=duration_minutes)

            candidate_starts: List[datetime] = []
            if service.fixed_start_times:
                for time_str in service.fixed_start_times.split(','):
                    time_str = time_str.strip()
                    if not time_str:
                        continue
                    h, m = map(int, time_str.split(':'))
                    slot_start = datetime.combine(current_date, time(h, m)).replace(tzinfo=timezone.utc)
                    if slot_start >= working_start and slot_start + duration <= working_end:
                        candidate_starts.append(slot_start)
            else:
                current_slot = working_start
                while current_slot + duration <= working_end:
                    candidate_starts.append(current_slot)
                    current_slot += timedelta(minutes=15)

            if not candidate_starts:
                continue

            # Step 6: Query overlapping constraints once per day/provider for peak high-performance
            now_utc = datetime.now(timezone.utc)
            margin_start = working_start - timedelta(hours=4)
            margin_end = working_end + timedelta(hours=4)

            active_bookings = (
                db.query(Booking)
                .filter(
                    Booking.provider_id == prov.id,
                    Booking.status != BookingStatus.CANCELLED,
                    Booking.end_time > margin_start,
                    Booking.start_time < margin_end,
                )
                .all()
            )

            provider_blocked = (
                db.query(BlockedTime)
                .filter(
                    BlockedTime.tenant_id == prov.tenant_id,
                    BlockedTime.active.is_(True),
                    BlockedTime.end_time > working_start,
                    BlockedTime.start_time < working_end,
                    (BlockedTime.provider_id == prov.id) | (BlockedTime.provider_id.is_(None)),
                )
                .all()
            )

            active_holds = (
                db.query(Hold)
                .filter(
                    Hold.tenant_id == prov.tenant_id,
                    Hold.status == HoldStatus.PENDING,
                    Hold.expires_at > now_utc,
                    Hold.end_time > working_start,
                    Hold.start_time < working_end,
                    (Hold.provider_id == prov.id) | (Hold.provider_id.is_(None)),
                )
                .all()
            )

            active_reservations = (
                db.query(ReservedTime)
                .filter(
                    ReservedTime.tenant_id == prov.tenant_id,
                    ReservedTime.end_time > working_start,
                    ReservedTime.start_time < working_end,
                    (ReservedTime.provider_id == prov.id) | (ReservedTime.provider_id.is_(None)),
                    (ReservedTime.expires_at.is_(None)) | (ReservedTime.expires_at > now_utc),
                )
                .all()
            )

            for slot_start in candidate_starts:
                slot_end = slot_start + duration

                # Check overlaps using the helper function
                if check_slot_overlaps(
                    slot_start,
                    slot_end,
                    active_bookings,
                    provider_blocked,
                    active_holds,
                    active_reservations,
                ):
                    continue

                # Check Resource Availability
                resources = find_available_resources(
                    db,
                    service=service,
                    start_time=slot_start,
                    end_time=slot_end,
                    provider=prov,
                    location=location,
                )

                if resources is not None:
                    flat_resources = []
                    for req_id, res_list in resources.items():
                        for res, qty in res_list:
                            flat_resources.append({"id": res.id, "name": res.name, "quantity": qty})

                    results.append(
                        {
                            "start_time": slot_start.isoformat(),
                            "end_time": slot_end.isoformat(),
                            "provider": {"id": prov.id, "name": prov.name},
                            "resources": flat_resources,
                        }
                    )

        current_date += timedelta(days=1)

    return results