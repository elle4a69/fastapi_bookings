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

### Native Business Assistant Source-Reference Exception — Explicitly Approved

- FastAPI Bookings may selectively inspect and reimplement only the allowlisted
  behavioural assets from the legacy reference application for the native
  Business Assistant programme. The binding source allowlist, asset hashes,
  exclusions, and source-checkpoint requirement are in
  `docs/BUSINESS_ASSISTANT_REFERENCE_INVENTORY.md`; the delivery controls are in
  `docs/BUSINESS_ASSISTANT_NATIVE_PORT_PLAN.md`.
- This exception permits a native implementation inside FastAPI Bookings. It
  does not permit revival, wholesale copying, runtime coupling, shared
  databases, shared authentication sessions, shared credentials, runtime-module
  imports, deployment-resource reuse, or a Git submodule.
- No legacy-source database, environment file, secret, credential, production
  data, logs, message bodies, customer records, SMS number, deployment material,
  or unallowlisted folder may be read, copied, or depended upon.
- Untracked local integration material is out of scope. Do not stage, delete,
  modify, inspect for implementation, or commit it.
- The resulting Business Assistant must be owned, authenticated, tenant/user
  scoped, persisted, tested, and deployed wholly by FastAPI Bookings. It must
  not receive source-code, shell, Git, deployment, infrastructure,
  secret-reading, unrestricted-database, or coding-worker execution tools.
- The legacy reference application is never a production dependency. Any
  production release remains separately owner-approved and must use synthetic
  data and test numbers during development and staging verification.

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
6. Legacy-reference work must remain limited to the native Business Assistant
   programme, its approved source allowlist, and individually authorised work
   packages. Do not broaden it into a runtime bridge, wholesale application
   copy, messaging replacement, Chatwoot, arrival, reporting, or unrelated UI
   work unless separately approved.

One task must address one coherent outcome. Finish, verify, and commit it
before starting unrelated remediation.

## 3. Absolute prohibition of mock implementations

- **Mock implementations are not allowed under any circumstances. End of story.**
- There are no ifs, there are no buts. There is no such thing as a mock implementation.
  They do not exist on this platform.
- If an agent cannot code a real, complete, end-to-end implementation, it must not code it at all.
- Every feature must be real, fully plumbed, and functional from the database layer, through
  the backend APIs, all the way to the frontend UI.
- Strictly forbidden:
  - Synthetic `setTimeout` handlers simulating backend processing or delays.
  - Fake, hardcoded frontend state masquerading as real backend data.
  - Parallel "greenfield" unused scaffold code sitting disconnected from the production call graph.
  - Creating ORM models without real Alembic database migrations.
  - Writing tests that assert success for insecure or cross-tenant behavior.
  - Stub endpoints returning fake success without mutating real database state.
- Every UI interaction must call a real, authenticated, tenant-scoped API.
- Every service, tool, and prompt policy must be wired into the live execution path.

## 4. Business and data safety

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

## 5. Secrets, privacy, and telemetry

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

## 6. Git and change-control protocol

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

### Mandatory Automated Local Commit on Verified Task Completion
To ensure verified work is never stranded, forgotten, or lost in an uncommitted state:
- Once all verification tests pass, living documentation is verified via `python scripts/verify_living_docs.py`, and the QA audit sign-off is complete, the agent MUST automatically stage only the explicitly assigned task allowlist paths.
- The agent MUST automatically execute a clean, descriptive local git commit.
- The agent MUST report the resulting commit hash in its final delivery summary.
- Pushing to remote GitHub remains strictly user-triggered (never push autonomously).

## 7. Verification requirements

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

## 8. Runtime process management

- Before starting a server, inspect listening ports and existing processes.
- Run at most one intended FastAPI backend and one intended frontend dev
  server. Do not leave duplicate listeners or stale reload workers.
- Do not stop Docker, Chatwoot, SigNoz, Cloudflare tunnels, or user-run
  services unless the task explicitly requires it.
- Report the local URLs and health/smoke result after a requested start.

## 9. Stop conditions

Stop and ask for direction when:

- the intended behavior cannot be determined from existing code and the task;
- a change would create/alter external financial, SMS, booking, or customer
  actions;
- a required credential, secret, or production setting is missing;
- the diff exceeds the agreed scope or introduces an unrelated subsystem;
- verification reveals a broader regression than the requested task.

When uncertain, prefer a small documented diagnostic or a proposal over an
invented implementation.

## 10. Living Module Documentation and README Maintenance

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

## 11. Agent Cold-Start Protocol & Architectural Orientation

To eliminate token waste, blind directory scanning, and hallucinated paths on agent startup:

- **Mandatory First-Turn Inspection**: Before scanning arbitrary directories, reading unassigned files, or running broad exploratory searches, every automated agent must inspect the repository's pre-compiled architectural map:
  - Run `python scripts/query_docs.py --boot-snapshot` (or read `docs/AGENT_BOOT_SNAPSHOT.md`).
- **Targeted Test Command Retrieval**: Before running verification or writing tests, agents must query the authoritative verification command for the module being changed:
  - Run `python scripts/query_docs.py --test-command <module_name>` (e.g. `python scripts/query_docs.py --test-command sms`).
  - Do not guess test commands or run slow, un-targeted global test suites.
- **Semantic Documentation Search**: To discover architectural invariants, data safety boundaries, or contracts across modules:
  - Run `python scripts/query_docs.py --search "<topic>"` (e.g. `python scripts/query_docs.py --search "arrival token"`).
- **Compliance Verification**: All changes to modules must be verified against Rule 10 via:
  - `python scripts/verify_living_docs.py --path <module_readme_path>`.
