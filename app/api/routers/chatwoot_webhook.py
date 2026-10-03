import hashlib
import hmac
import logging
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.core.config import settings
from app.services.agent_runner import run_agent_turn

router = APIRouter(prefix="/webhooks", tags=["chatwoot"])
logger = logging.getLogger(__name__)


def verify_chatwoot_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Verify the Chatwoot webhook signature."""
    if not signature_header:
        return False
    
    secret = settings.CHATWOOT_WEBHOOK_SECRET
    if not secret:
        # If secret is not configured, we might either fail all or pass all.
        # It's safer to fail if a signature is required but secret is missing,
        # but let's assume if there's no secret we can't verify (or we might want to log a warning).
        logger.warning("CHATWOOT_WEBHOOK_SECRET is not configured.")
        return False

    # The signature might be plain hex or prefixed with "sha256="
    if signature_header.startswith("sha256="):
        provided_signature = signature_header[7:]
    else:
        provided_signature = signature_header

    mac = hmac.new(
        secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    )
    expected_signature = mac.hexdigest()

    return hmac.compare_digest(expected_signature, provided_signature)


@router.post("/chatwoot")
async def chatwoot_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_chatwoot_signature: str | None = Header(default=None)
) -> Dict[str, str]:
    """Handle incoming webhooks from Chatwoot."""
    raw_body = await request.body()
    
    # Verify signature
    if not verify_chatwoot_signature(raw_body, x_chatwoot_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    payload = await request.json()
    
    event = payload.get("event")
    if event != "message_created":
        return {"status": "event_ignored"}
        
    message_type = payload.get("message_type")
    # message_type 0 is incoming, 1 is outgoing. It can be string or int in Chatwoot API variations.
    if message_type not in (0, "incoming"):
        return {"status": "direction_ignored"}
        
    conversation = payload.get("conversation", {})
    assignee_id = conversation.get("assignee_id")
    status = conversation.get("status")
    
    if assignee_id is not None or status == "resolved":
        return {"status": "human_handling"}
        
    # Queue background task
    account_id = payload.get("account", {}).get("id") or 0
    inbox_id = payload.get("inbox", {}).get("id") or 0
    conversation_id = conversation.get("id") or 0
    sender_phone = payload.get("sender", {}).get("phone_number", "")
    message_text = payload.get("content", "")
    
    background_tasks.add_task(
        run_agent_turn,
        chatwoot_account_id=account_id,
        chatwoot_inbox_id=inbox_id,
        conversation_id=conversation_id,
        sender_phone=sender_phone,
        message_text=message_text
    )
    
    return {"status": "queued"}
