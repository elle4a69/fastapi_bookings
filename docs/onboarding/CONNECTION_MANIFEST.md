# FastAPI Bookings — Voice-First Onboarding Connection Manifest

**Document Version:** 1.0  
**Date:** 8 October 2026  
**Project:** `voice_first_onboarding`  
**Target Codebase:** `F:\Projects\fastapi_bookings`  
**Specification Reference:** `E:\Projects\Playground\VOICE_FIRST_ONBOARDING_IMPLEMENTATION_SPEC.md`  

---

## 1. Executive Summary & Purpose

This connection manifest establishes the authoritative baseline integration points between the existing, cloud-hosted LiveKit voice infrastructure and the new voice-first onboarding / visible in-app assistance module.

Per `VOICE_FIRST_ONBOARDING_IMPLEMENTATION_SPEC.md`, this onboarding module operates the actual application visibly. It does **not** install, host, provision, or configure LiveKit, nor does it replace audio transport, speech-to-text, or the underlying GPT Live session configuration. This manifest catalogues exact working-tree checkpoints, dependency versions, backend gateway methods, token issuance parameters, frontend RPC receivers, DOM events, and boundary rules to be strictly preserved throughout all stages of implementation.

---

## 2. Working-Tree Checkpoint & Dependency Versions

### 2.1 Git Working-Tree Reference
- **Active Branch:** `codex/business-assistant-foundation-and-migrations`
- **Head Commit Hash:** `117de435c5b18299d22a150ad63ff7e1d33689f7`
- **Head Commit Message:** `docs(living): reindex module catalog with authentication and SSO subsystem`
- **Repository Scope Discipline:** Untracked files and working-tree changes from preceding projects (Stages A, B, C) are deliberately preserved. No blanket staging (`git add .`) is permitted. All onboarding changes must strictly maintain an explicit changed-file allowlist.

### 2.2 Installed Backend Python Dependencies (`.venv`)
| Package | Installed Version | Purpose |
|---|---|---|
| `livekit` | `1.1.20` | LiveKit Python SDK core |
| `livekit-agents` | `1.8.5` | LiveKit Agents worker framework & `function_tool` bindings |
| `livekit-api` | `1.2.1` | LiveKit server API client (AccessToken, RoomAgentDispatch, VideoGrants) |
| `livekit-plugins-openai` | `1.8.5` | OpenAI Realtime / GPT Live model adapter & WebSearch plugin |
| `livekit-protocol` | `1.1.27` | Protobuf definitions for LiveKit room/agent protocol |
| `fastapi` | `0.139.0` | Backend API framework & routing |
| `pydantic` | `2.13.4` | Data validation, schemas, and typed payload contracts |
| `sqlalchemy` | `2.0.51` | Authoritative database ORM and persistence |

### 2.3 Installed Frontend Node Dependencies (`frontend/package.json`)
| Package | Installed Version | Purpose |
|---|---|---|
| `livekit-client` | `^2.22.3` | Browser LiveKit WebRTC client, RPC receiver, DataChannel |
| `@livekit/components-react` | `^2.9.24` | LiveKit UI primitives |
| `react` / `react-dom` | `^19.2.7` | UI component library |
| `react-router-dom` | `^7.18.1` | Client-side application routing |
| `typescript` | `~6.0.2` | Typed frontend contracts |
| `vite` | `^8.1.1` | Frontend build and dev tooling |

---

## 3. Preserved Voice Baseline & Identity Configuration

### 3.1 Immutable Session Configuration
The existing voice session baseline in `app/services/business_assistant/gpt_live/session_config.json` is preserved byte-for-byte and validated at runtime via SHA256 integrity:
- **Config File:** `app/services/business_assistant/gpt_live/session_config.json`
- **Expected SHA256:** `e9ba09d5fabed07ac87927ee909035e93d08b337ce273124d8bddc5397b97ca5`
- **Live Model:** `gpt-live-1`
- **Voice Output:** `gleam`
- **Delegation Mode:** `responses`
- **Delegated Model:** `gpt-5.6-terra`
- **Reasoning Effort:** `medium`
- **Parallel Tool Calls:** `false`
- **Native Tools:** `WebSearch`

