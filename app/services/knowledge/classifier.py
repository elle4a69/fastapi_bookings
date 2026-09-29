"""Fail-Closed Safety Classifier for Knowledge and Message Style Examples.

Enforces strict separation between durable factual business knowledge (CuratedMemory)
and procedural conversational style examples (MessageStyleExample).
Guards against dynamic operational pollution (Spec 19), PII leakage, and prompt injections.
"""

from __future__ import annotations

from enum import Enum
import logging
import re
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ClassificationCategory(str, Enum):
    """Classification categories for text proposed for knowledge or style stores."""
    DYNAMIC_OPERATIONAL = "DYNAMIC_OPERATIONAL"
    PII = "PII"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    FACTUAL_PROPOSAL = "FACTUAL_PROPOSAL"
    PROCEDURAL_EXAMPLE = "PROCEDURAL_EXAMPLE"


class SafetyDecision(str, Enum):
    """Classifier safety actions."""
    ACCEPT = "ACCEPT"
    QUARANTINE = "QUARANTINE"
    REJECT = "REJECT"


class ClassificationResult(BaseModel):
    """Result of classifying a candidate text or example pair."""
    category: ClassificationCategory
    decision: SafetyDecision
    reason: str
    is_safe: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


# -------------------------------------------------------------------------
# Prompt Injection Patterns (Adversarial System Overrides / Delimiters)
# -------------------------------------------------------------------------
_PROMPT_INJECTION_PATTERNS = [
    r"\bignore\s+(?:all\s+)?(?:previous\s+)?instructions\b",
    r"\bsystem\s+override\b",
    r"\b(?:jailbreak|unrestricted\s+mode|developer\s+mode)\b",
    r"\b(?:override|bypass|disable|circumvent)\s+.*?\b(?:rules?|constraints?|checks?|policy|policies)\b",
    r"\bgrant\s+(?:admin|superuser|root)\s+(?:access|role|permissions?)\b",
    r"\b(?:expose|reveal|dump|leak)\s+(?:secret|password|api\s*key|database|token)\b",
    r"\byou\s+are\s+now\s+(?:a|an)\b",
    r"\bact\s+as\s+(?:a|an)\b",
    r"\bdisregard\s+(?:system|all)\s+prompts?\b",
    r"(?:```\s*system|<\|im_start\|>|<\|im_end\|>|---BEGIN PROMPT---|---END PROMPT---|\[SYSTEM\]|system:)",
]
_PROMPT_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in _PROMPT_INJECTION_PATTERNS]


# -------------------------------------------------------------------------
# PII Patterns (Unscrubbed Australian Mobile/Landline, Email, Address, Cards)
# -------------------------------------------------------------------------
# Credit cards
_CREDIT_CARD_RE = re.compile(
    r"\b(?:"
    r"3[47]\d{2}[ .-]?\d{6}[ .-]?\d{5}|"
    r"(?:\d{4}[ .-]?){3}\d{1,4}|"
    r"\d{13,19}"
    r")\b"
)

# Email addresses (unscrubbed, not placeholder)
_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Phone numbers (unscrubbed Australian / international numbers)
_PHONE_PATTERNS = [
    r"\b04\d{2}[ -]?\d{3}[ -]?\d{3}\b",
    r"\+61\s*(?:\(0\))?[ -]*4\d{2}[ -]?\d{3}[ -]?\d{3}\b",
    r"\(\s*0[2-478]\s*\)[ -]?\d{4}[ -]?\d{4}\b",
    r"\b0[2-478]\s*\d{4}[ -]?\d{4}\b",
    r"\b1[38]00[ -]?\d{3}[ -]?\d{3}\b",
    r"\b13[ -]?\d{2}[ -]?\d{2}\b",
    r"\+\d{1,3}(?:[ -]?\(?\d{1,4}\)?){1,4}(?:[ -]?\d{3,4})\b",
]
_PHONE_RE = [re.compile(p) for p in _PHONE_PATTERNS]

