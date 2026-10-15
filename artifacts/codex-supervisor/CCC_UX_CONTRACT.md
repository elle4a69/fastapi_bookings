# Codex Control Centre — Development Supervisor UX Contract

**Work package:** `ccc_ux_contract`  
**Application:** FastAPI Bookings integrated Engineering Cockpit  
**Canonical UI:** `/admin/coding-cockpit`  
**Canonical API base:** `/api/admin/codex`  
**Status:** implementation-ready product and frontend contract; no application code is changed by this document

## 1. Outcome and non-negotiable boundaries

The Engineering Cockpit becomes a durable development-supervision workspace. The resident agent may write code, but the normal workflow is delegation-first and no implementation may be accepted solely by its author.

```text
Mission -> approved brief -> author run -> evidence collection
        -> independent audit -> accept | request rework | human decision
        -> context checkpoint
```

This contract applies only to the copy integrated into FastAPI Bookings under `frontend/src/pages/admin/coding-cockpit` and the backend mounted beneath `/api/admin/codex`. The separate `F:\Projects\codex-control-centre` repository is not part of the design, implementation, or runtime path.

Hard requirements:

- FastAPI Bookings remains the authentication and tenant boundary.
- Supervisor records are durable server records. Browser state may hold filters, open panels, and an unsaved form buffer, but never an authoritative status, verdict, evidence claim, or dispatch result.
- Every mutation is acknowledged by the server before the UI presents success.
- Author and audit runs are distinct records. The API rejects an audit reviewer identity/run that authored the submitted implementation.
- A work package cannot become `accepted` unless every mandatory acceptance criterion has a verified evidence reference and an independent audit verdict exists.
- Test output, commands, diffs, prompts, and evidence summaries must be scrubbed and bounded on the server before reaching the browser. Secrets, customer data, SMS bodies, booking notes, tokens, and raw prompts are never rendered or logged.
- No payment, booking, cancellation, SMS, deployment, merge, push, or production action is introduced by this interface.
- Existing workbench, support ticket, approvals, diff review, ticketed SSE, and tool-modal behavior remains available.
- There is no frontend fallback that fabricates IDs, runs, results, or evidence when the API is unavailable.

## 2. Existing patterns to retain

The implementation should extend, rather than replace, these established cockpit patterns:

- `CodingCockpitPage.tsx` remains the route entry and query-parameter coordinator.
- `CodexWorkbenchTab.tsx` remains the full-height, three-column shell.
- `UnifiedSidebar.tsx` remains the project/thread selector. A compact workspace-mode switch is added above its searchable content.
- `ThreadHeader.tsx` keeps the 44px header rhythm and connection/HUD behavior.
- `Inspector.tsx` remains the right contextual panel; supervisor views supply their own tabs/content through a typed selection.
- `BottomConsoleDock.tsx` remains live output. It is associated with a selected run, not used as an evidence ledger.
- `DiffReviewStudioModal.tsx` is reused for implementation/audit diff inspection.
- `workbench/api/client.ts` continues same-origin admin credentials and normalized error handling.
- `workbench/api/codexApi.ts` gains fully typed supervisor methods. New methods use paths relative to its `/api/admin/codex` base, for example `/supervisor/missions`; they must not hardcode another host or port.
- `useWorkbenchStore.ts` may coordinate selections and server snapshots, but durable entities remain API-backed.
- Existing dark-theme tokens, Radix primitives, 44px targets, focus treatment, drawers, and modal semantics are retained.

The current Demo Mode may continue to demonstrate the legacy workbench. It must not expose Supervisor navigation or synthetic Supervisor entities. When Demo Mode is selected, Supervisor controls are disabled with the explanation “Supervisor workflows require the live FastAPI API.”

## 3. Information architecture and URLs

### 3.1 Workspace modes

Add a compact top-level mode control to the left rail:

1. **Supervisor** — durable missions, briefs, runs, audits, evidence, decisions, and checkpoints.
2. **Workbench** — current project/thread timeline and composer.
3. **Support** — current support-ticket management station.

The default remains **Workbench** until the Supervisor bootstrap endpoint is available and the operator has at least `can_view_supervisor`. Once available, persist the last selected mode as a view preference only.

### 3.2 Query contract

The cockpit stays a single React route. State that should survive refresh is encoded in query parameters:

| URL | Meaning |
|---|---|
| `/admin/coding-cockpit?view=missions` | Mission Board |
| `?view=mission&mission={missionId}` | Mission overview |
| `?view=brief&mission={missionId}&brief={briefId}` | Brief Builder |
| `?view=runs&mission={missionId}` | Agent Runs for a mission |
| `?view=run&run={runId}` | One author/audit run |
| `?view=audit&audit={auditId}` | Independent Audit Studio |
| `?view=evidence&mission={missionId}` | Evidence Ledger |
| `?view=governance&mission={missionId}` | Decisions and Risks |
| `?view=brain&mission={missionId}` | Project Brain and checkpoints |
| `?view=workbench&thread={threadId}` | Existing thread workbench |

Compatibility rules:

- Existing `?thread=` links without `view` resolve to `view=workbench`.
- Existing `?tab=health|fuzzer|issues|skills|plugins|stream` keeps opening the matching secondary tool over the active view.
- Invalid or unauthorized IDs show a contextual not-found/forbidden state without clearing the rest of the workspace.
- Browser Back/Forward restores selected view and entity; transient form dirtiness is not written to the URL.

## 4. Page and component contract

Create a `supervisor/` package inside the existing cockpit module. Suggested ownership:

```text
frontend/src/pages/admin/coding-cockpit/
├── CodingCockpitPage.tsx                    # parses/routes supervisor query state
├── CodexWorkbenchTab.tsx                    # hosts workspace modes
└── supervisor/
    ├── SupervisorWorkspace.tsx              # route-level state switch and boundaries
    ├── SupervisorNav.tsx                    # mission-scoped section navigation
    ├── SupervisorInspector.tsx              # context actions/details
    ├── MissionBoard.tsx
    ├── MissionOverview.tsx
    ├── BriefBuilder.tsx
    ├── DispatchDialog.tsx
    ├── AgentRuns.tsx
    ├── AgentRunDetail.tsx
    ├── AuditStudio.tsx
    ├── EvidenceLedger.tsx
    ├── DecisionsRisks.tsx
    ├── ProjectBrain.tsx
    ├── CheckpointDrawer.tsx
    ├── supervisorTypes.ts
    ├── supervisorState.ts                   # pure selectors/reducer only
    └── supervisor.test.ts
```

This is a component boundary, not permission to implement a disconnected greenfield page. All views use the shared authenticated `CodexApi` instance and the selected existing `Project`.

### 4.1 Mission Board

Purpose: show the current development programme at a glance and make the next safe action obvious.

Desktop layout:

- Header: **Development Supervisor**, API freshness, active project selector, `New mission` when permitted.
- Summary strip: active, blocked, awaiting audit, human decision, accepted this week. Counts come from `MissionSummaryResponse`, never client recomputation from a partial page.
- Filter row: text search, status, risk, owner, stale-only, and sort.
- Default table/list columns: mission, status, next action, progress, risk, open work packages, last checkpoint, updated.
- Optional compact board grouping uses the same result set; it is not a separate status model.
- Selecting a row opens `MissionOverview`; the row action menu never contains destructive actions that are not supported by the API.

Mission cards show both status text and icon. “Stale” means the server-provided `is_stale`/`stale_reason`, not a browser clock guess.

### 4.2 Mission Overview

Top summary contains objective, scope, baseline commit, current status, owner, next action, and unresolved blocker/risk counts. Below it:

- Work-package progress with author and reviewer separation.
- Latest brief revision and approval state.
- Active/attention-required runs.
- Audit outcomes and rework loop.
- Latest checkpoint synopsis.
- Recent evidence, decisions, and risks.

Primary action is derived from server `allowed_actions`. Examples: `Edit brief`, `Approve brief`, `Dispatch author`, `Start independent audit`, `Resolve decision`, or `Create checkpoint`. The frontend must not infer allowed transitions from role names.

### 4.3 Brief Builder

The builder is a structured editor with these sections:

1. Objective and evidence-backed problem statement.
2. In scope / out of scope.
3. Changed-file allowlist.
4. Architecture and tenant/security invariants.
5. Acceptance criteria, each with a stable criterion ID and required evidence kinds.
6. Exact verification commands.
7. Documentation obligations.
8. Prohibited actions.
9. Dependencies, assumptions, and open questions.
10. Required delivery report.

Behavior:

- A new brief begins as a server-created `draft` and receives an ID before editing.
- Autosave is debounced, but only a successful `PATCH` changes the visible state to `Saved`. Failure leaves `Unsaved changes` with Retry.
- Every update supplies `revision`; `409 REVISION_CONFLICT` opens a compare dialog with server and local values. There is no last-write-wins overwrite.
- `Validate` calls the API and renders field/criterion errors. It does not imply approval.
- `Approve revision` is a separate confirmed action. Approval makes that revision immutable; edits create a new draft revision.
- Markdown preview is sanitized. Raw HTML and executable links are not rendered.
- File paths are repository-relative and validated by the API against the selected project boundary.
- Verification commands are displayed as text and are not executable from the Brief Builder.

