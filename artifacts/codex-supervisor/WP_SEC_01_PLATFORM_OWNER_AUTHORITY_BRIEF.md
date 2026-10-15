# WP-SEC-01 — Persisted Platform-Owner Authority

**Status:** signed v2 implementation brief; no implementation authorized by this document

**Version:** `v2`

**Supersedes v1 SHA-256:** `B3C1C3DCF2E9E3C776579CB59C9CE19BD28029BFE5B192E9F81F4894E2ACA01A`

**Base commit:** `3aa3b33b44907148c0e1854eb0373c03dc8a55a4`

**Implementation branch:** `codex/codex-supervisor-platform-authority`

**Anti-Gravity task:** `ccc_wp_sec_01`

**Dependency:** `ccc_wp_ui_00`

**Required next gate:** independent `ccc_wp_sec_01_review` before any corrected WP-UI-01A implementation

## 1. Outcome and security correction

WP-SEC-01 creates the real authority prerequisite for the Codex Control Centre,
resident agent, platform support console, and later Supervisor v2 facade. The
only platform-owner capability is a persisted field on the authoritative
FastAPI Bookings `users` row:

```text
User.is_platform_owner: BOOLEAN NOT NULL DEFAULT FALSE
```

`require_platform_owner` MUST authorize only a freshly authenticated user for
whom both `is_active is True` and the persisted `is_platform_owner is True`.
The dependency MUST NOT infer platform authority from tenant role `owner`,
`admin`, or `manager`; a dynamic `is_superuser` attribute; an environment
allowlist; the JWT; a Control Centre table; or a browser claim. Ordinary tenant
authorization remains unchanged.

This is a security correction to the authority premise recorded in
`artifacts/codex-supervisor/P0_INDEPENDENT_REVIEW.md` and
`artifacts/codex-supervisor/P0_INDEPENDENT_REREVIEW.md`. Those reports remain
immutable historical evidence. The implementation adds a new ADR that
explicitly supersedes only their `owner or is_superuser` authority definition;
it does not rewrite or invalidate the accepted P0 transport, SSE, Skills-RAG,
worker-acknowledgement, or mounted-secret containment evidence.

## 2. Scope

### In scope

1. Add and migrate `users.is_platform_owner` with a false backfill and false
   application/server defaults.
2. Replace the inferred `require_platform_owner` rule with the persisted,
   active-user rule.
3. Add a single transactional authority service and an offline-only CLI for
   `status`, `grant`, and `revoke` by positive numeric tenant/user IDs.
4. Write a structural `AuditLog` in the same transaction as every applied
   grant or revoke.
5. Serialize authority changes and prevent revocation of the last active
   platform owner.
6. Ensure public user creation/update, Google SSO, first-user creation, JWTs,
   and local authentication bypass cannot set or imply the capability.
7. Correct all affected authorization fixtures and add negative, migration,
   persistence, concurrency, CLI, audit, and database-isolation coverage.
8. Update living documentation and add the superseding authority ADR.

### Explicitly out of scope

- No HTTP endpoint, UI, API schema, token claim, role, generic superuser flag,
  environment list, or Control Centre table for granting/revoking authority.
- No Supervisor v2 bootstrap/project/claim implementation, actor scope,
  project ownership, idempotency ledger, facade route, cutover transition, or
  `v2_active` activation. Those remain blocked behind accepted WP-SEC-01.
- No changes to tenant role semantics or ordinary tenant CRUD permissions.
- No standalone Control Centre shared-secret redesign; the mounted boundary is
  the target. Existing standalone compatibility remains separately bounded.
- No production data change, default owner seeding, automatic promotion,
  email/login lookup, bulk listing, live service start, deployment, or push.
- No rewrite of the two historical P0 review artifacts.

The final “no push” restriction above applies to this brief-authoring task.
The later implementation task is governed by the repository completion policy:
after every required verification gate and independent QA sign-off passes, it
must stage only its approved allowlist, commit, and push the verified task
branch. It must not merge, force-push, push unrelated changes, or deploy.

## 3. Binding data contract

### 3.1 ORM and database

Update `app/models/user.py` and add migration
`alembic/versions/d4b8f2a6c901_add_platform_owner_authority.py` with:

- revision `d4b8f2a6c901`;
- `down_revision = "10251fbf7103"`; stop if the repository head differs;
- `users.is_platform_owner` as `Boolean`, `nullable=False`, Python default
  `False`, and retained database `server_default=sa.false()`;
