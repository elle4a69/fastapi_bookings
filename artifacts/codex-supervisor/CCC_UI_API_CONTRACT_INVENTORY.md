# Codex Control Centre UI v2 — API and Runtime Contract Inventory

**Audit task:** `ccc_ui_v2_contract_audit`  
**Repository:** `F:\Projects\fastapi_bookings`  
**Integrated UI:** `/admin/coding-cockpit`  
**Audit date:** 2026-10-15  
**Application baseline inspected:** `6256fc5d25e3` on `codex/business-assistant-foundation-and-migrations`  
**P0 trust-boundary commit:** `170f6f7eb62278bc029d39caaeda8637d4c99c59` on `codex/codex-supervisor-p0-trust`  
**P0 merge state:** pushed, verified, and **not an ancestor of the current primary HEAD**

## 1. Executive verdict

A ground-up UI is justified. The present cockpit is a composition of three different products:

1. a genuine Codex worker/worktree control plane;
2. an in-memory Resident Agent diagnostics prototype; and
3. a rich demo workbench whose TypeScript state model is substantially broader than the backend.

The new UI should reuse the reliable execution and governance primitives, but it should not preserve the current page hierarchy, demo-mode fixtures, fabricated view-model fields, or action buttons that have no server-side action contract.

The correct migration target is a new frontend against a versioned backend-for-frontend contract. Build it alongside the existing cockpit, then cut over only after parity and evidence gates pass. Do not couple UI v2 directly to the current route aliases or current Zustand store.

### Reliable reusable core

- Project registration constrained by workspace boundaries.
- Thread CRUD and thread-to-project association.
- Turn start, steer, interrupt, isolated worktree allocation, worker binding, and Codex app-server JSON-RPC transport.
- P0 platform-owner authorization, single-use SSE tickets, header-authenticated Resident Agent streaming, privacy-safe Skills RAG, and truthful support-ticket dispatch acknowledgement.
- Durable `Project`, `Thread`, `Turn`, `Item`, `ToolApproval`, `SubAgent`, `WorkspaceBoundary`, and `SystemSetting` tables in the separate Control Centre database.
- Approval request/resolution bridge back to the worker.
- Project file metadata listing, boundary management, telemetry settings/probes, models catalogue, Skills RAG bridge, plugin catalogue/install bridge, and diagnostics.
- Platform-owner support-ticket review and Codex launch bridge.

### Contracts that must not constrain UI v2

- Current cockpit layout, tabs, inspector/dock/modal topology, and oversized shared store.
- `demo` mode, fixture data, simulated responses, simulated completion timers, fake test names, fake terminal PIDs, and local-only diff verdicts.
- Resident Agent in-memory issue/plan/event state and its hard-coded remediation/competitor content.
- Legacy direct Resident Agent skills routes.
- Duplicate/recursive route aliases such as `/turns/turns/start`, `/events/events/ticket`, and `/codex/codex/diagnostics/deep`.
- Query-string bearer-token fallbacks in the current primary branch.
- Static model metadata as a permanent source of truth.
- Sub-agent registry rows as proof that a real child agent exists or performed work.
- Current UI fields such as branch, worktree, model, permissions, compaction, test and diff state when they are locally invented rather than returned by the server.

## 2. Scope and evidence

This audit covers only the integrated FastAPI Bookings application:

- `app/main.py`
- `app/api/routers/resident_agent.py`
- `app/api/routers/admin_support_tickets.py`
- `app/services/resident_agent/`
- `codex-control-centre/backend/`
- `frontend/src/pages/admin/coding-cockpit/`
- relevant integrated tests
- P0 commit `170f6f7e`

The separate application under `codex-control-centre/frontend/` is not the mounted FastAPI Bookings UI and is not a UI v2 source of truth. It contains parallel/duplicated frontend code and should be treated as reference-only until an explicit decommission decision.

No application code, database, runtime file, service, Git staging area, commit, or remote branch was changed by this audit. The only repository write is this report.

## 3. Runtime topology

```text
/admin/coding-cockpit (FastAPI Bookings React SPA)
        |
        +-- /api/admin/codex/* -----------------------+
        |                                             |
        |                                  mounted CCC routers
        |                                             |
        |                          codex.db: project/thread/turn/item/
        |                          approval/subagent/boundary/settings
        |                                             |
        |                          worker manager -> Codex app-server
        |                                             |
        |                          per-thread Git worktrees
        |
        +-- /api/admin/resident-agent/*
        |        in-memory audits/issues/plans/events + app DB diagnostics
        |
        +-- /api/admin/support-tickets/*
                 FastAPI Bookings support-ticket DB + launch bridge into CCC
```

