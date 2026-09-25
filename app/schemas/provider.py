"""Pydantic models for providers."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProviderBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(..., description="Provider's name")
    email: Optional[str] = Field(None, description="Provider's email address")
    phone: Optional[str] = Field(None, description="Provider's phone number")
    active: bool = Field(True, description="Whether the provider is active")
    is_visible: bool = Field(True, description="Whether the provider is visible publicly")
    capacity: int = Field(1, description="Capacity/slots available for concurrent bookings")
    color: Optional[str] = Field(None, description="Calendar color hex code")
    description: Optional[str] = Field(None, description="Provider description/bio")
    ignore_company_hours: bool = Field(False, description="Whether this provider ignores company-wide working hours")
    image: Optional[str] = Field(None, description="Provider profile image (base64 or URL)")
    weekly_schedule: Optional[dict] = Field(None, description="Provider's 7-day weekly schedule")
    in_call_address: Optional[str] = Field(None, description="In-call physical address")
    out_call_radius_km: float = Field(25.0, description="Out-call service radius in km")
    base_outcall_surcharge: Decimal = Field(Decimal("0.00"), description="Base surcharge for out-call services")
    per_km_fee: Decimal = Field(Decimal("0.00"), description="Per-km travel fee for out-call services")
    turnaround_buffer_mins: int = Field(15, description="Turnaround buffer in minutes")


class ProviderCreate(ProviderBase):
    pass


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    active: Optional[bool] = None
    is_visible: Optional[bool] = None
    capacity: Optional[int] = None
    color: Optional[str] = None
    description: Optional[str] = None
    ignore_company_hours: Optional[bool] = None
    image: Optional[str] = None
    weekly_schedule: Optional[dict] = None
    service_ids: Optional[list[int]] = None
    in_call_address: Optional[str] = None
    out_call_radius_km: Optional[float] = None
    base_outcall_surcharge: Optional[Decimal] = None
    per_km_fee: Optional[Decimal] = None
    turnaround_buffer_mins: Optional[int] = None


class ProviderInDBBase(ProviderBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class Provider(ProviderInDBBase):
    service_ids: list[int] = []


class ProviderListItem(BaseModel):
    """Provider fields needed in collection views.

    Full base64 profile images are intentionally excluded.  They can be several
    megabytes each and are available from the individual-provider endpoint.
    """

    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    active: bool = True
    is_visible: bool = True
    capacity: int = 1
    color: Optional[str] = None
    description: Optional[str] = None
    ignore_company_hours: bool = False
    thumbnail: Optional[str] = None
    weekly_schedule: Optional[dict] = None
    created_at: datetime
    service_ids: list[int] = []

    model_config = ConfigDict(from_attributes=True)


class ProviderListResponse(BaseModel):
    ok: bool
    data: list[ProviderListItem]
    meta: dict


class ProviderResponse(BaseModel):
    ok: bool
    data: Provider
