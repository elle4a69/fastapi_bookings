"""Pydantic schemas for dynamic itinerary recalculation and conflict sentinel."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ItineraryLeg(BaseModel):
    """Represents a discrete chronological leg in a provider's daily itinerary."""
    model_config = ConfigDict(from_attributes=True)

    booking_id: Optional[int] = Field(None, description="Associated booking ID if applicable")
    leg_type: str = Field(..., description="Leg type: inbound_travel, pre_buffer, client_service, post_buffer, onward_travel")
    origin: Optional[str] = Field(None, description="Starting waypoint for transit legs")
    destination: Optional[str] = Field(None, description="Arrival waypoint for transit legs or service location")
    start_time: datetime = Field(..., description="Start of leg (UTC)")
    end_time: datetime = Field(..., description="End of leg (UTC)")
    duration_minutes: float = Field(..., description="Duration of leg in minutes")
    distance_km: Optional[float] = Field(None, description="Road distance in km for transit legs")


class ItineraryConflict(BaseModel):
    """Represents an unresolvable operational scheduling collision or itinerary violation."""
    model_config = ConfigDict(from_attributes=True)

    booking_id: int = Field(..., description="Booking ID experiencing the conflict")
    provider_id: int = Field(..., description="Provider ID")
    target_date: str = Field(..., description="Calendar date of the itinerary conflict (YYYY-MM-DD)")
    conflict_type: str = Field("ITINERARY_CONFLICT", description="Conflict classification code")
    reason: str = Field(..., description="Human-readable explanation of why the itinerary is infeasible")
    required_start: Optional[datetime] = Field(None, description="Required operational departure / window start time")
    available_start: Optional[datetime] = Field(None, description="Earliest available departure / shift start time")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Detailed diagnostic context")


class ItineraryRecalculationResult(BaseModel):
    """Aggregate result from dynamic provider itinerary recalculation."""
    model_config = ConfigDict(from_attributes=True)

    provider_id: int = Field(..., description="Provider ID evaluated")
    target_date: str = Field(..., description="Date evaluated (YYYY-MM-DD)")
    bookings_evaluated: int = Field(0, description="Total active bookings evaluated on that date")
    itinerary_legs: List[ItineraryLeg] = Field(default_factory=list, description="All operational legs scheduled for the day")
    conflicts: List[ItineraryConflict] = Field(default_factory=list, description="List of detected unresolvable itinerary conflicts")
    has_conflicts: bool = Field(False, description="True if any itinerary conflicts were detected")
    allocations_updated: int = Field(0, description="Number of slot allocation slices synchronized")
    success: bool = Field(True, description="Whether recalculation ran to completion")


class ItineraryRecalculateRequest(BaseModel):
    """Request payload to manually trigger itinerary recalculation for a provider and date."""
    model_config = ConfigDict(from_attributes=True)

    provider_id: int = Field(..., description="Provider ID")
    target_date: date = Field(..., description="Target date to recalculate (YYYY-MM-DD)")


class ItineraryConflictListResponse(BaseModel):
    """Response payload for administrative conflict queries."""
    model_config = ConfigDict(from_attributes=True)

    ok: bool = True
    conflicts: List[ItineraryConflict] = Field(default_factory=list)
    total: int = 0
