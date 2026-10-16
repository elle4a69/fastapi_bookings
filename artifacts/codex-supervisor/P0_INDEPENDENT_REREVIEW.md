# P0 Final Independent Release Audit

**Anti-Gravity task:** `ccc_p0_independent_rereview`

**Branch:** `codex/codex-supervisor-p0-trust`

**Audited commit:** `64099c72c90f649e5629b80d73472b3edb78c2e8`

**Direct parent:** `6256fc5d25e3ad5c2f60d739c24446ebc4df3546`

**Audit date:** 2026-10-15 (Australia/Sydney)

**Verdict:** **accepted_with_conditions**

## Release decision

No Critical, High, or Medium P0 code defect was found. The four findings from
the first independent review are closed, and all six original trust-boundary
outcomes remain implemented at the pinned commit.

The only release condition is environmental: the repository-mandated browser
console/network gate must be rerun with the exact audited backend available on
port 8000 and must exit zero. The fresh run saw no backend listener and every
application API request returned HTTP 502 through the already-running Vite
proxy on port 7070. This is not evidence of a defect in the 21-path P0 diff, but
it also is not a valid release-gate pass. Do not merge or push this P0 release
until that one gate passes against this commit.

## Independence and method

The reviewer did not author the implementation and made no application-code
change. The repository boot snapshot and `AGENTS.md` were read before review.
The `differential-review` skill was selected through the required Skills-RAG
`find` -> `skill` path and its returned `SKILL.md` was read in full. Its named
companion files (`methodology.md`, `adversarial.md`, `reporting.md`, and
`patterns.md`) were absent from the returned skill location, so the complete
available checklist was applied directly and this degraded skill packaging is
recorded here.

The security baseline, architecture blueprint, first review, prior re-review,
complete parent-to-commit diff, commit history, tests, and documentation were
reviewed. No `.env`, credentials, customer data, or unrelated untracked
integration material was inspected.

## Exact scope confirmation

`git rev-parse HEAD` and `git rev-parse HEAD^` matched the hashes above.
`git diff --name-status HEAD^ HEAD` contained exactly these 21 paths:

1. `app/api/routers/README.md`
2. `app/api/routers/admin_support_tickets.py`
3. `app/api/routers/resident_agent.py`
4. `app/main.py`
5. `app/services/resident_agent/README.md`
6. `app/services/resident_agent/skill_library.py`
7. `artifacts/codex-supervisor/P0_INDEPENDENT_REREVIEW.md`
8. `artifacts/codex-supervisor/P0_INDEPENDENT_REVIEW.md`
9. `codex-control-centre/README.md`
10. `codex-control-centre/backend/middleware/auth.py`
11. `codex-control-centre/backend/routers/events.py`
12. `codex-control-centre/backend/routers/turns.py`
13. `codex-control-centre/backend/services/sse_tickets.py`
14. `codex-control-centre/tests/test_events.py`
15. `frontend/src/pages/admin/coding-cockpit/EventStream.tsx`
16. `frontend/src/pages/admin/coding-cockpit/README.md`
17. `frontend/src/pages/admin/coding-cockpit/coding-cockpit.test.ts`
18. `frontend/src/pages/admin/coding-cockpit/residentEventStream.ts`
19. `tests/test_admin_support_tickets.py`
20. `tests/test_codex_backend_mount.py`
21. `tests/test_resident_agent.py`

The worktree was clean before verification. This audit artifact is the only
post-audit modification. No commit or push was performed.

## Prior findings and P0 outcomes

| Control | Result | Evidence |
|---|---|---|
| P0-REV-001: truthful worker acknowledgement | **Closed** | Support dispatch opts into `await_worker_ack=True`, requires a returned turn ID plus `worker_acknowledged`, and records `codex_dispatch_failed` with HTTP 503 on rejection (`app/api/routers/admin_support_tickets.py:493-569`). The turn router awaits the real `worker.send_request("turn/start", ...)` before claiming acknowledgement (`codex-control-centre/backend/routers/turns.py:254-259`, `:329-442`). Success and post-creation rejection are tested at `tests/test_admin_support_tickets.py:304-436`. |
| P0-REV-002: Skills-RAG privacy | **Closed** | Search text is reduced to a fixed technical allowlist with a bounded term count before loopback URL construction (`app/services/resident_agent/skill_library.py:20-53`, `:132-157`). Reads accept only a validated indexed identifier. PII, bearer, API-key, token, and note canaries are verified absent from URL/result/logs at `tests/test_resident_agent.py:313-373`; host paths and traversal are rejected at `:376-388`. |
| P0-REV-003: atomic one-use SSE tickets | **Closed** | Valid consumption checks scope and removes the ticket inside one async lock (`codex-control-centre/backend/services/sse_tickets.py:37-56`). The mounted stream accepts only that ticket (`codex-control-centre/backend/routers/events.py:22-39`). Concurrent use and replay are covered at `codex-control-centre/tests/test_events.py:107-117` and `tests/test_codex_backend_mount.py:351-388`. |
| P0-REV-004: safe resident reconnect | **Closed** | The transport uses the fixed same-origin resident-events path, authenticated fetch, a single active request, bounded exponential retry for transient failures, terminal 401/403 handling, and teardown of timer/reader/controller (`frontend/src/pages/admin/coding-cockpit/residentEventStream.ts:24-168`; `EventStream.tsx:17-31`). Focused tests cover retry, overlap, URL credentials, and auth rejection. |
| Platform-owner authority | **Verified** | Mounted non-stream Control Centre routers use `Depends(require_platform_owner)` (`app/main.py:622-684`), and every resident route uses the same dependency (`app/api/routers/resident_agent.py:73-294`). Ordinary admin/manager denial is tested. The existing application contract defines this role as `owner` or `is_superuser` (`app/api/deps.py:190-205`). |
| Mounted secret/query rejection | **Verified** | Mounted auth resolves the native tenant/user and platform-owner boundary; standalone `local_secret` and query-token compatibility is reachable only for the distinct standalone app (`codex-control-centre/backend/middleware/auth.py:25-88`). Mounted bearer, `X-Token`, and query credential rejection is covered at `tests/test_codex_backend_mount.py:393-423`. |
| Authenticated resident stream, no URL credential | **Verified** | Backend requires platform owner and frontend supplies native authenticated headers without a query credential (`app/api/routers/resident_agent.py:92`; `frontend/src/pages/admin/coding-cockpit/EventStream.tsx:23-31`). |

