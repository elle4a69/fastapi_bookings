import { useState, useEffect } from 'react'
import type {
  Project,
  Thread,
  SubAgent,
  DiffFile,
  TelemetryIncident,
  ReasoningEffort,
  PermissionProfile,
  TimelineItem,
  SubAgentActivityItem,
  SSEEventEnvelope,
  WorkspaceBoundary,
  TelemetrySettings
} from '../types/workbench'
import {
  FIXTURE_PROJECTS,
  FIXTURE_THREADS,
  FIXTURE_SUBAGENTS,
  FIXTURE_DIFFS,
  FIXTURE_INCIDENTS
} from '../test/fixtures/realisticFixtures'
import { codexApi } from '../api/codexApi'

export type InspectorTab = 'changes' | 'files' | 'subagents' | 'tests' | 'terminal' | 'telemetry' | 'details'
export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected' | 'reconnecting'
export type AppMode = 'live' | 'demo' | 'unavailable'

// -------------------------------------------------------------
// Safe Environment Helpers (Node/Browser/SSR)
// -------------------------------------------------------------

export function getSafeLocalStorage(key: string, defaultValue: string): string {
  try {
    if (typeof localStorage !== 'undefined') {
      return localStorage.getItem(key) || defaultValue
    }
  } catch {
    // Ignore storage access errors
  }
  return defaultValue
}

export function setSafeLocalStorage(key: string, value: string): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, value)
    }
  } catch {
    // Ignore storage access errors
  }
}

// -------------------------------------------------------------
// Separated State Definitions
// -------------------------------------------------------------

export interface ServerState {
  projects: Project[]
  threads: Thread[]
  subAgents: SubAgent[]
  diffFiles: DiffFile[]
  telemetryIncidents: TelemetryIncident[]
  boundaries: WorkspaceBoundary[]
  telemetrySettings: TelemetrySettings | null
  // Per-thread streaming and race-condition tracking (CCC-003, CCC-004)
  streamingTurnIdByThread: Record<string, string | null>
  processedEventIdsByThread: Record<string, string[]>
  interruptedTurnIdsByThread: Record<string, string[]>
  lastSequenceByThread: Record<string, number>
}

export interface LocalUIState {
  theme: 'dark' | 'light'
  appMode: AppMode
  activeProjectId: string
  activeThreadId: string | null
  activeAgentId: string
  currentActionText?: string
  turnElapsedSeconds: number
  isSidebarOpen: boolean
  isInspectorOpen: boolean
  activeInspectorTab: InspectorTab
  isDiffStudioOpen: boolean
  selectedDiffFileIndex: number
  isCommandPaletteOpen: boolean
  sidebarWidth: number
  inspectorWidth: number
  threadSearchQuery: string
  threadStatusFilter: string
  connectionStatus: ConnectionStatus
  lastConnectedTime: string
  liveAnnouncements: string[]
}

export interface WorkbenchState extends ServerState, LocalUIState {
  isStreaming: boolean // Dynamically computed for activeThreadId
}

const storedAppMode = (getSafeLocalStorage('codex_app_mode', 'live') as AppMode) || 'live'
const isDemo = storedAppMode === 'demo'

export const initialServerState: ServerState = {
  projects: isDemo ? FIXTURE_PROJECTS : [],
  threads: isDemo ? FIXTURE_THREADS : [],
  subAgents: isDemo ? FIXTURE_SUBAGENTS : [],
  diffFiles: isDemo ? FIXTURE_DIFFS : [],
  telemetryIncidents: isDemo ? FIXTURE_INCIDENTS : [],
  boundaries: isDemo ? [
    { id: 'bound_fastapi', path: 'F:\\Projects\\fastapi_bookings', name: 'FastAPI Bookings', is_default: true },
    { id: 'bound_kok', path: 'E:\\Projects\\King of Kings', name: 'King of Kings', is_default: false },
    { id: 'bound_codex', path: 'F:\\Projects\\fastapi_bookings\\codex-control-centre', name: 'Codex Control Centre', is_default: false }
  ] : [],
  telemetrySettings: isDemo ? {
    signoz_url: 'http://localhost:3301',
    otlp_endpoint: 'http://localhost:4318',
    enabled: true,
    connected: true,
    status: 'Connected',
    latency_ms: 1.2
  } : null,
  streamingTurnIdByThread: {},
  processedEventIdsByThread: {},
  interruptedTurnIdsByThread: {},
  lastSequenceByThread: {}
}

export const initialLocalUIState: LocalUIState = {
  theme: (getSafeLocalStorage('codex_theme', 'dark') as 'dark' | 'light') || 'dark',
  appMode: storedAppMode,
  activeProjectId: isDemo ? 'proj_fastapi_bookings' : '',
  activeThreadId: isDemo ? 'th_active_stream' : null,
  activeAgentId: 'main',
  currentActionText: undefined,
  turnElapsedSeconds: 0,
  isSidebarOpen: true,
  isInspectorOpen: true,
  activeInspectorTab: 'changes',
  isDiffStudioOpen: false,
  selectedDiffFileIndex: 0,
  isCommandPaletteOpen: false,
  sidebarWidth: 300,
  inspectorWidth: 380,
  threadSearchQuery: '',
  threadStatusFilter: 'all',
  connectionStatus: isDemo ? 'connected' : 'disconnected',
  lastConnectedTime: new Date().toLocaleTimeString(),
  liveAnnouncements: []
}

function computeIsStreaming(serverState: ServerState, activeThreadId: string | null): boolean {
  if (!activeThreadId) return false
  return Boolean(serverState.streamingTurnIdByThread[activeThreadId])
}

// -------------------------------------------------------------
// Idempotent Event Reducer (CCC-001, CCC-003, CCC-004, CCC-021)
// -------------------------------------------------------------

