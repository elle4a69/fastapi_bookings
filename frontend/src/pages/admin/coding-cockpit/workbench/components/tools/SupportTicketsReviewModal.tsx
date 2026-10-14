import React, { useState, useEffect, useCallback } from 'react'
import {
  Headphones,
  Sparkles,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  Send,
  FileText,
  MessageSquare,
  Shield,
  Tag,
  ExternalLink,
  Lock,
  ChevronRight,
  Filter,
  Check
} from 'lucide-react'
import { getAuthenticatedAdminHeaders } from '@/lib/api'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import { Textarea } from '../ui/textarea'

export interface SupportTicketListItem {
  id: string
  tenant_id: number
  created_by_user_id: number
  title: string
  description: string
  category: string
  status: string
  tenant_status: string
  triage_priority: string
  error_context?: Record<string, any> | null
  idempotency_key?: string | null
  codex_thread_id?: string | null
  created_at: string
  updated_at: string
  resolved_at?: string | null
  message_count: number
  latest_activity_at: string
}

export interface SupportTicketMessage {
  id: string
  ticket_id: string
  sender_user_id?: number | null
  sender_type: string
  visibility: string
  body: string
  created_at: string
}

export interface SupportTicketAuditEvent {
  id: string
  ticket_id: string
  actor_user_id?: number | null
  action: string
  event_data?: Record<string, any> | null
  created_at: string
}

export interface SupportTicketDetail extends SupportTicketListItem {
  messages: SupportTicketMessage[]
  audit_events: SupportTicketAuditEvent[]
}

interface SupportTicketsReviewModalProps {
  onClose?: () => void
  onLaunchCodexSuccess?: (ticketId: string, threadId: string) => void
}

