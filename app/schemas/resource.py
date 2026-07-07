"""Schemas for resource related models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ResourceBase(BaseModel):
    name: str
    type: str
    location_id: Optional[int] = None
    capacity: int = 1
    active: bool = True


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(ResourceBase):
    pass


class ResourceOut(ResourceBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ServiceResourceRequirementBase(BaseModel):
    service_id: int
    resource_type: str
    quantity: int = 1


class ServiceResourceRequirementCreate(ServiceResourceRequirementBase):
    pass


class ServiceResourceRequirementOut(ServiceResourceRequirementBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class BookingResourceAllocationOut(BaseModel):
    id: int
    booking_id: int
    resource_id: int
    quantity: int
    model_config = ConfigDict(from_attributes=True)