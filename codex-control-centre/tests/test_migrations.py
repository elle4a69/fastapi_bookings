"""Real, isolated CCC migration ledger coverage."""

from pathlib import Path
import os
import subprocess
import sys

CCC_ROOT = Path(__file__).resolve().parents[1]
if str(CCC_ROOT) not in sys.path:
    sys.path.insert(0, str(CCC_ROOT))

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from backend.services.legacy_adoption_service import (
    root_identity_for_path,
    validate_legacy_schema,
)
from backend.services.migration_readiness_service import inspect_infrastructure


ALEMBIC_INI = CCC_ROOT / "alembic.ini"


def _child_environment(url: str) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.lower() != "database_url"
    }
    # Set the authoritative URL before the child imports backend.settings.
    environment["database_url"] = url
    return environment


def _run_alembic(
    url: str,
    *arguments: str,
    evidence_loss: bool = False,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI)]
    if evidence_loss:
        command.extend(["-x", "ccc_ack_claim_evidence_loss=yes"])
    command.extend(arguments)
    result = subprocess.run(
        command,
        cwd=CCC_ROOT,
        env=_child_environment(url),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        timeout=60,
    )
    if expect_success:
        assert result.returncode == 0, result.stdout
    else:
        assert result.returncode != 0, result.stdout
    return result


def _run_adoption(url: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.services.legacy_adoption_service",
            *arguments,
        ],
        cwd=CCC_ROOT,
        env=_child_environment(url),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        timeout=60,
    )


def _url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _revision(engine) -> str | None:
    with engine.connect() as connection:
        if "alembic_version" not in inspect(connection).get_table_names():
            return None
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def test_fresh_child_migration_url_precedes_ambient_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    target_path = tmp_path / "explicit-target.db"
    decoy_path = tmp_path / "ambient-decoy.db"
    monkeypatch.setenv("DATABASE_URL", _url(decoy_path))

    _run_alembic(_url(target_path), "upgrade", "head")

    target_engine = create_engine(_url(target_path))
    try:
        assert _revision(target_engine) == "003"
    finally:
        target_engine.dispose()
    assert not decoy_path.exists()


def test_empty_database_upgrades_and_guarded_roundtrip(tmp_path: Path):
    url = _url(tmp_path / "empty.db")
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    try:
        assert _revision(engine) == "003"
        tables = set(inspect(engine).get_table_names())
        assert {
            "workspace_boundaries", "system_settings", "schema_adoption_metadata",
            "control_plane_cutover_state", "idempotency_records", "supervisor_events",
        }.issubset(tables)
        project_columns = {column["name"]: column for column in inspect(engine).get_columns("projects")}
        assert project_columns["root_identity_digest"]["nullable"] is False
        identity_indexes = [
            index
            for index in inspect(engine).get_indexes("projects")
            if index["name"] == "ix_projects_root_identity_digest"
        ]
        assert identity_indexes == [
            {
                "name": "ix_projects_root_identity_digest",
                "column_names": ["root_identity_digest"],
                "unique": 0,
                "dialect_options": {},
            }
        ]
        result = _run_alembic(url, "downgrade", "002", expect_success=False)
        assert "claim_evidence_loss_acknowledgement_required" in result.stdout
        _run_alembic(url, "downgrade", "001", evidence_loss=True)
        assert _revision(engine) == "001"
        _run_alembic(url, "upgrade", "head")
        assert _revision(engine) == "003"
    finally:
        engine.dispose()


def test_real_001_database_preserves_legacy_rows(tmp_path: Path):
    url = _url(tmp_path / "legacy-001.db")
    _run_alembic(url, "upgrade", "001")
    legacy_root = tmp_path / "legacy-root"
    legacy_root.mkdir()
    expected_identity = root_identity_for_path(legacy_root)
    assert expected_identity is not None
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO projects (id, name, repo_path, default_branch) "
                "VALUES ('legacy', 'Legacy', :repo_path, 'develop')"
            ), {"repo_path": str(legacy_root)})
        _run_alembic(url, "upgrade", "head")
        with engine.connect() as connection:
            row = connection.execute(text(
                "SELECT name, scope_state, control_plane, version, root_identity_digest "
                "FROM projects WHERE id='legacy'"
            )).one()
        assert tuple(row) == (
            "Legacy",
            "unclaimed",
            "legacy",
            0,
            expected_identity[1],
        )
    finally:
        engine.dispose()


