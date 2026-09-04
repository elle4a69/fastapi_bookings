"""Add single-owner leases and retry state to the generic outbox.

Revision ID: d7e8f9a0b1c2
Revises: 4c9f0a1b2d3e
Create Date: 2026-09-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "d7e8f9a0b1c2"
down_revision = "4c9f0a1b2d3e"
branch_labels = ("outbox_safety_remediation",)
depends_on = None


def _add_validated_check(table: str, name: str, condition: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({condition}) NOT VALID"))
    op.execute(sa.text(f"ALTER TABLE {table} VALIDATE CONSTRAINT {name}"))


def upgrade() -> None:
    op.add_column("outbox_events", sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("outbox_events", sa.Column("max_attempts", sa.Integer(), server_default=sa.text("5"), nullable=False))
    op.add_column("outbox_events", sa.Column("error_code", sa.String(length=64), nullable=True))
    op.add_column("outbox_events", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("outbox_events", sa.Column("lease_owner", sa.String(length=128), nullable=True))
    op.add_column("outbox_events", sa.Column("lease_token", sa.String(length=36), nullable=True))
    op.add_column("outbox_events", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox_events", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox_events", sa.Column("dispatch_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox_events", sa.Column("provider_delivery_id", sa.String(length=128), nullable=True))
    op.add_column("outbox_events", sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("webhook_deliveries", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("webhook_deliveries", sa.Column("max_attempts", sa.Integer(), server_default=sa.text("5"), nullable=False))
    op.add_column("webhook_deliveries", sa.Column("lease_owner", sa.String(length=128), nullable=True))
    op.add_column("webhook_deliveries", sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(sa.text("UPDATE outbox_events SET retry_count = GREATEST(retry_count, 0)"))
    op.execute(sa.text("UPDATE outbox_events SET error_code = 'LEGACY_ERROR_REDACTED' WHERE error_log IS NOT NULL"))
    op.execute(sa.text("""
        UPDATE outbox_events SET status = 'QUARANTINED', processed = TRUE,
            processed_at = COALESCE(processed_at, created_at), terminal_at = COALESCE(processed_at, created_at),
            next_attempt_at = NULL, lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
            error_code = 'LEGACY_OUTCOME_UNKNOWN'
        WHERE status IN ('DISPATCHING', 'PROCESSING')
    """))
    op.execute(sa.text("""
        UPDATE outbox_events SET attempt_count = LEAST(retry_count, 5),
            status = CASE WHEN retry_count >= 5 THEN 'DEAD_LETTER' ELSE 'RETRY' END,
            processed = (retry_count >= 5),
            processed_at = CASE WHEN retry_count >= 5 THEN COALESCE(processed_at, created_at) ELSE NULL END,
            terminal_at = CASE WHEN retry_count >= 5 THEN COALESCE(processed_at, created_at) ELSE NULL END,
            next_attempt_at = CASE WHEN retry_count >= 5 THEN NULL ELSE created_at END,
            error_code = CASE WHEN retry_count >= 5 THEN 'ATTEMPTS_EXHAUSTED' ELSE error_code END
        WHERE status = 'FAILED'
    """))
    op.execute(sa.text("""
        UPDATE outbox_events SET status = 'SUCCEEDED', processed = TRUE,
            processed_at = COALESCE(processed_at, created_at), terminal_at = COALESCE(processed_at, created_at),
            next_attempt_at = NULL WHERE status = 'PROCESSED'
    """))
    op.execute(sa.text("""
        UPDATE outbox_events SET status = 'QUARANTINED', processed = TRUE,
            processed_at = COALESCE(processed_at, created_at), terminal_at = COALESCE(processed_at, created_at),
            next_attempt_at = NULL, lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
            error_code = 'LEGACY_STATUS_INVALID'
        WHERE status NOT IN ('PENDING','PROCESSING','RETRY','SUCCEEDED','DEAD_LETTER','QUARANTINED')
    """))
    op.execute(sa.text("UPDATE outbox_events SET next_attempt_at = COALESCE(next_attempt_at, created_at), processed = FALSE, terminal_at = NULL WHERE status IN ('PENDING','RETRY')"))
    op.execute(sa.text("UPDATE outbox_events SET processed = TRUE, terminal_at = COALESCE(terminal_at, processed_at, created_at), next_attempt_at = NULL WHERE status IN ('SUCCEEDED','QUARANTINED','DEAD_LETTER')"))
    op.execute(sa.text("UPDATE outbox_events SET error_code = 'LEGACY_ERROR_REDACTED' WHERE error_code IS NOT NULL AND error_code !~ '^[A-Z][A-Z0-9_]{0,63}$'"))
    op.execute(sa.text("UPDATE outbox_events SET idempotency_key = 'outbox:' || id::text WHERE idempotency_key IS NULL"))

    op.execute(sa.text("UPDATE webhook_deliveries SET attempt_count = LEAST(GREATEST(attempt_count, 0), 100)"))
    op.execute(sa.text("UPDATE webhook_deliveries SET max_attempts = GREATEST(5, attempt_count)"))
    op.execute(sa.text("""
        UPDATE webhook_deliveries SET status = 'QUARANTINED', terminal_at = COALESCE(delivered_at, CURRENT_TIMESTAMP),
            next_attempt_at = NULL, lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
            error_code = 'LEGACY_OUTCOME_UNKNOWN' WHERE status IN ('DISPATCHING','PROCESSING')
    """))
    op.execute(sa.text("""
        UPDATE webhook_deliveries SET status = CASE WHEN attempt_count >= 5 THEN 'DEAD_LETTER' ELSE 'RETRY' END,
            terminal_at = CASE WHEN attempt_count >= 5 THEN COALESCE(delivered_at, CURRENT_TIMESTAMP) ELSE NULL END,
            next_attempt_at = CASE WHEN attempt_count >= 5 THEN NULL ELSE CURRENT_TIMESTAMP END,
            error_code = CASE WHEN attempt_count >= 5 THEN 'ATTEMPTS_EXHAUSTED' ELSE error_code END,
            lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL WHERE status = 'FAILED'
    """))
    op.execute(sa.text("UPDATE webhook_deliveries SET status = 'SUCCEEDED', terminal_at = COALESCE(delivered_at, CURRENT_TIMESTAMP), next_attempt_at = NULL, lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL WHERE status = 'PROCESSED'"))
    op.execute(sa.text("""
        UPDATE webhook_deliveries SET status = 'QUARANTINED', terminal_at = COALESCE(delivered_at, CURRENT_TIMESTAMP),
            next_attempt_at = NULL, lease_owner = NULL, lease_token = NULL, lease_expires_at = NULL,
            error_code = 'LEGACY_STATUS_INVALID'
        WHERE status NOT IN ('PENDING','PROCESSING','RETRY','SUCCEEDED','DEAD_LETTER','QUARANTINED')
    """))
    op.execute(sa.text("UPDATE webhook_deliveries SET next_attempt_at = COALESCE(next_attempt_at, CURRENT_TIMESTAMP), terminal_at = NULL WHERE status IN ('PENDING','RETRY')"))
    op.execute(sa.text("UPDATE webhook_deliveries SET terminal_at = COALESCE(terminal_at, delivered_at, CURRENT_TIMESTAMP), next_attempt_at = NULL WHERE status IN ('SUCCEEDED','DEAD_LETTER','QUARANTINED')"))
    op.execute(sa.text("UPDATE webhook_deliveries SET error_code = 'LEGACY_ERROR_REDACTED' WHERE error_code IS NOT NULL AND error_code !~ '^[A-Z][A-Z0-9_]{0,63}$'"))
    op.execute(sa.text("""
        UPDATE webhook_deliveries SET idempotency_key = CASE WHEN webhook_id IS NULL
            THEN 'webhook:' || outbox_event_id::text || ':delivery:' || id::text
            ELSE 'webhook:' || outbox_event_id::text || ':' || webhook_id::text END
        WHERE idempotency_key IS NULL
    """))

    op.alter_column("outbox_events", "idempotency_key", existing_type=sa.String(length=128), nullable=False)
    op.alter_column("webhook_deliveries", "idempotency_key", existing_type=sa.String(length=128), nullable=False)
    op.create_unique_constraint("uq_outbox_events_idempotency_key", "outbox_events", ["idempotency_key"])
    op.create_unique_constraint("uq_outbox_events_lease_token", "outbox_events", ["lease_token"])
    op.create_unique_constraint("uq_webhook_deliveries_idempotency_key", "webhook_deliveries", ["idempotency_key"])
    op.drop_column("outbox_events", "error_log")

    checks = (
        ("outbox_events", "ck_outbox_events_status", "status IN ('PENDING','PROCESSING','RETRY','SUCCEEDED','DEAD_LETTER','QUARANTINED')"),
        ("outbox_events", "ck_outbox_events_attempts", "retry_count >= 0 AND attempt_count >= 0 AND max_attempts BETWEEN 1 AND 100 AND attempt_count <= max_attempts"),
        ("outbox_events", "ck_outbox_events_lease_state", "(status = 'PROCESSING' AND lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR (status <> 'PROCESSING' AND lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)"),
        ("outbox_events", "ck_outbox_events_next_attempt_state", "(status IN ('PENDING','RETRY') AND next_attempt_at IS NOT NULL) OR (status NOT IN ('PENDING','RETRY') AND next_attempt_at IS NULL)"),
        ("outbox_events", "ck_outbox_events_terminal_state", "(status IN ('SUCCEEDED','QUARANTINED','DEAD_LETTER') AND processed AND terminal_at IS NOT NULL) OR (status NOT IN ('SUCCEEDED','QUARANTINED','DEAD_LETTER') AND NOT processed AND terminal_at IS NULL)"),
        ("outbox_events", "ck_outbox_events_error_code", "error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,63}$'"),
        ("webhook_deliveries", "ck_webhook_deliveries_status", "status IN ('PENDING','PROCESSING','RETRY','SUCCEEDED','DEAD_LETTER','QUARANTINED')"),
        ("webhook_deliveries", "ck_webhook_deliveries_attempts", "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 100 AND attempt_count <= max_attempts"),
        ("webhook_deliveries", "ck_webhook_deliveries_lease_state", "(status = 'PROCESSING' AND lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR (status <> 'PROCESSING' AND lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)"),
        ("webhook_deliveries", "ck_webhook_deliveries_next_attempt_state", "(status IN ('PENDING','RETRY') AND next_attempt_at IS NOT NULL) OR (status NOT IN ('PENDING','RETRY') AND next_attempt_at IS NULL)"),
        ("webhook_deliveries", "ck_webhook_deliveries_terminal_state", "(status IN ('SUCCEEDED','DEAD_LETTER','QUARANTINED') AND terminal_at IS NOT NULL) OR (status NOT IN ('SUCCEEDED','DEAD_LETTER','QUARANTINED') AND terminal_at IS NULL)"),
        ("webhook_deliveries", "ck_webhook_deliveries_error_code", "error_code IS NULL OR error_code ~ '^[A-Z][A-Z0-9_]{0,63}$'"),
    )
    for table, name, condition in checks:
        _add_validated_check(table, name, condition)

    op.create_index("ix_outbox_events_dispatch_due", "outbox_events", ["next_attempt_at", "created_at", "id"], postgresql_where=sa.text("status IN ('PENDING','RETRY')"))
    op.create_index("ix_outbox_events_expired_lease", "outbox_events", ["lease_expires_at", "id"], postgresql_where=sa.text("status = 'PROCESSING'"))
    op.create_index("ix_webhook_deliveries_dispatch_due", "webhook_deliveries", ["next_attempt_at", "id"], postgresql_where=sa.text("status IN ('PENDING','RETRY')"))
    op.create_index("ix_webhook_deliveries_expired_lease", "webhook_deliveries", ["lease_expires_at", "id"], postgresql_where=sa.text("status = 'PROCESSING'"))


def downgrade() -> None:
    for index, table in (("ix_webhook_deliveries_expired_lease", "webhook_deliveries"), ("ix_webhook_deliveries_dispatch_due", "webhook_deliveries"), ("ix_outbox_events_expired_lease", "outbox_events"), ("ix_outbox_events_dispatch_due", "outbox_events")):
        op.drop_index(index, table_name=table)
    for table, name in (
        ("outbox_events", "ck_outbox_events_error_code"), ("outbox_events", "ck_outbox_events_terminal_state"),
        ("outbox_events", "ck_outbox_events_next_attempt_state"), ("outbox_events", "ck_outbox_events_lease_state"),
        ("outbox_events", "ck_outbox_events_attempts"), ("outbox_events", "ck_outbox_events_status"),
        ("webhook_deliveries", "ck_webhook_deliveries_error_code"), ("webhook_deliveries", "ck_webhook_deliveries_terminal_state"),
        ("webhook_deliveries", "ck_webhook_deliveries_next_attempt_state"), ("webhook_deliveries", "ck_webhook_deliveries_lease_state"),
        ("webhook_deliveries", "ck_webhook_deliveries_attempts"), ("webhook_deliveries", "ck_webhook_deliveries_status"),
    ):
        op.drop_constraint(name, table, type_="check")
    op.add_column("outbox_events", sa.Column("error_log", sa.Text(), nullable=True))
    op.execute(sa.text("""
        UPDATE outbox_events SET
            processed_at = CASE
                WHEN status IN ('SUCCEEDED','QUARANTINED','DEAD_LETTER','PROCESSING')
                    THEN COALESCE(processed_at, terminal_at, created_at)
                ELSE NULL
            END,
            processed = status IN ('SUCCEEDED','QUARANTINED','DEAD_LETTER','PROCESSING'),
            status = CASE
                WHEN status = 'SUCCEEDED' THEN 'PROCESSED'
                WHEN status = 'PENDING' THEN 'PENDING'
                WHEN status = 'RETRY' THEN 'FAILED'
                ELSE 'QUARANTINED'
            END
    """))
    op.execute(sa.text("""
        UPDATE webhook_deliveries SET status = CASE
            WHEN status = 'SUCCEEDED' THEN 'PROCESSED'
            WHEN status = 'PENDING' THEN 'PENDING'
            WHEN status = 'RETRY' THEN 'FAILED'
            ELSE 'QUARANTINED'
        END, lease_token = NULL, lease_expires_at = NULL, next_attempt_at = NULL
    """))
    op.drop_constraint("uq_outbox_events_lease_token", "outbox_events", type_="unique")
    op.drop_constraint("uq_outbox_events_idempotency_key", "outbox_events", type_="unique")
    op.drop_constraint("uq_webhook_deliveries_idempotency_key", "webhook_deliveries", type_="unique")
    for column in ("terminal_at", "lease_owner", "max_attempts", "idempotency_key"):
        op.drop_column("webhook_deliveries", column)
    for column in ("terminal_at", "provider_delivery_id", "dispatch_started_at", "next_attempt_at", "lease_expires_at", "lease_token", "lease_owner", "idempotency_key", "error_code", "max_attempts", "attempt_count"):
        op.drop_column("outbox_events", column)
