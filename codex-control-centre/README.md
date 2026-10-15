# Codex Control Centre

Codex Control Centre is the main coordination, telemetry, and governance hub for multi-agent workflows. It provides real-time event streaming, thread management, tool approval gating, subagent supervision, and isolated git worktrees.

> **WP-UI-00 ownership and freeze:** The canonical browser application is the repository-root `frontend/`. The duplicate `codex-control-centre/frontend/` tree is frozen as reference/decommission-only and must receive no new product features. The current `/admin/coding-cockpit` remains the operational v1 interface during controlled migration. The future `/api/admin/codex/v2` facade, durable supervisor domain and replacement interface are specified but not implemented; see [`../docs/architecture/ADR_CODEX_SUPERVISOR_V2_FACADE.md`](../docs/architecture/ADR_CODEX_SUPERVISOR_V2_FACADE.md).

---

## 1. Purpose & Scope

Codex Control Centre provides an enterprise-grade supervisory control plane and developer workbench for OpenAI Codex App-Server (`codex app-server`).
- **Core Ownership**:
  - Direct stdio JSON-RPC 2.0 communication with `codex app-server` worker subprocesses.
  - Multi-tenant thread and turn lifecycle management with resilient start, steer, and interrupt operations.
  - Real-time Server-Sent Events (SSE) streaming with event buffering, single-use ticket dispatch, and optimistic turn reconciliation.
  - Human-in-the-loop tool execution approval gates with risk-tier evaluation (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
  - Authenticated plugin catalog discovery, plugin installation, provider authorization handoff, and app-server initiated input/permission request handling.
  - Git worktree sandboxing ensuring all tool calls and edits occur in isolated worktrees (`worktrees/wt-<thread_id>`).
  - Telemetry pipeline exporting spans, metrics, and logs to SigNoz / OpenTelemetry collectors.
- **Explicit Non-Goals**:
  - Does not replace primary booking application database models or business domains.
  - Does not expose raw shell execution or bypass governance evaluation on mutating tools.

---

## 2. Architecture & Key Files

```
                  +-----------------------------------+
                  |        React + Vite Frontend      |
                  |     (Tailwind CSS + Radix UI)     |
                  +-----------------+-----------------+
                                    |
                           HTTP / SSE Stream
                                    |
                  +-----------------v-----------------+
                  |       FastAPI Backend Hub         |
                  |  (Auth, Routers, Event Broker)    |
                  +--------+------------------+-------+
                           |                  |
           +---------------+                  +---------------+
           |                                                  |
+----------v-----------+                          +-----------v-----------+
|  SQLite (Alembic DB) |                          | Worker Supervisor &   |
|   StaticPool Engine  |                          | Governance Manager    |
+----------------------+                          +-----------+-----------+
                                                              |
                                                      JSON-RPC 2.0 stdio
                                                              |
                                                  +-----------v-----------+
                                                  |   Codex App-Server    |
                                                  | (Sandboxed Worktree)  |
                                                  +-----------------------+
```

### Directory Layout & Key Files
- `backend/`:
  - `main.py`: FastAPI application factory, CORS policies, routers, exception handlers.
  - `config.py`: Application settings, environment overrides, CLI flags, loopback binding.
  - `database.py`: SQLAlchemy engine, session management with SQLite foreign key pragmas.
  - `routers/`:
    - `turns.py`: Turn execution lifecycle (`/start`, `/steer`, `/interrupt`), resilient turn ID resolution.
    - `events.py`: SSE endpoints (`/codex/events/{project_id}/{thread_id}`), single-use tickets, broker bridge.
    - `models.py`: Supported model catalog enumeration (`/models`, `/codex/models`).
    - `governance.py`: Approvals, risk tiering, subagent registration, concurrency enforcement.
    - `plugins.py`: Sanitized app-server plugin catalog, detail, and install bridge.
    - `skills.py`: Authenticated proxy for port 8008 hybrid skill search, statistics, and on-demand reads.
    - `worktrees.py`: Git worktree creation, validation, dirty-check deletion.
    - `diagnostics.py`: Readiness, liveness, SigNoz connectivity probes.
- **FastAPI Bookings Administrative Integration**:
  All primary Codex routers are mounted directly into FastAPI Bookings under `/api/admin/codex/*`. The integrated cockpit is a global development control plane and therefore requires `require_platform_owner`; ordinary tenant administrators and managers have no authority over its projects, threads, settings, worktrees, diagnostics, governance, plugins, or skills.
  - `services/`:
    - `worker.py`: Subprocess management, stdio JSON-RPC protocol dispatch, event routing.
    - `worker_manager.py`: Thread-to-worker process pool, graceful restart and teardown.
    - `protocol.py`: JSON-RPC message normalization (`agent_message`, `reasoning`, `turn_completed`, `turn_failed`).
    - `event_service.py`: In-memory thread-scoped SSE event broker with historical replay.
    - `sse_tickets.py`: Short-lived authorization tickets atomically removed on first valid consumption.
    - `telemetry.py`: SigNoz / OpenTelemetry instrumentation and fallback logger.
    - `skills_context.py`: Privacy-bounded skill query derivation, top-match retrieval, content budgets, and turn context assembly.
    - `skills_rag_mcp_bridge.py`: Dependency-free stdio MCP bridge exposing native read-only `find` and `skill` tools backed by the always-on port 8008 daemon.
- `frontend/` (**legacy duplicate; frozen reference/decommission-only, not the canonical FastAPI Bookings frontend**):
  - `src/App.tsx`: Root responsive 3-pane workbench container with mobile off-canvas drawer navigation and tablet/mobile overlay backdrops.
  - `src/components/layout/ProjectRail.tsx`: Project switcher, theme toggle, and settings triggers with touch-first tap targets.
  - `src/components/layout/ThreadSidebar.tsx`: Thread search, thread creation, pinned and archived thread lists.
  - `src/components/layout/ThreadHeader.tsx`: Responsive header with mobile hamburger trigger, truncated breadcrumbs, compaction gauge, and inspector toggle.
  - `src/components/inspector/Inspector.tsx`: Adaptive panel (in-flow on desktop >1024px, slide-over overlay on tablet 768px-1023px, full-width sheet on mobile <768px).
  - `src/components/composer/Composer.tsx`: Prompt input, model selector, reasoning controls, responsive wrapping toolbar with 44px tap targets. The FastAPI-mounted cockpit owns the current shared catalog and sticky preference.
  - `src/components/timeline/Timeline.tsx`: Virtualized event timeline with unique React keys, subagent filtering, and mobile horizontal containment.
  - `src/components/timeline/SubagentTabBar.tsx`: Horizontal interactive tab strip placed at the top of the timeline for switching between Main Orchestrator and child subagents with live status badges.
  - `src/components/timeline/LiveActivityPulse.tsx`: Pinned execution pulse beacon above the composer displaying active action, elapsed seconds, and an inline Stop / Interrupt button.
  - `src/components/timeline/items/ReasoningSummaryItem.tsx`: Dynamic auto-scrolling live reasoning accordion displaying real-time streaming tokens and thought trace.
  - `src/store/useWorkbenchStore.ts`: Global state, SSE reducer, subagent lifecycle events (`subagent_started`, `subagent_progress`, `subagent_completed`), live action tracking, optimistic turn adoption, turn interruption.
  - `src/api/codexApi.ts`: REST and SSE client wrappers.
  - `src/types/workbench.ts`: TypeScript contracts and DTO interfaces.

---

## 3. Setup, Configuration & Dependencies

### Prerequisites
- **Python**: 3.11+
- **Node.js**: 20+
- **Git**: 2.30+
- **Codex CLI**: Native executable (`codex.exe`) authenticated via OpenAI account.

### Installation
```bash
# Backend dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Database migrations
alembic upgrade head

# Frontend dependencies
cd frontend
npm install
cd ..
```

### Configuration Reference
Set these variables in `.env` or system environment:

| Variable | Default Value | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./codex.db` | SQLAlchemy database connection string. |
| `HOST` | `127.0.0.1` | Host address to bind the API server. |
| `PORT` | `4500` | Port for the API server. |
| `TOKEN_SECRET` | `local_secret` | Standalone-only compatibility secret. It is never accepted by the FastAPI Bookings mount; standalone deployments must override the default before exposure. |
| `SIGNOZ_URL` | `http://localhost:3301` | SigNoz telemetry collector URL (can also be dynamically managed in UI). |
| `OTLP_ENDPOINT` | `http://localhost:4318` | OpenTelemetry OTLP endpoint (can also be dynamically managed in UI). |
| `ALLOWED_BOUNDARIES` | `["<codex_dir>"]` | Comma-separated or JSON list of initial allowed workspace base boundaries. |
| `WORKTREES_DIR` | `<root>/worktrees` | Directory path for isolated git worktrees. |
| `CODEX_BIN_PATH` | `codex` | Path to Codex App-Server executable (automatically resolves to native `codex.exe`). |
| `CODEX_APP_SERVER_ARGS` | `["app-server"]` | Command line arguments passed when launching the Codex App-Server subprocess. |
| `CODEX_TRANSPORT` | `stdio` | Transport protocol used for communication with the worker process (`stdio`). |
| `CODEX_WORKER_TIMEOUT_SECONDS` | `60` | Default timeout in seconds for JSON-RPC requests sent to the worker process. |
| `SKILLS_RAG_URL` | `http://127.0.0.1:8008` | Loopback Skills RAG and hybrid vector/graph search service. |
| `SKILLS_RAG_ENABLED` | `true` | Enables automatic bounded skill retrieval for real Codex turns. |
| `SKILLS_RAG_TOP_K` | `3` | Maximum skills read and attached to each turn. |
| `SKILLS_RAG_MAX_SKILL_CHARS` | `6000` | Per-skill character budget. |
| `SKILLS_RAG_MAX_CONTEXT_CHARS` | `16000` | Total retrieved context character budget per turn. |

The Codex worker also registers `skills-rag` as a native MCP server. Its bridge
imports only Python's standard library and forwards `find` and `skill` calls to
the daemon, so worker startup never loads PyTorch, sentence-transformers,
ChromaDB, or the graph index. The original `mcp-skillset` stdio server remains
disabled to prevent duplicate models, graph deserialization, and SQLite locks.

---

## 4. Core Workflows & Contracts

### 1. Dynamic Workspace Boundaries & Project Registration
1. **Dynamic Multi-Folder Boundaries**: Allowed root boundaries (`WorkspaceBoundary`) are persisted in SQLite and managed via REST endpoints:
   - `GET /codex/settings/boundaries`: List active allowed directory paths.
   - `POST /codex/settings/boundaries`: Add a new allowed base directory boundary with strict on-disk existence validation.
   - `DELETE /codex/settings/boundaries/{id_or_path}`: Safely remove a boundary (protected: cannot remove the sole remaining boundary).
2. **Project Registration Enforcement**:
   - When registering a project via `POST /codex/projects`, the backend resolves the path and confirms it resides within at least one active allowed boundary.
   - If outside all boundaries, an explicit HTTP 400 error is returned with the list of active boundaries and instructions for adding the folder.
   - In the frontend "Register Project" modal, active boundaries are displayed in real time. If a user enters a path outside existing boundaries, a highlighted warning appears with an instant 1-click button to "+ Add to Allowed Boundaries".
3. **Safe Worktree Isolation for Large Repos**:
   - For massive monorepos (e.g. `F:\Projects\fastapi_bookings`), worktrees are strictly confined to `<repo_root>/worktrees/wt-<threadId>`.
   - A `.gitignore` with `*\n!.gitignore\n` is automatically provisioned inside `worktrees/` to prevent runaway scans, git status thrashing, or repo resets.
   - Non-git fallback strictly copies top-level files only, omitting `node_modules`, `.venv`, `.git`, and cache directories.

### 2. Dynamic Telemetry Configuration & Live Connectivity Testing
1. **Telemetry Settings REST Endpoints**:
   - `GET /codex/settings/telemetry`: Returns current `signoz_url`, `otlp_endpoint`, enabled state, and live reachability probe result.
   - `PUT /codex/settings/telemetry`: Persists settings to `SystemSetting` and updates runtime config without restarts.
   - `POST /codex/settings/telemetry/test`: Probes endpoint reachability and returns truthful round-trip latency in milliseconds.
2. **Dynamic UI Integration**:
   - Settings Modal includes a dedicated "Telemetry & SigNoz" tab with live connection testing, latency feedback, and enable/disable toggling.
   - The Telemetry tab in the Inspector dynamically routes SigNoz trace links to the configured SigNoz URL.

### 3. Turn Lifecycle & Optimistic Reconciliation
1. **User Submits Instruction**: `Composer` sends the prompt with the validated sticky model and selected reasoning effort via `POST /codex/turns/start`. If a direct client omits the model, the backend resolves it to `gpt-6.1-sol`.
2. **Bounded Skills Retrieval**: A low-cardinality technical query is derived without forwarding the raw prompt, then port 8008 performs hybrid vector/graph search. At most three full skills are loaded on demand under per-skill and total context budgets. Retrieval failure is fail-open and does not fail the turn.
3. **Optimistic Store Entry**: The frontend generates an optimistic turn and renders a pending timeline node.
4. **Turn Started Event**: Backend assigns integer turn ID (`turn_id`) and emits `turn_started`. The frontend reconciles the optimistic turn ID with the API turn ID without creating duplicate turn cards.
5. **Streaming Deltas**: As Codex generates tokens, stdio `item/agentMessage/delta` and `turn/reasoningDelta` notifications are translated to `agent_message` and `reasoning` SSE events and streamed to the UI.
6. **Completion or Failure**: When Codex emits `turn/completed`, any upstream error is extracted and displayed as a structured `FailureItem` with retry options.

### 4. Operator Interruption & Cascade Cancellation
1. **Stop Request**: Operator clicks "Stop" button in UI $\to$ `POST /codex/turns/interrupt` with `thread_id` and `turn_id`.
2. **Resilient Resolution**: Backend matches the active turn or falls back to the latest in-progress turn, returning HTTP 200 `{"status": "interrupted"}` without spurious 404s.
3. **Worker Interrupt**: Supervisor dispatches JSON-RPC `turn/interrupt` to Codex App-Server.
4. **Cascade**: All pending tool approvals and child subagents for the thread are marked cancelled.
5. **Timeline Update**: Interruption event is emitted and appended with a guaranteed-unique composite React key.

### 5. Tool Approval Gating
1. **Tool Invocation**: Worker requests tool execution via `turn/toolApprovalRequested`.
2. **Risk Classification**:
   - `LOW`: Auto-approved (e.g. `git status`, `cat`).
   - `HIGH` / `CRITICAL`: Enqueued as pending `ToolApproval` record and rendered as interactive approval gate in UI.
3. **Operator Resolution**: Operator approves or declines $\to$ backend dispatches JSON-RPC response to worker.

### 6. Plugin and Interactive Authorization Flow
1. `GET /codex/plugins` calls app-server `plugin/list` and returns a sanitized catalog without marketplace filesystem paths.
2. `GET /codex/plugins/{plugin_id}` resolves the ID against that catalog before calling `plugin/read`; `POST /codex/plugins/{plugin_id}/install` applies the same resolution before `plugin/install`.
3. The install response exposes only allowlisted app metadata and HTTPS provider setup links from `appsNeedingAuth`.
4. App-server initiated `item/tool/requestUserInput`, `mcpServer/elicitation/request`, and `item/permissions/requestApproval` requests are registered against their originating worker and emitted as `user_input_request` SSE events.
5. `POST /codex/governance/interactions/{interaction_id}/resolve` sends the method-specific JSON-RPC result to that worker. Resolution events contain status only; answers and secret values are not rebroadcast.
6. V2 command/file approvals use `{decision: accept|acceptForSession|decline}` so the UI's once/session choice matches the installed app-server contract.

### 6. Responsive Viewport Architecture & WCAG 2.2 AA Reflow Compliance
1. **Desktop Viewport (> 1024px)**: Full 3-pane workbench displaying Project Rail + Thread Sidebar, Central Timeline/Composer column, and in-flow Inspector panel with flexible horizontal layout.
2. **Tablet Viewport (768px - 1023px)**: Two-pane layout with persistent navigation rail and sidebar. The Inspector operates as a slide-over overlay drawer with a backdrop (`bg-black/60 z-40 lg:hidden backdrop-blur-xs`), preserving conversational focus.
3. **Mobile Viewport (< 768px down to 320px WCAG Reflow)**:
   - **Full-Width Single Pane**: Main chat stream and timeline occupy 100% of the screen width (`w-screen max-w-full overflow-x-hidden`).
   - **Combined Off-Canvas Drawer**: Project Rail and Thread Sidebar translate off-canvas (`-translate-x-full md:translate-x-0`). Tapping the 44px hamburger icon slides the drawer into view with a tap-to-dismiss backdrop. Selecting any thread automatically closes the drawer on mobile.
   - **Adaptive Inspector Sheet**: Inspector slides out as a top-layer sheet (`max-w-[92vw] sm:max-w-md`) with 44px close triggers and scrollable tab strips.
   - **Responsive Composer Toolbar**: Bottom controls reflow dynamically into wrapped flex rows (`flex-col sm:flex-row`), ensuring Model, Reasoning, and Permission selectors do not clip or induce horizontal scrolling.
   - **WCAG 2.2 AA Touch Target Size (SC 2.5.8)**: All interactive buttons, dropdown triggers, and modal actions enforce minimum 44x44px hit areas (`min-h-[44px]`).

### 7. FastAPI Bookings Administrative Host Mount
In addition to running as a standalone service on port 4500, Codex Control Centre is natively mounted into the FastAPI Bookings main application under the administrative namespace:
- **Mounted Endpoints**:
  - `GET /api/admin/codex/settings/boundaries` — Workspace boundary configuration.
  - `GET /api/admin/codex/projects` — Registered projects list.
  - `GET /api/admin/codex/models` — Supported model catalog (`gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-sol`, `gpt-6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`) with supported reasoning variants. GPT-4-era entries are intentionally unavailable.
  - `GET /api/admin/codex/plugins` — Sanitized live plugin catalog.
  - `GET /api/admin/codex/plugins/{plugin_id}` — Plugin apps, skills, and capability details.
  - `POST /api/admin/codex/plugins/{plugin_id}/install` — Install the catalog-resolved plugin and return required app authorization links.
  - `GET /api/admin/codex/skills/stats` — Sanitized hybrid-index status and counts.
  - `GET /api/admin/codex/skills/search` — Hybrid semantic/graph search through port 8008.
  - `GET /api/admin/codex/skills/{skill_id}` — Full on-demand skill read without exposing source filesystem paths.
  - `GET /api/admin/codex/threads/{project_id}` — Active threads per project.
  - `POST /api/admin/codex/turns/start` — Start new agent turn.
  - `POST /api/admin/codex/turns/interrupt` — Steer or cancel active turn.
  - `GET /api/admin/codex/events/{project_id}/{thread_id}` — Real-time SSE stream.
- **Security Boundary**: Mounted endpoints require the native FastAPI Bookings platform-owner identity. The standalone `TOKEN_SECRET` (including `local_secret`) and query-string bearer tokens have no mounted authority. Event ticket minting and publication require a platform owner; stream connections accept only a short-lived, scoped SSE ticket that is atomically removed on first valid consumption. Every reconnect mints a fresh ticket. Unauthenticated callers and ordinary tenant administrators receive HTTP 401/403.
- **Acknowledged Support Dispatch**: Normal interactive turns remain asynchronously dispatched, while the support-ticket bridge invokes the same turn-start path in acknowledgement mode and reports `queued_for_codex` only after the worker answers `turn/start`.
- **Lifespan Integration**:
  - `app_lifespan` in `app/main.py` explicitly initialises `WorkerProcessManager` (via `WorkerManager`), sets SQLite `PRAGMA journal_mode=WAL`, seeds default workspace boundaries, and performs a startup sweep on orphaned active turns.
  - On application shutdown, active Codex worker processes and SSE subscribers are gracefully terminated.

---

## 5. Data Safety & Isolation

- **Dynamic Boundary Confinement**: Projects and worktrees cannot escape beyond user-approved workspace boundaries.
- **Worktree Sandboxing**: Every thread executes inside an isolated git worktree (`worktrees/wt-<threadId>`).
- **Path Traversal Protection**: All boundary paths, worktree paths, and subpaths are validated against directory traversal patterns (`../`, symlink escapes).
- **Destructive Deletion Guard**: Deleting a worktree requires explicit `?force=true` if uncommitted modifications exist. Root directories and active branches cannot be deleted.
- **Local Loopback Security**: Backend strictly binds to `127.0.0.1`. CORS is locked down to authorized local origins with credentials enabled.
- **Secret Scrubbing**: API tokens, private keys, and sensitive environment variables are masked in telemetry and logs.
- **Plugin Catalog Trust Boundary**: Install calls accept only a plugin ID already present in the app-server catalog. Browser clients cannot provide local marketplace paths, and API projections omit those paths.
- **Interactive Secret Isolation**: User answers are delivered only in the JSON-RPC response to the originating worker and never copied into resolution events or logs.
- **WCAG 2.2 AA Accessibility & Reflow Isolation**: Touch target sizing (min 44px) and zero horizontal overflow (`w-screen max-w-full overflow-x-hidden`) prevent responsive layout clipping down to 320px viewports.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Model Availability Drift**: The mounted catalog reflects the current models enabled for this Codex environment. Runtime account entitlements can still reject a model that is not enabled for the signed-in account; catalog updates must keep the backend endpoint and integrated frontend `modelCatalog.ts` in parity.
- **Skills RAG Process Dependency**: The heavyweight `mcp-skillset` worker integration remains disabled to prevent worker startup hangs. Automatic context and the native `skills-rag` MCP tools both delegate to the independently managed loopback service on port 8008. If unavailable, automatic retrieval degrades to the original prompt, while explicit `find` or `skill` calls return a recoverable tool error. Neither path places the raw user prompt in Skills RAG request logs.
- **Subprocess Loop Cleanup on Windows**: Asyncio proactor transport warning (`RuntimeError: Event loop is closed`) on process teardown in Python 3.11 Windows is benign but handled via explicit transport closure.
- **Preview Plugin Protocol**: App-server plugin list/read/install methods are currently documented by OpenAI as under development. The bridge fails closed with 502/503 responses on malformed or unavailable protocol results.

---

## 7. Verification & Testing Commands

### WP-UI-00 P0 trust-boundary verification

Run the inherited P0 boundary suites from the repository root and the Control Centre directory. WP-UI-00 changes no application behavior and does not implement v2.

```powershell
# From the repository root
.\.venv\Scripts\python.exe -m pytest tests/test_resident_agent.py tests/test_codex_backend_mount.py tests/test_admin_support_tickets.py -k "not stress_fuzzer" -v

# From codex-control-centre/
..\.venv\Scripts\python.exe -m pytest tests/test_security.py tests/test_events.py -v
```

### Backend Verification
```bash
# Run full backend test suite (147 tests)
$env:PYTHONPATH="."
python -m pytest tests/ -v

# Run Boundaries and Settings integration suite
python -m pytest tests/test_boundaries_and_settings.py -v

# Run Codex App-Server integration suite
python -m pytest tests/test_codex_app_server.py -v

# Run plugin installation and interactive authorization contract tests
python -m pytest tests/test_plugins_and_interactions.py -v

# Run Skills RAG search, bounds, fail-open, and turn-injection tests
python -m pytest tests/test_skills_context.py tests/test_skills_rag_mcp_bridge.py -v

# Run End-to-End smoke suite
python -m pytest tests/test_e2e_smoke.py -v

# Run FastAPI Bookings Admin Mount test suite
python -m pytest tests/test_codex_backend_mount.py -v
```

### Frontend Verification
```bash
cd frontend

# Run TypeScript compilation and Vite build
npm run build

# Run Vitest test suite including WCAG 2.2 AA accessibility and mobile reflow (33 tests across 2 suites)
npm test
```

### Living Documentation Compliance
```bash
python ../scripts/verify_living_docs.py --path README.md
```
