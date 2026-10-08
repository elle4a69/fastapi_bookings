// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'

import {
  isRouteAllowlisted,
  isSectionAllowlisted,
  normalizeRoute,
  normalizeSection,
  executeRpcAction,
} from './action-catalogue.ts'
import { createAssistantRpcHandler, registerAssistantRpcMethods } from './rpc-receiver.ts'
import { validateAssistantRpcSender } from './sender-validation.ts'
import type { RpcReceiverContext } from './types.ts'

// ── 1. SENDER VALIDATION TESTS ──────────────────────────────────────────

test('validateAssistantRpcSender rejects missing or empty caller identity', () => {
  const result1 = validateAssistantRpcSender({ callerIdentity: '' })
  assert.equal(result1.valid, false)
  assert.match(result1.reason ?? '', /missing or empty/i)

  const result2 = validateAssistantRpcSender({ callerIdentity: '   ' })
  assert.equal(result2.valid, false)
  assert.match(result2.reason ?? '', /missing or empty/i)
})

test('validateAssistantRpcSender enforces isolation and rejects self-invocation', () => {
  const mockRoom = {
    localParticipant: { identity: 'part_client_123' },
    remoteParticipants: new Map(),
  } as any

  const result = validateAssistantRpcSender({
    callerIdentity: 'part_client_123',
    room: mockRoom,
  })
  assert.equal(result.valid, false)
  assert.match(result.reason ?? '', /self-invocation rejected/i)
})

test('validateAssistantRpcSender accepts expected agent identity and allowlisted identities', () => {
  const result1 = validateAssistantRpcSender({
    callerIdentity: 'agent_assistant_primary',
    expectedAgentIdentity: 'agent_assistant_primary',
  })
  assert.equal(result1.valid, true)

  const result2 = validateAssistantRpcSender({
    callerIdentity: 'custom_trusted_agent',
    allowedAgentIdentities: ['custom_trusted_agent', 'another_agent'],
  })
  assert.equal(result2.valid, true)
})

test('validateAssistantRpcSender validates remote participant agent status in room', () => {
  const mockAgentParticipant = {
    identity: 'agent_participant_77',
    name: 'bookings-business-assistant',
    isAgent: true,
  }
  const mockRegularParticipant = {
    identity: 'attendee_guest_99',
    name: 'Guest User',
    isAgent: false,
    kind: 0,
  }

  const remoteParticipants = new Map<string, any>()
  remoteParticipants.set('agent_participant_77', mockAgentParticipant)
  remoteParticipants.set('attendee_guest_99', mockRegularParticipant)

  const mockRoom = {
    localParticipant: { identity: 'user_browser_1' },
    remoteParticipants,
  } as any

  // Verified assistant agent should pass
  const passResult = validateAssistantRpcSender({
    callerIdentity: 'agent_participant_77',
    room: mockRoom,
    expectedAgentName: 'bookings-business-assistant',
  })
  assert.equal(passResult.valid, true)

  // Regular non-agent attendee should be rejected
  const rejectResult = validateAssistantRpcSender({
    callerIdentity: 'attendee_guest_99',
    room: mockRoom,
  })
  assert.equal(rejectResult.valid, false)
  assert.match(rejectResult.reason ?? '', /not a verified assistant/i)

  // Non-existent participant should be rejected
  const notFoundResult = validateAssistantRpcSender({
    callerIdentity: 'forged_intruder',
    room: mockRoom,
  })
  assert.equal(notFoundResult.valid, false)
  assert.match(notFoundResult.reason ?? '', /not found in the current LiveKit room/i)
})

// ── 2. ROUTE NAVIGATION & ALIAS TESTS ───────────────────────────────────

test('normalizeRoute resolves canonical routes and friendly aliases', () => {
  assert.equal(normalizeRoute('website'), '/admin/website')
  assert.equal(normalizeRoute('website_editor'), '/admin/website')
  assert.equal(normalizeRoute('media'), '/admin/media')
  assert.equal(normalizeRoute('services'), '/admin/catalog/services')
  assert.equal(normalizeRoute('onboarding'), '/admin/settings/business')
  assert.equal(normalizeRoute('bookings'), '/admin/bookings')
  assert.equal(normalizeRoute('/admin/website?tab=sections'), '/admin/website')
})

test('isRouteAllowlisted strictly allows approved admin routes and rejects unsafe paths', () => {
  assert.equal(isRouteAllowlisted('/admin/website'), true)
  assert.equal(isRouteAllowlisted('/admin/media'), true)
  assert.equal(isRouteAllowlisted('/admin/catalog/services'), true)
  assert.equal(isRouteAllowlisted('/admin/settings/business'), true)
  assert.equal(isRouteAllowlisted('website'), true)
  assert.equal(isRouteAllowlisted('services'), true)

  // Rejections
  assert.equal(isRouteAllowlisted('/admin/unknown-secret-route'), false)
  assert.equal(isRouteAllowlisted('https://malicious-external-url.com'), false)
  assert.equal(isRouteAllowlisted('http://evil.com'), false)
  assert.equal(isRouteAllowlisted('javascript:alert(1)'), false)
  assert.equal(isRouteAllowlisted('/admin/website/../../etc/passwd'), false)
  assert.equal(isRouteAllowlisted('//evil.com/xss'), false)
})

