import {
  BookOpenCheckIcon,
  ChevronRightIcon,
  Sparkles,
} from "lucide-react"
import { NavLink, useLocation } from "react-router-dom"

import { navigation, type NavItem } from "@/components/navigation"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar"
import { UserMenu } from "@/components/user-menu"

function isCurrentPath(currentPath: string, url: string) {
  return url === "/admin" ? currentPath === url : currentPath.startsWith(url)
}

function NavigationItem({ item, onNavigate }: { item: NavItem; onNavigate: () => void }) {
  const { pathname } = useLocation()
  const Icon = item.icon

  if (!item.children) {
    const isActive = Boolean(item.url && isCurrentPath(pathname, item.url))
    return (
      <SidebarMenuItem>
        <SidebarMenuButton
          asChild
          isActive={isActive}
          tooltip={item.title}
          className={`relative transition-all duration-200 rounded-lg px-3 py-2 text-sm font-medium ${
            isActive
              ? "bg-gradient-to-r from-primary/15 via-primary/10 to-transparent text-primary font-semibold border-l-2 border-primary shadow-xs"
              : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
          }`}
        >
          <NavLink to={item.url ?? "/admin"} onClick={onNavigate} className="flex items-center gap-3">
            <Icon className={`h-4 w-4 shrink-0 transition-transform duration-200 group-hover/menu-button:scale-110 ${isActive ? "text-primary" : "text-sidebar-foreground/60"}`} />
            <span className="truncate">{item.title}</span>
          </NavLink>
        </SidebarMenuButton>
      </SidebarMenuItem>
    )
  }

  const hasActiveChild = item.children.some((child) => isCurrentPath(pathname, child.url))

  return (
    <Collapsible defaultOpen={hasActiveChild} className="group/collapsible">
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton
            isActive={hasActiveChild}
            tooltip={item.title}
            className={`relative transition-all duration-200 rounded-lg px-3 py-2 text-sm font-medium ${
              hasActiveChild
                ? "bg-sidebar-accent/50 text-sidebar-foreground font-semibold"
                : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
            }`}
          >
            <Icon className={`h-4 w-4 shrink-0 ${hasActiveChild ? "text-primary" : "text-sidebar-foreground/60"}`} />
            <span className="truncate">{item.title}</span>
            <ChevronRightIcon className="ml-auto h-4 w-4 shrink-0 text-sidebar-foreground/40 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
          </SidebarMenuButton>
        </CollapsibleTrigger>
        <CollapsibleContent className="data-[state=open]:animate-accordion-down data-[state=closed]:animate-accordion-up">
          <SidebarMenuSub className="ml-4 border-l border-sidebar-border/60 pl-2 space-y-1 my-1">
            {item.children.map((child) => {
              const isChildActive = isCurrentPath(pathname, child.url)
              return (
                <SidebarMenuSubItem key={child.url}>
                  <SidebarMenuSubButton
                    asChild
                    isActive={isChildActive}
                    className={`rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                      isChildActive
                        ? "bg-primary/10 text-primary font-semibold"
                        : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                    }`}
                  >
                    <NavLink to={child.url} onClick={onNavigate} className="truncate">
                      {child.title}
                    </NavLink>
                  </SidebarMenuSubButton>
                </SidebarMenuSubItem>
              )
            })}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  )
}

export function AppSidebar() {
  const { isMobile, setOpenMobile } = useSidebar()
  const closeMobileNavigation = () => {
    if (isMobile) setOpenMobile(false)
  }

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border bg-sidebar font-sans shadow-sm">
      <SidebarHeader className="border-b border-sidebar-border/60 p-3">
        <NavLink
          to="/admin"
          onClick={closeMobileNavigation}
          className="flex h-11 items-center gap-3 overflow-hidden rounded-xl px-2 outline-none transition-colors hover:bg-sidebar-accent/50 focus-visible:ring-2 focus-visible:ring-sidebar-ring"
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-primary via-indigo-500 to-violet-500 text-white shadow-md shadow-primary/20">
            <BookOpenCheckIcon className="h-5 w-5" />
          </span>
          <span className="min-w-0 group-data-[collapsible=icon]:hidden">
            <span className="flex items-center gap-1.5 truncate text-sm font-bold font-heading text-sidebar-foreground">
              BookMe Pro
              <Sparkles className="h-3 w-3 text-primary animate-pulse" />
            </span>
            <span className="block truncate text-[11px] font-medium text-sidebar-foreground/50">Admin workspace</span>
          </span>
        </NavLink>
      </SidebarHeader>
      <SidebarContent className="px-2 py-3 space-y-4">
        {navigation.map((section) => (
          <SidebarGroup key={section.label} className="p-0">
            <SidebarGroupLabel className="text-[10px] font-bold tracking-wider text-sidebar-foreground/50 uppercase px-3 py-1.5">
              {section.label}
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu className="space-y-1">
                {section.items.map((item) => (
                  <NavigationItem
                    key={item.title}
                    item={item}
                    onNavigate={closeMobileNavigation}
                  />
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border/60 p-2">
        <UserMenu />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
