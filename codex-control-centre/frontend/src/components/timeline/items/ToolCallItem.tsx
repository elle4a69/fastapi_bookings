import React, { useState } from 'react'
import { Wrench, ChevronDown, ChevronRight } from 'lucide-react'
import type { ToolCallItem as ToolCallItemType } from '../../../types/workbench'
import { Badge } from '../../ui/badge'

interface Props {
  item: ToolCallItemType
}

export const ToolCallItem: React.FC<Props> = ({ item }) => {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className="my-1.5 max-w-4xl mx-auto border border-[var(--border)] rounded-md bg-[var(--surface-primary)] overflow-hidden text-xs">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-1.5 flex items-center justify-between gap-2 bg-[var(--surface-secondary)]/40 hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none text-left"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <Wrench className="w-3.5 h-3.5 text-[var(--accent)] flex-shrink-0" />
          <span className="font-mono font-medium text-xs text-[var(--text-primary)] truncate">
            {item.serverName} / {item.toolName}
          </span>
          <span className="text-[11px] text-[var(--text-subtle)] truncate">— {item.resultSummary}</span>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <Badge
            variant={item.status === 'success' ? 'success' : item.status === 'failed' ? 'danger' : 'default'}
            className="text-[9px] py-0 px-1"
          >
            {item.status}
          </Badge>
          {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </div>
      </button>

      {isExpanded && (
        <div className="p-3 border-t border-[var(--border)] bg-[var(--code-bg)] text-xs font-mono">
          <div className="text-[10px] text-[var(--text-subtle)] mb-1 uppercase font-semibold">Tool Arguments:</div>
          <pre className="text-[var(--text-primary)] whitespace-pre-wrap">{JSON.stringify(item.args, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
