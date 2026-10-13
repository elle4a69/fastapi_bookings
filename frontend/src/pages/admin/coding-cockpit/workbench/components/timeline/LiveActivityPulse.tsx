import React from 'react'
import { Square } from 'lucide-react'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { Button } from '../ui/button'

export const LiveActivityPulse: React.FC = () => {
  const { state, stopActiveTurn, activeThread } = useWorkbenchStore()

  // Only render when turn is active or streaming
  const isStreaming = state.isStreaming
  const hasInProgressTurn = Boolean(activeThread?.turns?.some(t => t.status === 'in_progress'))

  if (!isStreaming && !hasInProgressTurn) {
    return null
  }

  const elapsed = state.turnElapsedSeconds || 0
  const actionText = state.currentActionText || 'Thinking...'

  return (
    <aside
      role="status"
      aria-live="polite"
      aria-label="Active Turn Execution Pulse"
      className="w-full flex-shrink-0 border-t border-[var(--border)] bg-[var(--surface-primary)]/95 backdrop-blur-xs px-3 sm:px-4 py-2 flex items-center justify-between gap-3 shadow-xs z-20 max-w-full overflow-hidden"
    >
      <div className="flex items-center gap-2.5 min-w-0 flex-1 overflow-hidden">
        {/* Animated pulsing beacon */}
        <span className="relative flex h-2.5 w-2.5 flex-shrink-0" aria-hidden="true">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
        </span>

        {/* Status text with elapsed time and current action */}
        <div className="flex items-center gap-1.5 min-w-0 text-xs truncate">
          <span className="font-semibold text-[var(--text-primary)] flex-shrink-0">
            Agent Working
          </span>
          <span className="font-mono text-[var(--text-secondary)] text-[11px] flex-shrink-0">
            (elapsed: {elapsed}s)
          </span>
          <span className="text-[var(--text-subtle)] truncate">
            — {actionText}
          </span>
        </div>
      </div>

      {/* Inline Stop / Interrupt Button */}
      <Button
        type="button"
        size="sm"
        variant="dangerOutline"
        onClick={stopActiveTurn}
        aria-label="Stop active turn"
        className="min-h-[36px] px-2.5 sm:px-3 text-xs gap-1.5 flex-shrink-0 hover:bg-rose-500/10"
      >
        <Square className="w-3 h-3 fill-current" aria-hidden="true" />
        <span>Stop</span>
      </Button>
    </aside>
  )
}
