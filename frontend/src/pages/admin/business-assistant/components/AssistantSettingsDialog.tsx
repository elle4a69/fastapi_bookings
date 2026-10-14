import {
  Settings,
  ShieldCheck,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  useBusinessAssistant,
} from '../business-assistant-context'
import { DiagnosticModeToggle } from './DiagnosticModeToggle'
import { VoiceEngineSelector } from './VoiceEngineSelector'

export interface AssistantSettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AssistantSettingsDialog({
  open,
  onOpenChange,
}: AssistantSettingsDialogProps) {
  const {
    transport,
    transportDetails,
    voiceState,
  } = useBusinessAssistant()

  const activeTarget =
    transportDetails?.active_target ||
    (transport === 'direct_gpt_live'
      ? '/api/admin/business-assistant/voice/realtime'
      : 'wss://api.x.ai/v1/realtime')

  const getTransportBadge = () => {
    switch (transport) {
      case 'xai_grok_voice':
        return {
          label: 'xAI Grok Voice',
          color: 'bg-purple-500/10 text-purple-600 border-purple-500/20',
          health: 'Optimal - Direct WebSocket connection to xAI Grok Voice Realtime API (agent_YosGQC2yvTXwpdi7).',
        }
      case 'direct_gpt_live':
      default:
        return {
          label: 'Direct WebRTC (OpenAI GPT-Live)',
          color: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
          health: 'Optimal - Direct browser-to-server connection. No external daemons needed.',
        }
    }
  }

  const transportInfo = getTransportBadge()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-h-[90vh] overflow-y-auto sm:max-w-xl"
        data-testid="assistant-settings-dialog"
      >
        <DialogHeader>
          <div className="flex items-center gap-2 text-primary">
            <Settings className="h-5 w-5" aria-hidden="true" />
            <DialogTitle className="text-lg font-semibold">
              Assistant Voice &amp; Runtime Settings
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs text-muted-foreground">
            Configure direct real-time voice transport engines and diagnostic inspection mode.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2 text-xs">
          {/* Active Status & Health Banner */}
          <div className="rounded-lg border bg-muted/40 p-3 flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
                Connection Health &amp; Active Target
              </span>
              <Badge variant="outline" className={`font-mono text-[10px] ${transportInfo.color}`}>
                {transportInfo.label}
              </Badge>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] pt-1 border-t border-border/50">
              <div>
                <span className="text-muted-foreground">Active Target:</span>
                <p className="font-mono text-[10px] text-foreground truncate mt-0.5">
                  {activeTarget}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">Voice State:</span>
                <p className="font-mono text-[10px] text-foreground capitalize mt-0.5">
                  {voiceState}
                </p>
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground">
              {transportInfo.health}
            </p>
          </div>

          {/* Dual Realtime Voice Engines Selector */}
          <VoiceEngineSelector />

          {/* Diagnostic Inspection Mode */}
          <div className="flex flex-col gap-2">
            <span className="font-semibold text-foreground">Diagnostic Telemetry &amp; Runbook</span>
            <DiagnosticModeToggle />
            <p className="text-[11px] text-muted-foreground px-1">
              Diagnostic Mode arms an 8-step runtime inspection runbook capturing tool calls, WebRTC state snapshots, and error telemetries. Use this when troubleshooting microphone or model connection errors.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            data-testid="close-assistant-settings-dialog"
          >
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