The Control Centre shares the FastAPI process and main authentication stack when mounted, but it does **not** share the application database. Its entities live in `codex.db`. They currently have no tenant/user ownership columns; P0 mitigates this by restricting the integrated control plane to platform owners.

## 4. Authentication contract and P0 delta

| Surface | Current primary HEAD `6256fc5d` | P0 `170f6f7e` | UI v2 rule |
|---|---|---|---|
| Mounted projects, threads, turns, settings, models, worktrees, governance, plugins, skills | `get_current_admin`; ordinary tenant admin/manager roles may reach global CCC state | `require_platform_owner` | Depend on P0. Never expose to tenant admin roles. |
| Mounted diagnostics | Route-local `verify_auth`; liveness is public | Entire mounted diagnostics router also gets `require_platform_owner` | Public application health must remain separate from detailed CCC diagnostics. |
| CCC HTTP auth | Accepts Authorization, `X-Token`, query `token`, standalone shared secret, and several admin roles | Mounted mode delegates header token exclusively to native tenant/user resolution and `require_platform_owner`; query token rejected | UI v2 sends native Authorization/X-Tenant headers only. |
| Thread SSE | Ticket preferred, but current primary falls back to query bearer/shared secret/admin JWT | One-use, project/thread-scoped ticket is mandatory for mounted EventSource | Mint a fresh ticket for every connection/reconnection. Never place bearer tokens in URLs. |
| Resident endpoints | Most use `get_current_admin`; `/events` has no effective authentication | Every endpoint, including stream, uses `require_platform_owner`; stream uses authenticated `fetch` with bounded reconnect | UI v2 must not use current query-token `EventSource`. |
| Support tickets | Already platform-owner-only | Same boundary plus truthful worker acknowledgement | Keep platform-owner boundary. |

**Hard dependency:** integrate P0 before exposing UI v2. A new UI built on current primary HEAD would preserve the exact trust-boundary defects P0 was created to remove.

## 5. Canonical route, data, and action matrix

The paths below are the actual integrated FastAPI Bookings paths. “Canonical” identifies the route a v2 compatibility adapter may call during migration. Duplicate legacy aliases are listed separately and should not appear in new client code.

### 5.1 Projects and files

| Method and path | Request | Response/action | Current consumer | Disposition |
|---|---|---|---|---|
| `GET /api/admin/codex/projects` | none | `ProjectResponse[]`: `id`, `name`, `repo_path`, `default_branch`, timestamps, `thread_count` | Initial live-store hydration | **Keep behind v2 DTO.** Add ownership/capability fields later. |
| `POST /api/admin/codex/projects` | `{name, repo_path, id?, default_branch?}` | Upserts a project after path existence and boundary validation | Create-project action | **Keep with change.** POST currently behaves as create-or-update; v2 should use explicit create/update semantics and 201/200 codes. |
| `GET /api/admin/codex/projects/{project_id}` | path id | `ProjectResponse`; 404 if absent | API wrapper, little direct UI use | **Keep.** |
| `GET /api/admin/codex/projects/{project_id}/files?subpath=` | optional relative subpath | Up to 500 `{path,size,lines,type}` entries, depth capped at 4 | Files inspector | **Keep as metadata only.** It does not return file contents or a tree completeness marker. Do not label it a full repository browser. |

Project creation is global and path-based. The browser must never be allowed to choose arbitrary host paths outside platform-owner-managed boundaries.

### 5.2 Threads

| Method and path | Request | Response/action | Current consumer | Disposition |
|---|---|---|---|---|
| `GET /api/admin/codex/threads` | none | All `ThreadResponse[]`: `id`, `project_id`, `title`, `status`, `is_pinned`, `is_archived` | Initial hydration | **Keep with filtering/pagination.** Currently returns every global thread. |
| `POST /api/admin/codex/threads` | `{project_id,title,id?}` | Creates thread; may implicitly create a default project | Composer/support flows | **Rework.** v2 must reject unknown project IDs rather than silently manufacture projects. |
| `GET /api/admin/codex/threads/{thread_id}` | id | `ThreadResponse` | Deep-link/open ticket thread | **Keep.** |
| `PATCH /api/admin/codex/threads/{thread_id}` | any of `title,is_pinned,is_archived,status` | Updated `ThreadResponse`; terminal states cancel pending approvals | Rename/pin/archive | **Keep with enum validation and optimistic concurrency.** Current `status` is free text. |
| `DELETE /api/admin/codex/threads/{thread_id}` | id | `{message}`; cancels approvals and deletes cascaded records | Delete action | **Keep only with explicit destructive confirmation and recoverability policy.** |

There is no endpoint for listing a thread’s turns/items, no pagination, no durable context checkpoint API, and no assignment/audit/evidence relationship.

