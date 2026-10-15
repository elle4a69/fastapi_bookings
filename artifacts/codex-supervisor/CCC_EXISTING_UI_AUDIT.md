# Codex Control Centre Existing UI Audit

**Task:** `ccc_existing_ui_audit`

**Scope:** the Codex implementation integrated into FastAPI Bookings at `F:\Projects\fastapi_bookings\codex-control-centre`, its active UI at `frontend/src/pages/admin/coding-cockpit`, and the `/admin/coding-cockpit` route

**Explicit exclusion:** `F:\Projects\codex-control-centre`

**Mode:** read-only product, UX, accessibility, contract, and migration audit

**Product decision applied:** the current interface is reference material; the target supervisor interface is a new UI built from the ground up

**Application-code changes:** none

## 1. Executive verdict

The current Coding Cockpit should **not** be evolved into the Development Supervisor by adding more tabs, modals, inspector panels, or branches to `useWorkbenchStore.ts`. It is an accumulated engineering workbench rather than a coherent supervision product.

A ground-up UI is justified because the current implementation has five structural problems:

1. **The information architecture follows implementation tools, not the operator's supervisory workflow.** Projects, threads, support tickets, resident diagnostics, plugins, skills, fuzzing, settings, terminal output, diffs, and approvals all compete in one shell. There is no durable Mission -> Brief -> Author Run -> Evidence -> Independent Audit -> Decision -> Checkpoint journey.
2. **There are two frontend source trees for substantially the same workbench.** The integrated FastAPI frontend contains 63 paths corresponding to files under `codex-control-centre/frontend/src`; 27 are byte-identical and 36 have diverged or exist only on one side. The mounted application uses the FastAPI frontend copy, while the control-centre package still builds and tests its own frontend. This makes fixes, tests, and ownership ambiguous.
3. **The active state layer is a 2,419-line global store that mixes server records, local UI state, synthetic fixtures, transport, optimistic entities, event normalization, persistence, and business actions.** That is the wrong foundation for revisioned briefs, authoritative state machines, append-only evidence, and independent audit.
4. **Production code contains synthetic success paths and test fixtures.** Demo mode imports `realisticFixtures` into the live store, synthesizes turns and completion messages, uses local IDs, and supplies mock files/processes/tests. That contradicts the repository's absolute prohibition on mock implementations and is especially unsafe in an interface intended to attest that work is complete.
5. **The proposed supervisor domain is absent.** There are no implemented supervisor programmes/missions, work packages, brief revisions, assignments, agent runs, evidence artifacts, audit reviews, criteria, decisions/risks, or context checkpoints in the current frontend or backend model/API surface.

The correct approach is:

- keep the route and authenticated same-origin integration;
- preserve the proven worker, worktree, thread/turn, approval, event-ticket, skills, plugin, and diagnostics capabilities as backend/internal contracts;
- build a new task-oriented supervisor UI package against new durable supervisor APIs;
- selectively transplant only small, tested internals such as event renderers, diff rendering, approval/input forms, and authenticated transport;
- remove the duplicated standalone-style frontend, synthetic mode, and cockpit-specific component primitives after the new UI reaches functional parity.

This audit therefore supersedes the component-preservation assumptions in sections 2–4 of `CCC_UX_CONTRACT.md`. The durable workflow, security, state-machine, API, error, accessibility, and verification requirements in that document remain valid.

## 2. Audit method and evidence

The review used:

- the repository boot snapshot and current Git status;
- `CCC_ARCHITECTURE_BLUEPRINT.md` and `CCC_UX_CONTRACT.md`;
- the active route integration in `frontend/src/App.tsx`, `frontend/src/layouts/admin-layout.tsx`, and `frontend/src/components/navigation.ts`;
- all major cockpit surface, state, type, API-client, and backend-router families;
- a file-by-file hash comparison between `codex-control-centre/frontend/src` and `frontend/src/pages/admin/coding-cockpit/workbench`;
- the `baseline-ui` consistency rules and `accesslint-audit` report-mode guidance;
- static accessibility inspection. A live-DOM assistive-technology audit was not performed, so computed contrast, actual focus order, screen-reader announcements, and viewport overflow remain runtime verification work.

The primary checkout was already dirty before this audit, including an unrelated modification under `codex-control-centre/frontend`. Those files were not edited. The only report allowlist is this document.

