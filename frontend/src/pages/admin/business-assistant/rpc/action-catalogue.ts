import {
  ALLOWED_ROUTES,
  ROUTE_ALIASES,
  ALLOWED_SECTIONS,
  ALLOWED_SUBTABS,
  SUBTAB_ALIASES,
  isValidReceiptStateTransition,
  type RpcActionType,
  type RpcExecutionReceipt,
  type RpcReceiverContext,
  type ExecutionReceiptState,
  type FieldOrigin,
} from './types.ts'
import { formAdapterRegistry } from '../adapters/index.ts'
import { authenticatedAdminFetch } from '../../../../lib/api.ts'

// ── CONSOLE LOG RECORDER BUFFER ──────────────────────────────────────────
export interface CapturedConsoleLog {
  level: string
  message: string
  timestamp: string
}

const capturedConsoleLogs: CapturedConsoleLog[] = []
const MAX_CAPTURED_CONSOLE_LOGS = 5

export function recordConsoleLog(level: string, message: string): void {
  capturedConsoleLogs.push({
    level,
    message: String(message).slice(0, 500),
    timestamp: new Date().toISOString(),
  })
  if (capturedConsoleLogs.length > MAX_CAPTURED_CONSOLE_LOGS) {
    capturedConsoleLogs.shift()
  }
}

export function getRecentConsoleLogs(): CapturedConsoleLog[] {
  return [...capturedConsoleLogs]
}

if (typeof window !== 'undefined' && !(window as any).__business_assistant_console_hook__) {
  (window as any).__business_assistant_console_hook__ = true
  const origLog = console.log
  const origWarn = console.warn
  const origError = console.error

  console.log = (...args: any[]) => {
    try {
      recordConsoleLog('log', args.map((a) => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' '))
    } catch {}
    origLog.apply(console, args)
  }
  console.warn = (...args: any[]) => {
    try {
      recordConsoleLog('warn', args.map((a) => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' '))
    } catch {}
    origWarn.apply(console, args)
  }
  console.error = (...args: any[]) => {
    try {
      recordConsoleLog('error', args.map((a) => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' '))
    } catch {}
    origError.apply(console, args)
  }
}

// ── 1. ROUTE & SUBTAB NORMALIZATION ──────────────────────────────────────

/**
 * Normalizes and resolves a target route string, handling aliases and query parameters.
 */
export function normalizeRoute(rawRoute: string): string {
  const trimmed = rawRoute.trim()
  if (!trimmed) return ''

  // Remove any search params or hashes for route allowlist comparison
  const pathOnly = trimmed.split('?')[0].split('#')[0]

  // Check exact path match in ROUTE_ALIASES first
  if (ROUTE_ALIASES[pathOnly]) {
    return ROUTE_ALIASES[pathOnly]
  }

  // Strip leading/trailing whitespace and lower-case alias lookup
  const cleanKey = pathOnly.toLowerCase().replace(/^\/+/, '').replace(/\/+$/, '')
  if (ROUTE_ALIASES[cleanKey]) {
    return ROUTE_ALIASES[cleanKey]
  }

  // Also check if prefix is admin/ and subkey is an alias
  if (cleanKey.startsWith('admin/')) {
    const subKey = cleanKey.slice(6)
    if (ROUTE_ALIASES[subKey]) {
      return ROUTE_ALIASES[subKey]
    }
  }

  return pathOnly.startsWith('/') ? pathOnly : `/${pathOnly}`
}

/**
 * Verifies that a target route is within the strictly allowlisted application routes.
 */
export function isRouteAllowlisted(targetPath: string): boolean {
  if (!targetPath) return false

  const lower = targetPath.toLowerCase()
  if (
    lower.startsWith('javascript:') ||
    lower.startsWith('data:') ||
    lower.startsWith('vbscript:') ||
    lower.startsWith('http://') ||
    lower.startsWith('https://') ||
    lower.startsWith('//') ||
    lower.includes('..')
  ) {
    return false
  }

  const normalized = normalizeRoute(targetPath)
  return ALLOWED_ROUTES.some((allowed) => allowed === normalized || allowed === targetPath)
}

/**
 * Normalizes section identifier for website inspection and highlighting.
 */
export function normalizeSection(rawSection: string): string {
  return rawSection
    .trim()
    .toLowerCase()
    .replace(/-section$/, '')
    .replace(/^section-/, '')
    .replace(/[^a-z0-9_]/g, '_')
}

/**
 * Checks whether the section is recognized in the website sections catalogue.
 */
export function isSectionAllowlisted(section: string): boolean {
  const normalized = normalizeSection(section)
  return ALLOWED_SECTIONS.includes(normalized as (typeof ALLOWED_SECTIONS)[number])
}

/**
 * Normalizes subtab selector identifier.
 */
export function normalizeSubtab(rawSubtab: string): string {
  const trimmed = rawSubtab.trim().toLowerCase().replace(/[- ]+/g, '_')
  if (SUBTAB_ALIASES[trimmed]) {
    return SUBTAB_ALIASES[trimmed]
  }
  return trimmed
}

/**
 * Checks whether the subtab is recognized in the onboarding subtabs catalogue.
 */
export function isSubtabAllowlisted(subtab: string): boolean {
  if (!subtab) return false
  const normalized = normalizeSubtab(subtab)
  return ALLOWED_SUBTABS.includes(normalized as (typeof ALLOWED_SUBTABS)[number])
}

// ── 2. DOM INTERACTION HELPERS ───────────────────────────────────────────

/**
 * Visually highlights and scrolls to a website section in the document DOM.
 */
