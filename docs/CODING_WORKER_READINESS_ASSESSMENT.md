# Coding Worker Readiness Assessment

**Prepared:** 2 October 2026 (Australia/Sydney)  
**Scope:** Evidence-based readiness assessment for the Business Assistant engineering-ticket handoff  
**Status:** Candidate local execution target exists; automatic dispatch is **not approved or ready**  
**Assessment boundary:** Source inspection and two local, read-only worker handshake tests. No application code, configuration, data, or secrets were changed or read.

---

## 1. Decision

The Business Assistant must not dispatch engineering work to the FastAPI Bookings Resident Agent, its remediation executor, or the SMS agent-console tab. Those components can report success without applying a change or running the stated verification.

There is, however, a credible local development candidate: **Codex Control Centre** at `F:\Projects\codex-control-centre`, which starts the installed native Codex app-server through JSON-RPC and binds a worker to a per-thread Git worktree. The native binary was discovered locally and both real handshake tests passed on 2 October 2026.

That candidate is not yet an engineering-ticket worker. It has no inbound ticket contract, ticket claim/lease mechanism, FastAPI Bookings connector, approved-repository allowlist, durable idempotency boundary, reliable result/commit handback, independent review gate, or production-safe authentication model. At assessment time nothing was listening on port 8100, so it is not presently a running local service.

**Operational decision:** until the remediation stages and acceptance tests in this document pass, Business Assistant tickets must remain `awaiting_engineering`. They may be reviewed and manually assigned by an owner, but must not be automatically dispatched.

---

## 2. Evidence gathered

| Area | Evidence | Finding |
|---|---|---|
| Resident remediation executor | `app/services/resident_agent/executor.py:80-113` | With `simulate_only=False`, it only records proposed file paths. It does not write the proposed diff or run verification, then returns `success: true`, `status: EXECUTED`, and `verified: true`. |
| Resident remediation planner | `app/services/resident_agent/remediation_planner.py:18-186` | Plans are static templates or generated placeholder descriptions/diffs; they are not a worker task protocol or an actual code-change engine. |
| Resident remote approval | `app/api/routers/resident_agent.py:158-194` | An approved command invokes the same no-op executor with `simulate_only=False` and returns an “executed successfully” response. |
| Resident frontend | `frontend/src/pages/admin/resident-agent.tsx:428-460` | The interface calls the remediation endpoint with `simulate_only: false` and presents a success toast when that endpoint reports success. |
| SMS agent console | `frontend/src/pages/admin/sms/agent-console-tab.tsx:25-128` | Initial log entries, periodic activity, command parsing, and successful turns are browser-local synthetic state. The component has no authenticated API call. |
| Candidate worker launcher | `F:\Projects\codex-control-centre\backend/services/worker.py:131-190` | Launches a subprocess, performs the app-server `initialize`/`initialized` handshake, and communicates over JSON-RPC. |
| Candidate worktree binding | `F:\Projects\codex-control-centre\backend/routers/turns.py:234-284` and `backend/services/worker_manager.py:59-98` | A turn is associated with a project repository and a thread-specific worktree before the app-server receives `cwd` and `workspaceRoot`. |
| Candidate approval handling | `F:\Projects\codex-control-centre\backend/services/worker.py:300-365` and `backend/services/governance_service.py:29-154` | Tool requests are classified and some require persisted approval. The current managed profile auto-approves medium-risk file edits and Git changes, so it is insufficient as the ticket-worker policy. |
| Candidate persistence | `F:\Projects\codex-control-centre\backend/models/codex.py:6-90` | Projects, threads, turns, items, tool approvals, and subagent records exist, but no engineering ticket, claim, lease, result, commit, review, or dispatch-outbox records exist. |
| Current local availability | Local process inspection on 2 October 2026 | Native `codex.exe` is installed. No listener was present on port 8100. |
| Live integration check | `tests/test_worker.py::test_real_codex_app_server_if_available` and `tests/test_codex_app_server.py::test_handshake_and_discovery_real_app_server` | Both passed locally: `2 passed` in 8.13 seconds. This proves only executable discovery and the app-server handshake, not a task, file change, test run, review, or handback. |

The assessment did not read `.env` files, service tokens, databases, customer data, message bodies, or worker-history records.

---

## 3. Current-state classification

