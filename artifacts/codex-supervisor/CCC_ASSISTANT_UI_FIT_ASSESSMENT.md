# Assistant UI Fit Assessment for the Codex Supervisor UI

**Task:** `ccc_assistant_ui_fit_assessment`  
**Decision:** **SPIKE FIRST**  
**Scope:** Read-only architecture and dependency assessment. No package was installed, no service was started, and no application or supervisor-specification file was changed.  
**Application:** FastAPI Bookings  
**Canonical frontend:** `F:\Projects\fastapi_bookings\frontend`  
**Assessment date:** 2026-10-15 (Australia/Sydney)

## Executive decision

Assistant UI is a credible source of React chat primitives and a potentially useful **narrow presentation runtime** for one active Codex run. It must not become the ground-up supervisor's application shell, information architecture, durable thread store, permission system, approval authority, or control plane.

The current release is not ready for direct adoption in the accepted AG-UI path. The published `@assistant-ui/react-ag-ui` package is `0.0.69` and depends on `@ag-ui/client ^0.0.59`, while the supervisor contract and current CopilotKit path target frozen AG-UI 1.0 and current `@ag-ui/client 1.0.2`. That is a protocol-version mismatch, not a cosmetic package difference.

The correct next decision is therefore **SPIKE FIRST**:

1. keep the native Vite/React supervisor, TanStack Query, REST snapshots, ticketed passive SSE, and FastAPI durable domain authoritative;
2. compare Assistant UI primitives through `ExternalStoreRuntime` against the existing direct AG-UI/CopilotKit headless proof-of-concept;
3. do not use `@assistant-ui/react-ag-ui` unless a future exact-pinned release proves AG-UI 1.0 compatibility;
4. retain at most one third-party React agent runtime after the bake-off; do not ship Assistant UI and CopilotKit headless together unless measured evidence identifies distinct, non-overlapping responsibilities.

The likely successful production shape, if the spike passes, is **ADOPT NARROWLY** for a lazy-loaded Runs interaction/transcript pane. Intake may use the same composer primitives only for non-authoritative clarification text. Mission Board, Brief Builder, Audit Studio, Evidence Ledger, Decisions/Risks, Operations, navigation, and all consequential confirmations remain native supervisor UI.

The linked `https://www.assistant-ui.com/mcp` endpoint does not alter this decision. It is an `assistant-ui-docs` MCP documentation/template service for development agents, not an Assistant UI runtime, AG-UI agent server, Codex bridge, worker transport, or supervisor integration.

## Binding local context

The assessment follows the accepted supervisor foundation rather than treating a chat framework as a new product design:

- `frontend/` is the sole canonical frontend. `codex-control-centre/frontend/` is reference/decommission-only.
- The product is mission-first, not chat-first: Mission -> Work Package -> approved Brief -> bounded author Run -> Evidence -> independent Audit -> durable Checkpoint.
- FastAPI owns identity, tenant/user scope, project claims, missions, work packages, briefs, assignments, runs, approvals, evidence, audits, checkpoints, idempotency, and lifecycle state.
- TanStack Query v5 remains the planned server-state cache. A chat runtime may hold only a bounded projection of one visible run.
- Passive supervisor events remain short-lived, atomically single-use, scoped-ticket GET SSE. An active run stream is a separately authenticated POST/read-session contract.
- A disconnect, reload, retry, message edit, regenerate action, or runtime resume must never dispatch another worker run or resolve an approval.
- P0 prohibits query-string credentials, fabricated success, unscoped event replay, raw prompt/PII disclosure, and browser authority over consequential state.
- The UI foundation uses React `19.2.7`, React DOM `19.2.7`, Vite `8.1.1`, TypeScript `6.0.2`, Tailwind 4, and a `radix-nova` shadcn configuration. The current application already depends on the `radix-ui` umbrella package.

These constraints exclude a full Assistant UI starter, floating assistant, thread-list replacement, Assistant Cloud persistence, browser-executed tools, or model-generated control surfaces from the supervisor foundation.

## Project and package snapshot

### Licensing and stewardship

The official repository is MIT licensed, including the published `@assistant-ui/react`, `@assistant-ui/react-ag-ui`, and `@assistant-ui/react-markdown` package manifests. The root license requires preservation of its copyright and permission notice. Production adoption still requires a transitive license/notice inventory rather than relying only on the repository headline.

The repository is active and substantial: the official GitHub metadata showed approximately 12.5k stars and 1.2k forks at inspection time. The project publishes packages independently and frequently. Activity is positive, but rapid releases across `0.x` packages increase upgrade and compatibility risk.

