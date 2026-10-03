# FastAPI Bookings — Native Business Assistant Port Plan

**Document role:** Implementation plan, architectural decision record, delivery brief, and later audit baseline  
**Prepared:** 2 October 2026 (Australia/Sydney)  
**Target application:** `F:\Projects\fastapi_bookings`  
**Reference implementation:** Separate legacy reference application  
**Status:** Proposed — planning authority only; this document does not authorise deployment, production data access, live messaging, or customer contact

---

## 1. Executive decision

FastAPI Bookings should receive a native, tenant-scoped **Business Assistant** by selectively porting proven conversational assets from a separate legacy reference application. This is not a revival of that application, an embedded copy, a runtime bridge, or a dependency on its database or deployment.

“Selective port” means:

1. identify the useful source behaviour, prompts, schemas, voice protocol, UI patterns, tests, and safety rules;
2. copy only those bounded assets into the FastAPI Bookings repository;
3. adapt or rewrite them against FastAPI Bookings authentication, tenancy, persistence, domain services, APIs, styling, and test conventions; and
4. remove every runtime dependency on the legacy reference application before the feature can be accepted.

The Business Assistant is the user-facing conversational layer. It may explain the product, conduct onboarding, help operate the business, retrieve authorised business information, prepare confirmed business-rule changes, assist with approved workflows, and create structured support or engineering tickets. It must never receive source-code, shell, Git, deployment, infrastructure, unrestricted database, or coding-agent execution tools.

The separate coding agent performs engineering work. The user should be able to remain in the Business Assistant conversation while ticket status and safe summaries flow back through that assistant.

---

## 2. Relationship to existing control documents

The current remediation brief states that the obsolete legacy application must not be revived, copied, imported, or inspected for implementation. The repository `AGENTS.md` also limits new operations interface work unless it is separately approved.

This plan proposes a narrow, explicit exception for the Business Assistant only:

- The legacy reference application may be inspected solely as a reference implementation and source of the allowlisted assets in this plan.
- No legacy-source database, secrets, credentials, production data, runtime modules, deployment resources, or unallowlisted application folders may be copied or depended upon.
- The resulting feature must be entirely owned, authenticated, persisted, tested, and deployed by FastAPI Bookings.
- The exception does not reopen the deleted embedded application or broaden the historic bridge phase.

Before implementation begins, the owner should approve this exception and the corresponding wording should be added to `AGENTS.md` and `docs/ANTIGRAVITY_APPLICATION_REMEDIATION_BRIEF.md`. The remainder of those documents continues to apply.

---

## 3. Product outcome

The completed Business Assistant will provide one consistent conversation through which an authenticated user can:

- receive contextual onboarding rather than complete a long static form;
- ask how any authorised part of the application works;
- receive navigation and workflow guidance based on their role and enabled modules;
- inspect safe, tenant-scoped operational information;
- review relevant customer conversations and operational exceptions within their permissions;
- draft business knowledge, policies, tone guidance, and assistant behaviour changes;
- confirm those changes before activation;
- ask for bounded business actions such as preparing or sending approved communications;
- identify suitable customer cohorts for an authorised campaign without silently sending messages;
- create support, bug, feature, access, security, or upgrade tickets;
- hand eligible engineering tickets to the separate coding agent;
- receive user-safe progress and resolution summaries without seeing private code-runner internals;
- use text initially and realtime voice once the same permissions and audit controls are proven; and
- later assist with the website builder through a separately gated website tool pack.

The Business Assistant must answer only from live authorised domain services or approved durable knowledge. Dynamic facts such as availability, bookings, prices, services, customer state, messages, and website publication state must never be treated as remembered literals.

---

## 4. Non-goals

- Do not copy the whole legacy backend or `operations_service.py`.
- Do not run the legacy reference application beside FastAPI Bookings as a required service.
- Do not share databases, cookies, authentication sessions, API credentials, or filesystem state between the applications.
- Do not expose arbitrary tenant, provider, account, conversation, customer, or booking identifiers to model choice.
- Do not give the Business Assistant coding, shell, Git, file-write, deployment, infrastructure, secret-reading, or unrestricted query tools.
- Do not allow the assistant to send bulk messages, create or change bookings, publish a website, change access, or deploy code without the workflow-specific confirmation and authorisation defined for that action.
- Do not treat the existing Resident Agent UI, simulated SMS agent console, or no-op remediation executor as a production coding agent.
- Do not combine this work with unrelated remediation or broad UI redesign.
- Do not hard-code a particular AI or realtime model into the domain design. Model selection belongs in validated server configuration.

