import React, { useState, useMemo } from 'react'
import {
  FileDiff,
  Check,
  X,
  ChevronDown,
  Copy
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FilePatch } from '../../types'

export interface InlineDiffCardProps {
  patch?: FilePatch
  filePath?: string
  diff?: string
  additions?: number
  deletions?: number
  status?: 'pending' | 'accepted' | 'rejected' | 'discarded'
  onAccept?: (patchId: string) => void
  onDiscard?: (patchId: string) => void
  className?: string
  defaultExpanded?: boolean
}

interface ParsedDiffLine {
  type: 'add' | 'delete' | 'hunk' | 'context'
  content: string
  oldLineNumber?: number
  newLineNumber?: number
}

export const InlineDiffCard: React.FC<InlineDiffCardProps> = ({
  patch,
  filePath: propFilePath,
  diff: propDiff,
  additions: propAdditions,
  deletions: propDeletions,
  status: propStatus = 'pending',
  onAccept,
  onDiscard,
  className,
  defaultExpanded = true,
}) => {
  const patchId = patch?.id ?? 'patch-unknown'
  const filePath = patch?.filePath ?? propFilePath ?? 'unnamed_file'
  const diffText =
    patch?.diff ?? (patch?.diffHunks ? patch.diffHunks.join('\n') : propDiff ?? '')
  const additions = patch?.additions ?? propAdditions ?? 0
  const deletions = patch?.deletions ?? propDeletions ?? 0
  const [currentStatus, setCurrentStatus] = useState<'pending' | 'accepted' | 'rejected' | 'discarded'>(
    patch?.status ?? propStatus
  )

  const [isExpanded, setIsExpanded] = useState(defaultExpanded)
  const [copied, setCopied] = useState(false)

  // Parse diff text into structured lines with line numbers
  const parsedLines: ParsedDiffLine[] = useMemo(() => {
    if (!diffText) return []
    const lines = diffText.split('\n')
    const result: ParsedDiffLine[] = []

    let oldLine = 1
    let newLine = 1

    for (const line of lines) {
      if (line.startsWith('@@')) {
        // Hunk header e.g. @@ -1,5 +1,6 @@
        const match = line.match(/@@\s*-(\d+)(?:,\d+)?\s*\+(\d+)(?:,\d+)?\s*@@/)
        if (match) {
          oldLine = parseInt(match[1], 10)
          newLine = parseInt(match[2], 10)
        }
        result.push({
          type: 'hunk',
          content: line,
        })
      } else if (line.startsWith('+') && !line.startsWith('+++')) {
        result.push({
          type: 'add',
          content: line.slice(1),
          newLineNumber: newLine++,
        })
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        result.push({
          type: 'delete',
          content: line.slice(1),
          oldLineNumber: oldLine++,
        })
      } else {
        const content = line.startsWith(' ') ? line.slice(1) : line
        result.push({
          type: 'context',
          content,
          oldLineNumber: oldLine++,
          newLineNumber: newLine++,
        })
      }
    }

    return result
  }, [diffText])

  const handleAccept = () => {
    setCurrentStatus('accepted')
    onAccept?.(patchId)
  }

  const handleDiscard = () => {
    setCurrentStatus('discarded')
    onDiscard?.(patchId)
  }

  const handleCopy = () => {
    if (diffText) {
      navigator.clipboard.writeText(diffText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div
      className={cn(
        'rounded-xl border border-border/80 bg-zinc-950 text-zinc-100 shadow-sm overflow-hidden transition-all',
        currentStatus === 'accepted' && 'border-emerald-500/40 ring-1 ring-emerald-500/20',
        currentStatus === 'discarded' && 'border-rose-500/40 opacity-70',
        className
      )}
    >
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-3.5 py-2.5 bg-zinc-900 border-b border-zinc-800">
        <div
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2.5 min-w-0 cursor-pointer select-none flex-1"
        >
          <FileDiff className="w-4 h-4 text-zinc-400 shrink-0" />
          <span className="text-xs font-mono font-medium text-zinc-200 truncate">
            {filePath}
          </span>

          <div className="flex items-center gap-1.5 text-[11px] font-mono shrink-0 ml-1">
            <span className="text-emerald-400 font-semibold">+{additions}</span>
            <span className="text-rose-400 font-semibold">-{deletions}</span>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 shrink-0">
          {currentStatus === 'pending' ? (
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleDiscard}
                title="Discard file patch"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-rose-300 bg-rose-950/60 border border-rose-800/60 hover:bg-rose-900/80 active:scale-95 transition-all cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
                <span>Discard</span>
              </button>

              <button
                type="button"
                onClick={handleAccept}
                title="Accept file patch"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-emerald-200 bg-emerald-950/80 border border-emerald-700/80 hover:bg-emerald-900/90 active:scale-95 transition-all cursor-pointer shadow-xs"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Accept</span>
              </button>
            </div>
          ) : (
            <span
              className={cn(
                'text-[11px] font-medium px-2 py-0.5 rounded-full border',
                currentStatus === 'accepted'
                  ? 'bg-emerald-950/80 text-emerald-400 border-emerald-800'
                  : 'bg-rose-950/80 text-rose-400 border-rose-800'
              )}
            >
              {currentStatus === 'accepted' ? 'Accepted' : 'Discarded'}
            </span>
          )}

          <button
            type="button"
            onClick={handleCopy}
            title="Copy diff patch"
            className="p-1 text-zinc-400 hover:text-zinc-200 transition-colors rounded hover:bg-zinc-800"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? 'Collapse diff' : 'Expand diff'}
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

      {/* Diff Content Body */}
      {isExpanded && (
        <div className="font-mono text-[11px] leading-snug overflow-x-auto max-h-96 divide-y divide-zinc-900">
          {parsedLines.length === 0 ? (
            <div className="p-4 text-zinc-500 italic text-center">
              No patch modifications to display.
            </div>
          ) : (
            parsedLines.map((line, idx) => {
              if (line.type === 'hunk') {
                return (
                  <div
                    key={idx}
                    className="bg-blue-950/30 text-blue-400/90 px-3 py-1 text-[10px] select-none font-medium italic border-y border-blue-900/20"
                  >
                    {line.content}
                  </div>
                )
              }

              return (
                <div
                  key={idx}
                  className={cn(
                    'flex items-stretch hover:bg-zinc-900/60 transition-colors',
                    line.type === 'add' && 'bg-emerald-950/40 text-emerald-200',
                    line.type === 'delete' && 'bg-rose-950/40 text-rose-200'
                  )}
                >
                  {/* Line Numbers */}
                  <div className="flex shrink-0 select-none text-[10px] text-zinc-500 border-r border-zinc-800/80 bg-zinc-950/50">
                    <span className="w-9 px-1 text-right py-0.5">
                      {line.oldLineNumber ?? ''}
                    </span>
                    <span className="w-9 px-1 text-right py-0.5 border-l border-zinc-900">
                      {line.newLineNumber ?? ''}
                    </span>
                  </div>

                  {/* Diff marker */}
                  <div className="w-6 shrink-0 flex items-center justify-center font-bold select-none text-xs">
                    {line.type === 'add' && <span className="text-emerald-400">+</span>}
                    {line.type === 'delete' && <span className="text-rose-400">-</span>}
                    {line.type === 'context' && <span className="text-zinc-600"> </span>}
                  </div>

                  {/* Code Line Content */}
                  <div className="px-2 py-0.5 whitespace-pre flex-1 font-mono break-all overflow-hidden text-ellipsis">
                    {line.content || ' '}
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}
export default InlineDiffCard
