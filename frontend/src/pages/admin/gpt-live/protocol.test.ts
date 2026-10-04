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
