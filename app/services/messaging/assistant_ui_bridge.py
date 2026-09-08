"""Durable, fail-to-handoff bridge from Chatwoot projections to Assistant UI."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ...db.database import SessionLocal
from ...models.sms_chatwoot import SmsChatwootBinding
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import AssistantUiBridgeJob, SmsConversationEvent
from ...services.sms.outbound_service import (
    ChatwootOutboundHandoffUnavailable,
    enqueue_outbound_message_transactional,
)
from .assistant_ui_client import request_decision


MAX_BODY_CHARS = 2000
MAX_TRANSCRIPT_MESSAGES = 6
MAX_TRANSCRIPT_BODY_CHARS = 1000


def _handoff(db: Session, job: AssistantUiBridgeJob, reason_code: str) -> None:
    job.status = "HANDOFF"
    job.processed_at = datetime.now(timezone.utc)
    conversation = db.get(SmsConversation, job.conversation_id)
    if conversation is not None:
        conversation.state = "paused"
        db.add(SmsConversationEvent(
            conversation_id=conversation.id,
            type="chatwoot_operator_review",
            meta={"reason_code": reason_code},
        ))
    db.commit()


def _claim_next(db: Session) -> int | None:
    job = (
        db.query(AssistantUiBridgeJob)
        .filter(AssistantUiBridgeJob.status == "PENDING")
        .order_by(AssistantUiBridgeJob.id)
        .first()
    )
    if job is None:
        return None
    claimed = (
        db.query(AssistantUiBridgeJob)
        .filter(AssistantUiBridgeJob.id == job.id, AssistantUiBridgeJob.status == "PENDING")
        .update({"status": "PROCESSING"}, synchronize_session=False)
    )
    if not claimed:
        db.rollback()
        return None
    db.commit()
    return job.id


def _trusted_context(db: Session, job: AssistantUiBridgeJob):
    binding = db.get(SmsChatwootBinding, job.binding_id)
    conversation = db.get(SmsConversation, job.conversation_id)
    source = db.get(SmsMessage, job.source_message_id)
    if any(item is None for item in (binding, conversation, source)):
        return None
    if not (
        binding.tenant_id == job.tenant_id == conversation.tenant_id == source.tenant_id
        and conversation.chatwoot_binding_id == binding.id
        and source.conversation_id == conversation.id
        and source.chatwoot_binding_id == binding.id
        and source.direction == "inbound"
        and source.author_type == "customer"
        and source.chatwoot_content_type == "text"
        and not source.chatwoot_private
        and binding.effective_automation_enabled
        and binding.assistant_ui_policy_scope == job.policy_scope
        and conversation.state == "auto-reply"
    ):
        return None
    return binding, conversation, source


def _payload(db: Session, job: AssistantUiBridgeJob, binding: SmsChatwootBinding, conversation: SmsConversation, source: SmsMessage) -> dict:
    rows = (
        db.query(SmsMessage)
        .filter(SmsMessage.conversation_id == conversation.id, SmsMessage.id <= source.id)
        .order_by(SmsMessage.id.desc())
        .limit(MAX_TRANSCRIPT_MESSAGES)
        .all()
    )
    transcript = [
        {"direction": row.direction, "author_type": row.author_type, "body": row.body[:MAX_TRANSCRIPT_BODY_CHARS]}
        for row in reversed(rows)
        if row.chatwoot_content_type == "text" and not row.chatwoot_private
    ]
    return {
        "request_id": str(job.request_id),
        "policy_scope": job.policy_scope,
        "channel": binding.channel,
        "body": source.body[:MAX_BODY_CHARS],
        "transcript": transcript,
    }


async def process_one_assistant_ui_bridge_job(db: Session, *, job_id: int) -> str:
    job = db.get(AssistantUiBridgeJob, job_id)
    if job is None or job.status != "PROCESSING":
        return "missing"
    context = _trusted_context(db, job)
    if context is None:
        _handoff(db, job, "automation_ineligible")
        return "HANDOFF"
    binding, conversation, source = context
    decision = await request_decision(payload=_payload(db, job, binding, conversation, source))
    if decision is None:
        _handoff(db, job, "assistant_ui_unavailable")
        return "HANDOFF"
    if decision.kind == "handoff":
        _handoff(db, job, "assistant_ui_handoff")
        return "HANDOFF"

    # The decision may have raced with a staff message, note, or disable.
    db.expire_all()
    job = db.get(AssistantUiBridgeJob, job_id)
    context = _trusted_context(db, job) if job is not None else None
    if context is None or decision.reply is None:
        if job is not None:
            _handoff(db, job, "automation_ineligible")
        return "HANDOFF"
    _binding, conversation, source = context
    try:
        enqueue_outbound_message_transactional(
            db,
            account=None,
            conversation=conversation,
            body=decision.reply,
            author_type="ai",
            status="queued",
            parent_message_id=source.id,
            customer_turn_ref=str(source.id),
        )
    except ChatwootOutboundHandoffUnavailable:
        _handoff(db, job, "outbound_handoff_unavailable")
        return "HANDOFF"
    job.status = "COMPLETED"
    job.processed_at = datetime.now(timezone.utc)
    db.add(SmsConversationEvent(
        conversation_id=conversation.id,
        type="assistant_ui_decision_completed",
        meta={"reason_code": "assistant_ui_reply"},
    ))
    db.commit()
    return "COMPLETED"


async def process_pending_assistant_ui_bridge_jobs(db: Session | None = None) -> None:
    owns_session = db is None
    db = db or SessionLocal()
    try:
        for _ in range(10):
            job_id = _claim_next(db)
            if job_id is None:
                break
            await process_one_assistant_ui_bridge_job(db, job_id=job_id)
    finally:
        if owns_session:
            db.close()