### 4.4 Dispatch and Agent Runs

`DispatchDialog` is opened from an approved brief/work package. It displays:

- Immutable brief revision ID and baseline commit.
- Run kind (`author` or `audit`) and role.
- Model/reasoning selection using the existing catalog.
- Permission profile and assigned worktree strategy.
- File allowlist, prohibited actions, required evidence, and estimated concurrency conflicts.
- Reviewer independence warning for audit runs.

The confirm label is explicit: **Dispatch author agent** or **Dispatch independent auditor**. While the request is pending it is disabled and labelled **Dispatching…**. Only a `201` response with durable `run_id` is success. A timeout/unknown result triggers an idempotency lookup using the same `idempotency_key`; it never inserts a local run.

`AgentRuns` shows author and audit runs in a common list with kind, status, assigned agent, branch/worktree, baseline, elapsed time, last heartbeat, evidence count, and attention reason. `AgentRunDetail` reuses:

- Current HUD and interruption control.
- Timeline event components.
- Bottom live-output dock.
- Diff Review Studio.
- Pending approval and user-input cards.

An interrupted/failed run can be retried only through a server-provided allowed action. Retry creates a new run linked by `retry_of_run_id`; it never resets history.

### 4.5 Independent Audit Studio

The Audit Studio is a three-pane review on wide screens:

- Left: original approved brief, criteria, invariants, and file allowlist.
- Centre: acceptance matrix and reviewer findings.
- Right: linked evidence, implementation diff, claimed limitations, and run provenance.

Each criterion row contains:

- Criterion ID and requirement.
- Verdict: `verified`, `failed`, `not_applicable`, or `not_verified`.
- One or more evidence IDs for `verified`/`failed`.
- Concise rationale.
- Residual risk.

Verdict controls:

- **Accept implementation** — available only when mandatory criteria are verified, no blocking finding is open, evidence is valid for the submitted commit, and independence is server-confirmed.
- **Request rework** — requires actionable findings and creates a new rework cycle on the work package.
- **Escalate for human decision** — requires a question and options/trade-off summary.
- **Fail audit run** — records inability to complete the audit; it does not reject the implementation.

The frontend shows `independence.author_run_id`, `reviewer_run_id`, and `is_independent`. It cannot override a false value. Acceptance is a single confirmed API action with a revision precondition.

### 4.6 Evidence Ledger

The ledger is append-only from the operator’s perspective. It supports filtering by work package, criterion, run, kind, result, commit, and verification state.

Evidence row/card fields:

- Kind and human label.
- Source run/agent.
- Commit and environment.
- Sanitized command label or artifact label.
- Result, exit code where applicable, timestamp, and duration.
- Output digest and bounded server-scrubbed summary.
- Linked criterion IDs.
- Integrity/verification state and rejection reason.

The browser may link existing evidence to a criterion through an API mutation; it cannot create “passed” command evidence manually. Human observations use the separate `human_observation` kind and are visibly distinguished from machine-captured proof.

### 4.7 Decisions and Risks

One mission-scoped view has two tabs:

- **Decisions:** proposed, accepted, superseded, rejected. Each records question/context, chosen option, alternatives, consequences, decider, timestamp, and related work packages/brief revisions.
- **Risks:** open, mitigated, accepted, materialized, closed. Each records severity, likelihood, impact, mitigation, owner, due date, and links.

Closing/accepting requires a server action and revision. Editing an accepted decision creates a successor; it does not rewrite history. High/critical risk acceptance requires `can_accept_risk` and a confirmation showing consequences.

### 4.8 Compact Project Brain and context checkpoints

Project Brain is a curated mission memory, not a raw transcript. The default compact view contains:

- Mission objective and current synopsis.
- Baseline and currently submitted commit.
- Accepted decisions and active invariants.
- Open blockers/questions and top risks.
- Current work package/run/audit pointers.
- Latest verified evidence summary.
- Recommended next action.
- Context budget metadata (`source_count`, `estimated_tokens`, last compacted time).

`Create checkpoint` requests a server-generated snapshot. The response includes a durable checkpoint ID and source references. A checkpoint is immutable. `Mark current` changes only the mission’s pointer to an existing checkpoint. “Restore” means load that snapshot as agent context for a new run; it never mutates Git or application data.

The checkpoint detail drawer shows included and excluded source categories, allowing an operator to confirm that raw secrets/PII/transcripts were not captured.

## 5. Authoritative state machines

Statuses are server enums. Unknown values render as `Unknown` with a warning and remain non-actionable.

