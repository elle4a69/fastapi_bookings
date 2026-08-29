import pytest
from datetime import datetime, timezone, timedelta
from fastapi import status
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.user import User
from app.models.client import Client
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_message import SmsMessage
from app.models.sms_receipt import SmsInboundReceipt
from app.models.sms_outbox import SmsOutboundJob
from app.services.sms.transports.fake import FakeTransportAdapter

@pytest.fixture
def setup_sms_test_data(db_session):
    # 1. Create a tenant
    tenant = Tenant(name="SMS Test Tenant", subdomain="sms-test")
    db_session.add(tenant)
    db_session.commit()

    # 2. Create an admin user
    admin = User(tenant_id=tenant.id, login="admin@smstest.com", password_hash="hash", role="admin")
    db_session.add(admin)
    db_session.commit()

    # 3. Create two providers
    provider_a = Provider(tenant_id=tenant.id, name="Provider A", active=True)
    provider_b = Provider(tenant_id=tenant.id, name="Provider B", active=True)
    db_session.add_all([provider_a, provider_b])
    db_session.commit()

    # 4. Create two SMS accounts (one for Provider A, one for Provider B)
    account_a = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider_a.id,
        transport_type="simulator",
        display_name="Line A",
        sender_address="61400000001",
        is_enabled=True
    )
    account_b = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider_b.id,
        transport_type="simulator",
        display_name="Line B",
        sender_address="61400000002",
        is_enabled=True
    )
    db_session.add_all([account_a, account_b])
    db_session.commit()

    # 5. Create a client with matching phone
    client = Client(tenant_id=tenant.id, name="John Doe", phone="0400000000", active=True)
    db_session.add(client)
    db_session.commit()

    return {
        "tenant": tenant,
        "admin": admin,
        "provider_a": provider_a,
        "provider_b": provider_b,
        "account_a": account_a,
        "account_b": account_b,
        "client": client,
        "headers": {"X-Tenant": "sms-test", "X-Token": "mock-admin-token"}
    }


def test_provider_and_account_isolation(client, setup_sms_test_data, db_session):
    headers = setup_sms_test_data["headers"]
    acc_a = setup_sms_test_data["account_a"]
    acc_b = setup_sms_test_data["account_b"]

    # Send inbound to Account A
    payload_a = {
        "message_id": "evt-a-1",
        "sender": "0400 000 000",
        "to": acc_a.sender_address,
        "message": "Hello Line A",
        "received_at": datetime.now(timezone.utc).isoformat()
    }
    resp_a = client.post(f"/api/sms/webhooks/simulator/{acc_a.public_id}", json=payload_a)
    assert resp_a.status_code == status.HTTP_200_OK
    assert resp_a.json()["duplicate"] is False

    # Send inbound to Account B from the SAME customer number
    payload_b = {
        "message_id": "evt-b-1",
        "sender": "0400 000 000",
        "to": acc_b.sender_address,
        "message": "Hello Line B",
        "received_at": datetime.now(timezone.utc).isoformat()
    }
    resp_b = client.post(f"/api/sms/webhooks/simulator/{acc_b.public_id}", json=payload_b)
    assert resp_b.status_code == status.HTTP_200_OK
    assert resp_b.json()["duplicate"] is False

    # Assert that we have two completely distinct conversations in the DB
    conversations = db_session.query(SmsConversation).all()
    assert len(conversations) == 2
    assert conversations[0].id != conversations[1].id
    assert conversations[0].sms_account_id == acc_a.id
    assert conversations[1].sms_account_id == acc_b.id

    # Check client linkage (0400 000 000 normalizes to 61400000000)
    assert conversations[0].client_id == setup_sms_test_data["client"].id
    assert conversations[1].client_id == setup_sms_test_data["client"].id

    # Fetch messages list for conversation A
    resp_messages_a = client.get(f"/api/admin/sms/conversations/{conversations[0].id}/messages", headers=headers)
    assert resp_messages_a.status_code == status.HTTP_200_OK
    messages_a = resp_messages_a.json()
    assert len(messages_a) == 1
    assert messages_a[0]["body"] == "Hello Line A"

    # Fetch messages list for conversation B
    resp_messages_b = client.get(f"/api/admin/sms/conversations/{conversations[1].id}/messages", headers=headers)
    assert resp_messages_b.status_code == status.HTTP_200_OK
    messages_b = resp_messages_b.json()
    assert len(messages_b) == 1
    assert messages_b[0]["body"] == "Hello Line B"


