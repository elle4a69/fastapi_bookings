import pytest
import os
import httpx
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.service import Service
from app.models.service_provider import ServiceProvider
from app.models.client import Client
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_outbox import SmsAiJob, SmsConversationEvent, SmsOutboundJob
from app.models.sms_knowledge import SmsKnowledgeEntry, SmsPromptProfile

from app.services.sms.ai_orchestrator import run_ai_orchestration, call_openai_chat_completions

@pytest.fixture
def setup_openai_test_data(db_session):
    # 1. Tenant
    tenant = Tenant(name="OpenAI Test Tenant", subdomain="openai-test")
    db_session.add(tenant)
    db_session.commit()

    # 2. Provider
    provider = Provider(tenant_id=tenant.id, name="Dr. Alex", active=True)
    db_session.add(provider)
    db_session.commit()

    # 3. Service & link
    service = Service(tenant_id=tenant.id, name="Checkup", duration=30, price=50.0)
    db_session.add(service)
    db_session.commit()

    sp = ServiceProvider(tenant_id=tenant.id, provider_id=provider.id, service_id=service.id)
    db_session.add(sp)
    db_session.commit()

    # 4. SMS Account (AI enabled, autopilot)
    account = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transport_type="simulator",
        display_name="Line OpenAI",
        sender_address="61499999999",
        is_enabled=True,
        ai_enabled=True,
        ai_mode="autopilot",
        line_prompt="This is the line prompt for OpenAI Line."
    )
    db_session.add(account)
    db_session.commit()

    # 5. Conversation
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

    # 6. Active Prompt Profile
    prompt_profile = SmsPromptProfile(
        tenant_id=tenant.id,
        provider_id=provider.id,
        name="Alex Prompt Profile",
        system_prompt="This is the active prompt profile for Dr. Alex.",
        is_active=True
    )
    db_session.add(prompt_profile)

    # 7. Knowledge Entries
    knowledge_generic = SmsKnowledgeEntry(
        tenant_id=tenant.id,
        provider_id=None,
        category="policy",
        text="Generic Policy: No cancellations under 24 hours.",
        status="approved"
    )
    knowledge_provider = SmsKnowledgeEntry(
        tenant_id=tenant.id,
        provider_id=provider.id,
        category="location",
        text="Alex Location: 123 Main St.",
        status="approved"
    )
    knowledge_proposed = SmsKnowledgeEntry(
        tenant_id=tenant.id,
        provider_id=provider.id,
        category="faq",
        text="Alex Proposed: This should not be included.",
        status="proposed"
    )
    db_session.add_all([knowledge_generic, knowledge_provider, knowledge_proposed])
    db_session.commit()

    return {
        "tenant": tenant,
        "provider": provider,
        "service": service,
        "account": account,
        "conversation": conv,
        "prompt_profile": prompt_profile,
        "knowledge_generic": knowledge_generic,
        "knowledge_provider": knowledge_provider
    }

def test_openai_integration_success(db_session, setup_openai_test_data):
    data = setup_openai_test_data
    account = data["account"]
    conv = data["conversation"]
    
    # Set credentials containing api_key
    account.credentials = {"api_key": "sk-test-mock-key"}
    db_session.commit()

    # Create inbound message to start conversation (prior messages)
    msg_prior = SmsMessage(
        tenant_id=conv.tenant_id,
        provider_id=conv.provider_id,
        sms_account_id=account.id,
        conversation_id=conv.id,
        body="Prior message from customer",
        direction="inbound",
        author_type="customer",
        status="received",
        customer_turn_ref="turn-prior",
        occurred_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        received_at=datetime.now(timezone.utc) - timedelta(minutes=5)
    )
    db_session.add(msg_prior)

    # Create current turn inbound message
    msg_current = SmsMessage(
        tenant_id=conv.tenant_id,
        provider_id=conv.provider_id,
        sms_account_id=account.id,
        conversation_id=conv.id,
        body="I want to book an appointment",
        direction="inbound",
        author_type="customer",
        status="received",
        customer_turn_ref="turn-current",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc)
    )
    db_session.add(msg_current)
    db_session.commit()

    # Mock response from OpenAI
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Mocked response from OpenAI!"
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    # Mock AsyncClient
    with patch("httpx.AsyncClient") as mock_client_class, \
         patch("app.core.config.settings.OPENAI_API_KEY", "sk-test-mock-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client
        mock_client.post.return_value = mock_resp

        import asyncio
        asyncio.run(run_ai_orchestration(db_session, account, conv, "turn-current"))

        # Verify post called
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        url = call_args[0][0]
        kwargs = call_args[1]
        
        assert url == "https://api.openai.com/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer sk-test-mock-key"
        
        payload = kwargs["json"]
        assert payload["model"] == "gpt-4o-mini"
        
        messages = payload["messages"]
        # System instructions
        assert "Immutable Platform Safety Rules" in messages[0]["content"]
        assert "This is the active prompt profile for Dr. Alex." in messages[1]["content"]
        assert "This is the line prompt for OpenAI Line." not in [m["content"] for m in messages]

        # Knowledge entries
        assert messages[2]["content"] == "Context Knowledge: Generic Policy: No cancellations under 24 hours."
        assert messages[3]["content"] == "Context Knowledge: Alex Location: 123 Main St."
        # No proposed knowledge
        assert "Alex Proposed" not in [m["content"] for m in messages]

        # Prior messages
        assert messages[4]["role"] == "user"
        assert messages[4]["content"] == "Prior message from customer"

        # Current turn
        assert messages[5]["role"] == "user"
        assert messages[5]["content"] == "I want to book an appointment"

        # Assert that current turn does not duplicate history
        assert messages[4]["content"] != messages[5]["content"]

    # Verify AI reply is enqueued
    ai_msg = db_session.query(SmsMessage).filter(
        SmsMessage.conversation_id == conv.id,
        SmsMessage.author_type == "ai",
        SmsMessage.customer_turn_ref == "turn-current"
    ).first()
    assert ai_msg is not None
    assert ai_msg.body == "Mocked response from OpenAI!"
    assert ai_msg.direction == "outbound"
    assert ai_msg.status == "queued"

def test_openai_fallback_missing_key(db_session, setup_openai_test_data):
    data = setup_openai_test_data
    account = data["account"]
    conv = data["conversation"]
    
    # Ensure credentials are empty and env is empty
    account.credentials = {}
    db_session.commit()

    with patch("app.core.config.settings.OPENAI_API_KEY", None), patch.dict(os.environ, {}, clear=True):
        # Create current turn inbound message
        msg_current = SmsMessage(
            tenant_id=conv.tenant_id,
            provider_id=conv.provider_id,
            sms_account_id=account.id,
            conversation_id=conv.id,
            body="book",
            direction="inbound",
            author_type="customer",
            status="received",
            customer_turn_ref="turn-current-fallback-key",
            occurred_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc)
        )
        db_session.add(msg_current)
        db_session.commit()

        import asyncio
        asyncio.run(run_ai_orchestration(db_session, account, conv, "turn-current-fallback-key"))

        # Verify AI reply is enqueued, but it comes from the local rules engine
        ai_msg = db_session.query(SmsMessage).filter(
            SmsMessage.conversation_id == conv.id,
            SmsMessage.author_type == "ai",
            SmsMessage.customer_turn_ref == "turn-current-fallback-key"
        ).first()
        
        assert ai_msg is not None
        assert "We have the following openings" in ai_msg.body or "No open slots" in ai_msg.body

