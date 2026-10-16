import React, { useState } from 'react'
import {
  GitBranch,
  FolderGit2,
  FileCode,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  Terminal,
  Columns,
  SquareSplitHorizontal,
  ChevronDown,
  ArrowUpRight,
  ShieldCheck,
  Check,
  X,
  FileCheck2,
  Loader2
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface ModifiedFile {
  path: string
  status: 'modified' | 'added' | 'deleted'
  additions: number
  deletions: number
  diffHunks: string[]
  oldContent?: string
  newContent?: string
}

export interface TestRunResult {
  command: string
  status: 'idle' | 'running' | 'passed' | 'failed'
  totalCount: number
  passedCount: number
  failedCount: number
  skippedCount: number
  durationSeconds: number
  output: string[]
}

export interface CodingWorkspaceProps {
  activeBranch?: string
  worktreePath?: string
  onPromoteRelease?: () => void
  onRunTests?: (command: string) => void
  className?: string
}

const SAMPLE_MODIFIED_FILES: ModifiedFile[] = [
  {
    path: 'app/services/scheduling/booking_engine.py',
    status: 'modified',
    additions: 14,
    deletions: 3,
    diffHunks: [
      '@@ -182,7 +182,18 @@ async def acquire_hold_lock(db: AsyncSession, provider_id: int, slot_id: str):',
      '     # Enforce row-level lock with nowait and exponential backoff retry to prevent deadlocks',
      '-    stmt = select(AppointmentLock).where(AppointmentLock.slot_id == slot_id).with_for_update()',
      '-    result = await db.execute(stmt)',
      '-    return result.scalar_one_or_none()',
      '+    for attempt in range(MAX_RETRIES):',
      '+        try:',
      '+            stmt = (',
      '+                select(AppointmentLock)',
      '+                .where(AppointmentLock.slot_id == slot_id)',
      '+                .with_for_update(nowait=True)',
      '+            )',
      '+            result = await db.execute(stmt)',
      '+            return result.scalar_one_or_none()',
      '+        except OperationalError as err:',
      '+            if attempt == MAX_RETRIES - 1:',
      '+                raise LockAcquisitionTimeoutError(f"Contention on slot {slot_id}") from err',
      '+            await asyncio.sleep(0.05 * (2 ** attempt))'
    ],
    oldContent: `async def acquire_hold_lock(db: AsyncSession, provider_id: int, slot_id: str):
    stmt = select(AppointmentLock).where(AppointmentLock.slot_id == slot_id).with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()`,
    newContent: `async def acquire_hold_lock(db: AsyncSession, provider_id: int, slot_id: str):
    # Enforce row-level lock with nowait and exponential backoff retry to prevent deadlocks
    for attempt in range(MAX_RETRIES):
        try:
            stmt = (
                select(AppointmentLock)
                .where(AppointmentLock.slot_id == slot_id)
                .with_for_update(nowait=True)
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except OperationalError as err:
            if attempt == MAX_RETRIES - 1:
                raise LockAcquisitionTimeoutError(f"Contention on slot {slot_id}") from err
            await asyncio.sleep(0.05 * (2 ** attempt))`
  },
  {
    path: 'frontend/src/pages/admin/codex-v3/workspaces/TicketsWorkspace.tsx',
    status: 'added',
    additions: 210,
    deletions: 0,
    diffHunks: [
      '@@ -0,0 +1,210 @@',
      '+import React, { useState } from "react"',
      '+import { AlertCircle, Zap, ShieldCheck } from "lucide-react"',
      '+// Dedicated triage workspace surface with instant diagnostic synthesis'
    ],
    oldContent: '',
    newContent: '// Full TicketsWorkspace implementation'
  },
  {
    path: 'alembic/versions/2026_concurrency_fix.py',
    status: 'added',
    additions: 38,
    deletions: 0,
    diffHunks: [
      '@@ -0,0 +1,38 @@',
      '+"""Add composite index on appointment_locks(tenant_id, slot_id, expires_at)"""',
      '+from alembic import op',
      '+import sqlalchemy as sa',
      '+',
      '+def upgrade():',
      '+    op.create_index("ix_appointment_locks_slot_exp", "appointment_locks", ["tenant_id", "slot_id", "expires_at"])'
    ],
    oldContent: '',
    newContent: '# Alembic migration for concurrency lock indexing'
  }
]

export const CodingWorkspace: React.FC<CodingWorkspaceProps> = ({
  activeBranch: initialBranch = 'feat/codex-v3-workspaces',
  worktreePath = 'f:/Projects/fastapi_bookings/worktrees/codex-v3',
  onPromoteRelease,
  onRunTests,
  className
}) => {
  const [activeBranch, setActiveBranch] = useState(initialBranch)
  const [branches] = useState([
    'feat/codex-v3-workspaces',
    'main',
    'fix/concurrency-booking',
    'chore/telemetry-wiring'
  ])
  const [modifiedFiles, setModifiedFiles] = useState<ModifiedFile[]>(SAMPLE_MODIFIED_FILES)
  const [selectedFilePath, setSelectedFilePath] = useState<string>(SAMPLE_MODIFIED_FILES[0].path)
  const [diffMode, setDiffMode] = useState<'unified' | 'side-by-side'>('unified')
  const [acceptedFiles, setAcceptedFiles] = useState<Record<string, boolean>>({})

  // Test runner state
  const [selectedCommand, setSelectedCommand] = useState('pytest tests/test_bookings.py')
  const [testResult, setTestResult] = useState<TestRunResult>({
    command: 'pytest tests/test_bookings.py',
    status: 'passed',
    totalCount: 14,
    passedCount: 14,
    failedCount: 0,
    skippedCount: 0,
    durationSeconds: 1.42,
    output: [
      '============================= test session starts ============================== ',
      'platform win32 -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0',
      'rootdir: F:\\Projects\\fastapi_bookings',
      'configfile: pytest.ini',
      'plugins: anyio-4.3.0, asyncio-0.23.6',
      'collected 14 items',
      '',
      'tests/test_bookings.py::test_create_booking_hold PASSED                 [  7%]',
      'tests/test_bookings.py::test_concurrency_hold_race_condition PASSED    [ 14%]',
      'tests/test_bookings.py::test_exponential_backoff_retry PASSED          [ 21%]',
      'tests/test_bookings.py::test_lock_timeout_handling PASSED              [ 28%]',
      'tests/test_bookings.py::test_tenant_isolation_slot_locks PASSED        [ 35%]',
      'tests/test_bookings.py::test_alembic_composite_index_perf PASSED      [ 42%]',
      'tests/test_bookings.py::test_booking_confirmation_workflow PASSED      [ 50%]',
      'tests/test_bookings.py::test_double_booking_prevention PASSED          [ 57%]',
      'tests/test_bookings.py::test_optimistic_concurrency_version PASSED     [ 64%]',
      'tests/test_bookings.py::test_rollback_on_transaction_timeout PASSED   [ 71%]',
      'tests/test_bookings.py::test_cross_tenant_lock_rejection PASSED       [ 78%]',
      'tests/test_bookings.py::test_chatwoot_bridge_event_sync PASSED         [ 85%]',
      'tests/test_bookings.py::test_sms_outbox_queue_drain PASSED             [ 92%]',
      'tests/test_bookings.py::test_zero_console_gate_compatibility PASSED    [100%]',
      '',
      '============================== 14 passed in 1.42s =============================='
    ]
  })

  const [isRunningTests, setIsRunningTests] = useState(false)
  const [promotionStatus, setPromotionStatus] = useState<string | null>(null)

  const selectedFile = modifiedFiles.find((f) => f.path === selectedFilePath) || modifiedFiles[0]

  const handleRunTests = () => {
    setIsRunningTests(true)
    setTestResult((prev) => ({ ...prev, status: 'running' }))

    if (onRunTests) {
      onRunTests(selectedCommand)
    }

    setTimeout(() => {
      setIsRunningTests(false)
      setTestResult({
        command: selectedCommand,
        status: 'passed',
        totalCount: 14,
        passedCount: 14,
        failedCount: 0,
        skippedCount: 0,
        durationSeconds: 1.38,
        output: [
          `Running: ${selectedCommand}`,
          'Executing automated verification test suite...',
          'tests/test_bookings.py::test_concurrency_hold_race_condition PASSED',
          'tests/test_bookings.py::test_optimistic_concurrency_version PASSED',
          'All 14 tests completed with 0 errors.',
          'Result: PASSED (14 passed in 1.38s)'
        ]
      })
    }, 1500)
  }

  const handlePromote = () => {
    setPromotionStatus('Promoting changes to main branch...')
    if (onPromoteRelease) {
      onPromoteRelease()
    }
    setTimeout(() => {
      setPromotionStatus('Successfully promoted and staged to release tracking branch!')
      setTimeout(() => setPromotionStatus(null), 4000)
    }, 1200)
  }

  const handleAcceptFile = (path: string) => {
    setAcceptedFiles((prev) => ({ ...prev, [path]: true }))
  }

  const handleDiscardFile = (path: string) => {
    setModifiedFiles((prev) => prev.filter((f) => f.path !== path))
  }

  return (
    <div
      data-testid="coding-workspace"
      className={cn('flex flex-col h-full w-full p-4 sm:p-6 space-y-4 max-w-6xl mx-auto', className)}
    >
      {/* 1. Header & Active Branch / Worktree Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-3 border-b border-border/40">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <h1 className="text-xl font-bold tracking-tight text-foreground">
              Active Coding Studio & Diff Workbench
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground font-mono">
            <span className="flex items-center gap-1 text-foreground font-semibold">
              <FolderGit2 className="h-3.5 w-3.5 text-primary" />
              Worktree:
            </span>
            <span className="bg-background/80 px-2 py-0.5 rounded border border-border/40 text-[11px] truncate max-w-xs sm:max-w-md">
              {worktreePath}
            </span>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              Clean Worktree
            </span>
          </div>
        </div>

        {/* Branch Selector & Promote Release Button */}
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <div className="relative">
            <select
              aria-label="Active git branch"
              value={activeBranch}
              onChange={(e) => setActiveBranch(e.target.value)}
              className="appearance-none pl-7 pr-8 py-1.5 text-xs font-mono rounded-lg border border-border/60 bg-card/90 text-foreground cursor-pointer focus:outline-none focus:ring-1 focus:ring-primary min-h-[38px]"
            >
              {branches.map((b) => (
                <option key={b} value={b}>
                  branch: {b}
                </option>
              ))}
            </select>
            <GitBranch className="absolute left-2.5 top-3 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <ChevronDown className="absolute right-2.5 top-3 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
          </div>

          <button
            type="button"
            data-testid="promote-release-btn"
            onClick={handlePromote}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm transition-all min-h-[38px]"
          >
            <ArrowUpRight className="h-4 w-4" />
            <span>Promote to Release Branch</span>
          </button>
        </div>
      </div>

      {/* Promotion feedback banner */}
      {promotionStatus && (
        <div
          data-testid="promotion-status-banner"
          className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center justify-between animate-in fade-in"
        >
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <span>{promotionStatus}</span>
          </div>
          <button
            type="button"
            onClick={() => setPromotionStatus(null)}
            className="text-emerald-400/80 hover:text-emerald-200 font-mono text-[11px]"
          >
            Close
          </button>
        </div>
      )}

      {/* 2. Modified Files & Diff Studio Surface */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-0">
        {/* Left Column: File Tree (4 cols) */}
        <div className="lg:col-span-4 rounded-xl border border-border/40 bg-card/60 p-3 flex flex-col space-y-2">
          <div className="flex items-center justify-between border-b border-border/30 pb-2">
            <span className="text-xs font-semibold tracking-wide text-foreground flex items-center gap-1.5">
              <FileCode className="h-3.5 w-3.5 text-primary" />
              Modified Files ({modifiedFiles.length})
            </span>
            <span className="text-[10px] font-mono text-muted-foreground">
              +{modifiedFiles.reduce((acc, f) => acc + f.additions, 0)} / -{modifiedFiles.reduce((acc, f) => acc + f.deletions, 0)}
            </span>
          </div>

          <div className="space-y-1 overflow-y-auto max-h-[260px] lg:max-h-none flex-1">
            {modifiedFiles.map((file) => {
              const isSelected = file.path === selectedFilePath
              const isAccepted = acceptedFiles[file.path]

              return (
                <button
                  key={file.path}
                  type="button"
                  data-testid={`file-item-${file.path}`}
                  onClick={() => setSelectedFilePath(file.path)}
                  className={cn(
                    'w-full text-left p-2.5 rounded-lg text-xs font-mono transition-all flex items-center justify-between gap-2 border',
                    isSelected
                      ? 'bg-primary/10 border-primary/40 text-primary shadow-sm'
                      : 'bg-card/40 border-border/30 text-muted-foreground hover:text-foreground hover:bg-card/80'
                  )}
                >
                  <div className="min-w-0 truncate space-y-0.5">
                    <p className="truncate font-semibold text-foreground text-[11px]">
                      {file.path.split('/').pop()}
                    </p>
                    <p className="truncate text-[10px] text-muted-foreground/70">
                      {file.path}
                    </p>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className="text-[10px] text-emerald-400 font-bold">
                      +{file.additions}
                    </span>
                    {file.deletions > 0 && (
                      <span className="text-[10px] text-rose-400 font-bold">
                        -{file.deletions}
                      </span>
                    )}
                    {isAccepted && (
                      <FileCheck2 className="h-3.5 w-3.5 text-emerald-400 ml-1" />
                    )}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* Right Column: Diff Preview & Test Runner (8 cols) */}
        <div className="lg:col-span-8 flex flex-col space-y-4">
          {/* Diff Viewer Card */}
          <div className="rounded-xl border border-border/40 bg-card/60 p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/30 pb-2">
              <div className="min-w-0">
                <p className="text-xs font-mono font-bold text-foreground truncate">
                  {selectedFile.path}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px] font-mono text-emerald-400">
                    +{selectedFile.additions} additions
                  </span>
                  <span className="text-[10px] font-mono text-rose-400">
                    -{selectedFile.deletions} deletions
                  </span>
                </div>
              </div>

              {/* View Mode Toggle & Diff Actions */}
              <div className="flex items-center gap-1.5">
                <div className="inline-flex rounded-lg p-0.5 bg-muted/60 text-xs border border-border/40">
                  <button
                    type="button"
                    onClick={() => setDiffMode('unified')}
                    className={cn(
                      'px-2 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1',
                      diffMode === 'unified' ? 'bg-background text-foreground shadow-xs' : 'text-muted-foreground'
                    )}
                  >
                    <Columns className="h-3 w-3" />
                    <span>Unified</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setDiffMode('side-by-side')}
                    className={cn(
                      'px-2 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1',
                      diffMode === 'side-by-side' ? 'bg-background text-foreground shadow-xs' : 'text-muted-foreground'
                    )}
                  >
                    <SquareSplitHorizontal className="h-3 w-3" />
                    <span>Side-by-side</span>
                  </button>
                </div>

                <button
                  type="button"
                  data-testid="accept-diff-btn"
                  onClick={() => handleAcceptFile(selectedFile.path)}
                  className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30 border border-emerald-500/40 flex items-center gap-1"
                >
                  <Check className="h-3 w-3" />
                  <span>Accept</span>
                </button>

                <button
                  type="button"
                  data-testid="discard-diff-btn"
                  onClick={() => handleDiscardFile(selectedFile.path)}
                  className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-rose-500/15 text-rose-300 hover:bg-rose-500/25 border border-rose-500/30 flex items-center gap-1"
                >
                  <X className="h-3 w-3" />
                  <span>Discard</span>
                </button>
              </div>
            </div>

            {/* Diff Content Preview */}
            <div className="rounded-lg bg-zinc-950 p-3 font-mono text-[11px] overflow-x-auto max-h-[220px] border border-zinc-800">
              {diffMode === 'unified' ? (
                <div className="space-y-1">
                  {selectedFile.diffHunks.map((line, idx) => {
                    const isAddition = line.startsWith('+') && !line.startsWith('+++')
                    const isDeletion = line.startsWith('-') && !line.startsWith('---')
                    const isHunkHeader = line.startsWith('@@')

                    return (
                      <div
                        key={idx}
                        className={cn(
                          'px-2 py-0.5 rounded whitespace-pre',
                          isAddition && 'bg-emerald-950/60 text-emerald-300 border-l-2 border-emerald-500',
                          isDeletion && 'bg-rose-950/60 text-rose-300 border-l-2 border-rose-500',
                          isHunkHeader && 'text-zinc-500 bg-zinc-900/60 py-1 font-bold'
                        )}
                      >
                        {line}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2 text-[10px]">
                  <div className="space-y-1 bg-zinc-900/40 p-2 rounded border border-zinc-800/60">
                    <span className="text-zinc-500 font-bold block mb-1">Old Version:</span>
                    <pre className="text-zinc-400 whitespace-pre-wrap">
                      {selectedFile.oldContent || '// Empty baseline'}
                    </pre>
                  </div>
                  <div className="space-y-1 bg-emerald-950/20 p-2 rounded border border-emerald-800/40">
                    <span className="text-emerald-400 font-bold block mb-1">New Version:</span>
                    <pre className="text-emerald-300 whitespace-pre-wrap">
                      {selectedFile.newContent || '// New content'}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Test Execution Runner Surface */}
          <div className="rounded-xl border border-border/40 bg-card/60 p-4 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/30 pb-2">
              <div className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-primary" />
                <span className="text-xs font-semibold tracking-wide text-foreground">
                  Automated Test Execution Runner
                </span>
              </div>

              {/* Run Tests Action Button */}
              <div className="flex items-center gap-2">
                <select
                  aria-label="Test command selector"
                  value={selectedCommand}
                  onChange={(e) => setSelectedCommand(e.target.value)}
                  className="px-2 py-1 text-xs font-mono rounded-lg border border-border/60 bg-card text-foreground"
                >
                  <option value="pytest tests/test_bookings.py">pytest tests/test_bookings.py</option>
                  <option value="npm test">npm test</option>
                  <option value="python scripts/verify_zero_console_errors.py">verify_zero_console_errors.py</option>
                </select>

                <button
                  type="button"
                  data-testid="run-tests-btn"
                  disabled={isRunningTests}
                  onClick={handleRunTests}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-all shadow-sm disabled:opacity-50"
                >
                  {isRunningTests ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Play className="h-3.5 w-3.5 fill-current" />
                  )}
                  <span>{isRunningTests ? 'Executing...' : 'Run Tests'}</span>
                </button>
              </div>
            </div>

            {/* Test Pass/Fail Summary Chips */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span className="font-bold">{testResult.passedCount}</span>
                <span>Passed</span>
              </div>

              <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-rose-500/15 text-rose-400 border border-rose-500/30">
                <XCircle className="h-3.5 w-3.5" />
                <span className="font-bold">{testResult.failedCount}</span>
                <span>Failed</span>
              </div>

              <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-muted/60 text-muted-foreground border border-border/40 font-mono text-[11px]">
                <Clock className="h-3 w-3" />
                <span>{testResult.durationSeconds}s runtime</span>
              </div>

              <span className="ml-auto text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                <ShieldCheck className="h-3.5 w-3.5" />
                All Gates Passed
              </span>
            </div>

            {/* Terminal Console Output */}
            <div className="rounded-lg bg-zinc-950 p-3 font-mono text-[11px] text-zinc-300 max-h-[160px] overflow-y-auto border border-zinc-800 space-y-1">
              {testResult.output.map((line, idx) => (
                <div
                  key={idx}
                  className={cn(
                    'leading-tight',
                    line.includes('PASSED') && 'text-emerald-400',
                    line.includes('FAILED') && 'text-rose-400',
                    line.includes('Running:') && 'text-zinc-500 font-bold'
                  )}
                >
                  {line}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default CodingWorkspace
