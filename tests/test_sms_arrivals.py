"""Synthetic, no-send tests for secure arrival sessions and staff alerts."""

import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token
from app.core.state_machine import BookingStatus
from app.models.booking import Booking
from app.models.client import Client
from app.models.location import Location
from app.models.outbox import OutboxEvent
from app.models.provider import Provider
from app.models.service import Service
from app.models.sms_account import SmsAccount
from app.models.sms_arrival import SmsArrivalSession
from app.models.sms_conversation import SmsConversation
from app.models.sms_outbox import SmsConversationEvent
from app.models.tenant import Tenant
from app.models.user import User
from app.main import limiter as public_route_limiter
from app.api.routers.sms_arrivals import arrival_capability_limiter
from app.services.sms.arrival_service import (
    ArrivalNotFoundError,
    ArrivalPersistenceError,
    ArrivalStateError,
    acknowledge_arrival,
    create_arrival_session,
    hash_arrival_token,
    mark_customer_arrived,
    process_repeated_arrival_alerts,
)


@pytest.fixture(autouse=True)
def _isolate_arrival_rate_limiter():
    """Keep shared in-memory SlowAPI state from leaking between API tests."""

    public_route_limiter.reset()
    arrival_capability_limiter.reset()
    yield
    public_route_limiter.reset()
    arrival_capability_limiter.reset()


@pytest.fixture
def enabled_arrival_alerts(monkeypatch):
    """Explicitly enable the synthetic-only producer for alert tests."""

    from app.services.sms import arrival_service

    monkeypatch.setattr(
        arrival_service.settings, "ARRIVAL_ALERT_PRODUCTION_ENABLED", True
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
    assert invitation.token not in repr(invitation)
    assert invitation.token not in repr(invitation.session)


def test_invitation_creation_records_structural_event(
    db_session, synthetic_arrival_data
):
    invitation = synthetic_arrival_data["invitation_a"]
    event_row = (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id
            == synthetic_arrival_data["conversation_a"].id,
            SmsConversationEvent.type == "arrival_invitation_issued",
        )
        .one()
    )
    serialized = json.dumps(event_row.meta)
    assert event_row.meta["arrival_session_id"] == invitation.session.id
    assert invitation.token not in serialized
    assert synthetic_arrival_data["client_a"].phone not in serialized


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


def test_public_arrival_openapi_declares_bounded_body_without_token_parameter(client):
    operation = client.app.openapi()["paths"][
        "/api/admin/sms/arrivals/public/arrive"
    ]["post"]
    schema = operation["requestBody"]["content"]["application/json"]["schema"]
    token_schema = schema["properties"]["token"]
    assert operation["requestBody"]["required"] is True
    assert token_schema["format"] == "password"
    assert token_schema["writeOnly"] is True
    assert token_schema["minLength"] == 24
    assert token_schema["maxLength"] == 512
    assert "parameters" not in operation
    assert "422" not in operation["responses"]