### 3.2 Named Agent Dispatch Identity
- **Default Agent Name:** `bookings-business-assistant`
- **Configuration Symbol:** `settings.LIVEKIT_DEFAULT_AGENT_NAME` (`app/core/config.py`) and `DEFAULT_AGENT_NAME` (`app/services/business_assistant/livekit/config.py`)
- **Participant Identity Format:**
  * Browser participant: `part_{user_id}_{hex_uuid_8}` (opaque, non-PII)
  * Room name: `room_{tenant_id}_{conversation_id}_{hex_uuid_12}` (opaque, tenant-scoped)
  * Session ID: `sess_{hex_uuid_32}`

---

## 4. Backend Gateway Integration Points

### 4.1 Gateway Class: `LiveKitToolGateway`
**File:** `app/services/business_assistant/livekit/tool_gateway.py`

#### Context Envelope
```python
@dataclass(frozen=True)
class LiveKitSessionContext:
    session_id: str
    tenant_id: int
    user_id: int
    conversation_id: int
```

#### Core Methods & Signatures
1. **`execute_tool_sync(name: str, arguments: dict[str, Any]) -> dict[str, Any]`**
   - Validates session context, verifies tenant rollout gate, and verifies conversation lookup.
   - Instantiates `BusinessAssistantService` and `BusinessAssistantReadAdapters`.
   - Executes named tool via `BusinessAssistantToolRegistry(packs=self.packs)`.
   - Produces structured audit log (no PII or raw speech transcript).
2. **`execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]` (async)**
   - Offloads synchronous database execution to worker thread via `asyncio.to_thread`.
   - If status is `"ok"`, triggers `_dispatch_post_tool_rpc(name, arguments, result)`.
3. **`build_agent_tools() -> List[Any]`**
   - Iterates through `BusinessAssistantToolRegistry.schemas`.
   - Wraps each schema with LiveKit `function_tool` calling `execute_tool`.
   - Registers native `WebSearch()` tool.

#### Existing Post-Tool RPC & Dispatch Gap
The current `_dispatch_post_tool_rpc` implementation for website tools performs:
```python
# Broadcast to all remote participants:
for ident in remote_participants:
    rpc_call = rpc_fn(
        destination_identity=ident,
        method="assistant_ui_action",
        payload=payload_str,
        response_timeout=3.0,
    )
    ...
```
**Identified Gap & Contract Rule:**
- **Do not** extend broadcast dispatch to onboarding forms or field values.
- Broadcasting field values to multiple room participants violates privacy and causes duplicate state writes.
- Onboarding actions must target **only** the leased active-executor participant identity.
- RPC results must be parsed into asynchronous, truthful receipts (distinguishing `dispatched`, `fields_staged`, and `saved`) rather than assuming immediate execution upon dispatch.

---

## 5. Token Issuance & Router Contracts

### 5.1 FastAPI Voice Router: `app/services/business_assistant/livekit/router.py`
- **Prefix:** `/api/admin/business-assistant/voice`
- **Tag:** `Business Assistant Voice`

| Endpoint | Method | Response Model | Description |
|---|---|---|---|
| `/transport` | `GET` | `VoiceTransportRead` | Returns authoritative transport (`livekit_gpt_live` or `direct_gpt_live`) and default agent name. |
| `/conversations/{conversation_id}/session` | `POST` | `VoiceSessionResponse` | Creates/issues scoped room token, room name, participant identity, and dispatches named agent. |
| `/conversations/{conversation_id}/token/refresh` | `POST` | `VoiceTokenRefreshResponse` | Refreshes LiveKit room token validity window before expiration. |

### 5.2 Token Service: `app/services/business_assistant/livekit/token_service.py`
- **Class:** `LiveKitTokenService`
- **Method:** `create_room_token(tenant_id, user_id, conversation_id, ttl_seconds=600, agent_name=None, record=False) -> LiveKitRoomTokenResult`
- **Grants Enforced:**
  * `room_join=True`
  * `room=room_name`
  * `can_publish=True` (audio)
  * `can_subscribe=True` (assistant audio)
  * `can_publish_data=True` (captions & data events)
  * `room_record=False` (hard-coded privacy boundary; no media or egress recording enabled)
- **Dispatch Metadata:** JSON payload with `session_id`, `tenant_id`, `user_id`, `conversation_id` attached to `api.RoomAgentDispatch`.

---

## 6. LiveKit Caption Bridge & DataChannel

### 6.1 Caption Bridge: `app/services/business_assistant/livekit/caption_bridge.py`
- **Class:** `LiveKitCaptionBridge`
- **Topic:** `"captions"`
- **Event Types:**
  * `session.input_transcript.delta` (user speech fragment)
  * `session.output_transcript.delta` (assistant response fragment)
