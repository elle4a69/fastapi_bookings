# WP-UI-01A — Configured Project Claim and Durable Control-Plane Foundation

- **Status:** implementation-ready rebrief; implementation not started
- **Programme:** FastAPI Bookings Codex Development Supervisor
- **Anti-Gravity parent task:** `ccc_wp_ui_01`
- **Anti-Gravity child task:** `ccc_wp_ui_01a`
- **Required branch:** `codex/codex-supervisor-wp-ui-01a`
- **Required base:** `3aa3b33b44907148c0e1854eb0373c03dc8a55a4`
- **Canonical application:** `F:\Projects\fastapi_bookings`
- **Excluded application:** the separate `F:\Projects\codex-control-centre` repository

## 1. Outcome

WP-UI-01A creates the smallest safe, real persistence and API foundation for the
resident Codex supervisor without prematurely enabling a second mutation plane.
It must:

1. reconcile the integrated Control Centre's Alembic ledger with the schema that
   production `Base.metadata.create_all()` historically produced, including
   `workspace_boundaries` and `system_settings`;
2. stop relying on production `create_all()` and report migration readiness
   truthfully without automatically upgrading or stamping a database;
3. derive an immutable platform-owner `ActorScope` from the authenticated native
   FastAPI Bookings user;
4. add deploy-configured FastAPI Bookings repository root, display name, and
   opaque configured-project ID settings;
5. expose only authenticated, bounded v2 bootstrap, readiness, cutover-read, and
   configured-project read/claim contracts;
6. claim or create the configured project transactionally, using server-owned
   path configuration and a stored fingerprint rather than browser authority;
7. provide durable 24-hour idempotency reservation, fingerprinting, exact replay,
   and unknown-outcome safety for the claim mutation;
8. append an immutable, bounded project-scoped audit/event row in the same
   transaction as a successful claim and its terminal idempotency result; and
9. leave the current v1 Control Centre as the sole product mutation authority.

No Mission, Work Package, Brief, Assignment, Run, Evidence, Audit, Project Brain,
Intake, Operations mutation, v2 event-stream, frontend, or worker behavior is
implemented in this package.

## 2. Binding rebrief decisions

This brief narrows WP-UI-01 and requires a small clarification to the accepted
v2 facade ADR during implementation.

### 2.1 Cutover remains `v1_only`

- WP-UI-01A creates and reads a versioned singleton cutover row whose only legal
  value in this package is `v1_only`.
- There is no `PUT /operations/cutover-mode`, no `change_cutover_mode`
  descriptor, and no transition handler.
- The configured-project claim is a setup-plane mutation only. It does not set a
  project, thread, worker, or worktree to `supervisor_v2`; it does not authorize
  any Mission or worker mutation; it leaves `control_plane='legacy'`.
- Because v2 never becomes active in 01A, no stale-v1 mutation gate or evidence-
  backed activation can truthfully be claimed. Those are later prerequisites.

### 2.2 Action registry is an implemented v0.1 subset

- `action_registry_version` is exactly `0.1`.
- The only operator mutation code implemented or emitted is `claim_project`.
- Read endpoints are annotated `x-operator-action: false`.
- No placeholder route, disabled future descriptor, or synthetic handler is
  created for the frozen future 72-row registry `1.0`.
- CI proves a bijection between implemented v0.1 operator mutations, OpenAPI
  `x-action-code`, permission `project.claim`, and emitted descriptors.
- Promotion to registry `1.0` occurs only when the corresponding real endpoints
  exist and must be covered by a later ADR update and independent review.

### 2.3 Migration sequence is split before supervisor-domain tables

The earlier provisional `002`/`003` allocation is clarified as follows:

- `002_legacy_ledger_and_project_scope.py` reconciles the legacy Alembic ledger,
  records schema-adoption provenance, and adds project ownership/claim fields.
- `003_claim_idempotency_and_audit_events.py` creates the fixed `v1_only` cutover
  row, durable idempotency records, and the append-only project-scoped
  supervisor event/audit foundation.
- Mission, membership, work-package, brief, checkpoint, run, evidence, audit, and
  programme-scoped event tables move to later forward-only migrations. Applied
  `002` or `003` files must never be edited later.

