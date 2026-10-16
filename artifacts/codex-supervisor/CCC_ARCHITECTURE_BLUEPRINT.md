# Codex Control Centre Development Supervisor Architecture

**Artifact:** `CCC_ARCHITECTURE_BLUEPRINT.md`  
**Programme:** `ccc_arch_blueprint`  
**Status:** implementation-ready architecture; no application code changed  
**Target:** the integrated `F:\Projects\fastapi_bookings\codex-control-centre` mounted by FastAPI Bookings and surfaced at `/admin/coding-cockpit`  
**Explicit exclusion:** the separate `F:\Projects\codex-control-centre` repository is not a source, target, dependency, or migration input.

## 1. Outcome and architectural position

The integrated Codex Control Centre becomes a durable **Development Supervisor** for FastAPI Bookings. It preserves project intent outside any one model context window, prepares versioned work briefs, delegates bounded work to Codex agents, records verifiable evidence, launches a fresh independent audit, and accepts or rejects work against the original brief.

The supervisor is not a second booking source of truth. It remains an engineering-control subsystem. Booking, tenant, user, provider, availability, SMS, and customer data remain owned by FastAPI Bookings.

The target loop is:

```text
observe -> propose -> approve brief -> assign -> dispatch author run
        -> checkpoint -> collect evidence -> dispatch fresh audit run
        -> accept | reject | rebrief | human decision -> checkpoint
```

The resident agent may implement work when policy permits. The non-negotiable separation is:

> No implementation run may be its own sole auditor or final accepter.

This replaces the historical blanket rule that the resident can never code. Context preservation comes from immutable briefs, selective project memory, evidence, and checkpoints—not from keeping a single conversation alive.

## 2. Current-state facts and gaps

### Existing assets to retain

- FastAPI Bookings mounts the integrated control-centre routers under `/api/admin/codex/*` in `app/main.py` and protects most routes with `get_current_admin`.
- `Project`, `Thread`, `Turn`, `Item`, `ToolApproval`, and `SubAgent` are persisted in the control centre's isolated SQLite `codex.db`.
- A turn creates or reuses an isolated Git worktree, starts a dedicated Codex app-server worker, and streams normalized events.
- One-time SSE tickets, worktree path validation, approval handling, bounded skills-RAG context, model selection, and worker interruption already exist.
- The Coding Cockpit already consumes same-origin `/api/admin/codex` APIs and presents workbench, issues, diagnostics, skills, plugins, approvals, diffs, tests, and terminal views.
- The resident agent already audits, proposes remediation, and reports system status.

### Gaps this design closes

1. `Project` and its descendants have no tenant or user ownership fields; admin authentication alone does not scope rows.
2. Resident issues and remediation plans live in process memory and disappear on restart.
3. Worker-to-Codex-thread mappings and the 100-event SSE replay buffer live in process memory.
4. `SubAgent` records activity but is not linked to a brief, assignment, run, worktree, evidence set, or acceptance decision.
5. A turn prompt is the only durable task statement; it is not a versioned, approved engineering contract.
6. There is no immutable context checkpoint from which a supervisor can resume after restart or model compaction.
7. There is no evidence ledger tying claims to a commit, command, exit code, environment, and artifact digest.
8. There is no enforced fresh-context independent audit or criterion-level verdict.
9. The resident remediation executor truthfully refuses execution, but it is not wired to the working Codex worker/worktree path.
10. The resident SSE route does not currently apply `get_current_admin`; the supervisor must not reuse that unscoped stream.
11. SSE ticket issuance verifies authentication but not persisted project/thread ownership, and the stream still permits query-token fallback.
12. `init_db()` calls `create_all`; production schema evolution must instead be Alembic-owned and startup must fail readiness on a revision mismatch.

## 3. Bounded context architecture

### 3.1 Durable project brain

The project brain is relational and selective. It contains:

- the programme objective and current state;
- approved brief revisions;
- architecture decisions, invariants, risks, blockers, and known limitations;
- work-package dependencies and ownership;
- the most recent immutable context checkpoint;
- execution and audit lineage;
- evidence and acceptance decisions.

It deliberately does **not** store entire agent conversations as semantic memory. Existing `Turn` and `Item` rows remain the detailed execution transcript. The supervisor context assembler retrieves only approved, current, relevant records.

### 3.2 Context pack built for each run

Each dispatched run receives a generated context pack with a hard size budget and these sections in order:

1. repository and tenant scope;
2. approved brief revision and acceptance criteria;
3. current baseline/submission commit;
4. active invariants and decisions selected by tags and affected paths;
5. current checkpoint summary;
6. allowed files, prohibited actions, and required verification commands;
7. unresolved risks/blockers;
8. run role: `author`, `reviewer`, or `supervisor`;
9. tool and iteration budgets.

Default budget: 24,000 characters, with the brief and safety boundaries never truncated. Lower-priority memory is ranked and omitted with an explicit `context_omissions` list. Raw prompts, customer data, secrets, `.env` content, booking notes, SMS bodies, and authorization material are prohibited.

### 3.3 Checkpoint triggers

Create a checkpoint after:

- brief approval;
- assignment dispatch;
- author terminal state;
- evidence submission;
- audit terminal state;
- human decision;
- manual pause;
- detected context compaction notification;
- graceful shutdown when active programmes exist.

Checkpoints are immutable. A programme points to the newest valid checkpoint. Recovery rehydrates from that checkpoint plus subsequent durable events.

## 4. Policy modes

`policy_mode` is stored on the supervisor programme and snapshotted onto every work package and assignment.

| Mode | Resident behavior | Author | Required audit |
|---|---|---|---|
| `delegation_first` | Diagnoses, briefs, dispatches, supervises, and decides | Separate author agent by default | Separate fresh reviewer agent |
| `hybrid` | May implement bounded low/medium-risk work | Resident or delegated agent | Separate fresh reviewer; never the author run/thread |
| `audit_only` | Imports externally completed work and audits it | External agent/person | Resident-launched fresh reviewer plus human acceptance when high risk |
| `observe_only` | Read-only analysis and proposals | None | None until a brief is approved |

### Hybrid coding guard

