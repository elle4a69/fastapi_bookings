import { useState } from "react"
import { LogOutIcon, SettingsIcon, UserRoundIcon, MessageSquareIcon, ExternalLinkIcon, Loader2Icon } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
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
import { apiClient, endAdminSession } from "@/lib/api"
import { useAuth } from "@/context/auth-context"

type UserMenuProps = {
  compact?: boolean
  className?: string
}

export function UserMenu({ compact = false, className }: UserMenuProps) {
  const navigate = useNavigate()
  const { user, role, isProvider, chatwootSsoUrl } = useAuth()
  const [isLaunchingChatwoot, setIsLaunchingChatwoot] = useState(false)

  const handleLogout = () => {
    endAdminSession(navigate)
  }

  const handleOpenChatwoot = async () => {
    try {
      setIsLaunchingChatwoot(true)
      const res = await apiClient.get<{ ok: boolean; data: { chatwoot_sso_url: string } }>('/api/admin/auth/chatwoot-sso')
      if (res?.ok && res.data?.chatwoot_sso_url) {
        window.open(res.data.chatwoot_sso_url, '_blank', 'noopener,noreferrer')
        return
      }
    } catch {
      // Fall back to stored SSO link if available
      if (chatwootSsoUrl) {
        window.open(chatwootSsoUrl, '_blank', 'noopener,noreferrer')
        return
      }
      // If neither exists, open standard chatwoot URL
      window.open('http://localhost:4000', '_blank', 'noopener,noreferrer')
    } finally {
      setIsLaunchingChatwoot(false)
    }
  }

  const roleLabel =
    role === 'owner' ? 'Owner / Admin' :
    role === 'manager' ? 'Manager' :
    role === 'provider' ? 'Technician / Provider' : role

  const initials = (user?.first_name && user?.last_name)
    ? `${user.first_name[0]}${user.last_name[0]}`.toUpperCase()
    : (user?.login || 'Admin').slice(0, 2).toUpperCase()

  const displayName = (user?.first_name || user?.last_name)
    ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
    : (user?.login || 'Staff Member')

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={user?.login ? `${displayName} (${roleLabel})` : "User profile menu"}
          className={cn(
            "flex min-w-0 items-center gap-2 rounded-lg p-1.5 text-left outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
            compact ? "max-w-48" : "w-full",
            className,
          )}
        >
          <Avatar className="h-8 w-8">
            {user?.avatar_url && (
              <AvatarImage src={user.avatar_url} alt={displayName} />
            )}
            <AvatarFallback className="text-xs bg-primary text-primary-foreground font-semibold">{initials}</AvatarFallback>
          </Avatar>
          <span className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
            <span className="block truncate text-sm font-medium">{displayName}</span>
            <span className="block truncate text-xs text-muted-foreground">{roleLabel}</span>
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-56">
        <DropdownMenuLabel>
          <span className="block text-sm text-foreground">{displayName}</span>
          {user?.email && <span className="block text-xs text-muted-foreground truncate">{user.email}</span>}
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
          <DropdownMenuItem
            disabled={isLaunchingChatwoot}
            onSelect={(e) => {
              e.preventDefault()
              handleOpenChatwoot()
            }}
          >
            {isLaunchingChatwoot ? (
              <Loader2Icon className="h-4 w-4 animate-spin text-primary" />
            ) : (
              <MessageSquareIcon className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            )}
            <span>Chatwoot Workspace</span>
            <ExternalLinkIcon className="ml-auto h-3 w-3 text-muted-foreground" />
          </DropdownMenuItem>
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
