import { formatCaptionInterval, type GPTLiveCaption } from './protocol'

export function GPTLiveCaptionTimeline({
  captions,
  className = '',
}: {
  captions: GPTLiveCaption[]
  className?: string
}) {
  return (
    <section
      className={`rounded-lg border bg-card p-3 ${className}`}
      aria-live="polite"
      aria-label="Live voice captions"
      data-testid="gpt-live-caption-timeline"
    >
      <h3 className="text-sm font-semibold">Live captions</h3>
      {captions.length === 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Captions will appear when speech is transcribed.
        </p>
      ) : (
        <ol className="mt-3 space-y-2">
          {captions.map((caption, index) => (
            <li
              key={`${caption.speaker}-${caption.startMs}-${caption.endMs}-${index}`}
              className="rounded border p-2 text-sm"
            >
              <div className="mb-1 flex gap-2 text-xs text-muted-foreground">
                <span className="font-medium">
                  {caption.speaker === 'user' ? 'You' : 'Assistant'}
                </span>
                <span>{formatCaptionInterval(caption.startMs, caption.endMs)}</span>
              </div>
              <p className="whitespace-pre-wrap break-words">{caption.text}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
