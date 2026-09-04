import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch
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


def test_outbox_worker_processes_send_sms_with_fake_transport(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """A SEND_SMS event is processed through an explicit fake transport."""
    from app.core.config import settings

    # The fake transport must make this test independent of any configured
    # credentials and must prevent an accidental provider request.
    monkeypatch.setattr(settings, "CLICKSEND_API_USERNAME", "plausible-test-user")
    monkeypatch.setattr(settings, "CLICKSEND_API_KEY", "plausible-test-key")

    # Create a SEND_SMS outbox event
    payload = {
        "to": "+61411111111",
        "body": "Test message content"
    }
    event = create_outbox_event(db_session, "SEND_SMS", payload)
    db_session.commit()
    
    assert event.status == "PENDING"
    
    fake_send_sms = AsyncMock(return_value={"data": {"messages": [{"status": "SUCCESS"}]}})
    with patch(
        "app.services.outbox_worker.clicksend_client.send_sms", new=fake_send_sms
    ):
        asyncio.run(process_pending_outbox_events(db_session))

    fake_send_sms.assert_awaited_once_with(
        to=payload["to"], body=payload["body"], sender=None
    )

    db_session.refresh(event)
    assert event.status == "PROCESSED"
    assert event.processed is True
    assert event.retry_count == 0


def test_stripe_webhook_completion(client: TestClient, db_session: Session):
    """Test Stripe webhook processing updates booking status to confirmed."""
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

    # Mock stripe checkout session completed payload
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
    
    # POST to stripe webhook endpoint (verification will be bypassed because STRIPE_WEBHOOK_SECRET is empty)
    response = client.post("/api/v1/webhooks/stripe", json=webhook_payload)
    assert response.status_code == 200
    
    # Refresh booking and verify it transitioned to CONFIRMED
    db_session.refresh(booking)
    assert booking.status == BookingStatus.CONFIRMED

    # Verify a SEND_SMS and a booking.confirmed outbox event were enqueued
    sms_event = db_session.query(OutboxEvent).filter_by(type="SEND_SMS").first()
    assert sms_event is not None
    assert "CONFIRMED" in sms_event.payload
