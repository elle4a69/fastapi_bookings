import { type FormEvent, useEffect, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  History,
  LoaderCircle,
  ShieldAlert,
  Tag,
  Ticket,
  TicketPlus,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { apiClient } from '@/lib/api'

export type SupportTicket = {
  id: number
  conversation_id: number | null
  category: string
  severity: string
  status: string
  title: string
  description: string
  observed_behaviour?: string | null
  affected_product_area?: string | null
  user_impact?: string | null
  acceptance_criteria?: string | null
  authorisation_state?: string
  requires_owner_approval?: boolean
  resolution_summary?: string | null
  coding_task_id?: string | null
  created_at: string
  updated_at: string
}

export type SupportTicketEvent = {
  id: number
  event_type: string
  safe_metadata: Record<string, unknown>
  created_at: string
}

export type TicketCreateResponse = {
  ticket: SupportTicket
  duplicate_ticket: boolean
  confirmation_token?: string | null
}

function requestKey(): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `ticket-${Date.now()}-${Math.random().toString(36).slice(2)}`
  )
}

function formatStatus(status: string): string {
  return status.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function statusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'completed':
    case 'resolved':
      return 'default'
    case 'awaiting_engineering':
    case 'in_progress':
      return 'secondary'
    case 'cancelled':
    case 'rejected':
      return 'outline'
    default:
      return 'outline'
  }
}

function severityVariant(severity: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (severity) {
    case 'critical':
      return 'destructive'
    case 'high':
      return 'destructive'
    case 'normal':
      return 'secondary'
    case 'low':
    default:
      return 'outline'
  }
}

