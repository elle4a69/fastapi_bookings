# Independent Review — Codex Development Supervisor UI Foundation

**Reviewed artifact:** `CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md`  
**Final revision reviewed:** SHA-256 `CF9DB16A10D51AE3EE09949C63456A42981DD92007A4DB53C654343B93ED0D29`  
**Earlier accepted revision reviewed:** SHA-256 `CF57B7980231789351EC5C87E4876DFC5E9DDEFC7019291539F0D51FECE2FD4D`  
**Earlier amended revision reviewed:** SHA-256 `AD8B3BE61FBF3EEAE2E38514F592A882E67C99350353E29C2A2B43510E574AA6`  
**Review task:** `ccc_ui_v2_spec_review`  
**Review mode:** independent, read-only design/contract audit  
**Application-code changes:** none  
**Date:** 2026-10-15 (Australia/Sydney)  
**Verdict:** **ACCEPTED**

## 1. Scope and decision

The specification was reviewed against:

- the user's binding direction to build a ground-up interface and use the current cockpit only as reference;
- `CCC_EXISTING_UI_AUDIT.md`;
- `CCC_UI_API_CONTRACT_INVENTORY.md`;
- `CCC_ARCHITECTURE_BLUEPRINT.md`;
- `CCC_SECURITY_BASELINE.md`;
- repository `AGENTS.md`;
- the current primary checkout's routing, frontend package/tooling, shared UI primitives, legacy cockpit, and mounted backend surface.

Skills-RAG guidance used: `accesslint-audit` in report mode and `baseline-ui`. No live-DOM audit was appropriate because this is a specification review and UI v2 does not exist.

The original review accepted the product direction but required the conditions in sections 3 and 4 before implementation. Section 7 records the first closure audit. Section 8 records the final audit of the revision identified above and supersedes all earlier verdicts. Nothing in this acceptance authorizes frontend-only scaffolding, mock endpoints, fixture-backed screens, invented contracts, or weakening P0.

## 2. Positive findings

The following decisions are sound and must be preserved:

1. The UI is explicitly a new mission-first implementation, not a reskin or incremental extension of the current cockpit.
2. `frontend/` is correctly declared canonical; `codex-control-centre/frontend/` is reference/decommission-only.
3. The new UI is prohibited from importing the legacy global store, runtime fixtures, shell, inspector, modal coordinator, local primitive fork, or query-token transport.
4. No screen/action is enabled before its real database model, migration, authorization, state transition, API, and error behavior exist.
5. The specification preserves P0 requirements: platform-owner-only exposure, one-use event tickets, no query bearer token, truthful dispatch, bounded Skills-RAG, and explicit unavailable/unknown states.
6. REST snapshots are authoritative and SSE is used for invalidation/attention rather than as durable truth.
7. Brief immutability, author/reviewer separation, commit-bound evidence, criterion-level audit, rework lineage, and checkpoints match the supervisor architecture.
8. Loading, empty, forbidden, conflict, offline, reconnect, approval, destructive, responsive, keyboard, focus, and accessibility states receive materially better coverage than the current UI.
9. The parallel-route strangler strategy is safer than editing the legacy cockpit in place.
10. The spec accurately states current primary reality: HEAD `6256fc5d25e3ad5c2f60d739c24446ebc4df3546` does not contain P0 `170f6f7eb62278bc029d39caaeda8637d4c99c59`; no v2 facade or durable supervisor domain exists; the legacy client still contains `simplydemo`, `any`, fixture-backed runtime state, and inferred entities.

## 3. Severity-ranked findings

### High — H1: Eight primary destinations recreate the navigation sprawl the rewrite is meant to remove

**Evidence:** the spec declares eight destinations in primary navigation (`CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md:206-303`), including `Briefs`, `Evidence`, `Audit`, `Project Brain`, `Operations`, and `Intake` as peers. Slice 1 may also render later destinations as unavailable (`:948`). The existing audit deliberately concluded that the target should have five primary destinations and place Operations and Support/Intake secondarily (`CCC_EXISTING_UI_AUDIT.md:308-343`).

