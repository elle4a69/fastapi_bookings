import React from 'react'
import { User, Paperclip } from 'lucide-react'
import type { UserInstructionItem as UserInstructionItemType } from '../../../types/workbench'
import { Badge } from '../../ui/badge'

interface Props {
  item: UserInstructionItemType
}

export const UserInstructionItem: React.FC<Props> = ({ item }) => {
  return (
    <div className="flex items-start gap-3 my-4 p-4 rounded-lg bg-[var(--surface-secondary)] border border-[var(--border)] max-w-4xl mx-auto shadow-xs">
      <div className="w-8 h-8 rounded-full bg-[var(--accent)] text-[var(--accent-foreground)] flex items-center justify-center flex-shrink-0 font-medium text-xs shadow-xs">
        <User className="w-4 h-4" aria-hidden="true" />
      </div>

      <div className="flex-1 min-w-0 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">
              {item.authorName || 'Instruction'}
            </h3>
            <span className="text-[10px] text-[var(--text-subtle)] font-mono">
              {item.timestamp}
            </span>
          </div>
          <Badge variant="secondary" className="text-[10px] uppercase font-mono">
            User Turn
          </Badge>
        </div>

        <div className="text-xs text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap font-normal">
          {item.content}
        </div>

        {item.attachments && item.attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-2 border-t border-[var(--border)]/60">
            {item.attachments.map((att, idx) => (
              <div
                key={idx}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[var(--surface-primary)] border border-[var(--border)] text-[11px] text-[var(--text-secondary)] font-mono"
              >
                <Paperclip className="w-3 h-3 text-[var(--accent)]" />
                <span className="truncate max-w-[180px]">{att.name}</span>
                <span className="text-[10px] text-[var(--text-subtle)]">({att.size})</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