def test_inbound_webhook_idempotency(client, setup_sms_test_data, db_session):
    acc_a = setup_sms_test_data["account_a"]
    payload = {
        "message_id": "evt-idemp-1",
        "sender": "0400 000 000",
        "to": acc_a.sender_address,
        "message": "First Send",
        "received_at": datetime.now(timezone.utc).isoformat()
    }

    # Send first time
    resp1 = client.post(f"/api/sms/webhooks/simulator/{acc_a.public_id}", json=payload)
    assert resp1.status_code == status.HTTP_200_OK
    assert resp1.json()["duplicate"] is False

    # Send second time (retry payload)
    resp2 = client.post(f"/api/sms/webhooks/simulator/{acc_a.public_id}", json=payload)
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["duplicate"] is True

    # Assert only one message and receipt was stored in database
    messages = db_session.query(SmsMessage).all()
    assert len(messages) == 1
    assert messages[0].body == "First Send"

    receipts = db_session.query(SmsInboundReceipt).all()
    assert len(receipts) == 1
    assert receipts[0].event_key == "evt-idemp-1"


def test_chronological_rendering_order(client, setup_sms_test_data, db_session):
    headers = setup_sms_test_data["headers"]
    acc_a = setup_sms_test_data["account_a"]

    # Pre-create conversation
    conv = SmsConversation(
        tenant_id=acc_a.tenant_id,
        provider_id=acc_a.provider_id,
        sms_account_id=acc_a.id,
        customer_address="61400000000",
        state="auto-reply",
        unread_count=0
    )
    db_session.add(conv)
    db_session.commit()

    now = datetime.now(timezone.utc)

    # Insert messages out of order by ID but with correct occurred_at
    msg3 = SmsMessage(
        tenant_id=acc_a.tenant_id, provider_id=acc_a.provider_id, sms_account_id=acc_a.id,
        conversation_id=conv.id, body="Third", direction="inbound", author_type="customer",
        occurred_at=now + timedelta(seconds=20), received_at=now + timedelta(seconds=20)
    )
    msg1 = SmsMessage(
        tenant_id=acc_a.tenant_id, provider_id=acc_a.provider_id, sms_account_id=acc_a.id,
        conversation_id=conv.id, body="First", direction="inbound", author_type="customer",
        occurred_at=now, received_at=now
    )
    msg2 = SmsMessage(
        tenant_id=acc_a.tenant_id, provider_id=acc_a.provider_id, sms_account_id=acc_a.id,
        conversation_id=conv.id, body="Second", direction="inbound", author_type="customer",
        occurred_at=now + timedelta(seconds=10), received_at=now + timedelta(seconds=10)
    )

    db_session.add_all([msg3, msg1, msg2])
    db_session.commit()

    # Call messages endpoint
    resp = client.get(f"/api/admin/sms/conversations/{conv.id}/messages", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    msgs = resp.json()
    assert len(msgs) == 3
    
    # Must be sorted First -> Second -> Third
    assert msgs[0]["body"] == "First"
    assert msgs[1]["body"] == "Second"
    assert msgs[2]["body"] == "Third"


def test_durable_outbox_queue_and_leasing(client, setup_sms_test_data, db_session):
    import asyncio
    headers = setup_sms_test_data["headers"]
    acc_a = setup_sms_test_data["account_a"]

    # Pre-create conversation
    conv = SmsConversation(
        tenant_id=acc_a.tenant_id,
        provider_id=acc_a.provider_id,
        sms_account_id=acc_a.id,
        customer_address="61400000000",
        state="taken-over",
        unread_count=0
    )
    db_session.add(conv)
    db_session.commit()

    # Clear prior fake sent messages
    FakeTransportAdapter.sent_messages.clear()

    # Post manual reply (triggers queueing)
    reply_payload = {
        "body": "Test manual outbound queueing",
        "client_request_id": "req-outbound-1"
    }
    resp = client.post(f"/api/admin/sms/conversations/{conv.id}/messages", json=reply_payload, headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    message_id = resp.json()["id"]

    # Verify SMS job is created and status is PENDING
    job = db_session.query(SmsOutboundJob).filter(SmsOutboundJob.message_id == message_id).first()
    assert job is not None
    assert job.status == "PENDING"

    # Process outbound jobs manually
    from app.services.sms.outbox_worker import process_pending_sms_outbound_jobs
    asyncio.run(process_pending_sms_outbound_jobs(db=db_session))

    # Check job is now SUCCESS
    db_session.refresh(job)
    assert job.status == "SUCCESS"

    # Verify message status updated to 'sent'
    msg = db_session.query(SmsMessage).filter(SmsMessage.id == message_id).first()
    assert msg.status == "sent"
    assert msg.provider_message_id is not None

    # Check that message was delivered to fake adapter
    assert len(FakeTransportAdapter.sent_messages) == 1
    assert FakeTransportAdapter.sent_messages[0]["body"] == "Test manual outbound queueing"
    assert FakeTransportAdapter.sent_messages[0]["to"] == "61400000000"


def test_sms_credentials_encryption(db_session, setup_sms_test_data):
    acc = setup_sms_test_data["account_a"]
    creds_to_save = {"api_key": "secret_key_12345", "password": "super_secret_password"}
    
    acc.credentials = creds_to_save
    db_session.commit()
    
    # Force reload object from DB
    db_session.refresh(acc)
    
    # Verify that the transparent property decrypts it correctly
    assert acc.credentials == creds_to_save
    
    # Verify that the underlying database column has encrypted wrapper format
    raw_db_val = acc._credentials
    assert "encrypted_data" in raw_db_val
    assert raw_db_val["encrypted_data"] != "secret_key_12345"


def test_outbound_safety_blocklist(db_session, setup_sms_test_data):
    acc = setup_sms_test_data["account_a"]
    
    conv = SmsConversation(
        tenant_id=acc.tenant_id,
        provider_id=acc.provider_id,
        sms_account_id=acc.id,
        customer_address="61400000000",
        state="auto-reply",
        unread_count=0
    )
    db_session.add(conv)
    db_session.commit()
    
    from app.services.sms.outbound_service import enqueue_outbound_message_transactional
    from app.models.sms_outbox import SmsConversationEvent
    
    # Try sending safe message
    msg1 = enqueue_outbound_message_transactional(
        db=db_session,
        account=acc,
        conversation=conv,
        body="Hello customer, how can I help you?",
        author_type="ai"
    )
    assert msg1.status == "queued"
    
    # Try sending unsafe message containing leak term "system_prompt"
    msg2 = enqueue_outbound_message_transactional(
        db=db_session,
        account=acc,
        conversation=conv,
        body="This is an internal system_prompt leak text",
        author_type="ai"
    )
    # Must be marked failed immediately and not enqueued in outbox jobs
    assert msg2.status == "failed"
    
    # No SmsOutboundJob should exist for msg2
    job = db_session.query(SmsOutboundJob).filter(SmsOutboundJob.message_id == msg2.id).first()
    assert job is None
    
    # Safety block event should exist
    event = db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == conv.id,
        SmsConversationEvent.type == "outbound_safety_blocked"
    ).first()
    assert event is not None
    assert event.meta["message_id"] == msg2.id


def test_amend_booking_facade(db_session, setup_sms_test_data):
    acc = setup_sms_test_data["account_a"]
    tenant_id = acc.tenant_id
    
    # Create required service & booking structures
    from app.models.service import Service
    from app.models.booking import Booking
    
    service = Service(
        tenant_id=tenant_id,
        name="Test Service",
        duration=30,  # 30 minutes
        price=100.0,
        active=True
    )
    db_session.add(service)
    db_session.commit()
    
    booking = Booking(
        tenant_id=tenant_id,
        client_id=setup_sms_test_data["client"].id,
        provider_id=acc.provider_id,
        service_id=service.id,
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, minutes=30),
        status="confirmed",
        idempotency_key="key-amend-test"
    )
    db_session.add(booking)
    db_session.commit()
    
    from app.services.sms.booking_facade import amend_booking
    
    new_start_time = datetime.now(timezone.utc) + timedelta(days=1, hours=2)
    res = amend_booking(
        db=db_session,
        tenant_id=tenant_id,
        booking_id=booking.id,
        start_time=new_start_time,
        idempotency_key="key-amend-test-2"
    )
    
    assert res["status"] == "confirmed"
    assert res["duplicate"] is False
    
    # Verify booking start_time and end_time updated
    db_session.refresh(booking)
    assert booking.start_time.replace(tzinfo=timezone.utc) == new_start_time
    assert booking.end_time.replace(tzinfo=timezone.utc) == new_start_time + timedelta(minutes=30)


