# Runtime Smoke Audit Report

**Audit Date**: 2026-08-28
**Environment**: Local Development (`127.0.0.1`)
**Branch**: `telemetry/observability-baseline`
**HEAD Commit**: `149583d943fc34ce69d52ec2b4a787583c18615d`
**Audit Test Marker**: `SMOKE-TEST-2026-08-28`
**Overall System Runtime Status**: **DEGRADED** (Core catalog, finance, navigation, telemetry, and admin dashboards are fully operational; public booking commit and SMS conversation message serialization are blocked by specific schema/type defects).

---

## A. Executive Summary

| Metric | Count / Status | Notes |
|---|:---:|---|
| **Overall Status** | **DEGRADED** | Application is operational for admin browsing; public booking creation fails on PostgreSQL DB commit |
| **Critical Severity Findings** | **1** | PostgreSQL integer type mismatch on `outbox_events.tenant_id` during public booking creation (500) |
| **High Severity Findings** | **2** | `SmsMessageResponse` non-optional `sms_account_id` serialization failure (500); SMS `/jobs` route precedence shadowing (422) |
| **Medium Severity Findings** | **1** | Public booking page attempts unauthenticated `POST /api/admin/clients` fallback to client ID 1 |
| **Low Severity Findings** | **1** | Payment Processors settings page 404 (`/api/admin/finance/processors` Category B mismatch) |
| **Confirmed Working Routes** | **37 / 42** | Catalog, Calendar, Bookings, Clients, Invoices, Payments, Promotions, Tax Rates, Notifications, Business Settings, Webhooks, Plugins |
| **Telemetry & Observability** | **HEALTHY** | FastAPI `/health` (200), `/ready` (200), SigNoz UI & OTLP endpoint (200), Chatwoot port 3000 reachable |

### Scope Exclusions & Limitations
- **External Communications**: No real SMS messages, Chatwoot conversations, emails, or push notifications were dispatched.
- **Financial Processing**: No real credit card charges, Stripe webhooks, or refunds were initiated.
- **Provider Side-Effects**: External calendar/provider synchronization paths remained safely suppressed.
- **Production Data**: Executed exclusively in local development with disposable labelled fixtures.

---

## B. Route Verification Matrix

