import { useEffect } from 'react'
import { useWorkbenchStore } from './store/useWorkbenchStore'
import { ProjectRail } from './components/layout/ProjectRail'
import { ThreadSidebar } from './components/layout/ThreadSidebar'
import { ThreadHeader } from './components/layout/ThreadHeader'
import { Timeline } from './components/timeline/Timeline'
import { Composer } from './components/composer/Composer'
import { Inspector } from './components/inspector/Inspector'
import { DiffReviewStudioModal } from './components/diff/DiffReviewStudioModal'
import { CommandPalette } from './components/command-palette/CommandPalette'

export function App() {
  const { activeThread, state, setAppMode } = useWorkbenchStore()

  // Initialize theme class
  useEffect(() => {
    if (state.theme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [state.theme])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)] antialiased font-sans">
      {/* 1. Project Navigation Rail (56-64px) */}
      <ProjectRail />

      {/* 2. Thread Sidebar (280-320px) */}
      <ThreadSidebar />

      {/* 3. Primary Workspace Area (Flexible central column) */}
      <main className="flex-1 flex flex-col h-full min-w-0 overflow-hidden bg-[var(--bg-app)]">
        {state.appMode === 'demo' && (
          <div className="bg-blue-600 text-white text-xs px-4 py-2 flex items-center justify-between flex-shrink-0 z-50 font-medium">
            <span>[DEMO MODE: Displaying synthetic demonstration data. Actions do not affect real files or backend state.]</span>
            <button 
              onClick={() => setAppMode('live')}
              aria-label="Switch to Live Mode"
              className="px-2 py-1 bg-white/20 hover:bg-white/30 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-white"
            >
              Switch to Live Mode
            </button>
          </div>
        )}

        {/* Sticky Thread Header */}
        <ThreadHeader />

        {/* Central Conversation and Activity Timeline */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {state.appMode === 'live' && state.projects.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-sm text-[var(--text-secondary)]">
              No projects connected — Register a project or switch to Demo Mode
            </div>
          ) : (
            <Timeline thread={activeThread} />
          )}
        </div>

        {/* Multi-Action Composer */}
        <footer className="flex-shrink-0 z-10">
          <Composer />
        </footer>
      </main>

      {/* 4. Inspector Panel (360-440px with 7 tabs) */}
      <Inspector />

      {/* Global Modals & Overlays */}
      <DiffReviewStudioModal />
      <CommandPalette />

      {/* WCAG 2.2 AA Live Announcer Region for Screen Readers */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {state.liveAnnouncements[state.liveAnnouncements.length - 1] || ''}
      </div>
    </div>
  )
}

export default App
