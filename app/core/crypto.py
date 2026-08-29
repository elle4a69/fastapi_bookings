"""Centralized Cryptographic Service for FastAPI Bookings.

Provides versioned envelopes, secure key management, and fail-closed
encryption/decryption for credentials, webhook secrets, and sensitive tokens.
Addresses SEC-001 and SEC-002.
"""

import base64
import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional
from cryptography.fernet import Fernet, InvalidToken

from .config import settings

logger = logging.getLogger(__name__)

# Known insecure fallback keys that must NEVER be used or accepted
FORBIDDEN_FALLBACK_KEYS = {
    "fallback-default-secret-key-change-me",
    "local-public-key-change-me",
}

CURRENT_ENVELOPE_VERSION = "v1"


class CryptoError(Exception):
    """Base exception for all cryptographic errors."""
    pass


class EncryptionKeyMissingError(CryptoError):
    """Raised when no valid encryption key is configured or key is empty."""
    pass


class EncryptionError(CryptoError):
    """Raised when encryption fails."""
    pass


class DecryptionError(CryptoError):
    """Raised when decryption fails (invalid token, wrong key, tampered data)."""
    pass


def _derive_fernet_key(raw_key: str) -> bytes:
    """Derive a 32-byte urlsafe base64-encoded key suitable for Fernet from a string."""
    if not raw_key or not isinstance(raw_key, str):
        raise EncryptionKeyMissingError("Encryption key must be a non-empty string.")
    
    if raw_key in FORBIDDEN_FALLBACK_KEYS:
        raise EncryptionKeyMissingError(
            "Forbidden insecure fallback key detected. Centralized crypto requires a valid application key."
        )

    # Check if raw_key is already a valid 32-byte base64-encoded Fernet key
    try:
        decoded = base64.urlsafe_b64decode(raw_key.encode("utf-8"))
        if len(decoded) == 32:
            return raw_key.encode("utf-8")
    except Exception:
        pass

    # Deterministically derive 32-byte key using SHA-256
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet_cipher(key: Optional[str] = None) -> Fernet:
    """Instantiate a Fernet cipher with the configured or provided key.
    
    Fails closed if key is missing or forbidden.
    """
    if key is None:
        key = getattr(settings, "ENCRYPTION_KEY", None) or getattr(settings, "SECRET_KEY", None)

    if not key or not isinstance(key, str) or not key.strip():
        raise EncryptionKeyMissingError(
            "Application encryption key is not configured or is empty. Encryption fails closed."
        )

    derived_key = _derive_fernet_key(key)
    try:
        return Fernet(derived_key)
    except Exception as exc:
        raise CryptoError("Failed to initialize cryptographic cipher.") from exc


def encrypt_string(plaintext: str, key: Optional[str] = None, version: str = CURRENT_ENVELOPE_VERSION) -> str:
    """Encrypt a plaintext string and wrap in a versioned envelope (e.g. 'v1:<ciphertext>').
    
    Fails closed by raising EncryptionError / EncryptionKeyMissingError.
    """
    if not isinstance(plaintext, str):
        raise EncryptionError("Plaintext must be a string.")
    if plaintext == "":
        return ""

    cipher = get_fernet_cipher(key=key)
    try:
        token_bytes = cipher.encrypt(plaintext.encode("utf-8"))
        token_str = token_bytes.decode("utf-8")
        return f"{version}:{token_str}"
    except CryptoError:
        raise
    except Exception as exc:
        raise EncryptionError("Failed to encrypt data.") from exc


def decrypt_string(envelope: str, key: Optional[str] = None) -> str:
    """Decrypt a versioned ciphertext envelope (e.g. 'v1:<ciphertext>').
    
    Fails closed by raising DecryptionError / EncryptionKeyMissingError.
    """
    if not envelope or not isinstance(envelope, str):
        raise DecryptionError("Ciphertext envelope must be a non-empty string.")

    cipher = get_fernet_cipher(key=key)

    if envelope.startswith(f"{CURRENT_ENVELOPE_VERSION}:"):
        raw_token = envelope[len(CURRENT_ENVELOPE_VERSION) + 1:]
    elif ":" in envelope and envelope.split(":", 1)[0].startswith("v"):
        # Unsupported future envelope version
        unsupported_version = envelope.split(":", 1)[0]
        raise DecryptionError(f"Unsupported ciphertext envelope version: {unsupported_version}")
    else:
        # Legacy unversioned token fallback support during rotation
        raw_token = envelope

    try:
        decrypted_bytes = cipher.decrypt(raw_token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken as exc:
        raise DecryptionError("Decryption failed: invalid or corrupt ciphertext envelope.") from exc
    except CryptoError:
        raise
    except Exception as exc:
        raise DecryptionError("Decryption failed unexpectedly.") from exc


def encrypt_dict(data: Optional[Dict[str, Any]], key: Optional[str] = None) -> Dict[str, str]:
    """Encrypt a dictionary into a serialized envelope dictionary: {'encrypted_data': 'v1:...'}."""
    if not data:
        return {}
    if not isinstance(data, dict):
        raise EncryptionError("Data to encrypt must be a dictionary.")

    serialized = json.dumps(data)
    ciphertext = encrypt_string(serialized, key=key)
    return {"encrypted_data": ciphertext}


def decrypt_dict(encrypted_payload: Optional[Dict[str, Any]], key: Optional[str] = None) -> Dict[str, Any]:
    """Decrypt a dictionary envelope containing 'encrypted_data'."""
    if not encrypted_payload:
        return {}
    if not isinstance(encrypted_payload, dict):
        raise DecryptionError("Encrypted payload must be a dictionary.")
    
    if "encrypted_data" not in encrypted_payload:
        raise DecryptionError("Dictionary missing required 'encrypted_data' envelope key.")

    ciphertext = encrypted_payload["encrypted_data"]
    if not ciphertext or not isinstance(ciphertext, str):
        raise DecryptionError("Invalid 'encrypted_data' field in dictionary payload.")

    decrypted_str = decrypt_string(ciphertext, key=key)
    try:
        return json.loads(decrypted_str)
    except Exception as exc:
        raise DecryptionError("Failed to deserialize decrypted JSON dictionary.") from exc


def constant_time_compare(val1: Optional[str], val2: Optional[str]) -> bool:
    """Perform constant-time string comparison to prevent timing attacks."""
    if val1 is None or val2 is None:
        return False
    if not isinstance(val1, str) or not isinstance(val2, str):
        return False
    return hmac.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))
