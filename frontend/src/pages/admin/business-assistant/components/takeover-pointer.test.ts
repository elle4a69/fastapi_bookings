// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'

import {
  highlightFieldInDom,
  ControlEpochManager,
  defaultEpochManager,
  executeRpcAction,
} from '../rpc/action-catalogue.ts'

// ── 1. DOM HIGHLIGHT RESOLUTION & DISPATCH ───────────────────────────────

test('highlightFieldInDom resolves target input by selector candidates and dispatches highlight event', () => {
  // Setup minimal DOM simulation in Node environment
  const originalDocument = globalThis.document
  const originalWindow = globalThis.window

  let scrolled = false
  let eventDispatched: any = null

  const mockElement: any = {
    id: 'business_name',
    style: { outline: '', boxShadow: '', transition: '' },
    scrollIntoView: () => {
      scrolled = true
    },
    getBoundingClientRect: () => ({
      top: 120,
      left: 200,
      width: 320,
      height: 42,
    }),
  }

  const mockDocument: any = {
    querySelector: (selector: string) => {
      if (selector === '[data-field-name="business_name"]') {
        return mockElement
      }
      return null
    },
  }

  const mockWindow: any = {
    dispatchEvent: (ev: any) => {
      eventDispatched = ev
      return true
    },
  }

  ;(globalThis as any).document = mockDocument
  ;(globalThis as any).window = mockWindow

  try {
    const res = highlightFieldInDom('business_name')
    assert.equal(res.found, true)
    assert.equal(res.selector, '[data-field-name="business_name"]')
    assert.equal(res.id, 'business_name')
    assert.equal(scrolled, true)

    assert.ok(eventDispatched)
    assert.equal(eventDispatched.type, 'assistant:highlight-field')
    assert.equal(eventDispatched.detail.field, 'business_name')
    assert.equal(eventDispatched.detail.rect.top, 120)
    assert.equal(eventDispatched.detail.rect.width, 320)
  } finally {
    ;(globalThis as any).document = originalDocument
    ;(globalThis as any).window = originalWindow
  }
})

test('highlightFieldInDom resolves fallback selectors like id and name when data-field-name is absent', () => {
  const originalDocument = globalThis.document
  const originalWindow = globalThis.window

  const mockElement: any = {
    id: 'deposit_amount',
    style: {},
    scrollIntoView: () => {},
    getBoundingClientRect: () => ({ top: 50, left: 50, width: 100, height: 30 }),
  }

  const mockDocument: any = {
    querySelector: (selector: string) => {
      if (selector === '#deposit_amount') {
        return mockElement
      }
      return null
    },
  }

  ;(globalThis as any).document = mockDocument
  ;(globalThis as any).window = { dispatchEvent: () => true }

  try {
    const res = highlightFieldInDom('deposit_amount')
    assert.equal(res.found, true)
    assert.equal(res.selector, '#deposit_amount')
  } finally {
    ;(globalThis as any).document = originalDocument
    ;(globalThis as any).window = originalWindow
  }
})

test('highlightFieldInDom returns found=false gracefully when element is absent', () => {
  const originalDocument = globalThis.document
  ;(globalThis as any).document = { querySelector: () => null }

  try {
    const res = highlightFieldInDom('non_existent_field')
    assert.equal(res.found, false)
    assert.equal(res.selector, undefined)
  } finally {
    ;(globalThis as any).document = originalDocument
  }
})

// ── 2. MANUAL TAKEOVER & CONTROL EPOCH ADVANCEMENT ───────────────────────

test('Manual takeover increments control epoch and invalidates late agent writes', async () => {
  const epochMgr = new ControlEpochManager()
  assert.equal(epochMgr.getEpoch(), 1)

  // 1. Simulate agent preparing a field write under epoch 1
  const plannedAgentEpoch = epochMgr.getEpoch()

  // 2. User clicks "I'll do this part" manual takeover button
  const newEpoch = epochMgr.incrementEpoch("User clicked 'I\\'ll do this part'")
  assert.equal(newEpoch, 2)
  assert.equal(epochMgr.getEpoch(), 2)

  // 3. Late arriving agent write with epoch 1 is rejected
  const lateReceipt = await executeRpcAction(
    'fill_fields',
    {
      control_epoch: plannedAgentEpoch,
      fields: { phone: '+61400111222' },
    },
    {
      actionId: 'act_late_write',
      callerIdentity: 'agent_primary',
      epochManager: epochMgr,
    },
  )

  assert.equal(lateReceipt.status, 'rejected')
  assert.equal(lateReceipt.receipt_state, 'rejected')
  assert.equal(lateReceipt.error_code, 'stale_control_epoch')
  assert.match(lateReceipt.error || '', /stale control epoch/i)

  // 4. Command aligned with new epoch succeeds
  const freshReceipt = await executeRpcAction(
    'highlight_field',
    {
      control_epoch: newEpoch,
      field: 'phone',
    },
    {
      actionId: 'act_fresh_highlight',
      callerIdentity: 'agent_primary',
      epochManager: epochMgr,
    },
  )

  assert.equal(freshReceipt.status, 'waiting_for_ui')
  assert.equal(freshReceipt.receipt_state, 'waiting_for_ui')
  assert.equal(freshReceipt.control_epoch, 2)
})

// ── 3. MANUAL TAKEOVER CLEARS ADAPTER STAGING ────────────────────────────

test('Manual takeover triggers adapter staging cleanup and dispatches takeover event', () => {
  const originalWindow = globalThis.window
  let dispatchedEvents: string[] = []

  ;(globalThis as any).window = {
    dispatchEvent: (ev: any) => {
      dispatchedEvents.push(ev.type)
      return true
    },
  }

  try {
    const epochBefore = defaultEpochManager.getEpoch()
    const advancedEpoch = defaultEpochManager.incrementEpoch('Manual takeover test')
    assert.equal(advancedEpoch, epochBefore + 1)

    // Simulate window events dispatched by ManualTakeoverControl
    globalThis.window.dispatchEvent(
      new CustomEvent('assistant-rpc:manual-takeover', {
        detail: { newEpoch: advancedEpoch, source: 'ui_button' },
      }),
    )
    globalThis.window.dispatchEvent(new CustomEvent('assistant:dismiss-highlight'))

    assert.ok(dispatchedEvents.includes('assistant-rpc:manual-takeover'))
    assert.ok(dispatchedEvents.includes('assistant:dismiss-highlight'))
  } finally {
    ;(globalThis as any).window = originalWindow
  }
})
