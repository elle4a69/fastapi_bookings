"""Conftest file for setting up pytest fixtures and overriding app dependencies."""

import os

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
def clean_test_environment():
    """Ensure complete isolation before and after every test."""
    from app.core.telemetry import shutdown_telemetry
    from app.core.config import settings
    from app.main import limiter

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
