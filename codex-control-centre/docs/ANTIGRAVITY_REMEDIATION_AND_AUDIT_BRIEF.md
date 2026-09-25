# Codex Control Centre — Antigravity Remediation and Audit Brief

## Document control

| Field | Value |
|---|---|
| Document status | Ready for implementation planning |
| Created | 2026-08-29, Australia/Sydney |
| Intended implementers | Tailored specialist subagents assigned and managed by Antigravity |
| Intended reviewers | Codex, human maintainers, security reviewers, accessibility reviewers |
| Antigravity operating role | Project manager and orchestrator only; direct remediation coding is prohibited |
| Target environment | Local development first; no production deployment is authorised by this document |
| Repository path at audit time | `F:\Projects\codex-control-centre` |
| Governing principle | No completion claim without fresh, reproducible evidence |
| Scope | Full remediation of the application audit findings recorded below |

This is the durable implementation brief and future audit baseline for Codex Control Centre. It is deliberately more detailed than an `AGENTS.md` file. If an `AGENTS.md` is added later, it should remain concise and link to this document rather than duplicating it.

## 1. Mission

Transform Codex Control Centre from a visually convincing, fixture-driven prototype into a truthful, safe, testable, accessible, and maintainable local control centre with real frontend/backend integration.

The finished application must:

- Distinguish real operational data from demonstrations or unavailable features.
- Never claim that a command, test, review, approval, diagnostic, or agent action occurred unless the backend provides evidence that it occurred.
- Scope all state-changing actions to the correct project, thread, turn, approval, worker, or worktree.
- Remain safe when processes fail, clients disconnect, messages arrive late, users switch threads, and requests are duplicated.
- Default to loopback-only access until an explicit authentication and network-exposure model is approved.
- Provide reproducible setup, build, test, security, accessibility, and migration procedures.
- Satisfy the acceptance criteria and evidence gates in this document before any phase or finding is marked complete.

## 2. How Antigravity must use this brief

### 2.1 Mandatory non-coding project-manager role

Antigravity must remain the project manager and orchestrator for the entire remediation program. It must not implement the remediation itself.

Antigravity may:

- Inspect the repository and current state.
- Maintain plans, issue definitions, dependency maps, assignments, status, decision logs, and evidence registers.
- Select and brief specialist subagents.
- Coordinate dependencies and resolve non-code scheduling or ownership conflicts.
- Review complete diffs and artifacts returned by subagents.
- Run fresh verification commands and runtime checks.
- Accept, reject, re-brief, or escalate subagent work against this document.
- Produce progress, risk, and final audit reports.

Antigravity must not directly:

- Create or edit application source code.
- Create or edit tests intended to satisfy remediation acceptance criteria.
- Create or edit configuration, migrations, CI workflows, dependency manifests, launch scripts, infrastructure, or security controls.
- Repair a subagent's incomplete or faulty implementation itself.
- Perform a hidden “small fix” to make verification pass.
- Act as both implementation author and accepting reviewer for any work package.

Project-management and audit artifacts are the only files Antigravity may author directly. If implementation work fails review, Antigravity must return it to the responsible subagent with concrete findings or assign a new tailored subagent. It must never cross the role boundary and finish the code itself.

#### Required delegation model

- Delegate every implementation task to a subagent selected for the specific technology, risk, and work package.
- Give each subagent one bounded objective with explicit files or subsystem ownership, non-goals, dependencies, acceptance criteria, and required evidence.
- Do not hand the entire remediation program to one generalist subagent.
- Do not assign overlapping write ownership concurrently unless Antigravity defines an explicit integration boundary and merge order.
- Require each implementation subagent to report files changed, decisions made, tests run, results, limitations, and unresolved risks.
- Require a separate review subagent for security-sensitive, destructive, data-migration, authentication, worker, worktree, and cross-project isolation changes.
- Prefer an independent accessibility reviewer for WP-09 and an independent test/quality reviewer for WP-10.
- Do not allow subagents to declare their own work accepted. They may report completion, but Antigravity owns the acceptance decision after independent verification.
- Subagents must not expand scope or spawn further implementation agents unless Antigravity explicitly approves the delegation and retains visibility of ownership.
- When a subagent is blocked, Antigravity must re-plan, re-brief, reassign, or escalate; it must not take over implementation.

#### Tailored subagent role map

| Work package | Minimum tailored implementation role | Required independent review emphasis |
|---|---|---|
| WP-00 | Repository/toolchain and Python packaging specialist | Reproducibility and repository safety |
| WP-01 | React product-integrity specialist | Truthful states and removal of fabricated claims |
| WP-02 | FastAPI/SQLAlchemy migration specialist | Data preservation and schema integrity |
| WP-03 | Application security/authentication specialist | Authorisation, CORS, exposure, secrets |
| WP-04 | Async/SSE protocol specialist | Isolation, replay, ordering, resource bounds |
| WP-05 | Python asyncio/subprocess specialist | Timeout, cancellation, EOF, process leaks |
| WP-06 | Windows filesystem and Git-worktree specialist | Canonical paths, junctions, safe deletion |
| WP-07 | TypeScript state-machine/API integration specialist | Race conditions, idempotency, ownership |
| WP-08 | Feature-specific full-stack specialist per slice | End-to-end truthfulness and permission enforcement |
| WP-09 | Web accessibility and responsive UI specialist | WCAG, keyboard, screen reader, reflow |
| WP-10 | Test automation and CI specialist | Regression quality and clean-environment proof |
| WP-11 | Local operations/SRE specialist | Shutdown, readiness, logging, recovery |

This table defines minimum capability, not fixed agent names. Antigravity must inspect available subagent skills and choose the closest qualified specialist for each assignment. If no suitable specialist exists, it must report the capability gap and seek direction rather than coding the task itself.

#### Subagent assignment contract

Every assignment must contain:

```markdown
## Assignment
- Work package and finding IDs:
- Specialist role required:
- Objective:
- Owned files/subsystem:
- Inputs and dependencies:
- In scope:
- Non-goals:
- Acceptance criteria:
- Required focused tests:
- Required evidence:
- Safety constraints:
- Stop/escalation conditions:
- Expected handoff format:
```

