import React, { useState } from 'react'
import { 
  Terminal, 
  ChevronDown, 
  ChevronRight, 
  Copy, 
  Check, 
  Search, 
  WrapText, 
  Clock 
} from 'lucide-react'
import type { CommandExecutionItem as CommandExecutionItemType } from '../../../types/workbench'
import { Badge } from '../../ui/badge'
import { cn } from '../../../lib/utils'

interface Props {
  item: CommandExecutionItemType
}

export const CommandExecutionItem: React.FC<Props> = ({ item }) => {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isCopied, setIsCopied] = useState(false)
  const [isWrapped, setIsWrapped] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')

  const durationFormatted = (item.durationMs / 1000).toFixed(2)

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation()
    navigator.clipboard.writeText(`${item.command}\n\n${item.stdout}`)
    setIsCopied(true)
    setTimeout(() => setIsCopied(false), 2000)
  }

  const outputLines = item.stdout.split('\n')
  const filteredLines = searchQuery
    ? outputLines.filter(line => line.toLowerCase().includes(searchQuery.toLowerCase()))
    : outputLines

  return (
    <div className="my-2 max-w-4xl mx-auto border border-[var(--border)] rounded-md bg-[var(--surface-primary)] overflow-hidden text-xs shadow-xs">
      {/* Header bar */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 flex items-center justify-between gap-2 bg-[var(--surface-secondary)]/50 hover:bg-[var(--surface-hover)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] transition-colors cursor-pointer text-left"
        aria-expanded={isExpanded}
        aria-label={`Command execution: ${item.command}`}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <Terminal className="w-3.5 h-3.5 text-[var(--accent)] flex-shrink-0" aria-hidden="true" />
          <span className="font-mono font-medium text-xs text-[var(--text-primary)] truncate max-w-md">
            $ {item.command}
          </span>
          <span className="text-[10px] text-[var(--text-subtle)] truncate hidden sm:inline">
            in {item.workingDirectory}
          </span>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-[10px] text-[var(--text-subtle)] font-mono flex items-center gap-0.5">
            <Clock className="w-2.5 h-2.5" aria-hidden="true" />
            {durationFormatted}s
          </span>

          <Badge
            variant={item.status === 'completed' ? 'success' : item.status === 'failed' ? 'danger' : 'default'}
            className="text-[9px] py-0 px-1.5 uppercase font-mono"
          >
            {item.status === 'completed' && item.exitCode !== undefined ? `exit ${item.exitCode}` : item.status}
          </Badge>

          <span className="text-[var(--text-subtle)]">
            {isExpanded ? <ChevronDown className="w-3.5 h-3.5" aria-hidden="true" /> : <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />}
          </span>
        </div>
      </button>

      {/* Expanded Terminal Area */}
      {isExpanded && (
        <div className="border-t border-[var(--border)] bg-[var(--code-bg)]">
          {/* Terminal toolbar */}
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--code-border)] bg-[var(--surface-secondary)]/30 text-[11px] text-[var(--text-secondary)]">
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="w-3 h-3 absolute left-1.5 top-1/2 -translate-y-1/2 text-[var(--text-subtle)]" aria-hidden="true" />
                <input
                  type="text"
                  placeholder="Filter stdout..."
                  aria-label="Filter terminal stdout"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-5 pl-6 pr-2 text-[10px] rounded bg-[var(--surface-primary)] border border-[var(--border)] text-[var(--text-primary)] outline-none w-28 sm:w-40 focus:ring-1 focus:ring-[var(--accent)]"
                />
              </div>
              <span className="text-[10px] text-[var(--text-subtle)]">
                {filteredLines.length} lines
              </span>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setIsWrapped(!isWrapped)}
                className={cn(
                  'p-1 rounded text-[10px] flex items-center gap-1 transition-colors focus:outline-none focus:ring-1 focus:ring-[var(--accent)]',
                  isWrapped ? 'bg-[var(--surface-hover)] text-[var(--text-primary)]' : 'text-[var(--text-subtle)]'
                )}
                aria-label="Toggle word wrap"
              >
                <WrapText className="w-3 h-3" />
                <span className="hidden sm:inline">Wrap</span>
              </button>

              <button
                type="button"
                onClick={handleCopy}
                className="p-1 rounded text-[10px] flex items-center gap-1 text-[var(--text-subtle)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-hover)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
                aria-label="Copy terminal command and output"
              >
                {isCopied ? <Check className="w-3 h-3 text-[var(--success)]" /> : <Copy className="w-3 h-3" />}
                <span className="hidden sm:inline">Copy</span>
              </button>
            </div>
          </div>

          {/* Terminal Output */}
          <div
            className={cn(
              'p-3 font-mono text-[11px] leading-relaxed max-h-72 overflow-y-auto text-[var(--text-primary)] select-text',
              isWrapped ? 'whitespace-pre-wrap' : 'whitespace-pre overflow-x-auto'
            )}
          >
            {filteredLines.map((line, idx) => (
              <div key={idx} className="table-row hover:bg-white/5">
                <span className="table-cell select-none pr-3 text-right text-[var(--text-subtle)] opacity-50 text-[10px] w-6">
                  {idx + 1}
                </span>
                <span className="table-cell">{line}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