Adversarial paths checked included non-owner access, mounted standalone-secret
reuse, query/bearer event-stream bypass, concurrent ticket reuse, stale ticket
replay, raw-prompt/PII/secret disclosure, worker rejection after turn creation,
transient stream disconnect, and terminal authorization failure. The tests
exercise the real dependency/RPC boundaries rather than asserting insecure
cross-tenant success.

## Fresh verification

| Command | Result |
|---|---|
| `python scripts/query_docs.py --boot-snapshot` | PASS |
| `python scripts/query_docs.py --test-command resident_agent` | PASS; authoritative focused command returned |
| Test-command queries for `codex`, `coding-cockpit`, and `support` | No registered command; pre-existing documentation-index gap |
| Primary venv: `pytest tests/test_resident_agent.py tests/test_codex_backend_mount.py tests/test_admin_support_tickets.py -v` | 55 collected: **53 passed, 2 failed**; only the two legacy stress-fuzzer tests failed |
| Same command with `-k "not stress_fuzzer"` | **53 passed, 2 deselected** |
| Primary venv from `codex-control-centre`: `pytest tests/test_security.py tests/test_events.py -v` | **13 passed** |
| `node --experimental-strip-types --test src/pages/admin/coding-cockpit/coding-cockpit.test.ts` | **22 passed** |
| `npm run build` | PASS; 2540 modules transformed, only the existing chunk-size advisory |
| `python -m py_compile` over all eight changed Python modules | PASS |
| Four targeted `verify_living_docs.py --path ...` gates | PASS: 4/4 |
| `git diff --check 6256fc5d... 64099c72...` | PASS |
| `python scripts/verify_zero_console_errors.py` | **ENVIRONMENT BLOCKED**: no listener on 8000; six routes reported universal API HTTP 502 through Vite on 7070 |

The earlier Business Assistant import/build mismatch is not present in this
final pinned baseline: the integrated tests collected and 53 P0-relevant tests
passed, and the full frontend build passed. It is therefore not a current
condition or a P0 finding.

## Legacy stress-fuzzer assessment

The two failures are `test_stress_fuzzer_race_condition_simulation` and
`test_stress_fuzzer_endpoint` (`tests/test_resident_agent.py:383-417`). They
fail with `sqlite3.OperationalError: no such table: tenants` because
`app/services/resident_agent/stress_fuzzer.py` imports the process-global
`SessionLocal` at line 17 and opens it at lines 61 and 131, while the pytest
fixture constructs a separate connection-bound in-memory session at
`tests/conftest.py:81-82` and overrides only the request dependency.

This is pre-existing, out-of-scope test-isolation debt, not a P0 regression:
neither the fuzzer implementation nor those test bodies changed between the
audited parent and commit. The P0 authorization change merely moves the route
from the admin dependency to the required platform-owner dependency. The two
failures do not block this trust-boundary release, but the fuzzer should later
accept an injected session/factory so its concurrency test runs against the
pytest database.

## Residual scope and release condition

Durable tenant/user row ownership, principal-bound or run-scoped event
delivery, recursive support `error_context` scrubbing, approval/evidence
binding, and the broader audit ledger remain later blueprint work. This P0
verdict neither claims nor closes them.

Before merge or push, start the exact audited backend in a safe synthetic test
environment, rerun `python scripts/verify_zero_console_errors.py`, and require
zero console errors, page errors, and 4xx/5xx API or asset responses. Any code
change made to obtain that result requires a new independent diff review.

## Compressed handoff

`accepted_with_conditions` — exact 21-path commit and parent confirmed; no
Critical/High/Medium P0 defect; all four prior findings and six trust-boundary
outcomes verified. Fresh evidence: 53 P0-relevant integrated tests, 13 Control
Centre tests, 22 cockpit tests, build, compilation, docs, and diff checks pass.
Two unchanged stress-fuzzer tests fail only because global `SessionLocal`
bypasses the injected pytest database and are non-blocking legacy debt. The
sole release condition is a successful mandatory browser gate with the exact
backend available; the fresh attempt was environment-blocked by universal 502s
because port 8000 had no listener.
