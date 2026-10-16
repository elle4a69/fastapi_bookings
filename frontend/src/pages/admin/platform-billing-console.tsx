import { useEffect, useState, useCallback } from "react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/context/auth-context"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { MobilePageShell } from "@/components/ui/mobile-page-shell"
import { toast } from "sonner"
import {
  AlertTriangleIcon,
  DatabaseIcon,
  KeyIcon,
  PlusIcon,
  RefreshCwIcon,
  SearchIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
  Trash2Icon,
  UsersIcon,
} from "lucide-react"

interface TenantBillingSummary {
  tenant_id: number
  tenant_name: string
  subdomain: string
  plan_id: string
  plan_name: string
  status: string
  health: "healthy" | "warning" | "critical"
  billing_state: string
  current_period_end?: string | null
  is_past_due: boolean
  created_at: string
}

interface ProviderEventInboxItem {
  id: number
  provider: string
  external_event_id: string
  event_type: string
  payload_digest: string
  verified_at?: string | null
  processing_status: string
  retry_count: number
  error_message?: string | null
  processed_at?: string | null
  created_at: string
}

interface PlatformGrantItem {
  id: number
  tenant_id: number
  tenant_name?: string | null
  entitlement_key: string
  value_type: string
  granted_value: string
  expires_at?: string | null
  reason: string
  granted_by_user_id?: number | null
  is_revoked: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

interface TenantDiagnosticsData {
  tenant_id: number
  tenant_name: string
  subdomain: string
  billing_account?: {
    id: number
    flexprice_customer_id?: string
    billing_state: string
  } | null
  subscription?: {
    id: number
    external_subscription_id: string
    plan_id: string
    status: string
    current_period_start?: string | null
    current_period_end?: string | null
  } | null
  entitlements: Array<{
    id: number
    entitlement_key: string
    value_type: string
    value: string
    is_active: boolean
    expires_at?: string | null
  }>
  active_grants: PlatformGrantItem[]
  recent_events: ProviderEventInboxItem[]
  usage_summary: Record<string, { limit: any; current_usage: number }>
}

interface ReconciliationItem {
  tenant_id: number
  external_subscription_id?: string | null
  local_status?: string | null
  remote_status?: string | null
  is_synchronized: boolean
  discrepancy_details?: string | null
}

const CANONICAL_KEYS = [
  "assistant.enabled",
  "assistant.monthly_runs",
  "sms.enabled",
  "sms.monthly_outbound_messages",
  "locations.max",
  "providers.max",
  "api.enabled",
]

export default function PlatformBillingConsolePage() {
  const { isPlatformOwner } = useAuth()

  // State
  const [activeTab, setActiveTab] = useState("tenants")
  const [loading, setLoading] = useState(false)
  const [tenants, setTenants] = useState<TenantBillingSummary[]>([])
  const [inboxEvents, setInboxEvents] = useState<ProviderEventInboxItem[]>([])
  const [grants, setGrants] = useState<PlatformGrantItem[]>([])
  const [reconcileReports, setReconcileReports] = useState<ReconciliationItem[]>([])

  // Filters & Search
  const [tenantSearch, setTenantSearch] = useState("")
  const [inboxStatusFilter, setInboxStatusFilter] = useState<string>("all")

  // Diagnostics Modal State
  const [diagnosticsModalOpen, setDiagnosticsModalOpen] = useState(false)
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false)
  const [selectedDiagnostics, setSelectedDiagnostics] = useState<TenantDiagnosticsData | null>(null)

  // Create Grant Modal State
  const [grantModalOpen, setGrantModalOpen] = useState(false)
  const [grantTargetTenantId, setGrantTargetTenantId] = useState("")
  const [grantKey, setGrantKey] = useState("assistant.enabled")
  const [grantValueType, setGrantValueType] = useState("boolean")
  const [grantValue, setGrantValue] = useState("true")
  const [grantExpiresDays, setGrantExpiresDays] = useState("30")
  const [grantReason, setGrantReason] = useState("")
  const [grantSubmitting, setGrantSubmitting] = useState(false)

  // Reconciliation Loading
  const [reconcileLoading, setReconcileLoading] = useState(false)

