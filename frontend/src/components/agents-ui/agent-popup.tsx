'use client'

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from 'react'
import {
  Bot,
  Camera,
  CameraOff,
  ChevronDown,
  Ear,
  MessageSquare,
  Mic,
  MicOff,
  Monitor,
  MonitorOff,
  PhoneOff,
  RotateCcw,
  Send,
  Settings,
  Sparkles,
  Volume2,
  X,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'
import { useBusinessAssistant } from '@/pages/admin/business-assistant/business-assistant-context'
import {
  DiagnosticModeToggle,
  VoiceEngineSelector,
} from '@/pages/admin/business-assistant/components'
import { useAgent, type AgentSpeed } from '@/components/ui-agent/AgentProvider'
import { useVoice, VOICE_PROVIDERS, SLEEP_OPTIONS } from '@/components/ui-agent/VoiceProvider'

export interface AgentPopupControls {
  leave?: boolean
  microphone?: boolean
  chat?: boolean
  camera?: boolean
  screenShare?: boolean
}

export interface AudioVisualizerConfig {
  type?: 'bar' | 'wave' | 'ring'
  barCount?: number
  size?: 'sm' | 'md' | 'lg'
}

export interface AgentPopupProps {
  logo?: string
  agentName?: string
  tokenSource?: unknown
  themeMode?: 'light' | 'dark' | 'system'
  preConnectMessage?: string
  controls?: AgentPopupControls
  triggerColor?: `#${string}` | string
  isPreConnectBufferEnabled?: boolean
  audioVisualizer?: AudioVisualizerConfig
  className?: string
}

/**
 * Animated 3-Bar Audio Visualizer component.
 * Animates smoothly when audio/voice is live and active.
 */
function ThreeBarVisualizer({
  isActive,
  isMuted,
}: {
  isActive: boolean
  isMuted: boolean
}) {
  return (
    <div
      className="flex items-center justify-center gap-[3px] h-4 w-4"
      aria-hidden="true"
    >
      <span
        className={cn(
          'w-[3px] rounded-full transition-all duration-150',
          isMuted
            ? 'h-1 bg-muted-foreground/40'
            : isActive
              ? 'h-3.5 bg-emerald-500 animate-pulse'
              : 'h-1.5 bg-muted-foreground/60',
        )}
        style={{
          animationDuration: isActive ? '600ms' : undefined,
          animationDelay: '0ms',
        }}
      />
      <span
        className={cn(
          'w-[3px] rounded-full transition-all duration-150',
          isMuted
            ? 'h-1 bg-muted-foreground/40'
            : isActive
              ? 'h-4 bg-emerald-500 animate-pulse'
              : 'h-2 bg-muted-foreground/60',
        )}
        style={{
          animationDuration: isActive ? '750ms' : undefined,
          animationDelay: '150ms',
        }}
      />
      <span
        className={cn(
          'w-[3px] rounded-full transition-all duration-150',
          isMuted
            ? 'h-1 bg-muted-foreground/40'
            : isActive
              ? 'h-2.5 bg-emerald-500 animate-pulse'
              : 'h-1.5 bg-muted-foreground/60',
        )}
        style={{
          animationDuration: isActive ? '500ms' : undefined,
          animationDelay: '300ms',
        }}
      />
    </div>
  )
}

/**
 * Native LiveKit Agent Popup (AgentPopup_01)
 *
 * Provides a floating circular trigger button that expands into a compact
 * agent session card with full transcript timeline, typing input, audio controls,
 * camera toggle, screen sharing, and transcript toggle.
 */
export function AgentPopup({
  logo,
  agentName = 'Business Assistant',
  preConnectMessage = 'Agent is listening, ask it a question',
  controls = {
    leave: true,
    microphone: true,
    chat: true,
    camera: true,
    screenShare: true,
  },
  triggerColor,
  isPreConnectBufferEnabled: _isPreConnectBufferEnabled = true,
  audioVisualizer: _audioVisualizer = { type: 'bar', barCount: 3 },
  className,
}: AgentPopupProps) {
  const {
    drawerOpen,
    openDrawer,
    closeDrawer,
    voiceState,
    voiceCaptions,
    startVoice,
    stopVoice,
    isMuted,
    toggleMute,
    audioDevices,
    activeAudioDeviceId,
    switchAudioDevice,
    transport,
    messages,
    draft,
    setDraft,
    sendTurn,
    sending,
    pageContext,
  } = useBusinessAssistant()

  const agent = useAgent()
  const v = useVoice()

  const [showTranscript, setShowTranscript] = useState(true)
  const [showSettings, setShowSettings] = useState(false)
  const [isCameraActive, setIsCameraActive] = useState(false)
  const [isScreenSharing, setIsScreenSharing] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const cameraVideoRef = useRef<HTMLVideoElement | null>(null)
  const screenVideoRef = useRef<HTMLVideoElement | null>(null)
  const cameraStreamRef = useRef<MediaStream | null>(null)
  const screenStreamRef = useRef<MediaStream | null>(null)

  const isLive = voiceState === 'live' || v.active || v.state === 'listening' || v.state === 'speaking'
  const isConnecting = voiceState === 'connecting' || v.state === 'connecting'
  const isSessionActive = isLive || isConnecting

  // Sync transport with voice provider
  useEffect(() => {
    if (transport === 'xai_grok_voice' && v.provider !== 'xai') {
      v.setProvider('xai')
    } else if (transport === 'direct_gpt_live' && v.provider !== 'openai') {
      v.setProvider('openai')
    }
  }, [transport, v])

  // Auto-scroll transcript to bottom
  useEffect(() => {
    if (drawerOpen && showTranscript) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [drawerOpen, showTranscript, messages, voiceCaptions])

  // Stop media tracks cleanly on unmount or session stop
  const stopCamera = useCallback(() => {
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach((t) => t.stop())
      cameraStreamRef.current = null
    }
    if (cameraVideoRef.current) {
      cameraVideoRef.current.srcObject = null
    }
    setIsCameraActive(false)
  }, [])

  const stopScreenShare = useCallback(() => {
    if (screenStreamRef.current) {
      screenStreamRef.current.getTracks().forEach((t) => t.stop())
      screenStreamRef.current = null
    }
    if (screenVideoRef.current) {
      screenVideoRef.current.srcObject = null
    }
    setIsScreenSharing(false)
  }, [])

  // Toggle Camera
  const toggleCamera = useCallback(async () => {
    if (isCameraActive) {
      stopCamera()
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
      })
      cameraStreamRef.current = stream
      setIsCameraActive(true)
      if (cameraVideoRef.current) {
        cameraVideoRef.current.srcObject = stream
      }
    } catch {
      setIsCameraActive(false)
    }
  }, [isCameraActive, stopCamera])

  // Toggle Screen Share
  const toggleScreenShare = useCallback(async () => {
    if (isScreenSharing) {
      stopScreenShare()
      return
    }
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
      })
      screenStreamRef.current = stream
      setIsScreenSharing(true)
      if (screenVideoRef.current) {
        screenVideoRef.current.srcObject = stream
      }
      const videoTrack = stream.getVideoTracks()[0]
      if (videoTrack) {
        videoTrack.onended = () => {
          stopScreenShare()
        }
      }
    } catch {
      setIsScreenSharing(false)
    }
  }, [isScreenSharing, stopScreenShare])

  // Handle explicit end-of-call / hang up
  const handleLeaveSession = useCallback(() => {
    stopVoice()
    if (v.active) {
      v.stop()
    }
    stopCamera()
    stopScreenShare()
    closeDrawer()
  }, [stopVoice, v, stopCamera, stopScreenShare, closeDrawer])

  // Minimize / close the card without terminating the voice session
  const handleMinimize = useCallback(() => {
    closeDrawer()
  }, [closeDrawer])

  // Handle Trigger Click: toggle drawer without ending active voice session
  const handleTriggerClick = useCallback(() => {
    if (drawerOpen) {
      closeDrawer()
    } else {
      openDrawer()
      if (voiceState === 'idle' && !v.active) {
        void startVoice()
      }
    }
  }, [drawerOpen, closeDrawer, openDrawer, voiceState, v.active, startVoice])

  // Clean up streams if component unmounts
  useEffect(() => {
    return () => {
      stopCamera()
      stopScreenShare()
    }
  }, [stopCamera, stopScreenShare])

  // Handle typed text submission
  const handleSubmitText = useCallback(
    async (e: FormEvent) => {
      e.preventDefault()
      const text = draft.trim()
      if (!text || sending || agent.busy) return
      setDraft('')

      // If user typed a UI navigation / DOM operation prompt, dispatch to UI agent to drive DOM:
      const isUiAction = /^(navigate|go to|open|click|fill|type|select|check|scroll|find|search|show me|take me|set |choose |press )/i.test(text)
      if (isUiAction) {
        void agent.send(text, { source: 'text' })
      }

      await sendTurn(text)
    },
    [draft, sending, agent, sendTurn, setDraft],
  )

  const activeDeviceLabel =
    audioDevices.find((d) => d.deviceId === activeAudioDeviceId)?.label ||
    (audioDevices.length > 0 ? audioDevices[0].label : 'Default Microphone')

  return (
    <>
      {/* Floating Agent Session Popup Card */}
      {drawerOpen && (
        <aside
          role="dialog"
          aria-label={agentName}
          aria-modal="false"
          data-testid="livekit-agent-popup"
          className={cn(
            'fixed right-[max(1.25rem,env(safe-area-inset-right))] bottom-[max(5.5rem,calc(env(safe-area-inset-bottom)+5.25rem))] z-50',
            'flex flex-col w-[calc(100vw-2.5rem)] sm:w-[390px] h-[520px] max-h-[calc(100vh-7rem)]',
            'rounded-2xl border border-border/80 bg-card text-card-foreground shadow-2xl backdrop-blur-xl',
            'overflow-hidden transition-all duration-200 animate-in fade-in zoom-in-95 slide-in-from-bottom-3',
            className,
          )}
        >
          {/* Header Bar */}
          <header className="flex items-center justify-between border-b border-border/60 px-4 py-3 bg-muted/30">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary shadow-xs">
                {logo ? (
                  <img src={logo} alt={agentName} className="h-5 w-5 object-contain" />
                ) : (
                  <Bot className="h-4 w-4" aria-hidden="true" />
                )}
                <span
                  className={cn(
                    'absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-card',
                    isLive
                      ? 'bg-emerald-500'
                      : isConnecting
                        ? 'bg-amber-500 animate-pulse'
                        : 'bg-muted-foreground/60',
                  )}
                  aria-hidden="true"
                />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <h3 className="text-xs font-semibold text-foreground truncate">
                    {agentName}
                  </h3>
                  <span
                    className="rounded bg-primary/10 px-1.5 py-0.5 text-[9px] font-mono font-medium text-primary"
                    data-testid="agent-popup-transport-badge"
                  >
                    {transport === 'xai_grok_voice'
                      ? 'xAI Grok'
                      : transport === 'direct_gpt_live'
                        ? 'Direct'
                        : transport === 'cloud_livekit'
                          ? 'Cloud'
                          : 'LiveKit'}
                  </span>
                  {v.wakeListening && (
                    <span
                      data-testid="wake-word-indicator"
                      title={`Say "${v.wakePhrase}"`}
                      className="flex items-center gap-1 font-mono text-[9px] text-primary/80"
                    >
                      <Ear className="h-2.5 w-2.5 animate-pulse" /> “{v.wakePhrase}”
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => setShowSettings((prev) => !prev)}
                    title="Assistant Settings & Transport"
                    aria-label="Assistant Settings & Transport"
                    aria-expanded={showSettings}
                    data-testid="agent-popup-settings-button"
                    className={cn(
                      'flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors',
                      showSettings && 'bg-primary/15 text-primary hover:bg-primary/25',
                    )}
                  >
                    <Settings className="h-3 w-3" aria-hidden="true" />
                  </button>
                </div>
                <p className="text-[10px] text-muted-foreground truncate">
                  {agent.busy
                    ? 'Agent is automating the screen…'
                    : isLive
                      ? isMuted
                        ? 'Microphone muted'
                        : v.active && v.state === 'speaking'
                          ? 'Agent speaking…'
                          : 'Listening & ready'
                      : isConnecting
                        ? 'Connecting session…'
                        : pageContext?.module_name ?? 'Ready to assist'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1 shrink-0">
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                onClick={handleMinimize}
                title="Minimize assistant"
                aria-label="Minimize assistant"
                className="h-7 w-7 text-muted-foreground hover:text-foreground rounded-lg"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          </header>

          {showSettings ? (
            <div
              className="flex-1 overflow-y-auto p-3.5 space-y-3 bg-card text-xs select-text animate-in fade-in slide-in-from-top-2"
              data-testid="agent-popup-settings-panel"
            >
              <div className="flex items-center justify-between border-b border-border/60 pb-2">
                <div className="flex items-center gap-1.5 font-semibold text-foreground">
                  <Settings className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                  <span>Assistant Settings &amp; Transport</span>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  onClick={() => setShowSettings(false)}
                  data-testid="agent-popup-settings-done-button"
                  className="h-6 text-[11px] px-2 text-muted-foreground hover:text-foreground"
                >
                  Done
                </Button>
              </div>

              <VoiceEngineSelector />

              {/* Speaking Voice Selection Dropdown */}
              <div className="space-y-1.5 pt-1 border-t border-border/40">
                <label htmlFor="voice-voice-select" className="block text-[11px] font-medium text-foreground">
                  Speaking Voice ({VOICE_PROVIDERS.find((p) => p.id === v.provider)?.label || 'Selected Provider'})
                </label>
                <select
                  id="voice-voice-select"
                  data-testid="voice-voice-select"
                  value={v.voices[v.provider] || (v.provider === 'openai' ? 'marin' : 'eve')}
                  disabled={v.active || isLive}
                  onChange={(e) => v.setVoice(v.provider, e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs text-foreground shadow-xs focus:outline-hidden focus:ring-1 focus:ring-ring capitalize disabled:opacity-50"
                >
                  {VOICE_PROVIDERS.find((p) => p.id === v.provider)?.voices.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
                {(v.active || isLive) && (
                  <p className="text-[10px] text-muted-foreground">Voice changes apply to the next session.</p>
                )}
              </div>

              {/* Wake Word Hands-Free Section */}
              <div className="space-y-2 pt-1 border-t border-border/40">
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-[11px] font-medium text-foreground">Wake Word (Hands-Free)</span>
                    <span className="text-[10px] text-muted-foreground">Start voice automatically by speaking a phrase</span>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={v.wakeEnabled}
                    data-testid="wake-word-toggle"
                    disabled={!v.wakeSupported}
                    onClick={() => v.setWakeEnabled(!v.wakeEnabled)}
                    className={cn(
                      'relative h-5 w-9 shrink-0 rounded-full transition-colors disabled:opacity-40 cursor-pointer',
                      v.wakeEnabled ? 'bg-primary' : 'bg-muted-foreground/30',
                    )}
                  >
                    <span
                      className={cn(
                        'absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white transition-transform shadow-xs',
                        v.wakeEnabled ? 'translate-x-4' : 'translate-x-0',
                      )}
                    />
                  </button>
                </div>
                <input
                  data-testid="wake-word-input"
                  value={v.wakePhrase}
                  onChange={(e) => v.setWakePhrase(e.target.value)}
                  placeholder="e.g. Hey Aether"
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1 text-xs text-foreground placeholder:text-muted-foreground/60 shadow-xs focus:outline-hidden focus:ring-1 focus:ring-ring"
                  aria-label="Wake phrase"
                />
                <p data-testid="wake-word-status" className="text-[10px] text-muted-foreground">
                  {!v.wakeSupported
                    ? 'Wake word needs Chrome, Edge or Safari speech recognition.'
                    : v.wakeListening
                    ? `Listening for “${v.wakePhrase}”…`
                    : v.wakeEnabled
                    ? 'Paused while a voice session is active.'
                    : 'Off'}
                </p>
              </div>

              {/* DOM Automation Speed */}
              <div className="space-y-1.5 pt-1 border-t border-border/40">
                <span className="text-[11px] font-medium text-foreground">DOM Automation Speed</span>
                <p className="text-[10px] text-muted-foreground">
                  Speed of cursor movements, typing, and form navigation:
                </p>
                <div className="flex gap-1.5">
                  {(['slow', 'realistic', 'fast'] as AgentSpeed[]).map((s) => (
                    <button
                      key={s}
                      type="button"
                      data-testid={`agent-speed-${s}`}
                      onClick={() => agent.setSpeed(s)}
                      className={cn(
                        'flex-1 rounded-md border px-2.5 py-1 text-xs font-medium capitalize transition-colors',
                        agent.speed === s
                          ? 'border-primary/50 bg-primary/10 text-primary font-semibold'
                          : 'border-border/60 bg-muted/20 text-muted-foreground hover:text-foreground',
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              {/* Auto Sleep Silence Timeout */}
              <div className="space-y-1.5 pt-1 border-t border-border/40">
                <span className="text-[11px] font-medium text-foreground">Auto Sleep Timeout</span>
                <p className="text-[10px] text-muted-foreground">
                  End voice session after silence:
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {SLEEP_OPTIONS.map((sec) => (
                    <button
                      key={sec}
                      type="button"
                      data-testid={`auto-sleep-${sec}`}
                      onClick={() => v.setSleepAfter(sec)}
                      className={cn(
                        'rounded-md border px-2.5 py-1 text-xs transition-colors',
                        v.sleepAfter === sec
                          ? 'border-primary/50 bg-primary/10 text-primary font-semibold'
                          : 'border-border/60 bg-muted/20 text-muted-foreground hover:text-foreground',
                      )}
                    >
                      {sec === 0 ? 'Never' : sec < 60 ? `${sec}s` : `${sec / 60}m`}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-1.5 pt-1 border-t border-border/40">
                <span className="text-[11px] font-medium text-foreground">Diagnostic Telemetry</span>
                <DiagnosticModeToggle />
              </div>

              {/* Session Reset */}
              <div className="pt-1 border-t border-border/40">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  data-testid="settings-new-session"
                  onClick={() => {
                    agent.reset()
                    setShowSettings(false)
                  }}
                  className="w-full text-xs h-8"
                >
                  <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                  Start New Session
                </Button>
              </div>
            </div>
          ) : (
            <>
              {/* Video / Screen Share Mini Preview Strip */}
          {(isCameraActive || isScreenSharing) && (
            <div className="flex gap-2 p-2 bg-muted/20 border-b border-border/40 shrink-0">
              {isCameraActive && (
                <div className="relative h-20 w-28 rounded-lg overflow-hidden border border-border bg-black">
                  <video
                    ref={cameraVideoRef}
                    autoPlay
                    playsInline
                    muted
                    className="h-full w-full object-cover"
                  />
                  <span className="absolute bottom-1 left-1 rounded bg-black/70 px-1 py-0.2 text-[8px] font-medium text-white">
                    Camera
                  </span>
                </div>
              )}
              {isScreenSharing && (
                <div className="relative h-20 w-32 rounded-lg overflow-hidden border border-border bg-black">
                  <video
                    ref={screenVideoRef}
                    autoPlay
                    playsInline
                    muted
                    className="h-full w-full object-cover"
                  />
                  <span className="absolute bottom-1 left-1 rounded bg-black/70 px-1 py-0.2 text-[8px] font-medium text-white">
                    Screen
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Main Body: Transcript Mode vs Visualizer Mode */}
          <div className="flex-1 overflow-hidden flex flex-col">
            {showTranscript ? (
              <div
                className="flex-1 overflow-y-auto p-3 space-y-2.5 text-xs select-text"
                data-testid="agent-popup-transcript"
              >
                {/* Pre-connect Buffer / Empty State Prompt */}
                {messages.length === 0 && voiceCaptions.length === 0 && (
                  <div className="flex flex-col items-center justify-center h-full text-center p-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary mb-3">
                      <Sparkles className="h-5 w-5 animate-pulse" aria-hidden="true" />
                    </div>
                    <p className="text-xs font-medium text-foreground max-w-[240px]">
                      {preConnectMessage}
                    </p>
                    <p className="text-[11px] text-muted-foreground mt-1 max-w-[220px]">
                      Speak naturally or type your request below to navigate, stage fields, or ask questions.
                    </p>
                  </div>
                )}

                {/* Conversation History Messages */}
                {messages.map((msg) => {
                  const isUser = msg.role === 'user'
                  return (
                    <div
                      key={msg.id}
                      className={cn(
                        'flex flex-col max-w-[85%] animate-in fade-in-50',
                        isUser ? 'ml-auto items-end' : 'mr-auto items-start',
                      )}
                    >
                      <div
                        className={cn(
                          'rounded-2xl px-3.5 py-2 text-xs leading-relaxed shadow-2xs whitespace-pre-wrap break-words',
                          isUser
                            ? 'bg-primary text-primary-foreground rounded-tr-xs'
                            : 'bg-muted/70 text-foreground border border-border/50 rounded-tl-xs',
                        )}
                      >
                        {msg.content}
                      </div>
                      <span className="text-[9px] text-muted-foreground/70 px-1 mt-0.5">
                        {isUser
                          ? msg.channel === 'realtime_voice'
                            ? 'You (Speaking…)'
                            : 'You'
                          : msg.channel === 'realtime_voice'
                            ? `${agentName} (Voice)`
                            : agentName}
                      </span>
                    </div>
                  )
                })}

                {/* Live Voice Realtime Streaming Captions (rendered when not already in messages stream) */}
                {voiceCaptions
                  .filter(
                    (caption) =>
                      !messages.some(
                        (m) =>
                          m.channel === 'realtime_voice' &&
                          (m.content === caption.text || m.content.includes(caption.text.trim())),
                      ),
                  )
                  .map((caption, idx) => {
                  const isUser = caption.speaker === 'user'
                  return (
                    <div
                      key={`${caption.speaker}-${caption.startMs}-${idx}`}
                      className={cn(
                        'flex flex-col max-w-[85%] animate-in fade-in',
                        isUser ? 'ml-auto items-end' : 'mr-auto items-start',
                      )}
                    >
                      <div
                        className={cn(
                          'rounded-2xl px-3.5 py-2 text-xs leading-relaxed border shadow-2xs whitespace-pre-wrap break-words',
                          isUser
                            ? 'bg-primary/90 text-primary-foreground border-primary/40 rounded-tr-xs'
                            : 'bg-card text-foreground border-primary/30 rounded-tl-xs shadow-xs',
                        )}
                      >
                        {caption.text}
                      </div>
                      <span className="text-[9px] text-primary font-medium px-1 mt-0.5">
                        {isUser ? 'You (Speaking…)' : `${agentName} (Voice)`}
                      </span>
                    </div>
                  )
                })}

                {/* Voice Provider Streaming Caption */}
                {v.active && v.caption && (
                  <div
                    data-testid="voice-caption"
                    className="flex flex-col max-w-[85%] mr-auto items-start animate-in fade-in"
                  >
                    <div className="rounded-2xl px-3.5 py-2 text-xs leading-relaxed border shadow-2xs italic bg-card text-foreground border-primary/30 rounded-tl-xs">
                      “{v.caption}”
                    </div>
                    <span className="text-[9px] text-primary font-medium px-1 mt-0.5">
                      {agentName} (Voice)
                    </span>
                  </div>
                )}

                {/* Sending / Thinking Indicator */}
                {(sending || agent.busy) && (
                  <div
                    data-testid="agent-thinking"
                    className="flex items-center gap-1.5 text-[11px] text-muted-foreground mr-auto bg-muted/40 rounded-xl px-3 py-1.5 animate-pulse"
                  >
                    <Sparkles className="h-3 w-3 text-primary animate-spin" />
                    <span>{agent.busy ? 'Agent automating screen…' : 'Thinking…'}</span>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            ) : (
              /* Minimalist Live Visualizer View */
              <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
                <div
                  className={cn(
                    'relative flex h-24 w-24 items-center justify-center rounded-full transition-all duration-300',
                    isLive
                      ? 'bg-primary/10 shadow-lg shadow-primary/20 scale-105'
                      : 'bg-muted/40',
                  )}
                >
                  {isLive && (
                    <span className="absolute inset-0 rounded-full border-2 border-primary/30 animate-ping" />
                  )}
                  <Volume2
                    className={cn(
                      'h-10 w-10 transition-colors',
                      isLive ? 'text-primary animate-pulse' : 'text-muted-foreground',
                    )}
                  />
                </div>
                <h4 className="mt-4 text-xs font-semibold text-foreground">
                  {isLive
                    ? isMuted
                      ? 'Microphone is Muted'
                      : 'Listening to your voice…'
                    : isConnecting
                      ? 'Connecting encrypted voice channel…'
                      : 'Voice Assistant Idle'}
                </h4>
                <p className="mt-1 text-[11px] text-muted-foreground max-w-[220px]">
                  {isLive
                    ? 'Speak naturally or switch to transcript mode to read text history.'
                    : 'Click the microphone button below to talk.'}
                </p>
              </div>
            )}

            {/* Typing Input Form ("Type something...") */}
            <form
              onSubmit={handleSubmitText}
              className="flex items-center gap-1.5 border-t border-border/50 px-3 py-2 bg-muted/20"
            >
              <input
                type="text"
                data-testid="agent-chat-input"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Type something..."
                disabled={sending || agent.busy}
                className="flex-1 bg-transparent px-2.5 py-1 text-xs text-foreground placeholder:text-muted-foreground/70 focus:outline-hidden"
              />
              <Button
                type="submit"
                variant="ghost"
                size="icon-xs"
                data-testid="agent-send-btn"
                disabled={!draft.trim() || sending || agent.busy}
                className="h-7 w-7 rounded-lg text-primary hover:bg-primary/10 disabled:opacity-40"
                title="Send message"
                aria-label="Send message"
              >
                <Send className="h-3.5 w-3.5" />
              </Button>
            </form>
          </div>
            </>
          )}

          {/* Bottom Agent Control Bar */}
          <footer className="flex items-center justify-between border-t border-border/60 px-3 py-2 bg-card">
            {/* Microphone Mute Toggle & Device Dropdown */}
            <div className="flex items-center gap-1">
              {controls.microphone !== false && (
                <div className="flex items-center rounded-lg border border-border/80 bg-muted/30 p-0.5">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      if (!isSessionActive) {
                        void startVoice()
                      } else {
                        void toggleMute()
                      }
                    }}
                    className={cn(
                      'h-7 px-2 gap-1.5 text-xs font-medium rounded-md transition-colors',
                      isMuted
                        ? 'text-muted-foreground hover:text-foreground'
                        : isLive
                          ? 'text-emerald-600 hover:bg-emerald-500/10'
                          : 'text-foreground',
                    )}
                    title={isMuted ? 'Unmute microphone' : 'Mute microphone'}
                    aria-label={isMuted ? 'Unmute microphone' : 'Mute microphone'}
                  >
                    {isMuted ? (
                      <MicOff className="h-3.5 w-3.5 text-destructive" />
                    ) : (
                      <Mic className="h-3.5 w-3.5" />
                    )}
                    <ThreeBarVisualizer isActive={isLive} isMuted={isMuted} />
                  </Button>

                  {/* Device selector dropdown */}
                  {audioDevices.length > 0 && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          className="h-7 w-5 px-0 text-muted-foreground hover:text-foreground"
                          title={`Select microphone device (Current: ${activeDeviceLabel})`}
                          aria-label={`Select microphone device (Current: ${activeDeviceLabel})`}
                        >
                          <ChevronDown className="h-3 w-3" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start" className="w-56 text-xs">
                        <DropdownMenuLabel className="text-[11px]">
                          Audio Input Device
                        </DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        {audioDevices.map((device) => (
                          <DropdownMenuItem
                            key={device.deviceId}
                            onClick={() => void switchAudioDevice(device.deviceId)}
                            className="flex items-center justify-between text-xs"
                          >
                            <span className="truncate">{device.label || 'Microphone'}</span>
                            {device.deviceId === activeAudioDeviceId && (
                              <span className="text-emerald-500 text-[10px]">Active</span>
                            )}
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </div>
              )}
            </div>

            {/* Media Toggles (Camera, Screen Share, Transcript) */}
            <div className="flex items-center gap-1">
              {/* Camera Toggle */}
              {controls.camera !== false && (
                <Button
                  type="button"
                  variant={isCameraActive ? 'default' : 'ghost'}
                  size="icon-xs"
                  onClick={toggleCamera}
                  className={cn(
                    'h-7 w-7 rounded-lg transition-colors',
                    isCameraActive
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                  title={isCameraActive ? 'Turn off camera' : 'Turn on camera'}
                  aria-label={isCameraActive ? 'Turn off camera' : 'Turn on camera'}
                >
                  {isCameraActive ? (
                    <Camera className="h-3.5 w-3.5" />
                  ) : (
                    <CameraOff className="h-3.5 w-3.5" />
                  )}
                </Button>
              )}

              {/* Screen Share Toggle */}
              {controls.screenShare !== false && (
                <Button
                  type="button"
                  variant={isScreenSharing ? 'default' : 'ghost'}
                  size="icon-xs"
                  onClick={toggleScreenShare}
                  className={cn(
                    'h-7 w-7 rounded-lg transition-colors',
                    isScreenSharing
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                  title={isScreenSharing ? 'Stop sharing screen' : 'Share screen'}
                  aria-label={isScreenSharing ? 'Stop sharing screen' : 'Share screen'}
                >
                  {isScreenSharing ? (
                    <Monitor className="h-3.5 w-3.5" />
                  ) : (
                    <MonitorOff className="h-3.5 w-3.5" />
                  )}
                </Button>
              )}

              {/* Transcript/Chat Toggle */}
              {controls.chat !== false && (
                <Button
                  type="button"
                  variant={showTranscript ? 'secondary' : 'ghost'}
                  size="icon-xs"
                  onClick={() => setShowTranscript((prev) => !prev)}
                  className={cn(
                    'h-7 w-7 rounded-lg transition-colors',
                    showTranscript
                      ? 'bg-muted font-semibold text-foreground'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                  title={showTranscript ? 'Hide transcript' : 'Show transcript'}
                  aria-label={showTranscript ? 'Hide transcript' : 'Show transcript'}
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                </Button>
              )}

              {/* Leave / End Call Button */}
              {controls.leave !== false && isSessionActive && (
                <Button
                  type="button"
                  variant="destructive"
                  size="icon-xs"
                  onClick={handleLeaveSession}
                  className="h-7 w-7 rounded-lg shadow-2xs ml-1"
                  title="End voice session"
                  aria-label="End voice session"
                  data-testid="agent-popup-leave-button"
                >
                  <PhoneOff className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </footer>
        </aside>
      )}

      {/* Compact Floating Active Session Pill (shown when minimized and voice active) */}
      {!drawerOpen && isSessionActive && (
        <aside
          role="status"
          aria-live="polite"
          data-testid="agent-popup-active-pill"
          className="fixed right-[calc(max(1.25rem,env(safe-area-inset-right))+4.5rem)] bottom-[max(1.25rem,env(safe-area-inset-bottom))] z-50 flex items-center gap-2 rounded-full border border-emerald-500/40 bg-card/95 px-3.5 py-2 shadow-xl backdrop-blur-md transition-all duration-200 animate-in fade-in slide-in-from-right-4"
        >
          <button
            type="button"
            onClick={openDrawer}
            className="flex items-center gap-2 text-left cursor-pointer focus:outline-hidden"
            title="Assistant Active — Click to expand"
            aria-label="Assistant Active — Click to expand"
          >
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
            </span>
            <ThreeBarVisualizer isActive={isLive} isMuted={isMuted} />
            <div className="flex flex-col">
              <span className="text-[11px] font-semibold text-foreground leading-tight">
                Assistant Active
              </span>
              <span className="text-[9px] text-muted-foreground leading-tight">
                {isMuted ? 'Muted · Click to expand' : 'Listening · Click to expand'}
              </span>
            </div>
          </button>

          <div className="h-4 w-px bg-border/80 mx-0.5" />

          {/* Quick Mute in Pill */}
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            onClick={() => void toggleMute()}
            title={isMuted ? 'Unmute microphone' : 'Mute microphone'}
            aria-label={isMuted ? 'Unmute microphone' : 'Mute microphone'}
            className="h-6 w-6 rounded-full text-muted-foreground hover:text-foreground"
          >
            {isMuted ? (
              <MicOff className="h-3 w-3 text-destructive" />
            ) : (
              <Mic className="h-3 w-3 text-emerald-500" />
            )}
          </Button>

          {/* Quick Hang Up in Pill */}
          <Button
            type="button"
            variant="destructive"
            size="icon-xs"
            onClick={handleLeaveSession}
            title="End voice session"
            aria-label="End voice session"
            className="h-6 w-6 rounded-full"
            data-testid="pill-leave-button"
          >
            <PhoneOff className="h-3 w-3" />
          </Button>
        </aside>
      )}

      {/* Floating Circular Trigger Button (bottom-right) */}
      <button
        type="button"
        onClick={handleTriggerClick}
        data-testid="livekit-agent-popup-trigger"
        aria-label={drawerOpen ? 'Minimize Assistant' : 'Open Business Assistant'}
        aria-expanded={drawerOpen}
        style={triggerColor ? { backgroundColor: triggerColor } : undefined}
        className={cn(
          'fixed right-[max(1.25rem,env(safe-area-inset-right))] bottom-[max(1.25rem,env(safe-area-inset-bottom))] z-50',
          'flex h-13 w-13 sm:h-14 sm:w-14 items-center justify-center rounded-full shadow-2xl transition-all duration-200',
          'focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
          'hover:scale-105 active:scale-95 cursor-pointer',
          drawerOpen
            ? 'bg-primary text-primary-foreground ring-2 ring-primary/30'
            : isSessionActive
              ? 'bg-primary text-primary-foreground ring-2 ring-emerald-500/50 shadow-emerald-500/30'
              : 'bg-primary text-primary-foreground shadow-primary/30',
        )}
      >
        <Bot className="h-6 w-6" aria-hidden="true" />
      </button>
    </>
  )
}

export const AgentPopup_01 = AgentPopup
