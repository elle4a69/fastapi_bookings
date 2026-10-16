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


EXPECTED_REVISION = "006"
KNOWN_REVISIONS = {"001", "002", "003", "004", "005", "006"}

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
    ("table", "idempotency_records"): "294d4f33a2b221a9dc5fc4fe1bc4d7ba09594648776d7bbc4d2e663171aabb57",
    ("table", "items"): "992d8ca0472555cc9b047379cda44017ec7b9f3e2aa7168da004b6e9b8841826",
    ("table", "projects"): "b83ee5f3b91cb5242a0faea30d4bdfb2815719a5c9412a3faf11872c55bd0101",
    ("table", "schema_adoption_metadata"): "4a5ede8c59c717b8911cf6bb2ad6af0783d16a766ff994f163069b8788fa6dd0",
    ("table", "subagents"): "58219b53cbed27c4307c91a554cd4fdd40b92c72aaebb361253815c9d9e6bb35",
    ("table", "supervisor_events"): "59b61fa033d9d1d2732461720462c8d86fedeaae0ad296e7a99fe5e2bc9534d8",
    ("table", "system_settings"): "946925a04a8fa0c119712e47858e0b86a19d664563e62e0248e53ce10d4fed2b",
    ("table", "threads"): "b54fa780b3aadf37bb5fa59fddc8ddbe88b1c331b7273cff1246b85593fed1ef",
    ("table", "tool_approvals"): "c44c7c914368b911c06ba4c14226836625f131616d67d2cc4c3d01970bc04d69",
    ("table", "turns"): "91ef2b0c6adae466ee650c677016a32dc6bb6c32b6a58064a4782449eb235647",
    ("table", "workspace_boundaries"): "b38767959d68467dcb89f15bdd574c39c7b4efd04296d34c71c20475559fc9fa",
    ("trigger", "trg_cutover_state_no_delete"): "2bf80387294d702010dcb3e7dcd9c842a68c467ef72e24261db756f8808b697e",
    ("trigger", "trg_cutover_state_no_update"): "aff2323d10f5a1926ff3f787739d04713ad876061c980d44a7f5fc434e1b626a",
    ("trigger", "trg_idempotency_terminal_headers_insert"): "506f16eed742a822291d43b79446185961f33e8d0a109cd95cf30d45f7697f5e",
    ("trigger", "trg_idempotency_terminal_headers_update"): "cc31dee3bf4439266e5d9be6c954e09a8999b0858f435b550e88dee44a764942",
    ("trigger", "trg_projects_claimed_insert_guard"): "b7a685eccac1f16fd69c9cc6036b39ee4df7d18e707ef9c1235c0b947073ee1c",
    ("trigger", "trg_projects_claimed_update_guard"): "b3984efa52e6f8c412d2123337e6225f8a4147a81fdc18ac0efd75d8a9ff1765",
    ("trigger", "trg_supervisor_events_no_delete"): "1d1e62ae6721afb7037121478e3066958c5767463222e91612cc2b9844c2c43f",
    ("trigger", "trg_supervisor_events_no_update"): "463fbba77a73a238a1fe9da79080ea8bf4d23f0b0eb4b11e6c9f6efbbd2cb4fc",
}

# Revision 005 intentionally widens the action allowlists through SQLite batch
# recreation. These exact hashes seal the rebuilt replay/event ledgers and the
# new run tables, rather than accepting merely same-named objects.
EXPECTED_RUN_SCHEMA_HASHES = {
    ("table", "idempotency_records"): "0986b2eaf10a23be6450e507e3347e149dc1b88df7fc014af6d73320f377025a",
    ("table", "supervisor_events"): "b900f1bc0e6cfd9f955b113d2cfc49765f1df8f08816357252a055ebe9f5aa1a",
    ("table", "supervisor_dispatch_attempts"): "537d8510a81ede340e945a546c98f454e2946c764dbdfd346a4ecd64362723aa",
    ("table", "supervisor_run_start_authorization_grants"): "e725d27bd94f27ca42bf1e428030a936a2fc4e33d140d47281ba936a59cd7140",
    ("table", "supervisor_runs"): "fcc5542e73c6082cf0685dbf194931baec86faf6fea81b3f949600ebeb96b4dc",
    ("trigger", "trg_run_grant_parent_scope"): "b985f0723a02b4bf3308c73d52448a1bb9dccb8eb894d871e1c73ff489e2fc5c",
    ("trigger", "trg_run_parent_scope"): "f5c7270198f96283058651a4dae7225034b17c038631d8dee567b4b9bebaa5f0",
    ("trigger", "trg_run_grant_no_delete"): "bcb756e42d0022cb55a79903a4b47588fa30c5eb62f6ce5b87ef90040e3d0c65",
    ("trigger", "trg_run_grant_consume_only"): "c030681450b3db5b8c9123849c4183cdc82d9e9e537b6277004685bb45ede49a",
    ("trigger", "trg_supervisor_run_no_delete"): "72ff0a4c3d2aa12e03cb37e42e43aa6b71b977f6d27a1784ced2cd8f15a61719",
    ("trigger", "trg_supervisor_run_transition_only"): "3b3628750062bd4ae31ab9c8a2063cdefa9841883584790f9ee5dbcd67dadeff",
    ("trigger", "trg_dispatch_attempt_no_delete"): "4dd7c216ffbf071f4c9d3bd5ffbc60f68a1832820887c61e595064a247c8ca8f",
    ("trigger", "trg_dispatch_attempt_transition_only"): "4e84f3be8a11b19a95423b79e7b0f84fc889d3edff257ee8a4dbdaca27e1656d",
}

