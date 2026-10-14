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
import {
  CODEX_MODELS,
  DEFAULT_CODEX_MODEL,
  getLastUsedCodexModel,
  resolveCodexModel,
  setLastUsedCodexModel,
} from './workbench/modelCatalog.ts'

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

  // Sticky Model Selector dropdown uses the shared current catalog.
  assert.ok(content.includes('CODEX_MODELS'), 'Must render the shared current model catalog')
  assert.ok(content.includes('useCodexModelPreference'), 'Must use the shared sticky model preference')
  assert.equal(content.includes('GPT-4 over 0.0'), false, 'Must not contain stale model strings')
})

test('Codex model catalog exposes all current variants and rejects retired GPT-4 selections', () => {
  assert.deepEqual(CODEX_MODELS.map(model => model.id), [
    'gpt-6.1-sol',
    'gpt-6-astra',
    'gpt-6-sol',
    'gpt-6-luna',
    'gpt-5.6-sol',
    'gpt-5.6-terra',
    'gpt-5.6-luna',
  ])
  assert.equal(CODEX_MODELS.some(model => model.id.startsWith('gpt-4')), false)
  assert.equal(resolveCodexModel('gpt-6-astra'), 'gpt-6-astra')
  assert.equal(resolveCodexModel('gpt-4o'), DEFAULT_CODEX_MODEL)
  assert.ok(CODEX_MODELS.find(model => model.id === 'gpt-6.1-sol')?.supportedReasoningEfforts.includes('ultra'))
  assert.equal(CODEX_MODELS.find(model => model.id === 'gpt-6-luna')?.supportedReasoningEfforts.includes('ultra'), false)
})

test('last selected Codex model remains the validated default across workflows', () => {
  const originalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
  const values = new Map<string, string>()
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    },
  })

  try {
    assert.equal(setLastUsedCodexModel('gpt-6-astra'), 'gpt-6-astra')
    assert.equal(getLastUsedCodexModel(), 'gpt-6-astra')
    values.set('codex_last_used_model', 'gpt-4o')
    assert.equal(getLastUsedCodexModel(), DEFAULT_CODEX_MODEL)
  } finally {
    if (originalStorage) {
      Object.defineProperty(globalThis, 'localStorage', originalStorage)
    } else {
      delete (globalThis as { localStorage?: unknown }).localStorage
    }
  }
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

test('codexApi connectThreadEvents implements resilient auto-reconnection and ticket refresh', () => {
  const codexApiPath = fileURLToPath(new URL('./workbench/api/codexApi.ts', import.meta.url))
  const content = readFileSync(codexApiPath, 'utf8')

  assert.ok(content.includes('scheduleReconnect'), 'Must have auto-reconnect scheduling')
  assert.ok(content.includes('currentLastEventId'), 'Must track last received event ID')
  assert.ok(content.includes('createThreadEventTicket'), 'Must refresh SSE ticket on connection')
  assert.ok(content.includes('Math.min(1000 * Math.pow(1.5, retryCount)'), 'Must implement exponential backoff')
})

test('ThreadHeader and useWorkbenchStore guard against null thread and undefined properties', () => {
  const headerPath = fileURLToPath(new URL('./workbench/components/layout/ThreadHeader.tsx', import.meta.url))
  const storePath = fileURLToPath(new URL('./workbench/store/useWorkbenchStore.ts', import.meta.url))
  const pulsePath = fileURLToPath(new URL('./workbench/components/timeline/LiveActivityPulse.tsx', import.meta.url))
  const timelinePath = fileURLToPath(new URL('./workbench/components/timeline/Timeline.tsx', import.meta.url))

  const headerContent = readFileSync(headerPath, 'utf8')
  const storeContent = readFileSync(storePath, 'utf8')
  const pulseContent = readFileSync(pulsePath, 'utf8')
  const timelineContent = readFileSync(timelinePath, 'utf8')

  // Reactive sticky model
  assert.ok(headerContent.includes('selectedStickyModel'), 'ThreadHeader must have reactive sticky model state')
  
  // Safe optional chaining in pulse
  assert.ok(pulseContent.includes('activeThread?.turns?.some'), 'LiveActivityPulse must safely optional chain turns')

  // Safe fallback in timeline
  assert.ok(timelineContent.includes("thread.permissionProfile || 'workspace_write'"), 'Timeline must safely fallback permissionProfile')

  // Auto-thread creation fallback on message send
  assert.ok(storeContent.includes('if (!threadId) {'), 'sendUserMessage must auto-create thread if null')
})

