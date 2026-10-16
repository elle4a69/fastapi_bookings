# WP-UI-00 — P0 Integration and Codex Supervisor Contract Freeze

| Field | Value |
|---|---|
| Anti-Gravity task | `ccc_wp_ui_00` |
| Programme | `fastapi_bookings_codex_supervisor` |
| Sub-project | `ccc_supervisor_foundation` |
| Status | `ready` |
| Execution gate | Allowed only on the clean branch/worktree defined below |
| Owner | Security/backend implementation agent |
| Independent reviewer | A fresh agent that did not author the change |
| Repository | `F:\Projects\fastapi_bookings` |
| Brief version | `3` |
| Revision | Git-blob evidence authority and Windows-safe worktree validation |
| Supersedes | Brief SHA-256 `5802DEE9E3A05F4C692103A9E2E4C6372E5E6F82BC6F1130089721926069EB68` |
| Revised | 2026-10-15 (Australia/Sydney) |

## Problem

The accepted Codex Supervisor design is not yet on a version-controlled implementation line. Baseline commit `6256fc5d25e3ad5c2f60d739c24446ebc4df3546` does not itself contain the P0 trust-boundary hardening, although pushed P0 commit `170f6f7eb62278bc029d39caaeda8637d4c99c59` directly descends from that baseline. The approved supervisor design and audit records are also still untracked in the primary checkout.

WP-UI-01 and every visible v2 UI package must remain blocked until P0 ancestry and the governing v2 contract decisions are frozen on one clean, independently audited branch.

## Goal

Create a clean WP-UI-00 branch whose history contains both the authoritative baseline and P0, commit only the approved supervisor design/audit records plus the narrow ADR and living-documentation updates, and prove that the inherited P0 implementation still passes its trust-boundary, frontend, documentation, browser, and clean-checkout gates.

This is an integration and contract-freeze package. It does not implement the durable supervisor domain, `/api/admin/codex/v2`, or the replacement UI.

## Revision 3 rationale

Revision 2 correctly separated the twelve immutable evidence files from mutable-document whitespace validation, but it treated raw worktree bytes as authoritative. On Windows, a fresh checkout with `core.autocrlf=true` may materialize CRLF worktree bytes from an unchanged LF Git blob, so that criterion rejected a valid committed artifact solely because of checkout configuration. Revision 3 makes the repository object the portable evidence boundary without weakening content integrity:

- each artifact's committed Git blob at `HEAD:<path>` is byte-authoritative and must match the unchanged SHA-256 manifest;
- the corresponding worktree file must equal that committed blob after replacing CRLF byte pairs with LF byte pairs only; no other whitespace, encoding, BOM, or content normalization is permitted;
- `git diff --check` remains mandatory for every mutable WP-UI-00 document and any unexpected changed path, excluding only the same twelve exact immutable-evidence paths;
- acceptance must be reproduced in fresh Windows checkouts with `core.autocrlf=true` and `core.autocrlf=false` wherever both modes are available.

## Required branch and ancestry

1. Create a dedicated clean worktree and branch named `codex/codex-supervisor-wp-ui-00` at exact commit `170f6f7eb62278bc029d39caaeda8637d4c99c59`.
2. Do not implement from the dirty primary checkout and do not copy its unrelated modifications or untracked runtime files.
3. Before editing, prove both commands exit `0`:

```powershell
git merge-base --is-ancestor 6256fc5d25e3ad5c2f60d739c24446ebc4df3546 HEAD
git merge-base --is-ancestor 170f6f7eb62278bc029d39caaeda8637d4c99c59 HEAD
```

4. Record `git status --short`, which must be empty before the approved files are introduced.
5. P0 is integrated by ancestry. Do not cherry-pick, squash, reconstruct, or partially reapply it.

## Scope

### 1. Preserve and verify P0

Retain the exact P0 behavior already committed at `170f6f7e`:

