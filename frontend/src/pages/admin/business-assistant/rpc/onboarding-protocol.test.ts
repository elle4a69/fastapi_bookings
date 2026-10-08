// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'

import {
  executeRpcAction,
  normalizeSubtab,
  isSubtabAllowlisted,
  ControlEpochManager,
  LeaseTokenManager,
  ReceiptStateTracker,
} from './action-catalogue.ts'
import {
  createAssistantRpcHandler,
  ONBOARDING_RPC_METHODS,
  ALL_RPC_METHODS,
} from './rpc-receiver.ts'
import {
  isValidReceiptStateTransition,
  RECEIPT_STATE_TRANSITIONS,
  type RpcReceiverContext,
  type FillFieldsParams,
  type SaveFormParams,
} from './types.ts'

// ── 1. SUBTAB NORMALIZATION & ALLOWLIST TESTS ────────────────────────────

test('normalizeSubtab resolves canonical subtabs and friendly aliases', () => {
  assert.equal(normalizeSubtab('business_profile'), 'business_profile')
  assert.equal(normalizeSubtab('profile'), 'business_profile')
  assert.equal(normalizeSubtab('solo_provider'), 'solo_provider')
  assert.equal(normalizeSubtab('solo'), 'solo_provider')
  assert.equal(normalizeSubtab('primary_location'), 'primary_location')
  assert.equal(normalizeSubtab('location'), 'primary_location')
  assert.equal(normalizeSubtab('services_list'), 'services')
  assert.equal(normalizeSubtab('service'), 'service_details')
  assert.equal(normalizeSubtab('category'), 'category_details')
  assert.equal(normalizeSubtab('hours'), 'hours')
  assert.equal(normalizeSubtab('scheduling'), 'scheduling')
})

test('isSubtabAllowlisted accepts authorized subtabs and rejects unknown selectors', () => {
  assert.equal(isSubtabAllowlisted('business_profile'), true)
  assert.equal(isSubtabAllowlisted('solo_provider'), true)
  assert.equal(isSubtabAllowlisted('primary_location'), true)
  assert.equal(isSubtabAllowlisted('services'), true)
  assert.equal(isSubtabAllowlisted('categories'), true)
  assert.equal(isSubtabAllowlisted('unknown_random_tab'), false)
  assert.equal(isSubtabAllowlisted(''), false)
})

// ── 2. RECEIPT STATE TRANSITION & TRACKER TESTS ─────────────────────────

test('isValidReceiptStateTransition strictly enforces allowed progression', () => {
  assert.ok(RECEIPT_STATE_TRANSITIONS.received.includes('waiting_for_ui'))
  // Valid progression: received -> waiting_for_ui -> executing -> fields_staged -> saved
  assert.equal(isValidReceiptStateTransition('received', 'waiting_for_ui'), true)
  assert.equal(isValidReceiptStateTransition('received', 'executing'), true)
  assert.equal(isValidReceiptStateTransition('waiting_for_ui', 'executing'), true)
  assert.equal(isValidReceiptStateTransition('executing', 'fields_staged'), true)
  assert.equal(isValidReceiptStateTransition('executing', 'saved'), true)
  assert.equal(isValidReceiptStateTransition('fields_staged', 'saved'), true)

  // Rejections / Failures from any active state
  assert.equal(isValidReceiptStateTransition('received', 'rejected'), true)
  assert.equal(isValidReceiptStateTransition('received', 'failed'), true)
  assert.equal(isValidReceiptStateTransition('executing', 'rejected'), true)
  assert.equal(isValidReceiptStateTransition('executing', 'outcome_unknown'), true)

  // Disallowed backwards transitions from terminal states
  assert.equal(isValidReceiptStateTransition('saved', 'fields_staged'), false)
  assert.equal(isValidReceiptStateTransition('saved', 'executing'), false)
  assert.equal(isValidReceiptStateTransition('rejected', 'saved'), false)
  assert.equal(isValidReceiptStateTransition('failed', 'waiting_for_ui'), false)
  assert.equal(isValidReceiptStateTransition('outcome_unknown', 'saved'), false)
})