### 2.4 One durable project-scoped event ledger

For 01A, `supervisor_events` is the append-only audit/event ledger. A claim row
contains the actor, request, action, outcome, project version, safe structural
payload, and integrity digest. It is sufficient for claim/readiness provenance
without inventing a Mission. Later migrations may add nullable Mission/run
correlation columns, but may not rewrite 01A rows or weaken append-only guards.

## 3. Changed-file allowlist for implementation

The implementer may modify or create only these exact paths:

1. `artifacts/codex-supervisor/WP_UI_01A_IMPLEMENTATION_BRIEF.md` — immutable
   signed task contract; only a separately approved rebrief may change it.
2. `docs/architecture/ADR_CODEX_SUPERVISOR_V2_FACADE.md` — document the 01A
   split, fixed `v1_only` posture, registry `0.1`, and revised migration order.
3. `codex-control-centre/README.md` — living module documentation and exact
   verification/adoption/rollback commands.
4. `docs/AGENT_BOOT_SNAPSHOT.md` — generated living-document index output only.
5. `docs/MODULE_INDEX.md` — generated living-document index output only.
6. `docs/module_manifest.json` — generated living-document index output only.
7. `codex-control-centre/backend/config.py`.
8. `codex-control-centre/backend/database.py`.
9. `codex-control-centre/backend/main.py`.
10. `codex-control-centre/backend/models/codex.py`.
11. `codex-control-centre/backend/schemas/v2_supervisor.py` — new.
12. `codex-control-centre/backend/routers/v2_supervisor.py` — new.
13. `codex-control-centre/backend/services/actor_scope.py` — new.
14. `codex-control-centre/backend/services/migration_readiness_service.py` — new.
15. `codex-control-centre/backend/services/legacy_adoption_service.py` — new.
16. `codex-control-centre/backend/services/cutover_service.py` — new, read-only.
17. `codex-control-centre/backend/services/idempotency_service.py` — new.
18. `codex-control-centre/backend/services/supervisor_repository.py` — new.
19. `codex-control-centre/backend/services/supervisor_event_service.py` — new.
20. `codex-control-centre/alembic/versions/002_legacy_ledger_and_project_scope.py`
    — new.
21. `codex-control-centre/alembic/versions/003_claim_idempotency_and_audit_events.py`
    — new.
22. `app/main.py` — authenticated mounted router and non-mutating readiness startup.
23. `codex-control-centre/tests/test_supervisor_identity.py` — new.
24. `codex-control-centre/tests/test_supervisor_bootstrap_claim.py` — new.
25. `codex-control-centre/tests/test_supervisor_idempotency.py` — new.
26. `codex-control-centre/tests/test_supervisor_events.py` — new.
27. `codex-control-centre/tests/test_migrations.py`.
28. `tests/test_codex_backend_mount.py`.

No dependency or lockfile change is authorized. If another path is required,
stop and rebrief before modifying it. The three generated documentation outputs
may change only by running the repository's documented index generator after the
README/ADR changes; hand edits are forbidden.

## 4. Configuration contract

Add these non-secret settings to the integrated Control Centre settings model:

| Setting / environment name | Type | Rules |
|---|---|---|
| `supervisor_configured_project_id` / `CODEX_SUPERVISOR_CONFIGURED_PROJECT_ID` | string or null | Opaque, 1–96 characters, `[A-Za-z0-9_-]`, preferably `prj_...`; no path semantics |
| `supervisor_configured_repo_root` / `CODEX_SUPERVISOR_CONFIGURED_REPO_ROOT` | string or null | Absolute existing directory; resolved server-side; must be the configured FastAPI Bookings Git worktree root |
| `supervisor_configured_project_name` / `CODEX_SUPERVISOR_CONFIGURED_PROJECT_NAME` | string | Safe display text, trimmed 1–120 characters; default `FastAPI Bookings` |

Both ID and root are required for claim readiness. Missing either produces
`state='unconfigured'`; it never falls back to the Control Centre directory or a
browser-provided path. Validation resolves the final local path and verifies a
Git worktree marker without logging or returning the path. Configuration failure
returns only safe reason codes such as `configured_root_missing`,
`configured_root_not_absolute`, or `configured_root_not_git_worktree`.

