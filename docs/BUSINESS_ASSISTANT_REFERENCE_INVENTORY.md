# Business Assistant Reference Asset Inventory

**Purpose:** A bounded WP0 inventory of patterns that may be reimplemented natively in FastAPI Bookings. This is evidence for planning and review, not permission to copy a whole application, create a runtime dependency, use legacy credentials, or begin implementation before the governing approvals are complete.

**Prepared:** 2 October 2026 (Australia/Sydney)  
**Reference designation:** legacy reference application  
**Inspection boundary:** only the file allowlist in the native port plan was inspected. No environment files, databases, logs, deployment material, customer records, credentials, or unallowlisted source paths were read.

## 1. Reference snapshot facts

The inspected working tree is not a stable source snapshot. It was on branch `codex/fix-knowledge-startup-index`, at commit `08db4de75696903628385b945c79968031909a5a` (commit timestamp `2026-09-22T09:46:51+10:00`), with numerous modified and untracked files. The listed hashes identify only the specifically inspected assets; they do not identify a releasable source state.

Before any implementation work, the owner must select a recoverable source checkpoint and record its immutable identifier here. Do not treat the commit above as an approved checkpoint merely because it was observed during this inventory.

| Relative asset | SHA-256 | Size (bytes) | Observed UTC modification time |
|---|---|---:|---|
| `backend/services/business_assistant_service.py` | `16AFD490C2B77944F21BC6FCA05F8166DA7EE96439C4949D24C8EF74E428788F` | 21,999 | 2026-09-23T02:51:52.7685329Z |
| `backend/routes/operations.py` | `AC5565F62DA3F51BBEBFF5C5100C12AC3EDA9E8643A1C15D75F8FAF1C49BF9E1` | 19,566 | 2026-09-18T23:28:38.4202041Z |
| `backend/models/domain.py` | `0EB812EF0E59C32503B0E9D84476FC8ADDE11253919975493DFB38A1DE23F2BC` | 13,880 | 2026-09-18T23:22:47.9900406Z |
| `backend/schemas/domain.py` | `B52778450142056D8671AE4FFB16E6002CF8D918588EBE92BAE8DB91A6239AD3` | 18,688 | 2026-09-23T09:01:00.2734025Z |
| `backend/services/operations_service.py` | `444F5D57B09EAB3C55D24FB4EEBA634E3D4FFE5FB8C20FDDA00DAC04133E9F48` | 241,355 | 2026-09-23T02:47:57.0681955Z |
| `frontend/src/OperationsAIChat.tsx` | `A22D1C88888D5B0C41742B9A3EC36D0FC2C5F95F554C10CB8F906144CB7BE26B` | 16,057 | 2026-09-18T23:31:00.3366986Z |
| `frontend/src/useOperationsRealtimeVoice.ts` | `025F23B8EEE98701D043B422BEB5520CAB68F1A84F1BBDB8A9F528896A55704F` | 11,216 | 2026-08-30T04:38:36.2766237Z |
| `frontend/src/operationsRealtimeVoiceProtocol.ts` | `DEDA008B1EBDC9F7FA699BE8EFF377AB1850AAE29A0C4C6C082CAF31D4EEA100` | 6,252 | 2026-08-30T04:38:36.2746239Z |
| `backend/test_business_assistant.py` | `24211C91D5C885A4CDA8CE04896457BAB3F12A9F9D16DC2FE0F0B91D5ED51B97` | 5,118 | 2026-09-18T23:27:19.3739635Z |
| `backend/test_operations_ai_chat.py` | `20F626EABC1038026486E5540A0D690724D4F6FEE942BDA0A71FA0D7047CCF42` | 55,525 | 2026-09-18T22:04:06.7396601Z |

## 2. Reusable behavioural assets

### 2.1 Conversation boundary and tool policy

`backend/services/business_assistant_service.py` contains the clearest reference for the product boundary:

- a user-facing role focused on onboarding, business knowledge, product help, controlled customer operations, and structured technical handoff;
- an explicit allowlist of business tools rather than a general tool catalogue;
- explicit exclusions for source code, shell, version control, deployment, infrastructure, and developer settings;
- tool schemas with bounded string lengths, closed object shapes, and named confirmation inputs;
- separation between drafting a business rule and activating it; and
- sanitised support-ticket creation with categories, validation, duplicate detection, and a safe public result.

The reference’s confirmation helper accepts a limited set of affirmative phrases. That is useful evidence of the intended two-step experience, but it is insufficient for the target system. The target must use a server-side confirmation record bound to actor, tenant, action type, exact payload hash, expiry, and object version.

### 2.2 Bounded model turn

The operations route shows a practical bounded turn pattern: persist a user message, load a bounded history, call the model with an explicit tool list, execute function calls through a tool gateway, cap tool rounds at six, then persist the final reply. It also disables provider-side storage for the request.

Port the pattern, not its implementation. The target runtime needs server-configured model selection, request/turn timeout, token and cost limits, typed tool results, tracing with content redaction, conversation ownership checks, and transaction-safe idempotency.

### 2.3 Durable conversation, memory, action, and ticket concepts

The reference domain models establish four useful concepts:

| Reference concept | Useful invariant | Native replacement |
|---|---|---|
| `OperationsChatMessage` | A conversation message has a role, content, stable ID, and chronological timestamp. | `BusinessAssistantConversation` plus `BusinessAssistantMessage`, each carrying authoritative `tenant_id`, initiating `user_id`, conversation ownership, and ordering/idempotency fields. |
| `OperationsAction` | A proposed action has a type, payload, reason, state, and execution time. | `BusinessAssistantConfirmation` and `BusinessAssistantToolRun`, with encrypted/minimised payload handling and append-only events. |
| `SupportTicket` | User-safe ticket fields are distinct from private engineering work metadata. | Tenant-scoped `SupportTicket` and `SupportTicketEvent`; keep private worker instructions/logs outside the user-safe representation. |
| `OperationsMemory` | Durable memory must be bounded and separately maintained from ordinary chat history. | `BusinessAssistantMemory`, restricted to approved durable knowledge with provenance, scope, retention, and review status. |

The reference records are single-scope and lack the target application’s required tenant/user isolation. They are concepts only, never source models to transplant.

### 2.4 Realtime voice protocol

The reference separates browser transport from transcript parsing:

- the browser creates an audio offer, requests a server-negotiated SDP answer, and handles microphone denial and connection teardown;
- realtime events are parsed defensively from unknown JSON into small transcript-state types;
- user and responder transcripts are queued, deduplicated, paired in order, and persisted as completed turns;
- realtime function-call arguments are sent to the same server-side policy gateway, and the result is returned through the data channel; and
- deterministic IDs based on session, role, and provider event ID make persisted voice pairs retry-safe.

These are reusable design patterns. Rebuild them behind tenant/user-authorised endpoints and the same tool/confirmation engine as text. Do not use browser-held provider credentials or let voice access a wider tool set.

### 2.5 Conversation interface patterns

`frontend/src/OperationsAIChat.tsx` demonstrates a compact, accessible conversation feature:

- persistent history with loading, refresh, recoverable composer errors, optimistic send and restoration of failed drafts;
- keyboard support for Enter-to-send and Shift+Enter newline;
- an `aria-live` conversation log, labelled controls, voice state feedback, and a constrained message length;
- visibly labelled voice-derived messages;
- user-safe ticket status cards; and
- an explicit user-facing statement that technical work is handed off, not done in the conversation.

The production feature should reuse these interaction ideas while using the target design system, routes, API client, role checks, and an approval design that never exposes a direct production-deployment control in the conversation panel.

## 3. Source-to-target mapping

