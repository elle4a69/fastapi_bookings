import React, { useEffect } from 'react'
import { useWorkbenchStore } from './workbench/store/useWorkbenchStore'
import { UnifiedSidebar } from './workbench/components/layout/UnifiedSidebar'
import { ThreadHeader } from './workbench/components/layout/ThreadHeader'
import { Timeline } from './workbench/components/timeline/Timeline'
import { Composer } from './workbench/components/composer/Composer'
import { Inspector } from './workbench/components/inspector/Inspector'
import { BottomConsoleDock } from './workbench/components/dock/BottomConsoleDock'
import { DiffReviewStudioModal } from './workbench/components/diff/DiffReviewStudioModal'
import { CommandPalette } from './workbench/components/command-palette/CommandPalette'
import type { AgentStatusData } from './types'

interface CodexWorkbenchTabProps {
  initialThreadId?: string
  statusData?: AgentStatusData | null
  loadingStatus?: boolean
  onRefreshStatus?: () => Promise<void>
}

export const CodexWorkbenchTab: React.FC<CodexWorkbenchTabProps> = ({
  initialThreadId,
  statusData,
  loadingStatus,
  onRefreshStatus
}) => {
  const {
    activeThread,
    state,
    setAppMode,
    setSidebarOpen,
    selectThread
  } = useWorkbenchStore()

  useEffect(() => {
    if (initialThreadId && initialThreadId !== state.activeThreadId) {
      selectThread(initialThreadId)
    }
  }, [initialThreadId, state.activeThreadId, selectThread])

  return (
    <div className="relative flex flex-col w-full h-full min-h-[500px] flex-1 overflow-hidden bg-slate-900 text-slate-100 select-none">
      {/* Demo Mode / Environment Status Notification Banner */}
      {state.appMode === 'demo' && (
        <div className="bg-indigo-600/90 text-white text-xs px-3 sm:px-4 py-1.5 flex items-center justify-between shrink-0 z-30 font-medium border-b border-indigo-500/40">
          <span className="truncate pr-2 text-[11px] sm:text-xs">
            [DEMO MODE: Synthetic Codex sandbox worktree data active]
          </span>
          <button
            onClick={() => setAppMode('live')}
            className="px-2 py-0.5 bg-white/20 hover:bg-white/30 rounded transition-colors text-[11px] font-semibold shrink-0 cursor-pointer"
          >
            Switch to Live API
          </button>
        </div>
      )}

      {/* Main Workspace Frame */}
      <div className="flex-1 flex w-full min-h-0 overflow-hidden relative">
        {/* Mobile Slide-out Drawer Backdrop for Left Sidebar */}
        {state.isSidebarOpen && (
          <div
            className="fixed inset-0 bg-black/60 z-40 md:hidden transition-opacity backdrop-blur-xs"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* 1. Unified Left Sidebar: Off-canvas on mobile, smoothly collapsible on desktop */}
        <div
          className={`h-full shrink-0 z-40 transition-all duration-300 ease-in-out fixed inset-y-0 left-0 w-[290px] sm:w-[320px] md:relative md:inset-auto md:z-20 ${
            state.isSidebarOpen
              ? 'translate-x-0 md:translate-x-0 shadow-2xl md:shadow-none'
              : '-translate-x-full md:-translate-x-full md:w-0 md:overflow-hidden'
          }`}
        >
          <div className="w-[290px] sm:w-[320px] h-full">
            <UnifiedSidebar onSelectThreadMobile={() => setSidebarOpen(false)} />
          </div>
        </div>

        {/* 2. Primary Workspace Center (takes 100% width on mobile or when sidebars collapse) */}
        <main className="flex-1 flex flex-col h-full min-w-0 w-full overflow-hidden bg-slate-900 relative">
          {/* Thread Header with Active Agent HUD, Live Timer & Panel Controls */}
          <ThreadHeader />

          {/* Central Conversation and Streaming Activity Timeline */}
          <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden relative">
            {state.appMode === 'live' && state.projects.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center p-6 sm:p-8 text-center text-sm text-slate-400">
                <p className="font-semibold text-slate-200">No projects connected</p>
                <p className="text-xs text-slate-400 mt-1 max-w-sm leading-relaxed">
                  Register a repository target in the sidebar or switch to Demo Mode to explore the Codex Engineering Workbench.
                </p>
                <button
                  onClick={() => setAppMode('demo')}
                  className="mt-4 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium cursor-pointer"
                >
                  Load Demo Mode
                </button>
              </div>
            ) : (
              <Timeline thread={activeThread} />
            )}
          </div>

          {/* 3. Integrated Bottom Console Dock (Terminal, Health, Fuzzer, AST Issues) */}
          <BottomConsoleDock
            statusData={statusData}
            loadingStatus={loadingStatus}
            onRefreshStatus={onRefreshStatus}
          />

          {/* 4. Multi-Action Fixed Composer Footer */}
          <footer className="shrink-0 z-10 w-full max-w-full">
            <Composer />
          </footer>
        </main>

        {/* 5. Right Inspector & Diff Review Panel */}
        <Inspector />
      </div>

      {/* Global Modals: Full Diff Review Studio Modal & Command Palette */}
      <DiffReviewStudioModal />
      <CommandPalette />
    </div>
  )
}
export default CodexWorkbenchTab
