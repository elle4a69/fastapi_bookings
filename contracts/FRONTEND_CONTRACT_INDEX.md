# FastAPI Bookings — Front-End Contract Index

This directory is the front-end contract layer for the booking application. It is intended to be read before building the public booking portal or admin dashboard.

## Source of truth order

1. Running backend OpenAPI and committed `openapi.json` — canonical wire shapes.
2. `contracts/route-manifest.json` — canonical logical endpoint names and paths.
3. `contracts/data-models.contract.json` and feature contracts — behavioral rules.
3. Feature contracts:
   - `auth.contract.json`
   - `public-booking.contract.json`
   - `admin-dashboard.contract.json`
   - `modules-ui.contract.json`
   - `booking-flow.contract.json`
   - `errors.contract.json`
4. Generated TypeScript: `contracts/types.ts` and `contracts/client.ts`.

If a handwritten contract and OpenAPI disagree about a wire shape, OpenAPI wins and the handwritten contract must be updated.

New booking widgets must begin with `configurable-booking-forms.contract.json` and `docs/CONFIGURABLE_BOOKING_FORMS_WIDGET_HANDOFF.md`. The static UI config and general public entity lists are deprecated for new integrations.

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
