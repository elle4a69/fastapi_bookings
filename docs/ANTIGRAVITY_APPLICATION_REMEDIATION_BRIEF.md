# FastAPI Bookings — Anti-Gravity Application Remediation and Audit Control Brief

**Document role:** Authoritative remediation brief, acceptance standard, and future audit reference
**Audience:** Anti-Gravity implementers, reviewers, auditors, and maintainers
**Prepared:** 2026-08-29 (Australia/Sydney)
**Audit baseline branch:** `telemetry/observability-baseline`
**Audit baseline commit:** `350d72466410d51b272569038f10e00f8e77e297`
**Baseline worktree:** Dirty; the worktree contained pre-existing staged, unstaged, and untracked changes when this brief was prepared
**Canonical application:** This FastAPI Bookings repository only

---

## 1. Purpose and authority

This document gives Anti-Gravity a complete, ordered remediation programme for the confirmed application risks identified during the 2026-08-29 comprehensive audit. It also defines the evidence an implementer must produce and the method a later auditor must use to independently verify any claimed remediation.

This is not a request to repair every finding in one uncontrolled change. Each work package below is a separate, coherent task with its own changed-file allowlist, regression tests, runtime proof, review, and commit. Critical containment work comes first. Unrelated cleanup must not be folded into a security or tenant-isolation fix.

The repository `AGENTS.md` remains mandatory. If this brief and `AGENTS.md` appear to conflict, the stricter safety, privacy, tenant-isolation, external-action, or change-control requirement controls. The user must explicitly authorize any production action, external customer contact, live SMS, real booking, payment, refund, destructive database operation, history rewrite, deployment, push, or broad deletion.

### 1.1 Intended outcomes

The remediation programme is complete only when:

1. Administrative access cannot be obtained through a development token, tenant fallback, or predictable deployment secret.
2. Payment state changes are authenticated, signed, tenant-scoped, idempotent, auditable, and derived from server-authoritative commercial data.
3. No request, background job, webhook, message, credential, or diagnostic can cross a tenant boundary.
4. Every external delivery is claimed atomically and is safe under retries, crashes, and multiple workers.
5. Tests cannot contact live providers, even if a developer machine contains valid credentials.
6. Credentials and webhook secrets fail closed, are never returned or logged, and have a documented rotation path.
7. A clean checkout can be built, migrated, tested, started, and health-checked reproducibly.
8. The frontend uses real authentication and has automated coverage for critical workflows.
9. Release claims are supported by independently reproducible evidence rather than green imports or broad statements.

### 1.2 Explicit non-goals

- Do not split the application into microservices merely to address these findings. The modular-monolith architecture remains suitable.
- Do not revive, copy, import, inspect for implementation, or depend on the obsolete Assistant UI or `integrations/assistant-ui-v2/`.
- Do not invent replacement APIs to conceal frontend/backend mismatches.
- Do not add payment, refund, cancellation, confirmation, SMS, or external-provider behavior beyond the minimum approved remediation.
- Do not combine unrelated onboarding, website-builder, Codex-control, hold-retirement, telemetry, or UI redesign work with critical security fixes.
- Do not purge Git history, delete tracked artifacts, rotate real credentials, or alter production infrastructure without explicit authorization and a recovery plan.

---

## 2. System context and architectural position

FastAPI Bookings is the source of truth for tenants, users, services, providers, availability, bookings, customers, payments, notifications, SMS, AI orchestration, arrival workflows, and Chatwoot integration. Chatwoot is a messaging channel and staff inbox, not the booking authority.

The application is a modular monolith:

- FastAPI routes under `app/api/routers/`
- cross-cutting dependencies and configuration under `app/api/deps.py` and `app/core/`
- SQLAlchemy models under `app/models/`
- business and integration services under `app/services/`
- Alembic migrations under `alembic/versions/`
- React/Vite administration and public booking UI under `frontend/src/`
- backend tests under `tests/`

The architectural shape is acceptable. The central weakness is inconsistent enforcement of authentication, tenant scope, secret handling, idempotency, and external-action safety across subsystems. The remediation should centralize those policies and apply them consistently, not introduce new distributed-system boundaries.

---

## 3. Audit baseline and verified evidence

The audit used read-only source inspection and isolated local verification. It did not load the repository `.env`, inspect customer databases or browser-profile contents, contact external providers, send SMS, create real bookings, run payments, deploy, or alter existing listeners.

### 3.1 Verification results at baseline

| Check | Baseline result | Interpretation |
|:---|:---|:---|
| Backend suite | `268 passed in 27.40s` | Functional baseline is strong, but some tests encode unsafe behavior |
| Frontend lint | Passed | No current Oxlint errors |
| Frontend TypeScript no-emit check | Passed | Static TypeScript compilation succeeds |
| Python `pip check` | Passed | Installed environment has no broken dependency requirements |
| Alembic heads | One head | The observed head was an untracked worktree migration, so the branch was not reproducible |
| Root npm production audit | No reported vulnerabilities | Point-in-time registry result |
| Frontend npm production audit | React Router advisory reported | Upgrade available; observed app does not appear to use the affected unstable RSC path |
| Python vulnerability audit | Not run | `pip-audit` was not installed and dependencies were not locked |
| Backend static security/type tools | Not run | Ruff, mypy, Bandit, and pip-audit were not installed or configured |

### 3.2 Worktree qualification

At preparation time, the worktree contained 13 tracked changes and 17 untracked files. These included deleted Codex files/tests, staged release-gate and SMS-test changes, modified telemetry/config/model registration, and untracked onboarding, website-builder, AI-governance, Codex-control, migration, runbook, and test files.

Every implementer and auditor must distinguish:

- defects present in the committed baseline;
- risks introduced only by the dirty worktree;
- remediation changes made by the current task; and
- unrelated user-owned changes that must be preserved.

No result may be attributed to a commit unless the exact commit was checked out or its diff was independently reconstructed.

---

## 4. Severity, status, and evidence vocabulary

### 4.1 Severity