The repository has a documented private vulnerability-reporting route and states that only the latest published version of each `@assistant-ui/*` package receives security fixes. Its GitHub Security page showed no published advisories at inspection time. Neither fact replaces an exact-version vulnerability scan, SBOM, provenance check, or local threat review.

### Current package maturity and compatibility

| Package | Current inspected release | Relevant metadata | Assessment |
|---|---:|---|---|
| `@assistant-ui/react` | `0.15.28` on npm; repository main was slightly behind at `0.15.22` | React/React DOM peers `^18 || ^19`; ESM; side-effect-free manifest; about 2.80 MB unpacked before transitive dependencies | React 19 compatible in declared peers, but still pre-1.0 and fast-moving. Vite 8/TS 6 must be proven locally. |
| `@assistant-ui/react-ag-ui` | `0.0.69` | React peer `^18 || ^19`; depends on `@ag-ui/client ^0.0.59`; about 1.06 MB unpacked before transitives | Too immature and protocol-misaligned for direct production adoption under the accepted AG-UI 1.0 contract. |
| `@assistant-ui/react-markdown` | `0.14.22` | React `^18 || ^19`; depends on `react-markdown 10.1.0` and Radix primitives; about 0.43 MB unpacked | Plausible, but optional. It must beat the native markdown/code renderer on security, accessibility, and bundle cost. |
| `@ag-ui/client` | `1.0.2` | Depends on exact `@ag-ui/core`, encoder, and proto `1.0.2`; about 1.15 MB unpacked | This is the current AG-UI 1.0 line used by the accepted CopilotKit assessment. |
| `@copilotkit/react-core` | `1.79.0` | React 18/19 peers; exact AG-UI `1.0.2`; about 7.82 MB unpacked before transitives | Protocol-aligned but substantially broader. Existing decision remains spike-only and headless. |
| `@copilotkit/runtime` | `1.79.0` | Node 20+; exact AG-UI `1.0.2`; about 4.96 MB unpacked before transitives | Adds a separate server process and trust/operations boundary. |

Unpacked package size is not browser bundle size. The spike must measure emitted route chunks, gzip/Brotli size, parse/evaluation time, and transitive package count from the exact lockfile.

### Dependency shape

`@assistant-ui/react` is not a tiny set of DOM wrappers. Its direct runtime graph includes `@assistant-ui/core`, `@assistant-ui/store`, `@assistant-ui/tap`, `assistant-stream`, `assistant-cloud`, `zustand`, `zod`, `safe-content-frame`, `react-textarea-autosize`, and `radix-ui`.

This has two consequences:

1. adopting only a few primitives still introduces an assistant-specific store/runtime abstraction and a cloud client package into the dependency graph;
2. tree-shaking claims must be verified in the actual Vite production build, especially because the desired surface is much smaller than a general chat product.

No cloud request is assumed merely because `assistant-cloud` is a transitive dependency. However, Assistant Cloud is not permitted to be configured or instantiated in the spike, and network capture must prove that no Assistant UI vendor endpoint is contacted.

## Hosted documentation MCP fit

The official `https://www.assistant-ui.com/mcp` endpoint identifies itself as `assistant-ui-docs` using Streamable HTTP. Its declared tools are:

- `list_pages` and `get_navigation` for documentation discovery;
- `search_docs` and `read_page` for current documentation, examples, design components, elements, and Tap pages;
- `list_templates` and `read_template` for hosted template metadata, schemas, rules, contracts, and example configuration;
- `preview_template` for creating a hosted preview session and returning preview/download URLs.

The official Agent Skills documentation likewise describes this MCP as a way for coding assistants and IDEs to look up live documentation and templates while implementing an application. It confers no runtime capability on FastAPI Bookings and does not connect the resident Codex supervisor to Assistant UI, AG-UI, Assistant Cloud, or a model provider.

### Permitted use during an approved spike

An implementation agent may use the hosted MCP **read-only as development-time reference material** after the spike brief is approved. The allowed default tool subset is:

- `list_pages`;
- `get_navigation`;
- `search_docs`;
- `read_page`;
- `list_templates` and `read_template` only for comparison or dependency/API research.

Returned text, examples, template rules, and component suggestions are untrusted reference material. Agents must reconcile them against the exact pinned package source, local TypeScript types, the supervisor specification, existing shared primitives, security boundaries, and the approved changed-file allowlist. Documentation freshness does not constitute compatibility, license, security, accessibility, or acceptance evidence.

