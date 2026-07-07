"""Admin calendar notes routes.

Calendar notes are short text annotations attached to a provider and
date on the admin calendar view.  They are useful for marking holidays,
internal reminders, or custom messages that appear alongside bookings.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...models.calendar_note import CalendarNote
from ...models.provider import Provider
from ...schemas.calendar_note import (
    CalendarNoteCreate,
    CalendarNoteListResponse,
    CalendarNoteOut,
    CalendarNoteResponse,
    CalendarNoteUpdate,
)

router = APIRouter(prefix="/api/admin/calendar-notes", tags=["calendar-notes"])


@router.get("", response_model=CalendarNoteListResponse)
def list_calendar_notes(
    provider_id: Optional[int] = Query(None, description="Filter by provider"),
    date_from: Optional[date] = Query(None, description="Start of date range"),
    date_to: Optional[date] = Query(None, description="End of date range"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> dict:
    """Return calendar notes, optionally filtered by provider and date range."""
    query = db.query(CalendarNote)
    if provider_id is not None:
        query = query.filter(CalendarNote.provider_id == provider_id)
    if date_from is not None:
        query = query.filter(CalendarNote.date >= date_from)
    if date_to is not None:
        query = query.filter(CalendarNote.date <= date_to)
    notes = query.order_by(CalendarNote.date.asc(), CalendarNote.id.asc()).all()
    return {"ok": True, "data": notes}


@router.post("", response_model=CalendarNoteResponse, status_code=status.HTTP_201_CREATED)
def create_calendar_note(
    note_in: CalendarNoteCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> dict:
    """Create a new calendar note."""
    if note_in.provider_id is not None:
        provider = db.query(Provider).filter(Provider.id == note_in.provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
    note = CalendarNote(**note_in.dict())
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"ok": True, "data": note}


@router.put("/{note_id}", response_model=CalendarNoteResponse)
def update_calendar_note(
    note_id: int,
    note_in: CalendarNoteUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> dict:
    """Update a calendar note."""
    note = db.query(CalendarNote).filter(CalendarNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Calendar note not found")
    if note_in.provider_id is not None:
        provider = db.query(Provider).filter(Provider.id == note_in.provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
    for field, value in note_in.dict(exclude_unset=True).items():
        setattr(note, field, value)
    db.commit()
    db.refresh(note)
    return {"ok": True, "data": note}


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_calendar_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> None:
    """Delete a calendar note."""
    note = db.query(CalendarNote).filter(CalendarNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Calendar note not found")
    db.delete(note)
    db.commit()
