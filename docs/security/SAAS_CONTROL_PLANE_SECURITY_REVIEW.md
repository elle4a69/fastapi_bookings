# SaaS Control Plane Platform Security Review (WP5)

**Document Classification:** Internal Security Audit  
**Author:** Lead DevOps, SRE & Platform Security Engineering  
**Scope:** Logto Identity Broker, Flexprice Metering & Billing, Multi-Tenant Isolation, API Ingress & Health

---

## 1. Executive Summary & Threat Model

The FastAPI Bookings SaaS Control Plane integrates Logto (OIDC/SSO Identity Provider) and Flexprice (Usage-Based Billing Engine) into a unified multi-tenant architecture. This review provides a formal security assessment of the authentication boundaries, cryptographic verifications, tenant isolation controls, and operational release gates.

### Threat Model Matrix (STRIDE)
| Threat Category | Potential Attack Vector | Platform Countermeasure / Control | Audit Result |
| :--- | :--- | :--- | :--- |
| **Spoofing** | Forged JWT bearer tokens or external webhook events | Asymmetric RS256 JWKS validation; HMAC-SHA256 constant-time webhook signatures | **PASS** |
| **Tampering** | Modifying webhook payload parameters or subscription tiers | Signed payloads, hash comparison, monotonic event sequence check | **PASS** |
| **Repudiation** | Denying administrative actions or billing modifications | Append-only `AuditLog` table and `ProviderEventInbox` transactional logs | **PASS** |
| **Information Disclosure** | Credential or tenant PII leakage in logs, traces, or health checks | Strict regex log scrubbing, anonymized health payloads, zero secrets in responses | **PASS** |
| **Denial of Service** | Webhook flooding, replay attacks, resource exhaustion | 300s timestamp window check, idempotency inbox deduplication, rate limits | **PASS** |
| **Elevation of Privilege** | Cross-tenant IDOR, tenant users attempting platform owner actions | Strict role-based dependencies (`require_platform_owner`), scoped tenant queries | **PASS** |

---

## 2. Authentication & Token Verification (RS256 JWKS)

### 2.1 Cryptographic Verification Architecture
All external user access is authenticated via JSON Web Tokens (JWT) issued by Logto:
- **Algorithm Enforcement**: Tokens MUST be signed using `RS256` (RSA Signature with SHA-256). Asymmetric key verification eliminates the risk of shared secret exposure.
- **Dynamic JWKS Fetching & Caching**: Public keys are retrieved from Logto's `/.well-known/jwks.json` endpoint and cached in-memory with a configurable TTL (1 hour). Key rotation is handled automatically by evicting stale keys when an unrecognized `kid` (Key ID) is encountered.
- **Claims Validation**:
  - `iss` (Issuer): Verified against `settings.LOGTO_ISSUER` or `settings.LOGTO_ENDPOINT`.
  - `aud` (Audience): Verified against `settings.LOGTO_API_RESOURCE`.
  - `exp` (Expiration): Enforced with zero clock skew allowance.
  - `tenant_id` / `org_id`: Extracted and cross-checked against tenant membership tables.

### 2.2 Rejection of Forged & Expired Tokens
- Any token signed with an untrusted key, tampered signature, or expired timestamp is rejected with `HTTP 401 Unauthorized`.
- Error messages returned to clients never leak key contents or internal stack traces.

---

## 3. Webhook Cryptographic Integrity & Anti-Replay Defense

### 3.1 Constant-Time HMAC-SHA256 Verification
Incoming webhooks from Flexprice (`POST /api/v1/platform-billing/webhooks/flexprice`) are signed using HMAC-SHA256:
- The secret key `settings.FLEXPRICE_WEBHOOK_SECRET` is used to compute the expected HMAC over the raw request body.
- Signatures are compared using Python's `hmac.compare_digest()` to eliminate timing attack vulnerabilities.

### 3.2 Anti-Replay & Timestamp Skew Protection
To prevent replay attacks:
1. **Timestamp Freshness**: Requests include `X-Flexprice-Timestamp`. Events older than 300 seconds (5 minutes) are immediately discarded (`HTTP 400 Bad Request`).
2. **Transactional Event Inbox (`ProviderEventInbox`)**:
   - Each event has a unique `event_id` column with a database-level unique constraint (`provider`, `event_id`).
   - Duplicate events are detected atomically; duplicate submissions return HTTP 200 acknowledging receipt without triggering redundant state transitions.
3. **Resurrection Guard**: Stale webhooks arriving out of order cannot reactivate cancelled subscriptions.

---

## 4. Zero Credential & Privacy Leakage Policy

### 4.1 Strict Logging Scrubbing
The logging pipeline (`app/main.py`) integrates an automatic regex-based PII and credential scrubber:
- Patterns matching API keys (`sk_live_...`, `Bearer ...`), passwords, JWT tokens, and connection strings are masked (`***REDACTED***`).
- Traceback frames are sanitized before ingestion into OpenTelemetry and SigNoz.

### 4.2 Health & Readiness Privacy Guarantee
- The deep health check (`GET /api/platform/health/readiness` and `/health/ready`) verifies the liveliness of PostgreSQL, Redis, Logto, and Flexprice.
- Health payloads report strictly status enums (`ok`, `degraded`, `down`), round-trip latencies in milliseconds, and generic status descriptors.
- **Absolute Exclusion**: Under no circumstances are database URLs (e.g. `postgres://user:pass@host/db`), Redis credentials, API tokens, or tenant identifiers returned in health responses.

---

## 5. Multi-Tenant Isolation & Role Boundaries

### 5.1 Platform Owner vs Tenant Boundaries
- Platform administration endpoints (`/api/platform/tenants`, `/api/platform/diagnostics`, `/api/platform/reconcile`) require the `require_platform_owner` dependency.
- Regular tenant administrators and end-users attempting to access platform-level controls receive `HTTP 403 Forbidden` (`PLATFORM_OWNER_REQUIRED`).
- All tenant database queries are explicitly filtered by `tenant_id` at the repository/service layer. Cross-tenant IDOR attempts are structurally blocked.

### 5.2 Fail-Closed Operational Architecture
- During third-party outages (Logto or Flexprice network downtime):
  - The system fails closed.
  - No fallback permits unauthenticated users to gain access or tenants to arbitrarily upgrade subscription quotas.
  - Billing portal requests return `HTTP 503 Service Unavailable`.
  - Local cached `SubscriptionProjection` records provide continuous read-only entitlement checks for valid, previously verified tenants.

---

## 6. Audit Sign-Off & Verification

All automated security contracts have been verified via regression test suites:
- Token tampering and expiration tests: `tests/test_wp1_logto_identity_contract.py` (PASS)
- Webhook HMAC and replay protection tests: `tests/test_wp2_flexprice_billing_contract.py` (PASS)
- Server-side entitlement and quota isolation: `tests/test_wp3_entitlements_contract.py` (PASS)
- Multi-tenant IDOR and operator privilege boundaries: `tests/test_wp0_security_contract.py`, `tests/test_wp4_ux_api_contract.py` (PASS)
- Readiness probe fail-closed and reconciliation tests: `tests/test_wp5_operational_hardening.py` (PASS)
