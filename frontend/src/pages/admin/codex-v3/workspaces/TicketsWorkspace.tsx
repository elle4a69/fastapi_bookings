import React, { useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  Info,
  Search,
  Zap,
  CheckCircle2,
  Clock,
  ShieldCheck,
  ChevronRight,
  Code2
} from 'lucide-react'
import { cn } from '@/lib/utils'

export type TicketSeverity = 'high' | 'med' | 'low'
export type TicketStatus = 'all' | 'needs_auth' | 'in_progress' | 'resolved'

export interface SupportTicket {
  id: string
  title: string
  severity: TicketSeverity
  status: 'needs_auth' | 'in_progress' | 'resolved' | 'open'
  errorContext: string
  tenantId?: string
  createdAt: string
  category?: string
  route?: string
  stackTrace?: string
}

export interface TicketsWorkspaceProps {
  onLaunchInvestigation?: (ticket: SupportTicket) => void
  className?: string
}

const INITIAL_TICKETS: SupportTicket[] = [
  {
    id: 'ERR-503',
    title: 'Booking Engine Lock Contention in PostgreSQL',
    severity: 'high',
    status: 'needs_auth',
    tenantId: 'tenant_aura_wellness',
    category: 'Database / Concurrency',
    route: 'POST /api/v1/bookings/hold',
    createdAt: '4 mins ago',
    errorContext: 'DBTransactionTimeout: deadlock detected on appointment_locks table during high-frequency parallel hold requests for provider_id=14.',
    stackTrace: 'asyncpg.exceptions.DeadlockDetectedError: deadlock detected\nDETAIL: Process 1420 waits for ExclusiveLock on tuple (42, 8); blocked by process 1424.\n  at app/services/scheduling/booking_engine.py:184 in acquire_hold_lock\n  at app/api/v1/endpoints/bookings.py:92 in create_booking_hold'
  },
  {
    id: 'AUTH-401',
    title: 'Webhook Signature Verification Desync in Chatwoot Bridge',
    severity: 'med',
    status: 'in_progress',
    tenantId: 'tenant_harbor_clinic',
    category: 'Security / Auth',
    route: 'POST /api/webhooks/chatwoot',
    createdAt: '18 mins ago',
    errorContext: 'SignatureVerificationFailed: Inbound HMAC-SHA256 signature mismatch on Chatwoot conversation update event. Secret rotation delay suspected.',
    stackTrace: 'fastapi.HTTPException: 401 Unauthorized - Invalid webhook signature\n  at app/services/chatwoot/security.py:48 in verify_chatwoot_hmac\n  at app/api/v1/endpoints/chatwoot_bridge.py:65 in receive_chatwoot_event'
  },
  {
    id: 'SMS-429',
    title: 'Rate-Limit Exceeded on Outbound Reminder Carrier Gateway',
    severity: 'high',
    status: 'needs_auth',
    tenantId: 'tenant_summit_health',
    category: 'SMS / Gateway',
    route: 'POST /api/v1/sms/dispatch',
    createdAt: '32 mins ago',
    errorContext: 'TwilioGatewayError: Exceeded 100 msg/sec outbound limit for shortcode 88201. Queue backlog accumulated 14 messages.',
    stackTrace: 'TwilioRestException: [HTTP 429] Unable to create record: Too Many Requests\n  at app/services/sms/carrier_adapter.py:112 in dispatch_sms\n  at app/services/sms/outbox_worker.py:76 in process_pending_outbox'
  },
  {
    id: 'CAL-200',
    title: 'Timezone Offset Inconsistency on Daylight Savings Transition',
    severity: 'low',
    status: 'resolved',
    tenantId: 'tenant_zen_spa',
    category: 'Calendar / Schedule',
    route: 'GET /api/v1/schedules/slots',
    createdAt: '1 hour ago',
    errorContext: 'TimezoneDriftWarning: Local slot calculation UTC+10 vs AEST offset shifted availability boundary by 60 minutes for multi-day recurrence.',
    stackTrace: 'ScheduleDriftNotice: Slot boundary recalculated with zoneinfo("Australia/Sydney")\n  at app/services/scheduling/slots.py:145 in generate_available_slots'
  },
  {
    id: 'PAY-402',
    title: 'Idempotency Key Conflict in Payment Processor Intent',
    severity: 'med',
    status: 'in_progress',
    tenantId: 'tenant_apex_physio',
    category: 'Finance / Payments',
    route: 'POST /api/v1/finance/payments/intent',
    createdAt: '2 hours ago',
    errorContext: 'StripeIdempotencyConflict: Keys matched an in-flight capture attempt with modified metadata payload.',
    stackTrace: 'stripe.error.IdempotencyError: Keys for idempotent requests cannot be reused with differing parameters\n  at app/services/finance/processor.py:90 in create_payment_intent'
  }
]

