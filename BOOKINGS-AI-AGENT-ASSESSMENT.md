# Bookings AI Agent Reuse Assessment

> **Consolidated:** The current implementation plan and scope decisions are in
> `ANTIGRAVITY-CONSOLIDATED-HANDOFF.md`. This document remains supporting evidence for
> the donor/archive decision.

Assessment date: 2026-08-24 (Australia/Sydney)

Reviewed project: `F:\Projects\bookings_ai_agent`

Compared with:

- operational source: `F:\Projects\assistant-ui`
- integration copy: `F:\Projects\fastapi_bookings\integrations\assistant-ui`
- authoritative booking system: `F:\Projects\fastapi_bookings`

## Executive decision

Do **not** integrate Assistant UI into `bookings_ai_agent` as the new foundation.
Continue with the copied Assistant UI as the messaging/AI runtime and FastAPI Bookings
as the booking authority. Keep `bookings_ai_agent` temporarily as a read-only donor
project and selectively port its strongest ideas and components.

Do **not** delete it yet. It contains unique source, configuration, a 3.1 MB training
dataset, and runtime data. Archive it after producing an inventory and migration ledger.

Confidence: **High**. The recommendation is based on direct source inspection, current
database inventory, frontend static validation, and comparison with the tested copied
Assistant implementation.

## What this prototype really is

It is a useful control-console prototype built around:

- Chatwoot and Mobile Message inbound/outbound messaging
- human reply approval/edit/reject screens
- a persona-based two-agent training simulator
- an onboarding interview that builds business settings and a system prompt
- Locanto integration experiments
- a virtual phone/customer simulator
- a standalone public booking form and local booking table
- direct Google Calendar availability/event writes

It is approximately 1,921 lines of Python and 3,154 lines of frontend TypeScript.
The frontend is substantial and statically healthy. The backend is a prototype rather
than a dependable booking/agent core.

## Evidence-backed scorecard

| Area | Reuse value | Decision | Confidence |
|---|---|---|---|
| Approval desk UI/workflow | High | Port selectively | High |
| Onboarding interview | High | Port concept and schema | High |
| Persona/bootcamp simulator | Medium–High | Port after adding tests and job isolation | High |
| Virtual phone UI | Medium | Compare and take superior UX pieces | High |
| Chatwoot adapter | Medium | Extract as an optional channel adapter | Medium |
| Locanto integration | Medium | Keep isolated; do not couple to booking core | Medium |
| Settings UI | Medium | Port selected controls, not the whole settings store | High |
| Training dataset | Unknown–Medium | Audit quality/licensing/PII, then deduplicate | Medium |
| AI response service | Low | Do not use as the new agent core | High |
| Local booking subsystem | Very low | Discard in favor of FastAPI Bookings API | High |
| Direct Google Calendar booking | Very low | Do not migrate | High |
| Project as integration foundation | Low | Do not adopt | High |

## Why it should not become the foundation

### 1. It does not actually integrate with FastAPI Bookings

`BOOKINGS_API_URL` is declared in `app/core/config.py`, but no implementation calls it.
The project creates bookings in its own SQLite `Booking` table and writes directly to
Google Calendar. This would recreate the split-brain booking problem that the current
Assistant adapter explicitly avoids.

The README describes function-calling tools for availability and booking actions, but
`app/services/agent.py` sends only a system message and the latest user message to the
model. It defines no booking tools, performs no booking API call, and carries no prior
conversation history into the generation request.

### 2. A safety-critical operating mode is bypassed

`app/services/agent.py` converts `pre_approval` into `autopilot` before deriving
`training_mode`. As a result, selecting pre-approval can still send outbound responses
automatically. This is unsuitable as a migration base for an operational SMS system.

### 3. It duplicates systems already implemented more robustly

It has its own booking database, services configuration, public form, booked-slot logic,
and Google Calendar event creation. FastAPI Bookings already owns these concerns, while
the copied Assistant has a tested HTTP adapter for its booking compatibility routes.

### 4. Backend verification and security are weak

- No backend or frontend tests were found.
- API routes have no visible authentication/authorization layer.
- CORS allows all origins while credentials are enabled.
- Multiple URLs and model names are hard-coded.
- Webhook paths can lead to real outbound SMS when credentials are configured.
- The directory is not an independent committed Git repository; the surrounding
  `F:\Projects` repository has no commits and reports the entire project as untracked.
- `.env` and `service_account.json` are present locally and must not be committed or
  casually copied.

### 5. Documentation overstates implementation

The README calls the service an orchestration layer over a 140+ endpoint booking API
and claims booking tool calls. The source shows a local booking implementation instead.
An older audit artifact is also stale: it says Docker and frontend integration are
missing even though both now exist. Source code must remain the primary evidence.

## What is genuinely worth preserving

### Approval desk

The frontend provides pending-message retrieval, approve, reject, edit-and-send, SMS
logs, and execution logs. This is a valuable operational workflow. Migrate the workflow
into the copied Assistant only after fixing the mode state machine and adding endpoint
authorization and idempotency.

### Onboarding interview

The onboarding flow converts a business-owner conversation into structured settings and
a system prompt. This could become a tenant setup wizard in FastAPI Bookings or a prompt
configuration module in the copied Assistant. Map its output onto authoritative tenant,
service, schedule, policy, and messaging settings rather than retaining a free-form
parallel profile.

### Persona bootcamp

