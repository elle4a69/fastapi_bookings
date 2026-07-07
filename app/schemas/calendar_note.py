"""Schemas for calendar notes."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CalendarNoteBase(BaseModel):
    provider_id: Optional[int] = None
    date: date
    start_time: Optional[str] = None   # HH:MM
    end_time: Optional[str] = None     # HH:MM
    text: str


class CalendarNoteCreate(CalendarNoteBase):
    pass


class CalendarNoteUpdate(BaseModel):
    provider_id: Optional[int] = None
    date: Optional[date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    text: Optional[str] = None


class CalendarNoteOut(CalendarNoteBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CalendarNoteListResponse(BaseModel):
    ok: bool
    data: list[CalendarNoteOut]


class CalendarNoteResponse(BaseModel):
    ok: bool
    data: CalendarNoteOut