| Severity | Meaning |
|:---|:---|
| Critical | Direct administrative compromise, payment/booking state forgery, cross-tenant disclosure/action, external-action duplication, or credential compromise |
| High | Serious privacy, isolation, deployment, SSRF, test-safety, or operational-integrity risk requiring remediation before production release |
| Medium | Material maintainability, resilience, auditability, dependency, or user-experience weakness |
| Low | Hygiene or documentation issue with limited immediate runtime impact |

### 4.2 Remediation status

Use only these states in future reports:

- **Not started** — baseline behavior remains.
- **In progress** — implementation exists but evidence is incomplete.
- **Remediated, unverified** — author reports completion; independent audit has not proved it.
- **Verified** — independent review reproduced all required positive and negative evidence.
- **Reopened** — claimed remediation is incomplete, regressed, bypassable, or caused a new defect.
- **Accepted risk** — the user explicitly accepted a documented residual risk, owner, scope, and review date.

### 4.3 Evidence confidence

- **High:** direct source, diff, test, HTTP, database, or runtime evidence.
- **Medium:** multiple consistent static signals without end-to-end reproduction.
- **Low:** plausible inference requiring further proof.

An item cannot be marked **Verified** with low-confidence evidence.

---

## 5. Master findings register

Line anchors below identify the audited snapshot and will drift after remediation. Paths and behavior are the durable evidence anchors.

| ID | Severity | Baseline status | Finding | Primary evidence |
|:---|:---|:---|:---|:---|
| AUTH-001 | Critical | Not started | Backend accepts the hard-coded `mock-admin-token` outside a test-only guard | `app/api/deps.py` |
| AUTH-002 | Critical | Not started | Frontend supplies `mock-admin-token` whenever no real token exists and defaults tenant to `simplydemo` | `frontend/src/lib/api.ts` |
| AUTH-003 | High | Not started | Missing tenant context can resolve the first tenant; administrative login is not covered by the public rate-limit middleware | `app/api/deps.py`, `app/main.py` |
| AUTH-004 | Medium | Not started | Seven-day symmetric JWTs lack issuer/audience/token-type controls; browser tokens are stored in `localStorage` | `app/core/security.py`, `frontend/src/lib/api.ts` |
| PAY-001 | Critical | Not started | Deposit-session creation is unauthenticated, not tenant-scoped, and accepts caller-controlled booking ID, amount, and redirect URLs | `app/api/routers/stripe_webhooks.py` |
| PAY-002 | Critical | Not started | Missing Stripe webhook secret causes signature verification to be bypassed | `app/api/routers/stripe_webhooks.py` |
| PAY-003 | Critical | Not started | Forged Stripe events can confirm/cancel unscoped bookings and enqueue customer SMS; event idempotency and provider-object reconciliation are absent | `app/api/routers/stripe_webhooks.py`, `tests/test_phase_5_6_7.py` |
| TEN-001 | Critical | Not started | Outbound webhook dispatch matches event type but not event tenant, enabling cross-tenant payload delivery | `app/services/outbox_worker.py` |
| TEN-002 | Critical | Not started | Webhook list/update/delete operations are not tenant-scoped | `app/api/routers/webhooks.py` |
| TEN-003 | Critical | Not started | Webhook API responses include stored signing secrets | `app/schemas/webhook.py` |
| TEN-004 | High | Not started | Calendar notes have no tenant column and admin CRUD is global | `app/models/calendar_note.py`, `app/api/routers/calendar_notes.py` |
| TEN-005 | High | Not started | GDPR consent creation and listing are globally keyed by client ID; the model has no tenant column | `app/models/general_systems.py`, `app/api/routers/general_systems.py` |
| TEN-006 | High | Not started | Public timeline endpoints resolve provider/service IDs without an active tenant | `app/api/routers/public_timeline.py` |
| TEN-007 | High | Not started | Admin diagnostics report global entity and queue counts to any tenant admin | `app/api/routers/diagnostics.py` |
| TEN-008 | High | Not started | Device registration is unauthenticated, globally upserts by token, accepts arbitrary user/client IDs, and does not set tenant ID | `app/api/routers/devices.py` |
| TEN-009 | High | Not started | Notification logs/preferences and several SMS child/job tables lack direct tenant ownership, increasing the chance of unscoped access and difficult policy enforcement | `app/models/notification.py`, `app/models/sms_outbox.py` |
| SEC-001 | Critical | Not started | SMS credential encryption reads raw environment variables and can use a known fallback key | `app/models/sms_account.py` |
| SEC-002 | Critical | Not started | SMS and Chatwoot credential setters store plaintext when encryption fails | `app/models/sms_account.py`, `app/models/sms_chatwoot.py` |
| SEC-003 | High | Not started | Chatwoot webhook URLs contain decrypted secrets in query strings and the receiver accepts query tokens | `app/api/routers/sms_chatwoot.py` |
| SEC-004 | High | Not started | Webhook target URLs are unconstrained strings; outbound delivery permits SSRF to internal/link-local destinations | `app/schemas/webhook.py`, `app/services/outbox_worker.py` |
| SEC-005 | High | Not started | Exception strings and tracebacks can place phone numbers, provider errors, URLs, or other private material in console logs and persistent error fields | `app/main.py`, `app/services/outbox_worker.py`, `app/services/sms/outbox_worker.py` |
| SEC-006 | High | Not started | Docker build context lacks `.dockerignore`, exposing ignored local secrets, databases, browser state, and media to the builder context | repository root, `Dockerfile` |
| DEL-001 | Critical | Not started | Generic outbox delivery has no atomic claim/lease; multiple processes can deliver the same external action | `app/services/outbox_worker.py` |
| DEL-002 | High | Not started | Every FastAPI process starts its own generic and SMS worker; web and worker lifecycle/scaling are coupled | `app/main.py`, `app/services/outbox_worker.py` |
| DEL-003 | High | Not started | Unknown outbox event types are marked processed instead of quarantined or failed | `app/services/outbox_worker.py` |
| DEL-004 | High | Not started | Generic webhook dispatch lacks per-destination delivery records and idempotency keys, so partial fan-out failure retries successful destinations | `app/services/outbox_worker.py` |
| TEST-001 | Critical | Not started | A backend test intentionally processes a `SEND_SMS` event without a mandatory provider mock and may use live credentials | `tests/test_phase_5_6_7.py` |
| TEST-002 | High | Not started | The suite positively asserts unsigned Stripe webhook acceptance and booking confirmation | `tests/test_phase_5_6_7.py` |
| TEST-003 | High | Not started | Existing tenant tests cover core catalog/booking paths but omit webhook, calendar-note, GDPR, diagnostics, timeline, and device boundaries | `tests/` |
| TEST-004 | Medium | Not started | No frontend unit/component/E2E test configuration or test files were found | `frontend/` |
| TEST-005 | Medium | Not started | No configured coverage threshold, backend lint/type gate, or automated security scan exists | repository root |
| OPS-001 | Critical if used | Not started | Compose declares production while providing predictable JWT/public API secrets and database credentials | `docker-compose.yml`, `app/core/config.py` |
| OPS-002 | High | Not started | Compose maps port 8000 to container port 8000 while the image listens on 8080 | `docker-compose.yml`, `Dockerfile` |
| OPS-003 | High | Not started | Docker image does not include/run Alembic; a clean deployment cannot prove schema readiness | `Dockerfile` |
| OPS-004 | High | Not started | `/ready` checks only `SELECT 1`, so it succeeds when required tables or migration revision are absent | `app/main.py` |
| OPS-005 | High | Not started | Empty-database migration path uses `Base.metadata.create_all()` and stamps head, bypassing revision execution and migration semantics | `alembic/env.py` |
| OPS-006 | High | Not started | Image uses an unpinned floating base, runs as root, has no image healthcheck, and contains no production worker/migration contract | `Dockerfile` |
| OPS-007 | High | Not started | No CI pipeline exists; dependencies use open-ended minimum versions and no lock/constraint file | `.github/` absent, `requirements.txt` |
| OPS-008 | Medium | Not started | `cryptography` is directly imported but undeclared; `httpx2` is declared but unused; development/test dependencies are not reproducible | `requirements.txt`, `app/models/` |
| OPS-009 | Medium | Not started | Frontend lockfile reports a fixable React Router advisory; practical RSC exploitability appears low but the dependency remains outdated | `frontend/package-lock.json` |
| REPO-001 | High | Not started | Thousands of generated Allure/browser/log artifacts and roughly 266 MB of unrelated media are committed | repository index |
| REPO-002 | High | Not started | Tracked browser profiles and logs may contain private operational or session material; contents were intentionally not inspected during audit | `playwright_session/`, tracked logs |
| DOC-001 | Medium | Not started | Root README describes a Vertex AI Node proxy rather than the FastAPI Bookings application | `README.md` |
| DOC-002 | High | Worktree-only | Current untracked runbook assumes seven workers, references obsolete/unwired systems, and does not describe safe delivery-worker ownership | `docs/OPERATIONS_RUNBOOK.md` |
| FE-001 | Critical | Not started | Admin UI has no trustworthy login boundary because the shared client auto-injects the bypass token | `frontend/src/lib/api.ts`, `frontend/src/App.tsx` |
| FE-002 | Medium | Not started | Shared pagination helper suppresses API failures and returns partial/empty data | `frontend/src/lib/api.ts` |
| FE-003 | Medium | Not started | Frontend contains 292 `any` references, 258 API-call sites, no tests, and multiple 1,000–2,100-line pages | `frontend/src/` |
| ARCH-001 | Medium | Not started | Cross-cutting security and tenant policy is repeated per router instead of enforced through shared scoped dependencies/repositories | `app/api/routers/` |
| ARCH-002 | Medium | Not started | Large route and service modules combine validation, persistence, state transition, delivery, and response mapping | `checkout.py`, `booking_forms.py`, `bookings.py`, SMS services |
| WORK-001 | High | Worktree-only | The only observed Alembic head is an untracked migration, so current state is not reproducible from the branch | `alembic/versions/a0dcb6b91db5_*.py` |
| WORK-002 | High | Worktree-only | Untracked onboarding and website routes are unwired, unauthenticated, keyed by caller-controlled user IDs, and backed by process-local memory | untracked routers/services |
| WORK-003 | High | Worktree-only | One untracked migration combines four new subsystems with destructive removal of `holds`, violating coherent-scope change control | `alembic/versions/a0dcb6b91db5_*.py` |
| WORK-004 | Medium | Worktree-only | Model registration contains duplicate imports and imports untracked models, making test/migration behavior depend on local files | `app/models/__init__.py` |

