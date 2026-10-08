// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import assert from 'node:assert/strict'
// @ts-expect-error Node's test-runner types are intentionally not part of the app build.
import test from 'node:test'

import {
  FormAdapterRegistry,
  formAdapterRegistry,
  type OnboardingFormAdapter,
} from './registry.ts'
import { BusinessSettingsAdapter } from './business-settings-adapter.ts'
import { CatalogServicesAdapter } from './catalog-services-adapter.ts'
import { executeRpcAction } from '../rpc/action-catalogue.ts'

// ── 1. REGISTRY TESTS ────────────────────────────────────────────────────────

test('FormAdapterRegistry manages registration, route matching, and lifecycle', () => {
  const registry = new FormAdapterRegistry()
  assert.equal(registry.getAllAdapters().length, 0)

  const mockAdapter: OnboardingFormAdapter = {
    form_id: 'test_form',
    route: '/admin/test',
    active_subtab: 'general',
    supported_fields: ['title', 'description'],
    is_ready: () => true,
    stage_field: (_field, _value) => ({ staged: true }),
    get_field_state: (_field) => ({ value: 'test', staged: false }),
    get_all_staged_fields: () => ({}),
    validate: async () => ({ valid: true }),
    save: async () => ({
      success: true,
      entity: { entity_type: 'test', id: 1, revision: 1 },
    }),
    cancel_staging: () => {},
  }

  const unregister = registry.registerAdapter(mockAdapter)
  assert.equal(registry.getAllAdapters().length, 1)
  assert.equal(registry.getAdapter('test_form'), mockAdapter)
  assert.equal(registry.getAdapter('test-form'), mockAdapter) // kebab-case alias
  assert.equal(registry.getAdapterForRoute('/admin/test'), mockAdapter)
  assert.equal(registry.getAdapterForRoute('/admin/test?foo=bar'), mockAdapter)
  assert.equal(registry.getActiveAdapter(), mockAdapter)

  unregister()
  assert.equal(registry.getAllAdapters().length, 0)
  assert.equal(registry.getAdapter('test_form'), undefined)
  assert.equal(registry.getAdapterForRoute('/admin/test'), undefined)
})

test('FormAdapterRegistry singleton instance is accessible and retains registered adapters', () => {
  assert.ok(formAdapterRegistry)
  const businessAdapter = formAdapterRegistry.getAdapter('business_settings')
  assert.ok(businessAdapter, 'business_settings adapter must be registered')
  assert.equal(businessAdapter?.form_id, 'business_settings')

  const catalogAdapter = formAdapterRegistry.getAdapter('catalog_services')
  assert.ok(catalogAdapter, 'catalog_services adapter must be registered')
  assert.equal(catalogAdapter?.form_id, 'catalog_services')

  const matchedRoute = formAdapterRegistry.getAdapterForRoute('/admin/settings/business')
  assert.equal(matchedRoute?.form_id, 'business_settings')
})

// ── 2. BUSINESS SETTINGS ADAPTER & AUTOSAVE STAGING GUARD TESTS ──────────────

test('BusinessSettingsAdapter supports all audited fields and subtab transitions', () => {
  const adapter = new BusinessSettingsAdapter()

  assert.equal(adapter.form_id, 'business_settings')
  assert.equal(adapter.route, '/admin/settings/business')
  assert.equal(adapter.active_subtab, 'business_profile')
  assert.ok(adapter.is_ready())

  // Verify core audited fields are in supported_fields
  const auditedFields = [
    'business_name',
    'company_number',
    'industry',
    'timezone',
    'currency',
    'support_email',
    'support_phone',
    'display_name',
    'bio',
    'title',
    'phone',
    'email',
    'address_line1',
    'city',
    'state',
    'postal_code',
    'country',
    'allow_in_call',
    'allow_out_call',
  ]
  for (const field of auditedFields) {
    assert.ok(
      adapter.supported_fields.includes(field),
      `Field ${field} must be supported by BusinessSettingsAdapter`,
    )
  }

  // Subtab switching
  assert.equal(adapter.set_subtab('solo_provider'), true)
  assert.equal(adapter.active_subtab, 'solo_provider')
  assert.equal(adapter.set_subtab('location'), true)
  assert.equal(adapter.active_subtab, 'primary_location')
  assert.equal(adapter.set_subtab('invalid_subtab'), false)
})

