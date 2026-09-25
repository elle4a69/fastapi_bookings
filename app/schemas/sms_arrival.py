"""Privacy-minimised contracts for booking-linked arrival sessions."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ArrivalCheckInRequest(BaseModel):
    # Length validation happens inside the service so framework validation
    # errors cannot reflect the submitted bearer value back to the caller.
    token: SecretStr = Field(repr=False)


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
    state: Literal["invited", "arrived", "acknowledged", "expired"]
    arrived_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    created_at: datetime
    expires_at: datetime
    booking_time: datetime

    model_config = ConfigDict(from_attributes=True)