**Why this matters:** splitting one supervisory journey into eight global destinations makes the operator reconstruct mission context across screens and gives Operations/Intake the same prominence as the work itself. Rendering disabled future navigation in Slice 1 would expose the product roadmap as permanent interface clutter. This conflicts with the user's ground-up, remove-what-is-not-needed direction.

**Required change:** reduce persistent primary navigation to:

1. `Missions`;
2. `Work` (packages and briefs);
3. `Runs`;
4. `Assurance` (evidence and audits);
5. `Context` (brain, decisions, risks, checkpoints).

Keep cross-mission Brief, Evidence, and Audit queues as route-backed subviews/filters inside Work or Assurance. Put Operations and Intake behind secondary navigation/attention affordances and platform-owner capabilities. Slice 1 must render only destinations that work end to end; unavailable future modules belong in documentation, not as disabled primary navigation.

### High — H2: Unknown mutation outcomes require an idempotency lookup that has no defined contract

**Evidence:** dispatch and the mutation truth table require an “idempotency lookup” after an unknown network result (`CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md:488-497`, `:694-701`), but the API/action matrix defines neither a lookup endpoint nor precise replay semantics (`:817-859`).

**Why this matters:** an implementer would have to invent recovery behavior for mission creation, approval, assignment dispatch, decisions, and destructive actions. Generating a new key risks duplicates; blindly replaying without request-fingerprint rules risks returning the wrong prior result.

**Required change:** freeze one exact contract before implementation. Prefer replaying the identical method/path/body/actor with the same `Idempotency-Key`, where the server stores a canonical request fingerprint and returns the original status/body/resource IDs. Define retention, `in_progress`, `completed`, and `failed` semantics plus `409 idempotency_conflict` when the fingerprint differs. If a separate lookup endpoint is chosen, specify its path, authorization, response schema, expiry, and correlation rules. Add network-drop-before-response and concurrent-retry tests proving only one durable mutation occurs.

### High — H3: Dual-run mutation authority is stated as a UI rule but not enforced as a backend cutover contract

**Evidence:** the spec says both UIs may read shared resources but only the surface with a server capability may mutate them (`CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md:158-165`). The existing v1 cockpit is not capability-driven and directly calls legacy mutation endpoints. A server-controlled feature flag is required but its authoritative scope and legacy endpoint behavior are not specified.

**Why this matters:** during the parallel route phase, v1 and v2 could mutate the same thread, approval, worker, or worktree through different routes. UI hiding does not prevent stale tabs, deep links, or direct requests from bypassing the intended owner surface.

**Required change:** define a server-enforced cutover mode with explicit states such as `v1_only`, `v2_read_only`, `v2_active`, and `rollback`. Bootstrap must return the mode and action capabilities. Legacy endpoints must reject mutations that would bypass supervisor state machines once a resource is supervisor-owned. Direct v2 deep links must fail before data loading when the flag/capability is absent. Rollback must not permit concurrent writers or delete v2 records. Add stale-v1-tab, direct-request, and rollback tests.

### High — H4: The required test and destructive-dialog foundations do not exist in the current frontend toolchain

**Evidence:** the spec requires rendered component tests, focus/live-region tests, axe, and the application's accessible `AlertDialog` (`CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md:684-693`, `:1080-1105`). Current `frontend/package.json` runs only Node tests matching `src/**/*.test.ts`; it has no DOM/component runner, Testing Library, jsdom/happy-dom, Playwright frontend test configuration, or axe dependency. `frontend/src/components/ui/` has `dialog.tsx` but no shared `alert-dialog.tsx`. No server-query library is installed even though the state boundary requires a server-query cache (`:572-579`).

**Why this matters:** Slice 1 cannot prove the stated behavior with current tooling, and implementers would otherwise improvise incompatible test/state/confirmation systems. Source-string tests are explicitly disallowed as acceptance evidence.

**Required change:** before WP-UI-02, make and document three choices:

1. the server-state cache implementation (an approved library or a small tested repository-standard abstraction), including cancellation and stale-result suppression;
2. the rendered-component/accessibility test harness, test filename pattern, DOM environment, and axe integration;
3. a shared accessible AlertDialog primitive built on the existing Radix package, with focus-return and non-destructive initial focus tests.

