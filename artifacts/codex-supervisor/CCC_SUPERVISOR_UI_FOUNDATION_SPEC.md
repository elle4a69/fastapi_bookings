# Codex Development Supervisor UI — Foundation Specification

**Task:** `ccc_ui_v2_foundation_spec`
**Status:** build-ready product and interaction specification; no application code changed
**Application:** FastAPI Bookings
**Canonical frontend:** `F:\Projects\fastapi_bookings\frontend`
**Temporary v2 route:** `/admin/coding-cockpit-v2`
**Final route after acceptance:** `/admin/coding-cockpit`
**Canonical API facade:** `/api/admin/codex/v2`
**Primary operator during development:** authenticated FastAPI Bookings platform owner
**Date:** 2026-10-15 (Australia/Sydney)

## 1. Binding product decision and supersession

The Codex Development Supervisor UI is a new, mission-first interface built from the ground up. It is not an extension, reskin, or incremental refactor of the current Coding Cockpit.

The following decisions are binding:

1. `frontend/` is the only canonical frontend source tree.
2. `codex-control-centre/frontend/` is reference/decommission-only. It receives no new features and is not a source of runtime components, styles, state, API types, or tests.
3. The existing integrated cockpit is reference material and a temporary fallback during cutover. Its shell, navigation, store, demo mode, fixture-backed state, inspector, global dock, and tool-modal composition are not foundations for the new UI.
4. The new UI reuses the proven backend execution substrate through typed adapters. It does not duplicate the worker, worktree, approval, or event infrastructure.
5. No supervisor screen or action is enabled until its durable backend model, authorization, state transition, API, and error behavior exist.
6. No mock, fixture, timer, browser-generated record, or optimistic lifecycle transition may appear in the production call graph.
7. CopilotKit/AG-UI, if later accepted through the comparative spike in sections 15.7 and 15.10, is an optional active-run transport/presentation adapter only. It does not alter the ground-up UI decision and cannot become the application shell, navigation, server-state cache, approval authority, durable control plane, or source of truth.
8. Codex Bridge is **REFERENCE ONLY** under section 15.8. It is not a runtime/build dependency, source donor, browser endpoint, authentication or mutation authority, lifecycle manager, persistence layer, or UI foundation.
9. Open WebUI is **REFERENCE ONLY** under section 15.9. No Open WebUI code, component, backend, authentication/RBAC, data store, model gateway, RAG, plugin/tool/terminal system, asset, CSS, branding, wording, page structure, or licence obligation enters the supervisor. Its accepted lessons are independently specified first-party behavior requirements only.
10. Assistant UI is **SPIKE FIRST / likely narrow only** under section 15.10. It is not a foundation dependency, shell, information architecture, state authority, approval authority, durable thread store, or control plane. The only currently eligible Assistant UI arm is an exact-pinned `@assistant-ui/react` core `ExternalStoreRuntime` projection of one selected Run; the current AG-UI adapter is blocked by protocol incompatibility.

This specification explicitly supersedes incompatible UI-preservation clauses in `CCC_UX_CONTRACT.md`, especially:

- section 2's direction to retain `CodingCockpitPage`, `CodexWorkbenchTab`, `UnifiedSidebar`, `ThreadHeader`, `Inspector`, and `BottomConsoleDock` as the supervisor shell;
- section 3's workspace-mode switch inside the old left rail and the default-to-Workbench rule;
- section 4's component tree rooted inside the existing cockpit and its implied preservation of the three-column workbench;
- any requirement to extend `useWorkbenchStore.ts`, `workbench/api/codexApi.ts`, local workbench UI wrappers, secondary tool modals, Demo Mode, or the old inspector/dock topology.

The old contract remains authoritative where compatible: durable server authority, independent audit, revision conflicts, idempotency, truthful error states, privacy, accessibility, responsive behavior, and verification. This specification also refines the architecture blueprint's phrase “add views inside the existing Coding Cockpit”: the final public route remains `/admin/coding-cockpit`, but the page implementation is replaced after v2 acceptance rather than extended in place. Neither the Open WebUI reference nor either optional React agent-runtime candidate changes that ground-up native decision.

## 2. Product outcome

The supervisor answers four questions without requiring the operator to reconstruct them from chat threads:

1. What work should happen next?
2. Which approved brief governs it?
3. Who is authoring or independently auditing it?
4. What durable evidence proves the result is acceptable?

The core loop is:

```text
Intake or observation
  -> Mission
  -> Work package
  -> Draft and approve brief
  -> Dispatch bounded author run
  -> Capture commit-bound evidence
  -> Dispatch independent audit
  -> Accept | request rework | require human decision
  -> Create durable checkpoint
```

The UI is an engineering-control surface. It does not become a booking, payment, SMS, deployment, or customer-data control plane.

## 3. Product principles

### 3.1 Mission before machinery

The home screen shows missions, blockers, decisions, and next safe actions. Threads, terminals, plugins, skills, and diagnostics are supporting capabilities, not the information architecture.

### 3.2 Server authority is visible

Every lifecycle status, capability, allowed action, revision, evidence result, and verdict comes from the v2 API. The browser may hold filters and unsaved form text; it may not invent authoritative state.

### 3.3 Truth over reassurance

`Unavailable`, `unknown`, `not verified`, `disconnected`, `failed`, and `skipped` are first-class states. The interface never converts absence or failure into a green result.

### 3.4 Briefs are contracts

An approved brief is immutable, versioned, reviewable, and sufficient for a fresh author or auditor. Free-form chat may clarify an active run, but it cannot replace scope, acceptance criteria, file allowlists, or verification commands.

### 3.5 Independent assurance is structural

The author and auditor are different assignments, runs, threads, worktrees, and contexts. The UI displays this provenance and cannot override a failed independence check.

### 3.6 Context is curated, not accumulated

The Project Brain contains decisions, invariants, risks, blockers, checkpoints, and next actions. It is not an endless transcript viewer.

### 3.7 Progressive disclosure

Mission status and next action are immediately visible. Execution detail, raw bounded output, diffs, evidence digests, and operations settings are available in context, not always on screen.

### 3.8 Safe actions are explicit

Buttons name the result: `Approve brief revision`, `Dispatch author agent`, `Interrupt run`, `Request rework`, or `Accept implementation`. Generic `Run`, `Apply`, and ambiguous icon-only actions are prohibited for material transitions.

### 3.9 One system, one visual language

Use FastAPI Bookings shared tokens and primitives. The product is calm, data-dense, and operational. It is not a sci-fi cockpit.

## 4. Canonical ownership and migration boundary

### 4.1 Frontend ownership

Create the new implementation under:

```text
frontend/src/pages/admin/codex-supervisor/
```

The package may import:

- shared FastAPI Bookings components from `@/components/ui`;
- shared authentication and same-origin transport from `frontend/src/lib` after unsafe tenant/default behavior is removed or wrapped;
- generated or strictly maintained v2 API types;
- small, explicitly extracted presentation internals from the legacy cockpit after they have focused tests and no legacy-store dependency.

It must not import:

- `useWorkbenchStore`;
- `realisticFixtures` or any demo fixture;
- the old cockpit shell, inspector, sidebar, modal coordinator, or local component primitives;
- modules from `codex-control-centre/frontend`;
- direct resident-agent in-memory endpoints as supervisor state;
- a standalone host/port or a browser-supplied tenant default.

### 4.2 Backend ownership

The v2 facade owns UI-facing schemas and action semantics at `/api/admin/codex/v2`. It adapts the durable supervisor domain and proven Control Centre services internally. FastAPI Bookings owns the sole southbound Codex app-server worker adapter and mutation/lifecycle authority; no third-party daemon or parallel manager may write a supervisor session. The browser does not call worker-manager internals, app-server, Codex Bridge, control sockets, rollout stores, or host-path endpoints directly.

UI terms map to domain terms without duplicate persistence:

| UI term | Durable domain aggregate |
|---|---|
| Mission | `supervisor_programme` |
| Work item | `work_package` |
| Brief | `brief_revision` |
| Assignment | `agent_assignment` |
| Run | `agent_run` linked to thread/turn/worktree |
| Evidence | `evidence_artifact` |
| Audit | `audit_review` + `audit_criteria` |
| Brain item | `project_memory_item` |
| Checkpoint | `context_checkpoint` |

### 4.3 Current prerequisite status

As inspected on 2026-10-15:

- P0 trust-boundary commit `170f6f7eb62278bc029d39caaeda8637d4c99c59` is pushed but is not an ancestor of primary HEAD `6256fc5d25e3ad5c2f60d739c24446ebc4df3546`.
- The durable supervisor domain and `/api/admin/codex/v2` facade are not implemented.
- The current API client still contains a `simplydemo` tenant fallback and loose `any` contracts.
- The current cockpit production path still contains demo/synthetic behavior.

These are backend/integration prerequisites, not invitations to fake the UI.

### 4.4 First-slice project claim and bootstrap

Slice 1 uses the architecture blueprint's explicit claim/quarantine model; it does not infer ownership from a repository path.

1. Deployment configuration identifies the one permitted FastAPI Bookings repository root server-side and gives it an opaque configured project ID. The path is never returned to or accepted from the browser.
2. Migration marks pre-ownership Control Centre projects `unclaimed` or `quarantined`. They are invisible to normal mission queries.
3. `GET /api/admin/codex/v2/bootstrap` returns a bounded, typed project context:

```ts
interface BootstrapProjectContext {
  state: 'ready' | 'unconfigured' | 'claim_required' | 'quarantined' | 'migration_required'
  project_id: string | null
  display_name: string | null
  project_version: number | null
  claim_action: AllowedActionDescriptor | null
  claim_action_absent_reason_code:
    | 'not_applicable' | 'forbidden' | 'resource_hidden' | null
}
```

When `state='claim_required'` and the actor may know the project exists, `claim_action` is a real descriptor with `action='claim_project'`, `resource_version=project_version`, `idempotency_required=true`, and either `allowed=true` or an explicit safe `allowed=false` reason such as `claim_guard_failed`. It is never a placeholder. `claim_action=null` is legal only when claiming is not applicable or disclosure/authorization policy forbids presenting it; `claim_action_absent_reason_code` is then non-null. For `state='ready'`, the absent reason is `not_applicable`. A forbidden/hidden response contains no claimable project ID.

4. When `claim_required`, a platform owner may call prerequisite `POST /api/admin/codex/v2/projects/{project_id}/claim` using an idempotency key, expected project version, and the exact server-provided `claim_project` action descriptor. The server validates the deploy-configured root, existing record fingerprint, actor, current claim state, and absence of conflicting ownership in one transaction.
5. Claiming stamps tenant/owner/actor fields and creates the owner membership. It does not move files, accept a browser path, infer identity from historical prompts, or expose quarantined IDs to another actor.
6. `unconfigured`, `quarantined`, and `migration_required` render a blocking readiness panel. The only possible recovery control is the server-provided platform-owner action leading to secondary Operations. Mission creation remains unavailable.

Negative tests cover guessed IDs, cross-tenant claims, repeat/concurrent claims, configured-root mismatch, quarantined rows, non-platform owners, and attempts to supply a host path.

## 5. Route and cutover strategy

### 5.1 Parallel route phase

During development:

- `/admin/coding-cockpit` continues to render v1.
- `/admin/coding-cockpit-v2/*` renders the new supervisor and is visible only to authenticated platform owners with `can_view_supervisor`.
- A persisted, server-controlled cutover mode governs route availability and mutation authority. A browser-only flag is insufficient.
- V2 does not embed or frame v1. A contextual link may open v1 in a separate route for a missing execution capability during migration.
- Both UIs may read resources where authorized, but server middleware—not UI visibility—enforces one mutation owner for every resource.

The cutover state is a versioned platform setting with an actor/time audit record:

| Mode | V1 behavior | V2 behavior | Mutation authority |
|---|---|---|---|
| `v1_only` | Existing authorized reads/mutations continue | Bootstrap returns the mode and no supervisor-domain data; an authorized platform owner receives only the cutover control fragment and `change_cutover_mode` descriptor, while all other actors receive `can_view_supervisor=false` and stop before domain queries | V1 only |
| `v2_read_only` | Legacy-only resources may still mutate through v1; claimed resources reject v1 mutation | Authorized v2 snapshots are readable; product mutations are denied with `409 cutover_read_only`; only `claim_project` and `change_cutover_mode` setup mutations may be server-enabled | V1 for legacy-only resources; v2 only for transactional claim/cutover setup; no product writer for supervisor-owned resources |
| `v2_active` | V1 may read; legacy mutation endpoints reject any supervisor-owned resource with `409 supervisor_owned` | V2 mutations allowed only through supervisor state machines and `allowed_actions` | V2 for supervisor-owned resources; V1 only for explicitly legacy-only resources |
| `rollback` | Legacy-only resources may mutate; supervisor-owned resources remain read-only to v1 | V2 reads remain available; new mission/dispatch/decision mutations stop; only server-listed drain actions such as interrupt/deny remain | No new supervisor writers; bounded v2 drain actions only |

Every project, thread, approval, worktree, assignment, and run exposed during dual operation has a server-owned `control_plane: legacy|supervisor_v2` marker or a durable supervisor lineage from which that marker is derived. A legacy endpoint performs this check transactionally before mutation. Stale v1 tabs and direct legacy requests receive `409 supervisor_owned` with a safe authorized route hint; they never bypass the v2 state machine. Rollback never deletes or rewrites v2 records, never transfers supervisor-owned resources back to v1, and never creates concurrent writers.

Only an authenticated platform owner with the server-returned `change_cutover_mode` descriptor may request a transition. The server still re-authorizes the actor and guards in the transaction. Rollback recovery additionally requires evidence from a different reviewer/approver than the operator who initiated rollback.

#### Complete legal transition graph

```text
v1_only <-> v2_read_only -> v2_active -> rollback -> v2_read_only
                 \-----------------------> rollback
```

There are no other edges. A request whose target equals the current mode is an idempotent no-op: `200`, `changed=false`, no version increment, and a `cutover.noop` audit record. It is not a transition edge.

| From | To | Who | Required guards and evidence |
|---|---|---|---|
| `v1_only` | `v2_read_only` | Platform owner | P0 is an ancestor of the deployed commit; migrations and OpenAPI/action-registry versions match; bootstrap/readiness pass; no incomplete cutover operation; reason required |
| `v2_read_only` | `v1_only` | Platform owner | No claimed/supervisor-owned project or resource; no mission/work/brief/run/audit/evidence/checkpoint row; no pending v2 idempotency record or v2 mutation lease; reason required |
| `v2_read_only` | `v2_active` | Platform owner | Configured project is `ready` and claimed; P0/migrations/readiness current; all v1 mutation leases/workers for the claimed scope drained; no unresolved v2 idempotency operation; independent clean-checkout/release evidence IDs supplied; typed activation acknowledgement supplied |
| `v2_read_only` | `rollback` | Platform owner | Incident/defect reason and evidence/reference supplied; transition is immediate even if readiness is degraded; setup mutations stop and supervisor-owned records remain preserved |
| `v2_active` | `rollback` | Platform owner | Incident/rollback reason required; transition is immediate and does not wait for active runs; new product mutations stop atomically; internal terminal event recording and descriptor-listed drain actions remain permitted |
| `rollback` | `v2_read_only` | Platform owner plus independent recovery approval | All runs terminal/interrupted; approvals/interactions resolved or fail-closed cancelled; mutation leases released; idempotency operations terminal; durable events/outbox reconciled; migrations/readiness pass; recovery evidence and a different reviewer/approver ID supplied |

Explicitly invalid transitions return `409 invalid_state`: `v1_only -> v2_active|rollback`, `v2_read_only ->` any mode not listed above, `v2_active -> v1_only|v2_read_only`, and `rollback -> v1_only|v2_active`. Recovery from rollback must pass through `v2_read_only`; returning to `v1_only` then additionally requires the zero-supervisor-resource guard.

Transition guards are evaluated from one locked cutover row plus transactionally consistent resource/lease/idempotency counts. A guard failure returns `409 transition_guard_failed` with safe reason codes and counts only; the client cannot override it. Internal worker completion, durable event append, evidence finalization, and fail-closed approval cancellation may finish in `rollback`. The only operator drain actions that may be emitted in rollback are `interrupt_run`, `release_run_writer`, a fail-closed `decide_approval`, and a fail-closed `respond_interaction`; no new assignment, dispatch, writer reacquisition, mission decision, retry, evidence-verification workflow, or other registry mutation may begin.

#### Exact conditional and idempotent cutover update

The following GET and PUT contracts are **prerequisites and are not implemented on the inspected primary branch**. `GET /api/admin/codex/v2/operations/cutover-mode` returns `200`, header `ETag: "cutover-<version>"`, and this exact data shape to an authorized platform owner:

```json
{
  "data": {
    "mode": "v1_only|v2_read_only|v2_active|rollback",
    "version": 7,
    "effective_at": "RFC3339",
    "mutation_authority": {
      "legacy_owned": "v1|read_only",
      "supervisor_owned": "v2|read_only|none",
      "allowed_drain_actions": ["interrupt_run", "release_run_writer"]
    },
    "allowed_transitions": [
      {
        "target_mode": "v2_active",
        "action": {
          "registry_version": "1.0",
          "action": "change_cutover_mode",
          "allowed": false,
          "reason_code": "activation_evidence_required",
          "reason": "Independent activation evidence is required.",
          "resource_version": 7,
          "risk_level": "high",
          "confirmation": {
            "kind": "typed",
            "phrase": "ACTIVATE V2",
            "consequences": ["Supervisor v2 becomes the writer for claimed resources."]
          },
          "idempotency_required": true,
          "expires_at": null
        }
      }
    ],
    "last_transition": {
      "audit_event_id": "sev_...",
      "request_id": "...",
      "from_mode": "v1_only",
      "to_mode": "v2_read_only",
      "changed": true,
      "occurred_at": "RFC3339"
    }
  },
  "meta": {"request_id": "...", "resource_version": 7}
}
```

`last_transition` is `null` before the first recorded transition. It is bounded, safe audit metadata, not authority. Every legal target is present in `allowed_transitions`; its descriptor may be `allowed=false` with a safe guard reason, while illegal edges are absent. Forbidden actors receive `403` without mode, version, transition, guard, or audit disclosure.

The update request is:

```http
PUT /api/admin/codex/v2/operations/cutover-mode
Authorization: Bearer <native application token>
X-Tenant: <resolved application tenant>
Idempotency-Key: <UUIDv4 retained for this logical transition>
If-Match: "cutover-<current_version>"
Content-Type: application/json
```

```json
{
  "target_mode": "v1_only|v2_read_only|v2_active|rollback",
  "expected_version": 7,
  "reason": "Bounded operator-authored reason",
  "evidence_ids": ["evd_..."],
  "independent_approver_id": null,
  "confirmation_phrase": null
}
```

- `expected_version` is required and must equal both the integer in `If-Match` and the locked current row. Header/body disagreement is `400 precondition_mismatch`.
- `reason` is required, trimmed, 1–1,000 characters, scrubbed before audit display, and never treated as authority.
- `evidence_ids` contains 0–20 authorized opaque supervisor evidence IDs. Activation and rollback recovery require the evidence described in the transition table.
- `independent_approver_id` is accepted only for `rollback -> v2_read_only`, must resolve server-side to an authorized actor distinct from the rollback initiator/recovery requester, and must have a durable signed recovery decision.
- `confirmation_phrase` is required only when the current `AllowedActionDescriptor.confirmation.kind` is `typed`; it is compared server-side and is not stored as evidence.

Success response:

Headers include `ETag: "cutover-<returned version>"`; an exact replay also includes `Idempotency-Replayed: true`. The initial changed/no-op response and every replay use the same status and safe body.

```json
{
  "data": {
    "previous_mode": "v2_read_only",
    "mode": "v2_active",
    "version": 8,
    "changed": true,
    "effective_at": "RFC3339",
    "actor": {"user_id": 42, "display_name": "Platform owner"},
    "audit_event_id": "sev_...",
    "evidence_ids": ["evd_..."],
    "mutation_authority": {
      "legacy_owned": "v1",
      "supervisor_owned": "v2",
      "allowed_drain_actions": []
    },
    "allowed_transitions": [
      {
        "target_mode": "rollback",
        "action": {
          "registry_version": "1.0",
          "action": "change_cutover_mode",
          "allowed": true,
          "reason_code": null,
          "reason": null,
          "resource_version": 8,
          "risk_level": "high",
          "confirmation": {
            "kind": "typed",
            "phrase": "ROLL BACK V2",
            "consequences": ["New supervisor mutations will stop."]
          },
          "idempotency_required": true,
          "expires_at": null
        }
      }
    ]
  },
  "meta": {
    "request_id": "...",
    "resource_version": 8,
    "idempotency_state": "succeeded|replayed"
  }
}
```

`allowed_transitions[].action` is the full typed `AllowedActionDescriptor`; every cutover target uses the single code `change_cutover_mode` plus its outer `target_mode`.

Exact errors:

| Status/code | Meaning |
|---|---|
| `400 precondition_mismatch` | `If-Match` and `expected_version` disagree or confirmation is malformed |
| `401 authentication_required` / `403 forbidden` | Actor is unauthenticated or is not an authorized platform owner |
| `409 invalid_state` | Requested edge is absent from the legal graph |
| `409 transition_guard_failed` | One or more named guards fail; safe `guard_codes` and counts returned |
| `409 idempotency_conflict` | Key was used with a different canonical fingerprint |
| `409 mutation_lease_conflict` | A conflicting v1/v2 mutation lease appeared before commit |
| `412 revision_conflict` | Locked cutover version differs from `If-Match`/`expected_version`; current safe mode/version returned |
| `428 precondition_required` | `If-Match` or `Idempotency-Key` is absent |
| `422 validation_failed` | Reason, evidence, approver, or required acknowledgement is invalid |
| `503 dependency_unavailable` | Required migration/readiness/evidence service cannot be verified; fail closed |

Every changed or no-op request appends immutable audit evidence containing: prior/target/result mode and version, actor ID, occurred time, reason digest plus scrubbed bounded display reason, authorized evidence IDs, independent approver/decision ID where required, request/correlation ID, idempotency-key digest (never the key), canonical request fingerprint, guard-result codes/counts, readiness/migration/deployed-commit identifiers, mutation-lease counts, active-run/approval/interaction counts, and the resulting mutation-authority summary. The state row, durable event, and idempotency terminal result commit atomically.

Unknown response outcomes follow section 15.2 exactly: replay this identical `PUT`, body, `If-Match`, and `Idempotency-Key`. A committed first request replays its original success even though the current version has advanced; a request that never reserved the key evaluates against the original precondition. The UI never issues a new key while the prior outcome is unresolved.

For cutover specifically, timeout changes the control to `Checking cutover outcome…`, freezes every transition control, and performs the section 15.2 0/1/3-second identical-request checks. `202` shows `Cutover transition still processing`, original request ID, and `Check again`; terminal replay refetches the GET contract and compares its ETag/mode/audit event to the replayed result. After checks are exhausted, `Outcome unresolved` offers only `Check again`, `Copy request ID`, `View current cutover state`, and the audit link. If a reload loses the in-memory key, the client must not synthesize or repeat the transition: it GETs current state, labels attribution `Needs audit confirmation`, and requires the operator to reconcile `last_transition`/audit evidence before a fresh descriptor and key can be used.

Contract tests cover every legal and illegal edge, same-mode no-op, two-operator race, stale/missing/mismatched preconditions, active runs, live approvals, mutation leases, unresolved idempotency, immediate rollback under degraded readiness, different-reviewer recovery, atomic audit evidence, response loss after commit, exact replay, and rollback-to-read-only recovery.

### 5.2 V2 route map

