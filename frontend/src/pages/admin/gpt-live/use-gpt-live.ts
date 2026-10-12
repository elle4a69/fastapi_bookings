import { useCallback, useEffect, useRef, useState } from 'react'

import { authenticatedAdminFetch, apiClient } from '@/lib/api'
import {
  formatRealtimeToolOutput,
  parseRealtimeToolCalls,
  type AgentActivityLog,
  createAgentActivityLog,
  MAX_CONSECUTIVE_TOOL_CALLS,
  shouldResetTurnToolQuota,
} from '../business-assistant/realtime-protocol'
import {
  executeRpcAction,
  executorCoordinator,
  type RpcExecutionReceipt,
  defaultLeaseManager,
} from '../business-assistant/rpc'
import { appendTranscriptDelta, type GPTLiveCaption } from './protocol'

export type GPTLiveVoiceState = 'idle' | 'connecting' | 'live' | 'finalising'

type SessionResponse = { session_id: string; sdp: string }

export type GPTLiveOptions = {
  conversationId: number | null
  onCaptionsChange: (captions: GPTLiveCaption[]) => void
  onError: (message: string) => void
  onNavigate?: (path: string) => void
  onRpcReceipt?: (receipt: RpcExecutionReceipt) => void
  onToolCallComplete?: (toolName: string, result: Record<string, unknown>) => void
  onActivityLog?: (log: AgentActivityLog) => void
}

const ICE_GATHERING_TIMEOUT_MS = 10_000

function waitForIceGatheringComplete(peerConnection: RTCPeerConnection): Promise<void> {
  if (peerConnection.iceGatheringState === 'complete') return Promise.resolve()

  return new Promise((resolve, reject) => {
    const cleanup = () => {
      window.clearTimeout(timeout)
      peerConnection.removeEventListener('icegatheringstatechange', onGatheringStateChange)
      peerConnection.removeEventListener('signalingstatechange', onSignalingStateChange)
    }
    const onGatheringStateChange = () => {
      if (peerConnection.iceGatheringState !== 'complete') return
      cleanup()
      resolve()
    }
    const onSignalingStateChange = () => {
      if (peerConnection.signalingState !== 'closed') return
      cleanup()
      reject(new Error('The voice connection closed before its WebRTC offer was ready.'))
    }
    const timeout = window.setTimeout(() => {
      cleanup()
      reject(new Error('The browser timed out while preparing the WebRTC voice connection.'))
    }, ICE_GATHERING_TIMEOUT_MS)

    peerConnection.addEventListener('icegatheringstatechange', onGatheringStateChange)
    peerConnection.addEventListener('signalingstatechange', onSignalingStateChange)
  })
}

