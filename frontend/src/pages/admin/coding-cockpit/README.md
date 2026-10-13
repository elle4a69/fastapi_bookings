# Codex Engineering Cockpit (`frontend/src/pages/admin/coding-cockpit`)

The Codex Engineering Cockpit provides a unified, mobile-first, production-grade operational command centre for software reliability, AST diagnostics, automated stress testing, skill discovery, and native Codex agent workflow orchestration inside FastAPI Bookings.

---

## 1. Purpose & Scope

- **Primary Purpose**: Consolidates the previously split and fragmented "Resident Agent" (with its broken 750px iframe on port 5180, static prompt copy cards, and competitor radar) and "Conversational Coding Studio" into a single, cohesive, mobile-first agent workspace mounted at `/admin/coding-cockpit`.
- **What it Owns**:
  - **Pixel-Perfect Aligned Slim Headers (Equal Height Across All 3 Columns)**:
    - Standardized slim height of `h-11` (44px) with `border-b border-slate-800` across `UnifiedSidebar.tsx` top header, `ThreadHeader.tsx` header, and `Inspector.tsx` header.
    - Ensures the horizontal divider line runs straight, uninterrupted, and unbroken across the entire screen from left to right.
  - **Draggable Resizable Side Panels**:
    - Vertical resizer splitter handles between Left Sidebar and Center Stage (resizes `sidebarWidth`, clamped between 220px and 480px, `cursor-col-resize`) and between Center Stage and Right Inspector (resizes `inspectorWidth`, clamped between 260px and 600px, `cursor-col-resize`).
    - Smooth visual feedback while dragging and persistent width storage in `localStorage` (`codex_sidebar_width`, `codex_inspector_width`) and `useWorkbenchStore`.
  - **Interactive Model Selector with Sticky Last-Used Default**:
    - Dropdown in `ThreadHeader.tsx` listing available models: `gpt-5.6-sol`, `gpt-4o`, `gpt-4o-mini`, `o3-mini`, `o1`, `claude-3-5-sonnet`.
    - Automatically syncs and persists selected model in `localStorage` (`codex_last_used_model`), with initialization in `useWorkbenchStore` defaulting new threads and composer to the sticky last-used model.
  - **Full-Screen Modal Overlays for Secondary Tools (`SecondaryToolsModals.tsx`)**:
    - Clean launcher dropdown in `ThreadHeader.tsx` for secondary engineering tools:
      - SRE Health Sentinels (`HealthSentinels.tsx`)
      - Concurrency Stress Fuzzer (`StressFuzzer.tsx`)
      - AST Issues Studio (`IssuesStudio.tsx`)
      - Engineering Skills Library (`SkillsBrowser.tsx`)
      - Real-time Event Stream (`EventStream.tsx`)
    - Opens tools as spacious full-screen modal overlays over the top using Radix Dialog/DialogContent (`w-full max-w-[96vw] md:max-w-7xl h-[94vh]`), dark slate styling, ESC to close, and an 'X' close button.
  - **Streamlined Bottom Console Dock (`BottomConsoleDock.tsx`)**:
    - Streamlined strictly to the Terminal / Live Output runner, preventing tab overflow or clipping. Features collapsible minimized (compact 38px status bar), expanded (340px), and maximized (80vh/580px) states.
  - **Unified Left Sidebar (`UnifiedSidebar.tsx`)**: Single unified left sidebar featuring project registration (`+ Project`), search & filter bar, and an expandable nested tree (using Radix Collapsible) of conversations/threads under each project.
  - **Active Agent HUD & Subagent Tab Bar (`ThreadHeader.tsx` & `SubagentTabBar.tsx`)**:
    - Live HUD: Top bar indicator displaying real-time agent status (`● Working on: ...` or `● Thinking...`), live ticking elapsed timer `(14s)`, and an inline stop/interrupt trigger.
    - Subagent Tab Switcher: Radix tab strip switching between `[ 👑 Main Agent ]` and child subagents `[ 🤖 Subagent: DB Worker ]` with status badges.
  - **Streamlined Timeline & Approvals**: Renders user instructions, live streaming responses, collapsible tool calls, reasoning process accordions, and one-click Approval cards (`once` / `session` scopes).
  - **One-Click Diff Review Studio (`DiffReviewStudioModal.tsx`)**: Native file diff inspection and verdict recording modal with zero iframes.
  - **Mobile-First Responsiveness**: 100% screen width on mobile (< 768px down to 320px) for center chat, fixed/sticky composer with min 44px tap targets, zero horizontal scroll, and zero layout squishing.
