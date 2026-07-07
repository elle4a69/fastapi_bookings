# Front-End Agent Handoff Instructions

## Purpose

Build a front end for the local FastAPI Bookings backend. The product requires two main UI surfaces:

1. **Admin / staff booking dashboard**
2. **Public customer self-booking portal**

The backend is intended to be self-contained and local. Do not call SimplyBook APIs from the front end. Use only this FastAPI backend.

---

## Current Contract Layer Status

The backend already includes a contract and documentation layer:

```text
contracts/
  admin-dashboard.contract.json
  auth.contract.json
  booking-flow.contract.json
  errors.contract.json
  public-booking.contract.json
  route-manifest.json

docs/frontend/
  admin-dashboard-flow.md
  auth-flow.md
  booking-state-machine.md
  errors.md
  public-booking-flow.md
  FRONTEND_AGENT_HANDOFF.md
```

Treat these files as the starting contract layer, but do **not** treat them as exhaustive. The source of truth should be:

1. The running backend Swagger docs: `GET /docs`
2. The generated OpenAPI schema: `GET /openapi.json`
3. The actual router files under `app/api/routers/`
4. The contract files under `contracts/`

The current contracts cover the core flows. They do not yet fully document every extended module such as resources, add-ons, products, packages, holds and waitlist behaviour.

---

## Important Implementation Rule

Do not invent backend behaviour. When the front end needs something that is not in the contract or OpenAPI schema, flag it as a backend contract gap instead of guessing.

Use a small typed API client layer rather than scattering raw `fetch()` calls across components.

Recommended structure:

```text
src/
  api/
    client.ts
    authApi.ts
    publicBookingApi.ts
    adminBookingApi.ts
    catalogApi.ts
    resourceApi.ts
  features/
    public-booking/
    admin-dashboard/
    clients/
    services/
    providers/
    resources/
  types/
    api.ts
```

---

## Authentication

### Admin login

Endpoint:

```http
POST /api/admin/auth
```

Payload:

```json
{
  "company": "simplydemo",
  "login": "admin",
  "password": "admin123"
}
```

Response shape:

```json
{
  "ok": true,
  "data": {
    "access_token": "...",
    "token_type": "bearer"
  }
}
```

Store the returned token and send it on protected admin requests:

```http
X-Token: <access_token>
```

### Public token

Endpoint:

```http
POST /api/public/auth/token
```

Payload:

```json
{
  "company": "simplydemo",
  "key": "local-public-key-change-me"
}
```

Send the returned token on public protected requests using the same `X-Token` header.

---

## Response Envelope

Successful responses generally follow this pattern:

```json
{
  "ok": true,
  "data": {},
  "meta": {}
}
```

List responses usually include `meta`:

```json
{
  "ok": true,
  "data": [],
  "meta": {
    "page": 1,
    "page_size": 25,
    "total": 100
  }
}
```

Errors may currently come from standard FastAPI `HTTPException` responses. The intended front-end-facing error contract is:

```json
{
  "ok": false,
  "error": {
    "code": "BOOKING_SLOT_UNAVAILABLE",
    "message": "That time slot is no longer available.",
    "field": "start_time",
    "details": null
  }
}
```

The front end should support both until the backend error middleware is fully standardised:

```ts
function getErrorMessage(error: unknown): string {
  // Prefer error.error.message when present.
  // Fall back to error.detail from FastAPI.
  // Fall back to a generic message.
}
```

---

## Public Booking Portal Flow

The public booking flow should support multiple entry points:

- location-first
- provider-first
- category-first
- service-first
- date/time-first

The safest first front-end implementation should use **service-first** with optional filters for location/provider/category/date.

### Step 1: Get public token

Call:

```http
POST /api/public/auth/token
```

### Step 2: Bootstrap public data

Call:

```http
GET /api/public/bootstrap
X-Token: <public-token>
```

Use this to initialise:

- services
- providers
- locations
- categories if returned
- booking rules
- timezone

### Step 3: Search availability

