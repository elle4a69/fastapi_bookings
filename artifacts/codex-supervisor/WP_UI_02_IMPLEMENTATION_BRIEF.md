# WP-UI-02 — V2 Development Supervisor UI shell

## Objective

Deliver the first ground-up, production read-only React surface for the native
Codex V2 supervisor facade at `/admin/coding-cockpit-v2`.  It is a parallel
route: the legacy coding cockpit, its redirects, and the duplicate Control
Centre frontend remain untouched.  The persisted cutover remains `v1_only`.

## API and authority boundary

The shell consumes only `/api/admin/codex/v2`.  Its adapter uses the existing
signed-in admin JWT supplied by `getAdminAccessToken()` and the existing
tenant context header convention.  It never manufactures identity, reads an
actor/scope value from URL, storage, or request body, and has no demo, local,
tunnel, or anonymous fallback.  If those established primitives are absent,
the UI presents an honest sign-in/configuration state and makes no request.

Only server responses provide projects, missions, work packages, briefs,
checkpoints and audit scope.  Unit tests may mock `fetch` transport responses
to verify the adapter but do not introduce demo entities or a fake domain
store.

## User interface

The page header identifies **Development Supervisor**, the configured project
when the API reports one, API freshness, refresh control, and a visible
`Planning only — no execution` boundary.  URL-backed navigation supports
Overview, Missions, and Context.  Selection is retained in query parameters
and is therefore reload/link safe.  The UI represents loading, sign-in,
configuration, migration/readiness, access, empty, API-error and unavailable
states without pretending data exists.

Mission detail reads the selected mission, its work packages, each selected
work package's briefs and audit scope, and the selected mission's checkpoints.
The `future_execution_authorization_requirement` shown on a brief is plainly
described as future planning metadata: a requested one-run waiver grants no
execution authority in this release.  WP-UI-02 adds no form, approval,
mutation, dispatch, worker, shell, Git, evidence, or audit-verdict control.

## Implementation controls

The adapter normalizes the existing `{data,meta}` and `{error,meta}` envelopes,
retains response ETags, sets `Cache-Control` policy server-side only, and
uses `AbortController` and sequence guards so stale responses cannot repaint
the shell.  It exposes safe error states, but not credentials or response
details that could be sensitive.

## Allowlist

Only these paths may change: this brief; `frontend/src/App.tsx`; files under
`frontend/src/pages/admin/codex-supervisor/` named by WP-UI-02; the listed
frontend and docs READMEs/catalogues.  The admin layout is not changed unless
needed to make the route render correctly.  No backend, legacy cockpit,
duplicate Control Centre frontend, or booking-domain path is in scope.

## Verification

Run the focused frontend tests, production build, the repository zero-console
gate against the intended V2 route, the module living-documentation gate, and
a changed-file allowlist review.  This work package does not alter server API
contracts or cutover state.
