import type { CSSProperties } from "react"
import { Outlet, useLocation } from "react-router-dom"

import { AppHeader } from "@/components/app-header"
import { AppSidebar } from "@/components/app-sidebar"
import { SupportButton } from "@/components/support-button"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { TenantModulesProvider } from "@/context/tenant-modules-context"

export function AdminLayout() {
  const location = useLocation()
  const isOperationalRoute = location.pathname.startsWith('/admin/sms-assistant') ||
                             location.pathname.startsWith('/admin/calendar') ||
                             location.pathname.startsWith('/admin/messages')

  return (
    <TenantModulesProvider>
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
                : "min-h-0 flex-1 overflow-y-auto p-3 sm:p-4 md:p-5 min-w-0 overflow-x-hidden pb-[calc(1.5rem+env(safe-area-inset-bottom))]"
            } 
            tabIndex={-1}
          >
            <Outlet />
          </div>
        </SidebarInset>
        <SupportButton />
      </SidebarProvider>
    </TooltipProvider>
  </TenantModulesProvider>
  )
}

