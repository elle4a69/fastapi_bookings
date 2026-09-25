import React, { useRef, useEffect, useState, useMemo } from 'react'
import { ArrowDown, MessageSquareCode, Terminal } from 'lucide-react'
import type { Thread, TimelineItem } from '../../types/workbench'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { UserInstructionItem } from './items/UserInstructionItem'
import { AgentMessageItem } from './items/AgentMessageItem'
import { ReasoningSummaryItem } from './items/ReasoningSummaryItem'
import { PlanItem } from './items/PlanItem'
import { CommandExecutionItem } from './items/CommandExecutionItem'
import { FileReadItem } from './items/FileReadItem'
import { FileChangeItem } from './items/FileChangeItem'
import { ToolCallItem } from './items/ToolCallItem'
import { WebResearchItem } from './items/WebResearchItem'
import { TestRunItem } from './items/TestRunItem'
import { ApprovalCard } from './items/ApprovalCard'
import { UserInputFormItem } from './items/UserInputFormItem'
import { SubAgentCard } from './items/SubAgentCard'
import { CompactionNoticeItem } from './items/CompactionNoticeItem'
import { WarningItem } from './items/WarningItem'
import { FailureItem } from './items/FailureItem'
import { InterruptionItem } from './items/InterruptionItem'
import { CompletionSummaryItem } from './items/CompletionSummaryItem'
import { Button } from '../ui/button'

interface TimelineProps {
  thread: Thread | null
}

