"""Synthetic no-network tests for authenticated Chatwoot webhook ingestion."""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from starlette.requests import Request

from app.models.client import Client
from app.models.provider import Provider
from app.models.sms_chatwoot import (
    ChatwootConnection,
    ChatwootWebhookReceipt,
    SmsChatwootBinding,
)
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_outbox import SmsAiJob, SmsConversationEvent, SmsOutboundJob
from app.models.tenant import Tenant
from app.services.messaging.chatwoot_security import encrypt_signing_secret


FIXED_NOW = datetime(2026, 9, 6, 1, 2, 3, tzinfo=timezone.utc)
FIXED_TIMESTAMP = str(int(FIXED_NOW.timestamp()))
SECRET = "synthetic-chatwoot-signing-secret-value-000001"


def _boundary(db_session, suffix="primary", *, inbox_id=7002, account_id=7001):
    tenant = Tenant(
        name=f"Synthetic Ingress {suffix}", subdomain=f"ingress-{suffix}"
    )
    db_session.add(tenant)
    db_session.flush()
    provider = Provider(
        tenant_id=tenant.id, name=f"Synthetic Provider {suffix}", active=True
    )
    db_session.add(provider)
    db_session.flush()
    connection = ChatwootConnection(
        tenant_id=tenant.id,
        instance_origin=f"https://{suffix}.example.test",
        chatwoot_account_id=account_id,
        _signing_secret_ciphertext=encrypt_signing_secret(SECRET),
        enabled=True,
    )
    db_session.add(connection)
    db_session.flush()
    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        connection_id=connection.id,
        chatwoot_inbox_id=inbox_id,
        channel="web_widget",
        ingress_enabled=True,
        is_enabled=False,
    )
    db_session.add(binding)
    db_session.commit()
    return tenant, provider, connection, binding


def _payload(
    *,
    account_id=7001,
    inbox_id=7002,
    conversation_id=7003,
    message_id=7004,
    event="message_created",
    message_type="incoming",
    content_type="text",
    sender_type="Contact",
    private=False,
    content="Synthetic customer content",
    channel="Channel::WebWidget",
    attachments=None,
):
    result = {
        "event": event,
        "id": message_id,
        "content": content,
        "content_type": content_type,
        "message_type": message_type,
        "private": private,
        "created_at": int(FIXED_NOW.timestamp()) - 1,
        "account": {"id": account_id, "name": "ignored account name"},
        "inbox": {"id": inbox_id, "channel_type": channel},
        "conversation": {
            "id": conversation_id,
            "contact": {
                "id": 999001,
                "name": "Ignored Person",
                "email": "ignored@example.test",
                "phone_number": "+61400000000",
            },
        },
        "sender": {
            "id": 999001,
            "type": sender_type,
            "name": "Ignored Person",
            "email": "ignored@example.test",
            "phone_number": "+61400000000",
        },
        "source_id": "ignored-source",
        "external_source_ids": {"ignored": "value"},
    }
    if attachments is not None:
        result["attachments"] = attachments
    return result


def _raw(payload):
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()


def _headers(raw_body, *, secret=SECRET, timestamp=FIXED_TIMESTAMP, delivery=None):
    digest = hmac.new(
        secret.encode(), timestamp.encode() + b"." + raw_body, hashlib.sha256
    ).hexdigest()
    return {
        "X-Chatwoot-Signature": f"sha256={digest}",
        "X-Chatwoot-Timestamp": timestamp,
        "X-Chatwoot-Delivery": str(delivery or uuid4()),
        "Content-Type": "application/json",
    }


def _post(client, connection, payload, **header_overrides):
    raw_body = _raw(payload)
    headers = _headers(raw_body)
    headers.update(header_overrides)
    return client.post(
        f"/api/messaging/chatwoot/webhooks/{connection.public_id}",
        content=raw_body,
        headers=headers,
    )


@pytest.fixture(autouse=True)
def fixed_webhook_clock(monkeypatch):
    monkeypatch.setattr(
        "app.api.routers.chatwoot_webhooks._utc_now", lambda: FIXED_NOW
    )


