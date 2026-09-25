import React from 'react'
import { CheckCircle2, Circle, Clock, AlertCircle, ListChecks } from 'lucide-react'
import type { PlanItem as PlanItemType } from '../../../types/workbench'
import { Badge } from '../../ui/badge'
import { cn } from '../../../lib/utils'

interface Props {
  item: PlanItemType
}

export const PlanItem: React.FC<Props> = ({ item }) => {
  const completedCount = item.tasks.filter(t => t.status === 'completed').length
  const totalCount = item.tasks.length
  const progressPercent = Math.round((completedCount / (totalCount || 1)) * 100)

  const getTaskIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-3.5 h-3.5 text-[var(--success)] flex-shrink-0" />
      case 'active':
        return <Clock className="w-3.5 h-3.5 text-[var(--accent)] animate-spin flex-shrink-0" />
      case 'blocked':
        return <AlertCircle className="w-3.5 h-3.5 text-[var(--danger)] flex-shrink-0" />
      default:
        return <Circle className="w-3.5 h-3.5 text-[var(--text-subtle)] flex-shrink-0" />
    }
  }

  return (
    <div className="my-3 max-w-4xl mx-auto border border-[var(--border)] rounded-lg bg-[var(--surface-primary)] p-3.5 shadow-xs text-xs">
      <div className="flex items-center justify-between gap-2 pb-2 mb-2.5 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <ListChecks className="w-4 h-4 text-[var(--accent)]" aria-hidden="true" />
          <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">{item.title}</h3>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] text-[var(--text-secondary)] font-mono">
            {completedCount} / {totalCount} done ({progressPercent}%)
          </span>
          <div className="w-16 h-1.5 rounded-full bg-[var(--surface-secondary)] overflow-hidden">
            <div
              className="h-full bg-[var(--accent)] transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      </div>

      <div className="space-y-1.5">
        {item.tasks.map((task) => (
          <div
            key={task.id}
            className={cn(
              'flex items-center gap-2.5 p-1.5 rounded transition-colors',
              task.status === 'active'
                ? 'bg-[var(--accent-subtle)]/40 font-medium'
                : 'hover:bg-[var(--surface-secondary)]'
            )}
          >
            {getTaskIcon(task.status)}
            <span
              className={cn(
                'text-xs flex-1',
                task.status === 'completed'
                  ? 'text-[var(--text-subtle)] line-through'
                  : task.status === 'active'
                  ? 'text-[var(--text-primary)] font-medium'
                  : 'text-[var(--text-secondary)]'
              )}
            >
              {task.title}
            </span>
            <Badge
              variant={
                task.status === 'completed' ? 'success' : task.status === 'active' ? 'default' : 'secondary'
              }
              className="text-[9px] py-0 px-1 capitalize"
            >
              {task.status}
            </Badge>
          </div>
        ))}
      </div>
    </div>
  )
}
