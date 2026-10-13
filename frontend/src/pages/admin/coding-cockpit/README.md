# Codex Engineering Cockpit (`frontend/src/pages/admin/coding-cockpit`)

The Codex Engineering Cockpit provides a unified, mobile-first, production-grade operational command centre for software reliability, AST diagnostics, automated stress testing, skill discovery, and native Codex agent workflow orchestration inside FastAPI Bookings.

---

## 1. Purpose & Scope

- **Primary Purpose**: Consolidates the previously split and fragmented "Resident Agent" (with its broken 750px iframe on port 5180, static prompt copy cards, and competitor radar) and "Conversational Coding Studio" into a single, cohesive, mobile-first agent workspace mounted at `/admin/coding-cockpit`.
- **What it Owns**:
  - **Unified Left Sidebar (`UnifiedSidebar.tsx`)**: Replaces the redundant two-column layout (`ProjectRail` + `ThreadSidebar`) with ONE unified left sidebar featuring project registration (`+ New Project`), search & filter bar, and an expandable nested tree (using Radix Collapsible) of conversations/threads under each project.
  - **Collapsible Desktop & Mobile Off-Canvas Panels**:
    - Left Sidebar: Toggleable via top-left hamburger menu (mobile slide-out off-canvas drawer with backdrop overlay) or desktop toggle button (`Ctrl+B`), collapsing smoothly to give 100% full width to the center workspace.
    - Right Inspector: Houses Diff Review, Active Files explorer, and Settings (Workspace Boundaries & OTel Telemetry), sliding smoothly on desktop and functioning as a slide-out off-canvas sheet on mobile.
  - **Integrated Bottom Console Dock (`BottomConsoleDock.tsx`)**: Positioned directly underneath the central conversation feed, tabbed via Radix Tabs between Terminal / Command Output, SRE Health Sentinels, Concurrency Stress Fuzzer, AST Issues Studio, Skills Library, and Event Stream. Features collapsible minimized (compact 38px status bar), expanded (340px), and maximized (full/580px) states.
  - **Active Agent HUD & Subagent Tab Bar (`ThreadHeader.tsx` & `SubagentTabBar.tsx`)**:
    - Live HUD: Top bar indicator displaying real-time agent status (`● Working on: ...` or `● Thinking...`), live ticking elapsed timer `(14s)`, and an inline stop/interrupt trigger.
    - Subagent Tab Switcher: Radix tab strip switching between `[ 👑 Main Agent ]` and child subagents `[ 🤖 Subagent: DB Worker ]` with status badges (Running spinner, Waiting Approval, Completed, Failed).
  - **Streamlined Timeline & Approvals**: Renders user instructions, live streaming responses, collapsible tool calls, reasoning process accordions, and one-click Approval cards (`once` / `session` scopes).
  - **One-Click Diff Review Studio (`DiffReviewStudioModal.tsx`)**: Native file diff inspection and verdict recording modal with **ZERO IFRAMES**.
  - **Mobile-First Responsiveness**: 100% screen width on mobile (< 768px down to 320px) for center chat, fixed/sticky composer with min 44px tap targets, zero horizontal scroll, and zero layout squishing.
- **What it Deliberately Avoids**:
  - No synthetic iframe embeds or mock port 5180 previews.
  - No competitor marketing radars or static prompt preset copy cards.
  - No redundant 2-column sidebar clutter.
  - No port 4500 hardcoding (uses same-origin `/api/admin/codex/...` reverse proxy).
  - Does not execute mutations directly against production without worktree sandbox isolation and operator diff approval.

---

## 2. Architecture & Key Files

The module is structured as a modular suite of embedded workspace components and consoles:

```
frontend/src/pages/admin/coding-cockpit/
├── index.tsx                                         # Barrel export for CodingCockpitPage
├── types.ts                                          # Shared contracts (issues, plans, metrics, fuzzer)
├── CodingCockpitPage.tsx                             # Full-viewport operational page shell with dock syncing
├── CodexWorkbenchTab.tsx                             # Native embedded Codex agent cockpit (zero iframes)
├── HealthSentinels.tsx                               # SRE health sentinels, OTel metrics, queue monitoring
├── StressFuzzer.tsx                                  # Concurrency race-condition load testing suite
├── IssuesStudio.tsx                                  # AST diagnostics & isolated sandbox fix executor
├── SkillsBrowser.tsx                                 # C:\Users\Frank\skills interactive catalog
├── EventStream.tsx                                   # Filtered SSE event stream console
├── coding-cockpit.test.ts                            # Unit test suite verifying routing, sidebar, dock, and HUD
├── README.md                                         # This living architecture documentation
└── workbench/
    ├── api/client.ts                                 # Same-origin /api/admin/codex API client with admin tokens
    ├── api/codexApi.ts                               # Typed API methods for threads, turns, diffs, approvals
    ├── store/useWorkbenchStore.ts                    # Reactive store (projects, threads, dock, panels, SSE)
    ├── types/workbench.ts                            # State contracts and event envelope interfaces
    └── components/
        ├── layout/UnifiedSidebar.tsx                 # Consolidated single left sidebar (nested project tree)
        ├── layout/ThreadHeader.tsx                   # Top bar Active Agent HUD & panel toggle triggers
        ├── layout/ProjectRail.tsx                    # Backwards-compatible thin shim to UnifiedSidebar
        ├── layout/ThreadSidebar.tsx                  # Backwards-compatible thin shim to UnifiedSidebar
        ├── dock/BottomConsoleDock.tsx                # Integrated bottom dock (Terminal, Health, Fuzzer, AST)
        ├── timeline/Timeline.tsx                     # Streaming conversation and activity timeline
        ├── timeline/SubagentTabBar.tsx               # Accessible subagent execution tab switcher
        ├── timeline/LiveActivityPulse.tsx            # Pulsing beacon and interrupt control
        ├── composer/Composer.tsx                     # Sticky multi-action composer with min 44px tap targets
        ├── inspector/Inspector.tsx                   # Right inspector panel (Diff Review, Files, Settings)
        ├── inspector/tabs/SettingsInspectorTab.tsx   # Workspace boundaries and OTel telemetry inspector
        ├── diff/DiffReviewStudioModal.tsx            # Fullscreen diff review studio overlay
        └── command-palette/CommandPalette.tsx        # Keyboard shortcut command palette
```

---

## 3. Setup, Configuration & Dependencies

- **Vite Reverse Proxy Rule**:
  - `frontend/vite.config.ts` includes a dedicated proxy mapping `/api/admin/codex` -> `http://127.0.0.1:4500`, stripping the `/api/admin` prefix to forward `/codex/...` endpoints directly to the Codex Control Centre daemon.
- **Admin Shell Integration**:
  - Mounted inside `AdminLayout.tsx` at `/admin/coding-cockpit`.
  - Registered as an operational route in `admin-layout.tsx` (`min-h-0 flex-1 flex flex-col p-0 overflow-hidden`), giving full height to the workspace without clipping or duplicate outer scrollbars.
- **Design System & Theme Tokens**:
  - Radix UI primitives (`@radix-ui/react-tabs`, `@radix-ui/react-collapsible`, `@radix-ui/react-dialog`, `@radix-ui/react-dropdown-menu`, `@radix-ui/react-tooltip`).
  - Tailwind CSS dark theme tokens (`bg-slate-900`, `border-slate-800`, `text-slate-100`, `bg-slate-950`).
  - Agents Kit design system patterns (thinking state pulses, decision approval cards, generative result surfaces).
- **Authentication**:
  - Uses the same-origin admin session bearer token retrieved via `getAdminAccessToken()` from `src/lib/api.ts`.
- **Runtime Services**:
  - FastAPI Bookings backend on `http://127.0.0.1:8000`.
  - Codex Control Centre backend daemon on `http://127.0.0.1:4500`.

