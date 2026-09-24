import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routers import sms_webhooks
from app.models.sms_account import SmsAccount, SmsCredentialError
from app.models.sms_chatwoot import (
    SmsChatwootBinding,
    SmsChatwootCredentialError,
)
from app.services.sms.transports.base import OutboundSmsCommand
from app.services.sms.transports.mobilemessage import MobileMessageAdapter


CANARY = "SYNTHETIC_PRIVATE_FAILURE_CANARY"


def _sms_account() -> SmsAccount:
    return SmsAccount(
        tenant_id=1,
        provider_id=1,
        transport_type="mobilemessage",
        display_name="Synthetic privacy line",
        sender_address="61410000001",
        is_enabled=True,
    )


def _chatwoot_binding() -> SmsChatwootBinding:
    return SmsChatwootBinding(
        tenant_id=1,
        provider_id=1,
        chatwoot_account_id=1,
        chatwoot_inbox_id=1,
        chatwoot_base_url="https://chatwoot.invalid",
        chatwoot_api_token="synthetic-token",
        webhook_secret="synthetic-secret",
        is_enabled=True,
    )


def test_sms_credential_encryption_failure_preserves_existing_ciphertext(caplog):
    account = _sms_account()
    account.credentials = {"password": "synthetic-old-secret"}
    stored = dict(account._credentials)

    with (
        patch(
            "app.models.sms_account._sms_credential_cipher",
            side_effect=RuntimeError(CANARY),
        ),
        caplog.at_level(logging.ERROR),
        pytest.raises(SmsCredentialError, match="SMS credential encryption failed"),
    ):
        account.credentials = {"password": CANARY}

    assert account._credentials == stored
    assert CANARY not in caplog.text


def test_sms_plaintext_and_invalid_ciphertext_fail_with_typed_private_error(caplog):
    account = _sms_account()
    with caplog.at_level(logging.ERROR):
        account._credentials = {"password": CANARY}
        with pytest.raises(SmsCredentialError, match="storage is invalid"):
            _ = account.credentials
        account._credentials = {"encrypted_data": CANARY}
        with pytest.raises(SmsCredentialError, match="decryption failed"):
            _ = account.credentials

    assert CANARY not in caplog.text


@pytest.mark.parametrize("field", ["chatwoot_api_token", "webhook_secret"])
def test_chatwoot_encryption_failure_preserves_existing_ciphertext(field, caplog):
    binding = _chatwoot_binding()
    storage_name = f"_{field}"
    stored = getattr(binding, storage_name)

    with (
        patch(
            "app.models.sms_chatwoot._chatwoot_token_cipher",
            side_effect=RuntimeError(CANARY),
        ),
        caplog.at_level(logging.ERROR),
        pytest.raises(SmsChatwootCredentialError, match="encryption failed"),
    ):
        setattr(binding, field, CANARY)

    assert getattr(binding, storage_name) == stored
    assert CANARY not in caplog.text


@pytest.mark.parametrize(
    ("field", "storage_name"),
    [
        ("chatwoot_api_token", "_chatwoot_api_token"),
        ("webhook_secret", "_webhook_secret"),
    ],
)
def test_chatwoot_plaintext_fails_with_typed_private_error(
    field, storage_name, caplog
):
    binding = _chatwoot_binding()
    setattr(binding, storage_name, CANARY)

    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(SmsChatwootCredentialError, match="decryption failed"),
    ):
        getattr(binding, field)

    assert CANARY not in caplog.text


@pytest.mark.asyncio
async def test_mobilemessage_unusable_credentials_fail_closed_without_canary(caplog):
    account = _sms_account()
    account._credentials = {"password": CANARY}
    adapter = MobileMessageAdapter()

    with caplog.at_level(logging.ERROR):
        result = await adapter.send(
            account,
            OutboundSmsCommand(to="61410000002", body="Synthetic test message"),
        )

    assert result.status == "error"
    assert result.error_code == "CREDENTIALS_UNAVAILABLE"
    assert CANARY not in result.model_dump_json()
    assert CANARY not in caplog.text


@pytest.mark.asyncio
async def test_mobilemessage_provider_failure_is_structural_only(caplog):
    account = _sms_account()
    account.credentials = {
        "username": "synthetic-user",
        "password": "synthetic-password",
    }
    adapter = MobileMessageAdapter()

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            raise RuntimeError(CANARY)

    with (
        patch(
            "app.services.sms.transports.mobilemessage.httpx.AsyncClient",
            return_value=FailingClient(),
        ),
        caplog.at_level(logging.ERROR),
    ):
        result = await adapter.send(
            account,
            OutboundSmsCommand(to="61410000002", body="Synthetic test message"),
        )

    assert result.status == "error"
    assert result.error_code == "CONNECTION_ERROR"
    assert result.error_message == "Provider delivery request failed."
    assert result.raw_response is None
    assert CANARY not in result.model_dump_json()
    assert CANARY not in caplog.text


@pytest.mark.asyncio
async def test_mobilemessage_http_failure_does_not_return_provider_body():
    account = _sms_account()
    account.credentials = {
        "username": "synthetic-user",
        "password": "synthetic-password",
    }
    adapter = MobileMessageAdapter()

    class FailedResponse:
        status_code = 503
        text = CANARY

    class FailedHttpClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FailedResponse()

    with patch(
        "app.services.sms.transports.mobilemessage.httpx.AsyncClient",
        return_value=FailedHttpClient(),
    ):
        result = await adapter.send(
            account,
            OutboundSmsCommand(to="61410000002", body="Synthetic test message"),
        )

    assert result.status == "error"
    assert result.error_code == "PROVIDER_HTTP_ERROR"
    assert result.error_message == "Provider delivery request failed."
    assert result.raw_response is None
    assert CANARY not in result.model_dump_json()


@pytest.mark.asyncio
async def test_mobilemessage_receipt_error_fields_are_not_retained():
    adapter = MobileMessageAdapter()
    request = MagicMock()
    raw_body = json.dumps(
        {
            "message_id": "synthetic-provider-message",
            "status": "failed",
            "error_code": CANARY,
            "error_message": CANARY,
        }
    ).encode("utf-8")

    async def body():
        return raw_body

    request.body = body
    update = await adapter.parse_delivery_receipt(request, _sms_account())

    assert update.error_code == "PROVIDER_REPORTED_FAILURE"
    assert update.error_message == "Provider reported a delivery failure."
    assert update.raw_payload is None
    assert CANARY not in update.model_dump_json()


@pytest.mark.asyncio
async def test_inbound_webhook_exception_is_non_reflecting_and_structural(caplog):
    async def fail_processing(**_kwargs):
        raise RuntimeError(CANARY)

    with (
        patch.object(sms_webhooks, "process_inbound_webhook", fail_processing),
        caplog.at_level(logging.ERROR),
        pytest.raises(HTTPException) as exc_info,
    ):
        await sms_webhooks.inbound_webhook(
            transport_type=f"transport-{CANARY}",
            account_public_id=f"account-{CANARY}",
            request=MagicMock(),
            db=MagicMock(),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Error processing inbound webhook."
    assert CANARY not in caplog.text
    assert CANARY not in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_missing_delivery_account_log_does_not_reflect_route_values(caplog):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with caplog.at_level(logging.WARNING), pytest.raises(HTTPException) as exc_info:
        await sms_webhooks.delivery_receipt_webhook(
            transport_type=f"transport-{CANARY}",
            account_public_id=f"account-{CANARY}",
            request=MagicMock(),
            db=db,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "SMS account not found or disabled."
    assert CANARY not in caplog.text
    assert CANARY not in str(exc_info.value.detail)
