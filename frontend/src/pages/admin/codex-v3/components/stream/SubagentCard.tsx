import React from 'react'
import {
  Bot,
  ExternalLink,
  Clock,
  Activity,
  CheckCircle2,
  XCircle,
  Loader2
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SubagentActivity } from '../../types'

export interface SubagentCardProps {
  subagent?: SubagentActivity
  role?: string
  status?: 'running' | 'completed' | 'failed' | 'idle' | 'pending'
  elapsedSeconds?: number
  currentAction?: string
  childThreadId?: string
  toolsCount?: number
  onViewThread?: (threadId: string) => void
  className?: string
}

export const SubagentCard: React.FC<SubagentCardProps> = ({
  subagent,
  role: propRole,
  status: propStatus,
  elapsedSeconds: propElapsedSeconds,
  currentAction: propCurrentAction,
  childThreadId: propChildThreadId,
  toolsCount: propToolsCount,
  onViewThread,
  className,
}) => {
  const role = subagent?.role ?? propRole ?? 'Subagent Worker'
  const status = subagent?.status ?? propStatus ?? 'running'
  const elapsed = subagent?.elapsedSeconds ?? subagent?.elapsedSec ?? propElapsedSeconds
  const currentAction =
    subagent?.currentAction ?? subagent?.task ?? propCurrentAction ?? 'Processing task...'
  const childThreadId = subagent?.childThreadId ?? propChildThreadId ?? subagent?.id
  const toolsCount = subagent?.toolsCount ?? propToolsCount

  const formatElapsed = (sec?: number) => {
    if (typeof sec !== 'number') return null
    if (sec < 60) return `${Math.round(sec)}s`
    const mins = Math.floor(sec / 60)
    const remSec = Math.round(sec % 60)
    return `${mins}m ${remSec}s`
  }

  const renderBadge = () => {
    switch (status) {
      case 'running':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
            <Loader2 className="w-3 h-3 animate-spin" />
            Active
          </span>
        )
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" />
            Done
          </span>
        )
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/10 text-rose-500 border border-rose-500/20">
            <XCircle className="w-3 h-3" />
            Failed
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-muted text-muted-foreground">
            {status}
          </span>
        )
    }
  }

  return (
    <div
      className={cn(
        'rounded-xl border border-border/70 bg-linear-to-r from-card/80 via-card/50 to-muted/20 backdrop-blur-xs p-3.5 shadow-xs transition-all',
        status === 'running' && 'border-indigo-500/30 ring-1 ring-indigo-500/10 shadow-indigo-500/5',
        className
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Subagent Meta & Role */}
        <div className="flex items-start sm:items-center gap-3 min-w-0">
          <div className="relative shrink-0 mt-0.5 sm:mt-0">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-500">
              <Bot className="w-4 h-4" />
            </div>
            {status === 'running' && (
              <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500" />
              </span>
            )}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold text-foreground tracking-tight">
                {role}
              </span>
              {renderBadge()}
              {typeof toolsCount === 'number' && toolsCount > 0 && (
                <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded font-mono">
                  {toolsCount} tools
                </span>
              )}
            </div>

            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-0.5">
              <Activity className="w-3 h-3 text-indigo-400 shrink-0" />
              <span className="truncate font-mono text-[11px] text-foreground/80">
                {currentAction}
              </span>
            </div>
          </div>
        </div>

        {/* Actions & Timing */}
        <div className="flex items-center justify-between sm:justify-end gap-3 pt-2 sm:pt-0 border-t sm:border-t-0 border-border/40">
          {typeof elapsed === 'number' && (
            <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground font-mono">
              <Clock className="w-3 h-3" />
              {formatElapsed(elapsed)}
            </span>
          )}

          {childThreadId && (
            <button
              type="button"
              onClick={() => onViewThread?.(childThreadId)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-foreground bg-muted hover:bg-muted/80 active:scale-95 transition-all focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring cursor-pointer"
            >
              <span>View Thread</span>
              <ExternalLink className="w-3.5 h-3.5 text-muted-foreground" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
export default SubagentCard