The primary branch currently points to `6256fc5d25e3ad5c2f60d739c24446ebc4df3546`. The completed P0 trust-boundary commit `170f6f7eb62278bc029d39caaeda8637d4c99c59` is pushed on `codex/codex-supervisor-p0-trust` but is not an ancestor of the primary checkout. Findings about query-token streams and platform-owner gating describe the current primary source; the P0 implementation is the required contract to carry forward.

## 3. Current product map

The visible product is one application route, `/admin/coding-cockpit`, rendered without the usual page padding inside the FastAPI Bookings admin shell. Legacy `/admin/resident-agent` and `/admin/coding-studio` routes redirect to it.

Inside that route, the active UI is:

```text
CodingCockpitPage
└── CodexWorkbenchTab
    ├── UnifiedSidebar
    │   ├── project/thread tree
    │   ├── support-ticket switch
    │   ├── live/demo switch
    │   └── boundary + telemetry settings dialogs
    ├── ThreadHeader
    │   ├── model selector and run HUD
    │   ├── support-ticket trigger
    │   └── tools launcher
    ├── Timeline or SupportTicketManagementStation
    ├── BottomConsoleDock
    ├── Composer
    ├── Inspector
    │   ├── changes/diff
    │   ├── files
    │   ├── settings
    │   ├── agents
    │   └── tests
    ├── DiffReviewStudioModal
    ├── SecondaryToolsModals
    │   ├── support-ticket review
    │   ├── health sentinels
    │   ├── stress fuzzer
    │   ├── issues studio
    │   ├── skills browser
    │   ├── plugin manager
    │   └── resident event stream
    └── CommandPalette
```

This explains the user's description that the UI feels stuck together: the center stage, header, left rail, right inspector, bottom dock, command palette, and full-screen modal layer each contain overlapping navigation and operational concepts.

## 4. Major findings

### F1 — Critical product mismatch: no supervisor workflow exists

The target is an engineering supervisor that preserves context, produces approved briefs, delegates work, collects commit-bound evidence, dispatches an independent auditor, and records acceptance/rework decisions. The current interface is a chat/thread console plus diagnostic utilities.

Repository search found no implementation of the blueprint's core aggregates: supervisor programme/mission, project memory, work package, brief revision, agent assignment/run, context checkpoint, evidence artifact, or audit review/criteria. Consequently, a visual restyle of the current cockpit cannot deliver the intended product. The missing durable backend and typed contracts are a prerequisite for the new UI.

### F2 — High maintainability risk: two divergent frontend implementations

The integrated repository contains:

- `codex-control-centre/frontend/src`: an independently buildable workbench frontend; and
- `frontend/src/pages/admin/coding-cockpit/workbench`: the copy actually embedded in FastAPI Bookings.

Of 63 corresponding paths, 27 are identical and 36 differ or are missing on one side. The active embedded copy has acquired `UnifiedSidebar`, `BottomConsoleDock`, settings, support-ticket surfaces, and tool modals while the control-centre frontend retains its older `ProjectRail`/`ThreadSidebar` app shell. Both retain their own API, store, types, UI primitives, timeline items, tests, and fixtures.

This is not useful component reuse; it is a fork. It creates false test confidence because `codex-control-centre/package.json` still runs tests/builds against the other frontend. The rewrite must establish one canonical frontend under the FastAPI application. The internal `codex-control-centre/frontend` tree should be frozen during migration, then removed once its still-useful behavior has been extracted and replacement verification is complete.

### F3 — High truthfulness risk: synthetic production behavior

`workbench/store/useWorkbenchStore.ts` imports production state from `workbench/test/fixtures/realisticFixtures.ts`. Demo mode supplies synthetic projects, threads, subagents, diffs, incidents, boundaries, telemetry, support-ticket counts, and streaming turns. It also uses delayed simulated completion text claiming analysis and verification succeeded. `FilesTab`, `TerminalTab`, and `TestsTab` contain separate mock/demo records.

This is incompatible with the repository rule that mock implementations do not exist on this platform. In a supervisory UI it is also an evidence-integrity defect: operators must never have to determine whether a green state, completed run, test result, file list, or health indicator is genuine.

**Decision:** remove Demo Mode and all fixture imports from runtime. Demonstration data, if ever needed, must be loaded into an isolated test environment through real APIs and unmistakably labelled outside production.

### F4 — High state-integrity risk: one mutable global store owns everything

`useWorkbenchStore.ts` combines:

- server entities and local UI state;
- localStorage preferences;
- API loading and mapping;
- SSE lifecycle and event reduction;
- temporary local IDs and optimistic turns;
- thread/project CRUD;
- approvals, subagents, worktrees, telemetry, boundaries, support-ticket counts, and demo behavior;
- synthetic timestamps and inferred/default fields.

It also maps incomplete backend thread rows into invented frontend values such as branch, worktree, model, reasoning effort, permission profile, health, and timestamps. The event reducer generates client IDs when server IDs are absent. This makes rendered state look more authoritative than the data is.

The new UI needs four explicit layers:

1. typed transport and DTO validation;
2. server-state queries/caches keyed by entity and revision;
3. URL route state;
4. local view/form state.

No client reducer may synthesize an authoritative status, evidence result, verdict, run, commit, or checkpoint.

### F5 — High hierarchy problem: operational tools overwhelm the primary job

The interface gives prime navigation space to support tickets, health sentinels, stress fuzzing, AST issues, skills, plugins, event stream, terminal, files, tests, telemetry, settings, diffs, and subagents. Most open as nearly full-screen modals on top of another full-screen cockpit. They are capabilities, not the operator's main workflow.

The result has three separate navigation systems:

- project/thread tree in the left rail;
- center-stage mode switching between timeline and tickets;
- tools launched into full-screen dialogs, plus inspector and bottom-dock tabs.

Support tickets are particularly duplicated. The header sets the center view to `tickets` and simultaneously opens a separate `support_tickets` modal. The code contains both a 1,038-line `SupportTicketManagementStation` and `SupportTicketsReviewModal` for overlapping jobs.

**Decision:** supervisor navigation is entity/workflow based. Engineering utilities move to a secondary Operations area or contextual actions. Support remains a separate product area and may launch a mission or run, but it is not a supervisor center-stage mode.

### F6 — High API/contract drift

`CodexApi` provides useful endpoint wrappers, but several project/worktree/subagent/diagnostics results are typed as `any`, and the client defaults a missing tenant to `simplydemo`. The active event client still contains a bearer-token query fallback if ticket minting fails. The standalone resident `EventStream.tsx` in primary constructs a query-token URL directly.

P0 replaces the resident stream with authenticated header streaming, enforces one-use tickets for the control-centre stream, and applies platform-owner gating. Those P0 semantics are mandatory for the rewrite. The new UI must not preserve current fallback behavior or infer tenancy from a fixed string.

The new supervisor API specified in the architecture and UX contract does not yet exist. The UI must not begin with disconnected DTOs or static screens; backend migrations, authorization, and contract tests must precede each enabled workflow slice.

### F7 — Medium/High accessibility debt in the shell

Static inspection found recurring barriers:

- the two panel splitters are pointer-only `div` elements with no `role="separator"`, keyboard controls, accessible name, or current/min/max values;
- the thread title is a clickable `h1`, not a button or labelled edit control;
- the working-state stop buttons include controls as small as 16x16 and multiple 24–28px icon buttons, below the 44px touch target required by the UX contract;
- large shell regions use `select-none`, preventing normal text selection across output and operational content;
- repeated `animate-ping`/`animate-pulse` status affordances have no demonstrated reduced-motion handling;
- mobile drawers and the inspector are manually composed fixed panels rather than a consistent accessible sheet primitive;
- full-screen tool dialogs nest application-like workspaces inside modal semantics, increasing focus and Escape-key ambiguity;
- dense 9–11px labels and horizontally scrolling tabs are relied on for important state;
- the embedded workbench lacks the standalone frontend's explicit live-announcer region at its root, while announcements are stored globally;
- several transient errors are toast-only or console-only rather than remaining beside the failed action.

Positive findings worth retaining include use of Radix/shadcn primitives for many dialogs, dropdowns, tabs, tooltips, and scroll areas; multiple icon-only controls have `aria-label`; status frequently includes text as well as color; and the outer admin shell supplies a skip link and a single content target.

A live-DOM WCAG 2.2 audit is still required once the new shell exists. Source review is insufficient for focus restoration, accessible names after composition, computed contrast, and 320px overflow.

### F8 — Medium layout and visual-system inconsistency

The current shell mixes FastAPI Bookings theme tokens with hard-coded slate, indigo, emerald, amber, rose, cyan, purple, and blue utility colors. It also maintains local `workbench/components/ui` wrappers alongside the application's shared `@/components/ui` primitives. The UI uses broad `select-none`, backdrop blur, arbitrary z-index layers, extensive tiny text, pulsing badges, and multiple full-height overlays.

