"""Schemas for recurring booking series."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BookingSeriesBase(BaseModel):
    client_id: Optional[int] = None
    service_id: int
    provider_id: Optional[int] = None
    location_id: Optional[int] = None
    recurrence_rule: str
    name: Optional[str] = None
    end_date: Optional[datetime] = None


class BookingSeriesCreate(BookingSeriesBase):
    pass


class BookingSeriesOut(BookingSeriesBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
