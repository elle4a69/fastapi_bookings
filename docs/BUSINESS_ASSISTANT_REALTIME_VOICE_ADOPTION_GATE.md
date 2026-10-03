# Native Business Assistant Realtime Voice Adoption Gate

**Status:** Deferred. This document is an implementation and release gate, not authority to enable voice.  
**Prepared:** 2 October 2026 (Australia/Sydney)  
**Depends on:** `BUSINESS_ASSISTANT_NATIVE_PORT_PLAN.md`, `BUSINESS_ASSISTANT_THREAT_MODEL_AND_CAPABILITY_MATRIX.md`, the native text foundation, and `AGENTS.md`.

## 1. Decision

Realtime voice must remain disabled until the native text conversation boundary is accepted and every gate in this document is met. Voice is an alternate transport for the same Business Assistant conversation; it is not a second agent, an alternate authorisation path, or a browser-side shortcut to tools.

The first voice release is owner/admin-only, uses the existing tenant/user conversation ownership model, starts with the same no-tool text policy, and falls back to text on any authentication, provider, microphone, transport, transcript, or persistence failure. Adding a voice-specific tool is a later, separately reviewed change; it cannot precede proven text-tool policy and voice/text parity.

## 2. Evidence inspected for this gate

### Native text foundation

The following target assets were inspected:

- `app/models/business_assistant.py`: dedicated tenant/user-scoped conversation and message records; structural tool-run record; user-safe tickets/events.
- `app/schemas/business_assistant.py`: bounded text-turn request and response contracts.
- `app/api/routers/business_assistant.py`: authenticated owner routes; text provider failure preserves the user message; route errors do not manufacture a reply.
- `app/services/business_assistant/repository.py` and `service.py`: tenant/user ownership checks, chronological history, idempotent request keys, retry claim, and persisted reply linkage.
- `app/services/business_assistant/runtime.py`: server-configured, bounded text generation with no tools.
- `frontend/src/pages/admin/business-assistant/index.tsx`: authenticated text API client, stable request key while retrying, history recovery, and no external-action capability.
- `tests/test_business_assistant_api.py` and `tests/test_business_assistant_foundation.py`: authentication, tenant isolation, persistence separation, idempotency, and provider-unavailable behaviour.

### Allowlisted realtime reference assets

Only these legacy reference application assets were inspected:

- `backend/routes/operations.py` realtime SDP, completed-turn, and voice-tool route patterns.
- `backend/schemas/domain.py` bounded session/event/transcript payload pattern.
- `backend/services/operations_service.py` SDP exchange, constrained voice tool gateway, deterministic transcript IDs, and atomic transcript-pair persistence pattern.
- `frontend/src/useOperationsRealtimeVoice.ts` WebRTC lifecycle, media cleanup, connection-generation guard, data-channel event handling, pairing queue, and serial persistence pattern.
- `frontend/src/operationsRealtimeVoiceProtocol.ts` defensive event parsing, terminal-state handling, deduplication, and ordered pairing pattern.
- `backend/test_operations_ai_chat.py` provider-unavailable, tool-boundary, and transcript-order/idempotency acceptance patterns.

No code, configuration, external service, credentials, database, logs, or customer data was accessed or changed for this gate.

## 3. Preconditions to begin implementation

All conditions below must be evidenced before a voice implementation work package starts:

1. The text foundation’s migrations apply and downgrade cleanly, its tenant/user isolation tests pass, and its text routes are authenticated end-to-end.
2. Text remains no-tool until a separate native tool registry and confirmation engine have passed their own controls. Voice starts with the identical no-tool policy.
3. The native conversation/message model has an approved, migrated voice provenance design; no customer-message table or shared unauthorised store may be used.
4. Server-held realtime-provider configuration is validated without printing or returning credentials. No browser environment variable, HTML payload, API response, SDP answer, telemetry event, ticket, or error may contain a provider credential.
5. A staging origin policy, synthetic tenant, and non-production provider account are available for later real integration verification. This prerequisite does not authorise a provider call in development or production.
6. Text failure/retry behaviour is retained: a user turn is preserved once, duplicate requests do not create another turn, and an unavailable provider never produces a fabricated reply.
7. A focused implementation work package has an approved route/schema/model/file allowlist, accessibility plan, privacy review, and rollback step.