The new interface should use the application design tokens and shared primitives as its only foundation. One status/accent color per view, quiet data-dense layouts, tabular numbers, structural skeletons, visible inline errors, and motion limited to requested/necessary compositor feedback are sufficient. A supervisor does not need a “futuristic cockpit” visual metaphor to convey authority.

### F9 — Medium test strategy rewards structure rather than behavior

`coding-cockpit.test.ts` is dominated by source-string assertions such as checking that component names, class strings, endpoint literals, modal dimensions, and implementation phrases occur in files. These tests can pass while focus behavior, API reconciliation, route restoration, accessible names, and operator workflows fail.

The rewrite needs:

- pure contract/state tests for DTOs, revisions, idempotency, and event gaps;
- rendered component tests for empty/error/forbidden/stale/pending states;
- workflow tests for brief approval, author dispatch, evidence, independent audit, rework, and checkpointing;
- browser tests at desktop, tablet, and 320px mobile widths;
- keyboard, focus restoration, and live-region assertions.

### F10 — Medium operational actions lack a single risk language

Create/delete/archive/interrupt/approve/decline/install/launch/fuzz/sweep actions are scattered among the sidebar, header, timeline cards, settings tabs, and tool modals. Destructive and irreversible actions do not consistently use the same confirmation primitive or display server-provided capability/disabled reasons.

The new supervisor should render actions only from server `allowed_actions`/capabilities, use explicit action names, show target/impact, preserve the last confirmed state while pending, and never optimistically claim a lifecycle transition.

## 5. Surface and component disposition

The classifications mean:

- **KEEP AS CONTRACT:** preserve behavior/API/route semantics, not present markup.
- **REUSE INTERNAL:** transplant a bounded internal behavior after decoupling and testing; do not retain its current containing screen.
- **REBUILD:** the capability remains but receives a new information hierarchy and component implementation.
- **REMOVE:** delete from the production UI/runtime after migration; do not reproduce it in the new design.

