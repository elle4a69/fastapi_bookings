"""Pydantic models for locations."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LocationBase(BaseModel):
    name: str = Field(..., description="Location name")
    address: Optional[str] = Field(None, description="Physical address")
    timezone: Optional[str] = Field(None, description="IANA time zone identifier")
    image: Optional[str] = None
    active: bool = Field(True, description="Whether location is active")
    is_visible: bool = Field(True, description="Whether location is visible")


class LocationCreate(LocationBase):
    provider_ids: Optional[list[int]] = None
    service_ids: Optional[list[int]] = None
    category_ids: Optional[list[int]] = None
    product_ids: Optional[list[int]] = None


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = None
    image: Optional[str] = None
    active: Optional[bool] = None
    is_visible: Optional[bool] = None
    provider_ids: Optional[list[int]] = None
    service_ids: Optional[list[int]] = None
    category_ids: Optional[list[int]] = None
    product_ids: Optional[list[int]] = None


class LocationInDBBase(LocationBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class Location(LocationInDBBase):
    provider_ids: list[int] = []
    service_ids: list[int] = []
    category_ids: list[int] = []
    product_ids: list[int] = []


class LocationListResponse(BaseModel):
    ok: bool
    data: list[Location]
    meta: dict


class LocationResponse(BaseModel):
    ok: bool
    data: Location