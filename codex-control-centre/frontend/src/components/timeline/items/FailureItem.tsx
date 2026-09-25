import React, { useState } from 'react'
import { XCircle, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react'
import type { FailureItem as FailureItemType } from '../../../types/workbench'
import { Button } from '../../ui/button'
import { Badge } from '../../ui/badge'

interface Props {
  item: FailureItemType
}

export const FailureItem: React.FC<Props> = ({ item }) => {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className="my-3 max-w-4xl mx-auto border border-[var(--danger)] rounded-lg bg-[var(--danger-subtle)]/30 p-3.5 shadow-xs text-xs space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <XCircle className="w-4 h-4 text-[var(--danger)] flex-shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-xs text-[var(--danger)]">
              Turn Failed: {item.summary}
            </div>
            <div className="text-[10px] text-[var(--text-subtle)] font-mono uppercase mt-0.5">
              Category: {item.errorCategory.replace('_', ' ')}
            </div>
          </div>
        </div>

        <Badge variant="danger" className="uppercase font-mono text-[9px]">
          {item.errorCategory}
        </Badge>
      </div>

      {item.details && (
        <div>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 text-[11px] text-[var(--danger)] hover:underline font-medium cursor-pointer"
          >
            {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            {isExpanded ? 'Hide diagnostic trace' : 'View diagnostic trace'}
          </button>

          {isExpanded && (
            <pre className="mt-2 p-2.5 rounded bg-[var(--code-bg)] border border-[var(--code-border)] font-mono text-[11px] text-[var(--danger)] whitespace-pre-wrap">
              {item.details}
            </pre>
          )}
        </div>
      )}

      {item.canRetry && (
        <div className="flex justify-end pt-1">
          <Button size="sm" variant="dangerOutline" className="h-6 text-xs gap-1">
            <RefreshCw className="w-3 h-3" />
            Retry Turn
          </Button>
        </div>
      )}
    </div>
  )
}
