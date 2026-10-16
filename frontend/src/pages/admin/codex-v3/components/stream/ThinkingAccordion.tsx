import React, { useState } from 'react'
import { ChevronDown, Sparkles, BrainCircuit } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ThinkingBlock } from '../../types'

export interface ThinkingAccordionProps {
  thinking?: ThinkingBlock
  durationSeconds?: number
  steps?: string[]
  isThinking?: boolean
  defaultExpanded?: boolean
  className?: string
}

export const ThinkingAccordion: React.FC<ThinkingAccordionProps> = ({
  thinking,
  durationSeconds: propDuration,
  steps: propSteps,
  isThinking: propIsThinking,
  defaultExpanded = false,
  className,
}) => {
  const duration = thinking?.durationSeconds ?? propDuration ?? 0
  const steps = thinking?.steps ?? propSteps ?? []
  const isThinking = thinking?.isThinking ?? propIsThinking ?? false

  const [isOpen, setIsOpen] = useState(defaultExpanded || isThinking)

  const formattedDuration = duration >= 1 ? `${duration.toFixed(1)}s` : `${Math.round(duration * 1000)}ms`

  return (
    <div
      className={cn(
        'rounded-xl border border-border/60 bg-muted/20 backdrop-blur-xs transition-all overflow-hidden',
        isThinking && 'border-violet-500/40 shadow-xs shadow-violet-500/10',
        className
      )}
    >
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="w-full flex items-center justify-between gap-3 px-3.5 py-2.5 text-left text-xs text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-colors focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
      >
        <div className="flex items-center gap-2 min-w-0">
          {isThinking ? (
            <BrainCircuit className="w-4 h-4 text-violet-500 animate-pulse shrink-0" />
          ) : (
            <Sparkles className="w-4 h-4 text-violet-400 shrink-0" />
          )}

          <span
            className={cn(
              'font-medium truncate',
              isThinking
                ? 'bg-gradient-to-r from-violet-500 via-fuchsia-400 to-violet-500 bg-size-[200%_auto] animate-pulse bg-clip-text text-transparent font-semibold'
                : 'text-muted-foreground'
            )}
          >
            {isThinking
              ? `Thinking... (${formattedDuration})`
              : `Thought for ${formattedDuration}`}
          </span>

          {steps.length > 0 && (
            <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground font-mono">
              {steps.length} {steps.length === 1 ? 'step' : 'steps'}
            </span>
          )}
        </div>

        <ChevronDown
          className={cn(
            'w-4 h-4 text-muted-foreground shrink-0 transition-transform duration-200',
            isOpen && 'rotate-180 text-foreground'
          )}
        />
      </button>

      {isOpen && (
        <div className="px-4 pb-3 pt-1 border-t border-border/40 text-xs space-y-2.5">
          {steps.length === 0 ? (
            <p className="text-muted-foreground italic text-[11px]">
              {isThinking ? 'Synthesizing reasoning process...' : 'Reasoning steps not recorded.'}
            </p>
          ) : (
            <ol className="space-y-2 text-foreground/90 pl-1">
              {steps.map((step, idx) => (
                <li key={idx} className="flex items-start gap-2.5 group">
                  <span className="shrink-0 flex items-center justify-center w-4 h-4 rounded-full bg-violet-500/10 text-violet-500 font-mono text-[10px] font-semibold mt-0.5">
                    {idx + 1}
                  </span>
                  <div className="flex-1 min-w-0 leading-relaxed text-[12px] text-muted-foreground group-hover:text-foreground transition-colors">
                    {step}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  )
}
export default ThinkingAccordion
