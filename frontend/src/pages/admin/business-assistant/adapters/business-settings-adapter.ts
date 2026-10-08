import type { FieldOrigin } from '../rpc/types.ts'
import type { OnboardingFormAdapter } from './registry.ts'

export const BUSINESS_SETTINGS_SUBTABS = [
  'business_profile',
  'solo_provider',
  'primary_location',
] as const

export type BusinessSettingsSubtab = (typeof BUSINESS_SETTINGS_SUBTABS)[number]

export const BUSINESS_SETTINGS_SUPPORTED_FIELDS: readonly string[] = [
  // Business Profile
  'business_name',
  'company_number',
  'industry',
  'timezone',
  'currency',
  'support_email',
  'support_phone',
  'name',
  'email',
  'phone',
  'address',
  'business_email',
  'business_phone',
  'business_address',

  // Solo Provider
  'display_name',
  'bio',
  'title',
  'solo_provider_name',
  'solo_provider_email',
  'solo_provider_phone',
  'solo_provider_bio',
  'allow_in_call',
  'allow_out_call',
  'out_call_radius_km',
  'base_outcall_surcharge',
  'per_km_fee',
  'turnaround_buffer_mins',

  // Primary Location
  'address_line1',
  'address_line2',
  'city',
  'state',
  'postal_code',
  'country',
  'primary_location_name',
  'primary_location_timezone',
  'primary_location_address',
  'primary_location_street',
  'primary_location_city',
  'primary_location_state',
  'primary_location_postcode',
  'street',
  'postcode',
  'is_client_hidden',
] as const

export interface BusinessSettingsSavePayload {
  profile?: Record<string, unknown>
  provider?: Record<string, unknown>
  location?: Record<string, unknown>
}

export interface BusinessSettingsAdapterOptions {
  initialSubtab?: BusinessSettingsSubtab
  initialValues?: Record<string, unknown>
  saveHandler?: (
    payload: BusinessSettingsSavePayload,
    nonce?: string,
  ) => Promise<{ id?: string | number; revision?: number }>
  onStageChange?: (field: string, value: unknown, origin?: FieldOrigin) => void
}

/**
 * Normalizes field aliases into canonical field keys.
 */
function normalizeBusinessField(field: string, subtab: BusinessSettingsSubtab): string {
  const clean = field.trim().toLowerCase()
  if (clean === 'name') {
    if (subtab === 'solo_provider') return 'display_name'
    if (subtab === 'primary_location') return 'primary_location_name'
    return 'business_name'
  }
  if (clean === 'email') {
    if (subtab === 'solo_provider') return 'email'
    return 'support_email'
  }
  if (clean === 'phone') {
    if (subtab === 'solo_provider') return 'phone'
    return 'support_phone'
  }
  if (clean === 'address') {
    if (subtab === 'primary_location') return 'primary_location_address'
    return 'business_address'
  }
  if (clean === 'business_email') return 'support_email'
  if (clean === 'business_phone') return 'support_phone'
  if (clean === 'solo_provider_name') return 'display_name'
  if (clean === 'solo_provider_bio') return 'bio'
  if (clean === 'solo_provider_phone') return 'phone'
  if (clean === 'solo_provider_email') return 'email'
  if (clean === 'street' || clean === 'primary_location_street') return 'address_line1'
  if (clean === 'postcode' || clean === 'primary_location_postcode') return 'postal_code'
  return clean
}

/**
 * OnboardingFormAdapter implementation for Business Settings (`/admin/settings/business`).
 *
 * Implements the CRITICAL AUTOSAVE STAGING GUARD:
 * In `settings/business.tsx`, manual inputs trigger debounced autosave (600ms).
 * The adapter intercepts and holds assistant-staged field values in an isolated
 * in-memory staging buffer. Partial spoken transcripts or unconfirmed entities
 * NEVER trigger premature database autosaves until explicitly committed or saved.
 */
export class BusinessSettingsAdapter implements OnboardingFormAdapter {
  readonly form_id: string = 'business_settings'
  readonly route: string = '/admin/settings/business'
  readonly supported_fields: readonly string[] = BUSINESS_SETTINGS_SUPPORTED_FIELDS

  active_subtab: string = 'business_profile'

  private committedFields: Record<string, unknown> = {}
  private stagedFields: Record<string, { value: unknown; origin?: FieldOrigin }> = {}
  private revision: number = 1
  private entityId: string | number = 'business_profile'
  private saveHandler?: (
    payload: BusinessSettingsSavePayload,
    nonce?: string,
  ) => Promise<{ id?: string | number; revision?: number }>
  private onStageChange?: (field: string, value: unknown, origin?: FieldOrigin) => void

  constructor(options: BusinessSettingsAdapterOptions = {}) {
    if (options.initialSubtab) {
      this.active_subtab = options.initialSubtab
    }
    if (options.initialValues) {
      this.committedFields = { ...options.initialValues }
    }
    this.saveHandler = options.saveHandler
    this.onStageChange = options.onStageChange
  }

  is_ready(): boolean {
    return true
  }

  /**
   * Sets the active subtab with normalization.
   */
  set_subtab(subtab: string): boolean {
    const raw = subtab.trim().toLowerCase().replace(/[- ]+/g, '_')
    let resolved: BusinessSettingsSubtab | undefined
    if (raw === 'business_profile' || raw === 'profile' || raw === 'business') {
      resolved = 'business_profile'
    } else if (raw === 'solo_provider' || raw === 'provider' || raw === 'solo') {
      resolved = 'solo_provider'
    } else if (raw === 'primary_location' || raw === 'location' || raw === 'primary') {
      resolved = 'primary_location'
    }

    if (resolved) {
      this.active_subtab = resolved
      return true
    }
    return false
  }

