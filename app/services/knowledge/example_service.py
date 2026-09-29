"""Bounded Procedural Example Retrieval Service.

Retrieves approved MessageStyleExample records for prompt conditioning,
prioritizing provider overrides -> tenant defaults -> platform seed examples.
Enforces deduplication and bounded context footprint.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Set

from sqlalchemy.orm import Session

from app.models.message_style_example import MessageStyleExample

logger = logging.getLogger(__name__)

DEFAULT_EXAMPLE_LIMIT = 3
DEFAULT_MAX_CHAR_BUDGET = 2400  # ~600 tokens


# This deliberately small vocabulary is used only to select already-approved
# procedural examples.  It is not a classifier and it must never turn live
# values (dates, prices, addresses, customer data) into reusable knowledge.
_INTENT_PATTERNS = (
    ("pregnancy_inquiry", r"\b(?:pregnan|prenatal)\b"),
    ("cancellation", r"\b(?:cancel|reschedul|refund)\b"),
    ("availability", r"\b(?:available|availability|opening|slot|free)\b"),
    ("pricing", r"\b(?:price|pricing|cost|how much|rate|fee)\b"),
    ("travel", r"\b(?:travel|mobile|home visit|come to)\b"),
    ("address", r"\b(?:address|location|where are you)\b"),
    ("hours", r"\b(?:hours|open|close|opening hours)\b"),
    ("provider", r"\b(?:provider|practitioner|therapist|doctor|dr\.)\b"),
    ("service", r"\b(?:service|massage|treatment|appointment)\b"),
    ("greeting", r"^\s*(?:hi|hello|hey|good\s+(?:morning|afternoon|evening))\b"),
)


def detect_style_intent(message: Optional[str]) -> Optional[str]:
    """Return a conservative procedural intent for style-example retrieval.

    Returning ``None`` is intentional when no recognised conversational intent
    is present: callers must not inject merely recent, unrelated examples into
    a production prompt.
    """
    text = (message or "").strip().lower()
    if not text:
        return None
    for intent, pattern in _INTENT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return intent
    return None


def retrieve_style_examples(
    db: Session,
    tenant_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    detected_intent: Optional[str] = None,
    limit: int = DEFAULT_EXAMPLE_LIMIT,
    max_char_budget: int = DEFAULT_MAX_CHAR_BUDGET,
) -> List[MessageStyleExample]:
    """Retrieve at most `limit` approved, active style examples matching the intent.

    Priority Scoping:
    1. Provider-scoped overrides (matching tenant_id and provider_id).
    2. Tenant-wide defaults (matching tenant_id with provider_id is NULL).
    3. Platform-wide seed examples (tenant_id is NULL and provider_id is NULL).

    Args:
        db: Active SQLAlchemy session.
        tenant_id: Tenant context ID (if any).
        provider_id: Provider context ID (if any).
        detected_intent: Target conversation intent (e.g. 'greeting', 'pricing'), or None for general examples.
        limit: Maximum number of examples to return (default: 3).
        max_char_budget: Maximum character budget for the returned examples.

    Returns:
        Deduplicated list of MessageStyleExample instances, up to `limit`.
    """
    if limit <= 0:
        return []

    results: List[MessageStyleExample] = []
    seen_hashes: Set[str] = set()
    current_char_count = 0

    def try_add_examples(query_filter) -> None:
        nonlocal current_char_count
        if len(results) >= limit:
            return

        filters = [
            MessageStyleExample.is_approved.is_(True),
            MessageStyleExample.is_active.is_(True),
            *query_filter,
        ]
        if detected_intent:
            filters.append(MessageStyleExample.intent == detected_intent)

        candidates = (
            db.query(MessageStyleExample)
            .filter(*filters)
            .order_by(MessageStyleExample.id.desc())
            .all()
        )

        for candidate in candidates:
            if len(results) >= limit:
                break
            h = candidate.content_hash or f"{candidate.intent}::{candidate.client_message}"
            if h in seen_hashes:
                continue

            ex_chars = len(candidate.client_message or "") + len(candidate.assistant_reply or "")
            if results and (current_char_count + ex_chars > max_char_budget):
                # Stop if exceeding budget (always permit at least 1 example if results is empty)
                break

            seen_hashes.add(h)
            results.append(candidate)
            current_char_count += ex_chars

    # 1. Provider Scoped: specific to (tenant_id, provider_id)
    if tenant_id is not None and provider_id is not None:
        try_add_examples([
            MessageStyleExample.tenant_id == tenant_id,
            MessageStyleExample.provider_id == provider_id,
        ])

    # 2. Tenant Scoped: tenant-wide defaults
    if len(results) < limit and tenant_id is not None:
        try_add_examples([
            MessageStyleExample.tenant_id == tenant_id,
            MessageStyleExample.provider_id.is_(None),
        ])

    # 3. Platform Wide: global seed examples
    if len(results) < limit:
        try_add_examples([
            MessageStyleExample.tenant_id.is_(None),
            MessageStyleExample.provider_id.is_(None),
        ])

    return results


def format_style_examples_for_prompt(examples: List[MessageStyleExample]) -> str:
    """Format procedural style examples into a compact text block for system prompts."""
    if not examples:
        return ""

    blocks: List[str] = [
        "### Conversational Tone & Style Exemplars (Follow this phrasing & tone):"
    ]
    for idx, ex in enumerate(examples, start=1):
        client_text = (
            getattr(ex, "client_message", None)
            or getattr(ex, "user_query", "")
            or ""
        ).strip()
        reply_text = (
            getattr(ex, "assistant_reply", None)
            or getattr(ex, "ideal_response", "")
            or ""
        ).strip()
        intent = getattr(ex, "intent", "")
        intent_label = f" ({intent})" if intent else ""
        blocks.append(
            f"Example {idx}{intent_label}:\n"
            f"Client: {client_text}\n"
            f"Assistant: {reply_text}"
        )

    return "\n\n".join(blocks)