test('executeRpcAction route_navigation dispatches navigation and returns receipt', async () => {
  let navigatedPath: string | null = null

  const context: RpcReceiverContext = {
    onNavigate: (path) => {
      navigatedPath = path
    },
  }

  const receipt = await executeRpcAction(
    'route_navigation',
    { path: '/admin/website' },
    {
      actionId: 'act_nav_1',
      callerIdentity: 'agent_primary',
      context,
    },
  )

  assert.equal(receipt.status, 'success')
  assert.equal(receipt.action, 'route_navigation')
  assert.equal(receipt.resulting_page, '/admin/website')
  assert.equal(navigatedPath, '/admin/website')

  // Negative test: unallowlisted route
  const rejectedReceipt = await executeRpcAction(
    'route_navigation',
    { path: '/unauthorized/route' },
    {
      actionId: 'act_nav_bad',
      callerIdentity: 'agent_primary',
      context,
    },
  )
  assert.equal(rejectedReceipt.status, 'rejected')
  assert.match(rejectedReceipt.error ?? '', /not in the allowlisted/i)
})

// ── 3. PREVIEW TOGGLE TESTS ─────────────────────────────────────────────

test('executeRpcAction preview_toggle handles open, closed, and toggle states', async () => {
  let currentState: 'open' | 'closed' = 'closed'

  const context: RpcReceiverContext = {
    onPreviewToggle: (requested) => {
      if (requested === 'open') currentState = 'open'
      else if (requested === 'closed') currentState = 'closed'
      else currentState = currentState === 'open' ? 'closed' : 'open'
      return currentState
    },
  }

  const receiptOpen = await executeRpcAction(
    'preview_toggle',
    { state: 'open' },
    { actionId: 'act_prev_1', callerIdentity: 'agent_primary', context },
  )
  assert.equal(receiptOpen.status, 'success')
  assert.equal(receiptOpen.preview_state, 'open')
  assert.equal(currentState, 'open')

  const receiptClose = await executeRpcAction(
    'preview_toggle',
    { state: 'closed' },
    { actionId: 'act_prev_2', callerIdentity: 'agent_primary', context },
  )
  assert.equal(receiptClose.status, 'success')
  assert.equal(receiptClose.preview_state, 'closed')
  assert.equal(currentState, 'closed')

  const receiptToggle = await executeRpcAction(
    'preview_toggle',
    { state: 'toggle' },
    { actionId: 'act_prev_3', callerIdentity: 'agent_primary', context },
  )
  assert.equal(receiptToggle.status, 'success')
  assert.equal(receiptToggle.preview_state, 'open')
  assert.equal(currentState, 'open')
})

// ── 4. SECTION HIGHLIGHT TESTS ──────────────────────────────────────────

test('normalizeSection and isSectionAllowlisted validate known website sections', () => {
  assert.equal(normalizeSection('hero-section'), 'hero')
  assert.equal(normalizeSection('section-about'), 'about')
  assert.equal(normalizeSection('services'), 'services')

  assert.equal(isSectionAllowlisted('hero'), true)
  assert.equal(isSectionAllowlisted('about'), true)
  assert.equal(isSectionAllowlisted('services'), true)
  assert.equal(isSectionAllowlisted('booking'), true)
  assert.equal(isSectionAllowlisted('contact'), true)
  assert.equal(isSectionAllowlisted('footer'), true)

  assert.equal(isSectionAllowlisted('fake_section_injection'), false)
})

test('executeRpcAction section_highlight validates section and reports element resolution', async () => {
  let highlightedSection: string | null = null

  const context: RpcReceiverContext = {
    onSectionHighlight: (sec) => {
      highlightedSection = sec
      return { found: true, id: `${sec}-section` }
    },
  }

  const receipt = await executeRpcAction(
    'section_highlight',
    { section: 'services' },
    { actionId: 'act_hl_1', callerIdentity: 'agent_primary', context },
  )

  assert.equal(receipt.status, 'success')
  assert.equal(receipt.action, 'section_highlight')
  assert.equal(receipt.target_section, 'services')
  assert.equal(receipt.details?.element_found, true)
  assert.equal(receipt.details?.element_id, 'services-section')
  assert.equal(highlightedSection, 'services')

  // Negative test: invalid section
  const badReceipt = await executeRpcAction(
    'section_highlight',
    { section: 'non_existent_section' },
    { actionId: 'act_hl_bad', callerIdentity: 'agent_primary', context },
  )
  assert.equal(badReceipt.status, 'rejected')
  assert.match(badReceipt.error ?? '', /not an allowlisted/i)
})

