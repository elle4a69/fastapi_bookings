import { useCallback, useEffect, useRef, useState } from 'react'

import { authenticatedAdminFetch } from '@/lib/api'

import {
  formatRealtimeSessionUpdate,
  formatRealtimeToolOutput,
  pairReadyRealtimeTranscripts,
  parseRealtimeAssistantTranscript,
  parseRealtimeToolCall,
  parseRealtimeUserTranscript,
  upsertRealtimeAssistantTranscript,
  upsertRealtimeUserTranscript,
  type RealtimeAssistantTranscript,
  type RealtimeUserTranscript,
} from './realtime-protocol.ts'

export type RealtimeVoiceState = 'idle' | 'connecting' | 'live'

export type PersistedVoiceMessage = {
  id: number
  conversation_id: number
  role: 'user' | 'business_assistant' | 'system'
  content: string
  in_reply_to_message_id: number | null
  created_at: string
  channel: 'realtime_voice'
}

export type PersistedVoiceTurn = {
  user_message: PersistedVoiceMessage
  assistant_message: PersistedVoiceMessage
  duplicate_turn: boolean
}

export type RealtimeVoiceOptions = {
  conversationId: number | null
  onTurnPersisted: (turn: PersistedVoiceTurn) => void
  onError: (message: string) => void
}