| Reference asset | Reusable unit or evidence | Target treatment | Dependencies to replace or exclude |
|---|---|---|---|
| `backend/services/business_assistant_service.py` | Tool policy, prompt boundary, business-rule draft/confirm sequence, curator interview flow, support-ticket shape. | Reimplement as small native instruction, tool-registry, confirmation, knowledge, and ticket services. | Replace SQLAlchemy session assumptions, old knowledge/curator functions, operational tool gateway, regular-expression sanitisation alone, and automatic worker launch. |
| `backend/routes/operations.py` | Text turn lifecycle; SDP request contract; turn persistence and voice-tool endpoints. | Create authenticated `/api/admin/business-assistant/*` routes with conversation IDs and object-level authorisation. | Replace global admin assumptions, old routes, old provider/model literal, response capability flags, and unauthenticated/single-owner database access. |
| `backend/models/domain.py` | Message, action, ticket, memory, run/event concepts. | New tenant-scoped models plus Alembic migration and repository layer. | Do not reuse the legacy tables, fields, primary-key format, or missing tenant/user ownership. |
| `backend/schemas/domain.py` | Bounded chat, tool and realtime-turn payload shapes; UUID and transcript limits. | Create target schemas with Pydantic limits, opaque server-issued selection IDs, confirmation IDs, and idempotency keys. | Replace camel-case legacy fields and bare tool-name/argument endpoint with conversation-scoped policy execution. |
| `backend/services/operations_service.py` | Serialisation, bounded safe snapshot/memory construction, transcript idempotency, selected customer-operation concepts. | Extract only independently verified patterns into focused adapters under the native module. | Exclude wholesale transfer; old module combines messaging, calendar access, local files, coding runner, deployment, web search, and legacy persistence. |
| `frontend/src/OperationsAIChat.tsx` | Conversation layout, recovery behaviour, accessible transcript, voice and ticket presentation. | Rebuild as target page/drawer components against the native API client. | Replace local API imports, direct deployment approval, old curator state call, fixed message IDs, wording, and styling assumptions. |
| `frontend/src/useOperationsRealtimeVoice.ts` | WebRTC cleanup, connection-generation guard, transcript queue flushing, server-mediated function result loop. | Reimplement after target realtime API and identity model are accepted. | Replace old API functions and session generation assumptions; add origin/auth validation, content-size limits, cancellation observability, and voice/text policy parity. |
| `frontend/src/operationsRealtimeVoiceProtocol.ts` | Small parsing/state/pairing functions for unordered realtime events. | Candidate for carefully reviewed reuse or equivalent rewrite with protocol tests. | Reconfirm upstream event contract; preserve strict unknown-value parsing and ordered pairing. |
| Relevant operations API methods | List/load/send conversation, create SDP session, persist voice turn, run a bounded voice tool, read ticket status. | Replace with target API client methods matching the approved OpenAPI contract. | Remove direct settings endpoints and deployment-approval method; derive scope from login, never model arguments. |

## 4. Explicit exclusions

The following observed material is not reusable for the target Business Assistant implementation:

- any coding-runner, source-reading, version-control, deployment, worker-claim, autonomous-console, or runtime-setting function from `operations_service.py`;
- old customer messaging, phone/account selection, calendar, booking recovery, internet research, notification, or local-file behaviour;
- the legacy table schema and global administrative conversation model;
- the direct ticket deployment approval endpoint and button;
- direct imports from the legacy reference application at runtime; and
- all content or configuration outside the approved inspection list.

## 5. Test cases to carry forward as native acceptance coverage

The test files are behavioural references, not directly portable test harnesses. The target repository prohibits mock implementations, so each case below must be rewritten against real target services with synthetic tenant-scoped fixtures and actual migrations.

