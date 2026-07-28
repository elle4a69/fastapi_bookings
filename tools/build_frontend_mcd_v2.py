"""Generate and validate the FastAPI Bookings frontend MCD v2.

The report is derived from the current OpenAPI document, SQLAlchemy metadata,
router source locations, and test inventory.  It deliberately avoids invented
request/response examples; contracts are represented by canonical schema refs.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

os.environ.setdefault("OTEL_SDK_DISABLED", "true")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OPENAPI_PATH = ROOT / "openapi.json"
MANIFEST_PATH = ROOT / "contracts" / "route-manifest.json"
OUTPUT_PATH = ROOT / "fastapi_bookings_frontend_mcd_v2.md"

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
ALLOWED_CLASSES = {
    "directly represented",
    "indirectly used by another workflow",
    "administrative or system-only",
    "intentionally excluded",
    "deprecated",
    "unresolved",
}


FRONTEND_ROUTES = [
    ("Public", "/discover", "Discovery map and accessible list", "Public", "discovery"),
    ("Public", "/book/:formSlug", "Tenant booking surface", "Public token via BFF", "booking-forms-widget"),
    ("Public", "/book/:formSlug/details", "Dynamic intake and client details", "Public token via BFF", "additional-fields"),
    ("Public", "/book/:formSlug/checkout", "Quote, promotion and checkout", "Public token via BFF", "checkout"),
    ("Public", "/book/:formSlug/outcome", "Request outcome", "Navigation state", "public-bookings"),
    ("Public dev-only", "/dev/:tenantSlug/book/:formSlug", "Explicit tenant override", "Development only", "tenancy"),
    ("Client", "/client/login", "Client login", "Public token", "public-clients"),
    ("Client", "/client/register", "Client registration", "Public token", "public-clients"),
    ("Client", "/client/password-reset", "Password reset request", "Public token", "public-clients"),
    ("Client", "/client/profile", "Client profile", "Client subject through X-Token", "public-clients"),
    ("Client", "/client/terms", "Terms and consent", "Client/public subject", "public-gdpr"),
    ("Admin", "/admin/login", "Administrative login", "Credentials exchange", "auth"),
    ("Admin", "/admin/role-not-enabled", "Staff/viewer denial", "Authenticated unsupported role", "auth"),
    ("Admin", "/admin", "Operational dashboard", "Owner/admin", "dashboard"),
    ("Admin", "/admin/calendar", "Calendar and schedule", "Owner/admin", "schedule"),
    ("Admin", "/admin/bookings", "Booking list", "Owner/admin", "bookings"),
    ("Admin", "/admin/bookings/:bookingId", "Booking detail and transitions", "Owner/admin", "bookings"),
    ("Admin", "/admin/booking-forms", "Booking-form list", "Owner/admin", "booking-forms-admin"),
    ("Admin", "/admin/booking-forms/new", "Booking-form creation", "Owner/admin", "booking-forms-admin"),
    ("Admin", "/admin/booking-forms/:formId", "Booking-form editor/design/embed", "Owner/admin", "booking-forms-admin"),
    ("Admin", "/admin/catalog/services", "Services", "Owner/admin", "services"),
    ("Admin", "/admin/catalog/providers", "Providers", "Owner/admin", "providers"),
    ("Admin", "/admin/catalog/locations", "Locations", "Owner/admin", "locations"),
    ("Admin", "/admin/catalog/categories", "Categories", "Owner/admin", "categories"),
    ("Admin", "/admin/catalog/add-ons", "Add-ons", "Owner/admin", "add-ons"),
    ("Admin", "/admin/catalog/products", "Products", "Owner/admin", "products"),
    ("Admin", "/admin/catalog/packages", "Packages and steps", "Owner/admin", "packages"),
    ("Admin", "/admin/resources", "Resources and requirements", "Owner/admin", "resources"),
    ("Admin", "/admin/relationships", "Cross-entity relationship editor", "Owner/admin", "relationship-management"),
    ("Admin", "/admin/schedule/workdays", "Workdays", "Owner/admin", "schedule"),
    ("Admin", "/admin/schedule/exceptions", "Special, blocked and reserved time", "Owner/admin", "schedule"),
    ("Admin", "/admin/clients", "Client list", "Owner/admin", "clients"),
    ("Admin", "/admin/clients/:clientId", "Client detail and compliance", "Owner/admin", "clients"),
    ("Admin", "/admin/configuration/additional-fields", "Additional fields", "Owner/admin", "additional-fields"),
    ("Admin", "/admin/finance/invoices", "Invoices", "Owner/admin", "checkout"),
    ("Admin", "/admin/finance/payments", "Payments", "Owner/admin", "payments"),
    ("Admin", "/admin/finance/promotions", "Promotions", "Owner/admin", "checkout"),
    ("Admin", "/admin/finance/tax-rates", "Tax rates", "Owner/admin", "checkout"),
    ("Admin", "/admin/finance/processors", "Payment processors", "Owner/admin", "checkout"),
    ("Admin", "/admin/notifications/messages", "Notifications", "Owner/admin", "notifications"),
    ("Admin", "/admin/notifications/templates", "Notification templates", "Owner/admin", "notification-templates"),
    ("Admin", "/admin/notifications/reminders", "Reminder rules", "Owner/admin", "reminder-rules"),
    ("Admin", "/admin/reviews", "Management reviews", "Owner/admin", "management-reviews"),
    ("Admin", "/admin/audit", "Audit log", "Owner/admin", "audit"),
    ("Admin", "/admin/compliance/gdpr", "GDPR consent records", "Owner/admin", "system"),
    ("Admin", "/admin/settings/business", "Business profile", "Owner/admin", "business-profile"),
    ("Admin", "/admin/settings/webhooks", "Webhooks", "Owner/admin", "webhooks"),
    ("Admin", "/admin/settings/plugins", "Plugin states", "Owner/admin", "system"),
    ("Admin", "/admin/system", "Diagnostics and maintenance", "Owner/admin", "system-admin"),
    ("Error", "/403", "Permission denied", "Any", "errors"),
    ("Error", "/404", "Not found", "Any", "errors"),
    ("Error", "*", "Route fallback", "Any", "errors"),
]


TAG_ROUTE = {
    "add-ons": ("Catalog / add-ons", "/admin/catalog/add-ons"),
    "additional-fields": ("Additional fields", "/admin/configuration/additional-fields"),
    "audit": ("Audit", "/admin/audit"),
    "auth": ("Authentication", "/admin/login"),
    "availability": ("Public availability", "/book/:formSlug"),
    "booking-forms-admin": ("Booking-form administration", "/admin/booking-forms"),
    "booking-forms-widget": ("Public booking form", "/book/:formSlug"),
    "bookings": ("Booking operations", "/admin/bookings"),
    "business-profile": ("Business profile", "/admin/settings/business"),
    "calendar-notes": ("Calendar", "/admin/calendar"),
    "categories": ("Catalog / categories", "/admin/catalog/categories"),
    "checkout": ("Checkout and finance", "/admin/finance/invoices"),
    "clients": ("Client administration", "/admin/clients"),
    "dashboard": ("Dashboard", "/admin"),
    "devices": ("Notification device registration", "/admin/notifications/messages"),
    "discovery": ("Discovery", "/discover"),
    "forms": ("Generated form metadata", "/book/:formSlug/details"),
    "holds": ("Public booking hold", "/book/:formSlug/checkout"),
    "location-relationships": ("Relationship editor", "/admin/relationships"),
    "locations": ("Catalog / locations", "/admin/catalog/locations"),
    "management-reviews": ("Management reviews", "/admin/reviews"),
    "notification-templates": ("Notification templates", "/admin/notifications/templates"),
    "notifications": ("Notifications", "/admin/notifications/messages"),
    "packages": ("Catalog / packages", "/admin/catalog/packages"),
    "payments": ("Payments", "/admin/finance/payments"),
    "products": ("Catalog / products", "/admin/catalog/products"),
    "providers": ("Catalog / providers", "/admin/catalog/providers"),
    "public": ("Public booking bootstrap", "/book/:formSlug"),
    "public-bookings": ("Public booking", "/book/:formSlug/outcome"),
    "public-clients": ("Client account", "/client/profile"),
    "public-gdpr": ("Client consent", "/client/terms"),
    "public-timeline": ("Public availability", "/book/:formSlug"),
    "relationship-management": ("Relationship editor", "/admin/relationships"),
    "reminder-rules": ("Reminder rules", "/admin/notifications/reminders"),
    "resources": ("Resources", "/admin/resources"),
    "schedule": ("Schedule", "/admin/calendar"),
    "search-availability": ("Public availability", "/book/:formSlug"),
    "series": ("Booking series", "/admin/bookings"),
    "service-relations": ("Relationship editor", "/admin/relationships"),
    "services": ("Catalog / services", "/admin/catalog/services"),
    "stripe": ("Payment integration", "/admin/finance/payments"),
    "system": ("System and compliance", "/admin/system"),
    "system-admin": ("System maintenance", "/admin/system"),
    "ui-config": ("Deprecated compatibility", "N/A"),
    "waitlist": ("Public waitlist", "/book/:formSlug/outcome"),
    "webhooks": ("Webhooks", "/admin/settings/webhooks"),
}


RELATED_TESTS = {
    "auth": ["tests/test_multi_tenancy.py", "tests/test_audit_resolution.py"],
    "booking-forms-admin": ["tests/test_configurable_booking_forms.py", "tests/test_booking_form_contracts.py"],
    "booking-forms-widget": ["tests/test_configurable_booking_forms.py", "tests/test_embed_configuration.py"],
    "bookings": ["tests/test_booking_policies_remediation.py", "tests/test_concurrency.py", "tests/test_audit_fixes.py"],
    "availability": ["tests/test_scheduling_intervals.py", "tests/test_scheduling_constraints.py"],
    "public-timeline": ["tests/test_scheduling_intervals.py", "tests/test_scheduling_edge_cases.py"],
    "search-availability": ["tests/test_audit_resolution.py", "tests/test_security_fuzzing.py"],
    "holds": ["tests/test_concurrency.py", "tests/test_audit_fixes.py"],
    "waitlist": ["tests/test_concurrency.py", "tests/test_scheduling_edge_cases.py"],
    "additional-fields": ["tests/test_booking_policies_remediation.py"],
    "public-clients": ["tests/test_multi_tenancy.py"],
    "public": ["tests/test_public_entities_remediation.py"],
    "services": ["tests/test_multi_tenancy.py", "tests/test_scheduling_constraints.py"],
    "providers": ["tests/test_relationships_remediation.py"],
    "categories": ["tests/test_relationships_remediation.py"],
    "locations": ["tests/test_relationships_remediation.py"],
    "location-relationships": ["tests/test_relationships_remediation.py"],
    "relationship-management": ["tests/test_relationships_remediation.py"],
    "service-relations": ["tests/test_relationships_remediation.py"],
    "checkout": ["tests/test_booking_policies_remediation.py", "tests/test_audit_fixes.py"],
    "notification-templates": ["tests/test_notification_configs.py"],
    "reminder-rules": ["tests/test_notification_configs.py"],
    "devices": ["tests/test_phase_5_6_7.py"],
    "stripe": ["tests/test_phase_5_6_7.py"],
    "system-admin": ["tests/test_retention_remediation.py"],
    "audit": ["tests/test_audit_resolution.py"],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def md(value: Any) -> str:
    if value is None:
        return "—"
    # Raw angle brackets in schema labels such as ``array<Foo>`` are parsed as
    # HTML tags by Markdown renderers, which makes ledger cells appear corrupt.
    # Escape HTML-significant characters before applying Markdown table escaping.
    text = (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("|", "\\|")
        .replace("\n", " ")
    )
    return text or "—"


def schema_name(schema: Any) -> str:
    if not schema:
        return "—"
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if schema.get("type") == "array":
        return f"array<{schema_name(schema.get('items'))}>"
    return schema.get("title") or schema.get("type") or "inline schema"


def operation_source_index() -> dict[str, list[tuple[str, int]]]:
    index: dict[str, list[tuple[str, int]]] = {}
    for path in sorted((ROOT / "app" / "api" / "routers").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                index.setdefault(node.name, []).append((path.relative_to(ROOT).as_posix(), node.lineno))
    return index


def endpoint_function(operation_id: str) -> str:
    if "_api_" in operation_id:
        return operation_id.split("_api_", 1)[0]
    suffixes = ("_health_get", "_ready_get", "_version_get", "_notifications_get", "_notifications_post")
    for suffix in suffixes:
        if operation_id.endswith(suffix):
            return operation_id[: -len(suffix)]
    return operation_id.rsplit("_", 1)[0]


def source_for(operation_id: str, index: dict[str, list[tuple[str, int]]]) -> str:
    matches = index.get(endpoint_function(operation_id), [])
    if not matches:
        return "app/main.py or generated route; exact function lookup unresolved"
    if len(matches) == 1:
        return f"{matches[0][0]}:{matches[0][1]}"
    return "; ".join(f"{path}:{line}" for path, line in matches)


def classify(method: str, path: str, deprecated: bool, tags: list[str]) -> str:
    if deprecated:
        return "deprecated"
    if path in {"/health", "/ready", "/version"} or path == "/api/v1/webhooks/stripe":
        return "administrative or system-only"
    if path.startswith(("/notification-templates", "/notifications", "/reminder-rules")):
        return "intentionally excluded"
    if path == "/api/admin/public/bookings":
        return "indirectly used by another workflow"
    if path in {
        "/api/public/auth/token",
        "/api/public/bootstrap",
        "/api/v1/devices/register",
    } or path.startswith("/api/forms/") or path.endswith(("/runtime-manifest", "/embed-config")):
        return "indirectly used by another workflow"
    return "directly represented"


def route_for(path: str, tags: list[str], classification: str) -> tuple[str, str]:
    if classification in {"administrative or system-only", "intentionally excluded", "deprecated"}:
        if path in {"/health", "/ready", "/version"}:
            return "System health", "N/A (monitoring/CI)"
        return "Compatibility/system", "N/A"
    if path == "/api/admin/auth":
        return "Authentication", "/admin/login"
    if path.startswith("/api/public/clients"):
        if path.endswith("/login"):
            return "Client account", "/client/login"
        if path.endswith("/register") or path == "/api/public/clients":
            return "Client account", "/client/register"
        if "password-reset" in path:
            return "Client account", "/client/password-reset"
        if path.endswith("/terms"):
            return "Client account", "/client/terms"
        return "Client account", "/client/profile"
    if path == "/api/public/gdpr-consent":
        return "Client consent", "/client/terms"
    tag = tags[0] if tags else "system"
    return TAG_ROUTE.get(tag, (tag, "/admin/system" if path.startswith("/api/admin") else "/book/:formSlug"))


def auth_policy(path: str, headers: list[str]) -> tuple[str, str]:
    has_token = any(h.lower() == "x-token" for h in headers)
    if path == "/api/admin/auth":
        return "Credentials exchange", "Tenant required"
    if path == "/api/public/auth/token":
        return "Server-side API-key exchange (BFF)", "Tenant required"
    if path == "/api/v1/webhooks/stripe":
        return "Stripe signature/webhook policy", "No browser consumer"
    if path in {"/health", "/ready", "/version"} or path.startswith("/api/discovery/"):
        return "No X-Token declared", "No tenant for global/system route"
    tenant = "Tenant required" if path.startswith(("/api/admin", "/api/public")) else "Verify route implementation"
    if has_token:
        return "X-Token", tenant
    if path.startswith("/api/admin"):
        return "UNGUARDED ADMIN OPERATION — backend gap", tenant
    return "No X-Token declared", tenant


def load_operations(spec: dict[str, Any]) -> list[dict[str, Any]]:
    source_index = operation_source_index()
    operations: list[dict[str, Any]] = []
    for path in sorted(spec["paths"]):
        item = spec["paths"][path]
        for method in sorted(item):
            if method not in HTTP_METHODS:
                continue
            op = item[method]
            tags = list(op.get("tags", []))
            parameters = list(item.get("parameters", [])) + list(op.get("parameters", []))
            headers = [p.get("name", "") for p in parameters if p.get("in") == "header"]
            query = [p.get("name", "") for p in parameters if p.get("in") == "query"]
            path_params = [p.get("name", "") for p in parameters if p.get("in") == "path"]
            request_content = op.get("requestBody", {}).get("content", {})
            request_schema = schema_name(
                request_content.get("application/json", {}).get("schema")
                or next((v.get("schema") for v in request_content.values()), None)
            )
            responses = []
            for code, response in op.get("responses", {}).items():
                content = response.get("content", {})
                schema = content.get("application/json", {}).get("schema") or next(
                    (v.get("schema") for v in content.values()), None
                )
                responses.append(f"{code}:{schema_name(schema)}")
            deprecated = bool(op.get("deprecated"))
            classification = classify(method.upper(), path, deprecated, tags)
            module, frontend_route = route_for(path, tags, classification)
            auth, tenant = auth_policy(path, headers)
            operation_id = op.get("operationId", "")
            tests = sorted({test for tag in tags for test in RELATED_TESTS.get(tag, [])})
            operations.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation_id,
                    "tags": tags,
                    "deprecated": deprecated,
                    "classification": classification,
                    "module": module,
                    "frontend_route": frontend_route,
                    "auth": auth,
                    "tenant": tenant,
                    "headers": headers,
                    "query": query,
                    "path_params": path_params,
                    "request_schema": request_schema,
                    "responses": responses,
                    "source": source_for(operation_id, source_index),
                    "tests": tests,
                }
            )
    return operations


def load_resources() -> list[dict[str, str]]:
    from app.db.database import Base
    import app.models  # noqa: F401

    resources: list[dict[str, str]] = []
    for name, table in sorted(Base.metadata.tables.items()):
        columns = []
        foreign_keys = []
        unique = []
        for column in table.columns:
            flags = []
            if column.primary_key:
                flags.append("PK")
            if not column.nullable:
                flags.append("required")
            if column.unique:
                flags.append("unique")
            columns.append(f"{column.name}:{column.type}" + (f" ({', '.join(flags)})" if flags else ""))
            for fk in column.foreign_keys:
                foreign_keys.append(f"{column.name} → {fk.target_fullname}")
        for constraint in table.constraints:
            if constraint.__class__.__name__ == "UniqueConstraint":
                cols = ",".join(c.name for c in constraint.columns)
                if cols:
                    unique.append(cols)
        if "tenant_id" in table.columns:
            tenant_scope = "Direct tenant_id"
        elif any(fk.endswith("tenants.id") for fk in foreign_keys):
            tenant_scope = "Direct tenant foreign key"
        elif foreign_keys:
            tenant_scope = "Indirect through parent — verify every query"
        else:
            tenant_scope = "No tenant key — global or security gap"
        resources.append(
            {
                "table": name,
                "tenant": tenant_scope,
                "columns": "; ".join(columns),
                "fks": "; ".join(foreign_keys) or "—",
                "unique": "; ".join(unique) or "—",
                "evidence": f"app/models + SQLAlchemy metadata ({name})",
            }
        )
    return resources


def table(headers: list[str], rows: list[list[Any]]) -> str:
    result = ["| " + " | ".join(md(h) for h in headers) + " |"]
    result.append("| " + " | ".join("---" for _ in headers) + " |")
    result.extend("| " + " | ".join(md(cell) for cell in row) + " |" for row in rows)
    return "\n".join(result)


def section(title: str, body: str) -> str:
    return f"## {title}\n\n{body.strip()}\n"


def build_report(spec: dict[str, Any], operations: list[dict[str, Any]], resources: list[dict[str, str]]) -> str:
    class_counts = Counter(op["classification"] for op in operations)
    unguarded_admin = [
        op for op in operations
        if op["auth"].startswith("UNGUARDED") and op["path"] != "/api/admin/auth"
    ]
    deprecated = [op for op in operations if op["deprecated"]]
    schema_names = sorted(spec.get("components", {}).get("schemas", {}))
    test_files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").glob("test_*.py"))

    route_table = table(
        ["Surface", "Frontend route", "Screen", "Guard", "Backend module"],
        [list(row) for row in FRONTEND_ROUTES],
    )
    auth_gap_table = table(
        ["Method", "Backend path", "Operation ID", "Source", "Required disposition"],
        [[op["method"], op["path"], op["operation_id"], op["source"], "Add backend X-Token/owner-admin guard or explicitly reclassify"] for op in unguarded_admin],
    )
    state_table = table(
        ["Current", "Allowed next states", "Frontend rule"],
        [
            ["pending", "confirmed, cancelled, rescheduled", "Show only valid actions"],
            ["confirmed", "cancelled, completed, no_show, rescheduled", "Show only valid actions"],
            ["rescheduled", "confirmed, cancelled", "Require renewed confirmation/cancellation"],
            ["cancelled", "none", "Terminal/read-only"],
            ["completed", "none", "Terminal/read-only"],
            ["no_show", "none", "Terminal/read-only"],
        ],
    )
    schema_table = table(
        ["Schema", "Canonical reference"],
        [[name, f"openapi.json#/components/schemas/{name}"] for name in schema_names],
    )
    resource_table = table(
        ["Table/resource", "Tenant scope", "Foreign keys", "Unique constraints", "Columns", "Evidence"],
        [[r["table"], r["tenant"], r["fks"], r["unique"], r["columns"], r["evidence"]] for r in resources],
    )
    operation_table = table(
        ["#", "Method", "Backend path", "Operation ID", "Class", "Frontend module", "Frontend route", "Auth", "Tenant", "Request schema", "Responses", "Source", "Related tests"],
        [
            [
                i,
                op["method"],
                op["path"],
                op["operation_id"],
                op["classification"],
                op["module"],
                op["frontend_route"],
                op["auth"],
                op["tenant"],
                op["request_schema"],
                ", ".join(op["responses"]),
                op["source"],
                ", ".join(op["tests"]) or "No direct mapping asserted",
            ]
            for i, op in enumerate(operations, 1)
        ],
    )

    header = f"""# FastAPI Bookings Frontend — Main Context Document v2

