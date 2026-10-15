"""add claim idempotency, fixed cutover posture and append-only events

Revision ID: 003
Revises: 002
"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, Sequence[str], None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        raise RuntimeError("unsupported_ccc_database_dialect")
    op.create_table(
        "control_plane_cutover_state",
        sa.Column("singleton_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False, server_default="v1_only"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("singleton_id = 1", name="ck_cutover_singleton"),
        sa.CheckConstraint("mode = 'v1_only'", name="ck_cutover_mode"),
        sa.CheckConstraint("version = 1", name="ck_cutover_version"),
        sa.PrimaryKeyConstraint("singleton_id"),
    )
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action_code", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(), nullable=True),
        sa.Column("lease_token_hash", sa.String(length=64), nullable=True),
        sa.Column("lease_acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.LargeBinary(), nullable=True),
        sa.Column("response_headers", sa.Text(), nullable=True),
        sa.CheckConstraint("tenant_id > 0 AND user_id > 0", name="ck_idempotency_scope_positive"),
        sa.CheckConstraint(
            "status IN ('in_progress', 'succeeded', 'failed')", name="ck_idempotency_status"
        ),
        sa.CheckConstraint(
            "lease_owner IS NULL OR (length(lease_owner) = 36 "
            "AND substr(lease_owner, 1, 4) = 'exe_' "
            "AND substr(lease_owner, 5) NOT GLOB '*[^0-9a-f]*')",
            name="ck_idempotency_lease_owner",
        ),
        sa.CheckConstraint("action_code = 'claim_project'", name="ck_idempotency_action"),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64 "
            "AND request_fingerprint NOT GLOB '*[^0-9a-f]*'",
            name="ck_idempotency_request_fingerprint",
        ),
        sa.CheckConstraint(
            "response_status IS NULL OR response_status BETWEEN 100 AND 599",
            name="ck_idempotency_response_status",
        ),
        sa.CheckConstraint(
            "lease_token_hash IS NULL OR (length(lease_token_hash) = 64 AND lease_token_hash NOT GLOB '*[^0-9a-f]*')",
            name="ck_idempotency_lease_hash",
        ),
        sa.CheckConstraint(
            "(status = 'in_progress' AND completed_at IS NULL AND expires_at IS NULL "
            "AND response_status IS NULL AND response_body IS NULL AND response_headers IS NULL "
            "AND lease_owner IS NOT NULL AND lease_token_hash IS NOT NULL "
            "AND lease_acquired_at IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
            "(status IN ('succeeded', 'failed') AND completed_at IS NOT NULL AND expires_at IS NOT NULL "
            "AND response_status IS NOT NULL AND response_body IS NOT NULL AND response_headers IS NOT NULL "
            "AND lease_owner IS NULL AND lease_token_hash IS NULL "
            "AND lease_acquired_at IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_idempotency_lifecycle",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR "
            "(strftime('%s', completed_at) IS NOT NULL AND "
            "strftime('%s', expires_at) IS NOT NULL AND "
            "CAST(strftime('%s', expires_at) AS INTEGER) = "
            "CAST(strftime('%s', completed_at) AS INTEGER) + 86400)",
            name="ck_idempotency_retention_24h",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            "action_code",
            "idempotency_key",
            name="uq_idempotency_scope_key",
        ),
    )
    op.create_index(
        "ix_idempotency_retention", "idempotency_records", ["status", "expires_at"], unique=False
    )
    op.create_table(
        "supervisor_events",
        sa.Column("event_key", sa.String(), nullable=False),
        sa.Column("project_public_id", sa.String(), nullable=False),
        sa.Column("project_sequence", sa.Integer(), nullable=False),
        sa.Column("actor_tenant_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("action_code", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False, server_default="0.1"),
        sa.Column("previous_digest", sa.String(length=64), nullable=True),
        sa.Column("integrity_digest", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actor_tenant_id > 0 AND actor_user_id > 0", name="ck_supervisor_event_scope"
        ),
        sa.CheckConstraint("action_code = 'claim_project'", name="ck_supervisor_event_action"),
        sa.CheckConstraint("schema_version = '0.1'", name="ck_supervisor_event_schema"),
        sa.CheckConstraint("project_version >= 1", name="ck_supervisor_event_project_version"),
        sa.CheckConstraint("project_sequence >= 1", name="ck_supervisor_event_sequence"),
        sa.CheckConstraint(
            "(project_sequence = 1 AND previous_digest IS NULL) OR "
            "(project_sequence > 1 AND length(previous_digest) = 64 "
            "AND previous_digest NOT GLOB '*[^0-9a-f]*')",
            name="ck_supervisor_event_previous_digest",
        ),
        sa.CheckConstraint("outcome = 'succeeded'", name="ck_supervisor_event_outcome"),
        sa.CheckConstraint(
            "length(payload_sha256) = 64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="ck_supervisor_event_payload_digest",
        ),
        sa.CheckConstraint(
            "length(idempotency_key_hash) = 64 AND idempotency_key_hash NOT GLOB '*[^0-9a-f]*'",
            name="ck_supervisor_event_idempotency_digest",
        ),
        sa.CheckConstraint(
            "length(integrity_digest) = 64 AND integrity_digest NOT GLOB '*[^0-9a-f]*'",
            name="ck_supervisor_event_integrity_digest",
        ),
        sa.PrimaryKeyConstraint("event_key"),
        sa.UniqueConstraint("integrity_digest", name="uq_supervisor_event_integrity_digest"),
        sa.UniqueConstraint(
            "project_public_id", "project_sequence", name="uq_supervisor_event_project_sequence"
        ),
        sa.UniqueConstraint("request_id", "action_code", name="uq_supervisor_event_request_action"),
    )
    op.create_index(
        "ix_supervisor_events_project_time",
        "supervisor_events",
        ["project_public_id", "occurred_at"],
        unique=False,
    )
    op.execute(
        """
        CREATE TRIGGER trg_supervisor_events_no_update
        BEFORE UPDATE ON supervisor_events
        BEGIN SELECT RAISE(ABORT, 'supervisor_events_append_only'); END
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_cutover_state_no_update
        BEFORE UPDATE ON control_plane_cutover_state
        BEGIN SELECT RAISE(ABORT, 'cutover_state_fixed'); END
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_cutover_state_no_delete
        BEFORE DELETE ON control_plane_cutover_state
        BEGIN SELECT RAISE(ABORT, 'cutover_state_fixed'); END
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_idempotency_terminal_headers_insert
        BEFORE INSERT ON idempotency_records
        WHEN NEW.response_headers IS NOT NULL AND (
          json_valid(NEW.response_headers) = 0 OR
          (SELECT count(*) FROM json_each(NEW.response_headers)) NOT IN (3, 4) OR
          (SELECT count(*) FROM json_each(NEW.response_headers)) <>
            (SELECT count(DISTINCT key) FROM json_each(NEW.response_headers)) OR
          EXISTS (
            SELECT 1 FROM json_each(NEW.response_headers)
            WHERE key NOT IN ('Content-Type', 'ETag', 'Cache-Control', 'X-Request-ID')
               OR type <> 'text'
          ) OR
          json_extract(NEW.response_headers, '$."Content-Type"') IS NOT 'application/json' OR
          json_extract(NEW.response_headers, '$."Cache-Control"') IS NOT 'no-store' OR
          json_extract(NEW.response_headers, '$."X-Request-ID"') IS NOT NEW.request_id OR
          (NEW.status = 'succeeded' AND (
            (SELECT count(*) FROM json_each(NEW.response_headers)) <> 4 OR
            json_type(NEW.response_headers, '$."ETag"') IS NOT 'text'
          )) OR
          (NEW.status = 'failed' AND (
            (SELECT count(*) FROM json_each(NEW.response_headers)) <> 3 OR
            json_type(NEW.response_headers, '$."ETag"') IS NOT NULL
          ))
        )
        BEGIN SELECT RAISE(ABORT, 'invalid_replay_headers'); END
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_idempotency_terminal_headers_update
        BEFORE UPDATE ON idempotency_records
        WHEN NEW.response_headers IS NOT NULL AND (
          json_valid(NEW.response_headers) = 0 OR
          (SELECT count(*) FROM json_each(NEW.response_headers)) NOT IN (3, 4) OR
          (SELECT count(*) FROM json_each(NEW.response_headers)) <>
            (SELECT count(DISTINCT key) FROM json_each(NEW.response_headers)) OR
          EXISTS (
            SELECT 1 FROM json_each(NEW.response_headers)
            WHERE key NOT IN ('Content-Type', 'ETag', 'Cache-Control', 'X-Request-ID')
               OR type <> 'text'
          ) OR
          json_extract(NEW.response_headers, '$."Content-Type"') IS NOT 'application/json' OR
          json_extract(NEW.response_headers, '$."Cache-Control"') IS NOT 'no-store' OR
          json_extract(NEW.response_headers, '$."X-Request-ID"') IS NOT NEW.request_id OR
          (NEW.status = 'succeeded' AND (
            (SELECT count(*) FROM json_each(NEW.response_headers)) <> 4 OR
            json_type(NEW.response_headers, '$."ETag"') IS NOT 'text'
          )) OR
          (NEW.status = 'failed' AND (
            (SELECT count(*) FROM json_each(NEW.response_headers)) <> 3 OR
            json_type(NEW.response_headers, '$."ETag"') IS NOT NULL
          ))
        )
        BEGIN SELECT RAISE(ABORT, 'invalid_replay_headers'); END
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_supervisor_events_no_delete
        BEFORE DELETE ON supervisor_events
        BEGIN SELECT RAISE(ABORT, 'supervisor_events_append_only'); END
        """
    )

    now = datetime.now(timezone.utc)
    op.bulk_insert(
        sa.table(
            "control_plane_cutover_state",
            sa.column("singleton_id", sa.Integer()),
            sa.column("mode", sa.String()),
            sa.column("version", sa.Integer()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [{"singleton_id": 1, "mode": "v1_only", "version": 1, "created_at": now, "updated_at": now}],
    )


def downgrade() -> None:
    x_args = context.get_x_argument(as_dictionary=True)
    acknowledged = x_args.get("ccc_ack_claim_evidence_loss") == "yes"
    acknowledged = acknowledged or bool(
        context.config.attributes.get("ccc_ack_claim_evidence_loss") == "yes"
    )
    if not acknowledged:
        raise RuntimeError("claim_evidence_loss_acknowledgement_required")
    op.execute("DROP TRIGGER IF EXISTS trg_idempotency_terminal_headers_update")
    op.execute("DROP TRIGGER IF EXISTS trg_idempotency_terminal_headers_insert")
    op.execute("DROP TRIGGER IF EXISTS trg_cutover_state_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_cutover_state_no_update")
    op.execute("DROP TRIGGER IF EXISTS trg_supervisor_events_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_supervisor_events_no_update")
    op.drop_index("ix_supervisor_events_project_time", table_name="supervisor_events")
    op.drop_table("supervisor_events")
    op.drop_index("ix_idempotency_retention", table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_table("control_plane_cutover_state")