| Reference test intent | Native acceptance test |
|---|---|
| Tool catalogue excludes code/deployment tools. | Assert no source, shell, version-control, deployment, secret, or unrestricted database tool can be registered or executed through text or voice. |
| Instructions describe onboarding, clear questions, confirmation, and technical handoff. | Assert approved instructions and tool metadata preserve the product boundary; backend policy tests remain authoritative. |
| A hidden engineering tool request is rejected. | Send an unregistered tool request through the live route and verify a tenant-safe rejection with no side effect. |
| Rule activation requires an affirmative confirmation. | Create a versioned draft, reject stale/ambiguous/wrong-actor confirmations, and accept only the matching expiring confirmation token. |
| Private knowledge does not become an owner question. | Verify visibility and knowledge-scope filters prevent cross-tenant, private, and quarantined content entering assistant context. |
| A technical handoff becomes a ticket. | Create a sanitised ticket, test deduplication and sensitive-category approval gates, and verify it remains `awaiting_engineering` until a real worker is independently accepted. |
| Text turn persists both roles and uses a bounded snapshot. | Verify chronological, tenant/user-scoped persistence; context limits; explicit provider failure; and no private message content in logs. |
| Voice session uses a server-held credential and fails closed when absent. | Verify SDP content/origin/auth validation, no credential in browser/API response, and clean fallback to text. |
| Voice completed turns are chronological, sanitised and idempotent. | Submit repeated/out-of-order synthetic transcript events and verify exactly one ordered pair with target conversation ownership. |
| Messaging and customer operations maintain account context and audit actions. | Defer until the target messaging tool pack is approved; then verify server-authoritative tenant/provider resolution, consent, opt-out, idempotency and audit with synthetic recipients only. |
| Searches and diagnostic results are bounded and privacy safe. | Verify limits, pagination, object authorisation, field allowlists, and content redaction against target services. |

The following reference tests specifically demonstrate capabilities that must not be ported into the Business Assistant: coding task start/cancel/claim, source file reading, deployment proposal/approval, and runtime settings mutation. Preserve them only as negative architecture evidence.

## 6. Dependency rewrite ledger

| Dependency pattern observed | Required native outcome |
|---|---|
| Global database session passed directly into agent/tool functions. | Request-scoped transaction and service interfaces with tenant/user context established before tool lookup. |
| Large combined service exposing unrelated tools. | Small adapters grouped by product-help, onboarding, knowledge, booking reads, customer operations, and tickets; use a contextual 5–10 tool pack. |
| Static prompt text as the principal safety boundary. | Backend authorisation, schema validation, confirmation binding, idempotency, audit events, and negative tests. |
| Single global chat history and memory tables. | Conversation and memory records with authoritative tenant and user ownership, visibility rules, retention, and pagination. |
| Direct model tool arguments identify customer/account objects. | Server-issued opaque choices and object-level authorisation; model input cannot select arbitrary tenant/provider/customer identifiers. |
| Persisting text/voice messages in the same row type. | Shared target message model is acceptable only when all messages belong to the same authorised Business Assistant conversation and voice provenance is explicit. |
| Immediate handoff to a coding task. | Persist a structured ticket first. Dispatch only after a real isolated worker, idempotent claim, actual test evidence, independent review, and owner deployment gate are proven. |

## 7. WP0 actions before code transfer

1. Obtain the required narrow source-reference exception in the governing documents.
2. Create and record an immutable, recoverable source checkpoint; update the hash table if the approved assets differ.
3. Produce a target data-flow/PII classification and role/capability matrix.
4. Select the real coding-worker target and prove its acceptance gate independently.
5. Freeze the first-release scope as owner/admin text-first unless the owner explicitly approves a broader release.
6. Write the target OpenAPI and persistence contracts before any frontend or realtime implementation.

## 8. Inventory verification

- This document is the only file created by this inventory task.
- Its content intentionally uses the term “legacy reference application” and does not use the prohibited legacy product name.
- The listed asset hashes were calculated from the exact approved file paths on 2 October 2026; they are evidence of inspected inputs, not source-control approval.
