# Core Runtime Policies

## Purpose & Scope

The `app.core` package owns shared runtime configuration, security,
observability, and privacy boundaries used by more than one application
entrypoint. It does not own booking, customer, provider, calendar, SMS, AI, or
arrival business behavior.

## Architecture & Key Files

- `config.py`: validated server-side settings.
- `security.py`: authentication and password/token security helpers.
- `telemetry.py`: privacy-constrained OpenTelemetry traces, metrics, and logs.
- `privacy_logging.py`: shared web/worker HTTP logging bootstrap, namespace
  matching, factory-stage payload neutralization, handler-stage structural
  allowlisting, and JSON console formatting.

## Setup, Configuration & Dependencies

The privacy logging boundary uses Python logging and the existing
OpenTelemetry API. It adds no environment variables or database schema. The
web process calls `configure_privacy_safe_logging(include_server_loggers=True)`
before application-service imports. The standalone worker calls the same
bootstrap with server logger configuration disabled.

OpenTelemetry remains controlled by the existing settings documented in
`telemetry.py`. When telemetry is enabled, its operational
`PrivacySafeOTelLoggingHandler` has both `PrivacySafeAccessFilter` and the
existing general redaction filter. Synthetic verification uses only an
in-memory exporter; no real collector behavior is claimed.

## Core Workflows & Contracts

For the exact `app.access`, `uvicorn.access`, `httpx`, and `httpcore`
namespaces and their children:

1. The process `LogRecordFactory` replaces message/argument/exception/stack
   payloads with a fixed event, captures bounded structure in a lock-protected
   weak sidecar keyed by record identity, and canonicalizes a protected child
   logger name to its fixed family before handlers run. No trusted structure is
   stored in caller-controlled `LogRecord` extras.
2. `PrivacySafeAccessFilter` runs after `extra` merging. It deletes arbitrary
   attributes, including caller `otel*` values, and emits only the privately
   captured bounded method, route sentinel/template, status, duration bucket,
   and request ID. When factory provenance is absent, it uses a deterministic
   family-only `OTHER`/zero/sentinel fallback without reading the message,
   arguments, or extras.
3. `JSONFormatter` renders the structural console event. The privacy-specific
   OTel handler builds an exact protected attribute dictionary and excludes
   stock code-file/function/line attributes. Trace/span context and resource
   identity are supplied by the trusted SDK context/provider, not log extras.

Namespace matching is segment-aware. For example, `httpx._client` is
protected while `httpx2` is unrelated and remains unchanged.

## Data Safety & Isolation

Protected records never retain raw URLs, query strings, headers, cookies,
authorization values, bodies, exception text, stack text, arbitrary child
logger suffixes, caller-supplied OTel correlation fields, or other caller
attributes in configured console or telemetry output. Route data is accepted
only as a bounded code-owned template; external client logs use `<external>`
and server logs use `<unmatched>`.

This policy is process-local and contains no tenant data. Tenant/customer
identifiers must not be added to protected records. OpenTelemetry trace/span
correlation is taken from the active SDK context, and service identity from the
configured provider resource; neither is accepted from caller log extras.
Telemetry initialization failures use fixed structural event codes and never
include exception text, tracebacks, or configured collector endpoints.

## Known Issues, Edge Cases & Outstanding Work

- Custom console handlers added after bootstrap must attach
  `PrivacySafeAccessFilter`; custom OTel handlers must also use
  `PrivacySafeOTelLoggingHandler` so stock translation cannot add code-location
  fields. The factory neutralizes message payloads, but only the post-merge
  filter can remove caller `extra` attributes.
- A third-party library that replaces instead of chains the global record
  factory can remove factory-stage protection from an unfiltered custom
  handler. Configured handlers ignore caller-shaped provenance and apply a
  family-only filter-stage fallback. Startup integration tests cover the
  supported web and worker entrypoints.
- Trusted sidecar entries are weakly keyed and released with each log record;
  access is serialized so concurrent logging cannot mix record structure.
- The privacy OTel handler pins the installed SDK's private
  `_get_attributes(record)` hook and refuses initialization when that signature
  changes. SDK upgrades require the exact in-memory export tests; no live
  collector has been verified by this module.
- Reverse-proxy and platform logs are outside this Python-process boundary and
  require independent raw-query and credential logging controls.
- Inbound proxy request IDs are intentionally not trusted. Cross-proxy
  correlation requires a separately approved trace or trusted-header policy.

## Verification & Testing Commands

```powershell
$env:OTEL_SDK_DISABLED='true'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider tests/test_validation_error_privacy.py tests/test_numeric_id_bounds.py tests/test_auth_contract.py tests/test_telemetry_pipeline.py
python -m py_compile app/main.py app/worker.py app/core/privacy_logging.py app/core/telemetry.py tests/test_validation_error_privacy.py tests/test_telemetry_pipeline.py
python -m ruff check app/core/privacy_logging.py app/worker.py tests/test_validation_error_privacy.py tests/test_telemetry_pipeline.py
python -m ruff check app/core/telemetry.py --ignore F401,F841
python -m ruff check app/main.py --ignore F401,E402,F811
```

The privacy tests use only synthetic request data, subprocess imports, and an
in-memory OpenTelemetry exporter. They do not contact an external collector or
perform SMS, booking, payment, or customer actions.
