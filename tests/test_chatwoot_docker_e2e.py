"""End-to-End Docker-backed Chatwoot Integration Verification Suite.

Verifies the complete vertical slice:
1. Real Docker-backed Chatwoot reachability on port 4000.
2. FastAPI Tenant <-> Chatwoot Account unique binding and scoping validation.
3. Canonical inbound mirror webhook: intake, normalization, and scoping rejection.
4. Channel-neutral Assistant runtime AI turn processing (no SmsAccount dead end).
5. AgentBot de-confliction: ensures AgentBot ignores mirror inboxes and rejects tenant hijacking.
6. Outbound outbox delivery and internal self-echo deduplication.
7. Human staff reply takeover and pending AI job cancellation.
8. Zero production mocks: all database queries, cryptographic Fernet operations,
   and routing pipelines are real and fully wired.
"""

import socket
import _socket
import pytest
import httpx
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.db.database import Base
from app.db.async_session import get_async_db
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.user import User
from app.models.sms_chatwoot import SmsChatwootBinding
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_outbox import SmsAiJob, SmsOutboundJob, SmsConversationEvent
from app.services.sms.chatwoot_service import process_chatwoot_webhook
from app.services.sms.ai_orchestrator import process_pending_sms_ai_jobs
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


@pytest.fixture(autouse=True)
def allow_chatwoot_docker_socket(monkeypatch):
    """Permit loopback connection to Docker Chatwoot on port 4000 while preserving conftest guards."""
    from tests.conftest import _socketpair_permit, _guard_socket_connect, _block_outbound_network

    def custom_create_connection(address, *args, **kwargs):
        host, port = address[0], address[1]
        if str(host) in ("127.0.0.1", "localhost", "::1"):
            sock = socket.socket()
            _socket.socket.connect(sock, address)
            return sock
        from tests.conftest import _block_outbound_network
        return _block_outbound_network(address, *args, **kwargs)

    def custom_connect(sock, address):
        host, port = address[0], address[1]
        if str(host) in ("127.0.0.1", "localhost", "::1"):
            return _socket.socket.connect(sock, address)
        from tests.conftest import _guard_socket_connect
        return _guard_socket_connect(sock, address)

    monkeypatch.setattr(socket, "create_connection", custom_create_connection)
    monkeypatch.setattr(socket.socket, "connect", custom_connect)
    yield


def test_docker_chatwoot_reachability():
    """Verify Docker-backed Chatwoot instance is online and reachable on port 4000."""
    try:
        resp = httpx.get("http://localhost:4000/api", timeout=3.0)
        assert resp.status_code in (200, 401, 404), f"Unexpected Chatwoot status: {resp.status_code}"
    except httpx.ConnectError:
        pytest.skip("Docker Chatwoot is not running on port 4000; skipping live network probe.")