The stored `configured_root_fingerprint` is lower-case SHA-256 over a canonical,
Windows-case-normalized representation of the resolved root plus the configured
opaque project ID. It is an internal comparison value, never returned to the
browser or telemetry. The raw configured root remains server-side in the legacy
`projects.repo_path` column because the current worker requires it; no v2 schema,
error, event, or log may serialize it.

## 5. Actor and authorization contract

`ActorScope` is a frozen dataclass or equivalent immutable value with:

```text
tenant_id: positive integer
user_id: positive integer
role: normalized bounded string
is_platform_owner: true
```

It is built only from the `User` returned by native FastAPI Bookings
`require_platform_owner`. Request bodies, headers other than native auth/tenant
resolution, query parameters, and the Control Centre database cannot override
tenant or user identity.

- Every v2 endpoint requires native authentication and platform-owner authority.
- Ordinary tenant `admin`, `manager`, `provider`, inactive/invalid users, and
  standalone `TOKEN_SECRET` callers are denied before a Control Centre domain
  query.
- Cross-tenant, differently owned, guessed, quarantined, and hidden project IDs
  return the same non-leaking `404 resource_not_found` where disclosure is not
  permitted.
- The v2 router is mounted only by FastAPI Bookings at
  `/api/admin/codex/v2`. It is not mounted into the standalone Control Centre
  app, because standalone shared-secret identity cannot form an `ActorScope`.

## 6. Persistence contract

All timestamps are UTC `DateTime(timezone=True)`. JSON is schema-versioned,
bounded structural data. Opaque IDs use cryptographically random UUID-derived
values with stable prefixes. SQLite foreign keys remain enabled.

### 6.1 Existing `projects` additions in migration 002

| Column | Type | Rules |
|---|---|---|
| `tenant_id` | integer nullable | External FastAPI Bookings reference; null while unclaimed |
| `owner_user_id` | integer nullable | External native user reference; null while unclaimed |
| `scope_state` | string(16) not null | `unclaimed|claimed|quarantined`; default `unclaimed` |
| `control_plane` | string(20) not null | `legacy|supervisor_v2`; default and only 01A value `legacy` |
| `configured_root_fingerprint` | string(64) nullable | lower-case SHA-256, internal only |
| `version` | integer not null | default `1`, positive optimistic version |

Add checks for both enums and positive version; unique `(tenant_id, id)`; indexes
on `(scope_state, id)` and `(tenant_id, owner_user_id, updated_at)`. Existing rows
become `unclaimed` unless deterministic schema validation shows an unsafe or
conflicting configured identity, in which case they become `quarantined`.
Migration never infers tenant or owner from `repo_path`, prompts, threads, names,
or historical content.

Thread/run lineage and descendant tenant denormalization are deliberately
deferred because 01A neither reads nor mutates those resources through v2.

### 6.2 Alembic ledger reconciliation in migration 002

The current ORM contains `workspace_boundaries` and `system_settings`, while
revision `001` does not. Migration 002 must:

1. inspect names and exact safe column signatures before DDL;
2. create either table only if absent;
3. fail closed on a same-name incompatible table;
4. create `schema_adoption_metadata` with a singleton row recording whether each
   table pre-existed, the source schema classification, revision, and timestamp;
5. never copy or log boundary paths or setting values; and
6. use the provenance flags during downgrade so tables created by 002 are
   removed while verified pre-existing runtime tables are preserved.

`schema_adoption_metadata` contains no path, setting value, secret, prompt, or
customer data.

### 6.3 `control_plane_cutover_state` in migration 003

Singleton row, keyed by `id='global'`:

- `mode='v1_only'` with a database check permitting only `v1_only` in 01A;
- `version=1`, positive;
- `effective_at`, `updated_at` UTC;
- `updated_by_user_id` nullable for the migration seed; and
- `last_event_id` nullable.

There is no mutation service method for this table in 01A.

### 6.4 `idempotency_records` in migration 003

