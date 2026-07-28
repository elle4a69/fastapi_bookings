"""Schemas for add‑on models."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AddOnBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: Optional[Decimal] = None
    duration: int = 0
    active: bool = True
    is_visible: bool = True
    image: Optional[str] = None


class AddOnCreate(AddOnBase):
    service_id: Optional[int] = None


class AddOnUpdate(AddOnBase):
    service_id: Optional[int] = None


class AddOnOut(AddOnBase):
    id: int
    service_id: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
