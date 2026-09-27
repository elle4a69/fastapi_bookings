"""Pydantic models for services."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .resource import ServiceResourceRequirementOut, ServiceResourceRequirementCreate


class ServiceBase(BaseModel):
    name: str = Field(..., description="Service name")
    description: Optional[str] = Field(None, description="Description of the service")
    duration: int = Field(..., ge=1, description="Duration in minutes")
    price: Optional[Decimal] = Field(None, description="Price of the service")
    active: bool = Field(True, description="Whether the service is available for booking")
    is_visible: bool = Field(True, description="Whether the service is visible publicly")
    allow_in_call: bool = Field(True, description="Whether the service allows in-call booking")
    allow_out_call: bool = Field(True, description="Whether the service allows out-call booking")
    outcall_price: Optional[Decimal] = Field(
        None,
        description="Out-call price. Defaults to price if out-call is enabled and not explicitly specified.",
    )
    outcall_buffer_before: int = Field(0, ge=0, description="Out-call buffer before appointment in minutes")
    outcall_buffer_after: int = Field(0, ge=0, description="Out-call buffer after appointment in minutes")
    deposit_amount: Decimal = Field(Decimal("0.0"), description="Required deposit amount")
    tax_rate_id: Optional[int] = Field(None, description="Identifier of the associated tax rate")
    buffer_before: int = Field(0, ge=0, description="Prep buffer in minutes before appointment")
    buffer_after: int = Field(0, ge=0, description="Cleanup buffer in minutes after appointment")
    fixed_start_times: Optional[str] = Field(None, description="Comma-separated fixed start times (HH:MM)")
    min_group_size: int = Field(1, ge=1, description="Minimum spots/people for group booking")
    max_group_size: Optional[int] = Field(None, ge=1, description="Maximum spots/people for group booking")
    max_advance_days: Optional[int] = Field(None, description="Service-specific booking horizon override in days")
    image: Optional[str] = Field(None, description="Image URL or Base64 data")


class ServiceCreate(ServiceBase):
    category_ids: Optional[list[int]] = None
    provider_ids: Optional[list[int]] = None
    addon_ids: Optional[list[int]] = None
    product_ids: Optional[list[int]] = None
    requirements: Optional[list[ServiceResourceRequirementCreate]] = None

    @model_validator(mode="after")
    def default_outcall_price(self) -> "ServiceCreate":
        if self.allow_out_call and self.outcall_price is None and self.price is not None:
            self.outcall_price = self.price
        return self


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = Field(None, ge=1)
    price: Optional[Decimal] = None
    active: Optional[bool] = None
    is_visible: Optional[bool] = None
    allow_in_call: Optional[bool] = None
    allow_out_call: Optional[bool] = None
    outcall_price: Optional[Decimal] = None
    outcall_buffer_before: Optional[int] = Field(None, ge=0)
    outcall_buffer_after: Optional[int] = Field(None, ge=0)
    deposit_amount: Optional[Decimal] = None
    tax_rate_id: Optional[int] = None
    buffer_before: Optional[int] = Field(None, ge=0)
    buffer_after: Optional[int] = Field(None, ge=0)
    fixed_start_times: Optional[str] = None
    min_group_size: Optional[int] = Field(None, ge=1)
    max_group_size: Optional[int] = Field(None, ge=1)
    max_advance_days: Optional[int] = None
    image: Optional[str] = None
    category_ids: Optional[list[int]] = None
    provider_ids: Optional[list[int]] = None
    addon_ids: Optional[list[int]] = None
    product_ids: Optional[list[int]] = None
    requirements: Optional[list[ServiceResourceRequirementCreate]] = None


class ServiceInDBBase(ServiceBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class Service(ServiceInDBBase):
    category_ids: list[int] = []
    provider_ids: list[int] = []
    addon_ids: list[int] = []
    product_ids: list[int] = []
    requirements: list[ServiceResourceRequirementOut] = []


class ServiceListResponse(BaseModel):
    ok: bool
    data: list[Service]
    meta: dict


class ServiceResponse(BaseModel):
    ok: bool
    data: Service