import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import httpx
from fastapi import Request, HTTPException

from .base import (
    SmsTransportAdapter, 
    NormalizedInboundMessage, 
    OutboundSmsCommand, 
    TransportSendResult, 
    DeliveryUpdate,
    normalize_sms_destination
)
from ....models.sms_account import SmsAccount

logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.mobilemessage.com.au/v1"

class MobileMessageAdapter(SmsTransportAdapter):
    transport_type: str = "mobilemessage"

    async def verify_webhook(self, request: Request, account: SmsAccount) -> None:
        """Verify webhook signature/secret. Fail-closed lockout in favor of Chatwoot."""
        logger.warning(f"Direct carrier webhook locked out for MobileMessage (SMS Account {account.id})")
        raise HTTPException(
            status_code=410,
            detail="MobileMessage direct carrier webhooks are permanently locked out and deactivated. Route traffic through Chatwoot omnichannel inboxes.",
        )

    async def parse_inbound(self, request: Request, account: SmsAccount) -> NormalizedInboundMessage:
        """Parse inbound webhook. Fail-closed lockout in favor of Chatwoot."""
        logger.warning(f"Direct carrier inbound parsing locked out for MobileMessage (SMS Account {account.id})")
        raise HTTPException(
            status_code=410,
            detail="MobileMessage direct carrier webhooks are permanently locked out and deactivated. Route traffic through Chatwoot omnichannel inboxes.",
        )

    async def send(self, account: SmsAccount, command: OutboundSmsCommand) -> TransportSendResult:
        """Send SMS via carrier. Fail-closed lockout in favor of Chatwoot."""
        logger.warning(f"Direct carrier send locked out for MobileMessage (SMS Account {account.id})")
        return TransportSendResult(
            status="error",
            error_code="DIRECT_CARRIER_LOCKED_OUT",
            error_message="MobileMessage direct carrier transport is locked out and deactivated. Route all outbound SMS via Chatwoot omnichannel inboxes.",
        )

    async def parse_delivery_receipt(self, request: Request, account: SmsAccount) -> DeliveryUpdate:
        """Parse delivery receipt. Fail-closed lockout in favor of Chatwoot."""
        logger.warning(f"Direct carrier delivery receipt locked out for MobileMessage (SMS Account {account.id})")
        raise HTTPException(
            status_code=410,
            detail="MobileMessage direct carrier delivery receipts are permanently locked out and deactivated. Route traffic through Chatwoot omnichannel inboxes.",
        )

    def normalise_address(self, value: str) -> Optional[str]:
        return normalize_sms_destination(value)
        return normalize_sms_destination(value)
