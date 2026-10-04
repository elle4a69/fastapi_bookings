import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useLocation } from 'react-router-dom'

import {
  apiClient,
  toUserFacingApiError,
  type UserFacingApiError,
} from '@/lib/api'

import {
  useRealtimeVoice,
  type RealtimeVoiceState,
} from './use-realtime-voice'

export type Conversation = {
  id: number
  title: string | null
  status: string
  created_at: string
  updated_at: string
}

export type ConversationMessage = {
  id: number
  conversation_id: number
  role: 'user' | 'business_assistant' | 'system'
  content: string
  in_reply_to_message_id: number | null
  created_at: string
  channel?: 'text' | 'realtime_voice'
}

export type TextTurnResponse = {
  user_message: ConversationMessage
  assistant_message: ConversationMessage
  duplicate_request: boolean
}

import {
  resolvePageContext,
  type PageContextInfo,
} from './context-boundary'

export {
  resolvePageContext,
  type PageContextInfo,
}

function requestKey(): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `turn-${Date.now()}-${Math.random().toString(36).slice(2)}`
  )
}

export type BusinessAssistantContextType = {
  drawerOpen: boolean
  openDrawer: () => void
  closeDrawer: () => void
  toggleDrawer: () => void
  conversations: Conversation[]
  activeConversationId: number | null
  setActiveConversationId: (id: number | null) => void
  messages: ConversationMessage[]
  draft: string
  setDraft: (draft: string) => void
  loading: boolean
  sending: boolean
  error: string | null
  setError: (err: string | null) => void
  turnError: UserFacingApiError | null
  setTurnError: (err: UserFacingApiError | null) => void
  voiceState: RealtimeVoiceState
  startVoice: () => Promise<void>
  stopVoice: () => void
  createConversation: () => Promise<number | null>
  selectConversation: (id: number) => Promise<void>
  sendTurn: (overrideContent?: string) => Promise<void>
  refreshConversations: () => Promise<void>
  pageContext: PageContextInfo
  includePageContext: boolean
  setIncludePageContext: (include: boolean) => void
}

const BusinessAssistantContext = createContext<BusinessAssistantContextType | null>(null)

export function BusinessAssistantProvider({ children }: { children: ReactNode }) {
  const location = useLocation()
  const pageContext = useMemo(() => resolvePageContext(location.pathname), [location.pathname])

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [draft, setDraft] = useState('')
  const [pendingRequestKey, setPendingRequestKey] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [turnError, setTurnError] = useState<UserFacingApiError | null>(null)
  const [includePageContext, setIncludePageContext] = useState(false)

  const openDrawer = useCallback(() => setDrawerOpen(true), [])
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])
  const toggleDrawer = useCallback(() => setDrawerOpen((prev) => !prev), [])

  const { voiceState, startVoice, stopVoice } = useRealtimeVoice({
    conversationId: activeConversationId,
    onTurnPersisted: (turn) => {
      setMessages((current) => {
        const next = [
          ...current.filter(
            (m) => m.id !== turn.user_message.id && m.id !== turn.assistant_message.id,
          ),
          turn.user_message,
          turn.assistant_message,
        ]
        return next.sort((left, right) => {
          const compared = left.created_at.localeCompare(right.created_at)
          return compared || left.id - right.id
        })
      })
    },
    onError: setError,
  })

  const loadMessages = useCallback(async (conversationId: number) => {
    try {
      const history = await apiClient.get<ConversationMessage[]>(
        `/api/admin/business-assistant/conversations/${conversationId}/messages`,
      )
      setMessages(history)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load conversation messages.')
    }
  }, [])

  const refreshConversations = useCallback(async () => {
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
  }, [activeConversationId, loadMessages])

  const initialLoadedRef = useRef(false)
  useEffect(() => {
    if (initialLoadedRef.current) return
    initialLoadedRef.current = true
    void refreshConversations()
  }, [refreshConversations])

  const selectConversation = useCallback(
    async (conversationId: number) => {
      setError(null)
      setActiveConversationId(conversationId)
      await loadMessages(conversationId)
    },
    [loadMessages],
  )

  const createConversation = useCallback(async (): Promise<number | null> => {
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
      return conversation.id
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to create conversation.')
      return null
    }
  }, [])

  const sendTurn = useCallback(
    async (overrideContent?: string) => {
      let targetConversationId = activeConversationId
      if (!targetConversationId) {
        targetConversationId = await createConversation()
        if (!targetConversationId) return
      }

      let content = (overrideContent ?? draft).trim()
      if (!content || sending) return

      if (includePageContext) {
        content = `[Context: path=${pageContext.current_path}, module=${pageContext.module_name}]\n${content}`
      }

      const nextRequestKey = pendingRequestKey ?? requestKey()
      setPendingRequestKey(nextRequestKey)
      setSending(true)
      setTurnError(null)

      try {
        const result = await apiClient.post<TextTurnResponse>(
          `/api/admin/business-assistant/conversations/${targetConversationId}/messages`,
          { content, request_key: nextRequestKey },
        )
        setMessages((current) => {
          const withoutCurrent = current.filter((m) => m.id !== result.user_message.id)
          return [...withoutCurrent, result.user_message, result.assistant_message]
        })
        if (!overrideContent) {
          setDraft('')
        }
        setPendingRequestKey(null)
        setTurnError(null)
      } catch (caught) {
        setTurnError(toUserFacingApiError(caught, 'The message could not be submitted.'))
        try {
          await loadMessages(targetConversationId)
        } catch {
          // Preserve the turn submission error
        }
      } finally {
        setSending(false)
      }
    },
    [
      activeConversationId,
      createConversation,
      draft,
      includePageContext,
      loadMessages,
      pageContext.current_path,
      pageContext.module_name,
      pendingRequestKey,
      sending,
    ],
  )

  const value = useMemo(
    () => ({
      drawerOpen,
      openDrawer,
      closeDrawer,
      toggleDrawer,
      conversations,
      activeConversationId,
      setActiveConversationId,
      messages,
      draft,
      setDraft,
      loading,
      sending,
      error,
      setError,
      turnError,
      setTurnError,
      voiceState,
      startVoice,
      stopVoice,
      createConversation,
      selectConversation,
      sendTurn,
      refreshConversations,
      pageContext,
      includePageContext,
      setIncludePageContext,
    }),
    [
      drawerOpen,
      openDrawer,
      closeDrawer,
      toggleDrawer,
      conversations,
      activeConversationId,
      messages,
      draft,
      loading,
      sending,
      error,
      turnError,
      voiceState,
      startVoice,
      stopVoice,
      createConversation,
      selectConversation,
      sendTurn,
      refreshConversations,
      pageContext,
      includePageContext,
    ],
  )

  return (
    <BusinessAssistantContext.Provider value={value}>
      {children}
    </BusinessAssistantContext.Provider>
  )
}

export function useBusinessAssistant() {
  const context = useContext(BusinessAssistantContext)
  if (!context) {
    throw new Error('useBusinessAssistant must be used within a BusinessAssistantProvider')
  }
  return context
}
