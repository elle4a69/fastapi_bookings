# Platform Billing & Subscription Projection Service (`app/services/platform_billing/`)

## 1. Purpose & Scope

The `app/services/platform_billing/` module implements the native SaaS billing adapter, subscription projections, entitlement snapshots, usage metering, and tenant/operator user interfaces for **FastAPI Bookings** in integration with **Flexprice** (WP2, WP3 & WP4).

### What this module owns:
- Local projection of tenant billing accounts, active subscriptions, and entitlement limits.
- Stable business entitlement catalogue definition and enforcement:
  - `assistant.enabled` (boolean)
  - `assistant.monthly_runs` (numeric limit)
  - `sms.enabled` (boolean)
  - `sms.monthly_outbound_messages` (numeric limit)
  - `providers.max` (numeric limit)
  - `locations.max` (numeric limit)
  - `api.enabled` (boolean)
- Server-side entitlement and quota enforcement guards (`EntitlementGuardService`, `require_entitlement`, `require_quota`, `check_quota`).
- Explicit, expiring, audited platform operator overrides (`PlatformEntitlementGrant`).
- Cryptographic verification of inbound billing webhooks (HMAC-SHA256 over exact raw request bodies).
- Privacy-safe event deduplication via SHA-256 payload digest in `ProviderEventInbox`.
- Out-of-order event protection preventing resurrecting terminated or cancelled subscriptions from delayed webhooks.
- Fine-grained entitlement calculations (`EntitlementSnapshot`) for locations, staff, voice, SMS quotas, and feature flags.
- Outbox queuing (`UsageEventOutbox`) for metered consumption events with stable idempotency keys.
- Safe generation of hosted customer billing portal sessions.
- Consistency reconciliation between local projection and remote billing provider state.
- Tenant-facing Plan & Billing interface (`frontend/src/pages/admin/plan-billing.tsx`) with real-time quota gauges and grace period alerts.
- Platform Operator Console (`frontend/src/pages/admin/platform-billing-console.tsx`) for tenant diagnostics, inbox retry, grants management, and provider reconciliation.

### What this module deliberately avoids:
- **NO Payment Credentials Stored**: Credit card numbers, expiration dates, CVVs, and banking credentials are never collected, processed, or persisted. All payment collection is strictly handled by Flexprice-hosted checkout and customer portal interfaces.
- **Fail-Closed Security**: API failures or missing/expired entitlement snapshots fail closed (403 Forbidden: `EntitlementRequiredError` / `QuotaExceededError`); they never grant elevated privileges or bypass limits.
- **Client Direct Tier Manipulation**: Tenants and clients cannot directly mutate subscription tiers or active entitlements; all modifications must originate from verified provider webhooks or platform-owner administration.
- **Feature Flag Abuse**: Feature flags may restrict rollout; they may NEVER grant unpurchased features without underlying entitlement.
- **Mock Implementations**: No synthetic delays, setTimeout simulations, or fake success state; every transaction reflects real database state and authenticated APIs.

---

## 2. Architecture & Key Files

```text
app/services/platform_billing/
├── __init__.py                # Package facade exposing clients, services, guards, and models
├── entitlement_guard.py       # Authoritative server-side entitlement & quota guards (WP3)
├── flexprice_client.py        # Flexprice API client with fail-closed outage handling
├── webhook_verifier.py        # Raw-body HMAC-SHA256 signature verification & SHA-256 digesting
├── projection_service.py      # SubscriptionProjection & EntitlementSnapshot management
├── metering_service.py        # Idempotent UsageEventOutbox recording & batch dispatching
├── reconciliation_service.py  # Projection vs remote state audit & dead-letter queue inspection
└── README.md                  # Authoritative module documentation (Rule 10)

app/api/routers/
├── platform_billing.py        # Tenant subscription overview, portal session, and operator endpoints
└── flexprice_webhooks.py      # Cryptographically verified webhook intake endpoint

frontend/src/pages/admin/
├── plan-billing.tsx           # Tenant-facing Plan & Billing page with quotas & portal redirect
└── platform-billing-console.tsx # Platform operator console for cross-tenant overview & grants
```