| Component | Classification | May receive Business Assistant tickets? | Reason |
|---|---|---:|---|
| Resident Agent audit and advisory functions | Read-only/advisory capability | No | It is not an isolated coding worker. |
| Resident remediation planner | Proposal generator | No | Its output is not an executable, bounded work package. |
| Resident remediation executor | Unsafe simulated-success path | No | It does not apply code or execute verification. |
| SMS agent-console tab | Demonstration-only interface | No | Its state is synthetic and disconnected from backend execution. |
| Codex Control Centre + native app-server | Development candidate | Not yet | Real handshake and worktree-oriented plumbing exist, but essential ticket, hardening, and evidence gates are absent. |

The candidate must be treated as a separate local engineering system. It is not part of the FastAPI Bookings runtime and must never receive customer-facing access tokens, tenant database credentials, production environment files, or direct deployment authority.

---

## 4. Candidate strengths and gaps

### Strengths that can be retained

- The installed app-server executable resolves to a native binary, rather than a browser-only simulation.
- The worker process uses JSON-RPC over standard input/output and supports turn start, steering, interruption, notification handling, and tool approvals.
- The turn route resolves a project repository, creates a thread-specific worktree, and passes the resolved directory as both `workspaceRoot` and `cwd`.
- The candidate has persisted records for threads, turns, individual events, and approval requests; it also has event streaming and cascade cancellation primitives.
- Existing tests cover the real executable handshake, worktree path selection, interruption, and approval-response plumbing. Most lifecycle assertions still use mocked workers, so they are necessary but not sufficient evidence.

### Release-blocking gaps

1. **No ticket ingress or linkage.** FastAPI Bookings does not call the candidate, and neither system has a shared, typed ticket-dispatch protocol.
2. **No authoritative task claim.** There is no durable single-claim lease, heartbeat, expiry, retry policy, or reconciliation logic for a work item.
3. **No fixed repository authority.** The candidate project API accepts caller-provided repository paths. A ticket connector must not pass any repository path, branch, worktree name, command, or filesystem path supplied by a model or tenant user.
4. **Fallback worktree copying is unacceptable.** `backend/services/worktree_service.py:165-227` copies files into a directory if `git worktree add` fails. A ticket worker must fail closed when a real Git worktree cannot be created from the recorded base commit.
5. **Current approvals are too permissive.** In the managed governance profile, medium-risk writes and Git operations do not require approval (`backend/services/governance_service.py:108-127`). Ticket execution needs a strict, policy-owned allowlist and a separate owner approval for any non-approved class of action.
6. **No reliable evidence bundle.** Current records can retain raw prompts and arbitrary notification payloads (`backend/models/codex.py:34-58`; `backend/services/worker.py:405-424`). The user-facing ticket channel must receive only a sanitised summary, while the private evidence store needs a documented retention and access policy.
7. **No completion proof.** No contract requires an actual diff/commit identifier, recorded test command and exit code, independent reviewer decision, or explicit failed/no-change outcome.
8. **No ticket-scoped access control.** Candidate authentication is a shared bearer-token comparison and has a development default (`backend/middleware/auth.py:1-17`; `backend/config.py:10-31`). It is not sufficient for a cross-process production connector.
9. **No repeatable source baseline.** The Control Centre folder currently sits inside a parent Git worktree whose `master` branch has no commits and reports a large set of unrelated untracked siblings. Its source must first be placed under controlled version history or another immutable release artifact before it can become a dependable worker target.
10. **No active service.** No process was listening on port 8100 during this assessment, so there is no currently running handoff endpoint.

---

## 5. Minimum secure ticket-to-worker contract

The following is the smallest acceptable contract. It deliberately separates the user-visible support ticket from the private engineering job.

### 5.1 Public support-ticket record in FastAPI Bookings

The user-facing record may contain only:

- `ticket_id`, opaque public reference, tenant ID, initiating user ID, and conversation ID;
- category, severity, title, observed behaviour, desired outcome, and acceptance criteria;
- sanitised evidence references rather than copied customer content;
- approval state and policy classification;
- stable deduplication key and a payload version/hash;
- lifecycle state: `awaiting_engineering`, `approved_for_dispatch`, `claimed`, `in_progress`, `awaiting_review`, `resolved`, `failed`, `cancelled`; and
- a user-safe progress message and final resolution summary.

It must not expose the worker prompt, source paths, access tokens, raw terminal output, branch credentials, internal commands, private code review, or unredacted errors.

### 5.2 Private engineering-job envelope

Only a trusted server-side dispatcher may construct this envelope after policy checks. Required fields are:

```text
job_id                    UUID, generated by the dispatcher
source_ticket_id          immutable internal ticket reference
idempotency_key           unique per approved ticket payload version
repository_key            fixed allowlisted value: fastapi-bookings
repository_root           server configuration only; never ticket/model input
base_commit               resolved immutable commit SHA before worktree creation
branch_name               deterministic, e.g. codex/ticket-<job_id>
scope_allowlist           approved repository-relative paths/modules
task_statement            bounded engineering objective
acceptance_commands       fixed reviewed command allowlist
approval_class            ordinary / elevated / denied
requested_by              initiating user and tenant references
correlation_id            tracing-only opaque identifier
expiry_at                 dispatch authorisation expiry
```

The envelope must reject secrets, credentials, database URLs, customer identities, message bodies, arbitrary shell commands, arbitrary models, arbitrary repository paths, arbitrary branches, and external deployment instructions. Sensitive supporting evidence should be kept behind a separately authorised internal reference that the worker cannot read by default.

### 5.3 Results contract

The worker must return exactly one terminal result for a claimed job:

```text
job_id, claim_epoch, terminal_status,
base_commit, result_commit_or_diff_id,
changed_paths, test_results[{command_id, exit_code, duration_ms}],
review_status, review_reference,
sanitised_summary, failure_code, completed_at
```

`success` is valid only if a real worktree change exists, the changed paths satisfy the scope allowlist, every required test result was captured from an actual process, and independent review accepted the result. A blocked or no-change outcome must be explicit rather than represented as success.

---

## 6. Required isolated execution model

```text
Business Assistant
    -> creates a sanitised support ticket only
    -> owner/policy approval
    -> FastAPI Bookings dispatch outbox
    -> trusted local dispatcher
    -> fixed Control Centre project for FastAPI Bookings
    -> real Git worktree at recorded base commit
    -> native app-server coding turn with strict tool policy
    -> actual tests + recorded exit results
    -> independent reviewer
    -> private evidence bundle + sanitised ticket update
    -> owner-controlled merge/deployment process
```

Mandatory controls:

1. The dispatcher resolves the repository from a server-side allowlist. It never accepts a path from a ticket, a model, an HTTP request body, or a conversation.
2. Worktree creation must use `git worktree add` at the recorded commit. If that fails, the job fails before any turn starts; file-copy fallback is prohibited.
3. The worker process must run with the worktree as its only writable project directory and with a restrictive permission profile. It must not be started with broad host filesystem access.
4. Network access, package installation, secret reads, remote pushes, merges, and deployments are denied by default. An exception requires a separately recorded owner approval and cannot be inferred from ticket text.
5. Exactly one dispatcher transaction may claim a job. Use a database unique constraint plus a lease token, expiry, heartbeat, and compare-and-set terminal transition.
6. Each job pins the source baseline SHA and emits its changed-path list. A dirty primary repository or a changed baseline invalidates the job before execution.
7. An independent reviewer receives the diff and recorded results, not an assertion of success. The worker cannot approve its own work.
8. The worker may create a commit in its isolated branch only after required tests pass. It must never merge, push, deploy, alter production data, send messages, or create bookings.
9. Cancellation revokes pending approvals, interrupts the turn, marks the claim as cancelled, and preserves enough structural state for reconciliation. A new attempt uses a new claim epoch.

---

## 7. Staged remediation plan

### Stage 0 — Freeze and choose ownership

**Outcome:** A controlled, reproducible local worker candidate is selected.

- Put the Control Centre source under an immutable commit or release artifact; do not use the current uncommitted parent worktree as a deployment baseline.
- Record the native app-server version/binary identity and rerun the real handshake check after the source baseline is fixed.
- Name one owner for the dispatcher and one owner for independent review.
- Decide whether the worker is development-only or has a separately approved production control plane. The default is development-only.

### Stage 1 — Build ticket persistence without dispatch

**Outcome:** FastAPI Bookings can create, deduplicate, approve, cancel, and display user-safe engineering tickets while every ticket remains `awaiting_engineering`.

- Add tenant/user-scoped ticket records, append-only events, payload hashing, confirmation binding, and redaction.
- Add a transactional outbox record but do not run a consumer.
- Prove a Business Assistant user cannot see private worker information or another tenant’s ticket.

### Stage 2 — Harden the candidate control plane

**Outcome:** The local worker is safe enough to receive a synthetic job from a trusted dispatcher.

- Remove or disable the file-copy fallback; require a valid Git repository, recorded base SHA, clean dedicated worktree, and an explicit failure otherwise.
- Replace the shared development-default bearer approach for the connector with a dedicated local service identity, rotation procedure, and transport restricted to the intended host boundary. Do not put credentials in query strings.
- Enforce a repository-key allowlist and resolve the FastAPI Bookings repository path only in server configuration.
- Use a strict tool policy: all writes, commands, installs, network access, secret access, remote operations, and deployment attempts require explicit policy handling; ordinary ticket execution has no deployment path.
- Add retention/redaction controls for worker prompts, event payloads, stderr, and persisted items.

