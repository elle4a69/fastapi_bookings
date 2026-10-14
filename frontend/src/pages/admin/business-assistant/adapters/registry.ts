import type { FieldOrigin } from '../rpc/types.ts'

export interface StagedFieldState {
  value: unknown
  staged: boolean
  origin?: FieldOrigin
}

export interface StagedFieldMap {
  [field: string]: {
    value: unknown
    origin?: FieldOrigin
  }
}

export interface OnboardingFormAdapter {
  form_id: string
  route: string
  active_subtab: string
  supported_fields: readonly string[]
  is_ready(): boolean
  stage_field(
    field: string,
    value: unknown,
    origin?: FieldOrigin,
  ): { staged: boolean; error?: string }
  get_field_state(field: string): { value: unknown; staged: boolean; origin?: FieldOrigin }
  get_all_staged_fields(): Record<string, { value: unknown; origin?: FieldOrigin }>
  validate(): Promise<{ valid: boolean; errors?: Record<string, string> }>
  save(authorisation_nonce?: string): Promise<{
    success: boolean
    entity?: { entity_type: string; id: number | string; revision: number }
    error?: string
  }>
  cancel_staging(): void
  set_subtab?(subtab: string): boolean | Promise<boolean>
}

const ADAPTER_STEP_ALIASES: Record<string, string> = {
  step_1_identity: 'business_settings',
  step_1: 'business_settings',
  identity: 'business_settings',
  business: 'business_settings',
  profile: 'business_settings',
  business_profile: 'business_settings',
  step_2_team: 'team_roster',
  step_2: 'team_roster',
  team: 'team_roster',
  step_3_services: 'catalog_services',
  step_3: 'catalog_services',
  services: 'catalog_services',
  service_catalog: 'catalog_services',
  catalog: 'catalog_services',
  step_4_hours: 'operating_hours',
  step_4: 'operating_hours',
  hours: 'operating_hours',
  step_5_policies: 'booking_policies',
  step_5: 'booking_policies',
  policies: 'booking_policies',
  step_6_payments: 'payment_settings',
  step_6: 'payment_settings',
  payments: 'payment_settings',
  step_7_communications: 'notifications',
  step_7: 'notifications',
  communications: 'notifications',
  step_8_website: 'website_builder',
  step_8: 'website_builder',
  website: 'website_builder',
}

/**
 * Registry holding active and registered onboarding form adapters.
 * Manages route and form_id lookups with support for graceful fallbacks.
 */
export class FormAdapterRegistry {
  private static instance: FormAdapterRegistry | null = null
  private adapters: Map<string, OnboardingFormAdapter> = new Map()
  private activeFormId: string | null = null

  static getInstance(): FormAdapterRegistry {
    if (!FormAdapterRegistry.instance) {
      FormAdapterRegistry.instance = new FormAdapterRegistry()
    }
    return FormAdapterRegistry.instance
  }

  /**
   * Registers an adapter and returns an unsubscribe callback.
   */
  registerAdapter(adapter: OnboardingFormAdapter): () => void {
    this.adapters.set(adapter.form_id, adapter)
    return () => {
      const current = this.adapters.get(adapter.form_id)
      if (current === adapter) {
        this.adapters.delete(adapter.form_id)
        if (this.activeFormId === adapter.form_id) {
          this.activeFormId = null
        }
      }
    }
  }

  /**
   * Retrieves an adapter by its unique form_id.
   */
  getAdapter(formId: string): OnboardingFormAdapter | undefined {
    if (!formId) return undefined
    const clean = formId.trim().toLowerCase().replace(/-/g, '_')
    if (this.adapters.has(formId)) return this.adapters.get(formId)
    if (this.adapters.has(clean)) return this.adapters.get(clean)

    const aliased = ADAPTER_STEP_ALIASES[clean]
    if (aliased && this.adapters.has(aliased)) {
      return this.adapters.get(aliased)
    }

    for (const [id, adapter] of this.adapters.entries()) {
      const normalizedId = id.toLowerCase().replace(/-/g, '_')
      if (normalizedId === clean || (aliased && normalizedId === aliased)) {
        return adapter
      }
    }
    return undefined
  }

  /**
   * Resolves the adapter mapped to a specific admin pathname / route.
   */
  getAdapterForRoute(route: string): OnboardingFormAdapter | undefined {
    if (!route) return undefined
    const cleanRoute = route.split('?')[0].split('#')[0].replace(/\/+$/, '')
    for (const adapter of this.adapters.values()) {
      const adapterRoute = adapter.route.split('?')[0].split('#')[0].replace(/\/+$/, '')
      if (adapterRoute === cleanRoute || cleanRoute.startsWith(adapterRoute)) {
        return adapter
      }
    }
    return undefined
  }

  /**
   * Retrieves the currently active ready adapter.
   */
  getActiveAdapter(): OnboardingFormAdapter | undefined {
    // 1. Explicitly designated active adapter
    if (this.activeFormId && this.adapters.has(this.activeFormId)) {
      const explicit = this.adapters.get(this.activeFormId)
      if (explicit && explicit.is_ready()) return explicit
    }

    // 2. Active route matching in browser context
    if (typeof window !== 'undefined' && window.location && window.location.pathname) {
      const matched = this.getAdapterForRoute(window.location.pathname)
      if (matched && matched.is_ready()) {
        return matched
      }
    }

    // 3. First ready adapter
    for (const adapter of this.adapters.values()) {
      if (adapter.is_ready()) {
        return adapter
      }
    }

    // 4. Fallback to any registered adapter
    const all = Array.from(this.adapters.values())
    return all.length > 0 ? all[0] : undefined
  }

  /**
   * Designates a specific form_id as active.
   */
  setActiveAdapter(formId: string | null): void {
    this.activeFormId = formId
  }

  /**
   * Returns a snapshot array of all currently registered adapters.
   */
  getAllAdapters(): OnboardingFormAdapter[] {
    return Array.from(this.adapters.values())
  }

  /**
   * Clears all registered adapters (primarily for testing teardown).
   */
  clear(): void {
    this.adapters.clear()
    this.activeFormId = null
  }
}

export const formAdapterRegistry = FormAdapterRegistry.getInstance()
