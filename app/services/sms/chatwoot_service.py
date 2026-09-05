"""Legacy outbound Chatwoot client retained until Package D."""

import logging
from typing import Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...models.sms_chatwoot import SmsChatwootBinding
from ...models.sms_conversation import SmsConversation


logger = logging.getLogger(__name__)


async def send_chatwoot_message(
    db: Session,
    conversation: SmsConversation,
    body: str,
    source_id: Optional[str] = None,
) -> int:
    """Send through the legacy outbound path, pending Package D replacement."""
    binding = db.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.tenant_id == conversation.tenant_id,
        SmsChatwootBinding.provider_id == conversation.provider_id,
        SmsChatwootBinding.is_enabled == True,
    ).first()

    if not binding:
        raise ValueError("No enabled Chatwoot binding found for conversation.")

    decrypted_token = binding.chatwoot_api_token
    base_url = binding.chatwoot_base_url.rstrip("/")
    url = f"{base_url}/api/v1/accounts/{binding.chatwoot_account_id}/conversations/{conversation.chatwoot_conversation_id}/messages"

    headers = {
        "api_access_token": decrypted_token,
        "Content-Type": "application/json",
    }
    payload = {
        "content": body,
        "message_type": "outgoing",
    }
    if source_id:
        payload["source_id"] = source_id

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return int(data["id"])
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError):
        logger.error("Chatwoot outbound request failed")
        raise


def process_chatwoot_webhook(
    db: Session, payload: dict, token: Optional[str]
) -> dict:
    """Fail closed for callers of the retired token-authenticated processor."""
    del db, payload, token
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Legacy Chatwoot webhook is retired.",
    )
