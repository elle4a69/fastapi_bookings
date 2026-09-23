import asyncio

import httpx
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException

from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.sms_chatwoot import SmsChatwootBinding
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_outbox import SmsAiJob, SmsOutboundJob, SmsConversationEvent
from app.services.sms.outbound_service import enqueue_outbound_message_transactional
from app.services.sms.outbox_worker import process_pending_sms_outbound_jobs
from app.services.sms.chatwoot_service import (
    process_chatwoot_webhook,
    send_chatwoot_message,
)

@pytest.fixture
def setup_chatwoot_data(db_session):
    # Create Tenant
    tenant = Tenant(name="Chatwoot Test Tenant", subdomain="chatwoot-test")
    db_session.add(tenant)
    db_session.commit()

    # Create Provider
    provider = Provider(tenant_id=tenant.id, name="Test Chatwoot Provider", active=True)
    db_session.add(provider)
    db_session.commit()

    # Create Chatwoot Binding
    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        chatwoot_account_id=1,
        chatwoot_inbox_id=45,
        chatwoot_base_url="https://app.chatwoot.com",
        chatwoot_api_token="my-secret-token",
        webhook_secret="my-webhook-secret",
        is_enabled=True
    )
    db_session.add(binding)
    db_session.commit()

    return {
        "tenant": tenant,
        "provider": provider,
        "binding": binding
    }

def test_inbound_idempotency(db_session, setup_chatwoot_data):
    # First webhook call
    payload = {
        "id": 101,
        "content": "Hello, I need assistance.",
        "message_type": "incoming",
        "private": False,
        "inbox": {"id": 45},
        "conversation": {
            "id": 500,
            "contact": {
                "id": 89,
                "phone_number": "+61400000000"
            }
        }
    }
    
    result = process_chatwoot_webhook(db_session, payload, token="my-webhook-secret")
    assert result["status"] == "success"
    assert result["duplicate"] is False
    assert result["conversation_id"] is not None

    # Check database
    msg = db_session.query(SmsMessage).filter(SmsMessage.chatwoot_message_id == 101).first()
    assert msg is not None
    assert msg.body == "Hello, I need assistance."
    assert msg.direction == "inbound"
    assert msg.author_type == "customer"

    # Send the exact same webhook again
    result2 = process_chatwoot_webhook(db_session, payload, token="my-webhook-secret")
    assert result2["status"] == "success"
    assert result2["duplicate"] is True
    assert result2["message_id"] == msg.id

    # Verify no duplicate messages in DB
    msg_count = db_session.query(SmsMessage).filter(SmsMessage.chatwoot_message_id == 101).count()
    assert msg_count == 1

def test_provider_inbox_isolation(db_session, setup_chatwoot_data):
    data1 = setup_chatwoot_data

    # Create a second Tenant, Provider and Binding
    tenant2 = Tenant(name="Chatwoot Test Tenant 2", subdomain="chatwoot-test-2")
    db_session.add(tenant2)
    db_session.commit()

    provider2 = Provider(tenant_id=tenant2.id, name="Test Chatwoot Provider 2", active=True)
    db_session.add(provider2)
    db_session.commit()

    binding2 = SmsChatwootBinding(
        tenant_id=tenant2.id,
        provider_id=provider2.id,
        chatwoot_account_id=2,
        chatwoot_inbox_id=46,
        chatwoot_base_url="https://app.chatwoot.com",
        chatwoot_api_token="another-secret-token",
        webhook_secret="another-webhook-secret",
        is_enabled=True
    )
    db_session.add(binding2)
    db_session.commit()

    # Webhook payload targetted to inbox 45 (first binding)
    payload = {
        "id": 102,
        "content": "Message for Provider 1",
        "message_type": "incoming",
        "inbox": {"id": 45},
        "conversation": {
            "id": 501,
            "contact": {
                "id": 90,
                "phone_number": "+61411111111"
            }
        }
    }

    # Verify invalid token rejected
    with pytest.raises(Exception) as exc_info:
        process_chatwoot_webhook(db_session, payload, token="wrong-token")
    assert "401" in str(exc_info.value) or "webhook secret" in str(exc_info.value)

    # Process with correct token
    result = process_chatwoot_webhook(db_session, payload, token="my-webhook-secret")
    assert result["status"] == "success"

    # Verify message is created for provider 1, but not provider 2
    msg1 = db_session.query(SmsMessage).filter(SmsMessage.chatwoot_message_id == 102).first()
    assert msg1 is not None
    assert msg1.provider_id == data1["provider"].id
    assert msg1.tenant_id == data1["tenant"].id

    # Verify second provider remains untouched
    conv2_count = db_session.query(SmsConversation).filter(SmsConversation.provider_id == provider2.id).count()
    assert conv2_count == 0

