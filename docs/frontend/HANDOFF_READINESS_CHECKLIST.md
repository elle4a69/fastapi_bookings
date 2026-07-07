# Handoff Readiness Checklist

Use this checklist before the front-end agent starts.

## Backend status

- The front-end contracts are complete under `contracts/`.
- The public booking endpoint is exposed as `POST /api/public/bookings`.
- Public bookings are created as `pending`.
- Admin/provider approval is done with `POST /api/admin/bookings/{booking_id}/confirm`.
- Rejection/cancellation is done with `POST /api/admin/bookings/{booking_id}/cancel`.
- Recurring booking series are intentionally excluded.
- Automatic waitlist promotion is intentionally excluded.
- Payments and notifications are CRUD-style records only; they are not external gateway integrations yet.

## Front-end first calls

1. `POST /api/public/auth/token`
2. `GET /api/public/ui-config`
3. `GET /api/public/bootstrap`
4. `POST /api/public/search-availability`
5. `POST /api/public/holds`
6. `POST /api/public/holds/{hold_id}/confirm`

## Admin first calls

1. `POST /api/admin/auth`
2. `GET /api/admin/dashboard/bootstrap`
3. `GET /api/admin/bookings`
4. `POST /api/admin/bookings/{booking_id}/confirm`
5. `POST /api/admin/bookings/{booking_id}/cancel`

## UI rules

- Hide modules that are disabled by UI config.
- Do not assume a public booking is confirmed immediately.
- Use the backend response as source of truth for availability and booking status.
- Normalize both structured error envelopes and FastAPI `{ "detail": "..." }` errors.
