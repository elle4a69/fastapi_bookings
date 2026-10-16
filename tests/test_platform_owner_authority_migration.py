"""Alembic evidence for the persisted platform-owner capability."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text


REPO_ROOT = Path(__file__).resolve().parents[1]
PARENT_REVISION = "10251fbf7103"
HEAD_REVISION = "d4b8f2a6c901"


def _database_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _run_alembic(path: Path, *args: str) -> None:
    child_env = dict(os.environ)
    child_env["DATABASE_URL"] = _database_url(path)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=child_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, "isolated Alembic command failed"


def _create_parent_revision_database(path: Path) -> None:
    """Create only the pre-migration contract using SQL, never ORM metadata."""
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE tenants (
                id INTEGER PRIMARY KEY,
                name VARCHAR NOT NULL UNIQUE,
                subdomain VARCHAR NOT NULL UNIQUE
            );
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                login VARCHAR NOT NULL,
                password_hash VARCHAR NOT NULL,
                role VARCHAR NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1
            );
            CREATE TABLE alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            );
            INSERT INTO alembic_version(version_num) VALUES ('10251fbf7103');
            INSERT INTO tenants(id, name, subdomain) VALUES (1, 'Synthetic Migration', 'migration-synthetic');
            INSERT INTO users(id, tenant_id, login, password_hash, role, is_active) VALUES
                (11, 1, 'owner-synthetic', 'unused', 'owner', 1),
                (12, 1, 'admin-synthetic', 'unused', 'admin', 1),
                (13, 1, 'manager-synthetic', 'unused', 'manager', 1);
            """
        )


def test_fresh_empty_database_upgrade_head_is_bootstrap_parity_only(tmp_path):
    database = tmp_path / "fresh.db"
    _run_alembic(database, "upgrade", "head")
    engine = create_engine(_database_url(database))
    inspector = inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("users")}
    assert columns["is_platform_owner"]["nullable"] is False
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD_REVISION
    engine.dispose()


def test_populated_parent_upgrade_backfills_false_and_retains_default_and_index(tmp_path):
    database = tmp_path / "populated.db"
    _create_parent_revision_database(database)
    _run_alembic(database, "upgrade", "head")
    engine = create_engine(_database_url(database))
    inspector = inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("users")}
    capability = columns["is_platform_owner"]
    assert capability["nullable"] is False
    assert str(capability["default"]).strip("()'").lower() in {"0", "false"}
    indexes = {index["name"]: index for index in inspector.get_indexes("users")}
    assert indexes["ix_users_platform_owner_active"]["column_names"] == [
        "is_platform_owner",
        "is_active",
    ]
    with engine.begin() as connection:
        assert connection.execute(text("SELECT is_platform_owner FROM users ORDER BY id")).scalars().all() == [False, False, False]
        connection.execute(
            text(
                "INSERT INTO users(id, tenant_id, login, password_hash, role, is_active) "
                "VALUES (14, 1, 'raw-synthetic', 'unused', 'owner', 1)"
            )
        )
        assert connection.execute(text("SELECT is_platform_owner FROM users WHERE id=14")).scalar_one() in (0, False)
    engine.dispose()


def test_downgrade_and_reupgrade_preserve_user_data_except_capability(tmp_path):
    database = tmp_path / "roundtrip.db"
    _create_parent_revision_database(database)
    _run_alembic(database, "upgrade", "head")
    engine = create_engine(_database_url(database))
    with engine.begin() as connection:
        connection.execute(text("UPDATE users SET is_platform_owner=1 WHERE id=11"))
    engine.dispose()

    _run_alembic(database, "downgrade", PARENT_REVISION)
    engine = create_engine(_database_url(database))
    assert "is_platform_owner" not in {column["name"] for column in inspect(engine).get_columns("users")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id, role FROM users ORDER BY id")).all() == [
            (11, "owner"),
            (12, "admin"),
            (13, "manager"),
        ]
    engine.dispose()

    _run_alembic(database, "upgrade", "head")
    engine = create_engine(_database_url(database))
    with engine.connect() as connection:
        assert connection.execute(text("SELECT is_platform_owner FROM users ORDER BY id")).scalars().all() == [False, False, False]
    engine.dispose()


def test_revision_linkage_and_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config(str(REPO_ROOT / "alembic.ini")))
    heads = script.get_heads()
    assert heads == [HEAD_REVISION]
    revision = script.get_revision(HEAD_REVISION)
    assert revision.down_revision == PARENT_REVISION
