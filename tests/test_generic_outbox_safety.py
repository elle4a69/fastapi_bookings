"""Focused regression tests for generic outbox ownership and recovery."""

import asyncio
from dataclasses import FrozenInstanceError
import json
import os
import socket
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.main import app_lifespan, app as fastapi_app
from app.models.outbox import OutboxEvent
from app.models.tenant import Tenant
from app.models.webhook import WebhookDelivery, WebhookRegistration
from app.services import outbox_worker
from app.services.outbox_service import create_outbox_event
from app import worker as worker_entrypoint


# Keep the injected clock deterministically later than real enqueue timestamps.
# Tests exercise due/lease semantics, not the wall-clock date on which they run.
NOW = datetime(2100, 1, 1, 1, 0, tzinfo=timezone.utc)
_REAL_SOCKET_CONNECT = socket.socket.connect


class _WebhookResponse:
    def __init__(self, status):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError("synthetic remote response")


class _WebhookSession:
    calls = []
    failing_urls = set()
    transaction_probe = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def post(self, url, **kwargs):
        probe = type(self).transaction_probe
        if probe is not None:
            probe()
        self.calls.append((url, kwargs))
        return _WebhookResponse(500 if url in self.failing_urls else 200)


def test_postgresql_claim_uses_skip_locked_and_database_clock():
    sql = str(
        outbox_worker._claim_statement(NOW).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "FOR UPDATE SKIP LOCKED" in sql

    class _PostgresDialect:
        name = "postgresql"

    class _PostgresBind:
        dialect = _PostgresDialect()

    observed = []

    class _FakeSession:
        def get_bind(self):
            return _PostgresBind()

        def execute(self, statement):
            observed.append(str(statement))
            return SimpleNamespace(scalar_one=lambda: NOW)

    assert outbox_worker._claim_clock(_FakeSession(), NOW - timedelta(days=1)) == NOW
    assert any("clock_timestamp" in statement for statement in observed)


def test_live_lease_is_single_owner_and_stale_token_is_fenced(db_session):
    event = create_outbox_event(db_session, "unsupported.event", {})
    db_session.commit()

    claimed = outbox_worker.claim_next_outbox_event(
        db_session, worker_id="worker:one", now=NOW
    )
    assert not db_session.in_transaction()
    assert claimed.id == event.id
    assert claimed.status == "PROCESSING"
    assert claimed.attempt_count == 1
    with pytest.raises(FrozenInstanceError):
        claimed.lease_owner = "worker:mutated"
    stale = SimpleNamespace(id=claimed.id, lease_token=claimed.lease_token)
    assert outbox_worker.claim_next_outbox_event(
        db_session, worker_id="worker:two", now=NOW
    ) is None

    db_session.query(OutboxEvent).filter(OutboxEvent.id == claimed.id).update(
        {
            OutboxEvent.lease_owner: "worker:replacement",
            OutboxEvent.lease_token: str(uuid.uuid4()),
        },
        synchronize_session=False,
    )
    db_session.commit()
    assert outbox_worker._owned_update(
        db_session, stale, {OutboxEvent.status: "SUCCEEDED"}
    ) is False


def test_expired_lease_is_recovered_and_attempts_are_bounded(db_session):
    event = create_outbox_event(db_session, "unsupported.event", {})
    db_session.flush()
    event.status = "PROCESSING"
    event.lease_owner = "worker:dead"
    event.lease_token = str(uuid.uuid4())
    event.lease_expires_at = NOW - timedelta(seconds=1)
    event.next_attempt_at = None
    event.attempt_count = 1
    event.max_attempts = 2
    db_session.commit()

    recovered = outbox_worker.claim_next_outbox_event(
        db_session, worker_id="worker:recovery", now=NOW
    )
    assert recovered.id == event.id
    assert recovered.lease_owner == "worker:recovery"
    assert recovered.attempt_count == 2

    recovered_row = db_session.get(OutboxEvent, recovered.id)
    recovered_row.lease_expires_at = NOW - timedelta(seconds=1)
    db_session.commit()
    assert outbox_worker.claim_next_outbox_event(
        db_session, worker_id="worker:third", now=NOW
    ) is None
    db_session.refresh(recovered_row)
    assert recovered_row.status == "DEAD_LETTER"
    assert recovered_row.error_code == "ATTEMPTS_EXHAUSTED"


def test_unknown_and_legacy_provider_types_are_quarantined(db_session):
    events = [
        create_outbox_event(db_session, event_type, {"sensitive": "not-logged"})
        for event_type in ("unknown.event", "SEND_SMS", "SEND_MMS", "CHATWOOT_REPLY", "PUSH_NOTIFICATION", "arrival.alert")
    ]
    db_session.commit()
    asyncio.run(outbox_worker.process_pending_outbox_events(db_session, clock=lambda: NOW))
    for event in events:
        db_session.refresh(event)
        assert event.status == "QUARANTINED"
        assert event.error_code == "EVENT_TYPE_UNSUPPORTED"


def test_poison_event_does_not_block_next_event_and_errors_are_structural(
    db_session, monkeypatch, caplog
):
    poison = create_outbox_event(db_session, "booking.created", {"private": "payload-a"})
    healthy = create_outbox_event(db_session, "booking.created", {"private": "payload-b"})
    poison.webhook_snapshot_at = NOW
    healthy.webhook_snapshot_at = NOW
    db_session.commit()

    async def fake_dispatch(_db, event, _payload):
        if event.id == poison.id:
            raise RuntimeError("customer +61400000000 secret-response")

    monkeypatch.setattr(outbox_worker, "_dispatch_claimed_event", fake_dispatch)
    asyncio.run(
        outbox_worker.process_pending_outbox_events(
            db_session, worker_id="worker:test", clock=lambda: NOW, jitter=lambda: 0.5
        )
    )
    db_session.refresh(poison)
    db_session.refresh(healthy)
    assert poison.status == "RETRY"
    assert poison.error_code == "PROVIDER_DELIVERY_FAILED"
    assert poison.next_attempt_at.replace(tzinfo=timezone.utc) == NOW + timedelta(seconds=5)
    assert healthy.status == "SUCCEEDED"
    assert "+61400000000" not in caplog.text
    assert "secret-response" not in caplog.text
    assert "payload-a" not in caplog.text


def test_cancellation_preserves_ambiguous_lease_until_expiry(db_session, monkeypatch):
    event = create_outbox_event(db_session, "booking.created", {})
    event.webhook_snapshot_at = NOW
    db_session.commit()

    async def cancelled(*_args):
        raise asyncio.CancelledError

    monkeypatch.setattr(outbox_worker, "_dispatch_claimed_event", cancelled)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(outbox_worker.process_pending_outbox_events(db_session, clock=lambda: NOW))
    db_session.refresh(event)
    assert event.status == "PROCESSING"
    assert event.lease_token is not None
    assert event.lease_expires_at.replace(tzinfo=timezone.utc) == NOW + timedelta(seconds=120)


def test_retry_backoff_is_deterministic_and_bounded():
    assert outbox_worker.retry_delay_seconds(
        1, base_seconds=5, maximum_seconds=300, jitter_ratio=0.2, jitter_value=0.0
    ) == 4
    assert outbox_worker.retry_delay_seconds(
        2, base_seconds=5, maximum_seconds=300, jitter_ratio=0.2, jitter_value=0.5
    ) == 10
    assert outbox_worker.retry_delay_seconds(
        100, base_seconds=5, maximum_seconds=300, jitter_ratio=0.2, jitter_value=1.0
    ) == 300
    first = outbox_worker.stable_retry_jitter("outbox:stable", 3)
    assert first == outbox_worker.stable_retry_jitter("outbox:stable", 3)
    assert first != outbox_worker.stable_retry_jitter("outbox:stable", 4)
    assert 0.0 <= first <= 1.0


def test_stop_event_during_batch_prevents_the_next_claim(db_session, monkeypatch):
    first = create_outbox_event(db_session, "booking.created", {})
    second = create_outbox_event(db_session, "booking.created", {})
    first.webhook_snapshot_at = NOW
    second.webhook_snapshot_at = NOW
    db_session.commit()
    stop_event = asyncio.Event()
    dispatches = []

    async def stop_after_first(_db, event, _payload):
        dispatches.append(event.id)
        stop_event.set()

    monkeypatch.setattr(outbox_worker, "_dispatch_claimed_event", stop_after_first)
    asyncio.run(
        outbox_worker.process_pending_outbox_events(
            db_session,
            worker_id="worker:graceful-stop",
            clock=lambda: NOW,
            stop_event=stop_event,
        )
    )
    db_session.refresh(first)
    db_session.refresh(second)
    assert dispatches == [first.id]
    assert first.status == "SUCCEEDED"
    assert second.status == "PENDING"
    assert second.attempt_count == 0


def test_parent_waits_for_latest_child_without_refunding_claims(db_session):
    tenant = Tenant(name="Synthetic stagger", subdomain="synthetic-stagger")
    db_session.add(tenant)
    db_session.flush()
    event = create_outbox_event(
        db_session, "booking.created", {"fixture": "synthetic"}, tenant_id=tenant.id
    )
    event.webhook_snapshot_at = NOW
    db_session.flush()
    latest_due = NOW + timedelta(hours=2)
    earlier_due = latest_due - timedelta(hours=1)
    db_session.add_all(
        [
            WebhookDelivery(
                outbox_event_id=event.id,
                tenant_id=tenant.id,
                target_url="https://8.8.8.8/a",
                encrypted_signing_secret="synthetic",
                idempotency_key=f"webhook:{event.id}:a",
                status="RETRY",
                next_attempt_at=earlier_due,
            ),
            WebhookDelivery(
                outbox_event_id=event.id,
                tenant_id=tenant.id,
                target_url="https://8.8.4.4/b",
                encrypted_signing_secret="synthetic",
                idempotency_key=f"webhook:{event.id}:b",
                status="RETRY",
                next_attempt_at=latest_due,
            ),
        ]
    )
    db_session.commit()

    for expected_attempt in (1, 2):
        asyncio.run(
            outbox_worker.process_pending_outbox_events(
                db_session, worker_id="worker:stagger", clock=lambda: NOW
            )
        )
        db_session.refresh(event)
        assert event.status == "RETRY"
        assert event.attempt_count == expected_attempt
        assert event.retry_count == 0
        assert event.error_code == "WEBHOOK_DELIVERY_PENDING"
        assert event.next_attempt_at.replace(tzinfo=timezone.utc) == latest_due
        if expected_attempt == 1:
            event.next_attempt_at = NOW
            db_session.commit()


def test_failed_webhook_round_increments_retry_and_respects_latest_child_due(
    db_session, monkeypatch
):
    event = create_outbox_event(db_session, "booking.created", {})
    event.webhook_snapshot_at = NOW
    db_session.commit()
    child_due = NOW + timedelta(minutes=3)

    async def failed_round(*_args, **_kwargs):
        raise outbox_worker.WebhookRoundIncomplete(
            next_attempt_at=child_due,
            made_attempt=True,
            terminal=False,
        )

    monkeypatch.setattr(outbox_worker, "_dispatch_claimed_event", failed_round)
    asyncio.run(
        outbox_worker.process_pending_outbox_events(
            db_session, worker_id="worker:failed-round", clock=lambda: NOW
        )
    )
    db_session.refresh(event)
    assert event.status == "RETRY"
    assert event.attempt_count == 1
    assert event.retry_count == 1
    assert event.error_code == "WEBHOOK_DELIVERY_FAILED"
    assert event.next_attempt_at.replace(tzinfo=timezone.utc) == child_due


def test_webhook_round_attempts_all_due_children_and_retry_body_is_stable(
    db_session, monkeypatch
):
    tenant = Tenant(name="Synthetic hooks", subdomain="synthetic-hooks")
    db_session.add(tenant)
    db_session.flush()
    failed_url = "https://8.8.8.8/fail"
    success_url = "https://8.8.4.4/succeed"
    db_session.add_all(
        [
            WebhookRegistration(
                tenant_id=tenant.id,
                event="booking.created",
                target_url=failed_url,
                secret="a" * 32,
            ),
            WebhookRegistration(
                tenant_id=tenant.id,
                event="booking.created",
                target_url=success_url,
                secret="b" * 32,
            ),
        ]
    )
    db_session.commit()
    event = create_outbox_event(
        db_session, "booking.created", {"fixture": "synthetic"}, tenant_id=tenant.id
    )
    db_session.commit()

    _WebhookSession.calls = []
    _WebhookSession.failing_urls = {failed_url}
    _WebhookSession.transaction_probe = None
    monkeypatch.setattr(outbox_worker.aiohttp, "TCPConnector", lambda **_kwargs: object())
    monkeypatch.setattr(outbox_worker.aiohttp, "ClientSession", lambda **_kwargs: _WebhookSession())
    monkeypatch.setattr(outbox_worker, "validate_webhook_target_url", lambda value: value)

    with pytest.raises(outbox_worker.WebhookRoundIncomplete):
        asyncio.run(
            outbox_worker.dispatch_outbound_webhooks(
                db_session, event=event, payload={"fixture": "synthetic"}
            )
        )
    assert {call[0] for call in _WebhookSession.calls} == {failed_url, success_url}
    first_failed_request = next(call[1] for call in _WebhookSession.calls if call[0] == failed_url)
    deliveries = db_session.query(WebhookDelivery).order_by(WebhookDelivery.id).all()
    assert {delivery.status for delivery in deliveries} == {"RETRY", "SUCCEEDED"}

    failed_delivery = next(delivery for delivery in deliveries if delivery.status == "RETRY")
    failed_delivery.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    _WebhookSession.calls = []
    _WebhookSession.failing_urls = set()
    asyncio.run(
        outbox_worker.dispatch_outbound_webhooks(
            db_session, event=event, payload={"fixture": "synthetic"}
        )
    )
    assert len(_WebhookSession.calls) == 1
    retried_request = _WebhookSession.calls[0][1]
    assert retried_request["data"] == first_failed_request["data"]
    assert retried_request["headers"]["X-Webhook-Timestamp"] == first_failed_request["headers"]["X-Webhook-Timestamp"]
    assert retried_request["headers"]["Idempotency-Key"] == retried_request["headers"]["X-Webhook-Delivery-Id"]
    assert db_session.query(WebhookDelivery).filter(WebhookDelivery.status != "SUCCEEDED").count() == 0


def test_crash_after_webhook_success_before_parent_commit_does_not_resend(
    db_session, monkeypatch
):
    tenant = Tenant(name="Synthetic crash", subdomain="synthetic-crash")
    db_session.add(tenant)
    db_session.flush()
    db_session.add(
        WebhookRegistration(
            tenant_id=tenant.id,
            event="booking.created",
            target_url="https://8.8.8.8/crash",
            secret="c" * 32,
        )
    )
    db_session.commit()
    event = create_outbox_event(
        db_session, "booking.created", {"fixture": "synthetic"}, tenant_id=tenant.id
    )
    db_session.commit()

    _WebhookSession.calls = []
    _WebhookSession.failing_urls = set()
    def assert_no_transaction_during_transport():
        assert not db_session.in_transaction()

    _WebhookSession.transaction_probe = assert_no_transaction_during_transport
    monkeypatch.setattr(outbox_worker.aiohttp, "TCPConnector", lambda **_kwargs: object())
    monkeypatch.setattr(outbox_worker.aiohttp, "ClientSession", lambda **_kwargs: _WebhookSession())
    monkeypatch.setattr(outbox_worker, "validate_webhook_target_url", lambda value: value)
    original_owned_update = outbox_worker._owned_update

    def crash_before_parent_finalize(db, claim, values):
        if values.get(OutboxEvent.status) == "SUCCEEDED":
            raise asyncio.CancelledError
        return original_owned_update(db, claim, values)

    monkeypatch.setattr(outbox_worker, "_owned_update", crash_before_parent_finalize)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            outbox_worker.process_pending_outbox_events(
                db_session, worker_id="worker:crash", clock=lambda: NOW
            )
        )
    assert len(_WebhookSession.calls) == 1
    db_session.refresh(event)
    delivery = db_session.query(WebhookDelivery).filter_by(outbox_event_id=event.id).one()
    assert event.status == "PROCESSING"
    assert delivery.status == "SUCCEEDED"

    monkeypatch.setattr(outbox_worker, "_owned_update", original_owned_update)
    event.lease_expires_at = NOW - timedelta(seconds=1)
    db_session.commit()
    asyncio.run(
        outbox_worker.process_pending_outbox_events(
            db_session, worker_id="worker:recovery", clock=lambda: NOW
        )
    )
    db_session.refresh(event)
    assert event.status == "SUCCEEDED"
    assert event.attempt_count == 2
    assert len(_WebhookSession.calls) == 1
    _WebhookSession.transaction_probe = None


