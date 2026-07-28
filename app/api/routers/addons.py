"""Add‑on CRUD routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db
from ...models.tenant import Tenant
from ...models.service import Service
from ...models.addon import AddOn as AddOnModel, ServiceAddOn
from ...schemas.addon import AddOnCreate, AddOnUpdate, AddOnOut

router = APIRouter(prefix="/api/admin/add-ons", tags=["add-ons"])


@router.get("", response_model=List[AddOnOut])
def list_addons(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> List[AddOnOut]:
    add_ons = db.query(AddOnModel).filter(AddOnModel.tenant_id == tenant.id).all()
    return [AddOnOut.from_orm(a) for a in add_ons]


@router.post("", response_model=AddOnOut)
def create_addon(
    addon_in: AddOnCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> AddOnOut:
    values = addon_in.model_dump(exclude={"service_id"})
    addon = AddOnModel(tenant_id=tenant.id, **values)
    db.add(addon)
    db.flush()
    if addon_in.service_id is not None:
        service = db.query(Service).filter(Service.id == addon_in.service_id, Service.tenant_id == tenant.id).first()
        if not service:
            db.rollback()
            raise HTTPException(status_code=404, detail="Service not found")
        db.add(ServiceAddOn(tenant_id=tenant.id, service_id=service.id, add_on_id=addon.id))
    db.commit()
    db.refresh(addon)
    return AddOnOut.from_orm(addon)


@router.get("/{add_on_id}", response_model=AddOnOut)
def get_addon(
    add_on_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> AddOnOut:
    addon = db.query(AddOnModel).filter(AddOnModel.id == add_on_id, AddOnModel.tenant_id == tenant.id).first()
    if not addon:
        raise HTTPException(status_code=404, detail="Add‑on not found")
    return AddOnOut.from_orm(addon)


@router.put("/{add_on_id}", response_model=AddOnOut)
def update_addon(
    add_on_id: int,
    addon_in: AddOnUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> AddOnOut:
    addon = db.query(AddOnModel).filter(AddOnModel.id == add_on_id, AddOnModel.tenant_id == tenant.id).first()
    if not addon:
        raise HTTPException(status_code=404, detail="Add‑on not found")
    for field, value in addon_in.model_dump(exclude_unset=True, exclude={"service_id"}).items():
        setattr(addon, field, value)
    db.commit()
    db.refresh(addon)
    return AddOnOut.from_orm(addon)


@router.delete("/{add_on_id}", response_model=AddOnOut)
def delete_addon(
    add_on_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> AddOnOut:
    addon = db.query(AddOnModel).filter(AddOnModel.id == add_on_id, AddOnModel.tenant_id == tenant.id).first()
    if not addon:
        raise HTTPException(status_code=404, detail="Add‑on not found")
    db.delete(addon)
    db.commit()
    return AddOnOut.from_orm(addon)
