import React from 'react'
import { PauseCircle } from 'lucide-react'
import type { InterruptionItem as InterruptionItemType } from '../../../types/workbench'

interface Props {
  item: InterruptionItemType
}

export const InterruptionItem: React.FC<Props> = ({ item }) => {
  return (
    <div className="my-2 max-w-4xl mx-auto flex items-center justify-between gap-3 p-3 rounded-md bg-[var(--surface-secondary)] border border-[var(--border)] text-xs text-[var(--text-secondary)]">
      <div className="flex items-center gap-2">
        <PauseCircle className="w-4 h-4 text-[var(--warning)] flex-shrink-0" />
        <div>
          <span className="font-semibold text-xs text-[var(--text-primary)]">Turn Interrupted</span>
          <span className="text-[11px] text-[var(--text-secondary)] ml-2">— {item.reason}</span>
        </div>
      </div>

      <div className="text-[10px] text-[var(--text-subtle)] font-mono">
        by {item.interruptedBy}
      </div>
    </div>
  )
}