  // 1. Fetch Tenants
  const fetchTenants = useCallback(async () => {
    try {
      setLoading(true)
      const res = await apiClient.get<TenantBillingSummary[]>("/api/admin/platform/billing/tenants")
      setTenants(Array.isArray(res) ? res : [])
    } catch (err: any) {
      toast.error(err?.message || "Failed to load tenant billing summaries")
    } finally {
      setLoading(false)
    }
  }, [])

  // 2. Fetch Inbox Events
  const fetchInbox = useCallback(async (filter?: string) => {
    try {
      setLoading(true)
      const statusParam = filter && filter !== "all" ? `?status_filter=${filter}` : ""
      const res = await apiClient.get<ProviderEventInboxItem[]>(`/api/admin/platform/billing/inbox${statusParam}`)
      setInboxEvents(Array.isArray(res) ? res : [])
    } catch (err: any) {
      toast.error(err?.message || "Failed to load provider event inbox")
    } finally {
      setLoading(false)
    }
  }, [])

  // 3. Fetch Grants
  const fetchGrants = useCallback(async () => {
    try {
      setLoading(true)
      const res = await apiClient.get<PlatformGrantItem[]>("/api/admin/platform/billing/grants")
      setGrants(Array.isArray(res) ? res : [])
    } catch (err: any) {
      toast.error(err?.message || "Failed to load platform grants")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeTab === "tenants") fetchTenants()
    if (activeTab === "inbox") fetchInbox(inboxStatusFilter)
    if (activeTab === "grants") fetchGrants()
  }, [activeTab, fetchTenants, fetchInbox, fetchGrants, inboxStatusFilter])

  // Inspect Diagnostics
  const handleInspectDiagnostics = async (tenantId: number) => {
    try {
      setDiagnosticsLoading(true)
      setDiagnosticsModalOpen(true)
      const res = await apiClient.get<TenantDiagnosticsData>(`/api/admin/platform/billing/tenants/${tenantId}/diagnostics`)
      setSelectedDiagnostics(res)
    } catch (err: any) {
      toast.error(err?.message || "Failed to fetch tenant diagnostics")
      setDiagnosticsModalOpen(false)
    } finally {
      setDiagnosticsLoading(false)
    }
  }

  // Retry Inbox Item
  const handleRetryInboxItem = async (eventId: number | string) => {
    try {
      await apiClient.post(`/api/admin/platform/billing/inbox/${eventId}/retry`)
      toast.success("Event status reset to pending for retry")
      fetchInbox(inboxStatusFilter)
    } catch (err: any) {
      toast.error(err?.message || "Failed to retry inbox event")
    }
  }

  // Create Grant
  const handleCreateGrant = async () => {
    if (!grantTargetTenantId) {
      toast.error("Please enter a target Tenant ID")
      return
    }
    if (!grantReason.trim() || grantReason.trim().length < 3) {
      toast.error("A descriptive operational audit reason is required")
      return
    }

    try {
      setGrantSubmitting(true)
      const expiryDate = grantExpiresDays
        ? new Date(Date.now() + Number(grantExpiresDays) * 86400000).toISOString()
        : null

      await apiClient.post("/api/admin/platform/billing/grants", {
        tenant_id: Number(grantTargetTenantId),
        entitlement_key: grantKey,
        value_type: grantValueType,
        granted_value: grantValue,
        expires_at: expiryDate,
        reason: grantReason.trim(),
      })
      toast.success("Platform grant created successfully")
      setGrantModalOpen(false)
      setGrantReason("")
      fetchGrants()
    } catch (err: any) {
      toast.error(err?.message || "Failed to create platform grant")
    } finally {
      setGrantSubmitting(false)
    }
  }

  // Revoke Grant
  const handleRevokeGrant = async (grantId: number) => {
    if (!confirm("Are you sure you want to revoke this platform grant?")) return

    try {
      await apiClient.delete(`/api/admin/platform/billing/grants/${grantId}`)
      toast.success("Grant revoked")
      fetchGrants()
    } catch (err: any) {
      toast.error(err?.message || "Failed to revoke grant")
    }
  }

