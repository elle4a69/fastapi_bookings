import json
import logging
import secrets
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routers import sms_webhooks
from app.models.sms_account import SmsAccount, SmsCredentialError
from app.models.sms_chatwoot import (
    SmsChatwootBinding,
    SmsChatwootCredentialError,
)
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_receipt import SmsDeliveryReceipt, SmsInboundReceipt
from app.models.provider import Provider
from app.models.tenant import Tenant
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


def _persist_mobilemessage_delivery(
    db_session,
    *,
    credentials: dict,
    message_status: str = "queued",
) -> tuple[SmsAccount, SmsMessage]:
    tenant = Tenant(
        name="Synthetic credential privacy tenant",
        subdomain="synthetic-credential-privacy",
    )
    db_session.add(tenant)
    db_session.flush()
    provider = Provider(
        tenant_id=tenant.id,
        name="Synthetic credential privacy provider",
        active=True,
    )
    db_session.add(provider)
    db_session.flush()
    account = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transport_type="mobilemessage",
        display_name="Synthetic credential privacy line",
        sender_address="61410000001",
        is_enabled=True,
    )
    account.credentials = credentials
    db_session.add(account)
    db_session.flush()
    conversation = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=account.id,
        customer_address="61410000002",
        state="paused",
        ai_enabled=False,
    )
    db_session.add(conversation)
    db_session.flush()
    message = SmsMessage(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=account.id,
        conversation_id=conversation.id,
        body="Synthetic outbound receipt target",
        normalized_body="synthetic outbound receipt target",
        direction="outbound",
        author_type="staff",
        status=message_status,
        provider_message_id="synthetic-provider-message",
    )
    db_session.add(message)
    db_session.commit()
    return account, message


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


@pytest.mark.parametrize("route_suffix", ["", "/delivery"])
@pytest.mark.parametrize(
    "credential_shape",
    ["missing", "blank", "wrong_type", "corrupt_ciphertext"],
)
def test_public_mobilemessage_routes_require_usable_webhook_secret_before_mutation(
    client,
    db_session,
    caplog,
    route_suffix,
    credential_shape,
):
    credentials: dict = {
        "username": "synthetic-user",
        "password": "synthetic-password",
    }
    if credential_shape == "blank":
        credentials["webhook_secret"] = "   "
    elif credential_shape == "wrong_type":
        credentials["webhook_secret"] = 12345
    account, message = _persist_mobilemessage_delivery(
        db_session,
        credentials=credentials,
    )
    if credential_shape == "corrupt_ciphertext":
        account._credentials = {"encrypted_data": CANARY}
        db_session.commit()

    payload = (
        {
            "message_id": "synthetic-provider-message",
            "status": "delivered",
        }
        if route_suffix
        else {
            "message_id": "synthetic-inbound-event",
            "sender": "0410000002",
            "to": "0410000001",
            "message": CANARY,
        }
    )
    with caplog.at_level(logging.ERROR):
        response = client.post(
            f"/api/sms/webhooks/mobilemessage/{account.public_id}{route_suffix}",
            headers={"X-MobileMessage-Signature": CANARY},
            json=payload,
        )

    assert response.status_code == 503
    error_payload = response.json()
    assert error_payload["ok"] is False
    assert error_payload["error"]["message"] == (
        "SMS webhook authentication is unavailable."
    )
    assert CANARY not in response.text
    assert CANARY not in caplog.text
    db_session.refresh(message)
    assert message.status == "queued"
    assert db_session.query(SmsDeliveryReceipt).count() == 0
    assert db_session.query(SmsInboundReceipt).count() == 0
    assert db_session.query(SmsMessage).count() == 1


@pytest.mark.asyncio
async def test_mobilemessage_valid_secret_uses_constant_time_comparison():
    account = _sms_account()
    account.credentials = {"webhook_secret": "synthetic-webhook-secret"}
    request = MagicMock()
    request.headers = {"X-MobileMessage-Signature": "wrong-secret"}
    request.query_params = {}

    with (
        patch(
            "app.services.sms.transports.mobilemessage.secrets.compare_digest",
            wraps=secrets.compare_digest,
        ) as compare_digest,
        pytest.raises(HTTPException) as exc_info,
    ):
        await MobileMessageAdapter().verify_webhook(request, account)

    assert exc_info.value.status_code == 401
    compare_digest.assert_called_once_with(
        "wrong-secret", "synthetic-webhook-secret"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_status",
    [None, "", CANARY, "x" * 33, ["delivered"]],
)
async def test_mobilemessage_rejects_unrecognized_delivery_status_without_reflection(
    provider_status,
    caplog,
):
    request = MagicMock()
    raw_body = json.dumps(
        {
            "message_id": "synthetic-provider-message",
            "status": provider_status,
        }
    ).encode("utf-8")

    async def body():
        return raw_body

    request.body = body
    with caplog.at_level(logging.ERROR), pytest.raises(HTTPException) as exc_info:
        await MobileMessageAdapter().parse_delivery_receipt(request, _sms_account())

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid delivery receipt."
    assert CANARY not in str(exc_info.value.detail)
    assert CANARY not in caplog.text


