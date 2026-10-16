# Codex Web Local Fit Assessment for the Integrated Codex Supervisor

**Assessment date:** 15 October 2026  
**Decision:** **REJECT**  
**Target:** the integrated `F:\Projects\fastapi_bookings\codex-control-centre` and the ground-up supervisor UI in the canonical FastAPI Bookings frontend  
**Scope:** read-only architecture and security assessment. `codex-web-local` was not cloned, installed, executed, copied, or added as a dependency. No application code or existing specification was changed.

## Executive verdict

Reject `pavel-voronin/codex-web-local` as a dependency, replacement, UI foundation, runtime adapter, remote-access service, or implementation spike for FastAPI Bookings.

The repository is a small personal Codex web wrapper, not a development-supervisor platform. GitHub records it as archived and read-only since 3 April 2026. It has six commits, package version `0.1.0`, no security policy, no documented release/compatibility programme, and no future path for adapting to Codex app-server protocol changes. Its public contract offers either a single shared password or `--no-password`, including a stated remote-browser use case. Neither mode satisfies native FastAPI identity, platform-owner authorization, object ownership, durable approvals, audit, or multi-tenant isolation.

It also adds no meaningful capability that the integrated Control Centre does not already possess. The local system already starts Codex app-server workers, manages isolated worktrees, normalizes events, persists threads/turns/items/approvals, and exposes a same-origin React surface. The approved v2 architecture adds the missing mission, brief, assignment, evidence, independent-audit, acceptance, and Project Brain layers. A Desktop-style Vue web clone would bypass rather than advance that design.

Unlike the `codex-bridge` assessment, this is not `REFERENCE ONLY` as an architectural component. Codex Bridge contains several mature operational ideas worth independent reimplementation. `codex-web-local` offers only general cautionary lessons already covered by P0 and the v2 specification. It should be recorded as a rejected alternative and left off the implementation critical path.

## Repository facts reviewed

The public repository and package metadata establish:

- GitHub archived the repository at the owner's request on 3 April 2026; it is read-only.
- The repository contains six commits and identifies one author in its package metadata.
- The published package is version `0.1.0` and requires Node.js 18 or newer.
- The production server dependencies are Express `^5.1.0` and Commander `^13.1.0`.
- The frontend is Vue 3/Vue Router with Vite 6, Tailwind 4, TypeScript 5.7, `tsup`, and associated build dependencies.
- The lockfile is present and uses integrity hashes, but the package manifest has no test, lint, security, conformance, or audit script.
- The documented execution paths are `npx codex-web-local` and a global npm installation.
- Password protection is enabled by default with an auto-generated password printed to the console; callers may provide a password or disable password protection completely.
- The stated product purpose is to replicate the Codex desktop UI and expose a local Codex instance remotely from a browser.
- The repository uses the MIT licence.
- GitHub reports no `SECURITY.md` and no published security advisories. Absence of advisories is not evidence of absence of vulnerabilities, especially for an archived six-commit project.

No claim is made here about unreviewed internal cryptography, session-cookie attributes, origin checks, CSRF protection, rate limiting, WebSocket authorization, or process shutdown. The public README does not document those controls, and the task deliberately prohibited cloning or copying the source for deeper testing.

## Architectural comparison

