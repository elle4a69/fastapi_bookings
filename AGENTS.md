# FastAPI Bookings — Agent Operating Rules

These rules apply to every automated agent and every task in this repository.
They are mandatory unless the user explicitly overrides a rule in writing.

## 1. Source of truth and architecture

- This repository, **FastAPI Bookings**, is the active application.
- FastAPI Bookings owns booking, provider, service, availability, customer,
  SMS, AI-orchestration, arrival, and Chatwoot-integration logic.
- Chatwoot is a messaging channel and staff-inbox integration; it is not the
  booking source of truth.
- The old Assistant UI / Assistant UI V2 application is obsolete. It must not
  be copied, imported, revived, embedded, or made a runtime dependency.
- `integrations/assistant-ui-v2/` is intentionally untracked local material.
  Do not stage, delete, modify, inspect for implementation, or commit it.

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