def test_outbound_delivery_via_chatwoot_only(db_session, setup_chatwoot_data):
    data = setup_chatwoot_data

    # Setup pre-existing Chatwoot conversation
    conversation = SmsConversation(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        sms_account_id=None,
        customer_address="+61400000000",
        state="auto-reply",
        chatwoot_conversation_id=500,
        chatwoot_inbox_id=45
    )
    db_session.add(conversation)
    db_session.commit()

    # Enqueue outbound message
    msg = enqueue_outbound_message_transactional(
        db=db_session,
        account=None,
        conversation=conversation,
        body="This is an outbound reply to Chatwoot.",
        author_type="staff",
        status="queued"
    )

    # Verify SmsOutboundJob was created
    job = db_session.query(SmsOutboundJob).filter(SmsOutboundJob.message_id == msg.id).first()
    assert job is not None
    assert job.status == "PENDING"
    assert job.sms_account_id is None

    # Process outbound jobs using mock Chatwoot client send function
    with patch("app.services.sms.chatwoot_service.send_chatwoot_message") as mock_send:
        mock_send.return_value = 888888

        import asyncio
        asyncio.run(process_pending_sms_outbound_jobs(db_session))

        # Assert send_chatwoot_message was called and not any standard SMS transports
        mock_send.assert_called_once_with(
            db_session,
            conversation,
            "This is an outbound reply to Chatwoot.",
            source_id=f"fastapi-chatwoot-message-{msg.id}",
        )

        # Verify job and message updates
        db_session.refresh(job)
        db_session.refresh(msg)
        assert job.status == "SUCCESS"
        assert msg.status == "sent"
        assert msg.chatwoot_message_id == 888888

def test_webhook_loops_prevention_and_staff_takeover(db_session, setup_chatwoot_data):
    data = setup_chatwoot_data

    # Setup pre-existing Chatwoot conversation
    conversation = SmsConversation(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        sms_account_id=None,
        customer_address="+61400000000",
        state="auto-reply",
        chatwoot_conversation_id=500,
        chatwoot_inbox_id=45
    )
    db_session.add(conversation)
    db_session.commit()

    # Case 1: Webhook loop prevention (deduplicate our own outbound message)
    # Put a message in the DB that has a chatwoot_message_id
    our_msg = SmsMessage(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        sms_account_id=None,
        conversation_id=conversation.id,
        body="Message already sent by us.",
        direction="outbound",
        author_type="staff",
        status="sent",
        chatwoot_message_id=202
    )
    db_session.add(our_msg)
    db_session.commit()

    # Simulating Chatwoot webhook echoing back our message
    payload_loop = {
        "id": 202,
        "content": "Message already sent by us.",
        "message_type": "outgoing",
        "inbox": {"id": 45},
        "conversation": {
            "id": 500,
            "contact": {
                "id": 89,
                "phone_number": "+61400000000"
            }
        }
    }

    result = process_chatwoot_webhook(db_session, payload_loop, token="my-webhook-secret")
    assert result["status"] == "success"
    assert result["duplicate"] is True # Webhook loop prevented

    # Verify conversation is NOT taken over since it was our own message
    db_session.refresh(conversation)
    assert conversation.state == "auto-reply"

    # Case 2: Staff takeover from Chatwoot UI
    # Enqueue a pending AI Job for the conversation
    ai_job = SmsAiJob(
        conversation_id=conversation.id,
        customer_turn_ref="turn-prior",
        status="PENDING"
    )
    db_session.add(ai_job)
    db_session.commit()

    # Simulating a new outgoing message sent by a staff member in Chatwoot UI
    payload_staff = {
        "id": 203,
        "content": "Hello, this is Agent Bob. How can I help you?",
        "message_type": "outgoing",
        "inbox": {"id": 45},
        "conversation": {
            "id": 500,
            "contact": {
                "id": 89,
                "phone_number": "+61400000000"
            }
        }
    }

    result2 = process_chatwoot_webhook(db_session, payload_staff, token="my-webhook-secret")
    assert result2["status"] == "success"
    assert result2["duplicate"] is False
    assert result2["state"] == "taken-over"

    # Verify conversation state is updated
    db_session.refresh(conversation)
    assert conversation.state == "taken-over"

    # Verify staff message is recorded
    staff_msg = db_session.query(SmsMessage).filter(SmsMessage.chatwoot_message_id == 203).first()
    assert staff_msg is not None
    assert staff_msg.direction == "outbound"
    assert staff_msg.author_type == "staff"
    assert staff_msg.body == "Hello, this is Agent Bob. How can I help you?"

    # Verify pending AI Job is cancelled
    db_session.refresh(ai_job)
    assert ai_job.status == "CANCELLED"

    # Verify takeover event is recorded
    event = db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == conversation.id,
        SmsConversationEvent.type == "takeover"
    ).first()
    assert event is not None
    assert event.meta.get("chatwoot_message_id") == 203


