import { useCallback, useEffect, useState } from 'react'

export interface HighlightDetail {
  field: string
  selector?: string
  id?: string
  label?: string
  rect?: {
    top: number
    left: number
    width: number
    height: number
  }
}

export function useFieldHighlight() {
  const [activeHighlight, setActiveHighlight] = useState<HighlightDetail | null>(null)

  useEffect(() => {
    const handleHighlightEvent = (event: Event) => {
      const customEvent = event as CustomEvent<HighlightDetail>
      if (customEvent.detail && customEvent.detail.field) {
        setActiveHighlight(customEvent.detail)
      }
    }

    const handleDismissEvent = () => {
      setActiveHighlight(null)
    }

    if (typeof window !== 'undefined') {
      window.addEventListener('assistant:highlight-field', handleHighlightEvent)
      window.addEventListener('assistant-rpc:highlight-field', handleHighlightEvent as EventListener)
      window.addEventListener('assistant-rpc:manual-takeover', handleDismissEvent)
      window.addEventListener('assistant:dismiss-highlight', handleDismissEvent)
    }

    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('assistant:highlight-field', handleHighlightEvent)
        window.removeEventListener('assistant-rpc:highlight-field', handleHighlightEvent as EventListener)
        window.removeEventListener('assistant-rpc:manual-takeover', handleDismissEvent)
        window.removeEventListener('assistant:dismiss-highlight', handleDismissEvent)
      }
    }
  }, [])

  const highlightField = useCallback((field: string, label?: string) => {
    if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
      window.dispatchEvent(
        new CustomEvent<HighlightDetail>('assistant:highlight-field', {
          detail: { field, label },
        }),
      )
    }
  }, [])

  const dismissHighlight = useCallback(() => {
    setActiveHighlight(null)
    if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
      window.dispatchEvent(new CustomEvent('assistant:dismiss-highlight'))
    }
  }, [])

  return {
    activeHighlight,
    highlightField,
    dismissHighlight,
  }
}