- **Envelope Properties:** `type`, `delta`, `start_ms`, `end_ms`, `epoch`, `sequence`, `speaker`, `session_id`.
- **Deduplication:** Maintained via sequence and epoch tracking; deques up to 500 events.
- **Session Finalisation:** Observes terminal provider event `session.closed` to set `is_finalised=True` (distinguished from transient network disconnects).

---

## 7. Frontend LiveKit Hook & RPC Boundary

### 7.1 React Hook: `useLiveKitVoice`
**File:** `frontend/src/pages/admin/business-assistant/use-livekit-voice.ts`
- **Exported Hook:** `useLiveKitVoice(options: UseLiveKitVoiceOptions): UseLiveKitVoiceResult`
- **Inputs:** `conversationId`, `onCaptionsChange`, `onError`, `onNavigate`, `onRpcReceipt`.
- **Returns:** `voiceState`, `captions`, `isMuted`, `audioDevices`, `activeAudioDeviceId`, `lastRpcReceipt`, `startVoice`, `stopVoice`, `toggleMute`, `switchAudioDevice`.
- **Lifecycle Integration:**
  * Connects to LiveKit Room via token from `/session`.
  * Subscribes to remote audio track and attaches to DOM `<audio>` element with autoplay.
  * Receives caption delta packets on DataChannel and updates timeline via `appendTranscriptDelta`.
  * Invokes `registerAssistantRpcMethods(room, context)` upon room connection.
  * Disconnects and releases audio resources cleanly on `stopVoice()` or component teardown.

### 7.2 RPC Registration & Receiver: `frontend/src/pages/admin/business-assistant/rpc/`

#### Registered RPC Method Names
- `assistant_ui_action` (universal payload router)
- `route_navigation` / `navigate`
- `preview_toggle`
- `section_highlight`
- `change_review_drawer`

#### Sender Validation: `sender-validation.ts`
- **Function:** `validateAssistantRpcSender(options: SenderValidationOptions): SenderValidationResult`
- **Rules:**
  1. Rejects missing or empty caller identity.
  2. Enforces isolation: rejects self-invocation (`localParticipant.identity === callerIdentity`).
  3. Validates caller against `expectedAgentIdentity` or `allowedAgentIdentities`.
  4. In active rooms, checks remote participant's agent flag (`isAgent`, `kind === 'agent' | 2`), matching agent name (`bookings-business-assistant`), or prefix (`agent_`, `assistant`).

#### Action Catalogue & Allowlisted Routes: `action-catalogue.ts` & `types.ts`
- **Allowed Routes:** 30 strict admin routes (e.g., `/admin`, `/admin/settings/business`, `/admin/catalog/services`, `/admin/website`, etc.).
- **Route Aliases:** Normalized friendly aliases (e.g., `services` -> `/admin/catalog/services`, `settings` -> `/admin/settings/business`, `website` -> `/admin/website`).
- **Route Validation:** Strictly rejects non-allowlisted routes, path traversals (`..`), `javascript:`, `data:`, `vbscript:`, and external HTTP URLs.

#### Browser Custom DOM Events Dispatched
| Event Name | Payload / Detail Type | Description |
|---|---|---|
| `assistant-rpc:receipt` | `RpcExecutionReceipt` | Global receipt broadcast for any executed RPC action |
| `assistant-rpc:action` | `{ action: string, receipt: RpcExecutionReceipt }` | Action dispatch notification |
| `assistant-rpc:preview-toggle` | `{ state: 'open' \| 'closed' }` | Toggles website preview canvas |
| `assistant-rpc:section-highlight` | `{ section: string, elementFound?: boolean }` | Visual smooth-scroll and highlight overlay |
| `assistant-rpc:change-review-drawer` | `{ state: 'open' \| 'closed', proposalId?: number }` | Controls website proposal review drawer |

---

## 8. Leased Active-Executor Concept & Identity Binding

In multi-tab browser sessions, multiple instances of the application might share or observe the same LiveKit room. Unrestricted RPC broadcasting causes race conditions, double submissions, and duplicate saves.

### 8.1 The Active-Executor Lease Model
1. **Single Leased Tab:** Only one browser tab holds the active automation lease (`active_executor_lease`) for a given tenant session.
2. **Lease Token & Epoch:**
   - `lease_token`: Unique UUID generated by the holding browser tab.
   - `control_epoch`: Monotonically increasing counter; advanced on manual takeover or lease handover.
   - `holder_identity`: Browser participant identity in the LiveKit room.