Include `frontend/package.json`, the lockfile, test configuration, shared primitive, and their focused tests in that work package's exact allowlist. Do not create a supervisor-local primitive fork.

### High — H5: Run output, diff, activity, and evidence reads need a frozen server-side disclosure contract

**Evidence:** the UI promises bounded/scrubbed output and provenance, but the API matrix only names `GET /v2/runs/{id}/diff|tests|output` without schemas, pagination, bounds, truncation, redaction markers, artifact authorization, or content-type rules (`CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md:835-840`). Current worker data includes prompts, model responses, command output, diffs, paths, and event payloads that cannot be returned wholesale under `AGENTS.md` privacy rules and the security baseline.

**Why this matters:** a new renderer cannot make an unsafe backend payload safe. Leaving the contract open invites reuse of current raw event/output records and may expose prompts, responses, credentials, customer data, unrestricted paths, or unbounded output.

**Required change:** add strict schemas for timeline, output, diff, test, and evidence detail responses. Define server-side allowlists/redaction, maximum page/item/field sizes, cursor semantics, truncation indicators, safe logical worktree/file identifiers, digest/provenance fields, and explicit exclusion of prompts, hidden reasoning, model response bodies, authorization material, customer data, and unrestricted host paths. Artifact retrieval must use opaque IDs, authorization, bounded content types, and download/display disposition. Add PII/secret canary and oversized/malformed payload tests before Run Detail is enabled.

### Medium — M1: First-slice project selection/claiming is not closed end to end

**Evidence:** Mission creation depends on a project and the architecture requires claimed ownership, but the v2 matrix defines only `GET /v2/projects` (`CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md:823`) and Slice 1 begins with create/open mission (`:956-969`). Current Control Centre projects are global, expose repository paths, and have no actor ownership.

**Required change:** define the first-slice project bootstrap rule. Either bind the development supervisor to one deploy-configured FastAPI Bookings project ID or implement the blueprint's explicit claim/quarantine/adoption service before Mission creation. The browser receives opaque ID/name/state, never an arbitrary host path. Define the empty/no-claimed-project UI, platform-owner recovery action, and negative isolation tests.

### Medium — M2: Dirty-form navigation, offline edit loss, and audit-edit recovery are underspecified

**Evidence:** the browser may own unsaved form text (`CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md:68`), brief saving is debounced, failures remain unsaved, and conflict buffers are preserved; however, there is no contract for route navigation, browser close/reload, session expiry, offline transition while dirty, or partially edited audit criteria.

**Required change:** define a shared dirty-buffer policy for Brief Builder and Audit Studio: route/blocker behavior, accessible confirmation text, retry/discard/copy actions, session-expiry behavior, conflict compare/rebase behavior, and whether any browser persistence is allowed. If persistence is allowed, it must be non-authoritative, bounded, scoped to actor/resource/revision, cleared on commit/logout, and prohibited from holding secrets/customer data. Add keyboard/focus tests for the guard and recovery dialog.

### Medium — M3: `allowed_actions` is central but has no typed affordance schema

**Evidence:** the UI must not infer permissions and must display server reasons for disabled actions, but the envelope only names capabilities/`allowed_actions`; it does not define their shape, version binding, expiry, or confirmation/risk metadata.

**Required change:** define a strict action descriptor, for example: `action`, `allowed`, `reason_code`, safe `reason`, `resource_version`, `risk_level`, `confirmation_kind`, `idempotency_required`, and optional `expires_at`. Unknown actions must be non-actionable. Mutation requests must still be re-authorized server-side; descriptors are presentation hints, not bearer capabilities. Add stale-descriptor and reason-rendering tests.

### Medium — M4: Legacy deep-link and support-launch compatibility is missing from cutover tests

**Evidence:** the existing audit requires compatible `thread` deep links (`CCC_EXISTING_UI_AUDIT.md:221`), and current application redirects use `/admin/coding-cockpit?tab=workbench` (`frontend/src/App.tsx:215-230`). The new route/cutover section does not say how `thread`, `tab`, or support-ticket-launched thread links behave during parallel operation or after v1 retirement.