### 5.1 Mission

```text
draft -> active -> paused -> active
             \-> completed
             \-> cancelled

Any non-terminal mission may become blocked when it has an unresolved blocking risk,
decision, or work package. `blocked` is derived by the server and does not replace
the persisted lifecycle status.
```

### 5.2 Brief revision

```text
draft -> validating -> draft            (validation errors)
                    -> ready_for_approval
ready_for_approval -> approved
ready_for_approval -> draft              (requested changes)
approved -> superseded                   (only after a newer revision is approved)
```

### 5.3 Work package

```text
draft -> ready -> dispatching -> running
running -> awaiting_audit | blocked | failed | cancelled
awaiting_audit -> auditing
auditing -> accepted | rework_requested | human_decision_required | audit_failed
rework_requested -> ready                (new approved brief revision as needed)
human_decision_required -> auditing | rework_requested | cancelled
audit_failed -> awaiting_audit            (new independent audit run)
accepted -> completed                     (mission roll-up may then complete)
```

`dispatching` is server-observed, not optimistic UI state. `accepted` requires the audit invariant. `completed` does not mean merged, pushed, or deployed.

### 5.4 Run

```text
queued -> provisioning -> running
running -> waiting_approval | waiting_input | completed | failed | interrupted | timed_out
waiting_approval -> running | failed | interrupted
waiting_input -> running | failed | interrupted
```

### 5.5 Audit

```text
queued -> running -> submitted
submitted -> accepted | rework_requested | human_decision_required
running -> failed | interrupted
```

### 5.6 Evidence

```text
captured -> verifying -> verified | rejected | unavailable
```

Evidence never transitions from rejected/unavailable to verified in place; recapture creates a successor evidence record.

## 6. TypeScript DTO contract

Add these DTOs to `supervisor/supervisorTypes.ts` and export them through `workbench/api/index.ts`. No supervisor API method returns `any`.

