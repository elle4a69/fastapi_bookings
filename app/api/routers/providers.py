"""Provider CRUD routes."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db, get_current_tenant, MAX_DATABASE_ID
from ...core.pagination import paginate_query, pagination_params
from ...models.provider import Provider as ProviderModel
from ...models.tenant import Tenant
from ...schemas.provider import (
    ProviderCreate,
    ProviderListResponse,
    ProviderResponse,
    ProviderUpdate,
)


router = APIRouter()


@router.get("/providers", response_model=ProviderListResponse, tags=["providers"])
def list_providers(
    params: dict = Depends(pagination_params),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Return a paginated list of providers."""
    query = db.query(ProviderModel).filter(ProviderModel.tenant_id == tenant.id, ProviderModel.deleted_at.is_(None))
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


from ...models.schedule import ProviderWorkDay, ProviderSpecialDay


def sync_workdays_from_schedule(db: Session, tenant_id: int, provider_id: int, weekly_schedule: dict):
    """Sync ProviderWorkDay rows from the weekly_schedule JSON.

    Only days where recurring=True are promoted as repeating weekly templates.
    Days with recurring=False are treated as one-off overrides — their ProviderWorkDay
    is set to is_working=False so the booking engine falls through to ProviderSpecialDay
    lookups for those dates instead.
    """
    if not isinstance(weekly_schedule, dict):
        return
    day_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    for day_name, weekday_num in day_map.items():
        day_info = weekly_schedule.get(day_name)
        if not isinstance(day_info, dict):
            continue

        is_recurring = day_info.get("recurring", True)
        is_working = day_info.get("is_working", False)

        # A non-recurring day must NOT appear as a repeating ProviderWorkDay template.
        # Setting is_working=False ensures the engine skips the weekly rule and will
        # instead match a ProviderSpecialDay for the specific date when present.
        effective_is_working = is_working and is_recurring

        workday = db.query(ProviderWorkDay).filter(
            ProviderWorkDay.tenant_id == tenant_id,
            ProviderWorkDay.provider_id == provider_id,
            ProviderWorkDay.weekday == weekday_num
        ).first()

        if not workday:
            workday = ProviderWorkDay(
                tenant_id=tenant_id,
                provider_id=provider_id,
                weekday=weekday_num,
                start_time="09:00",
                end_time="17:00",
                is_working=effective_is_working
            )
            db.add(workday)
        else:
            workday.is_working = effective_is_working

