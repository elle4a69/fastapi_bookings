import { useEffect, useState, useCallback, useRef } from "react"
import { apiClient } from "@/lib/api"
import { useTenantModules } from "@/context/tenant-modules-context"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { MobilePageShell } from "@/components/ui/mobile-page-shell"
import { AddressAutocomplete } from "@/components/ui/address-autocomplete"
import { AutoSaveStatus, type SaveState } from "@/components/ui/auto-save-status"
import {
  User,
  MapPin,
  Building,
  Car,
  Clock,
  DollarSign,
  EyeOff,
  Copy,
  Plus,
  Sparkles,
  Info,
  Upload,
  X,
  Globe,
} from "lucide-react"
import { toast } from "sonner"

interface BusinessProfile {
  name: string
  email: string
  phone: string
  address: string
}

interface SoloProvider {
  id: number | string
  name: string
  email?: string
  phone?: string
  description?: string
  image?: string
  avatar?: string
  allow_in_call: boolean
  allow_out_call: boolean
  out_call_radius_km: number
  base_outcall_surcharge: number
  per_km_fee: number
  turnaround_buffer_mins: number
}

interface PrimaryLocation {
  id: number | string
  name: string
  address?: string
  image?: string
  timezone?: string
  is_client_hidden?: boolean
}

const POPULAR_TIMEZONES = [
  { value: "Australia/Sydney", label: "Australia/Sydney (AEDT/AEST)" },
  { value: "Australia/Melbourne", label: "Australia/Melbourne (AEDT/AEST)" },
  { value: "Australia/Brisbane", label: "Australia/Brisbane (AEST - No DST)" },
  { value: "Australia/Perth", label: "Australia/Perth (AWST)" },
  { value: "Australia/Adelaide", label: "Australia/Adelaide (ACDT/ACST)" },
  { value: "Australia/Darwin", label: "Australia/Darwin (ACST)" },
  { value: "Australia/Hobart", label: "Australia/Hobart (AEDT/AEST)" },
  { value: "UTC", label: "UTC (Coordinated Universal Time)" },
  { value: "America/New_York", label: "America/New_York (Eastern Time)" },
  { value: "America/Los_Angeles", label: "America/Los_Angeles (Pacific Time)" },
  { value: "Europe/London", label: "Europe/London (GMT/BST)" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo (JST)" },
  { value: "Asia/Singapore", label: "Asia/Singapore (SGT)" },
  { value: "Pacific/Auckland", label: "Pacific/Auckland (NZDT/NZST)" },
]

const IMAGE_MAX_DIMENSION = 400
const IMAGE_MAX_BYTES = 120 * 1024

function canvasToBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob)
      } else {
        reject(new Error("Unable to compress image"))
      }
    }, "image/webp", quality)
  })
}

async function createImageThumbnail(file: File): Promise<string> {
  if (!file.type.startsWith("image/")) {
    throw new Error("Please select an image file (JPG, PNG, WEBP)")
  }

  const objectUrl = URL.createObjectURL(file)
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image()
      element.onload = () => resolve(element)
      element.onerror = () => reject(new Error("Unable to read image file"))
      element.src = objectUrl
    })

    let width = image.naturalWidth
    let height = image.naturalHeight
    const largestDimension = Math.max(width, height)
    if (largestDimension > IMAGE_MAX_DIMENSION) {
      const scale = IMAGE_MAX_DIMENSION / largestDimension
      width = Math.round(width * scale)
      height = Math.round(height * scale)
    }

    const canvas = document.createElement("canvas")
    const context = canvas.getContext("2d")
    if (!context) {
      throw new Error("Image processing is not available in this browser")
    }

    let quality = 0.82
    let blob: Blob
    do {
      canvas.width = width
      canvas.height = height
      context.drawImage(image, 0, 0, width, height)
      blob = await canvasToBlob(canvas, quality)
      quality -= 0.12
    } while (blob.size > IMAGE_MAX_BYTES && quality >= 0.46)

    return await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onloadend = () => resolve(String(reader.result))
      reader.onerror = () => reject(new Error("Unable to save image thumbnail"))
      reader.readAsDataURL(blob)
    })
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

function parseAddressParts(rawAddress?: string | null) {
  if (!rawAddress) return { street: "", city: "", state: "", postalCode: "" }
  const parts = rawAddress.split(",").map((p) => p.trim()).filter(Boolean)
  if (parts.length >= 4) {
    return {
      street: parts.slice(0, parts.length - 3).join(", "),
      city: parts[parts.length - 3],
      state: parts[parts.length - 2],
      postalCode: parts[parts.length - 1],
    }
  } else if (parts.length === 3) {
    const lastPart = parts[2].trim()
    const stateZipMatch = lastPart.match(/^([A-Za-z\s]+)\s+([A-Za-z0-9-]+)$/)
    if (stateZipMatch) {
      return {
        street: parts[0],
        city: parts[1],
        state: stateZipMatch[1],
        postalCode: stateZipMatch[2],
      }
    }
    return {
      street: parts[0],
      city: parts[1],
      state: parts[2],
      postalCode: "",
    }
  } else if (parts.length === 2) {
    return {
      street: parts[0],
      city: parts[1],
      state: "",
      postalCode: "",
    }
  }
  return {
    street: rawAddress,
    city: "",
    state: "",
    postalCode: "",
  }
}

