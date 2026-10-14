# P0 Independent Security and Truthfulness Review

**Task:** `ccc_p0_independent_review`
**Branch:** `codex/codex-supervisor-p0-trust`
**Review date:** 2026-10-15 (Australia/Sydney)
**Verdict:** **rejected**

## Scope and independence

This review covers only the uncommitted P0 diff in the isolated worktree at
`C:\Users\Frank\.codex\worktrees\codex-supervisor-p0\fastapi_bookings`.
The reviewer did not author or modify the implementation. The only review-time
repository change is this artifact.

The review used the repository boot snapshot, `AGENTS.md`,
`CCC_SECURITY_BASELINE.md`, `CCC_ARCHITECTURE_BLUEPRINT.md`, and the complete
14-file diff. The `api-security-best-practices` skill was selected through the
required port-8008 Skills RAG `find` -> `skill` flow and read in full.

## Executive result

The diff successfully narrows the integrated Control Centre and resident routes
to the existing `require_platform_owner` boundary, removes mounted shared-secret
and query-bearer stream fallbacks, authenticates resident SSE through request
headers, removes direct host-file skill reads, and removes the fabricated
fallback turn. Those are worthwhile containment changes.

It is not acceptable yet because two High-severity defects defeat the stated
truthfulness/privacy outcomes:

1. the support-ticket route reports `queued_for_codex` before the worker has
   acknowledged `turn/start`; and
2. the new Skills RAG HTTP client places the raw resident prompt/search text in
   a URL query parameter.

Two Medium issues also remain in the changed transport contract: Control Centre
SSE tickets described as one-use are reusable for 15 seconds, and the new
resident fetch-stream client silently stops forever after disconnect.

## Findings

### P0-REV-001 — High — Support-ticket success still precedes worker acknowledgement

**Evidence**

- `app/api/routers/admin_support_tickets.py:496-501` treats a returned database
  `turn_id` as dispatch success, and lines `541-559` immediately set the ticket
  to `queued_for_codex` and return success.
- `codex-control-centre/backend/routers/turns.py:404-419` schedules
  `_safe_dispatch_turn_start(...)` with `asyncio.create_task(...)` and returns
  the active turn before the task calls the worker.
- The actual worker acknowledgement is `await worker.send_request("turn/start", ...)`
  at `codex-control-centre/backend/routers/turns.py:253`. Failures are caught only
  inside the detached task at lines `255-315`, after the support ticket has
  already been reported as queued.
- `tests/test_admin_support_tickets.py:353-406` patches `start_turn` itself to
  throw. It never exercises the real failure mode where `start_turn` returns a
  turn ID and the background worker request subsequently fails.
- `app/api/routers/README.md:62` therefore overstates the contract: a “real turn
  ID” proves a database row/worktree/worker object was created, not that the
  worker accepted the Codex turn.

**Impact**

The exact false-success race identified by `CCC-SEC-006` remains. A worker can
reject or fail the request immediately after the API reports success, leaving
the support ticket queued while the Codex turn is already failed.

**Smallest remediation**

Add an awaitable acknowledgement mode to the existing turn-start path (do not
build another executor). For support-ticket launches, await the initial
`turn/start` request and return success only after the worker acknowledges it;
then continue long-running event processing asynchronously. On rejection,
transactionally mark the Codex turn failed, keep the ticket under review, write
`codex_dispatch_failed`, and return 503. Add a regression test that makes the
real worker's `send_request("turn/start", ...)` fail after turn creation and
asserts that no queued ticket is returned.

### P0-REV-002 — High — Raw prompts are newly placed in Skills-RAG query URLs

**Evidence**

- `app/services/resident_agent/engine.py:266` passes the complete advisory
  `prompt` to `find_relevant_skills` when research does not supply matches.
- `app/services/resident_agent/remediation_planner.py:164-166` can include an
  issue title in the search query, and `web_researcher.py:174-175` forwards its
  search query as well.
- The new client sends that string as `params={"query": query}` to
  `/api/skills/search` at `app/services/resident_agent/skill_library.py:101-103`.
  This places the text in an HTTP URL/query string, a common access-log and
  telemetry surface.
