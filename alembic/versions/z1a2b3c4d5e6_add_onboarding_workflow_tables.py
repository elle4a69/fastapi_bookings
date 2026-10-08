"""Add onboarding workflow tables (plans, steps, audit logs)

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
Create Date: 2026-10-08 17:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'z1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'y0z1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "onboarding_plans" not in existing_tables:
        op.create_table(
            "onboarding_plans",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="in_progress"),
            sa.Column("current_step_id", sa.String(length=64), nullable=True),
            sa.Column("domains_state", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("control_epoch", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("active_lease_token", sa.String(length=128), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_onboarding_plans_tenant_user_status",
            "onboarding_plans",
            ["tenant_id", "user_id", "status"],
        )

    if "onboarding_steps" not in existing_tables:
        op.create_table(
            "onboarding_steps",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column(
                "plan_id",
                sa.Integer(),
                sa.ForeignKey("onboarding_plans.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("step_id", sa.String(length=64), nullable=False),
            sa.Column("domain", sa.Integer(), nullable=False),
            sa.Column("route", sa.String(length=255), nullable=False),
            sa.Column("form_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="not_started"),
            sa.Column("required_facts", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("answered_facts", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("staged_fields", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("persisted_entity_id", sa.String(length=64), nullable=True),
            sa.Column("persisted_revision", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("plan_id", "step_id", name="uq_onboarding_step_plan_step"),
        )
        op.create_index(
            "ix_onboarding_steps_plan_domain",
            "onboarding_steps",
            ["plan_id", "domain"],
        )

    if "onboarding_audit_logs" not in existing_tables:
        op.create_table(
            "onboarding_audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "plan_id",
                sa.Integer(),
                sa.ForeignKey("onboarding_plans.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("actor", sa.String(length=32), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_onboarding_audit_logs_tenant_created",
            "onboarding_audit_logs",
            ["tenant_id", "created_at"],
        )
        op.create_index(
            "ix_onboarding_audit_logs_plan_created",
            "onboarding_audit_logs",
            ["plan_id", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "onboarding_audit_logs" in existing_tables:
        op.drop_table("onboarding_audit_logs")
    if "onboarding_steps" in existing_tables:
        op.drop_table("onboarding_steps")
    if "onboarding_plans" in existing_tables:
        op.drop_table("onboarding_plans")
