"""Configured project resolution and real transactional claim tests."""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import os
import subprocess
import sys
import uuid

CCC_ROOT = Path(__file__).resolve().parents[1]
if str(CCC_ROOT) not in sys.path:
    sys.path.insert(0, str(CCC_ROOT))

import pytest
from sqlalchemy import create_engine, event, func, select, text

from backend.config import settings
from backend.models.codex import IdempotencyRecord, Project, SupervisorEvent
from backend.services.actor_scope import ActorScope
from backend.services.idempotency_service import canonical_fingerprint, reserve
from backend.services.legacy_adoption_service import (
    load_configured_project,
    root_identity_for_path,
)
from backend.services.migration_readiness_service import inspect_infrastructure
from backend.services.supervisor_repository import claim_reserved_project, resolve_project_read_only


def migrated_engine(tmp_path: Path):
    database_path = tmp_path / "ccc.db"
    url = f"sqlite:///{database_path.as_posix()}"
    _run_alembic(url, "head")
    settings.database_url = url
    return create_engine(url, connect_args={"check_same_thread": False})


def _run_alembic(url: str, revision: str) -> None:
    env = {key: value for key, value in os.environ.items() if key.lower() != "database_url"}
    env["database_url"] = url
    env["OTEL_SDK_DISABLED"] = "true"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(CCC_ROOT / "alembic.ini"), "upgrade", revision],
        cwd=CCC_ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-2000:]


def configured_project(tmp_path: Path):
    repository = tmp_path / "repository"
    repository.mkdir()
    settings.codex_supervisor_configured_project_id = "prj_1234567890abcdef"
    settings.codex_supervisor_configured_project_root = str(repository)
    settings.codex_supervisor_configured_project_name = "FastAPI Bookings"
    settings.codex_supervisor_configured_default_branch = "develop"
    result = load_configured_project()
    assert result.state == "ready"
    assert result.project is not None
    return result.project


def _hidden_claimed_values(index: int, repo_path: str) -> dict[str, object]:
    root_identity = root_identity_for_path(repo_path)
    assert root_identity is not None
    return {
        "id": f"hidden-volume-{index}",
        "name": f"Hidden {index}",
        "repo_path": repo_path,
        "default_branch": "develop",
        "public_id": f"prj_{index:016x}",
        "tenant_id": 100_000 + index,
        "owner_user_id": 200_000 + index,
        "scope_state": "claimed",
        "control_plane": "legacy",
        "configured_fingerprint": hashlib.sha256(
            f"hidden-volume-{index}".encode("ascii")
        ).hexdigest(),
        "root_identity_digest": root_identity[1],
        "claimed_at": datetime.now(timezone.utc),
        "version": 1,
    }


def test_readiness_resolution_and_claim_survive_restart(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=11, user_id=22)
    key = str(uuid.uuid4())
    fingerprint = canonical_fingerprint(
        actor=actor,
        project_id=configured.public_id,
        expected_version=0,
        confirmation=True,
    )
    try:
        readiness = inspect_infrastructure(engine)
        assert readiness.state == "ready"
        before = resolve_project_read_only(actor=actor, configured=configured, db_engine=engine)
        assert before.state == "claim_required"
        assert before.public_summary()["version"] == 0

        reservation = reserve(
            actor=actor,
            idempotency_key=key,
            fingerprint=fingerprint,
            db_engine=engine,
        )
        assert reservation.mode == "execute"
        result = claim_reserved_project(
            actor=actor,
            configured=configured,
            reservation=reservation,
            idempotency_key=key,
            expected_version=0,
            db_engine=engine,
        )
        assert result.mode == "success"
        assert result.response_status == 200
        assert configured.canonical_root.encode() not in result.response_body

        engine.dispose()
        engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
        after = resolve_project_read_only(actor=actor, configured=configured, db_engine=engine)
        assert after.state == "claimed"
        with engine.connect() as connection:
            project = connection.execute(select(Project.__table__)).one()._mapping
            assert project["tenant_id"] == actor.tenant_id
            assert project["owner_user_id"] == actor.user_id
            assert project["control_plane"] == "legacy"
            assert project["version"] == 1
            assert connection.execute(select(func.count()).select_from(SupervisorEvent.__table__)).scalar_one() == 1
            record = connection.execute(select(IdempotencyRecord.__table__)).one()._mapping
            assert record["status"] == "succeeded"
            assert record["expires_at"] is not None
    finally:
        engine.dispose()


