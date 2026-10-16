import type { StreamEvent } from './types'

export type ResidentStreamState =
  | { status: 'connecting' }
  | { status: 'live' }
  | { status: 'retrying'; attempt: number; retryInMs: number }
  | { status: 'error'; message: string }

type StreamFetch = (
  endpoint: string,
  options: RequestInit,
) => Promise<Response>

type ResidentEventStreamOptions = {
  onEvent: (event: StreamEvent) => void
  onState: (state: ResidentStreamState) => void
  fetchStream: StreamFetch
  maxReconnects?: number
  baseDelayMs?: number
  schedule?: typeof setTimeout
  cancelSchedule?: typeof clearTimeout
}

const STREAM_ENDPOINT = '/api/admin/resident-agent/events'

function parseFrames(buffer: string): {
  events: StreamEvent[]
  remainder: string
} {
  const frames = buffer.split(/\r?\n\r?\n/)
  const remainder = frames.pop() || ''
  const events: StreamEvent[] = []

  for (const frame of frames) {
    const data = frame
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
      .join('\n')
    if (!data) continue
    try {
      events.push(JSON.parse(data) as StreamEvent)
    } catch {
      // Ignore malformed frames without logging potentially sensitive payloads.
    }
  }
  return { events, remainder }
}

export function connectResidentEventStream(
  options: ResidentEventStreamOptions,
): () => void {
  const fetchStream = options.fetchStream
  const maxReconnects = Math.max(0, options.maxReconnects ?? 5)
  const baseDelayMs = Math.max(0, options.baseDelayMs ?? 500)
  const schedule = options.schedule || setTimeout
  const cancelSchedule = options.cancelSchedule || clearTimeout

  let stopped = false
  let terminal = false
  let active = false
  let reconnects = 0
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let controller: AbortController | null = null
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null

  const scheduleReconnect = () => {
    if (stopped || terminal || retryTimer !== null) return
    if (reconnects >= maxReconnects) {
      terminal = true
      options.onState({
        status: 'error',
        message: 'Live event stream disconnected after repeated retries.',
      })
      return
    }

    const retryInMs = Math.min(
      baseDelayMs * Math.pow(2, reconnects),
      10_000,
    )
    reconnects += 1
    options.onState({
      status: 'retrying',
      attempt: reconnects,
      retryInMs,
    })
    const beginRetry = () => {
      if (stopped || terminal) {
        retryTimer = null
        return
      }
      if (active) {
        retryTimer = schedule(beginRetry, 0)
        return
      }
      retryTimer = null
      void connect()
    }
    retryTimer = schedule(beginRetry, retryInMs)
  }

  const connect = async () => {
    if (stopped || terminal || active) return
    active = true
    controller = new AbortController()
    if (reconnects === 0) {
      options.onState({ status: 'connecting' })
    }

    try {
      const response = await fetchStream(STREAM_ENDPOINT, {
        headers: { Accept: 'text/event-stream' },
        signal: controller.signal,
      })
      if (response.status === 401 || response.status === 403) {
        terminal = true
        options.onState({
          status: 'error',
          message: 'Live event stream authorization was rejected.',
        })
        return
      }
      if (!response.ok || !response.body) {
        scheduleReconnect()
        return
      }

      options.onState({ status: 'live' })
      reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (!stopped && !terminal) {
        const { value, done } = await reader.read()
        if (done) {
          scheduleReconnect()
          break
        }
        buffer += decoder.decode(value, { stream: true })
        const parsed = parseFrames(buffer)
        buffer = parsed.remainder
        for (const event of parsed.events) {
          reconnects = 0
          options.onEvent(event)
        }
      }
    } catch {
      if (!stopped && !controller.signal.aborted) {
        scheduleReconnect()
      }
    } finally {
      active = false
      reader = null
    }
  }

  void connect()

  return () => {
    stopped = true
    controller?.abort()
    void reader?.cancel()
    if (retryTimer !== null) {
      cancelSchedule(retryTimer)
      retryTimer = null
    }
  }
}
