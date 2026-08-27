import pytest
from datetime import datetime, timezone, timedelta
from app.models.tenant import Tenant
from app.models.provider import Provider
from app.models.user import User
from app.models.client import Client
from app.models.booking import Booking
from app.models.service import Service
from app.models.sms_account import SmsAccount
from app.models.sms_conversation import SmsConversation
from app.models.sms_arrival import SmsArrivalSession
from app.models.sms_outbox import SmsConversationEvent
from app.models.outbox import OutboxEvent
from app.services.sms.arrival_service import create_arrival_session, process_repeated_arrival_alerts

@pytest.fixture
def setup_arrival_test_data(db_session):
    # 1. Create a tenant
    tenant = Tenant(name="Arrival Test Tenant", subdomain="arrival-test")
    db_session.add(tenant)
    db_session.commit()

    # 2. Create an admin user
    admin = User(tenant_id=tenant.id, login="admin@arrivaltest.com", password_hash="hash", role="admin")
    db_session.add(admin)
    db_session.commit()

    # 3. Create a provider
    provider = Provider(tenant_id=tenant.id, name="Provider Arrival", active=True)
    db_session.add(provider)
    db_session.commit()

    # 4. Create SMS account
    account = SmsAccount(
        tenant_id=tenant.id,
        provider_id=provider.id,
        transport_type="simulator",
        display_name="Arrival Line",
        sender_address="61499999999",
        is_enabled=True
    )
    db_session.add(account)
    db_session.commit()

    # 5. Create a client
    client_obj = Client(tenant_id=tenant.id, name="Jane Arrival", phone="0499999999", active=True)
    db_session.add(client_obj)
    db_session.commit()

    # 6. Create service
    service = Service(
        tenant_id=tenant.id,
        name="Arrival Test Service",
        duration=30,
        price=50.0,
        active=True
    )
    db_session.add(service)
    db_session.commit()

    # 7. Create booking
    booking = Booking(
        tenant_id=tenant.id,
        client_id=client_obj.id,
        provider_id=provider.id,
        service_id=service.id,
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, minutes=30),
        status="confirmed",
        idempotency_key="booking-arrival-key"
    )
    db_session.add(booking)
    db_session.commit()

    # 8. Create SmsConversation
    conversation = SmsConversation(
        tenant_id=tenant.id,
        provider_id=provider.id,
        sms_account_id=account.id,
        customer_address="61499999999",
        state="auto-reply",
        unread_count=0
    )
    db_session.add(conversation)
    db_session.commit()

    # 9. Create SmsArrivalSession
    arrival_session = create_arrival_session(
        db=db_session,
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        booking_id=booking.id
    )

    return {
        "tenant": tenant,
        "admin": admin,
        "provider": provider,
        "account": account,
        "client": client_obj,
        "service": service,
        "booking": booking,
        "conversation": conversation,
        "arrival_session": arrival_session,
        "headers": {"X-Tenant": "arrival-test", "X-Token": "mock-admin-token"}
    }

def test_client_arrival_triggers_initial_event(client, setup_arrival_test_data, db_session):
    data = setup_arrival_test_data
    token = data["arrival_session"].token
    
    # 1. Post to arrive endpoint
    resp = client.post(f"/api/admin/sms/arrivals/public/{token}/arrive")
    assert resp.status_code == 200
    res_json = resp.json()
    assert res_json["status"] == "success"
    assert res_json["booking_id"] == data["booking"].id
    assert res_json["arrived_at"] is not None
    
    # 2. Query DB and assert arrived_at is set and event is logged
    session = db_session.query(SmsArrivalSession).filter(SmsArrivalSession.token == token).first()
    assert session.arrived_at is not None
    
    event = db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == data["conversation"].id,
        SmsConversationEvent.type == "customer_arrived"
    ).first()
    assert event is not None
    assert event.meta["booking_id"] == data["booking"].id

def test_repeated_arrival_alerts(client, setup_arrival_test_data, db_session):
    data = setup_arrival_test_data
    token = data["arrival_session"].token
    
    # Arrive first
    resp = client.post(f"/api/admin/sms/arrivals/public/{token}/arrive")
    assert resp.status_code == 200
    
    # Verify no alert triggered yet (since 0 seconds elapsed)
    process_repeated_arrival_alerts(db_session)
    alert_events = db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == data["conversation"].id,
        SmsConversationEvent.type == "arrival_alert_triggered"
    ).all()
    assert len(alert_events) == 0
    
    # Mock time progression: update arrived_at to 65 seconds ago
    session = db_session.query(SmsArrivalSession).filter(SmsArrivalSession.token == token).first()
    session.arrived_at = datetime.now(timezone.utc) - timedelta(seconds=65)
    db_session.commit()
    
    # Trigger alert
    process_repeated_arrival_alerts(db_session)
    alert_events = db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == data["conversation"].id,
        SmsConversationEvent.type == "arrival_alert_triggered"
    ).all()
    assert len(alert_events) == 1
    assert alert_events[0].meta["booking_id"] == data["booking"].id
    
    # Check that outbox event "arrival.alert" was enqueued
    outbox_event = db_session.query(OutboxEvent).filter(
        OutboxEvent.type == "arrival.alert",
        OutboxEvent.tenant_id == data["tenant"].id
    ).first()
    assert outbox_event is not None
    
    # Try triggering immediately again - should not trigger
    process_repeated_arrival_alerts(db_session)
    alert_events = db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == data["conversation"].id,
        SmsConversationEvent.type == "arrival_alert_triggered"
    ).all()
    assert len(alert_events) == 1
    
    # Simulate another 65 seconds since last alert
    last_event = alert_events[0]
    last_event.created_at = datetime.now(timezone.utc) - timedelta(seconds=65)
    db_session.commit()
    
    # Trigger repeated alert
    process_repeated_arrival_alerts(db_session)
    alert_events = db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == data["conversation"].id,
        SmsConversationEvent.type == "arrival_alert_triggered"
    ).order_by(SmsConversationEvent.created_at.asc()).all()
    assert len(alert_events) == 2
    
    # Check that another outbox event was created
    outbox_events = db_session.query(OutboxEvent).filter(
        OutboxEvent.type == "arrival.alert",
        OutboxEvent.tenant_id == data["tenant"].id
    ).all()
    assert len(outbox_events) == 2

def test_acknowledgement_stops_alerts(client, setup_arrival_test_data, db_session):
    data = setup_arrival_test_data
    token = data["arrival_session"].token
    
    # Arrive first
    client.post(f"/api/admin/sms/arrivals/public/{token}/arrive")
    
    # Acknowledge arrival
    session = db_session.query(SmsArrivalSession).filter(SmsArrivalSession.token == token).first()
    ack_resp = client.post(
        f"/api/admin/sms/arrivals/{session.id}/acknowledge",
        headers=data["headers"]
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "success"
    
    # Assert acknowledged_at is set and event is logged
    db_session.refresh(session)
    assert session.acknowledged_at is not None
    
    ack_event = db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == data["conversation"].id,
        SmsConversationEvent.type == "arrival_acknowledged"
    ).first()
    assert ack_event is not None
    
    # Move time forward by 65 seconds to see if alert triggers
    session.arrived_at = datetime.now(timezone.utc) - timedelta(seconds=65)
    db_session.commit()
    
    # Process alerts
    process_repeated_arrival_alerts(db_session)
    
    # Verify no alert triggered
    alert_events = db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id == data["conversation"].id,
        SmsConversationEvent.type == "arrival_alert_triggered"
    ).all()
    assert len(alert_events) == 0
