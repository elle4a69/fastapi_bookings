"""Pydantic models for bookings."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ..core.state_machine import BookingStatus


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


class BookingCreate(BookingBase):
    pass


class PublicBookingCreate(BaseModel):
    """Contact-based booking request accepted by the public endpoint."""

    client_name: Optional[str] = Field(None, description="Name of the client")
    client_email: Optional[str] = Field(None, description="Email of the client")
    client_phone: Optional[str] = Field(None, description="Phone of the client")
    provider_id: int = Field(..., description="Identifier of the provider")
    service_id: int = Field(..., description="Identifier of the service")
    location_id: Optional[int] = Field(None, description="Identifier of the location")
    start_time: datetime = Field(..., description="Start time of the appointment")
    end_time: datetime = Field(..., description="End time of the appointment")
    notes: Optional[str] = Field(None, description="Notes attached to the booking")
    addon_ids: list[int] = Field(
        default_factory=list,
        description="Existing public-form add-on selections",
    )
    product_ids: list[int] = Field(
        default_factory=list,
        description="Existing public-form product selections",
    )
    idempotency_key: Optional[str] = Field(
        None,
        description="Unique idempotency key for preventing duplicate submissions",
    )
    # Unknown keys are retained only long enough for the public route to reject
    # them with a non-reflecting error. The published contract remains closed.
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"additionalProperties": False},
    )


class BookingUpdate(BaseModel):
    provider_id: Optional[int] = None
    service_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[BookingStatus] = None
    notes: Optional[str] = None

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


class PublicBookingReceipt(BaseModel):
    """Non-PII booking receipt returned by the unauthenticated public route."""

    id: int
    provider_id: int
    service_id: int
    location_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PublicBookingResponse(BaseModel):
    ok: bool
    data: PublicBookingReceipt


class ErrorResponse(BaseModel):
    ok: bool = False
    error: dict


class BookingReschedule(BaseModel):
    new_start: datetime = Field(..., description="New start time of the appointment")
    new_end: datetime = Field(..., description="New end time of the appointment")
