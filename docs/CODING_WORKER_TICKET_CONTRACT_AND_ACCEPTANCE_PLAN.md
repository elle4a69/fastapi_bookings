# Coding Worker Ticket Contract and Acceptance Plan

**Prepared:** 2 October 2026 (Australia/Sydney)  
**Status:** Specification only — no dispatcher, worker, connector, or deployment path is implemented or authorised by this document  
**Scope:** The future, private handoff boundary between a FastAPI Bookings engineering ticket and an isolated coding worker

---

## 1. Decision and scope

Engineering tickets may eventually be handed to a separately operated coding worker, but only through the bounded contract in this document. The Business Assistant creates and displays sanitised tickets; it neither constructs a worker prompt nor receives code-execution capability.

This specification expands [CODING_WORKER_READINESS_ASSESSMENT.md](CODING_WORKER_READINESS_ASSESSMENT.md). It does not select, launch, connect to, or approve a worker. The current state remains:

- the Resident Agent execution routes fail closed;
- the SMS coding-worker status panel is non-interactive and reports that no worker is connected;
- tickets must remain `awaiting_engineering` until every applicable acceptance gate below has reproducible evidence; and
- merge, push, deploy, production-data access, booking changes, payment actions, and customer communications are out of scope and prohibited.

The target must be a dedicated development control plane with an immutable source baseline and a real Git worktree. It cannot be a browser simulation, a no-op service, a general-purpose repository-path API, or a component inside the FastAPI Bookings runtime.

---

## 2. Trust boundaries

```text
Authenticated application user
  -> Business Assistant / support UI
  -> public, tenant-scoped ticket record
  -> policy and owner approval
  -> transactional dispatch outbox
  -> trusted dispatcher
  -> private engineering-job record and isolated worker adapter
  -> isolated Git worktree + coding worker
  -> test evidence + independent reviewer
  -> sanitised ticket event only
  -> owner-controlled merge and deployment process
```

| Boundary | Trusted input | Explicitly rejected |
|---|---|---|
| User to ticket | Sanitised issue description and authorised evidence references | Paths, shell commands, credentials, raw customer content, deployment requests |
| Ticket to dispatcher | Approved ticket revision and server-derived policy classification | Model-generated repository, branch, scope, command, worker, or environment selections |
| Dispatcher to adapter | Private job envelope signed or authenticated as a service request | Browser session cookies, tenant tokens, arbitrary URLs, caller-provided filesystem paths |
| Adapter to worker | Fixed worktree, reviewed tool policy, bounded objective | Primary repository write access, production credentials, remote push/merge/deploy authority |
| Worker to ticket | Sanitised lifecycle events and verified terminal evidence | Raw prompts, terminal streams, secrets, private source paths, approval credentials |

Tenant boundaries end at the public ticket and dispatch authorisation. The worker must not receive tenant data except the minimum sanitised engineering statement needed to address the approved issue.

---

## 3. Records and separation of public and private data

### 3.1 Public support ticket

FastAPI Bookings owns a tenant- and user-scoped ticket with these safe fields:

```text
ticket_id, public_reference, tenant_id, initiating_user_id, conversation_id,
category, severity, title, observed_behaviour, desired_outcome,
acceptance_criteria, sanitised_evidence_references, policy_class,
payload_version, payload_hash, deduplication_key, lifecycle_state,
user_safe_status, user_safe_summary, created_at, updated_at
```

The ticket must never contain a source path, worker prompt, raw worker event, shell command, credential, private branch name, database URL, customer identity, message body, or production configuration.

### 3.2 Dispatch outbox

The same transaction that moves an approved ticket revision to `approved_for_dispatch` creates one outbox row. It contains only an internal ticket reference, approved payload version/hash, dispatch policy version, idempotency key, attempt counter, and delivery state. The outbox is not a job queue visible to a user or model.

### 3.3 Private engineering job

The dispatcher owns the private job record. It may link to the internal ticket ID but is not queryable through a public ticket endpoint. It must retain the job envelope hash, fixed source baseline, claim history, status transitions, evidence references, reviewer decision, and a sanitised result suitable for publication.

Private worker output must be redacted and stored under a separate retention and access policy. The public ticket may only receive an allowlisted lifecycle event and sanitised summary after validation.

---

## 4. Private job envelope

Only the dispatcher may construct this envelope after reading an approved ticket revision and server-owned policy. No HTTP client, tenant user, model tool call, or ticket text may supply its protected fields.