Resident implementation is allowed only when all are true:

- work package risk is `low` or `medium`;
- no payment, refund, live SMS, production deployment, credential, destructive migration, or real customer action is involved;
- a changed-file allowlist is approved;
- the resident author run has a bounded worktree, tool set, iteration limit, token budget, timeout, and cost ceiling;
- an independent reviewer assignment is created before author dispatch;
- final acceptance is performed by a different run and, for high-impact changes, a human.

`high` and `critical` work always use delegation-first or audit-only and require human acceptance after independent review.

## 5. Identity and ownership model

The control-centre database remains isolated from the booking database. Therefore `tenant_id` and `owner_user_id` are **external identity references**, not cross-database foreign keys. Each request obtains the authenticated FastAPI Bookings `User` through `get_current_admin`, then passes this immutable scope to the supervisor repository layer:

```python
ActorScope(
    tenant_id=current_admin.tenant_id,
    user_id=current_admin.id,
    role=current_admin.role,
)
```

Every query begins with `tenant_id = :actor_tenant_id`. Mutations additionally require either `owner_user_id = :actor_user_id` or an explicit role/collaborator grant. Resource existence is not disclosed across tenants; cross-tenant access returns `404`.

### Roles inside a programme

- `owner`: create/archive programme, change policy, make final human decisions;
- `supervisor`: approve briefs, dispatch/rebrief, manage assignments;
- `author`: execute assigned brief and submit evidence;
- `reviewer`: read brief/submission and record audit findings;
- `observer`: read non-sensitive programme status and evidence summaries.

FastAPI role establishes entry eligibility; `programme_memberships` establishes resource-level authority. The creator is inserted as `owner` transactionally.

## 6. Exact data model

All timestamps are UTC `DateTime(timezone=True)`. IDs are opaque UUID strings (`spg_`, `wp_`, `br_`, `asn_`, `run_`, `cp_`, `evd_`, `aud_`, `acr_`, `mem_`, `sev_`). JSON columns contain schema-versioned, bounded structural data only. Every mutable aggregate has integer `version` for optimistic concurrency.

### 6.1 Existing-table extensions

#### `projects`

Add:

- `tenant_id INTEGER NULL` during adoption, later `NOT NULL`
- `owner_user_id INTEGER NULL` during adoption, later `NOT NULL`
- `scope_state VARCHAR(16) NOT NULL DEFAULT 'unclaimed'` — `unclaimed|claimed|quarantined`
- `version INTEGER NOT NULL DEFAULT 1`

Constraints/indexes:

- unique `(tenant_id, id)`
- index `(tenant_id, owner_user_id, updated_at)`
- check `scope_state IN (...)`

Legacy rows remain invisible until explicitly claimed by a current tenant owner. Repository paths are never used to infer ownership.

#### `threads`

Add:

- `tenant_id INTEGER NULL`, later `NOT NULL`
- `owner_user_id INTEGER NULL`, later `NOT NULL`
- `codex_thread_id VARCHAR NULL`
- `worktree_name VARCHAR NULL`
- `worktree_path TEXT NULL`
- `branch_name VARCHAR NULL`
- `last_event_sequence INTEGER NOT NULL DEFAULT 0`
- `version INTEGER NOT NULL DEFAULT 1`
- `updated_at DATETIME NOT NULL`

Constraints/indexes:

- foreign key `(project_id)` remains;
- unique `(tenant_id, codex_thread_id)` when non-null;
- index `(tenant_id, project_id, status)`;
- check thread tenant equals project tenant in repository/service logic and migration audit.

#### `turns`, `tool_approvals`, `subagents`

Add `tenant_id`, `owner_user_id`, `updated_at`, and `version`. Add `agent_run_id` to `turns` and `subagents`; add `expires_at`, `decided_by_user_id`, and immutable terminal-decision fields to `tool_approvals`. All access remains joined/scoped through the owning thread even after denormalized tenant columns are added.

### 6.2 New supervisor tables

#### `supervisor_programmes`

| Column | Type | Rules |
|---|---|---|
| `id` | string PK | opaque ID |
| `tenant_id` | integer | required, indexed |
| `owner_user_id` | integer | required |
| `project_id` | string FK projects | required, restrict delete |
| `name` | string(200) | required |
| `objective` | text | required, bounded 20k |
| `policy_mode` | string(24) | required enum |
| `status` | string(24) | required enum |
| `baseline_commit` | string(64) | required before activation |
| `current_checkpoint_id` | string nullable | application-managed pointer |
| `context_budget_chars` | integer | default 24000, 8000..64000 |
| `max_parallel_runs` | integer | default 2, 1..8 |
| `version` | integer | optimistic concurrency |
| `created_at/updated_at/archived_at` | datetime | audit fields |

Unique `(tenant_id, project_id, name)` for active/non-archived programmes.

#### `programme_memberships`

- `programme_id` FK cascade
- `tenant_id`
- `user_id`
- `role` enum
- `created_by_user_id`, `created_at`
- primary key `(programme_id, user_id)`
- index `(tenant_id, user_id, role)`

#### `project_memory_items`

- `id`, `programme_id`, `tenant_id`
- `kind`: `decision|invariant|risk|blocker|known_issue|assumption|limitation`
- `title`, `summary`, `details_json`
- `tags_json`, `affected_paths_json`
- `status`: `active|resolved|superseded`
- `supersedes_id` nullable self-FK
- `source_type`, `source_id`
- `created_by_user_id`, `created_at`, `resolved_at`
- `content_hash` SHA-256

Items are immutable except status/resolution. Supersession creates a new item.

#### `work_packages`

- `id`, `programme_id`, `tenant_id`, `owner_user_id`
- `key` human-stable within programme, e.g. `CCC-SUP-001`
- `title`, `outcome`, `priority`
- `risk_level`: `low|medium|high|critical`
- `policy_mode_snapshot`
- `status`
- `approved_brief_revision_id` nullable
- `baseline_commit`, `submitted_commit` nullable
- `changed_file_allowlist_json`
- `prohibited_actions_json`
- `required_checks_json`
- `assigned_role` nullable
- `blocked_reason` nullable
- `version`, `created_at`, `updated_at`, `accepted_at`

