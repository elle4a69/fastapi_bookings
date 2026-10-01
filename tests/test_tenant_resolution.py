"""Tenant subdomain resolution tests — Phase 5: Platform Governance.

Verifies that ``_tenant_subdomain_from_host`` in ``app/api/deps.py`` correctly:
  - Extracts subdomain from RFC 6761 ``*.localhost`` hosts with and without ports.
  - Falls back to the ``X-Tenant`` header when no subdomain is present.
  - Returns HTTP 404 for unknown (non-existent) subdomains.
  - Returns HTTP 400 when host-based and header-based tenant contexts disagree.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import _tenant_subdomain_from_host
from app.main import app as fastapi_app
from app.db.database import get_db
from app.models.tenant import Tenant


# ---------------------------------------------------------------------------
# Pure unit tests for _tenant_subdomain_from_host
# ---------------------------------------------------------------------------


class TestSubdomainExtraction:
    """Unit tests for the subdomain extraction helper."""

    def test_localhost_with_port_8000(self):
        """tenant1.localhost:8000 → subdomain 'tenant1'."""
        assert _tenant_subdomain_from_host("tenant1.localhost:8000") == "tenant1"

    def test_localhost_with_port_7070(self):
        """tenant2.localhost:7070 → subdomain 'tenant2'."""
        assert _tenant_subdomain_from_host("tenant2.localhost:7070") == "tenant2"

    def test_localhost_no_port(self):
        """tenant2.localhost → subdomain 'tenant2'."""
        assert _tenant_subdomain_from_host("tenant2.localhost") == "tenant2"

    def test_simplydemo_localhost_with_port(self):
        """simplydemo.localhost:8000 → subdomain 'simplydemo'."""
        assert _tenant_subdomain_from_host("simplydemo.localhost:8000") == "simplydemo"

    def test_clinic_localhost(self):
        """clinic.localhost → subdomain 'clinic'."""
        assert _tenant_subdomain_from_host("clinic.localhost") == "clinic"

    def test_bare_localhost_returns_none(self):
        """localhost (no subdomain) → None."""
        assert _tenant_subdomain_from_host("localhost") is None

    def test_bare_localhost_with_port_returns_none(self):
        """localhost:8000 (no subdomain) → None."""
        assert _tenant_subdomain_from_host("localhost:8000") is None

    def test_cloud_run_domain_returns_none(self):
        """.run.app Cloud Run domain → None."""
        assert _tenant_subdomain_from_host("myservice-xyz.run.app") is None

    def test_www_subdomain_excluded(self):
        """www.example.com → None (reserved label)."""
        assert _tenant_subdomain_from_host("www.example.com") is None

    def test_api_subdomain_excluded(self):
        """api.example.com → None (reserved label)."""
        assert _tenant_subdomain_from_host("api.example.com") is None

    def test_three_label_host_extracts_first(self):
        """simplydemo.dev.localhost → subdomain 'simplydemo'."""
        assert _tenant_subdomain_from_host("simplydemo.dev.localhost") == "simplydemo"

    def test_production_fqdn(self):
        """myclinic.bookopenapi.com → subdomain 'myclinic'."""
        assert _tenant_subdomain_from_host("myclinic.bookopenapi.com") == "myclinic"

    def test_bare_two_label_production_returns_none(self):
        """bookopenapi.com (no tenant label) → None."""
        assert _tenant_subdomain_from_host("bookopenapi.com") is None

    def test_empty_hostname_returns_none(self):
        assert _tenant_subdomain_from_host("") is None

    def test_none_hostname_returns_none(self):
        assert _tenant_subdomain_from_host(None) is None

    def test_uppercase_hostname_normalised(self):
        """Case is normalised to lowercase before comparison."""
        result = _tenant_subdomain_from_host("SimplyCLINIC.localhost:8000")
        assert result == "simplyclinic"


# ---------------------------------------------------------------------------
# Integration tests using TestClient against a real in-memory DB
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_with_tenant(db_session):
    """Provide a TestClient with a known tenant 'acmecorp' seeded in the database."""
    tenant = Tenant(name="Acme Corp", subdomain="acmecorp")
    db_session.add(tenant)
    db_session.commit()

    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app, raise_server_exceptions=False) as c:
        yield c, tenant
    fastapi_app.dependency_overrides.clear()


def _extract_error_message(body: dict) -> str:
    """Extract the error message from the app's error envelope or fallback to detail."""
    # App wraps errors in {"ok": false, "error": {"code": ..., "message": ...}}
    err = body.get("error")
    if isinstance(err, dict):
        return (err.get("message") or "").lower()
    # Fallback to FastAPI default shape
    return (body.get("detail") or "").lower()


class TestSubdomainIntegration:
    """End-to-end HTTP integration tests for tenant resolution."""

    def test_xheader_fallback_resolves_known_tenant(self, client_with_tenant):
        """X-Tenant header fallback resolves an existing tenant (HTTP 200 or 200-range)."""
        test_client, tenant = client_with_tenant
        resp = test_client.get(
            "/api/public/translations",
            headers={"X-Tenant": tenant.subdomain},
        )
        # The translations endpoint should succeed (200 or 404 for missing data)
        # but must NOT be a tenant-resolution 400 or 404-by-tenant error.
        assert resp.status_code in {200, 404}
        if resp.status_code == 404:
            body = resp.json()
            # 404 here means the translations record is missing, not tenant missing
            msg = _extract_error_message(body)
            assert tenant.subdomain not in msg or "not found" not in msg

    def test_unknown_subdomain_returns_404(self, client_with_tenant):
        """An unregistered subdomain slug must result in HTTP 404."""
        test_client, _ = client_with_tenant
        resp = test_client.get(
            "/api/public/translations",
            headers={"X-Tenant": "this-tenant-does-not-exist-xyz"},
        )
        assert resp.status_code == 404
        body = resp.json()
        msg = _extract_error_message(body)
        assert "not found" in msg

    def test_missing_tenant_context_returns_400(self, client_with_tenant):
        """No subdomain and no X-Tenant header must result in HTTP 400."""
        test_client, _ = client_with_tenant
        resp = test_client.get("/api/public/translations")
        assert resp.status_code == 400
        body = resp.json()
        msg = _extract_error_message(body)
        assert "tenant" in msg

    def test_host_and_xheader_mismatch_returns_400(self, client_with_tenant):
        """Conflicting host subdomain and X-Tenant header must result in HTTP 400."""
        test_client, _ = client_with_tenant
        # Supply a Host header with a subdomain AND a mismatching X-Tenant header
        resp = test_client.get(
            "/api/public/translations",
            headers={
                "Host": "acmecorp.localhost:8000",
                "X-Tenant": "othertenant",
            },
        )
        assert resp.status_code == 400
        body = resp.json()
        msg = _extract_error_message(body)
        assert "match" in msg or "mismatch" in msg or "do not match" in msg
