import React from 'react'
import { CheckCircle2, FileCode2, FlaskConical, Clock } from 'lucide-react'
import type { CompletionSummaryItem as CompletionSummaryItemType } from '../../../types/workbench'

interface Props {
  item: CompletionSummaryItemType
}

export const CompletionSummaryItem: React.FC<Props> = ({ item }) => {
  return (
    <div className="my-4 max-w-4xl mx-auto border border-[var(--success)] rounded-lg bg-[var(--success-subtle)]/20 p-4 shadow-xs text-xs space-y-2.5">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="w-5 h-5 text-[var(--success)] flex-shrink-0" />
        <h3 className="font-semibold text-xs text-[var(--text-primary)]">
          {item.outcome}
        </h3>
      </div>

      <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
        {item.summary}
      </p>

      <div className="flex items-center gap-4 pt-2 border-t border-[var(--border)] text-[11px] font-mono text-[var(--text-secondary)]">
        <span className="flex items-center gap-1">
          <FileCode2 className="w-3.5 h-3.5 text-[var(--accent)]" /> {item.changedFilesCount} files changed
        </span>
        <span className="flex items-center gap-1">
          <FlaskConical className="w-3.5 h-3.5 text-[var(--success)]" /> {item.testsPassedCount} tests passing
        </span>
        <span className="flex items-center gap-1">
          <Clock className="w-3.5 h-3.5 text-[var(--text-subtle)]" /> {item.durationSeconds}s duration
        </span>
      </div>
    </div>
  )
}
