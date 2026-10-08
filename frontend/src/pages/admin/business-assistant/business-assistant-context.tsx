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
import { useLocation, useNavigate } from 'react-router-dom'

import {
  apiClient,
  toUserFacingApiError,
  type UserFacingApiError,
} from '@/lib/api'
import { AuthContext } from '@/context/auth-context'

import {
  useGPTLive,
  type GPTLiveVoiceState,
} from '../gpt-live/use-gpt-live'
import { useLiveKitVoice } from './use-livekit-voice'
import { type GPTLiveCaption } from '../gpt-live/protocol'
import type { RpcExecutionReceipt } from './rpc'

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
  voiceState: GPTLiveVoiceState
  voiceCaptions: GPTLiveCaption[]
  startVoice: (requestedConversationId?: number) => Promise<void>
  stopVoice: () => void
  isMuted: boolean
  toggleMute: () => Promise<void>
  audioDevices: MediaDeviceInfo[]
  activeAudioDeviceId: string | null
  switchAudioDevice: (deviceId: string) => Promise<void>
  transport: 'livekit_gpt_live' | 'direct_gpt_live'
  setTransport: (transport: 'livekit_gpt_live' | 'direct_gpt_live') => void
  lastRpcReceipt?: RpcExecutionReceipt | null
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
  const navigate = useNavigate()
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
  const [voiceCaptions, setVoiceCaptions] = useState<GPTLiveCaption[]>([])
  const [lastRpcReceipt, setLastRpcReceipt] = useState<RpcExecutionReceipt | null>(null)

  const openDrawer = useCallback(() => setDrawerOpen(true), [])
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])
  const toggleDrawer = useCallback(() => setDrawerOpen((prev) => !prev), [])

  const [transport, setTransport] = useState<'livekit_gpt_live' | 'direct_gpt_live'>('livekit_gpt_live')

  const livekitVoice = useLiveKitVoice({
    conversationId: activeConversationId,
    onCaptionsChange: setVoiceCaptions,
    onError: setError,
    onNavigate: (path) => navigate(path),
    onRpcReceipt: (receipt) => setLastRpcReceipt(receipt),
  })

  const directVoice = useGPTLive({
    conversationId: activeConversationId,
    onCaptionsChange: setVoiceCaptions,
    onError: setError,
  })

  useEffect(() => {
    let active = true
    apiClient
      .get<{ transport?: string }>('/api/admin/business-assistant/voice/transport')
      .then((res) => {
        if (active && res?.transport === 'direct_gpt_live') {
          setTransport('direct_gpt_live')
        }
      })
      .catch(() => {
        // Fallback or offline uses default
      })
    return () => {
      active = false
    }
  }, [])

  const voiceState = transport === 'livekit_gpt_live' ? livekitVoice.voiceState : directVoice.voiceState
  const startVoice = transport === 'livekit_gpt_live' ? livekitVoice.startVoice : directVoice.startVoice
  const stopVoice = useCallback(() => {
    livekitVoice.stopVoice()
    directVoice.stopVoice()
  }, [livekitVoice, directVoice])

  // Multi-tenant and logout scope isolation: clear all state and stop voice on tenant/user change
  const authContext = useContext(AuthContext)
  const currentTenantUserKey = authContext?.user
    ? `${authContext.user.tenant_id ?? 0}:${authContext.user.id}`
    : null
  const previousUserKeyRef = useRef<string | null>(currentTenantUserKey)

  useEffect(() => {
    if (previousUserKeyRef.current !== currentTenantUserKey) {
      previousUserKeyRef.current = currentTenantUserKey
      stopVoice()
      setDrawerOpen(false)
      setActiveConversationId(null)
      setConversations([])
      setMessages([])
      setVoiceCaptions([])
      setError(null)
      setTurnError(null)
    }
  }, [currentTenantUserKey, stopVoice])

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
      voiceCaptions,
      startVoice,
      stopVoice,
      isMuted: livekitVoice.isMuted,
      toggleMute: livekitVoice.toggleMute,
      audioDevices: livekitVoice.audioDevices,
      activeAudioDeviceId: livekitVoice.activeAudioDeviceId,
      switchAudioDevice: livekitVoice.switchAudioDevice,
      transport,
      setTransport,
      lastRpcReceipt,
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
      voiceCaptions,
      startVoice,
      stopVoice,
      livekitVoice.isMuted,
      livekitVoice.toggleMute,
      livekitVoice.audioDevices,
      livekitVoice.activeAudioDeviceId,
      livekitVoice.switchAudioDevice,
      transport,
      setTransport,
      lastRpcReceipt,
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