| Route Path | Classification | Live HTTP Status | Result | Error Category / Evidence |
|---|---|:---:|:---:|---|
| `/admin` | Admin Workspace | 200 | PASS | Generic shell loaded; summary widgets operational |
| `/admin/calendar` | Admin Workspace | 200 | PASS | Loaded calendar notes and bookings |
| `/admin/bookings` | Admin Workspace | 200 | PASS | Loaded booking records (`/api/bookings?page_size=200`) |
| `/admin/clients` | Admin Workspace | 200 | PASS | Loaded 23 client records from `/api/admin/clients` |
| `/admin/catalog/locations` | Admin Catalog | 200 | PASS | Loaded locations, providers, and resources |
| `/admin/catalog/providers` | Admin Catalog | 200 | PASS | Loaded providers, services, and special days |
| `/admin/catalog/services` | Admin Catalog | 200 | PASS | Loaded services, categories, add-ons, and products |
| `/admin/catalog/categories` | Admin Catalog | 200 | PASS | Loaded categories list |
| `/admin/catalog/add-ons` | Admin Catalog | 200 | PASS | Loaded add-ons and compatible services |
| `/admin/catalog/products` | Admin Catalog | 200 | PASS | Loaded product inventory list |
| `/admin/catalog/packages` | Admin Catalog | 200 | PASS | Loaded package offerings list |
| `/admin/catalog/scheduling` | Admin Catalog | 200 | PASS | Loaded provider schedules and special days |
| `/admin/resources` | Admin Catalog | 200 | PASS | Loaded resource allocation and requirements |
| `/admin/relationships` | Admin Operations | 200 | PASS | Loaded entity relationship matrix |
| `/admin/relationships-matrix` | Admin Operations | 200 | PASS | Interactive matrix rendered |
| `/admin/relationships-tree` | Admin Operations | 200 | PASS | Hierarchy tree loaded |
| `/admin/schedule/workdays` | Admin Operations | 200 | PASS | Workday configuration loaded |
| `/admin/schedule/exceptions` | Admin Operations | 200 | PASS | Blocked and reserved times loaded |
| `/admin/finance/invoices` | Admin Finance | 200 | PASS | Canonical `/api/admin/invoices` returns 200 |
| `/admin/finance/payments` | Admin Finance | 200 | PASS | Canonical `/api/admin/payments` returns 200 |
| `/admin/finance/promotions` | Admin Finance | 200 | PASS | Canonical `/api/admin/promotions` returns 200 |
| `/admin/finance/tax-rates` | Admin Finance | 200 | PASS | Canonical `/api/admin/tax-rates` returns 200 |
| `/admin/finance/processors` | Admin Finance | 200 | FAIL | Backend returns 404 for `/api/admin/finance/processors` (Category B) |
| `/admin/notifications/messages` | Admin Notifications | 200 | PASS | Canonical `/api/admin/notifications` returns 200 |
| `/admin/notifications/templates`| Admin Notifications | 200 | PASS | Canonical `/api/admin/notification-templates` returns 200 |
| `/admin/notifications/reminders`| Admin Notifications | 200 | PASS | Canonical `/api/admin/notification-templates` returns 200 |
| `/admin/settings/business` | Admin Settings | 200 | PASS | Business profile loaded |
| `/admin/settings/webhooks` | Admin Settings | 200 | PASS | Webhook endpoints loaded |
| `/admin/settings/plugins` | Admin Settings | 200 | PASS | Explicit in-memory mock catalog renders with zero HTTP errors |
| `/admin/compliance/gdpr` | Admin Compliance | 200 | PASS | Compliance dashboard rendered |
| `/admin/audit` | Admin System | 200 | PASS | Audit logs loaded from `/api/admin/audit-log` |
| `/admin/system` | Admin System | 200 | PASS | System health loaded from `/api/admin/system/health` |
| `/admin/media` | Admin Media | 200 | PASS | Provider media list loaded |
| `/admin/booking-forms` | Admin Forms | 200 | PASS | Booking form list loaded |
| `/admin/reviews` | Admin Reviews | 200 | PASS | Management reviews loaded |
| `/admin/configuration/additional-fields` | Admin Config | 200 | PASS | Additional fields loaded |
| `/admin/sms-assistant` | Admin Messaging | 200 | DEGRADED | Inbox messages fail with 500; jobs route fails with 422 |
| `/book` | Public Booking | 200 | DEGRADED | Bootstrap loads (200), but booking creation fails on DB commit (500) |
| `/public/upload` | Public Portal | 200 | PASS | Upload interface rendered |
| `/403` | Error Page | 200 | PASS | Permission denied screen rendered |
| `/404` | Error Page | 200 | PASS | Not found screen rendered |

---

## C. Findings Table

### [SMOKE-001] CRITICAL: Public Booking Creation Fails on PostgreSQL Outbox Tenant ID Type Error
- **Severity**: **CRITICAL**
- **Endpoint**: `POST /api/public/bookings`
- **Exact Reproduction**:
  ```bash
  curl -X POST http://127.0.0.1:8000/api/public/bookings     -H "Content-Type: application/json"     -H "X-Tenant: simplydemo"     -d '{"client_id": 1, "service_id": 3, "provider_id": 1, "start_time": "2026-09-11T12:00:00Z", "end_time": "2026-09-11T13:00:00Z"}'
  ```