export function reduceSSEEvent(prevState: WorkbenchState, event: SSEEventEnvelope): WorkbenchState {
  const threadId = event.thread_id
  if (!threadId) return prevState

  // 1. Deduplication Gate: If event has already been processed for this thread, ignore replay
  const processedList = prevState.processedEventIdsByThread[threadId] || []
  if (event.id && processedList.includes(event.id)) {
    return prevState
  }

  const updatedProcessedList = event.id ? [...processedList, event.id] : processedList
  const currentSeq = prevState.lastSequenceByThread[threadId] || 0
  const updatedSeq = event.sequence > currentSeq ? event.sequence : currentSeq

  let nextThreads = [...prevState.threads]
  let nextStreamingTurns = { ...prevState.streamingTurnIdByThread }
  let nextInterruptedTurns = { ...prevState.interruptedTurnIdsByThread }
  let nextSubAgents = [...prevState.subAgents]
  let currentActionText = prevState.currentActionText
  let turnElapsedSeconds = prevState.turnElapsedSeconds

  // Ensure target thread exists
  let targetThreadIndex = nextThreads.findIndex(t => t.id === threadId)
  if (targetThreadIndex === -1) {
    const newThread: Thread = {
      id: threadId,
      projectId: event.project_id || prevState.activeProjectId || 'default',
      title: 'Active Thread',
      module: 'General Engineering',
      status: 'active',
      branch: 'main',
      worktree: 'wt-main',
      model: 'gpt-4o',
      reasoningEffort: 'medium',
      permissionProfile: 'workspace_write',
      contextCompactionState: 'healthy',
      subAgentCount: 0,
      approvalCount: 0,
      createdAt: new Date().toLocaleTimeString(),
      updatedAt: new Date().toLocaleTimeString(),
      turns: []
    }
    nextThreads.push(newThread)
    targetThreadIndex = nextThreads.length - 1
  }

  const targetThread = { ...nextThreads[targetThreadIndex] }
  const payload = event.payload || {}
  const eventTime = event.occurred_at || new Date().toLocaleTimeString()

  switch (event.type) {
    case 'turn_started':
    case 'turn/start': {
      const turnId = String(payload.turn_id || payload.turnId || `turn_${Date.now()}`)
      nextStreamingTurns[threadId] = turnId
      currentActionText = payload.prompt ? `Starting: ${String(payload.prompt).slice(0, 40)}...` : 'Thinking...'
      turnElapsedSeconds = 0

      // Remove turn from interrupted list if restarted
      if (nextInterruptedTurns[threadId]) {
        nextInterruptedTurns[threadId] = nextInterruptedTurns[threadId].filter(id => id !== turnId)
      }

      const existingTurn = targetThread.turns.find(t => t.id === turnId)
      if (!existingTurn) {
        // Reconcile and adopt any in-progress optimistic turn created before backend responded
        const optimisticTurn = targetThread.turns.find(t => t.status === 'in_progress' && (t.id.startsWith('turn_') || isNaN(Number(t.id))))
        if (optimisticTurn) {
          targetThread.turns = targetThread.turns.map(t =>
            t.id === optimisticTurn.id
              ? {
                  ...t,
                  id: turnId,
                  items: t.items.map(i => ({ ...i, turnId }))
                }
              : t
          )
        } else {
          const initialItems: TimelineItem[] = []
          if (payload.prompt) {
            initialItems.push({
              id: `usr_${Date.now()}`,
              turnId,
              type: 'user_instruction',
              timestamp: eventTime,
              content: payload.prompt,
              authorName: 'Operator'
            })
          }
          targetThread.turns = [
            ...targetThread.turns,
            {
              id: turnId,
              threadId,
              turnNumber: targetThread.turns.length + 1,
              status: 'in_progress',
              startedAt: eventTime,
              items: initialItems
            }
          ]
        }
      } else {
        targetThread.turns = targetThread.turns.map(t =>
          t.id === turnId ? { ...t, status: 'in_progress' } : t
        )
      }
      targetThread.status = 'active'
      break
    }

    case 'agent_message': {
      const turnId = String(payload.turn_id || payload.turnId || nextStreamingTurns[threadId] || (targetThread.turns[targetThread.turns.length - 1]?.id ?? ''))
      const itemId = String(payload.item_id || payload.id || `msg_${Date.now()}`)
      const isStreaming = payload.is_streaming ?? false
      const incomingChunk = payload.chunk || payload.delta || payload.text || payload.content || ''
      currentActionText = 'Generating response...'

      targetThread.turns = targetThread.turns.map(turn => {
        if (turn.id !== turnId && turn.status !== 'in_progress') return turn

        // Filter out initial temporary streaming placeholders once real message arrives
        const baseItems = turn.items.filter(i => !i.id.startsWith('stream_'))
        const existingItemIndex = baseItems.findIndex(i => i.id === itemId)

        if (existingItemIndex >= 0) {
          const prev = baseItems[existingItemIndex]
          const existingText = ('content' in prev ? (prev.content as string) : '') || ''
          const nextText = isStreaming
            ? (payload.content && payload.content !== incomingChunk ? payload.content : (existingText + incomingChunk))
            : (payload.content || payload.text || existingText || incomingChunk)

          const updatedItems = [...baseItems]
          updatedItems[existingItemIndex] = {
            ...prev,
            type: 'agent_message',
            content: nextText,
            isStreaming,
            agentId: payload.agent_id || payload.agentId || prev.agentId
          }
          return { ...turn, id: turnId || turn.id, items: updatedItems }
        }

        return {
          ...turn,
          id: turnId || turn.id,
          items: [
            ...baseItems,
            {
              id: itemId,
              turnId: turnId || turn.id,
              type: 'agent_message',
              timestamp: eventTime,
              content: incomingChunk,
              isStreaming,
              agentId: payload.agent_id || payload.agentId
            }
          ]
        }
      })
      break
    }

    case 'reasoning':
    case 'reasoning_summary': {
      const turnId = String(payload.turn_id || payload.turnId || nextStreamingTurns[threadId] || (targetThread.turns[targetThread.turns.length - 1]?.id ?? ''))
      const itemId = String(payload.item_id || payload.id || `reason_${Date.now()}`)
      const isStreaming = payload.is_streaming ?? (Boolean(nextStreamingTurns[threadId]))
      const incomingChunk = payload.chunk || payload.delta || ''
      currentActionText = payload.summary ? `Thinking: ${payload.summary}` : 'Thinking...'

      targetThread.turns = targetThread.turns.map(turn => {
        if (turn.id !== turnId && turn.status !== 'in_progress') return turn
        const existingItemIndex = turn.items.findIndex(i => i.id === itemId)
        const prev = existingItemIndex >= 0 ? (turn.items[existingItemIndex] as any) : null
        const prevTrace = prev?.rawTrace || ''
        const nextTrace = payload.raw_trace || payload.reasoning || (incomingChunk ? prevTrace + incomingChunk : (prevTrace || payload.summary || ''))
        const nextSummary = payload.summary || (nextTrace ? (nextTrace.slice(0, 100) + (nextTrace.length > 100 ? '...' : '')) : 'Analyzing repository architecture and constraints...')

        const item: TimelineItem = {
          id: itemId,
          turnId: turn.id,
          type: 'reasoning_summary',
          timestamp: eventTime,
          summary: nextSummary,
          rawTrace: nextTrace,
          elapsedMs: payload.elapsed_ms || payload.elapsedMs || (prev?.elapsedMs ? prev.elapsedMs + 200 : 1200),
          isStreaming,
          agentId: payload.agent_id || payload.agentId || prev?.agentId
        }
        if (existingItemIndex >= 0) {
          const updated = [...turn.items]
          updated[existingItemIndex] = item
          return { ...turn, items: updated }
        }
        return { ...turn, items: [...turn.items, item] }
      })
      break
    }

    case 'plan': {
      const turnId = String(payload.turn_id || payload.turnId || nextStreamingTurns[threadId] || (targetThread.turns[targetThread.turns.length - 1]?.id ?? ''))
      const itemId = String(payload.item_id || payload.id || `plan_${Date.now()}`)

      targetThread.turns = targetThread.turns.map(turn => {
        if (turn.id !== turnId) return turn
        const existingItemIndex = turn.items.findIndex(i => i.id === itemId)
        const item: TimelineItem = {
          id: itemId,
          turnId,
          type: 'plan',
          timestamp: eventTime,
          title: payload.title || 'Execution Plan',
          tasks: payload.tasks || [],
          agentId: payload.agent_id || payload.agentId
        }
        if (existingItemIndex >= 0) {
          const updated = [...turn.items]
          updated[existingItemIndex] = item
          return { ...turn, items: updated }
        }
        return { ...turn, items: [...turn.items, item] }
      })
      break
    }

    case 'command':
    case 'command_execution': {
      const turnId = String(payload.turn_id || payload.turnId || nextStreamingTurns[threadId] || (targetThread.turns[targetThread.turns.length - 1]?.id ?? ''))
      const itemId = String(payload.item_id || payload.id || `cmd_${Date.now()}`)
      currentActionText = payload.command ? `Running command: ${payload.command}` : 'Running command...'

      targetThread.turns = targetThread.turns.map(turn => {
        if (turn.id !== turnId) return turn
        const existingItemIndex = turn.items.findIndex(i => i.id === itemId)
        const item: TimelineItem = {
          id: itemId,
          turnId,
          type: 'command_execution',
          timestamp: eventTime,
          command: payload.command || '',
          summary: payload.summary || '',
          workingDirectory: payload.workingDirectory || payload.working_directory || '/',
          status: payload.status || 'completed',
          durationMs: payload.durationMs || payload.duration_ms || 350,
          stdout: payload.stdout || payload.chunk || '',
          stderr: payload.stderr,
          exitCode: payload.exitCode ?? payload.exit_code ?? 0,
          lineCount: payload.lineCount || (payload.stdout ? payload.stdout.split('\n').length : (payload.chunk ? payload.chunk.split('\n').length : 0)),
          processId: payload.processId || payload.process_id,
          agentId: payload.agent_id || payload.agentId
        }
        if (existingItemIndex >= 0) {
          const updated = [...turn.items]
          updated[existingItemIndex] = item
          return { ...turn, items: updated }
        }
        return { ...turn, items: [...turn.items, item] }
      })
      break
    }

    case 'file_change': {
      const turnId = String(payload.turn_id || payload.turnId || nextStreamingTurns[threadId] || (targetThread.turns[targetThread.turns.length - 1]?.id ?? ''))
      const itemId = String(payload.item_id || payload.id || `file_${Date.now()}`)
      currentActionText = payload.summary ? `Updating files: ${payload.summary}` : 'Updating files...'

      targetThread.turns = targetThread.turns.map(turn => {
        if (turn.id !== turnId) return turn
        const existingItemIndex = turn.items.findIndex(i => i.id === itemId)
        const item: TimelineItem = {
          id: itemId,
          turnId,
          type: 'file_change',
          timestamp: eventTime,
          summary: payload.summary || 'Applied source code updates',
          files: payload.files || [],
          totalAdditions: payload.totalAdditions ?? payload.total_additions ?? 0,
          totalDeletions: payload.totalDeletions ?? payload.total_deletions ?? 0,
          agentId: payload.agent_id || payload.agentId
        }
        if (existingItemIndex >= 0) {
          const updated = [...turn.items]
          updated[existingItemIndex] = item
          return { ...turn, items: updated }
        }
        return { ...turn, items: [...turn.items, item] }
      })
      break
    }

    case 'tool_call': {
      const turnId = String(payload.turn_id || payload.turnId || nextStreamingTurns[threadId] || (targetThread.turns[targetThread.turns.length - 1]?.id ?? ''))
      const itemId = String(payload.item_id || payload.id || `tool_${Date.now()}`)
      const toolName = payload.tool_name || payload.toolName || 'tool'
      currentActionText = `Executing tool: ${toolName}`

      targetThread.turns = targetThread.turns.map(turn => {
        if (turn.id !== turnId) return turn
        const existingItemIndex = turn.items.findIndex(i => i.id === itemId)
        const item: TimelineItem = {
          id: itemId,
          turnId,
          type: 'tool_call',
          timestamp: eventTime,
          serverName: payload.server_name || payload.serverName || 'system',
          toolName,
          args: payload.args || {},
          resultSummary: payload.result_summary || payload.resultSummary || 'Tool execution completed',
          status: payload.status || 'success',
          durationMs: payload.duration_ms || payload.durationMs || 150,
          agentId: payload.agent_id || payload.agentId
        }
        if (existingItemIndex >= 0) {
          const updated = [...turn.items]
          updated[existingItemIndex] = item
          return { ...turn, items: updated }
        }
        return { ...turn, items: [...turn.items, item] }
      })
      break
    }

    case 'approval_requested':
    case 'approval_created': {
      const turnId = String(payload.turn_id || payload.turnId || nextStreamingTurns[threadId] || (targetThread.turns[targetThread.turns.length - 1]?.id ?? 'turn_0'))
      const approvalId = String(payload.approval_id || payload.approvalId || payload.id || `appr_${Date.now()}`)

      let alreadyExists = false
      targetThread.turns.forEach(t => {
        if (t.items.some(i => i.type === 'approval_request' && i.approvalId === approvalId)) {
          alreadyExists = true
        }
      })

      if (!alreadyExists) {
        const approvalItem: TimelineItem = {
          id: `item_${approvalId}`,
          turnId,
          type: 'approval_request',
          timestamp: eventTime,
          approvalId,
          category: payload.category || 'command',
          title: payload.title || payload.command || 'Approval Request',
          consequence: payload.consequence || 'Requires operator authorization',
          command: payload.command,
          targetPath: payload.target_path || payload.targetPath,
          workingDirectory: payload.working_directory || payload.workingDirectory,
          reason: payload.reason || 'Safety policy check',
          risk: payload.risk || payload.risk_level || 'medium',
          status: 'pending',
          scope: 'once'
        }

        if (targetThread.turns.length === 0) {
          targetThread.turns = [{
            id: turnId,
            threadId,
            turnNumber: 1,
            status: 'in_progress',
            startedAt: eventTime,
            items: [approvalItem]
          }]
        } else {
          const lastTurn = targetThread.turns[targetThread.turns.length - 1]
          targetThread.turns = targetThread.turns.map(t =>
            t.id === lastTurn.id ? { ...t, items: [...t.items, approvalItem] } : t
          )
        }

        targetThread.approvalCount = (targetThread.approvalCount || 0) + 1
        targetThread.status = 'needs_approval'
      }
      break
    }

    case 'approval_resolved': {
      const approvalId = String(payload.approval_id || payload.approvalId || payload.id || '')
      const approved = payload.approved !== undefined ? Boolean(payload.approved) : payload.status === 'approved'
      const scope = payload.scope || 'once'

      let mutated = false
      targetThread.turns = targetThread.turns.map(turn => ({
        ...turn,
        items: turn.items.map(item => {
          if (item.type === 'approval_request' && item.approvalId === approvalId) {
            if (item.status === 'pending') {
              mutated = true
            }
            return {
              ...item,
              status: approved ? 'approved' : 'declined',
              scope
            }
          }
          return item
        })
      }))

      if (mutated) {
        targetThread.approvalCount = Math.max(0, (targetThread.approvalCount || 0) - 1)
        if (targetThread.approvalCount === 0 && targetThread.status === 'needs_approval') {
          targetThread.status = 'active'
        }
      }
      break
    }

    case 'compaction_notice':
    case 'context_compacted': {
      const turnId = String(payload.turn_id || payload.turnId || (targetThread.turns[0]?.id ?? 'turn_0'))
      const compactionNotice: TimelineItem = {
        id: String(payload.id || `comp_${Date.now()}`),
        turnId,
        type: 'compaction_notice',
        timestamp: eventTime,
        explanation: payload.explanation || 'Codex condensed earlier conversation history to preserve room for continued work.',
        tokensSaved: payload.tokens_saved ?? payload.tokensSaved ?? 0,
        originalTurnCount: payload.original_turn_count ?? payload.originalTurnCount ?? targetThread.turns.length
      }

      targetThread.contextCompactionState = 'compacted'
      if (targetThread.turns.length > 0) {
        targetThread.turns = targetThread.turns.map((turn, idx) =>
          idx === 0 ? { ...turn, items: [compactionNotice, ...turn.items] } : turn
        )
      } else {
        targetThread.turns = [{
          id: turnId,
          threadId,
          turnNumber: 1,
          status: 'completed',
          startedAt: eventTime,
          items: [compactionNotice]
        }]
      }
      break
    }

    case 'turn_completed':
    case 'turn/complete': {
      const turnId = String(payload.turn_id || payload.turnId || nextStreamingTurns[threadId] || '')
      const isInterrupted = (nextInterruptedTurns[threadId] || []).includes(turnId)
      const isFailed = payload.status === 'failed' || Boolean(payload.error)

      // CCC-003: Stale completion event must NOT overwrite an interrupted or stopped turn
      if (!isInterrupted) {
        targetThread.turns = targetThread.turns.map(turn => {
          if (turnId && turn.id !== turnId && turn.status !== 'in_progress') return turn
          return {
            ...turn,
            status: isFailed ? 'failed' : 'completed',
            completedAt: eventTime,
            items: turn.items.map(i => ({ ...i, isStreaming: false }))
          }
        })

        if (isFailed) {
          const failSummary = payload.error || payload.summary || payload.details || 'Turn failed during execution'
          targetThread.status = 'failed'
          targetThread.turns = targetThread.turns.map(turn => {
            if (turnId && turn.id !== turnId && turn.status !== 'failed') return turn
            const hasFailureItem = turn.items.some(i => i.type === 'failure')
            if (hasFailureItem) return turn
            const failureItem: TimelineItem = {
              id: `fail_${Date.now()}_${turn.id}_${Math.random().toString(36).slice(2, 6)}`,
              turnId: turn.id,
              type: 'failure',
              timestamp: eventTime,
              errorCategory: payload.error_category || 'internal',
              summary: failSummary,
              details: payload.details || payload.error,
              canRetry: payload.can_retry ?? true,
              suggestedAction: 'retry'
            }
            return {
              ...turn,
              items: [...turn.items, failureItem]
            }
          })
        } else if (payload.summary) {
          const summaryItem: TimelineItem = {
            id: `summary_${Date.now()}_${turnId}`,
            turnId: turnId || 'turn_0',
            type: 'completion_summary',
            timestamp: eventTime,
            outcome: payload.outcome || 'success',
            changedFilesCount: payload.changed_files_count ?? 1,
            testsPassedCount: payload.tests_passed_count ?? 1,
            durationSeconds: payload.duration_seconds ?? 4,
            summary: payload.summary
          }
          targetThread.turns = targetThread.turns.map(t =>
            (t.id === turnId || t.status === 'completed') ? { ...t, items: [...t.items, summaryItem] } : t
          )
        }
      }

      // Turn finished or resolved
      nextStreamingTurns[threadId] = null
      currentActionText = undefined
      turnElapsedSeconds = 0
      break
    }

    case 'turn_interrupted':
    case 'turn/interrupt': {
      const turnId = String(payload.turn_id || payload.turnId || nextStreamingTurns[threadId] || '')

      if (turnId) {
        const interruptedList = nextInterruptedTurns[threadId] || []
        if (!interruptedList.includes(turnId)) {
          nextInterruptedTurns[threadId] = [...interruptedList, turnId]
        }
      }

      targetThread.status = 'interrupted'
      targetThread.turns = targetThread.turns.map(turn => {
        if (turnId && turn.id !== turnId && turn.status !== 'in_progress') return turn
        const hasInterruptItem = turn.items.some(i => i.type === 'interruption')
        const interruptItem: TimelineItem = {
          id: `int_${Date.now()}_${turn.id}_${Math.random().toString(36).slice(2, 6)}`,
          turnId: turn.id,
          type: 'interruption',
          timestamp: eventTime,
          reason: payload.reason || 'Turn manually interrupted by operator.',
          interruptedBy: payload.interrupted_by || 'Operator'
        }
        return {
          ...turn,
          status: 'interrupted',
          items: hasInterruptItem
            ? turn.items.map(i => ({ ...i, isStreaming: false }))
            : [...turn.items.map(i => ({ ...i, isStreaming: false })), interruptItem]
        }
      })
      nextStreamingTurns[threadId] = null
      currentActionText = undefined
      turnElapsedSeconds = 0
      break
    }

    case 'turn_failed': {
      const turnId = String(payload.turn_id || payload.turnId || nextStreamingTurns[threadId] || '')
      targetThread.status = 'failed'
      targetThread.turns = targetThread.turns.map(turn => {
        if (turnId && turn.id !== turnId && turn.status !== 'in_progress') return turn
        const hasFailureItem = turn.items.some(i => i.type === 'failure')
        const failureItem: TimelineItem = {
          id: `fail_${Date.now()}_${turn.id}_${Math.random().toString(36).slice(2, 6)}`,
          turnId: turn.id,
          type: 'failure',
          timestamp: eventTime,
          errorCategory: payload.error_category || 'internal',
          summary: payload.summary || payload.error || 'Task failed during execution',
          details: payload.details || payload.error,
          canRetry: payload.can_retry ?? true,
          suggestedAction: 'retry'
        }
        return {
          ...turn,
          status: 'failed',
          items: hasFailureItem
            ? turn.items.map(i => ({ ...i, isStreaming: false }))
            : [...turn.items.map(i => ({ ...i, isStreaming: false })), failureItem]
        }
      })
      nextStreamingTurns[threadId] = null
      currentActionText = undefined
      turnElapsedSeconds = 0
      break
    }

    case 'subagent_started': {
      const agentId = String(payload.agent_id || payload.agentId || payload.id || `sa_${Date.now()}`)
      const existingIdx = nextSubAgents.findIndex(sa => sa.id === agentId)
      const role = payload.role || payload.name || 'Subagent Worker'
      const progressSummary = payload.progress_summary || payload.current_action || 'Subagent started'
      currentActionText = `Subagent ${role}: Starting...`

      const subAgentData: SubAgent = {
        id: agentId,
        parentThreadId: threadId,
        role,
        objective: payload.objective || payload.goal || 'Assist engineering workflow',
        status: (payload.status as any) || 'running',
        model: payload.model || 'gpt-4o',
        reasoningEffort: payload.reasoning_effort || payload.reasoningEffort || 'medium',
        scope: payload.scope || 'workspace_write',
        branch: payload.branch,
        startedAt: payload.started_at || eventTime,
        elapsedSeconds: payload.elapsed_seconds ?? payload.elapsedSeconds ?? 0,
        progressSummary,
        resultSummary: payload.result_summary,
        filesChangedCount: payload.files_changed_count ?? payload.filesChangedCount ?? 0,
        testsRunCount: payload.tests_run_count ?? payload.testsRunCount ?? 0
      }
      if (existingIdx >= 0) {
        nextSubAgents[existingIdx] = { ...nextSubAgents[existingIdx], ...subAgentData }
      } else {
        nextSubAgents.push(subAgentData)
      }
      targetThread.subAgentCount = nextSubAgents.filter(sa => sa.parentThreadId === threadId).length

      const turnId = String(payload.turn_id || payload.turnId || nextStreamingTurns[threadId] || (targetThread.turns[targetThread.turns.length - 1]?.id ?? 'turn_0'))
      const subAgentItem: TimelineItem = {
        id: `sa_item_${agentId}`,
        turnId,
        type: 'sub_agent_activity',
        timestamp: eventTime,
        agentId,
        role: subAgentData.role,
        objective: subAgentData.objective,
        status: subAgentData.status,
        progressSummary: subAgentData.progressSummary,
        resultSummary: subAgentData.resultSummary,
        filesChangedCount: subAgentData.filesChangedCount,
        testsRunCount: subAgentData.testsRunCount
      }
      targetThread.turns = targetThread.turns.map(t => {
        if (t.id !== turnId && t.status !== 'in_progress') return t
        const existingItemIdx = t.items.findIndex(i => i.id === subAgentItem.id || (i.type === 'sub_agent_activity' && (i as any).agentId === agentId))
        if (existingItemIdx >= 0) {
          const updated = [...t.items]
          updated[existingItemIdx] = subAgentItem
          return { ...t, items: updated }
        }
        return { ...t, items: [...t.items, subAgentItem] }
      })
      break
    }

    case 'subagent_progress': {
      const agentId = String(payload.agent_id || payload.agentId || payload.id || '')
      const existingIdx = nextSubAgents.findIndex(sa => sa.id === agentId)
      const existing = existingIdx >= 0 ? nextSubAgents[existingIdx] : null
      const role = payload.role || payload.name || existing?.role || 'Subagent Worker'
      const updatedStatus = (payload.status as any) || existing?.status || 'running'
      const updatedProgress = payload.progress_summary || payload.current_action || payload.summary || existing?.progressSummary || 'Executing subagent tasks'
      currentActionText = `Subagent ${role}: ${updatedProgress}`

      const subAgentData: SubAgent = {
        id: agentId || existing?.id || `sa_${Date.now()}`,
        parentThreadId: threadId,
        role,
        objective: payload.objective || existing?.objective || 'Assist engineering workflow',
        status: updatedStatus,
        model: payload.model || existing?.model || 'gpt-4o',
        reasoningEffort: payload.reasoning_effort || payload.reasoningEffort || existing?.reasoningEffort || 'medium',
        scope: payload.scope || existing?.scope || 'workspace_write',
        branch: payload.branch || existing?.branch,
        startedAt: existing?.startedAt || eventTime,
        elapsedSeconds: payload.elapsed_seconds ?? payload.elapsedSeconds ?? ((existing?.elapsedSeconds || 0) + 5),
        progressSummary: updatedProgress,
        resultSummary: payload.result_summary || existing?.resultSummary,
        filesChangedCount: payload.files_changed_count ?? payload.filesChangedCount ?? existing?.filesChangedCount,
        testsRunCount: payload.tests_run_count ?? payload.testsRunCount ?? existing?.testsRunCount
      }
      if (existingIdx >= 0) {
        nextSubAgents[existingIdx] = subAgentData
      } else {
        nextSubAgents.push(subAgentData)
      }
      targetThread.subAgentCount = nextSubAgents.filter(sa => sa.parentThreadId === threadId).length

      targetThread.turns = targetThread.turns.map(t => {
        const itemIdx = t.items.findIndex(i => i.type === 'sub_agent_activity' && (i as any).agentId === agentId)
        if (itemIdx >= 0) {
          const prevItem = t.items[itemIdx] as SubAgentActivityItem
          const updatedItem: TimelineItem = {
            ...prevItem,
            status: updatedStatus,
            progressSummary: updatedProgress,
            resultSummary: subAgentData.resultSummary,
            filesChangedCount: subAgentData.filesChangedCount,
            testsRunCount: subAgentData.testsRunCount
          }
          const updated = [...t.items]
          updated[itemIdx] = updatedItem
          return { ...t, items: updated }
        }
        return t
      })
      break
    }

    case 'subagent_completed': {
      const agentId = String(payload.agent_id || payload.agentId || payload.id || '')
      const existingIdx = nextSubAgents.findIndex(sa => sa.id === agentId)
      const existing = existingIdx >= 0 ? nextSubAgents[existingIdx] : null
      const role = payload.role || payload.name || existing?.role || 'Subagent Worker'
      const isFailed = payload.status === 'failed' || Boolean(payload.error)
      const completedStatus = isFailed ? 'failed' : ((payload.status as any) || 'completed')
      const summaryText = payload.result_summary || payload.summary || payload.progress_summary || (isFailed ? 'Subagent failed execution' : 'Subagent completed execution')
      currentActionText = `Subagent ${role}: ${isFailed ? 'Failed' : 'Completed'}`

      const subAgentData: SubAgent = {
        id: agentId || existing?.id || `sa_${Date.now()}`,
        parentThreadId: threadId,
        role,
        objective: payload.objective || existing?.objective || 'Assist engineering workflow',
        status: completedStatus,
        model: payload.model || existing?.model || 'gpt-4o',
        reasoningEffort: payload.reasoning_effort || payload.reasoningEffort || existing?.reasoningEffort || 'medium',
        scope: payload.scope || existing?.scope || 'workspace_write',
        branch: payload.branch || existing?.branch,
        startedAt: existing?.startedAt || eventTime,
        elapsedSeconds: payload.elapsed_seconds ?? payload.elapsedSeconds ?? existing?.elapsedSeconds ?? 15,
        progressSummary: summaryText,
        resultSummary: summaryText,
        filesChangedCount: payload.files_changed_count ?? payload.filesChangedCount ?? existing?.filesChangedCount,
        testsRunCount: payload.tests_run_count ?? payload.testsRunCount ?? existing?.testsRunCount
      }
      if (existingIdx >= 0) {
        nextSubAgents[existingIdx] = subAgentData
      } else {
        nextSubAgents.push(subAgentData)
      }
      targetThread.subAgentCount = nextSubAgents.filter(sa => sa.parentThreadId === threadId).length

      targetThread.turns = targetThread.turns.map(t => {
        const itemIdx = t.items.findIndex(i => i.type === 'sub_agent_activity' && (i as any).agentId === agentId)
        if (itemIdx >= 0) {
          const prevItem = t.items[itemIdx] as SubAgentActivityItem
          const updatedItem: TimelineItem = {
            ...prevItem,
            status: completedStatus,
            progressSummary: summaryText,
            resultSummary: summaryText,
            filesChangedCount: subAgentData.filesChangedCount,
            testsRunCount: subAgentData.testsRunCount
          }
          const updated = [...t.items]
          updated[itemIdx] = updatedItem
          return { ...t, items: updated }
        }
        return t
      })
      break
    }

    case 'subagent_activity':
    case 'subagent_status': {
      const agentId = payload.id || `sa_${Date.now()}`
      const existingIdx = nextSubAgents.findIndex(sa => sa.id === agentId)
      const subAgentData: SubAgent = {
        id: agentId,
        parentThreadId: threadId,
        role: payload.role || 'Subagent Worker',
        objective: payload.objective || payload.name || 'Assist engineering workflow',
        status: payload.status || 'running',
        model: payload.model || 'gpt-4o',
        reasoningEffort: payload.reasoningEffort || 'medium',
        scope: payload.scope || 'workspace_write',
        startedAt: eventTime,
        elapsedSeconds: payload.elapsed_seconds || 15,
        progressSummary: payload.progress_summary || payload.current_action || 'Executing tasks',
        resultSummary: payload.result_summary,
        filesChangedCount: payload.files_changed_count,
        testsRunCount: payload.tests_run_count
      }
      if (existingIdx >= 0) {
        nextSubAgents[existingIdx] = { ...nextSubAgents[existingIdx], ...subAgentData }
      } else {
        nextSubAgents.push(subAgentData)
      }
      targetThread.subAgentCount = nextSubAgents.filter(sa => sa.parentThreadId === threadId).length
      break
    }
  }

  nextThreads[targetThreadIndex] = targetThread

  const nextServerState: ServerState = {
    ...prevState,
    threads: nextThreads,
    subAgents: nextSubAgents,
    streamingTurnIdByThread: nextStreamingTurns,
    processedEventIdsByThread: {
      ...prevState.processedEventIdsByThread,
      [threadId]: updatedProcessedList
    },
    interruptedTurnIdsByThread: nextInterruptedTurns,
    lastSequenceByThread: {
      ...prevState.lastSequenceByThread,
      [threadId]: updatedSeq
    }
  }

  return {
    ...prevState,
    ...nextServerState,
    currentActionText,
    turnElapsedSeconds,
    isStreaming: computeIsStreaming(nextServerState, prevState.activeThreadId)
  }
}

