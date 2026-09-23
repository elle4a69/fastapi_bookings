"""Tenant-safe staff operations for the native SMS workspace.

The functions in this module deliberately keep customer message content out of
structural audit events.  Message and note bodies remain in their authoritative
tables, while events record who performed an action and which record changed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ...models.client import Client
from ...models.provider import Provider
from ...models.sms_account import SmsAccount
from ...models.sms_chatwoot import SmsChatwootBinding
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import SmsAiJob, SmsConversationEvent, SmsNote


class SmsOperationConflict(ValueError):
    """Raised when an operation is valid syntactically but unsafe in state."""


TRANSITION_MATRIX: dict[str, dict[str, str]] = {
    "takeover": {
        "auto-reply": "taken-over",
        "paused": "taken-over",
        "taken-over": "taken-over",
    },
    "escalate": {
        "auto-reply": "escalated",
        "paused": "escalated",
        "taken-over": "escalated",
        "needs-review": "escalated",
    },
    "resolve": {
        "auto-reply": "resolved",
        "paused": "resolved",
        "taken-over": "resolved",
        "needs-review": "resolved",
        "escalated": "resolved",
    },
    "clear_review": {"needs-review": "taken-over"},
    "reopen": {"resolved": "taken-over"},
    "release": {"taken-over": "auto-reply"},
}


def null_safe_message_account_scope():
    """Match message/conversation line identity, including Chatwoot-only NULLs."""

    return or_(
        SmsMessage.sms_account_id == SmsConversation.sms_account_id,
        and_(
            SmsMessage.sms_account_id.is_(None),
            SmsConversation.sms_account_id.is_(None),
        ),
    )


def get_scoped_conversation(
    db: Session,
    *,
    tenant_id: int,
    conversation_id: int,
) -> SmsConversation | None:
    """Return a tenant-owned conversation with a consistent line binding.

    Historical system conversations may have no SMS account.  When a line is
    present, its tenant and provider must match the conversation before staff
    actions are allowed.
    """

    conversation = (
        db.query(SmsConversation)
        .filter(
            SmsConversation.id == conversation_id,
            SmsConversation.tenant_id == tenant_id,
        )
        .first()
    )
    if conversation is None:
        return None

    provider_exists = db.query(Provider.id).filter(
        Provider.id == conversation.provider_id,
        Provider.tenant_id == tenant_id,
    ).first()
    if provider_exists is None:
        return None

    if conversation.client_id is not None:
        client_exists = db.query(Client.id).filter(
            Client.id == conversation.client_id,
            Client.tenant_id == tenant_id,
        ).first()
        if client_exists is None:
            return None

    if conversation.sms_account_id is None:
        binding = get_scoped_chatwoot_binding(db, conversation=conversation)
        if binding is None:
            return None
        return conversation

    account = (
        db.query(SmsAccount)
        .filter(
            SmsAccount.id == conversation.sms_account_id,
            SmsAccount.tenant_id == tenant_id,
            SmsAccount.provider_id == conversation.provider_id,
        )
        .first()
    )
    return conversation if account is not None else None


def get_scoped_chatwoot_binding(
    db: Session,
    *,
    conversation: SmsConversation,
    require_enabled: bool = True,
) -> SmsChatwootBinding | None:
    """Resolve the exact Chatwoot inbox bound to a channel-only conversation."""

    if (
        conversation.chatwoot_conversation_id is None
        or conversation.chatwoot_inbox_id is None
    ):
        return None
    query = db.query(SmsChatwootBinding).filter(
        SmsChatwootBinding.tenant_id == conversation.tenant_id,
        SmsChatwootBinding.provider_id == conversation.provider_id,
        SmsChatwootBinding.chatwoot_inbox_id == conversation.chatwoot_inbox_id,
    )
    if require_enabled:
        query = query.filter(SmsChatwootBinding.is_enabled.is_(True))
    binding = query.first()
    if binding is None or not binding.chatwoot_api_token:
        return None
    return binding


def has_enabled_delivery_target(db: Session, conversation: SmsConversation) -> bool:
    if conversation.sms_account_id is not None:
        return get_scoped_account(
            db, conversation=conversation, require_enabled=True
        ) is not None
    return get_scoped_chatwoot_binding(db, conversation=conversation) is not None


def ensure_customer_send_allowed(conversation: SmsConversation) -> None:
    if conversation.is_blocked:
        raise SmsOperationConflict("Unblock this contact before sending.")
    if conversation.state == "resolved":
        raise SmsOperationConflict(
            "Resolved conversations must be reopened before sending."
        )


def get_scoped_account(
    db: Session,
    *,
    conversation: SmsConversation,
    require_enabled: bool = False,
) -> SmsAccount | None:
    if conversation.sms_account_id is None:
        return None
    query = db.query(SmsAccount).filter(
        SmsAccount.id == conversation.sms_account_id,
        SmsAccount.tenant_id == conversation.tenant_id,
        SmsAccount.provider_id == conversation.provider_id,
    )
    if require_enabled:
        query = query.filter(SmsAccount.is_enabled.is_(True))
    return query.first()


def cancel_pending_ai_jobs(db: Session, conversation_id: int) -> int:
    return (
        db.query(SmsAiJob)
        .filter(
            SmsAiJob.conversation_id == conversation_id,
            SmsAiJob.status == "PENDING",
        )
        .update({"status": "CANCELLED"}, synchronize_session=False)
    )


def record_event(
    db: Session,
    *,
    conversation_id: int,
    event_type: str,
    actor_id: int | None,
    metadata: dict[str, Any] | None = None,
) -> SmsConversationEvent:
    structural_meta: dict[str, Any] = {"actor_id": actor_id}
    if metadata:
        structural_meta.update(metadata)
    event = SmsConversationEvent(
        conversation_id=conversation_id,
        type=event_type,
        meta=structural_meta,
    )
    db.add(event)
    return event


def transition_conversation(
    db: Session,
    *,
    conversation: SmsConversation,
    action: str,
    actor_id: int,
    reason: str | None = None,
) -> SmsConversation:
    """Apply a guarded lifecycle transition and append an audit event."""

    previous_state = conversation.state
    metadata: dict[str, Any] = {"from_state": previous_state}
    if reason:
        metadata["reason"] = reason.strip()

    if action not in TRANSITION_MATRIX:
        raise SmsOperationConflict("Unsupported conversation transition.")
    target_state = TRANSITION_MATRIX[action].get(previous_state)
    if target_state is None:
        raise SmsOperationConflict(
            f"Conversation state '{previous_state}' cannot perform '{action}'."
        )

    if conversation.is_blocked and action in {"takeover", "clear_review", "reopen", "release"}:
        raise SmsOperationConflict(
            "Blocked conversations must be unblocked before this transition."
        )

    if action == "escalate":
        if not reason or not reason.strip():
            raise SmsOperationConflict("An escalation reason is required.")
    elif action == "resolve":
        if not reason or not reason.strip():
            raise SmsOperationConflict("A resolution note is required.")
    elif action == "reopen":
        if not reason or not reason.strip():
            raise SmsOperationConflict("A reopen reason is required.")
    elif action == "release":
        account = get_scoped_account(db, conversation=conversation, require_enabled=True)
        if account is None or not account.ai_enabled or account.ai_mode not in {"draft", "autopilot"}:
            raise SmsOperationConflict(
                "The bound SMS line is not enabled for AI handling."
            )

    conversation.state = target_state
    conversation.ai_enabled = action == "release"
    if action != "release":
        cancel_pending_ai_jobs(db, conversation.id)

    metadata["to_state"] = conversation.state
    record_event(
        db,
        conversation_id=conversation.id,
        event_type=f"conversation_{action}",
        actor_id=actor_id,
        metadata=metadata,
    )
    return conversation


def scoped_drafts(
    db: Session,
    *,
    tenant_id: int,
    message_ids: Iterable[int],
) -> list[SmsMessage]:
    ids = list(dict.fromkeys(message_ids))
    if not ids:
        return []
    return (
        db.query(SmsMessage)
        .join(SmsConversation, SmsConversation.id == SmsMessage.conversation_id)
        .filter(
            SmsMessage.id.in_(ids),
            SmsMessage.tenant_id == tenant_id,
            SmsConversation.tenant_id == tenant_id,
            SmsMessage.provider_id == SmsConversation.provider_id,
            null_safe_message_account_scope(),
            SmsMessage.status == "draft",
        )
        .all()
    )


def timeline_items(db: Session, conversation: SmsConversation) -> list[dict[str, Any]]:
    """Build the staff timeline without returning unsafe event payload copies."""

    items: list[dict[str, Any]] = []
    messages = (
        db.query(SmsMessage)
        .filter(
            SmsMessage.conversation_id == conversation.id,
            SmsMessage.tenant_id == conversation.tenant_id,
            SmsMessage.provider_id == conversation.provider_id,
            SmsMessage.sms_account_id == conversation.sms_account_id,
        )
        .all()
    )
    for message in messages:
        items.append(
            {
                "kind": "message",
                "id": message.id,
                "occurred_at": message.occurred_at,
                "body": message.body,
                "direction": message.direction,
                "author_type": message.author_type,
                "status": message.status,
            }
        )

    notes = db.query(SmsNote).filter(SmsNote.conversation_id == conversation.id).all()
    for note in notes:
        items.append(
            {
                "kind": "internal_note",
                "id": note.id,
                "occurred_at": note.created_at,
                "body": note.text,
                "author_id": note.author_id,
            }
        )

    safe_meta_keys = {
        "actor_id",
        "message_id",
        "note_id",
        "from_state",
        "to_state",
        "trigger",
        "reason",
        "corrected_wording",
        "contains_dynamic_facts",
        "discarded_count",
        "ai_mode",
        "requires_review",
        "ai_enabled",
        "is_pinned",
        "is_blocked",
        "state",
    }
    events = (
        db.query(SmsConversationEvent)
        .filter(SmsConversationEvent.conversation_id == conversation.id)
        .all()
    )
    for event in events:
        raw_meta = event.meta if isinstance(event.meta, dict) else {}
        items.append(
            {
                "kind": "event",
                "id": event.id,
                "occurred_at": event.created_at,
                "event_type": event.type,
                "meta": {key: raw_meta[key] for key in safe_meta_keys if key in raw_meta},
            }
        )

    floor = datetime.min.replace(tzinfo=timezone.utc)
    items.sort(key=lambda item: (item.get("occurred_at") or floor, item["kind"], item["id"]))
    return items
