"""Pydantic models for services."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ServiceBase(BaseModel):
    name: str = Field(..., description="Service name")
    description: Optional[str] = Field(None, description="Description of the service")
    duration: int = Field(..., ge=1, description="Duration in minutes")
    price: Optional[Decimal] = Field(None, description="Price of the service")
    active: bool = Field(True, description="Whether the service is available for booking")
    is_visible: bool = Field(True, description="Whether the service is visible publicly")
    deposit_amount: Decimal = Field(Decimal("0.0"), description="Required deposit amount")
    tax_rate_id: Optional[int] = Field(None, description="Identifier of the associated tax rate")
    min_group_size: int = Field(1, ge=1, description="Minimum spots/people for group booking")
    max_group_size: Optional[int] = Field(None, ge=1, description="Maximum spots/people for group booking")


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = Field(None, ge=1)
    price: Optional[Decimal] = None
    active: Optional[bool] = None
    is_visible: Optional[bool] = None
    deposit_amount: Optional[Decimal] = None
    tax_rate_id: Optional[int] = None
    min_group_size: Optional[int] = Field(None, ge=1)
    max_group_size: Optional[int] = Field(None, ge=1)


class ServiceInDBBase(ServiceBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class Service(ServiceInDBBase):
    pass


class ServiceListResponse(BaseModel):
    ok: bool
    data: list[Service]
    meta: dict


class ServiceResponse(BaseModel):
    ok: bool
    data: Service