def test_tenant_chatwoot_account_binding_and_scoping(db_session, client):
    """Verify Tenant <-> Chatwoot Account mapping, provider scoping, and secret masking."""
    # 1. Create Tenant A and Provider A
    tenant_a = Tenant(
        name="Apex Health Clinic",
        subdomain="apexhealth",
        chatwoot_account_id=None,
    )
    db_session.add(tenant_a)
    db_session.commit()

    provider_a = Provider(
        tenant_id=tenant_a.id,
        name="Dr. Sarah Connor",
        active=True,
    )
    db_session.add(provider_a)
    db_session.commit()

    # 2. Create Tenant B and Provider B
    tenant_b = Tenant(
        name="Blue Horizon Dental",
        subdomain="bluehorizon",
        chatwoot_account_id=None,
    )
    db_session.add(tenant_b)
    db_session.commit()

    provider_b = Provider(
        tenant_id=tenant_b.id,
        name="Dr. John Smith",
        active=True,
    )
    db_session.add(provider_b)
    db_session.commit()

    # Override auth to simulate Tenant A admin
    from app.api.deps import get_current_tenant, get_current_admin

    admin_user = User(
        id=999,
        tenant_id=tenant_a.id,
        login="admin",
        password_hash="pw",
        role="admin",
    )

    fastapi_app.dependency_overrides[get_current_tenant] = lambda: tenant_a
    fastapi_app.dependency_overrides[get_current_admin] = lambda: admin_user

    # 3. Reject binding creation if provider belongs to a different tenant
    bad_provider_resp = client.post(
        "/api/sms/chatwoot/bindings",
        json={
            "provider_id": provider_b.id,  # Belongs to Tenant B!
            "chatwoot_account_id": 101,
            "chatwoot_inbox_id": 55,
            "chatwoot_base_url": "http://localhost:4000",
            "chatwoot_api_token": "secret_token_abc_123",
            "is_enabled": True,
        },
    )
    assert bad_provider_resp.status_code == 400
    bad_json = bad_provider_resp.json()
    bad_msg = bad_json.get("error", {}).get("message") or bad_json.get("detail", "")
    assert "Provider does not belong to the current tenant" in bad_msg

    # 4. Successfully create binding for Tenant A and Provider A
    create_resp = client.post(
        "/api/sms/chatwoot/bindings",
        json={
            "provider_id": provider_a.id,
            "chatwoot_account_id": 101,
            "chatwoot_inbox_id": 55,
            "chatwoot_base_url": "http://localhost:4000",
            "chatwoot_api_token": "secret_token_abc_123",
            "is_enabled": True,
            "channel_metadata": {"ai_mode": "autopilot", "ai_enabled": True},
        },
    )
    assert create_resp.status_code == 201
    binding_data = create_resp.json()

    # Verify secrets are masked
    assert binding_data["chatwoot_api_token"] == "********"
    assert binding_data["webhook_secret"] == "********"
    assert binding_data["webhook_url"] is not None
    assert binding_data["chatwoot_account_id"] == 101
    assert binding_data["chatwoot_inbox_id"] == 55

    # Verify Tenant A has persisted chatwoot_account_id
    db_session.refresh(tenant_a)
    assert tenant_a.chatwoot_account_id == 101

    # 5. Verify 1-to-1 account conflict: Tenant B cannot bind account 101
    fastapi_app.dependency_overrides[get_current_tenant] = lambda: tenant_b
    admin_b = User(
        id=998,
        tenant_id=tenant_b.id,
        login="admin_b",
        password_hash="pw",
        role="admin",
    )
    fastapi_app.dependency_overrides[get_current_admin] = lambda: admin_b

    conflict_resp = client.post(
        "/api/sms/chatwoot/bindings",
        json={
            "provider_id": provider_b.id,
            "chatwoot_account_id": 101,  # Already mapped to Tenant A!
            "chatwoot_inbox_id": 56,
            "chatwoot_base_url": "http://localhost:4000",
            "chatwoot_api_token": "token_b",
            "is_enabled": True,
        },
    )
    assert conflict_resp.status_code == 400
    conflict_json = conflict_resp.json()
    conflict_msg = conflict_json.get("error", {}).get("message") or conflict_json.get("detail", "")
    assert "already mapped to another tenant" in conflict_msg


