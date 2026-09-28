import { useEffect, useState, useCallback } from "react"
import { apiClient } from "@/lib/api"
import { useTenantModules } from "@/context/tenant-modules-context"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
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
import {
  Save,
  User,
  MapPin,
  Building,
  Car,
  Clock,
  DollarSign,
  EyeOff,
  Copy,
  Plus,
  Loader2,
  Sparkles,
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
  in_call_address?: string
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
  const [savingAll, setSavingAll] = useState(false)
  const [savingProfile, setSavingProfile] = useState(false)
  const [savingProvider, setSavingProvider] = useState(false)
  const [savingLocation, setSavingLocation] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
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
          // Fetch full provider record to ensure all out-call and in-call fields are retrieved
          const fullProvRes = await apiClient.get<any>(`/api/admin/providers/${firstProv.id}`)
          const full = fullProvRes.data || fullProvRes
          setSoloProvider({
            id: full.id,
            name: full.name || "",
            email: full.email || "",
            phone: full.phone || "",
            description: full.description || "",
            in_call_address: full.in_call_address || "",
            allow_in_call: full.allow_in_call ?? true,
            allow_out_call: full.allow_out_call ?? true,
            out_call_radius_km: full.out_call_radius_km ?? 25,
            base_outcall_surcharge: full.base_outcall_surcharge ?? 0,
            per_km_fee: full.per_km_fee ?? 0,
            turnaround_buffer_mins: full.turnaround_buffer_mins ?? 15,
          })
          setNoProviderFound(false)
        } catch {
          // Fallback to list item if single-fetch fails
          setSoloProvider({
            id: firstProv.id,
            name: firstProv.name || "",
            email: firstProv.email || "",
            phone: firstProv.phone || "",
            description: firstProv.description || "",
            in_call_address: firstProv.in_call_address || "",
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
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Save Business Profile
  const handleSaveProfile = async (silent = false) => {
    if (!profile) return
    setSavingProfile(true)
    try {
      const payload: Record<string, any> = {
        name: profile.name,
        email: profile.email || null,
        phone: profile.phone || null,
        address: profile.address || null,
      }
      // If in solo mode, align tenant capabilities with solo provider
      if (!multipleProvidersEnabled && soloProvider) {
        payload.allow_in_call = soloProvider.allow_in_call
        payload.allow_out_call = soloProvider.allow_out_call
      }
      await apiClient.put("/api/admin/business-profile", payload)
      if (!silent) toast.success("Business profile saved successfully")
    } catch (err: any) {
      const msg = err?.data?.detail || err?.message || "Failed to save profile"
      toast.error(msg)
      throw err
    } finally {
      setSavingProfile(false)
    }
  }

  // Save Solo Provider
  const handleSaveProvider = async (silent = false) => {
    if (!soloProvider) return
    setSavingProvider(true)
    try {
      // First ensure tenant capabilities permit provider capabilities
      if (profile) {
        await apiClient.put("/api/admin/business-profile", {
          allow_in_call: soloProvider.allow_in_call,
          allow_out_call: soloProvider.allow_out_call,
        })
      }
      const payload = {
        name: soloProvider.name,
        email: soloProvider.email || null,
        phone: soloProvider.phone || null,
        description: soloProvider.description || null,
        in_call_address: soloProvider.in_call_address || null,
        allow_in_call: soloProvider.allow_in_call,
        allow_out_call: soloProvider.allow_out_call,
        out_call_radius_km: Number(soloProvider.out_call_radius_km) || 0,
        base_outcall_surcharge: Number(soloProvider.base_outcall_surcharge) || 0,
        per_km_fee: Number(soloProvider.per_km_fee) || 0,
        turnaround_buffer_mins: Number(soloProvider.turnaround_buffer_mins) || 0,
      }
      await apiClient.put(`/api/admin/providers/${soloProvider.id}`, payload)
      if (!silent) toast.success("Solo provider details saved successfully")
    } catch (err: any) {
      const msg = err?.data?.detail || err?.message || "Failed to save provider details"
      toast.error(msg)
      throw err
    } finally {
      setSavingProvider(false)
    }
  }

  // Save Primary Location
  const handleSaveLocation = async (silent = false) => {
    if (!primaryLocation) return
    setSavingLocation(true)
    try {
      const combinedAddress = composeAddress(locStreet, locCity, locState, locPostalCode)
      const payload = {
        name: primaryLocation.name,
        address: combinedAddress || null,
        timezone: primaryLocation.timezone || "Australia/Melbourne",
        is_client_hidden: primaryLocation.is_client_hidden ?? false,
      }
      await apiClient.put(`/api/admin/locations/${primaryLocation.id}`, payload)
      setPrimaryLocation((prev) => (prev ? { ...prev, address: combinedAddress } : null))
      if (!silent) toast.success("Primary location details saved successfully")
    } catch (err: any) {
      const msg = err?.data?.detail || err?.message || "Failed to save location details"
      toast.error(msg)
      throw err
    } finally {
      setSavingLocation(false)
    }
  }

  // Save All Active Sections
  const handleSaveAll = async () => {
    setSavingAll(true)
    try {
      const tasks: Promise<any>[] = []
      if (profile) tasks.push(handleSaveProfile(true))
      if (!multipleProvidersEnabled && soloProvider) tasks.push(handleSaveProvider(true))
      if (!locationsEnabled && primaryLocation) tasks.push(handleSaveLocation(true))

      await Promise.all(tasks)
      toast.success("All settings saved successfully")
    } catch {
      // Individual error toasts handled inside save methods
    } finally {
      setSavingAll(false)
    }
  }

  // Create Solo Provider if none exists
  const handleCreateSoloProvider = async () => {
    try {
      const payload = {
        name: profile?.name || "Primary Practitioner",
        email: profile?.email || null,
        phone: profile?.phone || null,
        in_call_address: profile?.address || null,
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
        in_call_address: created.in_call_address || "",
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
        timezone: created.timezone || "Australia/Melbourne",
        is_client_hidden: created.is_client_hidden ?? false,
      })
      setNoLocationFound(false)
      toast.success("Primary location initialized")
    } catch (err: any) {
      toast.error(err?.message || "Failed to initialize primary location")
    }
  }

  const updateProfileField = (field: keyof BusinessProfile, value: string) => {
    if (profile) setProfile({ ...profile, [field]: value })
  }

  const updateSoloProviderField = (field: keyof SoloProvider, value: any) => {
    if (soloProvider) setSoloProvider({ ...soloProvider, [field]: value })
  }

  const updatePrimaryLocationField = (field: keyof PrimaryLocation, value: any) => {
    if (primaryLocation) setPrimaryLocation({ ...primaryLocation, [field]: value })
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-72 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    )
  }

  if (!profile) return null

  const isSavingAny = savingAll || savingProfile || savingProvider || savingLocation

  return (
    <MobilePageShell
      title="Business Profile"
      description="Manage business operator details, solo provider profile, and primary location"
      actions={
        <Button
          onClick={handleSaveAll}
          disabled={isSavingAny}
          className="h-10 min-h-[44px] w-full sm:w-auto touch-manipulation gap-2 shadow-xs"
        >
          {savingAll ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          <span>{savingAll ? "Saving All..." : "Save All Changes"}</span>
        </Button>
      }
    >
      <div className="space-y-6">
        {/* ==================================================================== */}
        {/* SECTION 1: Contact Details                                           */}
        {/* ==================================================================== */}
        <Card className="shadow-xs">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base sm:text-lg flex items-center gap-2">
                  <Building className="h-4 w-4 text-primary" />
                  <span>Contact Details</span>
                </CardTitle>
                <CardDescription className="text-xs">
                  Primary details shown on your public booking portal, client receipts, and communications
                </CardDescription>
              </div>
            </div>
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
                onChange={(e) => updateProfileField("name", e.target.value)}
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
                  onChange={(e) => updateProfileField("email", e.target.value)}
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
                  onChange={(e) => updateProfileField("phone", e.target.value)}
                  placeholder="+61 400 000 000"
                  className="h-11 min-h-[44px]"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label
                htmlFor="address"
                className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Business HQ / Physical Address
              </Label>
              <Input
                id="address"
                value={profile.address}
                onChange={(e) => updateProfileField("address", e.target.value)}
                placeholder="e.g. Suite 4, 120 Collins St, Melbourne VIC 3000"
                className="h-11 min-h-[44px]"
              />
            </div>
          </CardContent>
          <CardFooter className="justify-end border-t pt-3 pb-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleSaveProfile(false)}
              disabled={isSavingAny}
              className="h-9 min-h-[38px] touch-manipulation gap-1.5 text-xs font-medium"
            >
              {savingProfile ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              <span>Save Business Details</span>
            </Button>
          </CardFooter>
        </Card>

        {/* ==================================================================== */}
        {/* SECTION 2: Solo Provider Details Panel                               */}
        {/* Shown only when Multiple Service Providers module is OFF             */}
        {/* ==================================================================== */}
        {!multipleProvidersEnabled && (
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
                    Directly manages your single practitioner profile, bio, in-call studio, and mobile out-call parameters
                  </CardDescription>
                </div>
                {soloProvider && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      if (profile.name && soloProvider) {
                        updateSoloProviderField("name", profile.name)
                        toast.success("Synchronized name with Operator Name")
                      }
                    }}
                    className="h-8 text-xs text-muted-foreground hover:text-foreground touch-manipulation gap-1"
                    title="Copy operator name into provider name"
                  >
                    <Copy className="h-3.5 w-3.5" />
                    <span>Sync with Operator Name</span>
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
                    disabled={isSavingAny}
                    className="gap-2"
                  >
                    <Plus className="h-4 w-4" />
                    <span>Initialize Solo Provider</span>
                  </Button>
                </div>
              ) : soloProvider ? (
                <>
                  {/* Basic Solo Provider Info */}
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
                        onChange={(e) => updateSoloProviderField("name", e.target.value)}
                        placeholder="e.g. Dr. Jane Smith / Sarah"
                        className="h-11 min-h-[44px]"
                      />
                    </div>
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
                        onChange={(e) => updateSoloProviderField("email", e.target.value)}
                        placeholder="practitioner@business.com"
                        className="h-11 min-h-[44px]"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
                        onChange={(e) => updateSoloProviderField("phone", e.target.value)}
                        placeholder="+61 400 123 456"
                        className="h-11 min-h-[44px]"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Label
                          htmlFor="solo-in-call-address"
                          className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                        >
                          In-Call Studio / Appointment Address
                        </Label>
                        {profile.address && (
                          <button
                            type="button"
                            onClick={() => {
                              updateSoloProviderField("in_call_address", profile.address)
                              toast.success("Applied business address")
                            }}
                            className="text-[11px] text-primary hover:underline font-medium"
                          >
                            Use Business Address
                          </button>
                        )}
                      </div>
                      <Input
                        id="solo-in-call-address"
                        value={soloProvider.in_call_address || ""}
                        onChange={(e) => updateSoloProviderField("in_call_address", e.target.value)}
                        placeholder="e.g. Suite 4, 120 Collins St, Melbourne"
                        className="h-11 min-h-[44px]"
                      />
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
                      onChange={(e) => updateSoloProviderField("description", e.target.value)}
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
                          onCheckedChange={(checked) => updateSoloProviderField("allow_in_call", checked)}
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
                          onCheckedChange={(checked) => updateSoloProviderField("allow_out_call", checked)}
                        />
                      </div>
                    </div>

                    {soloProvider.allow_out_call && (
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
                            onChange={(e) =>
                              updateSoloProviderField("out_call_radius_km", parseFloat(e.target.value) || 0)
                            }
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
                            onChange={(e) =>
                              updateSoloProviderField("base_outcall_surcharge", parseFloat(e.target.value) || 0)
                            }
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
                            onChange={(e) =>
                              updateSoloProviderField("per_km_fee", parseFloat(e.target.value) || 0)
                            }
                            className="h-10 min-h-[40px]"
                          />
                        </div>

                        <div className="space-y-1.5">
                          <Label
                            htmlFor="out-call-buffer"
                            className="text-xs font-semibold text-muted-foreground flex items-center gap-1"
                          >
                            <Clock className="h-3 w-3 text-primary" />
                            <span>Travel Buffer (mins)</span>
                          </Label>
                          <Input
                            id="out-call-buffer"
                            type="number"
                            min={0}
                            step={5}
                            value={soloProvider.turnaround_buffer_mins}
                            onChange={(e) =>
                              updateSoloProviderField("turnaround_buffer_mins", parseInt(e.target.value, 10) || 0)
                            }
                            className="h-10 min-h-[40px]"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </>
              ) : null}
            </CardContent>

            {soloProvider && (
              <CardFooter className="justify-end border-t pt-3 pb-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleSaveProvider(false)}
                  disabled={isSavingAny}
                  className="h-9 min-h-[38px] touch-manipulation gap-1.5 text-xs font-medium"
                >
                  {savingProvider ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                  <span>Save Provider Details</span>
                </Button>
              </CardFooter>
            )}
          </Card>
        )}

        {/* ==================================================================== */}
        {/* SECTION 3: Primary Location Details Panel                            */}
        {/* Shown only when Multiple Locations module is OFF                     */}
        {/* ==================================================================== */}
        {!locationsEnabled && (
          <Card className="shadow-xs border-primary/25 bg-card">
            <CardHeader className="pb-3 border-b bg-muted/15">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <CardTitle className="text-base sm:text-lg flex items-center gap-2">
                      <MapPin className="h-4 w-4 text-primary" />
                      <span>Primary Location Details</span>
                    </CardTitle>
                    <Badge variant="secondary" className="text-[11px] font-normal tracking-tight">
                      Single Location Mode
                    </Badge>
                  </div>
                  <CardDescription className="text-xs mt-1">
                    Configures your primary clinic or studio address, timezone, and public directory visibility
                  </CardDescription>
                </div>
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
                    disabled={isSavingAny}
                    className="gap-2"
                  >
                    <Plus className="h-4 w-4" />
                    <span>Initialize Primary Location</span>
                  </Button>
                </div>
              ) : primaryLocation ? (
                <>
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
                        onChange={(e) => updatePrimaryLocationField("name", e.target.value)}
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
                        onValueChange={(val) => updatePrimaryLocationField("timezone", val)}
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

                  {/* Address Breakdown */}
                  <div className="space-y-3 p-4 rounded-xl border bg-muted/10">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        Physical Address Breakdown
                      </Label>
                      {profile.address && (
                        <button
                          type="button"
                          onClick={() => {
                            const parsed = parseAddressParts(profile.address)
                            setLocStreet(parsed.street)
                            setLocCity(parsed.city)
                            setLocState(parsed.state)
                            setLocPostalCode(parsed.postalCode)
                            toast.success("Applied business address")
                          }}
                          className="text-[11px] text-primary hover:underline font-medium"
                        >
                          Use Business Address
                        </button>
                      )}
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="loc-street" className="text-xs text-muted-foreground">
                        Street Address
                      </Label>
                      <Input
                        id="loc-street"
                        value={locStreet}
                        onChange={(e) => setLocStreet(e.target.value)}
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
                          onChange={(e) => setLocCity(e.target.value)}
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
                          onChange={(e) => setLocState(e.target.value)}
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
                          onChange={(e) => setLocPostalCode(e.target.value)}
                          placeholder="e.g. 2000"
                          className="h-10 min-h-[40px]"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Public Directory Visibility Toggle */}
                  <div className="flex items-center justify-between p-3.5 rounded-lg border bg-card/60">
                    <div className="space-y-0.5 pr-4">
                      <div className="flex items-center gap-1.5">
                        <EyeOff className="h-4 w-4 text-muted-foreground" />
                        <Label htmlFor="loc-is-client-hidden" className="text-sm font-medium cursor-pointer">
                          Discreet / Private Location
                        </Label>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Hide full street address from public booking cards and directories until appointment confirmation
                      </p>
                    </div>
                    <Switch
                      id="loc-is-client-hidden"
                      checked={primaryLocation.is_client_hidden ?? false}
                      onCheckedChange={(checked) =>
                        updatePrimaryLocationField("is_client_hidden", checked)
                      }
                    />
                  </div>
                </>
              ) : null}
            </CardContent>

            {primaryLocation && (
              <CardFooter className="justify-end border-t pt-3 pb-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleSaveLocation(false)}
                  disabled={isSavingAny}
                  className="h-9 min-h-[38px] touch-manipulation gap-1.5 text-xs font-medium"
                >
                  {savingLocation ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                  <span>Save Location Details</span>
                </Button>
              </CardFooter>
            )}
          </Card>
        )}
      </div>
    </MobilePageShell>
  )
}