### 5.3 Turns and workers

| Method and canonical path | Request | Response/action | Current consumer | Disposition |
|---|---|---|---|---|
| `POST /api/admin/codex/turns/start` | `{thread_id,prompt,model="gpt-6.1-sol",reasoning_effort?}`; camelCase aliases are accepted | Creates durable Turn, ensures `worktrees/wt-{thread}`, binds/starts worker, sends `thread/start` and `turn/start`; returns `{turn_id,status,workspace_root}`. P0 adds `worker_acknowledged`. | Composer and issue dispatch | **Keep behind a v2 run endpoint.** Ordinary UI start is asynchronous; “active” is not proof of worker acknowledgement. |
| `POST /api/admin/codex/turns/steer` | `{thread_id,instruction,turn_id?}` | `{status:"steered"}`; 409 if no bound worker | Composer steering | **Keep.** Require exact active run identity in v2. |
| `POST /api/admin/codex/turns/interrupt` | `{thread_id,turn_id?}` | Idempotently interrupts locally/worker, cancels approvals, emits event | Stop button | **Keep.** Return an explicit terminal snapshot in v2. |
| `POST /api/admin/codex/turns/approvals/respond` | `{thread_id?,tool_call_id,approved,feedback?}` | Legacy tool-call response `{status,tool_call_id}` | Not preferred by integrated wrapper | **Deprecate.** Use governance approval IDs. |

Legacy duplicate aliases currently mounted include `/api/admin/codex/turns/turns/start`, `/turns/turns/steer`, `/turns/turns/interrupt`, and `/turns/turns/approvals/respond`. Do not carry them into v2.

Workers have no first-class HTTP collection. They are transient processes hidden behind turn actions. Diagnostics exposes only a summary of a single manager worker, while the manager can bind multiple thread workers. UI v2 needs an explicit run/worker read model before it can truthfully display worker state.

### 5.4 Event stream

| Method and canonical path | Request | Response/action | Disposition |
|---|---|---|---|
| `POST /api/admin/codex/events/ticket` | `{project_id,thread_id}` with normal auth | `{ticket,expires_at}`; P0 tickets are atomic, single-use, max TTL 300s | **Keep after P0.** |
| `GET /api/admin/codex/events/{project_id}/{thread_id}?sse_ticket=...&last_event_id=...` | one-use scoped ticket; optional last event id | SSE named events; `id:` is envelope id, `event:` is type, `data:` is only the payload | **Keep transport, replace schema contract.** |
| `POST /api/admin/codex/events/publish` | arbitrary `{project_id,thread_id,type/event_type,payload/data}` | Publishes arbitrary event | **Do not expose to UI.** Internal/test/operator capability only. |

Other aliases include `/events/stream`, `/events/events/stream`, `/events/events/{project}/{thread}`, `/events/events/publish`, and `/events/codex/events/publish`. UI v2 should consume one documented path only.

The broker is process memory, partitioned only by `thread_id`, with a 100-event deque. It loses all history on restart. `Last-Event-ID` only replays if the event remains in that deque; if absent it replays the whole remaining deque. The stored envelope contains `id`, `schema_version`, `project_id`, `thread_id`, `sequence`, `type`, `occurred_at`, and `payload`, but the SSE serializer sends only `payload` in `data:`. The current client reconstructs the envelope, so `sequence` is normally lost and becomes zero.

### 5.5 Approvals and operator interactions

| Method and path | Request | Response/action | Disposition |
|---|---|---|---|
| `GET /api/admin/codex/governance/approvals/pending?thread_id=` | optional filter | Durable pending `ToolApprovalResponse[]` | **Keep.** Add run/turn identity and expiry. |
| `POST /api/admin/codex/governance/approvals` | `{thread_id,tool_call_id,command,risk_level?,consequence?,profile?}` | Creates DB approval and emits requested events | **Internal-only in v2.** The worker/gateway should create approvals, not the browser. |
| `POST /api/admin/codex/governance/approvals/{id}/resolve` | `{approved,feedback?,scope:"once"|"session"}` | Durable resolution plus exact pending worker RPC reply | **Keep.** Enforce pending-only/idempotent semantics and actor audit. |
| `GET /api/admin/codex/governance/interactions/pending?thread_id=` | optional filter | In-memory user-input/elicitation/permission requests | **Rework before reliance.** Registry disappears on restart. |
| `POST /api/admin/codex/governance/interactions/{id}/resolve` | `{action,response}` | Replies to exact worker JSON-RPC request | **Keep behavior, make durable or explicitly ephemeral.** |
| `POST /api/admin/codex/governance/evaluate` | `{command,tool_name?,profile?}` | Risk level, approval requirement, consequence | **Internal/policy-preview only.** Never treat browser evaluation as enforcement. |

