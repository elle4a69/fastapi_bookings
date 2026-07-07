"""Schemas for categories and service categories."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    active: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ServiceCategoryBase(BaseModel):
    service_id: int
    category_id: int


class ServiceCategoryOut(ServiceCategoryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)