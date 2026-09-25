import React, { useState } from 'react'
import { Bot, Copy, Check } from 'lucide-react'
import type { AgentMessageItem as AgentMessageItemType } from '../../../types/workbench'

interface Props {
  item: AgentMessageItemType
}

export const AgentMessageItem: React.FC<Props> = ({ item }) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(item.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Simple clean markdown parser for prose, headers, backtick code, and code fences
  const renderFormattedContent = (text: string) => {
    const lines = text.split('\n')
    const elements: React.ReactNode[] = []
    let inCodeBlock = false
    let codeBlockContent: string[] = []

    lines.forEach((line, idx) => {
      if (line.startsWith('```')) {
        if (inCodeBlock) {
          elements.push(
            <pre
              key={`code-${idx}`}
              className="p-3 my-2 rounded-md bg-[var(--code-bg)] border border-[var(--code-border)] font-mono text-xs text-[var(--text-primary)] overflow-x-auto"
            >
              <code>{codeBlockContent.join('\n')}</code>
            </pre>
          )
          codeBlockContent = []
          inCodeBlock = false
        } else {
          inCodeBlock = true
        }
        return
      }

      if (inCodeBlock) {
        codeBlockContent.push(line)
        return
      }

      if (line.startsWith('# ')) {
        elements.push(<h2 key={idx} className="text-sm font-bold text-[var(--text-primary)] mt-3 mb-1">{line.slice(2)}</h2>)
      } else if (line.startsWith('## ')) {
        elements.push(<h3 key={idx} className="text-xs font-bold text-[var(--text-primary)] mt-2.5 mb-1">{line.slice(3)}</h3>)
      } else if (line.startsWith('- ')) {
        elements.push(
          <li key={idx} className="ml-4 list-disc text-xs text-[var(--text-primary)] my-0.5 leading-relaxed">
            {renderInline(line.slice(2))}
          </li>
        )
      } else if (line.trim() === '') {
        elements.push(<div key={idx} className="h-2" />)
      } else {
        elements.push(
          <p key={idx} className="text-xs text-[var(--text-primary)] leading-relaxed my-1">
            {renderInline(line)}
          </p>
        )
      }
    })

    if (inCodeBlock && codeBlockContent.length > 0) {
      elements.push(
        <pre
          key="code-unfinished"
          className="p-3 my-2 rounded-md bg-[var(--code-bg)] border border-[var(--code-border)] font-mono text-xs text-[var(--text-primary)] overflow-x-auto"
        >
          <code>{codeBlockContent.join('\n')}</code>
        </pre>
      )
    }

    return elements
  }

  const renderInline = (line: string) => {
    const parts = line.split(/(`[^`]+`|\*\*[^*]+\*\*)/g)
    return parts.map((part, i) => {
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code
            key={i}
            className="px-1.5 py-0.5 rounded bg-[var(--code-bg)] border border-[var(--code-border)] font-mono text-[11px] text-[var(--accent)]"
          >
            {part.slice(1, -1)}
          </code>
        )
      }
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold text-[var(--text-primary)]">{part.slice(2, -2)}</strong>
      }
      return part
    })
  }

  return (
    <div className="flex items-start gap-3 my-3 p-4 rounded-lg bg-[var(--surface-primary)] border border-[var(--border)] max-w-4xl mx-auto shadow-xs group">
      <div className="w-8 h-8 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)] text-[var(--accent)] flex items-center justify-center flex-shrink-0 font-medium text-xs">
        <Bot className="w-4 h-4" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-xs text-[var(--text-primary)] m-0">Codex Assistant</h3>
            <span className="text-[10px] text-[var(--text-subtle)] font-mono">{item.timestamp}</span>
            {item.isStreaming && (
              <span className="inline-flex items-center gap-1 text-[10px] text-[var(--accent)] font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-ping" aria-hidden="true" />
                Streaming...
              </span>
            )}
          </div>

          <button
            onClick={handleCopy}
            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[var(--surface-hover)] text-[var(--text-subtle)] hover:text-[var(--text-primary)] transition-opacity"
            aria-label="Copy message"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-[var(--success)]" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>

        <div className="text-xs text-[var(--text-primary)] leading-relaxed">
          {renderFormattedContent(item.content)}
          {item.isStreaming && (
            <span className="inline-block w-2 h-4 ml-1 align-middle bg-[var(--accent)] animate-pulse" />
          )}
        </div>
      </div>
    </div>
  )
}
