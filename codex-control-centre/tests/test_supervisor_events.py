"""Database-enforced supervisor audit and claimed-project invariants."""

from pathlib import Path
from datetime import datetime, timezone
import sys
import uuid

CCC_ROOT = Path(__file__).resolve().parents[1]
if str(CCC_ROOT) not in sys.path:
    sys.path.insert(0, str(CCC_ROOT))

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError

from backend.models.codex import Project, SupervisorEvent
from backend.services.actor_scope import ActorScope
from backend.services.idempotency_service import canonical_fingerprint, reserve
from backend.services.legacy_adoption_service import root_identity_for_path
from backend.services.supervisor_event_service import verify_project_chain
from backend.services.supervisor_repository import claim_reserved_project
from test_supervisor_bootstrap_claim import configured_project, migrated_engine


def _claimed(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=10, user_id=20)
    key = str(uuid.uuid4())
    reservation = reserve(
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
    claim_reserved_project(
        actor=actor,
        configured=configured,
        reservation=reservation,
        idempotency_key=key,
        expected_version=0,
        db_engine=engine,
    )
    return engine, configured


def test_event_is_single_append_only_and_digest_valid(tmp_path: Path):
    engine, configured = _claimed(tmp_path)
    try:
        with engine.connect() as connection:
            events = connection.execute(select(SupervisorEvent.__table__)).all()
            assert len(events) == 1
            assert events[0].project_sequence == 1
            assert verify_project_chain(connection, configured.public_id)
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(update(SupervisorEvent.__table__).values(outcome="failed"))
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(delete(SupervisorEvent.__table__))
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("public_id", "prj_aaaaaaaaaaaaaaaa"),
        ("name", "Changed"),
        ("repo_path", "C:/changed"),
        ("default_branch", "changed"),
        ("configured_fingerprint", "b" * 64),
        ("root_identity_digest", "0" * 64),
        ("tenant_id", 99),
        ("owner_user_id", 99),
        ("claimed_at", None),
        ("control_plane", "legacy"),
        ("scope_state", "quarantined"),
        ("version", 2),
    ],
)
def test_direct_sql_cannot_mutate_claimed_project(
    tmp_path: Path, column: str, value: object
):
    engine, _ = _claimed(tmp_path)
    try:
        # control_plane='legacy' is an unchanged value; use NULL to prove the
        # protected nullability for that parameterized case.
        applied = None if column == "control_plane" else value
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(f"UPDATE projects SET {column} = :value"), {"value": applied}
                )
    finally:
        engine.dispose()


def test_invalid_direct_claimed_insert_is_rejected(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    repository = tmp_path / "invalid-claimed-root"
    repository.mkdir()
    root_identity = root_identity_for_path(repository)
    assert root_identity is not None
    try:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(Project.__table__.insert().values(
                    id="invalid",
                    name="Invalid",
                    repo_path=str(repository),
                    root_identity_digest=root_identity[1],
                    default_branch="dev",
                    scope_state="claimed",
                    control_plane="legacy",
                    version=1,
                ))
    finally:
        engine.dispose()


def test_direct_claimed_insert_rejects_non_opaque_public_id(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    repository = tmp_path / "invalid-public-id-root"
    repository.mkdir()
    root_identity = root_identity_for_path(repository)
    assert root_identity is not None
    try:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(Project.__table__.insert().values(
                    id="invalid-public-id",
                    name="Invalid",
                    repo_path=str(repository),
                    root_identity_digest=root_identity[1],
                    default_branch="dev",
                    public_id="prj_!!!!!!!!!!!!!!!!",
                    tenant_id=1,
                    owner_user_id=1,
                    scope_state="claimed",
                    control_plane="legacy",
                    configured_fingerprint="a" * 64,
                    claimed_at=datetime.now(timezone.utc),
                    version=1,
                ))
    finally:
        engine.dispose()


def test_event_rejects_malformed_previous_digest(tmp_path: Path):
    engine, configured = _claimed(tmp_path)
    try:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(SupervisorEvent.__table__.insert().values(
                    event_key=f"evt_{uuid.uuid4().hex}",
                    project_public_id=configured.public_id,
                    project_sequence=2,
                    actor_tenant_id=10,
                    actor_user_id=20,
                    action_code="claim_project",
                    outcome="succeeded",
                    project_version=1,
                    request_id=f"req_{uuid.uuid4().hex}",
                    idempotency_key_hash="a" * 64,
                    payload="{}",
                    payload_sha256="b" * 64,
                    schema_version="0.1",
                    previous_digest="not-a-digest",
                    integrity_digest="c" * 64,
                    occurred_at=datetime.now(timezone.utc),
                ))
    finally:
        engine.dispose()
