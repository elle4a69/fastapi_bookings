import { useState } from 'react'
import { Activity, Wrench } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { useBusinessAssistant } from '../business-assistant-context'

export interface DiagnosticModeToggleProps {
  className?: string
  compact?: boolean
}

export function DiagnosticModeToggle({
  className = '',
  compact = false,
}: DiagnosticModeToggleProps) {
  const { diagnosticMode, setDiagnosticMode } = useBusinessAssistant()
  const [toggling, setToggling] = useState(false)

  const handleToggle = async () => {
    if (toggling) return
    setToggling(true)
    try {
      await setDiagnosticMode(!diagnosticMode)
    } finally {
      setToggling(false)
    }
  }

  return (
    <div
      className={`flex items-center justify-between rounded-lg border bg-card/60 backdrop-blur-xs text-xs ${
        compact ? 'p-1.5 gap-1.5' : 'p-2 sm:p-2.5 gap-2'
      } ${className}`}
      data-testid="diagnostic-mode-container"
    >
      <div className="flex items-center gap-2">
        <div
          className={`flex h-7 w-7 items-center justify-center rounded-md transition-colors ${
            diagnosticMode
              ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
              : 'bg-muted text-muted-foreground'
          }`}
        >
          {diagnosticMode ? (
            <Wrench className="h-4 w-4 animate-pulse" aria-hidden="true" />
          ) : (
            <Activity className="h-4 w-4" aria-hidden="true" />
          )}
        </div>
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5 font-medium text-foreground">
            <span>Diagnostic Mode</span>
            <Badge
              variant="outline"
              className={`font-mono text-[10px] tracking-tight px-1.5 py-0.2 ${
                diagnosticMode
                  ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30'
                  : 'bg-muted/50 text-muted-foreground border-border'
              }`}
              data-testid="diagnostic-mode-status-badge"
            >
              {diagnosticMode ? 'ACTIVE' : 'OFF'}
            </Badge>
          </div>
          {!compact && (
            <span className="text-[10px] text-muted-foreground">
              {diagnosticMode
                ? '8-step runbook active; real runtime inspection & telemetry logging'
                : 'Standard business assistant operational mode'}
            </span>
          )}
        </div>
      </div>

      <button
        type="button"
        role="switch"
        aria-checked={diagnosticMode}
        aria-label="Toggle diagnostic mode"
        disabled={toggling}
        onClick={() => void handleToggle()}
        data-testid="diagnostic-mode-toggle"
        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${
          diagnosticMode ? 'bg-amber-500' : 'bg-muted-foreground/30'
        }`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-background shadow-lg ring-0 transition duration-200 ease-in-out ${
            diagnosticMode ? 'translate-x-5' : 'translate-x-0'
          }`}
        />
      </button>
    </div>
  )
}