- The existing bounded Control Centre implementation already provides the safe
  pattern: `codex-control-centre/backend/services/skills_context.py:41-53`
  derives an allowlisted, low-cardinality technical query before calling port
  8008.
- The added resident tests use only the literal safe string `fastapi async` and
  contain no secret/PII canary assertion (`tests/test_resident_agent.py:257-305`).

**Impact**

Prompts, support issue titles, customer identifiers, tokens, or booking details
can cross the resident process boundary and appear in daemon/proxy logs as URL
query data. This conflicts with the repository prohibition on logging prompts,
customer data, secrets, and query-string credentials.

**Smallest remediation**

Make `SkillLibrary.find_relevant_skills` accept or internally derive only a
bounded allowlisted technical query, reusing the semantics of
`derive_safe_search_query`. Never put raw prompt/title/context text into the
request URL. Add captured-request tests with labelled email, phone, booking-note,
API-key, and bearer-token canaries and assert none occur in the outgoing URL,
logs, response, or exception.

### P0-REV-003 — Medium — “Single-use” SSE ticket documentation is false

**Evidence**

- The changed documentation repeatedly calls tickets single/one-use:
  `codex-control-centre/README.md:13`, `:61`, `:75`, `:231` and
  `frontend/src/pages/admin/coding-cockpit/README.md:114`.
- `codex-control-centre/backend/services/sse_tickets.py:55-62` deliberately
  accepts every reuse during a 15-second grace window instead of removing the
  ticket on first successful consume.
- The new tests prove bearer/query-token rejection but do not attempt a second
  connection with the same ticket (`tests/test_codex_backend_mount.py:351-417`).

**Impact**

A copied ticket can open more than one stream during the grace period. The
mounted stream is ticket-only, but it is not one-use as documented, weakening
the credential replay boundary and making the security documentation
materially inaccurate.

**Smallest remediation**

Atomically pop the ticket on first valid consume and mint a fresh ticket for
every reconnect. Add a test asserting that the second consume/connection is
401. If grace replay is intentionally retained, stop calling it single-use and
record that limitation explicitly; however, that would not meet the blueprint's
one-use contract.

### P0-REV-004 — Medium — Resident live stream no longer reconnects

**Evidence**

- `frontend/src/pages/admin/coding-cockpit/EventStream.tsx:17-66` replaces
  browser `EventSource` with one authenticated `fetch` and a reader loop.
- When `reader.read()` returns `done`, or when the request/stream throws, the
  function exits. There is no retry timer, backoff, or subsequent call to
  `connect`; the catch block intentionally does nothing.
- No added frontend test covers this component or a disconnect/reconnect
  journey. The existing cockpit source test checks reconnection only for the
  separate Control Centre `connectThreadEvents` implementation.

**Impact**

Any proxy timeout, backend restart, transient network interruption, or normal
stream close permanently freezes the resident event view until the component is
remounted. The failure is silent, so the supervisor UI can appear current when
it is stale.

**Smallest remediation**

Retain header-authenticated fetch streaming, but reconnect after non-abort EOF
or transport failure using bounded exponential backoff. Cancel both the active
reader and retry timer on unmount. Expose a truthful disconnected/retrying state
and add a component/unit test proving a second authenticated request occurs
after a synthetic disconnect without placing a token in the URL.

## Acceptance matrix

| Assigned outcome | Result | Evidence |
|---|---|---|
| Platform-owner authority | **Verified statically; runtime blocked** | `app/main.py:610-672` and all resident routes use `require_platform_owner`; negative admin tests were added. Integrated collection is blocked by the unrelated Business Assistant mismatch. |
| Reject mounted `local_secret`, query bearer, and tenant-admin access | **Verified statically; runtime blocked** | Mounted `verify_auth` uses native identity before standalone secret logic (`auth.py:68-88`); stream code accepts tickets only (`events.py:22-39`); negative tests cover all three credential forms and role `admin`. |
| Ticket-only Control Centre SSE | **Partial / failed contract** | Bearer and query fallback are removed, but a ticket remains reusable for 15 seconds (P0-REV-003). |
| Authenticated resident SSE with no query token | **Verified** | `resident_agent.py:89-104` requires `require_platform_owner`; `EventStream.tsx` uses authenticated headers and no token query. Reconnect behavior regressed (P0-REV-004). |
| Bounded port-8008 Skills-RAG identifier reads | **Failed privacy boundary** | Host-path reads are removed and IDs are syntax checked, but raw caller text is sent in query URLs (P0-REV-002). |
| Truthful support-ticket dispatch failure | **Failed** | Direct `start_turn` exceptions are truthful, but real worker dispatch remains detached and unacknowledged (P0-REV-001). |

