# LiveKit Voice Assistant & Worker Subsystem

## Purpose & Scope

The `app/services/business_assistant/livekit` package implements the real-time media, participant token issuance, LiveKit Agent worker, and business tool gateway for the FastAPI Bookings conversational business assistant. It delivers a duplex voice interaction experience for authenticated business owners across the global application shell (onboarding, business settings, service catalog, calendar availability, website draft and review, and support tickets).

Key architectural tenets:
- **Global Application Scope**: Mounts inside the authenticated application shell and drawer, preserving conversations across client page navigation rather than binding to single pages.
- **Native GPT-Live Integration**: Employs LiveKit's `openai.realtime.GPTLiveModel` with `delegation="responses"` directed to `gpt-5.6-terra`, preserving the immutable session configuration baseline.
- **Narrowly Audited Tool Execution**: Connects agent function calls to authoritative backend business tools via `LiveKitToolGateway` and `BusinessAssistantToolRegistry` with tenant isolation and thread pool offloading.
- **Dual Transport Flexibility**: Operates seamlessly alongside the legacy direct WebRTC transport (`direct_gpt_live`), enabling zero-downtime rollback and failover.

---

## Architecture & Key Files

- `config.py`: Baseline configuration mapping and cryptographic integrity verification for `session_config.json` (SHA256 hash checking). Enforces strict model, voice, and delegation whitelists (`gpt-live-1`, `gleam`, `gpt-5.6-terra`).
- `token_service.py`: Generates authenticated LiveKit room participant tokens with opaque non-PII identities, scoped room grants (`room_record=False`), and named agent dispatch configuration.
- `router.py`: FastAPI endpoints for voice transport configuration (`GET /business-assistant/voice/transport`), session initiation (`POST /business-assistant/voice/conversations/{id}/session`), token refresh (`POST /business-assistant/voice/sessions/{id}/refresh`), and session release (`DELETE /business-assistant/voice/sessions/{id}`).
- `tool_gateway.py`: Bridges LiveKit function calls to `BusinessAssistantToolRegistry`. Enforces tenant and conversation authorization, audits execution results, offloads blocking SQLAlchemy queries to worker threads via `asyncio.to_thread`, and triggers client UI RPC actions.
- `caption_bridge.py`: Intercepts raw OpenAI server events (`session.input_transcript.delta`, `session.output_transcript.delta`, `session.started`, `session.closed`) from the duplex session. Preserves original millisecond timings and unicode characters, tracks session epochs/sequences, and monitors truthful provider finalization.
- `worker.py`: Standalone LiveKit agent worker entrypoint running `BusinessAssistantAgent` and `AgentSession`. Implements graceful job draining (`WorkerDrainState`) and enforces content recording disabled by default (`record=False`).

---

## Setup, Configuration & Dependencies

### Python Dependencies
The module requires the following pinned packages in the backend environment:
- `livekit-agents[openai]~=1.8`
- `livekit-api`

### Environment Variables
Configure the following environment variables in `.env` or the container environment:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `LIVEKIT_URL` | LiveKit Cloud or self-hosted server WebSocket URL | `ws://127.0.0.1:7880` |
| `LIVEKIT_API_KEY` | Server API key for LiveKit project | `None` (Required) |
| `LIVEKIT_API_SECRET` | Server API secret for LiveKit project | `None` (Required) |
| `OPENAI_API_KEY` | OpenAI project key with GPT-Live & Realtime permissions | `None` (Required) |
| `VOICE_ASSISTANT_TRANSPORT` | Authoritative default transport (`livekit_gpt_live` or `direct_gpt_live`) | `livekit_gpt_live` |
| `LIVEKIT_DEFAULT_AGENT_NAME`| Registered worker name for explicit named dispatch | `bookings-business-assistant` |
| `LIVEKIT_RECORD_BY_DEFAULT` | Cloud media/egress recording policy (enforced disabled) | `False` |

---

## Core Workflows & Contracts

### 1. Session Issuance & Named Dispatch
1. The authenticated frontend client sends `POST /business-assistant/voice/conversations/{conversation_id}/session`.
2. The server verifies tenant ownership, active user role, and checks global/tenant concurrency limits in `OperatorControlsService`.
3. `LiveKitTokenService` generates an opaque room ID (`room_<tenant_id>_<conv_id>_<uuid>`) and participant identity (`part_<user_id>_<uuid>`).
4. A short-lived JWT token is returned containing room grants (`room_record=False`, `egress=None`) and `RoomAgentDispatch` targeting `bookings-business-assistant` with opaque session metadata.

