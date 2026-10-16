"""Lease, replay and scoped idempotency behavior."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
import sys
import threading
import time
import uuid

CCC_ROOT = Path(__file__).resolve().parents[1]
if str(CCC_ROOT) not in sys.path:
    sys.path.insert(0, str(CCC_ROOT))

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from backend.middleware.v2_errors import SupervisorHTTPError
from backend.config import settings
from backend.models.codex import IdempotencyRecord, Project, SupervisorEvent
from backend.services.actor_scope import ActorScope
from backend.services.idempotency_service import (
    canonical_fingerprint,
    reserve,
    terminalize_failure,
    utc_now,
)
from backend.services.supervisor_repository import claim_reserved_project
from test_supervisor_bootstrap_claim import configured_project, migrated_engine


def test_active_identical_reservation_returns_observable_202_state(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    actor = ActorScope(tenant_id=1, user_id=2)
    key = str(uuid.uuid4())
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id="prj_1234567890abcdef",
        expected_version=0,
        confirmation=True,
    )
    try:
        first = reserve(actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine)
        second = reserve(actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine)
        assert first.mode == "execute"
        assert second.mode == "in_progress"
        assert second.request_id == first.request_id
    finally:
        engine.dispose()


def test_expired_lease_is_cas_reclaimed_with_original_request_id(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    actor = ActorScope(tenant_id=3, user_id=4)
    key = str(uuid.uuid4())
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id="prj_1234567890abcdef",
        expected_version=0,
        confirmation=True,
    )
    try:
        first = reserve(actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine)
        with engine.begin() as connection:
            connection.execute(
                update(IdempotencyRecord.__table__)
                .where(IdempotencyRecord.__table__.c.id == first.record_id)
                .values(lease_expires_at=utc_now() - timedelta(seconds=1))
            )
        reclaimed = reserve(
            actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine
        )
        assert reclaimed.mode == "execute"
        assert reclaimed.request_id == first.request_id
        assert reclaimed.raw_lease_token != first.raw_lease_token
    finally:
        engine.dispose()


def test_terminal_success_replays_exact_body_and_conflicting_fingerprint_fails(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=5, user_id=6)
    key = str(uuid.uuid4())
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id=configured.public_id,
        expected_version=0,
        confirmation=True,
    )
    try:
        reservation = reserve(
            actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine
        )
        success = claim_reserved_project(
            actor=actor,
            configured=configured,
            reservation=reservation,
            idempotency_key=key,
            expected_version=0,
            db_engine=engine,
        )
        replay = reserve(
            actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine
        )
        assert replay.mode == "replay"
        assert replay.request_id == success.request_id
        assert replay.response_body == success.response_body
        assert replay.response_headers == success.response_headers

        different = canonical_fingerprint(
            actor=actor,
            project_id=configured.public_id,
            expected_version=1,
            confirmation=True,
        )
        conflict = reserve(
            actor=actor, idempotency_key=key, fingerprint=different, db_engine=engine
        )
        assert conflict.mode == "conflict"
    finally:
        engine.dispose()


def test_terminal_expiry_is_completion_based_and_allows_fresh_replacement(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=7, user_id=8)
    key = str(uuid.uuid4())
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id=configured.public_id,
        expected_version=0,
        confirmation=True,
    )
    try:
        reservation = reserve(
            actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine
        )
        claim_reserved_project(
            actor=actor,
            configured=configured,
            reservation=reservation,
            idempotency_key=key,
            expected_version=0,
            db_engine=engine,
        )
        with engine.connect() as connection:
            row = connection.execute(select(IdempotencyRecord.__table__)).one()._mapping
            assert row["expires_at"] - row["completed_at"] == timedelta(hours=24)
        expired_completion = utc_now() - timedelta(hours=25)
        with engine.begin() as connection:
            connection.execute(
                update(IdempotencyRecord.__table__).values(
                    completed_at=expired_completion,
                    expires_at=expired_completion + timedelta(hours=24),
                )
            )
        replacement = reserve(
            actor=actor,
            idempotency_key=key,
            fingerprint=canonical_fingerprint(
                actor=actor,
                project_id=configured.public_id,
                expected_version=1,
                confirmation=True,
            ),
            db_engine=engine,
        )
        assert replacement.mode == "execute"
        assert replacement.request_id != reservation.request_id
    finally:
        engine.dispose()


def test_concurrent_identical_reservations_have_one_executor(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    actor = ActorScope(tenant_id=9, user_id=10)
    key = str(uuid.uuid4())
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id="prj_1234567890abcdef",
        expected_version=0,
        confirmation=True,
    )
    barrier = threading.Barrier(2)

    def contend():
        barrier.wait(timeout=5)
        return reserve(
            actor=actor,
            idempotency_key=key,
            fingerprint=fingerprint,
            db_engine=engine,
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: contend(), range(2)))
        assert sorted(result.mode for result in results) == ["execute", "in_progress"]
        assert len({result.request_id for result in results}) == 1
        with engine.connect() as connection:
            assert connection.execute(
                select(func.count()).select_from(IdempotencyRecord.__table__)
            ).scalar_one() == 1
    finally:
        engine.dispose()


def test_readable_in_progress_and_conflict_do_not_wait_for_writer_lock(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    actor = ActorScope(tenant_id=13, user_id=14)
    key = str(uuid.uuid4())
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id="prj_1234567890abcdef",
        expected_version=0,
        confirmation=True,
    )
    try:
        first = reserve(actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine)
        with engine.connect() as writer:
            writer.exec_driver_sql("PRAGMA busy_timeout=5000")
            writer.commit()
            writer.exec_driver_sql("BEGIN IMMEDIATE")
            started = time.monotonic()
            current = reserve(
                actor=actor,
                idempotency_key=key,
                fingerprint=fingerprint,
                db_engine=engine,
            )
            different = reserve(
                actor=actor,
                idempotency_key=key,
                fingerprint=canonical_fingerprint(
                    actor=actor,
                    project_id="prj_1234567890abcdef",
                    expected_version=1,
                    confirmation=True,
                ),
                db_engine=engine,
            )
            elapsed = time.monotonic() - started
            writer.rollback()
        assert first.mode == "execute"
        assert current.mode == "in_progress"
        assert different.mode == "conflict"
        assert elapsed < 1.0
    finally:
        engine.dispose()


def test_reclaimed_lease_rejects_old_executor_and_new_executor_can_claim(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=15, user_id=16)
    key = str(uuid.uuid4())
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id=configured.public_id,
        expected_version=0,
        confirmation=True,
    )
    try:
        old = reserve(actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine)
        with engine.begin() as connection:
            connection.execute(
                update(IdempotencyRecord.__table__)
                .where(IdempotencyRecord.__table__.c.id == old.record_id)
                .values(lease_expires_at=utc_now() - timedelta(seconds=1))
            )
        current = reserve(
            actor=actor,
            idempotency_key=key,
            fingerprint=fingerprint,
            db_engine=engine,
        )
        with pytest.raises(SupervisorHTTPError) as exc_info:
            claim_reserved_project(
                actor=actor,
                configured=configured,
                reservation=old,
                idempotency_key=key,
                expected_version=0,
                db_engine=engine,
            )
        assert exc_info.value.status_code == 503
        result = claim_reserved_project(
            actor=actor,
            configured=configured,
            reservation=current,
            idempotency_key=key,
            expected_version=0,
            db_engine=engine,
        )
        assert result.mode == "success"
    finally:
        engine.dispose()


def test_terminal_failed_result_replays_exactly(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    actor = ActorScope(tenant_id=17, user_id=18)
    key = str(uuid.uuid4())
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id="prj_1234567890abcdef",
        expected_version=0,
        confirmation=True,
    )
    try:
        reservation = reserve(
            actor=actor,
            idempotency_key=key,
            fingerprint=fingerprint,
            db_engine=engine,
        )
        failed = terminalize_failure(
            reservation=reservation,
            code="supervisor_unconfigured",
            status_code=503,
            db_engine=engine,
        )
        replay = reserve(
            actor=actor,
            idempotency_key=key,
            fingerprint=fingerprint,
            db_engine=engine,
        )
        assert replay.mode == "replay"
        assert replay.request_id == failed.request_id
        assert replay.response_status == failed.response_status
        assert replay.response_body == failed.response_body
        assert replay.response_headers == failed.response_headers

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE idempotency_records SET completed_at='not-a-timestamp' "
                        "WHERE id=:record_id"
                    ),
                    {"record_id": reservation.record_id},
                )
        duplicate_headers = (
            '{"Content-Type":"application/json","Content-Type":"application/json",'
            f'"Cache-Control":"no-store","X-Request-ID":"{reservation.request_id}"}}'
        )
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE idempotency_records SET response_headers=:headers "
                        "WHERE id=:record_id"
                    ),
                    {"headers": duplicate_headers, "record_id": reservation.record_id},
                )
    finally:
        engine.dispose()


def test_different_keys_racing_to_claim_create_one_event_and_terminalize_loser(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=19, user_id=20)
    keys = [str(uuid.uuid4()), str(uuid.uuid4())]
    reservations = [
        reserve(
            actor=actor,
            idempotency_key=key,
            fingerprint=canonical_fingerprint(
                actor=actor,
                project_id=configured.public_id,
                expected_version=0,
                confirmation=True,
            ),
            db_engine=engine,
        )
        for key in keys
    ]
    barrier = threading.Barrier(2)

    def claim(index: int):
        barrier.wait(timeout=5)
        try:
            return claim_reserved_project(
                actor=actor,
                configured=configured,
                reservation=reservations[index],
                idempotency_key=keys[index],
                expected_version=0,
                db_engine=engine,
            )
        except SupervisorHTTPError as exc:
            assert exc.code == "invalid_state"
            return terminalize_failure(
                reservation=reservations[index],
                code=exc.code,
                status_code=exc.status_code,
                db_engine=engine,
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(claim, range(2)))
        assert sorted(result.mode for result in results) == ["success", "terminal_failure"]
        with engine.connect() as connection:
            assert connection.execute(
                select(func.count()).select_from(SupervisorEvent.__table__)
            ).scalar_one() == 1
            statuses = connection.execute(
                select(IdempotencyRecord.__table__.c.status)
            ).scalars().all()
        assert sorted(statuses) == ["failed", "succeeded"]
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "failure_point",
    [
        "before_project_write",
        "after_project_write",
        "before_event_write",
        "after_event_write",
        "before_terminal_write",
        "after_terminal_write",
    ],
)
def test_deterministic_phase_two_failure_uses_one_outer_transaction_without_partial_side_effects(
    tmp_path: Path, failure_point: str
):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=31, user_id=32)
    key = str(uuid.uuid4())
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id=configured.public_id,
        expected_version=0,
        confirmation=True,
    )
    reservation = reserve(
        actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine
    )

    def inject(point: str) -> None:
        if point == failure_point:
            raise SupervisorHTTPError(409, "claim_guard_failed")

    try:
        failed = claim_reserved_project(
            actor=actor,
            configured=configured,
            reservation=reservation,
            idempotency_key=key,
            expected_version=0,
            db_engine=engine,
            failure_injector=inject,
        )
        assert failed.mode == "terminal_failure"
        assert failed.response_status == 409
        with engine.connect() as connection:
            assert connection.execute(select(func.count()).select_from(Project.__table__)).scalar_one() == 0
            assert connection.execute(select(func.count()).select_from(SupervisorEvent.__table__)).scalar_one() == 0
            record = connection.execute(select(IdempotencyRecord.__table__)).one()._mapping
            assert record["status"] == "failed"
        replay = reserve(
            actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine
        )
        assert replay.mode == "replay"
        assert replay.response_body == failed.response_body
        assert replay.response_headers == failed.response_headers
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "failure_point",
    ["after_project_write", "after_event_write", "after_terminal_write"],
)
def test_unexpected_phase_two_failure_rolls_back_and_leaves_reclaimable_lease(
    tmp_path: Path, failure_point: str
):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=33, user_id=34)
    key = str(uuid.uuid4())
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id=configured.public_id,
        expected_version=0,
        confirmation=True,
    )
    reservation = reserve(
        actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine
    )

    def inject(point: str) -> None:
        if point == failure_point:
            raise RuntimeError("synthetic_unexpected_failure")

    try:
        with pytest.raises(RuntimeError, match="synthetic_unexpected_failure"):
            claim_reserved_project(
                actor=actor,
                configured=configured,
                reservation=reservation,
                idempotency_key=key,
                expected_version=0,
                db_engine=engine,
                failure_injector=inject,
            )
        with engine.connect() as connection:
            assert connection.execute(select(func.count()).select_from(Project.__table__)).scalar_one() == 0
            assert connection.execute(select(func.count()).select_from(SupervisorEvent.__table__)).scalar_one() == 0
            record = connection.execute(select(IdempotencyRecord.__table__)).one()._mapping
            assert record["status"] == "in_progress"
            assert record["completed_at"] is None
    finally:
        engine.dispose()


def test_phase_two_revalidates_configuration_and_root_before_mutation(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=35, user_id=36)
    key = str(uuid.uuid4())
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id=configured.public_id,
        expected_version=0,
        confirmation=True,
    )
    reservation = reserve(
        actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine
    )
    original_branch = settings.codex_supervisor_configured_default_branch
    settings.codex_supervisor_configured_default_branch = "changed-after-reservation"
    try:
        failed = claim_reserved_project(
            actor=actor,
            configured=configured,
            reservation=reservation,
            idempotency_key=key,
            expected_version=0,
            db_engine=engine,
        )
        assert failed.mode == "terminal_failure"
        assert failed.response_status == 409
        with engine.connect() as connection:
            assert connection.execute(select(func.count()).select_from(Project.__table__)).scalar_one() == 0
            assert connection.execute(select(func.count()).select_from(SupervisorEvent.__table__)).scalar_one() == 0
    finally:
        settings.codex_supervisor_configured_default_branch = original_branch
        engine.dispose()


@pytest.mark.parametrize(
    "failure_point",
    ["before_failure_terminal_write", "after_failure_terminal_write"],
)
def test_unexpected_failure_terminal_write_rolls_back_and_leaves_reservation_in_progress(
    tmp_path: Path, failure_point: str
):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=37, user_id=38)
    key = str(uuid.uuid4())
    requested_project_id = "prj_ffffffffffffffff"
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id=requested_project_id,
        expected_version=0,
        confirmation=True,
    )
    reservation = reserve(
        actor=actor, idempotency_key=key, fingerprint=fingerprint, db_engine=engine
    )

    def inject(point: str) -> None:
        if point == failure_point:
            raise RuntimeError("synthetic_failure_terminal_write")

    try:
        with pytest.raises(RuntimeError, match="synthetic_failure_terminal_write"):
            claim_reserved_project(
                actor=actor,
                project_id=requested_project_id,
                reservation=reservation,
                idempotency_key=key,
                expected_version=0,
                db_engine=engine,
                failure_injector=inject,
            )
        with engine.connect() as connection:
            assert connection.execute(
                select(func.count()).select_from(Project.__table__)
            ).scalar_one() == 0
            assert connection.execute(
                select(func.count()).select_from(SupervisorEvent.__table__)
            ).scalar_one() == 0
            record = connection.execute(select(IdempotencyRecord.__table__)).one()._mapping
            assert record["status"] == "in_progress"
            assert record["completed_at"] is None
    finally:
        engine.dispose()
