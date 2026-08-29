"""Comprehensive Payment Security & Financial Integrity Tests (Work Package B).

Covers findings:
- PAY-001: Server-authoritative deposit amounts, tenant scoping, and URL validation.
- PAY-002: Fail-closed Stripe webhook signature verification.
- PAY-003: Stripe event idempotency, reconciliation, and atomic state transitions.
- TEST-002: Verified rejection of unsigned webhooks and validation of signed events.

Zero live network calls to Stripe or ClickSend are made.
"""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.state_machine import BookingStatus
from app.models.booking import Booking as BookingModel
from app.models.client import Client as ClientModel
from app.models.outbox import OutboxEvent
from app.models.payment import Payment as PaymentModel, ProcessedStripeEvent
from app.models.provider import Provider as ProviderModel
from app.models.service import Service as ServiceModel
from app.models.tenant import Tenant as TenantModel


TEST_SECRET = "whsec_test_secret_for_payment_remediation_12345"


def create_signed_webhook_header(payload_bytes: bytes, secret: str = TEST_SECRET, timestamp: int | None = None) -> str:
    """Generate a valid Stripe-Signature header for testing."""
    if timestamp is None:
        timestamp = int(time.time())
    signed_data = f"{timestamp}.".encode("utf-8") + payload_bytes
    signature = hmac.new(secret.encode("utf-8"), signed_data, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def get_error_message(response) -> str:
    """Extract error message from standardized JSON response."""
    data = response.json()
    if "error" in data and isinstance(data["error"], dict):
        return data["error"].get("message", "")
    return data.get("detail", "")


@pytest.fixture
def payment_fixture(db_session: Session):
    """Seed test tenant, client, provider, service, and pending booking."""
    tenant = TenantModel(name="Payment Security Salon", subdomain="pay-sec-salon")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    client_obj = ClientModel(
        tenant_id=tenant.id,
        name="Alice Tester",
        email="alice@example.com",
        phone="+61412345678"
    )
    provider = ProviderModel(
        tenant_id=tenant.id,
        name="Stylist Bob",
        active=True
    )
    service = ServiceModel(
        tenant_id=tenant.id,
        name="Premium Cut & Color",
        duration=60,
        price=120.0,
        deposit_amount=50.0,
        active=True
    )
    db_session.add_all([client_obj, provider, service])
    db_session.commit()
    db_session.refresh(client_obj)
    db_session.refresh(provider)
    db_session.refresh(service)

    start_time = datetime.utcnow() + timedelta(days=1)
    end_time = start_time + timedelta(minutes=60)
    booking = BookingModel(
        tenant_id=tenant.id,
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

    return {
        "tenant": tenant,
        "client": client_obj,
        "provider": provider,
        "service": service,
        "booking": booking,
    }


# ============================================================================
# PAY-002: Stripe Webhook Signature Verification (Fail-Closed)
# ============================================================================

def test_webhook_missing_secret_fails_closed_503(client: TestClient, monkeypatch):
    """Webhook endpoint must return HTTP 503 when STRIPE_WEBHOOK_SECRET is unconfigured."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    payload = json.dumps({"id": "evt_test", "object": "event"}).encode("utf-8")

    response = client.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": "t=123,v1=abc"}
    )
    assert response.status_code == 503
    assert "not configured" in get_error_message(response)


def test_webhook_missing_signature_header_returns_400(client: TestClient, monkeypatch):
    """Webhook endpoint must return HTTP 400 when Stripe-Signature header is omitted."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_SECRET)
    payload = json.dumps({"id": "evt_test", "object": "event"}).encode("utf-8")

    response = client.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert "Missing Stripe-Signature header" in get_error_message(response)


def test_webhook_invalid_signature_returns_400(client: TestClient, monkeypatch):
    """Webhook endpoint must return HTTP 400 when signature is forged or invalid."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_SECRET)
    payload = json.dumps({"id": "evt_test", "object": "event"}).encode("utf-8")

    response = client.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": "t=1700000000,v1=forged_signature_hex"}
    )
    assert response.status_code == 400
    assert "Invalid signature" in get_error_message(response)


def test_webhook_tampered_payload_returns_400(client: TestClient, monkeypatch):
    """Webhook endpoint must reject payload whose bytes were altered after signing."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_SECRET)
    original_payload = json.dumps({"id": "evt_original", "object": "event"}).encode("utf-8")
    sig_header = create_signed_webhook_header(original_payload, TEST_SECRET)

    tampered_payload = json.dumps({"id": "evt_tampered", "object": "event"}).encode("utf-8")

    response = client.post(
        "/api/v1/webhooks/stripe",
        content=tampered_payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header}
    )
    assert response.status_code == 400


# ============================================================================
# PAY-003: Event Idempotency, Reconciliation & Atomic State Transitions
# ============================================================================

def test_webhook_valid_signed_event_confirms_booking_and_creates_payment(client: TestClient, db_session: Session, payment_fixture, monkeypatch):
    """Valid signed event transitions booking to CONFIRMED, creates Payment, and enqueues Outbox."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_SECRET)
    booking = payment_fixture["booking"]
    tenant = payment_fixture["tenant"]

    event_payload = {
        "id": "evt_valid_checkout_101",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_101",
                "object": "checkout.session",
                "amount_total": 5000,  # 50.00 AUD deposit in cents
                "currency": "aud",
                "payment_intent": "pi_test_intent_101",
                "metadata": {
                    "booking_id": str(booking.id),
                    "tenant_id": str(tenant.id)
                }
            }
        }
    }
    raw_payload = json.dumps(event_payload).encode("utf-8")
    sig_header = create_signed_webhook_header(raw_payload, TEST_SECRET)

    response = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True

    # 1. Verify Booking Transition
    db_session.refresh(booking)
    assert booking.status == BookingStatus.CONFIRMED

    # 2. Verify Payment Record
    payment = db_session.query(PaymentModel).filter_by(
        booking_id=booking.id,
        tenant_id=tenant.id
    ).first()
    assert payment is not None
    assert payment.status == "completed"
    assert payment.amount == Decimal("50.00")
    assert payment.currency == "AUD"
    assert payment.stripe_event_id == "evt_valid_checkout_101"
    assert payment.stripe_session_id == "cs_test_session_101"
    assert payment.stripe_payment_intent_id == "pi_test_intent_101"

    # 3. Verify ProcessedStripeEvent Record
    processed_evt = db_session.query(ProcessedStripeEvent).filter_by(
        event_id="evt_valid_checkout_101"
    ).first()
    assert processed_evt is not None
    assert processed_evt.status == "processed"
    assert processed_evt.booking_id == booking.id

    # 4. Verify Outbox Events
    outbox_events = db_session.query(OutboxEvent).filter_by(tenant_id=tenant.id).all()
    event_types = [e.type for e in outbox_events]
    assert "SEND_SMS" in event_types
    assert "booking.confirmed" in event_types
    assert "payment.received" in event_types


def test_webhook_duplicate_event_is_idempotent(client: TestClient, db_session: Session, payment_fixture, monkeypatch):
    """Duplicate Stripe event delivery returns 200 without creating duplicate payments or outbox entries."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_SECRET)
    booking = payment_fixture["booking"]
    tenant = payment_fixture["tenant"]

    event_payload = {
        "id": "evt_duplicate_checkout_202",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_202",
                "object": "checkout.session",
                "amount_total": 5000,
                "currency": "aud",
                "payment_intent": "pi_test_intent_202",
                "metadata": {
                    "booking_id": str(booking.id),
                    "tenant_id": str(tenant.id)
                }
            }
        }
    }
    raw_payload = json.dumps(event_payload).encode("utf-8")
    sig_header = create_signed_webhook_header(raw_payload, TEST_SECRET)

    # First Delivery
    res1 = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header}
    )
    assert res1.status_code == 200

    outbox_count_first = db_session.query(OutboxEvent).filter_by(tenant_id=tenant.id).count()
    payment_count_first = db_session.query(PaymentModel).filter_by(booking_id=booking.id).count()
    assert outbox_count_first == 3
    assert payment_count_first == 1

    # Second Delivery (Duplicate)
    res2 = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header}
    )
    assert res2.status_code == 200
    assert res2.json()["ok"] is True

    # Check that counts did not increase
    outbox_count_second = db_session.query(OutboxEvent).filter_by(tenant_id=tenant.id).count()
    payment_count_second = db_session.query(PaymentModel).filter_by(booking_id=booking.id).count()
    assert outbox_count_second == outbox_count_first
    assert payment_count_second == payment_count_first


