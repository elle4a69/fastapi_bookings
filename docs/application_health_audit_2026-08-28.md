# FastAPI Bookings — Comprehensive Application Health Audit

**Date**: 2026-08-28
**Audit Scope**: Repository & Startup Integrity, Backend Routes & Tests, Frontend Type-Safety & API Contracts, Integrations, Performance & Reliability.
**Branch**: `telemetry/observability-baseline`
**HEAD Commit**: `b7e512214b3d13cf5f6a99a21ac1afcf6f43ebad`
**Safety Directives Followed**: Zero code/config/DB changes made; no live customer/SMS/booking actions triggered; `.env` unread/unprinted; `integrations/assistant-ui-v2/` preserved untouched.

---

## A. Executive Summary

- **Overall Application Status**: **DEGRADED**
  The core FastAPI backend, PostgreSQL database, SigNoz observability pipeline, Chatwoot service, and frontend Vite dev runtime are active and healthy. However, the application is rated **Degraded** due to:
  1. Frontend TypeScript compiler errors (`tsc -b`) blocking strict CI builds (`npm run build`).
  2. 26 frontend-to-backend API route contract mismatches (chiefly in Finance, Notification Templates, and Plugin Settings admin pages).
  3. 4 specific backend test failures (cross-tenant provider validation, restricted client approval, public tenant fallback, waitlist hold concurrency).
- **Findings Summary**:
  - **Critical**: 0
  - **High**: 2
  - **Medium**: 3
  - **Low**: 2
- **Confirmed Working**:
  - FastAPI backend startup and `/health`, `/ready`, `/version` endpoints (HTTP 200).
  - Outbox and SMS background worker loops starting and running with active trace contexts.
  - End-to-end SigNoz telemetry export on port `4318` (traces in `signoz_index_v3`, logs in `logs_v2`, metrics in `samples_v4`, 0 privacy leaks).
  - PostgreSQL database queries and connection pooling.
  - Chatwoot server reachability (port 3000).
  - Frontend Vite bundling (`npx vite build` transforms all 1,973 modules into `dist/` in 2.30s).
- **What Was Not Tested & Rationale**:
  - Live SMS sending / external ClickSend API calls (avoid real communication / charges).
  - Live payments / refund processing (avoid modifying financial data).
  - Customer data mutation forms (strictly read-only / synthetic tests per `AGENTS.md`).

---

## B. Findings Table

| ID | Severity | Component | Summary | Expected Behavior | Actual Behavior | Safe to Repair Without Approval? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **AUDIT-001** | **High** | Frontend Type Checking | `npm run build` (`tsc -b`) fails with 67 compiler errors across 8 files. | `tsc -b` passes with zero compiler errors. | Fails with `TS6133` (unused variables), `TS6192` (unused imports), `TS1484` (non-type import for `ChangeEvent`). | **Yes** (pure type-checking & lint cleanup). |
| **AUDIT-002** | **High** | Backend Cross-Tenant Isolation | `POST /api/public/bookings` accepts a `provider_id` belonging to a different tenant. | Returns HTTP 400 or 404 when provider does not belong to the active tenant. | Booking is created under Tenant A with Tenant B's provider (HTTP 200). | **No** (requires approval of business validation error response format). |
| **AUDIT-003** | **Medium** | Backend Booking Policies | `POST /api/public/bookings` bypasses `client.management_approval_required`. | Returns HTTP 403 Forbidden when client requires management review. | Booking is created directly without review (HTTP 200). | **Yes** (enforces existing model attribute). |
| **AUDIT-004** | **Medium** | Backend Public Tenant Fallback | `/api/public/services` defaults to first tenant when unauthenticated. | Returns HTTP 401 Unauthorized when unauthenticated request lacks tenant context. | Returns HTTP 200 with first tenant's catalog. | **No** (requires architectural decision on public discovery authentication boundary). |
| **AUDIT-005** | **Medium** | Frontend/Backend API Contracts | 26 frontend API calls use non-existent route paths (e.g. `/api/admin/finance/*`). | Frontend paths match implemented backend endpoints. | Admin UI pages for Finance, Notification Templates, and Plugin Settings fail with 404. | **Yes** (align frontend URLs to existing backend routes). |
| **AUDIT-006** | **Low** | Backend Router Mounting | `notifications.router` mounted twice in `main.py` (with and without `/api/admin` prefix). | Router mounted once under canonical `/api/admin` prefix. | Duplicate root endpoints (`/notifications`, `/reminder-rules`) exposed. | **Yes** (removes duplicate `include_router`). |
| **AUDIT-007** | **Low** | OpenAPI Generation | Duplicate operation ID warning for `create_public_booking`. | Unique operation IDs across all endpoints. | Warning emitted during OpenAPI schema generation. | **Yes** (specify explicit `operation_id`). |