```ts
export type ISODateTime = string
export type MissionStatus = 'draft' | 'active' | 'paused' | 'completed' | 'cancelled'
export type WorkPackageStatus =
  | 'draft' | 'ready' | 'dispatching' | 'running' | 'awaiting_audit'
  | 'auditing' | 'rework_requested' | 'human_decision_required'
  | 'audit_failed' | 'accepted' | 'completed' | 'blocked' | 'failed' | 'cancelled'
export type RunStatus =
  | 'queued' | 'provisioning' | 'running' | 'waiting_approval' | 'waiting_input'
  | 'completed' | 'failed' | 'interrupted' | 'timed_out'
export type AuditStatus =
  | 'queued' | 'running' | 'submitted' | 'accepted' | 'rework_requested'
  | 'human_decision_required' | 'failed' | 'interrupted'
export type EvidenceState = 'captured' | 'verifying' | 'verified' | 'rejected' | 'unavailable'
export type RiskSeverity = 'low' | 'medium' | 'high' | 'critical'

export interface AllowedAction {
  action: string
  enabled: boolean
  disabled_reason?: string
}

export interface SupervisorCapabilities {
  can_view_supervisor: boolean
  can_create_mission: boolean
  can_edit_brief: boolean
  can_approve_brief: boolean
  can_dispatch_author: boolean
  can_dispatch_audit: boolean
  can_submit_audit_verdict: boolean
  can_accept_risk: boolean
  can_create_checkpoint: boolean
}

export interface SupervisorBootstrapResponse {
  capabilities: SupervisorCapabilities
  active_project_id: string | null
  counts: MissionCounts
  server_time: ISODateTime
  event_stream_available: boolean
}

export interface MissionCounts {
  active: number
  blocked: number
  awaiting_audit: number
  human_decision_required: number
  accepted_this_week: number
}

export interface MissionSummary {
  id: string
  project_id: string
  title: string
  objective: string
  status: MissionStatus
  is_blocked: boolean
  next_action: string
  progress_percent: number
  highest_risk: RiskSeverity | null
  open_work_package_count: number
  latest_checkpoint_id: string | null
  is_stale: boolean
  stale_reason: string | null
  owner_display_name: string
  revision: number
  created_at: ISODateTime
  updated_at: ISODateTime
  allowed_actions: AllowedAction[]
}

export interface MissionDetail extends MissionSummary {
  scope_summary: string
  baseline_commit: string
  open_blocker_count: number
  open_risk_count: number
  latest_brief: BriefRevisionSummary | null
  work_packages: WorkPackageSummary[]
  latest_checkpoint: ContextCheckpoint | null
}

export interface AcceptanceCriterion {
  id: string
  statement: string
  mandatory: boolean
  required_evidence_kinds: EvidenceKind[]
}

export type BriefStatus = 'draft' | 'validating' | 'ready_for_approval' | 'approved' | 'superseded'
export interface BriefRevisionSummary {
  id: string
  mission_id: string
  revision_number: number
  status: BriefStatus
  title: string
  updated_at: ISODateTime
  approved_at: ISODateTime | null
}

export interface BriefRevision extends BriefRevisionSummary {
  problem_statement: string
  objective: string
  in_scope: string[]
  out_of_scope: string[]
  changed_file_allowlist: string[]
  invariants: string[]
  acceptance_criteria: AcceptanceCriterion[]
  verification_commands: string[]
  documentation_obligations: string[]
  prohibited_actions: string[]
  dependencies: string[]
  assumptions: string[]
  open_questions: string[]
  delivery_requirements: string[]
  revision: number
  allowed_actions: AllowedAction[]
}

export interface WorkPackageSummary {
  id: string
  mission_id: string
  title: string
  status: WorkPackageStatus
  approved_brief_revision_id: string | null
  author_run_id: string | null
  current_audit_id: string | null
  cycle_number: number
  revision: number
  updated_at: ISODateTime
  allowed_actions: AllowedAction[]
}

export interface AgentRunSummary {
  id: string
  work_package_id: string
  kind: 'author' | 'audit'
  status: RunStatus
  agent_display_name: string
  model: string
  reasoning_effort: string
  permission_profile: 'read_only' | 'workspace_write' | 'managed' | 'elevated'
  thread_id: string
  branch: string | null
  worktree: string | null
  baseline_commit: string
  submitted_commit: string | null
  evidence_count: number
  attention_reason: string | null
  last_heartbeat_at: ISODateTime | null
  started_at: ISODateTime | null
  completed_at: ISODateTime | null
  retry_of_run_id: string | null
  allowed_actions: AllowedAction[]
}

export type EvidenceKind =
  | 'test_run' | 'build' | 'lint' | 'runtime_smoke' | 'browser_gate'
  | 'diff_review' | 'security_check' | 'documentation_gate' | 'human_observation'
export interface EvidenceRecord {
  id: string
  mission_id: string
  work_package_id: string
  source_run_id: string | null
  kind: EvidenceKind
  label: string
  state: EvidenceState
  result: 'passed' | 'failed' | 'inconclusive' | 'observed'
  commit_sha: string | null
  environment: string
  command_label: string | null
  exit_code: number | null
  duration_ms: number | null
  output_digest: string | null
  summary: string
  criterion_ids: string[]
  rejection_reason: string | null
  captured_at: ISODateTime
  verified_at: ISODateTime | null
}

export type CriterionVerdict = 'verified' | 'failed' | 'not_applicable' | 'not_verified'
export interface AuditCriterionResult {
  criterion_id: string
  verdict: CriterionVerdict
  evidence_ids: string[]
  rationale: string
  residual_risk: string | null
}

export interface AuditDetail {
  id: string
  work_package_id: string
  status: AuditStatus
  author_run_id: string
  reviewer_run_id: string
  is_independent: boolean
  submitted_commit: string
  brief_revision_id: string
  criterion_results: AuditCriterionResult[]
  blocking_finding_count: number
  overall_rationale: string | null
  revision: number
  allowed_actions: AllowedAction[]
}

export interface DecisionRecord {
  id: string
  mission_id: string
  status: 'proposed' | 'accepted' | 'superseded' | 'rejected'
  question: string
  context: string
  chosen_option: string | null
  alternatives: string[]
  consequences: string[]
  successor_decision_id: string | null
  revision: number
  updated_at: ISODateTime
}

export interface RiskRecord {
  id: string
  mission_id: string
  status: 'open' | 'mitigated' | 'accepted' | 'materialized' | 'closed'
  title: string
  severity: RiskSeverity
  likelihood: 'unlikely' | 'possible' | 'likely'
  impact: string
  mitigation: string
  owner_display_name: string | null
  due_at: ISODateTime | null
  blocking: boolean
  revision: number
  updated_at: ISODateTime
}

export interface ContextCheckpoint {
  id: string
  mission_id: string
  sequence: number
  synopsis: string
  baseline_commit: string
  submitted_commit: string | null
  decision_ids: string[]
  invariant_ids: string[]
  open_risk_ids: string[]
  work_package_id: string | null
  run_id: string | null
  audit_id: string | null
  evidence_ids: string[]
  next_action: string
  source_count: number
  estimated_tokens: number
  included_source_categories: string[]
  excluded_source_categories: string[]
  created_at: ISODateTime
  created_by_display_name: string
}

export interface Page<T> {
  items: T[]
  next_cursor: string | null
  total: number
}
```

