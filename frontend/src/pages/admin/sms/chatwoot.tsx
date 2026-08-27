import { useState, useEffect } from "react";
import { Plus, Edit2, Trash2, Link2, KeyRound } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

interface SmsChatwootBinding {
  id: number;
  provider_id: number;
  chatwoot_account_id: number;
  chatwoot_inbox_id: number;
  chatwoot_base_url: string;
  chatwoot_api_token: string;
  is_enabled: boolean;
}

export default function SmsChatwootTab() {
  const [bindings, setBindings] = useState<SmsChatwootBinding[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingBinding, setEditingBinding] = useState<SmsChatwootBinding | null>(null);

  // Form states
  const [providerId, setProviderId] = useState("");
  const [chatwootAccountId, setChatwootAccountId] = useState("");
  const [chatwootInboxId, setChatwootInboxId] = useState("");
  const [chatwootBaseUrl, setChatwootBaseUrl] = useState("https://app.chatwoot.com");
  const [chatwootApiToken, setChatwootApiToken] = useState("");
  const [isEnabled, setIsEnabled] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [bindRes, provRes] = await Promise.all([
        apiClient.get<SmsChatwootBinding[]>("/api/admin/sms/chatwoot/bindings"),
        apiClient.get<any>("/api/admin/providers")
      ]);
      setBindings(bindRes);
      setProviders(Array.isArray(provRes) ? provRes : (provRes?.data ?? []));
    } catch (err: any) {
      toast.error(err.message || "Failed to load Chatwoot bindings.");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreate = () => {
    setEditingBinding(null);
    setProviderId(providers[0]?.id ? String(providers[0].id) : "");
    setChatwootAccountId("");
    setChatwootInboxId("");
    setChatwootBaseUrl("https://app.chatwoot.com");
    setChatwootApiToken("");
    setIsEnabled(true);
    setDialogOpen(true);
  };

  const handleOpenEdit = (bind: SmsChatwootBinding) => {
    setEditingBinding(bind);
    setProviderId(String(bind.provider_id || providers[0]?.id || ""));
    setChatwootAccountId(String(bind.chatwoot_account_id));
    setChatwootInboxId(String(bind.chatwoot_inbox_id));
    setChatwootBaseUrl(bind.chatwoot_base_url);
    setChatwootApiToken(bind.chatwoot_api_token); // Will be masked as ********
    setIsEnabled(bind.is_enabled);
    setDialogOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!providerId || !chatwootAccountId || !chatwootInboxId || !chatwootBaseUrl || !chatwootApiToken) {
      toast.error("Please fill in all required fields.");
      return;
    }

    const payload = {
      provider_id: Number(providerId),
      chatwoot_account_id: Number(chatwootAccountId),
      chatwoot_inbox_id: Number(chatwootInboxId),
      chatwoot_base_url: chatwootBaseUrl,
      chatwoot_api_token: chatwootApiToken,
      is_enabled: isEnabled
    };

    try {
      if (editingBinding) {
        await apiClient.put(`/api/admin/sms/chatwoot/bindings/${editingBinding.id}`, payload);
        toast.success("Chatwoot binding updated successfully.");
      } else {
        await apiClient.post("/api/admin/sms/chatwoot/bindings", payload);
        toast.success("Chatwoot binding created successfully.");
      }
      setDialogOpen(false);
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to save Chatwoot binding.");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this Chatwoot binding?")) {
      return;
    }
    try {
      await apiClient.delete(`/api/admin/sms/chatwoot/bindings/${id}`);
      toast.success("Chatwoot binding deleted successfully.");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to delete Chatwoot binding.");
    }
  };

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Chatwoot Integrations</h2>
            <p className="text-sm text-muted-foreground">
              Map booking providers to Chatwoot accounts and inboxes to synchronize customer conversations.
            </p>
          </div>
          <Button onClick={handleOpenCreate} size="sm" className="gap-2">
            <Plus className="w-4 h-4" /> Add Binding
          </Button>
        </div>

        {loading ? (
          <div className="flex justify-center items-center py-8">
            <span className="animate-spin mr-2">⏳</span> Loading...
          </div>
        ) : bindings.length === 0 ? (
          <div className="flex flex-col items-center justify-center border-2 border-dashed rounded-lg py-12 px-4 text-center">
            <Link2 className="w-10 h-10 text-muted-foreground mb-3" />
            <h3 className="font-semibold text-sm">No Chatwoot Bindings</h3>
            <p className="text-xs text-muted-foreground max-w-xs mt-1 mb-4">
              Map a booking provider to Chatwoot to sync customer support messages.
            </p>
            <Button onClick={handleOpenCreate} variant="outline" size="sm">
              Create your first binding
            </Button>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Provider</TableHead>
                <TableHead>Account ID</TableHead>
                <TableHead>Inbox ID</TableHead>
                <TableHead>Base URL</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-20 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {bindings.map((bind) => {
                const provider = providers.find((p) => p.id === bind.provider_id);
                return (
                  <TableRow key={bind.id}>
                    <TableCell className="font-medium">
                      {provider ? provider.name : `Provider #${bind.provider_id}`}
                    </TableCell>
                    <TableCell>{bind.chatwoot_account_id}</TableCell>
                    <TableCell>{bind.chatwoot_inbox_id}</TableCell>
                    <TableCell className="font-mono text-[10px] text-muted-foreground">
                      {bind.chatwoot_base_url}
                    </TableCell>
                    <TableCell>
                      {bind.is_enabled ? (
                        <Badge className="bg-green-500/10 text-green-600 border-green-500/20 hover:bg-green-500/20 text-[10px]">Enabled</Badge>
                      ) : (
                        <Badge variant="secondary" className="text-[10px]">Disabled</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          onClick={() => handleOpenEdit(bind)}
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </Button>
                        <Button
                          onClick={() => handleDelete(bind.id)}
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive hover:text-destructive hover:bg-destructive/10"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle>
                {editingBinding ? "Edit Chatwoot Binding" : "Add Chatwoot Binding"}
              </DialogTitle>
              <DialogDescription>
                Configure the API credentials and mapping rules for Chatwoot.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSave} className="space-y-4 py-2">
              <div className="grid gap-2">
                <Label htmlFor="provider">Booking Provider</Label>
                <Select value={providerId} onValueChange={setProviderId}>
                  <SelectTrigger id="provider">
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="accountId">Chatwoot Account ID</Label>
                  <Input
                    id="accountId"
                    type="number"
                    value={chatwootAccountId}
                    onChange={(e) => setChatwootAccountId(e.target.value)}
                    placeholder="e.g. 1"
                    required
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="inboxId">Chatwoot Inbox ID</Label>
                  <Input
                    id="inboxId"
                    type="number"
                    value={chatwootInboxId}
                    onChange={(e) => setChatwootInboxId(e.target.value)}
                    placeholder="e.g. 45"
                    required
                  />
                </div>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="baseUrl">Chatwoot Base URL</Label>
                <Input
                  id="baseUrl"
                  type="url"
                  value={chatwootBaseUrl}
                  onChange={(e) => setChatwootBaseUrl(e.target.value)}
                  placeholder="https://app.chatwoot.com"
                  required
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="token" className="flex items-center gap-1.5">
                  <KeyRound className="w-3.5 h-3.5 text-muted-foreground" /> Chatwoot API Token
                </Label>
                <Input
                  id="token"
                  type="password"
                  value={chatwootApiToken}
                  onChange={(e) => setChatwootApiToken(e.target.value)}
                  placeholder="Enter API token or bot access token"
                  required
                />
              </div>

              <div className="flex items-center justify-between border rounded-lg p-3 bg-muted/20">
                <div className="space-y-0.5">
                  <Label className="text-sm font-medium">Enable Integration</Label>
                  <p className="text-[10px] text-muted-foreground">
                    Direct incoming messages to FastAPI assistant workflows.
                  </p>
                </div>
                <Switch
                  checked={isEnabled}
                  onCheckedChange={setIsEnabled}
                />
              </div>

              <DialogFooter className="pt-2">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit">
                  {editingBinding ? "Save Changes" : "Create Binding"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
