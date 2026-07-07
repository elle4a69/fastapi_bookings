# Admin Dashboard Flow

This document describes how the admin dashboard retrieves data and
interacts with the API.

1. **Authentication:** An admin user logs in via `POST /api/admin/auth` and
   stores the returned access token. All subsequent requests must
   include this token in the `X-Token` header.
2. **Bootstrap:** When the dashboard loads, call
   `GET /api/admin/dashboard/bootstrap` to fetch an aggregated view of
   today’s bookings, upcoming bookings, pending bookings, providers,
   services and summary counts. This reduces the number of API calls
   required to render the initial view.
3. **Navigation:** Use the route manifest (`contracts/route-manifest.json`) to
   locate endpoints for managing services, providers, clients,
   locations, bookings, payments, notifications and audit logs.
4. **Pagination and filtering:** List endpoints accept `page`,
   `page_size` and additional filters via query parameters. Always
   paginate results to improve performance.
5. **State transitions:** Booking status changes are performed via
   dedicated endpoints such as `POST /api/admin/bookings/{id}/confirm`,
   `cancel`, `complete`, `noshow` and `reschedule`. These endpoints
   enforce the booking state machine rules.