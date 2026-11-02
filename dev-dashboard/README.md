# Dev Dashboard (Port 2310)

Comprehensive development control panel and infrastructure orchestration dashboard for the **FastAPI Bookings** ecosystem. Provides real-time process monitoring, live stdout/stderr log inspection, and granular container lifecycle management across all services and dependencies.

---

## 1. Purpose & Scope

### What It Owns
- **Module Lifecycle Management**: Starting, stopping, restarting, and monitoring local ecosystem services (FastAPI Backend, React Admin UI, SMS Assistant UI/API, Bookings AI Agent, Locanto Autoreply, Mapbox UI, etc.).
- **Process Supervision**: Tracking operating system PIDs, port release on shutdown via PowerShell/taskkill, and session log persistence.
- **Docker Container Fleet Management**: Real-time inspection of container state (running, exited, restarting), health probes, port mappings, and container lifecycle actions (`start`, `stop`, `restart`) using safe CLI execution (`execFile`).
- **Live Terminal Telemetry**: Streaming module and container stdout/stderr logs directly into dark-mode monospace consoles in the browser.
- **Anti-Gravity Workflows Bridge**: Reading SQLite project states, task dependency grids, and agent execution logs from the Anti-Gravity engine.

### What It Deliberately Avoids
- Does not modify or bypass database authentication or credentials.
- Does not execute arbitrary shell strings for container operations; all container names and actions are strictly regex-validated and executed via `execFile` without a shell interpreter.
- Does not own live business logic, reservation booking data, or financial transactions.

---

## 2. Architecture & Key Files

### Directory Layout
```
dev-dashboard/
├── logs/                   # Module session logs (stdout/stderr captures)
├── public/
│   └── index.html          # Single-page dashboard UI (Vanilla JS + WebSocket + CSS)
├── pids.json               # Persisted process ID state for tracked local processes
├── project-modules.json    # Declarative definition of local ecosystem services
├── server.js               # Node.js Express + WebSocket orchestration server
├── package.json            # Node.js dependencies (express, ws, axios, cors)
└── README.md               # Living module documentation
```

### Key Components & Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/status` | `GET` | Returns aggregated status of all local modules and Docker containers. |
| `/api/modules/:name/start` | `POST` | Spawns module process via PowerShell wrapper, saves PID to `pids.json`. |
| `/api/modules/:name/stop` | `POST` | Terminates module process tree via `taskkill /PID ... /T /F` and frees port. |
| `/api/modules/:name/restart` | `POST` | Stops and restarts a module. |
| `/api/modules/:name/logs` | `GET` | Returns tail of module session log file. |
| `/api/docker/containers` | `GET` | Queries Docker daemon via `docker ps -a --format {{json .}}` with 2.5s TTL cache. |
| `/api/docker/containers/:name/:action` | `POST` | Executes `start`, `stop`, or `restart` on container `:name` safely. |
| `/api/docker/containers/:name/logs` | `GET` | Tails container logs (`docker logs --tail <n> <name>`). |
| `/api/anti-gravity/state` | `GET` | Queries Anti-Gravity SQLite database for projects, tasks, and worker logs. |
| `ws://localhost:2310/` | `WS` | Real-time WebSocket connection broadcasting status updates every 3.5 seconds. |

---

## 3. Setup, Configuration & Dependencies

### Prerequisites
- Node.js 18+ (tested on Node 20 / 22)
- Docker Desktop or Docker Engine running locally
- PowerShell on Windows (used for background process spawning with hidden windows)

### Installation & Startup
```bash
# Navigate to dev dashboard directory
cd F:\Projects\fastapi_bookings\dev-dashboard

# Install dependencies
npm install

# Start the dashboard server on port 2310
node server.js
```
The dashboard will be available at: `http://localhost:2310`

---

## 4. Core Workflows & Contracts

