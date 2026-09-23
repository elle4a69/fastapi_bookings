# Application Entrypoint and HTTP Error Boundary

## Purpose & Scope

The `app` package contains the FastAPI Bookings application. `main.py` creates
the FastAPI instance, installs middleware and exception handlers, and registers
the application routers. Business workflows remain owned by their routers and
services; this entrypoint does not own booking, SMS, AI, calendar, or provider
domain behavior.

## Architecture & Key Files

- `main.py`: application construction, router registration, middleware, CORS,
  lifecycle hooks, and shared HTTP error envelopes.
- `api/`: authenticated and public API routers and dependencies.
- `services/`: domain workflows and external-integration boundaries.
- `models/` and `schemas/`: database and API data contracts.
- `core/`: configuration, security, telemetry, and shared application policy.

## Setup, Configuration & Dependencies

The entrypoint uses the existing FastAPI, Starlette, Pydantic, SQLAlchemy,
SlowAPI, and OpenTelemetry dependencies. No new environment variables or
external services are required for validation-error handling. Database schema
changes are managed through Alembic and are outside this module change.

## Core Workflows & Contracts

`RequestValidationError` produces HTTP 422 (unprocessable content) with the
standard application envelope: `ok=false`, error code `VALIDATION_ERROR`, a
generic message, bounded structural details, and a non-empty request ID. Each
detail exposes only a source category, an allowlisted error category, and a
fixed message. It does not serialize Pydantic errors verbatim. The handler
examines at most 256 errors, deduplicates their structural categories, sorts
them deterministically, and returns at most 20 details.

The correlation middleware creates one validated 32-character hexadecimal
request ID (using the active trace ID when valid, otherwise a random ID),
stores it in `request.state`, and reuses that exact value in the error envelope,
`X-Request-ID`, `X-Trace-ID`, and the application access event.

HTTP authentication, authorization, not-found, and method-not-allowed behavior
continues through the existing dependency and HTTP-exception boundaries.

## Data Safety & Isolation

Validation responses and validation-handler logs must never include request
body values, query/header/cookie values, authorization material, Pydantic
`input` or `ctx`, raw parser messages, dynamic field keys, prompts, canaries, or
customer data. The handler emits no validation log. Tenant and authorization
behavior is unchanged.

Application-controlled access logging is structural. Before any configured
handler or exporter receives a record, records from `app.access`,
`uvicorn.access`, HTTPX, and HTTPCore have their arbitrary messages, arguments,
exception text, and stack text replaced. The application event contains only
an allowlisted method, code-owned route template, numeric status, finite
latency bucket, and validated request ID. Uvicorn access records retain only
method/status with an `<unmatched>` route sentinel, and client records use an
`<external>` sentinel. Raw URLs, query strings, cookies, headers, bodies, and
arbitrary transport messages are not retained. This boundary is installed
even when OpenTelemetry is disabled.

## Known Issues, Edge Cases & Outstanding Work

- The structural validation response intentionally omits field-level paths;
  dynamically keyed objects can otherwise turn error locations into a data-
  reflection channel. This reduces field-specific UI guidance. The current
  frontend consumes the generic error message and does not depend on reflected
  field paths, so its existing contract remains compatible.
- The handler categorizes unknown future Pydantic error types as `invalid`.
- Because server/client libraries do not expose a trustworthy code-owned route
  template at record-construction time, their sanitized records deliberately
  use fixed sentinels. `app.access` is the authoritative route-template event.
- The installed record factory protects application-controlled Python logging.
  Reverse proxies and platform infrastructure remain separately responsible
  for disabling raw URL/query logging outside this process.
- This dependency set predates Starlette's
  `HTTP_422_UNPROCESSABLE_CONTENT` export. The entrypoint uses that name with a
  numeric 422 compatibility fallback and can drop the fallback after Starlette
  is upgraded.
- A full-file Ruff run on `main.py` still reports inherited unused/import-order
  findings outside this handler. The scoped verification below excludes only
  those existing `F401`, `E402`, and duplicate-import `F811` categories.

## Verification & Testing Commands

Run synthetic validation privacy and compatibility tests with telemetry off:

```powershell
$env:OTEL_SDK_DISABLED='true'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider tests/test_validation_error_privacy.py
python -m pytest -q -p no:cacheprovider tests/test_validation_error_privacy.py tests/test_numeric_id_bounds.py tests/test_auth_contract.py
python -m py_compile app/main.py tests/test_validation_error_privacy.py
python -m ruff check tests/test_validation_error_privacy.py
python -m ruff check app/main.py --ignore F401,E402,F811
```

Tests use in-process TestClient requests and labelled synthetic values only;
they perform no external network, SMS, booking, payment, or customer action.
