import type { Room, RpcInvocationData } from 'livekit-client'

import { executeRpcAction } from './action-catalogue.ts'
import { executorCoordinator } from './executor-coordinator.ts'
import { validateAssistantRpcSender } from './sender-validation.ts'
import type {
  RpcExecutionReceipt,
  RpcReceiverContext,
  RpcRegistration,
} from './types.ts'

export const REGISTERED_RPC_METHODS = [
  'assistant_ui_action',
  'route_navigation',
  'navigate',
  'preview_toggle',
  'section_highlight',
  'change_review_drawer',
] as const

export const ONBOARDING_RPC_METHODS = [
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
  'highlight_field',
  'point_to_field',
  'read_form_state',
] as const

export const ALL_RPC_METHODS = [
  ...REGISTERED_RPC_METHODS,
  ...ONBOARDING_RPC_METHODS,
] as const

/**
 * Safely dispatches a custom event to the window in browser environments.
 */
export function dispatchRpcEvent<T>(eventName: string, detail: T): void {
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
    try {
      const event = new CustomEvent(eventName, { detail })
      window.dispatchEvent(event)
    } catch {
      // Guard against non-standard event environments
    }
  }
}

/**
 * Resolves the action name from method name and payload.
 */
export function resolveActionName(method: string, payload: Record<string, unknown>): string {
  if (method === 'assistant_ui_action' || method === 'ui_action') {
    const raw = (payload.action as string) || (payload.name as string) || 'unknown'
    if (raw === 'navigate') return 'route_navigation'
    if (raw === 'select_subtab') return 'navigate_subtab'
    if (raw === 'set_fields') return 'fill_fields'
    if (raw === 'point_to_field' || raw === 'highlight_field') return 'highlight_field'
    return raw
  }
  if (method === 'navigate') {
    return 'route_navigation'
  }
  if (method === 'select_subtab') {
    return 'navigate_subtab'
  }
  if (method === 'set_fields') {
    return 'fill_fields'
  }
  if (method === 'point_to_field') {
    return 'highlight_field'
  }
  return method
}

/**
 * Creates an RPC invocation handler wired to sender validation, action catalogue, and receipts.
 */
