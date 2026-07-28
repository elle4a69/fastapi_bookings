# Configurable Booking Forms — Widget and Frontend Handoff

## Contract authority

The running OpenAPI document and `openapi.json` define wire shapes. `contracts/types.ts` and `contracts/client.ts` are generated/compiled from that document. The JSON contracts describe behavior that OpenAPI cannot express, especially fixed-point inference and universal-default relationships.

## Authentication and startup

The widget obtains the existing tenant public token, then sends `X-Tenant` and `X-Token` on every request. Start with `GET /api/public/booking-forms/{slug}`. Do not load the deprecated public entity lists for a new widget.

The bootstrap response contains the form, resolved context, resolution sources, visible modules, options, and warnings. Render only `visible_modules`, in the returned order. `client` is always last.

## Selection loop

After a customer changes location, category, service, or provider, send the current IDs to `POST /api/public/booking-forms/{slug}/resolve`. Replace local options and visible steps with the response; do not duplicate relationship logic in TypeScript.

Resolution sources are `predefined`, `customer_selected`, `inferred`, `automatic`, `unresolved`, and `disabled`. Only unresolved modules are interactive. Automatic providers are deliberately hidden. Optional providers include an option whose ID is `null` and label is “Anyone available.”

## Availability and booking

Once service and all required disabled modules resolve, call `POST /api/public/booking-forms/{slug}/availability` with selections and an ISO date window. Render returned slots. In automatic/Anyone mode the backend chooses the least-loaded compatible provider, with provider ID as a stable tie-breaker.

Create the request with `POST /api/public/booking-forms/{slug}/bookings`. Send the chosen time range, client ID, and current selections. The server repeats resolution and availability checks transactionally. A `409` means the slot is stale and availability must be refreshed. Successful public bookings remain `pending` until confirmed by an administrator/provider.

## Errors and warnings

- `401`: missing, invalid, or wrong-tenant token.
- `404`: inactive/missing form or tenant-owned entity.
- `409`: duplicate form slug or stale booking slot.
- `422`: invalid configuration, incompatible selections, unresolved required data, or invalid date window.

Warnings are preview/resolution guidance and do not replace HTTP errors. Admin preview returns the same structured state plus embed metadata.

## Embed work boundary

The backend returns a script URL, slug, tenant, appearance/settings, and generated embed snippet. The referenced widget runtime is intentionally not implemented in this delivery. A widget agent should build that runtime against the narrow API above and use `contracts/client.ts` rather than the legacy endpoints.

## Representative flows

- No presets: render unresolved location/category/service/provider followed by time and client.
- Location preset: location is hidden and all later options are constrained.
- Service preset with one compatible category/location/provider: render only time and client.
- Required provider with multiple candidates: render provider.
- Optional provider: render provider with Anyone available.
- Automatic provider: hide provider and let availability/booking assign it.
