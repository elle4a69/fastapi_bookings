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
  const { activeThread, state, setAppMode, setSidebarOpen } = useWorkbenchStore()

  // Initialize theme class
  useEffect(() => {
    if (state.theme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [state.theme])

  return (
    <div className="flex h-screen w-screen max-w-full overflow-x-hidden overflow-y-hidden bg-[var(--bg-app)] text-[var(--text-primary)] antialiased font-sans">
      {/* 1 & 2. Responsive Navigation: Off-canvas drawer on mobile (<768px), side-by-side in-flow on tablet (768px-1023px) and desktop (>1024px) */}
      
      {/* Mobile Drawer Backdrop */}
      {state.isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden transition-opacity backdrop-blur-xs"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Navigation Container */}
      <div
        className={`h-full flex-shrink-0 z-50 transition-transform duration-200 ease-in-out fixed inset-y-0 left-0 flex md:relative md:inset-auto md:z-20 md:translate-x-0 ${
          state.isSidebarOpen ? 'translate-x-0 shadow-2xl md:shadow-none' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <ProjectRail />
        <ThreadSidebar />
      </div>

      {/* 3. Primary Workspace Area (Full-width on mobile, flexible central column on tablet/desktop) */}
      <main className="flex-1 flex flex-col h-full min-w-0 w-full max-w-full overflow-hidden bg-[var(--bg-app)]">
        {state.appMode === 'demo' && (
          <div className="bg-blue-600 text-white text-xs px-3 sm:px-4 py-2 flex items-center justify-between flex-shrink-0 z-30 font-medium">
            <span className="truncate pr-2">[DEMO MODE: Displaying synthetic demonstration data]</span>
            <button 
              onClick={() => setAppMode('live')}
              aria-label="Switch to Live Mode"
              className="px-2 py-1 bg-white/20 hover:bg-white/30 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-white flex-shrink-0 min-h-[32px] flex items-center text-xs"
            >
              Switch to Live Mode
            </button>
          </div>
        )}

        {/* Sticky Thread Header */}
        <ThreadHeader />

        {/* Central Conversation and Activity Timeline */}
        <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden">
          {state.appMode === 'live' && state.projects.length === 0 ? (
            <div className="flex-1 flex items-center justify-center p-4 text-center text-sm text-[var(--text-secondary)]">
              No projects connected — Register a project or switch to Demo Mode
            </div>
          ) : (
            <Timeline thread={activeThread} />
          )}
        </div>

        {/* Multi-Action Composer */}
        <footer className="flex-shrink-0 z-10 w-full max-w-full">
          <Composer />
        </footer>
      </main>

      {/* 4. Inspector Panel (Adaptive: in-flow on desktop >1024px, slide-over overlay on tablet 768-1023px, full-width sheet on mobile <768px) */}
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