Approvals are durable, but the pending RPC handle needed to resume a worker is in memory. A database row may survive while its actionable worker request does not. UI v2 must show the distinction between “recorded pending” and “live/actionable”.

### 5.6 Sub-agent registry

| Method and path | Request | Response/action | Disposition |
|---|---|---|---|
| `GET /api/admin/codex/governance/subagents/{thread_id}` | thread id | `SubAgentResponse[]` | **Use only as registry data.** |
| `POST /api/admin/codex/governance/subagents/register` | `{thread_id,parent_thread_id?,name,role}` | Creates row and enforces maximum active count | **Internal-only.** It does not spawn an agent. |
| `POST /api/admin/codex/governance/subagents/{id}/progress` | `{progress,current_action?,status}` | Updates row | **Internal-only.** |
| `POST /api/admin/codex/governance/subagents/{id}/steer` | `{instruction}` | Mutates recorded state | **Legacy/leaky.** It does not prove delivery to a real child agent. |
| `POST /api/admin/codex/governance/subagents/{id}/stop` | none | Marks row stopped | **Legacy/leaky.** It does not terminate a real agent process. |
| `POST /api/admin/codex/governance/threads/{thread_id}/terminate-subagents` | none | Cancels registry rows and approvals | **Legacy/leaky.** |

Do not build the supervisor UI around this registry. The desired author-agent/auditor-agent orchestration requires assignments, dispatched runs, immutable briefs, role separation, evidence, and actual orchestration acknowledgements.

### 5.7 Worktrees and workspace boundaries

| Method and path | Request | Response/action | Disposition |
|---|---|---|---|
| `GET /api/admin/codex/worktrees?repo_path=` | absolute bounded repo path | Parsed Git worktree records `{path,head,branch}` | **Keep behind project ID.** The browser should not send host paths. |
| `POST /api/admin/codex/worktrees/create` | `{repo_path,branch,worktree_name}` | `{name,path,branch}` | **Internal-only in v2.** Normal creation should be assignment-driven. |
| `DELETE /api/admin/codex/worktrees/{name}?repo_path=&force=` | target and force | Removes worktree; refuses dirty unless forced | **Restrict heavily.** No ordinary UI `force` toggle. Require typed confirmation, clean-state evidence, and recoverability. |
| `GET /api/admin/codex/settings/boundaries` | none | `WorkspaceBoundary[]` | **Keep for platform-owner settings.** |
| `POST /api/admin/codex/settings/boundaries` | `{path,name?}` | Added boundary | **Keep, platform-owner settings only.** |
| `DELETE /api/admin/codex/settings/boundaries/{idOrPath}` | id or encoded path | Removal result | **Prefer ID-only v2 route.** |

`ensure_thread_worktree` contains a non-Git fallback that creates an isolated directory and copies selected top-level files. That fallback conflicts with this repository’s absolute prohibition on mock/disconnected implementations and should not be a UI-visible success condition. UI v2 should show a hard failure when a real Git worktree cannot be created.

### 5.8 Diagnostics, telemetry, models, skills, and plugins

| Method and path | Response/action | Disposition |
|---|---|---|
| `GET /api/admin/codex/health` | `{status,version,timestamp,codex_db}` | **Keep as CCC liveness.** Under P0 mounted diagnostics are platform-owner protected. |
| `GET /api/admin/codex/diagnostics/deep` | database, event broker, worker, worktree storage, telemetry status | **Keep but version response.** Current worker summary is incomplete for multi-worker state. |
| `GET /api/admin/codex/diagnostics/telemetry?collector_url=` | reachability and runtime OTel status | **Keep; avoid arbitrary URL probing from browser.** Use configured target IDs. |
| `GET/PUT /api/admin/codex/settings/telemetry` | read/update `{signoz_url,otlp_endpoint,enabled}` | **Settings-only.** URL validation/allowlisting is required. |
| `POST /api/admin/codex/settings/telemetry/test` | `{endpoint}` | reachability result | **Settings-only.** Guard SSRF/local-network probing. |
| `GET /api/admin/codex/models` and `/{model_id}` | static `ModelListResponse` / `ModelItem` | **Temporary adapter.** The list is source-code static, not live app-server/account capability discovery. |
| `GET /api/admin/codex/skills/stats` | Skills RAG index status/counts | **Keep.** |
| `GET /api/admin/codex/skills/search?query=&top_k=` | `{results}` from local Skills RAG service | **Keep.** P0 privacy-safe query derivation applies to automatic prompt enrichment; interactive search still requires deliberate user text. |
| `GET /api/admin/codex/skills/{skill_id}` | full indexed skill content | **Keep.** Never restore direct host filesystem reads. |
| `GET /api/admin/codex/plugins` | sanitized worker catalogue | **Keep as experimental.** Response explicitly says `apiStatus:"under_development"`. |
| `GET /api/admin/codex/plugins/{id}` | sanitized plugin detail | **Keep as experimental.** |
| `POST /api/admin/codex/plugins/{id}/install` | worker-mediated install plus apps needing auth | **Do not place in primary execution flow.** Installation is a separate high-impact settings action. |

