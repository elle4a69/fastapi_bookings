"""Pydantic models for bookings."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ..core.state_machine import BookingStatus


class BookingBase(BaseModel):
    client_id: int = Field(..., description="Identifier of the client")
    provider_id: int = Field(..., description="Identifier of the provider")
    service_id: int = Field(..., description="Identifier of the service")
    location_id: Optional[int] = Field(None, description="Identifier of the location")
    start_time: datetime = Field(..., description="Start time of the appointment")
    end_time: datetime = Field(..., description="End time of the appointment")
    notes: Optional[str] = Field(None, description="Notes attached to the booking")


class BookingCreate(BookingBase):
    pass


class BookingUpdate(BaseModel):
    provider_id: Optional[int] = None
    service_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[BookingStatus] = None
    notes: Optional[str] = None


class BookingInDBBase(BookingBase):
    id: int
    status: BookingStatus
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class Booking(BookingInDBBase):
    pass


class BookingListResponse(BaseModel):
    ok: bool
    data: list[Booking]
    meta: dict


class BookingResponse(BaseModel):
    ok: bool
    data: Booking


class ErrorResponse(BaseModel):
    ok: bool = False
    error: dict


class BookingReschedule(BaseModel):
    new_start: datetime = Field(..., description="New start time of the appointment")
    new_end: datetime = Field(..., description="New end time of the appointment")