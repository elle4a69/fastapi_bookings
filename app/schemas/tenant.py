"""Pydantic schemas for Tenant domain contracts."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TravelChargeOrigin(str, Enum):
    """Origin calculation policy for out-call travel charges."""
    ALWAYS_FROM_BASE = "ALWAYS_FROM_BASE"
    ACTUAL_ORIGIN = "ACTUAL_ORIGIN"


class TenantBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(..., description="Business name")
    subdomain: str = Field(..., description="Subdomain slug")
    timezone: str = Field("UTC", description="Business timezone")
    country: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    public_address_visibility: str = Field("visible")
    max_advance_days: int = Field(60)
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    logo_url: Optional[str] = None
    allow_in_call: bool = Field(True, description="Whether business allows in-call bookings")
    allow_out_call: bool = Field(True, description="Whether business allows out-call bookings")
    travel_charge_origin: TravelChargeOrigin = Field(
        TravelChargeOrigin.ALWAYS_FROM_BASE,
        description="Policy for calculating out-call travel charges: ALWAYS_FROM_BASE or ACTUAL_ORIGIN",
    )


class TenantCreate(TenantBase):
    subscription_tier: str = "starter"


class TenantUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    timezone: Optional[str] = None
    country: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    public_address_visibility: Optional[str] = None
    max_advance_days: Optional[int] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    logo_url: Optional[str] = None
    allow_in_call: Optional[bool] = None
    allow_out_call: Optional[bool] = None
    travel_charge_origin: Optional[TravelChargeOrigin] = None


class TenantInDBBase(TenantBase):
    id: int
    subscription_tier: str
    addon_quota: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenantOut(TenantInDBBase):
    pass


class TenantResponse(BaseModel):
    ok: bool
    data: TenantOut