Unique `(programme_id, key)`, index `(tenant_id, programme_id, status, priority)`.

#### `work_package_dependencies`

- `work_package_id`, `depends_on_work_package_id`
- `dependency_type`: `blocks|informs`
- composite primary key
- check IDs differ
- cycle detection in service before insert

#### `brief_revisions`

- `id`, `work_package_id`, `tenant_id`
- `revision_number` integer
- `status`: `draft|approved|superseded|withdrawn`
- `problem_statement`, `intended_outcome`
- `in_scope_json`, `out_of_scope_json`
- `architecture_invariants_json`
- `security_boundaries_json`
- `acceptance_criteria_json` — each criterion has stable ID, statement, evidence kind
- `verification_commands_json`
- `changed_file_allowlist_json`
- `prohibited_actions_json`
- `delivery_contract_json`
- `context_manifest_json` — memory/checkpoint IDs and content hashes
- `created_by_user_id`, `approved_by_user_id`, `created_at`, `approved_at`
- `content_hash`

Unique `(work_package_id, revision_number)`. Approved revisions are immutable. Approving one revision supersedes the previous approved revision in the same transaction.

#### `agent_assignments`

- `id`, `work_package_id`, `tenant_id`
- `brief_revision_id`
- `role`: `author|reviewer|supervisor`
- `agent_kind`: `resident_codex|delegated_codex|external`
- `status`
- `thread_id` FK threads nullable until dispatch
- `review_of_assignment_id` nullable self-FK
- `model`, `reasoning_effort`
- `tool_profile` — named allowlisted profile, not arbitrary tool JSON
- `max_iterations`, `max_tokens`, `timeout_seconds`, `cost_limit_microunits`
- `assigned_by_user_id`, `assigned_at`, `expires_at`
- `version`

Invariant: reviewer assignment must reference an author assignment, must use a different `thread_id`, and cannot start until the author has a submitted commit and evidence set.

#### `agent_runs`

- `id`, `assignment_id`, `tenant_id`
- `attempt_number`
- `status`
- `thread_id` FK threads
- `turn_id` FK turns nullable until created
- `parent_run_id` nullable for retry/resume lineage
- `codex_thread_id` nullable persisted mapping
- `worktree_name`, `worktree_path`, `branch_name`
- `baseline_commit`, `result_commit` nullable
- `context_checkpoint_id`, `context_pack_hash`
- `started_at`, `heartbeat_at`, `completed_at`
- `exit_reason`, `error_code`, `error_summary`
- `token_input`, `token_output`, `cost_microunits`, `iteration_count`
- `version`

Unique `(assignment_id, attempt_number)`. Only one non-terminal run per assignment. Only one active writer assignment may own an allowlisted path within one programme; path leases are acquired transactionally.

#### `context_checkpoints`

- `id`, `programme_id`, `tenant_id`
- `sequence` monotonically increasing per programme
- `reason`
- `baseline_commit`, `head_commit` nullable
- `summary`
- `state_json` — active package/assignment/run IDs and statuses
- `decision_ids_json`, `risk_ids_json`, `evidence_ids_json`
- `open_questions_json`, `next_actions_json`
- `created_by_type`: `system|user|run`
- `created_by_id`, `created_at`
- `content_hash`, `schema_version`

Unique `(programme_id, sequence)`. Rows are append-only.

#### `evidence_artifacts`

- `id`, `work_package_id`, `tenant_id`
- `agent_run_id`
- `criterion_id` nullable
- `kind`: `command|test_report|runtime_journey|diff|commit|screenshot|trace|document|external_attestation`
- `status`: `captured|verified|rejected|superseded`
- `command_text` nullable and redacted
- `exit_code` nullable
- `environment_json` allowlisted structural fields only
- `summary`
- `artifact_uri` repository-relative or managed artifact reference; never an arbitrary remote URL
- `content_sha256`
- `byte_size`
- `captured_at`, `verified_at`
- `verified_by_run_id` nullable

Raw output is stored as a bounded artifact file under an application-managed evidence directory; the database stores metadata and digest. Evidence is accepted only if the recorded commit matches the submitted commit.

#### `audit_reviews`

- `id`, `work_package_id`, `tenant_id`
- `author_assignment_id`, `reviewer_assignment_id`, `reviewer_run_id`
- `brief_revision_id`, `submitted_commit`
- `status`: `requested|running|needs_info|accepted|rejected|rebrief_required|human_decision_required|cancelled`
- `overall_summary`, `residual_risk`
- `decided_by_user_id` nullable
- `started_at`, `completed_at`
- `version`

Constraints: author and reviewer assignments/runs/threads differ; reviewed brief and commit are immutable after start.

#### `audit_criteria`

- `id`, `audit_review_id`, `tenant_id`
- `criterion_key` from approved brief
- `verdict`: `verified|failed|not_run|not_applicable|needs_human`
- `evidence_ids_json`
- `finding`, `residual_risk`
- unique `(audit_review_id, criterion_key)`

#### `supervisor_events`

- `id`, `programme_id`, `tenant_id`
- `thread_id` nullable, `work_package_id` nullable, `agent_run_id` nullable
- `sequence` integer monotonically increasing per programme
- `event_type`, `payload_json`, `occurred_at`
- `correlation_id`, `causation_id` nullable
- `schema_version`

Unique `(programme_id, sequence)`, index `(tenant_id, programme_id, sequence)`. Payload schemas are allowlisted and bounded. This table becomes the durable SSE replay source for supervisor events; the in-memory broker remains a fan-out cache.

## 7. State machines and transition authority

All transitions are compare-and-swap updates using `version` and expected current status. Invalid or repeated terminal transitions return `409 invalid_state`; idempotent stop/cancel returns the existing state.

### 7.1 Programme

```text
draft -> active -> paused -> active
draft|active|paused -> cancelled
active -> completed
completed|cancelled -> archived
```

Only owners change policy mode or archive. Activation requires a claimed project, baseline commit, and at least one owner membership.

### 7.2 Work package

