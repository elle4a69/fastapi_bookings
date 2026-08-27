# AntiGravity Consolidated Handoff

## Assistant UI + FastAPI Bookings

Authoritative handoff date: 2026-08-24 (Australia/Sydney)

This document supersedes:

- `SMS-ASSISTANT-INTEGRATION-HANDOFF.md`
- `BOOKINGS-AI-AGENT-ASSESSMENT.md`

Those documents remain useful evidence, but this is the current plan.

---

## 1. Objective

Create a safe, current copy of the operational Assistant UI and integrate that copy
with FastAPI Bookings through HTTP APIs.

The operational Assistant UI must remain intact and available throughout the work.
FastAPI Bookings must remain the only authoritative booking system. The integration
copy continues to own messaging, conversations, prompts, RAG, autoresponder behavior,
training tools, and SMS-facing workflows.

The result should appear inside the FastAPI Bookings admin application through the
existing `SMS Assistant` menu item, while remaining an independently runnable module.

---

## 2. Non-negotiable safety boundary

### Operational application — protected, read-only

```text
Path:     F:\Projects\assistant-ui
Frontend: http://localhost:5190
Backend:  http://localhost:8025
```

This is currently in use.

AntiGravity must not:

- edit this directory;
- overwrite, rename, move, or delete it;
- run formatters or dependency upgrades in it;
- stop or restart ports 5190 or 8025;
- change its `.env`, databases, credentials, webhooks, or startup scripts;
- use its live database as the integration database;
- register a second consumer for its production SMS webhook;
- send test messages through its configured production SMS account.

Read-only inspection and hashing are allowed.

At handoff time, the live processes were confirmed as:

```text
5190 -> F:\Projects\assistant-ui\frontend\...\vite.js
8025 -> original Assistant FastAPI service
```

### Main booking application

```text
Path:     F:\Projects\fastapi_bookings
Frontend: http://localhost:7070
Backend:  http://localhost:8000
```

Avoid broad changes to its FastAPI backend. Use its existing HTTP API unless a proven
contract gap requires a small, reviewed endpoint change.

---

## 3. Current state

### The first integration copy is stale

An earlier copy exists at:

```text
F:\Projects\fastapi_bookings\integrations\assistant-ui
```

It contains valuable integration work, including:

- `backend/booking_api.py`
- `backend/test_booking_api.py`
- remote/local booking mode hooks in `backend/main.py`
- integration documentation and environment examples
- isolated startup scripts
- a tested booking API compatibility layer

However, it was copied around 2026-08-11. The operational Assistant continued changing
through at least 2026-08-17.

Read-only comparison found:

```text
Operational source files inspected: 72
Old integration-copy files:          53
Identical files:                     28
Changed shared files:                21
Files only in operational source:    23
Integration-only files:               4
```

The operational `backend/main.py` is approximately 345 KB; the old integration copy is
approximately 207 KB. This is too large a divergence for a blind overwrite or casual
three-way merge.

Newer operational work includes conversational booking tools, timezone fixes, anonymous
content, arrival screens, inline booking, operations AI chat, PWA/push behavior, message
timestamp logic, webhook reliability, and additional safety/booking tests.

### Current main-admin integration

The main booking frontend already contains:

- menu item: `SMS Assistant`
- route: `/admin/sms-assistant`
- page: `frontend/src/pages/admin/sms-assistant.tsx`
- iframe/external-tab workspace

That page currently defaults to port 5190. It must be repointed to the new integration
frontend on port 5191 before integrated testing.

### Git/worktree state

At handoff:

```text
Repository: F:\Projects\fastapi_bookings
Branch:     master
HEAD:       debfb0a
```

The repository has extensive unrelated, user-owned modifications and untracked files.
Relevant integration status includes:

```text
 M frontend/src/App.tsx
 M frontend/src/components/navigation.ts
 M start.bat
?? frontend/src/pages/admin/sms-assistant.tsx
?? integrations/assistant-ui/
?? start-assistant-ui.bat
```

`App.tsx` and `navigation.ts` also contain unrelated changes. Do not replace them
wholesale, discard hunks, reset the repository, or blanket-stage files.

---

## 4. Target architecture