| Column | Rules |
|---|---|
| `id` | `idr_` opaque primary key |
| `tenant_id`, `actor_user_id` | required external identity scope |
| `method`, `normalized_path`, `action_code` | bounded allowlisted values |
| `key_sha256` | SHA-256 of UUIDv4 idempotency key; raw key is never stored |
| `request_fingerprint` | SHA-256 over actor, tenant, method, normalized path, canonical body hash, expected version |
| `state` | `in_progress|succeeded|failed` |
| `request_id` | original safe request identifier |
| `response_status` | nullable until terminal |
| `response_body_json` | bounded safe terminal envelope only |
| `response_headers_json` | allowlist: `ETag`, `Idempotency-Replayed` metadata only |
| `resource_type`, `resource_id`, `resource_version` | bounded nullable terminal linkage |
| `error_code` | safe nullable terminal code |
| `created_at`, `completed_at`, `expires_at` | `expires_at = created_at + 24 hours` |

Unique `(tenant_id, actor_user_id, method, normalized_path, key_sha256)` and an
expiry index are required. A same key/fingerprint replays the original terminal
status and safe body; a different fingerprint returns
`409 idempotency_conflict`. Expired records may be purged only after terminal
state. Resource uniqueness/state checks still prevent a duplicate claim after
expiry.

### 6.5 `supervisor_events` in migration 003

Project-scoped append-only rows:

- `id` (`sev_` opaque primary key);
- `tenant_id`, `project_id`, monotonically increasing `sequence` per project;
- `event_type` (01A permits `project.claimed` only);
- `action_code` (`claim_project`);
- `actor_user_id`, `request_id`, nullable `correlation_id`;
- `idempotency_record_id`, `resource_version`, `outcome`;
- `payload_json` containing only safe IDs, state, version, and reason codes;
- `payload_sha256`, `schema_version='0.1'`, and `occurred_at`.

Unique `(project_id, sequence)` and unique claim request/event linkage are
required. SQLite triggers reject `UPDATE` and `DELETE`; application services
provide append only. Payloads exclude repository paths/fingerprints, credentials,
headers, prompts, source, diffs, commands, customer/booking/SMS/payment data,
email, phone, and raw exception text.

## 7. Migration readiness and production startup

`Base.metadata.create_all()` must no longer be a production migration mechanism.
`init_db()` may remain as a compatibility symbol only if it performs a read-only
revision/schema readiness check and creates no table, column, index, trigger, or
seed row.

Startup behavior:

- open the configured database read-only where practical;
- compare current Alembic revision to the single expected head;
- verify required 01A tables/columns/triggers only when revision claims head;
- log bounded state/reason codes, never database URLs, paths, SQL, values, or raw
  exceptions;
- continue serving authenticated bootstrap/readiness when the schema is merely
  behind, returning `migration_required`;
- return `dependency_unavailable` when the database cannot be safely inspected;
  and
- never auto-run Alembic, auto-stamp, auto-backfill ownership, or auto-claim.

Legacy routes are unchanged. A database that is not ready must not be presented
as v2-ready.

## 8. Legacy database adoption matrix

The implementation and tests must support these exact cases:

| Input database | Required result |
|---|---|
| Empty file | Alembic `upgrade head` runs `001 -> 002 -> 003`; current=head; all required tables exist |
| Versioned revision `001` only | `upgrade head` creates missing ledger tables, scope fields, foundation tables and triggers |
| Versioned `001` with runtime-created `workspace_boundaries`/`system_settings` | 002 verifies and preserves both, records them as pre-existing, then reaches head |
| Unversioned database exactly matching the approved historical runtime-created schema | Readiness reports `migration_required` and `runtime_schema_adoption_required`; after quiesced backup and explicit operator `stamp 001`, `upgrade head` preserves data and reaches head |
| Unversioned, partial, unknown, or incompatible schema | No automatic stamp/DDL; readiness reports `migration_required` or `quarantined` with safe codes only |
| Current head | Startup/readiness performs no DDL and reports ready |

Tests use synthetic databases only. No test opens or mutates the repository's
real `codex.db`, `-wal`, or `-shm` files.

## 9. Project resolution and claim algorithm

### 9.1 Read resolution

After readiness is confirmed, compare the deployment-configured ID/fingerprint
with durable projects:

1. missing configuration -> `unconfigured`, no claim descriptor;
2. no row with configured ID and no conflicting fingerprint -> `claim_required`
   with virtual `project_version=0` and a real claim descriptor;