### Stage 3 — Implement a narrow dispatcher connector

**Outcome:** A policy-approved synthetic ticket can create one job, one worktree, and one traceable worker turn.

- The dispatcher claims the outbox row idempotently and constructs the private envelope server-side.
- The candidate exposes a dedicated job endpoint or a similarly narrow authenticated adapter. It must not reuse general project/path creation endpoints for ticket input.
- Persist job/claim/lease/heartbeat/result records and report only sanitised events to FastAPI Bookings.
- Start with owner-approved, ordinary, low-risk maintenance tasks and a one-job concurrency limit.

### Stage 4 — Evidence, review, and recovery

**Outcome:** The worker can demonstrate an end-to-end safe task lifecycle on a disposable synthetic repository and a non-production FastAPI Bookings worktree.

- Require actual change, test output, diff/commit reference, changed-path validation, independent reviewer decision, cancellation recovery, and duplicate-delivery reconciliation.
- Demonstrate a truthful blocked outcome when approval, worktree, tool policy, test, or review fails.
- Add alerts for expired claims, stuck turns, approval timeouts, worker exits, and result-delivery failures.

### Stage 5 — Controlled limited use

**Outcome:** The owner may manually approve a constrained set of real development tickets.

- No automatic dispatch from a conversation.
- No production deployment or external action.
- Every ticket remains owner-visible through review and merge.
- Expand scope only after a fresh independent security and operational audit.

---

## 8. Acceptance tests before the handoff gate can open

| Test | Required proof |
|---|---|
| Native worker readiness | Real installed app-server passes handshake and starts a turn in a real Git worktree, not a copied fallback directory. |
| Immutable baseline | Job records a commit SHA; the worktree HEAD equals that SHA before the turn starts. |
| Scope restriction | A worker attempt to edit an out-of-scope path is rejected and leaves no accepted result. |
| Idempotent dispatch | Replaying the same outbox event creates or resumes one job only; no second worker starts. |
| Claim recovery | A killed worker’s lease expires or is reconciled; retry uses a new claim epoch without duplicate result publication. |
| Actual modification | A synthetic maintenance task produces a real diff/commit in the isolated branch. |
| Actual verification | Required tests execute as separate processes; captured exit codes, duration, and output references prove their result. |
| Honest failure | A deliberately failing test produces `failed` or `awaiting_review`, never success. |
| Approval policy | Secret read, network write, install, push, merge, deployment, and unapproved shell command are denied or require a recorded owner approval. |
| Review separation | A distinct reviewer accepts/rejects the diff and evidence. The worker cannot mark itself reviewed. |
| Tenant and privacy isolation | One tenant cannot read or influence another tenant’s ticket; public ticket events contain no private worker prompt, source detail, raw command output, credentials, or customer content. |
| Cancellation | Cancelling a ticket interrupts the turn, declines pending approvals, stops result publication, and leaves a reconciled terminal state. |
| No simulated success | A test asserts that claiming a job without a diff, recorded test exits, and review is rejected as non-success. |

---

## 9. Unblockers and owner decisions

1. Approve the Control Centre only as a **development candidate** after its source is checkpointed in a controlled repository or immutable release artifact.
2. Assign the ownership boundary: FastAPI Bookings owns tickets and user-safe status; the local control plane owns worktrees, tool approvals, worker lifecycle, and private evidence.
3. Approve the strict execution policy and explicitly prohibit fallback file copying, arbitrary repository paths, deployment, remote push, and unapproved network/package actions.
4. Decide the human approval rule for ordinary engineering dispatch. Recommended initial rule: every dispatch is owner-approved.
5. Fund the dedicated connector, job persistence, reconciliation, retention policy, and independent review workflow. None is currently implemented.
6. Require a clean non-production environment and synthetic ticket/evidence fixtures for acceptance testing. Do not validate this path against customer data, live messaging, bookings, payments, or production secrets.

---

## 10. Audit conclusion

The current Resident Agent and SMS console are demonstrably unsuitable as coding-worker targets because they include simulated or no-op success paths. The local Control Centre is the only identified candidate with a real native app-server handshake and worktree-oriented execution design. It is promising infrastructure, not a finished coding-worker integration.

The Business Assistant plan is correct to keep automatic engineering dispatch disabled. The earliest safe milestone is ticket creation and owner review; actual handoff becomes eligible only after every Stage 0–4 gate and acceptance test in this assessment has reproducible evidence.