def test_signed_created_message_projects_without_automation_or_identity_matching(
    client, db_session
):
    tenant, _, connection, binding = _boundary(db_session)
    db_session.add(
        Client(
            tenant_id=tenant.id,
            name="Synthetic Similar Person",
            phone="+61400000000",
            email="similar@example.test",
        )
    )
    db_session.commit()

    response = _post(client, connection, _payload())
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    conversation = db_session.query(SmsConversation).one()
    message = db_session.query(SmsMessage).one()
    receipt = db_session.query(ChatwootWebhookReceipt).one()
    assert conversation.chatwoot_binding_id == binding.id
    assert conversation.client_id is None
    assert conversation.state == "paused"
    assert conversation.customer_address == (
        f"chatwoot-binding-{binding.id}-conversation-7003"
    )
    assert message.direction == "inbound"
    assert message.author_type == "customer"
    assert message.body == "Synthetic customer content"
    assert message.chatwoot_sender_reference == "999001"
    assert receipt.outcome == "projected"
    assert db_session.query(SmsAiJob).count() == 0
    assert db_session.query(SmsOutboundJob).count() == 0
    event = db_session.query(SmsConversationEvent).one()
    assert event.type == "chatwoot_operator_review"
    assert event.meta == {
        "reason_code": "automation_disabled",
        "identity_code": "untrusted_client_identity",
    }


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({}, 401),
        ({"X-Chatwoot-Signature": "sha256=not-hex"}, 401),
        ({"X-Chatwoot-Timestamp": "not-a-time"}, 401),
        ({"X-Chatwoot-Delivery": ""}, 401),
    ],
)
def test_missing_or_malformed_auth_is_generic_and_writes_nothing(
    client, db_session, headers, expected
):
    _, _, connection, _ = _boundary(db_session, suffix=str(uuid4())[:8])
    response = client.post(
        f"/api/messaging/chatwoot/webhooks/{connection.public_id}",
        content=b"not-json-sensitive-body",
        headers=headers,
    )
    assert response.status_code == expected
    assert response.json()["error"]["message"] == "Webhook authentication failed."
    assert db_session.query(ChatwootWebhookReceipt).count() == 0
    assert db_session.query(SmsMessage).count() == 0


@pytest.mark.parametrize("offset", [-301, 301])
def test_stale_and_future_timestamps_are_rejected(client, db_session, offset):
    _, _, connection, _ = _boundary(db_session, suffix=f"time-{offset}")
    raw_body = _raw(_payload())
    timestamp = str(int(FIXED_NOW.timestamp()) + offset)
    response = client.post(
        f"/api/messaging/chatwoot/webhooks/{connection.public_id}",
        content=raw_body,
        headers=_headers(raw_body, timestamp=timestamp),
    )
    assert response.status_code == 401
    assert db_session.query(ChatwootWebhookReceipt).count() == 0


def test_signature_uses_exact_raw_body_and_tampering_is_pre_parse(
    client, db_session
):
    _, _, connection, _ = _boundary(db_session, suffix="raw")
    signed = b'{"event":"message_created", "account":{"id":7001}}'
    tampered = signed.replace(b" ", b"")
    response = client.post(
        f"/api/messaging/chatwoot/webhooks/{connection.public_id}",
        content=tampered,
        headers=_headers(signed),
    )
    assert response.status_code == 401
    assert db_session.query(ChatwootWebhookReceipt).count() == 0


def test_unknown_disabled_and_decrypt_failure_have_fixed_responses(
    client, db_session
):
    _, _, connection, _ = _boundary(db_session, suffix="availability")
    payload = _payload()
    raw_body = _raw(payload)
    headers = _headers(raw_body)
    unknown = client.post(
        f"/api/messaging/chatwoot/webhooks/{uuid4()}",
        content=raw_body,
        headers=headers,
    )
    assert unknown.status_code == 401
    connection.enabled = False
    db_session.commit()
    disabled = client.post(
        f"/api/messaging/chatwoot/webhooks/{connection.public_id}",
        content=raw_body,
        headers=headers,
    )
    assert disabled.status_code == 401
    connection.enabled = True
    connection._signing_secret_ciphertext = "invalid-ciphertext"
    db_session.commit()
    unavailable = client.post(
        f"/api/messaging/chatwoot/webhooks/{connection.public_id}",
        content=raw_body,
        headers=headers,
    )
    assert unavailable.status_code == 401
    assert (
        unavailable.json()["error"]["message"]
        == "Webhook authentication failed."
    )
    assert db_session.query(ChatwootWebhookReceipt).count() == 0