3. matching unclaimed row with matching fingerprint -> `claim_required` with its
   current version;
4. matching claimed row owned by the current actor scope -> `ready`;
5. mismatched ID/root fingerprint, multiple conflicting rows, quarantined row, or
   row claimed by another scope -> fail closed as `quarantined` or a non-leaking
   hidden state, with no usable descriptor.

A read never inserts, claims, repairs, or quarantines a row.

### 9.2 Claim transaction

For SQLite, use one `BEGIN IMMEDIATE` transaction or an equivalent proven
single-writer transaction:

1. authenticate and derive `ActorScope` before opening a domain query;
2. validate `Idempotency-Key`, `If-Match`, body/action, and configured state;
3. reserve or replay the actor/route-scoped idempotency record;
4. re-read configured project candidates inside the write transaction;
5. recompute the server-side configured-root fingerprint;
6. reject conflict/quarantine/cross-scope conditions without disclosure;
7. create the configured project when absent, or compare-and-swap the exact
   unclaimed row/version;
8. stamp `tenant_id`, `owner_user_id`, `scope_state='claimed'`, fingerprint,
   `control_plane='legacy'`, and increment/set the version;
9. append exactly one `project.claimed` event with the next project sequence;
10. finalize the idempotency record with the exact safe response; and
11. commit once.

If the transaction aborts, none of the project, event, or terminal idempotency
changes persist. Response loss after commit is recovered by replaying the exact
request/key. Different-key concurrent losers receive a safe terminal conflict;
they never overwrite ownership.

## 10. HTTP and OpenAPI contract

All paths below are relative to `/api/admin/codex/v2`. All responses set
`Cache-Control: no-store`. Request IDs are server generated or validated from the
existing correlation middleware. Schemas use Pydantic `extra='forbid'`.

Success envelope:

```json
{
  "data": {},
  "meta": {
    "request_id": "opaque-request-id",
    "schema_version": "0.1",
    "resource_version": 1
  }
}
```

Error envelope:

```json
{
  "error": {
    "code": "stable_safe_code",
    "message": "Bounded operator-safe message.",
    "request_id": "opaque-request-id",
    "details": {}
  }
}
```

Error details are allowlisted and may contain safe current versions or reason
codes. They never contain SQL, tracebacks, raw exceptions, host paths,
fingerprints, database URLs, hidden IDs, or credentials.

### 10.1 `GET /bootstrap`

Authentication: native platform owner. Operator action: false.

Returns `200` even when a safely inspectable database is behind, so the UI can
render a blocking readiness state. `ETag` is
`"bootstrap-<cutover_version>-<project_version_or_0>-<readiness_token>"` and is
informational under `no-store`.

```json
{
  "data": {
    "capabilities": {
      "can_view_supervisor": true,
      "can_claim_project": true
    },
    "action_registry_version": "0.1",
    "cutover": {
      "mode": "v1_only",
      "version": 1,
      "mutation_authority": {
        "legacy_owned": "v1",
        "supervisor_owned": "none",
        "allowed_drain_actions": []
      }
    },
    "readiness": {
      "state": "ready|migration_required|quarantined|dependency_unavailable",
      "current_revision": "001|002|003|null",
      "expected_revision": "003",
      "reason_codes": []
    },
    "project": {
      "state": "ready|unconfigured|claim_required|quarantined|migration_required",
      "project_id": "opaque-id-or-null",
      "display_name": "safe-name-or-null",
      "project_version": 1,
      "claim_action": null,
      "claim_action_absent_reason_code": "not_applicable|forbidden|resource_hidden|migration_required|unconfigured|null"
    }
  },
  "meta": {
    "request_id": "...",
    "schema_version": "0.1",
    "resource_version": 1
  }
}
```

For `claim_required`, `claim_action` replaces null with:

```json
{
  "registry_version": "0.1",
  "action": "claim_project",
  "allowed": true,
  "reason_code": null,
  "reason": null,
  "resource_version": 0,
  "risk_level": "medium",
  "confirmation": {
    "kind": "dialog",
    "phrase": null,
    "consequences": ["The configured project will be bound to your tenant and user scope."]
  },
  "idempotency_required": true,
  "expires_at": null
}
```

