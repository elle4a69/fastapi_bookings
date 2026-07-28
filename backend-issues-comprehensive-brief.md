# FastAPI Bookings Backend — Comprehensive Issues Brief

**Prepared for:** Frank Lucisano  
**Assessment date:** 12 July 2026  
**Systems assessed:**

- Deployed Cloud Run backend: `https://bookopenapi-backend-208926050296.us-central1.run.app`
- Public OpenAPI document: `/openapi.json`
- Canonical local backend: `F:\Projects\fastapi_bookings`
- Separate partial/legacy backend also found: `E:\Projects\Fast-API-Bookings`
- Frontend contract: 19-section **FastAPI Bookings Front-End MCD**

## 1. Executive Summary

The backend is not currently ready to support the complete production frontend defined by the MCD.

The canonical local backend is `F:\Projects\fastapi_bookings`. It is a substantial Git-backed project containing the application, Alembic migrations, contracts, tests, frontend, MCD, audit report, database and a 437 KB OpenAPI document. Its OpenAPI identifies as **FastAPI Bookings 0.1.0** and exposes 120 paths.

A direct structural comparison confirmed that the canonical local OpenAPI and deployed Cloud Run OpenAPI contain:

- 120 paths each;
- zero missing paths in either environment; and
- zero HTTP-method differences.

Therefore, the original conclusion that the canonical local and Cloud Run APIs were different contracts was incorrect. That conclusion arose because a separate partial backend at `E:\Projects\Fast-API-Bookings` was initially mistaken for the real project. The `E:` backend exposes only nine paths and uses a different contract, but it is **not** the canonical source for Cloud Run.

The Cloud Run deployment also produced confirmed HTTP 500 failures for public service retrieval and admin authentication. Several release-critical business rules from the MCD are missing from the deployed API entirely, particularly client management restrictions, management review requests, atomic deposit confirmation, provider/company-hours controls, notification configuration and business-profile persistence.

**Overall decision:** backend remediation and contract unification are required before the frontend can be released legitimately.

---

## 2. Severity Classification

| Severity | Meaning |
|---|---|
| Critical | Prevents secure production release or risks incorrect booking/payment/tenant behaviour |
| High | Blocks a required MVP workflow or causes major frontend/backend incompatibility |
| Medium | Produces incomplete behaviour, misleading documentation or significant maintainability risk |
| Low | Quality, consistency or developer-experience defect that should be corrected |

---

## 3. Confirmed Findings Summary

| ID | Severity | Finding | Status |
|---|---:|---|---|
| BE-001 | Medium | Separate partial backend at `E:` can be mistaken for the canonical `F:` project | Confirmed |
| BE-002 | Critical | Cloud Run public services endpoint returns HTTP 500 | Confirmed |
| BE-003 | Critical | Cloud Run admin authentication returns HTTP 500 instead of a controlled auth response | Confirmed |
| BE-004 | Critical | Required-deposit payment and booking confirmation are not proven atomic | Confirmed contract gap |
| BE-005 | Critical | Client management restriction is absent from the deployed Client contract | Confirmed |
| BE-006 | High | No Management Review Request API exists | Confirmed |
| BE-007 | High | Public authentication cannot be configured locally because `PUBLIC_API_KEY` is absent | Confirmed |
| BE-008 | High | Provider `ignore_company_hours` and booking horizon are absent from scheduling contracts | Confirmed |
| BE-009 | High | Business-profile read/update API is absent | Confirmed |
| BE-010 | High | Notification delivery records exist, but notification configuration does not | Confirmed |
| BE-011 | High | Tenant retention/deletion policy is undefined | Confirmed release blocker |
| BE-012 | Low | Partial/legacy `E:` backend uses incompatible authentication and token formats | Confirmed; non-canonical |
| BE-013 | Medium | Partial/legacy `E:` backend remains runnable and can mislead development | Confirmed; non-canonical |
| BE-014 | Medium | Credentials from the partial `E:` backend were incorrectly assumed to apply to Cloud Run | Confirmed |
| BE-015 | Medium | Public endpoint security requirements are inconsistent in OpenAPI | Confirmed |
| BE-016 | Medium | Error handling leaks generic HTTP 500 responses for expected failures | Confirmed |
| BE-017 | Medium | Service/provider/category/location relationship coverage is incomplete or one-sided | Confirmed contract limitation |
| BE-018 | Low | Partial/legacy `E:` response envelopes differ from the canonical contract | Confirmed; non-canonical |
| BE-019 | Low | Partial/legacy `E:` booking fields/state model differ from the canonical contract | Confirmed; non-canonical |
| BE-020 | Low | Partial/legacy `E:` health/readiness conventions differ | Confirmed; non-canonical |

