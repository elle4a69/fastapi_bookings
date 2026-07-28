# FastAPI Bookings Frontend — Main Context Document v2

Status: **Corrected implementation brief — backend-derived**  
Generated from the current working tree.  
OpenAPI SHA-256: `B1CD8B1E29C3547FE0E82F0CD18501AB598B76B7DCA5FB7B4CF0FC747C53D2B7`  
Route manifest SHA-256: `A5041A652775D68DA5E755B22EE4015C18C9E89F1E94FAD593B4E8ED122CC25E`  

## Release-readiness summary

- OpenAPI inventory: **246 operations / 170 paths / 229 schemas**.
- SQLAlchemy inventory: **55 tables/resources**.
- Operation ledger: **246 unique method/path rows**, zero missing and zero duplicates after validation.
- Classifications: **administrative or system-only: 4**, **deprecated: 6**, **directly represented: 216**, **indirectly used by another workflow: 9**, **intentionally excluded: 11**.
- Deprecated operations: **6**; none may be consumed by new UI code.
- Critical backend security gap: **0 non-login `/api/admin` operations do not declare `X-Token` in live OpenAPI**. Production release is blocked until each is guarded or explicitly reclassified by the backend owner.
- Public-token release gate: `PUBLIC_API_KEY` is treated as secret; production requires a same-origin BFF/server exchange or a backend replacement explicitly safe for unauthenticated browser bootstrap.
- This document contains no handwritten wire examples. Request and response contracts are referenced by canonical OpenAPI schema names.

## 1. Product overview

FastAPI Bookings is a multi-tenant booking, scheduling, checkout, and operations platform. The frontend must provide a public booking surface, client self-service, and an owner/admin workspace while remaining contract-driven against the current FastAPI application.

The existing `mapbox/` application is migration evidence only. It uses deprecated endpoints, handwritten API types, unsupported `X-Client-Token`, and persistent bearer tokens. The v2 target is a new production architecture rather than a declaration that the prototype is complete.

**Primary outcome:** a frontend team can implement every approved screen without guessing endpoint shapes, tenant rules, authentication, state transitions, or evidence sources.

## 2. Problem statement

The backend exposes a broad and changing API, while the existing frontend covers only a subset and contains contract mismatches. Ad hoc implementation would create broken payloads, insecure tenant boundaries, false role assumptions, deprecated dependencies, and untestable coverage claims.

The solution is an OpenAPI-generated integration layer plus an exact screen/operation/resource register. Backend contradictions remain visible as release gates rather than being converted into frontend assumptions.

## 3. Goals and success metrics

### Goals

- Deliver public booking, client, and owner/admin workflows represented by non-deprecated backend capabilities.
- Generate API types and client functions from the hashed OpenAPI document.
- Prevent cross-tenant cache, token, URL, and state leakage.
- Make backend gaps visible before implementation or release.

### Initial measurable targets

| Area | Target | Window and measurement |
| --- | --- | --- |
| Tenant activation | ≥95% of valid tenant entries render a booking surface within 10 seconds | Rolling 7 days; tenant-resolution and surface-ready events |
| Booking conversion | ≥60% of sessions viewing a slot reach a recorded outcome within 15 minutes | First 30 production days; funnel events |
| Admin task success | ≥95% of supported mutations avoid unhandled frontend failure | Rolling 30 days; mutation telemetry |
| Performance | p75 mobile LCP ≤2.5s, INP ≤200ms, CLS ≤0.1 | Rolling 28-day field data |
| Reliability | Uncaught-error sessions <1%; non-user-caused request failures <2% | Rolling 7 days |
| Accessibility | Zero critical/serious automated violations and 100% keyboard completion of critical flows | Every release |
| Contract quality | 246/246 operations classified; 100% consumed operations generated and contract-tested | Every CI run |
| Retention | ≥50% of activated tenant admins complete an action in weeks 2, 3 and 4 | First 90 days |

## 4. Target users and roles

| User | V2 treatment | Proven authority |
| --- | --- | --- |
| Public visitor | Discovery and published booking flows | Public endpoints after tenant/public-token bootstrap |
| Client | Own login, registration, profile, terms, consent and booking flows | Client subject supplied through `X-Token` |
| Owner | Full supported admin workspace | Backend `get_current_admin` accepts owner |
| Admin | Same V1 authority as owner | Backend `get_current_admin` accepts admin |
| Staff | Route to role-not-enabled screen | Backend admin guard rejects staff |
| Viewer | Route to role-not-enabled screen | Backend admin guard rejects viewer |
| Operator/developer | Health, diagnostics and contract governance | System and CI surfaces |

No UI-only owner/admin distinctions are allowed until the backend enforces them. Staff/viewer remain typed future roles but receive no speculative permissions.

## 5. Confirmed decisions, assumptions, and open gates

### Confirmed decisions

1. `openapi.json` is canonical for wire shapes; generated clients replace handwritten API types.
2. `X-Token` is the only current bearer-token header. `X-Client-Token` is reserved and must not be sent.
3. Bearer tokens are memory-only. Tenant/account/auth changes clear tokens and tenant-scoped query caches.
4. Persistent login is deferred until a BFF/backend supplies Secure HttpOnly SameSite cookies, refresh/revocation semantics and CSRF protection.
5. `PUBLIC_API_KEY` is treated as secret unless the backend/security owner documents otherwise.
6. Deprecated operations are compatibility-only and prohibited in new frontend code.

### Open release gates

- Resolve all 0 unexpectedly unguarded non-login admin operations listed in Section 13.
- Implement server-side public-token exchange or an approved safe backend bootstrap.
- Define legal retention periods; the frontend must not invent them.
- Select an analytics provider and privacy policy before enabling production event collection.
- Add direct contract/integration tests for every operation the frontend consumes.

## 6. Scope and exclusions

### In scope

Public configurable booking forms, availability, holds, waitlist, checkout, client identity and consent; discovery; owner/admin booking operations; catalog, relationships, schedules, resources, finance, notifications, reviews, audit, compliance, integrations and diagnostics represented by approved operations.

### Excluded or deferred

- Six deprecated public list/UI-config operations.
- Unprefixed duplicate notification/template/reminder operations.
- Inbound Stripe webhook and health endpoints as browser screens; they remain system/monitoring capabilities.
- Staff/viewer RBAC activation, persistent login, speculative file imports and any unsupported recurrence UX.
- Any operation that remains unguarded after the backend security audit may not ship merely because the frontend hides it.

## 7. Complete user journeys

### Public booking

1. Resolve tenant from production hostname; development may use the explicit dev route.
2. Obtain a public token through the same-origin BFF.
3. Load the configured booking form/runtime manifest.
4. Resolve service/provider/location relationships and fetch availability.
5. Create a hold when the selected slot needs protection during details/checkout.
6. Identify/create the client, collect additional fields and consent, create quote/invoice/checkout as configured.
7. Submit the booking once with idempotency protection where the backend supports it.
8. Present the actual backend outcome; ordinary public bookings are pending and copy must say “awaiting confirmation.”

### Client self-service

Register or log in, retain the client token in memory, view/update only the current profile, review terms and record consent. Reload ends the session. Password reset is request-only because no completion endpoint exists in the current inventory.

### Owner/admin operations

Authenticate, verify role, enter the tenant-scoped shell, load the dashboard, and navigate to concrete routes in Section 9. Mutations use generated types, disable duplicate submissions, normalize error envelopes and invalidate only tenant-scoped query keys.

### Booking lifecycle

{state_table}

## 8. Core feature specifications

Features are enumerated from OpenAPI tags before UI specification. Operation-level ownership is authoritative in Appendix D.

| Backend tag | Operations | Frontend module | Primary route | Related backend tests |
| --- | --- | --- | --- | --- |
| add-ons | 5 | Catalog / add-ons | /admin/catalog/add-ons | No direct mapping asserted |
| additional-fields | 8 | Additional fields | /admin/configuration/additional-fields | tests/test_booking_policies_remediation.py |
| audit | 2 | Audit | /admin/audit | tests/test_audit_resolution.py |
| auth | 3 | Authentication | /admin/login | tests/test_multi_tenancy.py, tests/test_audit_resolution.py |
| availability | 1 | Public availability | /book/:formSlug | tests/test_scheduling_intervals.py, tests/test_scheduling_constraints.py |
| booking-forms-admin | 11 | Booking-form administration | /admin/booking-forms | tests/test_configurable_booking_forms.py, tests/test_booking_form_contracts.py |
| booking-forms-widget | 6 | Public booking form | /book/:formSlug | tests/test_configurable_booking_forms.py, tests/test_embed_configuration.py |
| bookings | 10 | Booking operations | /admin/bookings | tests/test_booking_policies_remediation.py, tests/test_concurrency.py, tests/test_audit_fixes.py |
| business-profile | 4 | Business profile | /admin/settings/business | No direct mapping asserted |
| calendar-notes | 4 | Calendar | /admin/calendar | No direct mapping asserted |
| categories | 5 | Catalog / categories | /admin/catalog/categories | tests/test_relationships_remediation.py |
| checkout | 22 | Checkout and finance | /admin/finance/invoices | tests/test_booking_policies_remediation.py, tests/test_audit_fixes.py |
| clients | 5 | Client administration | /admin/clients | No direct mapping asserted |
| dashboard | 1 | Dashboard | /admin | No direct mapping asserted |
| devices | 1 | Notification device registration | /admin/notifications/messages | tests/test_phase_5_6_7.py |
| discovery | 3 | Discovery | /discover | No direct mapping asserted |
| forms | 3 | Generated form metadata | /book/:formSlug/details | No direct mapping asserted |
| holds | 3 | Public booking hold | /book/:formSlug/checkout | tests/test_concurrency.py, tests/test_audit_fixes.py |
| location-relationships | 9 | Relationship editor | /admin/relationships | tests/test_relationships_remediation.py |
| locations | 5 | Catalog / locations | /admin/catalog/locations | tests/test_relationships_remediation.py |
| management-reviews | 4 | Management reviews | /admin/reviews | No direct mapping asserted |
| notification-templates | 8 | Notification templates | /admin/notifications/templates | tests/test_notification_configs.py |
| notifications | 6 | Notifications | /admin/notifications/messages | No direct mapping asserted |
| packages | 8 | Catalog / packages | /admin/catalog/packages | No direct mapping asserted |
| payments | 3 | Payments | /admin/finance/payments | No direct mapping asserted |
| products | 6 | Catalog / products | /admin/catalog/products | No direct mapping asserted |
| providers | 5 | Catalog / providers | /admin/catalog/providers | tests/test_relationships_remediation.py |
| public | 5 | Public booking bootstrap | /book/:formSlug | tests/test_public_entities_remediation.py |
| public-bookings | 1 | Public booking | /book/:formSlug/outcome | No direct mapping asserted |
| public-clients | 8 | Client account | /client/profile | tests/test_multi_tenancy.py |
| public-gdpr | 1 | Client consent | /client/terms | No direct mapping asserted |
| public-timeline | 3 | Public availability | /book/:formSlug | tests/test_scheduling_intervals.py, tests/test_scheduling_edge_cases.py |
| relationship-management | 10 | Relationship editor | /admin/relationships | tests/test_relationships_remediation.py |
| reminder-rules | 8 | Reminder rules | /admin/notifications/reminders | tests/test_notification_configs.py |
| resources | 6 | Resources | /admin/resources | No direct mapping asserted |
| schedule | 17 | Schedule | /admin/calendar | No direct mapping asserted |
| search-availability | 1 | Public availability | /book/:formSlug | tests/test_audit_resolution.py, tests/test_security_fuzzing.py |
| series | 3 | Booking series | /admin/bookings | No direct mapping asserted |
| service-relations | 6 | Relationship editor | /admin/relationships | tests/test_relationships_remediation.py |
| services | 5 | Catalog / services | /admin/catalog/services | tests/test_multi_tenancy.py, tests/test_scheduling_constraints.py |
| stripe | 2 | Payment integration | /admin/finance/payments | tests/test_phase_5_6_7.py |
| system | 9 | System and compliance | /admin/system | No direct mapping asserted |
| system-admin | 2 | System maintenance | /admin/system | tests/test_retention_remediation.py |
| ui-config | 2 | Deprecated compatibility | N/A | No direct mapping asserted |
| waitlist | 2 | Public waitlist | /book/:formSlug/outcome | tests/test_concurrency.py, tests/test_scheduling_edge_cases.py |
| webhooks | 6 | Webhooks | /admin/settings/webhooks | No direct mapping asserted |

### Common feature contract

Every directly represented feature must provide initial/background loading, empty, offline/network, normalized 400/401/403/404/409/422/429/500 states, destructive confirmation, duplicate-submit protection, success feedback and targeted TanStack Query invalidation. Exact payloads come from the schema references in Appendix D; teams must not copy illustrative payloads from prose.

## 9. Screen and frontend route inventory

The following is the canonical target route inventory. Production tenant identity comes from hostname/configuration; `/dev/:tenantSlug/...` is development-only. Protected admin routes share an owner/admin layout guard. Client routes use an in-memory client session.

| Surface | Frontend route | Screen | Guard | Backend module |
| --- | --- | --- | --- | --- |
| Public | /discover | Discovery map and accessible list | Public | discovery |
| Public | /book/:formSlug | Tenant booking surface | Public token via BFF | booking-forms-widget |
| Public | /book/:formSlug/details | Dynamic intake and client details | Public token via BFF | additional-fields |
| Public | /book/:formSlug/checkout | Quote, promotion and checkout | Public token via BFF | checkout |
| Public | /book/:formSlug/outcome | Request outcome | Navigation state | public-bookings |
| Public dev-only | /dev/:tenantSlug/book/:formSlug | Explicit tenant override | Development only | tenancy |
| Client | /client/login | Client login | Public token | public-clients |
| Client | /client/register | Client registration | Public token | public-clients |
| Client | /client/password-reset | Password reset request | Public token | public-clients |
| Client | /client/profile | Client profile | Client subject through X-Token | public-clients |
| Client | /client/terms | Terms and consent | Client/public subject | public-gdpr |
| Admin | /admin/login | Administrative login | Credentials exchange | auth |
| Admin | /admin/role-not-enabled | Staff/viewer denial | Authenticated unsupported role | auth |
| Admin | /admin | Operational dashboard | Owner/admin | dashboard |
| Admin | /admin/calendar | Calendar and schedule | Owner/admin | schedule |
| Admin | /admin/bookings | Booking list | Owner/admin | bookings |
| Admin | /admin/bookings/:bookingId | Booking detail and transitions | Owner/admin | bookings |
| Admin | /admin/booking-forms | Booking-form list | Owner/admin | booking-forms-admin |
| Admin | /admin/booking-forms/new | Booking-form creation | Owner/admin | booking-forms-admin |
| Admin | /admin/booking-forms/:formId | Booking-form editor/design/embed | Owner/admin | booking-forms-admin |
| Admin | /admin/catalog/services | Services | Owner/admin | services |
| Admin | /admin/catalog/providers | Providers | Owner/admin | providers |
| Admin | /admin/catalog/locations | Locations | Owner/admin | locations |
| Admin | /admin/catalog/categories | Categories | Owner/admin | categories |
| Admin | /admin/catalog/add-ons | Add-ons | Owner/admin | add-ons |
| Admin | /admin/catalog/products | Products | Owner/admin | products |
| Admin | /admin/catalog/packages | Packages and steps | Owner/admin | packages |
| Admin | /admin/resources | Resources and requirements | Owner/admin | resources |
| Admin | /admin/relationships | Cross-entity relationship editor | Owner/admin | relationship-management |
| Admin | /admin/schedule/workdays | Workdays | Owner/admin | schedule |
| Admin | /admin/schedule/exceptions | Special, blocked and reserved time | Owner/admin | schedule |
| Admin | /admin/clients | Client list | Owner/admin | clients |
| Admin | /admin/clients/:clientId | Client detail and compliance | Owner/admin | clients |
| Admin | /admin/configuration/additional-fields | Additional fields | Owner/admin | additional-fields |
| Admin | /admin/finance/invoices | Invoices | Owner/admin | checkout |
| Admin | /admin/finance/payments | Payments | Owner/admin | payments |
| Admin | /admin/finance/promotions | Promotions | Owner/admin | checkout |
| Admin | /admin/finance/tax-rates | Tax rates | Owner/admin | checkout |
| Admin | /admin/finance/processors | Payment processors | Owner/admin | checkout |
| Admin | /admin/notifications/messages | Notifications | Owner/admin | notifications |
| Admin | /admin/notifications/templates | Notification templates | Owner/admin | notification-templates |
| Admin | /admin/notifications/reminders | Reminder rules | Owner/admin | reminder-rules |
| Admin | /admin/reviews | Management reviews | Owner/admin | management-reviews |
| Admin | /admin/audit | Audit log | Owner/admin | audit |
| Admin | /admin/compliance/gdpr | GDPR consent records | Owner/admin | system |
| Admin | /admin/settings/business | Business profile | Owner/admin | business-profile |
| Admin | /admin/settings/webhooks | Webhooks | Owner/admin | webhooks |
| Admin | /admin/settings/plugins | Plugin states | Owner/admin | system |
| Admin | /admin/system | Diagnostics and maintenance | Owner/admin | system-admin |
| Error | /403 | Permission denied | Any | errors |
| Error | /404 | Not found | Any | errors |
| Error | * | Route fallback | Any | errors |

### Navigation rules

- Unknown routes go to `/404`; permission failures go to `/403` or `/admin/role-not-enabled`.
- Tenant change clears auth state, booking state and all tenant-prefixed query caches before navigation.
- Deep links must reload their own required server state; outcome routes without a public retrieval endpoint must show a safe “outcome unavailable after reload” fallback rather than inventing a fetch.
- Admin list/detail/edit routes preserve filters in query parameters but never tokens or sensitive data.

## 10. Interaction and request-lifecycle rules

1. Use a centralized generated client middleware to attach tenant context and the current in-memory `X-Token`.
2. Normalize the standard `{ok,error}` envelope and legacy FastAPI `detail`/validation envelopes into one typed UI error.
3. Map 422 locations to React Hook Form fields; retain an accessible summary for unmapped errors.
4. A 401 clears the relevant in-memory session and redirects to the appropriate login/bootstrap flow.
5. A 403 preserves safe context and shows permission/role-not-enabled guidance.
6. A 409 retains user input, refetches the conflicted resource/availability and requires explicit retry.
7. A 429 honors `Retry-After` when present; otherwise use bounded backoff and never loop automatically on mutations.
8. Destructive and booking-state mutations are pessimistic by default. Optimistic updates are allowed only for reversible low-risk preferences.
9. Query keys always begin with tenant identity and auth subject class.
10. Public routes are rate-limited; availability requests must debounce/cancel stale requests.

## 11. Content and messaging

- Ordinary public booking: **“Your booking request has been received and is awaiting confirmation.”**
- Conflict: **“That time is no longer available. Choose another time.”**
- Role disabled: **“This account role is not enabled for the administration workspace.”**
- Tenant failure distinguishes missing tenant (400) from unknown tenant (404).
- Never expose stack traces, secrets, raw gateway responses or cross-tenant identifiers.
- Copy is centralized and localization-ready. Date, time, currency and timezone formatting uses tenant configuration and accessible explicit labels.

## 12. Data, resource, relationship, and state model

This register is generated from current SQLAlchemy metadata. “Indirect through parent” requires a query-by-query tenant audit; it is not proof of unsafe behavior or proof of isolation.

