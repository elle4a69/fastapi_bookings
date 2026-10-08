import { useCallback, useState } from 'react'
import { Hand, Check } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { defaultEpochManager } from '../rpc/action-catalogue.ts'
import { formAdapterRegistry } from '../adapters/registry.ts'

export interface ManualTakeoverControlProps {
  /** Optional custom callback invoked after takeover */
  onTakeover?: (newEpoch: number) => void
  /** Variant style for button */
  variant?: 'default' | 'destructive' | 'outline' | 'secondary'
  /** Size for button */
  size?: 'default' | 'sm' | 'lg'
  /** Custom label */
  label?: string
  /** Whether takeover is currently active */
  isTakenOver?: boolean
}

export function ManualTakeoverControl({
  onTakeover,
  variant = 'destructive',
  size = 'sm',
  label = "I'll do this part",
  isTakenOver = false,
}: ManualTakeoverControlProps) {
  const [takenOver, setTakenOver] = useState(isTakenOver)

  const handleTakeoverClick = useCallback(() => {
    // 1. Advance control epoch immediately to invalidate pending / late agent writes
    const newEpoch = defaultEpochManager.incrementEpoch("User clicked 'I\\'ll do this part' manual takeover")

    setTakenOver(true)

    // 2. Clear any staged form values or debounces in active adapter
    try {
      const activeAdapter = formAdapterRegistry.getActiveAdapter()
      if (activeAdapter && typeof activeAdapter.cancel_staging === 'function') {
        activeAdapter.cancel_staging()
      }
    } catch {
      // Form adapter guard
    }

    // 3. Dispatch browser event for system reactivity (field overlays, voice state, etc.)
    if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
      try {
        window.dispatchEvent(
          new CustomEvent('assistant-rpc:manual-takeover', {
            detail: {
              newEpoch,
              source: 'ui_button',
              reason: "User clicked 'I\\'ll do this part'",
              timestamp: new Date().toISOString(),
            },
          }),
        )
        window.dispatchEvent(new CustomEvent('assistant:dismiss-highlight'))
      } catch {
        // Event guard
      }
    }

    if (onTakeover) {
      onTakeover(newEpoch)
    }
  }, [onTakeover])

  if (takenOver) {
    return (
      <div
        data-testid="manual-takeover-active-indicator"
        className="flex items-center gap-1.5 rounded-md bg-amber-500/15 border border-amber-500/30 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:text-amber-400"
      >
        <Check className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" aria-hidden="true" />
        <span>Manual Control Active</span>
      </div>
    )
  }

  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      onClick={handleTakeoverClick}
      data-testid="manual-takeover-button"
      className="gap-1.5 font-medium shadow-sm transition-transform active:scale-95"
      title="Take manual control over current form and cancel pending assistant writes"
      aria-label="I'll do this part - Take manual control"
    >
      <Hand className="h-3.5 w-3.5" aria-hidden="true" />
      <span>{label}</span>
    </Button>
  )
}