## Additional security observations

- The path-read vulnerability itself is closed: `read_skill` validates the ID
  against `^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$` and calls only port-8008
  `/api/skills/read`; it never constructs a filesystem path.
- Mounted `local_secret` rejection is fail-closed for the native application
  object, and the event stream no longer accepts either authorization headers
  or a `token` query parameter.
- The support route still serializes `ticket.error_context` into the agent
  prompt without recursive allowlisting/scrubbing
  (`app/api/routers/admin_support_tickets.py:489-490`). This is a pre-existing
  `CCC-SEC-007` risk, not introduced by the P0 diff, but it remains a required
  follow-up before support tickets with untrusted diagnostic context are safe.
- The global Control Centre still lacks durable tenant/user ownership. This P0
  correctly contains it to the current platform-owner dependency but does not
  implement the later ownership migrations described by the blueprint.

## Fresh verification evidence

| Command | Result |
|---|---|
| `python scripts/query_docs.py --boot-snapshot` | PASS |
| `python scripts/query_docs.py --test-command resident_agent` | PASS; returned `.venv\\Scripts\\python.exe -m pytest tests/test_resident_agent.py -v` |
| `query_docs.py --test-command` for Control Centre, Coding Cockpit, support tickets, API routers | No registered command (documented repository gap) |
| `.\\.venv\\Scripts\\python.exe -m pytest ...` | Could not start: isolated worktree has no `.venv` |
| system Python and primary-checkout venv running `tests/test_resident_agent.py tests/test_codex_backend_mount.py tests/test_admin_support_tickets.py -v` | BLOCKED during `tests/conftest.py` import by missing `BusinessAssistantDiagnosticSetting`; the same clean-branch Business Assistant mismatch occurs with both interpreters and no Business Assistant file is in the P0 diff |
| from `codex-control-centre`: primary venv `-m pytest tests/test_security.py tests/test_events.py -v` | PASS: 12 passed |
| `python -m py_compile` over all six changed Python modules | PASS |
| focused Coding Cockpit Node test | PASS: 20 passed |
| `npm run build` | BLOCKED by pre-existing clean-branch Business Assistant missing exports/modules and context/type mismatch; no cited file is in the P0 diff |
| four targeted `verify_living_docs.py --path ...` commands | PASS: 4/4 |
| `python scripts/verify_zero_console_errors.py` | PASS on all six routes against pre-existing listeners on ports 7070/8000; environmental smoke only, not proof of isolated-worktree code |
| `git diff --check` | PASS; only CRLF normalization warnings |

The Business Assistant import/build failures are treated as external because
the complete P0 changed-file list contains no Business Assistant model,
component, context, hook, or caption-timeline file. They still prevent the
mandatory integrated runtime suite and isolated frontend build from being used
as acceptance evidence.

## Required re-review gate

Re-review after P0-REV-001 and P0-REV-002 are fixed with the specified negative
tests. P0-REV-003 and P0-REV-004 must also be corrected, or explicitly rebriefed
with truthful documentation and an owner-approved security/availability tradeoff.
The integrated focused tests and isolated frontend build must then run cleanly
once the external Business Assistant baseline is repaired.

## Compressed handoff

`rejected` — containment is directionally correct, but support dispatch still
reports success before worker acknowledgement and raw prompts now enter Skills
RAG URL queries. Also fix reusable “single-use” tickets and silent resident SSE
disconnects. Fresh standalone security/events tests: 12 passed; cockpit source
tests: 20 passed; Python compile/living-docs/browser gate passed; integrated
pytest and isolated build remain blocked by the unrelated Business Assistant
clean-branch mismatch.
