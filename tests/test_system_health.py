"""Tests for GET /api/admin/system/health.

Rule 3 compliance: the endpoint must exercise real live connections and
return a truthful SystemHealthResponse.  These tests validate:
  1. Unauthenticated requests are rejected (401/403).
  2. An authenticated admin receives a valid SystemHealthResponse shape with
     real DB data (postgres.status derived from an actual SELECT 1).
  3. When a dependency (Redis or Neo4j) is unavailable the endpoint still
     returns HTTP 200, marks that service "down", and sets api_status to
     "degraded".
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app as fastapi_app
from app.db.database import Base, get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.api.deps import get_current_admin, get_current_tenant
import app.models  # noqa: F401 — registers all ORM models on Base.metadata


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def health_engine():
    """Session-wide in-memory SQLite engine for health tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def health_db(health_engine):
    """Function-scoped DB session with rollback isolation."""
    connection = health_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(autocommit=False, autoflush=False, bind=connection)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def health_client(health_db):
    """TestClient with DB override and a seeded admin user + tenant."""
    # Seed tenant
    tenant = Tenant(name="Health Test Tenant", subdomain="health-test")
    health_db.add(tenant)
    health_db.flush()

    # Seed admin user (use the actual User model field names: login, password_hash)
    user = User(
        tenant_id=tenant.id,
        login="healthadmin@example.com",
        password_hash="x",
        role="admin",
    )
    health_db.add(user)
    health_db.commit()
    health_db.refresh(user)
    health_db.refresh(tenant)

    def override_db():
        yield health_db

    def override_admin():
        return user

    def override_tenant():
        return tenant

    fastapi_app.dependency_overrides[get_db] = override_db
    fastapi_app.dependency_overrides[get_current_admin] = override_admin
    fastapi_app.dependency_overrides[get_current_tenant] = override_tenant

    with TestClient(fastapi_app) as client:
        yield client, user, tenant

    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def unauthed_client(health_db):
    """TestClient without admin override.

    We patch the DB and pre-seed the tenant so that tenant resolution succeeds
    (avoiding 404), allowing get_current_admin to run and return 401/403 for
    the missing authentication token.
    """
    # Seed tenant so get_current_tenant resolves instead of returning 404
    tenant = Tenant(name="Health Test Tenant", subdomain="health-test")
    health_db.add(tenant)
    health_db.commit()
    health_db.refresh(tenant)

    def override_db():
        yield health_db

    def override_tenant():
        return tenant

    fastapi_app.dependency_overrides[get_db] = override_db
    fastapi_app.dependency_overrides[get_current_tenant] = override_tenant
    # Deliberately do NOT override get_current_admin — the real dep must reject the request

    with TestClient(fastapi_app) as client:
        yield client

    fastapi_app.dependency_overrides.clear()


# ── Test 1: authentication guard ─────────────────────────────────────────────

def test_health_endpoint_requires_authentication(unauthed_client):
    """Unauthenticated request must be rejected with 401 or 403."""
    response = unauthed_client.get(
        "/api/admin/system/health",
        headers={"X-Tenant": "health-test"},  # tenant header present; no auth token
    )
    assert response.status_code in (401, 403), (
        f"Expected 401 or 403 for unauthenticated access, got {response.status_code}"
    )


# ── Test 2: valid shape with real DB data ─────────────────────────────────────

