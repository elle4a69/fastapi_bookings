import { useEffect, useState, useCallback, useMemo } from "react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/context/auth-context"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { toast } from "sonner"
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Copy,
  ExternalLink,
  Layers,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Users,
  Check,
  Power,
  RotateCcw,
} from "lucide-react"

export interface TenantRecord {
  id: number
  name: string
  subdomain: string
  timezone: string
  country?: string | null
  email?: string | null
  phone?: string | null
  website?: string | null
  public_address_visibility: string
  max_advance_days: number
  address?: string | null
  latitude?: number | null
  longitude?: number | null
  logo_url?: string | null
  allow_in_call: boolean
  allow_out_call: boolean
  travel_charge_origin: string
  chatwoot_account_id?: number | null
  status: "active" | "suspended" | string
  suspended_at?: string | null
  suspension_reason?: string | null
  subscription_tier: "starter" | "growth" | "enterprise" | string
  addon_quota: number
  created_at: string
  invitation_token?: string | null
}

export interface TenantListApiResponse {
  ok: boolean
  data: TenantRecord[]
}

export interface TenantCreateApiResponse {
  ok: boolean
  data: TenantRecord
}

export default function TenantsPage() {
  const { isPlatformOwner } = useAuth()

  // State
  const [loading, setLoading] = useState(true)
  const [tenants, setTenants] = useState<TenantRecord[]>([])
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [tierFilter, setTierFilter] = useState<string>("all")

  // Provision Modal State
  const [isProvisionOpen, setIsProvisionOpen] = useState(false)
  const [provisionName, setProvisionName] = useState("")
  const [provisionSubdomain, setProvisionSubdomain] = useState("")
  const [provisionEmail, setProvisionEmail] = useState("")
  const [provisionTier, setProvisionTier] = useState<string>("starter")
  const [provisionTimezone, setProvisionTimezone] = useState("UTC")
  const [isProvisioning, setIsProvisioning] = useState(false)

  // Success Invitation State
  const [invitationResult, setInvitationResult] = useState<{
    tenantName: string
    subdomain: string
    token: string
  } | null>(null)
  const [hasCopiedInvite, setHasCopiedInvite] = useState(false)

  // Suspend Modal State
  const [tenantToSuspend, setTenantToSuspend] = useState<TenantRecord | null>(null)
  const [suspendReason, setSuspendReason] = useState("")
  const [isSuspending, setIsSuspending] = useState(false)

  // Reactivate Modal State
  const [tenantToReactivate, setTenantToReactivate] = useState<TenantRecord | null>(null)
  const [isReactivating, setIsReactivating] = useState(false)

  // 1. Fetch Tenants
  const fetchTenants = useCallback(async () => {
    try {
      setLoading(true)
      const res = await apiClient.get<TenantListApiResponse>("/api/tenants")
      if (res && res.ok && Array.isArray(res.data)) {
        setTenants(res.data)
      } else if (Array.isArray(res)) {
        setTenants(res as any)
      }
    } catch (err: any) {
      toast.error(err?.message || "Failed to load tenant directory")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTenants()
  }, [fetchTenants])

  // Subdomain Validation
  const subdomainError = useMemo(() => {
    if (!provisionSubdomain) return null
    const valid = /^[a-z0-9-]+$/.test(provisionSubdomain)
    if (!valid) {
      return "Subdomain may only contain lowercase letters, numbers, and hyphens."
    }
    if (provisionSubdomain.startsWith("-") || provisionSubdomain.endsWith("-")) {
      return "Subdomain cannot start or end with a hyphen."
    }
    return null
  }, [provisionSubdomain])

  // Auto-generate subdomain from name
  const handleNameChange = (val: string) => {
    setProvisionName(val)
    if (!provisionSubdomain || provisionSubdomain === slugify(provisionName)) {
      setProvisionSubdomain(slugify(val))
    }
  }

  function slugify(text: string) {
    return text
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9\s-]/g, "")
      .replace(/[\s_]+/g, "-")
      .replace(/^-+|-+$/g, "")
  }

  // Handle Provisioning
  const handleProvisionSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!provisionName.trim() || !provisionSubdomain.trim() || !provisionEmail.trim()) {
      toast.error("Please fill in all required fields.")
      return
    }
    if (subdomainError) {
      toast.error(subdomainError)
      return
    }

    try {
      setIsProvisioning(true)
      const payload = {
        name: provisionName.trim(),
        subdomain: provisionSubdomain.toLowerCase().trim(),
        owner_email: provisionEmail.toLowerCase().trim(),
        subscription_tier: provisionTier,
        timezone: provisionTimezone,
      }

      const res = await apiClient.post<TenantCreateApiResponse>("/api/tenants", payload)
      if (res && res.ok && res.data) {
        toast.success(`Tenant '${res.data.name}' provisioned successfully!`)
        fetchTenants()

        const token = res.data.invitation_token
        if (token) {
          setInvitationResult({
            tenantName: res.data.name,
            subdomain: res.data.subdomain,
            token,
          })
        } else {
          setIsProvisionOpen(false)
          resetProvisionForm()
        }
      }
    } catch (err: any) {
      toast.error(err?.message || "Failed to provision tenant")
    } finally {
      setIsProvisioning(false)
    }
  }

  const resetProvisionForm = () => {
    setProvisionName("")
    setProvisionSubdomain("")
    setProvisionEmail("")
    setProvisionTier("starter")
    setProvisionTimezone("UTC")
    setInvitationResult(null)
    setHasCopiedInvite(false)
  }

  // Handle Copy Invitation Link
  const getInviteUrl = (token: string) => {
    const origin = typeof window !== "undefined" ? window.location.origin : ""
    return `${origin}/invite?token=${token}`
  }

  const handleCopyInviteUrl = (token: string) => {
    const url = getInviteUrl(token)
    navigator.clipboard.writeText(url)
    setHasCopiedInvite(true)
    toast.success("Invitation URL copied to clipboard!")
    setTimeout(() => setHasCopiedInvite(false), 2500)
  }

  // Handle Suspend
  const handleConfirmSuspend = async () => {
    if (!tenantToSuspend) return
    try {
      setIsSuspending(true)
      const res = await apiClient.post<TenantCreateApiResponse>(
        `/api/tenants/${tenantToSuspend.id}/suspend`,
        { reason: suspendReason.trim() || "Administrative suspension by platform owner" }
      )
      if (res && res.ok) {
        toast.success(`Tenant '${tenantToSuspend.name}' has been suspended.`)
        setTenantToSuspend(null)
        setSuspendReason("")
        fetchTenants()
      }
    } catch (err: any) {
      toast.error(err?.message || "Failed to suspend tenant")
    } finally {
      setIsSuspending(false)
    }
  }

  // Handle Reactivate
  const handleConfirmReactivate = async () => {
    if (!tenantToReactivate) return
    try {
      setIsReactivating(true)
      const res = await apiClient.post<TenantCreateApiResponse>(
        `/api/tenants/${tenantToReactivate.id}/reactivate`
      )
      if (res && res.ok) {
        toast.success(`Tenant '${tenantToReactivate.name}' has been reactivated.`)
        setTenantToReactivate(null)
        fetchTenants()
      }
    } catch (err: any) {
      toast.error(err?.message || "Failed to reactivate tenant")
    } finally {
      setIsReactivating(false)
    }
  }

  // Metrics
  const metrics = useMemo(() => {
    const total = tenants.length
    const active = tenants.filter((t) => t.status === "active").length
    const suspended = tenants.filter((t) => t.status === "suspended").length
    const enterprise = tenants.filter((t) => t.subscription_tier === "enterprise").length
    const growth = tenants.filter((t) => t.subscription_tier === "growth").length
    return { total, active, suspended, enterprise, growth }
  }, [tenants])

  // Filtered List
  const filteredTenants = useMemo(() => {
    return tenants.filter((t) => {
      // Query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim()
        const matchesName = t.name.toLowerCase().includes(q)
        const matchesSubdomain = t.subdomain.toLowerCase().includes(q)
        const matchesEmail = (t.email || "").toLowerCase().includes(q)
        if (!matchesName && !matchesSubdomain && !matchesEmail) {
          return false
        }
      }

      // Status filter
      if (statusFilter !== "all" && t.status !== statusFilter) {
        return false
      }

      // Tier filter
      if (tierFilter !== "all" && t.subscription_tier !== tierFilter) {
        return false
      }

      return true
    })
  }, [tenants, searchQuery, statusFilter, tierFilter])

  return (
    <div className="flex-1 space-y-6 p-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-border/60">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
              <Building2 className="h-6 w-6 text-primary" />
              Tenant Organizations
            </h1>
            <Badge variant="outline" className="bg-primary/5 text-primary border-primary/20 text-xs font-semibold">
              Super Admin Control Plane
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Provision, monitor, and regulate tenant workspaces, subdomains, and operational lifecycles.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchTenants}
            disabled={loading}
            className="gap-1.5 shadow-xs"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => {
              resetProvisionForm()
              setIsProvisionOpen(true)
            }}
            disabled={!isPlatformOwner}
            className="gap-1.5 shadow-xs bg-primary hover:bg-primary/90 text-primary-foreground font-medium"
          >
            <Plus className="h-4 w-4" />
            Provision Tenant
          </Button>
        </div>
      </div>

      {/* Platform Owner Authority Guard */}
      {!isPlatformOwner ? (
        <div className="flex items-center gap-2 p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200 text-xs">
          <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0" />
          <span>Platform Owner privileges required to provision new tenants and mutate lifecycle states.</span>
        </div>
      ) : (
        <div className="flex items-center justify-between px-1 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-medium">
            <ShieldCheck className="h-3.5 w-3.5" />
            Platform Owner Authority Active
          </span>
          {loading && (
            <span className="flex items-center gap-1">
              <RefreshCw className="h-3 w-3 animate-spin" /> Updating directory...
            </span>
          )}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="shadow-xs border-border/80">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Total Organizations
            </CardTitle>
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <Building2 className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{metrics.total}</div>
            <p className="text-xs text-muted-foreground mt-1">Active instances hosted</p>
          </CardContent>
        </Card>

        <Card className="shadow-xs border-border/80">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Active Tenants
            </CardTitle>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{metrics.active}</div>
            <p className="text-xs text-muted-foreground mt-1">Operating without restrictions</p>
          </CardContent>
        </Card>

        <Card className="shadow-xs border-border/80">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Suspended
            </CardTitle>
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-600 dark:text-rose-400">
              <AlertTriangle className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-rose-600 dark:text-rose-400">{metrics.suspended}</div>
            <p className="text-xs text-muted-foreground mt-1">Access revoked / paused</p>
          </CardContent>
        </Card>

        <Card className="shadow-xs border-border/80">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Growth & Enterprise
            </CardTitle>
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
              <Layers className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">
              {metrics.enterprise + metrics.growth}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {metrics.enterprise} Enterprise, {metrics.growth} Growth
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <Card className="shadow-xs border-border/80">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
            <div className="relative w-full sm:w-80">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name, subdomain, email..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 text-sm"
              />
            </div>

            <div className="flex items-center gap-3 w-full sm:w-auto">
              <div className="flex items-center gap-1.5 w-full sm:w-auto">
                <span className="text-xs font-medium text-muted-foreground whitespace-nowrap">Status:</span>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-[125px] h-9 text-xs">
                    <SelectValue placeholder="All" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="suspended">Suspended</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-1.5 w-full sm:w-auto">
                <span className="text-xs font-medium text-muted-foreground whitespace-nowrap">Tier:</span>
                <Select value={tierFilter} onValueChange={setTierFilter}>
                  <SelectTrigger className="w-[125px] h-9 text-xs">
                    <SelectValue placeholder="All" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Tiers</SelectItem>
                    <SelectItem value="starter">Starter</SelectItem>
                    <SelectItem value="growth">Growth</SelectItem>
                    <SelectItem value="enterprise">Enterprise</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tenants Table */}
      <Card className="shadow-xs border-border/80">
        <CardHeader className="px-6 py-4 border-b border-border/60">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold">Registered Tenants</CardTitle>
              <CardDescription className="text-xs">
                Showing {filteredTenants.length} of {tenants.length} total organizations
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader className="bg-muted/30">
                <TableRow>
                  <TableHead className="w-[260px] font-semibold text-xs">Organization</TableHead>
                  <TableHead className="font-semibold text-xs">Subdomain</TableHead>
                  <TableHead className="font-semibold text-xs">Plan Tier</TableHead>
                  <TableHead className="font-semibold text-xs">Status</TableHead>
                  <TableHead className="font-semibold text-xs">
                    <span className="flex items-center gap-1.5">
                      <Users className="h-3.5 w-3.5 text-muted-foreground" />
                      Contact / Owner
                    </span>
                  </TableHead>
                  <TableHead className="font-semibold text-xs">Created</TableHead>
                  <TableHead className="text-right font-semibold text-xs">Lifecycle Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-12 text-sm text-muted-foreground">
                      <div className="flex items-center justify-center gap-2">
                        <RefreshCw className="h-4 w-4 animate-spin text-primary" />
                        <span>Loading tenant organizations...</span>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : filteredTenants.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-12">
                      <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground">
                        <Building2 className="h-8 w-8 text-muted-foreground/50" />
                        <p className="text-sm font-medium">No tenant organizations found</p>
                        <p className="text-xs">Try adjusting your search criteria or provision a new tenant.</p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredTenants.map((t) => {
                    const isSuspended = t.status === "suspended"
                    return (
                      <TableRow key={t.id} className="hover:bg-muted/40 transition-colors">
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2.5">
                            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary font-bold text-sm">
                              {t.name.charAt(0).toUpperCase()}
                            </div>
                            <div className="flex flex-col min-w-0">
                              <span className="font-semibold text-sm text-foreground truncate">{t.name}</span>
                              <span className="text-xs text-muted-foreground">ID: #{t.id}</span>
                            </div>
                          </div>
                        </TableCell>

                        <TableCell>
                          <div className="flex items-center gap-1.5">
                            <code className="text-xs bg-muted px-2 py-0.5 rounded font-mono text-foreground font-medium">
                              {t.subdomain}
                            </code>
                          </div>
                        </TableCell>

                        <TableCell>
                          <Badge
                            variant="secondary"
                            className={`capitalize text-xs font-medium ${
                              t.subscription_tier === "enterprise"
                                ? "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-200/50"
                                : t.subscription_tier === "growth"
                                ? "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border-indigo-200/50"
                                : "bg-muted text-muted-foreground"
                            }`}
                          >
                            {t.subscription_tier}
                          </Badge>
                        </TableCell>

                        <TableCell>
                          {isSuspended ? (
                            <div className="flex flex-col gap-0.5">
                              <Badge variant="destructive" className="w-fit text-xs gap-1 font-medium bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-200/50 hover:bg-rose-500/20">
                                <AlertTriangle className="h-3 w-3" />
                                Suspended
                              </Badge>
                              {t.suspension_reason && (
                                <span className="text-[11px] text-muted-foreground truncate max-w-[160px]" title={t.suspension_reason}>
                                  {t.suspension_reason}
                                </span>
                              )}
                            </div>
                          ) : (
                            <Badge variant="outline" className="w-fit text-xs gap-1 font-medium bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20">
                              <CheckCircle2 className="h-3 w-3" />
                              Active
                            </Badge>
                          )}
                        </TableCell>

                        <TableCell>
                          <div className="flex flex-col text-xs">
                            <span className="text-foreground font-medium">{t.email || "—"}</span>
                            {t.phone && <span className="text-muted-foreground">{t.phone}</span>}
                          </div>
                        </TableCell>

                        <TableCell className="text-xs text-muted-foreground">
                          {t.created_at ? new Date(t.created_at).toLocaleDateString() : "—"}
                        </TableCell>

                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => window.open(`/portal/${t.subdomain}`, "_blank")}
                              title={`Open ${t.name} Customer Portal`}
                              className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </Button>
                            {isSuspended ? (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setTenantToReactivate(t)}
                                disabled={!isPlatformOwner}
                                className="h-8 text-xs gap-1.5 text-emerald-600 border-emerald-300 dark:border-emerald-800 hover:bg-emerald-50 dark:hover:bg-emerald-950/40"
                              >
                                <RotateCcw className="h-3.5 w-3.5" />
                                Reactivate
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  setTenantToSuspend(t)
                                  setSuspendReason("")
                                }}
                                disabled={!isPlatformOwner}
                                className="h-8 text-xs gap-1.5 text-rose-600 border-rose-200 dark:border-rose-900/60 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                              >
                                <Power className="h-3.5 w-3.5" />
                                Suspend
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Provision Tenant Modal */}
      <Dialog
        open={isProvisionOpen}
        onOpenChange={(open) => {
          if (!open) {
            setIsProvisionOpen(false)
            resetProvisionForm()
          }
        }}
      >
        <DialogContent className="sm:max-w-[540px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg">
              <Building2 className="h-5 w-5 text-primary" />
              Provision New Tenant Organization
            </DialogTitle>
            <DialogDescription className="text-xs">
              Configure organizational details, subdomain routing, and administrator access.
            </DialogDescription>
          </DialogHeader>

          {invitationResult ? (
            /* Success View with One-Time Invitation URL */
            <div className="space-y-5 py-3">
              <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 p-4 space-y-2">
                <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300 font-semibold text-sm">
                  <CheckCircle2 className="h-5 w-5" />
                  Tenant "{invitationResult.tenantName}" Provisioned!
                </div>
                <p className="text-xs text-emerald-600 dark:text-emerald-400">
                  Subdomain <code className="font-bold">{invitationResult.subdomain}</code> is active. An initial cryptographic owner invitation token has been created.
                </p>
              </div>

              <div className="space-y-2">
                <Label className="text-xs font-semibold text-foreground">
                  One-Time Owner Onboarding URL
                </Label>
                <div className="flex items-center gap-2">
                  <Input
                    readOnly
                    value={getInviteUrl(invitationResult.token)}
                    className="font-mono text-xs select-all bg-muted"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => handleCopyInviteUrl(invitationResult.token)}
                    className="gap-1.5 shrink-0"
                  >
                    {hasCopiedInvite ? (
                      <>
                        <Check className="h-4 w-4 text-emerald-600" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-4 w-4" />
                        Copy Link
                      </>
                    )}
                  </Button>
                </div>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Share this secure single-use URL with the administrator. It allows them to set their password and finish initial workspace onboarding.
                </p>
              </div>

              <DialogFooter>
                <Button
                  onClick={() => {
                    setIsProvisionOpen(false)
                    resetProvisionForm()
                  }}
                  className="w-full"
                >
                  Done
                </Button>
              </DialogFooter>
            </div>
          ) : (
            /* Provision Form */
            <form onSubmit={handleProvisionSubmit} className="space-y-4 py-2">
              <div className="space-y-1.5">
                <Label htmlFor="tenant-name" className="text-xs font-semibold">
                  Organization Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="tenant-name"
                  placeholder="e.g. Apex Health Partners"
                  value={provisionName}
                  onChange={(e) => handleNameChange(e.target.value)}
                  required
                  className="text-sm"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="tenant-subdomain" className="text-xs font-semibold">
                  Subdomain Slug <span className="text-destructive">*</span>
                </Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="tenant-subdomain"
                    placeholder="e.g. apex-health"
                    value={provisionSubdomain}
                    onChange={(e) => setProvisionSubdomain(e.target.value.toLowerCase())}
                    required
                    className="font-mono text-sm"
                  />
                  <span className="text-xs text-muted-foreground whitespace-nowrap">.bookmepro.com</span>
                </div>
                {subdomainError ? (
                  <p className="text-xs text-destructive font-medium">{subdomainError}</p>
                ) : (
                  <p className="text-[11px] text-muted-foreground">
                    Only lowercase letters, numbers, and hyphens.
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="tenant-admin-email" className="text-xs font-semibold">
                  Administrator / Owner Email <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="tenant-admin-email"
                  type="email"
                  placeholder="admin@organization.com"
                  value={provisionEmail}
                  onChange={(e) => setProvisionEmail(e.target.value)}
                  required
                  className="text-sm"
                />
                <p className="text-[11px] text-muted-foreground">
                  The initial owner account invitation will be bound to this email address.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="tenant-tier" className="text-xs font-semibold">
                    Subscription Tier
                  </Label>
                  <Select value={provisionTier} onValueChange={setProvisionTier}>
                    <SelectTrigger id="tenant-tier" className="text-xs h-9">
                      <SelectValue placeholder="Select tier" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="starter">Starter (Core features)</SelectItem>
                      <SelectItem value="growth">Growth (Multi-provider & AI)</SelectItem>
                      <SelectItem value="enterprise">Enterprise (Dedicated support)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="tenant-tz" className="text-xs font-semibold">
                    Timezone
                  </Label>
                  <Select value={provisionTimezone} onValueChange={setProvisionTimezone}>
                    <SelectTrigger id="tenant-tz" className="text-xs h-9">
                      <SelectValue placeholder="Select timezone" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="UTC">UTC (Universal)</SelectItem>
                      <SelectItem value="America/New_York">America/New York (EST/EDT)</SelectItem>
                      <SelectItem value="America/Los_Angeles">America/Los Angeles (PST/PDT)</SelectItem>
                      <SelectItem value="Europe/London">Europe/London (GMT/BST)</SelectItem>
                      <SelectItem value="Australia/Sydney">Australia/Sydney (AEST/AEDT)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <DialogFooter className="pt-3 gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setIsProvisionOpen(false)
                    resetProvisionForm()
                  }}
                  disabled={isProvisioning}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isProvisioning || Boolean(subdomainError)}
                  className="gap-2 bg-primary text-primary-foreground font-medium"
                >
                  {isProvisioning && <RefreshCw className="h-4 w-4 animate-spin" />}
                  {isProvisioning ? "Provisioning..." : "Create Tenant"}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>

      {/* Suspend Confirmation Modal */}
      <Dialog
        open={Boolean(tenantToSuspend)}
        onOpenChange={(open) => {
          if (!open) {
            setTenantToSuspend(null)
            setSuspendReason("")
          }
        }}
      >
        <DialogContent className="sm:max-w-[460px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
              <ShieldAlert className="h-5 w-5" />
              Suspend Organization
            </DialogTitle>
            <DialogDescription className="text-xs">
              Temporarily revoke operational access for this tenant and all associated staff accounts.
            </DialogDescription>
          </DialogHeader>

          {tenantToSuspend && (
            <div className="space-y-4 py-2">
              <div className="rounded-lg bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/50 p-3 text-xs text-rose-800 dark:text-rose-300 space-y-1">
                <p className="font-semibold">
                  You are about to suspend "{tenantToSuspend.name}" ({tenantToSuspend.subdomain})
                </p>
                <p className="text-[11px] opacity-90">
                  Staff members will be unable to log in, and customer portal bookings will be blocked until reactivated.
                </p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="suspend-reason" className="text-xs font-semibold">
                  Reason for Suspension (Required)
                </Label>
                <Textarea
                  id="suspend-reason"
                  placeholder="e.g. Delinquent billing, terms of service violation, administrative hold..."
                  value={suspendReason}
                  onChange={(e) => setSuspendReason(e.target.value)}
                  className="text-xs resize-none h-20"
                />
              </div>

              <DialogFooter className="pt-2 gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setTenantToSuspend(null)
                    setSuspendReason("")
                  }}
                  disabled={isSuspending}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  onClick={handleConfirmSuspend}
                  disabled={isSuspending}
                  className="gap-2"
                >
                  {isSuspending && <RefreshCw className="h-4 w-4 animate-spin" />}
                  Confirm Suspension
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Reactivate Confirmation Modal */}
      <Dialog
        open={Boolean(tenantToReactivate)}
        onOpenChange={(open) => {
          if (!open) {
            setTenantToReactivate(null)
          }
        }}
      >
        <DialogContent className="sm:max-w-[460px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
              <ShieldCheck className="h-5 w-5" />
              Reactivate Organization
            </DialogTitle>
            <DialogDescription className="text-xs">
              Restore operational access and portal capabilities for this tenant.
            </DialogDescription>
          </DialogHeader>

          {tenantToReactivate && (
            <div className="space-y-4 py-2">
              <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900/50 p-3 text-xs text-emerald-800 dark:text-emerald-300 space-y-1">
                <p className="font-semibold">
                  Reactivate "{tenantToReactivate.name}" ({tenantToReactivate.subdomain})?
                </p>
                <p className="text-[11px] opacity-90">
                  Staff authentication and booking schedules will be restored immediately.
                </p>
              </div>

              <DialogFooter className="pt-2 gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setTenantToReactivate(null)}
                  disabled={isReactivating}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  onClick={handleConfirmReactivate}
                  disabled={isReactivating}
                  className="gap-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium"
                >
                  {isReactivating && <RefreshCw className="h-4 w-4 animate-spin" />}
                  Confirm Reactivate
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
