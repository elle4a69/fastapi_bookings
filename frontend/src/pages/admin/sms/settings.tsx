import { useState, useEffect } from "react";
import { Plus, Edit2, Trash2, Check, Sparkles, BookOpen } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface KnowledgeEntry {
  id: number;
  category: string;
  text: string;
  source?: string;
  status: string; // proposed, approved, rejected, archived
  provenance: string;
  created_at: string;
  provider_id?: number | null;
  sms_account_id?: number | null;
}

interface PromptProfile {
  id: number;
  name: string;
  system_prompt: string;
  is_active: boolean;
  provider_id?: number | null;
  sms_account_id?: number | null;
}

export default function SmsSettingsTab() {
  const [knowledge, setKnowledge] = useState<KnowledgeEntry[]>([]);
  const [prompts, setPrompts] = useState<PromptProfile[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Dialog & Form states
  const [knowDialogOpen, setKnowDialogOpen] = useState(false);
  const [knowDialogOpenType, setKnowDialogOpenType] = useState<"shared" | "provider">("shared");
  const [editingEntry, setEditingEntry] = useState<KnowledgeEntry | null>(null);
  const [knowCategory, setKnowCategory] = useState("faq");
  const [knowText, setKnowText] = useState("");
  const [knowSource, setKnowSource] = useState("");
  const [knowProviderId, setKnowProviderId] = useState("");

  const [promptDialogOpen, setPromptDialogOpen] = useState(false);
  const [promptDialogOpenType, setPromptDialogOpenType] = useState<"global" | "provider">("global");
  const [editingPrompt, setEditingPrompt] = useState<PromptProfile | null>(null);
  const [promptName, setPromptName] = useState("");
  const [promptText, setPromptText] = useState("");
  const [promptProviderId, setPromptProviderId] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [knowRes, promptRes, provRes] = await Promise.all([
        apiClient.get<KnowledgeEntry[]>("/api/admin/sms/settings/knowledge"),
        apiClient.get<PromptProfile[]>("/api/admin/sms/settings/prompts"),
        apiClient.get<any>("/api/admin/providers")
      ]);
      setKnowledge(knowRes);
      setPrompts(promptRes);
      setProviders(Array.isArray(provRes) ? provRes : (provRes?.data ?? []));
    } catch (err: any) {
      toast.error(err.message || "Failed to load SMS settings.");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreateSharedKnowledge = () => {
    setEditingEntry(null);
    setKnowCategory("faq");
    setKnowText("");
    setKnowSource("");
    setKnowProviderId("");
    setKnowDialogOpenType("shared");
    setKnowDialogOpen(true);
  };

  const handleOpenEditSharedKnowledge = (entry: KnowledgeEntry) => {
    setEditingEntry(entry);
    setKnowCategory(entry.category);
    setKnowText(entry.text);
    setKnowSource(entry.source || "");
    setKnowProviderId("");
    setKnowDialogOpenType("shared");
    setKnowDialogOpen(true);
  };

  const handleOpenCreateProviderKnowledge = () => {
    setEditingEntry(null);
    setKnowCategory("faq");
    setKnowText("");
    setKnowSource("");
    setKnowProviderId(providers[0]?.id ? String(providers[0].id) : "");
    setKnowDialogOpenType("provider");
    setKnowDialogOpen(true);
  };

  const handleOpenEditProviderKnowledge = (entry: KnowledgeEntry) => {
    setEditingEntry(entry);
    setKnowCategory(entry.category);
    setKnowText(entry.text);
    setKnowSource(entry.source || "");
    setKnowProviderId(entry.provider_id ? String(entry.provider_id) : "");
    setKnowDialogOpenType("provider");
    setKnowDialogOpen(true);
  };

  const handleSaveKnowledge = async () => {
    if (!knowText) {
      toast.error("Knowledge text is required.");
      return;
    }
    const payload = {
      category: knowCategory,
      text: knowText,
      source: knowSource,
      provider_id: knowDialogOpenType === "provider" ? (knowProviderId ? Number(knowProviderId) : null) : null
    };

    try {
      if (editingEntry) {
        await apiClient.put(`/api/admin/sms/settings/knowledge/${editingEntry.id}`, payload);
        toast.success("Knowledge entry updated.");
      } else {
        await apiClient.post("/api/admin/sms/settings/knowledge", payload);
        toast.success("Knowledge entry added.");
      }
      setKnowDialogOpen(false);
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to save knowledge entry.");
    }
  };

  const handleApproveKnowledge = async (id: number) => {
    try {
      await apiClient.put(`/api/admin/sms/settings/knowledge/${id}`, { status: "approved" });
      toast.success("Knowledge entry approved.");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to approve entry.");
    }
  };

  const handleDeleteKnowledge = async (id: number) => {
    if (!confirm("Are you sure you want to delete this entry?")) return;
    try {
      await apiClient.delete(`/api/admin/sms/settings/knowledge/${id}`);
      toast.success("Knowledge entry deleted.");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to delete entry.");
    }
  };

  const handleOpenCreateGlobalPrompt = () => {
    setEditingPrompt(null);
    setPromptName("");
    setPromptText("");
    setPromptProviderId("");
    setPromptDialogOpenType("global");
    setPromptDialogOpen(true);
  };

  const handleOpenEditGlobalPrompt = (p: PromptProfile) => {
    setEditingPrompt(p);
    setPromptName(p.name);
    setPromptText(p.system_prompt);
    setPromptProviderId("");
    setPromptDialogOpenType("global");
    setPromptDialogOpen(true);
  };

  const handleOpenCreateProviderPrompt = () => {
    setEditingPrompt(null);
    setPromptName("");
    setPromptText("");
    setPromptProviderId(providers[0]?.id ? String(providers[0].id) : "");
    setPromptDialogOpenType("provider");
    setPromptDialogOpen(true);
  };

  const handleOpenEditProviderPrompt = (p: PromptProfile) => {
    setEditingPrompt(p);
    setPromptName(p.name);
    setPromptText(p.system_prompt);
    setPromptProviderId(p.provider_id ? String(p.provider_id) : "");
    setPromptDialogOpenType("provider");
    setPromptDialogOpen(true);
  };

  const handleSavePrompt = async () => {
    if (!promptName || !promptText) {
      toast.error("Prompt name and system prompt text are required.");
      return;
    }
    const payload = {
      name: promptName,
      system_prompt: promptText,
      provider_id: promptDialogOpenType === "provider" ? (promptProviderId ? Number(promptProviderId) : null) : null
    };

    try {
      if (editingPrompt) {
        await apiClient.put(`/api/admin/sms/settings/prompts/${editingPrompt.id}`, payload);
        toast.success("Prompt profile updated.");
      } else {
        await apiClient.post("/api/admin/sms/settings/prompts", payload);
        toast.success("Prompt profile created.");
      }
      setPromptDialogOpen(false);
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to save prompt profile.");
    }
  };

  const handleSetActivePrompt = async (p: PromptProfile) => {
    try {
      await apiClient.put(`/api/admin/sms/settings/prompts/${p.id}`, { is_active: true });
      toast.success("Prompt profile activated.");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to activate prompt.");
    }
  };

  const handleDeletePrompt = async (id: number) => {
    if (!confirm("Are you sure you want to delete this prompt?")) return;
    try {
      await apiClient.delete(`/api/admin/sms/settings/prompts/${id}`);
      toast.success("Prompt profile deleted.");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to delete prompt.");
    }
  };

  const globalPrompts = prompts.filter(p => p.provider_id === null || p.provider_id === undefined);
  const providerPrompts = prompts.filter(p => p.provider_id !== null && p.provider_id !== undefined);
  const sharedKnowledge = knowledge.filter(k => k.provider_id === null || k.provider_id === undefined);
  const providerKnowledge = knowledge.filter(k => k.provider_id !== null && k.provider_id !== undefined);

  return (
    <div className="space-y-4">
      <Tabs defaultValue="global_prompts" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="global_prompts" className="text-xs">
            <Sparkles className="w-3.5 h-3.5 mr-2" /> Global System Prompt
          </TabsTrigger>
          <TabsTrigger value="provider_prompts" className="text-xs">
            <Sparkles className="w-3.5 h-3.5 mr-2" /> Provider Instructions
          </TabsTrigger>
          <TabsTrigger value="shared_knowledge" className="text-xs">
            <BookOpen className="w-3.5 h-3.5 mr-2" /> Shared Knowledge
          </TabsTrigger>
          <TabsTrigger value="provider_knowledge" className="text-xs">
            <BookOpen className="w-3.5 h-3.5 mr-2" /> Provider Knowledge
          </TabsTrigger>
        </TabsList>

        {/* Global Prompts Content */}
        <TabsContent value="global_prompts" className="space-y-4 pt-3">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-base font-bold tracking-tight">Global System Prompts</h3>
              <p className="text-muted-foreground text-xs">Tenant-wide safety instructions and safety rules for SMS bots.</p>
            </div>
            <Button size="sm" onClick={handleOpenCreateGlobalPrompt}>
              <Plus className="w-4 h-4 mr-2" /> Add Global Prompt
            </Button>
          </div>

          <Card>
            <CardContent className="p-0">
              {loading ? (
                <div className="p-8 text-center text-muted-foreground text-sm">Loading prompts...</div>
              ) : globalPrompts.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground text-sm">No Global System Prompts defined.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Profile Name</TableHead>
                      <TableHead>System Prompt Preview</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {globalPrompts.map((p) => (
                      <TableRow key={p.id}>
                        <TableCell className="font-semibold">{p.name}</TableCell>
                        <TableCell className="max-w-md truncate text-xs text-muted-foreground font-mono">{p.system_prompt}</TableCell>
                        <TableCell>
                          {p.is_active ? (
                            <Badge className="bg-blue-500/10 text-blue-600 border-blue-500/20">Active</Badge>
                          ) : (
                            <Badge variant="secondary">Inactive</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right space-x-1">
                          {!p.is_active && (
                            <Button variant="ghost" size="icon" className="text-emerald-500" onClick={() => handleSetActivePrompt(p)} title="Set Active">
                              <Check className="w-3.5 h-3.5" />
                            </Button>
                          )}
                          <Button variant="ghost" size="icon" onClick={() => handleOpenEditGlobalPrompt(p)}>
                            <Edit2 className="w-3.5 h-3.5" />
                          </Button>
                          <Button variant="ghost" size="icon" className="text-red-500" onClick={() => handleDeletePrompt(p.id)}>
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
        </TabsContent>

        {/* Provider Prompts Content */}
        <TabsContent value="provider_prompts" className="space-y-4 pt-3">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-base font-bold tracking-tight">Provider Instructions</h3>
              <p className="text-muted-foreground text-xs">AI instructions and persona overrides tailored to specific providers.</p>
            </div>
            <Button size="sm" onClick={handleOpenCreateProviderPrompt}>
              <Plus className="w-4 h-4 mr-2" /> Add Provider Instructions
            </Button>
          </div>

          <Card>
            <CardContent className="p-0">
              {loading ? (
                <div className="p-8 text-center text-muted-foreground text-sm">Loading prompts...</div>
              ) : providerPrompts.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground text-sm">No Provider Instructions defined.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Profile Name</TableHead>
                      <TableHead>Provider</TableHead>
                      <TableHead>System Prompt Preview</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {providerPrompts.map((p) => {
                      const providerName = providers.find(prov => prov.id === p.provider_id)?.name || `Provider #${p.provider_id}`;
                      return (
                        <TableRow key={p.id}>
                          <TableCell className="font-semibold">{p.name}</TableCell>
                          <TableCell className="font-medium text-blue-600">{providerName}</TableCell>
                          <TableCell className="max-w-md truncate text-xs text-muted-foreground font-mono">{p.system_prompt}</TableCell>
                          <TableCell>
                            {p.is_active ? (
                              <Badge className="bg-blue-500/10 text-blue-600 border-blue-500/20">Active</Badge>
                            ) : (
                              <Badge variant="secondary">Inactive</Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-right space-x-1">
                            {!p.is_active && (
                              <Button variant="ghost" size="icon" className="text-emerald-500" onClick={() => handleSetActivePrompt(p)} title="Set Active">
                                <Check className="w-3.5 h-3.5" />
                              </Button>
                            )}
                            <Button variant="ghost" size="icon" onClick={() => handleOpenEditProviderPrompt(p)}>
                              <Edit2 className="w-3.5 h-3.5" />
                            </Button>
                            <Button variant="ghost" size="icon" className="text-red-500" onClick={() => handleDeletePrompt(p.id)}>
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Shared Knowledge Content */}
        <TabsContent value="shared_knowledge" className="space-y-4 pt-3">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-base font-bold tracking-tight">Shared Knowledge Base</h3>
              <p className="text-muted-foreground text-xs">Global knowledge facts injected into RAG contexts for all providers.</p>
            </div>
            <Button size="sm" onClick={handleOpenCreateSharedKnowledge}>
              <Plus className="w-4 h-4 mr-2" /> Add Shared Fact
            </Button>
          </div>

          <Card>
            <CardContent className="p-0">
              {loading ? (
                <div className="p-8 text-center text-muted-foreground text-sm">Loading knowledge entries...</div>
              ) : sharedKnowledge.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground text-sm">No shared facts stored.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Category</TableHead>
                      <TableHead>Fact Content</TableHead>
                      <TableHead>Source</TableHead>
                      <TableHead>Origin</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sharedKnowledge.map((entry) => (
                      <TableRow key={entry.id}>
                        <TableCell>
                          <Badge variant="outline" className="capitalize">{entry.category}</Badge>
                        </TableCell>
                        <TableCell className="max-w-md truncate text-xs font-mono">{entry.text}</TableCell>
                        <TableCell className="text-xs">{entry.source || "Manual Entry"}</TableCell>
                        <TableCell className="capitalize text-xs text-muted-foreground">{entry.provenance}</TableCell>
                        <TableCell>
                          {entry.status === "approved" ? (
                            <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20">Approved</Badge>
                          ) : entry.status === "proposed" ? (
                            <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/20">Proposed</Badge>
                          ) : (
                            <Badge variant="secondary">{entry.status}</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right space-x-1">
                          {entry.status === "proposed" && (
                            <Button variant="ghost" size="icon" className="text-emerald-500" onClick={() => handleApproveKnowledge(entry.id)}>
                              <Check className="w-3.5 h-3.5" />
                            </Button>
                          )}
                          <Button variant="ghost" size="icon" onClick={() => handleOpenEditSharedKnowledge(entry)}>
                            <Edit2 className="w-3.5 h-3.5" />
                          </Button>
                          <Button variant="ghost" size="icon" className="text-red-500" onClick={() => handleDeleteKnowledge(entry.id)}>
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
        </TabsContent>

        {/* Provider Knowledge Content */}
        <TabsContent value="provider_knowledge" className="space-y-4 pt-3">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-base font-bold tracking-tight">Provider Knowledge Base</h3>
              <p className="text-muted-foreground text-xs">Knowledge facts enjected into RAG contexts for specific providers.</p>
            </div>
            <Button size="sm" onClick={handleOpenCreateProviderKnowledge}>
              <Plus className="w-4 h-4 mr-2" /> Add Provider Fact
            </Button>
          </div>

          <Card>
            <CardContent className="p-0">
              {loading ? (
                <div className="p-8 text-center text-muted-foreground text-sm">Loading knowledge entries...</div>
              ) : providerKnowledge.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground text-sm">No provider-specific facts stored.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Category</TableHead>
                      <TableHead>Provider</TableHead>
                      <TableHead>Fact Content</TableHead>
                      <TableHead>Source</TableHead>
                      <TableHead>Origin</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {providerKnowledge.map((entry) => {
                      const providerName = providers.find(prov => prov.id === entry.provider_id)?.name || `Provider #${entry.provider_id}`;
                      return (
                        <TableRow key={entry.id}>
                          <TableCell>
                            <Badge variant="outline" className="capitalize">{entry.category}</Badge>
                          </TableCell>
                          <TableCell className="font-medium text-blue-600">{providerName}</TableCell>
                          <TableCell className="max-w-md truncate text-xs font-mono">{entry.text}</TableCell>
                          <TableCell className="text-xs">{entry.source || "Manual Entry"}</TableCell>
                          <TableCell className="capitalize text-xs text-muted-foreground">{entry.provenance}</TableCell>
                          <TableCell>
                            {entry.status === "approved" ? (
                              <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20">Approved</Badge>
                            ) : entry.status === "proposed" ? (
                              <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/20">Proposed</Badge>
                            ) : (
                              <Badge variant="secondary">{entry.status}</Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-right space-x-1">
                            {entry.status === "proposed" && (
                              <Button variant="ghost" size="icon" className="text-emerald-500" onClick={() => handleApproveKnowledge(entry.id)}>
                                <Check className="w-3.5 h-3.5" />
                              </Button>
                            )}
                            <Button variant="ghost" size="icon" onClick={() => handleOpenEditProviderKnowledge(entry)}>
                              <Edit2 className="w-3.5 h-3.5" />
                            </Button>
                            <Button variant="ghost" size="icon" className="text-red-500" onClick={() => handleDeleteKnowledge(entry.id)}>
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Knowledge Form Dialog */}
      <Dialog open={knowDialogOpen} onOpenChange={setKnowDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editingEntry ? "Edit Fact" : `Add ${knowDialogOpenType === "provider" ? "Provider" : "Shared"} Fact`}
            </DialogTitle>
            <DialogDescription>Knowledge base facts inform AI responses.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-2 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Category</Label>
                <Select value={knowCategory} onValueChange={setKnowCategory}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="service">Service details</SelectItem>
                    <SelectItem value="policy">Policy rules</SelectItem>
                    <SelectItem value="location">Locations info</SelectItem>
                    <SelectItem value="faq">General FAQ</SelectItem>
                    <SelectItem value="tone">Tone of voice</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {knowDialogOpenType === "provider" && (
                <div className="space-y-1">
                  <Label>Provider Scope *</Label>
                  <Select value={knowProviderId} onValueChange={setKnowProviderId}>
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
              )}
            </div>

            <div className="space-y-1">
              <Label>Source reference</Label>
              <Input placeholder="E.g., Tori bio page" value={knowSource} onChange={e => setKnowSource(e.target.value)} />
            </div>

            <div className="space-y-1">
              <Label>Fact Content *</Label>
              <Textarea placeholder="Explain the fact in clear, simple wording..." value={knowText} onChange={e => setKnowText(e.target.value)} className="min-h-[120px]" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setKnowDialogOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleSaveKnowledge}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Prompt Form Dialog */}
      <Dialog open={promptDialogOpen} onOpenChange={setPromptDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editingPrompt ? "Edit Prompt Profile" : `Create ${promptDialogOpenType === "provider" ? "Provider Instructions" : "Global System Prompt"}`}
            </DialogTitle>
            <DialogDescription>Define system directives for SMS bots.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 my-2 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Profile Name *</Label>
                <Input placeholder="E.g., Tori Primary Safety Persona" value={promptName} onChange={e => setPromptName(e.target.value)} />
              </div>

              {promptDialogOpenType === "provider" && (
                <div className="space-y-1">
                  <Label>Provider Scope *</Label>
                  <Select value={promptProviderId} onValueChange={setPromptProviderId}>
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
              )}
            </div>

            <div className="space-y-1">
              <Label>System Prompt *</Label>
              <Textarea placeholder="You are an assistant. Always remain helpful..." value={promptText} onChange={e => setPromptText(e.target.value)} className="min-h-[220px] font-mono text-[11px]" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setPromptDialogOpen(false)}>Cancel</Button>
            <Button size="sm" onClick={handleSavePrompt}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