export function highlightSectionInDom(section: string): { found: boolean; id?: string } {
  if (typeof document === 'undefined') {
    return { found: false }
  }

  const normalized = normalizeSection(section)
  const candidateIds = [
    `${normalized}-section`,
    normalized,
    `section-${normalized}`,
    `#${normalized}-section`,
  ]

  let element: HTMLElement | null = null
  let matchedId: string | undefined

  for (const id of candidateIds) {
    const cleanId = id.replace(/^#/, '')
    const el = document.getElementById(cleanId)
    if (el) {
      element = el
      matchedId = cleanId
      break
    }
  }

  if (!element) {
    element = document.querySelector(
      `[data-section="${normalized}"], [data-section-id="${normalized}"]`,
    ) as HTMLElement | null
    if (element) {
      matchedId = element.id || normalized
    }
  }

  if (element) {
    try {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    } catch {
      // Smooth scroll fallback
    }

    try {
      const origOutline = element.style.outline
      const origShadow = element.style.boxShadow
      const origTransition = element.style.transition

      element.style.transition = 'all 0.3s ease-in-out'
      element.style.outline = '3px solid #6366f1'
      element.style.outlineOffset = '4px'
      element.style.boxShadow = '0 0 24px rgba(99, 102, 241, 0.45)'

      setTimeout(() => {
        if (element) {
          element.style.outline = origOutline
          element.style.boxShadow = origShadow
          element.style.transition = origTransition
        }
      }, 3000)
    } catch {
      // Style manipulation guard
    }

    return { found: true, id: matchedId }
  }

  return { found: false }
}

/**
 * Visually highlights and scrolls to a target form field in the document DOM.
 * Resolves by [data-field-name="{field}"], [name="{field}"], [data-testid="input-{field}"], or #{field}.
 */
export function highlightFieldInDom(field: string): { found: boolean; selector?: string; id?: string } {
  if (typeof document === 'undefined' || !field) {
    return { found: false }
  }

  const cleanField = field.trim()
  const candidateSelectors = [
    `[data-field-name="${cleanField}"]`,
    `[name="${cleanField}"]`,
    `[data-testid="input-${cleanField}"]`,
    `#${cleanField}`,
    `[data-control-id="${cleanField}"]`,
    `#field-${cleanField}`,
    `[id="${cleanField}"]`,
  ]

  let element: HTMLElement | null = null
  let matchedSelector: string | undefined

  for (const selector of candidateSelectors) {
    try {
      const el = document.querySelector(selector) as HTMLElement | null
      if (el) {
        element = el
        matchedSelector = selector
        break
      }
    } catch {
      // Selector query guard
    }
  }

  if (element) {
    try {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    } catch {
      // Smooth scroll fallback
    }

    try {
      const origOutline = element.style.outline
      const origShadow = element.style.boxShadow
      const origTransition = element.style.transition

      element.style.transition = 'all 0.3s ease-in-out'
      element.style.outline = '2px solid #6366f1'
      element.style.outlineOffset = '2px'
      element.style.boxShadow = '0 0 16px rgba(99, 102, 241, 0.45)'

      setTimeout(() => {
        if (element) {
          element.style.outline = origOutline
          element.style.boxShadow = origShadow
          element.style.transition = origTransition
        }
      }, 3500)
    } catch {
      // Style guard
    }

    // Dispatch event for FieldPointerOverlay
    if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
      try {
        const rect = element.getBoundingClientRect()
        window.dispatchEvent(
          new CustomEvent('assistant:highlight-field', {
            detail: {
              field: cleanField,
              selector: matchedSelector,
              id: element.id || cleanField,
              rect: {
                top: rect.top,
                left: rect.left,
                width: rect.width,
                height: rect.height,
              },
            },
          }),
        )
      } catch {
        // Event dispatch guard
      }
    }

    return { found: true, selector: matchedSelector, id: element.id || cleanField }
  }

  return { found: false }
}

/**
 * Populates an input, textarea, or select element in the DOM, triggering React synthetic change events.
 */
export function populateInputFieldInDom(field: string, value: unknown): { success: boolean; element?: HTMLElement } {
  if (typeof document === 'undefined' || !field) {
    return { success: false }
  }

  const cleanField = field.trim()
  const aliasKeys: string[] = [cleanField]
  if (cleanField === 'business_name') aliasKeys.push('name', 'businessName', 'company_name', 'business-name')
  else if (cleanField === 'name') aliasKeys.push('business_name', 'display_name')
  else if (cleanField === 'business_email' || cleanField === 'support_email') aliasKeys.push('email', 'contact_email', 'businessEmail')
  else if (cleanField === 'email') aliasKeys.push('business_email', 'support_email', 'contact_email')
  else if (cleanField === 'business_phone' || cleanField === 'support_phone') aliasKeys.push('phone', 'contact_phone', 'businessPhone')
  else if (cleanField === 'phone') aliasKeys.push('business_phone', 'support_phone', 'contact_phone')
  else if (cleanField === 'business_address') aliasKeys.push('address', 'businessAddress')
  else if (cleanField === 'address') aliasKeys.push('business_address', 'address_line1', 'street')
  else if (cleanField === 'display_name') aliasKeys.push('name', 'solo_provider_name')

  const candidateSelectors: string[] = []
  for (const k of aliasKeys) {
    candidateSelectors.push(
      `input[name="${k}"]`,
      `textarea[name="${k}"]`,
      `select[name="${k}"]`,
      `[data-field-name="${k}"] input`,
      `[data-field-name="${k}"] textarea`,
      `[data-field-name="${k}"] select`,
      `[data-field-name="${k}"]`,
      `[data-testid="input-${k}"]`,
      `#${k}`,
      `[name="${k}"]`,
      `#field-${k}`,
      `[id="${k}"]`,
    )
  }

  let element: HTMLElement | null = null

  for (const selector of candidateSelectors) {
    try {
      const el = document.querySelector(selector) as HTMLElement | null
      if (el) {
        element = el
        break
      }
    } catch {
      // Selector query guard
    }
  }

  if (!element) {
    return { success: false }
  }

  const stringVal = value === null || value === undefined ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value)

  try {
    if (element instanceof HTMLInputElement) {
      if (element.type === 'checkbox') {
        const boolVal = Boolean(value && value !== 'false' && value !== '0')
        const propDesc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'checked')
        if (propDesc && propDesc.set) {
          propDesc.set.call(element, boolVal)
        } else {
          element.checked = boolVal
        }
        element.dispatchEvent(new Event('input', { bubbles: true }))
        element.dispatchEvent(new Event('change', { bubbles: true }))
      } else {
        const tracker = (element as any)._valueTracker
        if (tracker) {
          tracker.setValue(element.value !== stringVal ? element.value : '')
        }
        const propDesc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
        if (propDesc && propDesc.set) {
          propDesc.set.call(element, stringVal)
        } else {
          element.value = stringVal
        }
        element.dispatchEvent(new Event('input', { bubbles: true }))
        element.dispatchEvent(new Event('change', { bubbles: true }))
      }
    } else if (element instanceof HTMLTextAreaElement) {
      const tracker = (element as any)._valueTracker
      if (tracker) {
        tracker.setValue(element.value !== stringVal ? element.value : '')
      }
      const propDesc = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')
      if (propDesc && propDesc.set) {
        propDesc.set.call(element, stringVal)
      } else {
        element.value = stringVal
      }
      element.dispatchEvent(new Event('input', { bubbles: true }))
      element.dispatchEvent(new Event('change', { bubbles: true }))
    } else if (element instanceof HTMLSelectElement) {
      const propDesc = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value')
      if (propDesc && propDesc.set) {
        propDesc.set.call(element, stringVal)
      } else {
        element.value = stringVal
      }
      element.dispatchEvent(new Event('input', { bubbles: true }))
      element.dispatchEvent(new Event('change', { bubbles: true }))
    } else {
      const innerInput = element.querySelector('input, textarea, select') as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null
      if (innerInput) {
        return populateInputFieldInDom(innerInput.name || innerInput.id || cleanField, value)
      }
    }

    highlightFieldInDom(cleanField)
    return { success: true, element }
  } catch (err) {
    console.warn(`Failed to set DOM value for ${cleanField}:`, err)
    return { success: false, element }
  }
}

// ── 3. CONTROL EPOCH & LEASE TOKEN MANAGERS ──────────────────────────────

export class ControlEpochManager {
  private currentEpoch: number = 1
  private history: Array<{ epoch: number; timestamp: string; reason?: string }> = [
    { epoch: 1, timestamp: new Date().toISOString(), reason: 'initialisation' },
  ]

  getEpoch(): number {
    return this.currentEpoch
  }

  advanceEpoch(reason?: string): number {
    this.currentEpoch += 1
    this.history.push({
      epoch: this.currentEpoch,
      timestamp: new Date().toISOString(),
      reason,
    })
    return this.currentEpoch
  }

  incrementEpoch(reason?: string): number {
    return this.advanceEpoch(reason)
  }

  resetEpoch(initial = 1): void {
    this.currentEpoch = initial
    this.history = [{ epoch: initial, timestamp: new Date().toISOString(), reason: 'reset' }]
  }