### Key Models & Relational Architecture:
- [`BillingAccount`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Links `tenants.id` to `flexprice_customer_id` and tracks account lifecycle state (`unconfigured`, `active`, `past_due`, `cancelled`).
- [`SubscriptionProjection`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Authoritative local projection tracking `plan_id`, `plan_version`, `status`, `current_period_start/end`, and ordering metadata (`last_event_timestamp`, `last_event_sequence`).
- [`EntitlementSnapshot`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Atomic snapshot of active features and quotas derived from current subscription.
- [`PlatformEntitlementGrant`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Audited platform-authorized overrides with optional expiration (`expires_at`) and revocation (`is_revoked`).
- [`ProviderEventInbox`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Deduplication and audit log holding raw payload SHA-256 digests and processing status.
- [`UsageEventOutbox`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Reliable transactional outbox for metered consumption events with stable idempotency keys.

---

## 3. Setup, Configuration & Dependencies

### Environment Variables
- `FLEXPRICE_BASE_URL`: Base URL for the external Flexprice billing API (e.g. `https://api.flexprice.io/v1`).
- `FLEXPRICE_API_KEY`: Secret API token used to authenticate outbound requests to Flexprice.
- `FLEXPRICE_WEBHOOK_SECRET`: Secret key used for raw-body HMAC-SHA256 webhook signature validation.

### Internal Dependencies
- `app.models.tenant.Tenant`: Host tenant records.
- `app.models.user.User`: Authentication and platform owner role resolution.
- `app.models.location.Location`: Real-time active location count for state-based quota checks.
- `app.models.provider.Provider`: Real-time active staff provider count for state-based quota checks.
- `app.db.database.Base`: Declarative Base for SQLAlchemy ORM models.

---

## 4. Core Workflows & Contracts

### 4.1 Resolution Hierarchy
When resolving `get_effective_entitlement(db, tenant_id, entitlement_key)`:
1. **Platform Grants**: Check `PlatformEntitlementGrant` where `is_revoked == False` and (`expires_at is None or expires_at > now`). Active platform grants take highest priority.
2. **Subscription Status**: If the tenant's latest `SubscriptionProjection` is `cancelled`, `terminated`, or `past_due`, the guard fails closed (returns None).
3. **Entitlement Snapshots**: Query `EntitlementSnapshot` where `is_active == True` and (`expires_at is None or expires_at > now`).
4. **Plan Catalog Fallback**: If no snapshot exists yet (e.g. unconfigured trial or demo tenant), resolve default limits from `PLAN_ENTITLEMENT_CATALOG` for `tenant.subscription_tier`.
5. **Fail-Closed**: If unresolvable or expired, returns `None`.

### 4.2 Stable Business Entitlement Catalogue

| Canonical Entitlement Key | Value Type | Starter | Growth / Pro | Unlimited / Enterprise |
|---|---|---|---|---|
| `assistant.enabled` | boolean | `false` | `true` | `true` |
| `assistant.monthly_runs` | numeric | `50` | `500` | `5000` |
| `sms.enabled` | boolean | `true` | `true` | `true` |
| `sms.monthly_outbound_messages` | numeric | `100` | `1000` | `10000` |
| `providers.max` | numeric | `2` | `10` | `100` |
| `locations.max` | numeric | `1` | `5` | `100` |
| `api.enabled` | boolean | `false` | `true` | `true` |

*(Backward-compatible aliases like `max_locations`, `sms_monthly_quota`, and `max_staff` are maintained and resolved seamlessly).*

### 4.3 Tenant & Platform Operator Endpoints
- **Tenant Subscription Overview** (`GET /api/billing/subscription`): Returns plan details, active status, billing cycle, past-due flag, and consumption progress across all quotas.
- **Hosted Portal Session** (`POST /api/billing/portal-session`): Gated on tenant owner; returns short-lived hosted portal session URL.
- **Platform Overview** (`GET /api/admin/platform/billing/tenants`): Gated on `require_platform_owner`; returns cross-tenant health and subscription projections.
- **Tenant Diagnostics** (`GET /api/admin/platform/billing/tenants/{tenant_id}/diagnostics`): Detailed diagnostics modal showing projections, snapshots, grants, and recent events.
- **Event Inbox & Dead Letters** (`GET /api/admin/platform/billing/inbox`, `POST /api/admin/platform/billing/inbox/{event_id}/retry`): Inspects received webhooks and retries failed deliveries.
- **Platform Grants Manager** (`GET`, `POST`, `DELETE /api/admin/platform/billing/grants`): Creates, lists, and revokes expiring or permanent audited entitlement overrides.
- **Provider Reconciliation** (`POST /api/admin/platform/billing/reconcile`): On-demand synchronization asserting local projection consistency against Flexprice.

---

## 5. Data Safety & Isolation

- **Tenant Boundary Isolation**: All tenant billing endpoints require active tenant resolution (`get_current_tenant`) and match authenticated user tenant affinity. Tenant A can never query or mutate Tenant B's billing records.
- **Zero Card Data Retention**: Payment instruments and credit cards are NEVER accepted or persisted within the application database. All payment actions are delegated to the hosted Flexprice customer portal.
- **Digest Privacy Protection**: `ProviderEventInbox` persists only the hex-encoded SHA-256 digest of raw inbound payloads, preventing customer PII or secret leaks in event logs.
- **Audit Logging of Overrides**: Every platform grant requires an explicit non-empty operational reason (`reason`), recording `granted_by_user_id` and timestamps.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Full Control Plane Integration**: WP1 through WP5 are fully implemented and verified. Production deployment topology is codified in [`docs/operations/DEPLOYMENT_TOPOLOGY_LOGTO_FLEXPRICE.md`](file:///f:/Projects/fastapi_bookings/docs/operations/DEPLOYMENT_TOPOLOGY_LOGTO_FLEXPRICE.md), operational runbooks in [`docs/runbooks/SAAS_CONTROL_PLANE_RUNBOOK.md`](file:///f:/Projects/fastapi_bookings/docs/runbooks/SAAS_CONTROL_PLANE_RUNBOOK.md), and platform security review in [`docs/security/SAAS_CONTROL_PLANE_SECURITY_REVIEW.md`](file:///f:/Projects/fastapi_bookings/docs/security/SAAS_CONTROL_PLANE_SECURITY_REVIEW.md).
- **Out-of-Order Webhook Sequences**: Addressed by monotonic sequence checks in `SubscriptionProjectionService`; older events arriving after a cancellation will not resurrect the subscription.
- **External Provider Outages**: Fail-closed architecture raises `HTTPException(503)` when the remote provider is unreachable, ensuring unpurchased features are never accidentally exposed.
- **Grace Period Past Due**: Subscriptions in `past_due` status trigger the amber grace period warning banner in the tenant UX without abruptly locking out existing bookings.
- **Operational CLI Tooling**: The offline reconciliation script [`scripts/reconcile_saas_control_plane.py`](file:///f:/Projects/fastapi_bookings/scripts/reconcile_saas_control_plane.py) enables operators to audit drift and batch replay dead-letter events.

---

## 7. Verification & Testing Commands

Run the full contract test suites across billing, entitlements, UX, and operational release gates:

```powershell
# Run full SaaS control plane contract and operational hardening test suite
.venv\Scripts\python.exe -m pytest tests/test_wp0_security_contract.py tests/test_wp1_logto_identity_contract.py tests/test_wp2_flexprice_billing_contract.py tests/test_wp3_entitlements_contract.py tests/test_wp4_ux_api_contract.py tests/test_wp5_operational_hardening.py -v

# Run operational reconciliation script smoke check
.venv\Scripts\python.exe scripts/reconcile_saas_control_plane.py --help

# Run living documentation compliance linter
python scripts/verify_living_docs.py

# Verify frontend build & TypeScript compliance
cd frontend && npm run build
```
