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

test('voice session is consolidated into unified voice interface while full page consumes context', () => {
  assert.match(contextSource, /useGPTLive/)
  assert.doesNotMatch(contextSource, /useRealtimeVoice/)
  assert.match(contextSource, /voiceCaptions/)

  assert.match(pageSource, /useBusinessAssistant\(\)/)
  assert.doesNotMatch(pageSource, /useGPTLive/)
  assert.doesNotMatch(pageSource, /data-testid="business-assistant-voice-start"/)
  assert.doesNotMatch(pageSource, /GPTLiveCaptionTimeline/)

  assert.match(conversationSource, /voiceCaptions/)
  assert.match(conversationSource, /GPTLiveCaptionTimeline/)
  assert.doesNotMatch(conversationSource, /realtime\/turns/)
})

test('context manages voice session lifecycle across scope and conversation transitions', () => {
  assert.match(contextSource, /previousUserKeyRef/)
  assert.match(contextSource, /stopVoice\(\)/)
})

test('GPT-Live coordinates active executor lease and dispatches UI automation RPC actions', () => {
  assert.match(gptLiveHookSource, /executorCoordinator\.claimActiveExecutor\(\)/)
  assert.match(gptLiveHookSource, /executorCoordinator\.releaseActiveExecutor\(\)/)
  assert.match(gptLiveHookSource, /parseRealtimeToolCalls\(event\)/)
  assert.match(gptLiveHookSource, /executeRpcAction\(/)
  assert.match(gptLiveHookSource, /assistant-rpc:action/)
  assert.match(gptLiveHookSource, /formatRealtimeToolOutput\(/)

  // Verify context passes onNavigate and onRpcReceipt to useGPTLive
  assert.match(contextSource, /const directVoice = useGPTLive\(\{[\s\S]*?onNavigate:[\s\S]*?onRpcReceipt:/)
})

test('GPT-Live handles OpenAI error events and posts telemetry to client-state endpoint', () => {
  assert.match(gptLiveHookSource, /if \(event\.type === 'error'\)/)
  assert.match(gptLiveHookSource, /console\.error\('\[GPT-Live Error\]', event\.error\)/)
  assert.match(gptLiveHookSource, /callbacksRef\.current\.onError\(errorMessage\)/)
  assert.match(gptLiveHookSource, /\/conversations\/\$\{activeConversationId\}\/client-state/)
  assert.match(gptLiveHookSource, /client_status:\s*'error'/)
  assert.match(gptLiveHookSource, /webrtc_state:\s*'direct_gpt_live'/)
})

test('GPT-Live prevents response_already_in_progress and avoids tool-response deadlock', () => {
  assert.match(gptLiveHookSource, /responseInProgressRef/)
  assert.match(gptLiveHookSource, /pendingResponseCreateRef/)
  assert.match(gptLiveHookSource, /if \(event\.type === 'response\.created'\)/)
  assert.match(gptLiveHookSource, /if \(event\.type === 'response\.done' \|\| event\.type === 'response\.cancelled'\)/)
  assert.match(gptLiveHookSource, /if \(pendingResponseCreateRef\.current && dataChannel\.readyState === 'open'\)/)
  assert.match(gptLiveHookSource, /150/)
})

test('GPT-Live does not pass session.modalities in session.update', () => {
  assert.doesNotMatch(gptLiveHookSource, /modalities:\s*\[/)
  assert.match(gptLiveHookSource, /input_audio_transcription:\s*\{/)
})

const xaiVoiceHookSource = readFileSync(
  fileURLToPath(new URL('./use-xai-grok-voice.ts', import.meta.url)),
  'utf8',
)

test('xAI Grok Voice coordinates active executor lease and dispatches UI automation RPC and backend tools', () => {
  assert.match(xaiVoiceHookSource, /executorCoordinator\.claimActiveExecutor\(\)/)
  assert.match(xaiVoiceHookSource, /executorCoordinator\.releaseActiveExecutor\(\)/)
  assert.match(xaiVoiceHookSource, /parseRealtimeToolCalls\(data\)/)
  assert.match(xaiVoiceHookSource, /executeRpcAction\(/)
  assert.match(xaiVoiceHookSource, /formatRealtimeToolOutput\(/)
  assert.match(xaiVoiceHookSource, /\/api\/admin\/business-assistant\/conversations\/\$\{activeConversationId\}\/realtime\/session/)
  assert.match(xaiVoiceHookSource, /\/api\/admin\/business-assistant\/conversations\/\$\{activeConversationId\}\/realtime\/tools/)
  assert.match(xaiVoiceHookSource, /ws\.send\(JSON\.stringify\(\{ type: 'response\.create' \}\)\)/)
})



