import { useEffect, useState, useCallback } from "react"
import { apiClient } from "@/lib/api"
import { useAuth } from "@/context/auth-context"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { MobilePageShell } from "@/components/ui/mobile-page-shell"
import { toast } from "sonner"
import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  CreditCardIcon,
  ExternalLinkIcon,
  MapPinIcon,
  UserRoundCogIcon,
  MessageSquareIcon,
  BotIcon,
  ShieldCheckIcon,
  SparklesIcon,
  RefreshCwIcon,
  LockIcon,
} from "lucide-react"

interface QuotaDetail {
  key: string
  label: string
  limit: number | string | null
  current_usage: number
  unit: string
}

interface TenantSubscriptionOverview {
  billing_account?: {
    id: number
    tenant_id: number
    flexprice_customer_id?: string
    billing_state: string
    created_at: string
    updated_at: string
  } | null
  subscription?: {
    id: number
    tenant_id: number
    external_subscription_id: string
    plan_id: string
    plan_version: number
    status: string
    trial_end?: string | null
    current_period_start?: string | null
    current_period_end?: string | null
    cancel_at?: string | null
  } | null
  entitlements: Array<{
    id: number
    tenant_id: number
    entitlement_key: string
    value_type: string
    value: string
    effective_from?: string | null
    expires_at?: string | null
    is_active: boolean
  }>
  plan_name?: string
  status?: string
  billing_cycle?: string
  is_past_due: boolean
  usage_quotas: Record<string, QuotaDetail>
  capabilities: Record<string, boolean>
}