When readiness is not `ready`, domain tables are not queried and
`can_claim_project=false`. Authentication failure is `401`; non-platform owner is
`403`; an uninspectable dependency is `503 dependency_unavailable` only when no
safe readiness response can be produced.

### 10.2 `GET /operations/readiness`

Authentication: native platform owner. Operator action: false. Returns `200` with
the same bounded readiness object and no project path/schema content. No ETag is
used because this is a live diagnostic snapshot. Database inspection failure is
`503 dependency_unavailable`.

### 10.3 `GET /operations/cutover-mode`

Authentication: native platform owner. Operator action: false. Returns `200`,
`ETag: "cutover-1"`, fixed mode `v1_only`, version `1`, the mutation-authority
object above, `allowed_transitions: []`, and
`transition_absent_reason_code='deferred_by_wp_ui_01a'`.

`PUT`, `PATCH`, `POST`, or `DELETE` on this path is not registered and therefore
returns framework `405`. No hidden mutation helper exists.

### 10.4 `GET /projects`

Authentication: native platform owner. Operator action: false. Requires migration
readiness. Returns `200` and zero or one configured-project summary containing
only opaque ID, display name, claim state, version, control-plane value, and
allowed claim descriptor. It never returns `repo_path` or fingerprint. ETag is
`"projects-<digest-of-safe-id-version-state-vector>"`.

Migration not ready is `503 database_migration_required`; hidden/cross-scope
records are omitted rather than counted.

### 10.5 `POST /projects/{project_id}/claim`

Authentication: native platform owner. Permission: `project.claim`.
OpenAPI extensions:

```yaml
x-operator-action: true
x-action-code: claim_project
x-action-registry-version: "0.1"
x-backend-permission: project.claim
```

Required headers:

```http
Idempotency-Key: <UUIDv4>
If-Match: "project-<current_version>"
```

For a configured project with no row, current version is `0` and the required
ETag is `"project-0"`.

Request body:

```json
{
  "action": "claim_project",
  "registry_version": "0.1",
  "expected_version": 0,
  "confirmation": true
}
```

No tenant ID, user ID, repository path, fingerprint, project name, or
control-plane value is accepted. Extra fields are rejected.

First success is `200`, with `ETag: "project-<new_version>"`:

```json
{
  "data": {
    "project": {
      "project_id": "opaque-id",
      "display_name": "FastAPI Bookings",
      "state": "ready",
      "version": 1,
      "control_plane": "legacy"
    },
    "audit_event_id": "sev_..."
  },
  "meta": {
    "request_id": "...",
    "schema_version": "0.1",
    "resource_version": 1,
    "idempotency_state": "succeeded"
  }
}
```

Exact terminal replay returns the original status/body/ETag plus
`Idempotency-Replayed: true` and meta state `replayed`. A durable in-progress
record returns `202`, the original request ID, `operation_state='in_progress'`,
and `Retry-After: 1`; it never invents a project result.

Exact error behavior:

| HTTP/code | Condition |
|---|---|
| `400 precondition_mismatch` | Header/body versions disagree or malformed confirmation/action |
| `401 authentication_required` | Native authentication absent/invalid |
| `403 forbidden` | Authenticated actor is not a platform owner |
| `404 resource_not_found` | Guessed, hidden, cross-scope, or non-configured project ID |
| `409 idempotency_conflict` | Same key with a different canonical fingerprint |
| `409 invalid_state` | Already claimed/quarantined or otherwise not claimable without leaking another owner |
| `409 claim_guard_failed` | Safe configured-root/record guard failed |
| `412 revision_conflict` | Durable project version differs from `If-Match`/body |
| `422 validation_failed` | Body/UUID/action validation failed |
| `428 precondition_required` | `Idempotency-Key` or `If-Match` absent |
| `503 database_migration_required` | Alembic/schema readiness is not current |
| `503 dependency_unavailable` | Database/configured-root validation cannot safely complete |

## 11. Concurrency, integrity, and replay tests

Tests must prove:

1. two actors/keys racing the absent configured project create at most one row;
2. two keys racing one unclaimed version produce one claim and one safe conflict;
3. identical concurrent keys produce one project row, one event, and one terminal
   result that both callers receive or replay;
