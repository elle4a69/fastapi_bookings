"""Package D regression tests for replacing the legacy Chatwoot sender."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.models.provider import Provider
from app.models.sms_chatwoot import (
    ChatwootConnection,
    ChatwootOutboundIntent,
    SmsChatwootBinding,
)
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_outbox import SmsOutboundJob
from app.models.tenant import Tenant
from app.services.messaging.chatwoot_security import (
    encrypt_api_token,
    encrypt_signing_secret,
)
from app.services.messaging.chatwoot_gateway import (
    claim_outbound_intent_for_dispatch,
    dispatch_outbound_intent,
    reconcile_unknown_outbound_intent,
)
from app.services.messaging.chatwoot_reconciliation import reconcile_remote_message
from app.services.sms.chatwoot_service import (
    LEGACY_OUTBOUND_RETIRED_DETAIL,
    send_chatwoot_message,
)
from app.services.sms.outbound_service import enqueue_outbound_message_transactional
from app.services.sms.outbound_service import ChatwootOutboundHandoffUnavailable
from app.services.sms.outbox_worker import (
    CHATWOOT_GENERIC_JOB_TERMINAL_REASON,
    process_pending_sms_outbound_jobs,
)


@pytest.fixture(autouse=True)
def _configure_trusted_chatwoot_origin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "CHATWOOT_TRUSTED_ORIGINS",
        "https://chatwoot.synthetic.test",
    )


@pytest.fixture
def outbound_boundary(db_session):
    tenant = Tenant(name="Synthetic D Tenant", subdomain="chatwoot-d-outbound")
    db_session.add(tenant)
    db_session.flush()
    provider = Provider(tenant_id=tenant.id, name="Synthetic D Provider", active=True)
    db_session.add(provider)
    db_session.flush()
    connection = ChatwootConnection(
        tenant_id=tenant.id,
        instance_origin="https://chatwoot.synthetic.test",
        chatwoot_account_id=7001,
        _signing_secret_ciphertext=encrypt_signing_secret("synthetic-signing-secret-value-000001"),
        _api_token_ciphertext=encrypt_api_token("synthetic-api-token-000001"),
        expected_integration_sender_type="User",
        expected_integration_sender_id=7005,
        enabled=True,
        outbound_enabled=True,
    )
    db_session.add(connection)
    db_session.flush()
    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        connection_id=connection.id,
        chatwoot_inbox_id=7002,
        channel="web_widget",
        ingress_enabled=True,
        outbound_enabled=True,
        is_enabled=False,
    )
    db_session.add(binding)
    db_session.flush()
    conversation = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        customer_address="synthetic-chatwoot-reference",
        state="paused",
        chatwoot_binding_id=binding.id,
        chatwoot_conversation_id=7003,
        chatwoot_inbox_id=binding.chatwoot_inbox_id,
    )
    db_session.add(conversation)
    db_session.commit()
    return tenant, provider, connection, binding, conversation


def _outbound_response(correlation_id, *, message_id=7006):
    return {
        "id": message_id,
        "content": "Synthetic response body",
        "content_type": "text",
        "message_type": "outgoing",
        "private": False,
        "account": {"id": 7001},
        "inbox": {"id": 7002},
        "conversation": {"id": 7003},
        "sender": {"id": 7005, "type": "User"},
        "content_attributes": {
            "fastapi_bookings": {"outbound_correlation_id": str(correlation_id)}
        },
    }


class _FakeClient:
    def __init__(self, *, post_result=None, post_error=None, get_result=None):
        self.post_result = post_result
        self.post_error = post_error
        self.get_result = get_result
        self.post = AsyncMock(side_effect=self._post)
        self.get = AsyncMock(side_effect=self._get)

    async def _post(self, *_args, **_kwargs):
        if self.post_error is not None:
            raise self.post_error
        return self.post_result

    async def _get(self, *_args, **_kwargs):
        return self.get_result or MagicMock(status_code=200, json=lambda: {"payload": []})

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


def test_outbound_intent_is_the_only_chatwoot_delivery_authority(
    db_session, outbound_boundary
):
    *_ignored, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db=db_session,
        account=None,
        conversation=conversation,
        body="Synthetic outbound response",
        author_type="ai",
        status="queued",
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    assert db_session.query(SmsOutboundJob).filter_by(message_id=message.id).count() == 0
    assert intent.status == "PENDING"
    assert intent.pre_send_cursor is None

    response = MagicMock(status_code=201)
    response.json.return_value = _outbound_response(intent.outbound_correlation_id)
    fake = _FakeClient(post_result=response)
    with patch(
        "app.services.messaging.chatwoot_gateway.httpx.AsyncClient", return_value=fake
    ) as client_factory:
        asyncio.run(process_pending_sms_outbound_jobs(db_session))

    fake.post.assert_awaited_once()
    url, = fake.post.call_args.args
    assert url == "https://chatwoot.synthetic.test/api/v1/accounts/7001/conversations/7003/messages"
    assert fake.post.call_args.kwargs["headers"] == {"api_access_token": "synthetic-api-token-000001"}
    assert fake.post.call_args.kwargs["json"] == {
        "content": "Synthetic outbound response",
        "message_type": "outgoing",
        "private": False,
        "content_attributes": {
            "fastapi_bookings": {"outbound_correlation_id": str(intent.outbound_correlation_id)}
        },
    }
    assert "source_id" not in fake.post.call_args.kwargs["json"]
    assert client_factory.call_args.kwargs["follow_redirects"] is False
    assert client_factory.call_args.kwargs["trust_env"] is False
    assert client_factory.call_args.kwargs["timeout"].connect == 5.0
    db_session.refresh(intent)
    db_session.refresh(message)
    assert intent.status == "SUCCEEDED"
    assert intent.remote_chatwoot_message_id == 7006
    assert message.status == "sent"
    assert message.chatwoot_message_id == 7006


def test_timeout_is_terminal_unknown_with_one_bounded_get_and_no_repost(
    db_session, outbound_boundary, caplog
):
    *_ignored, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db_session, None, conversation, "Synthetic timeout body", "ai", status="queued"
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    fake = _FakeClient(post_error=httpx.TimeoutException("synthetic-timeout"))
    with patch(
        "app.services.messaging.chatwoot_gateway.httpx.AsyncClient", return_value=fake
    ) as client_factory:
        asyncio.run(process_pending_sms_outbound_jobs(db_session))
        asyncio.run(process_pending_sms_outbound_jobs(db_session))
    assert fake.post.await_count == 1
    assert fake.get.await_count == 1
    assert all(call.kwargs["trust_env"] is False for call in client_factory.call_args_list)
    db_session.refresh(intent)
    assert intent.status == "OUTCOME_UNKNOWN"
    assert intent.reconciliation_attempted is True
    assert "Synthetic timeout body" not in caplog.text
    assert "synthetic-api-token-000001" not in caplog.text


def test_definitive_4xx_fails_once_without_reconciliation_get(
    db_session, outbound_boundary
):
    *_ignored, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db_session, None, conversation, "Synthetic rejected body", "ai", status="queued"
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    response = MagicMock(status_code=422)
    fake = _FakeClient(post_result=response)
    with patch("app.services.messaging.chatwoot_gateway.httpx.AsyncClient", return_value=fake):
        asyncio.run(process_pending_sms_outbound_jobs(db_session))
    assert fake.post.await_count == 1
    assert fake.get.await_count == 0
    db_session.refresh(intent)
    assert intent.status == "FAILED"


def test_in_process_http_boundary_observes_exact_post_contract(
    db_session, outbound_boundary
):
    *_ignored, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db_session, None, conversation, "Synthetic boundary body", "ai", status="queued"
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["method"] = request.method
        observed["path"] = request.url.path
        observed["token"] = request.headers.get("api_access_token")
        observed["body"] = json.loads(request.content)
        marker = observed["body"]["content_attributes"]["fastapi_bookings"][
            "outbound_correlation_id"
        ]
        return httpx.Response(201, json=_outbound_response(marker))

    client_calls = []
    real_async_client = httpx.AsyncClient

    def in_process_client(**kwargs):
        client_calls.append(kwargs)
        return real_async_client(
            transport=httpx.MockTransport(handler),
            follow_redirects=kwargs["follow_redirects"],
            timeout=kwargs["timeout"],
            trust_env=kwargs["trust_env"],
        )

    with patch(
        "app.services.messaging.chatwoot_gateway.httpx.AsyncClient",
        side_effect=in_process_client,
    ):
        asyncio.run(process_pending_sms_outbound_jobs(db_session))

    assert observed == {
        "method": "POST",
        "path": "/api/v1/accounts/7001/conversations/7003/messages",
        "token": "synthetic-api-token-000001",
        "body": {
            "content": "Synthetic boundary body",
            "message_type": "outgoing",
            "private": False,
            "content_attributes": {
                "fastapi_bookings": {
                    "outbound_correlation_id": str(intent.outbound_correlation_id)
                }
            },
        },
    }
    assert len(client_calls) == 1
    assert client_calls[0]["follow_redirects"] is False
    assert client_calls[0]["trust_env"] is False


@pytest.mark.parametrize("status_code, malformed", [(503, False), (201, True)])
def test_uncertain_5xx_or_malformed_success_never_reposts(
    db_session, outbound_boundary, status_code, malformed
):
    *_ignored, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db_session, None, conversation, "Synthetic uncertain response", "ai", status="queued"
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    response = MagicMock(status_code=status_code)
    response.json.return_value = {} if malformed else {"ignored": "synthetic"}
    fake = _FakeClient(post_result=response)
    with patch("app.services.messaging.chatwoot_gateway.httpx.AsyncClient", return_value=fake):
        asyncio.run(process_pending_sms_outbound_jobs(db_session))
        asyncio.run(process_pending_sms_outbound_jobs(db_session))
    assert fake.post.await_count == 1
    assert fake.get.await_count == 1
    db_session.refresh(intent)
    assert intent.status == "OUTCOME_UNKNOWN"


@pytest.mark.parametrize(
    "candidate_id, expected_status",
    [(7001, "SUCCEEDED"), (7000, "OUTCOME_UNKNOWN")],
)
def test_bounded_get_reconciles_only_newer_single_trusted_match(
    db_session, outbound_boundary, candidate_id, expected_status
):
    *_ignored, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db_session, None, conversation, "Synthetic GET candidate", "ai", status="queued"
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    intent.status = "OUTCOME_UNKNOWN"
    intent.pre_send_cursor = 7000
    db_session.commit()
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "payload": [_outbound_response(intent.outbound_correlation_id, message_id=candidate_id)]
    }
    fake = _FakeClient(get_result=response)
    with patch("app.services.messaging.chatwoot_gateway.httpx.AsyncClient", return_value=fake):
        asyncio.run(reconcile_unknown_outbound_intent(db_session, intent_id=intent.id))
    db_session.refresh(intent)
    assert intent.status == expected_status
    if expected_status == "SUCCEEDED":
        assert intent.remote_chatwoot_message_id == candidate_id


def test_bounded_get_multiple_marker_matches_quarantines_without_resend(
    db_session, outbound_boundary
):
    *_ignored, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db_session, None, conversation, "Synthetic uncertain body", "ai", status="queued"
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    intent.status = "OUTCOME_UNKNOWN"
    intent.pre_send_cursor = 7000
    db_session.commit()
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "payload": [
            _outbound_response(intent.outbound_correlation_id, message_id=7011),
            _outbound_response(intent.outbound_correlation_id, message_id=7012),
        ]
    }
    fake = _FakeClient(get_result=response)
    with patch("app.services.messaging.chatwoot_gateway.httpx.AsyncClient", return_value=fake):
        assert asyncio.run(reconcile_unknown_outbound_intent(db_session, intent_id=intent.id)) == "QUARANTINED"
    fake.post.assert_not_awaited()
    fake.get.assert_awaited_once()
    assert fake.get.call_args.kwargs["params"] == {"after": "7000"}
    db_session.refresh(intent)
    assert intent.status == "QUARANTINED"


def test_in_process_http_boundary_observes_exact_bounded_get_contract(
    db_session, outbound_boundary
):
    *_ignored, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db_session, None, conversation, "Synthetic GET boundary", "ai", status="queued"
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    intent.status = "OUTCOME_UNKNOWN"
    intent.pre_send_cursor = 7000
    db_session.commit()
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["method"] = request.method
        observed["path"] = request.url.path
        observed["after"] = request.url.params.get("after")
        observed["token"] = request.headers.get("api_access_token")
        return httpx.Response(
            200,
            json={
                "payload": [
                    _outbound_response(
                        intent.outbound_correlation_id,
                        message_id=7001,
                    )
                ]
            },
        )

    client_calls = []
    real_async_client = httpx.AsyncClient

    def in_process_client(**kwargs):
        client_calls.append(kwargs)
        return real_async_client(
            transport=httpx.MockTransport(handler),
            follow_redirects=kwargs["follow_redirects"],
            timeout=kwargs["timeout"],
            trust_env=kwargs["trust_env"],
        )

    with patch(
        "app.services.messaging.chatwoot_gateway.httpx.AsyncClient",
        side_effect=in_process_client,
    ):
        assert (
            asyncio.run(reconcile_unknown_outbound_intent(db_session, intent_id=intent.id))
            == "reconciled"
        )

    assert observed == {
        "method": "GET",
        "path": "/api/v1/accounts/7001/conversations/7003/messages",
        "after": "7000",
        "token": "synthetic-api-token-000001",
    }
    assert len(client_calls) == 1
    assert client_calls[0]["follow_redirects"] is False
    assert client_calls[0]["trust_env"] is False
    db_session.refresh(intent)
    assert intent.status == "SUCCEEDED"


def test_cursor_is_owned_at_claim_and_excludes_later_local_messages(
    db_session, outbound_boundary
):
    tenant, provider, _connection, binding, conversation = outbound_boundary
    # Preserve the causal ordering of the intent: the pre-existing projection
    # is inserted with a lower local ID, then a later row follows the intent.
    earlier = SmsMessage(
        tenant_id=tenant.id,
        provider_id=provider.id,
        conversation_id=conversation.id,
        body="Synthetic prior projection",
        direction="inbound",
        author_type="customer",
        status="received",
        chatwoot_binding_id=binding.id,
        chatwoot_message_id=7007,
    )
    db_session.add(earlier)
    db_session.flush()
    message = enqueue_outbound_message_transactional(
        db_session, None, conversation, "Synthetic first body", "ai", status="queued"
    )
    db_session.flush()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    later = SmsMessage(
        tenant_id=tenant.id,
        provider_id=provider.id,
        conversation_id=conversation.id,
        body="Synthetic later local record",
        direction="outbound",
        author_type="ai",
        status="queued",
        chatwoot_binding_id=binding.id,
        chatwoot_message_id=7999,
    )
    db_session.add(later)
    db_session.commit()
    assert intent.pre_send_cursor is None
    assert claim_outbound_intent_for_dispatch(db_session, intent_id=intent.id) is True
    db_session.refresh(intent)
    assert intent.status == "SENDING"
    assert intent.pre_send_cursor == 7007


def test_reconciliation_same_remote_id_is_idempotent_and_conflict_quarantines(
    db_session, outbound_boundary
):
    tenant, provider, connection, binding, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db_session, None, conversation, "Synthetic race body", "ai", status="queued"
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    assert claim_outbound_intent_for_dispatch(db_session, intent_id=intent.id) is True
    assert reconcile_remote_message(
        db_session,
        intent=intent,
        remote_message_id=7010,
        sender_type=connection.expected_integration_sender_type,
        sender_reference=str(connection.expected_integration_sender_id),
        invoke_verified_processor=True,
    ) == "reconciled"
    assert reconcile_remote_message(
        db_session,
        intent=intent,
        remote_message_id=7010,
        sender_type=connection.expected_integration_sender_type,
        sender_reference=str(connection.expected_integration_sender_id),
        invoke_verified_processor=True,
    ) == "reconciled"
    assert db_session.query(SmsMessage).filter(SmsMessage.conversation_id == conversation.id).count() == 1
    from app.models.sms_outbox import SmsConversationEvent

    assert db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == conversation.id
    ).count() == 1
    assert reconcile_remote_message(
        db_session,
        intent=intent,
        remote_message_id=7011,
        sender_type=connection.expected_integration_sender_type,
        sender_reference=str(connection.expected_integration_sender_id),
        invoke_verified_processor=True,
    ) == "quarantined"
    assert intent.status == "QUARANTINED"


def test_api_response_after_early_signed_echo_reconciles_exactly_once(
    db_session, outbound_boundary
):
    _tenant, _provider, connection, _binding, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db_session, None, conversation, "Synthetic early echo body", "ai", status="queued"
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    assert claim_outbound_intent_for_dispatch(db_session, intent_id=intent.id) is True
    real_async_client = httpx.AsyncClient

    def handler(_request: httpx.Request) -> httpx.Response:
        assert reconcile_remote_message(
            db_session,
            intent=intent,
            remote_message_id=7015,
            sender_type=connection.expected_integration_sender_type,
            sender_reference=str(connection.expected_integration_sender_id),
            invoke_verified_processor=True,
        ) == "reconciled"
        return httpx.Response(201, json=_outbound_response(intent.outbound_correlation_id, message_id=7015))

    def in_process_client(**kwargs):
        return real_async_client(
            transport=httpx.MockTransport(handler),
            follow_redirects=kwargs["follow_redirects"],
            timeout=kwargs["timeout"],
            trust_env=kwargs["trust_env"],
        )

    with patch(
        "app.services.messaging.chatwoot_gateway.httpx.AsyncClient",
        side_effect=in_process_client,
    ):
        assert asyncio.run(dispatch_outbound_intent(db_session, intent_id=intent.id)) == "reconciled"
    from app.models.sms_outbox import SmsConversationEvent

    db_session.refresh(intent)
    assert intent.status == "SUCCEEDED"
    assert db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == conversation.id
    ).count() == 1


@pytest.mark.parametrize("missing_field", ["chatwoot_binding_id", "chatwoot_conversation_id"])
def test_partial_chatwoot_linkage_fails_closed_without_generic_job(
    db_session, outbound_boundary, missing_field
):
    tenant, provider, _connection, binding, conversation = outbound_boundary
    setattr(conversation, missing_field, None)
    db_session.commit()
    before_jobs = db_session.query(SmsOutboundJob).count()
    with pytest.raises(ChatwootOutboundHandoffUnavailable, match="handoff is unavailable"):
        enqueue_outbound_message_transactional(
            db_session, None, conversation, "Synthetic partial link", "ai", status="queued"
        )
    assert db_session.query(SmsOutboundJob).count() == before_jobs

    # A historical generic job associated with either half of a Chatwoot
    # linkage is also terminal. It cannot fall through to a direct adapter.
    message = SmsMessage(
        tenant_id=tenant.id,
        provider_id=provider.id,
        conversation_id=conversation.id,
        body="Synthetic partial legacy job",
        direction="outbound",
        author_type="ai",
        status="queued",
        chatwoot_binding_id=binding.id,
    )
    db_session.add(message)
    db_session.flush()
    job = SmsOutboundJob(message_id=message.id, sms_account_id=None, status="PENDING")
    db_session.add(job)
    db_session.commit()
    asyncio.run(process_pending_sms_outbound_jobs(db_session))
    db_session.refresh(job)
    assert job.status == "FAILED"
    assert job.error_log == CHATWOOT_GENERIC_JOB_TERMINAL_REASON


@pytest.mark.parametrize(
    "invalid_local_tuple",
    [
        "ingress_disabled",
        "conversation_inbox_mismatch",
        "message_binding_mismatch",
    ],
)
def test_dispatch_requires_effective_ingress_and_consistent_local_tuple(
    db_session, outbound_boundary, invalid_local_tuple
):
    """No credentialed POST occurs after any local trust tuple drift."""
    *_prefix, binding, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db_session, None, conversation, "Synthetic tuple drift", "ai", status="queued"
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    if invalid_local_tuple == "ingress_disabled":
        binding.ingress_enabled = False
    elif invalid_local_tuple == "conversation_inbox_mismatch":
        conversation.chatwoot_inbox_id = binding.chatwoot_inbox_id + 1
    else:
        message.chatwoot_binding_id = None
    db_session.commit()
    fake = _FakeClient(post_result=MagicMock(status_code=201))
    with patch("app.services.messaging.chatwoot_gateway.httpx.AsyncClient", return_value=fake):
        asyncio.run(process_pending_sms_outbound_jobs(db_session))
    fake.post.assert_not_awaited()
    db_session.refresh(intent)
    assert intent.status == "FAILED"


def test_unsafe_stored_origin_blocks_dispatch_before_token_or_content_reaches_client(
    db_session, outbound_boundary
):
    """Historical unsafe records cannot decrypt a credential or build a POST."""
    *_prefix, connection, _binding, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db_session,
        None,
        conversation,
        "Synthetic blocked dispatch body",
        "ai",
        status="queued",
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    assert claim_outbound_intent_for_dispatch(db_session, intent_id=intent.id) is True
    connection.instance_origin = "https://127.0.0.1"
    db_session.commit()

    with patch(
        "app.services.messaging.chatwoot_gateway.decrypt_api_token",
        side_effect=AssertionError("token decryption reached"),
    ) as decrypt, patch(
        "app.services.messaging.chatwoot_gateway.httpx.AsyncClient",
        side_effect=AssertionError("credentialed client reached"),
    ) as client_factory:
        assert asyncio.run(dispatch_outbound_intent(db_session, intent_id=intent.id)) == "FAILED"

    decrypt.assert_not_called()
    client_factory.assert_not_called()
    db_session.refresh(intent)
    db_session.refresh(message)
    assert intent.status == "FAILED"
    assert message.status == "failed"


def test_unsafe_stored_origin_blocks_reconciliation_before_token_or_client(
    db_session, outbound_boundary
):
    """An unsafe historical record cannot leak a token during its one-shot GET."""
    *_prefix, connection, _binding, conversation = outbound_boundary
    message = enqueue_outbound_message_transactional(
        db_session,
        None,
        conversation,
        "Synthetic blocked reconciliation body",
        "ai",
        status="queued",
    )
    db_session.commit()
    intent = db_session.query(ChatwootOutboundIntent).filter_by(message_id=message.id).one()
    intent.status = "OUTCOME_UNKNOWN"
    connection.instance_origin = "https://169.254.169.254"
    db_session.commit()

    with patch(
        "app.services.messaging.chatwoot_gateway.decrypt_api_token",
        side_effect=AssertionError("token decryption reached"),
    ) as decrypt, patch(
        "app.services.messaging.chatwoot_gateway.httpx.AsyncClient",
        side_effect=AssertionError("credentialed client reached"),
    ) as client_factory:
        assert (
            asyncio.run(reconcile_unknown_outbound_intent(db_session, intent_id=intent.id))
            == "QUARANTINED"
        )

    decrypt.assert_not_called()
    client_factory.assert_not_called()
    db_session.refresh(intent)
    db_session.refresh(message)
    assert intent.status == "QUARANTINED"
    assert intent.reconciliation_attempted is False
    assert message.status == "failed"


def test_legacy_sender_and_generic_chatwoot_job_fail_closed(
    db_session, outbound_boundary, monkeypatch
):
    *_ignored, conversation = outbound_boundary
    with pytest.raises(RuntimeError, match="Legacy Chatwoot outbound is retired"):
        asyncio.run(send_chatwoot_message(db_session, conversation, "Synthetic"))

    message = enqueue_outbound_message_transactional(
        db_session, None, conversation, "Synthetic intent body", "ai", status="queued"
    )
    db_session.flush()
    # A historical generic job must not be able to invoke a legacy sender or
    # a direct transport, even when a conversation is Chatwoot-bound.
    job = SmsOutboundJob(message_id=message.id, sms_account_id=None, status="PENDING")
    db_session.add(job)
    db_session.commit()
    monkeypatch.setattr(
        "app.services.sms.chatwoot_service.send_chatwoot_message",
        AsyncMock(side_effect=AssertionError("legacy send reached")),
    )
    asyncio.run(process_pending_sms_outbound_jobs(db_session))
    db_session.refresh(job)
    assert job.status == "FAILED"
    assert job.error_log == CHATWOOT_GENERIC_JOB_TERMINAL_REASON
    assert LEGACY_OUTBOUND_RETIRED_DETAIL == "Legacy Chatwoot outbound is retired."
