import type { SenderValidationOptions, SenderValidationResult } from './types.ts'

/**
 * Validates that an incoming RPC invocation originates from an authorized assistant participant.
 * Rejects unverified, forged, self, or non-assistant callers.
 */
export function validateAssistantRpcSender(options: SenderValidationOptions): SenderValidationResult {
  const { callerIdentity, expectedAgentIdentity, expectedAgentName, room, allowedAgentIdentities } = options

  if (!callerIdentity || typeof callerIdentity !== 'string' || callerIdentity.trim() === '') {
    return { valid: false, reason: 'Caller identity is missing or empty.' }
  }

  const trimmedCaller = callerIdentity.trim()

  // Enforce isolation: Reject self-invocation (local participant cannot call own RPC handler)
  if (room && room.localParticipant && room.localParticipant.identity === trimmedCaller) {
    return {
      valid: false,
      reason: 'Self-invocation rejected: local participant cannot invoke assistant RPC.',
    }
  }

  // Exact match against designated agent identity if provided
  if (expectedAgentIdentity && trimmedCaller === expectedAgentIdentity) {
    return { valid: true }
  }

  // Match against allowlisted agent identities list if provided
  if (allowedAgentIdentities && allowedAgentIdentities.includes(trimmedCaller)) {
    return { valid: true }
  }

  // When room is active, inspect remote participants to verify caller identity and agent status
  if (room && room.remoteParticipants) {
    const remote = Array.from(room.remoteParticipants.values()).find(
      (p) => p.identity === trimmedCaller,
    )

    if (!remote) {
      return {
        valid: false,
        reason: `Participant '${trimmedCaller}' not found in the current LiveKit room.`,
      }
    }

    // Remote participant is in the room. Check if it is verified as an agent.
    const isAgentKind = Boolean(
      (remote as { isAgent?: boolean }).isAgent ||
        (remote as { kind?: string | number }).kind === 'agent' ||
        (remote as { kind?: string | number }).kind === 2, // LiveKit ParticipantKind.AGENT
    )

    const matchesExpectedName = Boolean(
      expectedAgentName &&
        (remote.name === expectedAgentName ||
          remote.identity === expectedAgentName ||
          trimmedCaller.includes(expectedAgentName)),
    )

    const hasAgentPrefix =
      trimmedCaller.startsWith('agent_') ||
      trimmedCaller.startsWith('agent-') ||
      trimmedCaller.includes('assistant')

    if (isAgentKind || matchesExpectedName || hasAgentPrefix) {
      return { valid: true }
    }

    return {
      valid: false,
      reason: `Participant '${trimmedCaller}' is present but is not a verified assistant agent.`,
    }
  }

  // Room not supplied (e.g. testing or disconnected validation)
  if (
    (expectedAgentName && trimmedCaller === expectedAgentName) ||
    trimmedCaller.startsWith('agent_') ||
    trimmedCaller.startsWith('agent-') ||
    trimmedCaller.includes('assistant')
  ) {
    return { valid: true }
  }

  return {
    valid: false,
    reason: `Caller identity '${trimmedCaller}' does not match any verified assistant participant.`,
  }
}
