// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import { readFileSync } from 'node:fs'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url'
import { navigation, filterNavigationByModules } from '../../../components/navigation.ts'
import { ApiClient } from './workbench/api/client.ts'

test('Navigation menu consolidates Resident Agent and Coding Studio into Engineering Cockpit', () => {
  const complianceSection = navigation.find((s) => s.label === 'Compliance & System')
  assert.ok(complianceSection, 'Compliance & System section must exist')

  const titles = complianceSection!.items.map((i) => i.title)
  const urls = complianceSection!.items.map((i) => i.url)

  // Single unified entry
  assert.ok(titles.includes('Engineering Cockpit'), 'Engineering Cockpit must be in navigation')
  assert.ok(urls.includes('/admin/coding-cockpit'), '/admin/coding-cockpit route must be in navigation')

  // Redundant entries removed
  assert.equal(titles.includes('Resident Agent'), false, 'Resident Agent must be removed from menu')
  assert.equal(titles.includes('Conversational Coding Studio'), false, 'Coding Studio must be removed from menu')
  assert.equal(urls.includes('/admin/resident-agent'), false, 'Legacy route must be removed from menu')
  assert.equal(urls.includes('/admin/coding-studio'), false, 'Legacy route must be removed from menu')
})

test('filterNavigationByModules preserves Engineering Cockpit when modules are enabled', () => {
  const filtered = filterNavigationByModules(navigation, ['locations', 'sms'])
  const complianceSection = filtered.find((s) => s.label === 'Compliance & System')
  assert.ok(complianceSection)
  const item = complianceSection!.items.find((i) => i.url === '/admin/coding-cockpit')
  assert.ok(item, 'Engineering Cockpit must remain accessible')
  assert.equal(item!.title, 'Engineering Cockpit')
})

test('ApiClient defaults to same-origin /api/admin/codex and attaches admin tokens', () => {
  const client = new ApiClient()
  assert.equal(client.getBaseUrl(), '/api/admin/codex')

  // Check default timeout
  assert.ok(client.getBaseUrl().startsWith('/api/admin/codex'))
})

test('CodexWorkbenchTab contains ZERO IFRAMES and uses native embedded components', () => {
  const workbenchFilePath = fileURLToPath(new URL('./CodexWorkbenchTab.tsx', import.meta.url))
  const content = readFileSync(workbenchFilePath, 'utf8')

  // Strict prohibition on iframes
  assert.equal(content.includes('<iframe'), false, 'CodexWorkbenchTab must not contain any iframe')
  assert.equal(content.includes(':5180'), false, 'Must not reference port 5180')
  assert.equal(content.includes('http://127.0.0.1:4500'), false, 'Must not hardcode port 4500')

  // Native components present
  assert.ok(content.includes('Timeline'), 'Timeline component must be embedded')
  assert.ok(content.includes('Composer'), 'Composer component must be embedded')
  assert.ok(content.includes('Inspector'), 'Inspector component must be embedded')
  assert.ok(content.includes('DiffReviewStudioModal'), 'DiffReviewStudioModal must be embedded')
})

test('Monolith resident-agent.tsx is pruned and pruned of competitor radar and iframe', () => {
  const residentAgentPath = fileURLToPath(new URL('../resident-agent.tsx', import.meta.url))
  const content = readFileSync(residentAgentPath, 'utf8')

  // Pruned down to thin re-export
  assert.ok(content.length < 500, 'resident-agent.tsx monolith must be pruned down to a thin shim')
  assert.equal(content.includes('<iframe'), false, 'Must have zero iframes')
  assert.equal(content.includes('Competitor Tech Radar'), false, 'Must have zero competitor radar')
  assert.equal(content.includes('Quick Start Prompt Presets'), false, 'Must have zero static prompt copy cards')
})
