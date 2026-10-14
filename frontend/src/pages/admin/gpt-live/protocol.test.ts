// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'

import { appendTranscriptDelta, formatCaptionInterval } from './protocol.ts'

test('GPT-Live captions preserve exact deltas and group by overlapping session intervals', () => {
  const first = appendTranscriptDelta([], {
    type: 'session.input_transcript.delta', delta: 'I need', start_ms: 1_000, end_ms: 1_200,
  })
  const grouped = appendTranscriptDelta(first, {
    type: 'session.input_transcript.delta', delta: ' help', start_ms: 1_200, end_ms: 1_450,
  })
  assert.deepEqual(grouped, [{ speaker: 'user', startMs: 1_000, endMs: 1_450, text: 'I need help' }])
})

test('GPT-Live captions keep speakers and separated timestamp intervals independent', () => {
  const user = appendTranscriptDelta([], {
    type: 'session.input_transcript.delta', delta: 'Hello ', start_ms: 10, end_ms: 30,
  })
  const output = appendTranscriptDelta(user, {
    type: 'session.output_transcript.delta', delta: 'Hi', start_ms: 20, end_ms: 45,
  })
  assert.equal(output.length, 2)
  assert.equal(output[0].text, 'Hello ')
  assert.equal(formatCaptionInterval(1_000, 1_200), '1.0–1.2s')
})

test('GPT-Live captions accumulate streaming deltas without splitting words into separate bubbles', () => {
  // Test sequential streaming words with normal speech pauses (gap of 50-100ms)
  let captions = appendTranscriptDelta([], {
    type: 'response.audio_transcript.delta', delta: 'The', start_ms: 100, end_ms: 250,
  })
  captions = appendTranscriptDelta(captions, {
    type: 'response.audio_transcript.delta', delta: ' dashboard', start_ms: 300, end_ms: 550,
  })
  captions = appendTranscriptDelta(captions, {
    type: 'response.audio_transcript.delta', delta: ' is', start_ms: 600, end_ms: 700,
  })
  captions = appendTranscriptDelta(captions, {
    type: 'response.audio_transcript.delta', delta: ' ready', start_ms: 750, end_ms: 900,
  })

  // All 4 words must accumulate into 1 single caption turn, not 4 separate bubbles
  assert.equal(captions.length, 1)
  assert.equal(captions[0].speaker, 'assistant')
  assert.equal(captions[0].text, 'The dashboard is ready')
  assert.equal(captions[0].endMs, 900)
})

test('GPT-Live captions update full transcript on completion events', () => {
  let captions = appendTranscriptDelta([], {
    type: 'input_audio_transcription.completed', transcript: 'Can you show me my services?',
  })
  assert.equal(captions.length, 1)
  assert.equal(captions[0].speaker, 'user')
  assert.equal(captions[0].text, 'Can you show me my services?')
})
