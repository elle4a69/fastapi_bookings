# Open WebUI Fit Assessment for the Integrated Codex Supervisor

**Assessment date:** 15 October 2026  
**Decision:** **REFERENCE ONLY**  
**Target:** the integrated `F:\Projects\fastapi_bookings\codex-control-centre` and the ground-up supervisor UI in the canonical FastAPI Bookings React frontend  
**Anti-Gravity task:** `ccc_open_webui_fit_assessment`  
**Scope:** read-only architecture, licensing, security, supply-chain, and interaction-design assessment. Open WebUI was not cloned, installed, executed, copied, or added as a dependency. No application or specification file was modified.

## Executive decision

Do **not** adopt Open WebUI as the Codex Supervisor application, shell, frontend component source, backend, authentication layer, RBAC authority, model gateway, RAG system, database, or worker runtime.

Use it as a **design-pattern reference only** for a bounded set of interaction ideas:

- a responsive activity/conversation timeline with progressive disclosure;
- a visible, editable queue that distinguishes waiting work from active work;
- searchable model/agent selection with concise capability metadata;
- mobile and installable-PWA layout lessons;
- permission-aware visibility and disabled-reason presentation;
- explicit disconnected, retrying, failed, and attachment/input-blocked states;
- background-completion cues and stable navigation between long-running activities.

These patterns should be independently specified and implemented with FastAPI Bookings components and contracts. No Open WebUI code, assets, branding, page structure, or visual identity should be copied.

The decision is structural:

1. Open WebUI is a broad, chat-first AI platform. The Codex Supervisor is a mission-first engineering control plane whose canonical journey is Mission -> Work package -> Approved brief -> Author run -> Evidence -> Independent audit -> Decision -> Checkpoint.
2. Open WebUI's SvelteKit/Svelte 5 frontend is incompatible with the canonical React 19/Vite application. Reusing components would require a rewrite while importing a second design system and foreign state assumptions.
3. Open WebUI brings its own FastAPI backend, authentication, additive RBAC, database, chat/task persistence, model routing, plugins, RAG/vector storage, analytics, files, channels, calendar, automations, and optional terminal ecosystem. Nearly all of that duplicates or conflicts with FastAPI Bookings authority.
4. Its current multi-license repository requires commit/file provenance. Current Open WebUI-licensed material carries a branding-preservation condition that is incompatible with quietly absorbing it into a FastAPI Bookings-branded supervisor at unrestricted scale.
5. Its broad dependency and integration surface, rapid release cadence, and latest-version-only security support would create a large, permanent upgrade and vulnerability-management obligation for capabilities the supervisor does not need.

## Decision by adoption mode

| Proposed use | Decision | Reason |
|---|---|---|
| Adopt the complete Open WebUI platform | **REJECT** | Replaces rather than complements the native supervisor, duplicates backend/auth/data/model systems, and preserves the wrong chat-first information architecture. |
| Mount Open WebUI beside or inside FastAPI Bookings | **REJECT** | Creates a second application authority, identity/session system, API surface, persistence layer, operational topology, and branding obligation. |
| Replace the canonical supervisor frontend | **REJECT** | SvelteKit/Svelte conflicts with React/Vite; Open WebUI pages organize conversations, models, knowledge, and tools rather than mission/brief/evidence/audit state. |
| Reuse Open WebUI Svelte components or source | **REJECT** | Framework mismatch, strong coupling to Open WebUI stores/APIs, uncertain per-file licence provenance, branding constraints, and high rewrite cost eliminate the benefit. |
| Reuse Open WebUI backend modules | **REJECT** | Duplicates FastAPI Bookings authentication, RBAC, SQLAlchemy/Alembic, model/provider, files, telemetry, RAG, and plugin systems without adding supervisor-domain semantics. |
| Use Open WebUI as a Codex worker or app-server bridge | **REJECT** | It is a generic model/chat platform, not a durable Codex app-server adapter or a mission/evidence/audit orchestrator. |
| Copy its branding, visual design, or assets | **REJECT** | Not required, not product-aligned, and current licence terms protect Open WebUI branding. |
| Learn from interaction patterns | **ACCEPT** | Several mature chat/run interactions translate well when independently implemented under native contracts. |
| Run an Open WebUI integration spike | **REJECT FOR CURRENT ROADMAP** | No unresolved supervisor requirement justifies the added platform. Revisit only for a separately approved general-purpose AI-chat product, not the supervisor. |