def test_invalid_body_token_is_not_reflected(client):
    invalid_token = "synthetic-secret"
    response = client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": invalid_token},
    )
    assert response.status_code == 404
    assert invalid_token not in response.text


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (b"", "application/json"),
        (b"null", "application/json"),
        (b"[]", "application/json"),
        (b'{"token": 123}', "application/json"),
        (b'{"token": {"value": "CAPABILITY_CANARY_DO_NOT_REFLECT"}}', "application/json"),
        (b'{"token": "CAPABILITY_CANARY_DO_NOT_REFLECT", "extra": true}', "application/json"),
        (b'{"token": "CAPABILITY_CANARY_DO_NOT_REFLECT"', "application/json"),
        (
            json.dumps(
                {"token": "CAPABILITY_CANARY_DO_NOT_REFLECT" + ("x" * 1100)}
            ).encode(),
            "application/json",
        ),
        (b'{"token": "CAPABILITY_CANARY_DO_NOT_REFLECT"}', "text/plain"),
    ],
    ids=(
        "empty",
        "null",
        "array",
        "numeric-token",
        "nested-token",
        "extra-field",
        "truncated-json",
        "oversized",
        "wrong-content-type",
    ),
)
def test_malformed_capability_bodies_share_non_reflecting_contract(
    client, caplog, body, content_type
):
    marker = "CAPABILITY_CANARY_DO_NOT_REFLECT"
    response = client.post(
        "/api/admin/sms/arrivals/public/arrive",
        content=body,
        headers={"Content-Type": content_type},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert (
        response.json()["error"]["message"]
        == "Arrival session is invalid or expired."
    )
    assert response.json()["error"]["details"] == {}
    assert marker not in response.text
    assert marker not in caplog.text


def test_public_arrival_rate_limit_is_explicit_and_non_reflecting(
    client, synthetic_arrival_data
):
    capability = synthetic_arrival_data["invitation_a"].token
    for _ in range(10):
        response = client.post(
            "/api/admin/sms/arrivals/public/arrive",
            json={"token": capability},
        )
        assert response.status_code == 200

    limited = client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": capability},
    )
    assert limited.status_code == 429
    assert capability not in limited.text


def test_digest_lookup_does_not_bind_raw_capability(
    client, engine, synthetic_arrival_data
):
    raw_token = synthetic_arrival_data["invitation_a"].token
    captured_parameters = []

    def capture_parameters(_conn, _cursor, statement, parameters, _context, _many):
        if "sms_arrival_sessions" in statement and "token" in statement:
            captured_parameters.append(parameters)

    event.listen(engine, "before_cursor_execute", capture_parameters)
    try:
        response = client.post(
            "/api/admin/sms/arrivals/public/arrive",
            json={"token": raw_token},
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_parameters)

    assert response.status_code == 200
    assert captured_parameters
    assert raw_token not in repr(captured_parameters)
    assert hash_arrival_token(raw_token) in repr(captured_parameters)


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
    db_session.refresh(invitation_b.session)
    assert invitation_b.session.token == hash_arrival_token(legacy_token)
    assert legacy_token not in repr(invitation_b.session)


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


def test_creation_retries_token_digest_collision_without_losing_outer_state(
    db_session, synthetic_arrival_data, monkeypatch
):
    from app.services.sms import arrival_service

    raw_collision = "synthetic-arrival-token-collision-0001"
    raw_success = "synthetic-arrival-token-success-0000002"
    synthetic_arrival_data["invitation_b"].session.token = hash_arrival_token(
        raw_collision
    )
    db_session.delete(synthetic_arrival_data["invitation_a"].session)
    db_session.flush()
    sentinel = Tenant(
        name="SYNTHETIC Outer Transaction Sentinel",
        subdomain="synthetic-arrival-sentinel",
    )
    db_session.add(sentinel)
    generated = iter((raw_collision, raw_success))
    monkeypatch.setattr(
        arrival_service.secrets, "token_urlsafe", lambda _size: next(generated)
    )

    invitation = create_arrival_session(
        db_session,
        tenant_id=synthetic_arrival_data["tenant_a"].id,
        conversation_id=synthetic_arrival_data["conversation_a"].id,
        booking_id=synthetic_arrival_data["booking_a"].id,
    )

    assert invitation.token == raw_success
    assert invitation.session.token == hash_arrival_token(raw_success)
    assert db_session.query(Tenant).filter(Tenant.id == sentinel.id).one() is sentinel