function newSessionId(): string {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  throw new Error('This browser cannot create a secure realtime session identifier.')
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

async function responseError(response: Response, fallback: string): Promise<Error> {
  const body = await response.text().catch(() => '')
  try {
    const parsed = JSON.parse(body)
    const detail =
      typeof parsed?.error?.message === 'string'
        ? parsed.error.message
        : typeof parsed?.detail === 'string'
          ? parsed.detail
          : typeof parsed?.detail?.message === 'string'
            ? parsed.detail.message
            : ''
    return new Error(detail || fallback)
  } catch {
    return new Error(fallback)
  }
}

export function useRealtimeVoice(options: RealtimeVoiceOptions) {
  const [voiceState, setVoiceState] = useState<RealtimeVoiceState>('idle')
  const optionsRef = useRef(options)
  const generationRef = useRef(0)
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null)
  const microphoneStreamRef = useRef<MediaStream | null>(null)
  const audioElementRef = useRef<HTMLAudioElement | null>(null)
  const dataChannelRef = useRef<RTCDataChannel | null>(null)
  const sessionIdRef = useRef<string | null>(null)
  const usersRef = useRef<RealtimeUserTranscript[]>([])
  const assistantsRef = useRef<RealtimeAssistantTranscript[]>([])
  const seenTerminalEventsRef = useRef(new Set<string>())
  const persistenceChainRef = useRef<Promise<void>>(Promise.resolve())

  useEffect(() => {
    optionsRef.current = options
  }, [options])

  const setState = useCallback((state: RealtimeVoiceState) => {
    setVoiceState(state)
  }, [])

  const stopVoice = useCallback(() => {
    generationRef.current += 1
    microphoneStreamRef.current?.getTracks().forEach((track) => track.stop())
    microphoneStreamRef.current = null
    dataChannelRef.current?.close()
    dataChannelRef.current = null
    peerConnectionRef.current?.close()
    peerConnectionRef.current = null
    if (audioElementRef.current) {
      audioElementRef.current.pause()
      audioElementRef.current.srcObject = null
      audioElementRef.current.remove()
      audioElementRef.current = null
    }
    sessionIdRef.current = null
    usersRef.current = []
    assistantsRef.current = []
    seenTerminalEventsRef.current.clear()
    setState('idle')
  }, [setState])

  const flushTranscriptPairs = useCallback(() => {
    const conversationId = optionsRef.current.conversationId
    const sessionId = sessionIdRef.current
    if (!conversationId || !sessionId) return

    const paired = pairReadyRealtimeTranscripts(usersRef.current, assistantsRef.current)
    usersRef.current = paired.users
    assistantsRef.current = paired.assistants
    if (paired.dropped > 0) {
      optionsRef.current.onError('A partial voice exchange could not be saved. You can continue in text.')
    }

    for (const turn of paired.pairs) {
      persistenceChainRef.current = persistenceChainRef.current
        .then(async () => {
          const response = await authenticatedAdminFetch(
            `/api/admin/business-assistant/conversations/${conversationId}/realtime/turns`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                session_id: sessionId,
                user_item_id: turn.user.sourceId,
                assistant_response_id: turn.assistant.sourceId,
                user_transcript: turn.user.transcript,
                assistant_transcript: turn.assistant.transcript,
              }),
            },
          )
          if (!response.ok) throw await responseError(response, 'The completed voice turn could not be saved.')
          const payload = (await response.json()) as PersistedVoiceTurn
          optionsRef.current.onTurnPersisted(payload)
        })
        .catch((error: unknown) => {
          optionsRef.current.onError(
            error instanceof Error ? error.message : 'The completed voice turn could not be saved.',
          )
        })
    }
  }, [])

  const handleRealtimeEvent = useCallback(
    async (payload: Record<string, unknown>) => {
      const user = parseRealtimeUserTranscript(payload)
      if (user) {
        const key = `user:${user.sourceId}`
        if (user.state !== 'pending' && seenTerminalEventsRef.current.has(key)) return
        if (user.state !== 'pending') seenTerminalEventsRef.current.add(key)
        usersRef.current = upsertRealtimeUserTranscript(usersRef.current, user)
        flushTranscriptPairs()
        return
      }

      const assistant = parseRealtimeAssistantTranscript(payload)
      if (assistant) {
        const key = `assistant:${assistant.sourceId}`
        if (seenTerminalEventsRef.current.has(key)) return
        seenTerminalEventsRef.current.add(key)
        assistantsRef.current = upsertRealtimeAssistantTranscript(assistantsRef.current, assistant)
        flushTranscriptPairs()
        return
      }

      const toolCall = parseRealtimeToolCall(payload)
      if (toolCall) {
        const conversationId = optionsRef.current.conversationId
        if (conversationId && dataChannelRef.current?.readyState === 'open') {
          try {
            const response = await authenticatedAdminFetch(
              `/api/admin/business-assistant/conversations/${conversationId}/realtime/tools`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  name: toolCall.name,
                  arguments: toolCall.arguments,
                }),
              },
            )
            const result = response.ok ? ((await response.json()) as Record<string, unknown>) : { status: 'error' }
            const toolOutputEvent = formatRealtimeToolOutput(toolCall.callId, result)
            dataChannelRef.current.send(JSON.stringify(toolOutputEvent))
            dataChannelRef.current.send(JSON.stringify({ type: 'response.create' }))
          } catch {
            const errorOutput = formatRealtimeToolOutput(toolCall.callId, {
              status: 'unavailable',
              reason: 'Tool execution failed in this voice session.',
            })
            dataChannelRef.current?.send(JSON.stringify(errorOutput))
            dataChannelRef.current?.send(JSON.stringify({ type: 'response.create' }))
          }
        }
        return
      }

      if (payload.type === 'error') {
        const error = asRecord(payload.error)
        const message = typeof error?.message === 'string' ? error.message : 'Realtime voice reported an error.'
        optionsRef.current.onError(message)
      }
    },
    [flushTranscriptPairs],
  )

  const startVoice = useCallback(async () => {
    const conversationId = optionsRef.current.conversationId
    if (!conversationId || voiceState !== 'idle') return
    if (!navigator.mediaDevices?.getUserMedia) {
      optionsRef.current.onError('This browser does not support microphone access. You can continue in text.')
      return
    }

    const generation = generationRef.current + 1
    generationRef.current = generation
    sessionIdRef.current = newSessionId()
    usersRef.current = []
    assistantsRef.current = []
    seenTerminalEventsRef.current.clear()
    setState('connecting')

    try {
      const microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (generationRef.current !== generation) {
        microphoneStream.getTracks().forEach((track) => track.stop())
        return
      }
      microphoneStreamRef.current = microphoneStream

      const peerConnection = new RTCPeerConnection()
      peerConnectionRef.current = peerConnection
      const audioElement = document.createElement('audio')
      audioElement.autoplay = true
      audioElement.hidden = true
      audioElement.setAttribute('playsinline', 'true')
      document.body.appendChild(audioElement)
      audioElementRef.current = audioElement
      peerConnection.ontrack = (event) => {
        audioElement.srcObject = event.streams[0]
        void audioElement.play().catch(() => undefined)
      }
      peerConnection.onconnectionstatechange = () => {
        if (peerConnectionRef.current !== peerConnection) return
        if (peerConnection.connectionState === 'connected') setState('live')
        if (['failed', 'disconnected', 'closed'].includes(peerConnection.connectionState)) stopVoice()
      }
      microphoneStream.getAudioTracks().forEach((track) => peerConnection.addTrack(track, microphoneStream))

      const sessionConfigPromise = authenticatedAdminFetch(
        `/api/admin/business-assistant/conversations/${conversationId}/realtime/session`,
      )
        .then(async (res) => {
          if (!res.ok) return null
          return (await res.json()) as { instructions: string; tools: Array<Record<string, unknown>> }
        })
        .catch(() => null)

      let sessionUpdated = false
      const sendSessionUpdate = async (channel: RTCDataChannel) => {
        if (sessionUpdated) return
        const config = await sessionConfigPromise
        if (config && channel.readyState === 'open' && generationRef.current === generation && !sessionUpdated) {
          sessionUpdated = true
          channel.send(JSON.stringify(formatRealtimeSessionUpdate(config.instructions, config.tools)))
        }
      }

      const attachChannel = (channel: RTCDataChannel) => {
        dataChannelRef.current = channel
        channel.onmessage = (event) => {
          try {
            const payload = asRecord(JSON.parse(String(event.data)))
            if (payload) void handleRealtimeEvent(payload)
          } catch {
            optionsRef.current.onError('Realtime voice sent an invalid event. You can continue in text.')
          }
        }
        channel.onopen = () => {
          void sendSessionUpdate(channel)
        }
        if (channel.readyState === 'open') {
          void sendSessionUpdate(channel)
        }
      }

      const dataChannel = peerConnection.createDataChannel('oai-events')
      attachChannel(dataChannel)
      peerConnection.ondatachannel = (event) => {
        attachChannel(event.channel)
      }

      const offer = await peerConnection.createOffer()
      await peerConnection.setLocalDescription(offer)
      if (!offer.sdp) throw new Error('The browser could not create a voice offer.')
      const response = await authenticatedAdminFetch(
        `/api/admin/business-assistant/conversations/${conversationId}/realtime`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/sdp', Accept: 'application/sdp' },
          body: offer.sdp,
        },
      )
      if (!response.ok) throw await responseError(response, 'Realtime voice could not start.')
      const answerSdp = await response.text()
      if (!answerSdp.trim()) throw new Error('Realtime voice returned an empty session answer.')
      if (generationRef.current !== generation) return
      await peerConnection.setRemoteDescription({ type: 'answer', sdp: answerSdp })
      if (dataChannelRef.current?.readyState === 'open') {
        void sendSessionUpdate(dataChannelRef.current)
      }
    } catch (error: unknown) {
      if (generationRef.current !== generation) return
      stopVoice()
      if (error instanceof DOMException && error.name === 'NotAllowedError') {
        optionsRef.current.onError('Microphone access was declined. You can continue in text.')
      } else {
        optionsRef.current.onError(error instanceof Error ? error.message : 'Realtime voice could not start.')
      }
    }
  }, [handleRealtimeEvent, setState, stopVoice, voiceState])

  useEffect(() => () => stopVoice(), [stopVoice])

  return { voiceState, startVoice, stopVoice }
}

export const useBusinessAssistantRealtimeVoice = useRealtimeVoice