```json
{
  "schema_version": 1,
  "job_id": "UUID",
  "source_ticket_id": "internal immutable ID",
  "ticket_payload_version": 1,
  "ticket_payload_hash": "SHA-256",
  "idempotency_key": "unique approved-revision key",
  "repository_key": "fastapi-bookings",
  "base_commit": "immutable full Git SHA",
  "branch_name": "server-generated deterministic branch name",
  "scope_allowlist": ["repository-relative approved path or module"],
  "task_statement": "bounded sanitised engineering objective",
  "acceptance_command_ids": ["reviewed command identifier"],
  "policy_version": "immutable policy reference",
  "approval_class": "ordinary | elevated",
  "requested_by": {"tenant_ref": "opaque", "user_ref": "opaque"},
  "correlation_id": "opaque trace ID",
  "authorised_at": "RFC 3339 timestamp",
  "expires_at": "RFC 3339 timestamp"
}
```

The adapter resolves `repository_key` through its own allowlist to a configured repository root. It must reject a repository path, worktree path, branch, test command, model choice, tool policy, environment selector, URL, secret reference, or deployment instruction supplied by any other field.

The dispatcher must validate all of the following before delivery:

1. the ticket is in `approved_for_dispatch` and its stored hash equals the approved revision;
2. approval has not expired, been revoked, or been superseded by a newer ticket revision;
3. the repository key, scope allowlist, command identifiers, and policy version are enabled by server-owned configuration;
4. the full base SHA exists in the configured repository and represents an approved clean baseline; and
5. no active or terminal-successful job already exists for the idempotency key.

---

## 5. Claim, lease, and idempotency state machine

### 5.1 States

| State | Meaning | Permitted next states |
|---|---|---|
| `awaiting_engineering` | Ticket exists but has no dispatch approval | `approved_for_dispatch`, `cancelled` |
| `approved_for_dispatch` | Approved revision and outbox entry exist | `dispatching`, `cancelled`, `expired` |
| `dispatching` | Dispatcher is atomically creating/resuming the job | `claimed`, `failed`, `awaiting_engineering` |
| `claimed` | Worker has a valid lease but has not started work | `in_progress`, `cancel_requested`, `claim_expired`, `failed` |
| `in_progress` | Worker is active in the isolated worktree | `awaiting_review`, `failed`, `cancel_requested`, `claim_expired` |
| `awaiting_review` | Worker supplied evidence; review is pending | `resolved`, `failed`, `cancel_requested` |
| `resolved` | Independent review accepted all required evidence | terminal |
| `failed` | Honest non-success terminal outcome | terminal; a new ticket revision is required to retry |
| `cancel_requested` | Cancellation is being propagated | `cancelled`, `failed` |
| `cancelled` | Work was stopped or invalidated | terminal |
| `claim_expired` | Lease ended without reconciliation | `dispatching`, `failed`, `cancelled` |
| `expired` | Dispatch approval elapsed before claim | `awaiting_engineering`, `cancelled` |

`resolved` is prohibited unless the independent reviewer accepts a real worktree change, validated changed paths, all required test results, and the evidence bundle. A no-change, blocked, interrupted, or unverified outcome is never success.

### 5.2 Atomic claim protocol

1. The dispatcher locks the outbox row and private job row in one database transaction.
2. It inserts the job with a unique constraint on `idempotency_key`, or loads the existing job when the same approved revision was already delivered.
3. It may create a claim only when the job is eligible and has no live lease.
4. The claim receives `claim_epoch`, an unpredictable `lease_token`, `claimed_at`, and `lease_expires_at`.
5. Every worker heartbeat and result submission must include the exact job ID, claim epoch, and lease token. A stale token cannot extend or complete a job.
6. The worker cannot claim a second job while its one-job concurrency limit is active.

The database must enforce the idempotency constraint; application-level checks alone are insufficient. If the adapter delivery response is lost, the dispatcher queries the job by the same immutable job ID and idempotency key rather than issuing a new job.

### 5.3 Lease and heartbeat rules

- Leases are short, finite, and renewable only by an authenticated adapter heartbeat.
- A heartbeat records structural data only: job ID, claim epoch, timestamp, phase, and opaque progress sequence.
- Repeated heartbeats may not extend a job beyond the policy maximum duration without a separate approval.
- The dispatcher marks an expired lease `claim_expired` and reconciles it before retrying.
- A retry creates a new claim epoch; it never reuses the previous lease token.

---

## 6. Authenticated adapter boundary

The worker adapter is a narrow server-to-server boundary. It must not reuse the general application API, browser authentication, or a generic project-management endpoint.

### 6.1 Minimum protocol