def test_creation_fails_structurally_after_bounded_token_collisions(
    db_session, synthetic_arrival_data, monkeypatch
):
    from app.services.sms import arrival_service

    raw_collision = "synthetic-arrival-token-collision-bounded"
    synthetic_arrival_data["invitation_b"].session.token = hash_arrival_token(
        raw_collision
    )
    db_session.delete(synthetic_arrival_data["invitation_a"].session)
    db_session.flush()
    monkeypatch.setattr(
        arrival_service.secrets, "token_urlsafe", lambda _size: raw_collision
    )

    with pytest.raises(
        ArrivalPersistenceError, match="arrival session could not be created"
    ) as captured:
        create_arrival_session(
            db_session,
            tenant_id=synthetic_arrival_data["tenant_a"].id,
            conversation_id=synthetic_arrival_data["conversation_a"].id,
            booking_id=synthetic_arrival_data["booking_a"].id,
        )

    assert captured.value.__cause__ is None
    assert (
        db_session.query(SmsArrivalSession)
        .filter(SmsArrivalSession.booking_id == synthetic_arrival_data["booking_a"].id)
        .count()
        == 0
    )


def test_creation_maps_only_booking_unique_integrity_to_domain_conflict(
    db_session, synthetic_arrival_data
):
    db_session.delete(synthetic_arrival_data["invitation_a"].session)
    db_session.flush()

    def fail_with_booking_unique(_mapper, _connection, _target):
        raise IntegrityError(
            "synthetic", {}, Exception(
                "UNIQUE constraint failed: sms_arrival_sessions.booking_id"
            )
        )

    event.listen(SmsArrivalSession, "before_insert", fail_with_booking_unique)
    try:
        with pytest.raises(ArrivalStateError, match="already exists"):
            create_arrival_session(
                db_session,
                tenant_id=synthetic_arrival_data["tenant_a"].id,
                conversation_id=synthetic_arrival_data["conversation_a"].id,
                booking_id=synthetic_arrival_data["booking_a"].id,
            )
    finally:
        event.remove(SmsArrivalSession, "before_insert", fail_with_booking_unique)


def test_creation_translates_unrelated_integrity_without_losing_outer_state(
    db_session, synthetic_arrival_data
):
    db_session.delete(synthetic_arrival_data["invitation_a"].session)
    db_session.flush()
    sentinel = Tenant(
        name="SYNTHETIC Persistence Sentinel",
        subdomain="synthetic-persistence-sentinel",
    )
    db_session.add(sentinel)

    def fail_structurally(_mapper, _connection, _target):
        raise IntegrityError(
            "synthetic", {}, Exception("synthetic unrelated constraint")
        )

    event.listen(SmsConversationEvent, "before_insert", fail_structurally)
    try:
        with pytest.raises(
            ArrivalPersistenceError, match="arrival session could not be created"
        ) as captured:
            create_arrival_session(
                db_session,
                tenant_id=synthetic_arrival_data["tenant_a"].id,
                conversation_id=synthetic_arrival_data["conversation_a"].id,
                booking_id=synthetic_arrival_data["booking_a"].id,
            )
    finally:
        event.remove(SmsConversationEvent, "before_insert", fail_structurally)

    assert captured.value.__cause__ is None
    assert db_session.query(Tenant).filter(Tenant.id == sentinel.id).one() is sentinel
    assert (
        db_session.query(SmsArrivalSession)
        .filter(SmsArrivalSession.booking_id == synthetic_arrival_data["booking_a"].id)
        .count()
        == 0
    )


def test_creation_rejects_cross_tenant_booking_location(
    db_session, synthetic_arrival_data
):
    db_session.delete(synthetic_arrival_data["invitation_a"].session)
    wrong_location = Location(
        tenant_id=synthetic_arrival_data["tenant_b"].id,
        name="SYNTHETIC Wrong Tenant Location",
        active=True,
    )
    db_session.add(wrong_location)
    db_session.flush()
    synthetic_arrival_data["booking_a"].location_id = wrong_location.id
    db_session.flush()

    with pytest.raises(ArrivalNotFoundError):
        create_arrival_session(
            db_session,
            tenant_id=synthetic_arrival_data["tenant_a"].id,
            conversation_id=synthetic_arrival_data["conversation_a"].id,
            booking_id=synthetic_arrival_data["booking_a"].id,
        )


