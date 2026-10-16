# Codex Bridge Fit Assessment for the Integrated Codex Supervisor

**Assessment date:** 15 October 2026  
**Decision:** **REFERENCE ONLY**  
**Target:** the integrated `F:\Projects\fastapi_bookings\codex-control-centre` and the ground-up supervisor UI under the canonical FastAPI Bookings frontend  
**Scope:** read-only architecture and security assessment. Codex Bridge was not cloned, installed, executed, copied, or added as a dependency. No application or specification file was changed.

## Executive decision

Do **not** adopt `hitsmaxft/codex-bridge` as a runtime dependency, replace the integrated Control Centre with it, embed its Web UI, or place it between FastAPI Bookings and Codex app-server.

Use it as a **reference implementation only** for a small set of transport and operator-experience concepts: explicit app-server writer ownership, read-only degradation when another writer owns a session, bounded/paginated history, deterministic snapshot/live reconciliation, truthful queue/steer/interrupt capability states, explicit session handoff, and carefully bounded file retrieval.

The reasons are structural rather than cosmetic:

- Codex Bridge is a self-hosted, single-user/homelab Codex app-server client and lifecycle daemon. FastAPI Bookings needs an authenticated, platform-owner-gated, eventually actor-scoped development supervisor.
- Its Rust daemon, rollout reader, CLI, Web UI, app-server supervisor, and Unix-socket topology substantially duplicate the existing Python worker manager, typed schema bundle, worktree service, REST/SSE facade, and canonical React application.
- Its public installation contract currently supports macOS and Linux, while the active FastAPI Bookings environment is Windows and the integrated worker already contains Windows-specific Codex executable and process handling.
- It has no mission, approved brief, assignment, evidence, independent-audit, acceptance, risk, decision, or Project Brain control plane. Substituting it would bypass the very durable supervisory layer being built.
- Its Basic-Auth/session-cookie or trusted reverse-proxy posture cannot replace FastAPI Bookings identity, platform-owner authorization, project claim, actor scope, idempotency, and non-leaking resource authorization.
- The project is active but young: version `0.3.10`, 8 stars, 2 forks, 126 commits, rapid releases, three open issues concentrated in session ownership/history/transport, and no published security policy. That is useful reference material, not an acceptable new privileged execution dependency without a separate, pinned supply-chain review.

This decision does **not** reject the underlying Codex app-server protocol. The integrated Control Centre already uses that protocol directly and should continue to do so through a first-party adapter owned by FastAPI Bookings.

## Decision by proposed role

| Proposed role | Decision | Reason |
|---|---|---|
| Replacement for the integrated Control Centre | **Reject** | Removes native FastAPI authorization and duplicates worker/worktree/event infrastructure while omitting the durable supervisor domain. |
| Runtime dependency behind `/api/admin/codex/v2` | **Reject** | Adds a privileged Rust daemon, a second process manager, another session/history store reader, and an incompatible authentication boundary. |
| Foundation for the ground-up supervisor UI | **Reject** | Its UI is conversation/session-first; the approved product is mission/brief/evidence/audit-first and must live in the canonical frontend. |
| Drop-in Windows app-server manager | **Reject** | No documented Windows installer/service topology; the implementation assumes Unix sockets plus launchd/systemd. |
| Source-code donor | **Reject** | No source should be copied. Any adopted idea must be independently specified and implemented against local contracts. |
| Architecture and UX reference | **Accept** | Several mature operational ideas are directly useful when translated into the native supervisor architecture. |

## What Codex Bridge is

The public repository describes a Rust daemon with:

- a typed local control protocol shared by `codexctl` and its embedded Vite Web UI;
- direct Codex app-server control over WebSocket on a Unix-domain socket;
- read access to the Codex rollout store for history and metadata;
- queue, steer, interrupt, archive, rename, pin, custom-section, model, skill, tool, diff, file, and transcription experiences;
- optional ownership of the app-server process and an advisory writer lock;
- optional macOS Desktop interposition through a TCP-to-Unix WebSocket adapter;
- password/session authentication for its Web UI or a loopback-only no-auth mode behind a trusted same-host proxy.

Its recommended topology is a separately installed Codex app-server managed by the Bridge daemon. If another app-server owns a session writer, Bridge keeps reads and queueing available but disables direct session mutations. It explicitly avoids choosing a write target by rollout modification time and provides a release-lock handoff.