def test_authenticated_invalid_delivery_payload_and_account_mismatch(
    client, db_session
):
    _, _, connection, _ = _boundary(db_session, suffix="invalid")
    payload = _payload()
    raw_body = _raw(payload)
    invalid_delivery = client.post(
        f"/api/messaging/chatwoot/webhooks/{connection.public_id}",
        content=raw_body,
        headers=_headers(raw_body, delivery="not-a-uuid"),
    )
    assert invalid_delivery.status_code == 400

    invalid_json = b"{authenticated-but-invalid-json"
    invalid_payload = client.post(
        f"/api/messaging/chatwoot/webhooks/{connection.public_id}",
        content=invalid_json,
        headers=_headers(invalid_json),
    )
    assert invalid_payload.status_code == 400
    mismatch = _post(client, connection, _payload(account_id=999999))
    assert mismatch.status_code == 403
    assert db_session.query(ChatwootWebhookReceipt).count() == 0


@pytest.mark.parametrize(
    "conversation_overrides",
    [{"inbox_id": 888888}, {"account_id": 888888}],
)
def test_conflicting_nested_identifiers_are_rejected(
    client, db_session, conversation_overrides
):
    _, _, connection, _ = _boundary(
        db_session, suffix=f"mismatch-{uuid4().hex[:8]}"
    )
    payload = _payload()
    payload["conversation"].update(conversation_overrides)
    response = _post(client, connection, payload)
    assert response.status_code == 400
    assert db_session.query(ChatwootWebhookReceipt).count() == 0
    assert db_session.query(SmsMessage).count() == 0


def test_unmapped_disabled_inbox_and_channel_mismatch_are_receipt_only(
    client, db_session
):
    _, _, connection, binding = _boundary(db_session, suffix="mapping")
    assert _post(client, connection, _payload(inbox_id=88001)).status_code == 202
    binding.ingress_enabled = False
    db_session.commit()
    assert (
        _post(client, connection, _payload(message_id=7005)).status_code == 202
    )
    binding.ingress_enabled = True
    db_session.commit()
    assert (
        _post(
            client,
            connection,
            _payload(message_id=7006, channel="Channel::Sms"),
        ).status_code
        == 202
    )
    assert db_session.query(ChatwootWebhookReceipt).count() == 3
    assert db_session.query(SmsMessage).count() == 0


def test_delivery_and_message_deduplication_are_scoped_and_idempotent(
    client, db_session
):
    _, _, connection, _ = _boundary(db_session, suffix="dedupe")
    payload = _payload()
    raw_body = _raw(payload)
    delivery = UUID("12345678-1234-4234-9234-123456789abc")
    headers = _headers(raw_body, delivery=delivery)
    path = f"/api/messaging/chatwoot/webhooks/{connection.public_id}"
    assert client.post(path, content=raw_body, headers=headers).status_code == 202
    assert client.post(path, content=raw_body, headers=headers).status_code == 202
    assert _post(client, connection, payload).status_code == 202
    assert db_session.query(SmsMessage).count() == 1
    assert db_session.query(ChatwootWebhookReceipt).count() == 2
    assert {
        item.outcome for item in db_session.query(ChatwootWebhookReceipt).all()
    } == {"projected", "duplicate_message"}