def test_conditional_arrive_and_acknowledge_have_one_winner(
    db_session, synthetic_arrival_data
):
    invitation = synthetic_arrival_data["invitation_a"]
    first_arrive = mark_customer_arrived(
        db_session, invitation.token, now=synthetic_arrival_data["now"]
    )
    second_arrive = mark_customer_arrived(
        db_session, invitation.token, now=synthetic_arrival_data["now"]
    )
    assert first_arrive.changed is True
    assert second_arrive.changed is False

    first_ack = acknowledge_arrival(
        db_session,
        tenant_id=synthetic_arrival_data["tenant_a"].id,
        arrival_id=invitation.session.id,
        actor_user_id=synthetic_arrival_data["admin_a"].id,
        now=synthetic_arrival_data["now"] + timedelta(seconds=1),
    )
    second_ack = acknowledge_arrival(
        db_session,
        tenant_id=synthetic_arrival_data["tenant_a"].id,
        arrival_id=invitation.session.id,
        actor_user_id=synthetic_arrival_data["admin_a"].id,
        now=synthetic_arrival_data["now"] + timedelta(seconds=2),
    )
    assert first_ack.changed is True
    assert second_ack.changed is False
    assert (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id
            == synthetic_arrival_data["conversation_a"].id,
            SmsConversationEvent.type == "customer_arrived",
        )
        .count()
        == 1
    )
    assert (
        db_session.query(SmsConversationEvent)
        .filter(
            SmsConversationEvent.conversation_id
            == synthetic_arrival_data["conversation_a"].id,
            SmsConversationEvent.type == "arrival_acknowledged",
        )
        .count()
        == 1
    )


def test_lifecycle_paths_request_arrival_row_locks(
    db_session, synthetic_arrival_data, monkeypatch
):
    from sqlalchemy.orm import Query

    requested_lock_targets = []
    original_with_for_update = Query.with_for_update

    def record_lock_target(query, *args, **kwargs):
        requested_lock_targets.append(kwargs.get("of"))
        return original_with_for_update(query, *args, **kwargs)

    monkeypatch.setattr(Query, "with_for_update", record_lock_target)
    invitation = synthetic_arrival_data["invitation_a"]
    mark_customer_arrived(
        db_session, invitation.token, now=synthetic_arrival_data["now"]
    )
    acknowledge_arrival(
        db_session,
        tenant_id=synthetic_arrival_data["tenant_a"].id,
        arrival_id=invitation.session.id,
        actor_user_id=synthetic_arrival_data["admin_a"].id,
        now=synthetic_arrival_data["now"] + timedelta(seconds=1),
    )
    assert sum(
        1
        for target in requested_lock_targets
        if isinstance(target, tuple)
        and SmsArrivalSession in target
        and Booking in target
    ) >= 2


def test_repeated_alerts_use_durable_structural_deduplication(
    client, db_session, synthetic_arrival_data, enabled_arrival_alerts
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


def test_acknowledgement_stops_future_alerts(
    client, db_session, synthetic_arrival_data, enabled_arrival_alerts
):
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


def test_acknowledgement_quarantines_pending_alert(
    client, db_session, synthetic_arrival_data, enabled_arrival_alerts
):
    client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": synthetic_arrival_data["invitation_a"].token},
    )
    arrival = synthetic_arrival_data["invitation_a"].session
    arrival.arrived_at = synthetic_arrival_data["now"]
    db_session.commit()
    assert process_repeated_arrival_alerts(
        db_session, now=synthetic_arrival_data["now"] + timedelta(minutes=2)
    ) == 1

    response = client.post(
        f"/api/admin/sms/arrivals/{arrival.id}/acknowledge",
        headers=_staff_headers(
            synthetic_arrival_data["tenant_a"], synthetic_arrival_data["admin_a"]
        ),
    )
    assert response.status_code == 200
    alert = (
        db_session.query(OutboxEvent)
        .filter(OutboxEvent.type == "arrival.alert")
        .one()
    )
    assert alert.status == "QUARANTINED"
    assert alert.processed is True
    assert alert.error_code == "ARRIVAL_ACKNOWLEDGED"
    assert alert.terminal_at is not None
    assert alert.next_attempt_at is None


