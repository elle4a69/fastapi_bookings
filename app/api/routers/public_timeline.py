"""Public timeline and schedule endpoints.

Read-only schedule information for the public booking interface.
Combines provider workday records, special-day overrides and the
scheduling service's availability output.
"""

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..deps import get_db, DatabaseId, get_public_tenant
from ...models.tenant import Tenant
from ...models import (
    Provider as ProviderModel,
    ProviderSpecialDay,
    ProviderWorkDay,
    Service as ServiceModel,
)
from ...schemas.schedule import ProviderSpecialDayOut, ProviderWorkDayOut
from ...services import scheduling_service

router = APIRouter(prefix="/api/public/timeline", tags=["public-timeline"])


@router.get("/schedule/{provider_id}")
def get_provider_schedule(
    provider_id: DatabaseId,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Return a provider's weekly workdays and special-day overrides."""
    provider = db.query(ProviderModel).filter(
        ProviderModel.id == provider_id,
        ProviderModel.tenant_id == tenant.id,
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    workdays = (
        db.query(ProviderWorkDay)
        .filter(
            ProviderWorkDay.tenant_id == tenant.id,
            or_(ProviderWorkDay.provider_id == provider_id, ProviderWorkDay.provider_id.is_(None)),
        )
        .order_by(ProviderWorkDay.weekday.asc(), ProviderWorkDay.provider_id.desc())
        .all()
    )
    special_days = (
        db.query(ProviderSpecialDay)
        .filter(
            ProviderSpecialDay.tenant_id == tenant.id,
            or_(ProviderSpecialDay.provider_id == provider_id, ProviderSpecialDay.provider_id.is_(None)),
        )
        .order_by(ProviderSpecialDay.date.asc(), ProviderSpecialDay.provider_id.desc())
        .all()
    )
    return {
        "ok": True,
        "data": {
            "providerId": provider_id,
            "workdays": [ProviderWorkDayOut.model_validate(item).model_dump(mode="json") for item in workdays],
            "specialDays": [ProviderSpecialDayOut.model_validate(item).model_dump(mode="json") for item in special_days],
        },
    }


@router.get("/slots")
def get_available_slots(
    service_id: int = Query(..., ge=1, description="Service identifier"),
    provider_id: Optional[int] = Query(None, description="Optional provider identifier"),
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Return available slots for a service over an optional date range."""
    service = db.query(ServiceModel).filter(
        ServiceModel.id == service_id,
        ServiceModel.tenant_id == tenant.id,
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    provider = None
    if provider_id:
        provider = db.query(ProviderModel).filter(
            ProviderModel.id == provider_id,
            ProviderModel.tenant_id == tenant.id,
        ).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
    start = datetime.combine(date_from, datetime.min.time()) if date_from else datetime.utcnow()
    end = datetime.combine(date_to, datetime.max.time()) if date_to else (start + timedelta(days=7))
    slots = scheduling_service.compute_availability(
        db,
        service=service,
        provider=provider,
        start_time=start,
        end_time=end,
    )
    return {"ok": True, "data": slots, "meta": {"count": len(slots)}}


@router.get("/first-available-day")
def get_first_available_day(
    service_id: int = Query(..., ge=1, description="Service identifier"),
    provider_id: Optional[int] = Query(None, description="Optional provider identifier"),
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Return the first date that has at least one available slot."""
    service = db.query(ServiceModel).filter(
        ServiceModel.id == service_id,
        ServiceModel.tenant_id == tenant.id,
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    provider = None
    if provider_id:
        provider = db.query(ProviderModel).filter(
            ProviderModel.id == provider_id,
            ProviderModel.tenant_id == tenant.id,
        ).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
    now = datetime.utcnow()
    for day_offset in range(60):
        day_start = now + timedelta(days=day_offset)
        day_end = day_start + timedelta(days=1)
        slots = scheduling_service.compute_availability(
            db, service=service, provider=provider, start_time=day_start, end_time=day_end
        )
        if slots:
            return {"ok": True, "data": {"date": day_start.date().isoformat(), "slots": slots}}
    return {"ok": True, "data": None}
