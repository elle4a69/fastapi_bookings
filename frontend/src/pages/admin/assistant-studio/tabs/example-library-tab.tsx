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
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newIntent, setNewIntent] = useState('');
  const [newClientMsg, setNewClientMsg] = useState('');
  const [newAssistantReply, setNewAssistantReply] = useState('');
  const [newCategory, setNewCategory] = useState('procedural');
  const [isSaving, setIsSaving] = useState(false);

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
      toast.error('Failed to update example status');
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
        setIsDialogOpen(false);
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
            Few-shot conversation demonstrations stored in MessageStyleExample. Injected into Tier 8 to condition tone and flow.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={() => setIsDialogOpen(true)} className="gap-1.5 shadow-sm">
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
          filteredExamples.map((ex) => (
            <Card
              key={ex.id}
              className={`border transition-all ${
                ex.is_active ? 'border-border/70 bg-card' : 'border-border/30 bg-muted/20 opacity-70'
              }`}
            >
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-mono text-[11px] font-semibold">
                      Intent: {ex.intent}
                    </Badge>
                    <Badge variant="secondary" className="text-[10px]">
                      {ex.category}
                    </Badge>
                    {ex.provider_id ? (
                      <Badge variant="default" className="text-[10px]">
                        Provider #{ex.provider_id}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px] text-muted-foreground">
                        Tenant-Wide
                      </Badge>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
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
                      onClick={() => handleDelete(ex.id)}
                      className="h-7 w-7 text-muted-foreground hover:text-destructive"
                      title="Delete Example"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="p-3 rounded-lg bg-muted/30 border space-y-1">
                    <span className="font-semibold text-primary font-mono text-[11px]">Incoming Customer Query:</span>
                    <p className="text-foreground leading-relaxed">{ex.client_message}</p>
                  </div>

                  <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 space-y-1">
                    <span className="font-semibold text-primary font-mono text-[11px]">Approved Exemplar Reply:</span>
                    <p className="text-foreground leading-relaxed">{ex.assistant_reply}</p>
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
          ))
        )}
      </div>

      {/* Add Example Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle>Add Approved Style Example</DialogTitle>
            <DialogDescription>
              Create a new conversational exemplar for Tier 8. Will be saved to MessageStyleExample table.
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
            <Button variant="outline" onClick={() => setIsDialogOpen(false)} disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={handleCreateExample} disabled={isSaving}>
              {isSaving ? <RefreshCw className="h-4 w-4 animate-spin mr-1" /> : null}
              Save Example
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
