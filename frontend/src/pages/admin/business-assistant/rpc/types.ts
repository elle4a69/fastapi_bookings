import type { Room } from 'livekit-client'

// ── 1. RPC ACTION TYPES & ENUMS ──────────────────────────────────────────

export type WebsiteRpcActionType =
  | 'route_navigation'
  | 'preview_toggle'
  | 'section_highlight'
  | 'change_review_drawer'

export type OnboardingActionType =
  | 'navigate_subtab'
  | 'open_modal'
  | 'close_modal'
  | 'fill_fields'
  | 'select_option'
  | 'validate_form'
  | 'save_form'
  | 'manual_takeover'
  | 'point_to_control'
  | 'highlight_field'
  | 'read_form_state'

export type RpcActionType = WebsiteRpcActionType | OnboardingActionType

// ── 2. EXECUTION RECEIPT STATES & TRANSITIONS ────────────────────────────

export type ExecutionReceiptState =
  | 'received'
  | 'waiting_for_ui'
  | 'executing'
  | 'fields_staged'
  | 'saved'
  | 'rejected'
  | 'failed'
  | 'outcome_unknown'

export type RpcReceiptStatus = ExecutionReceiptState | 'success'

export type RpcErrorCode =
  | 'unauthorised'
  | 'scope_revoked'
  | 'stale_control_epoch'
  | 'invalid_lease_token'
  | 'not_active_lease_holder'
  | 'manual_takeover'
  | 'stale_context'
  | 'field_changed'
  | 'target_unavailable'
  | 'unsupported_action'
  | 'invalid_value'
  | 'validation_failed'
  | 'save_conflict'
  | 'save_unavailable'
  | 'expired_command'
  | 'outcome_unknown'
  | 'security_gate_rejected'

export const RECEIPT_STATE_TRANSITIONS: Record<
  ExecutionReceiptState,
  readonly ExecutionReceiptState[]
> = {
  received: ['waiting_for_ui', 'executing', 'rejected', 'failed', 'outcome_unknown'],
  waiting_for_ui: ['executing', 'rejected', 'failed', 'outcome_unknown'],
  executing: ['fields_staged', 'saved', 'rejected', 'failed', 'outcome_unknown'],
  fields_staged: ['executing', 'saved', 'rejected', 'failed', 'outcome_unknown'],
  saved: [],
  rejected: [],
  failed: [],
  outcome_unknown: [],
} as const

export function isValidReceiptStateTransition(
  fromState: ExecutionReceiptState,
  toState: ExecutionReceiptState,
): boolean {
  if (fromState === toState) return true
  const allowed = RECEIPT_STATE_TRANSITIONS[fromState]
  return allowed ? allowed.includes(toState) : false
}

// ── 3. FIELD ORIGIN & METADATA ──────────────────────────────────────────

export type FieldOrigin =
  | 'agent_spoken'
  | 'agent_inferred'
  | 'user_explicit'
  | 'preset'

export interface FieldOriginMetadata {
  origin?: FieldOrigin
  confidence?: number
  transcription_turn_id?: string
}

export interface FieldStageItem {
  field: string
  value: unknown
  origin?: FieldOrigin
  metadata?: FieldOriginMetadata
}

// ── 4. TYPED ACTION PARAMETERS ───────────────────────────────────────────

export interface RouteNavigationParams {
  path: string
}

export interface PreviewToggleParams {
  state?: 'open' | 'closed' | 'toggle'
}

export interface SectionHighlightParams {
  section: string
}

export interface ChangeReviewDrawerParams {
  state?: 'open' | 'closed' | 'toggle'
  proposal_id?: number
}

export interface NavigateSubtabParams {
  route?: string
  subtab: string
}

export interface OpenModalParams {
  modal_id: string
  entity_id?: string | number | null
  target_entity_type?: string
}

export interface CloseModalParams {
  modal_id?: string
}

export interface FillFieldsParams {
  form_id?: string
  entity_type?: string
  entity_id?: string | number
  fields: Record<string, unknown> | FieldStageItem[]
  field_origins?: Record<string, FieldOrigin>
  staging_guard?: boolean
  prevent_autosave?: boolean
  expected_revision?: number
}

export interface SelectOptionParams {
  form_id?: string
  field_id?: string
  option_id: string | number
  label?: string
}

export interface ValidateFormParams {
  form_id?: string
  entity_id?: string | number
}

export interface SaveFormParams {
  form_id?: string
  target_entity_id?: string | number
  authorisation_nonce?: string
  expected_revision?: number
}