# Revision 006 seals structural evidence records. These hashes deliberately
# cover the exact batch-recreated action ledgers too, not merely table names.
EXPECTED_EVIDENCE_SCHEMA_HASHES = {
    ("table", "idempotency_records"): "1e545a6ad04bb88b08b60b2921070b2b52fc36aaf195bc2f41731ed05fef5ad0",
    ("table", "supervisor_events"): "ed88be9f4457ab2ea63e71ba422e4aea923ce462f07a90e7d973db81efb8993e",
    ("table", "supervisor_acceptance_contracts"): "be032bc95842304c2bf34f23d0c9d6ba14d77aaa1ce1b18bf371c0a663ec6bda",
    ("table", "supervisor_run_baselines"): "f2e6383114859cdca6dae285179338e86b5ad032b440b13607bb2530216c2444",
    ("table", "supervisor_sandbox_attestations"): "baa2d2313e90b7413e8bd5ad3a60b84d298155b359c7d6883fedac307baef9b6",
    ("table", "supervisor_audit_requests"): "540b5c0d5258e92f0a4796ae22c924e0d9c90696c0de51227905d60aaccef319",
    ("table", "supervisor_audit_criterion_results"): "d225208a2d96e4451c982c168215dd3e01c03550d1aab3fd62acd0c66419cdd6",
    ("trigger", "trg_acceptance_contract_scope"): "a1d6edaf041b7029b6bf97acc7cf743e370a923f32160baeb7bca0840d5386df",
    ("trigger", "trg_baseline_run_scope"): "936980eea4561211ff0cefb8580dd5be9380216f7033325268687d1dd23bdf15",
    ("trigger", "trg_audit_request_scope"): "5638a622bd7ee4df12fc59ee5b22cb7c8d1dc7bcd4737389f15b99cba85aa620",
}

EXPECTED_ADOPTION_DIGESTS = {
    "system_settings": "b9d3e0610185c1ed5d78cbde1cfb8088cb98bff5c2b7e1199562601a184f32bd",
    "workspace_boundaries": "8ad02a423e414273e5f7fd5c675018b6a8d07b48935433a8375c3a40c07562cc",
}

