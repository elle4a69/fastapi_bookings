"""Location relationships API router.

Provides endpoints to manage and retrieve links between locations and providers,
services, and categories.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..deps import get_db, get_current_tenant, get_current_admin
from ...models.tenant import Tenant
from ...models.user import User
from ...models.location import Location, LocationProvider, LocationService, LocationCategory
from ...models.provider import Provider
from ...models.service import Service
from ...models.category import Category
from ...schemas.provider import Provider as ProviderSchema
from ...schemas.service import Service as ServiceSchema
from ...schemas.category import CategoryOut as CategorySchema

router = APIRouter(prefix="/api/admin/locations", tags=["location-relationships"])


# --- Location-to-Provider Links ---

@router.post("/{location_id}/providers/{provider_id}", status_code=status.HTTP_201_CREATED)
def link_location_provider(
    location_id: int,
    provider_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Link a provider to a location."""
    # 1. Verify location exists and belongs to tenant
    loc = db.query(Location).filter(Location.id == location_id, Location.tenant_id == tenant.id).first()
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # 2. Verify provider exists and belongs to tenant
    prov = db.query(Provider).filter(Provider.id == provider_id, Provider.tenant_id == tenant.id, Provider.deleted_at.is_(None)).first()
    if not prov:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    # 3. Check for existing link
    existing = db.query(LocationProvider).filter(
        LocationProvider.tenant_id == tenant.id,
        LocationProvider.location_id == location_id,
        LocationProvider.provider_id == provider_id,
    ).first()
    if existing:
        return {"ok": True, "message": "Link already exists"}

    # 4. Create link
    link = LocationProvider(tenant_id=tenant.id, location_id=location_id, provider_id=provider_id)
    db.add(link)
    db.commit()
    return {"ok": True, "message": "Provider linked to location successfully."}


@router.delete("/{location_id}/providers/{provider_id}")
def unlink_location_provider(
    location_id: int,
    provider_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Unlink a provider from a location."""
    link = db.query(LocationProvider).filter(
        LocationProvider.tenant_id == tenant.id,
        LocationProvider.location_id == location_id,
        LocationProvider.provider_id == provider_id,
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    db.delete(link)
    db.commit()
    return {"ok": True, "message": "Provider unlinked from location successfully."}


@router.get("/{location_id}/providers", response_model=List[ProviderSchema])
def list_location_providers(
    location_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> List:
    """List all providers linked to a location."""
    loc = db.query(Location).filter(Location.id == location_id, Location.tenant_id == tenant.id).first()
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    providers = (
        db.query(Provider)
        .join(LocationProvider, Provider.id == LocationProvider.provider_id)
        .filter(LocationProvider.tenant_id == tenant.id, LocationProvider.location_id == location_id, Provider.tenant_id == tenant.id, Provider.deleted_at.is_(None))
        .all()
    )
    return providers


# --- Location-to-Service Links ---

@router.post("/{location_id}/services/{service_id}", status_code=status.HTTP_201_CREATED)
def link_location_service(
    location_id: int,
    service_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Link a service to a location."""
    loc = db.query(Location).filter(Location.id == location_id, Location.tenant_id == tenant.id).first()
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    srv = db.query(Service).filter(Service.id == service_id, Service.tenant_id == tenant.id, Service.deleted_at.is_(None)).first()
    if not srv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    existing = db.query(LocationService).filter(
        LocationService.tenant_id == tenant.id,
        LocationService.location_id == location_id,
        LocationService.service_id == service_id,
    ).first()
    if existing:
        return {"ok": True, "message": "Link already exists"}

    link = LocationService(tenant_id=tenant.id, location_id=location_id, service_id=service_id)
    db.add(link)
    db.commit()
    return {"ok": True, "message": "Service linked to location successfully."}


@router.delete("/{location_id}/services/{service_id}")
def unlink_location_service(
    location_id: int,
    service_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Unlink a service from a location."""
    link = db.query(LocationService).filter(
        LocationService.tenant_id == tenant.id,
        LocationService.location_id == location_id,
        LocationService.service_id == service_id,
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    db.delete(link)
    db.commit()
    return {"ok": True, "message": "Service unlinked from location successfully."}


@router.get("/{location_id}/services", response_model=List[ServiceSchema])
def list_location_services(
    location_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> List:
    """List all services linked to a location."""
    loc = db.query(Location).filter(Location.id == location_id, Location.tenant_id == tenant.id).first()
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    services = (
        db.query(Service)
        .join(LocationService, Service.id == LocationService.service_id)
        .filter(LocationService.tenant_id == tenant.id, LocationService.location_id == location_id, Service.tenant_id == tenant.id, Service.deleted_at.is_(None))
        .all()
    )
    return services


# --- Location-to-Category Links ---

@router.post("/{location_id}/categories/{category_id}", status_code=status.HTTP_201_CREATED)
def link_location_category(
    location_id: int,
    category_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Link a category to a location."""
    loc = db.query(Location).filter(Location.id == location_id, Location.tenant_id == tenant.id).first()
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    cat = db.query(Category).filter(Category.id == category_id, Category.tenant_id == tenant.id).first()
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    existing = db.query(LocationCategory).filter(
        LocationCategory.tenant_id == tenant.id,
        LocationCategory.location_id == location_id,
        LocationCategory.category_id == category_id,
    ).first()
    if existing:
        return {"ok": True, "message": "Link already exists"}

    link = LocationCategory(tenant_id=tenant.id, location_id=location_id, category_id=category_id)
    db.add(link)
    db.commit()
    return {"ok": True, "message": "Category linked to location successfully."}


@router.delete("/{location_id}/categories/{category_id}")
def unlink_location_category(
    location_id: int,
    category_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    """Unlink a category from a location."""
    link = db.query(LocationCategory).filter(
        LocationCategory.tenant_id == tenant.id,
        LocationCategory.location_id == location_id,
        LocationCategory.category_id == category_id,
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    db.delete(link)
    db.commit()
    return {"ok": True, "message": "Category unlinked from location successfully."}


@router.get("/{location_id}/categories", response_model=List[CategorySchema])
def list_location_categories(
    location_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> List:
    """List all categories linked to a location."""
    loc = db.query(Location).filter(Location.id == location_id, Location.tenant_id == tenant.id).first()
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    categories = (
        db.query(Category)
        .join(LocationCategory, Category.id == LocationCategory.category_id)
        .filter(LocationCategory.tenant_id == tenant.id, LocationCategory.location_id == location_id, Category.tenant_id == tenant.id)
        .all()
    )
    return categories
