import React from 'react'
import { Mic, Volume2, Sparkles, Loader2, AlertCircle } from 'lucide-react'
import { useCodexVoice } from '../../context/CodexVoiceContext'
import { cn } from '@/lib/utils'

interface VoiceFABProps {
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

export const VoiceFAB: React.FC<VoiceFABProps> = ({ className, size: _size = 'md' }) => {
  const { voiceState, toggleVoice, audioLevel } = useCodexVoice()

  const getStyleForState = () => {
    switch (voiceState) {
      case 'listening':
        return {
          btnClass: 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-500/40',
          ringClass: 'ring-4 ring-emerald-500/50',
          haloClass: 'border-emerald-400 bg-emerald-500/20',
          icon: <Mic className="h-6 w-6 animate-pulse" />,
          ariaLabel: 'GPT Listening - tap to stop voice session',
        }
      case 'speaking':
        return {
          btnClass: 'bg-purple-600 hover:bg-purple-500 text-white shadow-purple-500/40',
          ringClass: 'ring-4 ring-purple-500/50',
          haloClass: 'border-purple-400 bg-purple-500/20',
          icon: <Volume2 className="h-6 w-6 animate-bounce" />,
          ariaLabel: 'GPT Speaking - tap to interrupt',
        }
      case 'thinking':
        return {
          btnClass: 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/40',
          ringClass: 'ring-4 ring-blue-500/50',
          haloClass: 'border-blue-400 bg-blue-500/20',
          icon: <Sparkles className="h-6 w-6 animate-spin text-white" />,
          ariaLabel: 'GPT Thinking - please wait',
        }
      case 'connecting':
        return {
          btnClass: 'bg-amber-600 hover:bg-amber-500 text-white shadow-amber-500/30',
          ringClass: 'ring-4 ring-amber-500/40',
          haloClass: 'border-amber-400 bg-amber-500/15',
          icon: <Loader2 className="h-6 w-6 animate-spin" />,
          ariaLabel: 'Connecting voice session',
        }
      case 'error':
        return {
          btnClass: 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-500/40',
          ringClass: 'ring-4 ring-rose-500/50',
          haloClass: 'border-rose-400 bg-rose-500/20',
          icon: <AlertCircle className="h-6 w-6" />,
          ariaLabel: 'Voice error - tap to retry',
        }
      case 'idle':
      default:
        return {
          btnClass: 'bg-primary hover:bg-primary/90 text-primary-foreground shadow-primary/30',
          ringClass: '',
          haloClass: '',
          icon: <Mic className="h-6 w-6" />,
          ariaLabel: 'Start Realtime Voice Assistant',
        }
    }
  }

  const current = getStyleForState()
  const isLive = voiceState === 'listening' || voiceState === 'speaking' || voiceState === 'thinking'

  // Dynamic scale from audio level
  const audioPulseScale = isLive ? 1 + Math.min(0.25, audioLevel * 0.4) : 1

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      {/* Outer Halo Rings */}
      {isLive && (
        <>
          <span
            className={cn(
              'absolute inset-0 rounded-full animate-ping opacity-35 border pointer-events-none -m-1.5',
              current.haloClass,
            )}
            style={{
              animationDuration: voiceState === 'speaking' ? '1.2s' : '2s',
            }}
          />
          <span
            className={cn(
              'absolute inset-0 rounded-full opacity-25 border pointer-events-none -m-3 transition-transform duration-100',
              current.haloClass,
            )}
            style={{
              transform: `scale(${audioPulseScale})`,
            }}
          />
        </>
      )}

      {/* Main 54px elevated FAB button */}
      <button
        type="button"
        data-testid="codex-voice-fab"
        onClick={() => void toggleVoice()}
        aria-label={current.ariaLabel}
        className={cn(
          'relative z-10 flex items-center justify-center w-[54px] h-[54px] min-w-[54px] min-h-[54px] rounded-full shadow-xl transition-all duration-200 cursor-pointer outline-none active:scale-95 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          current.btnClass,
          current.ringClass,
        )}
      >
        {current.icon}
      </button>
    </div>
  )
}