@pytest.mark.parametrize(
    "payload",
    [
        {"id": 1, "content": "Synthetic", "message_type": "incoming", "inbox": []},
        {
            "id": -1,
            "content": "Synthetic",
            "message_type": "incoming",
            "inbox": {"id": 45},
            "conversation": {"id": 500},
        },
        {
            "id": 1,
            "content": "Synthetic",
            "message_type": "incoming",
            "inbox": {"id": True},
            "conversation": {"id": 500},
        },
        {
            "id": 1.5,
            "content": "Synthetic",
            "message_type": "incoming",
            "inbox": {"id": 45},
            "conversation": {"id": 500},
        },
        {
            "id": 1,
            "content": "Synthetic",
            "message_type": "incoming",
            "inbox": {"id": 45},
            "conversation": {"id": {"nested": 500}},
        },
    ],
)
def test_webhook_rejects_non_positive_or_wrong_type_identifiers(
    db_session, setup_chatwoot_data, payload
):
    with pytest.raises(HTTPException) as exc_info:
        process_chatwoot_webhook(db_session, payload, token="my-webhook-secret")
    assert exc_info.value.status_code == 400


def test_webhook_bounds_content_and_does_not_log_untrusted_message_type(
    db_session, setup_chatwoot_data, caplog
):
    oversized = {
        "id": 9001,
        "content": "x" * 1601,
        "message_type": "incoming",
        "inbox": {"id": 45},
        "conversation": {"id": 9500, "contact": {"id": 989}},
    }
    with pytest.raises(HTTPException) as exc_info:
        process_chatwoot_webhook(db_session, oversized, token="my-webhook-secret")
    assert exc_info.value.status_code == 422

    canary = "SYNTHETIC_SECRET_MESSAGE_TYPE_CANARY"
    skipped = process_chatwoot_webhook(
        db_session,
        {
            "id": 9002,
            "content": "Synthetic",
            "message_type": canary,
            "inbox": {"id": 45},
            "conversation": {"id": 9500},
        },
        token="my-webhook-secret",
    )
    assert skipped == {"status": "skipped", "reason": "unsupported_message_type"}
    assert canary not in caplog.text


def test_source_id_echo_is_scoped_to_exact_chatwoot_conversation(
    db_session, setup_chatwoot_data
):
    data = setup_chatwoot_data
    conversation_a = SmsConversation(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        customer_address="+61400000101",
        state="taken-over",
        chatwoot_conversation_id=5101,
        chatwoot_inbox_id=45,
    )
    conversation_b = SmsConversation(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        customer_address="+61400000102",
        state="auto-reply",
        chatwoot_conversation_id=5102,
        chatwoot_inbox_id=45,
    )
    db_session.add_all([conversation_a, conversation_b])
    db_session.flush()
    internal = SmsMessage(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        conversation_id=conversation_a.id,
        body="Synthetic FastAPI staff reply",
        direction="outbound",
        author_type="staff",
        status="sending",
        client_request_id="synthetic-cross-thread-source",
    )
    db_session.add(internal)
    db_session.commit()

    result = process_chatwoot_webhook(
        db_session,
        {
            "id": 9101,
            "content": "Synthetic Chatwoot staff reply",
            "source_id": "synthetic-cross-thread-source",
            "message_type": "outgoing",
            "inbox": {"id": 45},
            "conversation": {"id": 5102, "contact": {"id": 991}},
        },
        token="my-webhook-secret",
    )
    db_session.refresh(internal)
    assert result["duplicate"] is False
    assert result["conversation_id"] == conversation_b.id
    assert internal.chatwoot_message_id is None


