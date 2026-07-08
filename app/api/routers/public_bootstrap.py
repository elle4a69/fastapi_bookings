"""Public bootstrap endpoint."""

from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_public_tenant, get_db
from ...models.tenant import Tenant
from ...models.location import Location
from ...models.provider import Provider
from ...models.service import Service


router = APIRouter()


@router.get("/public/bootstrap", tags=["public"])
def public_bootstrap(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> Dict[str, Any]:
    """Return data required to bootstrap the public booking interface."""
    services = db.query(Service).filter(Service.tenant_id == tenant.id, Service.active == True).all()
    providers = db.query(Provider).filter(Provider.tenant_id == tenant.id, Provider.active == True).all()
    locations = db.query(Location).filter(Location.tenant_id == tenant.id).all()
    timezone = None
    if locations:
        timezone = locations[0].timezone
    return {
        "ok": True,
        "data": {
            "company": tenant.subdomain,
            "services": services,
            "providers": providers,
            "locations": locations,
            "categories": [],
            "bookingRules": {"allowSameDayBooking": True, "maxAdvanceDays": 60},
            "timezone": timezone,
        },
    }