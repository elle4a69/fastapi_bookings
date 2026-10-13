# Unified Business Assistant & Voice Agent Popup (`agents-ui`)

## 1. Purpose & Scope
The **Unified Business Assistant & Voice Agent Popup (`agents-ui`)** delivers the authoritative floating assistant experience across the administrative workspace in FastAPI Bookings.
- **What it owns**:
  - Floating circular trigger button (`AgentPopup_01` / `AgentPopup`) positioned at the bottom-right viewport anchor.
  - Expandable assistant card with full conversation history, realtime streaming captions, and pre-connect prompt buffers.
  - Consolidated assistant settings panel:
    - Realtime Voice Engine selection (OpenAI GPT-Live vs xAI Grok Voice).
    - Speaking voice timbre dropdown (`marin`, `cedar`, `quartz`, `eve`, `ara`, etc.).
    - Hands-free continuous wake-word listener toggle (`Hey Aether` by default) with speech recognition status.
    - DOM automation speed adjustment (`slow`, `realistic`, `fast`).
    - Auto-sleep inactivity timeout selection (`0`, `30s`, `60s`, `120s`, `300s`).
    - Diagnostic telemetry toggles and session reset.
  - Integrated DOM automation bridge: User-entered navigation or manipulation prompts automatically invoke `useAgent().send()` to drive page interactions via GhostCursor alongside conversation turns.
  - Video and screen sharing media previews with automated track disposal upon session hangup.
  - Animated 3-bar audio visualizer with microphone device enumeration and input switching.
  - Minimized floating session pill displayed while calls remain active in background mode.
- **What it deliberately avoids**:
  - Clunky fixed sidebars (`AgentSidebar`) or floating bottom status bars (`OnboardingStatusDock`).
  - Synthetic delays, mock implementations, or fake backend responses.
  - Direct database access (all interactions strictly pass through authenticated REST/WebSocket/WebRTC gateways).

## 2. Architecture & Key Files
- `agent-popup.tsx`: The primary unified component rendering the floating button, card dialog, active pill, settings panel, transcript stream, and input controls.
- `index.ts`: Package entry point re-exporting `AgentPopup` and its alias `AgentPopup_01`.
- `agent-popup.test.ts`: Node-based regression test suite verifying component spec, audio visualizer, media track cleanup, context lifecycle hooks, and consolidated settings controls.

## 3. Setup, Configuration & Dependencies
- **Context Providers Required in Layout (`admin-layout.tsx`)**:
  - `BusinessAssistantProvider`: Manages conversation history, message turns, LiveKit/GPT-Live/Grok voice transports, and device lists.
  - `AgentProvider`: Manages UI element scanning, synthetic DOM actions, step counters, Ghost Cursor, and speed settings.
  - `VoiceProvider`: Manages speech-to-speech WebRTC/WebSocket connections, wake-word detection, and auto-sleep timers.
- **UI Dependencies**:
  - `@/components/ui/button`, `@/components/ui/dropdown-menu`, `@/lib/utils`
  - `lucide-react`: Icons for bot, mic, camera, monitor, ear, settings, and sparkles.
- **Environment & Keys**:
  - `OPENAI_API_KEY`: Powers direct GPT-Live voice and UI Agent step planning.
  - `XAI_API_KEY`: Powers xAI Grok Voice realtime WebSocket sessions.

## 4. Core Workflows & Contracts
### 1. Unified Floating Lifecycle
- Operators click the floating bot trigger at the bottom right (`livekit-agent-popup-trigger`) to toggle the assistant card.
- If voice is currently idle, opening the popup automatically establishes the audio transport.
- Minimizing the popup closes the card while keeping voice alive, surfacing the compact status pill (`agent-popup-active-pill`) with quick mute and hang-up actions.
- Hanging up via `agent-popup-leave-button` cleanly stops voice, audio streams, camera video, and screen sharing tracks.

### 2. Hands-Free Wake Word & Speech Delegation
- Operators can enable continuous wake-word listening in the Settings panel (`wake-word-toggle`).
- When the wake phrase (e.g. *"Hey Aether"*) is recognized by the browser's speech recognition engine, the voice session automatically starts.
- Speech delegates to `useAgent().send()` to execute physical DOM actions (clicking, typing, selecting) while streaming captions in the popup.

### 3. DOM Automation Driving
- Submitting an imperative instruction (e.g. *"Navigate to services"*, *"Fill client name"*) in the typing input dispatches the text to `useAgent().send()` for immediate browser automation, while recording the turn in the backend conversation transcript.

## 5. Data Safety & Isolation
- **Tenant Isolation**: All conversation turns, session keys, and voice tokens are authenticated and tenant-scoped via `get_current_tenant_user`.
- **Media Privacy**: Camera and screen share streams are retained in ephemeral component refs and strictly terminated when minimizing or leaving sessions.
- **No Credentials Leaked**: No bearer tokens, API secrets, or sensitive customer notes are committed to browser storage or exposed in DOM attributes.

## 6. Known Issues, Edge Cases & Outstanding Work
- Wake word speech recognition depends on Chromium, Edge, or Safari support for `webkitSpeechRecognition` or `SpeechRecognition`.
- Display media (screen share) requires user consent and a secure browser context (`https://` or `localhost`).
- Simultaneous microphone access across multiple open browser tabs may require selecting the specific device in the audio input dropdown.

## 7. Verification & Testing Commands
- **Frontend Component Tests**:
  ```bash
  cd frontend
  node --experimental-strip-types --test "src/components/agents-ui/**/*.test.ts"
  npm test
  ```
- **Frontend Production Build**:
  ```bash
  cd frontend
  npm run build
  ```
- **Living Documentation Compliance Linter**:
  ```bash
  python scripts/verify_living_docs.py --path frontend/src/components/agents-ui/README.md
  ```
