// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'

import {
  ExecutorCoordinator,
} from './executor-coordinator.ts'
import { createAssistantRpcHandler } from './rpc-receiver.ts'
import { LeaseTokenManager } from './action-catalogue.ts'

class MockBroadcastChannel {
  name: string
  static channels: Map<string, Set<MockBroadcastChannel>> = new Map()
  onmessage: ((event: any) => void) | null = null
  private listeners: Set<(event: any) => void> = new Set()

  constructor(name: string) {
    this.name = name
    if (!MockBroadcastChannel.channels.has(name)) {
      MockBroadcastChannel.channels.set(name, new Set())
    }
    MockBroadcastChannel.channels.get(name)!.add(this)
  }

  postMessage(data: any) {
    const peers = MockBroadcastChannel.channels.get(this.name)
    if (peers) {
      for (const peer of peers) {
        if (peer !== this) {
          const event = { data }
          if (peer.onmessage) peer.onmessage(event)
          for (const l of peer.listeners) {
            l(event)
          }
        }
      }
    }
  }

  addEventListener(type: string, listener: (ev: any) => void) {
    if (type === 'message') this.listeners.add(listener)
  }

  removeEventListener(type: string, listener: (ev: any) => void) {
    if (type === 'message') this.listeners.delete(listener)
  }

  close() {
    MockBroadcastChannel.channels.get(this.name)?.delete(this)
  }
}

class MockStorage {
  private store: Map<string, string> = new Map()
  getItem(key: string): string | null {
    return this.store.get(key) ?? null
  }
  setItem(key: string, value: string): void {
    this.store.set(key, value)
  }
  removeItem(key: string): void {
    this.store.delete(key)
  }
  clear(): void {
    this.store.clear()
  }
}

// ── 1. INITIALIZATION & TAB ID GENERATION ────────────────────────────────

test('ExecutorCoordinator generates unique tab IDs with tab_ prefix', () => {
  const coord1 = new ExecutorCoordinator({
    broadcastChannelFactory: (name) => new MockBroadcastChannel(name),
    storage: new MockStorage() as any,
  })
  const coord2 = new ExecutorCoordinator({
    broadcastChannelFactory: (name) => new MockBroadcastChannel(name),
    storage: new MockStorage() as any,
  })

  try {
    assert.match(coord1.getCurrentTabId(), /^tab_\d+_[a-z0-9]+$/)
    assert.match(coord2.getCurrentTabId(), /^tab_\d+_[a-z0-9]+$/)
    assert.notEqual(coord1.getCurrentTabId(), coord2.getCurrentTabId())

    assert.equal(coord1.isCurrentTabActive(), false)
    assert.equal(coord1.getActiveTabId(), null)
    assert.equal(coord1.getActiveLeaseToken(), null)
  } finally {
    coord1.destroy()
    coord2.destroy()
  }
})

// ── 2. CLAIMING ACTIVE EXECUTOR LEASE ───────────────────────────────────

test('ExecutorCoordinator claimActiveExecutor establishes active lease and validates execution', () => {
  const storage = new MockStorage() as any
  const coord = new ExecutorCoordinator({
    tabId: 'tab_test_primary',
    broadcastChannelFactory: (name) => new MockBroadcastChannel(name),
    storage,
    leaseTtlMs: 5000,
  })

  try {
    assert.equal(coord.isCurrentTabActive(), false)
    const checkBefore = coord.validateExecution()
    assert.equal(checkBefore.allowed, false)
    assert.match(checkBefore.reason || '', /not the active executor/i)

    const token = coord.claimActiveExecutor()
    assert.ok(token.startsWith('lease_'))
    assert.equal(coord.isCurrentTabActive(), true)
    assert.equal(coord.getActiveTabId(), 'tab_test_primary')
    assert.equal(coord.getActiveLeaseToken(), token)

    const checkAfter = coord.validateExecution()
    assert.equal(checkAfter.allowed, true)
    assert.equal(checkAfter.reason, undefined)
  } finally {
    coord.destroy()
  }
})

// ── 3. MULTI-TAB LEASE HANDOVER & THEFT PROTECTION ──────────────────────

