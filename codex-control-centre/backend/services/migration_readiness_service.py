"""Read-only, bounded and exact CCC migration readiness inspection."""

from dataclasses import dataclass
import hashlib
import json
import re
import time
from typing import Literal

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from backend import database


EXPECTED_REVISION = "003"
KNOWN_REVISIONS = {"001", "002", "003"}

# SHA-256 of whitespace-normalized, lower-cased sqlite_master SQL emitted by the
# accepted 001 -> 002 -> 003 migration chain. Comparing the complete set and
# complete definitions proves columns (order/type/nullability/default/PK), FKs,
# unique/check constraints, explicit index columns/uniqueness, and trigger bodies.
EXPECTED_SCHEMA_HASHES = {
    ("index", "ix_idempotency_retention"): "5decdf15f10f9e1e4c23982e2bcc8a07c18cda0f5f82f9a97b324e9ce3543180",
    ("index", "ix_projects_root_identity_digest"): "7caba0848d02e95fbc73e742e58bbfddd393900e2bfd9a54b42d06992a4c92b3",
    ("index", "ix_projects_supervisor_scope"): "ed44e4cef7990e2e112a214a6ef65121c90768afc3d34ccda3f109ae331b86bc",
    ("index", "ix_supervisor_events_project_time"): "255337401cc56ccfa2edd0387be7630f65008a3a41ba35e9000edcb88bbf222c",
    ("index", "uq_projects_configured_fingerprint"): "89117d018ce9f67a4a6827a79035e2c25b080073d7ebb55745f4c416fc119d19",
    ("index", "uq_projects_public_id"): "4b688239b763993391efbeb7e9445238c2dbffa1c410b530076a71a57265bd28",
    ("table", "alembic_version"): "3534487946a27f6fa8fd1cc640a6c1ef3ebccd2d2601e74225dccf1b6bc97054",
    ("table", "control_plane_cutover_state"): "560c62b1127bf9e4dda10a10ca0616e78d9e4d1a819b7c3ed5d2c20e01f5598e",
    ("table", "idempotency_records"): "fa8b1a811bda425eae1cefa3d04970ba96a792f69ffb4a37dd036fee9628078c",
    ("table", "items"): "992d8ca0472555cc9b047379cda44017ec7b9f3e2aa7168da004b6e9b8841826",
    ("table", "projects"): "b83ee5f3b91cb5242a0faea30d4bdfb2815719a5c9412a3faf11872c55bd0101",
    ("table", "schema_adoption_metadata"): "4a5ede8c59c717b8911cf6bb2ad6af0783d16a766ff994f163069b8788fa6dd0",
    ("table", "subagents"): "58219b53cbed27c4307c91a554cd4fdd40b92c72aaebb361253815c9d9e6bb35",
    ("table", "supervisor_events"): "803dddce2673815417024d659e1fb8051c659ade6ab73d8270c4387ad5b8268b",
    ("table", "system_settings"): "946925a04a8fa0c119712e47858e0b86a19d664563e62e0248e53ce10d4fed2b",
    ("table", "threads"): "b54fa780b3aadf37bb5fa59fddc8ddbe88b1c331b7273cff1246b85593fed1ef",
    ("table", "tool_approvals"): "c44c7c914368b911c06ba4c14226836625f131616d67d2cc4c3d01970bc04d69",
    ("table", "turns"): "91ef2b0c6adae466ee650c677016a32dc6bb6c32b6a58064a4782449eb235647",
    ("table", "workspace_boundaries"): "b38767959d68467dcb89f15bdd574c39c7b4efd04296d34c71c20475559fc9fa",
    ("trigger", "trg_cutover_state_no_delete"): "2bf80387294d702010dcb3e7dcd9c842a68c467ef72e24261db756f8808b697e",
    ("trigger", "trg_cutover_state_no_update"): "aff2323d10f5a1926ff3f787739d04713ad876061c980d44a7f5fc434e1b626a",
    ("trigger", "trg_idempotency_terminal_headers_insert"): "39ddd75fa7e0eb6f8c023034d083a6e7cb480c34b8536078df3d708ffc590ef9",
    ("trigger", "trg_idempotency_terminal_headers_update"): "2ced7ea72ffafa74f1260a5a9598ec1b5774f513e94cb0b9b48fb19ec6d11f7d",
    ("trigger", "trg_projects_claimed_insert_guard"): "b7a685eccac1f16fd69c9cc6036b39ee4df7d18e707ef9c1235c0b947073ee1c",
    ("trigger", "trg_projects_claimed_update_guard"): "b3984efa52e6f8c412d2123337e6225f8a4147a81fdc18ac0efd75d8a9ff1765",
    ("trigger", "trg_supervisor_events_no_delete"): "1d1e62ae6721afb7037121478e3066958c5767463222e91612cc2b9844c2c43f",
    ("trigger", "trg_supervisor_events_no_update"): "463fbba77a73a238a1fe9da79080ea8bf4d23f0b0eb4b11e6c9f6efbbd2cb4fc",
}

EXPECTED_ADOPTION_DIGESTS = {
    "system_settings": "b9d3e0610185c1ed5d78cbde1cfb8088cb98bff5c2b7e1199562601a184f32bd",
    "workspace_boundaries": "8ad02a423e414273e5f7fd5c675018b6a8d07b48935433a8375c3a40c07562cc",
}


