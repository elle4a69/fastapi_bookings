"""PII Scrubber for conversation transcripts and memory curation.

Provides deterministic, rule-based redacting of Personally Identifiable
Information (PII) including:
- Customer names (introductory patterns, honorifics, salutations, explicit names)
- Phone numbers (Australian mobile, landlines, 13/1300/1800, international E.164)
- Email addresses
- Credit card numbers (standard format, Amex, Luhn check)
- Residential street addresses (Australian street suffixes, unit prefixes, states/postcodes)
"""

import re
from typing import Optional, Sequence

# -------------------------------------------------------------------------
# Regex Pattern Definitions
# -------------------------------------------------------------------------

# Credit cards: 13 to 19 digits grouped with hyphens/spaces/dots or contiguous (Visa, MC, Amex, Discover)
_CREDIT_CARD_RE = re.compile(
    r"\b(?:"
    r"3[47]\d{2}[ .-]?\d{6}[ .-]?\d{5}|"  # American Express (4-6-5 format)
    r"(?:\d{4}[ .-]?){3}\d{1,4}|"  # Grouped 16-19 digits (Visa, MC, Discover)
    r"\d{13,19}"  # Contiguous 13-19 digits
    r")\b"
)

# Email addresses (RFC 5322 simplified)
_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
)

# Phone numbers: Australian mobile, landline, toll-free, and international formats
_PHONE_PATTERNS = [
    # Australian mobile & landlines with area code in parentheses or prefix: (0412) 345 678, (02) 9876 5432
    r"\(\s*0[2-478]\d{0,2}\s*\)[ .-]?(?:\d[ .-]?){6,8}\b",
    # Australian mobile & landlines: 04xx xxx xxx, +61 4xx xxx xxx, 0412.345.678, 0412-345-678, etc.
    r"(?:\+?61\s*(?:\(0\))?[ .-]*|\(?0)[2-478]\)?[ .-]?(?:\d[ .-]?){7,8}\b",
    # Australian 1300 / 1800 numbers
    r"\b1[38]00(?:[ .-]?\d){6}\b",
    # Australian 13 xx xx
    r"\b13(?:[ .-]?\d){4}\b",
    # International E.164 style numbers with country code: +1 (555) 123-4567, +44 20 7946 0958, etc.
    r"\+\d{1,3}(?:[ .-]?\(?\d{1,4}\)?){1,4}(?:[ .-]?\d{2,4})\b",
]
_PHONE_RE = re.compile("|".join(f"(?:{p})" for p in _PHONE_PATTERNS))

# Street types common in Australian and international addresses
_STREET_TYPES = (
    r"(?:Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Close|Cl|Lane|Ln|"
    r"Place|Pl|Boulevard|Blvd|Parade|Pde|Court|Ct|Way|Terrace|Tce|"
    r"Crescent|Cres|Circuit|Cct|Highway|Hwy|Esplanade|Esp|Grove|Grv|Rise|Walk)"
)

# Australian states
_AUS_STATES = r"(?:NSW|VIC|QLD|WA|SA|TAS|ACT|NT)"

# Residential street addresses and PO Boxes
# Matches: "123 Main St, Richmond VIC 3121", "42 Wallaby Way, Sydney NSW 2000",
# "Unit 4/15 High Street, Melbourne", "Level 2, 742 Evergreen Terrace, Springfield",
# "P.O. Box 789, Melbourne VIC 3001", "15 King St., Sydney NSW 2000"
_ADDRESS_RE = re.compile(
    rf"\b(?:"
    rf"(?:(?:Unit|Apartment|Apt|Suite|Ste|Flat|Lot|Level)\s*\d+[a-zA-Z]?[\s,/]+)?"
    rf"(?:\d{{1,5}}(?:[/-]\d{{1,5}})?\s+)"
    rf"(?:[A-Z][a-zA-Z0-9'.-]+\s+){{1,4}}"
    rf"{_STREET_TYPES}\b\.?"
    rf"(?:[,\s]+[A-Z][a-zA-Z\s]+)?"
    rf"(?:[,\s]+{_AUS_STATES})?"
    rf"(?:\s*\b\d{{4}}\b)?"
    rf"|"
    rf"(?:P\.?O\.?\s+Box\s+\d+)(?:[,\s]+[A-Z][a-zA-Z\s]+)?(?:[,\s]+{_AUS_STATES})?(?:\s*\b\d{{4}}\b)?"
    rf")",
    re.IGNORECASE,
)

# Honorifics + Name: Mr. John Smith, Dr. Banner
_HONORIFIC_NAME_RE = re.compile(
    r"\b(?:Mr\.|Mrs\.|Ms\.|Miss|Dr\.|Prof\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
)

# Salutations: "Dear Frank,", "Hello Alice,"
_SALUTATION_NAME_RE = re.compile(
    r"\b(Dear|Hello|Hi|Hey)\s+([A-Z][a-z]+)\b"
)

# Sign-offs: "Regards, Jane Watson", "Cheers, Bob"
_SIGNOFF_NAME_RE = re.compile(
    r"\b(Regards|Best regards|Cheers|Thanks|Sincerely|Warm regards),?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
    re.IGNORECASE,
)

