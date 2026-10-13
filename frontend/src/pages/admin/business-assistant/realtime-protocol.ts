export type RealtimeTranscriptState = 'pending' | 'completed' | 'failed'

export type RealtimeUserTranscript = {
  sourceId: string
  state: RealtimeTranscriptState
  transcript: string
}

export type RealtimeAssistantTranscript = {
  sourceId: string
  state: Exclude<RealtimeTranscriptState, 'pending'>
  transcript: string
}

export type CompletedRealtimeTurn = {
  user: { sourceId: string; transcript: string }
  assistant: { sourceId: string; transcript: string }
}

export type PairResult = {
  pairs: CompletedRealtimeTurn[]
  users: RealtimeUserTranscript[]
  assistants: RealtimeAssistantTranscript[]
  dropped: number
}

export type RealtimeToolCall = {
  callId: string
  name: string
  arguments: Record<string, unknown>
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

export function parseRealtimeUserTranscript(value: unknown): RealtimeUserTranscript | null {
  const event = asRecord(value)
  if (!event) return null

  const type = text(event.type)
  const sourceId = text(event.item_id) || text(event.event_id)
  if (!sourceId) return null

  if (type === 'input_audio_buffer.committed') {
    return { sourceId, state: 'pending', transcript: '' }
  }
  if (type === 'conversation.item.input_audio_transcription.failed') {
    return { sourceId, state: 'failed', transcript: '' }
  }
  if (type === 'conversation.item.input_audio_transcription.completed') {
    const transcript = text(event.transcript)
    return { sourceId, state: transcript ? 'completed' : 'failed', transcript }
  }
  return null
}

export function parseRealtimeAssistantTranscript(value: unknown): RealtimeAssistantTranscript | null {
  const event = asRecord(value)
  if (!event) return null

  const type = text(event.type)
  if (
    type === 'response.output_audio_transcript.done'
    || type === 'response.audio_transcript.done'
    || type === 'response.output_text.done'
  ) {
    const sourceId = text(event.response_id) || text(event.item_id) || text(event.event_id)
    const transcript = text(event.transcript) || text(event.text)
    return sourceId && transcript ? { sourceId, state: 'completed', transcript } : null
  }

  if (type === 'response.done') {
    const response = asRecord(event.response)
    const status = text(response?.status)
    const sourceId = text(response?.id) || text(event.event_id)
    if (sourceId && ['failed', 'cancelled', 'incomplete'].includes(status)) {
      return { sourceId, state: 'failed', transcript: '' }
    }
  }
  return null
}

function parseToolArguments(raw: unknown): Record<string, unknown> {
  if (asRecord(raw)) return raw as Record<string, unknown>
  const rawArgs = text(raw)
  if (!rawArgs) return {}
  try {
    return asRecord(JSON.parse(rawArgs)) ?? {}
  } catch {
    return {}
  }
}

// call_id -> function name, learned from response.output_item.added/done where the name lives.
const toolCallNameCache = new Map<string, string>()

export function resetRealtimeToolCallNameCache(): void {
  toolCallNameCache.clear()
}

function rememberFunctionItem(item: Record<string, unknown> | null): void {
  if (!item || text(item.type) !== 'function_call') return
  const callId = text(item.call_id)
  const name = text(item.name)
  if (callId && name) toolCallNameCache.set(callId, name)
}

export function parseRealtimeToolCalls(value: unknown): RealtimeToolCall[] {
  const event = asRecord(value)
  if (!event) return []
  const type = text(event.type)

  if (type === 'response.output_item.added') {
    rememberFunctionItem(asRecord(event.item))
    return []
  }

  if (type === 'response.function_call_arguments.done') {
    const callId = text(event.call_id)
    const name = text(event.name) || toolCallNameCache.get(callId) || ''
    return callId && name ? [{ callId, name, arguments: parseToolArguments(event.arguments) }] : []
  }

  if (type === 'response.output_item.done') {
    const item = asRecord(event.item)
    rememberFunctionItem(item)
    if (item && text(item.type) === 'function_call') {
      const callId = text(item.call_id)
      const name = text(item.name) || toolCallNameCache.get(callId) || ''
      if (callId && name) return [{ callId, name, arguments: parseToolArguments(item.arguments) }]
    }
    return []
  }

  if (type === 'response.done') {
    const output = asRecord(event.response)?.output
    if (!Array.isArray(output)) return []
    const calls: RealtimeToolCall[] = []
    for (const entry of output) {
      const item = asRecord(entry)
      if (!item || text(item.type) !== 'function_call') continue
      rememberFunctionItem(item)
      const callId = text(item.call_id)
      const name = text(item.name) || toolCallNameCache.get(callId) || ''
      if (callId && name) calls.push({ callId, name, arguments: parseToolArguments(item.arguments) })
    }
    return calls
  }

  return []
}

export function parseRealtimeToolCall(value: unknown): RealtimeToolCall | null {
  return parseRealtimeToolCalls(value)[0] ?? null
}

export function formatRealtimeToolOutput(callId: string, output: Record<string, unknown>): Record<string, unknown> {
  return {
    type: 'conversation.item.create',
    item: {
      type: 'function_call_output',
      call_id: callId,
      output: JSON.stringify(output),
    },
  }
}

export function formatRealtimeSessionUpdate(
  instructions: string,
  tools: Array<Record<string, unknown>>,
): Record<string, unknown> {
  return {
    type: 'session.update',
    session: {
      instructions,
      tools,
    },
  }
}

export function upsertRealtimeUserTranscript(
  current: RealtimeUserTranscript[],
  update: RealtimeUserTranscript,
): RealtimeUserTranscript[] {
  const index = current.findIndex((item) => item.sourceId === update.sourceId)
  if (index < 0) return [...current, update]
  if (current[index].state !== 'pending' && update.state === 'pending') return current
  return current.map((item, itemIndex) => (itemIndex === index ? update : item))
}

export function upsertRealtimeAssistantTranscript(
  current: RealtimeAssistantTranscript[],
  update: RealtimeAssistantTranscript,
): RealtimeAssistantTranscript[] {
  const index = current.findIndex((item) => item.sourceId === update.sourceId)
  if (index < 0) return [...current, update]
  if (current[index].state === 'completed' && update.state === 'failed') return current
  return current.map((item, itemIndex) => (itemIndex === index ? update : item))
}

export function pairReadyRealtimeTranscripts(
  users: RealtimeUserTranscript[],
  assistants: RealtimeAssistantTranscript[],
): PairResult {
  const remainingUsers = [...users]
  const remainingAssistants = [...assistants]
  const pairs: CompletedRealtimeTurn[] = []
  let dropped = 0

  while (remainingUsers.length > 0 && remainingAssistants.length > 0) {
    if (remainingUsers[0].state === 'pending') break
    const user = remainingUsers.shift()!
    const assistant = remainingAssistants.shift()!
    if (user.state !== 'completed' || assistant.state !== 'completed') {
      dropped += 1
      continue
    }
    pairs.push({
      user: { sourceId: user.sourceId, transcript: user.transcript },
      assistant: { sourceId: assistant.sourceId, transcript: assistant.transcript },
    })
  }

  return { pairs, users: remainingUsers, assistants: remainingAssistants, dropped }
}

export type AgentActivityType =
  | 'VOICE_IN'
  | 'USER_INPUT'
  | 'DELEGATION'
  | 'TOOL_EXEC'
  | 'TOOL_RESULT'
  | 'REASONING_OUT'
  | 'VOICE_OUT'
  | 'ERROR'

export type AgentActivityStatus = 'info' | 'running' | 'success' | 'error'

export type AgentActivityLog = {
  id: string
  timestamp: string
  type: AgentActivityType
  title: string
  details?: string
  payload?: unknown
  status: AgentActivityStatus
  agentLabel?: string
  modelName?: string
}

export const AGENT_ACTIVITY_LOGS_STORAGE_KEY = 'fastapi_bookings_agent_activity_logs'
export const MAX_PERSISTED_AGENT_ACTIVITY_LOGS = 300

export function loadPersistedAgentActivityLogs(): AgentActivityLog[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(AGENT_ACTIVITY_LOGS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      const seen = new Set<string>()
      const unique: AgentActivityLog[] = []
      let hadDuplicates = false
      for (const item of parsed) {
        if (item && typeof item === 'object' && typeof (item as AgentActivityLog).id === 'string') {
          const log = item as AgentActivityLog
          if (!seen.has(log.id)) {
            seen.add(log.id)
            unique.push(log)
          } else {
            hadDuplicates = true
          }
        }
      }
      const trimmed = unique.slice(-MAX_PERSISTED_AGENT_ACTIVITY_LOGS)
      // Auto-migrate & sanitize: immediately purge existing duplicate keys from localStorage on boot
      if (hadDuplicates || trimmed.length !== parsed.length) {
        try {
          window.localStorage.setItem(AGENT_ACTIVITY_LOGS_STORAGE_KEY, JSON.stringify(trimmed))
        } catch {
          // safely ignore quota or permission issues
        }
      }
      return trimmed
    }
  } catch {
    // safely ignore corrupted JSON
  }
  return []
}