### Prohibited production and template use

The MCP endpoint must not be:

- bundled into the canonical frontend or backend;
- configured as a production supervisor MCP/tool source;
- called by the browser, FastAPI runtime, Codex worker, resident agent, or deployed supervisor;
- exposed to an operator, tenant, model, or subagent through the production tool registry;
- used as an authentication, persistence, telemetry, thread, approval, evidence, or lifecycle service;
- relied upon for offline/recovery behavior or treated as a production dependency.

`preview_template` is not ordinary documentation lookup: it creates a hosted preview session and returns remote preview/download URLs. An implementation agent may not call it, open a generated preview, or download/import template output unless the approved spike brief separately authorizes that exact external action and records the intended template, data-flow, source/license review, file allowlist, dependency review, and disposal plan.

Template previews or downloads cannot bypass repository rules. In particular, they cannot introduce mock state, simulated backend behavior, a duplicate application, a second shell/design system, unreviewed generated code/assets, hidden vendor services, or code outside the approved file allowlist. Any selected source must undergo file-level license/provenance review and the same no-mock, security, accessibility, living-documentation, clean-checkout, and independent-audit gates as hand-authored code.

The local stdio `@assistant-ui/mcp-docs-server` package is described by the vendor as a thin proxy to the hosted endpoint. It provides no offline trust advantage and should not be installed or committed for this assessment. If a later implementation environment cannot consume the hosted MCP directly, adding the proxy requires its own exact dependency and lockfile approval.

## UI primitive fit

Assistant UI's strongest fit is its unstyled, composable primitive layer:

- `ThreadPrimitive` for bounded transcript layout and auto-scroll;
- `ComposerPrimitive` for a run-scoped clarification/steer input;
- `MessagePrimitive` and message-part primitives for typed rendering;
- action primitives for copy-only controls;
- accessible error/status patterns;
- optional attachment rendering after a native secure upload contract exists.

The primitives use a Radix-inspired `Root`/part/`asChild` composition model and handle focus, submit behavior, stream state, keyboard interaction, and message context. This is materially closer to the supervisor's custom, calm, data-dense design than importing a pre-styled chat application.

### Base UI versus Radix

Assistant UI's component registry supports both Base UI and Radix-flavoured source components. FastAPI Bookings is already configured as `radix-nova` and imports the `radix-ui` umbrella package throughout shared UI primitives. The spike must therefore use the **Radix flavour or unstyled Assistant UI primitives composed with the application's existing shared components**.

It must not:

- introduce Base UI alongside Radix;
- scaffold a second shadcn design system;
- copy a full Assistant UI starter shell;
- fork shared buttons, dialogs, tooltips, scroll areas, or destructive confirmation primitives under the supervisor package.

If the spike cannot integrate cleanly with existing shared primitives and tokens, that is a rejection signal.

## Capability assessment

| Capability | Assistant UI capability | Supervisor-safe use | Decision |
|---|---|---|---|
| Streaming text | Native runtime support with token/chunk updates, stop state, auto-scroll, and message accumulation | Render only server-allowlisted, disclosure-safe run summaries | Useful in a spike |
| Run/activity state | AG-UI adapter understands run boundaries, activities, state snapshots/deltas, tool calls, custom and raw events | Do not pass raw/open events into the runtime. Pre-validate against the supervisor's closed schema or project native REST state through `ExternalStoreRuntime` | Adapter unsafe by default for this threat model |
| Retry/reload/edit | Handler-driven reload, edit, cancel, and branch features | Omit `onEdit`, `onReload`, and branch handlers. Retry means native idempotency reconciliation/refetch, never regenerate/redispatch | Disable generic controls |
| Reconnect/resume | Some runtimes provide resumable streams; AG-UI exposes run resumption and reload | Native durable run snapshot and sequence cursor remain authoritative. Assistant UI session storage cannot become recovery authority | Custom integration required |
| Attachments | Adapter slots support add/send/remove and progress states | Off by default. Later allow only opaque, expiring, actor/run-scoped artifact references after server-side type/size/content controls | Not in initial spike |
| Markdown | Optional streaming-aware markdown package with tables/code support | Allowlisted markdown subset; raw HTML disabled; remote images/media blocked; links normalized; source/path/secret canaries; copy only | Optional bake-off item |
| Code blocks | Render/copy-oriented code presentation | Read-only redacted snippets only. No execute, apply, edit, open-host-path, or tool action | Narrowly useful |
| Tool rendering | Custom tool cards and status states | May render safe status projections. It must never execute Codex, shell, Git, deployment, booking, SMS, payment, or customer actions in the browser | Presentation only |
| Approvals/HITL | General tool approval UI exists; AG-UI interrupts are explicitly experimental and use unstable/deprecated APIs in current docs | Native REST approval record and `AllowedActionDescriptor` remain authoritative. Assistant UI may only render a native approval view that refetches and calls the existing idempotent endpoint | Do not adopt framework authority |
| Subagents | AG-UI adapter can render nested subagent messages | Current docs state nesting does not survive reload and nested HITL lacks a resume path; supervisor assignments must remain durable first-class records | Status projection only |
| Multi-thread | Available but experimental in AG-UI runtime | Do not use as the mission/work/run hierarchy. One selected durable run maps to one bounded runtime instance | Exclude from production scope |
| Accessibility | Official primitives claim accessible keyboard/focus/error behavior | Helpful starting point, not acceptance evidence. Must pass local keyboard, focus-return, live-region, zoom/reflow, reduced-motion, and axe gates | Test, never assume |

