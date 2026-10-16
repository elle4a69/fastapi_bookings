# WP-UI-03 — Planning Workflow Forms

## Outcome

Add an authenticated, tenant-safe planning workflow to the existing native V2
Development Supervisor at `/admin/coding-cockpit-v2`. The UI creates missions,
work packages, immutable briefs, context checkpoints, and audit scopes, and may
approve a draft brief through the existing V2 API.

## Fixed boundaries

- The only server contract is `/api/admin/codex/v2`; no backend, migration,
  legacy cockpit, duplicate Control Centre frontend, dependency, or API-contract
  change is in scope.
- Mutations send the server-required action metadata, `confirmation: true`, a
  UUID idempotency key, and the fresh parent/resource ETag through the dedicated
  V2 adapter. The browser never supplies actor, user, project, or tenant identity
  in a request body.
- Inputs are bounded before submission and rendered as text only. User-facing
  failure messages are mapped by code/status and never display raw server data.
- Brief authorization metadata remains inert planning metadata. The UI must say
  it grants no authority in this release; it does not create a run, dispatch,
  worker, tool grant, evidence, verdict, or active bypass.

## Verification

Focused adapter/UI tests, full frontend tests, TypeScript/Vite build, controlled
zero-console/network check, living documentation validation, and a changed-file
review are required before handoff. No commit or push is authorised in this work
package.
