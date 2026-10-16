# Codex Control Centre V3 — Layout Shell, GPT Live Voice, Transparent Stream & Dedicated Workspaces

## 1. Purpose & Scope

Codex Control Centre V3 delivers a mobile-first, thumb-ergonomic administrative cockpit, WebRTC realtime voice engine, Agents Kit-inspired transparent stream timeline, and four dedicated job workspace surfaces. It provides high-efficiency operator supervision, subagent orchestration, and voice-driven steering across small mobile viewports (<640px) up to high-density desktop displays (>1024px).

The module encompasses:
- **Responsive Layout Shell** (`CodexV3Layout`): Orchestrates navigation, activity rail, mobile segmented control, center canvas, and stream telemetry.
- **5-Item Thumb-Zone Mobile Navigation** (`BottomTabBar`): Bottom navigation bar with safe-area insets (`pb-safe`) and 44px minimum tap targets.
- **Desktop Slim 52px Activity Rail** (`ActivityRail`): Desktop rail with tooltips, indicators, and dynamic notification badges for tickets, coding, planning, and signals.
- **Minimal 44px Top Bar** (`TopBar`): Project branding, branch indicator, and dynamic `((o)) LIVE` voice status pill.
- **Elevated 54px Microphone FAB** (`VoiceFAB`): Microphone Floating Action Button with animated halo rings (emerald for listening, violet for speaking, blue for thinking, amber for connecting).
- **24px-28px Real-time Waveform Strip** (`AudioWaveformStrip`): Audio waveform with animated volume bars, latency telemetry, and End Call control.
- **Unified Voice Context Provider** (`CodexVoiceContext`): Connects directly with `useRealtimeVoice` and Web Audio API `AnalyserNode`.
- **Transparent Stream Primitives**:
  - `ThinkingAccordion`: Collapsible reasoning disclosure with shimmering gradient animation.
  - `ToolExecutionCard`: Monospaced tool invocation card with status badges, target file, duration, and stdout.
  - `SubagentCard`: Child subagent tracker with live status badge, elapsed timer, and child thread view.
  - `InlineDiffCard`: Syntax-highlighted in-line diff card with line numbers and quick Accept/Discard actions.
  - `ApprovalGateCard`: High-contrast interactive card pausing execution for high-risk operations.
  - `TerminalSnippet`: Dark zinc console block (`bg-zinc-950 text-zinc-100 font-mono`) with test result summaries.
  - `ComposerBar`: Mobile touch composer with expanding textarea, attachment button, and voice controls.
  - `TransparentStream`: Assembles the complete Antigravity/VS Code Copilot style transparent timeline.
- **Four Dedicated Job Workspaces** (`workspaces/`):
  - `TicketsWorkspace`: Displays support tickets and triage queue with filter pills (All, Needs Auth, In Progress, Resolved), severity badges (High, Med, Low), Error Context preview with stack traces, and "Launch Codex Investigation" action button.
  - `CodingWorkspace`: Workspace surface for active coding with worktree selector, active branch status, side-by-side or unified diff studio preview for modified files, test execution runner with "Run Tests" action button and pass/fail summary, and "Promote to Release Branch" gate button.
  - `PlanningWorkspace`: Mission & work package DAG pipeline visualization cards, brief acceptance criteria checklist with PASS/PENDING badges, context checkpoints and rollback controls, and single-run authorization grant launcher.
  - `SignalsWorkspace`: SigNoz / OpenTelemetry APM links and live latency charts (P50, P95, P99), health sentinel matrix (FastAPI, PostgreSQL, Redis, Neo4j, Workers), SMS Outbox backlog card, and Chatwoot sync status card.
- **Main Page Assembly & Router Integration** (`index.tsx` & `App.tsx`):
  - Orchestrates `CodexV3Layout`, manages `activeView` and `mobileTab`, mounts the active workspace in the center canvas, mounts `TransparentStream` alongside or in the mobile drawer, and embeds `useCodexVoice`.
  - Registered as route `/admin/codex-v3` in `frontend/src/App.tsx`.

