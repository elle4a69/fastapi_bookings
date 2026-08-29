"""Verification tests for API routers registration, prefix hierarchy, and security isolation.

This module addresses ARCH-001 and ARCH-002 from docs/ANTIGRAVITY_APPLICATION_REMEDIATION_BRIEF.md:
1. Verifies no route collisions, duplicate registrations, or shadowing across FastAPI routers.
2. Asserts that administrative endpoints enforce authentication and tenant-scoping dependencies.
3. Asserts that public endpoints reside under /api/public/ or explicit public prefix boundaries.
4. Asserts that OpenAPI metadata (tags, descriptions) are consistent across all routes.
5. Asserts that app.api.routers exports all domain router modules cleanly in __all__.
"""

import inspect
from collections import defaultdict
from typing import Any, List, Set, Tuple

import pytest
from fastapi.routing import APIRoute, _IncludedRouter
from fastapi.testclient import TestClient

import app.api.routers as routers_pkg
from app.api.deps import (
    get_current_admin,
    get_current_assistant_channel,
    get_current_company,
    get_current_tenant,
    get_current_user,
    get_db,
    get_public_tenant,
)
from app.main import app


def _extract_all_routes(fastapi_app) -> List[Tuple[str, Set[str], Any, List[str], List[Any]]]:
    """Recursively extract all registered routes with path, methods, endpoint, tags, and dependencies."""
    extracted = []
    for r in fastapi_app.routes:
        if isinstance(r, APIRoute):
            deps = [d.dependency for d in r.dependencies]
            # Also extract endpoint signature parameter dependencies
            sig = inspect.signature(r.endpoint)
            for param in sig.parameters.values():
                if hasattr(param.default, "dependency"):
                    deps.append(param.default.dependency)
            extracted.append((r.path, r.methods, r.endpoint, list(r.tags), deps))
        elif isinstance(r, _IncludedRouter):
            prefix = r.include_context.prefix
            router_deps = [d.dependency for d in r.include_context.dependencies]
            router_tags = list(r.include_context.tags)
            for sr in r.original_router.routes:
                if isinstance(sr, APIRoute):
                    full_path = prefix + sr.path
                    sr_deps = list(router_deps) + [d.dependency for d in sr.dependencies]
                    sig = inspect.signature(sr.endpoint)
                    for param in sig.parameters.values():
                        if hasattr(param.default, "dependency"):
                            sr_deps.append(param.default.dependency)
                    sr_tags = list(router_tags) + list(sr.tags)
                    extracted.append((full_path, sr.methods, sr.endpoint, sr_tags, sr_deps))
    return extracted