Legacy diagnostic aliases containing `/api/admin/codex/codex/diagnostics/*` must not be used by v2.

### 5.9 Resident Agent routes

| Method and path | Request/response | Reality and disposition |
|---|---|---|
| `GET /api/admin/resident-agent/status` | dynamic health dict and active issues | **Extract useful diagnostics into v2 read models.** Active issues/latest audit are process memory. |
| `POST /api/admin/resident-agent/audit` | starts synchronous deep audit; returns unversioned dict | **Rework as durable audit run.** |
| `GET /api/admin/resident-agent/events` | SSE `StreamEvent` objects | **Use P0 authenticated fetch only during migration.** Separate stream, in-memory history of 150, no event IDs/resume token. |
| `POST /api/admin/resident-agent/plan-fix` | `{issue_id,issue_title?,category?,context?}` -> unversioned `RemediationPlan` dict | **Do not make a v2 core contract.** Plans are process memory and use hard-coded templates. |
| `POST /api/admin/resident-agent/execute-fix` | approval payload | Correctly returns unavailable/503; no coding worker is wired | **Remove from UI until real assignment workflow exists.** |
| `POST /api/admin/resident-agent/remote-action` | free-form command/action | Same unavailable execution path | **Remove.** |
| `POST /api/admin/resident-agent/advisory` | prompt/web/domain -> dynamic AI response | **Separate optional advisory product.** Not durable supervisor state; external web/LLM behavior needs explicit privacy controls. |
| `POST /api/admin/resident-agent/fuzz/race-condition` | `{concurrency:2..50}` | Creates synthetic database entities/bookings through global `SessionLocal` | **Exclude from cockpit v2.** It is a controlled QA tool, not a routine UI action; current lifecycle/cleanup and test-session behavior need remediation. |
| `GET /api/admin/resident-agent/tech-radar` | hard-coded competitor matrix/proposals | **Delete from v2 scope.** Static promotional content is not live system intelligence. |
| `GET /skills` and `GET /skills/{id}` | direct legacy skill discovery/read | **Deprecate.** Use `/api/admin/codex/skills/*`. P0 replaces host-file access with bounded service calls. |
| `POST /sentinel/sweep`, `GET /sentinel/status` | dynamic process-memory scheduler results | **Rework as durable scheduled audit/status.** |

The Resident Agent is not presently a durable development supervisor. Its `_active_issues`, `_plans`, `_latest_audit`, health state, scheduler state, and event history are in-process singletons. Restarting the app loses them.

### 5.10 Platform-owner support tickets

| Method and path | Request/response | Disposition |
|---|---|---|
| `GET /api/admin/support-tickets` | filters `status,tenant_id,category,limit,offset`; global ticket summaries | **Keep as a separate intake queue module.** |
| `GET /api/admin/support-tickets/{id}` | ticket, all messages including internal notes, audit events | **Keep.** Sensitive cross-tenant platform-owner surface. |
| `PATCH /api/admin/support-tickets/{id}/status` | `{status?,triage_priority?}` | updates ticket and audit log | **Keep.** |
| `POST /api/admin/support-tickets/{id}/internal-note` | `{body|message}` | internal note | **Keep.** |
| `POST /api/admin/support-tickets/{id}/tenant-reply` | `{body|message}` | tenant-visible message | **Keep with explicit external-communication confirmation.** |
| `POST /api/admin/support-tickets/{id}/launch-codex` | `{project_id?}` | `{ticket_id,codex_thread_id,turn_id}` | **Keep only with P0.** P0 waits for worker ACK and returns 503/under_review on failure rather than fabricating a queued launch. |

Support tickets are useful input to a supervisor, but they should not define the main engineering navigation model.

## 6. Event contract inventory

### 6.1 Codex worker events produced