Status: **Corrected implementation brief — backend-derived**  
Generated from the current working tree.  
OpenAPI SHA-256: `{sha256(OPENAPI_PATH)}`  
Route manifest SHA-256: `{sha256(MANIFEST_PATH)}`  

## Release-readiness summary

- OpenAPI inventory: **{len(operations)} operations / {len(spec['paths'])} paths / {len(schema_names)} schemas**.
- SQLAlchemy inventory: **{len(resources)} tables/resources**.
- Operation ledger: **{len(operations)} unique method/path rows**, zero missing and zero duplicates after validation.
- Classifications: {', '.join(f'**{k}: {v}**' for k, v in sorted(class_counts.items()))}.
- Deprecated operations: **{len(deprecated)}**; none may be consumed by new UI code.
- Critical backend security gap: **{len(unguarded_admin)} non-login `/api/admin` operations do not declare `X-Token` in live OpenAPI**. Production release is blocked until each is guarded or explicitly reclassified by the backend owner.
- Public-token release gate: `PUBLIC_API_KEY` is treated as secret; production requires a same-origin BFF/server exchange or a backend replacement explicitly safe for unauthenticated browser bootstrap.
- This document contains no handwritten wire examples. Request and response contracts are referenced by canonical OpenAPI schema names.
"""

    sections = []
    sections.append(section("1. Product overview", """
