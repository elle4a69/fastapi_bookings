import { useState, useEffect } from "react";
import { Plus, Edit2, Trash2, Check, Sparkles, BookOpen, X, RefreshCw, Brain, Wand2 } from "lucide-react";
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

interface KnowledgeProposal {
  id: number;
  proposal_type: string; // 'gap' | 'duplicate' | 'conflict' | 'add' | 'stale' | 'supersede' | 'quarantine' | string
  status: string; // 'pending' | 'accepted' | 'dismissed' | 'resolved'
  category?: string;
  user_query?: string | null;
  proposed_response?: string | null;
  text?: string | null;
  question?: string | null;
  reason_code?: string;
  confidence_score?: number;
  evidence_count?: number;
  target_memory_id?: number | null;
  provider_id?: number | null;
  created_at?: string;
}

export interface CuratorStatus {
  active_memories: number;
  superseded_memories: number;
  quarantined_memories?: number;
  pending_proposals: number;
  processed_learning_events: number;
  pending_learning_events?: number;
  behavioural_principles?: number;
  durable_facts?: number;
  scope_breakdown?: {
    tenant_wide: number;
    provider_specific: number;
  };
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

  // Knowledge Curator Proposals state
  const [proposals, setProposals] = useState<KnowledgeProposal[]>([]);
  const [loadingProposals, setLoadingProposals] = useState(false);
  const [resolvingProposalId, setResolvingProposalId] = useState<number | null>(null);

  // Autonomous Curator Status & Action state
  const [curatorStatus, setCuratorStatus] = useState<CuratorStatus | null>(null);
  const [loadingCuratorStatus, setLoadingCuratorStatus] = useState(false);
  const [isCurating, setIsCurating] = useState(false);

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

  const loadCuratorStatus = async () => {
    setLoadingCuratorStatus(true);
    try {
      const res = await apiClient.get<any>("/api/admin/sms/curator/status");
      const statusData = res?.data || res;
      if (statusData && typeof statusData === "object") {
        setCuratorStatus(statusData);
      }
    } catch {
      // Gracefully handle if curator status endpoint is offline
      setCuratorStatus({
        active_memories: 0,
        superseded_memories: 0,
        pending_proposals: 0,
        processed_learning_events: 0,
      });
    } finally {
      setLoadingCuratorStatus(false);
    }
  };

  const handleRunAutonomousCuration = async () => {
    setIsCurating(true);
    try {
      const res = await apiClient.post<any>("/api/admin/sms/curator/process", { limit: 50 });
      const processed = res?.processed ?? 0;
      const curated = res?.curated ?? 0;
      const superseded = res?.superseded ?? 0;
      toast.success(
        `Processed ${processed} learning event${processed === 1 ? "" : "s"}, curated ${curated} memor${curated === 1 ? "y" : "ies"}${superseded > 0 ? `, superseded ${superseded}` : ""}.`
      );
      await Promise.all([loadCuratorStatus(), loadProposals(), loadData()]);
    } catch (err: any) {
      toast.error(err?.message || "Autonomous curation run failed.");
    } finally {
      setIsCurating(false);
    }
  };