- platform-owner-only Control Centre and resident-agent authority;
- rejection of insecure default/query-token authentication;
- atomic, one-use event tickets;
- authenticated resident-event streaming with bounded reconnect behavior;
- privacy-safe Skills-RAG query derivation;
- worker acknowledgement before a dispatch is reported as accepted;
- truthful support-ticket dispatch failure instead of fabricated success.

No P0 application file should need editing in this package. If an inherited P0 test fails on the clean target commit, stop and report the exact regression rather than silently broadening WP-UI-00.

### 2. Publish the v2 contract ADR

Create `docs/architecture/ADR_CODEX_SUPERVISOR_V2_FACADE.md`. It must record, without claiming implementation:

- `/api/admin/codex/v2` as the sole future UI facade; no `/supervisor` alias;
- `Mission` as the external API/UI term mapped internally to `supervisor_programme`;
- canonical frontend ownership in `frontend/`;
- `codex-control-centre/frontend/` as reference/decommission-only and frozen against new features;
- platform-owner-only v2 exposure until actor-scoped ownership and negative isolation tests pass;
- FastAPI Bookings as the sole control plane and sole southbound Codex app-server mutation/lifecycle authority;
- native REST snapshots as durable truth and ticketed SSE as invalidation/attention transport;
- the four cutover modes, complete legal transition graph, conditional/idempotent update semantics, resource `control_plane` enforcement, and fail-closed rollback rules from the accepted foundation specification;
- exact idempotency/unknown-outcome semantics from section 15.2 of the accepted specification;
- `AllowedActionDescriptor` and closed action-registry `1.0` with 72 unique action codes, 72 registry rows, exact set equality, and the future OpenAPI mutation/action/permission bijection;
- bounded disclosure, redaction, opaque IDs, artifact-ticket, error, event, version, and non-leaking authorization conventions;
- deploy-configured project claim/quarantine as a prerequisite to Mission creation, with no browser-supplied host path;
- sole-native-worker, ownership, acknowledgement, recovery-source, and Windows-first invariants;
- CopilotKit and Assistant UI as later spike-only presentation candidates, at most one retained; Assistant UI documentation MCP as developer-only read-only research during an approved later spike;
- Codex Bridge and Open WebUI as reference-only; `codex-web-local` as rejected;
- no executable OpenAPI route, v2 model, migration, dependency, or UI is created by WP-UI-00. WP-UI-01 must implement and conformance-test the frozen contracts before any v2 screen is enabled.

The ADR may quote contract identifiers and compact schemas but should link to the accepted foundation specification rather than duplicating all 2,500-plus lines.

### 3. Version the approved supervisor records

Add the exact approved Markdown artifacts listed in the allowlist and hash manifest below. Do not add the recovery patch or arbitrary generated/task/runtime artifacts.

### 4. Update living documentation

- Update `codex-control-centre/README.md` to identify the canonical frontend, legacy freeze, P0 authority boundary, WP-UI-00 verification commands, and the fact that v2 remains unimplemented.
- Update `frontend/src/pages/admin/coding-cockpit/README.md` only with the legacy/freeze/cutover notice and current P0 verification command.
- Create `docs/architecture/README.md` with all mandatory living-document sections and links to the ADR and accepted supervisor artifacts.
- Update `docs/README.md` only to index the new architecture ADR and approved supervisor record set.
- After these inputs are committed, regenerate/query the documentation index only as a verification action. Do not commit generated index output unless a separately reviewed repository rule proves it is mandatory and the allowlist is formally amended before editing.

## Exact changed-file allowlist

Only these paths may differ from parent commit `170f6f7e`:

```text
artifacts/codex-supervisor/WP_UI_00_IMPLEMENTATION_BRIEF.md
artifacts/codex-supervisor/CCC_ARCHITECTURE_BLUEPRINT.md
artifacts/codex-supervisor/CCC_SECURITY_BASELINE.md
artifacts/codex-supervisor/CCC_UX_CONTRACT.md
artifacts/codex-supervisor/CCC_EXISTING_UI_AUDIT.md
artifacts/codex-supervisor/CCC_UI_API_CONTRACT_INVENTORY.md
artifacts/codex-supervisor/CCC_COPILOTKIT_FIT_ASSESSMENT.md
artifacts/codex-supervisor/CCC_CODEX_BRIDGE_FIT_ASSESSMENT.md
artifacts/codex-supervisor/CCC_CODEX_WEB_LOCAL_FIT_ASSESSMENT.md
artifacts/codex-supervisor/CCC_OPEN_WEBUI_FIT_ASSESSMENT.md
artifacts/codex-supervisor/CCC_ASSISTANT_UI_FIT_ASSESSMENT.md
artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md
artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_REVIEW.md
docs/architecture/ADR_CODEX_SUPERVISOR_V2_FACADE.md
docs/architecture/README.md
docs/README.md
codex-control-centre/README.md
frontend/src/pages/admin/coding-cockpit/README.md
```

The 21 files already contained in P0 are inherited history, not new WP-UI-00 modifications. If any P0 application/test file needs a new edit, stop and issue a rebrief.

## Approved immutable-evidence committed-blob manifest

The twelve files below are imported, immutable evidence. They are the only paths excluded from `git diff --check`. The committed Git blob at `HEAD:<path>` is byte-authoritative: its bytes, intentional Markdown hard breaks, headings, and content must not be edited, formatted, normalized, or rewritten. Each committed blob must match the SHA-256 value below. A Windows worktree may materialize CRLF line endings; after converting CRLF byte pairs to LF byte pairs only, its bytes must equal the committed blob exactly.

Committed-blob SHA-256 manifest:

```text
39D253F745FD2F5D2B823432D4A7136F0A146A2D474AD02D69846ABFDE58AAE2  CCC_ARCHITECTURE_BLUEPRINT.md
3C276CEF1632F72A02CB72A82CB59DDF582B85FD61A7727C2AB6B3873FD28331  CCC_SECURITY_BASELINE.md
3A9265F1626AF26528002E082D6FF3828710390C9F3B68031D820DC384F1B56F  CCC_UX_CONTRACT.md
AF9A7C7E21BC1AC9B03CC1054D779E659FC277FFB9EB184BB0C79F20BFC0155B  CCC_EXISTING_UI_AUDIT.md
05E99F56847F20D7D62A5B6C1DD30BFDFCE4176D29DFDE3B2776CAAFCB05E51B  CCC_UI_API_CONTRACT_INVENTORY.md
CC273088E7A517A1C88291CD0CFD33144C46A2A1AE62BF66B84253875C77B1B4  CCC_COPILOTKIT_FIT_ASSESSMENT.md
F524D3F14A7C86D95889E6FF3C0E4B6623D35A496EF7DF4FE6EDE979336D2E6B  CCC_CODEX_BRIDGE_FIT_ASSESSMENT.md
DAC9C0286B549C8621D9F24B41411365F8487970FF2A7E0EF43F78B2ECFC01B3  CCC_CODEX_WEB_LOCAL_FIT_ASSESSMENT.md
3DF9F267A772F6B2DCA6969120FA12B9A62FD9B7E984E684FA3382908C489A18  CCC_OPEN_WEBUI_FIT_ASSESSMENT.md
4C736351A9165F5BED5477980CC8234A611465C6638CD6178DF73F4636AC8D53  CCC_ASSISTANT_UI_FIT_ASSESSMENT.md
CF9DB16A10D51AE3EE09949C63456A42981DD92007A4DB53C654343B93ED0D29  CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md
B528B722FC5FCEF819320BB895732F9B52759AAF7868886DD2435BC0ABC706B9  CCC_SUPERVISOR_UI_FOUNDATION_REVIEW.md
```

The committed-blob hash is the controlling evidence-integrity gate. Worktree comparison permits only `b"\r\n"` to `b"\n"` conversion before exact byte equality is tested. It does not permit trimming, whitespace collapsing, Unicode whitespace normalization, decoding/re-encoding, BOM removal, formatter changes, or any other transformation.

