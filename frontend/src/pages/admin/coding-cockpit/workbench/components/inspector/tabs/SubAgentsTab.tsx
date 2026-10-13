import React from 'react'
import { Users } from 'lucide-react'
import { useWorkbenchStore } from '../../../store/useWorkbenchStore'
import { SubAgentCard } from '../../timeline/items/SubAgentCard'

export const SubAgentsTab: React.FC = () => {
  const { activeSubAgents } = useWorkbenchStore()

  const runningCount = activeSubAgents.filter(a => a.status === 'running').length
  const completedCount = activeSubAgents.filter(a => a.status === 'completed').length
  const failedCount = activeSubAgents.filter(a => a.status === 'failed').length

  return (
    <div className="p-3 space-y-3 text-xs">
      {/* Summary metric banner */}
      <div className="p-3 rounded-lg bg-[var(--surface-secondary)]/50 border border-[var(--border)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-[var(--accent)]" />
          <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">
            {activeSubAgents.length} Parallel Sub-agents
          </h3>
        </div>

        <div className="flex items-center gap-2 font-mono text-[10px]">
          <span className="text-[var(--accent)] font-medium">{runningCount} active</span>
          <span>·</span>
          <span className="text-[var(--success)]">{completedCount} done</span>
          {failedCount > 0 && (
            <>
              <span>·</span>
              <span className="text-[var(--danger)]">{failedCount} failed</span>
            </>
          )}
        </div>
      </div>

      {/* List of sub-agent cards */}
      <div className="space-y-2.5">
        {activeSubAgents.map(agent => (
          <SubAgentCard key={agent.id} agent={agent} />
        ))}
      </div>
    </div>
  )
}
