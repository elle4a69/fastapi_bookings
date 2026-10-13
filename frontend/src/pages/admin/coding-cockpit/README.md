# Codex Engineering Cockpit (`frontend/src/pages/admin/coding-cockpit`)

The Codex Engineering Cockpit provides a unified, production-grade operational command centre for software reliability, AST diagnostics, automated stress testing, skill discovery, and native Codex agent workflow orchestration inside FastAPI Bookings.

---

## 1. Purpose & Scope

- **Primary Purpose**: Consolidates the previously split and fragmented "Resident Agent" (with its broken 750px iframe on port 5180, static prompt copy cards, and competitor radar) and "Conversational Coding Studio" into a single, cohesive, high-performance workspace mounted at `/admin/coding-cockpit`.
- **What it Owns**:
  - Unified navigation routing: Single 'Engineering Cockpit' item in `Compliance & System` menu, with automated redirects for legacy `/admin/resident-agent` and `/admin/coding-studio` paths.
  - SRE & Health Sentinels: OpenTelemetry error budget gauges, SMS ingestion/delivery queues, Chatwoot webhook latency, and deep diagnostic audit triggers.
  - Concurrency & Race-Condition Stress Fuzzer: Configurable synthetic load generator (10x-50x concurrency) evaluating atomic locking integrity across appointment bookings and SMS intake.
  - AST Static Analysis & Issues Studio: Real-time scan of runtime issues with direct dispatch to isolated Codex worktree sandboxes (`createThread` + `startTurn`).
  - Native Codex Control Centre Workbench: Fully embedded native timeline, subagent tab bar, live activity pulse, thread switcher, composer, inspector, and diff review studio with **ZERO IFRAMES**.
  - Local Skills Browser: Interactive catalog and viewer for the 1,600+ skills located at `C:\Users\Frank\skills`.
  - Filtered Live Event Stream: SSE terminal viewer for real-time observability.
- **What it Deliberately Avoids**:
  - No synthetic iframe embeds or mock port 5180 previews.
  - No competitor marketing radars or static prompt preset cards.
  - No customer-facing or unauthenticated actions.
  - Does not execute arbitrary mutations directly against production without worktree sandbox isolation and manual diff approval.

---

## 2. Architecture & Key Files

The module is structured as a modular suite of tabbed views and embedded workbench components:

```
frontend/src/pages/admin/coding-cockpit/
├── index.tsx                         # Barrel export for CodingCockpitPage
├── types.ts                          # Shared data contracts (issues, plans, metrics, fuzzer)
├── CodingCockpitPage.tsx             # Main page shell with tab routing, breadcrumbs, sync state
├── HealthSentinels.tsx               # SRE health gauges, OTel metrics, queue monitoring
├── StressFuzzer.tsx                  # Concurrency load testing suite
├── IssuesStudio.tsx                  # AST diagnostics & isolated sandbox fix executor
├── SkillsBrowser.tsx                 # C:\Users\Frank\skills interactive catalog
├── EventStream.tsx                   # Filtered SSE event stream console
├── CodexWorkbenchTab.tsx             # Native embedded Codex Control Centre (zero iframes)
├── coding-cockpit.test.ts            # Automated unit tests for routing, contracts & zero iframes
├── README.md                         # This living architecture documentation
└── workbench/                        # Embedded Codex Control Centre implementation
    ├── api/client.ts                 # Same-origin /api/admin/codex client with admin auth
    ├── store/useCodexStore.ts        # Zustand reactive state store
    ├── types/codex.ts                # Thread, turn, diff, and event types
    └── components/                   # Embedded timeline, composer, diff reviewer, inspector
```

---

## 3. Setup, Configuration & Dependencies

- **Vite Reverse Proxy Rule**:
  - `frontend/vite.config.ts` includes a dedicated proxy mapping `/api/admin/codex` -> `http://127.0.0.1:4500`, stripping the `/api/admin` prefix to forward `/codex/...` endpoints directly to the Codex Control Centre daemon.
- **Authentication**:
  - Uses the same-origin admin session bearer token retrieved via `getAdminAccessToken()` from `src/lib/api.ts`.
- **Runtime Services**:
  - FastAPI Bookings backend on `http://127.0.0.1:8000`.
  - Codex Control Centre backend daemon on `http://127.0.0.1:4500`.
- **External Skills Directory**:
  - Reads curated skills from `C:\Users\Frank\skills` for local execution and inspection.

---

## 4. Core Workflows & Contracts

1. **Navigation & Legacy Routing**:
   - Accessing `/admin/resident-agent` or `/admin/coding-studio` cleanly redirects to `/admin/coding-cockpit`.
   - Sidebar displays `Engineering Cockpit` under the `Compliance & System` category.
2. **Issue Detection & Sandboxed Fix Execution**:
   - Operator reviews detected AST issues or runtime regressions in `IssuesStudio.tsx`.
   - Clicking **"Execute Fix in Sandbox"** dispatches an API call to `codexApi.createThread({ project_id, branch_name, title })` followed by `codexApi.startTurn(threadId, { prompt, isolated_worktree: true })`.
   - The user is switched to the **Codex Workbench** tab to observe turn execution and diff proposals.
3. **Native Workbench Execution (Zero Iframes)**:
   - Timeline streams SSE events (`thread.turn.progress`, `tool.call`, `diff.generated`).
   - Operator inspects proposed changes in `DiffReviewStudioModal` before approving merge.
4. **Stress Testing**:
   - Operator selects target subsystem (e.g. `Appointment Booking Flow` or `SMS Intake Pipeline`) and concurrency factor (10x - 50x).
   - System measures latency percentiles (p50, p95, p99), error rates, and atomic lock hold duration.

---

## 5. Data Safety & Isolation

- **Tenant Scoping**: All operations inherit tenant context from the active administrative session.
- **Isolated Worktrees**: Automated coding turns are executed inside dedicated Git worktrees or branches, preventing untracked alterations to working copies.
- **Manual Diff Review**: No automated changes are merged without human-in-the-loop review through the diff inspection modal.
- **Zero Mock Policy**: All diagnostic metrics, queue depths, and load fuzzer operations interact with real endpoints and structural models.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Daemon Offline Handling**: When Codex Control Centre daemon (`port 4500`) is offline, the workbench displays an inline reconnect banner with retry capabilities.
- **Skills Search Performance**: In-browser filtering of 1,600+ skills is performed via indexed fuzzy text matching; server-side semantic search indexing is planned for future iterations.
- **Multi-Tenant Worktree Cleanup**: Stale Git worktrees from abandoned turns are cleaned during periodic worker daemon GC sweeps.

---

## 7. Verification & Testing Commands

To verify the Codex Engineering Cockpit module, run the following commands:

- **Targeted Unit Tests**:
  ```bash
  node --experimental-strip-types --test "src/pages/admin/coding-cockpit/coding-cockpit.test.ts"
  ```
- **Full Frontend Test Suite**:
  ```bash
  npm test
  ```
- **TypeScript & Vite Build**:
  ```bash
  npm run build
  ```
- **Living Documentation Compliance Verification (Rule 10)**:
  ```bash
  python scripts/verify_living_docs.py --path frontend/src/pages/admin/coding-cockpit/README.md
  ```
