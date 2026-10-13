import React from 'react'
import {
  Terminal,
  ChevronDown,
  ChevronUp,
  Maximize2,
  Minimize2,
  X
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { TerminalTab } from '../inspector/tabs/TerminalTab'
import type { AgentStatusData } from '../../../types'

interface BottomConsoleDockProps {
  statusData?: AgentStatusData | null
  loadingStatus?: boolean
  onRefreshStatus?: () => Promise<void>
}

export const BottomConsoleDock: React.FC<BottomConsoleDockProps> = () => {
  const {
    state,
    setBottomDockOpen,
    setActiveBottomDockTab,
    setBottomDockMode
  } = useWorkbenchStore()

  const isDockOpen = state.isBottomDockOpen
  const dockMode = state.bottomDockMode // 'collapsed' | 'expanded' | 'maximized'

  // If dock is closed or minimized, render streamlined bottom launcher bar
  if (!isDockOpen || dockMode === 'collapsed') {
    return (
      <div
        className="w-full shrink-0 border-t border-slate-800 bg-slate-900/95 backdrop-blur-xs px-2.5 sm:px-3 py-1 flex items-center justify-between text-xs text-slate-300 z-20 min-h-[38px] select-none"
        aria-label="Console Dock Minimized Bar"
      >
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setActiveBottomDockTab('terminal')
              setBottomDockOpen(true)
              setBottomDockMode('expanded')
            }}
            className="flex items-center gap-2 px-2.5 py-1 rounded text-slate-300 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer text-xs font-medium"
          >
            <Terminal className="w-3.5 h-3.5 text-indigo-400" />
            <span>Terminal / Live Output Runner</span>
          </button>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setActiveBottomDockTab('terminal')
              setBottomDockOpen(true)
              setBottomDockMode('expanded')
            }}
            className="h-7 px-2 text-xs text-slate-400 hover:text-slate-100 hover:bg-slate-800 gap-1 cursor-pointer"
            title="Expand Terminal Runner"
          >
            <ChevronUp className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Terminal</span>
          </Button>
        </div>
      </div>
    )
  }

  // Expanded or Maximized Dock
  const dockHeightClass = dockMode === 'maximized'
    ? 'h-[80vh] sm:h-[580px]'
    : 'h-[320px] sm:h-[350px]'

  return (
    <section
      className={`w-full shrink-0 flex flex-col border-t border-slate-800 bg-slate-900 text-slate-100 z-20 shadow-2xl transition-all duration-200 overflow-hidden ${dockHeightClass}`}
      aria-label="Integrated Bottom Console Dock"
    >
      {/* Streamlined Dock Header for Terminal / Live Output Runner */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-slate-800 bg-slate-950/80 backdrop-blur-xs shrink-0 min-h-[40px]">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-200">
          <Terminal className="w-4 h-4 text-indigo-400" />
          <span>Terminal / Live Output Runner</span>
        </div>

        {/* Right Dock Controls: Maximize/Restore, Minimize, Close */}
        <div className="flex items-center gap-1 shrink-0">
          {dockMode === 'maximized' ? (
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={() => setBottomDockMode('expanded')}
              className="h-7 w-7 text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
              title="Restore standard height"
            >
              <Minimize2 className="w-3.5 h-3.5" />
            </Button>
          ) : (
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={() => setBottomDockMode('maximized')}
              className="h-7 w-7 text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
              title="Maximize dock height"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </Button>
          )}

          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={() => setBottomDockMode('collapsed')}
            className="h-7 w-7 text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
            title="Minimize dock"
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </Button>

          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={() => setBottomDockOpen(false)}
            className="h-7 w-7 text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
            title="Close dock"
          >
            <X className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Dock Content Body: Terminal Only */}
      <div className="flex-1 min-h-0 overflow-hidden bg-slate-950 p-2 sm:p-3">
        <TerminalTab />
      </div>
    </section>
  )
}

export default BottomConsoleDock
