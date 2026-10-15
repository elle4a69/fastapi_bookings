# Handoff Brief: Native SaaS Control Plane — Logto + Flexprice

## Objective
Implement a secure, production-grade SaaS control plane for FastAPI Bookings using:
- **Logto** for authentication, organization-aware identity, invitations, MFA, RBAC, and enterprise SSO.
- **Flexprice** for subscription lifecycle, plans, usage metering, credits, invoicing, and paid-feature entitlements.
- **FastAPI Bookings** as the continuing authoritative system for tenants, internal users, memberships, roles, bookings, customer data, domain operations, and audit history.

Logto is MPL-2.0 and provides organizations, RBAC, invitations, MFA, and enterprise SSO. Flexprice provides subscriptions, usage metering, credits, invoices, and feature access controls, but is AGPL-3.0/open-core and has substantial infrastructure requirements. [Logto](https://github.com/logto-io/logto), [Flexprice](https://github.com/flexprice/flexprice).

This is not a rewrite of FastAPI Bookings, Chatwoot, or the operational finance subsystem.

## Mandatory Preconditions
Before implementation begins:
1. Obtain explicit legal approval for:
   - Logto MPL-2.0.
   - Flexprice AGPL-3.0 and its open-core commercial components.
   - Any modifications, embedding, hosted distribution, or internal fork strategy.
2. Obtain user-provided sandbox credentials and approved test configuration for:
   - A self-hosted Logto environment.
   - A self-hosted Flexprice environment.
   - A payment processor only if Flexprice payment collection is in scope.
3. Confirm the initial commercial model:
   - Flat plan, per-seat plan, usage-based plan, credits, or hybrid.
   - Trial policy.
   - Grace-period, past-due, suspension, and cancellation policy.
   - Whether Flexprice will send invoices only or also initiate payment collection.
4. Do not use production secrets, real customer data, live payment methods, real SMS, or real bookings during implementation or verification.

## Source-of-Truth Rules
| Domain | Authoritative system |
| :--- | :--- |
| Internal tenant ID and lifecycle | FastAPI Bookings |
| Internal users, tenant memberships, domain roles | FastAPI Bookings |
| Credentials, login sessions, MFA, SAML/OIDC connections | Logto |
| Logto external identity and organization IDs | Mapped to FastAPI records; never replace internal IDs |
| Plans, subscription calculations, usage aggregation, credit balances | Flexprice |
| Runtime paid-access decision | FastAPI local entitlement projection |
| Booking/customer operational invoices and payments | Existing FastAPI Bookings finance domain |
| Platform subscription invoices | Flexprice only |
| Audit trail for platform actions | FastAPI Bookings immutable audit records |

- Never trust a browser-supplied tenant ID, Logto organization ID, Flexprice customer ID, plan ID, or entitlement claim without verifying its mapping to the authenticated internal tenant.
- Never permit a tenant owner to directly write `subscription_tier`, `enabled_modules`, paid quotas, or entitlement state.

## Architecture
```text
React frontend
  │
  ├── Logto sign-in / MFA / enterprise SSO
  │
  ▼
FastAPI authentication boundary
  ├── verify Logto JWT locally
  ├── map external subject → internal user
  ├── map external organization → internal tenant
  └── enforce local tenant membership and roles
  │
  ▼
FastAPI Bookings domain
  ├── tenants, users, memberships, bookings
  ├── local billing/entitlement projections
  ├── usage event outbox
  ├── provider webhook inbox
  └── immutable audit records
  │               ▲
  ├── provision/sync ───────┤
  ▼                         │
Logto                    Flexprice
identity & orgs          plans, subscriptions, metering, credits, invoices, entitlements
```

Every provider event must flow through a verified, persisted, idempotent event inbox before changing local state. Background workers must always carry an explicit internal `tenant_id`.

## Non-Negotiable Security and Scope Constraints
1. Fix the current public tenant-creation/first-owner takeover path before exposing any commercial onboarding.
2. No mock implementations, hardcoded billing state, fake checkout success, artificial timers, or disconnected scaffolding.
3. Do not reuse tenant customer invoices/payments for platform subscriptions.
4. Do not store raw payment-card data.
5. Do not create new public routes merely to make a UI work.
6. Do not make Chatwoot a source of truth for users, tenants, roles, subscriptions, or entitlements.
7. Do not use Logto organization membership alone as authorization; FastAPI must verify a local internal membership.
8. Do not allow Flexprice outage or stale client state to grant unauthorised paid features.
9. Do not delete tenant data on cancellation. Implement soft suspension, retention, export, and separately authorised deletion workflows.
10. Do not add an identity/billing provider database as a direct dependency of FastAPI. Use official APIs, signed webhooks, local projections, and reconciliation.

## Required Work Packages

### WP0 — Security baseline and control-plane contract
**Goal**: Remove the unsafe tenant-creation and direct-tier-mutation paths before adding providers.
- **Expected areas**:
  - `app/api/routers/tenants.py`
  - `app/api/routers/auth.py`
  - `app/api/routers/tenant_modules.py`
  - `app/api/deps.py`
  - `app/models/tenant.py`
  - Relevant schemas, tests, and module READMEs.
- **Deliverables**:
  - Separate `platform_owner` capability that is not equivalent to a tenant owner.
  - Tenant creation and cross-tenant lookup protected by the platform-control-plane boundary.
  - Remove "first authenticated Google user becomes tenant owner."
  - Introduce durable initial-owner invitation/acceptance flow.
  - Disable direct owner-driven subscription-tier mutation.
  - Record all platform tenant lifecycle actions in immutable audit records.
  - Document the ownership model in an ADR.
- **Acceptance criteria**:
  - Anonymous users cannot create, read, suspend, or alter tenants.
  - First tenant owner is provisioned only through a verified invitation or platform-approved workflow.
  - Tenant owners cannot self-upgrade by manipulating APIs.
  - Three-tenant isolation tests pass.
  - Targeted security, auth, role-hierarchy, and tenant isolation suites pass.

### WP1 — Logto foundation
**Goal**: Establish Logto as identity infrastructure without replacing internal tenant authority.
- **Expected new module boundary**:
  - `app/services/identity/`
  - `app/api/routers/identity/`
  - `app/models/external_identity.py`
  - Corresponding Alembic migration, schemas, tests, and README.
- **Required models**:
  - `ExternalIdentityLink`: provider name, external subject ID, internal `user_id`, timestamps, uniqueness constraints.
  - `ExternalOrganizationLink`: provider name, Logto organization ID, internal `tenant_id`, provisioning state, timestamps, uniqueness constraints.
  - `TenantInvitation`: tenant scope, intended role, inviter, expiry, accepted/revoked state, idempotency key.
- **Required workflows**:
  - Platform-authorized tenant provisioning creates the internal tenant transactionally.
  - An outbox event provisions or links the corresponding Logto organization.
  - The founding owner accepts a verified invitation.
  - FastAPI exchanges/validates Logto identity and links it to an internal user.
  - FastAPI maps Logto organization context to an internal tenant only after local membership verification.
  - Internal memberships/roles remain authoritative even if Logto org metadata drifts.
- **Logto capabilities**:
  - Password/social/OIDC sign-in as approved.
  - MFA for privileged roles.
  - Organization invitations.
  - Organization-aware tokens.
  - Enterprise SAML/OIDC only when an approved tenant requires it.
  - Do not introduce SCIM in this phase.
- **Acceptance criteria**:
  - A user can authenticate through Logto and access only linked internal tenants.
  - A user with multiple organisations cannot switch into an unlinked tenant.
  - Revoked membership blocks API access immediately according to defined session policy.
  - Tenant creation and provider provisioning are retry-safe and idempotent.
  - No Logto secrets or raw token values appear in logs, errors, telemetry, or frontend state.

### WP2 — Flexprice billing adapter and subscription projection
**Goal**: Integrate Flexprice as the SaaS billing engine while retaining a FastAPI-local projection.
- **Expected new module boundary**:
  - `app/services/platform_billing/`
  - `app/api/routers/platform_billing.py`
  - `app/api/routers/flexprice_webhooks.py`
  - `app/models/platform_billing.py`
  - Dedicated migrations, schemas, tests, and README.
- **Required models**:
  - `BillingAccount`: internal `tenant_id`, Flexprice customer ID, billing state, no payment credentials.
  - `SubscriptionProjection`: tenant scope, external subscription ID, plan/version, status, trial/current period/cancel-at dates, provider version/event ordering details.
  - `EntitlementSnapshot`: tenant scope, entitlement key, value/limit, effective/expiry time, source subscription and version, local enforcement status.
  - `ProviderEventInbox`: provider name, external event ID, raw-event digest only (not unrestricted sensitive payload logging), verified timestamp, processing state, retry/error metadata, unique `(provider, external_event_id)`.
  - `UsageEventOutbox`: tenant scope, stable idempotency key, meter key, quantity, occurred-at, delivery state.
- **Required behaviours**:
  - Flexprice products/plans created via approved admin or documented infrastructure workflows.
  - Tenant owner can request checkout/portal access, but cannot directly change plan state.
  - Webhooks preserve raw body for signature verification, verify signatures before parsing, persist a single event-inbox record, and return quickly.
  - Event handlers tolerate duplicate, delayed, and out-of-order delivery.
  - Local subscription and entitlement projections update transactionally.
  - Reconciliation worker compares local projections with Flexprice at defined cadence.
  - Provider outages follow an explicit grace/fail-closed policy.
- **Acceptance criteria**:
  - Duplicate webhook events change entitlement state once only.
  - Out-of-order events cannot resurrect cancelled subscriptions.
  - Client-side plan/price manipulation attempts cannot change subscription state.
  - Flexprice outage does not grant elevated access.
  - Tenant A cannot inspect or affect Tenant B's subscription, metering, credits, or portal session.

### WP3 — Entitlements, quotas, and usage metering
**Goal**: Make paid access real, tenant-scoped, and enforceable.
- **Refactor or replace**:
  - `app/api/routers/tenant_modules.py`
  - `app/models/tenant.py`
  - `frontend/src/context/tenant-modules-context.tsx`
  - Existing paid-module/navigation controls.
- **Rules**:
  - Entitlement keys must be stable business identifiers, never raw Flexprice plan IDs.
  - Feature flags may restrict a purchased feature for rollout; they may never grant an unpurchased feature.
  - Usage events need stable idempotency keys.
  - Quota enforcement happens server-side before protected work begins.
  - Usage must not double-count retries or failed tasks.
  - Tenant-specific grants must be explicit, expiring, platform-authorised, and audited.
  - Initial catalogue: `assistant.enabled`, `assistant.monthly_runs`, `sms.enabled`, `sms.monthly_outbound_messages`, `providers.max`, `locations.max`, `api.enabled`.

### WP4 — Tenant-facing and platform-facing UX
**Goal**: Expose only real, authenticated workflows.
- **Tenant-facing "Plan & Billing" page**:
  - Current plan and status.
  - Included limits and current usage.
  - Checkout or billing-portal action.
  - Past-due/grace messaging.
  - No direct tier-edit API.
  - No payment details handled by frontend.
- **Platform operator console**:
  - Tenant billing status and entitlement diagnostics.
  - Explicit, audited support grants/overrides with expiry.
  - Subscription reconciliation status.
  - Provider event processing failures.
  - No impersonation by default.
  - Distinct from `frontend/src/pages/admin/finance/`.

### WP5 — Operational hardening and release gates
**Goal**: Make integration supportable in production.
- **Deliverables**:
  - Deployment topology for Logto and Flexprice with backing dependencies.
  - Backup, restore, upgrade, observability, alerting, and incident runbooks.
  - Explicit capacity plan for Flexprice (PostgreSQL, Kafka, ClickHouse, Redis, Temporal).
  - Health/readiness checks without exposing credentials or customer data.
  - Reconciliation and dead-letter/retry tooling.
  - Provider outage drills.
  - Tenant export, retention, suspension, and deletion policy.
  - Security review of webhook signatures, replay protection, token handling, and audit integrity.

## Mandatory Verification
Each work package must:
1. Run `python scripts/query_docs.py --boot-snapshot` before exploration.
2. Retrieve authoritative test command using `python scripts/query_docs.py --test-command <module>`.
3. Add regression tests for every changed security or billing behaviour.
4. Run focused backend tests and relevant frontend checks.
5. Run `python scripts/verify_zero_console_errors.py` after frontend changes.
6. Run `python scripts/verify_living_docs.py --path <module README>` for each changed module README.
7. Use synthetic, labelled data only.
8. Verify method, route, auth boundary, schema, tenant isolation, error behaviour, and idempotency for every API.
9. Confirm no console errors, page errors, or 4xx/5xx network failures on the required route sweep.
10. Stage only agreed paths, commit only after all gates pass, and push only according to mandatory verified-completion procedure.

## Definition of Done
The programme is complete only when:
- Tenant creation, ownership, invitations, and suspension are secure and platform-governed.
- Logto authentication and organisation context map safely to internal users and tenants.
- Flexprice subscription state is projected locally through signed, idempotent webhooks.
- Paid features and quotas are enforced by server-side local entitlements.
- No tenant can change its own billing state without an approved checkout/provider event.
- Tenant operational finance remains distinct from platform subscription billing.
- Reconciliation, outage handling, audit history, and runbooks are live.
- All documentation, migrations, tests, browser gates, and production readiness checks pass.
