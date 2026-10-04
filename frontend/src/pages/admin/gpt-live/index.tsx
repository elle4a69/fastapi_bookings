import { useState } from 'react'
import { LoaderCircle, Mic, PhoneOff, Volume2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { apiClient, toUserFacingApiError } from '@/lib/api'

import { formatCaptionInterval, type GPTLiveCaption } from './protocol'
import { useGPTLive } from './use-gpt-live'

type Conversation = { id: number }

export default function GPTLivePage() {
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [captions, setCaptions] = useState<GPTLiveCaption[]>([])
  const [error, setError] = useState<string | null>(null)
  const [creatingConversation, setCreatingConversation] = useState(false)
  const { voiceState, startVoice, stopVoice } = useGPTLive({
    conversationId,
    onCaptionsChange: setCaptions,
    onError: setError,
  })

  const begin = async () => {
    setError(null)
    let nextConversationId = conversationId
    if (!nextConversationId) {
      setCreatingConversation(true)
      try {
        const conversation = await apiClient.post<Conversation>(
          '/api/admin/business-assistant/conversations',
          { title: 'GPT-Live voice session' },
        )
        nextConversationId = conversation.id
        setConversationId(nextConversationId)
      } catch (requestError) {
        setError(toUserFacingApiError(requestError, 'Could not prepare a private voice conversation.').message)
        return
      } finally {
        setCreatingConversation(false)
      }
    }
    await startVoice(nextConversationId)
  }

  const canStart = voiceState === 'idle' && !creatingConversation
  return (
    <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-8" aria-label="GPT-Live Business Assistant">
      <section className="rounded-lg border bg-card p-5 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold">Private Business Assistant voice</h1>
            <p className="mt-1 text-sm text-muted-foreground">Speak naturally. Captions are shown by their session timing, not forced into chat turns.</p>
          </div>
          {canStart ? (
            <Button type="button" onClick={() => void begin()} disabled={creatingConversation}>
              {creatingConversation ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Mic className="mr-2 h-4 w-4" />}
              Start voice
            </Button>
          ) : (
            <Button type="button" variant="outline" onClick={stopVoice} disabled={voiceState === 'finalising'}>
              {voiceState === 'finalising' ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <PhoneOff className="mr-2 h-4 w-4" />}
              {voiceState === 'finalising' ? 'Finalising…' : 'End voice'}
            </Button>
          )}
        </div>
        {voiceState !== 'idle' && (
          <p className="mt-4 flex items-center gap-2 text-sm text-primary" role="status">
            <Volume2 className="h-4 w-4" />
            {voiceState === 'connecting' ? 'Connecting microphone and waiting for the voice session to start…' : voiceState === 'finalising' ? 'Waiting for final session confirmation…' : 'Voice is live.'}
          </p>
        )}
        {error && <p className="mt-4 rounded border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive" role="alert">{error}</p>}
      </section>

      <section className="rounded-lg border bg-card p-5" aria-live="polite" aria-label="Live captions">
        <h2 className="font-semibold">Live captions</h2>
        {captions.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">Captions will appear when speech is transcribed.</p>
        ) : (
          <ol className="mt-4 space-y-3">
            {captions.map((caption, index) => (
              <li key={`${caption.speaker}-${caption.startMs}-${caption.endMs}-${index}`} className="rounded border p-3 text-sm">
                <div className="mb-1 flex gap-2 text-xs text-muted-foreground"><span className="font-medium">{caption.speaker === 'user' ? 'You' : 'Assistant'}</span><span>{formatCaptionInterval(caption.startMs, caption.endMs)}</span></div>
                <p className="whitespace-pre-wrap">{caption.text}</p>
              </li>
            ))}
          </ol>
        )}
      </section>
    </main>
  )
}