**Required change:** add a compatibility table. During parallel operation, legacy thread links should route explicitly to v1. After cutover, map a thread to its supervisor run only when an authorized durable lineage exists; otherwise show a non-leaking explanatory state or an authorized legacy-history route. Never silently drop the selected thread or expose existence across scope. Add authorized, unauthorized, missing-lineage, and stale-bookmark tests.

### Low — L1: Namespace terminology should be frozen in one place

The blueprint uses `/api/admin/codex/supervisor`, while the new spec selects `/api/admin/codex/v2` and uses UI “Mission” for `supervisor_programme`. The spec explicitly supersedes/refines prior UI decisions, so this is not a defect, but Slice 0 must publish an ADR/OpenAPI decision declaring `/api/admin/codex/v2` canonical, deprecating the alternative, and fixing terminology used in URLs, DTOs, telemetry, and documentation. Do not ship both aliases.

## 4. Exact pre-implementation amendment gate

Before an implementation agent receives WP-UI-01 or WP-UI-02, the binding specification/addendum must contain all of the following:

- [ ] Five-item mission-first primary navigation; Operations and Intake secondary; no disabled roadmap clutter in Slice 1.
- [ ] Exact idempotency replay/lookup contract and unknown-outcome tests.
- [ ] Server-enforced parallel/cutover/rollback mutation modes, including stale-v1 behavior.
- [ ] Chosen server-query cache and rendered accessibility test harness.
- [ ] Shared AlertDialog creation plan and allowlist, because the primitive does not currently exist.
- [ ] Bounded/redacted schemas for run timeline, output, diff, tests, and evidence artifacts.
- [ ] Project claim/configuration path required before Mission creation.
- [ ] Dirty-buffer/navigation/offline/session-expiry policy for briefs and audits.
- [ ] Typed `allowed_actions` descriptor and stale-action behavior.
- [ ] Legacy `thread`/`tab` deep-link mapping and tests.
- [ ] One canonical v2 namespace recorded by ADR/OpenAPI.
- [ ] Exact changed-file allowlist, migration IDs, focused commands from `query_docs.py`, independent reviewer, and clean-checkout gate for each work package.

Implementation must remain blocked if P0 is not an ancestor of the chosen target branch or if a screen's durable backend/API contract is not present. A visual shell with fixture data, stub responses, disabled fake actions, or locally invented authoritative status is not an acceptable intermediate deliverable.

## 5. Independent testability of delivery slices

The slice order is broadly valid, with these acceptance boundaries:

1. **Slice 0** is independently testable only when P0 ancestry, OpenAPI/error/event schemas, canonical namespace, feature/cutover mode, and frontend test harness decisions are recorded and verified from a clean checkout.
2. **Slice 1** is independently testable as the first end-to-end product increment once project claim/configuration is included. Backend persistence can be delivered before UI, but the slice is not accepted until Mission -> Work Package -> Brief draft/validate/approve survives refresh and process restart through real APIs.
3. **Slice 2** is independently testable only with durable run snapshot/timeline, real worker acknowledgement, exact approval/input binding, and event replay/gap recovery. It must not use the legacy subagent registry as proof of delegation.
4. **Slice 3** is independently testable after the disclosure contract in H5 is enforced server-side and evidence is commit-bound, append-only, hashed, and independently verifiable.
5. **Slice 4** is independently testable only when author/reviewer assignment, run, thread, worktree, and context identities differ and the acceptance service rejects stale/incomplete/self-reviewed submissions.
6. **Slice 5** can add the full Project Brain UI, but automated checkpoint creation required by earlier state transitions must already exist in preceding backend slices.
7. **Slice 6** must keep Operations/Intake secondary and individually capability-gated; it must not reintroduce the old tool inventory into the mission shell.
8. **Slice 7** requires legacy deep-link evidence, dual-route browser coverage, one-release rollback with a single mutation authority, and reachability proof before deleting either legacy frontend tree.

## 6. Original verdict (superseded by section 7)

**ORIGINAL VERDICT: ACCEPTED WITH CONDITIONS.**

The foundation gets the most important decisions right: new UI, mission-first workflow, real backend before screens, no mocks, P0 preservation, durable evidence, independent audit, truthful degraded states, and a controlled strangler cutover. It does not preserve the old cockpit's component architecture.

