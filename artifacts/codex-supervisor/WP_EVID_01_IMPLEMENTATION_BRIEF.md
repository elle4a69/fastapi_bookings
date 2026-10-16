# WP-EVID-01 — Evidence and Independent-Audit Foundation

## Scope

Add a fail-closed, tenant/owner-scoped evidence ledger for V2 supervisor runs.
The package stores only fixed criterion codes, structural Git identities/digests,
baseline/audit snapshot digests, sandbox attestations, audit-request state, and
criterion outcome codes. It never stores or reads worker turns, items, events,
SSE, prompts, commands, paths, diffs, logs, secrets, PII, or raw test results.

## Changed-file allowlist

- `codex-control-centre/alembic/versions/006_evidence_audit_foundation.py`
- `codex-control-centre/backend/models/codex.py`
- `codex-control-centre/backend/services/evidence_audit_service.py`
- `codex-control-centre/backend/services/supervisor_run_service.py`
- `codex-control-centre/backend/routers/v2_supervisor.py`
- `codex-control-centre/backend/services/migration_readiness_service.py`
- `codex-control-centre/tests/test_evidence_audit_foundation.py`
- `codex-control-centre/README.md`

## Non-goals

No audit worker dispatch, writable worktree, generic worktree use, legacy worker
inspection, browser evidence writes, implementation verdict, UI, or merge.
An audit request records `sandbox_unavailable` unless a separately implemented,
host-enforced independent sandbox can create a valid attestation.
