import type { FieldOrigin } from '../rpc/types.ts'
import type { OnboardingFormAdapter } from './registry.ts'

export const CATALOG_SERVICES_SUBTABS = [
  'details',
  'fixed_times',
  'categories',
  'providers',
  'products',
  'addons',
  'service_details',
  'services',
] as const

export type CatalogServicesSubtab = (typeof CATALOG_SERVICES_SUBTABS)[number]

export const CATALOG_SERVICES_SUPPORTED_FIELDS: readonly string[] = [
  'name',
  'service_name',
  'description',
  'price_amount',
  'price',
  'duration_minutes',
  'duration',
  'allow_in_call',
  'allow_out_call',
  'category_id',
  'category_ids',
  'buffer_before',
  'buffer_after',
  'outcall_price',
  'outcall_buffer_before',
  'outcall_buffer_after',
  'deposit_amount',
  'tax_rate_id',
  'fixed_start_times',
  'has_groups',
  'min_group_size',
  'max_group_size',
  'provider_ids',
  'product_ids',
  'addon_ids',
  'image',
] as const

export interface CatalogServicesAdapterOptions {
  initialMode?: 'create' | 'edit' | 'list'
  selectedServiceId?: string | number | null
  initialValues?: Record<string, unknown>
  saveHandler?: (
    payload: Record<string, unknown>,
    mode: 'create' | 'edit',
    serviceId?: string | number | null,
    nonce?: string,
  ) => Promise<{ id?: string | number; revision?: number }>
  onStageChange?: (field: string, value: unknown, origin?: FieldOrigin) => void
}

/**
 * Normalizes service field aliases to canonical field names.
 */
function normalizeServiceField(field: string): string {
  const clean = field.trim().toLowerCase()
  if (clean === 'service_name') return 'name'
  if (clean === 'price_amount') return 'price'
  if (clean === 'duration_minutes') return 'duration'
  if (clean === 'category_id') return 'category_ids'
  return clean
}

/**
 * OnboardingFormAdapter implementation for Catalog Services (`/admin/catalog/services`).
 *
 * Handles two distinct operational modes audited in `FORM_AUTOSAVE_AUDIT.md`:
 * 1. Creation Mode (`isCreating = true`):
 *    - Autosave is completely disabled in UI.
 *    - Validates service name and delivery modes (allow_in_call || allow_out_call).
 *    - Persisted via explicit save (`POST /api/admin/services`).
 * 2. Edit Mode (`selectedServiceId !== null`, `isCreating = false`):
 *    - Manual UI uses a 500ms debounced autosave (`PUT /api/admin/services/{id}`).
 *    - Staging guard protects against debounce triggers during speech, holding
 *      candidate changes in an isolated buffer until explicitly saved.
 */
export class CatalogServicesAdapter implements OnboardingFormAdapter {
  readonly form_id: string = 'catalog_services'
  readonly route: string = '/admin/catalog/services'
  readonly supported_fields: readonly string[] = CATALOG_SERVICES_SUPPORTED_FIELDS

  active_subtab: string = 'details'

  isCreating: boolean = true
  selectedServiceId: string | number | null = null

  private committedFields: Record<string, unknown> = {
    name: '',
    description: '',
    price: 0,
    duration: 60,
    allow_in_call: true,
    allow_out_call: false,
    buffer_before: 0,
    buffer_after: 0,
    category_ids: [],
    provider_ids: [],
  }

  private stagedFields: Record<string, { value: unknown; origin?: FieldOrigin }> = {}
  private revision: number = 1
  private saveHandler?: (
    payload: Record<string, unknown>,
    mode: 'create' | 'edit',
    serviceId?: string | number | null,
    nonce?: string,
  ) => Promise<{ id?: string | number; revision?: number }>
  private onStageChange?: (field: string, value: unknown, origin?: FieldOrigin) => void

  constructor(options: CatalogServicesAdapterOptions = {}) {
    if (options.initialMode === 'edit') {
      this.isCreating = false
      this.selectedServiceId = options.selectedServiceId ?? 1
    } else if (options.initialMode === 'create') {
      this.isCreating = true
      this.selectedServiceId = null
    } else if (options.selectedServiceId) {
      this.isCreating = false
      this.selectedServiceId = options.selectedServiceId
    }

    if (options.initialValues) {
      this.committedFields = { ...this.committedFields, ...options.initialValues }
    }
    this.saveHandler = options.saveHandler
    this.onStageChange = options.onStageChange
  }

  is_ready(): boolean {
    return true
  }

  /**
   * Switches to Creation Mode (`isCreating = true`).
   * Disables autosave and resets form state.
   */
  enterCreateMode(): void {
    this.isCreating = true
    this.selectedServiceId = null
    this.stagedFields = {}
    this.committedFields = {
      name: '',
      description: '',
      price: 0,
      duration: 60,
      allow_in_call: true,
      allow_out_call: false,
      buffer_before: 0,
      buffer_after: 0,
      category_ids: [],
      provider_ids: [],
    }
  }

  /**
   * Switches to Edit Mode for an existing service.
   */
  selectService(id: string | number, initialData?: Record<string, unknown>): void {
    this.isCreating = false
    this.selectedServiceId = id
    this.stagedFields = {}
    if (initialData) {
      this.committedFields = { ...initialData }
    }
  }

