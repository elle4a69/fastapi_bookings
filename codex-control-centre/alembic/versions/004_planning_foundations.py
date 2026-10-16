"""planning-only supervisor ledger; preserves the 003 claim ledger.

Revision ID: 004
Revises: 003
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, Sequence[str], None] = "003"
branch_labels = None
depends_on = None
_ACTIONS = "'claim_project','create_mission','create_work_package','create_brief','approve_brief','record_context_checkpoint','define_audit_scope'"

def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        raise RuntimeError("unsupported_ccc_database_dialect")
    # SQLite batch recreation preserves all existing records and event digest material.
    with op.batch_alter_table("idempotency_records") as b:
        b.drop_constraint("ck_idempotency_action", type_="check")
        b.create_check_constraint("ck_idempotency_action", f"action_code IN ({_ACTIONS})")
    with op.batch_alter_table("supervisor_events") as b:
        b.drop_constraint("ck_supervisor_event_action", type_="check")
        b.create_check_constraint("ck_supervisor_event_action", f"action_code IN ({_ACTIONS})")
        b.drop_constraint("ck_supervisor_event_schema", type_="check")
        b.create_check_constraint("ck_supervisor_event_schema", "schema_version IN ('0.1','0.2')")
    # SQLite batch recreation drops triggers. Restore the 003 replay and event
    # integrity guards before exposing the widened action registry.
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
    op.create_table("planning_missions", sa.Column("id",sa.String(),primary_key=True), sa.Column("project_id",sa.String(),sa.ForeignKey("projects.id",ondelete="RESTRICT"),nullable=False), sa.Column("tenant_id",sa.Integer(),nullable=False), sa.Column("owner_user_id",sa.Integer(),nullable=False), sa.Column("title",sa.String(160),nullable=False), sa.Column("summary",sa.String(1200),nullable=False), sa.Column("state",sa.String(),nullable=False,server_default="draft"), sa.Column("version",sa.Integer(),nullable=False,server_default="1"), sa.Column("created_at",sa.DateTime(timezone=True),nullable=False), sa.CheckConstraint("id LIKE 'mis_%'",name="ck_mission_id"),sa.CheckConstraint("tenant_id > 0 AND owner_user_id > 0 AND version >= 1",name="ck_mission_scope"),sa.CheckConstraint("state IN ('draft','planned')",name="ck_mission_state"))
    op.create_table("planning_work_packages", sa.Column("id",sa.String(),primary_key=True),sa.Column("mission_id",sa.String(),sa.ForeignKey("planning_missions.id",ondelete="RESTRICT"),nullable=False),sa.Column("project_id",sa.String(),sa.ForeignKey("projects.id",ondelete="RESTRICT"),nullable=False),sa.Column("tenant_id",sa.Integer(),nullable=False),sa.Column("owner_user_id",sa.Integer(),nullable=False),sa.Column("title",sa.String(160),nullable=False),sa.Column("scope",sa.String(1600),nullable=False),sa.Column("state",sa.String(),nullable=False,server_default="draft"),sa.Column("version",sa.Integer(),nullable=False,server_default="1"),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint("id LIKE 'wpk_%'",name="ck_work_package_id"),sa.CheckConstraint("tenant_id > 0 AND owner_user_id > 0 AND version >= 1",name="ck_work_package_scope"),sa.CheckConstraint("state IN ('draft','brief_ready','brief_approved')",name="ck_work_package_state"))
    op.create_table("planning_briefs",sa.Column("id",sa.String(),primary_key=True),sa.Column("work_package_id",sa.String(),sa.ForeignKey("planning_work_packages.id",ondelete="RESTRICT"),nullable=False),sa.Column("project_id",sa.String(),sa.ForeignKey("projects.id",ondelete="RESTRICT"),nullable=False),sa.Column("tenant_id",sa.Integer(),nullable=False),sa.Column("owner_user_id",sa.Integer(),nullable=False),sa.Column("revision",sa.Integer(),nullable=False),sa.Column("content",sa.String(4000),nullable=False),sa.Column("content_digest",sa.String(64),nullable=False),sa.Column("future_execution_authorization_requirement",sa.String(),nullable=False,server_default="requires_authorization"),sa.Column("state",sa.String(),nullable=False,server_default="draft"),sa.Column("version",sa.Integer(),nullable=False,server_default="1"),sa.Column("approved_by_user_id",sa.Integer()),sa.Column("approved_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("work_package_id","revision",name="uq_brief_revision"),sa.CheckConstraint("id LIKE 'brf_%'",name="ck_brief_id"),sa.CheckConstraint("state IN ('draft','approved','superseded')",name="ck_brief_state"),sa.CheckConstraint("future_execution_authorization_requirement IN ('requires_authorization','not_required_once_requested')",name="ck_brief_authorization"))
    op.create_table("planning_context_checkpoints",sa.Column("id",sa.String(),primary_key=True),sa.Column("mission_id",sa.String(),sa.ForeignKey("planning_missions.id",ondelete="RESTRICT"),nullable=False),sa.Column("project_id",sa.String(),sa.ForeignKey("projects.id",ondelete="RESTRICT"),nullable=False),sa.Column("tenant_id",sa.Integer(),nullable=False),sa.Column("owner_user_id",sa.Integer(),nullable=False),sa.Column("sequence",sa.Integer(),nullable=False),sa.Column("summary",sa.String(1600),nullable=False),sa.Column("decisions",sa.String(1600),nullable=False),sa.Column("constraints",sa.String(1600),nullable=False),sa.Column("open_questions",sa.String(1600),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("mission_id","sequence",name="uq_checkpoint_sequence"),sa.CheckConstraint("id LIKE 'ctx_%'",name="ck_checkpoint_id"))
    op.create_table("planning_audit_scopes",sa.Column("id",sa.String(),primary_key=True),sa.Column("work_package_id",sa.String(),sa.ForeignKey("planning_work_packages.id",ondelete="RESTRICT"),nullable=False,unique=True),sa.Column("project_id",sa.String(),sa.ForeignKey("projects.id",ondelete="RESTRICT"),nullable=False),sa.Column("tenant_id",sa.Integer(),nullable=False),sa.Column("owner_user_id",sa.Integer(),nullable=False),sa.Column("criteria",sa.String(2000),nullable=False),sa.Column("exclusions",sa.String(1200),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint("id LIKE 'asc_%'",name="ck_audit_scope_id"))
    for table in ("planning_missions","planning_context_checkpoints","planning_audit_scopes"):
        op.execute(f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'planning_append_only'); END")
        op.execute(f"CREATE TRIGGER trg_{table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'planning_immutable'); END")
    op.execute("CREATE TRIGGER trg_planning_briefs_immutable BEFORE UPDATE ON planning_briefs WHEN NOT ((OLD.state='draft' AND NEW.state='approved' AND NEW.approved_by_user_id IS NOT NULL AND NEW.approved_at IS NOT NULL AND NEW.version=OLD.version+1 AND NEW.work_package_id=OLD.work_package_id AND NEW.project_id=OLD.project_id AND NEW.tenant_id=OLD.tenant_id AND NEW.owner_user_id=OLD.owner_user_id AND NEW.revision=OLD.revision AND NEW.content=OLD.content AND NEW.content_digest=OLD.content_digest AND NEW.future_execution_authorization_requirement=OLD.future_execution_authorization_requirement AND NEW.created_at=OLD.created_at) OR (OLD.state='approved' AND NEW.state='superseded' AND NEW.version=OLD.version AND NEW.work_package_id=OLD.work_package_id AND NEW.project_id=OLD.project_id AND NEW.tenant_id=OLD.tenant_id AND NEW.owner_user_id=OLD.owner_user_id AND NEW.revision=OLD.revision AND NEW.content=OLD.content AND NEW.content_digest=OLD.content_digest AND NEW.future_execution_authorization_requirement=OLD.future_execution_authorization_requirement AND NEW.approved_by_user_id=OLD.approved_by_user_id AND NEW.approved_at=OLD.approved_at AND NEW.created_at=OLD.created_at)) BEGIN SELECT RAISE(ABORT, 'planning_brief_immutable'); END")
    op.execute("CREATE TRIGGER trg_planning_work_packages_immutable BEFORE UPDATE ON planning_work_packages WHEN NOT (((OLD.state='draft' AND NEW.state='brief_approved') OR (OLD.state='brief_approved' AND NEW.state='brief_ready') OR (OLD.state='brief_ready' AND NEW.state='brief_approved')) AND NEW.version=OLD.version+1 AND NEW.mission_id=OLD.mission_id AND NEW.project_id=OLD.project_id AND NEW.tenant_id=OLD.tenant_id AND NEW.owner_user_id=OLD.owner_user_id AND NEW.title=OLD.title AND NEW.scope=OLD.scope AND NEW.created_at=OLD.created_at) BEGIN SELECT RAISE(ABORT, 'planning_work_package_immutable'); END")
    # DB-level ancestry guards make direct SQL unable to forge cross-project or
    # cross-owner planning trees.  Application checks remain defensive only.
    for table in ("planning_work_packages", "planning_briefs"):
        op.execute(f"CREATE TRIGGER trg_{table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'planning_append_only'); END")
    op.execute("CREATE TRIGGER trg_mission_parent_scope BEFORE INSERT ON planning_missions WHEN NOT EXISTS (SELECT 1 FROM projects p WHERE p.id=NEW.project_id AND p.tenant_id=NEW.tenant_id AND p.owner_user_id=NEW.owner_user_id AND p.scope_state='claimed') BEGIN SELECT RAISE(ABORT,'planning_parent_scope'); END")
    op.execute("CREATE TRIGGER trg_work_package_parent_scope BEFORE INSERT ON planning_work_packages WHEN NOT EXISTS (SELECT 1 FROM planning_missions m JOIN projects p ON p.id=m.project_id WHERE m.id=NEW.mission_id AND m.project_id=NEW.project_id AND m.tenant_id=NEW.tenant_id AND m.owner_user_id=NEW.owner_user_id AND p.scope_state='claimed') BEGIN SELECT RAISE(ABORT,'planning_parent_scope'); END")
    op.execute("CREATE TRIGGER trg_brief_parent_scope BEFORE INSERT ON planning_briefs WHEN NOT EXISTS (SELECT 1 FROM planning_work_packages w JOIN planning_missions m ON m.id=w.mission_id WHERE w.id=NEW.work_package_id AND w.project_id=NEW.project_id AND w.tenant_id=NEW.tenant_id AND w.owner_user_id=NEW.owner_user_id AND m.project_id=NEW.project_id AND m.tenant_id=NEW.tenant_id AND m.owner_user_id=NEW.owner_user_id) BEGIN SELECT RAISE(ABORT,'planning_parent_scope'); END")
    op.execute("CREATE TRIGGER trg_checkpoint_parent_scope BEFORE INSERT ON planning_context_checkpoints WHEN NOT EXISTS (SELECT 1 FROM planning_missions m WHERE m.id=NEW.mission_id AND m.project_id=NEW.project_id AND m.tenant_id=NEW.tenant_id AND m.owner_user_id=NEW.owner_user_id) BEGIN SELECT RAISE(ABORT,'planning_parent_scope'); END")
    op.execute("CREATE TRIGGER trg_audit_scope_parent_scope BEFORE INSERT ON planning_audit_scopes WHEN NOT EXISTS (SELECT 1 FROM planning_work_packages w JOIN planning_missions m ON m.id=w.mission_id WHERE w.id=NEW.work_package_id AND w.project_id=NEW.project_id AND w.tenant_id=NEW.tenant_id AND w.owner_user_id=NEW.owner_user_id AND m.project_id=NEW.project_id AND m.tenant_id=NEW.tenant_id AND m.owner_user_id=NEW.owner_user_id) BEGIN SELECT RAISE(ABORT,'planning_parent_scope'); END")

def downgrade() -> None:
    bind = op.get_bind()
    # Downgrading an empty planning extension is reversible.  Existing durable
    # planning records are never silently discarded.
    for table in ("planning_missions", "planning_work_packages", "planning_briefs", "planning_context_checkpoints", "planning_audit_scopes"):
        if bind.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("planning_ledger_downgrade_blocked")
    for trigger in ("trg_mission_parent_scope", "trg_work_package_parent_scope", "trg_brief_parent_scope", "trg_checkpoint_parent_scope", "trg_audit_scope_parent_scope", "trg_planning_briefs_no_delete", "trg_planning_work_packages_no_delete", "trg_planning_work_packages_immutable", "trg_planning_briefs_immutable", "trg_planning_audit_scopes_no_delete", "trg_planning_audit_scopes_no_update", "trg_planning_context_checkpoints_no_delete", "trg_planning_context_checkpoints_no_update", "trg_planning_missions_no_delete", "trg_planning_missions_no_update"):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    for table in ("planning_audit_scopes", "planning_context_checkpoints", "planning_briefs", "planning_work_packages", "planning_missions"):
        op.drop_table(table)
    with op.batch_alter_table("supervisor_events") as b:
        b.drop_constraint("ck_supervisor_event_schema", type_="check")
        b.drop_constraint("ck_supervisor_event_action", type_="check")
        b.create_check_constraint("ck_supervisor_event_action", "action_code = 'claim_project'")
        b.create_check_constraint("ck_supervisor_event_schema", "schema_version = '0.1'")
    with op.batch_alter_table("idempotency_records") as b:
        b.drop_constraint("ck_idempotency_action", type_="check")
        b.create_check_constraint("ck_idempotency_action", "action_code = 'claim_project'")