---

## 6. Mandatory remediation programme

Each work package must begin with branch/status inspection, an explicit changed-file allowlist, and focused baseline reproduction. Each must finish with changed-file review, explicit path staging, focused tests, the relevant full gate, runtime evidence where required, and a single-purpose commit.

### Phase 0 — Immediate containment and release freeze

Until Phase 0 and Phase 1 are independently verified:

- do not deploy the audited Compose configuration;
- do not enable Stripe or accept payment webhooks;
- do not run multiple application workers against an outbox containing real external actions;
- do not run the unsafe SMS test in an environment with credentials or network access;
- do not expose the admin UI to untrusted users;
- do not treat the current green suite as a release authorization.

If any audited configuration has been exposed publicly, separately assess whether JWT, Stripe, Chatwoot, SMS, webhook, database, Firebase, OpenAI, or other credentials require rotation. Rotation is an externally consequential task and requires explicit authorization.

### Work package A — Remove the administrative bypass

**Findings:** AUTH-001, AUTH-002, FE-001, part of AUTH-003
**Priority:** P0
**Goal:** Every administrative operation requires a valid authenticated user bound to the selected tenant.

Required behavior:

1. Delete production/runtime recognition of `mock-admin-token` from `get_current_user` and `get_public_tenant`.
2. Remove the frontend fallback token. Absence of a token must produce an unauthenticated state and route to a real login flow or explicit access-denied screen.
3. Do not use environment-gated magic tokens as the final design. Tests must generate signed tokens or override the authentication dependency locally.
4. Reject missing tenant context in non-development runtime. Any local single-tenant convenience must be explicit, testable, and impossible in production.
5. Ensure user lookup, role authorization, and tenant lookup are evaluated together. A valid token for tenant A must not work with tenant B headers, hostnames, query parameters, or IDs.
6. Ensure inactive/deleted tenants or users cannot authenticate if those lifecycle states are introduced.
7. Add admin-login brute-force protection with a key that does not collapse all users behind one reverse proxy. Document trusted-proxy handling.