def test_phone_fallback_never_rebinds_existing_chatwoot_thread(
    db_session, setup_chatwoot_data
):
    data = setup_chatwoot_data
    existing = SmsConversation(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        customer_address="+61400000103",
        state="paused",
        chatwoot_conversation_id=5201,
        chatwoot_contact_id=992,
        chatwoot_inbox_id=45,
    )
    db_session.add(existing)
    db_session.commit()

    result = process_chatwoot_webhook(
        db_session,
        {
            "id": 9201,
            "content": "Synthetic distinct thread",
            "message_type": "incoming",
            "inbox": {"id": 45},
            "conversation": {
                "id": 5202,
                "contact": {"id": 993, "phone_number": "+61400000103"},
            },
        },
        token="my-webhook-secret",
    )
    db_session.refresh(existing)
    assert result["conversation_id"] != existing.id
    assert existing.chatwoot_conversation_id == 5201
    created = db_session.query(SmsConversation).filter(
        SmsConversation.id == result["conversation_id"]
    ).one()
    assert created.chatwoot_conversation_id == 5202


def test_ambiguous_unbound_phone_fallback_fails_closed(
    db_session, setup_chatwoot_data
):
    data = setup_chatwoot_data
    db_session.add_all(
        [
            SmsConversation(
                tenant_id=data["tenant"].id,
                provider_id=data["provider"].id,
                customer_address="61400000104",
                state="paused",
            ),
            SmsConversation(
                tenant_id=data["tenant"].id,
                provider_id=data["provider"].id,
                customer_address="61400000104",
                state="paused",
            ),
        ]
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        process_chatwoot_webhook(
            db_session,
            {
                "id": 9301,
                "content": "Synthetic ambiguous mapping",
                "message_type": "incoming",
                "inbox": {"id": 45},
                "conversation": {
                    "id": 5301,
                    "contact": {"id": 994, "phone_number": "+61400000104"},
                },
            },
            token="my-webhook-secret",
        )
    assert exc_info.value.status_code == 409

def test_internal_outbound_echo_before_remote_message_id_does_not_take_over(
    db_session, setup_chatwoot_data
):
    """The source ID protects against a webhook arriving before POST returns."""
    data = setup_chatwoot_data
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

    outbound = SmsMessage(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        sms_account_id=None,
        conversation_id=conversation.id,
        body="FastAPI generated reply.",
        direction="outbound",
        author_type="staff",
        status="sending",
    )
    db_session.add(outbound)
    db_session.commit()

    payload = {
        "id": 204,
        "source_id": f"fastapi-chatwoot-message-{outbound.id}",
        "content": "FastAPI generated reply.",
        "message_type": "outgoing",
        "inbox": {"id": 45},
        "conversation": {"id": 500, "contact": {"id": 89}},
    }

    result = process_chatwoot_webhook(db_session, payload, token="my-webhook-secret")

    assert result["status"] == "success"
    assert result["duplicate"] is True
    assert result["reason"] == "internal_outbound_echo"
    db_session.refresh(outbound)
    db_session.refresh(conversation)
    assert outbound.chatwoot_message_id == 204
    assert outbound.status == "sent"
    assert conversation.state == "auto-reply"
    assert db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == conversation.id,
        SmsConversationEvent.type == "takeover",
    ).count() == 0

