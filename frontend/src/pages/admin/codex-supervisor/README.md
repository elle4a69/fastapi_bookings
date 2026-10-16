# Development Supervisor V2 UI

## Purpose & Scope

This is the ground-up V2 Development Supervisor at
`/admin/coding-cockpit-v2`. It provides mission-first planning, active-run
management, and fail-closed structural evidence audit surfaces. It consumes
the native Control Centre V2 supervisor facade without fake progress, simulated
terminals, or unverified runtime states.

## Architecture & Key Files

- `SupervisorPage.tsx`: Owns URL-backed navigation, selection loading, mutation
  epochs, active-run lifecycle transitions, and evidence matrix state.
- `api.ts`: V2 transport adapter targeting `/api/admin/codex/v2`. Manages
  idempotent planning mutations, acceptance contract creation, one-run start
  authorizations, durable worker dispatch intents, and independent audit requests.
- `ActiveRunManager.tsx`: Active-run management card providing owner-confirmed
  "Request One-Run Authorization", single-use 120s credential tracking, real-time
  run lifecycle tracking (`grant_requested` -> `authorized` -> `dispatching` ->
  `running` -> `completed` / `failed`), `dispatch_unknown` warnings, and explicit
  `sandbox_unavailable` handling.
- `EvidenceAuditCard.tsx`: Structural Evidence & Audit Matrix Card displaying Git
  facts (Baseline Tree SHA, Submitted Tree SHA, Changed Files count, Line
  insertions/deletions), Test Evidence & Criteria Matrix (`repository_bound`,
  `baseline_captured`, `sandbox_attested`, `tests_passed`), and an actionable
  "Promote to Release Branch" button enabled strictly when all criteria pass.
- `SupervisorShell.tsx`, `SupervisorNav.tsx`: Clean application chrome and
  navigation header displaying configured project and supervisor status.
- `PlanningForms.tsx`: Accessible, explicitly-confirmed forms for missions,
  work packages, briefs, checkpoints, and audit scopes.
- `routeState.ts`: Preserves Overview, Missions, Context views, and selections
  in the browser URL search params.
- `types.ts`: Type definitions for envelopes, planning records, runs, start
  authorizations, acceptance contracts, audit requests, and structural evidence.

## Setup, Configuration & Dependencies

The frontend requires standard React/Vite dependencies. The V2 supervisor requires
a real signed-in platform-owner JWT and a tenant subdomain in the browser
hostname. Missing session or tenant context renders an honest unavailable state
without fallback demo fixtures.

## Core Workflows & Contracts

1. **Planning Lifecycle**: Missions, work packages, briefs, checkpoints, and
   audit scopes are created with UUIDv4 idempotency keys and parent ETag version
   matching (`If-Match`). Draft briefs are immutable once approved.
2. **One-Run Authorization**: An approved brief unlocks "Request One-Run
   Authorization". The server creates a single-use, hash-bound start authorization
   grant (`sag_...`) expiring in 120 seconds. The raw token is returned once to
   active browser memory and is never logged or rendered to the DOM.
3. **Durable Worker Dispatch**: The operator initiates dispatch with the grant
   token. The server atomically commits the run intent and baseline Git tree
   digest before attempting external app-server worker launch. Unknown launch
   outcomes map to `dispatch_unknown` to prevent double-dispatch.
4. **Independent Evidence & Audit**: The operator requests an independent audit.
   When an isolated execution sandbox is not configured, the server records an
   honest `sandbox_unavailable` state.
5. **Release Promotion Gate**: The "Promote to Release Branch" button is enabled
   if and only if every criterion in the matrix (`repository_bound`, `baseline_captured`,
   `sandbox_attested`, `tests_passed`) has an evaluated `passed` outcome.

## Data Safety & Isolation

- Zero raw prompts, secrets, grant tokens, or internal worker transcripts are rendered.
- Zero fake progress or mock terminal spinners: all status transitions correspond
  to real server-returned ledgers or deterministic browser state transitions.
- Client credentials and tenant boundaries are strictly isolated via platform owner
  checks and `X-Tenant` headers.

## Known Issues, Edge Cases & Outstanding Work

- The current release package records `sandbox_unavailable` for independent audit
  requests because host-enforced sandboxes require separate isolation daemon
  configuration.
- Because `sandbox_attested` requires an attested sandbox, the "Promote to Release
  Branch" button remains safely locked until an attested sandbox confirms all
  evaluation criteria.

## Verification & Testing Commands

```powershell
cd frontend
node --experimental-strip-types --test src/pages/admin/codex-supervisor/supervisor.test.ts
npm test
npm run build
npx tsc --noEmit
python ..\scripts\verify_living_docs.py --path src/pages/admin/codex-supervisor/README.md
```
