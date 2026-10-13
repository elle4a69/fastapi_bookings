import React, { useState, useEffect, useCallback } from 'react'
import {
  Terminal,
  Activity,
  Zap,
  Wrench,
  BookOpen,
  Radio,
  ChevronDown,
  ChevronUp,
  Maximize2,
  Minimize2,
  X
} from 'lucide-react'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { apiClient } from '@/lib/api'
import { useWorkbenchStore, type BottomDockTab } from '../../store/useWorkbenchStore'
import { TerminalTab } from '../inspector/tabs/TerminalTab'
import { HealthSentinels } from '../../../HealthSentinels'
import { StressFuzzer } from '../../../StressFuzzer'
import { IssuesStudio } from '../../../IssuesStudio'
import { SkillsBrowser } from '../../../SkillsBrowser'
import { EventStream } from '../../../EventStream'
import type { AgentStatusData } from '../../../types'

interface BottomConsoleDockProps {
  statusData?: AgentStatusData | null
  loadingStatus?: boolean
  onRefreshStatus?: () => Promise<void>
}

export const BottomConsoleDock: React.FC<BottomConsoleDockProps> = ({
  statusData: externalStatusData,
  loadingStatus: externalLoadingStatus,
  onRefreshStatus: externalRefreshStatus
}) => {
  const {
    state,
    setBottomDockOpen,
    setActiveBottomDockTab,
    setBottomDockMode,
    selectThread
  } = useWorkbenchStore()

  // Local fallback status if parent doesn't provide
  const [internalStatusData, setInternalStatusData] = useState<AgentStatusData | null>(null)
  const [internalLoading, setInternalLoading] = useState(false)

  const fetchStatus = useCallback(async () => {
    if (externalRefreshStatus) {
      await externalRefreshStatus()
      return
    }
    try {
      setInternalLoading(true)
      const res = await apiClient.get<AgentStatusData>('/api/admin/resident-agent/status')
      const data = (res as any)?.data ?? res
      setInternalStatusData(data)
    } catch {
      // Ignore background status polling errors
    } finally {
      setInternalLoading(false)
    }
  }, [externalRefreshStatus])

  useEffect(() => {
    if (!externalStatusData) {
      fetchStatus()
    }
  }, [externalStatusData, fetchStatus])

  const statusData = externalStatusData ?? internalStatusData
  const loadingStatus = externalLoadingStatus ?? internalLoading

  const isDockOpen = state.isBottomDockOpen
  const activeTab = state.activeBottomDockTab
  const dockMode = state.bottomDockMode // 'collapsed' | 'expanded' | 'maximized'

  const handleTabChange = (val: string) => {
    setActiveBottomDockTab(val as BottomDockTab)
    if (!isDockOpen) {
      setBottomDockOpen(true)
    }
  }

  const handleSwitchToThread = (threadId?: string) => {
    if (threadId) {
      selectThread(threadId)
    }
    setBottomDockMode('collapsed')
  }

  // If dock is closed/minimized, render compact bottom launcher bar
  if (!isDockOpen || dockMode === 'collapsed') {
    return (
      <div
        className="w-full shrink-0 border-t border-slate-800 bg-slate-900/95 backdrop-blur-xs px-2.5 sm:px-3 py-1 flex items-center justify-between text-xs text-slate-300 z-20 min-h-[38px] select-none"
        aria-label="Console Dock Minimized Bar"
      >
        <div className="flex items-center gap-1 overflow-x-auto scrollbar-none py-0.5">
          <button
            onClick={() => {
              setActiveBottomDockTab('terminal')
              setBottomDockMode('expanded')
            }}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors cursor-pointer text-xs font-medium shrink-0"
          >
            <Terminal className="w-3.5 h-3.5 text-indigo-400" />
            <span>Terminal</span>
          </button>

          <button
            onClick={() => {
              setActiveBottomDockTab('health')
              setBottomDockMode('expanded')
            }}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors cursor-pointer text-xs font-medium shrink-0"
          >
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <span>SRE Health</span>
            <Badge
              variant="outline"
              className="text-[10px] h-4 px-1 border-emerald-500/30 text-emerald-400 bg-emerald-500/10 ml-0.5"
            >
              {statusData?.health_score ?? 100}%
            </Badge>
          </button>

          <button
            onClick={() => {
              setActiveBottomDockTab('fuzzer')
              setBottomDockMode('expanded')
            }}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors cursor-pointer text-xs font-medium shrink-0"
          >
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Stress Fuzzer</span>
          </button>

          <button
            onClick={() => {
              setActiveBottomDockTab('issues')
              setBottomDockMode('expanded')
            }}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors cursor-pointer text-xs font-medium shrink-0"
          >
            <Wrench className="w-3.5 h-3.5 text-blue-400" />
            <span>AST Issues</span>
            {(statusData?.active_issues?.length ?? 0) > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-400 ml-0.5">
                {statusData?.active_issues?.length}
              </span>
            )}
          </button>

          <button
            onClick={() => {
              setActiveBottomDockTab('skills')
              setBottomDockMode('expanded')
            }}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors cursor-pointer text-xs font-medium shrink-0"
          >
            <BookOpen className="w-3.5 h-3.5 text-purple-400" />
            <span>Skills</span>
          </button>

          <button
            onClick={() => {
              setActiveBottomDockTab('stream')
              setBottomDockMode('expanded')
            }}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors cursor-pointer text-xs font-medium shrink-0"
          >
            <Radio className="w-3.5 h-3.5 text-cyan-400" />
            <span>Event Stream</span>
          </button>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setBottomDockOpen(true)
              setBottomDockMode('expanded')
            }}
            className="h-7 px-2 text-xs text-slate-400 hover:text-slate-100 hover:bg-slate-800 gap-1"
            title="Expand Console Dock"
          >
            <ChevronUp className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Console</span>
          </Button>
        </div>
      </div>
    )
  }

  // Expanded or Maximized Dock
  const dockHeightClass = dockMode === 'maximized'
    ? 'h-[80vh] sm:h-[580px]'
    : 'h-[320px] sm:h-[350px]'

  return (
    <section
      className={`w-full shrink-0 flex flex-col border-t border-slate-800 bg-slate-900 text-slate-100 z-20 shadow-2xl transition-all duration-200 overflow-hidden ${dockHeightClass}`}
      aria-label="Integrated Bottom Console Dock"
    >
      {/* Dock Header with Tabs & Controls */}
      <div className="flex items-center justify-between px-2.5 sm:px-3 py-1.5 border-b border-slate-800 bg-slate-950/80 backdrop-blur-xs shrink-0 min-h-[42px]">
        {/* Left: Tab Switcher using Radix Tabs List */}
        <Tabs value={activeTab} onValueChange={handleTabChange} className="w-auto overflow-x-auto scrollbar-none">
          <TabsList className="h-8 bg-slate-900/80 p-0.5 rounded-lg border border-slate-800 flex items-center w-max">
            <TabsTrigger
              value="terminal"
              className="flex items-center gap-1.5 text-xs px-2.5 h-7 rounded text-slate-300 data-[state=active]:bg-slate-800 data-[state=active]:text-white font-medium"
            >
              <Terminal className="w-3.5 h-3.5 text-indigo-400" />
              <span>Terminal</span>
            </TabsTrigger>

            <TabsTrigger
              value="health"
              className="flex items-center gap-1.5 text-xs px-2.5 h-7 rounded text-slate-300 data-[state=active]:bg-slate-800 data-[state=active]:text-white font-medium"
            >
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
              <span>SRE Sentinels</span>
              <Badge
                variant="outline"
                className="text-[9px] h-4 px-1 border-emerald-500/40 text-emerald-400 bg-emerald-500/10 ml-0.5"
              >
                {statusData?.health_score ?? 100}%
              </Badge>
            </TabsTrigger>

            <TabsTrigger
              value="fuzzer"
              className="flex items-center gap-1.5 text-xs px-2.5 h-7 rounded text-slate-300 data-[state=active]:bg-slate-800 data-[state=active]:text-white font-medium"
            >
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span>Stress Fuzzer</span>
            </TabsTrigger>

            <TabsTrigger
              value="issues"
              className="flex items-center gap-1.5 text-xs px-2.5 h-7 rounded text-slate-300 data-[state=active]:bg-slate-800 data-[state=active]:text-white font-medium"
            >
              <Wrench className="w-3.5 h-3.5 text-blue-400" />
              <span>AST Issues</span>
              {(statusData?.active_issues?.length ?? 0) > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-[9px] font-bold bg-amber-500/20 text-amber-400 ml-0.5">
                  {statusData?.active_issues?.length}
                </span>
              )}
            </TabsTrigger>

            <TabsTrigger
              value="skills"
              className="flex items-center gap-1.5 text-xs px-2.5 h-7 rounded text-slate-300 data-[state=active]:bg-slate-800 data-[state=active]:text-white font-medium"
            >
              <BookOpen className="w-3.5 h-3.5 text-purple-400" />
              <span>Skills</span>
            </TabsTrigger>

            <TabsTrigger
              value="stream"
              className="flex items-center gap-1.5 text-xs px-2.5 h-7 rounded text-slate-300 data-[state=active]:bg-slate-800 data-[state=active]:text-white font-medium"
            >
              <Radio className="w-3.5 h-3.5 text-cyan-400" />
              <span>Events</span>
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {/* Right Dock Controls: Maximize/Restore, Minimize, Close */}
        <div className="flex items-center gap-1 ml-2 shrink-0">
          {dockMode === 'maximized' ? (
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={() => setBottomDockMode('expanded')}
              className="h-7 w-7 text-slate-400 hover:text-white hover:bg-slate-800"
              title="Restore standard height"
            >
              <Minimize2 className="w-3.5 h-3.5" />
            </Button>
          ) : (
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={() => setBottomDockMode('maximized')}
              className="h-7 w-7 text-slate-400 hover:text-white hover:bg-slate-800"
              title="Maximize dock height"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </Button>
          )}

          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={() => setBottomDockMode('collapsed')}
            className="h-7 w-7 text-slate-400 hover:text-white hover:bg-slate-800"
            title="Minimize dock"
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </Button>

          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={() => setBottomDockOpen(false)}
            className="h-7 w-7 text-slate-400 hover:text-white hover:bg-slate-800"
            title="Close dock"
          >
            <X className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Dock Content Body */}
      <div className="flex-1 min-h-0 overflow-y-auto bg-slate-950/50 p-2 sm:p-4">
        {activeTab === 'terminal' && (
          <div className="h-full">
            <TerminalTab />
          </div>
        )}

        {activeTab === 'health' && (
          <div className="max-w-6xl mx-auto">
            <HealthSentinels
              statusData={statusData}
              loadingStatus={loadingStatus}
              onRefresh={fetchStatus}
            />
          </div>
        )}

        {activeTab === 'fuzzer' && (
          <div className="max-w-6xl mx-auto">
            <StressFuzzer />
          </div>
        )}

        {activeTab === 'issues' && (
          <div className="max-w-6xl mx-auto">
            <IssuesStudio
              statusData={statusData}
              onRefresh={fetchStatus}
              onSwitchToWorkbench={handleSwitchToThread}
            />
          </div>
        )}

        {activeTab === 'skills' && (
          <div className="max-w-6xl mx-auto">
            <SkillsBrowser />
          </div>
        )}

        {activeTab === 'stream' && (
          <div className="max-w-6xl mx-auto">
            <EventStream />
          </div>
        )}
      </div>
    </section>
  )
}
export default BottomConsoleDock