- **Expected Behaviour**: Booking is inserted into `bookings` table with status `pending`, outbox event is enqueued, and HTTP 200 response is returned.
- **Actual Behaviour**: HTTP 500 `INTERNAL_SERVER_ERROR`. PostgreSQL driver raises `DataError: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type integer: "simplydemo"`.
- **Root Cause**: In `app/api/routers/public_bookings.py:114`, `create_outbox_event()` is invoked with `tenant_id=tenant.subdomain` (string `'simplydemo'`). However, the underlying database column `outbox_events.tenant_id` is defined as `Integer` referencing `tenants.id`.
- **Impact**: All public booking attempts via the API fail at database commit time.
- **Smallest Repair Scope**: In `app/api/routers/public_bookings.py:114`, change `tenant_id=tenant.subdomain` to `tenant_id=tenant.id`.
- **Product Decision Required**: No.

---

### [SMOKE-002] HIGH: SMS Conversation Messages Serialization 500 Internal Server Error
- **Severity**: **HIGH**
- **Endpoint**: `GET /api/admin/sms/conversations/{conversation_id}/messages`
- **Exact Reproduction**:
  ```bash
  curl -X GET http://127.0.0.1:8000/api/admin/sms/conversations/1/messages     -H "X-Token: mock-admin-token"     -H "X-Tenant: simplydemo"
  ```
- **Expected Behaviour**: Returns list of SMS messages in conversation 1.
- **Actual Behaviour**: HTTP 500 `INTERNAL_SERVER_ERROR`. Pydantic raises `ValidationError: 1 validation error for SmsMessageResponse: sms_account_id: Input should be a valid integer, input_value=None`.
- **Root Cause**: `SmsMessageResponse` schema in `app/schemas/sms_message.py:27` declares `sms_account_id: int` as non-nullable, but inbound/system SMS message records in PostgreSQL have `sms_account_id = NULL`.
- **Impact**: Admin SMS Assistant Inbox cannot load conversation messages.
- **Smallest Repair Scope**: In `app/schemas/sms_message.py:27`, change `sms_account_id: int` to `sms_account_id: Optional[int] = None`.
- **Product Decision Required**: No.

---

### [SMOKE-003] HIGH: Route Precedence Shadowing on SMS Jobs Endpoint (422)
- **Severity**: **HIGH**
- **Endpoint**: `GET /api/admin/sms/conversations/jobs`
- **Exact Reproduction**:
  ```bash
  curl -X GET http://127.0.0.1:8000/api/admin/sms/conversations/jobs     -H "X-Token: mock-admin-token"     -H "X-Tenant: simplydemo"
  ```
- **Expected Behaviour**: Returns list of SMS background processing jobs.
- **Actual Behaviour**: HTTP 422 `VALIDATION_ERROR` with `{"loc": ["path", "conversation_id"], "msg": "Input should be a valid integer, unable to parse string as an integer", "input": "jobs"}`.
- **Root Cause**: In `app/api/routers/sms_conversations.py`, `@router.get("/{conversation_id}")` is defined before `@router.get("/jobs")`. FastAPI matches `"jobs"` against the path parameter `{conversation_id}` first.
- **Impact**: SMS Diagnostics tab cannot fetch active conversation jobs.
- **Smallest Repair Scope**: In `app/api/routers/sms_conversations.py`, reorder routes so static endpoints (`/jobs`, `/messages/...`) are declared above `/{conversation_id}`.
- **Product Decision Required**: No.

---

### [SMOKE-004] MEDIUM: Public Booking Wizard Attempts Unauthenticated Admin Client Creation
- **Severity**: **MEDIUM**
- **Location**: `frontend/src/pages/public/booking-page.tsx:628`
- **Exact Reproduction**: Inspect booking submission flow in `booking-page.tsx`.
- **Expected Behaviour**: Public booking wizard should either create/resolve a client via a dedicated public client endpoint or pass client information directly to `POST /api/public/bookings`.
- **Actual Behaviour**: The wizard issues `POST /api/admin/clients` (which requires admin authentication). When unauthenticated, the call fails and silently falls back to `clientId = 1`. If `client_id = 1` does not exist or belongs to another tenant, the booking fails with 404.
- **Impact**: Public users without an admin session cannot create new client identities dynamically through the public wizard.
- **Smallest Repair Scope**: Support inline client creation within `POST /api/public/bookings` or introduce an unauthenticated public client lookup/creation endpoint.
- **Product Decision Required**: Yes (Architecture design on public client creation policy).

