"""Fail-closed policy for durable, normalized messaging projections.

This module deliberately operates on already-persisted message metadata. It
does not parse webhook payloads, identify customers, or inspect message bodies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ...models.sms_chatwoot import SmsChatwootBinding
from ...models.sms_conversation import SmsConversation
from ...models.sms_message import SmsMessage


class ProcessingProvenance(str, Enum):
    """Origin assurance supplied by the caller of the durable processor.

    ``VERIFIED_FASTAPI_ECHO`` is reserved for Package D's future correlation
    validator. Webhook ingress always supplies ``UNVERIFIED``: a copied marker
    or an unvalidated payload field must never select the echo path.
    """

    UNVERIFIED = "unverified"
    VERIFIED_FASTAPI_ECHO = "verified_fastapi_echo"


@dataclass(frozen=True)
class PolicyDecision:
    """Structural, content-free result of processing one projected message."""

    event_type: str
    reason_code: str
    state: str | None
    cancel_pending_ai: bool
    identity_code: str | None = None


def decide_projected_message(
    *,
    binding: SmsChatwootBinding,
    conversation: SmsConversation,
    message: SmsMessage,
    provenance: ProcessingProvenance,
) -> PolicyDecision:
    """Return the one permitted action for a normalized projected message.

    ``conversation.client_id`` is intentionally not considered trusted
    cross-channel evidence. Package C cannot establish that relationship and
    must not turn a bare client reference into booking or AI authority.
    """

    # A future Package D validator may use this path only after it validates
    # account, binding, conversation, sender, and local intent correlation.
    # It must precede normal staff classification so echoes cannot take over.
    if provenance is ProcessingProvenance.VERIFIED_FASTAPI_ECHO:
        return PolicyDecision(
            event_type="chatwoot_projection_reconciled",
            reason_code="verified_fastapi_echo",
            state=None,
            cancel_pending_ai=False,
        )

    if message.author_type == "external_bot":
        return PolicyDecision(
            event_type="chatwoot_operator_review",
            reason_code="external_bot_conflict",
            state="paused",
            cancel_pending_ai=True,
        )

    if message.author_type == "staff" and bool(message.chatwoot_private):
        return PolicyDecision(
            event_type="chatwoot_operator_review",
            reason_code="human_private_note",
            state="paused",
            cancel_pending_ai=True,
        )

    if (
        message.author_type == "staff"
        and message.direction == "outbound"
        and not bool(message.chatwoot_private)
    ):
        return PolicyDecision(
            event_type="chatwoot_takeover",
            reason_code="human_staff_reply",
            state="taken-over",
            cancel_pending_ai=True,
        )

    if message.chatwoot_message_type not in {"incoming", "outgoing"}:
        return PolicyDecision(
            event_type="chatwoot_operator_review",
            reason_code="unsupported_message_type",
            state="paused",
            cancel_pending_ai=False,
        )

    if message.chatwoot_content_type != "text":
        return PolicyDecision(
            event_type="chatwoot_operator_review",
            reason_code="unsupported_content",
            state="paused",
            cancel_pending_ai=False,
        )

    if message.author_type not in {"customer", "staff", "external_bot"}:
        return PolicyDecision(
            event_type="chatwoot_operator_review",
            reason_code="unsupported_sender",
            state="paused",
            cancel_pending_ai=False,
        )

    if bool(message.chatwoot_private):
        return PolicyDecision(
            event_type="chatwoot_operator_review",
            reason_code="private_message_unsupported",
            state="paused",
            cancel_pending_ai=False,
        )

    if message.author_type == "customer" and message.direction == "inbound":
        # Package C has no safe outbound handoff, draft mechanism, or trusted
        # cross-channel identity contract. Both activation states therefore
        # pause for human review and create neither AI nor outbound work.
        return PolicyDecision(
            event_type="chatwoot_operator_review",
            reason_code=(
                "automation_disabled"
                if not binding.automation_enabled
                else "outbound_handoff_unavailable"
            ),
            state="paused",
            cancel_pending_ai=False,
            identity_code="untrusted_client_identity",
        )

    return PolicyDecision(
        event_type="chatwoot_operator_review",
        reason_code="unsupported_direction",
        state="paused",
        cancel_pending_ai=False,
    )
