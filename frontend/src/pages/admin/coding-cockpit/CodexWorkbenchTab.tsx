import React, { useEffect } from 'react'
import { useWorkbenchStore } from './workbench/store/useWorkbenchStore'
import { ProjectRail } from './workbench/components/layout/ProjectRail'
import { ThreadSidebar } from './workbench/components/layout/ThreadSidebar'
import { ThreadHeader } from './workbench/components/layout/ThreadHeader'
import { Timeline } from './workbench/components/timeline/Timeline'
import { Composer } from './workbench/components/composer/Composer'
import { Inspector } from './workbench/components/inspector/Inspector'
import { DiffReviewStudioModal } from './workbench/components/diff/DiffReviewStudioModal'
import { CommandPalette } from './workbench/components/command-palette/CommandPalette'

interface CodexWorkbenchTabProps {
  initialThreadId?: string
}

export const CodexWorkbenchTab: React.FC<CodexWorkbenchTabProps> = ({ initialThreadId }) => {
  const { activeThread, state, setAppMode, setSidebarOpen, selectThread } = useWorkbenchStore()

  useEffect(() => {
    if (initialThreadId && initialThreadId !== state.activeThreadId) {
      selectThread(initialThreadId)
    }
  }, [initialThreadId, state.activeThreadId, selectThread])

  return (
    <div className="relative flex flex-col w-full h-[calc(100vh-14rem)] min-h-[720px] rounded-xl border border-border/80 shadow-sm overflow-hidden bg-[var(--bg-app,#0f1115)] text-[var(--text-primary,#f2f4f7)]">
      {/* Demo Mode / Environment Status Banner */}
      {state.appMode === 'demo' && (
        <div className="bg-blue-600/90 text-white text-xs px-4 py-2 flex items-center justify-between shrink-0 z-30 font-medium">
          <span className="truncate pr-2">[DEMO MODE: Displaying synthetic Codex demonstration worktree data]</span>
          <button
            onClick={() => setAppMode('live')}
            className="px-2.5 py-1 bg-white/20 hover:bg-white/30 rounded transition-colors text-xs font-semibold"
          >
            Switch to Live API Mode
          </button>
        </div>
      )}

      {/* Main Workbench Layout Container */}
      <div className="flex-1 flex w-full min-h-0 overflow-hidden relative">
        {/* Mobile Drawer Backdrop */}
        {state.isSidebarOpen && (
          <div
            className="fixed inset-0 bg-black/60 z-40 md:hidden transition-opacity backdrop-blur-xs"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* Navigation Rail & Thread Sidebar */}
        <div
          className={`h-full shrink-0 z-40 transition-transform duration-200 ease-in-out fixed inset-y-0 left-0 flex md:relative md:inset-auto md:z-20 md:translate-x-0 ${
            state.isSidebarOpen ? 'translate-x-0 shadow-2xl md:shadow-none' : '-translate-x-full md:translate-x-0'
          }`}
        >
          <ProjectRail />
          <ThreadSidebar />
        </div>

        {/* Primary Workspace Area */}
        <main className="flex-1 flex flex-col h-full min-w-0 w-full overflow-hidden bg-[var(--bg-app,#0f1115)]">
          {/* Thread Header with Model, Reasoning Effort, and Controls */}
          <ThreadHeader />

          {/* Central Conversation and Activity Timeline */}
          <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden">
            {state.appMode === 'live' && state.projects.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-sm text-[var(--text-secondary,#aab2c0)]">
                <p className="font-semibold text-foreground">No projects connected</p>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                  Register a repository target or switch to Demo Mode to explore the Codex Engineering Workbench.
                </p>
                <button
                  onClick={() => setAppMode('demo')}
                  className="mt-4 px-3 py-1.5 rounded-lg border bg-muted/30 hover:bg-muted text-xs font-medium"
                >
                  Load Demo Mode
                </button>
              </div>
            ) : (
              <Timeline thread={activeThread} />
            )}
          </div>

          {/* Multi-Action Composer Footer */}
          <footer className="shrink-0 z-10 w-full max-w-full">
            <Composer />
          </footer>
        </main>

        {/* Inspector Panel */}
        <Inspector />
      </div>

      {/* Global Overlays: Diff Review Studio Modal & Command Palette */}
      <DiffReviewStudioModal />
      <CommandPalette />
    </div>
  )
}
