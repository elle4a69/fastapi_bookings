"""Category CRUD routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db
from ...models.tenant import Tenant
from ...models.category import Category as CategoryModel, ServiceCategory as ServiceCategoryModel
from ...schemas.category import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/api/admin/categories", tags=["categories"])


@router.get("", response_model=List[CategoryOut])
def list_categories(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> List[CategoryOut]:
    categories = db.query(CategoryModel).filter(CategoryModel.tenant_id == tenant.id).all()
    return [CategoryOut.from_orm(c) for c in categories]


@router.post("", response_model=CategoryOut)
def create_category(
    category_in: CategoryCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> CategoryOut:
    category = CategoryModel(tenant_id=tenant.id, **category_in.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return CategoryOut.from_orm(category)


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(
    category_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> CategoryOut:
    category = db.query(CategoryModel).filter(CategoryModel.id == category_id, CategoryModel.tenant_id == tenant.id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return CategoryOut.from_orm(category)


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    category_in: CategoryUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> CategoryOut:
    category = db.query(CategoryModel).filter(CategoryModel.id == category_id, CategoryModel.tenant_id == tenant.id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    for field, value in category_in.dict(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return CategoryOut.from_orm(category)


@router.delete("/{category_id}", response_model=CategoryOut)
def delete_category(
    category_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> CategoryOut:
    category = db.query(CategoryModel).filter(CategoryModel.id == category_id, CategoryModel.tenant_id == tenant.id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(category)
    db.commit()
    return CategoryOut.from_orm(category)
