import { BellIcon, BookOpenCheckIcon, Compass, Download, Menu } from "lucide-react"
import { Link, useLocation } from "react-router-dom"
import { toast } from "sonner"

import { navigation } from "@/components/navigation"
import { UserMenu } from "@/components/user-menu"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { usePwaInstall } from "@/hooks/use-pwa-install"
import { IosInstallDialog } from "@/components/ios-install-dialog"

import { ThemeToggle } from "@/components/theme-toggle"

function getPageLabel(pathname: string) {
  for (const section of navigation) {
    for (const item of section.items) {
      if (item.url && (pathname === item.url || (item.url !== "/admin" && pathname.startsWith(item.url)))) {
        return item.title
      }

      const child = item.children?.find(
        ({ url }) => pathname === url || pathname.startsWith(`${url}/`),
      )

      if (child) return child.title
    }
  }

  return "Admin workspace"
}

export function AppHeader({ unreadCount = 0 }: { unreadCount?: number }) {
  const { pathname } = useLocation()
  const { canInstall, isIOS, showIosInstructions, setShowIosInstructions, install } = usePwaInstall()

  const handleInstallClick = async () => {
    if (isIOS) {
      setShowIosInstructions(true)
      return
    }

    if (canInstall) {
      const accepted = await install()
      if (accepted) {
        toast.success("App installed successfully")
      }
    }
  }

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b bg-background/95 px-3 backdrop-blur sm:gap-2 sm:px-4">
      <SidebarTrigger 
        aria-label="Toggle navigation" 
        className="h-8 w-8 shrink-0 touch-manipulation hover:bg-accent"
      >
        <Menu className="h-4 w-4" />
      </SidebarTrigger>
      <Separator orientation="vertical" className="h-4 shrink-0" />
      <div className="flex min-w-0 max-w-[140px] items-center gap-1.5 sm:max-w-none md:hidden">
        <BookOpenCheckIcon className="h-4 w-4 shrink-0" />
        <span className="truncate text-xs font-semibold">FastAPI Bookings</span>
      </div>
      <p className="hidden min-w-0 flex-1 truncate text-xs font-medium text-muted-foreground md:block">
        {getPageLabel(pathname)}
      </p>
      <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
        <Link to="/directory">
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 border-primary/30 bg-primary/5 px-2.5 text-xs font-semibold text-primary shadow-xs hover:bg-primary/15"
            title="Open National Directory & Geo Map"
          >
            <Compass className="h-3.5 w-3.5 animate-spin-slow text-primary" />
            <span className="hidden sm:inline">Directory & Map</span>
            <span className="sm:hidden">Directory</span>
          </Button>
        </Link>
        {canInstall && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleInstallClick}
            className="h-8 gap-1.5 border-primary/40 bg-primary/10 px-2.5 text-xs font-medium text-primary shadow-xs hover:bg-primary/20"
            title="Install Progressive Web App"
          >
            <Download className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Install App</span>
            <span className="sm:hidden">Install</span>
          </Button>
        )}
        <ThemeToggle />
        <Button variant="ghost" size="icon" aria-label="Notifications" className="relative h-8 w-8">
          <BellIcon className="h-4 w-4" />
          {unreadCount > 0 && (
            <Badge className="absolute -top-1 -right-1 min-w-4 h-4 px-1 text-[10px] leading-none" aria-label={`${unreadCount} unread notifications`}>
              {unreadCount > 99 ? "99+" : unreadCount}
            </Badge>
          )}
        </Button>
        <UserMenu compact className="hidden sm:flex" />
      </div>

      <IosInstallDialog
        open={showIosInstructions}
        onOpenChange={setShowIosInstructions}
      />
    </header>
  )
}
