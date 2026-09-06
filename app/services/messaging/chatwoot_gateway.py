"""The bounded, one-POST FastAPI-to-Chatwoot Package D handoff boundary."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models.sms_chatwoot import (
    ChatwootConnection,
    ChatwootOutboundIntent,
    SmsChatwootBinding,
)
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from .chatwoot_reconciliation import (
    outbound_message_is_trusted,
    reconcile_remote_message,
)
from .chatwoot_security import ApiTokenUnavailable, decrypt_api_token
from .contracts import (
    InvalidChatwootPayload,
    extract_chatwoot_outbound_messages,
    parse_chatwoot_outbound_message,
)


REQUEST_TIMEOUT_SECONDS = 5.0
MAX_RECONCILIATION_MESSAGES = 100


def claim_outbound_intent_for_dispatch(db: Session, *, intent_id: int) -> bool:
    """Atomically own an intent and save its causal pre-send cursor.

    The conditional transition prevents a second worker from posting the same
    intent. The cursor deliberately excludes locally later messages: those
    records did not exist when this intent was created and are not evidence
    for reconciling this owned handoff.
    """
    claimed = (
        db.query(ChatwootOutboundIntent)
        .filter(
            ChatwootOutboundIntent.id == intent_id,
            ChatwootOutboundIntent.status == "PENDING",
        )
        .update({"status": "SENDING"}, synchronize_session=False)
    )
    if not claimed:
        db.rollback()
        return False
    db.expire_all()
    intent = db.get(ChatwootOutboundIntent, intent_id)
    if intent is None:
        db.rollback()
        return False
    # Only earlier local projections are causal context for this intent. A
    # later local record with a remote-looking ID must not widen GET search.
    intent.pre_send_cursor = (
        db.query(func.max(SmsMessage.chatwoot_message_id))
        .filter(
            SmsMessage.conversation_id == intent.conversation_id,
            SmsMessage.chatwoot_binding_id == intent.binding_id,
            SmsMessage.id < intent.message_id,
            SmsMessage.chatwoot_message_id.is_not(None),
        )
        .scalar()
    )
    intent.sent_at = datetime.now(timezone.utc)
    db.commit()
    return True


def _intent_context(
    db: Session, intent_id: int
) -> tuple[
    ChatwootOutboundIntent,
    ChatwootConnection,
    SmsChatwootBinding,
    SmsConversation,
    SmsMessage,
] | None:
    intent = db.get(ChatwootOutboundIntent, intent_id)
    if intent is None:
        return None
    connection = db.get(ChatwootConnection, intent.connection_id)
    binding = db.get(SmsChatwootBinding, intent.binding_id)
    conversation = db.get(SmsConversation, intent.conversation_id)
    message = db.get(SmsMessage, intent.message_id)
    if any(item is None for item in (connection, binding, conversation, message)):
        return None
    return intent, connection, binding, conversation, message


def _local_intent_is_trusted(
    *,
    intent: ChatwootOutboundIntent,
    connection: ChatwootConnection,
    binding: SmsChatwootBinding,
    conversation: SmsConversation,
    message: SmsMessage,
) -> bool:
    return bool(
        connection.tenant_id == intent.tenant_id == binding.tenant_id == conversation.tenant_id == message.tenant_id
        and binding.provider_id == intent.provider_id == conversation.provider_id == message.provider_id
        and binding.connection_id == connection.id == intent.connection_id
        and connection.expected_integration_sender_type == "User"
        and conversation.chatwoot_binding_id == binding.id
        and conversation.chatwoot_inbox_id == binding.chatwoot_inbox_id
        and conversation.chatwoot_conversation_id is not None
        and message.conversation_id == conversation.id
        and message.chatwoot_binding_id == binding.id == intent.binding_id
        and binding.effective_outbound_enabled
    )


def _mark_failed(db: Session, intent: ChatwootOutboundIntent) -> None:
    intent.status = "FAILED"
    intent.reconciled_at = datetime.now(timezone.utc)
    message = db.get(SmsMessage, intent.message_id)
    if message is not None:
        message.status = "failed"
    db.commit()


def _mark_unknown(db: Session, intent: ChatwootOutboundIntent) -> None:
    db.refresh(intent)
    if intent.status == "SUCCEEDED":
        return
    if intent.status == "QUARANTINED":
        return
    intent.status = "OUTCOME_UNKNOWN"
    intent.reconciled_at = datetime.now(timezone.utc)
    message = db.get(SmsMessage, intent.message_id)
    if message is not None:
        message.status = "outcome_unknown"
    db.commit()


def _mark_quarantined(db: Session, intent: ChatwootOutboundIntent) -> None:
    intent.status = "QUARANTINED"
    intent.reconciled_at = datetime.now(timezone.utc)
    message = db.get(SmsMessage, intent.message_id)
    if message is not None:
        message.status = "failed"
    db.commit()


def _messages_url(connection: ChatwootConnection, conversation: SmsConversation) -> str:
    return (
        f"{connection.instance_origin}/api/v1/accounts/"
        f"{connection.chatwoot_account_id}/conversations/"
        f"{conversation.chatwoot_conversation_id}/messages"
    )


async def reconcile_unknown_outbound_intent(
    db: Session, *, intent_id: int
) -> str:
    """Run at most one bounded GET after an uncertain POST outcome.

    Absence is deliberately not retry authority. Response payloads and errors
    stay in-process and are never logged or persisted.
    """
    context = _intent_context(db, intent_id)
    if context is None:
        return "missing"
    intent, connection, binding, conversation, _message = context
    if intent.status != "OUTCOME_UNKNOWN" or intent.reconciliation_attempted:
        return intent.status
    if not _local_intent_is_trusted(
        intent=intent,
        connection=connection,
        binding=binding,
        conversation=conversation,
        message=_message,
    ):
        _mark_quarantined(db, intent)
        return "QUARANTINED"
    try:
        token = decrypt_api_token(connection._api_token_ciphertext)
    except ApiTokenUnavailable:
        return "OUTCOME_UNKNOWN"

    # Persist the one-shot marker before any network activity. A crash after
    # this point is conservative: it can require manual reconciliation but
    # cannot trigger a duplicate GET or POST.
    intent.reconciliation_attempted = True
    db.commit()
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            trust_env=False,
        ) as client:
            response = await client.get(
                _messages_url(connection, conversation),
                headers={"api_access_token": token},
                params={"after": str(intent.pre_send_cursor or 0)},
            )
    except httpx.RequestError:
        return "OUTCOME_UNKNOWN"
    if response.status_code < 200 or response.status_code >= 300:
        return "OUTCOME_UNKNOWN"
    try:
        candidates = extract_chatwoot_outbound_messages(response.json())[
            :MAX_RECONCILIATION_MESSAGES
        ]
        matches = []
        for candidate in candidates:
            parsed = parse_chatwoot_outbound_message(candidate)
            if (
                intent.pre_send_cursor is not None
                and parsed.message_id <= intent.pre_send_cursor
            ):
                continue
            if outbound_message_is_trusted(
                connection=connection,
                binding=binding,
                intent=intent,
                message=parsed,
            ):
                matches.append(parsed)
    except (ValueError, TypeError, InvalidChatwootPayload):
        return "OUTCOME_UNKNOWN"
    if len(matches) == 0:
        return "OUTCOME_UNKNOWN"
    if len(matches) != 1:
        _mark_quarantined(db, intent)
        return "QUARANTINED"
    match = matches[0]
    result = reconcile_remote_message(
        db,
        intent=intent,
        remote_message_id=match.message_id,
        sender_type=match.sender_type,
        sender_reference=str(match.sender_id),
        invoke_verified_processor=False,
    )
    db.commit()
    return result


async def dispatch_outbound_intent(db: Session, *, intent_id: int) -> str:
    """Submit exactly one Chatwoot POST for an already-claimed intent."""
    context = _intent_context(db, intent_id)
    if context is None:
        return "missing"
    intent, connection, binding, conversation, message = context
    if intent.status != "SENDING":
        return intent.status
    if not _local_intent_is_trusted(
        intent=intent,
        connection=connection,
        binding=binding,
        conversation=conversation,
        message=message,
    ):
        _mark_failed(db, intent)
        return "FAILED"
    try:
        token = decrypt_api_token(connection._api_token_ciphertext)
    except ApiTokenUnavailable:
        _mark_failed(db, intent)
        return "FAILED"

    payload = {
        "content": message.body,
        "message_type": "outgoing",
        "private": False,
        "content_attributes": {
            "fastapi_bookings": {
                "outbound_correlation_id": str(intent.outbound_correlation_id)
            }
        },
    }
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            trust_env=False,
        ) as client:
            response = await client.post(
                _messages_url(connection, conversation),
                headers={"api_access_token": token},
                json=payload,
            )
    except httpx.RequestError:
        _mark_unknown(db, intent)
        return await reconcile_unknown_outbound_intent(db, intent_id=intent.id)

    if 400 <= response.status_code < 500:
        _mark_failed(db, intent)
        return "FAILED"
    if response.status_code < 200 or response.status_code >= 300:
        _mark_unknown(db, intent)
        return await reconcile_unknown_outbound_intent(db, intent_id=intent.id)
    try:
        parsed = parse_chatwoot_outbound_message(response.json())
        if not outbound_message_is_trusted(
            connection=connection,
            binding=binding,
            intent=intent,
            message=parsed,
        ):
            raise InvalidChatwootPayload("outbound response is not trusted")
    except (ValueError, TypeError, InvalidChatwootPayload):
        _mark_unknown(db, intent)
        return await reconcile_unknown_outbound_intent(db, intent_id=intent.id)

    result = reconcile_remote_message(
        db,
        intent=intent,
        remote_message_id=parsed.message_id,
        sender_type=parsed.sender_type,
        sender_reference=str(parsed.sender_id),
        invoke_verified_processor=False,
    )
    db.commit()
    return result
