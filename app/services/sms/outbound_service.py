import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from ...models.sms_account import SmsAccount
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import SmsOutboundJob, SmsConversationEvent

logger = logging.getLogger(__name__)

OUTBOUND_SAFETY_BLOCKLIST = (
    "[[handoff",
    "system_prompt",
    "safety rules",
    "internal notes",
    "as an ai assistant",
    "internal policy",
    "under platform rules",
    "hidden notes",
    "prompt profile",
    "platform rules",
)


def is_outbound_body_safe(body: str) -> bool:
    normalized = body.strip().lower()
    return bool(normalized) and not any(term in normalized for term in OUTBOUND_SAFETY_BLOCKLIST)

def enqueue_outbound_message_transactional(
    db: Session,
    account: Optional[SmsAccount],
    conversation: SmsConversation,
    body: str,
    author_type: str,  # 'staff', 'fixed_autoresponder', 'ai', 'system'
    author_id: Optional[int] = None,
    status: str = "queued",  # 'queued', 'draft'
    parent_message_id: Optional[int] = None,
    customer_turn_ref: Optional[str] = None,
    client_request_id: Optional[str] = None
) -> SmsMessage:
    """Creates an SmsMessage and enqueues a delivery job in one transaction."""
    if account is not None and (
        account.id != conversation.sms_account_id
        or account.tenant_id != conversation.tenant_id
        or account.provider_id != conversation.provider_id
    ):
        raise ValueError("SMS account and conversation scope do not match.")
    has_chatwoot_delivery = bool(
        conversation.chatwoot_conversation_id and conversation.chatwoot_inbox_id
    )
    delivery_unavailable = (
        (account is None and not has_chatwoot_delivery)
        or (account is not None and not account.is_enabled)
    )
    if status == "queued" and (
        delivery_unavailable or getattr(conversation, "is_blocked", False)
    ):
        raise ValueError("Outbound delivery is disabled for this conversation.")

    # 1. Idempotency Check using Client Request ID (e.g. for UI double clicks)
    if client_request_id:
        existing_msg = db.query(SmsMessage).filter(
            SmsMessage.tenant_id == conversation.tenant_id,
            SmsMessage.provider_id == conversation.provider_id,
            SmsMessage.conversation_id == conversation.id,
            SmsMessage.sms_account_id == (account.id if account else None),
            SmsMessage.client_request_id == client_request_id
        ).first()
        if existing_msg:
            logger.info("Duplicate outbound send was deduplicated.")
            return existing_msg

    # 2. Prevent duplicate AI replies for the same turn (AI safety rule)
    if author_type == "ai" and customer_turn_ref:
        existing_ai_reply = db.query(SmsMessage).filter(
            SmsMessage.tenant_id == conversation.tenant_id,
            SmsMessage.conversation_id == conversation.id,
            SmsMessage.author_type == "ai",
            SmsMessage.customer_turn_ref == customer_turn_ref
        ).first()
        if existing_ai_reply:
            logger.warning("Duplicate AI reply was blocked.")
            return existing_ai_reply

    # 3. Safety check on outbound body content to prevent leaks
    if not is_outbound_body_safe(body):
        # Create as a failed message and log a safety event, bypassing SMS outbox send
        message = SmsMessage(
            tenant_id=account.tenant_id if account else conversation.tenant_id,
            provider_id=account.provider_id if account else conversation.provider_id,
            sms_account_id=account.id if account else None,
            conversation_id=conversation.id,
            body=body,
            normalized_body=body.strip().lower(),
            direction="outbound",
            author_type=author_type,
            author_id=author_id,
            status="failed",
            parent_message_id=parent_message_id,
            client_request_id=client_request_id,
            customer_turn_ref=customer_turn_ref,
            occurred_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc)
        )
        db.add(message)
        db.flush()

        event = SmsConversationEvent(
            conversation_id=conversation.id,
            type="outbound_safety_blocked",
            meta={"message_id": message.id}
        )
        db.add(event)
        db.flush()
        logger.warning("Outbound SMS safety policy blocked delivery.")
        return message

    # 4. Create SmsMessage record
    message = SmsMessage(
        tenant_id=account.tenant_id if account else conversation.tenant_id,
        provider_id=account.provider_id if account else conversation.provider_id,
        sms_account_id=account.id if account else None,
        conversation_id=conversation.id,
        body=body,
        normalized_body=body.strip().lower(),
        direction="draft" if status == "draft" else "outbound",
        author_type=author_type,
        author_id=author_id,
        status=status,
        parent_message_id=parent_message_id,
        client_request_id=client_request_id,
        customer_turn_ref=customer_turn_ref,
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc)
    )
    db.add(message)
    db.flush()  # populate message.id

    # 4. If queued, create SmsOutboundJob record
    if status == "queued":
        job = SmsOutboundJob(
            message_id=message.id,
            sms_account_id=account.id if account else None,
            status="PENDING",
            retry_count=0,
            created_at=datetime.now(timezone.utc)
        )
        db.add(job)
        
    # Update conversation's last activity
    conversation.last_activity_at = datetime.now(timezone.utc)
    db.flush()
    
    return message
