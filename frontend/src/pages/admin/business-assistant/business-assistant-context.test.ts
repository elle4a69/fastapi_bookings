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

test('business assistant context refreshes messages on tool completions, rpc receipts, and client snapshots', () => {
  // 1. postClientSnapshot refreshes messages
  assert.match(contextSource, /postClientSnapshot[\s\S]*?finally\s*\{[\s\S]*?loadMessages\(activeConversationId\)/)

  // 2. onRpcReceipt refreshes messages
  assert.match(contextSource, /onRpcReceipt:\s*\(receipt\)\s*=>\s*\{[\s\S]*?loadMessages\(activeConversationId\)/)

  // 3. onToolCallComplete refreshes messages
  assert.match(contextSource, /onToolCallComplete:\s*\(\)\s*=>\s*\{[\s\S]*?loadMessages\(activeConversationId\)/)

  // 4. custom event listeners for tool and rpc completions
  assert.match(contextSource, /assistant-rpc:action/)
  assert.match(contextSource, /assistant-tool:complete/)
})

test('business assistant context provides unified voice controls and multi-tenant cleanup', () => {
  assert.match(contextSource, /export function useBusinessAssistant/)
  assert.match(contextSource, /startVoice/)
  assert.match(contextSource, /stopVoice/)
  assert.match(contextSource, /isMuted/)
  assert.match(contextSource, /audioDevices/)
  assert.match(contextSource, /previousUserKeyRef/)
  assert.match(contextSource, /stopVoice\(\)/)
})

test('business assistant context defaults transport to direct_gpt_live', () => {
  assert.match(
    contextSource,
    /const \[transport, setTransportState\] = useState<VoiceTransportMode>\('direct_gpt_live'\)/,
  )
})

test('business assistant context auto-creates conversation for startVoice and re-syncs on tenant user change', () => {
  // startVoice falls back to createConversation if activeConversationId is absent
  assert.match(contextSource, /startVoice\s*=\s*useCallback\(/)
  assert.match(contextSource, /if\s*\(!targetConversationId\)\s*\{\s*targetConversationId\s*=\s*await\s+createConversation\(\)/)
  assert.match(contextSource, /await\s+activeVoice\.startVoice\(targetConversationId\)/)

  // tenant/user change triggers refreshConversations if truthy
  assert.match(contextSource, /if\s*\(currentTenantUserKey\)\s*\{\s*void\s+refreshConversations\(\)\s*\}/)
})

