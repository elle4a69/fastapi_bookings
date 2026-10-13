// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'
// @ts-expect-error Node's file-system types are intentionally not part of the app build.
import { readFileSync } from 'node:fs'
// @ts-expect-error Node's URL types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url'

import {
  createAgentActivityLog,
  AGENT_ACTIVITY_LOGS_STORAGE_KEY,
  MAX_PERSISTED_AGENT_ACTIVITY_LOGS,
  loadPersistedAgentActivityLogs,
  savePersistedAgentActivityLogs,
  clearPersistedAgentActivityLogs,
} from './realtime-protocol.ts'

const consoleSource = readFileSync(
  fileURLToPath(new URL('./components/LiveAgentActivityConsole.tsx', import.meta.url)),
  'utf8',
)
const contextSource = readFileSync(
  fileURLToPath(new URL('./business-assistant-context.tsx', import.meta.url)),
  'utf8',
)
const pageSource = readFileSync(
  fileURLToPath(new URL('./index.tsx', import.meta.url)),
  'utf8',
)
const telemetrySource = readFileSync(
  fileURLToPath(new URL('../telemetry.tsx', import.meta.url)),
  'utf8',
)
const layoutSource = readFileSync(
  fileURLToPath(new URL('../../../layouts/admin-layout.tsx', import.meta.url)),
  'utf8',
)
const gptLiveSource = readFileSync(
  fileURLToPath(new URL('../gpt-live/use-gpt-live.ts', import.meta.url)),
  'utf8',
)

test('createAgentActivityLog creates valid structured activity logs with explicit agent and model labels', () => {
  const log = createAgentActivityLog('TOOL_EXEC', 'Tool Dispatch: stage_fields', {
    details: '{"service_id": 1}',
    payload: { service_id: 1 },
    status: 'running',
  })

  assert.ok(log.id.startsWith('act-'))
  assert.equal(log.type, 'TOOL_EXEC')
  assert.equal(log.status, 'running')
  assert.equal(log.title, 'Tool Dispatch: stage_fields')
  assert.equal(log.details, '{"service_id": 1}')
  assert.deepEqual(log.payload, { service_id: 1 })
  assert.equal(log.agentLabel, 'FastAPI Backend (Tool Runner)')
  assert.equal(log.modelName, 'python-tools')
  assert.ok(!Number.isNaN(Date.parse(log.timestamp)))

  // Voice transcript defaults to GPT-Live-1
  const voiceLog = createAgentActivityLog('VOICE_IN', 'Voice Transcription')
  assert.equal(voiceLog.agentLabel, 'GPT-Live-1 (Voice Front)')
  assert.equal(voiceLog.modelName, 'gpt-live-1')

  // Delegation defaults to GPT-5.6-Terra
  const delegationLog = createAgentActivityLog('DELEGATION', 'Model Delegation')
  assert.equal(delegationLog.agentLabel, 'GPT-5.6-Terra (Reasoning Engine)')
  assert.equal(delegationLog.modelName, 'gpt-5.6-terra')

  // Custom overrides respected
  const customLog = createAgentActivityLog('REASONING_OUT', 'Custom Turn', {
    agentLabel: 'GPT-4o (Text Assistant)',
    modelName: 'gpt-4o',
  })
  assert.equal(customLog.agentLabel, 'GPT-4o (Text Assistant)')
  assert.equal(customLog.modelName, 'gpt-4o')
})

const realtimeProtocolSource = readFileSync(
  fileURLToPath(new URL('./realtime-protocol.ts', import.meta.url)),
  'utf8',
)

test('localStorage persistence utilities adhere to key and bound constraints', () => {
  assert.equal(AGENT_ACTIVITY_LOGS_STORAGE_KEY, 'fastapi_bookings_agent_activity_logs')
  assert.equal(MAX_PERSISTED_AGENT_ACTIVITY_LOGS, 300)
  assert.equal(typeof loadPersistedAgentActivityLogs, 'function')
  assert.equal(typeof savePersistedAgentActivityLogs, 'function')
  assert.equal(typeof clearPersistedAgentActivityLogs, 'function')

  // Realtime protocol defines key and Context + Console wire into persistence
  assert.match(realtimeProtocolSource, /fastapi_bookings_agent_activity_logs/)
  assert.match(contextSource, /loadPersistedAgentActivityLogs/)
  assert.match(contextSource, /savePersistedAgentActivityLogs/)
  assert.match(contextSource, /clearPersistedAgentActivityLogs/)
  assert.match(consoleSource, /loadPersistedAgentActivityLogs/)
  assert.match(consoleSource, /clearPersistedAgentActivityLogs/)
})

test('LiveAgentActivityConsole component provides high-density terminal styling and badge types', () => {
  // 1. Live badge and terminal styling
  assert.match(consoleSource, /● LIVE/)
  assert.match(consoleSource, /bg-zinc-950/)
  assert.match(consoleSource, /font-mono/)

  // 2. Badge categories
  assert.match(consoleSource, /VOICE_IN/)
  assert.match(consoleSource, /DELEGATION/)
  assert.match(consoleSource, /TOOL_EXEC/)
  assert.match(consoleSource, /TOOL_RESULT/)
  assert.match(consoleSource, /REASONING/)
  assert.match(consoleSource, /VOICE_OUT/)
  assert.match(consoleSource, /ERROR/)

  // 3. Terminal actions (auto-scroll, payload inspector, clear, copy trace)
  assert.match(consoleSource, /autoScroll/)
  assert.match(consoleSource, /handleCopyTrace/)
  assert.match(consoleSource, /toggleExpand/)
  assert.match(consoleSource, /handleClear/)
  assert.match(consoleSource, /JSON\.stringify/)
})

