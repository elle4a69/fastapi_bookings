import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient, authenticatedAdminFetch } from '@/lib/api'
import { appendTranscriptDelta, type GPTLiveCaption } from '../gpt-live/protocol'
import type { GPTLiveVoiceState } from '../gpt-live/use-gpt-live'
import {
  executorCoordinator,
  executeRpcAction,
  type RpcExecutionReceipt,
  defaultLeaseManager,
} from './rpc'
import {
  type AgentActivityLog,
  createAgentActivityLog,
  parseRealtimeToolCalls,
  formatRealtimeToolOutput,
  MAX_CONSECUTIVE_TOOL_CALLS,
  shouldResetTurnToolQuota,
} from './realtime-protocol'

export type UseXAIGrokVoiceOptions = {
  conversationId: number | null
  onCaptionsChange: (captions: GPTLiveCaption[]) => void
  onError: (message: string) => void
  onNavigate?: (path: string) => void
  onRpcReceipt?: (receipt: RpcExecutionReceipt) => void
  onActivityLog?: (log: AgentActivityLog) => void
}

export type UseXAIGrokVoiceResult = {
  voiceState: GPTLiveVoiceState
  captions: GPTLiveCaption[]
  isMuted: boolean
  lastRpcReceipt: RpcExecutionReceipt | null
  startVoice: (requestedConversationId?: number) => Promise<void>
  stopVoice: () => void
  toggleMute: () => Promise<void>
}

