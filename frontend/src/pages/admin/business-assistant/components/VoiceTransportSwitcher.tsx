import { useEffect } from 'react'
import { Radio, Zap } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import {
  useBusinessAssistant,
  type VoiceTransportMode,
} from '../business-assistant-context'

export interface VoiceTransportSwitcherProps {
  className?: string
  compact?: boolean
}

export function VoiceTransportSwitcher({
  className = '',
  compact = false,
}: VoiceTransportSwitcherProps) {
  const {
    transport,
    setTransport,
    transportDetails,
    voiceState,
  } = useBusinessAssistant()

  // Initialize transport from localStorage on mount if saved
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('business-assistant-transport')
      if (
        saved &&
        ['xai_grok_voice', 'direct_gpt_live'].includes(saved) &&
        saved !== transport
      ) {
        void setTransport(saved as VoiceTransportMode)
      }
    }
  }, [])

  const isVoiceActive = voiceState === 'live'

  const handleSelectMode = async (mode: VoiceTransportMode) => {
    if (mode === transport || isVoiceActive) return
    if (typeof window !== 'undefined') {
      localStorage.setItem('business-assistant-transport', mode)
    }
    await setTransport(mode)
  }

  const getModeLabel = (mode: VoiceTransportMode): string => {
    switch (mode) {
      case 'xai_grok_voice':
        return 'Grok Voice'
      case 'direct_gpt_live':
      default:
        return 'Direct WebRTC'
    }
  }

  const activeModeCanonical: 'xai_grok_voice' | 'direct_gpt_live' =
    transport === 'xai_grok_voice' ? 'xai_grok_voice' : 'direct_gpt_live'

  return (
    <div
      className={`flex flex-col rounded-lg border bg-card/60 backdrop-blur-xs text-xs ${
        compact ? 'p-1.5 gap-1.5' : 'p-2 sm:p-2.5 gap-2'
      } ${className}`}
      data-testid="voice-transport-switcher"
    >
      {!compact && (
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 font-medium text-foreground">
            <Zap className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
            <span>Voice Transport</span>
          </div>
          <Badge
            variant="outline"
            className="font-mono text-[10px] tracking-tight bg-primary/10 text-primary border-primary/20"
            data-testid="voice-transport-badge"
          >
            Mode: {getModeLabel(transport)}
          </Badge>
        </div>
      )}

      {/* Segmented Control Buttons */}
      <div
        role="radiogroup"
        aria-label="Voice transport mode selection"
        className="grid grid-cols-2 gap-1 rounded-md bg-muted/50 p-1"
      >
        {/* Mode 1: Grok Voice */}
        <button
          type="button"
          role="radio"
          disabled={isVoiceActive}
          aria-checked={activeModeCanonical === 'xai_grok_voice'}
          data-testid="transport-option-grok"
          onClick={() => void handleSelectMode('xai_grok_voice')}
          className={`flex items-center justify-center gap-1 rounded px-2 py-1.5 text-[11px] font-medium transition-all ${
            isVoiceActive ? 'opacity-50 cursor-not-allowed' : ''
          } ${
            activeModeCanonical === 'xai_grok_voice'
              ? 'bg-background text-foreground shadow-xs font-semibold'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          title={
            isVoiceActive
              ? 'Cannot switch transport while voice session is active'
              : 'Grok Voice - Native low-latency conversational voice powered by xAI Grok'
          }
        >
          <Zap className="h-3 w-3 shrink-0 text-amber-500" aria-hidden="true" />
          <span className="truncate">Grok Voice</span>
        </button>

        {/* Mode 2: Direct WebRTC */}
        <button
          type="button"
          role="radio"
          disabled={isVoiceActive}
          aria-checked={activeModeCanonical === 'direct_gpt_live'}
          data-testid="transport-option-direct"
          onClick={() => void handleSelectMode('direct_gpt_live')}
          className={`flex items-center justify-center gap-1 rounded px-2 py-1.5 text-[11px] font-medium transition-all ${
            isVoiceActive ? 'opacity-50 cursor-not-allowed' : ''
          } ${
            activeModeCanonical === 'direct_gpt_live'
              ? 'bg-background text-foreground shadow-xs font-semibold'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          title={
            isVoiceActive
              ? 'Cannot switch transport while voice session is active'
              : 'Direct WebRTC - OpenAI GPT-Live direct browser-to-server connection'
          }
        >
          <Radio className="h-3 w-3 shrink-0 text-emerald-500" aria-hidden="true" />
          <span className="truncate">Direct GPT-Live</span>
        </button>
      </div>

      {/* Target status */}
      <div className="flex items-center justify-between text-[11px] text-muted-foreground px-1">
        <span className="truncate font-mono text-[10px]">
          Target: {transportDetails?.active_target || (activeModeCanonical === 'xai_grok_voice' ? 'wss://api.x.ai/v1/realtime' : '/voice/realtime')}
        </span>
      </div>
    </div>
  )
}