def test_exact_root_legacy_row_is_adopted_without_exposing_internal_identity(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=2, user_id=3)
    try:
        with engine.begin() as connection:
            connection.execute(Project.__table__.insert().values(
                id="legacy_internal_id",
                name="Old name",
                repo_path=configured.canonical_root,
                root_identity_digest=configured.root_identity_digest,
                default_branch="old",
                scope_state="unclaimed",
                control_plane="legacy",
                version=0,
            ))
        resolution = resolve_project_read_only(actor=actor, configured=configured, db_engine=engine)
        assert resolution.state == "claim_required"
        assert resolution.row_id == "legacy_internal_id"
        summary = resolution.public_summary()
        assert summary["project_id"] == configured.public_id
        assert "repo_path" not in summary
        assert "id" not in summary
    finally:
        engine.dispose()


def test_cross_scope_configured_row_is_hidden_as_absence(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=4, user_id=5)
    try:
        with engine.begin() as connection:
            connection.execute(Project.__table__.insert().values(
                id="hidden",
                name=configured.display_name,
                repo_path=configured.canonical_root,
                default_branch=configured.default_branch,
                public_id=configured.public_id,
                tenant_id=999,
                owner_user_id=999,
                scope_state="claimed",
                control_plane="legacy",
                configured_fingerprint=configured.fingerprint,
                root_identity_digest=configured.root_identity_digest,
                claimed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                version=1,
            ))
        resolution = resolve_project_read_only(actor=actor, configured=configured, db_engine=engine)
        assert resolution.state == "hidden"
        assert resolution.reason_codes == ()
        assert resolution.row_id is None
        assert resolution.public_resolution() == {"state": "claim_required", "reason_codes": []}
        public_summary = resolution.public_summary()
        assert public_summary is not None
        assert public_summary == {
            "project_id": configured.public_id,
            "display_name": configured.display_name,
            "default_branch": configured.default_branch,
            "state": "claim_required",
            "version": 0,
            "control_plane": "legacy",
            "claim_action": public_summary["claim_action"],
        }
        assert public_summary["claim_action"] is not None
    finally:
        engine.dispose()


@pytest.mark.parametrize("scope_state", ["claimed", "quarantined"])
def test_same_scope_protected_exact_root_is_quarantined(
    tmp_path: Path, scope_state: str
):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=44, user_id=55)
    values = {
        "id": f"same-root-{scope_state}",
        "name": "Conflicting",
        "repo_path": configured.canonical_root,
        "default_branch": "other",
        "tenant_id": actor.tenant_id,
        "owner_user_id": actor.user_id,
        "scope_state": scope_state,
        "control_plane": "legacy",
        "root_identity_digest": configured.root_identity_digest,
        "version": 0,
    }
    if scope_state == "claimed":
        values.update(
            public_id="prj_aaaaaaaaaaaaaaaa",
            configured_fingerprint="b" * 64,
            claimed_at=datetime.now(timezone.utc),
            version=1,
        )
    try:
        with engine.begin() as connection:
            connection.execute(Project.__table__.insert().values(**values))
        resolution = resolve_project_read_only(actor=actor, configured=configured, db_engine=engine)
        assert resolution.state == "quarantined"
        assert resolution.reason_codes == ("same_scope_identity_conflict",)
        with engine.connect() as connection:
            row = connection.execute(select(Project.__table__)).one()._mapping
            assert row["scope_state"] == scope_state
            assert row["name"] == "Conflicting"
    finally:
        engine.dispose()