def test_send_chatwoot_message_success(db_session, setup_chatwoot_data):
    import asyncio
    from unittest.mock import AsyncMock
    from app.services.sms.chatwoot_service import send_chatwoot_message
    
    data = setup_chatwoot_data
    conversation = SmsConversation(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        sms_account_id=None,
        customer_address="+61400000000",
        state="auto-reply",
        chatwoot_conversation_id=500,
        chatwoot_inbox_id=45
    )
    db_session.add(conversation)
    db_session.commit()

    # Mock client setup
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": 12345}
    
    mock_post = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        msg_id = asyncio.run(send_chatwoot_message(db_session, conversation, "Hello world"))
        
        # Verify message ID returned correctly
        assert msg_id == 12345
        
        # Verify correct formatting of the request (URL, headers, payload)
        expected_url = "https://app.chatwoot.com/api/v1/accounts/1/conversations/500/messages"
        expected_headers = {
            "api_access_token": "my-secret-token",
            "Content-Type": "application/json"
        }
        expected_payload = {
            "content": "Hello world",
            "message_type": "outgoing"
        }
        
        mock_post.assert_called_once_with(
            expected_url,
            headers=expected_headers,
            json=expected_payload
        )

def test_outbox_worker_updates_message_id_on_success(db_session, setup_chatwoot_data):
    import asyncio
    from unittest.mock import AsyncMock
    
    data = setup_chatwoot_data

    conversation = SmsConversation(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        sms_account_id=None,
        customer_address="+61400000000",
        state="auto-reply",
        chatwoot_conversation_id=500,
        chatwoot_inbox_id=45
    )
    db_session.add(conversation)
    db_session.commit()

    msg = enqueue_outbound_message_transactional(
        db=db_session,
        account=None,
        conversation=conversation,
        body="This is an outbound reply to Chatwoot.",
        author_type="staff",
        status="queued"
    )

    job = db_session.query(SmsOutboundJob).filter(SmsOutboundJob.message_id == msg.id).first()
    assert job is not None
    assert job.status == "PENDING"

    # Mock client setup
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": 888888}
    
    mock_post = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        asyncio.run(process_pending_sms_outbound_jobs(db_session))

        # Verify job and message updates
        db_session.refresh(job)
        db_session.refresh(msg)
        assert job.status == "SUCCESS"
        assert msg.status == "sent"
        assert msg.chatwoot_message_id == 888888

def test_send_chatwoot_message_no_binding(db_session):
    import asyncio
    import pytest
    from app.services.sms.chatwoot_service import send_chatwoot_message
    
    conversation = SmsConversation(
        tenant_id=999,
        provider_id=999,
        sms_account_id=None,
        customer_address="+61400000000",
        state="auto-reply",
        chatwoot_conversation_id=500,
        chatwoot_inbox_id=45
    )
    db_session.add(conversation)
    db_session.commit()

    with pytest.raises(ValueError) as excinfo:
        asyncio.run(send_chatwoot_message(db_session, conversation, "Hello"))
    assert "enabled Chatwoot binding" in str(excinfo.value)

def test_send_chatwoot_message_timeout(db_session, setup_chatwoot_data):
    import asyncio
    import httpx
    import pytest
    from unittest.mock import AsyncMock
    from app.services.sms.chatwoot_service import send_chatwoot_message
    
    data = setup_chatwoot_data
    conversation = SmsConversation(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        sms_account_id=None,
        customer_address="+61400000000",
        state="auto-reply",
        chatwoot_conversation_id=500,
        chatwoot_inbox_id=45
    )
    db_session.add(conversation)
    db_session.commit()

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.TimeoutException):
            asyncio.run(send_chatwoot_message(db_session, conversation, "Hello"))

def test_send_chatwoot_message_status_error(db_session, setup_chatwoot_data):
    import asyncio
    import httpx
    import pytest
    from unittest.mock import AsyncMock
    from app.services.sms.chatwoot_service import send_chatwoot_message
    
    data = setup_chatwoot_data
    conversation = SmsConversation(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        sms_account_id=None,
        customer_address="+61400000000",
        state="auto-reply",
        chatwoot_conversation_id=500,
        chatwoot_inbox_id=45
    )
    db_session.add(conversation)
    db_session.commit()

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Bad Request", request=MagicMock(), response=mock_response
    )
    
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(send_chatwoot_message(db_session, conversation, "Hello"))