export interface ManualTakeoverParams {
  reason?: string
  field_id?: string
  source?: 'keyboard' | 'mouse' | 'ui_button' | 'voice_command'
}

export interface PointToControlParams {
  control_id: string
  duration_ms?: number
  variant?: 'point' | 'highlight'
}

export interface HighlightFieldParams {
  field: string
  form_id?: string
  label?: string
  duration_ms?: number
}

export interface ReadFormStateParams {
  form_id?: string
}

// ── 5. REQUEST & RECEIPT ENVELOPES ──────────────────────────────────────

export interface AssistantRpcRequestPayload {
  // Protocol envelope metadata
  protocol_version?: string
  command_id?: string
  action_id?: string
  action: RpcActionType
  params?: Record<string, unknown>

  // Lease & Concurrency Control
  lease_token?: string
  control_epoch?: number
  expected_revision?: number
  timestamp?: string
  expiry?: string

  // Direct convenience parameter mappings (website + onboarding)
  path?: string
  route?: string
  state?: 'open' | 'closed' | 'toggle'
  section?: string
  section_id?: string
  proposal_id?: number

  subtab?: string
  modal_id?: string
  entity_id?: string | number
  form_id?: string
  fields?: Record<string, unknown> | FieldStageItem[]
  field_origins?: Record<string, FieldOrigin>
  staging_guard?: boolean
  prevent_autosave?: boolean
  field_id?: string
  field?: string
  field_name?: string
  option_id?: string | number
  control_id?: string
  reason?: string
  source?: 'keyboard' | 'mouse' | 'ui_button' | 'voice_command'
  authorisation_nonce?: string
}

export interface RpcExecutionReceipt {
  action_id: string
  action: RpcActionType | 'unknown'
  status: RpcReceiptStatus
  receipt_state: ExecutionReceiptState
  caller_identity: string
  timestamp: string
  control_epoch?: number
  lease_token?: string

  // Navigation & Subtab results
  resulting_page?: string
  active_subtab?: string

  // Modal results
  active_modal?: string | null

  // UI highlight, pointer & preview results
  target_section?: string
  preview_state?: 'open' | 'closed'
  drawer_state?: 'open' | 'closed'
  pointed_control?: string

  // Form Staging, Validation & Save results
  form_id?: string
  staged_fields?: string[]
  field_count?: number
  validation_valid?: boolean
  validation_errors?: Record<string, string[]> | string[]
  persisted_entity?: {
    entity_type?: string
    id?: string | number
    revision?: number
  }

  // Error handling
  error?: string
  error_code?: RpcErrorCode
  details?: Record<string, unknown>
}

// ── 6. SENDER VALIDATION & RECEIVER CONTEXT ──────────────────────────────

export interface SenderValidationOptions {
  callerIdentity: string
  expectedAgentIdentity?: string | null
  expectedAgentName?: string | null
  room?: Room | null
  allowedAgentIdentities?: string[]
}

export interface SenderValidationResult {
  valid: boolean
  reason?: string
}

export interface RpcReceiverContext {
  room?: Room | null
  expectedAgentIdentity?: string | null
  expectedAgentName?: string | null
  allowedAgentIdentities?: string[]

  // Website action hooks
  onNavigate?: (path: string) => void
  onPreviewToggle?: (state: 'open' | 'closed' | 'toggle') => 'open' | 'closed'
  onSectionHighlight?: (section: string) => { found: boolean; id?: string }
  onChangeReviewDrawer?: (
    state: 'open' | 'closed' | 'toggle',
    proposalId?: number,
  ) => 'open' | 'closed'
  onReceipt?: (receipt: RpcExecutionReceipt) => void