## 4. Required server/client boundary

```text
Authenticated browser
  |  microphone media, SDP offer, user-visible controls
  v
Native authenticated voice routes
  |  resolve tenant, user, conversation ownership and policy
  |  validate origin, media type, length, request/session state
  v
Server-held realtime-provider session exchange
  |  minimised instructions and the text-equivalent tool policy
  v
Realtime media/data channel
  |  transcript events are untrusted transport data
  v
Native transcript normaliser and idempotent persistence
  |  same conversation, messages, audit and confirmation policy as text
  v
Authenticated browser transcript refresh / text fallback
```

The browser owns microphone permission, local media tracks, peer-connection lifecycle, local playback, and accessible status display. The browser does not own identity, tenant scope, conversation scope, provider credential, model/session configuration, tool authorisation, confirmation, message persistence, audit decisions, or ticket handling.

The server owns identity resolution, object-level conversation ownership, SDP exchange, provider credential containment, session configuration, policy selection, transcript acceptance, idempotency, persistence, audit events, and safe error mapping. The server must derive all scope from the same authenticated dependencies used by text; it must not accept a tenant/user/conversation claim from an SDP body or data-channel event.

## 5. Proposed native API and transport contract

The route shape follows the approved plan and remains subject to the native schema review:

| Route | Contract and required checks |
|---|---|
| `POST /api/admin/business-assistant/conversations/{conversation_id}/realtime` | Accept exactly `Content-Type: application/sdp`; authenticated owner; conversation must belong to current tenant/user; require an allowlisted browser `Origin`; reject a missing/invalid/oversized offer; return SDP only with `Content-Type: application/sdp` and `Cache-Control: no-store`. |
| `POST /api/admin/business-assistant/conversations/{conversation_id}/realtime/turns` | Authenticated owner; accept only a completed, bounded, normalised transcript pair tied to a server-created session and that conversation; persist atomically and idempotently. |
| `POST /api/admin/business-assistant/conversations/{conversation_id}/realtime/tools` | **Not enabled in the first voice release.** It may exist only after the text tool gateway passes review and the server can prove the request has no broader authority than an equivalent text tool request. |

Required request limits:

- SDP offer: valid UTF-8, `application/sdp` only, maximum 100,000 bytes after receipt; reject malformed encoding and NUL-containing input.
- Origin: exact configured application origin in production/staging; no wildcard origin, reflected origin, or credentialed cross-origin access. Local development requires an explicit non-production allowlist.
- Session ID: server-created UUID or opaque random ID, scoped to tenant/user/conversation, with short expiry and one active connection policy per conversation/user unless separately designed.
- Provider event/source IDs: 1–200 characters, constrained to a safe identifier alphabet; store only a scoped keyed hash where raw storage is not required.
- Transcript: each side 1–8,000 Unicode characters after normalisation; reject empty, over-limit, or invalid pairing data.
- Event payload: maximum 32,768 bytes; accept only known event types and fields; unknown, duplicate, stale, or out-of-scope events have no persistence or tool effect.

## 6. WebRTC and credential containment requirements

1. The browser sends an SDP offer only to the authenticated native route. The server performs the upstream exchange using a credential obtained from validated server configuration.
2. The credential, upstream authorisation header, raw session configuration, and any provider token are never returned to the browser, included in a URL, stored in conversation/ticket/audit records, or sent to telemetry.
3. The server uses a bounded upstream timeout and returns a generic, non-sensitive failure. It does not log the SDP, transcript, credential, raw provider error body, or response body.
4. Session instructions and any contextual data are constructed server-side from the same approved policy/context service as text. Dynamic or personal data must be minimised and may not be supplied merely because voice is active.
5. The browser must stop microphone tracks, close the data channel and peer connection, remove playback resources, and return to `idle` on explicit stop, unmount, failed/disconnected connection, or failed setup. A generation counter or equivalent must prevent a stale asynchronous operation from resurrecting a closed session.
6. Realtime session creation must not create a booking, message, ticket, confirmation, or tool run merely because media connected.

