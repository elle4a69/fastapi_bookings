import React, { useState } from 'react'
import { Columns2, AlignJustify, Copy, Check } from 'lucide-react'
import type { DiffFile } from '../../types/workbench'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import { cn } from '../../lib/utils'

interface DiffViewerProps {
  file: DiffFile
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ file }) => {
  const [viewMode, setViewMode] = useState<'unified' | 'split'>('split')
  const [copied, setCopied] = useState(false)

  const handleCopyPath = () => {
    navigator.clipboard.writeText(file.path)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-[var(--surface-primary)] border border-[var(--border)] rounded-lg text-xs select-text">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--border)] bg-[var(--surface-secondary)]/50 select-none flex-shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-mono font-semibold text-xs text-[var(--text-primary)] truncate">
            {file.path}
          </span>
          <Badge
            variant={file.status === 'added' ? 'success' : 'default'}
            className="text-[9px] py-0 px-1.5 uppercase font-mono"
          >
            {file.status}
          </Badge>
          <div className="flex items-center gap-1.5 font-mono text-[11px] ml-1">
            <span className="text-[var(--success)] font-medium">+{file.additions}</span>
            <span className="text-[var(--danger)] font-medium">-{file.deletions}</span>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {/* Mode Switcher */}
          <div className="flex items-center rounded-md border border-[var(--border)] bg-[var(--surface-primary)] p-0.5">
            <button
              onClick={() => setViewMode('unified')}
              className={cn(
                'px-2 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1 cursor-pointer',
                viewMode === 'unified'
                  ? 'bg-[var(--surface-hover)] text-[var(--text-primary)] shadow-2xs'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              )}
            >
              <AlignJustify className="w-3 h-3" />
              Unified
            </button>
            <button
              onClick={() => setViewMode('split')}
              className={cn(
                'px-2 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1 cursor-pointer hidden md:flex',
                viewMode === 'split'
                  ? 'bg-[var(--surface-hover)] text-[var(--text-primary)] shadow-2xs'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              )}
            >
              <Columns2 className="w-3 h-3" />
              Split
            </button>
          </div>

          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={handleCopyPath}
          >
            {copied ? <Check className="w-3 h-3 text-[var(--success)]" /> : <Copy className="w-3 h-3" />}
          </Button>
        </div>
      </div>

      {/* Diff Content */}
      <div className="flex-1 overflow-auto font-mono text-xs leading-relaxed bg-[var(--code-bg)]">
        {file.hunks.map((hunk, hIdx) => (
          <div key={hIdx} className="border-b border-[var(--code-border)] last:border-b-0">
            {/* Hunk header */}
            <div className="px-3 py-1 bg-[var(--surface-secondary)] text-[10px] text-[var(--text-subtle)] font-mono select-none sticky top-0 border-y border-[var(--border)]">
              {hunk.header}
            </div>

            {/* Hunk lines in Unified View */}
            {viewMode === 'unified' ? (
              <div className="divide-y divide-transparent">
                {hunk.lines.map((line, lIdx) => {
                  const isAdd = line.type === 'add'
                  const isDel = line.type === 'del'

                  return (
                    <div
                      key={lIdx}
                      className={cn(
                        'flex items-start px-2 py-0.5 hover:opacity-90',
                        isAdd && 'bg-[var(--diff-add-bg)] text-[var(--diff-add-text)]',
                        isDel && 'bg-[var(--diff-del-bg)] text-[var(--diff-del-text)]',
                        !isAdd && !isDel && 'text-[var(--text-primary)]'
                      )}
                    >
                      {/* Old Line No */}
                      <span className="w-8 select-none text-right pr-2 text-[10px] text-[var(--text-subtle)] opacity-50 flex-shrink-0">
                        {line.oldLineNumber ?? ''}
                      </span>
                      {/* New Line No */}
                      <span className="w-8 select-none text-right pr-3 text-[10px] text-[var(--text-subtle)] opacity-50 flex-shrink-0">
                        {line.newLineNumber ?? ''}
                      </span>
                      {/* Sign */}
                      <span className="w-4 select-none text-center font-bold flex-shrink-0">
                        {isAdd ? '+' : isDel ? '-' : ' '}
                      </span>
                      {/* Content */}
                      <span className="flex-1 whitespace-pre-wrap break-all">
                        {line.content.replace(/^[+-]/, '')}
                      </span>
                    </div>
                  )
                })}
              </div>
            ) : (
              /* Hunk lines in Split View */
              <div className="grid grid-cols-2 divide-x divide-[var(--code-border)]">
                {/* Left (Old) and Right (New) columns */}
                <div className="overflow-x-auto">
                  {hunk.lines
                    .filter(l => l.type === 'context' || l.type === 'del')
                    .map((line, lIdx) => (
                      <div
                        key={lIdx}
                        className={cn(
                          'flex items-start px-2 py-0.5',
                          line.type === 'del' && 'bg-[var(--diff-del-bg)] text-[var(--diff-del-text)]',
                          line.type === 'context' && 'text-[var(--text-secondary)]'
                        )}
                      >
                        <span className="w-8 select-none text-right pr-2 text-[10px] text-[var(--text-subtle)] opacity-50 flex-shrink-0">
                          {line.oldLineNumber ?? ''}
                        </span>
                        <span className="flex-1 whitespace-pre-wrap break-all pl-2">
                          {line.content.replace(/^[+-]/, '')}
                        </span>
                      </div>
                    ))}
                </div>

                <div className="overflow-x-auto">
                  {hunk.lines
                    .filter(l => l.type === 'context' || l.type === 'add')
                    .map((line, lIdx) => (
                      <div
                        key={lIdx}
                        className={cn(
                          'flex items-start px-2 py-0.5',
                          line.type === 'add' && 'bg-[var(--diff-add-bg)] text-[var(--diff-add-text)]',
                          line.type === 'context' && 'text-[var(--text-primary)]'
                        )}
                      >
                        <span className="w-8 select-none text-right pr-2 text-[10px] text-[var(--text-subtle)] opacity-50 flex-shrink-0">
                          {line.newLineNumber ?? ''}
                        </span>
                        <span className="flex-1 whitespace-pre-wrap break-all pl-2">
                          {line.content.replace(/^[+-]/, '')}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
