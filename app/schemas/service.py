"""Pydantic models for services."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ServiceBase(BaseModel):
    name: str = Field(..., description="Service name")
    description: Optional[str] = Field(None, description="Description of the service")
    duration: int = Field(..., ge=1, description="Duration in minutes")
    price: Optional[float] = Field(None, description="Price of the service")
    active: bool = Field(True, description="Whether the service is available for booking")


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = Field(None, ge=1)
    price: Optional[float] = None
    active: Optional[bool] = None


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