test('BusinessSettingsAdapter Autosave Staging Guard prevents premature database persistence', async () => {
  let saveCount = 0
  let savedPayload: unknown = null

  const adapter = new BusinessSettingsAdapter({
    saveHandler: async (payload) => {
      saveCount += 1
      savedPayload = payload
      return { id: 'business_1', revision: 2 }
    },
  })

  // 1. Stage spoken candidate fields
  const stage1 = adapter.stage_field('business_name', 'Elena Beauty Studio', 'agent_spoken')
  assert.equal(stage1.staged, true)
  assert.equal(saveCount, 0, 'Autosave must NOT fire while staging fields')

  const stage2 = adapter.stage_field('support_email', 'contact@elenabeauty.com', 'agent_spoken')
  assert.equal(stage2.staged, true)
  assert.equal(saveCount, 0, 'Autosave must NOT fire on subsequent staged fields')

  // 2. Check staging states
  const nameState = adapter.get_field_state('business_name')
  assert.equal(nameState.value, 'Elena Beauty Studio')
  assert.equal(nameState.staged, true)
  assert.equal(nameState.origin, 'agent_spoken')

  const allStaged = adapter.get_all_staged_fields()
  assert.equal(Object.keys(allStaged).length, 2)
  assert.equal(allStaged.business_name.value, 'Elena Beauty Studio')

  // 3. Cancelling staging clears buffer without saving
  adapter.cancel_staging()
  assert.equal(Object.keys(adapter.get_all_staged_fields()).length, 0)
  assert.equal(saveCount, 0)
  assert.equal(adapter.get_field_state('business_name').staged, false)

  // 4. Re-stage and explicit save authoritatively commits
  adapter.stage_field('business_name', 'Elena Hair & Spa', 'agent_spoken')
  adapter.stage_field('support_email', 'info@elenahair.com', 'agent_spoken')

  const saveResult = await adapter.save('auth_nonce_123')
  assert.equal(saveResult.success, true)
  assert.equal(saveCount, 1, 'Authoritative save must trigger persistence')
  assert.deepEqual(savedPayload, {
    profile: {
      business_name: 'Elena Hair & Spa',
      support_email: 'info@elenahair.com',
    },
    provider: {},
    location: {},
  })

  // Staged buffer is cleared after successful save
  assert.equal(Object.keys(adapter.get_all_staged_fields()).length, 0)
  const committedState = adapter.get_field_state('business_name')
  assert.equal(committedState.value, 'Elena Hair & Spa')
  assert.equal(committedState.staged, false)
})

test('BusinessSettingsAdapter validates business rules', async () => {
  const adapter = new BusinessSettingsAdapter()

  // Business name cannot be empty
  adapter.stage_field('business_name', '   ')
  let valRes = await adapter.validate()
  assert.equal(valRes.valid, false)
  assert.ok(valRes.errors?.business_name)

  // Invalid email format
  adapter.stage_field('business_name', 'Valid Studio')
  adapter.stage_field('support_email', 'not-an-email')
  valRes = await adapter.validate()
  assert.equal(valRes.valid, false)
  assert.ok(valRes.errors?.support_email)

  // Delivery modes invariant: cannot disable both in-call and out-call
  adapter.stage_field('support_email', 'valid@studio.com')
  adapter.stage_field('allow_in_call', false)
  adapter.stage_field('allow_out_call', false)
  valRes = await adapter.validate()
  assert.equal(valRes.valid, false)
  assert.ok(valRes.errors?.delivery_modes)

  // Enabling at least one delivery mode passes validation
  adapter.stage_field('allow_in_call', true)
  valRes = await adapter.validate()
  assert.equal(valRes.valid, true)
})

// ── 3. CATALOG SERVICES ADAPTER (CREATE & EDIT MODES) TESTS ──────────────────

test('CatalogServicesAdapter creation mode enforces manual save and validates invariants', async () => {
  let createdCount = 0
  let createdPayload: unknown = null

  const adapter = new CatalogServicesAdapter({
    initialMode: 'create',
    saveHandler: async (payload, mode) => {
      assert.equal(mode, 'create')
      createdCount += 1
      createdPayload = payload
      return { id: 'svc_999', revision: 1 }
    },
  })

  assert.equal(adapter.form_id, 'catalog_services')
  assert.equal(adapter.route, '/admin/catalog/services')
  assert.equal(adapter.isCreating, true)
  assert.equal(adapter.selectedServiceId, null)

  // Validation fails when service name is blank
  let valRes = await adapter.validate()
  assert.equal(valRes.valid, false)
  assert.ok(valRes.errors?.name)

  // Validation fails when both delivery modes are false
  adapter.stage_field('service_name', 'Deluxe Manicure')
  adapter.stage_field('allow_in_call', false)
  adapter.stage_field('allow_out_call', false)
  valRes = await adapter.validate()
  assert.equal(valRes.valid, false)
  assert.ok(valRes.errors?.delivery_modes)

  // Enabling allow_in_call satisfies delivery mode invariant
  adapter.stage_field('allow_in_call', true)
  adapter.stage_field('price', 85)
  adapter.stage_field('duration', 45)
  valRes = await adapter.validate()
  assert.equal(valRes.valid, true)

  // Explicit save creates service and transitions adapter into edit mode
  const saveRes = await adapter.save()
  assert.equal(saveRes.success, true)
  assert.equal(createdCount, 1)
  assert.ok(createdPayload)
  assert.equal(saveRes.entity?.id, 'svc_999')
  assert.equal(saveRes.entity?.entity_type, 'service')

  // Adapter transitioned to edit mode for the newly created service
  assert.equal(adapter.isCreating, false)
  assert.equal(adapter.selectedServiceId, 'svc_999')
})

