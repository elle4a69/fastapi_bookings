"""Pydantic models for bookings."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ..core.state_machine import BookingStatus


class ServiceMode(str, Enum):
    """Appointment delivery mode: in-call (client visits provider/location) or out-call (provider travels to client)."""
    IN_CALL = "in_call"
    OUT_CALL = "out_call"


class BookingBase(BaseModel):
    client_id: Optional[int] = Field(None, description="Identifier of the client")
    client_name: Optional[str] = Field(None, description="Name of the client for public bookings")
    client_email: Optional[str] = Field(None, description="Email of the client for public bookings")
    client_phone: Optional[str] = Field(None, description="Phone of the client for public bookings")
    provider_id: int = Field(..., description="Identifier of the provider")
    service_id: int = Field(..., description="Identifier of the service")
    location_id: Optional[int] = Field(None, description="Identifier of the location")
    start_time: datetime = Field(..., description="Start time of the appointment")
    end_time: datetime = Field(..., description="End time of the appointment")
    notes: Optional[str] = Field(None, description="Notes attached to the booking")
    idempotency_key: Optional[str] = Field(None, description="Unique idempotency key for preventing duplicate submissions")
    service_mode: ServiceMode = Field(ServiceMode.IN_CALL, description="Delivery mode: in_call or out_call")
    client_suburb: Optional[str] = Field(None, description="Client suburb for out-call booking")
    client_postcode: Optional[str] = Field(None, description="Client postcode for out-call booking")
    service_address: Optional[str] = Field(None, description="Client street address for out-call booking")
    chargeable_travel_distance_km: Optional[float] = Field(None, description="Chargeable travel distance in km")
    chargeable_travel_fee: Optional[Decimal] = Field(None, description="Chargeable travel fee")
    has_itinerary_conflict: bool = Field(False, description="Whether booking has an operational itinerary collision")
    itinerary_conflict: Optional[str] = Field(None, description="Operational itinerary conflict reason")


class BookingCreate(BookingBase):
    pass


class BookingUpdate(BaseModel):
    provider_id: Optional[int] = None
    service_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[BookingStatus] = None
    notes: Optional[str] = None
    service_mode: Optional[ServiceMode] = None
    client_suburb: Optional[str] = None
    client_postcode: Optional[str] = None
    service_address: Optional[str] = None
    chargeable_travel_distance_km: Optional[float] = None
    chargeable_travel_fee: Optional[Decimal] = None
    has_itinerary_conflict: Optional[bool] = None
    itinerary_conflict: Optional[str] = None


class BookingClientInfo(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class BookingProviderInfo(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    color: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class BookingServiceInfo(BaseModel):
    id: int
    name: str
    duration: int
    price: Optional[Decimal] = None
    model_config = ConfigDict(from_attributes=True)

class BookingLocationInfo(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)

class BookingInDBBase(BookingBase):
    id: int
    status: BookingStatus
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class Booking(BookingInDBBase):
    client: Optional[BookingClientInfo] = None
    provider: Optional[BookingProviderInfo] = None
    service: Optional[BookingServiceInfo] = None
    location: Optional[BookingLocationInfo] = None


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