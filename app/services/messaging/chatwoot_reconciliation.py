"""Fail-closed local reconciliation for Package D outbound intents."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ...models.sms_chatwoot import (
    ChatwootConnection,
    ChatwootOutboundIntent,
    SmsChatwootBinding,
)
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from .contracts import ParsedChatwootEvent, ParsedChatwootOutboundMessage
from .policy import ProcessingProvenance
from .processor import process_projected_message


def outbound_message_is_trusted(
    *,
    connection: ChatwootConnection,
    binding: SmsChatwootBinding,
    intent: ChatwootOutboundIntent,
    message: ParsedChatwootOutboundMessage,
) -> bool:
    """Compare all ownership and sender fields, never a marker alone."""
    return bool(
        message.account_id == connection.chatwoot_account_id
        and message.inbox_id == binding.chatwoot_inbox_id
        and message.conversation_id
        == intent.conversation.chatwoot_conversation_id
        and message.message_type == "outgoing"
        and message.content_type == "text"
        and message.private is False
        # The verified 4.15.1 outbound handoff is authored by the configured
        # API user. An AgentBot event is never an echo, even if a marker is
        # copied and configuration is corrupted outside this admin boundary.
        and message.sender_type == "User"
        and connection.expected_integration_sender_type == "User"
        and message.sender_type == connection.expected_integration_sender_type
        and message.sender_id == connection.expected_integration_sender_id
        and message.outbound_correlation_id == intent.outbound_correlation_id
    )


def _set_quarantined(intent: ChatwootOutboundIntent, message: SmsMessage) -> None:
    intent.status = "QUARANTINED"
    intent.reconciled_at = datetime.now(timezone.utc)
    message.status = "failed"


def _local_tuple_is_consistent(
    *,
    intent: ChatwootOutboundIntent,
    binding: SmsChatwootBinding,
    conversation: SmsConversation,
    message: SmsMessage,
) -> bool:
    """Require the persisted local tuple before an echo changes state."""
    return bool(
        intent.tenant_id == binding.tenant_id == conversation.tenant_id == message.tenant_id
        and intent.provider_id == binding.provider_id == conversation.provider_id == message.provider_id
        and intent.binding_id == binding.id == conversation.chatwoot_binding_id == message.chatwoot_binding_id
        and intent.conversation_id == conversation.id == message.conversation_id
        and conversation.chatwoot_inbox_id == binding.chatwoot_inbox_id
    )


def reconcile_remote_message(
    db: Session,
    *,
    intent: ChatwootOutboundIntent,
    remote_message_id: int,
    sender_type: str,
    sender_reference: str,
    invoke_verified_processor: bool,
) -> str:
    """Persist one remote identifier, handling API/webhook races once.

    A different remote message identifier is not resolved optimistically: it is
    quarantined for an operator because resending could duplicate delivery.
    """
    current = (
        db.query(ChatwootOutboundIntent)
        .populate_existing()
        .with_for_update()
        .filter(ChatwootOutboundIntent.id == intent.id)
        .one_or_none()
    )
    if current is None:
        return "missing_intent"
    message = db.get(SmsMessage, current.message_id)
    conversation = db.get(SmsConversation, current.conversation_id)
    binding = db.get(SmsChatwootBinding, current.binding_id)
    if message is None or conversation is None or binding is None:
        if message is not None:
            _set_quarantined(current, message)
        else:
            current.status = "QUARANTINED"
            current.reconciled_at = datetime.now(timezone.utc)
        db.flush()
        return "quarantined"
    if not _local_tuple_is_consistent(
        intent=current,
        binding=binding,
        conversation=conversation,
        message=message,
    ):
        _set_quarantined(current, message)
        db.flush()
        return "quarantined"

    existing_remote_id = current.remote_chatwoot_message_id
    if existing_remote_id is not None and existing_remote_id != remote_message_id:
        _set_quarantined(current, message)
        db.flush()
        return "quarantined"
    if current.status == "SUCCEEDED" and existing_remote_id == remote_message_id:
        # A duplicated delivery or API/echo race is idempotent: do not emit a
        # second reconciliation event or mutate the already-owned message.
        return "reconciled"
    if current.status in {"FAILED", "QUARANTINED"}:
        _set_quarantined(current, message)
        db.flush()
        return "quarantined"

    current.remote_chatwoot_message_id = remote_message_id
    current.status = "SUCCEEDED"
    current.reconciled_at = datetime.now(timezone.utc)
    message.status = "sent"
    message.chatwoot_binding_id = binding.id
    message.chatwoot_message_id = remote_message_id
    message.chatwoot_message_type = "outgoing"
    message.chatwoot_content_type = "text"
    message.chatwoot_private = False
    message.chatwoot_sender_type = sender_type
    message.chatwoot_sender_reference = sender_reference
    db.flush()

    if invoke_verified_processor:
        process_projected_message(
            db,
            binding=binding,
            conversation=conversation,
            message=message,
            provenance=ProcessingProvenance.VERIFIED_FASTAPI_ECHO,
        )
    return "reconciled"


def reconcile_verified_echo(
    db: Session,
    *,
    connection: ChatwootConnection,
    binding: SmsChatwootBinding,
    event: ParsedChatwootEvent,
) -> str | None:
    """Recognize an echo only after every local and remote check matches."""
    if not (
        event.event_type == "message_created"
        and event.account_id == connection.chatwoot_account_id
        and event.inbox_id == binding.chatwoot_inbox_id
        and event.message_id is not None
        and event.conversation_id is not None
        and event.message_type == "outgoing"
        and event.content_type == "text"
        and event.private is False
        and event.outbound_correlation_id is not None
        and connection.has_expected_integration_sender
        and connection.expected_integration_sender_type == "User"
        and binding.connection_id == connection.id
        and binding.tenant_id == connection.tenant_id
        and event.sender_type == connection.expected_integration_sender_type
        and event.sender_reference == str(connection.expected_integration_sender_id)
    ):
        return None
    conversation = (
        db.query(SmsConversation)
        .filter(
            SmsConversation.id.is_not(None),
            SmsConversation.tenant_id == binding.tenant_id,
            SmsConversation.provider_id == binding.provider_id,
            SmsConversation.chatwoot_binding_id == binding.id,
            SmsConversation.chatwoot_conversation_id == event.conversation_id,
        )
        .first()
    )
    if conversation is None:
        return None
    intents = (
        db.query(ChatwootOutboundIntent)
        .filter(
            ChatwootOutboundIntent.outbound_correlation_id
            == event.outbound_correlation_id,
            ChatwootOutboundIntent.tenant_id == connection.tenant_id,
            ChatwootOutboundIntent.connection_id == connection.id,
            ChatwootOutboundIntent.binding_id == binding.id,
            ChatwootOutboundIntent.conversation_id == conversation.id,
        )
        .all()
    )
    if len(intents) != 1:
        return None
    return reconcile_remote_message(
        db,
        intent=intents[0],
        remote_message_id=event.message_id,
        sender_type=event.sender_type,
        sender_reference=event.sender_reference,
        invoke_verified_processor=True,
    )
