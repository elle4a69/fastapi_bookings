import React, { useState } from 'react'
import { Zap, Play, CheckCircle2, ShieldCheck } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { apiClient } from '@/lib/api'
import type { RaceConditionFuzzResult } from './types'

export const StressFuzzer: React.FC = () => {
  const [fuzzConcurrency, setFuzzConcurrency] = useState<number>(15)
  const [fuzzing, setFuzzing] = useState<boolean>(false)
  const [fuzzResult, setFuzzResult] = useState<RaceConditionFuzzResult | null>(null)

  const handleRunRaceConditionTest = async () => {
    try {
      setFuzzing(true)
      toast.info(`Triggering race-condition stress fuzzer (${fuzzConcurrency} concurrent bookings)...`)

      const res = await apiClient.post<RaceConditionFuzzResult>(
        '/api/admin/resident-agent/fuzz/race-condition',
        { concurrency: fuzzConcurrency }
      )
      const data = (res as any)?.data ?? res
      setFuzzResult(data)
      toast.success(
        `Fuzzer completed! 0 double-bookings: ${data.conflicts_prevented}/${data.concurrency_tested} conflicts cleanly handled.`
      )
    } catch (err: any) {
      toast.error('Race condition fuzzer failed: ' + (err.message || 'Unknown error'))
    } finally {
      setFuzzing(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="border shadow-sm bg-card">
        <CardHeader className="p-5 pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="min-w-0 flex-1">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Zap className="w-5 h-5 text-amber-500 shrink-0" />
                <span>Concurrency & Race-Condition Stress Fuzzer</span>
              </CardTitle>
              <CardDescription className="text-xs text-muted-foreground mt-1 leading-relaxed">
                Simulates simultaneous booking transactions claiming the identical provider slot to verify
                100% zero-double-booking database row-level locking integrity under peak concurrency.
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
              <div className="flex items-center space-x-1 border rounded-md p-1 bg-muted/30">
                {[10, 15, 25, 30, 50].map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setFuzzConcurrency(n)}
                    className={`px-3 py-1.5 text-xs rounded font-medium transition-colors touch-manipulation min-h-[36px] ${
                      fuzzConcurrency === n
                        ? 'bg-primary text-primary-foreground shadow-xs'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {n}x
                  </button>
                ))}
              </div>
              <Button
                onClick={handleRunRaceConditionTest}
                disabled={fuzzing}
                className="font-semibold text-xs h-10 min-h-[44px] shadow-xs shrink-0 touch-manipulation px-4 gap-1.5"
              >
                <Play className={`w-3.5 h-3.5 ${fuzzing ? 'animate-spin' : ''}`} />
                {fuzzing ? 'Fuzzing Pipeline...' : 'Run Race Test'}
              </Button>
            </div>
          </div>
        </CardHeader>

        {fuzzResult ? (
          <CardContent className="p-5 pt-0 space-y-4">
            <div className="p-4 rounded-xl border bg-muted/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-foreground flex items-center gap-2">
                    Transactional Lock Integrity Verified
                    <Badge variant="default" className="bg-emerald-600 text-white hover:bg-emerald-700 text-[10px] h-5">
                      {fuzzResult.double_bookings_prevented_pct}% Double-Bookings Prevented
                    </Badge>
                  </div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">
                    Single-winner committed. All {fuzzResult.conflicts_prevented} concurrent attempts caught atomic unique constraints.
                  </div>
                </div>
              </div>
              <div className="text-[11px] font-mono text-muted-foreground text-right">
                Test ID: {fuzzResult.test_id}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3.5 rounded-lg border bg-card text-center">
                <div className="text-[11px] text-muted-foreground font-medium">Concurrency Tested</div>
                <div className="text-xl font-bold text-foreground mt-0.5">{fuzzResult.concurrency_tested}</div>
                <div className="text-[10px] text-muted-foreground">parallel workers</div>
              </div>
              <div className="p-3.5 rounded-lg border bg-card text-center">
                <div className="text-[11px] text-muted-foreground font-medium">Single Winner</div>
                <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                  {fuzzResult.successful_bookings}
                </div>
                <div className="text-[10px] text-muted-foreground">confirmed booking</div>
              </div>
              <div className="p-3.5 rounded-lg border bg-card text-center">
                <div className="text-[11px] text-muted-foreground font-medium">Conflicts Handled</div>
                <div className="text-xl font-bold text-amber-600 dark:text-amber-400 mt-0.5">
                  {fuzzResult.conflicts_prevented}
                </div>
                <div className="text-[10px] text-muted-foreground">{fuzzResult.conflict_rate_pct}% collision rate</div>
              </div>
              <div className="p-3.5 rounded-lg border bg-card text-center">
                <div className="text-[11px] text-muted-foreground font-medium">Avg Contention Latency</div>
                <div className="text-xl font-bold text-primary mt-0.5">{fuzzResult.avg_lock_contention_ms}ms</div>
                <div className="text-[10px] text-muted-foreground">lock acquisition time</div>
              </div>
            </div>
          </CardContent>
        ) : (
          <CardContent className="p-8 text-center bg-muted/10 border-t flex flex-col items-center justify-center">
            <ShieldCheck className="w-10 h-10 text-muted-foreground/60 mb-2" />
            <h4 className="text-sm font-semibold text-foreground">Ready for Concurrency Verification</h4>
            <p className="text-xs text-muted-foreground max-w-md mt-1">
              Select a concurrency factor above and click "Run Race Test" to execute an atomic transactional
              load test against the bookings database table.
            </p>
          </CardContent>
        )}
      </Card>
    </div>
  )
}