def test_cross_scope_exact_root_with_different_ids_is_hidden(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=66, user_id=77)
    try:
        with engine.begin() as connection:
            connection.execute(Project.__table__.insert().values(
                id="hidden-alias",
                name="Other scope",
                repo_path=configured.canonical_root,
                default_branch="other",
                public_id="prj_bbbbbbbbbbbbbbbb",
                tenant_id=999,
                owner_user_id=999,
                scope_state="claimed",
                control_plane="legacy",
                configured_fingerprint="c" * 64,
                root_identity_digest=configured.root_identity_digest,
                claimed_at=datetime.now(timezone.utc),
                version=1,
            ))
        resolution = resolve_project_read_only(actor=actor, configured=configured, db_engine=engine)
        assert resolution.state == "hidden"
        assert resolution.reason_codes == ()
        assert resolution.public_summary()["state"] == "claim_required"
        assert resolution.public_summary()["version"] == 0
        assert resolution.public_summary()["claim_action"] is not None
    finally:
        engine.dispose()


def test_samefile_alias_is_not_treated_as_a_second_repository(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=88, user_id=99)
    alias = tmp_path / "repository-alias"
    try:
        alias.symlink_to(Path(configured.canonical_root), target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink unavailable on this host")
    try:
        with engine.begin() as connection:
            connection.execute(Project.__table__.insert().values(
                id="legacy-alias",
                name="Legacy",
                repo_path=str(alias),
                root_identity_digest=configured.root_identity_digest,
                default_branch="legacy",
                scope_state="unclaimed",
                control_plane="legacy",
                version=0,
            ))
        resolution = resolve_project_read_only(actor=actor, configured=configured, db_engine=engine)
        assert resolution.state == "claim_required"
        assert resolution.row_id == "legacy-alias"
    finally:
        engine.dispose()


def test_identity_bound_same_scope_legacy_root_rows_are_quarantined_not_unavailable(
    tmp_path: Path,
):
    """A non-unique physical-root digest is an ownership ambiguity, not an outage."""
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=101, user_id=102)
    try:
        with engine.begin() as connection:
            connection.execute(
                Project.__table__.insert(),
                [
                    {
                        "id": f"legacy-same-root-{index}",
                        "name": f"Legacy {index}",
                        "repo_path": configured.canonical_root,
                        "default_branch": "legacy",
                        "root_identity_digest": configured.root_identity_digest,
                        "scope_state": "unclaimed",
                        "control_plane": "legacy",
                        "version": 0,
                    }
                    for index in range(513)
                ],
            )

        project_selects: list[str] = []

        def capture_project_selects(
            _connection, _cursor, statement, _parameters, _context, _executemany
        ):
            normalized = " ".join(statement.lower().split())
            if normalized.startswith("select") and " from projects " in normalized:
                project_selects.append(normalized)

        event.listen(engine, "before_cursor_execute", capture_project_selects)
        try:
            resolution = resolve_project_read_only(
                actor=actor, configured=configured, db_engine=engine
            )
        finally:
            event.remove(engine, "before_cursor_execute", capture_project_selects)
        assert resolution.state == "quarantined"
        assert resolution.reason_codes == ("same_scope_candidate_ambiguous",)
        assert resolution.public_summary() is None
        assert len(project_selects) == 1
        assert " limit " in project_selects[0]
    finally:
        engine.dispose()


def test_more_than_identity_bound_hidden_unrelated_rows_do_not_change_visible_resolution(
    tmp_path: Path,
):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=501, user_id=502)
    unrelated_root = tmp_path / "unrelated-root"
    unrelated_root.mkdir()
    try:
        baseline = resolve_project_read_only(
            actor=actor, configured=configured, db_engine=engine
        )
        assert baseline.state == "claim_required"
        assert baseline.reason_codes == ()

        with engine.begin() as connection:
            connection.execute(
                Project.__table__.insert(),
                [
                    _hidden_claimed_values(
                        index,
                        str(unrelated_root),
                    )
                    for index in range(10_001)
                ],
            )

        project_selects: list[str] = []

        def capture_project_selects(
            _connection, _cursor, statement, _parameters, _context, _executemany
        ):
            normalized = " ".join(statement.lower().split())
            if normalized.startswith("select") and " from projects " in normalized:
                project_selects.append(normalized)

        event.listen(engine, "before_cursor_execute", capture_project_selects)
        try:
            after = resolve_project_read_only(
                actor=actor, configured=configured, db_engine=engine
            )
        finally:
            event.remove(engine, "before_cursor_execute", capture_project_selects)
        assert after.state == baseline.state
        assert after.reason_codes == baseline.reason_codes
        assert after.public_resolution() == baseline.public_resolution()
        assert after.public_summary() == baseline.public_summary()
        assert len(project_selects) == 2
        assert all("root_identity_digest" in statement for statement in project_selects)
        assert all(" limit " in statement for statement in project_selects)
    finally:
        engine.dispose()


