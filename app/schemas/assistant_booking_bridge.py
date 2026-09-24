"""Deliberately small request/response contract for Assistant UI booking calls."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AvailabilityRequest(BaseModel):
    service_id: int = Field(gt=0)
    start_time: datetime
    end_time: datetime


class ProposalRequest(BaseModel):
    service_id: int = Field(gt=0)
    start_time: datetime


class ConfirmRequest(BaseModel):
    proposal_id: str = Field(min_length=36, max_length=36)
    request_id: str = Field(min_length=8, max_length=96)
    customer_name: str = Field(min_length=1, max_length=200)
    customer_phone: Optional[str] = Field(default=None, max_length=64)
    customer_email: Optional[str] = Field(default=None, max_length=254)


class BridgeError(BaseModel):
    ok: bool = False
    error: dict