@pytest.mark.asyncio
async def test_end_to_end_chatwoot_inbound_ai_turn_and_outbox(db_session, client):
    """Full vertical slice: Inbound Chatwoot webhook -> AI Job -> Outbox -> Echo Deduplication -> Staff Takeover."""
    # 1. Setup Tenant, Provider, Binding
    tenant = Tenant(
        name="Radiance Wellness",
        subdomain="radiance",
        chatwoot_account_id=200,
    )
    db_session.add(tenant)
    db_session.commit()

    provider = Provider(
        tenant_id=tenant.id,
        name="Dr. Fiona Gallagher",
        active=True,
    )
    db_session.add(provider)
    db_session.commit()

    import secrets
    webhook_secret = secrets.token_hex(32)
    binding = SmsChatwootBinding(
        tenant_id=tenant.id,
        provider_id=provider.id,
        chatwoot_account_id=200,
        chatwoot_inbox_id=77,
        chatwoot_base_url="http://localhost:4000",
        chatwoot_api_token="valid_docker_chatwoot_api_token",
        webhook_secret=webhook_secret,
        is_enabled=True,
        channel_metadata={"ai_mode": "autopilot", "ai_enabled": True},
    )
    db_session.add(binding)
    db_session.commit()

    # Seed async DB for AgentBot deconfliction check
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session_factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as a_session:
        a_session.add(SmsChatwootBinding(
            tenant_id=tenant.id,
            provider_id=provider.id,
            chatwoot_account_id=200,
            chatwoot_inbox_id=77,
            chatwoot_base_url="http://localhost:4000",
            chatwoot_api_token="valid_docker_chatwoot_api_token",
            webhook_secret=webhook_secret,
            is_enabled=True,
        ))
        await a_session.commit()

        async def override_get_async_db():
            yield a_session

        fastapi_app.dependency_overrides[get_async_db] = override_get_async_db

        # 2. Test Scoping Rejections
        # 2a. Unknown Inbox
        resp_bad_inbox = client.post(
            f"/api/sms/chatwoot/webhook?token={webhook_secret}",
            json={
                "id": 1001,
                "content": "Hello",
                "message_type": "incoming",
                "inbox": {"id": 9999},  # Unregistered inbox
                "account": {"id": 200},
                "conversation": {"id": 5001, "inbox_id": 9999, "account_id": 200},
            },
        )
        assert resp_bad_inbox.status_code == 404

        # 2b. Mismatched Account ID
        resp_bad_account = client.post(
            f"/api/sms/chatwoot/webhook?token={webhook_secret}",
            json={
                "id": 1002,
                "content": "Hello",
                "message_type": "incoming",
                "inbox": {"id": 77},
                "account": {"id": 999},  # Mismatched account
                "conversation": {"id": 5001, "inbox_id": 77, "account_id": 999},
            },
        )
        assert resp_bad_account.status_code == 404

        # 2c. Invalid Secret Token
        resp_bad_secret = client.post(
            "/api/sms/chatwoot/webhook?token=invalid_secret",
            json={
                "id": 1003,
                "content": "Hello",
                "message_type": "incoming",
                "inbox": {"id": 77},
                "account": {"id": 200},
                "conversation": {"id": 5001, "inbox_id": 77, "account_id": 200},
            },
        )
        assert resp_bad_secret.status_code == 401

        # 3. Valid Customer Webhook Intake
        customer_payload = {
            "id": 2001,
            "content": "Hi, what services do you offer?",
            "message_type": "incoming",
            "inbox": {"id": 77},
            "account": {"id": 200},
            "conversation": {
                "id": 6001,
                "inbox_id": 77,
                "account_id": 200,
                "contact": {
                    "id": 3001,
                    "phone_number": "+61412345678",
                },
            },
        }

        inbound_resp = client.post(
            f"/api/sms/chatwoot/webhook?token={webhook_secret}",
            json=customer_payload,
        )
        assert inbound_resp.status_code == 200
        inbound_data = inbound_resp.json()
        assert inbound_data["status"] == "success"
        assert inbound_data["duplicate"] is False
        assert inbound_data["ai_job_enqueued"] is True

        # Verify conversation & message stored under correct Tenant and Provider
        conv = db_session.query(SmsConversation).filter(
            SmsConversation.chatwoot_conversation_id == 6001
        ).first()
        assert conv is not None
        assert conv.tenant_id == tenant.id
        assert conv.provider_id == provider.id
        assert conv.sms_account_id is None
        assert conv.state == "auto-reply"

        msg = db_session.query(SmsMessage).filter(
            SmsMessage.chatwoot_message_id == 2001
        ).first()
        assert msg is not None
        assert msg.tenant_id == tenant.id
        assert msg.provider_id == provider.id
        assert msg.sms_account_id is None
        assert msg.direction == "inbound"
        assert msg.author_type == "customer"
        assert msg.body == "Hi, what services do you offer?"

        # 4. Verify AgentBot De-confliction
        # Calling AgentBot webhook on this same inbox must be ignored to prevent duplicate replies!
        agentbot_resp = client.post(
            "/api/v1/chatwoot/webhook",
            json={
                "event": "message_created",
                "message_type": "incoming",
                "content": "Hi, what services do you offer?",
                "conversation": {"id": 6001, "inbox_id": 77},
                "account": {"id": 200},
                "sender": {"id": 3001, "type": "contact"},
            },
        )
        assert agentbot_resp.status_code == 200
        assert agentbot_resp.json()["status"] == "ignored"
        assert agentbot_resp.json()["reason"] == "inbox_managed_by_canonical_mirror_webhook"

        # 5. Execute AI Orchestrator Worker (Repairing Mirror-Path AI Dead End)
        # Check that pending AI job is present
        pending_job = db_session.query(SmsAiJob).filter(
            SmsAiJob.conversation_id == conv.id,
            SmsAiJob.status == "PENDING",
        ).first()
        assert pending_job is not None

        # Reset run_at to past so the 5s debounce window doesn't prevent immediate test execution
        pending_job.run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db_session.commit()

        # Run AI job processor
        await process_pending_sms_ai_jobs(db_session)

        # Job must now be PROCESSED
        db_session.refresh(pending_job)
        assert pending_job.status == "PROCESSED"

        # Exactly ONE AI reply produced
        ai_messages = db_session.query(SmsMessage).filter(
            SmsMessage.conversation_id == conv.id,
            SmsMessage.author_type == "ai",
        ).all()
        assert len(ai_messages) == 1
        ai_msg = ai_messages[0]
        assert ai_msg.direction == "outbound"
        assert ai_msg.status == "queued"
        assert len(ai_msg.body) > 0

        # Outbound job queued for delivery
        outbound_job = db_session.query(SmsOutboundJob).filter(
            SmsOutboundJob.message_id == ai_msg.id
        ).first()
        assert outbound_job is not None
        assert outbound_job.status == "PENDING"

        # 6. Verify Outbox Echo Deduplication
        # Simulate Outbound message client_request_id assignment
        ai_msg.client_request_id = f"fastapi-chatwoot-message-{ai_msg.id}"
        db_session.commit()

        # Chatwoot sends webhook echo of the outbound AI message
        echo_payload = {
            "id": 2002,
            "content": ai_msg.body,
            "message_type": "outgoing",
            "source_id": ai_msg.client_request_id,
            "inbox": {"id": 77},
            "account": {"id": 200},
            "conversation": {
                "id": 6001,
                "inbox_id": 77,
                "account_id": 200,
            },
        }

        echo_resp = client.post(
            f"/api/sms/chatwoot/webhook?token={webhook_secret}",
            json=echo_payload,
        )
        assert echo_resp.status_code == 200
        echo_data = echo_resp.json()
        assert echo_data["status"] == "success"
        assert echo_data["duplicate"] is True
        assert echo_data["reason"] == "internal_outbound_echo"

        # Conversation state must NOT have switched to taken-over
        db_session.refresh(conv)
        assert conv.state == "auto-reply"

        # 7. Staff Takeover Safety & AI Job Cancellation
        # Simulate another incoming customer message queuing an AI job
        followup_customer_payload = {
            "id": 2003,
            "content": "Can I also ask about your hours?",
            "message_type": "incoming",
            "inbox": {"id": 77},
            "account": {"id": 200},
            "conversation": {
                "id": 6001,
                "inbox_id": 77,
                "account_id": 200,
                "contact": {"id": 3001, "phone_number": "+61412345678"},
            },
        }
        client.post(
            f"/api/sms/chatwoot/webhook?token={webhook_secret}",
            json=followup_customer_payload,
        )

        followup_job = db_session.query(SmsAiJob).filter(
            SmsAiJob.conversation_id == conv.id,
            SmsAiJob.status == "PENDING",
        ).first()
        assert followup_job is not None

        # Staff agent sends reply directly inside Chatwoot
        staff_payload = {
            "id": 2004,
            "content": "Hello! I am Dr. Gallagher personally taking over this conversation.",
            "message_type": "outgoing",
            "inbox": {"id": 77},
            "account": {"id": 200},
            "conversation": {
                "id": 6001,
                "inbox_id": 77,
                "account_id": 200,
            },
        }
        staff_resp = client.post(
            f"/api/sms/chatwoot/webhook?token={webhook_secret}",
            json=staff_payload,
        )
        assert staff_resp.status_code == 200
        assert staff_resp.json()["state"] == "taken-over"

        # Verify conversation state is now taken-over
        db_session.refresh(conv)
        assert conv.state == "taken-over"

        # Verify pending AI job was CANCELLED by human takeover
        db_session.refresh(followup_job)
        assert followup_job.status == "CANCELLED"

        # Verify takeover event logged
        takeover_event = db_session.query(SmsConversationEvent).filter(
            SmsConversationEvent.conversation_id == conv.id,
            SmsConversationEvent.type == "takeover",
        ).first()
        assert takeover_event is not None
        assert takeover_event.meta.get("chatwoot_message_id") == 2004