function composeAddress(street: string, city: string, state: string, postalCode: string): string {
  const cityStateZip = [
    city.trim(),
    [state.trim(), postalCode.trim()].filter(Boolean).join(" "),
  ]
    .filter(Boolean)
    .join(", ")

  if (street.trim() && cityStateZip) {
    return `${street.trim()}, ${cityStateZip}`
  }
  return [street.trim(), city.trim(), state.trim(), postalCode.trim()]
    .filter(Boolean)
    .join(", ")
}

export default function BusinessSettings() {
  const { multipleProvidersEnabled, locationsEnabled } = useTenantModules()

  // Business profile
  const [profile, setProfile] = useState<BusinessProfile | null>(null)

  // Solo provider state
  const [soloProvider, setSoloProvider] = useState<SoloProvider | null>(null)
  const [noProviderFound, setNoProviderFound] = useState(false)

  // Primary location state
  const [primaryLocation, setPrimaryLocation] = useState<PrimaryLocation | null>(null)
  const [noLocationFound, setNoLocationFound] = useState(false)
  const [locStreet, setLocStreet] = useState("")
  const [locCity, setLocCity] = useState("")
  const [locState, setLocState] = useState("")
  const [locPostalCode, setLocPostalCode] = useState("")

  const [loading, setLoading] = useState(true)
  const [saveState, setSaveState] = useState<SaveState>("idle")

  // Auto-save debounce and lifecycle refs
  const profileDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const providerDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const locationDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const savedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isInitialLoadedRef = useRef(false)
  const activeSaveCountRef = useRef(0)

  // Clean up timers on unmount
  useEffect(() => {
    return () => {
      if (profileDebounceRef.current) clearTimeout(profileDebounceRef.current)
      if (providerDebounceRef.current) clearTimeout(providerDebounceRef.current)
      if (locationDebounceRef.current) clearTimeout(locationDebounceRef.current)
      if (savedTimerRef.current) clearTimeout(savedTimerRef.current)
    }
  }, [])

  const handleSaveSuccess = () => {
    activeSaveCountRef.current = Math.max(0, activeSaveCountRef.current - 1)
    if (activeSaveCountRef.current === 0) {
      setSaveState("saved")
      if (savedTimerRef.current) clearTimeout(savedTimerRef.current)
      savedTimerRef.current = setTimeout(() => {
        setSaveState("idle")
      }, 2500)
    }
  }

  const handleSaveFailure = (errorMsg?: string) => {
    activeSaveCountRef.current = Math.max(0, activeSaveCountRef.current - 1)
    setSaveState("failed")
    if (errorMsg) {
      toast.error(errorMsg)
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // 1. Save Business Profile
  // ─────────────────────────────────────────────────────────────────────────────
  const executeSaveProfile = async (targetProfile: BusinessProfile) => {
    if (profileDebounceRef.current) clearTimeout(profileDebounceRef.current)
    activeSaveCountRef.current += 1
    setSaveState("saving")
    try {
      const payload: Record<string, any> = {
        name: targetProfile.name,
        email: targetProfile.email || null,
        phone: targetProfile.phone || null,
        address: targetProfile.address || null,
      }
      await apiClient.put("/api/admin/business-profile", payload)
      handleSaveSuccess()
    } catch (err: any) {
      const msg = err?.data?.detail || err?.message || "Failed to save business profile"
      handleSaveFailure(msg)
    }
  }

  const triggerDebouncedProfileSave = (targetProfile: BusinessProfile) => {
    if (!isInitialLoadedRef.current) return
    if (profileDebounceRef.current) clearTimeout(profileDebounceRef.current)
    setSaveState("saving")
    profileDebounceRef.current = setTimeout(() => {
      executeSaveProfile(targetProfile)
    }, 600)
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // 2. Save Solo Provider
  // ─────────────────────────────────────────────────────────────────────────────
  const executeSaveProvider = async (targetProv: SoloProvider) => {
    if (providerDebounceRef.current) clearTimeout(providerDebounceRef.current)
    activeSaveCountRef.current += 1
    setSaveState("saving")
    try {
      // Ensure tenant capabilities allow the provider capabilities before updating provider
      if (targetProv.allow_in_call || targetProv.allow_out_call) {
        await apiClient.put("/api/admin/business-profile", {
          ...(targetProv.allow_in_call ? { allow_in_call: true } : {}),
          ...(targetProv.allow_out_call ? { allow_out_call: true } : {}),
        })
      }

      const payload: Record<string, any> = {
        name: targetProv.name,
        email: targetProv.email || null,
        phone: targetProv.phone || null,
        description: targetProv.description || null,
        allow_in_call: targetProv.allow_in_call,
        allow_out_call: targetProv.allow_out_call,
        out_call_radius_km: Number(targetProv.out_call_radius_km) || 0,
        base_outcall_surcharge: Number(targetProv.base_outcall_surcharge) || 0,
        per_km_fee: Number(targetProv.per_km_fee) || 0,
        turnaround_buffer_mins: Number(targetProv.turnaround_buffer_mins) || 0,
      }
      if (targetProv.image !== undefined) {
        payload.image = targetProv.image || null
      }

      await apiClient.put(`/api/admin/providers/${targetProv.id}`, payload)
      handleSaveSuccess()
    } catch (err: any) {
      const msg = err?.data?.detail || err?.message || "Failed to save provider details"
      handleSaveFailure(msg)
    }
  }

  const triggerDebouncedProviderSave = (targetProv: SoloProvider) => {
    if (!isInitialLoadedRef.current) return
    if (providerDebounceRef.current) clearTimeout(providerDebounceRef.current)
    setSaveState("saving")
    providerDebounceRef.current = setTimeout(() => {
      executeSaveProvider(targetProv)
    }, 600)
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // 3. Save Primary Location
  // ─────────────────────────────────────────────────────────────────────────────
  const executeSaveLocation = async (targetLoc: PrimaryLocation, fullAddress: string) => {
    if (locationDebounceRef.current) clearTimeout(locationDebounceRef.current)
    activeSaveCountRef.current += 1
    setSaveState("saving")
    try {
      const payload: Record<string, any> = {
        name: targetLoc.name,
        address: fullAddress || null,
        timezone: targetLoc.timezone || "Australia/Melbourne",
        is_client_hidden: targetLoc.is_client_hidden ?? false,
      }
      if (targetLoc.image !== undefined) {
        payload.image = targetLoc.image || null
      }

      await apiClient.put(`/api/admin/locations/${targetLoc.id}`, payload)
      setPrimaryLocation((prev) => (prev ? { ...prev, address: fullAddress, image: targetLoc.image } : null))
      handleSaveSuccess()
    } catch (err: any) {
      const msg = err?.data?.detail || err?.message || "Failed to save location details"
      handleSaveFailure(msg)
    }
  }

  const triggerDebouncedLocationSave = (targetLoc: PrimaryLocation, fullAddress: string) => {
    if (!isInitialLoadedRef.current) return
    if (locationDebounceRef.current) clearTimeout(locationDebounceRef.current)
    setSaveState("saving")
    locationDebounceRef.current = setTimeout(() => {
      executeSaveLocation(targetLoc, fullAddress)
    }, 600)
  }

  // Retry action for AutoSaveStatus
  const handleRetry = () => {
    if (profile) executeSaveProfile(profile)
    if (!multipleProvidersEnabled && soloProvider) executeSaveProvider(soloProvider)
    if (!locationsEnabled && primaryLocation) {
      const combinedAddress = composeAddress(locStreet, locCity, locState, locPostalCode)
      executeSaveLocation(primaryLocation, combinedAddress)
    }
  }

  // Initial Data Fetch
  const fetchData = useCallback(async () => {
    setLoading(true)
    isInitialLoadedRef.current = false
    try {
      const [profileRes, provsRes, locsRes] = await Promise.all([
        apiClient.get<any>("/api/admin/business-profile").catch(() => null),
        apiClient.get<any>("/api/admin/providers").catch(() => null),
        apiClient.get<any>("/api/admin/locations").catch(() => null),
      ])

      // 1. Set Profile
      if (profileRes) {
        const p = profileRes.data || profileRes
        setProfile({
          name: p.name || "",
          email: p.email || "",
          phone: p.phone || "",
          address: p.address || "",
        })
      }

      // 2. Set Solo Provider
      const rawProviders = Array.isArray(provsRes) ? provsRes : (provsRes?.data ?? [])
      if (rawProviders.length > 0) {
        const firstProv = rawProviders[0]
        try {
          const fullProvRes = await apiClient.get<any>(`/api/admin/providers/${firstProv.id}`)
          const full = fullProvRes.data || fullProvRes
          setSoloProvider({
            id: full.id,
            name: full.name || "",
            email: full.email || "",
            phone: full.phone || "",
            description: full.description || "",
            image: full.image || "",
            avatar: full.avatar || full.image || "",
            allow_in_call: full.allow_in_call ?? true,
            allow_out_call: full.allow_out_call ?? true,
            out_call_radius_km: full.out_call_radius_km ?? 25,
            base_outcall_surcharge: full.base_outcall_surcharge ?? 0,
            per_km_fee: full.per_km_fee ?? 0,
            turnaround_buffer_mins: full.turnaround_buffer_mins ?? 15,
          })
          setNoProviderFound(false)
        } catch {
          setSoloProvider({
            id: firstProv.id,
            name: firstProv.name || "",
            email: firstProv.email || "",
            phone: firstProv.phone || "",
            description: firstProv.description || "",
            image: firstProv.image || "",
            avatar: firstProv.avatar || firstProv.image || "",
            allow_in_call: firstProv.allow_in_call ?? true,
            allow_out_call: firstProv.allow_out_call ?? true,
            out_call_radius_km: firstProv.out_call_radius_km ?? 25,
            base_outcall_surcharge: firstProv.base_outcall_surcharge ?? 0,
            per_km_fee: firstProv.per_km_fee ?? 0,
            turnaround_buffer_mins: firstProv.turnaround_buffer_mins ?? 15,
          })
          setNoProviderFound(false)
        }
      } else {
        setSoloProvider(null)
        setNoProviderFound(true)
      }

      // 3. Set Primary Location
      const rawLocations = Array.isArray(locsRes) ? locsRes : (locsRes?.data ?? [])
      if (rawLocations.length > 0) {
        const firstLoc = rawLocations[0]
        setPrimaryLocation({
          id: firstLoc.id,
          name: firstLoc.name || "",
          address: firstLoc.address || "",
          image: firstLoc.image || "",
          timezone: firstLoc.timezone || "Australia/Melbourne",
          is_client_hidden: firstLoc.is_client_hidden ?? false,
        })
        const parsed = parseAddressParts(firstLoc.address)
        setLocStreet(parsed.street)
        setLocCity(parsed.city)
        setLocState(parsed.state)
        setLocPostalCode(parsed.postalCode)
        setNoLocationFound(false)
      } else {
        setPrimaryLocation(null)
        setNoLocationFound(true)
      }
    } catch {
      toast.error("Failed to load business profile settings")
    } finally {
      setLoading(false)
      setTimeout(() => {
        isInitialLoadedRef.current = true
      }, 100)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Create Solo Provider if none exists
  const handleCreateSoloProvider = async () => {
    try {
      const payload = {
        name: profile?.name || "Primary Practitioner",
        email: profile?.email || null,
        phone: profile?.phone || null,
        allow_in_call: true,
        allow_out_call: true,
      }
      const res = await apiClient.post<any>("/api/admin/providers", payload)
      const created = res.data || res
      setSoloProvider({
        id: created.id,
        name: created.name,
        email: created.email || "",
        phone: created.phone || "",
        description: created.description || "",
        image: created.image || "",
        avatar: created.avatar || created.image || "",
        allow_in_call: created.allow_in_call ?? true,
        allow_out_call: created.allow_out_call ?? true,
        out_call_radius_km: created.out_call_radius_km ?? 25,
        base_outcall_surcharge: created.base_outcall_surcharge ?? 0,
        per_km_fee: created.per_km_fee ?? 0,
        turnaround_buffer_mins: created.turnaround_buffer_mins ?? 15,
      })
      setNoProviderFound(false)
      toast.success("Solo provider initialized")
    } catch (err: any) {
      toast.error(err?.message || "Failed to initialize solo provider")
    }
  }

  // Create Primary Location if none exists
  const handleCreatePrimaryLocation = async () => {
    try {
      const combinedAddress = composeAddress(locStreet, locCity, locState, locPostalCode)
      const payload = {
        name: profile?.name ? `${profile.name} (Main Studio)` : "Primary Location",
        address: combinedAddress || profile?.address || null,
        timezone: "Australia/Melbourne",
        is_client_hidden: false,
      }
      const res = await apiClient.post<any>("/api/admin/locations", payload)
      const created = res.data || res
      setPrimaryLocation({
        id: created.id,
        name: created.name,
        address: created.address || "",
        image: created.image || "",
        timezone: created.timezone || "Australia/Melbourne",
        is_client_hidden: created.is_client_hidden ?? false,
      })
      setNoLocationFound(false)
      toast.success("Primary location initialized")
    } catch (err: any) {
      toast.error(err?.message || "Failed to initialize primary location")
    }
  }

  // Copy Contact Info (Name, Email, Phone) into Solo Provider
  const handleCopyBusinessToProvider = () => {
    if (!profile || !soloProvider) return
    const updatedSolo: SoloProvider = {
      ...soloProvider,
      name: profile.name || soloProvider.name,
      email: profile.email || soloProvider.email,
      phone: profile.phone || soloProvider.phone,
    }
    setSoloProvider(updatedSolo)
    executeSaveProvider(updatedSolo)
    toast.success("Copied contact details (name, email, phone) to provider")
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      </div>
    )
  }

  if (!profile) return null

  const hasSoloProvider = !multipleProvidersEnabled
  const hasPrimaryLocation = !locationsEnabled

  // ==========================================================================
  // SECTION 1: Business Profile Card
  // ==========================================================================
  const renderBusinessProfileCard = () => (
    <Card className="shadow-xs">
      <CardHeader className="pb-3">
        <CardTitle className="text-base sm:text-lg flex items-center gap-2">
          <Building className="h-4 w-4 text-primary" />
          <span>Contact Details</span>
        </CardTitle>
        <CardDescription className="text-xs">
          Primary details shown on your public booking portal, client receipts, and communications
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label
            htmlFor="name"
            className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
          >
            Business / Operator / Owner Name
          </Label>
          <Input
            id="name"
            value={profile.name}
            onChange={(e) => {
              const updated = { ...profile, name: e.target.value }
              setProfile(updated)
              triggerDebouncedProfileSave(updated)
            }}
            placeholder="e.g. Elena Rostova / Lumina Studio"
            className="h-11 min-h-[44px]"
          />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label
              htmlFor="email"
              className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              Email Address
            </Label>
            <Input
              id="email"
              type="email"
              value={profile.email}
              onChange={(e) => {
                const updated = { ...profile, email: e.target.value }
                setProfile(updated)
                triggerDebouncedProfileSave(updated)
              }}
              placeholder="contact@business.com"
              className="h-11 min-h-[44px]"
            />
          </div>
          <div className="space-y-1.5">
            <Label
              htmlFor="phone"
              className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              Phone Number
            </Label>
            <Input
              id="phone"
              value={profile.phone}
              onChange={(e) => {
                const updated = { ...profile, phone: e.target.value }
                setProfile(updated)
                triggerDebouncedProfileSave(updated)
              }}
              placeholder="+61 400 000 000"
              className="h-11 min-h-[44px]"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <AddressAutocomplete
            id="address"
            label="Business HQ / Physical Address"
            value={profile.address}
            onChange={(formatted) => {
              const updated = { ...profile, address: formatted }
              setProfile(updated)
              executeSaveProfile(updated)
            }}
            placeholder="Search verified business address..."
            helperText="Standardized physical headquarters address used for receipts and company legal records."
          />
        </div>
      </CardContent>
    </Card>
  )

  // ==========================================================================
  // SECTION 2: Solo Provider Details Card
  // ==========================================================================
  const renderSoloProviderCard = () => (
    <Card className="shadow-xs border-primary/25 bg-card">
      <CardHeader className="pb-3 border-b bg-muted/15">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <CardTitle className="text-base sm:text-lg flex items-center gap-2">
                <User className="h-4 w-4 text-primary" />
                <span>Solo Service Provider Details</span>
              </CardTitle>
              <Badge variant="secondary" className="text-[11px] font-normal tracking-tight">
                Solo Mode
              </Badge>
            </div>
            <CardDescription className="text-xs mt-1">
              Directly manages your single practitioner profile, photo, bio, in-call studio, and travel parameters
            </CardDescription>
          </div>
          {soloProvider && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyBusinessToProvider}
              className="h-8 text-xs text-muted-foreground hover:text-foreground touch-manipulation gap-1.5"
              title="Copy business operator name, email, and phone into provider settings"
            >
              <Copy className="h-3.5 w-3.5" />
              <span>Copy Contact Info</span>
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-5 pt-4">
        {noProviderFound ? (
          <div className="p-4 border border-dashed rounded-lg text-center space-y-3 bg-muted/10">
            <p className="text-sm text-muted-foreground">
              No solo provider record found for this account. Create one to enable appointment bookings.
            </p>
            <Button
              size="sm"
              onClick={handleCreateSoloProvider}
              className="gap-2"
            >
              <Plus className="h-4 w-4" />
              <span>Initialize Solo Provider</span>
            </Button>
          </div>
        ) : soloProvider ? (
          <>
            {/* Provider Photo / Avatar (Compact) */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Provider Photo / Avatar
              </Label>
              <div className="flex items-center gap-3 p-3 rounded-lg border bg-muted/10">
                <div className="relative shrink-0">
                  {soloProvider.image ? (
                    <img
                      src={soloProvider.image}
                      alt={soloProvider.name}
                      className="w-14 h-14 rounded-full object-cover border-2 border-primary/20 shadow-xs"
                    />
                  ) : (
                    <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center text-primary font-semibold text-base border border-dashed border-primary/30">
                      {soloProvider.name ? soloProvider.name.charAt(0).toUpperCase() : <User className="h-6 w-6" />}
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="file"
                      id="solo-provider-image-input"
                      accept="image/*"
                      className="hidden"
                      onChange={async (e) => {
                        const file = e.target.files?.[0]
                        if (!file) return
                        try {
                          const thumbnail = await createImageThumbnail(file)
                          const updated = { ...soloProvider, image: thumbnail }
                          setSoloProvider(updated)
                          executeSaveProvider(updated)
                          toast.success("Provider photo updated")
                        } catch (err: any) {
                          toast.error(err.message || "Failed to upload image")
                        }
                      }}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => document.getElementById("solo-provider-image-input")?.click()}
                      className="h-8 text-xs gap-1.5 touch-manipulation"
                    >
                      <Upload className="h-3.5 w-3.5" />
                      <span>{soloProvider.image ? "Change Photo" : "Upload Photo"}</span>
                    </Button>
                    {soloProvider.image && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          const updated = { ...soloProvider, image: "" }
                          setSoloProvider(updated)
                          executeSaveProvider(updated)
                          toast.success("Provider photo removed")
                        }}
                        className="h-8 text-xs text-destructive hover:text-destructive hover:bg-destructive/10"
                      >
                        <X className="h-3.5 w-3.5 mr-1" />
                        Remove
                      </Button>
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Avatar shown to clients on booking cards & messages (JPG, PNG, WEBP)
                  </p>
                </div>
              </div>
            </div>

            {/* Basic Solo Provider Info */}
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label
                  htmlFor="solo-provider-name"
                  className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                >
                  Provider / Practitioner Name *
                </Label>
                <Input
                  id="solo-provider-name"
                  value={soloProvider.name}
                  onChange={(e) => {
                    const updated = { ...soloProvider, name: e.target.value }
                    setSoloProvider(updated)
                    triggerDebouncedProviderSave(updated)
                  }}
                  placeholder="e.g. Dr. Jane Smith / Sarah"
                  className="h-11 min-h-[44px]"
                />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label
                    htmlFor="solo-provider-email"
                    className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    Direct Provider Email
                  </Label>
                  <Input
                    id="solo-provider-email"
                    type="email"
                    value={soloProvider.email || ""}
                    onChange={(e) => {
                      const updated = { ...soloProvider, email: e.target.value }
                      setSoloProvider(updated)
                      triggerDebouncedProviderSave(updated)
                    }}
                    placeholder="practitioner@business.com"
                    className="h-11 min-h-[44px]"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label
                    htmlFor="solo-provider-phone"
                    className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    Direct Provider Phone
                  </Label>
                  <Input
                    id="solo-provider-phone"
                    value={soloProvider.phone || ""}
                    onChange={(e) => {
                      const updated = { ...soloProvider, phone: e.target.value }
                      setSoloProvider(updated)
                      triggerDebouncedProviderSave(updated)
                    }}
                    placeholder="+61 400 123 456"
                    className="h-11 min-h-[44px]"
                  />
                </div>
              </div>
            </div>

            {/* Bio / Description */}
            <div className="space-y-1.5">
              <Label
                htmlFor="solo-provider-bio"
                className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Bio / Professional Description
              </Label>
              <Textarea
                id="solo-provider-bio"
                rows={3}
                value={soloProvider.description || ""}
                onChange={(e) => {
                  const updated = { ...soloProvider, description: e.target.value }
                  setSoloProvider(updated)
                  triggerDebouncedProviderSave(updated)
                }}
                placeholder="Write a brief introduction, specialties, or practitioner credentials for client viewing..."
                className="min-h-[80px]"
              />
            </div>

            {/* Out-Call & Capability Parameters */}
            <div className="p-4 rounded-xl border bg-muted/20 space-y-4">
              <div className="flex items-center justify-between pb-2 border-b">
                <div className="flex items-center gap-2">
                  <Car className="h-4 w-4 text-primary" />
                  <h4 className="text-sm font-semibold text-foreground">
                    Service Delivery Capabilities & Travel Settings
                  </h4>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* In-Call toggle */}
                <div className="flex items-center justify-between p-3 rounded-lg border bg-card/60">
                  <div className="space-y-0.5">
                    <Label htmlFor="allow-in-call" className="text-sm font-medium cursor-pointer">
                      Allow In-Call Studio Bookings
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Clients visit your physical location
                    </p>
                  </div>
                  <Switch
                    id="allow-in-call"
                    checked={soloProvider.allow_in_call}
                    onCheckedChange={(checked) => {
                      const updated = { ...soloProvider, allow_in_call: checked }
                      setSoloProvider(updated)
                      executeSaveProvider(updated)
                    }}
                  />
                </div>

                {/* Out-Call toggle */}
                <div className="flex items-center justify-between p-3 rounded-lg border bg-card/60">
                  <div className="space-y-0.5">
                    <Label htmlFor="allow-out-call" className="text-sm font-medium cursor-pointer">
                      Allow Out-Call Mobile Bookings
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      You travel to the client's address
                    </p>
                  </div>
                  <Switch
                    id="allow-out-call"
                    checked={soloProvider.allow_out_call}
                    onCheckedChange={(checked) => {
                      const updated = { ...soloProvider, allow_out_call: checked }
                      setSoloProvider(updated)
                      executeSaveProvider(updated)
                    }}
                  />
                </div>
              </div>

              {soloProvider.allow_out_call && (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-2">
                    <div className="space-y-1.5">
                      <Label
                        htmlFor="out-call-radius"
                        className="text-xs font-semibold text-muted-foreground flex items-center gap-1"
                      >
                        <Sparkles className="h-3 w-3 text-primary" />
                        <span>Max Radius (km)</span>
                      </Label>
                      <Input
                        id="out-call-radius"
                        type="number"
                        min={0}
                        step={1}
                        value={soloProvider.out_call_radius_km}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value) || 0
                          const updated = { ...soloProvider, out_call_radius_km: val }
                          setSoloProvider(updated)
                          triggerDebouncedProviderSave(updated)
                        }}
                        className="h-10 min-h-[40px]"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <Label
                        htmlFor="out-call-surcharge"
                        className="text-xs font-semibold text-muted-foreground flex items-center gap-1"
                      >
                        <DollarSign className="h-3 w-3 text-primary" />
                        <span>Base Surcharge ($)</span>
                      </Label>
                      <Input
                        id="out-call-surcharge"
                        type="number"
                        min={0}
                        step={0.01}
                        value={soloProvider.base_outcall_surcharge}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value) || 0
                          const updated = { ...soloProvider, base_outcall_surcharge: val }
                          setSoloProvider(updated)
                          triggerDebouncedProviderSave(updated)
                        }}
                        className="h-10 min-h-[40px]"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <Label
                        htmlFor="out-call-per-km"
                        className="text-xs font-semibold text-muted-foreground flex items-center gap-1"
                      >
                        <DollarSign className="h-3 w-3 text-primary" />
                        <span>Per-KM Fee ($)</span>
                      </Label>
                      <Input
                        id="out-call-per-km"
                        type="number"
                        min={0}
                        step={0.01}
                        value={soloProvider.per_km_fee}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value) || 0
                          const updated = { ...soloProvider, per_km_fee: val }
                          setSoloProvider(updated)
                          triggerDebouncedProviderSave(updated)
                        }}
                        className="h-10 min-h-[40px]"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <Label
                        htmlFor="out-call-buffer"
                        className="text-xs font-semibold text-muted-foreground flex items-center gap-1"
                      >
                        <Clock className="h-3 w-3 text-primary" />
                        <span>Turnaround Buffer (mins)</span>
                      </Label>
                      <Input
                        id="out-call-buffer"
                        type="number"
                        min={0}
                        step={5}
                        value={soloProvider.turnaround_buffer_mins}
                        onChange={(e) => {
                          const val = parseInt(e.target.value, 10) || 0
                          const updated = { ...soloProvider, turnaround_buffer_mins: val }
                          setSoloProvider(updated)
                          triggerDebouncedProviderSave(updated)
                        }}
                        className="h-10 min-h-[40px]"
                      />
                      <p className="text-[11px] text-muted-foreground">
                        Buffer between bookings (applied in addition to road driving time).
                      </p>
                    </div>
                  </div>

                  {/* 5-Segment Operational Model Explainer */}
                  <div className="p-3.5 rounded-lg border bg-blue-50/50 dark:bg-blue-950/20 text-xs space-y-2 mt-2">
                    <div className="flex items-center gap-1.5 font-semibold text-blue-900 dark:text-blue-300">
                      <Info className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0" />
                      <span>5-Segment Operational Travel & Buffer Architecture</span>
                    </div>
                    <div className="space-y-1 text-muted-foreground text-[11px] leading-relaxed">
                      <p>
                        • <strong>Travel Time</strong> is dynamically calculated and reserved based on actual driving distance to/from this address.
                      </p>
                      <p>
                        • <strong>Buffer Times</strong> (Turnaround, Pre-Service Prep & Post-Service Pack-up) are <strong>in addition to travel time</strong>, ensuring dedicated time to park, enter, unpack, sanitize, and pack up without eating into client appointment time or driving transit.
                      </p>
                    </div>
                  </div>
                </>
              )}
            </div>
          </>
        ) : null}
      </CardContent>
    </Card>
  )

  // ==========================================================================
  // SECTION 3: Primary Location Details Card
  // ==========================================================================
  const renderPrimaryLocationCard = () => (
    <Card className="shadow-xs border-primary/25 bg-card">
      <CardHeader className="pb-3 border-b bg-muted/15">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <MapPin className="h-4 w-4 text-primary" />
              <span>Primary Location Details</span>
            </div>
            <CardDescription className="text-xs mt-1">
              Configures your primary clinic or studio address, photo, timezone, and live map
            </CardDescription>
          </div>
          <Badge variant="secondary" className="text-[11px] font-normal tracking-tight">
            Single Location Mode
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-4">
        {noLocationFound ? (
          <div className="p-4 border border-dashed rounded-lg text-center space-y-3 bg-muted/10">
            <p className="text-sm text-muted-foreground">
              No primary location record found. Create one to anchor your calendar and appointments.
            </p>
            <Button
              size="sm"
              onClick={handleCreatePrimaryLocation}
              className="gap-2"
            >
              <Plus className="h-4 w-4" />
              <span>Initialize Primary Location</span>
            </Button>
          </div>
        ) : primaryLocation ? (
          <>
            {/* Location Photo (Compact) */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Location Studio Photo
              </Label>
              <div className="flex items-center gap-3 p-3 rounded-lg border bg-muted/10">
                <div className="relative shrink-0">
                  {primaryLocation.image ? (
                    <img
                      src={primaryLocation.image}
                      alt={primaryLocation.name}
                      className="w-16 h-14 rounded-lg object-cover border shadow-xs"
                    />
                  ) : (
                    <div className="w-16 h-14 rounded-lg bg-muted/40 flex items-center justify-center text-muted-foreground border border-dashed">
                      <MapPin className="h-5 w-5" />
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="file"
                      id="location-image-input"
                      accept="image/*"
                      className="hidden"
                      onChange={async (e) => {
                        const file = e.target.files?.[0]
                        if (!file) return
                        try {
                          const thumbnail = await createImageThumbnail(file)
                          const updated = { ...primaryLocation, image: thumbnail }
                          setPrimaryLocation(updated)
                          executeSaveLocation(updated, composeAddress(locStreet, locCity, locState, locPostalCode))
                          toast.success("Location photo updated")
                        } catch (err: any) {
                          toast.error(err.message || "Failed to upload image")
                        }
                      }}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => document.getElementById("location-image-input")?.click()}
                      className="h-8 text-xs gap-1.5 touch-manipulation"
                    >
                      <Upload className="h-3.5 w-3.5" />
                      <span>{primaryLocation.image ? "Change Photo" : "Upload Photo"}</span>
                    </Button>
                    {primaryLocation.image && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          const updated = { ...primaryLocation, image: "" }
                          setPrimaryLocation(updated)
                          executeSaveLocation(updated, composeAddress(locStreet, locCity, locState, locPostalCode))
                          toast.success("Location photo removed")
                        }}
                        className="h-8 text-xs text-destructive hover:text-destructive hover:bg-destructive/10"
                      >
                        <X className="h-3.5 w-3.5 mr-1" />
                        Remove
                      </Button>
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Storefront or clinic entrance photo shown to clients (JPG, PNG, WEBP)
                  </p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label
                  htmlFor="primary-location-name"
                  className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                >
                  Location / Branch Name *
                </Label>
                <Input
                  id="primary-location-name"
                  value={primaryLocation.name}
                  onChange={(e) => {
                    const updated = { ...primaryLocation, name: e.target.value }
                    setPrimaryLocation(updated)
                    triggerDebouncedLocationSave(updated, composeAddress(locStreet, locCity, locState, locPostalCode))
                  }}
                  placeholder="e.g. Downtown Studio / Main Clinic"
                  className="h-11 min-h-[44px]"
                />
              </div>

              <div className="space-y-1.5">
                <Label
                  htmlFor="primary-location-timezone"
                  className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                >
                  Timezone
                </Label>
                <Select
                  value={primaryLocation.timezone || "Australia/Melbourne"}
                  onValueChange={(val) => {
                    const updated = { ...primaryLocation, timezone: val }
                    setPrimaryLocation(updated)
                    executeSaveLocation(updated, composeAddress(locStreet, locCity, locState, locPostalCode))
                  }}
                >
                  <SelectTrigger id="primary-location-timezone" className="h-11 min-h-[44px] w-full">
                    <SelectValue placeholder="Select timezone" />
                  </SelectTrigger>
                  <SelectContent>
                    {POPULAR_TIMEZONES.map((tz) => (
                      <SelectItem key={tz.value} value={tz.value}>
                        {tz.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Physical Location Address */}
            <div className="space-y-3 p-4 rounded-xl border bg-muted/10">
              <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Physical Location Address
              </Label>

              <AddressAutocomplete
                id="loc-autocomplete"
                value={composeAddress(locStreet, locCity, locState, locPostalCode)}
                onChange={(formatted, structured) => {
                  let newStreet = ""
                  let newCity = ""
                  let newState = ""
                  let newPostal = ""
                  if (structured) {
                    newStreet = structured.street_address || formatted.split(",")[0] || ""
                    newCity = structured.suburb || ""
                    newState = structured.state || ""
                    newPostal = structured.postcode || ""
                  } else {
                    const parsed = parseAddressParts(formatted)
                    newStreet = parsed.street
                    newCity = parsed.city
                    newState = parsed.state
                    newPostal = parsed.postalCode
                  }
                  setLocStreet(newStreet)
                  setLocCity(newCity)
                  setLocState(newState)
                  setLocPostalCode(newPostal)
                  const combined = composeAddress(newStreet, newCity, newState, newPostal) || formatted
                  executeSaveLocation(primaryLocation, combined)
                }}
                placeholder="Search verified location street address..."
                noticeText="This is the location that will be used to calculate outcall travel times and travel requirements."
              />

              <div className="pt-2 border-t space-y-2">
                <p className="text-[11px] font-medium text-muted-foreground">
                  Detailed Address Breakdown (auto-populated via address search or manual override):
                </p>
                <div className="space-y-1.5">
                  <Label htmlFor="loc-street" className="text-xs text-muted-foreground">
                    Street Address
                  </Label>
                  <Input
                    id="loc-street"
                    value={locStreet}
                    onChange={(e) => {
                      const nextStreet = e.target.value
                      setLocStreet(nextStreet)
                      triggerDebouncedLocationSave(
                        primaryLocation,
                        composeAddress(nextStreet, locCity, locState, locPostalCode)
                      )
                    }}
                    placeholder="e.g. 73 Market Street"
                    className="h-10 min-h-[40px]"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="loc-city" className="text-xs text-muted-foreground">
                      City / Suburb
                    </Label>
                    <Input
                      id="loc-city"
                      value={locCity}
                      onChange={(e) => {
                        const nextCity = e.target.value
                        setLocCity(nextCity)
                        triggerDebouncedLocationSave(
                          primaryLocation,
                          composeAddress(locStreet, nextCity, locState, locPostalCode)
                        )
                      }}
                      placeholder="e.g. Sydney"
                      className="h-10 min-h-[40px]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="loc-state" className="text-xs text-muted-foreground">
                      State / Province
                    </Label>
                    <Input
                      id="loc-state"
                      value={locState}
                      onChange={(e) => {
                        const nextState = e.target.value
                        setLocState(nextState)
                        triggerDebouncedLocationSave(
                          primaryLocation,
                          composeAddress(locStreet, locCity, nextState, locPostalCode)
                        )
                      }}
                      placeholder="e.g. NSW"
                      className="h-10 min-h-[40px]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="loc-postcode" className="text-xs text-muted-foreground">
                      Postal Code
                    </Label>
                    <Input
                      id="loc-postcode"
                      value={locPostalCode}
                      onChange={(e) => {
                        const nextPostal = e.target.value
                        setLocPostalCode(nextPostal)
                        triggerDebouncedLocationSave(
                          primaryLocation,
                          composeAddress(locStreet, locCity, locState, nextPostal)
                        )
                      }}
                      placeholder="e.g. 2000"
                      className="h-10 min-h-[40px]"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Public Directory Visibility Toggle placed directly under address */}
            <div className="flex items-center justify-between p-3.5 rounded-lg border bg-muted/20">
              <div className="space-y-0.5 pr-4">
                <div className="flex items-center gap-1.5">
                  <EyeOff className="h-4 w-4 text-muted-foreground" />
                  <Label htmlFor="loc-is-client-hidden" className="text-xs font-semibold cursor-pointer">
                    Discreet / Private Location
                  </Label>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Hide full street address from public booking cards until appointment confirmation
                </p>
              </div>
              <Switch
                id="loc-is-client-hidden"
                checked={primaryLocation.is_client_hidden ?? false}
                onCheckedChange={(checked) => {
                  const updated = { ...primaryLocation, is_client_hidden: checked }
                  setPrimaryLocation(updated)
                  executeSaveLocation(updated, composeAddress(locStreet, locCity, locState, locPostalCode))
                }}
              />
            </div>

            {/* Live Google Map Preview (Derived from Address) */}
            <div className="space-y-1.5 pt-1">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                <Globe className="h-3.5 w-3.5 text-primary" />
                <span>Live Location Map (Derived from Address)</span>
              </div>
              <div className="w-full h-[180px] rounded-lg overflow-hidden border bg-muted/20 relative shadow-inner">
                <iframe
                  title="Location Map Preview"
                  width="100%"
                  height="100%"
                  style={{ border: 0 }}
                  loading="lazy"
                  src={`https://maps.google.com/maps?q=${encodeURIComponent(
                    composeAddress(locStreet, locCity, locState, locPostalCode) || profile.address || "Australia"
                  )}&t=&z=14&ie=UTF8&iwloc=&output=embed`}
                />
              </div>
            </div>
          </>
        ) : null}
      </CardContent>
    </Card>
  )

  // Layout presentation: Responsive side-by-side grid
  return (
    <MobilePageShell
      title="Business Profile"
      description="Manage business operator details, solo provider profile, and primary location"
      actions={<AutoSaveStatus state={saveState} onRetry={handleRetry} />}
    >
      {!hasSoloProvider && !hasPrimaryLocation ? (
        <div className="max-w-2xl mx-auto">
          {renderBusinessProfileCard()}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          {/* Column 1 */}
          <div className="space-y-6">
            {renderBusinessProfileCard()}
            {hasSoloProvider && hasPrimaryLocation && renderPrimaryLocationCard()}
          </div>

          {/* Column 2 */}
          <div className="space-y-6">
            {hasSoloProvider && renderSoloProviderCard()}
            {!hasSoloProvider && hasPrimaryLocation && renderPrimaryLocationCard()}
          </div>
        </div>
      )}
    </MobilePageShell>
  )
}