def test_fastapi_lifespan_does_not_start_a_worker(monkeypatch):
    monkeypatch.setattr(
        asyncio,
        "create_task",
        lambda *_args, **_kwargs: pytest.fail("FastAPI lifespan started a worker"),
    )

    async def enter_lifespan():
        async with app_lifespan(fastapi_app):
            pass

    asyncio.run(enter_lifespan())


def test_worker_supervisor_allows_completion_within_grace():
    completed = []

    async def role(stop_event):
        await stop_event.wait()
        completed.append(True)

    async def scenario():
        stop_event = asyncio.Event()
        supervised = asyncio.create_task(
            worker_entrypoint._supervise_worker(
                role, stop_event, grace_seconds=1.0
            )
        )
        await asyncio.sleep(0)
        stop_event.set()
        await supervised

    asyncio.run(scenario())
    assert completed == [True]


def test_worker_supervisor_forces_timeout_and_preserves_claimed_lease(
    db_session, monkeypatch
):
    event = create_outbox_event(db_session, "booking.created", {})
    event.webhook_snapshot_at = NOW
    db_session.commit()

    async def scenario():
        claimed = asyncio.Event()
        never_finishes = asyncio.Event()

        async def stuck_dispatch(*_args):
            claimed.set()
            await never_finishes.wait()

        async def role(stop_event):
            await outbox_worker.process_pending_outbox_events(
                db_session,
                worker_id="worker:forced-stop",
                clock=lambda: NOW,
                stop_event=stop_event,
            )

        monkeypatch.setattr(outbox_worker, "_dispatch_claimed_event", stuck_dispatch)
        stop_event = asyncio.Event()
        supervised = asyncio.create_task(
            worker_entrypoint._supervise_worker(
                role, stop_event, grace_seconds=0.01
            )
        )
        await asyncio.wait_for(claimed.wait(), timeout=1.0)
        stop_event.set()
        await supervised

    asyncio.run(scenario())
    db_session.refresh(event)
    assert event.status == "PROCESSING"
    assert event.lease_token is not None
    assert event.lease_expires_at.replace(tzinfo=timezone.utc) == NOW + timedelta(seconds=120)