  /**
   * Sets the active subtab or accordion section.
   */
  set_subtab(subtab: string): boolean {
    const raw = subtab.trim().toLowerCase().replace(/[- ]+/g, '_')
    let resolved: CatalogServicesSubtab | undefined
    if (raw === 'details' || raw === 'service_details' || raw === 'service') {
      resolved = 'details'
    } else if (raw === 'fixed_times' || raw === 'schedule' || raw === 'hours') {
      resolved = 'fixed_times'
    } else if (raw === 'categories' || raw === 'category') {
      resolved = 'categories'
    } else if (raw === 'providers' || raw === 'provider') {
      resolved = 'providers'
    } else if (raw === 'products' || raw === 'product') {
      resolved = 'products'
    } else if (raw === 'addons' || raw === 'addon') {
      resolved = 'addons'
    } else if (raw === 'services') {
      resolved = 'services'
    }

    if (resolved) {
      this.active_subtab = resolved
      return true
    }
    return false
  }

  /**
   * Stages a field value.
   * In Edit Mode, completely guards against the 500ms debounced autosave.
   * In Create Mode, stores in buffer without saving.
   */
  stage_field(
    field: string,
    value: unknown,
    origin?: FieldOrigin,
  ): { staged: boolean; error?: string } {
    const canonicalKey = normalizeServiceField(field)
    if (!this.supported_fields.includes(canonicalKey as (typeof this.supported_fields)[number])) {
      return {
        staged: false,
        error: `Field '${field}' is not supported by catalog_services adapter.`,
      }
    }

    // Convert category_id string or number to category_ids array if needed
    let sanitizedValue = value
    if (canonicalKey === 'category_ids' && !Array.isArray(value)) {
      sanitizedValue = [String(value)]
    }

    this.stagedFields[canonicalKey] = {
      value: sanitizedValue,
      origin: origin || 'agent_spoken',
    }

    if (this.onStageChange) {
      this.onStageChange(canonicalKey, sanitizedValue, origin)
    }

    return { staged: true }
  }

  /**
   * Reads field state and whether it is staged.
   */
  get_field_state(field: string): { value: unknown; staged: boolean; origin?: FieldOrigin } {
    const canonicalKey = normalizeServiceField(field)
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
   * Cancels any staged changes without persisting them.
   */
  cancel_staging(): void {
    this.stagedFields = {}
  }

  /**
   * Validates service name and delivery modes.
   */
  async validate(): Promise<{ valid: boolean; errors?: Record<string, string> }> {
    const errors: Record<string, string> = {}
    const getVal = (key: string): unknown => {
      if (key in this.stagedFields) return this.stagedFields[key].value
      return this.committedFields[key]
    }

    // 1. Service Name is Required
    const nameVal = getVal('name')
    if (!nameVal || (typeof nameVal === 'string' && !nameVal.trim())) {
      errors.name = 'Name is required'
    }

    // 2. Delivery Modes Invariant: At least one delivery mode must be active
    const allowInCall = getVal('allow_in_call')
    const allowOutCall = getVal('allow_out_call')
    if (!allowInCall && !allowOutCall) {
      errors.delivery_modes = 'At least one delivery mode (In-Call or Out-Call) must be enabled'
    }

    // 3. Duration must be at least 1 minute
    const durationVal = getVal('duration')
    if (durationVal !== undefined && typeof durationVal === 'number' && durationVal < 1) {
      errors.duration = 'Duration must be at least 1 minute'
    }

    // 4. Price must be >= 0
    const priceVal = getVal('price')
    if (priceVal !== undefined && typeof priceVal === 'number' && priceVal < 0) {
      errors.price = 'Price cannot be negative'
    }

    const valid = Object.keys(errors).length === 0
    return { valid, errors: valid ? undefined : errors }
  }

  /**
   * Authoritatively saves the service.
   * In Creation Mode, triggers POST and transitions to Edit Mode.
   * In Edit Mode, triggers PUT and increments revision.
   */
  async save(authorisation_nonce?: string): Promise<{
    success: boolean
    entity?: { entity_type: string; id: number | string; revision: number }
    error?: string
  }> {
    const valResult = await this.validate()
    if (!valResult.valid) {
      const errList = Object.values(valResult.errors || {}).join('; ')
      return {
        success: false,
        error: `Validation failed: ${errList}`,
      }
    }

    const payload: Record<string, unknown> = {
      ...this.committedFields,
    }

    for (const [key, item] of Object.entries(this.stagedFields)) {
      payload[key] = item.value
      this.committedFields[key] = item.value
    }

    const mode = this.isCreating ? 'create' : 'edit'
    let persistedId: string | number = this.selectedServiceId ?? 1

    if (this.saveHandler) {
      try {
        const result = await this.saveHandler(
          payload,
          mode,
          this.selectedServiceId,
          authorisation_nonce,
        )
        if (result?.id) {
          persistedId = result.id
        }
        if (result?.revision) {
          this.revision = result.revision
        } else {
          this.revision += 1
        }
      } catch (err: unknown) {
        return {
          success: false,
          error: (err as Error)?.message || 'Failed to save service.',
        }
      }
    } else {
      this.revision += 1
    }

    // If we were creating, transition into edit mode
    if (this.isCreating) {
      this.isCreating = false
      this.selectedServiceId = persistedId
    }

    // Clear staging buffer
    this.stagedFields = {}

    return {
      success: true,
      entity: {
        entity_type: 'service',
        id: persistedId,
        revision: this.revision,
      },
    }
  }
}