export function TicketStatusCard({
  ticket,
  onRefresh: _onRefresh,
}: {
  ticket: SupportTicket
  onRefresh?: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [events, setEvents] = useState<SupportTicketEvent[]>([])
  const [loadingEvents, setLoadingEvents] = useState(false)
  const [eventsError, setEventsError] = useState<string | null>(null)

  const toggleEvents = async () => {
    if (!expanded && events.length === 0) {
      setLoadingEvents(true)
      setEventsError(null)
      try {
        const items = await apiClient.get<SupportTicketEvent[]>(
          `/api/admin/business-assistant/tickets/${ticket.id}/events`,
        )
        setEvents(items)
      } catch (err) {
        setEventsError(err instanceof Error ? err.message : 'Unable to load event timeline.')
      } finally {
        setLoadingEvents(false)
      }
    }
    setExpanded(!expanded)
  }

  return (
    <article
      className="flex flex-col gap-3 rounded-lg border bg-card p-4 shadow-xs"
      data-testid={`ticket-card-${ticket.id}`}
      aria-labelledby={`ticket-title-${ticket.id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Ticket className="h-4 w-4 text-primary" aria-hidden="true" />
          <span className="font-mono text-xs text-muted-foreground">#{ticket.id}</span>
          <Badge variant={statusVariant(ticket.status)} className="capitalize">
            {formatStatus(ticket.status)}
          </Badge>
          <Badge variant={severityVariant(ticket.severity)} className="capitalize">
            {ticket.severity} severity
          </Badge>
          <Badge variant="outline" className="capitalize">
            <Tag className="mr-1 h-3 w-3" aria-hidden="true" />
            {ticket.category}
          </Badge>
          {ticket.requires_owner_approval && (
            <Badge variant="destructive" className="gap-1">
              <ShieldAlert className="h-3 w-3" aria-hidden="true" />
              Owner Approval Required
            </Badge>
          )}
        </div>
        <time className="text-xs text-muted-foreground" dateTime={ticket.created_at}>
          {new Date(ticket.created_at).toLocaleString()}
        </time>
      </div>

      <div>
        <h3 id={`ticket-title-${ticket.id}`} className="text-base font-semibold text-foreground">
          {ticket.title}
        </h3>
        <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
          {ticket.description}
        </p>
      </div>

      {ticket.resolution_summary && (
        <div className="rounded-md border border-primary/20 bg-primary/5 p-3 text-xs text-foreground">
          <div className="flex items-center gap-1.5 font-semibold text-primary">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
            Resolution Summary
          </div>
          <p className="mt-1 text-muted-foreground">{ticket.resolution_summary}</p>
        </div>
      )}

      <div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 px-2 text-xs text-muted-foreground hover:text-foreground"
          onClick={toggleEvents}
          aria-expanded={expanded}
          aria-controls={`ticket-events-${ticket.id}`}
        >
          {expanded ? (
            <ChevronDown className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <ChevronRight className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
          )}
          <History className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
          Event timeline {events.length > 0 ? `(${events.length})` : ''}
        </Button>

        {expanded && (
          <div
            id={`ticket-events-${ticket.id}`}
            className="mt-3 border-l-2 border-muted pl-4 space-y-3"
            role="region"
            aria-label="Ticket event timeline"
          >
            {loadingEvents ? (
              <div className="flex items-center gap-2 py-2 text-xs text-muted-foreground">
                <LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                Loading timeline…
              </div>
            ) : eventsError ? (
              <p className="py-1 text-xs text-destructive">{eventsError}</p>
            ) : events.length === 0 ? (
              <p className="py-1 text-xs text-muted-foreground">No events recorded yet.</p>
            ) : (
              events.map((event) => (
                <div key={event.id} className="relative pb-1">
                  <div className="flex items-center gap-2 text-xs">
                    <Clock className="h-3 w-3 text-muted-foreground" aria-hidden="true" />
                    <span className="font-semibold text-foreground">
                      {formatStatus(event.event_type)}
                    </span>
                    <time className="text-muted-foreground" dateTime={event.created_at}>
                      {new Date(event.created_at).toLocaleTimeString()}
                    </time>
                  </div>
                  {event.safe_metadata && Object.keys(event.safe_metadata).length > 0 && (
                    <div className="mt-1 rounded bg-muted/50 p-2 font-mono text-[11px] text-muted-foreground">
                      {JSON.stringify(event.safe_metadata, null, 2)}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </article>
  )
}

export function TicketStatusSection({
  conversationId = null,
  initialTickets = [],
  onTicketCreated,
}: {
  conversationId?: number | null
  initialTickets?: SupportTicket[]
  onTicketCreated?: (ticket: SupportTicket) => void
}) {
  const [tickets, setTickets] = useState<SupportTicket[]>(initialTickets)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  // Form inputs
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('support')
  const [severity, setSeverity] = useState('normal')
  const [creating, setCreating] = useState(false)
  const [formFeedback, setFormFeedback] = useState<string | null>(null)

  const loadTickets = async () => {
    setLoading(true)
    setError(null)
    try {
      const items = await apiClient.get<SupportTicket[]>('/api/admin/business-assistant/tickets')
      setTickets(items)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load tickets.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (initialTickets.length > 0) {
      setTickets(initialTickets)
    } else {
      void loadTickets()
    }
  }, [initialTickets])

  const submitTicket = async (event: FormEvent) => {
    event.preventDefault()
    const cleanTitle = title.trim()
    const cleanDesc = description.trim()
    if (!cleanTitle || !cleanDesc || creating) return

    setCreating(true)
    setFormFeedback(null)
    setError(null)
    try {
      const res = await apiClient.post<TicketCreateResponse>(
        '/api/admin/business-assistant/tickets',
        {
          conversation_id: conversationId,
          category,
          severity,
          title: cleanTitle,
          description: cleanDesc,
          request_key: requestKey(),
        },
      )
      setTickets((current) => [
        res.ticket,
        ...current.filter((item) => item.id !== res.ticket.id),
      ])
      setTitle('')
      setDescription('')
      setShowForm(false)
      if (res.duplicate_ticket) {
        setFormFeedback(
          'An active ticket already covers this summary. Its existing record is displayed.',
        )
      }
      onTicketCreated?.(res.ticket)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create ticket.')
    } finally {
      setCreating(false)
    }
  }

  return (
    <section
      className="flex flex-col gap-4 rounded-lg border bg-card p-4 sm:p-5"
      aria-labelledby="support-ticket-heading"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b pb-4">
        <div>
          <div className="flex items-center gap-2 text-primary">
            <TicketPlus className="h-5 w-5" aria-hidden="true" />
            <h2 id="support-ticket-heading" className="text-base font-semibold">
              Support tickets
            </h2>
          </div>
          <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
            Submit a sanitised summary. Tickets remain awaiting engineering review; they do not trigger work automatically.
          </p>
        </div>
        <Button
          type="button"
          variant={showForm ? 'secondary' : 'default'}
          size="sm"
          onClick={() => setShowForm(!showForm)}
          aria-expanded={showForm}
          aria-controls="create-ticket-form"
        >
          <TicketPlus className="mr-1.5 h-4 w-4" aria-hidden="true" />
          {showForm ? 'Cancel ticket' : 'Create ticket'}
        </Button>
      </div>

      {formFeedback && (
        <div
          className="flex items-center gap-2 rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-xs text-primary"
          role="status"
        >
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{formFeedback}</span>
        </div>
      )}

      {error && (
        <div
          className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive"
          role="alert"
        >
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {showForm && (
        <form
          id="create-ticket-form"
          className="flex flex-col gap-3 rounded-lg border border-dashed p-4"
          onSubmit={(e) => void submitTicket(e)}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-xs font-medium">
              Category
              <select
                className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-xs"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={creating}
              >
                <option value="support">Support</option>
                <option value="bug">Bug</option>
                <option value="feature">Feature</option>
                <option value="access">Access</option>
                <option value="security">Security</option>
                <option value="upgrade">Upgrade</option>
              </select>
            </label>
            <label className="text-xs font-medium">
              Severity
              <select
                className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-xs"
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
                disabled={creating}
              >
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </label>
          </div>

          <label className="block text-xs font-medium">
            Summary
            <input
              className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-xs"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Concise overview of the issue"
              maxLength={240}
              disabled={creating}
              required
            />
          </label>

          <label className="block text-xs font-medium">
            Sanitised details
            <Textarea
              className="mt-1 text-xs"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what occurred. Do not include customer passwords, API secrets, or sensitive customer PII."
              maxLength={20_000}
              rows={4}
              disabled={creating}
              required
            />
          </label>

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={creating}
              onClick={() => setShowForm(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={!title.trim() || !description.trim() || creating}
            >
              {creating && <LoaderCircle className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
              Submit ticket
            </Button>
          </div>
        </form>
      )}

      <div className="flex flex-col gap-3" aria-label="Support tickets list">
        {loading ? (
          <div className="flex items-center gap-2 p-4 text-xs text-muted-foreground">
            <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
            Loading tickets…
          </div>
        ) : tickets.length === 0 ? (
          <p className="p-4 text-xs text-muted-foreground">
            No support tickets recorded for this tenant yet.
          </p>
        ) : (
          tickets.map((ticket) => (
            <TicketStatusCard key={ticket.id} ticket={ticket} onRefresh={loadTickets} />
          ))
        )}
      </div>
    </section>
  )
}
