# UI Agent DOM Automation, Ghost Cursor & Voice Delegation Suite

## 1. Purpose & Scope
The **UI Agent DOM Automation, Ghost Cursor & Voice Delegation Suite** provides live visual element scanning, automated synthetic user interaction, an animated Ghost Cursor overlay, and conversational voice control (GPT-Live & Grok Voice) for the administrative workspace in FastAPI Bookings.
- **What it owns**:
  - DOM visual element scanning (`scanPage`, `labelFor`, `refOf`, `findByRef`) with accessible name extraction and ref tagging.
  - Synthetic user interaction execution (`createExecutor`, `setNativeValue`, `realClick`, `pressEnter`) targeting inputs, selects, Radix UI comboboxes, and datepicker popovers.
  - Ghost Cursor overlay (`GhostCursor.tsx`) with spring-animated cursor pointer, target focus glow, pulse ripples, and floating action tags.
  - State machine and observation loop (`AgentProvider.tsx`) with step progression, pause/stop/replay, speed control (`slow`, `realistic`, `fast`), and SSE streaming integration.
  - Hands-free wake word recognition (`wakeWord.ts`) supporting continuous browser speech recognition with phonetic consonant skeleton matching.
  - Realtime voice delegation engines (`voice/openaiLive.ts`, `voice/grokVoice.ts`):
    - **OpenAI Live Delegation**: Employs OpenAI Live with `"delegation": {"type": "client"}`, preventing WebRTC tool lockups by delegating DOM tasks directly to the UI Agent.
    - **Grok Voice Realtime**: Connects to xAI Realtime via WebSockets with a single `operate_app` function tool for natural voice operations.
  - Realtime voice delegation engines (`voice/openaiLive.ts`, `voice/grokVoice.ts`):
    - **OpenAI Live Delegation**: Employs OpenAI Live with `"delegation": {"type": "client"}`, preventing WebRTC tool lockups by delegating DOM tasks directly to the UI Agent.
    - **Grok Voice Realtime**: Connects to xAI Realtime via WebSockets with a single `operate_app` function tool for natural voice operations.
  - Full UI controls and indicators:
    - Unified Assistant Popup (`components/agents-ui/agent-popup.tsx`) housing full voice selection, wake-word toggle, DOM automation speed, and session controls.
    - Prominent visual takeover banner (`AgentControlBanner.tsx`) displaying a soft slow red pulse indicator whenever the agent is driving the screen.
    - Floating mobile controller and speech bubble (`MobileAgent.tsx`).
    - Audio pulse bar with sleep timer countdown and provider indicators (`VoiceBar.tsx`).
    - Settings panel (`SettingsPanel.tsx`) for voice selection, wake phrase editing, sleep timeout, and agent speed.
  - Streaming SSE communication (`stream.ts`) communicating with `/api/admin/ui-agent/chat/stream`.
  - RPC bridge (`operate_app`) connecting the Business Assistant and Grok Voice tool runners to live UI automation.
- **What it deliberately avoids**:
  - Direct database mutations (all backend state alterations must go through authoritative authenticated API routes).
  - Bypassing tenant security or administrative authentication boundaries.
  - Fabricating synthetic delays or mock data in production environments.

## 2. Architecture & Key Files
- `scanner.ts`: Scans interactive elements (`a`, `button`, `input`, `select`, `textarea`, `role="combobox"`, etc.), assigns stable reference keys (`data-agent-ref` or `data-testid`), resolves accessible labels, and generates structured page snapshots.
- `executor.ts`: Dispatches pointer and keyboard events using native prototype descriptor property setters (supporting React controlled inputs), Radix UI popover menus, and calendar navigation.
- `GhostCursor.tsx`: Renders spring-physics cursor pointer and highlighting borders using `framer-motion` and `lucide-react`.
- `AgentControlBanner.tsx`: Top-center floating takeover indicator (`● Agent in Control — Please wait while automated actions complete`) with soft slow red pulse animation active during DOM execution.
- `stream.ts`: Consumes server-sent events (SSE) from `/api/admin/ui-agent/chat/stream`, emitting deltas and executing final action arrays.
- `AgentProvider.tsx`: Context provider managing session lifecycle, step counter, speed settings, error states, and listening for global `ui-agent:operate` and `operate_app` events.
- `wakeWord.ts`: Continuous SpeechRecognition engine detecting wake phrases hands-free with phonetic normalization.
- `voice/providers.ts`: Configuration for voice engines (GPT-Live, Grok Voice) and idle sleep durations.
- `voice/openaiLive.ts`: WebRTC client for OpenAI Live using native client delegation.
- `voice/grokVoice.ts`: WebSocket client for xAI Realtime voice using the `operate_app` tool.
- `VoiceProvider.tsx`: React context orchestrating voice engines, wake word listeners, caption streaming, and inactivity sleep timers.
- `VoiceBar.tsx`: Embedded audio bar displaying active provider, voice status, wake word badge, and sleep countdown.
- `AgentSidebar.tsx`: Legacy desktop sidebar component (retired from default admin layout in favor of consolidated popup controls).
- `MobileAgent.tsx`: Floating mobile action button and caption bubble for small screens.
- `SettingsPanel.tsx`: Configuration panel for voices, wake phrase, speed, and session reset.
- `index.ts`: Package entry point re-exporting scanner, executor, cursor, banner, voice, and layout components.
- `ui-agent.test.ts`: Automated test suite verifying DOM scanning, action execution, wake word detection, SSE parsing, takeover banner, and RPC event dispatch.

