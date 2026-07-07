"""Pydantic models for payments."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PaymentBase(BaseModel):
    booking_id: int = Field(..., description="Associated booking identifier")
    amount: float = Field(..., gt=0, description="Amount paid")
    currency: str = Field("USD", description="Currency code")
    status: str = Field("pending", description="Payment status")


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(BaseModel):
    status: Optional[str] = None


class PaymentInDBBase(PaymentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class Payment(PaymentInDBBase):
    pass


class PaymentListResponse(BaseModel):
    ok: bool
    data: list[Payment]
    meta: dict


class PaymentResponse(BaseModel):
    ok: bool
    data: Payment