const STATUS_OPTIONS = [
  { value: 'all', label: 'All Statuses' },
  { value: 'received', label: 'Received' },
  { value: 'under_review', label: 'Under Review' },
  { value: 'queued_for_codex', label: 'Queued for Codex' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'waiting_on_tenant', label: 'Needs Info' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' }
]

const PRIORITY_COLORS: Record<string, string> = {
  critical: 'border-rose-500/40 text-rose-400 bg-rose-500/10',
  high: 'border-amber-500/40 text-amber-400 bg-amber-500/10',
  normal: 'border-blue-500/40 text-blue-400 bg-blue-500/10',
  low: 'border-slate-500/40 text-slate-400 bg-slate-500/10'
}

export const SupportTicketsReviewModal: React.FC<SupportTicketsReviewModalProps> = ({
  onClose,
  onLaunchCodexSuccess
}) => {
  const [tickets, setTickets] = useState<SupportTicketListItem[]>([])
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null)
  const [ticketDetail, setTicketDetail] = useState<SupportTicketDetail | null>(null)
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [statusFilter, setStatusFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Reply / Note Form State
  const [activeMessageTab, setActiveMessageTab] = useState<'internal' | 'tenant'>('internal')
  const [messageBody, setMessageBody] = useState('')
  const [isSubmittingMessage, setIsSubmittingMessage] = useState(false)
  const [isLaunchingCodex, setIsLaunchingCodex] = useState(false)
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false)
  const [actionSuccessNotice, setActionSuccessNotice] = useState<string | null>(null)

  // Fetch list of tickets
  const fetchTickets = useCallback(async () => {
    setLoadingList(true)
    setErrorMsg(null)
    try {
      const params = new URLSearchParams()
      if (statusFilter !== 'all') params.append('status', statusFilter)
      if (categoryFilter !== 'all') params.append('category', categoryFilter)

      const qs = params.toString() ? `?${params.toString()}` : ''
      const res = await fetch(`/api/admin/support-tickets${qs}`, {
        headers: getAuthenticatedAdminHeaders('application/json')
      })
      if (!res.ok) {
        throw new Error(`Failed to load tickets (HTTP ${res.status})`)
      }
      const data = await res.json()
      setTickets(Array.isArray(data) ? data : [])
      if (data.length > 0 && !selectedTicketId) {
        setSelectedTicketId(data[0].id)
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Error fetching support tickets')
    } finally {
      setLoadingList(false)
    }
  }, [statusFilter, categoryFilter, selectedTicketId])

  // Fetch full detail of selected ticket
  const fetchTicketDetail = useCallback(async (ticketId: string) => {
    setLoadingDetail(true)
    setErrorMsg(null)
    try {
      const res = await fetch(`/api/admin/support-tickets/${ticketId}`, {
        headers: getAuthenticatedAdminHeaders('application/json')
      })
      if (!res.ok) {
        throw new Error(`Failed to load ticket details (HTTP ${res.status})`)
      }
      const data = await res.json()
      setTicketDetail(data)
    } catch (err: any) {
      setErrorMsg(err.message || 'Error fetching ticket details')
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  useEffect(() => {
    fetchTickets()
  }, [fetchTickets])

  useEffect(() => {
    if (selectedTicketId) {
      fetchTicketDetail(selectedTicketId)
    }
  }, [selectedTicketId, fetchTicketDetail])

  // Handle posting internal note or tenant reply
  const handleSendMessage = async () => {
    if (!selectedTicketId || !messageBody.trim()) return
    setIsSubmittingMessage(true)
    setErrorMsg(null)
    setActionSuccessNotice(null)

    const endpoint =
      activeMessageTab === 'internal'
        ? `/api/admin/support-tickets/${selectedTicketId}/internal-note`
        : `/api/admin/support-tickets/${selectedTicketId}/tenant-reply`

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: getAuthenticatedAdminHeaders('application/json'),
        body: JSON.stringify({ body: messageBody.trim() })
      })
      if (!res.ok) {
        throw new Error(`Failed to post message (HTTP ${res.status})`)
      }
      setMessageBody('')
      setActionSuccessNotice(
        activeMessageTab === 'internal'
          ? 'Internal note recorded.'
          : 'Tenant reply sent successfully.'
      )
      await fetchTicketDetail(selectedTicketId)
      await fetchTickets()
    } catch (err: any) {
      setErrorMsg(err.message || 'Error posting message')
    } finally {
      setIsSubmittingMessage(false)
    }
  }

  // Handle status update
  const handleUpdateStatus = async (newStatus: string) => {
    if (!selectedTicketId) return
    setIsUpdatingStatus(true)
    setErrorMsg(null)
    try {
      const res = await fetch(`/api/admin/support-tickets/${selectedTicketId}/status`, {
        method: 'PATCH',
        headers: getAuthenticatedAdminHeaders('application/json'),
        body: JSON.stringify({ status: newStatus })
      })
      if (!res.ok) {
        throw new Error(`Failed to update status (HTTP ${res.status})`)
      }
      const updated = await res.json()
      setTicketDetail(updated)
      setActionSuccessNotice(`Ticket status updated to ${newStatus}`)
      await fetchTickets()
    } catch (err: any) {
      setErrorMsg(err.message || 'Error updating status')
    } finally {
      setIsUpdatingStatus(false)
    }
  }

  // Handle Codex investigation launch
  const handleLaunchCodex = async () => {
    if (!selectedTicketId) return
    setIsLaunchingCodex(true)
    setErrorMsg(null)
    setActionSuccessNotice(null)
    try {
      const res = await fetch(`/api/admin/support-tickets/${selectedTicketId}/launch-codex`, {
        method: 'POST',
        headers: getAuthenticatedAdminHeaders('application/json'),
        body: JSON.stringify({})
      })
      if (!res.ok) {
        throw new Error(`Failed to launch Codex investigation (HTTP ${res.status})`)
      }
      const data = await res.json()
      setActionSuccessNotice(`Codex investigation dispatched! Thread: ${data.codex_thread_id}`)
      await fetchTicketDetail(selectedTicketId)
      await fetchTickets()

      if (onLaunchCodexSuccess) {
        onLaunchCodexSuccess(selectedTicketId, data.codex_thread_id)
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Error launching Codex investigation')
    } finally {
      setIsLaunchingCodex(false)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-[550px] bg-card text-foreground">
      {/* Top Banner / Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 border-b border-border bg-muted/40 shrink-0">
        <div className="flex items-center gap-2">
          <Headphones className="w-4 h-4 text-emerald-400" />
          <span className="font-semibold text-xs tracking-tight">Platform Owner Support Review Queue</span>
          <Badge variant="outline" className="text-[10px] font-mono px-1.5 py-0 border-border bg-background">
            {tickets.length} Inbound
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Filter className="w-3.5 h-3.5" />
            <span>Filter:</span>
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-7 text-xs rounded border border-border bg-background px-2 text-foreground focus:outline-none"
            aria-label="Filter tickets by status"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <Button
            size="sm"
            variant="outline"
            onClick={() => fetchTickets()}
            disabled={loadingList}
            className="h-7 px-2 text-xs gap-1 border-border bg-background hover:bg-muted text-foreground cursor-pointer"
            title="Refresh tickets"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingList ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {/* Error / Success Notices */}
      {errorMsg && (
        <div className="p-2.5 mx-3 mt-2 rounded-md bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2 shrink-0">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="truncate">{errorMsg}</span>
        </div>
      )}
      {actionSuccessNotice && (
        <div className="p-2.5 mx-3 mt-2 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2 shrink-0">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span className="truncate">{actionSuccessNotice}</span>
        </div>
      )}

      {/* Main Split Content: Left List & Right Detail */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left Ticket List Column */}
        <div className="w-full md:w-80 lg:w-96 border-r border-border flex flex-col bg-slate-950/20 shrink-0">
          <div className="p-2 border-b border-border/80 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            Inbound Escalations
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-border/60">
            {loadingList && tickets.length === 0 ? (
              <div className="p-6 text-center text-xs text-muted-foreground flex flex-col items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-muted-foreground" />
                <span>Loading tickets...</span>
              </div>
            ) : tickets.length === 0 ? (
              <div className="p-6 text-center text-xs text-muted-foreground">
                No support tickets match the selected filter.
              </div>
            ) : (
              tickets.map((t) => {
                const isSelected = t.id === selectedTicketId
                return (
                  <div
                    key={t.id}
                    onClick={() => setSelectedTicketId(t.id)}
                    className={`p-3 cursor-pointer transition-colors hover:bg-muted/60 ${
                      isSelected ? 'bg-primary/10 border-l-2 border-primary text-foreground' : 'text-foreground'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1 mb-1">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <Badge
                          variant="outline"
                          className="text-[9px] px-1 py-0 border-border bg-muted/80 text-foreground font-mono shrink-0"
                        >
                          T#{t.tenant_id}
                        </Badge>
                        <Badge
                          variant="outline"
                          className="text-[9px] px-1 py-0 border-primary/30 bg-primary/5 text-primary capitalize shrink-0"
                        >
                          {t.category}
                        </Badge>
                      </div>
                      <Badge
                        variant="outline"
                        className={`text-[9px] px-1 py-0 capitalize shrink-0 ${
                          PRIORITY_COLORS[t.triage_priority] || PRIORITY_COLORS.normal
                        }`}
                      >
                        {t.triage_priority}
                      </Badge>
                    </div>

                    <h4 className="text-xs font-semibold truncate mb-1 text-foreground leading-tight">{t.title}</h4>

                    <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                      <span className="font-medium text-foreground/80">{t.tenant_status}</span>
                      <div className="flex items-center gap-2">
                        {t.codex_thread_id && (
                          <span className="inline-flex items-center gap-1 text-[9px] text-indigo-400 font-mono">
                            <Sparkles className="w-2.5 h-2.5" />
                            Codex
                          </span>
                        )}
                        <span className="inline-flex items-center gap-0.5">
                          <MessageSquare className="w-2.5 h-2.5" />
                          {t.message_count}
                        </span>
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Right Ticket Detail Column */}
        <div className="flex-1 flex flex-col min-h-0 bg-background overflow-y-auto">
          {loadingDetail && !ticketDetail ? (
            <div className="flex-1 flex items-center justify-center p-8 text-xs text-muted-foreground gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-primary" />
              <span>Loading ticket details...</span>
            </div>
          ) : !ticketDetail ? (
            <div className="flex-1 flex items-center justify-center p-8 text-xs text-muted-foreground">
              Select a support ticket from the list to review details.
            </div>
          ) : (
            <div className="flex flex-col h-full">
              {/* Detail Header & Launch Codex Bar */}
              <div className="p-4 border-b border-border bg-card shrink-0 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-border bg-muted text-foreground font-mono">
                        Tenant #{ticketDetail.tenant_id}
                      </Badge>
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-primary/30 text-primary capitalize">
                        {ticketDetail.category}
                      </Badge>
                      <Badge
                        variant="outline"
                        className={`text-[10px] px-1.5 py-0 capitalize ${
                          PRIORITY_COLORS[ticketDetail.triage_priority] || PRIORITY_COLORS.normal
                        }`}
                      >
                        {ticketDetail.triage_priority} Priority
                      </Badge>
                      <span className="text-[10px] text-muted-foreground">
                        Created {new Date(ticketDetail.created_at).toLocaleString()}
                      </span>
                    </div>

                    <h2 className="text-base font-bold text-foreground leading-snug m-0">{ticketDetail.title}</h2>
                  </div>

                  {/* Primary Review Action: Launch / Open Codex Investigation */}
                  <div className="flex items-center gap-2 shrink-0">
                    {ticketDetail.codex_thread_id ? (
                      <Button
                        size="sm"
                        onClick={() => {
                          if (onLaunchCodexSuccess) {
                            onLaunchCodexSuccess(ticketDetail.id, ticketDetail.codex_thread_id!)
                          }
                        }}
                        className="h-8 px-3 text-xs gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium cursor-pointer"
                        title="Open linked investigation thread in workbench"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        <span>Open Codex Thread</span>
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        onClick={handleLaunchCodex}
                        disabled={isLaunchingCodex}
                        className="h-8 px-3 text-xs gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold cursor-pointer shadow-xs"
                        title="Platform Owner Review Gate: Launch autonomous Codex investigation"
                      >
                        <Sparkles className={`w-3.5 h-3.5 ${isLaunchingCodex ? 'animate-spin' : ''}`} />
                        <span>{isLaunchingCodex ? 'Launching Codex...' : 'Launch Codex Investigation'}</span>
                      </Button>
                    )}
                  </div>
                </div>

                {/* Status Triage Dropdown Selector */}
                <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border/60 text-xs">
                  <span className="text-muted-foreground font-medium">Triage Status:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      { val: 'received', label: 'Received' },
                      { val: 'under_review', label: 'Under Review' },
                      { val: 'queued_for_codex', label: 'Queued for Codex' },
                      { val: 'in_progress', label: 'In Progress' },
                      { val: 'waiting_on_tenant', label: 'Waiting on Tenant' },
                      { val: 'resolved', label: 'Resolved' },
                      { val: 'closed', label: 'Closed' }
                    ].map((s) => (
                      <button
                        key={s.val}
                        disabled={isUpdatingStatus}
                        onClick={() => handleUpdateStatus(s.val)}
                        className={`px-2 py-0.5 rounded text-[11px] font-medium border transition-colors cursor-pointer ${
                          ticketDetail.status === s.val
                            ? 'bg-primary text-primary-foreground border-primary'
                            : 'bg-muted/60 text-muted-foreground border-border hover:bg-muted hover:text-foreground'
                        }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Detail Body (Scrollable) */}
              <div className="flex-1 p-4 space-y-4 overflow-y-auto">
                {/* Description Card */}
                <div className="p-3.5 rounded-lg border border-border bg-card/60 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                    <FileText className="w-3.5 h-3.5 text-primary" />
                    <span>Customer Issue Description (Sanitized)</span>
                  </div>
                  <p className="text-xs text-foreground/90 whitespace-pre-wrap leading-relaxed m-0">
                    {ticketDetail.description}
                  </p>
                </div>

                {/* Error Context Card (if present) */}
                {ticketDetail.error_context && (
                  <div className="p-3.5 rounded-lg border border-amber-500/30 bg-amber-500/5 space-y-2">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-400">
                      <AlertCircle className="w-3.5 h-3.5" />
                      <span>Captured Error Context</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-mono">
                      {ticketDetail.error_context.route && (
                        <div className="p-1.5 rounded bg-black/20 border border-border/40">
                          <span className="text-muted-foreground block text-[10px]">Route:</span>
                          <span className="text-foreground">{ticketDetail.error_context.route}</span>
                        </div>
                      )}
                      {ticketDetail.error_context.error_code && (
                        <div className="p-1.5 rounded bg-black/20 border border-border/40">
                          <span className="text-muted-foreground block text-[10px]">Error Code:</span>
                          <span className="text-amber-400">{ticketDetail.error_context.error_code}</span>
                        </div>
                      )}
                      {ticketDetail.error_context.action_attempted && (
                        <div className="p-1.5 rounded bg-black/20 border border-border/40 sm:col-span-2">
                          <span className="text-muted-foreground block text-[10px]">Action Attempted:</span>
                          <span className="text-foreground">{ticketDetail.error_context.action_attempted}</span>
                        </div>
                      )}
                      {ticketDetail.error_context.error_message && (
                        <div className="p-1.5 rounded bg-black/20 border border-border/40 sm:col-span-2">
                          <span className="text-muted-foreground block text-[10px]">Error Message:</span>
                          <span className="text-rose-400">{ticketDetail.error_context.error_message}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Threaded Discussion (Tenant messages + Internal notes) */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs font-semibold text-foreground border-b border-border pb-1.5">
                    <span className="flex items-center gap-1.5">
                      <MessageSquare className="w-3.5 h-3.5 text-primary" />
                      <span>Threaded Discussion & Activity ({ticketDetail.messages.length})</span>
                    </span>
                  </div>

                  <div className="space-y-2.5">
                    {ticketDetail.messages.length === 0 ? (
                      <p className="text-xs text-muted-foreground italic py-2">
                        No messages in this ticket thread yet.
                      </p>
                    ) : (
                      ticketDetail.messages.map((m) => {
                        const isInternal = m.visibility === 'internal_only'
                        return (
                          <div
                            key={m.id}
                            className={`p-3 rounded-lg border text-xs leading-relaxed ${
                              isInternal
                                ? 'bg-amber-950/20 border-amber-500/40 text-amber-200'
                                : m.sender_type === 'platform_owner'
                                ? 'bg-primary/10 border-primary/30 text-foreground'
                                : 'bg-muted/40 border-border text-foreground'
                            }`}
                          >
                            <div className="flex items-center justify-between gap-2 mb-1 text-[10px]">
                              <div className="flex items-center gap-1.5">
                                {isInternal ? (
                                  <span className="inline-flex items-center gap-1 font-bold text-amber-400 uppercase tracking-wider text-[9px] bg-amber-500/20 px-1 py-0.2 rounded border border-amber-500/40">
                                    <Lock className="w-2.5 h-2.5" />
                                    Internal Note
                                  </span>
                                ) : (
                                  <span className="font-semibold text-foreground capitalize">
                                    {m.sender_type.replace('_', ' ')}
                                  </span>
                                )}
                              </div>
                              <span className="text-muted-foreground">
                                {new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </span>
                            </div>
                            <p className="m-0 whitespace-pre-wrap">{m.body}</p>
                          </div>
                        )
                      })
                    )}
                  </div>
                </div>

                {/* Reply / Internal Note Input Box */}
                <div className="p-3 rounded-lg border border-border bg-card/80 space-y-2">
                  <div className="flex items-center gap-2 border-b border-border pb-2 text-xs">
                    <button
                      type="button"
                      onClick={() => setActiveMessageTab('internal')}
                      className={`px-2.5 py-1 rounded text-xs font-medium cursor-pointer transition-colors ${
                        activeMessageTab === 'internal'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      Post Internal Note
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveMessageTab('tenant')}
                      className={`px-2.5 py-1 rounded text-xs font-medium cursor-pointer transition-colors ${
                        activeMessageTab === 'tenant'
                          ? 'bg-primary/20 text-primary border border-primary/40'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      Send Tenant Reply
                    </button>
                  </div>

                  <Textarea
                    value={messageBody}
                    onChange={(e) => setMessageBody(e.target.value)}
                    placeholder={
                      activeMessageTab === 'internal'
                        ? 'Write private engineering or triage note (never visible to customer)...'
                        : 'Write message visible to tenant customer...'
                    }
                    rows={3}
                    className="w-full text-xs bg-background border-border text-foreground resize-none"
                  />

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[10px] text-muted-foreground">
                      {activeMessageTab === 'internal'
                        ? 'Stored with visibility=internal_only'
                        : 'Stored with visibility=tenant_visible'}
                    </span>
                    <Button
                      size="sm"
                      onClick={handleSendMessage}
                      disabled={isSubmittingMessage || !messageBody.trim()}
                      className="h-7 px-3 text-xs gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground font-medium cursor-pointer"
                    >
                      <Send className="w-3 h-3" />
                      <span>{isSubmittingMessage ? 'Sending...' : 'Post Message'}</span>
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default SupportTicketsReviewModal
