import React, { useState } from 'react'
import { 
  Users, 
  CheckCircle2, 
  Clock, 
  Send, 
  Square, 
  ArrowRight, 
  FileCode2, 
  FlaskConical 
} from 'lucide-react'
import type { SubAgent } from '../../../types/workbench'
import { useWorkbenchStore } from '../../../store/useWorkbenchStore'
import { Badge } from '../../ui/badge'
import { Button } from '../../ui/button'
import { Input } from '../../ui/input'

interface Props {
  agent: SubAgent
}

export const SubAgentCard: React.FC<Props> = ({ agent }) => {
  const { steerSubAgent, stopSubAgent, selectThread } = useWorkbenchStore()
  const [steerPrompt, setSteerPrompt] = useState('')
  const [isSteeringOpen, setIsSteeringOpen] = useState(false)

  const getStatusBadge = () => {
    switch (agent.status) {
      case 'completed':
        return <Badge variant="success" className="capitalize text-[10px]">Completed</Badge>
      case 'running':
        return <Badge variant="default" className="capitalize text-[10px] animate-pulse">Running ({agent.elapsedSeconds}s)</Badge>
      case 'failed':
        return <Badge variant="danger" className="capitalize text-[10px]">Failed</Badge>
      case 'stopped':
        return <Badge variant="secondary" className="capitalize text-[10px]">Stopped</Badge>
      default:
        return <Badge variant="secondary" className="capitalize text-[10px]">Waiting</Badge>
    }
  }

  const handleSteer = (e: React.FormEvent) => {
    e.preventDefault()
    if (steerPrompt.trim()) {
      steerSubAgent(agent.id, steerPrompt.trim())
      setSteerPrompt('')
      setIsSteeringOpen(false)
    }
  }

  return (
    <div className="border border-[var(--border)] rounded-lg bg-[var(--surface-primary)] p-3.5 shadow-xs text-xs space-y-2.5">
      {/* Top line: Role & Status */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded bg-[var(--surface-secondary)] border border-[var(--border)] flex items-center justify-center flex-shrink-0 text-[var(--accent)]">
            <Users className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <h4 className="font-semibold text-xs text-[var(--text-primary)] truncate">
              {agent.role}
            </h4>
            <span className="text-[10px] font-mono text-[var(--text-subtle)]">
              {agent.model} · {agent.scope.replace('_', ' ')}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 flex-shrink-0">
          {getStatusBadge()}
        </div>
      </div>

      {/* Objective */}
      <div className="p-2 rounded bg-[var(--surface-secondary)]/50 text-xs text-[var(--text-primary)] leading-relaxed">
        <span className="font-semibold text-[10px] text-[var(--text-subtle)] uppercase block mb-0.5">Objective</span>
        {agent.objective}
      </div>

      {/* Progress & Result */}
      <div className="text-xs text-[var(--text-secondary)] space-y-1">
        <div className="flex items-center gap-1.5">
          <Clock className="w-3 h-3 text-[var(--text-subtle)]" />
          <span><strong>Progress:</strong> {agent.progressSummary}</span>
        </div>

        {agent.resultSummary && (
          <div className="flex items-center gap-1.5 text-[var(--success)] font-medium">
            <CheckCircle2 className="w-3 h-3" />
            <span><strong>Result:</strong> {agent.resultSummary}</span>
          </div>
        )}
      </div>

      {/* Metadata stats & Actions */}
      <div className="flex items-center justify-between pt-2 border-t border-[var(--border)] text-[11px]">
        <div className="flex items-center gap-3 text-[var(--text-subtle)] font-mono">
          {agent.filesChangedCount !== undefined && (
            <span className="flex items-center gap-1">
              <FileCode2 className="w-3 h-3 text-[var(--accent)]" /> {agent.filesChangedCount} files
            </span>
          )}
          {agent.testsRunCount !== undefined && (
            <span className="flex items-center gap-1">
              <FlaskConical className="w-3 h-3 text-[var(--success)]" /> {agent.testsRunCount} tests
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {agent.status === 'running' && (
            <>
              <Button
                size="sm"
                variant="ghost"
                className="h-6 px-2 text-[10px] text-[var(--danger)] hover:bg-[var(--danger-subtle)]"
                onClick={() => stopSubAgent(agent.id)}
                aria-label={`Stop subagent ${agent.role}`}
              >
                <Square className="w-2.5 h-2.5 mr-1 fill-current" /> Stop
              </Button>

              <Button
                size="sm"
                variant="outline"
                className="h-6 px-2 text-[10px]"
                onClick={() => setIsSteeringOpen(!isSteeringOpen)}
                aria-label={`Toggle steering input for ${agent.role}`}
              >
                Steer
              </Button>
            </>
          )}

          {agent.childThreadId && (
            <Button
              size="sm"
              variant="secondary"
              className="h-6 px-2 text-[10px] gap-1"
              onClick={() => selectThread(agent.childThreadId!)}
            >
              Open Thread <ArrowRight className="w-2.5 h-2.5" />
            </Button>
          )}
        </div>
      </div>

      {/* Steering Input dropdown */}
      {isSteeringOpen && (
        <form onSubmit={handleSteer} className="flex items-center gap-1.5 pt-1">
          <Input
            value={steerPrompt}
            onChange={(e) => setSteerPrompt(e.target.value)}
            placeholder="Add guidance to this sub-agent..."
            aria-label={`Steer subagent ${agent.role}`}
            className="h-7 text-xs flex-1"
            autoFocus
          />
          <Button 
            size="sm" 
            type="submit" 
            className="h-7 px-2 text-xs"
            aria-label="Send steering guidance"
          >
            <Send className="w-3 h-3" />
          </Button>
        </form>
      )}
    </div>
  )
}
