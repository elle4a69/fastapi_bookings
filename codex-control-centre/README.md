# Codex Control Centre

Codex Control Centre is the main coordination, telemetry, and governance hub for multi-agent workflows. It provides real-time event streaming, thread management, tool approval gating, subagent supervision, and isolated git worktrees.

---

## Table of Contents
- [Architecture & Overview](#architecture--overview)
- [Codex App-Server Integration Architecture](#codex-app-server-integration-architecture)
  - [JSON-RPC 2.0 Protocol & Handshake](#json-rpc-20-protocol--handshake)
  - [Worktree Sandboxing & Isolation](#worktree-sandboxing--isolation)
  - [Real-Time SSE Event Streaming](#real-time-sse-event-streaming)
  - [Interactive Approval Gates & Cascade Cancellation](#interactive-approval-gates--cascade-cancellation)
- [Prerequisites & Setup](#prerequisites--setup)
- [API Route Reference](#api-route-reference)
  - [Liveness & Diagnostics](#liveness--diagnostics)
  - [Events & SSE Streaming](#events--sse-streaming)
  - [Threads & Turns](#threads--turns)
  - [Governance & Approvals](#governance--approvals)
  - [Worktrees Management](#worktrees-management)
- [Security Features](#security-features)
  - [Loopback Binding & CORS Protection](#loopback-binding--cors-protection)
  - [Bearer Token Authentication](#bearer-token-authentication)
  - [Tool Risk Tiering & Evaluation](#tool-risk-tiering--evaluation)
  - [Sub-Agent Concurrency Limits & Cascade Cancellation](#sub-agent-concurrency-limits--cascade-cancellation)
  - [Safe Worktree Deletion & Traversal Prevention](#safe-worktree-deletion--traversal-prevention)
- [Development & Verification Commands](#development--verification-commands)
  - [Master Quality Gates Verification](#master-quality-gates-verification)
- [Database & Migrations](#database--migrations)
- [Configuration Reference](#configuration-reference)

---

## Architecture & Overview

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

---

## Codex App-Server Integration Architecture

Codex Control Centre interfaces directly with the native OpenAI Codex App-Server (`codex app-server`) over bidirectional JSON-RPC 2.0 via standard input/output (`stdio`).

### JSON-RPC 2.0 Protocol & Handshake
1. **Discovery & Initialization**: Upon process launch, the supervisor performs a strict lifecycle handshake:
   - Supervisor sends `initialize` request with client identification and capabilities (`{"clientInfo": {"name": "CodexControlCentre", "version": "1.0.0"}, "capabilities": {"streaming": true, "approvals": true}}`).
   - Codex App-Server returns server metadata, user agent, and supported feature capabilities.
   - Supervisor acknowledges with an `initialized` notification to unblock the worker for turn execution.
2. **Binary Resolution**: On Windows systems, `resolve_codex_binary` resolves PATH entries, transparently bypassing `.cmd`/`.bat` shell wrappers and locating the native compiled binary (`codex.exe`) within Node/NVM paths.

### Worktree Sandboxing & Isolation
- Each conversation thread runs in a sandboxed git worktree directory (`worktrees/wt-<threadId>`).
- When a turn is initiated (`POST /codex/turns/start`), the backend:
  1. Creates or verifies the isolated git worktree via `ensure_thread_worktree`.
  2. Sets the worker process working directory (`cwd`) strictly to the worktree path.
  3. Dispatches `turn/start` with both `workspaceRoot` and `cwd` pointing exclusively to `worktrees/wt-<threadId>`.

### Real-Time SSE Event Streaming
Codex App-Server notifications are translated in real-time by `Protocol.normalize_notification` into standardized `EventEnvelope` structures and published to the thread-scoped `EventBroker`:
- `turn/reasoningDelta` $\to$ `reasoning` (streaming chain-of-thought tokens)
- `turn/messageDelta` $\to$ `agent_message` (assistant response text)
- `turn/commandExecution` $\to$ `command` (command execution status, exit code, stdout/stderr)
- `turn/fileModified` $\to$ `file_change` (diffs, additions, deletions, modified paths)
- `turn/completed` $\to$ `turn_completed` (turn completion summary and timestamp)

Frontend clients consume these events through the Server-Sent Events (SSE) endpoint (`GET /codex/events/{project_id}/{thread_id}`), which supports automatic backlog replay via the `Last-Event-ID` header.

### Interactive Approval Gates & Cascade Cancellation
- When Codex App-Server requests tool execution (`turn/toolApprovalRequested`):
  - **LOW Risk**: Read-only tools/commands (`git status`, `cat`) are auto-approved immediately.
  - **HIGH / CRITICAL Risk**: Potentially destructive commands (`git reset --hard`, `npm install`, shell scripts) pause execution and persist a pending `ToolApproval` record in SQLite.
  - Operators review and approve or decline via `POST /codex/approvals/respond`, which dispatches the JSON-RPC response `{"jsonrpc": "2.0", "id": "<req_id>", "result": {"approved": true/false}}` to unblock worker execution.
- **Cascade Cancellation**: Invoking `POST /codex/turns/interrupt` issues `turn/interrupt` to the worker and automatically cascades cancellation to all pending tool approvals and active subagents for that thread.

---

## Prerequisites & Setup

- **Python**: 3.11+
- **Node.js**: 20+
- **Git**: 2.30+

### 1. Install Backend Dependencies
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Install Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

### 3. Initialize Database
```bash
alembic upgrade head
```

---

## API Route Reference

All `/codex/*` endpoints require Bearer Token Authentication (`Authorization: Bearer <TOKEN>`) unless stated otherwise.

### Liveness & Diagnostics
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | Public | Public liveness probe returning `status: "healthy"` and UTC timestamp. |
| `GET` | `/` | Public | Root welcoming banner endpoint. |
| `GET` | `/codex/diagnostics/readiness` | Bearer | Readiness probe checking database, event broker, worker, worktree storage, and telemetry. |
| `GET` | `/codex/diagnostics/deep` | Bearer | Deep multi-subsystem diagnostic audit probe. |
| `GET` | `/codex/diagnostics/telemetry` | Bearer | Truthful probe verifying SigNoz / OTLP telemetry collector connectivity. |

### Events & SSE Streaming
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/codex/events/{project_id}/{thread_id}` | Bearer | Server-Sent Events (SSE) stream supporting reconnection and backlog replay with `Last-Event-ID` header. |
| `POST` | `/codex/events/publish` | Bearer | Publishes a typed `EventEnvelope` to the thread-scoped in-memory event broker. |

### Threads & Turns
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/codex/threads` | Bearer | Creates a new conversation thread under a project. |
| `GET` | `/codex/threads` | Bearer | Lists all threads across projects. |
| `GET` | `/codex/threads/{thread_id}` | Bearer | Retrieves detailed thread metadata by ID. |
| `PATCH` | `/codex/threads/{thread_id}` | Bearer | Updates thread metadata (`title`, `is_pinned`, `is_archived`, `status`). |
| `DELETE` | `/codex/threads/{thread_id}` | Bearer | Cascades deletion to turns, approvals, and subagents for the specified thread. |
| `POST` | `/codex/turns/start` | Bearer | Initializes a new active turn and notifies the worker process. |
| `POST` | `/codex/turns/steer` | Bearer | Sends dynamic steering instructions to an active turn. |
| `POST` | `/codex/turns/interrupt` | Bearer | Interrupts a running turn execution. |
| `POST` | `/codex/approvals/respond` | Bearer | Dispatches user approval decision (`approved: true/false`) to the worker. |

### Governance & Approvals
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/codex/governance/evaluate` | Bearer | Evaluates command or tool risk tier against governance profiles (`managed`, `strict`, `permissive`). |
| `GET` | `/codex/governance/approvals/pending` | Bearer | Lists pending approval requests, optionally filtered by `?thread_id=`. |
| `POST` | `/codex/governance/approvals` | Bearer | Creates a new tool approval gate (`HIGH` or `CRITICAL` risk). |
| `POST` | `/codex/governance/approvals/{approval_id}/resolve` | Bearer | Resolves an approval gate (`approved: true/false`) and emits `approval.resolved` event. |
| `GET` | `/codex/governance/subagents/{thread_id}` | Bearer | Lists all subagents active or registered under a thread. |
| `POST` | `/codex/governance/subagents/register` | Bearer | Registers a subagent with active concurrency enforcement (max 6). |
| `POST` | `/codex/governance/subagents/{subagent_id}/progress` | Bearer | Updates subagent progress percentage and telemetry action. |
| `POST` | `/codex/governance/subagents/{subagent_id}/steer` | Bearer | Sends steering instruction to an active subagent. |
| `POST` | `/codex/governance/subagents/{subagent_id}/stop` | Bearer | Stops a specific subagent. |
| `POST` | `/codex/governance/threads/{thread_id}/terminate-subagents` | Bearer | Cascades cancellation to all active child subagents when parent thread terminates. |

### Worktrees Management
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/codex/worktrees/create` | Bearer | Creates an isolated git worktree branch under the designated workspace directory. |
| `GET` | `/codex/worktrees?repo_path=` | Bearer | Lists all active git worktrees registered for a repository. |
| `DELETE` | `/codex/worktrees/{worktree_name}` | Bearer | Deletes a worktree. Requires `?force=true` if worktree contains uncommitted/dirty changes. |

---

## Security Features

### Loopback Binding & CORS Protection
- Backend binds strictly to `127.0.0.1` by default.
- Strict CORS middleware allowlists only authorized local frontend origins (`http://127.0.0.1:5180`, `http://localhost:5180`, `http://127.0.0.1:5173`, `http://localhost:5173`). Wildcard `*` origins are prohibited.

### Bearer Token Authentication
- All mutating and internal routes enforce token authentication via the `verify_auth` FastAPI dependency.
- Token secret is securely loaded via environment variables (`TOKEN_SECRET`) with `local_secret` as default for local development.

### Tool Risk Tiering & Evaluation
The governance subsystem categorizes commands into four deterministic risk tiers:
- **`LOW`**: Read-only operations (`git status`, `cat`, `grep`, `ls`). Auto-approved in managed profile.
- **`MEDIUM`**: Workspace file mutations (`git add`, `touch`, `mkdir`). Auto-approved in managed profile; requires approval in strict profile.
- **`HIGH`**: Destructive commands (`rm -rf`, `git reset --hard`, `npm install`, `pip install`, shell execution). Strictly requires human approval.
- **`CRITICAL`**: Repository history changes or secret access (`git push`, `git branch -D`, `cat .env`, outbound POST requests). Strictly requires human approval.

### Sub-Agent Concurrency Limits & Cascade Cancellation
- Enforces a maximum concurrency ceiling of **6 active subagents** per thread to prevent resource exhaustion.
- Thread cancellation automatically cascades cancellation to all active child subagents (`status: 'cancelled'`) and notifies subscribers via SSE.

### Safe Worktree Deletion & Traversal Prevention
- Worktree paths are validated against directory traversal patterns (`../`, path separators).
- Primary repository roots and arbitrary filesystem directories are protected from deletion.
- Uncommitted modifications in worktrees prevent accidental deletion unless explicitly confirmed with `force=True`.

---

## Development & Verification Commands

### Master Quality Gates Verification
Execute all 9 backend and frontend quality gates via the unified PowerShell runner:
```powershell
powershell -ExecutionPolicy Bypass -File .\test_all.ps1
```

### Run Full Backend Test Suite
```bash
python -m pytest tests/ -v
```

### Run Codex App-Server End-to-End Integration Suite
```bash
python -m pytest tests/test_codex_app_server.py -v
```

### Run End-to-End Smoke Test Suite
```bash
python -m pytest tests/test_e2e_smoke.py -v
```

### Run Python Linting & Typechecking
```bash
python -m ruff check backend tests
python -m mypy backend
```

### Build Frontend
```bash
cd frontend
npm run build
```

### Start Development Backend
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8100 --reload
```

### Start Frontend Dev Server
```bash
cd frontend
npm run dev
```

---

## Database & Migrations

Codex Control Centre uses SQLite with Alembic for migrations and foreign key constraints enabled via SQLite pragmas.

```bash
# Run latest database migrations
alembic upgrade head

# Create a new migration revision
alembic revision -m "add_new_feature_table"
```

---

## Configuration Reference

Set these variables in `.env` or system environment:

| Variable | Default Value | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./codex.db` | SQLAlchemy database connection string. |
| `HOST` | `127.0.0.1` | Host address to bind the API server. |
| `PORT` | `8100` | Port for the API server. |
| `TOKEN_SECRET` | `local_secret` | Bearer token secret for authentication. |
| `SIGNOZ_URL` | `http://localhost:3301` | SigNoz telemetry collector URL. |
| `OTLP_ENDPOINT` | `http://localhost:4318` | OpenTelemetry OTLP endpoint. |
| `WORKTREES_DIR` | `<root>/worktrees` | Directory path for isolated git worktrees. |
| `CODEX_BIN_PATH` | `codex` | Path to Codex App-Server executable (automatically resolves to native `codex.exe`). |
| `CODEX_APP_SERVER_ARGS` | `["app-server"]` | Command line arguments passed when launching the Codex App-Server subprocess. |
| `CODEX_TRANSPORT` | `stdio` | Transport protocol used for communication with the worker process (`stdio`). |
| `CODEX_WORKER_TIMEOUT_SECONDS` | `60` | Default timeout in seconds for JSON-RPC requests sent to the worker process. |
| `CODEX_API_KEY` | `None` | Optional API key injected into the worker subprocess environment (`CODEX_API_KEY`). |