def test_002_root_identity_backfill_fails_before_schema_mutation(tmp_path: Path):
    url = _url(tmp_path / "unprovable-root.db")
    _run_alembic(url, "upgrade", "001")
    missing_root = tmp_path / "missing-root"
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO projects (id, name, repo_path, default_branch) "
                    "VALUES ('legacy', 'Legacy', :repo_path, 'develop')"
                ),
                {"repo_path": str(missing_root)},
            )
        result = _run_alembic(url, "upgrade", "002", expect_success=False)
        assert "project_root_identity_unavailable" in result.stdout
        assert _revision(engine) == "001"
        assert [
            column["name"] for column in inspect(engine).get_columns("projects")
        ] == [
            "id",
            "name",
            "repo_path",
            "default_branch",
            "created_at",
            "updated_at",
        ]
        assert not {
            "workspace_boundaries",
            "system_settings",
            "schema_adoption_metadata",
        } & set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_readiness_requires_exact_root_identity_index(tmp_path: Path):
    url = _url(tmp_path / "identity-index.db")
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    try:
        assert inspect_infrastructure(engine).state == "ready"
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP INDEX ix_projects_root_identity_digest")
        readiness = inspect_infrastructure(engine)
        assert readiness.state == "migration_required"
        assert readiness.reason_codes == ("schema_mismatch",)
    finally:
        engine.dispose()


def test_claimed_project_blocks_002_to_001(tmp_path: Path):
    url = _url(tmp_path / "claimed.db")
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    try:
        root_identity = root_identity_for_path(tmp_path)
        assert root_identity is not None
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO projects "
                "(id,name,repo_path,default_branch,public_id,tenant_id,owner_user_id,"
                "scope_state,control_plane,configured_fingerprint,root_identity_digest,"
                "claimed_at,version) "
                "VALUES ('p','P',:repo_path,'dev','prj_1234567890abcdef',1,1,"
                "'claimed','legacy',:digest,:root_digest,CURRENT_TIMESTAMP,1)"
            ), {
                "repo_path": str(tmp_path),
                "digest": "a" * 64,
                "root_digest": root_identity[1],
            })
        with pytest.raises(IntegrityError, match="claimed_project_invariant"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE projects SET root_identity_digest=:digest WHERE id='p'"
                    ),
                    {"digest": "b" * 64},
                )
        result = _run_alembic(
            url, "downgrade", "001", evidence_loss=True, expect_success=False
        )
        assert "project_scope_downgrade_blocked" in result.stdout
    finally:
        engine.dispose()


def _create_unversioned_historical_database(url: str) -> None:
    _run_alembic(url, "upgrade", "001")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE workspace_boundaries (id VARCHAR NOT NULL PRIMARY KEY, "
                "path VARCHAR NOT NULL UNIQUE, name VARCHAR, is_default BOOLEAN NOT NULL, "
                "created_at DATETIME)"
            )
            connection.exec_driver_sql(
                "CREATE TABLE system_settings (key VARCHAR NOT NULL PRIMARY KEY, "
                "value TEXT NOT NULL, updated_at DATETIME)"
            )
            connection.exec_driver_sql("DROP TABLE alembic_version")
    finally:
        engine.dispose()


def test_unversioned_exact_legacy_schema_requires_explicit_adoption(tmp_path: Path):
    url = _url(tmp_path / "unversioned.db")
    _create_unversioned_historical_database(url)
    assert _run_adoption(url).returncode == 0
    engine = create_engine(url)
    try:
        assert _revision(engine) is None
    finally:
        engine.dispose()
    assert _run_adoption(url, "--apply", "--confirm", "STAMP-CCC-LEGACY-001").returncode == 4
    assert _run_adoption(
        url, "--apply", "--confirm", "ADOPT-LEGACY-CCC-SCHEMA"
    ).returncode == 0
    engine = create_engine(url)
    try:
        assert _revision(engine) == "001"
        _run_alembic(url, "upgrade", "head")
        assert _revision(engine) == "003"
        with engine.connect() as connection:
            origins = dict(connection.execute(text(
                "SELECT asset_key, origin FROM schema_adoption_metadata"
            )).all())
        assert origins == {"system_settings": "adopted", "workspace_boundaries": "adopted"}
    finally:
        engine.dispose()


def test_incompatible_unversioned_schema_is_not_stamped(tmp_path: Path):
    url = _url(tmp_path / "partial.db")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE projects (id VARCHAR PRIMARY KEY)")
    finally:
        engine.dispose()
    assert _run_adoption(
        url, "--apply", "--confirm", "ADOPT-LEGACY-CCC-SCHEMA"
    ).returncode == 3
    engine = create_engine(url)
    try:
        assert _revision(engine) is None
        assert set(inspect(engine).get_table_names()) == {"projects"}
    finally:
        engine.dispose()