# Residential Street Addresses (unscrubbed, e.g. "123 Main St, Richmond VIC 3121")
_ADDRESS_PATTERNS = [
    r"\b\d{1,5}\s+[A-Za-z0-9\s]{2,30}\s+(?:Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Close|Cl|Lane|Ln|Place|Pl|Boulevard|Blvd|Parade|Pde|Court|Ct|Way|Terrace|Tce|Crescent|Cres|Highway|Hwy)\b",
    r"\b\d{1,5}\s+[A-Za-z\s]+(?:,\s*[A-Za-z\s]+)?\s+(?:NSW|VIC|QLD|WA|SA|TAS|ACT|NT)\s+\d{4}\b",
]
_ADDRESS_RE = [re.compile(p, re.IGNORECASE) for p in _ADDRESS_PATTERNS]

# Customer name intros: "My name is John Doe", "I am Jane Doe"
_NAME_INTRO_RE = re.compile(
    r"\b(?:my\s+name\s+is|i\s+am|this\s+is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
)


# -------------------------------------------------------------------------
# Dynamic Operational Data Patterns (Dates, Times, Slots, Live Pricing)
# -------------------------------------------------------------------------
_DYNAMIC_OPERATIONAL_PATTERNS = [
    # Specific times / time slots / calendar availability
    r"\b(?:tomorrow|today|yesterday|tonight)\s+(?:at|around)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b",
    r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s+(?:tomorrow|today|yesterday|tonight)\b",
    r"\b(?:appointment|booking|session)\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?(?:\s+(?:tomorrow|today|tonight))?\b",
    r"\b(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?:at|around)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b",
    r"\b(?:open\s+slot|slot\s+available|available\s+slot|booked\s+you\s+in|confirmed\s+your\s+appointment|book\s+you\s+for|can\s+fit\s+you\s+in)\b",
    r"\b(?:open\s+slot|slot\s+available|opening)\s+(?:at|on)\s+\b",
    r"\b(?:fully\s+booked|no\s+availability)\s+(?:today|tomorrow|this\s+week)\b",
    r"\b(?:booked\s+you\s+in|confirmed\s+for)\s+(?:today|tomorrow|\w+day)\b",
    r"\b(?:30|45|60|90)\s*mins?\s+(?:slot|appointment|opening)\b",
    # Specific transient price quotes or payment links
    r"\b(?:total|quote|balance|price)\s+(?:is|came\s+to|of)\s+[\$£€]\d+(?:\.\d{2})?\b",
    r"\b[\$£€]\d+(?:\.\d{2})?\s+(?:for\s+today|now|deposit|balance)\b",
    r"https?://(?:buy\.|checkout\.)?stripe\.com/\S+",
    r"https?://[^\s/]+/pay/\S+",
    r"https?://[^\s/]+/invoice/\S+",
    r"\b(?:pay\s+link|payment\s+link):\s*https?://\S+\b",
]
_DYNAMIC_OPERATIONAL_RE = [re.compile(p, re.IGNORECASE) for p in _DYNAMIC_OPERATIONAL_PATTERNS]


# -------------------------------------------------------------------------
# Conversational / Procedural Markers
# -------------------------------------------------------------------------
_PROCEDURAL_MARKERS = [
    r"\b(?:hello|hi|hey|thanks|thank\s+you|g'day|cheers|bye|regards)\b",
    r"\b(?:see\s+you|let\s+me\s+know|sounds\s+good|no\s+worries|fair\s+enough)\b",
    r"\b(?:can\s+i|are\s+you\s+free|what\s+time|how\s+much|how\s+long)\b",
    r"\b(?:ur|u|pls|gorg|haha|sweet|yay|xxx|😘|🙃|🙄)\b",
    r"\{[a-z_]+\}",  # Templated sanitized placeholders
]
_PROCEDURAL_RE = [re.compile(p, re.IGNORECASE) for p in _PROCEDURAL_MARKERS]

# Static business truth indicators (policies, facilities, parking, accessibility)
_FACTUAL_INDICATORS = [
    r"\b(?:parking|wheelchair|accessible|facility|facilities|entrance|amenity|amenities)\b",
    r"\b(?:complimentary|tea|water|wifi|waiting\s+area|lounge|suite)\b",
    r"\b(?:cancellation\s+policy|notice\s+required|deposit\s+policy|terms)\b",
    r"\b(?:located\s+at|address\s+is|behind\s+the|situated\s+in)\b",
    r"\b(?:specialise\s+in|services\s+include|treatment\s+options)\b",
]
_FACTUAL_RE = [re.compile(p, re.IGNORECASE) for p in _FACTUAL_INDICATORS]


