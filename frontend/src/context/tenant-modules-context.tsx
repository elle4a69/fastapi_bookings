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

export interface TenantModulesContextType {
  modulesData: TenantModulesData | null
  enabledModules: string[]
  loading: boolean
  error: string | null
  refreshModules: () => Promise<void>
  toggleModule: (moduleKey: string, enabled: boolean) => Promise<{ ok: boolean; message: string }>
  updateTier: (tier: string, quota?: number) => Promise<{ ok: boolean; message?: string }>
  isModuleEnabled: (moduleKey: string) => boolean
  multipleProvidersEnabled: boolean
  locationsEnabled: boolean
  categoriesEnabled: boolean
  productsEnabled: boolean
  addonsEnabled: boolean
  relationshipMatrixEnabled: boolean
  hasMultipleProviders: boolean
  hasLocations: boolean
  hasCategories: boolean
  hasProducts: boolean
  hasAddons: boolean
  hasRelationshipMatrix: boolean
}

const TenantModulesContext = createContext<TenantModulesContextType | null>(null)

// Safe fallback for core modules before initial network load completes
const DEFAULT_FALLBACK_MODULES = [
  "dashboard",
  "calendar",
  "bookings",
  "website",
  "multiple_providers",
  "providers",
  "locations",
  "categories",
  "products",
  "addons",
  "packages",
  "sms_assistant",
  "finance_invoicing",
  "media",
  "booking_forms",
  "reviews",
  "calcom_scheduling",
  "relationship_matrix",
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

  const isModuleEnabled = useCallback(
    (moduleKey: string): boolean => {
      const k = moduleKey.toLowerCase()
      if (k === "multiple_providers" || k === "providers") {
        return enabledModules.some((m) => m.toLowerCase() === "multiple_providers" || m.toLowerCase() === "providers")
      }
      if (k === "addons" || k === "packages") {
        return enabledModules.some((m) => m.toLowerCase() === "addons" || m.toLowerCase() === "packages")
      }
      if (k === "relationship_matrix" || k === "relationships_matrix") {
        return enabledModules.some((m) => m.toLowerCase() === "relationship_matrix" || m.toLowerCase() === "relationships_matrix")
      }
      return enabledModules.some((m) => m.toLowerCase() === k)
    },
    [enabledModules]
  )

  const multipleProvidersEnabled = useMemo(() => isModuleEnabled("multiple_providers"), [isModuleEnabled])
  const locationsEnabled = useMemo(() => isModuleEnabled("locations"), [isModuleEnabled])
  const categoriesEnabled = useMemo(() => isModuleEnabled("categories"), [isModuleEnabled])
  const productsEnabled = useMemo(() => isModuleEnabled("products"), [isModuleEnabled])
  const addonsEnabled = useMemo(() => isModuleEnabled("addons"), [isModuleEnabled])
  const relationshipMatrixEnabled = useMemo(
    () => isModuleEnabled("relationship_matrix") && multipleProvidersEnabled,
    [isModuleEnabled, multipleProvidersEnabled]
  )

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
      isModuleEnabled,
      multipleProvidersEnabled,
      locationsEnabled,
      categoriesEnabled,
      productsEnabled,
      addonsEnabled,
      relationshipMatrixEnabled,
      hasMultipleProviders: multipleProvidersEnabled,
      hasLocations: locationsEnabled,
      hasCategories: categoriesEnabled,
      hasProducts: productsEnabled,
      hasAddons: addonsEnabled,
      hasRelationshipMatrix: relationshipMatrixEnabled,
    }),
    [
      modulesData,
      enabledModules,
      loading,
      error,
      refreshModules,
      toggleModule,
      updateTier,
      isModuleEnabled,
      multipleProvidersEnabled,
      locationsEnabled,
      categoriesEnabled,
      productsEnabled,
      addonsEnabled,
      relationshipMatrixEnabled,
    ]
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

