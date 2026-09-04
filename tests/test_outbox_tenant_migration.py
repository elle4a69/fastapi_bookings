from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.dialects import postgresql


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "4c9f0a1b2d3e_normalize_outbox_tenant_id.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("outbox_tenant_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Result:
    def __init__(self, value: bool):
        self.value = value

    def scalar_one(self) -> bool:
        return self.value


class _Bind:
    def __init__(self, dialect: str = "postgresql", results: tuple[bool, ...] = ()):
        self.dialect = SimpleNamespace(name=dialect)
        self._results = iter(results)
        self.statements: list[str] = []

    def execute(self, statement):
        self.statements.append(str(statement))
        if self.statements[-1].startswith("LOCK TABLE"):
            return _Result(False)
        return _Result(next(self._results))


class _Inspector:
    default_schema_name = "public"

    def __init__(self, column_type, foreign_keys=()):
        self.column_type = column_type
        self.foreign_keys = list(foreign_keys)

    def get_columns(self, table_name):
        assert table_name == "outbox_events"
        return [{"name": "tenant_id", "type": self.column_type}]

    def get_foreign_keys(self, table_name):
        assert table_name == "outbox_events"
        return self.foreign_keys


def _exact_fk(name="fk_existing_outbox_tenant"):
    return {
        "name": name,
        "constrained_columns": ["tenant_id"],
        "referred_schema": None,
        "referred_table": "tenants",
        "referred_columns": ["id"],
        "options": {"ondelete": "CASCADE"},
    }


def _run_upgrade(migration, inspector, results=(False, False)):
    bind = _Bind(results=results)
    with (
        patch.object(migration.op, "get_bind", return_value=bind),
        patch.object(migration.sa, "inspect", return_value=inspector),
        patch.object(migration.op, "alter_column") as alter,
        patch.object(migration.op, "create_foreign_key") as create,
    ):
        migration.upgrade()
    return bind, alter, create


