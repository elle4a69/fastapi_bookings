"""Add‑on CRUD routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...models.addon import AddOn as AddOnModel
from ...schemas.addon import AddOnCreate, AddOnUpdate, AddOnOut

router = APIRouter(prefix="/api/admin/add-ons", tags=["add-ons"])


@router.get("", response_model=List[AddOnOut])
def list_addons(db: Session = Depends(get_db)) -> List[AddOnOut]:
    add_ons = db.query(AddOnModel).all()
    return [AddOnOut.from_orm(a) for a in add_ons]


@router.post("", response_model=AddOnOut)
def create_addon(
    addon_in: AddOnCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> AddOnOut:
    addon = AddOnModel(**addon_in.dict())
    db.add(addon)
    db.commit()
    db.refresh(addon)
    return AddOnOut.from_orm(addon)


@router.get("/{add_on_id}", response_model=AddOnOut)
def get_addon(add_on_id: int, db: Session = Depends(get_db)) -> AddOnOut:
    addon = db.query(AddOnModel).filter(AddOnModel.id == add_on_id).first()
    if not addon:
        raise HTTPException(status_code=404, detail="Add‑on not found")
    return AddOnOut.from_orm(addon)


@router.put("/{add_on_id}", response_model=AddOnOut)
def update_addon(
    add_on_id: int,
    addon_in: AddOnUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> AddOnOut:
    addon = db.query(AddOnModel).filter(AddOnModel.id == add_on_id).first()
    if not addon:
        raise HTTPException(status_code=404, detail="Add‑on not found")
    for field, value in addon_in.dict(exclude_unset=True).items():
        setattr(addon, field, value)
    db.commit()
    db.refresh(addon)
    return AddOnOut.from_orm(addon)


@router.delete("/{add_on_id}", response_model=AddOnOut)
def delete_addon(
    add_on_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> AddOnOut:
    addon = db.query(AddOnModel).filter(AddOnModel.id == add_on_id).first()
    if not addon:
        raise HTTPException(status_code=404, detail="Add‑on not found")
    db.delete(addon)
    db.commit()
    return AddOnOut.from_orm(addon)