def test_outbox_worker_retry_on_exception(db_session, setup_chatwoot_data):
    import asyncio
    import httpx
    from unittest.mock import AsyncMock
    
    data = setup_chatwoot_data

    conversation = SmsConversation(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        sms_account_id=None,
        customer_address="+61400000000",
        state="auto-reply",
        chatwoot_conversation_id=500,
        chatwoot_inbox_id=45
    )
    db_session.add(conversation)
    db_session.commit()

    msg = enqueue_outbound_message_transactional(
        db=db_session,
        account=None,
        conversation=conversation,
        body="Retrying outbound message.",
        author_type="staff",
        status="queued"
    )

    job = db_session.query(SmsOutboundJob).filter(SmsOutboundJob.message_id == msg.id).first()
    assert job is not None
    assert job.status == "PENDING"
    assert job.retry_count == 0

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        asyncio.run(process_pending_sms_outbound_jobs(db_session))

        db_session.refresh(job)
        db_session.refresh(msg)
        assert job.status == "PENDING"
        assert job.retry_count == 1
        assert msg.status == "queued"

def test_webhook_authentication_regression_cases(db_session, setup_chatwoot_data):
    """Regression tests for webhook secret authentication, loop prevention, and takeover."""
    from fastapi import HTTPException
    data = setup_chatwoot_data
    
    # Payload for a new inbound message
    payload = {
        "id": 801,
        "content": "Testing webhook secrets.",
        "message_type": "incoming",
        "inbox": {"id": 45},
        "conversation": {
            "id": 500,
            "contact": {
                "id": 89,
                "phone_number": "+61400000000"
            }
        }
    }
    
    # 1. Valid dedicated webhook secret accepted
    result = process_chatwoot_webhook(db_session, payload, token="my-webhook-secret")
    assert result["status"] == "success"
    assert result["duplicate"] is False
    
    # 2. API token rejected as webhook secret
    payload["id"] = 802
    with pytest.raises(HTTPException) as exc_info:
        process_chatwoot_webhook(db_session, payload, token="my-secret-token")
    assert exc_info.value.status_code == 401
    assert "webhook secret" in exc_info.value.detail or "Invalid" in exc_info.value.detail

    # 3. Invalid secret rejected
    payload["id"] = 803
    with pytest.raises(HTTPException) as exc_info:
        process_chatwoot_webhook(db_session, payload, token="invalid-secret-key")
    assert exc_info.value.status_code == 401
    assert "webhook secret" in exc_info.value.detail or "Invalid" in exc_info.value.detail

    # Set up conversation for loop and takeover cases
    conversation = db_session.query(SmsConversation).filter(
        SmsConversation.chatwoot_conversation_id == 500
    ).first()
    assert conversation is not None
    conversation.state = "auto-reply"
    db_session.commit()

    # 4. FastAPI's own outbound Chatwoot echo does not trigger takeover
    # Create the internal outbound message with the client_request_id (source_id)
    outbound = SmsMessage(
        tenant_id=data["tenant"].id,
        provider_id=data["provider"].id,
        sms_account_id=None,
        conversation_id=conversation.id,
        body="FastAPI reply.",
        direction="outbound",
        author_type="ai",
        status="sending",
        client_request_id="fastapi-source-id-takeover-test",
    )
    db_session.add(outbound)
    db_session.commit()

    payload_echo = {
        "id": 804,
        "source_id": "fastapi-source-id-takeover-test",
        "content": "FastAPI reply.",
        "message_type": "outgoing",
        "inbox": {"id": 45},
        "conversation": {"id": 500, "contact": {"id": 89}},
    }
    
    result_echo = process_chatwoot_webhook(db_session, payload_echo, token="my-webhook-secret")
    assert result_echo["status"] == "success"
    assert result_echo["duplicate"] is True
    assert result_echo["reason"] == "internal_outbound_echo"
    
    db_session.refresh(conversation)
    assert conversation.state == "auto-reply"  # State remains auto-reply (no takeover)

    # 5. Real staff outgoing message still triggers takeover
    ai_job = SmsAiJob(
        conversation_id=conversation.id,
        customer_turn_ref="turn-test",
        status="PENDING"
    )
    db_session.add(ai_job)
    db_session.commit()

    payload_staff = {
        "id": 805,
        "content": "Hello, I am a human agent.",
        "message_type": "outgoing",
        "inbox": {"id": 45},
        "conversation": {"id": 500, "contact": {"id": 89}},
    }
    
    result_staff = process_chatwoot_webhook(db_session, payload_staff, token="my-webhook-secret")
    assert result_staff["status"] == "success"
    assert result_staff["duplicate"] is False
    assert result_staff["state"] == "taken-over"
    
    db_session.refresh(conversation)
    assert conversation.state == "taken-over"
    db_session.refresh(ai_job)
    assert ai_job.status == "CANCELLED"