test('ReceiptStateTracker manages progression and throws on invalid transitions', () => {
  const tracker = new ReceiptStateTracker('received')
  assert.equal(tracker.getState(), 'received')

  tracker.transitionTo('waiting_for_ui', 'Form mounting in background')
  assert.equal(tracker.getState(), 'waiting_for_ui')

  tracker.transitionTo('executing', 'Staging fields')
  assert.equal(tracker.getState(), 'executing')

  tracker.transitionTo('fields_staged', 'Values placed in buffer')
  assert.equal(tracker.getState(), 'fields_staged')

  tracker.transitionTo('saved', 'Committed to database')
  assert.equal(tracker.getState(), 'saved')

  // Cannot transition from terminal 'saved'
  assert.throws(
    () => tracker.transitionTo('fields_staged'),
    /Invalid receipt state transition/i,
  )

  const history = tracker.getHistory()
  assert.equal(history.length, 5)
  assert.equal(history[0].state, 'received')
  assert.equal(history[4].state, 'saved')
})

// ── 3. CONTROL EPOCH TRACKING & STALE COMMAND REJECTION ─────────────────

test('ControlEpochManager increments epoch on manual takeover and rejects stale epochs', () => {
  const epochMgr = new ControlEpochManager()
  assert.equal(epochMgr.getEpoch(), 1)

  // First check passes
  const validCheck1 = epochMgr.validateEpoch(1)
  assert.equal(validCheck1.valid, true)

  // User takes over via manual interaction
  const newEpoch = epochMgr.advanceEpoch('User typed in business name field')
  assert.equal(newEpoch, 2)
  assert.equal(epochMgr.getEpoch(), 2)

  // Stale epoch (generated by agent before takeover) must be rejected
  const staleCheck = epochMgr.validateEpoch(1)
  assert.equal(staleCheck.valid, false)
  assert.match(staleCheck.reason ?? '', /stale control epoch/i)

  // Up-to-date epoch passes
  const freshCheck = epochMgr.validateEpoch(2)
  assert.equal(freshCheck.valid, true)
})

test('executeRpcAction rejects actions with stale control epoch', async () => {
  const epochMgr = new ControlEpochManager()
  epochMgr.advanceEpoch('User clicked manual takeover') // Epoch is now 2

  const context: RpcReceiverContext = {}

  // Agent tries to execute fill_fields using old epoch (1)
  const staleReceipt = await executeRpcAction(
    'fill_fields',
    {
      control_epoch: 1,
      fields: { name: 'Elena Nails Studio' },
    },
    {
      actionId: 'act_stale_1',
      callerIdentity: 'agent_assistant_primary',
      context,
      epochManager: epochMgr,
    },
  )

  assert.equal(staleReceipt.status, 'rejected')
  assert.equal(staleReceipt.receipt_state, 'rejected')
  assert.equal(staleReceipt.error_code, 'stale_control_epoch')
  assert.match(staleReceipt.error ?? '', /stale control epoch/i)
  assert.equal(staleReceipt.control_epoch, 2)
})

// ── 4. SINGLE-TAB LEASE TOKEN VALIDATION TESTS ──────────────────────────

test('LeaseTokenManager enforces single-tab active executor lease', () => {
  const leaseMgr = new LeaseTokenManager()
  assert.equal(leaseMgr.getActiveLease().token, null)

  // Tab Alpha claims active lease
  const tokenAlpha = leaseMgr.acquireLease('lease_tab_alpha', 60000)
  assert.equal(tokenAlpha, 'lease_tab_alpha')
  assert.equal(leaseMgr.getActiveLease().token, 'lease_tab_alpha')

  // Command presenting matching token passes
  const validCheck = leaseMgr.validateLease('lease_tab_alpha')
  assert.equal(validCheck.valid, true)

  // Command from another tab or mismatched participant is rejected
  const invalidCheck = leaseMgr.validateLease('lease_tab_beta')
  assert.equal(invalidCheck.valid, false)
  assert.match(invalidCheck.reason ?? '', /invalid lease token/i)

  // Command missing lease token while lease is active is rejected
  const missingCheck = leaseMgr.validateLease(undefined)
  assert.equal(missingCheck.valid, false)
  assert.match(missingCheck.reason ?? '', /missing required lease token/i)
})