#### Antigravity review gate after every subagent handoff

1. Confirm the subagent stayed within assigned scope and file ownership.
2. Inspect every changed line plus relevant surrounding code.
3. Compare the result line-by-line with the assigned acceptance criteria.
4. Obtain independent specialist review where required.
5. Run fresh focused tests, then the applicable broader gates.
6. Check for regressions, hidden fixture fallbacks, weakened validation, and unsupported success claims.
7. Record evidence and residual risk.
8. Accept, reject with a re-brief, reassign, or escalate.

### 2.2 Execution state machine

Every work package must move through these states:

1. `intake`
2. `issue-gated`
3. `executing`
4. `review-loop`
5. `runtime-verification`
6. `accepted` or `escalated`

An issue may enter `executing` only when it contains:

- Problem
- Goal
- Scope
- Non-goals
- Dependencies and blockers
- Testable acceptance criteria
- Current status: `draft`, `ready`, `blocked`, or `done`
- Execution gate: `allowed` or `blocked` with reason

### 2.3 Evidence rule

Code changes are not evidence of completion. Before claiming a work package is complete, Antigravity must:

1. Identify the command, test, runtime observation, or artifact that proves each acceptance criterion.
2. Run the full verification freshly after the final change.
3. Record the exact command, exit code, important output, and artifact location.
4. Confirm that negative/security cases were exercised where applicable.
5. Mark the work package `accepted` only when every criterion has evidence.

If acceptance still fails after two full implementation/verification rounds, move the package to `escalated` and report:

- What passed
- What failed
- Evidence
- Open risk
- The smallest human decision required

### 2.4 Safety and scope rules

- Do not deploy to staging or production under this brief.
- Do not force-push, rewrite history, delete user data, or delete an existing worktree without explicit human approval.
- Preserve existing SQLite files until their ownership and retention requirements are confirmed.
- Do not silently replace real data with fixtures to make tests pass.
- Do not add a control that appears active unless it performs the represented operation or is clearly marked unavailable.
- Do not weaken an acceptance criterion to match an incomplete implementation.
- Keep changes reviewable: separate infrastructure, backend, frontend, accessibility, and test changes when practical.
- Avoid unrelated refactors and mass formatting.
- Record material architecture decisions in `docs/adr/`.
- Antigravity must not bypass its non-coding role even when a change appears trivial, urgent, or easy.

## 3. Baseline architecture and observed state

### 3.1 Frontend

- React 19 and TypeScript 6 application built with Vite 8.
- Radix UI primitives and Tailwind CSS.
- A module-level singleton store in `frontend/src/store/useWorkbenchStore.ts`.
- Production UI state is initialized from `frontend/src/test/fixtures/realisticFixtures.ts`.
- No frontend API client, `fetch`, `EventSource`, or WebSocket connection was present at audit time.
- Agent turns, reconnection, approvals, files, test results, processes, telemetry, and diff verdicts are wholly or partly simulated.

### 3.2 Backend

- FastAPI application with a root route and publish/subscribe SSE routes.
- SQLAlchemy models for threads, turns, items, and approvals.
- SQLite configured through a process-working-directory-relative URL.
- A JSON-RPC subprocess worker implementation exists but is not wired into the API.
- A Git worktree manager exists but is not wired into the API.
- A SigNoz diagnostics class exists but returns mock data and owns an unmanaged `httpx.AsyncClient`.

### 3.3 Tooling and repository

- Frontend lockfile exists and the production build passes.
- No backend dependency manifest, migration configuration, CI workflow, or root README existed at audit time.
- `python -m pytest -q` failed from the application root because backend imports depend on the working directory.
- With `PYTHONPATH=backend`, the two existing endpoint tests passed but emitted Pydantic and SQLAlchemy deprecation warnings.
- The Git root resolved to `F:\Projects`, not the application directory, and the application was untracked in a repository with no commits.
- Both `codex.db` and `backend/codex.db` existed, demonstrating working-directory-dependent database selection.

## 4. Scope

### 4.1 In scope

- Repository and dependency reproducibility
- Backend packaging and configuration
- Database ownership, schema integrity, and migrations
- Authentication, authorisation, CORS, and network defaults
- SSE protocol, isolation, replay, backpressure, and lifecycle
- JSON-RPC worker lifecycle and failure handling
- Worktree creation and deletion safety
- Real frontend/backend integration
- Correct per-thread and per-operation frontend state
- Truthful feature and status presentation
- Approval, turn, compaction, diagnostics, file, diff, test, and process workflows
- Accessibility and responsive behaviour
- Automated tests, security checks, CI, observability, and release readiness
- Documentation and future audit procedure

### 4.2 Non-goals unless separately approved

- Production deployment
- Multi-tenant cloud hosting
- Billing integration
- A distributed message broker
- Kubernetes or other orchestration infrastructure
- Supporting arbitrary remote Git repositories
- Destructive migration of existing SQLite data without an approved backup and rollback plan
- Claiming full WCAG conformance without manual assistive-technology testing by a qualified reviewer

## 5. Non-negotiable product invariants

These invariants apply across all phases:

1. **Truthfulness:** UI status derives from backend state or is explicitly labelled demo/unavailable.
2. **Ownership:** Every mutable entity has an unambiguous project and thread owner.
3. **Isolation:** An action on one thread cannot alter another thread unless an explicit cross-thread operation says so.
4. **Idempotency:** Retrying a state-changing request must not duplicate turns, approvals, worktrees, or commands.
5. **Cancellation:** A stopped operation cannot later report success without a new explicit resume/retry action.
6. **Least privilege:** The application binds to loopback and denies unauthenticated state changes by default.
7. **Safe deletion:** Only resources created and registered by the application may be automatically deleted.
8. **Bounded resources:** Queues, request durations, payloads, subscribers, subprocess output, and logs must have limits.
9. **Auditable decisions:** Approvals, declines, interruptions, retries, and destructive actions retain actor, scope, time, and result.
10. **Evidence:** Completion and health claims are backed by reproducible tests or runtime observations.
11. **Accessibility:** Core journeys work by keyboard and do not rely on colour alone.
12. **Recoverability:** Schema and data changes have backup, migration, and rollback procedures.

## 6. Findings register