Those are sensible properties for a personal remote Codex client. They do not amount to a multi-user supervisory control plane.

## Current local architecture and overlap

The integrated Control Centre already owns the corresponding execution substrate:

- `WorkerProcess` launches `codex app-server`, completes the initialize handshake, correlates requests, handles server requests/approvals, normalizes notifications, and manages Windows process groups.
- `WorkerManager` assigns a dedicated worker to a Control Centre thread and its isolated Git worktree.
- `turns.py` implements thread start/resume, `turn/start`, steer, interrupt, and approval responses.
- the Control Centre database persists projects, threads, turns, items, approvals, and sub-agent records;
- the event service and SSE facade project worker activity to the browser;
- the repository carries generated Codex app-server v1/v2 schema files;
- the canonical FastAPI Bookings frontend already contains the integrated coding workbench while the approved v2 specification replaces it with a new mission-first supervisor UI.

The accepted P0 commit `170f6f7eb62278bc029d39caaeda8637d4c99c59` strengthens the intended boundary with platform-owner-only mounted authority, header-only native credentials, atomic one-use SSE tickets, authenticated resident streaming, privacy-safe Skills-RAG requests, and truthful worker acknowledgement. At assessment time that commit is on `codex/codex-supervisor-p0-trust` but is **not an ancestor of the inspected primary checkout** (`6256fc5d25e3ad5c2f60d739c24446ebc4df3546`). No third-party adapter should be evaluated in the application until the accepted P0 ancestry is integrated and independently proven.

### Capability comparison

| Capability | Integrated Control Centre | Codex Bridge | Fit conclusion |
|---|---|---|---|
| App-server lifecycle | Per-thread stdio subprocesses, FastAPI lifecycle, Windows handling | Managed/adopted app-server over Unix WebSocket, user service lifecycle | Duplicate; study adoption/health semantics, keep local implementation. |
| Protocol | JSON request correlation, notification normalization, checked-in generated schemas | Rust typed bridge protocol plus app-server adapter | Improve local code generation/conformance; do not add the daemon. |
| Session ownership | In-memory worker/thread mapping; no explicit cross-client writer state | Explicit external-writer/read-only state, advisory manager lock, release handoff | High-value concept to reimplement durably. |
| Queue/steer/interrupt | Start, steer, interrupt; durable supervisor queue not yet built | Queue while externally owned, direct steer/interrupt when owned | Adopt capability-state semantics, not its CLI queue path. |
| History | Control Centre DB items plus in-memory 100-event replay | Rollout-store pagination plus live app-server state | Adopt bounded snapshot/live reconciliation; rollout files remain diagnostic only. |
| Diffs/tools/output | Existing normalized items and cockpit viewers; v2 safe disclosure still prerequisite | Rich typed tools, diffs, terminal progress, screenshots | UX reference only; local redaction and evidence contracts govern. |
| File access | v2 spec requires opaque artifact IDs and authorization | Workspace/visible-root validation, symlink rejection, 16 MiB cap, five-minute download tickets | Reuse principles with stricter actor/resource binding; do not expose host paths. |
| Authentication | Native FastAPI identity and P0 platform-owner boundary | Basic Auth/session cookie or trusted loopback proxy | Incompatible as an application authority. |
| Persistence | Control DB now; planned mission/brief/run/evidence/audit/checkpoint schema | Codex rollout store plus daemon caches/session metadata | Cannot replace supervisor persistence. |
| UI | Canonical React application; ground-up mission-first v2 approved | Embedded conversation/session Web UI and CLI | Do not migrate; use only interaction lessons. |

## Windows and operational fit

The documented installers and service contracts are macOS `launchd` and Linux `systemd --user`. The app-server transport, daemon control socket, writer lock, service adoption, and Desktop interposition are expressed around Unix-domain sockets and macOS/Linux paths. No Windows installation, service manager, process-lifecycle, path, ACL, or upgrade/rollback contract is documented.

The upstream OpenAI Codex repository now documents an experimental app-server daemon with platform-specific Linux, macOS, and Windows handling, but explicitly warns that its lifecycle contract may change. That upstream capability may eventually inform the local worker adapter. It does not make Codex Bridge Windows-supported.

Adopting Bridge would add at least:

- Rust/Cargo build and upgrade ownership;
- Node/npm solely to build its embedded frontend even if that frontend is not wanted;
- a second long-running daemon and health/readiness surface;
- another app-server lifecycle manager capable of stopping or restarting the writer;
- Unix-socket or compatibility transport work on Windows;
- a second configuration, authentication, logging, cache, file-serving, and rollback path;
- writer-lock conflicts with the existing Control Centre and Codex Desktop;
- version coordination among Codex CLI, app-server protocol, Bridge, FastAPI, and the supervisor UI.

That burden is disproportionate because nearly all functional value already exists locally or is explicitly planned.

## Security and trust-boundary assessment

### Authentication and authorization

Bridge's Web UI security is credible for its stated homelab purpose: loopback by default, a mode-`0600` password file, HttpOnly session cookies, rejection of unauthenticated non-loopback startup, optional TLS, and a reverse-proxy deployment pattern. It is still the wrong authority model for FastAPI Bookings.

It does not natively establish the FastAPI actor, tenant, role, platform-owner capability, claimed project, mission, assignment, run, or approval binding required by the v2 contract. Putting it behind a proxy would authenticate access to Bridge, not authorize each supervisor object or action. A trusted `no_auth` hop would create a dangerous bypass if routing or proxy policy drifted.

The native rule remains: the browser talks to same-origin FastAPI; FastAPI authenticates and authorizes every request; opaque IDs are untrusted selectors; the v2 facade alone invokes the worker adapter. No Bridge cookie, Basic Auth credential, control socket, or reverse-proxy assertion may become supervisor authority.

### Process and host authority

Bridge can manage the app-server lifecycle, inspect rollout history, serve local files, execute a policy-limited host command set, and in advanced mode alter the Desktop launch environment. Those are privileged host capabilities. Running it beside the existing worker manager creates two potential owners of the same app-server/session and weakens the single-mutation-authority rule.

The following must not migrate:

- Desktop interposition, CDP/CGEvent experiments, or launch-environment mutation;
- Bridge's host-executor or device-specific command policy;
- unmanaged projectless workspace creation;
- direct browser access to Bridge's `/api` or control socket;
- broad configured `visible_directories` as a substitute for run/evidence authorization;
- rollout repair or app-server restart controls outside native platform-owner operations;
- Whisper management, notifications, or unrelated personal-client features.

### History and evidence integrity

Codex rollouts are valuable recovery inputs, but they are not supervisor evidence. They can be written by other clients, reflect a different writer, omit native mission/brief context, change format with Codex, and contain raw prompts, reasoning, tool data, paths, commands, source, secrets, or PII.

Therefore:

- rollout data may be used only by a future read-only, version-pinned reconciliation adapter;
- it must be labelled `observed`, never `verified`;
- it cannot create or approve a mission, brief, run, evidence result, audit verdict, acceptance, or checkpoint;
- browser disclosure must pass the v2 bounded/redacted typed contracts;
- commit-bound machine evidence continues to come from native capture and independent verification.

## Protocol stability and maintenance maturity

The official Codex app-server is a capable typed interface, but it is actively evolving. The upstream source contains stable and explicitly experimental methods and fields; the app-server daemon itself is documented as experimental. The wire format is JSON-RPC-like but omits the `jsonrpc` field in current upstream Rust types. Compatibility must be proven against the exact installed Codex binary rather than inferred from a third-party wrapper.

Codex Bridge mitigates this with typed Rust structures, fixtures, a checked-in `Cargo.lock`, a test suite, and frequent releases. Its release history reports Rust workspace, browser, build, formatting, installer, and live local checks. Positive engineering signals include fail-closed configuration parsing, no modification-time write targeting, explicit writer ownership, bounded caches/files, and truthful transport errors.

Maturity risks remain:

- pre-1.0 version `0.3.10`;
- only 8 stars and 2 forks at review time;
- 126 commits but a very short public release history: ten releases from 15 September to 4 October 2026;
- three open issues, all in sensitive ownership/transport/history areas, including duplicate rollout ordinals truncating paginated history and Desktop/shared-app-server resume problems;
- no detected `SECURITY.md` and no published security advisories;
- no reviewed evidence in the public release pages of signed artifacts, an SBOM, SLSA provenance, or a documented compatibility matrix;
- the advanced Desktop/broker path is explicitly experimental and fake-tested rather than proven as a replacement.

This is an active project worth watching, not a stable privileged subsystem to inherit today.

## Licensing and supply-chain position

The root repository is MIT licensed, which is permissive and compatible in principle. Attribution and the license notice would still be required for copied or distributed substantial portions. This assessment recommends no copying and no package adoption, so no new notice obligation is introduced by this work.

