"""Operational Window Engine for 5-Segment In-Call & Out-Call Scheduling.

5-Segment Window Architecture:
[Inbound Operational Travel] -> [Pre-Buffer] -> [Client Service] -> [Post-Buffer] -> [Onward Operational Travel]

Canonical Ownership Rule:
- Destination booking owns its inbound travel leg (Booking B owns A -> B).
- Avoid double-counting travel.
- For last booking of the day, onward travel is transit back to provider base.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, time
import math
from typing import Any, Dict, List, Optional, Tuple

from ...models.booking import Booking
from ...models.provider import Provider
from ...models.service import Service
from ...core.state_machine import BookingStatus
from ..routing.travel_service import TravelCalculationService


def normalize_to_utc(dt: datetime) -> datetime:
    """Normalize datetime to timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class OperationalSegment:
    """A single segment within the 5-segment operational window."""
    name: str  # inbound_travel, pre_buffer, client_service, post_buffer, onward_travel
    start_time: datetime
    end_time: datetime
    duration_minutes: float
    location: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_minutes": round(self.duration_minutes, 1),
            "location": self.location,
        }


@dataclass
class OperationalWindow:
    """Encapsulates the 5-segment operational window for an appointment."""
    service_mode: str  # in_call or out_call
    client_start: datetime
    client_end: datetime
    inbound_travel_minutes: float = 0.0
    pre_buffer_minutes: int = 0
    service_duration_minutes: int = 0
    post_buffer_minutes: int = 0
    onward_travel_minutes: float = 0.0
    operational_window_start: datetime = field(init=False)
    operational_window_end: datetime = field(init=False)
    inbound_origin: Optional[str] = None
    destination: Optional[str] = None
    onward_destination: Optional[str] = None
    segments: List[OperationalSegment] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.client_start = normalize_to_utc(self.client_start)
        self.client_end = normalize_to_utc(self.client_end)

        inbound_total = self.pre_buffer_minutes + self.inbound_travel_minutes
        outbound_total = self.post_buffer_minutes + self.onward_travel_minutes

        self.operational_window_start = self.client_start - timedelta(minutes=inbound_total)
        self.operational_window_end = self.client_end + timedelta(minutes=outbound_total)

        if not self.segments:
            self._build_segments()

    def _build_segments(self) -> None:
        """Construct the 5 discrete chronological segments."""
        segs: List[OperationalSegment] = []

        # 1. Inbound Travel
        t_inbound_end = self.client_start - timedelta(minutes=self.pre_buffer_minutes)
        if self.inbound_travel_minutes > 0:
            segs.append(
                OperationalSegment(
                    name="inbound_travel",
                    start_time=self.operational_window_start,
                    end_time=t_inbound_end,
                    duration_minutes=self.inbound_travel_minutes,
                    location=self.inbound_origin,
                )
            )

        # 2. Pre-Buffer
        if self.pre_buffer_minutes > 0:
            segs.append(
                OperationalSegment(
                    name="pre_buffer",
                    start_time=t_inbound_end,
                    end_time=self.client_start,
                    duration_minutes=float(self.pre_buffer_minutes),
                )
            )

        # 3. Client Service
        client_dur = (self.client_end - self.client_start).total_seconds() / 60.0
        segs.append(
            OperationalSegment(
                name="client_service",
                start_time=self.client_start,
                end_time=self.client_end,
                duration_minutes=client_dur,
                location=self.destination,
            )
        )

        # 4. Post-Buffer
        t_post_end = self.client_end + timedelta(minutes=self.post_buffer_minutes)
        if self.post_buffer_minutes > 0:
            segs.append(
                OperationalSegment(
                    name="post_buffer",
                    start_time=self.client_end,
                    end_time=t_post_end,
                    duration_minutes=float(self.post_buffer_minutes),
                )
            )

        # 5. Onward Travel
        if self.onward_travel_minutes > 0:
            segs.append(
                OperationalSegment(
                    name="onward_travel",
                    start_time=t_post_end,
                    end_time=self.operational_window_end,
                    duration_minutes=self.onward_travel_minutes,
                    location=self.onward_destination,
                )
            )

        self.segments = segs

    def overlaps(self, other_start: datetime, other_end: datetime) -> bool:
        """Check if an external interval overlaps with this operational window."""
        o_start = normalize_to_utc(other_start)
        o_end = normalize_to_utc(other_end)
        return self.operational_window_start < o_end and self.operational_window_end > o_start

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_mode": self.service_mode,
            "operational_window_start": self.operational_window_start.isoformat(),
            "operational_window_end": self.operational_window_end.isoformat(),
            "client_start": self.client_start.isoformat(),
            "client_end": self.client_end.isoformat(),
            "inbound_travel_minutes": self.inbound_travel_minutes,
            "pre_buffer_minutes": self.pre_buffer_minutes,
            "service_duration_minutes": self.service_duration_minutes,
            "post_buffer_minutes": self.post_buffer_minutes,
            "onward_travel_minutes": self.onward_travel_minutes,
            "inbound_origin": self.inbound_origin,
            "destination": self.destination,
            "onward_destination": self.onward_destination,
            "segments": [s.to_dict() for s in self.segments],
        }