def test_message_update_reconciles_projection_without_side_effects(
    client, db_session
):
    _, _, connection, _ = _boundary(db_session, suffix="update")
    assert _post(client, connection, _payload()).status_code == 202
    conversation = db_session.query(SmsConversation).one()
    original_state = conversation.state
    updated = _payload(event="message_updated", content="Synthetic revised content")
    assert _post(client, connection, updated).status_code == 202
    message = db_session.query(SmsMessage).one()
    db_session.refresh(conversation)
    assert message.body == "Synthetic revised content"
    assert conversation.state == original_state
    assert db_session.query(SmsAiJob).count() == 0
    assert db_session.query(SmsOutboundJob).count() == 0
    # The single event came from the initial created projection. Updates only
    # reconcile the durable message and never re-run policy processing.
    assert db_session.query(SmsConversationEvent).count() == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"private": True},
        {"message_type": "template", "sender_type": "User"},
        {"content_type": "form"},
        {"message_type": "activity", "sender_type": "User"},
    ],
)
def test_private_template_unsupported_and_activity_never_store_content_or_automate(
    client, db_session, changes
):
    suffix = f"classification-{uuid4().hex[:8]}"
    _, _, connection, _ = _boundary(db_session, suffix=suffix)
    payload = _payload(**changes)
    assert _post(client, connection, payload).status_code == 202
    if changes.get("message_type") == "activity":
        assert db_session.query(SmsMessage).count() == 0
    else:
        message = db_session.query(SmsMessage).one()
        assert message.body == ""
    assert db_session.query(SmsAiJob).count() == 0
    assert db_session.query(SmsOutboundJob).count() == 0
    expected_events = 0 if changes.get("message_type") == "activity" else 1
    assert db_session.query(SmsConversationEvent).count() == expected_events


def test_sender_classification_and_attachment_allowlist(client, db_session):
    _, _, connection, _ = _boundary(db_session, suffix="classification")
    attachments = [
        {
            "id": 44,
            "file_type": "image",
            "content_type": "image/png",
            "file_size": 123,
            "data_url": "https://secret.example.test/customer-file",
            "thumb_url": "https://secret.example.test/thumb",
            "coordinates": {"lat": -33.8, "long": 151.2},
            "audio_transcript": "sensitive transcript",
        }
    ]
    staff = _payload(
        message_type="outgoing",
        sender_type="User",
        attachments=attachments,
    )
    assert _post(client, connection, staff).status_code == 202
    message = db_session.query(SmsMessage).one()
    assert message.direction == "outbound"
    assert message.author_type == "staff"
    assert message.chatwoot_attachment_metadata == [
        {
            "id": "44",
            "file_type": "image",
            "content_type": "image/png",
            "file_size": 123,
        }
    ]
    serialized = json.dumps(message.chatwoot_attachment_metadata)
    assert "https://" not in serialized
    assert "transcript" not in serialized
    assert "coordinates" not in serialized

    agent_bot = _payload(
        message_id=7005,
        message_type="outgoing",
        sender_type="AgentBot",
    )
    assert _post(client, connection, agent_bot).status_code == 202
    bot = db_session.query(SmsMessage).filter_by(chatwoot_message_id=7005).one()
    assert bot.author_type == "external_bot"

    unknown = _payload(
        message_id=7006,
        message_type="incoming",
        sender_type="UnknownActor",
    )
    assert _post(client, connection, unknown).status_code == 202
    unknown_message = (
        db_session.query(SmsMessage).filter_by(chatwoot_message_id=7006).one()
    )
    assert unknown_message.direction == "system"
    assert unknown_message.author_type == "system"
    assert unknown_message.body == ""


def test_same_remote_ids_are_isolated_by_trusted_binding(client, db_session):
    _, _, connection_a, binding_a = _boundary(
        db_session, suffix="tenant-a", inbox_id=9002, account_id=9001
    )
    _, _, connection_b, binding_b = _boundary(
        db_session, suffix="tenant-b", inbox_id=9002, account_id=9001
    )
    payload = _payload(
        account_id=9001,
        inbox_id=9002,
        conversation_id=9003,
        message_id=9004,
    )
    assert _post(client, connection_a, payload).status_code == 202
    assert _post(client, connection_b, payload).status_code == 202
    messages = db_session.query(SmsMessage).order_by(SmsMessage.id).all()
    assert len(messages) == 2
    assert {message.chatwoot_binding_id for message in messages} == {
        binding_a.id,
        binding_b.id,
    }


