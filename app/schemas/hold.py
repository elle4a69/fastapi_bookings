"""Schemas for hold model."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..models.hold import HoldStatus


class HoldBase(BaseModel):
    service_id: int
    start_time: datetime
    end_time: datetime
    provider_id: Optional[int] = None
    location_id: Optional[int] = None
    client_id: Optional[int] = None


class HoldCreate(HoldBase):
    expires_at: datetime


class HoldConfirm(BaseModel):
    hold_id: int
    client_details: Optional[dict] = None


class HoldOut(HoldBase):
    id: int
    status: HoldStatus
    expires_at: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)