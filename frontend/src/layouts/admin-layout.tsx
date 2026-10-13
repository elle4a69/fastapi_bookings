import type { CSSProperties } from "react"
import { Outlet, useLocation } from "react-router-dom"

import { AppHeader } from "@/components/app-header"
import { AppSidebar } from "@/components/app-sidebar"
import { SupportButton } from "@/components/support-button"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { TenantModulesProvider } from "@/context/tenant-modules-context"
import { BusinessAssistantProvider } from "@/pages/admin/business-assistant/business-assistant-context"
import { AgentPopup_01 } from "@/components/agents-ui/agent-popup"
import {
  FieldPointerOverlay,
  OnboardingStatusDock,
} from "@/pages/admin/business-assistant/components"
import { AgentProvider, VoiceProvider, AgentSidebar } from "@/components/ui-agent"

export function AdminLayout() {
  const location = useLocation()
  const isOperationalRoute =
    location.pathname.startsWith('/admin/sms-assistant') ||
    location.pathname.startsWith('/admin/calendar') ||
    location.pathname.startsWith('/admin/messages') ||
    location.pathname.startsWith('/admin/coding-cockpit')

  return (
    <TenantModulesProvider>
      <BusinessAssistantProvider>
        <AgentProvider>
          <VoiceProvider>
            <TooltipProvider>
          <SidebarProvider
            style={
              {
                "--sidebar-width": "13.75rem",
                "--sidebar-width-icon": "3.75rem",
              } as CSSProperties
            }
          >
            <a
              href="#main-content"
              className="fixed top-2 left-2 -translate-y-16 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-transform focus:translate-y-0"
            >
              Skip to content
            </a>
            <AppSidebar />
            <SidebarInset className="h-svh min-w-0 overflow-hidden">
              <AppHeader />
              <div
                id="main-content"
                className={
                  isOperationalRoute
                    ? "min-h-0 flex-1 flex flex-col p-0 overflow-hidden"
                    : "min-h-0 flex-1 overflow-y-auto px-1.5 py-2 sm:p-4 md:p-5 min-w-0 overflow-x-hidden pb-[calc(1.5rem+env(safe-area-inset-bottom))]"
                }
                tabIndex={-1}
              >
                <Outlet />
              </div>
            </SidebarInset>
            <SupportButton />
            <AgentPopup_01
              agentName="Business Assistant"
              isPreConnectBufferEnabled={true}
              preConnectMessage="Agent is listening, ask it a question"
              audioVisualizer={{ type: 'bar', barCount: 3 }}
              controls={{
                leave: true,
                microphone: true,
                chat: true,
                camera: true,
                screenShare: true,
              }}
            />
            <FieldPointerOverlay />
            <OnboardingStatusDock />
            <AgentSidebar />
          </SidebarProvider>
        </TooltipProvider>
          </VoiceProvider>
        </AgentProvider>
      </BusinessAssistantProvider>
    </TenantModulesProvider>
  )
}