def test_unsupported_event_is_structural_receipt_only(client, db_session):
    _, _, connection, _ = _boundary(db_session, suffix="unsupported")
    payload = {
        "event": "conversation_updated",
        "account": {"id": 7001},
        "customer": {"email": "ignored@example.test"},
    }
    assert _post(client, connection, payload).status_code == 202
    receipt = db_session.query(ChatwootWebhookReceipt).one()
    assert receipt.outcome == "unsupported_event"
    assert db_session.query(SmsMessage).count() == 0


def test_response_and_logs_do_not_disclose_webhook_data(
    client, db_session, caplog
):
    _, _, connection, _ = _boundary(db_session, suffix="privacy")
    sensitive_content = "SYNTHETIC-CONTENT-MUST-NOT-LEAK"
    sensitive_url = "https://secret.example.test/private"
    payload = _payload(
        content=sensitive_content,
        attachments=[{"id": 1, "data_url": sensitive_url}],
    )
    response = _post(client, connection, payload)
    combined = response.text + caplog.text
    for forbidden in (
        SECRET,
        sensitive_content,
        sensitive_url,
        "7004",
    ):
        assert forbidden not in combined


def test_body_limit_precheck_and_stream_limit(client, db_session):
    _, _, connection, _ = _boundary(db_session, suffix="size")
    oversized = b"x" * (1024 * 1024 + 1)
    response = client.post(
        f"/api/messaging/chatwoot/webhooks/{connection.public_id}",
        content=oversized,
        headers=_headers(oversized),
    )
    assert response.status_code == 413
    unknown = client.post(
        f"/api/messaging/chatwoot/webhooks/{uuid4()}",
        content=oversized,
        headers=_headers(oversized),
    )
    assert unknown.status_code == response.status_code
    malformed_known = client.post(
        f"/api/messaging/chatwoot/webhooks/{connection.public_id}",
        content=b"{}",
        headers={**_headers(b"{}"), "Content-Length": "invalid"},
    )
    malformed_unknown = client.post(
        f"/api/messaging/chatwoot/webhooks/{uuid4()}",
        content=b"{}",
        headers={**_headers(b"{}"), "Content-Length": "invalid"},
    )
    assert malformed_known.status_code == malformed_unknown.status_code == 400
    assert db_session.query(ChatwootWebhookReceipt).count() == 0

    from app.api.routers.chatwoot_webhooks import _read_bounded_raw_body

    chunks = iter([b"x" * (700 * 1024), b"y" * (400 * 1024), b""])

    async def receive():
        chunk = next(chunks)
        return {
            "type": "http.request",
            "body": chunk,
            "more_body": bool(chunk),
        }

    request = Request(
        {"type": "http", "method": "POST", "path": "/", "headers": []},
        receive,
    )
    with pytest.raises(Exception) as exc_info:
        asyncio.run(_read_bounded_raw_body(request))
    assert getattr(exc_info.value, "status_code", None) == 413


@pytest.mark.parametrize("unsafe_key", ["", "short-production-key", "changeme"])
def test_signing_secret_cipher_fails_closed_for_unsafe_production_keys(
    monkeypatch, unsafe_key
):
    from app.core.config import settings
    from app.services.messaging.chatwoot_security import SigningSecretUnavailable

    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", unsafe_key)
    with pytest.raises(SigningSecretUnavailable):
        encrypt_signing_secret(SECRET)