| Route | View |
|---|---|
| `/admin/coding-cockpit-v2` | Redirect to `/missions` after bootstrap |
| `/admin/coding-cockpit-v2/missions` | Mission Board |
| `/admin/coding-cockpit-v2/missions/:missionId` | Mission Overview |
| `/admin/coding-cockpit-v2/work` | Cross-mission work packages and briefs |
| `/admin/coding-cockpit-v2/missions/:missionId/work` | Mission work packages and dependencies |
| `/admin/coding-cockpit-v2/work/briefs/:briefId` | Brief Builder / immutable revision view |
| `/admin/coding-cockpit-v2/runs` | Cross-mission Runs |
| `/admin/coding-cockpit-v2/runs/:runId` | Run Detail |
| `/admin/coding-cockpit-v2/assurance?view=evidence` | Evidence Ledger subview |
| `/admin/coding-cockpit-v2/assurance?view=audits` | Audit Queue subview |
| `/admin/coding-cockpit-v2/assurance/audits/:auditId` | Audit Studio |
| `/admin/coding-cockpit-v2/context` | Cross-mission context index |
| `/admin/coding-cockpit-v2/context/missions/:missionId` | Project Brain |
| `/admin/coding-cockpit-v2/operations` | Operations overview |
| `/admin/coding-cockpit-v2/operations/:section` | Scoped platform operations |
| `/admin/coding-cockpit-v2/intake` | Intake queue |
| `/admin/coding-cockpit-v2/intake/:intakeId` | Intake detail and promotion |

Filters that should survive reload use query parameters (`status`, `risk`, `owner`, `q`, `cursor`). Selected durable entities use path parameters. Tenant identity, filesystem paths, secrets, and action state never enter the URL.

`Operations` and `Intake` are secondary destinations reached from the operator menu and attention inbox, not items in the persistent five-item mission navigation. Slice 1 renders only `Missions` and `Work`; future destinations are not shown as disabled roadmap clutter.

### 5.3 Cutover acceptance

Make v2 the implementation behind `/admin/coding-cockpit` only when:

1. P0 is integrated into the target branch.
2. Mission -> Brief -> Author Run -> Evidence -> Independent Audit -> Decision -> Checkpoint works through real APIs.
3. Required v2 browser, accessibility, isolation, restart, and zero-error gates pass.
4. Independent QA accepts the cutover.
5. V1 rollback is documented and server-controlled for one release window.

After the release window:

- remove production Demo Mode and fixture imports;
- remove the old embedded cockpit after reachability/parity review;
- decommission `codex-control-centre/frontend` after its useful behavior is extracted and verified;
- remove deprecated API aliases under a separately tested deprecation task.

### 5.4 Legacy link translation

Legacy bookmarks are translated at the route boundary; selected IDs are never silently discarded.

| Incoming link | Parallel phase | After v2 cutover |
|---|---|---|
| `/admin/coding-cockpit?thread={id}` | Open the authorized v1 thread view explicitly | Call prerequisite `GET /api/admin/codex/v2/legacy-links/threads/{id}`. `mapped` redirects to the linked v2 run; `legacy_only` opens an authorized read-only legacy-history route; unauthorized/unknown returns the same non-leaking 404 state |
| `?tab=workbench&thread={id}` | Normalize to the explicit v1 thread view | Apply the thread mapping above |
| `?tab=health|skills|plugins` | Open the existing authorized v1 tool while v1 is enabled | Translate to the matching capability-gated Operations section |
| `?tab=issues` | Open the v1 issue view during parallel operation | Translate to Intake only when a durable authorized intake record exists; otherwise show a non-leaking explanatory state |
| `?tab=fuzzer|stream` | Keep in v1 only while explicitly authorized | No automatic v2 equivalent; show that the legacy tool was retired and link to authorized Operations diagnostics where applicable |
| `/admin/resident-agent` | Existing v1 redirect | Translate to authorized Intake/Operations landing according to server capability |
| `/admin/coding-studio` | Existing explicit v1 workbench redirect | Apply the thread mapping if present; otherwise open Runs |
| support launch returning `thread_id` | Open acknowledged v1 thread until the support adapter is upgraded | Support adapter returns a durable supervisor `run_id`; old thread IDs use the mapping endpoint |

The mapping response is actor-scoped and contains only `state: mapped|legacy_only|not_found`, an authorized target kind/opaque ID, and a safe message. It never reveals cross-scope existence. Tests cover authorized mapping, known ID without lineage, unauthorized ID, deleted/missing ID, stale bookmark, and support-launch transition.

## 6. Information architecture

The persistent primary navigation has five mission-first groups. A selected mission remains visible in the shell so movement between groups does not lose context.

### 6.1 Missions

Purpose: answer what is active, blocked, awaiting assurance, or waiting on the operator.

Contains:

- Mission Board with server-provided counts;
- searchable/filterable missions;
- status, risk, owner, last checkpoint, next action, and staleness;
- Mission Overview with current work, runs, assurance, and context summaries;
- create mission when allowed.

### 6.2 Work

Purpose: define, sequence, and approve the exact work contract an agent will receive.

Contains:

- work packages and dependency relationships;
- cross-mission work queue as a route-backed filter, not another primary destination;
- brief revision history and immutable approved revisions;
- structured Brief Builder;
- validation, conflict resolution, approval provenance, and create-next-revision action.

### 6.3 Runs

Purpose: monitor real author and auditor execution with bounded controls.

Contains:

- run queue and attention states;
- assignment role, model, limits, logical workspace/branch, baseline/result commits;
- activity timeline, approvals/input, steer/interrupt, diff, output, and captured evidence;
- retry lineage without resetting history.

### 6.4 Assurance

Purpose: show what proves the result and independently decide whether it satisfies the approved brief.

Route-backed subviews:

- **Evidence:** append-only ledger filtered by mission, package, criterion, run, commit, kind, result, and verification state;
- **Audits:** queue, approved brief, submitted commit, criterion matrix, evidence links, and reviewer independence;
- **Decisions:** accept, request rework, escalate, or fail-audit actions as server allowed.

Evidence and Audit remain distinct resources and views, but not separate global navigation items.

### 6.5 Context

Purpose: preserve compact durable project understanding across restarts and context-window changes.

Contains:

- mission objective/current synopsis;
- decisions, invariants, assumptions, risks, blockers, known issues, and limitations;
- checkpoint history, source categories, omitted categories, context budget, and next action;
- server-generated checkpoint and mark-current actions.

### 6.6 Secondary destinations

**Operations** is reached from the platform-owner menu or an operational attention item. It houses only justified real capabilities: worker/service readiness, actionable approvals and operator-input requests, repository boundaries, telemetry, models, Skills RAG, plugins, and event connection diagnostics. Worktree deletion, boundary mutation, plugin installation, and telemetry changes use separate confirmations. Model, Skills RAG, worker/service, and event-connection surfaces are read-only diagnostics in this specification; adding configuration mutations for them requires an action-registry version bump. Stress fuzzing and raw event feeds are not primary navigation.

**Intake** is reached from the attention inbox, support source, or `Create from intake` action. It converts real support tickets, resident findings, or operator observations into proposed work without treating them as evidence. Intake shows source, severity, recency, ownership, triage status, scrubbed summary, duplicate/defer/decline options, and promotion to mission/work package. Promotion never silently dispatches an agent.

## 7. Application shell and responsive model

### 7.1 Desktop

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Product header: Codex Supervisor | project | connection | operator          │
├───────────────┬──────────────────────────────────────────────┬───────────────┤
│ Primary nav   │ Main route                                  │ Context panel │
│ Missions      │ One page title + one dominant workflow      │ selection,    │
│ Work          │                                              │ provenance,   │
│ Runs          │                                              │ allowed       │
│ Assurance     │                                              │ actions       │
│ Context       │                                              │               │
└───────────────┴──────────────────────────────────────────────┴───────────────┘
```

- Navigation width is fixed and not user-resizable in the first release.
- The context panel appears only when it materially aids the route; otherwise the main content uses the space.
- There is no global terminal dock or global inspector.
- Run output, diffs, evidence, and approvals live inside Run Detail or Audit Studio.
- Operations and Intake appear only in the operator menu or attention inbox when capability-gated; they do not occupy persistent primary navigation.

### 7.2 Tablet

- Primary navigation becomes a labelled drawer.
- Context becomes an accessible right sheet.
- Audit panes become route-local tabs with an always-visible unsaved indicator.

### 7.3 Mobile and 320 CSS pixels

- One pane at a time: list -> detail -> action/editor.
- Tables become labelled cards; the page never scrolls horizontally.
- Sticky action bars respect `env(safe-area-inset-bottom)`.
- Wide diff/output content scrolls inside a labelled region.
- Essential status, provenance, and disabled reasons remain visible without hover.
- Run timelines use a bounded virtualized/cursor-backed list, stable item IDs, preserved scroll anchor, and a visible `new activity` affordance rather than forcing the viewport to jump.
- Touch controls provide at least a 44 by 44 CSS-pixel hit area with spacing; swipe, long-press, drag, and hover are never the sole path to an action.
- A narrow screen keeps the connection/authority state and the one current primary action reachable while moving secondary metadata into labelled disclosure regions.
- Installability is not offline authority: PWA/service-worker caching and notifications remain deferred by section 15.9.

## 8. Low-fidelity layouts

### 8.1 Mission Board

```text
[Missions]                           [Live paused?] [Create mission]
[Active 4] [Blocked 1] [Audit 2] [Human decision 1]
[Search................] [Status v] [Risk v] [Owner v] [Sort v]

Mission                 Status      Next safe action       Risk   Updated
Supervisor UI v2        Briefing    Approve revision 2     Med    12 min
Worker recovery         Blocked     Resolve DB decision    High   1 h

[pagination / cursor]
```

Empty: one explanation and `Create mission` only when capable. No sample cards.

### 8.2 Mission Overview

```text
[Back] Mission title                      [status] [risk] [primary action]
Objective and scope
Baseline commit | owner | policy | latest checkpoint

[Work progress] [Active/attention runs] [Open decisions] [Open risks]

Work packages
- WP-01 Brief approved -> author ready
- WP-02 Blocked by WP-01

Recent evidence | latest audit | checkpoint synopsis
```

The primary action comes from `allowed_actions`, never from a client-side role/status table.

### 8.3 Brief Builder

```text
[Mission / Work package]  Revision 2 DRAFT  [Unsaved changes]
[Revision history]                           [Validate] [Approve revision]

1 Objective + problem statement
2 In scope / out of scope
3 Changed-file allowlist
4 Architecture + security invariants
5 Acceptance criteria + required evidence
6 Verification commands
7 Documentation obligations
8 Prohibited actions
9 Dependencies / assumptions / questions
10 Delivery report requirements

[inline error summary linked to fields]
```

Approved view is read-only. `Create revision 3` is the only edit path.

### 8.4 Run list and detail

```text
Runs [All] [Queued] [Active] [Author] [Audit] [Attention]
Role   Work package   Queue/ack state   Agent/profile   Branch   Heartbeat

Run detail
[identity + real worker/queue state + limits]              [Steer] [Interrupt]
[Search eligible agent/model...] [capability/availability/restriction summary]
[Activity] [Approvals/Input] [Changes] [Output] [Evidence]
Activity: [older history] [live boundary] [new activity marker]
grouped bounded timeline / truthful connection and recovery state
```

Recorded database state and live worker actionability are shown separately. `queued`, `awaiting_writer`, `dispatching`, `worker_acknowledged`, `running`, `stopping`, and terminal outcomes are not collapsed. The picker is server-filtered and capability-aware; an unavailable, forbidden, incompatible, or independence-conflicting choice stays distinguishable through a safe reason. On narrow screens the queue/list, selected run, and action/detail view are separate route states so Back restores the prior filter and scroll position.

### 8.5 Assurance — Evidence Ledger

```text
Evidence [mission] [package] [criterion] [kind] [state] [commit]
Kind        Result      Commit    Source run    Verified by    Captured
Browser     Passed      1a2b3c    run_17        run_22         14:03

Selected evidence
summary | exact safe command label | exit code | environment | digest
criterion links | rejection reason | artifact reference
```

There is no browser control to create machine-passed evidence manually.

### 8.6 Assurance — Audit Studio

```text
Audit: WP-01     Submitted 1a2b3c     Independent: YES
┌────────────────────┬────────────────────────┬────────────────────┐
│ Approved brief     │ Criterion matrix       │ Evidence / diff    │
│ scope/invariants   │ AC-01 verified         │ linked artifact    │
│ acceptance rules   │ AC-02 failed           │ provenance         │
└────────────────────┴────────────────────────┴────────────────────┘
[Request rework] [Escalate] [Accept implementation]
```

Acceptance remains disabled with a visible server reason until all invariants hold.

### 8.7 Context — Project Brain

```text
Project Brain                     [Create checkpoint]
Current synopsis | baseline | submitted commit | context budget
[Decisions] [Invariants] [Risks] [Blockers] [Known debt]

Latest checkpoint #18
Sources included | categories excluded | next action
[View immutable checkpoint] [Mark current]
```

### 8.8 Secondary — Operations

```text
Operations [Platform owner]
Readiness: API | database migration | workers | event stream | evidence storage
Attention: 2 approvals | 1 input request | 1 unavailable worker
[Approvals] [Boundaries] [Telemetry] [Models] [Skills] [Plugins]
```

### 8.9 Secondary — Intake

```text
Intake [Open] [Deferred] [Promoted] [Declined]
Source         Summary             Severity   Duplicate?   Updated
Support #142   worker timeout      High       no           8 min

Detail: scrubbed context + provenance
[Promote to mission/work package] [Defer] [Decline]
```

## 9. Primary workflows

### 9.1 Start and approve work

1. Bootstrap authenticates the platform owner and returns capabilities, active project, counts, feature availability, server time, and migration/readiness state.
2. Operator creates or opens a mission.
3. Operator creates a work package.
4. Server creates a draft brief revision and returns its ID/revision.
5. Operator edits structured sections. Debounced saves update only after server acknowledgement.
6. Validate returns field and criterion errors without approving.
7. Approve requires confirmation, expected revision, and server validation.
8. The revision becomes immutable; the work package becomes ready only if the server commits that transition.

### 9.2 Dispatch author

1. Open an approved work package.
2. Review immutable brief, baseline, allowlist, limits, tool profile, conflicts, and required evidence.
3. Submit `Dispatch author agent` with an idempotency key and expected revision.
4. Keep the prior confirmed status visible while pending.
5. Success requires a durable assignment/run ID and real worker acknowledgement semantics.
6. Unknown network outcome replays the identical request with the same idempotency key under section 15.2; it never creates a local run or a new key.

### 9.3 Supervise a run

1. Load durable run snapshot before connecting to events.
2. Mint a one-use event ticket and connect.
3. Apply events only when schema, entity, and sequence are valid.
4. On gap/reconnect/unknown event, refetch the snapshot.
5. Resolve approvals or requested input only when the server says the request is still live/actionable.
6. Interrupt and retry are explicit server actions; retry creates lineage.
7. If and only if the section 15.7 spike is approved, an optional active-run projection may attach after the durable snapshot; it remains separate from passive ticketed SSE and never dispatches, mutates, or authorizes the run.

### 9.4 Collect evidence

1. Backend captures command/test/build/browser/docs/diff evidence against the run commit.
2. UI lists captured state while verification is pending.
3. Independent verifier marks evidence verified or rejected; rejected records remain immutable.
4. Required criterion coverage is calculated by the server and displayed by the UI.

### 9.5 Conduct independent audit

1. Server creates a reviewer assignment distinct from the author.
2. Auditor receives the exact approved brief, submission commit, diff, evidence, and relevant brain items—not author hidden reasoning.
3. Audit Studio records one verdict per criterion with evidence references and residual risk.
4. Submit validates matrix completeness.
5. Server permits accept, rework, or human-decision outcomes according to policy and risk.

### 9.6 Rework

1. `Request rework` requires actionable findings.
2. The prior brief, author run, evidence, and audit stay immutable.
3. A new cycle and, if needed, new brief revision are created.
4. Mission Overview shows the lineage rather than overwriting history.

### 9.7 Resume after restart or context compaction

1. Bootstrap reports interrupted/orphaned run state truthfully.
2. Mission opens with latest durable checkpoint and subsequent events.
3. Operator reviews next actions and omissions.
4. A new run receives a bounded context pack derived from the approved brief and selected durable memory.

## 10. Component and data ownership

### 10.1 Proposed package boundary

```text
frontend/src/pages/admin/codex-supervisor/
├── CodexSupervisorPage.tsx          # route outlet + top-level boundaries
├── routes.tsx                       # v2 route definitions
├── api/
│   ├── supervisorClient.ts          # authenticated /api/admin/codex/v2 transport
│   ├── supervisorTypes.ts           # generated/strict DTOs; no any
│   └── supervisorEvents.ts          # ticketed stream + schema validation
├── shell/
│   ├── SupervisorShell.tsx
│   ├── PrimaryNavigation.tsx
│   ├── ProjectContext.tsx
│   └── ConnectionStatus.tsx
├── missions/
├── briefs/
├── runs/
├── evidence/
├── audits/
├── brain/
├── operations/
├── intake/
└── shared/
    ├── AllowedActionButton.tsx
    ├── EntityState.tsx
    ├── Provenance.tsx
    ├── RevisionConflictDialog.tsx
    └── AsyncAnnouncement.tsx
```

### 10.2 State boundaries

| Layer | Owns | Must not own |
|---|---|---|
| V2 API client | auth headers, request IDs, ETags/revisions, idempotency, structured errors, abort | component state, synthetic defaults |
| Server-query cache | snapshots keyed by entity and revision, freshness, invalidation | unsaved forms, lifecycle inference |
| Router | selected destination/entity and shareable filters | tenant identity, secrets, pending action state |
| Form controller | local dirty buffer, field errors, save state | approved revision mutation, authoritative status |
| Event client | ticket, connection state, sequence, invalidation | durable entity truth, evidence verdicts |
| Components | rendering and local disclosure state | permissions or state-machine rules |

Use the server's `allowed_actions` and bootstrap capabilities. Client checks improve presentation only.

### 10.3 Chosen query, test, and dialog foundations

The current frontend has React 19, React Router 7, Tailwind 4, and the bundled `radix-ui` package. It does not currently have a server-query library, a DOM component-test runner, Testing Library, axe integration, or a shared `AlertDialog` wrapper. The following are approved **future WP-UI-02 dependency additions**; this specification task does not install them.

#### Server state

- Add `@tanstack/react-query` v5 as the sole supervisor server-query/cache library.
- One application-level `QueryClientProvider` owns the client. Supervisor feature modules define query-key factories by resource ID, filter, and server revision.
- Query functions receive TanStack's `AbortSignal` and pass it to the typed fetch client. Superseded route requests are cancelled; response application still verifies entity ID/version to suppress late stale data.
- Mutations do not optimistically alter lifecycle state. On acknowledgement they invalidate the exact resource/query families named by the response.
- Query cache contains server-safe DTOs only. Raw output/artifact bodies are not persisted, dehydrated, or written to browser storage.

#### Rendered component and accessibility tests

- Add Vitest with `jsdom` as the rendered-component runner.
- Add `@testing-library/react`, `@testing-library/user-event`, and `@testing-library/jest-dom`.
- Add `axe-core` with `vitest-axe` for component-level automated rules; live browser routes additionally use the repository-approved axe/Playwright path because jsdom cannot validate computed layout, contrast, or real browser focus behavior completely.
- Component tests use `*.component.test.tsx`; the existing Node contract tests remain `*.test.ts`.
- Add `frontend/vitest.config.ts` and `frontend/src/test/setup.ts`. Scripts become `test:contracts` for the existing Node tests, `test:components` for `vitest run`, and `test` runs both. Exact resolved versions are locked and verified against React 19/TypeScript 6 in the implementation task.

#### Shared destructive confirmation

- Create `frontend/src/components/ui/alert-dialog.tsx`, shared application-wide, using `AlertDialog as AlertDialogPrimitive` from the already-installed `radix-ui` bundle, plus the existing shared `Button` and `cn` utilities.
- Export Root, Trigger, Portal, Overlay, Content, Header, Footer, Title, Description, Cancel, and Action wrappers. Do not create a supervisor-local fork and do not use the ordinary `Dialog` for destructive confirmation.
- `AlertDialogContent` requires a programmatic title and description. Cancel receives initial focus unless an explicitly documented safer control exists. Close restores focus to the trigger. Escape behavior, focus trapping, and labelling remain Radix-owned.
- Focused component tests verify title/description association, keyboard-only open/cancel/action, non-destructive initial focus, Escape behavior, focus return, disabled committing state, and consequence text.

WP-UI-02's exact allowlist must include `frontend/package.json`, `frontend/package-lock.json`, `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`, `frontend/src/components/ui/alert-dialog.tsx`, its focused component test, the root Query provider integration, and the new supervisor package files. These dependencies must not be added in a backend-only work package.

This approval does not include AG-UI, CopilotKit, Assistant UI, Open WebUI, or any related runtime/cloud/adapter package. Those packages are forbidden from WP-UI-02 and WP-UI-03 and from the native shell/query/event path. Only the separately approved comparative spike in sections 15.7 and 15.10 may add its exact-pinned candidate dependencies in an isolated allowlist. Open WebUI remains reference-only and has no eligible dependency arm.

### 10.4 Legacy extraction candidates

Only these behaviors are candidates for extraction after decoupling and tests:

- normalized activity renderers for bounded worker events;
- approval and user-input form interaction patterns;
- diff parser/viewer internals;
- collapsible run-output presentation;
- model catalogue presentation;
- Skills RAG search/read presentation.

Do not reuse the containing screens, state store, navigation, local primitives, demo fixtures, event fallback, or inferred view models.

## 11. Role and platform-owner behavior

### 11.1 Development-phase rule

Until tenant/user ownership is implemented and negative isolation tests pass, the entire v2 surface is platform-owner-only. `owner`, `admin`, or `manager` within an ordinary tenant is not sufficient.

Bootstrap behavior:

- `401`: application authentication flow; no v2 data requests continue.
- `403 can_view_supervisor=false`: render a compact forbidden page; omit navigation and background queries.
- dependency/migration unavailable: render read-only readiness state; do not fall back to v1 data or fixtures.

### 11.2 Future programme roles

When the durable ownership model exists:

| Role | Core capabilities |
|---|---|
| Owner | policy, membership, archive, final high-risk decision |
| Supervisor | brief approval, assignment, dispatch, rebrief, checkpoints |
| Author | assigned run and evidence submission only |
| Reviewer | independent audit and evidence verification only |
| Observer | permitted read-only history |

The backend resolves memberships and returns capabilities. The UI never derives authority from a displayed role string.

The future role table describes authorization intent, not additional registry `1.0` mutations. Membership/policy administration is deliberately absent from this foundation UI; adding it requires a reviewed action-registry version bump and exact endpoint/permission rows before any control appears.

### 11.3 Provenance

Material records display safe provenance: actor display name, time, source run, revision, and commit where relevant. Never expose email, access token, raw identity claims, unrestricted host path, hidden model reasoning, or customer content.

## 12. Complete state contract

Every destination and material action implements the states below.

### 12.1 Loading and refreshing

- Initial load uses a structure-matching skeleton and preserves a programmatic page title.
- Background refresh keeps confirmed content visible with a quiet freshness indicator.
- Route changes abort stale list/detail requests.
- A slow mutation disables only conflicting actions and uses the explicit pending verb.

### 12.2 Empty

- Missions: explain the workflow; show `Create mission` only when allowed.
- Briefs: explain that a mission/work package is required and link to the allowed next step.
- Runs: explain that an approved brief and assignment are required.
- Evidence: say `No evidence captured`; separately show required evidence kinds.
- Audit: explain author completion and evidence prerequisites.
- Brain: say no decisions/risks/checkpoints recorded; never claim “all clear”.
- Operations: an empty approval queue means no pending approvals, not that workers are healthy.
- Intake: distinguish no open intake from source unavailable.

Each empty state has at most one primary next action.

### 12.3 Errors

- Inline error beside the action or field, plus request ID when supplied.
- `401`: end v2 requests and enter application auth recovery.
- `403`: preserve permitted read-only content; show server reason.
- `404`: contextual missing/unauthorized state without leaking existence.
- `409 revision_conflict`: preserve local buffer and open compare/refresh dialog.
- `409 invalid_state`: refetch resource and explain the confirmed current state.
- `409 idempotency_conflict`: block; never generate a new key silently.
- `422`: field/criterion summary; focus first invalid field.
- `429`: show retry guidance from server; no aggressive polling.
- `503`: show unavailable/readiness reason and retry; no synthetic mode.
- unknown enum/event: warning, safe raw value, refetch, no mutating action.

Toasts are supplementary. Durable errors remain visible in context.

### 12.4 Dirty buffers and recovery

Brief Builder and Audit Studio use one shared dirty-buffer policy:

- The local buffer is memory-only in the first release. It is never written to `localStorage`, `sessionStorage`, IndexedDB, URL state, logs, telemetry, or the query cache. The latest acknowledged server revision is the crash/reload recovery point.
- A buffer is dirty when its canonical form differs from the last acknowledged server representation. Debounce does not clear dirty state; only a successful matching save does.
- In-app route changes, mission switches, Back/Forward navigation, and logout invoke the shared route blocker. Its AlertDialog states the resource and unsaved sections and offers `Stay`, `Copy unsaved text`, and `Discard and leave`. Initial focus is `Stay`.
- Browser reload/tab close installs `beforeunload` only while dirty. Browser-native wording is accepted; the UI does not claim recovery after a hard close.
- Going offline pauses autosave, keeps the buffer in memory, shows `Unsaved — offline`, blocks approval/submission, and exposes Retry/Copy. Returning online does not overwrite; it first refetches the server version.
- Session expiry freezes the buffer, blocks mutation, and offers `Copy unsaved text` plus the application re-authentication path. If authentication is restored without unload, Retry reuses the same resource version/idempotency contract. Logout/discard clears the buffer.
- A revision conflict opens a field/section comparison of local buffer versus current server record. The operator may copy, discard to server, or explicitly rebase selected local fields onto the new server revision. Rebase creates a new canonical body and new idempotency key; it is never automatic.
- Audit criteria, rationale, and evidence links follow the same policy. Leaving one dirty criterion cannot silently discard another.
- Copy is a deliberate clipboard action and includes a reminder that briefs/audits must not contain secrets or customer data. Clipboard success/failure is announced without logging content.

Component/browser tests cover keyboard focus in the route guard, Stay/Copy/Discard, Back/Forward, dirty logout, session expiry, offline/online conflict, approval while dirty, and hard-reload warning registration.

### 12.5 Offline, SSE loss, and reconnect

- The connection state is a closed presentation union: `current`, `stale`, `disconnected`, `reconnecting`, `exhausted`, or `auth_failed`. It always shows the last confirmed sequence and absolute time where a run/event cursor exists.
- Browser offline: persistent `Offline — confirmed data may be stale`; block mutations. Unsaved input remains explicitly local and editable but never appears queued, sent, approved, or accepted.
- SSE loss: `Live updates paused`; REST content remains with last-confirmed timestamp. Any action requiring current authority is disabled until an authoritative refetch returns a fresh descriptor.
- Reconnect uses bounded exponential backoff, mints a fresh one-use ticket for every attempt, and resumes after the last durable sequence. The UI announces the first loss, recovery, and terminal exhaustion without flooding a live region.
- Sequence gap, lower unseen sequence, invalid/unknown event, or replay miss stops event application and triggers snapshot refetch before accepting later events.
- After retry exhaustion, show manual Retry and continue REST-only reads. Authentication failure stops retries and exposes only the application reauthentication path; worker/dependency unavailability remains distinct from authentication, authorization, timeout, conflict, and unknown mutation outcome.
- Never place bearer tokens in URLs or reuse consumed tickets.

### 12.6 Approval and operator input

- Show recorded status and `live_actionable` separately.
- Pending request includes run, tool/action, consequence, risk, expiry, and safe command digest/summary.
- Approve/deny uses explicit buttons and one confirmation for high-risk actions.
- Expired, resolved, disconnected, or restart-orphaned requests are disabled with reason.
- Duplicate decisions return the durable prior result or a conflict; the UI never claims a second success.

### 12.7 Destructive and irreversible actions

Use the application's accessible `AlertDialog` primitive for:

- cancelling a mission/work package;
- interrupting an active run when work may be lost;
- deleting/removing a worktree or boundary;
- accepting high/critical residual risk;
- plugin installation or settings changes with host impact;
- archival where restoration semantics are limited.

The dialog names the target, effect, recoverability, and affected run/worktree. Initial focus is non-destructive. Typed confirmation is required only where risk warrants it. There is no browser-exposed force deletion in normal workflows.

### 12.8 Mutation truth table

```text
idle -> submitting -> server-confirmed success -> refetch/reconcile
                  \-> validation/conflict/error -> keep prior confirmed state + local buffer
                  \-> unknown network outcome -> replay identical request/key
                                             -> in_progress | confirmed result | unresolved
