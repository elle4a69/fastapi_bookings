import React from 'react'
import { FileDiff, FileCode2, ArrowRight } from 'lucide-react'
import type { FileChangeItem as FileChangeItemType } from '../../../types/workbench'
import { useWorkbenchStore } from '../../../store/useWorkbenchStore'
import { Button } from '../../ui/button'
import { Badge } from '../../ui/badge'

interface Props {
  item: FileChangeItemType
}

export const FileChangeItem: React.FC<Props> = ({ item }) => {
  const { setDiffStudioOpen, selectDiffFile } = useWorkbenchStore()

  return (
    <div className="my-3 max-w-4xl mx-auto border border-[var(--border)] rounded-lg bg-[var(--surface-primary)] p-3.5 shadow-xs text-xs">
      <div className="flex items-center justify-between gap-2 pb-2 mb-2 border-b border-[var(--border)]">
        <div className="flex items-center gap-2 min-w-0">
          <FileDiff className="w-4 h-4 text-[var(--accent)] flex-shrink-0" aria-hidden="true" />
          <h3 className="font-semibold text-xs text-[var(--text-primary)] truncate m-0">
            {item.summary || 'Proposed File Modifications'}
          </h3>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-[var(--success)] font-medium">
            +{item.totalAdditions}
          </span>
          <span className="text-[11px] font-mono text-[var(--danger)] font-medium">
            -{item.totalDeletions}
          </span>

          <Button
            size="sm"
            variant="outline"
            className="h-6 px-2 text-[11px] gap-1 text-[var(--accent)] border-[var(--accent)]/30 hover:bg-[var(--accent-subtle)]"
            onClick={() => setDiffStudioOpen(true)}
            aria-label="Open Diff Review Studio"
          >
            <FileCode2 className="w-3 h-3" />
            Open Diff Review
          </Button>
        </div>
      </div>

      <div className="space-y-1">
        {item.files.map((file, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => selectDiffFile(idx)}
            aria-label={`Inspect diff for ${file.path}`}
            className="w-full flex items-center justify-between p-1.5 rounded hover:bg-[var(--surface-secondary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] cursor-pointer transition-colors text-left"
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="font-mono text-xs text-[var(--text-primary)] truncate">
                {file.path}
              </span>
              {file.requiresApproval && (
                <Badge variant="warning" className="text-[9px] py-0 px-1">
                  Requires Approval
                </Badge>
              )}
            </div>

            <div className="flex items-center gap-2 text-[11px] font-mono">
              <span className="text-[var(--success)]">+{file.additions}</span>
              <span className="text-[var(--danger)]">-{file.deletions}</span>
              <ArrowRight className="w-3 h-3 text-[var(--text-subtle)]" aria-hidden="true" />
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
