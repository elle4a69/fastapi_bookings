import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react"
import { apiClient } from "@/lib/api"

export interface TenantModuleInfo {
  key: string
  name: string
  description: string
  category: string
  is_core: boolean
  enabled: boolean
  icon: string
}

export interface TenantModulesData {
  tier: string
  addon_quota: number
  used_addons: number
  available_addons: number
  modules: TenantModuleInfo[]
}

interface TenantModulesContextType {
  modulesData: TenantModulesData | null
  enabledModules: string[]
  loading: boolean
  error: string | null
  refreshModules: () => Promise<void>
  toggleModule: (moduleKey: string, enabled: boolean) => Promise<{ ok: boolean; message: string }>
  updateTier: (tier: string, quota?: number) => Promise<{ ok: boolean; message?: string }>
}

const TenantModulesContext = createContext<TenantModulesContextType | null>(null)

// Safe fallback for core modules before initial network load completes
const DEFAULT_FALLBACK_MODULES = [
  "dashboard",
  "calendar",
  "bookings",
  "website",
  "sms_assistant",
  "locations",
  "providers",
  "packages",
  "finance_invoicing",
  "media",
  "booking_forms",
  "reviews",
  "calcom_scheduling",
]

export function TenantModulesProvider({ children }: { children: React.ReactNode }) {
  const [modulesData, setModulesData] = useState<TenantModulesData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const refreshModules = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await apiClient.get<TenantModulesData>("/api/admin/tenant/modules")
      setModulesData(data)
    } catch (err: any) {
      const msg = err?.data?.error?.message || err?.message || "Failed to load tenant modules"
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshModules()
  }, [refreshModules])

  const enabledModules = useMemo(() => {
    if (!modulesData) {
      return DEFAULT_FALLBACK_MODULES
    }
    return modulesData.modules.filter((m) => m.enabled).map((m) => m.key)
  }, [modulesData])

  const toggleModule = useCallback(
    async (moduleKey: string, enabled: boolean): Promise<{ ok: boolean; message: string }> => {
      try {
        const res = await apiClient.post<{ ok: boolean; message: string; enabled_modules: string[] }>(
          "/api/admin/tenant/modules/toggle",
          { module_key: moduleKey, enabled }
        )
        // Refresh full modules data to update quotas, counts and flags
        await refreshModules()
        return { ok: true, message: res.message }
      } catch (err: any) {
        const msg = err?.data?.error?.message || err?.message || "Failed to update module state"
        throw new Error(msg)
      }
    },
    [refreshModules]
  )

  const updateTier = useCallback(
    async (tier: string, quota?: number): Promise<{ ok: boolean; message?: string }> => {
      try {
        await apiClient.put<TenantModulesData>("/api/admin/tenant/modules/tier", {
          tier,
          addon_quota: quota,
        })
        await refreshModules()
        return { ok: true, message: `Subscription tier updated to ${tier}` }
      } catch (err: any) {
        const msg = err?.data?.error?.message || err?.message || "Failed to update subscription tier"
        throw new Error(msg)
      }
    },
    [refreshModules]
  )

  const contextValue = useMemo<TenantModulesContextType>(
    () => ({
      modulesData,
      enabledModules,
      loading,
      error,
      refreshModules,
      toggleModule,
      updateTier,
    }),
    [modulesData, enabledModules, loading, error, refreshModules, toggleModule, updateTier]
  )

  return (
    <TenantModulesContext.Provider value={contextValue}>
      {children}
    </TenantModulesContext.Provider>
  )
}

export function useTenantModules(): TenantModulesContextType {
  const ctx = useContext(TenantModulesContext)
  if (!ctx) {
    throw new Error("useTenantModules must be used within a TenantModulesProvider")
  }
  return ctx
}
