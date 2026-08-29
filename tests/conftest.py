"""Conftest file for setting up pytest fixtures and overriding app dependencies."""

import os
import socket
import ipaddress
import contextlib
import threading
from typing import Optional

# Force OTel SDK off before ANY app module is imported.
# Uses a hard assignment so shell env overrides are also suppressed.
os.environ["OTEL_SDK_DISABLED"] = "true"

# ---------------------------------------------------------------------------
import sys

# Process-wide singleton for network trap disable flag to bridge conftest import variants
if not hasattr(sys, "_fastapi_test_network_trap_disabled"):
    sys._fastapi_test_network_trap_disabled = threading.local()

_NETWORK_TRAP_DISABLED = sys._fastapi_test_network_trap_disabled


@contextlib.contextmanager
def allow_network_calls():
    """Context manager to temporarily bypass the network trap for dedicated local/integration tests."""
    previous = getattr(_NETWORK_TRAP_DISABLED, "value", False)
    _NETWORK_TRAP_DISABLED.value = True
    try:
        yield
    finally:
        _NETWORK_TRAP_DISABLED.value = previous


# Alias for compatibility
disable_network_trap = allow_network_calls


def _extract_host_port(address):
    """Extract host and port from socket address representations."""
    if isinstance(address, tuple) and len(address) >= 1:
        return str(address[0]), (address[1] if len(address) > 1 else None)
    if isinstance(address, (str, bytes)):
        if isinstance(address, bytes):
            address = address.decode("utf-8", errors="replace")
        return address, None
    return str(address), None


def _is_allowed_host(host: Optional[str]) -> bool:
    """Return True if host is localhost / loopback / testserver / unix socket."""
    if getattr(_NETWORK_TRAP_DISABLED, "value", False):
        return True
    if not host:
        return True

    host_clean = host.lower().strip()
    if host_clean.startswith("[") and host_clean.endswith("]"):
        host_clean = host_clean[1:-1]

    allowed_hostnames = {"localhost", "127.0.0.1", "::1", "testserver", "test", "0.0.0.0", "::", ""}
    if host_clean in allowed_hostnames:
        return True

    try:
        ip = ipaddress.ip_address(host_clean)
        return ip.is_loopback or ip.is_unspecified
    except ValueError:
        pass

    return False


def _deny_network_access(destination_desc: str):
    raise RuntimeError(
        f"Live network access is prohibited during testing: attempted connection to {destination_desc}"
    )


if not hasattr(socket.socket, "_unpatched_connect"):
    socket.socket._unpatched_connect = socket.socket.connect
    socket.socket._unpatched_connect_ex = socket.socket.connect_ex
    socket._unpatched_create_connection = socket.create_connection

_ORIGINAL_SOCKET_CONNECT = socket.socket._unpatched_connect
_ORIGINAL_SOCKET_CONNECT_EX = socket.socket._unpatched_connect_ex
_ORIGINAL_CREATE_CONNECTION = socket._unpatched_create_connection


def _trapped_socket_connect(sock_self, address):
    host, _ = _extract_host_port(address)
    if not _is_allowed_host(host):
        _deny_network_access(f"{address}")
    return _ORIGINAL_SOCKET_CONNECT(sock_self, address)


def _trapped_socket_connect_ex(sock_self, address):
    host, _ = _extract_host_port(address)
    if not _is_allowed_host(host):
        _deny_network_access(f"{address}")
    return _ORIGINAL_SOCKET_CONNECT_EX(sock_self, address)


def _trapped_create_connection(address, *args, **kwargs):
    host, _ = _extract_host_port(address)
    if not _is_allowed_host(host):
        _deny_network_access(f"{address}")
    return _ORIGINAL_CREATE_CONNECTION(address, *args, **kwargs)


socket.socket.connect = _trapped_socket_connect
socket.socket.connect_ex = _trapped_socket_connect_ex
socket.create_connection = _trapped_create_connection


def pytest_configure(config):
    """Register custom markers to avoid warnings."""
    config.addinivalue_line(
        "markers", "allow_network: Opt-out of the network denial trap for dedicated tests."
    )
    config.addinivalue_line(
        "markers", "allow_external_network: Opt-out of the network denial trap for dedicated tests."
    )


import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.db.database import Base, get_db
import app.models  # Crucial: imports all models to register them on Base.metadata

# SQLite in-memory database URL for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

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

def create_test_token(user_id: int, role: str = "admin", **extra_claims) -> str:
    """Generate a valid signed JWT access token for testing."""
    from app.core.security import create_access_token
    payload = {"sub": str(user_id), "role": role, **extra_claims}
    return create_access_token(payload)


