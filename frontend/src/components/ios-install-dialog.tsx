import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { SquareArrowUp, SquarePlus, Plus, Compass, Smartphone } from "lucide-react"

interface IosInstallDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function IosInstallDialog({ open, onOpenChange }: IosInstallDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary mb-2 shadow-inner">
            <Smartphone className="h-6 w-6" />
          </div>
          <DialogTitle className="text-center text-lg font-bold">
            Install on iPhone &amp; iPad
          </DialogTitle>
          <DialogDescription className="text-center text-xs text-muted-foreground">
            Install FastAPI Bookings on your home screen for a fast, native app experience with offline support.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2">
          {/* Step 1 */}
          <div className="flex items-start gap-3 rounded-lg border bg-card p-3 shadow-xs">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-bold text-primary">
              1
            </div>
            <div className="space-y-0.5 text-xs leading-relaxed">
              <p className="font-semibold text-foreground flex items-center gap-1.5 flex-wrap">
                Tap the <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-[11px] font-medium text-foreground"><SquareArrowUp className="h-3.5 w-3.5 text-primary" /> Share</span> button
              </p>
              <p className="text-muted-foreground">
                Located in Safari&apos;s bottom toolbar (or top right on iPad).
              </p>
            </div>
          </div>

          {/* Step 2 */}
          <div className="flex items-start gap-3 rounded-lg border bg-card p-3 shadow-xs">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-bold text-primary">
              2
            </div>
            <div className="space-y-0.5 text-xs leading-relaxed">
              <p className="font-semibold text-foreground flex items-center gap-1.5 flex-wrap">
                Tap <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-[11px] font-medium text-foreground"><SquarePlus className="h-3.5 w-3.5 text-primary" /> Add to Home Screen</span>
              </p>
              <p className="text-muted-foreground">
                Scroll down in the share sheet options to find it.
              </p>
            </div>
          </div>

          {/* Step 3 */}
          <div className="flex items-start gap-3 rounded-lg border bg-card p-3 shadow-xs">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-bold text-primary">
              3
            </div>
            <div className="space-y-0.5 text-xs leading-relaxed">
              <p className="font-semibold text-foreground flex items-center gap-1.5 flex-wrap">
                Tap <span className="inline-flex items-center gap-1 rounded bg-primary text-primary-foreground px-1.5 py-0.5 text-[11px] font-medium"><Plus className="h-3 w-3" /> Add</span>
              </p>
              <p className="text-muted-foreground">
                In the top right corner to confirm and place on your home screen.
              </p>
            </div>
          </div>

          {/* In-app browser notice */}
          <div className="flex items-center gap-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-[11px] text-amber-800 dark:text-amber-300">
            <Compass className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            <span>
              If you opened this inside Gmail, Slack, or another app, tap <strong>•••</strong> or the browser icon to <strong>Open in Safari</strong> first.
            </span>
          </div>
        </div>

        <DialogFooter className="sm:justify-center">
          <Button
            type="button"
            className="w-full sm:w-auto min-w-[120px]"
            onClick={() => onOpenChange(false)}
          >
            Got it
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