## Non-goals and prohibited work

- No durable supervisor tables, ORM models, repositories, services, migrations, APIs, routers, or `/api/admin/codex/v2` runtime.
- No new frontend route, shell, screen, component, state store, fixture, or visual redesign.
- No change to current production route behavior or cutover mode.
- No dependency or lockfile change.
- No TanStack Query, Vitest, Testing Library, axe, AlertDialog, AG-UI, CopilotKit, Assistant UI, Assistant Cloud, Open WebUI, Codex Bridge, or `codex-web-local` installation/runtime.
- No edit to `codex-control-centre/frontend/`.
- No migration; expected migration change count is zero.
- No deployment, branch merge, worktree deletion, service restart, live external action, booking, SMS, customer contact, payment, or production-data access.
- No `.env` read or modification.
- No staging of `codex.db`, `codex.db-wal`, `codex.db-shm`, logs, caches, build output, media drafts, recovered patch files, Anti-Gravity task artifacts, or unrelated dirty-primary files.
- No mock implementation, fake API, fake status, fixture-backed production behavior, or locally invented authority.

## Dependencies and blockers

Dependencies are complete:

- baseline `6256fc5d25e3ad5c2f60d739c24446ebc4df3546`;
- P0 `170f6f7eb62278bc029d39caaeda8637d4c99c59`;
- accepted foundation specification SHA-256 `CF9DB16A10D51AE3EE09949C63456A42981DD92007A4DB53C654343B93ED0D29`;
- accepted independent foundation review;
- accepted architecture, security, UI audit, API inventory, and external-fit assessments.

Current documentation discovery returns the authoritative resident-agent command but no registered command for `codex-control-centre`, `coding-cockpit`, or `admin support`. This is a known documentation-index gap to close through the allowlisted README inputs. It is not permission to invent a global test suite.

Stop and rebrief if:

- either required commit is absent or ancestry fails;
- any approved artifact hash differs;
- a required change falls outside the allowlist;
- P0 verification exposes a new regression;
- the clean checkout imports untracked primary-checkout content;
- completion would require a migration, dependency, v2 runtime, or UI implementation.

## Acceptance criteria

1. `HEAD` descends from exact baseline `6256fc5d` and exact P0 `170f6f7e`.
2. The candidate worktree is clean before work and contains no imported unrelated primary-checkout changes.
3. The only candidate diff against `170f6f7e` is the exact allowlist above.
4. All twelve approved supervisor design/audit records are tracked as immutable evidence, and every committed Git blob retains its byte-authoritative manifest hash; each worktree file equals its blob after CRLF-to-LF conversion only. `p0_implementation_recovered.patch` is not tracked.
5. The ADR records every contract decision in Scope section 2 and consistently marks future v2 models/endpoints/OpenAPI implementation as prerequisites, not current functionality.
6. The ADR contains the complete four-mode legal cutover graph and registry `1.0` integrity statement: 72 unique codes, 72 unique rows, exact equality, no duplicate semantic route.
7. `frontend/` is declared canonical in all relevant docs; `codex-control-centre/frontend/` is explicitly frozen/reference-only, and no file under it changes.
8. P0 trust-boundary tests pass with no new failure and preserve platform-owner isolation, ticket single use, credential handling, privacy-safe skill lookup, acknowledged dispatch, and truthful failure behavior.
9. No migrations, dependency changes, v2 runtime routes, supervisor data models, or new UI files exist in the diff.
10. Living-document checks pass for every changed README, and the post-change documentation index returns focused commands for resident-agent, Control Centre security/events, and coding-cockpit contracts.
11. Frontend tests/build and the six-route zero-console/network browser gate pass against the exact candidate commit using labelled synthetic/local data only.
12. Scoped `git diff --check` passes for every mutable WP-UI-00 document and every unexpected changed path, excluding only the twelve exact immutable-evidence paths named in the manifest. No blanket whitespace waiver is used.
13. The manifest-verification script passes for all twelve exclusions, proving exact committed-blob bytes and worktree equality after CRLF-to-LF conversion only in fresh Windows `core.autocrlf=true` and `core.autocrlf=false` checkouts.
14. An independent reviewer reproduces the branch, hash, allowlist, ancestry, tests, documentation, browser, whitespace, and no-scope-expansion evidence from a separate clean checkout and issues `ACCEPTED` with no Critical, High, or Medium finding.
15. Only after every required gate passes, explicit paths are staged, one descriptive commit is created, and the current tracking branch is pushed.

