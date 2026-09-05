"""Authenticated Chatwoot event projection without automation side effects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models.provider import Provider
from ...models.sms_chatwoot import (
    ChatwootConnection,
    ChatwootWebhookReceipt,
    SmsChatwootBinding,
)
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from .contracts import (
    ParsedChatwootEvent,
    SUPPORTED_CHANNEL_OBSERVATIONS,
    SUPPORTED_EVENTS,
    normalize_message,
)
from .policy import ProcessingProvenance
from .processor import process_projected_message


@dataclass(frozen=True)
class IngressResult:
    outcome: str


class IngressConfigurationError(RuntimeError):
    """Raised when trusted server-side ownership records are inconsistent."""


def _receipt(
    *,
    connection: ChatwootConnection,
    delivery_id,
    event: ParsedChatwootEvent,
    outcome: str,
    webhook_timestamp: datetime,
) -> ChatwootWebhookReceipt:
    return ChatwootWebhookReceipt(
        connection_id=connection.id,
        delivery_id=delivery_id,
        event_type=event.event_type,
        outcome=outcome,
        chatwoot_inbox_id=event.inbox_id,
        chatwoot_conversation_id=event.conversation_id,
        chatwoot_message_id=event.message_id,
        webhook_timestamp=webhook_timestamp,
        processed_at=datetime.now(timezone.utc),
    )


def _binding_for_event(
    db: Session, connection: ChatwootConnection, event: ParsedChatwootEvent
) -> SmsChatwootBinding | None:
    if event.inbox_id is None:
        return None
    binding = (
        db.query(SmsChatwootBinding)
        .filter(
            SmsChatwootBinding.connection_id == connection.id,
            SmsChatwootBinding.tenant_id == connection.tenant_id,
            SmsChatwootBinding.chatwoot_inbox_id == event.inbox_id,
        )
        .first()
    )
    if binding is None or not binding.effective_ingress_enabled:
        return None
    provider_exists = (
        db.query(Provider.id)
        .filter(
            Provider.id == binding.provider_id,
            Provider.tenant_id == binding.tenant_id,
            Provider.tenant_id == connection.tenant_id,
        )
        .first()
    )
    if provider_exists is None:
        raise IngressConfigurationError("invalid trusted binding ownership")
    return binding


def _conversation_for_event(
    db: Session, binding: SmsChatwootBinding, event: ParsedChatwootEvent
) -> SmsConversation | None:
    return (
        db.query(SmsConversation)
        .filter(
            SmsConversation.chatwoot_binding_id == binding.id,
            SmsConversation.chatwoot_conversation_id == event.conversation_id,
        )
        .first()
    )


def _project_created(
    db: Session, binding: SmsChatwootBinding, event: ParsedChatwootEvent
) -> str:
    existing = (
        db.query(SmsMessage)
        .filter(
            SmsMessage.chatwoot_binding_id == binding.id,
            SmsMessage.chatwoot_message_id == event.message_id,
        )
        .first()
    )
    if existing is not None:
        return "duplicate_message"

    conversation = _conversation_for_event(db, binding, event)
    if conversation is None:
        conversation = SmsConversation(
            tenant_id=binding.tenant_id,
            provider_id=binding.provider_id,
            sms_account_id=None,
            customer_address=(
                f"chatwoot-binding-{binding.id}-conversation-{event.conversation_id}"
            ),
            client_id=None,
            state="paused",
            unread_count=0,
            chatwoot_binding_id=binding.id,
            chatwoot_conversation_id=event.conversation_id,
            chatwoot_contact_id=None,
            chatwoot_inbox_id=binding.chatwoot_inbox_id,
            last_activity_at=event.occurred_at,
        )
        db.add(conversation)
        db.flush()

    normalized = normalize_message(event)
    message = SmsMessage(
        tenant_id=binding.tenant_id,
        provider_id=binding.provider_id,
        sms_account_id=None,
        conversation_id=conversation.id,
        body=normalized.body,
        normalized_body=normalized.normalized_body,
        direction=normalized.direction,
        author_type=normalized.author_type,
        status="received" if normalized.direction == "inbound" else "sent",
        chatwoot_binding_id=binding.id,
        chatwoot_message_id=event.message_id,
        chatwoot_message_type=event.message_type,
        chatwoot_content_type=event.content_type,
        chatwoot_private=event.private,
        chatwoot_sender_type=event.sender_type,
        chatwoot_sender_reference=event.sender_reference,
        chatwoot_attachment_metadata=event.attachments or None,
        occurred_at=event.occurred_at,
        received_at=datetime.now(timezone.utc),
    )
    db.add(message)
    db.flush()
    # Only a successful, newly persisted ``message_created`` projection reaches
    # policy processing. Caller-controlled metadata is never used to select the
    # reserved FastAPI-echo provenance.
    process_projected_message(
        db,
        binding=binding,
        conversation=conversation,
        message=message,
        provenance=ProcessingProvenance.UNVERIFIED,
    )
    return "projected"


def _project_updated(
    db: Session, binding: SmsChatwootBinding, event: ParsedChatwootEvent
) -> str:
    message = (
        db.query(SmsMessage)
        .filter(
            SmsMessage.chatwoot_binding_id == binding.id,
            SmsMessage.chatwoot_message_id == event.message_id,
        )
        .first()
    )
    if message is None:
        return "update_without_projection"
    normalized = normalize_message(event)
    message.body = normalized.body
    message.normalized_body = normalized.normalized_body
    message.direction = normalized.direction
    message.author_type = normalized.author_type
    message.chatwoot_message_type = event.message_type
    message.chatwoot_content_type = event.content_type
    message.chatwoot_private = event.private
    message.chatwoot_sender_type = event.sender_type
    message.chatwoot_sender_reference = event.sender_reference
    message.chatwoot_attachment_metadata = event.attachments or None
    db.flush()
    return "updated"


def _event_outcome(
    db: Session, connection: ChatwootConnection, event: ParsedChatwootEvent
) -> str:
    if event.event_type not in SUPPORTED_EVENTS:
        return "unsupported_event"
    binding = _binding_for_event(db, connection, event)
    if binding is None:
        return "unmapped_inbox"
    if (
        event.channel_observation is not None
        and event.channel_observation not in SUPPORTED_CHANNEL_OBSERVATIONS
    ):
        return "unsupported_channel"
    if event.message_type == "activity":
        return "activity_ignored"
    if event.event_type == "message_updated":
        return _project_updated(db, binding, event)
    return _project_created(db, binding, event)


def process_authenticated_event(
    db: Session,
    *,
    connection: ChatwootConnection,
    delivery_id,
    event: ParsedChatwootEvent,
    webhook_timestamp: datetime,
) -> IngressResult:
    existing_receipt = (
        db.query(ChatwootWebhookReceipt.id)
        .filter(
            ChatwootWebhookReceipt.connection_id == connection.id,
            ChatwootWebhookReceipt.delivery_id == delivery_id,
        )
        .first()
    )
    if existing_receipt is not None:
        return IngressResult("duplicate_delivery")

    def persist_once() -> str:
        with db.begin_nested():
            attempt_outcome = _event_outcome(db, connection, event)
            db.add(
                _receipt(
                    connection=connection,
                    delivery_id=delivery_id,
                    event=event,
                    outcome=attempt_outcome,
                    webhook_timestamp=webhook_timestamp,
                )
            )
            db.flush()
        return attempt_outcome

    try:
        outcome = persist_once()
        db.commit()
        return IngressResult(outcome)
    except IntegrityError:
        # Either another worker inserted this delivery, or another delivery
        # projected the same binding-scoped message. The failed savepoint
        # contains no durable receipt or partial projection.
        if (
            db.query(ChatwootWebhookReceipt.id)
            .filter(
                ChatwootWebhookReceipt.connection_id == connection.id,
                ChatwootWebhookReceipt.delivery_id == delivery_id,
            )
            .first()
            is not None
        ):
            return IngressResult("duplicate_delivery")
        # A distinct delivery can race while both create the same conversation
        # or message. At READ COMMITTED the retry sees the winner and either
        # projects the distinct message or records a duplicate-message receipt.
        outcome = persist_once()
        db.commit()
        return IngressResult(outcome)
