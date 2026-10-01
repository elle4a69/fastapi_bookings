# Core Configuration, Security, Redis & Telemetry

## Purpose & Scope
The `app/core/` package encapsulates cross-cutting concerns for the application:
- Environment settings and secrets loading via Pydantic (`config.py`).
- Cryptographic password hashing, JWT access token generation, and role checks (`security.py`).
- Centralized, resilient Redis connection pooling, key namespacing, and health checks (`redis.py`).
- Finite state machines for appointment lifecycle transitions (`state_machine.py`).
- OpenTelemetry instrumentation, OTLP exporters, and PII redaction filters (`telemetry.py`).

---

## Architecture & Key Files

```
app/core/
├── config.py                 # Global Settings (DATABASE_URL, REDIS_URL, SECRET_KEY, CHATWOOT_BASE_URL, MAPBOX_ACCESS_TOKEN, …)
├── capability_validator.py   # Tenant → Provider → Service hierarchy & booking service-mode validators
├── redis.py                  # Sync & Async Redis connection pools, 'fb:' key formatting, ping healthcheck & fallback
├── security.py               # Passlib Argon2/Bcrypt hashing, JWT encode/decode routines
├── state_machine.py          # BookingStatus state machine (pending → confirmed → completed / cancelled)
└── telemetry.py              # OpenTelemetry TracerProvider, MeterProvider, and privacy span processor
```

---

## Setup, Configuration & Dependencies
Key environment variables in `.env`:
- `DATABASE_URL`: PostgreSQL connection string (cut over to dedicated instance on port 5433).
- `REDIS_URL`: Redis connection URL (default: `redis://127.0.0.1:6380/0`).
- `SECRET_KEY`: High-entropy key for JWT signature validation.
- `OPENAI_API_KEY`: API key for GPT-4o autonomous dialogue agent.
- `CALCOM_API_KEY`: Optional Cal.com API key for headless scheduling federation.
- `CHATWOOT_BASE_URL`: Chatwoot server URL (default: `http://localhost:4000`).
- `CHATWOOT_API_ACCESS_TOKEN`: Tenant-level Chatwoot API token.
- `CHATWOOT_PLATFORM_API_TOKEN`: Superadmin Platform API token for automated account/inbox provisioning.
- `CHATWOOT_AUTO_PROVISION`: Boolean flag to trigger automatic Chatwoot provisioning during tenant onboarding.
- `LOCAL_AUTH_BYPASS`: Boolean flag strictly for local development on localhost/127.0.0.1 (forbidden in production).
- `OTEL_EXPORTER_OTLP_ENDPOINT`: SigNoz or OpenTelemetry collector endpoint (e.g. `http://localhost:4318`).
- `MAPBOX_ACCESS_TOKEN`: Mapbox geocoding token — used server-side ONLY, never exposed in API responses or frontend config.

---

## Phase 5: Platform Owner Governance Layer

### 5.1 Chatwoot SuperAdmin Deep-Link Endpoint