export function createAssistantRpcHandler(context: RpcReceiverContext) {
  return async (method: string, data: RpcInvocationData): Promise<string> => {
    const callerIdentity = data.callerIdentity || ''
    const requestId = data.requestId || `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const timestamp = new Date().toISOString()

    // 1. Sender validation: ensure invocation comes from a verified assistant participant
    const validation = validateAssistantRpcSender({
      callerIdentity,
      expectedAgentIdentity: context.expectedAgentIdentity,
      expectedAgentName: context.expectedAgentName,
      room: context.room,
      allowedAgentIdentities: context.allowedAgentIdentities,
    })

    if (!validation.valid) {
      const rejectionReceipt: RpcExecutionReceipt = {
        action_id: requestId,
        action: 'unknown',
        status: 'rejected',
        receipt_state: 'rejected',
        caller_identity: callerIdentity,
        timestamp,
        error_code: 'unauthorised',
        error: `Sender validation failed: ${validation.reason}`,
      }

      dispatchRpcEvent('assistant-rpc:receipt', rejectionReceipt)
      if (context.onReceipt) {
        context.onReceipt(rejectionReceipt)
      }

      return JSON.stringify(rejectionReceipt)
    }

    // 2. Parse payload safely
    let parsedPayload: Record<string, unknown> = {}
    if (data.payload && typeof data.payload === 'string' && data.payload.trim()) {
      try {
        parsedPayload = JSON.parse(data.payload)
      } catch {
        const errorReceipt: RpcExecutionReceipt = {
          action_id: requestId,
          action: 'unknown',
          status: 'failed',
          receipt_state: 'failed',
          caller_identity: callerIdentity,
          timestamp,
          error_code: 'invalid_value',
          error: 'RPC payload is malformed or invalid JSON.',
        }

        dispatchRpcEvent('assistant-rpc:receipt', errorReceipt)
        if (context.onReceipt) {
          context.onReceipt(errorReceipt)
        }

        return JSON.stringify(errorReceipt)
      }
    }

    const actionName = resolveActionName(method, parsedPayload)
    const actionId =
      (parsedPayload.action_id as string) ||
      (parsedPayload.command_id as string) ||
      (parsedPayload.id as string) ||
      requestId

    // Enforce active executor leasing if requested by context or multi-tab coordination
    if (context.requireActiveExecutorLease) {
      const coordinator = context.executorCoordinator || executorCoordinator
      const activeCheck = coordinator.validateExecution()
      if (!activeCheck.allowed) {
        const leaseRejection: RpcExecutionReceipt = {
          action_id: actionId,
          action: (actionName as any) || 'unknown',
          status: 'rejected',
          receipt_state: 'rejected',
          caller_identity: callerIdentity,
          timestamp,
          error_code: 'not_active_lease_holder',
          error: activeCheck.reason,
        }

        dispatchRpcEvent('assistant-rpc:receipt', leaseRejection)
        if (context.onReceipt) {
          context.onReceipt(leaseRejection)
        }

        return JSON.stringify(leaseRejection)
      }
    }

    // 3. Execute action from typed catalogue with epoch and lease checks
    const receipt = await executeRpcAction(actionName, parsedPayload, {
      actionId,
      callerIdentity,
      context,
    })

    // 4. Dispatch browser events for UI reactivity
    dispatchRpcEvent('assistant-rpc:receipt', receipt)
    dispatchRpcEvent('assistant-rpc:action', { action: actionName, receipt })

    if (receipt.action === 'preview_toggle' && (receipt.status === 'success' || receipt.receipt_state === 'saved')) {
      dispatchRpcEvent('assistant-rpc:preview-toggle', { state: receipt.preview_state })
    } else if (receipt.action === 'section_highlight' && (receipt.status === 'success' || receipt.receipt_state === 'waiting_for_ui')) {
      dispatchRpcEvent('assistant-rpc:section-highlight', {
        section: receipt.target_section,
        elementFound: receipt.details?.element_found,
      })
    } else if (receipt.action === 'change_review_drawer' && (receipt.status === 'success' || receipt.receipt_state === 'saved')) {
      dispatchRpcEvent('assistant-rpc:change-review-drawer', {
        state: receipt.drawer_state,
        proposalId: receipt.details?.proposal_id,
      })
    } else if (receipt.action === 'navigate_subtab') {
      dispatchRpcEvent('assistant-rpc:navigate-subtab', {
        subtab: receipt.active_subtab,
        route: receipt.resulting_page,
      })
    } else if (receipt.action === 'open_modal') {
      dispatchRpcEvent('assistant-rpc:open-modal', {
        modalId: receipt.active_modal,
        entityId: receipt.details?.entity_id,
      })
    } else if (receipt.action === 'close_modal') {
      dispatchRpcEvent('assistant-rpc:close-modal', {})
    } else if (receipt.action === 'fill_fields') {
      dispatchRpcEvent('assistant-rpc:fill-fields', {
        formId: receipt.form_id,
        stagedFields: receipt.staged_fields,
      })
    } else if (receipt.action === 'select_option') {
      dispatchRpcEvent('assistant-rpc:select-option', {
        formId: receipt.form_id,
        details: receipt.details,
      })
    } else if (receipt.action === 'validate_form') {
      dispatchRpcEvent('assistant-rpc:validate-form', {
        formId: receipt.form_id,
        valid: receipt.validation_valid,
      })
    } else if (receipt.action === 'save_form') {
      dispatchRpcEvent('assistant-rpc:save-form', {
        formId: receipt.form_id,
        entity: receipt.persisted_entity,
      })
    } else if (receipt.action === 'manual_takeover') {
      dispatchRpcEvent('assistant-rpc:manual-takeover', {
        newEpoch: receipt.control_epoch,
        details: receipt.details,
      })
    } else if (receipt.action === 'point_to_control') {
      dispatchRpcEvent('assistant-rpc:point-to-control', {
        controlId: receipt.pointed_control,
      })
    } else if (receipt.action === 'highlight_field') {
      dispatchRpcEvent('assistant-rpc:highlight-field', {
        field: receipt.pointed_control || (receipt.details?.field as string),
        details: receipt.details,
      })
    }

    if (context.onReceipt) {
      context.onReceipt(receipt)
    }

    return JSON.stringify(receipt)
  }
}

/**
 * Registers the typed assistant RPC methods on an active LiveKit Room instance.
 * Returns an unregister handle for clean teardown.
 */
export function registerAssistantRpcMethods(
  room: Room,
  context: Omit<RpcReceiverContext, 'room'> = {},
  methods: readonly string[] = REGISTERED_RPC_METHODS,
): RpcRegistration {
  const fullContext: RpcReceiverContext = {
    ...context,
    room,
  }

  const handler = createAssistantRpcHandler(fullContext)
  const registeredMethods: string[] = []

  for (const method of methods) {
    try {
      if (typeof room.registerRpcMethod === 'function') {
        room.registerRpcMethod(method, async (data: RpcInvocationData) => {
          return handler(method, data)
        })
        registeredMethods.push(method)
      }
    } catch (err) {
      console.warn(`[LiveKit RPC] Failed to register method ${method}:`, err)
    }
  }

  return {
    registeredMethods,
    unregister: () => {
      for (const method of registeredMethods) {
        try {
          if (typeof room.unregisterRpcMethod === 'function') {
            room.unregisterRpcMethod(method)
          }
        } catch {
          // Ignored during cleanup
        }
      }
    },
  }
}

/**
 * Registers all assistant RPC methods (including all onboarding methods) on an active LiveKit Room instance.
 */
export function registerAllAssistantRpcMethods(
  room: Room,
  context: Omit<RpcReceiverContext, 'room'> = {},
): RpcRegistration {
  return registerAssistantRpcMethods(room, context, ALL_RPC_METHODS)
}