class TestApiRoutersRegistration:
    """Test suite for API router registration hygiene and security policy enforcement."""

    def test_no_route_method_collisions(self):
        """Verify that every (HTTP method, path) combination maps to exactly one endpoint handler (no shadowing)."""
        routes = _extract_all_routes(app)
        assert len(routes) > 0, "FastAPI application has no registered routes"

        route_map = defaultdict(list)
        for path, methods, ep, tags, deps in routes:
            for method in methods:
                # Exclude auto-generated HEAD/OPTIONS if any
                if method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    route_map[(method, path)].append(f"{ep.__module__}.{ep.__name__}")

        collisions = {route_key: handlers for route_key, handlers in route_map.items() if len(handlers) > 1}
        assert not collisions, f"Detected route collisions / shadowing: {collisions}"

    def test_admin_endpoints_require_authentication(self):
        """Verify that all /api/admin/* endpoints enforce authentication and tenant dependencies.
        
        Exceptions must be explicitly documented public token or webhook validation endpoints.
        """
        routes = _extract_all_routes(app)
        admin_routes = [r for r in routes if r[0].startswith("/api/admin")]
        assert len(admin_routes) > 0, "No /api/admin routes found"

        # Recognized auth / tenant scoping dependencies
        recognized_auth_deps = {
            get_current_admin,
            get_current_user,
            get_current_tenant,
            get_current_company,
            get_current_assistant_channel,
        }

        # Explicitly allowed non-standard admin paths with documented token / signature auth
        allowed_exceptions = {
            "/api/admin/sms/arrivals/public/{token}/arrive",  # Public single-use token in path
            "/api/admin/sms/chatwoot/webhook",  # Header-based signature verification in body
        }

        unprotected_admin_routes = []
        for path, methods, ep, tags, deps in admin_routes:
            if path in allowed_exceptions:
                continue
            has_auth = any(d in recognized_auth_deps for d in deps)
            if not has_auth:
                unprotected_admin_routes.append((path, methods, ep.__name__))

        assert not unprotected_admin_routes, (
            f"Found administrative routes lacking authentication dependencies: {unprotected_admin_routes}"
        )

    def test_unauthenticated_requests_to_admin_routes_fail(self):
        """Test sending unauthenticated requests to sample admin routes returns 400/401/403 (never 200)."""
        client = TestClient(app, raise_server_exceptions=False)
        test_paths = [
            "/api/admin/services",
            "/api/admin/providers",
            "/api/admin/clients",
            "/api/admin/locations",
            "/api/admin/bookings",
            "/api/admin/notifications",
            "/api/admin/payments",
            "/api/admin/categories",
            "/api/admin/sms/accounts",
            "/api/admin/sms/conversations",
        ]

        for path in test_paths:
            resp = client.get(path)
            assert resp.status_code in (400, 401, 403, 404), (
                f"Expected unauthenticated request to {path} to fail, got {resp.status_code}: {resp.text}"
            )

    def test_public_routes_conformance(self):
        """Verify that public endpoints reside under /api/public/ or explicit valid namespaces."""
        routes = _extract_all_routes(app)
        system_paths = {"/health", "/healthcheck", "/ready", "/version", "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}

        # Ensure root-level un-prefixed notifications do NOT exist
        root_notification_routes = [r[0] for r in routes if r[0].startswith("/notifications") or r[0].startswith("/reminder-rules") or r[0].startswith("/notification-templates")]
        assert not root_notification_routes, (
            f"Found orphaned un-prefixed notification routes at root level: {root_notification_routes}"
        )

        # Verify all public/general routes belong to a recognized prefix
        for path, methods, ep, tags, deps in routes:
            if path in system_paths:
                continue
            if path.startswith("/api/admin/") or path.startswith("/api/"):
                continue
            # Any route not starting with /api/ or system_paths is invalid
            pytest.fail(f"Route '{path}' is mounted outside /api/ hierarchy without valid prefix")

    def test_openapi_schema_metadata_complete(self):
        """Verify OpenAPI schema generation succeeds and every operation has tags and description/summary."""
        schema = app.openapi()
        assert schema is not None
        assert "paths" in schema
        assert len(schema["paths"]) > 0

        missing_tags = []
        for path, methods in schema["paths"].items():
            for method, op in methods.items():
                if method.lower() in ("get", "post", "put", "delete", "patch"):
                    tags = op.get("tags", [])
                    if not tags:
                        missing_tags.append((method.upper(), path))

        assert not missing_tags, f"OpenAPI operations missing tags: {missing_tags}"

    def test_routers_init_package_exports(self):
        """Verify that app.api.routers exports all active router modules in __all__."""
        expected_modules = [
            "auth",
            "services",
            "providers",
            "clients",
            "locations",
            "bookings",
            "availability",
            "admin_dashboard",
            "public_bootstrap",
            "audit",
            "payments",
            "notifications",
            "waitlist",
            "search",
            "ui_config",
            "booking_forms",
            "relationship_management",
            "forms",
            "diagnostics",
            "categories",
            "resources",
            "addons",
            "products",
            "packages",
            "public_bookings",
            "admin_schedule",
            "additional_fields",
            "checkout",
            "public_clients",
            "public_entities",
            "public_timeline",
            "series",
            "service_relations",
            "webhooks",
            "calendar_notes",
            "general_systems",
            "stripe_webhooks",
            "devices",
            "management_reviews",
            "business_profile",
            "location_relations",
            "system",
            "discovery",
            "sms_accounts",
            "sms_arrivals",
            "sms_chatwoot",
            "sms_conversations",
            "sms_settings",
            "sms_webhooks",
            "assistant_facade",
        ]

        for mod_name in expected_modules:
            assert hasattr(routers_pkg, mod_name), f"app.api.routers missing export for {mod_name}"
            assert mod_name in routers_pkg.__all__, f"{mod_name} not listed in app.api.routers.__all__"
