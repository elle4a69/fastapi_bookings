// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'

import { validatePublicationGate } from './publication-gate.ts'
import { executeRpcAction } from '../business-assistant/rpc/action-catalogue.ts'

// ── 1. STRICT OWNER PUBLICATION GATE TESTS ──────────────────────────────

test('validatePublicationGate rejects automated attempts from voice assistants or RPC', () => {
  const result = validatePublicationGate({
    isOwner: true,
    isStale: false,
    isAutomated: true, // Automated call attempt
    proposalId: 10,
  })

  assert.equal(result.permitted, false)
  assert.equal(result.errorCode, 'AUTOMATED_ATTEMPT_BLOCKED')
  assert.match(result.reason ?? '', /automated publication via voice assistant or rpc is strictly prohibited/i)
})

test('validatePublicationGate rejects non-owner users', () => {
  const result = validatePublicationGate({
    isOwner: false, // Provider or Manager without owner authority
    isStale: false,
    isAutomated: false,
    proposalId: 10,
  })

  assert.equal(result.permitted, false)
  assert.equal(result.errorCode, 'UNAUTHORIZED_ROLE')
  assert.match(result.reason ?? '', /only authenticated business owners have permission/i)
})

test('validatePublicationGate rejects stale proposals', () => {
  const result = validatePublicationGate({
    isOwner: true,
    isStale: true, // Proposal is stale due to conflicting changes
    isAutomated: false,
    proposalId: 10,
  })

  assert.equal(result.permitted, false)
  assert.equal(result.errorCode, 'STALE_PROPOSAL')
  assert.match(result.reason ?? '', /website configuration has advanced/i)
})

test('validatePublicationGate rejects missing or invalid proposal IDs', () => {
  const result = validatePublicationGate({
    isOwner: true,
    isStale: false,
    isAutomated: false,
    proposalId: 0,
  })

  assert.equal(result.permitted, false)
  assert.equal(result.errorCode, 'INVALID_PROPOSAL')
})

test('validatePublicationGate permits authenticated manual owner action on fresh proposal', () => {
  const result = validatePublicationGate({
    isOwner: true,
    isStale: false,
    isAutomated: false,
    proposalId: 15,
  })

  assert.equal(result.permitted, true)
  assert.equal(result.errorCode, undefined)
  assert.equal(result.reason, undefined)
})

// ── 2. RPC SECURITY REJECTION TESTS ─────────────────────────────────────

test('executeRpcAction strictly blocks and rejects "publish" and "publish_website" calls', async () => {
  const options = {
    actionId: 'req_test_pub_1',
    callerIdentity: 'agent_assistant_primary',
    context: {},
  }

  const receipt1 = await executeRpcAction('publish', {}, options)
  assert.equal(receipt1.status, 'rejected')
  assert.match(receipt1.error ?? '', /automated publication or approval via assistant rpc is strictly prohibited/i)

  const receipt2 = await executeRpcAction('publish_website', { is_published: true }, options)
  assert.equal(receipt2.status, 'rejected')
  assert.match(receipt2.error ?? '', /automated publication or approval via assistant rpc is strictly prohibited/i)
})

test('executeRpcAction strictly blocks and rejects "approve" and "approve_proposal" calls', async () => {
  const options = {
    actionId: 'req_test_appr_1',
    callerIdentity: 'agent_assistant_primary',
    context: {},
  }

  const receipt1 = await executeRpcAction('approve', { proposal_id: 12 }, options)
  assert.equal(receipt1.status, 'rejected')
  assert.match(receipt1.error ?? '', /automated publication or approval via assistant rpc is strictly prohibited/i)

  const receipt2 = await executeRpcAction('approve_proposal', { proposal_id: 12 }, options)
  assert.equal(receipt2.status, 'rejected')
  assert.match(receipt2.error ?? '', /automated publication or approval via assistant rpc is strictly prohibited/i)
})

// ── 3. ASSISTANT RPC CHANGE REVIEW DRAWER TESTS ─────────────────────────

test('executeRpcAction change_review_drawer opens drawer with exact proposal ID', async () => {
  let capturedState: string | undefined
  let capturedProposalId: number | undefined

  const context = {
    onChangeReviewDrawer: (state: 'open' | 'closed' | 'toggle', proposalId?: number) => {
      capturedState = state
      capturedProposalId = proposalId
      return state === 'closed' ? 'closed' : 'open'
    },
  }

  const receipt = await executeRpcAction(
    'change_review_drawer',
    { state: 'open', proposal_id: 105 },
    {
      actionId: 'req_drawer_1',
      callerIdentity: 'agent_assistant_primary',
      context,
    },
  )

  assert.equal(receipt.status, 'success')
  assert.equal(receipt.action, 'change_review_drawer')
  assert.equal(receipt.drawer_state, 'open')
  assert.equal(receipt.details?.proposal_id, 105)
  assert.equal(capturedState, 'open')
  assert.equal(capturedProposalId, 105)
})