def test_projection_failure_rolls_back_and_emits_only_fixed_error(
    client, db_session, caplog, monkeypatch
):
    _, _, connection, _ = _boundary(db_session, suffix="persistence-failure")
    sentinels = (
        "SENTINEL-DB-SECRET",
        "SENTINEL-DB-BODY",
        "SENTINEL-DB-SENDER",
        "https://sentinel.example.test/private?token=SENTINEL-DB-URL",
    )

    def fail_projection(*_args, **_kwargs):
        raise RuntimeError(" ".join(sentinels))

    monkeypatch.setattr(
        "app.api.routers.chatwoot_webhooks.process_authenticated_event",
        fail_projection,
    )
    payload = _payload(
        content=sentinels[1],
        attachments=[{"id": 1, "data_url": sentinels[3]}],
    )
    response = _post(client, connection, payload)
    assert response.status_code == 500
    assert response.json()["error"]["message"] == "Webhook processing failed."
    combined = response.text + caplog.text
    for sentinel in sentinels:
        assert sentinel not in combined
    assert "chatwoot_webhook_projection_failed" in caplog.text
    assert db_session.query(ChatwootWebhookReceipt).count() == 0
    assert db_session.query(SmsMessage).count() == 0
    assert db_session.query(SmsConversation).count() == 0


def test_corrupt_cross_tenant_provider_binding_fails_before_any_write(
    client, db_session, caplog
):
    _, _, connection, binding = _boundary(db_session, suffix="corrupt-binding")
    other_tenant = Tenant(
        name="Synthetic Corrupt Other", subdomain="corrupt-binding-other"
    )
    db_session.add(other_tenant)
    db_session.flush()
    other_provider = Provider(
        tenant_id=other_tenant.id,
        name="Synthetic Cross Tenant Provider",
        active=True,
    )
    db_session.add(other_provider)
    db_session.flush()
    binding.provider_id = other_provider.id
    db_session.commit()

    response = _post(client, connection, _payload())
    assert response.status_code == 500
    assert response.json()["error"]["message"] == "Webhook processing failed."
    assert "chatwoot_webhook_projection_failed" in caplog.text
    assert db_session.query(ChatwootWebhookReceipt).count() == 0
    assert db_session.query(SmsMessage).count() == 0
    assert db_session.query(SmsConversation).count() == 0
    assert db_session.query(SmsAiJob).count() == 0
    assert db_session.query(SmsOutboundJob).count() == 0
    assert db_session.query(SmsConversationEvent).count() == 0


@pytest.mark.parametrize(
    "raw_body",
    [
        b'{"event":"message_created","account":{"id":NaN}}',
        (
            b'{"event":"message_created","account":{"id":"'
            + b"9" * 5000
            + b'"}}'
        ),
        (
            b'{"event":"message_created","account":{"id":7001},"nested":'
            + b"[" * 1100
            + b"0"
            + b"]" * 1100
            + b"}"
        ),
    ],
)
def test_extreme_and_nonstandard_json_fail_with_fixed_400(
    client, db_session, caplog, raw_body
):
    _, _, connection, _ = _boundary(
        db_session, suffix=f"extreme-{uuid4().hex[:8]}"
    )
    response = client.post(
        f"/api/messaging/chatwoot/webhooks/{connection.public_id}",
        content=raw_body,
        headers=_headers(raw_body),
    )
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Invalid webhook payload."
    assert "999999999999999999999999" not in response.text + caplog.text
    assert db_session.query(ChatwootWebhookReceipt).count() == 0
    assert db_session.query(SmsMessage).count() == 0


def test_global_unhandled_exception_logging_is_content_safe(caplog):
    from app.main import global_exception_handler

    sentinel = "SENTINEL-GLOBAL-EXCEPTION?token=private"
    request = Request(
        {"type": "http", "method": "GET", "path": "/", "headers": []}
    )
    response = asyncio.run(global_exception_handler(request, RuntimeError(sentinel)))
    assert response.status_code == 500
    assert sentinel not in response.body.decode() + caplog.text
    assert "unhandled_exception" in caplog.text


def test_uvicorn_access_record_removes_legacy_query_token():
    import io
    import logging

    sentinel = "SENTINEL-ACCESS-TOKEN"
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.addHandler(handler)
    try:
        access_logger.info(
            '%s - "%s %s HTTP/%s" %d',
            "127.0.0.1:12345",
            "POST",
            f"/api/sms/chatwoot/webhook?token={sentinel}",
            "1.1",
            410,
        )
    finally:
        access_logger.removeHandler(handler)
    assert sentinel not in stream.getvalue()
    assert "/api/sms/chatwoot/webhook" in stream.getvalue()
