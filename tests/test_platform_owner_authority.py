"""Security and persistence tests for platform-owner authority."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.api.deps import get_current_user, require_platform_owner
from app.core.config import settings
from app.core.security import create_access_token
from app.db.database import Base
from app.models.audit import AuditLog
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth.platform_owner_authority import (
    PlatformOwnerAuthorityError,
    get_platform_owner_status,
    preview_platform_owner_change,
    set_platform_owner,
)
from scripts import manage_platform_owner


def _make_factory(path: Path):
    engine = create_engine(
        f"sqlite:///{path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _seed(factory, *, owners: int = 0):
    with factory() as session:
        tenant = Tenant(name="Authority Synthetic", subdomain="authority-synthetic")
        session.add(tenant)
        session.flush()
        users = []
        for index in range(max(owners, 1)):
            users.append(
                User(
                    tenant_id=tenant.id,
                    login=f"synthetic-{index}",
                    password_hash="unused-test-hash",
                    role="owner" if index == 0 else "manager",
                    is_active=True,
                    is_platform_owner=index < owners,
                )
            )
        session.add_all(users)
        session.commit()
        return tenant.id, [user.id for user in users]


def test_capability_defaults_false_and_persists_across_sessions(tmp_path):
    engine, factory = _make_factory(tmp_path / "persistence.db")
    tenant_id, (user_id,) = _seed(factory)
    with factory() as session:
        assert get_platform_owner_status(session, tenant_id=tenant_id, user_id=user_id).is_platform_owner is False
    with factory() as session:
        set_platform_owner(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            grant=True,
            reason_code="initial_provisioning",
        )
    with factory() as session:
        assert get_platform_owner_status(session, tenant_id=tenant_id, user_id=user_id).is_platform_owner is True
    engine.dispose()


@pytest.mark.asyncio
async def test_dependency_requires_exact_active_persisted_capability():
    for role in ("owner", "admin", "manager"):
        ordinary = User(id=1, tenant_id=1, login=role, role=role, is_active=True, is_platform_owner=False)
        with pytest.raises(HTTPException) as denied:
            await require_platform_owner(current_user=ordinary)
        assert denied.value.status_code == 403

    dynamic = User(id=2, tenant_id=1, login="dynamic", role="owner", is_active=True)
    dynamic.is_superuser = True
    with pytest.raises(HTTPException):
        await require_platform_owner(current_user=dynamic)

    allowed = User(id=3, tenant_id=1, login="allowed", role="manager", is_active=True, is_platform_owner=True)
    assert await require_platform_owner(current_user=allowed) is allowed
    allowed.is_active = False
    with pytest.raises(HTTPException):
        await require_platform_owner(current_user=allowed)


def test_numeric_composite_identity_status_preview_and_not_found(tmp_path):
    engine, factory = _make_factory(tmp_path / "identity.db")
    tenant_id, (user_id,) = _seed(factory)
    with factory() as session:
        preview = preview_platform_owner_change(
            session, tenant_id=tenant_id, user_id=user_id, grant=True
        )
        assert preview.changed is True and preview.applied is False
    with factory() as session:
        with pytest.raises(PlatformOwnerAuthorityError, match="target_not_found"):
            get_platform_owner_status(session, tenant_id=tenant_id + 1, user_id=user_id)
    engine.dispose()


@pytest.mark.parametrize("invalid_id", [0, -1, 2_147_483_648])
def test_invalid_or_overflow_identity_is_rejected(tmp_path, invalid_id):
    engine, factory = _make_factory(tmp_path / f"invalid-{invalid_id}.db")
    tenant_id, (user_id,) = _seed(factory)
    with factory() as session:
        with pytest.raises(PlatformOwnerAuthorityError, match="invalid_identity"):
            get_platform_owner_status(
                session,
                tenant_id=invalid_id if invalid_id != user_id else tenant_id,
                user_id=user_id,
            )
    engine.dispose()


def test_postgresql_mutation_path_requests_transaction_advisory_lock():
    session = MagicMock()
    session.in_transaction.return_value = False
    session.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql")
    )
    session.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = None
    with pytest.raises(PlatformOwnerAuthorityError, match="target_not_found"):
        set_platform_owner(
            session,
            tenant_id=1,
            user_id=1,
            grant=True,
            reason_code="initial_provisioning",
        )
    statement = str(session.execute.call_args.args[0])
    assert "pg_advisory_xact_lock" in statement


def test_grant_revoke_are_idempotent_and_canonically_audited(tmp_path):
    engine, factory = _make_factory(tmp_path / "audit.db")
    tenant_id, (user_id,) = _seed(factory)
    with factory() as session:
        first = set_platform_owner(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            grant=True,
            reason_code="operator_change",
            change_ref="SEC-01/review",
        )
    with factory() as session:
        second = set_platform_owner(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            grant=True,
            reason_code="operator_change",
        )
        audits = session.query(AuditLog).all()
        assert first.changed is True and second.changed is False
        assert len(audits) == 1
        assert audits[0].user_id is None
        assert audits[0].action == "platform_owner.granted"
        assert audits[0].target_type == "user" and audits[0].target_id == user_id
        assert audits[0].details == json.dumps(
            {
                "change_ref": "SEC-01/review",
                "new_value": True,
                "previous_value": False,
                "reason_code": "operator_change",
                "source": "offline_cli",
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    # Add a second owner so the first can be revoked, then prove repeat revoke
    # is a no-op without a duplicate audit.
    with factory() as session:
        tenant = session.get(Tenant, tenant_id)
        other = User(
            tenant_id=tenant.id,
            login="second-owner",
            password_hash="unused",
            role="staff",
            is_active=True,
            is_platform_owner=True,
        )
        session.add(other)
        session.commit()
    with factory() as session:
        assert set_platform_owner(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            grant=False,
            reason_code="access_review",
        ).changed is True
    with factory() as session:
        assert set_platform_owner(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            grant=False,
            reason_code="access_review",
        ).changed is False
        assert session.query(AuditLog).count() == 2
    engine.dispose()


def test_audit_failure_rolls_back_capability(tmp_path):
    engine, factory = _make_factory(tmp_path / "rollback.db")
    tenant_id, (user_id,) = _seed(factory)

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("synthetic audit insertion failure")

    event.listen(AuditLog, "before_insert", fail_audit)
    try:
        with factory() as session:
            with pytest.raises(PlatformOwnerAuthorityError, match="transaction_failed"):
                set_platform_owner(
                    session,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    grant=True,
                    reason_code="rollback",
                )
    finally:
        event.remove(AuditLog, "before_insert", fail_audit)
    with factory() as session:
        assert session.get(User, user_id).is_platform_owner is False
        assert session.query(AuditLog).count() == 0
    engine.dispose()


def test_last_active_owner_guard_allows_inactive_flag_cleanup(tmp_path):
    engine, factory = _make_factory(tmp_path / "last-owner.db")
    tenant_id, (user_id,) = _seed(factory, owners=1)
    with factory() as session:
        with pytest.raises(PlatformOwnerAuthorityError, match="last_active_platform_owner"):
            set_platform_owner(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                grant=False,
                reason_code="access_review",
            )
    with factory() as session:
        user = session.get(User, user_id)
        user.is_active = False
        session.commit()
    with factory() as session:
        result = set_platform_owner(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            grant=False,
            reason_code="access_review",
        )
        assert result.changed is True
    engine.dispose()


def test_real_threaded_sqlite_concurrent_grant_and_revoke(tmp_path):
    engine, factory = _make_factory(tmp_path / "concurrency.db")
    tenant_id, user_ids = _seed(factory, owners=0)
    user_id = user_ids[0]

    def change(user, grant):
        with factory() as session:
            try:
                return set_platform_owner(
                    session,
                    tenant_id=tenant_id,
                    user_id=user,
                    grant=grant,
                    reason_code="operator_change",
                ).changed
            except PlatformOwnerAuthorityError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        grants = list(pool.map(lambda _: change(user_id, True), range(2)))
    assert sorted(grants) == [False, True]
    with factory() as session:
        second = User(
            tenant_id=tenant_id,
            login="concurrent-second",
            password_hash="unused",
            role="admin",
            is_active=True,
            is_platform_owner=True,
        )
        session.add(second)
        session.commit()
        second_id = second.id
    with ThreadPoolExecutor(max_workers=2) as pool:
        revokes = list(pool.map(lambda uid: change(uid, False), [user_id, second_id]))
    assert sorted((str(item) for item in revokes)) == ["True", "last_active_platform_owner"]
    with factory() as session:
        assert session.query(User).filter(User.is_active.is_(True), User.is_platform_owner.is_(True)).count() == 1
        assert session.query(AuditLog).filter(AuditLog.action == "platform_owner.revoked").count() == 1
    engine.dispose()


@pytest.mark.skipif(
    not os.environ.get("WP_SEC_01_TEST_POSTGRES_URL"),
    reason="requires an explicitly approved disposable PostgreSQL database",
)
def test_real_postgresql_concurrent_authority_serialization():
    """Prove PostgreSQL advisory locking serializes real authority writes."""
    engine = create_engine(
        os.environ["WP_SEC_01_TEST_POSTGRES_URL"],
        pool_pre_ping=True,
        hide_parameters=True,
    )
    lock_statement_count = 0
    count_guard = Lock()

    @event.listens_for(engine, "before_cursor_execute")
    def record_advisory_lock(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal lock_statement_count
        if "pg_advisory_xact_lock" in statement:
            with count_guard:
                lock_statement_count += 1

    schema_statements = (
        """
        CREATE TABLE tenants (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            subdomain VARCHAR NOT NULL UNIQUE
        )
        """,
        "CREATE TABLE providers (id INTEGER PRIMARY KEY)",
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            login VARCHAR NOT NULL,
            password_hash VARCHAR NOT NULL,
            role VARCHAR NOT NULL,
            email VARCHAR,
            google_sub VARCHAR,
            chatwoot_user_id INTEGER,
            first_name VARCHAR,
            last_name VARCHAR,
            avatar_url VARCHAR,
            is_active BOOLEAN NOT NULL,
            is_platform_owner BOOLEAN NOT NULL DEFAULT FALSE,
            provider_id INTEGER REFERENCES providers(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
            CONSTRAINT uq_users_tenant_login UNIQUE (tenant_id, login)
        )
        """,
        "CREATE INDEX ix_users_platform_owner_active ON users (is_platform_owner, is_active)",
        """
        CREATE TABLE audit_logs (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id),
            action VARCHAR NOT NULL,
            target_type VARCHAR,
            target_id INTEGER,
            details TEXT,
            timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL
        )
        """,
    )
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def change(user_id: int, grant: bool):
        with factory() as session:
            try:
                return set_platform_owner(
                    session,
                    tenant_id=1,
                    user_id=user_id,
                    grant=grant,
                    reason_code="operator_change",
                    change_ref="WP-SEC-01/postgresql",
                ).changed
            except PlatformOwnerAuthorityError as exc:
                return exc.code

    try:
        with engine.begin() as connection:
            for statement in schema_statements:
                connection.execute(text(statement))
            connection.execute(
                text(
                    "INSERT INTO tenants (id, name, subdomain) "
                    "VALUES (1, 'PostgreSQL Synthetic', 'wp-sec-01-postgresql')"
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO users (
                        id, tenant_id, login, password_hash, role, is_active,
                        is_platform_owner, created_at, updated_at
                    ) VALUES
                        (1, 1, 'synthetic-owner-one', 'unused', 'manager', TRUE, FALSE, NOW(), NOW()),
                        (2, 1, 'synthetic-owner-two', 'unused', 'manager', TRUE, FALSE, NOW(), NOW())
                    """
                )
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            grants = list(pool.map(lambda _: change(1, True), range(2)))
        assert grants.count(True) == 1
        assert grants.count(False) == 1

        assert change(2, True) is True

        with ThreadPoolExecutor(max_workers=2) as pool:
            revokes = list(pool.map(lambda user_id: change(user_id, False), [1, 2]))
        assert sum(result is True for result in revokes) == 1
        assert revokes.count("last_active_platform_owner") == 1

        with factory() as session:
            assert (
                session.query(User)
                .filter(User.is_active.is_(True), User.is_platform_owner.is_(True))
                .count()
                == 1
            )
            assert (
                session.query(AuditLog)
                .filter(AuditLog.action == "platform_owner.granted")
                .count()
                == 2
            )
            assert (
                session.query(AuditLog)
                .filter(AuditLog.action == "platform_owner.revoked")
                .count()
                == 1
            )
        assert lock_statement_count == 5
    finally:
        event.remove(engine, "before_cursor_execute", record_advisory_lock)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DROP TABLE IF EXISTS audit_logs, users, providers, tenants CASCADE"
                )
            )
        engine.dispose()


def test_cli_dry_run_confirmation_and_non_disclosing_output(tmp_path, monkeypatch, capsys):
    engine, factory = _make_factory(tmp_path / "cli.db")
    tenant_id, (user_id,) = _seed(factory)
    monkeypatch.setattr(manage_platform_owner, "SessionLocal", factory)

    assert manage_platform_owner.main([
        "grant", "--tenant-id", str(tenant_id), "--user-id", str(user_id),
        "--reason-code", "initial_provisioning",
    ]) == 0
    dry = json.loads(capsys.readouterr().out)
    assert dry["applied"] is False and dry["changed"] is True
    with factory() as session:
        assert session.query(AuditLog).count() == 0

    assert manage_platform_owner.main([
        "grant", "--tenant-id", str(tenant_id), "--user-id", str(user_id),
        "--reason-code", "initial_provisioning", "--apply", "--confirm", "wrong",
    ]) == 2
    captured = capsys.readouterr()
    assert "confirmation_mismatch" in captured.err

    assert manage_platform_owner.main([
        "grant", "--tenant-id", str(tenant_id), "--user-id", str(user_id),
        "--reason-code", "initial_provisioning", "--apply", "--confirm",
        f"GRANT PLATFORM OWNER {tenant_id}:{user_id}",
    ]) == 0
    output = capsys.readouterr()
    combined = output.out + output.err
    assert "synthetic-0" not in combined
    assert "sqlite:" not in combined
    assert "unused-test-hash" not in combined
    assert json.loads(output.out)["is_platform_owner"] is True
    engine.dispose()


@pytest.mark.asyncio
async def test_local_bypass_requires_active_persisted_platform_owner(tmp_path, monkeypatch):
    engine, factory = _make_factory(tmp_path / "bypass.db")
    tenant_id, (user_id,) = _seed(factory)
    monkeypatch.setattr(settings, "LOCAL_AUTH_BYPASS", True)
    with factory() as session:
        tenant = session.get(Tenant, tenant_id)
        with pytest.raises(HTTPException) as unavailable:
            await get_current_user(
                x_token="local-development-bypass", tenant=tenant, db=session
            )
        assert unavailable.value.status_code == 503
    with factory() as session:
        set_platform_owner(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            grant=True,
            reason_code="initial_provisioning",
        )
    with factory() as session:
        tenant = session.get(Tenant, tenant_id)
        selected = await get_current_user(
            x_token="local-development-bypass", tenant=tenant, db=session
        )
        assert selected.id == user_id
    with factory() as session:
        user = session.get(User, user_id)
        user.is_active = False
        session.commit()
    with factory() as session:
        tenant = session.get(Tenant, tenant_id)
        with pytest.raises(HTTPException) as inactive:
            await get_current_user(
                x_token="local-development-bypass", tenant=tenant, db=session
            )
        assert inactive.value.status_code == 503
    engine.dispose()


def test_role_claim_cross_tenant_and_revocation_take_effect_immediately(client, db_session):
    tenant_a = Tenant(name="Authority Tenant A", subdomain="authority-a")
    tenant_b = Tenant(name="Authority Tenant B", subdomain="authority-b")
    db_session.add_all([tenant_a, tenant_b])
    db_session.flush()
    target = User(
        tenant_id=tenant_a.id,
        login="target-synthetic",
        password_hash="unused",
        role="manager",
        is_active=True,
        is_platform_owner=True,
    )
    recovery = User(
        tenant_id=tenant_b.id,
        login="recovery-synthetic",
        password_hash="unused",
        role="staff",
        is_active=True,
        is_platform_owner=True,
    )
    db_session.add_all([target, recovery])
    db_session.commit()
    token = create_access_token(
        {"sub": str(target.id), "tenant_id": tenant_a.id, "role": "owner"}
    )
    headers = {"X-Tenant": tenant_a.subdomain, "X-Token": token}
    assert client.get("/api/admin/codex/projects", headers=headers).status_code == 200
    assert client.get(
        "/api/admin/codex/projects",
        headers={"X-Tenant": tenant_b.subdomain, "X-Token": token},
    ).status_code == 401

    target.is_platform_owner = False
    db_session.commit()
    assert client.get("/api/admin/codex/projects", headers=headers).status_code == 403

    target.is_platform_owner = True
    target.is_active = False
    db_session.commit()
    assert client.get("/api/admin/codex/projects", headers=headers).status_code == 403


def test_child_cleanup_helper_uses_db_and_mounted_control_centre(client, db_session):
    """Non-recursive child target that opens both application database paths."""
    tenant = Tenant(name="Child Cleanup Synthetic", subdomain="child-cleanup-synthetic")
    db_session.add(tenant)
    db_session.flush()
    owner = User(
        tenant_id=tenant.id,
        login="child-cleanup-owner",
        password_hash="unused",
        role="manager",
        is_active=True,
        is_platform_owner=True,
    )
    db_session.add(owner)
    db_session.commit()
    token = create_access_token({"sub": str(owner.id)})

    response = client.get(
        "/api/admin/codex/projects",
        headers={"X-Tenant": tenant.subdomain, "X-Token": token},
    )

    assert response.status_code == 200


def test_default_runtime_database_sentinels_unchanged(default_database_snapshot):
    before, snapshot = default_database_snapshot
    assert {path: snapshot(path) for path in before} == before


def test_child_pytest_run_removes_process_unique_database_directory(
    tmp_path, default_database_snapshot
):
    child_temp_root = tmp_path / "child-process-temp"
    child_temp_root.mkdir()
    environment = os.environ.copy()
    environment["TEMP"] = str(child_temp_root)
    environment["TMP"] = str(child_temp_root)
    sentinel_paths, snapshot = default_database_snapshot
    before_child = {path: snapshot(path) for path in sentinel_paths}

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_platform_owner_authority.py::test_child_cleanup_helper_uses_db_and_mounted_control_centre",
            "-q",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert completed.returncode == 0, (
        "isolated child pytest run failed\n"
        f"stdout:\n{completed.stdout[-2000:]}\n"
        f"stderr:\n{completed.stderr[-2000:]}"
    )
    assert list(child_temp_root.glob("fastapi-bookings-pytest-*")) == []
    assert list(child_temp_root.glob("codex-control-centre-pytest-*")) == []
    assert {path: snapshot(path) for path in sentinel_paths} == before_child