4. response loss after commit replays the exact body/status/ETag/event ID;
5. response loss before commit leaves no project, event, or terminal record;
6. same key with changed method/path/body/version/actor/tenant conflicts;
7. missing/stale/mismatched preconditions never mutate;
8. a new key after a terminal claim cannot duplicate or transfer ownership;
9. expiry is no earlier than 24 hours and purging only removes terminal expired
   records;
10. event sequences remain unique/monotonic under concurrent writers;
11. database triggers reject event update/delete; and
12. process restart preserves claim, replay result, event, and readiness state.

## 12. Security and disclosure negatives

Required negative tests include:

- unauthenticated, malformed token, ordinary admin, manager, provider, and
  standalone shared-secret access;
- guessed configured and non-configured IDs;
- different tenant/user owner, claimed-row collision, quarantined row, duplicate
  fingerprint, ID/path mismatch, missing Git marker, inaccessible root, and
  symlink/reparse root mismatch;
- body/query/header attempts using `repo_path`, `path`, `root`, `tenant_id`,
  `owner_user_id`, `fingerprint`, or `control_plane`;
- secret/PII/path canaries in validation failures, logs, response envelopes,
  OpenAPI examples, event payloads, and idempotency response storage;
- oversized strings, malformed Unicode/control characters, unknown fields,
  invalid UUID keys, and invalid/negative versions; and
- direct standalone Control Centre requests proving no v2 route is mounted.

No test may inspect `.env`, send SMS, create bookings, use customer data, start a
Codex worker, alter worktrees, or contact an external service.

## 13. Rollback and recovery

Before applying migrations to any retained `codex.db`:

1. stop all Control Centre writers/workers;
2. checkpoint and close SQLite WAL connections;
3. create and verify a recoverable database backup without separately copying
   live `-wal`/`-shm` files;
4. record current revision and synthetic schema fingerprint; and
5. run the migration first against a copy.

Application rollback before database migration is an ordinary reviewed code
revert. After migration:

- disposable/fresh/`001` databases must pass `003 -> 002 -> 001 -> head` tests;
- 003 downgrade drops its new triggers/tables in dependency-safe order;
- 002 downgrade removes project-scope additions and drops ledger tables only
  when `schema_adoption_metadata` proves 002 created them;
- for a retained adopted runtime database, operational rollback is restoration
  of the verified quiesced backup, not an improvised in-place downgrade; and
- no rollback may erase or overwrite an existing boundary/setting table that
  predates Alembic adoption.

No migration, restore, branch merge, deployment, or real-database operation is
authorized by this brief alone.

## 14. Living documentation requirements

Update `codex-control-centre/README.md` with all seven mandatory living-document
sections and specifically document:

- v2 01A purpose and deliberate exclusions;
- native platform-owner/ActorScope boundary;
- configuration names without real values;
- migration/adoption/readiness/backup/rollback procedure;
- the five exact endpoints and response states;
- idempotency/event integrity and privacy rules;
- known limitation: fixed `v1_only`, no Mission/work/worker mutation; and
- exact focused verification commands.

Update the ADR with context, decision, rationale, trade-offs, consequences, and
revisit triggers. Regenerate the three allowed documentation index outputs only
after the README/ADR are correct.

## 15. Verification gates

The implementer must first query the current command:

```powershell
python scripts/query_docs.py --test-command codex-control-centre
```

The README must register exact commands. At minimum run:

```powershell
# From repository root: mounted native auth/OpenAPI boundary
.\.venv\Scripts\python.exe -m pytest tests/test_codex_backend_mount.py -v

# From codex-control-centre/: focused 01A suites
..\.venv\Scripts\python.exe -m pytest `
  tests/test_supervisor_identity.py `
  tests/test_supervisor_bootstrap_claim.py `
  tests/test_supervisor_idempotency.py `
  tests/test_supervisor_events.py `
  tests/test_migrations.py -v

# Existing P0 boundary regressions
..\.venv\Scripts\python.exe -m pytest tests/test_security.py tests/test_events.py -v