| Canonical event type | Important payload fields | Durability |
|---|---|---|
| `turn_started` | `turn_id/turnId`, `status` | Turn row status updated. |
| `agent_message` | `text/content/chunk`, item and turn IDs, `is_streaming` | Only completed messages are persisted as `Item(type="text")`. |
| `reasoning` | `chunk/reasoning/summary`, sequence, turn IDs | Stream only. |
| `command` | command, exit code, stdout/stderr/chunk, status, cwd/duration when supplied | Persisted as `Item(type="command")`. |
| `file_change` | path/files, additions, deletions, diff, summary | Stream only in current worker persistence logic. |
| `approval_requested` | approval/tool-call IDs, command, risk, consequence, category/title/reason | Approval row is durable; worker handle is not. |
| `approval_resolved` | IDs, approved/status, feedback, scope, resolved time | Approval row durable. |
| `approval_cancelled` | IDs, status, reason, resolved time | Approval row durable. |
| `user_input_request` | request ID, method/kind/schema/permissions/etc. | Pending interaction registry is memory only. |
| `user_input_resolved` | request ID, action, status | Stream only. |
| `turn_completed` | status, completed time, turn IDs, optional summary/error | Turn row durable; not all streamed items are. |
| `turn_failed` | IDs, summary/details/error, retry indicator | Turn and error Item durable. |
| `turn_interrupted` | IDs, status, reason, actor | Turn row durable. |
| `warning`, `worker_log`, `skills_context`, `error` | diagnostic/context-specific payload | Stream only. |
| `subagent.registered`, `subagent.progress`, `subagent.steered`, `subagent.stopped`, `subagent.terminated` | registry state | Registry rows durable, but not proof of worker execution. |

### 6.2 Current frontend listener mismatch

The integrated client explicitly registers EventSource handlers for names such as `reasoning_summary` and `command_execution`, while the backend emits `reasoning` and `command`. The store can process both aliases, but EventSource never delivers a named event to `onmessage`, and the missing names are not registered.

Currently unregistered or inconsistently named events include:

- `reasoning`
- `command`
- `skills_context`
- `error`
- `worker_log`
- `user_input_resolved`
- `approval_cancelled`
- dotted sub-agent/approval compatibility events

This means the backend may truthfully emit data that the current UI silently never receives.

### 6.3 Required v2 event contract

Create one discriminated, versioned event schema and return the full envelope as SSE data:

```json
{
  "id": "evt_...",
  "schema_version": "2.0",
  "project_id": "...",
  "thread_id": "...",
  "run_id": "...",
  "sequence": 42,
  "type": "command.completed",
  "occurred_at": "...",
  "payload": {}
}
```

Requirements:

- stable documented type names, not multiple synonyms;
- monotonic sequence per run or thread;
- durable replay/checkpoint endpoint, not process-memory replay alone;
- project/thread/run authorization checked when minting tickets;
- ticket-per-connection/reconnect from P0;
- schema generation into TypeScript with exhaustive handling;
- unknown-event fallback visible in diagnostics, not silently discarded;
- explicit snapshot endpoint so UI recovery does not depend on replaying every event.

## 7. Backend data model and missing supervisor domain

### Existing durable tables

| Table | What it reliably represents | Missing for UI v2 |
|---|---|---|
| `projects` | Repository path and default branch | owner/tenant, lifecycle, policy, description, remote/ref identity |
| `threads` | Project conversation identity and simple flags | timestamps beyond create, current model/policy, assigned work package, latest run summary |
| `turns` | numbered prompt execution and terminal state | external worker turn ID, model/effort, worktree, acknowledgement, evidence and token metrics |
| `items` | selected completed messages/commands/errors | complete normalized event history; reasoning/file/test/tool records are incomplete |
| `tool_approvals` | approval record and outcome | actor, decision reason policy, expiry, live-worker actionability |
| `subagents` | manually managed registry status | assignment, real agent/thread ID, dispatch ack, artifacts, independent-auditor relationship |
| `workspace_boundaries` | allowed repository roots | actor/audit/change history |
| `system_settings` | string-valued global settings | typed validation, secret separation, actor/audit history |

### Required supervisor domain not implemented

- Project brain / compact durable context.
- Goals, decisions, assumptions, risks, blockers, and known-debt register.
- Work packages with dependencies and acceptance criteria.
- Immutable/versioned briefs with owner approval.
- Assignment records distinguishing author, reviewer, auditor, and approver.
- Agent runs with actual Codex thread/worktree identities and acknowledgements.
- Evidence ledger linking commits, diffs, commands, tests, browser gates, docs checks, and artifacts.
- Audit findings and criterion-by-criterion verdicts.
- Rebrief/remediation cycles.
- Context checkpoints and resumable handoff snapshots.
- Release/cutover gates.

The new UI should not fake these concepts in client state. Build the backend domain first, then render it.

## 8. Frontend consumer audit

### Current live consumers that map to real APIs

