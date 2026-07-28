"""Public entity listing routes.

Read-only endpoints for listing core entities needed by the public
booking portal.  These endpoints do not require authentication and
only return active entities.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db, get_public_tenant
from ...models.tenant import Tenant
from ...models.category import Category as CategoryModel, ServiceCategory as ServiceCategoryModel
from ...models.location import Location as LocationModel
from ...models.provider import Provider as ProviderModel
from ...models.service import Service as ServiceModel
from ...schemas.category import CategoryOut
from ...schemas.location import Location
from ...schemas.provider import ProviderListResponse
from ...schemas.service import ServiceListResponse


router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/services", response_model=ServiceListResponse, deprecated=True)
def list_public_services(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Return all active services for the public portal."""
    services = db.query(ServiceModel).filter(
        ServiceModel.tenant_id == tenant.id,
        ServiceModel.active == True,
        ServiceModel.deleted_at.is_(None),
    ).all()
    return {"ok": True, "data": services, "meta": {"count": len(services)}}


@router.get("/providers", response_model=ProviderListResponse, deprecated=True)
def list_public_providers(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> dict:
    """Return all active providers for the public portal."""
    providers = db.query(ProviderModel).filter(
        ProviderModel.tenant_id == tenant.id,
        ProviderModel.active == True,
        ProviderModel.deleted_at.is_(None),
    ).all()
    return {"ok": True, "data": providers, "meta": {"count": len(providers)}}


@router.get("/categories", response_model=List[CategoryOut], deprecated=True)
def list_public_categories(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> List[CategoryOut]:
    """Return all active categories for the public portal."""
    categories = (
        db.query(CategoryModel)
        .join(CategoryModel.services)
        .join(ServiceCategoryModel.service)
        .filter(
            ServiceModel.tenant_id == tenant.id,
            CategoryModel.tenant_id == tenant.id,
            ServiceCategoryModel.tenant_id == tenant.id,
            CategoryModel.active == True,
            ServiceModel.deleted_at.is_(None),
        )
        .distinct()
        .all()
    )
    return [CategoryOut.from_orm(c) for c in categories]


@router.get("/locations", response_model=List[Location], deprecated=True)
def list_public_locations(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
) -> List[Location]:
    """Return all locations."""
    locations = db.query(LocationModel).filter(LocationModel.tenant_id == tenant.id).all()
    return [Location.from_orm(l) for l in locations]
