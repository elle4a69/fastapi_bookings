"""Schemas for the commercial checkout shell."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class QuoteLine(BaseModel):
    line_type: str
    item_id: Optional[int] = None
    description: str
    quantity: int = 1
    unit_price: float = 0.0
    amount: float = 0.0


class QuoteRequest(BaseModel):
    booking_id: Optional[int] = None
    client_id: Optional[int] = None
    service_id: Optional[int] = None
    add_on_ids: list[int] = Field(default_factory=list)
    product_ids: list[int] = Field(default_factory=list)
    package_id: Optional[int] = None
    promotion_code: Optional[str] = None
    tip_amount: float = 0.0
    currency: str = "USD"


class QuoteResponse(BaseModel):
    ok: bool = True
    data: dict


class InvoiceLineBase(BaseModel):
    line_type: str
    item_id: Optional[int] = None
    description: str
    quantity: int = 1
    unit_price: float = 0.0
    amount: float = 0.0


class InvoiceLineCreate(InvoiceLineBase):
    pass


class InvoiceLineOut(InvoiceLineBase):
    id: int
    invoice_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InvoiceBase(BaseModel):
    booking_id: Optional[int] = None
    client_id: Optional[int] = None
    currency: str = "USD"
    subtotal: float = 0.0
    discount_total: float = 0.0
    tax_total: float = 0.0
    tip_total: float = 0.0
    total: float = 0.0
    amount_paid: float = 0.0
    status: str = "draft"
    promotion_code: Optional[str] = None
    notes: Optional[str] = None


class InvoiceCreate(BaseModel):
    booking_id: Optional[int] = None
    client_id: Optional[int] = None
    quote: QuoteRequest
    status: str = "draft"
    notes: Optional[str] = None


class InvoiceStatusUpdate(BaseModel):
    status: str
    amount_paid: Optional[float] = None


class InvoiceOut(InvoiceBase):
    id: int
    created_at: datetime
    updated_at: datetime
    lines: list[InvoiceLineOut] = []
    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    ok: bool
    data: InvoiceOut


class InvoiceListResponse(BaseModel):
    ok: bool
    data: list[InvoiceOut]
    meta: dict


class PromotionCodeBase(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str = "fixed"
    discount_value: float = 0.0
    active: bool = True
    max_redemptions: Optional[int] = None
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class PromotionCodeCreate(PromotionCodeBase):
    pass


class PromotionCodeUpdate(BaseModel):
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    active: Optional[bool] = None
    max_redemptions: Optional[int] = None
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class PromotionCodeOut(PromotionCodeBase):
    id: int
    times_redeemed: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PromotionValidationResponse(BaseModel):
    ok: bool
    data: dict


class TaxRateBase(BaseModel):
    name: str
    rate_percent: float = 0.0
    active: bool = True


class TaxRateCreate(TaxRateBase):
    pass


class TaxRateUpdate(BaseModel):
    name: Optional[str] = None
    rate_percent: Optional[float] = None
    active: Optional[bool] = None


class TaxRateOut(TaxRateBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TipCreate(BaseModel):
    amount: float
    note: Optional[str] = None


class TipOut(TipCreate):
    id: int
    invoice_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PaymentProcessorConfigBase(BaseModel):
    provider: str
    enabled: bool = False
    display_name: Optional[str] = None
    public_key: Optional[str] = None
    config_json: Optional[str] = None


class PaymentProcessorConfigCreate(PaymentProcessorConfigBase):
    pass


class PaymentProcessorConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    display_name: Optional[str] = None
    public_key: Optional[str] = None
    config_json: Optional[str] = None


class PaymentProcessorConfigOut(PaymentProcessorConfigBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