def test_delivery_receipt_transition_duplicate_and_downgrade_are_private_and_idempotent(
    client,
    db_session,
):
    secret = "synthetic-webhook-secret"
    account, message = _persist_mobilemessage_delivery(
        db_session,
        credentials={"webhook_secret": secret},
    )
    url = f"/api/sms/webhooks/mobilemessage/{account.public_id}/delivery"
    headers = {"X-MobileMessage-Signature": secret}

    sent = client.post(
        url,
        headers=headers,
        json={"message_id": message.provider_message_id, "status": "sent"},
    )
    assert sent.status_code == 200
    assert sent.json() == {"status": "success"}
    db_session.refresh(message)
    assert message.status == "sent"
    assert db_session.query(SmsDeliveryReceipt).count() == 1

    duplicate = client.post(
        url,
        headers=headers,
        json={"message_id": message.provider_message_id, "status": "sent"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json() == {"status": "success"}
    assert db_session.query(SmsDeliveryReceipt).count() == 1

    delivered = client.post(
        url,
        headers=headers,
        json={"message_id": message.provider_message_id, "status": "delivered"},
    )
    assert delivered.status_code == 200
    assert delivered.json() == {"status": "success"}
    db_session.refresh(message)
    assert message.status == "delivered"
    assert db_session.query(SmsDeliveryReceipt).count() == 2

    downgrade = client.post(
        url,
        headers=headers,
        json={"message_id": message.provider_message_id, "status": "sent"},
    )
    assert downgrade.status_code == 200
    assert downgrade.json() == {"status": "success"}
    db_session.refresh(message)
    assert message.status == "delivered"
    assert db_session.query(SmsDeliveryReceipt).count() == 2

    untracked = client.post(
        url,
        headers=headers,
        json={"message_id": "synthetic-untracked", "status": "sent"},
    )
    assert untracked.status_code == 200
    assert untracked.json() == sent.json()


@pytest.mark.parametrize(
    ("terminal_status", "incoming_status"),
    [
        ("delivered", "queued"),
        ("delivered", "failed"),
        ("failed", "queued"),
        ("failed", "sent"),
        ("failed", "delivered"),
    ],
)
def test_delivery_receipt_preserves_terminal_state(
    client,
    db_session,
    terminal_status,
    incoming_status,
):
    secret = "synthetic-webhook-secret"
    account, message = _persist_mobilemessage_delivery(
        db_session,
        credentials={"webhook_secret": secret},
        message_status=terminal_status,
    )
    response = client.post(
        f"/api/sms/webhooks/mobilemessage/{account.public_id}/delivery",
        headers={"X-MobileMessage-Signature": secret},
        json={
            "message_id": message.provider_message_id,
            "status": incoming_status,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    db_session.refresh(message)
    assert message.status == terminal_status
    assert db_session.query(SmsDeliveryReceipt).count() == 0


@pytest.mark.parametrize("provider_status", [CANARY, "x" * 33, 12345])
def test_delivery_receipt_route_rejects_bad_status_without_mutation_or_reflection(
    client,
    db_session,
    caplog,
    provider_status,
):
    secret = "synthetic-webhook-secret"
    account, message = _persist_mobilemessage_delivery(
        db_session,
        credentials={"webhook_secret": secret},
    )
    with caplog.at_level(logging.ERROR):
        response = client.post(
            f"/api/sms/webhooks/mobilemessage/{account.public_id}/delivery",
            headers={"X-MobileMessage-Signature": secret},
            json={
                "message_id": message.provider_message_id,
                "status": provider_status,
            },
        )

    assert response.status_code == 400
    error_payload = response.json()
    assert error_payload["ok"] is False
    assert error_payload["error"]["message"] == "Invalid delivery receipt."
    assert CANARY not in response.text
    assert CANARY not in caplog.text
    db_session.refresh(message)
    assert message.status == "queued"
    assert db_session.query(SmsDeliveryReceipt).count() == 0
