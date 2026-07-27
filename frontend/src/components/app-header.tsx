import { BellIcon, BookOpenCheckIcon } from "lucide-react"
import { useLocation } from "react-router-dom"

import { navigation } from "@/components/navigation"
import { UserMenu } from "@/components/user-menu"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"

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

  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur sm:px-6">
      <SidebarTrigger aria-label="Toggle navigation" />
      <Separator orientation="vertical" className="h-5" />
      <div className="flex min-w-0 items-center gap-2 md:hidden">
        <BookOpenCheckIcon className="shrink-0" />
        <span className="truncate text-sm font-semibold">FastAPI Bookings</span>
      </div>
      <p className="hidden min-w-0 flex-1 truncate text-sm font-medium text-muted-foreground md:block">
        {getPageLabel(pathname)}
      </p>
      <div className="ml-auto flex shrink-0 items-center gap-2">
        <ThemeToggle />
        <Button variant="ghost" size="icon" aria-label="Notifications" className="relative h-9 w-9">
          <BellIcon />
          {unreadCount > 0 && (
            <Badge className="absolute -top-1 -right-1 min-w-5 px-1" aria-label={`${unreadCount} unread notifications`}>
              {unreadCount > 99 ? "99+" : unreadCount}
            </Badge>
          )}
        </Button>
        <UserMenu compact className="hidden sm:flex" />
      </div>
    </header>
  )
}
