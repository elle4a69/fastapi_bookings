"""Pydantic models for providers."""

from datetime import datetime
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
    service_ids: Optional[list[int]] = None


class ProviderInDBBase(ProviderBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class Provider(ProviderInDBBase):
    service_ids: list[int] = []


class ProviderListResponse(BaseModel):
    ok: bool
    data: list[Provider]
    meta: dict


class ProviderResponse(BaseModel):
    ok: bool
    data: Provider