| Concern | Integrated CCC and approved v2 | `codex-web-local` | Decision |
|---|---|---|---|
| Product model | Mission -> brief -> assignment -> run -> evidence -> independent audit -> decision -> checkpoint | Desktop-style Codex conversation clone | Fundamentally different; cannot replace the supervisor. |
| Backend ownership | FastAPI-mounted Control Centre with native database, worker manager, worktrees, governance, and planned v2 facade | Separate Node/Express wrapper over Codex app-server | Duplicates and bypasses the native boundary. |
| Browser ownership | One canonical React application and same-origin authenticated transport | Separate Vue/Vite application | Do not add a duplicate frontend or framework island. |
| Authentication | Accepted P0: native platform-owner authority and header credentials; v2 adds actor/object scope | Shared password or no-password mode | Incompatible and unsafe for the required authority model. |
| Authorization | Platform-owner first, then durable actor/project/mission/run binding and non-leaking denials | No documented user, tenant, project, run, or action authorization | Cannot protect supervisory or host-level actions. |
| Persistence | Control DB plus planned durable briefs, runs, evidence, audits, decisions, and checkpoints | No documented supervisor-domain persistence | Cannot preserve or prove work. |
| Execution isolation | Verified repository boundaries and isolated Git worktrees | Public README promises app-server access but no supervisor worktree contract | Must not become an execution path. |
| Events and recovery | Typed native snapshots plus ticketed SSE; durable v2 sequencing planned | No documented durable sequence, replay, gap, or restart contract | Protocol adapter is insufficient for supervisor recovery. |
| Protocol maintenance | Local checked-in schemas and an explicit compatibility-gate recommendation | Archived adapter with no ongoing compatibility programme | App-server drift will accumulate without remediation. |
| Auditability | Actor, revision, idempotency, evidence digest, reviewer independence, and audit lineage are binding requirements | Shared web access to a Codex session | Cannot support trustworthy acceptance. |
| Supply chain | Existing approved Python/React stacks under repository gates | Additional npm CLI/server plus a separate Vue build graph | Unjustified exposure for duplicated functionality. |

## Relationship to P0 and the native UI

The accepted P0 trust-boundary work establishes the opposite of `codex-web-local`'s access model:

- mounted Control Centre operations are platform-owner-only;
- native credentials are not accepted in query strings;
- browser event connections use short-lived, scoped, atomic one-use tickets;
- resident streams are authenticated;
- dispatch success requires real worker acknowledgement;
- failures remain failures rather than optimistic UI success.

A shared application password cannot stand in for those controls. A no-password mode is categorically incompatible, even on a “trusted” network: network location is not actor identity, resource ownership, approval authority, or protection against browser-origin mistakes and local lateral access.

The new UI is intentionally built from the ground up in the canonical React application. It is mission-first and evidence-first, not a clone of the Codex desktop conversation view. Importing a Vue web clone would reintroduce the exact duplicate shell, state, routing, component library, authentication, and build ownership that the foundation specification rejects.

P0 is a prerequisite, not a feature that can be placed in front of this package. Wrapping `codex-web-local` behind a FastAPI proxy would still leave two UI stacks and an unowned protocol adapter, while FastAPI would have to reconstruct every authorization and disclosure guarantee around it. At that point the package provides no useful leverage over the existing first-party worker.

## Relationship to Codex Bridge

Both projects sit below the supervisor domain as alternative Codex app-server clients with browser interfaces. Their maturity is materially different:

| Dimension | Codex Bridge | `codex-web-local` |
|---|---|---|
| Status | Active, pre-1.0, frequent releases | Archived/read-only |
| Depth | Rust daemon, typed protocol, rollout history, writer ownership, CLI, bounded file access | Lightweight Node/Express and Vue web clone |
| Operational concepts | Several worth independently reimplementing | No unique supervisor-relevant concept identified |
| Authentication posture | Homelab Basic/session or trusted loopback proxy; still incompatible | Shared password or no password; materially weaker |
| Maintenance evidence | Tests and release notes reported; still young | Six commits, no test script or compatibility programme documented |
| Assessment | `REFERENCE ONLY` | **REJECT** |

The Codex Bridge decision already recommends one first-party southbound app-server adapter, explicit writer ownership, bounded history, and no parallel daemon/browser authority. `codex-web-local` reinforces that decision but does not add a new design direction.

## Relationship to CopilotKit and AG-UI

CopilotKit/AG-UI occupies a different, optional northbound layer: a future gated projection of one already-authorized active run. Its assessment is `SPIKE FIRST`, subject to P0 ancestry, durable run ownership, strict safe-event schemas, and a native fallback.

