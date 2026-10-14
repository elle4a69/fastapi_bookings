import React, { useRef, useEffect, useState, useMemo } from 'react'
import { ArrowDown, MessageSquareCode, Terminal } from 'lucide-react'
import type { Thread, TimelineItem } from '../../types/workbench'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'
import { SubagentTabBar } from './SubagentTabBar'
import { LiveActivityPulse } from './LiveActivityPulse'
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
import { getLastUsedCodexModel } from '../../modelCatalog'

interface TimelineProps {
  thread: Thread | null
}

export const Timeline: React.FC<TimelineProps> = ({ thread }) => {
  const { sendUserMessage, state, activeSubAgents } = useWorkbenchStore()
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [showScrollBottom, setShowScrollBottom] = useState(false)
  const [userHasScrolledUp, setUserHasScrolledUp] = useState(false)

  const activeAgentId = state.activeAgentId || 'main'

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

  // Filter items based on active tab: main vs child subagent
  const filteredItems = useMemo(() => {
    if (activeAgentId === 'main') {
      return allItems.filter(item => {
        const itemAgentId = (item as any).agentId
        // Main thread shows items without agentId, or explicitly marked 'main', or subagent activity overview items
        return !itemAgentId || itemAgentId === 'main' || item.type === 'sub_agent_activity'
      })
    } else {
      // Subagent tab shows items belonging to the selected subagent
      return allItems.filter(item => {
        const itemAgentId = (item as any).agentId
        return itemAgentId === activeAgentId || (item.type === 'sub_agent_activity' && (item as any).agentId === activeAgentId)
      })
    }
  }, [allItems, activeAgentId])

  // Lookup subagent if currently focused on a subagent tab
  const selectedSubAgent = useMemo(() => {
    if (activeAgentId === 'main') return null
    return activeSubAgents.find(sa => sa.id === activeAgentId) || state.subAgents.find(sa => sa.id === activeAgentId) || null
  }, [activeAgentId, activeSubAgents, state.subAgents])

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

  // Auto-scroll on new items or streaming updates unless user is reading history
  useEffect(() => {
    if (!userHasScrolledUp) {
      scrollToBottom(false)
    }
  }, [allItems.length, state.isStreaming, state.currentActionText, userHasScrolledUp])

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

  const starterChips = [
    'Explore repository and verify invariants',
    'Diagnose race condition in availability service',
    'Generate Alembic schema migration for slot locking',
    'Run focused pytest suite with synthetic fixtures',
    'Audit OpenTelemetry traces in SigNoz preview'
  ]

  // Render individual timeline item with fallback for unknown types
  const renderItem = (item: TimelineItem, index: number) => {
    const itemKey = `${item.id || 'item'}_${index}`
    switch (item.type) {
      case 'user_instruction':
        return <UserInstructionItem key={itemKey} item={item} />
      case 'agent_message':
        return <AgentMessageItem key={itemKey} item={item} />
      case 'reasoning_summary':
        return <ReasoningSummaryItem key={itemKey} item={item} />
      case 'plan':
        return <PlanItem key={itemKey} item={item} />
      case 'command_execution':
        return <CommandExecutionItem key={itemKey} item={item} />
      case 'file_read':
        return <FileReadItem key={itemKey} item={item} />
      case 'file_change':
        return <FileChangeItem key={itemKey} item={item} />
      case 'tool_call':
        return <ToolCallItem key={itemKey} item={item} />
      case 'web_research':
        return <WebResearchItem key={itemKey} item={item} />
      case 'test_run':
        return <TestRunItem key={itemKey} item={item} />
      case 'approval_request':
        return <ApprovalCard key={itemKey} item={item} />
      case 'user_input_request':
        return <UserInputFormItem key={itemKey} item={item} />
      case 'sub_agent_activity':
        return (
          <div key={itemKey} className="my-2 max-w-4xl mx-auto">
            <SubAgentCard
              agent={{
                id: item.agentId,
                parentThreadId: thread.id,
                role: item.role,
                objective: item.objective,
                status: item.status,
                model: getLastUsedCodexModel(),
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
        return <CompactionNoticeItem key={itemKey} item={item} />
      case 'warning':
        return <WarningItem key={itemKey} item={item} />
      case 'failure':
        return <FailureItem key={itemKey} item={item} />
      case 'interruption':
        return <InterruptionItem key={itemKey} item={item} />
      case 'completion_summary':
        return <CompletionSummaryItem key={itemKey} item={item} />
      default:
        return (
          <div key={itemKey} className="my-2 p-3 max-w-4xl mx-auto rounded bg-[var(--surface-secondary)] border border-[var(--border)] text-xs text-[var(--text-subtle)] font-mono">
            Generic Event: {(item as any).type}
          </div>
        )
    }
  }

  return (
    <div className="relative flex-1 flex flex-col h-full w-full max-w-full overflow-hidden bg-[var(--bg-app)]">
      {/* Subagent Tab Strip at Top of Timeline */}
      <SubagentTabBar />

      {/* Main Content Area */}
      {allItems.length === 0 && activeAgentId === 'main' ? (
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[var(--bg-app)]">
          <div className="w-12 h-12 rounded-2xl bg-[var(--surface-primary)] border border-[var(--border)] flex items-center justify-center mb-3 shadow-xs">
            <Terminal className="w-6 h-6 text-[var(--accent)]" aria-hidden="true" />
          </div>
          <h2 className="text-base font-semibold text-[var(--text-primary)]">{thread.title}</h2>
          <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-md">
            Thread initialized with <strong>{thread.model}</strong> under <strong>{(thread.permissionProfile || 'workspace_write').replace('_', ' ')}</strong> permissions.
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
      ) : (
        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto px-2 sm:px-4 py-3 sm:py-4 scroll-smooth w-full max-w-full overflow-x-hidden"
          role="feed"
          aria-label={activeAgentId === 'main' ? 'Main Orchestrator Conversation and Activity Timeline' : `Subagent ${activeAgentId} Activity Timeline`}
        >
          <div className="max-w-4xl mx-auto w-full pb-6 space-y-3 min-w-0 overflow-x-hidden">
            {/* If focused on a subagent tab and its card is not already an item, render card at top */}
            {selectedSubAgent && !filteredItems.some(i => i.type === 'sub_agent_activity' && (i as any).agentId === selectedSubAgent.id) && (
              <div className="my-2 max-w-4xl mx-auto">
                <SubAgentCard agent={selectedSubAgent} />
              </div>
            )}

            {filteredItems.map((item, index) => renderItem(item, index))}

            {activeAgentId !== 'main' && filteredItems.length === 0 && !selectedSubAgent && (
              <div className="text-center py-8 text-xs text-[var(--text-secondary)]">
                No activity recorded for this subagent yet.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Floating 'New activity ↓' Chip */}
      {showScrollBottom && (
        <div className="absolute bottom-14 left-1/2 -translate-x-1/2 z-20">
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

      {/* Live Activity Pulse Beacon mounted at bottom above Composer */}
      <LiveActivityPulse />
    </div>
  )
}