**Route:** `GET /api/admin/governance/chatwoot-links`  
**Auth:** Requires authenticated admin user (via `get_current_admin` + `get_current_tenant`)  
**Location:** [`app/api/routers/general_systems.py`](file:///f:/Projects/fastapi_bookings/app/api/routers/general_systems.py#L152-L175)

Returns deep links for the platform owner:
```json
{
  "ok": true,
  "super_admin_url": "http://localhost:4000/super_admin",
  "account_url": "http://localhost:4000/app/accounts/42",
  "chatwoot_account_id": 42,
  "base_url": "http://localhost:4000"
}
```

The `account_url` is `null` when the tenant has not been provisioned with a Chatwoot account yet. `CHATWOOT_BASE_URL` is resolved from settings — never hardcoded.

**Frontend:** [`frontend/src/pages/admin/system.tsx`](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/system.tsx) fetches this endpoint on mount and renders "Open SuperAdmin Console" and "Open Tenant Workspace" buttons using `window.open(..., '_blank')`. Both buttons link to the server-resolved URLs — no hardcoded frontend URLs.

---

### 5.2 RFC 6761 `*.localhost` Subdomain Gateway Routing

**Location:** [`app/api/deps.py`](file:///f:/Projects/fastapi_bookings/app/api/deps.py) — `_tenant_subdomain_from_host()` + `get_current_tenant()`

Subdomain resolution rules (in order of priority):

| Host Header | Extracted Subdomain |
|---|---|
| `simplydemo.localhost:8000` | `simplydemo` |
| `clinic.localhost:7070` | `clinic` |
| `clinic.localhost` | `clinic` |
| `simplydemo.bookopenapi.com` | `simplydemo` |
| `simplydemo.dev.localhost` | `simplydemo` |
| `localhost:8000` | *(none — falls back to X-Tenant)* |
| `www.example.com` | *(reserved — excluded)* |
| `myservice.run.app` | *(Cloud Run — excluded)* |

**RFC 6761 Compliance:** Port numbers are stripped before label parsing. Both `clinic.localhost` and `clinic.localhost:8000` are handled seamlessly without modifying `/etc/hosts`.

**Fallback chain:**
1. Host-header subdomain (from `Host` or `X-Forwarded-Host`).
2. `X-Tenant` request header (for API clients, curl, background workers, test fixtures).
3. `tenant` query parameter (legacy support).

**Error behaviour:**
- No tenant context → `HTTP 400 BAD_REQUEST`.
- Unknown subdomain → `HTTP 404 NOT_FOUND`.
- Host subdomain ≠ X-Tenant header → `HTTP 400 BAD_REQUEST` (prevents confusion).

---

### 5.3 SigNoz Telemetry PII Isolation

**Location:** [`app/core/telemetry.py`](file:///f:/Projects/fastapi_bookings/app/core/telemetry.py)

All OpenTelemetry spans are wrapped by `PrivacySafeSpanExporter` before being sent to SigNoz. The `SanitizedSpanProxy` enforces `SAFE_ATTRIBUTE_KEYS` — an immutable `frozenset` of permitted structural low-cardinality attribute names:

**Permitted attributes (structural only):**
`tenant_id`, `route`, `http.method`, `http.route`, `http.status_code`, `http.scheme`, `http.target`, `db.system`, `db.operation`, `error.type`, `exception.type`, `service.name`, `service.namespace`, `deployment.environment`, `frontend.*` (structural only), `event_code`, `status`, `job_type`, `operation`, `reason`, `account_id`

**All other attributes are silently dropped** — including any PII fields (phone, email, customer_name, prompt, body, address, etc.) that instrumentation libraries may inadvertently capture.

**Additional value-level redaction** (`_sanitize_attribute_value`):
- Email-like values (`@` + `.`) → `[REDACTED]`
- Phone-like values (8–16 digits with typical phone formatting) → `[REDACTED]`
- Bearer tokens, secrets, prompt text → `[REDACTED]`
- URL path dynamic segments (numeric IDs, UUIDs, hex tokens) → `{id}`

**Log export (`PrivacySafeLogFilter`):** Applied to all OTLP log handlers. Redacts authorization headers, tokens, passwords, secrets, query parameters, email addresses, and prompt/SMS body content from all log records before SigNoz export.

---

### 5.4 Mapbox Token Server-Side Isolation

`MAPBOX_ACCESS_TOKEN` is:
- Stored exclusively in server-side environment (`.env` / Docker secrets).
- Used only in `app/services/geocoding.py` for background geocoding of tenant addresses.
- **Never serialized** into API response bodies, frontend configs, or public endpoints.
- The geocoding service constructs the Mapbox URL server-side; coordinates are stored in the database and returned via `tenant.latitude`/`tenant.longitude` — not the raw token.

---

### 5.5 Admin System Health Endpoint

The `GET /api/admin/system/health` endpoint (implemented in [`app/api/routers/system.py`](file:///f:/Projects/fastapi_bookings/app/api/routers/system.py)) uses two functions from `app/core/` to measure live service latency:

| Core Function | Used By | Purpose |
|---|---|---|
| `get_redis_client()` in `redis.py` | `_check_redis()` | Issue a real `PING` and measure round-trip ms |
| `get_neo4j_driver()` in `graphiti_client.py` | `_check_neo4j()` | Run `RETURN 1` and measure round-trip ms |

The health endpoint never crashes — each probe is wrapped in `try/except`. If Redis or Neo4j is unavailable the service is reported as `"down"` and `api_status` is set to `"degraded"`.

**Background workers:** No Celery/ARQ queue system is configured. The endpoint reports `background_workers` as `{ status: "ok", latency_ms: null, detail: "source=none; no distributed task queue is configured" }` rather than inventing a fake count.

---

## Redis Integration & Key Namespacing

- **Key Prefixing**: All Redis keys are strictly formatted via `format_key()` with the prefix `fb:` or `fb:{tenant_id}:...` ensuring strict multi-tenant isolation.
- **Connection Pools**: Thread-safe sync (`get_redis_client()`) and async (`get_async_redis_client()`) connection pools lazily initialized with reconnect handling and bounded connection counts.
- **Health Checks**: Synchronous `ping()` and asynchronous `async_ping()` methods for liveness/readiness probes.
- **Resilient Fallback**: Graceful local in-memory fallback mechanisms protect callers during transient Redis unavailability.

---

## Data Safety & Privacy
- **Redaction by Design**: `telemetry.py` strips all customer identities, phone numbers, emails, addresses, and query-string tokens from traces and logs before exporting.
- **Low-Cardinality Attributes Only**: Spans record structural data like HTTP method, route template, status code, and tenant hash.
- **Hashed Identifiers in Caches**: OTP cache keys hash phone numbers (`fb:otp:{tenant_id}:{sha256(phone)}`) so cleartext customer numbers are never stored in cache keys.
- **Mapbox Token Isolation**: The geocoding API token is server-side only; coordinates are what the API returns, not the token.

---

## Known Issues, Edge Cases & Outstanding Work
- Telemetry span attribute allowlist (`SAFE_ATTRIBUTE_KEYS`) should be reviewed when adding new instrumentation libraries to ensure no new PII leakage paths are introduced.
- `OTEL_SDK_DISABLED=true` is enforced in all test fixtures via `conftest.py` to prevent any telemetry network calls during tests.

---

## Verification Commands
```bash
# Run Phase 5 governance, tenant resolution, and telemetry privacy tests
.venv\Scripts\python.exe -m pytest tests/test_tenant_resolution.py tests/test_telemetry_privacy.py -v

# Run security isolation, telemetry pipeline, and redaction tests
.venv\Scripts\python.exe -m pytest tests/test_security_isolation_remediation.py tests/test_telemetry_pipeline.py tests/test_telemetry_redaction.py tests/test_client_portal.py -v
```
