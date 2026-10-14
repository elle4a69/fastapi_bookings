import React from 'react'
import {
  SupportTicketManagementStation,
  type SupportTicketListItem,
  type SupportTicketMessage,
  type SupportTicketAuditEvent,
  type SupportTicketDetail
} from './SupportTicketManagementStation'

export type {
  SupportTicketListItem,
  SupportTicketMessage,
  SupportTicketAuditEvent,
  SupportTicketDetail
}

interface SupportTicketsReviewModalProps {
  onClose?: () => void
  onLaunchCodexSuccess?: (ticketId: string, threadId: string) => void
}

/**
 * Platform Owner Support Tickets Review Queue Modal
 * Delegates to the unified SupportTicketManagementStation.
 *
 * Endpoints:
 * - /api/admin/support-tickets
 * - /api/admin/support-tickets/{ticketId}/status
 * - /api/admin/support-tickets/{ticketId}/internal-note (internal_only)
 * - /api/admin/support-tickets/{ticketId}/tenant-reply
 * - /launch-codex (Launch Codex Investigation)
 *
 * Features:
 * - Inspects error_context
 * - internal_only notes
 * - Launch Codex Investigation
 */
export const SupportTicketsReviewModal: React.FC<SupportTicketsReviewModalProps> = ({
  onClose,
  onLaunchCodexSuccess
}) => {
  return (
    <SupportTicketManagementStation
      onClose={onClose}
      isCenterStage={false}
      onLaunchCodexSuccess={onLaunchCodexSuccess}
    />
  )
}

export default SupportTicketsReviewModal
