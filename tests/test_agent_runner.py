import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.db.database import Base
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.sms_chatwoot import SmsChatwootBinding
from app.services.agent_runner import run_agent_turn
import app.db.async_session
import app.services.agent_runner

@pytest_asyncio.fixture
async def async_test_session(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(app.db.async_session, "AsyncSessionLocal", session_maker)
    
    async with session_maker() as session:
        tenant = Tenant(
            name="Test Tenant",
            subdomain="test-tenant",
            chatwoot_account_id=123
        )
        session.add(tenant)
        await session.flush()
        
        provider = Provider(
            tenant_id=tenant.id,
            name="Test Provider",
            chatwoot_inbox_id=456,
            max_char_limit=160
        )
        session.add(provider)
        await session.flush()
        
        binding = SmsChatwootBinding(
            tenant_id=tenant.id,
            provider_id=provider.id,
            chatwoot_account_id=123,
            chatwoot_inbox_id=456,
            chatwoot_base_url="https://chatwoot.test",
            chatwoot_api_token="test_token",
            is_enabled=True
        )
        session.add(binding)
        await session.commit()
        
        yield session

@pytest.mark.asyncio
async def test_run_agent_turn_end_to_end(async_test_session, monkeypatch):
    calls = []
    async def mock_send_bot_message(**kwargs):
        calls.append(kwargs)
        return {"status": "success"}
        
    monkeypatch.setattr(app.services.agent_runner, "send_bot_message", mock_send_bot_message)
    
    # We call the real function. process_dialogue_turn will process the message.
    await run_agent_turn(
        chatwoot_account_id=123,
        chatwoot_inbox_id=456,
        conversation_id=999,
        sender_phone="+1234567890",
        message_text="Hello"
    )
    
    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["chatwoot_base_url"] == "https://chatwoot.test"
    assert kwargs["account_id"] == 123
    assert kwargs["conversation_id"] == 999
    assert len(kwargs["content"]) > 0