## 3. Setup, Configuration & Dependencies
- **Frontend Dependencies**:
  - `react`, `react-dom`, `react-router-dom`
  - `framer-motion` (for spring-physics cursor, 3D flip panel, and focus tag animations)
  - `lucide-react` (for icons)
- **Backend API**:
  - `POST /api/admin/ui-agent/chat/stream`: SSE step planning stream.
  - `POST /api/admin/ui-agent/chat`: Synchronous action execution.
  - `POST /api/admin/ui-agent/sessions/{session_id}/final`: Final results audit endpoint.
  - `GET /api/admin/ui-agent/sessions/{session_id}/timeline`: Session history timeline.
  - `DELETE /api/admin/ui-agent/sessions/{session_id}`: Session cleanup.
  - `GET /api/admin/ui-agent/voice/providers`: Check OpenAI and xAI API key availability.
  - `POST /api/admin/ui-agent/voice/openai/session`: OpenAI Live WebRTC SDP negotiation with client delegation.
  - `POST /api/admin/ui-agent/voice/xai/token`: Ephemeral xAI Realtime client token generation.
- **Environment Variables**:
  - `OPENAI_API_KEY`: API key for step planning model and GPT-Live voice.
  - `XAI_API_KEY`: API key for Grok Voice realtime WebSocket sessions.
  - `LLM_BASE_URL`: Optional custom OpenAI-compatible endpoint.
  - `LLM_MODEL`: Model name (default: `gpt-4o-mini`).

## 4. Core Workflows & Contracts
### Inbound / Outbound Action Lifecycle
1. **Triggering Automation**:
   - An operator issues a text prompt in `AgentSidebar`, clicks a suggestion chip, speaks aloud to GPT-Live/Grok Voice, or triggers an `operate_app` RPC action.
   - For hands-free interaction, the operator says the wake word (e.g. *"Hey Aether"*), which automatically activates the voice session.
2. **Client Delegation (No WebRTC Lockups)**:
   - When using GPT-Live, requests emit `session.delegation.created`. The client `onDelegate` handler receives the intent and invokes `send(request)` on `AgentProvider`.
   - The voice agent acknowledges the user while the UI Agent executes the required DOM actions.
   - `openaiLive.ts` negotiates `POST /api/admin/ui-agent/voice/openai/session` configured specifically with `gpt-live-1`, verifying that local microphone tracks are attached to the peer connection and that the SDP offer contains a valid audio media section (`m=audio`) prior to dispatch.
   - Web Audio API instances (`AudioContext`) are lazy-initialized strictly on explicit user gesture / connection initiation via `createSafeAudioContext`, wrapping initialization in sample rate fallback logic (24000 Hz falling back to system default) and attaching state change listeners to prevent device renderer errors.
3. **DOM Snapshotting & SSE Step Generation**:
   - `AgentProvider` captures `scanPage()` containing the current route, page text, alerts, and visible interactable elements.
   - Sent to `/api/admin/ui-agent/chat/stream`, streaming deltas and concrete structured actions (`click`, `type`, `select`, `pick_date`, `navigate`).
4. **Execution & Ghost Cursor Animation**:
   - `createExecutor` smoothly scrolls elements into view, positions the Ghost Cursor, triggers the pulse ripple, sets the input values, and logs execution in the action stream console.
5. **Observation Turn & Commentary Relay**:
   - If `continue: true` is returned, the new DOM state is rescanned and submitted back to the agent until the goal completes, bounded by `MAX_STEPS = 20` actions per turn loop.
   - When finished, the UI Agent's spoken message is passed to `session.commentary.append`, allowing GPT-Live or Grok Voice to speak the conclusion naturally.

## 5. Data Safety & Isolation
- **Tenant Isolation**: Every backend endpoint requires authenticated tenant credentials via `get_current_tenant_user`. Session histories, voice tokens, and final execution audits are strictly segregated by `(tenant_id, session_id)`.
- **Credential & Secret Protection**: No bearer tokens, authorization headers, or customer PII are logged or stored in DOM element tags.
- **Bounded History**: In-memory session buffers are capped to the most recent 30 turns per session to avoid unbounded memory consumption.

## 6. Known Issues, Edge Cases & Outstanding Work
- Custom canvas elements or external iframes without accessible DOM tree nodes cannot be scanned by `scanner.ts`.
- Complex nested drag-and-drop interactions currently require manual operator takeover.
- Browser SpeechRecognition requires Chrome, Edge, or Safari for the hands-free wake word listener.
- Hardware audio outputs that reject explicit 24000 Hz sample rates fall back to the host audio renderer's default sample rate.

## 7. Verification & Testing Commands
- **Frontend Unit & Component Tests**:
  ```bash
  cd frontend
  node --experimental-strip-types --test "src/components/ui-agent/**/*.test.ts"
  npm test
  ```
- **Frontend Production Build Check**:
  ```bash
  cd frontend
  npm run build
  ```
- **Backend API Tests**:
  ```bash
  .\.venv\Scripts\python.exe -m pytest tests/test_ui_agent.py -v
  ```
- **Living Documentation Verification**:
  ```bash
  python scripts/verify_living_docs.py --path frontend/src/components/ui-agent/README.md
  ```