def detect_prompt_injection(text: str) -> Optional[str]:
    """Check text for prompt injection, system overrides, or delimiter escapes."""
    if not text:
        return None
    for pattern in _PROMPT_INJECTION_RE:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def detect_pii(text: str) -> Optional[Tuple[str, str]]:
    """Check text for unscrubbed PII (phones, emails, addresses, credit cards, names).
    
    Returns (pii_type, matched_snippet) or None if no unscrubbed PII is found.
    """
    if not text:
        return None

    # Credit card check
    cc_match = _CREDIT_CARD_RE.search(text)
    if cc_match:
        return ("credit_card", cc_match.group(0))

    # Email check
    email_match = _EMAIL_RE.search(text)
    if email_match:
        return ("email", email_match.group(0))

    # Phone check
    for pattern in _PHONE_RE:
        match = pattern.search(text)
        if match:
            return ("phone", match.group(0))

    # Street address check
    for pattern in _ADDRESS_RE:
        match = pattern.search(text)
        if match:
            return ("address", match.group(0))

    # Name intro check
    name_match = _NAME_INTRO_RE.search(text)
    if name_match:
        return ("customer_name", name_match.group(1))

    return None


def detect_dynamic_operational(text: str) -> Optional[str]:
    """Check text for transient dates, times, slot details, live quotes, or payment links."""
    if not text:
        return None
    for pattern in _DYNAMIC_OPERATIONAL_RE:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def is_conversational_or_procedural(text: str) -> bool:
    """Detect whether text has conversational phrasing or template tokens."""
    if not text:
        return False
    for pattern in _PROCEDURAL_RE:
        if pattern.search(text):
            return True
    return False


def is_factual_proposal(text: str) -> bool:
    """Detect whether text is a static factual business statement."""
    if not text:
        return False
    for pattern in _FACTUAL_RE:
        if pattern.search(text):
            return True
    # If it's a declarative sentence without conversational cues
    if not is_conversational_or_procedural(text) and len(text.strip()) >= 20:
        return True
    return False


def classify_text(text: str) -> ClassificationResult:
    """Classify standalone text proposed for knowledge or style stores.

    Fail-closed: Returns REJECT if input is empty, ambiguous, or safety rules fail.
    """
    if not text or not text.strip():
        return ClassificationResult(
            category=ClassificationCategory.DYNAMIC_OPERATIONAL,
            decision=SafetyDecision.REJECT,
            reason="Empty or whitespace-only content rejected by fail-closed policy",
            is_safe=False,
        )

    # 1. Prompt Injection Gate
    injection_match = detect_prompt_injection(text)
    if injection_match:
        return ClassificationResult(
            category=ClassificationCategory.PROMPT_INJECTION,
            decision=SafetyDecision.REJECT,
            reason=f"Prompt injection or system override detected: '{injection_match}'",
            is_safe=False,
            details={"match": injection_match},
        )

    # 2. PII Gate
    pii_match = detect_pii(text)
    if pii_match:
        pii_type, snippet = pii_match
        return ClassificationResult(
            category=ClassificationCategory.PII,
            decision=SafetyDecision.REJECT,
            reason=f"Unscrubbed PII detected ({pii_type}): '{snippet}'",
            is_safe=False,
            details={"pii_type": pii_type, "snippet": snippet},
        )

    # 3. Dynamic Operational Gate
    dyn_match = detect_dynamic_operational(text)
    if dyn_match:
        return ClassificationResult(
            category=ClassificationCategory.DYNAMIC_OPERATIONAL,
            decision=SafetyDecision.REJECT,
            reason=f"Dynamic operational data detected: '{dyn_match}'",
            is_safe=False,
            details={"match": dyn_match},
        )

    # 4. Procedural vs Factual Classification
    if is_conversational_or_procedural(text):
        return ClassificationResult(
            category=ClassificationCategory.PROCEDURAL_EXAMPLE,
            decision=SafetyDecision.ACCEPT,
            reason="Conversational dialogue or style exemplar suitable for MessageStyleExample",
            is_safe=True,
        )

    if is_factual_proposal(text):
        return ClassificationResult(
            category=ClassificationCategory.FACTUAL_PROPOSAL,
            decision=SafetyDecision.ACCEPT,
            reason="Static business truth or durable policy suitable for CuratedMemory",
            is_safe=True,
        )

    # Fail-closed for short or ambiguous statements
    return ClassificationResult(
        category=ClassificationCategory.DYNAMIC_OPERATIONAL,
        decision=SafetyDecision.REJECT,
        reason="Ambiguous content rejected by fail-closed policy",
        is_safe=False,
    )


