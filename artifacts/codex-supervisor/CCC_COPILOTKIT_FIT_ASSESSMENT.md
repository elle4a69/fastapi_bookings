# CopilotKit / AG-UI Fit Assessment for the Codex Supervisor UI

**Assessment date:** 15 October 2026  
**Decision:** **SPIKE FIRST**  
**Scope:** Read-only architecture assessment. No packages were installed, no services were started, and no application or specification files were modified.

## Executive decision

CopilotKit should **not** become the foundation, application shell, state store, approval authority, or durable control plane for the ground-up Codex Supervisor UI.

A small, gated proof-of-concept is justified to determine whether **AG-UI 1.0 plus CopilotKit v2 headless components** can add value as a narrowly bounded **active-run transport and presentation adapter**. The existing supervisor design remains authoritative:

- FastAPI owns identity, authorization, tenant/user scope, missions, work packages, brief revisions, assignments, runs, evidence, approvals, audit, checkpoints, and idempotency.
- The main Vite/React application remains the only production frontend.
- REST snapshots remain authoritative.
- The supervisor's ticketed SSE channel remains the passive invalidation/attention channel.
- TanStack Query remains the intended server-state cache; CopilotKit must not replace it.

The likely adoption outcome, if the spike succeeds, is **ADOPT NARROWLY**. Failure of any security, durability, privacy, reconnect, or operational-cost criterion means **REJECT the CopilotKit runtime** and retain the native REST/SSE architecture. AG-UI may still be retained as an internal normalization schema if it proves independently useful.

## The important distinction: the linked Codex page is not a runtime integration