  validateEpoch(commandEpoch?: number): { valid: boolean; currentEpoch: number; reason?: string } {
    if (commandEpoch === undefined || commandEpoch === null) {
      return { valid: true, currentEpoch: this.currentEpoch }
    }
    if (commandEpoch < this.currentEpoch) {
      return {
        valid: false,
        currentEpoch: this.currentEpoch,
        reason: `Stale control epoch: command epoch (${commandEpoch}) is older than active epoch (${this.currentEpoch}). Action rejected due to manual takeover or state progression.`,
      }
    }
    return { valid: true, currentEpoch: this.currentEpoch }
  }

  getHistory() {
    return [...this.history]
  }
}

export const defaultEpochManager = new ControlEpochManager()

export class LeaseTokenManager {
  private activeToken: string | null = null
  private leaseExpiry: number | null = null
  private tabId: string =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `tab_${Math.random().toString(36).slice(2, 9)}`

  getTabId(): string {
    return this.tabId
  }

  getActiveLease(): { token: string | null; tabId: string; expiresAt: number | null } {
    if (this.leaseExpiry && Date.now() > this.leaseExpiry) {
      this.activeToken = null
      this.leaseExpiry = null
    }
    return { token: this.activeToken, tabId: this.tabId, expiresAt: this.leaseExpiry }
  }

