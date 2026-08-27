import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import Request
from .base import (
    SmsTransportAdapter, 
    NormalizedInboundMessage, 
    OutboundSmsCommand, 
    TransportSendResult, 
    DeliveryUpdate,
    normalize_sms_destination
)
from ....models.sms_account import SmsAccount

class FakeTransportAdapter(SmsTransportAdapter):
    transport_type: str = "simulator"
    
    # Static list to track sent messages during testing / simulation
    sent_messages: List[Dict[str, Any]] = []

    async def verify_webhook(self, request: Request, account: SmsAccount) -> None:
        # Fake webhook needs no signature verification
        pass

    async def parse_inbound(self, request: Request, account: SmsAccount) -> NormalizedInboundMessage:
        try:
            body_bytes = await request.body()
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            payload = {}
            
        event_key = payload.get("message_id") or payload.get("event_key") or f"fake-{datetime.now(timezone.utc).timestamp()}"
        sender = self.normalise_address(payload.get("sender", ""))
        to = self.normalise_address(payload.get("to", ""))
        body = payload.get("message", "")
        received_at_str = payload.get("received_at")
        
        if received_at_str:
            try:
                received_at = datetime.fromisoformat(received_at_str.replace("Z", "+00:00"))
            except ValueError:
                received_at = datetime.now(timezone.utc)
        else:
            received_at = datetime.now(timezone.utc)
            
        return NormalizedInboundMessage(
            event_key=event_key,
            sender=sender,
            to=to,
            body=body,
            received_at=received_at,
            media_urls=payload.get("media_urls", []),
            raw_payload=json.dumps(payload)
        )

    async def send(self, account: SmsAccount, command: OutboundSmsCommand) -> TransportSendResult:
        clean_to = self.normalise_address(command.to)
        if not clean_to:
            return TransportSendResult(
                status="error",
                error_code="INVALID_DESTINATION",
                error_message="Invalid phone number format."
            )
            
        # Simulate send delay or logs
        provider_msg_id = f"msg_{secrets_token_hex()}" if 'secrets_token_hex' in globals() else f"msg_{datetime.now(timezone.utc).timestamp()}"
        
        sent_record = {
            "to": clean_to,
            "body": command.body,
            "sender": account.sender_address,
            "idempotency_key": command.idempotency_key,
            "provider_message_id": provider_msg_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.sent_messages.append(sent_record)
        
        return TransportSendResult(
            status="success",
            provider_message_id=provider_msg_id,
            raw_response=json.dumps(sent_record)
        )

    async def parse_delivery_receipt(self, request: Request, account: SmsAccount) -> DeliveryUpdate:
        try:
            body_bytes = await request.body()
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            payload = {}
            
        return DeliveryUpdate(
            provider_message_id=payload.get("provider_message_id", ""),
            status=payload.get("status", "delivered"),
            error_code=payload.get("error_code"),
            error_message=payload.get("error_message"),
            raw_payload=json.dumps(payload)
        )

    def normalise_address(self, value: str) -> Optional[str]:
        return normalize_sms_destination(value)

# Import helper inside functions to avoid module load cycles
import secrets
def secrets_token_hex():
    return secrets.token_hex(8)
from typing import Any
