"""Waitlist API routes.

These endpoints manage waitlist entries.  Clients can add themselves
to a waitlist when no suitable slots are available.  Admins can
view and manage waitlist entries.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...models import Service, Provider, Location, WaitlistEntry, WaitlistStatus
from ...schemas.waitlist import WaitlistCreate, WaitlistOut

router = APIRouter(prefix="/api/public/waitlist", tags=["waitlist"])


@router.post("", response_model=WaitlistOut)
def add_to_waitlist(
    payload: WaitlistCreate,
    db: Session = Depends(get_db),
) -> WaitlistOut:
    """Add a client to the waitlist for a service.
    """
    service = db.query(Service).filter(Service.id == payload.service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    provider = None
    if payload.provider_id:
        provider = db.query(Provider).filter(Provider.id == payload.provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
    location = None
    if payload.location_id:
        location = db.query(Location).filter(Location.id == payload.location_id).first()
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")
    entry = WaitlistEntry(
        service_id=payload.service_id,
        provider_id=payload.provider_id,
        location_id=payload.location_id,
        desired_date_from=payload.desired_date_from,
        desired_date_to=payload.desired_date_to,
        client_id=payload.client_id,
        status=WaitlistStatus.REQUESTED,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return WaitlistOut.from_orm(entry)


@router.get("", response_model=List[WaitlistOut])
def list_waitlist(
    service_id: int,
    db: Session = Depends(get_db),
) -> List[WaitlistOut]:
    """List waitlist entries for a service.
    """
    entries = db.query(WaitlistEntry).filter(WaitlistEntry.service_id == service_id).all()
    return [WaitlistOut.from_orm(e) for e in entries]