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
- `worker.py`: standalone generic/SMS worker entrypoint using the same privacy-
  safe logging bootstrap as the web process.
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

The outermost correlation middleware creates one validated 32-character
hexadecimal request ID (using the active trace ID when valid, otherwise a
random ID) and holds it in a request-scoped `ContextVar`. `request.state` is a
projection, not the authority, so downstream replacement cannot cause the
error envelope, `X-Request-ID`, `X-Trace-ID`, and application access event to
diverge. The outer placement also gives allowed and denied CORS preflight
responses the same correlation and structural access contract.

HTTP authentication, authorization, not-found, and method-not-allowed behavior
continues through the existing dependency and HTTP-exception boundaries.

## Data Safety & Isolation

Validation responses and validation-handler logs must never include request
body values, query/header/cookie values, authorization material, Pydantic
`input` or `ctx`, raw parser messages, dynamic field keys, prompts, canaries, or
customer data. The handler emits no validation log. Tenant and authorization
behavior is unchanged.

Application-controlled access logging is structural. The process record
factory first replaces arbitrary messages, arguments, exception text, and
stack text for the exact `app.access`, `uvicorn.access`, `httpx`, and `httpcore`
namespaces and their children and canonicalizes every protected child name to
its fixed family. Segment-aware matching leaves lookalike or unrelated loggers
unchanged. A filter on the configured console and OpenTelemetry handlers then
runs after caller `extra` values are merged, removes every caller attribute
(including values named like OpenTelemetry correlation fields), and publishes
only the approved structural fields captured privately by the factory. This
two-stage design avoids `LoggerAdapter` semantic-field collisions while
preventing request URLs, headers, cookies, authorization data, bodies, child
logger suffixes, and arbitrary transport data from reaching configured output.

The application event contains only an allowlisted method, code-owned route
template, numeric status, finite latency bucket, and validated request ID.
Uvicorn access records retain method/status with an `<unmatched>` route
sentinel, and client records use an `<external>` sentinel. Both the web and
standalone worker entrypoints install the boundary before importing their
application services, including when OpenTelemetry is disabled.

The privacy-specific OpenTelemetry logging handler delegates unrelated records
to the installed SDK behavior. For protected records it constructs an exact
attribute set after stock translation would normally add code-location fields:
method, route sentinel/template and status, plus duration bucket and request ID
only when available. Trace/span correlation comes from the active trusted OTel
context and service identity comes from the configured provider resource;
caller `otel*` extras are never promoted. Tests use an in-memory exporter and
do not establish delivery or privacy behavior in a real collector.

The current FastAPI runtime keeps included routers lazy: the matched route
stored in the request scope can contain only the router-local path. The
application access event therefore combines the matched `_IncludedRouter`'s
code-owned prefix with that local route template. It never uses the raw
request path, so dynamic path values remain absent from logs while the
template retains its full API prefix.

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
- The shared bootstrap protects handlers configured by the application.
  Future custom console handlers must attach `PrivacySafeAccessFilter`, and
  custom OTel handlers must use `PrivacySafeOTelLoggingHandler` as well; the
  filter alone cannot stop a stock OTel handler adding code-location fields.
  The factory still neutralizes protected message/argument/exception payloads,
  but a custom unfiltered handler could export arbitrary caller `extra`
  attributes. A later library that replaces rather than chains the global
  record factory can remove the first-stage protection for unfiltered custom
  handlers; configured handlers retain their filter-stage fail-closed path.
- The protected OTel attribute builder pins the installed SDK's private
  `_get_attributes(record)` hook and fails initialization if its signature is
  incompatible. Any OpenTelemetry SDK upgrade must rerun the in-memory exact-
  body, scope, resource and attribute tests before deployment.
- Reverse proxies and platform infrastructure remain separately responsible
  for disabling raw URL/query logging outside this process. The application
  deliberately creates its own request ID rather than trusting an inbound
  proxy-provided value; cross-proxy correlation requires a separately approved
  trusted-header or trace-context policy.
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
python -m py_compile app/main.py app/worker.py app/core/privacy_logging.py app/core/telemetry.py tests/test_validation_error_privacy.py
python -m ruff check tests/test_validation_error_privacy.py
python -m ruff check app/core/privacy_logging.py app/worker.py tests/test_validation_error_privacy.py
python -m ruff check app/core/telemetry.py --ignore F401,F841
python -m ruff check app/main.py --ignore F401,E402,F811
```

Tests use in-process TestClient requests and labelled synthetic values only;
they perform no external network, SMS, booking, payment, or customer action.
