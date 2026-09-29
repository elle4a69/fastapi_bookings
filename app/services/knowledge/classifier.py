"""Fail-Closed Safety Classifier for Knowledge and Message Style Examples.

Enforces strict separation between durable factual business knowledge (CuratedMemory)
and procedural conversational style examples (MessageStyleExample).
Guards against dynamic operational pollution (Spec 19), PII leakage, and prompt injections.
"""

from __future__ import annotations

from enum import Enum
import logging
import re
from typing import Any, Dict, Optional, Set, Tuple

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


class TypedVariableKind(str, Enum):
    """Approved, non-customer variables that a procedural example may reference.

    These are *references*, not values to learn.  Their values are resolved from
    tenant/provider configuration or a live tool at response time.  In
    particular, there is intentionally no customer, date, time, price, slot or
    arbitrary address variable here.
    """

    BUSINESS_NAME = "business_name"
    PROVIDER_NAME = "provider_name"
    LOCATION_NAME = "location_name"
    LOCATION_ADDRESS = "location_address"
    SERVICE_NAME = "service_name"
    SERVICE_AREA = "service_area"
    BOOKING_LINK = "booking_link"


class TypedVariableAssessment(BaseModel):
    """Privacy-safe result of checking template references in learning content."""

    is_safe: bool
    variables: Set[str] = Field(default_factory=set)
    reason: Optional[str] = None


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
    # Raw template / SSTI / execution injection syntax
    r"\{\{.*?\}\}",
    r"\$\{.*?\}",
    r"<%#?.*?%>",
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

# Customer name intros: "My name is John Doe", "my name is John Doe", "this is Jane Doe"
_NAME_INTRO_RE = re.compile(
    r"\b(?i:my\s+name\s+is|this\s+is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
)


