"""Schemas for waitlist model."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..models.waitlist import WaitlistStatus


class WaitlistBase(BaseModel):
    service_id: int
    provider_id: Optional[int] = None
    location_id: Optional[int] = None
    desired_date_from: Optional[datetime] = None
    desired_date_to: Optional[datetime] = None
    client_id: Optional[int] = None


class WaitlistCreate(WaitlistBase):
    pass


class WaitlistOut(WaitlistBase):
    id: int
    status: WaitlistStatus
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)