```text
FastAPI Bookings admin
http://localhost:7070/admin/sms-assistant
                         |
                         | iframe / new-tab link
                         v
New Assistant integration frontend
http://localhost:5191
                         |
                         | VITE_API_BASE=http://localhost:8026
                         v
New Assistant integration API
http://localhost:8026
            |                              |
            | Assistant-owned concerns     | HTTP booking adapter
            v                              v
Separate local runtime data         FastAPI Bookings API
messages, prompts, RAG, etc.         http://localhost:8000
                                    authoritative booking data
```

Protected operational application remains alongside it:

```text
Original Assistant UI: 5190 -> 8025
New integration copy:  5191 -> 8026
FastAPI Bookings:      7070 -> 8000
```

---

## 5. Correct implementation strategy

Do not update the old integration copy in place.

### Phase A — inventory and immutable baseline

1. Inspect the operational source read-only.
2. Record a manifest of source paths, file sizes, modification times, and hashes.
3. Identify source/config/runtime data separately.
4. Record the operational process command lines for 5190 and 8025.
5. Confirm no planned command targets those ports or that directory.

### Phase B — create a fresh V2 integration copy

Create:

```text
F:\Projects\fastapi_bookings\integrations\assistant-ui-v2
```

Copy the current operational source, excluding:

- `.env` and all secret-bearing environment files;
- `service_account.json`, credentials, and private keys;
- SQLite databases and journals;
- `.venv`;
- `node_modules`;
- `dist`, caches, logs, temporary files, and generated browser state;
- production webhook/runtime state;
- generated datasets unless individually reviewed.

Do not use symlinks or junctions back to the operational directory.

Create clean dependencies and isolated runtime state under V2. Copy only documented
example configuration. All external side-effect credentials must start empty/disabled.

### Phase C — assign safe ports before first launch

Before running V2:

```dotenv
# V2 backend
PORT=8026

# V2 frontend
VITE_API_BASE=http://localhost:8026
```

Configure Vite for port 5191. Any V2 port-cleaning script may target only 5191 and
8026. It must never target 5190 or 8025.

Verify process working directories after launch. An HTTP 200 is insufficient evidence;
the command line must point into `integrations\assistant-ui-v2`.

### Phase D — forward-port the booking adapter

Use the old integration copy as a donor, not as the base.

Port and adapt:

- `backend/booking_api.py`
- `backend/test_booking_api.py`
- booking environment variables and examples
- remote booking-mode behavior
- Assistant compatibility-route delegation
- read-only service-catalogue behavior in remote mode
- clear error behavior when FastAPI Bookings is unavailable

Do not replace the newer V2 `backend/main.py` with the old file. Inspect each old hook
and apply it deliberately to the current source. Prefer extracting a router/service
module instead of adding more code to the already-large `main.py`.

### Phase E — connect the booking admin

Update the main booking frontend so:

```dotenv
VITE_ASSISTANT_UI_URL=http://localhost:5191
```

The `/admin/sms-assistant` page must embed V2 and retain its external-tab link. Update
root startup scripts to start V2 on 5191/8026 without touching the original Assistant.

Keep V2 independently startable and stoppable.

### Phase F — validation and cutover

Do not delete or overwrite the old integration copy until V2 passes acceptance tests.
After V2 is accepted, document whether the old copy should be archived or removed.
Deletion requires explicit user approval.

---

## 6. Booking API boundary

FastAPI Bookings owns:

- tenants;
- services and catalogue visibility;
- providers and service/provider relationships;
- locations;
- schedules and availability;
- clients;
- bookings and lifecycle state;
- confirmation, rescheduling, completion, no-show, and cancellation.

Assistant V2 owns:

- inbound/outbound message orchestration;
- conversation threads and operator state;
- autoresponder rules;
- prompts, knowledge/RAG, and training data;
- customer SMS simulator;
- message alerts and triage UI;
- messaging-provider configuration;
- optional test/training modules.

V2 must not import FastAPI Bookings ORM models or access its database directly.

### Existing adapter endpoints

The donor adapter currently consumes:

- `GET /health`
- `GET /api/public/bootstrap`
- `GET /api/admin/services`
- `GET /api/public/availability`
- `POST /api/public/clients`
- `POST /api/public/clients/identify`
- `PUT /api/admin/clients/{id}`
- `POST /api/public/bookings`
- `GET /api/admin/bookings`
- `GET /api/admin/bookings/{id}`
- `PUT /api/admin/bookings/{id}`
- `POST /api/admin/bookings/{id}/confirm`
- `POST /api/admin/bookings/{id}/reschedule`
- `POST /api/admin/bookings/{id}/complete`
- `POST /api/admin/bookings/{id}/noshow`
- `POST /api/admin/bookings/{id}/cancel`