test('CatalogServicesAdapter edit mode protects against debounced autosave via staging guard', async () => {
  let updateCount = 0
  let updatedPayload: unknown = null

  const adapter = new CatalogServicesAdapter({
    initialMode: 'edit',
    selectedServiceId: 'svc_100',
    initialValues: {
      name: 'Classic Pedicure',
      price: 60,
      duration: 30,
      allow_in_call: true,
      allow_out_call: false,
    },
    saveHandler: async (payload, mode, serviceId) => {
      assert.equal(mode, 'edit')
      assert.equal(serviceId, 'svc_100')
      updateCount += 1
      updatedPayload = payload
      return { id: 'svc_100', revision: 3 }
    },
  })

  assert.equal(adapter.isCreating, false)
  assert.equal(adapter.selectedServiceId, 'svc_100')

  // Staging changes does NOT fire the update handler
  adapter.stage_field('price', 75, 'agent_spoken')
  adapter.stage_field('duration', 40, 'agent_spoken')
  adapter.stage_field('allow_out_call', true, 'agent_spoken')
  assert.equal(updateCount, 0, 'Autosave must NOT fire during speech staging')

  const priceState = adapter.get_field_state('price')
  assert.equal(priceState.value, 75)
  assert.equal(priceState.staged, true)

  // Authoritative save persists changes
  const saveRes = await adapter.save()
  assert.equal(saveRes.success, true)
  assert.equal(updateCount, 1)
  assert.equal((updatedPayload as any).price, 75)
  assert.equal((updatedPayload as any).duration, 40)
  assert.equal((updatedPayload as any).allow_out_call, true)

  // Staging buffer is cleared
  assert.equal(adapter.get_field_state('price').staged, false)
})

// ── 4. RPC RECEIVER & ACTION CATALOGUE WIRING TESTS ──────────────────────────

test('Action catalogue delegates fill_fields, validate_form, save_form to registered adapter', async () => {
  let savedNonce: string | undefined
  let savedProfile: unknown = null

  const customBusinessAdapter = new BusinessSettingsAdapter({
    saveHandler: async (payload, nonce) => {
      savedNonce = nonce
      savedProfile = payload.profile
      return { id: 'tenant_biz_42', revision: 5 }
    },
  })

  // Register on singleton
  const unregister = formAdapterRegistry.registerAdapter(customBusinessAdapter)
  formAdapterRegistry.setActiveAdapter('business_settings')

  try {
    // 1. RPC fill_fields
    const fillReceipt = await executeRpcAction(
      'fill_fields',
      {
        form_id: 'business_settings',
        fields: {
          business_name: 'Staged by RPC Voice',
          support_phone: '+61 400 123 456',
        },
      },
      { actionId: 'act_fill_1', callerIdentity: 'agent_onboarding', context: {} },
    )

    assert.equal(fillReceipt.status, 'fields_staged')
    assert.equal(fillReceipt.receipt_state, 'fields_staged')
    assert.deepEqual(fillReceipt.staged_fields, ['business_name', 'support_phone'])

    const stagedName = customBusinessAdapter.get_field_state('business_name')
    assert.equal(stagedName.value, 'Staged by RPC Voice')
    assert.equal(stagedName.staged, true)

    // 2. RPC validate_form
    const validateReceipt = await executeRpcAction(
      'validate_form',
      { form_id: 'business_settings' },
      { actionId: 'act_val_1', callerIdentity: 'agent_onboarding', context: {} },
    )
    assert.equal(validateReceipt.status, 'fields_staged')
    assert.equal(validateReceipt.validation_valid, true)

    // 3. RPC save_form
    const saveReceipt = await executeRpcAction(
      'save_form',
      {
        form_id: 'business_settings',
        authorisation_nonce: 'voice_auth_token_99',
      },
      { actionId: 'act_save_1', callerIdentity: 'agent_onboarding', context: {} },
    )

    assert.equal(saveReceipt.status, 'saved')
    assert.equal(saveReceipt.receipt_state, 'saved')
    assert.equal(saveReceipt.persisted_entity?.id, 'tenant_biz_42')
    assert.equal(savedNonce, 'voice_auth_token_99')
    assert.equal((savedProfile as any)?.business_name, 'Staged by RPC Voice')

    // 4. RPC navigate_subtab
    const navReceipt = await executeRpcAction(
      'navigate_subtab',
      {
        subtab: 'solo_provider',
        route: '/admin/settings/business',
      },
      { actionId: 'act_nav_1', callerIdentity: 'agent_onboarding', context: {} },
    )
    assert.equal(navReceipt.status, 'waiting_for_ui')
    assert.equal(navReceipt.active_subtab, 'solo_provider')
    assert.equal(customBusinessAdapter.active_subtab, 'solo_provider')
  } finally {
    unregister()
  }
})
