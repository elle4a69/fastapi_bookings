"""Tests for deployment hardening, readiness probes, container configuration, and CI gates."""

import os
import re
from unittest.mock import MagicMock
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.api.deps import get_db


def _extract_error_message(response_json: dict) -> str:
    """Helper to extract error message from standard or custom JSON response."""
    if "error" in response_json and "message" in response_json["error"]:
        return response_json["error"]["message"]
    return response_json.get("detail", "")


# ---------------------------------------------------------------------------
# 1. Readiness Probe Tests (OPS-004)
# ---------------------------------------------------------------------------

def test_readiness_probe_healthy(client):
    """Ensure /ready returns 200 OK when core tables are available and DB is healthy."""
    response = client.get("/ready")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"ok": True}


def test_readiness_probe_unmigrated_empty_db():
    """Ensure /ready returns 503 Service Unavailable on an empty/unmigrated database."""
    empty_engine = create_engine("sqlite:///:memory:")
    EmptySession = sessionmaker(bind=empty_engine)

    def override_get_db():
        session = EmptySession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        test_client = TestClient(app)
        response = test_client.get("/ready")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        msg = _extract_error_message(response.json())
        assert msg == "Database schema incomplete or unmigrated."
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_readiness_probe_missing_critical_core_table():
    """Ensure /ready returns 503 when one of the critical core tables is missing."""
    partial_engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    # Create only tenants and users, omitting bookings, services, providers
    Table("tenants", metadata, Column("id", Integer, primary_key=True))
    Table("users", metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(bind=partial_engine)

    PartialSession = sessionmaker(bind=partial_engine)

    def override_get_db():
        session = PartialSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        test_client = TestClient(app)
        response = test_client.get("/ready")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        msg = _extract_error_message(response.json())
        assert msg == "Database schema incomplete or unmigrated."
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_readiness_probe_persistent_db_requires_alembic_version(tmp_path):
    """Ensure /ready returns 503 on persistent databases if alembic_version is absent or unpopulated."""
    from app.main import get_expected_alembic_heads
    db_file = tmp_path / "persistent_test.db"
    persistent_engine = create_engine(f"sqlite:///{db_file}")
    metadata = MetaData()
    # Create all core tables but NOT alembic_version
    for table_name in ["tenants", "users", "bookings", "services", "providers"]:
        Table(table_name, metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(bind=persistent_engine)

    PersistentSession = sessionmaker(bind=persistent_engine)

    def override_get_db():
        session = PersistentSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        test_client = TestClient(app)
        response = test_client.get("/ready")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        msg = _extract_error_message(response.json())
        assert msg == "Database schema incomplete or unmigrated."

        # Now add alembic_version with current head revision and verify it passes
        alembic_table = Table("alembic_version", metadata, Column("version_num", String(32), primary_key=True))
        metadata.create_all(bind=persistent_engine)

        heads = list(get_expected_alembic_heads())
        assert len(heads) > 0
        with persistent_engine.begin() as conn:
            conn.execute(alembic_table.insert().values(version_num=heads[0]))

        response_ok = test_client.get("/ready")
        assert response_ok.status_code == status.HTTP_200_OK
        assert response_ok.json() == {"ok": True}
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_readiness_probe_version_mismatch(tmp_path):
    """Ensure /ready returns 503 when alembic_version contains an outdated revision (OPS-004)."""
    db_file = tmp_path / "version_mismatch_test.db"
    persistent_engine = create_engine(f"sqlite:///{db_file}")
    metadata = MetaData()
    for table_name in ["tenants", "users", "bookings", "services", "providers"]:
        Table(table_name, metadata, Column("id", Integer, primary_key=True))
    alembic_table = Table("alembic_version", metadata, Column("version_num", String(32), primary_key=True))
    metadata.create_all(bind=persistent_engine)

    # Insert an outdated / non-matching revision
    with persistent_engine.begin() as conn:
        conn.execute(alembic_table.insert().values(version_num="outdated_migration_rev_000"))

    PersistentSession = sessionmaker(bind=persistent_engine)

    def override_get_db():
        session = PersistentSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        test_client = TestClient(app)
        response = test_client.get("/ready")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        msg = _extract_error_message(response.json())
        assert msg == "Database schema version mismatch."
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_readiness_probe_empty_alembic_version_table(tmp_path):
    """Ensure /ready returns 503 when alembic_version exists but contains no rows."""
    db_file = tmp_path / "empty_alembic_test.db"
    persistent_engine = create_engine(f"sqlite:///{db_file}")
    metadata = MetaData()
    for table_name in ["tenants", "users", "bookings", "services", "providers"]:
        Table(table_name, metadata, Column("id", Integer, primary_key=True))
    Table("alembic_version", metadata, Column("version_num", String(32), primary_key=True))
    metadata.create_all(bind=persistent_engine)

    PersistentSession = sessionmaker(bind=persistent_engine)

    def override_get_db():
        session = PersistentSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        test_client = TestClient(app)
        response = test_client.get("/ready")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        msg = _extract_error_message(response.json())
        assert msg == "Database schema incomplete or unmigrated."
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_readiness_probe_database_disconnected():
    """Ensure /ready returns 503 when the database connection throws an exception."""
    mock_session = MagicMock()
    mock_session.execute.side_effect = ConnectionError("Could not connect to PostgreSQL server")

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        test_client = TestClient(app)
        response = test_client.get("/ready")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        msg = _extract_error_message(response.json())
        assert msg == "Database connectivity failed."
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# 2. Dockerfile Hardening & Non-Root Assertions (OPS-002, OPS-003, OPS-006, SEC-006)
# ---------------------------------------------------------------------------

def test_dockerfile_hardening_assertions():
    """Verify Dockerfile meets non-root, pinned version, healthcheck, and startup migration requirements."""
    dockerfile_path = os.path.join(os.path.dirname(__file__), "..", "Dockerfile")
    assert os.path.exists(dockerfile_path), "Dockerfile must exist at repository root"

    with open(dockerfile_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Pinned base image
    assert "FROM python:3.11.9-slim" in content or "FROM python:3.11." in content, "Must use pinned Python 3.11 base"

    # Non-root user creation and switch
    assert "useradd" in content and "appuser" in content, "Must create appuser non-root user"
    assert re.search(r"^\s*USER\s+appuser", content, re.MULTILINE), "Must switch to non-root USER appuser"

    # Alembic migrations included
    assert "alembic" in content and "alembic.ini" in content, "Must include Alembic and migration files"

    # Port 8000 exposed
    assert re.search(r"^\s*EXPOSE\s+8000", content, re.MULTILINE), "Must expose port 8000"

    # Healthcheck instruction
    assert re.search(r"^\s*HEALTHCHECK\s+", content, re.MULTILINE), "Must define HEALTHCHECK instruction"

    # Automated startup migration assertion (OPS-003)
    assert "alembic upgrade head" in content, "Dockerfile CMD must execute alembic upgrade head on startup"


# ---------------------------------------------------------------------------
# 3. .dockerignore Hardening Assertions (SEC-006)
# ---------------------------------------------------------------------------

def test_dockerignore_hardening_assertions():
    """Verify .dockerignore excludes sensitive secrets, databases, logs, and venvs."""
    dockerignore_path = os.path.join(os.path.dirname(__file__), "..", ".dockerignore")
    assert os.path.exists(dockerignore_path), ".dockerignore must exist at repository root"

    with open(dockerignore_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]

    required_ignores = [
        ".git",
        ".env*",
        "*.db",
        "*.sqlite",
        "*.log",
        ".venv/",
        "node_modules/",
        "integrations/assistant-ui-v2/",
    ]

    for req in required_ignores:
        assert any(req in line for line in lines), f".dockerignore must contain pattern matching '{req}'"

    # Ensure .env.example is not blocked
    assert "!.env.example" in lines, ".dockerignore must allow .env.example"


# ---------------------------------------------------------------------------
# 4. Compose Hardening & Secret Removal Assertions (OPS-001, OPS-002, OPS-003)
# ---------------------------------------------------------------------------

def test_docker_compose_security_assertions():
    """Verify docker-compose.yml has no hardcoded secrets, separates web and worker, and runs migrations."""
    compose_path = os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")
    assert os.path.exists(compose_path), "docker-compose.yml must exist at repository root"

    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Secret removal verification (no literal placeholder strings)
    assert "production-secret-key-must-be-configured" not in content, "Must not contain hardcoded secret placeholder"
    assert "production-public-key-must-be-configured" not in content, "Must not contain hardcoded public key placeholder"

    # Port binding verification
    assert "8000:8000" in content, "Web service must bind port 8000:8000"

    # Service separation verification
    assert "web:" in content, "Compose must define web service"
    assert "outbox-worker:" in content, "Compose must define outbox-worker service"

    # Ensure web service disables internal background workers to prevent duplicate loops
    assert "ENABLE_BACKGROUND_WORKERS=false" in content, "Web service must set ENABLE_BACKGROUND_WORKERS=false"

    # Database healthcheck verification
    assert "pg_isready" in content, "PostgreSQL service must define pg_isready healthcheck"

    # Startup migration execution verification (OPS-003)
    assert "alembic upgrade head" in content, "Compose must run alembic upgrade head on startup"


# ---------------------------------------------------------------------------
# 5. CI Pipeline & Dependency Governance Assertions (OPS-007, OPS-008, TEST-005)
# ---------------------------------------------------------------------------

def test_ci_workflow_assertions():
    """Verify .github/workflows/ci.yml defines comprehensive automated gates."""
    ci_path = os.path.join(os.path.dirname(__file__), "..", ".github", "workflows", "ci.yml")
    assert os.path.exists(ci_path), "ci.yml workflow must exist"

    with open(ci_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Quality and security gate assertions (OPS-007, TEST-005)
    assert "pytest" in content, "CI workflow must run pytest tests"
    assert "--cov=app" in content, "CI workflow must measure test coverage"
    assert "flake8" in content, "CI workflow must run linter"
    assert "mypy" in content, "CI workflow must run mypy type checker"
    assert "bandit" in content, "CI workflow must run bandit security scanner"
    assert "alembic upgrade head" in content, "CI workflow must validate migrations"
    assert "alembic check" in content, "CI workflow must run alembic check"
    assert "frontend" in content, "CI workflow must include frontend verification"
    assert "npm test" in content, "CI workflow must run frontend test suite"
    assert "npm run build" in content, "CI workflow must run frontend build"
    assert "docker" in content, "CI workflow must include Docker build/compose checks"


def test_requirements_governance():
    """Verify requirements.txt declares runtime dependencies directly, pins bcrypt, and removes unused ones."""
    req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
    assert os.path.exists(req_path), "requirements.txt must exist"

    with open(req_path, "r", encoding="utf-8") as f:
        content = f.read()

    # OPS-008 bcrypt / passlib compatibility pinning
    assert "bcrypt==3.2.2" in content or "bcrypt<4.0.0" in content, "requirements.txt must pin bcrypt to avoid passlib TypeError"
    assert "passlib" in content, "requirements.txt must declare passlib"
    assert "cryptography" in content, "requirements.txt must directly declare cryptography"
    assert "httpx2" not in content, "requirements.txt must remove unused httpx2"

