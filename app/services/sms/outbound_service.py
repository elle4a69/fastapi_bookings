import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from ...models.sms_account import SmsAccount
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import SmsOutboundJob

logger = logging.getLogger(__name__)

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
    # 1. Idempotency Check using Client Request ID (e.g. for UI double clicks)
    if client_request_id:
        existing_msg = db.query(SmsMessage).filter(
            SmsMessage.sms_account_id == (account.id if account else None),
            SmsMessage.client_request_id == client_request_id
        ).first()
        if existing_msg:
            logger.info(f"Duplicate outbound send detected and deduplicated via client_request_id={client_request_id}")
            return existing_msg

    # 2. Prevent duplicate AI replies for the same turn (AI safety rule)
    if author_type == "ai" and customer_turn_ref:
        existing_ai_reply = db.query(SmsMessage).filter(
            SmsMessage.conversation_id == conversation.id,
            SmsMessage.author_type == "ai",
            SmsMessage.customer_turn_ref == customer_turn_ref
        ).first()
        if existing_ai_reply:
            logger.warning(f"AI duplicate reply blocked for turn={customer_turn_ref}")
            return existing_ai_reply

    # 3. Safety check on outbound body content to prevent leaks
    is_safe = True
    blocklist = [
        "[[handoff", "system_prompt", "safety rules", "internal notes",
        "as an ai assistant", "internal policy", "under platform rules",
        "hidden notes", "prompt profile", "platform rules"
    ]
    body_lower = body.lower()
    for term in blocklist:
        if term in body_lower:
            is_safe = False
            break

    if not is_safe:
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

        from ...models.sms_outbox import SmsConversationEvent
        event = SmsConversationEvent(
            conversation_id=conversation.id,
            type="outbound_safety_blocked",
            meta={"blocked_body": body, "message_id": message.id}
        )
        db.add(event)
        db.flush()
        logger.warning(f"Outbound SMS safety blocklist triggered for conversation={conversation.id}")
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