- `workbench/api/client.ts`: same-origin base `/api/admin/codex`, native admin token and tenant headers.
- `workbench/api/codexApi.ts`: projects, threads, turn controls, approvals/interactions, worktrees, subagents, diagnostics, boundaries, telemetry, models indirectly, skills, plugins, and ticketed SSE.
- `CodingCockpitPage.tsx`: polls Resident Agent status every 30 seconds.
- `HealthSentinels.tsx`: audit and sentinel sweep.
- `IssuesStudio.tsx`: creates in-memory remediation plan, then creates a real Codex thread/turn.
- `SkillsBrowser.tsx`: authenticated Skills RAG bridge.
- `PluginManager.tsx`: worker plugin bridge.
- `SupportTicketManagementStation.tsx`: platform-owner ticket queue and launch bridge.
- `FilesTab.tsx`: real file metadata listing.
- `TelemetryTab.tsx`: deep diagnostics.

### Current UI state that is invented, incomplete, or only event-derived

- Live thread hydration invents `module`, `branch`, `worktree`, `model`, reasoning effort, permission profile, compaction status, counts, and timestamps.
- There is no REST hydration of turns/items after reload; the timeline depends on the current browser session and at most 100 in-memory events.
- `diffFiles` is populated by demo fixtures or incoming file-change events, not a canonical Git diff snapshot API.
- Diff “Approve”, “Request Correction”, and “Decline” only call `recordDiffVerdict`, which writes a local announcement and has no backend effect.
- Tests are reconstructed from `test_run` events, but the backend normalizer does not currently produce a `test_run` contract. The “Run All” button has no action.
- Terminal entries are reconstructed from command events. Refresh and Terminate buttons have no action contract. Demo mode uses fake processes/PIDs.
- Files view returns metadata only and displays no server-provided content.
- The frontend permits `PATCH {model}`, but `ThreadUpdate` ignores/rejects no explicit model field; model choice is held locally and passed on turn start.
- Sub-agent steer/stop APIs update registry state rather than controlling a real delegated agent.
- The giant global store combines server state, synthetic projections, stream reducers, and UI state, making contract drift hard to detect.

### Demo-mode violation

The store imports production-facing fixture data and supports a persisted `codex_app_mode=demo`. It synthesizes streamed completion with `setTimeout` and contains fake test/terminal/diff content. Repository Rule 3 prohibits mock implementations and fake frontend state masquerading as backend data. UI v2 must have only real, unavailable, empty, loading, error, and permission-denied states. Storybook/test fixtures must stay outside the production call graph.

## 9. Recommended compatibility strategy

### Phase 0 — integrate and freeze trust boundaries

1. Merge or cherry-pick P0 `170f6f7e` into the approved primary line.
2. Re-run its focused backend, frontend, browser, living-doc, and independent audit gates.
3. Freeze v1 route behavior except critical fixes. Mark aliases deprecated.

### Phase 1 — create a v2 backend-for-frontend contract

Add `/api/admin/codex/v2/*` rather than making the new UI depend directly on today’s route layout. Initially, the v2 service may adapt reliable v1 services internally, but it must present:

- one response envelope and error shape;
- strict Pydantic request/response models;
- platform-owner authorization at one router boundary;
- project IDs rather than browser-supplied host paths;
- enumerated statuses and capabilities;
- pagination/cursors;
- idempotency keys for create/dispatch/decision actions;
- server-provided action availability;
- resource versions/ETags for conflicting operator actions;
- generated TypeScript types from OpenAPI.

Minimum endpoints needed before UI v2 implementation:

```text
GET    /v2/projects
GET    /v2/projects/{id}/workspace
GET    /v2/work-packages
POST   /v2/work-packages
GET    /v2/work-packages/{id}
POST   /v2/work-packages/{id}/briefs
POST   /v2/briefs/{id}/approve
POST   /v2/work-packages/{id}/assignments
POST   /v2/assignments/{id}/dispatch
GET    /v2/runs/{id}
POST   /v2/runs/{id}/steer
POST   /v2/runs/{id}/interrupt
GET    /v2/runs/{id}/timeline
GET    /v2/runs/{id}/diff
GET    /v2/runs/{id}/tests
GET    /v2/runs/{id}/processes
GET    /v2/approvals
POST   /v2/approvals/{id}/decide
GET    /v2/evidence
POST   /v2/audits
POST   /v2/audits/{id}/verdict
GET    /v2/project-brain
POST   /v2/checkpoints
POST   /v2/events/ticket
GET    /v2/events/stream
```

Names may change, but the capabilities must exist as real contracts before matching UI controls are built.

### Phase 2 — build UI v2 alongside v1

