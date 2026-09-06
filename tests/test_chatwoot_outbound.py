"""Contract-level, no-network checks for Package D outbound primitives."""

from pathlib import Path
from uuid import UUID

import pytest

from app.services.messaging.contracts import (
    InvalidChatwootPayload,
    parse_chatwoot_outbound_message,
    parse_outbound_correlation_id,
)
from app.services.messaging.chatwoot_security import (
    ApiTokenUnavailable,
    SigningSecretUnavailable,
    decrypt_api_token,
    decrypt_signing_secret,
    encrypt_api_token,
    encrypt_signing_secret,
)


MARKER = UUID("12345678-1234-4234-9234-123456789abc")


def _message(*, marker=str(MARKER)):
    return {
        "id": 41,
        "content": "Synthetic contract message",
        "message_type": "outgoing",
        "content_type": "text",
        "private": False,
        "account": {"id": 11},
        "inbox": {"id": 12},
        "conversation": {"id": 13},
        "sender": {"id": 14, "type": "User"},
        "content_attributes": {
            "fastapi_bookings": {"outbound_correlation_id": marker}
        },
    }


def test_415_contract_fixture_parses_only_the_namespaced_opaque_uuid():
    parsed = parse_chatwoot_outbound_message(_message())
    assert parsed.outbound_correlation_id == MARKER
    assert parsed.message_id == 41
    assert parse_outbound_correlation_id({"source_id": str(MARKER)}) is None
    assert parse_outbound_correlation_id(
        {"fastapi_bookings": {"outbound_correlation_id": str(MARKER), "extra": "x"}}
    ) is None
    with pytest.raises(InvalidChatwootPayload):
        parse_chatwoot_outbound_message({**_message(), "sender": {"type": "User"}})


def test_api_token_and_signing_secret_have_domain_separated_ciphertexts():
    value = "synthetic-shared-secret-material-000001"
    token_ciphertext = encrypt_api_token(value)
    signing_ciphertext = encrypt_signing_secret(value)
    assert token_ciphertext != signing_ciphertext
    assert decrypt_api_token(token_ciphertext) == value
    assert decrypt_signing_secret(signing_ciphertext) == value
    with pytest.raises(ApiTokenUnavailable):
        decrypt_api_token(signing_ciphertext)
    with pytest.raises(SigningSecretUnavailable):
        decrypt_signing_secret(token_ciphertext)


def test_415_contract_document_requires_pinned_version_change_rerun():
    document = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "CHATWOOT_OUTBOUND_CONTRACT_4_15_1.md"
    ).read_text(encoding="utf-8").lower()
    assert "4.15.1" in document
    assert "pin the" in document
    assert "version change requires" in document
    assert "fixture run" in document
    assert "source_id" in document