FastAPI Bookings is a multi-tenant booking, scheduling, checkout, and operations platform. The frontend must provide a public booking surface, client self-service, and an owner/admin workspace while remaining contract-driven against the current FastAPI application.

The existing `mapbox/` application is migration evidence only. It uses deprecated endpoints, handwritten API types, unsupported `X-Client-Token`, and persistent bearer tokens. The v2 target is a new production architecture rather than a declaration that the prototype is complete.

**Primary outcome:** a frontend team can implement every approved screen without guessing endpoint shapes, tenant rules, authentication, state transitions, or evidence sources.
"""))
    sections.append(section("2. Problem statement", """
The backend exposes a broad and changing API, while the existing frontend covers only a subset and contains contract mismatches. Ad hoc implementation would create broken payloads, insecure tenant boundaries, false role assumptions, deprecated dependencies, and untestable coverage claims.

The solution is an OpenAPI-generated integration layer plus an exact screen/operation/resource register. Backend contradictions remain visible as release gates rather than being converted into frontend assumptions.
"""))
    sections.append(section("3. Goals and success metrics", """
### Goals

- Deliver public booking, client, and owner/admin workflows represented by non-deprecated backend capabilities.
- Generate API types and client functions from the hashed OpenAPI document.
- Prevent cross-tenant cache, token, URL, and state leakage.
- Make backend gaps visible before implementation or release.

