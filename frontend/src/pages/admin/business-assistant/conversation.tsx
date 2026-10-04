import { type FormEvent, type KeyboardEvent, useEffect, useRef } from 'react'
import {
  Compass,
  LoaderCircle,
  Mic,
  PhoneOff,
  RotateCcw,
  Send,
  Volume2,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

import {
  useBusinessAssistant,
  type ConversationMessage,
} from './business-assistant-context'

export function ConversationMessagesList({
  messages,
  activeConversationId,
}: {
  messages: ConversationMessage[]
  activeConversationId: number | null
}) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (!activeConversationId) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-muted-foreground">
        <p>Start a conversation to begin asking for guidance.</p>
      </div>
    )
  }

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-muted-foreground">
        <p>No messages in this conversation yet. Send a question below.</p>
      </div>
    )
  }

  return (
    <div
      className="flex flex-1 flex-col gap-3 overflow-y-auto p-3 sm:p-4"
      aria-label="Conversation message stream"
      aria-live="polite"
    >
      {messages.map((message) => {
        const isUser = message.role === 'user'
        return (
          <article
            key={message.id}
            data-testid={`message-${message.id}`}
            className={`flex max-w-[85%] flex-col rounded-lg px-3 py-2 text-sm shadow-xs ${
              isUser
                ? 'ml-auto bg-primary text-primary-foreground'
                : 'bg-muted text-foreground'
            }`}
          >
            <div className="mb-1 flex items-center justify-between gap-2 text-xs opacity-75">
              <span className="font-semibold">
                {isUser ? 'You' : 'Business Assistant'}
              </span>
              {message.channel === 'realtime_voice' && (
                <span className="flex items-center gap-1 font-mono text-[10px]">
                  <Mic className="h-3 w-3" aria-hidden="true" />
                  Voice
                </span>
              )}
            </div>
            <p className="whitespace-pre-wrap break-words leading-relaxed">
              {message.content}
            </p>
          </article>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}

export function ConversationView({
  showContextBanner = true,
  className = '',
}: {
  showContextBanner?: boolean
  className?: string
}) {
  const {
    activeConversationId,
    messages,
    draft,
    setDraft,
    sending,
    error,
    turnError,
    voiceState,
    startVoice,
    stopVoice,
    sendTurn,
    pageContext,
    includePageContext,
    setIncludePageContext,
  } = useBusinessAssistant()

  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    void sendTurn()
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void sendTurn()
    }
  }

  return (
    <section
      className={`flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border bg-card ${className}`}
      aria-label="Conversation"
    >
      {showContextBanner && pageContext && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5 truncate">
            <Compass className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
            <span className="truncate">
              Page context: <code className="font-mono text-foreground">{pageContext.current_path}</code> ({pageContext.module_name})
            </span>
          </div>
          <label className="flex cursor-pointer items-center gap-1.5 select-none font-medium text-foreground">
            <input
              type="checkbox"
              checked={includePageContext}
              onChange={(e) => setIncludePageContext(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-muted-foreground/30 accent-primary"
            />
            Attach page context
          </label>
        </div>
      )}

      {voiceState !== 'idle' && (
        <div
          className="flex items-center justify-between border-b border-primary/20 bg-primary/10 px-3 py-2 text-xs text-primary"
          role="status"
        >
          <div className="flex items-center gap-2">
            <Volume2 className="h-4 w-4 animate-pulse" aria-hidden="true" />
            <span>
              {voiceState === 'connecting'
                ? 'Connecting your microphone and encrypted voice session…'
                : 'Voice is live. You can speak naturally or interrupt at any time.'}
            </span>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs text-primary hover:bg-primary/20"
            onClick={stopVoice}
          >
            <PhoneOff className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
            End call
          </Button>
        </div>
      )}

      {error && (
        <div
          className="m-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive"
          role="alert"
        >
          {error}
        </div>
      )}

      {turnError && (
        <div
          className="m-3 flex flex-col gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive"
          role="alert"
        >
          <p>
            <span className="font-semibold">{turnError.code}</span>: {turnError.message}
          </p>
          {turnError.requestId && (
            <p className="font-mono text-[10px]">Request ID: {turnError.requestId}</p>
          )}
          {turnError.retryable && (
            <div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                disabled={sending}
                onClick={() => void sendTurn()}
              >
                <RotateCcw className="mr-1 h-3 w-3" aria-hidden="true" />
                Retry message
              </Button>
            </div>
          )}
        </div>
      )}

      <ConversationMessagesList
        messages={messages}
        activeConversationId={activeConversationId}
      />

      <form
        onSubmit={handleSubmit}
        className="border-t bg-background/50 p-2 sm:p-3"
        aria-label="Send message"
      >
        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask for business assistance (e.g. how to configure services or view invoices)…"
            disabled={!activeConversationId || sending}
            rows={2}
            maxLength={20_000}
            className="min-h-[50px] resize-none pr-24 text-xs sm:text-sm"
            aria-label="Message"
          />
          <div className="absolute right-2 bottom-2 flex items-center gap-1.5">
            {voiceState === 'idle' ? (
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                disabled={!activeConversationId || sending}
                onClick={() => void startVoice()}
                title="Start voice session"
                aria-label="Start voice session"
              >
                <Mic className="h-4 w-4" aria-hidden="true" />
              </Button>
            ) : (
              <Button
                type="button"
                variant="destructive"
                size="icon-sm"
                onClick={stopVoice}
                title="End voice session"
                aria-label="End voice session"
              >
                {voiceState === 'connecting' ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <PhoneOff className="h-4 w-4" aria-hidden="true" />
                )}
              </Button>
            )}
            <Button
              type="submit"
              size="sm"
              disabled={!activeConversationId || !draft.trim() || sending}
              className="h-8 px-3 text-xs"
            >
              {sending ? (
                <LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <Send className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              <span className="ml-1 hidden sm:inline">Send</span>
            </Button>
          </div>
        </div>
      </form>
    </section>
  )
}
