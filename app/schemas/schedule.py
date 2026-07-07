"""Schemas for schedule/work calendar models."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class ProviderWorkDayBase(BaseModel):
    provider_id: Optional[int] = None
    location_id: Optional[int] = None
    weekday: int = Field(..., ge=0, le=6, description="Monday=0, Sunday=6")
    start_time: Optional[str] = Field(None, description="HH:MM")
    end_time: Optional[str] = Field(None, description="HH:MM")
    is_working: bool = True


class ProviderWorkDayCreate(ProviderWorkDayBase):
    pass


class ProviderWorkDayUpdate(BaseModel):
    provider_id: Optional[int] = None
    location_id: Optional[int] = None
    weekday: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_working: Optional[bool] = None


class ProviderWorkDayOut(ProviderWorkDayBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProviderSpecialDayBase(BaseModel):
    provider_id: Optional[int] = None
    location_id: Optional[int] = None
    date: date
    is_working: bool = False
    start_time: Optional[str] = Field(None, description="HH:MM")
    end_time: Optional[str] = Field(None, description="HH:MM")
    reason: Optional[str] = None


class ProviderSpecialDayCreate(ProviderSpecialDayBase):
    pass


class ProviderSpecialDayUpdate(BaseModel):
    provider_id: Optional[int] = None
    location_id: Optional[int] = None
    date: Optional[date] = None
    is_working: Optional[bool] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    reason: Optional[str] = None


class ProviderSpecialDayOut(ProviderSpecialDayBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BlockedTimeBase(BaseModel):
    provider_id: Optional[int] = None
    location_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    reason: Optional[str] = None
    active: bool = True


class BlockedTimeCreate(BlockedTimeBase):
    pass


class BlockedTimeUpdate(BaseModel):
    provider_id: Optional[int] = None
    location_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reason: Optional[str] = None
    active: Optional[bool] = None


class BlockedTimeOut(BlockedTimeBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReservedTimeBase(BaseModel):
    provider_id: Optional[int] = None
    service_id: Optional[int] = None
    client_id: Optional[int] = None
    location_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    expires_at: Optional[datetime] = None
    status: str = "reserved"
    note: Optional[str] = None


class ReservedTimeCreate(ReservedTimeBase):
    pass


class ReservedTimeUpdate(BaseModel):
    provider_id: Optional[int] = None
    service_id: Optional[int] = None
    client_id: Optional[int] = None
    location_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    status: Optional[str] = None
    note: Optional[str] = None


class ReservedTimeOut(ReservedTimeBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WorkloadSummary(BaseModel):
    """Counts of bookings within the next day, week and month."""
    day: int
    week: int
    month: int
