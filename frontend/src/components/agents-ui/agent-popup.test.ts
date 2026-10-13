// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'
// @ts-expect-error Node's file-system types are intentionally not part of the app build.
import { readFileSync } from 'node:fs'
// @ts-expect-error Node's URL types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url'

const popupSource = readFileSync(
  fileURLToPath(new URL('./agent-popup.tsx', import.meta.url)),
  'utf8',
)
const adminLayoutSource = readFileSync(
  fileURLToPath(new URL('../../layouts/admin-layout.tsx', import.meta.url)),
  'utf8',
)

test('AgentPopup conforms to LiveKit AgentPopup_01 spec with floating trigger and card', () => {
  // Verifies component name and export alias
  assert.match(popupSource, /export\s+function\s+AgentPopup\(/)
  assert.match(popupSource, /export\s+const\s+AgentPopup_01\s*=\s*AgentPopup/)

  // Verifies testids for automation and accessibility
  assert.match(popupSource, /data-testid="livekit-agent-popup"/)
  assert.match(popupSource, /data-testid="livekit-agent-popup-trigger"/)
  assert.match(popupSource, /data-testid="agent-popup-transcript"/)
  assert.match(popupSource, /data-testid="agent-popup-transport-badge"/)
})

test('AgentPopup includes 3-bar animated audio visualizer and mute controls', () => {
  assert.match(popupSource, /function\s+ThreeBarVisualizer/)
  assert.match(popupSource, /toggleMute/)
  assert.match(popupSource, /isMuted/)
  assert.match(popupSource, /switchAudioDevice/)
  assert.match(popupSource, /audioDevices/)
})

test('AgentPopup provides real camera and screen share media controls with clean release', () => {
  assert.match(popupSource, /navigator\.mediaDevices\.getUserMedia/)
  assert.match(popupSource, /navigator\.mediaDevices\.getDisplayMedia/)
  assert.match(popupSource, /cameraStreamRef\.current\.getTracks\(\)\.forEach/)
  assert.match(popupSource, /screenStreamRef\.current\.getTracks\(\)\.forEach/)
})

test('AgentPopup connects to BusinessAssistantContext lifecycle and supports typed turn input', () => {
  assert.match(popupSource, /useBusinessAssistant/)
  assert.match(popupSource, /startVoice/)
  assert.match(popupSource, /stopVoice/)
  assert.match(popupSource, /sendTurn/)
  assert.match(popupSource, /voiceCaptions/)
  assert.match(popupSource, /placeholder="Type something\.\.\."/)
})

test('AdminLayout mounts AgentPopup_01 and removes messy drawer, AgentSidebar and OnboardingStatusDock', () => {
  assert.match(adminLayoutSource, /AgentPopup_01/)
  assert.doesNotMatch(adminLayoutSource, /BusinessAssistantDrawer/)
  assert.doesNotMatch(adminLayoutSource, /MinimizedVoiceController/)
  assert.doesNotMatch(adminLayoutSource, /<AgentSidebar/)
  assert.doesNotMatch(adminLayoutSource, /<OnboardingStatusDock/)
})

test('AgentPopup consolidates UI Agent DOM automation and Voice controls seamlessly', () => {
  // Verifies integration with useAgent and useVoice hooks
  assert.match(popupSource, /useAgent/)
  assert.match(popupSource, /useVoice/)
  assert.match(popupSource, /VOICE_PROVIDERS/)
  assert.match(popupSource, /SLEEP_OPTIONS/)

  // Verifies wake-word hands-free controls
  assert.match(popupSource, /data-testid="wake-word-toggle"/)
  assert.match(popupSource, /data-testid="wake-word-input"/)
  assert.match(popupSource, /data-testid="wake-word-status"/)
  assert.match(popupSource, /data-testid="wake-word-indicator"/)

  // Verifies speaking voice selector dropdown
  assert.match(popupSource, /data-testid="voice-voice-select"/)

  // Verifies DOM automation speed adjustments
  assert.match(popupSource, /data-testid=\{`agent-speed-\$\{s\}`\}/)

  // Verifies auto-sleep options
  assert.match(popupSource, /data-testid=\{`auto-sleep-\$\{sec\}`\}/)

  // Verifies session reset control
  assert.match(popupSource, /data-testid="settings-new-session"/)
})

