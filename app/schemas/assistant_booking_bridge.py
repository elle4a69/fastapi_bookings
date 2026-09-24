"""Deliberately small request/response contract for Assistant UI booking calls."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

class _UtcTimes(BaseModel):
    @field_validator("start_time", "end_time", check_fields=False)
    @classmethod
    def require_utc_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("offset-aware UTC timestamp required")
        return value.astimezone(__import__("datetime").timezone.utc)


class AvailabilityRequest(_UtcTimes):
    service_id: int = Field(gt=0)
    start_time: datetime
    end_time: datetime


class ProposalRequest(_UtcTimes):
    service_id: int = Field(gt=0)
    start_time: datetime


class ConfirmRequest(BaseModel):
    proposal_id: str = Field(min_length=36, max_length=36)
    request_id: str = Field(min_length=8, max_length=96)
    customer_name: str = Field(min_length=1, max_length=200)
    customer_phone: Optional[str] = Field(default=None, max_length=64)
    customer_email: Optional[str] = Field(default=None, max_length=254)


class CanonicalProposalSummary(BaseModel):
    """Customer-safe proposal snapshot; display fields are never scope selectors."""

    service_id: int = Field(gt=0)
    service_name: str = Field(min_length=1, max_length=255)
    provider_display_name: str = Field(min_length=1, max_length=255)
    location_display_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    start_time: str = Field(min_length=1)
    end_time: str = Field(min_length=1)
    duration_minutes: int = Field(gt=0)
    price: str = Field(pattern=r"^\d+\.\d{2}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    show_duration: bool
    timezone: str = Field(min_length=1, max_length=128)


class ProposalData(BaseModel):
    proposal_id: str = Field(min_length=36, max_length=36)
    canonical_summary: CanonicalProposalSummary
    expires_at: datetime
    status: str


class ProposalResponse(BaseModel):
    ok: bool
    data: ProposalData


class BridgeError(BaseModel):
    ok: bool = False
    error: dict
