import React from 'react'
import { CheckSquare, Terminal, Compass, Activity } from 'lucide-react'
import type { CodexView } from '../../types'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

interface ActivityRailProps {
  activeView: CodexView
  onViewChange: (view: CodexView) => void
  ticketCount?: number
  activeSubagents?: number
  signalCount?: number
  className?: string
}

interface NavItem {
  id: CodexView
  label: string
  icon: React.ComponentType<{ className?: string }>
  badge?: number
}

export const ActivityRail: React.FC<ActivityRailProps> = ({
  activeView,
  onViewChange,
  ticketCount = 0,
  activeSubagents = 0,
  signalCount = 0,
  className,
}) => {
  const items: NavItem[] = [
    {
      id: 'tickets',
      label: 'Tickets & Tasks',
      icon: CheckSquare,
      badge: ticketCount > 0 ? ticketCount : undefined,
    },
    {
      id: 'coding',
      label: 'Coding & Terminal',
      icon: Terminal,
      badge: activeSubagents > 0 ? activeSubagents : undefined,
    },
    {
      id: 'planning',
      label: 'Architecture & Planning',
      icon: Compass,
    },
    {
      id: 'signals',
      label: 'Signals & Sentinels',
      icon: Activity,
      badge: signalCount > 0 ? signalCount : undefined,
    },
  ]

  return (
    <TooltipProvider delayDuration={150}>
      <aside
        data-testid="codex-activity-rail"
        className={cn(
          'hidden lg:flex flex-col items-center w-[52px] min-w-[52px] h-full py-3 bg-card/60 backdrop-blur-md border-r border-border/40 select-none z-20',
          className,
        )}
      >
        <div className="flex flex-col items-center space-y-2.5 w-full flex-1">
          {items.map((item) => {
            const isActive = activeView === item.id
            const Icon = item.icon

            return (
              <Tooltip key={item.id}>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={() => onViewChange(item.id)}
                    aria-label={item.label}
                    data-testid={`activity-rail-${item.id}`}
                    className={cn(
                      'relative group flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-primary',
                      isActive
                        ? 'bg-primary/15 text-primary shadow-sm'
                        : 'text-muted-foreground hover:bg-muted/70 hover:text-foreground',
                    )}
                  >
                    {/* Active vertical edge indicator */}
                    {isActive && (
                      <span className="absolute -left-[6px] top-2 bottom-2 w-1 rounded-r-full bg-primary" />
                    )}

                    <Icon className="h-5 w-5 transition-transform group-hover:scale-105" />

                    {/* Status Badge */}
                    {typeof item.badge === 'number' && (
                      <span className="absolute -top-1 -right-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground shadow-sm">
                        {item.badge > 99 ? '99+' : item.badge}
                      </span>
                    )}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right" sideOffset={12}>
                  <p className="font-medium text-xs">{item.label}</p>
                </TooltipContent>
              </Tooltip>
            )
          })}
        </div>
      </aside>
    </TooltipProvider>
  )
}
