"""Regression tests for bounded integer IDs and driver overflow safety.

Verifies that requests containing oversized numeric identifiers (e.g., exceeding
SQL 32-bit INTEGER or 64-bit BIGINT bounds) are handled gracefully with HTTP 404
or 422, and never produce an unhandled database exception or HTTP 500 error.
"""

import pytest
from app.core.security import create_access_token
from app.models.tenant import Tenant
from app.models.user import User

OVERSIZED_IDS = [
    2147483648,  # > int32 max (2**31 - 1)
    9223372036854775807,  # int64 max (2**63 - 1)
    9223372036854775808,  # > int64 max (SQLite INTEGER Overflow threshold)
    10**30,  # Arbitrary multi-precision integer
]

TEST_ENDPOINTS = [
    "/api/admin/services/{id}",
    "/api/admin/providers/{id}",
    "/api/admin/clients/{id}",
    "/api/admin/locations/{id}",
    "/api/admin/bookings/{id}",
    "/api/admin/categories/{id}",
    "/api/admin/addons/{id}",
    "/api/admin/products/{id}",
    "/api/admin/packages/{id}",
    "/api/admin/management-reviews/{id}",
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


@pytest.mark.parametrize("endpoint_template", TEST_ENDPOINTS)
@pytest.mark.parametrize("oversized_id", OVERSIZED_IDS)
def test_oversized_numeric_id_never_500(client, auth_headers, endpoint_template, oversized_id):
    """Ensure querying any resource with huge integer ID never crashes the server."""
    url = endpoint_template.format(id=oversized_id)
    response = client.get(url, headers=auth_headers)
    assert response.status_code in (404, 422), (
        f"Expected safe client error (404/422) for {url}, got {response.status_code}: {response.text}"
    )
    assert response.status_code < 500
