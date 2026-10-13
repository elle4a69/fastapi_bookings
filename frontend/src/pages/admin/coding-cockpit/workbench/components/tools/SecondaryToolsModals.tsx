import React from 'react'
import {
  Activity,
  Zap,
  Wrench,
  BookOpen,
  Radio,
  X
} from 'lucide-react'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '../ui/dialog'
import { Badge } from '@/components/ui/badge'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { HealthSentinels } from '../../../HealthSentinels'
import { StressFuzzer } from '../../../StressFuzzer'
import { IssuesStudio } from '../../../IssuesStudio'
import { SkillsBrowser } from '../../../SkillsBrowser'
import { EventStream } from '../../../EventStream'
import type { AgentStatusData } from '../../../types'

interface SecondaryToolsModalsProps {
  statusData?: AgentStatusData | null
  loadingStatus?: boolean
  onRefreshStatus?: () => Promise<void>
}

export const SecondaryToolsModals: React.FC<SecondaryToolsModalsProps> = ({
  statusData,
  loadingStatus,
  onRefreshStatus
}) => {
  const { state, setActiveToolModal, selectThread } = useWorkbenchStore()
  const activeTool = state.activeToolModal

  if (!activeTool) return null

  const getToolMeta = () => {
    switch (activeTool) {
      case 'health':
        return {
          title: 'SRE Health Sentinels',
          subtitle: 'Automated reliability metrics, error rates, and system pulse diagnostics',
          icon: <Activity className="w-4 h-4 text-emerald-400" />,
          badge: statusData ? (
            <Badge variant="outline" className="text-[10px] h-4 px-1.5 border-emerald-500/40 text-emerald-400 bg-emerald-500/10">
              {statusData.health_score ?? 100}% Health
            </Badge>
          ) : null
        }
      case 'fuzzer':
        return {
          title: 'Concurrency Stress Fuzzer',
          subtitle: 'Simulate high-concurrency race conditions, mutex serialization, and drain tests',
          icon: <Zap className="w-4 h-4 text-amber-400" />,
          badge: null
        }
      case 'issues':
        return {
          title: 'AST Issues Studio',
          subtitle: 'Static analysis violations, AST syntax discrepancies, and autonomous remediation',
          icon: <Wrench className="w-4 h-4 text-blue-400" />,
          badge: (statusData?.active_issues?.length ?? 0) > 0 ? (
            <Badge variant="outline" className="text-[10px] h-4 px-1.5 border-amber-500/40 text-amber-400 bg-amber-500/10">
              {statusData?.active_issues?.length} Active
            </Badge>
          ) : null
        }
      case 'skills':
        return {
          title: 'Engineering Skills Library',
          subtitle: 'Searchable repository of vetted coding directives, architectural patterns, and capabilities',
          icon: <BookOpen className="w-4 h-4 text-purple-400" />,
          badge: null
        }
      case 'stream':
        return {
          title: 'Real-time Event Stream',
          subtitle: 'Live SSE telemetry feed of resident agent actions, tool invocations, and kernel logs',
          icon: <Radio className="w-4 h-4 text-cyan-400" />,
          badge: null
        }
      default:
        return {
          title: 'Engineering Tool',
          subtitle: 'Secondary diagnostic workspace',
          icon: <Wrench className="w-4 h-4 text-indigo-400" />,
          badge: null
        }
    }
  }

  const { title, subtitle, icon, badge } = getToolMeta()

  return (
    <Dialog open={Boolean(activeTool)} onOpenChange={(open) => !open && setActiveToolModal(null)}>
      <DialogContent className="w-full max-w-[96vw] md:max-w-7xl h-[94vh] p-0 overflow-hidden flex flex-col bg-card border border-border shadow-2xl rounded-xl text-card-foreground">
        <DialogTitle className="sr-only">{title}</DialogTitle>
        <DialogDescription className="sr-only">{subtitle}</DialogDescription>

        {/* Modal Top Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card/95 shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-muted text-foreground border border-border flex items-center justify-center shrink-0">
              {icon}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="font-semibold text-sm text-foreground truncate m-0">
                  {title}
                </h2>
                {badge}
              </div>
              <p className="text-[11px] text-muted-foreground truncate m-0">
                {subtitle}
              </p>
            </div>
          </div>

          <button
            onClick={() => setActiveToolModal(null)}
            className="h-8 w-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
            aria-label="Close Tool Modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Content Body */}
        <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 bg-background">
          {activeTool === 'health' && (
            <div className="max-w-6xl mx-auto">
              <HealthSentinels
                statusData={statusData || null}
                loadingStatus={Boolean(loadingStatus)}
                onRefresh={onRefreshStatus || (async () => {})}
              />
            </div>
          )}

          {activeTool === 'fuzzer' && (
            <div className="max-w-6xl mx-auto">
              <StressFuzzer />
            </div>
          )}

          {activeTool === 'issues' && (
            <div className="max-w-6xl mx-auto">
              <IssuesStudio
                statusData={statusData || null}
                onRefresh={onRefreshStatus || (async () => {})}
                onSwitchToWorkbench={(threadId) => {
                  setActiveToolModal(null)
                  if (threadId) {
                    selectThread(threadId)
                  }
                }}
              />
            </div>
          )}

          {activeTool === 'skills' && (
            <div className="max-w-6xl mx-auto">
              <SkillsBrowser />
            </div>
          )}

          {activeTool === 'stream' && (
            <div className="max-w-6xl mx-auto">
              <EventStream />
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default SecondaryToolsModals
