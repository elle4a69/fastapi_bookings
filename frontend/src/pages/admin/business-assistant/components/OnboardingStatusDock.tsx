import { useCallback, useEffect, useState } from 'react'
import {
  Bot,
  CheckCircle2,
  Clock,
  ExternalLink,
  ShieldAlert,
  Volume2,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ManualTakeoverControl } from './ManualTakeoverControl.tsx'
import { useActiveExecutor } from '../rpc/useActiveExecutor.ts'

export type AssistantMode = 'hands_off' | 'guided' | 'delegated' | 'manual_only'

export interface OnboardingStatusDockProps {
  /** Initial or controlled mode */
  initialMode?: AssistantMode
  /** Optional callback on mode change */
  onModeChange?: (mode: AssistantMode) => void
  /** Explicit voice status override */
  voiceStatusOverride?: string
}

export function OnboardingStatusDock({
  initialMode = 'guided',
  onModeChange,
  voiceStatusOverride,
}: OnboardingStatusDockProps) {
  const [mode, setMode] = useState<AssistantMode>(initialMode)
  const [voiceStatus, setVoiceStatus] = useState<string>('Voice assistant active')
  const [lastAction, setLastAction] = useState<string | null>(null)
  const [isTakenOver, setIsTakenOver] = useState(false)

  const {
    isActiveExecutor,
    makeActive,
  } = useActiveExecutor()

  const handleModeChange = useCallback(
    (newMode: AssistantMode) => {
      setMode(newMode)
      if (onModeChange) {
        onModeChange(newMode)
      }
    },
    [onModeChange],
  )

  const handleTakeover = useCallback(
    (newEpoch: number) => {
      setIsTakenOver(true)
      handleModeChange('manual_only')
      setVoiceStatus('Manual takeover active')
      setLastAction(`Takeover at epoch ${newEpoch}`)
    },
    [handleModeChange],
  )

  useEffect(() => {
    // Listen for RPC events and receipt status updates
    const handleReceipt = (event: Event) => {
      const customEvent = event as CustomEvent<any>
      const receipt = customEvent.detail
      if (!receipt) return

      if (receipt.action === 'save_form' && receipt.receipt_state === 'saved') {
        setVoiceStatus('Saved')
        setLastAction('Form saved to database')
      } else if (receipt.action === 'fill_fields' && receipt.receipt_state === 'fields_staged') {
        setVoiceStatus('Staged (pending save)')
        setLastAction(`${receipt.field_count || 1} fields staged`)
      } else if (receipt.action === 'manual_takeover') {
        setIsTakenOver(true)
        setMode('manual_only')
        setVoiceStatus('Manual takeover active')
      } else if (receipt.receipt_state === 'waiting_for_ui') {
        setVoiceStatus('Listening')
        setLastAction(receipt.action)
      }
    }

    const handleFillFields = (event: Event) => {
      const customEvent = event as CustomEvent<any>
      setVoiceStatus('Staged (pending save)')
      if (customEvent.detail?.stagedFields) {
        setLastAction(`${customEvent.detail.stagedFields.length} fields staged`)
      }
    }

    const handleSaveForm = () => {
      setVoiceStatus('Saved')
      setLastAction('Form saved')
    }

    const handleTakeoverEvent = () => {
      setIsTakenOver(true)
      setMode('manual_only')
      setVoiceStatus('Manual takeover active')
    }

    if (typeof window !== 'undefined') {
      window.addEventListener('assistant-rpc:receipt', handleReceipt)
      window.addEventListener('assistant-rpc:fill-fields', handleFillFields)
      window.addEventListener('assistant-rpc:save-form', handleSaveForm)
      window.addEventListener('assistant-rpc:manual-takeover', handleTakeoverEvent)
    }

    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('assistant-rpc:receipt', handleReceipt)
        window.removeEventListener('assistant-rpc:fill-fields', handleFillFields)
        window.removeEventListener('assistant-rpc:save-form', handleSaveForm)
        window.removeEventListener('assistant-rpc:manual-takeover', handleTakeoverEvent)
      }
    }
  }, [])

  const currentDisplayStatus = voiceStatusOverride || voiceStatus

  // Mode badge styling helper
  const getModeBadge = (currentMode: AssistantMode) => {
    switch (currentMode) {
      case 'hands_off':
        return (
          <Badge
            variant="outline"
            data-testid="mode-badge-hands-off"
            className="border-slate-300 bg-slate-100 text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
          >
            Hands-off
          </Badge>
        )
      case 'guided':
        return (
          <Badge
            variant="outline"
            data-testid="mode-badge-guided"
            className="border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-300"
          >
            Guided
          </Badge>
        )
      case 'delegated':
        return (
          <Badge
            variant="outline"
            data-testid="mode-badge-delegated"
            className="border-indigo-300 bg-indigo-50 text-indigo-800 dark:border-indigo-800 dark:bg-indigo-950 dark:text-indigo-300"
          >
            Delegated
          </Badge>
        )
      case 'manual_only':
        return (
          <Badge
            variant="outline"
            data-testid="mode-badge-manual-only"
            className="border-amber-400 bg-amber-50 text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300"
          >
            Manual Only
          </Badge>
        )
    }
  }

  // Voice status icon helper
  const getStatusIcon = (status: string) => {
    if (status.includes('Saved')) {
      return <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-hidden="true" />
    }
    if (status.includes('Staged')) {
      return <Clock className="h-4 w-4 text-amber-500 animate-pulse" aria-hidden="true" />
    }
    if (status.includes('Manual')) {
      return <ShieldAlert className="h-4 w-4 text-amber-600" aria-hidden="true" />
    }
    if (status.includes('Listening') || status.includes('active')) {
      return <Volume2 className="h-4 w-4 text-indigo-500 animate-pulse" aria-hidden="true" />
    }
    return <Bot className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
  }

  return (
    <aside
      role="region"
      aria-label="Assistant Onboarding Status Dock"
      data-testid="onboarding-status-dock"
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-30 flex max-w-[calc(100vw-2rem)] flex-wrap items-center justify-between gap-3 rounded-xl border border-border/80 bg-background/95 px-3.5 py-2 shadow-lg backdrop-blur-md transition-all sm:flex-nowrap"
    >
      {/* Voice Status & Indicator */}
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          {getStatusIcon(currentDisplayStatus)}
        </div>
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-2">
            <span
              data-testid="voice-status-indicator"
              className="text-xs font-semibold text-foreground truncate"
            >
              {currentDisplayStatus}
            </span>
            {getModeBadge(mode)}
          </div>
          {lastAction && (
            <span className="text-[11px] text-muted-foreground truncate">
              {lastAction}
            </span>
          )}
        </div>
      </div>

      {/* Multi-Tab Executor Coordination & Manual Takeover */}
      <div className="flex items-center gap-2 shrink-0">
        {!isActiveExecutor && (
          <div className="flex items-center gap-1.5">
            <Badge
              variant="secondary"
              data-testid="inactive-tab-badge"
              className="text-[10px] text-muted-foreground"
            >
              View Only
            </Badge>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => makeActive()}
              data-testid="make-tab-active-button"
              className="h-7 text-xs px-2.5 gap-1"
            >
              <ExternalLink className="h-3 w-3" aria-hidden="true" />
              <span>Make this tab active</span>
            </Button>
          </div>
        )}

        {isActiveExecutor && (
          <Badge
            variant="outline"
            data-testid="active-executor-badge"
            className="border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-[10px]"
          >
            Active Executor
          </Badge>
        )}

        {/* Prominent "I'll do this part" Takeover Button */}
        <ManualTakeoverControl
          onTakeover={handleTakeover}
          isTakenOver={isTakenOver}
        />
      </div>
    </aside>
  )
}
