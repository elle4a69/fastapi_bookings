"""Configured-root identity and offline legacy-ledger adoption."""

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from backend.config import settings


PROJECT_ID_RE = re.compile(r"^prj_[A-Za-z0-9_-]{16,64}$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ConfiguredProject:
    public_id: str
    canonical_root: str
    root_identity_digest: str
    display_name: str
    default_branch: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ConfigurationResult:
    state: str
    reason_codes: tuple[str, ...]
    project: ConfiguredProject | None = None


def _valid_branch(value: str) -> bool:
    # ``git check-ref-format --branch`` intentionally accepts the shorthand
    # ``@`` even though it is not an unambiguous configured branch name for
    # the control-plane contract.
    if value == "@" or not (1 <= len(value) <= 255) or CONTROL_RE.search(value):
        return False
    try:
        result = subprocess.run(
            ["git", "check-ref-format", "--branch", value],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _has_reparse_marker(path: Path) -> bool:
    try:
        # lstat inspects the directory entry itself; stat would follow a link
        # and hide the reparse marker we need to reject for configured roots.
        attrs = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except OSError:
        return True


def root_identity_for_path(raw_path: str | Path) -> tuple[str, str] | None:
    """Return a canonical path and stable, non-public physical-root digest."""
    try:
        path = Path(raw_path)
        if not path.is_absolute():
            return None
        resolved = path.resolve(strict=True)
        if not resolved.is_dir():
            return None
        identity = resolved.stat()
        device = int(identity.st_dev)
        inode = int(identity.st_ino)
        if device <= 0 or inode <= 0:
            return None
        canonical_root = os.path.normcase(os.path.normpath(str(resolved)))
        material = {
            "canonical_root": canonical_root,
            "device": device,
            "inode": inode,
            "version": 1,
        }
        encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return canonical_root, hashlib.sha256(encoded).hexdigest()
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def load_configured_project() -> ConfigurationResult:
    values = (
        settings.codex_supervisor_configured_project_id,
        settings.codex_supervisor_configured_project_root,
        settings.codex_supervisor_configured_project_name,
        settings.codex_supervisor_configured_default_branch,
    )
    if any(value is None or not str(value).strip() for value in values):
        return ConfigurationResult("unconfigured", ("configured_value_missing",))

    public_id, raw_root, display_name, branch = (str(value).strip() for value in values)
    invalid = (
        PROJECT_ID_RE.fullmatch(public_id) is None
        or not (1 <= len(display_name) <= 120)
        or CONTROL_RE.search(display_name) is not None
        or not display_name.isprintable()
        or not _valid_branch(branch)
    )
    root = Path(raw_root)
    if invalid or not root.is_absolute():
        return ConfigurationResult("quarantined", ("configured_value_invalid",))
    try:
        if not root.exists():
            return ConfigurationResult(
                "dependency_unavailable", ("configured_root_unavailable",)
            )
        if root.is_symlink() or _has_reparse_marker(root):
            return ConfigurationResult("quarantined", ("root_identity_ambiguous",))
        resolved = root.resolve(strict=True)
        # Prove that resolution did not redirect to another filesystem object.
        if not os.path.samefile(root, resolved):
            return ConfigurationResult("quarantined", ("root_identity_ambiguous",))
    except (OSError, RuntimeError):
        return ConfigurationResult("dependency_unavailable", ("configured_root_unavailable",))

    root_identity = root_identity_for_path(resolved)
    if root_identity is None:
        return ConfigurationResult(
            "dependency_unavailable", ("configured_root_unavailable",)
        )
    canonical_root, root_identity_digest = root_identity
    material = {
        "default_branch": branch,
        "display_name": display_name,
        "project_id": public_id,
        "root_identity_digest": root_identity_digest,
        "schema_version": "0.1",
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    configured = ConfiguredProject(
        public_id=public_id,
        canonical_root=canonical_root,
        root_identity_digest=root_identity_digest,
        display_name=display_name,
        default_branch=branch,
        fingerprint=hashlib.sha256(encoded).hexdigest(),
    )
    return ConfigurationResult("ready", (), configured)


def paths_are_same(stored_path: str, configured: ConfiguredProject) -> bool | None:
    try:
        stored_identity = root_identity_for_path(stored_path)
        if stored_identity is None:
            return None
        normalized, root_identity_digest = stored_identity
        resolved = Path(stored_path).resolve(strict=True)
        configured_root = Path(configured.canonical_root)
        same_file = os.path.samefile(resolved, configured_root)
        # Canonical comparison catches normal Windows case/separator variants;
        # samefile catches symlink, junction and reparse aliases so they cannot
        # be treated as a second repository identity.
        return (
            same_file
            and normalized == configured.canonical_root
            and root_identity_digest == configured.root_identity_digest
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def _columns(*items: tuple[str, str, bool, int]) -> list[tuple[str, str, bool, object, int]]:
    return [(name, type_name, nullable, None, primary_key) for name, type_name, nullable, primary_key in items]


_LEGACY_EXPECTED: dict[str, dict[str, object]] = {
    "projects": {
        "columns": _columns(
            ("id", "VARCHAR", False, 1), ("name", "VARCHAR", False, 0),
            ("repo_path", "VARCHAR", False, 0), ("default_branch", "VARCHAR", False, 0),
            ("created_at", "DATETIME", True, 0), ("updated_at", "DATETIME", True, 0),
        ),
    },
    "threads": {
        "columns": _columns(
            ("id", "VARCHAR", False, 1), ("project_id", "VARCHAR", False, 0),
            ("title", "VARCHAR", False, 0), ("created_at", "DATETIME", True, 0),
            ("status", "VARCHAR", False, 0), ("is_pinned", "BOOLEAN", False, 0),
            ("is_archived", "BOOLEAN", False, 0),
        ),
        "foreign_keys": [(('project_id',), "projects", ('id',), "CASCADE")],
    },
    "subagents": {
        "columns": _columns(
            ("id", "VARCHAR", False, 1), ("thread_id", "VARCHAR", False, 0),
            ("parent_thread_id", "VARCHAR", True, 0), ("name", "VARCHAR", False, 0),
            ("role", "VARCHAR", False, 0), ("status", "VARCHAR", False, 0),
            ("progress", "INTEGER", False, 0), ("current_action", "TEXT", True, 0),
            ("created_at", "DATETIME", True, 0),
        ),
        "foreign_keys": [(('thread_id',), "threads", ('id',), "CASCADE")],
    },
    "tool_approvals": {
        "columns": _columns(
            ("id", "VARCHAR", False, 1), ("thread_id", "VARCHAR", False, 0),
            ("tool_call_id", "VARCHAR", False, 0), ("command", "TEXT", False, 0),
            ("risk_level", "VARCHAR", False, 0), ("consequence", "TEXT", False, 0),
            ("status", "VARCHAR", False, 0), ("created_at", "DATETIME", True, 0),
            ("resolved_at", "DATETIME", True, 0),
        ),
        "foreign_keys": [(('thread_id',), "threads", ('id',), "CASCADE")],
    },
    "turns": {
        "columns": _columns(
            ("id", "INTEGER", False, 1), ("thread_id", "VARCHAR", False, 0),
            ("turn_number", "INTEGER", False, 0), ("status", "VARCHAR", False, 0),
            ("created_at", "DATETIME", True, 0), ("completed_at", "DATETIME", True, 0),
            ("prompt", "TEXT", True, 0),
        ),
        "foreign_keys": [(('thread_id',), "threads", ('id',), "CASCADE")],
        "unique": [("thread_id", "turn_number")],
    },
    "items": {
        "columns": _columns(
            ("id", "VARCHAR", False, 1), ("turn_id", "INTEGER", False, 0),
            ("item_type", "VARCHAR", False, 0), ("content", "JSON", False, 0),
            ("sequence", "INTEGER", False, 0), ("created_at", "DATETIME", True, 0),
        ),
        "foreign_keys": [(('turn_id',), "turns", ('id',), "CASCADE")],
    },
    "workspace_boundaries": {
        "columns": _columns(
            ("id", "VARCHAR", False, 1), ("path", "VARCHAR", False, 0),
            ("name", "VARCHAR", True, 0), ("is_default", "BOOLEAN", False, 0),
            ("created_at", "DATETIME", True, 0),
        ),
        "unique": [("path",)],
    },
    "system_settings": {
        "columns": _columns(
            ("key", "VARCHAR", False, 1), ("value", "TEXT", False, 0),
            ("updated_at", "DATETIME", True, 0),
        ),
    },
}


def _structure_manifest(connection, inspector, table_name: str) -> dict[str, object]:
    columns = [
        (
            column["name"],
            type(column["type"]).__name__.upper(),
            bool(column["nullable"]),
            column.get("default"),
            int(column.get("primary_key") or 0),
        )
        for column in inspector.get_columns(table_name)
    ]
    foreign_keys = sorted(
        (
            tuple(foreign_key.get("constrained_columns") or ()),
            str(foreign_key.get("referred_table") or ""),
            tuple(foreign_key.get("referred_columns") or ()),
            str((foreign_key.get("options") or {}).get("ondelete") or "").upper(),
        )
        for foreign_key in inspector.get_foreign_keys(table_name)
    )
    unique = {
        tuple(constraint.get("column_names") or ())
        for constraint in inspector.get_unique_constraints(table_name)
    }
    indexes = []
    for index in inspector.get_indexes(table_name):
        columns_for_index = tuple(index.get("column_names") or ())
        if index.get("unique"):
            unique.add(columns_for_index)
        else:
            indexes.append(columns_for_index)
    checks = sorted(
        " ".join(str(constraint.get("sqltext") or "").split())
        for constraint in inspector.get_check_constraints(table_name)
    )
    triggers = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=? ORDER BY name",
        (table_name,),
    ).scalars().all()
    return {
        "columns": columns,
        "foreign_keys": foreign_keys,
        "unique": sorted(unique),
        "indexes": sorted(indexes),
        "checks": checks,
        "triggers": list(triggers),
    }


def _expected_manifest(table_name: str) -> dict[str, object]:
    expected = _LEGACY_EXPECTED[table_name]
    return {
        "columns": expected["columns"],
        "foreign_keys": expected.get("foreign_keys", []),
        "unique": expected.get("unique", []),
        "indexes": [],
        "checks": [],
        "triggers": [],
    }


def _validate_legacy_connection(connection) -> tuple[bool, str, str]:
    if connection.dialect.name != "sqlite":
        return False, "unsupported_database_dialect", ""
    integrity = connection.exec_driver_sql("PRAGMA integrity_check").scalar_one()
    foreign_key_errors = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
    if integrity != "ok" or foreign_key_errors:
        return False, "legacy_database_integrity_failed", ""
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if tables != set(_LEGACY_EXPECTED):
        return False, "legacy_table_set_mismatch", ""
    if inspector.get_view_names():
        return False, "legacy_structure_mismatch", ""
    shapes: dict[str, dict[str, object]] = {}
    for table_name in sorted(_LEGACY_EXPECTED):
        actual = _structure_manifest(connection, inspector, table_name)
        if actual != _expected_manifest(table_name):
            return False, "legacy_structure_mismatch", ""
        shapes[table_name] = actual
    digest = hashlib.sha256(
        json.dumps(shapes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return True, "legacy_structure_valid", digest


def validate_legacy_schema(database_url: str) -> tuple[bool, str, str]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return _validate_legacy_connection(connection)
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate/adopt an unversioned CCC database")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)
    database_url = os.environ.get("database_url") or os.environ.get("DATABASE_URL")
    if not database_url:
        print("result=database_url_missing")
        return 2
    valid, code, digest = validate_legacy_schema(database_url)
    print(f"result={code}")
    if not valid:
        return 3
    if not args.apply:
        print("mode=dry_run")
        return 0
    if args.confirm != "ADOPT-LEGACY-CCC-SCHEMA":
        print("result=confirmation_required")
        return 4

    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA busy_timeout=5000")
            connection.commit()
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            still_valid, locked_code, locked_digest = _validate_legacy_connection(connection)
            if not still_valid or locked_digest != digest:
                connection.rollback()
                print(f"result={locked_code}")
                return 5
            migration_context = MigrationContext.configure(connection)
            script = ScriptDirectory.from_config(config)
            migration_context.stamp(script, "001")
            connection.commit()
    finally:
        engine.dispose()
    # Adoption owns only the exact, locked legacy-to-001 stamp.  Subsequent
    # revisions remain an explicit Alembic operation, avoiding a second
    # connection/race that could make a failed adoption appear partially done.
    print("result=adopted_revision_001")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
