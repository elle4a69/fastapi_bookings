import React from 'react'
import { AlertTriangle } from 'lucide-react'
import type { WarningItem as WarningItemType } from '../../../types/workbench'
import { Button } from '../../ui/button'

interface Props {
  item: WarningItemType
}

export const WarningItem: React.FC<Props> = ({ item }) => {
  return (
    <div className="my-2 max-w-4xl mx-auto flex items-start justify-between gap-3 p-3 rounded-md bg-[var(--warning-subtle)]/40 border border-[var(--warning)] text-xs text-[var(--text-primary)]">
      <div className="flex items-start gap-2 min-w-0">
        <AlertTriangle className="w-4 h-4 text-[var(--warning)] flex-shrink-0 mt-0.5" />
        <div>
          <div className="font-semibold text-xs text-[var(--warning)]">{item.title}</div>
          <div className="text-[11px] text-[var(--text-secondary)] mt-0.5">{item.message}</div>
        </div>
      </div>

      {item.actionLabel && (
        <Button size="sm" variant="outline" className="h-6 text-[10px]">
          {item.actionLabel}
        </Button>
      )}
    </div>
  )
}