The finding IDs below are permanent. Implementations, issues, pull requests, test names, and audit reports should reference them.

| ID | Severity | Finding | Primary evidence at baseline |
|---|---|---|---|
| CCC-001 | Blocker | Frontend has no real backend integration and is initialized from fixtures | `frontend/src/store/useWorkbenchStore.ts:12-18, 58-86` |
| CCC-002 | Blocker | UI fabricates operational success and security claims | `useWorkbenchStore.ts:340-369`; inspector fixture tabs |
| CCC-003 | High | Approval/decline mutates unrelated threads | `useWorkbenchStore.ts:229-266` |
| CCC-004 | High | Turn completion, thread switching, stop, and resume race conditions | `useWorkbenchStore.ts:295-402` |
| CCC-005 | High | Backend is unauthenticated, permissive CORS, and launched on all interfaces | `backend/main.py:9-15`; `start.ps1:33` |
| CCC-006 | High | SSE relay has unbounded queues, no isolation, replay, rate limits, or backpressure | `backend/routers/events.py:14-39` |
| CCC-007 | High | Relative SQLite path selects different databases by working directory | `backend/config.py:5`; duplicate database files observed |
| CCC-008 | High | Schema creation occurs on import; no migration or upgrade process | `backend/database.py:56` |
| CCC-009 | High | Worker requests can hang and subprocess I/O can deadlock | `backend/services/worker.py:19-90` |
| CCC-010 | High, latent | Worktree cleanup may recursively delete an arbitrary supplied path | `backend/services/workspace_manager.py:36-55` |
| CCC-011 | High | Launcher force-kills unrelated processes on selected ports | `start.ps1:11-27`; `start.bat:2-4` |
| CCC-012 | High | Backend imports and dependencies are not reproducible | root pytest collection failure; no backend manifest |
| CCC-013 | High | Automated coverage is insufficient for represented behaviours | only two basic endpoint tests at baseline |
| CCC-014 | High | Project registration, test/process controls, files, and diff approval are stubs | inspector and modal components |
| CCC-015 | Medium | Accessibility scan reported eight occurrences in five rule categories | axe-core baseline on 2026-08-29 |
| CCC-016 | Medium | Fixed panels do not provide 320px reflow; global text selection is disabled | `frontend/src/App.tsx:25`; inspector/sidebar fixed widths |
| CCC-017 | Medium | Database relationships lack explicit integrity and lifecycle constraints | `backend/database.py:15-54` |
| CCC-018 | Medium | Diagnostics are mock data behind production-looking privacy claims | `backend/services/diagnostics_tool.py`; `TelemetryTab.tsx` |
| CCC-019 | Medium | Diagnostics HTTP client lifecycle is unmanaged | `backend/services/diagnostics_tool.py:14-16` |
| CCC-020 | Medium | Configuration drifts between port 8000 and launcher port 8100 | `backend/config.py:6`; launcher scripts |
| CCC-021 | Medium | Compaction inserts the same notice into every turn and reports success without work | `useWorkbenchStore.ts:203-227` |
| CCC-022 | Medium | Forms have unassociated labels and weak required-field enforcement | project and user-input forms |
| CCC-023 | Medium | Clickable non-semantic rows lack complete keyboard interaction | file/diff/command lists and nested thread controls |
| CCC-024 | Medium | No project-level Git baseline or application-specific ignore policy | Git inspection on 2026-08-29 |
| CCC-025 | Low | Frontend ships a single approximately 496 KB JavaScript chunk | Vite production build baseline |
| CCC-026 | Low | Pydantic and SQLAlchemy APIs in use emit deprecation warnings | adjusted-path pytest baseline |

## 7. Target architecture

The implementation may evolve, but deviations from these boundaries require an ADR.

```text
React UI
  -> typed API client
     -> authenticated FastAPI routes
        -> application services
           -> repositories / SQLAlchemy session boundary
           -> thread + approval state machine
           -> worker supervisor
           -> registered worktree service
           -> diagnostics adapter
        -> event service
           -> scoped event envelopes
           -> bounded subscriber buffers
           -> replay cursor / sequence support

SQLite (local/dev)
  -> absolute configured data directory
  -> migrations
  -> constraints and indexes
  -> explicit backup/restore procedure
```

### 7.1 Boundary rules

- Routes validate transport concerns and delegate to application services.
- Application services own transactional behaviour and authorisation checks.
- Repositories own persistence operations; UI fixture types are not persistence models.
- The worker supervisor owns subprocess creation, I/O, timeouts, cancellation, and shutdown.
- The workspace manager accepts opaque registered workspace IDs at public boundaries, not arbitrary deletion paths.
- Diagnostics providers implement an interface and expose provider availability; mock providers are enabled only by an explicit demo/test setting.
- Events are emitted only after the relevant transaction succeeds, or through an outbox-equivalent mechanism if reliability requires it.

### 7.2 Minimum event envelope

Every event must contain:

```json
{
  "id": "immutable-event-id",
  "schema_version": 1,
  "project_id": "project-id",
  "thread_id": "thread-id-or-null",
  "turn_id": "turn-id-or-null",
  "sequence": 123,
  "type": "turn.completed",
  "occurred_at": "RFC-3339 UTC timestamp",
  "payload": {}
}
```

Required semantics:

- Sequence is monotonic within the documented scope.
- Clients can resume using `Last-Event-ID` or an equivalent cursor.
- Events are filtered by authorised project/thread scope.
- Unknown event types do not crash the client.
- Event payloads have maximum size and validation.
- Slow subscribers are disconnected or coalesced according to a documented policy; memory cannot grow without bound.

## 8. Remediation work packages

### WP-00 — Establish repository and evidence baseline

Addresses: CCC-012, CCC-013, CCC-024, CCC-026.

Required work:

- Confirm whether `F:\Projects\codex-control-centre` should become its own Git repository or a deliberate subdirectory of a parent repository.
- Add an application-specific `.gitignore` covering databases, environment files, caches, coverage, build output, and transient worktrees without hiding source or migrations.
- Add a root README containing supported operating systems, prerequisites, setup, development commands, test commands, configuration, data location, and known limitations.
- Add a locked backend dependency definition using an approved tool.
- Make backend imports package-safe from the application root.
- Add root-level canonical commands or scripts for setup, development, tests, linting, type checking, security checks, and builds.
- Capture the baseline failures and warnings before remediation.
- Do not commit existing database contents until a human confirms they contain no private or operational data.