---

## 5. Source asset allowlist

The legacy reference repository is currently a working tree with substantial uncommitted changes. Before porting, create a recoverable checkpoint or commit containing the exact reviewed source state. Record its commit or snapshot identifier in this document.

The initial legacy-source inspection/copy allowlist is:

| Source asset | Permitted use | Port treatment |
|---|---|---|
| `backend/services/business_assistant_service.py` | Behaviour, prompt policy, tool schemas, confirmation and ticket concepts | Extract and rewrite against native services |
| `backend/routes/operations.py` | Operations chat and realtime endpoint contracts only | Redesign under authenticated admin Business Assistant routes |
| `backend/models/domain.py` | Operations chat, action, memory, and support-ticket concepts only | Replace with tenant/user-scoped FastAPI models and Alembic migrations |
| `backend/schemas/domain.py` | Relevant chat/realtime request schemas only | Convert to native schemas with strict bounds |
| `backend/services/operations_service.py` | Individually identified realtime and safe diagnostic helper behaviour only | Do not copy wholesale; implement native adapters |
| `frontend/src/OperationsAIChat.tsx` | Conversation UX, status presentation, voice controls, ticket display | Restyle and reconnect to native API client |
| `frontend/src/useOperationsRealtimeVoice.ts` | WebRTC lifecycle and transcript workflow | Reuse after security and failure-path review |
| `frontend/src/operationsRealtimeVoiceProtocol.ts` | Realtime transcript event parsing | Reuse with protocol regression tests |
| Relevant methods in `frontend/src/api.ts` | Request/response shapes | Reimplement through FastAPI Bookings API client/authentication |
| `backend/test_business_assistant.py` | Safety and handoff acceptance cases | Port and expand |
| Relevant realtime tests | Voice protocol and persistence acceptance cases | Port and expand |

Any additional legacy-source asset requires an explicit allowlist update before inspection or use. No source `.env`, database, logs, message bodies, customer records, deployment files, or secrets may be read for this work.

---

## 6. Target architecture

```text
Authenticated user
    |
    v
Business Assistant interface
    |-- text conversation
    |-- optional realtime voice
    |-- ticket/progress cards
    |
    v
/api/admin/business-assistant/*
    |
    +--> Conversation service and tenant-scoped persistence
    +--> Agent runtime with bounded turns, time, tokens and cost
    +--> Contextual tool-pack selector
    +--> Confirmation/policy engine
    +--> Structured audit events
            |
            +--> Onboarding and product-help adapters
            +--> Business knowledge/curator adapters
            +--> Messaging and customer-workflow adapters
            +--> Booking/availability read adapters
            +--> Website-builder adapters (later gate)
            +--> Support-ticket service
                        |
                        v
                  Engineering queue adapter
                        |
                        v
                  Real coding worker
                        |
                        v
                  Safe status/result summary
```

### 6.1 Module boundary

Create a dedicated backend module, expected to resemble:

```text
app/services/business_assistant/
    README.md
    runtime.py
    instructions.py
    tool_registry.py
    confirmation.py
    context.py
    memory.py
    tickets.py
    realtime.py
    adapters/
```

The exact layout may follow existing repository conventions, but the Business Assistant must not be folded into the customer SMS assistant or the coding agent. Those domains can expose typed service adapters to it.

Create a dedicated frontend feature, expected to resemble:

```text
frontend/src/pages/admin/business-assistant/
    README.md
    index.tsx
    conversation.tsx
    use-realtime-voice.ts
    realtime-protocol.ts
    ticket-status.tsx
```

### 6.2 Persistence boundary

Do not store the owner/admin conversation in customer SMS `Conversation` and `Message` rows. Introduce dedicated tenant-scoped assistant records, with names finalised during schema design:

- `BusinessAssistantConversation`
- `BusinessAssistantMessage`
- `BusinessAssistantToolRun`
- `BusinessAssistantMemory`
- `SupportTicket`
- `SupportTicketEvent`

Every applicable record must carry authoritative `tenant_id`; conversations and actions must also record the initiating `user_id`. Provider or location scope must be nullable only where tenant-wide scope is intentional and authorised. Store public-safe ticket text separately from private coding-worker instructions and logs.

