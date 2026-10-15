# Codex Control Centre Security and Truthfulness Baseline

**Audit date:** 2026-10-15 (Australia/Sydney)  
**Audit scope:** only the Codex Control Centre embedded in `F:\Projects\fastapi_bookings` and the FastAPI Bookings resident-agent/support-ticket integration. The separate `F:\Projects\codex-control-centre` repository was not inspected.  
**Method:** non-intrusive static review plus focused existing regression tests. No application code, runtime data, `.env` file, credential, database content, or untracked integration material was read or modified.  
**Security readiness:** **2/10 for use as a multi-tenant development supervisor**. Keep autonomous execution disabled until Critical and High findings are remediated.

## Executive verdict

The embedded implementation has several useful foundations: a separate control database, SQLite WAL/foreign-key setup, random short-lived SSE tickets, path normalization, worktree-name traversal rejection, a fail-closed resident fix executor, and bounded/sanitized skills-RAG query derivation in the newer Control Centre path.

It is not yet safe to act as a shared resident supervisor. The principal problem is that authenticated FastAPI Bookings tenant administrators are treated as administrators of one global Control Centre. Its records have no tenant or user ownership, and any tenant owner/admin/manager can reach global project, thread, settings, worktree, and approval operations. Two event surfaces also bypass the mounted application's normal authorization: the Control Centre accepts a hard-coded default bearer secret, and the resident-agent SSE stream is unauthenticated. The current implementation also contains several paths that claim dispatch, health, research, or queued work when the underlying operation did not occur.

## Positive controls worth preserving

- The Codex database is configured separately from the main application database and enables SQLite WAL and foreign keys (`codex-control-centre/backend/config.py:8-17`; `codex-control-centre/backend/database.py:5-18`; `app/main.py:247-274`).
- SSE tickets use 32-byte URL-safe random values and a bounded TTL (`codex-control-centre/backend/services/sse_tickets.py:25-37`).
- Worktree names reject traversal separators, repository paths are normalized against boundaries, and real worktrees require a verified Git root (`codex-control-centre/backend/services/worktree_service.py:19-56`, `229-265`).
- The newer Control Centre skills path derives a small technical vocabulary query instead of forwarding the raw prompt to the skills service (`codex-control-centre/backend/services/skills_context.py:41-47`, `119-166`).
- The resident fix executor fails closed and explicitly reports `verified: false` when no isolated worker is connected (`app/services/resident_agent/executor.py:32-80`).
- Support-ticket launch is restricted to a platform-owner dependency at its router boundary (`app/api/routers/admin_support_tickets.py:206-210`, `449-456`).

## Ranked findings

### CCC-SEC-001 — Critical — Global Control Centre authority is granted to ordinary tenant administrators

**Evidence**

- Mounted project, thread, turn, settings, worktree, governance, plugin, and skills routers use `get_current_admin` (`app/main.py:609-673`).
- `get_current_admin` accepts any `owner`, `admin`, or `manager` in any tenant (`app/api/deps.py:229-235`). This is materially broader than the existing platform-owner control (`app/api/deps.py:190-202`).
- `Project`, `Thread`, `Turn`, `Item`, `ToolApproval`, `SubAgent`, `WorkspaceBoundary`, and `SystemSetting` have no `tenant_id`, `owner_user_id`, actor, or policy-scope columns (`codex-control-centre/backend/models/codex.py:6-105`).
- List/get/update/delete handlers query only global IDs and return all records (`codex-control-centre/backend/routers/projects.py:176-211`; `codex-control-centre/backend/routers/threads.py:65-102`).
- A tenant administrator can add any existing host directory as a boundary (`codex-control-centre/backend/routers/settings.py:48-56`; `codex-control-centre/backend/services/boundary_service.py:144-178`) and then create projects/worktrees within it.

**Impact**

One tenant manager can view other users' prompts and work, steer or interrupt their agents, mutate global settings, widen filesystem access, create worktrees, and approve code-changing tool calls. In a multi-tenant application this is a cross-tenant confidentiality and host-integrity failure.

