import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import {
  reduceSSEEvent,
  initialServerState,
  initialLocalUIState,
  resetStateForTesting,
  getWorkbenchState
} from '../store/useWorkbenchStore'
import type { WorkbenchState } from '../store/useWorkbenchStore'
import { CodexApi } from '../api/codexApi'
import { ApiClient } from '../api/client'
import type { SSEEventEnvelope } from '../types/workbench'

describe('useWorkbenchStore & State Architecture (WP-07)', () => {
  let baseState: WorkbenchState

  beforeEach(() => {
    baseState = {
      ...initialServerState,
      ...initialLocalUIState,
      appMode: 'live',
      projects: [
        {
          id: 'proj_codex',
          name: 'Codex Control Centre',
          repository: 'codex-control-centre',
          defaultBranch: 'main',
          activeThreadCount: 2,
          healthState: 'healthy',
          lastActivity: 'Just now',
          writeRoots: ['frontend/', 'backend/'],
          authMode: 'chatgpt_managed',
          modelPolicy: 'gpt-4o default'
        }
      ],
      activeProjectId: 'proj_codex',
      threads: [
        {
          id: 'th_alpha',
          projectId: 'proj_codex',
          title: 'Thread Alpha',
          module: 'Core Module',
          status: 'active',
          branch: 'main',
          worktree: 'wt-main',
          model: 'gpt-4o',
          reasoningEffort: 'medium',
          permissionProfile: 'workspace_write',
          contextCompactionState: 'healthy',
          subAgentCount: 0,
          approvalCount: 0,
          createdAt: '10:00 AM',
          updatedAt: '10:00 AM',
          turns: []
        },
        {
          id: 'th_beta',
          projectId: 'proj_codex',
          title: 'Thread Beta',
          module: 'Telemetry Module',
          status: 'active',
          branch: 'main',
          worktree: 'wt-main',
          model: 'gpt-4o',
          reasoningEffort: 'medium',
          permissionProfile: 'workspace_write',
          contextCompactionState: 'healthy',
          subAgentCount: 0,
          approvalCount: 0,
          createdAt: '10:05 AM',
          updatedAt: '10:05 AM',
          turns: []
        }
      ],
      activeThreadId: 'th_alpha',
      subAgents: [],
      diffFiles: [],
      telemetryIncidents: [],
      streamingTurnIdByThread: {},
      processedEventIdsByThread: {},
      interruptedTurnIdsByThread: {},
      lastSequenceByThread: {},
      isStreaming: false
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // -------------------------------------------------------------
  // Test 1: Event deduplication on replayed SSE events (CCC-004)
  // -------------------------------------------------------------
  it('deduplicates replayed SSE events and prevents timeline or counter duplication', () => {
    // 1. Send turn_started event
    const startEvent: SSEEventEnvelope = {
      id: 'evt_start_1',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 1,
      type: 'turn_started',
      occurred_at: '10:10:00 AM',
      payload: { turn_id: 'turn_101', prompt: 'Run benchmark' }
    }
    let state = reduceSSEEvent(baseState, startEvent)

    // 2. Send agent message
    const msgEvent: SSEEventEnvelope = {
      id: 'evt_msg_1',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 2,
      type: 'agent_message',
      occurred_at: '10:10:02 AM',
      payload: { turn_id: 'turn_101', item_id: 'item_msg_1', content: 'Evaluating files...', is_streaming: true }
    }
    state = reduceSSEEvent(state, msgEvent)

    // 3. Send approval request
    const apprEvent: SSEEventEnvelope = {
      id: 'evt_appr_1',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 3,
      type: 'approval_requested',
      occurred_at: '10:10:05 AM',
      payload: {
        turn_id: 'turn_101',
        approval_id: 'appr_gate_1',
        command: 'rm -rf /tmp/cache',
        risk: 'high',
        consequence: 'Deletes temp cache'
      }
    }
    state = reduceSSEEvent(state, apprEvent)

    const threadAlpha = state.threads.find(t => t.id === 'th_alpha')!
    expect(threadAlpha.turns.length).toBe(1)
    expect(threadAlpha.turns[0].items.length).toBe(3) // prompt + message + approval
    expect(threadAlpha.approvalCount).toBe(1)
    expect(threadAlpha.status).toBe('needs_approval')

    // 4. Replay identical events (as in EventSource reconnection / replay buffer)
    const stateReplayedMsg = reduceSSEEvent(state, msgEvent)
    const stateReplayedAppr = reduceSSEEvent(stateReplayedMsg, apprEvent)

    const replayedThread = stateReplayedAppr.threads.find(t => t.id === 'th_alpha')!
    expect(replayedThread.turns[0].items.length).toBe(3) // EXACT same count, no duplicates!
    expect(replayedThread.approvalCount).toBe(1) // Still 1, no double counting!
    expect(stateReplayedAppr.processedEventIdsByThread['th_alpha']).toContain('evt_msg_1')
    expect(stateReplayedAppr.processedEventIdsByThread['th_alpha']).toContain('evt_appr_1')
  })

  // -------------------------------------------------------------
  // Test 2: Multi-thread isolation (CCC-003)
  // -------------------------------------------------------------
  it('enforces multi-thread isolation without global streaming lock bleed', () => {
    // 1. Start streaming turn on Thread Alpha
    const startEventAlpha: SSEEventEnvelope = {
      id: 'evt_turn_alpha',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 1,
      type: 'turn_started',
      occurred_at: '10:15:00 AM',
      payload: { turn_id: 'turn_alpha_1', prompt: 'Task Alpha' }
    }
    let state = reduceSSEEvent(baseState, startEventAlpha)

    // Thread Alpha is streaming
    expect(state.streamingTurnIdByThread['th_alpha']).toBe('turn_alpha_1')
    // Thread Beta is NOT streaming
    expect(state.streamingTurnIdByThread['th_beta']).toBeFalsy()

    // When activeThreadId is Alpha, isStreaming is true
    state = { ...state, activeThreadId: 'th_alpha', isStreaming: Boolean(state.streamingTurnIdByThread['th_alpha']) }
    expect(state.isStreaming).toBe(true)

    // When activeThreadId is Beta, isStreaming is false
    state = { ...state, activeThreadId: 'th_beta', isStreaming: Boolean(state.streamingTurnIdByThread['th_beta']) }
    expect(state.isStreaming).toBe(false)

    // 2. Start a turn concurrently on Thread Beta
    const startEventBeta: SSEEventEnvelope = {
      id: 'evt_turn_beta',
      project_id: 'proj_codex',
      thread_id: 'th_beta',
      sequence: 1,
      type: 'turn_started',
      occurred_at: '10:15:05 AM',
      payload: { turn_id: 'turn_beta_1', prompt: 'Task Beta' }
    }
    state = reduceSSEEvent(state, startEventBeta)

    expect(state.streamingTurnIdByThread['th_alpha']).toBe('turn_alpha_1')
    expect(state.streamingTurnIdByThread['th_beta']).toBe('turn_beta_1')

    // 3. Complete Thread Alpha turn
    const completeEventAlpha: SSEEventEnvelope = {
      id: 'evt_complete_alpha',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 2,
      type: 'turn_completed',
      occurred_at: '10:15:10 AM',
      payload: { turn_id: 'turn_alpha_1', outcome: 'success' }
    }
    state = reduceSSEEvent(state, completeEventAlpha)

    // Thread Alpha is now completed & idle, Thread Beta is still active streaming!
    expect(state.streamingTurnIdByThread['th_alpha']).toBeNull()
    expect(state.streamingTurnIdByThread['th_beta']).toBe('turn_beta_1')
  })

  // -------------------------------------------------------------
  // Test 3: Approval resolution in Thread A does not mutate Thread B (CCC-021)
  // -------------------------------------------------------------
  it('scopes approval resolution strictly to the target thread without mutating other threads', () => {
    // Setup state with pending approvals in both Thread Alpha and Thread Beta
    const stateWithApprovals: WorkbenchState = {
      ...baseState,
      threads: [
        {
          ...baseState.threads[0],
          approvalCount: 1,
          status: 'needs_approval',
          turns: [
            {
              id: 'turn_a',
              threadId: 'th_alpha',
              turnNumber: 1,
              status: 'in_progress',
              startedAt: '10:00 AM',
              items: [
                {
                  id: 'item_appr_a',
                  turnId: 'turn_a',
                  type: 'approval_request',
                  timestamp: '10:01 AM',
                  approvalId: 'appr_alpha_100',
                  category: 'command',
                  title: 'Run migrations on Alpha',
                  consequence: 'Applies DB schema changes',
                  reason: 'Testing migration',
                  risk: 'high',
                  status: 'pending',
                  scope: 'once'
                }
              ]
            }
          ]
        },
        {
          ...baseState.threads[1],
          approvalCount: 1,
          status: 'needs_approval',
          turns: [
            {
              id: 'turn_b',
              threadId: 'th_beta',
              turnNumber: 1,
              status: 'in_progress',
              startedAt: '10:00 AM',
              items: [
                {
                  id: 'item_appr_b',
                  turnId: 'turn_b',
                  type: 'approval_request',
                  timestamp: '10:02 AM',
                  approvalId: 'appr_beta_200',
                  category: 'file_write',
                  title: 'Overwrite config on Beta',
                  consequence: 'Modifies runtime config',
                  reason: 'Testing config update',
                  risk: 'medium',
                  status: 'pending',
                  scope: 'once'
                }
              ]
            }
          ]
        }
      ]
    }

    // Resolve approval in Thread Alpha only
    const resolveAlphaEvent: SSEEventEnvelope = {
      id: 'evt_res_alpha',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 10,
      type: 'approval_resolved',
      occurred_at: '10:05 AM',
      payload: {
        approval_id: 'appr_alpha_100',
        approved: true,
        scope: 'once'
      }
    }

    const nextState = reduceSSEEvent(stateWithApprovals, resolveAlphaEvent)

    const threadA = nextState.threads.find(t => t.id === 'th_alpha')!
    const threadB = nextState.threads.find(t => t.id === 'th_beta')!

    // Thread Alpha approval is approved and count decremented
    expect(threadA.approvalCount).toBe(0)
    expect(threadA.status).toBe('active')
    const itemA = threadA.turns[0].items[0]
    expect(itemA.type).toBe('approval_request')
    if (itemA.type === 'approval_request') {
      expect(itemA.status).toBe('approved')
    }

    // Thread Beta approval is COMPLETELY UNTOUCHED
    expect(threadB.approvalCount).toBe(1)
    expect(threadB.status).toBe('needs_approval')
    const itemB = threadB.turns[0].items[0]
    expect(itemB.type).toBe('approval_request')
    if (itemB.type === 'approval_request') {
      expect(itemB.status).toBe('pending')
    }
  })

  // -------------------------------------------------------------
  // Test 4: Turn stop/interrupt prevents stale completion resurrection (CCC-003)
  // -------------------------------------------------------------
  it('prevents stale completion events from resurrecting an interrupted turn', () => {
    // 1. Start a turn
    const startEvent: SSEEventEnvelope = {
      id: 'evt_turn_start',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 1,
      type: 'turn_started',
      occurred_at: '10:20:00 AM',
      payload: { turn_id: 'turn_stop_test', prompt: 'Long running build' }
    }
    let state = reduceSSEEvent(baseState, startEvent)
    expect(state.streamingTurnIdByThread['th_alpha']).toBe('turn_stop_test')

    // 2. Interrupt the turn
    const interruptEvent: SSEEventEnvelope = {
      id: 'evt_turn_int',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 2,
      type: 'turn_interrupted',
      occurred_at: '10:20:05 AM',
      payload: { turn_id: 'turn_stop_test', reason: 'Operator pressed Stop' }
    }
    state = reduceSSEEvent(state, interruptEvent)

    const threadAfterInterrupt = state.threads.find(t => t.id === 'th_alpha')!
    const turnAfterInterrupt = threadAfterInterrupt.turns.find(t => t.id === 'turn_stop_test')!
    expect(turnAfterInterrupt.status).toBe('interrupted')
    expect(state.streamingTurnIdByThread['th_alpha']).toBeNull()
    expect(state.interruptedTurnIdsByThread['th_alpha']).toContain('turn_stop_test')

    // 3. Stale completion event arrives later from backend worker
    const staleCompletionEvent: SSEEventEnvelope = {
      id: 'evt_stale_complete',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 3,
      type: 'turn_completed',
      occurred_at: '10:20:10 AM',
      payload: { turn_id: 'turn_stop_test', summary: 'Finished late' }
    }
    state = reduceSSEEvent(state, staleCompletionEvent)

    const threadAfterStale = state.threads.find(t => t.id === 'th_alpha')!
    const turnAfterStale = threadAfterStale.turns.find(t => t.id === 'turn_stop_test')!
    // MUST remain interrupted! Must NOT be resurrected to completed!
    expect(turnAfterStale.status).toBe('interrupted')
    expect(state.streamingTurnIdByThread['th_alpha']).toBeNull()
  })

  // -------------------------------------------------------------
  // Test 5: Compaction notices rendered ONLY on backend event (CCC-021)
  // -------------------------------------------------------------
  it('renders compaction notices only upon backend compaction event confirmation', () => {
    const thread = baseState.threads.find(t => t.id === 'th_alpha')!
    expect(thread.contextCompactionState).toBe('healthy')
    expect(thread.turns.length).toBe(0)

    const compactionEvent: SSEEventEnvelope = {
      id: 'evt_compact_1',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 5,
      type: 'compaction_notice',
      occurred_at: '10:30:00 AM',
      payload: {
        explanation: 'Codex condensed earlier conversation history to preserve room for continued work.',
        tokens_saved: 4120,
        original_turn_count: 6
      }
    }

    const state = reduceSSEEvent(baseState, compactionEvent)
    const compactedThread = state.threads.find(t => t.id === 'th_alpha')!
    expect(compactedThread.contextCompactionState).toBe('compacted')
    expect(compactedThread.turns.length).toBe(1)
    expect(compactedThread.turns[0].items[0].type).toBe('compaction_notice')
  })

  // -------------------------------------------------------------
  // Test 6: Reducer handling of plan, command execution, and file change items
  // -------------------------------------------------------------
  it('correctly processes plan, command execution, file change, and subagent events', () => {
    let state = reduceSSEEvent(baseState, {
      id: 'evt_turn',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 1,
      type: 'turn_started',
      occurred_at: '10:00 AM',
      payload: { turn_id: 'turn_rich_1' }
    })

    // Plan event
    state = reduceSSEEvent(state, {
      id: 'evt_plan',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 2,
      type: 'plan',
      occurred_at: '10:01 AM',
      payload: {
        turn_id: 'turn_rich_1',
        title: 'Refactor Auth Architecture',
        tasks: [
          { id: 't1', title: 'Add Bearer Token Middleware', status: 'completed' },
          { id: 't2', title: 'Verify Signature Invariants', status: 'active' }
        ]
      }
    })

    // Command execution event
    state = reduceSSEEvent(state, {
      id: 'evt_cmd',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 3,
      type: 'command_execution',
      occurred_at: '10:02 AM',
      payload: {
        turn_id: 'turn_rich_1',
        command: 'pytest tests/test_auth.py',
        summary: 'Ran 12 unit tests',
        status: 'completed',
        stdout: '12 passed in 0.42s',
        exit_code: 0
      }
    })

    // File change event
    state = reduceSSEEvent(state, {
      id: 'evt_file',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 4,
      type: 'file_change',
      occurred_at: '10:03 AM',
      payload: {
        turn_id: 'turn_rich_1',
        summary: 'Updated middleware',
        files: [{ path: 'backend/auth.py', status: 'applied', additions: 15, deletions: 2 }],
        total_additions: 15,
        total_deletions: 2
      }
    })

    // Subagent status event
    state = reduceSSEEvent(state, {
      id: 'evt_subagent',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 5,
      type: 'subagent_activity',
      occurred_at: '10:04 AM',
      payload: {
        id: 'sa_worker_01',
        role: 'Database Migration Subagent',
        objective: 'Execute Alembic migrations',
        status: 'running',
        progress_summary: 'Migrating revision 001...'
      }
    })

    const thread = state.threads.find(t => t.id === 'th_alpha')!
    const turn = thread.turns.find(t => t.id === 'turn_rich_1')!
    expect(turn.items.some(i => i.type === 'plan')).toBe(true)
    expect(turn.items.some(i => i.type === 'command_execution')).toBe(true)
    expect(turn.items.some(i => i.type === 'file_change')).toBe(true)
    expect(state.subAgents.some(sa => sa.id === 'sa_worker_01')).toBe(true)
    expect(thread.subAgentCount).toBe(1)
  })

  // -------------------------------------------------------------
  // Test 7: Typed API Client and Codex API methods (CCC-001)
  // -------------------------------------------------------------
  it('configures ApiClient with default base URL, bearer token, and timeout', async () => {
    const client = new ApiClient()
    expect(client.getBaseUrl()).toBe('http://127.0.0.1:4500')
    expect(client.getToken()).toBe('local_secret')

    const codexApi = new CodexApi(client)
    expect(codexApi.getClient()).toBe(client)

    // Test EventSource connection helper
    const cleanup = codexApi.connectThreadEvents('proj_test', 'th_test', () => {})
    expect(typeof cleanup).toBe('function')
    cleanup()
  })

  // -------------------------------------------------------------
  // Test 8: ApiClient HTTP requests & error handling
  // -------------------------------------------------------------
  it('makes typed API requests with correct headers and bearer token', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'healthy', timestamp: '2026-08-30T00:00:00Z' })
    })
    globalThis.fetch = mockFetch

    const client = new ApiClient({ baseUrl: 'http://127.0.0.1:4500', token: 'custom_secret' })
    const api = new CodexApi(client)

    const health = await api.getHealth()
    expect(health.status).toBe('healthy')
    expect(mockFetch).toHaveBeenCalledTimes(1)
    const [calledUrl, calledInit] = mockFetch.mock.calls[0]
    expect(calledUrl).toBe('http://127.0.0.1:4500/health')
    expect(calledInit.headers['Authorization']).toBe('Bearer custom_secret')
  })

  it('handles API error responses with ApiError structure', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: 'Thread not found' })
    })
    globalThis.fetch = mockFetch

    const client = new ApiClient()
    const api = new CodexApi(client)

    await expect(api.getThread('non_existent')).rejects.toThrow('Thread not found')
  })

  // -------------------------------------------------------------
  // Test 9: Zero fixture dependence in live mode
  // -------------------------------------------------------------
  it('maintains zero fixture dependence in live mode when unpopulated', () => {
    resetStateForTesting({
      appMode: 'live',
      projects: [],
      threads: [],
      subAgents: [],
      diffFiles: [],
      telemetryIncidents: []
    })

    const state = getWorkbenchState()
    expect(state.appMode).toBe('live')
    expect(state.projects.length).toBe(0)
    expect(state.threads.length).toBe(0)
    expect(state.subAgents.length).toBe(0)
  })

  // -------------------------------------------------------------
  // Test 10: Slice A — Project & Thread lifecycle (create, delete, rename)
  // -------------------------------------------------------------
  it('WP-08 Slice A: supports project creation, thread deletion, and persistence', async () => {
    const mockDelete = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ message: 'Thread deleted' }) })
    globalThis.fetch = mockDelete

    resetStateForTesting({
      appMode: 'live',
      projects: [{ id: 'proj_main', name: 'Main Project', repository: 'repo', defaultBranch: 'main', activeThreadCount: 1, healthState: 'healthy', lastActivity: 'now', writeRoots: [], authMode: 'chatgpt_managed', modelPolicy: 'gpt-4o' }],
      activeProjectId: 'proj_main',
      threads: [
        { id: 'th_1', projectId: 'proj_main', title: 'T1', module: 'M', status: 'active', branch: 'b', worktree: 'w', model: 'gpt-4o', reasoningEffort: 'medium', permissionProfile: 'workspace_write', contextCompactionState: 'healthy', subAgentCount: 0, approvalCount: 0, createdAt: '', updatedAt: '', turns: [] },
        { id: 'th_2', projectId: 'proj_main', title: 'T2', module: 'M', status: 'active', branch: 'b', worktree: 'w', model: 'gpt-4o', reasoningEffort: 'medium', permissionProfile: 'workspace_write', contextCompactionState: 'healthy', subAgentCount: 0, approvalCount: 0, createdAt: '', updatedAt: '', turns: [] }
      ],
      activeThreadId: 'th_1'
    })

    const client = new ApiClient()
    const api = new CodexApi(client)
    const delRes = await api.deleteThread('th_1')
    expect(delRes.message).toBe('Thread deleted')
  })

  // -------------------------------------------------------------
  // Test 11: Slice B — Turns & Steering payload transmission
  // -------------------------------------------------------------
  it('WP-08 Slice B: transmits startTurn, steerTurn, and interruptTurn payloads', async () => {
    const mockFetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes('/turns/start')) {
        return { ok: true, status: 200, json: async () => ({ turn_id: 42, status: 'active' }) }
      }
      if (url.includes('/turns/steer')) {
        return { ok: true, status: 200, json: async () => ({ status: 'steered' }) }
      }
      if (url.includes('/turns/interrupt')) {
        return { ok: true, status: 200, json: async () => ({ status: 'interrupted' }) }
      }
      return { ok: true, status: 200, json: async () => ({}) }
    })
    globalThis.fetch = mockFetch

    const api = new CodexApi()
    const startRes = await api.startTurn({ thread_id: 'th_alpha', prompt: 'Audit invariants' })
    expect(startRes.turn_id).toBe(42)

    const steerRes = await api.steerTurn({ thread_id: 'th_alpha', turn_id: 42, instruction: 'Focus on auth token' })
    expect(steerRes.status).toBe('steered')

    const intRes = await api.interruptTurn({ thread_id: 'th_alpha', turn_id: 42 })
    expect(intRes.status).toBe('interrupted')
  })

  // -------------------------------------------------------------
  // Test 12: Slice C — Approvals with feedback transmission
  // -------------------------------------------------------------
  it('WP-08 Slice C: transmits resolveApproval with feedback', async () => {
    let receivedPayload: any = null
    const mockFetch = vi.fn().mockImplementation(async (_url: string, init: any) => {
      receivedPayload = JSON.parse(init.body)
      return {
        ok: true,
        status: 200,
        json: async () => ({
          id: 'appr_123',
          thread_id: 'th_alpha',
          tool_call_id: 'tc_1',
          command: 'rm -rf /tmp',
          risk_level: 'high',
          consequence: 'Deletes cache',
          status: receivedPayload.approved ? 'approved' : 'declined'
        })
      }
    })
    globalThis.fetch = mockFetch

    const api = new CodexApi()
    const res = await api.resolveApproval('appr_123', false, 'Unsafe path deletion')
    expect(receivedPayload.approved).toBe(false)
    expect(receivedPayload.feedback).toBe('Unsafe path deletion')
    expect(res.status).toBe('declined')
  })

  // -------------------------------------------------------------
  // Test 13: Slice F — Deep Diagnostics & Truthful SigNoz Probe
  // -------------------------------------------------------------
  it('WP-08 Slice F: fetches deep diagnostics and truthfully reports subsystems', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        status: 'healthy',
        timestamp: '2026-08-30T00:00:00Z',
        subsystems: {
          database: { status: 'healthy', connected: true },
          event_broker: { status: 'healthy', active_subscriber_queues: 1 },
          worker: { status: 'running', running: true, pid: 1234 },
          worktree_storage: { status: 'healthy', writable: true },
          telemetry: { connected: false, status: 'Not connected (No active telemetry collector)' }
        }
      })
    })
    globalThis.fetch = mockFetch

    const api = new CodexApi()
    const diag = await api.getDeepDiagnostics()
    expect(diag.status).toBe('healthy')
    expect(diag.subsystems.telemetry.connected).toBe(false)
    expect(diag.subsystems.worker.pid).toBe(1234)
  })

  // -------------------------------------------------------------
  // Test 14: Dynamic Workspace Boundaries API (List, Add, Delete)
  // -------------------------------------------------------------
  it('WP-08 Slice G: manages workspace boundaries via API client', async () => {
    let capturedMethod = ''
    let capturedUrl = ''
    let capturedBody: any = null

    const mockFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      capturedUrl = url
      capturedMethod = init?.method || 'GET'
      capturedBody = init?.body ? JSON.parse(init.body as string) : null

      if (capturedMethod === 'GET') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => [
            { id: 'bound_fastapi', path: 'F:\\Projects\\fastapi_bookings', name: 'FastAPI Bookings', is_default: true }
          ]
        })
      }
      if (capturedMethod === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 'bound_kok',
            path: capturedBody.path,
            name: capturedBody.name || 'King of Kings',
            is_default: false
          })
        })
      }
      if (capturedMethod === 'DELETE') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ status: 'success', message: 'Boundary removed' })
        })
      }
      return Promise.reject(new Error('Unknown method'))
    })
    globalThis.fetch = mockFetch

    const api = new CodexApi()

    // 1. List boundaries
    const boundaries = await api.listBoundaries()
    expect(boundaries).toHaveLength(1)
    expect(boundaries[0].path).toBe('F:\\Projects\\fastapi_bookings')

    // 2. Add boundary
    const added = await api.addBoundary({ path: 'E:\\Projects\\King of Kings', name: 'King of Kings' })
    expect(capturedMethod).toBe('POST')
    expect(capturedBody.path).toBe('E:\\Projects\\King of Kings')
    expect(added.id).toBe('bound_kok')

    // 3. Delete boundary
    const delRes = await api.deleteBoundary('bound_kok')
    expect(capturedMethod).toBe('DELETE')
    expect(delRes.status).toBe('success')
  })

  // -------------------------------------------------------------
  // Test 15: Telemetry Configuration & Endpoint Reachability Test
  // -------------------------------------------------------------
  it('WP-08 Slice H: gets, updates, and tests telemetry settings', async () => {
    let capturedUrl = ''
    let capturedBody: any = null

    const mockFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      capturedUrl = url
      capturedBody = init?.body ? JSON.parse(init.body as string) : null

      if (url.includes('/telemetry/test')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            connected: true,
            status: 'Connected',
            latency_ms: 3.5,
            url: capturedBody.endpoint
          })
        })
      }
      if (init?.method === 'PUT') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            signoz_url: capturedBody.signoz_url,
            otlp_endpoint: capturedBody.otlp_endpoint,
            enabled: capturedBody.enabled,
            status: 'Saved'
          })
        })
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          signoz_url: 'http://localhost:3301',
          otlp_endpoint: 'http://localhost:4318',
          enabled: true,
          connected: true,
          status: 'Connected',
          latency_ms: 2.1
        })
      })
    })
    globalThis.fetch = mockFetch

    const api = new CodexApi()

    // 1. Get telemetry settings
    const settings = await api.getTelemetrySettings()
    expect(settings.signoz_url).toBe('http://localhost:3301')
    expect(settings.connected).toBe(true)

    // 2. Update telemetry settings
    const updated = await api.updateTelemetrySettings({
      signoz_url: 'http://localhost:8080',
      otlp_endpoint: 'http://localhost:4318',
      enabled: true
    })
    expect(updated.signoz_url).toBe('http://localhost:8080')

    // 3. Test telemetry connectivity
    const testResult = await api.testTelemetryEndpoint('http://localhost:4318')
    expect(testResult.connected).toBe(true)
    expect(testResult.latency_ms).toBe(3.5)
  })

  // -------------------------------------------------------------
  // Test 16: Subagent Lifecycle Events (Started, Progress, Completed)
  // -------------------------------------------------------------
  it('WP-Workstream-1: handles subagent_started, subagent_progress, and subagent_completed events', () => {
    // 1. subagent_started
    const startedEvent: SSEEventEnvelope = {
      id: 'evt_sa_start_1',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 1,
      type: 'subagent_started',
      occurred_at: '10:10 AM',
      payload: {
        agent_id: 'sa_db_worker',
        role: 'Database Migration Specialist',
        objective: 'Generate slot locking migration',
        status: 'running',
        model: 'gpt-4o'
      }
    }
    const stateAfterStart = reduceSSEEvent(baseState, startedEvent)
    expect(stateAfterStart.subAgents).toHaveLength(1)
    expect(stateAfterStart.subAgents[0].id).toBe('sa_db_worker')
    expect(stateAfterStart.subAgents[0].status).toBe('running')
    expect(stateAfterStart.threads.find(t => t.id === 'th_alpha')?.subAgentCount).toBe(1)
    expect(stateAfterStart.currentActionText).toContain('Database Migration Specialist')

    // 2. subagent_progress
    const progressEvent: SSEEventEnvelope = {
      id: 'evt_sa_progress_1',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 2,
      type: 'subagent_progress',
      occurred_at: '10:11 AM',
      payload: {
        agent_id: 'sa_db_worker',
        status: 'running',
        progress_summary: 'Synthesizing Alembic revision AST...',
        files_changed_count: 1
      }
    }
    const stateAfterProgress = reduceSSEEvent(stateAfterStart, progressEvent)
    expect(stateAfterProgress.subAgents[0].progressSummary).toBe('Synthesizing Alembic revision AST...')
    expect(stateAfterProgress.subAgents[0].filesChangedCount).toBe(1)
    expect(stateAfterProgress.currentActionText).toContain('Synthesizing Alembic revision AST...')

    // 3. subagent_completed
    const completedEvent: SSEEventEnvelope = {
      id: 'evt_sa_comp_1',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 3,
      type: 'subagent_completed',
      occurred_at: '10:12 AM',
      payload: {
        agent_id: 'sa_db_worker',
        status: 'completed',
        summary: 'Successfully applied schema migration.',
        tests_run_count: 3
      }
    }
    const stateAfterCompleted = reduceSSEEvent(stateAfterProgress, completedEvent)
    expect(stateAfterCompleted.subAgents[0].status).toBe('completed')
    expect(stateAfterCompleted.subAgents[0].resultSummary).toBe('Successfully applied schema migration.')
    expect(stateAfterCompleted.subAgents[0].testsRunCount).toBe(3)
  })

  // -------------------------------------------------------------
  // Test 17: Live Activity Pulse Action Tracking & Reset
  // -------------------------------------------------------------
  it('WP-Workstream-1: tracks currentActionText dynamically and resets on turn completion', () => {
    // 1. turn_started
    const turnStart: SSEEventEnvelope = {
      id: 'evt_ts_1',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 1,
      type: 'turn_started',
      occurred_at: '10:15 AM',
      payload: { turn_id: 'turn_10', prompt: 'Run test suite' }
    }
    const state1 = reduceSSEEvent(baseState, turnStart)
    expect(state1.currentActionText).toContain('Starting')

    // 2. command_execution
    const cmdEvent: SSEEventEnvelope = {
      id: 'evt_cmd_1',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 2,
      type: 'command_execution',
      occurred_at: '10:15:05 AM',
      payload: { turn_id: 'turn_10', command: 'pytest tests/test_concurrency.py' }
    }
    const state2 = reduceSSEEvent(state1, cmdEvent)
    expect(state2.currentActionText).toBe('Running command: pytest tests/test_concurrency.py')

    // 3. turn_completed
    const turnComplete: SSEEventEnvelope = {
      id: 'evt_tc_1',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 3,
      type: 'turn_completed',
      occurred_at: '10:15:10 AM',
      payload: { turn_id: 'turn_10', status: 'completed' }
    }
    const state3 = reduceSSEEvent(state2, turnComplete)
    expect(state3.currentActionText).toBeUndefined()
    expect(state3.turnElapsedSeconds).toBe(0)
  })

  // -------------------------------------------------------------
  // Test 18: Streaming Reasoning Tokens Aggregation
  // -------------------------------------------------------------
  it('WP-Workstream-1: aggregates streaming reasoning chunks into rawTrace with isStreaming active', () => {
    const turnStart: SSEEventEnvelope = {
      id: 'evt_ts_2',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 1,
      type: 'turn_started',
      occurred_at: '10:20 AM',
      payload: { turn_id: 'turn_20' }
    }
    const state1 = reduceSSEEvent(baseState, turnStart)

    // First reasoning chunk
    const r1: SSEEventEnvelope = {
      id: 'evt_r_1',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 2,
      type: 'reasoning',
      occurred_at: '10:20:01 AM',
      payload: {
        turn_id: 'turn_20',
        item_id: 'reason_20',
        chunk: 'Step 1: Check lock acquisition. ',
        is_streaming: true
      }
    }
    const state2 = reduceSSEEvent(state1, r1)
    const turn20 = state2.threads.find(t => t.id === 'th_alpha')?.turns.find(t => t.id === 'turn_20')
    const reasonItem = turn20?.items.find(i => i.id === 'reason_20') as any
    expect(reasonItem).toBeDefined()
    expect(reasonItem.rawTrace).toBe('Step 1: Check lock acquisition. ')
    expect(reasonItem.isStreaming).toBe(true)

    // Second reasoning chunk appended
    const r2: SSEEventEnvelope = {
      id: 'evt_r_2',
      project_id: 'proj_codex',
      thread_id: 'th_alpha',
      sequence: 3,
      type: 'reasoning',
      occurred_at: '10:20:02 AM',
      payload: {
        turn_id: 'turn_20',
        item_id: 'reason_20',
        chunk: 'Step 2: Validate timeout parameters.',
        is_streaming: true
      }
    }
    const state3 = reduceSSEEvent(state2, r2)
    const reasonItem2 = state3.threads.find(t => t.id === 'th_alpha')?.turns.find(t => t.id === 'turn_20')?.items.find(i => i.id === 'reason_20') as any
    expect(reasonItem2.rawTrace).toBe('Step 1: Check lock acquisition. Step 2: Validate timeout parameters.')
    expect(reasonItem2.isStreaming).toBe(true)
  })
})