| Current surface/component | Classification | Decision and boundary |
|---|---|---|
| `/admin/coding-cockpit` route and legacy redirects | KEEP AS CONTRACT | Keep the canonical route and compatible `thread` deep links. Replace the page contents and define a smaller, coherent supervisor query contract. |
| `CodingCockpitPage.tsx` | REBUILD | Retain route-entry responsibility only. New entry performs capability bootstrap, route parsing, error boundary, and workspace composition. Do not keep its resident-status poll as page-level architecture. |
| `CodexWorkbenchTab.tsx` three-column shell | REBUILD | Use as layout evidence only. New shell is mission-first and responsive; no global all-purpose inspector/dock/modal stack. |
| `UnifiedSidebar.tsx` | REBUILD | Replace project/thread/settings/support/live-demo mixture with a small application navigation and selected-mission context. |
| `ProjectRail.tsx` and `ThreadSidebar.tsx` in the internal frontend | REMOVE | Superseded predecessors of `UnifiedSidebar`; do not carry three competing sidebar models. |
| `ThreadHeader.tsx` | REBUILD | Preserve useful run identity, status, model, and stop concepts within Run Detail. Remove tool/support navigation and clickable-heading editing. |
| `Timeline.tsx` rendering pipeline | REUSE INTERNAL | Retain event ordering, unknown-item fallback, and incremental rendering ideas. Remove starter prompts and invented subagent metadata; bind to authoritative run events. |
| Timeline item family: agent message, plan, command, file change/read, tool, web, tests, warnings, failures, interruption, completion | REUSE INTERNAL | Reuse renderers selectively after output redaction/bounds and accessibility review. These become Run Detail activity, not the supervisor's home screen. |
| `ApprovalCard.tsx` and `UserInputFormItem.tsx` | REUSE INTERNAL | Valuable execution controls. Require server capabilities, durable pending/error states, and accessible validation/focus. |
| `SubAgentCard.tsx` / `SubagentTabBar.tsx` | REBUILD | Present author/reviewer assignment and run provenance, not ad-hoc tabs with inferred status. |
| `Composer.tsx` | REBUILD | A free-form composer remains only for an active run's steer/input flow. Mission/brief/audit state changes use structured forms and actions. |
| `Inspector.tsx` | REBUILD | Replace global five-tab inspector with route-specific contextual panels/sheets. |
| `ChangesTab.tsx` and `DiffReviewStudioModal.tsx` / `DiffViewer.tsx` | REUSE INTERNAL | Keep diff parsing/rendering and file navigation after provenance, commit binding, keyboard, and large-diff behavior are verified. Embed contextually in Run and Audit. |
| `FilesTab.tsx` | REBUILD | Remove demo files. If repository browsing remains necessary, use a scoped, lazy, read-only project browser within Run/Brief context. |
| `TestsTab.tsx`, `TerminalTab.tsx`, `TelemetryTab.tsx` | REBUILD | Show server-captured run output, evidence, and diagnostics. Do not infer empty arrays as success or use demo records. |
| `SettingsInspectorTab.tsx` and sidebar settings dialog | REMOVE | They duplicate each other. Replace with one platform-owner Operations/Settings page outside the primary mission workflow. |
| `BottomConsoleDock.tsx` | REUSE INTERNAL | Reuse collapsed/expanded output behavior inside Run Detail only. It is not global navigation and never serves as evidence. |
| `CommandPalette.tsx` | REBUILD | Retain the command-palette concept, but populate it from current route and server-allowed actions. |
| `SecondaryToolsModals.tsx` | REMOVE | Remove the “application inside full-screen modal” pattern. Capabilities get contextual panels or Operations routes. |
| `HealthSentinels.tsx` | REBUILD | Convert to a compact, truthful Operations health view and mission intake signal. Remove from the primary header/tool modal. |
| `IssuesStudio.tsx` | REBUILD | Resident findings should create durable issue/memory/work-package proposals. Remove local approval/execution state. |
| `StressFuzzer.tsx` | REMOVE from primary UI | Keep the backend diagnostic only if independently authorized and safe; expose it through controlled Operations/testing workflows, not a permanent cockpit feature. |
| `SkillsBrowser.tsx` | REUSE INTERNAL | Reuse authenticated search/read calls. Present skills contextually in brief/assignment configuration or a small capability library. |
| `PluginManager.tsx` | REBUILD | Plugin installation/authorization is platform configuration, not mission work. Preserve real API behavior in Operations with explicit risk and result states. |
| `EventStream.tsx` | REMOVE | Raw resident SSE is not a user-facing primary feature. Replace with durable, scoped supervisor activity and use P0 transport internally. |
| `SupportTicketManagementStation.tsx` | REBUILD outside supervisor core | Preserve the real support-ticket API and Codex launch bridge, but make Support a distinct workspace/route with one canonical interface. |
| `SupportTicketsReviewModal.tsx` | REMOVE | Duplicates the management station and creates two simultaneous support contexts. |
| local `workbench/components/ui/*` wrappers | REMOVE | Use FastAPI Bookings shared `@/components/ui` primitives. Add a shared primitive only when the application does not already supply it. |
| `workbench/modelCatalog.ts` | KEEP AS CONTRACT / REUSE INTERNAL | Keep one validated model catalog aligned with the backend endpoint and account capabilities. Do not treat localStorage as authority. |
| `workbench/api/client.ts` | REUSE INTERNAL | Preserve same-origin authenticated requests, timeouts, and normalized errors. Remove fixed-tenant fallback; add structured errors, AbortSignal, revision, and idempotency support. |
| `workbench/api/codexApi.ts` | REBUILD around typed contracts | Retain endpoint family knowledge and ticket-first event behavior. Eliminate `any`, query-token fallback, duplicate `/codex` path normalization ambiguity, and untyped responses. |
| `workbench/types/workbench.ts` | REBUILD | Split transport DTOs, domain view models, and event payloads. Unknown enums remain non-actionable; do not blend fixture fields with server fields. |
| `workbench/store/useWorkbenchStore.ts` | REMOVE and replace | Do not refactor incrementally. Replace with bounded server-query modules, pure selectors/reducers, URL state, and local form/view stores. |
| `workbench/test/fixtures/realisticFixtures.ts` runtime import and Demo Mode | REMOVE | Test fixtures stay test-only. Remove local success simulation and live/demo switch from production. |
| `coding-cockpit.test.ts` source-string assertions | REMOVE and replace | Preserve contract intent as rendered/unit/browser tests; do not assert implementation text. |
| `codex-control-centre/frontend` internal duplicate app | REMOVE after parity gate | Freeze as reference during migration. Delete after extracted internals and replacement tests/build are in place; update root scripts to test the canonical FastAPI frontend. |