| Table/resource | Tenant scope | Foreign keys | Unique constraints | Columns | Evidence |
| --- | --- | --- | --- | --- | --- |
| add_ons | Direct tenant_id | tenant_id → tenants.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR (required); description:VARCHAR; price:NUMERIC(10, 2); duration:INTEGER (required); active:BOOLEAN (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (add_ons) |
| additional_field_responses | Indirect through parent — verify every query | field_id → additional_fields.id; client_id → clients.id; booking_id → bookings.id | — | id:INTEGER (PK, required); field_id:INTEGER (required); client_id:INTEGER; booking_id:INTEGER; value:TEXT; created_at:DATETIME (required) | app/models + SQLAlchemy metadata (additional_field_responses) |
| additional_fields | Direct tenant_id | tenant_id → tenants.id; service_id → services.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); scope:VARCHAR (required); service_id:INTEGER; name:VARCHAR (required); label:VARCHAR (required); field_type:VARCHAR (required); required:BOOLEAN (required); active:BOOLEAN (required); position:INTEGER (required); placeholder:VARCHAR; help_text:TEXT; options_json:TEXT; default_value:TEXT; created_at:DATETIME (required) | app/models + SQLAlchemy metadata (additional_fields) |
| audit_logs | Direct tenant_id | tenant_id → tenants.id; user_id → users.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); user_id:INTEGER; action:VARCHAR (required); target_type:VARCHAR; target_id:INTEGER; details:TEXT; timestamp:DATETIME (required) | app/models + SQLAlchemy metadata (audit_logs) |
| blocked_times | Direct tenant_id | tenant_id → tenants.id; provider_id → providers.id; location_id → locations.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); provider_id:INTEGER; location_id:INTEGER; start_time:DATETIME (required); end_time:DATETIME (required); reason:VARCHAR; active:BOOLEAN (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (blocked_times) |
| booking_events | Indirect through parent — verify every query | booking_id → bookings.id | — | id:INTEGER (PK, required); booking_id:INTEGER (required); type:VARCHAR(18) (required); data:TEXT; created_at:DATETIME (required) | app/models + SQLAlchemy metadata (booking_events) |
| booking_forms | Direct tenant_id | tenant_id → tenants.id | tenant_id,slug | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR (required); slug:VARCHAR (required); description:TEXT; active:BOOLEAN (required); module_order:JSON (required); enabled_modules:JSON (required); predefined_values:JSON (required); provider_selection_mode:VARCHAR (required); clear_session_on_start:BOOLEAN (required); allow_switch_to_ada:BOOLEAN (required); widget_type:VARCHAR (required); appearance:JSON (required); settings:JSON (required); created_at:DATETIME (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (booking_forms) |
| booking_resource_allocations | Indirect through parent — verify every query | booking_id → bookings.id; resource_id → resources.id | — | id:INTEGER (PK, required); booking_id:INTEGER (required); resource_id:INTEGER (required); quantity:INTEGER (required) | app/models + SQLAlchemy metadata (booking_resource_allocations) |
| booking_series | Direct tenant_id | tenant_id → tenants.id; client_id → clients.id; service_id → services.id; provider_id → providers.id; location_id → locations.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR; client_id:INTEGER; service_id:INTEGER (required); provider_id:INTEGER; location_id:INTEGER; recurrence_rule:VARCHAR (required); end_date:DATETIME; created_at:DATETIME (required) | app/models + SQLAlchemy metadata (booking_series) |
| bookings | Direct tenant_id | tenant_id → tenants.id; client_id → clients.id; provider_id → providers.id; service_id → services.id; location_id → locations.id; series_id → booking_series.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); client_id:INTEGER (required); provider_id:INTEGER (required); service_id:INTEGER (required); location_id:INTEGER; series_id:INTEGER; start_time:DATETIME (required); end_time:DATETIME (required); status:VARCHAR(11) (required); notes:TEXT; idempotency_key:VARCHAR (unique); created_at:DATETIME (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (bookings) |
| calendar_notes | Indirect through parent — verify every query | provider_id → providers.id | — | id:INTEGER (PK, required); provider_id:INTEGER; date:DATE (required); start_time:VARCHAR; end_time:VARCHAR; text:TEXT (required); note_type:VARCHAR; is_time_blocked:BOOLEAN (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (calendar_notes) |
| categories | Direct tenant_id | tenant_id → tenants.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR (required); description:VARCHAR; active:BOOLEAN (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (categories) |
| clients | Direct tenant_id | tenant_id → tenants.id; restricted_by_id → users.id; restriction_cleared_by_id → users.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR; email:VARCHAR; phone:VARCHAR; password_hash:VARCHAR; address_line1:VARCHAR; address_line2:VARCHAR; city:VARCHAR; state:VARCHAR; postcode:VARCHAR; country:VARCHAR; timezone:VARCHAR; accepts_marketing:BOOLEAN (required); terms_accepted_at:DATETIME; privacy_accepted_at:DATETIME; notes:TEXT; active:BOOLEAN (required); deleted_at:DATETIME; created_at:DATETIME (required); management_approval_required:BOOLEAN (required); restriction_reason:VARCHAR; restricted_by_id:INTEGER; restricted_at:DATETIME; restriction_cleared_by_id:INTEGER; restriction_cleared_at:DATETIME | app/models + SQLAlchemy metadata (clients) |
| device_tokens | Direct tenant_id | client_id → clients.id; user_id → users.id | token | id:INTEGER (PK, required); tenant_id:VARCHAR; client_id:INTEGER; user_id:INTEGER; token:VARCHAR (required); platform:VARCHAR; device_id:VARCHAR; enabled:BOOLEAN (required); last_seen_at:DATETIME (required); created_at:DATETIME (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (device_tokens) |
| gdpr_consents | Indirect through parent — verify every query | client_id → clients.id | — | id:INTEGER (PK, required); client_id:INTEGER (required); consent_type:VARCHAR (required); is_approved:BOOLEAN (required); ip_address:VARCHAR (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (gdpr_consents) |
| holds | Direct tenant_id | tenant_id → tenants.id; client_id → clients.id; service_id → services.id; provider_id → providers.id; location_id → locations.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); client_id:INTEGER; service_id:INTEGER (required); provider_id:INTEGER; location_id:INTEGER; start_time:DATETIME (required); end_time:DATETIME (required); status:VARCHAR(9) (required); expires_at:DATETIME (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (holds) |
| invoice_lines | Direct tenant_id | tenant_id → tenants.id; invoice_id → invoices.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); invoice_id:INTEGER (required); line_type:VARCHAR (required); item_id:INTEGER; description:VARCHAR (required); quantity:INTEGER (required); unit_price:NUMERIC(10, 2) (required); amount:NUMERIC(10, 2) (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (invoice_lines) |
| invoices | Direct tenant_id | tenant_id → tenants.id; booking_id → bookings.id; client_id → clients.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); booking_id:INTEGER; client_id:INTEGER; currency:VARCHAR (required); subtotal:NUMERIC(10, 2) (required); discount_total:NUMERIC(10, 2) (required); tax_total:NUMERIC(10, 2) (required); tip_total:NUMERIC(10, 2) (required); total:NUMERIC(10, 2) (required); amount_paid:NUMERIC(10, 2) (required); status:VARCHAR (required); promotion_code:VARCHAR; notes:TEXT; idempotency_key:VARCHAR (unique); created_at:DATETIME (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (invoices) |
| location_categories | Direct tenant_id | tenant_id → tenants.id; location_id → locations.id; category_id → categories.id | tenant_id,location_id,category_id | id:INTEGER (PK, required); tenant_id:INTEGER (required); location_id:INTEGER (required); category_id:INTEGER (required) | app/models + SQLAlchemy metadata (location_categories) |
| location_products | Direct tenant_id | tenant_id → tenants.id; location_id → locations.id; product_id → products.id | tenant_id,location_id,product_id | id:INTEGER (PK, required); tenant_id:INTEGER (required); location_id:INTEGER (required); product_id:INTEGER (required) | app/models + SQLAlchemy metadata (location_products) |
| location_providers | Direct tenant_id | tenant_id → tenants.id; location_id → locations.id; provider_id → providers.id | tenant_id,location_id,provider_id | id:INTEGER (PK, required); tenant_id:INTEGER (required); location_id:INTEGER (required); provider_id:INTEGER (required) | app/models + SQLAlchemy metadata (location_providers) |
| location_services | Direct tenant_id | tenant_id → tenants.id; location_id → locations.id; service_id → services.id | tenant_id,location_id,service_id | id:INTEGER (PK, required); tenant_id:INTEGER (required); location_id:INTEGER (required); service_id:INTEGER (required) | app/models + SQLAlchemy metadata (location_services) |
| locations | Direct tenant_id | tenant_id → tenants.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR (required); address:VARCHAR; timezone:VARCHAR | app/models + SQLAlchemy metadata (locations) |
| management_review_requests | Direct tenant_id | tenant_id → tenants.id; client_id → clients.id; service_id → services.id; provider_id → providers.id; location_id → locations.id; resolved_by_id → users.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); client_id:INTEGER (required); service_id:INTEGER; provider_id:INTEGER; location_id:INTEGER; preferred_time:DATETIME; reason:VARCHAR; state:VARCHAR (required); slot_reserved:BOOLEAN (required); payment_taken:BOOLEAN (required); resolution_notes:TEXT; resolved_by_id:INTEGER; resolved_at:DATETIME; created_at:DATETIME (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (management_review_requests) |
| notification_logs | Indirect through parent — verify every query | notification_id → notifications.id; outbox_event_id → outbox_events.id; template_id → notification_templates.id; rule_id → reminder_rules.id; booking_id → bookings.id; client_id → clients.id | — | id:INTEGER (PK, required); notification_id:INTEGER; outbox_event_id:INTEGER; template_id:INTEGER; rule_id:INTEGER; booking_id:INTEGER; client_id:INTEGER; channel:VARCHAR (required); recipient:VARCHAR; subject:VARCHAR; body:TEXT; status:VARCHAR (required); provider:VARCHAR (required); gateway_response:TEXT; created_at:DATETIME (required); updated_at:DATETIME (required); dispatched_at:DATETIME | app/models + SQLAlchemy metadata (notification_logs) |
| notification_preferences | Indirect through parent — verify every query | client_id → clients.id | client_id | id:INTEGER (PK, required); client_id:INTEGER (required); email_enabled:BOOLEAN (required); sms_enabled:BOOLEAN (required); push_enabled:BOOLEAN (required); reminders_enabled:BOOLEAN (required); marketing_enabled:BOOLEAN (required); created_at:DATETIME (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (notification_preferences) |
| notification_templates | Direct tenant_id | tenant_id → tenants.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); code:VARCHAR (required, unique); name:VARCHAR (required); channel:VARCHAR (required); subject:VARCHAR; body:TEXT (required); locale:VARCHAR (required); active:BOOLEAN (required); created_at:DATETIME (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (notification_templates) |
| notifications | Direct tenant_id | tenant_id → tenants.id; booking_id → bookings.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); booking_id:INTEGER; recipient_email:VARCHAR; type:VARCHAR (required); status:VARCHAR (required); content:TEXT; created_at:DATETIME (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (notifications) |
| outbox_events | Direct tenant_id | — | — | id:INTEGER (PK, required); tenant_id:VARCHAR; type:VARCHAR (required); payload:TEXT (required); status:VARCHAR (required); retry_count:INTEGER (required); error_log:TEXT; processed:BOOLEAN (required); created_at:DATETIME (required); processed_at:DATETIME | app/models + SQLAlchemy metadata (outbox_events) |
| package_steps | Indirect through parent — verify every query | package_id → service_packages.id; service_id → services.id | — | id:INTEGER (PK, required); package_id:INTEGER (required); service_id:INTEGER (required); order:INTEGER (required); offset_days:INTEGER (required); price:NUMERIC(10, 2); active:BOOLEAN (required) | app/models + SQLAlchemy metadata (package_steps) |
| payment_processor_configs | Direct tenant_id | tenant_id → tenants.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); provider:VARCHAR (required); enabled:BOOLEAN (required); display_name:VARCHAR; public_key:VARCHAR; config_json:TEXT; created_at:DATETIME (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (payment_processor_configs) |
| payments | Direct tenant_id | tenant_id → tenants.id; booking_id → bookings.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); booking_id:INTEGER (required); amount:NUMERIC(10, 2) (required); currency:VARCHAR (required); status:VARCHAR (required); created_at:DATETIME (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (payments) |
| plugin_states | Direct tenant_id | tenant_id → tenants.id | tenant_id,name | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR (required); is_enabled:BOOLEAN (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (plugin_states) |
| products | Direct tenant_id | tenant_id → tenants.id | tenant_id,sku | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR (required); description:VARCHAR; price:NUMERIC(10, 2) (required); sku:VARCHAR; active:BOOLEAN (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (products) |
| promotion_codes | Direct tenant_id | tenant_id → tenants.id | tenant_id,code | id:INTEGER (PK, required); tenant_id:INTEGER (required); code:VARCHAR (required); description:VARCHAR; discount_type:VARCHAR (required); discount_value:NUMERIC(10, 2) (required); active:BOOLEAN (required); max_redemptions:INTEGER; times_redeemed:INTEGER (required); starts_at:DATETIME; expires_at:DATETIME; created_at:DATETIME (required) | app/models + SQLAlchemy metadata (promotion_codes) |
| provider_categories | Direct tenant_id | tenant_id → tenants.id; provider_id → providers.id; category_id → categories.id | tenant_id,provider_id,category_id | id:INTEGER (PK, required); tenant_id:INTEGER (required); provider_id:INTEGER (required); category_id:INTEGER (required) | app/models + SQLAlchemy metadata (provider_categories) |
| provider_special_days | Direct tenant_id | tenant_id → tenants.id; provider_id → providers.id; location_id → locations.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); provider_id:INTEGER; location_id:INTEGER; date:DATE (required); is_working:BOOLEAN (required); start_time:VARCHAR; end_time:VARCHAR; reason:VARCHAR; created_at:DATETIME (required) | app/models + SQLAlchemy metadata (provider_special_days) |
| provider_workdays | Direct tenant_id | tenant_id → tenants.id; provider_id → providers.id; location_id → locations.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); provider_id:INTEGER; location_id:INTEGER; weekday:INTEGER (required); start_time:VARCHAR; end_time:VARCHAR; is_working:BOOLEAN (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (provider_workdays) |
| providers | Direct tenant_id | tenant_id → tenants.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR (required); email:VARCHAR; phone:VARCHAR; active:BOOLEAN (required); deleted_at:DATETIME; created_at:DATETIME (required); is_visible:BOOLEAN (required); capacity:INTEGER (required); color:VARCHAR; description:TEXT; ignore_company_hours:BOOLEAN (required) | app/models + SQLAlchemy metadata (providers) |
| reminder_rules | Direct tenant_id | tenant_id → tenants.id; template_id → notification_templates.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR (required); event_type:VARCHAR (required); channel:VARCHAR (required); audience:VARCHAR (required); timing:VARCHAR (required); offset_minutes:INTEGER (required); template_id:INTEGER; active:BOOLEAN (required); conditions_json:TEXT; created_at:DATETIME (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (reminder_rules) |
| reserved_times | Direct tenant_id | tenant_id → tenants.id; provider_id → providers.id; service_id → services.id; client_id → clients.id; location_id → locations.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); provider_id:INTEGER; service_id:INTEGER; client_id:INTEGER; location_id:INTEGER; start_time:DATETIME (required); end_time:DATETIME (required); expires_at:DATETIME; status:VARCHAR (required); note:TEXT; created_at:DATETIME (required) | app/models + SQLAlchemy metadata (reserved_times) |
| resources | Direct tenant_id | tenant_id → tenants.id; location_id → locations.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR (required); type:VARCHAR (required); location_id:INTEGER; capacity:INTEGER (required); active:BOOLEAN (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (resources) |
| service_add_ons | Direct tenant_id | tenant_id → tenants.id; service_id → services.id; add_on_id → add_ons.id | tenant_id,service_id,add_on_id | id:INTEGER (PK, required); tenant_id:INTEGER (required); service_id:INTEGER (required); add_on_id:INTEGER (required) | app/models + SQLAlchemy metadata (service_add_ons) |
| service_categories | Direct tenant_id | tenant_id → tenants.id; service_id → services.id; category_id → categories.id | tenant_id,service_id,category_id | id:INTEGER (PK, required); tenant_id:INTEGER (required); service_id:INTEGER (required); category_id:INTEGER (required) | app/models + SQLAlchemy metadata (service_categories) |
| service_packages | Direct tenant_id | tenant_id → tenants.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR (required); description:VARCHAR; price:NUMERIC(10, 2); active:BOOLEAN (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (service_packages) |
| service_products | Direct tenant_id | tenant_id → tenants.id; service_id → services.id; product_id → products.id | tenant_id,service_id,product_id | id:INTEGER (PK, required); tenant_id:INTEGER (required); service_id:INTEGER (required); product_id:INTEGER (required) | app/models + SQLAlchemy metadata (service_products) |
| service_providers | Direct tenant_id | tenant_id → tenants.id; service_id → services.id; provider_id → providers.id | tenant_id,service_id,provider_id | id:INTEGER (PK, required); tenant_id:INTEGER (required); service_id:INTEGER (required); provider_id:INTEGER (required) | app/models + SQLAlchemy metadata (service_providers) |
| service_resource_requirements | Indirect through parent — verify every query | service_id → services.id | — | id:INTEGER (PK, required); service_id:INTEGER (required); resource_type:VARCHAR (required); quantity:INTEGER (required) | app/models + SQLAlchemy metadata (service_resource_requirements) |
| services | Direct tenant_id | tenant_id → tenants.id; tax_rate_id → tax_rates.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR (required); description:VARCHAR; duration:INTEGER (required); price:NUMERIC(10, 2); active:BOOLEAN (required); deleted_at:DATETIME; buffer_before:INTEGER (required); buffer_after:INTEGER (required); fixed_start_times:VARCHAR; is_visible:BOOLEAN (required); deposit_amount:NUMERIC(10, 2) (required); max_advance_days:INTEGER; tax_rate_id:INTEGER; min_group_size:INTEGER (required); max_group_size:INTEGER | app/models + SQLAlchemy metadata (services) |
| tax_rates | Direct tenant_id | tenant_id → tenants.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); name:VARCHAR (required); rate_percent:NUMERIC(10, 2) (required); active:BOOLEAN (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (tax_rates) |
| tenants | No tenant key — global or security gap | — | name | id:INTEGER (PK, required); name:VARCHAR (required, unique); subdomain:VARCHAR (required, unique); created_at:DATETIME (required); timezone:VARCHAR (required); country:VARCHAR; email:VARCHAR; phone:VARCHAR; website:VARCHAR; public_address_visibility:VARCHAR (required); max_advance_days:INTEGER (required); address:VARCHAR; latitude:FLOAT; longitude:FLOAT; logo_url:VARCHAR | app/models + SQLAlchemy metadata (tenants) |
| tips | Direct tenant_id | tenant_id → tenants.id; invoice_id → invoices.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); invoice_id:INTEGER (required); amount:NUMERIC(10, 2) (required); note:TEXT; created_at:DATETIME (required) | app/models + SQLAlchemy metadata (tips) |
| users | Direct tenant_id | tenant_id → tenants.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); login:VARCHAR (required, unique); password_hash:VARCHAR (required); role:VARCHAR (required); created_at:DATETIME (required); updated_at:DATETIME (required) | app/models + SQLAlchemy metadata (users) |
| waitlist_entries | Direct tenant_id | tenant_id → tenants.id; client_id → clients.id; service_id → services.id; provider_id → providers.id; location_id → locations.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); client_id:INTEGER; service_id:INTEGER (required); provider_id:INTEGER; location_id:INTEGER; desired_date_from:DATETIME; desired_date_to:DATETIME; status:VARCHAR(9) (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (waitlist_entries) |
| webhooks | Direct tenant_id | tenant_id → tenants.id | — | id:INTEGER (PK, required); tenant_id:INTEGER (required); event:VARCHAR (required); target_url:VARCHAR (required); secret:VARCHAR; is_active:BOOLEAN (required); created_at:DATETIME (required) | app/models + SQLAlchemy metadata (webhooks) |

### Canonical API schema register

The 188 schema names below are references, not handwritten examples. Implementations consume their generated TypeScript equivalents.

| Schema | Canonical reference |
| --- | --- |
| AddOnCreate | openapi.json#/components/schemas/AddOnCreate |
| AddOnOut | openapi.json#/components/schemas/AddOnOut |
| AddOnUpdate | openapi.json#/components/schemas/AddOnUpdate |
| AdditionalFieldCreate | openapi.json#/components/schemas/AdditionalFieldCreate |
| AdditionalFieldOut | openapi.json#/components/schemas/AdditionalFieldOut |
| AdditionalFieldResponseCreate | openapi.json#/components/schemas/AdditionalFieldResponseCreate |
| AdditionalFieldResponseOut | openapi.json#/components/schemas/AdditionalFieldResponseOut |
| AdditionalFieldSubmitRequest | openapi.json#/components/schemas/AdditionalFieldSubmitRequest |
| AdditionalFieldUpdate | openapi.json#/components/schemas/AdditionalFieldUpdate |
| AdminAuthRequest | openapi.json#/components/schemas/AdminAuthRequest |
| AdminUIConfigModules | openapi.json#/components/schemas/AdminUIConfigModules |
| AdminUIConfigResponse | openapi.json#/components/schemas/AdminUIConfigResponse |
| AuditLog | openapi.json#/components/schemas/AuditLog |
| AuditLogCreate | openapi.json#/components/schemas/AuditLogCreate |
| AuditLogListResponse | openapi.json#/components/schemas/AuditLogListResponse |
| AuditLogResponse | openapi.json#/components/schemas/AuditLogResponse |
| AvailabilityRequest | openapi.json#/components/schemas/AvailabilityRequest |
| AvailabilitySearchQuery | openapi.json#/components/schemas/AvailabilitySearchQuery |
| BlockedTimeCreate | openapi.json#/components/schemas/BlockedTimeCreate |
| BlockedTimeOut | openapi.json#/components/schemas/BlockedTimeOut |
| BlockedTimeUpdate | openapi.json#/components/schemas/BlockedTimeUpdate |
| Booking | openapi.json#/components/schemas/Booking |
| BookingCreate | openapi.json#/components/schemas/BookingCreate |
| BookingFlowConfig | openapi.json#/components/schemas/BookingFlowConfig |
| BookingFormCreate | openapi.json#/components/schemas/BookingFormCreate |
| BookingFormOut | openapi.json#/components/schemas/BookingFormOut |
| BookingFormUpdate | openapi.json#/components/schemas/BookingFormUpdate |
| BookingListResponse | openapi.json#/components/schemas/BookingListResponse |
| BookingReschedule | openapi.json#/components/schemas/BookingReschedule |
| BookingResponse | openapi.json#/components/schemas/BookingResponse |
| BookingSelections | openapi.json#/components/schemas/BookingSelections |
| BookingSeriesCreate | openapi.json#/components/schemas/BookingSeriesCreate |
| BookingSeriesOut | openapi.json#/components/schemas/BookingSeriesOut |
| BookingStatus | openapi.json#/components/schemas/BookingStatus |
| BookingUpdate | openapi.json#/components/schemas/BookingUpdate |
| BusinessProfileOut | openapi.json#/components/schemas/BusinessProfileOut |
| BusinessProfileResponse | openapi.json#/components/schemas/BusinessProfileResponse |
| BusinessProfileUpdate | openapi.json#/components/schemas/BusinessProfileUpdate |
| ButtonGradient | openapi.json#/components/schemas/ButtonGradient |
| CalendarNoteCreate | openapi.json#/components/schemas/CalendarNoteCreate |
| CalendarNoteListResponse | openapi.json#/components/schemas/CalendarNoteListResponse |
| CalendarNoteOut | openapi.json#/components/schemas/CalendarNoteOut |
| CalendarNoteResponse | openapi.json#/components/schemas/CalendarNoteResponse |
| CalendarNoteUpdate | openapi.json#/components/schemas/CalendarNoteUpdate |
| CategoryCreate | openapi.json#/components/schemas/CategoryCreate |
| CategoryOut | openapi.json#/components/schemas/CategoryOut |
| CategoryUpdate | openapi.json#/components/schemas/CategoryUpdate |
| CheckoutCommitRequest | openapi.json#/components/schemas/CheckoutCommitRequest |
| CheckoutCommitResponse | openapi.json#/components/schemas/CheckoutCommitResponse |
| Client | openapi.json#/components/schemas/Client |
| ClientAuthResponse | openapi.json#/components/schemas/ClientAuthResponse |
| ClientCreate | openapi.json#/components/schemas/ClientCreate |
| ClientIdentifyData | openapi.json#/components/schemas/ClientIdentifyData |
| ClientIdentifyResponse | openapi.json#/components/schemas/ClientIdentifyResponse |
| ClientListResponse | openapi.json#/components/schemas/ClientListResponse |
| ClientResponse | openapi.json#/components/schemas/ClientResponse |
| ClientUpdate | openapi.json#/components/schemas/ClientUpdate |
| CreateAndConnectRequest | openapi.json#/components/schemas/CreateAndConnectRequest |
| DeviceToken | openapi.json#/components/schemas/DeviceToken |
| DeviceTokenCreate | openapi.json#/components/schemas/DeviceTokenCreate |
| DeviceTokenResponse | openapi.json#/components/schemas/DeviceTokenResponse |
| DiagnosticsCounts | openapi.json#/components/schemas/DiagnosticsCounts |
| DiagnosticsModules | openapi.json#/components/schemas/DiagnosticsModules |
| DiagnosticsResponse | openapi.json#/components/schemas/DiagnosticsResponse |
| DuplicateBookingFormRequest | openapi.json#/components/schemas/DuplicateBookingFormRequest |
| EmbedAppearance | openapi.json#/components/schemas/EmbedAppearance |
| EmbedCatalogue | openapi.json#/components/schemas/EmbedCatalogue |
| EmbedConfiguration | openapi.json#/components/schemas/EmbedConfiguration |
| EmbedConfigurationPatch | openapi.json#/components/schemas/EmbedConfigurationPatch |
| EmbedManifest | openapi.json#/components/schemas/EmbedManifest |
| EmbedManifestFlow | openapi.json#/components/schemas/EmbedManifestFlow |
| EmbedManifestSurface | openapi.json#/components/schemas/EmbedManifestSurface |
| EmbedRuntimeSettings | openapi.json#/components/schemas/EmbedRuntimeSettings |
| FormCatalogueResponse | openapi.json#/components/schemas/FormCatalogueResponse |
| FormEmbedData | openapi.json#/components/schemas/FormEmbedData |
| FormEmbedResponse | openapi.json#/components/schemas/FormEmbedResponse |
| FormFieldSchema | openapi.json#/components/schemas/FormFieldSchema |
| FormOption | openapi.json#/components/schemas/FormOption |
| FormPreviewData | openapi.json#/components/schemas/FormPreviewData |
| FormPreviewResponse | openapi.json#/components/schemas/FormPreviewResponse |
| FormSchemaResponse | openapi.json#/components/schemas/FormSchemaResponse |
| GdprConsentCreate | openapi.json#/components/schemas/GdprConsentCreate |
| GdprConsentListResponse | openapi.json#/components/schemas/GdprConsentListResponse |
| GdprConsentOut | openapi.json#/components/schemas/GdprConsentOut |
| GdprConsentResponse | openapi.json#/components/schemas/GdprConsentResponse |
| HTTPValidationError | openapi.json#/components/schemas/HTTPValidationError |
| HoldConfirm | openapi.json#/components/schemas/HoldConfirm |
| HoldCreate | openapi.json#/components/schemas/HoldCreate |
| HoldOut | openapi.json#/components/schemas/HoldOut |
| HoldStatus | openapi.json#/components/schemas/HoldStatus |
| InvoiceCreate | openapi.json#/components/schemas/InvoiceCreate |
| InvoiceLineOut | openapi.json#/components/schemas/InvoiceLineOut |
| InvoiceListResponse | openapi.json#/components/schemas/InvoiceListResponse |
| InvoiceOut | openapi.json#/components/schemas/InvoiceOut |
| InvoiceResponse | openapi.json#/components/schemas/InvoiceResponse |
| InvoiceStatusUpdate | openapi.json#/components/schemas/InvoiceStatusUpdate |
| Location | openapi.json#/components/schemas/Location |
| LocationCreate | openapi.json#/components/schemas/LocationCreate |
| LocationListResponse | openapi.json#/components/schemas/LocationListResponse |
| LocationResponse | openapi.json#/components/schemas/LocationResponse |
| LocationUpdate | openapi.json#/components/schemas/LocationUpdate |
| ManagementReviewRequestCreate | openapi.json#/components/schemas/ManagementReviewRequestCreate |
| ManagementReviewRequestListResponse | openapi.json#/components/schemas/ManagementReviewRequestListResponse |
| ManagementReviewRequestOut | openapi.json#/components/schemas/ManagementReviewRequestOut |
| ManagementReviewRequestResponse | openapi.json#/components/schemas/ManagementReviewRequestResponse |
| ManagementReviewRequestUpdate | openapi.json#/components/schemas/ManagementReviewRequestUpdate |
| Notification | openapi.json#/components/schemas/Notification |
| NotificationCreate | openapi.json#/components/schemas/NotificationCreate |
| NotificationListResponse | openapi.json#/components/schemas/NotificationListResponse |
| NotificationResponse | openapi.json#/components/schemas/NotificationResponse |
| NotificationTemplate | openapi.json#/components/schemas/NotificationTemplate |
| NotificationTemplateCreate | openapi.json#/components/schemas/NotificationTemplateCreate |
| NotificationTemplateListResponse | openapi.json#/components/schemas/NotificationTemplateListResponse |
| NotificationTemplateResponse | openapi.json#/components/schemas/NotificationTemplateResponse |
| NotificationTemplateUpdate | openapi.json#/components/schemas/NotificationTemplateUpdate |
| NotificationUpdate | openapi.json#/components/schemas/NotificationUpdate |
| PackageCreate | openapi.json#/components/schemas/PackageCreate |
| PackageOut | openapi.json#/components/schemas/PackageOut |
| PackageStepCreate | openapi.json#/components/schemas/PackageStepCreate |
| PackageStepOut | openapi.json#/components/schemas/PackageStepOut |
| PackageStepUpdate | openapi.json#/components/schemas/PackageStepUpdate |
| PackageUpdate | openapi.json#/components/schemas/PackageUpdate |
| Payment | openapi.json#/components/schemas/Payment |
| PaymentCreate | openapi.json#/components/schemas/PaymentCreate |
| PaymentListResponse | openapi.json#/components/schemas/PaymentListResponse |
| PaymentProcessorConfigCreate | openapi.json#/components/schemas/PaymentProcessorConfigCreate |
| PaymentProcessorConfigOut | openapi.json#/components/schemas/PaymentProcessorConfigOut |
| PaymentProcessorConfigUpdate | openapi.json#/components/schemas/PaymentProcessorConfigUpdate |
| PaymentResponse | openapi.json#/components/schemas/PaymentResponse |
| PaymentUpdate | openapi.json#/components/schemas/PaymentUpdate |
| PluginStateCreate | openapi.json#/components/schemas/PluginStateCreate |
| PluginStateListResponse | openapi.json#/components/schemas/PluginStateListResponse |
| PluginStateOut | openapi.json#/components/schemas/PluginStateOut |
| PluginStateResponse | openapi.json#/components/schemas/PluginStateResponse |
| PluginStateUpdate | openapi.json#/components/schemas/PluginStateUpdate |
| PredefinedValues | openapi.json#/components/schemas/PredefinedValues |
| ProductCreate | openapi.json#/components/schemas/ProductCreate |
| ProductOut | openapi.json#/components/schemas/ProductOut |
| ProductUpdate | openapi.json#/components/schemas/ProductUpdate |
| PromotionCodeCreate | openapi.json#/components/schemas/PromotionCodeCreate |
| PromotionCodeOut | openapi.json#/components/schemas/PromotionCodeOut |
| PromotionCodeUpdate | openapi.json#/components/schemas/PromotionCodeUpdate |
| PromotionValidationResponse | openapi.json#/components/schemas/PromotionValidationResponse |
| Provider | openapi.json#/components/schemas/Provider |
| ProviderCreate | openapi.json#/components/schemas/ProviderCreate |
| ProviderListResponse | openapi.json#/components/schemas/ProviderListResponse |
| ProviderResponse | openapi.json#/components/schemas/ProviderResponse |
| ProviderSpecialDayCreate | openapi.json#/components/schemas/ProviderSpecialDayCreate |
| ProviderSpecialDayOut | openapi.json#/components/schemas/ProviderSpecialDayOut |
| ProviderSpecialDayUpdate | openapi.json#/components/schemas/ProviderSpecialDayUpdate |
| ProviderUpdate | openapi.json#/components/schemas/ProviderUpdate |
| ProviderWorkDayCreate | openapi.json#/components/schemas/ProviderWorkDayCreate |
| ProviderWorkDayOut | openapi.json#/components/schemas/ProviderWorkDayOut |
| ProviderWorkDayUpdate | openapi.json#/components/schemas/ProviderWorkDayUpdate |
| PublicAuthRequest | openapi.json#/components/schemas/PublicAuthRequest |
| PublicBootstrapData | openapi.json#/components/schemas/PublicBootstrapData |
| PublicBootstrapResponse | openapi.json#/components/schemas/PublicBootstrapResponse |
| PublicBusinessProfileOut | openapi.json#/components/schemas/PublicBusinessProfileOut |
| PublicBusinessProfileResponse | openapi.json#/components/schemas/PublicBusinessProfileResponse |
| PublicClientLogin | openapi.json#/components/schemas/PublicClientLogin |
| PublicClientProfileUpdate | openapi.json#/components/schemas/PublicClientProfileUpdate |
| PublicClientRegister | openapi.json#/components/schemas/PublicClientRegister |
| PublicUIConfigResponse | openapi.json#/components/schemas/PublicUIConfigResponse |
| QuoteRequest | openapi.json#/components/schemas/QuoteRequest |
| QuoteResponse | openapi.json#/components/schemas/QuoteResponse |
| RelationshipEditorResponse | openapi.json#/components/schemas/RelationshipEditorResponse |
| RelationshipLinkResponse | openapi.json#/components/schemas/RelationshipLinkResponse |
| RelationshipListResponse | openapi.json#/components/schemas/RelationshipListResponse |
| ReminderRule | openapi.json#/components/schemas/ReminderRule |
| ReminderRuleCreate | openapi.json#/components/schemas/ReminderRuleCreate |
| ReminderRuleListResponse | openapi.json#/components/schemas/ReminderRuleListResponse |
| ReminderRuleResponse | openapi.json#/components/schemas/ReminderRuleResponse |
| ReminderRuleUpdate | openapi.json#/components/schemas/ReminderRuleUpdate |
| ReservedTimeCreate | openapi.json#/components/schemas/ReservedTimeCreate |
| ReservedTimeOut | openapi.json#/components/schemas/ReservedTimeOut |
| ReservedTimeUpdate | openapi.json#/components/schemas/ReservedTimeUpdate |
| ResolveRequest | openapi.json#/components/schemas/ResolveRequest |
| ResolvedBookingForm | openapi.json#/components/schemas/ResolvedBookingForm |
| ResolvedContext | openapi.json#/components/schemas/ResolvedContext |
| ResourceCreate | openapi.json#/components/schemas/ResourceCreate |
| ResourceOut | openapi.json#/components/schemas/ResourceOut |
| ResourceUpdate | openapi.json#/components/schemas/ResourceUpdate |
| SearchAvailabilityMeta | openapi.json#/components/schemas/SearchAvailabilityMeta |
| SearchAvailabilityProvider | openapi.json#/components/schemas/SearchAvailabilityProvider |
| SearchAvailabilityResource | openapi.json#/components/schemas/SearchAvailabilityResource |
| SearchAvailabilityResponse | openapi.json#/components/schemas/SearchAvailabilityResponse |
| SearchAvailabilityService | openapi.json#/components/schemas/SearchAvailabilityService |
| Service | openapi.json#/components/schemas/Service |
| ServiceCreate | openapi.json#/components/schemas/ServiceCreate |
| ServiceListResponse | openapi.json#/components/schemas/ServiceListResponse |
| ServiceOption | openapi.json#/components/schemas/ServiceOption |
| ServiceProductBase | openapi.json#/components/schemas/ServiceProductBase |
| ServiceProductOut | openapi.json#/components/schemas/ServiceProductOut |
| ServiceResourceRequirementCreate | openapi.json#/components/schemas/ServiceResourceRequirementCreate |
| ServiceResourceRequirementOut | openapi.json#/components/schemas/ServiceResourceRequirementOut |
| ServiceResponse | openapi.json#/components/schemas/ServiceResponse |
| ServiceUpdate | openapi.json#/components/schemas/ServiceUpdate |
| SurfaceColours | openapi.json#/components/schemas/SurfaceColours |
| TaxRateCreate | openapi.json#/components/schemas/TaxRateCreate |
| TaxRateOut | openapi.json#/components/schemas/TaxRateOut |
| TaxRateUpdate | openapi.json#/components/schemas/TaxRateUpdate |
| TenantMapPin | openapi.json#/components/schemas/TenantMapPin |
| TipCreate | openapi.json#/components/schemas/TipCreate |
| TipOut | openapi.json#/components/schemas/TipOut |
| TokenResponse | openapi.json#/components/schemas/TokenResponse |
| UIConfigModules | openapi.json#/components/schemas/UIConfigModules |
| User | openapi.json#/components/schemas/User |
| UserCreate | openapi.json#/components/schemas/UserCreate |
| UserResponse | openapi.json#/components/schemas/UserResponse |
| ValidationError | openapi.json#/components/schemas/ValidationError |
| WaitlistCreate | openapi.json#/components/schemas/WaitlistCreate |
| WaitlistOut | openapi.json#/components/schemas/WaitlistOut |
| WaitlistStatus | openapi.json#/components/schemas/WaitlistStatus |
| WebhookAckResponse | openapi.json#/components/schemas/WebhookAckResponse |
| WebhookCreate | openapi.json#/components/schemas/WebhookCreate |
| WebhookListResponse | openapi.json#/components/schemas/WebhookListResponse |
| WebhookOut | openapi.json#/components/schemas/WebhookOut |
| WebhookResponse | openapi.json#/components/schemas/WebhookResponse |
| WebhookUpdate | openapi.json#/components/schemas/WebhookUpdate |
| WidgetAvailabilityData | openapi.json#/components/schemas/WidgetAvailabilityData |
| WidgetAvailabilityResponse | openapi.json#/components/schemas/WidgetAvailabilityResponse |
| WidgetBookingRequest | openapi.json#/components/schemas/WidgetBookingRequest |
| WidgetFormData | openapi.json#/components/schemas/WidgetFormData |
| WidgetFormResponse | openapi.json#/components/schemas/WidgetFormResponse |
| WidgetResolveResponse | openapi.json#/components/schemas/WidgetResolveResponse |
| WidgetRuntimeManifestResponse | openapi.json#/components/schemas/WidgetRuntimeManifestResponse |
| WorkloadSummary | openapi.json#/components/schemas/WorkloadSummary |
| app__api__routers__booking_forms__SearchAvailabilityItem | openapi.json#/components/schemas/app__api__routers__booking_forms__SearchAvailabilityItem |
| app__api__routers__search__SearchAvailabilityItem | openapi.json#/components/schemas/app__api__routers__search__SearchAvailabilityItem |

## 13. Authentication, tenancy, and permissions

### Tenant resolution

Backend order is `X-Tenant`, then `tenant` query parameter, then hostname subdomain with Cloud Run/common-host exclusions. Production uses hostname/configuration; query/header overrides are restricted to controlled development and BFF contexts.

### Token and role rules

- Admin credentials and public API-key exchange both require tenant context.
- Owner/admin are the only V1 admin roles.
- Staff/viewer receive a dedicated denial route.
- Public/client/admin JWT subjects are transmitted through `X-Token` only.
- Tokens are memory-only and cleared with tenant/auth cache boundaries.

### Critical backend authorization audit

Live OpenAPI exposes the following non-login `/api/admin` operations without an `X-Token` header. The frontend cannot repair backend authorization by hiding controls. Each operation blocks production until the backend adds an owner/admin dependency or explicitly documents a safe alternative.

| Method | Backend path | Operation ID | Source | Required disposition |
| --- | --- | --- | --- | --- |

## 14. Non-functional, responsive, accessibility, and security requirements

### Responsive design

Public booking is mobile-first with single-column progression and a collapsible summary. At 320 CSS px, content reflows without two-dimensional page scrolling; only intrinsically wide data regions may scroll inside a labelled container. At 200% zoom, primary actions, validation messages and navigation remain visible and operable. Admin lists become cards or horizontally scrollable labelled regions below tablet widths; destructive actions remain reachable without hover. Calendars provide agenda/list alternatives, and maps provide a synchronised result list. Breakpoints are content-driven and tested in portrait and landscape with touch, keyboard and pointer input.

### Accessibility

Target WCAG 2.2 AA with the following release criteria:

- **Structure and navigation:** one descriptive `h1`, ordered headings, semantic landmarks, skip link, descriptive page titles and current-route indication. Repeated controls have accessible names that include their row/card context.
- **Keyboard and focus:** all actions work without a pointer; focus order follows the visual/task order; focus is never trapped except inside an active modal; dialogs restore focus to their trigger; route changes and validation failures move focus deliberately and visibly.
- **Forms:** persistent programmatic labels, instructions before input, required state conveyed in text, `aria-describedby` links to help/errors, an error summary linked to invalid fields, and no loss of valid input after server errors. Date, time, combobox and file controls retain native semantics or follow established ARIA patterns.
- **Dynamic states:** loading, mutation outcomes, slot expiry and background errors use appropriately scoped live regions without repeated announcements. Skeletons are hidden from assistive technology and never replace an announced accessible status.
- **Visual access:** text and meaningful UI meet AA contrast, status never depends on color alone, focus indicators remain visible, targets meet WCAG 2.2 minimum sizing, text-spacing overrides do not clip content, and animations respect `prefers-reduced-motion`.
- **Complex views:** map results have a synchronised list; calendars have agenda/table alternatives; charts expose a text summary and data table; drag-and-drop actions have keyboard controls; virtualised lists preserve names, positions and focus.
- **Timing and recovery:** warn before session, hold or slot expiry; allow extension where backend rules permit; preserve non-sensitive form input; confirmations identify the affected record; destructive and financial operations require review or an undo path where feasible.
- **Verification:** automated axe checks run in component and Playwright suites. Manual keyboard and screen-reader checks cover tenant entry, public booking, checkout, client authentication, admin login, booking approval/rejection and rescheduling at every release.

### Security

No bearer tokens or API secrets in persistent browser storage, URLs, analytics or logs. Encode untrusted output, validate external URLs, disallow arbitrary HTML, enforce CSP at deployment, scan built assets for secrets, and clear tenant-scoped state atomically. CORS is an allowlist, not an authorization control. Same-origin BFF cookies, if introduced, require CSRF protection.

### Performance and reliability

Meet Section 3 field targets. Code-split admin modules, prefetch only safe tenant-scoped data, cancel stale requests, and keep booking selections resilient to recoverable network errors without persisting sensitive values.

## 15. Validation, errors, conflicts, and edge cases

| State | Required UI behavior | Applies to |
| --- | --- | --- |
| Initial loading | Skeleton/progress; controls disabled | All |
| Empty | Explain absence and offer permitted creation/change action | Lists/forms |
| Network/offline | Retain safe input; retry manually; never duplicate mutation | All |
| 400 | Tenant/request-level explanation | Global/form |
| 401 | Clear session and reauthenticate/bootstrap | Authenticated |
| 403 | Permission or role-not-enabled screen | Protected |
| 404 | Not-found state with safe parent navigation | Detail/public surface |
| 409 | Refetch, retain input, require explicit retry | Availability/state transitions |
| 422 | Field mapping plus accessible summary | Forms |
| 429 | Retry guidance and bounded backoff | Public/rate-limited |
| 500 | Generic message plus request ID; no internals | All |
| Tenant switch | Clear tokens, stores, query cache and pending requests | All |
| Slot expires | Return to refreshed availability | Booking |
| Reload after outcome | Safe fallback if no retrieval endpoint | Public outcome |

## 16. Technical frontend architecture and API integration

### Stack

React 19, TypeScript, Vite, React Router, TanStack Query, React Hook Form, Zod refinements, OpenAPI-generated types/client, Tailwind CSS with a controlled shadcn/ui layer, limited Zustand/Context for ephemeral session/UI state, Vitest/React Testing Library, Playwright and Storybook.

### Layering

```text
routes/layouts
  → feature screens
    → query/mutation hooks
      → generated OpenAPI client
        → tenant/auth/error middleware
          → FastAPI or same-origin BFF
```

Generated API types are never re-declared manually. Zod may refine UI-only cross-field rules but must not contradict OpenAPI. The BFF owns the secret public-token exchange. Environment configuration contains only publishable values such as API base URL and controlled development tenant override.

### Contract workflow

1. Export fresh OpenAPI from the importable app.
2. Fail CI when its hash differs from committed `openapi.json`.
3. Regenerate `contracts/types.ts` and the typed client.
4. Typecheck feature hooks and validate the operation ledger.
5. Run contract/integration and Playwright tests before build promotion.

## 17. Analytics, audit, and observability

Instrument tenant resolution, booking-surface readiness, availability viewed, hold created/expired, booking outcome, client auth outcome, admin mutation outcome, role denial, deprecated-operation detection and frontend errors. Capture duration, outcome category and non-sensitive tenant pseudonym; never capture tokens, passwords, free-text notes, payment credentials or sensitive client fields.

Preserve backend `request_id` in support-visible error details and telemetry correlation. Analytics remains disabled until provider selection, consent basis, retention and data residency are approved.

## 18. Testing and QA acceptance criteria

### Required layers

- Generator/contract tests: OpenAPI hash, 246 exact operations, zero duplicate ledger keys, generated type freshness and zero deprecated imports.
- Unit tests: error normalization, tenant resolution, auth middleware, query-key isolation, state-machine action visibility and Zod refinements.
- Component tests: every loading/empty/error/permission/conflict state and accessible keyboard behavior.
- Integration tests: every consumed operation has at least one generated-client contract test; related backend tests are evidence but not a substitute.
- Playwright: public booking, hold conflict, client auth/profile, owner/admin login, staff/viewer denial, booking lifecycle, tenant switch isolation and critical CRUD.
- Accessibility: automated axe plus manual keyboard/screen-reader testing for login, booking, approval and rescheduling.
- Security: built-asset secret scan, token persistence scan, external URL tests and cross-tenant cache tests.

### Current backend verification evidence

Focused suite: 18 passed with six deprecation warnings across tenancy, booking-form contracts, configurable forms and booking policies. Full test inventory:

| Test file | Status in this report |
| --- | --- |
| tests/test_audit_fixes.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_audit_resolution.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_booking_form_contracts.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_booking_policies_remediation.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_concurrency.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_configurable_booking_forms.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_embed_configuration.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_fuzzer.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_multi_tenancy.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_notification_configs.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_phase_5_6_7.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_predecessor_record_keeping.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_public_entities_remediation.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_relationships_remediation.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_retention_remediation.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_scheduling_constraints.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_scheduling_edge_cases.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_scheduling_intervals.py | Available; direct per-operation linkage only where Appendix D says related |
| tests/test_security_fuzzing.py | Available; direct per-operation linkage only where Appendix D says related |

## 19. Implementation sequence, MVP, and release gates

1. **Backend security gate:** resolve unexpectedly unguarded admin operations and public-token exchange.
2. **Contract foundation:** regenerate OpenAPI types/client, tenant/auth middleware, errors and query-key factory.
3. **Design foundation:** accessible primitives, layout, forms, tables/cards, dialogs, calendars and state components.
4. **Public core:** tenant entry, booking-form runtime, availability, details, hold and pending outcome.
5. **Client core:** registration/login/profile/terms/consent.
6. **Admin core:** login/role guard, dashboard, bookings/calendar and booking transitions.
7. **Catalog and scheduling:** services/providers/locations/categories, relationships, workdays/exceptions and resources.
8. **Commerce and communications:** add-ons/products/packages, invoices/payments/tax/promotions, notifications/templates/reminders.
9. **Operations:** reviews, audit, GDPR, webhooks, plugins, diagnostics and maintenance.
10. **Release hardening:** operation-to-test coverage, Playwright, accessibility, performance, security and observability gates.

MVP release requires zero unresolved critical/high findings, zero deprecated calls, all consumed operations generated and tested, the authorization audit closed, BFF token exchange operational, accessibility critical flows passing, and production telemetry/privacy approval.

## Appendix A. Screen-to-API ownership

| Operation | Frontend module | Frontend route | Classification |
| --- | --- | --- | --- |
| GET /api/admin/add-ons | Catalog / add-ons | /admin/catalog/add-ons | directly represented |
| POST /api/admin/add-ons | Catalog / add-ons | /admin/catalog/add-ons | directly represented |
| DELETE /api/admin/add-ons/{add_on_id} | Catalog / add-ons | /admin/catalog/add-ons | directly represented |
| GET /api/admin/add-ons/{add_on_id} | Catalog / add-ons | /admin/catalog/add-ons | directly represented |
| PUT /api/admin/add-ons/{add_on_id} | Catalog / add-ons | /admin/catalog/add-ons | directly represented |
| GET /api/admin/additional-field-responses | Additional fields | /admin/configuration/additional-fields | directly represented |
| GET /api/admin/additional-fields | Additional fields | /admin/configuration/additional-fields | directly represented |
| POST /api/admin/additional-fields | Additional fields | /admin/configuration/additional-fields | directly represented |
| DELETE /api/admin/additional-fields/{field_id} | Additional fields | /admin/configuration/additional-fields | directly represented |
| PUT /api/admin/additional-fields/{field_id} | Additional fields | /admin/configuration/additional-fields | directly represented |
| GET /api/admin/audit-log | Audit | /admin/audit | directly represented |
| POST /api/admin/audit-log | Audit | /admin/audit | directly represented |
| POST /api/admin/auth | Authentication | /admin/login | directly represented |
| GET /api/admin/booking-forms | Booking-form administration | /admin/booking-forms | directly represented |
| POST /api/admin/booking-forms | Booking-form administration | /admin/booking-forms | directly represented |
| GET /api/admin/booking-forms/configuration-catalogue | Booking-form administration | /admin/booking-forms | directly represented |
| DELETE /api/admin/booking-forms/{form_id} | Booking-form administration | /admin/booking-forms | directly represented |
| GET /api/admin/booking-forms/{form_id} | Booking-form administration | /admin/booking-forms | directly represented |
| PUT /api/admin/booking-forms/{form_id} | Booking-form administration | /admin/booking-forms | directly represented |
| GET /api/admin/booking-forms/{form_id}/design | Booking-form administration | /admin/booking-forms | directly represented |
| PUT /api/admin/booking-forms/{form_id}/design | Booking-form administration | /admin/booking-forms | directly represented |
| POST /api/admin/booking-forms/{form_id}/duplicate | Booking-form administration | /admin/booking-forms | directly represented |
| GET /api/admin/booking-forms/{form_id}/embed | Booking-form administration | /admin/booking-forms | directly represented |
| GET /api/admin/booking-forms/{form_id}/preview | Booking-form administration | /admin/booking-forms | directly represented |
| GET /api/admin/bookings | Booking operations | /admin/bookings | directly represented |
| POST /api/admin/bookings | Booking operations | /admin/bookings | directly represented |
| GET /api/admin/bookings/{booking_id} | Booking operations | /admin/bookings | directly represented |
| PUT /api/admin/bookings/{booking_id} | Booking operations | /admin/bookings | directly represented |
| POST /api/admin/bookings/{booking_id}/cancel | Booking operations | /admin/bookings | directly represented |
| POST /api/admin/bookings/{booking_id}/complete | Booking operations | /admin/bookings | directly represented |
| POST /api/admin/bookings/{booking_id}/confirm | Booking operations | /admin/bookings | directly represented |
| POST /api/admin/bookings/{booking_id}/noshow | Booking operations | /admin/bookings | directly represented |
| POST /api/admin/bookings/{booking_id}/reschedule | Booking operations | /admin/bookings | directly represented |
| GET /api/admin/business-profile | Business profile | /admin/settings/business | directly represented |
| PUT /api/admin/business-profile | Business profile | /admin/settings/business | directly represented |
| POST /api/admin/business-profile/geocode | Discovery | /discover | directly represented |
| GET /api/admin/calendar-notes | Calendar | /admin/calendar | directly represented |
| POST /api/admin/calendar-notes | Calendar | /admin/calendar | directly represented |
| DELETE /api/admin/calendar-notes/{note_id} | Calendar | /admin/calendar | directly represented |
| PUT /api/admin/calendar-notes/{note_id} | Calendar | /admin/calendar | directly represented |
| GET /api/admin/categories | Catalog / categories | /admin/catalog/categories | directly represented |
| POST /api/admin/categories | Catalog / categories | /admin/catalog/categories | directly represented |
| DELETE /api/admin/categories/{category_id} | Catalog / categories | /admin/catalog/categories | directly represented |
| GET /api/admin/categories/{category_id} | Catalog / categories | /admin/catalog/categories | directly represented |
| PUT /api/admin/categories/{category_id} | Catalog / categories | /admin/catalog/categories | directly represented |
| GET /api/admin/categories/{record_id}/editor | Relationship editor | /admin/relationships | directly represented |
| GET /api/admin/clients | Client administration | /admin/clients | directly represented |
| POST /api/admin/clients | Client administration | /admin/clients | directly represented |
| DELETE /api/admin/clients/{client_id} | Client administration | /admin/clients | directly represented |
| GET /api/admin/clients/{client_id} | Client administration | /admin/clients | directly represented |
| PUT /api/admin/clients/{client_id} | Client administration | /admin/clients | directly represented |
| GET /api/admin/clients/{record_id}/editor | Relationship editor | /admin/relationships | directly represented |
| GET /api/admin/dashboard/bootstrap | Dashboard | /admin | directly represented |
| GET /api/admin/gdpr-consents | System and compliance | /admin/system | directly represented |
| GET /api/admin/gdpr-consents/{client_id} | System and compliance | /admin/system | directly represented |
| GET /api/admin/invoices | Checkout and finance | /admin/finance/invoices | directly represented |
| GET /api/admin/invoices/{invoice_id} | Checkout and finance | /admin/finance/invoices | directly represented |
| PUT /api/admin/invoices/{invoice_id}/status | Checkout and finance | /admin/finance/invoices | directly represented |
| GET /api/admin/locations | Catalog / locations | /admin/catalog/locations | directly represented |
| POST /api/admin/locations | Catalog / locations | /admin/catalog/locations | directly represented |
| DELETE /api/admin/locations/{location_id} | Catalog / locations | /admin/catalog/locations | directly represented |
| GET /api/admin/locations/{location_id} | Catalog / locations | /admin/catalog/locations | directly represented |
| PUT /api/admin/locations/{location_id} | Catalog / locations | /admin/catalog/locations | directly represented |
| GET /api/admin/locations/{location_id}/categories | Relationship editor | /admin/relationships | directly represented |
| DELETE /api/admin/locations/{location_id}/categories/{category_id} | Relationship editor | /admin/relationships | directly represented |
| POST /api/admin/locations/{location_id}/categories/{category_id} | Relationship editor | /admin/relationships | directly represented |
| GET /api/admin/locations/{location_id}/providers | Relationship editor | /admin/relationships | directly represented |
| DELETE /api/admin/locations/{location_id}/providers/{provider_id} | Relationship editor | /admin/relationships | directly represented |
| POST /api/admin/locations/{location_id}/providers/{provider_id} | Relationship editor | /admin/relationships | directly represented |
| GET /api/admin/locations/{location_id}/services | Relationship editor | /admin/relationships | directly represented |
| DELETE /api/admin/locations/{location_id}/services/{service_id} | Relationship editor | /admin/relationships | directly represented |
| POST /api/admin/locations/{location_id}/services/{service_id} | Relationship editor | /admin/relationships | directly represented |
| GET /api/admin/locations/{record_id}/editor | Relationship editor | /admin/relationships | directly represented |
| GET /api/admin/management-reviews | Management reviews | /admin/reviews | directly represented |
| GET /api/admin/management-reviews/{review_id} | Management reviews | /admin/reviews | directly represented |
| PUT /api/admin/management-reviews/{review_id}/resolve | Management reviews | /admin/reviews | directly represented |
| GET /api/admin/notification-templates | Notification templates | /admin/notifications/templates | directly represented |
| POST /api/admin/notification-templates | Notification templates | /admin/notifications/templates | directly represented |
| DELETE /api/admin/notification-templates/{template_id} | Notification templates | /admin/notifications/templates | directly represented |
| PUT /api/admin/notification-templates/{template_id} | Notification templates | /admin/notifications/templates | directly represented |
| GET /api/admin/notifications | Notifications | /admin/notifications/messages | directly represented |
| POST /api/admin/notifications | Notifications | /admin/notifications/messages | directly represented |
| PUT /api/admin/notifications/{notification_id} | Notifications | /admin/notifications/messages | directly represented |
| GET /api/admin/packages | Catalog / packages | /admin/catalog/packages | directly represented |
| POST /api/admin/packages | Catalog / packages | /admin/catalog/packages | directly represented |
| DELETE /api/admin/packages/steps/{step_id} | Catalog / packages | /admin/catalog/packages | directly represented |
| PUT /api/admin/packages/steps/{step_id} | Catalog / packages | /admin/catalog/packages | directly represented |
| DELETE /api/admin/packages/{package_id} | Catalog / packages | /admin/catalog/packages | directly represented |
| GET /api/admin/packages/{package_id} | Catalog / packages | /admin/catalog/packages | directly represented |
| PUT /api/admin/packages/{package_id} | Catalog / packages | /admin/catalog/packages | directly represented |
| POST /api/admin/packages/{package_id}/steps | Catalog / packages | /admin/catalog/packages | directly represented |
| GET /api/admin/payment-processor/configs | Checkout and finance | /admin/finance/invoices | directly represented |
| POST /api/admin/payment-processor/configs | Checkout and finance | /admin/finance/invoices | directly represented |
| PUT /api/admin/payment-processor/configs/{config_id} | Checkout and finance | /admin/finance/invoices | directly represented |
| GET /api/admin/payments | Payments | /admin/finance/payments | directly represented |
| POST /api/admin/payments | Payments | /admin/finance/payments | directly represented |
| PUT /api/admin/payments/{payment_id} | Payments | /admin/finance/payments | directly represented |
| GET /api/admin/plugin-states | System and compliance | /admin/system | directly represented |
| POST /api/admin/plugin-states | System and compliance | /admin/system | directly represented |
| PUT /api/admin/plugin-states/{name} | System and compliance | /admin/system | directly represented |
| GET /api/admin/products | Catalog / products | /admin/catalog/products | directly represented |
| POST /api/admin/products | Catalog / products | /admin/catalog/products | directly represented |
| POST /api/admin/products/assign | Catalog / products | /admin/catalog/products | directly represented |
| DELETE /api/admin/products/{product_id} | Catalog / products | /admin/catalog/products | directly represented |
| GET /api/admin/products/{product_id} | Catalog / products | /admin/catalog/products | directly represented |
| PUT /api/admin/products/{product_id} | Catalog / products | /admin/catalog/products | directly represented |
| GET /api/admin/products/{record_id}/editor | Relationship editor | /admin/relationships | directly represented |
| GET /api/admin/promotions | Checkout and finance | /admin/finance/invoices | directly represented |
| POST /api/admin/promotions | Checkout and finance | /admin/finance/invoices | directly represented |
| DELETE /api/admin/promotions/{promotion_id} | Checkout and finance | /admin/finance/invoices | directly represented |
| PUT /api/admin/promotions/{promotion_id} | Checkout and finance | /admin/finance/invoices | directly represented |
| GET /api/admin/providers | Catalog / providers | /admin/catalog/providers | directly represented |
| POST /api/admin/providers | Catalog / providers | /admin/catalog/providers | directly represented |
| DELETE /api/admin/providers/{provider_id} | Catalog / providers | /admin/catalog/providers | directly represented |
| GET /api/admin/providers/{provider_id} | Catalog / providers | /admin/catalog/providers | directly represented |
| PUT /api/admin/providers/{provider_id} | Catalog / providers | /admin/catalog/providers | directly represented |
| GET /api/admin/providers/{record_id}/editor | Relationship editor | /admin/relationships | directly represented |
| POST /api/admin/public/bookings | Booking operations | /admin/bookings | indirectly used by another workflow |
| GET /api/admin/relationships/{left_type}/{left_id}/{right_type} | Relationship editor | /admin/relationships | directly represented |
| POST /api/admin/relationships/{left_type}/{left_id}/{right_type}/create-and-connect | Relationship editor | /admin/relationships | directly represented |
| DELETE /api/admin/relationships/{left_type}/{left_id}/{right_type}/{right_id} | Relationship editor | /admin/relationships | directly represented |
| POST /api/admin/relationships/{left_type}/{left_id}/{right_type}/{right_id} | Relationship editor | /admin/relationships | directly represented |
| GET /api/admin/reminder-rules | Reminder rules | /admin/notifications/reminders | directly represented |
| POST /api/admin/reminder-rules | Reminder rules | /admin/notifications/reminders | directly represented |
| DELETE /api/admin/reminder-rules/{rule_id} | Reminder rules | /admin/notifications/reminders | directly represented |
| PUT /api/admin/reminder-rules/{rule_id} | Reminder rules | /admin/notifications/reminders | directly represented |
| GET /api/admin/resources | Resources | /admin/resources | directly represented |
| POST /api/admin/resources | Resources | /admin/resources | directly represented |
| POST /api/admin/resources/requirements | Resources | /admin/resources | directly represented |
| DELETE /api/admin/resources/{resource_id} | Resources | /admin/resources | directly represented |
| GET /api/admin/resources/{resource_id} | Resources | /admin/resources | directly represented |
| PUT /api/admin/resources/{resource_id} | Resources | /admin/resources | directly represented |
| GET /api/admin/schedule/blocked-times | Schedule | /admin/calendar | directly represented |
| POST /api/admin/schedule/blocked-times | Schedule | /admin/calendar | directly represented |
| DELETE /api/admin/schedule/blocked-times/{block_id} | Schedule | /admin/calendar | directly represented |
| PUT /api/admin/schedule/blocked-times/{block_id} | Schedule | /admin/calendar | directly represented |
| GET /api/admin/schedule/reserved-times | Schedule | /admin/calendar | directly represented |
| POST /api/admin/schedule/reserved-times | Schedule | /admin/calendar | directly represented |
| DELETE /api/admin/schedule/reserved-times/{reserved_id} | Schedule | /admin/calendar | directly represented |
| PUT /api/admin/schedule/reserved-times/{reserved_id} | Schedule | /admin/calendar | directly represented |
| GET /api/admin/schedule/special-days | Schedule | /admin/calendar | directly represented |
| POST /api/admin/schedule/special-days | Schedule | /admin/calendar | directly represented |
| DELETE /api/admin/schedule/special-days/{day_id} | Schedule | /admin/calendar | directly represented |
| PUT /api/admin/schedule/special-days/{day_id} | Schedule | /admin/calendar | directly represented |
| GET /api/admin/schedule/workdays | Schedule | /admin/calendar | directly represented |
| POST /api/admin/schedule/workdays | Schedule | /admin/calendar | directly represented |
| DELETE /api/admin/schedule/workdays/{workday_id} | Schedule | /admin/calendar | directly represented |
| PUT /api/admin/schedule/workdays/{workday_id} | Schedule | /admin/calendar | directly represented |
| GET /api/admin/schedule/workload | Schedule | /admin/calendar | directly represented |
| GET /api/admin/series | Booking series | /admin/bookings | directly represented |
| POST /api/admin/series | Booking series | /admin/bookings | directly represented |
| GET /api/admin/series/{series_id} | Booking series | /admin/bookings | directly represented |
| GET /api/admin/services | Catalog / services | /admin/catalog/services | directly represented |
| POST /api/admin/services | Catalog / services | /admin/catalog/services | directly represented |
| GET /api/admin/services/{record_id}/editor | Relationship editor | /admin/relationships | directly represented |
| DELETE /api/admin/services/{service_id} | Catalog / services | /admin/catalog/services | directly represented |
| GET /api/admin/services/{service_id} | Catalog / services | /admin/catalog/services | directly represented |
| PUT /api/admin/services/{service_id} | Catalog / services | /admin/catalog/services | directly represented |
| GET /api/admin/services/{service_id}/categories | Relationship editor | /admin/relationships | directly represented |
| DELETE /api/admin/services/{service_id}/categories/{category_id} | Relationship editor | /admin/relationships | directly represented |
| POST /api/admin/services/{service_id}/categories/{category_id} | Relationship editor | /admin/relationships | directly represented |
| GET /api/admin/services/{service_id}/providers | Relationship editor | /admin/relationships | directly represented |
| DELETE /api/admin/services/{service_id}/providers/{provider_id} | Relationship editor | /admin/relationships | directly represented |
| POST /api/admin/services/{service_id}/providers/{provider_id} | Relationship editor | /admin/relationships | directly represented |
| POST /api/admin/system/cleanup | System maintenance | /admin/system | directly represented |
| POST /api/admin/system/clients/{client_id}/anonymize | System maintenance | /admin/system | directly represented |
| GET /api/admin/system/diagnostics | System and compliance | /admin/system | directly represented |
| GET /api/admin/tax-rates | Checkout and finance | /admin/finance/invoices | directly represented |
| POST /api/admin/tax-rates | Checkout and finance | /admin/finance/invoices | directly represented |
| DELETE /api/admin/tax-rates/{tax_rate_id} | Checkout and finance | /admin/finance/invoices | directly represented |
| PUT /api/admin/tax-rates/{tax_rate_id} | Checkout and finance | /admin/finance/invoices | directly represented |
| POST /api/admin/users | Authentication | /admin/login | directly represented |
| GET /api/admin/webhooks | Webhooks | /admin/settings/webhooks | directly represented |
| POST /api/admin/webhooks | Webhooks | /admin/settings/webhooks | directly represented |
| GET /api/admin/webhooks/events | Webhooks | /admin/settings/webhooks | directly represented |
| DELETE /api/admin/webhooks/{webhook_id} | Webhooks | /admin/settings/webhooks | directly represented |
| PUT /api/admin/webhooks/{webhook_id} | Webhooks | /admin/settings/webhooks | directly represented |
| GET /api/discovery/map | Discovery | /discover | directly represented |
| GET /api/discovery/services | Discovery | /discover | directly represented |
| GET /api/forms/booking | Generated form metadata | /book/:formSlug/details | indirectly used by another workflow |
| GET /api/forms/provider | Generated form metadata | /book/:formSlug/details | indirectly used by another workflow |
| GET /api/forms/service | Generated form metadata | /book/:formSlug/details | indirectly used by another workflow |
| POST /api/public/additional-field-responses | Additional fields | /admin/configuration/additional-fields | directly represented |
| GET /api/public/additional-fields | Additional fields | /admin/configuration/additional-fields | directly represented |
| POST /api/public/auth/token | Authentication | /admin/login | indirectly used by another workflow |
| GET /api/public/availability | Public availability | /book/:formSlug | directly represented |
| GET /api/public/booking-forms/{slug} | Public booking form | /book/:formSlug | directly represented |
| POST /api/public/booking-forms/{slug}/availability | Public booking form | /book/:formSlug | directly represented |
| POST /api/public/booking-forms/{slug}/bookings | Public booking form | /book/:formSlug | directly represented |
| GET /api/public/booking-forms/{slug}/embed-config | Public booking form | /book/:formSlug | indirectly used by another workflow |
| POST /api/public/booking-forms/{slug}/resolve | Public booking form | /book/:formSlug | directly represented |
| GET /api/public/booking-forms/{slug}/runtime-manifest | Public booking form | /book/:formSlug | indirectly used by another workflow |
| POST /api/public/bookings | Public booking | /book/:formSlug/outcome | directly represented |
| GET /api/public/bootstrap | Public booking bootstrap | /book/:formSlug | indirectly used by another workflow |
| GET /api/public/business-profile | Business profile | /admin/settings/business | directly represented |
| GET /api/public/categories | Compatibility/system | N/A | deprecated |
| POST /api/public/checkout/commit | Checkout and finance | /admin/finance/invoices | directly represented |
| POST /api/public/clients | Client account | /client/register | directly represented |
| POST /api/public/clients/identify | Client account | /client/profile | directly represented |
| POST /api/public/clients/login | Client account | /client/login | directly represented |
| GET /api/public/clients/me | Client account | /client/profile | directly represented |
| PUT /api/public/clients/me | Client account | /client/profile | directly represented |
| POST /api/public/clients/password-reset/request | Client account | /client/password-reset | directly represented |
| POST /api/public/clients/register | Client account | /client/register | directly represented |
| GET /api/public/clients/terms | Client account | /client/terms | directly represented |
| POST /api/public/gdpr-consent | Client consent | /client/terms | directly represented |
| POST /api/public/holds | Public booking hold | /book/:formSlug/checkout | directly represented |
| DELETE /api/public/holds/{hold_id} | Public booking hold | /book/:formSlug/checkout | directly represented |
| POST /api/public/holds/{hold_id}/confirm | Public booking hold | /book/:formSlug/checkout | directly represented |
| POST /api/public/invoices | Checkout and finance | /admin/finance/invoices | directly represented |
| GET /api/public/invoices/{invoice_id} | Checkout and finance | /admin/finance/invoices | directly represented |
| POST /api/public/invoices/{invoice_id}/tips | Checkout and finance | /admin/finance/invoices | directly represented |
| GET /api/public/locations | Compatibility/system | N/A | deprecated |
| POST /api/public/management-reviews | Management reviews | /admin/reviews | directly represented |
| GET /api/public/payment-methods | Checkout and finance | /admin/finance/invoices | directly represented |
| GET /api/public/payment-processor/config | Checkout and finance | /admin/finance/invoices | directly represented |
| GET /api/public/promotions/{code}/validate | Checkout and finance | /admin/finance/invoices | directly represented |
| GET /api/public/providers | Compatibility/system | N/A | deprecated |
| POST /api/public/quote | Checkout and finance | /admin/finance/invoices | directly represented |
| POST /api/public/search-availability | Public availability | /book/:formSlug | directly represented |
| GET /api/public/services | Compatibility/system | N/A | deprecated |
| GET /api/public/services/{service_id}/intake-form | Additional fields | /admin/configuration/additional-fields | directly represented |
| GET /api/public/timeline/first-available-day | Public availability | /book/:formSlug | directly represented |
| GET /api/public/timeline/schedule/{provider_id} | Public availability | /book/:formSlug | directly represented |
| GET /api/public/timeline/slots | Public availability | /book/:formSlug | directly represented |
| GET /api/public/ui-config | Compatibility/system | N/A | deprecated |
| GET /api/public/ui-config/admin | Compatibility/system | N/A | deprecated |
| GET /api/public/waitlist | Public waitlist | /book/:formSlug/outcome | directly represented |
| POST /api/public/waitlist | Public waitlist | /book/:formSlug/outcome | directly represented |
| POST /api/v1/checkout/deposit-session | Payment integration | /admin/finance/payments | directly represented |
| POST /api/v1/devices/register | Notification device registration | /admin/notifications/messages | indirectly used by another workflow |
| POST /api/v1/webhooks/stripe | Compatibility/system | N/A | administrative or system-only |
| GET /health | System health | N/A (monitoring/CI) | administrative or system-only |
| GET /notification-templates | Compatibility/system | N/A | intentionally excluded |
| POST /notification-templates | Compatibility/system | N/A | intentionally excluded |
| DELETE /notification-templates/{template_id} | Compatibility/system | N/A | intentionally excluded |
| PUT /notification-templates/{template_id} | Compatibility/system | N/A | intentionally excluded |
| GET /notifications | Compatibility/system | N/A | intentionally excluded |
| POST /notifications | Compatibility/system | N/A | intentionally excluded |
| PUT /notifications/{notification_id} | Compatibility/system | N/A | intentionally excluded |
| GET /ready | System health | N/A (monitoring/CI) | administrative or system-only |
| GET /reminder-rules | Compatibility/system | N/A | intentionally excluded |
| POST /reminder-rules | Compatibility/system | N/A | intentionally excluded |
| DELETE /reminder-rules/{rule_id} | Compatibility/system | N/A | intentionally excluded |
| PUT /reminder-rules/{rule_id} | Compatibility/system | N/A | intentionally excluded |
| GET /version | System health | N/A (monitoring/CI) | administrative or system-only |

## Appendix B. Evidence register

| Requirement area | Exact evidence | Confidence/limitation |
| --- | --- | --- |
| Operation shapes | `openapi.json` SHA `B1CD8B1E29C3547FE0E82F0CD18501AB598B76B7DCA5FB7B4CF0FC747C53D2B7` and schema refs in Appendix D | Canonical wire source; inline `{}` responses require route/schema implementation review |
| Method/path reconciliation | `contracts/route-manifest.json` SHA `A5041A652775D68DA5E755B22EE4015C18C9E89F1E94FAD593B4E8ED122CC25E` | Does not prove UI use or authentication |
| Tenant/auth implementation | `app/api/deps.py`, `app/api/routers/auth.py`, OpenAPI header parameters | OpenAPI lacks security schemes; Section 13 lists unguarded admin operations |
| Booking states | `app/core/state_machine.py` | Frontend must still handle concurrent 409 responses |
| Resources/relationships | SQLAlchemy `Base.metadata`, model files, Alembic migrations | Indirect tenant scope requires query audit |
| Public booking forms | `app/api/routers/booking_forms.py`, `app/schemas/booking_form.py`, configurable-form tests | Some success responses are inline `{}` in OpenAPI |
| Errors | `app/main.py`, `contracts/errors.contract.json`, `HTTPValidationError` | Legacy FastAPI detail envelopes coexist |
| Existing frontend defects | `mapbox/App.tsx`, `mapbox/services/apiClient.ts`, `mapbox/store/*.tsx` | Evidence only; not target architecture |
| Focused verification | tenancy, booking-form contract, configurable-form and booking-policy test files | 18-test run is not full-suite proof |

## Appendix C. Canonical schema contract rule

Do not copy JSON examples from this document. For every operation, generate the request and response TypeScript types named in Appendix D from `openapi.json`. When OpenAPI exposes an inline or empty schema, inspect the cited route implementation, add an explicit response model to the backend, regenerate OpenAPI, and only then bind production UI to the shape.

## Appendix D. Complete 246-operation ledger

| # | Method | Backend path | Operation ID | Class | Frontend module | Frontend route | Auth | Tenant | Request schema | Responses | Source | Related tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | GET | /api/admin/add-ons | list_addons_api_admin_add_ons_get | directly represented | Catalog / add-ons | /admin/catalog/add-ons | X-Token | Tenant required | — | 200:array&lt;AddOnOut&gt;, 422:HTTPValidationError | app/api/routers/addons.py:18 | No direct mapping asserted |
| 2 | POST | /api/admin/add-ons | create_addon_api_admin_add_ons_post | directly represented | Catalog / add-ons | /admin/catalog/add-ons | X-Token | Tenant required | AddOnCreate | 200:AddOnOut, 422:HTTPValidationError | app/api/routers/addons.py:28 | No direct mapping asserted |
| 3 | DELETE | /api/admin/add-ons/{add_on_id} | delete_addon_api_admin_add_ons__add_on_id__delete | directly represented | Catalog / add-ons | /admin/catalog/add-ons | X-Token | Tenant required | — | 200:AddOnOut, 422:HTTPValidationError | app/api/routers/addons.py:81 | No direct mapping asserted |
| 4 | GET | /api/admin/add-ons/{add_on_id} | get_addon_api_admin_add_ons__add_on_id__get | directly represented | Catalog / add-ons | /admin/catalog/add-ons | X-Token | Tenant required | — | 200:AddOnOut, 422:HTTPValidationError | app/api/routers/addons.py:50 | No direct mapping asserted |
| 5 | PUT | /api/admin/add-ons/{add_on_id} | update_addon_api_admin_add_ons__add_on_id__put | directly represented | Catalog / add-ons | /admin/catalog/add-ons | X-Token | Tenant required | AddOnUpdate | 200:AddOnOut, 422:HTTPValidationError | app/api/routers/addons.py:63 | No direct mapping asserted |
| 6 | GET | /api/admin/additional-field-responses | list_admin_field_responses_api_admin_additional_field_responses_get | directly represented | Additional fields | /admin/configuration/additional-fields | X-Token | Tenant required | — | 200:array&lt;AdditionalFieldResponseOut&gt;, 422:HTTPValidationError | app/api/routers/additional_fields.py:160 | tests/test_booking_policies_remediation.py |
| 7 | GET | /api/admin/additional-fields | list_admin_additional_fields_api_admin_additional_fields_get | directly represented | Additional fields | /admin/configuration/additional-fields | X-Token | Tenant required | — | 200:array&lt;AdditionalFieldOut&gt;, 422:HTTPValidationError | app/api/routers/additional_fields.py:106 | tests/test_booking_policies_remediation.py |
| 8 | POST | /api/admin/additional-fields | create_additional_field_api_admin_additional_fields_post | directly represented | Additional fields | /admin/configuration/additional-fields | X-Token | Tenant required | AdditionalFieldCreate | 201:AdditionalFieldOut, 422:HTTPValidationError | app/api/routers/additional_fields.py:117 | tests/test_booking_policies_remediation.py |
| 9 | DELETE | /api/admin/additional-fields/{field_id} | delete_additional_field_api_admin_additional_fields__field_id__delete | directly represented | Additional fields | /admin/configuration/additional-fields | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/additional_fields.py:147 | tests/test_booking_policies_remediation.py |
| 10 | PUT | /api/admin/additional-fields/{field_id} | update_additional_field_api_admin_additional_fields__field_id__put | directly represented | Additional fields | /admin/configuration/additional-fields | X-Token | Tenant required | AdditionalFieldUpdate | 200:AdditionalFieldOut, 422:HTTPValidationError | app/api/routers/additional_fields.py:130 | tests/test_booking_policies_remediation.py |
| 11 | GET | /api/admin/audit-log | list_audit_logs_api_admin_audit_log_get | directly represented | Audit | /admin/audit | X-Token | Tenant required | — | 200:AuditLogListResponse, 422:HTTPValidationError | app/api/routers/audit.py:22 | tests/test_audit_resolution.py |
| 12 | POST | /api/admin/audit-log | create_audit_log_api_admin_audit_log_post | directly represented | Audit | /admin/audit | X-Token | Tenant required | AuditLogCreate | 200:AuditLogResponse, 422:HTTPValidationError | app/api/routers/audit.py:35 | tests/test_audit_resolution.py |
| 13 | POST | /api/admin/auth | admin_login_api_admin_auth_post | directly represented | Authentication | /admin/login | Credentials exchange | Tenant required | AdminAuthRequest | 200:TokenResponse, 422:HTTPValidationError | app/api/routers/auth.py:47 | tests/test_audit_resolution.py, tests/test_multi_tenancy.py |
| 14 | GET | /api/admin/booking-forms | list_booking_forms_api_admin_booking_forms_get | directly represented | Booking-form administration | /admin/booking-forms | X-Token | Tenant required | — | 200:array&lt;BookingFormOut&gt;, 422:HTTPValidationError | app/api/routers/booking_forms.py:225 | tests/test_booking_form_contracts.py, tests/test_configurable_booking_forms.py |
| 15 | POST | /api/admin/booking-forms | create_booking_form_api_admin_booking_forms_post | directly represented | Booking-form administration | /admin/booking-forms | X-Token | Tenant required | BookingFormCreate | 201:BookingFormOut, 422:HTTPValidationError | app/api/routers/booking_forms.py:234 | tests/test_booking_form_contracts.py, tests/test_configurable_booking_forms.py |
| 16 | GET | /api/admin/booking-forms/configuration-catalogue | get_embed_configuration_catalogue_api_admin_booking_forms_configuration_catalogue_get | directly represented | Booking-form administration | /admin/booking-forms | X-Token | Tenant required | — | 200:FormCatalogueResponse, 422:HTTPValidationError | app/api/routers/booking_forms.py:220 | tests/test_booking_form_contracts.py, tests/test_configurable_booking_forms.py |
| 17 | DELETE | /api/admin/booking-forms/{form_id} | delete_booking_form_api_admin_booking_forms__form_id__delete | directly represented | Booking-form administration | /admin/booking-forms | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/booking_forms.py:295 | tests/test_booking_form_contracts.py, tests/test_configurable_booking_forms.py |
| 18 | GET | /api/admin/booking-forms/{form_id} | get_booking_form_api_admin_booking_forms__form_id__get | directly represented | Booking-form administration | /admin/booking-forms | X-Token | Tenant required | — | 200:BookingFormOut, 422:HTTPValidationError | app/api/routers/booking_forms.py:257; app/api/routers/forms.py:61 | tests/test_booking_form_contracts.py, tests/test_configurable_booking_forms.py |
| 19 | PUT | /api/admin/booking-forms/{form_id} | update_booking_form_api_admin_booking_forms__form_id__put | directly represented | Booking-form administration | /admin/booking-forms | X-Token | Tenant required | BookingFormUpdate | 200:BookingFormOut, 422:HTTPValidationError | app/api/routers/booking_forms.py:267 | tests/test_booking_form_contracts.py, tests/test_configurable_booking_forms.py |
| 20 | GET | /api/admin/booking-forms/{form_id}/design | get_booking_form_design_api_admin_booking_forms__form_id__design_get | directly represented | Booking-form administration | /admin/booking-forms | X-Token | Tenant required | — | 200:EmbedConfiguration, 422:HTTPValidationError | app/api/routers/booking_forms.py:344 | tests/test_booking_form_contracts.py, tests/test_configurable_booking_forms.py |
| 21 | PUT | /api/admin/booking-forms/{form_id}/design | update_booking_form_design_api_admin_booking_forms__form_id__design_put | directly represented | Booking-form administration | /admin/booking-forms | X-Token | Tenant required | EmbedConfigurationPatch | 200:EmbedConfiguration, 422:HTTPValidationError | app/api/routers/booking_forms.py:354 | tests/test_booking_form_contracts.py, tests/test_configurable_booking_forms.py |
| 22 | POST | /api/admin/booking-forms/{form_id}/duplicate | duplicate_booking_form_api_admin_booking_forms__form_id__duplicate_post | directly represented | Booking-form administration | /admin/booking-forms | X-Token | Tenant required | DuplicateBookingFormRequest | 201:BookingFormOut, 422:HTTPValidationError | app/api/routers/booking_forms.py:306 | tests/test_booking_form_contracts.py, tests/test_configurable_booking_forms.py |
| 23 | GET | /api/admin/booking-forms/{form_id}/embed | booking_form_embed_api_admin_booking_forms__form_id__embed_get | directly represented | Booking-form administration | /admin/booking-forms | X-Token | Tenant required | — | 200:FormEmbedResponse, 422:HTTPValidationError | app/api/routers/booking_forms.py:390 | tests/test_booking_form_contracts.py, tests/test_configurable_booking_forms.py |
| 24 | GET | /api/admin/booking-forms/{form_id}/preview | preview_booking_form_api_admin_booking_forms__form_id__preview_get | directly represented | Booking-form administration | /admin/booking-forms | X-Token | Tenant required | — | 200:FormPreviewResponse, 422:HTTPValidationError | app/api/routers/booking_forms.py:379 | tests/test_booking_form_contracts.py, tests/test_configurable_booking_forms.py |
| 25 | GET | /api/admin/bookings | list_bookings_api_admin_bookings_get | directly represented | Booking operations | /admin/bookings | X-Token | Tenant required | — | 200:BookingListResponse, 422:HTTPValidationError | app/api/routers/bookings.py:31 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py, tests/test_concurrency.py |
| 26 | POST | /api/admin/bookings | create_booking_api_admin_bookings_post | directly represented | Booking operations | /admin/bookings | X-Token | Tenant required | BookingCreate | 200:BookingResponse, 422:HTTPValidationError | app/api/routers/bookings.py:58 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py, tests/test_concurrency.py |
| 27 | GET | /api/admin/bookings/{booking_id} | get_booking_api_admin_bookings__booking_id__get | directly represented | Booking operations | /admin/bookings | X-Token | Tenant required | — | 200:BookingResponse, 422:HTTPValidationError | app/api/routers/bookings.py:193 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py, tests/test_concurrency.py |
| 28 | PUT | /api/admin/bookings/{booking_id} | update_booking_api_admin_bookings__booking_id__put | directly represented | Booking operations | /admin/bookings | X-Token | Tenant required | BookingUpdate | 200:BookingResponse, 422:HTTPValidationError | app/api/routers/bookings.py:202 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py, tests/test_concurrency.py |
| 29 | POST | /api/admin/bookings/{booking_id}/cancel | cancel_booking_api_admin_bookings__booking_id__cancel_post | directly represented | Booking operations | /admin/bookings | X-Token | Tenant required | — | 200:BookingResponse, 422:HTTPValidationError | app/api/routers/bookings.py:257 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py, tests/test_concurrency.py |
| 30 | POST | /api/admin/bookings/{booking_id}/complete | complete_booking_api_admin_bookings__booking_id__complete_post | directly represented | Booking operations | /admin/bookings | X-Token | Tenant required | — | 200:BookingResponse, 422:HTTPValidationError | app/api/routers/bookings.py:291 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py, tests/test_concurrency.py |
| 31 | POST | /api/admin/bookings/{booking_id}/confirm | confirm_booking_api_admin_bookings__booking_id__confirm_post | directly represented | Booking operations | /admin/bookings | X-Token | Tenant required | — | 200:BookingResponse, 422:HTTPValidationError | app/api/routers/bookings.py:229 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py, tests/test_concurrency.py |
| 32 | POST | /api/admin/bookings/{booking_id}/noshow | noshow_booking_api_admin_bookings__booking_id__noshow_post | directly represented | Booking operations | /admin/bookings | X-Token | Tenant required | — | 200:BookingResponse, 422:HTTPValidationError | app/api/routers/bookings.py:321 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py, tests/test_concurrency.py |
| 33 | POST | /api/admin/bookings/{booking_id}/reschedule | reschedule_booking_api_admin_bookings__booking_id__reschedule_post | directly represented | Booking operations | /admin/bookings | X-Token | Tenant required | BookingReschedule | 200:BookingResponse, 422:HTTPValidationError | app/api/routers/bookings.py:351 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py, tests/test_concurrency.py |
| 34 | GET | /api/admin/business-profile | get_business_profile_api_admin_business_profile_get | directly represented | Business profile | /admin/settings/business | X-Token | Tenant required | — | 200:BusinessProfileResponse, 422:HTTPValidationError | app/api/routers/business_profile.py:24 | No direct mapping asserted |
| 35 | PUT | /api/admin/business-profile | update_business_profile_api_admin_business_profile_put | directly represented | Business profile | /admin/settings/business | X-Token | Tenant required | BusinessProfileUpdate | 200:BusinessProfileResponse, 422:HTTPValidationError | app/api/routers/business_profile.py:33 | No direct mapping asserted |
| 36 | POST | /api/admin/business-profile/geocode | trigger_geocode_api_admin_business_profile_geocode_post | directly represented | Discovery | /discover | X-Token | Tenant required | — | 200:Response Trigger Geocode Api Admin Business Profile Geocode Post, 422:HTTPValidationError | app/api/routers/discovery.py:230 | No direct mapping asserted |
| 37 | GET | /api/admin/calendar-notes | list_calendar_notes_api_admin_calendar_notes_get | directly represented | Calendar | /admin/calendar | X-Token | Tenant required | — | 200:CalendarNoteListResponse, 422:HTTPValidationError | app/api/routers/calendar_notes.py:29 | No direct mapping asserted |
| 38 | POST | /api/admin/calendar-notes | create_calendar_note_api_admin_calendar_notes_post | directly represented | Calendar | /admin/calendar | X-Token | Tenant required | CalendarNoteCreate | 201:CalendarNoteResponse, 422:HTTPValidationError | app/api/routers/calendar_notes.py:49 | No direct mapping asserted |
| 39 | DELETE | /api/admin/calendar-notes/{note_id} | delete_calendar_note_api_admin_calendar_notes__note_id__delete | directly represented | Calendar | /admin/calendar | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/calendar_notes.py:91 | No direct mapping asserted |
| 40 | PUT | /api/admin/calendar-notes/{note_id} | update_calendar_note_api_admin_calendar_notes__note_id__put | directly represented | Calendar | /admin/calendar | X-Token | Tenant required | CalendarNoteUpdate | 200:CalendarNoteResponse, 422:HTTPValidationError | app/api/routers/calendar_notes.py:67 | No direct mapping asserted |
| 41 | GET | /api/admin/categories | list_categories_api_admin_categories_get | directly represented | Catalog / categories | /admin/catalog/categories | X-Token | Tenant required | — | 200:array&lt;CategoryOut&gt;, 422:HTTPValidationError | app/api/routers/categories.py:17 | tests/test_relationships_remediation.py |
| 42 | POST | /api/admin/categories | create_category_api_admin_categories_post | directly represented | Catalog / categories | /admin/catalog/categories | X-Token | Tenant required | CategoryCreate | 200:CategoryOut, 422:HTTPValidationError | app/api/routers/categories.py:27 | tests/test_relationships_remediation.py |
| 43 | DELETE | /api/admin/categories/{category_id} | delete_category_api_admin_categories__category_id__delete | directly represented | Catalog / categories | /admin/catalog/categories | X-Token | Tenant required | — | 200:CategoryOut, 422:HTTPValidationError | app/api/routers/categories.py:72 | tests/test_relationships_remediation.py |
| 44 | GET | /api/admin/categories/{category_id} | get_category_api_admin_categories__category_id__get | directly represented | Catalog / categories | /admin/catalog/categories | X-Token | Tenant required | — | 200:CategoryOut, 422:HTTPValidationError | app/api/routers/categories.py:41 | tests/test_relationships_remediation.py |
| 45 | PUT | /api/admin/categories/{category_id} | update_category_api_admin_categories__category_id__put | directly represented | Catalog / categories | /admin/catalog/categories | X-Token | Tenant required | CategoryUpdate | 200:CategoryOut, 422:HTTPValidationError | app/api/routers/categories.py:54 | tests/test_relationships_remediation.py |
| 46 | GET | /api/admin/categories/{record_id}/editor | category_editor_api_admin_categories__record_id__editor_get | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:RelationshipEditorResponse, 422:HTTPValidationError | app/api/routers/relationship_management.py:222 | tests/test_relationships_remediation.py |
| 47 | GET | /api/admin/clients | list_clients_api_admin_clients_get | directly represented | Client administration | /admin/clients | X-Token | Tenant required | — | 200:ClientListResponse, 422:HTTPValidationError | app/api/routers/clients.py:23 | No direct mapping asserted |
| 48 | POST | /api/admin/clients | create_client_api_admin_clients_post | directly represented | Client administration | /admin/clients | X-Token | Tenant required | ClientCreate | 200:ClientResponse, 422:HTTPValidationError | app/api/routers/clients.py:35 | No direct mapping asserted |
| 49 | DELETE | /api/admin/clients/{client_id} | delete_client_api_admin_clients__client_id__delete | directly represented | Client administration | /admin/clients | X-Token | Tenant required | — | 200:ClientResponse, 422:HTTPValidationError | app/api/routers/clients.py:80 | No direct mapping asserted |
| 50 | GET | /api/admin/clients/{client_id} | get_client_api_admin_clients__client_id__get | directly represented | Client administration | /admin/clients | X-Token | Tenant required | — | 200:ClientResponse, 422:HTTPValidationError | app/api/routers/clients.py:49 | No direct mapping asserted |
| 51 | PUT | /api/admin/clients/{client_id} | update_client_api_admin_clients__client_id__put | directly represented | Client administration | /admin/clients | X-Token | Tenant required | ClientUpdate | 200:ClientResponse, 422:HTTPValidationError | app/api/routers/clients.py:62 | No direct mapping asserted |
| 52 | GET | /api/admin/clients/{record_id}/editor | client_editor_api_admin_clients__record_id__editor_get | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:RelationshipEditorResponse, 422:HTTPValidationError | app/api/routers/relationship_management.py:232 | tests/test_relationships_remediation.py |
| 53 | GET | /api/admin/dashboard/bootstrap | admin_dashboard_bootstrap_api_admin_dashboard_bootstrap_get | directly represented | Dashboard | /admin | X-Token | Tenant required | — | 200:Response Admin Dashboard Bootstrap Api Admin Dashboard Bootstrap Get, 422:HTTPValidationError | app/api/routers/admin_dashboard.py:26 | No direct mapping asserted |
| 54 | GET | /api/admin/gdpr-consents | list_gdpr_consents_api_admin_gdpr_consents_get | directly represented | System and compliance | /admin/system | X-Token | Tenant required | — | 200:GdprConsentListResponse, 422:HTTPValidationError | app/api/routers/general_systems.py:105 | No direct mapping asserted |
| 55 | GET | /api/admin/gdpr-consents/{client_id} | list_gdpr_consents_for_client_api_admin_gdpr_consents__client_id__get | directly represented | System and compliance | /admin/system | X-Token | Tenant required | — | 200:GdprConsentListResponse, 422:HTTPValidationError | app/api/routers/general_systems.py:112 | No direct mapping asserted |
| 56 | GET | /api/admin/invoices | list_admin_invoices_api_admin_invoices_get | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | — | 200:InvoiceListResponse, 422:HTTPValidationError | app/api/routers/checkout.py:312 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 57 | GET | /api/admin/invoices/{invoice_id} | get_admin_invoice_api_admin_invoices__invoice_id__get | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | — | 200:InvoiceResponse, 422:HTTPValidationError | app/api/routers/checkout.py:322 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 58 | PUT | /api/admin/invoices/{invoice_id}/status | update_invoice_status_api_admin_invoices__invoice_id__status_put | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | InvoiceStatusUpdate | 200:InvoiceResponse, 422:HTTPValidationError | app/api/routers/checkout.py:338 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 59 | GET | /api/admin/locations | list_locations_api_admin_locations_get | directly represented | Catalog / locations | /admin/catalog/locations | X-Token | Tenant required | — | 200:LocationListResponse, 422:HTTPValidationError | app/api/routers/locations.py:22 | tests/test_relationships_remediation.py |
| 60 | POST | /api/admin/locations | create_location_api_admin_locations_post | directly represented | Catalog / locations | /admin/catalog/locations | X-Token | Tenant required | LocationCreate | 200:LocationResponse, 422:HTTPValidationError | app/api/routers/locations.py:34 | tests/test_relationships_remediation.py |
| 61 | DELETE | /api/admin/locations/{location_id} | delete_location_api_admin_locations__location_id__delete | directly represented | Catalog / locations | /admin/catalog/locations | X-Token | Tenant required | — | 200:LocationResponse, 422:HTTPValidationError | app/api/routers/locations.py:79 | tests/test_relationships_remediation.py |
| 62 | GET | /api/admin/locations/{location_id} | get_location_api_admin_locations__location_id__get | directly represented | Catalog / locations | /admin/catalog/locations | X-Token | Tenant required | — | 200:LocationResponse, 422:HTTPValidationError | app/api/routers/locations.py:48 | tests/test_relationships_remediation.py |
| 63 | PUT | /api/admin/locations/{location_id} | update_location_api_admin_locations__location_id__put | directly represented | Catalog / locations | /admin/catalog/locations | X-Token | Tenant required | LocationUpdate | 200:LocationResponse, 422:HTTPValidationError | app/api/routers/locations.py:61 | tests/test_relationships_remediation.py |
| 64 | GET | /api/admin/locations/{location_id}/categories | list_location_categories_api_admin_locations__location_id__categories_get | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:array&lt;CategoryOut&gt;, 422:HTTPValidationError | app/api/routers/location_relations.py:237 | tests/test_relationships_remediation.py |
| 65 | DELETE | /api/admin/locations/{location_id}/categories/{category_id} | unlink_location_category_api_admin_locations__location_id__categories__category_id__delete | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:Response Unlink Location Category Api Admin Locations  Location Id  Categories  Category Id  Delete, 422:HTTPValidationError | app/api/routers/location_relations.py:215 | tests/test_relationships_remediation.py |
| 66 | POST | /api/admin/locations/{location_id}/categories/{category_id} | link_location_category_api_admin_locations__location_id__categories__category_id__post | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 201:Response Link Location Category Api Admin Locations  Location Id  Categories  Category Id  Post, 422:HTTPValidationError | app/api/routers/location_relations.py:184 | tests/test_relationships_remediation.py |
| 67 | GET | /api/admin/locations/{location_id}/providers | list_location_providers_api_admin_locations__location_id__providers_get | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:array&lt;Provider&gt;, 422:HTTPValidationError | app/api/routers/location_relations.py:85 | tests/test_relationships_remediation.py |
| 68 | DELETE | /api/admin/locations/{location_id}/providers/{provider_id} | unlink_location_provider_api_admin_locations__location_id__providers__provider_id__delete | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:Response Unlink Location Provider Api Admin Locations  Location Id  Providers  Provider Id  Delete, 422:HTTPValidationError | app/api/routers/location_relations.py:63 | tests/test_relationships_remediation.py |
| 69 | POST | /api/admin/locations/{location_id}/providers/{provider_id} | link_location_provider_api_admin_locations__location_id__providers__provider_id__post | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 201:Response Link Location Provider Api Admin Locations  Location Id  Providers  Provider Id  Post, 422:HTTPValidationError | app/api/routers/location_relations.py:28 | tests/test_relationships_remediation.py |
| 70 | GET | /api/admin/locations/{location_id}/services | list_location_services_api_admin_locations__location_id__services_get | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:array&lt;Service&gt;, 422:HTTPValidationError | app/api/routers/location_relations.py:161 | tests/test_relationships_remediation.py |
| 71 | DELETE | /api/admin/locations/{location_id}/services/{service_id} | unlink_location_service_api_admin_locations__location_id__services__service_id__delete | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:Response Unlink Location Service Api Admin Locations  Location Id  Services  Service Id  Delete, 422:HTTPValidationError | app/api/routers/location_relations.py:139 | tests/test_relationships_remediation.py |
| 72 | POST | /api/admin/locations/{location_id}/services/{service_id} | link_location_service_api_admin_locations__location_id__services__service_id__post | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 201:Response Link Location Service Api Admin Locations  Location Id  Services  Service Id  Post, 422:HTTPValidationError | app/api/routers/location_relations.py:108 | tests/test_relationships_remediation.py |
| 73 | GET | /api/admin/locations/{record_id}/editor | location_editor_api_admin_locations__record_id__editor_get | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:RelationshipEditorResponse, 422:HTTPValidationError | app/api/routers/relationship_management.py:217 | tests/test_relationships_remediation.py |
| 74 | GET | /api/admin/management-reviews | list_review_requests_api_admin_management_reviews_get | directly represented | Management reviews | /admin/reviews | X-Token | Tenant required | — | 200:ManagementReviewRequestListResponse, 422:HTTPValidationError | app/api/routers/management_reviews.py:110 | No direct mapping asserted |
| 75 | GET | /api/admin/management-reviews/{review_id} | get_review_request_api_admin_management_reviews__review_id__get | directly represented | Management reviews | /admin/reviews | X-Token | Tenant required | — | 200:ManagementReviewRequestResponse, 422:HTTPValidationError | app/api/routers/management_reviews.py:123 | No direct mapping asserted |
| 76 | PUT | /api/admin/management-reviews/{review_id}/resolve | resolve_review_request_api_admin_management_reviews__review_id__resolve_put | directly represented | Management reviews | /admin/reviews | X-Token | Tenant required | ManagementReviewRequestUpdate | 200:ManagementReviewRequestResponse, 422:HTTPValidationError | app/api/routers/management_reviews.py:137 | No direct mapping asserted |
| 77 | GET | /api/admin/notification-templates | list_notification_templates_api_admin_notification_templates_get | directly represented | Notification templates | /admin/notifications/templates | X-Token | Tenant required | — | 200:NotificationTemplateListResponse, 422:HTTPValidationError | app/api/routers/notifications.py:92 | tests/test_notification_configs.py |
| 78 | POST | /api/admin/notification-templates | create_notification_template_api_admin_notification_templates_post | directly represented | Notification templates | /admin/notifications/templates | X-Token | Tenant required | NotificationTemplateCreate | 200:NotificationTemplateResponse, 422:HTTPValidationError | app/api/routers/notifications.py:105 | tests/test_notification_configs.py |
| 79 | DELETE | /api/admin/notification-templates/{template_id} | delete_notification_template_api_admin_notification_templates__template_id__delete | directly represented | Notification templates | /admin/notifications/templates | X-Token | Tenant required | — | 200:NotificationTemplateResponse, 422:HTTPValidationError | app/api/routers/notifications.py:158 | tests/test_notification_configs.py |
| 80 | PUT | /api/admin/notification-templates/{template_id} | update_notification_template_api_admin_notification_templates__template_id__put | directly represented | Notification templates | /admin/notifications/templates | X-Token | Tenant required | NotificationTemplateUpdate | 200:NotificationTemplateResponse, 422:HTTPValidationError | app/api/routers/notifications.py:129 | tests/test_notification_configs.py |
| 81 | GET | /api/admin/notifications | list_notifications_api_admin_notifications_get | directly represented | Notifications | /admin/notifications/messages | X-Token | Tenant required | — | 200:NotificationListResponse, 422:HTTPValidationError | app/api/routers/notifications.py:38 | No direct mapping asserted |
| 82 | POST | /api/admin/notifications | create_notification_api_admin_notifications_post | directly represented | Notifications | /admin/notifications/messages | X-Token | Tenant required | NotificationCreate | 200:NotificationResponse, 422:HTTPValidationError | app/api/routers/notifications.py:51 | No direct mapping asserted |
| 83 | PUT | /api/admin/notifications/{notification_id} | update_notification_api_admin_notifications__notification_id__put | directly represented | Notifications | /admin/notifications/messages | X-Token | Tenant required | NotificationUpdate | 200:NotificationResponse, 422:HTTPValidationError | app/api/routers/notifications.py:68 | No direct mapping asserted |
| 84 | GET | /api/admin/packages | list_packages_api_admin_packages_get | directly represented | Catalog / packages | /admin/catalog/packages | X-Token | Tenant required | — | 200:array&lt;PackageOut&gt;, 422:HTTPValidationError | app/api/routers/packages.py:23 | No direct mapping asserted |
| 85 | POST | /api/admin/packages | create_package_api_admin_packages_post | directly represented | Catalog / packages | /admin/catalog/packages | X-Token | Tenant required | PackageCreate | 200:PackageOut, 422:HTTPValidationError | app/api/routers/packages.py:32 | No direct mapping asserted |
| 86 | DELETE | /api/admin/packages/steps/{step_id} | delete_package_step_api_admin_packages_steps__step_id__delete | directly represented | Catalog / packages | /admin/catalog/packages | X-Token | Tenant required | — | 200:PackageStepOut, 422:HTTPValidationError | app/api/routers/packages.py:123 | No direct mapping asserted |
| 87 | PUT | /api/admin/packages/steps/{step_id} | update_package_step_api_admin_packages_steps__step_id__put | directly represented | Catalog / packages | /admin/catalog/packages | X-Token | Tenant required | PackageStepUpdate | 200:PackageStepOut, 422:HTTPValidationError | app/api/routers/packages.py:106 | No direct mapping asserted |
| 88 | DELETE | /api/admin/packages/{package_id} | delete_package_api_admin_packages__package_id__delete | directly represented | Catalog / packages | /admin/catalog/packages | X-Token | Tenant required | — | 200:PackageOut, 422:HTTPValidationError | app/api/routers/packages.py:74 | No direct mapping asserted |
| 89 | GET | /api/admin/packages/{package_id} | get_package_api_admin_packages__package_id__get | directly represented | Catalog / packages | /admin/catalog/packages | X-Token | Tenant required | — | 200:PackageOut, 422:HTTPValidationError | app/api/routers/packages.py:45 | No direct mapping asserted |
| 90 | PUT | /api/admin/packages/{package_id} | update_package_api_admin_packages__package_id__put | directly represented | Catalog / packages | /admin/catalog/packages | X-Token | Tenant required | PackageUpdate | 200:PackageOut, 422:HTTPValidationError | app/api/routers/packages.py:57 | No direct mapping asserted |
| 91 | POST | /api/admin/packages/{package_id}/steps | add_package_step_api_admin_packages__package_id__steps_post | directly represented | Catalog / packages | /admin/catalog/packages | X-Token | Tenant required | PackageStepCreate | 200:PackageStepOut, 422:HTTPValidationError | app/api/routers/packages.py:88 | No direct mapping asserted |
| 92 | GET | /api/admin/payment-processor/configs | list_payment_processor_configs_api_admin_payment_processor_configs_get | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | — | 200:array&lt;PaymentProcessorConfigOut&gt;, 422:HTTPValidationError | app/api/routers/checkout.py:492 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 93 | POST | /api/admin/payment-processor/configs | create_payment_processor_config_api_admin_payment_processor_configs_post | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | PaymentProcessorConfigCreate | 201:PaymentProcessorConfigOut, 422:HTTPValidationError | app/api/routers/checkout.py:501 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 94 | PUT | /api/admin/payment-processor/configs/{config_id} | update_payment_processor_config_api_admin_payment_processor_configs__config_id__put | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | PaymentProcessorConfigUpdate | 200:PaymentProcessorConfigOut, 422:HTTPValidationError | app/api/routers/checkout.py:517 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 95 | GET | /api/admin/payments | list_payments_api_admin_payments_get | directly represented | Payments | /admin/finance/payments | X-Token | Tenant required | — | 200:PaymentListResponse, 422:HTTPValidationError | app/api/routers/payments.py:23 | No direct mapping asserted |
| 96 | POST | /api/admin/payments | create_payment_api_admin_payments_post | directly represented | Payments | /admin/finance/payments | X-Token | Tenant required | PaymentCreate | 200:PaymentResponse, 422:HTTPValidationError | app/api/routers/payments.py:36 | No direct mapping asserted |
| 97 | PUT | /api/admin/payments/{payment_id} | update_payment_api_admin_payments__payment_id__put | directly represented | Payments | /admin/finance/payments | X-Token | Tenant required | PaymentUpdate | 200:PaymentResponse, 422:HTTPValidationError | app/api/routers/payments.py:58 | No direct mapping asserted |
| 98 | GET | /api/admin/plugin-states | list_plugin_states_api_admin_plugin_states_get | directly represented | System and compliance | /admin/system | X-Token | Tenant required | — | 200:PluginStateListResponse, 422:HTTPValidationError | app/api/routers/general_systems.py:33 | No direct mapping asserted |
| 99 | POST | /api/admin/plugin-states | upsert_plugin_state_api_admin_plugin_states_post | directly represented | System and compliance | /admin/system | X-Token | Tenant required | PluginStateCreate | 201:PluginStateResponse, 422:HTTPValidationError | app/api/routers/general_systems.py:40 | No direct mapping asserted |
| 100 | PUT | /api/admin/plugin-states/{name} | toggle_plugin_state_api_admin_plugin_states__name__put | directly represented | System and compliance | /admin/system | X-Token | Tenant required | PluginStateUpdate | 200:PluginStateResponse, 422:HTTPValidationError | app/api/routers/general_systems.py:60 | No direct mapping asserted |
| 101 | GET | /api/admin/products | list_products_api_admin_products_get | directly represented | Catalog / products | /admin/catalog/products | X-Token | Tenant required | — | 200:array&lt;ProductOut&gt;, 422:HTTPValidationError | app/api/routers/products.py:24 | No direct mapping asserted |
| 102 | POST | /api/admin/products | create_product_api_admin_products_post | directly represented | Catalog / products | /admin/catalog/products | X-Token | Tenant required | ProductCreate | 200:ProductOut, 422:HTTPValidationError | app/api/routers/products.py:34 | No direct mapping asserted |
| 103 | POST | /api/admin/products/assign | assign_product_to_service_api_admin_products_assign_post | directly represented | Catalog / products | /admin/catalog/products | X-Token | Tenant required | ServiceProductBase | 200:ServiceProductOut, 422:HTTPValidationError | app/api/routers/products.py:103 | No direct mapping asserted |
| 104 | DELETE | /api/admin/products/{product_id} | delete_product_api_admin_products__product_id__delete | directly represented | Catalog / products | /admin/catalog/products | X-Token | Tenant required | — | 200:ProductOut, 422:HTTPValidationError | app/api/routers/products.py:88 | No direct mapping asserted |
| 105 | GET | /api/admin/products/{product_id} | get_product_api_admin_products__product_id__get | directly represented | Catalog / products | /admin/catalog/products | X-Token | Tenant required | — | 200:ProductOut, 422:HTTPValidationError | app/api/routers/products.py:52 | No direct mapping asserted |
| 106 | PUT | /api/admin/products/{product_id} | update_product_api_admin_products__product_id__put | directly represented | Catalog / products | /admin/catalog/products | X-Token | Tenant required | ProductUpdate | 200:ProductOut, 422:HTTPValidationError | app/api/routers/products.py:65 | No direct mapping asserted |
| 107 | GET | /api/admin/products/{record_id}/editor | product_editor_api_admin_products__record_id__editor_get | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:RelationshipEditorResponse, 422:HTTPValidationError | app/api/routers/relationship_management.py:227 | tests/test_relationships_remediation.py |
| 108 | GET | /api/admin/promotions | list_promotions_api_admin_promotions_get | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | — | 200:array&lt;PromotionCodeOut&gt;, 422:HTTPValidationError | app/api/routers/checkout.py:361 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 109 | POST | /api/admin/promotions | create_promotion_api_admin_promotions_post | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | PromotionCodeCreate | 201:PromotionCodeOut, 422:HTTPValidationError | app/api/routers/checkout.py:370 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 110 | DELETE | /api/admin/promotions/{promotion_id} | delete_promotion_api_admin_promotions__promotion_id__delete | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/checkout.py:412 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 111 | PUT | /api/admin/promotions/{promotion_id} | update_promotion_api_admin_promotions__promotion_id__put | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | PromotionCodeUpdate | 200:PromotionCodeOut, 422:HTTPValidationError | app/api/routers/checkout.py:391 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 112 | GET | /api/admin/providers | list_providers_api_admin_providers_get | directly represented | Catalog / providers | /admin/catalog/providers | X-Token | Tenant required | — | 200:ProviderListResponse, 422:HTTPValidationError | app/api/routers/providers.py:23 | tests/test_relationships_remediation.py |
| 113 | POST | /api/admin/providers | create_provider_api_admin_providers_post | directly represented | Catalog / providers | /admin/catalog/providers | X-Token | Tenant required | ProviderCreate | 200:ProviderResponse, 422:HTTPValidationError | app/api/routers/providers.py:36 | tests/test_relationships_remediation.py |
| 114 | DELETE | /api/admin/providers/{provider_id} | delete_provider_api_admin_providers__provider_id__delete | directly represented | Catalog / providers | /admin/catalog/providers | X-Token | Tenant required | — | 200:ProviderResponse, 422:HTTPValidationError | app/api/routers/providers.py:94 | tests/test_relationships_remediation.py |
| 115 | GET | /api/admin/providers/{provider_id} | get_provider_api_admin_providers__provider_id__get | directly represented | Catalog / providers | /admin/catalog/providers | X-Token | Tenant required | — | 200:ProviderResponse, 422:HTTPValidationError | app/api/routers/providers.py:53 | tests/test_relationships_remediation.py |
| 116 | PUT | /api/admin/providers/{provider_id} | update_provider_api_admin_providers__provider_id__put | directly represented | Catalog / providers | /admin/catalog/providers | X-Token | Tenant required | ProviderUpdate | 200:ProviderResponse, 422:HTTPValidationError | app/api/routers/providers.py:71 | tests/test_relationships_remediation.py |
| 117 | GET | /api/admin/providers/{record_id}/editor | provider_editor_api_admin_providers__record_id__editor_get | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:RelationshipEditorResponse, 422:HTTPValidationError | app/api/routers/relationship_management.py:207 | tests/test_relationships_remediation.py |
| 118 | POST | /api/admin/public/bookings | create_public_booking_api_admin_public_bookings_post | indirectly used by another workflow | Booking operations | /admin/bookings | X-Token | Tenant required | BookingCreate | 200:BookingResponse, 422:HTTPValidationError | app/api/routers/bookings.py:139; app/api/routers/public_bookings.py:23 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py, tests/test_concurrency.py |
| 119 | GET | /api/admin/relationships/{left_type}/{left_id}/{right_type} | list_explicit_relationships_api_admin_relationships__left_type___left_id___right_type__get | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:RelationshipListResponse, 422:HTTPValidationError | app/api/routers/relationship_management.py:83 | tests/test_relationships_remediation.py |
| 120 | POST | /api/admin/relationships/{left_type}/{left_id}/{right_type}/create-and-connect | create_and_connect_api_admin_relationships__left_type___left_id___right_type__create_and_connect_post | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | CreateAndConnectRequest | 201:RelationshipLinkResponse, 422:HTTPValidationError | app/api/routers/relationship_management.py:143 | tests/test_relationships_remediation.py |
| 121 | DELETE | /api/admin/relationships/{left_type}/{left_id}/{right_type}/{right_id} | unlink_records_api_admin_relationships__left_type___left_id___right_type___right_id__delete | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/relationship_management.py:124 | tests/test_relationships_remediation.py |
| 122 | POST | /api/admin/relationships/{left_type}/{left_id}/{right_type}/{right_id} | link_records_api_admin_relationships__left_type___left_id___right_type___right_id__post | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 201:RelationshipLinkResponse, 422:HTTPValidationError | app/api/routers/relationship_management.py:100 | tests/test_relationships_remediation.py |
| 123 | GET | /api/admin/reminder-rules | list_reminder_rules_api_admin_reminder_rules_get | directly represented | Reminder rules | /admin/notifications/reminders | X-Token | Tenant required | — | 200:ReminderRuleListResponse, 422:HTTPValidationError | app/api/routers/notifications.py:179 | tests/test_notification_configs.py |
| 124 | POST | /api/admin/reminder-rules | create_reminder_rule_api_admin_reminder_rules_post | directly represented | Reminder rules | /admin/notifications/reminders | X-Token | Tenant required | ReminderRuleCreate | 200:ReminderRuleResponse, 422:HTTPValidationError | app/api/routers/notifications.py:192 | tests/test_notification_configs.py |
| 125 | DELETE | /api/admin/reminder-rules/{rule_id} | delete_reminder_rule_api_admin_reminder_rules__rule_id__delete | directly represented | Reminder rules | /admin/notifications/reminders | X-Token | Tenant required | — | 200:ReminderRuleResponse, 422:HTTPValidationError | app/api/routers/notifications.py:231 | tests/test_notification_configs.py |
| 126 | PUT | /api/admin/reminder-rules/{rule_id} | update_reminder_rule_api_admin_reminder_rules__rule_id__put | directly represented | Reminder rules | /admin/notifications/reminders | X-Token | Tenant required | ReminderRuleUpdate | 200:ReminderRuleResponse, 422:HTTPValidationError | app/api/routers/notifications.py:209 | tests/test_notification_configs.py |
| 127 | GET | /api/admin/resources | list_resources_api_admin_resources_get | directly represented | Resources | /admin/resources | X-Token | Tenant required | — | 200:array&lt;ResourceOut&gt;, 422:HTTPValidationError | app/api/routers/resources.py:23 | No direct mapping asserted |
| 128 | POST | /api/admin/resources | create_resource_api_admin_resources_post | directly represented | Resources | /admin/resources | X-Token | Tenant required | ResourceCreate | 200:ResourceOut, 422:HTTPValidationError | app/api/routers/resources.py:33 | No direct mapping asserted |
| 129 | POST | /api/admin/resources/requirements | create_service_resource_requirement_api_admin_resources_requirements_post | directly represented | Resources | /admin/resources | X-Token | Tenant required | ServiceResourceRequirementCreate | 200:ServiceResourceRequirementOut, 422:HTTPValidationError | app/api/routers/resources.py:104 | No direct mapping asserted |
| 130 | DELETE | /api/admin/resources/{resource_id} | delete_resource_api_admin_resources__resource_id__delete | directly represented | Resources | /admin/resources | X-Token | Tenant required | — | 200:ResourceOut, 422:HTTPValidationError | app/api/routers/resources.py:86 | No direct mapping asserted |
| 131 | GET | /api/admin/resources/{resource_id} | get_resource_api_admin_resources__resource_id__get | directly represented | Resources | /admin/resources | X-Token | Tenant required | — | 200:ResourceOut, 422:HTTPValidationError | app/api/routers/resources.py:49 | No direct mapping asserted |
| 132 | PUT | /api/admin/resources/{resource_id} | update_resource_api_admin_resources__resource_id__put | directly represented | Resources | /admin/resources | X-Token | Tenant required | ResourceUpdate | 200:ResourceOut, 422:HTTPValidationError | app/api/routers/resources.py:65 | No direct mapping asserted |
| 133 | GET | /api/admin/schedule/blocked-times | list_blocked_times_api_admin_schedule_blocked_times_get | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | — | 200:array&lt;BlockedTimeOut&gt;, 422:HTTPValidationError | app/api/routers/admin_schedule.py:202 | No direct mapping asserted |
| 134 | POST | /api/admin/schedule/blocked-times | create_blocked_time_api_admin_schedule_blocked_times_post | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | BlockedTimeCreate | 201:BlockedTimeOut, 422:HTTPValidationError | app/api/routers/admin_schedule.py:210 | No direct mapping asserted |
| 135 | DELETE | /api/admin/schedule/blocked-times/{block_id} | delete_blocked_time_api_admin_schedule_blocked_times__block_id__delete | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/admin_schedule.py:251 | No direct mapping asserted |
| 136 | PUT | /api/admin/schedule/blocked-times/{block_id} | update_blocked_time_api_admin_schedule_blocked_times__block_id__put | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | BlockedTimeUpdate | 200:BlockedTimeOut, 422:HTTPValidationError | app/api/routers/admin_schedule.py:227 | No direct mapping asserted |
| 137 | GET | /api/admin/schedule/reserved-times | list_reserved_times_api_admin_schedule_reserved_times_get | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | — | 200:array&lt;ReservedTimeOut&gt;, 422:HTTPValidationError | app/api/routers/admin_schedule.py:267 | No direct mapping asserted |
| 138 | POST | /api/admin/schedule/reserved-times | create_reserved_time_api_admin_schedule_reserved_times_post | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | ReservedTimeCreate | 201:ReservedTimeOut, 422:HTTPValidationError | app/api/routers/admin_schedule.py:275 | No direct mapping asserted |
| 139 | DELETE | /api/admin/schedule/reserved-times/{reserved_id} | delete_reserved_time_api_admin_schedule_reserved_times__reserved_id__delete | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/admin_schedule.py:316 | No direct mapping asserted |
| 140 | PUT | /api/admin/schedule/reserved-times/{reserved_id} | update_reserved_time_api_admin_schedule_reserved_times__reserved_id__put | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | ReservedTimeUpdate | 200:ReservedTimeOut, 422:HTTPValidationError | app/api/routers/admin_schedule.py:292 | No direct mapping asserted |
| 141 | GET | /api/admin/schedule/special-days | list_special_days_api_admin_schedule_special_days_get | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | — | 200:array&lt;ProviderSpecialDayOut&gt;, 422:HTTPValidationError | app/api/routers/admin_schedule.py:133 | No direct mapping asserted |
| 142 | POST | /api/admin/schedule/special-days | create_special_day_api_admin_schedule_special_days_post | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | ProviderSpecialDayCreate | 201:ProviderSpecialDayOut, 422:HTTPValidationError | app/api/routers/admin_schedule.py:142 | No direct mapping asserted |
| 143 | DELETE | /api/admin/schedule/special-days/{day_id} | delete_special_day_api_admin_schedule_special_days__day_id__delete | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/admin_schedule.py:186 | No direct mapping asserted |
| 144 | PUT | /api/admin/schedule/special-days/{day_id} | update_special_day_api_admin_schedule_special_days__day_id__put | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | ProviderSpecialDayUpdate | 200:ProviderSpecialDayOut, 422:HTTPValidationError | app/api/routers/admin_schedule.py:160 | No direct mapping asserted |
| 145 | GET | /api/admin/schedule/workdays | list_workdays_api_admin_schedule_workdays_get | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | — | 200:array&lt;ProviderWorkDayOut&gt;, 422:HTTPValidationError | app/api/routers/admin_schedule.py:65 | No direct mapping asserted |
| 146 | POST | /api/admin/schedule/workdays | create_workday_api_admin_schedule_workdays_post | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | ProviderWorkDayCreate | 201:ProviderWorkDayOut, 422:HTTPValidationError | app/api/routers/admin_schedule.py:74 | No direct mapping asserted |
| 147 | DELETE | /api/admin/schedule/workdays/{workday_id} | delete_workday_api_admin_schedule_workdays__workday_id__delete | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/admin_schedule.py:117 | No direct mapping asserted |
| 148 | PUT | /api/admin/schedule/workdays/{workday_id} | update_workday_api_admin_schedule_workdays__workday_id__put | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | ProviderWorkDayUpdate | 200:ProviderWorkDayOut, 422:HTTPValidationError | app/api/routers/admin_schedule.py:92 | No direct mapping asserted |
| 149 | GET | /api/admin/schedule/workload | get_workload_api_admin_schedule_workload_get | directly represented | Schedule | /admin/calendar | X-Token | Tenant required | — | 200:WorkloadSummary, 422:HTTPValidationError | app/api/routers/admin_schedule.py:332 | No direct mapping asserted |
| 150 | GET | /api/admin/series | list_series_api_admin_series_get | directly represented | Booking series | /admin/bookings | X-Token | Tenant required | — | 200:array&lt;BookingSeriesOut&gt;, 422:HTTPValidationError | app/api/routers/series.py:17 | No direct mapping asserted |
| 151 | POST | /api/admin/series | create_series_api_admin_series_post | directly represented | Booking series | /admin/bookings | X-Token | Tenant required | BookingSeriesCreate | 200:BookingSeriesOut, 422:HTTPValidationError | app/api/routers/series.py:27 | No direct mapping asserted |
| 152 | GET | /api/admin/series/{series_id} | get_series_api_admin_series__series_id__get | directly represented | Booking series | /admin/bookings | X-Token | Tenant required | — | 200:BookingSeriesOut, 422:HTTPValidationError | app/api/routers/series.py:43 | No direct mapping asserted |
| 153 | GET | /api/admin/services | list_services_api_admin_services_get | directly represented | Catalog / services | /admin/catalog/services | X-Token | Tenant required | — | 200:ServiceListResponse, 422:HTTPValidationError | app/api/routers/services.py:23 | tests/test_multi_tenancy.py, tests/test_scheduling_constraints.py |
| 154 | POST | /api/admin/services | create_service_api_admin_services_post | directly represented | Catalog / services | /admin/catalog/services | X-Token | Tenant required | ServiceCreate | 200:ServiceResponse, 422:HTTPValidationError | app/api/routers/services.py:36 | tests/test_multi_tenancy.py, tests/test_scheduling_constraints.py |
| 155 | GET | /api/admin/services/{record_id}/editor | service_editor_api_admin_services__record_id__editor_get | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:RelationshipEditorResponse, 422:HTTPValidationError | app/api/routers/relationship_management.py:212 | tests/test_relationships_remediation.py |
| 156 | DELETE | /api/admin/services/{service_id} | delete_service_api_admin_services__service_id__delete | directly represented | Catalog / services | /admin/catalog/services | X-Token | Tenant required | — | 200:ServiceResponse, 422:HTTPValidationError | app/api/routers/services.py:94 | tests/test_multi_tenancy.py, tests/test_scheduling_constraints.py |
| 157 | GET | /api/admin/services/{service_id} | get_service_api_admin_services__service_id__get | directly represented | Catalog / services | /admin/catalog/services | X-Token | Tenant required | — | 200:ServiceResponse, 422:HTTPValidationError | app/api/routers/services.py:53 | tests/test_multi_tenancy.py, tests/test_scheduling_constraints.py |
| 158 | PUT | /api/admin/services/{service_id} | update_service_api_admin_services__service_id__put | directly represented | Catalog / services | /admin/catalog/services | X-Token | Tenant required | ServiceUpdate | 200:ServiceResponse, 422:HTTPValidationError | app/api/routers/services.py:71 | tests/test_multi_tenancy.py, tests/test_scheduling_constraints.py |
| 159 | GET | /api/admin/services/{service_id}/categories | list_service_categories_api_admin_services__service_id__categories_get | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:array&lt;CategoryOut&gt;, 422:HTTPValidationError | app/api/routers/service_relations.py:86 | tests/test_relationships_remediation.py |
| 160 | DELETE | /api/admin/services/{service_id}/categories/{category_id} | unassign_category_from_service_api_admin_services__service_id__categories__category_id__delete | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/service_relations.py:120 | tests/test_relationships_remediation.py |
| 161 | POST | /api/admin/services/{service_id}/categories/{category_id} | assign_category_to_service_api_admin_services__service_id__categories__category_id__post | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/service_relations.py:98 | tests/test_relationships_remediation.py |
| 162 | GET | /api/admin/services/{service_id}/providers | list_service_providers_api_admin_services__service_id__providers_get | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 200:array&lt;Provider&gt;, 422:HTTPValidationError | app/api/routers/service_relations.py:33 | tests/test_relationships_remediation.py |
| 163 | DELETE | /api/admin/services/{service_id}/providers/{provider_id} | unassign_provider_from_service_api_admin_services__service_id__providers__provider_id__delete | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/service_relations.py:67 | tests/test_relationships_remediation.py |
| 164 | POST | /api/admin/services/{service_id}/providers/{provider_id} | assign_provider_to_service_api_admin_services__service_id__providers__provider_id__post | directly represented | Relationship editor | /admin/relationships | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/service_relations.py:45 | tests/test_relationships_remediation.py |
| 165 | POST | /api/admin/system/cleanup | run_historic_cleanup_api_admin_system_cleanup_post | directly represented | System maintenance | /admin/system | X-Token | Tenant required | — | 200:Response Run Historic Cleanup Api Admin System Cleanup Post, 422:HTTPValidationError | app/api/routers/system.py:15 | tests/test_retention_remediation.py |
| 166 | POST | /api/admin/system/clients/{client_id}/anonymize | anonymize_client_record_api_admin_system_clients__client_id__anonymize_post | directly represented | System maintenance | /admin/system | X-Token | Tenant required | — | 200:Response Anonymize Client Record Api Admin System Clients  Client Id  Anonymize Post, 422:HTTPValidationError | app/api/routers/system.py:30 | tests/test_retention_remediation.py |
| 167 | GET | /api/admin/system/diagnostics | get_system_diagnostics_api_admin_system_diagnostics_get | directly represented | System and compliance | /admin/system | X-Token | Tenant required | — | 200:DiagnosticsResponse, 422:HTTPValidationError | app/api/routers/diagnostics.py:59 | No direct mapping asserted |
| 168 | GET | /api/admin/tax-rates | list_tax_rates_api_admin_tax_rates_get | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | — | 200:array&lt;TaxRateOut&gt;, 422:HTTPValidationError | app/api/routers/checkout.py:429 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 169 | POST | /api/admin/tax-rates | create_tax_rate_api_admin_tax_rates_post | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | TaxRateCreate | 201:TaxRateOut, 422:HTTPValidationError | app/api/routers/checkout.py:438 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 170 | DELETE | /api/admin/tax-rates/{tax_rate_id} | delete_tax_rate_api_admin_tax_rates__tax_rate_id__delete | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/checkout.py:475 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 171 | PUT | /api/admin/tax-rates/{tax_rate_id} | update_tax_rate_api_admin_tax_rates__tax_rate_id__put | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | TaxRateUpdate | 200:TaxRateOut, 422:HTTPValidationError | app/api/routers/checkout.py:454 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 172 | POST | /api/admin/users | create_user_api_admin_users_post | directly represented | Authentication | /admin/login | X-Token | Tenant required | UserCreate | 200:UserResponse, 422:HTTPValidationError | app/api/routers/auth.py:97 | tests/test_audit_resolution.py, tests/test_multi_tenancy.py |
| 173 | GET | /api/admin/webhooks | list_webhooks_api_admin_webhooks_get | directly represented | Webhooks | /admin/settings/webhooks | X-Token | Tenant required | — | 200:WebhookListResponse, 422:HTTPValidationError | app/api/routers/webhooks.py:42 | No direct mapping asserted |
| 174 | POST | /api/admin/webhooks | create_webhook_api_admin_webhooks_post | directly represented | Webhooks | /admin/settings/webhooks | X-Token | Tenant required | WebhookCreate | 201:WebhookResponse, 422:HTTPValidationError | app/api/routers/webhooks.py:49 | No direct mapping asserted |
| 175 | GET | /api/admin/webhooks/events | list_supported_events_api_admin_webhooks_events_get | directly represented | Webhooks | /admin/settings/webhooks | X-Token | Tenant required | — | 200:Response List Supported Events Api Admin Webhooks Events Get, 422:HTTPValidationError | app/api/routers/webhooks.py:102 | No direct mapping asserted |
| 176 | DELETE | /api/admin/webhooks/{webhook_id} | delete_webhook_api_admin_webhooks__webhook_id__delete | directly represented | Webhooks | /admin/settings/webhooks | X-Token | Tenant required | — | 204:—, 422:HTTPValidationError | app/api/routers/webhooks.py:88 | No direct mapping asserted |
| 177 | PUT | /api/admin/webhooks/{webhook_id} | update_webhook_api_admin_webhooks__webhook_id__put | directly represented | Webhooks | /admin/settings/webhooks | X-Token | Tenant required | WebhookUpdate | 200:WebhookResponse, 422:HTTPValidationError | app/api/routers/webhooks.py:68 | No direct mapping asserted |
| 178 | GET | /api/discovery/map | discovery_map_api_discovery_map_get | directly represented | Discovery | /discover | No X-Token declared | No tenant for global/system route | — | 200:array&lt;TenantMapPin&gt;, 422:HTTPValidationError | app/api/routers/discovery.py:129 | No direct mapping asserted |
| 179 | GET | /api/discovery/services | discovery_services_api_discovery_services_get | directly represented | Discovery | /discover | No X-Token declared | No tenant for global/system route | — | 200:array&lt;ServiceOption&gt; | app/api/routers/discovery.py:203 | No direct mapping asserted |
| 180 | GET | /api/forms/booking | get_booking_form_api_forms_booking_get | indirectly used by another workflow | Generated form metadata | /book/:formSlug/details | No X-Token declared | Verify route implementation | — | 200:FormSchemaResponse | app/api/routers/booking_forms.py:257; app/api/routers/forms.py:61 | No direct mapping asserted |
| 181 | GET | /api/forms/provider | get_provider_form_api_forms_provider_get | indirectly used by another workflow | Generated form metadata | /book/:formSlug/details | No X-Token declared | Verify route implementation | — | 200:FormSchemaResponse | app/api/routers/forms.py:47 | No direct mapping asserted |
| 182 | GET | /api/forms/service | get_service_form_api_forms_service_get | indirectly used by another workflow | Generated form metadata | /book/:formSlug/details | No X-Token declared | Verify route implementation | — | 200:FormSchemaResponse | app/api/routers/forms.py:32 | No direct mapping asserted |
| 183 | POST | /api/public/additional-field-responses | submit_public_additional_field_responses_api_public_additional_field_responses_post | directly represented | Additional fields | /admin/configuration/additional-fields | X-Token | Tenant required | AdditionalFieldSubmitRequest | 200:array&lt;AdditionalFieldResponseOut&gt;, 422:HTTPValidationError | app/api/routers/additional_fields.py:76 | tests/test_booking_policies_remediation.py |
| 184 | GET | /api/public/additional-fields | list_public_additional_fields_api_public_additional_fields_get | directly represented | Additional fields | /admin/configuration/additional-fields | X-Token | Tenant required | — | 200:array&lt;AdditionalFieldOut&gt;, 422:HTTPValidationError | app/api/routers/additional_fields.py:48 | tests/test_booking_policies_remediation.py |
| 185 | POST | /api/public/auth/token | public_login_api_public_auth_token_post | indirectly used by another workflow | Authentication | /admin/login | Server-side API-key exchange (BFF) | Tenant required | PublicAuthRequest | 200:TokenResponse, 422:HTTPValidationError | app/api/routers/auth.py:73 | tests/test_audit_resolution.py, tests/test_multi_tenancy.py |
| 186 | GET | /api/public/availability | availability_api_public_availability_get | directly represented | Public availability | /book/:formSlug | X-Token | Tenant required | — | 200:Response Availability Api Public Availability Get, 422:HTTPValidationError | app/api/routers/availability.py:20 | tests/test_scheduling_constraints.py, tests/test_scheduling_intervals.py |
| 187 | GET | /api/public/booking-forms/{slug} | get_widget_form_api_public_booking_forms__slug__get | directly represented | Public booking form | /book/:formSlug | X-Token | Tenant required | — | 200:WidgetFormResponse, 422:HTTPValidationError | app/api/routers/booking_forms.py:400 | tests/test_configurable_booking_forms.py, tests/test_embed_configuration.py |
| 188 | POST | /api/public/booking-forms/{slug}/availability | widget_availability_api_public_booking_forms__slug__availability_post | directly represented | Public booking form | /book/:formSlug | X-Token | Tenant required | AvailabilityRequest | 200:WidgetAvailabilityResponse, 422:HTTPValidationError | app/api/routers/booking_forms.py:460 | tests/test_configurable_booking_forms.py, tests/test_embed_configuration.py |
| 189 | POST | /api/public/booking-forms/{slug}/bookings | create_widget_booking_api_public_booking_forms__slug__bookings_post | directly represented | Public booking form | /book/:formSlug | X-Token | Tenant required | WidgetBookingRequest | 201:BookingResponse, 422:HTTPValidationError | app/api/routers/booking_forms.py:475 | tests/test_configurable_booking_forms.py, tests/test_embed_configuration.py |
| 190 | GET | /api/public/booking-forms/{slug}/embed-config | widget_embed_config_api_public_booking_forms__slug__embed_config_get | indirectly used by another workflow | Public booking form | /book/:formSlug | X-Token | Tenant required | — | 200:FormEmbedResponse, 422:HTTPValidationError | app/api/routers/booking_forms.py:543 | tests/test_configurable_booking_forms.py, tests/test_embed_configuration.py |
| 191 | POST | /api/public/booking-forms/{slug}/resolve | resolve_widget_form_api_public_booking_forms__slug__resolve_post | directly represented | Public booking form | /book/:formSlug | X-Token | Tenant required | ResolveRequest | 200:WidgetResolveResponse, 422:HTTPValidationError | app/api/routers/booking_forms.py:406 | tests/test_configurable_booking_forms.py, tests/test_embed_configuration.py |
| 192 | GET | /api/public/booking-forms/{slug}/runtime-manifest | booking_surface_runtime_manifest_api_public_booking_forms__slug__runtime_manifest_get | indirectly used by another workflow | Public booking form | /book/:formSlug | X-Token | Tenant required | — | 200:WidgetRuntimeManifestResponse, 422:HTTPValidationError | app/api/routers/booking_forms.py:526 | tests/test_configurable_booking_forms.py, tests/test_embed_configuration.py |
| 193 | POST | /api/public/bookings | create_public_booking_api_public_bookings_post | directly represented | Public booking | /book/:formSlug/outcome | X-Token | Tenant required | BookingCreate | 200:BookingResponse, 422:HTTPValidationError | app/api/routers/bookings.py:139; app/api/routers/public_bookings.py:23 | No direct mapping asserted |
| 194 | GET | /api/public/bootstrap | public_bootstrap_api_public_bootstrap_get | indirectly used by another workflow | Public booking bootstrap | /book/:formSlug | X-Token | Tenant required | — | 200:PublicBootstrapResponse, 422:HTTPValidationError | app/api/routers/public_bootstrap.py:43 | tests/test_public_entities_remediation.py |
| 195 | GET | /api/public/business-profile | get_public_business_profile_api_public_business_profile_get | directly represented | Business profile | /admin/settings/business | X-Token | Tenant required | — | 200:PublicBusinessProfileResponse, 422:HTTPValidationError | app/api/routers/business_profile.py:72 | No direct mapping asserted |
| 196 | GET | /api/public/categories | list_public_categories_api_public_categories_get | deprecated | Compatibility/system | N/A | X-Token | Tenant required | — | 200:array&lt;CategoryOut&gt;, 422:HTTPValidationError | app/api/routers/public_entities.py:57 | tests/test_public_entities_remediation.py |
| 197 | POST | /api/public/checkout/commit | checkout_commit_api_public_checkout_commit_post | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | CheckoutCommitRequest | 200:CheckoutCommitResponse, 422:HTTPValidationError | app/api/routers/checkout.py:539 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 198 | POST | /api/public/clients | create_public_client_contact_api_public_clients_post | directly represented | Client account | /client/register | No X-Token declared | Tenant required | ClientCreate | 200:ClientResponse, 422:HTTPValidationError | app/api/routers/public_clients.py:59 | tests/test_multi_tenancy.py |
| 199 | POST | /api/public/clients/identify | identify_or_create_client_api_public_clients_identify_post | directly represented | Client account | /client/profile | No X-Token declared | Tenant required | — | 200:ClientIdentifyResponse, 422:HTTPValidationError | app/api/routers/public_clients.py:76 | tests/test_multi_tenancy.py |
| 200 | POST | /api/public/clients/login | login_client_api_public_clients_login_post | directly represented | Client account | /client/login | No X-Token declared | Tenant required | PublicClientLogin | 200:ClientAuthResponse, 422:HTTPValidationError | app/api/routers/public_clients.py:156 | tests/test_multi_tenancy.py |
| 201 | GET | /api/public/clients/me | get_my_profile_api_public_clients_me_get | directly represented | Client account | /client/profile | No X-Token declared | Tenant required | — | 200:ClientResponse, 422:HTTPValidationError | app/api/routers/public_clients.py:178 | tests/test_multi_tenancy.py |
| 202 | PUT | /api/public/clients/me | update_my_profile_api_public_clients_me_put | directly represented | Client account | /client/profile | No X-Token declared | Tenant required | PublicClientProfileUpdate | 200:ClientResponse, 422:HTTPValidationError | app/api/routers/public_clients.py:184 | tests/test_multi_tenancy.py |
| 203 | POST | /api/public/clients/password-reset/request | request_password_reset_api_public_clients_password_reset_request_post | directly represented | Client account | /client/password-reset | No X-Token declared | Tenant required | PublicClientLogin | 200:Response Request Password Reset Api Public Clients Password Reset Request Post, 422:HTTPValidationError | app/api/routers/public_clients.py:198 | tests/test_multi_tenancy.py |
| 204 | POST | /api/public/clients/register | register_client_api_public_clients_register_post | directly represented | Client account | /client/register | No X-Token declared | Tenant required | PublicClientRegister | 200:ClientAuthResponse, 422:HTTPValidationError | app/api/routers/public_clients.py:116 | tests/test_multi_tenancy.py |
| 205 | GET | /api/public/clients/terms | get_client_terms_api_public_clients_terms_get | directly represented | Client account | /client/terms | No X-Token declared | Tenant required | — | 200:Response Get Client Terms Api Public Clients Terms Get | app/api/routers/public_clients.py:213 | tests/test_multi_tenancy.py |
| 206 | POST | /api/public/gdpr-consent | record_gdpr_consent_api_public_gdpr_consent_post | directly represented | Client consent | /client/terms | No X-Token declared | Tenant required | GdprConsentCreate | 201:GdprConsentResponse, 422:HTTPValidationError | app/api/routers/general_systems.py:79 | No direct mapping asserted |
| 207 | POST | /api/public/holds | create_hold_endpoint_api_public_holds_post | directly represented | Public booking hold | /book/:formSlug/checkout | X-Token | Tenant required | HoldCreate | 200:HoldOut, 422:HTTPValidationError | app/api/routers/holds.py:31 | tests/test_audit_fixes.py, tests/test_concurrency.py |
| 208 | DELETE | /api/public/holds/{hold_id} | cancel_hold_endpoint_api_public_holds__hold_id__delete | directly represented | Public booking hold | /book/:formSlug/checkout | X-Token | Tenant required | — | 200:HoldOut, 422:HTTPValidationError | app/api/routers/holds.py:188 | tests/test_audit_fixes.py, tests/test_concurrency.py |
| 209 | POST | /api/public/holds/{hold_id}/confirm | confirm_hold_endpoint_api_public_holds__hold_id__confirm_post | directly represented | Public booking hold | /book/:formSlug/checkout | X-Token | Tenant required | Payload | 200:BookingResponse, 422:HTTPValidationError | app/api/routers/holds.py:69 | tests/test_audit_fixes.py, tests/test_concurrency.py |
| 210 | POST | /api/public/invoices | create_public_invoice_api_public_invoices_post | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | InvoiceCreate | 200:InvoiceResponse, 422:HTTPValidationError | app/api/routers/checkout.py:222 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 211 | GET | /api/public/invoices/{invoice_id} | get_public_invoice_api_public_invoices__invoice_id__get | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | — | 200:InvoiceResponse, 422:HTTPValidationError | app/api/routers/checkout.py:273 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 212 | POST | /api/public/invoices/{invoice_id}/tips | add_public_tip_api_public_invoices__invoice_id__tips_post | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | TipCreate | 200:TipOut, 422:HTTPValidationError | app/api/routers/checkout.py:288 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 213 | GET | /api/public/locations | list_public_locations_api_public_locations_get | deprecated | Compatibility/system | N/A | X-Token | Tenant required | — | 200:array&lt;Location&gt;, 422:HTTPValidationError | app/api/routers/public_entities.py:80 | tests/test_public_entities_remediation.py |
| 214 | POST | /api/public/management-reviews | submit_review_request_api_public_management_reviews_post | directly represented | Management reviews | /admin/reviews | X-Token | Tenant required | ManagementReviewRequestCreate | 200:ManagementReviewRequestResponse, 422:HTTPValidationError | app/api/routers/management_reviews.py:32 | No direct mapping asserted |
| 215 | GET | /api/public/payment-methods | public_payment_methods_api_public_payment_methods_get | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | — | 200:Response Public Payment Methods Api Public Payment Methods Get, 422:HTTPValidationError | app/api/routers/checkout.py:200 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 216 | GET | /api/public/payment-processor/config | public_payment_processor_config_api_public_payment_processor_config_get | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | — | 200:Response Public Payment Processor Config Api Public Payment Processor Config Get, 422:HTTPValidationError | app/api/routers/checkout.py:188 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 217 | GET | /api/public/promotions/{code}/validate | public_validate_promotion_api_public_promotions__code__validate_get | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | — | 200:PromotionValidationResponse, 422:HTTPValidationError | app/api/routers/checkout.py:212 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 218 | GET | /api/public/providers | list_public_providers_api_public_providers_get | deprecated | Compatibility/system | N/A | X-Token | Tenant required | — | 200:ProviderListResponse, 422:HTTPValidationError | app/api/routers/public_entities.py:43 | tests/test_public_entities_remediation.py |
| 219 | POST | /api/public/quote | create_quote_api_public_quote_post | directly represented | Checkout and finance | /admin/finance/invoices | X-Token | Tenant required | QuoteRequest | 200:QuoteResponse, 422:HTTPValidationError | app/api/routers/checkout.py:178 | tests/test_audit_fixes.py, tests/test_booking_policies_remediation.py |
| 220 | POST | /api/public/search-availability | search_availability_api_public_search_availability_post | directly represented | Public availability | /book/:formSlug | X-Token | Tenant required | AvailabilitySearchQuery | 200:SearchAvailabilityResponse, 422:HTTPValidationError | app/api/routers/search.py:77 | tests/test_audit_resolution.py, tests/test_security_fuzzing.py |
| 221 | GET | /api/public/services | list_public_services_api_public_services_get | deprecated | Compatibility/system | N/A | X-Token | Tenant required | — | 200:ServiceListResponse, 422:HTTPValidationError | app/api/routers/public_entities.py:29 | tests/test_public_entities_remediation.py |
| 222 | GET | /api/public/services/{service_id}/intake-form | get_public_service_intake_form_api_public_services__service_id__intake_form_get | directly represented | Additional fields | /admin/configuration/additional-fields | X-Token | Tenant required | — | 200:array&lt;AdditionalFieldOut&gt;, 422:HTTPValidationError | app/api/routers/additional_fields.py:62 | tests/test_booking_policies_remediation.py |
| 223 | GET | /api/public/timeline/first-available-day | get_first_available_day_api_public_timeline_first_available_day_get | directly represented | Public availability | /book/:formSlug | No X-Token declared | Tenant required | — | 200:Response Get First Available Day Api Public Timeline First Available Day Get, 422:HTTPValidationError | app/api/routers/public_timeline.py:86 | tests/test_scheduling_edge_cases.py, tests/test_scheduling_intervals.py |
| 224 | GET | /api/public/timeline/schedule/{provider_id} | get_provider_schedule_api_public_timeline_schedule__provider_id__get | directly represented | Public availability | /book/:formSlug | No X-Token declared | Tenant required | — | 200:Response Get Provider Schedule Api Public Timeline Schedule  Provider Id  Get, 422:HTTPValidationError | app/api/routers/public_timeline.py:29 | tests/test_scheduling_edge_cases.py, tests/test_scheduling_intervals.py |
| 225 | GET | /api/public/timeline/slots | get_available_slots_api_public_timeline_slots_get | directly represented | Public availability | /book/:formSlug | No X-Token declared | Tenant required | — | 200:Response Get Available Slots Api Public Timeline Slots Get, 422:HTTPValidationError | app/api/routers/public_timeline.py:57 | tests/test_scheduling_edge_cases.py, tests/test_scheduling_intervals.py |
| 226 | GET | /api/public/ui-config | get_public_ui_config_api_public_ui_config_get | deprecated | Compatibility/system | N/A | X-Token | Tenant required | — | 200:PublicUIConfigResponse, 422:HTTPValidationError | app/api/routers/ui_config.py:55 | No direct mapping asserted |
| 227 | GET | /api/public/ui-config/admin | get_admin_ui_config_api_public_ui_config_admin_get | deprecated | Compatibility/system | N/A | X-Token | Tenant required | — | 200:AdminUIConfigResponse, 422:HTTPValidationError | app/api/routers/ui_config.py:80 | No direct mapping asserted |
| 228 | GET | /api/public/waitlist | list_waitlist_api_public_waitlist_get | directly represented | Public waitlist | /book/:formSlug/outcome | X-Token | Tenant required | — | 200:array&lt;WaitlistOut&gt;, 422:HTTPValidationError | app/api/routers/waitlist.py:59 | tests/test_concurrency.py, tests/test_scheduling_edge_cases.py |
| 229 | POST | /api/public/waitlist | add_to_waitlist_api_public_waitlist_post | directly represented | Public waitlist | /book/:formSlug/outcome | X-Token | Tenant required | WaitlistCreate | 200:WaitlistOut, 422:HTTPValidationError | app/api/routers/waitlist.py:22 | tests/test_concurrency.py, tests/test_scheduling_edge_cases.py |
| 230 | POST | /api/v1/checkout/deposit-session | create_deposit_session_api_v1_checkout_deposit_session_post | directly represented | Payment integration | /admin/finance/payments | No X-Token declared | Verify route implementation | — | 200:Response Create Deposit Session Api V1 Checkout Deposit Session Post, 422:HTTPValidationError | app/api/routers/stripe_webhooks.py:25 | tests/test_phase_5_6_7.py |
| 231 | POST | /api/v1/devices/register | register_device_api_v1_devices_register_post | indirectly used by another workflow | Notification device registration | /admin/notifications/messages | No X-Token declared | Verify route implementation | DeviceTokenCreate | 200:DeviceTokenResponse, 422:HTTPValidationError | app/api/routers/devices.py:12 | tests/test_phase_5_6_7.py |
| 232 | POST | /api/v1/webhooks/stripe | stripe_webhook_api_v1_webhooks_stripe_post | administrative or system-only | Compatibility/system | N/A | Stripe signature/webhook policy | No browser consumer | — | 200:WebhookAckResponse | app/api/routers/stripe_webhooks.py:46 | tests/test_phase_5_6_7.py |
| 233 | GET | /health | health_health_get | administrative or system-only | System health | N/A (monitoring/CI) | No X-Token declared | No tenant for global/system route | — | 200:Response Health Health Get | app/main.py or generated route; exact function lookup unresolved | No direct mapping asserted |
| 234 | GET | /notification-templates | list_notification_templates_notification_templates_get | intentionally excluded | Compatibility/system | N/A | X-Token | Verify route implementation | — | 200:NotificationTemplateListResponse, 422:HTTPValidationError | app/main.py or generated route; exact function lookup unresolved | tests/test_notification_configs.py |
| 235 | POST | /notification-templates | create_notification_template_notification_templates_post | intentionally excluded | Compatibility/system | N/A | X-Token | Verify route implementation | NotificationTemplateCreate | 200:NotificationTemplateResponse, 422:HTTPValidationError | app/main.py or generated route; exact function lookup unresolved | tests/test_notification_configs.py |
| 236 | DELETE | /notification-templates/{template_id} | delete_notification_template_notification_templates__template_id__delete | intentionally excluded | Compatibility/system | N/A | X-Token | Verify route implementation | — | 200:NotificationTemplateResponse, 422:HTTPValidationError | app/main.py or generated route; exact function lookup unresolved | tests/test_notification_configs.py |
| 237 | PUT | /notification-templates/{template_id} | update_notification_template_notification_templates__template_id__put | intentionally excluded | Compatibility/system | N/A | X-Token | Verify route implementation | NotificationTemplateUpdate | 200:NotificationTemplateResponse, 422:HTTPValidationError | app/main.py or generated route; exact function lookup unresolved | tests/test_notification_configs.py |
| 238 | GET | /notifications | list_notifications_notifications_get | intentionally excluded | Compatibility/system | N/A | X-Token | Verify route implementation | — | 200:NotificationListResponse, 422:HTTPValidationError | app/api/routers/notifications.py:38 | No direct mapping asserted |
| 239 | POST | /notifications | create_notification_notifications_post | intentionally excluded | Compatibility/system | N/A | X-Token | Verify route implementation | NotificationCreate | 200:NotificationResponse, 422:HTTPValidationError | app/api/routers/notifications.py:51 | No direct mapping asserted |
| 240 | PUT | /notifications/{notification_id} | update_notification_notifications__notification_id__put | intentionally excluded | Compatibility/system | N/A | X-Token | Verify route implementation | NotificationUpdate | 200:NotificationResponse, 422:HTTPValidationError | app/main.py or generated route; exact function lookup unresolved | No direct mapping asserted |
| 241 | GET | /ready | readiness_ready_get | administrative or system-only | System health | N/A (monitoring/CI) | No X-Token declared | No tenant for global/system route | — | 200:Response Readiness Ready Get | app/main.py or generated route; exact function lookup unresolved | No direct mapping asserted |
| 242 | GET | /reminder-rules | list_reminder_rules_reminder_rules_get | intentionally excluded | Compatibility/system | N/A | X-Token | Verify route implementation | — | 200:ReminderRuleListResponse, 422:HTTPValidationError | app/main.py or generated route; exact function lookup unresolved | tests/test_notification_configs.py |
| 243 | POST | /reminder-rules | create_reminder_rule_reminder_rules_post | intentionally excluded | Compatibility/system | N/A | X-Token | Verify route implementation | ReminderRuleCreate | 200:ReminderRuleResponse, 422:HTTPValidationError | app/main.py or generated route; exact function lookup unresolved | tests/test_notification_configs.py |
| 244 | DELETE | /reminder-rules/{rule_id} | delete_reminder_rule_reminder_rules__rule_id__delete | intentionally excluded | Compatibility/system | N/A | X-Token | Verify route implementation | — | 200:ReminderRuleResponse, 422:HTTPValidationError | app/main.py or generated route; exact function lookup unresolved | tests/test_notification_configs.py |
| 245 | PUT | /reminder-rules/{rule_id} | update_reminder_rule_reminder_rules__rule_id__put | intentionally excluded | Compatibility/system | N/A | X-Token | Verify route implementation | ReminderRuleUpdate | 200:ReminderRuleResponse, 422:HTTPValidationError | app/main.py or generated route; exact function lookup unresolved | tests/test_notification_configs.py |
| 246 | GET | /version | version_version_get | administrative or system-only | System health | N/A (monitoring/CI) | No X-Token declared | No tenant for global/system route | — | 200:Response Version Version Get | app/main.py or generated route; exact function lookup unresolved | No direct mapping asserted |
