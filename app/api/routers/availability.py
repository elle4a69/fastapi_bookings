"""Availability endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_public_tenant
from ...models.tenant import Tenant
from ...models.provider import Provider
from ...models.service import Service
from ...services.availability_service import get_available_slots


router = APIRouter()


@router.get("/availability", tags=["availability"])
def availability(
    service_id: int = Query(..., description="Service ID"),
    provider_id: int = Query(..., description="Provider ID"),
    date: datetime = Query(..., description="Date for which availability is requested"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Return available time slots for a provider and service on a specific date.

    This endpoint is intended for public use and requires a public token.
    """
    service = db.query(Service).filter(Service.id == service_id, Service.tenant_id == tenant.id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    provider = db.query(Provider).filter(Provider.id == provider_id, Provider.tenant_id == tenant.id).first()
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    slots = get_available_slots(db, service.duration, provider_id, date)
    # Convert datetimes to ISO strings
    formatted = [
        {"start": slot["start"].isoformat(), "end": slot["end"].isoformat()}
        for slot in slots
    ]
    return {"ok": True, "data": formatted}