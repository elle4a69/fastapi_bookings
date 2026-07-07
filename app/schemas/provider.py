"""Pydantic models for providers."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProviderBase(BaseModel):
    name: str = Field(..., description="Provider's name")
    email: Optional[str] = Field(None, description="Provider's email address")
    phone: Optional[str] = Field(None, description="Provider's phone number")
    active: bool = Field(True, description="Whether the provider is active")


class ProviderCreate(ProviderBase):
    pass


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    active: Optional[bool] = None


class ProviderInDBBase(ProviderBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class Provider(ProviderInDBBase):
    pass


class ProviderListResponse(BaseModel):
    ok: bool
    data: list[Provider]
    meta: dict


class ProviderResponse(BaseModel):
    ok: bool
    data: Provider


class ProviderResponse(BaseModel):
    ok: bool
    data: Provider


class ProviderResponse(BaseModel):
    ok: bool
    data: Provider