```text
proposed -> briefing -> ready -> assigned -> in_progress
in_progress -> awaiting_evidence -> audit_pending -> auditing
auditing -> accepted
auditing -> rejected -> briefing
auditing -> rebrief_required -> briefing
auditing -> human_decision_required -> accepted|rejected|briefing
ready|assigned|in_progress|awaiting_evidence|audit_pending|auditing -> blocked
blocked -> prior_nonterminal_state
proposed|briefing|ready|assigned|blocked -> cancelled
```

`ready` requires an approved brief. `accepted` requires a complete audit matrix, verified required evidence, a distinct reviewer, and human acceptance for high/critical risk.

### 7.3 Brief revision

```text
draft -> approved -> superseded
draft -> withdrawn
```

Approved/superseded/withdrawn revisions are immutable. Rebrief creates revision `n+1`.

### 7.4 Assignment

```text
queued -> dispatching -> running -> finishing -> completed
running -> awaiting_input -> running
queued|dispatching|running|awaiting_input|finishing -> cancelling -> cancelled
dispatching|running|awaiting_input|finishing -> failed|timed_out
queued -> expired
```

An assignment is a durable intent. A retry creates a new `agent_run`, not a reset of the prior run.

### 7.5 Agent run

```text
queued -> starting -> running -> succeeded
running -> awaiting_approval -> running
running|awaiting_approval -> stopping -> interrupted
queued|starting -> cancelled
starting|running|awaiting_approval|stopping -> failed|timed_out
failed|interrupted|timed_out -> queued  (new child run only)
```

Terminal states never change. Late Codex events are recorded with `late_event=true` but cannot mutate a terminal run.

### 7.6 Audit review

```text
requested -> running
running -> needs_info -> running
running -> accepted|rejected|rebrief_required|human_decision_required
requested|running|needs_info -> cancelled
human_decision_required -> accepted|rejected|rebrief_required
```

Machine review may recommend; the acceptance service validates all invariants before committing a terminal decision.

## 8. Service boundaries and execution flow

### 8.1 New backend services

- `actor_scope.py`: derives and validates tenant/user scope passed from FastAPI Bookings.
- `supervisor_repository.py`: the only persistence entry point for supervisor aggregates; every method requires `ActorScope`.
- `brief_service.py`: revisioning, validation, approval, and context manifest generation.
- `context_service.py`: selective memory retrieval, deterministic context packs, checkpoint creation/recovery.
- `assignment_service.py`: policy/risk enforcement, role selection, limits, and path leases.
- `run_orchestrator.py`: creates thread/turn/worktree records and calls existing worker manager; no duplicate worker implementation.
- `evidence_service.py`: redaction, hashing, bounded artifact storage, commit binding, and evidence verification.
- `audit_service.py`: creates fresh reviewer assignment/worktree, builds criterion matrix, validates independence, and applies verdicts.
- `supervisor_event_service.py`: transactionally appends persistent events and publishes committed events through the existing broker.
- `legacy_adoption_service.py`: explicit claim/quarantine workflow for pre-ownership records.

### 8.2 Transactional dispatch sequence

1. Lock work package and validate `ready`, dependencies, approved brief, policy, and path conflicts.
2. Create assignment and run in `queued`; snapshot policy and context checkpoint.
3. Commit and emit `assignment.queued` with idempotency key.
4. Async orchestrator moves run to `starting`, creates a scoped `Thread`, persists worktree/branch identifiers, and invokes existing `ensure_thread_worktree`.
5. Build the bounded context pack and persist its hash; do not persist secrets or hidden model reasoning.
6. Create existing `Turn` linked by `agent_run_id`; dispatch through existing `worker_manager.get_worker_for_thread` and `turn/start`.
7. Normalize Codex notifications to both existing thread events and durable supervisor events.
8. Persist heartbeat, resource counters, final status, result commit, and a checkpoint.
9. On success, move package to `awaiting_evidence`; on failure, preserve the failed run and expose retry/rebrief choices.

No endpoint reports a running assignment before the queued/run rows commit. Dispatch failure becomes an explicit failed run; it never creates a synthetic successful turn.

### 8.3 Author evidence and audit sequence

1. Author run records changed files and result commit.
2. Required commands execute in the author worktree; command, exit code, digest, and bounded artifact are recorded.
3. Evidence service rejects artifacts whose commit, tenant, package, or run lineage does not match.
4. When the evidence manifest is complete, package moves to `audit_pending`.
5. Audit service creates a new reviewer assignment, new thread, and separate clean worktree pinned to `submitted_commit` (or a read-only diff workspace).
6. Reviewer receives the approved brief, baseline/submitted commits, complete diff, evidence metadata, and relevant decisions—never the author's hidden reasoning or full transcript.
7. Reviewer runs fresh required checks and produces one `audit_criteria` row per acceptance criterion.
8. Acceptance service validates reviewer independence, evidence completeness, commit consistency, risk policy, and criterion verdicts.
9. It records `accepted`, `rejected`, `rebrief_required`, or `human_decision_required`, then creates a checkpoint.

### 8.4 Resident-agent integration

The resident agent becomes a producer/consumer of the supervisor services:

- detected issues create or update `project_memory_items(kind='known_issue')`;
- a remediation proposal creates a `work_package` plus draft `brief_revision`;
- `execute-fix` is replaced by a supervisor dispatch request after brief approval;
- resident status is computed from durable programme/package/run/audit state;
- the existing in-memory `_active_issues` and `_plans` are removed after data migration;
- resident audits may suggest work but cannot mark implementation accepted;
- resident events are relayed through scoped supervisor events, not the unprotected resident SSE route.

The Coding Cockpit remains the single UI. No parallel application or runtime bridge is introduced.

## 9. HTTP API contract

All routes are under `/api/admin/codex/supervisor`, require `get_current_admin`, derive `ActorScope` server-side, return JSON, and never accept tenant/user IDs from request bodies as authority. Mutations require `Idempotency-Key`; updates require `If-Match: <version>`.

### 9.1 Response and error shape

Success:

```json
{"data": {}, "meta": {"request_id": "...", "version": 3}}
```

Error:

