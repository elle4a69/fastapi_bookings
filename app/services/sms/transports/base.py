import re
from datetime import datetime
from typing import Optional, Protocol, List, Dict, Any, runtime_checkable
from fastapi import Request
from pydantic import BaseModel, Field
from ....models.sms_account import SmsAccount

def normalize_sms_destination(to_phone: str) -> Optional[str]:
    """Return an E.164-style destination without '+', or None when malformed."""
    digits = re.sub(r"\D", "", to_phone or "")
    if digits.startswith("6104") and len(digits) == 12:
        digits = "614" + digits[4:]
    elif digits.startswith("04") and len(digits) == 10:
        digits = "61" + digits[1:]
    elif digits.startswith("4") and len(digits) == 9:
        digits = "61" + digits

    if digits.startswith("61") and not re.fullmatch(r"614\d{8}", digits):
        return None
    if not re.fullmatch(r"[1-9]\d{7,14}", digits):
        return None
    return digits


class NormalizedInboundMessage(BaseModel):
    event_key: str = Field(description="Unique event/message ID from the provider")
    sender: str = Field(description="Normalized customer phone number")
    to: str = Field(description="Normalized target sender number")
    body: str = Field(description="Body of the SMS message")
    received_at: datetime = Field(description="Timestamp of when the message was received by the provider")
    media_urls: List[str] = Field(default_factory=list, description="Associated MMS media attachments")
    raw_payload: str = Field(description="JSON serialized raw payload for retention")


class OutboundSmsCommand(BaseModel):
    to: str = Field(description="Target destination E.164 phone number")
    body: str = Field(description="Message content")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for delivery retry safety")


class TransportSendResult(BaseModel):
    status: str = Field(description="'success', 'error', 'skipped', 'exception'")
    provider_message_id: Optional[str] = Field(None, description="Message ID returned by provider")
    error_code: Optional[str] = Field(None, description="Error code if send failed")
    error_message: Optional[str] = Field(None, description="Error message description")
    raw_response: Optional[str] = Field(None, description="Raw provider response body")


class DeliveryUpdate(BaseModel):
    provider_message_id: str
    status: str  # 'delivered', 'failed', 'sent', etc.
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_payload: Optional[str] = None


@runtime_checkable
class SmsTransportAdapter(Protocol):
    transport_type: str

    async def verify_webhook(self, request: Request, account: SmsAccount) -> None:
        """Verify the webhook signature/headers. Raise HTTPException if verification fails."""
        ...

    async def parse_inbound(self, request: Request, account: SmsAccount) -> NormalizedInboundMessage:
        """Parse raw request body into a normalized inbound message object."""
        ...

    async def send(self, account: SmsAccount, command: OutboundSmsCommand) -> TransportSendResult:
        """Deliver the outbound SMS via the provider API."""
        ...

    async def parse_delivery_receipt(self, request: Request, account: SmsAccount) -> DeliveryUpdate:
        """Parse raw delivery receipt webhook into a normalized DeliveryUpdate."""
        ...

    def normalise_address(self, value: str) -> Optional[str]:
        """Normalise phone numbers to E.164 without '+'. Return None if invalid."""
        ...
