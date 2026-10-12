import { useState, useEffect, type FormEvent } from 'react'
import { Cloud, Radio, Server, Settings, Zap } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
    updateTransportConfig,
    voiceState,
  } = useBusinessAssistant()

  const [isConfigOpen, setIsConfigOpen] = useState(false)
  const [cloudUrl, setCloudUrl] = useState(
    transportDetails?.cloud_livekit_url || 'wss://live-agent-project-1j5q9yfo.livekit.cloud',
  )
  const [cloudApiKey, setCloudApiKey] = useState('')
  const [cloudApiSecret, setCloudApiSecret] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Initialize transport from localStorage on mount if saved
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('business-assistant-transport')
      if (
        saved &&
        ['xai_grok_voice', 'direct_gpt_live', 'local_livekit', 'cloud_livekit'].includes(saved) &&
        saved !== transport
      ) {
        void setTransport(saved as VoiceTransportMode)
      }
    }
  }, [])

  // Do not permanently disable the switcher when connecting or in error; allow the user to switch away anytime
  const isVoiceActive = voiceState === 'live'

  const handleSelectMode = async (mode: VoiceTransportMode) => {
    if (mode === transport || isVoiceActive) return
    if (typeof window !== 'undefined') {
      localStorage.setItem('business-assistant-transport', mode)
    }
    await setTransport(mode)
  }

  const handleSaveCloudConfig = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      await updateTransportConfig({
        transport: 'cloud_livekit',
        cloud_livekit_url: cloudUrl,
        cloud_livekit_api_key: cloudApiKey || undefined,
        cloud_livekit_api_secret: cloudApiSecret || undefined,
      })
      setIsConfigOpen(false)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save LiveKit Cloud configuration')
    } finally {
      setSaving(false)
    }
  }

  const getModeLabel = (mode: VoiceTransportMode): string => {
    switch (mode) {
      case 'xai_grok_voice':
        return 'Grok Voice'
      case 'direct_gpt_live':
        return 'Direct WebRTC'
      case 'cloud_livekit':
        return 'LiveKit Cloud'
      case 'local_livekit':
      case 'livekit_gpt_live':
      default:
        return 'LiveKit Local'
    }
  }

  const activeModeCanonical: 'xai_grok_voice' | 'direct_gpt_live' | 'local_livekit' | 'cloud_livekit' =
    transport === 'xai_grok_voice'
      ? 'xai_grok_voice'
      : transport === 'direct_gpt_live'
        ? 'direct_gpt_live'
        : transport === 'cloud_livekit'
          ? 'cloud_livekit'
          : 'local_livekit'

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
        className="grid grid-cols-4 gap-1 rounded-md bg-muted/50 p-1"
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
          <span className="truncate">Grok</span>
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
              ? 'bg-background text-foreground shadow-xs'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          title={
            isVoiceActive
              ? 'Cannot switch transport while voice session is active'
              : 'Direct WebRTC (Stand-Alone) - Connects directly without LiveKit server'
          }
        >
          <Radio className="h-3 w-3 shrink-0" aria-hidden="true" />
          <span className="truncate">Direct</span>
        </button>

        {/* Mode 3: Local LiveKit */}
        <button
          type="button"
          role="radio"
          disabled={isVoiceActive}
          aria-checked={activeModeCanonical === 'local_livekit'}
          data-testid="transport-option-local"
          onClick={() => void handleSelectMode('local_livekit')}
          className={`flex items-center justify-center gap-1 rounded px-2 py-1.5 text-[11px] font-medium transition-all ${
            isVoiceActive ? 'opacity-50 cursor-not-allowed' : ''
          } ${
            activeModeCanonical === 'local_livekit'
              ? 'bg-background text-foreground shadow-xs'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          title={
            isVoiceActive
              ? 'Cannot switch transport while voice session is active'
              : 'Local LiveKit - Local server on ws://127.0.0.1:7880'
          }
        >
          <Server className="h-3 w-3 shrink-0" aria-hidden="true" />
          <span className="truncate">Local</span>
        </button>

        {/* Mode 4: LiveKit Cloud */}
        <button
          type="button"
          role="radio"
          disabled={isVoiceActive}
          aria-checked={activeModeCanonical === 'cloud_livekit'}
          data-testid="transport-option-cloud"
          onClick={() => void handleSelectMode('cloud_livekit')}
          className={`flex items-center justify-center gap-1 rounded px-2 py-1.5 text-[11px] font-medium transition-all ${
            isVoiceActive ? 'opacity-50 cursor-not-allowed' : ''
          } ${
            activeModeCanonical === 'cloud_livekit'
              ? 'bg-background text-foreground shadow-xs'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          title={
            isVoiceActive
              ? 'Cannot switch transport while voice session is active'
              : 'LiveKit Cloud - Remote LiveKit Cloud project'
          }
        >
          <Cloud className="h-3 w-3 shrink-0" aria-hidden="true" />
          <span className="truncate">Cloud</span>
        </button>
      </div>

      {/* Target status / config link */}
      <div className="flex items-center justify-between text-[11px] text-muted-foreground px-1">
        <span className="truncate font-mono text-[10px]">
          Target: {transportDetails?.active_target || (activeModeCanonical === 'xai_grok_voice' ? 'wss://api.x.ai/v1/realtime' : activeModeCanonical === 'direct_gpt_live' ? '/voice/realtime' : activeModeCanonical === 'local_livekit' ? 'ws://127.0.0.1:7880' : 'LiveKit Cloud')}
        </span>
        <button
          type="button"
          onClick={() => setIsConfigOpen((v) => !v)}
          className="flex items-center gap-1 text-primary hover:underline ml-1 shrink-0"
          data-testid="toggle-cloud-config-button"
          title="Configure Cloud credentials"
        >
          <Settings className="h-3 w-3" aria-hidden="true" />
          <span>Config</span>
        </button>
      </div>

      {/* Cloud Configuration Modal / Drawer Inline Form */}
      {isConfigOpen && (
        <form
          onSubmit={handleSaveCloudConfig}
          className="flex flex-col gap-2 rounded-md border border-border bg-background p-2.5 text-xs shadow-xs mt-1 animate-in fade-in"
          data-testid="cloud-config-form"
        >
          <div className="font-semibold text-foreground">LiveKit Cloud Project Settings</div>
          {saveError && (
            <div className="rounded bg-destructive/10 p-1.5 text-[11px] text-destructive">
              {saveError}
            </div>
          )}
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-muted-foreground">Cloud URL (wss://&lt;project&gt;.livekit.cloud)</span>
            <input
              type="text"
              value={cloudUrl}
              onChange={(e) => setCloudUrl(e.target.value)}
              placeholder="wss://<project>.livekit.cloud"
              className="h-7 rounded border bg-card px-2 text-xs text-foreground font-mono"
              required
              data-testid="cloud-url-input"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-muted-foreground">API Key</span>
            <input
              type="text"
              value={cloudApiKey}
              onChange={(e) => setCloudApiKey(e.target.value)}
              placeholder={transportDetails?.cloud_livekit_api_key_masked || 'API Key'}
              className="h-7 rounded border bg-card px-2 text-xs text-foreground font-mono"
              data-testid="cloud-api-key-input"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] text-muted-foreground">API Secret</span>
            <input
              type="password"
              value={cloudApiSecret}
              onChange={(e) => setCloudApiSecret(e.target.value)}
              placeholder={transportDetails?.cloud_livekit_api_secret_masked || 'API Secret'}
              className="h-7 rounded border bg-card px-2 text-xs text-foreground font-mono"
              data-testid="cloud-api-secret-input"
            />
          </label>
          <div className="flex justify-end gap-1.5 pt-1">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => setIsConfigOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              className="h-7 px-3 text-xs"
              disabled={saving}
              data-testid="save-cloud-config-button"
            >
              {saving ? 'Saving…' : 'Save & Switch'}
            </Button>
          </div>
        </form>
      )}
    </div>
  )
}