def test_list_conversation_messages_with_null_sms_account_id(client, db_session, setup_sms_test_data):
    from app.core.security import create_access_token
    tenant = setup_sms_test_data["tenant"]
    admin = setup_sms_test_data["admin"]
    provider = setup_sms_test_data["provider_a"]
    token = create_access_token({"sub": str(admin.id)})
    headers = {"X-Tenant": tenant.subdomain, "X-Token": token}

    # 1. Create a conversation
    conv = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        customer_address="61400000099",
        state="active",
        unread_count=1
    )
    db_session.add(conv)
    db_session.commit()

    # 2. Create message with sms_account_id = None (e.g. system message or raw inbound)
    msg = SmsMessage(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=None,
        conversation_id=conv.id,
        body="Hello from system without direct account link",
        direction="inbound",
        author_type="customer",
        status="received",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc)
    )
    db_session.add(msg)
    db_session.commit()

    # 3. Query conversation messages
    resp = client.get(f"/api/admin/sms/conversations/{conv.id}/messages", headers=headers)
    assert resp.status_code == status.HTTP_200_OK, resp.text
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == msg.id
    assert data[0]["sms_account_id"] is None
    assert data[0]["body"] == "Hello from system without direct account link"


def test_list_outbound_jobs_route_precedence(client, db_session, setup_sms_test_data):
    from app.core.security import create_access_token
    tenant = setup_sms_test_data["tenant"]
    admin = setup_sms_test_data["admin"]
    account = setup_sms_test_data["account_a"]
    provider = setup_sms_test_data["provider_a"]
    token = create_access_token({"sub": str(admin.id)})
    headers = {"X-Tenant": tenant.subdomain, "X-Token": token}

    # Create message and job
    conv = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=account.id,
        customer_address="61400000099",
        state="active"
    )
    db_session.add(conv)
    db_session.commit()

    msg = SmsMessage(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=account.id,
        conversation_id=conv.id,
        body="Test message for job",
        direction="outbound",
        author_type="staff",
        status="queued"
    )
    db_session.add(msg)
    db_session.commit()

    job = SmsOutboundJob(
        message_id=msg.id,
        sms_account_id=account.id,
        status="PENDING",
        retry_count=0
    )
    db_session.add(job)
    db_session.commit()

    # Query /jobs route (must NOT return 422 int_parsing validation error)
    resp = client.get("/api/admin/sms/conversations/jobs", headers=headers)
    assert resp.status_code == status.HTTP_200_OK, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert any(j["id"] == job.id for j in data)