Required negative tests:

- `mock-admin-token` receives 401 in development, test, and production settings unless a test dependency override is installed in-process.
- missing token receives 401 for every admin route family;
- malformed, expired, wrong-signature, wrong-audience/type, and cross-tenant tokens receive 401;
- staff role receives 403 on owner/admin-only operations;
- missing/unknown tenant does not fall back to the first tenant;
- frontend makes no admin request with a fabricated fallback token.

Acceptance evidence:

- focused auth and multi-tenancy tests;
- an OpenAPI/admin-route inventory showing the authentication dependency on every admin operation;
- HTTP smoke evidence for login, authenticated access, unauthenticated denial, and cross-tenant denial;
- browser proof that unauthenticated admin navigation is redirected or denied without leaking a token.

Prohibited shortcuts:

- renaming the magic token;
- accepting the token only when `APP_ENV != production` as the final remediation;
- returning the first user/tenant from the database;
- weakening admin roles to make frontend calls pass.

### Work package B — Make payment processing fail closed

**Findings:** PAY-001, PAY-002, PAY-003, TEST-002
**Priority:** P0
**Goal:** No caller can forge or arbitrarily price a payment, confirmation, cancellation, refund, or SMS side effect.

Required behavior:

1. If payment support is not explicitly approved, remove or disable the Stripe mutation routes and return a clear unavailable response without changing records.
2. If approved, authenticate deposit-session creation and bind it to a tenant-authorized booking/client workflow.
3. Calculate currency and amount from server-authoritative booking/service/deposit policy. Never accept an arbitrary amount as the source of truth.
4. Validate success/cancel destinations against a configured frontend origin or use server-generated destinations.
5. Require a configured Stripe webhook secret in every environment that mounts the route. Missing secret must fail startup or return service unavailable; it must never accept unsigned JSON.
6. Verify the Stripe signature before parsing or acting on the event.
7. Store and enforce unique provider event IDs. Duplicate delivery must be a no-op with an auditable duplicate result.
8. Retrieve and reconcile the Stripe object/session against the stored booking, tenant, currency, amount, and expected payment state.
9. Tenant-scope every booking/payment lookup. Never trust tenant ID from provider metadata as authorization.
10. Perform payment record change, booking state transition, audit entry, and outbox enqueue in one designed transaction with explicit failure semantics.
11. Do not enqueue live SMS from tests. Use an outbox assertion with a fake transport.

Required tests:

- unsigned, missing-signature, invalid-signature, stale/tampered, unknown-event, duplicate-event, wrong-tenant, wrong-booking, wrong-amount, wrong-currency, and invalid-transition cases;
- two simultaneous identical events result in one state transition and one notification intent;
- database failure rolls back payment, booking, audit, and outbox changes;
- arbitrary URLs and amounts are rejected;
- no test performs a provider network call.

Runtime proof must use Stripe test fixtures or a fully local fake with labelled synthetic data. No real payment, refund, booking confirmation, cancellation, or customer contact is authorized by this brief.

### Work package C — Repair webhook tenant isolation and SSRF safety

**Findings:** TEN-001, TEN-002, TEN-003, SEC-004, DEL-004
**Priority:** P0
**Goal:** Each domain event reaches only destinations owned by the same tenant, without leaking secrets or accessing protected network targets.

Required behavior:

1. Tenant-scope list, create, get, update, and delete operations.
2. Never include stored webhook secrets in list/get/update responses. Use `has_secret`, a one-time secret presentation at creation if required, or a rotate operation that never stores a retrievable plaintext representation.
3. Change `target_url` to a validated HTTPS URL contract for production.
4. Resolve and reject loopback, private, link-local, multicast, unspecified, metadata-service, and otherwise prohibited targets for both IPv4 and IPv6. Revalidate redirects and DNS resolution at dispatch time to address rebinding.
5. Match `WebhookRegistration.tenant_id == OutboxEvent.tenant_id` during dispatch.
6. Require a non-null tenant for tenant-owned event types; quarantine legacy/null events instead of broadcasting them.
7. Introduce per-event/per-destination delivery state with a unique constraint so retries do not resend to destinations that already succeeded.
8. Sign a canonical byte payload and document the signature version, timestamp, replay window, and key rotation behavior.
9. Do not log target query strings, secrets, payloads, or customer data.

Required tests:

- two tenants with the same event subscription receive only their own events;
- tenant B cannot list/read/update/delete tenant A registrations;
- responses never contain a stored secret;
- internal, localhost, link-local, IPv6-local, redirect-to-private, and DNS-rebinding candidates are rejected;
- one destination succeeds and one fails, then retry contacts only the failed destination;
- duplicate worker execution creates one delivery per event/destination.

### Work package D — Make all outbox delivery single-owner and idempotent

**Findings:** DEL-001, DEL-002, DEL-003, DEL-004, SEC-005
**Priority:** P0
**Goal:** External delivery is safe under concurrency, retries, process crashes, and horizontal scaling.

Required behavior:

1. Separate web-process lifecycle from worker ownership. A deployment must explicitly run the intended number of web and worker processes.
2. Add atomic database claim/lease fields and transitions to the generic outbox, including lease owner, lease expiry, next-attempt time, terminal state, and safe retry count.
3. Claim work with database semantics suitable for PostgreSQL, such as `FOR UPDATE SKIP LOCKED` or an atomic conditional update. Prove the chosen mechanism with concurrent workers.
4. Use stable idempotency keys for each provider action and persist provider/delivery identifiers where available.
5. Define exponential backoff with bounded jitter, terminal failure/dead-letter handling, and operator retry rules.
6. Treat unknown event types as failed/quarantined. Never silently mark them processed.
7. Store only privacy-safe structured failure codes. Raw tracebacks, response bodies, phone numbers, message bodies, authorization data, and URLs with query strings must not enter logs or error columns.
8. Ensure shutdown returns or expires leases safely.
9. Ensure one poison event cannot block unrelated tenant events.

Required tests:

