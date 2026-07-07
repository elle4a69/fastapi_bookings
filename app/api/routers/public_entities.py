"""Public entity listing routes.

Read-only endpoints for listing core entities needed by the public
booking portal.  These endpoints do not require authentication and
only return active entities.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db
from ...models.category import Category as CategoryModel
from ...models.location import Location as LocationModel
from ...models.provider import Provider as ProviderModel
from ...models.service import Service as ServiceModel
from ...schemas.category import CategoryOut
from ...schemas.location import Location
from ...schemas.provider import ProviderListResponse
from ...schemas.service import ServiceListResponse


router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/services", response_model=ServiceListResponse)
def list_public_services(db: Session = Depends(get_db)) -> dict:
    """Return all active services for the public portal."""
    services = db.query(ServiceModel).filter(ServiceModel.active == True).all()
    return {"ok": True, "data": services, "meta": {"count": len(services)}}


@router.get("/providers", response_model=ProviderListResponse)
def list_public_providers(db: Session = Depends(get_db)) -> dict:
    """Return all active providers for the public portal."""
    providers = db.query(ProviderModel).filter(ProviderModel.active == True).all()
    return {"ok": True, "data": providers, "meta": {"count": len(providers)}}


@router.get("/categories", response_model=List[CategoryOut])
def list_public_categories(db: Session = Depends(get_db)) -> List[CategoryOut]:
    """Return all active categories for the public portal."""
    categories = db.query(CategoryModel).filter(CategoryModel.active == True).all()
    return [CategoryOut.from_orm(c) for c in categories]


@router.get("/locations", response_model=List[Location])
def list_public_locations(db: Session = Depends(get_db)) -> List[Location]:
    """Return all locations."""
    locations = db.query(LocationModel).all()
    return [Location.from_orm(l) for l in locations]
