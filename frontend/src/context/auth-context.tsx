import React, { createContext, useContext, useEffect, useState, useMemo, useCallback } from 'react'
import { getAdminAccessToken, apiClient } from '@/lib/api'

export type UserRole = 'owner' | 'manager' | 'provider' | 'admin'

export interface AuthUser {
  id: number
  login: string
  role: UserRole
  provider_id: number | null
  company?: string
  tenant_id?: number
}

interface AuthContextValue {
  user: AuthUser | null
  role: UserRole
  provider_id: number | null
  isOwner: boolean
  isManager: boolean
  isProvider: boolean
  isLoading: boolean
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function parseJwt(token: string): { sub?: string; role?: string; provider_id?: number } | null {
  try {
    const base64Url = token.split('.')[1]
    if (!base64Url) return null
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const token = getAdminAccessToken()
    if (!token) return null
    const payload = parseJwt(token)
    if (!payload || !payload.sub) return null
    return {
      id: Number(payload.sub),
      login: 'Staff Member',
      role: (payload.role as UserRole) || 'owner',
      provider_id: payload.provider_id ?? null,
    }
  })
  const [isLoading, setIsLoading] = useState<boolean>(true)

  const fetchCurrentUser = useCallback(async () => {
    const token = getAdminAccessToken()
    if (!token) {
      setUser(null)
      setIsLoading(false)
      return
    }

    try {
      const res = await apiClient.get<{ ok: boolean; data: AuthUser }>('/api/admin/auth/me')
      if (res?.ok && res?.data) {
        setUser(res.data)
      }
    } catch {
      // Fallback to token payload if server is temporarily unreachable or on dev
      const payload = parseJwt(token)
      if (payload?.sub) {
        setUser((prev) => prev || {
          id: Number(payload.sub),
          login: 'Staff Member',
          role: (payload.role as UserRole) || 'owner',
          provider_id: payload.provider_id ?? null,
        })
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCurrentUser()
  }, [fetchCurrentUser])

  const role = user?.role || 'owner'
  const isOwner = role === 'owner' || role === 'admin'
  const isManager = role === 'manager'
  const isProvider = role === 'provider'
  const provider_id = user?.provider_id ?? null

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      role,
      provider_id,
      isOwner,
      isManager,
      isProvider,
      isLoading,
      refreshUser: fetchCurrentUser,
    }),
    [user, role, provider_id, isOwner, isManager, isProvider, isLoading, fetchCurrentUser]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    // Fallback default state for components rendered outside provider
    return {
      user: null,
      role: 'owner',
      provider_id: null,
      isOwner: true,
      isManager: false,
      isProvider: false,
      isLoading: false,
      refreshUser: async () => {},
    }
  }
  return context
}