Mutation payloads always include the current `revision` for editable durable records. Dispatch payloads additionally include an operator-generated UUID `idempotency_key`; the server stores it and returns the original result for identical retries.

## 7. REST and event contract

All paths below are relative to `/api/admin/codex`. Every route requires the FastAPI Bookings admin dependency and tenant/user ownership enforcement. The frontend must not ship Supervisor UI against routes that only check the legacy standalone token.

| Method and path | Purpose |
|---|---|
| `GET /supervisor/bootstrap` | capabilities, project, counts, server time, stream availability |
| `GET /supervisor/missions` | cursor-paginated filtered Mission Board |
| `POST /supervisor/missions` | create durable draft mission |
| `GET /supervisor/missions/{id}` | mission detail |
| `PATCH /supervisor/missions/{id}` | edit with revision precondition |
| `POST /supervisor/missions/{id}/actions/{action}` | explicit allowed mission transition |
| `POST /supervisor/missions/{id}/briefs` | create first/new draft revision |
| `GET /supervisor/briefs/{id}` | full structured brief |
| `PATCH /supervisor/briefs/{id}` | autosave structured brief with revision |
| `POST /supervisor/briefs/{id}/validate` | server validation, no state fabrication |
| `POST /supervisor/briefs/{id}/approve` | immutable approval action |
| `POST /supervisor/missions/{id}/work-packages` | create work package from approved brief |
| `GET /supervisor/work-packages/{id}` | work package detail |
| `POST /supervisor/work-packages/{id}/dispatch-author` | durable author run dispatch |
| `POST /supervisor/work-packages/{id}/dispatch-audit` | independent audit dispatch |
| `GET /supervisor/runs` | filtered author/audit runs |
| `GET /supervisor/runs/{id}` | run detail and provenance |
| `POST /supervisor/runs/{id}/interrupt` | interrupt an active run |
| `POST /supervisor/runs/{id}/retry` | create linked retry run |
| `GET /supervisor/audits/{id}` | audit matrix, independence, evidence |
| `PATCH /supervisor/audits/{id}` | save criterion review with revision |
| `POST /supervisor/audits/{id}/submit` | submit matrix |
| `POST /supervisor/audits/{id}/verdict` | accept, rework, or human-decision verdict |
| `GET /supervisor/evidence` | cursor-paginated evidence ledger |
| `POST /supervisor/evidence/{id}/criterion-links` | link existing evidence to criteria |
| `GET/POST /supervisor/missions/{id}/decisions` | list/create decisions |
| `PATCH /supervisor/decisions/{id}` | update proposed decision with revision |
| `POST /supervisor/decisions/{id}/actions/{action}` | accept/reject/supersede |
| `GET/POST /supervisor/missions/{id}/risks` | list/create risks |
| `PATCH /supervisor/risks/{id}` | update risk with revision |
| `POST /supervisor/risks/{id}/actions/{action}` | mitigate/accept/materialize/close |
| `GET /supervisor/missions/{id}/brain` | compact current project brain |
| `GET /supervisor/missions/{id}/checkpoints` | checkpoint history |
| `POST /supervisor/missions/{id}/checkpoints` | server-build immutable checkpoint |
| `POST /supervisor/missions/{id}/checkpoints/{checkpointId}/mark-current` | update current pointer |
| `POST /supervisor/events/ticket` | acquire scoped one-use stream ticket |
| `GET /supervisor/events/stream` | tenant/project-scoped supervisor SSE |

Do not expose a general-purpose `PATCH status`. Explicit action endpoints validate transition, role, evidence, independence, and current revision atomically.

Expected errors:

- `401`: expire session and use the application auth flow.
- `403`: keep read-only context where permitted; display the server reason.
- `404`: contextual not-found state.
- `409 REVISION_CONFLICT`: compare/refresh flow; never blind retry a PATCH.
- `409 IDEMPOTENCY_CONFLICT`: same key with different dispatch payload; block and report.
- `422`: map structured field and criterion errors inline.
- `503`: show unavailable/retry; never switch to synthetic data.

Supervisor SSE event names:

```text
mission.updated
brief.updated
work_package.updated
run.updated
run.attention_required
audit.updated
evidence.captured
evidence.verified
decision.updated
risk.updated
checkpoint.created
```

Each event envelope includes `id`, `sequence`, `occurred_at`, `project_id`, `mission_id`, `entity_id`, `entity_revision`, and a minimal payload. On sequence gap, stream reconnect, or unknown event, refetch the affected entity. SSE is an invalidation/attention channel; REST remains authoritative.

