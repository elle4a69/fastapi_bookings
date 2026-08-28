"""Comprehensive regression tests for numeric ID bounds and validation gates.

Proves:
1. Oversized numeric path IDs (> MAX_DATABASE_ID or < 1) are rejected at FastAPI request validation with HTTP 422.
2. The router handler and database query are NOT invoked for out-of-range IDs.
3. Valid in-range nonexistent IDs follow normal HTTP 404 NOT_FOUND contract.
4. Genuine unexpected database exceptions (such as DataError or OperationalError) produce HTTP 500 and are NOT masked as 404.
5. All discovered database-backed numeric path routes reject out-of-range values.
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DataError, OperationalError
from app.api.deps import MAX_DATABASE_ID
from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User

OVERSIZED_IDS = [
    MAX_DATABASE_ID + 1,  # 9223372036854775808 (> signed 64-bit int max)
    10**30,                # Arbitrary multi-precision Python integer
]

INVALID_IDS = [
    0,                     # < 1
    -1,                    # Negative
]

# Database-backed numeric path parameter GET routes across the application
ADMIN_GET_ID_ROUTES = [
    "/api/admin/services/{id}",
    "/api/admin/clients/{id}",
    "/api/admin/locations/{id}",
    "/api/admin/bookings/{id}",
    "/api/admin/categories/{id}",
    "/api/admin/add-ons/{id}",
    "/api/admin/products/{id}",
    "/api/admin/packages/{id}",
    "/api/admin/resources/{id}",
    "/api/admin/management-reviews/{id}",
    "/api/admin/series/{id}",
    "/api/admin/booking-forms/{id}",
    "/api/admin/sms/accounts/{id}",
    "/api/admin/sms/conversations/{id}",
    "/api/admin/sms/settings/knowledge/{id}",
    "/api/admin/sms/settings/prompts/{id}",
    "/api/admin/sms/chatwoot/bindings/{id}",
]

# Database-backed numeric path parameter mutating (PUT/POST/DELETE) routes
ADMIN_MUTATING_ID_ROUTES = [
    ("PUT", "/api/admin/payments/{id}"),
    ("PUT", "/api/admin/webhooks/{id}"),
    ("PUT", "/api/admin/calendar-notes/{id}"),
    ("PUT", "/api/admin/additional-fields/{id}"),
    ("POST", "/api/admin/sms/conversations/jobs/{id}/retry"),
    ("POST", "/api/admin/sms/conversations/messages/{id}/approve"),
    ("POST", "/api/admin/bookings/{id}/cancel"),
]


@pytest.fixture
def auth_headers(db_session):
    tenant = db_session.query(Tenant).filter(Tenant.subdomain == "boundstest").first()
    if not tenant:
        tenant = Tenant(name="Bounds Test Tenant", subdomain="boundstest")
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)

    user = db_session.query(User).filter(User.tenant_id == tenant.id, User.login == "bound_admin").first()
    if not user:
        user = User(tenant_id=tenant.id, login="bound_admin", password_hash="fake", role="owner")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return {
        "X-Tenant": "boundstest",
        "X-Token": token,
    }


@pytest.mark.parametrize("endpoint_template", ADMIN_GET_ID_ROUTES)
@pytest.mark.parametrize("oversized_id", OVERSIZED_IDS)
def test_oversized_numeric_id_rejected_at_validation(client, auth_headers, endpoint_template, oversized_id):
    """Ensure oversized numeric path IDs return HTTP 422 VALIDATION_ERROR before database execution."""
    url = endpoint_template.format(id=oversized_id)
    response = client.get(url, headers=auth_headers)
    assert response.status_code == 422, f"Expected 422 for {url}, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["ok"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("method,endpoint_template", ADMIN_MUTATING_ID_ROUTES)
@pytest.mark.parametrize("oversized_id", OVERSIZED_IDS)
def test_mutating_oversized_numeric_id_rejected_at_validation(client, auth_headers, method, endpoint_template, oversized_id):
    """Ensure mutating endpoints with oversized path IDs return HTTP 422 VALIDATION_ERROR."""
    url = endpoint_template.format(id=oversized_id)
    response = client.request(method, url, headers=auth_headers, json={})
    assert response.status_code == 422, f"Expected 422 for {method} {url}, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["ok"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("endpoint_template", ADMIN_GET_ID_ROUTES)
@pytest.mark.parametrize("invalid_id", INVALID_IDS)
def test_non_positive_numeric_id_rejected_at_validation(client, auth_headers, endpoint_template, invalid_id):
    """Ensure non-positive integer path IDs (< 1) return HTTP 422 VALIDATION_ERROR."""
    url = endpoint_template.format(id=invalid_id)
    response = client.get(url, headers=auth_headers)
    assert response.status_code == 422, f"Expected 422 for {url}, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["ok"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("method,endpoint_template", ADMIN_MUTATING_ID_ROUTES)
@pytest.mark.parametrize("invalid_id", INVALID_IDS)
def test_mutating_non_positive_numeric_id_rejected_at_validation(client, auth_headers, method, endpoint_template, invalid_id):
    """Ensure mutating endpoints with non-positive integer path IDs (< 1) return HTTP 422 VALIDATION_ERROR."""
    url = endpoint_template.format(id=invalid_id)
    response = client.request(method, url, headers=auth_headers, json={})
    assert response.status_code == 422, f"Expected 422 for {method} {url}, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["ok"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_router_handler_not_invoked_for_oversized_id(client, auth_headers):
    """Verify that route handlers are NEVER invoked when an invalid path parameter is provided."""
    with patch("app.models.service.Service.__table__.select") as mock_select:
        response = client.get(f"/api/admin/services/{MAX_DATABASE_ID + 1}", headers=auth_headers)
        assert response.status_code == 422
        mock_select.assert_not_called()


@pytest.mark.parametrize("endpoint_template", [
    "/api/admin/services/{id}",
    "/api/admin/clients/{id}",
    "/api/admin/locations/{id}",
    "/api/admin/categories/{id}",
    "/api/admin/add-ons/{id}",
    "/api/admin/products/{id}",
    "/api/admin/packages/{id}",
])
def test_valid_in_range_nonexistent_id_returns_404(client, auth_headers, endpoint_template):
    """Verify that a valid in-range ID that does not exist in DB returns HTTP 404 NOT_FOUND."""
    url = endpoint_template.format(id=MAX_DATABASE_ID)  # Valid max positive 64-bit int
    response = client.get(url, headers=auth_headers)
    assert response.status_code == 404, f"Expected 404 for {url}, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["ok"] is False
    assert data["error"]["code"] == "NOT_FOUND"


def test_unrelated_database_data_error_not_masked_as_404(client, auth_headers, db_session):
    """Verify that genuine unexpected database DataError returns HTTP 500 and is NOT converted to 404."""
    unhandled_client = TestClient(client.app, raise_server_exceptions=False)
    with patch.object(db_session, "query", side_effect=DataError("statement", "params", "orig")):
        response = unhandled_client.get("/api/admin/services/1", headers=auth_headers)
        assert response.status_code == 500, f"Expected 500, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["ok"] is False
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"


def test_unrelated_database_operational_error_returns_500(client, auth_headers, db_session):
    """Verify that unexpected database OperationalError returns HTTP 500."""
    unhandled_client = TestClient(client.app, raise_server_exceptions=False)
    with patch.object(db_session, "query", side_effect=OperationalError("statement", "params", "orig")):
        response = unhandled_client.get("/api/admin/services/1", headers=auth_headers)
        assert response.status_code == 500, f"Expected 500, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["ok"] is False
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"


def test_providers_string_route_oversized_bounds_check(client, auth_headers):
    """Verify providers endpoint with string prefix handles oversized integers safely as 404."""
    response = client.get(f"/api/admin/providers/{MAX_DATABASE_ID + 1}", headers=auth_headers)
    assert response.status_code == 404
    data = response.json()
    assert data["ok"] is False
    assert data["error"]["code"] == "NOT_FOUND"


def test_relationship_create_and_connect_route_precedence(client, auth_headers, db_session):
    """Prove literal 'create-and-connect' subpath is not shadowed by dynamic '{right_id}' route."""
    from app.models.provider import Provider as ProviderModel
    tenant = db_session.query(Tenant).filter(Tenant.subdomain == "boundstest").first()
    provider = ProviderModel(tenant_id=tenant.id, name="Dr. Precedence", active=True)
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)

    payload = {
        "record": {
            "name": "Precedence Service",
            "duration": 45,
            "price": 75.0,
            "active": True,
        }
    }
    response = client.post(
        f"/api/admin/relationships/provider/{provider.id}/service/create-and-connect",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Expected 201 Created, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["ok"] is True
    assert "record" in data["data"]
    assert data["data"]["record"]["name"] == "Precedence Service"
    assert "relationship_id" in data["data"]


def test_relationship_dynamic_link_and_bounds(client, auth_headers, db_session):
    """Prove dynamic relationship linking accepts valid DatabaseIds and rejects oversized IDs at validation."""
    from app.models.provider import Provider as ProviderModel
    from app.models.service import Service as ServiceModel

    tenant = db_session.query(Tenant).filter(Tenant.subdomain == "boundstest").first()
    provider = ProviderModel(tenant_id=tenant.id, name="Dr. Dynamic", active=True)
    service = ServiceModel(tenant_id=tenant.id, name="Dynamic Service", duration=30, price=50.0, active=True)
    db_session.add_all([provider, service])
    db_session.commit()
    db_session.refresh(provider)
    db_session.refresh(service)

    # 1. Valid link creation
    response = client.post(
        f"/api/admin/relationships/provider/{provider.id}/service/{service.id}",
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["ok"] is True

    # 2. Oversized right_id rejected at validation (422)
    response = client.post(
        f"/api/admin/relationships/provider/{provider.id}/service/{MAX_DATABASE_ID + 1}",
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    # 3. Valid unlink
    response = client.delete(
        f"/api/admin/relationships/provider/{provider.id}/service/{service.id}",
        headers=auth_headers,
    )
    assert response.status_code == 204