The workspace pins a lockfile and uses mainstream Rust components such as Axum, Tokio, rusqlite, Tungstenite, Reqwest, and Rustls; the Web UI introduces a separate npm dependency graph. The official installer builds from a checkout and runs `cargo install --locked --force`, so adopting it transfers build provenance and the full Rust/npm transitive tree to this project.

If a future owner reopens dependency adoption, it requires a new isolated spike with:

1. an exact immutable tag and commit digest;
2. source/archive hash verification and a recorded provenance decision;
3. Cargo and npm SBOMs plus vulnerability, license, and abandoned-dependency review;
4. review of build scripts, installers, process execution, file serving, auth, logging, telemetry, and update behavior;
5. Windows build/runtime/service proof;
6. an upstream Codex version compatibility matrix and protocol conformance suite;
7. native P0/v2 authorization, privacy-canary, clean-checkout, rollback, and independent-security-review gates.

No such spike is justified while the first-party adapter already covers the required execution path.

## Concepts worth reimplementing locally

These ideas should be translated into FastAPI-owned contracts without copying Bridge source:

1. **Explicit session writer state.** Add a truthful capability projection such as `writer_state = native_owned | externally_owned | unowned | unknown` with independently derived `can_read`, `can_queue`, `can_steer`, `can_interrupt`, and `can_release`. Never infer write ownership from the newest rollout file.
2. **Read-only degradation.** When another app-server owns a Codex thread, keep bounded observation available but disable direct mutation. The UI must explain which owner is known and which actions are unavailable.
3. **Explicit handoff.** Releasing or reacquiring a writer is a separately authorized, audited operation with confirmation and worker acknowledgement; refresh/polling never silently reacquires it.
4. **Snapshot/live reconciliation.** Load a bounded durable REST snapshot first, then apply typed sequenced events. Preserve viewport/UI state while refetching. On duplicates, gaps, unknown events, invalid deltas, restart, or expired history, refetch rather than inventing state.
5. **Bounded history.** Provide cursor pagination and a newest-window default. Long sessions must not replay unbounded output into browser memory or model context.
6. **Truthful queue semantics.** A supervisor queue is a durable native assignment/run state. Queue acceptance is not worker execution; dispatch becomes active only after the correct writer and app-server acknowledge it. Do not shell out to another `codex queue` path behind the control plane.
7. **Typed protocol compatibility.** Generate or validate adapter types from the exact installed Codex schema; maintain version/capability negotiation, golden fixtures, unknown-field tolerance where safe, and fail-closed handling for privileged unknown methods.
8. **App-server adoption and shutdown rules.** Record whether FastAPI owns, adopted, or merely observes a process; never let two managers restart the same writer; make disruptive restart explicit and recoverable.
9. **File-ticket discipline.** Retain opaque artifact IDs, root/symlink/regular-file/MIME/size checks, bounded streaming, `nosniff`, and short expiry. Strengthen them with actor, mission, run, evidence, digest, disposition, and permitted-retry binding from the v2 spec.
10. **No modification-time routing.** Every read or mutation uses an exact native thread/run mapping and current ownership/capability record.
11. **Bounded process output.** Retain byte caps, timeouts, process-tree termination, environment allowlists, and safe summaries in the worker/evidence layer.
12. **Mobile/long-session interaction lessons.** Queue withdrawal, stable scroll anchoring, compact live tool groups, background-completion cues, and explicit read-only state are useful UX references for Run Detail—not a visual design source.

## Components and assumptions that must not migrate

- the Rust daemon, `codexctl`, `ws-unix-bridge`, launcher, or embedded Web UI;
- Bridge's rollout store, caches, or session metadata as supervisor persistence;
- Basic Auth, Bridge session cookies, proxy `no_auth`, or a separate public listener;
- direct Bridge API calls from the canonical browser;
- a second app-server lifecycle manager or writer lock beside the native manager;
- Unix-only installation/service assumptions in the Windows application;
- direct rollout-file mutation/repair from the supervisor;
- its queue command as an alternative dispatch route;
- Desktop interposition or experimental broker/CDP paths;
- generic host execution, broad visible roots, projectless workspaces, Whisper, or notification features;
- Bridge UI components, styling, navigation, or conversation-first information architecture;
- raw history, tool events, diffs, output, files, reasoning, prompts, or metadata crossing the v2 disclosure boundary.

