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
import { useBusinessAssistant } from '../business-assistant-context.tsx'

export type AssistantMode = 'hands_off' | 'guided' | 'delegated' | 'manual_only'

function useOptionalBusinessAssistant() {
  try {
    return useBusinessAssistant()
  } catch {
    return null
  }
}

export interface OnboardingStatusDockProps {
  /** Initial or controlled mode */
  initialMode?: AssistantMode
  /** Optional callback on mode change */
  onModeChange?: (mode: AssistantMode) => void
  /** Explicit voice status override */
  voiceStatusOverride?: string
  /** Active voice transport mode */
  voiceTransport?: string
}

export function OnboardingStatusDock({
  initialMode = 'guided',
  onModeChange,
  voiceStatusOverride,
  voiceTransport,
}: OnboardingStatusDockProps) {
  const assistant = useOptionalBusinessAssistant()
  const voiceState = assistant?.voiceState ?? 'idle'
  const effectiveTransport = voiceTransport || assistant?.transport
  const drawerOpen = assistant?.drawerOpen ?? false

  const [mode, setMode] = useState<AssistantMode>(initialMode)
  const [voiceEventStatus, setVoiceEventStatus] = useState<string | null>(null)
  const [lastAction, setLastAction] = useState<string | null>(null)
  const [isTakenOver, setIsTakenOver] = useState(false)
  const [stagedCount, setStagedCount] = useState<number>(0)

  const {
    isActiveExecutor,
    makeActive,
  } = useActiveExecutor()

  // Auto-claim active executor when voice is live or drawer is open if not already active
  useEffect(() => {
    if (!isActiveExecutor && (voiceState === 'live' || drawerOpen)) {
      makeActive()
    }
  }, [isActiveExecutor, voiceState, drawerOpen, makeActive])

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
      setStagedCount(0)
      handleModeChange('manual_only')
      setVoiceEventStatus('Manual takeover active')
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

      if (
        (receipt.action === 'save_form' || receipt.action === 'commit_save') &&
        receipt.receipt_state === 'saved'
      ) {
        setVoiceEventStatus('Saved')
        setLastAction('Form saved to database')
        setStagedCount(0)
      } else if (
        (receipt.action === 'fill_fields' || receipt.action === 'stage_fields') &&
        receipt.receipt_state === 'fields_staged'
      ) {
        setVoiceEventStatus('Staged (pending save)')
        const count = receipt.field_count || (receipt.staged_fields ? receipt.staged_fields.length : 1)
        setStagedCount(count)
        setLastAction(`${count} fields staged`)
      } else if (receipt.action === 'manual_takeover') {
        setIsTakenOver(true)
        setStagedCount(0)
        setMode('manual_only')
        setVoiceEventStatus('Manual takeover active')
      } else if (receipt.receipt_state === 'waiting_for_ui') {
        setVoiceEventStatus('Listening')
        setLastAction(receipt.action)
      }
    }

    const handleFillFields = (event: Event) => {
      const customEvent = event as CustomEvent<any>
      setVoiceEventStatus('Staged (pending save)')
      const count =
        customEvent.detail?.receipt?.field_count ||
        (customEvent.detail?.fields ? Object.keys(customEvent.detail.fields).length : 1)
      setStagedCount(count)
      setLastAction(`${count} fields staged`)
    }

    const handleSaveForm = () => {
      setVoiceEventStatus('Saved')
      setLastAction('Form saved')
      setStagedCount(0)
    }

    const handleTakeoverEvent = () => {
      setIsTakenOver(true)
      setStagedCount(0)
      setMode('manual_only')
      setVoiceEventStatus('Manual takeover active')
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

  const getDisplayStatus = () => {
    if (voiceStatusOverride) return voiceStatusOverride
    if (isTakenOver) return 'Manual takeover active'
    if (voiceState === 'connecting') return 'Connecting voice...'
    if (voiceState === 'finalising') return 'Disconnecting...'
    if (voiceState === 'live') {
      return voiceEventStatus || 'Voice assistant active'
    }
    if (voiceEventStatus) return voiceEventStatus
    if (drawerOpen) return 'Assistant Ready'
    return 'Assistant Ready (Idle)'
  }

  const currentDisplayStatus = getDisplayStatus()

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
    if (status.includes('Listening') || status.includes('active') || status.includes('Connecting')) {
      return <Volume2 className="h-4 w-4 text-indigo-500 animate-pulse" aria-hidden="true" />
    }
    return <Bot className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
  }

  const isIdle = voiceState === 'idle' && !drawerOpen && stagedCount === 0 && !isTakenOver

  if (isIdle) {
    return (
      <aside
        role="region"
        aria-label="Assistant Onboarding Status Dock"
        data-testid="onboarding-status-dock"
        className="fixed bottom-4 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 rounded-full border border-border/70 bg-background/90 px-3 py-1.5 shadow-md backdrop-blur-md transition-all hover:bg-background/95 hover:border-primary/40 cursor-pointer text-xs text-muted-foreground hover:text-foreground select-none"
        onClick={() => assistant?.openDrawer?.()}
        title="Click to open Business Assistant"
      >
        <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Bot className="h-3.5 w-3.5" aria-hidden="true" />
        </div>
        <span
          data-testid="voice-status-indicator"
          className="font-medium text-xs text-foreground/80"
        >
          {currentDisplayStatus}
        </span>
        {getModeBadge(mode)}
        {isActiveExecutor ? (
          <Badge
            variant="outline"
            data-testid="active-executor-badge"
            className="border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-[10px] font-medium"
            title="Assistant can stage fields in this tab"
          >
            Control Active
          </Badge>
        ) : (
          <Badge
            variant="secondary"
            data-testid="inactive-tab-badge"
            className="text-[10px] text-muted-foreground"
            title="Assistant control idle or unlinked"
          >
            View Only
          </Badge>
        )}
      </aside>
    )
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
            {effectiveTransport && (
              <Badge
                variant="outline"
                data-testid="dock-voice-transport-badge"
                className="text-[10px] border-primary/20 bg-primary/10 text-primary font-mono"
              >
                {effectiveTransport === 'xai_grok_voice'
                  ? 'xAI Grok Voice'
                  : 'Direct WebRTC'}
              </Badge>
            )}
            {stagedCount > 0 && (
              <Badge
                variant="outline"
                data-testid="dock-staged-count-badge"
                className="text-[10px] border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400 font-medium"
              >
                {stagedCount} staged
              </Badge>
            )}
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
              className="h-7 text-xs px-2.5 gap-1 font-medium border-primary/40 hover:bg-primary/10 text-primary"
            >
              <ExternalLink className="h-3 w-3" aria-hidden="true" />
              <span>Activate Assistant Control</span>
            </Button>
          </div>
        )}

        {isActiveExecutor && (
          <Badge
            variant="outline"
            data-testid="active-executor-badge"
            className="border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-[10px] font-semibold"
          >
            Assistant Control Active
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
