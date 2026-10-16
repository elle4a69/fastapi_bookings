import React from 'react'
import { GitBranch, Radio, Sparkles, Volume2, AlertCircle, Loader2 } from 'lucide-react'
import { useCodexVoice } from '../../context/CodexVoiceContext'
import { cn } from '@/lib/utils'

interface TopBarProps {
  projectName?: string
  activeBranch?: string
  className?: string
}

export const TopBar: React.FC<TopBarProps> = ({
  projectName = 'Codex Control Centre V3',
  activeBranch = 'main',
  className,
}) => {
  const { voiceState, toggleVoice } = useCodexVoice()

  const getVoicePillConfig = () => {
    switch (voiceState) {
      case 'listening':
        return {
          label: '((o)) LIVE',
          color: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/25',
          dot: 'bg-emerald-500 animate-ping',
          icon: <Radio className="h-3 w-3 animate-pulse text-emerald-400" />,
        }
      case 'speaking':
        return {
          label: 'GPT Speaking',
          color: 'bg-purple-500/15 text-purple-300 border-purple-500/30 hover:bg-purple-500/25',
          dot: 'bg-purple-400 animate-pulse',
          icon: <Volume2 className="h-3 w-3 animate-bounce text-purple-300" />,
        }
      case 'thinking':
        return {
          label: 'GPT Thinking',
          color: 'bg-blue-500/15 text-blue-300 border-blue-500/30 hover:bg-blue-500/25',
          dot: 'bg-blue-400 animate-pulse',
          icon: <Sparkles className="h-3 w-3 animate-spin text-blue-300" />,
        }
      case 'connecting':
        return {
          label: 'Connecting...',
          color: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
          dot: 'bg-amber-400 animate-ping',
          icon: <Loader2 className="h-3 w-3 animate-spin text-amber-300" />,
        }
      case 'error':
        return {
          label: 'Voice Error',
          color: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
          dot: 'bg-rose-500',
          icon: <AlertCircle className="h-3 w-3 text-rose-400" />,
        }
      case 'idle':
      default:
        return {
          label: 'Voice Standby',
          color: 'bg-muted/50 text-muted-foreground border-border/40 hover:bg-muted/80',
          dot: 'bg-muted-foreground/50',
          icon: <Radio className="h-3 w-3 text-muted-foreground/60" />,
        }
    }
  }

  const pill = getVoicePillConfig()

  return (
    <header
      data-testid="codex-topbar"
      className={cn(
        'h-[44px] min-h-[44px] w-full border-b border-border/40 bg-card/80 backdrop-blur-md px-3 flex items-center justify-between gap-2 z-30 select-none',
        className,
      )}
    >
      {/* Project & Branch Branding */}
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="flex items-center gap-1.5 font-semibold text-xs tracking-tight text-foreground truncate">
          <span className="h-2 w-2 rounded-full bg-primary" />
          <span className="truncate">{projectName}</span>
        </div>

        <div className="hidden xs:flex items-center gap-1 px-1.5 py-0.5 rounded bg-muted/60 text-[11px] font-mono text-muted-foreground border border-border/40 max-w-[130px] truncate">
          <GitBranch className="h-2.5 w-2.5 shrink-0 opacity-70" />
          <span className="truncate">{activeBranch}</span>
        </div>
      </div>

      {/* Voice Status Pill */}
      <button
        type="button"
        onClick={() => void toggleVoice()}
        title={voiceState === 'idle' ? 'Click to start GPT Realtime Voice' : 'Click to stop voice session'}
        className={cn(
          'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors cursor-pointer shrink-0',
          pill.color,
        )}
      >
        <span className="relative flex h-2 w-2">
          <span className={cn('absolute inline-flex h-full w-full rounded-full opacity-75', pill.dot)} />
          <span className={cn('relative inline-flex rounded-full h-2 w-2', pill.dot.replace('animate-ping', ''))} />
        </span>
        {pill.icon}
        <span className="font-mono tracking-wide">{pill.label}</span>
      </button>
    </header>
  )
}
