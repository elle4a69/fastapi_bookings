# Development Supervisor V2 UI

## Purpose & Scope

This is the ground-up, read-only V2 Development Supervisor at
`/admin/coding-cockpit-v2`. It reads the native Control Centre V2 planning
facade; it does not replace the legacy coding cockpit or execute work.

## Architecture & Key Files

- `SupervisorPage.tsx` owns URL-backed view and selection loading.
- `api.ts` is the only V2 transport adapter and targets `/api/admin/codex/v2`.
- `SupervisorShell.tsx`, `SupervisorNav.tsx`, and panels render live state.
- `routeState.ts` preserves Overview, Missions, Context, mission and package
  selection in the URL.

## Setup, Configuration & Dependencies

The normal frontend requires its installed Vite/React dependencies. The page
requires a real signed-in administrator JWT and a valid tenant subdomain from
the browser hostname. It deliberately rejects the generic frontend's localhost,
tunnel, and `simplydemo` development fallbacks.

## Core Workflows & Contracts

Only read operations are made: bootstrap, readiness/project discovery,
missions, mission details, work packages, briefs, context checkpoints, and
audit scope. All API responses use the V2 envelope and ETags. The fixed server
cutover remains `v1_only`; no form, approval, dispatch, execution, evidence,
or audit-verdict action exists here.

## Data Safety & Isolation

The browser never supplies actor, user, or scope identity. It only sends the
existing trusted admin token and hostname-derived tenant context when both are
present. Missing context renders an honest unavailable state instead of a
fallback identity or demo data. Brief metadata about a future one-run waiver is
informational only and grants no authority.

## Known Issues, Edge Cases & Outstanding Work

The UI is intentionally read-only. Future packages may add controlled planning
mutations, execution dispatch, proof capture, and independent audit outcomes
only after separate approval and contracts. A local developer host will show
the sign-in/context state until an actual tenant-scoped session is available.

## Verification & Testing Commands

```powershell
cd frontend
node --experimental-strip-types --test src/pages/admin/codex-supervisor/supervisor.test.ts
npm test
npm run build
python ..\scripts\verify_zero_console_errors.py --url http://localhost:7070 --routes /admin/coding-cockpit-v2
python ..\scripts\verify_living_docs.py --path src/pages/admin/codex-supervisor/README.md
```