- 20 concurrent workers claim a single event and exactly one fake delivery occurs;
- process failure before send, during send, and after provider success/before commit has documented behavior;
- expired lease recovery works;
- retry timing and terminal failure are deterministic under a fake clock;
- unknown type is quarantined;
- log/error privacy tests prove redaction and structural allowlisting;
- tenant A poison jobs do not block tenant B.

### Work package E — Repair credential and webhook-secret handling

**Findings:** SEC-001, SEC-002, SEC-003
**Priority:** P0
**Goal:** Secrets use explicit key management, fail closed, never appear in responses/query strings/logs, and can be rotated safely.

Required behavior:

1. Centralize encryption/decryption in a service that uses one validated application key source. Do not derive encryption from the public API key.
2. Require an encryption key in any environment that stores credentials. Missing or invalid key must prevent the write/startup as appropriate.
3. Remove plaintext fallback behavior. Encryption failure must roll back and return a safe error.
4. Version ciphertext envelopes so keys and algorithms can be rotated.
5. Plan migration of existing plaintext/fallback-key ciphertext without exposing values in logs, migrations, diffs, or responses.
6. Use header-based or signed-body Chatwoot webhook authentication. Do not generate or accept query-string secrets.
7. Compare secrets in constant time after resolving the tenant/binding through a non-secret public identifier.
8. Mask credentials using explicit response schemas. `has_credentials` must not trigger decryption merely to render a list.
9. Define rotation, revocation, recovery, and audit behavior.

Required tests:

- known fallback keys cannot decrypt new data;
- missing key prevents storage;
- injected encryption failure stores nothing;
- responses and telemetry contain no secret or ciphertext fragment;
- old/new versioned keys decrypt only as designed during rotation;
- query tokens are rejected;
- Chatwoot bindings remain tenant/provider isolated.

### Work package F — Make tests incapable of live external action

**Findings:** TEST-001, TEST-002, TEST-003
**Priority:** P0
**Goal:** A test run is safe even when the host has valid production credentials and unrestricted network access.

Required behavior:

1. Remove the test that may call ClickSend or replace the client at the integration boundary with a mandatory fake.
2. Add an autouse network-denial fixture for backend tests, with narrow explicit opt-in only for dedicated local integration tests.
3. Override provider clients before application lifespan workers can start.
4. Use unmistakably synthetic reserved/example addresses and identities. Never use a plausible real customer number.
5. Cancel or drain synthetic AI/outbox jobs created by tests.
6. Replace unsigned-Stripe success assertions with fail-closed assertions.
7. Add a release-gate test that fails if real provider endpoints or non-test credentials are referenced during tests.

Acceptance evidence includes a full suite run with deliberately populated fake-looking provider environment variables and a network trap proving zero outbound connection attempts.

### Work package G — Complete the tenant-isolation sweep

**Findings:** AUTH-003, TEN-004 through TEN-009, TEST-003, ARCH-001
**Priority:** P1, immediately after P0
**Goal:** Tenant ownership is structurally represented and enforced for every tenant-owned row and request.

Required behavior:

1. Produce a model/route/service matrix identifying the owner of every table and every route.
2. Add explicit non-null tenant ownership where appropriate to calendar notes, GDPR consents, device tokens, notification logs/preferences, and other tenant-owned child/job/event tables.
3. Backfill only after a deterministic, auditable ownership rule is proved. Abort migration on ambiguous or orphaned rows; do not assign everything to the first tenant.
4. Add foreign keys and uniqueness constraints that include tenant where business uniqueness is tenant-local.
5. Tenant-scope public timeline service/provider/schedule resolution.
6. Tenant-scope diagnostics and return only the active tenant's structural counts.
7. For public GDPR consent, resolve the tenant and client from an authenticated/session-bound context. Do not trust arbitrary client ID or caller-supplied IP as audit truth.
8. Authenticate device registration to the client/user and derive owner IDs from the authenticated principal.
9. Prefer shared scoped-query helpers/repositories where they reduce omission risk, while keeping queries explicit and testable.
10. Return 404 rather than revealing the existence of another tenant's record.

Required verification:

- per-subsystem two-tenant CRUD and direct-ID attack tests;
- property/fuzz tests across header, query, host, token, child ID, and parent ID mismatches;
- migration tests for clean, populated, orphaned, and ambiguous datasets;
- PostgreSQL runtime verification, not SQLite-only proof;
- a final grep/AST-assisted query inventory manually reviewed for unscoped tenant-owned lookups.

### Work package H — Repair deployment, migration, and readiness contracts

**Findings:** OPS-001 through OPS-006, SEC-006
**Priority:** P1
**Goal:** A clean checkout produces a hardened image that migrates and starts predictably with fail-closed configuration.

Required behavior:

1. Remove known secrets and credentials from Compose. Use environment/secret injection and fail validation on placeholder or insufficient secrets.
2. Correct host/container ports and document backend/frontend URLs.
3. Add `.dockerignore` covering `.git`, `.env*` except an approved example, credentials, databases, backups, browser profiles, logs, test artifacts, virtual environments, node modules, local media, scratch data, obsolete integrations, and build output.
4. Pin the Python base image by supported patch version and preferably digest through an approved update process.
5. Run as a non-root user with minimal filesystem permissions.
6. Include Alembic and the migration files in the deployment artifact.
7. Define who runs migrations, exactly once, before traffic. Do not run competing auto-migrations in every web process.
8. Remove the empty-database `create_all`/stamp shortcut. A clean database must be constructed through a reviewed migration baseline/revision sequence.
9. Make readiness verify database connectivity, expected Alembic revision, and required core schema without exposing sensitive details.
10. Keep liveness independent of transient downstream providers.
11. Configure web and outbox/SMS workers as distinct process roles.
12. Add timeouts and graceful shutdown budgets.

Required verification:

- `docker compose config` contains no literal secret values;
- image history and filesystem scan contain no local secrets or unwanted artifacts;
- clean disposable PostgreSQL database upgrades to head and serves authenticated smoke requests;
- an intentionally unmigrated database fails readiness;
- rollback/forward migration behavior is tested where supported;
- container listens on the documented port and runs as non-root;
- two web processes do not create two worker loops;
- configuration errors fail before serving traffic.