### Initial measurable targets

| Area | Target | Window and measurement |
| --- | --- | --- |
| Tenant activation | ≥95% of valid tenant entries render a booking surface within 10 seconds | Rolling 7 days; tenant-resolution and surface-ready events |
| Booking conversion | ≥60% of sessions viewing a slot reach a recorded outcome within 15 minutes | First 30 production days; funnel events |
| Admin task success | ≥95% of supported mutations avoid unhandled frontend failure | Rolling 30 days; mutation telemetry |
| Performance | p75 mobile LCP ≤2.5s, INP ≤200ms, CLS ≤0.1 | Rolling 28-day field data |
| Reliability | Uncaught-error sessions <1%; non-user-caused request failures <2% | Rolling 7 days |
| Accessibility | Zero critical/serious automated violations and 100% keyboard completion of critical flows | Every release |
| Contract quality | 246/246 operations classified; 100% consumed operations generated and contract-tested | Every CI run |
| Retention | ≥50% of activated tenant admins complete an action in weeks 2, 3 and 4 | First 90 days |
"""))
    sections.append(section("4. Target users and roles", """
| User | V2 treatment | Proven authority |
| --- | --- | --- |
| Public visitor | Discovery and published booking flows | Public endpoints after tenant/public-token bootstrap |
| Client | Own login, registration, profile, terms, consent and booking flows | Client subject supplied through `X-Token` |
| Owner | Full supported admin workspace | Backend `get_current_admin` accepts owner |
| Admin | Same V1 authority as owner | Backend `get_current_admin` accepts admin |
| Staff | Route to role-not-enabled screen | Backend admin guard rejects staff |
| Viewer | Route to role-not-enabled screen | Backend admin guard rejects viewer |
| Operator/developer | Health, diagnostics and contract governance | System and CI surfaces |