def test_health_endpoint_returns_valid_shape(health_client, monkeypatch):
    """Authenticated admin gets a well-formed SystemHealthResponse.

    Redis and Neo4j are patched to return 'ok' so we can assert the full
    happy-path shape without needing live external services in CI.
    The postgres check always exercises a real (in-memory) DB session.
    """
    from app.api.routers import system as system_module
    from app.schemas.general_systems import ServiceHealthCheck

    def fake_redis_ok():
        return ServiceHealthCheck(status="ok", latency_ms=0.5)

    def fake_neo4j_ok():
        return ServiceHealthCheck(status="ok", latency_ms=1.2)

    monkeypatch.setattr(system_module, "_check_redis", fake_redis_ok)
    monkeypatch.setattr(system_module, "_check_neo4j", fake_neo4j_ok)

    client, _user, _tenant = health_client
    response = client.get("/api/admin/system/health")
    assert response.status_code == 200, response.text

    data = response.json()

    # Top-level api_status
    assert data["api_status"] in ("operational", "degraded", "down")

    # postgres: real SELECT 1 on in-memory SQLite
    pg = data["postgres"]
    assert pg["status"] == "ok"
    assert isinstance(pg["latency_ms"], float)
    assert pg["latency_ms"] >= 0

    # redis: patched ok
    rd = data["redis"]
    assert rd["status"] == "ok"
    assert rd["latency_ms"] == 0.5

    # neo4j: patched ok
    n4j = data["neo4j"]
    assert n4j["status"] == "ok"
    assert n4j["latency_ms"] == 1.2

    # background_workers: truthful null-source report
    bw = data["background_workers"]
    assert bw is not None
    assert bw["status"] == "ok"
    assert "source=none" in (bw.get("detail") or "")

    # checked_at: parseable ISO datetime
    from datetime import datetime
    checked_at = datetime.fromisoformat(data["checked_at"].replace("Z", "+00:00"))
    assert checked_at is not None

    # overall api_status should be "operational" when all services are ok
    assert data["api_status"] == "operational"


# ── Test 3: degraded when a service is unavailable ───────────────────────────

def test_health_endpoint_degraded_when_redis_down(health_client, monkeypatch):
    """When Redis is unreachable the endpoint returns HTTP 200 with api_status 'degraded'."""
    from app.api.routers import system as system_module
    from app.schemas.general_systems import ServiceHealthCheck

    def fake_redis_down():
        return ServiceHealthCheck(
            status="down",
            latency_ms=None,
            detail="Connection refused",
        )

    def fake_neo4j_none():
        # Neo4j not configured in this scenario
        return None

    monkeypatch.setattr(system_module, "_check_redis", fake_redis_down)
    monkeypatch.setattr(system_module, "_check_neo4j", fake_neo4j_none)

    client, _user, _tenant = health_client
    response = client.get("/api/admin/system/health")
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["api_status"] == "degraded"
    assert data["redis"]["status"] == "down"
    assert data["redis"]["latency_ms"] is None
    assert "Connection refused" in (data["redis"].get("detail") or "")


def test_health_endpoint_degraded_when_neo4j_down(health_client, monkeypatch):
    """When Neo4j is down the api_status must be 'degraded'."""
    from app.api.routers import system as system_module
    from app.schemas.general_systems import ServiceHealthCheck

    def fake_redis_ok():
        return ServiceHealthCheck(status="ok", latency_ms=0.3)

    def fake_neo4j_down():
        return ServiceHealthCheck(
            status="down",
            latency_ms=None,
            detail="ServiceUnavailable",
        )

    monkeypatch.setattr(system_module, "_check_redis", fake_redis_ok)
    monkeypatch.setattr(system_module, "_check_neo4j", fake_neo4j_down)

    client, _user, _tenant = health_client
    response = client.get("/api/admin/system/health")
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["api_status"] == "degraded"
    assert data["neo4j"]["status"] == "down"


def test_health_endpoint_operational_when_neo4j_absent(health_client, monkeypatch):
    """When neo4j returns None (not configured) api_status is 'operational' if postgres+redis ok."""
    from app.api.routers import system as system_module
    from app.schemas.general_systems import ServiceHealthCheck

    def fake_redis_ok():
        return ServiceHealthCheck(status="ok", latency_ms=0.3)

    def fake_neo4j_none():
        return None

    monkeypatch.setattr(system_module, "_check_redis", fake_redis_ok)
    monkeypatch.setattr(system_module, "_check_neo4j", fake_neo4j_none)

    client, _user, _tenant = health_client
    response = client.get("/api/admin/system/health")
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["api_status"] == "operational"
    assert data["neo4j"] is None
