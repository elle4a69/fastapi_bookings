import React, { useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileCheck,
  FileCode,
  History,
  RefreshCw,
  Search,
  Sparkles,
  Wrench,
  Zap,
  ExternalLink,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'
import { apiClient } from '@/lib/api'
import { codexApi } from './workbench/api/codexApi'
import { getLastUsedCodexModel } from './workbench/modelCatalog'
import { useWorkbenchStore } from './workbench/store/useWorkbenchStore'
import type { AgentIssue, RemediationPlan, AgentStatusData } from './types'

interface IssuesStudioProps {
  statusData: AgentStatusData | null
  onRefresh: () => Promise<void>
  onSwitchToWorkbench?: (threadId?: string) => void
}

export const IssuesStudio: React.FC<IssuesStudioProps> = ({
  statusData,
  onRefresh,
  onSwitchToWorkbench,
}) => {
  const [selectedIssue, setSelectedIssue] = useState<AgentIssue | null>(
    statusData?.active_issues?.[0] || null
  )
  const [activePlan, setActivePlan] = useState<RemediationPlan | null>(null)
  const [planningFix, setPlanningFix] = useState<boolean>(false)
  const [fixApproved, setFixApproved] = useState<boolean>(false)
  const [executingFix, setExecutingFix] = useState<boolean>(false)
  const [executionResult, setExecutionResult] = useState<{
    success: boolean
    message: string
    threadId?: string
  } | null>(null)

  const { selectThread, state } = useWorkbenchStore()

  // Generate Remediation Plan
  const handleGeneratePlan = async (issue: AgentIssue) => {
    try {
      setPlanningFix(true)
      setActivePlan(null)
      setExecutionResult(null)
      setFixApproved(false)
      setSelectedIssue(issue)

      const res = await apiClient.post<RemediationPlan>('/api/admin/resident-agent/plan-fix', {
        issue_id: issue.id,
        issue_title: issue.title,
        category: issue.category,
        context: { description: issue.description, severity: issue.severity },
      })

      const plan = (res as any)?.data ?? res
      setActivePlan(plan)
      toast.success(`Remediation plan generated for ${issue.id}`)
    } catch (err: any) {
      toast.error('Failed to generate remediation plan: ' + (err.message || 'Error occurred'))
    } finally {
      setPlanningFix(false)
    }
  }

  // Rewired Execute Fix: dispatches directly into isolated Codex worktree sandbox!
  const handleExecuteFix = async () => {
    if (!activePlan) return
    if (!fixApproved) {
      toast.error('Explicit approval is required before executing changes.')
      return
    }

    try {
      setExecutingFix(true)
      setExecutionResult(null)

      // 1. Resolve project ID (default to first active project or root)
      const targetProjectId = state.activeProjectId || state.projects[0]?.id || 'fastapi-bookings'

      // 2. Create isolated remediation thread in Codex Control Centre
      const thread = await codexApi.createThread({
        project_id: targetProjectId,
        title: `Fix ${activePlan.issue_id}: ${activePlan.title}`,
      })

      // 3. Dispatch remediation prompt into isolated worktree sandbox turn
      const remediationPrompt = [
        `Execute approved remediation plan for issue ${activePlan.issue_id} (${activePlan.title}):`,
        '',
        '## Root Cause Analysis:',
        activePlan.root_cause_analysis,
        '',
        '## Proposed File Modifications & Diffs:',
        JSON.stringify(activePlan.proposed_modifications, null, 2),
        '',
        '## Verification Steps to Execute:',
        ...activePlan.verification_steps.map((s, idx) => `${idx + 1}. ${s}`),
        '',
        '## Rollback Procedures if Verification Fails:',
        ...activePlan.rollback_steps.map((s, idx) => `${idx + 1}. ${s}`),
        '',
        'Please inspect the git worktree, apply the exact proposed edits, run the verification commands, and report the verified result.',
      ].join('\n')

      await codexApi.startTurn({
        thread_id: thread.id,
        prompt: remediationPrompt,
        model: getLastUsedCodexModel(),
        reasoning_effort: 'high',
      })

      // 4. Update UI state with success & thread reference
      setExecutionResult({
        success: true,
        message: `Remediation dispatched into isolated Codex worktree sandbox (Thread: ${thread.id}).`,
        threadId: thread.id,
      })

      // Select thread in workbench store
      selectThread(thread.id)

      toast.success(`Fix dispatched to isolated Codex sandbox! Thread ID: ${thread.id}`)
    } catch (err: any) {
      const errMsg = err?.message || 'Failed dispatching fix to Codex sandbox'
      setExecutionResult({
        success: false,
        message: errMsg,
      })
      toast.error(errMsg)
    } finally {
      setExecutingFix(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Issues List */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-amber-500" />
              Detected Issues ({statusData?.active_issues?.length ?? 0})
            </h2>
            <Button variant="ghost" size="sm" onClick={onRefresh} className="h-7 text-xs">
              <RefreshCw className="w-3 h-3 mr-1" /> Refresh
            </Button>
          </div>

          {!statusData?.active_issues || statusData.active_issues.length === 0 ? (
            <Card className="border-dashed p-8 text-center bg-card/50">
              <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
              <h3 className="font-semibold text-sm">No Active Issues Detected</h3>
              <p className="text-xs text-muted-foreground mt-1">
                All AST syntax trees, telemetry pipelines, outbox queues, and codebase checks are currently clean.
              </p>
            </Card>
          ) : (
            <div className="space-y-3">
              {statusData.active_issues.map((issue) => {
                const isSelected = selectedIssue?.id === issue.id
                return (
                  <Card
                    key={issue.id}
                    onClick={() => setSelectedIssue(issue)}
                    className={`cursor-pointer transition-all border shadow-xs ${
                      isSelected
                        ? 'border-primary ring-1 ring-primary bg-primary/5'
                        : 'hover:border-border/80 hover:bg-muted/30'
                    }`}
                  >
                    <CardHeader className="p-4 pb-2">
                      <div className="flex items-start justify-between gap-2">
                        <Badge
                          variant={
                            issue.severity === 'CRITICAL'
                              ? 'destructive'
                              : issue.severity === 'WARNING'
                              ? 'secondary'
                              : 'outline'
                          }
                          className="text-[10px] uppercase font-bold"
                        >
                          {issue.severity}
                        </Badge>
                        <span className="text-[11px] font-mono text-muted-foreground">{issue.id}</span>
                      </div>
                      <CardTitle className="text-sm font-semibold mt-1.5">{issue.title}</CardTitle>
                    </CardHeader>
                    <CardContent className="p-4 pt-0">
                      <p className="text-xs text-muted-foreground line-clamp-2">{issue.description}</p>
                      <div className="mt-3 flex items-center justify-between">
                        <span className="text-[11px] text-muted-foreground font-mono">
                          {issue.category}
                        </span>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 text-xs"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleGeneratePlan(issue)
                          }}
                        >
                          Fix Plan <ArrowRight className="w-3 h-3 ml-1" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          )}
        </div>

        {/* Right: Remediation Plan & Sandbox Dispatch Studio */}
        <div className="lg:col-span-7">
          {activePlan ? (
            <Card className="border shadow-md bg-card">
              <CardHeader className="border-b bg-muted/20 pb-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-mono text-xs">
                      {activePlan.plan_id}
                    </Badge>
                    <Badge
                      variant={activePlan.severity === 'CRITICAL' ? 'destructive' : 'secondary'}
                      className="text-xs"
                    >
                      {activePlan.severity}
                    </Badge>
                  </div>
                  <Badge variant="outline" className="text-xs font-mono">
                    Requires Explicit Approval
                  </Badge>
                </div>
                <CardTitle className="text-base font-bold mt-2 text-foreground">{activePlan.title}</CardTitle>
                <CardDescription className="text-xs">
                  Generated at {new Date(activePlan.created_at).toLocaleTimeString()}
                </CardDescription>
              </CardHeader>

              <CardContent className="p-6 space-y-5">
                {/* RCA */}
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1.5">
                    <Search className="w-3.5 h-3.5 text-primary" /> Root Cause Analysis (RCA)
                  </h4>
                  <p className="text-xs bg-muted/50 p-3 rounded-lg border leading-relaxed text-foreground">
                    {activePlan.root_cause_analysis}
                  </p>
                </div>

                {/* Proposed Diffs */}
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
                    <FileCode className="w-3.5 h-3.5 text-primary" /> Proposed File Modifications & Diffs
                  </h4>
                  {activePlan.proposed_modifications.map((mod, idx) => (
                    <div key={idx} className="space-y-1.5 mb-3">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-mono font-semibold text-primary">{mod.file_path}</span>
                        <span className="text-muted-foreground text-[11px]">{mod.description}</span>
                      </div>
                      <pre className="text-[11px] font-mono bg-zinc-950 text-zinc-100 p-3 rounded-lg overflow-x-auto border border-zinc-800 leading-normal">
                        <code>{mod.diff}</code>
                      </pre>
                    </div>
                  ))}
                </div>

                {/* Verification & Rollback */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="bg-muted/30 p-3 rounded-lg border space-y-1.5">
                    <span className="font-semibold text-foreground flex items-center gap-1">
                      <FileCheck className="w-3.5 h-3.5 text-emerald-500" /> Automated Verification Steps
                    </span>
                    <ul className="list-disc list-inside text-muted-foreground space-y-1 text-[11px]">
                      {activePlan.verification_steps.map((v, i) => (
                        <li key={i}>{v}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="bg-muted/30 p-3 rounded-lg border space-y-1.5">
                    <span className="font-semibold text-foreground flex items-center gap-1">
                      <History className="w-3.5 h-3.5 text-amber-500" /> Safe Rollback Procedures
                    </span>
                    <ul className="list-disc list-inside text-muted-foreground space-y-1 text-[11px]">
                      {activePlan.rollback_steps.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Execution Result Feedback */}
                {executionResult && (
                  <div
                    className={`p-4 rounded-lg border text-xs flex items-start justify-between gap-3 ${
                      executionResult.success
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-800 dark:text-emerald-300'
                        : 'bg-destructive/10 border-destructive/30 text-destructive'
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      {executionResult.success ? (
                        <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5 text-emerald-500" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                      )}
                      <div>
                        <div className="font-bold">
                          {executionResult.success ? 'Dispatched to Codex Sandbox' : 'Dispatch Failed'}
                        </div>
                        <p className="mt-0.5">{executionResult.message}</p>
                      </div>
                    </div>

                    {executionResult.success && onSwitchToWorkbench && (
                      <Button
                        size="sm"
                        variant="default"
                        onClick={() => onSwitchToWorkbench(executionResult.threadId)}
                        className="h-8 text-xs shrink-0 gap-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                      >
                        Open in Workbench <ExternalLink className="w-3.5 h-3.5 ml-1" />
                      </Button>
                    )}
                  </div>
                )}
              </CardContent>

              <CardFooter className="border-t bg-muted/20 p-4 flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="approve-switch"
                    checked={fixApproved}
                    onCheckedChange={setFixApproved}
                  />
                  <Label htmlFor="approve-switch" className="text-xs font-semibold cursor-pointer">
                    Approve remediation modifications
                  </Label>
                </div>

                <Button
                  onClick={handleExecuteFix}
                  disabled={executingFix || !fixApproved}
                  className="font-semibold text-xs bg-emerald-600 hover:bg-emerald-700 text-white shadow h-9 px-4 gap-1.5"
                >
                  <Zap className={`w-3.5 h-3.5 ${executingFix ? 'animate-spin' : ''}`} />
                  {executingFix ? 'Dispatching to Sandbox...' : 'Execute in Codex Worktree'}
                </Button>
              </CardFooter>
            </Card>
          ) : (
            <Card className="border-dashed p-12 text-center bg-muted/10 h-full flex flex-col items-center justify-center">
              <Wrench className="w-10 h-10 text-muted-foreground/60 mb-3" />
              <h3 className="font-semibold text-sm">Select an Issue to Inspect Remediation</h3>
              <p className="text-xs text-muted-foreground max-w-sm mt-1">
                Click "Fix Plan" on any issue in the left panel to review its Root Cause Analysis,
                inspect AST diffs, and dispatch into an isolated Codex worktree sandbox.
              </p>
              {selectedIssue && (
                <Button
                  size="sm"
                  onClick={() => handleGeneratePlan(selectedIssue)}
                  disabled={planningFix}
                  className="mt-4 text-xs font-medium gap-1.5"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  {planningFix ? 'Generating Plan...' : `Plan Fix for ${selectedIssue.id}`}
                </Button>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
