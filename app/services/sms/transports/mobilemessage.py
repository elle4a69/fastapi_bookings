import json
import logging
from datetime import datetime, timezone
from typing import Optional
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
from ....models.sms_account import SmsAccount, SmsCredentialError

logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.mobilemessage.com.au/v1"

class MobileMessageAdapter(SmsTransportAdapter):
    transport_type: str = "mobilemessage"

    async def verify_webhook(self, request: Request, account: SmsAccount) -> None:
        """Verify webhook signature/secret.
        MobileMessage uses a configured secret token sent as a header
        or a query parameter, if set up in the account credentials.
        """
        try:
            creds = account.credentials or {}
        except SmsCredentialError as exc:
            raise HTTPException(
                status_code=503,
                detail="SMS webhook authentication is unavailable.",
            ) from exc
        webhook_secret = creds.get("webhook_secret")
        if not webhook_secret:
            # If no secret is configured, allow the webhook but log a warning.
            return

        # Check standard headers for authorization/signature
        signature = request.headers.get("X-MobileMessage-Signature") or request.query_params.get("secret")
        if not signature or signature != webhook_secret:
            logger.warning("MobileMessage webhook authentication failed.")
            raise HTTPException(status_code=401, detail="Invalid webhook signature or secret.")

    async def parse_inbound(self, request: Request, account: SmsAccount) -> NormalizedInboundMessage:
        try:
            body_bytes = await request.body()
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            logger.error("MobileMessage inbound payload parsing failed.")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        # MobileMessage inbound payload format:
        # {
        #   "message_id": "...",
        #   "sender": "0412345678",
        #   "to": "61400000010",
        #   "message": "Hello...",
        #   "received_at": "2026-08-11T10:00:00Z"
        # }
        event_key = payload.get("message_id")
        if not event_key:
            # Fallback to generating a key if missing
            event_key = f"mm-{hash(json.dumps(payload))}"

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
        try:
            creds = account.credentials or {}
        except SmsCredentialError:
            return TransportSendResult(
                status="error",
                error_code="CREDENTIALS_UNAVAILABLE",
                error_message="SMS delivery credentials are unavailable.",
            )
        username = creds.get("username", "").strip()
        password = creds.get("password", "").strip()
        
        if not username or not password:
            return TransportSendResult(
                status="skipped",
                error_code="MISSING_CREDENTIALS",
                error_message="MobileMessage credentials missing in account config."
            )

        clean_to = self.normalise_address(command.to)
        if not clean_to:
            return TransportSendResult(
                status="error",
                error_code="INVALID_DESTINATION",
                error_message="Invalid Australian mobile or phone number format."
            )

        sender_id = creds.get("sender", "").strip() or account.sender_address
        
        payload_msg = {
            "to": clean_to,
            "message": command.body
        }
        if sender_id:
            payload_msg["sender"] = sender_id

        headers = {}
        if command.idempotency_key:
            headers["Idempotency-Key"] = command.idempotency_key

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{API_BASE_URL}/messages",
                    json={"messages": [payload_msg]},
                    auth=(username, password),
                    headers=headers,
                    timeout=15.0
                )
                
                if resp.status_code in (200, 201):
                    data = resp.json()
                    results = data.get("results", [])
                    
                    # Check if the single message succeeded
                    if results and results[0].get("status") == "success":
                        provider_msg_id = results[0].get("message_id")
                        return TransportSendResult(
                            status="success",
                            provider_message_id=provider_msg_id,
                        )
                    else:
                        return TransportSendResult(
                            status="error",
                            error_code="REJECTED_BY_PROVIDER",
                            error_message="Provider rejected the outbound command.",
                        )
                else:
                    return TransportSendResult(
                        status="error",
                        error_code="PROVIDER_HTTP_ERROR",
                        error_message="Provider delivery request failed.",
                    )
            except Exception:
                logger.error("MobileMessage outbound request failed.")
                return TransportSendResult(
                    status="error",
                    error_code="CONNECTION_ERROR",
                    error_message="Provider delivery request failed.",
                )

    async def parse_delivery_receipt(self, request: Request, account: SmsAccount) -> DeliveryUpdate:
        try:
            body_bytes = await request.body()
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            logger.error("MobileMessage delivery receipt parsing failed.")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        # Expected receipt format:
        # {
        #   "message_id": "msg_123",
        #   "status": "delivered",
        #   "error_code": null,
        #   "error_message": null
        # }
        return DeliveryUpdate(
            provider_message_id=payload.get("message_id", ""),
            status=payload.get("status", "unknown"),
            error_code=(
                "PROVIDER_REPORTED_FAILURE"
                if payload.get("error_code") or payload.get("error_message")
                else None
            ),
            error_message=(
                "Provider reported a delivery failure."
                if payload.get("error_code") or payload.get("error_message")
                else None
            ),
            raw_payload=None,
        )

    def normalise_address(self, value: str) -> Optional[str]:
        return normalize_sms_destination(value)