3. **Execution Restriction:**
   - Only the active executor tab registers executable form adapters and executes mutating actions (`set_fields`, `save_form`).
   - Secondary tabs operate in read-only / observational mode.
4. **Targeted Dispatch:**
   - The backend gateway targets RPC calls directly to `holder_identity` instead of iterating all room participants.
5. **Epoch Invalidation:**
   - Any manual user interaction (typing, clicking, modal dismissal) advances the `control_epoch`, instantly rejecting queued or in-flight commands carrying an older epoch.

---

## 9. Onboarding Action Protocol & Receipt State Machine

Per Section 10 of the implementation specification, onboarding actions must enforce discrete, truthful receipt states:

```
[Agent Intent]
      │
      ▼
┌───────────────┐
│   received    │
└───────┬───────┘
        ▼
┌───────────────┐      (Target component mounting / modal opening)
│waiting_for_ui ├──────────────┐
└───────┬───────┘              │
        ▼                      ▼
┌───────────────┐      ┌───────────────┐
│   executing   │      │   rejected    │ (Stale epoch / Manual takeover /
└───────┬───────┘      └───────────────┘  Unregistered target / Validation failure)
        ├──────────────────────┬───────────────┐
        ▼                      ▼               ▼
┌───────────────┐      ┌───────────────┐┌───────────────┐
│ fields_staged │      │    failed     ││outcome_unknown│
└───────┬───────┘      └───────────────┘└───────────────┘
        │ (Explicit save deleg.)       (Network timeout / Reconcile required)
        ▼
┌───────────────┐
│     saved     │ (Committed database revision returned)
└───────────────┘
```

- **`fields_staged` is NOT `saved`:** Staging populated fields into React state must never be reported as persisted until the database transaction commits.
- **Autosave Protection:** Staged fields must not prematurely trigger debounce/blur autosaves until deliberate submission.

---

## 10. Boundaries to Preserve (Non-Negotiables)

1. **No LiveKit Reinstallation or Provisioning:** LiveKit is cloud-hosted and active. No changes to room provisioning, network egress, or transport infrastructure are permitted.
2. **Preserve Audio Transport & GPT Live Baseline:** Do not replace `livekit-client` audio tracks, WebRTC handlers, or alter `session_config.json` (`gpt-live-1` / `gleam` / `gpt-5.6-terra`).
3. **No Arbitrary DOM Automation:** Absolutely no arbitrary CSS selectors, raw coordinate clicks, or JavaScript execution from model hallucinations. All UI interactions must route through registered semantic `OnboardingFormAdapter` interfaces.
4. **Absolute Prohibition of Mocks:** All adapters, routers, services, and tests must be real, functional, and wired into live code paths.
5. **Scope Discipline:** Never blanket-add files (`git add .`). Maintain an explicit changed-file allowlist for all commits.
6. **Data & Telemetry Safety:** No PII, customer records, raw transcripts, authentication tokens, or secrets in telemetry or audit logs.

---

## 11. Upstream Prerequisites & Downstream Integration Contracts

