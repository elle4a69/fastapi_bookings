// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'

import {
  pairReadyRealtimeTranscripts,
  parseRealtimeAssistantTranscript,
  parseRealtimeUserTranscript,
  upsertRealtimeUserTranscript,
} from './realtime-voice-protocol.ts'

test('realtime protocol keeps a pending user turn ahead of later terminal events', () => {
  const pending = parseRealtimeUserTranscript({ type: 'input_audio_buffer.committed', item_id: 'user-a' })
  const completed = parseRealtimeUserTranscript({
    type: 'conversation.item.input_audio_transcription.completed',
    item_id: 'user-b',
    transcript: 'Second turn',
  })
  const assistant = parseRealtimeAssistantTranscript({
    type: 'response.output_audio_transcript.done',
    response_id: 'assistant-b',
    transcript: 'Second response',
  })

  assert.ok(pending)
  assert.ok(completed)
  assert.ok(assistant)
  const result = pairReadyRealtimeTranscripts([pending!, completed!], [assistant!])
  assert.deepEqual(result.pairs, [])
  assert.equal(result.users[0].sourceId, 'user-a')
})

test('realtime protocol pairs only completed transcript heads and discards terminal failures', () => {
  const result = pairReadyRealtimeTranscripts(
    [
      { sourceId: 'failed-user', state: 'failed', transcript: '' },
      { sourceId: 'good-user', state: 'completed', transcript: 'Hello' },
    ],
    [
      { sourceId: 'failed-assistant', state: 'failed', transcript: '' },
      { sourceId: 'good-assistant', state: 'completed', transcript: 'Hi' },
    ],
  )

  assert.equal(result.dropped, 1)
  assert.deepEqual(result.pairs, [{
    user: { sourceId: 'good-user', transcript: 'Hello' },
    assistant: { sourceId: 'good-assistant', transcript: 'Hi' },
  }])
})

test('realtime protocol never lets a late pending event replace a completed transcript', () => {
  const complete = parseRealtimeUserTranscript({
    type: 'conversation.item.input_audio_transcription.completed',
    item_id: 'user-a',
    transcript: 'Saved turn',
  })
  const pending = parseRealtimeUserTranscript({ type: 'input_audio_buffer.committed', item_id: 'user-a' })
  assert.ok(complete)
  assert.ok(pending)
  const result = upsertRealtimeUserTranscript([complete!], pending!)
  assert.deepEqual(result, [complete])
})