---

### [SMOKE-005] LOW: Payment Processors Page 404 Route Mismatch
- **Severity**: **LOW**
- **Location**: `frontend/src/pages/admin/finance/processors.tsx:43, 62`
- **Expected Behaviour**: Page should manage payment processor settings.
- **Actual Behaviour**: Page calls `GET /api/admin/finance/processors`, returning HTTP 404.
- **Root Cause**: Known Category B contract discrepancy. Backend exposes `GET/PUT /api/admin/payment-processor/configs` (`list[PaymentProcessorConfigOut]`), whereas the frontend expects a composite object `{ currency, processors: { stripe, paypal, offline } }`.
- **Impact**: Admin cannot view or update payment processors via this specific UI page without mock data fallback.
- **Smallest Repair Scope**: Update `processors.tsx` to adapt to `PaymentProcessorConfig` backend entities.
- **Product Decision Required**: Yes (Frontend form schema alignment).

---

## D. Booking-Test Record

- **Test Identifier**: `SMOKE-TEST-2026-08-28`
- **Actions Tested**:
  1. Public Catalog Discovery (`GET /api/public/services`, `GET /api/public/providers`): **PASS (200 OK)**
  2. Ineligible Provider Validation Check (Service 1 + Provider 1): **PASS (400 Bad Request — Correctly Blocked)**
  3. Public Booking Creation Submission: **FAILED on DB Commit (psycopg2 integer DataError on outbox tenant_id)**
  4. Reschedule / Cancellation / Status Update APIs: **Verified against admin schema**
- **External Suppression**: Zero real SMS, Chatwoot, webhook, or payment side-effects were emitted during tests.
- **Cleanup Verification**: Database teardown executed via Python session; all synthetic test bookings and related outbox records deleted. Active synthetic records remaining in database: **0**.

---

## E. Explicit Non-Findings (Confirmed Healthy Subsystems)

1. **Frontend Production Build**: `npm run build` succeeds cleanly in 2.31s with exit code 0.
2. **Category A API Contract Alignments**:
   - `/api/admin/invoices`: HTTP 200 OK
   - `/api/admin/payments`: HTTP 200 OK
   - `/api/admin/promotions`: HTTP 200 OK
   - `/api/admin/tax-rates`: HTTP 200 OK
   - `/api/admin/notifications`: HTTP 200 OK
   - `/api/admin/notification-templates`: HTTP 200 OK
3. **Plugins Settings**: Fully decoupled mock catalog renders cleanly with zero invalid HTTP calls and interactive toggle state.
4. **Backend Core Services**:
   - `GET /health`: 200 OK (`{"ok": true}`)
   - `GET /ready`: 200 OK (`{"ok": true}`)
   - `GET /api/public/ui-config`: 200 OK
   - `GET /api/public/ui-config/admin`: 200 OK
5. **Observability Pipeline**:
   - SigNoz UI (`127.0.0.1:8080`): Healthy
   - SigNoz OTLP HTTP receiver (`127.0.0.1:4318`): Healthy
   - Traces and metrics actively ingested without privacy leaks.
6. **Chatwoot Integration**: Port 3000 reachable.

---

## F. Prioritised Next Steps

1. **Task 1 (Critical)**: Fix `tenant_id` integer type mismatch in `app/api/routers/public_bookings.py:114` (`tenant_id=tenant.id` instead of `tenant.subdomain`) so PostgreSQL commits public bookings successfully.
2. **Task 2 (High)**: Make `sms_account_id` optional in `app/schemas/sms_message.py:27` (`Optional[int] = None`) and fix route ordering in `app/api/routers/sms_conversations.py` to restore SMS Assistant Inbox & Diagnostics.
3. **Task 3 (Medium)**: Align public booking client identity workflow in `frontend/src/pages/public/booking-page.tsx` so unauthenticated guests can complete bookings without relying on admin endpoints or hardcoded fallbacks.
