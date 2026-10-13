import React from 'react'
import { 
  AlertTriangle, 
  Check, 
  X, 
  Terminal, 
  FileEdit, 
  Globe, 
  KeyRound, 
  CheckCircle2, 
  XCircle 
} from 'lucide-react'
import type { ApprovalRequestItem as ApprovalRequestItemType } from '../../../types/workbench'
import { useWorkbenchStore } from '../../../store/useWorkbenchStore'
import { Button } from '../../ui/button'
import { Badge } from '../../ui/badge'
import { cn } from '../../../lib/utils'

interface Props {
  item: ApprovalRequestItemType
}

export const ApprovalCard: React.FC<Props> = ({ item }) => {
  const { approveRequest, declineRequest } = useWorkbenchStore()
  const [feedback, setFeedback] = React.useState('')
  const [showFeedback, setShowFeedback] = React.useState(false)

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case 'critical':
      case 'high':
        return <Badge variant="danger" className="uppercase font-bold tracking-wider">High Risk</Badge>
      case 'medium':
        return <Badge variant="warning" className="uppercase font-semibold tracking-wider">Medium Risk</Badge>
      default:
        return <Badge variant="secondary" className="uppercase tracking-wider">Low Risk</Badge>
    }
  }

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'command':
        return <Terminal className="w-4 h-4 text-[var(--accent)]" />
      case 'file_write':
        return <FileEdit className="w-4 h-4 text-[var(--warning)]" />
      case 'network':
        return <Globe className="w-4 h-4 text-[var(--accent)]" />
      case 'permission':
        return <KeyRound className="w-4 h-4 text-[var(--danger)]" />
      default:
        return <AlertTriangle className="w-4 h-4 text-[var(--warning)]" />
    }
  }

  const isPending = item.status === 'pending'

  return (
    <div
      className={cn(
        'my-3 sm:my-4 max-w-4xl mx-auto rounded-lg border p-3 sm:p-4 shadow-sm transition-all w-full max-w-full overflow-hidden break-words',
        isPending
          ? item.risk === 'high' || item.risk === 'critical'
            ? 'bg-[var(--danger-subtle)]/30 border-[var(--danger)]'
            : 'bg-[var(--warning-subtle)]/30 border-[var(--warning)]'
          : 'bg-[var(--surface-primary)] border-[var(--border)] opacity-80'
      )}
      role="region"
      aria-label={`Approval Request: ${item.title}`}
    >
      {/* Header */}
      <div className="flex flex-wrap sm:flex-nowrap items-center justify-between gap-2 pb-2.5 border-b border-[var(--border)]">
        <div className="flex items-center gap-2 min-w-0">
          {getCategoryIcon(item.category)}
          <h3 className="font-semibold text-xs text-[var(--text-primary)] truncate">
            Action Approval Required: {item.title}
          </h3>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {getRiskBadge(item.risk)}
          {!isPending && (
            <Badge variant={item.status === 'approved' ? 'success' : 'danger'} className="capitalize">
              {item.status} ({item.scope || 'once'})
            </Badge>
          )}
        </div>
      </div>

      {/* Body: Consequence & Details */}
      <div className="py-3 space-y-2.5 text-xs">
        <div>
          <span className="font-semibold text-[var(--text-primary)]">Potential Consequence: </span>
          <span className="text-[var(--text-secondary)] leading-relaxed break-words">{item.consequence}</span>
        </div>

        {item.command && (
          <div className="p-2 rounded bg-[var(--code-bg)] border border-[var(--code-border)] font-mono text-xs overflow-x-auto max-w-full break-words">
            <div className="text-[10px] text-[var(--text-subtle)] mb-0.5">Command to execute:</div>
            <div className="text-[var(--text-primary)]">$ {item.command}</div>
            {item.workingDirectory && (
              <div className="text-[10px] text-[var(--text-subtle)] mt-1">in {item.workingDirectory}</div>
            )}
          </div>
        )}

        {item.targetPath && (
          <div className="p-2 rounded bg-[var(--code-bg)] border border-[var(--code-border)] font-mono text-xs overflow-x-auto max-w-full break-words">
            <div className="text-[10px] text-[var(--text-subtle)] mb-0.5">Target path:</div>
            <div className="text-[var(--text-primary)]">{item.targetPath}</div>
          </div>
        )}

        <div>
          <span className="font-semibold text-[var(--text-primary)]">Agent Rationale: </span>
          <span className="text-[var(--text-secondary)] break-words">{item.reason}</span>
        </div>

        {/* Optional Feedback Input when Pending */}
        {isPending && (
          <div className="pt-1">
            {!showFeedback ? (
              <button
                type="button"
                onClick={() => setShowFeedback(true)}
                className="text-[10px] text-[var(--accent)] hover:underline font-medium cursor-pointer h-7 flex items-center"
              >
                + Add operator feedback / guidance note
              </button>
            ) : (
              <div className="mt-1 space-y-1">
                <label 
                  htmlFor={`approval-feedback-${item.id}`}
                  className="text-[10px] font-medium text-[var(--text-secondary)]"
                >
                  Feedback note for agent:
                </label>
                <input
                  id={`approval-feedback-${item.id}`}
                  type="text"
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="Optional constraint or reason for decision..."
                  className="w-full h-8 rounded border border-[var(--border)] bg-[var(--surface-primary)] px-2.5 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Actions */}
      {isPending ? (
        <div className="flex flex-wrap sm:flex-nowrap items-center justify-end gap-2 pt-2.5 border-t border-[var(--border)]">
          <Button
            size="sm"
            variant="outline"
            className="h-8 w-full sm:w-auto text-xs text-[var(--danger)] border-[var(--danger)]/40 hover:bg-[var(--danger-subtle)] justify-center"
            onClick={() => declineRequest(item.approvalId, undefined, feedback || undefined)}
          >
            <X className="w-4 h-4 mr-1" />
            Decline
          </Button>

          <Button
            size="sm"
            variant="secondary"
            className="h-8 w-full sm:w-auto text-xs justify-center"
            onClick={() => approveRequest(item.approvalId, 'session', undefined, feedback || undefined)}
          >
            Approve for Session
          </Button>

          <Button
            size="sm"
            variant={item.risk === 'high' ? 'danger' : 'default'}
            className="h-8 w-full sm:w-auto text-xs justify-center font-medium"
            onClick={() => approveRequest(item.approvalId, 'once', undefined, feedback || undefined)}
          >
            <Check className="w-4 h-4 mr-1" />
            Approve Once
          </Button>
        </div>
      ) : (
        <div className="flex items-center gap-1.5 pt-2 text-xs font-medium text-[var(--text-subtle)]">
          {item.status === 'approved' ? (
            <CheckCircle2 className="w-4 h-4 text-[var(--success)]" />
          ) : (
            <XCircle className="w-4 h-4 text-[var(--danger)]" />
          )}
          <span>Request has been {item.status} by the operator.</span>
        </div>
      )}
    </div>
  )
}
