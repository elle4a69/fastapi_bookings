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
) -> dict:
    """Return a paginated list of services."""
    query = db.query(ServiceModel).filter(ServiceModel.tenant_id == tenant.id, ServiceModel.deleted_at.is_(None))
    items, meta = paginate_query(query, params["page"], params["page_size"])
    return {"ok": True, "data": items, "meta": meta}


@router.post("/services", response_model=ServiceResponse, tags=["services"])
def create_service(
    service_in: ServiceCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> dict:
    """Create a new service."""
    service_dict = service_in.dict()
    service_dict["tenant_id"] = tenant.id
    service = ServiceModel(**service_dict)
    db.add(service)
    db.commit()
    db.refresh(service)
    return {"ok": True, "data": service}


@router.get("/services/{service_id}", response_model=ServiceResponse, tags=["services"])
def get_service(
    service_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
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
    for field, value in service_in.dict(exclude_unset=True).items():
        setattr(service, field, value)
    db.commit()
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