`codex-web-local` is neither AG-UI nor a supervisor presentation adapter. It is an alternative full web client over app-server. It would expose the lower-level Codex conversation model directly and therefore compete with both the native v2 facade and the canonical UI.

The approved layering remains:

```text
Native mission / brief / assignment / evidence / audit control plane
                         |
         FastAPI v2 REST authority + ticketed SSE
                         |
             Canonical React supervisor UI
                         |
    optional bounded AG-UI presentation spike only
                         |
          first-party Codex app-server adapter
```

There is no place in that stack for a second archived Node/Vue app-server Web UI.

## Security risks

### Critical

1. **Alternate authority and browser surface.** Direct remote access to app-server would bypass native actor, project, mission, run, worktree, approval, and evidence authorization.
2. **No-password execution exposure.** An explicitly supported unauthenticated mode could expose a code-capable local agent to any reachable browser client if binding, firewall, proxy, or network assumptions are wrong.
3. **Shared-password ambiguity.** One password identifies neither a person nor a tenant and cannot create trustworthy attribution, separation of duties, or independent-review provenance.
4. **Raw disclosure risk.** A Desktop-style app-server UI may need raw messages, tools, paths, diffs, and output. Those classes are prohibited from crossing the supervisor v2 boundary without strict server-side redaction and bounds.

### High

5. **Archived protocol adapter.** Codex app-server is actively evolving. An archived April 2026 client cannot be expected to track October 2026 request, event, approval, schema, ownership, or security behavior.
6. **No supervisor domain.** It cannot preserve immutable briefs, evidence, audit decisions, checkpoints, or author/reviewer independence and could create the appearance of supervision from an ordinary chat transcript.
7. **Remote transport assumptions are underdocumented.** The README promotes remote browser access but does not document TLS, exact bind defaults, origin/CSRF controls, brute-force limits, session expiry, proxy trust, or credential rotation.
8. **Unmaintained npm supply chain.** `npx` executes a published package and resolves its bundled dependency tree; the archived project will not issue fixes for future Node, Express, Vue, Vite, or app-server incompatibilities.
9. **Duplicate runtime and UI.** A second Express process and Vue frontend add failure, patching, logging, asset, routing, accessibility, and shutdown responsibilities without a unique capability.

### Medium

10. **Console credential handling.** Printing an authentication secret to the console creates avoidable terminal-capture, support-log, screen-share, and process-output exposure risk.
11. **No documented automated assurance.** The package manifest contains build and publish scripts but no test, lint, protocol-conformance, browser-security, dependency-audit, or release-verification script.
12. **False confidence from MIT licensing.** The permissive licence answers reuse permission, not maintenance, security, provenance, compatibility, or operational suitability.

## Supply-chain and licence position

MIT licensing is compatible in principle, subject to preservation of the copyright and permission notice for copied or distributed substantial portions. This assessment recommends neither copying nor distribution, so it creates no new licence-notice obligation.

The package has a lockfile with registry integrity hashes, which is positive but insufficient. Direct manifest ranges use caret constraints, the npm package is invoked through `npx` or global install, and the archived maintainer will not review future vulnerabilities or compatibility regressions. No security policy, support window, signed release, SBOM, provenance statement, or maintained Codex compatibility matrix was identified in the reviewed public materials.

Because the functionality is duplicated locally, even a successful one-time audit would not justify assuming indefinite ownership of a fork and its transitive dependencies.

## Limited concepts worth retaining

No code or component should migrate. The following general lessons may be retained without source copying:

1. **Small app-server adapters are feasible.** The native worker interface should stay narrow rather than inheriting a whole external application.
2. **Unsafe modes must be explicit.** A no-auth option should be rejected entirely in the integrated application; development bypasses remain native, setting-gated, platform-owner-scoped, and tested.
3. **Remote access expands the threat model.** Any future remote supervisor access must use native HTTPS/session policy, exact origins, per-request authorization, audit attribution, and no direct app-server exposure.
4. **Simple onboarding is valuable.** Readiness should clearly report whether the Codex binary, app-server handshake, repository boundary, and worker are available—but without printing credentials or inventing success.
5. **Conversation rendering is a support detail.** Structured messages and tools can inform bounded Run Detail presentation, but they remain subordinate to mission, evidence, and audit state.