@router.post("/providers", response_model=ProviderResponse, tags=["providers"])
def create_provider(
    provider_in: ProviderCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a new provider."""
    provider_dict = provider_in.model_dump()
    provider_dict["tenant_id"] = tenant.id
    provider = ProviderModel(**provider_dict)
    db.add(provider)
    db.commit()
    db.refresh(provider)

    if provider.weekly_schedule:
        sync_workdays_from_schedule(db, tenant.id, provider.id, provider.weekly_schedule)
        db.commit()

    return {"ok": True, "data": provider}


@router.get("/providers/{provider_id}", response_model=ProviderResponse, tags=["providers"])
def get_provider(
    provider_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Retrieve a single provider by ID."""
    try:
        numeric_id = int(provider_id.replace("prov-", ""))
        if numeric_id < 1 or numeric_id > MAX_DATABASE_ID:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    provider = db.query(ProviderModel).filter(
        ProviderModel.id == numeric_id,
        ProviderModel.tenant_id == tenant.id,
        ProviderModel.deleted_at.is_(None)
    ).first()
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return {"ok": True, "data": provider}


@router.put("/providers/{provider_id}", response_model=ProviderResponse, tags=["providers"])
def update_provider(
    provider_id: str,
    provider_in: ProviderUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update an existing provider."""
    try:
        numeric_id = int(provider_id.replace("prov-", ""))
        if numeric_id < 1 or numeric_id > MAX_DATABASE_ID:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    except ValueError:
        numeric_id = None

    provider = None
    if numeric_id is not None:
        provider = db.query(ProviderModel).filter(
            ProviderModel.id == numeric_id,
            ProviderModel.tenant_id == tenant.id,
            ProviderModel.deleted_at.is_(None)
        ).first()

    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    for field, value in provider_in.model_dump(exclude_unset=True, exclude={"service_ids"}).items():
        setattr(provider, field, value)

    if provider_in.service_ids is not None:
        from ...models.service_provider import ServiceProvider
        provider.services = []
        db.flush()
        provider.services = [ServiceProvider(tenant_id=tenant.id, service_id=svc_id) for svc_id in provider_in.service_ids]

    if provider.weekly_schedule:
        sync_workdays_from_schedule(db, tenant.id, provider.id, provider.weekly_schedule)

    db.commit()
    db.refresh(provider)
    return {"ok": True, "data": provider}


from datetime import date as date_type
from pydantic import BaseModel


class SpecialDayPayload(BaseModel):
    date: str           # ISO date string e.g. "2025-08-12"
    is_working: bool
    active_slots: list[str] = []  # 12h slot strings e.g. ["9:00 AM", "9:30 AM"]
    reason: str | None = None


import json

@router.get("/providers/{provider_id}/special-days", tags=["providers"])
def get_provider_special_days(
    provider_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Retrieve all special-day overrides for a specific provider."""
    try:
        numeric_id = int(provider_id.replace("prov-", ""))
        if numeric_id < 1 or numeric_id > MAX_DATABASE_ID:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    special_days = db.query(ProviderSpecialDay).filter(
        ProviderSpecialDay.tenant_id == tenant.id,
        ProviderSpecialDay.provider_id == numeric_id,
    ).all()

    result = []
    for sd in special_days:
        active_slots = []
        if sd.reason and sd.reason.startswith("SLOTS:"):
            try:
                active_slots = json.loads(sd.reason[6:])
            except Exception:
                active_slots = []

        result.append({
            "id": sd.id,
            "date": sd.date.isoformat(),
            "is_working": sd.is_working,
            "start_time": sd.start_time,
            "end_time": sd.end_time,
            "active_slots": active_slots,
            "reason": sd.reason,
        })

    return {"ok": True, "data": result}


@router.post("/providers/{provider_id}/special-days", tags=["providers"])
def upsert_provider_special_day(
    provider_id: str,
    payload: SpecialDayPayload,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create or update a one-off ProviderSpecialDay for a specific calendar date."""
    try:
        numeric_id = int(provider_id.replace("prov-", ""))
        if numeric_id < 1 or numeric_id > MAX_DATABASE_ID:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    provider = db.query(ProviderModel).filter(
        ProviderModel.id == numeric_id,
        ProviderModel.tenant_id == tenant.id,
        ProviderModel.deleted_at.is_(None)
    ).first()
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    target_date = date_type.fromisoformat(payload.date)

    start_time_str = None
    end_time_str = None
    if payload.is_working and payload.active_slots:
        def to_24h(slot: str) -> str:
            import re
            m = re.match(r"(\d+):(\d+)\s*(AM|PM)", slot, re.IGNORECASE)
            if not m:
                return slot
            h, mn, period = int(m.group(1)), m.group(2), m.group(3).upper()
            if period == "PM" and h != 12:
                h += 12
            if period == "AM" and h == 12:
                h = 0
            return f"{h:02d}:{mn}"

        sorted_slots = sorted(payload.active_slots, key=to_24h)
        start_time_str = to_24h(sorted_slots[0])
        last = to_24h(sorted_slots[-1])
        lh, lm = map(int, last.split(":"))
        lm += 30
        if lm >= 60:
            lh += 1
            lm -= 60
        end_time_str = f"{lh:02d}:{lm:02d}"

    encoded_reason = f"SLOTS:{json.dumps(payload.active_slots)}" if payload.active_slots else (payload.reason or "Special Day Override")

    existing = db.query(ProviderSpecialDay).filter(
        ProviderSpecialDay.tenant_id == tenant.id,
        ProviderSpecialDay.provider_id == numeric_id,
        ProviderSpecialDay.date == target_date,
    ).first()

    if existing:
        existing.is_working = payload.is_working
        existing.start_time = start_time_str
        existing.end_time = end_time_str
        existing.reason = encoded_reason
    else:
        db.add(ProviderSpecialDay(
            tenant_id=tenant.id,
            provider_id=numeric_id,
            date=target_date,
            is_working=payload.is_working,
            start_time=start_time_str,
            end_time=end_time_str,
            reason=encoded_reason,
        ))

    db.commit()
    return {"ok": True, "message": f"Special day saved for {payload.date}"}


@router.delete("/providers/{provider_id}/special-days/{date_str}", tags=["providers"])
def delete_provider_special_day(
    provider_id: str,
    date_str: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Delete a special-day override for a specific provider and date."""
    try:
        numeric_id = int(provider_id.replace("prov-", ""))
        if numeric_id < 1 or numeric_id > MAX_DATABASE_ID:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    try:
        target_date = date_type.fromisoformat(date_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format, expected YYYY-MM-DD")
    existing = db.query(ProviderSpecialDay).filter(
        ProviderSpecialDay.tenant_id == tenant.id,
        ProviderSpecialDay.provider_id == numeric_id,
        ProviderSpecialDay.date == target_date,
    ).first()

    if existing:
        db.delete(existing)
        db.commit()

    return {"ok": True, "message": f"Special day removed for {date_str}"}



@router.delete("/providers/{provider_id}", response_model=ProviderResponse, tags=["providers"])
def delete_provider(
    provider_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Delete a provider."""
    try:
        numeric_id = int(provider_id.replace("prov-", ""))
        if numeric_id < 1 or numeric_id > MAX_DATABASE_ID:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    except ValueError:
        numeric_id = None

    if numeric_id is not None:
        provider = db.query(ProviderModel).filter(
             ProviderModel.id == numeric_id,
             ProviderModel.tenant_id == tenant.id,
             ProviderModel.deleted_at.is_(None)
         ).first()
        if provider:
            provider.deleted_at = datetime.now(timezone.utc)
            db.commit()
            return {"ok": True, "data": provider}
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")