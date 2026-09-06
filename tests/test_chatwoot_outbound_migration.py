"""Static and guarded-database checks for the Package D Alembic revision."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
import sqlalchemy as sa
from alembic.script import ScriptDirectory
from alembic.config import Config
from alembic import command


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "d1e2f3a4b5c6_add_chatwoot_outbound_intents.py"
)
TEST_DATABASE_ENV = "CHATWOOT_INGRESS_TEST_DATABASE_URL"


def _load_migration():
    spec = importlib.util.spec_from_file_location("chatwoot_outbound_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_descends_from_package_c_and_leaves_one_head():
    migration = _load_migration()
    assert migration.revision == "d1e2f3a4b5c6"
    assert migration.down_revision == "f6a7b8c9d0e1"
    script = ScriptDirectory.from_config(Config(str(Path(__file__).parents[1] / "alembic.ini")))
    assert script.get_heads() == ["d1e2f3a4b5c6"]


def test_migration_is_postgresql_only_default_disabled_and_never_rewrites_rows():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "requires PostgreSQL" in source
    assert 'server_default=sa.text("false")' in source
    assert "chatwoot_outbound_intents" in source
    assert "UPDATE " not in source
    assert "app.core.config" not in source
    assert "settings" not in source
    assert "api_token_ciphertext IS NOT NULL" in source


class _Scalar:
    def scalar_one(self):
        return True


class _Bind:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self):
        self.statements: list[str] = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return _Scalar()


def test_downgrade_guard_reads_structural_presence_only():
    migration = _load_migration()
    bind = _Bind()
    assert migration._outbound_configuration_or_intent_exists(bind) is True
    rendered = " ".join(bind.statements).lower()
    assert "api_token_ciphertext is not null" in rendered
    assert "chatwoot_outbound_intents" in rendered
    assert "message_id" not in rendered
    assert "body" not in rendered


def _disposable_postgres_url() -> str:
    database_url = os.environ.get(TEST_DATABASE_ENV)
    if not database_url:
        pytest.skip(f"set {TEST_DATABASE_ENV} to an explicit local disposable PostgreSQL test database")
    parsed = urlsplit(database_url)
    name = parsed.path.lstrip("/").lower()
    if parsed.scheme not in {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"}:
        pytest.fail(f"{TEST_DATABASE_ENV} must use PostgreSQL")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or "test" not in name:
        pytest.fail(f"{TEST_DATABASE_ENV} must target an explicit local test database")
    return database_url


def test_disposable_postgresql_url_guard_is_explicit():
    """A real rehearsal is enabled only by an explicitly supplied local test URL."""
    database_url = os.environ.get(TEST_DATABASE_ENV)
    if database_url:
        assert _disposable_postgres_url() == database_url
    else:
        with pytest.raises(pytest.skip.Exception):
            _disposable_postgres_url()


def _migration_config(tmp_path: Path, database_url: str) -> Config:
    script_path = tmp_path / "alembic"
    versions = script_path / "versions"
    versions.mkdir(parents=True)
    shutil.copy2(MIGRATION_PATH, versions / MIGRATION_PATH.name)
    (versions / "f6a7b8c9d0e1_package_c_base.py").write_text(
        """revision = 'f6a7b8c9d0e1'\ndown_revision = None\nbranch_labels = None\ndepends_on = None\ndef upgrade(): pass\ndef downgrade(): pass\n""",
        encoding="utf-8",
    )
    (script_path / "env.py").write_text(
        """from alembic import context\nfrom sqlalchemy import engine_from_config, pool\nconfig = context.config\nengine = engine_from_config(config.get_section(config.config_ini_section), prefix='sqlalchemy.', poolclass=pool.NullPool)\nwith engine.connect() as connection:\n    context.configure(connection=connection)\n    with context.begin_transaction():\n        context.run_migrations()\n""",
        encoding="utf-8",
    )
    config = Config()
    config.set_main_option("script_location", str(script_path).replace("%", "%%"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _create_package_c_shape(connection) -> None:
    metadata = sa.MetaData()
    sa.Table("tenants", metadata, sa.Column("id", sa.Integer, primary_key=True))
    sa.Table("providers", metadata, sa.Column("id", sa.Integer, primary_key=True))
    sa.Table(
        "chatwoot_connections", metadata,
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("tenant_id", sa.Integer),
        sa.Column("instance_origin", sa.String), sa.Column("chatwoot_account_id", sa.BigInteger),
        sa.Column("signing_secret_ciphertext", sa.String), sa.Column("enabled", sa.Boolean),
    )
    sa.Table(
        "sms_chatwoot_bindings", metadata,
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("tenant_id", sa.Integer),
        sa.Column("provider_id", sa.Integer), sa.Column("connection_id", sa.Integer),
        sa.Column("automation_enabled", sa.Boolean),
    )
    sa.Table("sms_conversations", metadata, sa.Column("id", sa.Integer, primary_key=True))
    sa.Table("sms_messages", metadata, sa.Column("id", sa.Integer, primary_key=True))
    metadata.create_all(connection)


def test_postgresql_upgrade_and_guarded_downgrade_rehearsal(tmp_path):
    database_url = _disposable_postgres_url()
    engine = sa.create_engine(database_url)
    created = False
    tables = (
        "chatwoot_outbound_intents", "sms_messages", "sms_conversations",
        "sms_chatwoot_bindings", "chatwoot_connections", "providers", "tenants", "alembic_version",
    )
    try:
        with engine.begin() as connection:
            if sa.inspect(connection).get_table_names():
                pytest.fail(f"{TEST_DATABASE_ENV} must be an empty disposable database")
            _create_package_c_shape(connection)
            created = True
        config = _migration_config(tmp_path, database_url)
        command.stamp(config, "f6a7b8c9d0e1")
        command.upgrade(config, "d1e2f3a4b5c6")
        with engine.connect() as connection:
            columns = {column["name"] for column in sa.inspect(connection).get_columns("chatwoot_connections")}
            assert {"api_token_ciphertext", "expected_integration_sender_type", "expected_integration_sender_id", "outbound_enabled"} <= columns
            assert "chatwoot_outbound_intents" in set(sa.inspect(connection).get_table_names())
        command.downgrade(config, "f6a7b8c9d0e1")
        with engine.connect() as connection:
            assert "chatwoot_outbound_intents" not in set(sa.inspect(connection).get_table_names())
    finally:
        if created:
            with engine.begin() as connection:
                for table in tables:
                    connection.execute(sa.text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
        engine.dispose()
