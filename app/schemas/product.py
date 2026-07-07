"""Schemas for product models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    sku: Optional[str] = None
    active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(ProductBase):
    pass


class ProductOut(ProductBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ServiceProductBase(BaseModel):
    service_id: int
    product_id: int


class ServiceProductOut(ServiceProductBase):
    id: int
    model_config = ConfigDict(from_attributes=True)