## Verification commands

Run `python scripts/query_docs.py --boot-snapshot` first. Query the registered commands before tests:

```powershell
python scripts/query_docs.py --test-command resident_agent
python scripts/query_docs.py --test-command codex-control-centre
python scripts/query_docs.py --test-command coding-cockpit
```

The following are the WP-UI-00 minimum gates. Repository-documented equivalents may replace them only when the exact replacement is recorded in the delivery report.

```powershell
# Ancestry and clean start
git merge-base --is-ancestor 6256fc5d25e3ad5c2f60d739c24446ebc4df3546 HEAD
git merge-base --is-ancestor 170f6f7eb62278bc029d39caaeda8637d4c99c59 HEAD
git status --short

# P0 application boundary
.\.venv\Scripts\python.exe -m pytest tests/test_resident_agent.py tests/test_codex_backend_mount.py tests/test_admin_support_tickets.py -k "not stress_fuzzer" -v

# Control Centre security and one-use events (run from codex-control-centre)
..\.venv\Scripts\python.exe -m pytest tests/test_security.py tests/test_events.py -v

# Canonical cockpit P0 contracts (run from frontend)
node --experimental-strip-types --test src/pages/admin/coding-cockpit/coding-cockpit.test.ts
npm test
npm run build

# Import/compile and migration graph; WP-UI-00 changes no migration
.\.venv\Scripts\python.exe -m py_compile app/api/routers/admin_support_tickets.py app/api/routers/resident_agent.py app/main.py app/services/resident_agent/skill_library.py codex-control-centre/backend/middleware/auth.py codex-control-centre/backend/routers/events.py codex-control-centre/backend/routers/turns.py codex-control-centre/backend/services/sse_tickets.py
.\.venv\Scripts\python.exe -c "from app.main import app; assert app is not None"
.\.venv\Scripts\alembic.exe heads

# Living documentation
python scripts/verify_living_docs.py --path docs/architecture/README.md
python scripts/verify_living_docs.py --path codex-control-centre/README.md
python scripts/verify_living_docs.py --path frontend/src/pages/admin/coding-cockpit/README.md

# Mandatory browser gate using the exact audited local application listeners
python scripts/verify_zero_console_errors.py

# Change control: validate all changed paths except the twelve exact immutable evidence files
$immutableEvidenceExclusions = @(
  ':(exclude)artifacts/codex-supervisor/CCC_ARCHITECTURE_BLUEPRINT.md',
  ':(exclude)artifacts/codex-supervisor/CCC_SECURITY_BASELINE.md',
  ':(exclude)artifacts/codex-supervisor/CCC_UX_CONTRACT.md',
  ':(exclude)artifacts/codex-supervisor/CCC_EXISTING_UI_AUDIT.md',
  ':(exclude)artifacts/codex-supervisor/CCC_UI_API_CONTRACT_INVENTORY.md',
  ':(exclude)artifacts/codex-supervisor/CCC_COPILOTKIT_FIT_ASSESSMENT.md',
  ':(exclude)artifacts/codex-supervisor/CCC_CODEX_BRIDGE_FIT_ASSESSMENT.md',
  ':(exclude)artifacts/codex-supervisor/CCC_CODEX_WEB_LOCAL_FIT_ASSESSMENT.md',
  ':(exclude)artifacts/codex-supervisor/CCC_OPEN_WEBUI_FIT_ASSESSMENT.md',
  ':(exclude)artifacts/codex-supervisor/CCC_ASSISTANT_UI_FIT_ASSESSMENT.md',
  ':(exclude)artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md',
  ':(exclude)artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_REVIEW.md'
)
git diff --check 170f6f7eb62278bc029d39caaeda8637d4c99c59...HEAD -- . $immutableEvidenceExclusions
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git status --short
git diff --stat 170f6f7eb62278bc029d39caaeda8637d4c99c59...HEAD
git diff --name-only 170f6f7eb62278bc029d39caaeda8637d4c99c59...HEAD
```

