import { Sparkles } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useBusinessAssistant } from '../business-assistant-context'

export interface VoiceEngineSelectorProps {
  className?: string
}

export function VoiceEngineSelector({ className }: VoiceEngineSelectorProps) {
  const { transport, setTransport, voiceState, startVoice } = useBusinessAssistant()

  const handleSelectEngine = async (target: 'xai_grok_voice' | 'direct_gpt_live') => {
    if (target === transport) return
    const wasActive = voiceState === 'live' || voiceState === 'connecting'
    await setTransport(target)
    if (wasActive) {
      setTimeout(() => {
        void startVoice()
      }, 250)
    }
  }

  return (
    <div
      className={cn(
        'flex flex-col gap-2 rounded-xl border border-primary/20 bg-primary/5 p-3.5',
        className,
      )}
      data-testid="voice-engine-selector-container"
    >
      <div className="flex items-center justify-between">
        <span className="font-semibold text-foreground flex items-center gap-1.5 text-xs">
          <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
          Realtime Voice Engine
        </span>
        <Badge variant="outline" className="text-[10px]">Dual Realtime</Badge>
      </div>
      <p className="text-[11px] text-muted-foreground">
        Select your real-time conversational AI voice engine:
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1" role="radiogroup" aria-label="Voice Engine">
        <button
          type="button"
          onClick={() => void handleSelectEngine('xai_grok_voice')}
          data-testid="voice-engine-option-xai"
          className={`flex flex-col p-2.5 rounded-lg border text-left transition-all cursor-pointer ${
            transport === 'xai_grok_voice'
              ? 'border-primary bg-background shadow-xs ring-1 ring-primary'
              : 'border-border/60 bg-card/60 hover:bg-muted/40'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-foreground text-xs">xAI Grok Voice</span>
            {transport === 'xai_grok_voice' && (
              <Badge variant="secondary" className="text-[9px] px-1 py-0 h-4 bg-purple-500/15 text-purple-600 font-medium">Active</Badge>
            )}
          </div>
          <span className="text-[10px] text-muted-foreground mt-0.5">grok-voice-think-fast-2.0</span>
          <span className="text-[9px] text-muted-foreground/75 font-mono mt-1">agent_YosGQC2yvTXwpdi7</span>
        </button>

        <button
          type="button"
          onClick={() => void handleSelectEngine('direct_gpt_live')}
          data-testid="voice-engine-option-openai"
          className={`flex flex-col p-2.5 rounded-lg border text-left transition-all cursor-pointer ${
            transport === 'direct_gpt_live'
              ? 'border-primary bg-background shadow-xs ring-1 ring-primary'
              : 'border-border/60 bg-card/60 hover:bg-muted/40'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-foreground text-xs">OpenAI GPT-Live</span>
            {transport === 'direct_gpt_live' && (
              <Badge variant="secondary" className="text-[9px] px-1 py-0 h-4 bg-emerald-500/15 text-emerald-600 font-medium">Active</Badge>
            )}
          </div>
          <span className="text-[10px] text-muted-foreground mt-0.5">gpt-live-1</span>
          <span className="text-[9px] text-muted-foreground/75 font-mono mt-1">Direct WebRTC</span>
        </button>
      </div>
    </div>
  )
}
