"""Public bootstrap endpoint."""

from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_current_company, get_db
from ...models.location import Location as LocationModel
from ...models.provider import Provider as ProviderModel
from ...models.service import Service as ServiceModel
from ...schemas.service import Service as ServiceSchema
from ...schemas.provider import Provider as ProviderSchema
from ...schemas.location import Location as LocationSchema


router = APIRouter()


@router.get("/public/bootstrap", tags=["public"])
def public_bootstrap(
    db: Session = Depends(get_db),
    company: str = Depends(get_current_company),
) -> Dict[str, Any]:
    """Return data required to bootstrap the public booking interface."""
    services = db.query(ServiceModel).filter(ServiceModel.active == True).all()
    providers = db.query(ProviderModel).filter(ProviderModel.active == True).all()
    locations = db.query(LocationModel).all()
    timezone = None
    if locations:
        timezone = locations[0].timezone
        
    # Serialize ORM models to Pydantic schemas
    serialized_services = [ServiceSchema.model_validate(s).model_dump() for s in services]
    serialized_providers = [ProviderSchema.model_validate(p).model_dump() for p in providers]
    serialized_locations = [LocationSchema.model_validate(l).model_dump() for l in locations]
    
    return {
        "ok": True,
        "data": {
            "company": company,
            "services": serialized_services,
            "providers": serialized_providers,
            "locations": serialized_locations,
            "categories": [],
            "bookingRules": {"allowSameDayBooking": True, "maxAdvanceDays": 60},
            "timezone": timezone,
        },
    }