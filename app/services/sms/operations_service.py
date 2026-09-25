"""Tenant-safe staff operations for the native SMS workspace.

The functions in this module deliberately keep customer message content out of
structural audit events.  Message and note bodies remain in their authoritative
tables, while events record who performed an action and which record changed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from ...models.sms_account import SmsAccount
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import SmsAiJob, SmsConversationEvent, SmsNote


class SmsOperationConflict(ValueError):
    """Raised when an operation is valid syntactically but unsafe in state."""


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
    if conversation is None or conversation.sms_account_id is None:
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

    if action == "takeover":
        conversation.state = "taken-over"
        conversation.ai_enabled = False
        cancel_pending_ai_jobs(db, conversation.id)
    elif action == "escalate":
        if not reason or not reason.strip():
            raise SmsOperationConflict("An escalation reason is required.")
        conversation.state = "escalated"
        conversation.ai_enabled = False
        cancel_pending_ai_jobs(db, conversation.id)
    elif action == "resolve":
        if not reason or not reason.strip():
            raise SmsOperationConflict("A resolution note is required.")
        conversation.state = "resolved"
        conversation.ai_enabled = False
        cancel_pending_ai_jobs(db, conversation.id)
    elif action == "release":
        if conversation.is_blocked:
            raise SmsOperationConflict("Blocked conversations cannot be released to automation.")
        if conversation.state not in {"taken-over", "paused"}:
            raise SmsOperationConflict(
                "Only paused or taken-over conversations can be released to automation."
            )
        account = get_scoped_account(db, conversation=conversation, require_enabled=True)
        if account is None or not account.ai_enabled or account.ai_mode not in {"draft", "autopilot"}:
            raise SmsOperationConflict("The bound SMS line is not enabled for AI handling.")
        conversation.state = "auto-reply"
        conversation.ai_enabled = True
    elif action == "clear_review":
        if conversation.state == "needs-review":
            conversation.state = "paused"
    else:
        raise SmsOperationConflict("Unsupported conversation transition.")

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