```

No lifecycle status is optimistically advanced.

## 13. Accessibility, keyboard, and focus

Target WCAG 2.2 AA and verify with automated and manual tests.

### 13.1 Structure

- One `main` landmark per page.
- Labelled primary `nav`; contextual `aside` only when present.
- One visible `h1`, logical `h2`/`h3` hierarchy, no skipped levels caused by card styling.
- Page title reflects destination and selected entity.
- Status always has text/icon; color is never the sole signal.

### 13.2 Keyboard

- All actions are native buttons/links/inputs or project-standard accessible primitives.
- Tab order follows visual/read order.
- Enter/Space activate buttons; Escape closes non-committing dialogs/sheets.
- No global shortcut fires while typing unless it is the documented Escape behavior.
- Lists/tables do not invent grid keyboard behavior unless implemented with a tested accessible grid primitive.
- Any retained resizer is a focusable separator with name, orientation, min/max/current values, and Arrow-key support. Prefer fixed layout where resizing is unnecessary.

### 13.3 Focus

- Visible high-contrast focus indicators are never removed.
- Opening a dialog/sheet moves focus to its heading or safe first field.
- Closing returns focus to the trigger.
- Route navigation focuses the new `h1`; background refresh does not steal focus.
- Validation focuses the error summary, whose links move to fields.
- Adding/removing repeated criteria announces the change and places focus predictably.
- While a mutation is committing, prevent duplicate submit without trapping the user.

### 13.4 Forms and dynamic updates

- Every field has a persistent label and programmatic description/error relation.
- Required state is exposed semantically.
- Paste is never blocked.
- Autosave status uses a polite live region; dispatch, approval, and audit failures use `role="alert"`.
- Relative times have an accessible absolute timestamp.
- Progress uses text and `aria-valuenow/min/max` where determinate.

### 13.5 Responsive and visual access

- Core workflows reflow at 320 CSS pixels without page-level horizontal scroll.
- Content remains usable at 200% zoom.
- Touch targets are at least 44x44 CSS pixels on touch layouts.
- Text and UI contrast meet WCAG AA; focus indicators meet non-text contrast.
- Reduced-motion preference disables non-essential movement.
- A manual screen-reader pass covers Mission -> Brief approval and Run -> Approval -> Audit decision.

## 14. Visual baseline

### 14.1 Color and surface

- Use existing FastAPI Bookings semantic tokens before adding any token.
- One accent color per view; reserve semantic success/warning/error colors for state.
- No gradients.
- No glow effects.
- No full-screen blur/backdrop effects.
- Dark and light modes must both pass contrast gates if both remain supported by the application.

### 14.2 Typography and density

- Use the application's existing font stack and type scale.
- Headings use balanced wrapping; body text uses readable wrapping.
- IDs, counts, durations, commits, and timestamps use tabular numerals/monospace only where useful.
- Avoid 9–11px text for operational information.
- Dense tables may truncate with an accessible full-value mechanism.

### 14.3 Layout and elevation

- Use shared spacing and shadow scales; no arbitrary z-index values.
- Prefer borders, grouping, and whitespace over nested cards.
- Each view has one dominant action and one clear reading order.
- Fixed elements respect safe-area insets.
- Use `min-h-dvh`/application shell constraints, never `h-screen`.

### 14.4 Motion

- Add no decorative animation.
- Interaction feedback stays at or below 200ms and uses transform/opacity only.
- No perpetual pulse/ping for normal connected/running states.
- Long-running activity uses text, progress, or a restrained spinner with accessible label.

## 15. V2 facade contract

`/api/admin/codex/v2` is the one canonical UI namespace. Slice 0 records this in an ADR and OpenAPI, deprecates the earlier `/api/admin/codex/supervisor` proposal, and fixes `Mission` as the API/UI term mapped internally to `supervisor_programme`. No alias is shipped. Telemetry uses `mission_id` externally and may retain the database table name only in repository-layer spans.

### 15.1 Envelope and concurrency

Success:

```json
{"data": {}, "meta": {"request_id": "...", "resource_version": 3}}
```

Error:

```json
{
  "error": {
    "code": "revision_conflict",
    "message": "The brief changed after you opened it.",
    "request_id": "...",
    "details": {"current_version": 4}
  }
}
```

- Mutations use `Idempotency-Key` where replay could duplicate records/actions.
- Mutable aggregates use `If-Match` or an explicit expected version, consistently documented.
- The facade returns capabilities and `allowed_actions`; it never accepts tenant/user IDs as authority.
- TypeScript DTOs are generated from or conformance-tested against OpenAPI and contain no `any`.

### 15.2 Exact idempotency and unknown-outcome contract

Idempotency is mandatory for every create, action/transition, approval, dispatch, retry, claim, checkpoint, and destructive mutation, and for PATCH saves where a dropped response could make the client repeat a logical edit.

#### Key and request identity

- The client generates one UUIDv4 `Idempotency-Key` when the operator begins one logical submission. It retains that key in the in-memory pending-mutation record until the outcome is terminal.
- Retries send the identical HTTP method, normalized route, canonical JSON body, authenticated actor, project/mission scope, and expected resource version with the same key.
- The server fingerprints `actor_id + tenant_id + method + normalized_path + canonical_json_sha256 + expected_resource_version`. Headers containing credentials are never fingerprinted or stored.
- A key is scoped to the authenticated actor and normalized route, stored for 24 hours after terminal completion, and never accepted across actors/tenants.

#### Server states and replay

| Stored state | Same key + same fingerprint | Same key + different fingerprint |
|---|---|---|
| `in_progress` | `202` with `operation_state: in_progress`, original request ID, `Retry-After`, and no invented resource | `409 idempotency_conflict` |
| `succeeded` | Replay the original status, safe response body, resource IDs/version, and header `Idempotency-Replayed: true` | `409 idempotency_conflict` |
| `failed` | Replay the original terminal safe error/status and `Idempotency-Replayed: true` | `409 idempotency_conflict` |
| expired/missing | Process as a new request only if no matching durable operation/resource exists; server-side uniqueness/state checks still prevent duplication | normal validation/conflict rules |

The server reserves the key and fingerprint transactionally before the first side effect. Terminal success/error and resource IDs commit in the same transaction as the state transition where possible; asynchronous dispatch stores the durable assignment/run IDs before returning `202`. A confirmed terminal failure requires a new operator action and new key for a new attempt. An unresolved/in-progress operation never permits `Start new attempt`.

#### Unknown-outcome UX

1. A timeout or connection loss after submission changes the button to `Checking outcome…`; it does not revert to idle or advance state.
2. The client replays the exact request/key after `Retry-After`, with at most three automatic checks using 0/1/3-second waits.
3. `202 in_progress` shows the original request ID and keeps conflicting controls disabled. Manual `Check again` replays the same request/key.
4. A replayed terminal response reconciles by returned resource ID/version and refetches the authoritative snapshot.
5. After automatic checks are exhausted, show `Outcome unresolved` with `Check again`, `Copy request ID`, and `Return to read-only view`. Do not offer a new attempt while unresolved.
6. `409 idempotency_conflict` is a blocking integrity error; preserve the buffer, show the request ID, and do not silently create a key.

Tests inject a network drop before the first response, concurrent identical retries, retry after server commit, retry while in progress, different-body reuse, actor/scope reuse, terminal failure followed by an explicitly new attempt, and retention expiry. Every case proves at most one durable side effect.

### 15.3 Typed capabilities and allowed actions

Bootstrap capabilities are a closed typed object. Per-resource actions use this exact descriptor:

```ts
export type ActionCode =
  | 'change_cutover_mode' | 'claim_project'
  | 'create_mission' | 'edit_mission' | 'activate_mission' | 'pause_mission'
  | 'resume_mission' | 'complete_mission' | 'cancel_mission' | 'archive_mission'
  | 'create_work_package' | 'edit_work_package' | 'add_work_dependency'
  | 'remove_work_dependency' | 'block_work_package' | 'unblock_work_package'
  | 'cancel_work_package' | 'rebrief_work_package'
  | 'create_brief_revision' | 'edit_brief_revision' | 'validate_brief'
  | 'submit_brief_for_approval' | 'approve_brief' | 'reject_brief' | 'withdraw_brief'
  | 'assign_author' | 'assign_reviewer' | 'dispatch_assignment'
  | 'withdraw_queued_assignment'
  | 'steer_run' | 'interrupt_run' | 'retry_run'
  | 'release_run_writer' | 'reacquire_run_writer' | 'restart_worker'
  | 'decide_approval' | 'respond_interaction'
  | 'link_evidence' | 'verify_evidence' | 'reject_evidence'
  | 'create_audit' | 'edit_audit_matrix' | 'submit_audit' | 'accept_implementation'
  | 'request_rework' | 'require_human_decision' | 'record_human_decision' | 'fail_audit'
  | 'create_decision' | 'edit_decision' | 'accept_decision' | 'reject_decision'
  | 'supersede_decision'
  | 'create_risk' | 'edit_risk' | 'mitigate_risk' | 'accept_risk'
  | 'materialize_risk' | 'close_risk'
  | 'create_checkpoint' | 'mark_checkpoint_current'
  | 'add_workspace_boundary' | 'remove_workspace_boundary'
  | 'update_telemetry_settings' | 'test_telemetry_connection'
  | 'install_plugin' | 'remove_worktree'
  | 'create_intake' | 'promote_intake' | 'defer_intake'
  | 'decline_intake' | 'mark_intake_duplicate'

