"""Resource CRUD routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db, get_current_tenant
from ...models.resource import Resource as ResourceModel, ServiceResourceRequirement as SRRModel
from ...models.tenant import Tenant
from ...schemas.resource import (
    ResourceCreate,
    ResourceUpdate,
    ResourceOut,
    ServiceResourceRequirementCreate,
    ServiceResourceRequirementOut,
)

router = APIRouter(prefix="/api/admin/resources", tags=["resources"])


@router.get("", response_model=List[ResourceOut])
def list_resources(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> List[ResourceOut]:
    resources = db.query(ResourceModel).filter(ResourceModel.tenant_id == tenant.id).all()
    return [ResourceOut.from_orm(r) for r in resources]


@router.post("", response_model=ResourceOut)
def create_resource(
    resource_in: ResourceCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ResourceOut:
    resource_dict = resource_in.dict()
    resource_dict["tenant_id"] = tenant.id
    resource = ResourceModel(**resource_dict)
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return ResourceOut.from_orm(resource)


@router.get("/{resource_id}", response_model=ResourceOut)
def get_resource(
    resource_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
) -> ResourceOut:
    resource = db.query(ResourceModel).filter(
        ResourceModel.id == resource_id,
        ResourceModel.tenant_id == tenant.id
    ).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return ResourceOut.from_orm(resource)


@router.put("/{resource_id}", response_model=ResourceOut)
def update_resource(
    resource_id: int,
    resource_in: ResourceUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ResourceOut:
    resource = db.query(ResourceModel).filter(
        ResourceModel.id == resource_id,
        ResourceModel.tenant_id == tenant.id
    ).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    for field, value in resource_in.dict(exclude_unset=True).items():
        setattr(resource, field, value)
    db.commit()
    db.refresh(resource)
    return ResourceOut.from_orm(resource)


@router.delete("/{resource_id}", response_model=ResourceOut)
def delete_resource(
    resource_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ResourceOut:
    resource = db.query(ResourceModel).filter(
        ResourceModel.id == resource_id,
        ResourceModel.tenant_id == tenant.id
    ).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    db.delete(resource)
    db.commit()
    return ResourceOut.from_orm(resource)


@router.post("/requirements", response_model=ServiceResourceRequirementOut)
def create_service_resource_requirement(
    requirement_in: ServiceResourceRequirementCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ServiceResourceRequirementOut:
    requirement = SRRModel(**requirement_in.dict())
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return ServiceResourceRequirementOut.from_orm(requirement)