```json
{
  "error": {
    "code": "invalid_state",
    "message": "Work package must be ready before dispatch.",
    "request_id": "...",
    "details": {"resource_id": "wp_...", "expected": ["ready"], "actual": "briefing"}
  }
}
```

Allowed codes: `authentication_required`, `forbidden`, `not_found`, `conflict`, `invalid_state`, `validation_failed`, `rate_limited`, `dependency_unavailable`, `operation_timeout`, `operation_cancelled`, `evidence_invalid`, `review_independence_required`, `internal_error`.

### 9.2 Programme and memory endpoints

| Method/path | Contract |
|---|---|
| `POST /programmes` | Create draft programme for a claimed project; body `project_id,name,objective,policy_mode,context_budget_chars,max_parallel_runs` |
| `GET /programmes` | Tenant-scoped paginated list; filters `status,project_id` |
| `GET /programmes/{id}` | Programme summary, current checkpoint, counts, capabilities |
| `PATCH /programmes/{id}` | Update mutable draft/policy fields with `If-Match` |
| `POST /programmes/{id}/transitions` | Body `action=activate|pause|resume|complete|cancel|archive`, optional reason |
| `GET /programmes/{id}/memory` | Filtered current memory items |
| `POST /programmes/{id}/memory` | Create a typed memory item |
| `POST /memory/{id}/supersede` | Create replacement item; original becomes superseded |
| `GET /programmes/{id}/checkpoints` | Cursor-paginated immutable checkpoints |
| `POST /programmes/{id}/checkpoints` | Manual checkpoint; server derives authoritative state |
| `POST /programmes/{id}/resume` | Rehydrate and return next-actions plan from latest checkpoint |

### 9.3 Work package and brief endpoints

| Method/path | Contract |
|---|---|
| `POST /programmes/{id}/work-packages` | Create proposed package with stable key, outcome, priority, risk |
| `GET /programmes/{id}/work-packages` | Paginated/filterable mission board |
| `GET /work-packages/{id}` | Package, dependencies, approved brief, assignments, evidence/audit summary |
| `PATCH /work-packages/{id}` | Edit only fields permitted in current state |
| `POST /work-packages/{id}/dependencies` | Add `blocks|informs` dependency after cycle check |
| `POST /work-packages/{id}/briefs` | Create next draft revision from explicit fields or prior revision |
| `GET /work-packages/{id}/briefs` | Revision history and hashes |
| `POST /briefs/{id}/approve` | Validate completeness, approve immutably, make package ready |
| `POST /briefs/{id}/withdraw` | Withdraw draft only |
| `POST /work-packages/{id}/transitions` | Explicit block/unblock/cancel/rebrief actions |

Brief approval rejects missing allowlist, acceptance criteria, verification commands, security boundaries, or delivery contract.

### 9.4 Assignment and run endpoints

| Method/path | Contract |
|---|---|
| `POST /work-packages/{id}/assignments` | Create author/reviewer assignment; server validates policy and independence |
| `POST /assignments/{id}/dispatch` | Queue a real run; returns `202` with run/thread IDs |
| `GET /assignments/{id}` | Assignment and attempt lineage |
| `GET /runs/{id}` | Authoritative run state, limits, worktree identifiers, evidence summary |
| `POST /runs/{id}/steer` | Forward bounded instruction to active underlying turn and record event |
| `POST /runs/{id}/stop` | Idempotent stop mapped to existing turn interrupt |
| `POST /runs/{id}/retry` | New child run after failed/interrupted/timed-out state |
| `POST /external-runs/import` | Import external result manifest; never marks verified or accepted |

The existing `/codex/threads`, `/turns`, `/worktrees`, and governance APIs remain available but are updated to enforce actor scope. Supervisor-run mutation should occur through supervisor endpoints so state-machine invariants cannot be bypassed.

### 9.5 Evidence and audit endpoints

| Method/path | Contract |
|---|---|
| `POST /runs/{id}/evidence` | Register evidence metadata/artifact; verifies commit and digest |
| `GET /work-packages/{id}/evidence` | Paginated, redacted ledger |
| `POST /evidence/{id}/verify` | Reviewer/system verification, never author self-verification |
| `POST /work-packages/{id}/audit` | Create fresh reviewer assignment/review and queue it |
| `GET /audits/{id}` | Review plus criterion matrix and residual risks |
| `POST /audits/{id}/criteria/{key}` | Reviewer records verdict and evidence IDs |
| `POST /audits/{id}/submit` | Validate complete matrix and propose terminal outcome |
| `POST /audits/{id}/human-decision` | Owner accepts/rejects/rebriefs when required |

### 9.6 SSE contract

- `POST /programmes/{id}/events/ticket` mints a 60-second, one-use ticket bound to tenant, user, programme, and optional thread.
- `GET /programmes/{id}/events?ticket=...&after_sequence=N` streams durable events.
- Ticket mint verifies programme membership; ticket consume verifies the exact same scope.
- Query bearer-token fallback is removed from the integrated supervisor stream. If ticket mint fails, the browser displays authentication failure and does not leak a token into a URL.
- Replay reads `supervisor_events WHERE sequence > after_sequence`; in-memory fan-out only accelerates live delivery.
- Envelope schema:

```json
{
  "id": "sev_...",
  "schema_version": "2.0",
  "programme_id": "spg_...",
  "project_id": "proj_...",
  "thread_id": "...",
  "work_package_id": "wp_...",
  "agent_run_id": "run_...",
  "sequence": 42,
  "type": "run.completed",
  "occurred_at": "RFC3339",
  "correlation_id": "...",
  "payload": {}
}
```

Payloads contain IDs, status, progress, bounded summaries, and safe metrics only. They exclude prompts, model responses, command output, diffs, credentials, PII, and unrestricted paths.

## 10. Migration sequence

Migrations live in `codex-control-centre/alembic/versions`; `codex.db` remains isolated. Each migration has upgrade/downgrade tests against an empty database and a copy of the legacy `001` schema.

### `002_identity_scope_and_runtime_lineage`

