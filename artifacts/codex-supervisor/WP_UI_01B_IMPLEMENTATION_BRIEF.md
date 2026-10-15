# WP-UI-01B — Planning Foundations

## Scope

This work package adds a durable, tenant and platform-owner scoped planning ledger to the
native Codex Control Centre.  The fixed cutover remains `v1_only`; this package does not
execute, dispatch, approve tools, create worktrees, run commands, ingest evidence, or
produce audit findings/verdicts.

## Resources and state

`Mission (mis_)` belongs to the claimed project and is `draft|planned`. A work package
(`wpk_`) belongs to a mission and is `draft|brief_ready|brief_approved`. Brief revisions
(`brf_`) are immutable once approved (`draft|approved|superseded`). Context checkpoints
(`ctx_`) are append-only, ordered structural summaries. Audit scopes (`asc_`) contain only
bounded criteria and exclusions; they never contain evidence, findings, results or a verdict.
Creating a later draft while a work package has an approved brief changes that package to
`brief_ready`; approving the draft atomically supersedes the prior approved revision and
returns the package to `brief_approved`. These are the only mutable work-package transitions.

All resources are isolated by `project_id`, `tenant_id`, and `owner_user_id`. Cross-scope
lookups return the ordinary absence-like `404 resource_not_found` response. Stored fields are
bounded structural text only and reject source code, paths, shell commands, credentials, PII,
raw prompts, outputs, logs, evidence and outcome language.
The validator uses an allowlisted single-line structural-prose grammar plus bounded field
schemas and lexical/pattern checks; it does not retain raw operational material for later
screening.

## Authorization metadata

Briefs carry `future_execution_authorization_requirement`, either
`requires_authorization` (the default) or `not_required_once_requested`. The latter is only
accepted from the authenticated active platform owner. It is future planning metadata only:
it creates no run, grant, expiry, tool permission, bypass, inheritance or retry behavior. A
future dispatch package must still create and validate a per-run atomic grant. The persisted
API never calls this a "God mode".

## API contract

All routes are under `/api/admin/codex/v2`, use the existing `{data,meta}` envelope,
`Cache-Control: no-store`, `X-Request-ID`, and `ETag` for resource reads/mutations. All
mutation requests require native `ActorScope`, JSON, UUIDv4 `Idempotency-Key`, `If-Match`
for the stated parent/resource version, explicit `confirmation:true`, and idempotent replay.
The action registry version is `0.2`: `claim_project`, `create_mission`,
`create_work_package`, `create_brief`, `approve_brief`, `record_context_checkpoint`, and
`define_audit_scope`.

Routes: list/create missions; get mission; list/create mission work packages; get work
package; list/create work-package briefs; get brief; approve brief; list/create mission
checkpoints; list/create work-package audit scope. Creation is immutable; approval only
transitions a draft brief atomically and supersedes prior approved revision. Audit scope
requires an approved brief. No PATCH, delete, execution, worker, SSE, v1 change or frontend
route is included.

## Persistence and verification

Alembic `004` preserves every `003` claim/idempotency/event row and digest chain while
expanding action-code constraints. SQLite has fifteen planning triggers: five ancestry guards
and two immutable/append-only guards for each planning table. Readiness exact-hashes those
guards plus the revised idempotency/event structures and terminal/event append-only guards.
SQLite triggers prevent direct update/delete of immutable planning rows, checkpoints and audit
scopes. Readiness requires revision `004` and exact schema structure. Tests cover migration
from 001, cross-scope absence, idempotency/replay,
immutability, unsafe-field rejection, API headers/OpenAPI, and the inert authorization
metadata.

## Changed-file allowlist

Only the 22 paths authorised for WP-UI-01B may change. `tests/conftest.py` is
the sole root-level addition: it migrates a process-unique temporary CCC SQLite
database to revision `004` before mounted-app imports. It is test-fixture-only;
production startup remains DDL-free.
