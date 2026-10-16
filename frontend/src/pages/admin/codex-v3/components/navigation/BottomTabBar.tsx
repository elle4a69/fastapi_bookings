import React from 'react'
import { CheckSquare, Terminal, Compass, Activity } from 'lucide-react'
import type { CodexView } from '../../types'
import { VoiceFAB } from '../voice/VoiceFAB'
import { cn } from '@/lib/utils'

interface BottomTabBarProps {
  activeView: CodexView
  onViewChange: (view: CodexView) => void
  ticketCount?: number
  activeSubagents?: number
  signalCount?: number
  className?: string
}

export const BottomTabBar: React.FC<BottomTabBarProps> = ({
  activeView,
  onViewChange,
  ticketCount = 0,
  activeSubagents = 0,
  signalCount = 0,
  className,
}) => {
  return (
    <nav
      data-testid="codex-bottom-tab-bar"
      aria-label="Bottom Navigation"
      className={cn(
        'sm:hidden fixed bottom-0 left-0 right-0 z-40 bg-card/95 backdrop-blur-md border-t border-border/40 pb-safe pb-[max(env(safe-area-inset-bottom,0px),0.5rem)] select-none shadow-lg',
        className,
      )}
    >
      <div className="grid grid-cols-5 items-end h-[56px] px-1 relative">
        {/* 1. Tickets */}
        <button
          type="button"
          data-testid="bottom-tab-tickets"
          onClick={() => onViewChange('tickets')}
          className={cn(
            'flex flex-col items-center justify-center min-h-[44px] min-w-[44px] py-1 transition-colors relative outline-none focus-visible:text-primary',
            activeView === 'tickets' ? 'text-primary font-semibold' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <div className="relative">
            <CheckSquare className="h-5 w-5" />
            {ticketCount > 0 && (
              <span className="absolute -top-1 -right-2 flex h-3.5 min-w-[14px] items-center justify-center rounded-full bg-primary px-0.5 text-[9px] font-bold text-primary-foreground">
                {ticketCount > 99 ? '99+' : ticketCount}
              </span>
            )}
          </div>
          <span className="text-[10px] mt-0.5 tracking-tight">Tickets</span>
        </button>

        {/* 2. Coding */}
        <button
          type="button"
          data-testid="bottom-tab-coding"
          onClick={() => onViewChange('coding')}
          className={cn(
            'flex flex-col items-center justify-center min-h-[44px] min-w-[44px] py-1 transition-colors relative outline-none focus-visible:text-primary',
            activeView === 'coding' ? 'text-primary font-semibold' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <div className="relative">
            <Terminal className="h-5 w-5" />
            {activeSubagents > 0 && (
              <span className="absolute -top-1 -right-2 flex h-3.5 min-w-[14px] items-center justify-center rounded-full bg-emerald-500 px-0.5 text-[9px] font-bold text-white">
                {activeSubagents}
              </span>
            )}
          </div>
          <span className="text-[10px] mt-0.5 tracking-tight">Coding</span>
        </button>

        {/* 3. Center Voice FAB slot */}
        <div className="flex flex-col items-center justify-start h-full">
          <div className="-mt-5">
            <VoiceFAB />
          </div>
        </div>

        {/* 4. Planning */}
        <button
          type="button"
          data-testid="bottom-tab-planning"
          onClick={() => onViewChange('planning')}
          className={cn(
            'flex flex-col items-center justify-center min-h-[44px] min-w-[44px] py-1 transition-colors relative outline-none focus-visible:text-primary',
            activeView === 'planning' ? 'text-primary font-semibold' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <Compass className="h-5 w-5" />
          <span className="text-[10px] mt-0.5 tracking-tight">Planning</span>
        </button>

        {/* 5. Signals */}
        <button
          type="button"
          data-testid="bottom-tab-signals"
          onClick={() => onViewChange('signals')}
          className={cn(
            'flex flex-col items-center justify-center min-h-[44px] min-w-[44px] py-1 transition-colors relative outline-none focus-visible:text-primary',
            activeView === 'signals' ? 'text-primary font-semibold' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <div className="relative">
            <Activity className="h-5 w-5" />
            {signalCount > 0 && (
              <span className="absolute -top-1 -right-2 flex h-3.5 min-w-[14px] items-center justify-center rounded-full bg-amber-500 px-0.5 text-[9px] font-bold text-white">
                {signalCount}
              </span>
            )}
          </div>
          <span className="text-[10px] mt-0.5 tracking-tight">Signals</span>
        </button>
      </div>
    </nav>
  )
}
