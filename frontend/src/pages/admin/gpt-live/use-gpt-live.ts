import { useCallback, useEffect, useRef, useState } from 'react'

import { apiClient } from '@/lib/api'

import { appendTranscriptDelta, type GPTLiveCaption } from './protocol'

export type GPTLiveVoiceState = 'idle' | 'connecting' | 'live' | 'finalising'

type SessionResponse = { session_id: string; sdp: string }

type GPTLiveOptions = {
  conversationId: number | null
  onCaptionsChange: (captions: GPTLiveCaption[]) => void
  onError: (message: string) => void
}

const FINALISATION_TIMEOUT_MS = 10_000

export function useGPTLive({ conversationId, onCaptionsChange, onError }: GPTLiveOptions) {
  const [voiceState, setVoiceState] = useState<GPTLiveVoiceState>('idle')
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null)
  const dataChannelRef = useRef<RTCDataChannel | null>(null)
  const microphoneRef = useRef<MediaStream | null>(null)
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null)
  const finalisationTimerRef = useRef<number | null>(null)
  const closedRef = useRef(false)
  const closingRef = useRef(false)
  const captionsRef = useRef<GPTLiveCaption[]>([])
  const callbacksRef = useRef({ onCaptionsChange, onError })
  callbacksRef.current = { onCaptionsChange, onError }

  const clearFinalisationTimer = () => {
    if (finalisationTimerRef.current !== null) {
      window.clearTimeout(finalisationTimerRef.current)
      finalisationTimerRef.current = null
    }
  }

  const releaseTransport = useCallback(() => {
    clearFinalisationTimer()
    dataChannelRef.current?.close()
    dataChannelRef.current = null
    peerConnectionRef.current?.close()
    peerConnectionRef.current = null
    microphoneRef.current?.getTracks().forEach((track) => track.stop())
    microphoneRef.current = null
    if (remoteAudioRef.current) {
      remoteAudioRef.current.pause()
      remoteAudioRef.current.srcObject = null
      remoteAudioRef.current = null
    }
    setVoiceState('idle')
  }, [])

  const reportIncompleteFinalisation = useCallback((reason: string) => {
    if (closedRef.current) return
    callbacksRef.current.onError(`Voice session finalisation is incomplete: ${reason}`)
    closedRef.current = true
    releaseTransport()
  }, [releaseTransport])

  const startVoice = useCallback(async (requestedConversationId?: number) => {
    const activeConversationId = requestedConversationId ?? conversationId
    if (!activeConversationId || voiceState !== 'idle') return
    setVoiceState('connecting')
    closedRef.current = false
    closingRef.current = false
    captionsRef.current = []
    callbacksRef.current.onCaptionsChange([])

    try {
      const peerConnection = new RTCPeerConnection()
      peerConnectionRef.current = peerConnection
      const microphone = await navigator.mediaDevices.getUserMedia({ audio: true })
      microphoneRef.current = microphone
      microphone.getTracks().forEach((track) => peerConnection.addTrack(track, microphone))

      const remoteAudio = new Audio()
      remoteAudio.autoplay = true
      remoteAudioRef.current = remoteAudio
      peerConnection.ontrack = ({ streams }) => {
        remoteAudio.srcObject = streams[0] ?? null
        void remoteAudio.play().catch(() => {
          callbacksRef.current.onError('Remote voice audio needs browser playback permission.')
        })
      }

      const dataChannel = peerConnection.createDataChannel('oai-events')
      dataChannelRef.current = dataChannel
      dataChannel.onmessage = ({ data }) => {
        if (typeof data !== 'string') return
        let event: Record<string, unknown>
        try {
          event = JSON.parse(data) as Record<string, unknown>
        } catch {
          return
        }
        if (event.type === 'session.started' && !closingRef.current) {
          setVoiceState('live')
          return
        }
        if (event.type === 'session.closed') {
          closedRef.current = true
          releaseTransport()
          return
        }
        const updated = appendTranscriptDelta(captionsRef.current, event)
        if (updated !== captionsRef.current) {
          captionsRef.current = updated
          callbacksRef.current.onCaptionsChange(updated)
        }
      }
      dataChannel.onclose = () => {
        if (!closedRef.current) reportIncompleteFinalisation('the event channel disconnected before session.closed.')
      }
      peerConnection.onconnectionstatechange = () => {
        if (['disconnected', 'failed', 'closed'].includes(peerConnection.connectionState) && !closedRef.current) {
          reportIncompleteFinalisation('the WebRTC transport disconnected before session.closed.')
        }
      }

      const offer = await peerConnection.createOffer()
      await peerConnection.setLocalDescription(offer)
      if (!offer.sdp) throw new Error('The browser did not produce a WebRTC SDP offer.')
      const response = await apiClient.post<SessionResponse>(
        `/api/admin/gpt-live/conversations/${activeConversationId}/sessions`,
        { sdp: offer.sdp },
      )
      await peerConnection.setRemoteDescription({ type: 'answer', sdp: response.sdp })
      // GPT-Live starts from the creation request. Do not send a second startup configuration.
    } catch (error) {
      callbacksRef.current.onError(error instanceof Error ? error.message : 'Voice could not start.')
      closedRef.current = true
      releaseTransport()
    }
  }, [conversationId, releaseTransport, reportIncompleteFinalisation, voiceState])

  const stopVoice = useCallback(() => {
    if (voiceState === 'idle' || closingRef.current) return
    closingRef.current = true
    setVoiceState('finalising')
    const dataChannel = dataChannelRef.current
    if (!dataChannel || dataChannel.readyState !== 'open') {
      reportIncompleteFinalisation('the event channel was unavailable while closing.')
      return
    }
    try {
      dataChannel.send(JSON.stringify({ type: 'session.close' }))
    } catch {
      reportIncompleteFinalisation('the event channel disconnected while closing.')
      return
    }
    finalisationTimerRef.current = window.setTimeout(() => {
      reportIncompleteFinalisation('timed out waiting for session.closed.')
    }, FINALISATION_TIMEOUT_MS)
  }, [reportIncompleteFinalisation, voiceState])

  useEffect(() => () => {
    closedRef.current = true
    releaseTransport()
  }, [releaseTransport])

  return { voiceState, captions: captionsRef.current, startVoice, stopVoice }
}
