"""Regression coverage for partially pre-existing Business Assistant tables."""

import importlib.util
from pathlib import Path

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect

from app.models.tenant import Tenant
from app.models.user import User


def _load_migration(filename: str, module_name: str):
    migration_path = Path("alembic/versions") / filename
    spec = importlib.util.spec_from_file_location(module_name, migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reconciliation_migration_repairs_a_preexisting_partial_conversation_table():
    engine = create_engine("sqlite:///:memory:")
    connection = engine.connect()
    Tenant.__table__.create(connection)
    User.__table__.create(connection)
    metadata = MetaData()
    Table(
        "business_assistant_conversations",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("tenant_id", Integer, nullable=False),
        Column("user_id", Integer, nullable=False),
        Column("title", String(160), nullable=True),
    ).create(connection)
    reconciliation = _load_migration(
        "h8j0k2m4n6p8_reconcile_business_assistant_schema.py",
        "business_assistant_reconciliation_test",
    )
    op._proxy = Operations(MigrationContext.configure(connection))
    try:
        reconciliation.upgrade()
        inspector = inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("business_assistant_conversations")}
        assert {
            "status",
            "creation_request_key",
            "creation_payload_hash",
            "created_at",
            "updated_at",
        } <= columns
        unique_names = {item.get("name") for item in inspector.get_unique_constraints("business_assistant_conversations")}
        index_names = {item.get("name") for item in inspector.get_indexes("business_assistant_conversations")}
        assert "uq_business_assistant_conversation_creation_key" in unique_names | index_names
        assert "ix_business_assistant_conversations_scope_updated" in index_names
    finally:
        del op._proxy
        connection.close()
        engine.dispose()


def test_reconcile_missing_domain_tables_upgrade_and_downgrade():
    from app.models.client import Client
    from app.models.booking import Booking

    engine = create_engine("sqlite:///:memory:")
    connection = engine.connect()
    Tenant.__table__.create(connection)
    User.__table__.create(connection)
    Client.__table__.create(connection)
    Booking.__table__.create(connection)

    migration = _load_migration(
        "m3n4p5q6r7s8_reconcile_missing_domain_tables.py",
        "reconcile_missing_domain_tables_test",
    )
    op._proxy = Operations(MigrationContext.configure(connection))
    try:
        migration.upgrade()
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())

        assert {
            "tenant_websites",
            "client_disputes",
            "sms_quick_tools",
            "gdpr_consents",
        } <= tables

        tw_cols = {c["name"] for c in inspector.get_columns("tenant_websites")}
        assert {
            "id", "tenant_id", "template_id", "theme_id", "custom_colors",
            "sections_data", "is_published", "published_at", "seo_title",
            "seo_description", "created_at", "updated_at",
        } <= tw_cols

        cd_cols = {c["name"] for c in inspector.get_columns("client_disputes")}
        assert {
            "id", "tenant_id", "client_id", "booking_id", "status", "reason",
            "description", "preferred_resolution", "resolution_notes", "photos",
            "created_at", "resolved_at",
        } <= cd_cols

        sq_cols = {c["name"] for c in inspector.get_columns("sms_quick_tools")}
        assert {
            "id", "tenant_id", "user_id", "slot_index", "label", "content", "updated_at",
        } <= sq_cols

        gc_cols = {c["name"] for c in inspector.get_columns("gdpr_consents")}
        assert {
            "id", "tenant_id", "client_id", "consent_type", "is_approved",
            "ip_address", "created_at",
        } <= gc_cols

        # Test safe downgrade
        migration.downgrade()
        inspector_post_down = inspect(connection)
        remaining_tables = set(inspector_post_down.get_table_names())
        assert not {
            "tenant_websites",
            "client_disputes",
            "sms_quick_tools",
            "gdpr_consents",
        }.intersection(remaining_tables)
    finally:
        del op._proxy
        connection.close()
        engine.dispose()


def test_reconcile_missing_domain_tables_idempotent_when_preexisting():
    from app.db.database import Base
    import app.models  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    connection = engine.connect()
    # Pre-create all models (simulating create_all / pre-existing tables)
    Base.metadata.create_all(connection)

    migration = _load_migration(
        "m3n4p5q6r7s8_reconcile_missing_domain_tables.py",
        "reconcile_missing_domain_tables_idempotency_test",
    )
    op._proxy = Operations(MigrationContext.configure(connection))
    try:
        # Upgrade should be cleanly idempotent
        migration.upgrade()
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        assert {
            "tenant_websites",
            "client_disputes",
            "sms_quick_tools",
            "gdpr_consents",
        } <= tables
    finally:
        del op._proxy
        connection.close()
        engine.dispose()