export interface AllowedActionDescriptor {
  registry_version: '1.0'
  action: ActionCode
  allowed: boolean
  reason_code: string | null
  reason: string | null          // bounded, server-safe operator text
  resource_version: number
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  confirmation: {
    kind: 'none' | 'dialog' | 'typed'
    phrase?: string
    consequences: string[]       // max 5, each server-bounded
  }
  idempotency_required: boolean
  expires_at: string | null
}
```

- Bootstrap returns `action_registry_version: '1.0'`. Every descriptor repeats that version so cached resources from another registry revision are rejected rather than guessed.
- Action arrays contain at most one descriptor per `action` and are bound to the resource version returned in the same response.
- An unknown action or reason code is displayed in diagnostics and remains non-actionable.
- A descriptor is stale when the resource version changes or `expires_at` passes. The UI disables it and refetches before action.
- `allowed=false` may be rendered with the safe reason when showing the disabled workflow helps the operator. It is never treated as evidence that the resource exists outside scope.
- The mutation includes the expected `resource_version`; high-value actions also include the current descriptor action name and idempotency key.
- Descriptors are presentation hints, not bearer capabilities. The server re-authenticates, re-authorizes, revalidates state/risk/evidence, and recomputes permission in the mutation transaction.

Tests cover stale descriptors, expired actions, unknown actions, safe disabled-reason rendering, version races, and a direct request that ignores the descriptor.

#### Exhaustive operator mutation registry v1.0

All paths below are relative to `/api/admin/codex/v2`. `Version owner` identifies the resource whose descriptor/version must be submitted. `Idem` means `Idempotency-Key` is mandatory. Risk is a floor; the server may raise it from current state. Every listed endpoint/model is a **prerequisite and is not implemented on the inspected primary branch**.

| ActionCode | Exact method and path | Descriptor/version owner | Idem | Confirmation / risk floor | Backend permission |
|---|---|---|---|---|---|
| `change_cutover_mode` | `PUT /operations/cutover-mode` | bootstrap cutover row | Yes | typed / high | `platform.cutover.change` |
| `claim_project` | `POST /projects/{project}/claim` | bootstrap project | Yes | dialog / medium | `project.claim` |
| `create_mission` | `POST /missions` | bootstrap claimed project | Yes | none / low | `mission.create` |
| `edit_mission` | `PATCH /missions/{mission}` | mission | Yes | none / low | `mission.edit` |
| `activate_mission` | `POST /missions/{mission}/actions/activate` | mission | Yes | dialog / medium | `mission.activate` |
| `pause_mission` | `POST /missions/{mission}/actions/pause` | mission | Yes | dialog / low | `mission.pause` |
| `resume_mission` | `POST /missions/{mission}/actions/resume` | mission | Yes | dialog / low | `mission.resume` |
| `complete_mission` | `POST /missions/{mission}/actions/complete` | mission | Yes | dialog / medium | `mission.complete` |
| `cancel_mission` | `POST /missions/{mission}/actions/cancel` | mission | Yes | typed / high | `mission.cancel` |
| `archive_mission` | `POST /missions/{mission}/actions/archive` | mission | Yes | dialog / medium | `mission.archive` |
| `create_work_package` | `POST /missions/{mission}/work-packages` | mission | Yes | none / low | `work.create` |
| `edit_work_package` | `PATCH /work-packages/{work}` | work package | Yes | none / low | `work.edit` |
| `add_work_dependency` | `POST /work-packages/{work}/dependencies` | work package | Yes | none / low | `work.dependency.add` |
| `remove_work_dependency` | `DELETE /work-packages/{work}/dependencies/{dependency}` | work package | Yes | dialog / low | `work.dependency.remove` |
| `block_work_package` | `POST /work-packages/{work}/actions/block` | work package | Yes | dialog / medium | `work.block` |
| `unblock_work_package` | `POST /work-packages/{work}/actions/unblock` | work package | Yes | dialog / medium | `work.unblock` |
| `cancel_work_package` | `POST /work-packages/{work}/actions/cancel` | work package | Yes | typed / high | `work.cancel` |
| `rebrief_work_package` | `POST /work-packages/{work}/actions/rebrief` | work package | Yes | dialog / medium | `work.rebrief` |
| `create_brief_revision` | `POST /work-packages/{work}/brief-revisions` | work package | Yes | none / low | `brief.create_revision` |
| `edit_brief_revision` | `PATCH /brief-revisions/{brief}` | brief revision | Yes | none / low | `brief.edit_revision` |
| `validate_brief` | `POST /brief-revisions/{brief}/validate` | brief revision | Yes | none / low | `brief.validate` |
| `submit_brief_for_approval` | `POST /brief-revisions/{brief}/submit` | brief revision | Yes | dialog / medium | `brief.submit` |
| `approve_brief` | `POST /brief-revisions/{brief}/approve` | brief revision | Yes | dialog / medium | `brief.approve` |
| `reject_brief` | `POST /brief-revisions/{brief}/reject` | brief revision | Yes | dialog / medium | `brief.reject` |
| `withdraw_brief` | `POST /brief-revisions/{brief}/withdraw` | brief revision | Yes | dialog / low | `brief.withdraw` |
| `assign_author` | `POST /work-packages/{work}/assignments/author` | work package | Yes | dialog / medium | `assignment.author.create` |
| `assign_reviewer` | `POST /work-packages/{work}/assignments/reviewer` | work package | Yes | dialog / medium | `assignment.reviewer.create` |
| `dispatch_assignment` | `POST /assignments/{assignment}/dispatch` | assignment | Yes | dialog / medium | `assignment.dispatch` |
| `withdraw_queued_assignment` | `POST /assignments/{assignment}/actions/withdraw-queue` | assignment | Yes | dialog / medium | `assignment.queue.withdraw` |
| `steer_run` | `POST /runs/{run}/actions/steer` | run | Yes | none / low | `run.steer` |
| `interrupt_run` | `POST /runs/{run}/actions/interrupt` | run | Yes | typed / high | `run.interrupt` |
| `retry_run` | `POST /runs/{run}/actions/retry` | run | Yes | dialog / medium | `run.retry` |
| `release_run_writer` | `POST /runs/{run}/writer/actions/release` | run writer lease | Yes | typed / high | `run.writer.release` |
| `reacquire_run_writer` | `POST /runs/{run}/writer/actions/reacquire` | run writer lease | Yes | typed / high | `run.writer.reacquire` |
| `restart_worker` | `POST /operations/workers/{worker}/actions/restart` | worker lifecycle record | Yes | typed / critical | `operations.worker.restart` |
| `decide_approval` | `POST /approvals/{approval}/decide` | approval | Yes | descriptor-dynamic / medium | `approval.decide` |
| `respond_interaction` | `POST /interactions/{interaction}/respond` | interaction | Yes | descriptor-dynamic / low | `interaction.respond` |
| `link_evidence` | `POST /evidence/{evidence}/criterion-links` | evidence | Yes | none / low | `evidence.link` |
| `verify_evidence` | `POST /evidence/{evidence}/actions/verify` | evidence | Yes | dialog / medium | `evidence.verify` |
| `reject_evidence` | `POST /evidence/{evidence}/actions/reject` | evidence | Yes | dialog / medium | `evidence.reject` |
| `create_audit` | `POST /work-packages/{work}/audits` | work package | Yes | dialog / medium | `audit.create` |
| `edit_audit_matrix` | `PATCH /audits/{audit}` | audit | Yes | none / low | `audit.edit_matrix` |
| `submit_audit` | `POST /audits/{audit}/submit` | audit | Yes | dialog / medium | `audit.submit` |
| `accept_implementation` | `POST /audits/{audit}/actions/accept` | audit | Yes | typed / high | `audit.accept` |
| `request_rework` | `POST /audits/{audit}/actions/request-rework` | audit | Yes | dialog / medium | `audit.request_rework` |
| `require_human_decision` | `POST /audits/{audit}/actions/require-human-decision` | audit | Yes | dialog / high | `audit.require_human_decision` |
| `record_human_decision` | `POST /audits/{audit}/actions/human-decision` | audit | Yes | typed / high | `audit.human_decision` |
| `fail_audit` | `POST /audits/{audit}/actions/fail` | audit | Yes | dialog / medium | `audit.fail` |
| `create_decision` | `POST /missions/{mission}/decisions` | mission | Yes | none / low | `decision.create` |
| `edit_decision` | `PATCH /decisions/{decision}` | decision | Yes | none / low | `decision.edit` |
| `accept_decision` | `POST /decisions/{decision}/actions/accept` | decision | Yes | dialog / medium | `decision.accept` |
| `reject_decision` | `POST /decisions/{decision}/actions/reject` | decision | Yes | dialog / medium | `decision.reject` |
| `supersede_decision` | `POST /decisions/{decision}/actions/supersede` | decision | Yes | dialog / medium | `decision.supersede` |
| `create_risk` | `POST /missions/{mission}/risks` | mission | Yes | none / low | `risk.create` |
| `edit_risk` | `PATCH /risks/{risk}` | risk | Yes | none / low | `risk.edit` |
| `mitigate_risk` | `POST /risks/{risk}/actions/mitigate` | risk | Yes | dialog / medium | `risk.mitigate` |
| `accept_risk` | `POST /risks/{risk}/actions/accept` | risk | Yes | typed / high | `risk.accept` |
| `materialize_risk` | `POST /risks/{risk}/actions/materialize` | risk | Yes | typed / high | `risk.materialize` |
| `close_risk` | `POST /risks/{risk}/actions/close` | risk | Yes | dialog / medium | `risk.close` |
| `create_checkpoint` | `POST /missions/{mission}/checkpoints` | mission | Yes | dialog / low | `checkpoint.create` |
| `mark_checkpoint_current` | `POST /missions/{mission}/checkpoints/{checkpoint}/mark-current` | mission | Yes | dialog / medium | `checkpoint.mark_current` |
| `add_workspace_boundary` | `POST /operations/boundaries` | operations settings | Yes | typed / high | `operations.boundary.add` |
| `remove_workspace_boundary` | `DELETE /operations/boundaries/{boundary}` | boundary | Yes | typed / high | `operations.boundary.remove` |
| `update_telemetry_settings` | `PUT /operations/telemetry` | telemetry settings | Yes | typed / high | `operations.telemetry.update` |
| `test_telemetry_connection` | `POST /operations/telemetry/test` | telemetry settings | Yes | dialog / medium | `operations.telemetry.test` |
| `install_plugin` | `POST /operations/plugins/{plugin}/install` | plugin catalogue item | Yes | typed / critical | `operations.plugin.install` |
| `remove_worktree` | `DELETE /operations/worktrees/{worktree}` | worktree | Yes | typed / critical | `operations.worktree.remove` |
| `create_intake` | `POST /intake` | bootstrap/project | Yes | none / low | `intake.create` |
| `promote_intake` | `POST /intake/{intake}/actions/promote` | intake item | Yes | dialog / medium | `intake.promote` |
| `defer_intake` | `POST /intake/{intake}/actions/defer` | intake item | Yes | none / low | `intake.defer` |
| `decline_intake` | `POST /intake/{intake}/actions/decline` | intake item | Yes | dialog / medium | `intake.decline` |
| `mark_intake_duplicate` | `POST /intake/{intake}/actions/mark-duplicate` | intake item | Yes | dialog / low | `intake.mark_duplicate` |

#### Registry invariants and expansion

1. OpenAPI annotates every externally callable state-changing v2 operation with exactly one `x-action-code` from registry `1.0`, one `x-backend-permission`, its descriptor-bearing resource/version source, and idempotency/confirmation metadata. Non-state-changing POST transport operations such as one-use event-ticket issuance are annotated `x-operator-action: false` and `x-operation-kind: read-session` and cannot mutate a domain aggregate.
2. Startup and CI build a bijection between the OpenAPI operator-mutation set and the registry table: no mutating operation lacks a code, no operation has two codes, no code maps to two semantic mutations, and no permission is blank.
3. A descriptor may be emitted only by the resource named in its registry row and only for that resource version. The mutation handler must require the same action code/permission and re-authorize it.
4. Machine-only mutations—worker event append, heartbeat/state ingestion, automatic evidence capture, durable outbox publication, automatic checkpointing, and idempotency finalization—are not operator actions and never emit `AllowedActionDescriptor`. They are separately annotated `x-operator-action: false` and require a named internal capability bound to the run/service identity; CI requires every such mutation to declare that capability.
5. Expanding the union requires a registry version bump, ADR/OpenAPI review, generated TypeScript refresh, backend permission/policy addition, route and descriptor conformance tests, and independent audit in the slice that introduces it. Unknown registry versions or codes fail closed.
6. Bootstrap exposes `action_registry_version`, and API/client conformance tests prove every enabled mutation has exactly one known descriptor while every emitted descriptor resolves to one implemented endpoint and backend permission.

### 15.4 API/action matrix

`Prerequisite` means the contract is required but not implemented on the inspected primary branch. It must not be represented by local fixtures.

| UI action/read | V2 facade contract | Capability/action | Current status |
|---|---|---|---|
| Bootstrap | `GET /api/admin/codex/v2/bootstrap` | `can_view_supervisor` | **Prerequisite**; must include P0/migration/readiness state |
| Cutover mode | `GET/PUT /operations/cutover-mode` | `change_cutover_mode` + `If-Match` + expected version | **Prerequisite** exact graph/conditional/idempotent contract in section 5.1 |
| List projects | `GET /projects` | platform owner / scoped member | **Prerequisite facade**; opaque ID/name/claim state only |
| Claim project | `POST /projects/{id}/claim` | `claim_project` | **Prerequisite durable claim/adoption**; no host path input |
| Legacy thread mapping | `GET /legacy-links/threads/{id}` | authorized translation | **Prerequisite** for cutover compatibility |
| Mission counts/list | `GET /missions` | `can_view_supervisor` | **Prerequisite durable domain** |
| Create mission | `POST /missions` | `create_mission` | **Prerequisite durable domain** |
| Mission detail | `GET /missions/{id}` | membership/capability | **Prerequisite durable domain** |
| Mission transition | `POST /missions/{id}/actions/{action}` | one of `activate_mission|pause_mission|resume_mission|complete_mission|cancel_mission|archive_mission` | **Prerequisite** explicit registered actions only |
| Work list/create | `GET/POST /missions/{id}/work-packages` | read / `create_work_package` | **Prerequisite durable domain** |
| Draft brief | `POST /work-packages/{id}/brief-revisions` | `create_brief_revision` | **Prerequisite durable domain** |
| Read/save brief | `GET/PATCH /brief-revisions/{id}` | read / `edit_brief_revision` + revision | **Prerequisite durable domain** |
| Validate brief | `POST /brief-revisions/{id}/validate` | `validate_brief` | **Prerequisite**; no state fabrication |
| Submit/reject/withdraw brief | `POST /brief-revisions/{id}/submit|reject|withdraw` | `submit_brief_for_approval|reject_brief|withdraw_brief` | **Prerequisite durable state machine** |
| Approve brief | `POST /brief-revisions/{id}/approve` | `approve_brief` | **Prerequisite** immutable transaction |
| Create assignment | `POST /work-packages/{id}/assignments/author|reviewer` | `assign_author|assign_reviewer` | **Prerequisite durable domain** |
| Dispatch assignment | `POST /assignments/{id}/dispatch` | `dispatch_assignment` | **Prerequisite**; adapts proven worker/worktree services |
| Withdraw queued assignment | `POST /assignments/{id}/actions/withdraw-queue` | `withdraw_queued_assignment` | **Prerequisite**; legal only before worker acknowledgement |
| List/read runs | `GET /runs`, `GET /runs/{id}` | view run | **Prerequisite read model** |
| Run snapshot/activity | `GET /runs/{id}/snapshot`, `GET /runs/{id}/timeline` | view run | **Prerequisite durable snapshot/history** |
| Steer/interrupt/retry | `POST /runs/{id}/actions/steer|interrupt|retry` | `steer_run|interrupt_run|retry_run` | **Prerequisite facade** over proven controls |
| Writer state/release/reacquire | `GET /runs/{id}/writer`, `POST /runs/{id}/writer/actions/release|reacquire` | read / `release_run_writer|reacquire_run_writer` | **Prerequisite** typed owner/capability and handoff contract in section 15.8 |
| Resolve approval/input | `POST /approvals/{id}/decide`, `POST /interactions/{id}/respond` | `decide_approval|respond_interaction` | **Prerequisite exact binding** |
| Diff/tests/output | `GET /runs/{id}/diff`, `/tests`, `/output` | view run evidence | **Prerequisite bounded disclosure schemas** |
| Evidence list/detail | `GET /evidence`, `GET /evidence/{id}` | view evidence | **Prerequisite durable domain and disclosure contract** |
| Artifact metadata | `GET /artifacts/{opaque_id}` | authorized evidence read | **Prerequisite** bounded metadata only; no bytes or host path |
| Artifact content ticket | `POST /artifacts/{opaque_id}/tickets`, `GET /artifacts/{opaque_id}/content` | authenticated `read-session`; no `ActionCode` | **Prerequisite/not implemented**; section 15.8.7 actor/resource/digest/root binding |
| Link/verify/reject evidence | `POST /evidence/{id}/criterion-links|actions/verify|actions/reject` | `link_evidence|verify_evidence|reject_evidence` | **Prerequisite**; cannot fabricate machine result |
| Create/read audit | `POST /work-packages/{id}/audits`, `GET /audits/{id}` | `create_audit` / read | **Prerequisite durable domain** |
| Save criterion matrix | `PATCH /audits/{id}` | `edit_audit_matrix` + revision | **Prerequisite** |
| Audit submission/outcome | registry paths in section 15.3 | `submit_audit|accept_implementation|request_rework|require_human_decision|record_human_decision|fail_audit` | **Prerequisite server enforcement** |
| Brain | `GET /missions/{id}/brain` | view brain | **Prerequisite durable domain** |
| Decisions/risks | registry paths in section 15.3 | closed decision/risk action-code subsets | **Prerequisite durable domain** |
| Checkpoints | `GET/POST /missions/{id}/checkpoints`, `POST .../{checkpoint}/mark-current` | `create_checkpoint|mark_checkpoint_current` | **Prerequisite durable domain** |
| Operations readiness | `GET /operations/readiness` | platform owner | **Prerequisite facade** over real diagnostics |
| Operations mutations | exact registry paths in section 15.3 | `add_workspace_boundary|remove_workspace_boundary|update_telemetry_settings|test_telemetry_connection|install_plugin|remove_worktree` | **Prerequisite facade**; never arbitrary URL/path inputs |
| Worker restart | `POST /operations/workers/{worker}/actions/restart` | `restart_worker` | **Prerequisite** platform-owner typed confirmation and lifecycle acknowledgement |
| Operations diagnostics | `/operations/readiness|models|skills|plugins|workers|events` | read-only platform-owner capability | **Prerequisite facade**; no unregistered mutation |
| Intake | registry paths in section 15.3 | `create_intake|promote_intake|defer_intake|decline_intake|mark_intake_duplicate` | **Prerequisite durable adapter** |
| Event ticket | `POST /events/ticket` | resource-scoped stream | **P0 transport exists on branch; v2 binding prerequisite** |
| Event stream | `GET /events/stream?sse_ticket=...&after_sequence=N` | consumed one-use ticket | **Prerequisite durable replay** |
| Optional active-run projection | `POST /runs/{id}/ag-ui/stream` | authenticated read-session attach to existing run; no `ActionCode` | **Optional prerequisite/not implemented**; section 15.7 PoC only, `x-operator-action: false` |

Except for the full bootstrap example, paths in this table are relative to the single canonical base `/api/admin/codex/v2`. Every listed v2 contract remains a prerequisite/not implemented on the inspected primary branch unless its status explicitly says only the lower-level P0 transport exists. No duplicate aliases are consumed by v2.

### 15.5 Event matrix

The full envelope is returned in SSE `data`, not reconstructed by the browser:

```json
{
  "id": "sev_...",
  "schema_version": "2.0",
  "sequence": 42,
  "occurred_at": "RFC3339",
  "project_id": "...",
  "mission_id": "...",
  "entity_id": "...",
  "entity_version": 4,
  "type": "run.updated",
  "payload": {}
}
```

| Event type | UI reaction | Authoritative follow-up |
|---|---|---|
| `mission.updated` | mark mission/count queries stale | refetch mission/counts |
| `brief.updated` | show external-update indicator | refetch unless local buffer dirty; then conflict flow |
| `work_package.updated` | update attention badge | refetch package/mission |
| `run.updated` | update run freshness/attention | refetch run snapshot |
| `run.attention_required` | persistent attention item + polite announcement | fetch actionable request |
| `approval.updated` | update approval status | refetch approval/run |
| `evidence.captured` | show captured-not-verified | refetch ledger/package coverage |
| `evidence.verified` | update verification indicator | refetch evidence/audit |
| `audit.updated` | update queue/decision availability | refetch audit/package |
| `decision.updated` | update brain attention | refetch brain/decision |
| `risk.updated` | update risk/blocker count | refetch brain/mission |
| `checkpoint.created` | announce durable checkpoint | refetch checkpoint/mission |
| unknown type | diagnostic warning; no reducer guess | refetch affected snapshot |

Events invalidate or draw attention. REST snapshots remain authoritative.

### 15.6 Bounded disclosure schemas

All contracts in this section are **backend prerequisites and not implemented on the inspected primary branch**. Redaction and bounds are enforced before serialization; the frontend is not a security boundary.

#### Common disclosure rules

- Cursor pagination defaults to 50 and caps at 100 records. Cursors are opaque, actor/resource/filter-bound, expire after 15 minutes, and contain no path or content.
- All text is valid UTF-8, Unicode-normalized, stripped of terminal control sequences and unsafe control characters, and bounded after redaction.
- Redaction replaces content with typed markers such as `[REDACTED:SECRET]`, `[REDACTED:PII]`, `[REDACTED:CUSTOMER_DATA]`, or `[REDACTED:PATH]`. Responses include counts by class, never the removed value.
- Every page/detail includes `schema_version`, `request_id`, source resource IDs, source commit where applicable, capture time, content digest, `truncated`, and `omitted_bytes`/`omitted_items` when known safely.
- Host paths become opaque logical workspace IDs plus normalized repository-relative paths. Drive letters, usernames, home paths, sibling roots, UNC paths, and temporary directories are never returned.
- Prompts, model response bodies, hidden reasoning, authorization/cookie/header material, credentials, environment values, database URLs, SMS bodies, booking notes, customer identities/contact details, and unallowlisted event payload keys are excluded—not merely visually hidden.
- Error/detail strings are server-authored safe summaries. Raw exception strings and worker payloads are not forwarded.

#### Timeline page — `GET /runs/{id}/timeline`

```ts
interface RunTimelinePage {
  items: Array<{
    id: string
    sequence: number
    kind: 'state' | 'command_summary' | 'file_change_summary' | 'approval' |
          'operator_input' | 'test_summary' | 'warning' | 'error'
    occurred_at: string
    title: string                 // max 160 characters
    summary: string               // max 2,000 characters
    status: string
    related_entity_id: string | null
    redaction_counts: Record<string, number>
    truncated: boolean
  }>
  next_cursor: string | null
  snapshot_sequence: number
}
```

No raw agent message, prompt, reasoning, command stdout/stderr, patch, or unrestricted worker event appears in the timeline.

#### Output page — `GET /runs/{id}/output`

```ts
interface RunOutputPage {
  items: Array<{
    id: string
    sequence: number
    stream: 'stdout' | 'stderr' | 'system'
    command_label: string | null  // server-derived, max 512 characters
    text: string                  // max 16 KiB after redaction
    byte_count: number
    content_sha256: string
    redaction_counts: Record<string, number>
    truncated: boolean
    omitted_bytes: number
    occurred_at: string
  }>
  next_cursor: string | null
  response_truncated: boolean
}
```

The response caps at 50 items and 512 KiB serialized content. Exact shell commands with sensitive arguments are replaced by a safe command label. ANSI escapes are removed. Output for prohibited/sensitive commands is evidence metadata only and never disclosed inline.

#### Diff page/detail — `GET /runs/{id}/diff`

```ts
interface RunDiffPage {
  baseline_commit: string
  submitted_commit: string
  files: Array<{
    file_id: string
    path: string                  // repository-relative, max 512 characters
    change_type: 'added' | 'modified' | 'deleted' | 'renamed' | 'binary'
    additions: number
    deletions: number
    patch: string | null          // max 256 KiB after redaction
    patch_sha256: string
    redaction_counts: Record<string, number>
    truncated: boolean
    omitted_bytes: number
  }>
  next_cursor: string | null
}
```

Each page caps at 50 files and 1 MiB serialized content. `.env`, credentials, runtime databases, logs, ignored secret material, and files outside the approved repository/allowlist return only a safe exclusion marker and digest where policy permits. Binary files never return inline bytes.

#### Test page — `GET /runs/{id}/tests`

```ts
interface RunTestPage {
  items: Array<{
    id: string
    suite: string                 // max 160 characters
    name: string                  // max 240 characters
    status: 'passed' | 'failed' | 'skipped' | 'unknown'
    duration_ms: number | null
    safe_failure_summary: string | null // max 2,000 characters
    evidence_id: string
    source_commit: string
  }>
  next_cursor: string | null
}
```

There is no raw test stdout, environment dump, fixture customer data, or stack trace. A missing/unexecuted test is `skipped` or `unknown`, never passed.

#### Evidence detail — `GET /evidence/{id}`

```ts
interface EvidenceDisclosure {
  id: string
  kind: string
  state: 'captured' | 'verified' | 'rejected' | 'superseded'
  result: 'passed' | 'failed' | 'inconclusive' | 'observed'
  source_run_id: string | null
  source_commit: string | null
  command_label: string | null    // max 512 characters
  exit_code: number | null
  duration_ms: number | null
  summary: string                 // max 4,000 characters
  environment: {
    os_family: string | null
    runtime_names: string[]       // allowlisted names/major versions only
    test_profile: string | null
  }
  criterion_ids: string[]         // max 100
  content_sha256: string
  byte_size: number
  artifact_ids: string[]          // opaque, max 20
  redaction_counts: Record<string, number>
  truncated: boolean
  captured_at: string
  verified_at: string | null
  verified_by_run_id: string | null
}
```

Environment keys are allowlisted; arbitrary environment variables are rejected. Human observations are visibly distinct and cannot claim machine pass status.

#### Artifact metadata and content policy

- Prerequisite `GET /artifacts/{opaque_id}` returns bounded metadata only. Byte-bearing content uses the expiring two-step ticket in section 15.8.7; the direct metadata response never contains content bytes.
- Authorization is rechecked against actor, mission, work package, run, evidence, and current retention state on metadata, ticket issuance, and content requests.
- The client supplies only an opaque artifact ID; it cannot supply a path or remote URL.
- First-release allowlist: scrubbed `text/plain` and `application/json` up to 256 KiB for inline display; verified/redacted `image/png` and `image/jpeg` up to 5 MiB in an isolated viewer; `application/pdf` up to 10 MiB as attachment only.
- HTML, SVG, executable content, archives, office macros, scripts, and unknown MIME types are never rendered inline. `X-Content-Type-Options: nosniff`, restrictive CSP for viewers, and safe `Content-Disposition` are mandatory.
- Size/type/digest mismatch returns `evidence_invalid`; the server never streams the rejected bytes.

Contract tests use labelled secret, token, email, phone, address, booking-note, SMS-body, prompt, model-response, host-path, ANSI/control-character, oversized, malformed UTF-8, binary, MIME-spoof, cross-tenant, and cursor-replay canaries. Run Detail and Evidence remain disabled until these tests pass.

### 15.7 Optional AG-UI/CopilotKit active-run adapter ADR and spike gate

This section incorporates the accepted `CCC_COPILOTKIT_FIT_ASSESSMENT.md` decision: **SPIKE FIRST**. It is a binding optional-adapter ADR amendment, not approval to install a dependency or implement a runtime. Every endpoint, persistence mapping, model, feature flag, package, and component described here is a **prerequisite/not implemented on the inspected primary branch** unless a future approved spike proves otherwise.

The native contract remains:

```text
FastAPI durable mission/run/approval/evidence/audit control plane
  -> authoritative REST snapshots + passive ticketed v2 SSE
  -> canonical React supervisor + TanStack Query
  -> optional active-run AG-UI/CopilotKit presentation adapter
  -> existing Codex worker
