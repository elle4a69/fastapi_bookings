# ADR: Codex Supervisor v2 Facade and Control-Plane Contract

- **Status:** Accepted; WP-UI-01A-v6 foundation implemented, activation deferred
- **Date:** 2026-10-15 (Australia/Sydney)
- **Work package:** WP-UI-00
- **P0 ancestor:** `170f6f7eb62278bc029d39caaeda8637d4c99c59`
- **Detailed source:** [`../../artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md`](../../artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md)
- **Independent design review:** [`../../artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_REVIEW.md`](../../artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_REVIEW.md)

## Context

FastAPI Bookings already mounts the P0-hardened Codex Control Centre and exposes the current cockpit at `/admin/coding-cockpit`. The durable development-supervisor domain and replacement interface do not yet exist. Incrementally extending the current cockpit would preserve fragmented ownership and state conventions, so the accepted design requires a ground-up v2 surface behind a single FastAPI-owned facade.

This record freezes the complete target contract. WP-UI-01A-v6 implements only
the authenticated five-route `0.1` project-claim foundation described below; it
does not activate a replacement UI, mission/work/brief/run domains, worker
control, or a writable cutover transition.

## Decision

### Namespace, terminology and frontend ownership

- `/api/admin/codex/v2` is the sole future UI facade. No `/supervisor` alias is permitted.
- `Mission` is the external API and UI term. It maps internally to the durable `supervisor_programme` aggregate; no duplicate mission store is created.
- The main `frontend/` application is the canonical frontend and owns every future v2 route and screen.
- `codex-control-centre/frontend/` is frozen as reference/decommission-only. It receives no new product feature and is never imported by the canonical frontend.
- Until actor-scoped ownership and negative isolation tests pass, the entire v2 surface is restricted to authenticated platform owners. An ordinary tenant `owner`, `admin` or `manager` is insufficient.

### Authority and transport

FastAPI Bookings is the sole control plane. It owns identity, authorization, ownership, durable state, approvals, idempotency, audit, and the only southbound mutation/lifecycle adapter to the supported Codex app-server protocol. Browsers, optional presentation runtimes, Codex Bridge, Codex Desktop and other daemons cannot become parallel writers or lifecycle managers.

Native authenticated REST snapshots are durable truth. Ticketed SSE is passive invalidation and attention transport: each connection consumes a scoped one-use ticket, events carry durable sequence/version references, and any gap or uncertainty is reconciled from REST. Events never replace authoritative snapshots or authorize mutations.

### Project claim and quarantine prerequisite

Deployment configuration supplies the one permitted repository root and an opaque project identity server-side. The browser never supplies or receives a host path. Existing pre-ownership Control Centre projects migrate to `unclaimed` or `quarantined` and remain absent from ordinary mission queries.

Mission creation is blocked until an authenticated platform owner transactionally claims the configured project with the server-returned `claim_project` descriptor, expected project version and idempotency key. The server validates the opaque `prj_` route identity before fingerprinting or reserving the key, validates the configured default branch with Git-equivalent branch-name rules, and then verifies the configured root, record fingerprint, actor, current claim state and conflicting ownership. A persisted, indexed, non-public physical-root digest binds the normalized resolved path and positive filesystem device/inode identity, allowing bounded candidate queries followed by canonical/same-file verification. Cross-scope rows are removed before candidate classification: they are never counted, described, quarantined, adopted, or mutated. Hidden collisions remain read-indistinguishable from absence (`claim_required`, version-0 summary/action, `can_claim_project=true`) while a targeted mutation returns only `404 resource_not_found`. `unconfigured`, `quarantined` and `migration_required` states fail closed and provide only authorized recovery controls. Negative tests must cover malformed and guessed IDs, cross-tenant and non-owner claims, concurrent/repeated claims, configured-root mismatch, Git-invalid branches, quarantined rows and browser-supplied paths.

## Cutover contract

Cutover is a persisted, versioned, server-controlled platform setting with actor/time audit evidence. Every dual-operation project, thread, approval, worktree, assignment and run has a server-owned `control_plane: legacy|supervisor_v2` marker or equivalent durable lineage. Legacy mutations check this transactionally; a stale v1 request against supervisor-owned state returns `409 supervisor_owned`.

| Mode | V1 behavior | V2 behavior | Mutation authority |
|---|---|---|---|
| `v1_only` | Authorized legacy reads and mutations continue | Only the authorized cutover-control fragment is visible; no supervisor-domain data | V1 only |
| `v2_read_only` | Legacy-only resources may mutate; claimed resources reject v1 mutation | Snapshots readable; product mutations return `409 cutover_read_only`; only guarded claim/cutover setup may be enabled | V1 for legacy-only state; v2 for setup only |
| `v2_active` | V1 may read; supervisor-owned mutations return `409 supervisor_owned` | Mutations occur only through v2 state machines and `allowed_actions` | V2 for supervisor-owned state |
| `rollback` | Legacy-only resources may mutate; supervisor-owned state remains read-only | Reads and bounded drain actions only; no new mission, dispatch or decision work | No new supervisor writer |

The complete legal transition graph is:

