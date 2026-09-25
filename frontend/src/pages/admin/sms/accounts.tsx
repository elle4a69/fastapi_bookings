import { useState, useEffect } from "react";
import { Plus, Edit2, Trash2, ShieldAlert, KeyRound } from "lucide-react";
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
import { Separator } from "@/components/ui/separator";

interface SmsAccount {
  id: number;
  public_id: string;
  provider_id: number;
  display_name: string;
  transport_type: string;
  sender_address: string;
  is_enabled: boolean;
  autoresponder_enabled: boolean;
  autoresponder_text?: string;
  ai_enabled: boolean;
  ai_mode: string;
  line_prompt?: string;
  catchup_cutoff_days: number;
  has_credentials: boolean;
}

export default function SmsAccountsTab() {
  const [accounts, setAccounts] = useState<SmsAccount[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<SmsAccount | null>(null);

  // Form states
  const [displayName, setDisplayName] = useState("");
  const [providerId, setProviderId] = useState("");
  const [transportType, setTransportType] = useState("simulator");
  const [senderAddress, setSenderAddress] = useState("");
  const [isEnabled, setIsEnabled] = useState(true);
  const [autoresponderEnabled, setAutoresponderEnabled] = useState(false);
  const [autoresponderText, setAutoresponderText] = useState("");
  const [aiEnabled, setAiEnabled] = useState(false);
  const [aiMode, setAiMode] = useState("off");
  const [linePrompt, setLinePrompt] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [accRes, provRes] = await Promise.all([
        apiClient.get<SmsAccount[]>("/api/admin/sms/accounts"),
        apiClient.get<any>("/api/admin/providers")
      ]);
      setAccounts(accRes);
      setProviders(Array.isArray(provRes) ? provRes : (provRes?.data ?? []));
    } catch (err: any) {
      toast.error(err.message || "Failed to load SMS accounts.");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreate = () => {
    setEditingAccount(null);
    setDisplayName("");
    setProviderId(providers[0]?.id ? String(providers[0].id) : "");
    setTransportType("simulator");
    setSenderAddress("");
    setIsEnabled(true);
    setAutoresponderEnabled(false);
    setAutoresponderText("");
    setAiEnabled(false);
    setAiMode("off");
    setLinePrompt("");
    setUsername("");
    setPassword("");
    setWebhookSecret("");
    setDialogOpen(true);
  };

  const handleOpenEdit = (acc: SmsAccount) => {
    setEditingAccount(acc);
    setDisplayName(acc.display_name);
    // Find provider associated with account or default
    setProviderId(String(acc.provider_id || providers[0]?.id || ""));
    setTransportType(acc.transport_type);
    setSenderAddress(acc.sender_address);
    setIsEnabled(acc.is_enabled);
    setAutoresponderEnabled(acc.autoresponder_enabled);
    setAutoresponderText(acc.autoresponder_text || "");
    setAiEnabled(acc.ai_enabled);
    setAiMode(acc.ai_mode);
    setLinePrompt(acc.line_prompt || "");
    setUsername("");
    setPassword("");
    setWebhookSecret("");
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!displayName || !senderAddress) {
      toast.error("Please fill in all required fields.");
      return;
    }

    const credentials: any = {};
    if (username) credentials.username = username;
    if (password) credentials.password = password;
    if (webhookSecret) credentials.webhook_secret = webhookSecret;

    const payload = {
      display_name: displayName,
      provider_id: Number(providerId),
      transport_type: transportType,
      sender_address: senderAddress,
      is_enabled: isEnabled,
      autoresponder_enabled: autoresponderEnabled,
      autoresponder_text: autoresponderText,
      ai_enabled: aiEnabled,
      ai_mode: aiMode,
      line_prompt: linePrompt,
      credentials: Object.keys(credentials).length > 0 ? credentials : undefined
    };

    try {
      if (editingAccount) {
        await apiClient.put(`/api/admin/sms/accounts/${editingAccount.id}`, payload);
        toast.success("SMS Account updated successfully.");
      } else {
        await apiClient.post("/api/admin/sms/accounts", payload);
        toast.success("SMS Account created successfully.");
      }
      setDialogOpen(false);
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to save SMS Account.");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this SMS account? This deletes all associated threads.")) return;
    try {
      await apiClient.delete(`/api/admin/sms/accounts/${id}`);
      toast.success("SMS Account deleted.");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to delete SMS account.");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold tracking-tight">SMS Accounts / Lines</h2>
          <p className="text-muted-foreground text-xs">Configure phone lines and assign transport adapters (Simulator, MobileMessage).</p>
        </div>
        <Button size="sm" onClick={handleOpenCreate}>
          <Plus className="w-4 h-4 mr-2" /> Add SMS Line
        </Button>
      </div>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          {loading ? (
            <div className="p-8 text-center text-muted-foreground text-sm">Loading SMS lines...</div>
          ) : accounts.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm">No SMS accounts configured. Click "Add SMS Line" to begin.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Line Name</TableHead>
                  <TableHead>Phone / Address</TableHead>
                  <TableHead>Adapter</TableHead>
                  <TableHead>Autoresponder</TableHead>
                  <TableHead>AI Status</TableHead>
                  <TableHead>Credentials</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.map((acc) => (
                  <TableRow key={acc.id}>
                    <TableCell className="font-semibold">{acc.display_name}</TableCell>
                    <TableCell className="font-mono text-xs">{acc.sender_address}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize">
                        {acc.transport_type}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {acc.autoresponder_enabled ? (
                        <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20">Enabled</Badge>
                      ) : (
                        <Badge variant="secondary">Disabled</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {acc.ai_enabled ? (
                        <Badge className="bg-indigo-500/10 text-indigo-600 border-indigo-500/20 capitalize">{acc.ai_mode}</Badge>
                      ) : (
                        <Badge variant="secondary">Off</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {acc.has_credentials ? (
                        <span className="flex items-center text-xs text-muted-foreground"><KeyRound className="w-3.5 h-3.5 text-emerald-500 mr-1" /> Set</span>
                      ) : (
                        <span className="flex items-center text-xs text-amber-600"><ShieldAlert className="w-3.5 h-3.5 mr-1" /> Not Configured</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {acc.is_enabled ? (
                        <Badge className="bg-blue-500/10 text-blue-600 border-blue-500/20">Active</Badge>
                      ) : (
                        <Badge className="bg-red-500/10 text-red-600 border-red-500/20">Disabled</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right space-x-1">
                      <Button variant="ghost" size="icon" onClick={() => handleOpenEdit(acc)}>
                        <Edit2 className="w-3.5 h-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" className="text-red-500 hover:text-red-600" onClick={() => handleDelete(acc.id)}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editingAccount ? "Edit SMS Line" : "Add SMS Line"}</DialogTitle>
            <DialogDescription>Configure account connections, autoresponders, and AI rules.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-2 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Display Name *</Label>
                <Input placeholder="Tori Primary" value={displayName} onChange={e => setDisplayName(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Sender E.164 Address *</Label>
                <Input placeholder="61412345678" value={senderAddress} onChange={e => setSenderAddress(e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Provider Scope</Label>
                <Select value={providerId} onValueChange={setProviderId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select Provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers.map(p => (
                      <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label>Transport Adapter</Label>
                <Select value={transportType} onValueChange={setTransportType}>
                  <SelectTrigger>
                    <SelectValue placeholder="Simulator" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="simulator">Simulator (Fake)</SelectItem>
                    <SelectItem value="mobilemessage">MobileMessage (Live AU)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Card className="p-3 border space-y-3">
              <h4 className="font-semibold text-sm">Transport Credentials</h4>
              <p className="text-muted-foreground text-[10px] leading-tight">Secure values stored at rest. Enter new credentials only to replace current settings.</p>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Username / API Key</Label>
                  <Input placeholder="username" value={username} onChange={e => setUsername(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>Password / Secret</Label>
                  <Input type="password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} />
                </div>
              </div>
              <div className="space-y-1">
                <Label>Webhook Auth Token / Secret</Label>
                <Input placeholder="shared-secret" value={webhookSecret} onChange={e => setWebhookSecret(e.target.value)} />
              </div>
            </Card>

            <div className="flex items-center justify-between">
              <div className="flex flex-col gap-0.5">
                <Label>Line Enabled</Label>
                <span className="text-muted-foreground text-[10px]">Deactivate line to reject all calls</span>
              </div>
              <Switch checked={isEnabled} onCheckedChange={setIsEnabled} />
            </div>

            <Separator />

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex flex-col gap-0.5">
                  <Label>Fixed Autoresponder</Label>
                  <span className="text-muted-foreground text-[10px]">Deterministic reply for first contact</span>
                </div>
                <Switch checked={autoresponderEnabled} onCheckedChange={setAutoresponderEnabled} />
              </div>
              {autoresponderEnabled && (
                <div className="space-y-1">
                  <Label>Autoresponder Text</Label>
                  <Input placeholder="Hi {name}, thanks for contacting us! We'll reply soon." value={autoresponderText} onChange={e => setAutoresponderText(e.target.value)} />
                </div>
              )}
            </div>

            <Separator />

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex flex-col gap-0.5">
                  <Label>Conversational AI</Label>
                  <span className="text-muted-foreground text-[10px]">Enable AI agent processing</span>
                </div>
                <Switch checked={aiEnabled} onCheckedChange={setAiEnabled} />
              </div>
              {aiEnabled && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>AI Mode</Label>
                    <Select value={aiMode} onValueChange={setAiMode}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="draft">Draft/Review (Manual Send)</SelectItem>
                        <SelectItem value="autopilot">Autopilot (Direct Send)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label>Line Prompt Profile</Label>
                    <Input placeholder="E.g. Tori Persona" value={linePrompt} onChange={e => setLinePrompt(e.target.value)} />
                  </div>
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleSave}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
