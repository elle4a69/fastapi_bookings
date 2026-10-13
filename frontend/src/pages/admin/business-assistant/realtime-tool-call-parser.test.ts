// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'
import {
  parseRealtimeToolCall,
  parseRealtimeToolCalls,
  resetRealtimeToolCallNameCache,
} from './realtime-protocol.ts'

test('parses arguments.done when the name is present', () => {
  resetRealtimeToolCallNameCache()
  assert.deepEqual(
    parseRealtimeToolCall({
      type: 'response.function_call_arguments.done',
      call_id: 'c1',
      name: 'navigate_route',
      arguments: '{"route":"/admin"}',
    }),
    { callId: 'c1', name: 'navigate_route', arguments: { route: '/admin' } },
  )
})

test('resolves the name from output_item.added when arguments.done omits it', () => {
  resetRealtimeToolCallNameCache()
  assert.deepEqual(
    parseRealtimeToolCalls({
      type: 'response.output_item.added',
      item: { type: 'function_call', call_id: 'c2', name: 'stage_fields' },
    }),
    [],
  )
  assert.deepEqual(
    parseRealtimeToolCall({
      type: 'response.function_call_arguments.done',
      call_id: 'c2',
      arguments: '{"fields":{"a":1}}',
    }),
    { callId: 'c2', name: 'stage_fields', arguments: { fields: { a: 1 } } },
  )
})

test('parses response.output_item.done function_call items', () => {
  resetRealtimeToolCallNameCache()
  assert.deepEqual(
    parseRealtimeToolCall({
      type: 'response.output_item.done',
      item: { type: 'function_call', call_id: 'c3', name: 'save_form', arguments: '{}' },
    }),
    { callId: 'c3', name: 'save_form', arguments: {} },
  )
})

test('parses function_call items inside response.done and ignores messages', () => {
  resetRealtimeToolCallNameCache()
  assert.deepEqual(
    parseRealtimeToolCalls({
      type: 'response.done',
      response: {
        output: [
          { type: 'message' },
          { type: 'function_call', call_id: 'c4', name: 'validate_form', arguments: '{"form_id":"x"}' },
        ],
      },
    }),
    [{ callId: 'c4', name: 'validate_form', arguments: { form_id: 'x' } }],
  )
})

test('MAX_CONSECUTIVE_TOOL_CALLS allows multi-step onboarding sequences up to 20 rounds', async () => {
  const { MAX_CONSECUTIVE_TOOL_CALLS } = await import('./realtime-protocol.ts')
  assert.equal(MAX_CONSECUTIVE_TOOL_CALLS, 20)
})

test('shouldResetTurnToolQuota identifies turn boundaries and spoken completion events', async () => {
  const { shouldResetTurnToolQuota } = await import('./realtime-protocol.ts')

  // Speech started from user mic
  assert.equal(shouldResetTurnToolQuota({ type: 'input_audio_buffer.speech_started' }), true)

  // Transcription completed
  assert.equal(shouldResetTurnToolQuota({ type: 'input_audio_transcription.completed' }), true)
  assert.equal(shouldResetTurnToolQuota({ type: 'conversation.item.input_audio_transcription.completed' }), true)

  // User message item created
  assert.equal(shouldResetTurnToolQuota({ type: 'conversation.item.created', item: { role: 'user' } }), true)
  assert.equal(shouldResetTurnToolQuota({ type: 'conversation.item.created', item: { role: 'assistant' } }), false)

  // Response cancelled
  assert.equal(shouldResetTurnToolQuota({ type: 'response.cancelled' }), true)

  // Response done WITH function_call -> intermediate tool response, quota should NOT reset
  assert.equal(
    shouldResetTurnToolQuota({
      type: 'response.done',
      response: {
        output: [{ type: 'function_call', name: 'stage_fields' }],
      },
    }),
    false,
  )

  // Response done WITHOUT function_call -> spoken answer to user, turn finished, quota resets!
  assert.equal(
    shouldResetTurnToolQuota({
      type: 'response.done',
      response: {
        output: [{ type: 'message', content: [{ type: 'audio' }] }],
      },
    }),
    true,
  )
})
