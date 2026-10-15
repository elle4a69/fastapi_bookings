# Platform Billing & Subscription Projection Service (`app/services/platform_billing/`)

## 1. Purpose & Scope

The `app/services/platform_billing/` module implements the native SaaS billing adapter, subscription projections, entitlement snapshots, and usage metering for **FastAPI Bookings** in integration with **Flexprice**.

### What this module owns:
- Local projection of tenant billing accounts, active subscriptions, and entitlement limits.
- Cryptographic verification of inbound billing webhooks (HMAC-SHA256 over exact raw request bodies).
- Privacy-safe event deduplication via SHA-256 payload digest in `ProviderEventInbox`.
- Out-of-order event protection preventing resurrecting terminated or cancelled subscriptions from delayed webhooks.
- Fine-grained entitlement calculations (`EntitlementSnapshot`) for locations, staff, voice, SMS quotas, and feature flags.
- Outbox queuing (`UsageEventOutbox`) for metered consumption events with stable idempotency keys.
- Safe generation of hosted customer billing portal sessions.
- Consistency reconciliation between local projection and remote billing provider state.

### What this module deliberately avoids:
- **NO Payment Credentials Stored**: Credit card numbers, expiration dates, CVVs, and banking credentials are never collected, processed, or persisted. All payment collection is strictly handled by Flexprice-hosted checkout and customer portal interfaces.
- **Fail-Closed Security**: API failures or network outages from Flexprice fail closed; they never grant elevated privileges or bypass entitlement limits.
- **Client Direct Tier Manipulation**: Tenants and clients cannot directly mutate subscription tiers or active entitlements; all modifications must originate from verified provider webhooks or platform-owner administration.

---

## 2. Architecture & Key Files

```text
app/services/platform_billing/
├── __init__.py                # Package facade exposing clients, services, and models
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
- [`EntitlementSnapshot`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Atomic snapshot of active features and quotas (`max_locations`, `ai_voice_enabled`, `sms_monthly_quota`).
- [`ProviderEventInbox`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Deduplication and audit log holding raw payload SHA-256 digests.
- [`UsageEventOutbox`](file:///F:/Projects/fastapi_bookings/app/models/platform_billing.py): Reliable transactional outbox for metered consumption events.

---

## 3. Setup, Configuration & Dependencies

### Environment Variables (`app/core/config.py`):
| Variable | Default | Purpose |
|---|---|---|
| `FLEXPRICE_API_BASE_URL` | `https://api.flexprice.io/v1` | Base URL for Flexprice REST API |
| `FLEXPRICE_API_KEY` | `test-flexprice-api-key` | Bearer authentication key for Flexprice API |
| `FLEXPRICE_WEBHOOK_SECRET` | `test-flexprice-webhook-secret` | Shared secret for verifying `X-Flexprice-Signature` |
| `FLEXPRICE_PORTAL_RETURN_URL` | `https://app.bookings.local/admin/billing` | Default return URL after customer exits billing portal |

### Dependencies:
- `httpx`: Robust HTTP client used with strict timeouts and fail-closed exception wrapping.
- `hashlib` & `hmac`: Standard library cryptographic primitives for constant-time signature verification and SHA-256 digesting.

---

## 4. Core Workflows & Contracts

### 4.1 Inbound Webhook Processing (`POST /api/webhooks/flexprice`)
1. Client/Flexprice sends event with raw body and `X-Flexprice-Signature` header.
2. `WebhookVerificationService.verify_signature(raw_body, signature)` calculates expected HMAC-SHA256 and asserts constant-time equality. Mismatches return 401 Unauthorized immediately.
3. `SubscriptionProjectionService.record_inbox_event` stores `ProviderEventInbox` with `payload_digest = sha256(raw_body)`.
4. If `external_event_id` was already processed, returns 200 OK with `action_taken = "deduplicated"`.
5. Out-of-order check: if event timestamp is older than existing `SubscriptionProjection.last_event_timestamp`, event is marked `ignored` and ignored without state mutation.
6. Resurrection guard: if existing subscription is cancelled and incoming event has stale or non-monotonic sequence, the event is rejected.
7. Upon successful validation, `SubscriptionProjection` is updated, `EntitlementSnapshot` is refreshed, and `tenant.subscription_tier` is aligned.

### 4.2 Hosted Billing Portal Session (`POST /api/billing/portal-session`)
1. Authenticated tenant owner requests a billing portal session.
2. If `BillingAccount.flexprice_customer_id` does not exist, `FlexpriceClient.create_customer` provisions the customer in Flexprice and persists the ID.
3. `FlexpriceClient.create_portal_session` requests a short-lived URL from Flexprice.
4. Returns `{ "portal_url": "https://billing.flexprice.io/portal/..." }`.

### 4.3 Metered Usage Tracking (`POST /api/billing/usage`)
1. Application logic or caller records usage units for a meter (e.g., `sms_outbound`, `ai_tokens`).
2. `UsageMeteringService.record_usage` records row into `usage_event_outbox` with a caller-supplied or generated idempotency key.
3. Duplicate keys return existing outbox rows without incrementing usage.
4. Background worker dispatches pending events in batches to Flexprice.

---

## 5. Data Safety & Isolation

1. **Strict Multi-Tenant Scoping**: All subscription projections, entitlement snapshots, and usage outbox records are foreign-keyed to `tenants.id` with `ondelete="CASCADE"`.
2. **Cross-Tenant Guard**: Endpoints in `/api/billing/*` enforce tenant isolation via `get_current_tenant` and reject cross-tenant access.
3. **No Credential Storage**: No credit cards, CVVs, or bank tokens are stored or transmitted through FastAPI Bookings.
4. **Privacy-Preserving Audit**: Raw webhook bodies are hashed to SHA-256 digests before persisting to `ProviderEventInbox`. Sensitive customer payload data is not written to database tables or application logs.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Background Dispatch Worker**: Batch dispatch from `usage_event_outbox` is triggered via service interface; full standalone daemon worker loop is scheduled for WP3/WP5.
- **Dynamic Plan Addons**: Basic catalog supports `starter`, `pro`, and `enterprise` tiers with custom entitlement payload overrides; arbitrary multi-line item add-on sync will be expanded in WP3.

---

## 7. Verification & Testing Commands

To run the authoritative test suite for WP2:
```bash
python -m pytest tests/test_wp2_flexprice_billing_contract.py -v
```

To run living documentation verification:
```bash
python scripts/verify_living_docs.py --path app/services/platform_billing/README.md
```