```

CopilotKit/AG-UI may make one already-authorized active run easier to observe or interact with. It cannot decide that work exists, dispatch work, establish identity or ownership, make an approval live, accept evidence, complete an audit/mission, persist Project Brain state, or replace any native REST/SSE workflow. CopilotKit thread persistence, if separately approved later, is only a projection containing opaque correlations.

#### 15.7.1 Passive and active channels are separate

| Channel | Contract and purpose | Authentication | Resume and unknown outcome |
|---|---|---|---|
| Passive supervisor events | `POST /events/ticket`, then `GET /events/stream?sse_ticket=...&after_sequence=N`; invalidation and attention only | Native authenticated ticket mint; short-lived atomic one-use ticket scoped to actor/project/thread; no bearer in URL | Mint a fresh ticket for every connect/reconnect; resume after last durable v2 sequence; REST refetch on gap, unknown event, expired history, or invalid envelope |
| Active run projection | prerequisite `POST /runs/{run}/ag-ui/stream`; attach to one existing durable run and project only bounded run presentation events | Ordinary native application credential in `Authorization`; FastAPI reauthenticates and reauthorizes every request; no query credential | Reattach to the same durable run and `after_sequence`, or refetch its REST snapshot; a disconnect never dispatches, retries, resumes a paused lifecycle, or mutates a run |

The active POST is `x-operator-action: false` and `x-operation-kind: read-session`; opening it cannot create an assignment/run, advance lifecycle, resolve an approval, or execute a tool. All mutations continue through the section 15.3 registry with their original idempotency keys. The P0 one-use GET ticket is never accepted by the active stream, transformed into a bearer, forwarded by a Node runtime, or placed in another query string. Passive SSE and active AG-UI maintain independent connection indicators and sequence cursors.

On active-stream loss, the client shows `Active run stream disconnected`, keeps the last REST-confirmed state, refetches `GET /runs/{run}/snapshot`, and reconnects only to the returned run identity. If a preceding dispatch or action has an unknown response, section 15.2 reconciliation completes first with the identical request/key; no runtime or client auto-redispatch is permitted. Offline input is UI intent only and is never shown as accepted.

#### 15.7.2 Bounded AG-UI 1.0 projection

The adapter supports only this versioned AG-UI 1.0 subset:

| Allowed event | Permitted meaning and payload |
|---|---|
| `RUN_STARTED` | Existing durable supervisor run became observable; opaque thread/run correlations and safe time/status only |
| `RUN_FINISHED` | Durable run reached a terminal successful state; safe status/finish time only |
| `RUN_ERROR` | Durable run reached a terminal failure; allowlisted error code and bounded operator-safe message, never an exception/trace |
| `ACTIVITY_SNAPSHOT` | Bounded redacted progress label, phase, status, percent when real, and updated time |
| `ACTIVITY_DELTA` | Validated change to the same allowlisted activity fields; never an arbitrary JSON patch |
| `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END` | Explicitly disclosure-safe assistant summary only; never prompt, reasoning, model body, command, tool argument/result, or transcript |
| `fastapi_bookings.supervisor.v1.interrupt.waiting` | Opaque durable approval ID/action reference, expected version, safe risk/consequences, policy digest, expiry, and `live_actionable` only |
| `fastapi_bookings.supervisor.v1.subagent.updated` | Opaque durable assignment/run references and safe role/status only |

No other standard or custom type is accepted without an ADR, schema version increment, disclosure review, and conformance tests. `RAW`, `rawEvent`, open metadata/state maps, arbitrary JSON Patch, tool-call events, source/file payloads, and browser-authored domain snapshots are forbidden. Custom events must use the exact `fastapi_bookings.supervisor.v1.*` namespace and a closed schema; unknown fields fail validation.

Each projected event is correlated to one durable supervisor event and carries validated `threadId`, `runId`, server event ID, and monotonically increasing run-local sequence. Deduplication key is `(supervisor_run_id, server_event_id)`. An exact duplicate is ignored; a lower unseen sequence, sequence gap, unknown type/field, invalid delta, mismatched identity, or oversized frame stops local application and triggers bounded REST refetch. The adapter never speculatively repairs state.

Hard serialization bounds are: 16 KiB per event; 2 KiB per text-content chunk and 8 KiB per completed safe summary; 8 KiB per activity snapshot; 4 KiB per activity delta or custom-event payload; maximum 100 replayed events per attach. All strings also obey section 15.6 normalization/redaction rules. Server-side validation and redaction happen before AG-UI serialization; the browser and optional Node runtime are not privacy boundaries.

#### 15.7.3 Full identity and ownership mapping

AG-UI and CopilotKit identifiers are untrusted selectors. The FastAPI adapter resolves this complete chain on every attach, resume, read, and approval-related request:

| Identity | Authority and required relationship |
|---|---|
| verified actor | Native FastAPI authentication result; platform-owner during the development phase; never a body/property/header assertion from the adapter |
| tenant | Server-resolved tenant/account scope for the verified actor; browser-supplied tenant/role claims are ignored |
| project | Claimed, actor-visible supervisor project owned in the tenant scope |
| mission | Durable mission belonging to that project and visible to the actor |
| supervisor thread | Durable supervisor thread belonging to the mission/work lineage; not a CopilotKit thread record |
| assignment | Durable author/reviewer assignment belonging to the work package/thread |
| supervisor run | Durable run belonging to that assignment, with current version/state/control plane |
| AG-UI `threadId` | Server-issued opaque projection ID mapped one-to-one to the supervisor thread for this adapter version |
| AG-UI `runId` | Server-issued opaque projection ID mapped one-to-one to the supervisor run; cannot select or create another run |
| CopilotKit correlation ID | Optional server-issued per-stream/runtime correlation mapped to the AG-UI/supervisor run pair; diagnostic only, never ownership or authorization |

The authorization predicate requires the whole chain to resolve consistently in one actor scope and the run to be eligible for projection. A client cannot supply actor, tenant, role, ownership, path, worker, worktree, or durable status. Guessed, stale, cross-project, cross-tenant, mismatched thread/run, orphaned, or unauthorized IDs use the existing non-leaking denial contract. The optional Node runtime may forward only `Authorization` and an allowlisted correlation header, uses exact-origin CORS, and cannot trust or forward browser-supplied `x-user`, `x-tenant`, `x-role`, project, or ownership assertions. FastAPI remains the final authority even if that runtime also validates authentication.

#### 15.7.4 Durable FastAPI approval binding

CopilotKit interrupt hooks are view/controllers over the existing durable FastAPI approval record; they are never the HITL authority. FastAPI creates and commits the interrupt/approval before any AG-UI projection. The UI then fetches authoritative REST detail and displays the exact durable approval ID, opaque action reference, supervisor run, expected record version, risk, bounded consequences, expiry, policy digest, and current `live_actionable` status.

Resolve/cancel continues through prerequisite `POST /approvals/{approval}/decide` with the `decide_approval` descriptor, native authentication, UUIDv4 `Idempotency-Key`, `If-Match`/`expected_version`, opaque action reference, decision/validated response, and policy digest. FastAPI reauthenticates, reauthorizes, validates the response schema, checks the run/action binding, current version, policy digest, expiry, and state, and atomically records the decision/result/audit evidence. Identical duplicate decisions replay the durable result; a different decision or response with the same key conflicts; expired, resolved, superseded, orphaned, mismatched, or non-actionable records are disabled in UI and rejected server-side.

Approval state survives browser reload plus worker, adapter, and optional runtime restart. A projected interrupt only prompts a REST refetch; it cannot make itself actionable or carry executable authority. Browser-side CopilotKit handlers must never execute shell, Git, deployment, booking, cancellation, SMS, payment, customer contact, or any other consequential effect.

#### 15.7.5 Privacy, prohibited fields, and no-egress canaries

No active-run event, request, response, browser store, optional-runtime log, telemetry item, trace, error, or outbound request may contain:

- prompts, hidden reasoning/chain-of-thought, model request/response bodies, raw worker events, `rawEvent`, transcripts, or open-ended metadata;
- commands, tool arguments/results, stdout/stderr, unrestricted logs, stack traces, working directories, host/local paths, diffs, source bodies, file content, environment values, credentials, secrets, authorization headers, cookies, or query tokens;
- customer/booking/provider data, SMS bodies, phone numbers, emails, addresses, notes, payment data, or other direct/indirect PII;
- browser-authored mission, brief, assignment, run, approval, evidence, audit, decision, risk, checkpoint, ownership, role, or lifecycle state.

Automated canaries seed labelled examples of every prohibited class into worker input/output and prove absence from browser payloads, DOM diagnostics, console, storage, FastAPI/Node logs, traces/metrics, crash reports, network capture, and all outbound destinations. A no-egress gate denies and records any unexpected hostname. Passing evidence must show no CopilotKit Intelligence, hosted thread, analytics, learning, vendor telemetry, or other unapproved vendor request from browser, FastAPI, or the optional Node process.

#### 15.7.6 Product-tier and dependency gates

CopilotKit Intelligence, hosted or self-hosted threads, memory, analytics, learning, and vendor telemetry are **off by default and out of scope for the spike**. They may not be enabled by a developer flag or package default. Any future proposal requires separate explicit owner, security, legal, privacy, procurement, Australian residency/cross-border, retention/deletion/backup/incident, encryption/identity, data-flow/subprocessor, operational-footprint, and telemetry/learning opt-in approval. Self-hosting does not waive these gates.

The dependency gate requires, before installation in an approved isolated spike:

- exact no-range versions for `@ag-ui/core` and `@ag-ui/client` at protocol gate; exact no-range `@copilotkit/react-core` and `@copilotkit/runtime` only at runtime-value gate;
- reviewed package and lockfile diff, complete transitive SBOM, vulnerability scan, per-package/file license and notice inventory, and explicit exclusion of CopilotKit showcase code/assets unless separately licensed;
- Vite 8, React 19, TypeScript 6 and, for runtime-value gate, Node 20+ build/runtime compatibility plus measured bundle size, startup, memory, health, failure, and shutdown behavior;
- treating every CopilotKit minor release as potentially breaking, with release-note/security/transitive/license review and full protocol/type/build/browser/reconnect/privacy requalification before upgrade;
- AG-UI 1.0 schema/conformance fixtures for every allowed, duplicate, out-of-order, gap, unknown, oversized, invalid-delta, and mismatched-identity case;
- an off-by-default server-controlled kill switch and tested native fallback that removes the adapter without impairing REST snapshots, passive SSE, mission/run supervision, approvals, evidence, audit, or checkpoints.

No CopilotKit/AG-UI package belongs in WP-UI-02, and no existing dependency approval in section 10.3 covers it. Package names or versions observed in the assessment are not approval to install them; the future spike brief must freeze exact reviewed versions and expand its own changed-file allowlist.

#### 15.7.7 Sequencing and two-gate proof of concept

No adapter dependency, route, component, transport, runtime, or UI reliance may begin until all four preconditions are independently evidenced on the spike branch:

1. It descends from the accepted P0 trust-boundary commit.
2. FastAPI exposes durable platform-owner-scoped project/mission/thread/assignment/run ownership, run version/snapshot, and exact idempotency through the v2 facade.
3. The strict server-side safe-event schema above exists and raw current worker events are not the browser contract.
4. The spike has a dedicated isolated branch/worktree, exact changed-file allowlist, test commands, rollback/removal plan, and independent security reviewer.

The spike uses one hidden, platform-owner-only canonical-frontend route and one real labelled synthetic read-only Codex author run. It uses no fake state, timers, customer/booking/SMS data, external side effect, chat popup/sidebar, showcase UI, generative UI, or visual redesign dependency.

**Gate 1 — protocol:** Vite React uses exact-pinned `@ag-ui/core`/`@ag-ui/client` directly against the FastAPI-owned active POST endpoint and renders only the bounded AG-UI 1.0 projection. Gate 2 is blocked until Gate 1 passes every applicable exit criterion.

**Gate 2 — runtime value:** Insert the smallest Node 20+ Express or Hono Copilot Runtime and v2 headless React integration in front of the same authenticated FastAPI adapter. Intelligence and vendor services stay disabled. Record the concrete material capability gained over Gate 1 and the added service/security/operational cost.

The spike passes only with evidence for all of these exit criteria:

1. Exact-version Vite 8/React 19/TypeScript 6 production build and focused component tests pass.
2. No credential enters a URL; missing/invalid credentials and tenant admins are denied; platform owner succeeds; FastAPI reauthenticates each request; CORS is exact-origin.
3. Guessed project, mission, thread, run, action, approval, and tenant identifiers cannot read, stream, resume, or mutate another scope and do not leak existence.
4. Forced disconnect/replay produces one durable dispatch and one worker execution; neither client nor runtime auto-redispatches.
5. Reload, offline/online, adapter/runtime restart, and worker restart preserve the run and recover from REST without duplicate effect.
6. Passive SSE mints a fresh one-use ticket per connection and handles duplicate, out-of-order, gap, and expired history correctly.
7. AG-UI mandatory boundaries/IDs conform to 1.0; duplicate, unknown, oversized, invalid-delta, identity mismatch, and out-of-order behavior is deterministic.
8. Disclosure/no-egress canaries prove all prohibited fields absent from payloads, logs, telemetry, storage, and outbound requests.
9. A durable interrupt survives reload/restarts and duplicate, conflicting, expired, resolved, superseded, and orphaned decisions obey section 15.7.4.
10. License inventory/notices, SBOM, vulnerability scan, bundle impact, Node memory/startup/health, and upgrade policy are recorded.
11. Gate 2 demonstrates material operational value that justifies the additional process and trust boundary.
12. Disabling/removing the adapter leaves native REST/SSE, mission workflow, approvals, evidence, and audit behavior passing unchanged.
13. Focused backend/frontend, zero-console/network, living-doc, independent security, and QA gates pass from a clean checkout.

The CopilotKit-arm sub-decision after evidence is one of: **COPILOTKIT ARM PASSES** only if every criterion passes and Gate 2 demonstrates material value; **DIRECT AG-UI CONTROL PASSES** if Gate 1 is valuable but Gate 2 is not; or **COPILOTKIT ARM REJECTED** if native v2 REST/SSE is safer, simpler, or equally capable. This is evidence supplied to the final three-arm selection in section 15.10; it is not permission to retain both arms. Failure of any security, durability, privacy, reconnect, fallback, or dependency criterion rejects the affected arm. The native ground-up supervisor remains fully operable in every outcome.

### 15.8 Codex Bridge reference-only ADR and native worker invariants

This section incorporates the accepted `CCC_CODEX_BRIDGE_FIT_ASSESSMENT.md` decision: **REFERENCE ONLY**. Codex Bridge may inform independently specified behavior, but it is not cloned, installed, copied, linked, invoked, proxied, embedded, or added to a Cargo/npm/runtime/build graph. Its daemon, CLI, Web UI, authentication, rollout persistence, process manager, control socket, queue path, and Unix service topology are not supervisor authorities or implementation foundations.

The ground-up canonical UI and section 15.7 CopilotKit/AG-UI optional spike decision remain unchanged. Codex Bridge is an alternative southbound app-server client/daemon, not a northbound presentation protocol. Stacking it beneath the optional AG-UI adapter is prohibited. All native endpoints, models, fields, migrations, and services described below are **prerequisites/not implemented on the inspected primary branch**.

#### 15.8.1 Sole worker adapter and typed writer capability

FastAPI Bookings owns exactly one first-party southbound adapter from the v2 supervisor control plane to the supported Codex app-server protocol. Only that adapter may issue supervisor mutations, correlate app-server requests, answer server requests, or manage the worker process. A browser, Codex Bridge, Codex CLI queue command, rollout reader, optional Node/Copilot runtime, Codex Desktop, or another daemon cannot become a parallel writer or bypass `/api/admin/codex/v2`.

Every run snapshot returns this closed projection, derived server-side rather than inferred from rollout modification time:

```ts
type WriterState =
  | 'native_owned'
  | 'externally_owned'
  | 'unowned'
  | 'stale'
  | 'unknown'

type LifecycleOwnerState = 'managed' | 'adopted' | 'external' | 'unknown'

interface WriterCapabilityProjection {
  writer_state: WriterState
  writer_owner: {
    kind: 'fastapi_worker' | 'codex_desktop' | 'other_app_server' | 'none' | 'unknown'
    opaque_instance_id: string | null
    safe_label: string
  }
  lifecycle_owner_state: LifecycleOwnerState
  owner_version: number
  observation_source:
    | 'native_manager'
    | 'app_server_handshake'
    | 'normalized_adapter_history'
    | 'rollout_diagnostic'
  confidence: 'authoritative' | 'confirmed' | 'observed' | 'stale' | 'unknown'
  observed_at: string
  expires_at: string | null
  read_only: boolean
  capabilities: {
    can_read: boolean
    can_queue: boolean
    can_steer: boolean
    can_interrupt: boolean
    can_release: boolean
    can_reacquire: boolean
    can_restart: boolean
  }
  reason_code: string | null
  reason: string | null
}
```

Capability behavior is binding:

| Writer state | Read | Queue | Steer / interrupt | Release | Reacquire / restart | UI behavior |
|---|---|---|---|---|---|---|
| `native_owned` | Yes | Yes | Only when run/action state permits | Descriptor-gated | Reacquire no; restart platform-owner descriptor only | Full server-listed actions; owner and acknowledgement visible |
| `externally_owned` | Bounded read when authorized | Yes, durable queue only | No | No; native cannot release another owner | No | Explicit read-only banner naming only safe owner kind; queued is not running |
| `unowned` | Yes | Yes | No | No | Descriptor-gated explicit reacquire; restart only if a native managed worker record exists | Show unowned and the permitted acquisition action; never auto-acquire |
| `stale` | Last confirmed bounded snapshot | No new mutation | No | No | No until fresh ownership probe; then a newly issued descriptor is required | Persistent stale warning and refresh ownership control |
| `unknown` | Safe durable supervisor snapshot only | No | No | No | No | Fail closed; no owner inference or newest-rollout routing |

`read_only=true` whenever the writer is external, stale, unknown, or otherwise lacks direct app-server mutation capability. `can_queue=true` may coexist with read-only because it creates only a durable local queue record and does not touch the worker until ownership is later valid. Capability booleans are presentation hints tied to `owner_version`; each mutation reauthenticates, reauthorizes, locks the ownership record, checks the expected version/lease, and revalidates app-server acknowledgement state. Safe owner labels never expose a host path, username, socket, PID, token, or cross-scope identity.

#### 15.8.2 One lifecycle owner, release, reacquire, and handoff

Each worker/session has one durable lifecycle owner record:

- `managed`: FastAPI launched the process and alone may stop/restart it;
- `adopted`: FastAPI explicitly adopted an already-running compatible process after authenticated handshake and a conflict-free ownership transaction; it becomes sole lifecycle owner only when the durable adoption contract grants stop/restart authority, otherwise the process remains `external`;
- `external`: another manager owns the process/session; FastAPI observes only and cannot stop, restart, release, or mutate it;
- `unknown`: ownership cannot be proven; all worker/session mutation fails closed.

No two manager leases may be active for the same native thread/run/app-server identity. Heartbeat expiry changes ownership to `stale`/`unknown`; it never transfers ownership. Polling, refresh, restart recovery, a newer rollout file, or process discovery never silently adopts or reacquires a writer.

Native release uses prerequisite `release_run_writer`; reacquisition uses `reacquire_run_writer`; disruptive managed-worker restart uses `restart_worker`. All require native authentication, platform-owner or narrower future policy, current descriptor and `owner_version`, UUIDv4 idempotency key, typed confirmation, reason, immutable audit event, and worker/app-server acknowledgement. A release freezes new dispatch/steer, drains or explicitly interrupts the active command, receives release acknowledgement, marks the writer `unowned`, increments `owner_version`, and only then permits a separate reacquire request. Reacquire performs a fresh protocol handshake, proves no other owner/lease, records the lifecycle owner/instance, increments the version, and acknowledges before queued work may dispatch.

There is no direct blind `externally_owned -> native_owned` transition. An external owner must release through its own authority and FastAPI must independently observe `unowned` before reacquisition. Partial/unknown release remains read-only and reconciliation is required; force-steal is not a UI action. Handoff is this two-transaction release-then-reacquire protocol, never a modification-time guess or lock-file deletion.

#### 15.8.3 Durable queue, steer, interrupt, and acknowledgement states

Queueing is a native durable supervisor transition, not an out-of-band Codex command. `dispatch_assignment` first commits an idempotent assignment/run command record, then progresses only through these states:

```text
queued -> awaiting_writer -> dispatching -> worker_acknowledged -> running -> terminal
   \-----------> withdrawn      \-----------> failed
```

- `queued` means FastAPI durably accepted the request; it does not mean a writer exists or execution began.
- `awaiting_writer` means ownership/capability prevents dispatch; externally owned sessions may remain here without mutation.
- `dispatching` means the sole native adapter has sent one version-bound request and is awaiting correlated acknowledgement.
- `worker_acknowledged` means the correct worker/app-server accepted that exact request; it is not yet proof that a turn is running.
- `running` requires the durable normalized turn-start fact for the same run/request.
- `terminal`, `withdrawn`, and `failed` are durable, audited outcomes. `withdraw_queued_assignment` is legal only before worker acknowledgement.

Steer and interrupt each create an immutable, idempotent command record with `requested -> worker_acknowledged -> applied|rejected|expired|failed`. The record binds actor, tenant/project/mission/thread/assignment/run, run and owner versions, action code, request/app-server correlation IDs, safe payload digest, request time, acknowledgement time, and terminal result. UI retains the prior confirmed run state while a command is `requested`; it never reports steered/interrupted from button press alone. Timeout is an unknown outcome reconciled against the command record and normalized adapter acknowledgement with the original idempotency key; no duplicate command is emitted.

Queue withdrawal, steer, interrupt, release, reacquire, and restart appear only through their section 15.3 `AllowedActionDescriptor`. No shell call, `codex queue`, direct app-server browser call, Bridge API, or optional AG-UI event may create these transitions.

#### 15.8.4 Codex app-server protocol/version conformance gate

Before readiness or dispatch, the native adapter records a compatibility fact containing the exact installed Codex version, executable digest/approved distribution identity, checked-in schema bundle version and digest, negotiated protocol capabilities/methods, initialize-handshake result, adapter version, platform, and observation time. It exposes only a bounded safe readiness summary to the browser.

An approved compatibility matrix defines each supported Codex version/schema digest/adapter version combination. Generated or schema-validated request/response/notification types, golden handshake and lifecycle fixtures, request-correlation tests, and live synthetic conformance must pass against the exact Windows binary. Unknown optional fields are tolerated only where the reviewed schema marks forward-compatible reads. Unknown privileged server requests/methods, incompatible required fields, missing capability, schema-major mismatch, or failed initialization fail closed, mark the worker unavailable, preserve the durable run/queue, and block dispatch/mutation.

Every Codex upgrade is a deliberate work package: update the matrix and generated/validated types; review protocol/release changes; run old/new golden fixtures, upgrade/rollback, restart/recovery, authorization, privacy, and Windows gates; then independently approve the exact binary/schema/adapter set. Third-party wrapper compatibility is never evidence of local compatibility.

#### 15.8.5 Explicit recovery-source hierarchy

Recovery uses this strict precedence:

| Rank | Source | Permitted use | Prohibited use |
|---:|---|---|---|
| 1 | Durable supervisor database, audit/event/outbox records, and authoritative v2 REST snapshot | All lifecycle, ownership, idempotency, approval, evidence, audit, and checkpoint truth | None may be overwritten from a lower source without a separately authorized native recovery transition |
| 2 | Normalized first-party app-server adapter history/handshake | Reconcile transient progress/acknowledgement and report observations against an existing durable run | Cannot create a mission/brief/assignment/run, change ownership/lifecycle, resolve approval, verify evidence, accept audit, or complete checkpoint |
| 3 | Raw Codex rollout diagnostic | Platform-owner-only, version-pinned, read-only investigation when ranks 1–2 cannot explain a mismatch | Never normal browser history, automatic recovery, routing authority, durable state, evidence, audit input, context memory, or proof of execution |

Any diagnostic record derived from raw rollouts is labelled `observed_unverified`, passes the full section 15.6 redaction/bounds before persistence or permitted display, and contains no raw prompt/reasoning/tool/path/source/customer data; the raw file itself never crosses the diagnostic adapter boundary. A disagreement creates a durable safe `recovery_mismatch` report containing opaque source IDs, source versions, sequence/time ranges, missing/conflicting fact codes, and recommended read-only next step. It does not mutate records, repair rollouts, promote evidence, restart a worker, or choose a writer. Resolution requires an explicit registered native action or a new brief if no safe action exists.

#### 15.8.6 Bounded snapshot/live history reconciliation

Run Detail uses the following deterministic algorithm:

1. Fetch an authoritative REST snapshot containing the newest window of at most 100 normalized items, `snapshot_sequence`, oldest/newest included sequence, and opaque older-page cursor.
2. Connect passive ticketed SSE after `snapshot_sequence`; while connecting, buffer only validated events for that exact run.
3. Merge by durable event ID and sequence. Ignore exact duplicates and any event already represented at or below the snapshot high-water mark.
4. If there is a gap, conflicting event ID/sequence, unknown type, invalid delta, restart epoch change, or expired history, stop applying live events and refetch the authoritative snapshot. Never splice raw rollout history or infer missing states.
5. Preserve selected item, viewport anchor, collapsed groups, and operator input while refetching unless the selected item is no longer authorized; announce the refresh without jumping scroll.

Older pages contain at most 50 normalized items. Cursors are opaque, actor/run/filter/snapshot-bound, expire after 15 minutes, and cannot cross a restart epoch. The browser retains at most 500 normalized timeline items or 1 MiB serialized data, whichever comes first; it virtualizes long sessions and evicts distant pages while retaining cursors/anchors. Raw output, diffs, files, and reasoning are never retained as timeline history or model context. The optional section 15.7 active projection applies the same native snapshot high-water mark and cannot widen these limits.

#### 15.8.7 Expiring artifact/file ticket contract

The logical artifact metadata read in section 15.6 remains authoritative, but byte-bearing content requires a two-step native ticket. Prerequisite `POST /artifacts/{opaque_id}/tickets` authenticates and authorizes the current actor and returns an opaque in-memory-only ticket; prerequisite `GET /artifacts/{opaque_id}/content` requires the same native authentication plus `X-Artifact-Ticket`. Neither request accepts a host path, root, filename, URL, tenant, owner, MIME, digest, or disposition as browser authority. Ticket issuance is `x-operator-action: false` / `read-session`, not an evidence mutation.

The server record binds ticket digest to actor, tenant, project, mission, work package, run, evidence, opaque artifact ID, expected content digest, allowlisted MIME, disposition, safe filename, maximum bytes, issued/expiry times, logical attempt ID, and `permitted_retry_count` (`0` or `1`). TTL is at most 60 seconds. Consumption is atomic and one logical retrieval only; an allowed retry must use the same actor/artifact/attempt/range and cannot outlive expiry. Otherwise the actor must reauthorize and mint a new ticket. Tickets never enter URLs, logs, telemetry, browser persistence, or error text.

Before the first byte, the server resolves the approved project/worktree/evidence root from durable records, opens the target with no-follow/platform-equivalent semantics, and validates the final handle—not just the input string. It rejects traversal, absolute/browser paths, UNC/device paths, alternate data streams, symlinks, junctions/reparse points, hard-link ambiguity, non-regular files, pipes/devices, root escape, ACL denial, MIME mismatch, digest mismatch, and size above the section 15.6 cap. Size is enforced before and during bounded streaming; mutation after validation aborts the response.

Responses use `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, restrictive viewer CSP, the bound MIME/digest/length, and sanitized `Content-Disposition`. Attachment is the default; inline remains limited to the section 15.6 allowlist. Generic visible-directory access, directory listing, Bridge file APIs, raw rollout paths, and arbitrary range probing are prohibited.

#### 15.8.8 Windows-first worker acceptance

Every worker-adapter, app-server protocol, lifecycle, ownership, worktree-lock, history, or artifact-ticket change must pass on the supported Windows environment before acceptance. Linux/macOS-only evidence cannot substitute. Required focused cases include:

- executable discovery and exact-version handshake for `.exe`/`.cmd`, quoted paths with spaces and Unicode, environment allowlist, and incompatible/missing binary failure;
- process-group/job-object or equivalent whole-tree shutdown on normal stop, interrupt, timeout, FastAPI crash, worker crash, and forced restart, with no orphan app-server/child process;
- managed/adopted/external/unknown lifecycle recovery across application/service restart, parallel-manager rejection, handoff acknowledgement, stale lease/lock, lock contention, and no lock-file force deletion;
- isolated worktree locking under concurrent dispatch, crash cleanup, file-in-use/antivirus contention, case-insensitive paths, long paths, Unicode paths, and deterministic safe failure for unsupported UNC/device/alternate-stream paths;
- symlink, junction/reparse, hard-link, ACL-denied, traversal, root-swap, file-growth, digest-race, oversized, MIME-spoof, expiry, replay, and cross-actor artifact-ticket tests;
- Codex version upgrade/downgrade, schema mismatch, privileged unknown method, worker/app-server restart, queued-command survival, acknowledgement reconciliation, and rollback to the previously approved binary/schema set.

Tests use labelled synthetic repositories and data only. Failure leaves durable queue/run state recoverable and marks the worker unavailable; it never weakens authorization, falls back to Bridge/CLI/rollout mutation, or silently changes process ownership.

### 15.9 Open WebUI reference-only ADR and first-party interaction requirements

This section incorporates the accepted `CCC_OPEN_WEBUI_FIT_ASSESSMENT.md` decision: **REFERENCE ONLY**. Open WebUI is a complete alternative chat/workspace platform, not a supervisor dependency or spike candidate. It must not be cloned, installed, mounted, embedded, copied, translated, linked, invoked, proxied, or used as a source of code, components, stores, routes, backend modules, authentication, RBAC, database, model gateway, RAG, files, analytics, plugins, tools, terminal/process execution, PWA assets, icons, CSS, wording, page structure, branding, or visual trade dress. No licence or branding condition from Open WebUI may enter the native product by informal reuse.

The following twelve requirements are independently authored FastAPI Bookings product contracts. Their implementation uses only the canonical React frontend, shared tokens/primitives, native v2 facade, and first-party worker adapter. References to Open WebUI document the origin of an interaction lesson, never implementation provenance or authority.

1. **Non-dependency boundary.** Architecture, lockfile, SBOM, build, runtime, route, network, database, authentication, worker, and asset scans must find no Open WebUI dependency or call path. A future general AI workspace proposal is a separate product decision, not a supervisor extension.
2. **Pattern-not-code rule.** External UI evaluation may contribute a behavior requirement or test case only. Every component, state model, accessible name, visual treatment, and error path is designed and reviewed as first-party FastAPI Bookings work; screenshots, assets, icons, copy, CSS, source, and distinctive trade dress are not copied.
3. **Chat containment.** Conversation/activity presentation is subordinate to the selected Run Detail route. A chat/thread record or message cannot represent or authorize a mission, work package, brief, assignment, run lifecycle, evidence item, audit, decision, acceptance, risk, or checkpoint.
4. **Durable queue contract.** The UI visibly distinguishes `queued`, `awaiting_writer`, `dispatching`, `worker_acknowledged`, `running`, `stopping`, and each terminal outcome; shows blocker kind such as dependency, writer availability, path lease, approval, budget, or failed input; preserves ordering and navigation; and exposes withdraw or steer only through the existing server action descriptors. Queued never means executing, browser memory never owns the queue, and urgent steer is a versioned action against one exact run.
5. **Capability-aware agent/model picker.** A searchable picker shows only server-approved author/reviewer profiles and models eligible for the selected work package. Search covers safe display name, role, and capability. Rows may expose opaque profile/model ID, availability, provider label, tool profile, limits, risk restriction, safe disabled reason, policy digest, and brief/run snapshot provenance—never credentials. `unavailable`, `not_permitted`, `not_compatible`, and `independence_conflict` remain distinct; the API re-enforces eligibility.
6. **Responsive run timeline.** Run Detail defaults to the newest bounded window, cursor-loads older history, groups related phase/tool activity, marks the live boundary and unread/new events, preserves scroll anchoring during refetch, collapses large safe output behind labelled disclosure, and keeps durable approvals/input visible rather than burying them in messages. Loading skeleton, empty, partial/error, and 320 CSS-pixel states are explicit. Long lists use bounded rendering/virtualization with stable IDs.
7. **Truthful connectivity.** The closed connection states in section 12.5, last confirmed sequence/time, bounded fresh-ticket reconnect, gap refetch, terminal exhaustion, and action disabling while stale are visible in context. Authentication, authorization, dependency, writer, timeout, conflict, malformed-event, and unknown-mutation-outcome failures have distinct safe recovery text.
8. **Offline-authority invariant.** Cached snapshots and unsaved drafts are non-authoritative. No offline dispatch, queue submission, steer, interrupt, approval, evidence verification, audit submission, acceptance, checkpoint, or other material mutation may appear successful before durable FastAPI acknowledgement. Unknown outcomes reuse the original idempotency key and reconcile under section 15.2.
9. **PWA and notification deferral.** Service-worker caching, install prompts, offline mutation/sync queues, push/browser notifications, and background execution are excluded from initial slices. A later ADR must threat-model update invalidation, stale authority, storage, session expiry, notification permission, privacy-safe opaque payloads, device loss, cache clearing, and removal. Responsive browser support does not imply installable-PWA scope.
10. **Permission explanation.** A bounded platform-owner diagnostic may explain the selected resource's effective capabilities, allowed-action reasons, and safe disabled reasons. It is read-only, never adopts additive third-party RBAC, and cannot expose another tenant/project/resource's existence. Hidden means irrelevant or undiscoverable; visible-but-disabled means known but temporarily illegal, with reason, risk, confirmation kind, and refresh path.
11. **Stable long-running navigation and completion cues.** Route-backed selection preserves mission/run filters, selected entity, cursor, and scroll anchor across in-app navigation. Background completion uses a safe badge/status cue linked to the authoritative run; it never includes prompts, source, command/output, evidence contents, customer data, or browser-invented success. Touch layouts provide visible controls with at least 44 by 44 CSS-pixel targets and no hover/gesture-only meaning.
12. **Dependency proportionality and provenance gate.** Any future proposal for a general AI UI platform must identify a concrete unmet native requirement, prove measurable benefit, pass owner/security/privacy/legal/licence/branding/SBOM/vulnerability/operations review, preserve one FastAPI control plane, and demonstrate clean removal. Open WebUI currently fails that gate and is not eligible for WP-UI-05A.

These requirements add no material mutation. Queue withdrawal, steer, interrupt, assignment/profile selection, and all consequential operations continue through the closed section 15.3 registry and backend permission. The picker and permission diagnostic are reads/draft inputs until an already-registered native mutation durably accepts them.

### 15.10 Assistant UI spike-only ADR and comparative active-run bake-off

This section incorporates the accepted `CCC_ASSISTANT_UI_FIT_ASSESSMENT.md` decision: **SPIKE FIRST / likely narrow only**. Assistant UI may be evaluated only as a lazy-loaded presentation layer for one selected Run. It cannot own authentication, authorization, tenant/project/run relationships, durable messages/threads, lifecycle, idempotency, reconnect truth, approvals/HITL, tools, evidence, audits, checkpoints, or any other domain state. Every route, package, adapter, feature flag, handler, test, and model described here is **prerequisite/not implemented** and requires the isolated WP-UI-05A brief.

#### 15.10.1 Current protocol block and eligible package boundary

The currently assessed `@assistant-ui/react-ag-ui@0.0.69` depends on `@ag-ui/client ^0.0.59`; the accepted supervisor contract uses AG-UI 1.0 and currently assessed exact `@ag-ui/client@1.0.2`. That split is incompatible. `@assistant-ui/react-ag-ui` is blocked from installation, the production adapter, and the bake-off unless an exact officially published version supports the accepted AG-UI 1.0 line at spike time and passes every section 15.7/15.10 protocol, disclosure, dependency, recovery, and removal gate without peer overrides, `--force`, `legacy-peer-deps`, duplicate React, or multiple AG-UI versions.

The only eligible current Assistant UI arm is exact-pinned `@assistant-ui/react@0.15.28` core using `ExternalStoreRuntime`. The future spike must re-resolve provenance and either freeze that exact assessed version or explicitly re-assess and freeze one later exact version; ranges are prohibited. `@assistant-ui/react-markdown`, `assistant-cloud`, `@assistant-ui/react-ag-ui`, starters, registries, templates, generative UI, MCP Apps, frontend tools, thread lists, and attachment upload are not included.

#### 15.10.2 External-store projection and ownership

- TanStack Query owns authoritative REST snapshots, versions, invalidation, and refetch status. The native section 12.5/15.8.6 event-recovery layer owns sequence, dedupe, gap detection, reconnect, and snapshot/live reconciliation.
- One small pure adapter converts only already-redacted stable-ID presentation records for the selected durable run into Assistant UI message/activity shapes. Assistant thread/message IDs are opaque correlations only and never select, create, resume, or authorize a resource.
- If the composer is enabled, `onNew` maps one validated run clarification to the existing native `respond_interaction` action descriptor, route, expected version, and UUIDv4 idempotency key. The UI does not append an authoritative optimistic message; unknown results remain `unknown` until identical-key reconciliation returns durable state.
- Native durable approval cards refetch and call `decide_approval`; framework approval/interrupt/tool APIs are not used as authority. Stop and interrupt controls map only to their named native descriptor when supplied. Missing or illegal native action means the handler and control are absent.
- `onEdit`, `onReload`/regenerate, `setMessages`, branching, generic retry, automatic pending-tool cancellation/execution, feedback, suggestions, speech, dictation, local/browser persistence, thread create/switch/delete, attachment add/send/remove, and framework-owned resume are not supplied. Retry means native refetch or identical-key reconciliation, never redispatch/regeneration.
- The arm uses unstyled primitives or Radix-flavoured composition with the application's existing shared Radix components and tokens. Base UI, a second shadcn foundation, duplicate buttons/dialogs/tooltips/scroll areas, and a starter chat shell are prohibited.

#### 15.10.3 Cloud, egress, privacy, and feature gate

Assistant Cloud is off, unconfigured, and outside the spike. Do not instantiate `AssistantCloud`, cloud thread/history adapters, anonymous cloud sessions, hosted files, reports, scores, learning, events, or telemetry; provide no Assistant Cloud URL, project/API key, token, workspace/user header, or environment variable. `assistant_ui_enabled` defaults false server-side and has an independent build/runtime kill switch. Captured browser/server traffic must prove no request to `assistant-api.com`, `assistant-ui.com`, a template/registry/analytics endpoint, CDN, or other unapproved vendor host.

Section 15.7.5 prohibited-field canaries apply unchanged to Assistant UI, its transitive packages, rendered DOM, accessibility tree/diagnostics, console, storage, network, errors, logs, traces, crash output, and generated artifacts. Markdown/code, if separately included in the spike allowlist, is an allowlisted read-only subset with raw HTML and remote media disabled, links normalized, code copy-only, and no execute/apply/edit/open-host-path action.

#### 15.10.4 Three-arm bake-off and one-runtime rule

After the section 15.7.7 preconditions and native WP-UI-05 acceptance, one hidden platform-owner-only route renders the same real labelled synthetic read-only author run in independently removable arms:

| Arm | Exact boundary | Additional authority allowed |
|---|---|---|
| Native/direct AG-UI control | Native React Run Detail over REST/TanStack/ticketed passive SSE; the section 15.7 Gate 1 exact-pinned direct AG-UI safe projection may be measured separately from pure native rendering | None |
| CopilotKit headless/runtime | Section 15.7 Gate 2 only after Gate 1 passes; smallest exact-pinned headless React/runtime layer over the same FastAPI adapter | None; optional Node runtime is transport/presentation only |
| Assistant UI core projection | Exact-pinned `@assistant-ui/react` `ExternalStoreRuntime` over the same native snapshots, safe events, recovery, and action descriptors | None; bounded view state for one selected run only |

The scripted workload is identical: identify status/phase/last durable sequence; observe safe live activity without duplicates or viewport jumps; recover the same run after disconnect, reload, offline/online, backend restart, worker restart, and candidate-runtime restart; reconcile one lost-response clarification with the original idempotency key; display and decide one durable low-risk synthetic approval including duplicate/conflict/expired cases; navigate transcript/composer/status/error/approval by keyboard and screen reader; and exercise 1,000 bounded items, markdown/code, malformed data, unknown/gap events, and privacy canaries.

The adoption result retains **one arm or none**. CopilotKit and Assistant UI must never ship together on the Runs surface, in separate supervisor routes, or as fallbacks without a new ADR proving distinct non-overlapping responsibilities, independent authority/failure ownership, combined dependency/egress/accessibility cost, and removal. “Keep both for flexibility” is prohibited.

#### 15.10.5 Measurable exit criteria, selection, and fallback

Every candidate is pass/fail; a material security, privacy, authority, durability, idempotency, recovery, or accessibility failure rejects that arm.

1. **Compatibility:** exact pins compile in the accepted React 19.2/Vite 8/TypeScript 6 environment with one React and one accepted AG-UI version, no override flags, and all protocol/type fixtures passing.
2. **Authority:** every durable read originates from native REST/TanStack Query, every material mutation maps to exactly one section 15.3 descriptor/permission, and no framework/browser record becomes authoritative.
3. **Idempotency:** disconnect, reload, double click, concurrent tab, delayed response, and deliberately lost response produce exactly one durable clarification/approval/dispatch effect and no duplicate worker execution.
4. **Reconnect:** every forced failure returns to the same durable run and sequence within 10 seconds on the agreed local test environment or presents a truthful exhausted/manual-retry state; no unbounded loop or redispatch occurs.
5. **Protocol:** accepted events satisfy the closed schema/bounds; duplicate events are ignored; gap, lower unseen sequence, unknown type/field, oversized frame, invalid delta/patch, and identity mismatch fail closed and trigger bounded native refetch.
6. **Identity and HITL:** header credentials, exact-origin CORS, object-scope isolation, non-leaking denial, durable approval reload/restart survival, version/policy/expiry display, and deterministic duplicate/conflict/expired/resolved/superseded/orphan behavior all pass.
7. **Privacy/no egress:** all section 15.7.5 canaries are absent everywhere and captured traffic contains no Assistant Cloud, CopilotKit Intelligence, analytics, learning, registry, CDN, or other unapproved vendor request.
8. **Accessibility/UI:** zero serious or critical axe findings; no keyboard trap; visible focus and correct return; bounded non-flooding status/error announcements; 200% zoom, 320 CSS pixels, touch targets, no gesture/hover-only action, and reduced motion pass. Stable IDs, cursor history, scroll anchoring, new-event markers, and deterministic error/empty/loading states pass with 1,000 bounded items.
9. **Bundle/runtime:** candidates are lazy-loaded; the main entry grows by no more than 10 KiB gzip; a candidate's total lazy-route JavaScript is no more than 75 KiB gzip above the smallest passing arm; scripted input and scroll interactions over the 1,000-item bounded history remain below 100 ms p95 on the agreed machine. Optional Node startup, memory, health, failure, and shutdown are recorded.
10. **Operator value:** across three independent scripted runs, the candidate reduces median task time or interaction count by at least 20% versus the native control with no increase in wrong-state interpretation, failed recovery, duplicate action, or accessibility error.
11. **Governance/removal:** exact lockfile diff, transitive SBOM, licences/notices, provenance/integrity, vulnerabilities, unpacked/emitted size, rapid/`0.x` upgrade policy, kill switch, and operational cost are accepted; no high/critical exploitable finding remains. Removing the arm requires no data migration and leaves native Runs/HITL/evidence/audit/build/tests passing.
12. **Repository evidence:** focused contract/component/browser tests, clean production build, zero-console/network gate, living docs, privacy/security review, independent QA, and clean-checkout reproduction pass against the exact candidate commit and synthetic fixture.

Selection is evidence-based: retain Assistant UI narrowly only if it passes every gate and materially outperforms the native/direct AG-UI control; retain CopilotKit narrowly only if its gated capability justifies the extra runtime/trust cost; retain direct AG-UI/native rendering when frameworks add no value; retain pure native REST/SSE when AG-UI itself adds no value. If more than one arm passes, choose the one with fewer authorities/dependencies, lower emitted and runtime cost, stronger recovery, better accessibility, and better operator result. The fallback in every rejection, kill-switch, upgrade failure, or incident is the already-complete native Run Detail—never the other third-party framework automatically.

#### 15.10.6 Registry and Intake invariants

This assessment adds no `ActionCode`: composer clarification uses `respond_interaction`; approval uses `decide_approval`; interrupt/steer/queue withdrawal use their existing closed codes; reads, reconnect, copy, disclosure toggles, and candidate selection are not material mutations. Any future framework feature that creates a new externally callable mutation requires the section 15.3 registry-version process before a handler or control exists.

Intake remains a structured native workflow. Assistant primitives may later collect bounded clarification text only through an existing action contract; promote, defer, decline, duplicate, mission creation, brief approval, assignment, and every lifecycle transition remain explicit native forms/actions.

#### 15.10.7 Assistant UI documentation MCP boundary

`https://www.assistant-ui.com/mcp` is developer-only, read-only documentation/tooling for an already approved WP-UI-05A spike. It is not a production supervisor runtime, dependency, endpoint, MCP/tool source, agent server, Codex bridge, worker transport, Assistant Cloud connection, or model-provider integration. It must not be bundled or configured in the canonical frontend/backend, called by the browser, FastAPI runtime, worker, resident supervisor, or deployed service, or exposed to an operator, tenant, model, or subagent through a production tool registry. It cannot own or support authentication, persistence, telemetry, threads, approvals, evidence, lifecycle, offline behavior, or recovery.

The default permitted development-time subset is read-only documentation discovery and research: `list_pages`, `get_navigation`, `search_docs`, `read_page`, and `list_templates`/`read_template` for comparison only. Returned documentation, examples, schemas, rules, and component suggestions are untrusted reference material and must be reconciled against the exact pinned package source/types, this specification, shared primitives, security boundaries, and the approved changed-file allowlist. Documentation freshness is not compatibility, licence, provenance, security, accessibility, or acceptance evidence. The local `@assistant-ui/mcp-docs-server` proxy is not installed or committed; any later proposal requires a separate exact dependency/lockfile approval.

`preview_template`, opening a generated preview URL, downloading template output, or importing any template/code/asset is prohibited by default. Each such action requires a separate explicit approved brief naming the exact template and external action, with reviewed source/file-level provenance and licence, complete data flow and egress, exact dependency/lockfile/SBOM/vulnerability/security review, accessibility and design-system review, repository no-mock proof, exact changed-file allowlist, living-documentation and independent-audit gates, and a disposal/removal plan for preview sessions, downloads, generated files, and rejected material. A preview or import may not introduce mock/simulated backend state, a duplicate application or shell/design system, hidden vendor service, unreviewed generated content, or any file outside that allowlist.

## 16. Deliberate exclusions

The first product does not include:

- a redesigned chat-first cockpit;
- production Demo Mode, fake fixtures, fake health, fake tests, or simulated runs;
- a second executor, worktree service, database, or standalone Control Centre deployment;
- direct access to host filesystem paths or arbitrary evidence artifact paths;
- raw transcript/reasoning as Project Brain memory;
- a global terminal, file explorer, diff approval, or test runner detached from a run;
- stress fuzzing as normal supervisor navigation;
- raw resident event-stream viewer;
- hard-coded competitor/tech-radar content;
- payment, refund, booking, cancellation, SMS, customer contact, deployment, merge, or push authority;
- autonomous acceptance by an author;
- widening access beyond platform owner before durable ownership/isolation is verified;
- plugin installation, boundary mutation, or force worktree cleanup in the first vertical slice;
- CopilotKit/AG-UI, Assistant UI, an optional Node runtime, Assistant Cloud, Intelligence, hosted/self-hosted vendor threads, analytics, memory, learning, vendor telemetry, chat chrome, or generative UI in any native slice;
- Open WebUI code, components, Svelte runtime, backend, auth/RBAC, database, model gateway, RAG, plugins, tools, terminal, assets, branding, page structure, PWA, or integration spike;
- service-worker caching, installable-PWA scope, offline mutation queues, browser/push notifications, or any claim that cached content is authoritative in the initial delivery slices;
- visual branding exploration, gradients, sci-fi HUD effects, or decorative animation;
- deletion of v1 or the duplicate frontend before the parity/cutover gate.

## 17. Vertical-slice delivery order

Each slice is a coherent work package with an author, independent reviewer, exact changed-file allowlist, focused tests, evidence, and acceptance decision.

### Slice 0 — P0 integration and contract freeze

Outcome:

- integrate P0 commit into the approved primary line;
- re-run trust-boundary gates;
- publish the ADR/OpenAPI decision making `/api/admin/codex/v2` and Mission terminology canonical;
- freeze v2 error, exhaustive action-registry `1.0`, idempotency, complete cutover transition graph/conditional contract, event, and bounded-disclosure conventions;
- verify the deploy-configured project and claim/quarantine migration plan;
- approve TanStack Query v5, Vitest/jsdom/Testing Library/axe, and the shared Radix AlertDialog work-package allowlist;
- declare `frontend/` canonical and freeze `codex-control-centre/frontend`.

No v2 screen is enabled before this exits.

### Slice 1 — authenticated bootstrap + Mission Board + Brief draft/approve

This is the first product slice and the only acceptable starting implementation.

Backend prerequisites:

- P0 merged and verified;
- ownership-safe project claim/programme/work-package/brief/checkpoint migrations;
- actor-scoped repositories;
- `GET /api/admin/codex/v2/bootstrap` with platform-owner capability, cutover mode, configured-project claim state, and readiness data;
- real configured-project claim/quarantine recovery with no browser path input;
- real mission list/create/detail;
- real work-package list/create;
- real brief create/read/save/validate/approve with immutable approved revisions, optimistic concurrency, audit actor, and checkpoints;
- structured errors and idempotency;
- focused negative authorization, persistence, restart, validation, immutability, and conflict tests.

Frontend outcome:

- new package and temporary v2 route;
- authenticated bootstrap/error boundary;
- application shell showing only the working `Missions` and `Work` primary destinations; no disabled roadmap destinations;
- Mission Board and Mission Overview;
- minimal Work view needed to select/create a work package;
- Brief Builder with autosave acknowledgement, validation, conflict comparison, approval confirmation, immutable approved view, and revision history;
- real loading, empty, forbidden, unavailable, offline, and unknown-status states;
- no import from v1 store or duplicate frontend.

Exit journey:

```text
platform owner signs in
  -> v2 bootstrap succeeds
  -> configured project is already claimed or is explicitly claimed
  -> creates/opens mission
  -> creates work package
  -> creates and edits brief draft
  -> validation errors are corrected
  -> approves immutable revision
  -> refresh/restart preserves all state and provenance
```

### Slice 2 — author assignment, dispatch, and Run Detail

- assignment/run persistence and policy enforcement;
- typed writer/lifecycle ownership and read-only capability projection;
- durable queue, withdraw, dispatch, steer, interrupt, release/reacquire, restart, and real worker/app-server acknowledgement;
- exact Codex version/schema/capability conformance and Windows worker recovery;
- durable run snapshot/timeline with bounded history and deterministic snapshot/live reconciliation;
- ticketed events, approvals/input, steer/interrupt/retry;
- selectively extracted activity/diff/output internals.

Slice 2 is native REST/ticketed-SSE functionality and must pass without an adapter. It implements the twelve first-party section 15.9 interaction requirements without Open WebUI code or dependencies. After its durable backend prerequisites are independently accepted, the optional comparative sections 15.7/15.10 spike may run as a separate `Slice 2A`; it is not a dependency of Slice 3 or later native delivery. No AG-UI, CopilotKit, or Assistant UI code may be merged into Run Detail until that candidate passes and receives an explicit one-arm-or-none adopt decision.

### Slice 3 — evidence ledger

- commit-bound append-only evidence;
- real diff/test/build/browser/docs read models;
- verification/rejection and criterion coverage;
- tamper and privacy tests.

### Slice 4 — independent Audit Studio and rework