# Migration head and application import
..\.venv\Scripts\python.exe -m alembic heads
..\.venv\Scripts\python.exe -c "from backend.models.codex import Project; from backend.routers.v2_supervisor import router; print('ok')"

# From repository root: native application import and living docs
.\.venv\Scripts\python.exe -c "from app.main import app; print('ok')"
python scripts/verify_living_docs.py --path codex-control-centre/README.md
python scripts/verify_living_docs.py
python scripts/verify_zero_console_errors.py
```

Also require:

- explicit migration-matrix tests for every row in section 8;
- OpenAPI test proving the v0.1 mutation/action/permission bijection and absence
  of all unimplemented v2 mutation paths;
- `git diff --check` over the exact changed-file allowlist;
- changed-file comparison against section 3;
- no runtime `codex.db`, WAL/SHM, build, cache, worktree, media, or generated
  artifact outside the three approved documentation indexes;
- focused privacy-canary log/response/event tests;
- a fresh independent reviewer who did not implement the package;
- clean-checkout QA from the resulting commit; and
- only after every gate succeeds: explicit-path staging, descriptive commit,
  push to the approved branch, commit hash, push confirmation, test evidence,
  and Anti-Gravity completion log.

No success claim may rely only on imports, static checks, or ORM model creation.

## 16. Stop conditions

Stop and rebrief before coding further if:

1. the configured root or opaque ID source cannot be implemented without reading
   or modifying `.env` or accepting browser authority;
2. a migration sees an unknown/incompatible schema, multiple Alembic heads, or a
   real runtime database without a verified quiesced backup/adoption decision;
3. exact claim identity cannot be resolved without disclosing another tenant,
   user, path, or fingerprint;
4. `create_all()` removal breaks a required legacy startup path that cannot be
   represented truthfully as migration readiness;
5. implementation needs a path outside section 3;
6. a Mission, work package, brief, worker, thread, worktree, evidence, audit,
   cutover transition, SSE stream, frontend, or external integration appears
   necessary;
7. the implementation would emit a future registry `1.0` descriptor or add a
   placeholder route;
8. a raw path, database URL, SQL statement, exception, credential, prompt,
   customer field, SMS/booking/payment field, or auth material reaches a
   response, event, log, trace, test snapshot, or committed artifact; or
9. focused verification exposes a broader regression or inconsistent frozen
   contract.

## 17. Explicit exclusions and later work

Deferred, not partially scaffolded:

- Mission/programme, membership, work package, dependency, brief, memory, and
  checkpoint tables or endpoints;
- cutover transitions, `v2_read_only`, `v2_active`, rollback, stale-v1 mutation
  enforcement, activation evidence, and the 72-row registry `1.0`;
- thread/turn/approval/subagent ownership migration and run lineage;
- assignments, dispatch, workers, worktrees, writer leases, run events, SSE,
  approvals/interactions, diffs, tests, terminal/process views, and artifact
  content;
- evidence, independent audit, decisions, risks, Project Brain, Operations
  mutations, Intake, and support-ticket promotion;
- any frontend route, component, client, dependency, fixture, demo mode, or UI
  state;
- AG-UI, CopilotKit, Assistant UI, Open WebUI, Codex Bridge, cloud memory,
  telemetry vendor, or other optional adapter;
- merge, deployment, production database migration, real project claim, worker
  start, or deletion/decommission of v1 or the duplicate frontend.

## 18. Acceptance evidence

WP-UI-01A is accepted only when a fresh independent reviewer verifies, criterion
by criterion, that:

- the exact branch descends from `3aa3b33b`;
- the diff contains only section 3 paths;
- all migration matrix and rollback tests pass without opening real runtime data;
- production startup performs no schema DDL;
- v2 identity is server-derived and platform-owner-only;
- bootstrap/readiness/cutover/projects/claim match section 10 exactly;
- claim is tenant-safe, path-free, conditional, idempotent, durable, atomic, and
  restart-safe;
- one and only one immutable safe event exists per successful logical claim;
- cutover remains `v1_only`, project control plane remains `legacy`, and no
  future mutation or descriptor is exposed;
- living documentation and generated indexes are current;
- all focused, P0, import, privacy, migration, zero-console/network, and
  clean-checkout gates pass; and
- commit/push evidence and known limitations are reported truthfully.

