"""Reconcile missing domain tables (tenant_websites, client_disputes, sms_quick_tools, gdpr_consents).

Revision ID: m3n4p5q6r7s8
Revises: k2m3n4p5q6r7
Create Date: 2026-10-02 20:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m3n4p5q6r7s8"
down_revision: Union[str, Sequence[str], None] = "k2m3n4p5q6r7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing_tables = _existing_tables()

    if "tenant_websites" not in existing_tables:
        op.create_table(
            "tenant_websites",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("template_id", sa.String(), nullable=False, server_default="minimalist"),
            sa.Column("theme_id", sa.String(), nullable=False, server_default="ocean_slate"),
            sa.Column("custom_colors", sa.JSON(), nullable=True),
            sa.Column("sections_data", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("seo_title", sa.String(), nullable=True),
            sa.Column("seo_description", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_tenant_websites_id", "tenant_websites", ["id"])
        op.create_index("ix_tenant_websites_tenant_id", "tenant_websites", ["tenant_id"], unique=True)

    if "client_disputes" not in existing_tables:
        op.create_table(
            "client_disputes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "client_id",
                sa.Integer(),
                sa.ForeignKey("clients.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "booking_id",
                sa.Integer(),
                sa.ForeignKey("bookings.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("status", sa.String(), nullable=False, server_default="submitted"),
            sa.Column("reason", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("preferred_resolution", sa.String(), nullable=False, server_default="redo_service"),
            sa.Column("resolution_notes", sa.Text(), nullable=True),
            sa.Column("photos", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_client_disputes_id", "client_disputes", ["id"])
        op.create_index("ix_client_disputes_tenant_id", "client_disputes", ["tenant_id"])
        op.create_index("ix_client_disputes_client_id", "client_disputes", ["client_id"])
        op.create_index("ix_client_disputes_booking_id", "client_disputes", ["booking_id"])

    if "sms_quick_tools" not in existing_tables:
        op.create_table(
            "sms_quick_tools",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("slot_index", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(length=8), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_sms_quick_tools_id", "sms_quick_tools", ["id"])
        op.create_index("ix_sms_quick_tools_tenant_id", "sms_quick_tools", ["tenant_id"])
        op.create_index("ix_sms_quick_tools_user_id", "sms_quick_tools", ["user_id"])

    if "gdpr_consents" not in existing_tables:
        op.create_table(
            "gdpr_consents",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "client_id",
                sa.Integer(),
                sa.ForeignKey("clients.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("consent_type", sa.String(), nullable=False, server_default="gdpr"),
            sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("ip_address", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_gdpr_consents_id", "gdpr_consents", ["id"])
        op.create_index("ix_gdpr_consents_tenant_id", "gdpr_consents", ["tenant_id"])
        op.create_index("ix_gdpr_consents_client_id", "gdpr_consents", ["client_id"])


def downgrade() -> None:
    existing_tables = _existing_tables()
    for table_name in (
        "sms_quick_tools",
        "client_disputes",
        "tenant_websites",
        "gdpr_consents",
    ):
        if table_name in existing_tables:
            op.drop_table(table_name)