  /**
   * Stages a field value safely inside the staging buffer.
   * Completely bypasses the 600ms autosave debounce timer.
   */
  stage_field(
    field: string,
    value: unknown,
    origin?: FieldOrigin,
  ): { staged: boolean; error?: string } {
    const canonicalKey = normalizeBusinessField(field, this.active_subtab as BusinessSettingsSubtab)
    if (!this.supported_fields.includes(canonicalKey as (typeof this.supported_fields)[number])) {
      return {
        staged: false,
        error: `Field '${field}' is not supported by business_settings adapter.`,
      }
    }

    this.stagedFields[canonicalKey] = {
      value,
      origin: origin || 'agent_spoken',
    }

    if (this.onStageChange) {
      this.onStageChange(canonicalKey, value, origin)
    }

    return { staged: true }
  }

  /**
   * Reads current field value and staging state.
   */
  get_field_state(field: string): { value: unknown; staged: boolean; origin?: FieldOrigin } {
    const canonicalKey = normalizeBusinessField(field, this.active_subtab as BusinessSettingsSubtab)
    if (canonicalKey in this.stagedFields) {
      const staged = this.stagedFields[canonicalKey]
      return {
        value: staged.value,
        staged: true,
        origin: staged.origin,
      }
    }

    if (canonicalKey in this.committedFields) {
      return {
        value: this.committedFields[canonicalKey],
        staged: false,
      }
    }

    return {
      value: undefined,
      staged: false,
    }
  }

  /**
   * Returns all currently staged fields.
   */
  get_all_staged_fields(): Record<string, { value: unknown; origin?: FieldOrigin }> {
    return { ...this.stagedFields }
  }

  /**
   * Discards all staged changes without persisting them.
   */
  cancel_staging(): void {
    this.stagedFields = {}
  }

  /**
   * Validates both committed and staged field values.
   */
  async validate(): Promise<{ valid: boolean; errors?: Record<string, string> }> {
    const errors: Record<string, string> = {}
    const getVal = (key: string): unknown => {
      if (key in this.stagedFields) return this.stagedFields[key].value
      return this.committedFields[key]
    }

    // 1. Business Name Validation
    const businessName = getVal('business_name')
    if (businessName !== undefined && typeof businessName === 'string' && !businessName.trim()) {
      errors.business_name = 'Business name cannot be blank.'
    }

    // 2. Email Validations
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    const supportEmail = getVal('support_email')
    if (supportEmail && typeof supportEmail === 'string' && !emailRegex.test(supportEmail.trim())) {
      errors.support_email = 'Invalid support email address format.'
    }
    const providerEmail = getVal('email')
    if (providerEmail && typeof providerEmail === 'string' && !emailRegex.test(providerEmail.trim())) {
      errors.email = 'Invalid solo provider email address format.'
    }

    // 3. Provider Delivery Modes Invariant
    const allowInCall = getVal('allow_in_call')
    const allowOutCall = getVal('allow_out_call')
    if (allowInCall !== undefined && allowOutCall !== undefined) {
      if (allowInCall === false && allowOutCall === false) {
        errors.delivery_modes = 'At least one delivery mode (In-Call or Out-Call) must be enabled.'
      }
    }

    // 4. Out-Call Parameters
    const outCallRadius = getVal('out_call_radius_km')
    if (outCallRadius !== undefined && typeof outCallRadius === 'number' && outCallRadius < 0) {
      errors.out_call_radius_km = 'Out-call radius must be a positive number.'
    }

    const valid = Object.keys(errors).length === 0
    return { valid, errors: valid ? undefined : errors }
  }

  /**
   * Authoritatively commits staged fields and saves the entity.
   */
  async save(authorisation_nonce?: string): Promise<{
    success: boolean
    entity?: { entity_type: string; id: number | string; revision: number }
    error?: string
  }> {
    const valResult = await this.validate()
    if (!valResult.valid) {
      const errList = Object.values(valResult.errors || {}).join(' ')
      return {
        success: false,
        error: `Validation failed: ${errList}`,
      }
    }

    const payload: BusinessSettingsSavePayload = {
      profile: {},
      provider: {},
      location: {},
    }

    // Merge staged values into committed fields and construct payload
    for (const [key, item] of Object.entries(this.stagedFields)) {
      this.committedFields[key] = item.value

      // Route to profile, provider, or location slice
      if (
        [
          'business_name',
          'company_number',
          'industry',
          'timezone',
          'currency',
          'support_email',
          'support_phone',
          'business_address',
        ].includes(key)
      ) {
        payload.profile![key] = item.value
      } else if (
        [
          'display_name',
          'bio',
          'title',
          'phone',
          'email',
          'allow_in_call',
          'allow_out_call',
          'out_call_radius_km',
          'base_outcall_surcharge',
          'per_km_fee',
          'turnaround_buffer_mins',
        ].includes(key)
      ) {
        payload.provider![key] = item.value
      } else {
        payload.location![key] = item.value
      }
    }

    if (this.saveHandler) {
      try {
        const result = await this.saveHandler(payload, authorisation_nonce)
        if (result?.id) {
          this.entityId = result.id
        }
        if (result?.revision) {
          this.revision = result.revision
        } else {
          this.revision += 1
        }
      } catch (err: unknown) {
        return {
          success: false,
          error: (err as Error)?.message || 'Failed to persist business settings.',
        }
      }
    } else {
      this.revision += 1
    }

    // Clear staging buffer upon successful commit
    this.stagedFields = {}

    return {
      success: true,
      entity: {
        entity_type: 'business_settings',
        id: this.entityId,
        revision: this.revision,
      },
    }
  }
}