Acceptance criteria:

- A clean clone can install frontend and backend dependencies using documented commands.
- `python -m pytest` runs from the project root without `PYTHONPATH` manipulation.
- A fresh checkout does not create or modify a database merely by importing a module.
- Generated files and local databases are ignored.
- A reproducible baseline report maps each finding ID to an issue/work package.

Required evidence:

- Clean-clone setup transcript
- Dependency lockfiles
- Root test command output
- `git status --short` after setup/build/test showing only expected changes

### WP-01 — Make the product truthful before adding capability

Addresses: CCC-001, CCC-002, CCC-014, CCC-018, CCC-021.

Required work:

- Add an explicit application mode: `live`, `demo`, or `unavailable`; do not infer it from missing data.
- Prevent fixture modules from entering a production/live bundle.
- Add a persistent and accessible demo banner when demo mode is selected.
- Remove or rewrite claims such as “verified,” “privacy redaction active,” “connected,” “passed,” and “approved” unless supported by backend evidence.
- Disable unavailable controls with an explanation or hide them when capability discovery says they are unavailable.
- Ensure project registration either persists a project through the backend or clearly reports that the action is unavailable.
- Ensure diff verdicts, test runs, process termination, telemetry, and file views do not imply backend effects when none occurred.
- Replace simulated completion timers with a real transport or an explicitly isolated demo adapter.

Acceptance criteria:

- Production/live mode contains no imports from `src/test/fixtures`.
- Disconnecting or stopping the backend makes the UI report disconnected/unavailable after a bounded timeout.
- Every enabled action produces a traceable backend request and result.
- Every demo-only screen is visibly and programmatically identified as demo data.
- No code path reports tests/files/security checks as verified without evidence fields from the backend.

Required evidence:

- Production bundle/import inspection
- End-to-end test with backend available and unavailable
- UI screenshots and accessibility-tree output for live and demo modes

### WP-02 — Backend packaging, configuration, and data ownership

Addresses: CCC-007, CCC-008, CCC-012, CCC-017, CCC-020, CCC-026.

Required work:

- Convert backend imports to a consistent package layout.
- Replace deprecated Pydantic configuration and SQLAlchemy imports.
- Centralise host, port, allowed origins, database path, data directory, log level, demo mode, and diagnostics settings.
- Use an absolute, resolved application data directory.
- Fail startup with a clear error when configuration is invalid.
- Replace import-time `create_all` with application startup checks plus a migration workflow.
- Add migrations for all tables, constraints, and indexes.
- Define foreign-key nullability, uniqueness, cascade/delete behaviour, and orphan handling.
- Store UTC-aware timestamps.
- Add explicit status values through validated enums or constraints.
- Add backup, upgrade, downgrade, and corrupted-database recovery documentation.
- Decide how the two baseline database files are retained, migrated, or archived; never merge them silently.

Minimum data constraints:

- Turn number is unique within a thread.
- Tool call identifiers are unique within their documented scope.
- Approval status and scope are validated.
- Foreign keys are enforced by SQLite connections.
- Deleting a project/thread cannot silently orphan turns, items, approvals, workers, or worktrees.
- Database sessions are scoped to requests or application-service units of work.

Acceptance criteria:

- Starting from an empty data directory applies migrations and reaches the current schema.
- Starting from the previous schema upgrades without data loss in a test fixture.
- Launching from different working directories opens the same configured database.
- Foreign-key and uniqueness violations fail predictably.
- Importing backend modules has no schema-creation side effect.
- Port and host values come from one documented configuration source.

Required evidence:

- Migration up/down/up transcript on disposable databases
- Database path test from at least two working directories
- Constraint tests
- Backup/restore test on synthetic data

### WP-03 — Authentication, authorisation, CORS, and secure network defaults

Addresses: CCC-005, CCC-006, CCC-011.

Required work:

- Bind backend and frontend development servers to `127.0.0.1` by default.
- Remove reload mode from persistent launch scripts; provide a separate explicit development command.
- Implement the approved authentication model.
- Authorise every project, thread, approval, worker, worktree, diagnostic, and event operation.
- Configure an explicit origin allowlist; never combine wildcard origin with credentials.
- Apply request body limits, rate limits, and timeouts to state-changing and streaming endpoints.
- Add security headers appropriate to the serving architecture.
- Replace “kill anything on this port” startup behaviour with owned-process tracking or a refusal that identifies the conflicting process.
- Keep secrets out of URLs, logs, events, local storage, fixture data, and source control.
- Add audit records for approvals, declines, process starts/stops, workspace deletion, and permission changes.

Safe default pending a human authentication decision:

- Loopback-only service.
- Random per-launch or explicitly configured local bearer/session secret.
- No LAN exposure.
- No remote repository or command execution.

Acceptance criteria:

- An unauthenticated client cannot publish, subscribe to, or mutate application state.
- A user authorised for project A cannot read or alter project B.
- Disallowed origins fail CORS checks.
- Default launch does not expose ports on non-loopback interfaces.
- Starting while a port is occupied does not terminate the unrelated process.
- Logs and event payloads pass a configured secret/PII redaction test.

Required evidence:

- Negative API tests for missing, invalid, expired, and wrong-scope credentials
- Socket/listener evidence showing loopback binding
- CORS preflight tests
- Port-conflict integration test
- Security test report mapped to CCC-005, CCC-006, and CCC-011

### WP-04 — Reliable event transport

Addresses: CCC-006 and supports CCC-001/004.

Required work:

- Replace the global list of raw queues with an event service abstraction.
- Scope subscriptions by authenticated project and optional thread.
- Bound subscriber buffers and define overflow behaviour.
- Add event IDs, sequence values, schema versions, timestamps, and replay/resume support.
- Add heartbeat intervals and disconnect cleanup.
- Add `Cache-Control: no-cache` and proxy buffering guidance where relevant.
- Ensure one slow/disconnected subscriber cannot block publishing to others.
- Define whether event delivery is at-most-once or at-least-once and make client reducers idempotent.
- Define single-process limitations if SQLite/in-memory delivery remains the dev architecture.