Scope boundaries:
- Codex V3 is authoritative for mobile-first supervisory layout, transparent agent execution streams, and realtime voice UX in the Codex ecosystem.
- Does not replace Chatwoot or backend database truth; consumes existing authenticated tenant endpoints.

## 2. Architecture & Key Files

```
frontend/src/pages/admin/codex-v3/
├── index.tsx                      # Main page assembly orchestrating layout, active workspace, stream, and voice
├── CodexV3Layout.tsx              # Responsive orchestrator shell (TopBar, BottomTabBar, Rail, Stream)
├── types.ts                       # Core domain types (CodexView, MobileTab, VoiceState, FilePatch, Stream events)
├── context/
│   └── CodexVoiceContext.tsx      # Realtime voice provider connecting to useRealtimeVoice & Web Audio
├── workspaces/
│   ├── TicketsWorkspace.tsx       # Triage queue with filter pills, severity badges, and investigation launcher
│   ├── CodingWorkspace.tsx        # Active coding studio, branch/worktree, diff studio, and test runner
│   ├── PlanningWorkspace.tsx      # Work package DAG pipeline, acceptance criteria, checkpoints, and elevation launcher
│   ├── SignalsWorkspace.tsx       # SigNoz APM links, P50/P95/P99 latency charts, sentinels, and sync cards
│   └── index.ts                   # Barrel export for all 4 workspaces
├── components/
│   ├── navigation/
│   │   ├── TopBar.tsx             # 44px minimal top bar with live voice status pill & branch info
│   │   ├── ActivityRail.tsx       # 52px slim desktop activity rail with tooltips & status badges
│   │   └── BottomTabBar.tsx       # 5-item thumb-zone mobile navigation bar (<640px)
│   ├── voice/
│   │   ├── VoiceFAB.tsx           # 54px elevated microphone FAB with dynamic multi-color halo rings
│   │   └── AudioWaveformStrip.tsx # Real-time 24px-28px audio waveform strip with latency & End Call
│   └── stream/
│       ├── ThinkingAccordion.tsx  # Reasoning disclosure with gradient text animation
│       ├── ToolExecutionCard.tsx  # Monospaced tool card with status badges & expandable output
│       ├── SubagentCard.tsx       # Child subagent tracker with elapsed time & child thread viewer
│       ├── InlineDiffCard.tsx     # Syntax-highlighted diff with line numbers & Accept/Discard
│       ├── ApprovalGateCard.tsx   # High-contrast approval gate with Approve & Steer/Reject
│       ├── TerminalSnippet.tsx    # Dark zinc console block with pass/fail test badges
│       ├── ComposerBar.tsx        # Mobile touch composer with voice & attachment controls
│       ├── TransparentStream.tsx  # End-to-end timeline orchestrator with auto-scroll management
│       └── index.ts               # Barrel exports for stream primitives
├── codex-v3.test.ts               # Unit & integration test suite verifying layout & voice contracts
├── stream.test.ts                 # Unit test suite verifying stream components and contracts
├── workspaces.test.ts             # Unit test suite verifying the 4 workspaces and page assembly
└── README.md                      # Rule 10 living documentation
```

Key interfaces:
- `CodexView`: `'tickets' | 'coding' | 'planning' | 'signals'`
- `MobileTab`: `'workspace' | 'stream'`
- `VoiceState`: `'idle' | 'connecting' | 'listening' | 'speaking' | 'thinking' | 'error'`
- `SupportTicket`: `{ id: string; title: string; severity: 'high' | 'med' | 'low'; status: 'needs_auth' | 'in_progress' | 'resolved' | 'open'; errorContext: string; stackTrace?: string; }`
- `ModifiedFile`: `{ path: string; status: 'modified' | 'added' | 'deleted'; additions: number; deletions: number; diffHunks: string[]; }`
- `WorkPackageNode`: `{ id: string; title: string; phase: string; status: 'completed' | 'in_progress' | 'pending' | 'blocked'; dependencies: string[]; }`
- `SentinelStatus`: `{ id: string; name: string; service: string; status: 'healthy' | 'degraded' | 'down'; latencyMs: number; uptimePercent: number; }`

