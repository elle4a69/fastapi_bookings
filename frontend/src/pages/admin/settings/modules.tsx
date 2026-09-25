import { useState, useMemo } from "react"
import { useTenantModules, type TenantModuleInfo } from "@/context/tenant-modules-context"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { MobilePageShell } from "@/components/ui/mobile-page-shell"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { toast } from "sonner"
import {
  LayoutDashboardIcon,
  CalendarDaysIcon,
  ClipboardListIcon,
  GlobeIcon,
  MessageSquareTextIcon,
  MapPinIcon,
  UserRoundCogIcon,
  GiftIcon,
  LandmarkIcon,
  ImagesIcon,
  FileInputIcon,
  StarIcon,
  CalendarClockIcon,
  SparklesIcon,
  BoxesIcon,
  LockIcon,
  AlertCircleIcon,
  LayersIcon,
} from "lucide-react"

// Map icon strings to Lucide components
const ICON_MAP: Record<string, any> = {
  LayoutDashboard: LayoutDashboardIcon,
  Calendar: CalendarDaysIcon,
  ClipboardList: ClipboardListIcon,
  Globe: GlobeIcon,
  MessageSquareText: MessageSquareTextIcon,
  MapPin: MapPinIcon,
  UserRoundCog: UserRoundCogIcon,
  Gift: GiftIcon,
  Landmark: LandmarkIcon,
  Images: ImagesIcon,
  FileInput: FileInputIcon,
  Star: StarIcon,
  CalendarClock: CalendarClockIcon,
}

