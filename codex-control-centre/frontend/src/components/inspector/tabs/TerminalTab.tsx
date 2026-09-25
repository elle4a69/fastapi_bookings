import React from 'react'
import { Square, RefreshCw } from 'lucide-react'
import { Button } from '../../ui/button'
import { Badge } from '../../ui/badge'
import { useWorkbenchStore } from '../../../store/useWorkbenchStore'

export const TerminalTab: React.FC = () => {
  const { state, activeThread } = useWorkbenchStore()

  // Extract real command executions from active thread items if in live mode
  const realProcesses = React.useMemo(() => {
    if (!activeThread) return []
    const procs: any[] = []
    activeThread.turns.forEach(turn => {
      turn.items.forEach(item => {
        if (item.type === 'command_execution') {
          procs.push({
            id: item.id,
            command: item.command,
            cwd: item.workingDirectory,
            status: item.status || 'completed',
            uptime: `${item.durationMs || 100}ms`,
            pid: item.processId || 8100
          })
        }
      })
    })
    return procs
  }, [activeThread])

  const processes = state.appMode === 'demo' ? [
    {
      id: 'proc_pytest_daemon',
      command: 'pytest --looponfail tests/test_availability.py',
      cwd: 'F:\\Projects\\fastapi_bookings',
      status: 'running',
      uptime: '4m 12s',
      pid: 14209
    },
    {
      id: 'proc_vite_dev',
      command: 'npm run dev -- --port 5180',
      cwd: 'F:\\Projects\\fastapi_bookings\\frontend',
      status: 'running',
      uptime: '18m 45s',
      pid: 8821
    }
  ] : realProcesses

  if (state.appMode === 'live' && processes.length === 0) {
    return (
      <div className="p-3 text-center text-xs text-[var(--text-subtle)] mt-10 space-y-2">
        <p className="font-medium text-[var(--text-secondary)]">No active runner attached</p>
        <p className="text-[11px]">Command and terminal executions will appear here when spawned by Codex.</p>
      </div>
    )
  }

  return (
    <div className="p-3 space-y-3 text-xs">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">
          Active Background Tasks ({processes.length})
        </h3>
        <Button 
          size="sm" 
          variant="ghost" 
          className="h-6 text-[10px] gap-1 text-[var(--text-secondary)]"
          aria-label="Refresh active background tasks"
        >
          <RefreshCw className="w-3 h-3" /> Refresh
        </Button>
      </div>

      <div className="space-y-2">
        {processes.map(proc => (
          <div key={proc.id} className="border border-[var(--border)] rounded-md bg-[var(--surface-primary)] p-3 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <h4 className="font-mono text-xs font-semibold text-[var(--text-primary)] truncate m-0">
                  $ {proc.command}
                </h4>
                <div className="text-[10px] text-[var(--text-subtle)] truncate mt-0.5">
                  PID {proc.pid} · {proc.cwd}
                </div>
              </div>
              <Badge variant="default" className="text-[9px] py-0 px-1 uppercase font-mono animate-pulse">
                {proc.status}
              </Badge>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-[var(--border)] text-[10px] text-[var(--text-subtle)]">
              <span>Uptime: {proc.uptime}</span>
              <Button 
                size="sm" 
                variant="outline" 
                className="h-5 px-1.5 text-[10px] text-[var(--danger)] border-[var(--danger)]/30 hover:bg-[var(--danger-subtle)]"
                aria-label={`Terminate process ${proc.pid} (${proc.command})`}
              >
                <Square className="w-2.5 h-2.5 mr-1 fill-current" /> Terminate
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