def test_webhook_missing_tenant_id_rejected_safe_quarantine(client: TestClient, db_session: Session, payment_fixture, monkeypatch):
    """Event metadata missing tenant_id must be quarantined/rejected with 400 and not mutate bookings."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_SECRET)
    booking = payment_fixture["booking"]

    event_payload = {
        "id": "evt_missing_tenant_302",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_302",
                "object": "checkout.session",
                "amount_total": 5000,
                "currency": "aud",
                "metadata": {
                    "booking_id": str(booking.id),
                    # Missing tenant_id
                }
            }
        }
    }
    raw_payload = json.dumps(event_payload).encode("utf-8")
    sig_header = create_signed_webhook_header(raw_payload, TEST_SECRET)

    response = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header}
    )
    assert response.status_code == 400
    assert "tenant_id" in get_error_message(response).lower()

    # Verify no booking mutation occurred
    db_session.refresh(booking)
    assert booking.status == BookingStatus.PENDING
    payment = db_session.query(PaymentModel).filter_by(stripe_event_id="evt_missing_tenant_302").first()
    assert payment is None

    # Verify event was quarantined
    quarantined = db_session.query(ProcessedStripeEvent).filter_by(event_id="evt_missing_tenant_302").first()
    assert quarantined is not None
    assert quarantined.status == "quarantined"


def test_webhook_tenant_mismatch_rejected_safe_rollback(client: TestClient, db_session: Session, payment_fixture, monkeypatch):
    """Event metadata tenant_id mismatching database booking tenant must be rejected and rolled back."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_SECRET)
    booking = payment_fixture["booking"]

    event_payload = {
        "id": "evt_tenant_mismatch_303",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_303",
                "object": "checkout.session",
                "amount_total": 5000,
                "currency": "aud",
                "metadata": {
                    "booking_id": str(booking.id),
                    "tenant_id": "99999"  # Attacker forging a different tenant
                }
            }
        }
    }
    raw_payload = json.dumps(event_payload).encode("utf-8")
    sig_header = create_signed_webhook_header(raw_payload, TEST_SECRET)

    response = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header}
    )
    assert response.status_code == 400
    assert "Tenant mismatch" in get_error_message(response)

    # Verify rollback
    db_session.refresh(booking)
    assert booking.status == BookingStatus.PENDING
    payment = db_session.query(PaymentModel).filter_by(stripe_event_id="evt_tenant_mismatch_303").first()
    assert payment is None