The exclusion list above is closed. Do not use `--ignore-space-at-eol`, `--ignore-all-space`, `core.whitespace` overrides, formatter exemptions, wildcard exclusions, or any other blanket waiver. The brief, ADR, architecture README, documentation index, and both changed module READMEs remain fully subject to `git diff --check`. Any unexpected changed path is also checked because `.` is the inclusive pathspec.

After the candidate commit exists, run this additional immutable-evidence verifier from each clean Windows candidate worktree. Run it once after checkout with `core.autocrlf=true` and once with `core.autocrlf=false` where both modes are available. It verifies the byte-authoritative committed blobs and permits only CRLF-to-LF conversion when comparing each worktree file with its blob:

```powershell
@'
from pathlib import Path
import hashlib
import subprocess

base = Path("artifacts/codex-supervisor")
manifest = {
    "CCC_ARCHITECTURE_BLUEPRINT.md": "39D253F745FD2F5D2B823432D4A7136F0A146A2D474AD02D69846ABFDE58AAE2",
    "CCC_SECURITY_BASELINE.md": "3C276CEF1632F72A02CB72A82CB59DDF582B85FD61A7727C2AB6B3873FD28331",
    "CCC_UX_CONTRACT.md": "3A9265F1626AF26528002E082D6FF3828710390C9F3B68031D820DC384F1B56F",
    "CCC_EXISTING_UI_AUDIT.md": "AF9A7C7E21BC1AC9B03CC1054D779E659FC277FFB9EB184BB0C79F20BFC0155B",
    "CCC_UI_API_CONTRACT_INVENTORY.md": "05E99F56847F20D7D62A5B6C1DD30BFDFCE4176D29DFDE3B2776CAAFCB05E51B",
    "CCC_COPILOTKIT_FIT_ASSESSMENT.md": "CC273088E7A517A1C88291CD0CFD33144C46A2A1AE62BF66B84253875C77B1B4",
    "CCC_CODEX_BRIDGE_FIT_ASSESSMENT.md": "F524D3F14A7C86D95889E6FF3C0E4B6623D35A496EF7DF4FE6EDE979336D2E6B",
    "CCC_CODEX_WEB_LOCAL_FIT_ASSESSMENT.md": "DAC9C0286B549C8621D9F24B41411365F8487970FF2A7E0EF43F78B2ECFC01B3",
    "CCC_OPEN_WEBUI_FIT_ASSESSMENT.md": "3DF9F267A772F6B2DCA6969120FA12B9A62FD9B7E984E684FA3382908C489A18",
    "CCC_ASSISTANT_UI_FIT_ASSESSMENT.md": "4C736351A9165F5BED5477980CC8234A611465C6638CD6178DF73F4636AC8D53",
    "CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md": "CF9DB16A10D51AE3EE09949C63456A42981DD92007A4DB53C654343B93ED0D29",
    "CCC_SUPERVISOR_UI_FOUNDATION_REVIEW.md": "B528B722FC5FCEF819320BB895732F9B52759AAF7868886DD2435BC0ABC706B9",
}

failures = []
for name, expected_blob_sha256 in manifest.items():
    path = base / name
    relative = path.as_posix()
    blob_result = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        capture_output=True,
        check=False,
    )
    if blob_result.returncode != 0:
        failures.append(f"{relative}: not tracked at HEAD")
        continue
    committed_blob = blob_result.stdout
    actual_blob_sha256 = hashlib.sha256(committed_blob).hexdigest().upper()
    if actual_blob_sha256 != expected_blob_sha256:
        failures.append(f"{relative}: committed-blob SHA-256 mismatch")
    worktree_bytes = path.read_bytes()
    worktree_lf = worktree_bytes.replace(b"\r\n", b"\n")
    if worktree_lf != committed_blob:
        failures.append(
            f"{relative}: worktree differs from committed blob after CRLF-to-LF conversion"
        )

if failures:
    raise SystemExit("Immutable evidence verification failed:\n" + "\n".join(failures))
print(
    f"Immutable evidence verified: {len(manifest)} committed blobs match the manifest; "
    "worktree files match after CRLF-to-LF conversion only"
)
'@ | .\.venv\Scripts\python.exe -
```

