import React, { useState, useRef, useEffect } from 'react'
import { Brain, ChevronDown, ChevronRight, Clock, Sparkles } from 'lucide-react'
import type { ReasoningSummaryItem as ReasoningSummaryItemType } from '../../../types/workbench'

interface Props {
  item: ReasoningSummaryItemType
}

export const ReasoningSummaryItem: React.FC<Props> = ({ item }) => {
  const [userToggled, setUserToggled] = useState<boolean | null>(null)
  const isStreaming = Boolean(item.isStreaming)
  const isExpanded = userToggled !== null ? userToggled : (isStreaming || false)

  const contentRef = useRef<HTMLDivElement>(null)

  // Auto-scroll trace container as new reasoning tokens arrive
  useEffect(() => {
    if (isStreaming && isExpanded && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [item.rawTrace, item.summary, isStreaming, isExpanded])

  const formattedDuration = (item.elapsedMs / 1000).toFixed(1)

  return (
    <div className={`my-2 max-w-4xl mx-auto border rounded-md overflow-hidden text-xs w-full max-w-full transition-colors ${
      isStreaming
        ? 'border-[var(--accent)]/40 bg-[var(--accent-subtle)]/10 shadow-xs'
        : 'border-[var(--border)] bg-[var(--surface-secondary)]/40'
    }`}>
      <button
        onClick={() => setUserToggled(!isExpanded)}
        className="w-full px-3 py-2 flex items-center justify-between gap-2 text-left hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
        aria-expanded={isExpanded}
        aria-label={isStreaming ? 'Live reasoning trace (streaming)' : `Reasoning trace (${formattedDuration}s)`}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <Brain className={`w-3.5 h-3.5 flex-shrink-0 ${isStreaming ? 'text-[var(--accent)] animate-pulse' : 'text-[var(--accent)]'}`} aria-hidden="true" />
          {isStreaming ? (
            <span className="font-semibold text-[var(--accent)] flex-shrink-0 flex items-center gap-1.5">
              <span>Thinking...</span>
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-ping" />
            </span>
          ) : (
            <span className="font-medium text-[var(--text-secondary)] flex-shrink-0">
              Thought for {formattedDuration}s
            </span>
          )}
          <span className="text-[var(--text-subtle)] truncate text-[11px]">
            — {item.summary}
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-[var(--text-subtle)] flex-shrink-0">
          {isStreaming ? (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-[var(--accent)]/15 text-[var(--accent)] border border-[var(--accent)]/30 animate-pulse">
              <Sparkles className="w-2.5 h-2.5" />
              Live
            </span>
          ) : (
            <>
              <Clock className="w-3 h-3" />
              <span className="text-[10px] font-mono">{formattedDuration}s</span>
            </>
          )}
          {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </div>
      </button>

      {isExpanded && (
        <div
          ref={contentRef}
          className="p-2.5 sm:p-3 border-t border-[var(--border)] bg-[var(--surface-primary)] text-xs font-mono text-[var(--text-secondary)] whitespace-pre-wrap break-words overflow-y-auto max-h-64 max-w-full leading-relaxed scroll-smooth"
        >
          {item.rawTrace || item.summary}
          {isStreaming && (
            <span
              className="inline-block w-1.5 h-3.5 bg-[var(--accent)] animate-pulse ml-0.5 align-middle"
              aria-hidden="true"
            />
          )}
        </div>
      )}
    </div>
  )
}
