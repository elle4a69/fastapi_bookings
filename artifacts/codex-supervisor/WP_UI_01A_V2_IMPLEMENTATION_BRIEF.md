# WP-UI-01A-v6 — Durable Supervisor Read Foundation and Configured-Project Claim

**Status:** Signed implementation brief version 6; authoritative for WP-UI-01A

**Implementation authorization:** exact 35-path allowlist; no stage, commit, push,
merge, deployment, or v2 activation before independent acceptance.

**Required base:** `c18f20ef46efa2740528c1b1f5040c3044d5c01e`

**Root application Alembic head at base:** `d4b8f2a6c901`

**Codex Control Centre Alembic head at base:** `001`

**Implementation branch:** `codex/codex-supervisor-wp-ui-01a-v2`

**Anti-Gravity task:** `ccc_wp_ui_01a_v2`

**Dependencies:** `ccc_wp_ui_00`, `ccc_wp_sec_01`

**Execution mode:** manual orchestration; no worker auto-execution

**Supersedes v5:** SHA-256
`BD42696C35404ED125959B2AB7EDF81AF0BB8C2D2E81A527A83D109142B11FE4`.

**Supersedes v4:** SHA-256
`BCAF87C9F3B4E6D06FB47B14A4A74412F37C5E15614E76DC1B83D2DA87F2FD90`.

**Supersedes v3:** SHA-256
`8F9231D8514B938102F3B9C1C1BFFCF316F27DA47BDB95E733C90CACF46D3746`.

**Supersedes v2:** SHA-256
`C387887A0738498C55C468191D973EB0E6428473682B29BE00EF46CEBC00A1F2`.

**Supersedes rejected v1:** the rejected WP-UI-01A brief at SHA-256
`A18B340833E856926C947A74165FB09E5A66A325DD00D97CF91790979EC493D4`.
The rejected brief remains unchanged as historical evidence.

## 1. Outcome

WP-UI-01A-v6 is the smallest safe, real backend slice for the future supervisor
UI. It must:

1. reconcile the nested Codex Control Centre (CCC) Alembic ledger, including
   `workspace_boundaries` and `system_settings`;
2. remove production/runtime reliance on `Base.metadata.create_all()` and report
   truthful migration readiness without startup DDL;
3. derive a server-owned `ActorScope` only after FastAPI Bookings has resolved an
   active persisted platform owner through the already accepted
   `require_platform_owner` dependency;
4. bind one deployment-configured FastAPI Bookings root to one opaque configured
   project identity without accepting or disclosing a browser-supplied path;
5. expose four read-only v2 resources and one transactional configured-project
   claim action;
6. give claim a durable, completion-based 24-hour idempotency window, optimistic
   concurrency, exact terminal replay, and an append-only event;
7. keep the control plane fixed at `v1_only` with no v2 activation, no mission,
   work-package, brief, run, assignment, approval, or evidence mutation surface.

This is not a scaffold. Every implemented route must use real configuration,
real migrated persistence, native authentication, tenant/user scope, real
transactions, and real tests. No placeholder route may be registered.

## 2. Binding boundaries

### 2.1 Accepted security dependency

WP-SEC-01 is implemented at the required base. Its persisted
`User.is_platform_owner`, offline provisioning command, and
`app.api.deps.require_platform_owner` are authoritative. WP-UI-01A-v6 must not
modify any WP-SEC file or reproduce, weaken, infer, or configure an alternative
authority mechanism.

For every v2 endpoint, dependency order is binding:

1. authenticate against the FastAPI Bookings application database;
2. resolve the active user through `require_platform_owner`;
3. create an immutable `ActorScope` from server-derived positive `tenant_id` and
   `user_id` plus the invariant `is_platform_owner=True`;
4. only then open, inspect, or query the CCC database.

`role`, tenant role `owner`, `is_superuser`, request fields, headers, environment
allowlists, CCC rows, and standalone shared secrets are not platform authority.
The v2 router is mounted only by FastAPI Bookings under
`/api/admin/codex/v2`. CCC stores tenant and user IDs as scalar external
references; cross-database foreign keys are forbidden.

WP-SEC's `LOCAL_AUTH_BYPASS` no-owner behavior remains authoritative: when bypass
is enabled but no active persisted platform owner exists, native authentication
fails with `503`. The v2 prefix adapter maps that condition to a safe
`503 authentication_unavailable` envelope. It must not convert it to 401/403,
select an ordinary tenant owner, or modify WP-SEC code.

### 2.2 Fixed cutover posture

The only legal persisted and returned cutover mode is `v1_only`, version `1`.
The configured project remains `control_plane='legacy'` after claim. There is no
`v2_read_only`, no `v2_active`, no transition endpoint, and no transition helper.
Claim records supervisor scope; it does not transfer mutation authority.

### 2.3 Implemented v0.1 action subset

`action_registry_version` is exactly `0.1`. The only mutation action is
`claim_project`. Exactly one OpenAPI operation has `x-operator-action: true`,
and it has action code `claim_project`. Every emitted allowed action descriptor
maps to that operation and every such operation maps back to exactly one
descriptor. The full 72-row v1.0 action registry and activation conformance are
deferred; no unimplemented action is emitted and no placeholder endpoint exists.

## 3. Exact future implementation allowlist

Implementation may change only these 35 repository paths:

1. `artifacts/codex-supervisor/WP_UI_01A_IMPLEMENTATION_BRIEF.md` — rejected
   historical artifact, reintroduced byte-for-byte; no implementation edits.
2. `artifacts/codex-supervisor/WP_UI_01A_V2_IMPLEMENTATION_BRIEF.md` — this
   authoritative brief.
3. `docs/architecture/ADR_CODEX_SUPERVISOR_V2_FACADE.md` — clarify the 01A
   subset/activation split and superseding security dependency.
4. `docs/architecture/README.md`.
5. `docs/README.md`.
6. `codex-control-centre/README.md`.
7. `docs/AGENT_BOOT_SNAPSHOT.md` — generated only by the documented generator.
8. `docs/MODULE_INDEX.md` — generated only by the documented generator.
9. `docs/module_manifest.json` — generated only by the documented generator.
10. `codex-control-centre/backend/config.py`.
11. `codex-control-centre/backend/database.py`.
12. `codex-control-centre/backend/main.py`.
13. `codex-control-centre/backend/models/codex.py`.
14. `codex-control-centre/backend/schemas/v2_supervisor.py` — new.
15. `codex-control-centre/backend/middleware/v2_errors.py` — new.
16. `codex-control-centre/backend/routers/v2_supervisor.py` — new.
17. `codex-control-centre/backend/routers/projects.py`.
18. `codex-control-centre/backend/services/actor_scope.py` — new.
19. `codex-control-centre/backend/services/migration_readiness_service.py` — new.
20. `codex-control-centre/backend/services/legacy_adoption_service.py` — new.
21. `codex-control-centre/backend/services/cutover_service.py` — new, read-only.
22. `codex-control-centre/backend/services/idempotency_service.py` — new.
23. `codex-control-centre/backend/services/supervisor_repository.py` — new.
24. `codex-control-centre/backend/services/supervisor_event_service.py` — new.
25. `codex-control-centre/alembic/versions/002_legacy_ledger_and_project_scope.py`
   — new.