test('executeRpcAction rejects actions with invalid or non-leased tokens', async () => {
  const leaseMgr = new LeaseTokenManager()
  leaseMgr.acquireLease('active_owner_tab_token', 60000)

  const context: RpcReceiverContext = {}

  // Mismatched tab token
  const receipt = await executeRpcAction(
    'navigate_subtab',
    {
      subtab: 'solo_provider',
      lease_token: 'stale_background_tab_token',
    },
    {
      actionId: 'act_lease_mismatch',
      callerIdentity: 'agent_assistant_primary',
      context,
      leaseManager: leaseMgr,
    },
  )

  assert.equal(receipt.status, 'rejected')
  assert.equal(receipt.receipt_state, 'rejected')
  assert.equal(receipt.error_code, 'invalid_lease_token')
  assert.match(receipt.error ?? '', /invalid lease token/i)
})

// ── 5. TYPED ONBOARDING ACTIONS EXECUTION & RECEIPT STATES ──────────────

test('executeRpcAction navigate_subtab navigates to subtab and returns waiting_for_ui', async () => {
  let navigatedSubtab = ''
  let navigatedRoute = ''

  const context: RpcReceiverContext = {
    onNavigate: (route) => {
      navigatedRoute = route
    },
    onNavigateSubtab: (subtab, _route) => {
      navigatedSubtab = subtab
      if (_route) navigatedRoute = _route
      return { success: true, active_subtab: subtab }
    },
  }

  const receipt = await executeRpcAction(
    'navigate_subtab',
    {
      subtab: 'profile', // Alias for business_profile
      route: '/admin/settings/business',
    },
    {
      actionId: 'act_nav_subtab_1',
      callerIdentity: 'agent_assistant_primary',
      context,
    },
  )

  assert.equal(receipt.status, 'waiting_for_ui')
  assert.equal(receipt.receipt_state, 'waiting_for_ui')
  assert.equal(receipt.active_subtab, 'business_profile')
  assert.equal(receipt.resulting_page, '/admin/settings/business')
  assert.equal(navigatedSubtab, 'business_profile')
  assert.equal(navigatedRoute, '/admin/settings/business')
})

test('executeRpcAction open_modal and close_modal manage modal lifecycle', async () => {
  let openModalId = ''
  let openEntityId: any = null
  let modalClosed = false

  const context: RpcReceiverContext = {
    onOpenModal: (id, entityId) => {
      openModalId = id
      openEntityId = entityId
      return { success: true, active_modal: id }
    },
    onCloseModal: () => {
      modalClosed = true
      return { success: true }
    },
  }

  // 1. Open modal
  const openReceipt = await executeRpcAction(
    'open_modal',
    {
      modal_id: 'service_create',
      entity_id: 42,
    },
    {
      actionId: 'act_open_modal_1',
      callerIdentity: 'agent_assistant_primary',
      context,
    },
  )

  assert.equal(openReceipt.status, 'waiting_for_ui')
  assert.equal(openReceipt.receipt_state, 'waiting_for_ui')
  assert.equal(openReceipt.active_modal, 'service_create')
  assert.equal(openReceipt.details?.entity_id, 42)
  assert.equal(openModalId, 'service_create')
  assert.equal(openEntityId, 42)

  // 2. Close modal
  const closeReceipt = await executeRpcAction(
    'close_modal',
    {},
    {
      actionId: 'act_close_modal_1',
      callerIdentity: 'agent_assistant_primary',
      context,
    },
  )

  assert.equal(closeReceipt.status, 'waiting_for_ui')
  assert.equal(closeReceipt.receipt_state, 'waiting_for_ui')
  assert.equal(closeReceipt.active_modal, null)
  assert.equal(modalClosed, true)
})

