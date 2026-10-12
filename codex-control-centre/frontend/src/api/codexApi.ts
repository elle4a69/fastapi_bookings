import { ApiClient, defaultApiClient } from './client'
import type {
  SSEEventEnvelope,
  ThreadResponse,
  CreateThreadPayload,
  UpdateThreadPayload,
  TurnStartPayload,
  TurnSteerPayload,
  TurnInterruptPayload,
  ToolApprovalResponse,
  ResolveApprovalPayload,
  CreateWorktreePayload,
  WorktreeResponse,
  SubAgentResponse,
  DeepDiagnosticsResponse,
  WorkspaceBoundary,
  TelemetrySettings,
  TelemetryTestResult
} from '../types/workbench'

export class CodexApi {
  private client: ApiClient

  constructor(client: ApiClient = defaultApiClient) {
    this.client = client
  }

  getClient(): ApiClient {
    return this.client
  }

  // Health & Diagnostics
  async getHealth(): Promise<{ status: string; timestamp: string }> {
    return this.client.get<{ status: string; timestamp: string }>('/health')
  }

  async getDeepDiagnostics(): Promise<DeepDiagnosticsResponse> {
    return this.client.get<DeepDiagnosticsResponse>('/codex/diagnostics/deep')
  }

  // Projects Management
  async listProjects(): Promise<any[]> {
    return this.client.get<any[]>('/codex/projects')
  }

  async createProject(payload: { name: string; repo_path: string; id?: string; default_branch?: string }): Promise<any> {
    return this.client.post<any>('/codex/projects', payload)
  }

  async getProject(projectId: string): Promise<any> {
    return this.client.get<any>(`/codex/projects/${projectId}`)
  }

  async getProjectFiles(projectId: string, subpath?: string): Promise<any[]> {
    const params = subpath ? { subpath } : undefined
    return this.client.get<any[]>(`/codex/projects/${projectId}/files`, params)
  }

  // Workspace Boundaries Management
  async listBoundaries(): Promise<WorkspaceBoundary[]> {
    return this.client.get<WorkspaceBoundary[]>('/codex/settings/boundaries')
  }

  async addBoundary(payload: { path: string; name?: string }): Promise<WorkspaceBoundary> {
    return this.client.post<WorkspaceBoundary>('/codex/settings/boundaries', payload)
  }

  async deleteBoundary(idOrPath: string): Promise<{ status: string; message: string }> {
    return this.client.delete<{ status: string; message: string }>(`/codex/settings/boundaries/${encodeURIComponent(idOrPath)}`)
  }

  // Telemetry Settings Management
  async getTelemetrySettings(): Promise<TelemetrySettings> {
    return this.client.get<TelemetrySettings>('/codex/settings/telemetry')
  }

  async updateTelemetrySettings(payload: { signoz_url: string; otlp_endpoint: string; enabled: boolean }): Promise<TelemetrySettings> {
    return this.client.put<TelemetrySettings>('/codex/settings/telemetry', payload)
  }

  async testTelemetryEndpoint(endpoint: string): Promise<TelemetryTestResult> {
    return this.client.post<TelemetryTestResult>('/codex/settings/telemetry/test', { endpoint })
  }

  // Threads Management
  async listThreads(): Promise<ThreadResponse[]> {
    return this.client.get<ThreadResponse[]>('/codex/threads')
  }

  async createThread(payload: CreateThreadPayload): Promise<ThreadResponse> {
    return this.client.post<ThreadResponse>('/codex/threads', payload)
  }

  async getThread(id: string): Promise<ThreadResponse> {
    return this.client.get<ThreadResponse>(`/codex/threads/${id}`)
  }

  async updateThread(id: string, payload: UpdateThreadPayload): Promise<ThreadResponse> {
    return this.client.patch<ThreadResponse>(`/codex/threads/${id}`, payload)
  }

  async deleteThread(id: string): Promise<{ message: string }> {
    return this.client.delete<{ message: string }>(`/codex/threads/${id}`)
  }

  // Turns Execution & Control
  async startTurn(payload: TurnStartPayload): Promise<{ turn_id: number; status: string }> {
    return this.client.post<{ turn_id: number; status: string }>('/codex/turns/start', payload)
  }

  async steerTurn(payload: TurnSteerPayload): Promise<{ status: string }> {
    return this.client.post<{ status: string }>('/codex/turns/steer', payload)
  }

  async interruptTurn(payload: TurnInterruptPayload): Promise<{ status: string }> {
    return this.client.post<{ status: string }>('/codex/turns/interrupt', payload)
  }

  // Governance & Approvals
  async listPendingApprovals(threadId?: string): Promise<ToolApprovalResponse[]> {
    const params = threadId ? { thread_id: threadId } : undefined
    return this.client.get<ToolApprovalResponse[]>('/codex/governance/approvals/pending', params)
  }