## Runtime choice

### Preferred Assistant UI spike path: `ExternalStoreRuntime`

`ExternalStoreRuntime` is the only current Assistant UI path that aligns cleanly with the accepted ownership model. It can consume messages from an application-owned store and turns UI features on only when corresponding handlers are supplied.

For the spike:

- TanStack Query owns authoritative REST snapshots and refetch state.
- The native supervisor event/recovery layer owns sequences, gap detection, and reconnect.
- A small pure converter maps already-redacted, stable-ID presentation records to `ThreadMessageLike`.
- `onNew`, if enabled, submits a native run interaction using the server-provided action descriptor, expected version, and idempotency key. It never appends an authoritative optimistic message.
- `onEdit`, `onReload`, `setMessages`, thread creation/switching, Assistant Cloud history, feedback, speech, dictation, suggestions, attachments, and frontend tool execution are absent.
- A failed or unknown mutation refetches the durable snapshot and displays `unknown` until reconciled.

This keeps Assistant UI below the application boundary and makes removal straightforward.

### Current `@assistant-ui/react-ag-ui`: blocked

The adapter is attractive because it parses AG-UI events and reconstructs messages, but the current version creates four immediate conflicts:

1. it resolves the pre-1.0 `@ag-ui/client ^0.0.59`, not the accepted `1.0.2` line;
2. its supported event model accepts broad state patches and custom values, passes custom event values through verbatim, ignores `RAW` after parsing, and ignores some invalid/unmatched activity deltas rather than failing closed;
3. interrupt and multi-thread behavior are experimental, while durable approval and recovery are safety-critical here;
4. defaults such as visible reasoning, automatic pending-tool cancellation, full transcript on resume, message reload/edit, and thread-switch cancellation do not match the supervisor's disclosure and exactly-once semantics.

Wrapping the adapter with enough validation and behavior overrides may cost more than mapping the small approved event subset directly. It may enter the bake-off only after an exact version is compatible with AG-UI 1.0 and all prohibited defaults are demonstrably disabled.

## Authentication, recovery, idempotency, and HITL boundaries

Assistant UI supplies presentation/runtime mechanisms; it does not satisfy P0 or the durable supervisor contract.

### Authentication and ownership

- The supplied agent/transport must use the native application `Authorization` header. No token, SSE ticket, actor, tenant, role, project, thread, run, approval, or path claim may be accepted from a query string or trusted browser field.
- FastAPI reauthenticates and reauthorizes every attach, refetch, interaction, interrupt, and approval decision.
- Assistant UI thread/message IDs are presentation correlations only. They cannot create or select a durable resource without the complete actor -> tenant -> project -> mission -> assignment -> run relationship resolving server-side.

### Idempotency and retry

- Assistant UI's reload/regenerate semantics are not supervisor retry semantics and must be disabled.
- A disconnected active stream reattaches to the same durable run or refetches the native snapshot; it never calls dispatch.
- An unknown interaction result is reconciled by replaying the exact native mutation with the same UUIDv4 idempotency key and request fingerprint.
- No optimistic message may be shown as accepted until its durable server record is returned.

### Human-in-the-loop

- FastAPI creates and commits the approval/interaction record before any UI is shown.
- The approval card fetches exact durable ID, action reference, expected version, policy digest, risk, consequences, expiry, and `live_actionable` state.
- Decision submission uses the native approval route, `If-Match`/expected version, and original idempotency key. FastAPI validates and records the result atomically.
- Assistant UI's `respondToApproval`, interrupt metadata, or tool status can be a visual adapter only; none is authority.
- Expired, resolved, superseded, orphaned, mismatched, or cross-scope approvals are disabled and rejected server-side.

