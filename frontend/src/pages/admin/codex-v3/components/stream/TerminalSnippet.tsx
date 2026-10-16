import React, { useState } from 'react'
import {
  Terminal as TerminalIcon,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Copy,
  Check,
  ChevronDown,
  Clock,
  Loader2
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TerminalOutput } from '../../types'

export interface TerminalSnippetProps {
  terminal?: TerminalOutput
  command?: string
  output?: string
  exitCode?: number
  passedCount?: number
  failedCount?: number
  skippedCount?: number
  durationMs?: number
  status?: 'running' | 'completed' | 'failed'
  defaultExpanded?: boolean
  className?: string
}

export const TerminalSnippet: React.FC<TerminalSnippetProps> = ({
  terminal,
  command: propCommand,
  output: propOutput,
  exitCode: propExitCode,
  passedCount: propPassedCount,
  failedCount: propFailedCount,
  skippedCount: propSkippedCount,
  durationMs: propDurationMs,
  status: propStatus,
  defaultExpanded = true,
  className,
}) => {
  const command = terminal?.command ?? propCommand ?? 'bash'
  const output = terminal?.output ?? propOutput ?? ''
  const exitCode = terminal?.exitCode ?? propExitCode
  const passedCount = terminal?.passedCount ?? propPassedCount
  const failedCount = terminal?.failedCount ?? propFailedCount
  const skippedCount = terminal?.skippedCount ?? propSkippedCount
  const durationMs = terminal?.durationMs ?? propDurationMs
  const status =
    terminal?.status ??
    propStatus ??
    (exitCode !== undefined ? (exitCode === 0 ? 'completed' : 'failed') : 'completed')

  const [isExpanded, setIsExpanded] = useState(defaultExpanded)
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (output) {
      navigator.clipboard.writeText(output)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const formatDuration = (ms?: number) => {
    if (typeof ms !== 'number') return null
    if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`
    return `${Math.round(ms)}ms`
  }

  const hasTestSummary =
    passedCount !== undefined || failedCount !== undefined || skippedCount !== undefined

  return (
    <div
      className={cn(
        'rounded-xl border border-zinc-800 bg-zinc-950 text-zinc-100 font-mono shadow-sm overflow-hidden transition-all',
        status === 'failed' && 'border-rose-900/50',
        status === 'running' && 'border-blue-900/50 ring-1 ring-blue-500/20',
        className
      )}
    >
      {/* Console Top Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 px-3.5 py-2.5 bg-zinc-900/90 border-b border-zinc-800/80">
        <div
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2.5 min-w-0 cursor-pointer select-none flex-1"
        >
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500/60 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/60 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/60 inline-block" />
          </div>

          <div className="flex items-center gap-2 min-w-0">
            <TerminalIcon className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
            <span className="text-xs font-semibold text-zinc-200 truncate">
              {command}
            </span>
          </div>
        </div>

        {/* Test Badges & Controls */}
        <div className="flex items-center gap-2 shrink-0">
          {hasTestSummary && (
            <div className="flex items-center gap-1.5 text-[11px]">
              {passedCount !== undefined && passedCount > 0 && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-950/80 text-emerald-400 border border-emerald-800/60">
                  <CheckCircle2 className="w-3 h-3" />
                  {passedCount} passed
                </span>
              )}
              {failedCount !== undefined && failedCount > 0 && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-rose-950/80 text-rose-400 border border-rose-800/60">
                  <XCircle className="w-3 h-3" />
                  {failedCount} failed
                </span>
              )}
              {skippedCount !== undefined && skippedCount > 0 && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-950/80 text-amber-400 border border-amber-800/60">
                  <AlertCircle className="w-3 h-3" />
                  {skippedCount} skipped
                </span>
              )}
            </div>
          )}

          {status === 'running' && (
            <span className="inline-flex items-center gap-1 text-[11px] text-blue-400 bg-blue-950/50 px-2 py-0.5 rounded border border-blue-900">
              <Loader2 className="w-3 h-3 animate-spin" />
              running
            </span>
          )}

          {durationMs !== undefined && (
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] text-zinc-500">
              <Clock className="w-3 h-3" />
              {formatDuration(durationMs)}
            </span>
          )}

          <button
            type="button"
            onClick={handleCopy}
            title="Copy output"
            className="p-1 text-zinc-400 hover:text-zinc-200 transition-colors rounded hover:bg-zinc-800"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? 'Collapse terminal' : 'Expand terminal'}
            className="p-1 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <ChevronDown
              className={cn(
                'w-4 h-4 transition-transform duration-200',
                isExpanded && 'rotate-180'
              )}
            />
          </button>
        </div>
      </div>

      {/* Terminal Body */}
      {isExpanded && (
        <div className="p-3 text-[11px] leading-relaxed max-h-72 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800">
          {output ? (
            <pre className="whitespace-pre-wrap break-all text-zinc-300 selection:bg-zinc-700 selection:text-white">
              {output}
            </pre>
          ) : (
            <p className="text-zinc-600 italic">(Empty output)</p>
          )}

          {exitCode !== undefined && (
            <div className="mt-2 pt-2 border-t border-zinc-900 flex items-center justify-between text-[10px] text-zinc-500">
              <span>Process exited with code {exitCode}</span>
              {exitCode === 0 ? (
                <span className="text-emerald-400">SUCCESS</span>
              ) : (
                <span className="text-rose-400">EXIT_FAILURE</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
export default TerminalSnippet