  async resolveApproval(
    approvalId: string,
    approved: boolean,
    feedback?: string
  ): Promise<ToolApprovalResponse> {
    const payload: ResolveApprovalPayload = { approved, feedback }
    return this.client.post<ToolApprovalResponse>(
      `/codex/governance/approvals/${approvalId}/resolve`,
      payload
    )
  }

  // Worktrees
  async listWorktrees(repoPath: string = '/'): Promise<WorktreeResponse[] | any> {
    return this.client.get<WorktreeResponse[] | any>('/codex/worktrees', { repo_path: repoPath })
  }

  async createWorktree(payload: CreateWorktreePayload): Promise<any> {
    return this.client.post<any>('/codex/worktrees/create', payload)
  }

  async deleteWorktree(name: string, repoPath: string = '/', force: boolean = false): Promise<any> {
    return this.client.delete<any>(`/codex/worktrees/${encodeURIComponent(name)}`, {
      repo_path: repoPath,
      force
    })
  }

  // Subagents
  async listSubagents(threadId: string): Promise<SubAgentResponse[]> {
    return this.client.get<SubAgentResponse[]>(`/codex/governance/subagents/${threadId}`)
  }

  async steerSubagent(id: string, instruction: string): Promise<any> {
    return this.client.post<any>(`/codex/governance/subagents/${id}/steer`, { instruction })
  }

  async stopSubagent(id: string): Promise<SubAgentResponse> {
    return this.client.post<SubAgentResponse>(`/codex/governance/subagents/${id}/stop`)
  }

  async createThreadEventTicket(projectId: string, threadId: string): Promise<{ ticket: string }> {
    return this.client.post<{ ticket: string }>('/codex/events/ticket', {
      project_id: projectId,
      thread_id: threadId,
    })
  }

  // EventSource SSE Stream Connection
  connectThreadEvents(
    projectId: string,
    threadId: string,
    onEvent: (event: SSEEventEnvelope) => void,
    onError?: (err: any) => void,
    lastEventId?: string
  ): () => void {
    if (typeof EventSource === 'undefined') {
      return () => {}
    }

    const encodedProj = encodeURIComponent(projectId)
    const encodedThread = encodeURIComponent(threadId)
    let eventSource: EventSource | null = null
    let closed = false

    const handleRawEvent = (event: MessageEvent, eventType?: string) => {
      try {
        let parsed: any = {}
        if (typeof event.data === 'string' && event.data.trim()) {
          try {
            parsed = JSON.parse(event.data)
          } catch {
            parsed = { raw: event.data }
          }
        } else if (typeof event.data === 'object' && event.data !== null) {
          parsed = event.data
        }

        const resolvedType = (eventType && eventType !== 'message') ? eventType : (parsed.type || 'message')

        // Skip internal keepalive pings
        if (resolvedType === 'ping') {
          return
        }

        const envelope: SSEEventEnvelope = {
          id: event.lastEventId || parsed.id || `evt_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
          schema_version: parsed.schema_version || '1.0',
          project_id: parsed.project_id || projectId,
          thread_id: parsed.thread_id || threadId,
          sequence: typeof parsed.sequence === 'number' ? parsed.sequence : 0,
          type: resolvedType,
          occurred_at: parsed.occurred_at || new Date().toISOString(),
          payload: parsed.payload !== undefined ? parsed.payload : parsed
        }

        onEvent(envelope)
      } catch (e) {
        onError?.(e)
      }
    }

    const eventNames = [
      'turn_started',
      'turn_completed',
      'turn_interrupted',
      'turn_failed',
      'agent_message',
      'reasoning_summary',
      'plan',
      'command_execution',
      'file_change',
      'file_read',
      'tool_call',
      'web_research',
      'test_run',
      'approval_requested',
      'approval_resolved',
      'compaction_notice',
      'subagent_activity',
      'subagent_status',
      'user_input_request',
      'warning',
      'failure'
    ]

    const openEventSource = async () => {
      try {
        // EventSource cannot send Authorization headers. A scoped, one-time
        // ticket keeps the long-lived URL free of the bearer credential.
        const { ticket } = await this.createThreadEventTicket(projectId, threadId)
        if (closed) return
        const params = new URLSearchParams({ sse_ticket: ticket })
        if (lastEventId) params.set('last_event_id', lastEventId)
        const url = `${this.client.getBaseUrl()}/codex/events/${encodedProj}/${encodedThread}?${params.toString()}`
        const es = new EventSource(url, { withCredentials: true })
        eventSource = es
        es.onmessage = (event) => handleRawEvent(event)
        eventNames.forEach(name => {
          es.addEventListener(name, (event: Event) => handleRawEvent(event as MessageEvent, name))
        })
        es.onerror = (err) => {
          es.close()
          if (eventSource === es) eventSource = null
          onError?.(err)
        }
      } catch (err) {
        onError?.(err)
      }
    }

    void openEventSource()

    return () => {
      closed = true
      eventSource?.close()
      eventSource = null
    }
  }
}

export const codexApi = new CodexApi(defaultApiClient)