### 6.3 Agent loop

Use a bounded function-calling loop rather than free-form autonomous execution:

- maximum tool rounds per user turn;
- maximum input/output tokens;
- request and overall turn timeouts;
- configurable cost/capacity limits;
- circuit breaker after repeated tool failures;
- idempotency key for every mutating tool call;
- structured tool output and explicit errors returned to the agent;
- no hidden retries of externally visible actions;
- conversation checkpoint after each completed turn; and
- safe failure message that preserves the user’s draft and explains the next available action.

The application may record tool names, duration, status, actor, tenant and safe structural metadata. It must not log private prompts, model responses, SMS bodies, customer identities, credentials, or unrestricted tool arguments.

### 6.4 Tool-pack selection

Do not expose the entire platform tool catalogue on every turn. Select a focused pack, normally no more than 5–10 tools, from the user’s request, role, current page, and enabled modules.

Initial packs:

1. **Product help and onboarding** — module discovery, safe configuration reads, onboarding progress, confirmed profile/settings writes.
2. **Business knowledge** — list unresolved curator questions, draft a rule, read back its interpretation, confirm activation, resolve a curator item.
3. **Customer operations** — search authorised conversations, inspect a selected thread, prepare a draft, identify an audience, create a campaign proposal.
4. **Booking operations** — read services, providers and availability; explain booking state; create a proposal for a separately authorised booking workflow.
5. **Support and engineering** — collect evidence, create/deduplicate a ticket, read user-safe status, request owner approval where required.
6. **Website builder** — inspect website state, propose content/layout changes, preview and request publication approval. This pack is disabled until its own acceptance gate passes.

Mutating tools must state exactly what they change, when not to use them, required permissions, confirmation requirements, idempotency behaviour, and possible errors.

---

## 7. Permission and confirmation model

Permission is enforced by backend code, never by prompt text alone.

| Capability | Default | Required control |
|---|---:|---|
| Product explanation and navigation help | Allowed | Authenticated role-aware context |
| Read tenant-scoped settings/status | Allowed where role permits | Server-resolved tenant and field allowlist |
| Draft business rule or message | Allowed | Persisted as draft; no external effect |
| Activate business rule | Confirmation required | Explicit confirmation tied to draft ID and version |
| Send one message | Confirmation required | Recipient preview, permission, idempotency and audit |
| Bulk/campaign messaging | Disabled initially | Separate campaign approval, audience snapshot, limits, opt-out and dry-run review |
| Create support ticket | Allowed | PII/secret sanitisation and deduplication |
| Start ordinary engineering ticket | Policy-controlled | Real worker only; bounded repository/task scope |
| Access/security engineering ticket | Owner approval required before dispatch | Elevated audit and no automatic execution |
| Booking/payment/refund/cancellation | Disabled initially | Separate domain-specific approval design |
| Website publication | Disabled initially | Preview plus explicit publication approval |
| Code, shell, Git or deployment tool | Never available to Business Assistant | Architectural separation |

Confirmation tokens must be bound to the authenticated user, tenant, action type, exact payload hash, expiry time, and object version. A generic later “yes” must not approve a changed or unrelated action.

---

## 8. Coding-agent handoff contract

The Business Assistant creates a structured ticket; it does not design or implement code changes. The ticket contract must include:

- tenant and initiating user IDs;
- ticket category and severity;
- concise title;
- observed behaviour;
- affected product area;
- user impact;
- desired outcome and acceptance criteria;
- sanitised evidence references, not copied customer PII;
- authorisation state;
- stable idempotency/deduplication key;
- coding task ID after accepted dispatch;
- user-safe lifecycle status;
- user-safe resolution summary; and
- timestamps and append-only status events.

The coding worker receives a separately constructed private instruction payload. The Business Assistant and user-facing ticket API must not expose source paths, secrets, raw worker logs, hidden prompts, branch credentials, or deployment tokens unless a deliberately authorised administrator view is later designed.

### 8.1 Hard prerequisite

Automatic dispatch must remain disabled until a real coding-worker path passes an independent acceptance test. The current FastAPI Bookings remediation executor records affected paths and returns successful execution without applying modifications or running verification. The SMS agent console also displays simulated activity. Neither qualifies as the handoff target.

