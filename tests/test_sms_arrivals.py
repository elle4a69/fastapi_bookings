"""Synthetic, no-send tests for secure arrival sessions and staff alerts."""

import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import create_access_token
from app.core.state_machine import BookingStatus
from app.models.booking import Booking
from app.models.client import Client
from app.models.outbox import OutboxEvent
from app.models.provider import Provider
from app.models.service import Service
from app.models.sms_account import SmsAccount
from app.models.sms_arrival import SmsArrivalSession
from app.models.sms_conversation import SmsConversation
from app.models.sms_outbox import SmsConversationEvent
from app.models.tenant import Tenant
from app.models.user import User
from app.services.sms.arrival_service import (
    ArrivalNotFoundError,
    ArrivalStateError,
    create_arrival_session,
    process_repeated_arrival_alerts,
)


def _staff_headers(tenant: Tenant, user: User) -> dict[str, str]:
    return {
        "X-Tenant": tenant.subdomain,
        "X-Token": create_access_token({"sub": str(user.id)}),
    }


@pytest.fixture
def synthetic_arrival_data(db_session):
    """Create labelled synthetic tenants; no transport or external call occurs."""

    now = datetime.now(timezone.utc)
    tenant_a = Tenant(name="SYNTHETIC Arrival A", subdomain="synthetic-arrival-a")
    tenant_b = Tenant(name="SYNTHETIC Arrival B", subdomain="synthetic-arrival-b")
    db_session.add_all([tenant_a, tenant_b])
    db_session.flush()

    admin_a = User(
        tenant_id=tenant_a.id,
        login="synthetic-arrival-admin-a",
        password_hash="synthetic-not-a-credential",
        role="admin",
    )
    admin_b = User(
        tenant_id=tenant_b.id,
        login="synthetic-arrival-admin-b",
        password_hash="synthetic-not-a-credential",
        role="admin",
    )
    provider_a = Provider(tenant_id=tenant_a.id, name="SYNTHETIC Provider A", active=True)
    provider_b = Provider(tenant_id=tenant_b.id, name="SYNTHETIC Provider B", active=True)
    db_session.add_all([admin_a, admin_b, provider_a, provider_b])
    db_session.flush()

    account_a = SmsAccount(
        tenant_id=tenant_a.id,
        provider_id=provider_a.id,
        transport_type="simulator",
        display_name="SYNTHETIC Arrival Line A",
        sender_address="+61000000001",
        is_enabled=True,
    )
    account_b = SmsAccount(
        tenant_id=tenant_b.id,
        provider_id=provider_b.id,
        transport_type="simulator",
        display_name="SYNTHETIC Arrival Line B",
        sender_address="+61000000002",
        is_enabled=True,
    )
    client_a = Client(
        tenant_id=tenant_a.id,
        name="SYNTHETIC Client A",
        phone="+61000000101",
        active=True,
    )
    client_b = Client(
        tenant_id=tenant_b.id,
        name="SYNTHETIC Client B",
        phone="+61000000102",
        active=True,
    )
    service_a = Service(
        tenant_id=tenant_a.id,
        name="SYNTHETIC Service A",
        duration=30,
        price=50.0,
        active=True,
    )
    service_b = Service(
        tenant_id=tenant_b.id,
        name="SYNTHETIC Service B",
        duration=30,
        price=50.0,
        active=True,
    )
    db_session.add_all([account_a, account_b, client_a, client_b, service_a, service_b])
    db_session.flush()

    booking_a = Booking(
        tenant_id=tenant_a.id,
        client_id=client_a.id,
        provider_id=provider_a.id,
        service_id=service_a.id,
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=1, minutes=30),
        status=BookingStatus.CONFIRMED,
        idempotency_key="synthetic-arrival-booking-a",
    )
    booking_b = Booking(
        tenant_id=tenant_b.id,
        client_id=client_b.id,
        provider_id=provider_b.id,
        service_id=service_b.id,
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=2, minutes=30),
        status=BookingStatus.CONFIRMED,
        idempotency_key="synthetic-arrival-booking-b",
    )
    db_session.add_all([booking_a, booking_b])
    db_session.flush()

    conversation_a = SmsConversation(
        tenant_id=tenant_a.id,
        provider_id=provider_a.id,
        sms_account_id=account_a.id,
        client_id=client_a.id,
        customer_address="+61000000101",
        state="auto-reply",
    )
    conversation_b = SmsConversation(
        tenant_id=tenant_b.id,
        provider_id=provider_b.id,
        sms_account_id=account_b.id,
        client_id=client_b.id,
        customer_address="+61000000102",
        state="auto-reply",
    )
    db_session.add_all([conversation_a, conversation_b])
    db_session.flush()

    invitation_a = create_arrival_session(
        db_session,
        tenant_id=tenant_a.id,
        conversation_id=conversation_a.id,
        booking_id=booking_a.id,
        now=now,
    )
    invitation_b = create_arrival_session(
        db_session,
        tenant_id=tenant_b.id,
        conversation_id=conversation_b.id,
        booking_id=booking_b.id,
        now=now,
    )
    db_session.commit()
    return {
        "now": now,
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "provider_a": provider_a,
        "provider_b": provider_b,
        "account_a": account_a,
        "client_a": client_a,
        "booking_a": booking_a,
        "booking_b": booking_b,
        "conversation_a": conversation_a,
        "conversation_b": conversation_b,
        "invitation_a": invitation_a,
        "invitation_b": invitation_b,
    }


