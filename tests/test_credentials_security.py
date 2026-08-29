"""Comprehensive Security & Cryptographic Tests for Work Package E (SEC-001, SEC-002, SEC-003).

Verifies:
1. Centralized Cryptographic Service with versioned envelopes (v1:...).
2. Rejection of known fallback keys and missing keys (fails closed).
3. Plaintext credentials are NEVER saved to database columns.
4. Injected encryption failures store nothing and fail closed.
5. Decryption failures handle errors safely without leaking sensitive information.
6. Chatwoot webhook endpoints strictly reject query-string secrets.
7. Chatwoot webhook endpoints authenticate via constant-time header comparison.
8. Chatwoot API token and webhook secret are masked in API responses.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.crypto import (
    encrypt_string,
    decrypt_string,
    encrypt_dict,
    decrypt_dict,
    get_fernet_cipher,
    constant_time_compare,
    CryptoError,
    EncryptionKeyMissingError,
    EncryptionError,
    DecryptionError,
    FORBIDDEN_FALLBACK_KEYS,
)
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.sms_account import SmsAccount
from app.models.sms_chatwoot import SmsChatwootBinding
from app.api.routers.sms_chatwoot import to_response
from app.schemas.sms_chatwoot import SmsChatwootBindingResponse
from app.core.security import create_access_token


@pytest.fixture(autouse=True)
def setup_encryption_key_for_tests():
    """Ensure a valid non-default ENCRYPTION_KEY is available during tests unless explicitly overridden."""
    original_key = settings.ENCRYPTION_KEY
    settings.ENCRYPTION_KEY = "valid-test-encryption-key-32-chars-long"
    yield
    settings.ENCRYPTION_KEY = original_key


@pytest.fixture
def crypto_test_data(db_session):
    """Fixture providing Tenant, Provider, SmsAccount, and SmsChatwootBinding records."""
    tenant = Tenant(name="Crypto Security Tenant", subdomain="crypto-sec-test")
    db_session.add(tenant)
    db_session.commit()

    provider = Provider(tenant_id=tenant.id, name="Dr. Cryptographer", active=True)
    db_session.add(provider)
    db_session.commit()

    account = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transport_type="simulator",
        display_name="Line Secure",
        sender_address="+61400111222",
        is_enabled=True,
    )
    account.credentials = {"api_username": "secure_user", "api_key": "super_secret_api_key_123"}
    db_session.add(account)
    db_session.commit()

    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        chatwoot_account_id=10,
        chatwoot_inbox_id=88,
        chatwoot_base_url="https://chatwoot.example.com",
        chatwoot_api_token="cw_live_tok_987654321",
        webhook_secret="wh_secret_abcdef123456",
        is_enabled=True,
    )
    db_session.add(binding)
    db_session.commit()

    return {
        "tenant": tenant,
        "provider": provider,
        "account": account,
        "binding": binding,
    }


# =============================================================================
# 1. Centralized Cryptographic Service Tests (SEC-001, SEC-002)
# =============================================================================

class TestCentralizedCryptoService:
    """Unit tests for app.core.crypto."""

    def test_versioned_envelope_string_roundtrip(self):
        """String encryption produces v1: envelope and decrypts accurately."""
        plaintext = "sensitive-api-token-value-2026"
        ciphertext = encrypt_string(plaintext)
        
        assert ciphertext.startswith("v1:")
        assert plaintext not in ciphertext

        decrypted = decrypt_string(ciphertext)
        assert decrypted == plaintext

    def test_versioned_envelope_dict_roundtrip(self):
        """Dictionary encryption serializes to JSON and encapsulates in v1: envelope."""
        creds = {"api_key": "abc123xyz", "account_sid": "AC999999", "tier": 1}
        encrypted = encrypt_dict(creds)

        assert "encrypted_data" in encrypted
        assert encrypted["encrypted_data"].startswith("v1:")
        assert "abc123xyz" not in encrypted["encrypted_data"]

        decrypted = decrypt_dict(encrypted)
        assert decrypted == creds

    def test_empty_values_behave_safely(self):
        """Empty strings and dicts return empty representations safely."""
        assert encrypt_string("") == ""
        assert encrypt_dict({}) == {}
        assert decrypt_dict({}) == {}

    def test_missing_or_empty_key_fails_closed(self):
        """When encryption key is missing or blank, crypto fails closed by raising EncryptionKeyMissingError."""
        for empty_val in ("", None, "   "):
            with patch.object(settings, "ENCRYPTION_KEY", empty_val):
                with pytest.raises(EncryptionKeyMissingError):
                    get_fernet_cipher()

                with pytest.raises(EncryptionKeyMissingError):
                    encrypt_string("plaintext")

                with pytest.raises(EncryptionKeyMissingError):
                    encrypt_dict({"secret": "val"})

    def test_forbidden_fallback_keys_rejected(self):
        """Known fallback keys are strictly rejected and cannot be used."""
        assert "changeme" in FORBIDDEN_FALLBACK_KEYS
        assert "test-secret-key" in FORBIDDEN_FALLBACK_KEYS
        assert "local-secret-key" in FORBIDDEN_FALLBACK_KEYS
        assert "fallback-default-secret-key-change-me" in FORBIDDEN_FALLBACK_KEYS
        assert "local-public-key-change-me" in FORBIDDEN_FALLBACK_KEYS

        for forbidden in FORBIDDEN_FALLBACK_KEYS:
            with patch.object(settings, "ENCRYPTION_KEY", forbidden):
                with pytest.raises(EncryptionKeyMissingError):
                    get_fernet_cipher()

                with pytest.raises(EncryptionKeyMissingError):
                    encrypt_string("secret")

                with pytest.raises(EncryptionKeyMissingError):
                    encrypt_dict({"secret": "val"})

            with pytest.raises(EncryptionKeyMissingError):
                get_fernet_cipher(key=forbidden)

            with pytest.raises(EncryptionKeyMissingError):
                encrypt_string("secret", key=forbidden)

    def test_different_key_cannot_decrypt(self):
        """Data encrypted with key A cannot be decrypted with key B (fails closed)."""
        key_a = "key-alpha-32-chars-long-secret-a"
        key_b = "key-bravo-32-chars-long-secret-b"
        ciphertext = encrypt_string("confidential_payload", key=key_a)

        with pytest.raises(DecryptionError):
            decrypt_string(ciphertext, key=key_b)

    def test_tampered_ciphertext_fails_closed(self):
        """Tampered or corrupted ciphertext envelope raises DecryptionError."""
        valid_ciphertext = encrypt_string("payload")
        corrupt_ciphertext = valid_ciphertext[:-4] + "XXXX"

        with pytest.raises(DecryptionError):
            decrypt_string(corrupt_ciphertext)

    def test_unsupported_future_version_fails_closed(self):
        """Envelopes with unknown future version prefix raise DecryptionError."""
        future_envelope = "v99:gAAAAABf..."
        with pytest.raises(DecryptionError) as exc_info:
            decrypt_string(future_envelope)
        assert "Unsupported ciphertext envelope version" in str(exc_info.value)

    def test_legacy_unversioned_token_rotation_support(self):
        """Legacy Fernet token without version prefix decrypts successfully with matching key."""
        from cryptography.fernet import Fernet
        import base64
        import hashlib

        secret = settings.ENCRYPTION_KEY
        key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
        fernet = Fernet(base64.urlsafe_b64encode(key_bytes))
        legacy_token = fernet.encrypt(b"legacy_unversioned_secret").decode("utf-8")

        # Must not start with v1:
        assert not legacy_token.startswith("v1:")

        # Centralized crypto decrypts legacy unversioned token cleanly
        decrypted = decrypt_string(legacy_token)
        assert decrypted == "legacy_unversioned_secret"

    def test_constant_time_comparison(self):
        """constant_time_compare correctly compares matching and non-matching strings."""
        assert constant_time_compare("secret_token_123", "secret_token_123") is True
        assert constant_time_compare("secret_token_123", "secret_token_456") is False
        assert constant_time_compare("secret_token_123", "") is False
        assert constant_time_compare(None, "secret_token_123") is False
        assert constant_time_compare("secret_token_123", None) is False
        assert constant_time_compare(None, None) is False


# =============================================================================
# 2. Safe Model Setters & Plaintext Elimination (SEC-001, SEC-002)
# =============================================================================

class TestSafeModelSetters:
    """Tests ensuring models never store plaintext and fail closed on encryption errors."""

    def test_sms_account_credentials_stored_encrypted_in_db(self, db_session, crypto_test_data):
        """SmsAccount._credentials column contains versioned encrypted data, never plaintext."""
        account = crypto_test_data["account"]
        raw_db_credentials = account._credentials

        assert isinstance(raw_db_credentials, dict)
        assert "encrypted_data" in raw_db_credentials
        assert raw_db_credentials["encrypted_data"].startswith("v1:")
        
        # Verify plaintext does NOT appear in the database column
        assert "super_secret_api_key_123" not in raw_db_credentials["encrypted_data"]
        assert "secure_user" not in raw_db_credentials["encrypted_data"]

        # Property getter decrypts correctly
        assert account.credentials == {"api_username": "secure_user", "api_key": "super_secret_api_key_123"}

    def test_sms_account_missing_key_fails_closed_never_stores_plaintext(self, db_session, crypto_test_data):
        """When encryption key is missing, setting SmsAccount.credentials raises CryptoError and stores nothing."""
        account = crypto_test_data["account"]
        
        with patch.object(settings, "ENCRYPTION_KEY", ""):
            with pytest.raises(CryptoError):
                account.credentials = {"leak_attempt": "plaintext_value"}

        # Verify old credentials remain or no plaintext was written
        assert "plaintext_value" not in str(account._credentials)

    def test_sms_account_injected_encryption_failure_stores_nothing(self, db_session, crypto_test_data):
        """Injected encryption failure in SmsAccount raises CryptoError and never stores plaintext."""
        account = crypto_test_data["account"]
        original_creds = account._credentials

        with patch("app.models.sms_account.encrypt_dict", side_effect=EncryptionError("Injected failure")):
            with pytest.raises(CryptoError):
                account.credentials = {"critical_token": "cannot_be_stored_plaintext"}

        # Column value must not have changed to plaintext
        assert account._credentials == original_creds

    def test_sms_account_corrupt_credentials_returns_empty_safely(self, crypto_test_data):
        """Corrupted ciphertext in SmsAccount._credentials returns empty dict without throwing or leaking."""
        account = crypto_test_data["account"]
        account._credentials = {"encrypted_data": "v1:tampered_ciphertext_data"}

        # Getter handles error safely
        assert account.credentials == {}

    def test_sms_chatwoot_tokens_stored_encrypted_in_db(self, db_session, crypto_test_data):
        """SmsChatwootBinding columns store v1: ciphertext and never plaintext."""
        binding = crypto_test_data["binding"]

        # Check raw database columns
        assert binding._chatwoot_api_token.startswith("v1:")
        assert binding._webhook_secret.startswith("v1:")

        assert "cw_live_tok_987654321" not in binding._chatwoot_api_token
        assert "wh_secret_abcdef123456" not in binding._webhook_secret

        # Property getters return decrypted plaintext
        assert binding.chatwoot_api_token == "cw_live_tok_987654321"
        assert binding.webhook_secret == "wh_secret_abcdef123456"

    def test_sms_chatwoot_missing_key_fails_closed(self, crypto_test_data):
        """When encryption key is missing, setting Chatwoot tokens raises CryptoError and does not store plaintext."""
        binding = crypto_test_data["binding"]

        with patch.object(settings, "ENCRYPTION_KEY", ""):
            with pytest.raises(CryptoError):
                binding.chatwoot_api_token = "new_token_attempt"

            with pytest.raises(CryptoError):
                binding.webhook_secret = "new_secret_attempt"

        assert "new_token_attempt" not in binding._chatwoot_api_token
        assert "new_secret_attempt" not in binding._webhook_secret

    def test_sms_chatwoot_injected_encryption_failure_stores_nothing(self, crypto_test_data):
        """Injected encryption failure in SmsChatwootBinding raises CryptoError and does not store plaintext."""
        binding = crypto_test_data["binding"]
        original_tok = binding._chatwoot_api_token
        original_sec = binding._webhook_secret

        with patch("app.models.sms_chatwoot.encrypt_string", side_effect=EncryptionError("Injected failure")):
            with pytest.raises(CryptoError):
                binding.chatwoot_api_token = "fail_test_token"

            with pytest.raises(CryptoError):
                binding.webhook_secret = "fail_test_secret"

        assert binding._chatwoot_api_token == original_tok
        assert binding._webhook_secret == original_sec

    def test_sms_chatwoot_corrupt_tokens_return_empty_safely(self, crypto_test_data):
        """Corrupt token in SmsChatwootBinding columns returns empty string without crashing."""
        binding = crypto_test_data["binding"]
        binding._chatwoot_api_token = "v1:corrupt_token_string"
        binding._webhook_secret = "v1:corrupt_secret_string"

        assert binding.chatwoot_api_token == ""
        assert binding.webhook_secret == ""


# =============================================================================
# 3. Chatwoot Webhook Secret Security & Header Authentication (SEC-003)
# =============================================================================

class TestChatwootWebhookSecretSecurity:
    """Tests verifying Chatwoot webhook endpoints and response schemas."""

    def test_to_response_omits_query_string_secret(self, crypto_test_data):
        """to_response helper creates webhook_url without query parameter secret."""
        binding = crypto_test_data["binding"]
        resp: SmsChatwootBindingResponse = to_response(binding)

        assert resp.webhook_url == "http://localhost:8000/api/sms/chatwoot/webhook"
        assert "?" not in resp.webhook_url
        assert "token=" not in resp.webhook_url
        assert "secret=" not in resp.webhook_url

        # Credentials must be masked
        assert resp.chatwoot_api_token == "********"
        assert resp.webhook_secret == "********"

    def test_chatwoot_webhook_rejects_query_string_token(self, client: TestClient, crypto_test_data):
        """Query-string tokens on /api/sms/chatwoot/webhook are strictly rejected with 400 Bad Request."""
        payload = {
            "id": 901,
            "content": "Test rejection of query token",
            "message_type": "incoming",
            "inbox": {"id": 88},
            "conversation": {
                "id": 555,
                "contact": {"id": 12, "phone_number": "+61400111222"}
            }
        }

        # Query param ?token=
        response = client.post(
            "/api/sms/chatwoot/webhook?token=wh_secret_abcdef123456",
            json=payload
        )
        assert response.status_code == 400
        data = response.json()
        error_msg = data.get("error", {}).get("message") or data.get("detail", "")
        assert "Query-string webhook secrets are prohibited" in error_msg

        # Query param ?secret=
        response_secret = client.post(
            "/api/sms/chatwoot/webhook?secret=wh_secret_abcdef123456",
            json=payload
        )
        assert response_secret.status_code == 400
        data_sec = response_secret.json()
        error_msg_sec = data_sec.get("error", {}).get("message") or data_sec.get("detail", "")
        assert "Query-string webhook secrets are prohibited" in error_msg_sec

    def test_chatwoot_webhook_header_authentication_success(self, client: TestClient, crypto_test_data):
        """Webhook succeeds with valid secret in X-Chatwoot-Signature, X-Chatwoot-Webhook-Token, X-Chatwoot-Token, or Bearer auth."""
        valid_secret = "wh_secret_abcdef123456"
        payload = {
            "id": 902,
            "content": "Valid header webhook message",
            "message_type": "incoming",
            "inbox": {"id": 88},
            "conversation": {
                "id": 556,
                "contact": {"id": 13, "phone_number": "+61400111222"}
            }
        }

        # 1. X-Chatwoot-Signature
        resp1 = client.post(
            "/api/sms/chatwoot/webhook",
            json=payload,
            headers={"X-Chatwoot-Signature": valid_secret}
        )
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "success"

        # 2. X-Chatwoot-Webhook-Token
        payload["id"] = 903
        resp2 = client.post(
            "/api/sms/chatwoot/webhook",
            json=payload,
            headers={"X-Chatwoot-Webhook-Token": valid_secret}
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "success"

        # 3. X-Chatwoot-Token
        payload["id"] = 904
        resp3 = client.post(
            "/api/sms/chatwoot/webhook",
            json=payload,
            headers={"X-Chatwoot-Token": valid_secret}
        )
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "success"

        # 4. Authorization: Bearer <secret>
        payload["id"] = 905
        resp4 = client.post(
            "/api/sms/chatwoot/webhook",
            json=payload,
            headers={"Authorization": f"Bearer {valid_secret}"}
        )
        assert resp4.status_code == 200
        assert resp4.json()["status"] == "success"

    def test_chatwoot_webhook_forged_header_secret_fails_constant_time(self, client: TestClient, crypto_test_data):
        """Forged or invalid header secrets are rejected with 401 Unauthorized."""
        payload = {
            "id": 906,
            "content": "Forged attempt",
            "message_type": "incoming",
            "inbox": {"id": 88},
            "conversation": {
                "id": 557,
                "contact": {"id": 14, "phone_number": "+61400111222"}
            }
        }

        response = client.post(
            "/api/sms/chatwoot/webhook",
            json=payload,
            headers={"X-Chatwoot-Signature": "forged_webhook_secret_999"}
        )
        assert response.status_code == 401
        data = response.json()
        error_msg = data.get("error", {}).get("message") or data.get("detail", "")
        assert "Invalid webhook secret" in error_msg

    def test_chatwoot_webhook_missing_header_auth_fails(self, client: TestClient, crypto_test_data):
        """Missing header auth is rejected with 401 Unauthorized."""
        payload = {
            "id": 907,
            "content": "No auth header",
            "message_type": "incoming",
            "inbox": {"id": 88},
            "conversation": {
                "id": 558,
                "contact": {"id": 15, "phone_number": "+61400111222"}
            }
        }

        response = client.post("/api/sms/chatwoot/webhook", json=payload)
        assert response.status_code == 401

    def test_rotate_chatwoot_webhook_secret_endpoint(self, client: TestClient, db_session, crypto_test_data):
        """Rotating secret generates new encrypted secret and masks values in response."""
        tenant = crypto_test_data["tenant"]
        binding = crypto_test_data["binding"]
        old_secret = binding.webhook_secret

        from app.models.user import User
        admin_user = User(tenant_id=tenant.id, login="admin@cryptosec.com", password_hash="pw", role="admin")
        db_session.add(admin_user)
        db_session.commit()

        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        headers = {
            "X-Tenant": tenant.subdomain,
            "X-Token": token,
        }

        response = client.post(
            f"/api/admin/sms/chatwoot/bindings/{binding.id}/rotate-secret",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["webhook_secret"] == "********"
        assert data["chatwoot_api_token"] == "********"
        assert data["webhook_url"] == "http://testserver/api/sms/chatwoot/webhook"

        db_session.refresh(binding)
        new_secret = binding.webhook_secret
        assert new_secret != old_secret
        assert binding._webhook_secret.startswith("v1:")
        assert new_secret not in binding._webhook_secret