@pytest.mark.parametrize("foreign_asset", ["view", "trigger"])
def test_legacy_adoption_rejects_unallowlisted_schema_objects(
    tmp_path: Path,
    foreign_asset: str,
):
    url = _url(tmp_path / f"foreign-{foreign_asset}.db")
    _create_unversioned_historical_database(url)
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            if foreign_asset == "view":
                connection.exec_driver_sql(
                    "CREATE VIEW unexpected_project_names AS SELECT name FROM projects"
                )
            else:
                connection.exec_driver_sql(
                    "CREATE TRIGGER unexpected_project_trigger AFTER UPDATE ON projects "
                    "BEGIN SELECT 1; END"
                )
        valid, code, digest = validate_legacy_schema(url)
        assert valid is False
        assert code == "legacy_structure_mismatch"
        assert digest == ""
        assert _revision(engine) is None
    finally:
        engine.dispose()


def test_legacy_adoption_rejects_column_type_mismatch(tmp_path: Path):
    url = _url(tmp_path / "wrong-type.db")
    _create_unversioned_historical_database(url)
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE system_settings")
            connection.exec_driver_sql(
                "CREATE TABLE system_settings (key VARCHAR NOT NULL PRIMARY KEY, "
                "value VARCHAR NOT NULL, updated_at DATETIME)"
            )
        valid, code, digest = validate_legacy_schema(url)
        assert valid is False
        assert code == "legacy_structure_mismatch"
        assert digest == ""
        assert _revision(engine) is None
    finally:
        engine.dispose()


def test_versioned_001_adopts_matching_ledger_tables_preserves_data_and_downgrade(tmp_path: Path):
    url = _url(tmp_path / "versioned-adopted.db")
    _run_alembic(url, "upgrade", "001")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE workspace_boundaries (id VARCHAR NOT NULL PRIMARY KEY, "
                "path VARCHAR NOT NULL UNIQUE, name VARCHAR, is_default BOOLEAN NOT NULL, "
                "created_at DATETIME)"
            )
            connection.exec_driver_sql(
                "CREATE TABLE system_settings (key VARCHAR NOT NULL PRIMARY KEY, "
                "value TEXT NOT NULL, updated_at DATETIME)"
            )
            connection.exec_driver_sql(
                "INSERT INTO workspace_boundaries (id,path,name,is_default) "
                "VALUES ('w1','C:/synthetic','Synthetic',1)"
            )
            connection.exec_driver_sql(
                "INSERT INTO system_settings (key,value) VALUES ('mode','synthetic')"
            )
        _run_alembic(url, "upgrade", "head")
        assert _revision(engine) == "003"
        with engine.connect() as connection:
            origins = dict(connection.execute(text(
                "SELECT asset_key, origin FROM schema_adoption_metadata"
            )).all())
            assert connection.execute(text("SELECT value FROM system_settings")).scalar_one() == "synthetic"
        assert origins == {"system_settings": "adopted", "workspace_boundaries": "adopted"}
        _run_alembic(url, "downgrade", "001", evidence_loss=True)
        assert _revision(engine) == "001"
        tables = set(inspect(engine).get_table_names())
        assert {"workspace_boundaries", "system_settings"}.issubset(tables)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT value FROM system_settings")).scalar_one() == "synthetic"
    finally:
        engine.dispose()


def test_versioned_001_rejects_mismatching_present_ledger_without_advancing(tmp_path: Path):
    url = _url(tmp_path / "versioned-mismatch.db")
    _run_alembic(url, "upgrade", "001")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE workspace_boundaries (id VARCHAR NOT NULL PRIMARY KEY, "
                "path VARCHAR NOT NULL UNIQUE, name VARCHAR, is_default BOOLEAN NOT NULL, "
                "created_at DATETIME)"
            )
            connection.exec_driver_sql(
                "CREATE TABLE system_settings (key VARCHAR NOT NULL PRIMARY KEY, "
                "value VARCHAR NOT NULL, updated_at DATETIME)"
            )
        result = _run_alembic(url, "upgrade", "head", expect_success=False)
        assert "incompatible_system_settings_schema" in result.stdout
        assert _revision(engine) == "001"
    finally:
        engine.dispose()


def test_quarantined_project_blocks_002_to_001(tmp_path: Path):
    url = _url(tmp_path / "quarantined.db")
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    try:
        root_identity = root_identity_for_path(tmp_path)
        assert root_identity is not None
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO projects (id,name,repo_path,default_branch,root_identity_digest,"
                "scope_state,control_plane,version) "
                "VALUES ('q','Q',:repo_path,'dev',:root_digest,'quarantined','legacy',0)"
            ), {"repo_path": str(tmp_path), "root_digest": root_identity[1]})
        result = _run_alembic(
            url, "downgrade", "001", evidence_loss=True, expect_success=False
        )
        assert "project_scope_downgrade_blocked" in result.stdout
    finally:
        engine.dispose()