def test_openai_fallback_http_error(db_session, setup_openai_test_data):
    data = setup_openai_test_data
    account = data["account"]
    conv = data["conversation"]
    
    # Set credentials containing api_key
    account.credentials = {"api_key": "sk-test-mock-key"}
    db_session.commit()

    # Create current turn inbound message asking for availability
    msg_current = SmsMessage(
        tenant_id=conv.tenant_id,
        provider_id=conv.provider_id,
        sms_account_id=account.id,
        conversation_id=conv.id,
        body="book",
        direction="inbound",
        author_type="customer",
        status="received",
        customer_turn_ref="turn-current-fallback-http",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc)
    )
    db_session.add(msg_current)
    db_session.commit()

    # Mock HTTP Error
    with patch("httpx.AsyncClient") as mock_client_class, \
         patch("app.core.config.settings.OPENAI_API_KEY", "sk-test-mock-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client
        mock_client.post.side_effect = httpx.HTTPError("Connection failed")

        import asyncio
        asyncio.run(run_ai_orchestration(db_session, account, conv, "turn-current-fallback-http"))

        # Verify AI reply is enqueued, and it comes from the local rules engine
        ai_msg = db_session.query(SmsMessage).filter(
            SmsMessage.conversation_id == conv.id,
            SmsMessage.author_type == "ai",
            SmsMessage.customer_turn_ref == "turn-current-fallback-http"
        ).first()
        
        assert ai_msg is not None
        assert "We have the following openings" in ai_msg.body or "No open slots" in ai_msg.body

def test_openai_fallback_timeout(db_session, setup_openai_test_data):
    data = setup_openai_test_data
    account = data["account"]
    conv = data["conversation"]
    
    # Set credentials containing api_key
    account.credentials = {"api_key": "sk-test-mock-key"}
    db_session.commit()

    # Create current turn inbound message asking for availability
    msg_current = SmsMessage(
        tenant_id=conv.tenant_id,
        provider_id=conv.provider_id,
        sms_account_id=account.id,
        conversation_id=conv.id,
        body="book",
        direction="inbound",
        author_type="customer",
        status="received",
        customer_turn_ref="turn-current-fallback-timeout",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc)
    )
    db_session.add(msg_current)
    db_session.commit()

    # Mock Timeout Exception
    with patch("httpx.AsyncClient") as mock_client_class, \
         patch("app.core.config.settings.OPENAI_API_KEY", "sk-test-mock-key"):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client_class.return_value = mock_client
        mock_client.post.side_effect = httpx.TimeoutException("Timeout duration exceeded")

        import asyncio
        asyncio.run(run_ai_orchestration(db_session, account, conv, "turn-current-fallback-timeout"))

        # Verify AI reply is enqueued, and it comes from the local rules engine
        ai_msg = db_session.query(SmsMessage).filter(
            SmsMessage.conversation_id == conv.id,
            SmsMessage.author_type == "ai",
            SmsMessage.customer_turn_ref == "turn-current-fallback-timeout"
        ).first()
        
        assert ai_msg is not None
        assert "We have the following openings" in ai_msg.body or "No open slots" in ai_msg.body