Acceptance criteria:

- Events from project A never reach a subscriber authorised only for project B.
- A disconnected client can resume without duplicate state transitions.
- A deliberately slow subscriber cannot cause unbounded memory growth.
- Disconnect cleanup returns subscriber/resource counts to baseline.
- An invalid event payload is rejected without terminating healthy streams.
- The client tolerates duplicated, delayed, unknown, and out-of-order events according to the protocol.

Required evidence:

- Concurrency and isolation tests
- Memory/buffer-bound test
- Reconnect/replay end-to-end test
- Event schema fixtures and compatibility tests

### WP-05 — Worker supervision and JSON-RPC correctness

Addresses: CCC-009.

Required work:

- Add explicit worker states: starting, running, stopping, stopped, failed.
- Prevent duplicate starts and writes to exited processes.
- Drain stdout and stderr concurrently with bounded capture or streaming.
- Add per-request timeout and cancellation.
- Fail all pending futures when EOF, process exit, protocol failure, or application shutdown occurs.
- Remove pending requests on timeout/cancellation.
- Validate JSON-RPC version, IDs, response/result exclusivity, method names, and parameter shapes.
- Decide how incoming JSON-RPC requests are handled; return a protocol error rather than silently ignoring them.
- Track notification-handler tasks and surface their failures.
- Await read-loop cancellation and make shutdown idempotent.
- Do not expose arbitrary executable/argument selection to an untrusted client.

Acceptance criteria:

- A normal request returns the matching response.
- A request times out within its configured bound and leaves no pending future.
- Child crash, EOF, malformed output, and stderr flood do not hang the service.
- Stop is safe when called zero, one, or multiple times.
- Pending requests all fail with typed errors during shutdown.
- An unauthorised user cannot start, steer, or stop a worker.

Required evidence:

- Tests using controlled fake child processes
- Timeout and crash transcripts
- Resource/task leak checks after repeated start/stop cycles

### WP-06 — Worktree lifecycle and deletion safety

Addresses: CCC-010 and supports CCC-024.

Required work:

- Validate repository ownership and confirm the repository has a usable commit before creating worktrees.
- Validate branch names using Git’s own reference checks.
- Generate worktree directories under a single configured, resolved worktree root.
- Persist a registry containing workspace ID, canonical path, repository identity, branch, creator, time, and lifecycle status.
- Public APIs accept workspace IDs, not arbitrary filesystem paths.
- Before deletion, resolve the target and prove it is a registered child of the configured worktree root and belongs to the expected repository.
- Do not run recursive deletion when `git worktree remove` fails unless an explicit recovery path proves ownership and receives the required approval.
- Preserve dirty worktrees unless force cleanup is explicitly approved.
- Record cleanup failures rather than swallowing them.

Acceptance criteria:

- Traversal paths, symlink/junction escapes, repository root, workspace root, drive root, and unregistered paths are rejected.
- A registered clean worktree can be created and removed.
- A dirty worktree is preserved by the default cleanup path.
- Branch cleanup affects only the registered branch.
- Concurrent create/cleanup operations cannot register the same branch or delete another workspace.

Required evidence:

- Windows-specific path, junction, and traversal tests
- Git integration tests in disposable repositories
- Audit-log entries for create and cleanup

### WP-07 — Frontend API integration and state architecture

Addresses: CCC-001, CCC-003, CCC-004, CCC-021.

Required work:

- Add a typed API client with central URL, authentication, error, timeout, retry, and cancellation handling.
- Separate server state from local UI state.
- Store streaming/operation status per thread or turn; remove the global `isStreaming` invariant.
- Capture immutable project/thread/turn IDs when starting asynchronous operations.
- Use operation IDs and abort signals so late results cannot overwrite interrupted or superseded operations.
- Make reducers idempotent under replay and duplicate events.
- Derive approval counts and thread status from owned approval state or update only the owning thread transactionally.
- Treat server responses as authoritative and reconcile optimistic updates on failure.
- Persist drafts safely per thread, but do not persist secrets or credentials in local storage.
- Reset selected indices when collections change and guard against stale selections.
- Insert compaction notices once, in the correct turn or timeline location, only after backend confirmation.

Acceptance criteria:

- Approving/declining a request changes only its owning approval and thread.
- Switching threads during a running turn does not strand, transfer, or mislabel the operation.
- Stopping a turn prevents a later success event from resurrecting it.
- Two threads can independently display their current operation states.
- Duplicate/replayed events do not duplicate timeline items or decrement counters twice.
- API failures visibly roll back or reconcile optimistic state.
- Compaction produces one backend-confirmed notice and no fabricated token count.

Required evidence:

- Reducer/state-machine unit tests
- Fake-timer cancellation tests
- Multi-thread end-to-end test
- Replayed/out-of-order event tests

### WP-08 — Implement real vertical feature slices

Addresses: CCC-014, CCC-018, CCC-019 and completes CCC-001/002.

Implement these slices one at a time. A slice is accepted only when its UI, API, service, persistence/event behaviour, error states, authorisation, tests, and documentation are complete.

#### Slice A — Projects and threads

- Register and validate a local repository.
- List projects and threads.
- Create, rename, pin, archive, and unarchive threads.
- Persist and reload state.

#### Slice B — Turns and steering

- Submit a user instruction.
- Stream lifecycle events and messages.
- Stop, resume, retry, and steer with defined semantics.
- Preserve final status across reload.

#### Slice C — Approvals

- Create an approval request with consequence, scope, owner, and expiry.
- Approve once, approve for defined session scope, or decline.
- Enforce decisions in the backend before executing the protected action.
- Record actor, timestamp, decision, scope, and result.

#### Slice D — Files and diffs

- Enumerate only files beneath an authorised workspace root.
- Read files with size/binary/symlink protections.
- Render real diffs tied to a worktree and commit/base reference.
- Persist review verdicts and make “apply” semantics explicit.
- Never treat visual approval as permission to run an unrelated destructive action.

#### Slice E — Tests and processes

