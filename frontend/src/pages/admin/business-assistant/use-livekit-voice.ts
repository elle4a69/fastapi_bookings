import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Room,
  RoomEvent,
  Track,
  type RemoteTrack,
  type RemoteTrackPublication,
  type RemoteParticipant,
  type DataPacket_Kind,
} from 'livekit-client'

import { apiClient } from '@/lib/api'
import { appendTranscriptDelta, type GPTLiveCaption } from '../gpt-live/protocol'
import type { GPTLiveVoiceState } from '../gpt-live/use-gpt-live'
import {
  executorCoordinator,
  registerAssistantRpcMethods,
  type RpcExecutionReceipt,
  type RpcRegistration,
} from './rpc'

export type LiveKitVoiceSessionResponse = {
  transport: 'livekit_gpt_live' | 'direct_gpt_live'
  livekit_url?: string
  token?: string
  session_id: string
  room_name?: string
  participant_identity?: string
  agent_name?: string
  expires_in?: number
  sdp?: string
}

export type UseLiveKitVoiceOptions = {
  conversationId: number | null
  onCaptionsChange: (captions: GPTLiveCaption[]) => void
  onError: (message: string) => void
  onNavigate?: (path: string) => void
  onRpcReceipt?: (receipt: RpcExecutionReceipt) => void
}

export type UseLiveKitVoiceResult = {
  voiceState: GPTLiveVoiceState
  captions: GPTLiveCaption[]
  isMuted: boolean
  audioDevices: MediaDeviceInfo[]
  activeAudioDeviceId: string | null
  lastRpcReceipt: RpcExecutionReceipt | null
  startVoice: (requestedConversationId?: number) => Promise<void>
  stopVoice: () => void
  toggleMute: () => Promise<void>
  switchAudioDevice: (deviceId: string) => Promise<void>
}