@pytest.mark.parametrize("use_alias", [False, True], ids=["canonical", "symlink-alias"])
def test_hidden_conflicting_root_is_found_after_unrelated_hidden_volume(
    tmp_path: Path, use_alias: bool
):
    engine = migrated_engine(tmp_path)
    configured = configured_project(tmp_path)
    actor = ActorScope(tenant_id=503, user_id=504)
    unrelated_root = tmp_path / "unrelated-root"
    unrelated_root.mkdir()
    conflict_path = configured.canonical_root
    if use_alias:
        alias = tmp_path / "hidden-root-alias"
        try:
            alias.symlink_to(Path(configured.canonical_root), target_is_directory=True)
        except OSError:
            engine.dispose()
            pytest.skip("directory symlink unavailable on this host")
        conflict_path = str(alias)

    unrelated = [
        _hidden_claimed_values(
            index,
            str(unrelated_root),
        )
        for index in range(10_001)
    ]
    conflict = _hidden_claimed_values(10_001, conflict_path)
    conflict["id"] = "zz-hidden-conflict"
    # Deliberately use an unrelated configured fingerprint so the indexed
    # physical-root digest, followed by same-file verification, proves alias
    # containment beyond the unrelated hidden-row volume.
    conflict["configured_fingerprint"] = "f" * 64
    conflict["root_identity_digest"] = configured.root_identity_digest
    try:
        with engine.begin() as connection:
            connection.execute(Project.__table__.insert(), [*unrelated, conflict])

        resolution = resolve_project_read_only(
            actor=actor, configured=configured, db_engine=engine
        )
        assert resolution.state == "hidden"
        assert resolution.reason_codes == ()
        assert resolution.row_id is None
        assert resolution.public_resolution() == {
            "state": "claim_required",
            "reason_codes": [],
        }
        assert resolution.public_summary()["state"] == "claim_required"
        assert resolution.public_summary()["version"] == 0
        assert resolution.public_summary()["claim_action"] is not None
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "branch",
    ["-topic", "@", "feature/.hidden", "foo.lock/bar", "trailing.", "a..b"],
)
def test_configured_branch_uses_git_check_ref_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, branch: str
):
    repository = tmp_path / "branch-repository"
    repository.mkdir()
    monkeypatch.setattr(settings, "codex_supervisor_configured_project_id", "prj_1234567890abcdef")
    monkeypatch.setattr(settings, "codex_supervisor_configured_project_root", str(repository))
    monkeypatch.setattr(settings, "codex_supervisor_configured_project_name", "FastAPI Bookings")
    monkeypatch.setattr(settings, "codex_supervisor_configured_default_branch", branch)
    assert load_configured_project().state == "quarantined"


def test_configured_branch_accepts_git_valid_nested_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repository = tmp_path / "valid-branch-repository"
    repository.mkdir()
    monkeypatch.setattr(settings, "codex_supervisor_configured_project_id", "prj_1234567890abcdef")
    monkeypatch.setattr(settings, "codex_supervisor_configured_project_root", str(repository))
    monkeypatch.setattr(settings, "codex_supervisor_configured_project_name", "FastAPI Bookings")
    monkeypatch.setattr(settings, "codex_supervisor_configured_default_branch", "feature/ops.v2")
    assert load_configured_project().state == "ready"


