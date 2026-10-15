# codex-control-centre Architecture Decision Records

- [Persisted Platform-Owner Authority](ADR_PLATFORM_OWNER_AUTHORITY.md) — sole
  cross-tenant authority bit, offline management, transactional audit, and
  last-active-owner protection.

## 1. Purpose & Scope

This directory records binding architectural decisions for FastAPI Bookings. It owns concise decision records that define system boundaries, terminology, authority, migration and rollback rules before implementation begins. Detailed product research and accepted design evidence remain in `artifacts/`; module implementation details remain in each module's living `README.md`.

It deliberately does not provide executable routes, database models, migrations, UI components, deployment configuration, or runtime feature flags.

## 2. Architecture & Key Files

- `ADR_CODEX_SUPERVISOR_V2_FACADE.md` freezes the Codex Supervisor v2 target and records the implemented WP-UI-01A-v6 five-route `0.1` project-claim foundation while keeping UI and activation work deferred.
- [`../../artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md`](../../artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md) is the detailed accepted source contract.
- [`../../artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_REVIEW.md`](../../artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_REVIEW.md) records its independent acceptance.

The central documentation catalog is [`../README.md`](../README.md). The current Control Centre and legacy cockpit contracts are documented in [`../../codex-control-centre/README.md`](../../codex-control-centre/README.md) and [`../../frontend/src/pages/admin/coding-cockpit/README.md`](../../frontend/src/pages/admin/coding-cockpit/README.md).

## 3. Setup, Configuration & Dependencies

Architecture records are Markdown and have no runtime dependency. They must be reviewed with the implementation brief and the repository `AGENTS.md`. A decision record may authorize a later work package, but it does not itself install a dependency, enable a route, alter a database, or relax an existing security boundary.

## 4. Core Workflows & Contracts

1. Record a decision and its current implementation status.
2. Link to the accepted source specification instead of duplicating its full detail.
3. Define ownership, authorization, concurrency, failure and rollback rules.
4. Implement the decision in a separately authorized package with focused tests.
5. Independently review the exact candidate commit before release.

WP-UI-01A-v6 implements only the migration/readiness/configured-project claim
slice. Readiness attests exact schema and migration state rather than object-name
presence. Claim validates the opaque route identity before reservation, applies
Git-equivalent branch validation, and uses a phase-two outer transaction with a
nested savepoint so deterministic failure can be terminalized without preserving
project or event writes. An indexed physical-root digest keeps identity lookup
bounded without scanning hidden rows. Hidden cross-scope rows are never counted
or classified and remain absence-equivalent on reads, while a targeted mutation
returns only 404.
Later packages remain responsible for the ground-up UI, supervisor domain
workflows, worker control, and active cutover.

## 5. Data Safety & Isolation

Architecture records must preserve tenant and actor isolation, avoid secrets and customer data, and use opaque identifiers in examples. Host paths, credentials, prompts, model bodies, source content and personal information must not be presented as browser contracts or telemetry fields. Authorization decisions are always server-side and fail closed.

## 6. Known Issues, Edge Cases & Outstanding Work

- The five-route v2 claim foundation is implemented; the replacement UI, writable cutover transition, and broader supervisor domain are not.
- The current cockpit remains the operational v1 interface during the controlled cutover.
- The closed action registry and future OpenAPI mutation mapping require conformance tests when implemented.
- Optional presentation adapters remain blocked until the durable native run contracts and comparative spike prerequisites are accepted.

## 7. Verification & Testing Commands

```powershell
.\.venv\Scripts\python.exe -m pytest codex-control-centre/tests/test_security.py codex-control-centre/tests/test_events.py -v
python scripts/verify_living_docs.py --path docs/architecture/README.md
python scripts/query_docs.py --search "Codex Supervisor v2 facade"
git diff --check
```