- Add nullable `tenant_id`/`owner_user_id`, `scope_state`, and `version` to existing ownership roots.
- Add denormalized ownership and timestamps to thread descendants.
- Add persisted Codex thread/worktree/branch mappings and `agent_run_id` linkage.
- Add indexes but keep legacy rows `unclaimed` and invisible.
- Add explicit project adoption service/API; no path-based auto-claim.

### `003_supervisor_brain_and_briefs`

- Create `supervisor_programmes`, `programme_memberships`, `project_memory_items`, `work_packages`, `work_package_dependencies`, and `brief_revisions`.
- Add enum checks, uniqueness, hash fields, optimistic versions, and cascade/restrict semantics.

### `004_assignments_runs_evidence_audits`

- Create `agent_assignments`, `agent_runs`, `context_checkpoints`, `evidence_artifacts`, `audit_reviews`, and `audit_criteria`.
- Add run/turn/subagent lineage foreign keys using SQLite batch operations.
- Add active-run uniqueness using a normalized `active_slot` column or transactionally enforced partial unique index supported by the deployed SQLite version.

### `005_durable_supervisor_events_and_idempotency`

- Create `supervisor_events` and `idempotency_records`.
- Initialize per-programme sequence counters transactionally.
- Backfill safe state-transition events from supervisor tables only; do not copy raw prompt/item content.

### `006_claimed_scope_enforcement`

- Precondition: every retained project is explicitly claimed; otherwise migration stops with IDs only and remediation instructions.
- Quarantined legacy projects are exported/archived or deleted only with explicit owner action.
- Rebuild SQLite tables to make required ownership columns non-null.
- Add final tenant consistency checks and indexes.

### Startup/readiness change

- Remove `Base.metadata.create_all()` as the production migration mechanism.
- Startup may initialize a disposable test database only under an explicit test setting.
- Readiness checks Alembic head and reports `database_migration_required` without attempting an implicit upgrade.
- Before any upgrade, create a recoverable copy of `codex.db`; do not copy `-wal`/`-shm` while writers are active—checkpoint/close first.

## 11. Repository file plan and allowlists

### Current architecture task allowlist

The only file changed by this task is:

- `artifacts/codex-supervisor/CCC_ARCHITECTURE_BLUEPRINT.md`

### Phase 1 implementation allowlist — identity and persistence foundation

- `codex-control-centre/backend/models/codex.py`
- `codex-control-centre/backend/database.py`
- `codex-control-centre/backend/main.py`
- `codex-control-centre/backend/services/actor_scope.py` (new)
- `codex-control-centre/backend/services/legacy_adoption_service.py` (new)
- `codex-control-centre/backend/routers/projects.py`
- `codex-control-centre/backend/routers/threads.py`
- `codex-control-centre/backend/routers/events.py`
- `codex-control-centre/backend/services/sse_tickets.py`
- `codex-control-centre/alembic/versions/002_identity_scope_and_runtime_lineage.py` (new)
- focused tests under `codex-control-centre/tests/`
- `codex-control-centre/README.md`

### Phase 2 allowlist — project brain and briefs

- model and migration files for `003`
- `backend/services/supervisor_repository.py` (new)
- `backend/services/brief_service.py` (new)
- `backend/services/context_service.py` (new)
- `backend/routers/supervisor.py` (new)
- `backend/main.py`, `app/main.py` only for router mounting/dependency injection
- focused tests and both relevant READMEs

### Phase 3 allowlist — assignments, runs, and evidence

- model and migration files for `004`
- `backend/services/assignment_service.py` (new)
- `backend/services/run_orchestrator.py` (new)
- `backend/services/evidence_service.py` (new)
- existing `turns.py`, `worker_manager.py`, `worktree_service.py`, and `event_service.py` only for adapters/lineage
- supervisor router, focused tests, READMEs

### Phase 4 allowlist — audit and durable events

- migration files for `005`
- `backend/services/audit_service.py` (new)
- `backend/services/supervisor_event_service.py` (new)
- supervisor/events routers, focused tests, READMEs

### Phase 5 allowlist — resident and cockpit integration

- `app/services/resident_agent/engine.py`
- `app/services/resident_agent/README.md`
- `app/api/routers/resident_agent.py`
- `frontend/src/pages/admin/coding-cockpit/**`
- focused backend/frontend tests
- `frontend/src/pages/admin/coding-cockpit/README.md`

No phase may touch unrelated booking, SMS, Business Assistant, payment, deployment, or customer-data modules. Each phase receives its own precise allowlist before work begins. Existing untracked or dirty integration material is not staged, modified, deleted, or used as an implementation source.

## 12. Runtime and package dependencies

Reuse existing dependencies:

- FastAPI dependency injection and `get_current_admin`;
- SQLAlchemy ORM/session management;
- Alembic for schema changes;
- Pydantic v2 for request/response schemas;
- existing Codex app-server JSON-RPC worker and model catalogue;
- existing worktree and boundary services;
- existing skills-RAG loopback service on port 8008, with graceful degraded discovery;
- Python `hashlib`, `json`, `pathlib`, and `secrets` for digests and tickets.

No Redis, Celery, external vector database, separate control-centre server, or standalone repository is required for the first implementation. SQLite WAL remains acceptable for a single FastAPI process; multi-process deployment is explicitly unsupported until sequence allocation, dispatch claiming, and pub/sub move to a shared database/broker.

The centralized Anti-Gravity database tracks implementation programme/task execution, but is not a runtime dependency of the Development Supervisor and never stores supervisor secrets or customer data.

## 13. UI information architecture

Add six supervisor views inside the existing Coding Cockpit, not new top-level applications:

1. **Mission Board** — programmes, work packages, dependencies, risk, policy mode, next action.
2. **Brief Builder** — structured fields, revision diff, completeness validation, approval.
3. **Agent Runs** — assignments, current limits, worktree/thread lineage, progress, stop/retry/steer.
4. **Audit Studio** — baseline/submission diff, criterion matrix, independent evidence, verdict.
5. **Evidence Ledger** — command/result metadata, digest, commit binding, verification status.
6. **Decisions & Risks** — active/superseded project memory and checkpoint recovery.

Frontend state treats server resources as authoritative. It may cache and optimistically render versioned updates, but no timer or local fixture may fabricate agent progress, evidence, or acceptance. Demo fixtures remain explicitly labelled and cannot be imported by live production paths.

