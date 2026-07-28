
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import get_current_admin, get_current_tenant, get_db
from ...models.tenant import Tenant
from ...models.service import Service
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
def list_products(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> List[ProductOut]:
    products = db.query(ProductModel).filter(ProductModel.tenant_id == tenant.id).all()
    return [ProductOut.from_orm(p) for p in products]


@router.post("", response_model=ProductOut)
def create_product(
    product_in: ProductCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ProductOut:
    product = ProductModel(tenant_id=tenant.id, **product_in.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Product SKU '{product_in.sku}' already exists") from exc
    db.refresh(product)
    return ProductOut.from_orm(product)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ProductOut:
    product = db.query(ProductModel).filter(ProductModel.id == product_id, ProductModel.tenant_id == tenant.id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut.from_orm(product)


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    product_in: ProductUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ProductOut:
    product = db.query(ProductModel).filter(ProductModel.id == product_id, ProductModel.tenant_id == tenant.id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in product_in.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        sku = product_in.sku or product.sku
        raise HTTPException(status_code=409, detail=f"Product SKU '{sku}' already exists") from exc
    db.refresh(product)
    return ProductOut.from_orm(product)


@router.delete("/{product_id}", response_model=ProductOut)
def delete_product(
    product_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ProductOut:
    product = db.query(ProductModel).filter(ProductModel.id == product_id, ProductModel.tenant_id == tenant.id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return ProductOut.from_orm(product)


@router.post("/assign", response_model=ServiceProductOut)
def assign_product_to_service(
    association: ServiceProductBase,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_admin),
) -> ServiceProductOut:
    service = db.query(Service).filter(Service.id == association.service_id, Service.tenant_id == tenant.id).first()
    product = db.query(ProductModel).filter(ProductModel.id == association.product_id, ProductModel.tenant_id == tenant.id).first()
    if not service or not product:
        raise HTTPException(status_code=404, detail="Service or product not found")
    existing = db.query(ServiceProductModel).filter(
        ServiceProductModel.tenant_id == tenant.id,
        ServiceProductModel.service_id == association.service_id,
        ServiceProductModel.product_id == association.product_id,
    ).first()
    if existing:
        return ServiceProductOut.from_orm(existing)
    record = ServiceProductModel(tenant_id=tenant.id, **association.model_dump())
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Product is already assigned to this service") from exc
    db.refresh(record)
    return ServiceProductOut.from_orm(record)