No UI-only owner/admin distinctions are allowed until the backend enforces them. Staff/viewer remain typed future roles but receive no speculative permissions.
"""))
    sections.append(section("5. Confirmed decisions, assumptions, and open gates", f"""
### Confirmed decisions

1. `openapi.json` is canonical for wire shapes; generated clients replace handwritten API types.
2. `X-Token` is the only current bearer-token header. `X-Client-Token` is reserved and must not be sent.
3. Bearer tokens are memory-only. Tenant/account/auth changes clear tokens and tenant-scoped query caches.
4. Persistent login is deferred until a BFF/backend supplies Secure HttpOnly SameSite cookies, refresh/revocation semantics and CSRF protection.
5. `PUBLIC_API_KEY` is treated as secret unless the backend/security owner documents otherwise.
6. Deprecated operations are compatibility-only and prohibited in new frontend code.

### Open release gates

- Resolve all {len(unguarded_admin)} unexpectedly unguarded non-login admin operations listed in Section 13.
- Implement server-side public-token exchange or an approved safe backend bootstrap.
- Define legal retention periods; the frontend must not invent them.
- Select an analytics provider and privacy policy before enabling production event collection.
- Add direct contract/integration tests for every operation the frontend consumes.
"""))
    sections.append(section("6. Scope and exclusions", """
### In scope

Public configurable booking forms, availability, holds, waitlist, checkout, client identity and consent; discovery; owner/admin booking operations; catalog, relationships, schedules, resources, finance, notifications, reviews, audit, compliance, integrations and diagnostics represented by approved operations.

### Excluded or deferred

- Six deprecated public list/UI-config operations.
- Unprefixed duplicate notification/template/reminder operations.
- Inbound Stripe webhook and health endpoints as browser screens; they remain system/monitoring capabilities.
- Staff/viewer RBAC activation, persistent login, speculative file imports and any unsupported recurrence UX.
- Any operation that remains unguarded after the backend security audit may not ship merely because the frontend hides it.
"""))
    sections.append(section("7. Complete user journeys", """
### Public booking

1. Resolve tenant from production hostname; development may use the explicit dev route.
2. Obtain a public token through the same-origin BFF.
3. Load the configured booking form/runtime manifest.
4. Resolve service/provider/location relationships and fetch availability.
5. Create a hold when the selected slot needs protection during details/checkout.
6. Identify/create the client, collect additional fields and consent, create quote/invoice/checkout as configured.
7. Submit the booking once with idempotency protection where the backend supports it.
8. Present the actual backend outcome; ordinary public bookings are pending and copy must say “awaiting confirmation.”

### Client self-service

Register or log in, retain the client token in memory, view/update only the current profile, review terms and record consent. Reload ends the session. Password reset is request-only because no completion endpoint exists in the current inventory.

### Owner/admin operations

Authenticate, verify role, enter the tenant-scoped shell, load the dashboard, and navigate to concrete routes in Section 9. Mutations use generated types, disable duplicate submissions, normalize error envelopes and invalidate only tenant-scoped query keys.

