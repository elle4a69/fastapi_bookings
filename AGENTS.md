# FastAPI Bookings — Agent Operating Rules

These rules apply to every automated agent and every task in this repository.
They are mandatory unless the user explicitly overrides a rule in writing.

## 1. Source of truth and architecture

- This repository, **FastAPI Bookings**, is the active application.
- FastAPI Bookings is authoritative for tenants, users, roles, providers,
  locations, categories, resources, services, availability, schedules,
  calendars, holds, bookings, booking status, customer booking records, and
  booking audit history.
- Chatwoot is not the booking source of truth.

### Bridge Phase Exception — Explicitly Approved

- The existing Assistant UI remains an independently deployable, protected
  messaging and AI application during the Bridge Phase.
- For Bridge-enabled providers only, Assistant UI may own SMS transport,
  conversations, message history, AI modes, drafts, knowledge, agent
  configuration, and staff messaging workflow.
- Assistant UI may call a narrow, authenticated FastAPI Booking Bridge API for
  live booking-domain operations only. FastAPI must resolve tenant, provider,
  location, and account scope server-side from the authenticated Assistant UI
  line/account mapping. The AI, frontend, and bridge caller must not select
  arbitrary tenant or provider IDs.
- Assistant UI must not directly read or write FastAPI databases, import
  FastAPI runtime modules, share authentication sessions, share production
  credentials, or become a Git submodule/runtime dependency.
- For a Bridge-enabled provider, Assistant UI's legacy booking, SQLite, Google
  Calendar, and availability paths must not create, confirm, modify, or cancel
  bookings. If FastAPI is unavailable, Assistant UI must fail closed into staff
  review rather than fall back to its legacy booking path.
- Chatwoot is out of scope for the Bridge Phase. Do not introduce it as an
  additional messaging dependency until a separate decision approves it.
- The deployed Assistant UI must not be modified during development. Bridge work
  must first occur in an isolated development or staging deployment, using test
  numbers and synthetic data. Any production Assistant UI release requires
  separate explicit owner approval.
- A long-term native FastAPI messaging/AI replacement remains optional future
  work. It is not an active requirement for the Bridge Phase.

### Assistant UI Source Boundaries

- `integrations/assistant-ui-v2/` is intentionally untracked local material.
  Do not stage, delete, modify, inspect for implementation, or commit it.
- Any permitted Assistant UI source audit or bridge adapter work must be
  explicitly scoped to the approved bridge source location and task allowlist.
  It must never use production databases, secrets, SMS numbers, or deployment
  resources.

## 2. Scope discipline

Before editing:

1. Read the current branch, `git status --short`, relevant architecture/docs,
   and the files directly involved in the requested task.
2. State the intended changed-file allowlist.
3. Do not create unrelated routes, pages, models, integrations, folders,
   migrations, or compatibility layers.
4. Do not treat a frontend/backend mismatch as permission to invent a new API.
   First establish the intended contract from the existing code and task.
5. If a request would expand the task materially, stop and report the decision
   point rather than silently broadening scope.
6. Bridge work must remain limited to the approved line-to-provider mapping,
   authenticated Booking Bridge API contract, and specific Assistant UI adapter
   call sites. Do not port or rebuild messaging, AI, knowledge, Chatwoot,
   arrival, reporting, or a new operations UI unless separately approved.

One task must address one coherent outcome. Finish, verify, and commit it
before starting unrelated remediation.

## 3. Business and data safety

- Never create a payment, refund, cancellation, booking confirmation, SMS,
  or external-provider action merely to satisfy a missing route or test.
- A payment/refund feature requires an approved provider integration,
  idempotency, audit trail, and explicit user authorization.
- Do not change booking, provider, service, availability, SMS, AI, Chatwoot,
  or customer data behavior unless that behavior is explicitly in scope.
- Preserve tenant/provider/account isolation. Never permit SMS context,
  replies, credentials, or learned knowledge to cross accounts.
- Do not send live SMS, create real bookings, or contact real customers during
  tests. Use labelled synthetic fixtures and cancel any created test AI jobs.

## 4. Secrets, privacy, and telemetry

- Never print, commit, return to the frontend, or put into logs/traces:
  credentials, API keys, webhook secrets, authorization headers, cookies,
  database URLs, SMS bodies, AI prompts/responses, customer identities,
  phone numbers, emails, addresses, booking notes, or query-string tokens.
- Never use `git add -A`, `git add .`, or blanket staging commands.
- Do not read or modify `.env` unless the task explicitly requires a narrowly
  defined configuration change. Never echo its contents.
