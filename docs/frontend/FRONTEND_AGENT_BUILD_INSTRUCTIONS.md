# Front-End Agent Build Instructions

You are building the front end for a FastAPI booking backend. Build against the contract files in `contracts/` and verify route behavior against `/docs` or `/openapi.json` when the backend is running.

## Applications to build

Build two front-end areas:

1. **Public customer booking portal**
2. **Admin/staff booking dashboard**

## Public booking portal

### Required pages

1. Public booking landing/start page
2. Service/category/location/provider selection flow
3. Availability search page
4. Customer details form
5. Booking review page
6. Booking request submitted page
7. Optional waitlist page

### Required behavior

- Load module config first: `GET /api/public/ui-config`.
- Load bootstrap data: `GET /api/public/bootstrap`.
- Hide disabled modules.
- Allow the booking flow to start from location, provider, category, service, or date/time.
- Use `POST /api/public/search-availability` for flexible availability search.
- Use holds when a customer selects a slot and then fills in details.
- Confirming a hold or creating a public booking creates a booking with status `pending`.
- Show clear language that the request is awaiting approval.

### Recommended slot selection flow

```text
public auth -> ui config -> bootstrap -> search availability -> create hold -> client details -> confirm hold -> pending confirmation screen
```

## Admin dashboard

### Required pages

1. Login
2. Dashboard overview
3. Pending booking approvals
4. Calendar/list bookings
5. Services
6. Providers
7. Clients
8. Locations
9. Categories
10. Resources
11. Add-ons
12. Products
13. Packages
14. Payments
15. Notifications
16. Audit log / diagnostics

### Required behavior

- Admin auth uses `POST /api/admin/auth`.
- Include `X-Token` on protected admin requests.
- Use `/api/admin/dashboard/bootstrap` to load dashboard data.
- Show pending bookings as the top operational queue.
- Confirm booking with `POST /api/admin/bookings/{booking_id}/confirm`.
- Cancel/reject booking with `POST /api/admin/bookings/{booking_id}/cancel`.
- Prefer action endpoints over direct status mutation.

## Error handling

Normalize both response types:

```json
{ "ok": false, "error": { "code": "string", "message": "string" } }
```

and FastAPI native errors:

```json
{ "detail": "string" }
```

into a single internal front-end error shape:

```ts
type UiError = {
  code: string;
  message: string;
  field?: string | null;
  details?: unknown;
};
```

## TypeScript SDK recommendation

Generate types from `/openapi.json` when backend is running, then layer named methods from `contracts/route-manifest.json`.

Suggested front-end modules:

```text
src/api/authApi.ts
src/api/publicBookingApi.ts
src/api/adminBookingApi.ts
src/api/servicesApi.ts
src/api/providersApi.ts
src/api/resourcesApi.ts
src/api/catalogApi.ts
src/api/clientsApi.ts
src/api/errors.ts
src/contracts/routes.ts
```

## Build order

1. API client and error normalization
2. Auth screens
3. Public bootstrap and module-aware UI
4. Public availability search
5. Holds + booking submission
6. Admin dashboard bootstrap
7. Pending approval queue
8. Admin CRUD screens
9. Calendar/list booking management
10. Polish, empty states, loading states, validation
