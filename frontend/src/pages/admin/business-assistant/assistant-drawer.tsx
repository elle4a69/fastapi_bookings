import { useEffect, useRef, useState } from 'react'
import {
  Bot,
  History,
  MessageSquare,
  Plus,
  Ticket,
  X,
} from 'lucide-react'

import { Button } from '@/components/ui/button'

import {
  useBusinessAssistant,
} from './business-assistant-context'
import { ConversationView } from './conversation'
import { TicketStatusSection } from './ticket-status'

export function BusinessAssistantDrawer() {
  const {
    drawerOpen,
    closeDrawer,
    conversations,
    activeConversationId,
    selectConversation,
    createConversation,
    pageContext,
  } = useBusinessAssistant()

  const [activeTab, setActiveTab] = useState<'chat' | 'history' | 'tickets'>('chat')
  const drawerRef = useRef<HTMLDivElement | null>(null)
  const previousActiveElementRef = useRef<HTMLElement | null>(null)

  // Focus management & Escape key handling
  useEffect(() => {
    if (drawerOpen) {
      previousActiveElementRef.current = document.activeElement as HTMLElement | null

      // Trap focus initially to drawer
      const timer = setTimeout(() => {
        const focusable = drawerRef.current?.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        )
        if (focusable && focusable.length > 0) {
          focusable[0].focus()
        }
      }, 50)

      const handleKeyDown = (event: KeyboardEvent) => {
        if (event.key === 'Escape') {
          event.preventDefault()
          closeDrawer()
        }
      }

      window.addEventListener('keydown', handleKeyDown)
      return () => {
        clearTimeout(timer)
        window.removeEventListener('keydown', handleKeyDown)
      }
    } else {
      // Restore focus on close
      if (previousActiveElementRef.current && typeof previousActiveElementRef.current.focus === 'function') {
        previousActiveElementRef.current.focus()
      }
    }
  }, [drawerOpen, closeDrawer])

  if (!drawerOpen) {
    return null
  }

  return (
    <>
      {/* Backdrop: z-40 ensures standard modal dialogs (higher layer) stay on top */}
      <div
        className="fixed inset-0 z-40 bg-background/60 backdrop-blur-xs transition-opacity"
        onClick={closeDrawer}
        aria-hidden="true"
        data-testid="business-assistant-drawer-backdrop"
      />

      {/* Drawer: z-40 discipline */}
      <aside
        ref={drawerRef}
        id="business-assistant-drawer"
        role="dialog"
        aria-label="Business Assistant"
        aria-modal="true"
        data-testid="business-assistant-drawer"
        className="fixed inset-y-0 right-0 z-40 flex w-full flex-col border-l bg-card shadow-2xl transition-transform sm:w-[28rem] lg:w-[32rem]"
      >
        {/* Header */}
        <header className="flex items-center justify-between border-b px-4 py-3 bg-muted/20">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Bot className="h-4 w-4" aria-hidden="true" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h2 className="text-sm font-semibold tracking-tight text-foreground">
                  Business Assistant
                </h2>
              </div>
              <p className="text-[11px] text-muted-foreground truncate max-w-[200px] sm:max-w-[240px]">
                {pageContext ? `${pageContext.module_name} (${pageContext.current_path})` : 'Active'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="outline"
              size="icon-sm"
              onClick={() => void createConversation()}
              title="New conversation"
              aria-label="New conversation"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={closeDrawer}
              title="Close Business Assistant"
              aria-label="Close Business Assistant"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        </header>

        {/* Tab switchers */}
        <nav
          className="flex border-b bg-muted/10 px-3 text-xs font-medium"
          aria-label="Assistant views"
        >
          <button
            type="button"
            onClick={() => setActiveTab('chat')}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs transition-colors ${
              activeTab === 'chat'
                ? 'border-primary text-primary font-semibold'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <MessageSquare className="h-3.5 w-3.5" aria-hidden="true" />
            Chat
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('history')}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs transition-colors ${
              activeTab === 'history'
                ? 'border-primary text-primary font-semibold'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <History className="h-3.5 w-3.5" aria-hidden="true" />
            History ({conversations.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('tickets')}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs transition-colors ${
              activeTab === 'tickets'
                ? 'border-primary text-primary font-semibold'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <Ticket className="h-3.5 w-3.5" aria-hidden="true" />
            Tickets
          </button>
        </nav>

        {/* Content area */}
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-3">
          {activeTab === 'chat' && (
            <ConversationView showContextBanner={true} className="border-0 shadow-none" />
          )}

          {activeTab === 'history' && (
            <div className="flex flex-1 flex-col overflow-y-auto" aria-label="Conversation history">
              {conversations.length === 0 ? (
                <div className="flex flex-1 items-center justify-center p-6 text-center text-xs text-muted-foreground">
                  <p>No saved conversations yet.</p>
                </div>
              ) : (
                <div className="flex flex-col gap-1.5">
                  {conversations.map((c) => (
                    <Button
                      key={c.id}
                      type="button"
                      variant={c.id === activeConversationId ? 'secondary' : 'ghost'}
                      className="h-auto flex-col items-start px-3 py-2.5 text-left"
                      onClick={() => {
                        void selectConversation(c.id)
                        setActiveTab('chat')
                      }}
                    >
                      <span className="line-clamp-1 font-medium text-xs text-foreground">
                        {c.title || `Conversation #${c.id}`}
                      </span>
                      <span className="mt-0.5 text-[10px] text-muted-foreground">
                        {new Date(c.created_at).toLocaleDateString()} · {c.status}
                      </span>
                    </Button>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'tickets' && (
            <div className="flex flex-1 flex-col overflow-y-auto">
              <TicketStatusSection conversationId={activeConversationId} />
            </div>
          )}
        </div>
      </aside>
    </>
  )
}