Also run the two known legacy stress-fuzzer tests separately and report their result. They were pre-existing non-blocking debt at P0 because they use global `SessionLocal` rather than the injected test database. Do not hide, repair, or broaden into that debt in WP-UI-00; any new or changed failure is blocking.

After the candidate commit is created, reproduce all applicable gates from a newly created clean detached worktree at that exact commit. Verify required artifacts with `git ls-tree -r --name-only HEAD`, verify no ignored/untracked file is needed, and confirm final `git status --short` is empty.

## Independent audit criteria

The reviewer must be independent of the implementation agent and must audit the exact candidate commit from a separate clean checkout. The review is criterion-by-criterion and must include:

- ancestry and exact commit identity;
- full changed-file allowlist comparison;
- immutable-evidence verification against the approved byte-authoritative committed-blob manifest, with worktree equality after CRLF-to-LF conversion only in fresh Windows `core.autocrlf=true` and `core.autocrlf=false` checkouts;
- confirmation that scoped `git diff --check` excluded only the twelve exact immutable-evidence paths and passed for every mutable or unexpected changed path;
- confirmation that no blanket whitespace waiver, formatter rewrite, line-ending normalization beyond the verifier's CRLF-to-LF comparison, or extra exclusion was used;
- P0 behavior and negative authorization/privacy cases;
- no default/query credentials, ticket reuse, raw prompt/PII/secret leakage, fabricated dispatch success, or ordinary-tenant-admin authority;
- canonical frontend and legacy freeze consistency;
- v2 namespace, Mission terminology, idempotency, cutover, 72-action registry, event, bounded disclosure, project claim, worker ownership, recovery, and external-reference decisions;
- explicit proof that proposed v2 contracts are not represented as implemented;
- no migration/dependency/runtime/UI expansion;
- test/build/browser/living-doc evidence tied to the candidate commit;
- clean-checkout reproduction and clean final worktree.

Any Critical, High, or Medium finding rejects the package and returns it for rebrief/rework. A conditional acceptance may not be committed or pushed as completion.

## Rollback and recovery

WP-UI-00 performs no migration and enables no v2 runtime behavior. Before merge, rollback is abandoning the dedicated branch/worktree while retaining the pushed P0 branch and Anti-Gravity audit trail. After merge, documentation-only WP-UI-00 changes may be reverted with an ordinary reviewed revert commit.

Do not silently revert P0 security controls. If P0 itself must be withdrawn, stop release and obtain explicit owner/security approval for a separate revert brief that preserves a safe disabled state and documents the resulting exposure. Never use reset, force-push, or branch deletion as rollback.

## Commit, push, and delivery report

After all gates and independent acceptance pass:

1. run final `git status --short`, `git diff --stat`, allowlist comparison, and `git diff --check`;
2. stage only the explicit allowlist paths—never `git add .` or `git add -A`;
3. commit with a message such as `docs(codex): freeze supervisor v2 foundation contracts`;
4. push `codex/codex-supervisor-wp-ui-00` to its current approved tracking branch;
5. update Anti-Gravity task `ccc_wp_ui_00` with final status and concise execution logs;
6. report commit hash, push confirmation, changed files, commands/results, independent reviewer verdict, artifact hashes, and known limitations.

WP-UI-01 remains a separate, owner-authorized task after WP-UI-00 acceptance.