---

## 4. Detailed Findings

### BE-001 — Separate Partial Backend Can Be Mistaken for the Canonical Project

**Severity:** Medium

#### Evidence

VS Code confirmed the canonical backend at:

`F:\Projects\fastapi_bookings`

It contains:

- `.git` and Alembic migrations;
- `app`, `contracts`, `docs` and `tests`;
- `fastapi_bookings.db`;
- `fastapi_bookings_mcd.md` and an audit report;
- `frontend`; and
- a 437 KB `openapi.json`.

Its Git remote is currently:

`https://github.com/elle4a69/fastapi_bookings.git`

Its OpenAPI uses paths such as:

- `POST /api/admin/auth`
- `GET /api/admin/bookings`
- `GET /api/public/services`
- `POST /api/public/search-availability`

The separate backend previously inspected at `E:\Projects\Fast-API-Bookings` uses:

- `POST /admin/auth`
- `GET /admin/bookings`
- `GET /public/services`
- `GET /public/schedules`

That separate `E:` API exposes only these functional groups:

- Admin authentication
- Admin bookings
- Admin clients
- Public token
- Public services
- Public schedules

It is not the source of the deployed 120-path API.

The canonical `F:` and deployed Cloud OpenAPI documents were compared directly: both have 120 paths, with zero missing paths and zero HTTP-method differences.

#### Impact

- Developers can accidentally run or test the wrong backend.
- Credentials from the `E:` backend can be incorrectly assumed to apply to the canonical project or Cloud Run.
- Frontend adapters added for the wrong API create unnecessary complexity and misleading results.
- Audit findings can be incorrectly attributed to the canonical backend.

#### Required remediation

1. Treat `F:\Projects\fastapi_bookings` as the canonical local backend.
2. Rename, archive or clearly label `E:\Projects\Fast-API-Bookings` as non-canonical.
3. Remove any frontend configuration pointing to the partial `E:` API.
4. Document the canonical local start command, port and environment setup in the root README.
5. Retain an OpenAPI parity gate so local and deployed contracts cannot drift.

#### Verification

- Developers start the backend only from the canonical `F:` project.
- Local and Cloud OpenAPI parity remains zero missing paths and zero method differences.
- No production frontend code contains an adapter for the partial `E:` contract.

---

### BE-002 — Cloud Run Public Services Returns HTTP 500

**Severity:** Critical

#### Evidence

A direct request to:

`GET /api/public/services` with `X-Tenant: simplydemo`

returned:

`HTTP/1.1 500 Internal Server Error`

The same failure occurred when the request passed through the frontend BFF, proving the frontend was not the source.

#### Impact

- The public booking funnel cannot begin.
- No service can be selected.
- All downstream discovery, provider and availability workflows are blocked.
- A production booking page displays an upstream failure before the user can take any action.

#### Required remediation

1. Inspect the Cloud Run exception trace for this endpoint.
2. Confirm tenant resolution for `simplydemo`.
3. Confirm database connectivity, migrations and seed data.
4. Confirm public authentication middleware behaviour.
5. Return a controlled 401/403 when a token is required, never 500.
6. Return a valid empty success envelope when the tenant contains no services.

#### Verification

- Valid tenant/token returns 200 with the documented service list envelope.
- Missing token returns documented 401/403.
- Unknown tenant returns documented 404 or tenant-not-found error.
- Empty catalogue returns 200 with an empty list.

---

### BE-003 — Cloud Run Admin Authentication Returns HTTP 500

**Severity:** Critical

#### Evidence

The frontend and a direct request both tested:

`POST /api/admin/auth`

using the repository's documented seed credentials. Cloud Run returned HTTP 500. Through the frontend it returned:

`{"detail":"Authentication failed"}`

The same credentials succeeded against the separate partial `E:` backend at `POST /admin/auth`; this was not evidence about the canonical `F:` backend.

#### Impact

- Administrators cannot access the production frontend.
- Invalid credentials are treated as server faults.
- Monitoring records false server incidents for normal authentication failures.
- The frontend cannot distinguish invalid credentials from database or infrastructure failure.