- existing rows backfilled to false by the non-null server default;
- a named composite index
  `ix_users_platform_owner_active (is_platform_owner, is_active)`;
- no trigger, separate grants table, role rewrite, or implicit initial owner.

The false server default is permanent, not a migration-only convenience. Raw
SQL, SSO, and future insertion paths therefore also fail closed. The downgrade
drops the named index and then the column; it is operationally forbidden while
new application code is running.

### 3.2 Authorization dependency

`app/api/deps.py::require_platform_owner` has exactly this decision:

```text
authenticated user absent/invalid                   -> existing upstream 401
authenticated user with is_active != True           -> 403
authenticated user with is_platform_owner != True   -> 403
both persisted booleans exactly True                 -> return current_user
```

The error is a stable, non-sensitive 403. Role, tenant plan, token claims,
`getattr(..., "is_superuser")`, and arbitrary runtime attributes are ignored.
`get_current_user` already reloads the tenant-scoped user row on every request;
the authority bit MUST NOT be embedded in the JWT, so revocation or
deactivation takes effect on the next request without token rotation.

### 3.3 Public schemas and creation paths

`UserCreate` and `UserUpdate` MUST use `extra="forbid"` and MUST NOT declare
`is_platform_owner` or `is_superuser`. Direct validation tests must prove that
either privileged key returns a validation error. The admin user-creation
route, Google SSO auto-provisioning, and first-user `role="owner"` behavior
continue to work, but every created row receives false from the trusted model
and database defaults. No request-body field is forwarded to the capability.

WP-SEC-01 does **not** add the capability to `/admin/auth/me`, `/admin/me`,
`User`, `UserResponse`, or an access-token claim. It is not required for
authorization or offline provisioning, and later Supervisor UI should consume
server-derived `allowed_actions`, not a writable privilege property. Any future
need for read-only self exposure requires a separate reviewed contract.

## 4. Offline management contract

Create `scripts/manage_platform_owner.py`. It imports the application session
factory and the single service in
`app/services/auth/platform_owner_authority.py`; it MUST NOT duplicate SQL or
authorization logic.

### 4.1 Commands

```powershell
python scripts/manage_platform_owner.py status --tenant-id 12 --user-id 34
python scripts/manage_platform_owner.py grant --tenant-id 12 --user-id 34 --reason-code initial_provisioning
python scripts/manage_platform_owner.py grant --tenant-id 12 --user-id 34 --reason-code initial_provisioning --apply --confirm "GRANT PLATFORM OWNER 12:34"
python scripts/manage_platform_owner.py revoke --tenant-id 12 --user-id 34 --reason-code access_review --apply --confirm "REVOKE PLATFORM OWNER 12:34"
```

Rules:

- `tenant-id` and `user-id` are required positive 32-bit integers for every
  command. The service resolves the composite `(tenant_id, user_id)` target;
  no login or email lookup is supported.
- `status` is read-only and does not accept `--apply`.
- `grant` and `revoke` are dry-run unless `--apply` is present. A dry-run opens
  no mutation transaction and writes no audit record.
- `--apply` also requires the exact, case-sensitive typed confirmation shown
  above after decimal ID normalization. Missing/mismatched confirmation fails
  before mutation.
- Applied mutation requires `--reason-code` from
  `initial_provisioning`, `operator_change`, `incident_response`,
  `access_review`, or `rollback`. Optional `--change-ref` is limited to 1–64
  characters matching `[A-Za-z0-9._:/-]+`.
- There is no `--database-url`, environment override, force flag, email/login
  output, interactive password, or HTTP call. The CLI uses configured FastAPI
  Bookings storage and never prints a database URL, credential, JWT, secret,
  login, email, name, or audit-details blob.
- Machine-readable stdout contains only `ok`, `operation`, numeric IDs,
  `active`, `is_platform_owner`, `changed`, `applied`, and a stable error code.
  Diagnostic exceptions are sanitized; stack traces are not emitted by
  default.
- Exit codes are `0` success/idempotent no-op/status, `2` invalid arguments or
  confirmation, `3` target not found/mismatched tenant, `4` last-active-owner
  protection, and `5` transactional failure.

### 4.2 Idempotency and transactionality

- Grant false -> true produces exactly one row update and one audit row.
- Grant true -> true returns `changed=false`, updates nothing, and creates no
  duplicate audit row.
