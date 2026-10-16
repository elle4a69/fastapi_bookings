import React from 'react'
import { PhoneOff, Radio } from 'lucide-react'
import { useCodexVoice } from '../../context/CodexVoiceContext'
import { cn } from '@/lib/utils'

interface AudioWaveformStripProps {
  className?: string
}

export const AudioWaveformStrip: React.FC<AudioWaveformStripProps> = ({ className }) => {
  const { voiceState, stopVoice, audioLevel, latencyMs, transcriptDelta } = useCodexVoice()

  if (voiceState === 'idle') {
    return null
  }

  // Generate 14 animated audio bars with subtle offsets
  const numBars = 14

  return (
    <div
      data-testid="codex-audio-waveform-strip"
      className={cn(
        'h-[28px] w-full bg-card/90 backdrop-blur-md border-b border-border/40 px-3 flex items-center justify-between gap-3 text-xs select-none transition-all z-20',
        voiceState === 'listening' && 'border-emerald-500/20 bg-emerald-950/20',
        voiceState === 'speaking' && 'border-purple-500/20 bg-purple-950/20',
        voiceState === 'thinking' && 'border-blue-500/20 bg-blue-950/20',
        className,
      )}
    >
      {/* Left: Status & Transcript Snip */}
      <div className="flex items-center gap-2 min-w-0 max-w-[45%] sm:max-w-[60%]">
        <Radio
          className={cn(
            'h-3 w-3 shrink-0',
            voiceState === 'listening' && 'text-emerald-400 animate-pulse',
            voiceState === 'speaking' && 'text-purple-400 animate-bounce',
            voiceState === 'thinking' && 'text-blue-400 animate-spin',
            voiceState === 'connecting' && 'text-amber-400 animate-spin',
          )}
        />
        <span className="font-mono text-[11px] font-medium capitalize shrink-0 text-foreground">
          {voiceState}:
        </span>
        <span className="text-[11px] text-muted-foreground truncate italic">
          {transcriptDelta || (voiceState === 'listening' ? 'Listening to your voice...' : 'Processing session audio...')}
        </span>
      </div>

      {/* Center: Real-time Waveform Bars */}
      <div className="flex items-center gap-[3px] h-[16px] px-2 shrink-0" aria-label="Audio level meter">
        {Array.from({ length: numBars }).map((_, idx) => {
          // Calculate dynamic bar height reacting to audioLevel
          const offset = Math.sin((idx / numBars) * Math.PI)
          const baseHeight = 3
          const dynamicHeight = Math.max(
            baseHeight,
            Math.round(baseHeight + audioLevel * offset * 12 + (voiceState === 'speaking' ? Math.random() * 4 : 0)),
          )

          return (
            <div
              key={idx}
              className={cn(
                'w-[2.5px] rounded-full transition-all duration-75',
                voiceState === 'listening' && 'bg-emerald-400',
                voiceState === 'speaking' && 'bg-purple-400',
                voiceState === 'thinking' && 'bg-blue-400',
                voiceState === 'connecting' && 'bg-amber-400',
                voiceState === 'error' && 'bg-rose-400',
              )}
              style={{
                height: `${Math.min(16, dynamicHeight)}px`,
              }}
            />
          )
        })}
      </div>

      {/* Right: Latency & End Call Button */}
      <div className="flex items-center gap-2 shrink-0">
        <span
          title="Round-trip audio latency"
          className="font-mono text-[10px] bg-background/80 px-1.5 py-0.5 rounded text-muted-foreground border border-border/40"
        >
          {latencyMs}ms
        </span>

        <button
          type="button"
          data-testid="audio-waveform-end-call"
          onClick={stopVoice}
          title="End Voice Call"
          className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-500/20 text-rose-400 hover:bg-rose-500/30 border border-rose-500/30 transition-colors cursor-pointer"
        >
          <PhoneOff className="h-2.5 w-2.5" />
          <span className="hidden sm:inline">End</span>
        </button>
      </div>
    </div>
  )
}