- Add a separate implementation root, for example `frontend/src/pages/admin/codex-supervisor-v2/`.
- Use a temporary platform-owner-only route such as `/admin/coding-cockpit-v2` or a server-controlled feature flag.
- Do not import the v1 store, fixtures, inspector tabs, or modal orchestration.
- Reuse only generic application design-system primitives and the authenticated API helper.
- Use a query/cache layer for server state and small isolated stores for temporary UI state.
- Make every visible action conditional on server-returned capabilities.
- Show provenance on every status: persisted record, live worker, Git evidence, test evidence, or telemetry.

### Phase 3 — dual-run and prove parity

- Contract tests compare v1 adapters and v2 read models where equivalence is intended.
- Event conformance tests publish every supported event and assert UI reducer coverage.
- Reload/reconnect tests prove timeline recovery from durable snapshots.
- Independent auditor runs verify author/auditor separation and evidence integrity.
- The zero-console/network gate visits both v1 and v2 while the feature flag is enabled.

### Phase 4 — cutover

1. Make `/admin/coding-cockpit` render UI v2.
2. Retain a platform-owner-only rollback flag for one release window.
3. Redirect legacy aliases only at the page level; do not retain duplicate API aliases indefinitely.
4. Remove v1 production fixtures, demo mode, dead components, and duplicate integrated/standalone frontend code after evidence-backed reachability analysis.
5. Keep backend v1 adapters temporarily for active workers, then remove them under a versioned deprecation plan.

## 10. Suggested UI v2 information architecture

The new UI should be organized by supervisory jobs, not by the existing pile of tools:

1. **Mission Board** — work packages, status, dependencies, blockers, owner decisions.
2. **Briefs** — immutable versions, acceptance criteria, changed-file allowlist, approval state.
3. **Runs** — assigned author/auditor agents, real worker state, worktree/branch, controls.
4. **Evidence** — commits, diffs, tests, browser gates, docs gates, runtime evidence.
5. **Audit** — findings, severity, criterion verdicts, rejection/rebrief loop, independent sign-off.
6. **Project Brain** — goals, architecture decisions, constraints, risks, checkpoints, compact context.
7. **Operations** — approvals, user-input requests, worker health, telemetry, boundaries, plugins/skills settings.
8. **Intake** — support tickets and detected issues feeding work-package creation, not occupying the primary engineering timeline.

Diff, tests, terminal/processes, files, and telemetry should be evidence views attached to a specific run—not permanent global inspector tabs pretending to have data.

## 11. Prioritized backend prerequisites

### P0 — before any UI v2 exposure

- Integrate `170f6f7e`.
- Remove query-token fallbacks from mounted clients.
- Enforce platform-owner scope everywhere in the mounted control plane.
- Keep one-use SSE ticket and authenticated Resident stream behavior.

### P1 — before meaningful UI v2 development

- Add durable supervisor domain: work packages, briefs, assignments/runs, evidence, audits, decisions/risks, checkpoints.
- Add thread/run snapshot and turn/item history endpoints.
- Define one versioned event registry and fix listener/producer mismatches.
- Add real diff, test-result, and process read models.
- Distinguish recorded state from live/actionable worker state.
- Replace host-path API inputs with project/resource IDs.
- Eliminate production demo mode and fake action buttons.

### P2 — before v1 cutover

- Complete pagination, idempotency, concurrency control, actor audit fields, and retention.
- Make model capability discovery live or explicitly configuration-backed.
- Make sub-agent dispatch real and record actual identities/acknowledgements.
- Persist pending interactions sufficiently for truthful recovery semantics.
- Resolve SSRF and destructive worktree-management surface risks.
- Decide whether Resident Agent diagnostics become v2 audit jobs or are retired.

## 12. Blocking decisions

1. **P0 integration:** UI v2 must target the P0 trust boundary, but P0 is not in current primary HEAD.
2. **Supervisor domain:** approve implementing the architecture blueprint’s durable supervisor models before UI construction.
3. **Routing:** approve a temporary parallel v2 page and `/api/admin/codex/v2` namespace.
4. **Legacy deletion:** decide whether `codex-control-centre/frontend/` is retained as standalone reference or formally decommissioned after cutover.
5. **Resident Agent:** decide which diagnostic capabilities are worth promoting to durable audit jobs; do not migrate the whole current surface.
6. **Ownership model:** platform-owner-only is safe for development, but a future multi-user operator model needs explicit owner, actor, and permission fields rather than widening access to global rows.

## 13. Final contract position

UI v2 should preserve the working execution engine, not the current cockpit. The durable unit of work must become:

```text
approved brief
  -> author assignment
  -> acknowledged isolated run
  -> evidence ledger
  -> independent audit
  -> accepted / rejected / rebriefed decision
  -> durable checkpoint
```

Today’s backend can create threads and turns and stream worker activity. It cannot yet truthfully represent that full supervisory lifecycle. Building the new visual shell before those contracts exist would recreate the same stitched-together problem with cleaner styling.