#### Required remediation

1. Return 401 for invalid credentials.
2. Return 403 for inactive/forbidden users or tenant mismatch.
3. Return 422 only for malformed requests.
4. Reserve 500 for unexpected internal failures.
5. Confirm the production tenant has an owner/admin account created through a controlled provisioning process.
6. Remove documentation that implies local seed credentials work in production.

#### Verification

- Valid production account returns 200 and the documented token envelope.
- Invalid password returns 401 with stable code `INVALID_CREDENTIALS`.
- Unknown tenant returns a deterministic tenant error.
- No expected authentication outcome returns 500.

---

### BE-004 — Deposit Payment and Booking Confirmation Are Not Atomic

**Severity:** Critical

#### MCD requirement

When a deposit is required, successful payment must atomically secure and confirm the ordinary booking. An unpaid request must never reserve inventory.

#### Contract issue

The deployed API contains payment and deposit-session surfaces, but the reviewed OpenAPI does not prove a single authoritative transaction that:

1. revalidates the live slot;
2. verifies the client is eligible;
3. confirms payment success;
4. creates one booking;
5. removes the slot from availability; and
6. returns one deterministic result under an idempotency key.

#### Impact

- Double charges or duplicate bookings are possible.
- Payment may succeed while booking creation fails.
- A stale slot may be paid for after another client books it.
- The frontend cannot safely retry an uncertain result.

#### Required remediation

Create one backend-controlled checkout/commit operation with:

- required idempotency key;
- database transaction or equivalent atomic orchestration;
- processor-event reconciliation;
- slot revalidation immediately before commit;
- no unpaid hold;
- deterministic confirmed/declined/conflict/uncertain result;
- read-after-uncertain-write reconciliation endpoint.

#### Verification

- Duplicate submission produces one payment and one booking.
- Declined payment produces no booking or hold.
- Concurrent slot loss produces no charge and no booking.
- Processor success with interrupted response can be reconciled without a second charge.

---

### BE-005 — Missing Client Management Restriction

**Severity:** Critical

#### MCD requirement

Clients may carry a persistent `management_approval_required` restriction. This must be evaluated before payment or ordinary booking creation.

#### Contract issue

The deployed Client and Client update schemas do not contain `management_approval_required` or an equivalent authoritative field.

#### Impact

- Restricted clients cannot be identified reliably.
- A client who must be reviewed may proceed to payment or booking.
- The frontend cannot enforce this safely because client-side state is not authoritative.

#### Required remediation

Add a persisted tenant-scoped restriction with:

- restriction boolean/status;
- reason;
- applied by;
- applied at;
- cleared by;
- cleared at;
- audit event;
- owner/management-only mutation permissions.

Evaluate it server-side before availability commitment, payment and booking creation.

---

### BE-006 — No Management Review Request API

**Severity:** High

The MCD requires restricted clients to submit a non-reserving, non-paying Management Review Request. No corresponding deployed endpoint or schema was identified.

The required object should include client, preferred service/provider/location/time, reason/state, `slot_reserved=false`, `payment_taken=false`, timestamps, resolution and audit fields.

The backend must reject duplicates and must not imply that the preferred slot has been approved or held.

---

### BE-007 — Missing Public API Key Configuration

**Severity:** High

The public token endpoint requires a configured `PUBLIC_API_KEY`. A non-secret presence check confirmed that the canonical `F:\Projects\fastapi_bookings\.env` does not currently contain a `PUBLIC_API_KEY=` entry. Without the key being provided through the runtime environment or secret manager, the frontend server cannot obtain a public widget token.

#### Required remediation

- Provision the key through a secret manager.
- Inject it server-side only.
- Never expose it as a `NEXT_PUBLIC_*` value.
- Rotate it and support overlap during rotation.
- Return clear configuration errors during startup/readiness checks.

---

### BE-008 — Missing Ignore Company Hours and Booking Horizon

**Severity:** High

The deployed workday contract contains provider, location, weekday, start time, end time and working-state fields. It does not represent:

- provider `ignore_company_hours`;
- `max_advance_days` booking horizon;
- the complete date-specific override priority required by the MCD.

These rules must be persisted and applied by the availability engine, not calculated solely in the frontend.

---

### BE-009 — Missing Business Profile API

**Severity:** High

No deployed read/update contract was found for business name, timezone, locale, country, contact details, website, public address visibility or tenant booking identity.