  // Onboarding action hooks
  onNavigateSubtab?: (
    subtab: string,
    route?: string,
  ) =>
    | Promise<{ success: boolean; active_subtab: string; error?: string }>
    | { success: boolean; active_subtab: string; error?: string }
  onOpenModal?: (
    modalId: string,
    entityId?: string | number | null,
  ) =>
    | Promise<{ success: boolean; active_modal: string; error?: string }>
    | { success: boolean; active_modal: string; error?: string }
  onCloseModal?: (
    modalId?: string,
  ) =>
    | Promise<{ success: boolean; error?: string }>
    | { success: boolean; error?: string }
  onFillFields?: (
    params: FillFieldsParams,
  ) =>
    | Promise<{ success: boolean; staged_fields: string[]; error?: string }>
    | { success: boolean; staged_fields: string[]; error?: string }
  onSelectOption?: (
    params: SelectOptionParams,
  ) =>
    | Promise<{ success: boolean; selected: string | number; error?: string }>
    | { success: boolean; selected: string | number; error?: string }
  onValidateForm?: (
    params: ValidateFormParams,
  ) =>
    | Promise<{ valid: boolean; errors?: Record<string, string[]> | string[]; error?: string }>
    | { valid: boolean; errors?: Record<string, string[]> | string[]; error?: string }
  onSaveForm?: (
    params: SaveFormParams,
  ) =>
    | Promise<{
        success: boolean
        entity?: { entity_type?: string; id?: string | number; revision?: number }
        error?: string
      }>
    | {
        success: boolean
        entity?: { entity_type?: string; id?: string | number; revision?: number }
        error?: string
      }
  onManualTakeover?: (
    params: ManualTakeoverParams,
  ) => { epoch: number; source?: string }
  onPointToControl?: (
    params: PointToControlParams,
  ) => { found: boolean; control_id: string }
  onHighlightField?: (
    params: HighlightFieldParams,
  ) => { found: boolean; field: string; selector?: string }
  onReadFormState?: (
    params: ReadFormStateParams,
  ) => Promise<Record<string, unknown>> | Record<string, unknown>

  // Lease & Concurrency overrides
  currentControlEpoch?: number
  activeLeaseToken?: string | null
  requireLeaseToken?: boolean
  requireActiveExecutorLease?: boolean
  executorCoordinator?: any
}

export interface RpcRegistration {
  registeredMethods: string[]
  unregister: () => void
}

// ── 7. CATALOGUES & ALLOWLISTS ───────────────────────────────────────────

export const ALLOWED_ROUTES: readonly string[] = [
  '/admin',
  '/admin/dashboard',
  '/admin/website',
  '/admin/media',
  '/admin/catalog/services',
  '/admin/catalog/providers',
  '/admin/catalog/categories',
  '/admin/catalog/locations',
  '/admin/catalog/scheduling',
  '/admin/catalog/products',
  '/admin/catalog/packages',
  '/admin/catalog/add-ons',
  '/admin/schedule/workdays',
  '/admin/schedule/exceptions',
  '/admin/bookings',
  '/admin/calendar',
  '/admin/booking-forms',
  '/admin/clients',
  '/admin/reviews',
  '/admin/settings/business',
  '/admin/settings/modules',
  '/admin/settings/webhooks',
  '/admin/settings/plugins',
  '/admin/business-assistant',
  '/admin/gpt-live',
  '/admin/assistant-studio',
  '/admin/telemetry',
  '/admin/system',
  '/admin/audit',
  '/admin/notifications/messages',
  '/admin/notifications/templates',
  '/admin/notifications/reminders',
] as const

export const ROUTE_ALIASES: Record<string, string> = {
  website: '/admin/website',
  'website-editor': '/admin/website',
  website_editor: '/admin/website',
  media: '/admin/media',
  'media-library': '/admin/media',
  media_library: '/admin/media',
  services: '/admin/catalog/services',
  onboarding: '/admin/settings/business',
  business_settings: '/admin/settings/business',
  'business-settings': '/admin/settings/business',
  settings: '/admin/settings/business',
  providers: '/admin/catalog/providers',
  categories: '/admin/catalog/categories',
  locations: '/admin/catalog/locations',
  scheduling: '/admin/catalog/scheduling',
  bookings: '/admin/bookings',
  calendar: '/admin/calendar',
  clients: '/admin/clients',
  reviews: '/admin/reviews',
  assistant: '/admin/business-assistant',
  'business-assistant': '/admin/business-assistant',
  business_assistant: '/admin/business-assistant',
  dashboard: '/admin/dashboard',
}

export const ALLOWED_SECTIONS: readonly string[] = [
  'hero',
  'about',
  'services',
  'booking',
  'testimonials',
  'reviews',
  'contact',
  'footer',
  'chat_widget',
] as const

export const ALLOWED_SUBTABS: readonly string[] = [
  'business_profile',
  'solo_provider',
  'primary_location',
  'services',
  'categories',
  'service_details',
  'category_details',
  'scheduling',
  'hours',
] as const

export const SUBTAB_ALIASES: Record<string, string> = {
  profile: 'business_profile',
  business: 'business_profile',
  business_profile: 'business_profile',
  provider: 'solo_provider',
  solo: 'solo_provider',
  solo_provider: 'solo_provider',
  location: 'primary_location',
  primary: 'primary_location',
  primary_location: 'primary_location',
  services_list: 'services',
  services: 'services',
  category: 'category_details',
  categories: 'categories',
  service: 'service_details',
  service_details: 'service_details',
  hours: 'hours',
  scheduling: 'scheduling',
}
