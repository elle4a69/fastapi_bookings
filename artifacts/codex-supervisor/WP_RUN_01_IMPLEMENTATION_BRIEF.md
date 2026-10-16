# WP-RUN-01 — bounded V2 run lifecycle

## Purpose

Add the first durable execution-control layer for the native Codex Supervisor.
This package records an approved Brief's immutable digest and audit-scope binding,
issues a one-run, expiring start-authorisation grant where policy permits, and
persists one dispatch intent before contacting the real Codex app-server bridge.

## Safety contract

- The V2 route is platform-owner and tenant/user scoped; it never calls legacy
  turn, governance, thread, event, or worktree HTTP routes.
- A Brief remains immutable. Its waiver metadata only controls whether a grant
  may be issued without a separate confirmation; it never grants a worker,
  tool, shell, filesystem, Git, secret, database, or deployment capability.
- A platform owner explicitly issues a random opaque start-authorisation token.
  Only its hash is stored; the token is returned once and never entered into an
  event, idempotency replay body, log, or later browser read. It is uniquely
  scope-bound, expires, and is atomically consumed with the run and
  dispatch-intent record. A retry requires a new grant.
- The bridge owns the project identity, worktree selection, and a fixed
  capability profile. It starts only a real app-server WorkerManager path.
- Missing safe prerequisites fail closed. An external acknowledgement changes a
  durable run from `dispatching` only on positive acknowledgement; exceptions
  and ambiguous outcomes become `dispatch_unknown` and are never auto-redriven.
- Neither the ledger nor browser responses persist or disclose prompts, worker
  output, commands, diffs, secrets, database material, customer data, or PII.

## Exact changed-file allowlist

1. `artifacts/codex-supervisor/WP_RUN_01_IMPLEMENTATION_BRIEF.md`
2. `codex-control-centre/alembic/versions/005_supervisor_run_lifecycle.py`
3. `codex-control-centre/backend/models/codex.py`
4. `codex-control-centre/backend/schemas/v2_supervisor.py`
5. `codex-control-centre/backend/routers/v2_supervisor.py`
6. `codex-control-centre/backend/services/supervisor_run_service.py`
7. `codex-control-centre/backend/services/supervisor_event_service.py`
8. `codex-control-centre/backend/services/migration_readiness_service.py`
9. `codex-control-centre/tests/test_supervisor_runs.py`
10. `codex-control-centre/tests/test_migrations.py`
11. `tests/conftest.py`
12. `tests/test_codex_backend_mount.py`
13. `codex-control-centre/README.md`
14. `docs/architecture/ADR_CODEX_SUPERVISOR_V2_FACADE.md`
15. `docs/README.md`
16. `docs/MODULE_INDEX.md`
17. `docs/module_manifest.json`
18. `docs/AGENT_BOOT_SNAPSHOT.md`

No frontend, legacy route, booking-domain, external-provider, evidence, audit
verdict, or active-run UI changes are part of this package.
