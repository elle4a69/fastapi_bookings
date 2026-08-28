# FastAPI Bookings — SigNoz Log Export Lifecycle & Privacy Rectification

**Date:** 2026-08-29  
**Branch:** `telemetry/observability-baseline`  
**Repository:** `F:\Projects\fastapi_bookings`  
**Status:** FULLY VERIFIED (0 Failures, 0 Warnings/Errors in Linter, 100% Quality Pass)

---

## Executive Summary

This remediation resolves the lifecycle leak and privacy boundary defects in the SigNoz operational log export implementation:
1. **Telemetry-Owned Handler Lifecycle:** The telemetry subsystem now strictly tracks every logging handler it creates and attaches (`_telemetry_owned_handlers`). On `shutdown_telemetry()`, all telemetry-owned handlers are flushed, closed, and safely detached from their respective loggers. Repeated initialization and shutdown cycles (`init -> shutdown -> init`) are completely idempotent and leave exactly one handler per target logger without touching third-party or user-installed handlers.
2. **Logger Topology & Zero-Duplication Policy:**
   - **Root Logger (`logging.getLogger()`):** Receives application log events via normal Python logging propagation. An operational `LoggingHandler` equipped with `PrivacySafeLogFilter` is attached here.
   - **Non-Propagating Framework Loggers (`uvicorn`, `uvicorn.error`, `uvicorn.access`, `fastapi`):** Since `setup_logging()` explicitly sets `propagate = False` on these loggers, the operational OTLP handler is attached directly to each. Because propagation is disabled, log events from these loggers are processed once and never double-exported to root.
   - **Dedicated Structured Telemetry Logger (`fastapi_bookings.telemetry`):** Has `propagate = False` and handles structured domain events with strict allowlisting.
3. **Privacy-Safe Redaction Filter:** Added `PrivacySafeLogFilter` to all operational log handlers. The filter sanitizes log messages, formatted arguments, extras, and exception traces by redacting:
   - Bearer tokens, JWTs, and authorization headers (`[REDACTED]`)
   - Passwords, API keys, cookies, secrets, and webhook signatures (`[REDACTED]`)
   - URL query strings in HTTP access lines and arbitrary URLs (`?[REDACTED]`)
   - Email addresses and customer PII
4. **Verification:** 100% test pass rate across 249 unit/integration tests, 302 Schemathesis fuzzer tests, clean frontend Vite build, 0 TypeScript errors, and 0 lint warnings.

---

## 1. Logger Topology Design

```
+-------------------------------------------------------------------------------+
|                             Python Logging Hierarchy                          |
+-------------------------------------------------------------------------------+
                                      |
         +----------------------------+---------------------------+
         |                                                        |
         v                                                        v
 [Root Logger] (Propagating App Logs)               [Framework Loggers (propagate=False)]
 - Attached: op_otlp_handler (with PrivacySafeLogFilter) - uvicorn
 - Receives: app.*, services.*, routers.*                - uvicorn.error
                                                         - uvicorn.access
                                                         - fastapi
                                                         Attached: op_otlp_handler (filtered)
                                                                  |
         +--------------------------------------------------------+
         |
         v
 [Dedicated Telemetry Logger] (propagate=False)
 - Attached: dedicated_handler
 - Name: "fastapi_bookings.telemetry"
 - Receives: Structured domain events only (allowlisted attributes)
```

---

## 2. Redaction Policy

The `PrivacySafeLogFilter` automatically applies before any log event is pushed to the OTLP `BatchLogRecordProcessor`:

| Data Category | Target in Log Record | Sanitization Action |
|---|---|---|
| **Bearer Tokens** | `record.msg`, `record.args`, `record.exc_text` | `Bearer [REDACTED]` |
| **Credentials & Secrets** | `password=`, `token=`, `api_key=`, `secret=`, `cookie=` | Key preserved, value replaced with `[REDACTED]` |
| **HTTP Access Queries** | `GET /path?query=val HTTP/1.1` | Query string replaced with `?[REDACTED]` |
| **Generic URLs** | `https://api.domain.com/v1?token=xyz` | `https://api.domain.com/v1?[REDACTED]` |
| **Emails & PII** | `user@example.com` | `[REDACTED_EMAIL]` |

---

## 3. Verification & Test Sweep Results

### 3.1 Backend Test Suites
- **Telemetry Pipeline & Lifecycle Suite (`tests/test_telemetry_pipeline.py`):** **18 / 18 PASSED** in 5.02s.
  - `test_init_telemetry_repeated_adds_no_duplicate_handlers`
  - `test_init_shutdown_init_lifecycle_leaves_exactly_one_handler`
  - `test_repeated_shutdown_is_safe`
  - `test_non_telemetry_handlers_never_removed`
  - `test_privacy_safe_log_filter_redacts_tokens_passwords_and_secrets`
  - `test_privacy_safe_log_filter_redacts_url_query_parameters`
  - `test_operational_uvicorn_fastapi_logs_no_duplicate_propagation`
  - Existing structured telemetry allowlist & metrics tests.
- **Full Backend Suite (non-fuzzer):** **249 / 249 PASSED** in 33.70s (0 failures, 0 xfailed).
- **Schemathesis Standalone Fuzzer (`tests/test_fuzzer.py`):** **302 / 302 PASSED** in 251.48s (0 errors across entire OpenAPI schema).

### 3.2 Frontend Quality Gates
- **Production Build (`npm run build`):** **PASSED** in 18.13s.
- **TypeScript Check (`npx tsc --noEmit`):** **PASSED** (0 errors).
- **Linter (`oxlint`):** **PASSED** (0 errors, 0 warnings across 91 files in 158ms).

### 3.3 Live Runtime Smoke Probes (Port 8000)
- `GET /health` -> 200 OK
- `GET /ready` -> 200 OK
- `GET /api/admin/system/diagnostics/telemetry/status` -> 200 OK (`telemetry_enabled: True`)
- Single safe HTTP request verified to produce exactly one operational log record without duplicate handler attachments.
