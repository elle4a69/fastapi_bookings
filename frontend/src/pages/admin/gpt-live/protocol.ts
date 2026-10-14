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
  text?: unknown
  output_text?: unknown
  transcript?: unknown
  start_ms?: unknown
  end_ms?: unknown
  speaker?: unknown
  is_final?: unknown
  segment_id?: unknown
}

function isFiniteTimestamp(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

/**
 * Keep received text byte-for-byte as JavaScript text. Captions are grouped by
 * speaker and conversational turns/session-time intervals without splitting
 * streaming deltas or words across lines.
 */
export function appendTranscriptDelta(
  captions: GPTLiveCaption[],
  event: TranscriptEvent,
): GPTLiveCaption[] {
  let speaker: GPTLiveSpeaker | null = null
  if (event.speaker === 'user' || event.speaker === 'assistant') {
    speaker = event.speaker
  } else if (
    event.type === 'session.input_transcript.delta' ||
    event.type === 'conversation.item.input_audio_transcription.completed' ||
    event.type === 'input_audio_transcription.completed' ||
    event.type === 'input_transcript.delta'
  ) {
    speaker = 'user'
  } else if (
    event.type === 'session.output_transcript.delta' ||
    event.type === 'response.audio_transcript.delta' ||
    event.type === 'response.output_audio_transcript.delta' ||
    event.type === 'response.audio_transcript.done' ||
    event.type === 'response.output_audio_transcript.done' ||
    event.type === 'response.text.delta' ||
    event.type === 'response.output_text.delta' ||
    event.type === 'response.text.done' ||
    event.type === 'response.output_text.done' ||
    event.type === 'output_transcript.delta'
  ) {
    speaker = 'assistant'
  }

  const rawText =
    typeof event.delta === 'string'
      ? event.delta
      : typeof event.text === 'string'
        ? event.text
        : typeof event.output_text === 'string'
          ? event.output_text
          : typeof event.transcript === 'string'
            ? event.transcript
            : null

  if (!speaker || rawText === null || rawText === '') {
    return captions
  }

  const startMs = isFiniteTimestamp(event.start_ms)
    ? event.start_ms
    : captions.at(-1)?.endMs ?? Date.now()
  const endMs = isFiniteTimestamp(event.end_ms)
    ? Math.max(startMs, event.end_ms)
    : startMs + 100

  const incoming: GPTLiveCaption = {
    speaker,
    startMs,
    endMs,
    text: rawText,
  }

  const last = captions.at(-1)
  // Merge into in-progress caption for the same speaker if within a normal conversational turn (gap <= 3000ms)
  if (
    last &&
    last.speaker === incoming.speaker &&
    incoming.startMs <= last.endMs + 3000
  ) {
    const isCompletedFullTranscript =
      event.type === 'conversation.item.input_audio_transcription.completed' ||
      event.type === 'input_audio_transcription.completed' ||
      event.type === 'response.audio_transcript.done' ||
      event.type === 'response.output_audio_transcript.done' ||
      event.type === 'response.text.done' ||
      event.type === 'response.output_text.done'

    const nextText = isCompletedFullTranscript
      ? incoming.text
      : last.text + incoming.text

    return [
      ...captions.slice(0, -1),
      {
        ...last,
        endMs: Math.max(last.endMs, incoming.endMs),
        text: nextText,
      },
    ]
  }

  return [...captions, incoming]
}

export function formatCaptionInterval(startMs: number, endMs: number): string {
  return `${(startMs / 1000).toFixed(1)}–${(endMs / 1000).toFixed(1)}s`
}