## 7. Transcript event, ordering, and idempotency contract

The client may receive transport events out of order, more than once, or with terminal failures. The native implementation must normalise only the following categories:

| Category | Required normalised fields | Terminal state |
|---|---|---|
| User audio committed | `user_source_id`, `pending` | No; wait for transcription result. |
| User transcription completed | `user_source_id`, sanitised transcript | Yes, successful. |
| User transcription failed | `user_source_id`, no transcript | Yes, failed. |
| Assistant transcript completed | `assistant_source_id`, sanitised transcript | Yes, successful. |
| Assistant response failed/cancelled/incomplete | `assistant_source_id`, no transcript | Yes, failed. |
| Provider error | safe category only | Does not create a persisted turn. |

Pairing algorithm:

1. Maintain separate FIFO queues for user and assistant transcript states per server-created session.
2. A pending user item blocks pairing behind it; do not pair a later assistant transcript with a later user item by timestamp guesswork.
3. Consume queue heads only when both are terminal. Persist one pair only when both are successful; for a failed pair, record a content-free structural failure event and display text fallback guidance.
4. Persist the user message before the assistant message with a stable sequence/order key even if the assistant event arrived first.
5. Use deterministic idempotency keys derived from tenant, user, conversation, session, role, and provider source ID. Enforce database uniqueness for each role/event and for the completed pair; a retry returns the same persisted records without duplication.
6. Session expiry, page reload, or transport disconnect must not invent a missing transcript or reply. Unpaired terminal items expire into a structural, content-free reconciliation record and the user may continue in text.

Voice messages must be stored in the native `BusinessAssistantMessage` table with explicit channel/provenance fields added by a migration. They retain the existing tenant/user/conversation ownership and reply linkage. Any new raw-event record must be scoped, time-limited, and content-free; raw provider event payloads are not persistent audit data.

## 8. Voice/text permission parity

Voice inherits the exact permissions and exclusions of the active text conversation. The following cannot differ by transport:

- current tenant, authenticated user, owner/role check, and conversation ownership;
- selected tool pack, tool schema, object-level authorisation, confirmation binding, idempotency, and audit policy;
- data classification and model-context field allowlists;
- ticket privacy tier and coding-worker separation; and
- source, shell, version-control, deployment, infrastructure, secret-reading, unrestricted-database, and worker-execution prohibitions.

The first release exposes no realtime tools. A browser data-channel function-call event is untrusted. It cannot be treated as proof that a provider asked for an action. Before any tool is added, either the server must attest the provider invocation through a server-mediated channel, or the endpoint must be demonstrably limited to the exact same low-risk, already-authorised operation available in text, with no privilege increase and no externally visible mutation. Confirmation-bound operations require the normal persistent confirmation route; an utterance or data-channel event cannot confirm them.

## 9. Failure and degradation behaviour

| Condition | Required outcome |
|---|---|
| User denies microphone | Do not create a voice session or message; explain that text remains available. |
| Browser lacks WebRTC/media support | Do not create a session; preserve text conversation access. |
| Authentication, tenant, ownership, origin, content-type, or SDP check fails | Reject before upstream contact; no transcript/ticket/tool/audit content is persisted. |
| Provider configuration absent or upstream setup fails | Return a generic unavailable response; do not expose configuration or fabricate a reply; text input remains available. |
| Connection disconnects or client stops | Release browser resources; retain only already accepted complete turns; never manufacture a partial turn. |
| Transcript is incomplete, invalid, oversized, duplicate, or unpairable | Do not persist a user/assistant pair; record only allowed structural status if needed; guide the user to text. |
| Transcript persistence fails | Keep the completed local display optional but label it unsaved; show text retry path; do not re-send an externally visible action. |
| Future tool call fails | Return a safe error to the provider session only if a server-authorised tool call was accepted; no hidden retry; preserve the text confirmation route. |