export const Timeline: React.FC<TimelineProps> = ({ thread }) => {
  const { sendUserMessage } = useWorkbenchStore()
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [showScrollBottom, setShowScrollBottom] = useState(false)
  const [userHasScrolledUp, setUserHasScrolledUp] = useState(false)

  // Flatten all items across turns in chronological order
  const allItems = useMemo(() => {
    if (!thread) return []
    const items: TimelineItem[] = []
    thread.turns.forEach(turn => {
      turn.items.forEach(item => {
        items.push(item)
      })
    })
    return items
  }, [thread])

  // Scroll to bottom helper
  const scrollToBottom = (smooth = true) => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: smooth ? 'smooth' : 'auto'
      })
      setUserHasScrolledUp(false)
      setShowScrollBottom(false)
    }
  }

  // Handle scroll events
  const handleScroll = () => {
    if (!scrollContainerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current
    const distanceToBottom = scrollHeight - scrollTop - clientHeight
    if (distanceToBottom > 120) {
      setUserHasScrolledUp(true)
      setShowScrollBottom(true)
    } else {
      setUserHasScrolledUp(false)
      setShowScrollBottom(false)
    }
  }

  // Auto-scroll on new items unless user is reading history
  useEffect(() => {
    if (!userHasScrolledUp) {
      scrollToBottom(false)
    }
  }, [allItems.length, userHasScrolledUp])

  if (!thread) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[var(--bg-app)]">
        <MessageSquareCode className="w-10 h-10 text-[var(--text-subtle)] stroke-1 mb-3" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Select or Create a Thread</h2>
        <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm">
          Select an engineering thread from the sidebar or press Cmd+K to launch a new investigation.
        </p>
      </div>
    )
  }

  // Empty thread starter screen
  if (allItems.length === 0) {
    const starterChips = [
      'Explore repository and verify invariants',
      'Diagnose race condition in availability service',
      'Generate Alembic schema migration for slot locking',
      'Run focused pytest suite with synthetic fixtures',
      'Audit OpenTelemetry traces in SigNoz preview'
    ]

    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[var(--bg-app)]">
        <div className="w-12 h-12 rounded-2xl bg-[var(--surface-primary)] border border-[var(--border)] flex items-center justify-center mb-3 shadow-xs">
          <Terminal className="w-6 h-6 text-[var(--accent)]" aria-hidden="true" />
        </div>
        <h2 className="text-base font-semibold text-[var(--text-primary)]">{thread.title}</h2>
        <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-md">
          Thread initialized with <strong>{thread.model}</strong> under <strong>{thread.permissionProfile.replace('_', ' ')}</strong> permissions.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-2 mt-6 max-w-lg">
          {starterChips.map((chip, idx) => (
            <button
              key={idx}
              onClick={() => sendUserMessage(chip)}
              aria-label={`Send starter prompt: ${chip}`}
              className="px-3 py-1.5 rounded-full bg-[var(--surface-primary)] hover:bg-[var(--surface-hover)] border border-[var(--border)] text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer text-left shadow-2xs focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
            >
              {chip}
            </button>
          ))}
        </div>
      </div>
    )
  }

  // Render individual timeline item with fallback for unknown types
  const renderItem = (item: TimelineItem) => {
    switch (item.type) {
      case 'user_instruction':
        return <UserInstructionItem key={item.id} item={item} />
      case 'agent_message':
        return <AgentMessageItem key={item.id} item={item} />
      case 'reasoning_summary':
        return <ReasoningSummaryItem key={item.id} item={item} />
      case 'plan':
        return <PlanItem key={item.id} item={item} />
      case 'command_execution':
        return <CommandExecutionItem key={item.id} item={item} />
      case 'file_read':
        return <FileReadItem key={item.id} item={item} />
      case 'file_change':
        return <FileChangeItem key={item.id} item={item} />
      case 'tool_call':
        return <ToolCallItem key={item.id} item={item} />
      case 'web_research':
        return <WebResearchItem key={item.id} item={item} />
      case 'test_run':
        return <TestRunItem key={item.id} item={item} />
      case 'approval_request':
        return <ApprovalCard key={item.id} item={item} />
      case 'user_input_request':
        return <UserInputFormItem key={item.id} item={item} />
      case 'sub_agent_activity':
        return (
          <div key={item.id} className="my-2 max-w-4xl mx-auto">
            <SubAgentCard
              agent={{
                id: item.agentId,
                parentThreadId: thread.id,
                role: item.role,
                objective: item.objective,
                status: item.status,
                model: 'gpt-4o',
                reasoningEffort: 'medium',
                scope: 'workspace_write',
                startedAt: 'Just now',
                elapsedSeconds: 15,
                progressSummary: item.progressSummary,
                resultSummary: item.resultSummary,
                filesChangedCount: item.filesChangedCount,
                testsRunCount: item.testsRunCount
              }}
            />
          </div>
        )
      case 'compaction_notice':
        return <CompactionNoticeItem key={item.id} item={item} />
      case 'warning':
        return <WarningItem key={item.id} item={item} />
      case 'failure':
        return <FailureItem key={item.id} item={item} />
      case 'interruption':
        return <InterruptionItem key={item.id} item={item} />
      case 'completion_summary':
        return <CompletionSummaryItem key={item.id} item={item} />
      default:
        return (
          <div key={(item as any).id} className="my-2 p-3 max-w-4xl mx-auto rounded bg-[var(--surface-secondary)] border border-[var(--border)] text-xs text-[var(--text-subtle)] font-mono">
            Generic Event: {(item as any).type}
          </div>
        )
    }
  }

  return (
    <div className="relative flex-1 flex flex-col h-full overflow-hidden bg-[var(--bg-app)]">
      {/* Scrollable Timeline */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-4 scroll-smooth"
        role="feed"
        aria-label="Thread Conversation and Activity Timeline"
      >
        <div className="max-w-4xl mx-auto w-full pb-6">
          {allItems.map(renderItem)}
        </div>
      </div>

      {/* Floating 'New activity ↓' Chip */}
      {showScrollBottom && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => scrollToBottom(true)}
            aria-label="Scroll down to newest activity"
            className="rounded-full shadow-md text-xs gap-1.5 px-3 py-1 bg-[var(--surface-elevated)] border-[var(--border-strong)] text-[var(--text-primary)] hover:bg-[var(--surface-hover)]"
          >
            <ArrowDown className="w-3.5 h-3.5 text-[var(--accent)] animate-bounce" aria-hidden="true" />
            New activity ↓
          </Button>
        </div>
      )}
    </div>
  )
}
