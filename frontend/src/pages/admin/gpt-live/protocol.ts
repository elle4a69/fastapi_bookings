export type GPTLiveSpeaker = 'user' | 'assistant'

export type GPTLiveCaption = {
  speaker: GPTLiveSpeaker
  startMs: number
  endMs: number
  text: string
}

type TranscriptEvent = {
  type?: unknown
  delta?: unknown
  start_ms?: unknown
  end_ms?: unknown
}

function isFiniteTimestamp(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

/**
 * Keep received text byte-for-byte as JavaScript text. Captions are grouped by
 * overlapping/contiguous session-time intervals, never by conversational turns.
 */
export function appendTranscriptDelta(
  captions: GPTLiveCaption[],
  event: TranscriptEvent,
): GPTLiveCaption[] {
  const speaker: GPTLiveSpeaker | null = event.type === 'session.input_transcript.delta'
    ? 'user'
    : event.type === 'session.output_transcript.delta'
      ? 'assistant'
      : null
  if (!speaker || typeof event.delta !== 'string' || !isFiniteTimestamp(event.start_ms) || !isFiniteTimestamp(event.end_ms)) {
    return captions
  }

  const incoming: GPTLiveCaption = {
    speaker,
    startMs: event.start_ms,
    endMs: event.end_ms,
    text: event.delta,
  }
  const last = captions.at(-1)
  if (last && last.speaker === incoming.speaker && incoming.startMs <= last.endMs) {
    return [
      ...captions.slice(0, -1),
      {
        ...last,
        endMs: Math.max(last.endMs, incoming.endMs),
        text: last.text + incoming.text,
      },
    ]
  }
  return [...captions, incoming]
}

export function formatCaptionInterval(startMs: number, endMs: number): string {
  return `${(startMs / 1000).toFixed(1)}–${(endMs / 1000).toFixed(1)}s`
}