| Stage | Task ID | Core Contract / Requirement | Status |
|---|---|---|---|
| **S1** | `task_s1_connection_manifest` | This manifest (`docs/onboarding/CONNECTION_MANIFEST.md`). | Completed |
| **S1** | `task_s1_form_autosave_audit` | Audit `settings/business.tsx` and `catalog/services.tsx` for field keys, debounces, blur handlers, and staging guard points. | Completed |
| **S1** | `task_s1_typed_action_protocol_frontend` | Extend `rpc/types.ts` & `rpc/action-catalogue.ts` with versioned onboarding action schemas (`set_fields`, `save_form`, `open_form`, etc.). | Completed |
| **S1** | `task_s1_backend_action_schemas` | Define matching Pydantic schemas in `app/services/business_assistant/onboarding/schemas.py`. | Completed |
| **S2** | `task_s2_form_adapter_registry` | Implement `OnboardingFormAdapter` registry interface in `frontend/.../adapters/`. | Completed |
| **S2** | `task_s2_business_settings_adapter` | Concrete adapter for Business Settings with autosave staging guard. | Completed |
| **S2** | `task_s2_catalog_services_adapter` | Concrete adapter for Services catalog (creation modal, pricing, categories). | Completed |
| **S2** | `task_s2_active_executor_rpc` | Single-tab active executor leasing, sender validation, and targeted RPC receipts. | Completed |
| **S2** | `task_s2_manual_takeover_ui_pointer` | Compact status bar, "I'll do this part" takeover handler, and non-intercepting pointer overlay. | Completed |
| **S3** | `task_s3_db_migration_plan` | Alembic migration & models for onboarding setup plan (`app/models/onboarding.py`). | Completed |
| **S3** | `task_s3_intent_normalizer` | Australian-English intent-to-field text normalizer preserving names/units. | Completed |
| **S3** | `task_s3_onboarding_plan_service` | Persistent adaptive setup planner service. | Completed |
| **S3** | `task_s3_delegation_save_guard` | Session delegation policy and single-use save guard. | Completed |
| **S3** | `task_s3_onboarding_api_router` | FastAPI router for onboarding plan, manual takeover, and reconciliation. | Completed |
| **S4** | `task_s4_agent_tool_pack` | Scoped agent tools (`read_context`, `plan_step`, `prepare_fields`, `navigate_show`, `fill_form`, `save_form`). | Completed |
| **S4** | `task_s4_livekit_tool_gateway_wiring` | Register onboarding tools into `tool_gateway.py` with active-executor targeting. | Completed |
| **S4** | `task_s4_website_onboarding_integration` | Wire onboarding into existing draft/Media services preserving owner review/publish gates. | Completed |
| **S4** | `task_s4_inline_interview_flow` | Inline multi-modal choice components resolving voice/click/text idempotently. | Completed |
| **S5** | `task_s5_*` | Acceptance test suites (text/intent QA, visible form QA, takeover QA, security QA) and living docs. | Completed |

---

## 12. Stage 5 Verification, Acceptance Test Suites & Execution Metrics

### 12.1 Backend QA Test Suites (Zero Mocks Enforced)
| Test Suite | File | Tests | Key Invariants Verified |
|---|---|---|---|
| **Text & Intent QA** | `tests/test_onboarding_text_and_intent_qa.py` | 27 | Australian spelling normalisation (`colour`, `programme`), currency ($ AUD), phone (+61), duration (mins), ABN formatting, material ambiguity detection, correction handling, zero hallucinated credentials. |
| **Visible Form Automation QA** | `tests/test_onboarding_form_automation_qa.py` | 9 | Form adapters, 600ms autosave debounce guards, Service model creation/editing (name, duration, price, active state), RPC receipts enforcing `staged_fields` (`persisted_entity_id=None`, `saved=False`). |
| **Takeover & Concurrency QA** | `tests/test_onboarding_takeover_concurrency_qa.py` | 9 | Manual takeover priority, monotonic control epoch invalidation (HTTP 409 `STALE_CONTROL_EPOCH`), single-tab active executor lease acquisition, lease heartbeat expiration (`LeaseExpiredError`), HTTP 409 `LEASE_CONFLICT`. |
| **Security, Privacy & Isolation QA** | `tests/test_onboarding_security_privacy_qa.py` | 12 | Strict tenant isolation (cross-tenant 404), cryptographic HMAC-SHA256 nonces (single-use, negative TTL expiration, tampered signature rejection, tenant/step binding), delegation mode gates (`view_only` refusal), zero credential leakage in audit logs. |
| **Pre-existing Onboarding Suites** | `tests/test_onboarding*.py` (5 files) | 90 | LiveKit gateway, session plan service, normalizer, delegation guard, API router. |
| **Total Backend Onboarding Suite** | **9 files** | **147** | **100% Passed (32.16s, zero mocks)** |

### 12.2 Frontend Verification
| Verification Command | Tests / Output | Result |
|---|---|---|
| `npm test` | 131 tests passing across 15 test suites | **PASS (5.1s)** |
| `npx tsc -b` | Full project TypeScript build | **PASS (0 errors)** |

### 12.3 Verification Commands
```powershell
# 1. Run all backend onboarding tests (Zero mocks)
.venv\Scripts\python.exe -m pytest tests/test_onboarding_text_and_intent_qa.py tests/test_onboarding_form_automation_qa.py tests/test_onboarding_takeover_concurrency_qa.py tests/test_onboarding_security_privacy_qa.py tests/test_onboarding_session_plan.py tests/test_onboarding_intent_normalizer.py tests/test_onboarding_delegation_guard.py tests/test_onboarding_api_router.py tests/test_onboarding_livekit_tool_gateway.py

# 2. Run frontend tests
npm test

# 3. Compile frontend TypeScript
npx tsc -b

# 4. Verify living documentation compliance (Rule 10)
.venv\Scripts\python.exe scripts/verify_living_docs.py
```

