import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Sparkles,
  User,
  ArrowDown,
  Lock,
  Unlock,
  Copy,
  Check,
  Bot
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TimelineEvent, VoiceState } from '../../types'
import { ThinkingAccordion } from './ThinkingAccordion'
import { ToolExecutionCard } from './ToolExecutionCard'
import { SubagentCard } from './SubagentCard'
import { InlineDiffCard } from './InlineDiffCard'
import { ApprovalGateCard } from './ApprovalGateCard'
import { TerminalSnippet } from './TerminalSnippet'
import { ComposerBar } from './ComposerBar'

export interface TransparentStreamProps {
  events: TimelineEvent[]
  isStreaming?: boolean
  voiceState?: VoiceState
  onSendMessage?: (message: string) => void
  onStopStreaming?: () => void
  onAcceptDiff?: (patchId: string) => void
  onDiscardDiff?: (patchId: string) => void
  onApproveGate?: (gateId: string) => void
  onRejectGate?: (gateId: string, feedback?: string) => void
  onViewSubagentThread?: (threadId: string) => void
  onAttach?: () => void
  onToggleVoice?: () => void
  headerSlot?: React.ReactNode
  footerSlot?: React.ReactNode
  className?: string
}

export const TransparentStream: React.FC<TransparentStreamProps> = ({
  events,
  isStreaming = false,
  voiceState = 'idle',
  onSendMessage,
  onStopStreaming,
  onAcceptDiff,
  onDiscardDiff,
  onApproveGate,
  onRejectGate,
  onViewSubagentThread,
  onAttach,
  onToggleVoice,
  headerSlot,
  footerSlot,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const bottomAnchorRef = useRef<HTMLDivElement>(null)

  const [autoScroll, setAutoScroll] = useState<boolean>(true)
  const [showScrollBottomBtn, setShowScrollBottomBtn] = useState<boolean>(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // Scroll to bottom smoothly
  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    if (bottomAnchorRef.current) {
      bottomAnchorRef.current.scrollIntoView({ behavior, block: 'end' })
    }
  }, [])

  // Auto-scroll when new events arrive or content streams, unless locked by user
  useEffect(() => {
    if (autoScroll) {
      scrollToBottom('smooth')
    }
  }, [events, isStreaming, autoScroll, scrollToBottom])

  // Track scroll position to detect if user manually scrolled up
  const handleScroll = () => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight

    if (distanceFromBottom > 120) {
      setShowScrollBottomBtn(true)
      if (autoScroll) {
        // Automatically release auto-scroll lock when user scrolls up
        setAutoScroll(false)
      }
    } else {
      setShowScrollBottomBtn(false)
    }
  }

  const handleResumeAutoScroll = () => {
    setAutoScroll(true)
    setShowScrollBottomBtn(false)
    scrollToBottom('smooth')
  }

  const handleCopyMessage = (id: string, text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const renderTimelineEvent = (event: TimelineEvent) => {
    switch (event.type) {
      case 'user_message':
        return (
          <div key={event.id} className="flex items-start justify-end gap-3 max-w-3xl ml-auto">
            <div className="flex flex-col items-end gap-1 max-w-[85%]">
              <div className="bg-primary text-primary-foreground px-4 py-3 rounded-2xl rounded-tr-xs text-xs sm:text-sm leading-relaxed shadow-xs break-words">
                {event.content}
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground pr-1">
                <span>{event.timestamp}</span>
              </div>
            </div>
            <div className="w-8 h-8 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0 mt-0.5">
              <User className="w-4 h-4" />
            </div>
          </div>
        )

      case 'thinking':
        return (
          <div key={event.id} className="w-full max-w-4xl">
            <ThinkingAccordion thinking={event.thinking} />
          </div>
        )

      case 'subagent':
        return (
          <div key={event.id} className="w-full max-w-4xl">
            <SubagentCard
              subagent={event.subagent}
              onViewThread={onViewSubagentThread}
            />
          </div>
        )

      case 'tool':
        return (
          <div key={event.id} className="w-full max-w-4xl">
            <ToolExecutionCard tool={event.tool} />
          </div>
        )

      case 'diff':
        return (
          <div key={event.id} className="w-full max-w-4xl">
            <InlineDiffCard
              patch={event.patch}
              onAccept={onAcceptDiff}
              onDiscard={onDiscardDiff}
            />
          </div>
        )

      case 'terminal':
        return (
          <div key={event.id} className="w-full max-w-4xl">
            <TerminalSnippet terminal={event.terminal} />
          </div>
        )

      case 'approval':
        return (
          <div key={event.id} className="w-full max-w-4xl">
            <ApprovalGateCard
              gate={event.gate}
              onApprove={onApproveGate}
              onReject={onRejectGate}
            />
          </div>
        )

      case 'agent_response':
        return (
          <div key={event.id} className="flex items-start gap-3 max-w-4xl mr-auto group">
            <div className="w-8 h-8 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-500 shrink-0 mt-0.5 shadow-xs">
              <Bot className="w-4 h-4" />
            </div>

            <div className="flex-1 min-w-0">
              <div className="bg-card/70 border border-border/70 backdrop-blur-xs px-4 py-3 rounded-2xl rounded-tl-xs text-xs sm:text-sm text-foreground leading-relaxed shadow-xs">
                <div className="whitespace-pre-wrap break-words">
                  {event.content}
                  {event.isStreaming && (
                    <span className="inline-block w-1.5 h-4 ml-1 bg-violet-500 animate-pulse align-middle" />
                  )}
                </div>

                <div className="mt-2 pt-2 border-t border-border/40 flex items-center justify-between text-[10px] text-muted-foreground">
                  <span>{event.timestamp}</span>

                  <button
                    type="button"
                    onClick={() => handleCopyMessage(event.id, event.content)}
                    className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors p-1"
                  >
                    {copiedId === event.id ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-500" />
                        <span className="text-emerald-500">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div
      className={cn(
        'relative flex flex-col h-full w-full overflow-hidden bg-background/50',
        className
      )}
    >
      {/* Optional Header Slot */}
      {headerSlot && <div className="shrink-0 z-10">{headerSlot}</div>}

      {/* Auto-scroll toggle bar */}
      <div className="shrink-0 flex items-center justify-between px-4 py-1.5 border-b border-border/40 bg-muted/20 text-[11px] text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-violet-500" />
          <span className="font-medium">Antigravity Transparent Stream</span>
          <span className="text-muted-foreground/60">•</span>
          <span>{events.length} stream events</span>
        </div>

        <button
          type="button"
          onClick={() => setAutoScroll(!autoScroll)}
          className={cn(
            'inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium transition-colors cursor-pointer',
            autoScroll
              ? 'bg-violet-500/10 text-violet-500 border border-violet-500/20'
              : 'bg-muted text-muted-foreground hover:text-foreground'
          )}
        >
          {autoScroll ? (
            <>
              <Lock className="w-3 h-3" /> Auto-scroll on
            </>
          ) : (
            <>
              <Unlock className="w-3 h-3" /> Auto-scroll off
            </>
          )}
        </button>
      </div>

      {/* Main Stream Events Container */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 space-y-4 scroll-smooth"
      >
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full min-h-[320px] text-center p-6 space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-linear-to-tr from-violet-600/20 to-indigo-600/20 border border-violet-500/30 flex items-center justify-center text-violet-500 shadow-md">
              <Sparkles className="w-7 h-7" />
            </div>

            <div className="max-w-md space-y-1.5">
              <h3 className="text-base font-semibold text-foreground tracking-tight">
                Codex Transparent Timeline
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Full real-time visibility into AI reasoning steps, tool invocations, subagents, code diffs, terminal outputs, and approval gates.
              </p>
            </div>

            {onSendMessage && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg pt-2">
                {[
                  'Run regression test suite',
                  'Audit recent code diffs',
                  'Inspect subagent tasks',
                  'Plan schema migration'
                ].map((promptText) => (
                  <button
                    key={promptText}
                    type="button"
                    onClick={() => onSendMessage(promptText)}
                    className="text-left p-2.5 rounded-xl border border-border/60 bg-card/60 hover:bg-muted/60 text-xs text-foreground transition-all cursor-pointer hover:border-violet-500/40 text-ellipsis truncate"
                  >
                    👉 {promptText}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          events.map(renderTimelineEvent)
        )}

        <div ref={bottomAnchorRef} className="h-2" />
      </div>

      {/* Floating Scroll to Bottom Button */}
      {showScrollBottomBtn && (
        <button
          type="button"
          onClick={handleResumeAutoScroll}
          className="absolute bottom-24 right-6 z-20 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary text-primary-foreground shadow-lg text-xs font-medium hover:opacity-90 active:scale-95 transition-all cursor-pointer animate-in fade-in slide-in-from-bottom-2"
        >
          <ArrowDown className="w-3.5 h-3.5" />
          <span>Scroll to latest</span>
        </button>
      )}

      {/* Optional Footer Slot */}
      {footerSlot && <div className="shrink-0 z-10">{footerSlot}</div>}

      {/* Bottom Composer */}
      {onSendMessage && (
        <div className="shrink-0 p-3 sm:px-6 bg-linear-to-t from-background via-background/90 to-transparent">
          <ComposerBar
            onSendMessage={onSendMessage}
            onStopStreaming={onStopStreaming}
            isStreaming={isStreaming}
            voiceState={voiceState}
            onToggleVoice={onToggleVoice}
            onAttach={onAttach}
          />
        </div>
      )}
    </div>
  )
}
export default TransparentStream
