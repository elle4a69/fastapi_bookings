"""Service CRUD routes."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db, get_current_tenant
from ...core.pagination import paginate_query, pagination_params
from ...models.service import Service as ServiceModel
from ...models.tenant import Tenant
from ...schemas.service import (
    ServiceCreate,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdate,
)


router = APIRouter()


@router.get("/services", response_model=ServiceListResponse, tags=["services"])
def list_services(
    params: dict = Depends(pagination_params),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Return a paginated list of services."""
    query = db.query(ServiceModel).filter(ServiceModel.tenant_id == tenant.id, ServiceModel.deleted_at.is_(None))
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


def sync_service_relationships(
    db: Session,
    tenant_id: int,
    service: ServiceModel,
    category_ids: list[int] = None,
    provider_ids: list[int] = None,
    addon_ids: list[int] = None,
    product_ids: list[int] = None,
    requirements = None,
) -> None:
    from ...models import ServiceCategory, ServiceProvider, ServiceAddOn, ServiceProduct, ServiceResourceRequirement
    
    # Clear collections
    if category_ids is not None:
        service.categories = []
    if provider_ids is not None:
        service.providers = []
    if addon_ids is not None:
        service.add_ons = []
    if product_ids is not None:
        service.products = []
    if requirements is not None:
        service.resource_requirements = []
        
    db.flush()
    
    # Assign new lists
    if category_ids is not None:
        service.categories = [ServiceCategory(tenant_id=tenant_id, category_id=cat_id) for cat_id in category_ids]
    if provider_ids is not None:
        service.providers = [ServiceProvider(tenant_id=tenant_id, provider_id=prov_id) for prov_id in provider_ids]
    if addon_ids is not None:
        service.add_ons = [ServiceAddOn(tenant_id=tenant_id, add_on_id=addon_id) for addon_id in addon_ids]
    if product_ids is not None:
        service.products = [ServiceProduct(tenant_id=tenant_id, product_id=prod_id) for prod_id in product_ids]
    if requirements is not None:
        service.resource_requirements = [ServiceResourceRequirement(resource_type=req.resource_type, quantity=req.quantity) for req in requirements]
            
    db.commit()


@router.post("/services", response_model=ServiceResponse, tags=["services"])
def create_service(
    service_in: ServiceCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a new service."""
    service_dict = service_in.dict(exclude={"category_ids", "provider_ids", "addon_ids", "product_ids", "requirements"})
    service_dict["tenant_id"] = tenant.id
    service = ServiceModel(**service_dict)
    db.add(service)
    db.commit()
    db.refresh(service)
    
    sync_service_relationships(
        db,
        tenant.id,
        service,
        category_ids=service_in.category_ids,
        provider_ids=service_in.provider_ids,
        addon_ids=service_in.addon_ids,
        product_ids=service_in.product_ids,
        requirements=service_in.requirements
    )
    
    db.refresh(service)
    return {"ok": True, "data": service}


@router.get("/services/{service_id}", response_model=ServiceResponse, tags=["services"])
def get_service(
    service_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Retrieve a single service by ID."""
    service = db.query(ServiceModel).filter(
        ServiceModel.id == service_id,
        ServiceModel.tenant_id == tenant.id,
        ServiceModel.deleted_at.is_(None)
    ).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return {"ok": True, "data": service}


@router.put("/services/{service_id}", response_model=ServiceResponse, tags=["services"])
def update_service(
    service_id: int,
    service_in: ServiceUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Update an existing service."""
    service = db.query(ServiceModel).filter(
        ServiceModel.id == service_id,
        ServiceModel.tenant_id == tenant.id,
        ServiceModel.deleted_at.is_(None)
    ).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    for field, value in service_in.dict(exclude_unset=True, exclude={"category_ids", "provider_ids", "addon_ids", "product_ids", "requirements"}).items():
        setattr(service, field, value)
    db.commit()
    
    sync_service_relationships(
        db,
        tenant.id,
        service,
        category_ids=service_in.category_ids,
        provider_ids=service_in.provider_ids,
        addon_ids=service_in.addon_ids,
        product_ids=service_in.product_ids,
        requirements=service_in.requirements
    )
    
    db.refresh(service)
    return {"ok": True, "data": service}


@router.delete("/services/{service_id}", response_model=ServiceResponse, tags=["services"])
def delete_service(
    service_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Delete a service."""
    service = db.query(ServiceModel).filter(
        ServiceModel.id == service_id,
        ServiceModel.tenant_id == tenant.id,
        ServiceModel.deleted_at.is_(None)
    ).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    service.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "data": service}