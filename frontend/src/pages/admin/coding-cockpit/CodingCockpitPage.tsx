import React, { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Activity,
  BookOpen,
  Code2,
  Terminal,
  Wrench,
  Zap,
} from 'lucide-react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import { apiClient } from '@/lib/api'

import { CodexWorkbenchTab } from './CodexWorkbenchTab'
import { IssuesStudio } from './IssuesStudio'
import { HealthSentinels } from './HealthSentinels'
import { StressFuzzer } from './StressFuzzer'
import { SkillsBrowser } from './SkillsBrowser'
import { EventStream } from './EventStream'
import type { AgentStatusData } from './types'

interface CodingCockpitPageProps {
  initialTab?: string
}

export const CodingCockpitPage: React.FC<CodingCockpitPageProps> = ({ initialTab }) => {
  const [searchParams, setSearchParams] = useSearchParams()

  // Map legacy tabs like 'coding' to 'workbench'
  const resolveTab = (tabValue: string | null): string => {
    if (!tabValue) return 'workbench'
    if (tabValue === 'coding' || tabValue === 'studio') return 'workbench'
    if (['workbench', 'issues', 'health', 'fuzzer', 'skills', 'stream'].includes(tabValue)) {
      return tabValue
    }
    return 'workbench'
  }

  const currentTab = resolveTab(searchParams.get('tab') || initialTab || 'workbench')
  const [activeTab, setActiveTab] = useState<string>(currentTab)
  const [statusData, setStatusData] = useState<AgentStatusData | null>(null)
  const [loadingStatus, setLoadingStatus] = useState<boolean>(false)
  const [targetThreadId, setTargetThreadId] = useState<string | undefined>(undefined)

  const handleTabChange = (val: string) => {
    setActiveTab(val)
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('tab', val)
        return next
      },
      { replace: true }
    )
  }

  // Fetch System Status Baseline
  const fetchStatus = useCallback(async () => {
    try {
      setLoadingStatus(true)
      const res = await apiClient.get<AgentStatusData>('/api/admin/resident-agent/status')
      const data = (res as any)?.data ?? res
      setStatusData(data)
    } catch (err: any) {
      toast.error('Failed to load system baseline status: ' + (err.message || 'Unknown error'))
    } finally {
      setLoadingStatus(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const handleSwitchToWorkbench = (threadId?: string) => {
    if (threadId) {
      setTargetThreadId(threadId)
    }
    handleTabChange('workbench')
  }

  return (
    <div className="w-full max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
      {/* Top Header & Breadcrumbs */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b pb-5">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground mb-1">
            <span>Admin</span>
            <span>/</span>
            <span>Compliance & System</span>
            <span>/</span>
            <span className="text-foreground font-semibold">Engineering Cockpit</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
              <span className="p-2 rounded-xl bg-primary/10 text-primary border border-primary/20">
                <Code2 className="w-6 h-6" />
              </span>
              Codex Engineering Cockpit
            </h1>
            <Badge
              variant="outline"
              className="text-[11px] font-mono border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10"
            >
              Unified Architecture
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-1 max-w-3xl leading-relaxed">
            Autonomous supervision, AST diagnostics, OpenTelemetry sentinels, concurrency stress testing,
            and native Codex Control Centre workbench execution.
          </p>
        </div>

        {/* Global Status Badges */}
        <div className="flex items-center gap-2.5 shrink-0">
          <Badge variant="outline" className="text-xs font-mono py-1 px-2.5 bg-card">
            Health: {statusData?.health_score ?? 100}%
          </Badge>
          <Badge
            variant={statusData?.telemetry_baseline?.telemetry_enabled ? 'default' : 'secondary'}
            className="text-xs font-mono py-1 px-2.5"
          >
            OTel: {statusData?.telemetry_baseline?.telemetry_enabled ? 'Active' : 'Suppressed'}
          </Badge>
          <Badge variant="outline" className="text-xs font-mono py-1 px-2.5 bg-card text-emerald-600 dark:text-emerald-400">
            Worktree Sandbox: Ready
          </Badge>
        </div>
      </header>

      {/* Main Tabbed Interface */}
      <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full space-y-6">
        <div className="overflow-x-auto pb-1">
          <TabsList className="h-11 bg-muted/40 p-1 rounded-xl border flex items-center w-max min-w-full sm:w-auto">
            <TabsTrigger
              value="workbench"
              className="flex items-center gap-2 text-xs font-medium px-4 h-9 rounded-lg"
            >
              <Code2 className="w-4 h-4 text-primary" />
              <span>Codex Workbench</span>
            </TabsTrigger>

            <TabsTrigger
              value="issues"
              className="flex items-center gap-2 text-xs font-medium px-4 h-9 rounded-lg"
            >
              <Wrench className="w-4 h-4" />
              <span>Issues & Fix Studio</span>
              {(statusData?.active_issues?.length ?? 0) > 0 && (
                <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-500">
                  {statusData?.active_issues?.length}
                </span>
              )}
            </TabsTrigger>

            <TabsTrigger
              value="health"
              className="flex items-center gap-2 text-xs font-medium px-4 h-9 rounded-lg"
            >
              <Activity className="w-4 h-4" />
              <span>System Health</span>
            </TabsTrigger>

            <TabsTrigger
              value="fuzzer"
              className="flex items-center gap-2 text-xs font-medium px-4 h-9 rounded-lg"
            >
              <Zap className="w-4 h-4 text-amber-500" />
              <span>Stress Fuzzer</span>
            </TabsTrigger>

            <TabsTrigger
              value="skills"
              className="flex items-center gap-2 text-xs font-medium px-4 h-9 rounded-lg"
            >
              <BookOpen className="w-4 h-4" />
              <span>Skills Library</span>
            </TabsTrigger>

            <TabsTrigger
              value="stream"
              className="flex items-center gap-2 text-xs font-medium px-4 h-9 rounded-lg"
            >
              <Terminal className="w-4 h-4" />
              <span>Event Stream</span>
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Tab 1: Native Codex Workbench */}
        <TabsContent value="workbench" className="mt-0 focus-visible:outline-none">
          <CodexWorkbenchTab initialThreadId={targetThreadId} />
        </TabsContent>

        {/* Tab 2: Issues & Fix Studio */}
        <TabsContent value="issues" className="mt-0 focus-visible:outline-none">
          <IssuesStudio
            statusData={statusData}
            onRefresh={fetchStatus}
            onSwitchToWorkbench={handleSwitchToWorkbench}
          />
        </TabsContent>

        {/* Tab 3: System Health & Sentinels */}
        <TabsContent value="health" className="mt-0 focus-visible:outline-none">
          <HealthSentinels
            statusData={statusData}
            loadingStatus={loadingStatus}
            onRefresh={fetchStatus}
          />
        </TabsContent>

        {/* Tab 4: Concurrency Stress Fuzzer */}
        <TabsContent value="fuzzer" className="mt-0 focus-visible:outline-none">
          <StressFuzzer />
        </TabsContent>

        {/* Tab 5: Local Skills Library */}
        <TabsContent value="skills" className="mt-0 focus-visible:outline-none">
          <SkillsBrowser />
        </TabsContent>

        {/* Tab 6: Live Event Stream Log */}
        <TabsContent value="stream" className="mt-0 focus-visible:outline-none">
          <EventStream />
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default CodingCockpitPage