The user-linked [Build with agents](https://docs.copilotkit.ai/build-with-agents) page describes **development-time assistance for coding agents**. Its Codex instructions add CopilotKit's documentation MCP server so Codex can retrieve current CopilotKit guidance and generate code with better context. The referenced skills are similarly thin documentation lookup instructions.

That page does **not** install CopilotKit into the application, connect the resident Codex supervisor to a runtime, add an AG-UI transport, provide authentication, or create durable agent threads. It may help an external coding agent implement a later approved spike, but it confers no runtime capability on FastAPI Bookings.

Runtime adoption is a separate architectural choice involving some combination of:

- CopilotKit React packages, preferably the v2 headless exports;
- a Copilot Runtime service or a deliberately direct AG-UI client;
- an AG-UI-compatible agent endpoint;
- explicit authentication, authorization, persistence, reconnect, and privacy controls.

## Local architecture fit

### What already fits

The canonical frontend is a Vite 8 / React 19 / TypeScript 6 application. Current `@copilotkit/react-core` metadata declares React 18 and 19 peer compatibility, and the official [React SPA quickstart](https://docs.copilotkit.ai/react-spa) explicitly supports a Vite SPA with a separately hosted runtime URL. The UI can therefore consume CopilotKit or AG-UI packages in principle.

The supervisor foundation specification already establishes the boundaries a safe integration needs:

- a centralized authenticated API client;
- server-authoritative REST snapshots;
- event clients that hold only connection, sequence, and invalidation state;
- bounded reconnect with fresh one-use SSE tickets;
- durable, exact idempotency for mutations;
- platform-owner-only access until ownership and isolation are proven;
- durable approval records and explicit evidence/audit provenance;
- strict disclosure limits for prompts, reasoning, commands, paths, diffs, logs, secrets, and PII.

These boundaries are compatible with an adapter, but not with handing the control plane to a generic conversational UI framework.

### What does not fit without new work

The current primary checkout's CCC models and routes do not yet provide the complete durable mission/run/ownership model required by the supervisor specification. Its existing event broker is in-memory, keeps a bounded history, uses schema `1.0`, and does not make event sequence durable. Existing worker normalization includes raw or high-risk fields such as reasoning chunks, commands, stdout/stderr, working directories, paths, and diffs. Those events must never be forwarded directly to a supervisor browser or vendor service.

The reviewed P0 trust-boundary branch adds the correct direction—FastAPI platform-owner enforcement and short-lived, project/thread-scoped, atomic single-use SSE tickets—but this assessment does not treat that work as integrated into the current primary checkout. A spike must not begin until its P0 ancestry and the required v2 durable backend primitives are proven in the spike branch.

The duplicate `codex-control-centre/frontend` is a reference/decommission candidate, not an adoption target. All proof work belongs in the canonical top-level `frontend` and the FastAPI-owned v2 facade.

## Supported deployment choices

### 1. Supported open-source CopilotKit path

The documented open-source path is:

```text
Vite React browser
    -> Node.js 20+ Copilot Runtime (Express or Hono)
    -> authenticated FastAPI AG-UI adapter / agent endpoint
    -> durable supervisor domain and Codex worker
```

The [Copilot Runtime documentation](https://docs.copilotkit.ai/langgraph-python/copilot-runtime) states that the TypeScript runtime is the default and most complete runtime, and the only runtime option usable without CopilotKit Intelligence. It can be hosted in Express, Hono, Next.js, or another JavaScript server; **Next.js is not required**, but a separate Node runtime is.

For FastAPI Bookings, that extra runtime is an operational and security cost: another process, dependency tree, authentication boundary, failure mode, deployment artifact, and upgrade stream. It is acceptable for a disposable spike, but must earn its place before production adoption.

### 2. Embedding CopilotKit's Python runtime in FastAPI

This is not a standalone open-source equivalent to the TypeScript runtime. The official runtime matrix says Python, Go, Ruby, and .NET runtime paths require a CopilotKit Intelligence project and server key and do not offer the TypeScript runtime's local in-memory/SQLite runner. It is therefore unsuitable as the default architecture for this repository.

### 3. Direct browser-to-FastAPI AG-UI

A browser can use the vendor-neutral AG-UI client directly against a FastAPI endpoint, with FastAPI retaining full auth and state ownership. This avoids the Node proxy and is the lowest-risk way to evaluate the **protocol**.

It is not the same as adopting the complete CopilotKit runtime. CopilotKit's `agents__unsafe_dev_only` direct mode is explicitly development-only. Its production `selfManagedAgents` path is associated with the Enterprise Intelligence offering in the [self-managed agents documentation](https://docs.copilotkit.ai/llamaindex/backend/self-managed-agents). A direct production implementation would therefore be a first-party AG-UI integration whose routing, authentication, persistence, and recovery are owned by FastAPI Bookings.

## Required trust boundaries

### Authentication and platform-owner propagation

The browser must send its ordinary FastAPI Bookings bearer/session credential in an authorization header, never in a query string or SSE URL. The [CopilotKit authentication guidance](https://docs.copilotkit.ai/auth) requires authentication on every runtime request and warns against trusting a user identity supplied by the request itself.

If the Node runtime is evaluated:

- its request hook must reject missing or invalid authentication before routing;
- it may forward only an explicit header allowlist, normally `Authorization` plus a low-cardinality correlation identifier;
- it must not trust or forward browser-supplied `x-user`, `x-tenant`, `x-role`, project, or ownership assertions;
- permissive default CORS must be disabled and replaced with the exact application origins;
- FastAPI must independently reauthenticate and require platform-owner access on every agent/run request;
- FastAPI remains the final authorization authority even if the Node layer also verifies the token.

No stable actor, tenant, role, or platform-owner claim may be derived from AG-UI state, CopilotKit properties, forwarded props, a thread ID, or browser-local state.

### Tenant, user, thread, and run ownership

AG-UI `threadId` and `runId` values are untrusted selectors. FastAPI must resolve them to server-owned mission, assignment, run, and actor records and verify access on every read, stream, mutation, resume, and approval operation. Guessed or cross-scope identifiers must use the supervisor specification's non-leaking denial behavior.

CopilotKit thread persistence, if ever enabled, is at most a projection with opaque correlation IDs. It must never become the source of truth for a mission, brief, assignment, approval, evidence record, audit entry, or checkpoint.

### Two different streaming channels

The existing supervisor SSE design and an AG-UI run stream solve different problems and must remain separate:

| Channel | Purpose | Authentication | Reconnect semantics |
|---|---|---|---|
| Supervisor v2 SSE | Passive durable invalidation and attention notices | Short-lived, one-use, scoped ticket | Mint a fresh ticket for every connection; resume after last durable sequence; REST refetch on a gap |
| AG-UI active run stream | Events for one already-authorized run | Authenticated POST, normally via `Authorization`; no query bearer | Reattach to the same durable run, or refetch its REST snapshot; never silently dispatch another run |

The P0 one-use GET ticket must not be reused as an AG-UI credential, converted to a reusable bearer, or forwarded through a query string. A dropped active stream is an unknown transport outcome, not permission to repeat a mutation. The client must check the durable run record and reuse the original idempotency key before any retry.

### Event normalization and disclosure

[AG-UI](https://github.com/ag-ui-protocol/ag-ui) supplies a useful typed lifecycle: run boundaries, messages, tools, state, activities, interrupts, and sub-agent events. It does not make the underlying business state durable or safe by itself.

The adapter should expose only a strict, versioned subset:

| Supervisor fact | Permitted AG-UI projection |
|---|---|
| Durable run began/ended/failed | `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR` |
| Bounded, redacted progress | `ACTIVITY_SNAPSHOT` / `ACTIVITY_DELTA`, or a namespaced validated custom event |
| Explicitly disclosure-safe assistant summary | Text message lifecycle events |
| Durable interrupt is waiting | Interrupt view data containing opaque action reference, exact version, risk and expiry |
| Durable sub-agent assignment | Sub-agent event containing opaque assignment/run references and safe status only |

The adapter must prohibit:

- raw reasoning or chain-of-thought;
- prompts or model request/response bodies;
- raw worker events or AG-UI `rawEvent` forwarding;
- commands, stdout/stderr, unrestricted logs, working directories, local paths, diffs, source bodies, environment values, secrets, or credentials;
- customer, booking, SMS, phone, email, address, notes, or other PII;
- open-ended metadata maps not validated against a server-side allowlist;
- browser-authored mission, approval, evidence, audit, or checkpoint state.

AG-UI state snapshots and patches may describe transient presentation state, but they cannot replace versioned REST snapshots or the supervisor's durable event and audit ledger.

## Human-in-the-loop approvals

CopilotKit can improve the rendering of an interrupt, but it cannot be the approval authority. The official [governed actions guidance](https://docs.copilotkit.ai/a2a/human-in-the-loop/governed-actions) recommends server-side policy and stable action identifiers. The [`useInterrupt` documentation](https://docs.copilotkit.ai/human-in-the-loop/useInterrupt) also notes that a declared response schema is surfaced to the UI but is not client-validated; the agent/backend must validate on resume.

For this application:

- FastAPI creates the durable interrupt/approval record before it is rendered.
- The UI displays the exact run, action reference, risk, consequence, expiry, policy digest, and current `live_actionable` state obtained from REST.
- Resolve/cancel sends the durable action ID, opaque reference, expected record version, and idempotency key.
- FastAPI reauthenticates, reauthorizes, validates the response schema, rechecks expiry/current state, and records decision and result.
- Duplicate identical decisions replay the durable result; conflicting decisions fail deterministically.
- Expired, resolved, superseded, or orphaned approvals are disabled and rejected server-side.
- Reloads and worker/runtime restarts must not lose the approval.
- Browser-side `useHumanInTheLoop` handlers must not execute privileged shell, Git, deployment, booking, SMS, payment, or other consequential side effects.

## Offline, reconnect, and idempotency behavior

CopilotKit and AG-UI do not remove the need for the foundation specification's exact mutation semantics.

- A dispatch is persisted before worker execution and bound to actor, scope, method, path, body/version fingerprint, and UUID idempotency key.
- A stream disconnect never creates a second dispatch.
- On reconnect, the client reads the durable run snapshot and either attaches to that run or shows a terminal/recoverable state.
- Passive SSE reconnect uses bounded exponential backoff and a fresh single-use ticket.
- Sequence gaps, expired history, an unknown event, or an invalid patch cause a bounded REST refetch, not speculative local repair.
- Duplicate and out-of-order AG-UI events are ignored using run-local sequence/event identity.
- Retry of a non-idempotent mutation is forbidden while the original result is unresolved.
- Offline approval attempts remain pending locally only as UI intent; they are not presented as accepted until the server durably records the decision.

## Compatibility with the durable supervisor control plane

CopilotKit is compatible only when it sits **below** the supervisor application boundary:

```text
Mission / brief / assignment / run / evidence / audit / brain / checkpoint
                 FastAPI-owned durable control plane
                                |
                 REST snapshots + v2 invalidation SSE
                                |
                    Supervisor React application
                                |
          optional AG-UI/CopilotKit active-run presentation adapter
                                |
                           Codex worker
```

The optional adapter may make one active run easier to observe or interact with. It may not decide what work exists, who owns it, what version is current, whether evidence is accepted, whether an approval is live, or whether a mission is complete.

## Licensing, data residency, and product-tier implications

### Open-source packages

The official [CopilotKit repository](https://github.com/CopilotKit/CopilotKit) root and core package manifests are MIT licensed. The current source tree contains React core/UI packages, runtime packages, shared/core packages, AG-UI integrations, examples, and product/showcase material. The official [AG-UI repository](https://github.com/ag-ui-protocol/ag-ui) is the protocol and SDK source.

The repository root license must not be assumed to cover every subtree identically. In particular, CopilotKit's `showcase/LICENSE` uses a separate source-available, non-commercial/view-and-study license. No showcase code, assets, or designs should be copied into FastAPI Bookings without a file-level license review. Production dependency approval must record the exact package licenses and notices, not merely the repository headline license.

### CopilotKit Intelligence

CopilotKit Intelligence supplies managed or self-hosted threads, memory, analytics, and learning features. It is not needed for the proposed protocol spike and must remain disabled.

The official [Intelligence self-hosting guide](https://docs.copilotkit.ai/claude-sdk-typescript/intelligence/self-hosting) describes commercial plan requirements and an operational footprint including Kubernetes, PostgreSQL, Redis, and OIDC, with additional optional services. Self-hosting can keep the data plane within an approved network boundary, but it introduces a commercial license and substantial platform ownership.

Cloud-hosted Intelligence could receive agent interactions, thread/state content, analytics, or memory inputs. It must not be enabled until a separately owner-approved review covers:

- data-flow and subprocessors;
- contractual terms and DPA;
- Australian data residency and cross-border disclosure;
- retention, deletion, backup, and incident handling;
- encryption and identity federation;
- telemetry/learning opt-in behavior;
- explicit prohibition or redaction of source, prompts, reasoning, commands, diffs, logs, secrets, and customer/booking/SMS data.

No conclusion about cloud residency or contractual suitability is made by this spike; those require current vendor commitments for the intended plan and region.

## Dependency maturity and upgrade risk

CopilotKit is a mature 1.x monorepo, but its [versioning policy](https://github.com/CopilotKit/CopilotKit/blob/main/VERSIONING.md) explicitly allows breaking changes in a 1.x **minor** release, while patch releases should remain non-breaking. The older v1 SDK is deprecated and new work targets v2; no automatic codemods are promised. Exact version pinning and deliberate migration review are therefore mandatory.

At the time of inspection, `@copilotkit/react-core` and `@copilotkit/runtime` on the official main branch report version `1.79.0`; the runtime requires Node 20 or newer and both consume AG-UI packages. AG-UI 1.0 is now a frozen protocol, but the 1.0 implementation line is very recent and continues to move. The local frontend also uses TypeScript 6 while CopilotKit's package development metadata is on an older TypeScript line, so successful React peer compatibility alone is not sufficient—Vite 8/TypeScript 6 compilation must be proven.

The official [CopilotKit security policy](https://github.com/CopilotKit/CopilotKit/blob/main/SECURITY.md) provides a vulnerability-reporting process but does not replace local dependency scanning, lockfile review, SBOM generation, or upgrade testing.

Required dependency policy if adopted:

- pin exact CopilotKit and AG-UI versions in the lockfile;
- treat every CopilotKit minor as potentially breaking;
- run protocol conformance, type/build, browser, reconnect, and privacy tests before upgrades;
- review release notes, security advisories, transitive dependencies, licenses, and bundle/runtime size;
- keep a tested feature flag/fallback that removes the adapter without impairing REST/SSE supervision.

## Minimal proof-of-concept

### Preconditions

Do not start the spike until all are true:

1. The spike branch is demonstrably descended from the accepted P0 trust-boundary commit.
2. FastAPI supplies a durable, platform-owner-scoped run record, ownership mapping, version, and exact idempotency behavior through the v2 facade.
3. A strict server-side safe-event schema exists; raw current worker events are not the browser contract.
4. The work has its own explicit changed-file allowlist and isolated worktree/branch.

### Shape

Implement one hidden, platform-owner-only route in the canonical frontend for one real, labelled synthetic, read-only Codex author run. It must use no fake state, timer simulation, live booking/customer/SMS data, or external side effect.

Evaluate in two gates within that one spike:

1. **Protocol gate:** Vite React uses `@ag-ui/core`/`@ag-ui/client` against a FastAPI-owned AG-UI endpoint and renders only bounded run lifecycle/activity data.
2. **Runtime-value gate:** only after the protocol gate passes, insert a minimal Node 20 Express/Hono Copilot Runtime using v2 headless React integration. Measure whether it provides material functionality that justifies the extra service. Do not enable Intelligence, hosted threads, memory, analytics, learning, or vendor telemetry.

No full chat popup/sidebar, showcase UI, generative UI, or redesign dependency belongs in this spike. Visual design remains governed by the supervisor UI specification.

### Exit criteria

The spike passes only if all of the following are evidenced:

- **Build fit:** Vite 8, React 19, and TypeScript 6 production build and focused component tests pass with exact package versions.
- **Authentication:** no credential is placed in a URL; missing/invalid credentials and tenant-admin users are denied; a platform owner is accepted; FastAPI reauthenticates every request; CORS is exact-origin only.
- **Isolation:** guessed project, mission, thread, run, action, and tenant identifiers cannot read, stream, resume, or mutate another scope and fail without leaking existence.
- **Exactly-once effect:** a forced disconnect and replay with the same idempotency key produces one durable dispatch and one worker execution; no client or runtime auto-redispatch occurs.
- **Recovery:** page reload, browser offline/online, runtime restart, and worker restart preserve the run record; the UI recovers from REST and reconnects without duplicate effects.
- **SSE integrity:** passive SSE obtains a new one-use ticket on each connection and correctly handles duplicate, out-of-order, gap, and expired-history cases.
- **AG-UI conformance:** mandatory run boundaries and IDs validate against AG-UI 1.0; duplicate, unknown, oversized, invalid-patch, and out-of-order events have deterministic behavior.
- **Disclosure safety:** automated canary tests prove that prompts, reasoning, commands, stdout/stderr, paths, diffs, secrets, environment values, source bodies, and synthetic PII do not appear in browser payloads, logs, telemetry, storage, or outbound requests.
- **Durable HITL:** an interrupt survives reload and process restart; exact action ID/reference/version/risk/expiry is shown; duplicate, conflicting, expired, resolved, and orphaned decisions behave as specified.
- **No vendor egress:** network capture proves no CopilotKit Intelligence, analytics, learning, or unapproved telemetry endpoint is contacted.
- **Dependency governance:** license inventory, notices, SBOM, vulnerability scan, bundle impact, Node memory/startup/health behavior, and upgrade policy are recorded.
- **Operational value:** the Node runtime demonstrates a concrete capability that would otherwise require enough first-party work to justify its process and security cost.
- **Fallback:** disabling/removing the adapter leaves the native REST snapshots, ticketed SSE, mission workflow, approvals, and audit behavior intact.
- **Repository gates:** focused backend/frontend tests, zero-console/network verification, living-doc verification, independent security review, and QA sign-off pass.

### Decision after the spike

- **ADOPT NARROWLY** only if every exit criterion passes and the Node runtime demonstrates material value over the direct AG-UI path.
- **Use AG-UI only** if the protocol normalization is valuable but the Copilot Runtime does not justify its operational/security cost.
- **REJECT both** if native v2 REST/SSE is simpler, safer, or equally capable for the tested workflow.

## Required amendments to the supervisor foundation specification

The existing specification should not be changed until this assessment is accepted. If accepted, add these explicit amendments before implementation:

1. **Optional-adapter ADR:** CopilotKit/AG-UI is an optional active-run transport/presentation adapter, not the UI foundation, application shell, server-state cache, or control-plane source of truth.
2. **Channel separation:** specify passive ticketed GET SSE versus authenticated active-run POST streaming, including fresh-ticket, reconnect, resume, and unknown-outcome behavior.
3. **AG-UI adapter contract:** freeze the supported AG-UI 1.0 event subset, namespace custom events, require ordering/deduplication tests, and ban raw/open-ended fields.
4. **Ownership mapping:** define the server mapping among verified actor, tenant, project, mission, supervisor thread, assignment, run, AG-UI thread/run identifiers, and any CopilotKit correlation ID.
5. **HITL binding:** make CopilotKit interrupt hooks view/controllers over durable FastAPI approvals and require exact action reference, expected version, expiry, policy digest, server validation, and idempotency.
6. **Privacy boundary:** enumerate prohibited event and telemetry fields and require automated no-egress/privacy canary tests.
7. **Product-tier gate:** state that Intelligence, hosted/self-hosted threads, memory, analytics, and learning are off by default and require separate owner, security, legal, privacy, residency, and operational approval.
8. **Dependency gate:** exact version pins, lockfile/SBOM/license review, CopilotKit-minor-is-breaking policy, AG-UI conformance tests, and a tested native fallback.
9. **Sequencing gate:** do not add CopilotKit dependencies to WP-UI-02 or begin UI implementation until P0 ancestry and the v2 durable ownership/run/idempotency prerequisites are proven and the PoC is approved.

## Principal risks

| Risk | Severity | Control |
|---|---:|---|
| Generic agent UI becomes the hidden source of truth | Critical | Keep all domain records and decisions in FastAPI; CopilotKit is projection only |
| Raw Codex events disclose source, reasoning, commands, paths, logs, secrets, or PII | Critical | New strict safe-event adapter; prohibited-field canaries; no `rawEvent` |
| Browser or runtime identity is trusted | Critical | FastAPI reauth/reauthorize every operation; opaque IDs; explicit header allowlist |
| Reconnect duplicates a consequential run or approval | Critical | Durable run first; exact idempotency; reattach/refetch, never redispatch |
| Node proxy increases attack surface and operational load | High | Gate it behind measured value; health/limits/CORS/security tests; retain direct/native fallback |
| Intelligence causes unapproved data egress or commercial lock-in | High | Disabled by default; separate legal/privacy/residency/procurement approval |
| Recent AG-UI 1.0 ecosystem or CopilotKit minor breaks integration | High | Exact pins; conformance contract; treat minors as breaking; feature flag |
| Framework HITL UI is mistaken for durable authorization | High | Durable FastAPI approval authority; server schema/state/expiry/version checks |
| CopilotKit thread model conflicts with mission-first workflow | High | Treat threads as opaque run correlation/projection only |
| Showcase assets are assumed MIT | Medium/High | File-level license review; do not copy separately licensed showcase code/assets |

## Final recommendation

Proceed with **SPIKE FIRST**, but only after the P0 trust boundary and v2 durable run/ownership/idempotency prerequisites are present on the spike branch. The spike should begin with vendor-neutral AG-UI protocol mapping and evaluate a small CopilotKit v2 headless + Node runtime layer only as a second gate. Keep the planned ground-up supervisor UI, TanStack Query/REST authority, ticketed invalidation SSE, durable mission model, evidence/audit trail, and FastAPI approvals unchanged.

CopilotKit is potentially useful here as a **thin interaction lens over one active run**. It is not a safe substitute for the resident supervisor's durable orchestration and audit system.

## Official sources reviewed

- [CopilotKit: Build with agents / Codex](https://docs.copilotkit.ai/build-with-agents)
- [CopilotKit official repository](https://github.com/CopilotKit/CopilotKit)
- [CopilotKit root MIT license](https://github.com/CopilotKit/CopilotKit/blob/main/LICENSE)
- [CopilotKit showcase-specific license](https://github.com/CopilotKit/CopilotKit/blob/main/showcase/LICENSE)
- [CopilotKit versioning policy](https://github.com/CopilotKit/CopilotKit/blob/main/VERSIONING.md)
- [CopilotKit security policy](https://github.com/CopilotKit/CopilotKit/blob/main/SECURITY.md)
- [Copilot Runtime](https://docs.copilotkit.ai/langgraph-python/copilot-runtime)
- [React SPA / Vite quickstart](https://docs.copilotkit.ai/react-spa)
- [Authentication](https://docs.copilotkit.ai/auth)
- [Self-managed agents](https://docs.copilotkit.ai/llamaindex/backend/self-managed-agents)
- [Governed actions](https://docs.copilotkit.ai/a2a/human-in-the-loop/governed-actions)
- [`useInterrupt`](https://docs.copilotkit.ai/human-in-the-loop/useInterrupt)
- [CopilotKit Intelligence self-hosting](https://docs.copilotkit.ai/claude-sdk-typescript/intelligence/self-hosting)
- [AG-UI official repository and specification](https://github.com/ag-ui-protocol/ag-ui)
