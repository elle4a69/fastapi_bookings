"""Schemas for plugin states and GDPR consent logs."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# --- Plugin State ---

class PluginStateBase(BaseModel):
    name: str
    is_enabled: bool = True


class PluginStateCreate(PluginStateBase):
    pass


class PluginStateUpdate(BaseModel):
    is_enabled: bool


class PluginStateOut(PluginStateBase):
    id: int
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PluginStateListResponse(BaseModel):
    ok: bool
    data: list[PluginStateOut]


class PluginStateResponse(BaseModel):
    ok: bool
    data: PluginStateOut


# --- GDPR Consent ---

class GdprConsentCreate(BaseModel):
    client_id: int
    consent_type: str = "gdpr"
    is_approved: bool = True
    ip_address: str


class GdprConsentOut(GdprConsentCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class GdprConsentListResponse(BaseModel):
    ok: bool
    data: list[GdprConsentOut]


class GdprConsentResponse(BaseModel):
    ok: bool
    data: GdprConsentOut