## 14. Security, privacy, and operational controls

- All list/get/update/delete queries are tenant-scoped in the repository layer; router-only filtering is insufficient.
- All mutations record authenticated actor ID, correlation ID, prior status, new status, and resource version.
- Tool profiles are server-defined and capped at 5–10 relevant tools per run.
- Every run has max iterations, tokens, timeout, and cost. Circuit breakers stop repeated tool failures.
- Worktree paths are canonicalized and checked against registered boundaries; symlinks/junctions cannot escape.
- Destructive worktree cleanup remains explicit, dirty-state checked, and recoverable where practical.
- Evidence artifact paths are application-generated; clients cannot supply arbitrary filesystem paths.
- Logs and telemetry carry low-cardinality IDs/statuses only. Prompt text, response text, command output, diffs, customer data, and secrets are excluded.
- External imports are untrusted attestations until a local reviewer verifies commit and evidence.
- Production deployment, push, payment, refund, booking, cancellation, and SMS actions require separate explicit user authority and are not granted by programme policy.
- An audit run receives read-only repository access by default. If it needs to add audit artifacts, it writes only to a dedicated artifact area, not the submitted branch.
- Supervisor acceptance does not deploy or merge. Those remain separately authorized actions.

## 15. Verification strategy and acceptance criteria

The documentation index currently has no registered test command for `codex control centre`; Phase 1 must add the authoritative command to living documentation/index inputs before claiming completion.

### Backend focused gates

```powershell
python -m pytest codex-control-centre/tests/test_supervisor_identity.py -v
python -m pytest codex-control-centre/tests/test_supervisor_briefs.py -v
python -m pytest codex-control-centre/tests/test_supervisor_runs.py -v
python -m pytest codex-control-centre/tests/test_supervisor_evidence.py -v
python -m pytest codex-control-centre/tests/test_supervisor_audits.py -v
python -m pytest codex-control-centre/tests/test_supervisor_events.py -v
python -m pytest codex-control-centre/tests/test_migrations.py codex-control-centre/tests/test_security.py codex-control-centre/tests/test_worktrees.py -v
```

### Frontend and application gates when Phase 5 changes land

```powershell
cd frontend
npm run typecheck
npm test -- coding-cockpit
npm run build
cd ..
python scripts/verify_zero_console_errors.py --url http://localhost:7070 --routes /admin/coding-cockpit
python scripts/verify_living_docs.py --path codex-control-centre/README.md
python scripts/verify_living_docs.py --path frontend/src/pages/admin/coding-cockpit/README.md
```

Use the commands recorded by `python scripts/query_docs.py --test-command <module>` once the documentation index is updated; do not substitute an unbounded repository-wide suite.

### Required acceptance criteria

#### Ownership and authorization

- Two synthetic tenants can create programmes/projects with identical names and neither can list, read, mutate, stream, or infer the other's resources.
- Two users in one tenant obey programme membership roles.
- Legacy unclaimed rows are invisible until an owner explicitly claims them.
- SSE tickets are one-use, expire, and fail when programme/thread/tenant/user scope differs.
- No integrated supervisor stream accepts bearer credentials in a query parameter.

#### Durability and recovery

- Restarting the application preserves programme, brief, package, assignment, run, evidence, audit, and checkpoint state.
- An active orphan run is marked interrupted/failed according to a deterministic startup recovery rule; it is never silently resumed.
- Persisted Codex thread/worktree mappings allow a valid continuation or an explicit new-run fallback.
- SSE replay after restart returns durable events strictly after the supplied sequence without duplicates.

#### Brief and policy enforcement

- An incomplete or unapproved brief cannot dispatch.
- A file outside the approved allowlist causes the author submission to fail validation.
- Observe-only cannot dispatch; audit-only cannot create an author run; hybrid rejects high/critical resident-author assignments.
- Every dispatch has iteration/token/time/cost caps and a named tool profile.

#### Independent audit

- Author and reviewer assignment, run, thread, and worktree identities differ.
- Reviewer context excludes author hidden reasoning and includes the exact approved brief and submitted commit.
- An author cannot verify its own evidence or submit its own audit verdict.
- Acceptance fails if any required criterion lacks a verdict/evidence or if the evidence commit differs.
- High/critical work stops at `human_decision_required` until an owner decides.

#### Evidence integrity

- Command evidence records command, exit code, environment, timestamp, commit, digest, and bounded artifact reference.
- Tampered artifacts fail digest verification.
- Claimed test success with non-zero exit code cannot be verified.
- Logs/events/API responses pass privacy tests proving no configured secret, prompt, response, customer identity, SMS body, or unrestricted path is exposed.

#### Concurrency and failure behavior

- Duplicate idempotency keys return the original result and do not create duplicate runs.
- Concurrent dispatch requests produce at most one active run/assignment for the same slot.
- Conflicting changed-file leases prevent concurrent writers.
- Worker crash, timeout, malformed response, SSE disconnect, stop-vs-complete race, and application restart resolve to explicit states.
- Telemetry/event publication failure does not roll back a successfully committed state transition; an outbox/retry path republishes it.

#### UI behavior

- The Mission Board, Brief Builder, Runs, Audit Studio, Evidence Ledger, and Decisions views use live APIs only.
- Loading, empty, offline, forbidden, conflict, and partial-failure states are truthful.
- Zero console errors, uncaught page errors, and 4xx/5xx route failures pass the required browser gate.
- Core supervisor actions are keyboard operable and remain usable at 320 CSS pixels and 200% zoom.

## 16. Phased implementation tasks

Each task below is one coherent outcome, must have a dedicated author assignment, and requires independent audit before acceptance.

### Phase 0 — baseline and contract freeze

1. Record current Alembic revision, database backup procedure, API snapshot, and synthetic tenant fixtures.
2. Add ADRs for isolated control-centre database, external identity references, and single-process SQLite limitation.
3. Register authoritative targeted test commands in living documentation.
4. Produce threat model for tenant scoping, worktrees, SSE tickets, artifacts, and agent authority.

Exit: no production code behavior changes; baseline can be reproduced.