test('BusinessAssistantPage integrates LiveAgentActivityConsole and Telemetry link', () => {
  assert.match(pageSource, /LiveAgentActivityConsole/)
  assert.match(pageSource, /data-testid="toggle-live-console-button"/)
  assert.match(pageSource, /data-testid="nav-telemetry-console-button"/)
  assert.match(pageSource, /\/admin\/telemetry/)
})

test('TelemetryPage embeds LiveAgentActivityConsole for live real-time observation', () => {
  assert.match(telemetrySource, /LiveAgentActivityConsole/)
  assert.match(telemetrySource, /Live Agent Activity & WebRTC Console/)
})

test('AdminLayout mounts AgentSidebar globally across admin routes without exclusion', () => {
  assert.match(layoutSource, /<AgentSidebar/)
  assert.doesNotMatch(
    layoutSource,
    /!location\.pathname\.startsWith\(['"]\/admin\/business-assistant['"]\) && \(\s*<AgentSidebar/,
  )
})

test('useGPTLive captures realtime events and emits structured activity logs with clean stop and response.create', () => {
  assert.match(gptLiveSource, /emitActivityLog\('VOICE_IN'/)
  assert.match(gptLiveSource, /emitActivityLog\('USER_INPUT'/)
  assert.match(gptLiveSource, /emitActivityLog\('DELEGATION'/)
  assert.match(gptLiveSource, /emitActivityLog\('TOOL_EXEC'/)
  assert.match(gptLiveSource, /emitActivityLog\('TOOL_RESULT'/)
  assert.match(gptLiveSource, /emitActivityLog\('REASONING_OUT'/)
  assert.match(gptLiveSource, /emitActivityLog\('VOICE_OUT'/)
  assert.match(gptLiveSource, /emitActivityLog\('ERROR'/)
  assert.match(gptLiveSource, /live-agent-activity/)

  // stopVoice cleans up hardware and guards against false positive finalisation error
  assert.match(gptLiveSource, /closingRef\.current = true/)
  assert.match(gptLiveSource, /getTracks\(\)\.forEach\(\(track\) => track\.stop\(\)\)/)
  assert.match(gptLiveSource, /if \(closedRef\.current \|\| closingRef\.current\) return/)

  // WebRTC data channel returns tool outputs and sends response.create
  assert.match(gptLiveSource, /formatRealtimeToolOutput/)
  assert.match(gptLiveSource, /dataChannel\.send\(\s*JSON\.stringify\(\{\s*type:\s*'response\.create'/)
})

test('LiveAgentActivityConsole prominently displays distinct agent and model identity badges', () => {
  assert.match(consoleSource, /getAgentBadgeConfig/)
  assert.match(consoleSource, /GPT-Live-1/)
  assert.match(consoleSource, /GPT-5\.6-Terra/)
  assert.match(consoleSource, /FastAPI Backend/)
  assert.match(consoleSource, /GPT-4o/)
  assert.match(consoleSource, /LiveKit Cloud/)
  assert.match(consoleSource, /\[\{agentBadge\.tag\}\]/)
})

test('agent activity logs deduplicate IDs and protect against React key collision', () => {
  const mockStorage: Record<string, string> = {}
  const originalWindow = (globalThis as unknown as { window: unknown }).window
  const mockLocalStorage: Storage = {
    getItem: (key: string) => mockStorage[key] ?? null,
    setItem: (key: string, val: string) => {
      mockStorage[key] = val
    },
    removeItem: (key: string) => {
      delete mockStorage[key]
    },
    clear: () => {
      for (const k of Object.keys(mockStorage)) delete mockStorage[k]
    },
    key: (index: number) => Object.keys(mockStorage)[index] ?? null,
    get length() {
      return Object.keys(mockStorage).length
    },
  }
  ;(globalThis as unknown as { window: unknown }).window = {
    localStorage: mockLocalStorage,
  }

  try {
    const duplicateLogs = [
      createAgentActivityLog('USER_INPUT', 'Turn 1', { id: 'dup-1' }),
      createAgentActivityLog('USER_INPUT', 'Turn 1 duplicate', { id: 'dup-1' }),
      createAgentActivityLog('VOICE_OUT', 'Turn 2', { id: 'dup-2' }),
      createAgentActivityLog('VOICE_OUT', 'Turn 2 duplicate', { id: 'dup-2' }),
    ]
    // Raw corrupted localStorage injection with duplicate IDs
    mockStorage[AGENT_ACTIVITY_LOGS_STORAGE_KEY] = JSON.stringify(duplicateLogs)

    // loadPersistedAgentActivityLogs() should auto-migrate & sanitize localStorage on the fly
    const loaded = loadPersistedAgentActivityLogs()
    assert.equal(loaded.length, 2)
    assert.equal(loaded[0].id, 'dup-1')
    assert.equal(loaded[1].id, 'dup-2')

    // Verify localStorage was written back with cleaned deduplicated content
    const sanitizedRaw = JSON.parse(mockStorage[AGENT_ACTIVITY_LOGS_STORAGE_KEY]!)
    assert.equal(sanitizedRaw.length, 2)
    assert.equal(sanitizedRaw[0].id, 'dup-1')
    assert.equal(sanitizedRaw[1].id, 'dup-2')
  } finally {
    ;(globalThis as unknown as { window: unknown }).window = originalWindow
  }

  assert.match(contextSource, /if\s*\(prev\.some\(\(item\)\s*=>\s*item\.id\s*===\s*fullLog\.id\)\)\s*return prev/)
  assert.doesNotMatch(contextSource, /addEventListener\(['"]live-agent-activity['"]/)
  assert.match(consoleSource, /key=\{`\$\{log\.id\}-\$\{index\}`\}/)
  assert.match(consoleSource, /const seenIds = new Set<string>\(\)/)
})