- Telemetry must use allowlisted, low-cardinality structural attributes only.
  Telemetry/export failure must never break normal application behavior.
- Do not claim telemetry works until traces, metrics, and logs are visibly
  verified in the configured collector with a privacy-safety test.

## 5. Git and change-control protocol

- Work on the current approved branch or a dedicated task branch.
- Preserve unrelated user changes and untracked files.
- Before committing, run:
  - `git status --short`
  - `git diff --stat`
  - a changed-file review against the task allowlist.
- Stage only explicit intended paths.
- Do not commit generated assets, duplicate applications, local runtime files,
  build output, data exports, credentials, or large binary media unless the
  user explicitly requested those exact files.
- Do not reset, force-push, delete branches, merge, push, or deploy unless the
  user explicitly requests that operation.
- A task report must include the commit hash, changed files, tests run, and
  known limitations. Do not report success based only on imports or static
  checks when runtime behavior is in scope.

## 6. Verification requirements

For any code change:

- Add or update regression tests for the defect/behavior being changed.
- Run focused backend tests and frontend TypeScript/Vite checks when frontend
  code changes.
- Perform a relevant runtime smoke test when routes, workers, configuration,
  or integrations change.
- For API work, verify HTTP method, path, auth boundary, response schema, and
  error behavior. Do not weaken authorization or accept arbitrary methods to
  hide a 404/405.
- For performance work, measure before and after using the relevant endpoint
  or query. Do not make unsupported causal claims.
- For external integrations, prove the real local integration path works using
  synthetic labelled data only.

## 7. Runtime process management

- Before starting a server, inspect listening ports and existing processes.
- Run at most one intended FastAPI backend and one intended frontend dev
  server. Do not leave duplicate listeners or stale reload workers.
- Do not stop Docker, Chatwoot, SigNoz, Cloudflare tunnels, or user-run
  services unless the task explicitly requires it.
- Report the local URLs and health/smoke result after a requested start.

## 8. Stop conditions

Stop and ask for direction when:

- the intended behavior cannot be determined from existing code and the task;
- a change would create/alter external financial, SMS, booking, or customer
  actions;
- a required credential, secret, or production setting is missing;
- the diff exceeds the agreed scope or introduces an unrelated subsystem;
- verification reveals a broader regression than the requested task.

When uncertain, prefer a small documented diagnostic or a proposal over an
invented implementation.

## 9. Living Module Documentation and README Maintenance

Comprehensive, living documentation is a mandatory deliverable of the development process.
To preserve application integrity and eliminate reliance on ad-hoc handoff notes:

- **Mandatory README Updates on Every Task**: Whenever an agent creates, modifies, or
  refactors any module, page, or service, it is mandatory to update that module's
  corresponding `README.md` (or create it if absent) before completing the task.
- **Hybrid Documentation Architecture**:
  - `docs/` serves as the central architectural repository, cross-module workflow index,
    and master catalog ([docs/README.md](file:///f:/Projects/fastapi_bookings/docs/README.md),
    [docs/ARCHITECTURE.md](file:///f:/Projects/fastapi_bookings/docs/ARCHITECTURE.md),
    [docs/MODULE_INDEX.md](file:///f:/Projects/fastapi_bookings/docs/MODULE_INDEX.md)).
  - Local `README.md` files sit at the root of each major module, service, and package
    (e.g., `app/services/sms/`, `app/services/scheduling/`, `frontend/src/pages/portal/`, etc.).
- **Required Sections for Module READMEs**:
  1. **Purpose & Scope**: Clear description of what the module owns and what it deliberately avoids.
  2. **Architecture & Key Files**: Directory layout, primary models, routers, services, and components.
  3. **Setup, Configuration & Dependencies**: Required environment variables, external services (e.g. Chatwoot, Cal.com), and database tables.
  4. **Core Workflows & Contracts**: Inbound/outbound flows, event lifecycle, and API contracts.
  5. **Data Safety & Isolation**: Multi-tenant boundaries, PII handling, and concurrency safety.
  6. **Known Issues, Edge Cases & Outstanding Work**: Explicit ledger of technical debt, active limitations, and planned enhancements.
  7. **Verification & Testing Commands**: Exact commands to run tests, smoke tests, and lint checks.
- **Self-Documenting Codebase**: An agent opening any module should understand its full
  state from its `README.md` without relying on previous chat transcripts or ephemeral notes.