```text
v1_only <-> v2_read_only -> v2_active -> rollback -> v2_read_only
                 \-----------------------> rollback
```

There are no other edges. Same-mode requests are audited idempotent no-ops (`200`, `changed=false`, no version increment). Legal transitions and guards are:

- `v1_only -> v2_read_only`: platform owner; deployed P0 ancestry, matching migrations/OpenAPI/registry, healthy bootstrap/readiness, no incomplete cutover, and reason.
- `v2_read_only -> v1_only`: platform owner; zero claimed or supervisor-owned resources/domain rows, pending v2 idempotency records and mutation leases, plus reason.
- `v2_read_only -> v2_active`: platform owner; project ready and claimed, current P0/migrations/readiness, drained v1 workers/leases, no unresolved operation, independent clean-checkout/release evidence, and typed acknowledgement.
- `v2_read_only -> rollback`: platform owner; incident/defect reason and evidence; immediate even during degraded readiness.
- `v2_active -> rollback`: platform owner; reason required; new product mutations stop atomically without waiting for active runs.
- `rollback -> v2_read_only`: platform owner plus a different, independently recorded recovery approver; terminal/interrupted runs, fail-closed approvals/interactions, released leases, terminal idempotency operations, reconciled durable events/outbox, current migrations/readiness and recovery evidence.

All other transitions return `409 invalid_state`. Guards are evaluated from a locked cutover row and transactionally consistent resource, lease and idempotency counts. Guard failures return `409 transition_guard_failed` with bounded safe codes/counts. Rollback preserves v2 records and ownership and permits only descriptor-listed drain operations: `interrupt_run`, `release_run_writer`, fail-closed `decide_approval`, and fail-closed `respond_interaction`. It never transfers supervisor-owned resources back to v1 or creates concurrent writers.

The future update is conditional and idempotent: the platform owner uses the server-returned `change_cutover_mode` descriptor, `If-Match: "cutover-<version>"`, the matching expected version, and a UUIDv4 `Idempotency-Key`. Missing or stale conditions fail closed. The state row, audit event, durable event and terminal idempotency result commit atomically. Rollback recovery requires the independent approver and signed decision specified above.

## Idempotency and unknown outcomes

Every create, transition/action, approval, dispatch, retry, claim, checkpoint, destructive mutation, and repeatable PATCH save requires idempotency.

- One logical submission creates one in-memory UUIDv4 key. Every retry preserves the identical method, normalized path, canonical JSON body, authenticated actor, scope and expected version.
- The server fingerprints `actor_id + tenant_id + method + normalized_path + canonical_json_sha256 + expected_resource_version`; credentials are never fingerprinted or stored. Keys are actor/route scoped and retained for 24 hours after terminal completion.
- The server transactionally reserves the key before its first side effect. The same key and fingerprint returns `202` plus original request ID while `in_progress`, or replays the original terminal safe success/error with `Idempotency-Replayed: true`. A different fingerprint returns `409 idempotency_conflict`.
- Phase two uses one outer immediate transaction and a nested savepoint around project and event writes. A deterministic safe failure rolls back the savepoint and terminalizes the failed reservation before committing that same outer transaction; it never opens a third write transaction. An unexpected failure rolls back the outer transaction completely, leaves the committed reservation `in_progress`, and relies on bounded lease expiry and reclaim.
- Expired or missing keys may begin new processing only after durable uniqueness/state checks exclude an existing operation or resource. A confirmed terminal failure requires an explicit new operator action and new key; an unresolved operation never offers a new attempt.
- On response loss, the UI freezes conflicting controls and replays the exact request/key at most three automatic checks using 0/1/3-second waits. It shows the original request ID. Terminal replay reconciles by resource ID/version and refetches REST truth.
- After checks are exhausted, the only choices are `Check again`, `Copy request ID`, and `Return to read-only view`. `409 idempotency_conflict` is a blocking integrity failure; the buffer is preserved and no new key is silently generated.

These semantics apply exactly to cutover updates as well as ordinary v2 mutations.

## Closed action registry 1.0

`AllowedActionDescriptor` is the only presentation contract for future operator mutations. It contains registry version `1.0`, one closed `ActionCode`, `allowed`, bounded safe reason fields, resource version, risk, confirmation contract, idempotency requirement and optional expiry. Descriptors are version-bound hints, not bearer capabilities: the server reauthenticates, reauthorizes and recomputes every guard inside the mutation transaction.

Registry `1.0` contains exactly **72 unique action codes and 72 unique registry rows**. The two sets must be exactly equal, with no duplicate semantic route. Future OpenAPI conformance must prove a bijection between every operator mutation operation, its `x-operator-action`, the registry row and permission mapping. A missing, duplicate, unknown, stale or extra action fails the build or remains non-actionable.

The closed codes are:

```text
change_cutover_mode, claim_project,
create_mission, edit_mission, activate_mission, pause_mission,
resume_mission, complete_mission, cancel_mission, archive_mission,
create_work_package, edit_work_package, add_work_dependency,
remove_work_dependency, block_work_package, unblock_work_package,
cancel_work_package, rebrief_work_package,
create_brief_revision, edit_brief_revision, validate_brief,
submit_brief_for_approval, approve_brief, reject_brief, withdraw_brief,
assign_author, assign_reviewer, dispatch_assignment,
withdraw_queued_assignment, steer_run, interrupt_run, retry_run,
release_run_writer, reacquire_run_writer, restart_worker,
decide_approval, respond_interaction,
link_evidence, verify_evidence, reject_evidence,
create_audit, edit_audit_matrix, submit_audit, accept_implementation,
request_rework, require_human_decision, record_human_decision, fail_audit,
create_decision, edit_decision, accept_decision, reject_decision,
supersede_decision, create_risk, edit_risk, mitigate_risk, accept_risk,
materialize_risk, close_risk, create_checkpoint, mark_checkpoint_current,
add_workspace_boundary, remove_workspace_boundary,
update_telemetry_settings, test_telemetry_connection,
install_plugin, remove_worktree, create_intake, promote_intake,
defer_intake, decline_intake, mark_intake_duplicate
```

## Disclosure, errors, events and artifacts

- Responses expose only fields required by the verified actor and current screen. Cross-scope and hidden resources use non-leaking authorization responses and opaque IDs.
- Prompts, reasoning, model bodies, commands, tool input/output, source, diffs, host paths, credentials, tokens, customer/booking/SMS/payment data and other PII are excluded from events, errors, telemetry and browser persistence.
- Error envelopes use stable allowlisted codes, bounded operator-safe messages and a request ID. They contain no trace, raw exception, SQL, filesystem path or existence leak.
- Mutable snapshots carry resource versions. Events carry schema version, durable sequence, occurrence time, opaque resource correlation and bounded invalidation/attention payloads. Unknown, oversized, out-of-order, gapped or mismatched events trigger bounded REST reconciliation and never speculative repair.
- Artifact metadata is bounded and redacted. Content is delivered only through short-lived, actor/resource/digest/root-bound one-use tickets; browser paths and arbitrary file access are forbidden.

## Native worker invariants

- FastAPI owns one southbound Codex app-server writer and lifecycle manager. Parallel management fails closed.
- Writer and lifecycle ownership, owner version, observation source, confidence, expiry, read-only state and capabilities are typed server projections; they are not inferred from UI state or rollout timestamps.
- Queue, steer, interrupt, release, reacquire, handoff and restart are durable, idempotent, audited operations. A UI success requires the applicable app-server acknowledgement; submission is never represented as completion.
- Recovery source precedence is native manager state, app-server handshake, normalized durable adapter history and only then bounded rollout diagnostics. Disagreement produces safe read-only/unknown state rather than guessed ownership.
- Worker changes require Windows-first process-tree, restart/recovery, worktree/lock, long/Unicode/case-insensitive path and ACL checks, rejection of UNC/device/alternate-stream escapes, exact protocol upgrade/rollback tests, and artifact race/replay checks. Linux or macOS success does not waive Windows acceptance.

## External technology decisions

- CopilotKit and Assistant UI are later **spike-only** presentation candidates. At most one may be retained after the native run contracts and comparative evidence exist; coexistence requires a new ADR.
- Assistant UI is limited, if later approved, to exact-pinned core `@assistant-ui/react` with `ExternalStoreRuntime` projecting one selected native Run. Its current AG-UI adapter is protocol-blocked. Assistant UI documentation MCP is developer-only, read-only research during an explicitly approved later spike and never a deployed supervisor tool.
- Codex Bridge and Open WebUI are **reference-only**. No source, dependency, daemon, backend, authentication, persistence, UI, asset, branding or authority is imported from them.
- `codex-web-local` is rejected and cannot enter the dependency or runtime graph.

## Implementation status and consequences

WP-UI-00 recorded the complete target contract. WP-UI-01A-v6 now supplies the
first durable backend slice: native active-platform-owner authority, independent
CCC Alembic revisions `002` and `003`, exact read-only readiness attestation,
exact-root configured-project resolution and claim, committed idempotency reservations,
append-only claim evidence, a fixed persisted `v1_only` cutover posture, and
exactly five `/api/admin/codex/v2` operations. Claimed projects reject legacy v1
mutation, but retain `control_plane='legacy'` in this slice.

Exact readiness requires both the migration-script head and database ledger to
match revision `003`, plus the complete expected columns and their type,
nullability, default and key properties; constraints; ordered index definitions;
normalized trigger SQL; and the fixed singleton row/state. Same-name or partial
objects, including a no-op trigger with an expected name, fail closed.

The implemented `0.1` registry contains only `claim_project`; it does not claim
the later 72-action registry `1.0`. The current v1 cockpit remains operational.
No replacement screen, mission/work-package/brief/run endpoint, worker adapter,
cutover activation, or general legacy API redesign is enabled by 01A.

Later packages own the replacement shell, workflow domains, active cutover,
runs, evidence and audit. No optional presentation adapter is permitted until
the separately approved comparative spike prerequisites pass.

Rollback of this documentation package is an ordinary reviewed revert. P0 security controls are not silently reverted.