def test_acknowledgement_does_not_claim_to_recall_leased_alert(
    client, db_session, synthetic_arrival_data, enabled_arrival_alerts
):
    client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": synthetic_arrival_data["invitation_a"].token},
    )
    arrival = synthetic_arrival_data["invitation_a"].session
    arrival.arrived_at = synthetic_arrival_data["now"]
    db_session.commit()
    assert process_repeated_arrival_alerts(
        db_session, now=synthetic_arrival_data["now"] + timedelta(minutes=2)
    ) == 1
    alert = db_session.query(OutboxEvent).filter(OutboxEvent.type == "arrival.alert").one()
    alert.status = "PROCESSING"
    alert.next_attempt_at = None
    alert.lease_owner = "synthetic-worker"
    alert.lease_token = "00000000-0000-0000-0000-000000000001"
    alert.lease_expires_at = synthetic_arrival_data["now"] + timedelta(minutes=5)
    db_session.commit()

    response = client.post(
        f"/api/admin/sms/arrivals/{arrival.id}/acknowledge",
        headers=_staff_headers(
            synthetic_arrival_data["tenant_a"], synthetic_arrival_data["admin_a"]
        ),
    )
    assert response.status_code == 200
    db_session.refresh(alert)
    assert alert.status == "PROCESSING"


def test_cancelled_booking_stops_future_alerts(
    client, db_session, synthetic_arrival_data, enabled_arrival_alerts
):
    client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": synthetic_arrival_data["invitation_a"].token},
    )
    synthetic_arrival_data["booking_a"].status = BookingStatus.CANCELLED
    db_session.commit()
    assert process_repeated_arrival_alerts(
        db_session, now=synthetic_arrival_data["now"] + timedelta(minutes=3)
    ) == 0


def test_cancelled_booking_quarantines_existing_pending_alert(
    client, db_session, synthetic_arrival_data, enabled_arrival_alerts
):
    client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": synthetic_arrival_data["invitation_a"].token},
    )
    arrival = synthetic_arrival_data["invitation_a"].session
    arrival.arrived_at = synthetic_arrival_data["now"]
    db_session.commit()
    assert process_repeated_arrival_alerts(
        db_session, now=synthetic_arrival_data["now"] + timedelta(minutes=2)
    ) == 1
    synthetic_arrival_data["booking_a"].status = BookingStatus.CANCELLED
    db_session.commit()

    assert process_repeated_arrival_alerts(
        db_session, now=synthetic_arrival_data["now"] + timedelta(minutes=3)
    ) == 0
    alert = db_session.query(OutboxEvent).filter(OutboxEvent.type == "arrival.alert").one()
    assert alert.status == "QUARANTINED"
    assert alert.error_code == "ARRIVAL_BOOKING_INELIGIBLE"