Preferred flexible endpoint:

```http
POST /api/public/search-availability
```

Example payload:

```json
{
  "location_id": null,
  "provider_id": null,
  "category_id": null,
  "service_id": 1,
  "desired_time": "afternoon",
  "date_from": "2026-07-10T00:00:00",
  "date_to": "2026-07-17T23:59:59"
}
```

Response:

```json
{
  "ok": true,
  "data": [
    {
      "start_time": "2026-07-10T10:00:00",
      "end_time": "2026-07-10T10:30:00",
      "provider": {
        "id": 1,
        "name": "Demo Provider"
      },
      "resources": []
    }
  ],
  "meta": {
    "count": 1
  }
}
```

### Step 4: Hold selected slot

Recommended, because it prevents a customer from losing a selected slot while filling out the form.

Call:

```http
POST /api/public/holds
```

Payload:

```json
{
  "service_id": 1,
  "provider_id": 1,
  "location_id": null,
  "client_id": null,
  "start_time": "2026-07-10T10:00:00",
  "end_time": "2026-07-10T10:30:00",
  "expires_at": "2026-07-10T09:55:00"
}
```

The hold confirmation endpoint can create a client from `client_details` if the hold has no `client_id`.

### Step 5: Confirm hold into booking

Call:

```http
POST /api/public/holds/{hold_id}/confirm
```

Payload:

```json
{
  "hold_id": 1,
  "client_details": {
    "name": "Mario Rossi",
    "email": "mario@example.com",
    "phone": "+61400000000"
  }
}
```

Expected result:

```json
{
  "ok": true,
  "data": {
    "id": 123,
    "client_id": 4,
    "provider_id": 1,
    "service_id": 1,
    "location_id": null,
    "start_time": "2026-07-10T10:00:00",
    "end_time": "2026-07-10T10:30:00",
    "status": "pending"
  }
}
```

### Step 6: Show pending approval

Public bookings should display as **pending**, not final confirmed bookings, unless the backend later enables auto-confirmation.

Use wording like:

```text
Your booking request has been received and is awaiting approval.
```

Do not show “confirmed” unless booking status is actually `confirmed`.

---

## Provider Approval Workflow

The admin dashboard must include a pending bookings queue.

### Admin sees pending bookings

Call:

```http
GET /api/admin/bookings?status_filter=pending
X-Token: <admin-token>
```

Or use:

```http
GET /api/admin/dashboard/bootstrap
```

### Admin approves booking

Call:

```http
POST /api/admin/bookings/{booking_id}/confirm
X-Token: <admin-token>
```

### Admin rejects/cancels booking

Call:

```http
POST /api/admin/bookings/{booking_id}/cancel
X-Token: <admin-token>
```

### Admin completes booking

Call:

```http
POST /api/admin/bookings/{booking_id}/complete
X-Token: <admin-token>
```

### Admin marks no-show

Call:

```http
POST /api/admin/bookings/{booking_id}/noshow
X-Token: <admin-token>
```

### Admin reschedules booking

Call:

```http
POST /api/admin/bookings/{booking_id}/reschedule?new_start=2026-07-10T11:00:00&new_end=2026-07-10T11:30:00
X-Token: <admin-token>
```

The UI should prevent invalid transitions according to the state machine:

```text
pending -> confirmed | cancelled | rescheduled
confirmed -> cancelled | completed | no_show | rescheduled
rescheduled -> confirmed | cancelled
cancelled/completed/no_show -> final
```

---

## Admin Dashboard Minimum Screens

Build these first:

1. **Login**
2. **Dashboard summary**
3. **Pending booking approvals**
4. **Calendar / booking list**
5. **Services**
6. **Providers**
7. **Clients**
8. **Locations**
9. **Resources**
10. **Categories**
11. **Add-ons**
12. **Products**
13. **Audit log / diagnostics**

Use the admin dashboard bootstrap endpoint first, then add list/detail screens as required.

---

## Module Flags and Optional Features