The frontend cannot legitimately persist this configuration. Add an owner/management-authorised business-profile resource and include its public-safe subset in bootstrap.

---

### BE-010 — Notification Records Without Notification Configuration

**Severity:** High

The deployed API supports notification records/delivery data, but no tenant configuration was found for:

- enabled channels;
- event templates;
- reminder timing;
- recipient policy;
- booking-state event mapping;
- retry/escalation policy.

Notification delivery must not alter booking state. Configuration changes require owner/management permissions and audit logging.

---

### BE-011 — Undefined Retention and Deletion Policy

**Severity:** High

No confirmed tenant/jurisdiction policy exists for retention and deletion of:

- clients;
- bookings;
- payments;
- notifications;
- audit logs.

This blocks final data-model and non-functional release gates. For Australia, the policy must be reviewed against the Privacy Act 1988 and Australian Privacy Principles, with jurisdiction overrides where required.

The backend needs documented retention periods, legal-hold behaviour, anonymisation versus deletion rules, audit retention and operator-facing enforcement jobs.

---

### BE-012 — Partial/Legacy Backend Authentication Divergence

**Severity:** Low

This finding applies only to the separate `E:\Projects\Fast-API-Bookings` backend. It does not establish divergence between the canonical `F:` backend and Cloud Run.

#### Cloud Run

- `X-Tenant`
- `X-Token`
- JWT-like three-segment token
- `/api/admin/auth`

#### Partial/legacy `E:` backend

- `Authorization: Bearer`
- custom two-segment signed token
- `/admin/auth`
- company returned as `local_bookings`

#### Impact

If the partial backend is mistaken for the canonical project, authorization code, token parsing and testing appear to behave differently and produce false conclusions.

#### Required remediation

Do not use the `E:` backend to validate the production frontend. Archive it or label it clearly. Authentication parity should be assessed between the canonical `F:` project and Cloud Run.

---

### BE-013 — Partial/Legacy Backend Remains Runnable

**Severity:** Medium

The separate `E:` backend exposes nine paths and lacks most MVP resources, including providers, categories, locations, add-ons, flexible availability search, dashboard bootstrap, lifecycle actions, notifications and relationships.

Because it is runnable and contains seeded credentials, it can easily be mistaken for the actual local environment. Normal development and testing must use `F:\Projects\fastapi_bookings`.

---

### BE-014 — Credentials From the Wrong Backend Were Applied to Cloud Run

**Severity:** Medium

`admin / admin123` is seeded in the separate `E:` backend's SQLite database and successfully authenticates against that backend's `/admin/auth`. This does not prove that those credentials belong to `F:\Projects\fastapi_bookings` or Cloud Run.

The canonical `F:` project's provisioning and authentication data must be checked independently. Production accounts require explicit tenant provisioning. Development credentials must be clearly labelled and must never be deployed as production defaults.

---

### BE-015 — Inconsistent OpenAPI Security Requirements

**Severity:** Medium

Some public routes are described without required token headers, while public bootstrap, UI configuration, availability and booking routes require `X-Token`. Runtime behaviour produced HTTP 500 rather than a controlled missing-auth response.

Every operation must declare its real security requirements. Contract tests must compare documentation with runtime responses.

---

### BE-016 — Incorrect Error Semantics

**Severity:** Medium

Expected failures currently become generic HTTP 500 responses. This was confirmed for Cloud Run authentication and public services.

Adopt one structured error envelope:

```json
{
  "ok": false,
  "error": {
    "code": "STABLE_MACHINE_CODE",
    "message": "Safe user-facing summary",
    "details": {},
    "request_id": "trace-id"
  }
}
```

Map domain outcomes to 400, 401, 403, 404, 409, 422 and 429 as appropriate. Reserve 500 for unhandled faults and log the underlying exception with the request ID.

---

### BE-017 — Incomplete Relationship Contract

**Severity:** Medium

The deployed API provides Service-to-Provider and Service-to-Category relationship routes. The MCD also requires canonical relationships for:

- Service-to-Add-on;
- Location-to-Provider;
- Location-to-Service;
- optional Location-to-Category.

Each relationship must be stored once, editable from either related entity and reflected consistently after mutation.

---

### BE-018 — Partial/Legacy Response Envelope Divergence

**Severity:** Low

The canonical deployed API generally documents `{ok, data, meta}` envelopes. The separate `E:` backend returns direct arrays and direct objects.