## 8. Client and state behavior

Add a `SupervisorApi` section to the existing `CodexApi` or a composed `SupervisorApi` that receives the same `ApiClient`. It must:

- Return the exact DTOs above, never `any`.
- Accept `AbortSignal` for list/detail GETs so route changes cancel stale requests.
- Preserve structured server error code, request ID, field errors, and current revision.
- Generate no entity IDs except the dispatch idempotency UUID.
- Reuse the existing ticket-first SSE strategy and backoff; do not put the long-lived bearer token in the URL.
- Refetch after successful mutations and reconcile by entity ID/revision.

State separation:

- **Server snapshot:** entities, counts, capabilities, allowed actions, revisions, and freshness.
- **Route state:** selected view/mission/brief/run/audit.
- **Local view state:** filters, collapsed sections, panel size.
- **Local form buffer:** dirty brief/audit/decision/risk fields until save acknowledgement.

Never optimistically transition mission/work-package/run/audit/evidence state. A pending action may show a spinner but continues to display the last confirmed state.

## 9. Loading, empty, degraded, and error states

Every view implements the following explicitly:

| State | Required presentation |
|---|---|
| Initial loading | Structure-matching skeleton with page title available to assistive tech |
| Background refresh | Non-blocking freshness indicator; preserve current content |
| Empty missions | “No missions yet” plus `Create mission` only when capability allows |
| Empty runs | Explain that an approved brief/work package is required; link to its missing step |
| Empty audit | Explain author completion/evidence prerequisite; no fake matrix |
| Empty evidence | “No evidence captured”; show required evidence from criteria separately |
| Empty decisions/risks | Neutral empty state, not “all safe” |
| Empty checkpoints | Explain server-generated checkpoint contents and `Create checkpoint` capability |
| Mutation pending | Disable only conflicting action; label action in progress |
| Validation failure | Inline section error summary plus focus first invalid field |
| Connection/SSE loss | Persistent `Live updates paused` badge and manual Retry; REST content stays visible and marked stale |
| API unavailable | Error panel with request ID and Retry; Supervisor cannot enter demo success state |
| Forbidden action | Disabled control with visible reason; server still enforces it |
| Stale revision | Compare/refresh dialog preserving the local buffer |
| Unknown status | Warning badge, raw safe enum value, no state-changing action |

Toasts are supplementary. Durable outcomes and errors remain visible in the relevant view after the toast disappears.

## 10. Responsive and accessibility behavior

### Desktop (`>= 1024px`)

- Preserve the current resizable left rail and right inspector.
- Mission Board uses the center stage; contextual filters/details use the right inspector.
- Audit Studio may use its internal three-pane layout only when the center width is at least 960px.

### Tablet (`768–1023px`)

- Left rail remains a drawer.
- Supervisor inspector becomes a right sheet.
- Audit brief, matrix, and evidence become accessible tabs with persistent unsaved-state indicator.

### Mobile (`< 768px`, including 320px)

- One pane at a time: list -> detail -> editor. Query parameters preserve the selected record.
- Data tables render as labelled cards; no horizontal page scrolling.
- Sticky bottom action bar respects `env(safe-area-inset-bottom)`.
- Diff review may scroll within its own labelled region.

Accessibility requirements:

- One `main` landmark and labelled `nav`, `aside`, and region landmarks.
- Logical `h1`/`h2` hierarchy even inside the full-height shell.
- All status information includes text; color is never the only signal.
- Interactive targets are at least 44x44 CSS pixels on touch layouts.
- Keyboard focus is visible and restored to the trigger after closing dialogs/sheets.
- Dialogs have title, description, focus trap, Escape close (unless a server mutation is committing), and a non-destructive initial focus.
- Async status uses a polite `aria-live` region; approval, dispatch, and audit errors use `role="alert"`.
- Mission/work-package progress exposes text and `aria-valuenow`; animations honor reduced motion.
- Resizer handles use `role="separator"`, `aria-orientation="vertical"`, current/min/max values, and Arrow-key resizing.
- Criterion errors are linked with `aria-describedby`; the error summary links back to fields.
- Destructive/cancelling actions require explicit labels and confirmation; Enter never accidentally accepts an audit while typing rationale.
- Relative times include an accessible absolute timestamp.

## 11. Authorization visibility and trust presentation

The bootstrap capabilities and per-entity `allowed_actions` control presentation:

- A user without `can_view_supervisor` sees a compact forbidden page; no Supervisor navigation or background data requests.
- Users who can view but not mutate see the complete evidence/audit history in read-only form where tenant policy permits.
- High-value controls remain visible but disabled when that aids workflow understanding; `disabled_reason` is rendered adjacent or in an accessible tooltip.
- Controls for data the user may not know exists are omitted, per backend policy.
- Client-side checks are presentation only. Every backend query/mutation is tenant- and user-scoped.
- Show provenance on verdicts, checkpoints, evidence, and decisions: actor display name, time, source run, and relevant commit. Do not expose email, token, raw identity claims, or filesystem secrets.

## 12. Verification contract

### 12.1 Pure state and API tests

Add focused tests for:

- Query parsing and legacy `thread`/`tab` compatibility.
- Every DTO-backed `CodexApi` path and method; assert no alternate host/port.
- Cursor/filter serialization and request cancellation.
- Structured 401/403/409/422/503 handling.
- Idempotent dispatch retry after an unknown network outcome.
- Pure state selectors for next action, unknown status, and freshness.
- No optimistic accepted/completed/verified transitions.
- SSE gap/refetch behavior and event-ticket renewal.

### 12.2 Component/workflow tests

Verify:

- Capability-gated navigation and disabled reasons.
- Brief autosave success/failure/conflict, validation, approval immutability, and new revision creation.
- Author dispatch only after approved brief; server error does not add a run.
- Audit dispatch shows and enforces independent reviewer provenance.
- Acceptance cannot be submitted with missing evidence or blocking findings.
- Rework creates a visible cycle and preserves prior audit/run history.
- Evidence cannot be manually fabricated as machine-passed.
- Decision supersession and critical-risk confirmation.
- Checkpoint creation/selection without Git rollback semantics.
- Loading, empty, forbidden, stale, disconnected, and unknown-enum states.
- Keyboard operation, focus restoration, live regions, labels, and 320px overflow.

### 12.3 Backend contract tests required before enabling the UI

- Tenant/user isolation for every list, detail, mutation, SSE ticket, and event.
- Role/capability enforcement independent of the browser.
- Revision conflict and idempotency behavior.
- Legal/illegal state transitions.
- Audit author/reviewer separation.
- Acceptance transaction requires verified criterion evidence for the submitted commit.
- Evidence append-only rules, output scrubbing, and bounded summaries.
- Checkpoint immutability and PII/secret exclusion.
- Restart recovery for queued/running runs and context checkpoints.

### 12.4 Required commands

Use repository-discovered and module-documented commands; do not substitute a broad guessed suite:

```powershell
npm test --prefix frontend
npm run build --prefix frontend
python scripts/verify_zero_console_errors.py --url http://localhost:7070 --routes /admin/coding-cockpit
python scripts/verify_living_docs.py --path frontend/src/pages/admin/coding-cockpit/README.md
```

The browser gate must exercise at least Mission Board, one mission, Brief Builder, a run, Audit Studio, Evidence Ledger, Decisions/Risks, and Project Brain using authenticated, tenant-scoped synthetic fixtures created through the real API. It must report zero `console.error`, zero page errors, and zero 4xx/5xx asset/API responses.

## 13. Delivery sequence and acceptance gates

1. **Backend trust foundation** — ownership columns/scoping, capabilities, revisioning, idempotency, explicit transitions, evidence integrity, migrations, and tests.
2. **Typed client and shell** — DTOs, Supervisor bootstrap, workspace navigation, URL contract, error boundary, and SSE invalidation.
3. **Mission + brief** — Mission Board, overview, Brief Builder, approval workflow.
4. **Dispatch + runs** — author dispatch, run monitoring, existing timeline/diff/output reuse.
5. **Evidence + independent audit** — ledger, criterion linking, Audit Studio, verdict gates, rework cycles.
6. **Decisions/risks + Project Brain** — governance records, checkpoint generation/history/current pointer.
7. **Cross-view QA** — responsive/accessibility pass, browser gate, living documentation, independent QA sign-off.

Do not enable a phase’s navigation in production until its real database migration, API, authorization, tests, and empty/error behavior exist. Feature flags may hide an incomplete phase; they may not route to static sample data.

## 14. Definition of done

The supervisor UX is complete when an authorized operator can create a mission, author and approve a structured brief, dispatch a real author agent, inspect durable run activity, collect commit-bound evidence, dispatch a different audit agent, receive an evidence-backed verdict, request rework or accept, record decisions/risks, and create a compact durable context checkpoint—all through tenant-scoped FastAPI endpoints, with truthful recovery after refresh/restart and no locally fabricated success path.

The final implementation report must include the migration(s), changed files, API tests, frontend tests, browser-gate output, documentation gate, independent QA result, commit hash, and push confirmation required by repository policy.