The specification must nevertheless be amended before implementation because the eight-item primary navigation risks rebuilding the same clutter at a different level, and several safety-critical contracts—idempotency recovery, dual-run mutation authority, safe output disclosure, project claiming, action descriptors, and the actual accessibility test/AlertDialog foundation—are not yet exact enough for independent agents to implement without inventing behavior.

## 7. Closure audit of amended revision

### 7.1 Current verdict

**ACCEPTED WITH CONDITIONS.**

The amended specification closes every original High/Medium condition except two related contract details in H3/M3. There are no remaining Critical or High findings. The ground-up UI direction, five-group navigation, real-backend-only slices, P0 dependency, privacy disclosure contract, project claim flow, dirty-buffer recovery, testing foundations, and legacy-link handling are now implementation-grade.

WP-UI-00 and the cutover portion of WP-UI-01 remain blocked until R1 and R2 below are incorporated into the binding spec/ADR/OpenAPI. Those corrections are narrow and do not require redesigning the product or changing application code during this specification phase.

### 7.2 Condition-by-condition result

| Original condition | Result | Independent closure evidence |
|---|---|---|
| H1 — navigation sprawl | **Closed** | Sections 5–7 now define exactly Missions, Work, Runs, Assurance, and Context; Operations/Intake are secondary; Slice 1 shows only working Missions/Work destinations. |
| H2 — unknown mutation outcome | **Closed** | Section 15.2 defines actor/route/fingerprint-bound keys, transactional reservation, 24-hour retention, replay states, conflict behavior, unresolved UX, and network/concurrency tests. |
| H3 — dual mutation authority | **Partially closed** | Resource `control_plane`, stale-v1 rejection, four mode behaviors, and drain-only rollback are strong. R1 remains: legal mode transitions and the exact mutation schema are not defined. |
| H4 — missing UI foundations | **Closed** | Section 10.3 selects TanStack Query v5, Vitest/jsdom, Testing Library, axe, and one shared Radix AlertDialog; section 20.1 provides the required dependency/config/primitive allowlist. |
| H5 — unsafe disclosure ambiguity | **Closed** | Section 15.6 defines server-side redaction/exclusion, cursor scope, hard bounds, logical paths, timeline/output/diff/test/evidence schemas, opaque artifacts, MIME/disposition rules, and canary tests. |
| M1 — project claim/bootstrap | **Closed** | Section 4.4 defines a deploy-configured opaque project, claim/quarantine states, no browser path input, transactional claim, blocking readiness, and negative tests. The bootstrap example should type `claim_action` as descriptor-or-null when R2 is corrected. |
| M2 — dirty edit recovery | **Closed** | Section 12.4 defines memory-only buffers, acknowledged revision recovery, route/back/logout/reload/offline/session/conflict behavior, deliberate copy, focus, and test coverage. |
| M3 — typed actions | **Partially closed** | The descriptor shape, version/expiry/risk/confirmation semantics, server reauthorization, and tests are sound. R2 remains: the declared closed `ActionCode` union omits material mutations already required by the same specification. |
| M4 — legacy links | **Closed** | Section 5.4 defines authorized thread/tab/resident/studio/support translation, legacy-only handling, non-leaking not-found behavior, and tests. |
| L1 — canonical namespace | **Closed** | Section 15 makes `/api/admin/codex/v2` and Mission terminology canonical through ADR/OpenAPI with no alias. |

### 7.3 Remaining conditions

#### R1 — Medium — Freeze the cutover state machine and exact update contract

Section 5.1 precisely describes behavior *within* `v1_only`, `v2_read_only`, `v2_active`, and `rollback`, but it does not define which transitions are legal. `GET/PUT /operations/cutover-mode` in section 15.4 also has no request/response schema. An unrestricted `PUT` could permit transitions such as `v2_active -> v2_read_only` that strand active supervisor runs outside the defined drain-only rollback behavior.

Before WP-UI-00 contract freeze, add:

