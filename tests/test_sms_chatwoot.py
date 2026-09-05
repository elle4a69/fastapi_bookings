"""Regression coverage for the legacy outbound path retained until Package D."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.provider import Provider
from app.models.sms_chatwoot import SmsChatwootBinding
from app.models.sms_conversation import SmsConversation
from app.models.sms_outbox import SmsOutboundJob
from app.models.tenant import Tenant
from app.services.sms.chatwoot_service import send_chatwoot_message
from app.services.sms.outbound_service import enqueue_outbound_message_transactional
from app.services.sms.outbox_worker import process_pending_sms_outbound_jobs


@pytest.fixture
def setup_chatwoot_data(db_session):
    tenant = Tenant(name="Chatwoot Test Tenant", subdomain="chatwoot-test")
    db_session.add(tenant)
    db_session.flush()
    provider = Provider(
        tenant_id=tenant.id, name="Test Chatwoot Provider", active=True
    )
    db_session.add(provider)
    db_session.flush()
    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        chatwoot_account_id=1,
        chatwoot_inbox_id=45,
        chatwoot_base_url="https://app.chatwoot.com",
        chatwoot_api_token="my-secret-token",
        webhook_secret="my-webhook-secret",
        is_enabled=True,
    )
    db_session.add(binding)
    db_session.commit()
    return {"tenant": tenant, "provider": provider, "binding": binding}


def _conversation(db_session, data):
    conversation = SmsConversation(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        sms_account_id=None,
        customer_address="+61400000000",
        state="auto-reply",
        chatwoot_conversation_id=500,
        chatwoot_inbox_id=45,
    )
    db_session.add(conversation)
    db_session.commit()
    return conversation


def _mock_client(result=None, error=None):
    client = MagicMock()
    client.post = AsyncMock(return_value=result, side_effect=error)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


def test_outbound_delivery_via_chatwoot_only(db_session, setup_chatwoot_data):
    conversation = _conversation(db_session, setup_chatwoot_data)
    message = enqueue_outbound_message_transactional(
        db=db_session,
        account=None,
        conversation=conversation,
        body="This is an outbound reply to Chatwoot.",
        author_type="ai",
        status="queued",
    )
    job = db_session.query(SmsOutboundJob).filter_by(message_id=message.id).one()
    assert job.status == "PENDING"
    assert job.sms_account_id is None

    with patch(
        "app.services.sms.chatwoot_service.send_chatwoot_message",
        new=AsyncMock(return_value=888888),
    ) as mock_send:
        asyncio.run(process_pending_sms_outbound_jobs(db_session))

    mock_send.assert_awaited_once_with(
        db_session,
        conversation,
        "This is an outbound reply to Chatwoot.",
        source_id=f"fastapi-chatwoot-message-{message.id}",
    )
    db_session.refresh(job)
    db_session.refresh(message)
    assert job.status == "SUCCESS"
    assert message.status == "sent"
    assert message.chatwoot_message_id == 888888


def test_send_chatwoot_message_success(db_session, setup_chatwoot_data):
    conversation = _conversation(db_session, setup_chatwoot_data)
    response = MagicMock()
    response.json.return_value = {"id": 12345}
    client = _mock_client(result=response)
    with patch("httpx.AsyncClient", return_value=client):
        message_id = asyncio.run(
            send_chatwoot_message(db_session, conversation, "Hello world")
        )
    assert message_id == 12345
    client.post.assert_awaited_once_with(
        "https://app.chatwoot.com/api/v1/accounts/1/conversations/500/messages",
        headers={
            "api_access_token": "my-secret-token",
            "Content-Type": "application/json",
        },
        json={"content": "Hello world", "message_type": "outgoing"},
    )


def test_outbox_worker_updates_message_id_on_success(
    db_session, setup_chatwoot_data
):
    conversation = _conversation(db_session, setup_chatwoot_data)
    message = enqueue_outbound_message_transactional(
        db=db_session,
        account=None,
        conversation=conversation,
        body="This is an outbound reply to Chatwoot.",
        author_type="ai",
        status="queued",
    )
    job = db_session.query(SmsOutboundJob).filter_by(message_id=message.id).one()
    response = MagicMock()
    response.json.return_value = {"id": 888888}
    with patch("httpx.AsyncClient", return_value=_mock_client(result=response)):
        asyncio.run(process_pending_sms_outbound_jobs(db_session))
    db_session.refresh(job)
    db_session.refresh(message)
    assert job.status == "SUCCESS"
    assert message.status == "sent"
    assert message.chatwoot_message_id == 888888


def test_send_chatwoot_message_no_binding(db_session):
    conversation = SmsConversation(
        tenant_id=999,
        provider_id=999,
        customer_address="+61400000000",
        chatwoot_conversation_id=500,
    )
    db_session.add(conversation)
    db_session.commit()
    with pytest.raises(ValueError, match="No enabled Chatwoot binding"):
        asyncio.run(send_chatwoot_message(db_session, conversation, "Hello"))


@pytest.mark.parametrize(
    "error",
    [
        httpx.TimeoutException("Connection timed out"),
        httpx.RequestError("Connection failed"),
    ],
)
def test_send_chatwoot_message_transport_error(
    db_session, setup_chatwoot_data, error
):
    conversation = _conversation(db_session, setup_chatwoot_data)
    with patch("httpx.AsyncClient", return_value=_mock_client(error=error)):
        with pytest.raises(type(error)):
            asyncio.run(send_chatwoot_message(db_session, conversation, "Hello"))


def test_send_chatwoot_message_status_error(db_session, setup_chatwoot_data):
    conversation = _conversation(db_session, setup_chatwoot_data)
    response = MagicMock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Bad Request", request=MagicMock(), response=response
    )
    with patch("httpx.AsyncClient", return_value=_mock_client(result=response)):
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(send_chatwoot_message(db_session, conversation, "Hello"))


def test_outbox_worker_retry_on_exception(db_session, setup_chatwoot_data):
    conversation = _conversation(db_session, setup_chatwoot_data)
    message = enqueue_outbound_message_transactional(
        db=db_session,
        account=None,
        conversation=conversation,
        body="Retrying outbound message.",
        author_type="ai",
        status="queued",
    )
    job = db_session.query(SmsOutboundJob).filter_by(message_id=message.id).one()
    with patch(
        "httpx.AsyncClient",
        return_value=_mock_client(error=httpx.TimeoutException("timeout")),
    ):
        asyncio.run(process_pending_sms_outbound_jobs(db_session))
    db_session.refresh(job)
    db_session.refresh(message)
    assert job.status == "PENDING"
    assert job.retry_count == 1
    assert message.status == "queued"