---

### Detailed Finding Reports

#### AUDIT-001: Frontend `tsc -b` Strict Compilation Errors
- **Component**: `frontend/src/` (`locations.tsx`, `packages.tsx`, `providers.tsx`, `services.tsx`, `media.tsx`, `relationships-matrix.tsx`, `relationships-tree.tsx`, `resources.tsx`, `booking-page.tsx`, `upload-page.tsx`)
- **Reproduction**: Run `npm run build` in `frontend/`.
- **Evidence**:
  ```
  src/pages/public/upload-page.tsx(1,31): error TS1484: 'ChangeEvent' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.
  src/pages/admin/catalog/locations.tsx(2,126): error TS6133: 'Gift' is declared but its value is never read.
  src/pages/admin/catalog/services.tsx(156,22): error TS6133: 'setIsListView' is declared but its value is never read.
  ```
- **Impact**: Strict CI build (`tsc -b && vite build`) is blocked, although `npx vite build` succeeds.
- **Recommended Repair**: Fix type-only imports (`import type { ChangeEvent }`) and remove/prefix unused local variables across the 8 affected files.

#### AUDIT-002: Cross-Tenant Provider Validation Missing in Public Booking Route
- **Component**: `app/api/routers/public_bookings.py`
- **Reproduction**: `pytest tests/test_security_fuzzing.py -k "test_cross_tenant_isolation_attempts"`
- **Evidence**:
  ```python
  resp_booking = client.post(
      "/api/public/bookings",
      json={
          "client_id": data["client_a"].id,
          "provider_id": data["provider_b"].id,  # Tenant B provider
          "service_id": data["service_a"].id,
          "start_time": "2026-07-09T10:00:00Z",
          "end_time": "2026-07-09T10:30:00Z"
      },
      headers=public_headers_a
  )
  assert resp_booking.status_code in [400, 404]
  # FAILED: returned HTTP 200
  ```
- **Impact**: Tenant isolation gap on public booking creation route.
- **Recommended Repair**: Validate in `create_public_booking` that `provider.tenant_id == tenant.id` and `service.tenant_id == tenant.id`.

#### AUDIT-003: Restricted Client Approval Check Missing in Public Booking Route
- **Component**: `app/api/routers/public_bookings.py`
- **Reproduction**: `pytest tests/test_booking_policies_remediation.py -k "test_client_restriction_ordinary_booking"`
- **Evidence**:
  ```
  assert response.status_code == status.HTTP_403_FORBIDDEN
  E assert 200 == 403
  ```
- **Impact**: Restricted clients flagged with `management_approval_required=True` can book without approval.
- **Recommended Repair**: Check `client.management_approval_required` in `create_public_booking` and return 403 Forbidden when flagged.

