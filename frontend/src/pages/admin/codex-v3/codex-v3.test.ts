// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'
// @ts-expect-error Node's file-system types are intentionally not part of the app build.
import { readFileSync } from 'node:fs'
// @ts-expect-error Node's URL types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url'

const typesSource = readFileSync(
  fileURLToPath(new URL('./types.ts', import.meta.url)),
  'utf8',
)
const topBarSource = readFileSync(
  fileURLToPath(new URL('./components/navigation/TopBar.tsx', import.meta.url)),
  'utf8',
)
const activityRailSource = readFileSync(
  fileURLToPath(new URL('./components/navigation/ActivityRail.tsx', import.meta.url)),
  'utf8',
)
const bottomTabBarSource = readFileSync(
  fileURLToPath(new URL('./components/navigation/BottomTabBar.tsx', import.meta.url)),
  'utf8',
)
const voiceFabSource = readFileSync(
  fileURLToPath(new URL('./components/voice/VoiceFAB.tsx', import.meta.url)),
  'utf8',
)
const audioWaveformStripSource = readFileSync(
  fileURLToPath(new URL('./components/voice/AudioWaveformStrip.tsx', import.meta.url)),
  'utf8',
)
const voiceContextSource = readFileSync(
  fileURLToPath(new URL('./context/CodexVoiceContext.tsx', import.meta.url)),
  'utf8',
)
const layoutSource = readFileSync(
  fileURLToPath(new URL('./CodexV3Layout.tsx', import.meta.url)),
  'utf8',
)

test('types.ts defines required CodexView, MobileTab, VoiceState, ToolStatus, SubagentActivity, and FilePatch', () => {
  assert.match(typesSource, /export type CodexView = 'tickets' \| 'coding' \| 'planning' \| 'signals'/)
  assert.match(typesSource, /export type MobileTab = 'workspace' \| 'stream'/)
  assert.match(typesSource, /export type VoiceState = 'idle' \| 'connecting' \| 'listening' \| 'speaking' \| 'thinking' \| 'error'/)
  assert.match(typesSource, /export type ToolStatus = 'pending' \| 'running' \| 'completed' \| 'failed'/)
  assert.match(typesSource, /export interface SubagentActivity \{/)
  assert.match(typesSource, /id:\s*string/)
  assert.match(typesSource, /role:\s*string/)
  assert.match(typesSource, /task:\s*string/)
  assert.match(typesSource, /status:\s*'running' \| 'done' \| 'failed'/)
  assert.match(typesSource, /elapsedSec:\s*number/)
  assert.match(typesSource, /export interface FilePatch \{/)
  assert.match(typesSource, /filePath:\s*string/)
  assert.match(typesSource, /additions:\s*number/)
  assert.match(typesSource, /deletions:\s*number/)
  assert.match(typesSource, /diffHunks:\s*string\[\]/)
  assert.match(typesSource, /status:\s*'pending' \| 'accepted' \| 'rejected'/)
})

test('TopBar provides minimal 44px height, project branding, active branch, and live voice pill', () => {
  assert.match(topBarSource, /h-\[44px\]/)
  assert.match(topBarSource, /min-h-\[44px\]/)
  assert.match(topBarSource, /activeBranch/)
  assert.match(topBarSource, /projectName/)
  assert.match(topBarSource, /\(\(o\)\) LIVE/)
  assert.match(topBarSource, /useCodexVoice/)
})

test('ActivityRail provides slim 52px desktop rail with tooltips, indicators, and status badges', () => {
  assert.match(activityRailSource, /w-\[52px\]/)
  assert.match(activityRailSource, /hidden lg:flex/)
  assert.match(activityRailSource, /Tooltip/)
  assert.match(activityRailSource, /tickets/)
  assert.match(activityRailSource, /coding/)
  assert.match(activityRailSource, /planning/)
  assert.match(activityRailSource, /signals/)
})

test('BottomTabBar provides 5-item thumb-zone bar (<640px) with safe-area padding and 44px tap targets', () => {
  assert.match(bottomTabBarSource, /sm:hidden/)
  assert.match(bottomTabBarSource, /pb-safe/)
  assert.match(bottomTabBarSource, /grid-cols-5/)
  assert.match(bottomTabBarSource, /min-h-\[44px\]/)
  assert.match(bottomTabBarSource, /min-w-\[44px\]/)
  assert.match(bottomTabBarSource, /VoiceFAB/)
})

test('VoiceFAB provides 54px elevated button with dynamic halo rings', () => {
  assert.match(voiceFabSource, /w-\[54px\]/)
  assert.match(voiceFabSource, /h-\[54px\]/)
  assert.match(voiceFabSource, /ring-emerald-500/)
  assert.match(voiceFabSource, /ring-purple-500/)
  assert.match(voiceFabSource, /ring-blue-500/)
  assert.match(voiceFabSource, /useCodexVoice/)
})

test('AudioWaveformStrip provides 24px-28px real-time waveform with animated volume bars, latency, and End Call', () => {
  assert.match(audioWaveformStripSource, /h-\[28px\]/)
  assert.match(audioWaveformStripSource, /latencyMs/)
  assert.match(audioWaveformStripSource, /stopVoice/)
  assert.match(audioWaveformStripSource, /audioLevel/)
})

test('CodexVoiceContext connects directly to useRealtimeVoice and exposes voiceState, toggleVoice, transcriptDelta, and audioLevel', () => {
  assert.match(voiceContextSource, /from '\.\.\/\.\.\/business-assistant\/use-realtime-voice'/)
  assert.match(voiceContextSource, /useRealtimeVoice/)
  assert.match(voiceContextSource, /voiceState/)
  assert.match(voiceContextSource, /toggleVoice/)
  assert.match(voiceContextSource, /transcriptDelta/)
  assert.match(voiceContextSource, /audioLevel/)
  assert.match(voiceContextSource, /latencyMs/)
})

test('CodexV3Layout orchestrates TopBar, BottomTabBar, ActivityRail, segmented control, and AudioWaveformStrip', () => {
  assert.match(layoutSource, /TopBar/)
  assert.match(layoutSource, /BottomTabBar/)
  assert.match(layoutSource, /ActivityRail/)
  assert.match(layoutSource, /AudioWaveformStrip/)
  assert.match(layoutSource, /data-testid="tab-workspace"/)
  assert.match(layoutSource, /data-testid="tab-stream"/)
  assert.match(layoutSource, /CodexVoiceProvider/)
})
