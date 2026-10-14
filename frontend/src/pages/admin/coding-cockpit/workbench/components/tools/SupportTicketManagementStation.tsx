import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Headphones,
  Sparkles,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Send,
  FileText,
  MessageSquare,
  ExternalLink,
  Lock,
  Search,
  ShieldAlert,
  ArrowRight,
  User,
  Zap,
  MessageCircle,
  CheckCheck
} from 'lucide-react'
import { getAuthenticatedAdminHeaders } from '@/lib/api'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import { Textarea } from '../ui/textarea'
import { Input } from '../ui/input'
import { useWorkbenchStore } from '../../store/useWorkbenchStore'

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

interface SupportTicketManagementStationProps {
  onClose?: () => void
  isCenterStage?: boolean
  onLaunchCodexSuccess?: (ticketId: string, threadId: string) => void
}

type FilterTab = 'all' | 'needs_authorization' | 'active_investigation' | 'waiting_on_tenant' | 'resolved'

const PRIORITY_OPTIONS = [
  { value: 'all', label: 'All Priorities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'normal', label: 'Normal' },
  { value: 'low', label: 'Low' }
]

const STATUS_OPTIONS = [
  { value: 'received', label: 'Received (Needs Auth)' },
  { value: 'under_review', label: 'Under Review' },
  { value: 'queued_for_codex', label: 'Queued for Codex' },
  { value: 'in_progress', label: 'Investigation Running' },
  { value: 'waiting_on_tenant', label: 'Waiting on Tenant' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' }
]

const PRIORITY_BADGES: Record<string, { label: string; className: string }> = {
  critical: { label: 'Critical', className: 'border-rose-500/50 text-rose-400 bg-rose-500/15' },
  high: { label: 'High', className: 'border-amber-500/50 text-amber-400 bg-amber-500/15' },
  normal: { label: 'Normal', className: 'border-blue-500/40 text-blue-400 bg-blue-500/10' },
  low: { label: 'Low', className: 'border-slate-500/40 text-slate-400 bg-slate-500/10' }
}

export const SupportTicketManagementStation: React.FC<SupportTicketManagementStationProps> = ({
  onClose,
  isCenterStage = false,
  onLaunchCodexSuccess
}) => {
  const { openThreadById, setActiveCenterView, fetchSupportTicketsSummary } = useWorkbenchStore()

  const [tickets, setTickets] = useState<SupportTicketListItem[]>([])
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null)
  const [ticketDetail, setTicketDetail] = useState<SupportTicketDetail | null>(null)
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  
  // Filters
  const [activeTab, setActiveTab] = useState<FilterTab>('all')
  const [priorityFilter, setPriorityFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  
  // Notices & state
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [actionSuccessNotice, setActionSuccessNotice] = useState<string | null>(null)
  
  // Composer state
  const [activeMessageTab, setActiveMessageTab] = useState<'tenant' | 'internal'>('tenant')
  const [messageBody, setMessageBody] = useState('')
  const [isSubmittingMessage, setIsSubmittingMessage] = useState(false)
  const [isLaunchingCodex, setIsLaunchingCodex] = useState(false)
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false)

  // Fetch all tickets
  const fetchTickets = useCallback(async () => {
    setLoadingList(true)
    setErrorMsg(null)
    try {
      const res = await fetch('/api/admin/support-tickets', {
        headers: getAuthenticatedAdminHeaders('application/json')
      })
      if (!res.ok) {
        throw new Error(`Failed to load tickets (HTTP ${res.status})`)
      }
      const data = await res.json()
      const list = Array.isArray(data) ? data : []
      setTickets(list)
      if (list.length > 0 && !selectedTicketId) {
        setSelectedTicketId(list[0].id)
      }
      // Also refresh global store counter
      fetchSupportTicketsSummary?.()
    } catch (err: any) {
      setErrorMsg(err.message || 'Error fetching support tickets')
    } finally {
      setLoadingList(false)
    }
  }, [selectedTicketId, fetchSupportTicketsSummary])

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

  // Tab counts
  const tabCounts = useMemo(() => {
    return {
      all: tickets.length,
      needs_authorization: tickets.filter(t => t.status === 'received').length,
      active_investigation: tickets.filter(t => t.status === 'queued_for_codex' || t.status === 'in_progress').length,
      waiting_on_tenant: tickets.filter(t => t.status === 'waiting_on_tenant').length,
      resolved: tickets.filter(t => t.status === 'resolved' || t.status === 'closed').length
    }
  }, [tickets])

  // Filtered tickets based on active tab, priority, search
  const filteredTickets = useMemo(() => {
    return tickets.filter(t => {
      // 1. Tab filter
      if (activeTab === 'needs_authorization' && t.status !== 'received') return false
      if (activeTab === 'active_investigation' && t.status !== 'queued_for_codex' && t.status !== 'in_progress') return false
      if (activeTab === 'waiting_on_tenant' && t.status !== 'waiting_on_tenant') return false
      if (activeTab === 'resolved' && t.status !== 'resolved' && t.status !== 'closed') return false

      // 2. Priority filter
      if (priorityFilter !== 'all' && t.triage_priority !== priorityFilter) return false

      // 3. Search query
      if (searchQuery.trim()) {
        const query = searchQuery.trim().toLowerCase()
        const matchTitle = t.title.toLowerCase().includes(query)
        const matchDesc = t.description?.toLowerCase().includes(query)
        const matchTenant = String(t.tenant_id).includes(query)
        const matchCat = t.category.toLowerCase().includes(query)
        if (!matchTitle && !matchDesc && !matchTenant && !matchCat) return false
      }

      return true
    })
  }, [tickets, activeTab, priorityFilter, searchQuery])

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
      setActionSuccessNotice(`Ticket status updated to ${newStatus.replace(/_/g, ' ')}`)
      await fetchTickets()
    } catch (err: any) {
      setErrorMsg(err.message || 'Error updating status')
    } finally {
      setIsUpdatingStatus(false)
    }
  }

  // Handle priority update
  const handleUpdatePriority = async (newPriority: string) => {
    if (!selectedTicketId) return
    setIsUpdatingStatus(true)
    setErrorMsg(null)
    try {
      const res = await fetch(`/api/admin/support-tickets/${selectedTicketId}/status`, {
        method: 'PATCH',
        headers: getAuthenticatedAdminHeaders('application/json'),
        body: JSON.stringify({ triage_priority: newPriority })
      })
      if (!res.ok) {
        throw new Error(`Failed to update priority (HTTP ${res.status})`)
      }
      const updated = await res.json()
      setTicketDetail(updated)
      setActionSuccessNotice(`Ticket priority updated to ${newPriority}`)
      await fetchTickets()
    } catch (err: any) {
      setErrorMsg(err.message || 'Error updating priority')
    } finally {
      setIsUpdatingStatus(false)
    }
  }

  // Handle posting message (tenant reply or internal note)
  const handleSendMessage = async (forceWaitingOnTenant = false) => {
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

      if (forceWaitingOnTenant) {
        await fetch(`/api/admin/support-tickets/${selectedTicketId}/status`, {
          method: 'PATCH',
          headers: getAuthenticatedAdminHeaders('application/json'),
          body: JSON.stringify({ status: 'waiting_on_tenant' })
        })
      }

      setMessageBody('')
      setActionSuccessNotice(
        activeMessageTab === 'internal'
          ? 'Internal note recorded.'
          : forceWaitingOnTenant
          ? 'Reply sent to tenant and ticket status set to Waiting on Tenant.'
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
      setActionSuccessNotice(`⚡ Codex investigation launched! Thread: ${data.codex_thread_id}`)
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

  // Jump to active thread in cockpit
  const handleSwitchToThread = (threadId: string) => {
    if (onClose) {
      onClose()
    }
    setActiveCenterView('timeline')
    openThreadById(threadId)
  }

  return (
    <div className="flex flex-col h-full w-full min-h-[550px] bg-card text-foreground overflow-hidden select-none">
      {/* Top Navigation & Filter Bar */}
      <div className="border-b border-border bg-card/95 shrink-0 px-3 py-2.5 space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          {/* Title & Badge */}
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center shrink-0">
              <Headphones className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-foreground leading-tight m-0">
                  Support Ticket Management Center
                </h2>
                {tabCounts.needs_authorization > 0 ? (
                  <Badge variant="outline" className="text-[10px] font-mono px-1.5 py-0 border-amber-500/50 bg-amber-500/15 text-amber-400 font-semibold">
                    ⚠️ {tabCounts.needs_authorization} Needs Auth
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-[10px] font-mono px-1.5 py-0 border-border bg-background text-muted-foreground">
                    {tickets.length} Total
                  </Badge>
                )}
              </div>
              <p className="text-[11px] text-muted-foreground leading-tight mt-0.5">
                Triage incoming escalations, review captured error context, authorize Codex investigations, and converse with tenants.
              </p>
            </div>
          </div>

          {/* Quick actions (Back to Timeline if in Center Stage, Refresh button) */}
          <div className="flex items-center gap-2">
            {isCenterStage && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setActiveCenterView('timeline')}
                className="h-8 px-2.5 text-xs gap-1.5 border-border bg-background hover:bg-muted text-foreground cursor-pointer"
                title="Switch back to active engineering thread"
              >
                <ArrowRight className="w-3.5 h-3.5 text-primary rotate-180" />
                <span>Return to Timeline</span>
              </Button>
            )}

            <Button
              size="sm"
              variant="outline"
              onClick={() => fetchTickets()}
              disabled={loadingList}
              className="h-8 px-2.5 text-xs gap-1.5 border-border bg-background hover:bg-muted text-foreground cursor-pointer"
              title="Refresh tickets from server"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingList ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Refresh</span>
            </Button>
          </div>
        </div>

        {/* Tab Filters Row */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-border/50">
          {/* Filter Tabs */}
          <div className="flex flex-wrap items-center gap-1">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'all'
                  ? 'bg-primary text-primary-foreground font-semibold shadow-xs'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/60'
              }`}
            >
              <span>All Tickets</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${activeTab === 'all' ? 'bg-primary-foreground/20 text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>
                {tabCounts.all}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('needs_authorization')}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'needs_authorization'
                  ? 'bg-amber-500 text-slate-950 font-bold shadow-xs'
                  : 'text-amber-400 hover:bg-amber-500/10'
              }`}
            >
              <span>⚠️ Needs Authorization</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${activeTab === 'needs_authorization' ? 'bg-black/30 text-slate-950 font-bold' : 'bg-amber-500/20 text-amber-400'}`}>
                {tabCounts.needs_authorization}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('active_investigation')}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'active_investigation'
                  ? 'bg-indigo-600 text-white font-semibold shadow-xs'
                  : 'text-indigo-400 hover:bg-indigo-600/10'
              }`}
            >
              <span>⚡ Active Investigations</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${activeTab === 'active_investigation' ? 'bg-white/20 text-white' : 'bg-indigo-600/20 text-indigo-400'}`}>
                {tabCounts.active_investigation}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('waiting_on_tenant')}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'waiting_on_tenant'
                  ? 'bg-purple-600 text-white font-semibold shadow-xs'
                  : 'text-purple-400 hover:bg-purple-600/10'
              }`}
            >
              <span>💬 Waiting on Tenant</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${activeTab === 'waiting_on_tenant' ? 'bg-white/20 text-white' : 'bg-purple-600/20 text-purple-400'}`}>
                {tabCounts.waiting_on_tenant}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('resolved')}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'resolved'
                  ? 'bg-emerald-600 text-white font-semibold shadow-xs'
                  : 'text-emerald-400 hover:bg-emerald-600/10'
              }`}
            >
              <span>✅ Resolved</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${activeTab === 'resolved' ? 'bg-white/20 text-white' : 'bg-emerald-600/20 text-emerald-400'}`}>
                {tabCounts.resolved}
              </span>
            </button>
          </div>

          {/* Search & Priority Selector */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search tenant or issue..."
                className="h-7 w-40 sm:w-52 pl-8 pr-2 text-xs bg-background border-border text-foreground"
              />
            </div>

            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="h-7 text-xs rounded border border-border bg-background px-2 text-foreground focus:outline-none"
              aria-label="Filter tickets by priority"
            >
              {PRIORITY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Error / Success Notifications */}
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

      {/* Main Split Body: Left Master List + Right Comprehensive Management Station */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left Column: Tickets Master List */}
        <div className="w-full md:w-80 lg:w-96 border-r border-border flex flex-col bg-slate-950/25 shrink-0 overflow-hidden">
          <div className="px-3 py-2 border-b border-border/70 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center justify-between">
            <span>Inbound Tickets ({filteredTickets.length})</span>
            {activeTab !== 'all' && (
              <span className="text-[10px] text-primary lowercase">filtered</span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-border/60">
            {loadingList && tickets.length === 0 ? (
              <div className="p-8 text-center text-xs text-muted-foreground flex flex-col items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-primary" />
                <span>Loading tickets...</span>
              </div>
            ) : filteredTickets.length === 0 ? (
              <div className="p-8 text-center text-xs text-muted-foreground space-y-1">
                <p className="font-medium text-foreground">No tickets match this filter</p>
                <p className="text-[11px] text-muted-foreground">Try clearing your search or switching filter tabs.</p>
              </div>
            ) : (
              filteredTickets.map((t) => {
                const isSelected = t.id === selectedTicketId
                const isReceived = t.status === 'received'
                const isInvestigating = t.status === 'in_progress' || t.status === 'queued_for_codex'
                const isWaiting = t.status === 'waiting_on_tenant'
                const isResolved = t.status === 'resolved' || t.status === 'closed'
                const isHighUrgency = t.triage_priority === 'critical' || t.triage_priority === 'high'

                return (
                  <div
                    key={t.id}
                    onClick={() => setSelectedTicketId(t.id)}
                    className={`p-3 cursor-pointer transition-colors relative border-l-2 ${
                      isSelected
                        ? 'bg-primary/10 border-l-primary text-foreground'
                        : isReceived
                        ? 'border-l-amber-500/80 bg-amber-500/5 hover:bg-amber-500/10 text-foreground'
                        : isInvestigating
                        ? 'border-l-indigo-500/80 bg-indigo-500/5 hover:bg-indigo-500/10 text-foreground'
                        : 'border-l-transparent hover:bg-muted/60 text-foreground'
                    }`}
                  >
                    {/* Header Row: Tenant, Category, Priority Urgency */}
                    <div className="flex items-center justify-between gap-1 mb-1.5">
                      <div className="flex items-center gap-1.5 min-w-0">
                        {isHighUrgency && (
                          <span className="w-2 h-2 rounded-full bg-rose-500 shrink-0 animate-pulse" title="High Urgency" />
                        )}
                        <Badge
                          variant="outline"
                          className="text-[9px] px-1.5 py-0 border-border bg-slate-800 text-foreground font-mono shrink-0"
                        >
                          T#{t.tenant_id}
                        </Badge>
                        <Badge
                          variant="outline"
                          className="text-[9px] px-1.5 py-0 border-primary/30 bg-primary/5 text-primary capitalize shrink-0"
                        >
                          {t.category}
                        </Badge>
                      </div>

                      <Badge
                        variant="outline"
                        className={`text-[9px] px-1 py-0 capitalize shrink-0 font-medium ${
                          PRIORITY_BADGES[t.triage_priority]?.className || PRIORITY_BADGES.normal.className
                        }`}
                      >
                        {t.triage_priority}
                      </Badge>
                    </div>

                    {/* Title */}
                    <h4 className="text-xs font-semibold line-clamp-2 mb-1.5 text-foreground leading-snug">
                      {t.title}
                    </h4>

                    {/* Prominent Status Chip */}
                    <div className="mb-2">
                      {isReceived && (
                        <span className="inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/40">
                          <ShieldAlert className="w-2.5 h-2.5" />
                          NEEDS AUTHORIZATION
                        </span>
                      )}
                      {isInvestigating && (
                        <span className="inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/40">
                          <Zap className="w-2.5 h-2.5" />
                          INVESTIGATION RUNNING
                        </span>
                      )}
                      {isWaiting && (
                        <span className="inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 border border-purple-500/40">
                          <MessageCircle className="w-2.5 h-2.5" />
                          WAITING ON TENANT
                        </span>
                      )}
                      {isResolved && (
                        <span className="inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                          <CheckCheck className="w-2.5 h-2.5" />
                          RESOLVED
                        </span>
                      )}
                      {!isReceived && !isInvestigating && !isWaiting && !isResolved && (
                        <span className="inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 uppercase">
                          {t.status.replace(/_/g, ' ')}
                        </span>
                      )}
                    </div>

                    {/* Footer Row: Thread info, message count, date */}
                    <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1 border-t border-border/40">
                      <div className="flex items-center gap-1">
                        {t.codex_thread_id ? (
                          <span className="inline-flex items-center gap-1 text-[9px] text-indigo-400 font-mono font-medium">
                            <Sparkles className="w-2.5 h-2.5" />
                            Codex Linked
                          </span>
                        ) : (
                          <span className="text-[10px] text-muted-foreground/80 font-mono truncate max-w-[100px]">
                            {t.id.slice(0, 8)}...
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center gap-0.5">
                          <MessageSquare className="w-2.5 h-2.5" />
                          {t.message_count}
                        </span>
                        <span>{new Date(t.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}</span>
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Right Column: Full Detail & Management Station */}
        <div className="flex-1 flex flex-col min-h-0 bg-background overflow-hidden">
          {loadingDetail && !ticketDetail ? (
            <div className="flex-1 flex items-center justify-center p-8 text-xs text-muted-foreground gap-2">
              <RefreshCw className="w-4 h-4 animate-spin text-primary" />
              <span>Loading ticket details...</span>
            </div>
          ) : !ticketDetail ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-xs text-muted-foreground space-y-2">
              <Headphones className="w-10 h-10 text-muted-foreground/40" />
              <p className="font-semibold text-foreground text-sm">No ticket selected</p>
              <p className="max-w-sm text-muted-foreground">Select a ticket from the master list to inspect error context, authorize Codex investigations, or reply to the tenant.</p>
            </div>
          ) : (
            <div className="flex flex-col h-full min-h-0 overflow-y-auto">
              {/* 1. Header with Title, Tenant Info, and Status/Priority Dropdowns */}
              <div className="p-4 border-b border-border bg-card shrink-0 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 mb-1.5">
                      <Badge variant="outline" className="text-[10px] px-2 py-0.5 border-border bg-slate-800 text-foreground font-mono">
                        Tenant #{ticketDetail.tenant_id}
                      </Badge>
                      <Badge variant="outline" className="text-[10px] px-2 py-0.5 border-primary/30 text-primary capitalize font-medium">
                        {ticketDetail.category}
                      </Badge>
                      <span className="text-[11px] text-muted-foreground font-mono">
                        ID: {ticketDetail.id}
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        • Created {new Date(ticketDetail.created_at).toLocaleString()}
                      </span>
                    </div>

                    <h1 className="text-base sm:text-lg font-bold text-foreground leading-snug m-0">
                      {ticketDetail.title}
                    </h1>
                  </div>

                  {/* Top Status & Priority Quick Selectors */}
                  <div className="flex flex-wrap items-center gap-2 shrink-0">
                    <div className="flex items-center gap-1.5 bg-muted/60 p-1 rounded-md border border-border">
                      <span className="text-[11px] text-muted-foreground px-1 font-medium">Status:</span>
                      <select
                        value={ticketDetail.status}
                        disabled={isUpdatingStatus}
                        onChange={(e) => handleUpdateStatus(e.target.value)}
                        className="h-7 text-xs rounded border border-border bg-background px-2 text-foreground font-medium focus:outline-none cursor-pointer"
                        aria-label="Update ticket status"
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s.value} value={s.value}>
                            {s.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="flex items-center gap-1.5 bg-muted/60 p-1 rounded-md border border-border">
                      <span className="text-[11px] text-muted-foreground px-1 font-medium">Priority:</span>
                      <select
                        value={ticketDetail.triage_priority}
                        disabled={isUpdatingStatus}
                        onChange={(e) => handleUpdatePriority(e.target.value)}
                        className="h-7 text-xs rounded border border-border bg-background px-2 text-foreground font-medium focus:outline-none cursor-pointer"
                        aria-label="Update ticket priority"
                      >
                        <option value="critical">Critical</option>
                        <option value="high">High</option>
                        <option value="normal">Normal</option>
                        <option value="low">Low</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* 2. Prominent Authorization & Action Banner */}
                {ticketDetail.status === 'received' ? (
                  <div className="p-3.5 rounded-lg border-2 border-amber-500/70 bg-amber-500/10 space-y-2.5 shadow-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-md bg-amber-500/20 border border-amber-500/50 flex items-center justify-center shrink-0">
                          <ShieldAlert className="w-4 h-4 text-amber-400" />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-amber-300 leading-tight m-0">
                            ⚡ Authorization Required: Tenant Reported Issue
                          </h4>
                          <p className="text-[11px] text-amber-200/80 leading-tight mt-0.5">
                            Review diagnostic context below and authorize an isolated Codex investigation worktree.
                          </p>
                        </div>
                      </div>

                      <Button
                        size="sm"
                        onClick={handleLaunchCodex}
                        disabled={isLaunchingCodex}
                        className="h-8 px-4 text-xs font-bold gap-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md cursor-pointer transition-transform active:scale-95"
                      >
                        <Sparkles className={`w-3.5 h-3.5 ${isLaunchingCodex ? 'animate-spin' : ''}`} />
                        <span>{isLaunchingCodex ? 'Launching Codex...' : 'Authorize & Launch Codex Investigation'}</span>
                      </Button>
                    </div>
                  </div>
                ) : ticketDetail.codex_thread_id ? (
                  <div className="p-3 rounded-lg border border-indigo-500/40 bg-indigo-500/10 flex flex-wrap items-center justify-between gap-2.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="w-7 h-7 rounded-md bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center shrink-0">
                        <Zap className="w-4 h-4 text-indigo-400" />
                      </div>
                      <div className="min-w-0">
                        <span className="text-xs font-bold text-indigo-300 block leading-tight">
                          Codex Investigation Thread Linked
                        </span>
                        <span className="text-[11px] text-muted-foreground font-mono truncate block">
                          Thread ID: {ticketDetail.codex_thread_id}
                        </span>
                      </div>
                    </div>

                    <Button
                      size="sm"
                      onClick={() => handleSwitchToThread(ticketDetail.codex_thread_id!)}
                      className="h-8 px-3.5 text-xs font-semibold gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer shadow-xs"
                      title="Switch Center Stage to this live conversation thread"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      <span>Switch to Live Investigation Thread</span>
                    </Button>
                  </div>
                ) : (
                  <div className="p-2.5 rounded-lg border border-border bg-muted/40 flex items-center justify-between text-xs">
                    <span className="text-muted-foreground text-[11px]">
                      Ticket is {ticketDetail.status.replace(/_/g, ' ')}. Need an automated investigation?
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleLaunchCodex}
                      disabled={isLaunchingCodex}
                      className="h-7 px-2.5 text-xs gap-1.5 border-border bg-card hover:bg-muted text-foreground cursor-pointer"
                    >
                      <Sparkles className="w-3 h-3 text-primary" />
                      <span>Launch Codex Investigation</span>
                    </Button>
                  </div>
                )}
              </div>

              {/* 3. Detail Body */}
              <div className="flex-1 p-4 space-y-4">
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

                {/* Error Context Section (Inspector Card) */}
                {ticketDetail.error_context && (
                  <div className="p-3.5 rounded-lg border border-amber-500/40 bg-amber-500/5 space-y-2">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-400">
                      <AlertCircle className="w-3.5 h-3.5" />
                      <span>Captured Diagnostic Error Context</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-mono">
                      {ticketDetail.error_context.route && (
                        <div className="p-2 rounded bg-black/30 border border-border/50">
                          <span className="text-muted-foreground block text-[10px] font-sans">Route:</span>
                          <span className="text-foreground font-semibold">{ticketDetail.error_context.route}</span>
                        </div>
                      )}
                      {ticketDetail.error_context.error_code && (
                        <div className="p-2 rounded bg-black/30 border border-border/50">
                          <span className="text-muted-foreground block text-[10px] font-sans">Error Code:</span>
                          <span className="text-amber-400 font-bold">{ticketDetail.error_context.error_code}</span>
                        </div>
                      )}
                      {ticketDetail.error_context.action_attempted && (
                        <div className="p-2 rounded bg-black/30 border border-border/50 sm:col-span-2">
                          <span className="text-muted-foreground block text-[10px] font-sans">Action Attempted:</span>
                          <span className="text-foreground">{ticketDetail.error_context.action_attempted}</span>
                        </div>
                      )}
                      {ticketDetail.error_context.error_message && (
                        <div className="p-2 rounded bg-black/30 border border-border/50 sm:col-span-2">
                          <span className="text-muted-foreground block text-[10px] font-sans">Error Message:</span>
                          <span className="text-rose-400">{ticketDetail.error_context.error_message}</span>
                        </div>
                      )}
                      {ticketDetail.error_context.client_timestamp && (
                        <div className="p-2 rounded bg-black/30 border border-border/50 sm:col-span-2">
                          <span className="text-muted-foreground block text-[10px] font-sans">Client Timestamp:</span>
                          <span className="text-muted-foreground">{ticketDetail.error_context.client_timestamp}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Conversation & Message History */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs font-semibold text-foreground border-b border-border pb-1.5">
                    <span className="flex items-center gap-1.5">
                      <MessageSquare className="w-3.5 h-3.5 text-primary" />
                      <span>Communication History ({ticketDetail.messages.length})</span>
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      Yellow notes are internal engineering notes invisible to tenants
                    </span>
                  </div>

                  <div className="space-y-2.5">
                    {ticketDetail.messages.length === 0 ? (
                      <p className="text-xs text-muted-foreground italic py-3 text-center border border-dashed border-border rounded-lg">
                        No messages in this ticket thread yet. Use composer below to reply or record internal notes.
                      </p>
                    ) : (
                      ticketDetail.messages.map((m) => {
                        const isInternal = m.visibility === 'internal_only'
                        return (
                          <div
                            key={m.id}
                            className={`p-3.5 rounded-lg border text-xs leading-relaxed transition-all ${
                              isInternal
                                ? 'bg-amber-950/25 border-amber-500/50 text-amber-200 shadow-xs'
                                : m.sender_type === 'platform_owner'
                                ? 'bg-primary/10 border-primary/40 text-foreground'
                                : 'bg-muted/40 border-border text-foreground'
                            }`}
                          >
                            <div className="flex items-center justify-between gap-2 mb-1.5 text-[10px]">
                              <div className="flex items-center gap-2">
                                {isInternal ? (
                                  <span className="inline-flex items-center gap-1 font-bold text-amber-300 uppercase tracking-wider text-[9px] bg-amber-500/25 px-1.5 py-0.5 rounded border border-amber-500/50">
                                    <Lock className="w-2.5 h-2.5" />
                                    Internal Note - Invisible to Tenant
                                  </span>
                                ) : (
                                  <span className="font-bold text-foreground capitalize flex items-center gap-1">
                                    <User className="w-3 h-3 text-muted-foreground" />
                                    {m.sender_type.replace('_', ' ')}
                                  </span>
                                )}
                              </div>
                              <span className="text-muted-foreground font-mono">
                                {new Date(m.created_at).toLocaleString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' })}
                              </span>
                            </div>
                            <p className="m-0 whitespace-pre-wrap text-xs">{m.body}</p>
                          </div>
                        )
                      })
                    )}
                  </div>
                </div>

                {/* Message Composer with Dual Tabs and Quick Status Shortcuts */}
                <div className="p-3.5 rounded-lg border border-border bg-card/90 space-y-3">
                  <div className="flex items-center gap-2 border-b border-border pb-2 text-xs">
                    <button
                      type="button"
                      onClick={() => setActiveMessageTab('tenant')}
                      className={`px-3 py-1 rounded text-xs font-semibold cursor-pointer transition-colors flex items-center gap-1.5 ${
                        activeMessageTab === 'tenant'
                          ? 'bg-primary/20 text-primary border border-primary/40 shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <MessageSquare className="w-3.5 h-3.5" />
                      <span>Reply to Tenant</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setActiveMessageTab('internal')}
                      className={`px-3 py-1 rounded text-xs font-semibold cursor-pointer transition-colors flex items-center gap-1.5 ${
                        activeMessageTab === 'internal'
                          ? 'bg-amber-500/25 text-amber-300 border border-amber-500/50 shadow-xs'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <Lock className="w-3.5 h-3.5" />
                      <span>Internal Note</span>
                    </button>
                  </div>

                  <Textarea
                    value={messageBody}
                    onChange={(e) => setMessageBody(e.target.value)}
                    placeholder={
                      activeMessageTab === 'internal'
                        ? 'Write private engineering or triage note (invisible to tenant customer)...'
                        : 'Write message visible to tenant customer...'
                    }
                    rows={3}
                    className="w-full text-xs bg-background border-border text-foreground resize-none focus-visible:ring-primary"
                  />

                  <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                      {activeMessageTab === 'internal' ? (
                        <span className="text-amber-400/90 font-medium flex items-center gap-1">
                          <Lock className="w-3 h-3" />
                          Visible strictly to platform engineering
                        </span>
                      ) : (
                        <span className="text-primary font-medium flex items-center gap-1">
                          <User className="w-3 h-3" />
                          Visible to tenant customer
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {activeMessageTab === 'tenant' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSendMessage(true)}
                          disabled={isSubmittingMessage || !messageBody.trim()}
                          className="h-7 px-2.5 text-xs gap-1 border-purple-500/40 text-purple-400 bg-purple-500/10 hover:bg-purple-500/20 cursor-pointer"
                          title="Send message and transition status to Waiting on Tenant"
                        >
                          <Send className="w-3 h-3" />
                          <span>Reply & Mark Waiting on Tenant</span>
                        </Button>
                      )}

                      <Button
                        size="sm"
                        onClick={() => handleSendMessage(false)}
                        disabled={isSubmittingMessage || !messageBody.trim()}
                        className="h-7 px-3 text-xs gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold cursor-pointer"
                      >
                        <Send className="w-3 h-3" />
                        <span>{isSubmittingMessage ? 'Sending...' : 'Post Message'}</span>
                      </Button>
                    </div>
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

export default SupportTicketManagementStation
