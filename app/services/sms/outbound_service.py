import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from ...models.sms_account import SmsAccount
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import SmsOutboundJob
from ...models.sms_chatwoot import ChatwootConnection, ChatwootOutboundIntent, SmsChatwootBinding

logger = logging.getLogger(__name__)


class ChatwootOutboundHandoffUnavailable(RuntimeError):
    """Fixed, non-sensitive failure for a non-dispatchable Chatwoot target."""


def _trusted_chatwoot_target(
    db: Session, conversation: SmsConversation
) -> tuple[SmsChatwootBinding, ChatwootConnection] | None:
    """Resolve only the connection-bound Package D target; never legacy data."""
    has_binding = conversation.chatwoot_binding_id is not None
    has_conversation = conversation.chatwoot_conversation_id is not None
    if not has_binding and not has_conversation:
        return None
    if not has_binding or not has_conversation:
        raise ChatwootOutboundHandoffUnavailable("Chatwoot outbound handoff is unavailable.")
    binding = (
        db.query(SmsChatwootBinding)
        .filter(
            SmsChatwootBinding.id == conversation.chatwoot_binding_id,
            SmsChatwootBinding.tenant_id == conversation.tenant_id,
            SmsChatwootBinding.provider_id == conversation.provider_id,
            SmsChatwootBinding.connection_id.is_not(None),
        )
        .first()
    )
    if binding is None:
        raise ChatwootOutboundHandoffUnavailable("Chatwoot outbound handoff is unavailable.")
    connection = (
        db.query(ChatwootConnection)
        .filter(
            ChatwootConnection.id == binding.connection_id,
            ChatwootConnection.tenant_id == conversation.tenant_id,
        )
        .first()
    )
    if connection is None or not binding.effective_outbound_enabled:
        raise ChatwootOutboundHandoffUnavailable("Chatwoot outbound handoff is unavailable.")
    return binding, connection

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

    # Chatwoot conversations are an explicit Package D handoff only. They do
    # not receive an SmsOutboundJob and can never fall through to a provider.
    chatwoot_target = _trusted_chatwoot_target(db, conversation)

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

    if chatwoot_target is not None and status == "queued":
        binding, connection = chatwoot_target
        message.chatwoot_binding_id = binding.id
        db.add(
            ChatwootOutboundIntent(
                tenant_id=conversation.tenant_id,
                provider_id=conversation.provider_id,
                connection_id=connection.id,
                binding_id=binding.id,
                conversation_id=conversation.id,
                message_id=message.id,
                status="PENDING",
            )
        )
    # 4. Non-Chatwoot queued messages retain their existing generic job flow.
    elif status == "queued":
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