- a legal transition table, normally `v1_only -> v2_read_only -> v2_active`, `v2_active -> rollback`, and a separately gated recovery transition from `rollback`;
- explicit invalid transitions and `409 invalid_state` behavior;
- prerequisites for every transition, including active-run/drain state, P0 ancestry, migration/readiness, rollback reason, and mutation-lease checks;
- the exact `PUT` request (`target_mode`, `expected_version`, `reason` where required) and response (new mode/version, actor/time audit reference, effective mutation-authority summary, allowed next transitions);
- idempotency and race tests for two operators, stale versions, active runs, and rollback recovery.

#### R2 — Medium — Make the closed action registry cover every material mutation

Section 15.3 calls `ActionCode` a closed union, but it omits mutations already present elsewhere in the specification. At minimum it lacks `change_cutover_mode`, `create_brief_revision`, `withdraw_brief`, `respond_interaction`, `verify_evidence`, and `mark_checkpoint_current`. Later Operations and Intake require additional actions such as boundary removal, telemetry update/test, plugin installation, worktree removal, and intake promote/defer/decline/duplicate. Unknown actions are intentionally non-actionable, so these omissions would block legitimate controls or cause agents to widen the union ad hoc.

Before WP-UI-00 contract freeze:

- define one canonical action code for every material mutation in the API/action matrix and the secondary Operations/Intake workflows;
- map each action code to its exact method/path, descriptor-bearing resource, expected version, idempotency requirement, confirmation kind, and risk floor;
- version the action registry in OpenAPI/TypeScript if later slices may add codes, and require the relevant slice ADR/contract review before expansion;
- change the bootstrap example's `claim_action` to the typed `AllowedActionDescriptor | null` contract, with a real `claim_project` descriptor when `state=claim_required`;
- add conformance tests proving every enabled mutation has exactly one known action descriptor and every descriptor maps to an implemented mutation.

### 7.4 Final implementation position

No UI implementation should begin on the current primary branch: P0 is still not an ancestor, and the supervisor domain/facade do not exist. After R1/R2 are fixed and WP-UI-00 integrates P0 and publishes the ADR/OpenAPI contract, the specification is suitable for the staged backend-first implementation it defines.

No application runtime, model, endpoint, component, dependency, service, staging area, commit, or remote branch was changed by either review pass.

## 8. Final specification audit

### 8.1 Final verdict

**ACCEPTED.**

The revision at SHA-256 `CF57B7980231789351EC5C87E4876DFC5E9DDEFC7019291539F0D51FECE2FD4D` closes R1 and R2 and remains consistent with the five external fit assessments. There are no remaining Critical, High, or Medium specification findings and no specification blocker to starting WP-UI-00.

This is acceptance of the design/build contract only. It is not evidence that P0 has been integrated or that any proposed v2 persistence, facade, UI, adapter, dependency, action, migration, or test harness has been implemented.

### 8.2 R1 and R2 closure

| Condition | Final result | Evidence |
|---|---|---|
| R1 — cutover graph and update contract | **Closed** | Section 5.1 now provides the complete legal transition graph; enumerates every legal and invalid edge; defines same-mode no-op behavior; binds platform-owner authority, transition guards, rollback/drain/recovery, independent recovery approval, mutation leases, readiness and evidence; and freezes exact conditional/idempotent GET/PUT schemas, status/error behavior, atomic audit evidence, replay, unresolved-outcome UX, and race/recovery tests. |
| R2 — closed material-action registry | **Closed** | Section 15.3 contains 72 `ActionCode` literals and 72 registry rows. A mechanical comparison found 72 unique codes in each set, exact set equality, no duplicate code, no duplicate method/path row, no missing required registry field, and no extra row. Registry/OpenAPI/descriptor/permission bijection and version-expansion rules are explicit. Bootstrap project claiming and cutover use typed descriptors. |

### 8.3 Final control assessment

