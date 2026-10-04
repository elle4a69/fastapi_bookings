"""Cryptographic confirmation tokens and knowledge validation for Business Assistant.

Enforces strict separation between draft and activation, cryptographic binding
of confirmation tokens to exact versioned content / payload hash / tenant / user,
and deterministic rejection of dynamic operational facts.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from typing import Any, Optional

from ...core.config import settings


class ConfirmationError(Exception):
    """Base error for confirmation token issues."""


class ConfirmationSignatureError(ConfirmationError):
    """Raised when token signature is invalid or tampered with."""


class ConfirmationExpiredError(ConfirmationError):
    """Raised when token has expired."""


class ConfirmationScopeMismatchError(ConfirmationError):
    """Raised when token does not match the active tenant or user scope."""


class ConfirmationPayloadMismatchError(ConfirmationError):
    """Raised when token does not match the exact target rule, version, or payload hash."""


class DynamicFactRejectedError(ValueError):
    """Raised when content contains dynamic operational facts that must not be stored as static rules."""

    def __init__(self, message: str, detected_types: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.detected_types = detected_types


_DYNAMIC_FACT_CHECKS = (
    (
        "pricing_or_payment",
        re.compile(
            r"(?:[$€£]\s*\d|\b(?:price|cost|fee|rate|deposit|balance|invoice|payment)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "slot_or_availability",
        re.compile(
            r"\b(?:open slot|free slot|slots|next appointment|booked out|appointment availability|available slot|available for booking|open for booking)\b|\b(?:available|availability)\b.{0,30}\b(?:slot|appointment|booking|session|tomorrow|today|morning|afternoon|calendar)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "booking_state_or_event",
        re.compile(
            r"\b(?:booking|appointment|reservation)\b.{0,28}\b(?:pending|confirmed|cancelled|canceled|rescheduled|completed|no[- ]show|#\d+|\bid\b)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "relative_or_specific_time",
        re.compile(
            r"\b(?:today|tomorrow|yesterday|tonight|this (?:week|month)|next (?:week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|currently|right now)\b|\b(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d{4}-\d{2}-\d{2})\b|\b(?:[01]?\d|2[0-3]):[0-5]\d\b|\b\d{1,2}(?::[0-5]\d)?\s*(?:am|pm)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "url_or_link",
        re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE),
    ),
    (
        "payment_detail",
        re.compile(
            r"\b(?:card number|credit card|debit card|bank account|bsb|routing number|payment link|checkout link|invoice link)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "customer_data_or_message",
        re.compile(
            r"(?:\[(?:NAME|PHONE|EMAIL|ADDRESS|CREDIT_CARD)\]|\b(?:customer|client|patient|my|your)\s+(?:phone|email|address|booking|appointment|payment|card|invoice|message)\b|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|\b04\d{8}\b|\b\+?\d{10,14}\b)",
            re.IGNORECASE,
        ),
    ),
)


def validate_static_business_knowledge(
    content: str,
    *,
    category: Optional[str] = None,
) -> None:
    """Validate that knowledge content contains only static business rules and policies.

    Fails closed: dynamic operational facts (availability slots, calendar events,
    current prices, specific booking IDs, customer messages) are rejected.
    """
    clean_text = (content or "").strip()
    if not clean_text:
        raise DynamicFactRejectedError("Business rule content cannot be empty.")

    detected: list[str] = []
    for label, pattern in _DYNAMIC_FACT_CHECKS:
        if pattern.search(clean_text):
            detected.append(label)

    if (category or "").lower() in {"pricing", "availability", "booking_status", "payment"}:
        detected.append("dynamic_category")

    if detected:
        unique_detected = tuple(dict.fromkeys(detected))
        types_str = ", ".join(unique_detected)
        raise DynamicFactRejectedError(
            f"Dynamic operational facts cannot be saved as static business knowledge. "
            f"Detected dynamic types: [{types_str}]. Live facts must be resolved from operational domain services.",
            detected_types=unique_detected,
        )


def compute_rule_payload_hash(
    *,
    tenant_id: int,
    user_id: int,
    memory_key: str,
    content: str,
    version: int,
) -> str:
    """Compute deterministic SHA-256 hash for rule versioning and confirmation binding."""
    canonical = json.dumps(
        {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "memory_key": memory_key.strip(),
            "content": content.strip(),
            "version": version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _get_signing_key(override: Optional[str] = None) -> bytes:
    key_str = override or getattr(settings, "SECRET_KEY", "business-assistant-confirmation-secret-key-default")
    return key_str.encode("utf-8")


def generate_confirmation_token(
    *,
    tenant_id: int,
    user_id: int,
    action: str,
    target_key: str,
    version: int,
    payload_hash: str,
    expires_in_seconds: int = 3600,
    secret_key: Optional[str] = None,
) -> str:
    """Generate a signed confirmation token bound to scope, target, version, and payload hash."""
    expires_at = int(time.time()) + expires_in_seconds
    payload_dict = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "action": action,
        "target_key": target_key,
        "version": version,
        "payload_hash": payload_hash,
        "exp": expires_at,
    }
    payload_bytes = json.dumps(payload_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")

    key = _get_signing_key(secret_key)
    sig = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_confirmation_token(
    token: str,
    *,
    expected_tenant_id: int,
    expected_user_id: int,
    expected_action: str,
    expected_target_key: str,
    expected_version: int,
    expected_payload_hash: str,
    secret_key: Optional[str] = None,
) -> dict[str, Any]:
    """Verify cryptographic confirmation token against scope and exact payload hash."""
    parts = token.strip().split(".")
    if len(parts) != 2:
        raise ConfirmationSignatureError("Malformed confirmation token.")

    payload_b64, sig = parts
    # Re-pad b64 if needed
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(padded)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise ConfirmationSignatureError("Failed to decode token payload.") from exc

    key = _get_signing_key(secret_key)
    expected_sig = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        raise ConfirmationSignatureError("Invalid confirmation token signature.")

    now = int(time.time())
    if payload.get("exp", 0) < now:
        raise ConfirmationExpiredError("Confirmation token has expired.")

    if payload.get("tenant_id") != expected_tenant_id or payload.get("user_id") != expected_user_id:
        raise ConfirmationScopeMismatchError(
            "Confirmation token was issued for a different tenant or user scope."
        )

    if payload.get("action") != expected_action:
        raise ConfirmationPayloadMismatchError(
            f"Action mismatch: token is for '{payload.get('action')}', expected '{expected_action}'."
        )

    if payload.get("target_key") != expected_target_key:
        raise ConfirmationPayloadMismatchError(
            f"Target mismatch: token is for '{payload.get('target_key')}', expected '{expected_target_key}'."
        )

    if payload.get("version") != expected_version:
        raise ConfirmationPayloadMismatchError(
            f"Version mismatch: token is for version {payload.get('version')}, but rule is currently version {expected_version}."
        )

    if payload.get("payload_hash") != expected_payload_hash:
        raise ConfirmationPayloadMismatchError(
            "Payload hash mismatch: the draft content has been modified since confirmation token was issued."
        )

    return payload


def compute_draft_payload_hash(
    *,
    tenant_id: int,
    user_id: int,
    conversation_id: int,
    content: str,
    version: int = 1,
) -> str:
    """Compute deterministic SHA-256 hash for message draft versioning and confirmation binding."""
    canonical = json.dumps(
        {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "content": content.strip(),
            "version": version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_campaign_payload_hash(
    *,
    tenant_id: int,
    user_id: int,
    title: str,
    content: str,
    recipient_count: int,
    version: int = 1,
) -> str:
    """Compute deterministic SHA-256 hash for campaign proposal versioning and confirmation binding."""
    canonical = json.dumps(
        {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "title": title.strip(),
            "content": content.strip(),
            "recipient_count": recipient_count,
            "version": version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