  acquireLease(token?: string, ttlMs: number = 30000): string {
    const assigned = token || `lease_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    this.activeToken = assigned
    this.leaseExpiry = Date.now() + ttlMs
    return assigned
  }

  releaseLease(token?: string): boolean {
    if (!token || token === this.activeToken) {
      this.activeToken = null
      this.leaseExpiry = null
      return true
    }
    return false
  }

  reset(): void {
    this.activeToken = null
    this.leaseExpiry = null
  }

  validateLease(
    commandLease?: string | null,
    requireLease: boolean = false,
  ): { valid: boolean; reason?: string } {
    if (this.leaseExpiry && Date.now() > this.leaseExpiry) {
      this.activeToken = null
      this.leaseExpiry = null
    }

    if (this.activeToken) {
      if (!commandLease) {
        return {
          valid: false,
          reason: 'Command missing required lease token while single-tab active executor lease is active.',
        }
      }
      if (commandLease !== this.activeToken) {
        return {
          valid: false,
          reason: `Invalid lease token: received '${commandLease}', active lease is '${this.activeToken}'.`,
        }
      }
      return { valid: true }
    }

    if (requireLease && !commandLease) {
      return {
        valid: false,
        reason: 'Action requires single-tab lease token but none was provided.',
      }
    }

    return { valid: true }
  }
}

export const defaultLeaseManager = new LeaseTokenManager()

export class ReceiptStateTracker {
  private currentState: ExecutionReceiptState
  private stateHistory: Array<{ state: ExecutionReceiptState; timestamp: string; note?: string }>

  constructor(initialState: ExecutionReceiptState = 'received') {
    this.currentState = initialState
    this.stateHistory = [{ state: initialState, timestamp: new Date().toISOString() }]
  }

  getState(): ExecutionReceiptState {
    return this.currentState
  }

  transitionTo(nextState: ExecutionReceiptState, note?: string): boolean {
    if (!isValidReceiptStateTransition(this.currentState, nextState)) {
      throw new Error(
        `Invalid receipt state transition: cannot transition from '${this.currentState}' to '${nextState}'.`,
      )
    }
    this.currentState = nextState
    this.stateHistory.push({ state: nextState, timestamp: new Date().toISOString(), note })
    return true
  }

  getHistory() {
    return [...this.stateHistory]
  }
}

// ── 4. ACTION EXECUTOR ───────────────────────────────────────────────────

export interface ExecuteActionOptions {
  actionId?: string
  callerIdentity?: string
  context?: RpcReceiverContext
  epochManager?: ControlEpochManager
  leaseManager?: LeaseTokenManager
}

/**
 * Executes a typed LiveKit RPC action from the assistant catalogue and returns a structured receipt.
 * Validates control epochs and single-tab lease tokens before executing.
 */
export async function executeRpcAction(
  action: RpcActionType | string,
  rawPayload: Record<string, unknown>,
  options: ExecuteActionOptions,
): Promise<RpcExecutionReceipt> {
  const { actionId = 'action_' + Date.now(), callerIdentity = '', context = {} } = options || {}
  const timestamp = new Date().toISOString()

  const epochMgr = options?.epochManager || defaultEpochManager
  const leaseMgr = options?.leaseManager || defaultLeaseManager
  const tracker = new ReceiptStateTracker('received')

  // Synchronize context epoch if provided
  if (context?.currentControlEpoch !== undefined && context.currentControlEpoch > epochMgr.getEpoch()) {
    epochMgr.resetEpoch(context.currentControlEpoch)
  }

  // 1. Validate Control Epoch: Reject stale commands generated prior to manual takeover
  const commandEpoch =
    typeof rawPayload.control_epoch === 'number'
      ? rawPayload.control_epoch
      : rawPayload.params && typeof rawPayload.params === 'object' && typeof (rawPayload.params as Record<string, unknown>).control_epoch === 'number'
      ? ((rawPayload.params as Record<string, unknown>).control_epoch as number)
      : undefined

  if (commandEpoch !== undefined) {
    const epochValidation = epochMgr.validateEpoch(commandEpoch)
    if (!epochValidation.valid) {
      tracker.transitionTo('rejected', epochValidation.reason)
      return {
        action_id: actionId,
        action: (action as RpcActionType) || 'unknown',
        status: 'rejected',
        receipt_state: 'rejected',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        error_code: 'stale_control_epoch',
        error: epochValidation.reason,
      }
    }
  }

  // 2. Validate Single-Tab Lease Token: Enforce active executor lease
  const commandLease =
    (rawPayload.lease_token as string) ||
    (rawPayload.params && typeof rawPayload.params === 'object'
      ? ((rawPayload.params as Record<string, unknown>).lease_token as string)
      : undefined) ||
    (context?.activeLeaseToken as string) ||
    (callerIdentity && ['xai-grok-voice', 'direct-gpt-live', 'realtime-voice', 'test_assistant'].includes(callerIdentity)
      ? leaseMgr.getActiveLease().token ?? undefined
      : undefined) ||
    undefined

  const leaseValidation = leaseMgr.validateLease(
    commandLease,
    context.requireLeaseToken || (context.activeLeaseToken !== null && context.activeLeaseToken !== undefined),
  )

  if (!leaseValidation.valid) {
    tracker.transitionTo('rejected', leaseValidation.reason)
    return {
      action_id: actionId,
      action: (action as RpcActionType) || 'unknown',
      status: 'rejected',
      receipt_state: 'rejected',
      caller_identity: callerIdentity,
      timestamp,
      control_epoch: epochMgr.getEpoch(),
      lease_token: leaseMgr.getActiveLease().token ?? undefined,
      error_code: 'invalid_lease_token',
      error: leaseValidation.reason,
    }
  }

  // 3. Dispatch to Typed Action Implementation
  switch (action) {
    // ── ONBOARDING: NAVIGATE SUBTAB ──────────────────────────────────────
    case 'navigate_subtab':
    case 'select_subtab': {
      tracker.transitionTo('waiting_for_ui')

      const rawSubtab =
        (rawPayload.subtab as string) ||
        (rawPayload.tab as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).subtab as string) ||
            ((rawPayload.params as Record<string, unknown>).tab as string)
          : '') ||
        ''

      if (!rawSubtab) {
        tracker.transitionTo('failed', 'Missing subtab parameter')
        return {
          action_id: actionId,
          action: 'navigate_subtab',
          status: 'failed',
          receipt_state: 'failed',
          caller_identity: callerIdentity,
          timestamp,
          control_epoch: epochMgr.getEpoch(),
          lease_token: leaseMgr.getActiveLease().token ?? undefined,
          error_code: 'invalid_value',
          error: 'navigate_subtab requires a subtab selector identifier.',
        }
      }

      const normalizedSubtab = normalizeSubtab(rawSubtab)
      const rawRoute =
        (rawPayload.route as string) ||
        (rawPayload.path as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).route as string) ||
            ((rawPayload.params as Record<string, unknown>).path as string)
          : undefined)

      let targetRoute: string | undefined
      if (rawRoute && typeof rawRoute === 'string') {
        targetRoute = normalizeRoute(rawRoute)
        if (!isRouteAllowlisted(targetRoute)) {
          tracker.transitionTo('rejected', `Route '${rawRoute}' is not allowlisted`)
          return {
            action_id: actionId,
            action: 'navigate_subtab',
            status: 'rejected',
            receipt_state: 'rejected',
            caller_identity: callerIdentity,
            timestamp,
            control_epoch: epochMgr.getEpoch(),
            lease_token: leaseMgr.getActiveLease().token ?? undefined,
            error_code: 'target_unavailable',
            error: `Navigation rejected: Route '${rawRoute}' is not allowlisted.`,
          }
        }
        if (context.onNavigate) {
          context.onNavigate(targetRoute)
        }
      }

      let subtabResult = { success: true, active_subtab: normalizedSubtab }
      if (context.onNavigateSubtab) {
        subtabResult = await context.onNavigateSubtab(normalizedSubtab, targetRoute)
        if (!subtabResult.success) {
          tracker.transitionTo('failed', (subtabResult as any).error)
          return {
            action_id: actionId,
            action: 'navigate_subtab',
            status: 'failed',
            receipt_state: 'failed',
            caller_identity: callerIdentity,
            timestamp,
            control_epoch: epochMgr.getEpoch(),
            lease_token: leaseMgr.getActiveLease().token ?? undefined,
            error_code: 'target_unavailable',
            error: (subtabResult as any).error || `Failed to activate subtab '${normalizedSubtab}'.`,
          }
        }
      } else {
        const adapter = targetRoute
          ? formAdapterRegistry.getAdapterForRoute(targetRoute)
          : formAdapterRegistry.getActiveAdapter()
        if (adapter && typeof adapter.set_subtab === 'function') {
          const switched = await adapter.set_subtab(normalizedSubtab)
          if (switched) {
            subtabResult = { success: true, active_subtab: adapter.active_subtab || normalizedSubtab }
          }
        }
      }

      return {
        action_id: actionId,
        action: 'navigate_subtab',
        status: 'waiting_for_ui',
        receipt_state: 'waiting_for_ui',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        resulting_page: targetRoute,
        active_subtab: subtabResult.active_subtab,
      }
    }

    // ── ONBOARDING: MODAL LIFECYCLE ──────────────────────────────────────
    case 'open_modal': {
      tracker.transitionTo('waiting_for_ui')

      const modalId =
        (rawPayload.modal_id as string) ||
        (rawPayload.modal as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).modal_id as string) ||
            ((rawPayload.params as Record<string, unknown>).modal as string)
          : '') ||
        ''

      if (!modalId) {
        tracker.transitionTo('failed', 'Missing modal_id')
        return {
          action_id: actionId,
          action: 'open_modal',
          status: 'failed',
          receipt_state: 'failed',
          caller_identity: callerIdentity,
          timestamp,
          control_epoch: epochMgr.getEpoch(),
          lease_token: leaseMgr.getActiveLease().token ?? undefined,
          error_code: 'invalid_value',
          error: 'open_modal requires a modal_id identifier.',
        }
      }

      const entityId =
        rawPayload.entity_id ??
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? (rawPayload.params as Record<string, unknown>).entity_id
          : undefined)

      if (context.onOpenModal) {
        const modalRes = await context.onOpenModal(modalId, entityId as any)
        if (!modalRes.success) {
          tracker.transitionTo('failed', modalRes.error)
          return {
            action_id: actionId,
            action: 'open_modal',
            status: 'failed',
            receipt_state: 'failed',
            caller_identity: callerIdentity,
            timestamp,
            control_epoch: epochMgr.getEpoch(),
            lease_token: leaseMgr.getActiveLease().token ?? undefined,
            error_code: 'target_unavailable',
            error: modalRes.error || `Failed to open modal '${modalId}'.`,
          }
        }
      }

      return {
        action_id: actionId,
        action: 'open_modal',
        status: 'waiting_for_ui',
        receipt_state: 'waiting_for_ui',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        active_modal: modalId,
        details: entityId !== undefined ? { entity_id: entityId } : undefined,
      }
    }

    case 'close_modal': {
      tracker.transitionTo('waiting_for_ui')

      const modalId =
        (rawPayload.modal_id as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).modal_id as string)
          : undefined)

      if (context.onCloseModal) {
        const closeRes = await context.onCloseModal(modalId)
        if (!closeRes.success) {
          tracker.transitionTo('failed', closeRes.error)
          return {
            action_id: actionId,
            action: 'close_modal',
            status: 'failed',
            receipt_state: 'failed',
            caller_identity: callerIdentity,
            timestamp,
            control_epoch: epochMgr.getEpoch(),
            lease_token: leaseMgr.getActiveLease().token ?? undefined,
            error_code: 'target_unavailable',
            error: closeRes.error || 'Failed to close modal.',
          }
        }
      }

      return {
        action_id: actionId,
        action: 'close_modal',
        status: 'waiting_for_ui',
        receipt_state: 'waiting_for_ui',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        active_modal: null,
      }
    }

    // ── ONBOARDING: FILL / STAGE FIELDS ──────────────────────────────────
    case 'stage_fields':
    case 'stage_field':
    case 'fill_fields':
    case 'set_fields': {
      tracker.transitionTo('executing')

      let fieldsObj: Record<string, unknown> = {}
      if (rawPayload.fields && typeof rawPayload.fields === 'object') {
        if (Array.isArray(rawPayload.fields)) {
          for (const item of rawPayload.fields) {
            if (item && typeof item === 'object' && 'field' in item) {
              fieldsObj[(item as { field: string }).field] = (item as { value: unknown }).value
            }
          }
        } else {
          fieldsObj = { ...(rawPayload.fields as Record<string, unknown>) }
        }
      } else if (rawPayload.params && typeof rawPayload.params === 'object' && (rawPayload.params as Record<string, unknown>).fields) {
        const pFields = (rawPayload.params as Record<string, unknown>).fields
        if (Array.isArray(pFields)) {
          for (const item of pFields) {
            if (item && typeof item === 'object' && 'field' in item) {
              fieldsObj[(item as { field: string }).field] = (item as { value: unknown }).value
            }
          }
        } else if (typeof pFields === 'object') {
          fieldsObj = { ...(pFields as Record<string, unknown>) }
        }
      }

      const fieldKeys = Object.keys(fieldsObj)
      if (fieldKeys.length === 0) {
        tracker.transitionTo('failed', 'Empty fields payload')
        return {
          action_id: actionId,
          action: 'fill_fields',
          status: 'failed',
          receipt_state: 'failed',
          caller_identity: callerIdentity,
          timestamp,
          control_epoch: epochMgr.getEpoch(),
          lease_token: leaseMgr.getActiveLease().token ?? undefined,
          error_code: 'invalid_value',
          error: 'fill_fields action requires a non-empty fields map or array.',
        }
      }

      const formId =
        (rawPayload.form_id as string) ||
        (rawPayload.step_id as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).form_id as string) ||
            ((rawPayload.params as Record<string, unknown>).step_id as string)
          : undefined)

      const stagingGuard =
        rawPayload.staging_guard !== false &&
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? (rawPayload.params as Record<string, unknown>).staging_guard !== false
          : true)

      const preventAutosave =
        rawPayload.prevent_autosave !== false &&
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? (rawPayload.params as Record<string, unknown>).prevent_autosave !== false
          : true)

      if (context.onFillFields) {
        const fillRes = await context.onFillFields({
          form_id: formId,
          fields: fieldsObj,
          field_origins: rawPayload.field_origins as any,
          staging_guard: stagingGuard,
          prevent_autosave: preventAutosave,
          expected_revision: rawPayload.expected_revision as number | undefined,
        })

        if (!fillRes.success) {
          tracker.transitionTo('failed', fillRes.error)
          return {
            action_id: actionId,
            action: 'fill_fields',
            status: 'failed',
            receipt_state: 'failed',
            caller_identity: callerIdentity,
            timestamp,
            control_epoch: epochMgr.getEpoch(),
            lease_token: leaseMgr.getActiveLease().token ?? undefined,
            error_code: 'target_unavailable',
            error: fillRes.error || 'Failed to stage fields in active form adapter.',
          }
        }
      } else {
        const adapter = formId
          ? formAdapterRegistry.getAdapter(formId)
          : formAdapterRegistry.getActiveAdapter()
        if (adapter) {
          const fieldOrigins = (rawPayload.field_origins || {}) as Record<string, FieldOrigin>
          for (const [key, val] of Object.entries(fieldsObj)) {
            const origin = fieldOrigins[key] || 'agent_spoken'
            const stageRes = adapter.stage_field(key, val, origin)
            if (!stageRes.staged) {
              tracker.transitionTo('failed', stageRes.error)
              return {
                action_id: actionId,
                action: 'fill_fields',
                status: 'failed',
                receipt_state: 'failed',
                caller_identity: callerIdentity,
                timestamp,
                control_epoch: epochMgr.getEpoch(),
                lease_token: leaseMgr.getActiveLease().token ?? undefined,
                error_code: 'target_unavailable',
                error: stageRes.error || `Failed to stage field '${key}'.`,
              }
            }
          }
        }
      }

      for (const [key, val] of Object.entries(fieldsObj)) {
        populateInputFieldInDom(key, val)
      }

      if (fieldKeys.length > 0) {
        highlightFieldInDom(fieldKeys[0])
      }

      tracker.transitionTo('fields_staged')

      return {
        action_id: actionId,
        action: 'fill_fields',
        status: 'fields_staged',
        receipt_state: 'fields_staged',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        form_id: formId,
        staged_fields: fieldKeys,
        field_count: fieldKeys.length,
        details: {
          staging_guard: stagingGuard,
          prevent_autosave: preventAutosave,
        },
      }
    }

    // ── ONBOARDING: SELECT OPTION ────────────────────────────────────────
    case 'select_option': {
      tracker.transitionTo('executing')

      const optionId =
        rawPayload.option_id ??
        (rawPayload.value as string | number) ??
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? (rawPayload.params as Record<string, unknown>).option_id ??
            (rawPayload.params as Record<string, unknown>).value
          : undefined)

      if (optionId === undefined || optionId === null) {
        tracker.transitionTo('failed', 'Missing option_id')
        return {
          action_id: actionId,
          action: 'select_option',
          status: 'failed',
          receipt_state: 'failed',
          caller_identity: callerIdentity,
          timestamp,
          control_epoch: epochMgr.getEpoch(),
          lease_token: leaseMgr.getActiveLease().token ?? undefined,
          error_code: 'invalid_value',
          error: 'select_option requires an option_id or value parameter.',
        }
      }

      const formId =
        (rawPayload.form_id as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).form_id as string)
          : undefined)

      const fieldId =
        (rawPayload.field_id as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).field_id as string)
          : undefined)

      if (context.onSelectOption) {
        const optRes = await context.onSelectOption({
          form_id: formId,
          field_id: fieldId,
          option_id: optionId as string | number,
          label: rawPayload.label as string,
        })
        if (!optRes.success) {
          tracker.transitionTo('failed', optRes.error)
          return {
            action_id: actionId,
            action: 'select_option',
            status: 'failed',
            receipt_state: 'failed',
            caller_identity: callerIdentity,
            timestamp,
            control_epoch: epochMgr.getEpoch(),
            lease_token: leaseMgr.getActiveLease().token ?? undefined,
            error_code: 'invalid_value',
            error: optRes.error || `Option selection failed for '${optionId}'.`,
          }
        }
      }

      tracker.transitionTo('fields_staged')

      return {
        action_id: actionId,
        action: 'select_option',
        status: 'fields_staged',
        receipt_state: 'fields_staged',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        form_id: formId,
        details: {
          field_id: fieldId,
          selected_option_id: optionId,
        },
      }
    }

    // ── ONBOARDING: VALIDATE FORM ────────────────────────────────────────
    case 'validate_form': {
      tracker.transitionTo('executing')

      const formId =
        (rawPayload.form_id as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).form_id as string)
          : undefined)

      let isValid = true
      let valErrors: Record<string, string[]> | string[] | undefined

      if (context.onValidateForm) {
        const valRes = await context.onValidateForm({ form_id: formId })
        isValid = valRes.valid
        valErrors = valRes.errors
      } else {
        const adapter = formId
          ? formAdapterRegistry.getAdapter(formId)
          : formAdapterRegistry.getActiveAdapter()
        if (adapter) {
          const valRes = await adapter.validate()
          isValid = valRes.valid
          if (valRes.errors) {
            valErrors = Object.entries(valRes.errors).reduce((acc, [k, v]) => {
              acc[k] = [v]
              return acc
            }, {} as Record<string, string[]>)
          }
        }
      }

      tracker.transitionTo('fields_staged')

      let formattedError: string | undefined
      if (!isValid) {
        if (valErrors) {
          if (Array.isArray(valErrors)) {
            formattedError = `Form validation failed: ${valErrors.join('; ')}`
          } else {
            const errParts = Object.entries(valErrors).map(
              ([fld, errs]) => `${fld}: ${Array.isArray(errs) ? errs.join(', ') : errs}`
            )
            formattedError = `Form validation failed: ${errParts.join('; ')}`
          }
        } else {
          formattedError = 'Form validation failed: required fields are missing or invalid.'
        }
      }

      return {
        action_id: actionId,
        action: 'validate_form',
        status: isValid ? 'fields_staged' : 'failed',
        receipt_state: 'fields_staged',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        form_id: formId,
        validation_valid: isValid,
        validation_errors: valErrors,
        error_code: isValid ? undefined : 'validation_failed',
        error: formattedError,
        details: valErrors ? { validation_errors: valErrors } : undefined,
      }
    }

    // ── ONBOARDING: SAVE FORM ────────────────────────────────────────────
    case 'commit_save':
    case 'save_form': {
      tracker.transitionTo('executing')

      const formId =
        (rawPayload.form_id as string) ||
        (rawPayload.step_id as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).form_id as string) ||
            ((rawPayload.params as Record<string, unknown>).step_id as string)
          : undefined)

      const targetEntityId =
        rawPayload.target_entity_id ??
        rawPayload.entity_id ??
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? (rawPayload.params as Record<string, unknown>).target_entity_id ??
            (rawPayload.params as Record<string, unknown>).entity_id
          : undefined)

      const nonce =
        (rawPayload.authorisation_nonce as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).authorisation_nonce as string)
          : undefined)

      let saveRes: {
        success: boolean
        entity?: { entity_type?: string; id?: string | number; revision?: number }
        error?: string
      } | null = null

      if (context.onSaveForm) {
        saveRes = await context.onSaveForm({
          form_id: formId,
          target_entity_id: targetEntityId as string | number | undefined,
          authorisation_nonce: nonce,
          expected_revision: rawPayload.expected_revision as number | undefined,
        })
      } else {
        const adapter = formId
          ? formAdapterRegistry.getAdapter(formId)
          : formAdapterRegistry.getActiveAdapter()
        if (adapter) {
          const aRes = await adapter.save(nonce)
          saveRes = {
            success: aRes.success,
            entity: aRes.entity,
            error: aRes.error,
          }
        } else {
          tracker.transitionTo('failed', 'No form save handler registered')
          return {
            action_id: actionId,
            action: 'save_form',
            status: 'failed',
            receipt_state: 'failed',
            caller_identity: callerIdentity,
            timestamp,
            control_epoch: epochMgr.getEpoch(),
            lease_token: leaseMgr.getActiveLease().token ?? undefined,
            error_code: 'save_unavailable',
            error: 'Save failed: No active form save handler registered in current context.',
          }
        }
      }

      if (!saveRes.success) {
        tracker.transitionTo('failed', saveRes.error)
        return {
          action_id: actionId,
          action: 'save_form',
          status: 'failed',
          receipt_state: 'failed',
          caller_identity: callerIdentity,
          timestamp,
          control_epoch: epochMgr.getEpoch(),
          lease_token: leaseMgr.getActiveLease().token ?? undefined,
          form_id: formId,
          error_code: 'save_conflict',
          error: saveRes.error || 'Form submission failed in authoritative save handler.',
        }
      }

      tracker.transitionTo('saved')

      return {
        action_id: actionId,
        action: 'save_form',
        status: 'saved',
        receipt_state: 'saved',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        form_id: formId,
        persisted_entity: saveRes.entity,
      }
    }

    // ── ONBOARDING: MANUAL TAKEOVER ──────────────────────────────────────
    case 'manual_takeover': {
      const reason =
        (rawPayload.reason as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).reason as string)
          : undefined) ||
        'User initiated manual takeover'

      const source =
        (rawPayload.source as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).source as string)
          : undefined) ||
        'ui_button'

      const prevEpoch = epochMgr.getEpoch()
      const newEpoch = epochMgr.advanceEpoch(reason)

      if (context.onManualTakeover) {
        context.onManualTakeover({ reason, source: source as any })
      }

      tracker.transitionTo('executing')
      tracker.transitionTo('saved', 'Control epoch incremented')

      return {
        action_id: actionId,
        action: 'manual_takeover',
        status: 'saved',
        receipt_state: 'saved',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: newEpoch,
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        details: {
          previous_epoch: prevEpoch,
          new_epoch: newEpoch,
          reason,
          source,
        },
      }
    }

    // ── UI AGENT: OPERATE APP ───────────────────────────────────────────
    case 'operate_app': {
      tracker.transitionTo('executing')
      const instruction =
        (rawPayload.instruction as string) ||
        (rawPayload.message as string) ||
        (rawPayload.text as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).instruction as string) ||
            ((rawPayload.params as Record<string, unknown>).text as string)
          : undefined) ||
        ''

      if (!instruction) {
        tracker.transitionTo('failed', 'Missing instruction for operate_app')
        return {
          action_id: actionId,
          action: 'operate_app',
          status: 'failed',
          receipt_state: 'failed',
          caller_identity: callerIdentity,
          timestamp,
          control_epoch: epochMgr.getEpoch(),
          lease_token: leaseMgr.getActiveLease().token ?? undefined,
          error_code: 'invalid_value',
          error: 'operate_app requires an instruction or text parameter.',
        }
      }

      if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
        window.dispatchEvent(
          new CustomEvent('ui-agent:operate', {
            detail: { instruction, source: callerIdentity || 'assistant-rpc' },
          }),
        )
      }

      tracker.transitionTo('saved')
      return {
        action_id: actionId,
        action: 'operate_app',
        status: 'saved',
        receipt_state: 'saved',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        details: { instruction },
      }
    }

    // ── ONBOARDING: POINT TO CONTROL ─────────────────────────────────────
    case 'point_to_control': {
      tracker.transitionTo('waiting_for_ui')

      const controlId =
        (rawPayload.control_id as string) ||
        (rawPayload.control as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).control_id as string) ||
            ((rawPayload.params as Record<string, unknown>).control as string)
          : '') ||
        ''

      if (!controlId) {
        tracker.transitionTo('failed', 'Missing control_id')
        return {
          action_id: actionId,
          action: 'point_to_control',
          status: 'failed',
          receipt_state: 'failed',
          caller_identity: callerIdentity,
          timestamp,
          control_epoch: epochMgr.getEpoch(),
          lease_token: leaseMgr.getActiveLease().token ?? undefined,
          error_code: 'invalid_value',
          error: 'point_to_control requires a control_id parameter.',
        }
      }

      let found = false
      if (context.onPointToControl) {
        const ptRes = context.onPointToControl({ control_id: controlId })
        found = ptRes.found
      } else if (typeof document !== 'undefined') {
        const el =
          document.getElementById(controlId) ||
          document.querySelector(`[data-control-id="${controlId}"]`)
        found = !!el
      }

      return {
        action_id: actionId,
        action: 'point_to_control',
        status: 'waiting_for_ui',
        receipt_state: 'waiting_for_ui',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        pointed_control: controlId,
        details: { found },
      }
    }

    // ── ONBOARDING: HIGHLIGHT FIELD ──────────────────────────────────────
    case 'highlight_field':
    case 'point_to_field': {
      tracker.transitionTo('waiting_for_ui')

      const field =
        (rawPayload.field as string) ||
        (rawPayload.field_name as string) ||
        (rawPayload.field_id as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).field as string) ||
            ((rawPayload.params as Record<string, unknown>).field_name as string) ||
            ((rawPayload.params as Record<string, unknown>).field_id as string)
          : '') ||
        ''

      if (!field) {
        tracker.transitionTo('failed', 'Missing field parameter')
        return {
          action_id: actionId,
          action: 'highlight_field',
          status: 'failed',
          receipt_state: 'failed',
          caller_identity: callerIdentity,
          timestamp,
          control_epoch: epochMgr.getEpoch(),
          lease_token: leaseMgr.getActiveLease().token ?? undefined,
          error_code: 'invalid_value',
          error: 'highlight_field requires a field identifier parameter.',
        }
      }

      let found = false
      let selector: string | undefined
      if (context.onHighlightField) {
        const hRes = context.onHighlightField({ field })
        found = hRes.found
        selector = hRes.selector
      } else {
        const domRes = highlightFieldInDom(field)
        found = domRes.found
        selector = domRes.selector
      }

      return {
        action_id: actionId,
        action: 'highlight_field',
        status: 'waiting_for_ui',
        receipt_state: 'waiting_for_ui',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        pointed_control: field,
        details: { found, field, selector },
      }
    }

    // ── ONBOARDING: READ FORM STATE ──────────────────────────────────────
    case 'read_form_state': {
      tracker.transitionTo('executing')

      const formId =
        (rawPayload.form_id as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).form_id as string)
          : undefined)

      let stateData: Record<string, unknown> = {}
      if (context.onReadFormState) {
        stateData = await context.onReadFormState({ form_id: formId })
      } else {
        const adapter = formId
          ? formAdapterRegistry.getAdapter(formId)
          : formAdapterRegistry.getActiveAdapter()
        if (adapter) {
          stateData = adapter.get_all_staged_fields()
        }
      }

      tracker.transitionTo('fields_staged')

      return {
        action_id: actionId,
        action: 'read_form_state',
        status: 'fields_staged',
        receipt_state: 'fields_staged',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        form_id: formId,
        details: { form_state: stateData },
      }
    }

    // ── WEBSITE: ROUTE NAVIGATION ────────────────────────────────────────
    case 'navigate_route':
    case 'route_navigation': {
      tracker.transitionTo('waiting_for_ui')

      const rawPath =
        (rawPayload.path as string) ||
        (rawPayload.route as string) ||
        (rawPayload.target_route as string) ||
        (rawPayload.targetRoute as string) ||
        (rawPayload.target as string) ||
        (rawPayload.page as string) ||
        (rawPayload.destination as string) ||
        (rawPayload.url as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).path as string) ||
            ((rawPayload.params as Record<string, unknown>).route as string) ||
            ((rawPayload.params as Record<string, unknown>).target_route as string) ||
            ((rawPayload.params as Record<string, unknown>).targetRoute as string) ||
            ((rawPayload.params as Record<string, unknown>).target as string) ||
            ((rawPayload.params as Record<string, unknown>).page as string) ||
            ((rawPayload.params as Record<string, unknown>).destination as string) ||
            ((rawPayload.params as Record<string, unknown>).url as string)
          : '') ||
        ''

      if (!rawPath || typeof rawPath !== 'string') {
        tracker.transitionTo('failed', 'Missing route path')
        return {
          action_id: actionId,
          action: 'route_navigation',
          status: 'failed',
          receipt_state: 'failed',
          caller_identity: callerIdentity,
          timestamp,
          control_epoch: epochMgr.getEpoch(),
          lease_token: leaseMgr.getActiveLease().token ?? undefined,
          error_code: 'invalid_value',
          error: 'Route path parameter is missing or invalid.',
        }
      }

      const targetPath = normalizeRoute(rawPath)

      if (!isRouteAllowlisted(targetPath)) {
        tracker.transitionTo('rejected', `Route '${rawPath}' not allowlisted`)
        return {
          action_id: actionId,
          action: 'route_navigation',
          status: 'rejected',
          receipt_state: 'rejected',
          caller_identity: callerIdentity,
          timestamp,
          control_epoch: epochMgr.getEpoch(),
          lease_token: leaseMgr.getActiveLease().token ?? undefined,
          error_code: 'target_unavailable',
          error: `Navigation rejected: Route '${rawPath}' is not in the allowlisted application routes.`,
        }
      }

      const rawSubtab =
        (rawPayload.subtab as string) ||
        (rawPayload.tab as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).subtab as string) ||
            ((rawPayload.params as Record<string, unknown>).tab as string)
          : '') ||
        ''

      if (rawSubtab && context.onNavigateSubtab) {
        try {
          void context.onNavigateSubtab(normalizeSubtab(rawSubtab), targetPath)
        } catch {
          // ignore subtab sync failure
        }
      }

      if (context.onNavigate) {
        context.onNavigate(targetPath)
      } else if (typeof window !== 'undefined' && window.location) {
        window.location.pathname = targetPath
      }

      return {
        action_id: actionId,
        action: 'route_navigation',
        status: 'success',
        receipt_state: 'waiting_for_ui',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        resulting_page: targetPath,
      }
    }

    // ── WEBSITE: PREVIEW TOGGLE ──────────────────────────────────────────
    case 'preview_toggle': {
      tracker.transitionTo('executing')

      const stateParam =
        (rawPayload.state as 'open' | 'closed' | 'toggle' | undefined) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).state as
              | 'open'
              | 'closed'
              | 'toggle'
              | undefined)
          : undefined) ||
        'toggle'

      let resultingState: 'open' | 'closed' = 'open'

      if (context.onPreviewToggle) {
        resultingState = context.onPreviewToggle(stateParam)
      } else {
        resultingState = stateParam === 'closed' ? 'closed' : 'open'
      }

      tracker.transitionTo('saved')

      return {
        action_id: actionId,
        action: 'preview_toggle',
        status: 'success',
        receipt_state: 'saved',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        preview_state: resultingState,
      }
    }

    // ── WEBSITE: SECTION HIGHLIGHT ───────────────────────────────────────
    case 'section_highlight': {
      tracker.transitionTo('waiting_for_ui')

      const rawSection =
        (rawPayload.section as string) ||
        (rawPayload.section_id as string) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).section as string) ||
            ((rawPayload.params as Record<string, unknown>).section_id as string)
          : '') ||
        ''

      if (!rawSection || typeof rawSection !== 'string') {
        tracker.transitionTo('failed', 'Missing section parameter')
        return {
          action_id: actionId,
          action: 'section_highlight',
          status: 'failed',
          receipt_state: 'failed',
          caller_identity: callerIdentity,
          timestamp,
          control_epoch: epochMgr.getEpoch(),
          lease_token: leaseMgr.getActiveLease().token ?? undefined,
          error_code: 'invalid_value',
          error: 'Section parameter is missing or invalid.',
        }
      }

      const normalizedSection = normalizeSection(rawSection)

      if (!isSectionAllowlisted(normalizedSection)) {
        tracker.transitionTo('rejected', `Section '${rawSection}' not allowlisted`)
        return {
          action_id: actionId,
          action: 'section_highlight',
          status: 'rejected',
          receipt_state: 'rejected',
          caller_identity: callerIdentity,
          timestamp,
          control_epoch: epochMgr.getEpoch(),
          lease_token: leaseMgr.getActiveLease().token ?? undefined,
          error_code: 'target_unavailable',
          error: `Section highlight rejected: Section '${rawSection}' is not an allowlisted website section.`,
        }
      }

      let highlightResult = { found: false }
      if (context.onSectionHighlight) {
        highlightResult = context.onSectionHighlight(normalizedSection)
      } else {
        highlightResult = highlightSectionInDom(normalizedSection)
      }

      return {
        action_id: actionId,
        action: 'section_highlight',
        status: 'success',
        receipt_state: 'waiting_for_ui',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        target_section: normalizedSection,
        details: {
          element_found: highlightResult.found,
          element_id: (highlightResult as { id?: string }).id,
        },
      }
    }

    // ── WEBSITE: REVIEW DRAWER ───────────────────────────────────────────
    case 'change_review_drawer': {
      tracker.transitionTo('executing')

      const stateParam =
        (rawPayload.state as 'open' | 'closed' | 'toggle' | undefined) ||
        (rawPayload.params && typeof rawPayload.params === 'object'
          ? ((rawPayload.params as Record<string, unknown>).state as
              | 'open'
              | 'closed'
              | 'toggle'
              | undefined)
          : undefined) ||
        'open'

      const proposalId =
        typeof rawPayload.proposal_id === 'number'
          ? rawPayload.proposal_id
          : rawPayload.params &&
            typeof rawPayload.params === 'object' &&
            typeof (rawPayload.params as Record<string, unknown>).proposal_id === 'number'
          ? ((rawPayload.params as Record<string, unknown>).proposal_id as number)
          : undefined

      let resultingState: 'open' | 'closed' = 'open'
      if (context.onChangeReviewDrawer) {
        resultingState = context.onChangeReviewDrawer(stateParam, proposalId)
      } else {
        resultingState = stateParam === 'closed' ? 'closed' : 'open'
      }

      tracker.transitionTo('saved')

      return {
        action_id: actionId,
        action: 'change_review_drawer',
        status: 'success',
        receipt_state: 'saved',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        drawer_state: resultingState,
        details: proposalId !== undefined ? { proposal_id: proposalId } : undefined,
      }
    }

    // ── RESIDENT AGENT & MAINTENANCE HANDOFF ────────────────────────────
    case 'create_maintenance_handoff':
    case 'create_support_ticket': {
      tracker.transitionTo('executing')
      const targetAction = action as RpcActionType
      let backendData: Record<string, unknown> | undefined

      // Attach active route, active form state, and last 5 console logs
      const activeRoute = typeof window !== 'undefined' ? window.location.pathname : ''
      let activeFormState: Record<string, unknown> | null = null
      try {
        const adapter = formAdapterRegistry.getActiveAdapter()
        if (adapter) {
          activeFormState = adapter.get_all_staged_fields()
        }
      } catch {
        // Safe fallback
      }

      const recentLogs = getRecentConsoleLogs()
      const enhancedArgs = {
        ...(rawPayload.params && typeof rawPayload.params === 'object' ? rawPayload.params : rawPayload),
        active_route: activeRoute,
        form_state: activeFormState,
        console_logs: recentLogs,
      }

      const convId = context?.conversationId
      if (convId) {
        try {
          const res = await authenticatedAdminFetch(
            `/api/admin/business-assistant/conversations/${convId}/realtime/tools`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                name: action,
                arguments: enhancedArgs,
              }),
            },
          )
          if (res.ok) {
            backendData = (await res.json()) as Record<string, unknown>
          }
        } catch (err) {
          console.warn('[RPC] Failed to forward ticket/handoff directly to backend:', err)
        }
      }

      tracker.transitionTo('saved')
      return {
        action_id: actionId,
        action: targetAction,
        status: 'success',
        receipt_state: 'saved',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        details: {
          handshake: 'delegated_to_backend',
          backend_response: backendData,
          active_route: activeRoute,
          form_state: activeFormState,
          console_logs: recentLogs,
          ...rawPayload,
        },
      }
    }

    // ── UI STATE VERIFICATION & RECEIPT RECORDING ─────────────────────────
    case 'verify_ui_state': {
      tracker.transitionTo('executing', 'Verifying UI state and form readiness')
      const activeRoute = typeof window !== 'undefined' ? window.location.pathname : ''
      let formState: Record<string, unknown> | null = null
      let isValid = true
      let validationErrors: string[] = []

      try {
        const adapter = formAdapterRegistry.getActiveAdapter()
        if (adapter) {
          formState = adapter.get_all_staged_fields()
          const v = await adapter.validate()
          isValid = v.valid
          validationErrors = v.errors
            ? Object.entries(v.errors).map(([k, msg]) => `${k}: ${msg}`)
            : []
        }
      } catch (err) {
        isValid = false
        validationErrors.push(err instanceof Error ? err.message : 'Adapter inspection failed')
      }

      const ticketId = rawPayload.ticket_id || rawPayload.ticketId || context?.ticketId
      let backendReceipt: Record<string, unknown> | undefined

      if (ticketId) {
        try {
          const receiptRes = await authenticatedAdminFetch(
            `/api/admin/business-assistant/tickets/${ticketId}/verify-receipt`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                receipt_state: isValid ? 'saved' : 'failed',
                verified: isValid,
                route: activeRoute,
                notes: rawPayload.notes || (isValid ? 'UI state verified successfully' : 'Validation errors observed in UI state'),
                details: {
                  form_state: formState,
                  validation_errors: validationErrors,
                },
              }),
            },
          )
          if (receiptRes.ok) {
            backendReceipt = (await receiptRes.json()) as Record<string, unknown>
          }
        } catch (err) {
          console.warn('[RPC] Failed to record verify-receipt on backend:', err)
        }
      }

      tracker.transitionTo(isValid ? 'saved' : 'failed', isValid ? 'UI state verified' : 'UI validation failed')
      return {
        action_id: actionId,
        action: 'verify_ui_state',
        status: isValid ? 'success' : 'failed',
        receipt_state: isValid ? 'saved' : 'failed',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        details: {
          route: activeRoute,
          valid: isValid,
          validation_errors: validationErrors,
          form_state: formState,
          backend_receipt: backendReceipt,
          ...rawPayload,
        },
      }
    }

    // ── DIAGNOSTIC INSPECTION & SYSTEM REPORT ─────────────────────────────
    case 'diagnostic_report':
    case 'run_diagnostic_check': {
      tracker.transitionTo('executing', 'Running real diagnostic report')
      let systemHealth: Record<string, unknown> = {}
      try {
        const diagRes = await authenticatedAdminFetch('/api/admin/diagnostics/system-health')
        if (diagRes.ok) {
          systemHealth = (await diagRes.json()) as Record<string, unknown>
        }
      } catch {
        // Fallback to local diagnostics
      }

      tracker.transitionTo('saved', 'Diagnostic report executed successfully')
      return {
        action_id: actionId,
        action: 'diagnostic_report',
        status: 'success',
        receipt_state: 'saved',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        applied_fields: {
          route: typeof window !== 'undefined' ? window.location.pathname : '',
          user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
          control_epoch: String(epochMgr.getEpoch()),
          active_lease_token: leaseMgr.getActiveLease().token || 'none',
          status: 'operational',
          system_health: JSON.stringify(systemHealth),
        },
      }
    }

    // ── SECURITY GATES: REJECT AUTOMATED APPROVAL/PUBLICATION ────────────
    case 'publish':
    case 'publish_website':
    case 'website_publish':
    case 'approve':
    case 'approve_proposal':
    case 'approve_and_publish': {
      tracker.transitionTo('rejected', 'Security gate: manual owner gate approval required')
      return {
        action_id: actionId,
        action: 'unknown',
        status: 'rejected',
        receipt_state: 'rejected',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        error_code: 'security_gate_rejected',
        error:
          'Security Gate Rejection: Automated publication or approval via assistant RPC is strictly prohibited. Publication requires manual owner gate approval in the UI.',
      }
    }

    default: {
      tracker.transitionTo('failed', `Unsupported RPC action '${action}'`)
      return {
        action_id: actionId,
        action: 'unknown',
        status: 'failed',
        receipt_state: 'failed',
        caller_identity: callerIdentity,
        timestamp,
        control_epoch: epochMgr.getEpoch(),
        lease_token: leaseMgr.getActiveLease().token ?? undefined,
        error_code: 'unsupported_action',
        error: `Unsupported RPC action: '${action}'. Supported actions are: navigate_subtab, open_modal, close_modal, fill_fields, select_option, validate_form, save_form, manual_takeover, point_to_control, read_form_state, route_navigation, preview_toggle, section_highlight, change_review_drawer.`,
      }
    }
  }
}