@dataclass(frozen=True, slots=True)
class InfrastructureReadiness:
    state: Literal["ready", "migration_required", "dependency_unavailable"]
    current_revision: str | None
    expected_revision: str = EXPECTED_REVISION
    reason_codes: tuple[str, ...] = ()

    def public_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "current_revision": self.current_revision,
            "expected_revision": self.expected_revision,
            "reason_codes": list(self.reason_codes),
        }


def _normalized_sql(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def _projects_structure_hash(connection) -> str:
    """Hash exact project structure without depending on SQLite clause order."""
    inspector = inspect(connection)
    material = {
        "columns": [
            {
                "name": column["name"],
                "type": str(column["type"]).upper(),
                "nullable": bool(column["nullable"]),
                "default": column.get("default"),
                "primary_key": int(column.get("primary_key") or 0),
            }
            for column in inspector.get_columns("projects")
        ],
        "checks": sorted(
            (
                str(constraint.get("name") or ""),
                _normalized_sql(str(constraint.get("sqltext") or "")),
            )
            for constraint in inspector.get_check_constraints("projects")
        ),
        "foreign_keys": sorted(
            (
                tuple(constraint.get("constrained_columns") or ()),
                str(constraint.get("referred_table") or ""),
                tuple(constraint.get("referred_columns") or ()),
                str((constraint.get("options") or {}).get("ondelete") or ""),
            )
            for constraint in inspector.get_foreign_keys("projects")
        ),
        "unique_constraints": sorted(
            tuple(constraint.get("column_names") or ())
            for constraint in inspector.get_unique_constraints("projects")
        ),
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _schema_hashes(connection) -> dict[tuple[str, str], str]:
    rows = connection.execute(
        text(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' AND sql IS NOT NULL "
            "ORDER BY type, name"
        )
    ).all()
    hashes = {
        (str(row.type), str(row.name)): hashlib.sha256(
            _normalized_sql(str(row.sql)).encode("utf-8")
        ).hexdigest()
        for row in rows
    }
    hashes[("table", "projects")] = _projects_structure_hash(connection)
    return hashes


def _fixed_rows_are_exact(connection) -> bool:
    cutover = connection.execute(
        text(
            "SELECT singleton_id, mode, version FROM control_plane_cutover_state "
            "ORDER BY singleton_id"
        )
    ).all()
    if [tuple(row) for row in cutover] != [(1, "v1_only", 1)]:
        return False

    adoption = connection.execute(
        text(
            "SELECT asset_key, structural_version, structure_digest, origin, adopted_at "
            "FROM schema_adoption_metadata ORDER BY asset_key"
        )
    ).all()
    if len(adoption) != 2:
        return False
    for row in adoption:
        if (
            row.asset_key not in EXPECTED_ADOPTION_DIGESTS
            or row.structural_version != "legacy-001"
            or row.structure_digest != EXPECTED_ADOPTION_DIGESTS[row.asset_key]
            or row.origin not in {"created", "adopted"}
            or row.adopted_at is None
        ):
            return False
    return True


def inspect_infrastructure(db_engine: Engine | None = None) -> InfrastructureReadiness:
    """Inspect ledger/structure/fixed metadata only, never a project-domain row."""
    selected_engine = db_engine or database.engine
    started = time.monotonic()
    try:
        with selected_engine.connect() as connection:
            if connection.dialect.name != "sqlite":
                return InfrastructureReadiness("dependency_unavailable", None)
            connection.exec_driver_sql("PRAGMA busy_timeout=1000")
            table_names = {
                str(row[0])
                for row in connection.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
            }
            if "alembic_version" not in table_names:
                return InfrastructureReadiness(
                    "migration_required", None, reason_codes=("revision_missing",)
                )
            ledger_columns = connection.exec_driver_sql(
                "PRAGMA table_info('alembic_version')"
            ).all()
            if len(ledger_columns) != 1 or ledger_columns[0][1] != "version_num":
                return InfrastructureReadiness(
                    "migration_required", "unknown", reason_codes=("schema_mismatch",)
                )
            revisions = tuple(
                row[0]
                for row in connection.execute(text("SELECT version_num FROM alembic_version"))
            )
            if len(revisions) != 1:
                return InfrastructureReadiness(
                    "migration_required", "unknown", reason_codes=("schema_mismatch",)
                )
            revision = str(revisions[0])
            if revision != EXPECTED_REVISION:
                if revision in {"001", "002"}:
                    return InfrastructureReadiness(
                        "migration_required", revision, reason_codes=("revision_behind",)
                    )
                return InfrastructureReadiness(
                    "migration_required", "unknown", reason_codes=("revision_ahead",)
                )

            if _schema_hashes(connection) != EXPECTED_SCHEMA_HASHES:
                return InfrastructureReadiness(
                    "migration_required", EXPECTED_REVISION, reason_codes=("schema_mismatch",)
                )
            if not _fixed_rows_are_exact(connection):
                return InfrastructureReadiness(
                    "migration_required", EXPECTED_REVISION, reason_codes=("schema_mismatch",)
                )
            if time.monotonic() - started > 1.0:
                return InfrastructureReadiness("dependency_unavailable", None)
            return InfrastructureReadiness("ready", EXPECTED_REVISION)
    except (SQLAlchemyError, OSError, ValueError):
        return InfrastructureReadiness("dependency_unavailable", None)