def test_new_session_stores_only_token_digest(synthetic_arrival_data):
    invitation = synthetic_arrival_data["invitation_a"]
    assert invitation.token != invitation.session.token
    assert re.fullmatch(r"[a-f0-9]{64}", invitation.session.token)
    assert invitation.expires_at > synthetic_arrival_data["now"]


def test_body_token_arrival_is_idempotent_and_minimal(
    client, db_session, synthetic_arrival_data
):
    invitation = synthetic_arrival_data["invitation_a"]
    endpoint = "/api/admin/sms/arrivals/public/arrive"
    first = client.post(endpoint, json={"token": invitation.token})
    second = client.post(endpoint, json={"token": invitation.token})

    assert first.status_code == 200
    assert first.json()["status"] == "arrived"
    assert second.status_code == 200
    assert second.json()["status"] == "already_arrived"
    assert set(first.json()) == {"status", "arrived_at"}

    events = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id
            == synthetic_arrival_data["conversation_a"].id,
            SmsConversationEvent.type == "customer_arrived",
        )
        .all()
    )
    assert len(events) == 1
    assert "token" not in json.dumps(events[0].meta).lower()
    assert synthetic_arrival_data["client_a"].phone not in json.dumps(events[0].meta)


def test_url_token_contract_is_retired(client, synthetic_arrival_data):
    response = client.post(
        f"/api/admin/sms/arrivals/public/{synthetic_arrival_data['invitation_a'].token}/arrive"
    )
    assert response.status_code == 404


def test_invalid_body_token_is_not_reflected(client):
    invalid_token = "synthetic-secret"
    response = client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": invalid_token},
    )
    assert response.status_code == 404
    assert invalid_token not in response.text


def test_expired_token_fails_closed_without_state_change(
    client, db_session, synthetic_arrival_data
):
    invitation = synthetic_arrival_data["invitation_a"]
    invitation.session.created_at = synthetic_arrival_data["now"] - timedelta(days=8)
    db_session.commit()

    response = client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": invitation.token},
    )
    assert response.status_code == 404
    assert invitation.token not in response.text
    db_session.refresh(invitation.session)
    assert invitation.session.arrived_at is None


def test_legacy_raw_token_row_is_temporarily_supported_without_disclosure(
    client, db_session, synthetic_arrival_data
):
    invitation_b = synthetic_arrival_data["invitation_b"]
    legacy_token = "synthetic-legacy-arrival-token-0001"
    invitation_b.session.token = legacy_token
    db_session.commit()

    response = client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": legacy_token},
    )
    assert response.status_code == 200
    assert legacy_token not in response.text


def test_acknowledge_requires_arrival_and_is_tenant_scoped(
    client, db_session, synthetic_arrival_data
):
    arrival = synthetic_arrival_data["invitation_a"].session
    headers_a = _staff_headers(
        synthetic_arrival_data["tenant_a"], synthetic_arrival_data["admin_a"]
    )
    headers_b = _staff_headers(
        synthetic_arrival_data["tenant_b"], synthetic_arrival_data["admin_b"]
    )

    before_arrival = client.post(
        f"/api/admin/sms/arrivals/{arrival.id}/acknowledge", headers=headers_a
    )
    assert before_arrival.status_code == 409

    checkin = client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": synthetic_arrival_data["invitation_a"].token},
    )
    assert checkin.status_code == 200

    cross_tenant = client.post(
        f"/api/admin/sms/arrivals/{arrival.id}/acknowledge", headers=headers_b
    )
    assert cross_tenant.status_code == 404

    first = client.post(
        f"/api/admin/sms/arrivals/{arrival.id}/acknowledge", headers=headers_a
    )
    second = client.post(
        f"/api/admin/sms/arrivals/{arrival.id}/acknowledge", headers=headers_a
    )
    assert first.status_code == 200
    assert first.json()["status"] == "acknowledged"
    assert second.json()["status"] == "already_acknowledged"

    events = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id
            == synthetic_arrival_data["conversation_a"].id,
            SmsConversationEvent.type == "arrival_acknowledged",
        )
        .all()
    )
    assert len(events) == 1
    assert events[0].meta["closure"] is True