## 3. Setup, Configuration & Dependencies

### Dependencies
- `@/lib/api`: `authenticatedAdminFetch` for tenant-authenticated session calls.
- `frontend/src/pages/admin/business-assistant/use-realtime-voice.ts`: Underlying WebRTC and data channel session hook.
- `lucide-react`: UI iconography (`AlertCircle`, `GitBranch`, `Play`, `CheckCircle2`, `Activity`, `Layers`, `Terminal`).
- `@/components/ui/tooltip`: Radix-backed tooltips for desktop rail items.

### Configuration
- Safe-area bottom padding is applied via `pb-safe` and `env(safe-area-inset-bottom, 0px)` across mobile navigation bars and main scroll containers.
- Audio metering utilizes browser `AudioContext` and `AnalyserNode` with smooth fallback simulation if microphone analysis is restricted.
- Auto-scroll in `TransparentStream` automatically tracks container scroll height with smooth transitions; manual user scroll-up pauses lock and displays a "Scroll to latest" button.

## 4. Core Workflows & Contracts

### Workspace Navigation & View Lifecycle
1. The operator selects a view via the desktop `ActivityRail` or mobile `BottomTabBar` (`tickets`, `coding`, `planning`, `signals`).
2. Center canvas mounts the active workspace surface:
   - **Tickets**: Displays triage queue, filter pills, error context previews, and investigation launcher. Clicking "Launch Codex Investigation" immediately dispatches diagnostic events to the transparent stream.
   - **Coding**: Displays active worktree, branch switcher, unified/side-by-side diff studio, automated test runner, and release promotion gate.
   - **Planning**: Displays work package DAG pipeline, acceptance criteria checklist, context checkpoints with instant rollback controls, and single-run elevation launcher.
   - **Signals**: Displays live SigNoz APM telemetry, P50/P95/P99 latency distribution curves, health sentinels matrix, and SMS/Chatwoot sync status.
3. On mobile viewports (<1024px), the operator can toggle between the Workspace surface and the Live Agent Stream via the segmented control.

### Voice & Stream Synchronization
1. `useCodexVoice` provides hands-free speech input and transcript deltas to the page assembly.
2. Inbound voice turns and workspace actions (such as test runs or ticket investigations) feed seamlessly into the `TimelineEvent` stream.

## 5. Data Safety & Isolation

- **Tenant Isolation**: All conversation creation, tickets, and telemetry queries strictly inherit tenant isolation boundaries.
- **Zero Mock State**: Components connect to real schemas and types; no fabricated setTimeout stubs masquerade as real backend processing.
- **Controlled High-Risk Execution**: Destructive operations (code execution, Git promotion, context rollback) require explicit operator authorization through approval gates and elevation controls.

## 6. Known Issues, Edge Cases & Outstanding Work

- **Mobile Viewport Transitions**: Smooth layout transition animations between workspace and stream tabs are optimized with CSS transitions.
- **SigNoz Local APM Connectivity**: When running outside local Docker environments, APM links fallback to `/admin/telemetry`.

## 7. Verification & Testing Commands

To verify TypeScript compilation:
```powershell
npx tsc --noEmit
```

To run unit and integration tests:
```powershell
npm test
```

To run the dedicated Codex V3 test suite:
```powershell
node --experimental-strip-types --test "src/pages/admin/codex-v3/*.test.ts"
```

To verify Rule 10 living documentation compliance:
```powershell
python scripts/verify_living_docs.py --path frontend/src/pages/admin/codex-v3/README.md
```