The simulator runs agent/persona dialogue loops and records the exchanges. The idea is
valuable for regression testing tone, booking intent, escalation, ambiguity, and hostile
inputs. Reimplement it behind a queue/background-job boundary with deterministic test
cases, cost limits, cancellation, and assertions against booking side effects.

### Chatwoot and Locanto channel work

These should be channel adapters feeding a common normalized inbound-message contract.
They should not own booking data or AI orchestration. Keep Locanto isolated because it
also depends on a separate localhost service on port 3033.

### UI concepts

The approval desk, bootcamp arena, onboarding console, settings panels, and virtual phone
are worth visual/interaction comparison with Assistant UI. Port components or patterns,
not the entire React application shell.

### Data that would be lost by immediate deletion

Current read-only inventory:

- `ai_training_data/dataset.jsonl`: 3,133,118 bytes
- `ai_agent.db`: 131,072 bytes
- 23 settings
- 10 personas
- 57 simulation logs
- 42 message queue records
- 4 confirmed local bookings
- 1 training dataset statistics record

Message records include processed, rejected, pending-approval, pending, and failed states
across simulator, Chatwoot, Mobile Message, and Locanto sources. Treat all of this as
potentially sensitive until reviewed.

## Recommended target architecture

```text
Channel adapters
  Mobile Message / Chatwoot / Locanto / Simulator
                       |
                       v
Copied Assistant API (messaging and AI orchestration)
  conversations, prompts, RAG, approval workflow, bootcamp
                       |
                       | documented HTTP adapter
                       v
FastAPI Bookings API (authoritative business and booking data)
  tenants, services, providers, locations, availability, clients, bookings
```

The copied Assistant should remain independently deployable. Channel adapters and
experimental modules should be optional and disabled by default in development copies.

## Migration map

| Prototype subsystem | Target | Method |
|---|---|---|
| `frontend/pages/Approvals.tsx` | Copied Assistant UI | Port selected views/actions |
| approval endpoints/state | Copied Assistant API | Rebuild with safe state transitions and idempotency |
| onboarding UI/service | Assistant UI plus booking tenant APIs | Define schema, then port |
| personas and simulator | Assistant test/training module | Port data; rewrite execution boundary |
| `VirtualPhone.tsx` | Copied Assistant customer simulator | Compare and merge superior UX only |
| Chatwoot webhook/reply | Optional Assistant channel adapter | Normalize payload; add verification/auth |
| Locanto modules | Optional isolated adapter | Keep outside booking core |
| settings UI | Existing Assistant settings | Map selected controls; avoid parallel stores |
| dataset JSONL | Curated Assistant training corpus | Audit, redact, deduplicate, validate |
| local `Booking` model/routes | Nowhere | Retire after archival |
| Google Calendar booking code | Nowhere | Use FastAPI Bookings availability/booking APIs |
| public booking form | Nowhere | FastAPI Bookings already owns booking forms |
| current `agent.py` | Reference only | Do not port wholesale |

## Safe sequence for AntiGravity

Use multiple agents for read-only discovery and separated ownership, with one lead agent
responsible for integration and final writes.

1. **Archivist/data agent (read-only):** inventory source, databases, dataset, settings,
   credentials, and external endpoints; produce a redacted manifest.
2. **Feature comparison agent (read-only):** compare every prototype screen/endpoint
   against copied Assistant functionality and mark keep/merge/drop.
3. **Security/side-effect agent (read-only):** trace every path that can send SMS, post
   to Chatwoot/Locanto, call OpenAI, or write Google Calendar/bookings.
4. **Test architect:** specify contract, state-machine, simulator, and no-side-effect
   tests before migration.
5. **Lead implementation agent:** migrate one bounded feature at a time into the copied
   Assistant, using distinct ports and disabled outbound integrations.
6. **QA agent:** validate original Assistant remains running and untouched, the copied
   Assistant uses its own processes/data, and all bookings exist only in FastAPI Bookings.

Do not let multiple agents edit `integrations/assistant-ui/backend/main.py` concurrently.
Prefer extracting new modules over expanding that already-large file.

## Archive-before-delete procedure

Do not delete the project until the migration ledger is complete.

1. Stop any auto-start entry for port 5172 without touching the operational Assistant.
2. Record hashes and sizes for source, dataset, database, and deployment artifacts.
3. Export a redacted inventory of database schema/counts and setting keys.
4. Store secrets (`.env`, service account, provider credentials) separately in an
   approved secret store; do not include them in a normal source archive.
5. Create a source archive excluding `.venv`, `frontend/node_modules`, caches, `dist`,
   `.env`, and credentials.
6. Create an encrypted data archive for the database and training corpus if retention is
   appropriate.
7. Confirm every keep/merge item has a destination issue or has been migrated.
8. Only then archive or remove the working directory.

## Validation performed

- Read project documentation, architecture brief, backend source, routes, models,
  services, frontend routes/API calls, and relevant Antigravity artifacts.
- Confirmed port 5172 was not listening during the assessment.
- TypeScript no-emit check: passed.
- Frontend lint: passed with four warnings (Fast Refresh export, one unused catch
  parameter, and two hook dependency warnings).
- No test files were found.
- No source code or runtime data in `F:\Projects\bookings_ai_agent` was modified.

## Acceptance decision

The project is a **donor/archive candidate**, not a foundation and not immediate trash.
The current FastAPI Bookings + copied Assistant UI direction remains the correct base.
Selective migration is justified only for features that outperform or do not yet exist
in Assistant UI, and every migrated feature must use FastAPI Bookings APIs for booking
operations.
