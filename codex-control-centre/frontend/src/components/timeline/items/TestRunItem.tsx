import React, { useState } from 'react'
import { CheckCircle2, XCircle, ChevronDown, ChevronRight, FlaskConical, Clock } from 'lucide-react'
import type { TestRunItem as TestRunItemType } from '../../../types/workbench'
import { Badge } from '../../ui/badge'

interface Props {
  item: TestRunItemType
}

export const TestRunItem: React.FC<Props> = ({ item }) => {
  const [isExpanded, setIsExpanded] = useState(false)

  const totalPassed = item.suites.reduce((acc, s) => acc + s.passed, 0)
  const totalFailed = item.suites.reduce((acc, s) => acc + s.failed, 0)
  const durationSec = (item.totalDurationMs / 1000).toFixed(2)

  return (
    <div className="my-2 max-w-4xl mx-auto border border-[var(--border)] rounded-md bg-[var(--surface-primary)] overflow-hidden text-xs shadow-xs">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 flex items-center justify-between gap-2 bg-[var(--surface-secondary)]/40 hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none text-left"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <FlaskConical className="w-3.5 h-3.5 text-[var(--accent)] flex-shrink-0" />
          <span className="font-semibold text-xs text-[var(--text-primary)] truncate">
            {item.framework} Test Run
          </span>
          <span className="text-[11px] text-[var(--text-secondary)]">
            — {totalPassed} passed{totalFailed > 0 ? `, ${totalFailed} failed` : ''}
          </span>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-[10px] text-[var(--text-subtle)] font-mono flex items-center gap-0.5">
            <Clock className="w-2.5 h-2.5" />
            {durationSec}s
          </span>

          <Badge
            variant={item.status === 'passed' ? 'success' : 'danger'}
            className="text-[9px] py-0 px-1.5 uppercase font-mono"
          >
            {item.status}
          </Badge>

          {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-[var(--text-subtle)]" /> : <ChevronRight className="w-3.5 h-3.5 text-[var(--text-subtle)]" />}
        </div>
      </button>

      {isExpanded && (
        <div className="p-3 border-t border-[var(--border)] space-y-2 bg-[var(--surface-secondary)]/20">
          {item.suites.map((suite, idx) => (
            <div key={idx} className="p-2.5 rounded bg-[var(--surface-primary)] border border-[var(--border)]">
              <div className="flex items-center justify-between font-mono text-xs">
                <span className="font-semibold text-[var(--text-primary)] truncate">{suite.name}</span>
                <span className="text-[10px] text-[var(--text-subtle)]">{(suite.durationMs / 1000).toFixed(2)}s</span>
              </div>

              <div className="flex items-center gap-2 mt-1.5 text-[11px]">
                <span className="text-[var(--success)] flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> {suite.passed} passed
                </span>
                {suite.failed > 0 && (
                  <span className="text-[var(--danger)] flex items-center gap-1">
                    <XCircle className="w-3 h-3" /> {suite.failed} failed
                  </span>
                )}
              </div>

              {suite.failures && suite.failures.length > 0 && (
                <div className="mt-2 p-2 rounded bg-[var(--code-bg)] border border-[var(--code-border)] text-xs font-mono text-[var(--danger)] space-y-1">
                  {suite.failures.map((f, fIdx) => (
                    <div key={fIdx}>
                      <div className="font-semibold">{f.testName}</div>
                      <div className="text-[11px] text-[var(--text-secondary)]">{f.message}</div>
                      {f.trace && <pre className="text-[10px] text-[var(--text-subtle)] mt-1 whitespace-pre-wrap">{f.trace}</pre>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