## Privacy, cloud, and telemetry

Assistant Cloud is outside the supervisor spike. Its official documentation describes hosted thread/message persistence and run telemetry. When configured, telemetry is enabled by default and can include assistant output, tool arguments/results, errors, and integration metadata; disabling telemetry does not disable cloud thread/message persistence.

The spike must therefore enforce all of the following:

- do not create `AssistantCloud`, `useCloudThreadListAdapter`, anonymous cloud sessions, cloud history/persistence, hosted files, run reports, events, scores, learning, or traces;
- do not provide an Assistant Cloud base URL, project key, API key, auth token, user/workspace header, or environment variable;
- set an explicit server-controlled `assistant_ui_enabled=false` default and a separate build/runtime kill switch;
- deny unexpected outbound hosts and prove no request reaches `assistant-api.com`, `assistant-ui.com`, registry/template endpoints, analytics endpoints, or another vendor service at runtime;
- seed prompts, reasoning, source, path, command, diff, environment, secret, token, synthetic customer/booking/SMS/PII, tool argument/result, and approval canaries and prove their absence from DOM diagnostics, console, storage, network, logs, traces, crash output, and generated artifacts;
- treat imported markdown, links, code, images, and attachments as untrusted content.

The fact that cloud use is optional does not justify leaving it merely “unused by convention.” A production decision needs enforceable absence plus a regression test.

## Direct comparison with CopilotKit headless

| Dimension | Assistant UI narrow path | CopilotKit headless path | Implication |
|---|---|---|---|
| Primary strength | Polished composable chat primitives and a bring-your-own-state runtime | Agent interaction hooks/runtime closely aligned with current AG-UI 1.0 | Assistant UI is stronger as a view layer; CopilotKit is stronger as an AG-UI-native interaction stack |
| Protocol alignment today | `react-ag-ui 0.0.69` pins pre-1.0 `@ag-ui/client ^0.0.59` | Current packages pin AG-UI `1.0.2` | Assistant UI AG-UI adapter cannot pass the current protocol gate today |
| Backend footprint | `ExternalStoreRuntime` or direct browser adapter can avoid a new server | Full supported open-source runtime adds Node 20+ service; direct AG-UI can avoid it | Assistant UI may have lower operational cost if used without cloud/runtime services |
| State abstraction | Assistant Runtime/store plus optional external-store mapping | CopilotKit React state/hooks plus runtime/AG-UI | Both duplicate native state if allowed above the presentation boundary |
| HITL | General approval UI; AG-UI interrupt APIs experimental | Better documented governed actions/interrupt hooks, still not durable authority | Neither replaces native approvals |
| Threads/persistence | Local/external runtime or Assistant Cloud | Local/runtime/Intelligence options | All third-party persistence remains prohibited as authority |
| UI fit | Unstyled primitives can be made visually native | Headless hooks permit fully native rendering | Both can fit; Assistant UI may save more composer/thread work |
| Dependency cost | Smaller headline packages but includes store, cloud client, streaming, Zustand, Radix, Zod, Tap | Larger React package and, at Gate 2, sizeable Node runtime graph | Measure real route and service cost; package size alone is not decisive |
| Cloud/telemetry risk | Cloud is optional, but client is a direct dependency and configured telemetry is on by default | Intelligence/analytics are optional and already prohibited by the existing assessment | Both require no-egress tests and explicit opt-in gates |
| Removal cost | Low only with one adapter module and no cloud/thread ownership | Low only with one adapter module and native fallback | Architectural containment matters more than library choice |

Using both React runtime layers would duplicate message normalization, thread state, streaming state, tool/HITL rendering, cancellation, retry, and event subscription. That would make failure ownership ambiguous and increase bundle/test/upgrade cost. The durable supervisor should select one of these outcomes after the spike:

1. native REST/SSE plus native components;
2. direct AG-UI 1.0 plus native components;
3. Assistant UI primitives with `ExternalStoreRuntime`;
4. CopilotKit headless/runtime, only if its second gate demonstrates unique value.

It should not ship both Assistant UI and CopilotKit headless on the same Runs surface.

## Minimal comparative bake-off

### Preconditions