def test_ineligible_booking_is_listed_and_may_be_operationally_acknowledged(
    client, db_session, synthetic_arrival_data
):
    client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": synthetic_arrival_data["invitation_a"].token},
    )
    arrival = synthetic_arrival_data["invitation_a"].session
    synthetic_arrival_data["booking_a"].status = BookingStatus.CANCELLED
    db_session.commit()
    headers = _staff_headers(
        synthetic_arrival_data["tenant_a"], synthetic_arrival_data["admin_a"]
    )

    listed = client.get("/api/admin/sms/arrivals", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["state"] == "ineligible"
    acknowledged = client.post(
        f"/api/admin/sms/arrivals/{arrival.id}/acknowledge", headers=headers
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"


def test_alert_batch_is_bounded_and_deterministic(
    db_session, synthetic_arrival_data, monkeypatch, enabled_arrival_alerts
):
    from app.services.sms import arrival_service

    for key in ("invitation_a", "invitation_b"):
        mutation = mark_customer_arrived(
            db_session,
            synthetic_arrival_data[key].token,
            now=synthetic_arrival_data["now"],
        )
        assert mutation.changed is True
    db_session.commit()
    monkeypatch.setattr(arrival_service, "ARRIVAL_ALERT_BATCH_LIMIT", 1)

    assert process_repeated_arrival_alerts(
        db_session, now=synthetic_arrival_data["now"] + timedelta(minutes=2)
    ) == 1
    outbox = db_session.query(OutboxEvent).filter(OutboxEvent.type == "arrival.alert").one()
    expected_id = min(
        synthetic_arrival_data["invitation_a"].session.id,
        synthetic_arrival_data["invitation_b"].session.id,
    )
    assert outbox.data()["arrival_session_id"] == expected_id
    assert process_repeated_arrival_alerts(
        db_session, now=synthetic_arrival_data["now"] + timedelta(minutes=2)
    ) == 1
    assert (
        db_session.query(OutboxEvent)
        .filter(OutboxEvent.type == "arrival.alert")
        .count()
        == 2
    )


def test_alert_batch_progresses_beyond_one_hundred_and_across_tenants(
    db_session, synthetic_arrival_data, enabled_arrival_alerts
):
    now = synthetic_arrival_data["now"]
    invitation_a = synthetic_arrival_data["invitation_a"]
    invitation_b = synthetic_arrival_data["invitation_b"]
    invitation_a.session.arrived_at = now
    invitation_b.session.arrived_at = now - timedelta(seconds=1)

    for index in range(100):
        booking = Booking(
            tenant_id=synthetic_arrival_data["tenant_a"].id,
            client_id=synthetic_arrival_data["client_a"].id,
            provider_id=synthetic_arrival_data["provider_a"].id,
            service_id=synthetic_arrival_data["booking_a"].service_id,
            start_time=now + timedelta(hours=3, minutes=index),
            end_time=now + timedelta(hours=3, minutes=index + 30),
            status=BookingStatus.CONFIRMED,
            idempotency_key=f"synthetic-arrival-bulk-{index}",
        )
        db_session.add(booking)
        db_session.flush()
        db_session.add(
            SmsArrivalSession(
                booking_id=booking.id,
                conversation_id=synthetic_arrival_data["conversation_a"].id,
                token=hash_arrival_token(
                    f"synthetic-arrival-bulk-token-{index:04d}-long-enough"
                ),
                arrived_at=now,
                created_at=now,
            )
        )
    db_session.commit()

    alert_time = now + timedelta(minutes=2)
    assert process_repeated_arrival_alerts(db_session, now=alert_time) == 100
    assert process_repeated_arrival_alerts(db_session, now=alert_time) == 2
    alerts = db_session.query(OutboxEvent).filter(OutboxEvent.type == "arrival.alert")
    assert alerts.count() == 102
    assert (
        alerts.filter(
            OutboxEvent.tenant_id == synthetic_arrival_data["tenant_b"].id
        ).count()
        == 1
    )


def test_alert_production_is_disabled_by_default_without_starting_transaction(
    db_session, synthetic_arrival_data
):
    invitation = synthetic_arrival_data["invitation_a"]
    invitation.session.arrived_at = synthetic_arrival_data["now"] - timedelta(
        minutes=2
    )
    db_session.commit()
    assert db_session.in_transaction() is False

    assert process_repeated_arrival_alerts(
        db_session, now=synthetic_arrival_data["now"]
    ) == 0
    assert db_session.in_transaction() is False
    assert db_session.query(OutboxEvent).filter(
        OutboxEvent.type == "arrival.alert"
    ).count() == 0


def test_enabled_alert_noop_completes_owned_transaction(
    db_session, synthetic_arrival_data, enabled_arrival_alerts
):
    db_session.commit()
    assert db_session.in_transaction() is False

    assert process_repeated_arrival_alerts(
        db_session, now=synthetic_arrival_data["now"]
    ) == 0
    assert db_session.in_transaction() is False


def test_enabled_alert_preserves_caller_transaction_and_rollback(
    db_session, synthetic_arrival_data, enabled_arrival_alerts
):
    sentinel = Tenant(
        name="SYNTHETIC Arrival Transaction Sentinel",
        subdomain="synthetic-arrival-transaction-sentinel",
    )
    db_session.add(sentinel)
    db_session.flush()
    sentinel_id = sentinel.id
    assert db_session.in_transaction() is True

    assert process_repeated_arrival_alerts(
        db_session, now=synthetic_arrival_data["now"]
    ) == 0
    assert db_session.in_transaction() is True

    db_session.rollback()
    assert db_session.query(Tenant).filter(Tenant.id == sentinel_id).first() is None


def test_expired_candidates_are_excluded_before_bounded_alert_batch(
    db_session, synthetic_arrival_data, enabled_arrival_alerts
):
    now = synthetic_arrival_data["now"]
    eligible = synthetic_arrival_data["invitation_a"].session
    eligible.arrived_at = now - timedelta(minutes=3)
    eligible.created_at = now

    for index in range(100):
        start = now + timedelta(hours=10, minutes=index)
        booking = Booking(
            tenant_id=synthetic_arrival_data["tenant_a"].id,
            client_id=synthetic_arrival_data["client_a"].id,
            provider_id=synthetic_arrival_data["provider_a"].id,
            service_id=synthetic_arrival_data["booking_a"].service_id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status=BookingStatus.CONFIRMED,
            idempotency_key=f"synthetic-arrival-expired-batch-{index}",
        )
        db_session.add(booking)
        db_session.flush()
        db_session.add(
            SmsArrivalSession(
                booking_id=booking.id,
                conversation_id=synthetic_arrival_data["conversation_a"].id,
                token=hash_arrival_token(
                    f"synthetic-arrival-expired-batch-token-{index:04d}"
                ),
                arrived_at=now - timedelta(minutes=2),
                created_at=now - timedelta(days=8),
            )
        )
    db_session.commit()

    assert process_repeated_arrival_alerts(db_session, now=now) == 1
    assert (
        db_session.query(OutboxEvent)
        .filter(OutboxEvent.idempotency_key == f"arrival-alert:{eligible.id}:3")
        .count()
        == 1
    )


def test_sql_provable_scope_mismatches_do_not_starve_alert_batch(
    db_session, synthetic_arrival_data, enabled_arrival_alerts
):
    now = synthetic_arrival_data["now"]
    eligible = synthetic_arrival_data["invitation_a"].session
    eligible.arrived_at = now - timedelta(minutes=3)

    for index in range(100):
        start = now + timedelta(hours=12, minutes=index)
        booking = Booking(
            tenant_id=synthetic_arrival_data["tenant_a"].id,
            client_id=synthetic_arrival_data["client_a"].id,
            provider_id=synthetic_arrival_data["provider_a"].id,
            service_id=synthetic_arrival_data["booking_a"].service_id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status=BookingStatus.CONFIRMED,
            idempotency_key=f"synthetic-arrival-invalid-scope-{index}",
        )
        db_session.add(booking)
        db_session.flush()
        db_session.add(
            SmsArrivalSession(
                booking_id=booking.id,
                conversation_id=synthetic_arrival_data["conversation_b"].id,
                token=hash_arrival_token(
                    f"synthetic-arrival-invalid-scope-token-{index:04d}"
                ),
                arrived_at=now - timedelta(minutes=2),
                created_at=now,
            )
        )
    db_session.commit()

    assert process_repeated_arrival_alerts(db_session, now=now) == 1
    assert (
        db_session.query(OutboxEvent)
        .filter(OutboxEvent.idempotency_key == f"arrival-alert:{eligible.id}:3")
        .count()
        == 1
    )


def test_post_lock_scope_failure_is_terminally_quarantined_and_advances(
    db_session,
    synthetic_arrival_data,
    enabled_arrival_alerts,
    monkeypatch,
):
    from app.services.sms import arrival_service

    now = synthetic_arrival_data["now"]
    first = synthetic_arrival_data["invitation_a"].session
    second = synthetic_arrival_data["invitation_b"].session
    first.arrived_at = now - timedelta(minutes=2)
    second.arrived_at = now - timedelta(minutes=2, seconds=1)
    db_session.commit()
    monkeypatch.setattr(arrival_service, "ARRIVAL_ALERT_BATCH_LIMIT", 1)
    original_to_scoped = arrival_service._to_scoped

    def reject_first(row):
        if row[0].id == first.id:
            raise ArrivalNotFoundError("synthetic scope change")
        return original_to_scoped(row)

    monkeypatch.setattr(arrival_service, "_to_scoped", reject_first)

    assert process_repeated_arrival_alerts(db_session, now=now) == 0
    marker = (
        db_session.query(OutboxEvent)
        .filter(
            OutboxEvent.idempotency_key
            == f"arrival-alert:{first.id}:scope-invalid"
        )
        .one()
    )
    assert marker.tenant_id == synthetic_arrival_data["tenant_a"].id
    assert marker.status == "QUARANTINED"
    assert marker.processed is True
    assert marker.error_code == "ARRIVAL_SCOPE_INVALID"
    assert marker.next_attempt_at is None
    assert marker.data() == {"arrival_session_id": first.id}

    assert process_repeated_arrival_alerts(db_session, now=now) == 1
    assert (
        db_session.query(OutboxEvent)
        .filter(OutboxEvent.idempotency_key == f"arrival-alert:{second.id}:2")
        .count()
        == 1
    )


def test_acknowledged_capability_is_revoked_without_duplicate_events(
    client, db_session, synthetic_arrival_data
):
    invitation = synthetic_arrival_data["invitation_a"]
    headers = _staff_headers(
        synthetic_arrival_data["tenant_a"], synthetic_arrival_data["admin_a"]
    )
    assert client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": invitation.token},
    ).status_code == 200
    assert client.post(
        f"/api/admin/sms/arrivals/{invitation.session.id}/acknowledge",
        headers=headers,
    ).status_code == 200
    event_count = db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id
        == synthetic_arrival_data["conversation_a"].id
    ).count()

    replay = client.post(
        "/api/admin/sms/arrivals/public/arrive",
        json={"token": invitation.token},
    )
    assert replay.status_code == 404
    assert replay.json()["error"]["message"] == "Arrival session is invalid or expired."
    assert invitation.token not in replay.text
    assert db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id
        == synthetic_arrival_data["conversation_a"].id
    ).count() == event_count


