import { Maximize2, Mic, PhoneOff, Volume2 } from 'lucide-react'

import { Button } from '@/components/ui/button'

import { useBusinessAssistant } from './business-assistant-context'

export function MinimizedVoiceController() {
  const {
    drawerOpen,
    openDrawer,
    voiceState,
    voiceCaptions,
    stopVoice,
  } = useBusinessAssistant()

  // Only show floating controller when drawer is minimized/closed and voice is active
  if (drawerOpen || voiceState === 'idle') {
    return null
  }

  const latestCaption = voiceCaptions[voiceCaptions.length - 1]
  const isLive = voiceState === 'live'
  const isConnecting = voiceState === 'connecting'
  const isFinalising = voiceState === 'finalising'

  return (
    <aside
      role="region"
      aria-label="Active voice assistant session"
      aria-live="polite"
      data-testid="business-assistant-minimized-mic"
      className="fixed right-[max(1.25rem,env(safe-area-inset-right))] bottom-[max(5rem,calc(env(safe-area-inset-bottom)+4.5rem))] z-30 flex max-w-[calc(100vw-2.5rem)] sm:max-w-md items-center gap-2 rounded-full border border-primary/30 bg-card/95 p-1.5 pr-2.5 shadow-xl backdrop-blur-md transition-all animate-in fade-in slide-in-from-bottom-2"
    >
      {/* Pulsing Voice Status Badge */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white transition-colors ${
          isLive
            ? 'bg-emerald-600 shadow-xs shadow-emerald-500/50'
            : isConnecting
              ? 'bg-amber-600 animate-pulse'
              : 'bg-muted-foreground'
        }`}
        title={
          isLive
            ? 'Microphone active - listening'
            : isConnecting
              ? 'Connecting encrypted voice session...'
              : 'Finalising session...'
        }
      >
        {isLive ? (
          <Volume2 className="h-4 w-4 animate-pulse" aria-hidden="true" />
        ) : (
          <Mic className="h-4 w-4" aria-hidden="true" />
        )}
      </div>

      {/* Voice Status & Latest Caption Snippet */}
      <div
        className="flex min-w-0 flex-1 cursor-pointer flex-col px-1"
        onClick={openDrawer}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            openDrawer()
          }
        }}
        title="Click to expand assistant drawer"
      >
        <div className="flex items-center gap-1.5">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              isLive
                ? 'bg-emerald-500 animate-ping'
                : isConnecting
                  ? 'bg-amber-500 animate-pulse'
                  : 'bg-muted-foreground'
            }`}
            aria-hidden="true"
          />
          <span className="text-[11px] font-semibold text-foreground">
            {isLive ? 'Voice Active' : isConnecting ? 'Connecting…' : 'Finalising…'}
          </span>
        </div>
        <p className="truncate text-[11px] text-muted-foreground">
          {latestCaption ? (
            <span>
              <strong className="text-foreground">
                {latestCaption.speaker === 'user' ? 'You: ' : 'Assistant: '}
              </strong>
              {latestCaption.text}
            </span>
          ) : isLive ? (
            'Listening… speak naturally or interrupt'
          ) : (
            'Preparing audio channel…'
          )}
        </p>
      </div>

      {/* Quick Controls */}
      <div className="flex shrink-0 items-center gap-1">
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          onClick={openDrawer}
          title="Expand Business Assistant"
          aria-label="Expand Business Assistant"
          className="h-7 w-7 text-muted-foreground hover:text-foreground"
        >
          <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
        <Button
          type="button"
          variant="destructive"
          size="icon-xs"
          onClick={stopVoice}
          disabled={isFinalising}
          title="End voice session"
          aria-label="End voice session"
          className="h-7 w-7 rounded-full shadow-xs"
        >
          <PhoneOff className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
      </div>
    </aside>
  )
}
