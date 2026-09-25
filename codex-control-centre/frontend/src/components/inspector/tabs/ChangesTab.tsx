import React from 'react'
import { FileDiff, FileCode2, ArrowRight } from 'lucide-react'
import { useWorkbenchStore } from '../../../store/useWorkbenchStore'
import { Button } from '../../ui/button'
import { Badge } from '../../ui/badge'

export const ChangesTab: React.FC = () => {
  const { state, setDiffStudioOpen, selectDiffFile } = useWorkbenchStore()

  const totalAdditions = state.diffFiles.reduce((acc, f) => acc + f.additions, 0)
  const totalDeletions = state.diffFiles.reduce((acc, f) => acc + f.deletions, 0)

  if (state.diffFiles.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-[var(--text-subtle)]">
        <FileDiff className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="font-medium text-[var(--text-secondary)]">No modified files</p>
        <p className="text-[11px] mt-1">Proposed code modifications will appear here.</p>
      </div>
    )
  }

  return (
    <div className="p-3 space-y-3 text-xs">
      {/* Overview header */}
      <div className="p-3 rounded-lg bg-[var(--surface-secondary)]/50 border border-[var(--border)] space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">
            {state.diffFiles.length} Changed Files
          </h3>
          <div className="flex items-center gap-2 font-mono text-[11px]">
            <span className="text-[var(--success)] font-medium">+{totalAdditions}</span>
            <span className="text-[var(--danger)] font-medium">-{totalDeletions}</span>
          </div>
        </div>

        <Button
          size="sm"
          className="w-full h-8 text-xs gap-1.5 bg-[var(--accent)] text-[var(--accent-foreground)] hover:bg-[var(--accent-hover)] font-semibold"
          onClick={() => setDiffStudioOpen(true)}
        >
          <FileCode2 className="w-3.5 h-3.5" />
          Launch Full Diff Review Studio
        </Button>
      </div>

      {/* File list */}
      <div className="space-y-1.5">
        {state.diffFiles.map((file, idx) => (
          <button
            key={file.path}
            type="button"
            onClick={() => selectDiffFile(idx)}
            className="w-full text-left p-2.5 rounded-md border border-[var(--border)] bg-[var(--surface-primary)] hover:bg-[var(--surface-hover)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] cursor-pointer transition-colors space-y-1 block"
            aria-label={`Inspect changes in ${file.path}`}
          >
            <div className="flex items-center justify-between gap-1">
              <span className="font-mono text-xs font-medium text-[var(--text-primary)] truncate">
                {file.path}
              </span>
              <Badge
                variant={file.status === 'added' ? 'success' : 'default'}
                className="text-[9px] py-0 px-1 capitalize"
              >
                {file.status}
              </Badge>
            </div>

            <div className="flex items-center justify-between text-[11px] text-[var(--text-subtle)] font-mono">
              <div className="flex items-center gap-2">
                <span className="text-[var(--success)]">+{file.additions}</span>
                <span className="text-[var(--danger)]">-{file.deletions}</span>
              </div>
              <span className="text-[10px] text-[var(--accent)] flex items-center gap-0.5 font-medium">
                Inspect <ArrowRight className="w-2.5 h-2.5" />
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