26. `codex-control-centre/alembic/versions/003_claim_idempotency_and_audit_events.py`
   — new.
27. `app/main.py`.
28. `codex-control-centre/tests/conftest.py` — existing accepted isolation code;
   modify only if a reproduced test proves a gap. Stop and rebrief before changing
   its isolation contract merely for convenience.
29. `tests/conftest.py` — narrow root-suite CCC migration bootstrap defined in
   section 11; no other fixture or isolation behavior change.
30. `codex-control-centre/tests/test_supervisor_identity.py` — new.
31. `codex-control-centre/tests/test_supervisor_bootstrap_claim.py` — new.
32. `codex-control-centre/tests/test_supervisor_idempotency.py` — new.
33. `codex-control-centre/tests/test_supervisor_events.py` — new.
34. `codex-control-centre/tests/test_migrations.py`.
35. `tests/test_codex_backend_mount.py`.

No WP-SEC implementation, root application migration, frontend,
legacy source, environment file, runtime database, generated build output, or
unlisted path is in scope. If another path is required, stop and rebrief before
editing it.

## 4. Server configuration contract

`codex-control-centre/backend/config.py` owns four deployment values:

| Setting | Contract |
|---|---|
| `CODEX_SUPERVISOR_CONFIGURED_PROJECT_ID` | Required opaque public ID, `prj_` prefix plus 16–64 URL-safe opaque characters; never a database primary key or path encoding. |
| `CODEX_SUPERVISOR_CONFIGURED_PROJECT_ROOT` | Required absolute FastAPI Bookings root; server-side only, never logged, serialized, placed in an error, or accepted from a request. |
| `CODEX_SUPERVISOR_CONFIGURED_PROJECT_NAME` | Required safe display name, 1–120 printable characters, no control characters. |
| `CODEX_SUPERVISOR_CONFIGURED_DEFAULT_BRANCH` | Required safe Git branch/ref, 1–255 characters, validated with Git check-ref-format-equivalent rules; no default to `main`. |

Missing values produce project-resolution `unconfigured`. Malformed IDs, names,
branches, relative roots, symlink/reparse ambiguity, or conflicting same-scope
identity produce project-resolution `quarantined`; an inaccessible or inconclusive
root produces project-resolution `dependency_unavailable`, as section 6 defines.
Values are loaded by the server;
the browser cannot override them.

The physical root identity is persisted as a non-public SHA-256 over a versioned,
canonical tuple containing the normalized resolved absolute path and positive
filesystem `st_dev`/`st_ino` identity. Missing, zero, inaccessible, or otherwise
inconclusive identity fails closed. The configured identity fingerprint is a
server-side SHA-256 over a versioned, canonical encoding of opaque ID, this root
identity digest, display name, and default branch. Neither digest nor canonical
root is logged, emitted in an event, or returned.

## 5. Persistence and migration contract

The root application and CCC have distinct Alembic ledgers. WP-UI-01A-v6 adds no
root migration after `d4b8f2a6c901`. CCC alone advances from `001` to `003` via
two separate, linear revisions.

### 5.1 CCC revision `002_legacy_ledger_and_project_scope`

Revision `002` must:

- create the model-declared but ledger-missing `workspace_boundaries` and
  `system_settings` tables with constraints/indexes matching current models;
- add to `projects`:
  - `public_id` nullable during migration, unique when non-null;
  - `tenant_id` and `owner_user_id`, nullable until claim and positive when set;
  - `scope_state` with only `unclaimed`, `claimed`, `quarantined`;
  - `control_plane` constrained to `legacy` in this slice;
  - `configured_fingerprint` nullable, unique when non-null;
  - `root_identity_digest` non-null, indexed non-uniquely, and constrained to a
    lowercase 64-character hexadecimal SHA-256;
  - `claimed_at` nullable UTC timestamp;
  - integer `version`, non-null, default `0`, nonnegative;
- preserve existing internal primary keys and `repo_path` only as server-side
  implementation data;
- add a durable schema-adoption metadata table recording versioned structural
  checks and adoption time, never paths or secrets;
- atomically backfill `root_identity_digest` for every existing revision-001
  project and abort the migration without partial adoption when any path identity
  cannot be proven;
- install database-level claimed-row insert and update guards. An insert or
  transition to `claimed` is accepted only when `public_id`, `name`, `repo_path`,
  `default_branch`, `configured_fingerprint`, `root_identity_digest`, positive `tenant_id`, positive
  `owner_user_id`, `claimed_at`, `control_plane='legacy'`, and `version=1` are all
  present and internally consistent. Once claimed, neither ORM, v1 route, nor
  direct SQL may change any of those fields, `scope_state`, or their nullability.
  SQLite triggers must compare every protected value null-safely and abort the
  write; equivalent constraints are required for any supported database backend.

The existing v1 `POST /projects` route must reject attempts to mutate a claimed
row before commit with `409 supervisor_owned`; it may not rename, repoint, change
the configured default branch, replace the public identity/fingerprint, alter
ownership, claimed time, control plane, state or version, or clear scope. The DB
guard is defense in depth and must also be tested through direct SQL for every
protected field and invalid claimed insert. Reads may continue. Unclaimed legacy
behavior changes only as necessary for exact adoption.

### 5.2 CCC revision `003_claim_idempotency_and_audit_events`

Revision `003` must create:

1. `control_plane_cutover_state`: a singleton row with mode constrained to
   `v1_only`, version fixed at `1`, and timestamps. No writable transition field.
2. `idempotency_records` with:
   - unique `(tenant_id, user_id, action_code, idempotency_key)`;
   - opaque `request_id`, canonical `request_fingerprint`, status limited to
     `in_progress`, `succeeded`, `failed`;
   - `created_at`, nullable `completed_at`, nullable retention `expires_at`;
   - bounded execution lease fields: nullable opaque `lease_owner` exactly
     `exe_` plus 32 lowercase hexadecimal characters; nullable 64-character
     lowercase SHA-256 `lease_token_hash` derived from a 32-byte random token;
     nullable UTC `lease_acquired_at`; and nullable UTC `lease_expires_at`; the
     raw token is never persisted, logged, returned, or included in an event;
   - nullable terminal `response_status`, exact serialized response bytes, and
     an allowlisted replay-header record containing `Content-Type`, `ETag`,
     `Cache-Control`, and `X-Request-ID` only;
   - check constraints: in-progress rows have no completion/retention-expiry or
     terminal response and have either a complete valid lease tuple or a reclaimable
     expired lease tuple; terminal rows clear owner/token authority while retaining
     the last acquired/expires timestamps as bounded structural evidence, have all terminal fields, and
     `expires_at = completed_at + 24 hours` according to application-normalized
     UTC values.