These are already embodied or more precisely specified by P0, the supervisor foundation, the CopilotKit/AG-UI assessment, and the Codex Bridge assessment.

## Specification impact

No existing specification should be amended for this repository. It introduces no accepted dependency, component, protocol, UI, state model, or spike.

At the next scheduled ADR/decision-register update, record only:

- `codex-web-local` is an archived rejected alternative;
- no shared-password or no-password app-server browser surface may run beside the canonical application;
- the browser must never call a third-party app-server wrapper directly;
- archived/unmaintained packages fail the privileged-dependency gate unless an explicit owner accepts a maintained fork and proves a unique capability—which is not justified here.

The Codex Bridge assessment's proposed “sole native worker adapter” and “third-party daemon/browser non-authority” amendments already cover the substantive architecture concern. No separate work package or proof of concept should be created.

## Revisit conditions

Do not revisit this archived repository itself. A successor project would require a fresh assessment and would need, at minimum:

- active maintenance and a documented security/contact policy;
- versioned Codex protocol compatibility and conformance tests;
- native FastAPI authentication and platform-owner/object authorization on every request;
- no unauthenticated mode and no shared-secret identity model;
- strict typed/redacted browser disclosure;
- Windows support and clean lifecycle ownership;
- a unique material capability absent from the first-party adapter;
- exact dependency pins, SBOM, licence inventory, vulnerability review, provenance, rollback, and independent security acceptance.

Meeting those conditions would qualify a different project for evaluation; it would not revive `codex-web-local` as a dependency.

## Final recommendation

**REJECT.** Keep `codex-web-local` out of the repository, runtime, UI, dependency graph, specifications, and implementation roadmap.

Continue the native sequence: integrate P0, implement durable mission/brief/checkpoint foundations, build the canonical ground-up supervisor UI, add explicit worker ownership and recovery to the first-party adapter, then implement commit-bound evidence and independent audit. Retain Codex Bridge only as a design reference and keep CopilotKit/AG-UI behind its already-defined future spike gate.

## Sources reviewed

### External primary sources

- [`pavel-voronin/codex-web-local` repository and README](https://github.com/pavel-voronin/codex-web-local)
- [`package.json`](https://github.com/pavel-voronin/codex-web-local/blob/main/package.json)
- [`package-lock.json`](https://github.com/pavel-voronin/codex-web-local/blob/main/package-lock.json)
- [MIT licence](https://github.com/pavel-voronin/codex-web-local/blob/main/LICENSE)
- [Security overview](https://github.com/pavel-voronin/codex-web-local/security)
- [Repository activity/actions surface](https://github.com/pavel-voronin/codex-web-local/actions)

### Local authoritative sources

- `codex-control-centre/README.md`
- `codex-control-centre/backend/services/worker.py`
- `codex-control-centre/backend/services/worker_manager.py`
- `codex-control-centre/backend/services/protocol.py`
- `codex-control-centre/backend/services/worktree_service.py`
- `codex-control-centre/backend/services/event_service.py`
- `codex-control-centre/backend/routers/turns.py`
- `codex-control-centre/backend/routers/events.py`
- `codex-control-centre/backend/middleware/auth.py`
- `artifacts/codex-supervisor/CCC_ARCHITECTURE_BLUEPRINT.md`
- `artifacts/codex-supervisor/CCC_SECURITY_BASELINE.md`
- `artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md`
- `artifacts/codex-supervisor/CCC_COPILOTKIT_FIT_ASSESSMENT.md`
- `artifacts/codex-supervisor/CCC_CODEX_BRIDGE_FIT_ASSESSMENT.md`