| Control | Result | Final audit conclusion |
|---|---|---|
| Ground-up mission-first UI | **Pass** | The canonical React implementation is new; the old cockpit and duplicate frontend are reference/decommission-only. Persistent navigation is exactly Missions, Work, Runs, Assurance, and Context. Operations and Intake are secondary, and Slice 1 exposes only working Missions/Work routes. |
| No mock/fake production path | **Pass** | Screens require real durable models, migrations, authorization, APIs, and error behavior. Demo data, fixtures, simulated runs, timer-driven success, browser-invented authority, optimistic lifecycle changes, and disconnected scaffolds are prohibited. Synthetic data appears only as labelled input to real integration and verification paths. |
| Authority and P0 | **Pass as contract; implementation prerequisite remains** | One FastAPI control plane, platform-owner gating, same-origin native authentication, actor/resource scoping, one-use event tickets, one mutation owner, typed action descriptors, server reauthorization, and the first-party worker boundary remain binding. P0 ancestry is still a WP-UI-00 gate rather than an accomplished fact. |
| Privacy and disclosure | **Pass** | Server-side bounds, redaction, opaque IDs, prohibited-field exclusions, safe MIME/disposition, artifact tickets, no-egress canaries, and non-leaking authorization failures cover native and optional-adapter paths. |
| Idempotency and unknown outcomes | **Pass** | Actor/tenant/route/fingerprint-bound UUIDv4 keys, transactional reservation, terminal replay, in-progress handling, conflicts, retained keys, identical-request recovery, bounded checks, and exactly-once tests are defined. |
| Accessibility and complete UI states | **Pass** | Loading, refreshing, empty, forbidden, unavailable, validation, conflict, pending, offline, reconnect, exhausted, authentication failure, stale authority, destructive confirmation, dirty buffers, unknown enum/event, keyboard, focus, screen-reader, zoom, 320-pixel reflow, touch, and reduced-motion requirements are explicit and testable. |
| Cutover and slice testability | **Pass** | Each slice has real backend prerequisites, a bounded outcome, an exit journey or acceptance boundary, focused verification, an independent reviewer, and changed-file control. V1 retirement occurs only after parity, link translation, rollback, and reachability evidence. |
| Windows-first gates | **Pass** | Exact binary/schema compatibility, whole process-tree termination, lifecycle recovery, parallel-manager rejection, worktree/lock behavior, Unicode/long/case-insensitive paths, UNC/device/alternate-stream rejection, reparse/symlink/hard-link and ACL handling, race/replay, upgrade/rollback, and queued-command survival are mandatory on supported Windows. |
| Proposed contracts versus present reality | **Pass** | Cutover, registry, API/action matrix, disclosure, worker, artifact, optional-adapter, dependency, model, and migration contracts are repeatedly labelled prerequisite/not implemented. The document does not claim that named endpoints or supervisor resources already exist. |

### 8.4 External-source and presentation-library decisions

| Assessment | Required decision | Final result |
|---|---|---|
| `CCC_COPILOTKIT_FIT_ASSESSMENT.md` | **SPIKE FIRST**; optional active-run presentation/transport only | **Incorporated.** Gate 1 direct AG-UI precedes Gate 2 CopilotKit; FastAPI/native REST remains authoritative; hosted intelligence, persistence, analytics, learning, and vendor telemetry remain out of scope; exact dependency, no-egress, recovery, privacy, removal, and independent-review gates apply. |
| `CCC_CODEX_BRIDGE_FIT_ASSESSMENT.md` | **REFERENCE ONLY** | **Incorporated.** No Bridge code, binary, daemon, auth, persistence, UI, process manager, or writer enters the application. Its useful operational lessons are independently specified as native contracts, and FastAPI owns the sole southbound app-server adapter. |
| `CCC_CODEX_WEB_LOCAL_FIT_ASSESSMENT.md` | **REJECT** | **Consistent.** The assessment explicitly requires no implementation/specification amendment. The candidate has no dependency, runtime, source, browser surface, protocol role, spike, or roadmap path. The sole-native-adapter, no-parallel-browser-authority, canonical-React, and no-second-executor rules enforce the rejection. Its name may be recorded in the next scheduled ADR decision register as a rejected alternative, but that clerical record is not an implementation blocker. |
| `CCC_OPEN_WEBUI_FIT_ASSESSMENT.md` | **REFERENCE ONLY** | **Incorporated.** No source, component, backend, auth/RBAC, data, model/RAG, plugin/tool/terminal, asset, style, wording, branding, PWA, licence obligation, or spike is adopted. The twelve accepted interaction lessons are first-party requirements only. |
| `CCC_ASSISTANT_UI_FIT_ASSESSMENT.md` | **SPIKE FIRST / likely narrow only** | **Incorporated.** Only exact-pinned core `ExternalStoreRuntime` is currently eligible; the assessed AG-UI adapter remains protocol-blocked. Cloud, framework persistence and generic chat actions are disabled, and native state/action authority remains unchanged. |