- Display processes actually owned by the application.
- Run allowlisted test commands in the correct workspace.
- Stream output with truncation/redaction and retain exit status.
- Terminate only owned processes.
- Display test results from parsed execution evidence, not fixtures.

#### Slice F — Diagnostics and telemetry

- Use a provider interface with explicit `available`, `unavailable`, and `demo` states.
- Close HTTP clients during application shutdown.
- Use strict validation and provider-specific query construction; regex removal of suspicious words is not a security boundary.
- Enforce timeouts, response-size limits, trace ID validation, and redaction.
- Do not claim privacy/redaction unless the configured pipeline is verified.

Acceptance criteria for every slice:

- Happy path passes through the real backend.
- Unauthorised and wrong-owner requests fail.
- Invalid inputs produce actionable errors.
- Backend unavailability is represented truthfully.
- Reload restores persisted final state.
- Enabled controls have observable effects; unavailable controls are disabled and explained.
- Audit/event records correlate the request and result.

### WP-09 — Accessibility and responsive interaction

Addresses: CCC-015, CCC-016, CCC-022, CCC-023.

Required work:

- Fix nested interactive controls in thread rows by separating row selection and action menu semantics.
- Replace clickable `div` elements with buttons/links or implement complete keyboard semantics only when a native element cannot be used.
- Give the thread filter button an accessible name.
- Correct `role="feed"` structure or use a more suitable landmark/list pattern.
- Correct heading hierarchy.
- Associate every label and description with its input; propagate `required`, error, and status semantics.
- Use `var(--accent-foreground)` or another verified colour pairing rather than white text on the dark-theme accent.
- Provide visible focus indicators, logical focus order, Escape handling, focus trapping/restoration, and no keyboard traps.
- Remove application-wide `select-none`; apply it only to controls where selection is genuinely undesirable.
- Support 320 CSS-pixel reflow by using overlays/drawers or breakpoint-aware panels.
- Ensure 200% text zoom does not hide controls or content.
- Respect reduced-motion preferences for spin, pulse, bounce, and transition effects.
- Ensure status is not conveyed by colour/icon alone.
- Provide accessible names for copy, close, menu, and icon-only controls.
- Announce meaningful async state changes without flooding live regions.

Baseline axe findings to close:

- `aria-required-children`
- `button-name`
- `color-contrast`
- `heading-order`
- `nested-interactive`

Acceptance criteria:

- Axe reports no critical or serious violations in all core screens and both themes; any remaining lower-impact item has documented justification and owner.
- Project registration, thread selection, instruction submission, approval, stop, diff review, and settings journeys are operable by keyboard alone.
- Core screens reflow at 320px and work at 200% zoom without loss of content or functionality.
- Form errors and dynamic operation states are announced by a screen reader.
- Manual checks are completed with at least one Windows screen reader and recorded.

Required evidence:

- Automated axe report per core route/state and theme
- Keyboard journey checklist
- 320px and 200% zoom screenshots
- Manual screen-reader notes, including limitations

### WP-10 — Test strategy, CI, dependency, and quality gates

Addresses: CCC-012, CCC-013, CCC-025, CCC-026 and verifies all other findings.

Required work:

- Add backend unit tests for services and state machines.
- Add backend integration tests for database, SSE, authentication, worker supervision, and worktrees.
- Add frontend unit/component tests for reducers, forms, controls, error states, and accessibility.
- Add browser end-to-end tests for core journeys.
- Add lint, formatting, type-checking, build, dependency, and secret-scanning commands.
- Add CI using clean dependency installation and disposable data/workspace directories.
- Pin supported Python and Node versions.
- Add a Python dependency vulnerability audit based on the committed lock/manifest.
- Run npm audit against the committed lockfile rather than incidental packages in a developer’s `node_modules`.
- Establish a bundle budget and split large inspector/diff functionality when justified by measurement.
- Make test fixtures unmistakably synthetic and inaccessible from live production code.

Minimum required automated scenarios:

- Root application startup
- Migration empty/upgraded/corrupt cases
- Authentication and project isolation
- SSE disconnect, reconnect, replay, slow subscriber, and duplicate event
- Worker success, timeout, malformed response, crash, and stderr flood
- Worktree traversal, dirty cleanup, and concurrent operations
- Approval ownership and idempotency
- Stop-versus-complete race and thread switching
- Backend unavailable and partial-failure UI
- Axe checks in light/dark themes
- 320px responsive smoke test

Acceptance criteria:

- One documented root command runs the full required verification suite from a clean checkout.
- CI fails on test, type, lint, build, migration, accessibility, dependency, or secret-scan failures.
- No production source imports test fixtures.
- Bundle size stays within the documented budget or has an accepted exception supported by measurements.
- Regression tests are demonstrated to fail against the original faulty behaviour where practical.

### WP-11 — Operational readiness and observability

Addresses operational aspects of CCC-005, CCC-006, CCC-009, CCC-011, CCC-018, and CCC-020.

Required work:

- Replace development-only launchers with explicit `dev` and local production-like commands.
- Use application-owned PID/process records rather than port-wide force termination.
- Add health endpoints that distinguish liveness and readiness.
- Readiness must account for database migrations and required worker/diagnostics dependencies without fabricating health.
- Add structured logs with request, project, thread, turn, operation, and event correlation IDs.
- Redact credentials, prompts/content where configured, filesystem secrets, and diagnostic attributes according to documented policy.
- Add bounded log retention and output truncation.
- Add graceful shutdown for SSE subscribers, workers, database sessions, and HTTP clients.
- Document backup, restore, upgrade, incident response, and safe shutdown.

Acceptance criteria:

- Ctrl+C/service stop closes resources within a documented timeout.
- Readiness fails when a required dependency is unusable and recovers when restored.
- Logs correlate a UI action through API, service, worker, persistence, and event result.
- Redaction tests prove configured sensitive values do not appear in logs/events.
- No persistent command uses auto-reload or binds publicly by default.

## 9. Recommended dependency order

```text
WP-00 Repository baseline
  -> WP-01 Truthful product state
  -> WP-02 Backend/data foundation
      -> WP-03 Security boundary
      -> WP-04 Event transport
      -> WP-05 Worker supervision
      -> WP-06 Worktree safety
          -> WP-07 Frontend integration/state
              -> WP-08 Real feature slices
                  -> WP-09 Accessibility/responsive completion
                  -> WP-10 Full quality gates
                      -> WP-11 Operational readiness
```

