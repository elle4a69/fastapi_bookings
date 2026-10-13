import React, { useState } from 'react'
import { Globe, ExternalLink, ChevronDown, ChevronRight } from 'lucide-react'
import type { WebResearchItem as WebResearchItemType } from '../../../types/workbench'

interface Props {
  item: WebResearchItemType
}

export const WebResearchItem: React.FC<Props> = ({ item }) => {
  const [isExpanded, setIsExpanded] = useState(false)

  const citations = item.citations || []

  return (
    <div className="my-2 max-w-4xl mx-auto border border-[var(--border)] rounded-md bg-[var(--surface-primary)] overflow-hidden text-xs w-full max-w-full break-words">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 flex items-center justify-between gap-2 bg-[var(--surface-secondary)]/40 hover:bg-[var(--surface-hover)] transition-colors cursor-pointer select-none text-left"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <Globe className="w-3.5 h-3.5 text-[var(--accent)] flex-shrink-0" aria-hidden="true" />
          <h3 className="font-medium text-xs text-[var(--text-primary)] truncate m-0">
            Research: &ldquo;{item.query}&rdquo;
          </h3>
          <span className="text-[11px] text-[var(--text-subtle)] truncate">— {item.summary}</span>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-[10px] text-[var(--text-subtle)]">
            {citations.length} sources
          </span>
          {isExpanded ? <ChevronDown className="w-3.5 h-3.5" aria-hidden="true" /> : <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />}
        </div>
      </button>

      {isExpanded && (
        <div className="p-3 border-t border-[var(--border)] space-y-2 bg-[var(--surface-secondary)]/20">
          {citations.map((cite, idx) => (
            <div key={idx} className="p-2 rounded bg-[var(--surface-primary)] border border-[var(--border)] break-words">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-xs text-[var(--text-primary)] truncate min-w-0">
                  {cite.title}
                </span>
                <a
                  href={cite.url}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`Open source link: ${cite.title || cite.url}`}
                  className="h-7 w-7 flex items-center justify-center text-[var(--accent)] hover:underline focus:outline-none focus:ring-1 focus:ring-[var(--accent)] flex-shrink-0"
                >
                  <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                </a>
              </div>
              <p className="text-[11px] text-[var(--text-secondary)] mt-1 line-clamp-2 break-words">
                {cite.snippet}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