### Work package I — Establish reproducible CI and dependency governance

**Findings:** OPS-007 through OPS-009, TEST-005
**Priority:** P1
**Goal:** Every proposed change is evaluated by a repeatable release pipeline.

Required behavior:

1. Separate runtime and development/test dependencies.
2. Directly declare every imported runtime package, including `cryptography` if retained.
3. Remove unused dependencies such as `httpx2` unless code and an architectural decision justify them.
4. Use a reviewed lock/constraints mechanism with hashes where practical.
5. Add CI gates for formatting/lint, backend type checking, Bandit or equivalent static security analysis, pip vulnerability audit, tests, coverage threshold, migration checks, frontend lint/type/build/tests, npm audit policy, and secret scanning.
6. Pin CI actions and container images to reviewed immutable revisions.
7. Document vulnerability triage: affected component, reachability, compensating controls, owner, target version, and deadline.
8. Upgrade React Router to a patched supported release and rerun browser/frontend tests.
9. Do not auto-apply major dependency upgrades without focused runtime verification.

### Work package J — Establish a real frontend authentication and test boundary

**Findings:** FE-001 through FE-003, TEST-004, AUTH-004
**Priority:** P1/P2 after backend auth contract is fixed
**Goal:** The frontend does not manufacture authority and critical user workflows are covered by tests.

Required behavior:

1. Implement a real login/logout/session-expiry flow against the canonical backend contract.
2. Prefer an approved secure session design. If bearer tokens remain, document XSS controls and avoid indefinite `localStorage` authority.
3. Separate public and admin API clients so public routes do not receive admin credentials by default.
4. Centralize tenant resolution and reject ambiguous host/header states.
5. Do not swallow pagination/API errors. Return typed partial/failure state and show it to the user.
6. Generate or share typed API contracts where practical; progressively remove `any` from boundary code first.
7. Add unit tests for the API client and auth state; component tests for error/loading/permission states; and synthetic E2E journeys for login, tenant isolation, booking, admin catalog, SMS approval, and logout/session expiry.
8. Split very large pages along stable domain/state boundaries after regression coverage exists.

Required gates:

- lint, TypeScript build, production Vite build, unit/component tests, and E2E tests;
- browser inspection proving no magic token, query secret, authorization value, or customer data appears in URL, console, storage beyond the approved session design, or telemetry;
- API contract sweep against generated OpenAPI.

### Work package K — Repository privacy and hygiene

**Findings:** REPO-001, REPO-002, DOC-001
**Priority:** P2; history rewrite requires separate authorization
**Goal:** The repository contains only source, migrations, tests, approved fixtures, and intentional documentation/assets.

Required behavior:

1. Inventory tracked Allure output, browser profiles, logs, media, executables, archives, generated OpenAPI, and local runtime state by owner and business purpose.
2. Do not inspect or redistribute potentially private content merely to classify it. Use names, types, sizes, provenance, and owner confirmation where possible.
3. Add precise ignore rules and artifact-retention locations outside Git.
4. Remove current tracked artifacts in a recoverable, explicitly approved task.
5. Evaluate whether past commits contain secrets, cookies, session data, customer data, or licensed media. If so, prepare a history-rewrite and credential-rotation plan for user approval; do not rewrite history automatically.
6. Replace the README with accurate architecture, prerequisites, safe local setup, migrations, test commands, process roles, and links to runbooks.
7. Store generated test evidence in CI artifact storage with retention and privacy controls.

### Work package L — Resolve worktree-only onboarding/website/migration changes

**Findings:** WORK-001 through WORK-004, DOC-002
**Priority:** Separate decision before merge
**Goal:** Prevent incomplete local prototypes or mixed-scope migrations from becoming runtime dependencies.

Required decision:

1. Determine whether onboarding, website builder, AI governance, and Codex control centre are approved product scope.
2. If not approved, preserve or remove the local work only with user direction; do not stage it.
3. If approved, create separate task branches/work packages for each bounded context, with tenant/auth/data contracts and durable persistence.
4. Do not expose caller-controlled `user_id` routes without authentication and ownership checks.
5. Do not use module-global in-memory dictionaries for multi-process durable application state.
6. Split new-table creation from hold retirement. A destructive hold migration must follow the approved hold-retirement plan and its own data audit/rollback proof.
7. Ensure Alembic head exists in committed source and a clean checkout reproduces the same metadata.
8. Correct duplicate imports and keep `app/models/__init__.py` aligned only with committed models.
9. Rewrite the operations runbook only after the actual deployment topology is established; remove assumptions about obsolete or unwired systems.

### Work package M — Maintainability and architectural hardening

**Findings:** ARCH-001, ARCH-002, FE-003
**Priority:** P2/P3 after security and isolation gates
**Goal:** Reduce the chance that future changes reintroduce security and tenant omissions.

Required direction:

- keep the modular monolith;
- define shared authenticated tenant context and scoped repository/service entry points;
- keep route handlers focused on HTTP parsing, authorization, and response mapping;
- move commercial calculation, state transitions, and external orchestration into transactional services;
- split the largest modules only behind existing characterization tests;
- document decisions affecting auth, tenant ownership, outbox delivery, payments, and secret management as ADRs;
- introduce architectural tests or static checks that identify admin routes without auth and tenant-owned queries without scope;
- avoid abstractions that hide the tenant predicate or make SQL behavior harder to audit.

---

## 7. Required sequencing and dependency map

The minimum safe order is:

1. **Contain:** freeze risky deployment/payment/external test execution.
2. **Identity:** Work package A.
3. **External financial state:** Work package B.
4. **Cross-tenant webhook boundary:** Work package C.
5. **Exactly-once-effective delivery controls:** Work package D.
6. **Secrets:** Work package E.
7. **Test network isolation:** Work package F.
8. **Remaining tenant sweep:** Work package G.
9. **Deployment/migrations/readiness:** Work package H.
10. **CI/dependencies:** Work package I.
11. **Frontend auth/testing:** Work package J.
12. **Repository hygiene and worktree decisions:** Work packages K and L.
13. **Maintainability refactors:** Work package M.

