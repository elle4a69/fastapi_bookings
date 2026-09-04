import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Client as ClientModel
from app.models.booking import Booking as BookingModel
from app.models.outbox import OutboxEvent
from app.models.notification import DeviceToken as DeviceTokenModel
from app.core.state_machine import BookingStatus
from app.services.outbox_worker import process_pending_outbox_events
from app.services.outbox_service import create_outbox_event

def test_device_registration(client: TestClient, db_session: Session):
    """Test device token registration and upsert endpoint."""
    payload = {
        "token": "test_fcm_token_123",
        "platform": "ios",
        "device_id": "iphone_15_pro",
        "enabled": True
    }
    response = client.post("/api/v1/devices/register", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["ok"] is True
    assert res_data["data"]["token"] == "test_fcm_token_123"
    
    # Check db
    db_token = db_session.query(DeviceTokenModel).filter_by(token="test_fcm_token_123").first()
    assert db_token is not None
    assert db_token.platform == "ios"

    # Test update (upsert)
    payload["platform"] = "android"
    response = client.post("/api/v1/devices/register", json=payload)
    assert response.status_code == 200
    
    db_session.refresh(db_token)
    assert db_token.platform == "android"


def test_generic_outbox_quarantines_legacy_send_sms(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """The obsolete generic provider path cannot produce a duplicate SMS."""
    payload = {
        "to": "+61411111111",
        "body": "Test message content"
    }
    event = create_outbox_event(db_session, "SEND_SMS", payload)
    db_session.commit()
    
    assert event.status == "PENDING"
    
    asyncio.run(process_pending_outbox_events(db_session))

    db_session.refresh(event)
    assert event.status == "QUARANTINED"
    assert event.processed is True
    assert event.error_code == "EVENT_TYPE_UNSUPPORTED"


def test_stripe_webhook_is_disabled_without_changing_booking_or_outbox(
    client: TestClient, db_session: Session
):
    """Legacy webhook events are rejected before they can mutate local state."""
    from app.models.tenant import Tenant as TenantModel
    from app.models.provider import Provider as ProviderModel
    from app.models.service import Service as ServiceModel

    # Create a tenant first
    tenant = TenantModel(
        name="Stripe Biz",
        subdomain="stripe-biz"
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    # Create a client
    client_obj = ClientModel(
        tenant_id=str(tenant.id),
        name="John Doe",
        email="john@example.com"
    )
    # Create a provider
    provider = ProviderModel(
        tenant_id=str(tenant.id),
        name="Dr. Alex",
        active=True
    )
    # Create a service
    service = ServiceModel(
        tenant_id=str(tenant.id),
        name="Consultation",
        duration=30,
        price=50.0,
        active=True
    )
    db_session.add_all([client_obj, provider, service])
    db_session.commit()
    db_session.refresh(client_obj)
    db_session.refresh(provider)
    db_session.refresh(service)

    from datetime import datetime, timedelta
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(minutes=30)

    # Create a mock pending booking
    booking = BookingModel(
        tenant_id=str(tenant.id),
        client_id=client_obj.id,
        provider_id=provider.id,
        service_id=service.id,
        status=BookingStatus.PENDING,
        start_time=start_time,
        end_time=end_time
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)
    
    assert booking.status == BookingStatus.PENDING

    # This otherwise-valid event must not be parsed or processed while payments
    # are disabled.
    webhook_payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_12345",
                "metadata": {
                    "booking_id": str(booking.id),
                    "tenant_id": "test_tenant"
                }
            }
        }
    }
    
    outbox_count_before = db_session.query(OutboxEvent).count()
    response = client.post("/api/v1/webhooks/stripe", json=webhook_payload)
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Stripe payments are temporarily unavailable"
    
    # Confirm the webhook did not transition the booking or enqueue side effects.
    db_session.refresh(booking)
    assert booking.status == BookingStatus.PENDING
    assert db_session.query(OutboxEvent).count() == outbox_count_before