3. `supervisor_events`, append-only, with internal opaque event key, configured
   project public ID, actor tenant/user scalar references, `claim_project`,
   outcome, project version, request ID, idempotency key hash, bounded structural
   payload, payload SHA-256, schema version `0.1`, previous digest, integrity
   digest, and UTC occurrence time. Database triggers reject update and delete.

The event payload may contain safe reason codes and before/after scope state. It
must not contain a path, raw idempotency key, database URL, prompt, response,
credential, email, tenant/user identity text, or internal database ID.

### 5.3 Downgrade and rollback

`003 -> 002` removes only 003-owned tables/triggers after an operator backup and
explicit acknowledgement that claim replay/event evidence will be lost.
`002 -> 001` must refuse while any project is claimed or quarantined unless an
approved backup-and-restore recovery plan is invoked. Downgrade never silently
unclaims or strips ownership. Re-upgrade `001 -> 002 -> 003` must be deterministic.
Production rollback is code rollback plus database backup restoration; migration
downgrade is not a casual runtime recovery mechanism.

## 6. Migration readiness and production startup

Remove the CCC production lifespan call to `Base.metadata.create_all()`.
`database.py` may retain metadata helpers only for explicitly isolated test tooling
that does not define production truth; the live FastAPI path performs no schema
DDL or stamping.

Startup and v2 readiness use read-only inspection of the CCC Alembic ledger and
the minimum structural invariants necessary to classify state. They must not query
domain tables before the ledger and required schema are current. Current means
CCC head `003`, not root head `d4b8f2a6c901`.

An unversioned database is never stamped by startup or an HTTP request. The future
implementation may expose an offline-only `python -m
backend.services.legacy_adoption_service` operator mode from the allowlisted
service module. It reads its database URL only from an environment variable,
defaults to validation/dry-run, requires `--apply` plus a typed non-secret
confirmation, and stamps `001` only after an exact allowlisted legacy schema
fingerprint succeeds. It prints only safe counts/reason codes/revision tokens.
Revision 002 then conditionally adopts already-present
`workspace_boundaries`/`system_settings` only when their complete structure
matches, or creates them when absent. Any mismatch, unknown partial state, or
concurrent schema change aborts without a stamp. This is migration-ledger adoption,
not configured-project claim, and it performs no `create_all`.

Readiness has two separate objects and must never collapse them into one state:

1. `infrastructure` describes only CCC connectivity, ledger, and schema:
   - `ready`: database inspection succeeded, revision is exactly `003`, and the
     required 003 structure is proven;
   - `migration_required`: inspection succeeded but the database is unversioned,
     behind, ahead, unknown, or structurally incompatible with revision `003`;
   - `dependency_unavailable`: the database is unopenable, corrupt, or remains
     locked after the bounded timeout, so classification cannot complete.
2. `project_resolution` is evaluated only when infrastructure is `ready`:
   - `unconfigured`: a required deployment value is absent;
   - `claim_required`: configuration and exact-root checks are safe and no
     same-scope configured claim exists;
   - `claimed`: the same-scope configured row matches every configured invariant;
   - `quarantined`: a same-scope configured row, same-scope exact-root candidate,
     server configuration, or invariant is conflicting or ambiguous;
   - `dependency_unavailable`: configured-root identity cannot be inspected
     conclusively.

Cross-scope rows/candidates are filtered as hidden before project resolution.
They do not produce `quarantined`, do not change reason codes or counts, and are
indistinguishable from absence on read endpoints. A mutation targeting a hidden
resource returns `404 resource_not_found`. Quarantine is a read-time safe
classification in this slice: bootstrap, readiness, and projects never persist or
repair `scope_state`, and a failed claim does not write a quarantine marker.
Existing persisted quarantine may be classified, but creating/remediating it is
deferred to an explicit later operator workflow.

Fault precedence is exact: native authentication/active platform authority first;
then request syntax/header/body validation for claim; then infrastructure
inspection; then migration state; then server configuration; then same-scope
project resolution; finally operation preconditions. A higher-precedence failure
prevents all lower-precedence queries. No project-domain table is queried unless
infrastructure is `ready`.

`GET /bootstrap` and `GET /operations/readiness` return `200` when infrastructure
is safely `ready` or `migration_required`, and include project resolution only
when infrastructure is ready. They return `503 dependency_unavailable` when
infrastructure cannot be classified. Project-root dependency failure is represented
as a `200` readiness snapshot with infrastructure `ready` and project resolution
`dependency_unavailable`; project/claim endpoints return `503
dependency_unavailable`. No endpoint substitutes fake defaults.

## 7. Exact-root legacy adoption and configured-project claim

Path identity is server-side. Normalize Windows case/separators and resolve the
configured root without accepting aliases. If both paths exist, require
`os.path.samefile` (or a platform-equivalent file identity) in addition to
canonical comparison. A symlink/reparse-point mismatch, inaccessible path, or
inconclusive identity check fails closed.

Resolution rules inside the post-reservation claim transaction:

1. Exclude cross-scope rows before candidate classification. Do not count, describe,
   quarantine, adopt, or mutate them. A mutation collision with a hidden configured
   identity returns only `404 resource_not_found`. Candidate discovery is bounded
   and index-backed by configured public ID, configured fingerprint, or physical-root
   digest; it never pages unrelated hidden rows. Any root-digest candidate receives
   a final canonical/same-file verification.
2. A same-scope row already carrying the configured `public_id` must match exact
   root, configured fingerprint, configured name, and configured safe default
   branch. Any mismatch is classified `quarantined`; it is never repaired from the
   request and the classification itself performs no write.
3. If no same-scope configured-ID row exists, locate only visible unclaimed legacy
   rows whose stored root is provably the exact configured root. Exactly one may be
   adopted.
4. Zero visible exact-root candidates permits creation and immediate claim of one
   configured row.
5. More than one same-scope exact-root candidate, a same-scope competing configured
   fingerprint/public ID, a visible claimed candidate, or uncertain path identity
   is classified `quarantined` and aborts without writing quarantine state.
6. Names, branch guesses, task text, prompts, threads, and working-directory
   proximity are never ownership evidence.

