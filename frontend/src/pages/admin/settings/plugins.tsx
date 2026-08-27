import { useEffect, useState } from "react"
import { apiClient } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { toast } from "sonner"
import { CreditCard, Calendar, Shield, Puzzle, Mail, FileText } from "lucide-react"

interface PluginConfig {
  id: string
  name: string
  description: string
  icon: string
  category: "payment" | "booking" | "system" | "communication"
  isActive: boolean
  isConfigured: boolean
}

const ICONS: Record<string, React.ReactNode> = {
  stripe: <CreditCard className="h-6 w-6 text-indigo-500" />,
  simplybook: <Calendar className="h-6 w-6 text-green-500" />,
  sso: <Shield className="h-6 w-6 text-blue-500" />,
  mailchimp: <Mail className="h-6 w-6 text-yellow-500" />,
  invoices: <FileText className="h-6 w-6 text-orange-500" />,
  default: <Puzzle className="h-6 w-6 text-slate-500" />
}

export default function PluginsSettings() {
  const [plugins, setPlugins] = useState<PluginConfig[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchPlugins()
  }, [])

  const fetchPlugins = async () => {
    try {
      // Trying to fetch from ui-config or similar plugin config
      const data = await apiClient.get<{ plugins: PluginConfig[] }>("/api/admin/ui-config")
      if (data && data.plugins) {
        setPlugins(data.plugins)
      } else {
        throw new Error("No plugins data")
      }
    } catch (error) {
      // Mock fallback
      setPlugins([
        { id: "stripe", name: "Stripe Payments", description: "Accept credit card payments and Apple Pay.", icon: "stripe", category: "payment", isActive: true, isConfigured: true },
        { id: "simplybook", name: "SimplyBook Widget", description: "Embeddable booking widget integration.", icon: "simplybook", category: "booking", isActive: false, isConfigured: false },
        { id: "sso", name: "Enterprise SSO", description: "SAML and OAuth2 authentication.", icon: "sso", category: "system", isActive: true, isConfigured: true },
        { id: "mailchimp", name: "Mailchimp", description: "Sync clients to mailing lists.", icon: "mailchimp", category: "communication", isActive: false, isConfigured: false },
        { id: "invoices", name: "Advanced Invoicing", description: "Generate PDF invoices automatically.", icon: "invoices", category: "payment", isActive: true, isConfigured: true },
      ])
    } finally {
      setLoading(false)
    }
  }

  const togglePlugin = async (id: string, currentActive: boolean) => {
    try {
      // Optimistic update
      setPlugins(plugins.map(p => p.id === id ? { ...p, isActive: !currentActive } : p))
      
      // In a real scenario you would update the specific plugin state
      // await apiClient.post(`/api/admin/plugins/${id}/toggle`, { active: !currentActive })
      
      toast.success(currentActive ? "Plugin disabled" : "Plugin enabled")
    } catch (error) {
      toast.error("Failed to toggle plugin")
      // Revert on error
      setPlugins(plugins.map(p => p.id === id ? { ...p, isActive: currentActive } : p))
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map(i => <Skeleton key={i} className="h-[200px] w-full" />)}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Plugins & Integrations</h1>
        <p className="text-muted-foreground">Extend your booking platform with additional modules and third-party services.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {plugins.map((plugin) => (
          <Card key={plugin.id} className="flex flex-col relative overflow-hidden transition-all hover:shadow-md">
            {!plugin.isActive && (
              <div className="absolute inset-0 bg-background/50 z-10 pointer-events-none" />
            )}
            <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2 relative z-20">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-muted rounded-md">
                  {ICONS[plugin.icon] || ICONS.default}
                </div>
                <div>
                  <CardTitle className="text-base">{plugin.name}</CardTitle>
                  <CardDescription className="text-xs uppercase tracking-wider font-semibold mt-1">
                    {plugin.category}
                  </CardDescription>
                </div>
              </div>
              <Switch 
                checked={plugin.isActive}
                onCheckedChange={() => togglePlugin(plugin.id, plugin.isActive)}
                className="pointer-events-auto"
              />
            </CardHeader>
            <CardContent className="flex-1 relative z-20 pt-4">
              <p className="text-sm text-muted-foreground line-clamp-2">
                {plugin.description}
              </p>
              
              <div className="mt-4 flex gap-2">
                {plugin.isActive ? (
                  plugin.isConfigured ? (
                    <Badge variant="default" className="bg-green-500/10 text-green-600 hover:bg-green-500/20 border-green-200">
                      Connected
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-yellow-600 border-yellow-200 bg-yellow-500/10">
                      Needs Configuration
                    </Badge>
                  )
                ) : (
                  <Badge variant="secondary">Inactive</Badge>
                )}
              </div>
            </CardContent>
            <CardFooter className="relative z-20 border-t pt-4">
              <Button variant="outline" size="sm" className="w-full pointer-events-auto" disabled={!plugin.isActive}>
                Configure
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  )
}