### Booking lifecycle

{state_table}
"""))
    feature_rows = []
    for tag, count in sorted(Counter(tag for op in operations for tag in op["tags"]).items()):
        module, frontend_route = TAG_ROUTE.get(tag, (tag, "N/A"))
        feature_rows.append([tag, count, module, frontend_route, ", ".join(RELATED_TESTS.get(tag, [])) or "No direct mapping asserted"])
    sections.append(section("8. Core feature specifications", f"""
Features are enumerated from OpenAPI tags before UI specification. Operation-level ownership is authoritative in Appendix D.

{table(["Backend tag", "Operations", "Frontend module", "Primary route", "Related backend tests"], feature_rows)}

### Common feature contract

Every directly represented feature must provide initial/background loading, empty, offline/network, normalized 400/401/403/404/409/422/429/500 states, destructive confirmation, duplicate-submit protection, success feedback and targeted TanStack Query invalidation. Exact payloads come from the schema references in Appendix D; teams must not copy illustrative payloads from prose.
"""))
    sections.append(section("9. Screen and frontend route inventory", f"""
The following is the canonical target route inventory. Production tenant identity comes from hostname/configuration; `/dev/:tenantSlug/...` is development-only. Protected admin routes share an owner/admin layout guard. Client routes use an in-memory client session.

{route_table}

### Navigation rules

- Unknown routes go to `/404`; permission failures go to `/403` or `/admin/role-not-enabled`.
- Tenant change clears auth state, booking state and all tenant-prefixed query caches before navigation.
- Deep links must reload their own required server state; outcome routes without a public retrieval endpoint must show a safe “outcome unavailable after reload” fallback rather than inventing a fetch.
- Admin list/detail/edit routes preserve filters in query parameters but never tokens or sensitive data.
"""))
    sections.append(section("10. Interaction and request-lifecycle rules", """
1. Use a centralized generated client middleware to attach tenant context and the current in-memory `X-Token`.
2. Normalize the standard `{ok,error}` envelope and legacy FastAPI `detail`/validation envelopes into one typed UI error.
3. Map 422 locations to React Hook Form fields; retain an accessible summary for unmapped errors.
4. A 401 clears the relevant in-memory session and redirects to the appropriate login/bootstrap flow.
5. A 403 preserves safe context and shows permission/role-not-enabled guidance.
6. A 409 retains user input, refetches the conflicted resource/availability and requires explicit retry.
7. A 429 honors `Retry-After` when present; otherwise use bounded backoff and never loop automatically on mutations.
8. Destructive and booking-state mutations are pessimistic by default. Optimistic updates are allowed only for reversible low-risk preferences.
9. Query keys always begin with tenant identity and auth subject class.
10. Public routes are rate-limited; availability requests must debounce/cancel stale requests.
"""))
    sections.append(section("11. Content and messaging", """
- Ordinary public booking: **“Your booking request has been received and is awaiting confirmation.”**
- Conflict: **“That time is no longer available. Choose another time.”**
- Role disabled: **“This account role is not enabled for the administration workspace.”**
- Tenant failure distinguishes missing tenant (400) from unknown tenant (404).
- Never expose stack traces, secrets, raw gateway responses or cross-tenant identifiers.
- Copy is centralized and localization-ready. Date, time, currency and timezone formatting uses tenant configuration and accessible explicit labels.
"""))
    sections.append(section("12. Data, resource, relationship, and state model", f"""
This register is generated from current SQLAlchemy metadata. “Indirect through parent” requires a query-by-query tenant audit; it is not proof of unsafe behavior or proof of isolation.

{resource_table}

### Canonical API schema register

The 188 schema names below are references, not handwritten examples. Implementations consume their generated TypeScript equivalents.

{schema_table}
"""))
    sections.append(section("13. Authentication, tenancy, and permissions", f"""
### Tenant resolution

Backend order is `X-Tenant`, then `tenant` query parameter, then hostname subdomain with Cloud Run/common-host exclusions. Production uses hostname/configuration; query/header overrides are restricted to controlled development and BFF contexts.

### Token and role rules

- Admin credentials and public API-key exchange both require tenant context.
- Owner/admin are the only V1 admin roles.
- Staff/viewer receive a dedicated denial route.
- Public/client/admin JWT subjects are transmitted through `X-Token` only.
- Tokens are memory-only and cleared with tenant/auth cache boundaries.

### Critical backend authorization audit

Live OpenAPI exposes the following non-login `/api/admin` operations without an `X-Token` header. The frontend cannot repair backend authorization by hiding controls. Each operation blocks production until the backend adds an owner/admin dependency or explicitly documents a safe alternative.

{auth_gap_table}
"""))
    sections.append(section("14. Non-functional, responsive, accessibility, and security requirements", """
### Responsive design

Public booking is mobile-first with single-column progression and a collapsible summary. At 320 CSS px, content reflows without two-dimensional page scrolling; only intrinsically wide data regions may scroll inside a labelled container. At 200% zoom, primary actions, validation messages and navigation remain visible and operable. Admin lists become cards or horizontally scrollable labelled regions below tablet widths; destructive actions remain reachable without hover. Calendars provide agenda/list alternatives, and maps provide a synchronised result list. Breakpoints are content-driven and tested in portrait and landscape with touch, keyboard and pointer input.

### Accessibility

Target WCAG 2.2 AA with the following release criteria:

- **Structure and navigation:** one descriptive `h1`, ordered headings, semantic landmarks, skip link, descriptive page titles and current-route indication. Repeated controls have accessible names that include their row/card context.
- **Keyboard and focus:** all actions work without a pointer; focus order follows the visual/task order; focus is never trapped except inside an active modal; dialogs restore focus to their trigger; route changes and validation failures move focus deliberately and visibly.
- **Forms:** persistent programmatic labels, instructions before input, required state conveyed in text, `aria-describedby` links to help/errors, an error summary linked to invalid fields, and no loss of valid input after server errors. Date, time, combobox and file controls retain native semantics or follow established ARIA patterns.
- **Dynamic states:** loading, mutation outcomes, slot expiry and background errors use appropriately scoped live regions without repeated announcements. Skeletons are hidden from assistive technology and never replace an announced accessible status.
- **Visual access:** text and meaningful UI meet AA contrast, status never depends on color alone, focus indicators remain visible, targets meet WCAG 2.2 minimum sizing, text-spacing overrides do not clip content, and animations respect `prefers-reduced-motion`.
- **Complex views:** map results have a synchronised list; calendars have agenda/table alternatives; charts expose a text summary and data table; drag-and-drop actions have keyboard controls; virtualised lists preserve names, positions and focus.
- **Timing and recovery:** warn before session, hold or slot expiry; allow extension where backend rules permit; preserve non-sensitive form input; confirmations identify the affected record; destructive and financial operations require review or an undo path where feasible.
- **Verification:** automated axe checks run in component and Playwright suites. Manual keyboard and screen-reader checks cover tenant entry, public booking, checkout, client authentication, admin login, booking approval/rejection and rescheduling at every release.

### Security

No bearer tokens or API secrets in persistent browser storage, URLs, analytics or logs. Encode untrusted output, validate external URLs, disallow arbitrary HTML, enforce CSP at deployment, scan built assets for secrets, and clear tenant-scoped state atomically. CORS is an allowlist, not an authorization control. Same-origin BFF cookies, if introduced, require CSRF protection.

### Performance and reliability

Meet Section 3 field targets. Code-split admin modules, prefetch only safe tenant-scoped data, cancel stale requests, and keep booking selections resilient to recoverable network errors without persisting sensitive values.
"""))
    failure_rows = [
        ["Initial loading", "Skeleton/progress; controls disabled", "All"],
        ["Empty", "Explain absence and offer permitted creation/change action", "Lists/forms"],
        ["Network/offline", "Retain safe input; retry manually; never duplicate mutation", "All"],
        ["400", "Tenant/request-level explanation", "Global/form"],
        ["401", "Clear session and reauthenticate/bootstrap", "Authenticated"],
        ["403", "Permission or role-not-enabled screen", "Protected"],
        ["404", "Not-found state with safe parent navigation", "Detail/public surface"],
        ["409", "Refetch, retain input, require explicit retry", "Availability/state transitions"],
        ["422", "Field mapping plus accessible summary", "Forms"],
        ["429", "Retry guidance and bounded backoff", "Public/rate-limited"],
        ["500", "Generic message plus request ID; no internals", "All"],
        ["Tenant switch", "Clear tokens, stores, query cache and pending requests", "All"],
        ["Slot expires", "Return to refreshed availability", "Booking"],
        ["Reload after outcome", "Safe fallback if no retrieval endpoint", "Public outcome"],
    ]
    sections.append(section("15. Validation, errors, conflicts, and edge cases", table(
        ["State", "Required UI behavior", "Applies to"], failure_rows
    )))
    sections.append(section("16. Technical frontend architecture and API integration", """
### Stack

React 19, TypeScript, Vite, React Router, TanStack Query, React Hook Form, Zod refinements, OpenAPI-generated types/client, Tailwind CSS with a controlled shadcn/ui layer, limited Zustand/Context for ephemeral session/UI state, Vitest/React Testing Library, Playwright and Storybook.

### Layering

```text
routes/layouts
  → feature screens
    → query/mutation hooks
      → generated OpenAPI client
        → tenant/auth/error middleware
          → FastAPI or same-origin BFF
```

Generated API types are never re-declared manually. Zod may refine UI-only cross-field rules but must not contradict OpenAPI. The BFF owns the secret public-token exchange. Environment configuration contains only publishable values such as API base URL and controlled development tenant override.

### Contract workflow

1. Export fresh OpenAPI from the importable app.
2. Fail CI when its hash differs from committed `openapi.json`.
3. Regenerate `contracts/types.ts` and the typed client.
4. Typecheck feature hooks and validate the operation ledger.
5. Run contract/integration and Playwright tests before build promotion.
"""))
    sections.append(section("17. Analytics, audit, and observability", """
Instrument tenant resolution, booking-surface readiness, availability viewed, hold created/expired, booking outcome, client auth outcome, admin mutation outcome, role denial, deprecated-operation detection and frontend errors. Capture duration, outcome category and non-sensitive tenant pseudonym; never capture tokens, passwords, free-text notes, payment credentials or sensitive client fields.

Preserve backend `request_id` in support-visible error details and telemetry correlation. Analytics remains disabled until provider selection, consent basis, retention and data residency are approved.
"""))
    sections.append(section("18. Testing and QA acceptance criteria", f"""
### Required layers

- Generator/contract tests: OpenAPI hash, 246 exact operations, zero duplicate ledger keys, generated type freshness and zero deprecated imports.
- Unit tests: error normalization, tenant resolution, auth middleware, query-key isolation, state-machine action visibility and Zod refinements.
- Component tests: every loading/empty/error/permission/conflict state and accessible keyboard behavior.
- Integration tests: every consumed operation has at least one generated-client contract test; related backend tests are evidence but not a substitute.
- Playwright: public booking, hold conflict, client auth/profile, owner/admin login, staff/viewer denial, booking lifecycle, tenant switch isolation and critical CRUD.
- Accessibility: automated axe plus manual keyboard/screen-reader testing for login, booking, approval and rescheduling.
- Security: built-asset secret scan, token persistence scan, external URL tests and cross-tenant cache tests.

### Current backend verification evidence

Focused suite: 18 passed with six deprecation warnings across tenancy, booking-form contracts, configurable forms and booking policies. Full test inventory:

{table(["Test file", "Status in this report"], [[path, "Available; direct per-operation linkage only where Appendix D says related"] for path in test_files])}
"""))
    sections.append(section("19. Implementation sequence, MVP, and release gates", """
