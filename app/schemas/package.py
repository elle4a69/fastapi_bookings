"""Schemas for service packages and steps."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PackageBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: Optional[Decimal] = None
    active: bool = True


class PackageCreate(PackageBase):
    pass


class PackageUpdate(PackageBase):
    pass


class PackageOut(PackageBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PackageStepBase(BaseModel):
    package_id: int
    service_id: int
    order: int
    offset_days: int = 0
    price: Optional[Decimal] = None
    active: bool = True


class PackageStepCreate(PackageStepBase):
    pass


class PackageStepUpdate(PackageStepBase):
    pass


class PackageStepOut(PackageStepBase):
    id: int
    model_config = ConfigDict(from_attributes=True)