Parallel work is permitted only where file ownership and contracts are clear. Shared protocol, model, migration, and store files require coordination to avoid conflicting assumptions.

## 10. API and error contract requirements

Before frontend integration, publish an OpenAPI-backed contract with:

- Stable resource identifiers
- Request and response schemas
- Authentication requirements
- Project/thread ownership rules
- Idempotency behaviour for mutations
- Optimistic concurrency or expected-state behaviour where races matter
- Error codes suitable for UI handling
- Pagination and limits
- Event correlation IDs
- Capability/availability discovery

Minimum error categories:

- `authentication_required`
- `forbidden`
- `not_found`
- `conflict`
- `invalid_state`
- `validation_failed`
- `rate_limited`
- `dependency_unavailable`
- `operation_timeout`
- `operation_cancelled`
- `internal_error`

Errors must not expose stack traces, secrets, raw subprocess environment, or unrestricted filesystem paths to untrusted clients.

## 11. Approval and turn state models

### 11.1 Approval state

Suggested transitions:

```text
pending -> approved_once
pending -> approved_session
pending -> declined
pending -> expired
```

Terminal decisions are immutable. A new request is required for a new decision. Approval records must include:

- Approval ID
- Project/thread/turn/tool-call owner
- Requested action and normalised target
- Consequence and risk
- Request time and expiry
- Decision, scope, actor, and decision time
- Execution result or reason no execution occurred

Approval UI counters must be derived from pending approvals owned by the thread.

### 11.2 Turn state

Suggested transitions:

```text
queued -> running -> completed
queued -> cancelled
running -> stopping -> interrupted
running -> failed
interrupted -> queued (new resume operation)
failed -> queued (new retry operation)
```

Rules:

- Completed, interrupted, failed, and cancelled are terminal for that operation ID.
- Resume/retry creates a new operation ID and retains lineage.
- A late event for a superseded operation may be recorded for audit but cannot alter the current turn state.
- Stop is idempotent.
- UI status is derived from the authoritative operation/turn state, not a global timer.

## 12. Audit protocol for future remediation reviews

Future auditors must independently verify remediation rather than relying on an Antigravity summary.

### 12.1 Intake

Collect:

- Issue IDs and finding IDs claimed fixed
- Commit or pull-request identifiers
- Architecture decisions
- Migration identifiers
- Antigravity evidence report
- Known limitations and accepted exceptions

### 12.2 Change review

For each finding:

1. Re-read the baseline evidence in this document.
2. Inspect the complete diff and adjacent code paths.
3. Confirm the fix is reachable in live mode.
4. Look for scope leakage, silent fallbacks, disabled validation, and fixture substitution.
5. Verify tests cover the original failure mechanism, not merely a happy path.
6. Check that new code does not create an equivalent issue elsewhere.
7. Assign `verified`, `partially verified`, `not verified`, or `regressed`.

### 12.3 Required fresh audit commands

Exact commands may change as tooling is established, but the canonical equivalents must cover:

```powershell
# Repository hygiene
git status --short

# Backend
python -m pytest
python -m ruff check backend tests
python -m mypy backend
python -m pip_audit

# Frontend
npm ci
npm run lint
npm run typecheck
npm run test
npm run test:e2e
npm run test:a11y
npm run build
npm audit --package-lock-only

# Migrations
<migration-command> upgrade head
<migration-command> downgrade <supported-target>
<migration-command> upgrade head
```

If the project chooses different tools, update these commands in this document and the README through a reviewed change.

### 12.4 Runtime audit journeys

Auditors must exercise at least:

1. Start from clean data and register a synthetic repository.
2. Create two projects and two threads.
3. Run concurrent turns in different threads and switch between them.
4. Stop one turn just before completion and verify it remains interrupted.
5. Create approvals in two threads and decide only one.
6. Disconnect and reconnect the event stream with replay.
7. Attempt cross-project access and unauthenticated access.
8. Run a controlled test command and verify real output/exit status.
9. Create and safely clean a disposable worktree; attempt prohibited paths.
10. Disable diagnostics and verify truthful unavailable state.
11. Complete keyboard-only core journeys.
12. Check light/dark themes, 320px reflow, and 200% zoom.
13. Restart the application and verify persisted final state.

### 12.5 Security re-check

- Listener interfaces and ports
- CORS allowlist
- Authentication and project isolation
- Rate, payload, queue, and timeout limits
- Path canonicalisation and symlink/junction handling
- Command allowlisting and argument handling
- Secret/PII redaction
- Database file permissions and backup handling
- Dependency vulnerability reports
- No debug/reload mode in persistent operation

### 12.6 Audit report format

```markdown
# Remediation Audit Report

## Status
accepted | partially accepted | rejected | escalated

## Scope
- Finding IDs reviewed
- Commit/PR range
- Environment

## Acceptance matrix
| Finding | Status | Evidence | Residual risk | Follow-up |

## Commands and results
| Command | Exit code | Summary | Artifact |

## Runtime journeys
| Journey | Pass/Fail | Evidence | Notes |

## Security and accessibility
- Results
- Exceptions

## Regressions or new findings
- Stable new finding ID
- Severity
- Evidence

## Human decisions required
- Smallest specific decision
```

## 13. Evidence register

Antigravity must maintain an evidence register during remediation. It may live in the issue system or a versioned report, but it must be linkable from the final handoff.

| Field | Required content |
|---|---|
| Finding/work-package ID | Stable ID from this brief |
| Acceptance criterion | Exact criterion being proven |
| Implementing subagent | Specialist identity/role that authored the implementation |
| Reviewing subagent | Independent specialist identity/role where required |
| Implementation reference | Commit, PR, or file reference |
| Verification command | Exact command or runtime procedure |
| Environment | OS, Python, Node, browser, database mode |
| Result | Pass/fail and exit code |
| Artifact | Log, screenshot, report, trace, or test file |
| Date/time | RFC-3339 timestamp |
| Residual risk | Known uncertainty or `none identified` |

Evidence must use synthetic, non-sensitive data.

