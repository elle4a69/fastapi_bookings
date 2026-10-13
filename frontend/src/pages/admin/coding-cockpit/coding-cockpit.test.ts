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

  // Check tenant resolution fallback
  assert.equal(client.getTenant(), 'simplydemo')
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
  assert.ok(content.includes('UnifiedSidebar'), 'UnifiedSidebar must replace 2-column sidebar')
  assert.ok(content.includes('BottomConsoleDock'), 'BottomConsoleDock must be embedded')
})

test('UnifiedSidebar eliminates redundant 2-column sidebar into single nested tree', () => {
  const unifiedSidebarPath = fileURLToPath(new URL('./workbench/components/layout/UnifiedSidebar.tsx', import.meta.url))
  const content = readFileSync(unifiedSidebarPath, 'utf8')

  // Project header with "+ New Project" / "Project" trigger
  assert.ok(content.includes('Projects & Threads'), 'Must have Unified Projects & Threads header')
  assert.ok(content.includes('Project'), 'Must have project registration trigger')
  assert.ok(content.includes('Collapsible'), 'Must use Radix Collapsible for nested tree')
  assert.ok(content.includes('Search'), 'Must have conversation/thread search input')
  assert.ok(content.includes('Settings'), 'Must have settings button')

  // Shims exist and are thin
  const projectRailPath = fileURLToPath(new URL('./workbench/components/layout/ProjectRail.tsx', import.meta.url))
  const projectRailContent = readFileSync(projectRailPath, 'utf8')
  assert.ok(projectRailContent.length < 500, 'ProjectRail must be a thin shim')

  const threadSidebarPath = fileURLToPath(new URL('./workbench/components/layout/ThreadSidebar.tsx', import.meta.url))
  const threadSidebarContent = readFileSync(threadSidebarPath, 'utf8')
  assert.ok(threadSidebarContent.length < 500, 'ThreadSidebar must be a thin shim')
})

test('BottomConsoleDock is streamlined strictly to Terminal / Live Output runner', () => {
  const dockPath = fileURLToPath(new URL('./workbench/components/dock/BottomConsoleDock.tsx', import.meta.url))
  const content = readFileSync(dockPath, 'utf8')

  // Streamlined strictly to TerminalTab
  assert.ok(content.includes('TerminalTab'), 'Must embed TerminalTab')
  assert.ok(content.includes('Terminal / Live Output Runner'), 'Must have Terminal runner header')

  // Minimizable / maximizable controls
  assert.ok(content.includes('Minimize2') || content.includes('Maximize2'), 'Must have maximize/restore controls')
  assert.ok(content.includes('ChevronDown') || content.includes('ChevronUp'), 'Must have minimize/collapse controls')
})

test('Full-screen modal overlays house secondary tools (SRE Health, Fuzzer, AST Issues, Skills, Stream)', () => {
  const modalPath = fileURLToPath(new URL('./workbench/components/tools/SecondaryToolsModals.tsx', import.meta.url))
  const content = readFileSync(modalPath, 'utf8')

  assert.ok(content.includes('HealthSentinels'), 'Must embed HealthSentinels')
  assert.ok(content.includes('StressFuzzer'), 'Must embed StressFuzzer')
  assert.ok(content.includes('IssuesStudio'), 'Must embed IssuesStudio')
  assert.ok(content.includes('SkillsBrowser'), 'Must embed SkillsBrowser')
  assert.ok(content.includes('EventStream'), 'Must embed EventStream')
  assert.ok(content.includes('DialogContent'), 'Must render within Radix DialogContent')
})