Admin calls use `X-Token`; tenant context uses `X-Tenant`. Development defaults must
not be used as production credentials.

Remote mode must never silently fall back to local booking writes. An API outage should
produce a visible failure, preventing split-brain bookings.

---

## 7. External-side-effect safety gate

Before any V2 process is started, ensure:

- Mobile Message username/password/sender are empty or sandbox-only;
- autoresponder and outbound SMS are disabled;
- no production webhook points to 8026;
- no Chatwoot webhook or API token is configured;
- no Locanto automation is configured;
- no production Google Calendar credentials are present;
- OpenAI usage is either disabled, mocked, or explicitly budgeted for testing;
- V2 uses new databases, not copied operational databases;
- test phone numbers cannot reach real customers.

Enable one external integration at a time only after local and mocked validation.

---

## 8. Chatwoot decision

Chatwoot exists separately at:

```text
E:\Projects\chatwoot-source
```

There is also a Docker installation. Chatwoot was considered primarily for its
multi-channel messaging integrations.

**Current decision: leave Chatwoot out of this integration.**

It is out of scope for V2 because it adds another application, database, authentication
model, webhook flow, channel state model, and deployment dependency. Stabilize direct
Assistant UI -> Assistant API -> FastAPI Bookings behavior first.

Future architecture may add Chatwoot as an optional channel adapter feeding a normalized
Assistant inbound-message contract. Do not design the core around it now and do not
modify `E:\Projects\chatwoot-source` in this task.

---

## 9. Abandoned `bookings_ai_agent` decision

Project:

```text
F:\Projects\bookings_ai_agent
```

This is not the integration foundation. Do not merge Assistant UI into it.

Why:

- its configured `BOOKINGS_API_URL` is not actually used by its booking implementation;
- it writes to its own booking table and directly to Google Calendar;
- its AI service has no implemented booking tools despite README claims;
- it has no tests or meaningful route authorization;
- its pre-approval mode is forcibly converted to autopilot before outbound messaging;
- it duplicates functions already implemented more robustly elsewhere.

It is a donor/archive candidate, not immediate trash. Preserve it read-only for now.

Potential donor features:

- approval/edit/reject desk;
- onboarding interview;
- persona bootcamp simulator;
- virtual-phone UX;
- selected Chatwoot/Locanto adapter concepts for later;
- selected settings/logging UI;
- curated training examples.

Do not migrate its local booking model, public booking form, Google Calendar booking
code, or current `agent.py` wholesale. Do not delete the project until a migration
ledger and safe archive exist, and only with explicit user approval.

---

## 10. Multi-agent work allocation

AntiGravity may use multiple agents, but file ownership must be explicit. Use one lead
writer/integrator. Discovery agents should remain read-only.

### Agent 1 — source inventory (read-only)

- Compare operational Assistant with old integration copy.
- Produce current-source manifest and V2 exclusion list.
- Identify secret/runtime/generated files.
- Do not edit or stop the operational app.

### Agent 2 — booking adapter analysis (read-only initially)

- Review donor `booking_api.py` and tests.
- Map every old `main.py` integration hook onto the newer source.
- Identify API contract gaps without changing FastAPI Bookings.

### Agent 3 — external-side-effect/security review (read-only)

- Trace SMS, webhook, OpenAI, calendar, Chatwoot, and Locanto paths.
- Specify safe defaults and test doubles.
- Verify V2 cannot affect real customers.

### Agent 4 — lead integrator (only primary writer)

- Create V2 source copy.
- Establish ports/config/dependencies.
- Implement modular booking bridge.
- Update the embedded admin target and startup scripts.
- Resolve integration conflicts.

### Agent 5 — QA/acceptance

- Run automated tests and builds.
- Verify process paths/ports.
- Perform end-to-end booking lifecycle testing.
- Prove the original application remained untouched.

If AntiGravity supports only a smaller team, combine agents 1–3 as read-only analysis
tasks and retain one writer plus one QA agent.

Do not allow multiple agents to edit `backend/main.py`, `frontend/src/App.tsx`, or root
startup scripts concurrently.

---

## 11. Required validation

### Original-app preservation

