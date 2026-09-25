import React, { useState, useEffect } from 'react'
import { ExternalLink, ShieldCheck, Clock, RefreshCw, Database, Activity, Cpu, HardDrive } from 'lucide-react'
import { useWorkbenchStore } from '../../../store/useWorkbenchStore'
import { codexApi } from '../../../api/codexApi'
import { Badge } from '../../ui/badge'
import { Button } from '../../ui/button'

export const TelemetryTab: React.FC = () => {
  const { state } = useWorkbenchStore()
  const [diagnostics, setDiagnostics] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(false)

  const fetchDiagnostics = async () => {
    if (state.appMode !== 'live') return
    setIsLoading(true)
    try {
      const data = await codexApi.getDeepDiagnostics()
      setDiagnostics(data)
    } catch {
      // If API fails or unauthenticated, fallback to minimal offline diagnostics
      setDiagnostics({
        status: 'degraded',
        subsystems: {
          telemetry: {
            connected: false,
            status: 'Not connected (No active telemetry collector on http://localhost:4318)'
          }
        }
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchDiagnostics()
  }, [state.appMode])

  const telemetryStatus = diagnostics?.subsystems?.telemetry?.status || 
    'Not connected (No active telemetry collector on http://localhost:4318)'
  const isTelemetryConnected = diagnostics?.subsystems?.telemetry?.connected === true

  return (
    <div className="p-3 space-y-3 text-xs">
      {/* Telemetry Provider Status Banner */}
      <div className="p-2.5 rounded-lg bg-[var(--surface-secondary)]/50 border border-[var(--border)] flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[var(--warning)] font-medium text-[11px]">
          <ShieldCheck className="w-4 h-4 flex-shrink-0" />
          <span className="truncate">
            Diagnostics Provider: {isTelemetryConnected ? 'Connected (http://localhost:4318)' : telemetryStatus}
          </span>
        </div>
        {state.appMode === 'live' && (
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-1 text-[10px] text-[var(--text-secondary)]"
            onClick={fetchDiagnostics}
            disabled={isLoading}
            aria-label="Refresh deep diagnostics"
          >
            <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        )}
      </div>

      {/* Subsystem Health Cards if in Live Mode */}
      {state.appMode === 'live' && diagnostics?.subsystems && (
        <div className="space-y-2">
          <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">
            Subsystem Health Status
          </h3>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div className="p-2 rounded bg-[var(--surface-primary)] border border-[var(--border)] flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-[var(--accent)]" />
                <span>Database</span>
              </div>
              <Badge variant={diagnostics.subsystems.database?.status === 'healthy' ? 'success' : 'danger'} className="text-[9px] py-0 px-1">
                {diagnostics.subsystems.database?.status || 'Unknown'}
              </Badge>
            </div>

            <div className="p-2 rounded bg-[var(--surface-primary)] border border-[var(--border)] flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-[var(--accent)]" />
                <span>Event Broker</span>
              </div>
              <Badge variant={diagnostics.subsystems.event_broker?.status === 'healthy' ? 'success' : 'warning'} className="text-[9px] py-0 px-1">
                {diagnostics.subsystems.event_broker?.status || 'Active'}
              </Badge>
            </div>

            <div className="p-2 rounded bg-[var(--surface-primary)] border border-[var(--border)] flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-[var(--accent)]" />
                <span>Worker</span>
              </div>
              <Badge variant={diagnostics.subsystems.worker?.running ? 'success' : 'secondary'} className="text-[9px] py-0 px-1">
                {diagnostics.subsystems.worker?.status || 'Idle'}
              </Badge>
            </div>

            <div className="p-2 rounded bg-[var(--surface-primary)] border border-[var(--border)] flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <HardDrive className="w-3.5 h-3.5 text-[var(--accent)]" />
                <span>Worktree</span>
              </div>
              <Badge variant={diagnostics.subsystems.worktree_storage?.status === 'healthy' ? 'success' : 'warning'} className="text-[9px] py-0 px-1">
                {diagnostics.subsystems.worktree_storage?.status || 'Healthy'}
              </Badge>
            </div>
          </div>
        </div>
      )}

      {/* Linked Incidents & Traces */}
      <div className="space-y-2">
        <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">
          Linked Incidents & Traces ({state.telemetryIncidents.length})
        </h3>

        {state.telemetryIncidents.length === 0 ? (
          <div className="p-4 text-center text-xs text-[var(--text-subtle)] border border-dashed border-[var(--border)] rounded-md">
            No telemetry incidents recorded
          </div>
        ) : (
          state.telemetryIncidents.map(inc => (
            <div
              key={inc.id}
              className="border border-[var(--border)] rounded-md bg-[var(--surface-primary)] p-3 space-y-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h4 className="font-semibold text-xs text-[var(--text-primary)] m-0">
                    {inc.message}
                  </h4>
                  <div className="text-[10px] font-mono text-[var(--text-subtle)] mt-0.5">
                    Trace ID: {inc.traceId} · {inc.serviceName}
                  </div>
                </div>
                <Badge
                  variant={inc.severity === 'error' ? 'danger' : 'warning'}
                  className="text-[9px] uppercase font-mono"
                >
                  {inc.severity}
                </Badge>
              </div>

              {inc.attributes && (
                <div className="p-2 rounded bg-[var(--code-bg)] border border-[var(--code-border)] font-mono text-[10px] space-y-0.5 text-[var(--text-secondary)]">
                  {Object.entries(inc.attributes).map(([k, v]) => (
                    <div key={k} className="truncate">
                      <span className="text-[var(--text-subtle)]">{k}:</span> {v}
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between pt-1 text-[10px] text-[var(--text-subtle)] font-mono">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" /> {inc.timestamp} ({inc.durationMs}ms)
                </span>
                <a
                  href={`http://localhost:3301/trace/${inc.traceId}`}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`View trace ${inc.traceId} in SigNoz`}
                  className="text-[var(--accent)] hover:underline flex items-center gap-0.5 font-medium"
                >
                  SigNoz <ExternalLink className="w-2.5 h-2.5" aria-hidden="true" />
                </a>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
