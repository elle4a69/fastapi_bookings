/**
 * Publication Gate Policy and Execution for Website Builder.
 *
 * Enforces strict owner-only manual publication gates.
 * Prohibits voice agents, automated scripts, and LiveKit RPC commands from approving
 * or triggering publishing automatically.
 */

import { apiClient } from '../../../lib/api.ts'

export interface PublicationGateValidationResult {
  permitted: boolean
  errorCode?:
    | 'UNAUTHORIZED_ROLE'
    | 'AUTOMATED_ATTEMPT_BLOCKED'
    | 'STALE_PROPOSAL'
    | 'INVALID_PROPOSAL'
    | 'CONFIRMATION_REQUIRED'
  reason?: string
}

export interface PublicationGateCheckOptions {
  isOwner: boolean
  isStale: boolean
  isAutomated?: boolean
  proposalId?: number | null
}

/**
 * Validates whether a publication action can proceed through the owner publication gate.
 * Strictly blocks non-owners, automated callers, and stale proposals.
 */
export function validatePublicationGate(
  options: PublicationGateCheckOptions,
): PublicationGateValidationResult {
  const { isOwner, isStale, isAutomated, proposalId } = options

  // 1. Absolute Prohibition: Automated invocation via RPC, voice agent, or script
  if (isAutomated) {
    return {
      permitted: false,
      errorCode: 'AUTOMATED_ATTEMPT_BLOCKED',
      reason:
        'Security Gate Violation: Automated publication via voice assistant or RPC is strictly prohibited. Publication requires direct manual confirmation by an authenticated business owner.',
    }
  }

  // 2. Strict Owner Authorization Gate
  if (!isOwner) {
    return {
      permitted: false,
      errorCode: 'UNAUTHORIZED_ROLE',
      reason:
        'Access Denied: Only authenticated business owners have permission to publish changes to the live website.',
    }
  }

  // 3. Stale Proposal Rejection
  if (isStale) {
    return {
      permitted: false,
      errorCode: 'STALE_PROPOSAL',
      reason:
        'Stale Proposal: The website configuration has advanced since this proposal was created. Please re-sync before publishing.',
    }
  }

  // 4. Proposal existence validation
  if (!proposalId || proposalId <= 0) {
    return {
      permitted: false,
      errorCode: 'INVALID_PROPOSAL',
      reason: 'Invalid proposal: A valid proposal reference is required to publish.',
    }
  }

  return {
    permitted: true,
  }
}

export interface PublishProposalResult {
  ok: boolean
  is_published: boolean
  published_at?: string | null
  message?: string
  error?: string
}

/**
 * Executes proposal publication through the two-phase owner confirmation token gate.
 * 1. Requests a cryptographically signed publication confirmation token from backend.
 * 2. Submits the confirmation token with owner authorization to execute the publication.
 */
export async function executeOwnerPublishProposal(
  proposalId: number,
  options: { isOwner: boolean; isStale: boolean; isAutomated?: boolean },
): Promise<PublishProposalResult> {
  const validation = validatePublicationGate({
    isOwner: options.isOwner,
    isStale: options.isStale,
    isAutomated: options.isAutomated,
    proposalId,
  })

  if (!validation.permitted) {
    throw new Error(validation.reason || 'Publication gate validation failed.')
  }

  // Step 1: Request publication approval token
  const tokenRes: any = await apiClient.post(
    `/api/business-assistant/website/proposals/${proposalId}/request-publish`,
    {},
  )

  if (!tokenRes || !tokenRes.confirmation_token) {
    throw new Error('Failed to obtain publication confirmation token from server.')
  }

  const confirmationToken = tokenRes.confirmation_token

  // Step 2: Publish using the confirmation token under owner credentials
  const publishRes: any = await apiClient.post(
    `/api/business-assistant/website/proposals/${proposalId}/publish`,
    {
      confirmation_token: confirmationToken,
    },
  )

  return {
    ok: Boolean(publishRes?.ok),
    is_published: Boolean(publishRes?.is_published),
    published_at: publishRes?.published_at,
    message: 'Website successfully published live!',
  }
}

/**
 * Direct toggle publication gate for the global 1-Click publish/unpublish header button.
 */
export async function executeOwnerPublishToggle(
  publish: boolean,
  options: { isOwner: boolean; isAutomated?: boolean },
): Promise<{ ok: boolean; is_published: boolean; published_at?: string | null }> {
  if (options.isAutomated) {
    throw new Error(
      'Automated publishing via assistant RPC or background script is strictly prohibited. An authenticated owner must manually confirm.',
    )
  }

  if (!options.isOwner) {
    throw new Error('Permission denied: Only business owners can publish or unpublish the website.')
  }

  const res: any = await apiClient.post('/api/admin/website/publish', {
    is_published: publish,
  })

  return {
    ok: Boolean(res?.ok),
    is_published: Boolean(res?.data?.is_published),
    published_at: res?.data?.published_at,
  }
}