---

## 4. Core Workflows & Contracts

1. **Unified Navigation & Routing**:
   - Accessing legacy `/admin/resident-agent` or `/admin/coding-studio` cleanly redirects to `/admin/coding-cockpit`.
   - Sidebar displays `Engineering Cockpit` under the `Compliance & System` category.
2. **Project & Thread Hierarchy**:
   - Operator clicks **"+ Project"** in `UnifiedSidebar.tsx` to register a local directory target.
   - Expanding the project shows its conversations. Clicking a thread selects it and sets the worktree context.
   - Clicking **"+"** on any project row creates a new conversation under that project.
3. **Live Streaming Turn Execution & Active Agent HUD**:
   - When a prompt is submitted, the Active Agent HUD in `ThreadHeader.tsx` activates with a pulsing emerald beacon, real-time status summary (`● Working on: Running pytest...`), and ticking elapsed timer.
   - If an agent turn needs to be halted or steered, the operator can click **"Stop"** or type guidance into `Composer.tsx` and click **"Steer Work"**.
4. **Child Subagent Supervision**:
   - When child subagents are spawned (e.g., `DB Worker`, `Sentinel Scanner`), they appear in `SubagentTabBar.tsx`.
   - Selecting a subagent tab filters the conversation timeline to that subagent's execution stream and tool calls.
5. **Integrated Bottom Console Dock**:
   - Operator toggles the bottom console dock via the header terminal button or minimized launcher bar.
   - Switching to `SRE Health` allows triggering deep audits and autonomous sentinel sweeps.
   - Switching to `Stress Fuzzer` runs concurrency race condition tests verifying 0 double-bookings.
   - Switching to `AST Issues` reviews detected code smells and dispatches sandboxed auto-fixes.
6. **Diff Review Studio**:
   - Changed files are indexed in `Inspector.tsx` (Changes tab).
   - Clicking **"Launch Full Diff Review Studio"** opens `DiffReviewStudioModal.tsx` for side-by-side hunk review and operator verdict approval.

---

## 5. Data Safety & Isolation

- **Tenant Scoping**: All operations inherit tenant authorization from the active administrative session.
- **Filesystem Boundaries**: Tool executions are strictly bounded by authorized workspace boundaries configured in `SettingsInspectorTab.tsx`.
- **Isolated Worktrees**: Autonomous turns execute in dedicated Git branches or sandboxed worktrees, preventing uncontrolled mutations.
- **Human-in-the-Loop Approval**: Critical system mutations, command executions, and diff merges require manual operator sign-off via explicit approval cards.

---

## 6. Known Issues, Edge Cases & Outstanding Work

- **Daemon Offline Handling**: When Codex Control Centre daemon (`port 4500`) is offline, the header connection status displays a reconnect banner with a retry trigger.
- **Mobile Keyboard Adjustment**: On small mobile viewports, opening the virtual keyboard shifts the sticky composer up; `env(safe-area-inset-bottom)` is enforced to avoid viewport cutoffs.
- **Local Skills Indexing**: Interactive search across 1,600+ skills at `C:\Users\Frank\skills` uses in-browser fuzzy indexing; server-side embedding search is scheduled for upcoming releases.

---

## 7. Verification & Testing Commands

To verify the Codex Engineering Cockpit module, run the following commands:

- **Targeted Unit Tests**:
  ```bash
  node --experimental-strip-types --test "src/pages/admin/coding-cockpit/coding-cockpit.test.ts"
  ```
- **Full Frontend Test Suite**:
  ```bash
  npm test --prefix frontend
  ```
- **TypeScript & Vite Production Build**:
  ```bash
  npm run build --prefix frontend
  ```
- **Living Documentation Compliance Verification (Rule 10)**:
  ```bash
  python scripts/verify_living_docs.py --path frontend/src/pages/admin/coding-cockpit/README.md
  ```
