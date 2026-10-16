"""reconcile legacy ledger and add project supervisor scope

Revision ID: 002
Revises: 001
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, Sequence[str], None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_EXPECTED = {
    "workspace_boundaries": {
        "columns": [
            ("id", "VARCHAR", False, None, 1),
            ("path", "VARCHAR", False, None, 0),
            ("name", "VARCHAR", True, None, 0),
            ("is_default", "BOOLEAN", False, None, 0),
            ("created_at", "DATETIME", True, None, 0),
        ],
        "unique": [("path",)],
    },
    "system_settings": {
        "columns": [
            ("key", "VARCHAR", False, None, 1),
            ("value", "TEXT", False, None, 0),
            ("updated_at", "DATETIME", True, None, 0),
        ],
        "unique": [],
    },
}


def _root_identity_digest(raw_path: str) -> str | None:
    """Mirror the v6 runtime identity tuple without importing application code."""
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
        material = {
            "canonical_root": os.path.normcase(os.path.normpath(str(resolved))),
            "device": device,
            "inode": inode,
            "version": 1,
        }
        encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def _manifest(table_name: str) -> dict[str, object]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
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
    unique = {
        tuple(constraint.get("column_names") or ())
        for constraint in inspector.get_unique_constraints(table_name)
    }
    unique.update(
        tuple(index.get("column_names") or ())
        for index in inspector.get_indexes(table_name)
        if index.get("unique")
    )
    non_unique_indexes = sorted(
        tuple(index.get("column_names") or ())
        for index in inspector.get_indexes(table_name)
        if not index.get("unique")
    )
    foreign_keys = inspector.get_foreign_keys(table_name)
    checks = inspector.get_check_constraints(table_name)
    triggers = bind.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=? ORDER BY name",
        (table_name,),
    ).scalars().all()
    return {
        "columns": columns,
        "unique": sorted(unique),
        "indexes": non_unique_indexes,
        "foreign_keys": foreign_keys,
        "checks": checks,
        "triggers": list(triggers),
    }


def _assert_existing_shape(table_name: str) -> str:
    actual = _manifest(table_name)
    expected = {
        **_EXPECTED[table_name],
        "indexes": [],
        "foreign_keys": [],
        "checks": [],
        "triggers": [],
    }
    if actual != expected:
        raise RuntimeError(f"incompatible_{table_name}_schema")
    return hashlib.sha256(
        json.dumps(actual, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise RuntimeError("unsupported_ccc_database_dialect")

    # Prove every revision-001 row before executing any DDL.  A missing,
    # relative, inaccessible, zero-valued or otherwise inconclusive filesystem
    # identity aborts with the database still at revision 001.
    root_identity_backfill: list[tuple[str, str]] = []
    for project_id, repo_path in bind.execute(
        sa.text("SELECT id, repo_path FROM projects ORDER BY id")
    ).all():
        digest = _root_identity_digest(str(repo_path))
        if digest is None:
            raise RuntimeError("project_root_identity_unavailable")
        root_identity_backfill.append((str(project_id), digest))

    schema_version_before = bind.exec_driver_sql("PRAGMA schema_version").scalar_one()
    tables = set(sa.inspect(bind).get_table_names())
    if ("workspace_boundaries" in tables) != ("system_settings" in tables):
        raise RuntimeError("partial_legacy_ledger_schema")
    origins: dict[str, str] = {}

    if "workspace_boundaries" in tables:
        _assert_existing_shape("workspace_boundaries")
        origins["workspace_boundaries"] = "adopted"
    else:
        op.create_table(
            "workspace_boundaries",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("path", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("path", name="uq_workspace_boundaries_path"),
        )
        origins["workspace_boundaries"] = "created"

    if "system_settings" in tables:
        _assert_existing_shape("system_settings")
        origins["system_settings"] = "adopted"
    else:
        op.create_table(
            "system_settings",
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("key"),
        )
        origins["system_settings"] = "created"

    # If the schema changed while preflight was reading it, abort rather than
    # blessing a moving target.  Own CREATE statements begin only after this
    # check for pre-existing assets.
    if schema_version_before != bind.exec_driver_sql("PRAGMA schema_version").scalar_one() and any(
        origin == "adopted" for origin in origins.values()
    ):
        raise RuntimeError("concurrent_schema_change")

    op.create_table(
        "schema_adoption_metadata",
        sa.Column("asset_key", sa.String(), nullable=False),
        sa.Column("structural_version", sa.String(), nullable=False),
        sa.Column("structure_digest", sa.String(length=64), nullable=False),
        sa.Column("origin", sa.String(), nullable=False),
        sa.Column("adopted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("origin IN ('created', 'adopted')", name="ck_schema_adoption_origin"),
        sa.PrimaryKeyConstraint("asset_key"),
    )
    metadata_table = sa.table(
        "schema_adoption_metadata",
        sa.column("asset_key", sa.String()),
        sa.column("structural_version", sa.String()),
        sa.column("structure_digest", sa.String(64)),
        sa.column("origin", sa.String()),
        sa.column("adopted_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    rows = []
    for asset_key, origin in origins.items():
        digest = _assert_existing_shape(asset_key)
        rows.append(
            {
                "asset_key": asset_key,
                "structural_version": "legacy-001",
                "structure_digest": digest,
                "origin": origin,
                "adopted_at": now,
            }
        )
    op.bulk_insert(metadata_table, rows)

    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("public_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("scope_state", sa.String(), nullable=False, server_default="unclaimed")
        )
        batch_op.add_column(
            sa.Column("control_plane", sa.String(), nullable=False, server_default="legacy")
        )
        batch_op.add_column(sa.Column("configured_fingerprint", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("root_identity_digest", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
        batch_op.create_check_constraint(
            "ck_projects_tenant_positive", "tenant_id IS NULL OR tenant_id > 0"
        )
        batch_op.create_check_constraint(
            "ck_projects_owner_positive", "owner_user_id IS NULL OR owner_user_id > 0"
        )
        batch_op.create_check_constraint(
            "ck_projects_scope_state",
            "scope_state IN ('unclaimed', 'claimed', 'quarantined')",
        )
        batch_op.create_check_constraint("ck_projects_control_plane", "control_plane = 'legacy'")
        batch_op.create_check_constraint(
            "ck_projects_root_identity_digest",
            "length(root_identity_digest) = 64 AND "
            "root_identity_digest NOT GLOB '*[^0-9a-f]*'",
        )
        batch_op.create_check_constraint("ck_projects_version_nonnegative", "version >= 0")

    for project_id, digest in root_identity_backfill:
        bind.execute(
            sa.text(
                "UPDATE projects SET root_identity_digest = :digest WHERE id = :project_id"
            ),
            {"project_id": project_id, "digest": digest},
        )
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.alter_column(
            "root_identity_digest",
            existing_type=sa.String(length=64),
            nullable=False,
        )

    op.create_index("uq_projects_public_id", "projects", ["public_id"], unique=True)
    op.create_index(
        "uq_projects_configured_fingerprint",
        "projects",
        ["configured_fingerprint"],
        unique=True,
    )
    op.create_index(
        "ix_projects_supervisor_scope",
        "projects",
        ["tenant_id", "owner_user_id", "scope_state"],
        unique=False,
    )
    op.create_index(
        "ix_projects_root_identity_digest",
        "projects",
        ["root_identity_digest"],
        unique=False,
    )

    op.execute(
        """
        CREATE TRIGGER trg_projects_claimed_insert_guard
        BEFORE INSERT ON projects
        WHEN NEW.scope_state = 'claimed' AND (
          NEW.public_id IS NULL OR length(NEW.public_id) < 20 OR length(NEW.public_id) > 68 OR
          substr(NEW.public_id, 1, 4) <> 'prj_' OR
          substr(NEW.public_id, 5) GLOB '*[^A-Za-z0-9_-]*' OR
          NEW.name IS NULL OR trim(NEW.name) = '' OR
          NEW.repo_path IS NULL OR trim(NEW.repo_path) = '' OR
          NEW.default_branch IS NULL OR trim(NEW.default_branch) = '' OR
          NEW.configured_fingerprint IS NULL OR length(NEW.configured_fingerprint) <> 64 OR
          NEW.configured_fingerprint GLOB '*[^0-9a-f]*' OR
          NEW.root_identity_digest IS NULL OR length(NEW.root_identity_digest) <> 64 OR
          NEW.root_identity_digest GLOB '*[^0-9a-f]*' OR
          NEW.tenant_id IS NULL OR NEW.tenant_id <= 0 OR
          NEW.owner_user_id IS NULL OR NEW.owner_user_id <= 0 OR
          NEW.claimed_at IS NULL OR NEW.control_plane <> 'legacy' OR NEW.version <> 1
        )
        BEGIN
          SELECT RAISE(ABORT, 'claimed_project_invariant');
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_projects_claimed_update_guard
        BEFORE UPDATE ON projects
        WHEN (
          OLD.scope_state = 'claimed' AND (
            NEW.public_id IS NOT OLD.public_id OR NEW.name IS NOT OLD.name OR
            NEW.repo_path IS NOT OLD.repo_path OR NEW.default_branch IS NOT OLD.default_branch OR
            NEW.configured_fingerprint IS NOT OLD.configured_fingerprint OR
            NEW.root_identity_digest IS NOT OLD.root_identity_digest OR
            NEW.tenant_id IS NOT OLD.tenant_id OR NEW.owner_user_id IS NOT OLD.owner_user_id OR
            NEW.claimed_at IS NOT OLD.claimed_at OR NEW.control_plane IS NOT OLD.control_plane OR
            NEW.scope_state IS NOT OLD.scope_state OR NEW.version IS NOT OLD.version
          )
        ) OR (
          NEW.scope_state = 'claimed' AND OLD.scope_state <> 'claimed' AND (
            NEW.public_id IS NULL OR length(NEW.public_id) < 20 OR length(NEW.public_id) > 68 OR
            substr(NEW.public_id, 1, 4) <> 'prj_' OR
            substr(NEW.public_id, 5) GLOB '*[^A-Za-z0-9_-]*' OR
            NEW.name IS NULL OR trim(NEW.name) = '' OR
            NEW.repo_path IS NULL OR trim(NEW.repo_path) = '' OR
            NEW.default_branch IS NULL OR trim(NEW.default_branch) = '' OR
            NEW.configured_fingerprint IS NULL OR length(NEW.configured_fingerprint) <> 64 OR
            NEW.configured_fingerprint GLOB '*[^0-9a-f]*' OR
            NEW.root_identity_digest IS NULL OR length(NEW.root_identity_digest) <> 64 OR
            NEW.root_identity_digest GLOB '*[^0-9a-f]*' OR
            NEW.tenant_id IS NULL OR NEW.tenant_id <= 0 OR
            NEW.owner_user_id IS NULL OR NEW.owner_user_id <= 0 OR
            NEW.claimed_at IS NULL OR NEW.control_plane <> 'legacy' OR NEW.version <> 1
          )
        )
        BEGIN
          SELECT RAISE(ABORT, 'claimed_project_invariant');
        END
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    protected = bind.execute(
        sa.text("SELECT COUNT(*) FROM projects WHERE scope_state IN ('claimed', 'quarantined')")
    ).scalar_one()
    if protected:
        raise RuntimeError("project_scope_downgrade_blocked")

    op.execute("DROP TRIGGER IF EXISTS trg_projects_claimed_update_guard")
    op.execute("DROP TRIGGER IF EXISTS trg_projects_claimed_insert_guard")
    op.drop_index("ix_projects_root_identity_digest", table_name="projects")
    op.drop_index("ix_projects_supervisor_scope", table_name="projects")
    op.drop_index("uq_projects_configured_fingerprint", table_name="projects")
    op.drop_index("uq_projects_public_id", table_name="projects")
    with op.batch_alter_table("projects", schema=None) as batch_op:
        for constraint in (
            "ck_projects_tenant_positive",
            "ck_projects_owner_positive",
            "ck_projects_scope_state",
            "ck_projects_control_plane",
            "ck_projects_root_identity_digest",
            "ck_projects_version_nonnegative",
        ):
            batch_op.drop_constraint(constraint, type_="check")
        for column in (
            "version",
            "claimed_at",
            "configured_fingerprint",
            "root_identity_digest",
            "control_plane",
            "scope_state",
            "owner_user_id",
            "tenant_id",
            "public_id",
        ):
            batch_op.drop_column(column)
    origins = dict(
        bind.execute(
            sa.text("SELECT asset_key, origin FROM schema_adoption_metadata")
        ).all()
    )
    op.drop_table("schema_adoption_metadata")
    if origins.get("system_settings") == "created":
        op.drop_table("system_settings")
    if origins.get("workspace_boundaries") == "created":
        op.drop_table("workspace_boundaries")
