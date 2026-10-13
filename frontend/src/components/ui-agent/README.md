# UI Agent DOM Automation & Ghost Cursor Engine

## 1. Purpose & Scope
The **UI Agent DOM Automation & Ghost Cursor Engine** provides live visual element scanning, automated synthetic user interaction, and an animated Ghost Cursor overlay for the administrative workspace in FastAPI Bookings.
- **What it owns**:
  - DOM visual element scanning (`scanPage`, `labelFor`, `refOf`, `findByRef`) with accessible name extraction and ref tagging.
  - Synthetic user interaction execution (`createExecutor`, `setNativeValue`, `realClick`, `pressEnter`) targeting inputs, selects, Radix UI comboboxes, and datepicker popovers.
  - Ghost Cursor overlay (`GhostCursor.tsx`) with spring-animated cursor pointer, target focus glow, pulse ripples, and floating action tags.
  - State machine and observation loop (`AgentProvider.tsx`) with step progression, pause/stop/replay, speed control, and SSE streaming integration.
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
- `stream.ts`: Consumes server-sent events (SSE) from `/api/admin/ui-agent/chat/stream`, emitting deltas and executing final action arrays.
- `AgentProvider.tsx`: Context provider managing session lifecycle, step counter, speed settings, error states, and listening for global `ui-agent:operate` and `operate_app` events.
- `index.ts`: Package entry point re-exporting scanner, executor, cursor, stream, and provider.
- `ui-agent.test.ts`: Automated test suite verifying DOM scanning, action execution, SSE parsing, and RPC event dispatch.

## 3. Setup, Configuration & Dependencies
- **Frontend Dependencies**:
  - `react`, `react-dom`, `react-router-dom`
  - `framer-motion` (for spring-physics cursor and focus tag animations)
  - `lucide-react` (for cursor icons)
- **Backend API**:
  - `POST /api/admin/ui-agent/chat/stream`: SSE step planning stream.
  - `POST /api/admin/ui-agent/chat`: Synchronous action execution.
  - `POST /api/admin/ui-agent/sessions/{session_id}/final`: Final results audit endpoint.
  - `GET /api/admin/ui-agent/sessions/{session_id}/timeline`: Session history timeline.
  - `DELETE /api/admin/ui-agent/sessions/{session_id}`: Session cleanup.
- **Environment Variables**:
  - `OPENAI_API_KEY`: API key for step planning model (falls back to deterministic inspection when unconfigured).
  - `LLM_BASE_URL`: Optional custom OpenAI-compatible endpoint.
  - `LLM_MODEL`: Model name (default: `gpt-4o-mini`).

## 4. Core Workflows & Contracts
### Inbound / Outbound Action Lifecycle
1. **Triggering Automation**:
   - An operator or voice assistant issues an `operate_app` RPC action with instructions (e.g. `"Navigate to services and create new service"`).
   - `executeRpcAction('operate_app', ...)` dispatches the custom event `ui-agent:operate`.
2. **DOM Snapshotting**:
   - `AgentProvider` captures `scanPage()` containing the current route, page text, alerts, and visible interactable elements.
3. **SSE Step Generation**:
   - `AgentProvider` sends `message` and `page_state` to `/api/admin/ui-agent/chat/stream`.
   - The backend LLM streams textual explanations (`delta`) followed by concrete structured actions (`click`, `type`, `select`, `pick_date`, `navigate`).
4. **Execution & Ghost Cursor Animation**:
   - `createExecutor` smoothly scrolls elements into view, positions the Ghost Cursor, triggers the pulse ripple, sets the input values, and reports execution status.
5. **Observation Turn**:
   - If `continue: true` is returned, the new DOM state is rescanned and submitted back to the agent until the goal completes.

## 5. Data Safety & Isolation
- **Tenant Isolation**: Every backend endpoint requires authenticated tenant credentials via `get_current_tenant_user`. Session histories and final execution audits are strictly segregated by `(tenant_id, session_id)`.
- **Credential & Secret Protection**: No bearer tokens, authorization headers, or customer PII are logged or stored in DOM element tags.
- **Bounded History**: In-memory session buffers are capped to the most recent 30 turns per session to avoid unbounded memory consumption.

## 6. Known Issues, Edge Cases & Outstanding Work
- Custom canvas elements or external iframes without accessible DOM tree nodes cannot be scanned by `scanner.ts`.
- Complex nested drag-and-drop interactions currently require manual operator takeover.

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
