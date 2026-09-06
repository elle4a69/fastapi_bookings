from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "a4c8e2f19b70_add_chatwoot_authenticated_ingress.py"
)
TEST_DATABASE_ENV = "CHATWOOT_INGRESS_TEST_DATABASE_URL"


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "chatwoot_ingress_migration", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_descends_from_current_head_and_leaves_one_head():
    migration = _load_migration()
    assert migration.revision == "a4c8e2f19b70"
    assert migration.down_revision == "d7e8f9a0b1c2"

    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["d1e2f3a4b5c6"]


def _disposable_postgres_url() -> str:
    database_url = os.environ.get(TEST_DATABASE_ENV)
    if not database_url:
        pytest.skip(
            f"set {TEST_DATABASE_ENV} to an explicit local disposable PostgreSQL test database"
        )
    parsed = urlsplit(database_url)
    database_name = parsed.path.lstrip("/").lower()
    if parsed.scheme not in {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"}:
        pytest.fail(f"{TEST_DATABASE_ENV} must use PostgreSQL")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail(f"{TEST_DATABASE_ENV} must target localhost")
    if "test" not in database_name:
        pytest.fail(f"{TEST_DATABASE_ENV} database name must contain 'test'")
    return database_url


def _create_legacy_schema(connection):
    metadata = sa.MetaData()
    sa.Table("tenants", metadata, sa.Column("id", sa.Integer, primary_key=True))
    sa.Table(
        "providers",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
    )
    sa.Table(
        "sms_chatwoot_bindings",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("provider_id", sa.Integer, nullable=False),
        sa.Column("chatwoot_account_id", sa.Integer, nullable=False),
        sa.Column("chatwoot_inbox_id", sa.Integer, nullable=False),
        sa.Column("chatwoot_base_url", sa.String, nullable=False),
        sa.Column("chatwoot_api_token", sa.String, nullable=False),
        sa.Column("webhook_secret", sa.String, nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False),
        sa.Column("channel_metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    sa.Table(
        "sms_conversations",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("chatwoot_conversation_id", sa.Integer, nullable=True),
        sa.Column("chatwoot_contact_id", sa.Integer, nullable=True),
        sa.Column("chatwoot_inbox_id", sa.Integer, nullable=True),
    )
    sa.Table(
        "sms_messages",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("conversation_id", sa.Integer, nullable=False),
        sa.Column("chatwoot_message_id", sa.Integer, nullable=True),
    )
    metadata.create_all(connection)


def _command_config(tmp_path: Path, database_url: str) -> Config:
    script_path = tmp_path / "alembic"
    versions_path = script_path / "versions"
    versions_path.mkdir(parents=True)
    shutil.copy2(MIGRATION_PATH, versions_path / MIGRATION_PATH.name)
    (versions_path / "d7e8f9a0b1c2_test_base.py").write_text(
        """
revision = "d7e8f9a0b1c2"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
""".lstrip(),
        encoding="utf-8",
    )
    (script_path / "env.py").write_text(
        """
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
connectable = engine_from_config(
    config.get_section(config.config_ini_section),
    prefix="sqlalchemy.",
    poolclass=pool.NullPool,
)
with connectable.connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
""".lstrip(),
        encoding="utf-8",
    )

    config = Config()
    config.set_main_option("script_location", str(script_path).replace("%", "%%"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _cleanup_disposable_schema(engine) -> None:
    tables = (
        "chatwoot_webhook_receipts",
        "sms_messages",
        "sms_conversations",
        "sms_chatwoot_bindings",
        "chatwoot_connections",
        "providers",
        "tenants",
        "alembic_version",
    )
    with engine.begin() as connection:
        for table_name in tables:
            connection.execute(sa.text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))


def test_postgresql_upgrade_preserves_legacy_and_downgrade_is_guarded(tmp_path):
    database_url = _disposable_postgres_url()
    engine = sa.create_engine(database_url)
    created_schema = False
    try:
        with engine.begin() as connection:
            if sa.inspect(connection).get_table_names():
                pytest.fail(f"{TEST_DATABASE_ENV} must be an empty disposable database")
            _create_legacy_schema(connection)
            created_schema = True
            connection.execute(sa.text("INSERT INTO tenants (id) VALUES (1)"))
            connection.execute(
                sa.text("INSERT INTO providers (id, tenant_id) VALUES (1, 1)")
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO sms_chatwoot_bindings
                      (id, tenant_id, provider_id, chatwoot_account_id,
                       chatwoot_inbox_id, chatwoot_base_url, chatwoot_api_token,
                       webhook_secret, is_enabled, channel_metadata, created_at, updated_at)
                    VALUES
                      (1, 1, 1, 100, 200, 'https://legacy.example.test',
                       'legacy-token-ciphertext', 'legacy-secret-ciphertext',
                       TRUE, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                )
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO sms_conversations
                      (id, tenant_id, chatwoot_conversation_id,
                       chatwoot_contact_id, chatwoot_inbox_id)
                    VALUES (1, 1, 400, 500, 200)
                    """
                )
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO sms_messages
                      (id, tenant_id, conversation_id, chatwoot_message_id)
                    VALUES (1, 1, 1, 600), (2, 1, 1, 600)
                    """
                )
            )

        config = _command_config(tmp_path, database_url)
        command.stamp(config, "d7e8f9a0b1c2")
        command.upgrade(config, "a4c8e2f19b70")

        with engine.connect() as connection:
            legacy = connection.execute(
                sa.text(
                    """
                    SELECT chatwoot_account_id, chatwoot_inbox_id,
                           chatwoot_base_url, chatwoot_api_token, webhook_secret,
                           is_enabled, connection_id, channel, ingress_enabled
                    FROM sms_chatwoot_bindings WHERE id = 1
                    """
                )
            ).mappings().one()
            assert dict(legacy) == {
                "chatwoot_account_id": 100,
                "chatwoot_inbox_id": 200,
                "chatwoot_base_url": "https://legacy.example.test",
                "chatwoot_api_token": "legacy-token-ciphertext",
                "webhook_secret": "legacy-secret-ciphertext",
                "is_enabled": True,
                "connection_id": None,
                "channel": None,
                "ingress_enabled": False,
            }
            assert connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM sms_messages WHERE chatwoot_message_id = 600"
                )
            ).scalar_one() == 2

        command.downgrade(config, "d7e8f9a0b1c2")
        with engine.connect() as connection:
            restored = connection.execute(
                sa.text(
                    """
                    SELECT chatwoot_account_id, chatwoot_inbox_id,
                           chatwoot_base_url, chatwoot_api_token, webhook_secret,
                           is_enabled
                    FROM sms_chatwoot_bindings WHERE id = 1
                    """
                )
            ).mappings().one()
            assert dict(restored) == {
                "chatwoot_account_id": 100,
                "chatwoot_inbox_id": 200,
                "chatwoot_base_url": "https://legacy.example.test",
                "chatwoot_api_token": "legacy-token-ciphertext",
                "webhook_secret": "legacy-secret-ciphertext",
                "is_enabled": True,
            }

        command.upgrade(config, "a4c8e2f19b70")
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO chatwoot_connections
                      (public_id, tenant_id, instance_origin, chatwoot_account_id,
                       enabled, created_at, updated_at)
                    VALUES
                      ('12345678-1234-4234-9234-123456789abc', 1,
                       'https://new.example.test', 300, FALSE,
                       CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                )
            )
        with pytest.raises(RuntimeError, match="Package B data"):
            command.downgrade(config, "d7e8f9a0b1c2")
    finally:
        if created_schema:
            _cleanup_disposable_schema(engine)
        engine.dispose()