### Phase 1 — ownership and truthful transport

1. Implement `002`, actor scope, claimed/unclaimed project handling, and tenant-scoped repository queries.
2. Persist Codex-thread/worktree mappings.
3. Bind SSE tickets to actor/resource ownership and remove integrated query-token fallback.
4. Replace exception details returned as 500 messages with stable redacted error contracts.
5. Add negative isolation, adoption, restart, and ticket tests.

Exit: current threads/turns/worktrees cannot cross tenants and legacy data is safely quarantined.

### Phase 2 — durable project brain and brief builder backend

1. Implement `003` models, repositories, state transitions, memory, dependency graph, brief revisions, and checkpoints.
2. Implement deterministic context manifest/pack builder with budget and omission reporting.
3. Mount supervisor router through FastAPI Bookings with `get_current_admin` passed into every operation.
4. Add state-machine, version conflict, cycle, immutability, and restart tests.

Exit: a programme can be created, checkpointed, resumed, and produce an approved versioned brief without running code.

### Phase 3 — assignment and real run orchestration

1. Implement `004` assignment/run/evidence foundations.
2. Adapt existing Thread/Turn/SubAgent/worker/worktree services; do not build a second executor.
3. Add policy enforcement, path leases, idempotent dispatch, resource limits, heartbeat, stop, and retry lineage.
4. Wire resident approved briefs to supervisor dispatch; remove fake/generic execution paths.
5. Add real synthetic worktree/worker integration tests and explicit unavailable behavior when Codex cannot start.

Exit: an approved brief launches a real bounded Codex run and survives process restart with truthful state.

### Phase 4 — evidence ledger and independent audit

1. Complete evidence artifact storage, hashing, redaction, and commit binding.
2. Implement fresh reviewer assignment/worktree/context and criterion matrix.
3. Implement acceptance validator and high-risk human decision gate.
4. Implement durable supervisor event log/outbox and sequence replay in `005`.
5. Add tamper, self-review, stale commit, late event, concurrency, and failure-path tests.

Exit: no package can become accepted without independent, reproducible evidence.

### Phase 5 — Coding Cockpit supervisor UI

1. Add typed API/resources and server-authoritative state store.
2. Implement Mission Board and Brief Builder.
3. Implement Runs and Evidence Ledger.
4. Implement Audit Studio and Decisions/Risks.
5. Replace resident in-memory issue/plan displays with durable supervisor resources.
6. Run TypeScript, component, accessibility, build, and zero-console/network gates.

Exit: the complete observe-to-audit loop is operable from `/admin/coding-cockpit` with no mock live state.

### Phase 6 — scope enforcement and operational hardening

1. Complete legacy data adoption/quarantine and run `006` non-null enforcement.
2. Add evidence retention/cleanup policies that preserve accepted audit trails.
3. Add health/readiness for migration state, worker availability, evidence storage, and event outbox.
4. Exercise backup/restore, crash recovery, and clean-checkout setup runbooks.
5. Permit proactive read-only improvement scans that create proposals, never silent code changes.

Exit: operational recovery and retention are documented and verified; proactive mode is proposal-only.

## 17. Work-package template for implementing agents

Every implementation assignment generated from this blueprint must contain:

```markdown
## Identity
- Programme/work-package/brief revision IDs
- Role: author or reviewer
- Baseline commit and assigned worktree

## Outcome
- One coherent result

## Scope
- Exact changed-file allowlist
- Explicit out-of-scope modules and actions

## Contracts
- Data model/API/state transitions involved
- Tenant/user and privacy invariants

## Acceptance criteria
- Stable criterion IDs

## Verification
- Exact focused commands and runtime journeys
- Required evidence kinds

## Limits
- Tool profile, iterations, tokens, timeout, cost

## Delivery
- Result commit, changed files, evidence manifest, limitations
```

## 18. Definition of done

The Development Supervisor programme is complete only when:

- all persisted resources are tenant/user scoped and negative isolation tests pass;
- approved brief revisions are immutable and dispatch is impossible without one;
- resident coding is governed by the selected policy mode and risk gates;
- every run is bounded and linked to a real thread, turn, worktree, commit, and checkpoint;
- evidence is reproducible, commit-bound, hashed, redacted, and independently verified;
- authors cannot audit or accept their own work;
- restart and compaction recovery use durable checkpoints rather than conversation history;
- supervisor SSE has durable ordered replay and scoped one-use tickets;
- the Coding Cockpit presents only server-authoritative live state;
- migrations, focused tests, runtime journeys, living documentation, browser error/network gate, and independent QA audit all pass;
- verified implementation is committed and pushed according to repository rules by the implementing work package, with exact commit/evidence reported.

## 19. Known limits and explicit non-goals

- First release is single FastAPI process + SQLite WAL. Horizontal workers require a shared transactional database and broker.
- The supervisor coordinates engineering work; it does not merge, deploy, send SMS, create bookings, charge/refund, or contact customers.
- It does not ingest the entire repository or skills library into model context.
- It does not make the standalone control-centre repository a dependency.
- It does not treat Anti-Gravity, Chatwoot, SigNoz, or a model transcript as a source of truth for acceptance.
- It does not infer tenant ownership from filesystem paths or historical thread content.
- It does not claim secure/accepted/completed state from an agent summary alone.

## 20. Architecture decision summary

1. Extend the working integrated Codex primitives; do not create a second execution stack.
2. Preserve `codex.db` isolation, with explicit external tenant/user identity references and mandatory scoped repositories.
3. Preserve context through structured immutable records and bounded retrieval, not unlimited chat history.
4. Make resident coding configurable through policy modes; require independent review in every coding mode.
5. Separate author and reviewer by assignment, run, thread, worktree, and context pack.
6. Treat evidence and audit decisions as first-class durable resources.
7. Use persistent events for recovery/replay and the in-memory broker only for live fan-out.
8. Migrate legacy rows through explicit claim/quarantine, never automatic ownership inference.
9. Keep UI and resident supervision inside the existing FastAPI Bookings Coding Cockpit.
10. Fail loudly and truthfully when worker, migration, evidence, or review prerequisites are unavailable.