def test_acknowledge_service_rejects_untrusted_actor_ids(
    db_session, synthetic_arrival_data
):
    invitation = synthetic_arrival_data["invitation_a"]
    mark_customer_arrived(
        db_session, invitation.token, now=synthetic_arrival_data["now"]
    )
    staff = User(
        tenant_id=synthetic_arrival_data["tenant_a"].id,
        login="synthetic-arrival-staff",
        password_hash="synthetic-not-a-credential",
        role="staff",
    )
    db_session.add(staff)
    db_session.flush()

    for actor_id in (
        staff.id,
        synthetic_arrival_data["admin_b"].id,
        9_223_372_036_854_775_000,
    ):
        with pytest.raises(ArrivalNotFoundError, match="unavailable"):
            acknowledge_arrival(
                db_session,
                tenant_id=synthetic_arrival_data["tenant_a"].id,
                arrival_id=invitation.session.id,
                actor_user_id=actor_id,
                now=synthetic_arrival_data["now"],
            )

    db_session.refresh(invitation.session)
    assert invitation.session.acknowledged_at is None
    assert db_session.query(SmsConversationEvent).filter(
        SmsConversationEvent.conversation_id
        == synthetic_arrival_data["conversation_a"].id,
        SmsConversationEvent.type == "arrival_acknowledged",
    ).count() == 0