def test_webhook_amount_mismatch_rejected_safe_rollback(client: TestClient, db_session: Session, payment_fixture, monkeypatch):
    """Event amount mismatching authoritative service deposit must be rejected."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_SECRET)
    booking = payment_fixture["booking"]
    tenant = payment_fixture["tenant"]

    event_payload = {
        "id": "evt_amount_mismatch_404",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_404",
                "object": "checkout.session",
                "amount_total": 100,  # $1.00 instead of $50.00 (5000 cents)
                "currency": "aud",
                "metadata": {
                    "booking_id": str(booking.id),
                    "tenant_id": str(tenant.id)
                }
            }
        }
    }
    raw_payload = json.dumps(event_payload).encode("utf-8")
    sig_header = create_signed_webhook_header(raw_payload, TEST_SECRET)

    response = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header}
    )
    assert response.status_code == 400
    assert "amount" in get_error_message(response).lower()

    # Verify rollback
    db_session.refresh(booking)
    assert booking.status == BookingStatus.PENDING


def test_webhook_currency_mismatch_rejected_safe_rollback(client: TestClient, db_session: Session, payment_fixture, monkeypatch):
    """Event currency mismatching authoritative service currency must be rejected."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_SECRET)
    booking = payment_fixture["booking"]
    tenant = payment_fixture["tenant"]

    event_payload = {
        "id": "evt_curr_mismatch_505",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_505",
                "object": "checkout.session",
                "amount_total": 5000,
                "currency": "usd",  # Expected AUD
                "metadata": {
                    "booking_id": str(booking.id),
                    "tenant_id": str(tenant.id)
                }
            }
        }
    }
    raw_payload = json.dumps(event_payload).encode("utf-8")
    sig_header = create_signed_webhook_header(raw_payload, TEST_SECRET)

    response = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header}
    )
    assert response.status_code == 400
    assert "currency" in get_error_message(response).lower()