### 2. Duplex Audio & Realtime Captions
1. The browser connects to the LiveKit room via `LiveKitRoom` and publishes microphone audio.
2. The agent worker joins the room, subscribes to audio, and initiates `GPTLiveModel`.
3. `LiveKitCaptionBridge` subscribes directly to `openai_server_event_received` on `Agent.duplex_session`.
4. As transcript deltas arrive, `LiveKitCaptionBridge` broadcasts allowlisted payloads over the room data channel (`topic="assistant_captions"`), conveying exact Unicode deltas, `start_ms`, `end_ms`, epoch, and sequence counters.

### 3. Audited Business Tool Execution & UI Actions
1. When the user requests an application action, `GPTLiveModel` delegates tool invocation to `gpt-5.6-terra`.
2. The worker routes the call to `LiveKitToolGateway.execute_tool`, which resolves tenant context server-side and invokes `BusinessAssistantToolRegistry`.
3. Mutations are audited and executed within isolated database transactions.
4. For UI actions (e.g., website draft creation, section edits), the gateway performs client RPC calls (`assistant_ui_action`) to trigger preview toggles, section highlights, or drawer opens while the owner watches.

### 4. Truthful Finalization Lifecycle
1. When voice ends, shutdown is signaled to the session.
2. The worker awaits the terminal `session.closed` provider event via `caption_bridge.wait_for_closed(timeout=2.0)`.
3. If `session.closed` is received, the session is recorded as `finalised=True`. If a timeout or abrupt network disconnect occurs, it is truthfully marked `finalised=False` (finalization incomplete).

---

## Data Safety & Isolation

- **Tenant Isolation**: Every tool call strictly derives tenant and user IDs from the authenticated server dispatch metadata. Cross-tenant access is rejected at the database query layer.
- **Non-PII Identifiers**: Room names and participant identities use opaque UUIDs and numeric IDs. Personal names, emails, and phone numbers are never embedded in room metadata or JWT claims.
- **Recording Disabled by Default**: `record=False` is passed explicitly to `AgentSession.start()`, `room_record=False` is set on all video grants, and `egress=None` is configured. Diagnostic recording never captures audio or transcripts without separate opt-in approval.
- **Secret Masking & Telemetry Safety**: Credentials (`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `OPENAI_API_KEY`) are masked in all health checks and diagnostic logs. Telemetry records only coarse metrics and status codes without prompts, tool parameters, or transcript bodies.

---

## Known Issues, Edge Cases & Outstanding Work

- **Provider Quota Saturation (429)**: When OpenAI Realtime quota is exhausted, token creation returns HTTP 429 `LIVEKIT_QUOTA_EXHAUSTED`. The frontend gracefully notifies the user and offers text-mode assistance or fallback to direct WebRTC.
- **Robust Exception Handling & Safe Degradation (503/502/429)**: Unconfigured credentials (`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `XAI_API_KEY`) safely return HTTP 503 (`LIVEKIT_CONFIGURATION_REQUIRED` or `XAI_CONFIGURATION_REQUIRED`) without bubbling up unhandled HTTP 500 errors. Token generation failures and missing credentials raise clean 503s, while LiveKit media network disconnections raise HTTP 502 (`LIVEKIT_NETWORK_DISCONNECTED`).
- **Staff-Role Authorization Scope**: All voice session endpoints (`/session`, `/heartbeat`, `/refresh`, `/sessions/{id}`, `/prune`) accept all authorized staff and provider roles (`Depends(get_current_staff)`), avoiding unexpected 403 or 500 errors for internal team members.
- **Multi-Transport Routing (3-Mode Toggle)**: Supports `direct_gpt_live` (standalone WebRTC discovery/session), `local_livekit` (`ws://127.0.0.1:7880`), `cloud_livekit` (LiveKit Cloud), and `xai_grok_voice` (WebSocket realtime proxy), dynamically switchable via `PATCH /transport`.
- **Microphone Permission Handling**: Browser permission revocation mid-call produces WebRTC track mute events; client UI surfaces clear recovery prompts.
- **Network Handover & Reconnection**: WebRTC ICE restarts over unstable networks trigger new session epochs; `LiveKitCaptionBridge` increments its epoch counter and resets sequence numbers to prevent transcript interleaving.

---

## Verification & Testing Commands

Execute the complete LiveKit test suite using pytest:

```powershell
# Run all LiveKit test suites
.\.venv\Scripts\python.exe -m pytest tests/test_livekit_worker_baseline.py `
  tests/test_livekit_token_dispatch.py `
  tests/test_livekit_tool_gateway.py `
  tests/test_livekit_caption_bridge.py `
  tests/test_livekit_website_tools.py `
  tests/test_livekit_concurrency_load.py `
  tests/test_livekit_synthetic_scenarios.py -q

# Run living documentation linter
python scripts/verify_living_docs.py --path app/services/business_assistant/livekit/README.md
```
