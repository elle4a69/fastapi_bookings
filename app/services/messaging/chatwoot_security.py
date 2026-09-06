"""Fail-closed Chatwoot signing-secret storage and webhook authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken

from ...core.config import settings


SIGNATURE_PATTERN = re.compile(r"\Asha256=([0-9a-f]{64})\Z")
REPLAY_WINDOW_SECONDS = 300
_SIGNING_SECRET_KEY_CONTEXT = b"fastapi-bookings:chatwoot-signing-secret:v1\x00"
_API_TOKEN_KEY_CONTEXT = b"fastapi-bookings:chatwoot-api-token:v1\x00"
_DEFAULT_KEYS = frozenset(
    {"changeme", "change-me", "secret", "default", "development-secret"}
)


class SigningSecretUnavailable(RuntimeError):
    """Raised without propagating sensitive cryptographic details."""


class ApiTokenUnavailable(RuntimeError):
    """Raised without propagating sensitive cryptographic details."""


def _fernet(context: bytes) -> Fernet:
    secret = settings.SECRET_KEY
    if not isinstance(secret, str) or not secret:
        raise SigningSecretUnavailable("signing secret storage unavailable")
    if settings.APP_ENV.lower() == "production" and (
        len(secret) < 32 or secret.lower() in _DEFAULT_KEYS
    ):
        raise SigningSecretUnavailable("signing secret storage unavailable")
    digest = hashlib.sha256(context + secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_signing_secret(secret: str) -> str:
    try:
        return _fernet(_SIGNING_SECRET_KEY_CONTEXT).encrypt(secret.encode("utf-8")).decode("ascii")
    except SigningSecretUnavailable:
        raise
    except Exception as exc:
        raise SigningSecretUnavailable("signing secret storage unavailable") from exc


def decrypt_signing_secret(ciphertext: str | None) -> str:
    if not ciphertext:
        raise SigningSecretUnavailable("signing secret storage unavailable")
    try:
        return _fernet(_SIGNING_SECRET_KEY_CONTEXT).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError, TypeError) as exc:
        raise SigningSecretUnavailable("signing secret storage unavailable") from exc


def encrypt_api_token(token: str) -> str:
    """Encrypt the write-only outbound API credential in its own domain."""
    try:
        return _fernet(_API_TOKEN_KEY_CONTEXT).encrypt(token.encode("utf-8")).decode("ascii")
    except SigningSecretUnavailable as exc:
        raise ApiTokenUnavailable("API token storage unavailable") from exc
    except Exception as exc:
        raise ApiTokenUnavailable("API token storage unavailable") from exc


def decrypt_api_token(ciphertext: str | None) -> str:
    if not ciphertext:
        raise ApiTokenUnavailable("API token storage unavailable")
    try:
        return _fernet(_API_TOKEN_KEY_CONTEXT).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except SigningSecretUnavailable as exc:
        raise ApiTokenUnavailable("API token storage unavailable") from exc
    except (InvalidToken, UnicodeError, ValueError, TypeError) as exc:
        raise ApiTokenUnavailable("API token storage unavailable") from exc


def parse_timestamp(timestamp_header: str | None) -> tuple[int, datetime]:
    if timestamp_header is None or not timestamp_header.isascii():
        raise ValueError("invalid timestamp")
    if not timestamp_header.isdigit() or len(timestamp_header) > 20:
        raise ValueError("invalid timestamp")
    seconds = int(timestamp_header)
    try:
        timestamp = datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("invalid timestamp") from exc
    return seconds, timestamp


def timestamp_is_fresh(timestamp_seconds: int, now: datetime) -> bool:
    return abs(int(now.timestamp()) - timestamp_seconds) <= REPLAY_WINDOW_SECONDS


def signature_is_well_formed(signature_header: str | None) -> bool:
    return bool(signature_header and SIGNATURE_PATTERN.fullmatch(signature_header))


def verify_signature(
    *, secret: str, timestamp_header: str, raw_body: bytes, signature_header: str
) -> bool:
    match = SIGNATURE_PATTERN.fullmatch(signature_header)
    if match is None:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        timestamp_header.encode("ascii") + b"." + raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, match.group(1))
