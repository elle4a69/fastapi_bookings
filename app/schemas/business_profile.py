"""Pydantic schemas for Tenant Business Profile."""

from typing import Optional
from pydantic import BaseModel, Field


class BusinessProfileBase(BaseModel):
    timezone: str = Field("UTC", description="Business primary timezone")
    country: Optional[str] = Field(None, description="ISO country code")
    email: Optional[str] = Field(None, description="General contact email")
    phone: Optional[str] = Field(None, description="General contact phone")
    website: Optional[str] = Field(None, description="Business website URL")
    public_address_visibility: str = Field("visible", description="Visibility of address on public portal")
    max_advance_days: int = Field(60, description="Horizon/limit for advance bookings in days")
    address: Optional[str] = Field(None, description="Physical address of the business")
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")
    logo_url: Optional[str] = Field(None, description="Business logo image URL")


class BusinessProfileUpdate(BaseModel):
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


class BusinessProfileOut(BusinessProfileBase):
    id: int
    name: str
    subdomain: str

    class Config:
        from_attributes = True


class PublicBusinessProfileOut(BaseModel):
    name: str
    subdomain: str
    timezone: str
    country: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    public_address_visibility: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    logo_url: Optional[str] = None

    class Config:
        from_attributes = True


class BusinessProfileResponse(BaseModel):
    ok: bool
    data: BusinessProfileOut


class PublicBusinessProfileResponse(BaseModel):
    ok: bool
    data: PublicBusinessProfileOut