# Introductory phrase prefix followed by capitalized words
_INTRO_PREFIX = r"(?i:\b(?:my name is|i am|i'm|this is|call me|name:))\s+"
_INTRO_NAME_RE = re.compile(
    rf"({_INTRO_PREFIX})((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*))\b"
)

# Stopwords that should terminate an introductory name match
_NAME_STOPWORDS = {
    "and", "or", "but", "if", "the", "a", "an", "please", "can",
    "could", "would", "will", "i", "to", "for", "from", "with",
    "at", "by", "on", "in", "calling", "here", "just", "looking",
}


def _luhn_checksum(candidate: str) -> bool:
    """Validate a card number string using Luhn algorithm."""
    digits = [int(c) for c in candidate if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = d * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += d
    return checksum % 10 == 0


class PIIScrubber:
    """Deterministic and regex-based PII scrubber."""

    @staticmethod
    def scrub_credit_cards(text: str, placeholder: str = "[CREDIT_CARD]") -> str:
        """Scrub credit card numbers from text."""
        def _replace_cc(m: re.Match[str]) -> str:
            val = m.group(0)
            digits_only = re.sub(r"\D", "", val)
            # If formatted in 4-digit groups or passes Luhn check
            if len(digits_only) in (15, 16) or _luhn_checksum(digits_only):
                return placeholder
            return val

        return _CREDIT_CARD_RE.sub(_replace_cc, text)

    @staticmethod
    def scrub_emails(text: str, placeholder: str = "[EMAIL]") -> str:
        """Scrub email addresses from text."""
        return _EMAIL_RE.sub(placeholder, text)

    @staticmethod
    def scrub_phone_numbers(text: str, placeholder: str = "[PHONE]") -> str:
        """Scrub Australian and international phone numbers from text."""
        return _PHONE_RE.sub(placeholder, text)

    @staticmethod
    def scrub_addresses(text: str, placeholder: str = "[ADDRESS]") -> str:
        """Scrub residential and commercial street addresses from text."""
        return _ADDRESS_RE.sub(placeholder, text)

    @staticmethod
    def scrub_names(
        text: str,
        customer_names: Optional[Sequence[str]] = None,
        placeholder: str = "[NAME]",
    ) -> str:
        """Scrub customer names from text using patterns and optional known names."""
        # 1. Scrub explicit customer names if provided
        if customer_names:
            for name in sorted(customer_names, key=len, reverse=True):
                clean_name = name.strip()
                if len(clean_name) >= 2:
                    pattern = re.compile(rf"\b{re.escape(clean_name)}\b", re.IGNORECASE)
                    text = pattern.sub(placeholder, text)

        # 2. Scrub honorifics (e.g. Dr. Banner -> [NAME])
        text = _HONORIFIC_NAME_RE.sub(placeholder, text)

        # 3. Scrub introductory name phrases (e.g. "My name is John Doe and..." -> "My name is [NAME] and...")
        def _replace_intro(m: re.Match[str]) -> str:
            prefix = m.group(1)
            name_part = m.group(2)
            parts = name_part.split()
            valid_parts: list[str] = []
            for p in parts:
                if p.lower() in _NAME_STOPWORDS:
                    break
                valid_parts.append(p)
            if not valid_parts:
                return m.group(0)
            remaining = " ".join(parts[len(valid_parts):])
            if remaining:
                return f"{prefix}{placeholder} {remaining}"
            return f"{prefix}{placeholder}"

        text = _INTRO_NAME_RE.sub(_replace_intro, text)

        # 4. Scrub salutations (e.g. "Hello Frank," -> "Hello [NAME],")
        def _replace_salutation(m: re.Match[str]) -> str:
            greeting = m.group(1)
            name = m.group(2)
            if name.lower() in _NAME_STOPWORDS:
                return m.group(0)
            return f"{greeting} {placeholder}"

        text = _SALUTATION_NAME_RE.sub(_replace_salutation, text)

        # 5. Scrub sign-offs (e.g. "Regards, Jane Watson" -> "Regards, [NAME]")
        def _replace_signoff(m: re.Match[str]) -> str:
            val = m.group(1)
            return f"{val}, {placeholder}"

        text = _SIGNOFF_NAME_RE.sub(_replace_signoff, text)

        return text

    @classmethod
    def scrub(
        cls,
        text: str,
        customer_names: Optional[Sequence[str]] = None,
    ) -> str:
        """Execute full PII scrubbing pipeline in priority order.

        1. Credit cards (scrubbed first to avoid false-positive phone matches)
        2. Email addresses
        3. Phone numbers (Australian & international)
        4. Street addresses
        5. Customer names
        """
        if not text:
            return ""

        scrubbed = cls.scrub_credit_cards(text)
        scrubbed = cls.scrub_emails(scrubbed)
        scrubbed = cls.scrub_phone_numbers(scrubbed)
        scrubbed = cls.scrub_addresses(scrubbed)
        scrubbed = cls.scrub_names(scrubbed, customer_names=customer_names)
        return scrubbed


def scrub_pii(text: str, customer_names: Optional[Sequence[str]] = None) -> str:
    """Convenience entrypoint to scrub all PII from text."""
    return PIIScrubber.scrub(text, customer_names=customer_names)