#### AUDIT-004: Public Entity Endpoints Silently Fallback to Default Tenant
- **Component**: `app/api/routers/public_entities.py`, `app/api/deps.py`
- **Reproduction**: `pytest tests/test_public_entities_remediation.py -k "test_public_entities_tenant_isolation"`
- **Evidence**: `assert response_missing.status_code == 401` returned `200`.
- **Impact**: Unauthenticated requests without `X-Tenant` header or subdomain return first tenant's catalog data.
- **Recommended Repair**: Clarify tenant resolution requirement for unauthenticated public catalog endpoints.

#### AUDIT-005: Frontend/Backend Route Path Mismatches
- **Component**: `frontend/src/pages/admin/finance/*`, `frontend/src/pages/admin/notifications/*`, `frontend/src/pages/admin/settings/*`
- **Reproduction**: Automated route scan comparing frontend `apiClient` calls against `app.openapi()`.
- **Key Discrepancies**:
  - `pages/admin/finance/invoices.tsx` -> calls `GET /api/admin/finance/invoices` (backend is `/api/admin/invoices`)
  - `pages/admin/finance/payments.tsx` -> calls `GET /api/admin/finance/payments` (backend is `/api/admin/payments`)
  - `pages/admin/finance/processors.tsx` -> calls `GET /api/admin/finance/processors` (backend is `/api/admin/payment-processors`)
  - `pages/admin/finance/promotions.tsx` -> calls `GET /api/admin/finance/promotions` (backend is `/api/admin/promotions`)
  - `pages/admin/finance/tax-rates.tsx` -> calls `GET /api/admin/finance/tax-rates` (backend is `/api/admin/tax-rates`)
  - `pages/admin/notifications/messages.tsx` -> calls `GET /api/admin/notifications/messages` (backend is `/api/admin/notifications`)
  - `pages/admin/notifications/templates.tsx` -> calls `GET /api/admin/notifications/templates` (backend is `/api/admin/notification-templates`)
  - `pages/admin/settings/plugins.tsx` -> calls `GET /api/admin/ui-config` (backend is `/api/public/ui-config/admin`)
- **Impact**: 404 errors when navigating to Admin Finance, Notification Templates, and Plugin settings.
- **Recommended Repair**: Update frontend `apiClient` URLs to match the canonical backend routes.

---

## C. API Contract Matrix

