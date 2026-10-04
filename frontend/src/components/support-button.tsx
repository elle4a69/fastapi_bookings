import { Bot } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useBusinessAssistant } from "@/pages/admin/business-assistant/business-assistant-context"

export function SupportButton() {
  const { toggleDrawer, drawerOpen } = useBusinessAssistant()

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          size="icon-lg"
          onClick={toggleDrawer}
          className="fixed right-[max(1.25rem,env(safe-area-inset-right))] bottom-[max(1.25rem,env(safe-area-inset-bottom))] rounded-full shadow-lg z-30"
          aria-label="Open Business Assistant"
          aria-expanded={drawerOpen}
          aria-controls="business-assistant-drawer"
          data-testid="business-assistant-floating-button"
        >
          <Bot className="h-5 w-5" />
        </Button>
      </TooltipTrigger>
      <TooltipContent side="left">Business Assistant</TooltipContent>
    </Tooltip>
  )
}
