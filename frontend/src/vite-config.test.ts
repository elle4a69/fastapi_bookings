// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import { readFileSync } from 'node:fs'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url'

const viteConfig = readFileSync(fileURLToPath(new URL('../vite.config.ts', import.meta.url)), 'utf8')

test('PWA leaves every API request on the network/proxy path', () => {
  assert.match(viteConfig, /navigateFallbackDenylist:\s*\[\/\^\\\/api\(\?:\\\/\|\$\)\//)
  assert.match(viteConfig, /disableDevLogs:\s*true/)
  assert.match(viteConfig, /devOptions:\s*\{[\s\S]*?enabled:\s*true/)
  assert.match(viteConfig, /proxy:\s*\{[\s\S]*?'\/api':\s*\{/)
})