The presentation bake-off is correctly one-or-none. Native/direct AG-UI, CopilotKit, and Assistant UI are measured against the same real labelled synthetic workload after native Run Detail exists. At most one arm is retained; CopilotKit and Assistant UI cannot coexist or act as automatic fallbacks without a new ADR. The safe fallback is the already-complete native Run Detail.

### 8.5 Readiness position

There is **no remaining specification blocker before WP-UI-00**. WP-UI-00 is itself the required first gate: it must integrate and verify P0 on the approved line, freeze the ADR/OpenAPI/action-registry/cutover contracts, prove the clean checkout, and preserve the specified allowlist and independent review. WP-UI-01, WP-UI-02, and every visible v2 screen remain blocked until their stated real backend, migration, dependency, authorization, testing, and readiness prerequisites exist.

No application code, dependency, service, staging area, commit, push, or runtime process was changed by this final audit.

## 9. Assistant UI documentation-MCP integrity recheck

### 9.1 Verdict continuity

**ACCEPTED remains valid.**

The revision at SHA-256 `CF9DB16A10D51AE3EE09949C63456A42981DD92007A4DB53C654343B93ED0D29` adds only the Assistant UI documentation-MCP boundary in section 15.10.7 and its AU13 closure row. The addition does not alter the product architecture, presentation bake-off, application dependency plan, v2 facade, durable authority, action registry, or implementation sequencing. No new Critical, High, or Medium finding is introduced.

### 9.2 Boundary and authorization findings

- **Developer-only boundary — Pass.** The hosted MCP is described as read-only development documentation/tooling available only after an approved WP-UI-05A spike brief. It is explicitly excluded as a production dependency, endpoint, MCP/tool source, agent server, worker transport, cloud/model connection, authentication/persistence/telemetry service, or lifecycle/recovery authority.
- **Production/runtime prohibition — Pass.** The browser, FastAPI runtime, worker, resident supervisor, deployed services, operators, tenants, models, and production subagents are all denied access through the production tool registry. The local proxy package is not installed or committed and would require a separate exact dependency/lockfile approval.
- **Untrusted-reference handling — Pass.** Documentation, examples, schemas, rules, template metadata, and component suggestions are explicitly untrusted reference material. They must be reconciled against exact pinned package source/types, the binding supervisor specification, shared primitives, security boundaries, and the approved changed-file allowlist; freshness is not treated as compatibility, licence, provenance, accessibility, security, or acceptance evidence.
- **Template preview/download/import — Pass.** `preview_template`, generated preview URLs, downloads, and imports are denied by default. Any exception requires a separate explicit approved brief naming the exact template and external action, plus source/file provenance, licence, data-flow/egress, exact dependency/lockfile/SBOM/vulnerability review, security, accessibility/design-system review, no-mock proof, exact file allowlist, living documentation, independent audit, and disposal/removal plan. The exception cannot introduce simulated backend state, a duplicate shell/application/design system, hidden vendor service, unreviewed generated content, or files outside the allowlist.
- **Fail-secure authority — Pass.** Documentation or template content grants no supervisor authority and cannot create an implicit dependency or bypass the later isolated spike, one-or-none adoption decision, native fallback, or production gates.

### 9.3 Registry integrity

The registry remains unchanged and closed. A fresh mechanical comparison found:

- 72 `ActionCode` literals, all unique;
- 72 registry rows, all unique;
- exact union/registry set equality;
- no duplicate method/path entry.

Documentation lookup, template comparison, and separately governed external preview/import work are development-process activities, not externally callable supervisor mutations. They therefore add no `ActionCode`. AU13 is consistent with section 15.10.6 and does not weaken the registry bijection.

There is no new blocker before WP-UI-00. No application code, dependency, service, MCP configuration, template preview, download, import, staging action, commit, push, or runtime process was changed or invoked by this recheck.
