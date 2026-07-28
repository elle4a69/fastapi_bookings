"""Location CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...core.pagination import paginate_query, pagination_params
from ...models.location import Location as LocationModel
from ...schemas.location import (
    Location,
    LocationCreate,
    LocationListResponse,
    LocationResponse,
    LocationUpdate,
)


router = APIRouter()


@router.get("/locations", response_model=LocationListResponse, tags=["locations"])
def list_locations(
    params: dict = Depends(pagination_params),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Return a paginated list of locations."""
    query = db.query(LocationModel).filter(LocationModel.tenant_id == current_user.tenant_id)
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


def sync_location_relationships(
    db: Session,
    tenant_id: int,
    location: LocationModel,
    provider_ids: list[int] = None,
    service_ids: list[int] = None,
    category_ids: list[int] = None,
    product_ids: list[int] = None,
) -> None:
    from ...models.location import LocationProvider, LocationService, LocationCategory, LocationProduct
    
    needs_flush = False

    if provider_ids is not None:
        location.location_providers = []
        needs_flush = True
            
    if service_ids is not None:
        location.location_services = []
        needs_flush = True
            
    if category_ids is not None:
        location.location_categories = []
        needs_flush = True

    if product_ids is not None:
        location.location_products = []
        needs_flush = True

    if needs_flush:
        db.flush()

    if provider_ids is not None:
        location.location_providers = [
            LocationProvider(tenant_id=tenant_id, provider_id=prov_id)
            for prov_id in provider_ids
        ]
            
    if service_ids is not None:
        location.location_services = [
            LocationService(tenant_id=tenant_id, service_id=svc_id)
            for svc_id in service_ids
        ]
            
    if category_ids is not None:
        location.location_categories = [
            LocationCategory(tenant_id=tenant_id, category_id=cat_id)
            for cat_id in category_ids
        ]

    if product_ids is not None:
        location.location_products = [
            LocationProduct(tenant_id=tenant_id, product_id=prod_id)
            for prod_id in product_ids
        ]
            
    db.commit()


@router.post("/locations", response_model=LocationResponse, tags=["locations"])
def create_location(
    location_in: LocationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a new location."""
    location_dict = location_in.dict(exclude={"provider_ids", "service_ids", "category_ids", "product_ids"})
    location = LocationModel(tenant_id=current_user.tenant_id, **location_dict)
    db.add(location)
    db.commit()
    db.refresh(location)
    
    sync_location_relationships(
        db,
        current_user.tenant_id,
        location,
        provider_ids=location_in.provider_ids,
        service_ids=location_in.service_ids,
        category_ids=location_in.category_ids,
        product_ids=location_in.product_ids
    )
    
    db.refresh(location)
    return {"ok": True, "data": location}


@router.get("/locations/{location_id}", response_model=LocationResponse, tags=["locations"])
def get_location(
    location_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Retrieve a single location by ID."""
    location = db.query(LocationModel).filter(LocationModel.id == location_id, LocationModel.tenant_id == current_user.tenant_id).first()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return {"ok": True, "data": location}


@router.put("/locations/{location_id}", response_model=LocationResponse, tags=["locations"])
def update_location(
    location_id: int,
    location_in: LocationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update an existing location."""
    location = db.query(LocationModel).filter(LocationModel.id == location_id, LocationModel.tenant_id == current_user.tenant_id).first()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    
    for field, value in location_in.dict(exclude_unset=True, exclude={"provider_ids", "service_ids", "category_ids", "product_ids"}).items():
        setattr(location, field, value)
    db.commit()
    
    sync_location_relationships(
        db,
        current_user.tenant_id,
        location,
        provider_ids=location_in.provider_ids,
        service_ids=location_in.service_ids,
        category_ids=location_in.category_ids,
        product_ids=location_in.product_ids
    )
    
    db.refresh(location)
    return {"ok": True, "data": location}


@router.delete("/locations/{location_id}", response_model=LocationResponse, tags=["locations"])
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Delete a location."""
    location = db.query(LocationModel).filter(LocationModel.id == location_id, LocationModel.tenant_id == current_user.tenant_id).first()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    db.delete(location)
    db.commit()
    return {"ok": True, "data": location}