## Relationship to CopilotKit and AG-UI

Codex Bridge and CopilotKit/AG-UI occupy different layers and are not interchangeable:

```text
Durable supervisor domain
  Mission -> Brief -> Assignment -> Run -> Evidence -> Audit -> Decision -> Checkpoint
                              |
               FastAPI v2 authorization and REST authority
                              |
          optional northbound active-run presentation protocol
                    CopilotKit / AG-UI spike
                              |
              first-party southbound worker adapter
                 Codex app-server JSON-RPC
                              |
          Codex Bridge is an alternative app-server client/daemon,
          not the durable domain and not the AG-UI presentation layer
```

- **Codex Bridge** is predominantly a southbound app-server adapter, session/history client, daemon, CLI, and ready-made personal Web UI.
- **AG-UI** is a northbound event/projection protocol for presenting and interacting with an already-authorized active run.
- **CopilotKit** is a presentation/runtime layer that may consume AG-UI; the accepted assessment allows only a future gated spike, never control-plane ownership.

Stacking Bridge beneath CopilotKit would add two adapters and another daemon without adding mission, evidence, or audit semantics. It would also make failure, identity, sequence, and writer ownership harder to reason about. The native architecture should keep one first-party app-server adapter and, only if the existing two-gate spike later proves value, one optional bounded AG-UI presentation projection above the v2 control plane.

## Required supervisor-spec amendments

These are recommended amendments for the next specification revision. They do not authorize code or dependency changes.

1. **Worker-adapter ownership ADR.** State that FastAPI Bookings owns the sole southbound Codex app-server adapter. Third-party daemons cannot become a parallel writer, lifecycle manager, browser endpoint, or durable state authority.
2. **Writer capability contract.** Add typed writer ownership, source, confidence/observed time, and legal capabilities to run snapshots. Define external-owner, unowned, native-owned, stale, and unknown behavior plus explicit release/reacquire transitions.
3. **Durable queue boundary.** Distinguish `queued`, `worker_acknowledged`, `running`, and `terminal`; queueing must not invoke an out-of-band Codex CLI path or imply writer acquisition.
4. **Protocol compatibility gate.** Bind the adapter to an exact supported Codex version/schema set; generate/validate types; require handshake capability recording, compatibility fixtures, privileged unknown-method rejection, and an upgrade matrix.
5. **Recovery-source hierarchy.** Make native supervisor DB/REST authoritative, app-server reads secondary, and rollouts diagnostic/observed only. Define mismatch reporting without automatic mutation or evidence promotion.
6. **Single lifecycle manager invariant.** Record `managed | adopted | external | unknown` app-server ownership, reject a second manager, and require an audited platform-owner action for disruptive restart or writer release.
7. **Long-history contract.** Add cursor bounds, newest-window loading, snapshot/live deduplication, gap behavior, restart behavior, and browser memory limits to Run Detail acceptance criteria.
8. **Artifact-ticket contract.** Freeze actor/resource/digest/MIME/disposition/size/expiry/retry binding and prohibit browser-supplied paths or generic visible-directory access.
9. **Windows-first acceptance.** Require Windows process-tree shutdown, path/ACL handling, worktree locking, service restart, long-path, and app-server upgrade tests for every worker-adapter change.
10. **Bridge non-dependency decision record.** Record this `REFERENCE ONLY` decision so future UI or worker tasks do not accidentally import Bridge, its UI, or its auth/process topology.

These amendments complement rather than replace the existing CopilotKit/AG-UI optional-adapter section. The planned ground-up UI, native REST/TanStack Query authority, passive ticketed SSE, durable mission model, independent audit, and evidence ledger remain unchanged.

## Revisit conditions

Reconsider a narrow Bridge dependency only if all of the following become true and the local adapter has a demonstrated gap that is expensive to close:

- documented and tested Windows support with an appropriate service/ACL/update contract;
- stable versioned public bridge API and Codex compatibility matrix;
- maintained security policy, vulnerability process, signed/provenanced releases, SBOM, and acceptable dependency review;
- a supported mode with no Web UI, CLI, rollout authority, host executor, Desktop interposition, or process-manager conflict;
- native FastAPI authentication/authorization on every operation without Basic Auth or proxy trust as the final authority;
- clear material benefit over the first-party adapter proven by measurements and failure tests.

Until then, no implementation spike is recommended. Review selected design ideas during WP-UI-05 (runs/events) and implement only those concepts under the native contracts.

