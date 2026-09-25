import { LogOutIcon, SettingsIcon, UserRoundIcon } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import { endAdminSession } from "@/lib/api"
import { useAuth } from "@/context/auth-context"

type UserMenuProps = {
  compact?: boolean
  className?: string
}

export function UserMenu({ compact = false, className }: UserMenuProps) {
  const navigate = useNavigate()
  const { user, role, isProvider } = useAuth()

  const handleLogout = () => {
    endAdminSession(navigate)
  }

  const roleLabel =
    role === 'owner' ? 'Owner / Admin' :
    role === 'manager' ? 'Manager' :
    role === 'provider' ? 'Technician / Provider' : role

  const initials = (user?.login || 'Admin')
    .slice(0, 2)
    .toUpperCase()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            "flex min-w-0 items-center gap-2 rounded-lg p-1.5 text-left outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
            compact ? "max-w-48" : "w-full",
            className,
          )}
        >
          <Avatar className="h-8 w-8">
            <AvatarFallback className="text-xs bg-primary/15 text-primary font-semibold">{initials}</AvatarFallback>
          </Avatar>
          <span className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
            <span className="block truncate text-sm font-medium">{user?.login || 'Staff Member'}</span>
            <span className="block truncate text-xs text-muted-foreground">{roleLabel}</span>
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-56">
        <DropdownMenuLabel>
          <span className="block text-sm text-foreground">{user?.login || 'Staff Member'}</span>
          <span className="font-normal text-xs text-muted-foreground capitalize">{roleLabel} workspace</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem onSelect={() => navigate(isProvider ? '/admin/my-profile' : '/admin')}>
            <UserRoundIcon />
            {isProvider ? 'My Profile' : 'Account'}
          </DropdownMenuItem>
          {!isProvider && (
            <DropdownMenuItem onSelect={() => navigate('/admin/settings/business')}>
              <SettingsIcon />
              Business settings
            </DropdownMenuItem>
          )}
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem variant="destructive" onSelect={handleLogout}>
            <LogOutIcon />
            Log out
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
