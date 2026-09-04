from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.state_machine import BookingStatus
from app.models import Client as ClientModel
from app.models.booking import Booking as BookingModel
from app.models.outbox import OutboxEvent
from app.models.provider import Provider as ProviderModel
from app.models.service import Service as ServiceModel
from app.models.tenant import Tenant as TenantModel


PAYMENTS_UNAVAILABLE_MESSAGE = "Stripe payments are temporarily unavailable"


def _assert_payments_unavailable(response) -> None:
    assert response.status_code == 503
    assert response.json()["ok"] is False
    assert response.json()["error"]["message"] == PAYMENTS_UNAVAILABLE_MESSAGE


def _pending_booking(db_session: Session) -> BookingModel:
    tenant = TenantModel(name="Payment-disabled tenant", subdomain="payment-disabled")
    db_session.add(tenant)
    db_session.commit()

    client = ClientModel(
        tenant_id=str(tenant.id), name="Synthetic customer", email="customer@example.test"
    )
    provider = ProviderModel(
        tenant_id=str(tenant.id), name="Synthetic provider", active=True
    )
    service = ServiceModel(
        tenant_id=str(tenant.id),
        name="Synthetic service",
        duration=30,
        price=50.0,
        active=True,
    )
    db_session.add_all([client, provider, service])
    db_session.commit()

    start_time = datetime.utcnow()
    booking = BookingModel(
        tenant_id=str(tenant.id),
        client_id=client.id,
        provider_id=provider.id,
        service_id=service.id,
        status=BookingStatus.PENDING,
        start_time=start_time,
        end_time=start_time + timedelta(minutes=30),
    )
    db_session.add(booking)
    db_session.commit()
    return booking


def test_deposit_session_is_disabled_before_request_processing(
    client: TestClient, db_session: Session
):
    """Deposit requests cannot reach booking lookup, Stripe, or local side effects."""
    booking = _pending_booking(db_session)
    outbox_count_before = db_session.query(OutboxEvent).count()

    # Deliberately malformed query parameters would have failed validation in
    # the legacy route. A 503 confirms the disabled route ignores them.
    response = client.post(
        "/api/v1/checkout/deposit-session?booking_id=not-an-id&amount_cents=bad",
        content=b"not-request-data",
        headers={"content-type": "application/json"},
    )

    _assert_payments_unavailable(response)
    db_session.refresh(booking)
    assert booking.status == BookingStatus.PENDING
    assert db_session.query(OutboxEvent).count() == outbox_count_before


def test_stripe_webhook_is_disabled_before_body_parsing(client: TestClient):
    """Malformed webhook content is rejected without parsing its request body."""
    response = client.post(
        "/api/v1/webhooks/stripe",
        content=b"{not-json",
        headers={"content-type": "application/json", "stripe-signature": "invalid"},
    )

    _assert_payments_unavailable(response)