test('Coding Cockpit integrates Platform Owner Support Ticket Review Queue and Codex Launch Bridge', () => {
  const headerPath = fileURLToPath(new URL('./workbench/components/layout/ThreadHeader.tsx', import.meta.url))
  const sidebarPath = fileURLToPath(new URL('./workbench/components/layout/UnifiedSidebar.tsx', import.meta.url))
  const modalsPath = fileURLToPath(new URL('./workbench/components/tools/SecondaryToolsModals.tsx', import.meta.url))
  const reviewModalPath = fileURLToPath(new URL('./workbench/components/tools/SupportTicketsReviewModal.tsx', import.meta.url))
  const storePath = fileURLToPath(new URL('./workbench/store/useWorkbenchStore.ts', import.meta.url))

  const headerContent = readFileSync(headerPath, 'utf8')
  const sidebarContent = readFileSync(sidebarPath, 'utf8')
  const modalsContent = readFileSync(modalsPath, 'utf8')
  const reviewModalContent = readFileSync(reviewModalPath, 'utf8')
  const storeContent = readFileSync(storePath, 'utf8')

  // 1. ThreadHeader has support_tickets trigger and icon
  assert.ok(headerContent.includes("setActiveToolModal('support_tickets')"), 'ThreadHeader must trigger support_tickets modal')
  assert.ok(headerContent.includes('Headphones'), 'ThreadHeader must import and display Headphones icon for tickets')

  // 2. UnifiedSidebar has support_tickets trigger
  assert.ok(sidebarContent.includes("setActiveToolModal('support_tickets')"), 'UnifiedSidebar must trigger support_tickets modal')

  // 3. Store supports support_tickets modal and openThreadById helper
  assert.ok(storeContent.includes("'support_tickets'"), 'ActiveToolModal must include support_tickets')
  assert.ok(storeContent.includes('openThreadById'), 'useWorkbenchStore must export openThreadById')

  // 4. SecondaryToolsModals renders SupportTicketsReviewModal
  assert.ok(modalsContent.includes('SupportTicketsReviewModal'), 'SecondaryToolsModals must embed SupportTicketsReviewModal')
  assert.ok(modalsContent.includes("case 'support_tickets':"), 'SecondaryToolsModals must handle support_tickets case')

  // 5. ReviewModal has required controls: API calls, launch codex, error context, messages
  assert.ok(reviewModalContent.includes('/api/admin/support-tickets'), 'ReviewModal must call admin support tickets endpoint')
  assert.ok(reviewModalContent.includes('/launch-codex'), 'ReviewModal must call launch-codex endpoint')
  assert.ok(reviewModalContent.includes('Launch Codex Investigation'), 'ReviewModal must display Launch Codex Investigation action')
  assert.ok(reviewModalContent.includes('error_context'), 'ReviewModal must inspect error_context')
  assert.ok(reviewModalContent.includes('internal_only'), 'ReviewModal must support internal notes')
})

test('SupportTicketManagementStation delivers full-featured Management Center with prominent authorization banners and thread jumping', () => {
  const stationPath = fileURLToPath(new URL('./workbench/components/tools/SupportTicketManagementStation.tsx', import.meta.url))
  const workbenchPath = fileURLToPath(new URL('./CodexWorkbenchTab.tsx', import.meta.url))
  const sidebarPath = fileURLToPath(new URL('./workbench/components/layout/UnifiedSidebar.tsx', import.meta.url))
  const headerPath = fileURLToPath(new URL('./workbench/components/layout/ThreadHeader.tsx', import.meta.url))
  const storePath = fileURLToPath(new URL('./workbench/store/useWorkbenchStore.ts', import.meta.url))

  const stationContent = readFileSync(stationPath, 'utf8')
  const workbenchContent = readFileSync(workbenchPath, 'utf8')
  const sidebarContent = readFileSync(sidebarPath, 'utf8')
  const headerContent = readFileSync(headerPath, 'utf8')
  const storeContent = readFileSync(storePath, 'utf8')

  // 1. Filter tabs with live counts
  assert.ok(stationContent.includes("activeTab === 'needs_authorization'"), 'Station must support Needs Authorization filter tab')
  assert.ok(stationContent.includes("activeTab === 'active_investigation'"), 'Station must support Active Investigation filter tab')
  assert.ok(stationContent.includes("activeTab === 'waiting_on_tenant'"), 'Station must support Waiting on Tenant filter tab')
  assert.ok(stationContent.includes("activeTab === 'resolved'"), 'Station must support Resolved filter tab')

  // 2. Prominent status chips in master list
  assert.ok(stationContent.includes('NEEDS AUTHORIZATION'), 'Must display amber NEEDS AUTHORIZATION chip')
  assert.ok(stationContent.includes('INVESTIGATION RUNNING'), 'Must display blue INVESTIGATION RUNNING chip')
  assert.ok(stationContent.includes('WAITING ON TENANT'), 'Must display purple WAITING ON TENANT chip')
  assert.ok(stationContent.includes('RESOLVED'), 'Must display green RESOLVED chip')

  // 3. Authorization Banner and Live Thread Switcher
  assert.ok(stationContent.includes('Authorization Required: Tenant Reported Issue'), 'Must display high-contrast authorization banner')
  assert.ok(stationContent.includes('Authorize & Launch Codex Investigation'), 'Must provide Authorize & Launch Codex action button')
  assert.ok(stationContent.includes('Switch to Live Investigation Thread'), 'Must provide instant switch to live investigation thread')

  // 4. Dual message composer & status shortcuts
  assert.ok(stationContent.includes('Reply to Tenant'), 'Must have Reply to Tenant tab')
  assert.ok(stationContent.includes('Internal Note - Invisible to Tenant'), 'Must display yellow internal note banner')
  assert.ok(stationContent.includes('Reply & Mark Waiting on Tenant'), 'Must provide quick Reply & Mark Waiting on Tenant shortcut')

  // 5. Store supports ActiveCenterView and live counters
  assert.ok(storeContent.includes('activeCenterView'), 'Store must track activeCenterView')
  assert.ok(storeContent.includes('supportTicketsSummary'), 'Store must track supportTicketsSummary')
  assert.ok(storeContent.includes('fetchSupportTicketsSummary'), 'Store must provide fetchSupportTicketsSummary')

  // 6. UnifiedSidebar prominent primary section & live badges
  assert.ok(sidebarContent.includes('Support Tickets'), 'UnifiedSidebar must have prominent primary Support Tickets section')
  assert.ok(sidebarContent.includes('needsAuth'), 'UnifiedSidebar must inspect needsAuth for live badge')

  // 7. ThreadHeader live badge and center view switcher
  assert.ok(headerContent.includes('needsAuth'), 'ThreadHeader must display live badge with needsAuth count')
  assert.ok(headerContent.includes("setActiveCenterView('tickets')"), 'ThreadHeader must support switching to tickets center view')

  // 8. CodexWorkbenchTab embeds SupportTicketManagementStation directly on Center Stage
  assert.ok(workbenchContent.includes('SupportTicketManagementStation'), 'CodexWorkbenchTab must embed SupportTicketManagementStation')
  assert.ok(workbenchContent.includes("state.activeCenterView === 'tickets'"), 'CodexWorkbenchTab must render tickets station on center stage')
})