| Frontend Caller / File | Method | Frontend Path | Backend Route | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `pages/admin/bookings.tsx:86` | GET | `/api/bookings` | `/api/bookings` | **Matched** | Paginated bookings |
| `pages/admin/bookings.tsx:137` | PUT | `/api/bookings/{id}` | `/api/bookings/{booking_id}` | **Matched** | Booking status update |
| `pages/admin/calendar.tsx:458` | GET | `/api/admin/services` | `/api/admin/services` | **Matched** | Service list |
| `pages/admin/calendar.tsx:459` | GET | `/api/admin/providers` | `/api/admin/providers` | **Matched** | Provider list |
| `pages/admin/calendar.tsx:460` | GET | `/api/admin/locations` | `/api/admin/locations` | **Matched** | Location list |
| `pages/admin/calendar.tsx:461` | GET | `/api/admin/clients` | `/api/admin/clients` | **Matched** | Client list |
| `pages/admin/calendar.tsx:462` | GET | `/api/admin/calendar-notes` | `/api/admin/calendar-notes` | **Matched** | Calendar notes |
| `pages/admin/catalog/add-ons.tsx:119` | GET | `/api/admin/add-ons` | `/api/admin/add-ons` | **Matched** | Add-on catalog |
| `pages/admin/catalog/categories.tsx:119` | GET | `/api/admin/categories` | `/api/admin/categories` | **Matched** | Category catalog |
| `pages/admin/catalog/packages.tsx:94` | GET | `/api/admin/packages` | `/api/admin/packages` | **Matched** | Package catalog |
| `pages/admin/catalog/products.tsx:106` | GET | `/api/admin/products` | `/api/admin/products` | **Matched** | Product catalog |
| `pages/admin/resources.tsx:75` | GET | `/api/admin/resources` | `/api/admin/resources` | **Matched** | Resource list |
| `pages/admin/booking-forms.tsx:78` | GET | `/api/admin/booking-forms` | `/api/admin/booking-forms` | **Matched** | Form presets |
| `pages/public/booking-page.tsx:95` | GET | `/api/public/booking-forms/{slug}` | `/api/public/booking-forms/{slug}` | **Matched** | Public widget bootstrap |
| `pages/public/booking-page.tsx:180` | POST | `/api/public/booking-forms/{slug}/resolve` | `/api/public/booking-forms/{slug}/resolve` | **Matched** | Preset resolution |
| `lib/telemetry.ts:8` | POST | `/api/public/diagnostics/telemetry` | `/api/public/diagnostics/telemetry` | **Matched** | Frontend diagnostics |
| `pages/admin/finance/invoices.tsx:71` | GET | `/api/admin/finance/invoices` | `/api/admin/invoices` | **MISMATCH** | Route prefix mismatch (`/finance`) |
| `pages/admin/finance/payments.tsx:35` | GET | `/api/admin/finance/payments` | `/api/admin/payments` | **MISMATCH** | Route prefix mismatch (`/finance`) |
| `pages/admin/finance/payments.tsx:51` | POST | `/api/admin/finance/payments/{id}/refund` | `/api/admin/payments/{payment_id}/refund` | **MISMATCH** | Route prefix mismatch (`/finance`) |
| `pages/admin/finance/processors.tsx:43` | GET | `/api/admin/finance/processors` | `/api/admin/payment-processors` | **MISMATCH** | Path naming mismatch |
| `pages/admin/finance/promotions.tsx:47` | GET | `/api/admin/finance/promotions` | `/api/admin/promotions` | **MISMATCH** | Route prefix mismatch (`/finance`) |
| `pages/admin/finance/tax-rates.tsx:35` | GET | `/api/admin/finance/tax-rates` | `/api/admin/tax-rates` | **MISMATCH** | Route prefix mismatch (`/finance`) |
| `pages/admin/notifications/messages.tsx:25` | GET | `/api/admin/notifications/messages` | `/api/admin/notifications` | **MISMATCH** | Subpath mismatch (`/messages`) |
| `pages/admin/notifications/templates.tsx:34` | GET | `/api/admin/notifications/templates` | `/api/admin/notification-templates` | **MISMATCH** | Path naming mismatch |
| `pages/admin/settings/plugins.tsx:41` | GET | `/api/admin/ui-config` | `/api/public/ui-config/admin` | **MISMATCH** | Admin config route path |
| `pages/admin/reviews.tsx:84` | PUT | `/api/admin/management-reviews/{id}` | `POST .../{id}/approve` or `reject` | **MISMATCH** | Verb/endpoint pattern |

*Total calls inventoried: 255 | Matched: 229 | Mismatches: 26*

---

## D. Test and Runtime Evidence

### 1. Backend Startup & Health
- **Command**: `.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Result**: Startup complete in 780ms; zero `ImportError` or worker loop errors.
- **Health Check**: `GET http://127.0.0.1:8000/health` -> HTTP 200 `{"ok": true}`
- **Database Readiness**: `GET http://127.0.0.1:8000/ready` -> HTTP 200 `{"ok": true}`

### 2. Frontend Dev Server & Build
- **Dev Server**: `http://localhost:7070` -> HTTP 200 OK (HTML shell served).
- **Vite Direct Build**: `npx vite build` -> **SUCCESS** (1,973 modules transformed into `dist/` in 2.30s).
- **TypeScript Strict Build**: `npm run build` (`tsc -b`) -> **FAILED** (67 compiler errors across 8 files).

### 3. Backend Test Suite (Non-Fuzzer)
- **Command**: `.venv\Scripts\python.exe -m pytest tests/ -k "not test_fuzzer" --tb=short`
- **Results**:
  - **Passed**: 109
  - **Failed**: 4 (`test_security_fuzzing`, `test_booking_policies_remediation`, `test_public_entities_remediation`, `test_concurrency`)
  - **XFailed**: 1 (`test_concurrent_holds_same_slot` known concurrency constraint)
  - **Deselected**: 309
  - **Duration**: 50.29s

