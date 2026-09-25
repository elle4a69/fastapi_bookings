"""Tests for deterministic & pattern-based PII scrubber (Track 4)."""

import pytest

from app.services.curation.pii_scrubber import PIIScrubber, scrub_pii


def test_scrub_australian_mobile_phone_numbers():
    """Verify various Australian mobile phone formats are redacted with [PHONE]."""
    samples = [
        "Call me on 0412 345 678 today.",
        "My mobile is 0412345678, thanks.",
        "Reach me at +61 412 345 678 please.",
        "Contact: +61412345678.",
        "Number: 0412-345-678.",
        "Mobile: +61 (0)4 1234 5678.",
    ]
    for s in samples:
        scrubbed = scrub_pii(s)
        assert "[PHONE]" in scrubbed
        assert "0412" not in scrubbed


def test_scrub_australian_landline_and_tollfree_numbers():
    """Verify Australian landlines and 1300/1800/13 numbers are redacted."""
    samples = [
        "Sydney office is (02) 9876 5432.",
        "Melbourne office is 03 9123 4567.",
        "Brisbane office is (07) 3123 4567.",
        "Perth line is +61 2 9876 5432.",
        "Toll-free hotline is 1800 123 456.",
        "Support number is 1300 555 123.",
        "Local rate: 13 14 15.",
    ]
    for s in samples:
        scrubbed = scrub_pii(s)
        assert "[PHONE]" in scrubbed
        assert "9876" not in scrubbed
        assert "1800" not in scrubbed
        assert "1300" not in scrubbed


def test_scrub_international_phone_numbers():
    """Verify international phone numbers are redacted."""
    samples = [
        "US office: +1 (555) 123-4567.",
        "UK hotline: +44 20 7946 0958.",
        "NZ contact: +64 9 123 4567.",
    ]
    for s in samples:
        scrubbed = scrub_pii(s)
        assert "[PHONE]" in scrubbed
        assert "7946" not in scrubbed


def test_scrub_email_addresses():
    """Verify standard and subdomain email addresses are redacted with [EMAIL]."""
    samples = [
        "Send confirmation to alice@example.com please.",
        "Reach me at bob.smith+booking@corp.domain.org.au anytime.",
        "Email support: frank.w_123@sub.domain.co",
    ]
    for s in samples:
        scrubbed = scrub_pii(s)
        assert "[EMAIL]" in scrubbed
        assert "@" not in scrubbed


def test_scrub_credit_cards():
    """Verify credit card numbers (Visa, Mastercard, Amex) are redacted with [CREDIT_CARD]."""
    samples = [
        "Visa: 4532 0151 1283 0366 expires 12/28.",
        "Mastercard: 5425-2334-3010-9821.",
        "Amex: 3782-822463-10005.",
        "Direct digits: 4532015112830366.",
    ]
    for s in samples:
        scrubbed = scrub_pii(s)
        assert "[CREDIT_CARD]" in scrubbed
        assert "4532" not in scrubbed
        assert "5425" not in scrubbed
        assert "3782" not in scrubbed


def test_scrub_residential_street_addresses():
    """Verify Australian and common street addresses are redacted with [ADDRESS]."""
    samples = [
        "I live at 42 Wallaby Way, Sydney NSW 2000.",
        "Send delivery to 123 Main Street, Richmond VIC 3121.",
        "Located at Unit 4/15 High St, Melbourne.",
        "Clinic is at Level 2, 742 Evergreen Terrace, Springfield.",
        "Meet at 10 Downing Street.",
        "Apt 3B, 88 Queen Street, Brisbane QLD 4000.",
    ]
    for s in samples:
        scrubbed = scrub_pii(s)
        assert "[ADDRESS]" in scrubbed
        assert "Wallaby Way" not in scrubbed
        assert "Main Street" not in scrubbed
        assert "High St" not in scrubbed
        assert "Queen Street" not in scrubbed


def test_scrub_customer_names():
    """Verify customer names are redacted with [NAME] across various sentence structures."""
    # 1. Introductions
    s1 = "My name is John Doe and I need to book a haircut."
    assert "My name is [NAME] and I need to book a haircut." == scrub_pii(s1)

    s2 = "I am Sarah Connor, please confirm my booking."
    assert "I am [NAME], please confirm my booking." == scrub_pii(s2)

    s3 = "Call me David please."
    assert "Call me [NAME] please." == scrub_pii(s3)

    # 2. Honorifics
    s4 = "Appointment with Dr. Bruce Banner tomorrow."
    assert "[NAME]" in scrub_pii(s4)
    assert "Bruce Banner" not in scrub_pii(s4)

    # 3. Salutations & Sign-offs
    s5 = "Hello Frank, could you check my appointment?"
    assert "Hello [NAME], could you check my appointment?" == scrub_pii(s5)

    s6 = "Thanks for the help.\nRegards, Jane Watson"
    scrubbed6 = scrub_pii(s6)
    assert "[NAME]" in scrubbed6
    assert "Jane Watson" not in scrubbed6

    # 4. Explicit customer names passed to scrubber
    s7 = "Can Frank Smith have the 2pm slot instead?"
    scrubbed7 = scrub_pii(s7, customer_names=["Frank Smith"])
    assert "Can [NAME] have the 2pm slot instead?" == scrubbed7


def test_scrub_combined_complex_message():
    """Verify a message containing multiple PII elements is completely scrubbed."""
    raw = (
        "Hi Frank, my name is John Doe. My phone number is 0412 345 678 and "
        "my email is john.doe@example.com. Please charge card 4532-0151-1283-0366. "
        "My billing address is 123 Main Street, Richmond VIC 3121. Thanks, John Doe"
    )
    scrubbed = scrub_pii(raw, customer_names=["Frank", "John Doe"])

    assert "0412" not in scrubbed
    assert "john.doe@example.com" not in scrubbed
    assert "4532" not in scrubbed
    assert "123 Main Street" not in scrubbed
    assert "John Doe" not in scrubbed

    assert "[PHONE]" in scrubbed
    assert "[EMAIL]" in scrubbed
    assert "[CREDIT_CARD]" in scrubbed
    assert "[ADDRESS]" in scrubbed
    assert "[NAME]" in scrubbed