**Required tests**

1. `test_codex_routes_reject_non_platform_owner`: a tenant manager receives 403 from every mounted Control Centre route.
2. `test_codex_records_are_principal_scoped`: tenant/user B cannot list, read, update, delete, stream, steer, interrupt, or approve tenant/user A records even when IDs are known.
3. `test_codex_create_stamps_owner_and_tenant`: every durable entity records tenant, initiating user, and actor.
4. `test_boundary_mutation_is_platform_owner_only_and_allowlisted`: an authenticated tenant administrator cannot add `C:\`, a home directory, a sibling repository, or any path outside the configured FastAPI Bookings root.

### CCC-SEC-002 — Critical — Mounted event authentication accepts the public default `local_secret`

**Evidence**

- The default Control Centre secret is the literal `local_secret` (`codex-control-centre/backend/config.py:21-24`).
- `verify_auth` accepts that secret before evaluating the mounted application's user/tenant identity (`codex-control-centre/backend/middleware/auth.py:42-59`).
- The events and diagnostics routers are mounted without the main application's `get_current_admin` dependency (`app/main.py:628-632`, `645-649`).
- Ticket issuance and event publication rely on `verify_auth` (`codex-control-centre/backend/routers/events.py:72-76`, `176-188`). The stream also directly accepts `settings.token_secret` (`codex-control-centre/backend/routers/events.py:24-45`).
- Existing standalone tests normalize the static secret as a valid credential rather than asserting it is forbidden in mounted mode (`codex-control-centre/tests/test_security.py:21-25` and multiple `AUTH_HEADERS` fixtures).

**Impact**

Anyone who can reach the mounted API and knows the repository-default secret can mint stream tickets, publish fabricated events, and access protected diagnostics without a FastAPI Bookings account. This also destroys evidence integrity because an unauthenticated caller can inject apparently legitimate agent events.

**Required tests**

1. `test_mounted_codex_rejects_default_control_secret`: `Bearer local_secret`, query `token=local_secret`, and `X-Token: local_secret` all return 401 in the FastAPI Bookings app.
2. `test_mounted_events_require_platform_owner_identity`: only a current, enabled platform owner with resolved tenant/account context can issue a ticket or publish an event.
3. `test_event_publish_is_internal_only`: browser/API users cannot publish worker evidence directly; publication requires an internal capability tied to a worker/run.
4. `test_production_refuses_default_or_missing_secret`: startup fails closed if a standalone deployment uses the default secret.

### CCC-SEC-003 — Critical — Resident SSE stream is unauthenticated and replays global sensitive history

**Evidence**

- `/api/admin/resident-agent/events` declares no `Depends(get_current_admin)` and accepts an optional `token` that is never validated (`app/api/routers/resident_agent.py:84-99`).
- The broker is one process-global singleton and replays the last 25 events to every subscriber (`app/services/resident_agent/event_broker.py:16-23`, `55-88`, `99-100`). There is no tenant, user, run, or thread partition key.
- Advisory handling publishes the first 100 characters of the raw prompt and then the complete prompt as the web-research query event (`app/services/resident_agent/engine.py:232-255`).

**Impact**

An unauthenticated client can receive operational events and prompt fragments from every tenant/admin using the resident agent. A reconnect receives historical events immediately.

**Required tests**

1. `test_resident_events_require_authenticated_platform_owner`.
2. `test_resident_events_do_not_accept_query_bearer_tokens`.
3. `test_resident_event_history_is_scoped_to_principal_and_run`.
4. `test_resident_events_never_include_raw_prompt_or_pii` using labelled email, phone, booking note, and token canaries.

### CCC-SEC-004 — Critical — Resident skill reader can return arbitrary host files

**Evidence**

- The skills endpoint returns the entire content supplied by `skill_library.read_skill` (`app/api/routers/resident_agent.py:247-260`).
- `read_skill` first constructs a bounded skill path but then explicitly accepts any caller-supplied path that exists and is a file (`app/services/resident_agent/skill_library.py:153-168`). On Windows an absolute path containing backslashes can remain a single URL path segment.
- This legacy reader scans `C:\Users\Frank\skills` directly rather than using the bounded port-8008 skills-RAG service (`app/services/resident_agent/skill_library.py:1-24`).

**Impact**

Any tenant owner/admin/manager that can reach the resident-agent admin endpoints may read arbitrary service-account-readable files, including source outside the repository or credentials, despite the apparent basename traversal guard.

**Required tests**

1. `test_resident_skill_read_rejects_absolute_windows_path`.
2. `test_resident_skill_read_rejects_absolute_posix_and_encoded_traversal`.
3. `test_resident_skill_read_only_accepts_indexed_skill_id`.
4. Remove the direct reader and contract-test the same bounded skills-RAG client used by Control Centre turns.

### CCC-SEC-005 — High — Approval resolution is not bound to principal, tenant, thread, turn, or worker

**Evidence**

- `ToolApproval` records only thread, tool-call, command, risk, consequence, and status; they do not record requester/approver identity, tenant, turn, worker/run, expiry, or an immutable command digest (`codex-control-centre/backend/models/codex.py:62-75`).
- The compatibility response endpoint accepts an optional `thread_id` but ignores it, selecting the first pending record by `tool_call_id` alone (`codex-control-centre/backend/routers/turns.py:83-87`, `537-552`).
- If no database record exists it may pop a process-global pending RPC by tool-call ID, and it then also sends a response through `worker_manager.get_worker()` rather than the worker bound to the requested thread (`codex-control-centre/backend/routers/turns.py:553-574`).
- The handler returns `approved`/`declined` even when neither a database approval nor pending RPC existed (`codex-control-centre/backend/routers/turns.py:576-579`).
- Governance RPC registries are process-global in-memory dictionaries (`codex-control-centre/backend/services/governance_service.py:157-202`).

**Impact**

An approval can be applied to the wrong thread/worker, replayed after context loss, or reported as successful without resolving anything. Combined with CCC-SEC-001, any tenant manager can approve another user's high-risk operation.

**Required tests**

1. `test_approval_requires_exact_tenant_user_thread_turn_worker_binding`.
2. `test_unknown_or_expired_approval_returns_404_not_success`.
3. `test_duplicate_approval_is_rejected_and_not_replayed`.
4. `test_approval_command_digest_must_match_worker_request`.
5. `test_restart_cancels_or_rehydrates_pending_approval_fail_closed`.

### CCC-SEC-006 — High — Support-ticket launch fabricates an active turn after dispatch failure

**Evidence**

- The launch handler catches any `start_turn` exception and, if no turn exists, creates a local `CodexTurn(status="active")` even though no worker was started (`app/api/routers/admin_support_tickets.py:493-519`).
- It then sets the ticket to `queued_for_codex`, records `launched_codex`, and returns a successful launch response (`app/api/routers/admin_support_tickets.py:521-539`).
- The existing test verifies only created IDs/status, not that a worker accepted the turn (`tests/test_admin_support_tickets.py:300-339`).

**Impact**

The supervisory record can claim work is queued and active when no executor exists. Operators may wait indefinitely or accept nonexistent work as an investigation run.

**Required tests**

1. `test_support_launch_dispatch_failure_returns_503_and_marks_dispatch_failed`.
2. `test_support_launch_never_creates_active_fallback_turn`.
3. `test_ticket_queued_only_after_worker_acknowledgement`.
4. `test_launch_audit_event_records_failure_reason_and_no_false_turn_id`.

### CCC-SEC-007 — High — Prompt, support context, and advisory data can leak externally or into global plaintext state

**Evidence**

- Advisory requests enable web research by default (`app/api/routers/resident_agent.py:50-53`).
- The raw prompt is sent as the DuckDuckGo query (`app/services/resident_agent/web_researcher.py:94-127`) and returned in the result (`app/services/resident_agent/web_researcher.py:177-184`).
- The raw prompt is also stored/published in resident events as described in CCC-SEC-003.
- Control Centre turns persist raw `prompt` and arbitrary item JSON without tenant ownership, redaction state, classification, retention, or encryption metadata (`codex-control-centre/backend/models/codex.py:34-58`).
- Support launch scrubs title and description but serializes `ticket.error_context` without scrubbing (`app/api/routers/admin_support_tickets.py:465-491`).

**Impact**

Source fragments, customer details, booking notes, tokens, stack traces, or identifiers placed in an advisory or ticket error context may be sent to an external search service or stored in a globally readable local database/event stream.

**Required tests**

1. `test_advisory_external_search_uses_derived_technical_query_only` with PII/secret canaries and a captured HTTP request.
2. `test_support_error_context_is_allowlisted_and_scrubbed_before_codex_prompt`.
3. `test_turn_and_item_storage_rejects_or_redacts_sensitive_fields`.
4. `test_prompt_retention_and_deletion_are_enforced_per_owner`.

### CCC-SEC-008 — High — Several monitoring/reporting paths claim success without evidence

**Evidence**

- Failed or unconfigured Chatwoot and SMS alerts are recorded as simulated channels while the record status is still `DISPATCHED`; the status API always claims remote approval is enabled (`app/services/resident_agent/alert_dispatcher.py:27-40`, `68-115`).
- SMS and Chatwoot sentinel exceptions return `healthy: True` (`app/services/resident_agent/sentinel_scheduler.py:184-193`, `228-237`), allowing the aggregate sweep to report `HEALTHY` when checks failed (`app/services/resident_agent/sentinel_scheduler.py:128-137`).
- Unknown remediation issues produce invented RCA text, a generic file target, and a fabricated diff rather than an evidence-based brief (`app/services/resident_agent/remediation_planner.py:139-162`).
- Offline research fallback says architectural guidance was “Verified” or that patterns were “Reviewed” without a successful external retrieval (`app/services/resident_agent/web_researcher.py:152-171`).
- The code auditor marks a missing test target as `passed: True` while also saying it was skipped (`app/services/resident_agent/code_auditor.py:166-176`).

**Impact**

A supervisor built on these statuses cannot distinguish success from unavailable, unknown, simulated, skipped, or failed. This is an acceptance-integrity defect, not cosmetic wording.

**Required tests**

1. `test_alert_failure_reports_failed_or_unavailable_never_dispatched`.
2. `test_sentinel_check_exception_is_unknown_or_degraded_never_healthy`.
3. `test_unknown_issue_yields_evidence_required_not_fabricated_diff`.
4. `test_offline_research_labels_sources_curated_and_retrieval_unverified`.
5. `test_missing_test_target_is_skipped_and_cannot_contribute_pass_credit`.

### CCC-SEC-009 — High — Durable supervisory context, independent audit, and evidence integrity are absent

**Evidence**

- Resident issues, plans, latest audit, health score, alert history, and event history are in-memory singleton fields (`app/services/resident_agent/engine.py:58-66`; `app/services/resident_agent/event_broker.py:16-23`; `app/services/resident_agent/alert_dispatcher.py:18-25`). Restart loses the supervisory state.
- Control Centre persistence has projects, threads, turns, items, approvals, subagents, boundaries, and settings only; there are no work-package, brief-revision, decision, risk, checkpoint, evidence, audit-verdict, author identity, reviewer identity, baseline/submitted commit, command exit-code, or artifact-digest entities (`codex-control-centre/backend/models/codex.py:6-105`).
- An authenticated caller can publish an arbitrary event payload (`codex-control-centre/backend/routers/events.py:168-188`), so events cannot be treated as execution evidence.
- `SubAgent` tracks only name, role, status, progress, and current action, and has no immutable assignment/evidence relationship (`codex-control-centre/backend/models/codex.py:77-90`).

**Impact**

Context cannot reliably survive restart/compaction, claimed test results cannot be tied to a commit and execution environment, and the system cannot prove that an auditor was independent of the author. It therefore cannot safely auto-accept delegated work.

**Required tests**

1. `test_supervisor_checkpoint_recovers_after_process_restart`.
2. `test_evidence_requires_run_commit_command_exit_code_timestamp_and_digest`.
3. `test_evidence_is_append_only_and_actor_attributed`.
4. `test_audit_reviewer_cannot_equal_author_and_receives_fresh_context`.
5. `test_acceptance_rejected_without_complete_acceptance_matrix_and_evidence`.

### CCC-SEC-010 — Medium — SSE tickets are scoped to IDs, not identity, and are reusable

**Evidence**

- Ticket records contain only `project_id`, `thread_id`, expiry, and consumption time—no user, tenant, session, purpose, or nonce state (`codex-control-centre/backend/services/sse_tickets.py:12-18`).
- Ticket issuance does not verify the project/thread exists or belongs to the requesting principal (`codex-control-centre/backend/routers/events.py:72-76`).
- A consumed ticket remains valid for repeated connections for 15 seconds (`codex-control-centre/backend/services/sse_tickets.py:39-62`), contrary to the module's “single-use” description.
- JWT fallback stream authorization checks role only and ignores tenant/account association (`codex-control-centre/backend/routers/events.py:47-60`).

**Impact**

A leaked ticket may be replayed during its grace window, and authorized users can mint tickets for guessed global IDs. This compounds the missing ownership model.

**Required tests**

1. `test_sse_ticket_is_one_use_without_reconnect_grace_replay`.
2. `test_sse_ticket_is_bound_to_principal_tenant_and_session`.
3. `test_ticket_issue_rejects_nonexistent_or_unowned_project_thread_pair`.
4. `test_jwt_stream_auth_requires_same_scope_as_ticket`.

### CCC-SEC-011 — Medium — Control database isolation is intended but not strictly enforced

**Evidence**

- Configuration comments require the database to resolve unambiguously to `codex.db`, but the validator accepts every URL beginning with `sqlite`, regardless of filename or location (`codex-control-centre/backend/config.py:66-73`).
- Schema creation uses `Base.metadata.create_all` rather than applying/verifying the existing Alembic migration chain (`codex-control-centre/backend/database.py:20-21`; `app/main.py:247-264`).
- The database stores raw prompts/items and global authorization state without ownership as covered above.

**Impact**

An environment override can point the control service at an unintended SQLite database, including one outside the intended folder, and startup can silently create an incomplete schema instead of proving migration state. The main PostgreSQL URL is rejected, which is a useful partial safeguard.

**Required tests**

1. `test_codex_database_url_accepts_only_canonical_codex_db_path` (with an explicit test-only override mechanism).
2. `test_codex_startup_refuses_unapplied_or_divergent_migrations`.
3. `test_codex_db_file_permissions_are_owner_only_where_supported`.

### CCC-SEC-012 — Medium — Workspace boundaries are structurally useful but administratively mutable and broader than documented

**Evidence**

- Defaults include both `codex-control-centre` and its parent FastAPI Bookings repository even though configuration comments describe isolation to the Control Centre directory (`codex-control-centre/backend/config.py:8-13`; `codex-control-centre/backend/services/boundary_service.py:36-43`).
- Startup always seeds the parent boundary and pre-existing project paths (`codex-control-centre/backend/services/boundary_service.py:82-113`).
- `add_boundary` accepts any existing directory; it does not constrain additions to a deploy-time root (`codex-control-centre/backend/services/boundary_service.py:144-178`).
- The per-worktree target uses string-prefix containment rather than `Path.is_relative_to`, although separator rejection makes the present construction harder to exploit (`codex-control-centre/backend/services/worktree_service.py:48-56`).

**Impact**

The effective filesystem authority is database-configurable at runtime, so the worktree sandbox is only as strong as the over-broad admin authorization protecting settings.

**Required tests**

1. `test_runtime_boundary_must_be_child_of_deploy_allowlist`.
2. `test_symlink_boundary_and_worktree_escape_rejected`.
3. `test_worktree_target_uses_path_relative_check_on_windows_case_variants`.
4. `test_worker_cwd_equals_assigned_worktree_and_cannot_write_parent_repo`.

## Safe remediation order

1. **Contain authority immediately.** Keep resident execution unavailable. Feature-flag the mounted Control Centre to local development and restrict every mounted control route—including events and diagnostics—to `require_platform_owner` until real ownership exists. Remove `local_secret` acceptance in mounted mode.
2. **Fix data ownership before delegation.** Add tenant/user/actor ownership migrations to projects, threads, turns, items, approvals, subagents, tickets, evidence, and audits. Backfill or quarantine existing global rows. Enforce ownership in every query and worker lookup.
3. **Close streaming and file-read paths.** Authenticate and scope resident SSE; bind Control Centre tickets to principal and make them genuinely single-use; eliminate raw-token query fallback; remove arbitrary `Path(skill_id)` reads and use bounded skills-RAG only.
4. **Constrain host access.** Make workspace roots deploy-time allowlists; allow runtime selection only beneath them; separate platform-owner settings from tenant administration; test symlink, case, UNC, and sibling-prefix escape cases.
5. **Make approvals cryptographically and transactionally exact.** Bind approval to tenant/user/thread/turn/run/worker plus command digest and expiry. Resolve once in a transaction, dispatch only to the bound worker, and return 404/409 when no pending request exists.
6. **Eliminate false-success semantics.** Remove fallback active turns, simulated dispatched alerts, fail-open healthy checks, fabricated generic diffs, and unverified “reviewed/verified” claims. Use explicit `unknown`, `unavailable`, `failed`, and `skipped` states.
7. **Establish privacy boundaries.** Derive allowlisted technical search queries, scrub structured error context recursively, classify/redact persisted prompts/items, add retention/deletion, and verify no PII reaches logs, SSE, search, or evidence artifacts.
8. **Build the durable supervisor ledger.** Add versioned work packages/briefs, decisions, checkpoints, assignments, immutable evidence, acceptance matrices, and author/reviewer identities. Evidence must include baseline/submitted commit, exact command, exit code, timestamp, environment, bounded output digest, and artifact references.
9. **Enforce independent audit.** Reviewer identity must differ from author; reviewer gets the original brief, exact diff, evidence, and a fresh context—not the author's reasoning transcript. Acceptance must fail closed if criteria or evidence are incomplete.
10. **Only then widen autonomy.** Re-enable delegation-first/hybrid modes incrementally behind policy profiles and negative isolation tests. External side effects, pushes, deployments, SMS, bookings, payments, and customer contact remain separately authorized.

## Minimum release gate for a resident Development Supervisor

- Zero Critical or High findings open.
- Platform-owner and cross-tenant negative tests pass for every route and stream.
- No static/default secret works in mounted mode.
- Every run is bound to one principal, work package, repository root, worktree, and baseline commit.
- Every approval is single-use, scoped, expiring, actor-attributed, and digest-bound.
- Every claimed test or audit result has independently reproducible evidence.
- Dispatch/monitoring states distinguish `accepted`, `running`, `completed`, `failed`, `unknown`, `unavailable`, and `skipped`.
- PII/secret canary tests prove no leakage to prompts, logs, SSE, web search, or persisted evidence.
- A fresh reviewer—not the author—must sign the acceptance matrix before merge/push authority is considered.

## Audit limitations

This baseline is a source-level control review of the current working tree, which already contained extensive unrelated user changes. It did not inspect database contents, environment values, live network services, external provider accounts, the separate standalone repository, or production deployment configuration. Findings therefore describe code-level capability and missing guarantees; they do not assert that an exploit has occurred.
