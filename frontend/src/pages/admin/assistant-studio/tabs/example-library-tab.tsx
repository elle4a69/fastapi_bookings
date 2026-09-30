import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Sparkles,
  Search,
  Plus,
  ToggleLeft,
  ToggleRight,
  Hash,
  Trash2,
  BookOpen,
  RefreshCw,
  Lock,
  Edit2,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import type { MessageStyleExampleItem, ProviderItem } from '../types';

interface ExampleLibraryTabProps {
  selectedProvider: ProviderItem | null;
}

export const ExampleLibraryTab: React.FC<ExampleLibraryTabProps> = ({ selectedProvider }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedIntent, setSelectedIntent] = useState<string>('all');
  const [examples, setExamples] = useState<MessageStyleExampleItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Dialog State for adding a new example
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newIntent, setNewIntent] = useState('');
  const [newClientMsg, setNewClientMsg] = useState('');
  const [newAssistantReply, setNewAssistantReply] = useState('');
  const [newCategory, setNewCategory] = useState('procedural');
  const [isSaving, setIsSaving] = useState(false);

  // Dialog State for editing an existing tenant-owned example
  const [editingExample, setEditingExample] = useState<MessageStyleExampleItem | null>(null);
  const [editIntent, setEditIntent] = useState('');
  const [editClientMsg, setEditClientMsg] = useState('');
  const [editAssistantReply, setEditAssistantReply] = useState('');
  const [editCategory, setEditCategory] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);

  const loadExamples = () => {
    setIsLoading(true);
    const params = selectedProvider?.id ? `?provider_id=${selectedProvider.id}` : '';
    apiClient
      .get<MessageStyleExampleItem[]>(`/api/admin/assistant-studio/examples${params}`)
      .then((data) => {
        if (Array.isArray(data)) {
          setExamples(data);
        }
      })
      .catch((err) => {
        console.error('Failed to load style examples:', err);
        toast.error('Failed to load style examples');
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    loadExamples();
  }, [selectedProvider?.id]);

  const handleToggleActive = async (id: number, currentActive: boolean) => {
    try {
      await apiClient.put(`/api/admin/assistant-studio/examples/${id}`, {
        is_active: !currentActive,
      });
      setExamples((prev) =>
        prev.map((ex) => (ex.id === id ? { ...ex, is_active: !currentActive } : ex))
      );
      toast.success(`Example #${id} ${!currentActive ? 'activated' : 'paused'}.`);
    } catch (err: any) {
      console.error('Failed to toggle example:', err);
      toast.error(err?.message || 'Failed to update example status');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await apiClient.delete(`/api/admin/assistant-studio/examples/${id}`);
      setExamples((prev) => prev.filter((ex) => ex.id !== id));
      toast.success(`Example #${id} deleted.`);
    } catch (err: any) {
      console.error('Failed to delete example:', err);
      toast.error(err?.message || 'Failed to delete example');
    }
  };

  const handleCreateExample = async () => {
    if (!newIntent.trim() || !newClientMsg.trim() || !newAssistantReply.trim()) {
      toast.error('Please fill in intent, client query, and assistant reply.');
      return;
    }

    setIsSaving(true);
    try {
      const created = await apiClient.post<MessageStyleExampleItem>('/api/admin/assistant-studio/examples', {
        provider_id: selectedProvider?.id ?? null,
        intent: newIntent.trim().toLowerCase(),
        client_message: newClientMsg.trim(),
        assistant_reply: newAssistantReply.trim(),
        category: newCategory.trim() || 'procedural',
        tags: [newIntent.trim().toLowerCase()],
        is_approved: true,
        is_active: true,
        source: 'assistant_studio',
      });

      if (created) {
        setExamples((prev) => [created, ...prev]);
        toast.success('Style example created and saved to database!');
        setIsAddOpen(false);
        setNewIntent('');
        setNewClientMsg('');
        setNewAssistantReply('');
      }
    } catch (err: any) {
      console.error('Failed to create example:', err);
      toast.error(err?.message || 'Failed to save example');
    } finally {
      setIsSaving(false);
    }
  };

  const openEditModal = (ex: MessageStyleExampleItem) => {
    setEditingExample(ex);
    setEditIntent(ex.intent || '');
    setEditClientMsg(ex.client_message || '');
    setEditAssistantReply(ex.assistant_reply || '');
    setEditCategory(ex.category || 'procedural');
  };

  const handleUpdateExample = async () => {
    if (!editingExample) return;
    if (!editIntent.trim() || !editClientMsg.trim() || !editAssistantReply.trim()) {
      toast.error('Please fill in intent, client query, and assistant reply.');
      return;
    }

    setIsUpdating(true);
    try {
      const updated = await apiClient.put<MessageStyleExampleItem>(
        `/api/admin/assistant-studio/examples/${editingExample.id}`,
        {
          intent: editIntent.trim().toLowerCase(),
          client_message: editClientMsg.trim(),
          assistant_reply: editAssistantReply.trim(),
          category: editCategory.trim() || 'procedural',
          tags: [editIntent.trim().toLowerCase()],
        }
      );

      if (updated) {
        setExamples((prev) =>
          prev.map((item) => (item.id === editingExample.id ? { ...item, ...updated } : item))
        );
        toast.success(`Example #${editingExample.id} updated successfully!`);
        setEditingExample(null);
      }
    } catch (err: any) {
      console.error('Failed to update example:', err);
      toast.error(err?.message || 'Failed to update example');
    } finally {
      setIsUpdating(false);
    }
  };

  const uniqueIntents = Array.from(new Set(examples.map((e) => e.intent))).filter(Boolean);

  const filteredExamples = examples.filter((ex) => {
    const matchesSearch =
      (ex.client_message || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (ex.assistant_reply || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (ex.intent || '').toLowerCase().includes(searchTerm.toLowerCase());
    const matchesIntent = selectedIntent === 'all' || ex.intent === selectedIntent;
    return matchesSearch && matchesIntent;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b">
        <div>
          <h2 className="text-xl font-bold tracking-tight flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Approved Style & Procedural Library
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Few-shot conversation demonstrations stored in MessageStyleExample. Injected into Tier 8 to condition tone and flow. Platform seeds are read-only and enforced system-wide.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={() => setIsAddOpen(true)} className="gap-1.5 shadow-sm">
            <Plus className="h-4 w-4" />
            Add Style Example
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search queries, replies, or intent keywords..."
            className="pl-9 text-xs"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <select
            value={selectedIntent}
            onChange={(e) => setSelectedIntent(e.target.value)}
            className="h-9 px-3 rounded-md border text-xs bg-background text-foreground"
          >
            <option value="all">All Intents ({uniqueIntents.length})</option>
            {uniqueIntents.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>

          <Button variant="outline" size="sm" onClick={loadExamples} disabled={isLoading} className="h-9 px-3">
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Examples Grid */}
      <div className="space-y-3">
        {isLoading && examples.length === 0 ? (
          <div className="py-16 text-center text-muted-foreground">
            <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-primary" />
            <p className="text-xs">Loading approved style examples from database...</p>
          </div>
        ) : filteredExamples.length === 0 ? (
          <div className="py-16 text-center text-muted-foreground border rounded-xl bg-card">
            <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-40" />
            <p className="text-sm font-medium">No style examples found matching criteria.</p>
            <p className="text-xs mt-1">Add a new example or import from the Approved Dataset Centre.</p>
          </div>
        ) : (
          filteredExamples.map((ex) => {
            const isPlatformSeed = ex.tenant_id === null;

            return (
              <Card
                key={ex.id}
                className={`border transition-all ${
                  isPlatformSeed
                    ? 'border-indigo-500/30 bg-indigo-500/[0.015]'
                    : ex.is_active
                    ? 'border-border/70 bg-card'
                    : 'border-border/30 bg-muted/20 opacity-70'
                }`}
              >
                <CardContent className="p-4 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="font-mono text-[11px] font-semibold">
                        Intent: {ex.intent}
                      </Badge>
                      <Badge variant="secondary" className="text-[10px]">
                        {ex.category}
                      </Badge>

                      {/* Distinctive Platform Seed (Read-Only) Badge */}
                      {isPlatformSeed ? (
                        <Badge
                          variant="outline"
                          className="bg-indigo-500/15 text-indigo-700 dark:text-indigo-400 border-indigo-500/30 text-[10px] font-semibold gap-1 font-mono"
                        >
                          <Lock className="h-3 w-3" />
                          Platform Seed (Read-Only)
                        </Badge>
                      ) : ex.provider_id ? (
                        <Badge variant="default" className="text-[10px]">
                          Provider #{ex.provider_id}
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px] text-muted-foreground">
                          Tenant-Owned
                        </Badge>
                      )}
                    </div>

                    {/* Action Controls: Read-only Lockdown for Platform Seeds vs Full CRUD for Tenant-Owned */}
                    <div className="flex items-center gap-1.5">
                      {isPlatformSeed ? (
                        <div
                          className="flex items-center gap-1.5"
                          title="Platform seeds are enforced system-wide and cannot be mutated or deleted by tenant admins."
                        >
                          <span className="text-[11px] font-mono text-muted-foreground flex items-center gap-1 px-2 py-0.5 rounded bg-muted/50 border">
                            <Lock className="h-3 w-3 text-muted-foreground" />
                            Enforced Active
                          </span>
                          <Button
                            variant="ghost"
                            size="icon"
                            disabled
                            className="h-7 w-7 text-muted-foreground opacity-40 cursor-not-allowed"
                            title="Platform seeds are enforced system-wide and cannot be edited by tenant admins."
                          >
                            <Edit2 className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            disabled
                            className="h-7 w-7 text-muted-foreground opacity-40 cursor-not-allowed"
                            title="Platform seeds are enforced system-wide and cannot be deleted by tenant admins."
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleToggleActive(ex.id, ex.is_active)}
                            className="h-7 px-2 text-xs gap-1"
                          >
                            {ex.is_active ? (
                              <>
                                <ToggleRight className="h-4 w-4 text-emerald-500" />
                                <span className="text-emerald-600 dark:text-emerald-400 font-medium">Active</span>
                              </>
                            ) : (
                              <>
                                <ToggleLeft className="h-4 w-4 text-muted-foreground" />
                                <span className="text-muted-foreground">Inactive</span>
                              </>
                            )}
                          </Button>

                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openEditModal(ex)}
                            className="h-7 w-7 text-muted-foreground hover:text-foreground"
                            title="Edit Example"
                          >
                            <Edit2 className="h-3.5 w-3.5" />
                          </Button>

                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDelete(ex.id)}
                            className="h-7 w-7 text-muted-foreground hover:text-destructive"
                            title="Delete Example"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="p-3 rounded-lg bg-muted/30 border space-y-1">
                      <span className="font-semibold text-primary font-mono text-[11px]">Incoming Customer Query:</span>
                      <p className="text-foreground leading-relaxed whitespace-pre-wrap">{ex.client_message}</p>
                    </div>

                    <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 space-y-1">
                      <span className="font-semibold text-primary font-mono text-[11px]">Approved Exemplar Reply:</span>
                      <p className="text-foreground leading-relaxed whitespace-pre-wrap">{ex.assistant_reply}</p>
                    </div>
                  </div>

                  {ex.content_hash && (
                    <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground font-mono">
                      <Hash className="h-3 w-3" />
                      <span>Hash: {ex.content_hash.slice(0, 16)}...</span>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })
        )}
      </div>

      {/* Add Example Dialog */}
      <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
        <DialogContent className="sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle>Add Approved Style Example</DialogTitle>
            <DialogDescription>
              Create a new conversational exemplar for Tier 8. Will be saved to MessageStyleExample table scoped to your tenant.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            <div>
              <Label className="text-xs">Intent Tag (e.g. greeting, cancellation, price)</Label>
              <Input
                value={newIntent}
                onChange={(e) => setNewIntent(e.target.value)}
                placeholder="e.g. greeting"
                className="mt-1 text-xs"
              />
            </div>

            <div>
              <Label className="text-xs">Category</Label>
              <Input
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                placeholder="e.g. procedural"
                className="mt-1 text-xs"
              />
            </div>

            <div>
              <Label className="text-xs">Incoming Client Message</Label>
              <Textarea
                value={newClientMsg}
                onChange={(e) => setNewClientMsg(e.target.value)}
                placeholder="What the client says..."
                className="mt-1 text-xs min-h-[60px]"
              />
            </div>

            <div>
              <Label className="text-xs">Approved Exemplar Assistant Reply</Label>
              <Textarea
                value={newAssistantReply}
                onChange={(e) => setNewAssistantReply(e.target.value)}
                placeholder="How Tori / Assistant should idealistically respond..."
                className="mt-1 text-xs min-h-[70px]"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddOpen(false)} disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={handleCreateExample} disabled={isSaving}>
              {isSaving ? <RefreshCw className="h-4 w-4 animate-spin mr-1" /> : null}
              Save Example
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Example Dialog for Tenant-Owned Examples */}
      <Dialog open={!!editingExample} onOpenChange={(open) => !open && setEditingExample(null)}>
        <DialogContent className="sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle>Edit Style Example #{editingExample?.id}</DialogTitle>
            <DialogDescription>
              Update conversational exemplar for Tier 8. Validated against prompt injection and dynamic data leaks.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            <div>
              <Label className="text-xs">Intent Tag</Label>
              <Input
                value={editIntent}
                onChange={(e) => setEditIntent(e.target.value)}
                placeholder="e.g. greeting"
                className="mt-1 text-xs"
              />
            </div>

            <div>
              <Label className="text-xs">Category</Label>
              <Input
                value={editCategory}
                onChange={(e) => setEditCategory(e.target.value)}
                placeholder="e.g. procedural"
                className="mt-1 text-xs"
              />
            </div>

            <div>
              <Label className="text-xs">Incoming Client Message</Label>
              <Textarea
                value={editClientMsg}
                onChange={(e) => setEditClientMsg(e.target.value)}
                placeholder="What the client says..."
                className="mt-1 text-xs min-h-[60px]"
              />
            </div>

            <div>
              <Label className="text-xs">Approved Exemplar Assistant Reply</Label>
              <Textarea
                value={editAssistantReply}
                onChange={(e) => setEditAssistantReply(e.target.value)}
                placeholder="How Tori / Assistant should respond..."
                className="mt-1 text-xs min-h-[70px]"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingExample(null)} disabled={isUpdating}>
              Cancel
            </Button>
            <Button onClick={handleUpdateExample} disabled={isUpdating}>
              {isUpdating ? <RefreshCw className="h-4 w-4 animate-spin mr-1" /> : null}
              Update Example
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