Do not start until the existing WP-UI-05A prerequisites are independently satisfied: P0 ancestry; durable actor/project/mission/assignment/run ownership; exact idempotency; safe bounded event schemas; accepted run snapshot/recovery; dedicated worktree/branch; exact changed-file allowlist; clean baseline; security reviewer; rollback/removal plan.

### Test surface

Use one hidden, platform-owner-only route and one real, labelled synthetic, read-only Codex author run. It must have no booking, customer, SMS, payment, deployment, or external side effect.

Render the same product slice in independently removable arms:

- **Control:** current native Runs design using REST snapshot plus ticketed passive SSE and, when available, direct exact-pinned AG-UI 1.0 safe projection.
- **Assistant UI arm:** exact-pinned `@assistant-ui/react` with `ExternalStoreRuntime`, existing shared Radix components/tokens, and the same native snapshot/event/interaction adapters. No `assistant-cloud`, `@assistant-ui/react-ag-ui`, generative UI, MCP Apps, frontend tools, thread list, or attachment upload.
- **Existing CopilotKit arm:** the already-specified direct AG-UI protocol gate, then optional smallest headless/runtime value gate. Do not broaden it to a full chat shell.

If a future `@assistant-ui/react-ag-ui` exact version supports the accepted AG-UI 1.0 packages, it may replace the Assistant UI external-store arm for one additional protocol-conformance run. Until then it is not a candidate implementation.

### Common scripted tasks

1. Open an existing running author run and identify current status, phase, last durable sequence, and disconnect state.
2. Observe streamed safe summaries and real progress without viewport jumps or duplicate messages.
3. Force a network disconnect, reload, offline/online cycle, backend restart, and worker restart; recover the same run without redispatch.
4. Submit one harmless run-scoped clarification through the native idempotent action and reconcile a deliberately lost response.
5. Render one durable low-risk synthetic approval, reload, decide once, and verify duplicate/conflicting/expired paths.
6. Navigate by keyboard and screen-reader landmarks through transcript, composer, status, error, and approval states.
7. Exercise long history, markdown/code, malformed content, unknown events, sequence gaps, and prohibited-field canaries.

### Measurable exit criteria

Every criterion is pass/fail; a material security, durability, or privacy failure rejects that arm.

1. **Version compatibility:** exact-pinned packages compile with React 19.2, Vite 8, and TypeScript 6; no peer override, `--force`, `legacy-peer-deps`, duplicate React, or AG-UI version split is required.
2. **One authority:** all durable reads originate from native REST/TanStack Query and all mutations use the native action registry. There is exactly one authoritative message/run store and no browser-created lifecycle record.
3. **Exactly-once behavior:** forced disconnect, reload, double click, concurrent tab, and lost response produce one durable interaction/approval/dispatch effect and no duplicate worker execution.
4. **Recovery:** each failure scenario returns to the same durable run and sequence within 10 seconds on local development infrastructure or presents a truthful terminal/manual-retry state; no unbounded reconnect loop occurs.
5. **Protocol safety:** all accepted events match the closed schema and limits; duplicate events are ignored; gap, lower unseen sequence, unknown type/field, oversized frame, invalid patch, and identity mismatch stop application and trigger bounded native refetch.
6. **Authentication/isolation:** credentials appear only in headers; unauthorized/tenant-admin/cross-scope/guessed IDs are denied without existence leakage; exact-origin CORS and platform-owner success are proven.
7. **HITL durability:** approval survives reload/restarts; its REST version/policy/expiry is shown; duplicate identical decision replays and conflicting/expired/resolved/superseded/orphaned decisions fail deterministically.
8. **No egress:** captured browser/server traffic contains no Assistant Cloud, CopilotKit Intelligence, analytics, learning, registry, CDN, or other unapproved vendor request.
9. **Disclosure:** every prohibited-field canary is absent from rendered content, browser storage, console, network, logs, telemetry, and artifacts.
10. **Accessibility:** zero serious/critical axe findings; no keyboard trap; visible focus; correct focus return; status/error changes announced without flooding; 200% zoom and narrow viewport retain controls; reduced motion honored.
11. **Performance:** the candidate route is lazy-loaded; the main application entry chunk grows by no more than 10 KiB gzip; the candidate's total lazy route JavaScript is no more than 75 KiB gzip larger than the smallest passing arm; a 1,000-item bounded history keeps scripted input and scroll interactions under 100 ms at p95 on the agreed test machine.
12. **Operator value:** three independent scripted runs show at least a 20% median reduction in task time or interaction count versus the native control, with zero increase in wrong-state interpretation or recovery errors.
13. **Dependency governance:** exact lockfile, SBOM, license/notices, provenance/integrity, vulnerability scan, unpacked and emitted size, and upgrade policy are reviewed. No high/critical exploitable finding remains.
14. **Removal:** disabling and removing the candidate adapter leaves native mission, run, approval, evidence, audit, REST, passive SSE, tests, and build passing without data migration.
15. **Repository gates:** focused component/contract/browser tests, full frontend test/build, zero-console/network gate, living-doc verification, clean-checkout verification, independent security review, and QA sign-off pass.

