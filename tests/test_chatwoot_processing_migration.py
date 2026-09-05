"""Static and structural safeguards for the Package C Alembic revision."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
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
    / "f6a7b8c9d0e1_add_chatwoot_automation_gate.py"
)
TEST_DATABASE_ENV = "CHATWOOT_INGRESS_TEST_DATABASE_URL"


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "chatwoot_processing_migration", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_descends_from_package_b_and_leaves_one_head():
    migration = _load_migration()
    assert migration.revision == "f6a7b8c9d0e1"
    assert migration.down_revision == "a4c8e2f19b70"

    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["f6a7b8c9d0e1"]


def test_migration_source_defaults_false_and_never_rewrites_rows():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'sa.Column(\n            "automation_enabled"' in source
    assert 'server_default=sa.text("false")' in source
    assert "nullable=False" in source
    assert "UPDATE " not in source
    assert "app.core.config" not in source
    assert "settings" not in source
    assert "LOCK TABLE sms_chatwoot_bindings IN ACCESS EXCLUSIVE MODE" in source


class _ScalarResult:
    def __init__(self, value: bool):
        self.value = value

    def scalar_one(self) -> bool:
        return self.value


class _Bind:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.statements: list[str] = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return _ScalarResult(self.enabled)


def test_downgrade_guard_reads_only_the_boolean_configuration_state():
    migration = _load_migration()
    bind = _Bind(enabled=True)
    assert migration._automation_is_enabled(bind) is True
    rendered = " ".join(bind.statements).lower()
    assert "automation_enabled" in rendered
    assert "tenant_id" not in rendered
    assert "customer" not in rendered
    assert "message" not in rendered


def test_downgrade_refuses_to_discard_enabled_configuration(monkeypatch):
    migration = _load_migration()
    bind = _Bind(enabled=True)
    monkeypatch.setattr(migration, "_online_postgresql_bind", lambda: bind)
    monkeypatch.setattr(migration, "_assert_downgrade_shape", lambda _bind: None)
    monkeypatch.setattr(migration.op, "execute", lambda _statement: None)
    with pytest.raises(RuntimeError, match="automation configuration"):
        migration.downgrade()


def _disposable_postgres_url() -> str:
    database_url = os.environ.get(TEST_DATABASE_ENV)
    if not database_url:
        pytest.skip(
            f"set {TEST_DATABASE_ENV} to an explicit local disposable PostgreSQL test database"
        )
    parsed = urlsplit(database_url)
    database_name = parsed.path.lstrip("/").lower()
    if parsed.scheme not in {
        "postgresql",
        "postgresql+psycopg",
        "postgresql+psycopg2",
    }:
        pytest.fail(f"{TEST_DATABASE_ENV} must use PostgreSQL")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail(f"{TEST_DATABASE_ENV} must target localhost")
    if "test" not in database_name:
        pytest.fail(f"{TEST_DATABASE_ENV} database name must contain 'test'")
    return database_url


def _command_config(tmp_path: Path, database_url: str) -> Config:
    script_path = tmp_path / "alembic"
    versions_path = script_path / "versions"
    versions_path.mkdir(parents=True)
    shutil.copy2(MIGRATION_PATH, versions_path / MIGRATION_PATH.name)
    (versions_path / "a4c8e2f19b70_package_b_base.py").write_text(
        """
revision = "a4c8e2f19b70"
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


def _create_package_b_binding_table(connection) -> None:
    metadata = sa.MetaData()
    sa.Table(
        "sms_chatwoot_bindings",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("provider_id", sa.Integer, nullable=False),
        sa.Column("connection_id", sa.Integer, nullable=True),
        sa.Column("chatwoot_inbox_id", sa.BigInteger, nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=True),
        sa.Column("ingress_enabled", sa.Boolean, nullable=False),
    )
    metadata.create_all(connection)


def _cleanup_disposable_schema(engine) -> None:
    with engine.begin() as connection:
        connection.execute(sa.text("DROP TABLE IF EXISTS sms_chatwoot_bindings"))
        connection.execute(sa.text("DROP TABLE IF EXISTS alembic_version"))


def test_postgresql_rehearsal_preserves_package_b_rows_without_rewrite(tmp_path):
    database_url = _disposable_postgres_url()
    engine = sa.create_engine(database_url)
    created_schema = False
    try:
        with engine.begin() as connection:
            if sa.inspect(connection).get_table_names():
                pytest.fail(f"{TEST_DATABASE_ENV} must be an empty disposable database")
            _create_package_b_binding_table(connection)
            created_schema = True
            connection.execute(
                sa.text(
                    """
                    INSERT INTO sms_chatwoot_bindings
                      (id, tenant_id, provider_id, connection_id,
                       chatwoot_inbox_id, is_enabled, channel, ingress_enabled)
                    VALUES (1, 11, 12, 13, 14, FALSE, 'web_widget', TRUE)
                    """
                )
            )
            before = connection.execute(
                sa.text(
                    """
                    SELECT ctid::text AS tuple_id, id, tenant_id, provider_id,
                           connection_id, chatwoot_inbox_id, is_enabled,
                           channel, ingress_enabled
                    FROM sms_chatwoot_bindings WHERE id = 1
                    """
                )
            ).mappings().one()

        config = _command_config(tmp_path, database_url)
        command.stamp(config, "a4c8e2f19b70")
        command.upgrade(config, "f6a7b8c9d0e1")

        with engine.connect() as connection:
            after = connection.execute(
                sa.text(
                    """
                    SELECT ctid::text AS tuple_id, id, tenant_id, provider_id,
                           connection_id, chatwoot_inbox_id, is_enabled,
                           channel, ingress_enabled, automation_enabled
                    FROM sms_chatwoot_bindings WHERE id = 1
                    """
                )
            ).mappings().one()
            assert dict(after) == {
                **dict(before),
                "automation_enabled": False,
            }
            assert after["tuple_id"] == before["tuple_id"]

        command.downgrade(config, "a4c8e2f19b70")
        with engine.connect() as connection:
            columns = {
                column["name"]
                for column in sa.inspect(connection).get_columns(
                    "sms_chatwoot_bindings"
                )
            }
            assert "automation_enabled" not in columns
            restored = connection.execute(
                sa.text(
                    """
                    SELECT ctid::text AS tuple_id, id, tenant_id, provider_id,
                           connection_id, chatwoot_inbox_id, is_enabled,
                           channel, ingress_enabled
                    FROM sms_chatwoot_bindings WHERE id = 1
                    """
                )
            ).mappings().one()
            assert dict(restored) == dict(before)
    finally:
        if created_schema:
            _cleanup_disposable_schema(engine)
        engine.dispose()
