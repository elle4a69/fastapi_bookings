"""Conftest file for setting up pytest fixtures and overriding app dependencies."""

import os
import socket
import threading

# Force OTel SDK off before ANY app module is imported.
# Uses a hard assignment so shell env overrides are also suppressed.
os.environ["OTEL_SDK_DISABLED"] = "true"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.db.database import Base, get_db
import app.models  # Crucial: imports all models to register them on Base.metadata

# SQLite in-memory database URL for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

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
    """Create a session-wide SQLite in-memory engine and build all database tables."""
    test_engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)

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