// -------------------------------------------------------------
// Singleton In-Memory Store
// -------------------------------------------------------------

let state: WorkbenchState = {
  ...initialServerState,
  ...initialLocalUIState,
  isStreaming: computeIsStreaming(initialServerState, initialLocalUIState.activeThreadId)
}

const listeners = new Set<() => void>()

function notify() {
  listeners.forEach(listener => listener())
}

export function updateState(
  updater: Partial<WorkbenchState> | ((prev: WorkbenchState) => Partial<WorkbenchState>)
) {
  const next = typeof updater === 'function' ? updater(state) : updater
  const merged = { ...state, ...next }
  merged.isStreaming = computeIsStreaming(merged, merged.activeThreadId)
  state = merged
  notify()
}

export function resetStateForTesting(customInitialState?: Partial<WorkbenchState>) {
  state = {
    ...initialServerState,
    ...initialLocalUIState,
    streamingTurnIdByThread: {},
    processedEventIdsByThread: {},
    interruptedTurnIdsByThread: {},
    lastSequenceByThread: {},
    isStreaming: false,
    ...customInitialState
  }
  notify()
}

export function getWorkbenchState(): WorkbenchState {
  return state
}

// Active EventSource connection tracker
let activeEventSourceCleanup: (() => void) | null = null

