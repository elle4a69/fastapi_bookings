"""Safety policy for durable knowledge ingestion and retrieval.

The policy is intentionally deterministic and fail-closed.  It does not ask an
LLM whether customer or live operational data is safe to remember.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


APPROVED_AUTHORITIES: tuple[str, ...] = (
    "owner_verified",
    "admin_verified",
    "approved_policy",
    "imported_verified",
)

AUTHORITY_RANK: dict[str, int] = {
    "owner_verified": 400,
    "admin_verified": 300,
    "approved_policy": 250,
    "imported_verified": 200,
    "staff_guidance": 100,
    "conversation_candidate": 0,
}

_MONEY_RE = re.compile(
    r"(?:[$€£]\s*\d|\b(?:price|cost|fee|rate|deposit|balance|invoice|payment)\b)",
    re.IGNORECASE,
)
_AVAILABILITY_RE = re.compile(
    r"\b(?:available|availability|open slot|free slot|next appointment|booked out)\b",
    re.IGNORECASE,
)
_BOOKING_STATE_RE = re.compile(
    r"\b(?:booking|appointment|reservation)\b.{0,28}\b(?:pending|confirmed|cancelled|canceled|rescheduled|completed|no[- ]show)\b",
    re.IGNORECASE | re.DOTALL,
)
_RELATIVE_TIME_RE = re.compile(
    r"\b(?:today|tomorrow|yesterday|tonight|this (?:week|month)|next (?:week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|currently|right now)\b",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d{4}-\d{2}-\d{2}|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2})\b",
    re.IGNORECASE,
)
_CLOCK_RE = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b|\b\d{1,2}(?::[0-5]\d)?\s*(?:am|pm)\b", re.IGNORECASE)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_PAYMENT_DETAIL_RE = re.compile(
    r"\b(?:card number|credit card|debit card|bank account|bsb|routing number|payment link|checkout link|invoice link)\b",
    re.IGNORECASE,
)
_CUSTOMER_CONTEXT_RE = re.compile(
    r"(?:\[(?:NAME|PHONE|EMAIL|ADDRESS|CREDIT_CARD)\]|\b(?:my|your)\s+(?:phone|email|address|booking|appointment|payment|card|invoice)\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class KnowledgeSafetyDecision:
    """Structural result safe to persist in audit metadata."""

    durable: bool
    reason_code: str
    dynamic_types: tuple[str, ...] = ()


def classify_knowledge_safety(
    user_query: str,
    proposed_response: str,
    *,
    category: str | None = None,
) -> KnowledgeSafetyDecision:
    """Reject dynamic or customer-specific facts from reusable knowledge.

    This classifier intentionally errs toward review/live lookup.  The caller
    may retain a structural rejection proposal, but must not retain the raw
    dynamic content as durable memory.
    """

    combined = f"{user_query}\n{proposed_response}".strip()
    detected: list[str] = []
    checks = (
        ("price_or_payment", _MONEY_RE),
        ("availability", _AVAILABILITY_RE),
        ("booking_state", _BOOKING_STATE_RE),
        ("relative_time", _RELATIVE_TIME_RE),
        ("date", _DATE_RE),
        ("time", _CLOCK_RE),
        ("link", _URL_RE),
        ("payment_detail", _PAYMENT_DETAIL_RE),
        ("customer_specific", _CUSTOMER_CONTEXT_RE),
    )
    for label, pattern in checks:
        if pattern.search(combined):
            detected.append(label)

    if (category or "").lower() in {"pricing", "availability", "booking_status", "payment"}:
        detected.append("dynamic_category")

    unique_detected = tuple(dict.fromkeys(detected))
    if unique_detected:
        return KnowledgeSafetyDecision(
            durable=False,
            reason_code="dynamic_fact_requires_live_source",
            dynamic_types=unique_detected,
        )
    if not user_query.strip() or not proposed_response.strip():
        return KnowledgeSafetyDecision(False, "empty_knowledge_candidate")
    return KnowledgeSafetyDecision(True, "durable_candidate")


def is_effective(
    *,
    effective_from: datetime | None,
    effective_until: datetime | None,
    at: datetime | None = None,
) -> bool:
    """Return whether a knowledge record is effective at ``at``."""

    now = at or datetime.now(timezone.utc)

    def aware(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    start = aware(effective_from)
    end = aware(effective_until)
    return not ((start is not None and start > now) or (end is not None and end <= now))


def authority_score(authority: str) -> int:
    """Return a bounded ranking; unknown authorities are not trusted."""

    return AUTHORITY_RANK.get(authority, -1)


def choose_authoritative(records: Iterable[object]) -> object | None:
    """Choose one clear record, or fail closed when top authorities conflict."""

    eligible = [
        record
        for record in records
        if getattr(record, "authority", None) in APPROVED_AUTHORITIES
        and getattr(record, "status", None) == "active"
        and getattr(record, "conflict_state", None) == "clear"
        and is_effective(
            effective_from=getattr(record, "effective_from", None),
            effective_until=getattr(record, "effective_until", None),
        )
    ]
    if not eligible:
        return None
    eligible.sort(
        key=lambda item: (
            authority_score(getattr(item, "authority", "")),
            float(getattr(item, "confidence_score", 0.0) or 0.0),
            getattr(item, "last_verified_at", datetime.min.replace(tzinfo=timezone.utc)),
        ),
        reverse=True,
    )
    best = eligible[0]
    best_rank = authority_score(getattr(best, "authority", ""))
    top = [item for item in eligible if authority_score(getattr(item, "authority", "")) == best_rank]
    normalized_answers = {
        " ".join(str(getattr(item, "ideal_response", "")).lower().split()) for item in top
    }
    if len(normalized_answers) > 1:
        return None
    return best
