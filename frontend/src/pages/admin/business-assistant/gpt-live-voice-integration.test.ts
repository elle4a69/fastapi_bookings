// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'
// @ts-expect-error Node's file-system types are intentionally not part of the app build.
import { readFileSync } from 'node:fs'
// @ts-expect-error Node's URL types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url'

const contextSource = readFileSync(
  fileURLToPath(new URL('./business-assistant-context.tsx', import.meta.url)),
  'utf8',
)
const pageSource = readFileSync(
  fileURLToPath(new URL('./index.tsx', import.meta.url)),
  'utf8',
)
const conversationSource = readFileSync(
  fileURLToPath(new URL('./conversation.tsx', import.meta.url)),
  'utf8',
)
const gptLiveHookSource = readFileSync(
  fileURLToPath(new URL('../gpt-live/use-gpt-live.ts', import.meta.url)),
  'utf8',
)

test('drawer and full page share GPT-Live voice with session-local timed captions', () => {
  assert.match(contextSource, /useGPTLive/)
  assert.doesNotMatch(contextSource, /useRealtimeVoice/)
  assert.match(contextSource, /voiceCaptions/)

  assert.match(pageSource, /useGPTLive/)
  assert.doesNotMatch(pageSource, /useRealtimeVoice/)
  assert.match(pageSource, /GPTLiveCaptionTimeline/)

  assert.match(conversationSource, /voiceCaptions/)
  assert.match(conversationSource, /GPTLiveCaptionTimeline/)
  assert.doesNotMatch(conversationSource, /realtime\/turns/)
})

test('GPT-Live startup ignores a microphone or provider result after its connection was closed', () => {
  assert.match(gptLiveHookSource, /connectionAttemptRef/)
  assert.match(gptLiveHookSource, /peerConnection\.signalingState !== 'closed'/)
  assert.match(gptLiveHookSource, /if \(!isCurrentAttempt\(\)\) \{\s*microphone\.getTracks\(\)/)
})

test('GPT-Live waits for the final ICE-gathered local SDP before session creation', () => {
  assert.match(gptLiveHookSource, /waitForIceGatheringComplete\(peerConnection\)/)
  assert.match(gptLiveHookSource, /peerConnection\.localDescription\?\.sdp/)
  assert.match(gptLiveHookSource, /\{ sdp: offerSdp \}/)
})

test('changing conversation stops the current voice session without stopping a newly connecting one', () => {
  assert.match(pageSource, /previousConversationIdRef/)
  assert.match(pageSource, /stopVoiceRef\.current\(\)/)
  assert.doesNotMatch(pageSource, /\[activeConversationId, stopVoice\]/)
})