test('Multi-tab lease coordination: Tab B claim safely relinquishes Tab A', () => {
  MockBroadcastChannel.channels.clear()
  const storage = new MockStorage() as any

  const tabA = new ExecutorCoordinator({
    tabId: 'tab_A',
    channelName: 'test_executor_sync',
    broadcastChannelFactory: (name) => new MockBroadcastChannel(name),
    storage,
    leaseTtlMs: 10000,
  })

  const tabB = new ExecutorCoordinator({
    tabId: 'tab_B',
    channelName: 'test_executor_sync',
    broadcastChannelFactory: (name) => new MockBroadcastChannel(name),
    storage,
    leaseTtlMs: 10000,
  })

  try {
    // 1. Tab A claims active executor
    tabA.claimActiveExecutor('lease_token_A')
    assert.equal(tabA.isCurrentTabActive(), true)
    assert.equal(tabA.validateExecution().allowed, true)

    // Tab B detects Tab A as active
    assert.equal(tabB.isCurrentTabActive(), false)
    assert.equal(tabB.getActiveTabId(), 'tab_A')
    assert.equal(tabB.getActiveLeaseToken(), 'lease_token_A')
    const checkB = tabB.validateExecution()
    assert.equal(checkB.allowed, false)
    assert.match(checkB.reason || '', /tab 'tab_A'/i)

    // 2. User clicks "Make this tab active" on Tab B
    tabB.claimActiveExecutor('lease_token_B')
    assert.equal(tabB.isCurrentTabActive(), true)
    assert.equal(tabB.validateExecution().allowed, true)

    // Tab A receives CLAIM_LEASE from Tab B and safely relinquishes capability
    assert.equal(tabA.isCurrentTabActive(), false)
    assert.equal(tabA.getActiveTabId(), 'tab_B')
    assert.equal(tabA.getActiveLeaseToken(), 'lease_token_B')

    const checkA = tabA.validateExecution()
    assert.equal(checkA.allowed, false)
    assert.match(checkA.reason || '', /tab 'tab_B'/i)

    // 3. Tab B releases lease
    tabB.releaseActiveExecutor('Tab B closed')
    assert.equal(tabB.isCurrentTabActive(), false)
    assert.equal(tabA.getActiveTabId(), null)
  } finally {
    tabA.destroy()
    tabB.destroy()
  }
})

// ── 4. LEASE EXPIRY & RELINQUISHMENT ────────────────────────────────────

test('ExecutorCoordinator relinquishes capability when lease expires', async () => {
  const coord = new ExecutorCoordinator({
    tabId: 'tab_expiring',
    broadcastChannelFactory: (name) => new MockBroadcastChannel(name),
    storage: new MockStorage() as any,
    leaseTtlMs: 50, // Short TTL for test
    heartbeatIntervalMs: 10000, // Heartbeat delayed so expiry fires
  })

  try {
    coord.claimActiveExecutor('lease_short', 50)
    assert.equal(coord.isCurrentTabActive(), true)

    // Wait for lease to expire
    await new Promise((resolve) => setTimeout(resolve, 80))

    assert.equal(coord.isCurrentTabActive(), false)
    const check = coord.validateExecution()
    assert.equal(check.allowed, false)
    assert.match(check.reason || '', /not the active executor/i)
  } finally {
    coord.destroy()
  }
})

// ── 5. INTEGRATION WITH LEASE TOKEN MANAGER & RPC RECEIVER ───────────────

test('RPC receiver enforces active executor leasing and rejects inactive tab execution', async () => {
  const leaseManager = new LeaseTokenManager()
  const coord = new ExecutorCoordinator({
    tabId: 'tab_inactive_worker',
    broadcastChannelFactory: (name) => new MockBroadcastChannel(name),
    storage: new MockStorage() as any,
    leaseManager,
  })

  try {
    // Current tab is inactive
    assert.equal(coord.isCurrentTabActive(), false)

    // Create RPC handler requiring active executor lease
    const handler = createAssistantRpcHandler({
      expectedAgentIdentity: 'agent_primary',
      requireActiveExecutorLease: true,
      executorCoordinator: coord,
    })

    const payload = JSON.stringify({
      field: 'business_name',
    })

    const responseStr = await handler('highlight_field', {
      callerIdentity: 'agent_primary',
      payload,
      requestId: 'req_test_1',
      responseTimeout: 1000,
    })

    const receipt = JSON.parse(responseStr)
    assert.equal(receipt.status, 'rejected')
    assert.equal(receipt.receipt_state, 'rejected')
    assert.equal(receipt.error_code, 'not_active_lease_holder')
    assert.match(receipt.error || '', /not the active executor lease holder/i)

    // Now tab claims active executor lease
    coord.claimActiveExecutor('lease_valid_123')
    assert.equal(coord.isCurrentTabActive(), true)

    const validResponseStr = await handler('highlight_field', {
      callerIdentity: 'agent_primary',
      payload,
      requestId: 'req_test_2',
      responseTimeout: 1000,
    })

    const validReceipt = JSON.parse(validResponseStr)
    assert.equal(validReceipt.status, 'waiting_for_ui')
    assert.equal(validReceipt.receipt_state, 'waiting_for_ui')
    assert.equal(validReceipt.action, 'highlight_field')
    assert.equal(validReceipt.pointed_control, 'business_name')
  } finally {
    coord.destroy()
  }
})
