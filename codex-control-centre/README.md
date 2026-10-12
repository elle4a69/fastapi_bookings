# Codex Control Centre

Codex Control Centre is the main coordination, telemetry, and governance hub for multi-agent workflows. It provides real-time event streaming, thread management, tool approval gating, subagent supervision, and isolated git worktrees.

---

## 1. Purpose & Scope

Codex Control Centre provides an enterprise-grade supervisory control plane and developer workbench for OpenAI Codex App-Server (`codex app-server`).
- **Core Ownership**:
  - Direct stdio JSON-RPC 2.0 communication with `codex app-server` worker subprocesses.
  - Multi-tenant thread and turn lifecycle management with resilient start, steer, and interrupt operations.
  - Real-time Server-Sent Events (SSE) streaming with event buffering, single-use ticket dispatch, and optimistic turn reconciliation.
  - Human-in-the-loop tool execution approval gates with risk-tier evaluation (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
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
    - `governance.py`: Approvals, risk tiering, subagent registration, concurrency enforcement.
    - `worktrees.py`: Git worktree creation, validation, dirty-check deletion.
    - `diagnostics.py`: Readiness, liveness, SigNoz connectivity probes.
  - `services/`:
    - `worker.py`: Subprocess management, stdio JSON-RPC protocol dispatch, event routing.
    - `worker_manager.py`: Thread-to-worker process pool, graceful restart and teardown.
    - `protocol.py`: JSON-RPC message normalization (`agent_message`, `reasoning`, `turn_completed`, `turn_failed`).
    - `event_service.py`: In-memory thread-scoped SSE event broker with historical replay.
    - `sse_tickets.py`: Short-lived single-use authorization ticket store.
    - `telemetry.py`: SigNoz / OpenTelemetry instrumentation and fallback logger.
- `frontend/`:
  - `src/components/composer/Composer.tsx`: Prompt input, model selector (`gpt-5.6-sol`, `o3-mini`), reasoning controls.
  - `src/components/timeline/Timeline.tsx`: Virtualized event timeline with unique React keys.
  - `src/store/useWorkbenchStore.ts`: Global state, SSE reducer, optimistic turn adoption, turn interruption.
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
| `TOKEN_SECRET` | `local_secret` | Bearer token secret for authentication. |
| `SIGNOZ_URL` | `http://localhost:3301` | SigNoz telemetry collector URL (can also be dynamically managed in UI). |
| `OTLP_ENDPOINT` | `http://localhost:4318` | OpenTelemetry OTLP endpoint (can also be dynamically managed in UI). |
| `ALLOWED_BOUNDARIES` | `["<codex_dir>"]` | Comma-separated or JSON list of initial allowed workspace base boundaries. |
| `WORKTREES_DIR` | `<root>/worktrees` | Directory path for isolated git worktrees. |
| `CODEX_BIN_PATH` | `codex` | Path to Codex App-Server executable (automatically resolves to native `codex.exe`). |
| `CODEX_APP_SERVER_ARGS` | `["app-server"]` | Command line arguments passed when launching the Codex App-Server subprocess. |
| `CODEX_TRANSPORT` | `stdio` | Transport protocol used for communication with the worker process (`stdio`). |
| `CODEX_WORKER_TIMEOUT_SECONDS` | `60` | Default timeout in seconds for JSON-RPC requests sent to the worker process. |

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
1. **User Submits Instruction**: `Composer` sends user prompt with selected model (`gpt-5.6-sol`) and reasoning effort via `POST /codex/turns/start`.
2. **Optimistic Store Entry**: The frontend generates an optimistic turn and renders a pending timeline node.
3. **Turn Started Event**: Backend assigns integer turn ID (`turn_id`) and emits `turn_started`. The frontend reconciles the optimistic turn ID with the API turn ID without creating duplicate turn cards.
4. **Streaming Deltas**: As Codex generates tokens, stdio `item/agentMessage/delta` and `turn/reasoningDelta` notifications are translated to `agent_message` and `reasoning` SSE events and streamed to the UI.
5. **Completion or Failure**: When Codex emits `turn/completed`, any upstream error is extracted and displayed as a structured `FailureItem` with retry options.

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

---

## 5. Data Safety & Isolation

- **Dynamic Boundary Confinement**: Projects and worktrees cannot escape beyond user-approved workspace boundaries.
- **Worktree Sandboxing**: Every thread executes inside an isolated git worktree (`worktrees/wt-<threadId>`).
- **Path Traversal Protection**: All boundary paths, worktree paths, and subpaths are validated against directory traversal patterns (`../`, symlink escapes).
- **Destructive Deletion Guard**: Deleting a worktree requires explicit `?force=true` if uncommitted modifications exist. Root directories and active branches cannot be deleted.
- **Local Loopback Security**: Backend strictly binds to `127.0.0.1`. CORS is locked down to authorized local origins with credentials enabled.
- **Secret Scrubbing**: API tokens, private keys, and sensitive environment variables are masked in telemetry and logs.
- **Mobile-First Responsive Layout**: All modals and toolbars support touch screens down to 320px viewport reflow with minimum 44px tap targets.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **ChatGPT Account Model Compatibility**: When Codex CLI is authenticated via a ChatGPT subscription account (rather than direct OpenAI API platform key), legacy models like `gpt-4o` and `gpt-6.1-sol` are rejected by the upstream CLI. Default model is locked to `gpt-5.6-sol`.
- **Hanging External MCP Servers**: External MCP plugins configured in `~/.codex/config.toml` that fail to respond (e.g. `mcp-skillset`, `main-context-document`) can delay initial worker startup. Backend passes flags to disable failing MCPs during worker launch.
- **Subprocess Loop Cleanup on Windows**: Asyncio proactor transport warning (`RuntimeError: Event loop is closed`) on process teardown in Python 3.11 Windows is benign but handled via explicit transport closure.

---

## 7. Verification & Testing Commands

### Backend Verification
```bash
# Run full backend test suite (146 tests)
$env:PYTHONPATH="."
python -m pytest tests/ -v

# Run Boundaries and Settings integration suite
python -m pytest tests/test_boundaries_and_settings.py -v

# Run Codex App-Server integration suite
python -m pytest tests/test_codex_app_server.py -v

# Run End-to-End smoke suite
python -m pytest tests/test_e2e_smoke.py -v
```

### Frontend Verification
```bash
cd frontend

# Run TypeScript compilation and Vite build
npm run build

# Run Vitest test suite (27 tests)
npm test
```

### Living Documentation Compliance
```bash
python ../scripts/verify_living_docs.py --path README.md
```