class OperationalWindowCalculator:
    """Service calculating 5-segment operational windows."""

    def __init__(self, travel_calc: Optional[TravelCalculationService] = None) -> None:
        self.travel_calc = travel_calc or TravelCalculationService()

    def calculate_window(
        self,
        *,
        provider: Provider,
        service: Service,
        client_start: datetime,
        client_end: datetime,
        service_mode: str = "in_call",
        destination: Optional[str] = None,
        previous_location: Optional[str] = None,
        next_location: Optional[str] = None,
        inbound_travel_override: Optional[float] = None,
        outbound_travel_override: Optional[float] = None,
    ) -> OperationalWindow:
        """Calculate complete 5-segment operational window for an appointment."""
        client_start = normalize_to_utc(client_start)
        client_end = normalize_to_utc(client_end)
        service_dur = int((client_end - client_start).total_seconds() / 60.0)

        # In-call path: 100% backward-compatible
        if service_mode != "out_call":
            buf_before = service.buffer_before if service and service.buffer_before else 0
            buf_after = service.buffer_after if service and service.buffer_after else 0
            return OperationalWindow(
                service_mode="in_call",
                client_start=client_start,
                client_end=client_end,
                inbound_travel_minutes=0.0,
                pre_buffer_minutes=buf_before,
                service_duration_minutes=service_dur,
                post_buffer_minutes=buf_after,
                onward_travel_minutes=0.0,
                destination=provider.in_call_address or "Provider Base",
            )

        # Out-call path
        pre_buf = getattr(service, "outcall_buffer_before", 0) or 0
        post_buf = getattr(service, "outcall_buffer_after", 0) or 0

        base_loc = (
            provider.in_call_address
            or (getattr(provider.tenant, "address", None) if getattr(provider, "tenant", None) else None)
            or (-33.8688, 151.2093)
        )
        effective_dest = destination or base_loc

        # 1. Inbound Travel Leg
        if inbound_travel_override is not None:
            inbound_mins = float(inbound_travel_override)
            inbound_origin = previous_location or str(base_loc)
        else:
            inbound_origin = previous_location or str(base_loc)
            seg_in = self.travel_calc.calculate_operational_travel_sync(inbound_origin, effective_dest)
            inbound_mins = float(seg_in.duration_minutes)

        # 2. Onward Travel Leg (Canonical Ownership Rule)
        if outbound_travel_override is not None:
            onward_mins = float(outbound_travel_override)
            onward_dest = next_location or str(base_loc)
        elif next_location:
            # Canonical ownership: destination owns inbound leg, so next booking owns transit to next_location
            onward_mins = 0.0
            onward_dest = next_location
        else:
            # Last booking of day: transit back to provider base
            onward_dest = str(base_loc)
            seg_out = self.travel_calc.calculate_operational_travel_sync(effective_dest, base_loc)
            onward_mins = float(seg_out.duration_minutes)

        return OperationalWindow(
            service_mode="out_call",
            client_start=client_start,
            client_end=client_end,
            inbound_travel_minutes=inbound_mins,
            pre_buffer_minutes=pre_buf,
            service_duration_minutes=service_dur,
            post_buffer_minutes=post_buf,
            onward_travel_minutes=onward_mins,
            inbound_origin=str(inbound_origin),
            destination=str(effective_dest),
            onward_destination=str(onward_dest),
        )


_DEFAULT_CALCULATOR = OperationalWindowCalculator()


def get_operational_window_calculator() -> OperationalWindowCalculator:
    return _DEFAULT_CALCULATOR
