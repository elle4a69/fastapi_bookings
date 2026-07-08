"""Public bootstrap endpoint."""

from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_current_company, get_db
from ...models.location import Location
from ...models.provider import Provider
from ...models.service import Service


router = APIRouter()


@router.get("/public/bootstrap", tags=["public"])
def public_bootstrap(
    db: Session = Depends(get_db),
    company: str = Depends(get_current_company),
) -> Dict[str, Any]:
    """Return data required to bootstrap the public booking interface."""
    services = db.query(Service).filter(Service.active == True).all()
    providers = db.query(Provider).filter(Provider.active == True).all()
    locations = db.query(Location).all()
    timezone = None
    if locations:
        timezone = locations[0].timezone
    return {
        "ok": True,
        "data": {
            "company": company,
            "services": services,
            "providers": providers,
            "locations": locations,
            "categories": [],
            "bookingRules": {"allowSameDayBooking": True, "maxAdvanceDays": 60},
            "timezone": timezone,
        },
    }