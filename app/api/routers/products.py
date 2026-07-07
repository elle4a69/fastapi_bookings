"""Product CRUD routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_db
from ...models.product import Product as ProductModel, ServiceProduct as ServiceProductModel
from ...schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductOut,
    ServiceProductBase,
    ServiceProductOut,
)

router = APIRouter(prefix="/api/admin/products", tags=["products"])


@router.get("", response_model=List[ProductOut])
def list_products(db: Session = Depends(get_db)) -> List[ProductOut]:
    products = db.query(ProductModel).all()
    return [ProductOut.from_orm(p) for p in products]


@router.post("", response_model=ProductOut)
def create_product(
    product_in: ProductCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ProductOut:
    product = ProductModel(**product_in.dict())
    db.add(product)
    db.commit()
    db.refresh(product)
    return ProductOut.from_orm(product)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductOut:
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut.from_orm(product)


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    product_in: ProductUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ProductOut:
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in product_in.dict(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return ProductOut.from_orm(product)


@router.delete("/{product_id}", response_model=ProductOut)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ProductOut:
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return ProductOut.from_orm(product)


@router.post("/assign", response_model=ServiceProductOut)
def assign_product_to_service(
    association: ServiceProductBase,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ServiceProductOut:
    record = ServiceProductModel(**association.dict())
    db.add(record)
    db.commit()
    db.refresh(record)
    return ServiceProductOut.from_orm(record)