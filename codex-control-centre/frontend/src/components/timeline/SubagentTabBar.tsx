import React from 'react'
import { Crown, Bot, Loader2, CheckCircle2, AlertCircle, Clock, Square } from 'lucide-react'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import type { SubAgent } from '../../types/workbench'

export const SubagentTabBar: React.FC = () => {
  const { activeThread, activeSubAgents, state, setActiveAgentId } = useWorkbenchStore()

  if (!activeThread) {
    return null
  }

  const activeAgentId = state.activeAgentId || 'main'
  const isStreaming = state.isStreaming

  // Status badge renderer for tabs
  const renderStatusBadge = (status: string, isRunning?: boolean) => {
    if (isRunning || status === 'running') {
      return (
        <span
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30"
          aria-label="Status: running"
        >
          <Loader2 className="w-2.5 h-2.5 animate-spin" aria-hidden="true" />
          Running
        </span>
      )
    }
    if (status === 'waiting_approval' || status === 'needs_approval' || status === 'waiting') {
      return (
        <span
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-yellow-500/15 text-yellow-400 border border-yellow-500/30"
          aria-label="Status: waiting approval"
        >
          <Clock className="w-2.5 h-2.5" aria-hidden="true" />
          Waiting Approval
        </span>
      )
    }
    if (status === 'completed') {
      return (
        <span
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
          aria-label="Status: completed"
        >
          <CheckCircle2 className="w-2.5 h-2.5" aria-hidden="true" />
          Completed
        </span>
      )
    }
    if (status === 'failed') {
      return (
        <span
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-500/15 text-rose-400 border border-rose-500/30"
          aria-label="Status: failed"
        >
          <AlertCircle className="w-2.5 h-2.5" aria-hidden="true" />
          Failed
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-zinc-500/15 text-zinc-400 border border-zinc-500/30">
        <Square className="w-2 h-2" aria-hidden="true" />
        {status}
      </span>
    )
  }

  // Determine main orchestrator status
  const mainStatus = activeThread.status === 'needs_approval'
    ? 'waiting_approval'
    : (isStreaming ? 'running' : (activeThread.status === 'failed' ? 'failed' : 'completed'))

  return (
    <div
      role="tablist"
      aria-label="Subagent Switcher and Execution Tab Strip"
      className="flex items-center gap-1.5 px-3 sm:px-4 pt-2 pb-0 border-b border-[var(--border)] bg-[var(--surface-secondary)]/60 backdrop-blur-xs overflow-x-auto scrollbar-none flex-shrink-0 z-10 w-full max-w-full"
    >
      {/* 👑 Main Orchestrator Tab */}
      <button
        type="button"
        role="tab"
        id="tab-main-orchestrator"
        aria-selected={activeAgentId === 'main'}
        aria-controls="timeline-feed"
        onClick={() => setActiveAgentId('main')}
        className={`min-h-[40px] px-3.5 py-1.5 rounded-t-md text-xs flex items-center gap-2 border-b-2 transition-all cursor-pointer select-none whitespace-nowrap focus:outline-none focus:ring-2 focus:ring-[var(--accent)] ${
          activeAgentId === 'main'
            ? 'bg-[var(--surface-primary)] text-[var(--text-primary)] border-[var(--accent)] font-semibold shadow-xs'
            : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] border-transparent font-medium'
        }`}
      >
        <Crown className={`w-3.5 h-3.5 ${activeAgentId === 'main' ? 'text-amber-400' : 'text-[var(--text-subtle)]'}`} aria-hidden="true" />
        <span>Main Orchestrator</span>
        {renderStatusBadge(mainStatus, isStreaming && activeAgentId === 'main')}
      </button>

      {/* Child Subagents Tabs */}
      {activeSubAgents.map((subagent: SubAgent) => {
        const isSelected = activeAgentId === subagent.id
        return (
          <button
            key={subagent.id}
            type="button"
            role="tab"
            id={`tab-subagent-${subagent.id}`}
            aria-selected={isSelected}
            aria-controls="timeline-feed"
            onClick={() => setActiveAgentId(subagent.id)}
            className={`min-h-[40px] px-3.5 py-1.5 rounded-t-md text-xs flex items-center gap-2 border-b-2 transition-all cursor-pointer select-none whitespace-nowrap focus:outline-none focus:ring-2 focus:ring-[var(--accent)] ${
              isSelected
                ? 'bg-[var(--surface-primary)] text-[var(--text-primary)] border-[var(--accent)] font-semibold shadow-xs'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] border-transparent font-medium'
            }`}
          >
            <Bot className={`w-3.5 h-3.5 ${isSelected ? 'text-[var(--accent)]' : 'text-[var(--text-subtle)]'}`} aria-hidden="true" />
            <span className="truncate max-w-[160px] sm:max-w-[220px]">
              Subagent: {subagent.role}
            </span>
            {renderStatusBadge(subagent.status, subagent.status === 'running')}
          </button>
        )
      })}
    </div>
  )
}