1. **Backend security gate:** resolve unexpectedly unguarded admin operations and public-token exchange.
2. **Contract foundation:** regenerate OpenAPI types/client, tenant/auth middleware, errors and query-key factory.
3. **Design foundation:** accessible primitives, layout, forms, tables/cards, dialogs, calendars and state components.
4. **Public core:** tenant entry, booking-form runtime, availability, details, hold and pending outcome.
5. **Client core:** registration/login/profile/terms/consent.
6. **Admin core:** login/role guard, dashboard, bookings/calendar and booking transitions.
7. **Catalog and scheduling:** services/providers/locations/categories, relationships, workdays/exceptions and resources.
8. **Commerce and communications:** add-ons/products/packages, invoices/payments/tax/promotions, notifications/templates/reminders.
9. **Operations:** reviews, audit, GDPR, webhooks, plugins, diagnostics and maintenance.
10. **Release hardening:** operation-to-test coverage, Playwright, accessibility, performance, security and observability gates.

MVP release requires zero unresolved critical/high findings, zero deprecated calls, all consumed operations generated and tested, the authorization audit closed, BFF token exchange operational, accessibility critical flows passing, and production telemetry/privacy approval.
"""))

    appendices = f"""
## Appendix A. Screen-to-API ownership

{table(["Operation", "Frontend module", "Frontend route", "Classification"], [[f"{op['method']} {op['path']}", op['module'], op['frontend_route'], op['classification']] for op in operations])}

## Appendix B. Evidence register

| Requirement area | Exact evidence | Confidence/limitation |
| --- | --- | --- |
| Operation shapes | `openapi.json` SHA `{sha256(OPENAPI_PATH)}` and schema refs in Appendix D | Canonical wire source; inline `{{}}` responses require route/schema implementation review |
| Method/path reconciliation | `contracts/route-manifest.json` SHA `{sha256(MANIFEST_PATH)}` | Does not prove UI use or authentication |
| Tenant/auth implementation | `app/api/deps.py`, `app/api/routers/auth.py`, OpenAPI header parameters | OpenAPI lacks security schemes; Section 13 lists unguarded admin operations |
| Booking states | `app/core/state_machine.py` | Frontend must still handle concurrent 409 responses |
| Resources/relationships | SQLAlchemy `Base.metadata`, model files, Alembic migrations | Indirect tenant scope requires query audit |
| Public booking forms | `app/api/routers/booking_forms.py`, `app/schemas/booking_form.py`, configurable-form tests | Some success responses are inline `{{}}` in OpenAPI |
| Errors | `app/main.py`, `contracts/errors.contract.json`, `HTTPValidationError` | Legacy FastAPI detail envelopes coexist |
| Existing frontend defects | `mapbox/App.tsx`, `mapbox/services/apiClient.ts`, `mapbox/store/*.tsx` | Evidence only; not target architecture |
| Focused verification | tenancy, booking-form contract, configurable-form and booking-policy test files | 18-test run is not full-suite proof |

## Appendix C. Canonical schema contract rule

Do not copy JSON examples from this document. For every operation, generate the request and response TypeScript types named in Appendix D from `openapi.json`. When OpenAPI exposes an inline or empty schema, inspect the cited route implementation, add an explicit response model to the backend, regenerate OpenAPI, and only then bind production UI to the shape.

## Appendix D. Complete 246-operation ledger

{operation_table}
"""
    return "\n\n".join([header.strip(), *[s.strip() for s in sections], appendices.strip()]) + "\n"


def validate(report: str, spec: dict[str, Any], operations: list[dict[str, Any]], resources: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    expected = {
        (method.upper(), path)
        for path, item in spec["paths"].items()
        for method in item
        if method in HTTP_METHODS
    }
    actual = {(op["method"], op["path"]) for op in operations}
    if len(operations) != 246:
        errors.append(f"Expected 246 operations, got {len(operations)}")
    if expected != actual:
        errors.append(f"Ledger mismatch: missing={len(expected-actual)} extra={len(actual-expected)}")
    if len(actual) != len(operations):
        errors.append("Duplicate method/path keys")
    if len(resources) != 55:
        errors.append(f"Expected 55 resources, got {len(resources)}")
    for number in range(1, 20):
        if f"## {number}." not in report:
            errors.append(f"Missing section {number}")
    if re.search(r"(?m)^Mermaid$|\[ASSUMPTION:|\[TODO|\bTBD\b", report):
        errors.append("Placeholder text remains")
    if any(op["classification"] not in ALLOWED_CLASSES for op in operations):
        errors.append("Invalid operation classification")
    for op in operations:
        if op["classification"] == "directly represented" and op["frontend_route"] in {"", "N/A"}:
            errors.append(f"Direct operation lacks route: {op['method']} {op['path']}")
    if "\"token\": \"jwt string\"" in report or '"id": "uuid"' in report:
        errors.append("Invented JSON contract example remains")
    if report.count("| # | Method | Backend path | Operation ID |") != 1:
        errors.append("Operation ledger table missing")
    appendix_d = report.split("## Appendix D. Complete 246-operation ledger", 1)[-1]
    if re.search(r"<[^>\n]+>", appendix_d):
        errors.append("Appendix D contains raw HTML-like angle-bracket content")
    return errors


def main() -> int:
    spec = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    operations = load_operations(spec)
    resources = load_resources()
    report = build_report(spec, operations, resources)
    errors = validate(report, spec, operations, resources)
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    OUTPUT_PATH.write_text(report, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Bytes: {OUTPUT_PATH.stat().st_size}")
    print(f"SHA-256: {sha256(OUTPUT_PATH)}")
    print(f"Operations: {len(operations)} unique={len({(o['method'], o['path']) for o in operations})}")
    print(f"Resources: {len(resources)}")
    print(f"Sections: {sum(f'## {n}.' in report for n in range(1, 20))}/19")
    print(f"Classifications: {dict(Counter(o['classification'] for o in operations))}")
    print(f"Unguarded non-login admin operations: {sum(o['auth'].startswith('UNGUARDED') and o['path'] != '/api/admin/auth' for o in operations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