export const TicketsWorkspace: React.FC<TicketsWorkspaceProps> = ({
  onLaunchInvestigation,
  className
}) => {
  const [tickets, setTickets] = useState<SupportTicket[]>(INITIAL_TICKETS)
  const [activeFilter, setActiveFilter] = useState<TicketStatus>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedTicketId, setExpandedTicketId] = useState<string | null>('ERR-503')
  const [investigatingTicketId, setInvestigatingTicketId] = useState<string | null>(null)
  const [notification, setNotification] = useState<string | null>(null)

  const filteredTickets = tickets.filter((ticket) => {
    const matchesFilter =
      activeFilter === 'all' ||
      (activeFilter === 'needs_auth' && ticket.status === 'needs_auth') ||
      (activeFilter === 'in_progress' && ticket.status === 'in_progress') ||
      (activeFilter === 'resolved' && ticket.status === 'resolved')

    const matchesSearch =
      searchQuery.trim() === '' ||
      ticket.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ticket.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ticket.errorContext.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (ticket.category && ticket.category.toLowerCase().includes(searchQuery.toLowerCase()))

    return matchesFilter && matchesSearch
  })

  const handleLaunch = (ticket: SupportTicket) => {
    setInvestigatingTicketId(ticket.id)
    setNotification(`Codex Autonomous Investigation launched for ticket ${ticket.id}`)

    // Update status to in_progress
    setTickets((prev) =>
      prev.map((t) => (t.id === ticket.id ? { ...t, status: 'in_progress' } : t))
    )

    if (onLaunchInvestigation) {
      onLaunchInvestigation(ticket)
    }

    setTimeout(() => {
      setInvestigatingTicketId(null)
      setTimeout(() => setNotification(null), 4000)
    }, 1200)
  }

  const getSeverityBadge = (severity: TicketSeverity) => {
    switch (severity) {
      case 'high':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
            <AlertCircle className="h-3 w-3 shrink-0" />
            <span>High Severity</span>
          </span>
        )
      case 'med':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
            <AlertTriangle className="h-3 w-3 shrink-0" />
            <span>Med Severity</span>
          </span>
        )
      case 'low':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-500/15 text-blue-400 border border-blue-500/30">
            <Info className="h-3 w-3 shrink-0" />
            <span>Low Severity</span>
          </span>
        )
    }
  }

  const getStatusBadge = (status: SupportTicket['status']) => {
    switch (status) {
      case 'needs_auth':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-purple-500/15 text-purple-300 border border-purple-500/30">
            <ShieldCheck className="h-3 w-3 text-purple-400" />
            <span>Needs Auth</span>
          </span>
        )
      case 'in_progress':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-blue-500/15 text-blue-300 border border-blue-500/30">
            <Clock className="h-3 w-3 text-blue-400 animate-spin" />
            <span>In Progress</span>
          </span>
        )
      case 'resolved':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="h-3 w-3 text-emerald-400" />
            <span>Resolved</span>
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-muted/60 text-muted-foreground border border-border/40">
            <span>Open</span>
          </span>
        )
    }
  }

  const countByFilter = {
    all: tickets.length,
    needs_auth: tickets.filter((t) => t.status === 'needs_auth').length,
    in_progress: tickets.filter((t) => t.status === 'in_progress').length,
    resolved: tickets.filter((t) => t.status === 'resolved').length
  }

  return (
    <div
      data-testid="tickets-workspace"
      className={cn('flex flex-col h-full w-full p-4 sm:p-6 space-y-4 max-w-6xl mx-auto', className)}
    >
      {/* Workspace Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-border/40">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-rose-500" />
            <h1 className="text-xl font-bold tracking-tight text-foreground">
              Support Tickets & Triage Queue
            </h1>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Realtime customer & operational defect intake with automated Codex diagnostic synthesis.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search errors or tickets..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-border/50 bg-background/60 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
        </div>
      </div>

      {/* Notification Banner */}
      {notification && (
        <div
          data-testid="ticket-notification"
          className="flex items-center justify-between p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs animate-in fade-in slide-in-from-top-2"
        >
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-emerald-400 animate-pulse" />
            <span>{notification}</span>
          </div>
          <button
            type="button"
            onClick={() => setNotification(null)}
            className="text-emerald-400/80 hover:text-emerald-300 font-mono text-[11px]"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Filter Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 select-none">
        {(
          [
            { id: 'all', label: 'All' },
            { id: 'needs_auth', label: 'Needs Auth' },
            { id: 'in_progress', label: 'In Progress' },
            { id: 'resolved', label: 'Resolved' }
          ] as const
        ).map((pill) => {
          const isActive = activeFilter === pill.id
          const count = countByFilter[pill.id]

          return (
            <button
              key={pill.id}
              type="button"
              data-testid={`filter-${pill.id}`}
              onClick={() => setActiveFilter(pill.id)}
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 border min-h-[36px]',
                isActive
                  ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                  : 'bg-card/60 text-muted-foreground hover:text-foreground border-border/40 hover:bg-card'
              )}
            >
              <span>{pill.label}</span>
              <span
                className={cn(
                  'text-[10px] font-mono px-1.5 py-0.2 rounded-full',
                  isActive ? 'bg-primary-foreground/20 text-primary-foreground' : 'bg-muted/80 text-muted-foreground'
                )}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>

      {/* Ticket List */}
      <div className="space-y-3 flex-1 overflow-y-auto pr-1">
        {filteredTickets.length === 0 ? (
          <div className="p-8 text-center rounded-xl border border-dashed border-border/50 bg-card/20 text-muted-foreground text-xs">
            No tickets matching filter criteria.
          </div>
        ) : (
          filteredTickets.map((ticket) => {
            const isExpanded = expandedTicketId === ticket.id
            const isLaunching = investigatingTicketId === ticket.id

            return (
              <div
                key={ticket.id}
                data-testid={`ticket-card-${ticket.id}`}
                className={cn(
                  'rounded-xl border transition-all duration-200 bg-card/60 hover:bg-card/90',
                  ticket.severity === 'high' ? 'border-rose-500/20 hover:border-rose-500/40' : 'border-border/40 hover:border-border/70',
                  isExpanded ? 'shadow-md ring-1 ring-border/50' : 'shadow-sm'
                )}
              >
                {/* Ticket Top Summary */}
                <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="space-y-1.5 min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-primary tracking-wider">
                        {ticket.id}
                      </span>
                      {getSeverityBadge(ticket.severity)}
                      {getStatusBadge(ticket.status)}
                      {ticket.category && (
                        <span className="text-[11px] font-mono text-muted-foreground px-2 py-0.5 rounded bg-muted/50 border border-border/30">
                          {ticket.category}
                        </span>
                      )}
                      <span className="text-[11px] text-muted-foreground font-mono ml-auto sm:ml-0">
                        {ticket.createdAt}
                      </span>
                    </div>

                    <h2 className="text-sm sm:text-base font-semibold text-foreground tracking-tight">
                      {ticket.title}
                    </h2>

                    {ticket.route && (
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
                        <span className="text-[11px] text-primary/80">Route:</span>
                        <span className="bg-background/80 px-1.5 py-0.5 rounded border border-border/40 text-[11px]">
                          {ticket.route}
                        </span>
                        {ticket.tenantId && (
                          <span className="text-muted-foreground/60 text-[10px]">
                            • {ticket.tenantId}
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Actions Column */}
                  <div className="flex items-center gap-2 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-border/20">
                    <button
                      type="button"
                      data-testid={`launch-investigation-${ticket.id}`}
                      disabled={isLaunching || ticket.status === 'resolved'}
                      onClick={() => handleLaunch(ticket)}
                      className={cn(
                        'inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-all min-h-[38px] shadow-sm',
                        ticket.status === 'resolved'
                          ? 'bg-muted/40 text-muted-foreground cursor-not-allowed border border-border/20'
                          : 'bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] text-white border border-emerald-500/40'
                      )}
                    >
                      <Zap className={cn('h-3.5 w-3.5', isLaunching ? 'animate-spin' : 'animate-pulse')} />
                      <span>{isLaunching ? 'Synthesizing...' : 'Launch Codex Investigation'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setExpandedTicketId(isExpanded ? null : ticket.id)}
                      title={isExpanded ? 'Collapse error context' : 'Expand error context'}
                      className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/30 transition-colors min-h-[38px] min-w-[38px] flex items-center justify-center"
                    >
                      <ChevronRight
                        className={cn('h-4 w-4 transition-transform duration-200', isExpanded && 'rotate-90')}
                      />
                    </button>
                  </div>
                </div>

                {/* Error Context Preview (Visible always or expanded for full stack) */}
                <div className="px-4 sm:px-5 pb-4 pt-0">
                  <div className="rounded-lg border border-border/40 bg-zinc-950 p-3 space-y-2">
                    <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 border-b border-zinc-800/80 pb-1.5">
                      <div className="flex items-center gap-1.5 text-rose-400">
                        <Code2 className="h-3.5 w-3.5" />
                        <span>Error Context & Diagnostic Capture</span>
                      </div>
                      <span className="text-[10px] text-zinc-500">FastAPI Bookings Sentinel</span>
                    </div>

                    <p className="text-xs font-mono text-zinc-200 leading-relaxed break-words">
                      {ticket.errorContext}
                    </p>

                    {isExpanded && ticket.stackTrace && (
                      <div className="pt-2 mt-2 border-t border-zinc-800/80 space-y-1">
                        <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                          Captured Stack Trace:
                        </span>
                        <pre className="text-[11px] font-mono text-rose-300/90 whitespace-pre-wrap overflow-x-auto leading-tight bg-zinc-900/60 p-2.5 rounded border border-zinc-800/60">
                          {ticket.stackTrace}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

export default TicketsWorkspace
