# Native Business Assistant Threat Model and Capability Matrix

**Status:** WP0/WP11 prerequisite — design and acceptance baseline; not implementation authority  
**Prepared:** 2 October 2026 (Australia/Sydney)  
**Applies to:** the native Business Assistant planned in `BUSINESS_ASSISTANT_NATIVE_PORT_PLAN.md`  
**Companion evidence:** `BUSINESS_ASSISTANT_REFERENCE_INVENTORY.md`, `AGENTS.md`, and the remediation control brief

## 1. Security objective and non-negotiable invariants

The Business Assistant is an authenticated, tenant-scoped conversation feature. It helps an authorised user understand and operate the product, prepares limited drafts, and creates structured support tickets. It is not an authority to bypass ordinary product permissions or a path to execute engineering work.

These invariants apply to every text, voice, tool, confirmation, and ticket path:

1. The server, not the model or browser, derives the actor, tenant, role, enabled modules, and object permissions.
2. Untrusted text and retrieved content can inform a response but cannot grant a capability, widen scope, change policy, or confirm an action.
3. Every externally visible or persistent mutation has a named policy, idempotency behaviour, audit event, and—where required—an exact, expiring, one-use confirmation.
4. Text and voice use the same tool registry, authorisation, confirmation engine, data classification, audit policy, and tenant/user conversation boundary.
5. The Business Assistant has no source-code, shell, version-control, deployment, infrastructure, secret-reading, unrestricted-database, or coding-worker execution capability.
6. A ticket is a request for separate engineering work, not authority to begin, approve, or deploy that work.
7. Logs, telemetry, user-safe ticket views, and model context contain only allowlisted data appropriate to their recipient and purpose.

## 2. Identities, authority, and tenant model

| Identity or component | Trust level | Permitted authority | Must never control |
|---|---|---|---|
| Authenticated user | Authenticated but input is untrusted | Act within their role and tenant; read their authorised conversations; create permitted drafts/tickets. | Tenant selection, role elevation, another user’s data, direct worker execution, or confirmation of a changed payload. |
| Owner/administrator | Elevated authenticated user | Role-authorised settings and confirmation flows; approval gates defined by product policy. | Cross-tenant data, unlogged external action, production deployment through conversation, or bypassing a required separate approval. |
| Business Assistant model | Untrusted decision-support component | Produce text and select from the server-issued, contextual tool pack. | Authentication, authorisation, identifiers outside issued choices, secrets, direct external effects, worker control, or policy changes. |
| Browser and voice client | Untrusted client | Present authorised data, submit a user turn, offer realtime media, and display server results. | Provider credentials, tenant/role claims, ticket privacy tier, tool result fabrication, or policy enforcement. |
| FastAPI application services | Trusted enforcement point | Authenticate, resolve scope, retrieve allowlisted context, validate tools, persist records, enforce confirmation/idempotency, and emit safe audit events. | Treat model output or client claims as authority. |
| Model/realtime provider | External processor | Receive only minimised, authorised request context under validated server configuration. | Receive secrets, unrestricted records, tenant-wide exports, or application credentials in browser payloads. |
| Coding worker | Separate, least-privilege execution boundary | Claim only an eligible ticket after its independent acceptance gate; produce actual bounded evidence. | Read customer/private assistant data, impersonate a user, deploy, or make the Business Assistant a code executor. |
| Auditor/reviewer | Authorised read-only role | Review approved audit records, diffs, test evidence, and user-safe ticket history. | Access hidden prompts, raw private content, worker secrets, or mutate operational state merely by reviewing. |

Tenant ID, user ID, role, provider/location scope, and current object permission must be established by the authenticated server request before the conversation runtime or any tool sees an object. A model may receive an opaque, short-lived choice issued by the server; it must not select arbitrary identifiers.

## 3. Data classification and handling rules

| Class | Examples | Assistant/context rule | Storage, display, and logging rule |
|---|---|---|---|
| Public product information | Help text, documented workflow labels, non-sensitive feature availability. | May be supplied in bounded product-help context. | Ordinary application records; telemetry still uses structural fields only. |
| Tenant operational data | Authorised services, provider/location choices, booking state summaries, onboarding state, enabled modules. | Retrieve live and minimise to the current request; never treat dynamic facts as remembered literals. | Tenant-scoped persistence and object-level checks; no unrestricted list/export tool. |
| Personal/customer data | Names, phones, emails, addresses, message bodies, booking notes, conversation content. | Exclude by default. A separately approved customer-operation tool may return only the smallest authorised field set. Treat all retrieved text as untrusted. | Do not put in prompts, logs, traces, telemetry, or user-safe engineering tickets unless a separately approved, minimised workflow requires it. |
| Sensitive business knowledge | Draft policies, preferences, unpublished website content, internal operational rules. | Versioned, scoped, provenance-labelled, and retrieved only when authorised. | Separate from ordinary history; retain/review under defined policy; do not cross tenants/providers. |
| Security and access information | Access requests, security observations, incident details. | Create a sanitised ticket only; no automatic dispatch. | Elevated visibility, append-only audit, owner approval before any worker dispatch. |
| Secrets and credentials | API keys, tokens, cookies, headers, database URLs, deployment secrets. | Never include in model context, tool schemas, browser payloads, tickets, or memory. | Never log, display, commit, trace, or return; server configuration only. |
| Private engineering material | Worker instructions, raw logs, source paths, branch/commit metadata, review details. | Never include in assistant context or public ticket text. | Separate protected store/view; translate only approved safe lifecycle status and resolution summary. |

