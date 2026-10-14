import { type FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity,
  Bot,
  ExternalLink,
  History,
  LoaderCircle,
  Menu,
  MessageCircle,
  MessageCirclePlus,
  Mic,
  RotateCcw,
  Settings,
  Sparkles,
  Terminal,
  TicketPlus,
  Volume2,
  X,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { apiClient } from '@/lib/api'

import {
  AssistantSettingsDialog,
  DiagnosticModeToggle,
  LiveAgentActivityConsole,
} from './components'
import {
  useBusinessAssistant,
  type Conversation,
} from './business-assistant-context'
import {
  type SupportTicket,
  type TicketCreateResponse,
} from './ticket-status'

type OnboardingResponse = {
  progress: {
    status: 'not_started' | 'in_progress' | 'completed'
    completed_steps: string[]
    updated_at: string | null
  }
  product_context: {
    availability: string
    enabled_modules: string[]
    setup_counts?: {
      active_services: number
      active_providers: number
      active_locations: number
    } | null
  }
}

function requestKey(): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `turn-${Date.now()}-${Math.random().toString(36).slice(2)}`
  )
}

export default function BusinessAssistantPage() {
  const {
    conversations,
    activeConversationId,
    selectConversation,
    createConversation,
    messages,
    loading,
    error,
    setError,
    turnError,
    sendTurn,
    transport,
    voiceState,
  } = useBusinessAssistant()

  const navigate = useNavigate()
  const [tickets, setTickets] = useState<SupportTicket[]>([])
  const [ticketTitle, setTicketTitle] = useState('')
  const [ticketDescription, setTicketDescription] = useState('')
  const [ticketCategory, setTicketCategory] = useState('support')
  const [ticketSeverity, setTicketSeverity] = useState('normal')
  const [creatingTicket, setCreatingTicket] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [showActivityConsole, setShowActivityConsole] = useState(false)
  const [viewingConversation, setViewingConversation] = useState<Conversation | null>(null)
  const [onboarding, setOnboarding] = useState<OnboardingResponse | null>(null)

  const loadTickets = async () => {
    try {
      const items = await apiClient.get<SupportTicket[]>('/api/admin/business-assistant/tickets')
      setTickets(items)
    } catch {
      // Non-blocking ticket load failure
    }
  }

  const loadOnboarding = async () => {
    try {
      const data = await apiClient.get<OnboardingResponse>(
        '/api/admin/business-assistant/onboarding',
      )
      setOnboarding(data)
    } catch {
      // Non-blocking onboarding load failure
    }
  }

  useEffect(() => {
    void loadTickets()
    void loadOnboarding()
  }, [])

  const submitTicket = async (event: FormEvent) => {
    event.preventDefault()
    const title = ticketTitle.trim()
    const description = ticketDescription.trim()
    if (!title || !description || creatingTicket) return

    setCreatingTicket(true)
    setError(null)
    try {
      const result = await apiClient.post<TicketCreateResponse>(
        '/api/admin/business-assistant/tickets',
        {
          conversation_id: activeConversationId,
          category: ticketCategory,
          severity: ticketSeverity,
          title,
          description,
          request_key: requestKey(),
        },
      )
      setTickets((current) => [
        result.ticket,
        ...current.filter((ticket) => ticket.id !== result.ticket.id),
      ])
      setTicketTitle('')
      setTicketDescription('')
      if (result.duplicate_ticket) {
        setError('An active ticket already covers that summary. Its existing record is shown below.')
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to create a support ticket.')
    } finally {
      setCreatingTicket(false)
    }
  }

  const handleOpenConversationTranscript = async (conversation: Conversation) => {
    setViewingConversation(conversation)
    await selectConversation(conversation.id)
  }

  const getVoiceEngineLabel = () => {
    switch (transport) {
      case 'xai_grok_voice':
        return 'xAI Grok Voice (grok-voice-think-fast-2.0)'
      case 'direct_gpt_live':
      default:
        return 'Direct GPT-Live (gpt-live-1 WebRTC)'
    }
  }

  return (
    <section className="mx-auto flex w-full max-w-6xl flex-col gap-5 pb-8">
      <header className="flex flex-col gap-3 border-b pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-primary">
            <Bot className="h-5 w-5" aria-hidden="true" />
            <p className="text-sm font-semibold">Business Assistant</p>
          </div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Administrative Operations</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage voice transports, inspect historical transcripts, and supervise assistant activity.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => navigate('/admin/telemetry')}
            data-testid="nav-telemetry-console-button"
            className="gap-1.5"
          >
            <Activity className="h-4 w-4 text-emerald-500" aria-hidden="true" />
            <span>Agent Telemetry</span>
            <ExternalLink className="h-3.5 w-3.5 opacity-70" aria-hidden="true" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowActivityConsole((prev) => !prev)}
            data-testid="toggle-live-console-button"
            className="gap-1.5"
          >
            <Terminal className="h-4 w-4 text-primary" aria-hidden="true" />
            <span>{showActivityConsole ? 'Hide Live Console' : 'Show Live Console'}</span>
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setSettingsOpen(true)}
            data-testid="business-assistant-settings-button"
          >
            <Settings className="h-4 w-4 mr-2" aria-hidden="true" />
            Assistant Settings
          </Button>
          <Button
            type="button"
            variant="outline"
            className="hidden sm:inline-flex"
            onClick={() => setHistoryOpen(true)}
            aria-expanded={historyOpen}
            aria-controls="business-assistant-history"
            data-testid="business-assistant-history-open"
          >
            <History className="mr-2 h-4 w-4" aria-hidden="true" />
            History
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="sm:hidden"
            onClick={() => setHistoryOpen(true)}
            aria-label="Open conversation history"
            aria-expanded={historyOpen}
            aria-controls="business-assistant-history"
            data-testid="business-assistant-history-menu"
          >
            <Menu className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            type="button"
            onClick={async () => {
              await createConversation()
              setHistoryOpen(false)
            }}
          >
            <MessageCirclePlus className="mr-2 h-4 w-4" aria-hidden="true" />
            New conversation
          </Button>
        </div>
      </header>

      {/* System & Transport Status Card */}
      <section
        className="rounded-xl border bg-card p-4 sm:p-5 shadow-xs"
        aria-label="System & Transport Status"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3">
          <div className="flex items-center gap-2">
            <Volume2 className="h-5 w-5 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold text-foreground">Voice Engine &amp; System Status</h2>
          </div>
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className="bg-primary/10 text-primary border-primary/20 px-2.5 py-0.5 font-mono text-xs"
              data-testid="active-voice-engine-badge"
            >
              {getVoiceEngineLabel()}
            </Badge>
            <Badge
              variant="secondary"
              className={`capitalize text-xs ${
                voiceState === 'live'
                  ? 'bg-emerald-500/15 text-emerald-600 border border-emerald-500/30'
                  : voiceState === 'connecting'
                    ? 'bg-amber-500/15 text-amber-600 border border-amber-500/30'
                    : 'text-muted-foreground'
              }`}
            >
              Voice: {voiceState}
            </Badge>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4 items-center">
          <div className="space-y-1">
            <p className="text-xs font-medium text-foreground">Diagnostic Telemetry Mode</p>
            <p className="text-[11px] text-muted-foreground">
              Captures WebRTC states and tool calls for live inspection.
            </p>
            <div className="pt-1">
              <DiagnosticModeToggle />
            </div>
          </div>

          <div className="space-y-1">
            <p className="text-xs font-medium text-foreground">Live Telemetry Console</p>
            <p className="text-[11px] text-muted-foreground">
              Monitor real-time events, transcript tokens, and tool actions.
            </p>
            <div className="pt-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/admin/telemetry')}
                className="gap-1.5 text-xs h-8"
              >
                <Activity className="h-3.5 w-3.5 text-emerald-500" />
                Open Telemetry Console
              </Button>
            </div>
          </div>

          <div className="space-y-1">
            <p className="text-xs font-medium text-foreground">Transport &amp; Engine Settings</p>
            <p className="text-[11px] text-muted-foreground">
              Switch between xAI Grok Voice and Direct OpenAI GPT-Live.
            </p>
            <div className="pt-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSettingsOpen(true)}
                className="gap-1.5 text-xs h-8"
              >
                <Settings className="h-3.5 w-3.5 text-primary" />
                Configure Engines
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Live Agent Activity Console if toggled */}
      {showActivityConsole && (
        <section
          className="rounded-xl border bg-card p-4 sm:p-5 shadow-xs"
          aria-label="Live Agent Activity Console"
        >
          <div className="flex items-center justify-between pb-3 border-b mb-3">
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="text-sm font-semibold">Live Agent Activity &amp; WebRTC Console</h2>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowActivityConsole(false)}
              className="h-7 text-xs"
            >
              Close
            </Button>
          </div>
          <LiveAgentActivityConsole />
        </section>
      )}

      {/* Onboarding milestone banner if available */}
      {onboarding && (
        <section
          className="rounded-lg border bg-muted/20 p-3 sm:p-4 shadow-xs"
          aria-label="Onboarding status"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="text-xs sm:text-sm font-semibold">Tenant Setup Milestones</h2>
              <Badge variant="outline" className="capitalize text-[11px]">
                {onboarding.progress.status.replaceAll('_', ' ')}
              </Badge>
            </div>
          </div>
        </section>
      )}

      {historyOpen && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 cursor-default bg-background/60 backdrop-blur-[1px]"
            aria-label="Close conversation history"
            onClick={() => setHistoryOpen(false)}
          />
          <aside
            id="business-assistant-history"
            className="fixed inset-y-0 right-0 z-50 flex w-[min(22rem,calc(100vw-1rem))] flex-col border-l bg-card p-3 shadow-xl"
            aria-label="Conversation history"
            aria-modal="true"
            role="dialog"
          >
            <div className="flex items-center justify-between gap-3 border-b pb-3">
              <div>
                <h2 className="text-base font-semibold">Conversation history</h2>
                <p className="mt-1 text-sm text-muted-foreground">Choose a saved conversation.</p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => setHistoryOpen(false)}
                aria-label="Close history"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto pt-3" id="business-assistant-history-list">
              {loading ? (
                <div className="flex items-center gap-2 p-3 text-sm text-muted-foreground">
                  <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading
                </div>
              ) : conversations.length === 0 ? (
                <p className="p-3 text-sm text-muted-foreground">Start a conversation to begin.</p>
              ) : (
                <div className="flex flex-col gap-1">
                  {conversations.map((conversation) => (
                    <Button
                      key={conversation.id}
                      type="button"
                      variant={conversation.id === activeConversationId ? 'secondary' : 'ghost'}
                      className="h-auto justify-start px-3 py-2 text-left"
                      onClick={() => {
                        void handleOpenConversationTranscript(conversation)
                        setHistoryOpen(false)
                      }}
                    >
                      <span className="line-clamp-2 text-sm">
                        {conversation.title || `Conversation #${conversation.id}`}
                      </span>
                    </Button>
                  ))}
                </div>
              )}
            </div>
          </aside>
        </>
      )}

      {error && (
        <div
          className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
          role="alert"
        >
          {error}
        </div>
      )}

      {turnError && (
        <div
          className="flex flex-col gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
          role="alert"
        >
          <p>
            <span className="font-semibold">{turnError.code}</span>: {turnError.message}
          </p>
          {turnError.requestId && (
            <p className="font-mono text-xs">Request ID: {turnError.requestId}</p>
          )}
          {turnError.retryable && (
            <div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void sendTurn()}
              >
                <RotateCcw className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                Retry message
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Recent Conversations Table (Clean Admin Archive) */}
      <section
        className="flex min-w-0 flex-col rounded-xl border bg-card shadow-xs"
        aria-label="Conversation"
      >
        <div className="flex items-center justify-between border-b px-5 py-3.5">
          <div className="flex items-center gap-2">
            <MessageCircle className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold text-foreground">Recent Conversations &amp; Transcripts</h2>
          </div>
          <Badge variant="outline" className="text-xs">
            {conversations.length} {conversations.length === 1 ? 'Record' : 'Records'}
          </Badge>
        </div>

        <div className="overflow-x-auto">
          {conversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-center text-sm text-muted-foreground">
              <Bot className="h-8 w-8 text-muted-foreground/40 mb-2" />
              <p>No conversation history found.</p>
              <p className="text-xs text-muted-foreground/70 mt-1">
                Interact with the floating Business Assistant widget to start your first session.
              </p>
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="border-b bg-muted/40 font-medium text-muted-foreground">
                <tr>
                  <th className="py-2.5 px-4 w-16">ID</th>
                  <th className="py-2.5 px-4">Title / Summary</th>
                  <th className="py-2.5 px-4 w-32">Status</th>
                  <th className="py-2.5 px-4 w-44">Last Updated</th>
                  <th className="py-2.5 px-4 w-32 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {conversations.map((conv) => (
                  <tr
                    key={conv.id}
                    className="hover:bg-muted/30 transition-colors cursor-pointer"
                    onClick={() => void handleOpenConversationTranscript(conv)}
                  >
                    <td className="py-3 px-4 font-mono text-muted-foreground">#{conv.id}</td>
                    <td className="py-3 px-4 font-medium text-foreground">
                      <div className="flex items-center gap-2">
                        <span>{conv.title || `Conversation #${conv.id}`}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant="outline" className="capitalize text-[10px]">
                        {conv.status || 'active'}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-muted-foreground font-mono text-[11px]">
                      {new Date(conv.updated_at || conv.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="xs"
                        onClick={(e) => {
                          e.stopPropagation()
                          void handleOpenConversationTranscript(conv)
                        }}
                        className="text-primary hover:text-primary hover:bg-primary/10"
                      >
                        Review
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* Read-Only Historical Transcript Dialog */}
      <Dialog
        open={Boolean(viewingConversation)}
        onOpenChange={(open) => {
          if (!open) setViewingConversation(null)
        }}
      >
        <DialogContent className="max-h-[85vh] sm:max-w-2xl flex flex-col">
          <DialogHeader className="border-b pb-3">
            <div className="flex items-center justify-between pr-6">
              <div className="flex items-center gap-2">
                <Bot className="h-5 w-5 text-primary" />
                <DialogTitle className="text-base font-semibold">
                  {viewingConversation?.title || `Conversation #${viewingConversation?.id}`}
                </DialogTitle>
              </div>
              <Badge variant="outline" className="text-[10px] font-mono">
                ID: {viewingConversation?.id}
              </Badge>
            </div>
            <DialogDescription className="text-xs text-muted-foreground">
              Read-only transcript archive. Live voice and text actions run through the floating assistant.
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-[55vh]">
            {loading ? (
              <div className="flex items-center justify-center p-8 gap-2 text-xs text-muted-foreground">
                <LoaderCircle className="h-4 w-4 animate-spin text-primary" />
                Loading messages…
              </div>
            ) : messages.length === 0 ? (
              <div className="text-center p-8 text-xs text-muted-foreground">
                No archived messages found for this conversation.
              </div>
            ) : (
              messages.map((message) => {
                const isUser = message.role === 'user'
                return (
                  <article
                    key={message.id}
                    className={`max-w-[85%] rounded-lg p-3 text-xs ${
                      isUser
                        ? 'ml-auto bg-primary text-primary-foreground'
                        : 'mr-auto bg-muted text-foreground border border-border/60'
                    }`}
                  >
                    <div className="mb-1 flex items-center justify-between gap-2 text-[10px] opacity-75 font-medium">
                      <span>{isUser ? 'You' : 'Business Assistant'}</span>
                      {message.channel === 'realtime_voice' && (
                        <span className="flex items-center gap-0.5">
                          <Mic className="h-3 w-3" /> Voice
                        </span>
                      )}
                    </div>
                    <p className="whitespace-pre-wrap break-words leading-relaxed">
                      {message.content}
                    </p>
                    <div className="mt-1 text-[9px] opacity-50 text-right">
                      {new Date(message.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </div>
                  </article>
                )
              })
            )}
          </div>

          <div className="border-t pt-3 flex justify-end">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setViewingConversation(null)}
            >
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Support Tickets Section */}
      <section
        className="grid gap-4 rounded-lg border bg-card p-4 lg:grid-cols-[minmax(0,1fr)_20rem]"
        aria-labelledby="support-ticket-heading"
      >
        <div>
          <div className="flex items-center gap-2 text-primary">
            <TicketPlus className="h-5 w-5" aria-hidden="true" />
            <h2 id="support-ticket-heading" className="text-base font-semibold">
              Support tickets
            </h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Submit a sanitised summary. Tickets remain awaiting engineering review; they do not trigger work automatically.
          </p>
          <form className="mt-4 space-y-3" onSubmit={(event) => void submitTicket(event)}>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm font-medium">
                Category
                <select
                  className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm"
                  value={ticketCategory}
                  onChange={(event) => setTicketCategory(event.target.value)}
                  disabled={creatingTicket}
                >
                  <option value="support">Support</option>
                  <option value="bug">Bug</option>
                  <option value="feature">Feature</option>
                  <option value="access">Access</option>
                  <option value="security">Security</option>
                  <option value="upgrade">Upgrade</option>
                </select>
              </label>
              <label className="text-sm font-medium">
                Severity
                <select
                  className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm"
                  value={ticketSeverity}
                  onChange={(event) => setTicketSeverity(event.target.value)}
                  disabled={creatingTicket}
                >
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </label>
            </div>
            <label className="block text-sm font-medium">
              Summary
              <input
                className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm"
                value={ticketTitle}
                onChange={(event) => setTicketTitle(event.target.value)}
                maxLength={240}
                disabled={creatingTicket}
                required
              />
            </label>
            <label className="block text-sm font-medium">
              Sanitised details
              <Textarea
                className="mt-1"
                value={ticketDescription}
                onChange={(event) => setTicketDescription(event.target.value)}
                maxLength={20_000}
                rows={4}
                disabled={creatingTicket}
                required
              />
            </label>
            <Button
              type="submit"
              disabled={!ticketTitle.trim() || !ticketDescription.trim() || creatingTicket}
            >
              {creatingTicket && (
                <LoaderCircle className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              Create ticket
            </Button>
          </form>
        </div>
        <div aria-label="Your support tickets">
          <h3 className="text-sm font-semibold">Your tickets</h3>
          {tickets.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">No support tickets yet.</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {tickets.map((ticket) => (
                <li key={ticket.id} className="rounded-md border p-3 text-sm">
                  <p className="font-medium">{ticket.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {ticket.category} · {ticket.severity} · {ticket.status.replaceAll('_', ' ')}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <AssistantSettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
      />
    </section>
  )
}
