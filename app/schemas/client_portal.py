"""Pydantic schemas for the Client Self-Service Portal and Dispute Center."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ClientOtpSendRequest(BaseModel):
    phone_or_email: str = Field(..., description="Client phone number or email address for OTP delivery")


class ClientOtpVerifyRequest(BaseModel):
    phone_or_email: str = Field(..., description="Client phone number or email address")
    code: str = Field(..., min_length=4, max_length=10, description="6-digit verification code")


class ClientProfile(BaseModel):
    id: int
    tenant_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    timezone: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ClientPortalAuthData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    client: ClientProfile


class ClientPortalAuthResponse(BaseModel):
    ok: bool = True
    message: str = "Authenticated successfully"
    data: ClientPortalAuthData


class ClientBookingItem(BaseModel):
    id: int
    tenant_id: int
    client_id: int
    provider_id: int
    service_id: int
    location_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    status: str
    notes: Optional[str] = None
    service_name: Optional[str] = None
    provider_name: Optional[str] = None
    location_name: Optional[str] = None
    price: Optional[float] = 0.0
    duration: Optional[int] = 0
    can_reschedule: bool = True
    can_cancel: bool = True
    has_dispute: bool = False
    dispute_id: Optional[int] = None
    dispute_status: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ClientRescheduleRequest(BaseModel):
    start_time: datetime = Field(..., description="Desired new appointment start time (ISO 8601)")


class ClientCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Optional cancellation reason")


class ClientInvoiceLineItem(BaseModel):
    id: int
    description: str
    quantity: int = 1
    unit_price: float
    total: float
    model_config = ConfigDict(from_attributes=True)


class ClientInvoiceItem(BaseModel):
    id: int
    tenant_id: int
    booking_id: Optional[int] = None
    service_name: Optional[str] = None
    subtotal: float
    discount_total: float = 0.0
    tax_total: float = 0.0
    tip_total: float = 0.0
    total: float
    amount_paid: float
    status: str
    currency: str = "USD"
    notes: Optional[str] = None
    created_at: datetime
    lines: List[ClientInvoiceLineItem] = []
    model_config = ConfigDict(from_attributes=True)


class ClientDisputeCreate(BaseModel):
    booking_id: Optional[int] = Field(None, description="Optional booking ID associated with the dispute")
    reason: str = Field(..., description="Reason category: incomplete_work, late_arrival, quality_concern, billing_dispute, other")
    description: str = Field(..., min_length=5, description="Detailed explanation of the issue")
    preferred_resolution: str = Field("redo_service", description="Desired remedy: redo_service, partial_refund, full_refund, credit_note")
    photos: Optional[List[str]] = Field(default=None, description="Optional URLs or base64 evidence images")


class ClientDisputeResponse(BaseModel):
    id: int
    tenant_id: int
    client_id: int
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    booking_id: Optional[int] = None
    booking_service_name: Optional[str] = None
    booking_start_time: Optional[datetime] = None
    status: str
    reason: str
    description: str
    preferred_resolution: str
    resolution_notes: Optional[str] = None
    photos: Optional[List[str]] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class AdminDisputeResolveRequest(BaseModel):
    status: str = Field(..., description="Updated status: under_review, resolved, rejected")
    resolution_notes: Optional[str] = Field(None, description="Resolution rationale, actions taken, or customer instructions")