## 4. Trust-boundary flow

```text
Authenticated browser / voice client
        |  untrusted text, SDP, realtime events, request IDs
        v
FastAPI authentication + tenant/user/role resolution
        |  server-issued scope and opaque authorised choices
        v
Conversation runtime + contextual tool-pack selector
        |                    |
        | bounded context    | validated tool request
        v                    v
External model/realtime service    Native domain adapters and confirmation engine
        |                    |
        | untrusted output   | authorised, minimised result
        +---------+----------+
                  v
          Native conversation, audit, and ticket records
                  |
                  v
        Separate coding-worker queue (gated; no direct model control)
```

Every downward transition must validate the actor and scope anew at the receiving service. Every upward transition must be sanitised for its recipient; model output, tool output, worker result, and realtime event payload are data, never authority.

## 5. Capability matrix

| Capability | First-release state | Required server controls | Required user control | Acceptance evidence |
|---|---|---|---|---|
| Product help/navigation | Enabled for authorised roles | Role-aware current-page/module context; field allowlist; no hidden admin settings. | None beyond normal authentication. | Same user receives only enabled/authorised module guidance; unauthorised request is denied. |
| Conversational onboarding | Enabled, owner/admin first | Tenant/user-scoped progress; live configuration reads; draft-first settings writes. | Exact confirmation for a resulting change. | Resume progress; reject cross-user/tenant access; stale version blocks activation. |
| Business knowledge draft | Enabled | Scoped draft record, provenance, content limits, sanitisation, object permission. | Review interpretation, then confirmation. | Draft has no live effect before confirmation and cannot cross scope. |
| Business knowledge activation | Disabled until confirmation engine exists | Actor/tenant/payload/version/expiry-bound one-use confirmation; transaction and audit event. | Explicit matching confirmation. | Wrong actor, tenant, payload, expired token, stale version, and replay all fail. |
| Booking/availability reads | Enabled only after adapter acceptance | Server-resolved scope, read-only adapter, response field allowlist, live authoritative service. | None beyond role permission. | No arbitrary identifiers; dynamic result is current and tenant-scoped. |
| Customer conversation read | Deferred | Separate approved tool pack, object authorisation, minimised fields, content treated as untrusted. | Authorised user request only. | Injected message cannot change tool policy; cross-tenant/thread reads fail. |
| Message/campaign proposal | Draft-only and deferred | Consent/opt-out/channel checks, audience snapshot, rate and idempotency policy. | Separate review and approval. | No provider call before the dedicated send gate; synthetic-recipient tests only. |
| Support ticket | Enabled | Sanitisation, data-classification checks, dedupe key, tenant/user ownership, append-only events. | Create request. | Private data rejected/redacted; duplicate active ticket reuses or reports existing item. |
| Engineering dispatch | Disabled until worker gate passes | Policy category check, idempotent claim, isolated worker contract, safe status mapper. | Owner approval for access/security; ordinary dispatch policy explicitly configured. | Actual isolated change, test output, independent review, interruption recovery; no simulated success. |
| Text turn | Enabled after MVP gate | Conversation ownership, bounded rounds/tokens/time/cost, safe error, idempotency. | Submit text. | End-to-end authorised turn persists in order; duplicate request has no duplicate side effect. |
| Realtime voice | Deferred until text controls pass | Same conversation/policy engine, authenticated SDP exchange, origin/content-size checks, server-held provider credential, transcript idempotency. | Microphone permission. | Voice cannot invoke a tool unavailable to text; denied microphone and upstream failure fall back safely. |
| Website changes/publication | Deferred | Separate website tool pack, draft/preview/publish states, version/rollback, asset/domain permissions. | Explicit publication approval outside ordinary conversational acknowledgement. | Draft cannot publish; conflicts/rollback and scope checks pass. |
| Source, shell, Git, deployment, secrets, unrestricted queries | Never enabled | No registry entry, route, token, or adapter; negative capability tests. | Not applicable. | Attempts through text, voice, crafted tool calls, and ticket content are rejected without side effects. |

## 6. Threat scenarios, controls, and testable evidence