## 10. Privacy-safe observability

Allowed voice telemetry and audit fields are: route/result category, authenticated scope identifiers under the repository’s safe-ID policy, opaque session hash, connection state, protocol/event category, byte/character bucket, elapsed duration, persistence outcome, duplicate/reconciliation count, and error class.

Never record or emit: SDP, audio, transcript content, raw realtime event JSON, model instructions, model responses, provider credentials/tokens, authorisation headers, customer identifiers, booking notes, ticket descriptions, or tool arguments/results. Telemetry failure must not block shutdown, text fallback, or normal conversation persistence.

Before voice is enabled, the configured collector must visibly receive only the allowlisted structural attributes during a synthetic privacy test. A successful application log statement is not evidence of telemetry safety.

## 11. Acceptance suite and release gate

| Gate | Concrete evidence |
|---|---|
| Native text prerequisite | Existing authenticated, tenant/user isolation, retry/idempotency, dedicated-table, and provider-unavailable tests pass against the migrated target application. |
| Route/auth/origin | Authenticated synthetic owner succeeds; unauthenticated, wrong-tenant, wrong-user, cross-origin, missing-origin, wildcard-origin, wrong-content-type, invalid UTF-8, NUL-containing, and oversized SDP requests fail before provider contact. |
| Credential containment | Synthetic provider/staging integration verifies no provider credential/session configuration appears in browser response, page state, API body, logs, traces, metrics, tickets, or database records. |
| Browser lifecycle | Automated browser tests cover denial, unsupported media, connecting/live/idle state, explicit stop, route navigation/unmount, failed/disconnected peer connection, and stale async completion after stop. |
| Transcript parser | Unit tests cover each accepted event, unknown schema, missing IDs, duplicate terminal event, pending user followed by later events, user/assistant failures, FIFO pairing, and unpaired expiry. |
| Persistence | Database integration tests prove atomic ordered pair insertion, deterministic retry return, concurrent duplicate protection, tenant/user/conversation isolation, message provenance, and no persisted partial pair. |
| Text/voice parity | A matrix of authorised and unauthorised actions proves voice has no tool, scope, data, confirmation, or ticket capability not available to the same text conversation. |
| Prompt and tool safety | Adversarial spoken/transcribed content and forged data-channel events cannot reveal instructions, create hidden tools, widen scope, confirm an action, dispatch work, or perform an external effect. |
| Failure degradation | Synthetic provider timeout/error, transcript failure, and persistence failure show an honest safe error plus usable text fallback; no fabricated response or hidden external retry occurs. |
| Telemetry privacy | Collector inspection from a synthetic session proves only allowlisted structural fields; a deliberate synthetic secret/PII marker is absent from logs, traces, metrics, and audit records. |
| Real integration release evidence | After separate authorisation, one staging-only session with synthetic data demonstrates authenticated SDP exchange, media, completed transcript persistence, failure fallback, and teardown. No production provider or customer data is used. |

All implementation and integration tests must use the real native route, database migration, policy service, and frontend call path. Simulated timers, disconnected components, fabricated success responses, or a browser-only prototype do not satisfy this gate.

## 12. Exit criteria

Voice may move from deferred to staged only after the project manager has reviewed a bounded implementation diff and reproducible evidence for every applicable gate above, an independent security/privacy reviewer has accepted the parity and telemetry evidence, and the owner separately approves the staging rollout. Production enablement remains a distinct decision after staged synthetic-tenant success and a documented rollback procedure.

## 13. Document verification

- This document defines no provider configuration, makes no network request, and does not enable voice.
- It is limited to the approved realtime source assets and current native text foundation listed in section 2.
- It uses neutral historical terminology and does not use the disallowed legacy product name.
