import { CircleHelpIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

export function SupportButton() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          size="icon-lg"
          className="fixed right-[max(1.25rem,env(safe-area-inset-right))] bottom-[max(1.25rem,env(safe-area-inset-bottom))] rounded-full shadow-lg"
          aria-label="Open support"
        >
          <CircleHelpIcon />
        </Button>
      </TooltipTrigger>
      <TooltipContent side="left">Support and help</TooltipContent>
    </Tooltip>
  )
}