# Revision 004 is a closed schema contract.  Do not replace these hashes with
# table-name checks: that would accept a dropped constraint or altered trigger.
EXPECTED_PLANNING_SCHEMA_HASHES = {
    ("table", "planning_audit_scopes"): "e20d08fdc621ddb8f6f445561f9b160879c070fc154820960603711ecee843dd",
    ("table", "planning_briefs"): "18457f1303ec0666e827c879a93821bb84e65e2ac850ce3db580c6cc17295489",
    ("table", "planning_context_checkpoints"): "ed128af27aecd516e76fcaab316602c5a7baea317aeb6e76493f03daee1c6623",
    ("table", "planning_missions"): "d1f5f441a3f1b7f8e46a1bfe48b2be2abb940ffed488f91df5a0fa68ea31be49",
    ("table", "planning_work_packages"): "f405231f3cd2c879b7066f0c6112a8aca783430fc601628f5385b34274fbff21",
    ("trigger", "trg_work_package_parent_scope"): "bd94ef02b433136d78c893bf5c5df2d27a3d93f64ad59b1f474e559d247aca17",
    ("trigger", "trg_brief_parent_scope"): "490b809134f252d6e0cd0d2a70c12eac0ab65ce29ab45eb4404d9a4de9413db5",
    ("trigger", "trg_checkpoint_parent_scope"): "812b2683e02d36386f3b7242edb9e4e925addf4df8bb79fd8f7c9f176eead6e5",
    ("trigger", "trg_audit_scope_parent_scope"): "df4686f035df16ad652daed52dcdb81d449e348acc39d0c6b9a6fcb8a0308fd2",
    ("trigger", "trg_mission_parent_scope"): "47841234ac4d43959c4d4b2b626387bb3c624eb0e1187981c08f356cc8f33ff2",
    ("trigger", "trg_planning_missions_no_delete"): "e266595aca2cc2bcb4d25351c5b65479e586e990640145c211db3d63a2037192",
    ("trigger", "trg_planning_missions_no_update"): "41f55ea9e007619b103684a871abf233df4eff92eccf0504eb4bef467648f3e0",
    ("trigger", "trg_planning_work_packages_no_delete"): "e2bacc25189aedf93981818e72e35b3475b32c08122afa16e5f67ab21d0e8dd2",
    ("trigger", "trg_planning_work_packages_immutable"): "b78a22468f4147e394cb29a4ab43f47b66072d9d2b332c9efdcbe508678507aa",
    ("trigger", "trg_planning_briefs_no_delete"): "d666ae39e608f1c1e634932ad7cf53c0d63c38bebb8e67982022557e9bd352bd",
    ("trigger", "trg_planning_briefs_immutable"): "0efaef736b88ce34095699638d74cc05fd55d1dd06ca4cfa11978777b22a21ea",
    ("trigger", "trg_planning_context_checkpoints_no_delete"): "84d6b6810462a87a4b0d78f456d5776a225d23085263bfa0600ee2e6c5874def",
    ("trigger", "trg_planning_context_checkpoints_no_update"): "7a703638da578b890232a29d0bbaabb495709ea523449f57ccdae16b163f76e0",
    ("trigger", "trg_planning_audit_scopes_no_delete"): "243427b3a8c40e2b6aebd2a54624a9a79cb10ca41e84dd36c76738117b5b9905",
    ("trigger", "trg_planning_audit_scopes_no_update"): "d6348b24a7dbdb0755071735ccffd2240992477b3a567036d23acc35046c6fe7",
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


def _ledger_structure_hash(connection, table_name: str) -> str:
    """Hash batch-recreated tables structurally, not by nondeterministic SQL order."""
    inspector = inspect(connection)
    material = {
        "columns": [{"name": c["name"], "type": str(c["type"]).upper(), "nullable": bool(c["nullable"]), "default": c.get("default"), "primary_key": int(c.get("primary_key") or 0)} for c in inspector.get_columns(table_name)],
        "checks": sorted((str(c.get("name") or ""), _normalized_sql(str(c.get("sqltext") or ""))) for c in inspector.get_check_constraints(table_name)),
        "foreign_keys": sorted((tuple(c.get("constrained_columns") or ()), str(c.get("referred_table") or ""), tuple(c.get("referred_columns") or ()), str((c.get("options") or {}).get("ondelete") or "")) for c in inspector.get_foreign_keys(table_name)),
        "unique_constraints": sorted(tuple(c.get("column_names") or ()) for c in inspector.get_unique_constraints(table_name)),
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


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
    hashes[("table", "idempotency_records")] = _ledger_structure_hash(connection, "idempotency_records")
    hashes[("table", "supervisor_events")] = _ledger_structure_hash(connection, "supervisor_events")
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
                if revision in {"001", "002", "003", "004", "005"}:
                    return InfrastructureReadiness(
                        "migration_required", revision, reason_codes=("revision_behind",)
                    )
                return InfrastructureReadiness(
                    "migration_required", "unknown", reason_codes=("revision_ahead",)
                )

            # 005 preserves the sealed planning contract and adds the bounded
            # run ledger.  The action-list constraints are intentionally
            # widened by the 005 migration, so they are checked structurally
            # through required tables rather than against 004's old hashes.
            hashes = _schema_hashes(connection)
            required_planning = {"planning_missions", "planning_work_packages", "planning_briefs", "planning_context_checkpoints", "planning_audit_scopes"}
            required_run = {"supervisor_runs", "supervisor_run_start_authorization_grants", "supervisor_dispatch_attempts"}
            required_evidence = {"supervisor_acceptance_contracts", "supervisor_run_baselines", "supervisor_sandbox_attestations", "supervisor_audit_requests", "supervisor_audit_criterion_results"}
            required_baseline = {key: value for key, value in EXPECTED_SCHEMA_HASHES.items() if key not in {("table", "idempotency_records"), ("table", "supervisor_events")}}
            if (not required_planning.issubset({name for (kind, name) in hashes if kind == "table"}) or
                not required_run.issubset({name for (kind, name) in hashes if kind == "table"}) or
                not required_evidence.issubset({name for (kind, name) in hashes if kind == "table"}) or
                any(hashes.get(key) != value for key, value in required_baseline.items()) or
                any(hashes.get(key) != value for key, value in EXPECTED_RUN_SCHEMA_HASHES.items() if key not in {("table", "idempotency_records"), ("table", "supervisor_events")}) or
                any(hashes.get(key) != value for key, value in EXPECTED_EVIDENCE_SCHEMA_HASHES.items()) or
                any(hashes.get(key) != value for key, value in EXPECTED_PLANNING_SCHEMA_HASHES.items())):
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
