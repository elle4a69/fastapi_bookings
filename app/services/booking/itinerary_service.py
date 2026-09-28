"""Dynamic Itinerary Recalculation Engine & Conflict Sentinel.

Phase 4 Implementation:
- Dynamic itinerary recalculation upon booking lifecycle events (create, confirm, cancel, reschedule, update).
- Backward expansion of operational windows and discrete slot allocations.
- Feasibility evaluation against provider working hours and preceding bookings.
- Administrative Conflict Sentinel for unresolvable itinerary overlaps.
- Invariant: Billing snapshot (booking.chargeable_travel_fee) is strictly preserved.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, time, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models.booking import Booking
from ...models.booking_slot_allocation import BookingSlotAllocation
from ...models.provider import Provider
from ...models.schedule import ProviderWorkDay, ProviderSpecialDay
from ...core.state_machine import BookingStatus
from ...schemas.itinerary import (
    ItineraryConflict,
    ItineraryLeg,
    ItineraryRecalculationResult,
)
from ..routing.travel_service import TravelCalculationService
from .operational_window import (
    get_operational_window_calculator,
    normalize_to_utc,
)
from .slot_allocation_service import (
    generate_operational_slot_timestamps,
    is_slot_allocation_conflict,
)
from ..scheduling_utils import parse_working_hours

logger = logging.getLogger(__name__)


def resolve_provider_shift(
    db: Session,
    provider: Provider,
    target_date: date,
) -> Tuple[bool, Optional[datetime], Optional[datetime]]:
    """Determine whether the provider is scheduled to work on target_date and return shift start and end (UTC).

    Resolution precedence:
    1. ProviderSpecialDay specific to provider.
    2. ProviderSpecialDay company override (if not provider.ignore_company_hours).
    3. ProviderWorkDay recurring rule specific to provider.
    4. ProviderWorkDay company template (if not provider.ignore_company_hours).
    5. Fallback: If no schedule records exist at all, provider is considered available all day (00:00 - 23:59:59).
    """
    # 1 & 2: Special day check
    special_day = (
        db.query(ProviderSpecialDay)
        .filter(
            ProviderSpecialDay.tenant_id == provider.tenant_id,
            ProviderSpecialDay.date == target_date,
            ProviderSpecialDay.provider_id == provider.id,
        )
        .first()
    )
    if not special_day and not provider.ignore_company_hours:
        special_day = (
            db.query(ProviderSpecialDay)
            .filter(
                ProviderSpecialDay.tenant_id == provider.tenant_id,
                ProviderSpecialDay.date == target_date,
                ProviderSpecialDay.provider_id.is_(None),
            )
            .first()
        )

    if special_day:
        if special_day.is_working:
            s_start, s_end = parse_working_hours(target_date, special_day.start_time, special_day.end_time)
            return True, s_start, s_end
        return False, None, None

    # 3 & 4: Workday check
    weekday_num = target_date.weekday()
    work_day = (
        db.query(ProviderWorkDay)
        .filter(
            ProviderWorkDay.tenant_id == provider.tenant_id,
            ProviderWorkDay.weekday == weekday_num,
            ProviderWorkDay.provider_id == provider.id,
        )
        .first()
    )
    if not work_day and not provider.ignore_company_hours:
        work_day = (
            db.query(ProviderWorkDay)
            .filter(
                ProviderWorkDay.tenant_id == provider.tenant_id,
                ProviderWorkDay.weekday == weekday_num,
                ProviderWorkDay.provider_id.is_(None),
            )
            .first()
        )

    if work_day:
        if work_day.is_working:
            s_start, s_end = parse_working_hours(target_date, work_day.start_time, work_day.end_time)
            return True, s_start, s_end
        return False, None, None

    # 5. Check if any workdays or special days exist for provider at all
    has_any_schedule = (
        db.query(ProviderWorkDay)
        .filter(
            ProviderWorkDay.tenant_id == provider.tenant_id,
            (ProviderWorkDay.provider_id == provider.id) | (ProviderWorkDay.provider_id.is_(None)),
        )
        .count()
        > 0
    )
    if has_any_schedule:
        # Provider has defined workdays, but none matched this weekday -> day off
        return False, None, None

    # No schedule records configured -> default open 24 hours
    day_start = datetime.combine(target_date, time.min).replace(tzinfo=timezone.utc)
    day_end = datetime.combine(target_date, time.max).replace(tzinfo=timezone.utc)
    return True, day_start, day_end


def _synchronize_booking_slot_allocations(
    db: Session,
    booking: Booking,
    operational_window_start: datetime,
    operational_window_end: datetime,
) -> int:
    """Atomically synchronize 15-minute slot allocations for a booking across its updated operational window."""
    target_slots = generate_operational_slot_timestamps(
        operational_window_start=operational_window_start,
        operational_window_end=operational_window_end,
    )
    target_slot_set = {normalize_to_utc(s) for s in target_slots}

    existing_allocations = (
        db.query(BookingSlotAllocation)
        .filter(BookingSlotAllocation.booking_id == booking.id)
        .all()
    )
    existing_slot_map = {
        normalize_to_utc(a.slot_start): a for a in existing_allocations
    }
    existing_slot_set = set(existing_slot_map.keys())

    # Release slots no longer required
    to_remove = existing_slot_set - target_slot_set
    if to_remove:
        db.query(BookingSlotAllocation).filter(
            BookingSlotAllocation.booking_id == booking.id,
            BookingSlotAllocation.slot_start.in_(list(to_remove)),
        ).delete(synchronize_session="fetch")

    # Add newly required slots
    to_add = target_slot_set - existing_slot_set
    for slot_time in sorted(to_add):
        alloc = BookingSlotAllocation(
            tenant_id=booking.tenant_id,
            booking_id=booking.id,
            provider_id=booking.provider_id,
            slot_start=slot_time,
        )
        db.add(alloc)

    return len(target_slots)


def recalculate_provider_itinerary(
    db: Session,
    provider_id: int,
    target_date: date | datetime,
    travel_calc: Optional[TravelCalculationService] = None,
) -> ItineraryRecalculationResult:
    """Recalculate dynamic itinerary, operational windows, and slot allocations for a provider on a given date.

    Preserves Billing Snapshot Invariant: booking.chargeable_travel_fee is NEVER modified.
    """
    if isinstance(target_date, datetime):
        d_date = target_date.date()
    else:
        d_date = target_date

    d_date_str = d_date.isoformat()

    provider = (
        db.query(Provider)
        .filter(Provider.id == provider_id, Provider.deleted_at.is_(None))
        .first()
    )
    if not provider:
        logger.warning("Provider %s not found for itinerary recalculation", provider_id)
        return ItineraryRecalculationResult(
            provider_id=provider_id,
            target_date=d_date_str,
            bookings_evaluated=0,
            has_conflicts=False,
            success=False,
        )

    t_calc = travel_calc or get_operational_window_calculator().travel_calc

    # 1. Resolve Provider Working Hours for target date
    is_working_day, shift_start, shift_end = resolve_provider_shift(db, provider, d_date)

    # 2. Query all non-cancelled, active bookings on this calendar day, sorted by start_time
    day_start = datetime.combine(d_date, time.min).replace(tzinfo=timezone.utc)
    day_end = datetime.combine(d_date, time.max).replace(tzinfo=timezone.utc)

    active_bookings = (
        db.query(Booking)
        .filter(
            Booking.provider_id == provider_id,
            Booking.status != BookingStatus.CANCELLED,
            Booking.start_time >= day_start,
            Booking.start_time <= day_end,
        )
        .order_by(Booking.start_time.asc())
        .all()
    )

    # Exclude any booking marked cancelled in current transaction/session
    active_bookings = [
        b for b in active_bookings
        if b.status not in (BookingStatus.CANCELLED, "CANCELLED", "cancelled")
    ]

    base_loc = (
        getattr(provider, "in_call_address", None)
        or (getattr(provider.tenant, "address", None) if getattr(provider, "tenant", None) else None)
        or "Sydney CBD"
    )

    itinerary_legs: List[ItineraryLeg] = []
    conflicts: List[ItineraryConflict] = []
    total_allocations_synced = 0

    prev_waypoint: str = str(base_loc)
    prev_free_time: datetime = shift_start if shift_start else day_start

    for idx, booking in enumerate(active_bookings):
        b_start_utc = normalize_to_utc(booking.start_time)
        b_end_utc = normalize_to_utc(booking.end_time)

        # -------------------------------------------------------------------
        # BILLING SNAPSHOT INVARIANT GUARANTEE
        # -------------------------------------------------------------------
        original_chargeable_fee = booking.chargeable_travel_fee
        original_chargeable_distance = booking.chargeable_travel_distance_km

        is_outcall = getattr(booking, "service_mode", None) == "out_call"

        if is_outcall:
            dest_waypoint = booking.service_address or booking.client_suburb or str(base_loc)
            pre_buf = getattr(booking.service, "outcall_buffer_before", 0) if booking.service else 0
            post_buf = getattr(booking.service, "outcall_buffer_after", 0) if booking.service else 0

            # Next booking check (Canonical Ownership Rule)
            next_b: Optional[Booking] = active_bookings[idx + 1] if idx + 1 < len(active_bookings) else None

            # Calculate inbound operational travel from preceding waypoint to destination
            inbound_transit = t_calc.calculate_operational_travel_sync(prev_waypoint, dest_waypoint)
            inbound_mins = float(inbound_transit.duration_minutes)
            inbound_dist = float(inbound_transit.distance_km)

            operational_window_start = b_start_utc - timedelta(minutes=(pre_buf + inbound_mins))

            if next_b is not None:
                # Canonical ownership: next booking owns transit to next booking
                onward_mins = 0.0
                onward_dist = 0.0
                operational_window_end = b_end_utc + timedelta(minutes=post_buf)
            else:
                # Last booking of the day: transit back to provider base
                return_transit = t_calc.calculate_operational_travel_sync(dest_waypoint, base_loc)
                onward_mins = float(return_transit.duration_minutes)
                onward_dist = float(return_transit.distance_km)
                operational_window_end = b_end_utc + timedelta(minutes=(post_buf + onward_mins))

            # ----------------------------------------------------------------
            # Feasibility Evaluation
            # ----------------------------------------------------------------
            conflict_reason: Optional[str] = None
            available_start: Optional[datetime] = None

            if not is_working_day:
                conflict_reason = f"Itinerary conflict: provider is not scheduled to work on {d_date_str}"
                available_start = None
            elif shift_start is not None and operational_window_start < shift_start:
                conflict_reason = (
                    f"Itinerary conflict: requires departure at {operational_window_start.strftime('%H:%M')}, "
                    f"but provider shift starts at {shift_start.strftime('%H:%M')}"
                )
                available_start = shift_start
            elif shift_end is not None and operational_window_end > shift_end:
                conflict_reason = (
                    f"Itinerary conflict: operational return window ends at {operational_window_end.strftime('%H:%M')}, "
                    f"but provider shift ends at {shift_end.strftime('%H:%M')}"
                )
                available_start = None
            elif idx > 0 and operational_window_start < prev_free_time:
                conflict_reason = (
                    f"Itinerary conflict: requires departure at {operational_window_start.strftime('%H:%M')}, "
                    f"but prior booking is occupied until {prev_free_time.strftime('%H:%M')}"
                )
                available_start = prev_free_time

            if conflict_reason:
                booking.has_itinerary_conflict = True
                booking.itinerary_conflict = conflict_reason
                conflicts.append(
                    ItineraryConflict(
                        booking_id=booking.id,
                        provider_id=provider.id,
                        target_date=d_date_str,
                        conflict_type="ITINERARY_CONFLICT",
                        reason=conflict_reason,
                        required_start=operational_window_start,
                        available_start=available_start,
                        details={
                            "inbound_minutes": inbound_mins,
                            "pre_buffer_minutes": pre_buf,
                            "post_buffer_minutes": post_buf,
                            "onward_minutes": onward_mins,
                            "preceding_waypoint": prev_waypoint,
                            "destination_waypoint": dest_waypoint,
                        },
                    )
                )
            else:
                # Feasible: clear conflict and synchronize slot allocations
                booking.has_itinerary_conflict = False
                booking.itinerary_conflict = None
                try:
                    count = _synchronize_booking_slot_allocations(
                        db, booking, operational_window_start, operational_window_end
                    )
                    total_allocations_synced += count
                except IntegrityError as exc:
                    if is_slot_allocation_conflict(exc):
                        db.rollback()
                        booking.has_itinerary_conflict = True
                        booking.itinerary_conflict = "Itinerary conflict: slot allocation unique constraint collision"
                        conflicts.append(
                            ItineraryConflict(
                                booking_id=booking.id,
                                provider_id=provider.id,
                                target_date=d_date_str,
                                conflict_type="SLOT_COLLISION",
                                reason=booking.itinerary_conflict,
                                required_start=operational_window_start,
                                available_start=None,
                            )
                        )

            # Record detailed chronological legs
            if inbound_mins > 0:
                t_in_end = operational_window_start + timedelta(minutes=inbound_mins)
                itinerary_legs.append(
                    ItineraryLeg(
                        booking_id=booking.id,
                        leg_type="inbound_travel",
                        origin=prev_waypoint,
                        destination=dest_waypoint,
                        start_time=operational_window_start,
                        end_time=t_in_end,
                        duration_minutes=inbound_mins,
                        distance_km=inbound_dist,
                    )
                )

            if pre_buf > 0:
                t_pre_start = b_start_utc - timedelta(minutes=pre_buf)
                itinerary_legs.append(
                    ItineraryLeg(
                        booking_id=booking.id,
                        leg_type="pre_buffer",
                        origin=dest_waypoint,
                        destination=dest_waypoint,
                        start_time=t_pre_start,
                        end_time=b_start_utc,
                        duration_minutes=float(pre_buf),
                    )
                )

            itinerary_legs.append(
                ItineraryLeg(
                    booking_id=booking.id,
                    leg_type="client_service",
                    origin=dest_waypoint,
                    destination=dest_waypoint,
                    start_time=b_start_utc,
                    end_time=b_end_utc,
                    duration_minutes=float((b_end_utc - b_start_utc).total_seconds() / 60.0),
                )
            )

            if post_buf > 0:
                t_post_end = b_end_utc + timedelta(minutes=post_buf)
                itinerary_legs.append(
                    ItineraryLeg(
                        booking_id=booking.id,
                        leg_type="post_buffer",
                        origin=dest_waypoint,
                        destination=dest_waypoint,
                        start_time=b_end_utc,
                        end_time=t_post_end,
                        duration_minutes=float(post_buf),
                    )
                )

            if onward_mins > 0:
                t_onward_start = b_end_utc + timedelta(minutes=post_buf)
                itinerary_legs.append(
                    ItineraryLeg(
                        booking_id=booking.id,
                        leg_type="onward_travel",
                        origin=dest_waypoint,
                        destination=str(base_loc),
                        start_time=t_onward_start,
                        end_time=operational_window_end,
                        duration_minutes=onward_mins,
                        distance_km=onward_dist,
                    )
                )

            prev_waypoint = dest_waypoint
            prev_free_time = b_end_utc + timedelta(minutes=post_buf)

        else:
            # In-Call Appointment (100% backward-compatible)
            in_call_loc = getattr(provider, "in_call_address", None) or str(base_loc)
            pre_buf = booking.service.buffer_before if (booking.service and booking.service.buffer_before) else 15
            post_buf = booking.service.buffer_after if (booking.service and booking.service.buffer_after) else 15
            operational_window_start = b_start_utc - timedelta(minutes=pre_buf)
            operational_window_end = b_end_utc + timedelta(minutes=post_buf)

            conflict_reason = None
            if not is_working_day:
                conflict_reason = f"Itinerary conflict: provider is not scheduled to work on {d_date_str}"
            elif shift_start is not None and operational_window_start < shift_start:
                conflict_reason = (
                    f"Itinerary conflict: requires preparation at {operational_window_start.strftime('%H:%M')}, "
                    f"but provider shift starts at {shift_start.strftime('%H:%M')}"
                )
            elif idx > 0 and operational_window_start < prev_free_time:
                conflict_reason = (
                    f"Itinerary conflict: booking buffer starts at {operational_window_start.strftime('%H:%M')}, "
                    f"but prior booking is occupied until {prev_free_time.strftime('%H:%M')}"
                )

            if conflict_reason:
                booking.has_itinerary_conflict = True
                booking.itinerary_conflict = conflict_reason
                conflicts.append(
                    ItineraryConflict(
                        booking_id=booking.id,
                        provider_id=provider.id,
                        target_date=d_date_str,
                        conflict_type="ITINERARY_CONFLICT",
                        reason=conflict_reason,
                        required_start=operational_window_start,
                        available_start=prev_free_time,
                    )
                )
            else:
                booking.has_itinerary_conflict = False
                booking.itinerary_conflict = None
                count = _synchronize_booking_slot_allocations(
                    db, booking, operational_window_start, operational_window_end
                )
                total_allocations_synced += count

            if pre_buf > 0:
                itinerary_legs.append(
                    ItineraryLeg(
                        booking_id=booking.id,
                        leg_type="pre_buffer",
                        origin=in_call_loc,
                        destination=in_call_loc,
                        start_time=operational_window_start,
                        end_time=b_start_utc,
                        duration_minutes=float(pre_buf),
                    )
                )

            itinerary_legs.append(
                ItineraryLeg(
                    booking_id=booking.id,
                    leg_type="client_service",
                    origin=in_call_loc,
                    destination=in_call_loc,
                    start_time=b_start_utc,
                    end_time=b_end_utc,
                    duration_minutes=float((b_end_utc - b_start_utc).total_seconds() / 60.0),
                )
            )

            if post_buf > 0:
                itinerary_legs.append(
                    ItineraryLeg(
                        booking_id=booking.id,
                        leg_type="post_buffer",
                        origin=in_call_loc,
                        destination=in_call_loc,
                        start_time=b_end_utc,
                        end_time=operational_window_end,
                        duration_minutes=float(post_buf),
                    )
                )

            prev_waypoint = in_call_loc
            prev_free_time = operational_window_end

        # -------------------------------------------------------------------
        # Enforce Billing Snapshot Invariant Post-Recalculation
        # -------------------------------------------------------------------
        assert booking.chargeable_travel_fee == original_chargeable_fee, (
            f"Billing Snapshot Invariant violated! Expected {original_chargeable_fee}, got {booking.chargeable_travel_fee}"
        )
        assert booking.chargeable_travel_distance_km == original_chargeable_distance, (
            f"Billing distance snapshot violated! Expected {original_chargeable_distance}, got {booking.chargeable_travel_distance_km}"
        )

    db.flush()

    return ItineraryRecalculationResult(
        provider_id=provider.id,
        target_date=d_date_str,
        bookings_evaluated=len(active_bookings),
        itinerary_legs=itinerary_legs,
        conflicts=conflicts,
        has_conflicts=len(conflicts) > 0,
        allocations_updated=total_allocations_synced,
        success=True,
    )


def get_provider_itinerary_conflicts(
    db: Session,
    provider_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    date_from: Optional[date | datetime] = None,
    date_to: Optional[date | datetime] = None,
) -> List[ItineraryConflict]:
    """Retrieve all flagged itinerary conflicts across bookings matching filters."""
    query = db.query(Booking).filter(
        Booking.has_itinerary_conflict.is_(True),
        Booking.status != BookingStatus.CANCELLED,
    )

    if tenant_id is not None:
        query = query.filter(Booking.tenant_id == tenant_id)
    if provider_id is not None:
        query = query.filter(Booking.provider_id == provider_id)
    if date_from is not None:
        d_from = date_from.date() if isinstance(date_from, datetime) else date_from
        start_utc = datetime.combine(d_from, time.min).replace(tzinfo=timezone.utc)
        query = query.filter(Booking.start_time >= start_utc)
    if date_to is not None:
        d_to = date_to.date() if isinstance(date_to, datetime) else date_to
        end_utc = datetime.combine(d_to, time.max).replace(tzinfo=timezone.utc)
        query = query.filter(Booking.start_time <= end_utc)

    flagged_bookings = query.order_by(Booking.start_time.asc()).all()

    conflicts: List[ItineraryConflict] = []
    for b in flagged_bookings:
        b_date = normalize_to_utc(b.start_time).date().isoformat()
        conflicts.append(
            ItineraryConflict(
                booking_id=b.id,
                provider_id=b.provider_id,
                target_date=b_date,
                conflict_type="ITINERARY_CONFLICT",
                reason=b.itinerary_conflict or "Itinerary conflict flagged on booking",
                required_start=None,
                available_start=None,
            )
        )

    return conflicts