### 4. Telemetry Pipeline Validation
- **Command**: `.venv\Scripts\python.exe bin\validate_signoz_live.py`
- **Result**: **PASSED** (Exit code 0).
  - Traces confirmed in `signoz_traces.signoz_index_v3` (3/3 received).
  - Structured logs confirmed in `signoz_logs.logs_v2` (1/1 received).
  - Metric samples confirmed in `signoz_metrics.samples_v4` (2 samples received).
  - Privacy canary scan confirmed 0 leaks.

### 5. Running Port & Process Inventory
- Port `8000`: FastAPI Backend (PID `115020`)
- Port `7070`: Frontend Vite Dev Server (PID `9144`)
- Port `4318`: SigNoz OTLP HTTP Collector (`signoz-ingester-1`)
- Port `4317`: SigNoz OTLP gRPC Collector (`signoz-ingester-1`)
- Port `8080`: SigNoz Web UI & Query Service (`signoz-signoz-0`)
- Port `3000`: Chatwoot Service (`chatwoot-rails-1`)
- Port `5432`: PostgreSQL Database (`fastapi_bookings`)

---

## E. Explicit Non-Findings (Confirmed Healthy)

1. **Database Layer**: PostgreSQL connection pool, table schemas, relationships, and queries operate normally without connection leaks or serialization errors.
2. **SigNoz Observability Pipeline**: Trace, metric, and structured log export pipelines are fully functional and fail-closed on port 4318.
3. **Background Worker Loops**: `outbox_worker` and `sms_outbox_worker` initialize cleanly with valid OpenTelemetry span context; zero import or runtime crashes.
4. **Chatwoot Integration**: Rails service is healthy and reachable on port 3000.
5. **CORS Configuration**: Handles allowed origins dynamically from settings with proper headers.
6. **Frontend Bundler**: Vite build handles all modules, CSS, React 19 components, and assets into production bundles without runtime packaging errors.

---

## F. Recommended Next Repair Tasks (In Priority Order)

### Task 1: Fix Frontend TypeScript Strict Compilation Errors (AUDIT-001)
- **Scope**: `frontend/src/pages/admin/catalog/*`, `frontend/src/pages/admin/media.tsx`, `frontend/src/pages/public/upload-page.tsx`, `frontend/src/pages/public/booking-page.tsx`.
- **Action**: Fix type-only imports (`import type { ChangeEvent }`) and clean up unused variables/imports to ensure `npm run build` (`tsc -b && vite build`) passes cleanly.
- **Estimated Scope**: Small (~8 files, purely static typing cleanup, zero logic changes).

### Task 2: Align Frontend Admin API Route Contracts (AUDIT-005)
- **Scope**: `frontend/src/pages/admin/finance/*`, `frontend/src/pages/admin/notifications/*`, `frontend/src/pages/admin/settings/plugins.tsx`.
- **Action**: Update mismatched `apiClient` paths to point to existing canonical backend endpoints (`/api/admin/invoices`, `/api/admin/payments`, `/api/admin/notification-templates`, etc.).
- **Estimated Scope**: Small (~5 frontend files, zero backend API invention).

### Task 3: Enforce Cross-Tenant and Policy Checks on Public Booking Endpoint (AUDIT-002, AUDIT-003)
- **Scope**: `app/api/routers/public_bookings.py`, `tests/test_security_fuzzing.py`, `tests/test_booking_policies_remediation.py`.
- **Action**: In `create_public_booking`, add validation ensuring `provider.tenant_id == tenant.id`, `service.tenant_id == tenant.id`, and `not client.management_approval_required` (returning 403).
- **Estimated Scope**: Small (~1 router file, 2 test files).