### 1. Docker Fleet Monitoring & Control Workflow
1. **Container Query & Enrichment**:
   - The server queries `docker ps -a --format {{json .}}`.
   - Each container is dynamically categorized into its ecosystem group:
     - **FastAPI Bookings**: `fastapi-bookings-postgres`, `fastapi-bookings-redis`, `fastapi-bookings-neo4j`, `fastapi_bookings`
     - **ShortURLs**: `shorturls-db-1`
     - **Agent Memory**: `agent-memory-graphiti`, `agent-memory-neo4j`
     - **Chatwoot**: `chatwoot-rails-1`, `chatwoot-sidekiq-1`, `chatwoot-redis-1`, `chatwoot-postgres-1`, `chatwoot-base-1`
     - **SigNoz APM**: `signoz-signoz-0`, `signoz-ingester-1`, `signoz-telemetrystore-clickhouse-0-0`, `signoz-metastore-postgres-0`, `signoz-telemetrykeeper-clickhousekeeper-0`, etc.
     - **Other**: Any additional containers running on the Docker host.
   - Status strings (e.g. `Up 21 minutes (healthy)`) are parsed into machine-readable `state` (`running`, `exited`, `restarting`) and `health` (`healthy`, `unhealthy`, `starting`, `none`).
2. **Interactive UI Actions**:
   - The dedicated **🐳 Docker Containers** tab provides filter pills by stack group, search filtering by container name or port, and real-time stat cards (Total, Running, Stopped, Healthy).
   - Clicking **Start**, **Stop**, or **Restart** sends a request to `/api/docker/containers/:name/:action`.
   - The UI displays loading spinners and automatically invalidates the server cache to broadcast updated container states across all connected WebSocket clients.
3. **Live Container Logs**:
   - Expanding any container card or clicking **📄 Logs** loads live output from `docker logs --tail 150 <name>`.
   - Auto-scroll and customizable line counts (50, 150, 300, 500) are supported with real-time log polling.

---

## 5. Data Safety & Isolation

- **Command Injection Protection**: Container names are strictly validated against `/^[a-zA-Z0-9_.-]+$/`. Commands are passed as structured arguments directly to `execFile('docker', [action, name])`, preventing any shell interpolation or injection vectors.
- **Action Whitelisting**: Only explicitly approved lifecycle verbs (`start`, `stop`, `restart`) can be invoked on containers.
- **Fail-Safe Caching**: Docker queries use a 2.5-second TTL cache to prevent Docker daemon CPU starvation from concurrent client requests or polling loops. If Docker is unreachable, cached data or a graceful empty list is returned without throwing 500 crashes.
- **Process Isolation**: Module stop actions target process trees (`taskkill /T /F`) and actively scan/clear lingering listener sockets on assigned ports (`netstat -ano` matching).

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Docker Desktop Cold Start**: If Docker Desktop is stopped or starting, Docker queries will time out gracefully (6s timeout) and report an empty list until the engine is fully initialized.
- **Long-Running Compose Projects**: When starting a complete stack like `docker-stack` via Compose from Tab 1, it may take 5–10 seconds for all child containers to report `healthy`. Tab 2 ("Docker Containers") can be used to observe each container's granular health progression.
- **Future Enhancement**: Add container memory/CPU metric graphs via `docker stats --no-stream` into the expandable details card.

---

## 7. Verification & Testing Commands

### Syntax Verification
```bash
node --check F:\Projects\fastapi_bookings\dev-dashboard\server.js
```

### Docker API Endpoints Smoke Tests
```bash
# Query container fleet
curl.exe -s http://localhost:2310/api/docker/containers

# Tail container logs
curl.exe -s "http://localhost:2310/api/docker/containers/fastapi-bookings-postgres/logs?lines=5"

# Verify security validation on invalid container name
curl.exe -s -X POST "http://localhost:2310/api/docker/containers/bad;name/start"
# Expected response: {"ok":false,"error":"Invalid container name format"}

# Verify full status payload includes docker fleet
curl.exe -s http://localhost:2310/api/status
```