- Revoke true -> false produces exactly one row update and one audit row unless
  the last-active-owner guard blocks it.
- Revoke false -> false returns `changed=false`, updates nothing, and creates no
  duplicate audit row.
- Audit insertion and capability mutation commit atomically. An audit failure
  rolls back the capability change.

Applied audit rows use the existing `audit_logs` table:

```text
tenant_id  = target tenant ID
user_id    = NULL (offline operator is not impersonated as an application user)
action     = "platform_owner.granted" | "platform_owner.revoked"
target_type= "user"
target_id  = target numeric user ID
details    = canonical JSON containing only source="offline_cli", reason_code,
             optional validated change_ref, previous_value, new_value
```

No customer data or human identity is stored or printed. The JSON is encoded
with sorted keys. The service must never write an audit row for dry-run,
status, validation failure, not-found, protected-last-owner, or idempotent
no-op.

### 4.3 Concurrency and last-owner invariant

All applied grant/revoke operations acquire one transaction-global authority
mutation lock before reading state:

- PostgreSQL: a fixed, documented `pg_advisory_xact_lock` key, followed by
  `SELECT ... FOR UPDATE` for the target user;
- SQLite: an explicit `BEGIN IMMEDIATE` transaction before the target read;
- any unsupported dialect fails closed rather than running unlocked.

Within that serialized transaction, revoke counts rows where
`is_platform_owner IS TRUE AND is_active IS TRUE`. Revoking an active target is
rejected when the count is one. Revoking an inactive flagged target is allowed
because it cannot reduce the active count. The grant path supports recovery
from a zero-owner post-migration state. Concurrent grants of the same target
must yield one changed result, one no-op, and one audit. Concurrent revokes of
two active owners must leave exactly one active owner, with one successful
audit and one stable `last_active_platform_owner` refusal.

This service is the sole supported writer. Future user deactivation/deletion
workflows that can affect a platform owner must call the same serialized guard;
none exists in the current HTTP surface, and WP-SEC-01 must not invent one.

## 5. LOCAL_AUTH_BYPASS resolution

`LOCAL_AUTH_BYPASS` remains a development-only authentication convenience and
never becomes an authorization bypass:

1. It remains forbidden in production by `Settings` validation.
2. `get_current_user` may use the fixed local token only when the flag is true,
   but the selected row must be active and persistently
   `is_platform_owner=True`; remove the current owner/admin role lookup.
3. The lookup remains tenant-scoped and deterministic. If no such row exists,
   return the existing safe 503-class unavailable result without revealing
   account details.
4. The mounted Control Centre helper still delegates to
   `require_platform_owner`; it cannot create a synthetic user, attach a
   dynamic property, or accept standalone `local_secret` authority.
5. Tests cover flag disabled, no eligible platform owner, inactive platform
   owner, ordinary tenant owner/admin, eligible persisted platform owner, and
   rejection outside the native mounted application.

## 6. Required endpoint and isolation evidence

WP-SEC-01 adds no endpoint. Existing methods, paths, and envelopes remain
unchanged. Tests must demonstrate:

- an active persisted platform owner can use representative protected routes;
- an ordinary tenant `owner`, `admin`, and `manager` each receive 403 from:
  - mounted Control Centre: `GET /api/admin/codex/projects` and a protected
    mutation such as `POST /api/admin/codex/events/ticket`;
  - resident agent: `GET /api/admin/resident-agent/status` and SSE events;
  - platform support, with these exact checks:
    `GET /api/admin/support-tickets`,
    `POST /api/admin/support-tickets/{ticket_id}/internal-note`, and
    `POST /api/admin/support-tickets/{ticket_id}/launch-codex`; every request
    made as an ordinary tenant owner/admin/manager must return exactly 403
    before ticket lookup, note creation, or worker dispatch;
- a dynamically attached `is_superuser=True` and a JWT role claim cannot
  authorize;
- inactive and revoked platform owners receive 403 immediately using the same
  otherwise-valid token;
- a token from tenant A presented with tenant B context is rejected upstream
  and cannot use a tenant-B privileged row;
- tenant owner/admin behavior on ordinary non-platform booking/admin routes is
  unchanged.

## 7. Required tests

### 7.1 New focused authority suite

`tests/test_platform_owner_authority.py` must cover:

1. persisted false/true reload through a new SQLAlchemy session;
2. exact active-plus-capability dependency rule;
3. denial of tenant owner/admin/manager, dynamic superuser, inactive, revoked,
   and cross-tenant identities;