Packages B, C, D, and E interact, but they must remain independently reviewable. A shared schema migration may be coordinated, yet each behavioral outcome needs its own tests and evidence. Do not create one mega-commit that makes regression attribution impossible.

---

## 8. Global release gates

All gates are cumulative. Passing a later gate does not waive an earlier one.

### Gate 1 — Change control

- current branch and `git status --short` recorded before work;
- explicit changed-file allowlist recorded;
- no unrelated user changes modified or staged;
- one coherent outcome per commit;
- `git diff --stat`, full changed-file review, and explicit path staging completed;
- commit hash and exact files reported.

### Gate 2 — Authentication and authorization

- no magic token exists in runtime or frontend source;
- every admin route requires the intended role;
- missing, invalid, expired, wrong-type, and cross-tenant credentials fail;
- production configuration rejects placeholder/weak secrets;
- login throttling works behind the intended proxy topology.

### Gate 3 — Tenant isolation

- every tenant-owned table has an ownership path;
- every read/write/delete and background dispatch uses that path;
- two-tenant direct-ID, child-ID, host/header/query, webhook, job, and diagnostic tests pass;
- no ambiguous migration backfill is silently accepted.

### Gate 4 — External-action safety

- tests have zero live network/provider actions;
- payment/SMS/Chatwoot/webhook/push actions require approved configuration;
- outbox claims and idempotency are proven under concurrency;
- retries do not duplicate successful side effects;
- unknown events fail visibly.

### Gate 5 — Privacy and secrets

- secrets never appear in API responses, URLs, logs, traces, exceptions, test artifacts, or frontend storage outside the approved design;
- customer identity, phone, email, address, booking notes, SMS bodies, and AI prompts/responses are absent from telemetry and operational errors;
- encryption failure is fail-closed;
- rotation is documented and tested.

### Gate 6 — Database and migrations

- exactly one committed Alembic head;
- clean PostgreSQL upgrade to head succeeds through migrations;
- populated upgrade test succeeds;
- downgrade/forward or documented irreversible-migration procedure exists;
- model metadata and migration schema are compared;
- readiness fails on an unmigrated schema.

### Gate 7 — API contract

- HTTP method, path, auth dependency, request schema, response schema, and error semantics verified;
- no duplicate/accidental route mounts or operation IDs;
- OpenAPI matches the runtime app;
- frontend contract sweep has zero unexplained mismatches.

### Gate 8 — Backend quality

- focused regression tests pass;
- complete suite passes in an isolated environment;
- backend lint, type, security, dependency, and coverage policy pass;
- warnings are either eliminated or explicitly reviewed;
- relevant runtime smoke test passes.

### Gate 9 — Frontend quality

- lint and TypeScript checks pass;
- production Vite build passes;
- unit/component/E2E tests pass;
- auth, tenant, error, loading, and session-expiry journeys are covered;
- dependency audit policy passes.

### Gate 10 — Deployment and operations

- image contains only intended files and no secrets;
- container runs non-root and on documented ports;
- migrations run once before traffic;
- liveness/readiness behavior is demonstrated;
- web/worker process topology is explicit;
- rollback and incident procedures match actual implementation;
- telemetry is visibly verified in the configured collector using privacy-safe synthetic events.

---

## 9. Required implementation evidence packet

Every Anti-Gravity remediation handoff must contain:

1. **Finding IDs addressed.** No vague “security cleanup” labels.
2. **Objective and non-goals.** State the exact behavior being changed.
3. **Baseline reproduction.** Show the defect before the change where safe.
4. **Changed-file allowlist.** Explain any deviation before editing further.
5. **Design decision.** Describe transaction, tenant, auth, idempotency, privacy, and failure semantics.
6. **Migration analysis.** Include data classification, backfill rule, constraints, rollback, and dialect proof if schema changes.
7. **Diff summary.** List every changed file and why it changed.
8. **Focused tests.** Include exact commands and results.
9. **Adversarial tests.** Include negative, cross-tenant, retry, concurrency, tamper, and privacy cases relevant to the finding.
10. **Full gates.** Backend suite and applicable frontend/build/security/migration gates.
11. **Runtime proof.** HTTP/process/database/provider-fake evidence appropriate to the change.
12. **External-action declaration.** Explicitly state that no live SMS/payment/booking/customer/provider action occurred.
13. **Known limitations and residual risk.** Never hide skipped checks.
14. **Repository state.** Final status, diff stat, staged paths, and unrelated changes preserved.
15. **Commit hash.** One coherent commit unless a documented migration sequence requires more.

Statements such as “imports pass,” “tests are green,” “looks tenant-scoped,” or “telemetry initialized” are insufficient without the required boundary-specific evidence.

---

## 10. Independent auditor protocol

This section governs future review of remediation performed by Anti-Gravity or any other agent.

### 10.1 Audit preparation

1. Read `AGENTS.md`, this brief, the claimed evidence packet, and the exact commit diff.
2. Record branch, commit, worktree status, environment, and excluded material.
3. Reconstruct the finding's original exploit/failure path from source. Do not rely on the implementer's summary.
4. Confirm the diff contains only the approved outcome and no hidden compatibility path or weakened authorization.
5. Identify whether current local files differ from the claimed commit.

### 10.2 Verification method

For each finding:

1. Verify the intended contract from code, schema, migrations, and product rules.
2. Review every entry point, not only the reported route.
3. Trace data from request through dependency, query, transaction, worker, provider adapter, logs, and response.
4. Test the expected success path with synthetic data.
5. Test the original exploit/failure path.
6. Test neighboring bypasses: alternate prefix, method, host, header, query, direct ID, child ID, retry, stale event, concurrency, malformed payload, and missing configuration.
7. Inspect persisted rows and outbox/delivery counts, not only HTTP status.
8. Inspect logs/traces structurally for privacy and cardinality.
9. Rerun focused tests and the applicable global gates.
10. Compare runtime OpenAPI and frontend calls where an API contract changed.
11. Record residual risk and evidence confidence.

### 10.3 Critical-finding audit questions

#### Authentication

- Can any constant, fallback, dependency override, seed token, or frontend default grant authority?
- Does tenant selection occur independently from identity validation?
- Can a token be replayed under a different host/header/query tenant?
- Are all alternate route mounts protected?