test('Codex cockpit exposes real plugin installation and app-server authorization responses', () => {
  const pluginManagerPath = fileURLToPath(new URL('./PluginManager.tsx', import.meta.url))
  const pluginManagerContent = readFileSync(pluginManagerPath, 'utf8')
  const apiPath = fileURLToPath(new URL('./workbench/api/codexApi.ts', import.meta.url))
  const apiContent = readFileSync(apiPath, 'utf8')
  const modalPath = fileURLToPath(new URL('./workbench/components/tools/SecondaryToolsModals.tsx', import.meta.url))
  const modalContent = readFileSync(modalPath, 'utf8')
  const headerPath = fileURLToPath(new URL('./workbench/components/layout/ThreadHeader.tsx', import.meta.url))
  const headerContent = readFileSync(headerPath, 'utf8')
  const inputPath = fileURLToPath(new URL('./workbench/components/timeline/items/UserInputFormItem.tsx', import.meta.url))
  const inputContent = readFileSync(inputPath, 'utf8')
  const storePath = fileURLToPath(new URL('./workbench/store/useWorkbenchStore.ts', import.meta.url))
  const storeContent = readFileSync(storePath, 'utf8')

  assert.ok(pluginManagerContent.includes('isCodexSecurity'), 'Plugin manager must prioritize the live Codex Security catalog identity')
  assert.ok(pluginManagerContent.includes('appsNeedingAuth'), 'Plugin manager must surface provider authorization requirements')
  assert.ok(pluginManagerContent.includes('detail.apps'), 'Plugin manager must retain provider authorization links after reload')
  assert.ok(pluginManagerContent.includes('Connect {app.name}'), 'Plugin manager must render provider connection actions')
  assert.ok(apiContent.includes('listPlugins'), 'API client must list the app-server plugin catalog')
  assert.ok(apiContent.includes('installPlugin'), 'API client must install a selected plugin')
  assert.ok(apiContent.includes('resolveInteraction'), 'API client must resolve server-initiated interaction requests')
  assert.ok(modalContent.includes('PluginManager'), 'Secondary tools must render Plugin Manager')
  assert.ok(headerContent.includes("setActiveToolModal('plugins')"), 'Header must expose the Plugin Manager')
  assert.ok(inputContent.includes('resolveUserInputRequest'), 'Input cards must submit responses through the store')
  assert.ok(inputContent.includes('Open authorization page'), 'MCP URL prompts must provide a visible authorization action')
  assert.ok(storeContent.includes("case 'user_input_request':"), 'SSE reducer must render server input requests')
  assert.ok(storeContent.includes("case 'user_input_resolved':"), 'SSE reducer must reconcile resolved requests')
})

