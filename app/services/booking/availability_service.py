"""Availability calculation and backward-chaining engine.

Supports Phase 3 5-segment operational windows:
[Inbound Operational Travel] -> [Pre-Buffer] -> [Client Service] -> [Post-Buffer] -> [Onward Operational Travel]

Enforces Canonical Ownership Rule:
- Destination booking owns inbound travel leg (B owns A -> B).
- Avoids double-counting travel.
- For last booking of the day, onward travel is transit back to provider base.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, time
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ...models import (
    Service,
    Provider,
    Location,
    Booking,
    BookingSlotAllocation,
    BlockedTime,
    ReservedTime,
)
from ...core.state_machine import BookingStatus
from .operational_window import (
    OperationalWindow,
    get_operational_window_calculator,
    normalize_to_utc,
)
from ..resource_service import find_available_resources

logger = logging.getLogger(__name__)


def evaluate_outcall_day_slots(
    db: Session,
    *,
    prov: Provider,
    service: Service,
    current_date: datetime.date,
    working_start: datetime,
    working_end: datetime,
    duration_minutes: int,
    active_bookings: List[Booking],
    provider_blocked: List[BlockedTime],
    active_reservations: List[ReservedTime],
    destination: Optional[str] = None,
    location: Optional[Location] = None,
) -> List[Dict[str, Any]]:
    """Evaluate candidate out-call slots for a single provider on a day using backward chaining."""
    # 1. Capability check
    if not getattr(prov, "allow_out_call", True) or not getattr(service, "allow_out_call", True):
        return []

    calc = get_operational_window_calculator()
    base_origin = (
        getattr(prov, "in_call_address", None)
        or (getattr(prov.tenant, "address", None) if getattr(prov, "tenant", None) else None)
        or (-33.8688, 151.2093)
    )
    effective_dest = destination or base_origin

    # 2. Provider Out-Call Radius Check
    base_transit = calc.travel_calc.calculate_operational_travel_sync(base_origin, effective_dest)
    max_radius_km = float(getattr(prov, "out_call_radius_km", 25.0) or 25.0)
    if base_transit.distance_km > max_radius_km:
        return []

    duration = timedelta(minutes=duration_minutes)
    pre_buf = getattr(service, "outcall_buffer_before", 0) or 0
    post_buf = getattr(service, "outcall_buffer_after", 0) or 0

    # 3. Filter provider's active bookings on this calendar day, sorted by start_time
    day_bookings = sorted(
        [
            b for b in active_bookings
            if normalize_to_utc(b.start_time).date() == current_date
            and b.provider_id == prov.id
        ],
        key=lambda b: normalize_to_utc(b.start_time),
    )

    results: List[Dict[str, Any]] = []
    current_slot = working_start

    while current_slot + duration <= working_end:
        slot_start = current_slot
        slot_end = slot_start + duration

        # 4. Backward-Chaining: Identify preceding booking and expected origin
        prev_b: Optional[Booking] = None
        for b in day_bookings:
            if normalize_to_utc(b.end_time) <= slot_start:
                prev_b = b
            else:
                break

        if prev_b:
            prev_loc = prev_b.service_address or prev_b.client_suburb or getattr(prov, "in_call_address", None) or base_origin
            prev_post = getattr(prev_b.service, "outcall_buffer_after", 0) if (prev_b.service and getattr(prev_b, "service_mode", None) == "out_call") else (prev_b.service.buffer_after if prev_b.service else 15)
            provider_free_time = normalize_to_utc(prev_b.end_time) + timedelta(minutes=prev_post)
        else:
            prev_loc = base_origin
            provider_free_time = working_start

        # Calculate transit duration from previous location
        inbound_seg = calc.travel_calc.calculate_operational_travel_sync(prev_loc, effective_dest)
        inbound_mins = float(inbound_seg.duration_minutes)

        # Backward-chain from requested start time:
        # operational_window_start = slot_start - outcall_buffer_before - inbound_travel_minutes
        operational_window_start = slot_start - timedelta(minutes=(pre_buf + inbound_mins))

        # Verify provider is completely free and unencumbered starting from operational_window_start
        if operational_window_start < provider_free_time:
            # Slot is physically impossible because travel/buffer collides with preceding booking or day start.
            # Shift candidate slots forward to the next valid operational window
            earliest_possible = provider_free_time + timedelta(minutes=(inbound_mins + pre_buf))
            rem = earliest_possible.minute % 15
            if rem > 0 or earliest_possible.second > 0 or earliest_possible.microsecond > 0:
                shift_mins = 15 - rem
                next_valid_slot = (earliest_possible + timedelta(minutes=shift_mins)).replace(second=0, microsecond=0)
            else:
                next_valid_slot = earliest_possible.replace(second=0, microsecond=0)

            current_slot = max(current_slot + timedelta(minutes=15), next_valid_slot)
            continue

        # 5. Check collision with BlockedTime & ReservedTime
        has_blocked_conflict = False
        for bt in provider_blocked:
            bt_start = normalize_to_utc(bt.start_time)
            bt_end = normalize_to_utc(bt.end_time)
            if operational_window_start < bt_end and slot_end > bt_start:
                has_blocked_conflict = True
                break
        if has_blocked_conflict:
            current_slot += timedelta(minutes=15)
            continue

        for rt in active_reservations:
            rt_start = normalize_to_utc(rt.start_time)
            rt_end = normalize_to_utc(rt.end_time)
            if operational_window_start < rt_end and slot_end > rt_start:
                has_blocked_conflict = True
                break
        if has_blocked_conflict:
            current_slot += timedelta(minutes=15)
            continue

        # 6. Check forward gap to next booking
        next_b: Optional[Booking] = None
        for b in day_bookings:
            if normalize_to_utc(b.start_time) >= slot_end:
                next_b = b
                break

        if next_b:
            next_loc = next_b.service_address or next_b.client_suburb or getattr(prov, "in_call_address", None) or base_origin
            next_pre = getattr(next_b.service, "outcall_buffer_before", 0) if (next_b.service and getattr(next_b, "service_mode", None) == "out_call") else (next_b.service.buffer_before if next_b.service else 15)
            onward_seg = calc.travel_calc.calculate_operational_travel_sync(effective_dest, next_loc)
            onward_mins = float(onward_seg.duration_minutes)

            # Forward gap must fit: [post_buffer] + [transit(A -> B)] + [next_pre_buffer]
            required_gap_end = slot_end + timedelta(minutes=(post_buf + onward_mins + next_pre))
            if required_gap_end > normalize_to_utc(next_b.start_time):
                current_slot += timedelta(minutes=15)
                continue
            onward_dest_label = next_loc
        else:
            # Last booking of day: transit back to provider base
            return_seg = calc.travel_calc.calculate_operational_travel_sync(effective_dest, base_origin)
            return_mins = float(return_seg.duration_minutes)
            operational_window_end = slot_end + timedelta(minutes=(post_buf + return_mins))
            if operational_window_end > working_end:
                current_slot += timedelta(minutes=15)
                continue
            onward_mins = return_mins
            onward_dest_label = str(base_origin)

        # 7. Check Resource Availability
        resources = find_available_resources(
            db,
            service=service,
            start_time=slot_start,
            end_time=slot_end,
            provider=prov,
            location=location,
        )
        if resources is None:
            current_slot += timedelta(minutes=15)
            continue

        # 8. Build detailed 5-segment OperationalWindow
        window = calc.calculate_window(
            provider=prov,
            service=service,
            client_start=slot_start,
            client_end=slot_end,
            service_mode="out_call",
            destination=effective_dest,
            previous_location=prev_loc if prev_b else None,
            next_location=next_loc if next_b else None,
            inbound_travel_override=inbound_mins,
            outbound_travel_override=0.0 if next_b else onward_mins,
        )

        flat_resources = []
        for req_id, res_list in resources.items():
            for res, qty in res_list:
                flat_resources.append({"id": res.id, "name": res.name, "quantity": qty})

        results.append({
            "start_time": slot_start.isoformat(),
            "end_time": slot_end.isoformat(),
            "provider": {"id": prov.id, "name": prov.name},
            "resources": flat_resources,
            "operational_window": window.to_dict(),
        })

        current_slot += timedelta(minutes=15)

    return results


def get_available_slots(
    db: Session,
    service_duration: int,
    provider_id: int,
    date: datetime,
    service_id: int | None = None,
    service_mode: str = "in_call",
    client_suburb: Optional[str] = None,
    service_address: Optional[str] = None,
    client_postcode: Optional[str] = None,
) -> List[dict]:
    """Return available time slots for a provider on a given date.

    Supports both in-call (100% backward compatible) and out-call (5-segment operational window)
    scheduling modes.
    """
    from ..scheduling_service import compute_availability

    provider = db.query(Provider).filter(Provider.id == provider_id, Provider.deleted_at.is_(None)).first()
    if not provider:
        return []

    service_query = db.query(Service).filter(
        Service.tenant_id == provider.tenant_id,
        Service.active.is_(True),
        Service.deleted_at.is_(None),
    )
    if service_id is not None:
        service_query = service_query.filter(Service.id == service_id)
        service = service_query.first()
    else:
        services = service_query.limit(2).all()
        service = services[0] if len(services) == 1 else None
    if not service:
        return []

    date_utc = normalize_to_utc(date)
    start_time = datetime.combine(date_utc.date(), time.min).replace(tzinfo=timezone.utc)
    end_time = datetime.combine(date_utc.date(), time.max).replace(tzinfo=timezone.utc)

    slots = compute_availability(
        db,
        service=service,
        provider=provider,
        start_time=start_time,
        end_time=end_time,
        desired_duration=service_duration,
        service_mode=service_mode,
        client_suburb=client_suburb,
        service_address=service_address,
        client_postcode=client_postcode,
    )

    compatible_slots = []
    for slot in slots:
        slot_dict = {
            "start": datetime.fromisoformat(slot["start_time"]),
            "end": datetime.fromisoformat(slot["end_time"]),
        }
        if "operational_window" in slot:
            slot_dict["operational_window"] = slot["operational_window"]
        compatible_slots.append(slot_dict)

    return compatible_slots
