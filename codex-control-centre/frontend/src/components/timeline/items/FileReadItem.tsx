import React from 'react'
import { FileSearch } from 'lucide-react'
import type { FileReadItem as FileReadItemType } from '../../../types/workbench'

interface Props {
  item: FileReadItemType
}

export const FileReadItem: React.FC<Props> = ({ item }) => {
  return (
    <div className="my-1.5 max-w-4xl mx-auto flex items-center justify-between gap-2 px-3 py-1.5 rounded bg-[var(--surface-secondary)]/30 border border-[var(--border)] text-xs text-[var(--text-secondary)]">
      <div className="flex items-center gap-2 min-w-0">
        <FileSearch className="w-3.5 h-3.5 text-[var(--accent)] flex-shrink-0" />
        <span className="font-mono text-xs text-[var(--text-primary)] truncate">{item.path}</span>
        {item.lineRange && (
          <span className="text-[10px] text-[var(--text-subtle)] font-mono">({item.lineRange})</span>
        )}
      </div>

      <div className="text-[11px] text-[var(--text-subtle)] truncate max-w-xs">
        {item.summary}
      </div>
    </div>
  )
}
