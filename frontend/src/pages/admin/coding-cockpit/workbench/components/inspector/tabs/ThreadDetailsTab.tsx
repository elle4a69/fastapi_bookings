import React from 'react'
import { Copy, Check } from 'lucide-react'
import { useWorkbenchStore } from '../../../store/useWorkbenchStore'
import { Badge } from '../../ui/badge'

export const ThreadDetailsTab: React.FC = () => {
  const { activeThread, activeProject } = useWorkbenchStore()
  const [copied, setCopied] = React.useState(false)

  if (!activeThread) {
    return <div className="p-4 text-xs text-[var(--text-subtle)]">No active thread</div>
  }

  const handleCopyId = () => {
    navigator.clipboard.writeText(activeThread.id)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="p-3 space-y-3 text-xs">
      <div className="border border-[var(--border)] rounded-md bg-[var(--surface-primary)] p-3 space-y-2.5">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">Thread Identifiers</h3>
          <button
            onClick={handleCopyId}
            aria-label="Copy Thread ID"
            className="flex items-center gap-1 text-[10px] text-[var(--accent)] hover:underline font-mono focus:outline-none focus:ring-2 focus:ring-[var(--accent)] rounded px-1"
          >
            {copied ? <Check className="w-3 h-3 text-[var(--success)]" /> : <Copy className="w-3 h-3" />}
            Copy ID
          </button>
        </div>

        <div className="space-y-1.5 font-mono text-[11px]">
          <div>
            <span className="text-[var(--text-subtle)]">Thread ID:</span>{' '}
            <span className="text-[var(--text-primary)]">{activeThread.id}</span>
          </div>
          <div>
            <span className="text-[var(--text-subtle)]">Project:</span>{' '}
            <span className="text-[var(--text-primary)]">{activeProject?.name}</span>
          </div>
          <div>
            <span className="text-[var(--text-subtle)]">Module:</span>{' '}
            <span className="text-[var(--text-primary)]">{activeThread.module}</span>
          </div>
          <div>
            <span className="text-[var(--text-subtle)]">Worktree:</span>{' '}
            <span className="text-[var(--text-primary)]">{activeThread.worktree || activeThread.branch}</span>
          </div>
        </div>
      </div>

      <div className="border border-[var(--border)] rounded-md bg-[var(--surface-primary)] p-3 space-y-2">
        <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">Model & Policy</h3>
        <div className="space-y-1.5 text-xs text-[var(--text-secondary)]">
          <div className="flex items-center justify-between">
            <span>Engineering Model:</span>
            <Badge variant="default" className="text-[10px]">{activeThread.model}</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span>Reasoning Effort:</span>
            <span className="font-medium text-[var(--text-primary)] capitalize">{activeThread.reasoningEffort}</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Permission Profile:</span>
            <Badge variant="secondary" className="text-[10px]">{activeThread.permissionProfile.replace('_', ' ')}</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span>Compaction State:</span>
            <span className="font-medium text-[var(--text-primary)] capitalize">{activeThread.contextCompactionState}</span>
          </div>
        </div>
      </div>

      {activeThread.goals && (
        <div className="border border-[var(--border)] rounded-md bg-[var(--surface-primary)] p-3 space-y-1">
          <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">Objective Goal</h3>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            {activeThread.goals}
          </p>
        </div>
      )}
    </div>
  )
}