The backend has a UI config endpoint:

```http
GET /api/public/ui-config
```

and an admin variant:

```http
GET /api/public/ui-config/admin
```

Use these flags to hide optional modules:

- locations
- categories
- resources
- products
- add_ons
- audit
- diagnostics
- export
- backup

If a module is disabled, hide the navigation item and do not require it in booking flow.

---

## Resources / Rooms Rule

Some services require resources such as rooms, equipment, or special locations.

The backend models this with:

- `Resource`
- `ServiceResourceRequirement`
- `BookingResourceAllocation`

The front end should not allocate resources manually. It should display available slots returned by `/api/public/search-availability` and allow the backend to allocate resources when the booking is created or a hold is confirmed.

Important scenario:

```text
3 providers are available.
Only 2 rooms are available.
Only 2 simultaneous bookings should be possible.
```

The UI must trust the backend if it rejects a slot because of resource conflict.

---

## Catalog Management

The admin catalog should support:

- services
- providers
- provider-service eligibility
- locations
- categories
- resources
- service resource requirements
- service add-ons
- products
- packages if retained

Current contracts do not fully document all catalog endpoints. Use Swagger/OpenAPI for exact request and response bodies.

---

## Known Backend Contract Gaps

These are known issues or gaps the front-end agent should not paper over:

1. **Direct public booking requires `client_id`**. Prefer the hold-confirmation flow, which can create a client from `client_details`.
2. **Error envelope is intended but not fully enforced globally**. Support FastAPI `detail` errors as fallback.
3. **Recurring booking series is deliberately not exposed as a finished feature.** Do not build recurring booking UI unless backend support is explicitly completed.
4. **Automatic waitlist promotion is deliberately not active.** Waitlist can collect requests, but it should not be assumed to auto-book clients.
5. **Package booking workflow is not integrated into public booking yet.** Admin package CRUD may exist, but do not build a package booking flow until backend confirms the package-to-booking behaviour.
6. **OpenAPI should be regenerated from the running backend** before generating TypeScript types.

---

## Front-End Agent Build Priorities

Build in this order:

1. API client with token handling and error normalisation
2. Admin login
3. Public token flow
4. Public bootstrap screen
5. Service-first booking flow
6. Availability search
7. Hold creation
8. Hold confirmation with client details
9. Pending approval confirmation screen
10. Admin pending approvals queue
11. Admin booking confirm/cancel actions
12. Services/providers/clients CRUD
13. Resources and service-resource requirements
14. Categories/add-ons/products
15. Diagnostics and audit screens

Do not start with a complex calendar. Build list-based booking management first, then add calendar views.

---

## Suggested TypeScript API Client Contract

Use this shape:

```ts
export type ApiSuccess<T> = {
  ok: true;
  data: T;
  meta?: Record<string, unknown>;
};

export type ApiError = {
  ok: false;
  error: {
    code?: string;
    message: string;
    field?: string | null;
    details?: Record<string, unknown> | null;
  };
};

export type ApiResponse<T> = ApiSuccess<T> | ApiError;
```

Add an adapter for raw FastAPI errors:

```ts
export function normaliseApiError(raw: any): ApiError {
  if (raw?.ok === false && raw?.error) return raw;
  if (raw?.detail) {
    return {
      ok: false,
      error: {
        message: typeof raw.detail === 'string' ? raw.detail : 'Request failed',
        details: typeof raw.detail === 'object' ? raw.detail : null,
      },
    };
  }
  return {
    ok: false,
    error: {
      message: 'Request failed',
      details: null,
    },
  };
}
```

---

## Final Instruction to Front-End Agent

Build against the backend as a contract-first client. Do not assume any feature exists unless it appears in `/openapi.json`, `contracts/`, or the router files.

For the first usable release, focus on:

- customer can request a booking
- booking is pending approval
- admin can approve or cancel it
- resources are respected by the backend
- services/providers/locations/resources can be managed

That will produce a stable front-end foundation without overbuilding unfinished backend modules.