export function savePersistedAgentActivityLogs(logs: AgentActivityLog[]): void {
  if (typeof window === 'undefined') return
  try {
    const seen = new Set<string>()
    const unique: AgentActivityLog[] = []
    for (const log of logs) {
      if (log?.id && !seen.has(log.id)) {
        seen.add(log.id)
        unique.push(log)
      }
    }
    const trimmed = unique.slice(-MAX_PERSISTED_AGENT_ACTIVITY_LOGS)
    window.localStorage.setItem(AGENT_ACTIVITY_LOGS_STORAGE_KEY, JSON.stringify(trimmed))
  } catch {
    // safely ignore quota or permission issues
  }
}

export function clearPersistedAgentActivityLogs(): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(AGENT_ACTIVITY_LOGS_STORAGE_KEY)
  } catch {
    // safely ignore
  }
}

export function createAgentActivityLog(
  type: AgentActivityType,
  title: string,
  options?: {
    details?: string
    payload?: unknown
    status?: AgentActivityStatus
    agentLabel?: string
    modelName?: string
    id?: string
    timestamp?: string
  },
): AgentActivityLog {
  let defaultAgentLabel = options?.agentLabel
  let defaultModelName = options?.modelName

  if (!defaultAgentLabel || !defaultModelName) {
    switch (type) {
      case 'VOICE_IN':
        defaultAgentLabel = defaultAgentLabel ?? 'GPT-Live-1 (Voice Front)'
        defaultModelName = defaultModelName ?? 'gpt-live-1'
        break
      case 'VOICE_OUT':
        defaultAgentLabel = defaultAgentLabel ?? 'GPT-Live-1 (Voice Front)'
        defaultModelName = defaultModelName ?? 'gpt-live-1'
        break
      case 'DELEGATION':
      case 'REASONING_OUT':
        defaultAgentLabel = defaultAgentLabel ?? 'GPT-5.6-Terra (Reasoning Engine)'
        defaultModelName = defaultModelName ?? 'gpt-5.6-terra'
        break
      case 'TOOL_EXEC':
      case 'TOOL_RESULT':
        defaultAgentLabel = defaultAgentLabel ?? 'FastAPI Backend (Tool Runner)'
        defaultModelName = defaultModelName ?? 'python-tools'
        break
      case 'USER_INPUT':
        defaultAgentLabel = defaultAgentLabel ?? 'User / Client Input'
        defaultModelName = defaultModelName ?? 'client'
        break
      case 'ERROR':
        defaultAgentLabel = defaultAgentLabel ?? 'System / Telemetry'
        defaultModelName = defaultModelName ?? 'error-boundary'
        break
    }
  }

  return {
    id: options?.id || `act-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    timestamp: options?.timestamp || new Date().toISOString(),
    type,
    title,
    details: options?.details,
    payload: options?.payload,
    status: options?.status ?? 'info',
    agentLabel: defaultAgentLabel,
    modelName: defaultModelName,
  }
}

export const MAX_CONSECUTIVE_TOOL_CALLS = 20

export function shouldResetTurnToolQuota(event: unknown): boolean {
  if (!event || typeof event !== 'object') return false
  const rec = event as Record<string, unknown>
  const type = typeof rec.type === 'string' ? rec.type : ''

  if (type === 'input_audio_buffer.speech_started') return true
  if (
    type === 'conversation.item.input_audio_transcription.completed' ||
    type === 'input_audio_transcription.completed'
  ) {
    return true
  }

  if (type === 'conversation.item.created') {
    const item = rec.item as Record<string, unknown> | undefined
    if (item && item.role === 'user') return true
  }

  if (type === 'response.cancelled') return true

  if (type === 'response.done') {
    const response = rec.response as Record<string, unknown> | undefined
    const output = Array.isArray(response?.output) ? response.output : []
    const hasFunctionCall = output.some(
      (item) => typeof item === 'object' && item !== null && (item as Record<string, unknown>).type === 'function_call',
    )
    if (!hasFunctionCall) return true
  }

  return false
}