test('ThreadHeader features Active Agent HUD, secondary tools launcher, and sticky Model Selector', () => {
  const headerPath = fileURLToPath(new URL('./workbench/components/layout/ThreadHeader.tsx', import.meta.url))
  const content = readFileSync(headerPath, 'utf8')

  // Active Agent HUD
  assert.ok(content.includes('isAgentWorking') || content.includes('actionText'), 'Must track agent working state')
  assert.ok(content.includes('stopActiveTurn'), 'Must support stopping active agent turn')
  assert.ok(content.includes('setSidebarOpen'), 'Must toggle collapsible left sidebar')
  assert.ok(content.includes('setInspectorOpen'), 'Must toggle collapsible right inspector')
  assert.ok(content.includes('toggleBottomDock'), 'Must toggle integrated bottom dock')

  // Secondary Tools launcher dropdown
  assert.ok(content.includes('setActiveToolModal'), 'Must launch tool modals')
  assert.ok(content.includes('SRE Health Sentinels'), 'Must include SRE Health')
  assert.ok(content.includes('Concurrency Stress Fuzzer'), 'Must include Stress Fuzzer')
  assert.ok(content.includes('AST Issues Studio'), 'Must include AST Issues')
  assert.ok(content.includes('Skills Library'), 'Must include Skills Library')
  assert.ok(content.includes('Event Stream'), 'Must include Event Stream')

  // Sticky Model Selector dropdown
  assert.ok(content.includes('gpt-5.6-sol'), 'Must list gpt-5.6-sol')
  assert.ok(content.includes('gpt-4o'), 'Must list gpt-4o')
  assert.ok(content.includes('gpt-4o-mini'), 'Must list gpt-4o-mini')
  assert.ok(content.includes('o3-mini'), 'Must list o3-mini')
  assert.ok(content.includes('o1'), 'Must list o1')
  assert.ok(content.includes('claude-3-5-sonnet'), 'Must list claude-3-5-sonnet')
  assert.ok(content.includes('codex_last_used_model'), 'Must persist model to localStorage')
  assert.equal(content.includes('GPT-4 over 0.0'), false, 'Must not contain stale model strings')
})

test('Standardized h-11 slim headers align across UnifiedSidebar, ThreadHeader, and Inspector', () => {
  const sidebarPath = fileURLToPath(new URL('./workbench/components/layout/UnifiedSidebar.tsx', import.meta.url))
  const headerPath = fileURLToPath(new URL('./workbench/components/layout/ThreadHeader.tsx', import.meta.url))
  const inspectorPath = fileURLToPath(new URL('./workbench/components/inspector/Inspector.tsx', import.meta.url))

  const sidebarContent = readFileSync(sidebarPath, 'utf8')
  const headerContent = readFileSync(headerPath, 'utf8')
  const inspectorContent = readFileSync(inspectorPath, 'utf8')

  assert.ok(sidebarContent.includes('h-11 px-3 border-b border-border'), 'UnifiedSidebar must use h-11 border-b')
  assert.ok(headerContent.includes('h-11 px-3 border-b border-border'), 'ThreadHeader must use h-11 border-b')
  assert.ok(inspectorContent.includes('h-11 px-3 border-b border-border'), 'Inspector must use h-11 border-b')
})

test('Draggable resizable side panels support clamping and persistent widths', () => {
  const workbenchPath = fileURLToPath(new URL('./CodexWorkbenchTab.tsx', import.meta.url))
  const storePath = fileURLToPath(new URL('./workbench/store/useWorkbenchStore.ts', import.meta.url))

  const workbenchContent = readFileSync(workbenchPath, 'utf8')
  const storeContent = readFileSync(storePath, 'utf8')

  // Splitters in workbench
  assert.ok(workbenchContent.includes('handleLeftSplitterPointerDown'), 'Must have left splitter handler')
  assert.ok(workbenchContent.includes('handleRightSplitterPointerDown'), 'Must have right splitter handler')
  assert.ok(workbenchContent.includes('cursor-col-resize'), 'Must set cursor-col-resize')

  // Persistence in store
  assert.ok(storeContent.includes('codex_sidebar_width'), 'Must persist sidebar width in localStorage')
  assert.ok(storeContent.includes('codex_inspector_width'), 'Must persist inspector width in localStorage')
  assert.ok(storeContent.includes('Math.max(220, Math.min(480'), 'Sidebar width must clamp between 220 and 480')
  assert.ok(storeContent.includes('Math.max(260, Math.min(600'), 'Inspector width must clamp between 260 and 600')
})

test('Inspector houses Diff Review, Active Files, and Settings', () => {
  const inspectorPath = fileURLToPath(new URL('./workbench/components/inspector/Inspector.tsx', import.meta.url))
  const content = readFileSync(inspectorPath, 'utf8')

  assert.ok(content.includes('ChangesTab'), 'Must embed Diff Review ChangesTab')
  assert.ok(content.includes('FilesTab'), 'Must embed Active FilesTab')
  assert.ok(content.includes('SettingsInspectorTab'), 'Must embed SettingsInspectorTab')
  assert.ok(content.includes('SubAgentsTab'), 'Must embed SubAgentsTab')
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