function floatTo16BitPCM(float32Array: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(float32Array.length * 2)
  const view = new DataView(buffer)
  let offset = 0
  for (let i = 0; i < float32Array.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, float32Array[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return buffer
}

function base64EncodeAudio(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

function base64ToFloat32Array(base64: string): Float32Array {
  const binaryString = atob(base64)
  const bytes = new Uint8Array(binaryString.length)
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i)
  }
  const dataView = new DataView(bytes.buffer)
  const sampleCount = Math.floor(bytes.byteLength / 2)
  const float32 = new Float32Array(sampleCount)
  for (let i = 0; i < sampleCount; i++) {
    const int16 = dataView.getInt16(i * 2, true)
    float32[i] = int16 / 32768.0
  }
  return float32
}

export function useXAIGrokVoice({
  conversationId,
  onCaptionsChange,
  onError,
  onNavigate,
  onRpcReceipt,
  onActivityLog,
}: UseXAIGrokVoiceOptions): UseXAIGrokVoiceResult {
  const [voiceState, setVoiceState] = useState<GPTLiveVoiceState>('idle')
  const [isMuted, setIsMuted] = useState(false)
  const [lastRpcReceipt, setLastRpcReceipt] = useState<RpcExecutionReceipt | null>(null)

  const isMutedRef = useRef(false)
  isMutedRef.current = isMuted

  const wsRef = useRef<WebSocket | null>(null)
  const microphoneStreamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null)
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const scheduledEndTimeRef = useRef<number>(0)
  const captionsRef = useRef<GPTLiveCaption[]>([])
  const connectionAttemptRef = useRef(0)
  const closingRef = useRef(false)
  const inactivityTimedOutRef = useRef(false)
  const handledCallIdsRef = useRef<Set<string>>(new Set())
  const consecutiveToolCallsRef = useRef(0)
  const terminalActionInTurnRef = useRef(false)

  const callbacksRef = useRef({ onCaptionsChange, onError, onActivityLog, onNavigate, onRpcReceipt })
  callbacksRef.current = { onCaptionsChange, onError, onActivityLog, onNavigate, onRpcReceipt }

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

  const releaseTransport = useCallback(() => {
    connectionAttemptRef.current += 1

    if (wsRef.current) {
      try {
        wsRef.current.onclose = null
        wsRef.current.onerror = null
        wsRef.current.onmessage = null
        if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
          wsRef.current.close(1000, 'Session stopped')
        }
      } catch {
        // safe ignore
      }
      wsRef.current = null
    }

    if (scriptProcessorRef.current) {
      try {
        scriptProcessorRef.current.disconnect()
      } catch {
        // safe ignore
      }
      scriptProcessorRef.current = null
    }

    if (sourceNodeRef.current) {
      try {
        sourceNodeRef.current.disconnect()
      } catch {
        // safe ignore
      }
      sourceNodeRef.current = null
    }

    if (microphoneStreamRef.current) {
      try {
        microphoneStreamRef.current.getTracks().forEach((t) => t.stop())
      } catch {
        // safe ignore
      }
      microphoneStreamRef.current = null
    }

    if (audioContextRef.current) {
      try {
        void audioContextRef.current.close()
      } catch {
        // safe ignore
      }
      audioContextRef.current = null
    }

    scheduledEndTimeRef.current = 0
    executorCoordinator.releaseActiveExecutor()
    setIsMuted(false)
    setVoiceState('idle')
  }, [])

  const playPcmChunk = useCallback((float32: Float32Array) => {
    try {
      if (!audioContextRef.current) {
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
        audioContextRef.current = new AudioCtx({ sampleRate: 24000 })
      }
      const audioCtx = audioContextRef.current
      if (audioCtx.state === 'suspended') {
        void audioCtx.resume()
      }

      const buffer = audioCtx.createBuffer(1, float32.length, 24000)
      buffer.getChannelData(0).set(float32)
      const source = audioCtx.createBufferSource()
      source.buffer = buffer
      source.connect(audioCtx.destination)

      const currentTime = audioCtx.currentTime
      if (scheduledEndTimeRef.current < currentTime) {
        scheduledEndTimeRef.current = currentTime
      }
      source.start(scheduledEndTimeRef.current)
      scheduledEndTimeRef.current += buffer.duration
    } catch (err) {
      console.warn('[xAI Grok Voice] Audio chunk playback error:', err)
    }
  }, [])

  const startVoice = useCallback(
    async (requestedConversationId?: number) => {
      const activeConversationId = requestedConversationId ?? conversationId
      if (!activeConversationId || voiceState !== 'idle') return

      const connectionAttempt = connectionAttemptRef.current + 1
      connectionAttemptRef.current = connectionAttempt

      setVoiceState('connecting')
      closingRef.current = false
      inactivityTimedOutRef.current = false
      captionsRef.current = []
      handledCallIdsRef.current.clear()
      callbacksRef.current.onCaptionsChange([])

      emitActivityLog('VOICE_IN', 'Grok Voice Session Initializing', {
        details: 'Minting xAI Realtime session and negotiating WebSocket transport',
        status: 'running',
        agentLabel: 'xAI Grok Voice (grok-voice-think-fast-2.0)',
        modelName: 'grok-voice-think-fast-2.0',
      })

      try {
        // 1. Get session info from backend
        const sessionInfo = await apiClient.post<{
          transport: string
          session_id: string
          livekit_url?: string
          token?: string
          agent_name?: string
          endpoint?: string
        }>(`/api/admin/business-assistant/voice/conversations/${activeConversationId}/session`, {
          transport: 'xai_grok_voice',
        })

        if (connectionAttemptRef.current !== connectionAttempt) return

        // 2. Fetch session configuration (instructions and tools)
        const sessionConfig = await apiClient
          .get<{
            instructions: string
            tools: Array<{
              type: string
              name: string
              description?: string
              parameters?: Record<string, unknown>
            }>
          }>(`/api/admin/business-assistant/conversations/${activeConversationId}/realtime/session`)
          .catch(() => null)

        if (connectionAttemptRef.current !== connectionAttempt) return

        // 3. Determine WebSocket URL (relay or direct)
        let wsUrl = sessionInfo.endpoint || '/api/admin/business-assistant/voice/realtime/xai-ws'
        if (wsUrl.startsWith('/')) {
          const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
          wsUrl = `${protocol}//${window.location.host}${wsUrl}?conversation_id=${activeConversationId}`
        }

        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = async () => {
          if (connectionAttemptRef.current !== connectionAttempt) {
            ws.close()
            return
          }

          // Enable Server Voice Activity Detection (VAD) and attach operational tools on xAI Realtime session
          try {
            const sessionPayload: Record<string, unknown> = {
              turn_detection: {
                type: 'server_vad',
              },
            }
            if (sessionConfig?.instructions) {
              sessionPayload.instructions = sessionConfig.instructions
            }
            if (sessionConfig?.tools && sessionConfig.tools.length > 0) {
              sessionPayload.tools = sessionConfig.tools
              sessionPayload.tool_choice = 'auto'
            }
            ws.send(
              JSON.stringify({
                type: 'session.update',
                session: sessionPayload,
              }),
            )
            emitActivityLog('DELEGATION', 'xAI Realtime Session Configured', {
              details: `Attached ${sessionConfig?.tools?.length ?? 0} operational tools to Grok voice session.`,
              status: 'success',
              agentLabel: 'xAI Grok Voice (grok-voice-think-fast-2.0)',
              modelName: 'grok-voice-think-fast-2.0',
            })
          } catch (e) {
            console.warn('[xAI Grok Voice] Failed to send session.update', e)
          }

          setVoiceState('live')
          executorCoordinator.claimActiveExecutor()

          emitActivityLog('VOICE_IN', 'Grok Voice Realtime Connected', {
            details: `Agent: ${sessionInfo.agent_name || 'agent_YosGQC2yvTXwpdi7'} | Engine: grok-voice-think-fast-2.0`,
            status: 'success',
            agentLabel: 'xAI Grok Voice (grok-voice-think-fast-2.0)',
            modelName: 'grok-voice-think-fast-2.0',
          })

          // Setup Microphone capture
          try {
            const stream = await navigator.mediaDevices.getUserMedia({
              audio: {
                channelCount: 1,
                sampleRate: 24000,
                echoCancellation: true,
                noiseSuppression: true,
              },
            })
            if (connectionAttemptRef.current !== connectionAttempt) {
              stream.getTracks().forEach((t) => t.stop())
              return
            }
            microphoneStreamRef.current = stream

            const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
            const audioCtx = new AudioCtx({ sampleRate: 24000 })
            audioContextRef.current = audioCtx

            const source = audioCtx.createMediaStreamSource(stream)
            sourceNodeRef.current = source

            const processor = audioCtx.createScriptProcessor(4096, 1, 1)
            scriptProcessorRef.current = processor

            processor.onaudioprocess = (e) => {
              if (isMutedRef.current || ws.readyState !== WebSocket.OPEN) return
              const inputData = e.inputBuffer.getChannelData(0)
              const pcm16 = floatTo16BitPCM(inputData)
              const base64Audio = base64EncodeAudio(pcm16)

              ws.send(
                JSON.stringify({
                  type: 'input_audio_buffer.append',
                  audio: base64Audio,
                }),
              )
            }

            source.connect(processor)
            processor.connect(audioCtx.destination)
          } catch (micErr) {
            callbacksRef.current.onError(
              micErr instanceof Error ? micErr.message : 'Microphone access denied for Grok voice',
            )
          }
        }

        ws.onmessage = async (event) => {
          if (typeof event.data !== 'string') return
          try {
            const data = JSON.parse(event.data) as Record<string, unknown>

            if (shouldResetTurnToolQuota(data)) {
              consecutiveToolCallsRef.current = 0
              terminalActionInTurnRef.current = false
            }

            // Handle tool calls from Realtime WebSocket
            const toolCalls = parseRealtimeToolCalls(data)
            if (toolCalls.length > 0) {
              if (terminalActionInTurnRef.current) {
                // Cascade breaker: Terminal navigation or action already completed in this turn
                for (const toolCall of toolCalls) {
                  handledCallIdsRef.current.add(toolCall.callId)
                  if (ws.readyState === WebSocket.OPEN) {
                    const skippedOutput = formatRealtimeToolOutput(toolCall.callId, {
                      status: 'completed',
                      message: 'Terminal action already executed for this turn. Concluding response.',
                    })
                    ws.send(JSON.stringify(skippedOutput))
                  }
                }
                return
              }

              if (consecutiveToolCallsRef.current >= MAX_CONSECUTIVE_TOOL_CALLS) {
                // Turn quota cap: max consecutive tool execution rounds per turn
                for (const toolCall of toolCalls) {
                  handledCallIdsRef.current.add(toolCall.callId)
                  if (ws.readyState === WebSocket.OPEN) {
                    const quotaOutput = formatRealtimeToolOutput(toolCall.callId, {
                      status: 'completed',
                      message: 'Turn tool quota reached. Please speak your answer to the user.',
                    })
                    ws.send(JSON.stringify(quotaOutput))
                  }
                }
                return
              }
              consecutiveToolCallsRef.current += 1

              let hasDispatchedAnyToolOutput = false
              for (const toolCall of toolCalls) {
                if (handledCallIdsRef.current.has(toolCall.callId)) continue
                handledCallIdsRef.current.add(toolCall.callId)

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
                      callerIdentity: 'xai-grok-voice',
                      context: {
                        conversationId: activeConversationId,
                        onNavigate: callbacksRef.current.onNavigate,
                        activeLeaseToken: defaultLeaseManager.getActiveLease().token ?? undefined,
                      },
                    },
                  )
                  if (clientReceipt) {
                    setLastRpcReceipt(clientReceipt)
                    callbacksRef.current.onRpcReceipt?.(clientReceipt)

                    if (clientReceipt.status === 'rejected') {
                      console.warn('[xAI Grok Voice] Client RPC action rejected:', clientReceipt.action, clientReceipt.error)
                      emitActivityLog('ERROR', `Client Action Rejected: ${clientReceipt.action}`, {
                        details: clientReceipt.error || 'Client action rejected',
                        payload: clientReceipt,
                        status: 'error',
                        agentLabel: 'xAI Grok Voice (RPC Client)',
                        modelName: 'grok-voice-think-fast-2.0',
                      })
                    }

                    // Dispatch global event for UI listeners (e.g. OnboardingStatusDock, TakeoverPointer)
                    if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
                      window.dispatchEvent(
                        new CustomEvent('assistant-rpc:action', {
                          detail: { name: toolCall.name, arguments: toolCall.arguments, receipt: clientReceipt },
                        }),
                      )
                    }
                  }

                  // 2. Dispatch to backend authoritative tool runner
                  const serverResponse = await authenticatedAdminFetch(
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

                  if (!serverResponse.ok) {
                    const errText = await serverResponse.text()
                    throw new Error(`Tool execution rejected [${serverResponse.status}]: ${errText}`)
                  }

                  const serverResult = (await serverResponse.json()) as Record<string, unknown>
                  if (toolCall.name === 'navigate_route' || serverResult.terminal) {
                    terminalActionInTurnRef.current = true
                  }

                  emitActivityLog('TOOL_RESULT', `Tool Finished: ${toolCall.name}`, {
                    details: JSON.stringify(serverResult).slice(0, 300),
                    payload: serverResult,
                    status: 'success',
                    agentLabel: 'FastAPI Backend (Tool Runner)',
                    modelName: 'python-tools',
                  })

                  // 3. Return tool output back to model via WebSocket
                  if (ws.readyState === WebSocket.OPEN) {
                    const toolOutputEvent = formatRealtimeToolOutput(toolCall.callId, serverResult)
                    ws.send(JSON.stringify(toolOutputEvent))
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
                  if (ws.readyState === WebSocket.OPEN) {
                    const errorOutput = formatRealtimeToolOutput(toolCall.callId, {
                      status: 'unavailable',
                      reason: err instanceof Error ? err.message : 'Tool execution failed',
                    })
                    ws.send(JSON.stringify(errorOutput))
                    hasDispatchedAnyToolOutput = true
                  }
                }
              }

              if (hasDispatchedAnyToolOutput && ws.readyState === WebSocket.OPEN) {
                try {
                  ws.send(JSON.stringify({ type: 'response.create' }))
                  emitActivityLog('DELEGATION', 'Tool Output Dispatched -> response.create', {
                    details: 'Signalled xAI Grok voice engine to continue generating with returned tool outputs.',
                    status: 'running',
                    agentLabel: 'xAI Grok Voice (grok-voice-think-fast-2.0)',
                    modelName: 'grok-voice-think-fast-2.0',
                  })
                } catch (err) {
                  console.warn('[xAI Grok Voice] Failed to send response.create', err)
                }
              }
              return
            }

            // Handle audio delta playback
            if (
              data.type === 'response.output_audio.delta' ||
              data.type === 'response.audio.delta'
            ) {
              const delta = (data.delta as string) || (data.audio as string) || ''
              if (delta) {
                const float32 = base64ToFloat32Array(delta)
                playPcmChunk(float32)
              }
            }

            // Handle streaming output transcript
            if (
              data.type === 'response.output_audio_transcript.delta' ||
              data.type === 'response.audio_transcript.delta'
            ) {
              const updated = appendTranscriptDelta(captionsRef.current, data)
              if (updated !== captionsRef.current) {
                captionsRef.current = updated
                callbacksRef.current.onCaptionsChange(updated)
              }
            }

            // Handle input transcription
            if (
              data.type === 'conversation.item.input_audio_transcription.completed' ||
              data.type === 'input_audio_transcription.completed'
            ) {
              const userTranscript =
                (typeof data.transcript === 'string' && data.transcript) ||
                (typeof data.text === 'string' && data.text) ||
                ''
              consecutiveToolCallsRef.current = 0
              terminalActionInTurnRef.current = false
              emitActivityLog('VOICE_IN', 'User Voice Input', {
                details: userTranscript,
                status: 'info',
                agentLabel: 'User Microphone',
                modelName: 'client-audio',
              })
              const updated = appendTranscriptDelta(captionsRef.current, data)
              if (updated !== captionsRef.current) {
                captionsRef.current = updated
                callbacksRef.current.onCaptionsChange(updated)
              }
            }

            // Handle server/relay error events
            if (data.type === 'error') {
              console.error('[xAI Grok Voice] WebSocket protocol error:', data)
              const message =
                typeof data.message === 'string'
                  ? data.message
                  : typeof data.error === 'object' && data.error && 'message' in (data.error as Record<string, unknown>)
                  ? String((data.error as Record<string, unknown>).message)
                  : 'Protocol error received from xAI Realtime service.'

              const isTimeout =
                message.toLowerCase().includes('inactivity') ||
                message.toLowerCase().includes('timed out')

              if (isTimeout) {
                inactivityTimedOutRef.current = true
                emitActivityLog('VOICE_OUT', 'Grok Voice Inactivity Timeout', {
                  details: 'Voice session timed out due to inactivity.',
                  status: 'info',
                  agentLabel: 'xAI Grok Voice (grok-voice-think-fast-2.0)',
                  modelName: 'grok-voice-think-fast-2.0',
                })
                setVoiceState('idle')
                releaseTransport()
                return
              }

              emitActivityLog('ERROR', 'Grok Voice Error', {
                details: message,
                status: 'error',
                agentLabel: 'xAI Grok Voice (grok-voice-think-fast-2.0)',
                modelName: 'grok-voice-think-fast-2.0',
              })
              callbacksRef.current.onError(`xAI Voice error: ${message}`)
            }

            if (data.type === 'response.done') {
              emitActivityLog('VOICE_OUT', 'Grok Turn Completed', {
                details: 'Speech response finished',
                status: 'success',
                agentLabel: 'xAI Grok Voice (grok-voice-think-fast-2.0)',
                modelName: 'grok-voice-think-fast-2.0',
              })
            }
          } catch {
            // safe parse ignore
          }
        }

        ws.onerror = (event) => {
          console.error('[xAI Grok Voice] WebSocket connection error:', event)
          if (closingRef.current || inactivityTimedOutRef.current) return
          emitActivityLog('ERROR', 'Grok Voice Network Error', {
            details: 'WebSocket transport encountered an unexpected connection error.',
            status: 'error',
            agentLabel: 'xAI Grok Voice (grok-voice-think-fast-2.0)',
            modelName: 'grok-voice-think-fast-2.0',
          })
          callbacksRef.current.onError('xAI Realtime WebSocket connection error.')
        }

        ws.onclose = (event) => {
          console.warn('[xAI Grok Voice] WebSocket closed:', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
          })
          const isCleanClose =
            event.code === 1000 ||
            event.code === 1001 ||
            event.code === 1005 ||
            closingRef.current ||
            inactivityTimedOutRef.current

          if (isCleanClose) {
            emitActivityLog('VOICE_OUT', 'Grok Voice Session Closed', {
              details: inactivityTimedOutRef.current
                ? 'Voice session ended after inactivity timeout'
                : 'Voice connection closed normally',
              status: 'info',
              agentLabel: 'xAI Grok Voice (grok-voice-think-fast-2.0)',
              modelName: 'grok-voice-think-fast-2.0',
            })
            setVoiceState('idle')
            releaseTransport()
            return
          }

          const reasonText = event.reason ? ` (${event.reason})` : ''
          const details = `Voice connection closed (code ${event.code}${reasonText})`
          emitActivityLog('ERROR', 'Grok Voice Connection Closed', {
            details,
            status: 'error',
            agentLabel: 'xAI Grok Voice (grok-voice-think-fast-2.0)',
            modelName: 'grok-voice-think-fast-2.0',
          })
          callbacksRef.current.onError(`Voice connection closed: ${details}`)
          setVoiceState('idle')
          releaseTransport()
        }
      } catch (err) {
        callbacksRef.current.onError(
          err instanceof Error ? err.message : 'Failed to connect xAI Grok Voice session',
        )
        releaseTransport()
      }
    },
    [conversationId, voiceState, emitActivityLog, playPcmChunk, releaseTransport],
  )

  const stopVoice = useCallback(() => {
    if (voiceState === 'idle' || closingRef.current) return
    closingRef.current = true
    setVoiceState('finalising')

    emitActivityLog('VOICE_OUT', 'Grok Voice Session Stopped', {
      details: 'WebSocket and audio context released',
      status: 'info',
      agentLabel: 'xAI Grok Voice (grok-voice-think-fast-2.0)',
      modelName: 'grok-voice-think-fast-2.0',
    })

    releaseTransport()
  }, [voiceState, releaseTransport, emitActivityLog])

  const toggleMute = useCallback(async () => {
    const next = !isMuted
    if (microphoneStreamRef.current) {
      microphoneStreamRef.current.getAudioTracks().forEach((track) => {
        track.enabled = !next
      })
    }
    setIsMuted(next)
  }, [isMuted])

  useEffect(() => () => {
    closingRef.current = true
    releaseTransport()
  }, [releaseTransport])

  return {
    voiceState,
    captions: captionsRef.current,
    isMuted,
    lastRpcReceipt,
    startVoice,
    stopVoice,
    toggleMute,
  }
}
