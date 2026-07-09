import schemathesis
from hypothesis import settings, HealthCheck
import pytest
from app.main import app
from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User

# Load the schema directly from the FastAPI app instance (ASGI mode)
schema = schemathesis.openapi.from_asgi("/openapi.json", app)

# Global constants for test scoping
TENANT_SUBDOMAIN = "fuzz-tenant"

@pytest.fixture(scope="function", autouse=True)
def setup_fuzz_data(db_session):
    """Ensure a valid tenant and owner exist in the database for the active session."""
    # 1. Create or fetch tenant
    tenant = db_session.query(Tenant).filter(Tenant.subdomain == TENANT_SUBDOMAIN).first()
    if not tenant:
        tenant = Tenant(name="Fuzzing Corp", subdomain=TENANT_SUBDOMAIN)
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)

    # 2. Create or fetch user
    user = db_session.query(User).filter(User.tenant_id == tenant.id, User.login == "fuzz_admin").first()
    if not user:
        user = User(
            tenant_id=tenant.id,
            login="fuzz_admin",
            password_hash="fuzz_fake_hash",
            role="owner"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    return tenant, user

@schema.parametrize()
@settings(
    max_examples=1,
    deadline=None,
    report_multiple_bugs=False,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_api_fuzzing(case, client, setup_fuzz_data):
    """Dynamically test every OpenAPI endpoint against unhandled internal server crashes."""
    tenant, user = setup_fuzz_data

    # 2. Generate authorization tokens
    admin_token = create_access_token({"sub": str(user.id)})
    public_token = create_access_token({"sub": TENANT_SUBDOMAIN})

    # 3. Inject standard headers based on endpoint scoping rules
    headers = {
        "X-Tenant": TENANT_SUBDOMAIN
    }
    
    if "/api/admin/" in case.path:
        headers["X-Token"] = admin_token
    elif "/api/public/" in case.path:
        headers["X-Token"] = public_token
    else:
        # Fallback to admin auth for non-prefixed paths unless they are health checks
        if case.path not in ("/health", "/ready", "/version", "/openapi.json"):
            headers["X-Token"] = admin_token

    # Override headers on this case run
    case.headers = headers

    # Helper to strip Schemathesis NotSet sentinels recursively
    def strip_not_set(val):
        if val.__class__.__name__ == "NotSet" or val is None:
            return None
        if isinstance(val, dict):
            return {k: strip_not_set(v) for k, v in val.items() if v.__class__.__name__ != "NotSet"}
        if isinstance(val, list):
            return [strip_not_set(v) for v in val if v.__class__.__name__ != "NotSet"]
        return val

    clean_headers = strip_not_set(case.headers) or {}
    clean_params = strip_not_set(case.query)
    clean_body = strip_not_set(case.body)

    kwargs = {}
    if clean_params:
        kwargs["params"] = clean_params
    if clean_body is not None:
        kwargs["json"] = clean_body

    # 4. Invoke the request via the pytest client (TestClient) to ensure dependency overrides are respected
    response = client.request(
        method=case.method,
        url=case.formatted_path,
        headers=clean_headers,
        **kwargs
    )

    # 5. Core validation: Ensure the API handled the input gracefully without returning HTTP 500
    assert response.status_code < 500, (
        f"CRASH DETECTED on {case.method} {case.formatted_path}\n"
        f"Status: {response.status_code}\n"
        f"Payload: {clean_body}\n"
        f"Headers: {clean_headers}\n"
        f"Response: {response.text}"
    )