@pytest.mark.parametrize("column_type", [postgresql.VARCHAR(), postgresql.TEXT()])
def test_upgrade_converts_history_text_shape_and_adds_fk(column_type):
    migration = _load_migration()
    bind, alter_column, create_foreign_key = _run_upgrade(
        migration,
        _Inspector(column_type),
    )

    assert bind.statements[0] == "LOCK TABLE tenants, outbox_events IN ACCESS EXCLUSIVE MODE"
    assert "tenant_id::text" in bind.statements[1]
    assert "(event.tenant_id::text)::integer" in bind.statements[2]
    assert alter_column.call_args.kwargs["existing_nullable"] is True
    assert alter_column.call_args.kwargs["postgresql_using"] == "tenant_id::integer"
    create_foreign_key.assert_called_once_with(
        "fk_outbox_events_tenant_id",
        "outbox_events",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def test_upgrade_accepts_existing_integer_and_exact_fk_without_duplicate_ddl():
    migration = _load_migration()
    _, alter_column, create_foreign_key = _run_upgrade(
        migration,
        _Inspector(postgresql.INTEGER(), [_exact_fk()]),
    )

    alter_column.assert_not_called()
    create_foreign_key.assert_not_called()


def test_upgrade_adds_missing_fk_to_existing_integer_shape():
    migration = _load_migration()
    _, alter_column, create_foreign_key = _run_upgrade(
        migration,
        _Inspector(postgresql.INTEGER()),
    )

    alter_column.assert_not_called()
    create_foreign_key.assert_called_once()


@pytest.mark.parametrize(
    ("results", "message"),
    [
        ((True,), "invalid non-null tenant identifiers"),
        ((False, True), "orphan non-null tenant identifiers"),
    ],
)
def test_upgrade_fails_closed_before_schema_changes(results, message):
    migration = _load_migration()
    bind = _Bind(results=results)
    inspector = _Inspector(postgresql.VARCHAR())

    with (
        patch.object(migration.op, "get_bind", return_value=bind),
        patch.object(migration.sa, "inspect", return_value=inspector),
        patch.object(migration.op, "alter_column") as alter_column,
        patch.object(migration.op, "create_foreign_key") as create_foreign_key,
        pytest.raises(RuntimeError, match=message),
    ):
        migration.upgrade()

    alter_column.assert_not_called()
    create_foreign_key.assert_not_called()


@pytest.mark.parametrize(
    ("column_type", "foreign_keys", "message"),
    [
        (postgresql.UUID(), (), "column type is unexpected"),
        (
            postgresql.INTEGER(),
            ({**_exact_fk(), "referred_table": "users"},),
            "constraint is unexpected",
        ),
        (
            postgresql.INTEGER(),
            (_exact_fk("fk_one"), _exact_fk("fk_two")),
            "constraints are unexpected",
        ),
        (postgresql.VARCHAR(), (_exact_fk(),), "text tenant_id has an unexpected constraint"),
    ],
)
def test_upgrade_rejects_unexpected_column_or_constraint_shapes(
    column_type, foreign_keys, message
):
    migration = _load_migration()
    bind = _Bind()
    inspector = _Inspector(column_type, foreign_keys)

    with (
        patch.object(migration.op, "get_bind", return_value=bind),
        patch.object(migration.sa, "inspect", return_value=inspector),
        patch.object(migration.op, "alter_column") as alter_column,
        patch.object(migration.op, "create_foreign_key") as create_foreign_key,
        pytest.raises(RuntimeError, match=message),
    ):
        migration.upgrade()

    assert bind.statements == ["LOCK TABLE tenants, outbox_events IN ACCESS EXCLUSIVE MODE"]
    alter_column.assert_not_called()
    create_foreign_key.assert_not_called()


def test_upgrade_refuses_non_postgresql_without_schema_changes():
    migration = _load_migration()
    bind = _Bind(dialect="sqlite")

    with (
        patch.object(migration.op, "get_bind", return_value=bind),
        patch.object(migration.op, "alter_column") as alter_column,
        patch.object(migration.op, "create_foreign_key") as create_foreign_key,
        pytest.raises(RuntimeError, match="requires PostgreSQL"),
    ):
        migration.upgrade()

    assert bind.statements == []
    alter_column.assert_not_called()
    create_foreign_key.assert_not_called()


@pytest.mark.parametrize("operation", ["upgrade", "downgrade"])
def test_offline_mode_is_rejected_before_binding_or_emitting_sql(operation):
    migration = _load_migration()

    with (
        patch.object(migration.context, "is_offline_mode", return_value=True),
        patch.object(migration.op, "get_bind") as get_bind,
        pytest.raises(RuntimeError, match="online-only; migration DDL was not emitted"),
    ):
        getattr(migration, operation)()

    get_bind.assert_not_called()


def test_downgrade_drops_the_introspected_fk_before_converting_to_text():
    migration = _load_migration()
    bind = _Bind()
    inspector = _Inspector(postgresql.INTEGER(), [_exact_fk("fk_custom_name")])

    with (
        patch.object(migration.op, "get_bind", return_value=bind),
        patch.object(migration.sa, "inspect", return_value=inspector),
        patch.object(migration.op, "drop_constraint") as drop_constraint,
        patch.object(migration.op, "alter_column") as alter_column,
    ):
        migration.downgrade()

    drop_constraint.assert_called_once_with(
        "fk_custom_name",
        "outbox_events",
        type_="foreignkey",
    )
    assert alter_column.call_args.kwargs["postgresql_using"] == "tenant_id::text"


def test_downgrade_handles_integer_without_fk_and_does_not_invent_a_drop():
    migration = _load_migration()
    bind = _Bind()
    inspector = _Inspector(postgresql.INTEGER())

    with (
        patch.object(migration.op, "get_bind", return_value=bind),
        patch.object(migration.sa, "inspect", return_value=inspector),
        patch.object(migration.op, "drop_constraint") as drop_constraint,
        patch.object(migration.op, "alter_column") as alter_column,
    ):
        migration.downgrade()

    drop_constraint.assert_not_called()
    alter_column.assert_called_once()
