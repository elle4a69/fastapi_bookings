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
  secret: string
  events: string[]
}

const AVAILABLE_EVENTS = [
  "booking.created",
  "booking.updated",
  "booking.cancelled",
  "payment.succeeded",
  "payment.failed",
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
      const data = await apiClient.get<WebhookEndpoint[]>("/api/admin/webhooks")
      setWebhooks(data || [])
      if (data?.length > 0) {
        setSelectedId(data[0].id)
      }
    } catch (error) {
      toast.error("Failed to load webhooks")
      // Mock data for development
      setWebhooks([
        { id: "1", url: "https://example.com/webhook", isActive: true, secret: "whsec_mock_123", events: ["booking.created"] }
      ])
      setSelectedId("1")
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async (webhook: WebhookEndpoint) => {
    setSaving(true)
    try {
      if (webhook.id.startsWith("new_")) {
        const { id, ...payload } = webhook
        const created = await apiClient.post<WebhookEndpoint>("/api/admin/webhooks", payload)
        setWebhooks(webhooks.map(w => w.id === webhook.id ? created : w))
        setSelectedId(created.id)
      } else {
        await apiClient.put(`/api/admin/webhooks/${webhook.id}`, webhook)
      }
      toast.success("Webhook saved successfully")
    } catch (error) {
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
    } catch (error) {
      toast.error("Failed to delete webhook")
    }
  }

  const handleAddNew = () => {
    const newId = `new_${Date.now()}`
    const newWebhook: WebhookEndpoint = {
      id: newId,
      url: "",
      isActive: true,
      secret: `whsec_new_${Date.now()}`,
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
                  <div className="flex items-center gap-2">
                    <code className="relative rounded bg-muted px-[0.3rem] py-[0.2rem] font-mono text-sm font-semibold flex-1">
                      {selectedWebhook.secret}
                    </code>
                  </div>
                  <p className="text-xs text-muted-foreground">Use this secret to verify the webhook payload signature.</p>
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