test('executeRpcAction fill_fields stages fields with staging guard and returns fields_staged (NOT saved)', async () => {
  let receivedParams: FillFieldsParams | null = null

  const context: RpcReceiverContext = {
    onFillFields: (params) => {
      receivedParams = params
      return {
        success: true,
        staged_fields: Object.keys(params.fields as Record<string, unknown>),
      }
    },
  }

  const receipt = await executeRpcAction(
    'fill_fields',
    {
      form_id: 'business_settings',
      fields: {
        name: 'Elena Organic Beauty',
        phone: '0412 345 678',
        email: 'elena@beauty.com.au',
      },
      field_origins: {
        name: 'agent_spoken',
        phone: 'agent_inferred',
        email: 'user_explicit',
      },
      staging_guard: true,
      prevent_autosave: true,
    },
    {
      actionId: 'act_fill_1',
      callerIdentity: 'agent_assistant_primary',
      context,
    },
  )

  // Crucial contract: staging is strictly discrete from persistence
  assert.equal(receipt.status, 'fields_staged')
  assert.equal(receipt.receipt_state, 'fields_staged')
  assert.equal(receipt.form_id, 'business_settings')
  assert.equal(receipt.field_count, 3)
  assert.deepEqual(receipt.staged_fields, ['name', 'phone', 'email'])
  assert.equal(receipt.details?.staging_guard, true)
  assert.equal(receipt.details?.prevent_autosave, true)

  assert.ok(receivedParams)
  assert.equal((receivedParams as any).staging_guard, true)
  assert.equal((receivedParams as any).prevent_autosave, true)
})

test('executeRpcAction select_option selects dropdown item and returns fields_staged', async () => {
  let selectedOption: any = null

  const context: RpcReceiverContext = {
    onSelectOption: (params) => {
      selectedOption = params.option_id
      return { success: true, selected: params.option_id }
    },
  }

  const receipt = await executeRpcAction(
    'select_option',
    {
      form_id: 'business_settings',
      field_id: 'primary-location-timezone',
      option_id: 'Australia/Melbourne',
    },
    {
      actionId: 'act_select_opt_1',
      callerIdentity: 'agent_assistant_primary',
      context,
    },
  )

  assert.equal(receipt.status, 'fields_staged')
  assert.equal(receipt.receipt_state, 'fields_staged')
  assert.equal(receipt.form_id, 'business_settings')
  assert.equal(receipt.details?.selected_option_id, 'Australia/Melbourne')
  assert.equal(selectedOption, 'Australia/Melbourne')
})

test('executeRpcAction validate_form triggers form validation without saving', async () => {
  let validatedFormId = ''

  const context: RpcReceiverContext = {
    onValidateForm: (params) => {
      validatedFormId = params.form_id ?? ''
      return {
        valid: true,
        errors: {},
      }
    },
  }

  const receipt = await executeRpcAction(
    'validate_form',
    { form_id: 'catalog_services' },
    {
      actionId: 'act_validate_1',
      callerIdentity: 'agent_assistant_primary',
      context,
    },
  )

  assert.equal(receipt.status, 'fields_staged')
  assert.equal(receipt.receipt_state, 'fields_staged')
  assert.equal(receipt.validation_valid, true)
  assert.equal(validatedFormId, 'catalog_services')
})

