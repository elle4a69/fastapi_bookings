# FastAPI Bookings — Front-End Contract Index

This directory is the front-end contract layer for the booking application. It is intended to be read before building the public booking portal or admin dashboard.

## Source of truth order

1. `contracts/route-manifest.json` — canonical endpoint names and paths.
2. `contracts/data-models.contract.json` — shared models, enums, and response envelope rules.
3. Feature contracts:
   - `auth.contract.json`
   - `public-booking.contract.json`
   - `admin-dashboard.contract.json`
   - `modules-ui.contract.json`
   - `booking-flow.contract.json`
   - `errors.contract.json`
4. Running backend OpenAPI:
   - `/docs`
   - `/openapi.json`

If the contracts and OpenAPI disagree, prefer the running backend, then update the contract file.

## Important front-end rules

Public booking requests create `pending` bookings. The user/customer is not guaranteed a confirmed appointment until an admin or provider confirms the booking.

The public booking flow should show:

> Your booking request has been received and is awaiting confirmation.

The admin dashboard should show pending bookings prominently and expose approve/reject actions:

- Approve: `POST /api/admin/bookings/{booking_id}/confirm`
- Reject/cancel: `POST /api/admin/bookings/{booking_id}/cancel`

## Module-aware UI

The UI must call:

- Public: `GET /api/public/ui-config`
- Admin: `GET /api/public/ui-config/admin`

Use the returned module flags to decide whether to show locations, categories, resources, products, add-ons, packages, and waitlist UI.

## Holds

Use holds when the customer has selected a slot but still needs to complete details.

Recommended flow:

1. `POST /api/public/holds`
2. collect customer details
3. `POST /api/public/holds/{hold_id}/confirm`

If the hold had no `client_id`, the confirmation request must include `client_details`.

## Flexible booking entry points

The public UI may start from:

- location
- provider
- category
- service
- date/time

Regardless of entry point, final booking creation requires:

- `client_id`
- `provider_id`
- `service_id`
- `start_time`
- `end_time`

`location_id` is optional.

## Known backend limitations to design around

- Recurring bookings are intentionally excluded.
- Automatic waitlist promotion is intentionally not active.
- Packages are admin-manageable, but package purchase/scheduling flow is not currently part of public booking.
- Payments and notifications are record-management endpoints, not real external integrations yet.