Claim atomically sets the server-derived public ID/fingerprint/name/default branch,
tenant/user scope, `claimed`, `legacy`, `claimed_at`, and version `1`; writes one
terminal idempotency result and exactly one append-only `claim_project` event in
the second transaction; and commits that transaction once. The earlier reservation
remains durable if this transaction rolls back, but no project or event write may
escape the rollback.

An already claimed configured row is not silently treated as a new success. Only
the original terminal idempotency record may replay success. A different key gets
`409 invalid_state`, even for the same actor.

## 8. Request IDs, envelopes, and disclosure

For every request under `/api/admin/codex/v2`, generate a server-side opaque,
nonzero request ID of form `req_<secure-random-or-UUID>`. Do not trust or echo an
inbound request ID. For a first execution, response `X-Request-ID` and
`meta.request_id` are identical. A terminal idempotency replay must return the
original operation request ID in both places to preserve the exact body; any
new replay-attempt correlation is internal and never replaces the stored response.

All v2 success bodies use:

```json
{"data": {}, "meta": {"request_id": "req_...", "schema_version": "0.1"}}
```

All v2 errors use:

```json
{"error": {"code": "safe_code", "message": "Safe bounded message", "details": {}}, "meta": {"request_id": "req_...", "schema_version": "0.1"}}
```

`v2_errors.py` handles validation errors, HTTP errors, and unexpected failures only
for this prefix. It must not serialize `str(exc)` or leak SQL, schema/table names,
paths, fingerprints, internal IDs, tracebacks, database URLs, configuration, or
identities. Prefix-specific handling must not change legacy v1 error contracts.
Every v2 response uses `Cache-Control: no-store`.

Only the deployment-configured opaque project ID and opaque request ID are public.
No new v2 response, OpenAPI example, supervisor event, or application log exposes
`repo_path`, canonical path, fingerprint, internal project/event/idempotency primary
keys, tenant/user IDs, or hidden-record counts. The existing legacy v1 project's
`repo_path` response is not expanded or copied into v2; removing it from the v1
contract is a separately reviewed later package, not an unannounced 01A change.

## 9. Exact HTTP contract — five endpoints only

All five endpoints require native authentication and active persisted platform-owner
authority. Missing/invalid authentication is `401 authentication_required`;
authenticated non-platform owners, inactive users, tenant owners, and dynamic
superusers are `403 forbidden`. Authorization happens before CCC access.
WP-SEC bypass-without-owner is `503 authentication_unavailable` as specified in
section 2.1.

The four GET operations each declare `x-operator-action: false` in OpenAPI and
have no action code. Claim alone declares `x-operator-action: true`. Every v2
response has `Content-Type: application/json`, `Cache-Control: no-store`, and a
nonzero `X-Request-ID` matching the body. Errors and readiness snapshots have no
ETag. Successful bootstrap, cutover, projects, and claim responses have the ETags
specified below. A `202` has `Retry-After: 1` and no ETag. Only terminal replay
adds `Idempotency-Replayed: true`; that header is absent otherwise.

All digest ETags use this encoding: construct the explicitly documented safe
`data` object only; encode JSON as UTF-8 with lexicographically sorted keys, no
insignificant whitespace, JSON lowercase booleans/null, and no floats; hash those
exact bytes with SHA-256; render the 64 lowercase hexadecimal characters inside
the quoted endpoint prefix. Arrays retain documented order; `reason_codes` are
deduplicated and sorted lexicographically before encoding. Request IDs and other
`meta` fields are excluded.

### 9.1 `GET /api/admin/codex/v2/bootstrap`

Returns `200` for every safely classified infrastructure state and project state;
returns `503 dependency_unavailable` when infrastructure inspection itself fails.
Its ETag is `"bootstrap-v1-<digest>"`; conditional `304` is not implemented.
It queries connection/ledger/structure first. Only when infrastructure is ready
does it read the cutover singleton, validate server configuration, and perform
bounded same-scope project resolution; it issues no other domain query.
The exact shape is:

```json
{
  "data": {
    "capabilities": {"can_view_supervisor": true, "can_claim_project": false},
    "action_registry_version": "0.1",
    "infrastructure": {
      "state": "ready|migration_required",
      "current_revision": "001|002|003|unknown|null",
      "expected_revision": "003",
      "reason_codes": []
    },
    "project_resolution": null,
    "cutover": null,
    "cutover_absent_reason_code": "migration_required",
    "project": null
  },
  "meta": {"request_id": "req_...", "schema_version": "0.1"}
}
```

Null combinations are binding:

| Infrastructure | Project resolution | Cutover | Project | Can claim |
|---|---|---|---|---|
| `migration_required` | `null` | `null`; absent reason `migration_required` | `null` | false |
| `ready` | `unconfigured` | fixed cutover; absent reason `null` | `null` | false |
| `ready` | `dependency_unavailable` | fixed cutover; absent reason `null` | `null` | false |
| `ready` | `quarantined` | fixed cutover; absent reason `null` | `null` | false |
| `ready` | `claim_required` | fixed cutover; absent reason `null` | configured safe summary at version 0 with descriptor | true |
| `ready` | `claimed` | fixed cutover; absent reason `null` | configured safe summary at version 1, descriptor `null` | false |

When non-null, `project_resolution` is exactly
`{"state":"unconfigured|claim_required|claimed|quarantined|dependency_unavailable","reason_codes":[]}`.
A project summary contains only `project_id`, `display_name`, `default_branch`,
`state`, `version`, `control_plane`, and `claim_action`. Hidden rows do not alter
the outward absence/claim-required representation. The claim descriptor is exactly:

```json
{
  "registry_version": "0.1",
  "action": "claim_project",
  "allowed": true,
  "reason_code": null,
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

### 9.2 `GET /api/admin/codex/v2/operations/readiness`

Returns `200` whenever infrastructure inspection is safe, with no ETag. It first
queries only connection/ledger/structural metadata. If and only if infrastructure
is `ready`, it validates server configuration and performs bounded same-scope
project resolution. It returns no project summary or candidate count:

```json
{
  "data": {
    "infrastructure": {
      "state": "ready|migration_required",
      "current_revision": "001|002|003|unknown|null",
      "expected_revision": "003",
      "reason_codes": []
    },
    "project_resolution": null
  },
  "meta": {"request_id": "req_...", "schema_version": "0.1"}
}
```

`project_resolution` is null exactly when infrastructure is not ready; otherwise
it is the bounded object defined in section 9.1. Failed infrastructure inspection
returns `503 dependency_unavailable` rather than a synthetic snapshot.
`current_revision` is one of the JSON strings `001`, `002`, `003`, `unknown`, or
JSON null. Infrastructure reason codes are limited to `revision_missing`,
`revision_behind`, `revision_ahead`, and `schema_mismatch`. Project reason codes
are limited to `configured_value_missing`, `configured_value_invalid`,
`same_scope_identity_conflict`, `same_scope_candidate_ambiguous`,
`claimed_invariant_mismatch`, `root_identity_ambiguous`, and
`configured_root_unavailable`. Codes are sorted, contain no dynamic values, and an
empty array is used when none applies.

### 9.3 `GET /api/admin/codex/v2/operations/cutover-mode`

Requires CCC migration/schema readiness, but does not require configured-project
readiness. Missing project configuration therefore does not hide the fixed safety
posture. It queries only infrastructure metadata and, when ready, the singleton
cutover row; it never queries projects. A behind/unknown ledger returns `503 database_migration_required`; failed
inspection returns `503 dependency_unavailable`. Returns `200`,
`ETag: "cutover-1"`, and:

```json
{
  "data": {
    "mode": "v1_only",
    "version": 1,
    "mutation_authority": {
      "legacy_owned": "v1",
      "supervisor_owned": "none",
      "allowed_drain_actions": []
    },
    "allowed_transitions": [],
    "transition_absent_reason_code": "deferred_by_wp_ui_01b"
  },
  "meta": {"request_id": "req_...", "schema_version": "0.1", "resource_version": 1}
}
```

No PUT/PATCH/POST/DELETE operation is registered on this path.

### 9.4 `GET /api/admin/codex/v2/projects`

Queries infrastructure first, then configuration and same-scope resolution only
when migration-ready. On success it returns `200`, ETag
`"projects-v1-<digest>"`, and exactly:

```json
{
  "data": {
    "projects": [
      {
        "project_id": "prj_opaque",
        "display_name": "FastAPI Bookings",
        "default_branch": "configured-safe-branch",
        "state": "claim_required|ready",
        "version": 0,
        "control_plane": "legacy",
        "claim_action": null
      }
    ]
  },
  "meta": {"request_id": "req_...", "schema_version": "0.1"}
}
```

The array contains zero or one same-scope summary; a claim-required summary has
version 0 and the exact descriptor from section 9.1, while a claimed summary has
state `ready`, version 1, and null descriptor. Hidden/cross-scope rows are omitted
without counts and cannot affect ETag material. Missing deployment configuration
is `503 supervisor_unconfigured`; behind/unknown ledger is `503
database_migration_required`; failed database/root inspection is `503
dependency_unavailable`; and a same-scope configuration/invariant conflict is
`409 supervisor_quarantined`. No conditional `304` is implemented.

### 9.5 `POST /api/admin/codex/v2/projects/{project_id}/claim`

This is the only v0.1 operator action. OpenAPI must include:

```yaml
x-operator-action: true
x-action-code: claim_project
x-action-registry-version: "0.1"
x-backend-permission: project.claim
```

`project_id` must exactly equal the configured opaque ID; all other IDs return
`404 resource_not_found`. Required headers are `Idempotency-Key: <UUIDv4>` and
`If-Match: "project-<current_version>"`. For an absent/unclaimed configured
resource the current version and required ETag are `0` / `"project-0"`.

The body has `extra='forbid'` and is exactly:

```json
{
  "action": "claim_project",
  "registry_version": "0.1",
  "expected_version": 0,
  "confirmation": true
}
```

It accepts no tenant/user ID, role, path, name, branch, fingerprint, scope, or
control-plane field. Header/body version mismatch is
`400 precondition_mismatch`; malformed typed input is `422 validation_failed`;
missing required precondition headers is `428 precondition_required`.

First success is `200`, with `ETag: "project-1"` and:

```json
{
  "data": {
    "project": {
      "project_id": "prj_opaque",
      "display_name": "FastAPI Bookings",
      "default_branch": "configured-safe-branch",
      "state": "ready",
      "version": 1,
      "control_plane": "legacy"
    }
  },
  "meta": {
    "request_id": "req_...",
    "schema_version": "0.1",
    "resource_version": 1,
    "idempotency_state": "succeeded"
  }
}
```

The append-only event ID is not returned. A terminal replay returns the original
status, byte-for-byte response body, original `ETag`, `Content-Type`,
`Cache-Control`, and `X-Request-ID`, plus `Idempotency-Replayed: true`. The replay
body remains unchanged, including `idempotency_state: "succeeded"`; it does not
claim to be a newly generated response.

An existing matching record with an unexpired execution lease returns `202`, the
original request ID, `Retry-After: 1`, no ETag/project result, and exactly:

```json
{
  "data": {
    "operation": {
      "action": "claim_project",
      "state": "in_progress",
      "retry_after_seconds": 1
    }
  },
  "meta": {
    "request_id": "req_...",
    "schema_version": "0.1",
    "idempotency_state": "in_progress"
  }
}
```

In-progress records have no retention expiry and are never purged. Their bounded
execution lease may expire and be reclaimed as section 10 defines. The terminal
24-hour replay window begins at `completed_at`, not `created_at`. Expired terminal
keys may be atomically replaced only after expiry.

Additional exact failures are:

| HTTP/code | Condition |
|---|---|
| `404 resource_not_found` | Guessed, hidden, cross-scope, or non-configured public ID. |
| `409 idempotency_conflict` | Same scoped key, different canonical request fingerprint. |
| `409 invalid_state` | Already claimed with another key, quarantined, or not claimable. |
| `409 claim_guard_failed` | Exact-root/fingerprint/candidate guard failed safely. |
| `409 supervisor_owned` | Legacy v1 attempts to mutate a claimed row. |
| `409 supervisor_quarantined` | A safely detected configured identity or invariant conflict requires operator recovery. |
| `412 revision_conflict` | Durable version differs from `If-Match`/body. |
| `503 supervisor_unconfigured` | One or more required deployment configuration values are absent. |
| `503 database_migration_required` | CCC revision/schema is not ready. |
| `503 dependency_unavailable` | Database or configured-root validation cannot complete safely. |

Unexpected failure is safe `500 internal_error`, never a raw exception.

The status/header matrix is binding (`base` means JSON content type, `no-store`,
and matching nonzero request ID header/body):

| Endpoint/outcome | Status | Additional headers |
|---|---:|---|
| Any endpoint, missing/invalid auth | 401 | base only |
| Any endpoint, authenticated but not active persisted platform owner | 403 | base only |
| Any endpoint, WP-SEC bypass has no persisted owner | 503 | base only; `authentication_unavailable` |
| Bootstrap, safely classified | 200 | base + `ETag: "bootstrap-v1-<digest>"` |
| Readiness, safely classified | 200 | base only |
| Cutover, infrastructure ready | 200 | base + `ETag: "cutover-1"` |
| Projects, project resolution usable | 200 | base + `ETag: "projects-v1-<digest>"` |
| Claim, first terminal success | 200 | base + `ETag: "project-1"` |
| Claim, matching active lease | 202 | base + `Retry-After: 1` |
| Claim, terminal success or failed replay | original | original allowlisted terminal headers + `Idempotency-Replayed: true` |
| Any safe 4xx/5xx not a terminal replay | specified status | base only |

Validation/auth failures that occur before reservation use the normal safe error
envelope and are not replayable. A deterministic failed result after reservation
uses the same error envelope, is stored byte-for-byte with its canonical status and
allowlisted headers, and replays exactly with only the replay header added.

## 10. Idempotency, transaction, and concurrency algorithm

The canonical fingerprint object contains method, route template, the syntactically
valid opaque route project ID, action, registry version, expected version, confirmation,
actor tenant/user numeric scope, and schema version. Encode it by the canonical
JSON rules in section 9 and store its SHA-256. It contains no filesystem path or
volatile header. The raw idempotency key is never logged or placed in an event;
events use its hash.

Authentication, media type, JSON parsing, required-header presence, UUID syntax,
body schema, action, registry version, confirmation type, and header/body version
agreement occur before reservation and are never stored as idempotency outcomes.
Infrastructure inspection also precedes reservation because an absent/unready 003
table cannot safely reserve; `authentication_unavailable`,
`database_migration_required`, and a database-level `dependency_unavailable` are
therefore not stored.

The first decision is a bounded read-only lookup; it does not set a writer busy
timeout, upgrade a transaction, or acquire the SQLite writer lock. Use a read-only
connection/deferred transaction with a one-second application deadline and close
that read transaction before any write attempt. If the lookup cannot complete
within the deadline, return safe `503 dependency_unavailable` without attempting a
writer lock or creating a reservation. Only the reservation upgrade/write
path and the claim transaction set `PRAGMA busy_timeout=5000` and use
`BEGIN IMMEDIATE`. Actual mutations retain the fixed lock order
`idempotency_records -> projects -> supervisor_events -> idempotency_records`.
The implementation uses two write transactions, preceded when applicable by the
read-only decision:

### 10.1 Bounded read decision and short committed reservation transaction

1. Perform the bounded deferred lookup by scoped key and end the read transaction.
   A same-fingerprint in-progress row with a current lease returns the exact `202`
   immediately from readable state. A same-fingerprint terminal row with current
   retention returns exact replay. A non-expired row with a different fingerprint,
   and any in-progress row with a different fingerprint even after lease expiry,
   returns `409 idempotency_conflict`. None of these paths takes a writer lock or
   waits behind the five-second writer busy timeout.
2. Only an absent row, a same-fingerprint in-progress row with an expired lease,
   or a terminal row with expired retention leaves the read path and attempts the
   upgrade/write path. Generate the needed request ID/lease token, close the read,
   open the write connection, set its five-second busy timeout, and begin immediate.
3. Re-read the scoped row under the writer lock before mutation. A racer may have
   changed it: current same-fingerprint in-progress returns 202 after rollback;
   current same-fingerprint terminal replays after rollback; conflicting current
   fingerprint returns 409 after rollback. These are race fallbacks, not the normal
   readable-state path.
4. If still absent, insert and immediately commit `in_progress` with a fixed
   30-second lease: bounded internal owner, token hash, `lease_acquired_at`, and
   `lease_expires_at=acquired_at+30s`. The reservation transaction performs no
   project/event read or side effect.
5. If still same-fingerprint in-progress and lease-expired, reclaim by one
   compare-and-swap over status, prior token hash, and prior expiry. Preserve the
   original request ID, replace lease owner/token hash/timestamps, and commit
   immediately. A CAS loser rolls back, performs a fresh bounded read, and returns
   202 or terminal replay.
6. If still terminal and retention-expired, atomically replace it as a fresh
   operation with a new request ID/fingerprint/lease and commit immediately.

The raw token exists only in the winning executor's memory. The owner is bounded
structural text, not a hostname/path/user identity. Reclaim is safe because the
old executor cannot enter or finalize transaction two unless its token hash still
matches; SQLite's immediate-write serialization resolves a still-running old
transaction before reclaim can commit.

### 10.2 Atomic claim/event/terminal transaction

1. Begin immediate within the 30-second lease and re-read the reservation. Abort
   unless status remains in-progress, token hash matches, and the lease is current.
2. Recheck configuration, same-scope visibility, exact-root identity, claimed-row
   invariants, and both resource-version preconditions in the documented order.
3. For success, create/adopt and claim the configured row, insert exactly one
   digest-chained event, serialize the canonical 200 body once, mark the reservation
   succeeded, clear lease owner/token authority while retaining lease timestamps, set `completed_at` and
   `expires_at=completed_at+24h`, then commit all three writes atomically.
4. For a deterministic safe post-reservation failure (`404 resource_not_found`,
   business `409`, `412 revision_conflict`, or `503 supervisor_unconfigured`),
   write no project/event change; serialize the safe error once; mark the
   reservation failed with its exact status/body/allowlisted headers, clear the
   lease owner/token authority while retaining lease timestamps, set
   completion/retention times, and commit. Retry replays the failed response
   byte-for-byte with the original request ID plus only
   `Idempotency-Replayed: true`.
5. For configured-root/database dependency loss after reservation, an unexpected
   exception, busy timeout, lost lease, or failed serialization, roll transaction
   two back completely. Return the safe transient 503/500 when possible. Leave the
   committed reservation in-progress; it returns 202 until lease expiry, after
   which one caller safely reclaims it. Never store a fabricated terminal result.

The second transaction must finish and terminalize before lease expiry; otherwise
it rolls back. If response delivery fails after a terminal commit, retry replays
the stored result. Failed results never create a project or event. Successful
results always create exactly one project transition and one event.

The identical-key outcome matrix is exact:

| Readable scoped state | Fingerprint | Read-path result | Writer path |
|---|---|---|---|
| absent | any valid | end read and attempt reservation | re-read, insert/CAS only if still eligible |
| in-progress, lease current | same | observable `202` with original request ID | none |
| in-progress, lease current | different | `409 idempotency_conflict` | none |
| in-progress, lease expired | same | end read and attempt reclaim | re-read, CAS only if still expired/unchanged |
| in-progress, lease expired | different | `409 idempotency_conflict` | none |
| terminal, retention current | same | exact success or failed replay | none |
| terminal, retention current | different | `409 idempotency_conflict` | none |
| terminal, retention expired | any valid | end read and attempt fresh replacement | re-read, replace only if still expired |

If the writer re-read observes a newly current same-fingerprint state, it rolls
back and returns 202/replay; a newly conflicting current fingerprint returns 409.
Thus writer contention is limited to genuine insert/reclaim/replacement races and
never contradicts the exact readable-state 202/replay/409 decisions.

For different idempotency keys racing to claim, immediate-write ordering and the
claimed-row trigger yield exactly one claim/event/success. Every loser is
terminalized as the deterministic safe conflict for its own key. No race creates
two events or leaves partial project state.

## 11. Required tests

All tests use isolated, process-unique, file-backed temporary SQLite databases and
real Alembic migrations. They must never open or alter the checkout/default
`codex.db`, `codex.db-wal`, or `codex.db-shm`. The accepted CCC conftest protection
is retained unless a proven gap requires rebriefing.

### 11.1 Root-suite nested migration bootstrap

The reproduced isolation gap is binding evidence: when the standalone root P0
tests are selected, pytest collects `tests/conftest.py` but not the sibling
`codex-control-centre/tests/conftest.py`. Removing production `create_all()` would
therefore leave the root suite's already-isolated CCC database unmigrated unless
the root test harness explicitly migrates it.

`tests/conftest.py` may receive only this narrow bootstrap change:

1. retain its existing process-unique temporary directory, root application DB,
   CCC DB, environment assignment, runtime-file sentinels, network guard, and
   cleanup behavior;
2. after assigning lowercase `database_url` to the unique temporary CCC SQLite
   file, but before importing `app.main` or any CCC backend module, construct an
   Alembic `Config` from the absolute
   `codex-control-centre/alembic.ini` path, set/verify the absolute nested
   `codex-control-centre/alembic` script location, and run `upgrade head`;
3. assert the temporary CCC database's Alembic revision is exactly `003` before
   allowing application/CCC imports. Fail collection/session setup safely if the
   migration or assertion fails; never fall back to metadata creation;
4. execute once per fresh root pytest process as an earliest conftest bootstrap
   (or an equivalently ordered session bootstrap that demonstrably precedes those
   imports), independent of test selection and test execution order;
5. never print the temporary database URL/path, and never inspect, create, alter,
   delete, or attach the checkout/runtime `codex.db`, `codex.db-wal`, or
   `codex.db-shm`.

This authorization does not permit a pytest branch in `app/main.py`, CCC
`backend/main.py`, or `backend/database.py`; production startup still performs no
DDL. It does not permit CCC `Base.metadata.create_all()` in the root harness. The
DDL is test-only and migration-led inside `tests/conftest.py`. The sibling CCC
migration suite retains exclusive control over its own disposable schema fixtures:
the root bootstrap must not be imported by, made autouse for, or otherwise alter
`codex-control-centre/tests/test_migrations.py` or its conftest.

### 11.2 Identity and security negatives

Prove auth precedes CCC access and that only an active persisted platform owner
can call all five endpoints. Cover unauthenticated, invalid token, ordinary user,
tenant `owner`, inactive platform owner, dynamic `is_superuser`, cross-tenant
project, guessed public ID, actor fields in body, and `LOCAL_AUTH_BYPASS` without a
persisted owner. Assert `401/403/404`, safe `503 authentication_unavailable`, and
zero path/internal-ID/error leakage. Prove cross-scope rows produce the same read
shape/ETag as absence, mutation 404, and no count/quarantine reason. Re-run WP-SEC
negatives for CCC, resident, and support-ticket admin routes.

### 11.3 Migration matrix

Prove separately:

1. empty CCC database upgrades `base -> 001 -> 002 -> 003` and matches metadata;
2. a real `001` database upgrades to `003`;
3. a runtime-created, unversioned legacy database is only adopted after exact
   structural validation and adoption metadata, then upgrades to `003`;
4. unversioned partial/unknown/incompatible schema is not stamped or mutated and
   reports infrastructure `migration_required`;
5. legacy databases with `workspace_boundaries`/`system_settings` absent and
   structurally matching-present both converge without data loss; mismatching
   present tables report infrastructure `migration_required`;
6. `003 -> 002 -> 001 -> 002 -> 003` works only under downgrade guards;
7. claimed rows block `002 -> 001`;
8. root head remains `d4b8f2a6c901` and CCC head becomes `003` independently;
9. startup makes no DDL and no call to `create_all`;
10. default runtime DB sidecar hashes/existence are unchanged.

### 11.4 Readiness, bootstrap, and adoption

Cover every infrastructure/project-resolution combination and null combination in
section 9, including unopenable, locked, corrupt, and uninspectable root cases.
Assert the exact fault precedence and query boundary: no project query before
migration readiness, readiness-only bounded resolution after it, and no fake
cutover. Cover zero/one/multiple same-scope exact-root candidates, 10,000-plus
unrelated hidden rows with invariant response data/ETags and bounded query count,
hidden cross-scope candidates, case-normalized same-file success, symlink/reparse mismatch,
inaccessible paths, wrong configured ID/fingerprint/name/branch, safe new-row
creation, no-write quarantine classification, and no path leakage.

### 11.5 Claim, v1 guard, events, and replay

Cover:

- first claim, post-restart persistence, exactly one event, hash-chain integrity,
  and event update/delete rejection;
- v1 route and direct SQL attempts to change each of `public_id`, `name`,
  `repo_path`, `default_branch`, `configured_fingerprint`, `root_identity_digest`, `tenant_id`,
  `owner_user_id`, `claimed_at`, `control_plane`, `scope_state`, and `version`, plus
  invalid direct-SQL claimed inserts and valid unclaimed-to-claimed transition;
- missing/malformed headers, body extra fields, stale ETag, action/version mismatch,
  false confirmation, wrong public ID, and non-ready database;
- a deterministic barrier after reservation commit proving a concurrent identical
  key observes the exact 202 response while the first request is unfinished;
- active, expired, lost, and compare-and-swap-reclaimed leases; only a current
  token can terminalize and owner/token data never leaks;
- bounded deferred/read-only lookup proving current identical-key 202, current
  replay, and fingerprint conflict do not request a writer lock or use the writer
  busy timeout; SQLite five-second busy timeout and `BEGIN IMMEDIATE` apply only to
  absent/expired/reclaimable upgrade races and phase-two mutation ordering;
- same-key same-fingerprint terminal success and terminal failed exact replay;
- byte-for-byte replay body and original headers plus only
  `Idempotency-Replayed: true`;
- same-key different-fingerprint `409`;
- delayed execution proving expiry is exactly 24 hours after `completed_at`;
- no retention expiry/purge of in-progress records, safe lease reclaim, and safe
  expired-terminal key reuse;
- response loss after commit and process restart replay;
- concurrent identical and different keys with exactly one claim/event;
- pre-reservation auth/validation failures create no record; deterministic
  post-reservation 404/409/412/unconfigured failures terminalize as failed with no
  project/event and exact replay; transient dependency/unexpected failures roll
  back phase two and recover through lease expiry;
- failure injection before/after reservation commit and every
  project/event/terminal write proving the reservation survives appropriately but
  project/event/terminal state is atomic and never orphaned.

### 11.6 API/OpenAPI conformance

Assert exactly five 01A-v6 routes, methods, status/header matrices, concrete safe
schemas, canonical digest bytes/ETags, request-ID
header/body equality, no browser path inputs, no hidden fields, `no-store`, ETags,
and absent mutation methods. Enumerate OpenAPI operations and prove all four reads
are explicitly `x-operator-action=false`, claim alone is true, the v0.1 bijection is
exactly `{claim_project}`, and no placeholder/full-registry route exists.

## 12. Verification gates for the future implementation

Before tests, retrieve authoritative module commands:

```powershell
python scripts/query_docs.py --boot-snapshot
python scripts/query_docs.py --test-command codex-control-centre
python scripts/query_docs.py --search "Codex supervisor migration readiness"
```

Then run at minimum, using isolated environment variables whose values are never
printed:

```powershell
python -m pytest codex-control-centre/tests/test_supervisor_identity.py -q
python -m pytest codex-control-centre/tests/test_supervisor_bootstrap_claim.py -q
python -m pytest codex-control-centre/tests/test_supervisor_idempotency.py -q
python -m pytest codex-control-centre/tests/test_supervisor_events.py -q
python -m pytest codex-control-centre/tests/test_migrations.py -q
python -m pytest tests/test_codex_backend_mount.py -q
python -m pytest tests/test_platform_owner_authority.py tests/test_auth_contract.py tests/test_resident_agent.py tests/test_admin_support_tickets.py tests/test_support_ticket_workflow.py -q
python scripts/verify_zero_console_errors.py
python scripts/verify_living_docs.py --path codex-control-centre/README.md
python scripts/verify_living_docs.py --path docs/architecture/README.md
python scripts/verify_living_docs.py --path docs/README.md
```

At the required base, every pre-existing script, README, mount/migration test, and
P0 regression-suite path in these commands exists. The four
`test_supervisor_*.py` targets are deliberate new allowlisted outputs of the future
implementation and must exist before this command block is run.

The P0 regression gate must additionally pass as this exact standalone command in
a fresh process, without relying on a previously run supervisor or migration test:

```powershell
python -m pytest tests/test_platform_owner_authority.py tests/test_auth_contract.py tests/test_resident_agent.py tests/test_admin_support_tickets.py tests/test_support_ticket_workflow.py -q
```

Acceptance requires that the root conftest-created CCC database reaches nested head
`003` before application use, the command succeeds regardless of test ordering,
the pre/post existence, size, modification time, and SHA-256 sentinels for every
default database/WAL/SHM file match, the process-unique temporary directory is
removed at session finish, and no database or sidecar residue remains.

Run isolated child-process migration probes for all matrix rows. Each child receives
only a newly created temporary database URL through its environment; the URL is
never printed, and the directory is removed afterward. Capture only exit status,
bounded revision tokens, and assertions. Verify root `alembic current` and nested
CCC `alembic current` independently against disposable databases. Do not run
Alembic against the checkout/default runtime database.

The relevant runtime smoke mounts FastAPI Bookings with synthetic users and a
temporary CCC DB, proves all five routes and auth boundaries, then exits without
leaving a listener. The zero-console/network gate is mandatory because `app/main.py`
and mounted browser-visible APIs change, even though no frontend file changes.

Inspect `git status --short`, `git diff --stat`, and the exact allowlist. Stage only
verified allowlisted paths; never stage runtime databases or unrelated drift. After
independent QA sign-off and all gates, the future implementation task must commit
and push the approved task branch as required by repository policy. This planning
turn performs no stage, commit, push, service start, or implementation.

## 13. Living documentation requirements

Update the ADR to record that 01A implements only a v0.1 read/claim subset and
cannot activate v2; the full registry and cutover enforcement remain later work.
Update the CCC README with purpose/scope, architecture/files, four configuration
values, two-database migration ownership, exact endpoints, auth/scope, adoption,
idempotency/concurrency, no-path disclosure, v1 claimed-row guard, rollback,
known limitations, and exact verification commands. Update central indexes only
through their normal generator and verify them. Do not rewrite the accepted
WP-SEC brief/ADR or the rejected historical brief.

## 14. Stop conditions

Stop and rebrief if:

1. the checkout is not at exact base `c18f20ef46efa2740528c1b1f5040c3044d5c01e`
   before implementation starts;
2. root head differs from `d4b8f2a6c901` or CCC head differs from `001` at base;
3. an implementation change to a WP-SEC file, root migration, frontend file, or
   any non-allowlisted path appears necessary;
4. `codex-control-centre/tests/conftest.py` appears to need modification without a
   reproduced isolation defect and explicit rebrief;
5. `tests/conftest.py` would need any change beyond the section 11.1 nested
   migration bootstrap, would touch a runtime database, would make production code
   test-aware, or would interfere with CCC migration tests;
6. active persisted `require_platform_owner` cannot run before CCC access;
7. exact-root identity is ambiguous, a legacy schema cannot be structurally proven,
   or a claimed-row invariant cannot be enforced at database level;
8. configuration would require a browser path, path response, implicit default
   branch, internal ID exposure, or environment-based authority;
9. safe degraded readiness would require querying an unavailable domain table or
   inventing state, or infrastructure/project readiness cannot remain distinct;
10. the short reservation cannot commit before work, lease ownership/reclaim cannot
   be compare-and-swap safe, or claim/event/terminalization cannot be atomic in the
   second transaction;
11. exact success and failed replay cannot preserve response bytes/headers or
    completion-based retention expiry;
12. a mission, work-package, brief, run, assignment, approval, evidence, cutover
    mutation, v2 activation, stream, UI, worker, shell, Git, deployment, external
    provider, booking, payment, SMS, or customer-data behavior enters scope;
13. verification touches the default `codex.db` or reveals unrelated regressions.

## 15. Explicit WP-UI-01B and later deferrals

Deferred work includes the rebuilt supervisor UI; mission/work-package/brief and
execution/evidence models; run, worker, assignment, approval and audit views;
SSE/WebSocket event delivery; full v1.0/72-row action registry; v2 read-only or
active cutover transitions; legacy mutation enforcement required before activation;
rollback/drain workflows; multi-project administration; general legacy API redesign;
and any coding-worker, shell, Git, deployment, source-reading, unrestricted database,
or external integration capability.

WP-UI-01A-v6 is accepted only when its five-endpoint contract is real and durable,
the configured project is safely claimed but remains legacy-controlled, migration
truth is explicit, authority is exclusively grant-backed, exact replay and event
integrity survive restart/concurrency, no path or internal identity leaks, all gates
pass, independent QA signs off, and the allowlisted implementation is committed and
pushed on the approved branch.