# -------------------------------------------------------------------------
# Dynamic Operational Data Patterns (Dates, Times, Slots, Live Pricing)
# -------------------------------------------------------------------------
_DYNAMIC_OPERATIONAL_PATTERNS = [
    # Relative calendar references are contextual to the conversation and are
    # never durable learning content, even without a written time.
    r"\b(?:today|tomorrow|yesterday|tonight)\b",
    # Concrete calendar dates are likewise a live booking context rather than
    # a reusable policy or style rule.
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
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

    typed_variables = assess_typed_variables(text)
    if not typed_variables.is_safe:
        return ClassificationResult(
            category=ClassificationCategory.DYNAMIC_OPERATIONAL,
            decision=SafetyDecision.REJECT,
            reason=typed_variables.reason or "Unsafe typed variable reference",
            is_safe=False,
            details={"variables": sorted(typed_variables.variables)},
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


def classify_curated_memory_candidate(
    user_query: str,
    ideal_response: str,
) -> ClassificationResult:
    """Validate both fields immediately before a durable-memory write.

    ``ideal_response`` must be a durable factual statement.  ``user_query``
    may be conversational, but it still cannot carry PII, a live operational
    claim, prompt injection, a redaction marker, or an unapproved variable.
    """
    response_result = classify_proposed_knowledge(ideal_response)
    if not response_result.is_safe:
        return response_result

    query_variables = assess_typed_variables(user_query)
    if not query_variables.is_safe:
        return ClassificationResult(
            category=ClassificationCategory.DYNAMIC_OPERATIONAL,
            decision=SafetyDecision.REJECT,
            reason=query_variables.reason or "Unsafe variable reference in memory query",
            is_safe=False,
        )
    injection = detect_prompt_injection(user_query)
    if injection:
        return ClassificationResult(
            category=ClassificationCategory.PROMPT_INJECTION,
            decision=SafetyDecision.REJECT,
            reason="Prompt injection detected in memory query",
            is_safe=False,
        )
    pii = detect_pii(user_query)
    if pii:
        return ClassificationResult(
            category=ClassificationCategory.PII,
            decision=SafetyDecision.REJECT,
            reason="PII detected in memory query",
            is_safe=False,
        )
    dynamic = detect_dynamic_operational(user_query)
    if dynamic:
        return ClassificationResult(
            category=ClassificationCategory.DYNAMIC_OPERATIONAL,
            decision=SafetyDecision.REJECT,
            reason="Dynamic operational data detected in memory query",
            is_safe=False,
        )
    return response_result


# -------------------------------------------------------------------------
# Placeholder Variable Allowlist Rules
# -------------------------------------------------------------------------
# This registry is deliberately small.  A procedural example may reference a
# stable business/configuration value, but it must never learn a customer value
# or turn a transient operational value into a reusable template.  Dates,
# times, availability, prices, booking IDs and customer/contact/address values
# therefore have no supported placeholder and must be fetched through a scoped
# live tool when they are needed.
APPROVED_TYPED_VARIABLES: Dict[str, TypedVariableKind] = {
    TypedVariableKind.BUSINESS_NAME.value: TypedVariableKind.BUSINESS_NAME,
    TypedVariableKind.PROVIDER_NAME.value: TypedVariableKind.PROVIDER_NAME,
    TypedVariableKind.LOCATION_NAME.value: TypedVariableKind.LOCATION_NAME,
    TypedVariableKind.LOCATION_ADDRESS.value: TypedVariableKind.LOCATION_ADDRESS,
    TypedVariableKind.SERVICE_NAME.value: TypedVariableKind.SERVICE_NAME,
    TypedVariableKind.SERVICE_AREA.value: TypedVariableKind.SERVICE_AREA,
    TypedVariableKind.BOOKING_LINK.value: TypedVariableKind.BOOKING_LINK,
}

ALLOWED_STYLE_PLACEHOLDERS: Set[str] = set(APPROVED_TYPED_VARIABLES)

LEGACY_SEED_PLACEHOLDERS: Set[str] = {
    "address",
    "building_number",
    "date",
    "hotel_name",
    "level_number",
    "name",
    "phone",
    "provider_name",
    "room_number",
    "suburb",
    "time",
    "website",
}

_REDACTION_MARKER_RE = re.compile(r"\[(?:ADDRESS|EMAIL|PHONE|NAME|CREDIT_CARD)\]")


def assess_typed_variables(
    text: str,
    *,
    is_approved_source: bool = False,
) -> TypedVariableAssessment:
    """Check a procedural template against the strict typed-variable registry.

    This is intentionally validation, not a best-effort anonymiser.  Replacing
    a literal appointment time, quote, customer address or phone number with a
    token after the fact would still convert a live conversation into reusable
    memory without proving that the replacement is semantically safe.  Callers
    must reject those candidates and use live tools for operational data.
    """
    if not text:
        return TypedVariableAssessment(is_safe=True)

    if _REDACTION_MARKER_RE.search(text):
        return TypedVariableAssessment(
            is_safe=False,
            reason="Redacted customer or address data cannot be retained as reusable memory",
        )

    raw_syntax_patterns = (
        r"\{\{.*?\}\}",
        r"\{%.*?%\}",
        r"\$\{.*?\}",
        r"<%#?.*?%>",
    )
    for pattern in raw_syntax_patterns:
        if re.search(pattern, text):
            return TypedVariableAssessment(
                is_safe=False,
                reason="Raw execution or template syntax is not an approved typed variable",
            )

    matches = {match.strip() for match in re.findall(r"\{([^{}]+)\}", text)}
    allowed = set(APPROVED_TYPED_VARIABLES)
    if is_approved_source:
        allowed |= LEGACY_SEED_PLACEHOLDERS
    unknown = matches - allowed
    if unknown:
        return TypedVariableAssessment(
            is_safe=False,
            variables=matches,
            reason="Unapproved variable reference in learning content",
        )

    cleaned = re.sub(r"\{[^{}]+\}", "", text)
    if "{" in cleaned or "}" in cleaned:
        return TypedVariableAssessment(
            is_safe=False,
            variables=matches,
            reason="Malformed placeholder braces detected",
        )

    return TypedVariableAssessment(is_safe=True, variables=matches)


def validate_style_placeholders(
    text: str,
    is_approved_source: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Validate placeholder variables in message style text against allowlist.

    Allowed standard variables:
      {business_name}, {provider_name}, {location_name}, {location_address}, {booking_link}, {service_name}
    When is_approved_source is True (packaged seed asset), legacy seed placeholders are also accepted.
    Any raw execution variables ({{...}}, ${...}, <%...%>) or unapproved variables are strictly rejected.
    """
    assessment = assess_typed_variables(text, is_approved_source=is_approved_source)
    if not assessment.is_safe:
        return False, assessment.reason
    return True, None


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

    # 3. Dynamic Payment Links & Operational Data Check
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

    dyn_match = detect_dynamic_operational(combined)
    if dyn_match:
        return ClassificationResult(
            category=ClassificationCategory.DYNAMIC_OPERATIONAL,
            decision=SafetyDecision.REJECT,
            reason=f"Dynamic operational data detected in style example: '{dyn_match}'",
            is_safe=False,
            details={"match": dyn_match},
        )

    # 4. Placeholder Allowlist & Raw Execution Variable Validation
    is_valid_client, err_client = validate_style_placeholders(
        client_message, is_approved_source=is_approved_source
    )
    if not is_valid_client:
        return ClassificationResult(
            category=ClassificationCategory.PROMPT_INJECTION,
            decision=SafetyDecision.REJECT,
            reason=f"Client message failed placeholder validation: {err_client}",
            is_safe=False,
            details={"error": err_client},
        )

    is_valid_reply, err_reply = validate_style_placeholders(
        assistant_reply, is_approved_source=is_approved_source
    )
    if not is_valid_reply:
        return ClassificationResult(
            category=ClassificationCategory.PROMPT_INJECTION,
            decision=SafetyDecision.REJECT,
            reason=f"Assistant reply failed placeholder validation: {err_reply}",
            is_safe=False,
            details={"error": err_reply},
        )

    # 5. Invariant: Factual proposals must NOT enter MessageStyleExample
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