def test_webhook_invalid_state_transition_rejected(client: TestClient, db_session: Session, payment_fixture, monkeypatch):
    """Attempting to confirm a cancelled booking via webhook must be rejected."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_SECRET)
    booking = payment_fixture["booking"]
    tenant = payment_fixture["tenant"]

    booking.status = BookingStatus.CANCELLED
    db_session.commit()

    event_payload = {
        "id": "evt_invalid_transition_606",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_606",
                "object": "checkout.session",
                "amount_total": 5000,
                "currency": "aud",
                "metadata": {
                    "booking_id": str(booking.id),
                    "tenant_id": str(tenant.id)
                }
            }
        }
    }
    raw_payload = json.dumps(event_payload).encode("utf-8")
    sig_header = create_signed_webhook_header(raw_payload, TEST_SECRET)

    response = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header}
    )
    assert response.status_code == 400
    assert "Invalid booking status transition" in get_error_message(response)


def test_webhook_payment_failed_cancels_booking_and_enqueues_outbox(client: TestClient, db_session: Session, payment_fixture, monkeypatch):
    """Charge or invoice failure event cancels pending booking and records failed payment."""
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", TEST_SECRET)
    booking = payment_fixture["booking"]
    tenant = payment_fixture["tenant"]

    event_payload = {
        "id": "evt_charge_failed_707",
        "object": "event",
        "type": "charge.failed",
        "data": {
            "object": {
                "id": "ch_failed_707",
                "object": "charge",
                "metadata": {
                    "booking_id": str(booking.id),
                    "tenant_id": str(tenant.id)
                }
            }
        }
    }
    raw_payload = json.dumps(event_payload).encode("utf-8")
    sig_header = create_signed_webhook_header(raw_payload, TEST_SECRET)

    response = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_payload,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header}
    )
    assert response.status_code == 200

    db_session.refresh(booking)
    assert booking.status == BookingStatus.CANCELLED

    failed_payment = db_session.query(PaymentModel).filter_by(
        booking_id=booking.id,
        status="failed"
    ).first()
    assert failed_payment is not None

    sms_event = db_session.query(OutboxEvent).filter_by(
        tenant_id=tenant.id,
        type="SEND_SMS"
    ).first()
    assert sms_event is not None
    assert "failed" in sms_event.payload


# ============================================================================
# PAY-001: Authoritative Deposit Session Creation & URL Validation
# ============================================================================

def test_deposit_session_without_tenant_header_fails_closed(client: TestClient, payment_fixture):
    """Creating deposit session without tenant header fails closed with HTTP 400."""
    booking = payment_fixture["booking"]

    response = client.post(
        f"/api/v1/checkout/deposit-session?booking_id={booking.id}&success_url=http://localhost:8000/success&cancel_url=http://localhost:8000/cancel"
    )
    assert response.status_code == 400
    assert "Tenant subdomain is missing or invalid" in get_error_message(response)


def test_deposit_session_rejects_non_pending_booking(client: TestClient, db_session: Session, payment_fixture):
    """Creating deposit session for confirmed or cancelled booking returns 400/409 Conflict."""
    booking = payment_fixture["booking"]

    # 1. Confirmed booking rejected
    booking.status = BookingStatus.CONFIRMED
    db_session.commit()

    res_confirmed = client.post(
        f"/api/v1/checkout/deposit-session?booking_id={booking.id}&success_url=http://localhost:8000/success&cancel_url=http://localhost:8000/cancel",
        headers={"X-Tenant": "pay-sec-salon"}
    )
    assert res_confirmed.status_code in (400, 409)

    # 2. Cancelled booking rejected
    booking.status = BookingStatus.CANCELLED
    db_session.commit()

    res_cancelled = client.post(
        f"/api/v1/checkout/deposit-session?booking_id={booking.id}&success_url=http://localhost:8000/success&cancel_url=http://localhost:8000/cancel",
        headers={"X-Tenant": "pay-sec-salon"}
    )
    assert res_cancelled.status_code in (400, 409)


def test_deposit_session_cross_tenant_returns_404(client: TestClient, db_session: Session, payment_fixture):
    """Requesting deposit session for a booking belonging to another tenant returns 404 Not Found."""
    booking = payment_fixture["booking"]

    other_tenant = TenantModel(name="Other Salon", subdomain="other-salon")
    db_session.add(other_tenant)
    db_session.commit()

    response = client.post(
        f"/api/v1/checkout/deposit-session?booking_id={booking.id}&success_url=http://localhost:8000/success&cancel_url=http://localhost:8000/cancel",
        headers={"X-Tenant": "other-salon"}
    )
    assert response.status_code == 404
    assert "Booking not found" in get_error_message(response)


def test_deposit_session_rejects_client_price_tampering(client: TestClient, payment_fixture):
    """Client attempting to supply a tampered deposit amount is rejected with 400."""
    booking = payment_fixture["booking"]

    response = client.post(
        f"/api/v1/checkout/deposit-session?booking_id={booking.id}&amount_cents=100&success_url=http://localhost:8000/success&cancel_url=http://localhost:8000/cancel",
        headers={"X-Tenant": "pay-sec-salon"}
    )
    assert response.status_code == 400
    assert "Deposit amount mismatch" in get_error_message(response)


def test_deposit_session_rejects_untrusted_redirect_urls(client: TestClient, payment_fixture):
    """Redirect URLs pointing to untrusted domains or dangerous schemes are rejected."""
    booking = payment_fixture["booking"]

    # 1. Untrusted external domain
    res1 = client.post(
        f"/api/v1/checkout/deposit-session?booking_id={booking.id}&success_url=https://attacker-phishing.com/steal&cancel_url=http://localhost:8000/cancel",
        headers={"X-Tenant": "pay-sec-salon"}
    )
    assert res1.status_code == 400
    assert "Invalid redirect URL" in get_error_message(res1)

    # 2. Dangerous javascript scheme
    res2 = client.post(
        f"/api/v1/checkout/deposit-session?booking_id={booking.id}&success_url=javascript:alert(1)&cancel_url=http://localhost:8000/cancel",
        headers={"X-Tenant": "pay-sec-salon"}
    )
    assert res2.status_code == 400


def test_deposit_session_nonexistent_booking_returns_404(client: TestClient, payment_fixture):
    """Requesting a deposit session for non-existent booking returns 404."""
    response = client.post(
        "/api/v1/checkout/deposit-session?booking_id=999999&success_url=http://localhost:8000/success&cancel_url=http://localhost:8000/cancel",
        headers={"X-Tenant": "pay-sec-salon"}
    )
    assert response.status_code == 404
    assert "Booking not found" in get_error_message(response)


def test_deposit_session_creation_success_with_authoritative_deposit(client: TestClient, payment_fixture):
    """Deposit session creation succeeds using server-calculated deposit without live Stripe calls."""
    booking = payment_fixture["booking"]

    mock_session = MagicMock()
    mock_session.id = "cs_mock_created_888"
    mock_session.url = "https://checkout.stripe.com/c/pay/cs_mock_created_888"

    with patch("app.services.stripe_service.stripe_service.create_checkout_session", return_value=mock_session) as mock_create:
        response = client.post(
            f"/api/v1/checkout/deposit-session?booking_id={booking.id}&success_url=http://localhost:8000/success&cancel_url=http://localhost:8000/cancel",
            headers={"X-Tenant": "pay-sec-salon"}
        )
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["ok"] is True
        assert res_data["data"]["session_id"] == "cs_mock_created_888"
        assert res_data["data"]["url"] == "https://checkout.stripe.com/c/pay/cs_mock_created_888"

        # Verify stripe_service was called with authoritative 5000 cents ($50.00)
        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        assert kwargs["booking_id"] == booking.id
        assert kwargs["amount_cents"] == 5000
        assert kwargs["currency"] == "aud"
        assert kwargs["tenant_id"] == str(booking.tenant_id)

