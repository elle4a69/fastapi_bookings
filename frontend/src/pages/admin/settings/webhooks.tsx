import { useEffect, useState } from "react"
import { apiClient } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { toast } from "sonner"
import { Plus, Trash2, Webhook } from "lucide-react"

interface WebhookEndpoint {
  id: string
  url: string
  isActive: boolean
  hasSecret: boolean
  secretInput: string
  events: string[]
}

const AVAILABLE_EVENTS = [
  "booking.created",
  "booking.confirmed",
  "booking.cancelled",
  "booking.completed",
  "booking.rescheduled",
  "booking.no_show",
  "client.created",
]

export default function WebhooksSettings() {
  const [webhooks, setWebhooks] = useState<WebhookEndpoint[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchWebhooks()
  }, [])

  const fetchWebhooks = async () => {
    try {
      const res: any = await apiClient.get("/api/admin/webhooks")
      const rawList = Array.isArray(res) ? res : res?.data || []
      const list: WebhookEndpoint[] = rawList.map((item: any) => ({
        id: String(item.id),
        url: item.target_url || item.url || "",
        isActive: item.is_active ?? item.isActive ?? true,
        hasSecret: Boolean(item.has_secret),
        // Secrets are intentionally write-only.  Never copy a response value
        // into state, including for legacy servers that may still return one.
        secretInput: "",
        events: item.events || (item.event ? [item.event] : [])
      }))
      setWebhooks(list)
      if (list.length > 0) {
        setSelectedId(list[0].id)
      }
    } catch {
      toast.error("Failed to load webhooks")
      setWebhooks([])
      setSelectedId(null)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async (webhook: WebhookEndpoint) => {
    if (webhook.id.startsWith("new_") && webhook.secretInput.trim().length < 32) {
      toast.error("A new webhook requires a signing secret of at least 32 characters")
      return
    }
    if (webhook.secretInput && webhook.secretInput.trim().length < 32) {
      toast.error("A replacement signing secret must be at least 32 characters")
      return
    }
    setSaving(true)
    try {
      const payload = {
        target_url: webhook.url,
        is_active: webhook.isActive,
        ...(webhook.secretInput ? { secret: webhook.secretInput } : {}),
        event: webhook.events[0] || "booking.created"
      }
      if (webhook.id.startsWith("new_")) {
        const res: any = await apiClient.post("/api/admin/webhooks", payload)
        const created = res?.data ?? res
        const newEndpoint: WebhookEndpoint = {
          id: String(created.id),
          url: created.target_url || webhook.url,
          isActive: created.is_active ?? webhook.isActive,
          hasSecret: Boolean(created.has_secret) || Boolean(webhook.secretInput),
          secretInput: "",
          events: webhook.events
        }
        setWebhooks(webhooks.map(w => w.id === webhook.id ? newEndpoint : w))
        setSelectedId(newEndpoint.id)
      } else {
        const res: any = await apiClient.put(`/api/admin/webhooks/${webhook.id}`, payload)
        const updated = res?.data ?? res
        setWebhooks(webhooks.map(w => w.id === webhook.id ? {
          ...w,
          url: updated.target_url || webhook.url,
          isActive: updated.is_active ?? webhook.isActive,
          hasSecret: Boolean(updated.has_secret) || Boolean(webhook.secretInput),
          secretInput: "",
          events: webhook.events,
        } : w))
      }
      toast.success("Webhook saved successfully")
    } catch {
      toast.error("Failed to save webhook")
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      if (!id.startsWith("new_")) {
        await apiClient.delete(`/api/admin/webhooks/${id}`)
      }
      setWebhooks(webhooks.filter(w => w.id !== id))
      if (selectedId === id) setSelectedId(null)
      toast.success("Webhook deleted")
    } catch {
      toast.error("Failed to delete webhook")
    }
  }

  const handleAddNew = () => {
    const newId = `new_${Date.now()}`
    const newWebhook: WebhookEndpoint = {
      id: newId,
      url: "",
      isActive: true,
      hasSecret: false,
      secretInput: "",
      events: []
    }
    setWebhooks([...webhooks, newWebhook])
    setSelectedId(newId)
  }

  const updateSelected = (updates: Partial<WebhookEndpoint>) => {
    setWebhooks(webhooks.map(w => w.id === selectedId ? { ...w, ...updates } : w))
  }

  const toggleEvent = (event: string) => {
    const current = selectedWebhook?.events || []
    const events = current.includes(event) 
      ? current.filter(e => e !== event)
      : [...current, event]
    updateSelected({ events })
  }

  if (loading) {
    return <Skeleton className="h-[600px] w-full" />
  }

  const selectedWebhook = webhooks.find(w => w.id === selectedId)

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-6">
      <div className="w-1/3 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Webhooks</h1>
            <p className="text-sm text-muted-foreground">Manage event endpoints</p>
          </div>
          <Button size="sm" onClick={handleAddNew}>
            <Plus className="mr-2 h-4 w-4" /> Add
          </Button>
        </div>
        
        <Card className="flex-1 flex flex-col overflow-hidden">
          <ScrollArea className="flex-1">
            <div className="p-4 space-y-2">
              {webhooks.length === 0 ? (
                <div className="text-center text-sm text-muted-foreground py-8">
                  No webhooks configured.
                </div>
              ) : (
                webhooks.map((wh) => (
                  <button
                    key={wh.id}
                    onClick={() => setSelectedId(wh.id)}
                    className={`w-full text-left flex items-start gap-3 rounded-lg p-3 text-sm transition-colors ${
                      selectedId === wh.id ? "bg-accent" : "hover:bg-accent/50"
                    }`}
                  >
                    <Webhook className="mt-0.5 h-4 w-4 text-muted-foreground" />
                    <div className="flex-1 overflow-hidden">
                      <p className="font-medium truncate">{wh.url || "New Endpoint"}</p>
                      <p className="text-xs text-muted-foreground">{wh.events.length} events</p>
                    </div>
                    {wh.isActive ? (
                      <Badge variant="default" className="text-[10px]">Active</Badge>
                    ) : (
                      <Badge variant="secondary" className="text-[10px]">Inactive</Badge>
                    )}
                  </button>
                ))
              )}
            </div>
          </ScrollArea>
        </Card>
      </div>

      <div className="w-2/3">
        {selectedWebhook ? (
          <Card className="h-full flex flex-col">
            <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-4 border-b">
              <div className="space-y-1">
                <CardTitle>Endpoint Details</CardTitle>
                <CardDescription>Configure where and what we send.</CardDescription>
              </div>
              <Button variant="destructive" size="icon" onClick={() => handleDelete(selectedWebhook.id)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </CardHeader>
            <ScrollArea className="flex-1">
              <CardContent className="space-y-6 pt-6">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-base">Active</Label>
                    <p className="text-sm text-muted-foreground">Enable or disable this endpoint.</p>
                  </div>
                  <Switch
                    checked={selectedWebhook.isActive}
                    onCheckedChange={(c) => updateSelected({ isActive: c })}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="url">Target URL</Label>
                  <Input
                    id="url"
                    value={selectedWebhook.url}
                    onChange={(e) => updateSelected({ url: e.target.value })}
                    placeholder="https://your-domain.com/webhook"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Signing Secret</Label>
                  <Input
                    type="password"
                    autoComplete="new-password"
                    value={selectedWebhook.secretInput}
                    onChange={(e) => updateSelected({ secretInput: e.target.value })}
                    placeholder={selectedWebhook.hasSecret ? "Enter a new value to rotate the existing secret" : "Required signing secret (32+ characters)"}
                  />
                  <p className="text-xs text-muted-foreground">
                    {selectedWebhook.hasSecret
                      ? "A signing secret is configured. Enter a new value only to rotate it; the existing value cannot be viewed."
                      : "Required for a new endpoint. Once saved, a signing secret cannot be viewed again."}
                  </p>
                </div>

                <Separator />

                <div className="space-y-4">
                  <div className="space-y-1">
                    <Label className="text-base">Events to send</Label>
                    <p className="text-sm text-muted-foreground">Select which events should trigger this webhook.</p>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    {AVAILABLE_EVENTS.map(event => (
                      <div key={event} className="flex items-center space-x-2">
                        <Checkbox 
                          id={`event-${event}`} 
                          checked={selectedWebhook.events.includes(event)}
                          onCheckedChange={() => toggleEvent(event)}
                        />
                        <label
                          htmlFor={`event-${event}`}
                          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                        >
                          {event}
                        </label>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </ScrollArea>
            <CardFooter className="border-t pt-6 justify-end">
              <Button onClick={() => handleSave(selectedWebhook)} disabled={saving}>
                {saving ? "Saving..." : "Save Endpoint"}
              </Button>
            </CardFooter>
          </Card>
        ) : (
          <div className="h-full flex items-center justify-center border rounded-xl bg-muted/30 border-dashed">
            <div className="text-center space-y-2">
              <Webhook className="mx-auto h-8 w-8 text-muted-foreground" />
              <p className="text-sm font-medium">Select a webhook</p>
              <p className="text-xs text-muted-foreground">Click on a webhook in the sidebar to view details.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