def test_staff_list_is_authenticated_tenant_scoped_and_contains_no_pii(
    client, synthetic_arrival_data
):
    endpoint = "/api/admin/sms/arrivals"
    missing_auth = client.get(
        endpoint, headers={"X-Tenant": synthetic_arrival_data["tenant_a"].subdomain}
    )
    assert missing_auth.status_code == 401

    response = client.get(
        endpoint,
        headers=_staff_headers(
            synthetic_arrival_data["tenant_a"], synthetic_arrival_data["admin_a"]
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["booking_id"] == synthetic_arrival_data["booking_a"].id
    forbidden_keys = {
        "token",
        "client_name",
        "client_phone",
        "customer_phone",
        "provider_name",
    }
    assert forbidden_keys.isdisjoint(body[0])
    serialized = json.dumps(body)
    assert synthetic_arrival_data["client_a"].phone not in serialized
    assert synthetic_arrival_data["invitation_a"].token not in serialized


def test_creation_rejects_cross_scope_booking_and_conversation(
    db_session, synthetic_arrival_data
):
    with pytest.raises(ArrivalNotFoundError):
        create_arrival_session(
            db_session,
            tenant_id=synthetic_arrival_data["tenant_a"].id,
            conversation_id=synthetic_arrival_data["conversation_b"].id,
            booking_id=synthetic_arrival_data["booking_a"].id,
        )


def test_checkin_fails_closed_when_conversation_loses_client_scope(
    client, db_session, synthetic_arrival_data
):
    synthetic_arrival_data["conversation_a"].client_id = None
    db_session.commit()
    response = client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": synthetic_arrival_data["invitation_a"].token},
    )
    assert response.status_code == 404


def test_creation_rejects_duplicate_booking_capability(
    db_session, synthetic_arrival_data
):
    with pytest.raises(ArrivalStateError, match="already exists"):
        create_arrival_session(
            db_session,
            tenant_id=synthetic_arrival_data["tenant_a"].id,
            conversation_id=synthetic_arrival_data["conversation_a"].id,
            booking_id=synthetic_arrival_data["booking_a"].id,
        )


def test_repeated_alerts_use_durable_structural_deduplication(
    client, db_session, synthetic_arrival_data
):
    arrival_time = synthetic_arrival_data["now"]
    response = client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": synthetic_arrival_data["invitation_a"].token},
    )
    assert response.status_code == 200
    arrival = synthetic_arrival_data["invitation_a"].session
    arrival.arrived_at = arrival_time
    db_session.commit()

    alert_time = arrival_time + timedelta(seconds=125)
    assert process_repeated_arrival_alerts(db_session, now=alert_time) == 1
    assert process_repeated_arrival_alerts(db_session, now=alert_time) == 0

    outbox = (
        db_session.query(OutboxEvent)
        .filter(OutboxEvent.idempotency_key == f"arrival-alert:{arrival.id}:2")
        .one()
    )
    payload = outbox.data()
    assert payload["alert_sequence"] == 2
    assert payload["sms_account_id"] == synthetic_arrival_data["account_a"].id
    assert "token" not in outbox.payload.lower()
    assert synthetic_arrival_data["client_a"].phone not in outbox.payload

    assert process_repeated_arrival_alerts(
        db_session, now=alert_time + timedelta(seconds=60)
    ) == 1
    assert (
        db_session.query(OutboxEvent)
        .filter(OutboxEvent.type == "arrival.alert")
        .count()
        == 2
    )


def test_acknowledgement_stops_future_alerts(client, db_session, synthetic_arrival_data):
    client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": synthetic_arrival_data["invitation_a"].token},
    )
    arrival = synthetic_arrival_data["invitation_a"].session
    client.post(
        f"/api/admin/sms/arrivals/{arrival.id}/acknowledge",
        headers=_staff_headers(
            synthetic_arrival_data["tenant_a"], synthetic_arrival_data["admin_a"]
        ),
    )
    assert process_repeated_arrival_alerts(
        db_session, now=synthetic_arrival_data["now"] + timedelta(minutes=3)
    ) == 0
    assert db_session.query(OutboxEvent).filter(OutboxEvent.type == "arrival.alert").count() == 0


def test_cancelled_booking_stops_future_alerts(client, db_session, synthetic_arrival_data):
    client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": synthetic_arrival_data["invitation_a"].token},
    )
    synthetic_arrival_data["booking_a"].status = BookingStatus.CANCELLED
    db_session.commit()
    assert process_repeated_arrival_alerts(
        db_session, now=synthetic_arrival_data["now"] + timedelta(minutes=3)
    ) == 0