- separate reviewer assignment/run/worktree/context;
- criterion matrix;
- accept/rework/human-decision gates;
- complete lineage and self-review rejection.

### Slice 5 — Project Brain

- decisions, invariants, risks, blockers, debt, and assumptions;
- immutable checkpoints and recovery;
- bounded context inclusion/omission presentation.

### Slice 6 — Operations and Intake

- truthful readiness, approvals, boundaries, telemetry, models, Skills RAG, and plugins;
- one canonical support/finding intake queue and promotion flow;
- separate confirmations for external communication or host-impact actions.

### Slice 7 — cutover and legacy retirement

- parity/reachability evidence;
- v2 becomes `/admin/coding-cockpit`;
- one-release server rollback flag;
- remove v1 runtime fixtures/store/shell and duplicate frontend only after independent acceptance.

## 18. Acceptance criteria

### 18.1 Foundation and ownership

- UI source exists only in canonical `frontend/` and imports nothing from `codex-control-centre/frontend`.
- V2 does not import the legacy store, fixtures, shell, local primitive wrappers, or modal coordinator.
- Persistent primary navigation has exactly Missions, Work, Runs, Assurance, and Context; Operations/Intake remain secondary and Slice 1 shows only working destinations.
- Every v2 request uses same-origin authenticated transport with no fixed tenant fallback and no bearer query parameter.
- Platform-owner denial occurs before supervisor data requests.
- Mission creation is impossible until the deploy-configured project is explicitly claimed; no browser route accepts or exposes a host path.
- Server cutover mode and resource control-plane ownership prevent v1/v2 concurrent mutation, including from stale tabs/direct requests.
- Every legal and illegal cutover edge, same-mode no-op, rollback/recovery guard, conditional write, atomic audit record, and unknown-outcome replay follows section 5.1 exactly.
- Every externally callable material mutation maps bijectively to one registry `1.0` `ActionCode` and one backend permission; no unregistered mutation or orphan descriptor is accepted.
- Future tenant/user records are actor-scoped and pass negative isolation tests before access is widened.

### 18.2 Mission and brief slice

- Mission Board counts and rows are real durable API data.
- A clean database shows a truthful empty state with one permitted next action.
- Draft brief saves are acknowledged; failed saves remain visibly unsaved.
- Dirty brief/audit buffers obey the memory-only route/reload/offline/session-expiry policy and never enter browser persistence.
- Validation and approval are separate server actions.
- Missing acceptance criteria, evidence kinds, verification commands, security boundaries, allowlist, prohibited actions, or delivery requirements prevent approval.
- Approved revisions are immutable and actor/time/hash attributed.
- Concurrent edit produces a compare/refresh flow with no last-write-wins overwrite.
- Unknown outcomes replay the identical request/key; concurrent retries create at most one durable side effect.
- Refresh and process restart preserve missions, packages, drafts, approved revisions, and checkpoints.

### 18.3 Run and event behavior

- UI never shows running until a durable run exists and server semantics confirm dispatch state.
- Queue acceptance, worker acknowledgement, and running are distinct durable states; withdrawal is impossible after acknowledgement.
- Writer owner, lifecycle owner, confidence, observation time, read-only status, and legal capabilities are typed; external/stale/unknown ownership fails closed.
- One lifecycle manager owns a session; release/reacquire/restart require versioned, idempotent, audited actions and app-server acknowledgement.
- Recorded and live/actionable worker state are visually distinct.
- Timeline/output/diff/test/evidence responses obey the frozen bounds, redaction, logical-path, MIME, digest, and opaque-artifact contracts.
- Each connection uses a newly minted, scope-bound one-use ticket.
- Sequence gaps, reconnects, unknown events, restart epochs, and long history recover through bounded authoritative snapshots without duplicates or viewport loss.
- Durable supervisor records outrank normalized adapter history; raw rollout diagnostics remain observed/unverified and cannot mutate state or become evidence.
- No event contains raw prompts, secrets, customer data, SMS content, unrestricted paths, or unsanitized command output.

### 18.4 Evidence and audit

- Evidence displays source run, submitted commit, safe command/artifact label, result, exit code where applicable, environment, timestamp, digest, and verification provenance.
- Artifact bytes require an expiring actor/resource/digest/MIME/disposition/size-bound ticket and pass canonical-root, no-follow/reparse/symlink, regular-file, ACL, size, digest, and safe-response-header checks.
- Browser users cannot manually create passed machine evidence.
- Author and reviewer assignment, run, thread, and worktree identities differ.
- Acceptance is impossible with missing/invalid evidence, failed mandatory criteria, stale commit, blocking finding, or failed independence.
- Rework preserves prior brief/run/evidence/audit history.
- High/critical outcomes stop for owner decision.

### 18.5 States and accessibility

- Every destination has tested loading, empty, error, forbidden, unavailable, offline/reconnect, stale/conflict, unknown-enum, and pending states as applicable.
- Unknown/stale/expired `allowed_actions` are non-actionable and direct requests are re-authorized by the server.
- Core journeys are keyboard operable with visible focus and correct restoration.
- Automated accessibility scans report no serious/critical violations on required routes.
- Manual keyboard/screen-reader/zoom/reflow checks pass at desktop, tablet, and 320px.
- Color is never the only status cue; one-accent/no-gradient baseline is maintained.

### 18.6 Cutover

- Mission -> Brief -> Author -> Evidence -> Audit -> Decision -> Checkpoint passes end to end using labelled synthetic repository data through real APIs.
- Refresh/restart recovery is demonstrated.
- Browser gate reports zero `console.error`, page errors, and 4xx/5xx application/asset failures.
- Legacy `thread`/`tab` and support-launch bookmarks translate without dropping selection or leaking resource existence.
- `v1_only`, `v2_read_only`, `v2_active`, and `rollback` browser/API tests prove one mutation authority and preserved v2 records.
- Independent QA accepts the exact commit and changed-file allowlist.
- Living documentation, migration checks, focused tests, build, commit, and push requirements are satisfied by each implementation task.

### 18.7 Optional adapter acceptance

- The native supervisor, including Run Detail and durable HITL, remains complete and passing with the adapter disabled or absent.
- Every adapter is non-production and hidden until its applicable section 15.7 gates, the comparative section 15.10 bake-off, and every exit criterion pass with independent security/QA evidence.
- FastAPI remains the sole identity, ownership, approval, idempotency, mission/run, evidence, audit, and checkpoint authority.
- Passive ticketed SSE and active authenticated POST streaming remain distinct and recover without redispatch or cross-channel credentials.
- Only the closed bounded AG-UI 1.0 subset and namespace are accepted; identity/order/dedupe/bounds/privacy/no-egress tests pass.
- `@assistant-ui/react-ag-ui@0.0.69` remains blocked because its `@ag-ui/client ^0.0.59` dependency is incompatible with accepted AG-UI 1.0; only an exact officially compatible future version may re-enter conformance review.
- The Assistant UI arm, if run, is exact-pinned core `ExternalStoreRuntime` over one selected run; generic edit/reload/regenerate/branch/tool/thread/persistence/attachment features and all Assistant Cloud configuration are absent.
- Intelligence, Assistant Cloud, and every hosted/self-hosted product-tier feature remain off unless the separate approval gate is completed.
- Exact dependency pins, SBOM, licenses/notices, vulnerability scan, compatibility evidence, measured operational cost, and native fallback are accepted before any adopt decision.
- The measured decision retains native/direct AG-UI, CopilotKit, Assistant UI, or none; CopilotKit and Assistant UI cannot coexist without a new ADR.

### 18.8 Open WebUI reference-only and native interaction acceptance

- Dependency/build/runtime/network/source scans prove no Open WebUI code, component, backend, auth/RBAC, data store, model/RAG, plugin/tool/terminal, asset, CSS, branding, wording, page structure, or PWA integration exists.
- The twelve section 15.9 requirements are implemented independently with canonical React primitives, native v2 resources, accessible names, and first-party tests.
- Run Detail proves bounded/cursor-backed grouped history, stable scroll anchoring, live-boundary/new-event markers, explicit queue/acknowledgement states, safe blocker reasons, and truthful recovery at 320 CSS pixels and 200% zoom.
- The searchable picker is server-filtered and capability-aware, preserves approved profile/model provenance, distinguishes all safe unavailable reasons, and cannot bypass author/reviewer independence or policy.
- Cached/offline UI never represents a material mutation as accepted; PWA/notification scope remains deferred; the permission diagnostic is read-only and non-leaking.
- Design/provenance review confirms no copied screenshot, icon, asset, wording, source, or distinctive trade dress and no imported licence/branding obligation.

### 18.9 Native worker adapter and Bridge reference-only acceptance

- No Codex Bridge source, binary, daemon, CLI, Web UI, API, cookie/auth model, control socket, rollout persistence, queue path, or lifecycle manager exists in the production/development dependency or call graph.
- Only the FastAPI-owned adapter may mutate Codex app-server sessions; a second writer/lifecycle manager is rejected.
- The full section 15.8 writer/capability, lifecycle-owner, queue/acknowledgement, protocol/version, recovery-source, bounded-history, and artifact-ticket contracts pass through real native APIs.
- Exact installed Codex binary/schema/capability compatibility is proven; privileged unknown methods and incompatible handshakes fail closed without losing durable work.
- Windows-first process tree, restart/recovery, worktree/lock/path/ACL, protocol upgrade/rollback, and artifact escape/race/replay tests pass.
- CopilotKit/AG-UI remains only the separately gated optional northbound adapter in section 15.7 and cannot acquire southbound writer authority.

## 19. Testing and verification gates

Implementers must query current module commands through `scripts/query_docs.py`; the commands below are contract minima, not permission to skip repository-documented gates.

### 19.1 Backend

- migration upgrade/downgrade from empty and legacy schema;
- platform-owner and negative tenant/user isolation tests;
- mission/work-package/brief persistence, state transition, revision, immutability, idempotency, and restart tests;
- project claim/quarantine/configured-root tests;
- all four cutover modes; every legal/illegal/same-mode edge; stale-v1 direct mutation; resource-control-plane; rollback/drain/recovery guards; `If-Match`/`expected_version` races; atomic audit; and unknown-outcome replay tests;
- network-drop/concurrent replay/idempotency-fingerprint/retention tests;
- dispatch acknowledgement, approval exact binding, event-ticket, event sequence/replay, evidence integrity, and independent-audit tests as their slices land;
- writer/lifecycle ownership transitions, parallel-manager rejection, durable queue/withdraw/steer/interrupt acknowledgements, recovery-source precedence, and mismatch-report tests;
- exact Codex version/schema/capability handshake, golden fixtures, privileged unknown-method rejection, and upgrade/rollback matrix tests;
- bounded disclosure, PII/secret canary, oversized/malformed content, MIME-spoof, artifact authorization, and cursor-scope tests before Run Detail;
- artifact-ticket actor/resource/digest/MIME/disposition/size/expiry/retry/root/final-handle binding and traversal/symlink/reparse/ACL/race tests;
- legacy thread/tab/support-link mapping tests;
- OpenAPI schema and TypeScript contract conformance, including the registry `1.0` mutation/action/permission bijection and bootstrap `claim_action` nullability/reason-code rules.

### 19.2 Frontend unit/component

```powershell
npm test --prefix frontend
npm run test:components --prefix frontend
npm run build --prefix frontend
```

`test:components` is a **WP-UI-02 prerequisite script**, not present in the inspected package today. WP-UI-02 adds and locks TanStack Query v5, Vitest/jsdom, Testing Library, user-event, jest-dom, axe-core/vitest-axe, the Vitest config/setup, and the shared Radix AlertDialog before component acceptance is claimed.

Required coverage includes:

- route parsing and unauthorized deep links;
- DTO/error parsing with no `any` fallback;
- request cancellation and stale-result suppression;
- mission empty/filter/pagination/readiness states;
- brief save/failure/conflict/validation/approval/immutability;
- no optimistic lifecycle transitions;
- idempotency unknown-outcome replay and unresolved UX;
- four cutover modes, every server-listed transition, unresolved cutover UX, and stale-v1 route/direct-request behavior;
- typed action descriptors, exhaustive action registry, bootstrap claim descriptor/null reason, stale/unknown/disabled reason behavior;
- dirty-buffer route/reload/offline/session-expiry/conflict handling;
- legacy deep-link translation;
- event gap/reconnect/refetch;
- distinct queue/worker-ack/running/stopping/terminal presentation, blocker reasons, and action eligibility;
- capability-aware agent/model picker search, disabled reasons, role/independence filtering, and recorded profile provenance;
- bounded/virtualized run history with stable IDs, scroll anchoring, live boundary, new-event markers, cursor history, grouped activities, and deterministic skeleton/empty/error states;
- closed `current|stale|disconnected|reconnecting|exhausted|auth_failed` connectivity presentation and last-confirmed sequence/time;
- offline non-authority, no gesture/hover-only actions, at least 44 by 44 CSS-pixel touch targets, and safe one-pane Run navigation;
- keyboard/focus/live-region behavior;
- 320px overflow and action-bar behavior.

Source-string assertions are not acceptance evidence.

### 19.3 Browser and accessibility

```powershell
python scripts/verify_zero_console_errors.py
python scripts/verify_living_docs.py --path frontend/src/pages/admin/codex-supervisor/README.md
python scripts/verify_living_docs.py --path codex-control-centre/README.md
```

The browser gate must be extended to visit v2 routes while the server flag is on and exercise real authenticated synthetic fixtures. Add axe or the repository-approved equivalent plus manual keyboard, focus, screen-reader, 200% zoom, reduced-motion, high-contrast, and 320px checks.

### 19.4 Conditional comparative adapter PoC

These gates run only in the separately approved sections 15.7/15.10 spike; they are not satisfied by native tests:

- complete identity-chain object authorization and exact-origin CORS tests for direct FastAPI and optional Node paths;
- AG-UI 1.0 schema, allowed-type, custom-namespace, ordering, dedupe, gap, bounds, invalid-delta, and unknown-field conformance;
- forced-disconnect exactly-once dispatch, REST recovery, reload/offline, worker restart, adapter restart, and optional runtime restart;
- durable approval duplicate/conflict/expiry/resolution/supersession/orphan and restart coverage;
- prohibited-field canaries and captured-network no-egress assertion across browser, FastAPI, worker adapter, and optional Node runtime;
- exact-pinned production build, focused component/browser tests, SBOM/license/notices, vulnerability scan, emitted bundle/runtime measurements, kill-switch, and adapter-removal/native-fallback test;
- Assistant UI conformance proving `ExternalStoreRuntime` projection only, stable IDs/bounded history, no optimistic authority, no generic edit/reload/regenerate/branch/tool/thread/persistence/attachment handlers, safe markdown/code when included, deterministic errors, and no Assistant Cloud/vendor egress;
- 1,000-item input/scroll performance, 320px/200% zoom, touch target, axe, keyboard, focus return, live-region, screen-reader, and reduced-motion evidence for each arm;
- identical scripted operator tasks and three independent value trials for native/direct AG-UI, CopilotKit, and Assistant UI, applying section 15.10.5 thresholds;
- separate independent evidence for direct AG-UI protocol Gate 1 and CopilotKit Gate 2; Gate 2 cannot run on a failed or conditionally accepted Gate 1. Assistant UI is separately gated and the final ADR selects one arm or none.

### 19.5 Windows-first native worker and history gates

Every WP-UI-05 worker-adapter change runs the section 15.8.8 suite on supported Windows, including whole process-tree termination/no-orphan checks, managed/adopted/external/unknown restart recovery, parallel-manager and stale-lock contention, worktree locking, long/Unicode/case-insensitive paths, safe rejection of UNC/device/alternate-stream paths, exact protocol upgrade/rollback, and queued-command/acknowledgement survival. Run Detail tests also prove the 100-item initial window, 50-item pagination, 500-item/1 MiB browser cap, stable scroll anchoring, cursor/restart-epoch boundaries, dedupe, and gap refetch.

Linux/macOS success does not waive this gate. If the approved Windows environment cannot run it, WP-UI-05 remains blocked.

### 19.6 Change control

Before any implementation commit:

- `git status --short`;
- `git diff --stat`;
- changed-file review against the task allowlist;
- `git diff --check`;
- one Alembic head and expected current revision;
- clean-checkout reproduction;
- independent audit;
- explicit staging only, then commit/push under repository policy.

## 20. Recommended implementation work packages

### WP-UI-00 — Integrate P0 and freeze contracts

Owner: security/backend.
Outcome: P0 is on the approved primary line; canonical namespace/terminology, cutover modes, idempotency, action descriptors, disclosure, frontend dependencies, error/event/version conventions, the optional-adapter/not-control-plane decisions in sections 15.7/15.10, the Codex Bridge `REFERENCE ONLY`/sole-native-worker decision in section 15.8, and the Open WebUI `REFERENCE ONLY`/first-party-pattern decision in section 15.9 are frozen by ADR/OpenAPI.
Blockers: current P0 ancestry mismatch.

### WP-UI-01 — Supervisor persistence and first-slice facade

Owner: backend/data.
Outcome: real actor-scoped project claim, mission, work-package, brief, checkpoint, idempotency, cutover, bootstrap, and first-slice endpoints.
Audit focus: isolation, migration safety, claim/quarantine, single mutation authority, immutability, revision conflict, idempotency, restart.

### WP-UI-02 — V2 transport and shell

Owner: frontend platform.
Outcome: approved native dependencies, shared AlertDialog, new canonical package, temporary route, authenticated typed client, TanStack Query layer, five-group shell, dirty-buffer guard, connection/error states. No AG-UI, CopilotKit, Assistant UI, Open WebUI, vendor cloud, component, route, or runtime is permitted.
Dependency: WP-UI-01 contract available.

### WP-UI-03 — Mission Board and Brief Builder

Owner: product frontend.
Outcome: complete first vertical slice against real APIs, including accessibility and responsive states.
Dependency: WP-UI-02.

### WP-UI-04 — First-slice independent QA

Owner: fresh reviewer.
Outcome: criterion-by-criterion security, contract, behavior, accessibility, browser, and clean-checkout verdict.
Dependency: WP-UI-03.

### WP-UI-05 — Runs and event recovery

Owner: orchestration + frontend.
Outcome: durable assignments/runs, typed writer/lifecycle ownership, queue/steer/interrupt/handoff acknowledgement, exact Codex protocol compatibility, bounded snapshot/live recovery, Windows lifecycle/lock/path safety, expiring artifact tickets, passive ticketed event replay, approvals/input, server-enforced bounded/redacted disclosure, and the twelve first-party section 15.9 interaction requirements—all through the sole first-party adapter and complete without Codex Bridge, Open WebUI, AG-UI, CopilotKit, or Assistant UI.
Dependency: first slice accepted.

### WP-UI-05A — Optional comparative active-run presentation bake-off

Owner: security/backend + frontend platform; independent privacy/security reviewer.
Outcome: execute the native/direct AG-UI control and section 15.7 Gate 1; only after Gate 1 passes, execute the CopilotKit Gate 2 arm; independently execute the exact-pinned section 15.10 Assistant UI core `ExternalStoreRuntime` arm. Apply one common workload and measurable gates, then record a single `ADOPT NATIVE/DIRECT AG-UI`, `ADOPT COPILOTKIT NARROWLY`, `ADOPT ASSISTANT UI NARROWLY`, or `REJECT ALL OPTIONAL ADAPTERS` decision. Never retain CopilotKit and Assistant UI together without a new ADR.
Dependencies: P0 ancestry proven; WP-UI-05 durable ownership/run/snapshot/idempotency/safe-event and native Run Detail prerequisites accepted; dedicated branch/worktree, exact changed-file allowlist, exact version pins, dependency/SBOM/licence/provenance/vulnerability/bundle plan, no-egress plan, kill switch, removal plan, approved synthetic scenario, independent security reviewer, and PoC approval recorded. `@assistant-ui/react-ag-ui` remains blocked unless exact official AG-UI 1.0 compatibility exists and is separately proven at spike time.
Non-dependency: native WP-UI-06 through WP-UI-08 do not wait for this optional spike and may not rely on it.

### WP-UI-06 — Evidence and independent audit

Owner: assurance.
Outcome: ledger, commit binding, reviewer separation, criterion matrix, rework/human-decision flow.

### WP-UI-07 — Brain, Operations, and Intake

Owner: context/operations.
Outcome: durable context/checkpoints and disciplined secondary capabilities.

### WP-UI-08 — Cutover and decommission

Owner: release manager + independent reviewer.
Outcome: v2 becomes canonical; legacy deep links translate; rollback preserves a single mutation authority; v1/demo/duplicate frontend retirement is backed by reachability evidence.

### 20.1 Binding migration and changed-file controls

Each work package receives a fresh branch/status check and may modify only its listed paths. If implementation proves another path necessary, stop and rebrief rather than silently expand. New filenames below are reserved contract names; changing them requires the WP-UI-00 ADR update before code work.

#### WP-UI-00 allowlist

- the exact files already contained in verified P0 commit `170f6f7eb62278bc029d39caaeda8637d4c99c59` during controlled integration;
- `docs/architecture/ADR_CODEX_SUPERVISOR_V2_FACADE.md` (new);
- `codex-control-centre/README.md`;
- `frontend/src/pages/admin/coding-cockpit/README.md` only for legacy/freeze/cutover notice;
- documentation index inputs required to register focused commands.

No migration is created in WP-UI-00. Required gates are the P0 documented focused backend tests, cockpit tests, frontend build, living-doc checks, zero-console/network gate, and clean-checkout independent audit.

#### WP-UI-01 allowlist

- `codex-control-centre/backend/models/codex.py`;
- `codex-control-centre/backend/database.py`;
- `codex-control-centre/backend/main.py`;
- `codex-control-centre/backend/schemas/v2_supervisor.py` (new);
- `codex-control-centre/backend/routers/v2_supervisor.py` (new);
- `codex-control-centre/backend/services/actor_scope.py` (new);
- `codex-control-centre/backend/services/legacy_adoption_service.py` (new);
- `codex-control-centre/backend/services/cutover_service.py` (new);
- `codex-control-centre/backend/services/idempotency_service.py` (new);
- `codex-control-centre/backend/services/supervisor_repository.py` (new);
- `codex-control-centre/backend/services/brief_service.py` (new);
- `codex-control-centre/backend/services/context_service.py` (new);
- `codex-control-centre/alembic/versions/002_identity_scope_and_runtime_lineage.py` (new);
- `codex-control-centre/alembic/versions/003_supervisor_brain_and_briefs.py` (new);
- `app/main.py` only for authenticated v2 router mount;
- `codex-control-centre/tests/test_supervisor_identity.py` (new);
- `codex-control-centre/tests/test_supervisor_briefs.py` (new);
- `codex-control-centre/tests/test_supervisor_cutover.py` (new);
- `codex-control-centre/tests/test_supervisor_idempotency.py` (new);
- `codex-control-centre/tests/test_migrations.py`;
- `codex-control-centre/README.md`.

Focused commands must be registered through living documentation, then include those five test modules, migration upgrade/downgrade/current-head checks, application import, living-doc verification, and `git diff --check`.

For first-slice unknown-outcome safety, migration `003_supervisor_brain_and_briefs.py` also creates the versioned cutover-mode record and `idempotency_records`; these cannot be deferred until run orchestration. This is an explicit refinement of the blueprint's earlier provisional migration allocation.

#### WP-UI-02 allowlist

