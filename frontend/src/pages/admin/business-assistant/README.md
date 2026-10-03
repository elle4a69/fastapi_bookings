# Business Assistant Page (`frontend/src/pages/admin/business-assistant`)

The Business Assistant frontend module provides the administrative conversational dialogue interface and real-time WebRTC voice session management for business owners and operators within **FastAPI Bookings**.

---

## 1. Purpose & Scope

This page provides the owner/admin text and voice conversation interface. It renders only persisted tenant-scoped history returned by the backend and does not generate browser-side replies or simulate processing.

Key capabilities owned by this module:
- Direct interactive chat interface for administrative enquiries, policy guidance, and business operations.
- Persisted conversation history drawer (closed by default) accessible via desktop action or mobile control without disrupting the active thread.
- Real-time WebRTC voice interaction with SDP negotiation for natural voice dialogue.
- Transcript synchronization and turn pairing back to backend conversation models.

This module deliberately avoids executing direct mutations on client bookings, inventing fake LLM responses in the browser (AGENTS.md Rule 3), or exposing external AI provider credentials to the client.

---

## 2. Architecture & Key Files

```
frontend/src/pages/admin/business-assistant/
├── index.tsx                             # Master conversational viewport, message list, input bar, and history drawer
├── realtime-voice-protocol.ts            # WebRTC SDP negotiation & event message schemas
├── use-business-assistant-realtime-voice.ts # Custom React hook for microphone capture and WebRTC peer connection
├── business-assistant-page.test.ts       # Page component and render test suite
├── realtime-voice-protocol.test.ts       # Protocol parser and validation tests
└── README.md                             # Living documentation
```

### Key Files:
- [index.tsx](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/index.tsx): Primary view rendering message bubbles, markdown text, status indicators, and the conversation switcher drawer.
- [realtime-voice-protocol.ts](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/realtime-voice-protocol.ts): Encapsulates message types, SDP offer/answer serialization, and event payloads for WebRTC voice streaming.
- [use-business-assistant-realtime-voice.ts](file:///f:/Projects/fastapi_bookings/frontend/src/pages/admin/business-assistant/use-business-assistant-realtime-voice.ts): Manages local audio capture (`navigator.mediaDevices.getUserMedia`), peer connection lifecycle, and microphone mute/unmute states.

---

## 3. Setup, Configuration & Dependencies

### Runtime Dependencies
- **React & TypeScript**: Component tree and strongly typed state hooks.
- **Lucide React**: Iconography for microphone, send, history drawer, and audio visualizers.
- **WebRTC API**: Native browser `RTCPeerConnection` and audio stream APIs.
- **Axios Client**: Shared HTTP API client injecting `Authorization: Bearer <token>` and `X-Tenant` headers.

### Environment & Permissions
- Requires browser permission for microphone access when using voice mode.
- Communicates with backend endpoints mounted at `/api/admin/business-assistant`.

---

## 4. Core Workflows & Contracts

### 4.1 Text Conversation Lifecycle
1. **Thread Loading**: On mount, loads recent conversations via `GET /api/admin/business-assistant/conversations`.
2. **Message Dispatch**: Submitting a user prompt calls `POST /api/admin/business-assistant/conversations/{id}/messages`.
3. **Turn Persistence**: Displays streaming or completed assistant turns returned from the backend; errors are rendered inline.

### 4.2 Realtime Voice Exchange
1. **SDP Handshake**: Invokes `POST /api/admin/business-assistant/conversations/{id}/realtime` with client SDP offer.
2. **Peer Connection**: Sets remote description from server SDP answer and begins bi-directional Opus audio streaming.
3. **Transcript Synchronization**: When an audio turn concludes, completed transcript turns are persisted to `/realtime/turns`.

---

## 5. Data Safety & Isolation

- **Tenant Boundary Enforcement**: All API requests transmit tenant identity via standard authentication headers; the browser cannot access or inspect conversations belonging to another tenant.
- **Credential Protection**: OpenAI API tokens or backend secrets are never exposed to browser memory or client-side WebRTC configurations.
- **No Mock Fallbacks (Rule 3)**: If the backend service is offline, the interface displays a clear network error rather than manufacturing fake responses.
- **Audio Privacy**: Microphone streams are active only while the voice session is explicitly toggled ON by the user.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Microphone Permissions Denied**: If a user rejects audio access, the interface gracefully disables voice controls and retains full text-mode capability.
- **WebRTC Reconnection Under Network Flaps**: Transient network disconnections during voice streaming require tearing down and re-establishing the peer connection.
- **Tool Invocations Disabled in Voice**: Realtime voice tools are disabled in the initial release; voice mode operates in conversational advice mode only.

---

## 7. Verification & Testing Commands

To run the unit tests and frontend validation for the business assistant module:

```powershell
# 1. Run Node.js tests for voice protocol and page rendering
npm test -- src/pages/admin/business-assistant

# 2. Run TypeScript strict type-check
npx tsc --noEmit

# 3. Run frontend linter
npm run lint
```