export function useGPTLive({
  conversationId,
  onCaptionsChange,
  onError,
  onNavigate,
  onRpcReceipt,
  onToolCallComplete,
  onActivityLog,
}: GPTLiveOptions) {
  const [voiceState, setVoiceState] = useState<GPTLiveVoiceState>('idle')
  const [isMuted, setIsMuted] = useState(false)
  const [lastRpcReceipt, setLastRpcReceipt] = useState<RpcExecutionReceipt | null>(null)
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null)
  const dataChannelRef = useRef<RTCDataChannel | null>(null)
  const microphoneRef = useRef<MediaStream | null>(null)
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null)
  const finalisationTimerRef = useRef<number | null>(null)
  const closedRef = useRef(false)
  const closingRef = useRef(false)
  const connectionAttemptRef = useRef(0)
  const captionsRef = useRef<GPTLiveCaption[]>([])
  const responseInProgressRef = useRef(false)
  const pendingResponseCreateRef = useRef(false)
  const callbacksRef = useRef({ onCaptionsChange, onError, onNavigate, onRpcReceipt, onToolCallComplete, onActivityLog })
  callbacksRef.current = { onCaptionsChange, onError, onNavigate, onRpcReceipt, onToolCallComplete, onActivityLog }

  const emitActivityLog = useCallback(
    (
      type: AgentActivityLog['type'],
      title: string,
      options?: {
        details?: string
        payload?: unknown
        status?: AgentActivityLog['status']
        agentLabel?: string
        modelName?: string
      },
    ) => {
      const log = createAgentActivityLog(type, title, options)
      callbacksRef.current.onActivityLog?.(log)
      if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
        window.dispatchEvent(new CustomEvent('live-agent-activity', { detail: log }))
      }
    },
    [],
  )

  const clearFinalisationTimer = () => {
    if (finalisationTimerRef.current !== null) {
      window.clearTimeout(finalisationTimerRef.current)
      finalisationTimerRef.current = null
    }
  }

  const releaseTransport = useCallback(() => {
    // Invalidates any asynchronous start that is still waiting for microphone
    // access or the server's SDP answer. Those continuations must never add a
    // track or install an answer on a connection which Stop/unmount has closed.
    connectionAttemptRef.current += 1
    responseInProgressRef.current = false
    pendingResponseCreateRef.current = false
    clearFinalisationTimer()
    if (dataChannelRef.current) {
      try {
        dataChannelRef.current.onclose = null
        dataChannelRef.current.onerror = null
        dataChannelRef.current.onmessage = null
        dataChannelRef.current.close()
      } catch {
        // safe ignore
      }
      dataChannelRef.current = null
    }
    if (peerConnectionRef.current) {
      try {
        peerConnectionRef.current.onconnectionstatechange = null
        peerConnectionRef.current.oniceconnectionstatechange = null
        peerConnectionRef.current.ontrack = null
        peerConnectionRef.current.close()
      } catch {
        // safe ignore
      }
      peerConnectionRef.current = null
    }
    microphoneRef.current?.getTracks().forEach((track) => track.stop())
    microphoneRef.current = null
    if (remoteAudioRef.current) {
      remoteAudioRef.current.pause()
      remoteAudioRef.current.srcObject = null
      remoteAudioRef.current = null
    }
    executorCoordinator.releaseActiveExecutor()
    setIsMuted(false)
    setVoiceState('idle')
  }, [])

  const toggleMute = useCallback(async () => {
    const next = !isMuted
    if (microphoneRef.current) {
      microphoneRef.current.getAudioTracks().forEach((track) => {
        track.enabled = !next
      })
    }
    setIsMuted(next)
  }, [isMuted])

  const reportIncompleteFinalisation = useCallback((reason: string) => {
    if (closedRef.current || closingRef.current) return
    const lower = reason.toLowerCase()
    if (
      lower.includes('closing') ||
      lower.includes('unavailable while closing') ||
      lower.includes('disconnected while closing')
    ) {
      closedRef.current = true
      releaseTransport()
      return
    }
    emitActivityLog('ERROR', 'Voice Session Finalisation Error', {
      details: reason,
      payload: { reason },
      status: 'error',
      agentLabel: 'GPT-Live (Voice Front)',
      modelName: 'gpt-live-1',
    })
    callbacksRef.current.onError(`Voice session finalisation is incomplete: ${reason}`)
    closedRef.current = true
    releaseTransport()
  }, [emitActivityLog, releaseTransport])

  const startVoice = useCallback(async (requestedConversationId?: number) => {
    const activeConversationId = requestedConversationId ?? conversationId
    if (!activeConversationId || voiceState !== 'idle') return
    const connectionAttempt = connectionAttemptRef.current + 1
    connectionAttemptRef.current = connectionAttempt
    setVoiceState('connecting')
    closedRef.current = false
    closingRef.current = false
    responseInProgressRef.current = false
    pendingResponseCreateRef.current = false
    captionsRef.current = []
    callbacksRef.current.onCaptionsChange([])

    try {
      const peerConnection = new RTCPeerConnection()
      peerConnectionRef.current = peerConnection
      const microphone = await navigator.mediaDevices.getUserMedia({ audio: true })
      const isCurrentAttempt = () => (
        connectionAttemptRef.current === connectionAttempt
        && peerConnectionRef.current === peerConnection
        && peerConnection.signalingState !== 'closed'
      )
      if (!isCurrentAttempt()) {
        microphone.getTracks().forEach((track) => track.stop())
        return
      }
      microphoneRef.current = microphone
      microphone.getAudioTracks().forEach((track) => {
        track.enabled = true
      })
      setIsMuted(false)
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

      const handledCallIds = new Set<string>()
      let consecutiveToolCalls = 0
      let terminalActionInTurn = false
      const dataChannel = peerConnection.createDataChannel('oai-events')
      dataChannelRef.current = dataChannel
      dataChannel.onopen = () => {
        // Note: OpenAI Live API (gpt-live-1) configures parameters at session creation.
        // Sending session.update with input_audio_transcription: { model: 'whisper-1' } is rejected by the provider.
        emitActivityLog('DELEGATION', 'Session Configuration Initialized', {
          details: 'WebRTC data channel connected and ready.',
          status: 'success',
          agentLabel: 'GPT-Live (Voice Front)',
          modelName: 'gpt-live-1',
        })
      }
      dataChannel.onmessage = async ({ data }) => {
        if (typeof data !== 'string') return
        let event: Record<string, unknown>
        try {
          event = JSON.parse(data) as Record<string, unknown>
        } catch {
          return
        }

        if (shouldResetTurnToolQuota(event)) {
          consecutiveToolCalls = 0
          terminalActionInTurn = false
        }
        if (event.type === 'session.started' && !closingRef.current) {
          setVoiceState('live')
          return
        }
        if (event.type === 'session.closed') {
          closedRef.current = true
          responseInProgressRef.current = false
          pendingResponseCreateRef.current = false
          releaseTransport()
          return
        }

        if (event.type === 'response.created') {
          responseInProgressRef.current = true
          emitActivityLog('DELEGATION', 'Agent Response Created', {
            details: `Response ID: ${((event.response as Record<string, unknown>)?.id as string) || (event.response_id as string) || 'active'}`,
            payload: event,
            status: 'running',
            agentLabel: 'GPT-5.6-Terra (Reasoning Engine)',
            modelName: 'gpt-5.6-terra',
          })
        }

        if (event.type === 'response.output_item.added') {
          const outItem = (event.item as Record<string, unknown>) || {}
          emitActivityLog('DELEGATION', `Output Item Added: ${(outItem.type as string) || 'item'}`, {
            details: `Item ID: ${(outItem.id as string) || ''} (${(outItem.role as string) || ''})`,
            payload: event,
            status: 'info',
            agentLabel: 'GPT-5.6-Terra (Reasoning Engine)',
            modelName: 'gpt-5.6-terra',
          })
        }

        if (
          event.type === 'conversation.item.input_audio_transcription.completed' ||
          event.type === 'input_audio_transcription.completed'
        ) {
          consecutiveToolCalls = 0
          terminalActionInTurn = false
          const userTranscript =
            (typeof event.transcript === 'string' && event.transcript) ||
            (typeof event.text === 'string' && event.text) ||
            ''
          emitActivityLog('VOICE_IN', 'Voice Input Transcription', {
            details: userTranscript || 'Speech transcribed',
            payload: event,
            status: 'info',
            agentLabel: 'GPT-Live (Voice Front)',
            modelName: 'gpt-live-1',
          })
          const updated = appendTranscriptDelta(captionsRef.current, event)
          if (updated !== captionsRef.current) {
            captionsRef.current = updated
            callbacksRef.current.onCaptionsChange(updated)
          }
        }

        if (
          event.type === 'response.audio_transcript.delta' ||
          event.type === 'response.output_audio_transcript.delta'
        ) {
          const updated = appendTranscriptDelta(captionsRef.current, event)
          if (updated !== captionsRef.current) {
            captionsRef.current = updated
            callbacksRef.current.onCaptionsChange(updated)
          }
        }

        if (event.type === 'conversation.item.create' || event.type === 'conversation.item.created') {
          const item = (event.item as Record<string, unknown>) || {}
          if (item.role === 'user') {
            const content = Array.isArray(item.content)
              ? JSON.stringify(item.content)
              : typeof item.content === 'string'
                ? item.content
                : 'User message'
            emitActivityLog('USER_INPUT', 'User Turn Item', {
              details: content,
              payload: event,
              status: 'info',
              agentLabel: 'User / Client Input',
              modelName: 'client',
            })
          } else if (item.type === 'function_call_output') {
            emitActivityLog('TOOL_RESULT', `Tool Output Return [${(item.call_id as string) || ''}]`, {
              details: typeof item.output === 'string' ? item.output.slice(0, 200) : 'Output attached',
              payload: event,
              status: 'success',
              agentLabel: 'FastAPI Backend (Tool Runner)',
              modelName: 'python-tools',
            })
          }
        }

        if (
          event.type === 'response.reasoning.done' ||
          event.type === 'response.reasoning.delta' ||
          (typeof event.type === 'string' && event.type.includes('reasoning'))
        ) {
          emitActivityLog('REASONING_OUT', 'Model Reasoning', {
            details:
              (typeof event.delta === 'string' && event.delta) ||
              (typeof event.text === 'string' && event.text) ||
              'Intermediate reasoning step',
            payload: event,
            status: 'info',
            agentLabel: 'GPT-5.6-Terra (Reasoning Engine)',
            modelName: 'gpt-5.6-terra',
          })
        } else if (
          event.type === 'response.text.done' ||
          event.type === 'response.output_text.done' ||
          event.type === 'response.text.delta' ||
          event.type === 'response.output_text.delta'
        ) {
          const textContent =
            (typeof event.text === 'string' && event.text) ||
            (typeof event.output_text === 'string' && event.output_text) ||
            (typeof event.delta === 'string' && event.delta) ||
            ''
          emitActivityLog('REASONING_OUT', 'Agent Text Output', {
            details: textContent,
            payload: event,
            status: 'info',
            agentLabel: 'GPT-5.6-Terra (Reasoning Engine)',
            modelName: 'gpt-5.6-terra',
          })
          const updated = appendTranscriptDelta(captionsRef.current, event)
          if (updated !== captionsRef.current) {
            captionsRef.current = updated
            callbacksRef.current.onCaptionsChange(updated)
          }
        }

        if (
          event.type === 'response.audio_transcript.done' ||
          event.type === 'response.output_audio_transcript.done'
        ) {
          const outTranscript = (typeof event.transcript === 'string' && event.transcript) || ''
          emitActivityLog('VOICE_OUT', 'Model Voice Output', {
            details: outTranscript || 'Audio output playback completed',
            payload: event,
            status: 'success',
            agentLabel: 'GPT-Live (Voice Front)',
            modelName: 'gpt-live-1',
          })
          const updated = appendTranscriptDelta(captionsRef.current, event)
          if (updated !== captionsRef.current) {
            captionsRef.current = updated
            callbacksRef.current.onCaptionsChange(updated)
          }
        }

        if (event.type === 'response.done' || event.type === 'response.cancelled') {
          responseInProgressRef.current = false
          if (pendingResponseCreateRef.current && dataChannel.readyState === 'open') {
            pendingResponseCreateRef.current = false
            responseInProgressRef.current = true
            try {
              dataChannel.send(
                JSON.stringify({
                  type: 'response.create',
                  response: {
                    instructions:
                      'Speak the tool execution results directly and concisely to the user in Australian English.',
                  },
                }),
              )
              emitActivityLog('DELEGATION', 'Tool Output Dispatched -> response.create (deferred)', {
                details: 'Turn completed; prompted GPT-5.6-Terra reasoning engine to speak the tool results.',
                status: 'running',
                agentLabel: 'GPT-5.6-Terra (Reasoning Engine)',
                modelName: 'gpt-5.6-terra',
              })
            } catch (err) {
              console.warn('[GPT-Live] Failed to send deferred response.create', err)
            }
          }
        }

        if (event.type === 'error') {
          const errObj = (event.error as Record<string, unknown> | undefined) ?? {}
          const errorMessage =
            typeof errObj.message === 'string' && errObj.message
              ? errObj.message
              : 'OpenAI Realtime error'
          const errorCode =
            typeof errObj.code === 'string' && errObj.code
              ? errObj.code
              : 'openai_realtime_error'

          const isAlreadyInProgress =
            errorCode === 'response_already_in_progress' ||
            errorMessage.toLowerCase().includes('already in progress') ||
            errorMessage.toLowerCase().includes('a response is already')

          if (!isAlreadyInProgress) {
            responseInProgressRef.current = false
            pendingResponseCreateRef.current = false
          }

          console.error('[GPT-Live Error]', event.error)
          callbacksRef.current.onError(errorMessage)
          emitActivityLog('ERROR', `Realtime Error [${errorCode}]`, {
            details: errorMessage,
            payload: event.error,
            status: 'error',
          })

          const isBenignParam = errorCode === 'unknown_parameter' || errorMessage.toLowerCase().includes('input_audio_transcription') || isAlreadyInProgress
          if (activeConversationId && !isBenignParam) {
            void authenticatedAdminFetch(
              `/api/admin/business-assistant/conversations/${activeConversationId}/client-state`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  client_status: 'error',
                  webrtc_state: 'direct_gpt_live',
                  last_error: `[${errorCode}] ${errorMessage}`,
                  error: {
                    code: errorCode,
                    message: errorMessage,
                  },
                  metadata_json: {
                    code: errorCode,
                    error: event.error,
                  },
                }),
              },
            ).catch((postErr) => {
              console.error('[GPT-Live Error Post Failed]', postErr)
            })
          }
          return
        }

        // Handle tool calls from Realtime WebRTC data channel
        const toolCalls = parseRealtimeToolCalls(event)
        if (toolCalls.length > 0) {
          if (terminalActionInTurn) {
            for (const toolCall of toolCalls) {
              handledCallIds.add(toolCall.callId)
              if (dataChannel.readyState === 'open') {
                const skippedOutput = formatRealtimeToolOutput(toolCall.callId, {
                  status: 'completed',
                  message: 'Terminal action already executed for this turn. Concluding response.',
                })
                dataChannel.send(JSON.stringify(skippedOutput))
              }
            }
            return
          }

          if (consecutiveToolCalls >= MAX_CONSECUTIVE_TOOL_CALLS) {
            for (const toolCall of toolCalls) {
              handledCallIds.add(toolCall.callId)
              if (dataChannel.readyState === 'open') {
                const quotaOutput = formatRealtimeToolOutput(toolCall.callId, {
                  status: 'completed',
                  message: 'Turn tool quota reached. Please speak your answer to the user.',
                })
                dataChannel.send(JSON.stringify(quotaOutput))
              }
            }
            return
          }
          consecutiveToolCalls += 1

          let hasDispatchedAnyToolOutput = false
          for (const toolCall of toolCalls) {
            if (handledCallIds.has(toolCall.callId)) continue
            handledCallIds.add(toolCall.callId)
            emitActivityLog('TOOL_EXEC', `Tool Dispatch: ${toolCall.name}`, {
              details: JSON.stringify(toolCall.arguments).slice(0, 300),
              payload: { name: toolCall.name, callId: toolCall.callId, arguments: toolCall.arguments },
              status: 'running',
              agentLabel: 'FastAPI Backend (Tool Runner)',
              modelName: 'python-tools',
            })
            try {
              // 1. Dispatch client-side action in DOM / form adapters
              const clientReceipt = await executeRpcAction(
                toolCall.name,
                toolCall.arguments,
                {
                  callerIdentity: 'direct-gpt-live',
                  context: {
                    conversationId: activeConversationId,
                    onNavigate: callbacksRef.current.onNavigate,
                    activeLeaseToken: defaultLeaseManager.getActiveLease().token ?? undefined,
                  },
                },
              )
              setLastRpcReceipt(clientReceipt)
              callbacksRef.current.onRpcReceipt?.(clientReceipt)

              if (clientReceipt.status === 'rejected') {
                console.warn('[GPT-Live] Client RPC action rejected:', clientReceipt.action, clientReceipt.error)
              }

              // Dispatch global event for listeners (like OnboardingStatusDock, FieldPointerOverlay)
              if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
                window.dispatchEvent(
                  new CustomEvent('assistant-rpc:action', {
                    detail: { name: toolCall.name, arguments: toolCall.arguments, receipt: clientReceipt },
                  }),
                )
                if (toolCall.name === 'stage_fields' || toolCall.name === 'fill_fields') {
                  window.dispatchEvent(
                    new CustomEvent('assistant-rpc:fill-fields', {
                      detail: {
                        fields: (toolCall.arguments as Record<string, unknown>).fields || toolCall.arguments,
                        receipt: clientReceipt,
                      },
                    }),
                  )
                } else if (toolCall.name === 'save_form' || toolCall.name === 'commit_save') {
                  window.dispatchEvent(
                    new CustomEvent('assistant-rpc:save-form', {
                      detail: { receipt: clientReceipt },
                    }),
                  )
                }
              }

              // 2. Authoritative server execution via realtime tools endpoint
              let serverResult: Record<string, unknown> = clientReceipt as unknown as Record<string, unknown>
              if (activeConversationId) {
                const res = await authenticatedAdminFetch(
                  `/api/admin/business-assistant/conversations/${activeConversationId}/realtime/tools`,
                  {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      name: toolCall.name,
                      arguments: toolCall.arguments,
                    }),
                  },
                )
                if (res.ok) {
                  const sData = (await res.json()) as Record<string, unknown>
                  serverResult = (sData.result || sData) as Record<string, unknown>
                }
                callbacksRef.current.onToolCallComplete?.(toolCall.name, serverResult)
                if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
                  window.dispatchEvent(
                    new CustomEvent('assistant-tool:complete', {
                      detail: { name: toolCall.name, result: serverResult },
                    }),
                  )
                }
              }

              if (toolCall.name === 'navigate_route' || serverResult.terminal) {
                terminalActionInTurn = true
              }

              emitActivityLog('TOOL_RESULT', `Tool Result: ${toolCall.name}`, {
                details: JSON.stringify(serverResult).slice(0, 300),
                payload: serverResult,
                status: 'success',
                agentLabel: 'FastAPI Backend (Tool Runner)',
                modelName: 'python-tools',
              })

              // 3. Return tool output back to model via WebRTC data channel
              if (dataChannel.readyState === 'open') {
                const toolOutputEvent = formatRealtimeToolOutput(toolCall.callId, serverResult)
                dataChannel.send(JSON.stringify(toolOutputEvent))
                hasDispatchedAnyToolOutput = true
              }
            } catch (err) {
              emitActivityLog('ERROR', `Tool Execution Failed: ${toolCall.name}`, {
                details: err instanceof Error ? err.message : 'Tool execution failed',
                payload: { error: err },
                status: 'error',
                agentLabel: 'FastAPI Backend (Tool Runner)',
                modelName: 'python-tools',
              })
              if (dataChannel.readyState === 'open') {
                const errorOutput = formatRealtimeToolOutput(toolCall.callId, {
                  status: 'unavailable',
                  reason: err instanceof Error ? err.message : 'Tool execution failed',
                })
                dataChannel.send(JSON.stringify(errorOutput))
                hasDispatchedAnyToolOutput = true
              }
            }
          }

          if (hasDispatchedAnyToolOutput && dataChannel.readyState === 'open') {
            if (responseInProgressRef.current) {
              pendingResponseCreateRef.current = true
              emitActivityLog('DELEGATION', 'Tool Output Dispatched -> Pending response.create', {
                details: 'Tool outputs returned to data channel. Queued response.create awaiting active speech turn completion.',
                status: 'running',
                agentLabel: 'GPT-5.6-Terra (Reasoning Engine)',
                modelName: 'gpt-5.6-terra',
              })
            } else {
              pendingResponseCreateRef.current = false
              responseInProgressRef.current = true
              try {
                const instructions = terminalActionInTurn
                  ? 'The requested action or navigation has completed. Speak a concise confirmation to the user and conclude your turn without executing further tools.'
                  : 'Speak the tool execution results directly and concisely to the user in Australian English.'
                dataChannel.send(
                  JSON.stringify({
                    type: 'response.create',
                    response: {
                      instructions,
                    },
                  }),
                )
                emitActivityLog('DELEGATION', 'Tool Output Dispatched -> response.create', {
                  details: 'Signalled GPT-5.6-Terra reasoning engine to continue generating with returned tool outputs.',
                  status: 'running',
                  agentLabel: 'GPT-5.6-Terra (Reasoning Engine)',
                  modelName: 'gpt-5.6-terra',
                })
              } catch (err) {
                console.warn('[GPT-Live] Failed to send response.create', err)
              }
            }
          }
          return
        }

        const updated = appendTranscriptDelta(captionsRef.current, event)
        if (updated !== captionsRef.current) {
          captionsRef.current = updated
          callbacksRef.current.onCaptionsChange(updated)
        }
      }
      dataChannel.onclose = () => {
        if (!closedRef.current && !closingRef.current) {
          reportIncompleteFinalisation('the event channel disconnected before session.closed.')
        }
      }
      peerConnection.onconnectionstatechange = () => {
        if (
          ['disconnected', 'failed', 'closed'].includes(peerConnection.connectionState) &&
          !closedRef.current &&
          !closingRef.current
        ) {
          reportIncompleteFinalisation('the WebRTC transport disconnected before session.closed.')
        }
      }

      const offer = await peerConnection.createOffer()
      await peerConnection.setLocalDescription(offer)
      await waitForIceGatheringComplete(peerConnection)
      if (!isCurrentAttempt()) return
      const offerSdp = peerConnection.localDescription?.sdp
      if (!offerSdp) throw new Error('The browser did not produce a WebRTC SDP offer.')
      const response = await apiClient.post<SessionResponse>(
        `/api/admin/gpt-live/conversations/${activeConversationId}/sessions`,
        { sdp: offerSdp },
      )
      if (!isCurrentAttempt()) return
      await peerConnection.setRemoteDescription({ type: 'answer', sdp: response.sdp })
      // Claim single-tab active executor lease for this session
      executorCoordinator.claimActiveExecutor()
    } catch (error) {
      callbacksRef.current.onError(error instanceof Error ? error.message : 'Voice could not start.')
      closedRef.current = true
      releaseTransport()
    }
  }, [conversationId, releaseTransport, reportIncompleteFinalisation, voiceState])

  const stopVoice = useCallback(() => {
    if (voiceState === 'idle' || closingRef.current) return
    closingRef.current = true
    closedRef.current = true
    setVoiceState('finalising')
    clearFinalisationTimer()
    responseInProgressRef.current = false
    pendingResponseCreateRef.current = false

    // Cleanly close data channel without triggering error callbacks
    const dataChannel = dataChannelRef.current
    if (dataChannel) {
      try {
        dataChannel.onclose = null
        dataChannel.onerror = null
        dataChannel.onmessage = null
        if (dataChannel.readyState === 'open') {
          try {
            dataChannel.send(JSON.stringify({ type: 'session.close' }))
          } catch {
            // safe ignore
          }
        }
        dataChannel.close()
      } catch {
        // safe ignore
      }
      dataChannelRef.current = null
    }

    // Cleanly close WebRTC peer connection
    const pc = peerConnectionRef.current
    if (pc) {
      try {
        pc.onconnectionstatechange = null
        pc.oniceconnectionstatechange = null
        pc.ontrack = null
        pc.close()
      } catch {
        // safe ignore
      }
      peerConnectionRef.current = null
    }

    // Stop all microphone tracks immediately
    if (microphoneRef.current) {
      try {
        microphoneRef.current.getTracks().forEach((track) => track.stop())
      } catch {
        // safe ignore
      }
      microphoneRef.current = null
    }

    // Stop remote audio element
    if (remoteAudioRef.current) {
      try {
        remoteAudioRef.current.pause()
        remoteAudioRef.current.srcObject = null
      } catch {
        // safe ignore
      }
      remoteAudioRef.current = null
    }

    executorCoordinator.releaseActiveExecutor()
    setVoiceState('idle')

    emitActivityLog('VOICE_OUT', 'Voice Session Stopped', {
      details: 'Voice hardware and WebRTC connection released cleanly',
      status: 'info',
      agentLabel: 'GPT-Live (Voice Front)',
      modelName: 'gpt-live-1',
    })
  }, [clearFinalisationTimer, emitActivityLog, voiceState])

  useEffect(() => () => {
    closingRef.current = true
    closedRef.current = true
    releaseTransport()
  }, [releaseTransport])

  return { voiceState, captions: captionsRef.current, isMuted, toggleMute, lastRpcReceipt, startVoice, stopVoice }
}
