import logging
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app, lifespan
from backend.database import Base, set_sqlite_pragma, get_db
from backend.config import settings
from backend.services.event_service import broker
from backend.services.worker_manager import WorkerManager
from backend.middleware.logging import (
    redact_secrets,
    redact_dict,
    RedactingFilter
)
from backend.services.diagnostics_tool import (
    get_deep_diagnostics,
    check_database_health
)


@pytest.fixture
def db_engine():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    event.listen(test_engine, "connect", set_sqlite_pragma)
    Base.metadata.create_all(bind=test_engine)
    yield test_engine


@pytest.fixture
def client(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_event_broker():
    broker.subscribers.clear()
    broker.history.clear()
    broker.sequences.clear()
    yield
    broker.subscribers.clear()
    broker.history.clear()
    broker.sequences.clear()


# ============================================================================
# 1. Structured Correlation Logging & Safe Redaction Tests
# ============================================================================

def test_correlation_logging_generates_request_id(client):
    """Verify that requests without X-Request-ID receive a generated request_id in response headers."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    req_id = resp.headers["X-Request-ID"]
    assert req_id.startswith("req_")


def test_correlation_logging_preserves_incoming_request_id(client):
    """Verify that incoming X-Request-ID or X-Correlation-ID is preserved and attached."""
    custom_id = "test-corr-id-12345"
    resp = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == custom_id


def test_correlation_logging_attaches_thread_id(client):
    """Verify that thread_id in path or query is extracted and attached to response header."""
    auth_headers = {
        "Authorization": f"Bearer {settings.token_secret}",
        "X-Thread-ID": "thread_custom_abc"
    }
    resp = client.get("/codex/threads", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers.get("X-Thread-ID") == "thread_custom_abc"


def test_redact_secrets_strings():
    """Verify redaction of bearer tokens and sensitive query parameters from string logs."""
    raw_bearer = "User sent header: Bearer super_secret_jwt_token_123456"
    sanitized = redact_secrets(raw_bearer)
    assert "super_secret_jwt_token_123456" not in sanitized
    assert "Bearer [REDACTED]" in sanitized

    raw_query = "http://127.0.0.1:8100/codex/events/p1/t1?token=my_secret_token&user=frank"
    sanitized_query = redact_secrets(raw_query)
    assert "my_secret_token" not in sanitized_query
    assert "token=[REDACTED]" in sanitized_query
    assert "user=frank" in sanitized_query


def test_redact_dict_structures():
    """Verify recursive redaction of sensitive dictionary keys and values."""
    sensitive_data = {
        "user": "alice",
        "authorization": "Bearer token_xyz",
        "token": "secret_abc",
        "nested": {
            "password": "p@ssword123",
            "api_key": "key_999",
            "safe_key": "safe_value"
        },
        "items": [
            {"token_secret": "my_secret", "name": "item1"}
        ]
    }
    redacted = redact_dict(sensitive_data)
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["api_key"] == "[REDACTED]"
    assert redacted["nested"]["safe_key"] == "safe_value"
    assert redacted["items"][0]["token_secret"] == "[REDACTED]"
    assert redacted["items"][0]["name"] == "item1"


def test_redacting_logging_filter():
    """Verify RedactingFilter automatically scrubs sensitive information from LogRecords."""
    log_filter = RedactingFilter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Connecting with Bearer secret_live_token_777 and token=abc1234",
        args=(),
        exc_info=None
    )
    result = log_filter.filter(record)
    assert result is True
    assert "secret_live_token_777" not in record.msg
    assert "abc1234" not in record.msg
    assert "Bearer [REDACTED]" in record.msg


# ============================================================================
# 2. Health & Readiness Subsystem Verification Tests
# ============================================================================

def test_unauthenticated_health_liveness(client):
    """Verify GET /health is an unauthenticated, fast liveness probe returning HTTP 200."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_authenticated_readiness_probe_healthy(client):
    """Verify GET /codex/diagnostics/readiness returns detailed subsystem checks."""
    auth_headers = {"Authorization": f"Bearer {settings.token_secret}"}
    resp = client.get("/codex/diagnostics/readiness", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "subsystems" in data
    assert data["subsystems"]["database"]["status"] == "healthy"
    assert data["subsystems"]["event_broker"]["status"] == "healthy"
    assert data["subsystems"]["worktree_storage"]["status"] == "healthy"
    assert "worker" in data["subsystems"]
    assert "telemetry" in data["subsystems"]


def test_diagnostics_deep_matches_readiness(client):
    """Verify /codex/diagnostics/deep provides congruent diagnostics structure."""
    auth_headers = {"Authorization": f"Bearer {settings.token_secret}"}
    resp = client.get("/codex/diagnostics/deep", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "subsystems" in data


def test_readiness_fails_unauthenticated(client):
    """Verify unauthenticated access to /codex/diagnostics/readiness is blocked."""
    resp = client.get("/codex/diagnostics/readiness")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_readiness_degraded_when_database_fails():
    """Verify overall readiness truthfully degrades when database check fails."""
    # Mock broken DB session
    broken_session = MagicMock()
    broken_session.execute.side_effect = Exception("DB Connection Lost")

    db_status = check_database_health(broken_session)
    assert db_status["status"] == "unhealthy"
    assert db_status["connected"] is False
    assert "DB Connection Lost" in db_status["error"]

    deep_status = await get_deep_diagnostics(broken_session)
    assert deep_status["status"] == "degraded"
    assert deep_status["subsystems"]["database"]["status"] == "unhealthy"


# ============================================================================
# 3. Graceful Shutdown & Subsystem Lifecycle Tests
# ============================================================================

@pytest.mark.asyncio
async def test_event_broker_graceful_close_all():
    """Verify EventBroker.close_all() broadcasts __close__ events and empties subscriber lists."""
    q1 = broker.subscribe("thread_alpha")
    q2 = broker.subscribe("thread_beta")

    assert len(broker.subscribers) == 2

    # Close all active subscribers
    await broker.close_all()

    # Verify both queues received __close__ event
    event1 = q1.get_nowait()
    assert event1.type == "__close__"
    assert event1.payload.get("reason") == "server_shutdown"

    event2 = q2.get_nowait()
    assert event2.type == "__close__"

    # Verify subscriber map is cleared
    assert len(broker.subscribers) == 0


@pytest.mark.asyncio
async def test_worker_manager_graceful_stop():
    """Verify WorkerManager.stop() cleanly shuts down worker process and futures."""
    cmd = ["python", "-c", "import sys, json\nwhile True:\n line = sys.stdin.readline()\n if not line: break\n sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': json.loads(line).get('id'), 'result': 'ok'}) + '\\n')\n sys.stdout.flush()"]
    manager = WorkerManager(cmd)
    worker = await manager.get_worker()
    assert worker.running

    await manager.stop()
    assert not worker.running


@pytest.mark.asyncio
async def test_app_lifespan_context_manager():
    """Verify application lifespan handler executes startup and teardown cleanly."""
    async with lifespan(app):
        # In-service state
        assert app.title == "Codex Control Centre"
    # Post-shutdown: Verify broker closed without exceptions
    assert len(broker.subscribers) == 0
