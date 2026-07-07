"""Schemas for add‑on models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AddOnBase(BaseModel):
    service_id: int
    name: str
    description: Optional[str] = None
    price: Optional[float] = None
    duration: int = 0
    active: bool = True


class AddOnCreate(AddOnBase):
    pass


class AddOnUpdate(AddOnBase):
    pass


class AddOnOut(AddOnBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)