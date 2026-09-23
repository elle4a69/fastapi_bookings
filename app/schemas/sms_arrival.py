"""Privacy-minimised contracts for booking-linked arrival sessions."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ArrivalCheckInRequest(BaseModel):
    """OpenAPI contract; the public route parses this bearer body manually."""

    token: SecretStr = Field(min_length=24, max_length=512)

    model_config = ConfigDict(extra="forbid")


class ArrivalCheckInResponse(BaseModel):
    status: Literal["arrived", "already_arrived"]
    arrived_at: datetime


class ArrivalAcknowledgeResponse(BaseModel):
    status: Literal["acknowledged", "already_acknowledged"]
    acknowledged_at: datetime


class ArrivalListItem(BaseModel):
    """Staff-safe structural view; deliberately excludes token and customer PII."""

    id: int
    booking_id: int
    conversation_id: int
    provider_id: int
    sms_account_id: int
    service_id: int
    location_id: Optional[int]
    state: Literal["invited", "arrived", "acknowledged", "expired", "ineligible"]
    arrived_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    created_at: datetime
    expires_at: datetime
    booking_time: datetime

    model_config = ConfigDict(from_attributes=True)
