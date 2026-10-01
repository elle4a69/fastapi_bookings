# HTTP REST API Layer (`app/api/routers`)

This module provides the HTTP REST API router registry, endpoint handlers, request/response serialization, rate-limiting, and error transformation for **FastAPI Bookings**.

---

## 1. Purpose & Scope

The API router module owns:
- HTTP ingress, routing, path parameter validation, and JSON serialization.
- Public intake endpoints for the frontend booking widget and client portal.
- Authenticated administration endpoints for owners, managers, and service providers.
- Webhook ingress handlers for SMS gateways, Stripe payment events, and Chatwoot agent events.
- Centralized error formatting into standardized envelope responses (`ok: false`, `error: {...}`).

This module deliberately avoids direct SQL query generation where service facades exist, long-running blocking operations (which are delegated to outbox workers or background tasks), and business logic bypassing tenant scoping.

---

## 2. Architecture & Key Files

The router registry is mounted in [app/main.py](file:///F:/Projects/fastapi_bookings/app/main.py) and authenticated via [app/api/deps.py](file:///F:/Projects/fastapi_bookings/app/api/deps.py).

```mermaid
graph TD
    ClientReq["Inbound HTTP Request"] --> MainApp["app/main.py (FastAPI App)"]
    MainApp --> RateLimit["SlowAPI Rate Limiter"]
    MainApp --> CorrID["X-Request-ID Header Middleware"]
    CorrID --> RouterGroup{"Route Path Matching"}

    RouterGroup -->|"/api/auth/*"| AuthRouter["auth.py"]
    RouterGroup -->|"/api/public/*"| PublicRouters["availability.py, public_bookings.py, public_clients.py"]
    RouterGroup -->|"/api/admin/*"| AdminRouters["bookings.py, providers.py, services.py, clients.py, admin_schedule.py"]
    RouterGroup -->|"/api/client-portal/*"| PortalRouter["client_portal.py"]
    RouterGroup -->|"/api/sms/*"| SMSRouters["sms_accounts.py, sms_conversations.py, sms_webhooks.py"]
    RouterGroup -->|"/api/resident-agent/*"| AgentRouter["resident_agent.py"]
    RouterGroup -->|"/api/webhooks/*"| WebhookRouters["stripe_webhooks.py, chatwoot_agentbot.py"]

    AuthRouter & PublicRouters & AdminRouters & PortalRouter & SMSRouters & AgentRouter --> Deps["app/api/deps.py (Auth, Tenant, RBAC, DB)"]
    Deps --> DB[(Database Session)]
```

### Key Router Files
- [auth.py](file:///F:/Projects/fastapi_bookings/app/api/routers/auth.py): User login, credential verification, JWT token issuance.
- [bookings.py](file:///F:/Projects/fastapi_bookings/app/api/routers/bookings.py): Primary booking management, admin scheduling, status updates (`CONFIRMED`, `CANCELLED`, `COMPLETED`).
- [availability.py](file:///F:/Projects/fastapi_bookings/app/api/routers/availability.py): Real-time availability calculation across provider schedules and buffer rules.
- [public_bookings.py](file:///F:/Projects/fastapi_bookings/app/api/routers/public_bookings.py): Intake endpoints consumed by the public booking widget.
- [client_portal.py](file:///F:/Projects/fastapi_bookings/app/api/routers/client_portal.py): Self-service client appointment views, reschedules, and cancellations.
- [sms_conversations.py](file:///F:/Projects/fastapi_bookings/app/api/routers/sms_conversations.py): SMS conversation thread view, message history, human takeover toggle.
- [sms_webhooks.py](file:///F:/Projects/fastapi_bookings/app/api/routers/sms_webhooks.py): Inbound webhook receiver for ClickSend and external SMS carriers.
- [sms_chatwoot.py](file:///F:/Projects/fastapi_bookings/app/api/routers/sms_chatwoot.py): Canonical Chatwoot mirror webhook intake, provider-scoped `SmsChatwootBinding` CRUD, token/secret masking, 1-to-1 Tenant mapping enforcement, and admin automated provisioning trigger (`POST /provision`).
- [tenants.py](file:///F:/Projects/fastapi_bookings/app/api/routers/tenants.py): Tenant creation and retrieval router with automated Chatwoot multi-tenant provisioning lifecycle hook (`CHATWOOT_AUTO_PROVISION`).
- [chatwoot_agentbot.py](file:///F:/Projects/fastapi_bookings/app/api/routers/chatwoot_agentbot.py): Chatwoot AgentBot webhook integration with automated de-confliction ignoring mirror-bound inboxes to prevent duplicate replies.
- [resident_agent.py](file:///F:/Projects/fastapi_bookings/app/api/routers/resident_agent.py): Operational health checks, deep audit trigger, and fuzzer controls.
- [assistant_studio.py](file:///F:/Projects/fastapi_bookings/app/api/routers/assistant_studio.py): Assistant Studio administration endpoints: 10-tier policy management (`Tenant.assistant_policy`), procedural style example CRUD, curator proposal management, simulation sandbox, cryptographic dataset importer, and evaluation suite with uniform `validate_tenant_provider` cross-tenant scoping and platform seed read-only lockdown.
- [deps.py](file:///F:/Projects/fastapi_bookings/app/api/deps.py): Core dependency injection functions: `get_current_tenant`, `get_current_user`, `require_role`, `get_current_client`.

---

## 3. Setup, Configuration & Dependencies

### Dependencies
- **FastAPI** & **Starlette**: HTTP routing, request parsing, and exception handling.
- **SlowAPI**: Rate limiting middleware for public routes (`default_limits=["10/minute"]`).
- **SQLAlchemy Session**: Injected into every route handler via `Depends(get_db)`.
- **Pydantic Schemas**: Request validation and response serialization models ([app/schemas/](file:///F:/Projects/fastapi_bookings/app/schemas/)).

### Environment Variables
Configured in [app/core/config.py](file:///F:/Projects/fastapi_bookings/app/core/config.py):
- `FRONTEND_ORIGINS`: Allowed CORS origins for widget and admin dashboards.
- `SECRET_KEY`: Used to sign and verify HMAC-SHA256 JWT tokens.
- `PUBLIC_API_KEY`: API key for public booking widget authentication.

---

## 4. Core Workflows & Contracts

### 4.1 Standardized Error Schema
All uncaught exceptions, Starlette HTTP exceptions, and validation errors are intercepted by global handlers in [app/main.py](file:///F:/Projects/fastapi_bookings/app/main.py) to guarantee a consistent JSON response:

```json
{
  "ok": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Booking not found",
    "details": {},
    "request_id": "9b1deb4d3b7d4bad9bdd2b0d7b3dcb6d"
  }
}
```

Standard error codes:
- `400`: `BAD_REQUEST`
- `401`: `UNAUTHORIZED`
- `403`: `FORBIDDEN`
- `404`: `NOT_FOUND`
- `409`: `CONFLICT` (e.g. double booking collision)
- `422`: `VALIDATION_ERROR` (Pydantic schema validation failure)
- `429`: `TOO_MANY_REQUESTS` (SlowAPI rate limit hit)
- `500`: `INTERNAL_SERVER_ERROR`

### 4.2 Authentication & Role Contracts
Clients pass their JWT access token via the `X-Token` header:
- **Public Widget**: Calls `/api/public/bootstrap` using `PUBLIC_API_KEY` to obtain a public tenant-scoped token.
- **Client Portal**: Clients log in via phone/email OTP and receive a client token containing `tenant_id` and client `sub`.
- **Staff / Admin**: Staff log in at `/api/auth/token` with username/password, receiving a user token containing their user `id` and `role`.

---

## 5. Data Safety, Multi-Tenancy & PII Isolation

1. **Strict Tenant Partitioning**:
   - `get_current_tenant` guarantees that every request is bound to a single verified `Tenant`.
   - Routes filter every read and write with `tenant_id == tenant.id`.
2. **Numeric ID Bounds Checking**:
   - Every integer path parameter is annotated with `DatabaseId` (`ge=1, le=9_223_372_036_854_775_807`), preventing integer truncation and SQL injection bugs.
3. **Correlation Tracking Without PII**:
   - `add_correlation_id_header` injects `X-Request-ID` and `X-Trace-ID` matching the active OpenTelemetry span context.
   - PII (passwords, payment details, phone numbers) is never echoed in correlation headers or error responses.
4. **Chatwoot AgentBot Tenant Resolution**:
   - AgentBot webhook inbound routing resolves the authentic internal `tenant.id` via `SmsChatwootBinding` or `Tenant.chatwoot_account_id == payload.account.id`, protecting memory curation and AI execution from cross-tenant contamination.
   - In production environments, unmapped accounts are rejected with `unmapped_chatwoot_account`.
5. **Website Chat Transcript HMAC Token Protection**:
   - Web chat history endpoints (`GET /api/public/website/chat/{conversation_id}`) enforce tenant-scoped HMAC-SHA256 session token verification (`X-Chat-Session-Token` or `token`) or authorized tenant staff authentication (`X-Token`).
   - Prevents unauthenticated conversation ID enumeration and transcript data leakage.
6. **Public Timeline Workday Scoping**:
   - Provider timeline endpoints (`GET /api/public/timeline/schedule/{provider_id}`) strictly bind company-wide workdays (`provider_id IS NULL`) and special-day overrides to `current_tenant.id`.
7. **Admin GDPR Consent Isolation**:
   - GDPR consent queries (`GET /api/admin/gdpr-consents` and `GET /api/admin/gdpr-consents/{client_id}`) strictly enforce `GdprConsent.tenant_id == current_tenant.id`.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Rate Limiting on Reverse Proxies**: SlowAPI uses `get_remote_address`, which resolves proxy IPs if `Forwarded` / `X-Forwarded-For` is not configured in upstream load balancers.
- **Public Bootstrap Deprecation**: Legacy endpoints allowing token-less public queries are being migrated to strictly enforce tenant subdomains.

---

## 7. Verification & Testing Commands

Execute targeted router tests:
```powershell
# 0. Test Phase 1 security hardening & tenant isolation remediations
pytest tests/test_security_isolation_remediation.py -v

# 1. Test authentication contracts and token verification
pytest tests/test_auth_contract.py -v

# 2. Test public intake and booking form contracts
pytest tests/test_booking_form_contracts.py tests/test_configurable_booking_forms.py -v

# 3. Test client portal routes
pytest tests/test_client_portal.py -v

# 4. Test role hierarchy enforcement
pytest tests/test_role_hierarchy.py -v

# 5. Test numeric bounds on path parameters
pytest tests/test_numeric_id_bounds.py -v

# 6. Test granular readiness & diagnostics
pytest tests/test_production_readiness_drills.py -k test_drill_11 -v

# 7. Test Assistant Studio policy persistence, scoping lockdown & importer dry-run safety
pytest tests/test_assistant_studio_policy_and_scoping.py tests/test_assistant_studio_api.py tests/test_curator_import_safety.py -v

# 8. Test Chatwoot Tenant Binding, Webhook Scoping, AgentBot De-confliction, Automated Provisioning, and Docker E2E
pytest tests/test_chatwoot_provisioning.py tests/test_sms_chatwoot.py tests/test_chatwoot_agentbot.py tests/test_chatwoot_docker_e2e.py -v
```

---

## 8. Granular System Health & Readiness Verification (Section 24)

The router layer provides unauthenticated public readiness checks (`/health/granular`, `/readiness`) and admin-scoped diagnostics (`/diagnostics/readiness`, `/api/admin/diagnostics/readiness`):
- **PostgreSQL Database Connectivity**: Verified via lightweight `SELECT 1` ping.
- **Redis Cache Subsystem**: Checked via real sync ping against connection pool.
- **Neo4j / Graphiti Engine**: Validated through driver connectivity and `ping_neo4j()` session execution.
- **Background Outbox Lag**: Quantifies pending and dead-letter projection queues (`knowledge_graph_projections`) and learning events (`learning_events`).
- **Telemetry & Celery Worker Status**: Evaluates tracing initialization and worker queue responsiveness.
- **Response Format**: Status 200 with `status: "ready"` if all critical subsystems are online; Status 503 with degraded component details if any core dependency fails.

---

## 9. Chatwoot Tenant Binding, Provisioning & AgentBot De-confliction (`sms_chatwoot.py`, `chatwoot_agentbot.py`, `tenants.py`)

### Purpose & Scope
This slice provides the HTTP REST API layer for bi-directional Chatwoot synchronization, authoritative tenant scoping, automated multi-tenant provisioning, and webhook de-confliction:
- **Automated Multi-Tenant Provisioning Trigger**:
  - Mounted at `POST /api/sms/chatwoot/provision` (accessible by authenticated tenant admin).
  - Automatically reconciles or provisions the Chatwoot account, API channel inboxes for active providers, `SmsChatwootBinding` entries, webhook subscriptions (`message_created`, `message_updated`), and staff agents.
  - Idempotent and safe for repeated calls.
- **Tenant Lifecycle Creation Hook**:
  - Mounted at `POST /api/tenants` (`tenants.py`).
  - When `CHATWOOT_AUTO_PROVISION=true`, triggers automated Chatwoot provisioning with graceful fail-safe handling if Chatwoot is offline.
- **FastAPI Tenant ↔ Chatwoot Account 1-to-1 Mapping**:
  - `Tenant.chatwoot_account_id` enforces unique 1-to-1 mapping between a FastAPI tenant and Chatwoot account.
  - Creating or updating an `SmsChatwootBinding` automatically links and validates that the Chatwoot account is not already claimed by a different tenant (`HTTP 400 Bad Request`).
  - Provider scoping requires that the provider belongs strictly to the authenticated tenant.
  - Secret tokens (`chatwoot_api_token` and `webhook_secret`) are masked with `********` on all response schemas.
- **Authoritative Canonical Inbound Webhook**:
  - Mounted at `POST /api/sms/chatwoot/webhook` (and `/api/admin/sms/chatwoot/webhook`).
  - Authenticated via query param `?token=` or `X-Chatwoot-Token` header matching the binding's `webhook_secret`.
  - Resolves bindings by exact `chatwoot_inbox_id` and `account.id`.
  - Rejects unknown inboxes, mismatched account IDs, or invalid secrets (`HTTP 401/404`).
- **AgentBot Inbound De-confliction**:
  - Mounted at `POST /api/v1/chatwoot/webhook` (`chatwoot_agentbot.py`).
  - Before handling an incoming message, checks whether `conversation.inbox_id` is registered with an active `SmsChatwootBinding`.
  - If bound to the canonical mirror path, AgentBot returns `{"status": "ignored", "reason": "inbox_managed_by_canonical_mirror_webhook"}` without executing duplicate AI turns or sending duplicate responses.
  - Verifies that the Chatwoot account belongs to the resolved tenant, rejecting tenant spoofing or hijacking attempts.