- **What it Deliberately Avoids**:
  - No synthetic iframe embeds or mock port 5180 previews.
  - No competitor marketing radars or static prompt preset copy cards.
  - No redundant 2-column sidebar clutter.
  - No cramming complex multi-view tools into tiny bottom dock tabs.
  - No port 4500 hardcoding (uses same-origin `/api/admin/codex/...` reverse proxy).

---

## 2. Architecture & Key Files

The module is structured as a modular suite of embedded workspace components and consoles:

```
frontend/src/pages/admin/coding-cockpit/
├── index.tsx                                         # Barrel export for CodingCockpitPage
├── types.ts                                          # Shared contracts (issues, plans, metrics, fuzzer)
├── CodingCockpitPage.tsx                             # Full-viewport operational page shell with modal routing
├── CodexWorkbenchTab.tsx                             # Embedded Codex agent cockpit with resizable splitters
├── HealthSentinels.tsx                               # SRE health sentinels, OTel metrics, queue monitoring
├── StressFuzzer.tsx                                  # Concurrency race-condition load testing suite
├── IssuesStudio.tsx                                  # AST diagnostics & isolated sandbox fix executor
├── SkillsBrowser.tsx                                 # C:\Users\Frank\skills interactive catalog
├── EventStream.tsx                                   # Filtered SSE event stream console
├── coding-cockpit.test.ts                            # Unit test suite verifying routing, headers, splitters, HUD
├── README.md                                         # This living architecture documentation
└── workbench/
    ├── api/client.ts                                 # Same-origin /api/admin/codex API client with admin tokens
    ├── api/codexApi.ts                               # Typed API methods for threads, turns, diffs, approvals
    ├── store/useWorkbenchStore.ts                    # Reactive store (projects, threads, dock, modals, widths)
    ├── types/workbench.ts                            # State contracts and event envelope interfaces
    └── components/
        ├── layout/UnifiedSidebar.tsx                 # Consolidated single left sidebar with h-11 header
        ├── layout/ThreadHeader.tsx                   # Top bar HUD, sticky Model Selector, Tools dropdown (h-11)
        ├── layout/ProjectRail.tsx                    # Backwards-compatible thin shim to UnifiedSidebar
        ├── layout/ThreadSidebar.tsx                  # Backwards-compatible thin shim to UnifiedSidebar
        ├── dock/BottomConsoleDock.tsx                # Streamlined Terminal / Live Output runner dock
        ├── tools/SecondaryToolsModals.tsx            # Full-screen modal overlays for SRE, Fuzzer, AST, Skills
        ├── timeline/Timeline.tsx                     # Streaming conversation and activity timeline
        ├── timeline/SubagentTabBar.tsx               # Accessible subagent execution tab switcher
        ├── timeline/LiveActivityPulse.tsx            # Pulsing beacon and interrupt control
        ├── composer/Composer.tsx                     # Sticky multi-action composer with sticky model sync
        ├── inspector/Inspector.tsx                   # Right inspector panel with h-11 slim header
        ├── inspector/tabs/SettingsInspectorTab.tsx   # Workspace boundaries and OTel telemetry inspector
        ├── diff/DiffReviewStudioModal.tsx            # Fullscreen diff review studio overlay
        └── command-palette/CommandPalette.tsx        # Keyboard shortcut command palette
```