- `frontend/package.json`;
- `frontend/package-lock.json`;
- `frontend/vitest.config.ts` (new);
- `frontend/src/test/setup.ts` (new);
- `frontend/src/components/ui/alert-dialog.tsx` (new);
- `frontend/src/components/ui/alert-dialog.component.test.tsx` (new);
- `frontend/src/App.tsx` only for the temporary v2 route;
- `frontend/src/pages/admin/codex-supervisor/index.ts` (new);
- `frontend/src/pages/admin/codex-supervisor/CodexSupervisorPage.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/routes.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/api/supervisorClient.ts` (new);
- `frontend/src/pages/admin/codex-supervisor/api/supervisorTypes.ts` (new/generated);
- `frontend/src/pages/admin/codex-supervisor/api/supervisorEvents.ts` (new);
- `frontend/src/pages/admin/codex-supervisor/api/queryClient.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/shell/SupervisorShell.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/shell/PrimaryNavigation.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/shell/ProjectContext.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/shell/ConnectionStatus.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/shared/AllowedActionButton.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/shared/RevisionConflictDialog.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/shared/DirtyBufferGuard.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/supervisor-shell.component.test.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/README.md` (new).

No migration belongs to WP-UI-02. Required gates: existing Node contracts, new Vitest component suite, build, focused live axe/keyboard smoke, living docs, zero-console/network route check, and clean-checkout independent review.

WP-UI-02 may not add `@ag-ui/*`, `@copilotkit/*`, `@assistant-ui/*`, Assistant Cloud, a Copilot Runtime, Open WebUI source/assets/packages, active-run adapter files, or adapter feature flags. WP-UI-03 inherits the same prohibition. The package/lockfile entries here are limited to the native foundations named in section 10.3.

#### WP-UI-03 allowlist

- `frontend/src/pages/admin/codex-supervisor/missions/MissionBoard.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/missions/MissionOverview.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/work/WorkQueue.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/work/BriefBuilder.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/work/BriefRevisionHistory.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/work/BriefConflictDialog.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/mission-brief.component.test.tsx` (new);
- `frontend/src/pages/admin/codex-supervisor/routes.tsx`;
- `frontend/src/pages/admin/codex-supervisor/README.md`.

No migration belongs to WP-UI-03. It consumes only accepted WP-UI-01 contracts. Required gates are Mission -> Work Package -> Brief draft/validate/approve rendered tests, accessibility/keyboard/mobile tests, full frontend tests/build, authenticated browser journey, living docs, zero-console/network, and independent review.

#### Later migration ownership

- WP-UI-05 owns `004_assignments_runs_evidence_audits.py` and only the run/orchestration/disclosure services, routers, first-party worker/protocol/lifecycle/recovery/artifact-ticket changes, Windows-focused tests, UI routes/components, and READMEs named by its approved brief. It may not add Codex Bridge source, packages, processes, APIs, auth, rollout authority, or UI.
- WP-UI-05A has no pre-approved file path. Its future brief must enumerate every FastAPI adapter, hidden canonical-frontend route/component, exact package/lockfile entry, optional Node runtime file, Assistant UI external-store adapter file, test, SBOM/licence/provenance artifact, bundle measurement, living doc, kill switch, and removal path. It may not reuse WP-UI-02's allowlist as permission and creates no new domain source of truth. Open WebUI has no spike arm or eligible file.
- WP-UI-06 completes evidence/audit behavior within `004` or a separately approved forward migration; it never edits an applied migration. It owns the assurance UI and focused integrity/independence tests.
- WP-UI-07 owns `005_durable_supervisor_events.py`; idempotency already exists from `003`. It owns brain/context, secondary Operations/Intake UI, and their focused tests/docs.
- WP-UI-08 owns `006_claimed_scope_enforcement.py`, legacy route translation/cutover files, v1 removal/decommission paths proven reachable, focused compatibility tests, and living docs. It must not rebuild earlier applied migrations.

For WP-UI-04 through WP-UI-08, including optional WP-UI-05A, the exact file-by-file allowlist and focused `query_docs.py` commands must be added to the approved brief before assignment; the package remains blocked without them. Every package requires a different independent reviewer and a clean-checkout gate.

## 21. Decisions, blockers, and definition of ready

### Decisions captured

1. New mission-first UI, not cockpit refactor.
2. Main FastAPI Bookings `frontend/` is canonical.
3. Duplicate Control Centre frontend is reference/decommission-only.
4. V2 runs alongside v1 until end-to-end acceptance.
5. `/api/admin/codex/v2` is the UI-facing facade; existing APIs are internal adapters during migration.
6. P0 plus durable backend contracts precede UI enablement.
7. First slice is authenticated bootstrap + Mission Board + work package + brief draft/validate/approve.
8. One-accent, no-gradient, shared-primitives visual baseline.
9. REST snapshots are authoritative; SSE invalidates and signals attention.
10. Platform-owner-only remains until durable ownership and isolation are proven.
11. Persistent navigation is exactly Missions, Work, Runs, Assurance, and Context; Operations/Intake are secondary.
12. Server cutover modes `v1_only`, `v2_read_only`, `v2_active`, and `rollback` use the complete guarded graph and exact conditional/idempotent contract in section 5.1 to enforce one mutation authority.
13. Identical-request replay with one actor/route/fingerprint-bound UUIDv4 key is the unknown-outcome protocol.
14. TanStack Query v5, Vitest/jsdom/Testing Library/axe, and one shared Radix AlertDialog are the selected future foundations.
15. Timeline/output/diff/test/evidence disclosure is server-bounded, redacted, typed, and artifact-ID based.
16. The configured FastAPI Bookings project must be explicitly claimed before Mission creation.
17. Brief/audit dirty buffers are memory-only and guarded across route, offline, conflict, session-expiry, and close scenarios.
18. `AllowedActionDescriptor` is typed, version-bound, expiring, and always re-authorized server-side; registry `1.0` is a closed mutation/action/permission bijection and bootstrap project claim uses that descriptor type.
19. Legacy thread/tab/support links translate through an authorized non-leaking mapping contract.
20. The accepted CopilotKit fit is `SPIKE FIRST`: an optional active-run transport/presentation adapter only, never the UI foundation, shell, TanStack Query replacement, approval authority, or control plane.
21. Passive one-use-ticket GET SSE and active authenticated POST AG-UI streaming are different channels with different credentials, cursors, and recovery semantics.
22. Only the bounded section 15.7 AG-UI 1.0 subset/custom namespace is eligible; FastAPI owns the complete actor/tenant/project/mission/thread/assignment/run mapping and durable HITL.
23. Intelligence, hosted/self-hosted threads, memory, analytics, learning, and vendor telemetry are off by default and require a separate multi-discipline owner approval.
24. No adapter dependency or UI reliance is allowed before P0 plus durable v2 run/ownership/idempotency/safe-event prerequisites, accepted native Run Detail, and an approved comparative PoC; the CopilotKit arm still obeys its Gate 1-before-Gate 2 order, and native delivery/fallback remain independent.
25. Codex Bridge is `REFERENCE ONLY`: no runtime/build dependency, source copy, authority, process topology, persistence, browser API, or UI import.
26. FastAPI owns the sole southbound Codex app-server adapter, writer, and lifecycle manager; ownership/capabilities are typed and parallel management fails closed.
27. Queue, worker acknowledgement, running, steer, interrupt, writer release/reacquire, and restart are distinct durable audited states/actions.
28. Exact Codex binary/schema/capability conformance and Windows-first process/lock/path/restart tests gate every worker-adapter change.
29. Recovery precedence is durable supervisor records, then normalized first-party adapter history, then raw rollout diagnostic only; lower sources never mutate or promote evidence.
30. Run history reconciles bounded snapshots/live events deterministically, and artifact bytes require short-lived actor/resource/digest/root-bound tickets.
31. Open WebUI is `REFERENCE ONLY`: no code, component, backend, auth/RBAC, data, model/RAG, plugin/tool/terminal, asset, licence/branding, page-structure, PWA, or spike reuse; its twelve accepted lessons are first-party native requirements.
32. Run Detail exposes a responsive bounded timeline, explicit durable queue/acknowledgement states, server-filtered capability-aware agent/model choice, safe completion/navigation cues, permission explanations, and truthful offline/reconnect/error states without becoming chat-first.
33. PWA/service-worker caching, offline mutation sync, and browser/push notifications are deferred to a separate threat-modelled ADR; cached UI is never action authority.
34. Assistant UI is `SPIKE FIRST / likely narrow only`; its current `react-ag-ui 0.0.69 -> @ag-ui/client ^0.0.59` adapter path is blocked against accepted AG-UI 1.0.2.
35. The only currently eligible Assistant UI arm is exact-pinned core `@assistant-ui/react` with `ExternalStoreRuntime`, projecting one selected Run from native REST/TanStack/event recovery. Assistant Cloud and generic edit/reload/branch/tool/thread/persistence/attachment behavior are disabled.
36. WP-UI-05A compares native/direct AG-UI, CopilotKit headless/runtime, and Assistant UI core under one workload and measurable UI/accessibility/bundle/reconnect/idempotency/value gates; the product retains one or none. CopilotKit plus Assistant UI requires a new ADR and cannot be an automatic fallback pair.

### Current blockers

- P0 is pushed but not integrated into the inspected primary branch.
- Supervisor persistence and v2 facade are not implemented.
- Current transport contains a fixed tenant fallback that v2 must not inherit.
- V1 production demo/synthetic paths remain and cannot be reused.
- Durable run history, diff/test/process read models, evidence, audits, and checkpoints remain later backend prerequisites.
- TanStack Query, Vitest/jsdom, Testing Library, axe integration, and the shared AlertDialog are approved dependencies but are not currently installed/implemented.
- The optional comparative adapter PoC is blocked by P0 ancestry, accepted native Run Detail, durable v2 ownership/run/idempotency/safe-event prerequisites, exact dependency/SBOM/licence/provenance/bundle governance, no-egress/privacy tests, and a dedicated approved brief; no AG-UI, CopilotKit, Assistant UI package, cloud/product tier, or adapter route is approved. The current Assistant UI AG-UI adapter is additionally protocol-blocked.
- WP-UI-05 is blocked until the typed writer/lifecycle model, acknowledgement records, exact Codex compatibility matrix, recovery hierarchy, bounded-history contract, artifact-ticket schema, and Windows verification commands are approved; none is implemented by adopting Codex Bridge.

### Definition of ready for the first implementation task

Implementation may begin when the approved task brief specifies:

- the exact target branch containing P0;
- exact changed-file allowlist;
- migration revision and backup/recovery plan;
- first-slice OpenAPI schemas, canonical namespace, action descriptors, idempotency, cutover, disclosure, and enum/error conventions;
- configured-project claim/quarantine procedure;
- the exact work-package allowlist from section 20.1 and registered focused commands;
- approved dependency/lockfile changes and component-test harness for WP-UI-02;
- platform-owner and negative isolation fixtures;
- focused test commands from living documentation;
- independent reviewer assignment;
- explicit confirmation that no legacy/duplicate frontend source is being extended.

The first native implementation task does not require or permit AG-UI, CopilotKit, Assistant UI, or Open WebUI. Any later adapter task must separately satisfy sections 15.7 and 15.10 preconditions, CopilotKit gate order, comparative workload, exit criteria, one-runtime decision, and exact allowlist; it cannot reinterpret readiness for WP-UI-02 or WP-UI-03. Open WebUI is never an adapter candidate.

Until then, this document is the build contract; it does not claim that the prerequisite endpoints or supervisor domain already exist.

## 22. Independent-review and accepted-assessment closure

This revision incorporates every condition from `CCC_SUPERVISOR_UI_FOUNDATION_REVIEW.md`:

| Finding | Resolution in this specification | Status |
|---|---|---|
| H1 navigation sprawl | Sections 5–7 define five primary groups; Operations/Intake are secondary; Slice 1 shows only Missions/Work | Closed |
| H2 unknown mutation outcome | Section 15.2 freezes identical-request replay, fingerprint, retention, states, UX, and concurrency/network tests | Closed |
| H3 dual mutation authority | Section 5.1 freezes four server modes, resource control-plane ownership, stale-v1 rejection, drain-only rollback, and tests | Closed |
| H4 missing UI foundations | Section 10.3 selects TanStack Query v5, Vitest/jsdom/Testing Library/axe, and one shared Radix AlertDialog; section 20.1 fixes the future allowlist | Closed |
| H5 unsafe disclosure ambiguity | Section 15.6 freezes timeline/output/diff/test/evidence/artifact schemas, redaction, bounds, MIME/disposition, and canary tests | Closed |
| M1 project claim | Section 4.4 defines deploy-configured project claim/quarantine, recovery states, and negative tests | Closed |
| M2 dirty edit recovery | Section 12.4 defines memory-only buffers, route/reload/offline/session/conflict behavior, Copy/Stay/Discard, and tests | Closed |
| M3 untyped actions | Section 15.3 defines a closed action descriptor, version/expiry/risk/confirmation semantics, server reauthorization, and tests | Closed |
| M4 legacy links | Section 5.4 defines thread/tab/resident/studio/support translation and non-leaking tests | Closed |
| L1 namespace | Section 15 makes `/api/admin/codex/v2` and Mission terminology the ADR/OpenAPI canonical contract with no alias | Closed |
| R1 incomplete cutover state/update contract | Section 5.1 now defines every legal/illegal edge, authorized actor, guards, rollback/recovery, exact GET and conditional/idempotent PUT schemas, errors, atomic audit evidence, and unknown-outcome UX | Closed |
| R2 incomplete action union/claim typing | Sections 4.4 and 15.3 define typed bootstrap claim presence/absence, the closed registry `1.0` union for every material operator mutation, exact backend permissions, and enforced OpenAPI/descriptor bijection | Closed |

All High, Medium, and Low review conditions, including re-review conditions R1 and R2, are closed at specification level. Closure means the design contract is now exact enough to brief implementation; it does not mean any prerequisite dependency, endpoint, model, migration, or UI has been implemented. Slice 0 and Slice 1 remain blocked until their stated backend, branch, clean-checkout, and independent-review gates are satisfied.

The accepted CopilotKit fit assessment's nine required amendments are binding as follows:

| Assessment amendment | Binding resolution | Status |
|---|---|---|
| 1. Optional-adapter ADR | Sections 1 and 15.7 preserve the ground-up native UI and constrain CopilotKit/AG-UI to an optional active-run lens | Incorporated |
| 2. Channel separation | Section 15.7.1 separates passive one-use-ticket GET SSE from authenticated active POST attach, including resume and unknown-outcome rules | Incorporated |
| 3. AG-UI adapter contract | Section 15.7.2 freezes the bounded AG-UI 1.0 subset, custom namespace, field/size limits, ordering/dedupe, and fail-closed behavior | Incorporated |
| 4. Ownership mapping | Section 15.7.3 maps verified actor through tenant/project/mission/supervisor thread/assignment/run to AG-UI and CopilotKit correlations | Incorporated |
| 5. HITL binding | Section 15.7.4 makes framework interrupts controllers over versioned, expiring, idempotent durable FastAPI approvals | Incorporated |
| 6. Privacy boundary | Section 15.7.5 enumerates prohibited fields and requires browser/server/runtime/storage/telemetry/network no-egress canaries | Incorporated |
| 7. Product-tier gate | Section 15.7.6 keeps Intelligence, threads, memory, analytics, learning, and telemetry off pending separate owner/security/legal/privacy/residency/operations approval | Incorporated |
| 8. Dependency gate | Section 15.7.6 requires exact pins, lockfile/SBOM/license/vulnerability/compatibility/conformance review and tested native fallback | Incorporated |
| 9. Sequencing and PoC | Sections 15.7.7, 15.10, 17, 19.4, and WP-UI-05A block adapter dependencies/UI reliance until P0 plus durable v2/native-Run prerequisites and the comparative decision; CopilotKit Gate 2 remains blocked until Gate 1 passes | Incorporated |

These amendments approve assessment incorporation only. They do not approve any dependency, endpoint, model, runtime, product tier, service, or implementation, and they do not place the optional spike on the native UI critical path.

The accepted Open WebUI fit assessment's twelve required amendments are binding as follows:

| Open WebUI assessment amendment | Binding resolution | Status |
|---|---|---|
| OW1. Non-dependency ADR | Sections 1, 15.9, 16, 18.8, and WP-UI-05 record `REFERENCE ONLY` and prohibit every Open WebUI runtime/source/component/backend/auth/data/licence/branding/plugin path | Incorporated |
| OW2. Pattern-not-code rule | Section 15.9 item 2 permits behavior requirements/tests only and requires independent first-party design, accessibility review, primitives, and tokens | Incorporated |
| OW3. Chat containment | Sections 6.3, 8.4, and 15.9 item 3 keep conversation/activity subordinate to Run Detail and outside domain authority | Incorporated |
| OW4. Durable queue contract | Sections 8.4, 15.8.3, and 15.9 item 4 distinguish every durable queue/acknowledgement state, blocker, withdraw, and steer boundary | Incorporated |
| OW5. Agent/model picker | Sections 8.4 and 15.9 item 5 freeze server-filtered search, capability metadata, safe unavailable reasons, policy/provenance, and independence enforcement | Incorporated |
| OW6. Timeline usability | Sections 7.3, 8.4, 15.8.6, and 15.9 item 6 require bounded cursor history, grouping, scroll anchor, markers, disclosure, states, and 320px behavior | Incorporated |
| OW7. Connectivity contract | Sections 12.5 and 15.9 item 7 define closed truthful connection/error states, sequence/time, ticket reconnect, gap refetch, exhaustion, and action disabling | Incorporated |
| OW8. Offline authority | Sections 12.5 and 15.9 item 8 make caches/drafts non-authoritative and require durable acknowledgement/identical-key reconciliation | Incorporated |
| OW9. PWA/notification deferral | Sections 7.3, 15.9 item 9, 16, and decision 33 defer installability, service workers, offline sync, and notifications to a separate threat-modelled ADR | Incorporated |
| OW10. Permission explanation | Sections 6.6 and 15.9 item 10 constrain the diagnostic to read-only, bounded, server-derived, non-leaking capability/action reasons | Incorporated |
| OW11. Pattern provenance | Sections 1 and 15.9 items 2/11 plus acceptance 18.8 prohibit copying screenshots/assets/icons/wording/code/trade dress and require first-party navigation/completion cues | Incorporated |
| OW12. Proportionality gate | Section 15.9 item 12 requires a concrete gap, measured value, multidisciplinary review, one authority, and clean removal; Open WebUI currently fails | Incorporated |

These Open WebUI amendments add no package, endpoint, model, action, runtime, service, licence, PWA, or implementation. They are native interaction requirements and do not make Open WebUI eligible for WP-UI-05A.

The accepted Assistant UI fit assessment's thirteen required amendments are binding as follows:

| Assistant UI assessment amendment | Binding resolution | Status |
|---|---|---|
| AU1. Alternate WP-UI-05A candidate only | Sections 1, 10.3, 15.10, 16, 17, and WP-UI-05A keep Assistant UI out of the foundation and WP-UI-02/03 | Incorporated |
| AU2. One-runtime rule | Section 15.10.4 requires selecting one arm or none and a new ADR before any CopilotKit/Assistant UI coexistence | Incorporated |
| AU3. Current protocol block | Section 15.10.1 records `@assistant-ui/react-ag-ui@0.0.69 -> @ag-ui/client ^0.0.59` as incompatible with accepted AG-UI 1.0.2 | Incorporated |
| AU4. ExternalStoreRuntime boundary | Sections 15.10.1–15.10.2 restrict exact-pinned core to one selected Run while native REST/TanStack/recovery remains authoritative | Incorporated |
| AU5. Disabled feature set | Section 15.10.2 removes cloud/thread persistence, edit, reload/regenerate, branch, tool cancellation/execution, speech, dictation, suggestions, attachments, and generic resume | Incorporated |
| AU6. Native action mapping | Sections 15.10.2 and 15.10.6 map supplied controls only to named native descriptors/idempotent endpoints; absent handlers mean absent controls | Incorporated |
| AU7. Design-system boundary | Section 15.10.2 requires unstyled/Radix composition with existing shared tokens and prohibits Base UI, second shadcn, duplicate primitives, and starter shells | Incorporated |
| AU8. Cloud/no-egress gate | Sections 15.10.3 and 15.10.5 keep Assistant Cloud/telemetry unconfigured and require kill-switch, host-capture, and prohibited-field canaries | Incorporated |
| AU9. Dependency governance | Sections 15.10.1/15.10.5 and WP-UI-05A require exact pins, lockfile, SBOM, licences/notices, provenance, vulnerabilities, bundle/runtime cost, upgrade policy, and removal | Incorporated |
| AU10. Comparative bake-off | Sections 15.10.4–15.10.5, 19.4, and WP-UI-05A compare native/direct AG-UI, CopilotKit, and Assistant UI under one workload and measurable decision rule | Incorporated |
| AU11. Assistant-specific conformance | Sections 15.10.5 and 19.4 test no optimistic authority/regeneration, safe markdown/code, stable IDs, bounded history, deterministic errors, accessibility, reconnect, and no egress | Incorporated |
| AU12. Structured Intake remains native | Section 15.10.6 limits any future Assistant primitive to clarification text; promotion/defer/decline/duplicate and all lifecycle actions remain native forms/contracts | Incorporated |
| AU13. Documentation MCP boundary | Section 15.10.7 permits `https://www.assistant-ui.com/mcp` only as developer read-only documentation during an approved spike, prohibits production/runtime/tool exposure, and separately gates every template preview/download/import with provenance, licence, data-flow, dependency/security/accessibility, no-mock, allowlist, audit, and disposal review | Incorporated |

These Assistant UI amendments approve assessment incorporation only. They do not approve a dependency, feature flag, endpoint, model, handler, cloud service, runtime, or implementation. `@assistant-ui/react-ag-ui` remains blocked, the core arm remains prerequisite/not implemented, and the native supervisor remains the fallback.

The accepted Codex Bridge fit assessment's ten required amendments are binding as follows:

| Bridge assessment amendment | Binding resolution | Status |
|---|---|---|
| 1. Worker-adapter ownership ADR | Sections 1, 4.2, and 15.8.1 make FastAPI the sole southbound app-server adapter/mutation authority and forbid parallel daemons/browser paths | Incorporated |
| 2. Writer capability contract | Sections 15.8.1–15.8.2 define typed writer/owner/lifecycle/confidence/read-only/capability state plus fail-closed release/reacquire rules | Incorporated |
| 3. Durable queue boundary | Section 15.8.3 separates queued, awaiting writer, dispatching, worker acknowledged, running, terminal, withdrawal, steer, and interrupt outcomes | Incorporated |
| 4. Protocol compatibility gate | Section 15.8.4 binds exact Codex binary/schema/adapter/capabilities to handshake, fixtures, unknown-method, upgrade, and rollback gates | Incorporated |
| 5. Recovery-source hierarchy | Section 15.8.5 makes durable supervisor records authoritative, normalized adapter history secondary, and raw rollout diagnostic/observed only | Incorporated |
| 6. Single lifecycle manager | Section 15.8.2 defines managed/adopted/external/unknown ownership, one manager lease, acknowledged handoff, and explicit restart | Incorporated |
| 7. Long-history contract | Section 15.8.6 freezes bounded newest-window/pagination/browser-memory limits and deterministic snapshot/live reconciliation | Incorporated |
| 8. Artifact-ticket contract | Section 15.8.7 binds short-lived retrieval to actor/resources/digest/MIME/disposition/size/retry and final-handle root/symlink/reparse protections | Incorporated |
| 9. Windows-first acceptance | Sections 15.8.8 and 19.5 require Windows process-tree, restart, lock/worktree, path/ACL, protocol, and artifact race/escape tests | Incorporated |
| 10. Bridge non-dependency record | Sections 1, 15.8, 18.8, WP-UI-05, and decision 25 record `REFERENCE ONLY` with no source copy, dependency, runtime, auth, persistence, or UI adoption | Incorporated |

These Bridge amendments are native design invariants, not permission to copy or depend on Codex Bridge. Every new endpoint/model/action remains prerequisite/not implemented, the existing ground-up UI decision remains binding, and the northbound active-run evaluation remains the optional comparative sections 15.7/15.10 spike.
