// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'
// @ts-expect-error Node's file-system types are intentionally not part of the app build.
import { readFileSync } from 'node:fs'
// @ts-expect-error Node's URL types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url'

const liveKitHookSource = readFileSync(
  fileURLToPath(new URL('./use-livekit-voice.ts', import.meta.url)),
  'utf8',
)
const contextSource = readFileSync(
  fileURLToPath(new URL('./business-assistant-context.tsx', import.meta.url)),
  'utf8',
)
const conversationSource = readFileSync(
  fileURLToPath(new URL('./conversation.tsx', import.meta.url)),
  'utf8',
)

test('useLiveKitVoice connects to room and manages audio track subscription', () => {
  // Verifies livekit-client imports
  assert.match(liveKitHookSource, /import\s*\{[^}]*Room[^}]*\}\s*from\s*'livekit-client'/)
  assert.match(liveKitHookSource, /RoomEvent\.TrackSubscribed/)
  assert.match(liveKitHookSource, /RoomEvent\.TrackUnsubscribed/)
  assert.match(liveKitHookSource, /Track\.Kind\.Audio/)

  // Remote audio track attached to document
  assert.match(liveKitHookSource, /track\.attach\(\)/)
  assert.match(liveKitHookSource, /track\.detach\(\)/)
  assert.match(liveKitHookSource, /audioElement\.autoplay = true/)

  // Unified voice session endpoint
  assert.match(
    liveKitHookSource,
    /\/api\/admin\/business-assistant\/voice\/conversations\/\$\{activeConversationId\}\/session/,
  )
})

test('useLiveKitVoice decodes raw caption data packets and updates timeline', () => {
  assert.match(liveKitHookSource, /RoomEvent\.DataReceived/)
  assert.match(liveKitHookSource, /new TextDecoder\(\)\.decode\(payload\)/)
  assert.match(liveKitHookSource, /data\.type === 'session\.input_transcript\.delta'/)
  assert.match(liveKitHookSource, /data\.type === 'session\.output_transcript\.delta'/)
  assert.match(liveKitHookSource, /appendTranscriptDelta\(captionsRef\.current, data\)/)
})

test('useLiveKitVoice enforces race condition protection and lifecycle isolation', () => {
  // Connection attempt guard prevents late connects from publishing to closed rooms
  assert.match(liveKitHookSource, /connectionAttemptRef\.current = connectionAttempt/)
  assert.match(liveKitHookSource, /if \(!isCurrentAttempt\(\)\)/)
  assert.match(liveKitHookSource, /setMicrophoneEnabled\(true\)/)
  assert.match(liveKitHookSource, /room\.disconnect\(\)/)
})

test('useLiveKitVoice provides device selection and microphone mute controls', () => {
  assert.match(liveKitHookSource, /toggleMute/)
  assert.match(liveKitHookSource, /switchAudioDevice/)
  assert.match(liveKitHookSource, /room\.switchActiveDevice\('audioinput', deviceId\)/)
  assert.match(liveKitHookSource, /navigator\.mediaDevices\.enumerateDevices/)
})

test('business assistant context exposes LiveKit controls and queries backend transport selector', () => {
  assert.match(contextSource, /useLiveKitVoice/)
  assert.match(contextSource, /useGPTLive/)
  assert.match(contextSource, /isMuted/)
  assert.match(contextSource, /toggleMute/)
  assert.match(contextSource, /audioDevices/)
  assert.match(contextSource, /switchAudioDevice/)
  assert.match(contextSource, /\/api\/admin\/business-assistant\/voice\/transport/)
})

test('conversation view renders accessible mute, mic selector, and transport badge', () => {
  assert.match(conversationSource, /data-testid="voice-mute-button"/)
  assert.match(conversationSource, /data-testid="voice-end-call-button"/)
  assert.match(conversationSource, /data-testid="voice-device-select"/)
  assert.match(conversationSource, /MicOff/)
  assert.match(conversationSource, /transport === 'livekit_gpt_live'/)
})
