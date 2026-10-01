import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react"
import { apiClient } from "@/lib/api"

export interface TerminologyMap {
  [key: string]: string
}

export interface PublicTranslationsResponse {
  locale: string
  terminology: TerminologyMap
}

export interface UpdateTranslationPayload {
  locale?: string
  preset?: string
  terminology?: TerminologyMap
}

export interface TranslationContextType {
  locale: string
  terminology: TerminologyMap
  loading: boolean
  error: string | null
  t: (key: string, fallback?: string) => string
  refreshTranslations: () => Promise<void>
  updateTranslations: (payload: UpdateTranslationPayload) => Promise<void>
}

export const DEFAULT_TERMINOLOGY: TerminologyMap = {
  client: "Client",
  clients: "Clients",
  provider: "Provider",
  providers: "Providers",
  booking: "Booking",
  bookings: "Bookings",
  service: "Service",
  services: "Services",
  location: "Location",
  locations: "Locations",
}

const TranslationContext = createContext<TranslationContextType | null>(null)

export function TranslationProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocale] = useState<string>("en")
  const [terminology, setTerminology] = useState<TerminologyMap>(DEFAULT_TERMINOLOGY)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const refreshTranslations = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await apiClient.get<PublicTranslationsResponse>("/api/public/translations")
      if (data) {
        if (data.locale) setLocale(data.locale)
        if (data.terminology) {
          setTerminology((prev) => ({
            ...prev,
            ...data.terminology,
          }))
        }
      }
    } catch (err: any) {
      // Gracefully fall back to DEFAULT_TERMINOLOGY if unauthenticated or offline
      const msg = err?.data?.error?.message || err?.message || "Failed to load translations"
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshTranslations()
  }, [refreshTranslations])

  const t = useCallback(
    (key: string, fallback?: string): string => {
      const normalizedKey = key.toLowerCase().trim()
      if (terminology[normalizedKey]) {
        return terminology[normalizedKey]
      }
      if (terminology[key]) {
        return terminology[key]
      }
      if (fallback !== undefined) {
        return fallback
      }
      if (DEFAULT_TERMINOLOGY[normalizedKey]) {
        return DEFAULT_TERMINOLOGY[normalizedKey]
      }
      return key
    },
    [terminology]
  )

  const updateTranslations = useCallback(
    async (payload: UpdateTranslationPayload) => {
      setLoading(true)
      try {
        const res = await apiClient.put<any>("/api/admin/translations", payload)
        if (res) {
          if (res.locale) setLocale(res.locale)
          if (res.terminology) {
            setTerminology((prev) => ({
              ...prev,
              ...res.terminology,
            }))
          }
        }
      } finally {
        setLoading(false)
      }
    },
    []
  )

  const value = useMemo(
    () => ({
      locale,
      terminology,
      loading,
      error,
      t,
      refreshTranslations,
      updateTranslations,
    }),
    [locale, terminology, loading, error, t, refreshTranslations, updateTranslations]
  )

  return <TranslationContext.Provider value={value}>{children}</TranslationContext.Provider>
}

export function useTranslation(): TranslationContextType {
  const context = useContext(TranslationContext)
  if (!context) {
    // Provide safe non-throwing fallback if rendered outside provider (e.g. unit tests or standalone components)
    return {
      locale: "en",
      terminology: DEFAULT_TERMINOLOGY,
      loading: false,
      error: null,
      t: (key: string, fallback?: string) => {
        const normalized = key.toLowerCase().trim()
        return DEFAULT_TERMINOLOGY[normalized] ?? fallback ?? key
      },
      refreshTranslations: async () => {},
      updateTranslations: async () => {},
    }
  }
  return context
}

export const useTerminology = useTranslation
