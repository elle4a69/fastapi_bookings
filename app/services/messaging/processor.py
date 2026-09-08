"""Transactional processor for authenticated, normalized message projections."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ...models.sms_chatwoot import SmsChatwootBinding
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage
from ...models.sms_outbox import AssistantUiBridgeJob, SmsAiJob, SmsConversationEvent
from .policy import ProcessingProvenance, decide_projected_message


@dataclass(frozen=True)
class ProcessingResult:
    """Content-free outcome for observability within the transaction."""

    reason_code: str


def process_projected_message(
    db: Session,
    *,
    binding: SmsChatwootBinding,
    conversation: SmsConversation,
    message: SmsMessage,
    provenance: ProcessingProvenance = ProcessingProvenance.UNVERIFIED,
) -> ProcessingResult:
    """Apply one fail-closed policy decision without dispatching any work.

    The caller must invoke this only after a newly-created normalized message
    has been flushed, and must retain ownership of the surrounding transaction.
    This function never commits, invokes AI, creates jobs, sends messages, or
    resolves customer identity.
    """

    decision = decide_projected_message(
        binding=binding,
        conversation=conversation,
        message=message,
        provenance=provenance,
    )

    if decision.cancel_pending_ai:
        (
            db.query(SmsAiJob)
            .filter(
                SmsAiJob.conversation_id == conversation.id,
                SmsAiJob.status == "PENDING",
            )
            .update({"status": "CANCELLED"}, synchronize_session=False)
        )
        (
            db.query(AssistantUiBridgeJob)
            .filter(
                AssistantUiBridgeJob.conversation_id == conversation.id,
                AssistantUiBridgeJob.status == "PENDING",
            )
            .update({"status": "CANCELLED"}, synchronize_session=False)
        )

    if decision.state is not None:
        conversation.state = decision.state

    if decision.reason_code == "automation_queued":
        db.add(
            AssistantUiBridgeJob(
                tenant_id=binding.tenant_id,
                binding_id=binding.id,
                conversation_id=conversation.id,
                source_message_id=message.id,
                policy_scope=binding.assistant_ui_policy_scope or "",
            )
        )

    metadata: dict[str, str] = {"reason_code": decision.reason_code}
    if decision.identity_code is not None:
        metadata["identity_code"] = decision.identity_code
    db.add(
        SmsConversationEvent(
            conversation_id=conversation.id,
            type=decision.event_type,
            meta=metadata,
        )
    )
    db.flush()
    return ProcessingResult(reason_code=decision.reason_code)