// ── 5. CHANGE-REVIEW DRAWER TESTS ───────────────────────────────────────

test('executeRpcAction change_review_drawer opens and closes review drawer with proposalId', async () => {
  let drawerOpenState: 'open' | 'closed' = 'closed'
  let capturedProposalId: number | undefined

  const context: RpcReceiverContext = {
    onChangeReviewDrawer: (state, propId) => {
      drawerOpenState = state === 'closed' ? 'closed' : 'open'
      capturedProposalId = propId
      return drawerOpenState
    },
  }

  const receiptOpen = await executeRpcAction(
    'change_review_drawer',
    { state: 'open', proposal_id: 105 },
    { actionId: 'act_drawer_1', callerIdentity: 'agent_primary', context },
  )

  assert.equal(receiptOpen.status, 'success')
  assert.equal(receiptOpen.drawer_state, 'open')
  assert.equal(receiptOpen.details?.proposal_id, 105)
  assert.equal(drawerOpenState, 'open')
  assert.equal(capturedProposalId, 105)

  const receiptClose = await executeRpcAction(
    'change_review_drawer',
    { state: 'closed' },
    { actionId: 'act_drawer_2', callerIdentity: 'agent_primary', context },
  )

  assert.equal(receiptClose.status, 'success')
  assert.equal(receiptClose.drawer_state, 'closed')
  assert.equal(drawerOpenState, 'closed')
})

// ── 6. FULL RPC HANDLER & LIVEKIT REGISTRATION ──────────────────────────

test('createAssistantRpcHandler executes full pipeline with sender validation and structured receipt', async () => {
  const receiptsEmitted: any[] = []
  const context: RpcReceiverContext = {
    expectedAgentIdentity: 'agent_designated_123',
    onNavigate: () => {},
    onReceipt: (rcpt) => receiptsEmitted.push(rcpt),
  }

  const handler = createAssistantRpcHandler(context)

  // 1. Successful unified invocation
  const responseJson = await handler('assistant_ui_action', {
    requestId: 'req_unified_001',
    callerIdentity: 'agent_designated_123',
    payload: JSON.stringify({
      action: 'route_navigation',
      params: { path: '/admin/media' },
    }),
    responseTimeout: 10000,
  })

  const receipt = JSON.parse(responseJson)
  assert.equal(receipt.status, 'success')
  assert.equal(receipt.action, 'route_navigation')
  assert.equal(receipt.resulting_page, '/admin/media')
  assert.equal(receiptsEmitted.length, 1)

  // 2. Sender validation rejection on forged caller
  const rejectedJson = await handler('assistant_ui_action', {
    requestId: 'req_forged_002',
    callerIdentity: 'unauthorized_hacker',
    payload: JSON.stringify({
      action: 'route_navigation',
      path: '/admin/website',
    }),
    responseTimeout: 10000,
  })

  const rejectedReceipt = JSON.parse(rejectedJson)
  assert.equal(rejectedReceipt.status, 'rejected')
  assert.match(rejectedReceipt.error ?? '', /sender validation failed/i)

  // 3. Malformed JSON handling
  const badJson = await handler('assistant_ui_action', {
    requestId: 'req_malformed_003',
    callerIdentity: 'agent_designated_123',
    payload: '{{invalid-json',
    responseTimeout: 10000,
  })

  const badJsonReceipt = JSON.parse(badJson)
  assert.equal(badJsonReceipt.status, 'failed')
  assert.match(badJsonReceipt.error ?? '', /malformed or invalid JSON/i)
})

test('registerAssistantRpcMethods registers all methods on Room and provides clean unregister handle', () => {
  const registered: Record<string, Function> = {}
  const unregistered: string[] = []

  const mockRoom = {
    registerRpcMethod: (method: string, fn: Function) => {
      registered[method] = fn
    },
    unregisterRpcMethod: (method: string) => {
      unregistered.push(method)
      delete registered[method]
    },
  } as any

  const registration = registerAssistantRpcMethods(mockRoom, {
    expectedAgentIdentity: 'agent_livekit_test',
  })

  assert.equal(registration.registeredMethods.length, 6)
  assert.ok(registered['assistant_ui_action'])
  assert.ok(registered['route_navigation'])
  assert.ok(registered['navigate'])
  assert.ok(registered['preview_toggle'])
  assert.ok(registered['section_highlight'])
  assert.ok(registered['change_review_drawer'])

  // Clean unregister
  registration.unregister()
  assert.equal(unregistered.length, 6)
  assert.equal(Object.keys(registered).length, 0)
})
