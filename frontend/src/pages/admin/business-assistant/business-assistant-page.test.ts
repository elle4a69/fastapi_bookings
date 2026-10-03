// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'
// @ts-expect-error Node's file-system types are intentionally not part of the app build.
import { readFileSync } from 'node:fs'
// @ts-expect-error Node's URL types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url'

const page = readFileSync(fileURLToPath(new URL('./index.tsx', import.meta.url)), 'utf8')

test('conversation is primary and history is an explicitly opened drawer', () => {
  assert.match(page, /const \[historyOpen, setHistoryOpen\] = useState\(false\)/)
  assert.match(page, /data-testid="business-assistant-history-open"/)
  assert.match(page, /data-testid="business-assistant-history-menu"/)
  assert.match(page, /id="business-assistant-history"/)
  assert.match(page, /setHistoryOpen\(false\)/)
  assert.doesNotMatch(page, /Guided onboarding|Enabled modules:|active services/)
  assert.ok(page.indexOf('aria-label="Conversation"') < page.indexOf('support-ticket-heading'))
})