| ID | Scenario | Required control | Evidence required before release |
|---|---|---|---|
| TM-01 | A client supplies another tenant, user, provider, conversation, booking, or ticket ID. | Resolve tenant/user/role from authentication; perform object-level checks in every route and adapter; use server-issued opaque choices for model tools. | API and integration tests for every object type show cross-tenant and cross-user denial; no model argument can widen scope. |
| TM-02 | A user, customer message, knowledge item, web result, or tool result instructs the model to ignore policy or use hidden tools. | Treat all such content as untrusted data; isolate it from instructions; only server registry/policy may select a tool or execute an effect. | Adversarial text cases prove no hidden tool, privilege escalation, confirmation bypass, or data expansion. |
| TM-03 | The model confuses similarly named tools or supplies malformed/extra arguments. | Contextual closed-schema tool pack; allowlisted tool name; strict validation; reject unknown/extra arguments; server-resolved IDs. | Contract tests cover unknown names, extra fields, malformed values, stale opaque choices, and tool/result errors. |
| TM-04 | A generic “yes”, delayed reply, replay, or another user confirms an action. | Persist one-use confirmation with actor, tenant, action type, canonical payload hash, target version, expiry, and consumed state. | Tests reject generic/mismatched/expired/replayed/stale/wrong-user confirmations and accept only the exact intended action once. |
| TM-05 | A ticket leaks personal data or private engineering details to a user or worker. | Classify/sanitise ticket input; separate user-safe ticket fields from protected worker payload/logs; use distinct serializers and access policies. | Tests attempt personal data/secrets in ticket text; user API never returns worker metadata; worker lacks customer/private-assistant access. |
| TM-06 | Voice bypasses text safeguards through SDP, transcript ordering, a function-call event, or a different tool list. | Server-authenticated SDP exchange; event size/type checks; shared registry/confirmation executor; deterministic transcript persistence; same conversation authorisation. | Parity suite compares text/voice permissions; duplicate/out-of-order events persist one ordered pair; forged/oversized events fail closed. |
| TM-07 | Logs, telemetry, errors, or diagnostics capture content/secrets. | Allowlisted low-cardinality structural telemetry only; redacted error mapping; no raw prompts/responses, messages, PII, tokens, or headers. | Privacy inspection of emitted logs/traces/metrics under synthetic secret/PII inputs; collector verification is required. |
| TM-08 | Model output causes direct code execution, deployment, or unsafe worker dispatch. | No coding/deployment tools; ticket-only handoff; worker acceptance gate; separate queue identity; owner deployment gate. | Negative capability suite plus worker evidence showing real diff/test/review and that dispatch remains unavailable until the gate passes. |
| TM-09 | Retries or concurrency duplicate a message, tool mutation, ticket, confirmation, or worker claim. | Idempotency keys, database uniqueness, transactional claims, object version checks, and reconciliation. | Concurrent/retry tests demonstrate one authoritative effect and explainable duplicate response/recovery. |
| TM-10 | Bounded agent execution becomes excessive, stuck, or silently retries an external effect. | Tool-round/token/time/cost caps, circuit breaker, explicit timeout state, no hidden retry of external action, recoverable draft. | Load/failure tests show cap enforcement, safe failure message, persisted draft, and no repeated external effect. |

## 7. Logging and audit contract

The minimum safe event contains: request/turn ID, tenant and actor identifiers under the repository’s safe identifier policy, selected tool-pack ID, invoked tool name, outcome category, duration, retry count, confirmation ID/state, ticket/worker lifecycle state, and non-content token/cost counters when available.

Never record system/developer instructions, raw model output, raw user/customer content, phone/email/address/booking-note values, credentials, headers, cookies, opaque authorisation tokens, unrestricted tool arguments/results, or private worker logs. User-visible tickets receive only a safe lifecycle status and an approved resolution summary.

Audit events must be append-only. Audit reads require the same tenant/user or specifically designed auditor permission, and audit data must not become assistant context merely because it exists.

## 8. Coding-worker separation contract

The Business Assistant can create and read a user-safe ticket. It cannot create a branch, access a repository, invoke a worker, read a worker log, approve a review, or deploy a result.

Before dispatch is enabled, the coding-worker integration must independently demonstrate: idempotent claim; repository/task scope restriction; actual bounded filesystem change; actual test exit results; independent review; safe commit/diff identifier handling; honest failure; interruption reconciliation; and a separate owner-controlled deployment step. Until then, all eligible tickets remain `awaiting_engineering`; access and security tickets require explicit owner approval even after the worker gate exists.

## 9. Release evidence checklist

The project manager may advance a work package only when its evidence identifies the control IDs above and includes:

1. exact changed-file allowlist and reviewed diff;
2. focused unit, API, migration, integration, and adversarial tests using synthetic tenant-scoped data;
3. authenticated runtime proof for any enabled route or tool;
4. privacy inspection for any new logging, telemetry, model context, ticket field, or error path;
5. text/voice parity evidence before voice is enabled;
6. idempotency/concurrency proof for mutations and worker claims;
7. independent reviewer results for the coding-worker gate; and
8. rollback/recovery evidence appropriate to the work package.

## 10. Open gates and decisions

- The source checkpoint must be recorded before source assets move beyond review.
- First release remains owner/admin text-first unless separately approved.
- The real coding-worker target is not yet named or accepted; automatic dispatch remains disabled.
- Messaging remains draft-only and website tools remain disabled until their dedicated controls and acceptance gates are approved.
- Realtime voice remains disabled until the text policy engine, privacy controls, and voice-parity tests are demonstrated.

## 11. Document verification

- This document defines controls and evidence requirements; it does not create code, routes, credentials, provider calls, or production access.
- It uses “legacy reference application” where historical context is necessary and does not use the disallowed legacy product name.