def test_incoming_source_id_never_reconciles_an_outbound_message(
    db_session, setup_chatwoot_data
):
    binding = setup_chatwoot_data["binding"]
    conversation = SmsConversation(
        tenant_id=binding.tenant_id,
        provider_id=binding.provider_id,
        sms_account_id=None,
        customer_address="chatwoot_contact_synthetic_source",
        state="paused",
        ai_enabled=False,
        chatwoot_conversation_id=9301,
        chatwoot_contact_id=9302,
        chatwoot_inbox_id=binding.chatwoot_inbox_id,
    )
    db_session.add(conversation)
    db_session.flush()
    outbound = SmsMessage(
        tenant_id=binding.tenant_id,
        provider_id=binding.provider_id,
        sms_account_id=None,
        conversation_id=conversation.id,
        body="Synthetic intended outbound",
        direction="outbound",
        author_type="staff",
        status="sending",
    )
    db_session.add(outbound)
    db_session.commit()

    result = process_chatwoot_webhook(
        db_session,
        {
            "id": 9303,
            "message_type": "incoming",
            "content": "Synthetic customer inbound",
            "source_id": f"fastapi-chatwoot-message-{outbound.id}",
            "inbox": {"id": binding.chatwoot_inbox_id},
            "conversation": {
                "id": conversation.chatwoot_conversation_id,
                "contact": {"id": conversation.chatwoot_contact_id},
            },
        },
        token="my-webhook-secret",
    )

    db_session.refresh(outbound)
    assert result["duplicate"] is False
    assert outbound.status == "sending"
    assert outbound.chatwoot_message_id is None
    inbound = db_session.query(SmsMessage).filter(
        SmsMessage.chatwoot_message_id == 9303
    ).one()
    assert inbound.direction == "inbound"


def test_outgoing_source_echo_requires_exact_body(db_session, setup_chatwoot_data):
    binding = setup_chatwoot_data["binding"]
    conversation = SmsConversation(
        tenant_id=binding.tenant_id,
        provider_id=binding.provider_id,
        sms_account_id=None,
        customer_address="chatwoot_contact_synthetic_body",
        state="taken-over",
        ai_enabled=False,
        chatwoot_conversation_id=9311,
        chatwoot_contact_id=9312,
        chatwoot_inbox_id=binding.chatwoot_inbox_id,
    )
    db_session.add(conversation)
    db_session.flush()
    outbound = SmsMessage(
        tenant_id=binding.tenant_id,
        provider_id=binding.provider_id,
        sms_account_id=None,
        conversation_id=conversation.id,
        body="Synthetic intended outbound",
        direction="outbound",
        author_type="staff",
        status="sending",
    )
    db_session.add(outbound)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        process_chatwoot_webhook(
            db_session,
            {
                "id": 9313,
                "message_type": "outgoing",
                "content": "Synthetic different staff body",
                "source_id": f"fastapi-chatwoot-message-{outbound.id}",
                "inbox": {"id": binding.chatwoot_inbox_id},
                "conversation": {
                    "id": conversation.chatwoot_conversation_id,
                    "contact": {"id": conversation.chatwoot_contact_id},
                },
            },
            token="my-webhook-secret",
        )
    assert exc_info.value.status_code == 409
    db_session.refresh(outbound)
    assert outbound.chatwoot_message_id is None