| Operation | Direction | Required protections |
|---|---|---|
| `submit_job` | Dispatcher → adapter | Dedicated service identity, request timestamp, nonce/idempotency key, job-envelope signature or mutually authenticated local transport |
| `heartbeat` | Adapter → dispatcher | Dedicated service identity, job ID, claim epoch, lease token, replay protection |
| `submit_result` | Adapter → dispatcher | Dedicated service identity, job ID, claim epoch, lease token, immutable evidence manifest, terminal status |
| `cancel_job` | Dispatcher → adapter | Dedicated service identity, terminal-state guard, cancellation reason category |
| `get_job_status` | Dispatcher → adapter | Dedicated service identity, job ID only, no raw worker history returned to public callers |

The implementation must define a key rotation and revocation procedure before enablement. Credentials belong in an approved server-side secret store; they must never appear in a ticket, browser response, URL, query string, log line, worker prompt, or repository file.

### 6.2 Adapter-side enforcement

Before starting a worker turn, the adapter must:

1. authenticate and authorise the dispatcher service identity;
2. validate schema version, signature/transport identity, timestamp window, nonce, expiry, and idempotency key;
3. resolve the fixed repository and repository root from `repository_key` alone;
4. ensure the source baseline is a full immutable SHA and create a real Git worktree at that SHA;
5. fail closed if `git worktree add` fails — copying files into a replacement directory is prohibited;
6. enforce the scope and test-command allowlists before execution, not by prompt text alone;
7. deny remote push, merge, deployment, external actions, package installation, unrestricted network access, and secret reads by default; and
8. record only privacy-safe structural telemetry.

---

## 7. Execution and evidence contract

The isolated worker may perform a bounded implementation turn only after the adapter records a valid claim. It has write access only to the created worktree and only for policy-approved paths. It must not mutate the primary checkout.

### 7.1 Required evidence manifest

The adapter must submit an immutable manifest with every terminal result:

```text
job_id, claim_epoch, terminal_status, base_commit,
result_commit_or_diff_id, changed_paths,
worktree_integrity_status,
test_results[{command_id, exit_code, duration_ms, output_reference}],
policy_decisions[{capability, outcome, reason_code}],
worker_exit_status, reviewer_required, completed_at,
sanitised_summary, failure_code
```

`output_reference` points to private, access-controlled evidence, not raw output returned in the public ticket API. Its retention period, redaction process, and authorised reviewers must be documented before a worker is enabled.

### 7.2 Evidence validation

The dispatcher or a dedicated validator must reject a proposed `awaiting_review` transition when any condition below is false:

- the claim epoch and lease token match the active claim;
- the recorded base SHA matches the job envelope;
- the worktree is a real Git worktree at that baseline, not a copied substitute;
- there is an actual non-empty diff or result commit associated with that worktree;
- every changed path satisfies the exact scope allowlist;
- each mandatory command ID has a result from a real process with an exit code;
- all mandatory commands exited successfully;
- no denied capability was used or bypassed;
- the worker status is not interrupted, cancelled, timed out, or unknown; and
- the public summary is sanitised and contains no private engineering detail.

A worker may report `failed`, `blocked`, or `cancelled` with a minimal safe reason. It may never self-classify an incomplete outcome as `resolved`.

---

## 8. Independent review and no-deploy boundary

An independent reviewer is a distinct authenticated actor or service from the worker claim. The reviewer receives the diff, allowed changed-path list, evidence manifest, and policy outcomes through a private review interface. The reviewer must explicitly accept or reject the result.

The reviewer must reject if scope, evidence, tests, or policy validation is incomplete. Review acceptance changes `awaiting_review` to `resolved`; it does not merge the branch or release software.

The following actions remain impossible from this contract, the adapter, and the worker permission profile:

- merge a branch;
- push to a remote;
- deploy or alter infrastructure;
- read production environment files or secrets;
- access production databases;
- send messages, make bookings, charge/refund, or invoke any external business action; and
- approve the worker's own work.

Any future merge or deployment process requires a separately approved change-control design and an explicit owner decision after review. It is not an extension of ticket completion.

---

## 9. Interruption, cancellation, and reconciliation

### 9.1 Cancellation

On a valid cancellation, the dispatcher atomically records `cancel_requested`, revokes future approvals for that job, and sends `cancel_job` to the adapter. The adapter interrupts the active turn, prevents result publication from the cancelled claim, and acknowledges the cancellation. The dispatcher then records `cancelled` with a safe reason category.

If acknowledgement is lost, the dispatcher must preserve `cancel_requested`, expire the claim, and reconcile before any retry. A late result from the cancelled claim is rejected by claim epoch and terminal-state checks.

### 9.2 Worker interruption and lost delivery

If the process exits, the adapter cannot be reached, or heartbeats cease:

