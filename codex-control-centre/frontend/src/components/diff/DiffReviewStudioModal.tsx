import React, { useState } from 'react'
import { 
  FileCode2, 
  Check, 
  X, 
  ShieldCheck, 
  CheckCircle2, 
  ArrowLeft, 
  ArrowRight, 
  FlaskConical 
} from 'lucide-react'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { DiffViewer } from './DiffViewer'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '../ui/dialog'
import { Button } from '../ui/button'
import { cn } from '../../lib/utils'

export const DiffReviewStudioModal: React.FC = () => {
  const { 
    state, 
    setDiffStudioOpen, 
    selectDiffFile,
    recordDiffVerdict
  } = useWorkbenchStore()

  const [approvedVerdict, setApprovedVerdict] = useState<string | null>(null)
  const currentFile = state.diffFiles[state.selectedDiffFileIndex] || state.diffFiles[0]

  if (!state.isDiffStudioOpen) return null

  const handleApplyVerdict = (verdict: string) => {
    setApprovedVerdict(verdict)
    recordDiffVerdict(verdict)
  }

  if (state.diffFiles.length === 0 || !currentFile) {
    return (
      <Dialog open={state.isDiffStudioOpen} onOpenChange={setDiffStudioOpen}>
        <DialogContent className="max-w-md p-6 text-center bg-[var(--surface-primary)] border-[var(--border-strong)] shadow-2xl rounded-xl">
          <DialogTitle className="sr-only">Workspace Clean</DialogTitle>
          <div className="w-10 h-10 rounded-xl bg-[var(--surface-secondary)] mx-auto flex items-center justify-center text-[var(--text-subtle)] mb-3">
            <FileCode2 className="w-5 h-5" aria-hidden="true" />
          </div>
          <h2 className="font-semibold text-sm text-[var(--text-primary)] m-0">
            Workspace Clean
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-1.5 leading-relaxed">
            No uncommitted file modifications or worktree diffs found in the active workspace.
          </p>
          <div className="mt-4 flex justify-center">
            <Button size="sm" variant="secondary" onClick={() => setDiffStudioOpen(false)}>
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  const handlePrev = () => {
    selectDiffFile((state.selectedDiffFileIndex - 1 + state.diffFiles.length) % state.diffFiles.length)
  }

  const handleNext = () => {
    selectDiffFile((state.selectedDiffFileIndex + 1) % state.diffFiles.length)
  }

  return (
    <Dialog open={state.isDiffStudioOpen} onOpenChange={setDiffStudioOpen}>
      <DialogContent className="max-w-7xl h-[92vh] p-0 overflow-hidden flex flex-col bg-[var(--surface-primary)] border-[var(--border-strong)] shadow-2xl rounded-xl">
        <DialogTitle className="sr-only">Engineering Diff Review Studio</DialogTitle>
        <DialogDescription className="sr-only">
          Reviewing {state.diffFiles.length} modified files before branch merge
        </DialogDescription>
        
        {/* Top Review Studio Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] bg-[var(--surface-primary)] flex-shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-[var(--accent-subtle)] text-[var(--accent)] flex items-center justify-center" aria-hidden="true">
              <FileCode2 className="w-4 h-4" />
            </div>
            <div>
              <h2 className="font-semibold text-xs text-[var(--text-primary)] m-0">
                Engineering Diff Review Studio
              </h2>
              <div className="text-[10px] text-[var(--text-subtle)]">
                Reviewing {state.diffFiles.length} modified files before branch merge
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={handlePrev} aria-label="Previous file diff">
                <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Prev File
              </Button>
              <span className="text-[11px] font-mono text-[var(--text-subtle)]">
                {state.selectedDiffFileIndex + 1} / {state.diffFiles.length}
              </span>
              <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={handleNext} aria-label="Next file diff">
                Next File <ArrowRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>

            <button
              onClick={() => setDiffStudioOpen(false)}
              className="p-1 rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] ml-2"
              aria-label="Close Diff Studio"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Main 3-Pane Body */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
          {/* Left Pane: File Tree List */}
          <div className="w-full md:w-64 border-b md:border-b-0 md:border-r border-[var(--border)] bg-[var(--surface-secondary)]/30 p-2 overflow-y-auto max-h-40 md:max-h-none flex-shrink-0 space-y-1">
            <h3 className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-subtle)] m-0">
              Modified Files ({state.diffFiles.length})
            </h3>

            {state.diffFiles.map((file, idx) => {
              const isSelected = idx === state.selectedDiffFileIndex
              return (
                <button
                  key={file.path}
                  type="button"
                  onClick={() => selectDiffFile(idx)}
                  aria-label={`Review diff for ${file.path}`}
                  className={cn(
                    'w-full text-left p-2 rounded-md cursor-pointer transition-colors text-xs font-mono space-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] block',
                    isSelected
                      ? 'bg-[var(--surface-primary)] border border-[var(--accent)] shadow-2xs text-[var(--text-primary)] font-semibold'
                      : 'hover:bg-[var(--surface-hover)] text-[var(--text-secondary)] border border-transparent'
                  )}
                >
                  <div className="truncate font-medium">{file.path}</div>
                  <div className="flex items-center justify-between text-[10px] text-[var(--text-subtle)]">
                    <span className="capitalize">{file.status}</span>
                    <div className="flex items-center gap-1 font-mono">
                      <span className="text-[var(--success)]">+{file.additions}</span>
                      <span className="text-[var(--danger)]">-{file.deletions}</span>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>

          {/* Centre Pane: Diff Viewer */}
          <div className="flex-1 p-3 overflow-hidden flex flex-col min-h-60">
            <DiffViewer file={currentFile} />
          </div>

          {/* Right Pane: Review Summary & Verdict Checklist */}
          <div className="w-full md:w-80 border-t md:border-t-0 md:border-l border-[var(--border)] bg-[var(--surface-primary)] p-4 overflow-y-auto flex-shrink-0 flex flex-col justify-between text-xs space-y-4">
            <div className="space-y-3">
              <h3 className="font-semibold text-xs text-[var(--text-primary)] pb-1 border-b border-[var(--border)] m-0">
                Review Verdict & Invariants
              </h3>

              {/* Invariant Verification Checklist */}
              <div className="space-y-2">
                <div className="flex items-start gap-2 p-2 rounded bg-[var(--surface-secondary)]/50">
                  <CheckCircle2 className="w-4 h-4 text-[var(--success)] flex-shrink-0 mt-0.5" aria-hidden="true" />
                  <div>
                    <h4 className="font-semibold text-xs text-[var(--text-primary)] m-0">Concurrency Locking</h4>
                    <div className="text-[11px] text-[var(--text-secondary)] mt-0.5">Acquires row-level read lock with 60s lease.</div>
                  </div>
                </div>

                <div className="flex items-start gap-2 p-2 rounded bg-[var(--surface-secondary)]/50">
                  <FlaskConical className="w-4 h-4 text-[var(--success)] flex-shrink-0 mt-0.5" aria-hidden="true" />
                  <div>
                    <h4 className="font-semibold text-xs text-[var(--text-primary)] m-0">Regression Coverage</h4>
                    <div className="text-[11px] text-[var(--text-secondary)] mt-0.5">2 targeted pytest unit tests pass cleanly.</div>
                  </div>
                </div>

                <div className="flex items-start gap-2 p-2 rounded bg-[var(--surface-secondary)]/50">
                  <ShieldCheck className="w-4 h-4 text-[var(--success)] flex-shrink-0 mt-0.5" aria-hidden="true" />
                  <div>
                    <h4 className="font-semibold text-xs text-[var(--text-primary)] m-0">Zero Secrets / Leaks</h4>
                    <div className="text-[11px] text-[var(--text-secondary)] mt-0.5">Verified no hardcoded keys or SMS customer PII.</div>
                  </div>
                </div>
              </div>

              {/* Status Notice if already reviewed */}
              {approvedVerdict && (
                <div className="p-3 rounded-md bg-[var(--success-subtle)] border border-[var(--success)] text-xs text-[var(--success)] font-medium">
                  Verdict recorded: {approvedVerdict}
                </div>
              )}
            </div>

            {/* Bottom Actions */}
            <div className="space-y-2 pt-3 border-t border-[var(--border)]">
              <Button
                className="w-full h-9 text-xs gap-1.5 bg-[var(--success)] text-white hover:opacity-90 font-semibold"
                onClick={() => handleApplyVerdict('Changes Approved for Apply')}
              >
                <Check className="w-4 h-4" />
                Approve All Changes
              </Button>

              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={() => handleApplyVerdict('Correction Requested from Codex')}
                >
                  Request Correction
                </Button>

                <Button
                  variant="dangerOutline"
                  size="sm"
                  className="text-xs"
                  onClick={() => handleApplyVerdict('Changes Declined')}
                >
                  Decline
                </Button>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
