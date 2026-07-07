"""Schemas for additional/intake/client fields."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AdditionalFieldBase(BaseModel):
    scope: str = "booking"
    service_id: Optional[int] = None
    name: str
    label: str
    field_type: str = "text"
    required: bool = False
    active: bool = True
    position: int = 0
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    options_json: Optional[str] = None
    default_value: Optional[str] = None


class AdditionalFieldCreate(AdditionalFieldBase):
    pass


class AdditionalFieldUpdate(BaseModel):
    scope: Optional[str] = None
    service_id: Optional[int] = None
    name: Optional[str] = None
    label: Optional[str] = None
    field_type: Optional[str] = None
    required: Optional[bool] = None
    active: Optional[bool] = None
    position: Optional[int] = None
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    options_json: Optional[str] = None
    default_value: Optional[str] = None


class AdditionalFieldOut(AdditionalFieldBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AdditionalFieldResponseBase(BaseModel):
    field_id: int
    client_id: Optional[int] = None
    booking_id: Optional[int] = None
    value: Optional[str] = None


class AdditionalFieldResponseCreate(AdditionalFieldResponseBase):
    pass


class AdditionalFieldResponseOut(AdditionalFieldResponseBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AdditionalFieldSubmitRequest(BaseModel):
    client_id: Optional[int] = None
    booking_id: Optional[int] = None
    responses: list[AdditionalFieldResponseCreate]
