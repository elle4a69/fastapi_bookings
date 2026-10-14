import React, { useEffect, useState } from 'react'
import { useWorkbenchStore } from './workbench/store/useWorkbenchStore'
import { UnifiedSidebar } from './workbench/components/layout/UnifiedSidebar'
import { ThreadHeader } from './workbench/components/layout/ThreadHeader'
import { Timeline } from './workbench/components/timeline/Timeline'
import { Composer } from './workbench/components/composer/Composer'
import { Inspector } from './workbench/components/inspector/Inspector'
import { BottomConsoleDock } from './workbench/components/dock/BottomConsoleDock'
import { DiffReviewStudioModal } from './workbench/components/diff/DiffReviewStudioModal'
import { SecondaryToolsModals } from './workbench/components/tools/SecondaryToolsModals'
import { SupportTicketManagementStation } from './workbench/components/tools/SupportTicketManagementStation'
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
    selectThread,
    setSidebarWidth,
    setInspectorWidth
  } = useWorkbenchStore()

  const [isDraggingLeft, setIsDraggingLeft] = useState(false)
  const [isDraggingRight, setIsDraggingRight] = useState(false)

  useEffect(() => {
    if (initialThreadId && initialThreadId !== state.activeThreadId) {
      selectThread(initialThreadId)
    }
  }, [initialThreadId, state.activeThreadId, selectThread])

  // Left Sidebar Resizer Splitter (220px to 480px, clamped)
  const handleLeftSplitterPointerDown = (e: React.PointerEvent) => {
    e.preventDefault()
    setIsDraggingLeft(true)
    const startX = e.clientX
    const startWidth = state.sidebarWidth

    const onPointerMove = (moveEvent: PointerEvent) => {
      const delta = moveEvent.clientX - startX
      const newWidth = Math.max(220, Math.min(480, startWidth + delta))
      setSidebarWidth(newWidth)
    }

    const onPointerUp = () => {
      setIsDraggingLeft(false)
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
    }

    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
  }

  // Right Inspector Resizer Splitter (260px to 600px, clamped)
  const handleRightSplitterPointerDown = (e: React.PointerEvent) => {
    e.preventDefault()
    setIsDraggingRight(true)
    const startX = e.clientX
    const startWidth = state.inspectorWidth

    const onPointerMove = (moveEvent: PointerEvent) => {
      const delta = startX - moveEvent.clientX
      const newWidth = Math.max(260, Math.min(600, startWidth + delta))
      setInspectorWidth(newWidth)
    }

    const onPointerUp = () => {
      setIsDraggingRight(false)
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
    }

    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
  }

  return (
    <div
      className={`relative flex flex-col w-full h-full min-h-[500px] flex-1 overflow-hidden bg-background text-foreground select-none ${
        isDraggingLeft || isDraggingRight ? 'cursor-col-resize select-none' : ''
      }`}
    >
      {/* Demo Mode / Environment Status Notification Banner */}
      {state.appMode === 'demo' && (
        <div className="bg-primary/90 text-primary-foreground text-xs px-3 sm:px-4 py-1.5 flex items-center justify-between shrink-0 z-30 font-medium border-b border-primary/30">
          <span className="truncate pr-2 text-[11px] sm:text-xs">
            [DEMO MODE: Synthetic Codex sandbox worktree data active]
          </span>
          <button
            onClick={() => setAppMode('live')}
            className="px-2 py-0.5 bg-primary-foreground/20 hover:bg-primary-foreground/30 text-primary-foreground rounded transition-colors text-[11px] font-semibold shrink-0 cursor-pointer"
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

        {/* 1. Unified Left Sidebar: Off-canvas on mobile, resizable & collapsible on desktop */}
        <div
          style={{ width: state.isSidebarOpen ? `${state.sidebarWidth}px` : undefined }}
          className={`h-full shrink-0 z-40 transition-[transform] md:transition-none duration-300 ease-in-out fixed inset-y-0 left-0 w-[290px] sm:w-[320px] md:w-auto md:relative md:inset-auto md:z-20 ${
            state.isSidebarOpen
              ? 'translate-x-0 md:translate-x-0 shadow-2xl md:shadow-none'
              : '-translate-x-full md:-translate-x-full md:w-0! md:overflow-hidden'
          }`}
        >
          <div className="h-full w-full" style={{ width: `${state.sidebarWidth}px` }}>
            <UnifiedSidebar onSelectThreadMobile={() => setSidebarOpen(false)} />
          </div>
        </div>

        {/* Left Vertical Resizer Splitter (desktop md+ only, when sidebar is open) */}
        {state.isSidebarOpen && (
          <div
            onPointerDown={handleLeftSplitterPointerDown}
            className={`hidden md:flex w-1.5 hover:w-1.5 shrink-0 cursor-col-resize items-center justify-center transition-colors z-30 select-none group ${
              isDraggingLeft ? 'bg-primary' : 'hover:bg-primary/50 bg-border'
            }`}
            title="Drag to resize sidebar (220px - 480px)"
          >
            <div
              className={`w-0.5 h-6 rounded-full transition-colors ${
                isDraggingLeft ? 'bg-primary-foreground' : 'bg-muted-foreground group-hover:bg-primary-foreground'
              }`}
            />
          </div>
        )}

        {/* 2. Primary Workspace Center (takes available width) */}
        <main className="flex-1 flex flex-col h-full min-w-0 w-full overflow-hidden bg-background relative">
          {/* Thread Header with Standardized h-11 Slim Height, Sticky Model Selector & Tools Launcher */}
          <ThreadHeader statusData={statusData} />

          {/* Central Conversation Timeline OR Support Tickets Management Station */}
          <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden relative">
            {state.activeCenterView === 'tickets' ? (
              <SupportTicketManagementStation isCenterStage={true} />
            ) : state.appMode === 'live' && state.projects.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center p-6 sm:p-8 text-center text-sm text-muted-foreground">
                <p className="font-semibold text-foreground">No projects connected</p>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm leading-relaxed">
                  Register a repository target in the sidebar or switch to Demo Mode to explore the Codex Engineering Workbench.
                </p>
                <button
                  onClick={() => setAppMode('demo')}
                  className="mt-4 px-3 py-1.5 rounded-lg border border-border bg-card hover:bg-muted text-foreground text-xs font-medium cursor-pointer"
                >
                  Load Demo Mode
                </button>
              </div>
            ) : (
              <Timeline thread={activeThread} />
            )}
          </div>

          {/* 3. Streamlined Bottom Console Dock (strictly Terminal / Live Output Runner) */}
          <BottomConsoleDock
            statusData={statusData}
            loadingStatus={loadingStatus}
            onRefreshStatus={onRefreshStatus}
          />

          {/* 4. Multi-Action Fixed Composer Footer (shown in Timeline view) */}
          {state.activeCenterView !== 'tickets' && (
            <footer className="shrink-0 z-10 w-full max-w-full">
              <Composer />
            </footer>
          )}
        </main>

        {/* Right Vertical Resizer Splitter (desktop lg+ only, when inspector is open) */}
        {state.isInspectorOpen && (
          <div
            onPointerDown={handleRightSplitterPointerDown}
            className={`hidden lg:flex w-1.5 hover:w-1.5 shrink-0 cursor-col-resize items-center justify-center transition-colors z-30 select-none group ${
              isDraggingRight ? 'bg-primary' : 'hover:bg-primary/50 bg-border'
            }`}
            title="Drag to resize inspector (260px - 600px)"
          >
            <div
              className={`w-0.5 h-6 rounded-full transition-colors ${
                isDraggingRight ? 'bg-primary-foreground' : 'bg-muted-foreground group-hover:bg-primary-foreground'
              }`}
            />
          </div>
        )}

        {/* 5. Right Inspector & Diff Review Panel */}
        <Inspector />
      </div>

      {/* Global Modals: Full Diff Review Studio Modal, Secondary Tools Modals & Command Palette */}
      <DiffReviewStudioModal />
      <SecondaryToolsModals
        statusData={statusData}
        loadingStatus={loadingStatus}
        onRefreshStatus={onRefreshStatus}
      />
      <CommandPalette />
    </div>
  )
}
export default CodexWorkbenchTab