@pytest.mark.parametrize(
    ("payload_override", "expected_status"),
    [
        ({"account": {"id": 9999}}, 401),
        ({"conversation": {"id": 9311, "contact": {"id": 9999}}}, 409),
    ],
)
def test_webhook_rejects_contradictory_account_or_contact_binding(
    db_session, setup_chatwoot_data, payload_override, expected_status
):
    binding = setup_chatwoot_data["binding"]
    conversation = SmsConversation(
        tenant_id=binding.tenant_id,
        provider_id=binding.provider_id,
        sms_account_id=None,
        customer_address="chatwoot_contact_synthetic_binding",
        state="paused",
        ai_enabled=False,
        chatwoot_conversation_id=9311,
        chatwoot_contact_id=9312,
        chatwoot_inbox_id=binding.chatwoot_inbox_id,
    )
    db_session.add(conversation)
    db_session.commit()
    payload = {
        "id": 9314,
        "message_type": "incoming",
        "content": "Synthetic binding check",
        "inbox": {"id": binding.chatwoot_inbox_id},
        "conversation": {
            "id": conversation.chatwoot_conversation_id,
            "contact": {"id": conversation.chatwoot_contact_id},
        },
    }
    payload.update(payload_override)

    with pytest.raises(HTTPException) as exc_info:
        process_chatwoot_webhook(
            db_session,
            payload,
            token="my-webhook-secret",
        )
    assert exc_info.value.status_code == expected_status
    assert db_session.query(SmsMessage).filter(
        SmsMessage.chatwoot_message_id == 9314
    ).count() == 0


def test_direct_chatwoot_send_rejects_unpersisted_thread_identity(
    db_session, setup_chatwoot_data
):
    binding = setup_chatwoot_data["binding"]
    conversation = SmsConversation(
        tenant_id=binding.tenant_id,
        provider_id=binding.provider_id,
        sms_account_id=None,
        customer_address="chatwoot_contact_synthetic_direct",
        state="taken-over",
        chatwoot_conversation_id=9321,
        chatwoot_contact_id=9322,
        chatwoot_inbox_id=binding.chatwoot_inbox_id,
    )
    db_session.add(conversation)
    db_session.commit()
    forged = SmsConversation(
        id=conversation.id,
        tenant_id=conversation.tenant_id,
        provider_id=conversation.provider_id,
        sms_account_id=None,
        customer_address=conversation.customer_address,
        state=conversation.state,
        chatwoot_conversation_id=999999,
        chatwoot_contact_id=conversation.chatwoot_contact_id,
        chatwoot_inbox_id=conversation.chatwoot_inbox_id,
    )

    with patch("httpx.AsyncClient") as client_class:
        with pytest.raises(ValueError, match="scope is inconsistent"):
            asyncio.run(
                send_chatwoot_message(db_session, forged, "Synthetic safe response")
            )
    client_class.assert_not_called()


def test_chatwoot_worker_honors_echo_that_wins_before_timeout(
    db_session, setup_chatwoot_data
):
    binding = setup_chatwoot_data["binding"]
    conversation = SmsConversation(
        tenant_id=binding.tenant_id,
        provider_id=binding.provider_id,
        sms_account_id=None,
        customer_address="chatwoot_contact_synthetic_timeout",
        state="taken-over",
        ai_enabled=False,
        chatwoot_conversation_id=9331,
        chatwoot_contact_id=9332,
        chatwoot_inbox_id=binding.chatwoot_inbox_id,
    )
    db_session.add(conversation)
    db_session.flush()
    message = SmsMessage(
        tenant_id=binding.tenant_id,
        provider_id=binding.provider_id,
        sms_account_id=None,
        conversation_id=conversation.id,
        body="Synthetic timeout response",
        direction="outbound",
        author_type="staff",
        status="queued",
    )
    db_session.add(message)
    db_session.flush()
    job = SmsOutboundJob(message_id=message.id, sms_account_id=None, status="PENDING")
    db_session.add(job)
    db_session.commit()

    async def accepted_then_timeout(db, _conversation, _body, source_id=None):
        assert source_id == f"fastapi-chatwoot-message-{message.id}"
        winner = db.query(SmsMessage).filter(SmsMessage.id == message.id).one()
        winner.chatwoot_message_id = 9333
        winner.status = "sent"
        db.commit()
        raise httpx.TimeoutException("synthetic timeout")

    with (
        patch(
            "app.services.sms.chatwoot_service.send_chatwoot_message",
            side_effect=accepted_then_timeout,
        ),
        patch(
            "app.services.sms.ai_orchestrator.process_pending_sms_ai_jobs",
            new=AsyncMock(),
        ),
        patch("app.services.sms.arrival_service.process_repeated_arrival_alerts"),
    ):
        asyncio.run(process_pending_sms_outbound_jobs(db_session))

    db_session.refresh(job)
    db_session.refresh(message)
    assert job.status == "SUCCESS"
    assert job.retry_count == 0
    assert message.status == "sent"
    assert message.chatwoot_message_id == 9333
