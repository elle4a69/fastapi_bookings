"""Availability schemas for in-call and out-call scheduling.

Supports Phase 3 5-segment operational windows:
[Inbound Operational Travel] -> [Pre-Buffer] -> [Client Service] -> [Post-Buffer] -> [Onward Operational Travel]
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class ServiceMode(str, Enum):
    IN_CALL = "in_call"
    OUT_CALL = "out_call"


class OperationalWindowSegment(BaseModel):
    """Details for a single segment of the 5-segment operational window."""
    name: str = Field(..., description="Segment identifier (inbound_travel, pre_buffer, client_service, post_buffer, onward_travel)")
    start_time: str = Field(..., description="ISO 8601 start timestamp")
    end_time: str = Field(..., description="ISO 8601 end timestamp")
    duration_minutes: float = Field(..., description="Duration in minutes")
    location: Optional[str] = Field(None, description="Location or waypoint for travel segments")


class OperationalWindowInfo(BaseModel):
    """Full 5-segment operational window breakdown."""
    operational_window_start: str = Field(..., description="Start of inbound travel / operational window")
    operational_window_end: str = Field(..., description="End of onward travel / operational window")
    client_start: str = Field(..., description="Visible appointment start")
    client_end: str = Field(..., description="Visible appointment end")
    service_mode: str = Field("in_call", description="Service mode (in_call or out_call)")
    inbound_travel_minutes: float = Field(0.0, description="Transit minutes immediately before appointment")
    pre_buffer_minutes: int = Field(0, description="Pre-service buffer minutes")
    service_duration_minutes: int = Field(..., description="Client service duration in minutes")
    post_buffer_minutes: int = Field(0, description="Post-service buffer minutes")
    onward_travel_minutes: float = Field(0.0, description="Transit minutes immediately after appointment")
    inbound_origin: Optional[str] = Field(None, description="Origin address or waypoint for inbound travel")
    destination: Optional[str] = Field(None, description="Destination appointment address or suburb")
    onward_destination: Optional[str] = Field(None, description="Destination for onward leg (next booking or base)")
    segments: Optional[List[OperationalWindowSegment]] = Field(None, description="Detailed breakdown of the 5 segments")


class TimeSlot(BaseModel):
    """Single available appointment time slot."""
    start: str = Field(..., description="ISO 8601 start timestamp for client appointment")
    end: str = Field(..., description="ISO 8601 end timestamp for client appointment")
    provider_id: Optional[int] = Field(None, description="Provider ID offering this slot")
    provider_name: Optional[str] = Field(None, description="Provider display name")
    operational_window: Optional[OperationalWindowInfo] = Field(
        None,
        description="Optional 5-segment operational window details for this slot",
    )


class AvailabilityQuery(BaseModel):
    """Availability search parameters."""
    service_id: int = Field(..., description="Service ID")
    provider_id: Optional[int] = Field(None, description="Optional specific Provider ID")
    date: datetime = Field(..., description="Requested date")
    service_mode: ServiceMode = Field(ServiceMode.IN_CALL, description="Delivery mode (in_call or out_call)")
    client_suburb: Optional[str] = Field(None, description="Client suburb for out-call transit resolution")
    service_address: Optional[str] = Field(None, description="Client street address for out-call transit resolution")
    client_postcode: Optional[str] = Field(None, description="Client postcode")


class AvailabilityResponse(BaseModel):
    """Standard API response for availability queries."""
    ok: bool = Field(True, description="Success status")
    data: List[TimeSlot] = Field(default_factory=list, description="List of available time slots")
