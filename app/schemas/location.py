"""Pydantic models for locations."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LocationBase(BaseModel):
    name: str = Field(..., description="Location name")
    address: Optional[str] = Field(None, description="Physical address")
    timezone: Optional[str] = Field(None, description="IANA time zone identifier")


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = None


class LocationInDBBase(LocationBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class Location(LocationInDBBase):
    pass


class LocationListResponse(BaseModel):
    ok: bool
    data: list[Location]
    meta: dict


class LocationResponse(BaseModel):
    ok: bool
    data: Location