## What Open WebUI is today

The official project describes Open WebUI as a self-hosted "home for AI" supporting local and cloud model providers. Its feature set includes conversations, multi-model interaction, model/agent presets, message queueing, memory, notes, channels, automations, calendars, image and voice features, tools, MCP/OpenAPI integrations, RAG, many vector databases, analytics, SSO/LDAP/SCIM, OpenTelemetry, and horizontal scaling.

The current implementation is a sizeable independent platform:

- SvelteKit/Svelte 5/Vite frontend with its own UI dependencies and test/build toolchain;
- Python/FastAPI backend with its own authentication/session stack;
- SQLAlchemy/Alembic persistence supporting SQLite and PostgreSQL;
- optional Redis, object storage, external identity, provider, extraction, and vector-database integrations;
- plugin and tool execution, including administrator-enabled Python execution;
- separate Open Terminal and broader ecosystem integrations for host/container execution.

That breadth is a strength for a general-purpose AI workspace and a liability for this focused control plane. The supervisor already has a canonical application, identity, database boundary, worker adapter, worktrees, run events, approvals, and a planned durable domain. Adopting Open WebUI would import an overlapping product rather than fill a missing layer.

Official sources:

- [Open WebUI repository and feature overview](https://github.com/open-webui/open-webui)
- [Official feature catalogue](https://docs.openwebui.com/features/)
- [Current frontend package manifest](https://github.com/open-webui/open-webui/blob/main/package.json)
- [Current Python package manifest](https://github.com/open-webui/open-webui/blob/main/pyproject.toml)
- [Authentication and access overview](https://docs.openwebui.com/features/authentication-access/)

## Product and information-architecture fit

### Chat-first is not supervisor-first

Open WebUI explicitly makes conversations the core experience. Models, files, tools, knowledge, memory, channels, notes, terminal access, and task lists attach to or surround chats. That is effective for an AI workbench, but it would repeat the central defect identified in the existing Coding Cockpit audit: machinery and chat activity would displace the operator's actual supervisory workflow.

The target supervisor must answer, without reconstructing meaning from transcripts:

1. What mission and work package is active?
2. Which immutable approved brief governs it?
3. Which distinct author and reviewer assignments exist?
4. Which commit-bound evidence covers each criterion?
5. What audit verdict, residual risk, decision, and checkpoint are authoritative?

Open WebUI has chats, tasks, agents, files, tools, memories, and analytics, but those are not substitutes for versioned briefs, assignment independence, commit-bound evidence, criterion-level audits, rework lineage, or durable checkpoints. Mapping these domain records onto chat metadata would hide authority inside generic conversation state and recreate the ambiguity the ground-up UI is intended to remove.

### Ground-up native UI remains the correct decision

The local v2 specification correctly requires:

- five mission-first primary areas: Missions, Work, Runs, Assurance, and Context;
- Operations and Intake as secondary, capability-gated destinations;
- REST snapshots as authoritative server state;
- SSE as a bounded invalidation/attention channel rather than durable truth;
- no global terminal dock, inspector stack, or all-purpose modal workspace;
- no client-invented lifecycle, evidence, verdict, or checkpoint state;
- React shared primitives and FastAPI Bookings visual tokens only.

Open WebUI should not alter those decisions. Its chat timeline may inform the Run Detail activity subview, but it must not become the application shell or domain model.

## Frontend and component-reuse assessment

The canonical frontend is React 19, React Router 7, Tailwind 4, and shared Radix-based application primitives. Open WebUI uses SvelteKit/Svelte 5 and a separate collection of UI, editor, terminal, visualization, media, and state dependencies.

Direct component reuse is therefore poor engineering even before licensing is considered:

- Svelte components cannot be imported into the React tree without a bridge or rewrite.
- A bridge would create two rendering/runtime models, two accessibility and focus systems, duplicated styling, and difficult test ownership.
- A rewrite would no longer be meaningful code reuse; it would preserve foreign interaction and state assumptions while losing upstream update compatibility.
- Open WebUI components are designed around chats, messages, models, knowledge, plugins, files, and its own APIs—not revisioned supervisor aggregates and `allowed_actions`.
- Copying its local primitives would repeat the duplicated-component problem already found in the existing cockpit.

**Decision:** independently implement useful behaviors using the canonical React design system. Do not port Svelte components, CSS, icons, assets, stores, or page layouts.

## Backend, authority, and persistence assessment

### Duplicate platform services

Open WebUI is not a thin UI library. Full or partial platform adoption would introduce parallel versions of:

- FastAPI routing and middleware;
- login, sessions, API keys, SSO/OIDC/LDAP/SCIM, roles, groups, and ACLs;
- SQLAlchemy models, Alembic migrations, SQLite/PostgreSQL ownership, and backup rules;
- model/provider configuration and credentials;
- chat/task/memory/file persistence;
- RAG ingestion, extraction, embedding, reranking, and vector databases;
- tools, functions, Skills, MCP and OpenAPI integrations;
- analytics, logging, OpenTelemetry, webhooks, and notifications;
- optional terminal/filesystem/code-execution infrastructure.

None supplies the missing native supervisor aggregates. Keeping both systems would require identity mapping, dual migrations, cross-database consistency, capability translation, incident response across two products, and a permanent upgrade matrix. Replacing the FastAPI Bookings systems would violate the established application source-of-truth and same-origin authority decisions.

### RBAC mismatch

Open WebUI's documented RBAC consists of Admin/User/Pending roles, additive group permissions, and ACLs for models, knowledge, tools, Skills, notes, folders, and shared chats. Administrators are superusers and, by default or by deployment access, can reach broad instance data. Its documentation explicitly treats administrators as sharing a trust boundary, and its tool/function permission can be equivalent to shell access.

The Codex Supervisor requires a different and narrower model:

- platform-owner-only entry during the development phase;
- server-derived FastAPI actor identity on every request;
- claimed project and mission/programme membership;
- object-level tenant/user/project/mission/run/evidence/audit scope;
- closed action descriptors, expected revisions, idempotency, and state-machine checks;
- distinct author/reviewer assignments and enforced independence;
- separate authorization for deployment, push, external customer actions, and other high-impact effects.

An Open WebUI Admin role, additive group grant, API key, or chat ownership record cannot authorize a supervisor action. Translating the models would be more complex and less trustworthy than using the native v2 facade.

Relevant official sources:

- [Open WebUI RBAC overview](https://docs.openwebui.com/features/authentication-access/rbac/)
- [Open WebUI role model](https://docs.openwebui.com/features/authentication-access/rbac/roles/)
- [Open WebUI group and resource ownership model](https://docs.openwebui.com/features/authentication-access/rbac/groups/)
- [Open WebUI security policy](https://github.com/open-webui/open-webui/blob/main/docs/SECURITY.md)

## Security, data, and telemetry assessment

Open WebUI provides real security controls and a public disclosure process; this assessment does not characterize it as insecure. The problem is that its intended trust model and attack surface are much broader than the supervisor needs.

Important differences and risks include:

1. **Privileged extensibility.** Open WebUI's official security policy treats Tools and Functions as intentional server-side code execution and says the relevant permission is root-equivalent. Importing that subsystem would create another privileged execution route beside the bounded Codex worker adapter.
2. **Admin trust.** Open WebUI administrators are effectively full-instance operators. FastAPI Bookings requires explicit platform-owner and object-scope checks even within its administrative application.
3. **Chat retention and visibility.** Chats, model usage, files, memories, and analytics have their own retention and admin-visibility rules. The supervisor forbids unrestricted prompts, hidden reasoning, model responses, commands, diffs, logs, paths, secrets, and customer data in browser events and telemetry.
4. **Optional external flows.** Providers, web search, community sharing, webhooks, cloud storage, identity providers, extraction engines, and ecosystem integrations expand possible egress. Open WebUI is self-hosted and says it does not send data externally by default, but connected providers necessarily receive relevant prompts/content and optional sharing features can deliberately publish data.
5. **Telemetry semantics.** Open WebUI supports application analytics and OpenTelemetry. The supervisor permits only low-cardinality structural telemetry and requires privacy-canary proof. Importing another analytics model would complicate deletion, retention, and audit completeness.
6. **Shared/open chat behavior.** Open WebUI supports resource sharing and, when enabled, unauthenticated open chat links. No equivalent public/share-link concept belongs in the supervisor.
7. **PWA/offline ambiguity.** An installable shell or cached screen is not offline authority. Dispatch, approval, interrupt, evidence verification, and acceptance must remain unavailable or pending until the native server confirms them.

The native rules remain:

- the browser talks only to same-origin FastAPI v2 APIs;
- FastAPI authenticates and authorizes every read and mutation;
- one first-party worker adapter owns Codex app-server execution;
- no raw run payload crosses the bounded disclosure facade;
- no third-party chat, memory, RAG, analytics, or sharing database becomes supervisor truth;
- offline intent is never displayed as an accepted server action.

## Licensing and branding

The repository is multi-licensed by contribution date and origin:

- early material before the first recorded cutoff is MIT;
- subsequent material through the second cutoff is BSD 3-Clause;
- material contributed or modified after the current cutoff is under the Open WebUI License.

The current Open WebUI License permits source and binary redistribution with conditions, but adds a material restriction against altering, removing, obscuring, or replacing Open WebUI branding unless one of the stated exceptions applies: no more than 50 end users in a rolling 30-day period, specific written permission, or an applicable enterprise licence. Official guidance says v0.6.6 and later use this branding-protection term and are not OSI-approved under that licence.

Consequences for this project:

- a repository-level label is insufficient to establish the licence of a copied component; file and commit provenance would be required;
- adopting the current UI while making it look like the native FastAPI Bookings supervisor could conflict with branding-preservation terms at scale;
- retaining prominent Open WebUI branding would itself conflict with the product requirement for one native FastAPI Bookings visual language;
- pinning to older BSD-licensed v0.6.5 material would freeze the project before later security, accessibility, responsive, and interaction improvements and still would not solve the framework/domain mismatch;
- referencing general interaction ideas without copying code, assets, wording, or trade dress avoids introducing these obligations.

This is an engineering assessment, not legal advice. Any future source reuse would require a file-level legal/licence review before implementation.

Primary licence sources:

- [Current Open WebUI licence](https://github.com/open-webui/open-webui/blob/main/LICENSE)
- [Multi-license notice](https://github.com/open-webui/open-webui/blob/main/LICENSE_NOTICE)
- [Licence history](https://github.com/open-webui/open-webui/blob/main/LICENSE_HISTORY)
- [Official licence explanation and branding guidance](https://docs.openwebui.com/license/)

## Supply-chain and upgrade burden

Open WebUI is actively maintained and widely used, which are positive signals. They do not make a full-platform dependency proportionate here.

The official manifests and feature catalogue show a large frontend and backend dependency surface spanning SvelteKit, editors, terminal rendering, media/vision, authentication, HTTP/WebSocket clients, cryptography, databases, document processing, object storage, model providers, vector stores, and optional execution systems. The release history is frequent, and the official FAQ says major releases are generally targeted weekly with other fixes as needed. The security policy supports `main`, not historical branches.

Adoption would therefore require:

- exact version and image/source digest pins;
- frontend and Python SBOMs;
- per-file licence/provenance review;
- vulnerability and security-advisory monitoring;
- migration and rollback tests for Open WebUI's database as well as the application databases;
- compatibility testing across FastAPI, Python, Node, Svelte, model providers, vector stores, Redis, and optional ecosystem services;
- regression testing of identity, data retention, analytics, plugins, files, PWA, and all exposed routes on every update;
- a plan for urgent upgrades because only the latest supported line receives security attention.

That work is unjustified when the desired deliverable is a focused supervisor and the useful UI behaviors can be implemented natively.

Sources:

- [Open WebUI releases](https://github.com/open-webui/open-webui/releases)
- [Open WebUI update cadence FAQ](https://docs.openwebui.com/faq/)
- [Open WebUI security overview and advisories](https://github.com/open-webui/open-webui/security)
- [Open WebUI development requirements](https://docs.openwebui.com/getting-started/advanced-topics/development/)

## Interaction patterns worth learning from

These are behavior references, not code or visual-design reuse.

### 1. Responsive active-run timeline

Open WebUI demonstrates the value of keeping streamed model/tool activity readable on desktop and mobile while progressively disclosing details. Apply this only inside **Run Detail**:

- group related activity by phase/tool rather than rendering an unbounded transcript;
- keep the current run status and last server-confirmed event visible;
- preserve scroll position when snapshots refresh;
- distinguish new-live activity from older cursor-loaded history;
- collapse large output behind bounded, labelled regions;
- keep approvals and operator input visible as actionable records, not buried chat messages.

The supervisor timeline remains a typed, redacted projection of durable run state. It must never expose raw prompts, hidden reasoning, unrestricted commands/output, secrets, PII, or host paths.

### 2. Visible queue with edit/withdraw semantics

Open WebUI's message queue clearly shows pending messages, supports edit/delete/send-now behavior, survives navigation within the same browser session, and exposes attachment failures that block later messages.

Translate the interaction principle, not its semantics:

- supervisor `queued` is a durable server assignment/run state, not a browser-memory message queue;
- distinguish `queued`, `worker_acknowledged`, `running`, `stopping`, and terminal states;
- allow withdraw only when the server action descriptor permits it;
- show why a queued run is blocked: dependency, worker availability, path lease, approval, budget, or failed input upload;
- never combine queued briefs/instructions implicitly or claim execution before worker acknowledgement;
- an urgent steer is a separate, versioned action against the exact active run, not "send now" against an ambiguous chat.

Official reference: [Open WebUI Message Queue](https://docs.openwebui.com/features/chat-conversations/chat-features/message-queue/).

### 3. Searchable model/agent picker

Open WebUI's searchable picker, pinned choices, access filtering, per-model controls, and clear unavailable-model response are useful. The supervisor equivalent should:

- show only server-approved author/reviewer profiles and models for the selected work package;
- search by display name, role, and capability;
- show availability, provider, context/tool profile, risk restrictions, and estimated limits without exposing credentials;
- preserve the approved brief's recorded model/profile snapshot;
- prevent author/reviewer independence violations at the API, not merely hide options;
- make `unavailable`, `not permitted`, and `not compatible` distinct states with safe reasons;
- avoid a generic "agent marketplace" or community import path.

Official reference: [Open WebUI Models and model switching](https://docs.openwebui.com/features/workspace/models/).

### 4. Mobile and PWA presentation

Open WebUI proves that a dense AI workspace can be installable and usable in a standalone mobile window. Useful lessons are:

- one-pane-at-a-time navigation on small screens;
- safe-area-aware sticky actions;
- background-completion indicators;
- explicit connection status;
- touch-sized controls and no hover-only meaning;
- resumable navigation to the relevant run or decision.

Do **not** add PWA scope to the first supervisor slices. Service-worker caching, update invalidation, notification permission, local storage, and apparent offline capability create security and stale-authority risks. A later PWA decision requires its own threat model and acceptance tests. Browser notifications, if ever added, contain opaque IDs and safe status only and must not carry prompts, source, commands, customer data, or evidence contents.

Official reference: [Open WebUI as a PWA](https://docs.openwebui.com/getting-started/open-webui-as-app/).

### 5. Permission-aware visibility

Open WebUI's roles, group grants, and resource visibility demonstrate the value of tailoring selectors and actions to effective access. Keep the presentation lesson but use native authority:

- render actions from versioned server `allowed_actions` descriptors;
- distinguish hidden because irrelevant from visible-but-disabled because temporarily illegal;
- show safe disabled reasons, risk level, confirmation kind, and stale-revision recovery;
- reauthorize every mutation server-side;
- provide a platform-owner diagnostic explaining effective mission/run access without exposing other tenants or resource existence.

Open WebUI's additive group permissions must not be imported. Supervisor programme membership and object scope remain authoritative.

### 6. Offline, reconnect, and error states

The strongest reusable principle is truthful degradation:

- retain the last confirmed snapshot with a visible stale/disconnected label;
- stop applying live events after a sequence gap or schema error and refetch;
- use bounded exponential reconnect with a fresh one-use ticket;
- distinguish authentication failure, authorization failure, dependency unavailable, worker unavailable, timeout, conflict, and unknown mutation outcome;
- keep failed queued input editable without treating it as submitted;
- use the same idempotency key to resolve unknown outcomes;
- never enable approval, acceptance, interrupt, or dispatch while the server state is not current enough to authorize it;
- provide copyable safe diagnostics without raw payloads.

## Relationship to CopilotKit and Codex Bridge

The three reviewed projects occupy different layers:

```text
Native durable supervisor domain
Mission -> Brief -> Assignment -> Run -> Evidence -> Audit -> Decision -> Checkpoint
                                |
                   FastAPI v2 authority
                                |
       canonical React supervisor UI and native REST/SSE
                                |
      optional future CopilotKit/AG-UI active-run lens
                                |
          first-party Codex app-server worker adapter

Codex Bridge: alternative southbound daemon/client and personal Web UI
Open WebUI: alternative full AI chat/workspace platform
```

- **CopilotKit/AG-UI — `SPIKE FIRST`:** potentially useful as a narrow northbound active-run presentation/interaction adapter after durable v2 prerequisites exist. It must not own missions, approvals, persistence, evidence, or audit.
- **Codex Bridge — `REFERENCE ONLY`:** a southbound app-server daemon/client and personal UI. Learn from writer ownership, bounded history, snapshot/live reconciliation, and truthful queue state; do not add its daemon or UI.
- **Open WebUI — `REFERENCE ONLY`:** a complete AI chat/workspace platform. Learn from interaction polish, responsive layouts, queue visibility, model picking, and error states; do not integrate its platform or source.

Stacking any two or all three would multiply identity, transport, persistence, event, failure, and upgrade boundaries without supplying the native mission/evidence/audit domain. The approved architecture remains one FastAPI authority, one canonical React UI, and one first-party Codex worker adapter.

## Recommended specification amendments

These amendments should be folded into the next accepted supervisor-spec revision or ADR. They do not authorize implementation or dependency changes.

1. **Open WebUI non-dependency ADR.** Record `REFERENCE ONLY`; prohibit Open WebUI runtime, backend, database, auth, RBAC, RAG, model gateway, plugins, terminal, components, CSS, assets, branding, and source imports from the supervisor.
2. **Pattern-not-code rule.** External UI evaluations may contribute behavior requirements and test cases only. Implementations use FastAPI Bookings React primitives and visual tokens and require independent accessibility review.
3. **Chat containment rule.** Conversation/activity UI exists only as a Run Detail subview. Chat/thread metadata cannot represent mission, brief, assignment, evidence, audit, acceptance, or checkpoint authority.
4. **Durable queue contract.** Freeze distinct `queued`, `worker_acknowledged`, `running`, `stopping`, and terminal states; define withdraw/steer eligibility, blockers, ordering, concurrency, and navigation persistence. Explicitly reject browser-memory chat queue semantics for authoritative work.
5. **Agent/model picker contract.** Add a server-filtered searchable picker schema with profile/model ID, role eligibility, availability, tool profile, limits, safe disabled reason, policy digest, and brief/run snapshot provenance.
6. **Timeline usability contract.** Require stable scroll anchoring, newest-window defaults, cursor history, grouped tool activity, unread/new-event markers, bounded output, skeleton/error states, and 320px behavior.
7. **Connectivity-state contract.** Define current/stale/disconnected/reconnecting/exhausted/auth-failed states, last confirmed sequence/time, fresh-ticket reconnect, gap refetch, and action disabling while authority is stale.
8. **Offline-authority invariant.** Cached UI and unsaved drafts are non-authoritative. No offline dispatch, approval, evidence verification, audit submission, acceptance, or interrupt may appear successful before durable server acknowledgement.
9. **PWA/notification deferral.** Keep PWA and browser notifications outside the initial delivery slices. Any later proposal requires service-worker/update, storage, notification privacy, session-expiry, and device-loss threat modelling.
10. **Permission-explanation view.** Add a bounded platform-owner diagnostic showing effective capability/action reasons for the selected resource without adopting additive Open WebUI RBAC or exposing cross-scope existence.
11. **External-pattern provenance.** Design documents may link to Open WebUI behavior as inspiration, but no screenshots, icons, assets, wording, or code enter implementation without explicit provenance and licence review.
12. **Dependency proportionality gate.** A future proposal to adopt a general AI UI platform must identify a concrete native gap, prove material measured benefit, pass licence/branding/security/SBOM review, and show that it does not duplicate the supervisor control plane. Open WebUI currently fails that gate.

## Revisit conditions

Do not revisit Open WebUI for the Codex Supervisor unless the product scope materially changes into a separately approved, general-purpose multi-model AI workspace and all of the following are true:

- the new product genuinely requires Open WebUI's chat, knowledge, model, media, channel, and administration platform rather than only interaction patterns;
- identity, tenant, platform-owner, and per-resource authorization can remain finally enforced by FastAPI Bookings;
- the Open WebUI application remains isolated from supervisor persistence and Codex worker authority;
- current licence and branding obligations are explicitly accepted by the owner and legal reviewer;
- exact versions/digests, SBOMs, vulnerability review, migrations, backups, telemetry, egress, and rollback are approved;
- a separate application/process boundary is accepted instead of embedding or copying it into the native supervisor.

Even then, it should be evaluated as a separate product, not as the supervisor foundation.

## Principal risks

| Risk | Severity | Required response |
|---|---:|---|
| Chat state becomes hidden supervisor authority | Critical | Keep all mission, brief, assignment, evidence, audit, decision, and checkpoint state in native v2 resources. |
| Second auth/RBAC system bypasses platform-owner and object scope | Critical | Do not adopt Open WebUI auth/RBAC; same-origin FastAPI reauthorizes every request. |
| Plugin/tool execution creates a parallel privileged code path | Critical | Do not import Open WebUI Tools, Functions, Open Terminal, or ecosystem execution. |
| Prompts, source, output, files, or customer data enter chat/RAG/analytics/sharing | Critical | No Open WebUI data plane; enforce native bounded disclosure and privacy canaries. |
| Current branding licence conflicts with native integrated UI | High | No code/UI/asset reuse; reference behavior only. Any future reuse gets file-level legal review. |
| Svelte and React runtimes/design systems coexist | High | Canonical React implementation only. |
| Duplicate FastAPI/DB/migration/model/RAG systems drift | High | Retain one native backend authority; reject platform mounting or module reuse. |
| Rapid releases and latest-only support create continuous upgrade pressure | High | Avoid dependency; monitor ideas through periodic read-only reviews only. |
| Chat-first navigation displaces mission/brief/evidence/audit workflow | High | Preserve five-area mission-first IA; timeline is subordinate to Run Detail. |
| PWA/offline shell implies actions succeeded without server authority | High | Defer PWA; require explicit stale/offline state and durable acknowledgement. |
| Generic model/agent picker violates author/reviewer policy | Medium/High | Server-filtered eligible options and backend independence checks. |
| External design copying creates licence or branding ambiguity | Medium/High | Independently specify patterns; do not copy code, assets, screenshots, wording, or trade dress. |

## Final recommendation

**REFERENCE ONLY.** Open WebUI is a capable, mature general AI workspace, but it is the wrong architectural unit for the integrated Codex Supervisor. Full-platform adoption, backend/module integration, and component/code reuse should be rejected.

Continue the approved native sequence:

1. preserve the accepted P0 trust boundary in the target ancestry;
2. implement the durable mission, work-package, brief, checkpoint, assignment, run, evidence, and audit backend;
3. build the ground-up React supervisor shell against native `/api/admin/codex/v2` contracts;
4. independently implement the selected interaction lessons in Run Detail, queue, picker, responsive, permission, and error-state tests;
5. keep CopilotKit/AG-UI as the only optional active-run presentation spike and Codex Bridge as a southbound design reference;
6. do not add an Open WebUI spike or dependency to the supervisor critical path.

## Local sources reviewed

- `artifacts/codex-supervisor/CCC_EXISTING_UI_AUDIT.md`
- `artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_SPEC.md`
- `artifacts/codex-supervisor/CCC_SUPERVISOR_UI_FOUNDATION_REVIEW.md`
- `artifacts/codex-supervisor/CCC_UI_API_CONTRACT_INVENTORY.md`
- `artifacts/codex-supervisor/CCC_ARCHITECTURE_BLUEPRINT.md`
- `artifacts/codex-supervisor/CCC_COPILOTKIT_FIT_ASSESSMENT.md`
- `artifacts/codex-supervisor/CCC_CODEX_BRIDGE_FIT_ASSESSMENT.md`

## Upstream sources reviewed

- [Open WebUI repository/README](https://github.com/open-webui/open-webui)
- [Feature catalogue](https://docs.openwebui.com/features/)
- [Frontend package manifest](https://github.com/open-webui/open-webui/blob/main/package.json)
- [Python package manifest](https://github.com/open-webui/open-webui/blob/main/pyproject.toml)
- [Authentication and access](https://docs.openwebui.com/features/authentication-access/)
- [RBAC overview](https://docs.openwebui.com/features/authentication-access/rbac/)
- [Roles](https://docs.openwebui.com/features/authentication-access/rbac/roles/)
- [Groups and ownership](https://docs.openwebui.com/features/authentication-access/rbac/groups/)
- [Security policy and advisories](https://github.com/open-webui/open-webui/security)
- [Security guidance](https://docs.openwebui.com/security/)
- [Environment/configuration reference](https://docs.openwebui.com/reference/env-configuration/)
- [Message Queue](https://docs.openwebui.com/features/chat-conversations/chat-features/message-queue/)
- [Models](https://docs.openwebui.com/features/workspace/models/)
- [PWA behavior](https://docs.openwebui.com/getting-started/open-webui-as-app/)
- [Analytics and privacy considerations](https://docs.openwebui.com/features/administration/analytics/)
- [Current licence](https://github.com/open-webui/open-webui/blob/main/LICENSE)
- [Multi-license notice](https://github.com/open-webui/open-webui/blob/main/LICENSE_NOTICE)
- [Licence history](https://github.com/open-webui/open-webui/blob/main/LICENSE_HISTORY)
- [Official licence explanation](https://docs.openwebui.com/license/)
- [Releases](https://github.com/open-webui/open-webui/releases)
- [Update cadence FAQ](https://docs.openwebui.com/faq/)