## 6. Backend and API capabilities that must remain stable

The UI rewrite must not destabilize these working capabilities:

1. **Mount and trust boundary**
   - same-origin `/api/admin/codex` under FastAPI Bookings;
   - FastAPI Bookings authentication and platform-owner policy from P0;
   - no dependency on a separate control-centre server or the excluded repository.

2. **Execution substrate**
   - project registration and validated repository boundaries;
   - thread/turn persistence;
   - isolated Git worktree creation/reuse and worker binding;
   - real Codex app-server dispatch acknowledgement, steering, interruption, and terminal state;
   - model/reasoning selection validated by the server.

3. **Human-in-the-loop governance**
   - persisted tool approvals;
   - interaction/user-input response transport;
   - subagent registration, progress, steering, stopping, and parent-thread relationship;
   - explicit risk/capability results rather than UI-only permission checks.

4. **Truthful live updates**
   - one-use, scope-bound event tickets;
   - authenticated resident streaming from P0 where still required;
   - reconnect/replay semantics and stable event IDs/sequences;
   - REST as the authoritative state after gaps or reconnects.

5. **Inspection internals**
   - bounded project file listing;
   - diagnostics/readiness and telemetry configuration/testing;
   - plugin catalog/detail/install/authorization results;
   - Skills-RAG stats/search/read through the bounded backend bridge;
   - support-ticket launch bridge that reports dispatch failure truthfully and links only an acknowledged turn.

6. **Required new supervisor contract before UI enablement**
   - actor-scoped programmes/missions and memberships;
   - revisioned briefs and work packages;
   - assignments/runs linked to threads, turns, worktrees, baseline and result commits;
   - append-only evidence with digests, bounded scrubbed summaries, and criterion links;
   - independent audit records and server-enforced author/reviewer separation;
   - decisions, risks, project memory, durable events, and immutable checkpoints;
   - capabilities/`allowed_actions`, structured errors, revision conflicts, and idempotency.

What need not remain stable is the current component shape, modal pattern, duplicate endpoint aliases, locally inferred DTO fields, Demo Mode, or the standalone-style frontend build.

## 7. Minimal target information architecture

The new interface should make one question dominant: **What work should happen next, who is doing it, and what proves it is acceptable?**

Use five primary destinations, not the current tool inventory:

1. **Missions**
   - programme list and mission overview;
   - status, next safe action, blockers, risk, progress, latest checkpoint.

2. **Work**
   - work packages and dependencies;
   - structured brief builder, revisions, validation, approval;
   - dispatch preparation and bounded assignment policy.

3. **Runs**
   - author and reviewer runs in one lineage-aware list;
   - selected run detail with activity, approvals, steer/stop, scoped output, diff, and captured evidence;
   - the only place where reusable timeline/composer/dock internals appear.

4. **Assurance**
   - independent audit matrix and reviewer provenance;
   - evidence ledger;
   - accept, request rework, or human-decision actions guarded by server rules.

5. **Context**
   - compact project brain;
   - decisions, risks, blockers, known limitations;
   - checkpoint history and next recommended action.

Secondary destinations:

- **Operations:** health, diagnostics, boundaries, telemetry, plugins, skills, event connection state. Platform-owner only and outside the normal mission loop.
- **Support:** one canonical support-ticket workspace. It may create/launch a scoped work package/run but does not share center-stage state with supervisor missions.

On desktop, a compact primary navigation and one contextual detail region are enough. On tablet, the contextual region becomes a sheet. On mobile, use one pane at a time with route-backed selection. Do not commit to final colors, typography, density, or pane proportions until the next design task validates workflows.

## 8. Migration boundary

The rewrite should use a strangler boundary rather than modifying the current workbench in place.

### Boundary rules

- One canonical route remains `/admin/coding-cockpit`.
- Create a new, isolated frontend package such as `frontend/src/pages/admin/coding-cockpit/supervisor-v2/` only after its first real backend slice exists.
- The new package may import only:
  - shared FastAPI Bookings UI primitives/tokens;
  - the authenticated base API transport;
  - explicitly extracted, framework-neutral renderer internals;
  - typed supervisor DTOs generated or maintained from the real API contract.
