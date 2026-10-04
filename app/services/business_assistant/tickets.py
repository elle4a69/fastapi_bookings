"""Safety rules for persisted support-ticket summaries."""

from __future__ import annotations

import hashlib
import re
from typing import Optional


class TicketContentSafetyError(ValueError):
    """Raised when ticket text contains information that must not be persisted."""


ACTIVE_TICKET_STATUSES: tuple[str, ...] = (
    "awaiting_engineering",
    "triaged",
    "in_progress",
    "pending_approval",
    "pending_owner_approval",
)

CLOSED_TICKET_STATUSES: tuple[str, ...] = (
    "resolved",
    "rejected",
    "closed",
    "cancelled",
)

ELEVATED_APPROVAL_CATEGORIES: tuple[str, ...] = (
    "access",
    "security",
)

_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|secret|password|token|authorization|auth_token|passwd|pwd)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+\-/]+=*", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\b(?:postgres(?:ql)?|mysql|redis|mongodb|amqp|cockroachdb):\/\/[^\s]+", re.IGNORECASE),
    re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{12,}\b", re.IGNORECASE),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b", re.IGNORECASE),
    re.compile(r"\b(?:ghp|github_pat)[A-Za-z0-9_-]{12,}\b", re.IGNORECASE),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9_-]{10,}\b", re.IGNORECASE),
    re.compile(r"\b(?:AKIA[0-9A-Z]{16}|aws_secret_access_key\s*[:=]\s*\S+)\b", re.IGNORECASE),
)

_CUSTOMER_IDENTIFIER_PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\w)\+\d[\d\s().-]{7,}\d(?!\w)"),
    re.compile(r"(?<!\w)(?:\+?61|0)4\d{8}(?!\w)"),
    re.compile(r"\b(?:\+?1[-.]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    re.compile(r"\b(?:customer|client)[ _-]?id\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b\d{3}\s\d{3}\s\d{3}\b"),
)

_WHITESPACE = re.compile(r"\s+")


def sanitise_ticket_text(value: str) -> str:
    """Normalise safe text and reject secrets or direct customer identifiers."""
    normalised = _WHITESPACE.sub(" ", value).strip()
    if any(pattern.search(normalised) for pattern in (*_SECRET_PATTERNS, *_CUSTOMER_IDENTIFIER_PATTERNS)):
        raise TicketContentSafetyError(
            "Ticket content contains a secret or direct customer identifier. Submit a sanitised summary instead."
        )
    return normalised


def ticket_deduplication_key(
    *,
    category: str,
    title: str,
    affected_product_area: Optional[str] = None,
    tenant_id: Optional[int] = None,
    description: Optional[str] = None,
) -> str:
    """Return a content fingerprint based on tenant scope, category, affected area, and normalized title."""
    parts = (
        str(tenant_id) if tenant_id is not None else "",
        category.strip().lower(),
        (affected_product_area or "").strip().lower(),
        title.strip().casefold(),
    )
    canonical = "\n".join(parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