  // Trigger Reconciliation
  const handleTriggerReconcile = async () => {
    try {
      setReconcileLoading(true)
      const res = await apiClient.post<ReconciliationItem[]>("/api/admin/platform/billing/reconcile")
      setReconcileReports(Array.isArray(res) ? res : [])
      toast.success("Provider reconciliation cycle executed")
    } catch (err: any) {
      toast.error(err?.message || "Reconciliation failed")
    } finally {
      setReconcileLoading(false)
    }
  }

  // Computed Metrics
  const totalTenantsCount = tenants.length
  const pastDueCount = tenants.filter((t) => t.is_past_due || t.status === "past_due").length
  const failedInboxCount = inboxEvents.filter((e) => e.processing_status === "failed").length
  const activeGrantsCount = grants.filter((g) => g.is_active).length

  // Filtered tenants list
  const filteredTenants = tenants.filter((t) => {
    if (!tenantSearch) return true
    const q = tenantSearch.toLowerCase()
    return (
      t.tenant_name.toLowerCase().includes(q) ||
      t.subdomain.toLowerCase().includes(q) ||
      t.plan_id.toLowerCase().includes(q) ||
      String(t.tenant_id).includes(q)
    )
  })

  return (
    <MobilePageShell
      title="Platform Billing Console"
      description="Cross-tenant subscription health, provider event inbox, entitlement diagnostics, and platform operator grants."
    >
      <div className="space-y-6 max-w-7xl pb-16">
        {/* Authority Status */}
        {!isPlatformOwner ? (
          <div className="flex items-center gap-2 p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200 text-xs">
            <ShieldAlertIcon className="h-4 w-4 text-amber-600 shrink-0" />
            <span>Platform Owner privileges required to execute mutations, retries, and issue grants.</span>
          </div>
        ) : (
          <div className="flex items-center justify-between px-1 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5 text-emerald-600 font-medium">
              <ShieldCheckIcon className="h-3.5 w-3.5" />
              Platform Owner Authority Active
            </span>
            {loading && (
              <span className="flex items-center gap-1">
                <RefreshCwIcon className="h-3 w-3 animate-spin" /> Updating...
              </span>
            )}
          </div>
        )}

        {/* KPI Metrics Header */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Card className="p-4 shadow-sm border">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-primary/10 text-primary">
                <UsersIcon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground font-medium">Total Tenants</p>
                <p className="text-2xl font-bold">{totalTenantsCount}</p>
              </div>
            </div>
          </Card>

          <Card className="p-4 shadow-sm border">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-600">
                <AlertTriangleIcon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground font-medium">Past Due / Grace</p>
                <p className="text-2xl font-bold text-amber-600">{pastDueCount}</p>
              </div>
            </div>
          </Card>

          <Card className="p-4 shadow-sm border">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-destructive/10 text-destructive">
                <ShieldAlertIcon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground font-medium">Dead Letter Events</p>
                <p className="text-2xl font-bold text-destructive">{failedInboxCount}</p>
              </div>
            </div>
          </Card>

          <Card className="p-4 shadow-sm border">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-blue-500/10 text-blue-600">
                <KeyIcon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground font-medium">Active Grants</p>
                <p className="text-2xl font-bold text-blue-600">{activeGrantsCount}</p>
              </div>
            </div>
          </Card>
        </div>

        {/* Tabbed Console Navigation */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="grid grid-cols-4 w-full max-w-xl">
            <TabsTrigger value="tenants">Tenants & Plans</TabsTrigger>
            <TabsTrigger value="inbox">
              Event Inbox {failedInboxCount > 0 && `(${failedInboxCount})`}
            </TabsTrigger>
            <TabsTrigger value="grants">Platform Grants</TabsTrigger>
            <TabsTrigger value="reconcile">Reconciliation</TabsTrigger>
          </TabsList>

          {/* TAB 1: Tenants List */}
          <TabsContent value="tenants" className="space-y-4">
            <Card className="shadow-sm border">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base">Tenant Subscriptions Overview</CardTitle>
                  <CardDescription className="text-xs">
                    Real-time status projections and billing states across all tenant practices.
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <div className="relative w-64">
                    <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search tenant or plan..."
                      value={tenantSearch}
                      onChange={(e) => setTenantSearch(e.target.value)}
                      className="pl-8 h-9 text-xs"
                    />
                  </div>
                  <Button variant="outline" size="sm" onClick={fetchTenants} className="h-9">
                    <RefreshCwIcon className="h-3.5 w-3.5 mr-1" />
                    Refresh
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-muted/50 border-y text-muted-foreground font-medium">
                      <tr>
                        <th className="py-2.5 px-4">ID</th>
                        <th className="py-2.5 px-4">Practice Name</th>
                        <th className="py-2.5 px-4">Subdomain</th>
                        <th className="py-2.5 px-4">Plan</th>
                        <th className="py-2.5 px-4">Status</th>
                        <th className="py-2.5 px-4">Health</th>
                        <th className="py-2.5 px-4">Period End</th>
                        <th className="py-2.5 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {filteredTenants.map((t) => (
                        <tr key={t.tenant_id} className="hover:bg-muted/30">
                          <td className="py-3 px-4 font-mono font-medium">{t.tenant_id}</td>
                          <td className="py-3 px-4 font-semibold">{t.tenant_name}</td>
                          <td className="py-3 px-4 text-muted-foreground">{t.subdomain}</td>
                          <td className="py-3 px-4 capitalize font-medium">{t.plan_name || t.plan_id}</td>
                          <td className="py-3 px-4">
                            <Badge
                              variant={
                                t.status === "active"
                                  ? "default"
                                  : t.status === "past_due"
                                  ? "destructive"
                                  : "secondary"
                              }
                              className="capitalize text-[10px]"
                            >
                              {t.status}
                            </Badge>
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`inline-flex items-center gap-1 font-medium capitalize ${
                                t.health === "healthy"
                                  ? "text-emerald-600"
                                  : t.health === "warning"
                                  ? "text-amber-600"
                                  : "text-destructive"
                              }`}
                            >
                              <span
                                className={`h-1.5 w-1.5 rounded-full ${
                                  t.health === "healthy"
                                    ? "bg-emerald-500"
                                    : t.health === "warning"
                                    ? "bg-amber-500"
                                    : "bg-destructive"
                                }`}
                              />
                              {t.health}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-muted-foreground">
                            {t.current_period_end
                              ? new Date(t.current_period_end).toLocaleDateString()
                              : "—"}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-7 text-xs"
                              onClick={() => handleInspectDiagnostics(t.tenant_id)}
                            >
                              Diagnostics
                            </Button>
                          </td>
                        </tr>
                      ))}
                      {filteredTenants.length === 0 && (
                        <tr>
                          <td colSpan={8} className="py-8 text-center text-muted-foreground">
                            No tenants match query.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* TAB 2: Event Inbox & Dead Letters */}
          <TabsContent value="inbox" className="space-y-4">
            <Card className="shadow-sm border">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base">Provider Webhook Event Inbox</CardTitle>
                  <CardDescription className="text-xs">
                    Cryptographically verified raw webhook events, idempotency digest, and retry queue.
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex rounded-md border p-1 bg-muted/40 gap-1 text-xs">
                    {["all", "failed", "pending", "processed"].map((f) => (
                      <button
                        key={f}
                        onClick={() => setInboxStatusFilter(f)}
                        className={`px-2.5 py-1 rounded capitalize font-medium ${
                          inboxStatusFilter === f
                            ? "bg-background shadow-xs text-foreground"
                            : "text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                  <Button variant="outline" size="sm" onClick={() => fetchInbox(inboxStatusFilter)}>
                    <RefreshCwIcon className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-muted/50 border-y text-muted-foreground font-medium">
                      <tr>
                        <th className="py-2.5 px-4">Event ID</th>
                        <th className="py-2.5 px-4">Type</th>
                        <th className="py-2.5 px-4">Payload Digest</th>
                        <th className="py-2.5 px-4">Status</th>
                        <th className="py-2.5 px-4">Retries</th>
                        <th className="py-2.5 px-4">Received At</th>
                        <th className="py-2.5 px-4">Error / Notes</th>
                        <th className="py-2.5 px-4 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {inboxEvents.map((evt) => (
                        <tr key={evt.id} className="hover:bg-muted/30">
                          <td className="py-3 px-4 font-mono font-medium">{evt.external_event_id}</td>
                          <td className="py-3 px-4 font-mono text-[11px]">{evt.event_type}</td>
                          <td className="py-3 px-4 font-mono text-[10px] text-muted-foreground">
                            {evt.payload_digest.slice(0, 16)}...
                          </td>
                          <td className="py-3 px-4">
                            <Badge
                              variant={
                                evt.processing_status === "processed"
                                  ? "default"
                                  : evt.processing_status === "failed"
                                  ? "destructive"
                                  : "secondary"
                              }
                              className="text-[10px] uppercase"
                            >
                              {evt.processing_status}
                            </Badge>
                          </td>
                          <td className="py-3 px-4 font-mono">{evt.retry_count}</td>
                          <td className="py-3 px-4 text-muted-foreground">
                            {new Date(evt.created_at).toLocaleString()}
                          </td>
                          <td className="py-3 px-4 text-destructive text-[11px] max-w-xs truncate">
                            {evt.error_message || "—"}
                          </td>
                          <td className="py-3 px-4 text-right">
                            {evt.processing_status === "failed" && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs"
                                onClick={() => handleRetryInboxItem(evt.id)}
                              >
                                Retry
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))}
                      {inboxEvents.length === 0 && (
                        <tr>
                          <td colSpan={8} className="py-8 text-center text-muted-foreground">
                            No inbox events found for this filter.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* TAB 3: Platform Grants */}
          <TabsContent value="grants" className="space-y-4">
            <Card className="shadow-sm border">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base">Platform Entitlement Grants & Overrides</CardTitle>
                  <CardDescription className="text-xs">
                    Explicit, expiring, audited overrides that take precedence over subscription projections.
                  </CardDescription>
                </div>
                <Button size="sm" onClick={() => setGrantModalOpen(true)}>
                  <PlusIcon className="h-4 w-4 mr-1.5" />
                  Issue Platform Grant
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-muted/50 border-y text-muted-foreground font-medium">
                      <tr>
                        <th className="py-2.5 px-4">Grant ID</th>
                        <th className="py-2.5 px-4">Tenant</th>
                        <th className="py-2.5 px-4">Entitlement Key</th>
                        <th className="py-2.5 px-4">Value</th>
                        <th className="py-2.5 px-4">Expires</th>
                        <th className="py-2.5 px-4">Reason / Audit Trail</th>
                        <th className="py-2.5 px-4">Status</th>
                        <th className="py-2.5 px-4 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {grants.map((g) => (
                        <tr key={g.id} className="hover:bg-muted/30">
                          <td className="py-3 px-4 font-mono">#{g.id}</td>
                          <td className="py-3 px-4 font-medium">
                            {g.tenant_name || `Tenant #${g.tenant_id}`}
                          </td>
                          <td className="py-3 px-4 font-mono text-[11px]">{g.entitlement_key}</td>
                          <td className="py-3 px-4 font-semibold">{g.granted_value}</td>
                          <td className="py-3 px-4 text-muted-foreground">
                            {g.expires_at ? new Date(g.expires_at).toLocaleDateString() : "Permanent"}
                          </td>
                          <td className="py-3 px-4 text-muted-foreground max-w-sm truncate" title={g.reason}>
                            {g.reason}
                          </td>
                          <td className="py-3 px-4">
                            {g.is_active ? (
                              <Badge className="bg-emerald-500/15 text-emerald-600 border-emerald-500/30 text-[10px]">
                                Active
                              </Badge>
                            ) : (
                              <Badge variant="secondary" className="text-[10px]">
                                {g.is_revoked ? "Revoked" : "Expired"}
                              </Badge>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right">
                            {g.is_active && (
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-7 text-destructive hover:bg-destructive/10"
                                onClick={() => handleRevokeGrant(g.id)}
                              >
                                <Trash2Icon className="h-3.5 w-3.5" />
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))}
                      {grants.length === 0 && (
                        <tr>
                          <td colSpan={8} className="py-8 text-center text-muted-foreground">
                            No platform grants recorded.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* TAB 4: Reconciliation */}
          <TabsContent value="reconcile" className="space-y-4">
            <Card className="shadow-sm border">
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <div>
                  <CardTitle className="text-base">External Provider Reconciliation</CardTitle>
                  <CardDescription className="text-xs">
                    Assert local subscription projections against authoritative Flexprice remote state.
                  </CardDescription>
                </div>
                <Button size="sm" onClick={handleTriggerReconcile} disabled={reconcileLoading}>
                  <RefreshCwIcon className={`h-4 w-4 mr-1.5 ${reconcileLoading ? "animate-spin" : ""}`} />
                  {reconcileLoading ? "Reconciling..." : "Trigger Provider Sync"}
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {reconcileReports.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-muted/50 border-y text-muted-foreground font-medium">
                        <tr>
                          <th className="py-2.5 px-4">Tenant ID</th>
                          <th className="py-2.5 px-4">External Sub ID</th>
                          <th className="py-2.5 px-4">Local Status</th>
                          <th className="py-2.5 px-4">Remote Status</th>
                          <th className="py-2.5 px-4">Sync State</th>
                          <th className="py-2.5 px-4">Discrepancy Details</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {reconcileReports.map((r, i) => (
                          <tr key={i} className="hover:bg-muted/30">
                            <td className="py-3 px-4 font-mono font-medium">{r.tenant_id}</td>
                            <td className="py-3 px-4 font-mono text-muted-foreground">
                              {r.external_subscription_id || "None"}
                            </td>
                            <td className="py-3 px-4 capitalize">{r.local_status || "—"}</td>
                            <td className="py-3 px-4 capitalize">{r.remote_status || "—"}</td>
                            <td className="py-3 px-4">
                              {r.is_synchronized ? (
                                <Badge className="bg-emerald-500/15 text-emerald-600 border-emerald-500/30 text-[10px]">
                                  Synchronized
                                </Badge>
                              ) : (
                                <Badge variant="destructive" className="text-[10px]">
                                  Discrepancy
                                </Badge>
                              )}
                            </td>
                            <td className="py-3 px-4 text-xs text-muted-foreground">
                              {r.discrepancy_details || "Aligned"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-8 text-center border rounded-lg bg-muted/20 text-muted-foreground text-xs">
                    Click "Trigger Provider Sync" to query Flexprice and reconcile active tenant projections.
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Modal: Tenant Diagnostics */}
        <Dialog open={diagnosticsModalOpen} onOpenChange={setDiagnosticsModalOpen}>
          <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-base flex items-center gap-2">
                <DatabaseIcon className="h-4 w-4 text-primary" />
                Diagnostics: {selectedDiagnostics?.tenant_name} (ID: {selectedDiagnostics?.tenant_id})
              </DialogTitle>
              <DialogDescription className="text-xs">
                Subdomain: <code className="text-foreground">{selectedDiagnostics?.subdomain}</code>
              </DialogDescription>
            </DialogHeader>

            {diagnosticsLoading ? (
              <div className="py-12 text-center text-xs text-muted-foreground">Loading diagnostics...</div>
            ) : selectedDiagnostics ? (
              <div className="space-y-4 text-xs">
                {/* Subscription Projection */}
                <div className="p-3 rounded-lg border bg-muted/30 space-y-1.5">
                  <p className="font-semibold text-foreground">Authoritative Subscription Projection</p>
                  <div className="grid grid-cols-2 gap-2 text-muted-foreground">
                    <div>External ID: <span className="font-mono text-foreground">{selectedDiagnostics.subscription?.external_subscription_id || "None"}</span></div>
                    <div>Plan: <span className="capitalize font-semibold text-foreground">{selectedDiagnostics.subscription?.plan_id || "Starter"}</span></div>
                    <div>Status: <span className="capitalize font-semibold text-foreground">{selectedDiagnostics.subscription?.status || "Active"}</span></div>
                    <div>Billing State: <span className="capitalize text-foreground">{selectedDiagnostics.billing_account?.billing_state || "Unconfigured"}</span></div>
                  </div>
                </div>

                {/* Quotas & Usage Summary */}
                <div className="space-y-2">
                  <p className="font-semibold text-foreground">Current Quotas & Metering</p>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(selectedDiagnostics.usage_summary || {}).map(([k, v]) => (
                      <div key={k} className="p-2.5 rounded-lg border bg-card space-y-1">
                        <p className="font-mono text-[11px] text-muted-foreground truncate">{k}</p>
                        <p className="font-semibold text-sm">
                          {v.current_usage} / {v.limit ?? "∞"}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Active Platform Grants */}
                <div className="space-y-2">
                  <p className="font-semibold text-foreground">Active Platform Grants ({selectedDiagnostics.active_grants.length})</p>
                  {selectedDiagnostics.active_grants.length > 0 ? (
                    <div className="divide-y border rounded-md">
                      {selectedDiagnostics.active_grants.map((g) => (
                        <div key={g.id} className="p-2 flex justify-between items-center text-[11px]">
                          <div>
                            <span className="font-mono font-medium">{g.entitlement_key}</span> = <strong>{g.granted_value}</strong>
                            <p className="text-muted-foreground text-[10px]">{g.reason}</p>
                          </div>
                          <Badge variant={g.is_active ? "default" : "secondary"} className="text-[9px]">
                            {g.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground italic">No platform grants assigned to this tenant.</p>
                  )}
                </div>
              </div>
            ) : null}

            <DialogFooter>
              <Button size="sm" variant="outline" onClick={() => setDiagnosticsModalOpen(false)}>
                Close
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Modal: Issue Platform Grant */}
        <Dialog open={grantModalOpen} onOpenChange={setGrantModalOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="text-base flex items-center gap-2">
                <KeyIcon className="h-4 w-4 text-primary" />
                Issue Platform Grant
              </DialogTitle>
              <DialogDescription className="text-xs">
                Grants temporary or permanent entitlement overrides with required operational auditing.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 text-xs py-2">
              <div className="space-y-1">
                <Label htmlFor="tenantId" className="text-xs">Target Tenant ID *</Label>
                <Input
                  id="tenantId"
                  placeholder="e.g. 1"
                  value={grantTargetTenantId}
                  onChange={(e) => setGrantTargetTenantId(e.target.value)}
                  className="h-8 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="grantKey" className="text-xs">Entitlement Key *</Label>
                <select
                  id="grantKey"
                  value={grantKey}
                  onChange={(e) => {
                    const k = e.target.value
                    setGrantKey(k)
                    if (k.endsWith(".enabled")) {
                      setGrantValueType("boolean")
                      setGrantValue("true")
                    } else {
                      setGrantValueType("numeric")
                      setGrantValue("10")
                    }
                  }}
                  className="w-full h-8 rounded-md border border-input bg-background px-3 text-xs"
                >
                  {CANONICAL_KEYS.map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label htmlFor="grantType" className="text-xs">Type</Label>
                  <select
                    id="grantType"
                    value={grantValueType}
                    onChange={(e) => setGrantValueType(e.target.value)}
                    className="w-full h-8 rounded-md border border-input bg-background px-3 text-xs"
                  >
                    <option value="boolean">Boolean</option>
                    <option value="numeric">Numeric</option>
                    <option value="string">String</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <Label htmlFor="grantVal" className="text-xs">Granted Value *</Label>
                  <Input
                    id="grantVal"
                    value={grantValue}
                    onChange={(e) => setGrantValue(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <Label htmlFor="grantExp" className="text-xs">Duration (Days)</Label>
                <select
                  id="grantExp"
                  value={grantExpiresDays}
                  onChange={(e) => setGrantExpiresDays(e.target.value)}
                  className="w-full h-8 rounded-md border border-input bg-background px-3 text-xs"
                >
                  <option value="7">7 Days</option>
                  <option value="14">14 Days</option>
                  <option value="30">30 Days</option>
                  <option value="90">90 Days</option>
                  <option value="">Indefinite / Permanent</option>
                </select>
              </div>

              <div className="space-y-1">
                <Label htmlFor="grantReason" className="text-xs">
                  Operational Reason (Required for Audit Trail) *
                </Label>
                <Textarea
                  id="grantReason"
                  placeholder="e.g. VIP onboarding exception requested by support ticket #412"
                  value={grantReason}
                  onChange={(e) => setGrantReason(e.target.value)}
                  className="text-xs h-20"
                />
              </div>
            </div>

            <DialogFooter>
              <Button size="sm" variant="outline" onClick={() => setGrantModalOpen(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleCreateGrant} disabled={grantSubmitting}>
                {grantSubmitting ? "Creating..." : "Save Platform Grant"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </MobilePageShell>
  )
}