- It must not import `useWorkbenchStore`, demo fixtures, the old shell, local workbench UI wrappers, or old modal/navigation state.
- Old Workbench remains reachable as a clearly labelled legacy execution view during migration, preferably through a feature flag or explicit `view=legacy-workbench`, not embedded inside the new supervisor shell.
- Each new destination remains hidden until its database migration, authorization, API, tests, loading/empty/error states, and browser checks are real.
- The route switches its default from legacy workbench to Missions only after Mission -> Brief -> Author Dispatch is operational.
- The legacy workbench is retired only after Run Detail supports event activity, approvals/input, steer/stop, diff, output, and evidence capture.
- Delete the duplicate `codex-control-centre/frontend` and old embedded workbench tree only after a parity inventory, route rollback plan, focused tests, full build, zero-console/network gate, living docs, and independent audit.

### Proposed implementation slices

1. **Contract foundation:** merge P0; implement supervisor database/authorization/bootstrap/mission/brief contracts and migrations.
2. **New shell + Missions/Work:** capability bootstrap, route state, mission board/overview, brief builder, real empty/error states.
3. **Runs:** dispatch and run lineage; extract only necessary timeline, approval, diff, and output internals.
4. **Assurance:** evidence ledger, independent audit, verdict/rework gates.
5. **Context:** brain, decisions, risks, checkpoints.
6. **Operations/Support separation:** relocate the few utilities that remain justified and consolidate support.
7. **Legacy retirement:** remove demo mode, old store/shell/modals/duplicate UI trees and replace source-string tests.

## 9. Blocking prerequisites and risks

### Blockers to implementation

1. **P0 is not merged into the primary branch.** New UI work must be based on the platform-owner, truthful-dispatch, privacy-safe, ticketed-stream contract, not the current primary implementation.
2. **Supervisor persistence and APIs do not exist.** A frontend-only build would violate the no-mock and fully-plumbed requirements.
3. **Canonical frontend ownership must be declared.** The FastAPI `frontend` is the target; the internal control-centre frontend must be frozen as reference to prevent parallel edits.
4. **The current architecture and UX documents still direct implementers to retain the existing shell.** Their durable domain/contract sections remain useful, but the component-preservation clauses must be amended before implementation briefs are issued.

### Risks to manage

- Retiring the old store too early could lose working event normalization and approval flows; extract behind tests first.
- Running both UIs against mutating endpoints without clear feature gates could create conflicting actions.
- A purely visual redesign before backend state machines exist would recreate the current problem with newer styling.
- Support, diagnostics, and plugin administration can easily creep back into primary navigation unless their product boundaries are explicit.
- Event payloads and evidence output must be bounded/scrubbed server-side; a new renderer cannot make raw sensitive output safe.

## 10. Recommended next design task

Create **`CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md`** as a product/interaction specification, not production code and not a high-fidelity visual design.

That task should:

1. amend the old UX contract to record that the existing shell/component-preservation requirement is superseded;
2. define the route map, responsive navigation model, page hierarchy, and entity-selection behavior for Missions, Work, Runs, Assurance, Context, Operations, and Support;
3. produce low-fidelity wireframes for the seven critical states:
   - mission board;
   - mission overview/next action;
   - brief builder;
   - author dispatch/run detail;
   - audit studio;
   - evidence ledger;
   - project brain/checkpoint;
4. specify loading, empty, forbidden, disconnected, conflict, validation, pending, and unknown-status behavior for each;
5. define a component/data ownership matrix and exact extraction candidates from the old workbench;
6. define accessibility acceptance criteria, including keyboard-resizable regions only where resizing remains justified;
7. map each screen action to a real backend endpoint/capability and mark unavailable contracts as blocked rather than mocking them;
8. finish with an implementation-ready first vertical slice: P0 + supervisor bootstrap + Missions + Brief draft/approval, with changed-file allowlists and verification gates.

Detailed visual styling should follow that foundation spec, once the workflow and backend contracts are approved. The priority is a truthful and understandable operating model, not a prettier cockpit.

## 11. Audit conclusion

The user assessment is correct: the present interface is an accumulation of individually plausible pieces, but the composition is not an effective resident development supervisor. Its valuable assets are below the page level—worker orchestration, worktrees, approvals, ticketed events, typed event renderers, diff inspection, skill/plugin bridges, and truthful support dispatch.

The new UI should be built from the ground up around durable missions and verifiable delegation. Preserve the operational substrate, extract only bounded internals, and retire the current shell, global store, synthetic runtime behavior, duplicated frontend, and tool-modal information architecture.