def test_worker_supervisor_returns_if_worker_exits_before_signal():
    async def role(_stop_event):
        return None

    asyncio.run(
        worker_entrypoint._supervise_worker(
            role, asyncio.Event(), grace_seconds=1.0
        )
    )


def test_worker_cli_and_migration_contracts():
    worker_source = Path("app/worker.py").read_text(encoding="utf-8")
    migration = Path(
        "alembic/versions/d7e8f9a0b1c2_add_generic_outbox_leases.py"
    ).read_text(encoding="utf-8")
    assert "python -m app.worker {generic|sms}" in worker_source
    assert "OUTBOX_SHUTDOWN_GRACE_SECONDS" in worker_source
    assert 'down_revision = "4c9f0a1b2d3e"' in migration
    assert "FOR UPDATE" not in migration
    assert "ck_outbox_events_lease_state" in migration
    assert "ck_webhook_deliveries_lease_state" in migration
    assert "LEGACY_OUTCOME_UNKNOWN" in migration
    assert "retry_count >= 5" in migration
    assert "attempt_count >= 5" in migration
    assert "NOT VALID" in migration
    assert "VALIDATE CONSTRAINT" in migration
    assert "dispatch_started_at" in migration
    assert "provider_delivery_id" in migration
    assert "ck_outbox_events_next_attempt_state" in migration
    assert "ck_webhook_deliveries_next_attempt_state" in migration
    for required_fragment in (
        "retry_count >= 0",
        "max_attempts BETWEEN 1 AND 100",
        "status IN ('PENDING','RETRY') AND next_attempt_at IS NOT NULL",
        "status = 'PROCESSING' AND lease_owner IS NOT NULL",
        "status IN ('SUCCEEDED','QUARANTINED','DEAD_LETTER') AND processed",
        "status IN ('SUCCEEDED','DEAD_LETTER','QUARANTINED') AND terminal_at IS NOT NULL",
    ):
        assert required_fragment in migration
    assert "postgresql_where" in migration
    assert 'op.drop_column("outbox_events", "error_log")' in migration
    assert "error_log = error_code" not in migration
    assert "WHEN status = 'RETRY' THEN 'FAILED'" in migration
    assert "ELSE 'QUARANTINED'" in migration


