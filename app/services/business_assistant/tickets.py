"""Safety rules for persisted support-ticket summaries."""

from __future__ import annotations

import hashlib
import re


class TicketContentSafetyError(ValueError):
    """Raised when ticket text contains information that must not be persisted."""


_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|secret|password|token|authorization)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+\-/]+=*", re.IGNORECASE),
    re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{12,}\b", re.IGNORECASE),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b", re.IGNORECASE),
    re.compile(r"\b(?:ghp|github_pat|xox[baprs]|AKIA)[A-Za-z0-9_-]{12,}\b", re.IGNORECASE),
)
_CUSTOMER_IDENTIFIER_PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\w)\+\d[\d\s().-]{7,}\d(?!\w)"),
    re.compile(r"(?<!\w)(?:\+?61|0)4\d{8}(?!\w)"),
    re.compile(r"\b(?:customer|client)[ _-]?id\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
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


def ticket_deduplication_key(*, category: str, title: str, description: str) -> str:
    """Return a content fingerprint without storing a second copy of ticket text."""
    canonical = "\n".join((category.strip().lower(), title.casefold(), description.casefold()))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
