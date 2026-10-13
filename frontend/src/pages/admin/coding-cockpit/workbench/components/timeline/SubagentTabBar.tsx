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
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30 shrink-0"
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
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-yellow-500/15 text-yellow-400 border border-yellow-500/30 shrink-0"
          aria-label="Status: waiting approval"
        >
          <Clock className="w-2.5 h-2.5" aria-hidden="true" />
          Wait Approval
        </span>
      )
    }
    if (status === 'completed') {
      return (
        <span
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shrink-0"
          aria-label="Status: completed"
        >
          <CheckCircle2 className="w-2.5 h-2.5" aria-hidden="true" />
          Done
        </span>
      )
    }
    if (status === 'failed') {
      return (
        <span
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-500/15 text-rose-400 border border-rose-500/30 shrink-0"
          aria-label="Status: failed"
        >
          <AlertCircle className="w-2.5 h-2.5" aria-hidden="true" />
          Failed
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400 border border-slate-700 shrink-0">
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
      className="flex items-center gap-1.5 px-3 sm:px-4 pt-1.5 pb-0 border-b border-slate-800 bg-slate-950/60 backdrop-blur-xs overflow-x-auto scrollbar-none shrink-0 z-10 w-full max-w-full select-none"
    >
      {/* 👑 Main Orchestrator Tab */}
      <button
        type="button"
        role="tab"
        id="tab-main-orchestrator"
        aria-selected={activeAgentId === 'main'}
        aria-controls="timeline-feed"
        onClick={() => setActiveAgentId('main')}
        className={`min-h-[40px] px-3.5 py-1.5 rounded-t-md text-xs flex items-center gap-2 border-b-2 transition-all cursor-pointer whitespace-nowrap focus:outline-none focus:ring-1 focus:ring-indigo-500 shrink-0 ${
          activeAgentId === 'main'
            ? 'bg-slate-900 text-slate-100 border-indigo-500 font-semibold shadow-xs'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/40 border-transparent font-medium'
        }`}
      >
        <Crown
          className={`w-3.5 h-3.5 shrink-0 ${activeAgentId === 'main' ? 'text-amber-400' : 'text-slate-500'}`}
          aria-hidden="true"
        />
        <span>👑 Main Agent</span>
        {renderStatusBadge(mainStatus, isStreaming && activeAgentId === 'main')}
      </button>

      {/* Child Subagents Tabs */}
      {activeSubAgents.map((sa: SubAgent) => {
        const isTabSelected = activeAgentId === sa.id

        return (
          <button
            key={sa.id}
            type="button"
            role="tab"
            id={`tab-subagent-${sa.id}`}
            aria-selected={isTabSelected}
            aria-controls="timeline-feed"
            onClick={() => setActiveAgentId(sa.id)}
            className={`min-h-[40px] px-3.5 py-1.5 rounded-t-md text-xs flex items-center gap-2 border-b-2 transition-all cursor-pointer whitespace-nowrap focus:outline-none focus:ring-1 focus:ring-indigo-500 shrink-0 ${
              isTabSelected
                ? 'bg-slate-900 text-slate-100 border-indigo-500 font-semibold shadow-xs'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/40 border-transparent font-medium'
            }`}
          >
            <Bot
              className={`w-3.5 h-3.5 shrink-0 ${isTabSelected ? 'text-indigo-400' : 'text-slate-500'}`}
              aria-hidden="true"
            />
            <span className="truncate max-w-[150px]">{sa.role || (sa as any).name || 'Subagent'}</span>
            {renderStatusBadge(sa.status)}
          </button>
        )
      })}
    </div>
  )
}
export default SubagentTabBar
