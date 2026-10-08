import { type FormEvent, useEffect, useRef, useState } from 'react'
import {
  Bot,
  CheckCircle2,
  History,
  LoaderCircle,
  Menu,
  MessageCirclePlus,
  Mic,
  PhoneOff,
  RotateCcw,
  Send,
  Sparkles,
  TicketPlus,
  Volume2,
  X,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  apiClient,
  toUserFacingApiError,
  type UserFacingApiError,
} from '@/lib/api'

import {
  useGPTLive,
} from '../gpt-live/use-gpt-live'
import { GPTLiveCaptionTimeline } from '../gpt-live/caption-timeline'
import { type GPTLiveCaption } from '../gpt-live/protocol'
import {
  type SupportTicket,
  type TicketCreateResponse,
} from './ticket-status'

type Conversation = {
  id: number
  title: string | null
  status: string
  created_at: string
  updated_at: string
}

type ConversationMessage = {
  id: number
  conversation_id: number
  role: 'user' | 'business_assistant' | 'system'
  content: string
  in_reply_to_message_id: number | null
  created_at: string
  channel?: 'text' | 'realtime_voice'
}

type TextTurnResponse = {
  user_message: ConversationMessage
  assistant_message: ConversationMessage
  duplicate_request: boolean
}

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
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [draft, setDraft] = useState('')
  const [pendingRequestKey, setPendingRequestKey] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [turnError, setTurnError] = useState<UserFacingApiError | null>(null)
  const [tickets, setTickets] = useState<SupportTicket[]>([])
  const [ticketTitle, setTicketTitle] = useState('')
  const [ticketDescription, setTicketDescription] = useState('')
  const [ticketCategory, setTicketCategory] = useState('support')
  const [ticketSeverity, setTicketSeverity] = useState('normal')
  const [creatingTicket, setCreatingTicket] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [onboarding, setOnboarding] = useState<OnboardingResponse | null>(null)
  const [voiceCaptions, setVoiceCaptions] = useState<GPTLiveCaption[]>([])

  const { voiceState, startVoice, stopVoice } = useGPTLive({
    conversationId: activeConversationId,
    onCaptionsChange: setVoiceCaptions,
    onError: setError,
  })

  const stopVoiceRef = useRef(stopVoice)
  const previousConversationIdRef = useRef<number | null>(activeConversationId)

  useEffect(() => {
    stopVoiceRef.current = stopVoice
  }, [stopVoice])

  useEffect(() => {
    if (previousConversationIdRef.current !== activeConversationId) {
      stopVoiceRef.current()
      previousConversationIdRef.current = activeConversationId
    }
  }, [activeConversationId])

  const loadMessages = async (conversationId: number) => {
    const history = await apiClient.get<ConversationMessage[]>(
      `/api/admin/business-assistant/conversations/${conversationId}/messages`,
    )
    setMessages(history)
  }

  const loadConversations = async () => {
    setLoading(true)
    try {
      const items = await apiClient.get<Conversation[]>(
        '/api/admin/business-assistant/conversations',
      )
      setConversations(items)
      if (items.length > 0) {
        const nextId =
          activeConversationId && items.some((item) => item.id === activeConversationId)
            ? activeConversationId
            : items[0].id
        setActiveConversationId(nextId)
        await loadMessages(nextId)
      } else {
        setActiveConversationId(null)
        setMessages([])
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load conversations.')
    } finally {
      setLoading(false)
    }
  }

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
    let active = true
    const loadInitialConversations = async () => {
      setLoading(true)
      try {
        const items = await apiClient.get<Conversation[]>(
          '/api/admin/business-assistant/conversations',
        )
        if (!active) return
        setConversations(items)
        if (items.length > 0) {
          setActiveConversationId(items[0].id)
          const history = await apiClient.get<ConversationMessage[]>(
            `/api/admin/business-assistant/conversations/${items[0].id}/messages`,
          )
          if (active) setMessages(history)
        }
        await loadTickets()
        await loadOnboarding()
      } catch (caught) {
        if (active) {
          setError(caught instanceof Error ? caught.message : 'Unable to load conversations.')
        }
      } finally {
        if (active) setLoading(false)
      }
    }
    void loadInitialConversations()
    return () => {
      active = false
    }
  }, [])

  const createConversation = async () => {
    setError(null)
    try {
      const conversation = await apiClient.post<Conversation>(
        '/api/admin/business-assistant/conversations',
        {
          request_key: requestKey(),
        },
      )
      setConversations((current) => [conversation, ...current])
      setActiveConversationId(conversation.id)
      setMessages([])
      setHistoryOpen(false)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to create a conversation.')
    }
  }

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

  const selectConversation = async (conversationId: number) => {
    setError(null)
    setActiveConversationId(conversationId)
    setHistoryOpen(false)
    try {
      await loadMessages(conversationId)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load conversation history.')
    }
  }

  const sendTurn = async () => {
    const content = draft.trim()
    if (!activeConversationId || !content || sending) return

    const nextRequestKey = pendingRequestKey ?? requestKey()
    setPendingRequestKey(nextRequestKey)
    setSending(true)
    setTurnError(null)
    try {
      const result = await apiClient.post<TextTurnResponse>(
        `/api/admin/business-assistant/conversations/${activeConversationId}/messages`,
        { content, request_key: nextRequestKey },
      )
      setMessages((current) => {
        const withoutCurrent = current.filter((message) => message.id !== result.user_message.id)
        return [...withoutCurrent, result.user_message, result.assistant_message]
      })
      setDraft('')
      setPendingRequestKey(null)
      setTurnError(null)
      await loadConversations()
    } catch (caught) {
      setTurnError(toUserFacingApiError(caught, 'The message could not be submitted.'))
      try {
        await loadMessages(activeConversationId)
      } catch {
        // Structured error retained
      }
    } finally {
      setSending(false)
    }
  }

  const submitTurn = (event: FormEvent) => {
    event.preventDefault()
    void sendTurn()
  }

  return (
    <section className="mx-auto flex w-full max-w-6xl flex-col gap-4 pb-8">
      <header className="flex flex-col gap-3 border-b pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-primary">
            <Bot className="h-5 w-5" aria-hidden="true" />
            <p className="text-sm font-semibold">Business Assistant</p>
          </div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Conversation</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Ask for product guidance by text or voice. This release cannot change business data or perform external actions.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
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
          {voiceState === 'idle' ? (
            <Button
              type="button"
              variant="outline"
              disabled={!activeConversationId || sending}
              onClick={() => void startVoice()}
              data-testid="business-assistant-voice-start"
            >
              <Mic className="mr-2 h-4 w-4" aria-hidden="true" />
              Talk by voice
            </Button>
          ) : (
            <Button
              type="button"
              variant="outline"
              onClick={stopVoice}
              disabled={voiceState === 'finalising'}
              data-testid="business-assistant-voice-stop"
            >
              {voiceState === 'connecting' || voiceState === 'finalising' ? (
                <LoaderCircle className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <PhoneOff className="mr-2 h-4 w-4" aria-hidden="true" />
              )}
              {voiceState === 'connecting'
                ? 'Connecting voice…'
                : voiceState === 'finalising'
                  ? 'Finalising voice…'
                  : 'End voice'}
            </Button>
          )}
          <Button type="button" onClick={() => void createConversation()}>
            <MessageCirclePlus className="mr-2 h-4 w-4" aria-hidden="true" />
            New conversation
          </Button>
        </div>
      </header>

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
            {onboarding.product_context.setup_counts && (
              <p className="text-xs text-muted-foreground">
                Configured catalog capacity: {onboarding.product_context.setup_counts.active_services} services · {onboarding.product_context.setup_counts.active_providers} providers · {onboarding.product_context.setup_counts.active_locations} locations
              </p>
            )}
          </div>
          {onboarding.progress.completed_steps.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {onboarding.progress.completed_steps.map((step) => (
                <Badge key={step} variant="secondary" className="gap-1 text-[10px]">
                  <CheckCircle2 className="h-3 w-3 text-primary" aria-hidden="true" />
                  {step.replaceAll('_', ' ')}
                </Badge>
              ))}
            </div>
          )}
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
                      onClick={() => void selectConversation(conversation.id)}
                    >
                      <span className="line-clamp-2 text-sm">
                        {conversation.title || 'New conversation'}
                      </span>
                    </Button>
                  ))}
                </div>
              )}
            </div>
          </aside>
        </>
      )}

      {voiceState !== 'idle' && (
        <div
          className="flex items-center gap-2 rounded-md border border-primary/30 bg-primary/5 px-4 py-3 text-sm"
          role="status"
        >
          <Volume2 className="h-4 w-4" aria-hidden="true" />
          {voiceState === 'connecting'
            ? 'Connecting your microphone and private voice session…'
            : voiceState === 'finalising'
              ? 'Finalising the voice session…'
            : 'Voice is live. You can interrupt naturally or end the call at any time.'}
        </div>
      )}

      {voiceState !== 'idle' && <GPTLiveCaptionTimeline captions={voiceCaptions} />}

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
                disabled={sending}
                onClick={() => void sendTurn()}
              >
                <RotateCcw className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                Retry message
              </Button>
            </div>
          )}
        </div>
      )}

      <section
        className="flex min-h-[32rem] min-w-0 flex-col rounded-lg border bg-card"
        aria-label="Conversation"
      >
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
            {!activeConversationId ? (
              <p className="text-sm text-muted-foreground">Create a conversation to send a message.</p>
            ) : messages.length === 0 ? (
              <p className="text-sm text-muted-foreground">Your saved conversation will appear here.</p>
            ) : (
              messages.map((message) => (
                <article
                  key={message.id}
                  className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                    message.role === 'user'
                      ? 'ml-auto bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground'
                  }`}
                >
                  <p className="mb-1 text-xs font-medium opacity-70">
                    {message.role === 'user' ? 'You' : 'Business Assistant'}
                  </p>
                  {message.channel === 'realtime_voice' && (
                    <p className="mb-1 flex items-center gap-1 text-xs opacity-70">
                      <Mic className="h-3 w-3" aria-hidden="true" /> Voice
                    </p>
                  )}
                  <p className="whitespace-pre-wrap break-words">{message.content}</p>
                </article>
              ))
            )}
          </div>

          <form className="border-t p-3" onSubmit={(event) => void submitTurn(event)}>
            <Textarea
              value={draft}
              onChange={(event) => {
                setDraft(event.target.value)
                setPendingRequestKey(null)
                setTurnError(null)
              }}
              placeholder="Ask how to use FastAPI Bookings…"
              disabled={!activeConversationId || sending}
              rows={3}
              maxLength={20_000}
              aria-label="Message"
            />
            <div className="mt-2 flex justify-end">
              <Button type="submit" disabled={!activeConversationId || !draft.trim() || sending}>
                {sending ? (
                  <LoaderCircle className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Send className="mr-2 h-4 w-4" aria-hidden="true" />
                )}
                Send
              </Button>
            </div>
          </form>
        </div>
      </section>

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
    </section>
  )
}
