import pytest
import pytest_asyncio
import httpx
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.services.contact_sync import sync_client_projection_to_chatwoot
from app.models.client import Client
from app.models.sms_chatwoot import SmsChatwootBinding
from app.models.tenant import Tenant

pytestmark = pytest.mark.asyncio

@pytest_asyncio.fixture
async def async_db_and_data():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        # Create tenant
        tenant = Tenant(name="Test Tenant", subdomain="test-tenant", subscription_tier="starter")
        session.add(tenant)
        await session.flush()

        # Create client
        client = Client(
            tenant_id=tenant.id,
            name="Test User",
            phone="+123456789",
            email="test@test.com",
            street_address="123 Test St",
            suburb="Test Suburb",
            postcode="1234"
        )
        session.add(client)
        
        # Create binding
        binding = SmsChatwootBinding(
            tenant_id=tenant.id,
            chatwoot_account_id=1,
            chatwoot_inbox_id=1,
            chatwoot_base_url="http://chatwoot.test",
            is_enabled=True
        )
        binding.chatwoot_api_token = "secret_token_123"
        session.add(binding)
        
        await session.commit()
        await session.refresh(client)
        await session.refresh(binding)
        
        yield session, tenant, client, binding

    await engine.dispose()


async def test_sync_client_existing_contact(async_db_and_data):
    db, tenant, client, binding = async_db_and_data
    
    def handler(request: httpx.Request):
        if "search" in str(request.url):
            return httpx.Response(200, json={"payload": [{"id": 999}]})
        elif request.method == "PUT":
            return httpx.Response(200, json={})
        return httpx.Response(404)
        
    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport)
    
    with patch("app.services.contact_sync.httpx.AsyncClient", return_value=mock_client):
        await sync_client_projection_to_chatwoot(db, client.id, tenant.id, 1)
        
    await db.refresh(client)
    assert client.chatwoot_contact_id == 999


async def test_sync_client_new_contact(async_db_and_data):
    db, tenant, client, binding = async_db_and_data
    
    def handler(request: httpx.Request):
        if "search" in str(request.url):
            return httpx.Response(200, json={"payload": []})
        elif request.method == "POST":
            return httpx.Response(200, json={"payload": {"contact": {"id": 888}}})
        return httpx.Response(404)
        
    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport)
    
    with patch("app.services.contact_sync.httpx.AsyncClient", return_value=mock_client):
        await sync_client_projection_to_chatwoot(db, client.id, tenant.id, 1)
        
    await db.refresh(client)
    assert client.chatwoot_contact_id == 888


async def test_sync_client_not_found(async_db_and_data):
    db, tenant, client, binding = async_db_and_data
    
    called = False
    def handler(request: httpx.Request):
        nonlocal called
        called = True
        return httpx.Response(404)
        
    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport)
    
    with patch("app.services.contact_sync.httpx.AsyncClient", return_value=mock_client):
        await sync_client_projection_to_chatwoot(db, 9999, tenant.id, 1)
        
    assert not called


async def test_sync_client_http_failure_resilience(async_db_and_data):
    db, tenant, client, binding = async_db_and_data
    
    def handler(request: httpx.Request):
        raise httpx.RequestError("Network Error")
        
    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport)
    
    with patch("app.services.contact_sync.httpx.AsyncClient", return_value=mock_client):
        await sync_client_projection_to_chatwoot(db, client.id, tenant.id, 1)
        
    await db.refresh(client)
    assert client.chatwoot_contact_id is None