def admin_auth_headers(tenant_subdomain: str, user_id: int, role: str = "admin") -> dict:
    """Return standard headers for administrative requests."""
    token = create_test_token(user_id, role)
    return {
        "X-Tenant": tenant_subdomain,
        "X-Token": token,
    }


class InterceptingTestClient(TestClient):
    """TestClient that bridges legacy test mock tokens to signed JWTs without production bypasses."""

    def __init__(self, app, db_session, is_auth_test: bool = False, **kwargs):
        super().__init__(app, **kwargs)
        self.db_session = db_session
        self.is_auth_test = is_auth_test

    def request(self, method, url, **kwargs):
        headers = kwargs.get("headers")
        if not self.is_auth_test and headers and isinstance(headers, dict):
            token = headers.get("X-Token")
            if token == "mock-admin-token":
                tenant_sub = headers.get("X-Tenant")
                from app.models.tenant import Tenant
                from app.models.user import User
                from app.core.security import create_access_token

                query = self.db_session.query(User)
                if tenant_sub:
                    tenant = self.db_session.query(Tenant).filter(Tenant.subdomain == tenant_sub).first()
                    if tenant:
                        query = query.filter(User.tenant_id == tenant.id)
                user = query.first()
                if user:
                    new_headers = dict(headers)
                    new_headers["X-Token"] = create_access_token({"sub": str(user.id), "role": user.role})
                    kwargs["headers"] = new_headers

        return super().request(method, url, **kwargs)


@pytest.fixture(scope="function")
def client(request, db_session):
    """Expose a TestClient with app.dependency_overrides set up to inject db_session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    is_auth_test = "test_auth_remediation" in getattr(request.node.module, "__name__", "")
    with InterceptingTestClient(fastapi_app, db_session, is_auth_test=is_auth_test) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture(scope="function", autouse=True)
def enforce_network_trap(request, monkeypatch):
    """
    Autouse fixture that enforces the network denial trap for every test.
    Checks for @pytest.mark.allow_network or @pytest.mark.allow_external_network markers.
    """
    has_opt_out = (
        request.node.get_closest_marker("allow_network") is not None
        or request.node.get_closest_marker("allow_external_network") is not None
    )
    if has_opt_out:
        with allow_network_calls():
            yield
    else:
        try:
            import httpx

            _orig_httpx_send = httpx.Client.send
            _orig_async_httpx_send = httpx.AsyncClient.send

            def _trapped_httpx_send(client_self, req, *args, **kwargs):
                if not _is_allowed_host(req.url.host):
                    _deny_network_access(f"{req.url.host} ({req.url})")
                return _orig_httpx_send(client_self, req, *args, **kwargs)

            async def _trapped_async_httpx_send(client_self, req, *args, **kwargs):
                if not _is_allowed_host(req.url.host):
                    _deny_network_access(f"{req.url.host} ({req.url})")
                return await _orig_async_httpx_send(client_self, req, *args, **kwargs)

            monkeypatch.setattr(httpx.Client, "send", _trapped_httpx_send)
            monkeypatch.setattr(httpx.AsyncClient, "send", _trapped_async_httpx_send)
        except ImportError:
            pass

        try:
            import urllib.request

            _orig_urlopen = urllib.request.urlopen

            def _trapped_urlopen(url_or_req, *args, **kwargs):
                from urllib.parse import urlparse

                if isinstance(url_or_req, str):
                    h = urlparse(url_or_req).hostname
                else:
                    h = urlparse(url_or_req.full_url).hostname
                if not _is_allowed_host(h):
                    _deny_network_access(f"{h}")
                return _orig_urlopen(url_or_req, *args, **kwargs)

            monkeypatch.setattr(urllib.request, "urlopen", _trapped_urlopen)
        except ImportError:
            pass

        yield


@pytest.fixture(scope="function", autouse=True)
def clean_test_environment():
    """Ensure complete isolation before and after every test."""
    from app.core.telemetry import shutdown_telemetry
    from app.core.config import settings
    from app.main import limiter
    try:
        from app.services.sms.transports.fake import FakeTransportAdapter
        FakeTransportAdapter.sent_messages.clear()
    except Exception:
        pass

    fastapi_app.dependency_overrides.clear()
    settings.OTEL_SDK_DISABLED = True
    try:
        limiter._storage.reset()
    except Exception:
        pass
    shutdown_telemetry()

    yield

    fastapi_app.dependency_overrides.clear()
    settings.OTEL_SDK_DISABLED = True
    try:
        limiter._storage.reset()
    except Exception:
        pass
    shutdown_telemetry()
    try:
        from app.services.sms.transports.fake import FakeTransportAdapter
        FakeTransportAdapter.sent_messages.clear()
    except Exception:
        pass
