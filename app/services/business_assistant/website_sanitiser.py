"""Content sanitisation and tenant-scoping for Website Builder Tool Pack (WP10).

Enforces strict rejection of:
1. XSS scripts, unsafe HTML/iframe/object injections, and executable event handlers.
2. Customer PII and payment card numbers in public website content.
3. Unauthorized external asset domains and dangerous URL schemes.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse


class WebsiteContentSafetyError(ValueError):
    """Raised when website content violates security, PII, or asset scope constraints."""


class WebsiteVersionConflictError(ValueError):
    """Raised when an edit proposal conflicts with the current website state version."""


# XSS & unsafe HTML / script injection patterns
_XSS_PATTERNS = (
    re.compile(r"<\s*script\b[^>]*>", re.IGNORECASE),
    re.compile(r"<\s*/\s*script\s*>", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"vbscript\s*:", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
    re.compile(r"<\s*iframe\b[^>]*>", re.IGNORECASE),
    re.compile(r"<\s*object\b[^>]*>", re.IGNORECASE),
    re.compile(r"<\s*embed\b[^>]*>", re.IGNORECASE),
    re.compile(r"<\s*applet\b[^>]*>", re.IGNORECASE),
    re.compile(r"<\s*form\b[^>]*>", re.IGNORECASE),
    re.compile(r"\bon[a-z]+\s*=", re.IGNORECASE),  # onload=, onerror=, onclick=
    re.compile(r"eval\s*\(", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),
)

# Customer PII patterns (PII placeholders, credit cards, customer-specific disclosures)
_CUSTOMER_PII_PATTERNS = (
    re.compile(r"\[(?:NAME|PHONE|EMAIL|ADDRESS|CREDIT_CARD)\]", re.IGNORECASE),
    re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b"),  # Major CCs
    re.compile(r"\b(?:credit\s*card|card\s*number|cvv|cvc)\s*[:=]\s*\d+", re.IGNORECASE),
    re.compile(r"\b(?:customer|client|patient)\s+(?:phone|email|credit\s*card|ssn|tfn)\b\s*[:=]", re.IGNORECASE),
)

# Standard allowed image/asset hosts for tenant website media
DEFAULT_ALLOWED_ASSET_DOMAINS = frozenset({
    "images.unsplash.com",
    "unsplash.com",
    "assets.fastapibookings.com",
    "cdn.fastapibookings.com",
    "storage.googleapis.com",
    "localhost",
    "127.0.0.1",
})

# Allowed hosts for social links & external destination links
DEFAULT_ALLOWED_SOCIAL_DOMAINS = frozenset({
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "twitter.com",
    "www.twitter.com",
    "x.com",
    "www.x.com",
    "linkedin.com",
    "www.linkedin.com",
    "youtube.com",
    "www.youtube.com",
    "tiktok.com",
    "www.tiktok.com",
})


def _validate_url_safety(
    url_str: str,
    field_name: str,
    allowed_domains: set[str],
) -> None:
    """Validate that a URL uses a safe scheme and points to an allowed domain if external."""
    trimmed = url_str.strip()
    if not trimmed:
        return

    # In-page anchor, mailto, tel, and relative assets are permitted
    if trimmed.startswith(("#", "/", "mailto:", "tel:")):
        return

    parsed = urlparse(trimmed)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise WebsiteContentSafetyError(
            f"Unsafe URL scheme '{scheme}' detected in field '{field_name}'. Only HTTP(S) URLs or relative paths are permitted."
        )

    netloc = (parsed.hostname or "").lower()
    if not netloc:
        raise WebsiteContentSafetyError(f"Invalid URL '{trimmed}' in field '{field_name}'.")

    # If it's an asset field (e.g. bg_image_url, image_url), check asset domain permissions
    is_asset_field = any(k in field_name for k in ("image", "bg_image", "logo", "asset", "icon"))
    if is_asset_field:
        if not any(netloc == domain or netloc.endswith("." + domain) for domain in allowed_domains):
            raise WebsiteContentSafetyError(
                f"Unauthorized asset domain '{netloc}' in field '{field_name}'. Assets must be hosted on authorized tenant domains or approved CDNs."
            )


def sanitise_and_validate_value(
    value: Any,
    field_name: str,
    allowed_domains: set[str],
) -> None:
    """Recursively inspect a content value for XSS, PII, and unauthorized asset domains."""
    if isinstance(value, str):
        # 1. Check for XSS and script injections
        for pat in _XSS_PATTERNS:
            if pat.search(value):
                raise WebsiteContentSafetyError(
                    f"Unsafe script or HTML injection detected in '{field_name}': {pat.pattern}"
                )

        # 2. Check for customer PII leaks
        for pat in _CUSTOMER_PII_PATTERNS:
            if pat.search(value):
                raise WebsiteContentSafetyError(
                    f"Customer PII or payment card data detected in website content ('{field_name}')."
                )

        # 3. Check URL fields
        if any(k in field_name for k in ("url", "link", "src", "href")) or value.startswith(("http://", "https://")):
            _validate_url_safety(value, field_name, allowed_domains)

    elif isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str):
                for pat in _XSS_PATTERNS:
                    if pat.search(k):
                        raise WebsiteContentSafetyError(f"Unsafe property key detected: '{k}'.")
            sanitise_and_validate_value(v, f"{field_name}.{k}" if field_name else str(k), allowed_domains)

    elif isinstance(value, (list, tuple)):
        for idx, item in enumerate(value):
            sanitise_and_validate_value(item, f"{field_name}[{idx}]", allowed_domains)


def validate_and_sanitise_website_content(
    content_payload: dict[str, Any],
    *,
    tenant_domain: Optional[str] = None,
    allowed_domains: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Validate website content payload against safety rules and asset permissions.

    Returns the validated payload unmodified if compliant; raises WebsiteContentSafetyError otherwise.
    """
    if not isinstance(content_payload, dict):
        raise WebsiteContentSafetyError("Website content payload must be a dictionary.")

    effective_allowed = set(DEFAULT_ALLOWED_ASSET_DOMAINS) | set(DEFAULT_ALLOWED_SOCIAL_DOMAINS)
    if allowed_domains:
        effective_allowed |= {d.lower() for d in allowed_domains}
    if tenant_domain:
        effective_allowed.add(tenant_domain.lower())

    sanitise_and_validate_value(content_payload, "content_payload", effective_allowed)
    return content_payload
