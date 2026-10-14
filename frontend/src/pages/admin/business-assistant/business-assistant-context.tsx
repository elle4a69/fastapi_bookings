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
import { useXAIGrokVoice } from './use-xai-grok-voice'
import { type GPTLiveCaption } from '../gpt-live/protocol'
import type { RpcExecutionReceipt } from './rpc'
import { formAdapterRegistry } from './adapters/registry'
import {
  type AgentActivityLog,
  type AgentActivityType,
  type AgentActivityStatus,
  createAgentActivityLog,
  loadPersistedAgentActivityLogs,
  savePersistedAgentActivityLogs,
  clearPersistedAgentActivityLogs,
  MAX_PERSISTED_AGENT_ACTIVITY_LOGS,
} from './realtime-protocol'

export type {
  AgentActivityLog,
  AgentActivityType,
  AgentActivityStatus,
}

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

export type VoiceTransportMode =
  | 'xai_grok_voice'
  | 'direct_gpt_live'

export type VoiceTransportDetails = {
  transport: VoiceTransportMode
  available_transports: string[]
  agent_name: string
  active_target?: string | null
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
  transport: VoiceTransportMode
  setTransport: (transport: VoiceTransportMode) => Promise<void>
  transportDetails: VoiceTransportDetails | null
  updateTransportConfig: (params: {
    transport: VoiceTransportMode
  }) => Promise<void>
  lastRpcReceipt?: RpcExecutionReceipt | null
  diagnosticMode: boolean
  setDiagnosticMode: (enabled: boolean) => Promise<void>
  postClientSnapshot: (payload: {
    client_status?: string
    webrtc_state?: string
    last_error?: string | null
    metadata_json?: Record<string, unknown>
    route?: string
    form_adapter?: string | null
    executor_lease?: string | null
    manual_takeover?: boolean
    staged_fields?: Record<string, unknown> | null
  }) => Promise<void>
  createConversation: () => Promise<number | null>
  selectConversation: (id: number) => Promise<void>
  sendTurn: (overrideContent?: string) => Promise<void>
  refreshConversations: () => Promise<void>
  pageContext: PageContextInfo
  includePageContext: boolean
  setIncludePageContext: (include: boolean) => void
  activityLogs: AgentActivityLog[]
  clearActivityLogs: () => void
  addActivityLog: (log: AgentActivityLog | Omit<AgentActivityLog, 'id' | 'timestamp'>) => void
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
  const [activityLogs, setActivityLogs] = useState<AgentActivityLog[]>(() => loadPersistedAgentActivityLogs())

  const clearActivityLogs = useCallback(() => {
    setActivityLogs([])
    clearPersistedAgentActivityLogs()
  }, [])

  const addActivityLog = useCallback(
    (logInput: AgentActivityLog | Omit<AgentActivityLog, 'id' | 'timestamp'>) => {
      const fullLog: AgentActivityLog =
        'id' in logInput && logInput.id && 'timestamp' in logInput && logInput.timestamp
          ? (logInput as AgentActivityLog)
          : createAgentActivityLog(logInput.type, logInput.title, {
              details: logInput.details,
              payload: logInput.payload,
              status: logInput.status,
              agentLabel: logInput.agentLabel,
              modelName: logInput.modelName,
              id: 'id' in logInput ? (logInput.id as string) : undefined,
              timestamp: 'timestamp' in logInput ? (logInput.timestamp as string) : undefined,
            })
      setActivityLogs((prev) => {
        if (prev.some((item) => item.id === fullLog.id)) return prev
        const seen = new Set<string>()
        const sanitizedPrev: AgentActivityLog[] = []
        for (const item of prev) {
          if (item?.id && !seen.has(item.id)) {
            seen.add(item.id)
            sanitizedPrev.push(item)
          }
        }
        const next = [...sanitizedPrev.slice(-(MAX_PERSISTED_AGENT_ACTIVITY_LOGS - 1)), fullLog]
        savePersistedAgentActivityLogs(next)
        return next
      })
    },
    [],
  )

  const openDrawer = useCallback(() => setDrawerOpen(true), [])
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])
  const toggleDrawer = useCallback(() => setDrawerOpen((prev) => !prev), [])

  const [transport, setTransportState] = useState<VoiceTransportMode>('direct_gpt_live')
  const [transportDetails, setTransportDetails] = useState<VoiceTransportDetails | null>(null)
  const [diagnosticMode, setDiagnosticModeState] = useState(false)

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

  const setDiagnosticMode = useCallback(async (enabled: boolean) => {
    try {
      const res = await apiClient.patch<{ enabled: boolean }>(
        '/api/admin/business-assistant/diagnostic-mode',
        { enabled },
      )
      setDiagnosticModeState(Boolean(res.enabled))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update diagnostic mode')
    }
  }, [])

  const postClientSnapshot = useCallback(
    async (snapshotPayload: {
      client_status?: string
      webrtc_state?: string
      last_error?: string | null
      metadata_json?: Record<string, unknown>
      route?: string
      form_adapter?: string | null
      executor_lease?: string | null
      manual_takeover?: boolean
      staged_fields?: Record<string, unknown> | null
    }) => {
      if (!activeConversationId) return
      const err = snapshotPayload.last_error
      if (err) {
        const lower = err.toLowerCase()
        if (
          lower.includes('inactivity') ||
          lower.includes('timed out') ||
          lower.includes('code 1000') ||
          lower.includes('code 1001') ||
          lower.includes('code 1005') ||
          lower.includes('unexpected closure with code 1006') ||
          lower.includes('closed unexpectedly with code 1006') ||
          lower.includes('unavailable while closing') ||
          lower.includes('disconnected while closing') ||
          lower.includes('disconnected before session.closed')
        ) {
          return
        }
      }
      try {
        await apiClient.post(
          `/api/admin/business-assistant/conversations/${activeConversationId}/client-state`,
          snapshotPayload,
        )
      } catch {
        // Non-blocking best-effort snapshot
      } finally {
        void loadMessages(activeConversationId)
      }
    },
    [activeConversationId, loadMessages],
  )

  useEffect(() => {
    if (typeof window === 'undefined') return
    const handleToolComplete = () => {
      if (activeConversationId) {
        void loadMessages(activeConversationId)
      }
    }
    window.addEventListener('assistant-rpc:action', handleToolComplete)
    window.addEventListener('assistant-tool:complete', handleToolComplete)
    return () => {
      window.removeEventListener('assistant-rpc:action', handleToolComplete)
      window.removeEventListener('assistant-tool:complete', handleToolComplete)
    }
  }, [activeConversationId, loadMessages])

  useEffect(() => {
    let active = true
    apiClient
      .get<{ enabled: boolean }>('/api/admin/business-assistant/diagnostic-mode')
      .then((res) => {
        if (active && res) {
          setDiagnosticModeState(Boolean(res.enabled))
        }
      })
      .catch(() => {
        // Fallback or offline uses default
      })
    return () => {
      active = false
    }
  }, [])

  // Accumulate streaming voice transcripts into messages without splitting words onto separate lines
  const handleVoiceCaptionsChange = useCallback(
    (captions: GPTLiveCaption[]) => {
      setVoiceCaptions(captions)
      if (captions.length === 0) return

      setMessages((prev) => {
        const baseMessages = prev.filter((m) => m.id > 0)
        const voiceDrafts = prev.filter((m) => m.id < 0 && m.channel === 'realtime_voice')

        const updatedVoiceMessages: ConversationMessage[] = captions.map((caption, idx) => {
          const role = caption.speaker === 'user' ? 'user' : 'business_assistant'
          const existing = voiceDrafts[idx]
          const id = existing ? existing.id : -(idx + 1)
          return {
            id,
            conversation_id: activeConversationId ?? 0,
            role,
            content: caption.text,
            in_reply_to_message_id: null,
            created_at: existing ? existing.created_at : new Date().toISOString(),
            channel: 'realtime_voice',
          }
        })

        return [...baseMessages, ...updatedVoiceMessages]
      })
    },
    [activeConversationId],
  )

  const directVoice = useGPTLive({
    conversationId: activeConversationId,
    onCaptionsChange: handleVoiceCaptionsChange,
    onError: (msg) => {
      setError(msg)
      if (activeConversationId) {
        void postClientSnapshot({
          client_status: 'error',
          webrtc_state: 'direct_gpt_live',
          last_error: msg,
        })
      }
    },
    onNavigate: (path) => navigate(path),
    onRpcReceipt: (receipt) => {
      setLastRpcReceipt(receipt)
      if (activeConversationId) {
        void loadMessages(activeConversationId)
      }
    },
    onToolCallComplete: () => {
      if (activeConversationId) {
        void loadMessages(activeConversationId)
      }
    },
    onActivityLog: addActivityLog,
  })

  const xaiVoice = useXAIGrokVoice({
    conversationId: activeConversationId,
    onCaptionsChange: handleVoiceCaptionsChange,
    onError: (msg) => {
      setError(msg)
      if (activeConversationId) {
        void postClientSnapshot({
          client_status: 'error',
          webrtc_state: 'xai_grok_voice',
          last_error: msg,
        })
      }
    },
    onNavigate: (path) => navigate(path),
    onRpcReceipt: (receipt) => {
      setLastRpcReceipt(receipt)
      if (activeConversationId) {
        void loadMessages(activeConversationId)
      }
    },
    onActivityLog: addActivityLog,
  })

  const isXai = transport === 'xai_grok_voice'
  const activeVoice = isXai ? xaiVoice : directVoice

  const voiceState = activeVoice.voiceState
  const stopVoice = useCallback(() => {
    xaiVoice.stopVoice()
    directVoice.stopVoice()
  }, [xaiVoice, directVoice])
  const isMuted = activeVoice.isMuted
  const toggleMute = activeVoice.toggleMute

  const [audioDevices] = useState<MediaDeviceInfo[]>([])
  const [activeAudioDeviceId, setActiveAudioDeviceId] = useState<string | null>(null)
  const switchAudioDevice = useCallback(async (deviceId: string) => {
    setActiveAudioDeviceId(deviceId)
  }, [])

  const setTransport = useCallback(
    async (newTransport: VoiceTransportMode) => {
      stopVoice()
      if (typeof window !== 'undefined') {
        localStorage.setItem('business-assistant-transport', newTransport)
      }
      setTransportState(newTransport)
      try {
        const res = await apiClient.patch<VoiceTransportDetails>(
          '/api/admin/business-assistant/voice/transport',
          { transport: newTransport },
        )
        setTransportState(res.transport)
        setTransportDetails(res)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to switch transport')
      }
    },
    [stopVoice],
  )

  const updateTransportConfig = useCallback(
    async (params: {
      transport: VoiceTransportMode
    }) => {
      stopVoice()
      try {
        const res = await apiClient.patch<VoiceTransportDetails>(
          '/api/admin/business-assistant/voice/transport',
          params,
        )
        setTransportState(res.transport)
        setTransportDetails(res)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update transport configuration')
      }
    },
    [stopVoice],
  )

  useEffect(() => {
    let active = true
    const savedTransport =
      typeof window !== 'undefined'
        ? localStorage.getItem('business-assistant-transport')
        : null

    apiClient
      .get<VoiceTransportDetails>('/api/admin/business-assistant/voice/transport')
      .then((res) => {
        if (active && res) {
          setTransportDetails(res)
          if (
            savedTransport &&
            ['xai_grok_voice', 'direct_gpt_live'].includes(savedTransport)
          ) {
            setTransportState(savedTransport as VoiceTransportMode)
          } else if (res.transport) {
            setTransportState(res.transport)
          }
        }
      })
      .catch(() => {
        // Fallback or offline uses default
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!activeConversationId) return
    const adapter =
      formAdapterRegistry.getAdapterForRoute(location.pathname) ||
      formAdapterRegistry.getActiveAdapter()
    const formAdapterId =
      adapter?.form_id ||
      (location.pathname.startsWith('/admin/settings/business')
        ? 'business_settings'
        : undefined)

    void postClientSnapshot({
      client_status: 'ready',
      route: location.pathname,
      form_adapter: formAdapterId,
    })
  }, [activeConversationId, location.pathname, postClientSnapshot])

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
      setActivityLogs([])
      clearPersistedAgentActivityLogs()
      setError(null)
      setTurnError(null)
      if (currentTenantUserKey) {
        void refreshConversations()
      }
    }
  }, [currentTenantUserKey, stopVoice, refreshConversations])

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

  const startVoice = useCallback(
    async (requestedConversationId?: number) => {
      let targetConversationId =
        requestedConversationId ?? activeConversationId ?? (conversations.length > 0 ? conversations[0].id : null)
      if (!targetConversationId) {
        targetConversationId = await createConversation()
        if (!targetConversationId) {
          setError('Unable to start voice session: failed to create conversation.')
          return
        }
      }
      if (targetConversationId !== activeConversationId) {
        setActiveConversationId(targetConversationId)
        void loadMessages(targetConversationId)
      }
      await activeVoice.startVoice(targetConversationId)
    },
    [activeConversationId, conversations, createConversation, loadMessages, activeVoice, setError],
  )

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

      addActivityLog({
        type: 'USER_INPUT',
        title: 'User Text Turn',
        details: content,
        payload: { content, conversation_id: targetConversationId, request_key: nextRequestKey },
        status: 'info',
        agentLabel: 'User / Client Input',
        modelName: 'client',
      })

      try {
        const result = await apiClient.post<TextTurnResponse>(
          `/api/admin/business-assistant/conversations/${targetConversationId}/messages`,
          { content, request_key: nextRequestKey },
        )
        setMessages((current) => {
          const withoutCurrent = current.filter((m) => m.id !== result.user_message.id)
          return [...withoutCurrent, result.user_message, result.assistant_message]
        })
        addActivityLog({
          type: 'REASONING_OUT',
          title: 'Assistant Response',
          details: result.assistant_message.content,
          payload: result,
          status: 'success',
          agentLabel: 'GPT-4o (Text Assistant)',
          modelName: 'gpt-4o',
        })
        if (!overrideContent) {
          setDraft('')
        }
        setPendingRequestKey(null)
        setTurnError(null)
      } catch (caught) {
        addActivityLog({
          type: 'ERROR',
          title: 'Text Turn Failed',
          details: caught instanceof Error ? caught.message : 'The message could not be submitted.',
          payload: caught,
          status: 'error',
          agentLabel: 'GPT-4o (Text Assistant)',
          modelName: 'gpt-4o',
        })
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
      addActivityLog,
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
      isMuted,
      toggleMute,
      audioDevices,
      activeAudioDeviceId,
      switchAudioDevice,
      transport,
      setTransport,
      transportDetails,
      updateTransportConfig,
      lastRpcReceipt,
      diagnosticMode,
      setDiagnosticMode,
      postClientSnapshot,
      createConversation,
      selectConversation,
      sendTurn,
      refreshConversations,
      pageContext,
      includePageContext,
      setIncludePageContext,
      activityLogs,
      clearActivityLogs,
      addActivityLog,
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
      isMuted,
      toggleMute,
      audioDevices,
      activeAudioDeviceId,
      switchAudioDevice,
      transport,
      setTransport,
      transportDetails,
      updateTransportConfig,
      lastRpcReceipt,
      diagnosticMode,
      setDiagnosticMode,
      postClientSnapshot,
      createConversation,
      selectConversation,
      sendTurn,
      refreshConversations,
      pageContext,
      includePageContext,
      activityLogs,
      clearActivityLogs,
      addActivityLog,
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

export function useBusinessAssistantOptional(): BusinessAssistantContextType | null {
  return useContext(BusinessAssistantContext)
}