## 14. Global Definition of Done

The remediation program is accepted only when all of the following are true:

- All blocker and high findings are `verified` by an independent audit.
- Medium findings are verified or have explicit human-approved exceptions with owner and expiry.
- Live mode has no fixture-backed operational state.
- No enabled control fabricates an effect or success result.
- Frontend and backend are integrated through documented typed contracts.
- Authentication, ownership checks, bounded resources, and loopback defaults pass negative tests.
- Approval and turn state-machine race tests pass.
- Worktree deletion safety tests pass on Windows.
- Database migrations, backup, restore, and fixed-path tests pass.
- Worker crash, timeout, EOF, malformed output, and shutdown tests pass.
- Root clean-clone setup and full verification commands pass.
- Accessibility automated and manual evidence meets WP-09 criteria.
- Core screens reflow at 320px and work at 200% zoom.
- Dependency and secret scans have no unaccepted high/critical results.
- Documentation describes actual behaviour and limitations.
- A future auditor can reproduce the evidence without unpublished local setup.
- Every implementation change is attributable to a bounded specialist subagent assignment.
- Antigravity remained in the project-manager/reviewer role and did not author remediation implementation.
- Security-sensitive work has independent specialist review evidence.

The following are not sufficient completion evidence:

- “Build passes” without behavioural tests.
- “Tests pass” when only existing trivial tests ran.
- Screenshots without API/runtime evidence.
- Agent-generated summaries without raw command results.
- Fixture-driven demonstrations.
- Controls that change only local display state.
- A successful happy path without security, ownership, cancellation, and failure-path tests.

## 15. Human decisions and safe defaults

These decisions must be confirmed before the relevant final implementation. Foundational work that does not depend on them may proceed using the safe defaults.

| Decision | Options | Safe default pending decision |
|---|---|---|
| Repository ownership | Standalone repository or deliberate parent monorepo | Standalone application repository |
| Authentication model | Single-user local token, OS identity, or multi-user accounts | Loopback-only single-user local token |
| Existing SQLite data | Preserve, migrate, archive, or discard | Preserve read-only backups; use new disposable dev DB |
| Codex worker command/protocol | Exact executable, version, and JSON-RPC contract | Do not expose worker controls until confirmed |
| Diff approval semantics | Review record only or permission to apply | Review record only |
| Diagnostics provider | SigNoz, another provider, or disabled | Disabled/unavailable, truthfully shown |
| Supported platforms | Windows only or cross-platform | Windows is required; avoid claiming others |
| LAN/remote access | Local only or authenticated network service | Local loopback only |

Any choice that expands exposure, destructive authority, or data handling requires a threat-model update and explicit human approval.

## 16. Antigravity completion handoff

At the end of each work package, Antigravity must provide:

```markdown
## Status
accepted | escalated

## Findings addressed
- CCC-...

## Delegation record
| Assignment | Implementing subagent/role | Owned scope | Reviewing subagent/role | Outcome |

## Acceptance criteria
- [x] Criterion — evidence link
- [ ] Criterion — failure/blocker

## Changes
- Concise implementation summary

## Verification
| Command/journey | Exit/result | Evidence |

## Security and data impact
- Authentication/authorisation changes
- Migration/data changes
- Destructive operations performed: none or explicit list

## Open risks
- Residual uncertainty

## Human input required
- Smallest decision, or `none`
```

Do not use “done,” “fixed,” “secure,” “accessible,” “verified,” or equivalent completion language unless the corresponding evidence is present and current.

Antigravity must also state explicitly that it authored no remediation implementation. If it did author implementation, the affected work package cannot be accepted under this brief and must be independently re-reviewed and remediated through the required subagent process.

## 17. Baseline validation record from the original audit

Recorded on 2026-08-29:

| Check | Baseline result |
|---|---|
| `npm run build` | Passed; main JavaScript approximately 496.34 KB, 141.62 KB gzip |
| `npm audit --package-lock-only --json` | Zero known vulnerabilities across 153 locked dependencies |
| `python -m compileall -q backend tests` | Passed |
| `python -m pytest -q` from project root | Failed during collection: `ModuleNotFoundError: No module named 'database'` |
| Pytest with backend manually added to import path | Two tests passed; three warnings |
| Axe against actual Vite application | Eight occurrences across five rule categories |
| Frontend network integration search | No API/SSE/WebSocket integration found |
| Git repository inspection | Git root was `F:\Projects`; no commits; application untracked |
| Database inspection | Both root and backend `codex.db` files present |

This baseline is historical evidence, not proof of current state. Future audits must rerun the checks.

## 18. Change control for this document

- Keep finding IDs stable.
- Do not delete a finding after remediation; change its status in audit reports.
- Add newly discovered findings using the next `CCC-` ID.
- Changes that weaken acceptance criteria require human approval and a recorded rationale.
- Update commands and paths when tooling changes, but preserve the intent of each gate.
- Record significant architecture changes in an ADR and link them from the relevant work package.
- Future briefs and audits should cite this file as the canonical remediation baseline until it is formally superseded.

## 19. Mandatory instruction to Antigravity

The following instruction applies whenever this brief is provided to Antigravity:

> Read this document in full and treat it as the authoritative remediation specification. You are the project manager and orchestrator, not an implementation agent. You must not write or modify remediation code, tests, configuration, migrations, CI, dependency manifests, launch scripts, infrastructure, or security controls yourself. Decompose the program into bounded assignments mapped to the stable `CCC-` finding IDs and work packages. Select subagents whose skills are tailored to each assignment, give them explicit scope and file ownership, and prevent conflicting concurrent writes. Maintain the plan, dependency map, status, risks, decisions, and evidence register. Review every subagent handoff, obtain separate specialist review for high-risk work, and run fresh verification before accepting it. If a subagent fails or work is incomplete, re-brief or reassign it; do not take over the coding. Begin with WP-00 and proceed according to the dependency order. Do not attempt the entire program as one change. Use the safe defaults for unresolved human decisions, but escalate before destructive operations, network exposure, authentication expansion, or migration of existing data. Do not claim a finding or phase complete without the evidence required by this document.

This instruction overrides any convenience preference to implement directly. Role separation is part of the remediation Definition of Done.
