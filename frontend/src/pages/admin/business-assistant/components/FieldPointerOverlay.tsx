import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Sparkles } from 'lucide-react'

export interface FieldPointerOverlayProps {
  /** Optional timeout in ms after which the highlight automatically dismisses (default: 6000ms) */
  autoDismissMs?: number
  /** Callback fired when highlight is dismissed */
  onDismiss?: (field: string) => void
}

interface OverlayRect {
  top: number
  left: number
  width: number
  height: number
}

export function FieldPointerOverlay({
  autoDismissMs = 6000,
  onDismiss,
}: FieldPointerOverlayProps) {
  const [activeField, setActiveField] = useState<string | null>(null)
  const [activeLabel, setActiveLabel] = useState<string | null>(null)
  const [rect, setRect] = useState<OverlayRect | null>(null)
  const targetElementRef = useRef<HTMLElement | null>(null)
  const dismissTimerRef = useRef<any>(null)

  const resolveTargetElement = (field: string): HTMLElement | null => {
    if (typeof document === 'undefined' || !field) return null
    const cleanField = field.trim()
    const selectors = [
      `[data-field-name="${cleanField}"]`,
      `[name="${cleanField}"]`,
      `[data-testid="input-${cleanField}"]`,
      `#${cleanField}`,
      `[data-control-id="${cleanField}"]`,
      `#field-${cleanField}`,
      `[id="${cleanField}"]`,
    ]

    for (const selector of selectors) {
      try {
        const el = document.querySelector(selector) as HTMLElement | null
        if (el) return el
      } catch {
        // Query selector guard
      }
    }
    return null
  }

  const updateRect = () => {
    if (!targetElementRef.current) return
    const el = targetElementRef.current
    const r = el.getBoundingClientRect()
    setRect({
      top: r.top,
      left: r.left,
      width: r.width,
      height: r.height,
    })
  }

  const dismiss = (fieldToDismiss?: string) => {
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current)
      dismissTimerRef.current = null
    }
    const currentField = fieldToDismiss || activeField
    setActiveField(null)
    setActiveLabel(null)
    setRect(null)
    targetElementRef.current = null

    if (currentField && onDismiss) {
      onDismiss(currentField)
    }
  }

  useEffect(() => {
    const handleHighlight = (event: Event) => {
      const customEvent = event as CustomEvent<{
        field?: string
        label?: string
        controlId?: string
      }>
      const field =
        customEvent.detail?.field ||
        customEvent.detail?.controlId ||
        (customEvent as any).detail?.pointed_control

      if (!field) return

      const el = resolveTargetElement(field)
      if (el) {
        targetElementRef.current = el
        const r = el.getBoundingClientRect()
        setRect({
          top: r.top,
          left: r.left,
          width: r.width,
          height: r.height,
        })
        setActiveField(field)
        setActiveLabel(customEvent.detail?.label || null)

        try {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        } catch {
          // Scroll guard
        }

        if (dismissTimerRef.current) {
          clearTimeout(dismissTimerRef.current)
        }
        if (autoDismissMs > 0) {
          dismissTimerRef.current = setTimeout(() => {
            dismiss(field)
          }, autoDismissMs)
        }
      }
    }

    const handleManualTakeover = () => {
      dismiss()
    }

    const handleDismiss = () => {
      dismiss()
    }

    // Dismiss immediately when user interacts with the target element directly (no focus battle)
    const handleUserInteraction = (event: Event) => {
      if (!targetElementRef.current) return
      const target = event.target as Node | null
      if (
        target &&
        (target === targetElementRef.current || targetElementRef.current.contains(target))
      ) {
        dismiss()
      }
    }

    if (typeof window !== 'undefined') {
      window.addEventListener('assistant:highlight-field', handleHighlight)
      window.addEventListener('assistant-rpc:highlight-field', handleHighlight as EventListener)
      window.addEventListener('assistant-rpc:point-to-control', handleHighlight as EventListener)
      window.addEventListener('assistant-rpc:manual-takeover', handleManualTakeover)
      window.addEventListener('assistant:dismiss-highlight', handleDismiss)

      window.addEventListener('focusin', handleUserInteraction, true)
      window.addEventListener('input', handleUserInteraction, true)
      window.addEventListener('scroll', updateRect, true)
      window.addEventListener('resize', updateRect)
    }

    return () => {
      if (dismissTimerRef.current) {
        clearTimeout(dismissTimerRef.current)
      }
      if (typeof window !== 'undefined') {
        window.removeEventListener('assistant:highlight-field', handleHighlight)
        window.removeEventListener('assistant-rpc:highlight-field', handleHighlight as EventListener)
        window.removeEventListener('assistant-rpc:point-to-control', handleHighlight as EventListener)
        window.removeEventListener('assistant-rpc:manual-takeover', handleManualTakeover)
        window.removeEventListener('assistant:dismiss-highlight', handleDismiss)

        window.removeEventListener('focusin', handleUserInteraction, true)
        window.removeEventListener('input', handleUserInteraction, true)
        window.removeEventListener('scroll', updateRect, true)
        window.removeEventListener('resize', updateRect)
      }
    }
  }, [autoDismissMs, dismiss])

  if (!activeField || !rect) {
    return null
  }

  // Position calculations with padding
  const padding = 4
  const top = rect.top - padding
  const left = rect.left - padding
  const width = rect.width + padding * 2
  const height = rect.height + padding * 2

  // Badge positioning (above or below element depending on viewport room)
  const isCloseToTop = rect.top < 36
  const badgeStyle: CSSProperties = isCloseToTop
    ? { top: '100%', marginTop: '6px' }
    : { bottom: '100%', marginBottom: '6px' }

  return (
    <div
      data-testid="field-pointer-overlay"
      aria-live="polite"
      role="status"
      className="pointer-events-none fixed z-50 transition-all duration-200"
      style={{
        top: `${top}px`,
        left: `${left}px`,
        width: `${width}px`,
        height: `${height}px`,
      }}
    >
      {/* Glowing pulsing accent ring */}
      <div
        className="absolute inset-0 rounded-md border-2 border-indigo-500 shadow-[0_0_18px_rgba(99,102,241,0.6)] animate-pulse"
        aria-hidden="true"
      />

      {/* Floating Badge */}
      <div
        className="absolute left-0 flex items-center gap-1.5 rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white shadow-lg backdrop-blur-xs whitespace-nowrap animate-in fade-in zoom-in-95 duration-150"
        style={badgeStyle}
      >
        <Sparkles className="h-3.5 w-3.5 animate-spin" style={{ animationDuration: '4s' }} aria-hidden="true" />
        <span>
          Assistant editing: <strong className="font-semibold">{activeLabel || activeField}</strong>
        </span>
      </div>
    </div>
  )
}