test('executeRpcAction save_form commits staged changes and returns saved state', async () => {
  let saveParamsReceived: SaveFormParams | null = null

  const context: RpcReceiverContext = {
    onSaveForm: (params) => {
      saveParamsReceived = params
      return {
        success: true,
        entity: {
          entity_type: 'tenant_profile',
          id: 101,
          revision: 3,
        },
      }
    },
  }

  const receipt = await executeRpcAction(
    'save_form',
    {
      form_id: 'business_settings',
      target_entity_id: 101,
      authorisation_nonce: 'nonce_auth_test_999',
    },
    {
      actionId: 'act_save_1',
      callerIdentity: 'agent_assistant_primary',
      context,
    },
  )

  assert.equal(receipt.status, 'saved')
  assert.equal(receipt.receipt_state, 'saved')
  assert.equal(receipt.form_id, 'business_settings')
  assert.deepEqual(receipt.persisted_entity, {
    entity_type: 'tenant_profile',
    id: 101,
    revision: 3,
  })
  assert.equal(
    (saveParamsReceived as SaveFormParams | null)?.authorisation_nonce,
    'nonce_auth_test_999',
  )
})

test('executeRpcAction manual_takeover increments epoch and records takeover details', async () => {
  const epochMgr = new ControlEpochManager()
  assert.equal(epochMgr.getEpoch(), 1)

  let takeoverNotified = false

  const context: RpcReceiverContext = {
    onManualTakeover: (params) => {
      takeoverNotified = true
      return { epoch: params.reason ? 2 : 1 }
    },
  }

  const receipt = await executeRpcAction(
    'manual_takeover',
    {
      reason: 'User clicked "I will do this part"',
      source: 'ui_button',
    },
    {
      actionId: 'act_takeover_1',
      callerIdentity: 'user_browser_local',
      context,
      epochManager: epochMgr,
    },
  )

  assert.equal(receipt.status, 'saved')
  assert.equal(receipt.receipt_state, 'saved')
  assert.equal(receipt.control_epoch, 2)
  assert.equal(epochMgr.getEpoch(), 2)
  assert.equal(receipt.details?.previous_epoch, 1)
  assert.equal(receipt.details?.new_epoch, 2)
  assert.equal(receipt.details?.source, 'ui_button')
  assert.equal(takeoverNotified, true)
})

// ── 6. END-TO-END RPC RECEIVER & EVENT BUS INTEGRATION ─────────────────

test('createAssistantRpcHandler executes onboarding action and dispatches typed event', async () => {
  let receivedReceipt: any = null
  let stagedCount = 0

  const context: RpcReceiverContext = {
    expectedAgentIdentity: 'agent_assistant_primary',
    onFillFields: (params) => {
      stagedCount = Object.keys(params.fields as Record<string, unknown>).length
      return {
        success: true,
        staged_fields: Object.keys(params.fields as Record<string, unknown>),
      }
    },
    onReceipt: (receipt) => {
      receivedReceipt = receipt
    },
  }

  const handler = createAssistantRpcHandler(context)

  const rawJson = await handler('assistant_ui_action', {
    callerIdentity: 'agent_assistant_primary',
    requestId: 'rpc_req_test_100',
    payload: JSON.stringify({
      action: 'fill_fields',
      form_id: 'services_form',
      fields: {
        name: 'Deluxe Manicure',
        duration_mins: 45,
        price: 65,
      },
    }),
    responseTimeout: 5000,
  })

  const parsedReceipt = JSON.parse(rawJson)
  assert.equal(parsedReceipt.status, 'fields_staged')
  assert.equal(parsedReceipt.receipt_state, 'fields_staged')
  assert.equal(parsedReceipt.field_count, 3)
  assert.equal(stagedCount, 3)
  assert.ok(receivedReceipt)
  assert.equal(receivedReceipt.action_id, 'rpc_req_test_100')
})

test('ONBOARDING_RPC_METHODS catalogue contains all required typed actions', () => {
  assert.ok(ALL_RPC_METHODS.length >= ONBOARDING_RPC_METHODS.length)
  const required = [
    'navigate_subtab',
    'select_subtab',
    'open_modal',
    'close_modal',
    'fill_fields',
    'set_fields',
    'select_option',
    'validate_form',
    'save_form',
    'manual_takeover',
    'point_to_control',
    'read_form_state',
  ]

  for (const method of required) {
    assert.ok(
      ONBOARDING_RPC_METHODS.includes(method as any),
      `Expected method '${method}' in ONBOARDING_RPC_METHODS`,
    )
  }
})
