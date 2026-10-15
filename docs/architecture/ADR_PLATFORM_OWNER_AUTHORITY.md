# ADR: Persisted Platform-Owner Authority

**Status:** Accepted

**Date:** 2026-10-15

**Supersedes:** only the inferred `owner or is_superuser` authority statement in the historical P0 independent review artifacts

## Context

The Control Centre, resident development agent, and platform support console
operate across tenant boundaries. Tenant roles such as `owner`, `admin`, and
`manager` describe authority inside one business account and cannot safely
grant platform-wide development or support access. Dynamic attributes and JWT
claims are likewise not authoritative persisted state.

## Decision

`users.is_platform_owner` is the sole platform authority bit. It is non-null,
defaults to false in both SQLAlchemy and the database, and is deliberately not
part of public user schemas, JWTs, or `/admin/auth/me` responses.

Every protected request reloads the tenant-scoped user row and requires both
`is_active is True` and `is_platform_owner is True`. Ordinary tenant roles,
dynamic `is_superuser` values, browser claims, and local-development tokens do
not confer authority. `LOCAL_AUTH_BYPASS` only selects an active, persisted
platform owner in the active tenant.

The sole supported writer is the offline `scripts/manage_platform_owner.py`
entry point backed by `app/services/auth/platform_owner_authority.py`. Applied
changes require positive numeric tenant/user IDs, an allowlisted reason, an
exact typed confirmation, a database-global mutation lock, and a structural
`AuditLog` in the same transaction. Revoking the last active platform owner is
refused. Dry-runs and idempotent no-ops do not write audit rows.

PostgreSQL uses transaction-scoped advisory lock key
`7247691531061001` followed by a target `SELECT FOR UPDATE`; SQLite uses
`BEGIN IMMEDIATE`. Unsupported dialects fail closed.

## Consequences

- Existing rows and all new creation paths begin without platform authority.
- Initial production provisioning is an explicit offline operator procedure;
  migration alone intentionally produces zero platform owners.
- Revocation or deactivation takes effect on the next request without token
  rotation because the capability is not embedded in the token.
- Future user deactivation or deletion flows that affect a platform owner must
  reuse the same serialized guard before they may be introduced.
- The additive column remains during a code rollback. Database downgrade is
  forbidden while application code references it and loses capability state.

## Historical evidence

`P0_INDEPENDENT_REVIEW.md` and `P0_INDEPENDENT_REREVIEW.md` remain immutable
historical evidence. This ADR corrects only their authority premise; it does
not invalidate their accepted transport, SSE ticket, Skills-RAG,
worker-acknowledgement, or mounted-secret containment findings.

## Verification

```powershell
F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -m pytest tests/test_platform_owner_authority.py tests/test_platform_owner_authority_migration.py tests/test_auth_contract.py -v
F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -m alembic heads
python scripts/verify_living_docs.py --path app/services/auth/README.md
```
