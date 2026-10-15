# Platform Billing & Subscription Projection Service (`app/services/platform_billing/`)

## 1. Purpose & Scope

The `app/services/platform_billing/` module implements the native SaaS billing adapter, subscription projections, entitlement snapshots, and usage metering for **FastAPI Bookings** in integration with **Flexprice** (WP2 & WP3).

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
- Explicit, expiring, audited platform overrides (`PlatformEntitlementGrant`).
- Cryptographic verification of inbound billing webhooks (HMAC-SHA256 over exact raw request bodies).
- Privacy-safe event deduplication via SHA-256 payload digest in `ProviderEventInbox`.
- Out-of-order event protection preventing resurrecting terminated or cancelled subscriptions from delayed webhooks.
- Fine-grained entitlement calculations (`EntitlementSnapshot`) for locations, staff, voice, SMS quotas, and feature flags.
- Outbox queuing (`UsageEventOutbox`) for metered consumption events with stable idempotency keys.
- Safe generation of hosted customer billing portal sessions.
- Consistency reconciliation between local projection and remote billing provider state.

### What this module deliberately avoids:
- **NO Payment Credentials Stored**: Credit card numbers, expiration dates, CVVs, and banking credentials are never collected, processed, or persisted. All payment collection is strictly handled by Flexprice-hosted checkout and customer portal interfaces.
- **Fail-Closed Security**: API failures or missing/expired entitlement snapshots fail closed (403 Forbidden: `EntitlementRequiredError` / `QuotaExceededError`); they never grant elevated privileges or bypass limits.
- **Client Direct Tier Manipulation**: Tenants and clients cannot directly mutate subscription tiers or active entitlements; all modifications must originate from verified provider webhooks or platform-owner administration.
- **Feature Flag Abuse**: Feature flags may restrict rollout; they may NEVER grant unpurchased features without underlying entitlement.

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
```

### Key Models & Relational Architecture:
- [`BillingAccount`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Links `tenants.id` to `flexprice_customer_id` and tracks account lifecycle state (`unconfigured`, `active`, `past_due`, `cancelled`).
- [`SubscriptionProjection`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Authoritative local projection tracking `plan_id`, `plan_version`, `status`, `current_period_start/end`, and ordering metadata (`last_event_timestamp`, `last_event_sequence`).
- [`EntitlementSnapshot`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Atomic snapshot of active features and quotas derived from current subscription.
- [`PlatformEntitlementGrant`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Audited platform-authorized overrides with optional expiration (`expires_at`) and revocation (`is_revoked`).
- [`ProviderEventInbox`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Deduplication and audit log holding raw payload SHA-256 digests.
- [`UsageEventOutbox`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Reliable transactional outbox for metered consumption events with stable idempotency keys.

---

## 3. Stable Business Entitlement Catalogue

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

---

## 4. Server-Side Entitlement & Quota Guard Architecture

### 4.1 Resolution Hierarchy
When checking `get_effective_entitlement(db, tenant_id, entitlement_key)`:
1. **Platform Grants**: Check `PlatformEntitlementGrant` where `is_revoked == False` and (`expires_at is None or expires_at > now`). Active platform grants take highest priority.
2. **Subscription Status**: If the tenant's latest `SubscriptionProjection` is `cancelled`, `terminated`, or `past_due`, the guard fails closed (returns None).
3. **Entitlement Snapshots**: Query `EntitlementSnapshot` where `is_active == True` and (`expires_at is None or expires_at > now`).
4. **Plan Catalog Fallback**: If no snapshot exists yet (e.g. unconfigured trial or demo tenant), resolve default limits from `PLAN_ENTITLEMENT_CATALOG` for `tenant.subscription_tier`.
5. **Fail-Closed**: If unresolvable or expired, returns `None`.

### 4.2 Guard APIs
- `require_entitlement(entitlement_key, required_value=True)`: FastAPI route dependency raising `EntitlementRequiredError` (403 Forbidden).
- `check_quota(db, tenant_id, quota_key, requested_quantity=1, raise_exception=True)`: Checks active state count or metered period usage against limit, raising `QuotaExceededError` (403 Forbidden).
- `record_usage_with_deduplication(...)`: Records usage to `UsageEventOutbox` with guaranteed idempotency deduplication.

---

## 5. Verification & Testing

Tests for entitlements and billing contracts are located at:
- `tests/test_wp3_entitlements_contract.py`
- `tests/test_wp2_flexprice_billing_contract.py`

### Key Invariants Tested:
1. Unpurchased modules and features blocked with 403 Forbidden (`EntitlementRequiredError`).
2. Quota enforcement prevents actions before execution begins (`QuotaExceededError`).
3. Usage deduplication ensures retries with identical `idempotency_key` never double-count.
4. Platform grants override subscription snapshots and expire/revoke cleanly.
5. Strict multi-tenant isolation prevents cross-tenant quota consumption or visibility.
6. Non-platform owners cannot manipulate subscription tiers or quotas.
