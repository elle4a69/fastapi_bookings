// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'
// @ts-expect-error Node's file-system types are intentionally not part of the app build.
import { readFileSync } from 'node:fs'
// @ts-expect-error Node's URL types are intentionally not part of the app build.
import { fileURLToPath } from 'node:url'

import { resolvePageContext } from './context-boundary.ts'
import {
  formatRealtimeToolOutput,
  parseRealtimeToolCall,
} from './realtime-protocol.ts'

const drawerSource = readFileSync(
  fileURLToPath(new URL('./assistant-drawer.tsx', import.meta.url)),
  'utf8',
)
const layoutSource = readFileSync(
  fileURLToPath(new URL('../../../layouts/admin-layout.tsx', import.meta.url)),
  'utf8',
)
const headerSource = readFileSync(
  fileURLToPath(new URL('../../../components/app-header.tsx', import.meta.url)),
  'utf8',
)
const supportButtonSource = readFileSync(
  fileURLToPath(new URL('../../../components/support-button.tsx', import.meta.url)),
  'utf8',
)
const voiceHookSource = readFileSync(
  fileURLToPath(new URL('./use-realtime-voice.ts', import.meta.url)),
  'utf8',
)
const ticketStatusSource = readFileSync(
  fileURLToPath(new URL('./ticket-status.tsx', import.meta.url)),
  'utf8',
)

test('context awareness boundary extracts only route and module identifiers, never DOM or secrets', () => {
  const routesToTest = [
    { path: '/admin', expectedModule: 'dashboard' },
    { path: '/admin/dashboard', expectedModule: 'dashboard' },
    { path: '/admin/calendar', expectedModule: 'calendar' },
    { path: '/admin/bookings?view=upcoming#list', expectedPath: '/admin/bookings', expectedModule: 'bookings' },
    { path: '/admin/sms-assistant', expectedModule: 'sms_assistant' },
    { path: '/admin/catalog/services', expectedModule: 'catalog_services' },
    { path: '/admin/catalog/locations', expectedModule: 'locations' },
    { path: '/admin/catalog/providers', expectedModule: 'multiple_providers' },
    { path: '/admin/finance/invoices', expectedModule: 'finance_invoicing' },
    { path: '/admin/website', expectedModule: 'website' },
    { path: '/admin/settings/business', expectedModule: 'business_settings' },
    { path: '/admin/settings/modules', expectedModule: 'tenant_modules' },
    { path: '/admin/business-assistant', expectedModule: 'business_assistant' },
    { path: '/admin/custom-plugin-area', expectedModule: 'general_admin' },
  ]

  for (const item of routesToTest) {
    const context = resolvePageContext(item.path)
    const expectedPath = item.expectedPath ?? item.path
    assert.equal(context.current_path, expectedPath)
    assert.equal(context.module_name, item.expectedModule)

    // Verify boundary guarantees: only current_path and module_name properties exist
    const keys = Object.keys(context)
    assert.deepEqual(keys.sort(), ['current_path', 'module_name'])

    // Absolute prohibition of secrets, DOM content, form fields, tokens
    assert.doesNotMatch(JSON.stringify(context), /token|password|secret|bearer|input|value|document|body|html/i)
  }
})

test('drawer enforces accessibility, focus trapping/restoration, and keyboard navigation', () => {
  // Accessibility role and modal status
  assert.match(drawerSource, /role="dialog"/)
  assert.match(drawerSource, /aria-label="Business Assistant"/)
  assert.match(drawerSource, /aria-modal="true"/)
  assert.match(drawerSource, /id="business-assistant-drawer"/)

  // Keyboard navigation: Escape key closes drawer
  assert.match(drawerSource, /event\.key === 'Escape'/)
  assert.match(drawerSource, /closeDrawer\(\)/)

  // Focus management: saving previous active element and restoring on close
  assert.match(drawerSource, /previousActiveElementRef\.current = document\.activeElement/)
  assert.match(drawerSource, /previousActiveElementRef\.current\.focus\(\)/)

  // Responsive mobile behavior
  assert.match(drawerSource, /w-full/)
  assert.match(drawerSource, /sm:w-\[28rem\]/)
  assert.match(drawerSource, /lg:w-\[32rem\]/)

  // Non-obstructive layer discipline: Drawer uses z-40 so dialogs at z-50 are never covered
  assert.match(drawerSource, /fixed inset-0 z-40/)
  assert.match(drawerSource, /fixed inset-y-0 right-0 z-40/)
  assert.doesNotMatch(drawerSource, /className="[^"]*\bz-50\b/)
})

test('admin layout shell persistently provides business assistant across route changes', () => {
  assert.match(layoutSource, /<BusinessAssistantProvider>/)
  assert.match(layoutSource, /<BusinessAssistantDrawer \/>/)
  assert.match(layoutSource, /<SupportButton \/>/)

  // Floating support button toggles assistant drawer
  assert.match(supportButtonSource, /useBusinessAssistant\(\)/)
  assert.match(supportButtonSource, /onClick=\{toggleDrawer\}/)
  assert.match(supportButtonSource, /aria-label="Open Business Assistant"/)
  assert.match(supportButtonSource, /aria-controls="business-assistant-drawer"/)

  // Top header button toggles assistant drawer
  assert.match(headerSource, /useBusinessAssistant\(\)/)
  assert.match(headerSource, /onClick=\{toggleDrawer\}/)
  assert.match(headerSource, /aria-label="Open Business Assistant"/)
  assert.match(headerSource, /aria-controls="business-assistant-drawer"/)
})

test('realtime protocol parses tool execution calls and formats outputs', () => {
  const toolCallEvent = {
    type: 'response.function_call_arguments.done',
    call_id: 'call_123',
    name: 'explain_catalog_services',
    arguments: JSON.stringify({ category: 'massage' }),
  }
  const parsed = parseRealtimeToolCall(toolCallEvent)
  assert.ok(parsed)
  if (!parsed) return
  assert.equal(parsed.callId, 'call_123')
  assert.equal(parsed.name, 'explain_catalog_services')
  assert.deepEqual(parsed.arguments, { category: 'massage' })

  const formattedOutput = formatRealtimeToolOutput('call_123', { status: 'ok', count: 3 })
  assert.equal(formattedOutput.type, 'conversation.item.create')
  assert.equal((formattedOutput.item as { call_id: string }).call_id, 'call_123')
  assert.equal((formattedOutput.item as { type: string }).type, 'function_call_output')
})

test('voice session hook degrades gracefully to text on mic denial and upstream error', () => {
  // Graceful degradation on microphone denial
  assert.match(voiceHookSource, /NotAllowedError/)
  assert.match(
    voiceHookSource,
    /Microphone access was declined\. You can continue in text\./,
  )

  // Proper teardown on disconnect or error
  assert.match(voiceHookSource, /stopVoice\(\)/)
  assert.match(voiceHookSource, /microphoneStream\.getTracks\(\)\.forEach\(/)
  assert.match(voiceHookSource, /peerConnectionRef\.current\?\.close\(\)/)
})

test('ticket status component renders user-safe status badges, timeline, and sanitised notice', () => {
  assert.match(ticketStatusSource, /formatStatus/)
  assert.match(ticketStatusSource, /awaiting_engineering/)
  assert.match(ticketStatusSource, /Owner Approval Required/)
  assert.match(ticketStatusSource, /Event timeline/)
  assert.match(
    ticketStatusSource,
    /Tickets remain awaiting engineering review; they do not trigger work automatically\./,
  )
  assert.match(
    ticketStatusSource,
    /Do not include customer passwords, API secrets, or sensitive customer PII\./,
  )
})