4. grant/revoke/status by numeric composite identity;
5. dry-run and confirmation mismatch cause zero writes and zero audits;
6. invalid/overflow IDs, unknown tenant/user, and tenant mismatch;
7. idempotent repeated grant/revoke audit cardinality;
8. canonical structural audit content and rollback on injected audit failure;
9. last-active-owner refusal;
10. real threaded SQLite concurrent grant and two-owner concurrent revoke using
    a temporary file-backed database, not in-memory connection illusions;
11. PostgreSQL advisory-lock statement and, in the approved ephemeral test
    database gate, the same concurrent-revoke invariant;
12. stdout/stderr canaries proving no email, login, database URL, credential,
    or secret disclosure.

### 7.2 Migration suite

`tests/test_platform_owner_authority_migration.py` must use temporary databases
and exercise:

- fresh empty-database `alembic upgrade head`, explicitly treated only as
  metadata/bootstrap-chain parity rather than evidence that a populated
  deployment upgrades safely;
- an existing database at revision `10251fbf7103` with owner/admin/manager user
  rows, then `10251fbf7103 -> d4b8f2a6c901`: every row is false and non-null;
- direct SQL insert omitting the column receives false;
- index and server-default introspection;
- `d4b8f2a6c901 -> downgrade 10251fbf7103 -> d4b8f2a6c901`, including data
  preservation except for the intentionally removed capability on downgrade;
- exactly one Alembic head and exact down-revision linkage;
- no `Base.metadata.create_all()` used as migration evidence;
- `alembic/env.py` remains unchanged. Any need to change it is a stop-and-
  rebrief condition.

### 7.3 Existing-suite corrections and P0 regression gate

Correct positive fixtures to set `is_platform_owner=True` and retain/add
ordinary-owner negatives in:

- `tests/test_admin_support_tickets.py`
- `tests/test_codex_backend_mount.py`
- `tests/test_codex_end_to_end_integration.py`
- `tests/test_resident_agent.py`
- `tests/test_support_ticket_workflow.py`

`tests/test_auth_contract.py` must prove UserCreate/UserUpdate reject privileged
extra fields, local/admin/SSO/first-user creation persists false, JWTs omit the
field, and `/admin/auth/me` does not expose it.

The full accepted P0 regression gate remains:

```powershell
F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -m pytest tests/test_platform_owner_authority.py tests/test_platform_owner_authority_migration.py tests/test_auth_contract.py tests/test_admin_support_tickets.py tests/test_codex_backend_mount.py tests/test_codex_end_to_end_integration.py tests/test_resident_agent.py tests/test_support_ticket_workflow.py -v

Push-Location codex-control-centre
F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -m pytest tests/test_security.py tests/test_events.py -v
Pop-Location

Push-Location frontend
node --experimental-strip-types --test src/pages/admin/coding-cockpit/coding-cockpit.test.ts
npm run build
Pop-Location
```

The two historical resident stress-fuzzer tests are not waived. WP-SEC-01 must
run the focused suite in isolated storage; a pre-existing unrelated failure is
reported separately and cannot conceal any authority failure.

### 7.4 Test database isolation

Root `tests/conftest.py` and new
`codex-control-centre/tests/conftest.py` must set a process-unique temporary
SQLite database URL before importing either application. The temporary
directory is cleaned at session end. No test may open, create, migrate, change,
or delete repository `codex-control-centre/codex.db`, its `-wal`/`-shm` files,
or the default `fastapi_bookings.db`.

Add sentinel tests that snapshot existence, size, mtime, and SHA-256 of those
default files before and after the focused/P0 app lifespans. Existing files are
never deleted or normalized. A changed/default-created file is a hard failure.

## 8. Deployment, provisioning, verification, and rollback

This section is a future operator procedure. It is not executed by this
brief-authoring task. The order is mandatory because all existing rows
backfill false, and migration/provisioning must come from the exact reviewed
release checkout or immutable artifact that will subsequently be deployed.

### Phase A — migration first

1. Pin the accepted WP-SEC release commit/artifact and record its digest. The
   serving application remains entirely on the pre-WP-SEC release during
   Phases A and B; do not start the reviewed checkout as an application server.
2. From that exact reviewed release checkout/artifact, use its offline Alembic
   and CLI entry points against the operator-approved database. Do not mix a
   migration from one commit with a CLI or deployment from another.
