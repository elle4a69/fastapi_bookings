"""Add fail-closed structural evidence and independent-audit records.

Revision ID: 006
Revises: 005
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, Sequence[str], None] = "005"
branch_labels = None
depends_on = None


def _digest(name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"length({name}) = 64 AND {name} NOT GLOB '*[^0-9a-f]*'", name=f"ck_{name}")


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        raise RuntimeError("unsupported_ccc_database_dialect")
    actions = "'claim_project','create_mission','create_work_package','create_brief','approve_brief','record_context_checkpoint','define_audit_scope','issue_run_start_authorization','start_supervisor_run','create_acceptance_contract','request_independent_audit'"
    for table, constraint in (("idempotency_records", "ck_idempotency_action"), ("supervisor_events", "ck_supervisor_event_action")):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(constraint, type_="check")
            column = "action_code"
            batch.create_check_constraint(constraint, f"{column} IN ({actions})")
    # Batch recreation removes these guards; restore them before a V2 action is possible.
    op.execute("CREATE TRIGGER trg_supervisor_events_no_update BEFORE UPDATE ON supervisor_events BEGIN SELECT RAISE(ABORT, 'supervisor_events_append_only'); END")
    op.execute("CREATE TRIGGER trg_supervisor_events_no_delete BEFORE DELETE ON supervisor_events BEGIN SELECT RAISE(ABORT, 'supervisor_events_append_only'); END")
    for trigger_name, event in (("trg_idempotency_terminal_headers_insert", "INSERT"), ("trg_idempotency_terminal_headers_update", "UPDATE")):
        op.execute(f"""CREATE TRIGGER {trigger_name} BEFORE {event} ON idempotency_records
        WHEN NEW.response_headers IS NOT NULL AND (
          json_valid(NEW.response_headers) = 0 OR
          (SELECT count(*) FROM json_each(NEW.response_headers)) NOT IN (3, 4) OR
          (SELECT count(*) FROM json_each(NEW.response_headers)) <> (SELECT count(DISTINCT key) FROM json_each(NEW.response_headers)) OR
          EXISTS (SELECT 1 FROM json_each(NEW.response_headers) WHERE key NOT IN ('Content-Type', 'ETag', 'Cache-Control', 'X-Request-ID') OR type <> 'text') OR
          json_extract(NEW.response_headers, '$."Content-Type"') IS NOT 'application/json' OR
          json_extract(NEW.response_headers, '$."Cache-Control"') IS NOT 'no-store' OR
          json_extract(NEW.response_headers, '$."X-Request-ID"') IS NOT NEW.request_id OR
          (NEW.status = 'succeeded' AND ((SELECT count(*) FROM json_each(NEW.response_headers)) <> 4 OR json_type(NEW.response_headers, '$."ETag"') IS NOT 'text')) OR
          (NEW.status = 'failed' AND ((SELECT count(*) FROM json_each(NEW.response_headers)) <> 3 OR json_type(NEW.response_headers, '$."ETag"') IS NOT NULL))
        ) BEGIN SELECT RAISE(ABORT, 'invalid_replay_headers'); END""")
    op.create_table(
        "supervisor_acceptance_contracts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_package_id", sa.String(), sa.ForeignKey("planning_work_packages.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("audit_scope_id", sa.String(), sa.ForeignKey("planning_audit_scopes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("registry_version", sa.String(), nullable=False), sa.Column("criterion_codes", sa.String(512), nullable=False),
        sa.Column("criterion_digest", sa.String(64), nullable=False), sa.Column("state", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id LIKE 'acc_%'", name="ck_acceptance_contract_id"),
        sa.CheckConstraint("tenant_id > 0 AND owner_user_id > 0", name="ck_acceptance_contract_scope"),
        sa.CheckConstraint("registry_version = '1'", name="ck_acceptance_contract_registry"),
        sa.CheckConstraint("criterion_codes IN ('[\"repository_identity_bound\",\"baseline_captured\",\"sandbox_attested\"]')", name="ck_acceptance_contract_codes"),
        _digest("criterion_digest"), sa.CheckConstraint("state = 'approved'", name="ck_acceptance_contract_state"),
    )
    op.create_table(
        "supervisor_run_baselines",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("run_id", sa.String(), sa.ForeignKey("supervisor_runs.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("repository_identity_digest", sa.String(64), nullable=False), sa.Column("head_commit_digest", sa.String(64), nullable=False), sa.Column("tree_digest", sa.String(64), nullable=False), sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id LIKE 'rbl_%'", name="ck_run_baseline_id"), sa.CheckConstraint("tenant_id > 0 AND owner_user_id > 0", name="ck_run_baseline_scope"),
        _digest("repository_identity_digest"), _digest("head_commit_digest"), _digest("tree_digest"),
    )
    op.create_table(
        "supervisor_sandbox_attestations",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("run_id", sa.String(), sa.ForeignKey("supervisor_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("owner_user_id", sa.Integer(), nullable=False), sa.Column("sandbox_profile", sa.String(), nullable=False),
        sa.Column("attestation_digest", sa.String(64), nullable=False, unique=True), sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id LIKE 'sat_%'", name="ck_sandbox_attestation_id"), sa.CheckConstraint("tenant_id > 0 AND owner_user_id > 0", name="ck_sandbox_attestation_scope"),
        sa.CheckConstraint("sandbox_profile = 'host_enforced_read_only_v1'", name="ck_sandbox_attestation_profile"), _digest("attestation_digest"), sa.CheckConstraint("expires_at > issued_at", name="ck_sandbox_attestation_expiry"),
    )
    op.create_table(
        "supervisor_audit_requests",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("run_id", sa.String(), sa.ForeignKey("supervisor_runs.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("owner_user_id", sa.Integer(), nullable=False), sa.Column("contract_id", sa.String(), sa.ForeignKey("supervisor_acceptance_contracts.id", ondelete="RESTRICT"), nullable=False), sa.Column("baseline_id", sa.String(), sa.ForeignKey("supervisor_run_baselines.id", ondelete="RESTRICT"), nullable=False), sa.Column("state", sa.String(), nullable=False), sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id LIKE 'arq_%'", name="ck_audit_request_id"), sa.CheckConstraint("tenant_id > 0 AND owner_user_id > 0", name="ck_audit_request_scope"), sa.CheckConstraint("state IN ('sandbox_unavailable','attestation_required','submitted','completed_no_verdict')", name="ck_audit_request_state"),
    )
    op.create_table(
        "supervisor_audit_criterion_results",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("audit_request_id", sa.String(), sa.ForeignKey("supervisor_audit_requests.id", ondelete="RESTRICT"), nullable=False), sa.Column("criterion_code", sa.String(), nullable=False), sa.Column("outcome", sa.String(), nullable=False), sa.Column("evidence_digest", sa.String(64)), sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("audit_request_id", "criterion_code", name="uq_audit_criterion_once"), sa.CheckConstraint("id LIKE 'acr_%'", name="ck_audit_criterion_id"), sa.CheckConstraint("criterion_code IN ('repository_identity_bound','baseline_captured','sandbox_attested')", name="ck_audit_criterion_code"), sa.CheckConstraint("outcome IN ('not_evaluated','passed','failed')", name="ck_audit_criterion_outcome"), _digest("evidence_digest"),
    )
    for table in ("supervisor_acceptance_contracts", "supervisor_run_baselines", "supervisor_sandbox_attestations", "supervisor_audit_requests", "supervisor_audit_criterion_results"):
        op.execute(f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, '{table}_append_only'); END")
        op.execute(f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, '{table}_append_only'); END")
    op.execute("CREATE TRIGGER trg_acceptance_contract_scope BEFORE INSERT ON supervisor_acceptance_contracts WHEN NOT EXISTS (SELECT 1 FROM planning_audit_scopes a JOIN planning_work_packages w ON w.id=a.work_package_id WHERE a.id=NEW.audit_scope_id AND w.id=NEW.work_package_id AND w.project_id=NEW.project_id AND w.tenant_id=NEW.tenant_id AND w.owner_user_id=NEW.owner_user_id AND w.state='brief_approved') BEGIN SELECT RAISE(ABORT, 'acceptance_contract_scope'); END")
    op.execute("CREATE TRIGGER trg_baseline_run_scope BEFORE INSERT ON supervisor_run_baselines WHEN NOT EXISTS (SELECT 1 FROM supervisor_runs r WHERE r.id=NEW.run_id AND r.tenant_id=NEW.tenant_id AND r.owner_user_id=NEW.owner_user_id) BEGIN SELECT RAISE(ABORT, 'baseline_run_scope'); END")
    op.execute("CREATE TRIGGER trg_audit_request_scope BEFORE INSERT ON supervisor_audit_requests WHEN NOT EXISTS (SELECT 1 FROM supervisor_runs r JOIN supervisor_acceptance_contracts c ON c.work_package_id=r.work_package_id JOIN supervisor_run_baselines b ON b.run_id=r.id WHERE r.id=NEW.run_id AND c.id=NEW.contract_id AND b.id=NEW.baseline_id AND r.tenant_id=NEW.tenant_id AND r.owner_user_id=NEW.owner_user_id AND c.tenant_id=NEW.tenant_id AND c.owner_user_id=NEW.owner_user_id AND b.tenant_id=NEW.tenant_id AND b.owner_user_id=NEW.owner_user_id) BEGIN SELECT RAISE(ABORT, 'audit_request_scope'); END")


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("supervisor_acceptance_contracts", "supervisor_run_baselines", "supervisor_sandbox_attestations", "supervisor_audit_requests", "supervisor_audit_criterion_results"):
        if bind.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("evidence_audit_ledger_downgrade_blocked")
    for table in ("supervisor_audit_criterion_results", "supervisor_audit_requests", "supervisor_sandbox_attestations", "supervisor_run_baselines", "supervisor_acceptance_contracts"):
        op.drop_table(table)
    actions = "'claim_project','create_mission','create_work_package','create_brief','approve_brief','record_context_checkpoint','define_audit_scope','issue_run_start_authorization','start_supervisor_run'"
    for table, constraint in (("idempotency_records", "ck_idempotency_action"), ("supervisor_events", "ck_supervisor_event_action")):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(constraint, type_="check")
            batch.create_check_constraint(constraint, f"action_code IN ({actions})")
    op.execute("CREATE TRIGGER trg_supervisor_events_no_update BEFORE UPDATE ON supervisor_events BEGIN SELECT RAISE(ABORT, 'supervisor_events_append_only'); END")
    op.execute("CREATE TRIGGER trg_supervisor_events_no_delete BEFORE DELETE ON supervisor_events BEGIN SELECT RAISE(ABORT, 'supervisor_events_append_only'); END")
    for trigger_name, event in (("trg_idempotency_terminal_headers_insert", "INSERT"), ("trg_idempotency_terminal_headers_update", "UPDATE")):
        op.execute(f"""CREATE TRIGGER {trigger_name} BEFORE {event} ON idempotency_records
        WHEN NEW.response_headers IS NOT NULL AND (json_valid(NEW.response_headers) = 0 OR (SELECT count(*) FROM json_each(NEW.response_headers)) NOT IN (3, 4) OR (SELECT count(*) FROM json_each(NEW.response_headers)) <> (SELECT count(DISTINCT key) FROM json_each(NEW.response_headers)) OR EXISTS (SELECT 1 FROM json_each(NEW.response_headers) WHERE key NOT IN ('Content-Type', 'ETag', 'Cache-Control', 'X-Request-ID') OR type <> 'text') OR json_extract(NEW.response_headers, '$."Content-Type"') IS NOT 'application/json' OR json_extract(NEW.response_headers, '$."Cache-Control"') IS NOT 'no-store' OR json_extract(NEW.response_headers, '$."X-Request-ID"') IS NOT NEW.request_id OR (NEW.status = 'succeeded' AND ((SELECT count(*) FROM json_each(NEW.response_headers)) <> 4 OR json_type(NEW.response_headers, '$."ETag"') IS NOT 'text')) OR (NEW.status = 'failed' AND ((SELECT count(*) FROM json_each(NEW.response_headers)) <> 3 OR json_type(NEW.response_headers, '$."ETag"') IS NOT NULL))) BEGIN SELECT RAISE(ABORT, 'invalid_replay_headers'); END""")