export function useLiveKitVoice({
  conversationId,
  onCaptionsChange,
  onError,
  onNavigate,
  onRpcReceipt,
}: UseLiveKitVoiceOptions): UseLiveKitVoiceResult {
  const [voiceState, setVoiceState] = useState<GPTLiveVoiceState>('idle')
  const [isMuted, setIsMuted] = useState(false)
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([])
  const [activeAudioDeviceId, setActiveAudioDeviceId] = useState<string | null>(null)
  const [lastRpcReceipt, setLastRpcReceipt] = useState<RpcExecutionReceipt | null>(null)

  const roomRef = useRef<Room | null>(null)
  const rpcRegistrationRef = useRef<RpcRegistration | null>(null)
  const remoteAudioElementsRef = useRef<HTMLAudioElement[]>([])
  const captionsRef = useRef<GPTLiveCaption[]>([])
  const connectionAttemptRef = useRef(0)
  const closingRef = useRef(false)
  const callbacksRef = useRef({ onCaptionsChange, onError, onNavigate, onRpcReceipt })
  callbacksRef.current = { onCaptionsChange, onError, onNavigate, onRpcReceipt }

  const refreshAudioDevices = useCallback(async () => {
    try {
      if (typeof navigator !== 'undefined' && navigator.mediaDevices?.enumerateDevices) {
        const devices = await navigator.mediaDevices.enumerateDevices()
        const inputs = devices.filter((d) => d.kind === 'audioinput')
        setAudioDevices(inputs)
      }
    } catch {
      // Device enumeration not available or denied
    }
  }, [])

  useEffect(() => {
    void refreshAudioDevices()
  }, [refreshAudioDevices])

  const cleanupAudioElements = useCallback(() => {
    for (const el of remoteAudioElementsRef.current) {
      try {
        el.pause()
        el.srcObject = null
        if (el.parentNode) {
          el.parentNode.removeChild(el)
        }
      } catch {
        // Ignored during cleanup
      }
    }
    remoteAudioElementsRef.current = []
  }, [])

  const releaseTransport = useCallback(() => {
    connectionAttemptRef.current += 1
    closingRef.current = false

    if (rpcRegistrationRef.current) {
      try {
        rpcRegistrationRef.current.unregister()
      } catch {
        // Ignored during release
      }
      rpcRegistrationRef.current = null
    }

    if (roomRef.current) {
      try {
        roomRef.current.disconnect()
      } catch {
        // Ignored during release
      }
      roomRef.current = null
    }

    cleanupAudioElements()
    executorCoordinator.releaseActiveExecutor()
    setIsMuted(false)
    setVoiceState('idle')
  }, [cleanupAudioElements])

  const startVoice = useCallback(
    async (requestedConversationId?: number) => {
      const activeConversationId = requestedConversationId ?? conversationId
      if (!activeConversationId || voiceState !== 'idle') return

      const connectionAttempt = connectionAttemptRef.current + 1
      connectionAttemptRef.current = connectionAttempt

      setVoiceState('connecting')
      closingRef.current = false
      captionsRef.current = []
      callbacksRef.current.onCaptionsChange([])

      try {
        // Request token and room dispatch from unified voice session endpoint
        const response = await apiClient.post<LiveKitVoiceSessionResponse>(
          `/api/admin/business-assistant/voice/conversations/${activeConversationId}/session`,
          {},
        )

        const isCurrentAttempt = () => connectionAttemptRef.current === connectionAttempt

        if (!isCurrentAttempt()) {
          return
        }

        if (!response.livekit_url || !response.token) {
          throw new Error('Server did not return LiveKit connection parameters.')
        }

        const room = new Room({
          adaptiveStream: false,
          dynacast: false,
          audioCaptureDefaults: {
            autoGainControl: true,
            echoCancellation: true,
            noiseSuppression: true,
          },
        })
        roomRef.current = room

        // Remote assistant audio track subscription
        room.on(
          RoomEvent.TrackSubscribed,
          (
            track: RemoteTrack,
            _publication: RemoteTrackPublication,
            _participant: RemoteParticipant,
          ) => {
            if (track.kind === Track.Kind.Audio) {
              const audioElement = track.attach()
              audioElement.autoplay = true
              document.body.appendChild(audioElement)
              remoteAudioElementsRef.current.push(audioElement)
            }
          },
        )

        room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
          track.detach()
        })

        // Live raw caption data channel receiver
        room.on(
          RoomEvent.DataReceived,
          (
            payload: Uint8Array,
            _participant?: RemoteParticipant,
            _kind?: DataPacket_Kind,
            _topic?: string,
          ) => {
            try {
              const text = new TextDecoder().decode(payload)
              const data = JSON.parse(text)
              if (
                data.type === 'session.input_transcript.delta' ||
                data.type === 'session.output_transcript.delta'
              ) {
                const updated = appendTranscriptDelta(captionsRef.current, data)
                if (updated !== captionsRef.current) {
                  captionsRef.current = updated
                  callbacksRef.current.onCaptionsChange(updated)
                }
              }
            } catch {
              // Ignore invalid packet
            }
          },
        )

        room.on(RoomEvent.Disconnected, () => {
          if (!closingRef.current) {
            setVoiceState('idle')
            cleanupAudioElements()
          }
        })

        // Connect room
        await room.connect(response.livekit_url, response.token)

        if (!isCurrentAttempt()) {
          room.disconnect()
          return
        }

        // Claim single-tab active executor lease for this session
        executorCoordinator.claimActiveExecutor()

        // Register Assistant RPC receiver
        rpcRegistrationRef.current = registerAssistantRpcMethods(room, {
          onNavigate: callbacksRef.current.onNavigate,
          expectedAgentName: response.agent_name,
          expectedAgentIdentity: response.agent_name,
          requireActiveExecutorLease: true,
          onReceipt: (receipt) => {
            setLastRpcReceipt(receipt)
            callbacksRef.current.onRpcReceipt?.(receipt)
          },
        })

        // Enable microphone
        await room.localParticipant.setMicrophoneEnabled(true)
        setIsMuted(false)
        setVoiceState('live')
        void refreshAudioDevices()
      } catch (err) {
        callbacksRef.current.onError(
          err instanceof Error ? err.message : 'LiveKit voice session failed to connect.',
        )
        releaseTransport()
      }
    },
    [conversationId, voiceState, refreshAudioDevices, cleanupAudioElements, releaseTransport],
  )

  const stopVoice = useCallback(() => {
    if (voiceState === 'idle' || closingRef.current) return
    closingRef.current = true
    setVoiceState('finalising')

    if (roomRef.current) {
      void roomRef.current.disconnect().finally(() => {
        releaseTransport()
      })
    } else {
      releaseTransport()
    }
  }, [voiceState, releaseTransport])

  const toggleMute = useCallback(async () => {
    const room = roomRef.current
    if (!room || voiceState !== 'live') return

    try {
      const nextMuted = !isMuted
      await room.localParticipant.setMicrophoneEnabled(!nextMuted)
      setIsMuted(nextMuted)
    } catch (e) {
      callbacksRef.current.onError(e instanceof Error ? e.message : 'Could not change microphone mute.')
    }
  }, [isMuted, voiceState])

  const switchAudioDevice = useCallback(
    async (deviceId: string) => {
      const room = roomRef.current
      if (!room) return

      try {
        await room.switchActiveDevice('audioinput', deviceId)
        setActiveAudioDeviceId(deviceId)
      } catch (e) {
        callbacksRef.current.onError(e instanceof Error ? e.message : 'Could not switch audio input device.')
      }
    },
    [],
  )

  useEffect(
    () => () => {
      releaseTransport()
    },
    [releaseTransport],
  )

  return {
    voiceState,
    captions: captionsRef.current,
    isMuted,
    audioDevices,
    activeAudioDeviceId,
    lastRpcReceipt,
    startVoice,
    stopVoice,
    toggleMute,
    switchAudioDevice,
  }
}