function syncEventSourceConnection(activeProjectId: string, activeThreadId: string | null) {
  if (activeEventSourceCleanup) {
    activeEventSourceCleanup()
    activeEventSourceCleanup = null
  }

  if (state.appMode !== 'live' || !activeProjectId || !activeThreadId) {
    return
  }

  activeEventSourceCleanup = codexApi.connectThreadEvents(
    activeProjectId,
    activeThreadId,
    (envelope) => {
      updateState(prev => reduceSSEEvent(prev, envelope))
    },
    (err) => {
      console.warn('SSE connection error for thread:', activeThreadId, err)
    }
  )
}

// -------------------------------------------------------------
// React Hook
// -------------------------------------------------------------

export function useWorkbenchStore() {
  const [, setTick] = useState(0)

  useEffect(() => {
    const listener = () => setTick(t => t + 1)
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  }, [])

  // Sync theme with DOM root
  useEffect(() => {
    if (typeof document !== 'undefined') {
      if (state.theme === 'dark') {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    }
    setSafeLocalStorage('codex_theme', state.theme)
  }, [state.theme])

  // Sync SSE connection on thread or mode change
  useEffect(() => {
    syncEventSourceConnection(state.activeProjectId, state.activeThreadId)
    return () => {
      if (activeEventSourceCleanup) {
        activeEventSourceCleanup()
        activeEventSourceCleanup = null
      }
    }
  }, [state.activeProjectId, state.activeThreadId, state.appMode])

  // Initial load for live mode
  useEffect(() => {
    if (state.appMode === 'live') {
      codexApi.getHealth()
        .then(() => {
          updateState({ connectionStatus: 'connected' })
          return Promise.all([
            codexApi.listProjects().catch(err => {
              console.warn('Failed to list projects:', err)
              return []
            }),
            codexApi.listThreads().catch(err => {
              console.warn('Failed to list threads:', err)
              return []
            }),
            codexApi.listBoundaries().catch(err => {
              console.warn('Failed to list boundaries:', err)
              return []
            }),
            codexApi.getTelemetrySettings().catch(err => {
              console.warn('Failed to get telemetry settings:', err)
              return null
            })
          ])
        })
        .then(([projectsData, threadsData, boundariesData, telemetryData]) => {
          const mappedThreads: Thread[] = Array.isArray(threadsData) ? threadsData.map(t => {
            const existing = state.threads.find(et => et.id === t.id)
            return {
              id: t.id,
              projectId: t.project_id,
              title: t.title,
              module: 'General Engineering',
              status: (t.status as any) || 'active',
              branch: 'main',
              worktree: 'wt-main',
              model: 'gpt-4o',
              reasoningEffort: 'medium',
              permissionProfile: 'workspace_write',
              contextCompactionState: 'healthy',
              subAgentCount: 0,
              approvalCount: 0,
              createdAt: new Date().toLocaleTimeString(),
              updatedAt: new Date().toLocaleTimeString(),
              isPinned: t.is_pinned,
              isArchived: t.is_archived,
              turns: existing?.turns || []
            }
          }) : []

          let mappedProjects: Project[] = []
          if (Array.isArray(projectsData) && projectsData.length > 0) {
            mappedProjects = projectsData.map(p => ({
              id: p.id,
              name: p.name,
              repository: p.repo_path || p.name,
              repo_path: p.repo_path,
              defaultBranch: p.default_branch || 'main',
              activeThreadCount: typeof p.thread_count === 'number' ? p.thread_count : 0,
              healthState: 'healthy',
              lastActivity: 'Just now',
              writeRoots: [p.repo_path || 'frontend/'],
              authMode: 'chatgpt_managed',
              modelPolicy: 'gpt-4o default',
              description: p.repo_path
            }))
          } else if (mappedThreads.length > 0) {
            const primaryProjectId = mappedThreads[0]?.projectId || 'proj_codex'
            mappedProjects = state.projects.length > 0 ? state.projects : [
              {
                id: primaryProjectId,
                name: 'Codex Control Centre',
                repository: 'codex-control-centre',
                defaultBranch: 'main',
                activeThreadCount: mappedThreads.length,
                healthState: 'healthy',
                lastActivity: 'Just now',
                writeRoots: ['frontend/', 'backend/'],
                authMode: 'chatgpt_managed',
                modelPolicy: 'gpt-4o default'
              }
            ]
          }

          const primaryProjectId = mappedProjects[0]?.id || mappedThreads[0]?.projectId || ''
          const chosenProjectId = state.activeProjectId && mappedProjects.some(p => p.id === state.activeProjectId)
            ? state.activeProjectId
            : (primaryProjectId || state.activeProjectId)

          const chosenThreadId = state.activeThreadId && mappedThreads.some(t => t.id === state.activeThreadId)
            ? state.activeThreadId
            : (mappedThreads.find(t => t.projectId === chosenProjectId)?.id || mappedThreads[0]?.id || null)

          updateState(prev => ({
            threads: mappedThreads,
            projects: mappedProjects.length > 0 ? mappedProjects : prev.projects,
            activeProjectId: chosenProjectId || prev.activeProjectId,
            activeThreadId: chosenThreadId,
            boundaries: Array.isArray(boundariesData) && boundariesData.length > 0 ? boundariesData : prev.boundaries,
            telemetrySettings: telemetryData || prev.telemetrySettings
          }))
        })
        .catch(err => {
          console.warn('Initial live API sync encountered connection status change:', err)
          updateState({ connectionStatus: 'disconnected' })
        })
    }
  }, [state.appMode])

  // Get active entities
  const activeProject = state.projects.find(p => p.id === state.activeProjectId) || state.projects[0]
  const activeThread = state.threads.find(t => t.id === state.activeThreadId) || null
  const projectThreads = state.threads.filter(t => t.projectId === state.activeProjectId)
  const activeSubAgents = state.subAgents.filter(sa => sa.parentThreadId === state.activeThreadId)

  // Actions
  const toggleTheme = () => {
    const nextTheme = state.theme === 'dark' ? 'light' : 'dark'
    updateState({ theme: nextTheme })
  }

  const selectProject = (projectId: string) => {
    const project = state.projects.find(p => p.id === projectId)
    if (!project) return
    const projectFirstThread = state.threads.find(t => t.projectId === projectId)
    updateState({
      activeProjectId: projectId,
      activeThreadId: projectFirstThread ? projectFirstThread.id : null,
      liveAnnouncements: [`Switched to project: ${project.name}`]
    })
  }

  const selectThread = (threadId: string) => {
    const thread = state.threads.find(t => t.id === threadId)
    if (thread) {
      updateState({
        activeThreadId: threadId,
        activeProjectId: thread.projectId,
        activeAgentId: 'main',
        liveAnnouncements: [`Opened thread: ${thread.title}`]
      })
    }
  }

  const isThreadStreaming = (threadId: string): boolean => {
    return Boolean(state.streamingTurnIdByThread[threadId])
  }

  const createThread = async (
    title: string,
    model: string = 'gpt-4o',
    reasoning: ReasoningEffort = 'medium',
    permission: PermissionProfile = 'workspace_write'
  ) => {
    const newThreadId = `th_${Date.now()}`
    const targetProjId = state.activeProjectId || 'proj_codex'

    const newThread: Thread = {
      id: newThreadId,
      projectId: targetProjId,
      title: title || 'New Engineering Investigation',
      module: 'General Engineering',
      status: 'active',
      branch: 'main',
      worktree: 'wt-main',
      model,
      reasoningEffort: reasoning,
      permissionProfile: permission,
      contextCompactionState: 'healthy',
      subAgentCount: 0,
      approvalCount: 0,
      createdAt: 'Just now',
      updatedAt: 'Just now',
      turns: []
    }

    updateState(prev => ({
      threads: [newThread, ...prev.threads],
      activeThreadId: newThreadId,
      liveAnnouncements: [`Created new thread: ${newThread.title}`]
    }))

    if (state.appMode === 'live') {
      try {
        const res = await codexApi.createThread({ project_id: targetProjId, title: newThread.title })
        if (res && res.id) {
          updateState(prev => ({
            threads: prev.threads.map(t => t.id === newThreadId ? { ...t, id: res.id } : t),
            activeThreadId: prev.activeThreadId === newThreadId ? res.id : prev.activeThreadId
          }))
        }
      } catch (err) {
        console.error('Failed to create thread via API:', err)
      }
    }
  }

  const renameThread = async (threadId: string, newTitle: string) => {
    updateState(prev => ({
      threads: prev.threads.map(t => t.id === threadId ? { ...t, title: newTitle } : t),
      liveAnnouncements: [`Renamed thread to: ${newTitle}`]
    }))

    if (state.appMode === 'live') {
      try {
        await codexApi.updateThread(threadId, { title: newTitle })
      } catch (err) {
        console.error('Failed to update thread title on API:', err)
      }
    }
  }

  const pinThread = async (threadId: string) => {
    const thread = state.threads.find(t => t.id === threadId)
    const nextPinned = !thread?.isPinned
    updateState(prev => ({
      threads: prev.threads.map(t => t.id === threadId ? { ...t, isPinned: nextPinned } : t)
    }))

    if (state.appMode === 'live') {
      try {
        await codexApi.updateThread(threadId, { is_pinned: nextPinned })
      } catch (err) {
        console.error('Failed to update pin state on API:', err)
      }
    }
  }

  const archiveThread = async (threadId: string) => {
    const thread = state.threads.find(t => t.id === threadId)
    const nextArchived = !thread?.isArchived
    updateState(prev => ({
      threads: prev.threads.map(t =>
        t.id === threadId
          ? { ...t, isArchived: nextArchived, status: nextArchived ? 'archived' : 'active' }
          : t
      )
    }))

    if (state.appMode === 'live') {
      try {
        await codexApi.updateThread(threadId, { is_archived: nextArchived, status: nextArchived ? 'archived' : 'active' })
      } catch (err) {
        console.error('Failed to update archive state on API:', err)
      }
    }
  }

  const compactThread = async (threadId: string) => {
    updateState({
      liveAnnouncements: [`Context compaction requested for thread: ${threadId}`]
    })

    // CCC-021: In demo mode, apply synthetic compaction event; in live mode, await backend event
    if (state.appMode === 'demo') {
      const demoEvent: SSEEventEnvelope = {
        id: `evt_comp_${Date.now()}`,
        project_id: state.activeProjectId,
        thread_id: threadId,
        sequence: (state.lastSequenceByThread[threadId] || 0) + 1,
        type: 'compaction_notice',
        occurred_at: new Date().toLocaleTimeString(),
        payload: {
          explanation: 'Codex condensed earlier conversation history to preserve room for continued work. Persisted project files and thread records remain available.',
          tokens_saved: 3840,
          original_turn_count: 4
        }
      }
      applySSEEvent(demoEvent)
    }
  }

  const createProject = async (name: string, repository: string) => {
    let newProject: Project
    if (state.appMode === 'live') {
      const created = await codexApi.createProject({
        name: name || 'Custom Engineering Project',
        repo_path: repository || 'frontend/'
      })
      newProject = {
        id: created.id,
        name: created.name,
        repository: created.repo_path,
        repo_path: created.repo_path,
        defaultBranch: created.default_branch || 'main',
        activeThreadCount: typeof created.thread_count === 'number' ? created.thread_count : 0,
        healthState: 'healthy',
        lastActivity: 'Just now',
        writeRoots: [created.repo_path],
        authMode: 'chatgpt_managed',
        modelPolicy: 'gpt-4o default',
        description: created.repo_path
      }
    } else {
      const newProjId = `proj_${Date.now()}`
      newProject = {
        id: newProjId,
        name: name || 'Custom Engineering Project',
        repository: repository || 'custom-repository',
        repo_path: repository || 'custom-repository',
        defaultBranch: 'main',
        activeThreadCount: 0,
        healthState: 'healthy',
        lastActivity: 'Just now',
        writeRoots: [repository || 'frontend/'],
        authMode: 'chatgpt_managed',
        modelPolicy: 'gpt-4o default'
      }
    }

    updateState(prev => {
      const exists = prev.projects.some(p => p.id === newProject.id)
      const nextProjects = exists
        ? prev.projects.map(p => p.id === newProject.id ? newProject : p)
        : [...prev.projects, newProject]
      return {
        projects: nextProjects,
        activeProjectId: newProject.id,
        activeThreadId: null,
        liveAnnouncements: [`Registered project: ${newProject.name}`]
      }
    })

    return newProject
  }

  const fetchBoundaries = async () => {
    if (state.appMode === 'live') {
      try {
        const boundaries = await codexApi.listBoundaries()
        updateState({ boundaries })
      } catch (err) {
        console.warn('Failed to fetch boundaries:', err)
      }
    }
  }

  const addBoundary = async (path: string, name?: string) => {
    if (state.appMode === 'live') {
      const created = await codexApi.addBoundary({ path, name })
      updateState(prev => {
        const exists = prev.boundaries.some(b => b.id === created.id || b.path.toLowerCase() === created.path.toLowerCase())
        return {
          boundaries: exists
            ? prev.boundaries.map(b => (b.id === created.id || b.path.toLowerCase() === created.path.toLowerCase()) ? created : b)
            : [...prev.boundaries, created],
          liveAnnouncements: [`Added workspace boundary: ${created.name}`]
        }
      })
      return created
    } else {
      const newBoundary: WorkspaceBoundary = {
        id: `bound_${Date.now()}`,
        path: path.trim(),
        name: name?.trim() || path.trim().split(/[\\/]/).pop() || 'Workspace Boundary',
        is_default: false
      }
      updateState(prev => ({
        boundaries: [...prev.boundaries, newBoundary],
        liveAnnouncements: [`Added workspace boundary: ${newBoundary.name}`]
      }))
      return newBoundary
    }
  }

  const removeBoundary = async (idOrPath: string) => {
    if (state.appMode === 'live') {
      await codexApi.deleteBoundary(idOrPath)
      await fetchBoundaries()
    } else {
      updateState(prev => ({
        boundaries: prev.boundaries.filter(b => b.id !== idOrPath && b.path !== idOrPath)
      }))
    }
  }

  const fetchTelemetrySettings = async () => {
    if (state.appMode === 'live') {
      try {
        const settings = await codexApi.getTelemetrySettings()
        updateState({ telemetrySettings: settings })
      } catch (err) {
        console.warn('Failed to fetch telemetry settings:', err)
      }
    }
  }

  const updateTelemetrySettings = async (payload: { signoz_url: string; otlp_endpoint: string; enabled: boolean }) => {
    if (state.appMode === 'live') {
      const updated = await codexApi.updateTelemetrySettings(payload)
      updateState({ telemetrySettings: updated })
      return updated
    } else {
      const mockUpdated: TelemetrySettings = {
        ...payload,
        connected: payload.enabled,
        status: payload.enabled ? 'Connected' : 'Disabled',
        latency_ms: 1.0
      }
      updateState({ telemetrySettings: mockUpdated })
      return mockUpdated
    }
  }

  const testTelemetry = async (endpoint: string) => {
    if (state.appMode === 'live') {
      return await codexApi.testTelemetryEndpoint(endpoint)
    } else {
      return {
        connected: true,
        status: 'Connected (Simulated)',
        status_code: 200,
        latency_ms: 2.4,
        url: endpoint
      }
    }
  }

  const deleteThread = async (threadId: string) => {
    const threadToDelete = state.threads.find(t => t.id === threadId)
    if (!threadToDelete) return

    updateState(prev => {
      const remainingThreads = prev.threads.filter(t => t.id !== threadId)
      let nextActiveThreadId = prev.activeThreadId
      if (prev.activeThreadId === threadId) {
        const siblingThread = remainingThreads.find(t => t.projectId === threadToDelete.projectId)
        nextActiveThreadId = siblingThread ? siblingThread.id : (remainingThreads[0]?.id || null)
      }

      const nextStreamingTurns = { ...prev.streamingTurnIdByThread }
      delete nextStreamingTurns[threadId]

      return {
        threads: remainingThreads,
        activeThreadId: nextActiveThreadId,
        streamingTurnIdByThread: nextStreamingTurns,
        liveAnnouncements: [`Deleted thread: ${threadToDelete.title}`]
      }
    })

    if (state.appMode === 'live') {
      try {
        await codexApi.deleteThread(threadId)
      } catch (err) {
        console.error('Failed to delete thread on API:', err)
      }
    }
  }

  const steerActiveTurn = async (instruction: string) => {
    const threadId = state.activeThreadId
    if (!threadId || !instruction.trim()) return

    const activeTurnId = state.streamingTurnIdByThread[threadId]

    updateState(prev => {
      // In demo mode or if turn exists, append steering agent message
      const updatedThreads = prev.threads.map(t => {
        if (t.id !== threadId) return t
        return {
          ...t,
          turns: t.turns.map(turn => {
            if (activeTurnId && turn.id === activeTurnId) {
              const steerNoticeItem: TimelineItem = {
                id: `steer_${Date.now()}`,
                turnId: turn.id,
                type: 'agent_message',
                timestamp: new Date().toLocaleTimeString(),
                content: `Steering instruction acknowledged: "${instruction}". Adjusting task execution...`
              }
              return { ...turn, items: [...turn.items, steerNoticeItem] }
            }
            return turn
          })
        }
      })

      return {
        threads: updatedThreads,
        liveAnnouncements: [`Sent steering guidance: "${instruction.slice(0, 40)}..."`]
      }
    })

    if (state.appMode === 'live' && activeTurnId) {
      try {
        await codexApi.steerTurn({
          thread_id: threadId,
          turn_id: parseInt(activeTurnId, 10) || 1,
          instruction: instruction.trim()
        })
      } catch (err) {
        console.error('Failed to steer turn on backend:', err)
      }
    }
  }

  // CCC-021: Approvals are strictly scoped to their owning thread
  const approveRequest = async (
    approvalId: string,
    scope: 'once' | 'session' = 'once',
    targetThreadId?: string,
    feedback?: string
  ) => {
    const owningThreadId = targetThreadId || state.threads.find(t =>
      t.turns.some(turn => turn.items.some(item => item.type === 'approval_request' && item.approvalId === approvalId))
    )?.id || state.activeThreadId

    if (!owningThreadId) return

    updateState(prev => ({
      threads: prev.threads.map(t => {
        if (t.id !== owningThreadId) return t
        let found = false
        const updatedTurns = t.turns.map(turn => ({
          ...turn,
          items: turn.items.map(item => {
            if (item.type === 'approval_request' && item.approvalId === approvalId) {
              found = true
              return { ...item, status: 'approved' as const, scope }
            }
            return item
          })
        }))
        const newApprovalCount = found ? Math.max(0, t.approvalCount - 1) : t.approvalCount
        return {
          ...t,
          approvalCount: newApprovalCount,
          status: found && t.status === 'needs_approval' && newApprovalCount === 0 ? 'active' : t.status,
          turns: updatedTurns
        }
      }),
      liveAnnouncements: [`Approved request ${approvalId} (${scope})`]
    }))

    if (state.appMode === 'live') {
      try {
        await codexApi.resolveApproval(approvalId, true, feedback)
      } catch (err) {
        console.error('Failed to resolve approval on backend:', err)
      }
    }
  }

  const declineRequest = async (
    approvalId: string,
    targetThreadId?: string,
    feedback?: string
  ) => {
    const owningThreadId = targetThreadId || state.threads.find(t =>
      t.turns.some(turn => turn.items.some(item => item.type === 'approval_request' && item.approvalId === approvalId))
    )?.id || state.activeThreadId

    if (!owningThreadId) return

    updateState(prev => ({
      threads: prev.threads.map(t => {
        if (t.id !== owningThreadId) return t
        let found = false
        const updatedTurns = t.turns.map(turn => ({
          ...turn,
          items: turn.items.map(item => {
            if (item.type === 'approval_request' && item.approvalId === approvalId) {
              found = true
              return { ...item, status: 'declined' as const }
            }
            return item
          })
        }))
        const newApprovalCount = found ? Math.max(0, t.approvalCount - 1) : t.approvalCount
        return {
          ...t,
          approvalCount: newApprovalCount,
          status: found && t.status === 'needs_approval' && newApprovalCount === 0 ? 'active' : t.status,
          turns: updatedTurns
        }
      }),
      liveAnnouncements: [`Declined request ${approvalId}`]
    }))

    if (state.appMode === 'live') {
      try {
        await codexApi.resolveApproval(approvalId, false, feedback)
      } catch (err) {
        console.error('Failed to decline approval on backend:', err)
      }
    }
  }

  const recordDiffVerdict = (verdict: string) => {
    updateState({
      liveAnnouncements: [`Diff review verdict recorded: ${verdict}`]
    })
  }

  const steerSubAgent = async (agentId: string, instruction: string) => {
    updateState(prev => ({
      subAgents: prev.subAgents.map(sa => {
        if (sa.id === agentId) {
          return {
            ...sa,
            progressSummary: `Operator steered: "${instruction.slice(0, 40)}..."`
          }
        }
        return sa
      }),
      liveAnnouncements: [`Sent steering guidance to agent: ${agentId}`]
    }))

    if (state.appMode === 'live') {
      try {
        await codexApi.steerSubagent(agentId, instruction)
      } catch (err) {
        console.error('Failed to steer subagent on backend:', err)
      }
    }
  }

  const stopSubAgent = async (agentId: string) => {
    updateState(prev => ({
      subAgents: prev.subAgents.map(sa => {
        if (sa.id === agentId) {
          return { ...sa, status: 'stopped', progressSummary: 'Stopped by operator' }
        }
        return sa
      }),
      liveAnnouncements: [`Stopped child subagent: ${agentId}`]
    }))

    if (state.appMode === 'live') {
      try {
        await codexApi.stopSubagent(agentId)
      } catch (err) {
        console.error('Failed to stop subagent on backend:', err)
      }
    }
  }

  const sendUserMessage = async (
    text: string,
    options?: { model?: string; reasoningEffort?: ReasoningEffort }
  ) => {
    const threadId = state.activeThreadId
    if (!threadId || !text.trim()) return

    const newTurnId = `turn_${Date.now()}`
    const userItem: TimelineItem = {
      id: `usr_${Date.now()}`,
      turnId: newTurnId,
      type: 'user_instruction',
      timestamp: new Date().toLocaleTimeString(),
      content: text,
      authorName: 'Operator'
    }

    const streamedResponseItem: TimelineItem = {
      id: `stream_${Date.now()}`,
      turnId: newTurnId,
      type: 'agent_message',
      timestamp: new Date().toLocaleTimeString(),
      isStreaming: true,
      content: `I am processing your instruction: "${text}". Inspecting codebase and verifying invariants...`
    }

    // CCC-003: Set streaming specifically for active thread
    updateState(prev => ({
      streamingTurnIdByThread: {
        ...prev.streamingTurnIdByThread,
        [threadId]: newTurnId
      },
      currentActionText: 'Thinking...',
      turnElapsedSeconds: 0,
      threads: prev.threads.map(t => {
        if (t.id !== threadId) return t
        return {
          ...t,
          updatedAt: 'Just now',
          turns: [
            ...t.turns,
            {
              id: newTurnId,
              threadId: t.id,
              turnNumber: t.turns.length + 1,
              status: 'in_progress',
              startedAt: 'Just now',
              items: [userItem, streamedResponseItem]
            }
          ]
        }
      }),
      liveAnnouncements: ['New instruction submitted to Codex']
    }))

    if (state.appMode === 'live') {
      try {
        const turnRes = await codexApi.startTurn({
          thread_id: threadId,
          prompt: text,
          model: options?.model,
          reasoning_effort: options?.reasoningEffort,
        })
        if (turnRes?.turn_id) {
          const apiTurnId = String(turnRes.turn_id)
          updateState(prev => ({
            streamingTurnIdByThread: {
              ...prev.streamingTurnIdByThread,
              [threadId]: apiTurnId
            },
            threads: prev.threads.map(t => {
              if (t.id !== threadId) return t
              return {
                ...t,
                turns: t.turns.map(turn => {
                  if (turn.id === newTurnId) {
                    return {
                      ...turn,
                      id: apiTurnId,
                      items: turn.items.map(item => ({ ...item, turnId: apiTurnId }))
                    }
                  }
                  return turn
                })
              }
            })
          }))
        }
      } catch (err: any) {
        console.error('Failed to start turn on backend:', err)
        const errMsg = err?.message || 'Failed to start turn on backend'
        updateState(prev => ({
          streamingTurnIdByThread: {
            ...prev.streamingTurnIdByThread,
            [threadId]: null
          },
          threads: prev.threads.map(t => {
            if (t.id !== threadId) return t
            return {
              ...t,
              status: 'failed',
              turns: t.turns.map(turn => {
                if (turn.id === newTurnId) {
                  return {
                    ...turn,
                    status: 'failed',
                    items: [
                      ...turn.items.map(i => ({ ...i, isStreaming: false })),
                      {
                        id: `fail_${Date.now()}_${turn.id}`,
                        turnId: turn.id,
                        type: 'failure',
                        timestamp: new Date().toLocaleTimeString(),
                        errorCategory: 'internal',
                        summary: errMsg,
                        details: String(err),
                        canRetry: true,
                        suggestedAction: 'retry'
                      }
                    ]
                  }
                }
                return turn
              })
            }
          })
        }))
      }
    } else {
      // In demo mode: simulate streaming turn completion after 2.5 seconds
      setTimeout(() => {
        // If turn was interrupted while waiting, do not complete it
        const currentInterrupted = state.interruptedTurnIdsByThread[threadId] || []
        if (currentInterrupted.includes(newTurnId)) {
          return
        }

        updateState(prev => ({
          streamingTurnIdByThread: {
            ...prev.streamingTurnIdByThread,
            [threadId]: null
          },
          threads: prev.threads.map(t => {
            if (t.id !== threadId) return t
            return {
              ...t,
              turns: t.turns.map(turn => {
                if (turn.id !== newTurnId) return turn
                return {
                  ...turn,
                  status: 'completed',
                  items: turn.items.map(item => {
                    if (item.type === 'agent_message' && item.isStreaming) {
                      return {
                        ...item,
                        isStreaming: false,
                        content: `I have completed the analysis for: "${text}". All verified files and tests match the defined specification.`
                      }
                    }
                    return item
                  })
                }
              })
            }
          }),
          liveAnnouncements: ['Turn execution completed']
        }))
      }, 2500)
    }
  }

  const stopActiveTurn = async () => {
    const threadId = state.activeThreadId
    if (!threadId) return

    const activeThreadObj = state.threads.find(t => t.id === threadId)
    const inProgressTurn = activeThreadObj?.turns.find(t => t.status === 'in_progress')
    const activeTurnId = state.streamingTurnIdByThread[threadId] || inProgressTurn?.id

    updateState(prev => {
      const interruptedList = prev.interruptedTurnIdsByThread[threadId] || []
      const updatedInterrupted = activeTurnId && !interruptedList.includes(activeTurnId)
        ? [...interruptedList, activeTurnId]
        : interruptedList

      return {
        streamingTurnIdByThread: {
          ...prev.streamingTurnIdByThread,
          [threadId]: null
        },
        currentActionText: undefined,
        turnElapsedSeconds: 0,
        interruptedTurnIdsByThread: {
          ...prev.interruptedTurnIdsByThread,
          [threadId]: updatedInterrupted
        },
        threads: prev.threads.map(t => {
          if (t.id !== threadId) return t
          return {
            ...t,
            status: 'interrupted',
            turns: t.turns.map(turn => {
              if (turn.status === 'in_progress') {
                const hasInterruptItem = turn.items.some(i => i.type === 'interruption')
                const interruptItem: TimelineItem = {
                  id: `int_${Date.now()}_${turn.id}_${Math.random().toString(36).slice(2, 6)}`,
                  turnId: turn.id,
                  type: 'interruption',
                  timestamp: new Date().toLocaleTimeString(),
                  reason: 'Turn manually interrupted by operator via Stop button.',
                  interruptedBy: 'Operator'
                }
                return {
                  ...turn,
                  status: 'interrupted',
                  items: hasInterruptItem
                    ? turn.items.map(i => ({ ...i, isStreaming: false }))
                    : [...turn.items.map(i => ({ ...i, isStreaming: false })), interruptItem]
                }
              }
              return turn
            })
          }
        }),
        liveAnnouncements: ['Active turn stopped']
      }
    })

    if (state.appMode === 'live') {
      try {
        let numericTurnId = 0
        if (activeTurnId && !activeTurnId.startsWith('turn_') && !isNaN(parseInt(activeTurnId, 10))) {
          numericTurnId = parseInt(activeTurnId, 10)
        } else if (inProgressTurn?.id && !inProgressTurn.id.startsWith('turn_') && !isNaN(parseInt(inProgressTurn.id, 10))) {
          numericTurnId = parseInt(inProgressTurn.id, 10)
        }
        await codexApi.interruptTurn({
          thread_id: threadId,
          turn_id: numericTurnId
        })
      } catch (err) {
        console.error('Failed to interrupt turn on backend:', err)
      }
    }
  }

  const applySSEEvent = (event: SSEEventEnvelope) => {
    updateState(prev => reduceSSEEvent(prev, event))
  }

  const setSidebarOpen = (open: boolean) => updateState({ isSidebarOpen: open })
  const setInspectorOpen = (open: boolean) => updateState({ isInspectorOpen: open })
  const setInspectorTab = (tab: InspectorTab) => updateState({ activeInspectorTab: tab, isInspectorOpen: true })
  const setDiffStudioOpen = (open: boolean) => updateState({ isDiffStudioOpen: open })
  const selectDiffFile = (index: number) => updateState({ selectedDiffFileIndex: index, isDiffStudioOpen: true })
  const setCommandPaletteOpen = (open: boolean) => updateState({ isCommandPaletteOpen: open })
  const setThreadSearchQuery = (query: string) => updateState({ threadSearchQuery: query })
  const setThreadStatusFilter = (filter: string) => updateState({ threadStatusFilter: filter })
  const setSidebarWidth = (width: number) => updateState({ sidebarWidth: Math.max(260, Math.min(480, width)) })
  const setInspectorWidth = (width: number) => updateState({ inspectorWidth: Math.max(320, Math.min(600, width)) })

  const retryConnection = () => {
    updateState({ connectionStatus: 'connecting', liveAnnouncements: ['Reconnecting to Codex Event stream...'] })
    if (state.appMode === 'live') {
      codexApi.getHealth()
        .then(() => {
          updateState({
            connectionStatus: 'connected',
            lastConnectedTime: new Date().toLocaleTimeString(),
            liveAnnouncements: ['Reconnected to Codex Event stream successfully']
          })
        })
        .catch(() => {
          updateState({ connectionStatus: 'disconnected' })
        })
    } else {
      setTimeout(() => {
        updateState({
          connectionStatus: 'connected',
          lastConnectedTime: new Date().toLocaleTimeString(),
          liveAnnouncements: ['Reconnected to Codex Event stream successfully']
        })
      }, 1200)
    }
  }

  const setAppMode = (mode: AppMode) => {
    setSafeLocalStorage('codex_app_mode', mode)
    if (mode === 'demo') {
      updateState({
        appMode: mode,
        projects: FIXTURE_PROJECTS,
        activeProjectId: 'proj_fastapi_bookings',
        threads: FIXTURE_THREADS,
        activeThreadId: 'th_active_stream',
        subAgents: FIXTURE_SUBAGENTS,
        diffFiles: FIXTURE_DIFFS,
        telemetryIncidents: FIXTURE_INCIDENTS,
        streamingTurnIdByThread: { th_active_stream: 'turn_live_1' },
        connectionStatus: 'connected'
      })
    } else {
      updateState({
        appMode: mode,
        projects: [],
        activeProjectId: '',
        threads: [],
        activeThreadId: null,
        subAgents: [],
        diffFiles: [],
        telemetryIncidents: [],
        streamingTurnIdByThread: {},
        processedEventIdsByThread: {},
        interruptedTurnIdsByThread: {},
        lastSequenceByThread: {},
        connectionStatus: 'connecting'
      })
      codexApi.getHealth()
        .then(() => updateState({ connectionStatus: 'connected' }))
        .catch(() => updateState({ connectionStatus: 'disconnected' }))
    }
  }

  // Live ticking turnElapsedSeconds during active streaming
  useEffect(() => {
    if (!state.isStreaming) return
    const interval = setInterval(() => {
      updateState(prev => {
        if (!prev.isStreaming) return prev
        return { turnElapsedSeconds: prev.turnElapsedSeconds + 1 }
      })
    }, 1000)
    return () => clearInterval(interval)
  }, [state.isStreaming])

  const setActiveAgentId = (id: string) => {
    updateState({
      activeAgentId: id,
      liveAnnouncements: [id === 'main' ? 'Switched to Main Orchestrator view' : `Switched to subagent view: ${id}`]
    })
  }

  return {
    state,
    activeProject,
    activeThread,
    projectThreads,
    activeSubAgents,
    activeAgentId: state.activeAgentId,
    currentActionText: state.currentActionText,
    turnElapsedSeconds: state.turnElapsedSeconds,
    setActiveAgentId,
    toggleTheme,
    selectProject,
    selectThread,
    createProject,
    createThread,
    deleteThread,
    renameThread,
    pinThread,
    archiveThread,
    compactThread,
    approveRequest,
    declineRequest,
    steerActiveTurn,
    steerSubAgent,
    stopSubAgent,
    sendUserMessage,
    stopActiveTurn,
    recordDiffVerdict,
    applySSEEvent,
    isThreadStreaming,
    setSidebarOpen,
    setInspectorOpen,
    setInspectorTab,
    setDiffStudioOpen,
    selectDiffFile,
    setCommandPaletteOpen,
    setThreadSearchQuery,
    setThreadStatusFilter,
    setSidebarWidth,
    setInspectorWidth,
    retryConnection,
    setAppMode,
    fetchBoundaries,
    addBoundary,
    removeBoundary,
    fetchTelemetrySettings,
    updateTelemetrySettings,
    testTelemetry
  }
}