export default function TenantModulesPage() {
  const { modulesData, loading, toggleModule, updateTier } = useTenantModules()
  const [activeCategory, setActiveCategory] = useState<string>("all")
  const [togglePendingKey, setTogglePendingKey] = useState<string | null>(null)
  const [quotaModalOpen, setQuotaModalOpen] = useState<boolean>(false)
  const [tierPending, setTierPending] = useState<boolean>(false)

  const categories = useMemo(() => {
    if (!modulesData) return ["all"]
    const cats = Array.from(new Set(modulesData.modules.map((m) => m.category)))
    return ["all", ...cats]
  }, [modulesData])

  const filteredModules = useMemo(() => {
    if (!modulesData) return []
    if (activeCategory === "all") return modulesData.modules
    return modulesData.modules.filter((m) => m.category.toLowerCase() === activeCategory.toLowerCase())
  }, [modulesData, activeCategory])

  const handleToggle = async (module: TenantModuleInfo, nextValue: boolean) => {
    if (module.is_core && !nextValue) {
      toast.error("Core modules are required and cannot be turned off.")
      return
    }

    if (nextValue && !module.is_core && !module.enabled) {
      if (modulesData && modulesData.tier !== "unlimited" && modulesData.available_addons <= 0) {
        setQuotaModalOpen(true)
        toast.warning(
          `Add-on quota reached (${modulesData.used_addons}/${modulesData.addon_quota}). Upgrade plan to unlock more!`
        )
        return
      }
    }

    try {
      setTogglePendingKey(module.key)
      const res = await toggleModule(module.key, nextValue)
      toast.success(res.message)
    } catch (err: any) {
      toast.error(err.message || "Failed to toggle module")
    } finally {
      setTogglePendingKey(null)
    }
  }

  const handleTierSwitch = async (tier: string) => {
    try {
      setTierPending(true)
      await updateTier(tier)
      toast.success(`Plan successfully switched to ${tier.toUpperCase()}!`)
      setQuotaModalOpen(false)
    } catch (err: any) {
      toast.error(err.message || "Failed to switch plan tier")
    } finally {
      setTierPending(false)
    }
  }

  if (loading && !modulesData) {
    return (
      <div className="space-y-6 max-w-7xl mx-auto pb-12">
        <div className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-96" />
        </div>
        <Skeleton className="h-32 w-full rounded-xl" />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-48 rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  const tier = modulesData?.tier || "starter"
  const addonQuota = modulesData?.addon_quota ?? 0
  const usedAddons = modulesData?.used_addons ?? 0
  const isUnlimited = tier === "unlimited"
  const quotaPercentage = isUnlimited
    ? 100
    : addonQuota > 0
    ? Math.min(100, Math.round((usedAddons / addonQuota) * 100))
    : 0

  return (
    <MobilePageShell
      title="Modules & App Store"
      description="Enable only the features your business requires. The navigation automatically adapts to declutter your workspace."
      actions={
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Plan:</span>
          {tier === "unlimited" && (
            <Badge className="bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-semibold shadow-xs px-3 py-1 flex items-center gap-1.5">
              <SparklesIcon className="h-3.5 w-3.5" />
              Unlimited
            </Badge>
          )}
          {tier === "growth" && (
            <Badge className="bg-emerald-600 text-white font-semibold shadow-xs px-3 py-1 flex items-center gap-1.5">
              <LayersIcon className="h-3.5 w-3.5" />
              Growth
            </Badge>
          )}
          {tier === "starter" && (
            <Badge variant="outline" className="border-primary/40 text-primary font-semibold px-3 py-1">
              Starter
            </Badge>
          )}
        </div>
      }
    >
      <div className="space-y-6">
        {/* Plan Entitlements & Quota Progress Banner */}
        <Card className="border shadow-xs bg-gradient-to-br from-card via-card to-muted/20">
          <CardContent className="p-4 sm:p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
              {/* Left: Summary */}
              <div className="md:col-span-2 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">Add-on Quota Utilization</span>
                    <Badge variant="secondary" className="text-xs font-medium">
                      {isUnlimited ? "Unlimited Add-ons" : `${usedAddons} of ${addonQuota} Active`}
                    </Badge>
                  </div>
                  {!isUnlimited && (
                    <span className="text-xs font-medium text-muted-foreground">
                      {modulesData?.available_addons ?? 0} available slot(s)
                    </span>
                  )}
                </div>

                {/* Progress Bar */}
                <div className="w-full bg-secondary/80 h-3 rounded-full overflow-hidden p-0.5 border border-border/40">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      isUnlimited
                        ? "bg-gradient-to-r from-violet-500 to-indigo-500"
                        : quotaPercentage >= 100
                        ? "bg-amber-500"
                        : "bg-primary"
                    }`}
                    style={{ width: `${isUnlimited ? 100 : quotaPercentage}%` }}
                  />
                </div>

                <p className="text-xs text-muted-foreground leading-relaxed">
                  {tier === "starter" &&
                    "Starter plan provides core single-location booking essentials. Upgrade to Growth to activate up to 3 custom add-ons."}
                  {tier === "growth" &&
                    "Growth plan includes core modules plus up to 3 specialized add-on modules of your choice."}
                  {tier === "unlimited" &&
                    "Unlimited Enterprise tier unlocks every feature, unlimited add-ons, AI capabilities, and integrations."}
                </p>
              </div>

              {/* Right: Quick Plan Switcher */}
              <div className="flex flex-col gap-2 md:border-l md:pl-6">
                <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Switch Plan
                </span>
                <div className="grid grid-cols-3 gap-1.5 bg-muted/60 p-1.5 rounded-lg border">
                  <Button
                    size="sm"
                    variant={tier === "starter" ? "default" : "ghost"}
                    disabled={tierPending || tier === "starter"}
                    onClick={() => handleTierSwitch("starter")}
                    className="h-10 min-h-[44px] text-xs font-semibold touch-manipulation"
                  >
                    Starter
                  </Button>
                  <Button
                    size="sm"
                    variant={tier === "growth" ? "default" : "ghost"}
                    disabled={tierPending || tier === "growth"}
                    onClick={() => handleTierSwitch("growth")}
                    className="h-10 min-h-[44px] text-xs font-semibold touch-manipulation"
                  >
                    Growth
                  </Button>
                  <Button
                    size="sm"
                    variant={tier === "unlimited" ? "default" : "ghost"}
                    disabled={tierPending || tier === "unlimited"}
                    onClick={() => handleTierSwitch("unlimited")}
                    className="h-10 min-h-[44px] text-xs font-semibold touch-manipulation"
                  >
                    Unlimited
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Category Filter Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none touch-manipulation -mx-1 px-1">
          {categories.map((cat) => {
            const isSelected = activeCategory === cat
            return (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`h-10 min-h-[44px] min-w-[44px] px-4 rounded-full text-xs font-medium capitalize transition-all whitespace-nowrap cursor-pointer touch-manipulation flex items-center justify-center ${
                  isSelected
                    ? "bg-primary text-primary-foreground shadow-xs"
                    : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground active:bg-muted"
                }`}
              >
                {cat === "all" ? "All Modules" : cat}
              </button>
            )
          })}
        </div>

        {/* Modules Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredModules.map((mod) => {
            const IconComponent = ICON_MAP[mod.icon] || BoxesIcon
            const isToggling = togglePendingKey === mod.key

            return (
              <Card
                key={mod.key}
                className={`flex flex-col justify-between border transition-all duration-200 ${
                  mod.enabled
                    ? "border-primary/30 bg-card shadow-xs"
                    : "border-border/60 bg-muted/20 opacity-80 hover:opacity-100"
                }`}
              >
                <CardHeader className="p-4 pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div
                        className={`p-2.5 rounded-xl transition-colors shrink-0 ${
                          mod.enabled ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                        }`}
                      >
                        <IconComponent className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <CardTitle className="text-base font-bold tracking-tight leading-snug truncate">
                          {mod.name}
                        </CardTitle>
                        <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider block">
                          {mod.category}
                        </span>
                      </div>
                    </div>

                    {mod.is_core ? (
                      <Badge variant="outline" className="text-[10px] font-semibold uppercase bg-muted/50 shrink-0">
                        Core
                      </Badge>
                    ) : (
                      <Badge
                        variant={mod.enabled ? "default" : "secondary"}
                        className="text-[10px] font-semibold uppercase shrink-0"
                      >
                        {mod.enabled ? "Active" : "Inactive"}
                      </Badge>
                    )}
                  </div>
                </CardHeader>

                <CardContent className="px-4 pb-4 flex-1">
                  <CardDescription className="text-xs leading-relaxed text-muted-foreground line-clamp-3">
                    {mod.description}
                  </CardDescription>
                </CardContent>

                <CardFooter className="p-4 pt-3 border-t border-border/40 flex items-center justify-between bg-muted/10">
                  {mod.is_core ? (
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
                      <LockIcon className="h-3.5 w-3.5 text-muted-foreground/70 shrink-0" />
                      <span>Included in all plans</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-medium ${
                          mod.enabled ? "text-primary font-semibold" : "text-muted-foreground"
                        }`}
                      >
                        {mod.enabled ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                  )}

                  <div className="min-h-[44px] min-w-[44px] flex items-center justify-end">
                    <Switch
                      checked={mod.enabled}
                      disabled={mod.is_core || isToggling}
                      onCheckedChange={(checked) => handleToggle(mod, checked)}
                      aria-label={`Toggle ${mod.name}`}
                      className="touch-manipulation"
                    />
                  </div>
                </CardFooter>
              </Card>
            )
          })}
        </div>

        {/* Upgrade / Quota Modal */}
        <Dialog open={quotaModalOpen} onOpenChange={setQuotaModalOpen}>
          <DialogContent className="w-full sm:max-w-md p-4 sm:p-6">
            <DialogHeader>
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400 mb-2">
                <AlertCircleIcon className="h-6 w-6" />
              </div>
              <DialogTitle className="text-center text-lg font-bold">Add-on Quota Reached</DialogTitle>
              <DialogDescription className="text-center text-xs sm:text-sm text-muted-foreground">
                Your current <span className="font-semibold capitalize">{tier}</span> tier includes{" "}
                <span className="font-semibold">{addonQuota}</span> active add-on(s). To enable additional capabilities,
                please upgrade your plan.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-2">
              <div className="p-3.5 rounded-xl border bg-muted/30 space-y-1">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span>Growth Plan</span>
                  <span className="text-emerald-600 dark:text-emerald-400">3 Add-ons</span>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Great for scaling single-site or expanding boutique clinics.
                </p>
              </div>

              <div className="p-3.5 rounded-xl border bg-muted/30 space-y-1">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span>Unlimited Enterprise</span>
                  <span className="text-violet-600 dark:text-violet-400">Unlimited Everything</span>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Full access to multi-location, all staff providers, AI assistant, and custom integrations.
                </p>
              </div>
            </div>

            <DialogFooter className="flex flex-col-reverse sm:flex-row gap-2">
              <Button 
                variant="outline" 
                onClick={() => setQuotaModalOpen(false)} 
                className="h-10 min-h-[44px] w-full sm:w-auto touch-manipulation"
              >
                Cancel
              </Button>
              {tier === "starter" ? (
                <Button
                  onClick={() => handleTierSwitch("growth")}
                  disabled={tierPending}
                  className="h-10 min-h-[44px] w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700 text-white touch-manipulation"
                >
                  Upgrade to Growth
                </Button>
              ) : (
                <Button
                  onClick={() => handleTierSwitch("unlimited")}
                  disabled={tierPending}
                  className="h-10 min-h-[44px] w-full sm:w-auto bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white touch-manipulation"
                >
                  Upgrade to Unlimited
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </MobilePageShell>
  )
}
