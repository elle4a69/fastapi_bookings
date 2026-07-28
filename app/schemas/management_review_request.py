"""Pydantic schemas for ManagementReviewRequests."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ManagementReviewRequestBase(BaseModel):
    client_id: int
    service_id: Optional[int] = None
    provider_id: Optional[int] = None
    location_id: Optional[int] = None
    preferred_time: Optional[datetime] = None
    reason: Optional[str] = None


class ManagementReviewRequestCreate(ManagementReviewRequestBase):
    pass


class ManagementReviewRequestUpdate(BaseModel):
    state: Optional[str] = None  # pending, approved, rejected
    resolution_notes: Optional[str] = None


class ManagementReviewRequestOut(ManagementReviewRequestBase):
    id: int
    tenant_id: int
    state: str
    slot_reserved: bool
    payment_taken: bool
    resolution_notes: Optional[str] = None
    resolved_by_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManagementReviewRequestListResponse(BaseModel):
    ok: bool
    data: list[ManagementReviewRequestOut]
    meta: dict


class ManagementReviewRequestResponse(BaseModel):
    ok: bool
    data: ManagementReviewRequestOut