### Selection rule

- Choose **Assistant UI narrowly** only if its arm passes every gate and materially outperforms the native/direct AG-UI control without compromising semantics.
- Choose **CopilotKit narrowly** only if its passing arm provides a distinct capability worth its extra runtime/trust cost.
- Choose **direct AG-UI/native UI** if neither framework produces measured product value.
- Choose **native REST/SSE only** if AG-UI itself adds no material value.
- If Assistant UI and CopilotKit both pass, select the one with fewer runtime authorities, fewer dependencies, lower emitted/runtime cost, better recovery semantics, and better operator results. Do not retain both “for flexibility.”

## Principal risks and controls

| Risk | Severity | Required control |
|---|---:|---|
| Pre-1.0 Assistant UI AG-UI adapter conflicts with AG-UI 1.0 contract | High | Block adapter adoption until exact protocol alignment and conformance evidence |
| Chat runtime becomes a second source of truth | Critical | External-store projection only; REST/TanStack Query and FastAPI remain authoritative |
| Generic reload/edit/cancel starts or mutates work unexpectedly | Critical | Do not supply those handlers; map named native actions only |
| Framework approval is mistaken for authorization | Critical | Durable native approval record, exact version/policy/idempotency, server reauthorization |
| Broad AG-UI custom/state/raw events leak sensitive material | Critical | Closed server schema, pre-runtime validation, fail-closed refetch, canary tests |
| Assistant Cloud sends or persists sensitive content | Critical | Do not instantiate/configure it; no-egress denylist/allowlist test; separate future approval gate |
| Full thread UI turns supervisor into a chat-first product | High | Restrict to Runs pane and optional Intake clarification; no primary navigation or domain ownership |
| Runtime duplication with CopilotKit | High | One-runtime selection rule and removal gate |
| Rapid `0.x` releases break integration | High | Exact pins; deliberate upgrades; full build/protocol/browser/privacy requalification |
| Hidden transitive/bundle cost | Medium/High | SBOM plus real Vite chunk/runtime measurements; lazy route budget |
| Claimed accessibility is accepted without proof | High | Local axe, keyboard, focus, live-region, zoom, reduced-motion, and screen-reader checks |
| Markdown/code/attachments create injection or egress paths | High | Restricted renderer, no raw HTML/remote media, opaque artifact references, server validation |
| Documentation MCP is mistaken for a runtime integration or template generator is allowed to widen scope | High | Developer-only read subset; no production exposure; separately approve every template preview/download and review all resulting source/licenses |

## Required supervisor-specification amendments if this assessment is accepted

Do not modify the foundation specification merely because this assessment exists. If the owner accepts the recommendation, make these amendments before authorizing a spike:

1. **Add Assistant UI as an alternate WP-UI-05A candidate, not a foundation dependency.** It remains prohibited from WP-UI-02 and WP-UI-03.
2. **Add a one-runtime rule.** The accepted product may use Assistant UI, CopilotKit headless, or neither for the active-run presentation layer; using both requires a new ADR proving non-overlapping responsibilities.
3. **Add the current protocol block.** `@assistant-ui/react-ag-ui 0.0.69`/`@ag-ui/client ^0.0.59` is incompatible with the accepted AG-UI 1.0 line and cannot be installed as the production adapter.
4. **Define the Assistant UI boundary.** `ExternalStoreRuntime` may project one selected run; TanStack Query/REST and the native recovery layer remain authoritative; Assistant UI thread IDs are correlations only.
5. **Freeze the disabled feature set.** No Assistant Cloud, remote thread list, local/browser persistence, branching, edit, regenerate/reload, automatic tool cancellation, speech, dictation, suggestions, frontend tools, generative UI, MCP Apps, or attachment upload in the initial spike.
6. **Freeze action mapping.** Composer send, stop, retry, approval, and interrupt controls must map to named native action descriptors and exact idempotent endpoints; absent handlers mean absent controls.
7. **Freeze the design-system choice.** Use unstyled primitives or Radix-flavoured source components with existing shared tokens/primitives; Base UI and a second shadcn foundation are prohibited.
8. **Add cloud/no-egress controls.** Assistant Cloud and telemetry are off and unconfigured, with runtime network tests. Any later cloud proposal requires separate owner, security, privacy, legal, residency, procurement, retention, and incident approval.
9. **Add dependency gates.** Exact versions, reviewed lockfile, SBOM, licenses/notices, provenance, vulnerability scan, bundle/runtime measurements, `0.x` upgrade policy, kill switch, and removal test.
10. **Replace the two-arm adapter wording with the comparative bake-off above.** The native/direct AG-UI control, Assistant UI external-store arm, and existing CopilotKit gates consume the same durable snapshot and safe events, then one or none is selected.
11. **Add Assistant UI-specific conformance tests.** Ensure no optimistic authority, no generic regeneration, safe markdown/code, stable message IDs, bounded history, deterministic errors, and all accessibility criteria.
12. **Keep Intake subordinate to structured workflow.** Assistant primitives may collect clarification text, but promotion/defer/decline/duplicate, mission creation, brief approval, and all lifecycle state remain explicit native forms/actions.
13. **Classify the Assistant UI MCP as developer documentation tooling only.** Permit read-only documentation search during an approved spike, prohibit production/runtime exposure, and require a separate reviewed action before any template preview or download.

## Final recommendation

Proceed with **SPIKE FIRST**, not immediate adoption.

Assistant UI is promising where the supervisor genuinely behaves like a bounded conversation: reading a safe active-run transcript, entering a clarification, viewing progress, and displaying a native durable approval. Its primitives may save meaningful accessibility, streaming, composer, markdown, and scroll work without adding a Node runtime.

It is a poor fit for the supervisor's governing structure and is currently blocked as an AG-UI adapter by its pre-1.0 client dependency and experimental interrupt/thread behavior. The safest evaluation is `@assistant-ui/react` plus `ExternalStoreRuntime`, contained behind one hidden lazy route and the existing native contracts. The bake-off must choose Assistant UI, CopilotKit, direct AG-UI/native rendering, or native REST/SSE—not accumulate all of them.

## Official sources reviewed

- [Assistant UI official repository](https://github.com/assistant-ui/assistant-ui)
- [`assistant-ui-docs` hosted MCP declaration](https://www.assistant-ui.com/mcp)
- [Agent Skills and MCP documentation](https://www.assistant-ui.com/docs/llm)
- [Root MIT license](https://github.com/assistant-ui/assistant-ui/blob/main/LICENSE)
- [Security policy](https://github.com/assistant-ui/assistant-ui/blob/main/SECURITY.md)
- [`@assistant-ui/react` package manifest](https://github.com/assistant-ui/assistant-ui/blob/main/packages/react/package.json)
- [`@assistant-ui/react-ag-ui` package manifest](https://github.com/assistant-ui/assistant-ui/blob/main/packages/react-ag-ui/package.json)
- [`@assistant-ui/react-markdown` package manifest](https://github.com/assistant-ui/assistant-ui/blob/main/packages/react-markdown/package.json)
- [Primitives overview](https://www.assistant-ui.com/docs/primitives)
- [Installation and Radix/Base UI registry selection](https://www.assistant-ui.com/docs/installation)
- [Custom runtime overview](https://www.assistant-ui.com/docs/runtimes/custom/overview)
- [ExternalStoreRuntime](https://www.assistant-ui.com/docs/runtimes/custom/external-store)
- [AG-UI runtime overview](https://www.assistant-ui.com/docs/runtimes/ag-ui/overview)
- [AG-UI runtime options, events, and experimental interrupts](https://www.assistant-ui.com/docs/runtimes/ag-ui/runtime-options)
- [Adapters and attachments](https://www.assistant-ui.com/docs/runtimes/concepts/adapters)
- [Tool UI and approvals](https://www.assistant-ui.com/docs/tools/tool-ui)
- [Multi-agent UI limitations](https://www.assistant-ui.com/docs/tools/multi-agent)
- [Resumable streams](https://www.assistant-ui.com/docs/guides/resumable-streams)
- [Assistant Cloud authentication](https://www.assistant-ui.com/docs/cloud/authorization)
- [Assistant Cloud threads](https://www.assistant-ui.com/docs/cloud/threads)
- [Assistant Cloud messages](https://www.assistant-ui.com/docs/cloud/messages)
- [Assistant Cloud run telemetry](https://www.assistant-ui.com/docs/cloud/telemetry)

