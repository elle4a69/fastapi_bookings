import React, { useState } from 'react'
import {
  RotateCcw,
  Plus,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Layers,
  ListCheck,
  KeyRound,
  History,
  Check
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface WorkPackageNode {
  id: string
  title: string
  phase: string
  status: 'completed' | 'in_progress' | 'pending' | 'blocked'
  dependencies: string[]
  description: string
  progressPercent: number
}

export interface AcceptanceCriterion {
  id: string
  label: string
  status: 'passed' | 'failed' | 'pending'
  category: string
  verifiedAt?: string
}

export interface ContextCheckpoint {
  id: string
  sha: string
  description: string
  timestamp: string
  filesCount: number
  author: string
}

export interface PlanningWorkspaceProps {
  onRollback?: (checkpointId: string) => void
  onCreateCheckpoint?: (name: string) => void
  onGrantAuthorization?: (scope: string[], durationMin: number) => void
  className?: string
}

const INITIAL_PACKAGES: WorkPackageNode[] = [
  {
    id: 'pkg-1',
    title: 'Package 1: Minimal 44px TopBar & Mobile Thumb-Zone',
    phase: 'Phase 1 - Layout Foundation',
    status: 'completed',
    dependencies: [],
    description: 'Establishes mobile-first responsive viewport, 52px desktop rail, and 5-item thumb zone.',
    progressPercent: 100
  },
  {
    id: 'pkg-2',
    title: 'Package 2: Realtime Voice Engine & Waveform Strip',
    phase: 'Phase 2 - GPT Live Realtime',
    status: 'completed',
    dependencies: ['pkg-1'],
    description: 'Bridges WebRTC audio analyser, microphone capture, and 24-28px real-time waveform.',
    progressPercent: 100
  },
  {
    id: 'pkg-3',
    title: 'Package 3: Transparent Agent Stream & Inspector',
    phase: 'Phase 3 - Execution Telemetry',
    status: 'completed',
    dependencies: ['pkg-2'],
    description: 'Inline diff cards, tool executions, approval gates, subagent orchestration, and thinking blocks.',
    progressPercent: 100
  },
  {
    id: 'pkg-4',
    title: 'Package 4: 4 Dedicated Job Workspaces & Page Assembly',
    phase: 'Phase 4 - Surface Specialization',
    status: 'in_progress',
    dependencies: ['pkg-3'],
    description: 'Tickets triage queue, active coding studio, planning DAG surface, and health sentinels.',
    progressPercent: 85
  },
  {
    id: 'pkg-5',
    title: 'Package 5: Production Verification & Zero Console Gate',
    phase: 'Phase 5 - Release Gate',
    status: 'pending',
    dependencies: ['pkg-4'],
    description: 'Headless Playwright audit, zero console error gatekeeper, and automated commit/push.',
    progressPercent: 0
  }
]

const INITIAL_CRITERIA: AcceptanceCriterion[] = [
  {
    id: 'crit-1',
    label: 'Mobile thumb-zone navigation (<640px) with 44px tap targets',
    status: 'passed',
    category: 'Mobile UX',
    verifiedAt: 'Verified 10:14 AM'
  },
  {
    id: 'crit-2',
    label: 'Realtime GPT Live Voice integration with audio waveform and latency display',
    status: 'passed',
    category: 'Voice Engine',
    verifiedAt: 'Verified 10:15 AM'
  },
  {
    id: 'crit-3',
    label: 'Syntax-highlighted inline diffs with Accept / Discard file controls',
    status: 'passed',
    category: 'Code Studio',
    verifiedAt: 'Verified 10:16 AM'
  },
  {
    id: 'crit-4',
    label: 'Interactive approval gates for high-risk write operations',
    status: 'passed',
    category: 'Safety & Security',
    verifiedAt: 'Verified 10:16 AM'
  },
  {
    id: 'crit-5',
    label: 'Zero TypeScript compilation errors (npx tsc --noEmit)',
    status: 'passed',
    category: 'Type Safety',
    verifiedAt: 'Verified 10:17 AM'
  },
  {
    id: 'crit-6',
    label: 'Zero console errors and zero 4xx/5xx network failures in browser runtime',
    status: 'pending',
    category: 'Quality Gate'
  }
]

const INITIAL_CHECKPOINTS: ContextCheckpoint[] = [
  {
    id: 'chk-8f12a',
    sha: '8f12a3d',
    description: 'Stream & Voice Integration Baseline with Transparent Timeline',
    timestamp: '18 mins ago',
    filesCount: 14,
    author: 'Codex AI'
  },
  {
    id: 'chk-5c91b',
    sha: '5c91b2e',
    description: 'Package 1 & 2 Layout Foundation & WebRTC Hook Initialization',
    timestamp: '45 mins ago',
    filesCount: 8,
    author: 'Codex AI'
  },
  {
    id: 'chk-2a44f',
    sha: '2a44fc7',
    description: 'Initial Codex V3 Type Definitions and Activity Rail Scaffold',
    timestamp: '2 hours ago',
    filesCount: 5,
    author: 'Lead Architect'
  }
]

export const PlanningWorkspace: React.FC<PlanningWorkspaceProps> = ({
  onRollback,
  onCreateCheckpoint,
  onGrantAuthorization,
  className
}) => {
  const [packages] = useState<WorkPackageNode[]>(INITIAL_PACKAGES)
  const [criteria] = useState<AcceptanceCriterion[]>(INITIAL_CRITERIA)
  const [checkpoints, setCheckpoints] = useState<ContextCheckpoint[]>(INITIAL_CHECKPOINTS)

  // Rollback confirmation dialog state
  const [confirmRollbackId, setConfirmRollbackId] = useState<string | null>(null)
  const [rollbackSuccess, setRollbackSuccess] = useState<string | null>(null)

  // Checkpoint creation state
  const [isCreatingCheckpoint, setIsCreatingCheckpoint] = useState(false)
  const [newCheckpointName, setNewCheckpointName] = useState('')

  // Elevation grant state
  const [selectedScopes, setSelectedScopes] = useState<string[]>(['fs:write', 'terminal:exec'])
  const [selectedDuration, setSelectedDuration] = useState<number>(15)
  const [activeGrant, setActiveGrant] = useState<{
    scopes: string[]
    expiresInMinutes: number
    grantedAt: string
  } | null>(null)

  const handleGrant = () => {
    const grant = {
      scopes: selectedScopes,
      expiresInMinutes: selectedDuration,
      grantedAt: 'Just now'
    }
    setActiveGrant(grant)
    if (onGrantAuthorization) {
      onGrantAuthorization(selectedScopes, selectedDuration)
    }
  }

  const handleRevoke = () => {
    setActiveGrant(null)
  }

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    )
  }

  const handleExecuteRollback = (checkpoint: ContextCheckpoint) => {
    if (onRollback) {
      onRollback(checkpoint.id)
    }
    setConfirmRollbackId(null)
    setRollbackSuccess(`Successfully rolled back to checkpoint ${checkpoint.sha}: "${checkpoint.description}"`)
    setTimeout(() => setRollbackSuccess(null), 4000)
  }

  const handleSaveCheckpoint = () => {
    if (!newCheckpointName.trim()) return
    const newChk: ContextCheckpoint = {
      id: `chk-${Math.random().toString(36).substring(2, 7)}`,
      sha: Math.random().toString(16).substring(2, 9),
      description: newCheckpointName.trim(),
      timestamp: 'Just now',
      filesCount: 12,
      author: 'Codex AI'
    }
    setCheckpoints([newChk, ...checkpoints])
    if (onCreateCheckpoint) {
      onCreateCheckpoint(newChk.description)
    }
    setNewCheckpointName('')
    setIsCreatingCheckpoint(false)
  }

  return (
    <div
      data-testid="planning-workspace"
      className={cn('flex flex-col h-full w-full p-4 sm:p-6 space-y-4 max-w-6xl mx-auto', className)}
    >
      {/* 1. Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/40">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-blue-500 animate-pulse" />
            <h1 className="text-xl font-bold tracking-tight text-foreground">
              Mission & Work Package DAG Planner
            </h1>
          </div>
          <p className="text-xs text-muted-foreground">
            Multi-stage work package DAG dependency tracking, acceptance gates, context checkpoints, and elevation launcher.
          </p>
        </div>

        {/* Create Checkpoint trigger button */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            data-testid="create-checkpoint-btn"
            onClick={() => setIsCreatingCheckpoint(!isCreatingCheckpoint)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-card/80 hover:bg-card border border-border/50 text-foreground transition-all shadow-sm min-h-[38px]"
          >
            <Plus className="h-3.5 w-3.5 text-primary" />
            <span>Create Checkpoint</span>
          </button>
        </div>
      </div>

      {/* Banner Notifications */}
      {rollbackSuccess && (
        <div
          data-testid="rollback-success-banner"
          className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between animate-in fade-in"
        >
          <div className="flex items-center gap-2">
            <Check className="h-4 w-4 text-emerald-400" />
            <span>{rollbackSuccess}</span>
          </div>
          <button
            type="button"
            onClick={() => setRollbackSuccess(null)}
            className="text-emerald-400/80 hover:text-emerald-200 font-mono text-[11px]"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* New Checkpoint Form (Inline) */}
      {isCreatingCheckpoint && (
        <div className="p-4 rounded-xl border border-primary/40 bg-card/80 space-y-3 animate-in fade-in slide-in-from-top-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <History className="h-4 w-4 text-primary" />
              Snapshot Context Checkpoint
            </span>
            <button
              type="button"
              onClick={() => setIsCreatingCheckpoint(false)}
              className="text-muted-foreground hover:text-foreground text-xs"
            >
              Cancel
            </button>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="e.g. Completed Package 4 workspace components baseline..."
              value={newCheckpointName}
              onChange={(e) => setNewCheckpointName(e.target.value)}
              className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-border/60 bg-background/80 focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <button
              type="button"
              onClick={handleSaveCheckpoint}
              disabled={!newCheckpointName.trim()}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              Save Checkpoint
            </button>
          </div>
        </div>
      )}

      {/* 2. Top Section: Work Package DAG Pipeline */}
      <div className="rounded-xl border border-border/40 bg-card/60 p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-border/30 pb-2">
          <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Layers className="h-4 w-4 text-primary" />
            Work Package DAG Pipeline
          </span>
          <span className="text-[11px] font-mono text-muted-foreground">
            3 Completed • 1 In Progress • 1 Pending
          </span>
        </div>

        {/* DAG Nodes Container */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          {packages.map((pkg) => {
            const isCompleted = pkg.status === 'completed'
            const isInProgress = pkg.status === 'in_progress'

            return (
              <div
                key={pkg.id}
                data-testid={`dag-node-${pkg.id}`}
                className={cn(
                  'rounded-lg border p-3 flex flex-col justify-between space-y-2 relative transition-all',
                  isCompleted && 'bg-emerald-950/15 border-emerald-500/30',
                  isInProgress && 'bg-blue-950/20 border-blue-500/40 shadow-sm ring-1 ring-blue-500/20',
                  pkg.status === 'pending' && 'bg-card/40 border-border/30 opacity-70'
                )}
              >
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono font-bold text-muted-foreground">
                      {pkg.id.toUpperCase()}
                    </span>
                    {isCompleted && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-mono text-emerald-400 font-semibold">
                        <CheckCircle2 className="h-3 w-3" /> Done
                      </span>
                    )}
                    {isInProgress && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-mono text-blue-400 font-semibold">
                        <Clock className="h-3 w-3 animate-spin" /> Active
                      </span>
                    )}
                    {pkg.status === 'pending' && (
                      <span className="text-[10px] font-mono text-muted-foreground">
                        Queued
                      </span>
                    )}
                  </div>

                  <h3 className="text-xs font-bold text-foreground leading-snug">
                    {pkg.title}
                  </h3>
                  <p className="text-[11px] text-muted-foreground leading-normal line-clamp-3">
                    {pkg.description}
                  </p>
                </div>

                {/* Progress bar */}
                <div className="space-y-1 pt-1 border-t border-border/20">
                  <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground">
                    <span>Progress</span>
                    <span>{pkg.progressPercent}%</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-muted/60 overflow-hidden">
                    <div
                      className={cn(
                        'h-full transition-all duration-500',
                        isCompleted ? 'bg-emerald-500' : isInProgress ? 'bg-blue-500' : 'bg-muted-foreground/30'
                      )}
                      style={{ width: `${pkg.progressPercent}%` }}
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* 3. Middle Grid: Acceptance Criteria & Elevation Launcher */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left: Acceptance Criteria (7 cols) */}
        <div className="lg:col-span-7 rounded-xl border border-border/40 bg-card/60 p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-border/30 pb-2">
            <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <ListCheck className="h-4 w-4 text-primary" />
              Brief Acceptance Criteria Checklist
            </span>
            <span className="text-[10px] font-mono text-emerald-400">
              {criteria.filter((c) => c.status === 'passed').length} / {criteria.length} Gates Passed
            </span>
          </div>

          <div className="space-y-2 overflow-y-auto max-h-[220px]">
            {criteria.map((item) => {
              const isPassed = item.status === 'passed'

              return (
                <div
                  key={item.id}
                  data-testid={`criterion-${item.id}`}
                  className="flex items-start justify-between gap-3 p-2.5 rounded-lg border border-border/30 bg-background/50 text-xs"
                >
                  <div className="space-y-0.5">
                    <p className="font-medium text-foreground leading-snug">
                      {item.label}
                    </p>
                    <div className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
                      <span className="px-1.5 py-0.2 rounded bg-muted/60">
                        {item.category}
                      </span>
                      {item.verifiedAt && (
                        <span>• {item.verifiedAt}</span>
                      )}
                    </div>
                  </div>

                  <span
                    className={cn(
                      'inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold shrink-0',
                      isPassed
                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                        : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                    )}
                  >
                    {isPassed ? (
                      <>
                        <Check className="h-3 w-3" /> PASS
                      </>
                    ) : (
                      <>
                        <Clock className="h-3 w-3" /> PENDING
                      </>
                    )}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right: Single-Run Elevation Launcher (5 cols) */}
        <div className="lg:col-span-5 rounded-xl border border-border/40 bg-card/60 p-4 space-y-3 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="flex items-center justify-between border-b border-border/30 pb-2">
              <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <KeyRound className="h-4 w-4 text-purple-400" />
                Single-Run Authorization Grant
              </span>
              <span className="text-[10px] font-mono text-muted-foreground">
                Zero-Trust Gate
              </span>
            </div>

            <p className="text-[11px] text-muted-foreground leading-normal">
              Authorize temporary autonomous agent actions within strict time and capability bounds.
            </p>

            {/* Scope Selectors */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-foreground">
                Grant Capability Scopes:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {[
                  { id: 'fs:write', label: 'File System Write' },
                  { id: 'terminal:exec', label: 'Terminal Exec' },
                  { id: 'git:commit', label: 'Git Commit & Push' },
                  { id: 'db:migrate', label: 'Alembic Migrate' }
                ].map((scope) => {
                  const isSelected = selectedScopes.includes(scope.id)
                  return (
                    <button
                      key={scope.id}
                      type="button"
                      onClick={() => toggleScope(scope.id)}
                      className={cn(
                        'px-2.5 py-1 rounded text-[11px] font-mono transition-all border',
                        isSelected
                          ? 'bg-purple-500/20 text-purple-300 border-purple-500/40 shadow-xs'
                          : 'bg-card/40 text-muted-foreground border-border/30 hover:bg-card'
                      )}
                    >
                      {scope.label}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Duration Selector */}
            <div className="space-y-1.5 pt-1">
              <span className="text-[11px] font-semibold text-foreground">
                Grant Duration:
              </span>
              <div className="flex gap-2">
                {[15, 30, 60].map((mins) => (
                  <button
                    key={mins}
                    type="button"
                    onClick={() => setSelectedDuration(mins)}
                    className={cn(
                      'flex-1 py-1 rounded text-xs font-medium border text-center transition-colors',
                      selectedDuration === mins
                        ? 'bg-primary text-primary-foreground border-primary font-bold'
                        : 'bg-muted/40 text-muted-foreground border-border/40 hover:bg-muted/70'
                    )}
                  >
                    {mins} mins
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Action Button / Active State */}
          <div className="pt-2">
            {activeGrant ? (
              <div className="p-2.5 rounded-lg bg-purple-500/10 border border-purple-500/30 flex items-center justify-between text-xs">
                <div className="space-y-0.5">
                  <span className="text-purple-300 font-semibold flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5 text-purple-400" />
                    Elevation Active ({activeGrant.expiresInMinutes}m)
                  </span>
                  <p className="text-[10px] font-mono text-purple-400/80">
                    {activeGrant.scopes.join(', ')}
                  </p>
                </div>
                <button
                  type="button"
                  data-testid="revoke-grant-btn"
                  onClick={handleRevoke}
                  className="px-2.5 py-1 rounded text-[11px] font-semibold bg-rose-600 hover:bg-rose-500 text-white"
                >
                  Revoke
                </button>
              </div>
            ) : (
              <button
                type="button"
                data-testid="grant-elevation-btn"
                onClick={handleGrant}
                className="w-full py-2 rounded-lg text-xs font-semibold bg-purple-600 hover:bg-purple-500 text-white transition-all shadow-sm flex items-center justify-center gap-1.5 min-h-[38px]"
              >
                <ShieldAlert className="h-3.5 w-3.5" />
                <span>Grant Single-Run Elevation ({selectedDuration}m)</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 4. Bottom Section: Context Checkpoints & Rollback Controls */}
      <div className="rounded-xl border border-border/40 bg-card/60 p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-border/30 pb-2">
          <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <History className="h-4 w-4 text-primary" />
            Context Checkpoints & Rollback History
          </span>
          <span className="text-[11px] font-mono text-muted-foreground">
            {checkpoints.length} Checkpoints Available
          </span>
        </div>

        <div className="space-y-2">
          {checkpoints.map((chk) => {
            const isConfirming = confirmRollbackId === chk.id

            return (
              <div
                key={chk.id}
                data-testid={`checkpoint-row-${chk.id}`}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg border border-border/30 bg-background/50 hover:bg-background/80 transition-colors"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
                      {chk.sha}
                    </span>
                    <span className="text-xs font-semibold text-foreground">
                      {chk.description}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
                    <span>{chk.timestamp}</span>
                    <span>•</span>
                    <span>{chk.filesCount} files tracked</span>
                    <span>•</span>
                    <span>Author: {chk.author}</span>
                  </div>
                </div>

                {/* Rollback Actions */}
                <div className="shrink-0 flex items-center gap-2">
                  {isConfirming ? (
                    <div className="flex items-center gap-2 animate-in fade-in">
                      <span className="text-[11px] font-bold text-rose-400">
                        Confirm rollback?
                      </span>
                      <button
                        type="button"
                        data-testid={`confirm-rollback-${chk.id}`}
                        onClick={() => handleExecuteRollback(chk)}
                        className="px-2.5 py-1 text-[11px] font-semibold rounded bg-rose-600 hover:bg-rose-500 text-white"
                      >
                        Yes, Rollback
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmRollbackId(null)}
                        className="px-2 py-1 text-[11px] rounded bg-muted/60 text-muted-foreground hover:text-foreground"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      data-testid={`rollback-btn-${chk.id}`}
                      onClick={() => setConfirmRollbackId(chk.id)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-rose-400 hover:bg-rose-500/10 border border-border/40 hover:border-rose-500/30 transition-all min-h-[36px]"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                      <span>Rollback to Checkpoint</span>
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default PlanningWorkspace