- Hash comparison shows no operational source changes caused by this task.
- 5190 and 8025 remain available throughout.
- Original environment, databases, and credentials remain unchanged.

### V2 runtime

- 5191 process working directory is under `integrations\assistant-ui-v2\frontend`.
- 8026 process working directory is under `integrations\assistant-ui-v2\backend`.
- V2 browser requests go to 8026, never 8025.
- V2 has separate databases and runtime files.

### Automated validation

- Run all tests copied from the current operational source.
- Port and run donor adapter tests.
- Add contract tests for every FastAPI Bookings endpoint used.
- Run Assistant frontend TypeScript/build validation.
- Run the main booking frontend build and distinguish unrelated existing failures.
- Add tests proving remote API failures do not create local bookings.
- Add tests proving outbound SMS/provider calls are disabled in test configuration.

The old integration baseline was 122 passing backend tests and a successful Assistant
frontend build, but V2 contains newer source and therefore must establish a new baseline.

### End-to-end booking lifecycle

Through `/admin/sms-assistant` or the V2 customer simulator:

1. Load services from FastAPI Bookings.
2. Resolve a valid provider/location relationship.
3. Retrieve availability from FastAPI Bookings.
4. Identify or create a test client.
5. Create one test booking in FastAPI Bookings.
6. Confirm it according to configuration.
7. List it in both the booking admin and Assistant compatibility view.
8. Reschedule it.
9. Change status where appropriate.
10. Cancel it and document cleanup.
11. Prove no corresponding booking was written to an Assistant-local database.

Use synthetic customer data and do not send real SMS.

---

## 12. Acceptance criteria

The task is complete only when:

- current operational Assistant source has been copied into V2 without secrets/runtime
  data and without modifying the original;
- original Assistant remains operational on 5190/8025;
- V2 runs independently on 5191/8026;
- main booking admin embeds V2 at `/admin/sms-assistant`;
- V2 calls 8026 and never accidentally calls 8025;
- V2 uses FastAPI Bookings HTTP APIs for all booking operations;
- FastAPI Bookings is the only authoritative booking store in remote mode;
- messaging, conversations, prompts, RAG, and simulator behavior remain Assistant-owned;
- remote booking failures never trigger local booking fallback;
- no real SMS, Chatwoot, Locanto, or calendar side effects occur during validation;
- automated tests and builds have documented results;
- all created test bookings are documented and cleaned up;
- unrelated dirty work remains preserved;
- no deletion occurs without explicit user approval.

---

## 13. Expected deliverables

1. `integrations/assistant-ui-v2/` with safe ignore rules and example configuration.
2. Modular FastAPI Bookings adapter and contract tests.
3. V2 startup/stop scripts limited to 5191/8026.
4. Main booking admin configured to embed 5191.
5. Updated architecture/runtime documentation.
6. Source-copy manifest and exclusion/redaction record.
7. Test/build/end-to-end validation report.
8. Explicit list of files changed.
9. Explicit confirmation that the operational Assistant was untouched.
10. Follow-up migration ledger for optional `bookings_ai_agent` donor features.

---

## 14. Copy/paste prompt for AntiGravity

> Read `F:\Projects\fastapi_bookings\ANTIGRAVITY-CONSOLIDATED-HANDOFF.md`
> completely and treat it as the authoritative specification. Use multi-agent discovery
> if useful, but appoint one lead writer and prevent concurrent edits to shared files.
> The operational app at `F:\Projects\assistant-ui` on ports 5190/8025 is in active use
> and is strictly read-only: do not edit it, stop it, change it, or reuse its runtime
> data/credentials. Create a fresh source-only copy at
> `F:\Projects\fastapi_bookings\integrations\assistant-ui-v2`, excluding secrets,
> databases, dependencies, caches, builds, logs, and production runtime state. Configure
> V2 for frontend 5191 and backend 8026 with all outbound integrations disabled. Use the
> stale `integrations\assistant-ui` only as a donor for its tested HTTP booking adapter;
> deliberately forward-port the adapter into the newer source instead of overwriting
> newer files. Keep FastAPI Bookings on 8000 as the only booking authority and do not
> access its database or import its ORM models. Point the existing booking-admin SMS
> Assistant page to 5191, run the full documented validation, clean up synthetic booking
> data, and report exact changes/results. Chatwoot and `bookings_ai_agent` integration are
> out of scope. Preserve all unrelated dirty work and perform no deletion without
> explicit approval.