3. Back up the target database under the normal operator process.
4. Apply Alembic through `d4b8f2a6c901` from the pinned reviewed artifact.
5. Verify the column, false default, non-null constraint, index, and one head.
6. Do not deploy or serve the new dependency yet.

### Phase B — offline provision and verify

1. Still while the serving application remains pre-WP-SEC, select targets
   out-of-band and use numeric tenant/user IDs only.
2. Run `status`, dry-run `grant`, then typed-confirmed `grant --apply` using
   the CLI from the same pinned reviewed release artifact used in Phase A.
3. Provision at least one active platform owner; two independent active owners
   are strongly required before production rollout so recovery does not depend
   on an emergency database change.
4. Run `status` again and independently verify the matching structural audit
   row. Do not paste user identity or database output into logs.
5. If no active platform owner is verified, stop deployment.

### Phase C — code rollout

1. Deploy the exact same pinned, reviewed release artifact used for migration
   and provisioning; a rebuilt or different commit must repeat review and the
   pre-deploy checks.
2. With labelled synthetic/staging identities, prove persisted platform owner
   success and ordinary tenant owner/admin denial across Control Centre,
   resident agent, and platform support.
3. Revoke a non-last synthetic platform owner and prove the same token is
   denied on its next request.
4. Run all gates in Section 10 before production approval.

### Rollback constraints

- Prefer code rollback only; leave the additive column and audit evidence in
  place. Old code will ignore the column.
- Never downgrade the migration while code references the column.
- Database downgrade requires explicit owner approval, prior code rollback,
  a backup, confirmation that no investigation needs the capability state, and
  acknowledgement that the boolean state is lost. Existing `AuditLog` rows are
  retained.
- There is no force-revoke escape hatch. Loss of every active platform owner
  requires an explicitly reviewed emergency database procedure outside this
  work package.

## 9. Exact future implementation changed-file allowlist

Only the following paths may change during implementation and independent
review. Any additional path is a stop-and-rebrief condition.

1. `artifacts/codex-supervisor/WP_SEC_01_PLATFORM_OWNER_AUTHORITY_BRIEF.md`
2. `alembic/versions/d4b8f2a6c901_add_platform_owner_authority.py`
3. `alembic/README.md`
4. `app/models/user.py`
5. `app/api/deps.py`
6. `app/schemas/user.py`
7. `app/services/auth/platform_owner_authority.py`
8. `scripts/manage_platform_owner.py`
9. `tests/conftest.py`
10. `tests/test_platform_owner_authority.py`
11. `tests/test_platform_owner_authority_migration.py`
12. `tests/test_auth_contract.py`
13. `tests/test_admin_support_tickets.py`
14. `tests/test_codex_backend_mount.py`
15. `tests/test_codex_end_to_end_integration.py`
16. `tests/test_resident_agent.py`
17. `tests/test_support_ticket_workflow.py`
18. `codex-control-centre/tests/conftest.py`
19. `app/models/README.md`
20. `app/services/auth/README.md`
21. `app/api/routers/README.md`
22. `scripts/README.md`
23. `tests/README.md`
24. `codex-control-centre/README.md`
25. `docs/architecture/ADR_PLATFORM_OWNER_AUTHORITY.md`
26. `docs/architecture/README.md`
27. `docs/README.md`
28. `docs/AGENT_BOOT_SNAPSHOT.md`
29. `docs/MODULE_INDEX.md`
30. `docs/module_manifest.json`

`app/core/config.py`, `app/api/routers/auth.py`, CCC production code, frontend
code, and public API schemas are deliberately absent: the capability needs no
new setting, `/auth/me` exposure, route mutation, or frontend control. If
implementation proves one of those files is necessary, stop and obtain a
rebrief before editing it.

## 10. Verification commands

Before tests, retrieve commands rather than guessing:

```powershell
python scripts/query_docs.py --boot-snapshot
python scripts/query_docs.py --test-command auth
python scripts/query_docs.py --test-command models
python scripts/query_docs.py --test-command resident_agent
python scripts/query_docs.py --search "platform owner authority"
```

Run the focused and P0 commands in Section 7, then:

```powershell
F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -m alembic heads
@'
import os
import subprocess
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="wp-sec-01-alembic-") as temp_dir:
    database_path = Path(temp_dir) / "verification.db"
    child_env = dict(os.environ)
    child_env["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    for alembic_args in (("upgrade", "head"), ("current",)):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *alembic_args],
            cwd=Path.cwd(),
            env=child_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise SystemExit("isolated Alembic child-process verification failed")
print("isolated Alembic child-process verification passed")
'@ | F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -
F:\Projects\fastapi_bookings\.venv\Scripts\python.exe -m py_compile app/models/user.py app/api/deps.py app/schemas/user.py app/services/auth/platform_owner_authority.py scripts/manage_platform_owner.py

python scripts/verify_living_docs.py --path alembic/README.md
python scripts/verify_living_docs.py --path app/models/README.md
python scripts/verify_living_docs.py --path app/services/auth/README.md
python scripts/verify_living_docs.py --path app/api/routers/README.md
python scripts/verify_living_docs.py --path scripts/README.md
python scripts/verify_living_docs.py --path tests/README.md
python scripts/verify_living_docs.py --path codex-control-centre/README.md

python scripts/index_living_docs.py
git diff --check
python scripts/verify_zero_console_errors.py
```

The child harness passes the temporary SQLite URL only through a copied child
environment, captures and discards command output, never prints the URL, and
deletes the database with its temporary directory. Its empty-database run is
only a bootstrap smoke check. The populated `10251fbf7103 -> d4b8f2a6c901`
and `head -> 10251fbf7103 -> head` tests in Section 7.2 are the required
migration evidence. `alembic/env.py` is not changed.

For PostgreSQL concurrency, use only an approved ephemeral synthetic test
database supplied through the test harness. Never print its URL and never use a
production or customer database. The browser gate requires the exact reviewed
backend and frontend with synthetic data; follow repository process-management
rules before starting them.

Before future implementation completion, compare `git diff --name-only` to
Section 9, verify default database sentinel hashes are unchanged, and obtain
independent security/QA sign-off. Once all required gates and that sign-off
pass, stage only the 30 explicit paths actually changed, commit, and push the
verified task branch as required by repository policy. Do not merge,
force-push, push unrelated paths, or deploy.

## 11. Acceptance criteria

WP-SEC-01 is acceptable only when all of the following are true:

- exactly one Alembic head exists and every existing/new user defaults false;
- only active persisted platform owners pass `require_platform_owner`;
- tenant roles and dynamic properties confer no platform authority;
- no HTTP/public-schema/SSO/first-user/JWT path can set or imply authority;
- CLI writes are opt-in, typed-confirmed, numeric-ID scoped, serialized,
  transactional, idempotent, audited, and non-disclosing;
- the last active owner cannot be revoked under concurrency;
- revocation/deactivation is effective on the next authenticated request;
- ordinary owners are denied across CCC, resident agent, and support console;
- default application and Control Centre databases are untouched by tests;
- focused, migration, all accepted P0, documentation, build, browser, and
  independent review gates pass;
- the superseding ADR clearly preserves historical P0 artifacts.

## 12. Stop conditions

Stop without broadening the diff if:

- HEAD is not exact `3aa3b33b` at implementation start, the Alembic head is not
  `10251fbf7103`, or the worktree is not clean apart from this approved brief;
- another task changes any allowlisted file or creates a competing authority
  mechanism/migration;
- safe PostgreSQL/SQLite serialization cannot be demonstrated;
- an existing user-management path can deactivate/delete the last active owner
  without the shared guard;
- migration/provisioning cannot verify at least one active owner before code
  rollout;
- a test touches a default/runtime database or requires live customer data,
  production credentials, SMS, booking, or external-provider actions;
- the implementation requires an HTTP mutation endpoint, browser-supplied
  privilege, `/auth/me` expansion, generic superuser, role reinterpretation,
  environment allowlist, or a file outside Section 9;
- any ordinary tenant authorization regression, cross-tenant access, secret or
  identity disclosure, multiple migration head, P0 regression, browser error,
  or network failure remains unresolved.

## 13. Delivery and review ordering

1. `ccc_wp_sec_01` implementation on the dedicated branch.
2. `ccc_wp_sec_01_review` independent audit, dependent on `ccc_wp_sec_01`.
3. Only after accepted review: issue the corrected WP-UI-01A brief v2 and
   register its implementation as dependent on `ccc_wp_sec_01_review` (as well
   as the existing WP-UI-00 ancestry).
4. Independent WP-UI-01A review remains a separate dependent task.

Anti-Gravity worker execution stays manual. Registration is tracking and
evidence only; it is not permission for the resident agent or dashboard to
auto-run implementation.
