import React from 'react'
import { Sparkles } from 'lucide-react'
import type { CompactionNoticeItem as CompactionNoticeItemType } from '../../../types/workbench'

interface Props {
  item: CompactionNoticeItemType
}

export const CompactionNoticeItem: React.FC<Props> = ({ item }) => {
  return (
    <div className="my-3 max-w-4xl mx-auto flex items-start gap-3 p-3.5 rounded-lg bg-[var(--surface-secondary)]/60 border border-[var(--border)] text-xs text-[var(--text-secondary)]">
      <div className="w-7 h-7 rounded-full bg-[var(--accent-subtle)] text-[var(--accent)] flex items-center justify-center flex-shrink-0">
        <Sparkles className="w-3.5 h-3.5" />
      </div>

      <div className="flex-1 space-y-1">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-xs text-[var(--text-primary)]">
            Context History Compacted
          </span>
          {item.tokensSaved > 0 && (
            <span className="text-[10px] font-mono text-[var(--accent)] font-medium">
              ~{item.tokensSaved.toLocaleString()} tokens reclaimed
            </span>
          )}
        </div>

        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          {item.explanation}
        </p>
      </div>
    </div>
  )
}