#### Payments

- Is the event signature mandatory and verified before parsing/action?
- Is the provider event unique and idempotent?
- Are amount, currency, booking, tenant, and expected state reconciled from authoritative records?
- Can any failure produce a booking/payment mismatch or duplicate SMS?

#### Webhooks and outbox

- Is tenant ID included in both selection and uniqueness constraints?
- Can two workers claim the same item?
- Can a retry resend already successful destinations?
- Can the destination reach internal infrastructure?
- Can payloads, secrets, or customer data reach logs or another tenant?

#### Credentials

- What exact key source and ciphertext version are used?
- What happens when key loading, encryption, or decryption fails?
- Can old/fallback/plaintext data still be written?
- Does any response, URL, log, trace, representation, or test artifact expose a secret?

#### Tenant migrations

- How was ownership of existing rows determined?
- What happens to ambiguous/orphaned rows?
- Do database constraints prevent future ambiguity?
- Do all parent and child queries enforce the same tenant?

### 10.4 Auditor result format

For every reviewed item, report:

| Field | Required content |
|:---|:---|
| Finding ID | Stable ID from this brief |
| Claimed status | Implementer's status |
| Audited status | Verified, Reopened, Remediated unverified, or Accepted risk |
| Evidence | Files, lines, commands, HTTP/database/runtime results |
| Confidence | High, Medium, or Low |
| Regression assessment | New failures or neighboring behavior changes |
| Residual risk | What remains and why |
| Required follow-up | Concrete next task and scope |

The auditor must lead with findings ordered by severity. Absence of findings should be stated explicitly only after all required checks were performed.

---

## 11. Regression protections that must remain green

Remediation must preserve the application's verified strengths:

- atomic first-confirmed-submission-wins booking behavior;
- booking slot-allocation integrity and repair safeguards;
- core service/provider/client/location/booking tenant isolation;
- provider/service relationship validation;
- configurable booking-form resolution and stale-slot handling;
- numeric database-ID bounds and route precedence;
- client restriction and management-review policies;
- scheduling interval, buffer, special-day, and DST behavior;
- SMS provider/account/conversation/prompt isolation;
- SMS outbound safety blocklist, rate limiting, quiet hours, and Chatwoot loop prevention;
- telemetry failure non-impact and privacy redaction;
- frontend lint and strict TypeScript compilation.

If a remediation breaks one of these behaviors, stop and report the regression rather than weakening its test.

---

## 12. Remediation tracking ledger

Update this ledger only through reviewed commits. Preserve prior status and evidence in commit history; do not erase reopened findings.

| Finding/work package | Owner | Status | Remediation commit | Independent audit commit/date | Evidence document | Residual risk |
|:---|:---|:---|:---|:---|:---|:---|
| A — Administrative bypass | Unassigned | Not started | — | — | — | Critical exposure remains |
| B — Payment integrity | Unassigned | Not started | — | — | — | Critical exposure remains |
| C — Webhook isolation/SSRF | Unassigned | Not started | — | — | — | Critical exposure remains |
| D — Outbox ownership/idempotency | Unassigned | Not started | — | — | — | Duplicate external action possible |
| E — Credential handling | Unassigned | Not started | — | — | — | Fail-open secret storage remains |
| F — External-safe tests | Unassigned | Not started | — | — | — | Test may contact provider |
| G — Tenant sweep | Unassigned | Not started | — | — | — | Multiple boundary gaps remain |
| H — Deployment/migrations | Unassigned | Not started | — | — | — | Clean release not reproducible |
| I — CI/dependencies | Unassigned | Not started | — | — | — | Automated gate coverage absent |
| J — Frontend auth/tests | Unassigned | Not started | — | — | — | Frontend manufactures authority |
| K — Repository hygiene | Unassigned | Not started | — | — | — | Tracked artifact/privacy risk remains |
| L — Worktree-only features | Unassigned | Decision required | — | — | — | Unapproved/incomplete local scope |
| M — Maintainability | Unassigned | Not started | — | — | — | Structural recurrence risk remains |

---

## 13. Definition of production readiness

FastAPI Bookings may be described as production-ready only when all Critical and High findings are **Verified** or explicitly **Accepted risk** by the user with an owner and review date, and when all global release gates pass on the exact release commit.

In particular, the following statements must all be true:

- no magic administrator token or predictable production signing secret exists;
- no unsigned or unreconciled payment event changes application state;
- no tenant-owned record or payload can be accessed or delivered across tenants;
- no two workers can produce duplicate effective external delivery;
- no credential can be stored plaintext on error or returned through an API/URL;
- no automated test can contact a live provider;
- a clean PostgreSQL database reaches the release schema through committed migrations;
- readiness detects schema mismatch;
- the image is reproducible, non-root, correctly ported, and secret-free;
- backend and frontend security, contract, test, dependency, migration, and build gates pass;
- telemetry and logs are demonstrably privacy-safe;
- documentation and runbooks describe the actual application and topology;
- the release commit has a clean, reviewed, single-purpose provenance.

Until then, reports should use a qualified statement such as: **functional development baseline with unresolved production release blockers**.

---

## 14. Standing instructions to Anti-Gravity

1. Treat this brief as the remediation backlog and acceptance contract, not as authorization for one broad rewrite.
2. Start each task by naming the finding IDs and intended changed-file allowlist.
3. Preserve unrelated staged, unstaged, and untracked work.
4. Work from the existing canonical FastAPI and React contracts. Do not introduce a second backend or revive obsolete UI code.
5. Make tenant scope, authorization, idempotency, and privacy behavior explicit in code and tests.
6. Use synthetic labelled fixtures and mandatory provider fakes.
7. Stop for user direction before any live external action, destructive migration decision, credential rotation, history rewrite, deployment, push, merge, or scope expansion.
8. Never call a finding fixed solely because imports, static checks, or happy-path tests pass.
9. Produce the complete evidence packet and one coherent commit per work package.
10. Expect an independent auditor to reproduce adversarial behavior and reopen incomplete fixes.

This document should remain the durable reference for future Anti-Gravity briefing and independent remediation review.