A valid coding-worker implementation must prove, in an isolated worktree or equivalent sandbox, that it can:

1. claim one ticket idempotently;
2. inspect only the authorised repository and scope;
3. create a bounded change;
4. run specified tests and record actual exit results;
5. request independent review;
6. return a commit/diff identifier and sanitised summary;
7. fail honestly when no safe change can be made;
8. never deploy without a separate owner approval; and
9. recover or reconcile after interruption without duplicating work.

Until that gate passes, the Business Assistant may create and track tickets with `awaiting_engineering` status only.

---

## 9. API contract outline

Final schemas must be OpenAPI-documented and tested. Expected routes:

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/admin/business-assistant/conversations` | List the current user’s authorised assistant conversations |
| `POST` | `/api/admin/business-assistant/conversations` | Create a conversation with an idempotent request key |
| `GET` | `/api/admin/business-assistant/conversations/{id}/messages` | Read tenant/user-authorised history |
| `POST` | `/api/admin/business-assistant/conversations/{id}/messages` | Submit a text turn and execute the bounded agent loop |
| `POST` | `/api/admin/business-assistant/conversations/{id}/realtime` | Exchange a WebRTC SDP offer using server-held credentials |
| `POST` | `/api/admin/business-assistant/conversations/{id}/realtime/turns` | Persist an idempotent completed voice turn |
| `POST` | `/api/admin/business-assistant/conversations/{id}/realtime/tools` | Execute an allowlisted realtime tool through the same policy engine |
| `GET` | `/api/admin/business-assistant/tickets` | List user-safe support/engineering tickets |
| `GET` | `/api/admin/business-assistant/tickets/{id}` | Read user-safe status and event history |
| `POST` | `/api/admin/business-assistant/confirmations/{id}` | Confirm one exact pending action |
| `POST` | `/api/admin/business-assistant/confirmations/{id}/reject` | Reject or expire a pending action |

The server must derive tenant and user scope from authentication. Model-generated arguments may reference opaque, short-lived choices issued by the server; they must not choose arbitrary tenant IDs or bypass object-level authorisation.

---

## 10. Delivery work packages

Each work package is a separate branch/commit-sized outcome with its own changed-file allowlist, tests, runtime evidence, review, and documentation update.

### WP0 — Governance, source checkpoint, and contract freeze

**Outcome:** The exception, source snapshot, feature boundary, threat model, and initial API/tool contracts are approved before code moves.

**Required evidence:**

- Legacy-source checkpoint identifier;
- amended `AGENTS.md` and remediation brief wording;
- source asset inventory with hashes;
- target module/file allowlist;
- role/capability matrix;
- data-flow and PII classification; and
- decision naming the real coding-worker integration target.

### WP1 — Tenant-scoped persistence and service skeleton

**Outcome:** Native models, schemas, migration, repositories, and service boundaries exist without an LLM or external side effects.

**Acceptance:**

- tenant/user object isolation tests;
- migrations upgrade and downgrade on a clean test database;
- no reuse of customer SMS conversation rows;
- append-only tool/ticket audit events; and
- module README documents ownership and exclusions.

### WP2 — Text conversation MVP

**Outcome:** Authenticated users can hold a persistent text conversation with bounded model execution and no mutating tools.

**Acceptance:**

- conversation persistence and chronological pagination;
- role and tenant isolation;
- bounded turns/time/tokens;
- failures are explicit and drafts are recoverable;
- no prompt or response leakage to logs; and
- frontend build, lint, accessibility checks and focused end-to-end flow pass.

### WP3 — Product help and conversational onboarding

**Outcome:** The assistant can explain the current application and conduct resumable, role-aware onboarding using live configuration state.

**Acceptance:**

- recommendations reflect enabled modules and current page;
- onboarding progress resumes across sessions;
- no unauthorised settings are revealed or modified;
- writes are draft-first and confirmation-bound; and
- stale/conflicting settings are detected before commit.

### WP4 — Business knowledge and curator workflow

**Outcome:** Users can naturally describe how the business should operate, review the assistant’s interpretation, confirm it, and resolve curator questions.

**Acceptance:**

- draft and activation are separate actions;
- confirmation binds to exact versioned content;
- dynamic facts cannot be stored as static business rules;
- cross-provider/tenant knowledge leakage tests pass; and
- every activation records provenance and actor.

### WP5 — Customer operations and messaging proposals

**Outcome:** The assistant can inspect authorised conversations and prepare individual drafts or audience/campaign proposals without silently sending.

**Acceptance:**

- server-authoritative audience selection and explainable inclusion criteria;
- opt-out, consent, channel, tenant and provider boundaries;
- preview includes exact recipient count and message version;
- duplicate-send protection and rate limits;
- tests use synthetic recipients and cannot contact live providers; and
- live send remains disabled until separately approved.

### WP6 — Support-ticket workflow

**Outcome:** Technical issues become sanitised, deduplicated, persistent tickets visible in the same conversation.

**Acceptance:**

- secret and customer-identifier rejection/redaction;
- duplicate active-ticket detection;
- access/security categories stop for approval;
- user-safe status/event contract; and
- no automatic engineering dispatch while the coding-worker gate is closed.

### WP7 — Real coding-worker connector

**Outcome:** Eligible tickets can be claimed by a genuine isolated coding worker and return verifiable results.

**Acceptance:** All nine requirements in section 8.1 pass with actual filesystem change, test output, interruption recovery, independent review, and deployment separation evidence. Simulated success is a release blocker.

### WP8 — Realtime voice

**Outcome:** Text and voice share the same permissions, conversation history, tools, confirmation policy, and audit trail.

**Acceptance:**

- API credentials remain server-side;
- SDP size/content checks and origin/auth protection;
- transcript turns are chronological and idempotent;
- interrupted and partial transcripts do not create false actions;
- tool errors are returned to the voice session;
- voice cannot access a broader tool set than text; and
- microphone denial and upstream failure degrade cleanly to text.

### WP9 — Application-wide presence

**Outcome:** The Business Assistant is reachable throughout the authenticated application through a responsive drawer or panel, with an optional full-page history view.

**Acceptance:**

- current-page context contains route/module identifiers only, not scraped secrets or uncontrolled page contents;
- keyboard, screen-reader, focus management and mobile behaviour pass;
- conversation persists while navigating; and
- the assistant does not obstruct destructive-action confirmations or security notices.

### WP10 — Website-builder tool pack

**Outcome:** The assistant can inspect website state, propose bounded edits, generate a preview, and request publication approval.

**Acceptance:**

- draft/preview/publish are separate states;
- generated content is sanitised and tenant-scoped;
- version conflict and rollback behaviour is defined;
- asset, domain and publication permissions are enforced; and
- no publication occurs from ordinary conversational confirmation alone.

### WP11 — Hardening, migration, and staged rollout

**Outcome:** The feature is independently audited and introduced without production surprise.

**Stages:** disabled → internal synthetic tenant → owner-only staging → selected non-production tenant → separately approved production rollout.

**Acceptance:**

- security and tenant-isolation review;
- prompt-injection and tool-confusion tests;
- cost, latency, timeout and failure-budget measurements;
- voice and text parity tests;
- recovery and reconciliation tests;
- audit-log privacy inspection;
- rollback procedure demonstrated; and
- no dependency on the legacy reference application remains.

---

## 11. Anti-Gravity execution model

Anti-Gravity’s primary agent must act as project manager and reviewer. It must not implement the work packages itself.

For each work package it must:

1. define the exact objective, acceptance criteria, changed-file allowlist, risks and non-goals;
2. assign implementation to a specialist subagent suited to that domain;
3. assign testing/security review to a different specialist subagent where practical;
4. prevent multiple subagents from editing overlapping files concurrently;
5. review the actual diff, tests, runtime evidence and documentation;
6. reject simulated, disconnected, untested or falsely reported implementations;
7. require correction by the responsible specialist rather than silently completing its code; and
8. close the work package only after the evidence is reproducible.

Suggested specialist assignments include database/migrations, backend agent runtime, authentication/tenant isolation, knowledge/curator integration, messaging safety, coding-worker integration, realtime voice, frontend/accessibility, and independent verification.

The project manager must not dispatch all work packages simultaneously. Later packages depend on contracts and gates established by earlier work.

---

## 12. Verification strategy

Every work package must add focused regression coverage. The eventual suite should include:

- unit tests for instructions, tool schemas, confirmation binding and sanitisation;
- API tests for authentication, tenant isolation, object-level authorisation, schemas and failures;
- migration tests on clean and upgraded databases;
- integration tests using real native services with synthetic data;
- idempotency and concurrency tests for messages, tools, tickets and worker claims;
- prompt-injection tests where customer content attempts to invoke admin/coding tools;
- realtime event-ordering, interruption and duplicate-turn tests;
- frontend component and accessibility tests;
- end-to-end text, voice, onboarding, rule-confirmation and ticket journeys; and
- independent negative tests proving the Business Assistant cannot access code, shell, Git or deployment capabilities.

Baseline verification commands should use the repository’s supported environment and be recorded per work package, normally including focused `pytest`, frontend tests, `npm run lint`, `npm run build`, migration checks, and a relevant authenticated runtime smoke test. A successful import or mocked response is not sufficient proof.

---

## 13. Observability and audit requirements

Record:

- request/turn ID;
- tenant and actor IDs using the repository’s safe identifier policy;
- selected tool pack and invoked tool name;
- outcome category, duration and retry count;
- confirmation ID and action status;
- ticket/worker lifecycle transitions; and
- token/cost counters where available without recording content.

Do not record:

- system/developer prompts;
- raw model responses;
- customer or user message bodies;
- phone numbers, emails, addresses or booking notes;
- credentials, tokens, cookies or authorisation headers;
- unrestricted tool arguments/results; or
- private coding-worker logs in user-visible tickets.

Dashboards and alerts should detect tool failure rates, stuck turns, duplicate claims, confirmation mismatches, tenant-scope rejections, ticket backlog, worker interruption, realtime failures, and unusual cost growth.

---

## 14. Principal risks and controls

| Risk | Control |
|---|---|
| Blindly copying a tightly coupled service | Source allowlist; native adapters; no wholesale `operations_service.py` copy |
| Cross-tenant data exposure | Server-derived scope, dedicated models, object-authorisation and adversarial tests |
| Business Assistant begins coding | No coding tools in registry; separate ticket contract; negative capability tests |
| Prompt injection through customer messages | Treat retrieved content as untrusted data; tool policy enforced outside prompt |
| “Yes” confirms the wrong action | Payload-hashed, expiring, version-bound confirmation record |
| Duplicate messages/actions | Idempotency keys, unique constraints, transactional claims and reconciliation |
| Simulated coding worker reports success | Hard gate requiring actual diff, tests and independent verification |
| Too many tools reduce reliability | Contextual 5–10 tool packs and explicit schemas/errors |
| Voice receives broader permissions | Shared policy/tool executor for text and voice |
| Agent memory becomes stale or invasive | Selective approved memory; live domain reads for dynamic facts; retention controls |
| Costs or loops run away | Turn, step, token, timeout and cost caps with circuit breakers |
| Source changes during port | Recorded source checkpoint and hashed asset inventory |

---

## 15. Definition of done

The native Business Assistant is complete only when:

1. it runs wholly inside FastAPI Bookings with no legacy-source runtime dependency;
2. conversations, memory, tools, confirmations and tickets are tenant/user scoped;
3. text and voice use the same policy engine and persistent conversation;
4. onboarding, product help and approved business workflows use live native services;
5. mutating actions are idempotent, auditable and confirmation-bound;
6. the assistant has no coding or deployment capability;
7. engineering tickets reach a proven real coding worker through a typed queue contract;
8. worker progress returns as safe ticket events and conversation summaries;
9. access/security and production deployment remain explicitly owner-gated;
10. all focused, integration, isolation, accessibility and runtime acceptance tests pass;
11. privacy-safe observability and recovery procedures are demonstrated;
12. module and architectural documentation is current; and
13. an independent reviewer can reproduce the evidence from a clean checkout.

---

## 16. Approval decisions required before WP0 closes

The owner should confirm:

1. approval of the narrow legacy-source exception described in section 2;
2. whether the first release is owner/admin-only or includes other tenant roles;
3. which real coding-worker package/service is the intended handoff target;
4. whether ordinary bug/feature tickets may dispatch automatically or require approval first;
5. whether realtime voice belongs in the first release or follows the text MVP;
6. whether messaging tools stop at drafts in the first release; and
7. whether website-builder assistance is part of the initial programme or a later extension.

Unless separately approved, the safest defaults are: owner/admin-only; text-first; ticket creation without automatic dispatch; messaging drafts only; website tools deferred; and no production rollout.
