import React, { useState } from 'react'
import type { CodexView, MobileTab } from './types'
import { CodexVoiceProvider, useOptionalCodexVoice } from './context/CodexVoiceContext'
import { TopBar } from './components/navigation/TopBar'
import { ActivityRail } from './components/navigation/ActivityRail'
import { BottomTabBar } from './components/navigation/BottomTabBar'
import { AudioWaveformStrip } from './components/voice/AudioWaveformStrip'
import { VoiceFAB } from './components/voice/VoiceFAB'
import { LayoutDashboard, Radio } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface CodexV3LayoutProps {
  activeView?: CodexView
  onViewChange?: (view: CodexView) => void
  mobileTab?: MobileTab
  onMobileTabChange?: (tab: MobileTab) => void
  projectName?: string
  activeBranch?: string
  ticketCount?: number
  subagentCount?: number
  signalCount?: number
  streamContent?: React.ReactNode
  children?: React.ReactNode
  initialConversationId?: number | null
}

const CodexV3LayoutInner: React.FC<CodexV3LayoutProps> = ({
  activeView: controlledView,
  onViewChange: controlledOnViewChange,
  mobileTab: controlledTab,
  onMobileTabChange: controlledOnTabChange,
  projectName = 'Codex Control Centre V3',
  activeBranch = 'main',
  ticketCount = 0,
  subagentCount = 0,
  signalCount = 0,
  streamContent,
  children,
}) => {
  const [internalView, setInternalView] = useState<CodexView>('tickets')
  const [internalTab, setInternalTab] = useState<MobileTab>('workspace')

  const activeView = controlledView ?? internalView
  const handleViewChange = controlledOnViewChange ?? setInternalView

  const mobileTab = controlledTab ?? internalTab
  const handleTabChange = controlledOnTabChange ?? setInternalTab

  return (
    <div
      data-testid="codex-v3-layout"
      className="flex flex-col h-screen w-screen overflow-hidden bg-background text-foreground antialiased font-sans"
    >
      {/* 1. Minimal 44px Top Bar */}
      <TopBar projectName={projectName} activeBranch={activeBranch} />

      {/* 2. Realtime Voice Waveform Strip (renders when active) */}
      <AudioWaveformStrip />

      {/* 3. Mobile Segmented Control [ Workspace | Agent Stream ] (<1024px) */}
      <div className="lg:hidden flex items-center justify-center p-2 bg-card/40 border-b border-border/30 select-none z-10">
        <div className="inline-flex rounded-lg p-0.5 bg-muted/70 text-xs border border-border/40 w-full max-w-xs">
          <button
            type="button"
            data-testid="tab-workspace"
            onClick={() => handleTabChange('workspace')}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md font-medium transition-all min-h-[36px]',
              mobileTab === 'workspace'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <LayoutDashboard className="h-3.5 w-3.5" />
            <span>Workspace</span>
          </button>

          <button
            type="button"
            data-testid="tab-stream"
            onClick={() => handleTabChange('stream')}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md font-medium transition-all min-h-[36px] relative',
              mobileTab === 'stream'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Radio className="h-3.5 w-3.5" />
            <span>Agent Stream</span>
            {subagentCount > 0 && (
              <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            )}
          </button>
        </div>
      </div>

      {/* 4. Body Area: Activity Rail + Workspace View + Optional Stream Panel */}
      <div className="flex flex-1 min-h-0 overflow-hidden relative">
        {/* Desktop Slim 52px Activity Rail (>1024px) */}
        <ActivityRail
          activeView={activeView}
          onViewChange={handleViewChange}
          ticketCount={ticketCount}
          activeSubagents={subagentCount}
          signalCount={signalCount}
        />

        {/* Workspace Main Area */}
        <main
          data-testid="codex-workspace-container"
          className={cn(
            'flex-1 min-w-0 h-full overflow-y-auto overflow-x-hidden relative',
            // Safe bottom padding on mobile for thumb-zone BottomTabBar
            'pb-[calc(4.5rem+env(safe-area-inset-bottom,0px))] sm:pb-0',
            mobileTab === 'stream' ? 'hidden lg:block' : 'block',
          )}
        >
          {children || (
            <div className="p-4 sm:p-6 space-y-4">
              <div className="rounded-xl border border-border/50 bg-card p-6 shadow-sm">
                <h2 className="text-lg font-semibold capitalize">{activeView} Workspace</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Active view: <span className="font-mono text-primary font-medium">{activeView}</span>.
                  Mobile tab: <span className="font-mono">{mobileTab}</span>.
                </p>
              </div>
            </div>
          )}
        </main>

        {/* Agent Stream Column / Mobile View */}
        <aside
          data-testid="codex-agent-stream-container"
          className={cn(
            'min-h-0 overflow-y-auto border-l border-border/40 bg-card/30 backdrop-blur-sm',
            'pb-[calc(4.5rem+env(safe-area-inset-bottom,0px))] sm:pb-0',
            // Mobile: shown when tab is 'stream'
            mobileTab === 'stream' ? 'flex-1 block' : 'hidden',
            // Desktop: 360px wide docked stream inspector
            'lg:flex lg:w-[380px] lg:flex-col lg:border-l lg:border-border/40',
          )}
        >
          {streamContent || (
            <div className="p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Live Agent Stream
                </h3>
                {subagentCount > 0 && (
                  <span className="inline-flex items-center gap-1 text-[11px] font-mono text-emerald-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    {subagentCount} active
                  </span>
                )}
              </div>
              <div className="rounded-lg border border-border/40 bg-card/60 p-3 text-xs text-muted-foreground font-mono">
                Stream ready. Live agent events, tool calls, and execution telemetry will render here.
              </div>
            </div>
          )}
        </aside>

        {/* Desktop Floating Voice FAB (when desktop rail is present, bottom right) */}
        <div className="hidden sm:block lg:hidden fixed bottom-6 right-6 z-30">
          <VoiceFAB />
        </div>
      </div>

      {/* 5. Mobile 5-Item Thumb-Zone Bottom Tab Bar (<640px) */}
      <BottomTabBar
        activeView={activeView}
        onViewChange={handleViewChange}
        ticketCount={ticketCount}
        activeSubagents={subagentCount}
        signalCount={signalCount}
      />
    </div>
  )
}

export { CodexV3LayoutInner }

export const CodexV3Layout: React.FC<CodexV3LayoutProps> = (props) => {
  const existingVoiceContext = useOptionalCodexVoice()
  if (existingVoiceContext) {
    return <CodexV3LayoutInner {...props} />
  }
  return (
    <CodexVoiceProvider initialConversationId={props.initialConversationId}>
      <CodexV3LayoutInner {...props} />
    </CodexVoiceProvider>
  )
}

export default CodexV3Layout
