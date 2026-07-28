"""Discovery Map API router.

Exposes public endpoints for the multi-tenant Discovery Map feature:

  GET /api/discovery/map          – Return all geocoded tenants with real-time
                                    availability status (green / orange / red).
  GET /api/discovery/services     – Return a deduplicated list of service names
                                    offered across all active tenants.
  POST /api/admin/business-profile/geocode – Admin endpoint to manually trigger
                                    address geocoding for the current tenant.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db
from ...core.config import settings
from ...models.category import Category, ServiceCategory
from ...models.service import Service
from ...models.tenant import Tenant
from ...services.geocoding import geocode_tenant_address
from ...services.scheduling_service import compute_availability

logger = logging.getLogger(__name__)

router = APIRouter(tags=["discovery"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TenantMapPin(BaseModel):
    tenant_id: int
    business_name: str
    slug: str
    latitude: float
    longitude: float
    image_url: Optional[str]
    status: str
    next_available_text: str


class ServiceOption(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUS_TODAY = "available_today"
_STATUS_LATER = "available_later"
_STATUS_NONE = "unavailable"


def _availability_status(tenant: Tenant, db: Session) -> tuple[str, str]:
    """Return (status_code, next_available_text) for a tenant.

    Scans up to max_advance_days into the future across all active services
    and providers to find the earliest unbooked slot.
    """
    today = datetime.now(timezone.utc).date()
    max_days = tenant.max_advance_days or 60
    horizon = today + timedelta(days=max_days)

    services: List[Service] = (
        db.query(Service)
        .filter(
            Service.tenant_id == tenant.id,
            Service.active.is_(True),
            Service.deleted_at.is_(None),
        )
        .all()
    )

    for offset in range(max_days + 1):
        check_date = today + timedelta(days=offset)
        if check_date > horizon:
            break

        start_dt = datetime.combine(check_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(check_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        for svc in services:
            try:
                slots = compute_availability(
                    db,
                    service=svc,
                    start_time=start_dt,
                    end_time=end_dt,
                )
            except Exception:
                logger.exception("Error computing availability for tenant %d service %d", tenant.id, svc.id)
                slots = []

            if slots:
                # Found a slot on check_date
                slot_start_str = slots[0].get("start_time", "")
                try:
                    slot_dt = datetime.fromisoformat(slot_start_str).astimezone(timezone.utc)
                except (ValueError, TypeError):
                    slot_dt = start_dt

                friendly_time = slot_dt.strftime("%I:%M %p").lstrip('0') if hasattr(slot_dt, "strftime") else slot_start_str

                if check_date == today:
                    return _STATUS_TODAY, f"Today at {friendly_time}"
                elif check_date == today + timedelta(days=1):
                    return _STATUS_LATER, f"Tomorrow at {friendly_time}"
                else:
                    return _STATUS_LATER, f"{check_date.strftime('%A')} at {friendly_time}"

    return _STATUS_NONE, "No upcoming availability"


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.get("/api/discovery/map", response_model=List[TenantMapPin])
def discovery_map(
    service_type: Optional[str] = Query(None, description="Filter by service name or category"),
    db: Session = Depends(get_db),
) -> List[TenantMapPin]:
    """Return geocoded tenants with real-time availability status for the map.

    Each tenant is represented as a map pin with a color-coded status:
    - available_today  (green)  – Has a free slot today.
    - available_later  (orange) – Has a free slot this week.
    - unavailable      (red)    – No upcoming free slots.
    """
    tenants: List[Tenant] = (
        db.query(Tenant)
        .filter(
            Tenant.latitude.isnot(None),
            Tenant.longitude.isnot(None),
        )
        .all()
    )

    if service_type:
        term = service_type.strip().lower()
        filtered: List[Tenant] = []
        for tenant in tenants:
            services = (
                db.query(Service)
                .filter(
                    Service.tenant_id == tenant.id,
                    Service.active.is_(True),
                    Service.deleted_at.is_(None),
                )
                .all()
            )
            # Match by service name
            if any(term in (s.name or "").lower() for s in services):
                filtered.append(tenant)
                continue
            # Match by category name
            service_ids = [s.id for s in services]
            if service_ids:
                category_match = (
                    db.query(Category)
                    .join(ServiceCategory, ServiceCategory.category_id == Category.id)
                    .filter(
                        ServiceCategory.service_id.in_(service_ids),
                        Category.active.is_(True),
                    )
                    .filter(Category.name.ilike(f"%{term}%"))
                    .first()
                )
                if category_match:
                    filtered.append(tenant)
        tenants = filtered

    pins: List[TenantMapPin] = []
    for tenant in tenants:
        availability_status, next_text = _availability_status(tenant, db)
        pins.append(
            TenantMapPin(
                tenant_id=tenant.id,
                business_name=tenant.name,
                slug=tenant.subdomain,
                latitude=tenant.latitude,
                longitude=tenant.longitude,
                image_url=tenant.logo_url,
                status=availability_status,
                next_available_text=next_text,
            )
        )

    return pins


@router.get("/api/discovery/services", response_model=List[ServiceOption])
def discovery_services(db: Session = Depends(get_db)) -> List[ServiceOption]:
    """Return a deduplicated list of all active service names across all tenants.

    Used to populate the search dropdown on the Discovery Map.
    """
    services = (
        db.query(Service.name)
        .filter(
            Service.active.is_(True),
            Service.deleted_at.is_(None),
        )
        .distinct()
        .order_by(Service.name)
        .all()
    )
    return [ServiceOption(name=row.name) for row in services]


# ---------------------------------------------------------------------------
# Admin geocoding endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/api/admin/business-profile/geocode",
    tags=["business-profile"],
    summary="Manually trigger Mapbox geocoding for the current tenant's address.",
)
async def trigger_geocode(
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(get_current_tenant),
    current_user=Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Re-run Mapbox geocoding for the tenant's stored address.

    Returns immediately while geocoding runs in the background.
    Returns a 400 error if no address is set on the business profile.
    """
    if not tenant.address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No address is set on this business profile. Update the address first.",
        )
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mapbox geocoding is not configured on this server.",
        )
    background_tasks.add_task(geocode_tenant_address, tenant.id, tenant.address)
    return {"ok": True, "message": "Geocoding has been triggered and will complete shortly."}