export default function PlanBillingPage() {
  const { isOwner } = useAuth()
  const [loading, setLoading] = useState(true)
  const [portalLoading, setPortalLoading] = useState(false)
  const [portalError, setPortalError] = useState<string | null>(null)
  const [data, setData] = useState<TenantSubscriptionOverview | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchSubscription = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await apiClient.get<TenantSubscriptionOverview>("/api/billing/subscription")
      setData(res)
    } catch (err: any) {
      const msg = err?.message || "Failed to load subscription details"
      setError(msg)
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSubscription()
  }, [fetchSubscription])

  const handleOpenPortal = async () => {
    if (!isOwner) {
      toast.error("Only tenant owners can manage billing and payment methods.")
      return
    }

    try {
      setPortalLoading(true)
      setPortalError(null)
      toast.loading("Connecting to secure billing portal...", { id: "billing-portal" })

      const returnUrl = `${window.location.origin}/admin/plan-billing`
      const res = await apiClient.post<{ portal_url: string; expires_at?: string }>(
        "/api/billing/portal-session",
        { return_url: returnUrl }
      )
      if (res?.portal_url) {
        toast.success("Redirecting to secure billing portal...", { id: "billing-portal" })
        window.location.assign(res.portal_url)
      } else {
        const emptyMsg = "Billing provider returned an empty portal URL. Please try again later."
        setPortalError(emptyMsg)
        toast.error(emptyMsg, { id: "billing-portal" })
      }
    } catch (err: any) {
      const msg = err?.message || "Unable to open billing portal. Service may be temporarily offline."
      setPortalError(msg)
      toast.error(msg, { id: "billing-portal" })
    } finally {
      setPortalLoading(false)
    }
  }

  const getStatusBadge = (statusStr: string | undefined) => {
    const s = (statusStr || "active").toLowerCase()
    switch (s) {
      case "active":
        return <Badge className="bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/25 border-emerald-500/30">Active</Badge>
      case "trialing":
        return <Badge className="bg-blue-500/15 text-blue-600 hover:bg-blue-500/25 border-blue-500/30">Trial</Badge>
      case "past_due":
        return <Badge className="bg-amber-500/15 text-amber-600 hover:bg-amber-500/25 border-amber-500/30">Past Due</Badge>
      case "cancelled":
      case "suspended":
        return <Badge variant="destructive">Cancelled</Badge>
      default:
        return <Badge variant="secondary">{s}</Badge>
    }
  }

  const formatPeriodDate = (isoStr?: string | null) => {
    if (!isoStr) return "N/A"
    try {
      return new Date(isoStr).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    } catch {
      return isoStr
    }
  }

  const renderQuotaBar = (label: string, icon: React.ReactNode, quotaKey: string) => {
    const quota = data?.usage_quotas?.[quotaKey]
    const usage = quota?.current_usage ?? 0
    const rawLimit = quota?.limit
    const limitNum = typeof rawLimit === "number" ? rawLimit : Number(rawLimit) || 0
    const isUnlimited = limitNum >= 10000 || rawLimit === null

    const percent = isUnlimited ? 0 : Math.min(100, Math.round((usage / (limitNum || 1)) * 100))
    const isHigh = percent >= 80 && percent < 100
    const isMax = percent >= 100

    return (
      <div key={quotaKey} className="rounded-lg border bg-card p-4 space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-medium">
            <span className="text-muted-foreground">{icon}</span>
            <span>{label}</span>
          </div>
          <span className="text-xs font-semibold tabular-nums">
            {usage} {isUnlimited ? "/ ∞" : `/ ${limitNum}`} {quota?.unit || ""}
          </span>
        </div>
        <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
          <div
            className={`h-full transition-all duration-300 rounded-full ${
              isMax ? "bg-destructive" : isHigh ? "bg-amber-500" : "bg-primary"
            }`}
            style={{ width: `${isUnlimited ? (usage > 0 ? 10 : 0) : percent}%` }}
          />
        </div>
        <div className="flex justify-between text-[11px] text-muted-foreground">
          <span>{isUnlimited ? "Unlimited entitlement" : `${percent}% allocated`}</span>
          {isMax && <span className="text-destructive font-medium">Limit reached</span>}
        </div>
      </div>
    )
  }

  return (
    <MobilePageShell
      title="Plan & Billing"
      description="Manage your practice subscription plan, included quotas, and secure hosted payment methods."
    >
      <div className="space-y-6 max-w-6xl pb-12">
        {/* Portal Connection Error Banner */}
        {portalError && (
          <div className="flex items-start justify-between gap-3 p-4 rounded-xl border border-destructive/40 bg-destructive/10 text-destructive animate-in fade-in slide-in-from-top-2">
            <div className="flex items-start gap-3">
              <AlertTriangleIcon className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
              <div className="space-y-1 text-sm">
                <p className="font-semibold text-destructive">
                  Unable to Connect to Billing Provider
                </p>
                <p className="text-xs leading-relaxed text-destructive/90">
                  The billing service (Flexprice) is currently offline, unreachable on port 8085, or not configured in this environment. Please ensure the Flexprice provider container is running or contact system support.
                </p>
                <div className="mt-2 text-xs font-mono bg-destructive/15 p-2 rounded border border-destructive/30 break-all">
                  {portalError}
                </div>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2.5 text-xs text-destructive hover:bg-destructive/20 hover:text-destructive shrink-0"
              onClick={() => setPortalError(null)}
            >
              Dismiss
            </Button>
          </div>
        )}

        {/* Past Due Grace Period Alert Banner */}
        {data?.is_past_due && (
          <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200">
            <AlertTriangleIcon className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div className="space-y-1 text-sm">
              <p className="font-semibold">Payment Past Due (Grace Period Active)</p>
              <p className="text-xs leading-relaxed text-amber-800 dark:text-amber-300">
                Your latest subscription invoice could not be automatically charged. Your features and bookings remain active during the grace period. Please update your payment method via the customer portal to prevent service interruption.
              </p>
              <div className="pt-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="border-amber-500/40 text-amber-900 dark:text-amber-100 hover:bg-amber-500/20"
                  onClick={handleOpenPortal}
                  disabled={portalLoading || !isOwner}
                >
                  {portalLoading ? (
                    <RefreshCwIcon className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                  ) : (
                    <CreditCardIcon className="h-3.5 w-3.5 mr-1.5" />
                  )}
                  {portalLoading ? "Connecting..." : "Update Payment Method"}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Loading Skeleton */}
        {loading && (
          <div className="space-y-4">
            <Skeleton className="h-44 w-full rounded-xl" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Skeleton className="h-40 rounded-xl" />
              <Skeleton className="h-40 rounded-xl" />
            </div>
          </div>
        )}

        {/* Main Subscription Card */}
        {!loading && data && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2 shadow-sm border">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-xl flex items-center gap-2">
                      <span>{data.plan_name || "Starter"} Plan</span>
                      {getStatusBadge(data.status)}
                    </CardTitle>
                    <CardDescription className="pt-1">
                      Billing Cycle: <span className="font-medium text-foreground capitalize">{data.billing_cycle || "monthly"}</span>
                    </CardDescription>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={fetchSubscription}
                    className="h-8 w-8 p-0"
                    title="Refresh billing data"
                  >
                    <RefreshCwIcon className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4 pt-2">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 p-4 rounded-lg bg-muted/40 border border-border/50 text-sm">
                  <div>
                    <p className="text-xs text-muted-foreground">Current Period Ends</p>
                    <p className="font-medium pt-0.5">
                      {formatPeriodDate(data.subscription?.current_period_end)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Account Status</p>
                    <p className="font-medium pt-0.5 capitalize">
                      {data.billing_account?.billing_state || data.status || "Active"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Hosted Checkout</p>
                    <p className="font-medium pt-0.5 text-emerald-600 flex items-center gap-1">
                      <ShieldCheckIcon className="h-3.5 w-3.5" />
                      Encrypted (PCI-DSS)
                    </p>
                  </div>
                </div>

                <div className="rounded-lg border border-border/40 p-4 space-y-2 bg-card">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Included Capabilities
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
                    <div className="flex items-center gap-2 text-xs">
                      {data.capabilities?.["assistant.enabled"] ? (
                        <CheckCircle2Icon className="h-4 w-4 text-emerald-500 shrink-0" />
                      ) : (
                        <LockIcon className="h-4 w-4 text-muted-foreground/60 shrink-0" />
                      )}
                      <span className={data.capabilities?.["assistant.enabled"] ? "font-medium" : "text-muted-foreground"}>
                        AI Voice Assistant
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-xs">
                      {data.capabilities?.["sms.enabled"] ? (
                        <CheckCircle2Icon className="h-4 w-4 text-emerald-500 shrink-0" />
                      ) : (
                        <LockIcon className="h-4 w-4 text-muted-foreground/60 shrink-0" />
                      )}
                      <span className={data.capabilities?.["sms.enabled"] ? "font-medium" : "text-muted-foreground"}>
                        SMS Communications
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-xs">
                      {data.capabilities?.["api.enabled"] ? (
                        <CheckCircle2Icon className="h-4 w-4 text-emerald-500 shrink-0" />
                      ) : (
                        <LockIcon className="h-4 w-4 text-muted-foreground/60 shrink-0" />
                      )}
                      <span className={data.capabilities?.["api.enabled"] ? "font-medium" : "text-muted-foreground"}>
                        Developer API Access
                      </span>
                    </div>
                  </div>
                </div>
              </CardContent>
              <CardFooter className="pt-2 border-t flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <ShieldCheckIcon className="h-4 w-4 text-muted-foreground" />
                  Payment methods and plan upgrades are securely managed via Flexprice.
                </p>
                <div className="flex flex-col items-end gap-1">
                  <Button
                    onClick={handleOpenPortal}
                    disabled={portalLoading || !isOwner}
                    className="font-medium"
                  >
                    {portalLoading ? (
                      <RefreshCwIcon className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <CreditCardIcon className="h-4 w-4 mr-2" />
                    )}
                    {portalLoading ? "Connecting to Portal..." : "Manage Billing & Payment Methods"}
                    {!portalLoading && <ExternalLinkIcon className="h-3.5 w-3.5 ml-2 opacity-70" />}
                  </Button>
                  {!isOwner && (
                    <span className="text-[11px] text-muted-foreground">
                      * Tenant owner role required to manage billing
                    </span>
                  )}
                </div>
              </CardFooter>
            </Card>

            {/* Quick Security & Portal Info Callout */}
            <Card className="shadow-sm border flex flex-col justify-between">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <SparklesIcon className="h-4 w-4 text-primary" />
                  Self-Service Portal
                </CardTitle>
                <CardDescription className="text-xs leading-relaxed">
                  Use the customer billing portal to update payment instruments, inspect past platform invoices, or modify tier subscriptions.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-xs text-muted-foreground">
                <div className="p-3 rounded-md bg-muted/50 border border-border/50 space-y-1">
                  <p className="font-semibold text-foreground">Zero Card Data Retention</p>
                  <p className="leading-relaxed">
                    Credit card numbers, CVVs, and banking credentials are never transmitted through or stored in our database.
                  </p>
                </div>
                <div className="p-3 rounded-md bg-muted/50 border border-border/50 space-y-1">
                  <p className="font-semibold text-foreground">Immediate Quota Upgrades</p>
                  <p className="leading-relaxed">
                    Tier upgrades take effect instantly across all scheduling, location, and assistant modules.
                  </p>
                </div>
              </CardContent>
              <CardFooter className="border-t pt-3 flex flex-col gap-1.5 items-stretch">
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={handleOpenPortal}
                  disabled={portalLoading || !isOwner}
                >
                  {portalLoading ? (
                    <>
                      <RefreshCwIcon className="h-3.5 w-3.5 mr-2 animate-spin" />
                      Connecting to Portal...
                    </>
                  ) : (
                    <>
                      Launch Customer Portal
                      <ExternalLinkIcon className="h-3 w-3 ml-1.5 opacity-70" />
                    </>
                  )}
                </Button>
                {!isOwner && (
                  <p className="text-[11px] text-muted-foreground text-center">
                    Tenant owner role required
                  </p>
                )}
              </CardFooter>
            </Card>
          </div>
        )}

        {/* Quotas & Usage Consumption Section */}
        {!loading && data && (
          <div className="space-y-3">
            <div>
              <h3 className="text-base font-semibold">Included Quotas & Real-Time Usage</h3>
              <p className="text-xs text-muted-foreground">
                Current cycle allocation and active entity consumption for this tenant.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {renderQuotaBar("Locations", <MapPinIcon className="h-4 w-4" />, "locations.max")}
              {renderQuotaBar("Staff Providers", <UserRoundCogIcon className="h-4 w-4" />, "providers.max")}
              {renderQuotaBar("SMS Messages", <MessageSquareIcon className="h-4 w-4" />, "sms.monthly_outbound_messages")}
              {renderQuotaBar("Assistant Runs", <BotIcon className="h-4 w-4" />, "assistant.monthly_runs")}
            </div>
          </div>
        )}

        {error && !loading && (
          <div className="p-6 rounded-xl border border-destructive/30 bg-destructive/5 text-destructive space-y-3">
            <p className="font-semibold text-sm">Failed to retrieve subscription status</p>
            <p className="text-xs">{error}</p>
            <Button size="sm" variant="outline" onClick={fetchSubscription}>
              Try Again
            </Button>
          </div>
        )}
      </div>
    </MobilePageShell>
  )
}
