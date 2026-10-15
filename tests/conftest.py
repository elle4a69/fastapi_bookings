"""Conftest file for setting up pytest fixtures and overriding app dependencies."""

import os
import hashlib
from pathlib import Path
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading

# Force OTel SDK off before ANY app module is imported.
# Uses a hard assignment so shell env overrides are also suppressed.
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-long-strictly-for-tests")
os.environ["CHATWOOT_WEBHOOK_SECRET"] = ""

# Select process-unique file-backed databases before either application is
# imported.  This prevents test collection and app lifespans from opening the
# repository's runtime databases.
_TEST_DATABASE_DIR = Path(tempfile.mkdtemp(prefix="fastapi-bookings-pytest-"))
_APP_TEST_DATABASE = _TEST_DATABASE_DIR / "application.db"
_CODEX_TEST_DATABASE = _TEST_DATABASE_DIR / "codex-control-centre.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_APP_TEST_DATABASE.as_posix()}"

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DATABASES = (
    _REPOSITORY_ROOT / "fastapi_bookings.db",
    _REPOSITORY_ROOT / "fastapi_bookings.db-wal",
    _REPOSITORY_ROOT / "fastapi_bookings.db-shm",
    _REPOSITORY_ROOT / "codex-control-centre" / "codex.db",
    _REPOSITORY_ROOT / "codex-control-centre" / "codex.db-wal",
    _REPOSITORY_ROOT / "codex-control-centre" / "codex.db-shm",
)


def _file_snapshot(path: Path) -> tuple[bool, int | None, int | None, str | None]:
    if not path.exists():
        return (False, None, None, None)
    stat = path.stat()
    return (True, stat.st_size, stat.st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())


_DEFAULT_DATABASE_SNAPSHOT = {path: _file_snapshot(path) for path in _DEFAULT_DATABASES}

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Windows environment names are case-insensitive, while the two applications
# intentionally use DATABASE_URL and database_url.  Freeze the FastAPI
# Bookings settings/engine first, then select the independent Control Centre
# database before importing the mounted application.
from app.db.database import Base, engine as application_engine, get_db
os.environ["database_url"] = f"sqlite:///{_CODEX_TEST_DATABASE.as_posix()}"

# Production startup deliberately performs no CCC DDL.  Root tests that mount
# CCC routes therefore migrate only their process-unique temporary CCC database
# before importing app.main or any nested backend module.
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

_CODEX_ROOT = _REPOSITORY_ROOT / "codex-control-centre"
_CODEX_ALEMBIC_ROOT = (_CODEX_ROOT / "alembic").resolve()
_codex_alembic_config = AlembicConfig(str((_CODEX_ROOT / "alembic.ini").resolve()))
_codex_alembic_config.set_main_option("script_location", str(_CODEX_ALEMBIC_ROOT))
_codex_alembic_config.set_main_option(
    "sqlalchemy.url", f"sqlite:///{_CODEX_TEST_DATABASE.as_posix()}"
)
if Path(_codex_alembic_config.get_main_option("script_location")).resolve() != _CODEX_ALEMBIC_ROOT:
    raise RuntimeError("isolated_ccc_migration_script_location_invalid")
alembic_command.upgrade(_codex_alembic_config, "head")
_codex_revision_connection = sqlite3.connect(_CODEX_TEST_DATABASE)
try:
    _codex_revisions = _codex_revision_connection.execute(
        "SELECT version_num FROM alembic_version"
    ).fetchall()
finally:
    _codex_revision_connection.close()
del _codex_revision_connection
if _codex_revisions != [("003",)]:
    raise RuntimeError("isolated_ccc_migration_revision_invalid")

from app.main import app as fastapi_app
import app.models  # Crucial: imports all models to register them on Base.metadata
from tests.fixtures.channel_fixtures import (  # noqa: F401
    channel_test_env,
    synthetic_channel_accounts,
    multi_turn_conversation_with_chatwoot,
    legacy_sms_compatibility_data,
)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{_APP_TEST_DATABASE.as_posix()}"

_ORIGINAL_SOCKET_CONNECT = socket.socket.connect
_ORIGINAL_SOCKETPAIR = socket.socketpair
_socketpair_permit = threading.local()


