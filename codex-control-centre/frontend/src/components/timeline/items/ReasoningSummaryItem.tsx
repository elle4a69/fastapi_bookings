import React, { useState } from 'react'
import { Brain, ChevronDown, ChevronRight, Clock } from 'lucide-react'
import type { ReasoningSummaryItem as ReasoningSummaryItemType } from '../../../types/workbench'

interface Props {
  item: ReasoningSummaryItemType
}

export const ReasoningSummaryItem: React.FC<Props> = ({ item }) => {
  const [isExpanded, setIsExpanded] = useState(false)

  const formattedDuration = (item.elapsedMs / 1000).toFixed(1)

  return (
    <div className="my-2 max-w-4xl mx-auto border border-[var(--border)] rounded-md bg-[var(--surface-secondary)]/40 overflow-hidden text-xs">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 flex items-center justify-between gap-2 text-left hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <Brain className="w-3.5 h-3.5 text-[var(--accent)] flex-shrink-0" />
          <span className="font-medium text-[var(--text-secondary)]">Thought for {formattedDuration}s</span>
          <span className="text-[var(--text-subtle)] truncate text-[11px]">— {item.summary}</span>
        </div>

        <div className="flex items-center gap-1.5 text-[var(--text-subtle)] flex-shrink-0">
          <Clock className="w-3 h-3" />
          <span className="text-[10px] font-mono">{formattedDuration}s</span>
          {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </div>
      </button>

      {isExpanded && (
        <div className="p-3 border-t border-[var(--border)] bg-[var(--surface-primary)] text-xs font-mono text-[var(--text-secondary)] whitespace-pre-wrap leading-relaxed">
          {item.rawTrace || item.summary}
        </div>
      )}
    </div>
  )
}