  const loadProposals = async () => {
    setLoadingProposals(true);
    try {
      const res = await apiClient.get<KnowledgeProposal[]>("/api/admin/sms/knowledge/proposals");
      const rawList = Array.isArray(res) ? res : ((res as any)?.items || (res as any)?.data || []);
      const pending = rawList.filter((p: KnowledgeProposal) => !p.status || p.status === "pending");
      setProposals(pending);
    } catch {
      // Gracefully handle if proposals endpoint is empty, offline, or returns error
      setProposals([]);
    } finally {
      setLoadingProposals(false);
    }
  };

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
    loadProposals();
    loadCuratorStatus();
  };

  const handleResolveProposal = async (id: number, action: "approve" | "dismiss") => {
    setResolvingProposalId(id);
    try {
      await apiClient.post(`/api/admin/sms/knowledge/proposals/${id}/resolve`, { action });
      toast.success(`Proposal ${action === "approve" ? "approved" : "dismissed"}.`);
      setProposals(prev => prev.filter(p => p.id !== id));
      if (action === "approve") {
        apiClient.get<KnowledgeEntry[]>("/api/admin/sms/settings/knowledge")
          .then(res => setKnowledge(res))
          .catch(() => {});
      }
    } catch (err: any) {
      toast.error(err.message || `Failed to ${action} proposal.`);
    } finally {
      setResolvingProposalId(null);
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

  const getProposalTypeBadge = (type: string) => {
    switch (type.toLowerCase()) {
      case "gap":
        return <Badge className="bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20 capitalize font-mono text-[10px]">gap</Badge>;
      case "conflict":
        return <Badge className="bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20 capitalize font-mono text-[10px]">conflict</Badge>;
      case "duplicate":
        return <Badge className="bg-slate-500/10 text-slate-700 dark:text-slate-300 border-slate-500/20 capitalize font-mono text-[10px]">duplicate</Badge>;
      case "add":
        return <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20 capitalize font-mono text-[10px]">add</Badge>;
      case "stale":
        return <Badge className="bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20 capitalize font-mono text-[10px]">stale</Badge>;
      default:
        return <Badge variant="outline" className="capitalize font-mono text-[10px]">{type}</Badge>;
    }
  };

  return (
    <div className="space-y-4">
      <Tabs defaultValue="global_prompts" className="w-full">
        <TabsList className="flex w-full overflow-x-auto no-scrollbar gap-1 p-1 bg-muted/40 rounded-lg h-auto sm:grid sm:grid-cols-5">
          <TabsTrigger value="global_prompts" className="text-xs whitespace-nowrap shrink-0">
            <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Global Prompt
          </TabsTrigger>
          <TabsTrigger value="provider_prompts" className="text-xs whitespace-nowrap shrink-0">
            <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Provider Instructions
          </TabsTrigger>
          <TabsTrigger value="shared_knowledge" className="text-xs whitespace-nowrap shrink-0">
            <BookOpen className="w-3.5 h-3.5 mr-1.5" /> Shared Knowledge
          </TabsTrigger>
          <TabsTrigger value="provider_knowledge" className="text-xs whitespace-nowrap shrink-0">
            <BookOpen className="w-3.5 h-3.5 mr-1.5" /> Provider Knowledge
          </TabsTrigger>
          <TabsTrigger value="curator_proposals" className="text-xs whitespace-nowrap shrink-0">
            <Sparkles className="w-3.5 h-3.5 mr-1.5 text-amber-500" /> Curator Proposals
            {proposals.length > 0 && (
              <Badge variant="secondary" className="ml-1.5 px-1 py-0 text-[10px] bg-amber-500/20 text-amber-700 dark:text-amber-300 font-semibold">
                {proposals.length}
              </Badge>
            )}
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
            <CardContent className="p-0 overflow-x-auto">
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
            <CardContent className="p-0 overflow-x-auto">
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

          {proposals.length > 0 && (
            <div className="flex items-center justify-between p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200 text-xs">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-600 shrink-0" />
                <span>
                  <strong>{proposals.length} pending Knowledge Curator Proposal{proposals.length === 1 ? "" : "s"}</strong> require operator review in the Curator Proposals tab.
                </span>
              </div>
            </div>
          )}

          <Card>
            <CardContent className="p-0 overflow-x-auto">
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
            <CardContent className="p-0 overflow-x-auto">
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
        {/* Knowledge Curator Proposals Content */}
        <TabsContent value="curator_proposals" className="space-y-4 pt-3">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-base font-bold tracking-tight">Knowledge Curator Proposals</h3>
              <p className="text-muted-foreground text-xs">
                Governed memory proposals extracted by AI curator. Review pending facts, gaps, and conflicts before promoting to active knowledge.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                loadProposals();
                loadCuratorStatus();
              }}
              disabled={loadingProposals || loadingCuratorStatus}
              className="h-8 text-xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loadingProposals || loadingCuratorStatus ? "animate-spin" : ""}`} />
              Refresh Proposals
            </Button>
          </div>

          {/* Curator Engine Status Card (Master Spec 21, 42) */}
          <Card className="border border-indigo-200 dark:border-indigo-900/60 bg-gradient-to-r from-indigo-50/40 via-white to-indigo-50/20 dark:from-indigo-950/20 dark:via-slate-900 dark:to-indigo-950/10 shadow-xs">
            <CardContent className="p-3 sm:p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-indigo-100 dark:border-indigo-900/40 pb-2.5">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-indigo-600 text-white shadow-xs">
                    <Brain className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs sm:text-sm font-bold tracking-tight text-foreground">
                        Curator Engine
                      </h4>
                      <Badge variant="outline" className="text-[10px] bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/30">
                        Autonomous Governance
                      </Badge>
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      Continuous memory lifecycle management across active facts, superseded memories, and learning events.
                    </p>
                  </div>
                </div>

                <Button
                  type="button"
                  size="sm"
                  disabled={isCurating}
                  onClick={handleRunAutonomousCuration}
                  className="h-8 text-xs gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold shadow-xs transition-all cursor-pointer"
                  title="Trigger autonomous evaluation across pending learning events"
                >
                  {isCurating ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Processing...</span>
                    </>
                  ) : (
                    <>
                      <Wand2 className="w-3.5 h-3.5" />
                      <span>Run Autonomous Curation</span>
                    </>
                  )}
                </Button>
              </div>

              {/* 4 Metrics Tiles */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
                  <span className="text-[10px] font-semibold text-muted-foreground block uppercase tracking-wider">
                    Active Memories
                  </span>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <span className="text-lg font-bold font-mono text-emerald-600 dark:text-emerald-400">
                      {curatorStatus?.active_memories ?? (knowledge.filter((k) => k.status === "approved").length || 0)}
                    </span>
                    <span className="text-[10px] text-muted-foreground">facts</span>
                  </div>
                </div>

                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
                  <span className="text-[10px] font-semibold text-muted-foreground block uppercase tracking-wider">
                    Superseded
                  </span>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <span className="text-lg font-bold font-mono text-slate-700 dark:text-slate-300">
                      {curatorStatus?.superseded_memories ?? 0}
                    </span>
                    <span className="text-[10px] text-muted-foreground">archived</span>
                  </div>
                </div>

                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
                  <span className="text-[10px] font-semibold text-muted-foreground block uppercase tracking-wider">
                    Pending Proposals
                  </span>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <span className="text-lg font-bold font-mono text-amber-600 dark:text-amber-400">
                      {curatorStatus?.pending_proposals ?? proposals.length}
                    </span>
                    <span className="text-[10px] text-muted-foreground">in review</span>
                  </div>
                </div>

                <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-2xs">
                  <span className="text-[10px] font-semibold text-muted-foreground block uppercase tracking-wider">
                    Processed Events
                  </span>
                  <div className="flex items-baseline gap-1.5 mt-0.5">
                    <span className="text-lg font-bold font-mono text-blue-600 dark:text-blue-400">
                      {curatorStatus?.processed_learning_events ?? 0}
                    </span>
                    <span className="text-[10px] text-muted-foreground">events</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-0 overflow-x-auto">
              {loadingProposals ? (
                <div className="p-8 text-center text-muted-foreground text-sm flex items-center justify-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-primary" />
                  Loading curator proposals...
                </div>
              ) : proposals.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground text-sm space-y-1">
                  <p className="font-medium text-foreground">No pending curator proposals.</p>
                  <p className="text-xs">All candidate knowledge entries have been reviewed and resolved.</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead className="min-w-[280px]">Proposed Fact / Query</TableHead>
                      <TableHead>Reason / Confidence</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {proposals.map((p) => {
                      const displayQuery = p.user_query || p.question;
                      const displayContent = p.proposed_response || p.text;
                      const isResolving = resolvingProposalId === p.id;

                      return (
                        <TableRow key={p.id}>
                          <TableCell>
                            {getProposalTypeBadge(p.proposal_type)}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className="capitalize text-[10px]">
                              {p.category || "faq"}
                            </Badge>
                          </TableCell>
                          <TableCell className="space-y-1 py-3">
                            {displayQuery && (
                              <div className="text-xs">
                                <span className="font-semibold text-muted-foreground">Inquiry: </span>
                                <span className="font-medium text-foreground">{displayQuery}</span>
                              </div>
                            )}
                            {displayContent ? (
                              <div className="text-xs text-muted-foreground font-mono bg-muted/40 p-2 rounded border border-border/40 max-w-xl whitespace-pre-wrap">
                                {displayContent}
                              </div>
                            ) : (
                              <div className="text-xs text-muted-foreground italic">
                                Proposal #{p.id} ({p.proposal_type})
                              </div>
                            )}
                          </TableCell>
                          <TableCell>
                            <div className="space-y-0.5 text-xs">
                              {p.reason_code && (
                                <div className="font-mono text-[10px] text-muted-foreground">
                                  {p.reason_code}
                                </div>
                              )}
                              {typeof p.confidence_score === "number" && (
                                <div className="text-[10px] text-muted-foreground">
                                  Confidence: <span className="font-semibold">{(p.confidence_score * 100).toFixed(0)}%</span>
                                </div>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-right space-x-1.5 whitespace-nowrap">
                            <Button
                              size="xs"
                              variant="default"
                              className="bg-emerald-600 hover:bg-emerald-700 text-white h-7 text-xs px-2.5 gap-1"
                              disabled={isResolving}
                              onClick={() => handleResolveProposal(p.id, "approve")}
                              title="Approve this proposal into durable knowledge"
                            >
                              <Check className="w-3.5 h-3.5" /> Approve
                            </Button>
                            <Button
                              size="xs"
                              variant="outline"
                              className="text-muted-foreground hover:text-foreground h-7 text-xs px-2.5 gap-1"
                              disabled={isResolving}
                              onClick={() => handleResolveProposal(p.id, "dismiss")}
                              title="Dismiss this proposal"
                            >
                              <X className="w-3.5 h-3.5" /> Dismiss
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