def _block_outbound_network(*args, **kwargs):
    """Fail closed if a test attempts to open a real network connection."""
    raise RuntimeError(
        "Outbound network access is disabled during tests. "
        "Use an explicit fake transport or mocked client instead."
    )


def _guard_socket_connect(socket_instance, address):
    """Permit only socketpair's private connection in its creating thread."""
    if getattr(_socketpair_permit, "allow_connect", False):
        return _ORIGINAL_SOCKET_CONNECT(socket_instance, address)
    return _block_outbound_network(socket_instance, address)


def _create_local_socketpair(*args, **kwargs):
    """Allow asyncio to create its private self-pipe without opening a network path."""
    # On Windows, socket.socketpair() constructs a loopback-only socket pair by
    # calling socket.connect internally. The guard stays installed globally;
    # only this thread may use the original connect during construction.
    previous_permit = getattr(_socketpair_permit, "allow_connect", False)
    _socketpair_permit.allow_connect = True
    try:
        return _ORIGINAL_SOCKETPAIR(*args, **kwargs)
    finally:
        _socketpair_permit.allow_connect = previous_permit

@pytest.fixture(scope="session")
def engine():
    """Create a session-wide isolated SQLite engine and build all tables."""
    test_engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture(scope="session")
def default_database_snapshot():
    """Expose a read-only sentinel proving runtime database files stay untouched."""
    return _DEFAULT_DATABASE_SNAPSHOT, _file_snapshot


def pytest_sessionfinish(session, exitstatus):
    cleanup_failures = []
    engines = [("FastAPI Bookings", application_engine)]
    codex_database = sys.modules.get("backend.database")
    codex_engine = getattr(codex_database, "engine", None)
    if codex_engine is not None and codex_engine is not application_engine:
        engines.append(("Codex Control Centre", codex_engine))

    for label, loaded_engine in engines:
        try:
            loaded_engine.dispose()
        except Exception as exc:  # pragma: no cover - exercised only on teardown failure
            cleanup_failures.append(f"{label} engine disposal failed: {type(exc).__name__}")

    changed = [
        str(path)
        for path, before in _DEFAULT_DATABASE_SNAPSHOT.items()
        if _file_snapshot(path) != before
    ]
    try:
        shutil.rmtree(_TEST_DATABASE_DIR)
    except FileNotFoundError:
        pass
    except Exception as exc:  # pragma: no cover - exercised only on teardown failure
        cleanup_failures.append(
            f"temporary test storage removal failed: {type(exc).__name__}: {_TEST_DATABASE_DIR}"
        )
    if _TEST_DATABASE_DIR.exists():
        cleanup_failures.append(f"temporary test storage remains: {_TEST_DATABASE_DIR}")

    if changed or cleanup_failures:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter:
            reporter.write_sep("=", "test database isolation failure")
            if changed:
                reporter.write_line("Unexpectedly changed runtime database sentinel(s):")
                for path in changed:
                    reporter.write_line(path)
            for failure in cleanup_failures:
                reporter.write_line(failure)

@pytest.fixture(scope="function")
def db_session(engine):
    """Provide a function-scoped database session, run inside a rollback-able transaction."""
    connection = engine.connect()
    transaction = connection.begin()
    
    nested = connection.begin_nested()
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionLocal()
    
    from sqlalchemy import event
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()
            
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    """Expose a TestClient with app.dependency_overrides set up to inject db_session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture(scope="function", autouse=True)
def clean_test_environment(monkeypatch):
    """Ensure complete isolation before and after every test."""
    from app.core.telemetry import shutdown_telemetry
    from app.core.config import settings

    # Block below HTTP-client libraries so requests, httpx, SDKs, and direct
    # socket users all fail before a real connection can be established.
    # FastAPI's in-process TestClient uses an ASGI transport and does not open
    # a socket, while tests that patch a client method remain unaffected.
    monkeypatch.setattr(socket, "create_connection", _block_outbound_network)
    monkeypatch.setattr(socket.socket, "connect", _guard_socket_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _block_outbound_network)
    monkeypatch.setattr(socket, "socketpair", _create_local_socketpair)

    fastapi_app.dependency_overrides.clear()
    settings.OTEL_SDK_DISABLED = True
    shutdown_telemetry()

    yield

    fastapi_app.dependency_overrides.clear()
    settings.OTEL_SDK_DISABLED = True
    shutdown_telemetry()