---

## 3. Setup, Configuration & Dependencies

- **Vite Reverse Proxy Rule**:
  - `frontend/vite.config.ts` proxies `/api` directly to `http://localhost:8000`. Native Codex endpoints are mounted directly in FastAPI Bookings under `/api/admin/codex` (eliminating the legacy standalone port 4500 rewrite rule).
- **Admin Shell Integration**:
  - Mounted inside `AdminLayout.tsx` at `/admin/coding-cockpit`.
  - Registered as an operational route in `admin-layout.tsx` (`min-h-0 flex-1 flex flex-col p-0 overflow-hidden`), giving full height to the workspace without clipping or duplicate outer scrollbars.
- **Design System & Theme Tokens**:
  - Radix UI primitives (`@radix-ui/react-tabs`, `@radix-ui/react-collapsible`, `@radix-ui/react-dialog`, `@radix-ui/react-dropdown-menu`, `@radix-ui/react-tooltip`).
  - Tailwind CSS dark theme tokens (`bg-slate-900`, `border-slate-800`, `text-slate-100`, `bg-slate-950`).
  - Standardized `h-11 border-b border-slate-800` header styling across all three columns.
- **Authentication**:
  - Uses the same-origin admin session bearer and tenant headers retrieved via `getAuthenticatedAdminHeaders()` and `getAdminAccessToken()` from `src/lib/api.ts` (attaching `X-Tenant`, `X-Token`, and `Authorization`).
- **Runtime Services**:
  - FastAPI Bookings backend on `http://127.0.0.1:8000` with native Codex routers mounted directly under `/api/admin/codex` (including `/health`, `/diagnostics/deep`, `/projects`, `/threads`, `/turns`, `/events`, `/settings`, and `/models`).

---

## 4. Core Workflows & Contracts

1. **Unified Navigation & Routing**:
   - Accessing legacy `/admin/resident-agent` or `/admin/coding-studio` cleanly redirects to `/admin/coding-cockpit`.
   - Sidebar displays `Engineering Cockpit` under the `Compliance & System` category.
2. **Project & Thread Hierarchy**:
   - Operator clicks **"+ Project"** in `UnifiedSidebar.tsx` to register a local directory target.
   - Expanding the project shows its conversations. Clicking a thread selects it and sets the worktree context.
   - Clicking **"+"** on any project row creates a new conversation under that project.
3. **Sticky Model Selection**:
   - The interactive Model Selector in `ThreadHeader.tsx` defaults to `gpt-5.6-sol` or the last chosen model from `localStorage` (`codex_last_used_model`).
   - Changing the model immediately updates the active thread's model policy and persists it for all subsequent turns.
4. **Secondary Tool Modals**:
   - Operator accesses secondary tools (SRE Health, Concurrency Stress Fuzzer, AST Issues Studio, Skills Library, Event Stream) via the "Tools" dropdown in `ThreadHeader.tsx`.
   - Clicking any tool opens a spacious, full-screen dialog overlay (`SecondaryToolsModals.tsx`) with ESC and 'X' close handling.
5. **Streamlined Terminal Runner**:
   - The bottom dock is strictly dedicated to the Terminal / Live Output runner, avoiding cramped tab strips or UI clipping.
6. **Draggable Resizable Side Panels**:
   - Desktop operators drag the splitter between Left Sidebar and Center (clamped 220px - 480px) or between Center and Right Inspector (clamped 260px - 600px).
   - Widths persist in `localStorage` under `codex_sidebar_width` and `codex_inspector_width`.
7. **Diff Review Studio**:
   - Changed files are indexed in `Inspector.tsx` (Changes tab).
   - Clicking **"Diffs"** opens `DiffReviewStudioModal.tsx` for side-by-side hunk review and operator verdict approval.

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
