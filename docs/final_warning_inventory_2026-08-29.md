# FastAPI Bookings — Final Warning Inventory & Audit

**Date:** 2026-08-29  
**Branch:** `telemetry/observability-baseline`  
**Repository:** `F:\Projects\fastapi_bookings`  

---

## 1. Initial Warning Inventory (Before Remediation)

Prior to remediation, a full run of the backend test suite revealed two active deprecation warnings:

| Warning Class | Originating File / Package | Category / Source | Count per Test Run | Impact / Resolution Path |
|---|---|---|---|---|
| `DeprecationWarning` | `opentelemetry.sdk._logs._internal.__init__.py:548` (`opentelemetry-sdk`) | Direct Dependency (SDK Log Handler) | 4 (lifecycle tests) | **Fixed in Project Code:** Migrate import path to supported `opentelemetry.instrumentation.logging.handler.LoggingHandler`. |
| `StarletteDeprecationWarning` | `fastapi.testclient.py:1` -> `starlette.testclient.py:48` (`starlette`) | Direct/Test Dependency (`starlette.testclient`) | 1 (per test session) | **Fixed in Dependency / Test Setup:** Install and declare `httpx2` (modernized Starlette test client backend). |

---

## 2. Source Classification & Breakdown

### A. Warnings Fixable in Project Code
- **`opentelemetry-sdk` LoggingHandler:**
  - *Location:* `app/core/telemetry.py`
  - *Root Cause:* `LoggingHandler` was imported from `opentelemetry.sdk._logs`, which emitted a deprecation warning directing callers to the handler in `opentelemetry-instrumentation-logging`.
  - *Fix:* Updated `app/core/telemetry.py` to import `LoggingHandler` from `opentelemetry.instrumentation.logging.handler` with safe backwards-compatible fallback.

### B. Warnings Requiring Direct Dependency Update
- **`starlette.testclient` ASGI Transport (`httpx2`):**
  - *Location:* `starlette.testclient`
  - *Root Cause:* Starlette 1.3.1 introduced support for `httpx2` for ASGI test client transport and warned when falling back to legacy `httpx`.
  - *Fix:* Installed `httpx2>=2.12.0` and declared in `requirements.txt`.

### C. Warnings Originating Inside Third-Party Tooling
- None remaining.
