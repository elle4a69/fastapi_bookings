import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import status
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.client import Client
from app.models.booking import Booking
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_outbox import SmsAiJob, SmsConversationEvent, SmsOutboundJob
from app.services.sms.booking_facade import find_live_availability
from app.services.sms.ai_orchestrator import process_pending_sms_ai_jobs
from app.services.sms.outbox_worker import process_pending_sms_outbound_jobs

@pytest.fixture(autouse=True)
def clear_env_openai_key():
    import os
    orig_key = os.environ.pop("OPENAI_API_KEY", None)
    yield
    if orig_key is not None:
        os.environ["OPENAI_API_KEY"] = orig_key

@pytest.fixture
def setup_integration_data(db_session):
    # 1. Create tenant
    tenant = Tenant(name="Integration Tenant", subdomain="integ")
    db_session.add(tenant)
    db_session.commit()

    # 2. Create provider
    provider = Provider(tenant_id=tenant.id, name="Dr. Alex", active=True)
    db_session.add(provider)
    db_session.commit()

    # 3. Create service and link to provider
    service = Service(tenant_id=tenant.id, name="General Checkup", duration=30, price=100.0)
    db_session.add(service)
    db_session.commit()

    sp = ServiceProvider(tenant_id=tenant.id, provider_id=provider.id, service_id=service.id)
    db_session.add(sp)
    db_session.commit()

    # 4. Create SMS account with AI enabled (draft mode first)
    account = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transport_type="simulator",
        display_name="Line AI",
        sender_address="61488888888",
        is_enabled=True,
        ai_enabled=True,
        ai_mode="draft"  # draft mode by default
    )
    db_session.add(account)
    db_session.commit()

    # 5. Create conversation
    conv = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=account.id,
        customer_address="61412345678",
        state="auto-reply",
        unread_count=0
    )
    db_session.add(conv)
    db_session.commit()

    return {
        "tenant": tenant,
        "provider": provider,
        "service": service,
        "account": account,
        "conversation": conv
    }


def test_booking_availability_facade(db_session, setup_integration_data):
    data = setup_integration_data
    # Verify we can find live availability slots
    slots = find_live_availability(db_session, data["provider"].id, data["service"].id)
    # The provider weekly schedule is not configured, so slots might be empty by default.
    # Let's verify it compiles and runs without throwing errors.
    assert isinstance(slots, list)


def test_ai_orchestration_draft_mode(db_session, setup_integration_data):
    data = setup_integration_data
    conv = data["conversation"]
    acc = data["account"]

    # 1. Simulate inbound message asking for availability
    msg = SmsMessage(
        tenant_id=conv.tenant_id,
        provider_id=conv.provider_id,
        sms_account_id=acc.id,
        conversation_id=conv.id,
        body="I want to book an appointment",
        direction="inbound",
        author_type="customer",
        status="received",
        customer_turn_ref="turn-1",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc)
    )
    db_session.add(msg)
    
    # Enqueue AI Job
    job = SmsAiJob(
        conversation_id=conv.id,
        customer_turn_ref="turn-1",
        status="PENDING",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(job)
    db_session.commit()

    # 2. Run AI Orchestrator
    from unittest.mock import patch, AsyncMock, MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": [{"message": {"content": "Mocked draft response"}}]}
    mock_resp.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client
        mock_client.post.return_value = mock_resp
        asyncio.run(process_pending_sms_ai_jobs(db_session))

    # 3. Verify AI reply is created as a DRAFT message (not enqueued for sending)
    ai_msg = db_session.query(SmsMessage).filter(
        SmsMessage.conversation_id == conv.id,
        SmsMessage.author_type == "ai"
    ).first()
    
    assert ai_msg is not None
    assert ai_msg.direction == "draft"
    assert ai_msg.status == "draft"

    # Verify no SmsOutboundJob is created for draft messages
    job_count = db_session.query(SmsOutboundJob).filter(SmsOutboundJob.message_id == ai_msg.id).count()
    assert job_count == 0


def test_ai_orchestration_autopilot_flow(client, db_session, setup_integration_data):
    data = setup_integration_data
    conv = data["conversation"]
    acc = data["account"]

    # Set AI mode to autopilot
    acc.ai_mode = "autopilot"
    db_session.commit()

    # 1. Simulate inbound message asking for availability
    payload = {
        "message_id": "mm-turn-2",
        "sender": "0412345678",
        "to": acc.sender_address,
        "message": "I want to book a slots tomorrow",
        "received_at": datetime.now(timezone.utc).isoformat()
    }
    resp = client.post(f"/api/sms/webhooks/simulator/{acc.public_id}", json=payload)
    assert resp.status_code == status.HTTP_200_OK

    # 2. Process AI Jobs (bypass debounce delay by shifting run_at to the past)
    from app.models.sms_outbox import SmsAiJob
    db_session.query(SmsAiJob).filter(SmsAiJob.status == "PENDING").update({
        "run_at": datetime.now(timezone.utc) - timedelta(seconds=1)
    })
    db_session.commit()
    
    from unittest.mock import patch, AsyncMock, MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": [{"message": {"content": "Mocked autopilot response"}}]}
    mock_resp.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client
        mock_client.post.return_value = mock_resp
        asyncio.run(process_pending_sms_ai_jobs(db_session))

    # 3. Dynamic requests fail closed into review even in autopilot mode.
    ai_msg = db_session.query(SmsMessage).filter(
        SmsMessage.conversation_id == conv.id,
        SmsMessage.author_type == "ai",
        SmsMessage.customer_turn_ref == "turn_mm-turn-2"
    ).first()
    
    assert ai_msg is not None
    assert ai_msg.direction == "draft"
    assert ai_msg.status == "draft"
    db_session.refresh(conv)
    assert conv.state == "needs-review"

    # Review-first safety: no provider delivery job exists before approval.
    job = db_session.query(SmsOutboundJob).filter(SmsOutboundJob.message_id == ai_msg.id).first()
    assert job is None