def test_migration_source_has_no_runtime_settings_or_legacy_update():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "app.core.config" not in source
    assert "settings" not in source
    assert "UPDATE sms_chatwoot_bindings" not in source
    assert "UPDATE sms_conversations" not in source
    assert "UPDATE sms_messages" not in source


class _ScalarResult:
    def __init__(self, value: bool):
        self.value = value

    def scalar_one(self) -> bool:
        return self.value


class _SequenceBind:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self, values: tuple[bool, ...]):
        self._values = iter(values)
        self.statements: list[str] = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return _ScalarResult(next(self._values))


def test_preflight_fails_without_selecting_identifiers_or_content():
    migration = _load_migration()
    bind = _SequenceBind((False, True))

    with pytest.raises(RuntimeError, match="non-positive remote identifiers"):
        migration._preflight_legacy_values(bind)

    rendered = " ".join(bind.statements).lower()
    assert "select id" not in rendered
    assert "body" not in rendered
    assert "content" not in rendered


def test_downgrade_range_guard_runs_before_bigint_narrowing():
    migration = _load_migration()
    # No nullable legacy field, then first widened column exceeds INTEGER.
    bind = _SequenceBind((False, True))
    assert migration._downgrade_values_fit_legacy_schema(bind) is False
    assert "2147483647" in bind.statements[-1]


def test_expected_shape_preflight_rejects_partial_target_before_ddl():
    migration = _load_migration()
    inspector = SimpleNamespace(
        get_table_names=lambda: [
            "sms_chatwoot_bindings",
            "sms_conversations",
            "sms_messages",
            "chatwoot_connections",
        ]
    )
    with (
        patch.object(migration.sa, "inspect", return_value=inspector),
        pytest.raises(RuntimeError, match="partial target schema"),
    ):
        migration._assert_upgrade_shape(object())
