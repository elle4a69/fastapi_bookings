"""Knowledge policy and boundary enforcement.

Guards against multi-tenant scope leakage, graph pollution by ephemeral/dynamic
operational data (Spec 19), and safety/security prompt injections.
"""

from __future__ import annotations

import re
from typing import Optional

# Regular expressions detecting dynamic operational data (Spec 19)
_DYNAMIC_OPERATIONAL_PATTERNS = [
    # Specific times / time slots / calendar availability
    r"\b(?:tomorrow|today|yesterday|tonight)\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b",
    r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s+(?:tomorrow|today|yesterday|tonight)\b",
    r"\b(?:appointment|booking|session)\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?(?:\s+(?:tomorrow|today|tonight))?\b",
    r"\b(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b",
    r"\b(?:available\s+(?:tomorrow|today)|booked\s+you\s+in|confirmed\s+your\s+appointment|open\s+slot|next\s+appointment|book\s+you\s+for|can\s+fit\s+you\s+in)\b",
    r"\b(?:open\s+slot|slot\s+available|opening)\s+(?:at|on)\s+\b",
    r"\b(?:fully\s+booked|no\s+availability)\s+(?:today|tomorrow|this\s+week)\b",
    r"\b(?:booked\s+you\s+in|confirmed\s+for)\s+(?:today|tomorrow|\w+day)\b",
    
    # Specific transient price quotes or payment links
    r"\b(?:total|quote|balance)\s+(?:is|came\s+to|of)\s+[\$£€]\d+(?:\.\d{2})?\s*(?:for\s+today|now)?\b",
    r"https?://(?:buy\.|checkout\.)?stripe\.com/\S+",
    r"https?://[^\s/]+/pay/\S+",
    r"https?://[^\s/]+/invoice/\S+",
    r"\b(?:pay\s+link|payment\s+link):\s*https?://\S+\b",
]

_DYNAMIC_OPERATIONAL_REGEXES = [re.compile(p, re.IGNORECASE) for p in _DYNAMIC_OPERATIONAL_PATTERNS]

# Regular expressions detecting system safety violations & adversarial instructions
_SAFETY_VIOLATION_PATTERNS = [
    r"\bignore\s+(?:all\s+)?(?:previous\s+)?instructions\b",
    r"\bsystem\s+override\b",
    r"\b(?:jailbreak|unrestricted\s+mode|developer\s+mode)\b",
    r"\b(?:override|bypass|disable|circumvent)\s+.*?\b(?:rules?|constraints?|checks?|policy|policies)\b",
    r"\b(?:override|bypass|disable|circumvent)\s+(?:all\s+)?(?:system|security|booking|calendar|cancellation|deposit|payment|safety)\s*(?:rules?|constraints?|checks?|policy|policies)?\b",
    r"\balways\s+say\s+yes\s+to\s+(?:any\s+)?appointments?\s+even\s+if\s+double\s+booked\b",
    r"\bno\s+need\s+to\s+check\s+availability\b",
    r"\bdisregard\s+(?:calendar|schedule|working\s+hours|business\s+hours)\b",
    r"\b(?:expose|reveal|dump|leak)\s+(?:secret|password|api\s*key|database|token)\b",
    r"\bgrant\s+(?:admin|superuser|root)\s+(?:access|role|permissions?)\b",
]

_SAFETY_VIOLATION_REGEXES = [re.compile(p, re.IGNORECASE) for p in _SAFETY_VIOLATION_PATTERNS]


def validate_scope(tenant_id: int, provider_id: Optional[int], allowed_tenant_id: int) -> bool:
    """Validate that the query or item scope strictly matches the authenticated tenant context.

    Returns False if:
    - tenant_id does not equal allowed_tenant_id
    - tenant_id <= 0
    - provider_id is provided and <= 0
    """
    if tenant_id <= 0 or allowed_tenant_id <= 0:
        return False
    if tenant_id != allowed_tenant_id:
        return False
    if provider_id is not None and provider_id <= 0:
        return False
    return True


def is_dynamic_operational_data(text: str) -> bool:
    """Detect real-time availability, booking times, pricing quotes, or one-time payment links.

    Per Spec 19, transient operational details must not pollute the long-term knowledge graph.
    """
    if not text or not text.strip():
        return False

    for pattern in _DYNAMIC_OPERATIONAL_REGEXES:
        if pattern.search(text):
            return True
    return False


def is_system_safety_violation(text: str) -> bool:
    """Detect safety violations, prompt injections, or attempts to circumvent booking rules."""
    if not text or not text.strip():
        return False

    for pattern in _SAFETY_VIOLATION_REGEXES:
        if pattern.search(text):
            return True
    return False
