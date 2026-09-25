import React from 'react'
import { CheckCircle2, Play } from 'lucide-react'
import { Button } from '../../ui/button'
import { Badge } from '../../ui/badge'
import { useWorkbenchStore } from '../../../store/useWorkbenchStore'

interface DisplayedTest {
  name: string
  status: string
  duration: string
}

interface DisplayedSuite {
  name: string
  status: 'passed' | 'failed' | 'running'
  passed: number
  failed: number
  tests: DisplayedTest[]
}

export const TestsTab: React.FC = () => {
  const { state, activeThread } = useWorkbenchStore()
  
  // Extract real test runs from active thread items if in live mode
  const realTestRuns = React.useMemo(() => {
    if (!activeThread) return []
    const runs: any[] = []
    activeThread.turns.forEach(turn => {
      turn.items.forEach(item => {
        if (item.type === 'test_run') {
          runs.push(item)
        }
      })
    })
    return runs
  }, [activeThread])

  const testSuites: DisplayedSuite[] = state.appMode === 'demo' ? [
    {
      name: 'tests/test_availability.py',
      status: 'passed',
      passed: 3,
      failed: 0,
      tests: [
        { name: 'test_timezone_offset_slot_calculation', status: 'passed', duration: '42ms' },
        { name: 'test_concurrent_lock_prevents_double_booking', status: 'passed', duration: '180ms' },
        { name: 'test_empty_slots_fallback', status: 'passed', duration: '12ms' }
      ]
    },
    {
      name: 'tests/test_booking_flow.py',
      status: 'passed',
      passed: 2,
      failed: 0,
      tests: [
        { name: 'test_create_booking_atomic_transaction', status: 'passed', duration: '95ms' },
        { name: 'test_idempotent_sms_notification_dispatch', status: 'passed', duration: '64ms' }
      ]
    }
  ] : realTestRuns.flatMap(r => (r.suites || []).map((s: any): DisplayedSuite => ({
    name: s.name || 'Test Suite',
    status: s.failed > 0 ? 'failed' : 'passed',
    passed: s.passed || 0,
    failed: s.failed || 0,
    tests: (s.failures || []).map((f: any) => ({
      name: f.testName || 'Test Case',
      status: 'failed',
      duration: `${s.durationMs || 50}ms`
    })).concat(
      Array.from({ length: s.passed || 0 }).map((_, i) => ({
        name: `test_scenario_${i + 1}`,
        status: 'passed',
        duration: `${Math.round((s.durationMs || 50) / Math.max(1, s.passed))}ms`
      }))
    )
  })))

  const totalPassed = testSuites.reduce((acc, s) => acc + s.passed, 0)
  const totalFailed = testSuites.reduce((acc, s) => acc + s.failed, 0)

  if (state.appMode === 'live' && testSuites.length === 0) {
    return (
      <div className="p-3 text-center text-xs text-[var(--text-subtle)] mt-10 space-y-2">
        <p className="font-medium text-[var(--text-secondary)]">No active runner attached</p>
        <p className="text-[11px]">Run a pytest command in this thread to see real execution output.</p>
      </div>
    )
  }

  return (
    <div className="p-3 space-y-3 text-xs">
      <div className="p-3 rounded-lg bg-[var(--surface-secondary)]/50 border border-[var(--border)] flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">Test Suites (pytest)</h3>
          <div className="text-[11px] text-[var(--text-secondary)] mt-0.5">
            {totalPassed} passing · {totalFailed} failing
          </div>
        </div>

        <Button 
          size="sm" 
          variant="secondary" 
          className="h-7 text-xs gap-1"
          aria-label="Run all test suites"
        >
          <Play className="w-3 h-3 fill-current text-[var(--accent)]" />
          Run All
        </Button>
      </div>

      <div className="space-y-3">
        {testSuites.map((suite, idx) => (
          <div key={idx} className="border border-[var(--border)] rounded-md bg-[var(--surface-primary)] p-2.5 space-y-2">
            <div className="flex items-center justify-between font-mono text-xs font-semibold text-[var(--text-primary)]">
              <h4 className="font-mono text-xs font-semibold text-[var(--text-primary)] m-0">{suite.name}</h4>
              <Badge variant={suite.status === 'passed' ? 'success' : 'danger'} className="text-[9px] py-0 px-1 capitalize">
                {suite.status}
              </Badge>
            </div>

            <div className="space-y-1">
              {suite.tests.map((test, tIdx) => (
                <div key={tIdx} className="flex items-center justify-between text-[11px] py-0.5 px-1 rounded hover:bg-[var(--surface-secondary)]">
                  <div className="flex items-center gap-1.5 font-mono text-[var(--text-secondary)] truncate">
                    <CheckCircle2 className="w-3 h-3 text-[var(--success)] flex-shrink-0" />
                    <span className="truncate">{test.name}</span>
                  </div>
                  <span className="text-[10px] text-[var(--text-subtle)] font-mono ml-2">{test.duration}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