@pytest.mark.skipif(
    not os.environ.get("OUTBOX_CONCURRENCY_TEST_DATABASE_URL"),
    reason="requires an explicitly configured disposable migrated PostgreSQL database",
)
def test_twenty_postgresql_sessions_deliver_one_event_once(monkeypatch):
    database_url = os.environ["OUTBOX_CONCURRENCY_TEST_DATABASE_URL"]
    parsed = make_url(database_url)
    if parsed.host not in {"localhost", "127.0.0.1", "::1"} or "test" not in (parsed.database or "").lower():
        pytest.fail("OUTBOX_CONCURRENCY_TEST_DATABASE_URL must target a local disposable test database")
    monkeypatch.setattr(socket.socket, "connect", _REAL_SOCKET_CONNECT)
    engine = create_engine(database_url)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    pg_now = datetime.now(timezone.utc)
    event_key = f"outbox:concurrency:{uuid.uuid4()}"
    with sessions() as session:
        event = OutboxEvent(
            type="booking.created",
            payload=json.dumps({"fixture": "synthetic"}),
            status="PENDING",
            processed=False,
            webhook_snapshot_at=NOW,
            idempotency_key=event_key,
            max_attempts=5,
            next_attempt_at=pg_now - timedelta(seconds=1),
        )
        session.add(event)
        session.commit()
        event_id = event.id

    dispatch_count = 0
    dispatch_lock = __import__("threading").Lock()

    async def fake_dispatch(_db, _event, _payload):
        nonlocal dispatch_count
        with dispatch_lock:
            dispatch_count += 1

    monkeypatch.setattr(outbox_worker, "_dispatch_claimed_event", fake_dispatch)

    def deliver(worker_number):
        with sessions() as session:
            asyncio.run(
                outbox_worker.process_pending_outbox_events(
                    session,
                    worker_id=f"worker:{worker_number}",
                    clock=lambda: NOW,
                )
            )

    event_ids = [event_id]
    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            list(pool.map(deliver, range(20)))
        assert dispatch_count == 1
        with sessions() as session:
            delivered = session.get(OutboxEvent, event_id)
            assert delivered.status == "SUCCEEDED"
            assert delivered.attempt_count == 1

        with sessions() as session:
            recovery = OutboxEvent(
                type="booking.created",
                payload=json.dumps({"fixture": "synthetic-recovery"}),
                status="PENDING",
                processed=False,
                webhook_snapshot_at=NOW,
                idempotency_key=f"outbox:recovery:{uuid.uuid4()}",
                max_attempts=5,
                next_attempt_at=pg_now - timedelta(seconds=1),
            )
            session.add(recovery)
            session.commit()
            recovery.status = "PROCESSING"
            recovery.attempt_count = 1
            recovery.lease_owner = "worker:stale"
            recovery.lease_token = str(uuid.uuid4())
            recovery.lease_expires_at = pg_now - timedelta(seconds=1)
            recovery.next_attempt_at = None
            recovery.dispatch_started_at = NOW
            session.commit()
            event_ids.append(recovery.id)
            stale = SimpleNamespace(id=recovery.id, lease_token=recovery.lease_token)
            recovery.lease_owner = "worker:replacement"
            recovery.lease_token = str(uuid.uuid4())
            session.commit()
        with sessions() as session:
            assert outbox_worker._owned_update(
                session, stale, {OutboxEvent.status: "SUCCEEDED"}
            ) is False
            recovered = outbox_worker.claim_next_outbox_event(
                session, worker_id="worker:recovery", now=NOW
            )
            assert recovered.id == recovery.id
            assert recovered.lease_owner == "worker:recovery"
            assert recovered.attempt_count == 2

        with sessions() as session:
            poison = OutboxEvent(
                type="booking.created",
                payload=json.dumps({"fixture": "synthetic-poison"}),
                status="PENDING",
                processed=False,
                webhook_snapshot_at=NOW,
                idempotency_key=f"outbox:poison:{uuid.uuid4()}",
                max_attempts=5,
                next_attempt_at=pg_now - timedelta(seconds=1),
            )
            healthy = OutboxEvent(
                type="booking.created",
                payload=json.dumps({"fixture": "synthetic-healthy"}),
                status="PENDING",
                processed=False,
                webhook_snapshot_at=NOW,
                idempotency_key=f"outbox:healthy:{uuid.uuid4()}",
                max_attempts=5,
                next_attempt_at=pg_now - timedelta(seconds=1),
            )
            session.add_all([poison, healthy])
            session.commit()
            event_ids.extend([poison.id, healthy.id])

            async def fake_dispatch(_db, candidate, _payload):
                if candidate.id == poison.id:
                    raise RuntimeError("synthetic poison")

            monkeypatch.setattr(outbox_worker, "_dispatch_claimed_event", fake_dispatch)
            asyncio.run(
                outbox_worker.process_pending_outbox_events(
                    session, worker_id="worker:poison-test", clock=lambda: NOW, jitter=lambda: 0.5
                )
            )
            session.refresh(poison)
            session.refresh(healthy)
            assert poison.status == "RETRY"
            assert healthy.status == "SUCCEEDED"
    finally:
        with engine.begin() as connection:
            connection.execute(delete(OutboxEvent).where(OutboxEvent.id.in_(event_ids)))
        engine.dispose()
