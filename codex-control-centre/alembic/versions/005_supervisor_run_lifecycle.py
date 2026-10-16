"""add the bounded supervisor run and one-run start-authorisation ledgers.

Revision ID: 005
Revises: 004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005"
down_revision: Union[str, Sequence[str], None] = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        raise RuntimeError("unsupported_ccc_database_dialect")
    actions = "'claim_project','create_mission','create_work_package','create_brief','approve_brief','record_context_checkpoint','define_audit_scope','issue_run_start_authorization','start_supervisor_run'"
    # Batch recreation drops the two append-only replay guards; restore them
    # before any V2 run action can be reserved.
    with op.batch_alter_table("idempotency_records") as batch:
        batch.drop_constraint("ck_idempotency_action", type_="check")
        batch.create_check_constraint("ck_idempotency_action", f"action_code IN ({actions})")
    with op.batch_alter_table("supervisor_events") as batch:
        batch.drop_constraint("ck_supervisor_event_action", type_="check")
        batch.create_check_constraint("ck_supervisor_event_action", f"action_code IN ({actions})")
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
        "supervisor_run_start_authorization_grants",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_package_id", sa.String(), sa.ForeignKey("planning_work_packages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("brief_id", sa.String(), sa.ForeignKey("planning_briefs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("audit_scope_id", sa.String(), sa.ForeignKey("planning_audit_scopes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("authorization_hash", sa.String(64), nullable=False, unique=True), sa.Column("policy", sa.String(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)), sa.Column("run_id", sa.String(), unique=True),
        sa.CheckConstraint("id LIKE 'sag_%'", name="ck_run_grant_id"),
        sa.CheckConstraint("tenant_id > 0 AND owner_user_id > 0", name="ck_run_grant_scope"),
        sa.CheckConstraint("policy IN ('requires_authorization','not_required_once_requested')", name="ck_run_grant_policy"),
        sa.CheckConstraint("length(authorization_hash) = 64 AND authorization_hash NOT GLOB '*[^0-9a-f]*'", name="ck_run_grant_hash"),
        sa.CheckConstraint("expires_at > issued_at", name="ck_run_grant_expiry"),
        sa.CheckConstraint("(consumed_at IS NULL AND run_id IS NULL) OR (consumed_at IS NOT NULL AND run_id IS NOT NULL)", name="ck_run_grant_consumption"),
    )
    op.create_table(
        "supervisor_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_package_id", sa.String(), sa.ForeignKey("planning_work_packages.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("brief_id", sa.String(), sa.ForeignKey("planning_briefs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("audit_scope_id", sa.String(), sa.ForeignKey("planning_audit_scopes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("grant_id", sa.String(), sa.ForeignKey("supervisor_run_start_authorization_grants.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("brief_content_digest", sa.String(64), nullable=False), sa.Column("capability_profile", sa.String(), nullable=False, server_default="development_worker_v1"),
        sa.Column("status", sa.String(), nullable=False), sa.Column("request_id", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("dispatched_at", sa.DateTime(timezone=True)), sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id LIKE 'run_%'", name="ck_supervisor_run_id"), sa.CheckConstraint("tenant_id > 0 AND owner_user_id > 0", name="ck_supervisor_run_scope"),
        sa.CheckConstraint("length(brief_content_digest) = 64 AND brief_content_digest NOT GLOB '*[^0-9a-f]*'", name="ck_supervisor_run_brief_digest"),
        sa.CheckConstraint("capability_profile = 'development_worker_v1'", name="ck_supervisor_run_capability"),
        sa.CheckConstraint("status IN ('dispatching','dispatch_acknowledged','dispatch_unknown','dispatch_rejected','completed','failed')", name="ck_supervisor_run_status"),
    )
    op.create_table(
        "supervisor_dispatch_attempts",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("run_id", sa.String(), sa.ForeignKey("supervisor_runs.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False), sa.Column("owner_user_id", sa.Integer(), nullable=False), sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id LIKE 'dpa_%'", name="ck_dispatch_attempt_id"), sa.CheckConstraint("tenant_id > 0 AND owner_user_id > 0 AND attempt_number = 1", name="ck_dispatch_attempt_scope"),
        sa.CheckConstraint("state IN ('intent_persisted','acknowledged','dispatch_unknown','rejected')", name="ck_dispatch_attempt_state"),
    )
    op.create_index("ix_supervisor_runs_scope_status", "supervisor_runs", ["tenant_id", "owner_user_id", "work_package_id", "status"])
    op.create_index("ix_run_grants_expiry", "supervisor_run_start_authorization_grants", ["expires_at", "consumed_at"])
    # Scope and immutable ancestry are enforced below the service boundary.
    op.execute("CREATE TRIGGER trg_run_grant_parent_scope BEFORE INSERT ON supervisor_run_start_authorization_grants WHEN NOT EXISTS (SELECT 1 FROM planning_briefs b JOIN planning_audit_scopes a ON a.work_package_id=b.work_package_id JOIN planning_work_packages w ON w.id=b.work_package_id WHERE b.id=NEW.brief_id AND a.id=NEW.audit_scope_id AND w.id=NEW.work_package_id AND b.project_id=NEW.project_id AND b.tenant_id=NEW.tenant_id AND b.owner_user_id=NEW.owner_user_id AND b.state='approved') BEGIN SELECT RAISE(ABORT,'run_grant_parent_scope'); END")
    op.execute("CREATE TRIGGER trg_run_parent_scope BEFORE INSERT ON supervisor_runs WHEN NOT EXISTS (SELECT 1 FROM supervisor_run_start_authorization_grants g WHERE g.id=NEW.grant_id AND g.project_id=NEW.project_id AND g.work_package_id=NEW.work_package_id AND g.brief_id=NEW.brief_id AND g.audit_scope_id=NEW.audit_scope_id AND g.tenant_id=NEW.tenant_id AND g.owner_user_id=NEW.owner_user_id AND g.run_id=NEW.id AND g.consumed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'run_parent_scope'); END")
    op.execute("CREATE TRIGGER trg_run_grant_no_delete BEFORE DELETE ON supervisor_run_start_authorization_grants BEGIN SELECT RAISE(ABORT,'run_grant_append_only'); END")
    op.execute("CREATE TRIGGER trg_run_grant_consume_only BEFORE UPDATE ON supervisor_run_start_authorization_grants WHEN NOT (OLD.consumed_at IS NULL AND OLD.run_id IS NULL AND NEW.consumed_at IS NOT NULL AND NEW.run_id IS NOT NULL AND julianday(NEW.consumed_at) IS NOT NULL AND julianday(OLD.expires_at) IS NOT NULL AND julianday(NEW.consumed_at) <= julianday(OLD.expires_at) AND NEW.id=OLD.id AND NEW.project_id=OLD.project_id AND NEW.work_package_id=OLD.work_package_id AND NEW.brief_id=OLD.brief_id AND NEW.audit_scope_id=OLD.audit_scope_id AND NEW.tenant_id=OLD.tenant_id AND NEW.owner_user_id=OLD.owner_user_id AND NEW.authorization_hash=OLD.authorization_hash AND NEW.policy=OLD.policy AND NEW.issued_at=OLD.issued_at AND NEW.expires_at=OLD.expires_at) BEGIN SELECT RAISE(ABORT,'run_grant_immutable'); END")
    op.execute("CREATE TRIGGER trg_supervisor_run_no_delete BEFORE DELETE ON supervisor_runs BEGIN SELECT RAISE(ABORT,'supervisor_run_append_only'); END")
    op.execute("CREATE TRIGGER trg_supervisor_run_transition_only BEFORE UPDATE ON supervisor_runs WHEN NOT ((OLD.status='dispatching' AND NEW.status IN ('dispatch_acknowledged','dispatch_unknown','dispatch_rejected') AND NEW.id=OLD.id AND NEW.project_id=OLD.project_id AND NEW.work_package_id=OLD.work_package_id AND NEW.brief_id=OLD.brief_id AND NEW.audit_scope_id=OLD.audit_scope_id AND NEW.grant_id=OLD.grant_id AND NEW.tenant_id=OLD.tenant_id AND NEW.owner_user_id=OLD.owner_user_id AND NEW.brief_content_digest=OLD.brief_content_digest AND NEW.capability_profile=OLD.capability_profile AND NEW.request_id=OLD.request_id AND NEW.created_at=OLD.created_at AND NEW.dispatched_at=OLD.dispatched_at AND ((NEW.status='dispatch_acknowledged' AND NEW.acknowledged_at IS NOT NULL) OR (NEW.status IN ('dispatch_unknown','dispatch_rejected') AND NEW.acknowledged_at IS NULL))) OR (OLD.status='dispatch_acknowledged' AND NEW.status IN ('completed','failed') AND NEW.id=OLD.id AND NEW.project_id=OLD.project_id AND NEW.work_package_id=OLD.work_package_id AND NEW.brief_id=OLD.brief_id AND NEW.audit_scope_id=OLD.audit_scope_id AND NEW.grant_id=OLD.grant_id AND NEW.tenant_id=OLD.tenant_id AND NEW.owner_user_id=OLD.owner_user_id AND NEW.brief_content_digest=OLD.brief_content_digest AND NEW.capability_profile=OLD.capability_profile AND NEW.request_id=OLD.request_id AND NEW.created_at=OLD.created_at AND NEW.dispatched_at=OLD.dispatched_at AND NEW.acknowledged_at=OLD.acknowledged_at)) BEGIN SELECT RAISE(ABORT,'supervisor_run_immutable'); END")
    op.execute("CREATE TRIGGER trg_dispatch_attempt_no_delete BEFORE DELETE ON supervisor_dispatch_attempts BEGIN SELECT RAISE(ABORT,'dispatch_attempt_append_only'); END")
    op.execute("CREATE TRIGGER trg_dispatch_attempt_transition_only BEFORE UPDATE ON supervisor_dispatch_attempts WHEN NOT (OLD.state='intent_persisted' AND NEW.state IN ('acknowledged','dispatch_unknown','rejected') AND NEW.id=OLD.id AND NEW.run_id=OLD.run_id AND NEW.tenant_id=OLD.tenant_id AND NEW.owner_user_id=OLD.owner_user_id AND NEW.attempt_number=OLD.attempt_number AND NEW.created_at=OLD.created_at AND ((NEW.state='acknowledged' AND NEW.acknowledged_at IS NOT NULL) OR (NEW.state IN ('dispatch_unknown','rejected') AND NEW.acknowledged_at IS NULL))) BEGIN SELECT RAISE(ABORT,'dispatch_attempt_immutable'); END")


def downgrade() -> None:
    bind = op.get_bind()
    # This revision must not partially downgrade to 004 and leave the durable
    # planning ledger to fail only in the next migration. Alembic records the
    # revision after each step, so all protected context is checked first.
    for table in ("planning_missions", "planning_work_packages", "planning_briefs", "planning_context_checkpoints", "planning_audit_scopes"):
        if bind.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("planning_ledger_downgrade_blocked")
    for table in ("supervisor_dispatch_attempts", "supervisor_runs", "supervisor_run_start_authorization_grants"):
        if bind.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("supervisor_run_ledger_downgrade_blocked")
    op.execute("DROP TRIGGER IF EXISTS trg_run_parent_scope")
    op.execute("DROP TRIGGER IF EXISTS trg_run_grant_parent_scope")
    for trigger in ("trg_run_grant_no_delete", "trg_run_grant_consume_only", "trg_supervisor_run_no_delete", "trg_supervisor_run_transition_only", "trg_dispatch_attempt_no_delete", "trg_dispatch_attempt_transition_only"):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    op.drop_index("ix_run_grants_expiry", table_name="supervisor_run_start_authorization_grants")
    op.drop_index("ix_supervisor_runs_scope_status", table_name="supervisor_runs")
    op.drop_table("supervisor_dispatch_attempts")
    op.drop_table("supervisor_runs")
    op.drop_table("supervisor_run_start_authorization_grants")