1. do not mark the ticket successful;
2. let the lease expire or record an authenticated interruption signal;
3. inspect private structural job/worktree state without exposing it to the ticket user;
4. record `claim_expired` or `failed` with an honest reason category;
5. reconcile whether a result was already accepted for the job and claim epoch; and
6. retry only through a new transaction and claim epoch, subject to the idempotency key and owner policy.

If a worktree change exists after interruption but lacks verified test evidence and independent review, the terminal state is `failed` or `awaiting_engineering`, never `resolved`. It must be retained or removed only under the private worker retention procedure; it must not be silently merged.

---

## 10. Acceptance-test plan

All tests must use a disposable local repository, synthetic ticket content, and a non-production worker environment. They must not use customer data, external messaging, real bookings, payments, production credentials, or a deployment target.

| ID | Scenario | Required evidence |
|---|---|---|
| CT-01 | Schema and envelope validation | Protected envelope fields supplied by a ticket/model are rejected; server-generated envelope validates. |
| CT-02 | Ticket revision binding | Changing the approved ticket content invalidates the old payload hash and blocks dispatch. |
| CT-03 | Idempotent outbox delivery | Replaying one outbox delivery yields one job and one active claim only. |
| CT-04 | Concurrent claims | Concurrent dispatcher attempts yield exactly one lease token and claim epoch. |
| CT-05 | Repository binding | Any path, branch, URL, or repository key outside the server allowlist is rejected before worktree creation. |
| CT-06 | Immutable baseline | Worktree HEAD equals the envelope full SHA; dirty primary checkout or missing SHA fails closed. |
| CT-07 | No copied fallback | Forced `git worktree add` failure records an honest failed state; no fallback directory is used. |
| CT-08 | Scope enforcement | Attempt to change an out-of-scope path is denied and cannot reach review. |
| CT-09 | Tool-policy denial | Secret read, remote push, merge, deployment, install, unrestricted network action, and unapproved command are denied and logged structurally. |
| CT-10 | Genuine change | A synthetic maintenance task produces a real isolated-worktree diff or commit with allowed paths. |
| CT-11 | Genuine tests | Required commands run as real processes; recorded command IDs, exit codes, and durations match observed results. |
| CT-12 | Failing verification | A deliberately failing test results in `failed` or `awaiting_review`, never `resolved`. |
| CT-13 | Stale result rejection | Result bearing an expired lease token or prior claim epoch is rejected without changing ticket status. |
| CT-14 | Worker interruption | Kill the worker; lease expires or interruption is recorded; no success event is published. |
| CT-15 | Lost result delivery | Drop the first response; reconciliation discovers one job/result and does not start duplicate work. |
| CT-16 | Cancellation race | Cancel during execution; a late success result cannot overwrite `cancelled`. |
| CT-17 | Review separation | Worker actor cannot approve evidence; distinct reviewer acceptance is necessary for `resolved`. |
| CT-18 | Public/private separation | Public ticket API exposes only sanitised lifecycle events; it never returns prompt, output, path, credential, or raw evidence. |
| CT-19 | No-deploy proof | Test policy attempts to merge, push, deploy, or use external business actions; each is denied. |
| CT-20 | End-to-end synthetic journey | Approved synthetic ticket completes through one job, one worktree, actual tests, review acceptance, and a sanitised status update. |

For CT-20, a successful result is valid only when the evidence manifest, independent review record, and public sanitised event can be reproduced from a clean checkout and the disposable worker environment.

---

## 11. Release gates and ownership decisions

Before enabling even owner-approved dispatch, the owner must approve:

1. the specific worker control plane and its immutable source baseline;
2. the dispatcher and independent-review owners;
3. the approved repository key, scope allowlists, test-command identifiers, and maximum job duration;
4. the service-authentication, rotation, revocation, retention, and private-evidence access procedures;
5. the cancellation and reconciliation runbook;
6. evidence that CT-01 through CT-20 passed in the required isolated environment; and
7. the initial dispatch rule. The recommended initial rule is one owner-approved, development-only ticket at a time.

Failure of any gate keeps tickets in `awaiting_engineering`. This document does not permit automatic dispatch, production use, merging, deployment, or any external action.

---

## 12. Implementation boundary for a future work package

A future implementation work package may add private job persistence, a transactional outbox, a dispatcher, and an adapter only after this specification is approved. Its changed-file allowlist, migration design, authentication design, threat model, worker policy, synthetic test fixtures, and rollback procedure must be reviewed before code is written.

The implementation must be independently reviewed against this document and [CODING_WORKER_READINESS_ASSESSMENT.md](CODING_WORKER_READINESS_ASSESSMENT.md). A mocked or no-op success response, an unverified diff, a self-approved result, or a deployment-capable worker is a release blocker.
