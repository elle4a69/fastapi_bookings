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

export function parseRealtimeToolCall(value: unknown): RealtimeToolCall | null {
  const event = asRecord(value)
  if (!event) return null

  const type = text(event.type)
  if (type === 'response.function_call_arguments.done') {
    const callId = text(event.call_id)
    const name = text(event.name)
    const rawArgs = text(event.arguments)
    let parsedArgs: Record<string, unknown> = {}
    if (rawArgs) {
      try {
        const parsed = JSON.parse(rawArgs)
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          parsedArgs = parsed as Record<string, unknown>
        }
      } catch {
        parsedArgs = {}
      }
    }
    if (callId && name) {
      return { callId, name, arguments: parsedArgs }
    }
  }

  return null
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
