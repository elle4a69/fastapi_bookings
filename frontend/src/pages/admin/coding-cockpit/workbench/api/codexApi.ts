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
  TelemetryTestResult,
  PluginCatalogResponse,
  PluginDetailResponse,
  PluginInstallResponse,
  SkillSearchResult,
  SkillDetail,
  SkillsStats,
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
    feedback?: string,
    scope: 'once' | 'session' = 'once'
  ): Promise<ToolApprovalResponse> {
    const payload: ResolveApprovalPayload = { approved, feedback, scope }
    return this.client.post<ToolApprovalResponse>(
      `/codex/governance/approvals/${approvalId}/resolve`,
      payload
    )
  }

  async resolveInteraction(
    requestId: string,
    action: 'accept' | 'decline' | 'cancel',
    response: Record<string, any>
  ): Promise<{ id: string; status: 'submitted' | 'declined'; action: string }> {
    return this.client.post(`/codex/governance/interactions/${encodeURIComponent(requestId)}/resolve`, {
      action,
      response,
    })
  }

  async listPlugins(): Promise<PluginCatalogResponse> {
    return this.client.get<PluginCatalogResponse>('/codex/plugins')
  }

  async readPlugin(pluginId: string): Promise<PluginDetailResponse> {
    return this.client.get<PluginDetailResponse>(`/codex/plugins/${encodeURIComponent(pluginId)}`)
  }

  async installPlugin(pluginId: string): Promise<PluginInstallResponse> {
    return this.client.post<PluginInstallResponse>(`/codex/plugins/${encodeURIComponent(pluginId)}/install`)
  }

  async getSkillsStats(): Promise<SkillsStats> {
    return this.client.get<SkillsStats>('/codex/skills/stats')
  }

  async searchSkills(query: string, topK: number = 12): Promise<{ results: SkillSearchResult[] }> {
    return this.client.get<{ results: SkillSearchResult[] }>('/codex/skills/search', { query, top_k: topK })
  }

  async readSkill(skillId: string): Promise<SkillDetail> {
    return this.client.get<SkillDetail>(`/codex/skills/${encodeURIComponent(skillId)}`)
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

  // EventSource SSE Stream Connection with Graceful Reconnection & Backoff
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
    let currentLastEventId = lastEventId || ''
    let retryCount = 0
    let reconnectTimer: any = null

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
          retryCount = 0
          return
        }

        const envelopeId = event.lastEventId || parsed.id || `evt_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`
        if (envelopeId) {
          currentLastEventId = envelopeId
        }

        const envelope: SSEEventEnvelope = {
          id: envelopeId,
          schema_version: parsed.schema_version || '1.0',
          project_id: parsed.project_id || projectId,
          thread_id: parsed.thread_id || threadId,
          sequence: typeof parsed.sequence === 'number' ? parsed.sequence : 0,
          type: resolvedType,
          occurred_at: parsed.occurred_at || new Date().toISOString(),
          payload: parsed.payload !== undefined ? parsed.payload : parsed
        }

        retryCount = 0
        onEvent(envelope)
      } catch (e) {
        onError?.(e)
      }
    }

    const scheduleReconnect = () => {
      if (closed || reconnectTimer) return
      const delay = Math.min(1000 * Math.pow(1.5, retryCount), 10000)
      retryCount++
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null
        if (!closed) {
          void openEventSource()
        }
      }, delay)
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
      if (closed) return
      try {
        let ticket = ''
        try {
          const res = await this.createThreadEventTicket(projectId, threadId)
          ticket = res.ticket
        } catch {
          // If ticket request fails, continue and let token fallback work
        }

        if (closed) return

        const tenant = this.client.getTenant()
        const params = new URLSearchParams()
        if (ticket) {
          params.set('sse_ticket', ticket)
        } else {
          const token = this.client.getToken()
          if (token) params.set('token', token)
        }
        if (tenant) params.set('tenant', tenant)
        if (currentLastEventId) params.set('last_event_id', currentLastEventId)

        const base = this.client.getBaseUrl().replace(/\/codex$/, '')
        const url = `${base}/codex/events/${encodedProj}/${encodedThread}?${params.toString()}`
        const es = new EventSource(url, { withCredentials: true })
        eventSource = es

        es.onopen = () => {
          retryCount = 0
        }

        es.onmessage = (event) => handleRawEvent(event)
        eventNames.forEach(name => {
          es.addEventListener(name, (event: Event) => handleRawEvent(event as MessageEvent, name))
        })
        es.onerror = (err) => {
          es.close()
          if (eventSource === es) eventSource = null
          onError?.(err)
          scheduleReconnect()
        }
      } catch (err) {
        onError?.(err)
        scheduleReconnect()
      }
    }

    void openEventSource()

    return () => {
      closed = true
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      eventSource?.close()
      eventSource = null
    }
  }
}

export const codexApi = new CodexApi(defaultApiClient)