No canonical frontend adapter should target the `E:` envelope. Remove the obsolete adapter and validate the canonical `F:` runtime responses against its OpenAPI.

---

### BE-019 — Partial/Legacy Booking Schema and State Divergence

**Severity:** Low

The deployed/canonical contract uses fields such as `start_time`, `end_time` and a booking status state machine. The separate `E:` API uses `start_datetime`, `end_datetime`, `is_confirmed` and a different create request.

The `F:`/Cloud contract is the relevant state model. The separate `E:` model must not influence the production frontend. The required lifecycle remains:

- pending;
- confirmed;
- cancelled;
- completed;
- no-show;
- rescheduled where represented as a transition/event.

Lifecycle operations must be explicit, permission-scoped and concurrency-safe.

---

### BE-020 — Partial/Legacy Health and Readiness Inconsistency

**Severity:** Low

The deployed/canonical contract includes `/health`, `/ready` and `/version`. The separate `E:` API returned 404 for `/health` while `/openapi.json` was available.

The canonical `F:` runtime should be checked against Cloud Run for identical:

- liveness;
- readiness;
- version/commit;
- database migration state;
- required-secret configuration state.

Readiness must fail when critical configuration such as database connectivity or `PUBLIC_API_KEY` is missing.

---

## 5. Recommended Remediation Sequence

### Phase 1 — Lock the canonical environment

1. Record `F:\Projects\fastapi_bookings` as the canonical local source.
2. Remove or clearly archive the separate partial `E:` API from the normal development path.
3. Run the `F:` application locally with its development database and secrets.
4. Retain OpenAPI parity CI; path/method parity is currently verified.

### Phase 2 — Restore baseline reliability

1. Fix Cloud Run `/api/public/services` HTTP 500.
2. Fix `/api/admin/auth` error semantics and provision a real owner account.
3. Add health/readiness dependency checks.
4. Standardise success and error envelopes.

### Phase 3 — Close booking-policy blockers

1. Add persistent client management restriction.
2. Add Management Review Requests.
3. Implement atomic deposit payment plus booking confirmation.
4. Implement idempotency and uncertain-result reconciliation.
5. Prove no unpaid holds.

### Phase 4 — Complete scheduling and configuration

1. Add company-hours and provider override model.
2. Add Ignore Company Hours.
3. Add booking horizon.
4. Add business profile.
5. Add notification settings/templates.
6. Complete canonical relationship routes.

### Phase 5 — Governance and release

1. Approve retention/deletion policy.
2. Add audit events for privileged changes.
3. Run tenant-boundary and staff-ownership security tests.
4. Run payment concurrency/idempotency tests.
5. Regenerate OpenAPI and TypeScript client.
6. Run the complete frontend MCD acceptance suite.

---

## 6. Minimum Backend Release Gate

Production release must not proceed until all of the following are true:

- [x] Canonical local and Cloud OpenAPI path/method contracts match: 120 paths, zero missing paths, zero method differences.
- [ ] Public services/bootstrap/availability return deterministic non-500 results.
- [ ] Production owner login succeeds; invalid credentials return 401.
- [ ] Tenant mismatch and cross-tenant identifiers are rejected.
- [ ] Staff only receive their own bookings/clients and cannot delete records.
- [ ] Client restriction is evaluated before payment and booking.
- [ ] Management review creates no payment, booking or slot reservation.
- [ ] Deposit success atomically creates one confirmed booking.
- [ ] Deposit decline creates no booking or hold.
- [ ] Duplicate checkout creates one payment and one booking.
- [ ] Company hours, provider availability, overrides, Ignore Company Hours and horizon are server-authoritative.
- [ ] Business profile and notification policy are persistable.
- [ ] Retention/deletion policy is approved and implemented.
- [ ] Health, readiness and version endpoints pass in every environment.
- [ ] Updated OpenAPI generates the frontend client without manual contract adapters.

---

## 7. Final Assessment

The frontend exposed these problems because it attempted to integrate the documented API exactly rather than concealing failures behind mock data. The canonical source has now been identified as `F:\Projects\fastapi_bookings`, and its OpenAPI path/method surface matches Cloud Run.

The remaining production issues concern runtime failures, configuration, authentication behaviour and missing booking-policy capabilities—not a canonical local-versus-cloud path divergence. Frontend workarounds must not be used to simulate client restrictions, payment authority, tenant enforcement, booking confirmation or retention policy.