@pytest.mark.parametrize(
    "tamper_sql",
    [
        "ALTER TABLE projects ADD COLUMN unexpected TEXT",
        "DROP TABLE items",
        "DROP INDEX ix_projects_supervisor_scope|||CREATE INDEX ix_projects_supervisor_scope ON projects (scope_state)",
        "DROP TRIGGER trg_supervisor_events_no_update|||CREATE TRIGGER trg_supervisor_events_no_update BEFORE UPDATE ON supervisor_events BEGIN SELECT 1; END",
        "UPDATE schema_adoption_metadata SET structural_version='wrong' WHERE asset_key='system_settings'",
        "DROP TRIGGER trg_cutover_state_no_delete|||DELETE FROM control_plane_cutover_state",
    ],
)
def test_readiness_rejects_exact_schema_or_fixed_state_tampering(
    tmp_path: Path, tamper_sql: str
):
    engine = migrated_engine(tmp_path)
    try:
        with engine.begin() as connection:
            for statement in tamper_sql.split("|||"):
                connection.exec_driver_sql(statement)
        readiness = inspect_infrastructure(engine)
        assert readiness.state == "migration_required"
        assert readiness.current_revision == "003"
        assert readiness.reason_codes == ("schema_mismatch",)
    finally:
        engine.dispose()


def test_infrastructure_distinguishes_unversioned_behind_and_corrupt(tmp_path: Path):
    unversioned_url = f"sqlite:///{(tmp_path / 'unversioned.db').as_posix()}"
    unversioned = create_engine(unversioned_url)
    try:
        assert inspect_infrastructure(unversioned).state == "migration_required"
        assert inspect_infrastructure(unversioned).reason_codes == ("revision_missing",)
    finally:
        unversioned.dispose()

    behind_url = f"sqlite:///{(tmp_path / 'behind.db').as_posix()}"
    _run_alembic(behind_url, "001")
    behind = create_engine(behind_url)
    try:
        readiness = inspect_infrastructure(behind)
        assert readiness.state == "migration_required"
        assert readiness.current_revision == "001"
        assert readiness.reason_codes == ("revision_behind",)
    finally:
        behind.dispose()

    corrupt_path = tmp_path / "corrupt.db"
    corrupt_path.write_bytes(b"not-a-sqlite-database")
    corrupt = create_engine(f"sqlite:///{corrupt_path.as_posix()}")
    try:
        assert inspect_infrastructure(corrupt).state == "dependency_unavailable"
    finally:
        corrupt.dispose()


def test_infrastructure_reports_bounded_dependency_failure_when_database_locked(tmp_path: Path):
    engine = migrated_engine(tmp_path)
    try:
        with engine.connect() as blocker:
            blocker.exec_driver_sql("PRAGMA locking_mode=EXCLUSIVE")
            blocker.exec_driver_sql("BEGIN EXCLUSIVE")
            readiness = inspect_infrastructure(engine)
            blocker.rollback()
        assert readiness.state == "dependency_unavailable"
    finally:
        engine.dispose()


def test_configured_project_rejects_ambiguous_or_missing_root(
    tmp_path: Path,
    monkeypatch,
):
    repository = tmp_path / "repository"
    repository.mkdir()
    monkeypatch.setattr(settings, "codex_supervisor_configured_project_id", "prj_1234567890abcdef")
    monkeypatch.setattr(settings, "codex_supervisor_configured_project_name", "FastAPI Bookings")
    monkeypatch.setattr(settings, "codex_supervisor_configured_default_branch", "develop")

    missing = tmp_path / "missing"
    monkeypatch.setattr(settings, "codex_supervisor_configured_project_root", str(missing))
    unavailable = load_configured_project()
    assert unavailable.state == "dependency_unavailable"
    assert unavailable.project is None

    symlink = tmp_path / "linked"
    try:
        symlink.symlink_to(repository, target_is_directory=True)
    except OSError:
        return
    monkeypatch.setattr(settings, "codex_supervisor_configured_project_root", str(symlink))
    ambiguous = load_configured_project()
    assert ambiguous.state == "quarantined"
    assert ambiguous.reason_codes == ("root_identity_ambiguous",)
