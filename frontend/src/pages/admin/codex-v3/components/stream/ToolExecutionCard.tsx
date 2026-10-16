import React, { useState } from 'react'
import {
  Wrench,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  ChevronDown,
  Copy,
  Check,
  FileCode2
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ToolExecution, ToolStatus } from '../../types'

export interface ToolExecutionCardProps {
  tool?: ToolExecution
  toolName?: string
  status?: ToolStatus
  targetFile?: string
  durationMs?: number
  args?: Record<string, unknown> | string
  stdout?: string
  stderr?: string
  className?: string
  defaultExpanded?: boolean
}

export const ToolExecutionCard: React.FC<ToolExecutionCardProps> = ({
  tool,
  toolName: propToolName,
  status: propStatus,
  targetFile: propTargetFile,
  durationMs: propDurationMs,
  args: propArgs,
  stdout: propStdout,
  stderr: propStderr,
  className,
  defaultExpanded = false,
}) => {
  const toolName = tool?.toolName ?? propToolName ?? 'unknown_tool'
  const status: ToolStatus = tool?.status ?? propStatus ?? 'running'
  const targetFile = tool?.targetFile ?? propTargetFile
  const durationMs = tool?.durationMs ?? propDurationMs
  const rawArgs = tool?.args ?? propArgs
  const stdout = tool?.stdout ?? propStdout
  const stderr = tool?.stderr ?? propStderr

  const [isOpen, setIsOpen] = useState(defaultExpanded)
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState<'args' | 'output'>('output')

  const formattedDuration =
    typeof durationMs === 'number'
      ? durationMs >= 1000
        ? `${(durationMs / 1000).toFixed(2)}s`
        : `${Math.round(durationMs)}ms`
      : null

  const stringifiedArgs =
    typeof rawArgs === 'string'
      ? rawArgs
      : rawArgs
      ? JSON.stringify(rawArgs, null, 2)
      : null

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation()
    const content = activeTab === 'args' ? stringifiedArgs : (stdout || stderr || '')
    if (content) {
      navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const renderStatusBadge = () => {
    switch (status) {
      case 'running':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-500/10 text-blue-500 border border-blue-500/20">
            <Loader2 className="w-3 h-3 animate-spin" />
            running
          </span>
        )
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" />
            completed
          </span>
        )
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/10 text-rose-500 border border-rose-500/20">
            <XCircle className="w-3 h-3" />
            failed
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-muted text-muted-foreground">
            {status}
          </span>
        )
    }
  }

  const hasDetails = Boolean(stringifiedArgs || stdout || stderr)

  return (
    <div
      className={cn(
        'rounded-xl border border-border/70 bg-card/60 backdrop-blur-xs shadow-xs overflow-hidden transition-all',
        status === 'running' && 'border-blue-500/30 ring-1 ring-blue-500/10',
        status === 'failed' && 'border-rose-500/30',
        className
      )}
    >
      <div
        onClick={() => hasDetails && setIsOpen(!isOpen)}
        className={cn(
          'w-full flex items-center justify-between gap-3 px-3.5 py-2.5 text-left text-xs font-mono select-none',
          hasDetails ? 'cursor-pointer hover:bg-muted/40 transition-colors' : 'cursor-default'
        )}
      >
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <div className="p-1.5 rounded-md bg-muted text-muted-foreground shrink-0">
            <Wrench className="w-3.5 h-3.5" />
          </div>

          <div className="flex items-center gap-2 min-w-0 flex-wrap">
            <span className="font-semibold text-foreground tracking-tight truncate">
              {toolName}
            </span>

            {targetFile && (
              <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground bg-muted/60 px-2 py-0.5 rounded-md border border-border/40 truncate max-w-[240px] sm:max-w-[320px]">
                <FileCode2 className="w-3 h-3 shrink-0 text-muted-foreground" />
                <span className="truncate">{targetFile}</span>
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          {formattedDuration && (
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] text-muted-foreground font-mono">
              <Clock className="w-3 h-3" />
              {formattedDuration}
            </span>
          )}

          {renderStatusBadge()}

          {hasDetails && (
            <button
              type="button"
              aria-label={isOpen ? 'Collapse tool output' : 'Expand tool output'}
              className="p-1 text-muted-foreground hover:text-foreground"
            >
              <ChevronDown
                className={cn(
                  'w-3.5 h-3.5 transition-transform duration-200',
                  isOpen && 'rotate-180'
                )}
              />
            </button>
          )}
        </div>
      </div>

      {isOpen && hasDetails && (
        <div className="border-t border-border/50 bg-zinc-950 text-zinc-200 text-xs font-mono">
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-zinc-800 bg-zinc-900/80">
            <div className="flex items-center gap-1">
              {stringifiedArgs && (
                <button
                  type="button"
                  onClick={() => setActiveTab('args')}
                  className={cn(
                    'px-2 py-0.5 rounded text-[11px] font-medium transition-colors',
                    activeTab === 'args'
                      ? 'bg-zinc-800 text-zinc-100'
                      : 'text-zinc-400 hover:text-zinc-200'
                  )}
                >
                  Arguments
                </button>
              )}
              {(stdout || stderr) && (
                <button
                  type="button"
                  onClick={() => setActiveTab('output')}
                  className={cn(
                    'px-2 py-0.5 rounded text-[11px] font-medium transition-colors',
                    activeTab === 'output'
                      ? 'bg-zinc-800 text-zinc-100'
                      : 'text-zinc-400 hover:text-zinc-200'
                  )}
                >
                  Output
                </button>
              )}
            </div>

            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1 text-[11px] text-zinc-400 hover:text-zinc-100 transition-colors p-1"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400" />
                  <span className="text-emerald-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>

          <div className="p-3 max-h-60 overflow-auto scrollbar-thin scrollbar-thumb-zinc-800">
            {activeTab === 'args' && stringifiedArgs && (
              <pre className="text-[11px] leading-relaxed text-zinc-300 whitespace-pre-wrap break-all">
                {stringifiedArgs}
              </pre>
            )}

            {activeTab === 'output' && (
              <>
                {stderr && (
                  <pre className="text-[11px] leading-relaxed text-rose-400 whitespace-pre-wrap break-all mb-2">
                    {stderr}
                  </pre>
                )}
                {stdout && (
                  <pre className="text-[11px] leading-relaxed text-zinc-300 whitespace-pre-wrap break-all">
                    {stdout}
                  </pre>
                )}
                {!stdout && !stderr && (
                  <p className="text-zinc-500 italic text-[11px]">(No output returned)</p>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
export default ToolExecutionCard