def classify_proposed_knowledge(text: str) -> ClassificationResult:
    """Classify text specifically proposed for CuratedMemory (factual store).

    Enforces that procedural examples NEVER enter CuratedMemory.
    """
    res = classify_text(text)
    if not res.is_safe:
        return res

    if res.category == ClassificationCategory.PROCEDURAL_EXAMPLE:
        return ClassificationResult(
            category=ClassificationCategory.PROCEDURAL_EXAMPLE,
            decision=SafetyDecision.REJECT,
            reason="Procedural dialog / style examples cannot be stored in CuratedMemory (factual store). Use MessageStyleExample instead.",
            is_safe=False,
        )

    if res.category == ClassificationCategory.FACTUAL_PROPOSAL:
        return res

    return ClassificationResult(
        category=ClassificationCategory.DYNAMIC_OPERATIONAL,
        decision=SafetyDecision.REJECT,
        reason="Unapproved content rejected for CuratedMemory",
        is_safe=False,
    )


def classify_style_example(
    client_message: str,
    assistant_reply: str,
    is_approved_source: bool = False,
) -> ClassificationResult:
    """Classify and validate a (client_message, assistant_reply) pair for MessageStyleExample.

    Ensures no unscrubbed PII, prompt injections, or unapproved dynamic payment leaks.
    Also ensures static factual proposals NEVER enter MessageStyleExample.
    """
    combined = f"{client_message or ''}\n{assistant_reply or ''}".strip()
    if not combined or not (client_message and client_message.strip()) or not (assistant_reply and assistant_reply.strip()):
        return ClassificationResult(
            category=ClassificationCategory.DYNAMIC_OPERATIONAL,
            decision=SafetyDecision.REJECT,
            reason="Incomplete dialog pair rejected by fail-closed policy",
            is_safe=False,
        )

    # 1. Prompt Injection
    injection = detect_prompt_injection(combined)
    if injection:
        return ClassificationResult(
            category=ClassificationCategory.PROMPT_INJECTION,
            decision=SafetyDecision.REJECT,
            reason=f"Prompt injection detected in style example: '{injection}'",
            is_safe=False,
        )

    # 2. PII Leak Gate
    pii = detect_pii(combined)
    if pii:
        pii_type, snippet = pii
        return ClassificationResult(
            category=ClassificationCategory.PII,
            decision=SafetyDecision.REJECT,
            reason=f"Unscrubbed PII ({pii_type}) detected in style example: '{snippet}'",
            is_safe=False,
            details={"pii_type": pii_type, "snippet": snippet},
        )

    # 3. Dynamic Payment Links Check (live stripe or pay URLs never permitted)
    payment_link_match = re.search(
        r"https?://(?:buy\.|checkout\.)?stripe\.com/\S+|https?://[^\s/]+/pay/\S+",
        combined,
        re.IGNORECASE,
    )
    if payment_link_match:
        return ClassificationResult(
            category=ClassificationCategory.DYNAMIC_OPERATIONAL,
            decision=SafetyDecision.REJECT,
            reason=f"Live payment link found in style example: '{payment_link_match.group(0)}'",
            is_safe=False,
        )

    # 4. Invariant: Factual proposals must NOT enter MessageStyleExample
    # If the candidate pair is just a static business truth (e.g. identical or non-dialogue static fact)
    if not is_approved_source:
        norm_client = client_message.strip().lower()
        norm_reply = assistant_reply.strip().lower()
        if (
            norm_client == norm_reply
            or (not is_conversational_or_procedural(client_message) and is_factual_proposal(assistant_reply))
        ):
            return ClassificationResult(
                category=ClassificationCategory.FACTUAL_PROPOSAL,
                decision=SafetyDecision.REJECT,
                reason="Static factual proposal cannot be stored in MessageStyleExample. Use CuratedMemory instead.",
                is_safe=False,
            )

    return ClassificationResult(
        category=ClassificationCategory.PROCEDURAL_EXAMPLE,
        decision=SafetyDecision.ACCEPT,
        reason="Approved procedural style example",
        is_safe=True,
    )