## Principal risks

| Risk | Severity | Required response |
|---|---:|---|
| Bridge becomes a second mutation authority beside FastAPI | Critical | Do not adopt daemon/API; enforce one native worker adapter and lifecycle owner. |
| Bridge auth bypasses platform-owner and object scope | Critical | Browser uses only same-origin native v2 APIs; FastAPI reauthorizes every action. |
| Rollout content is treated as verified evidence | Critical | Label rollout observations unverified; native commit-bound capture and independent verification remain mandatory. |
| Raw rollouts/files/tools expose secrets, source, reasoning, paths, or customer data | Critical | Never forward raw Bridge data; use the v2 bounded/redacted disclosure schema and canary tests. |
| Two app-server managers conflict over writer/session state | High | Model ownership explicitly; reject parallel management; audited handoff only. |
| Undocumented Windows behavior fails or weakens isolation | High | No adoption without Windows-specific proof; retain current first-party process/worktree path. |
| Fast protocol churn breaks a privileged adapter | High | Exact Codex version/schema compatibility, conformance fixtures, capability negotiation, upgrade gate. |
| Young dependency/supply chain becomes operationally critical | High | Reference only; if revisited, exact pins, hashes, SBOM, vulnerability/license/provenance review. |
| Conversation-first UI displaces mission/evidence/audit workflow | High | Ground-up canonical supervisor UI remains authoritative; no Bridge UI imports. |
| Extra daemon increases debugging and recovery ambiguity | Medium | Keep one process topology; native readiness exposes each owned component truthfully. |

## Final recommendation

**REFERENCE ONLY.** Codex Bridge is a thoughtful personal Codex remote-control implementation and a useful source of operational ideas. It is not the right dependency or replacement for FastAPI Bookings' integrated supervisor.

Continue with the approved native sequence:

1. integrate and prove the accepted P0 trust-boundary ancestry;
2. implement the durable mission/work-package/brief/checkpoint foundation;
3. implement the ground-up supervisor shell against native `/api/admin/codex/v2` REST authority;
4. add durable assignments/runs/events with explicit writer capability and recovery contracts informed by the concepts above;
5. add commit-bound evidence and structurally independent audit;
6. consider the already-approved CopilotKit/AG-UI two-gate spike only after its prerequisites exist.

Do not add a Codex Bridge spike to the critical path.

## Sources reviewed

### Codex Bridge primary sources

- [Repository and README](https://github.com/hitsmaxft/codex-bridge)
- [Design notes](https://github.com/hitsmaxft/codex-bridge/blob/main/DESIGN.md)
- [Installation and service topology](https://github.com/hitsmaxft/codex-bridge/blob/main/docs/install.md)
- [Configuration example](https://github.com/hitsmaxft/codex-bridge/blob/main/config.example.toml)
- [Workspace manifest](https://github.com/hitsmaxft/codex-bridge/blob/main/Cargo.toml)
- [MIT license](https://github.com/hitsmaxft/codex-bridge/blob/main/LICENSE)
- [Release history](https://github.com/hitsmaxft/codex-bridge/releases)
- [Open issues](https://github.com/hitsmaxft/codex-bridge/issues)
- [Security overview](https://github.com/hitsmaxft/codex-bridge/security)

### Upstream and local authoritative sources

- [OpenAI Codex app-server README](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
- [OpenAI Codex app-server protocol source](https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/src/rpc.rs)
- [OpenAI experimental app-server daemon](https://github.com/openai/codex/blob/main/codex-rs/app-server-daemon/README.md)
- `codex-control-centre/backend/services/worker.py`
- `codex-control-centre/backend/services/worker_manager.py`
- `codex-control-centre/backend/services/protocol.py`
- `codex-control-centre/backend/services/worktree_service.py`
- `codex-control-centre/backend/services/event_service.py`
- `codex-control-centre/backend/services/sse_tickets.py`
- `codex-control-centre/backend/routers/turns.py`
- `codex-control-centre/backend/routers/events.py`
- `codex-control-centre/backend/middleware/auth.py`
- `codex-control-centre/backend/models/codex.py`
- `artifacts/codex-supervisor/CCC_ARCHITECTURE_BLUEPRINT.md`
- `artifacts/codex-supervisor/CCC_SECURITY_BASELINE.md`
- `artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md`
- `artifacts/codex-supervisor/CCC_COPILOTKIT_FIT_ASSESSMENT.md`

