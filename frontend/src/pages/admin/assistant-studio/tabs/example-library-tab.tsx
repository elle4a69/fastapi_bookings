import { useState } from 'react';
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
  Edit2,
  Trash2,
  BookOpen
} from 'lucide-react';
import { toast } from 'sonner';
import type { MessageStyleExampleItem, ProviderItem } from '../types';

interface ExampleLibraryTabProps {
  selectedProvider: ProviderItem | null;
}

export const ExampleLibraryTab: React.FC<ExampleLibraryTabProps> = ({ selectedProvider }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedIntent, setSelectedIntent] = useState<string>('all');
  const [selectedScope, setSelectedScope] = useState<string>('all');

  // Seed examples mimicking approved procedural pairs
  const [examples, setExamples] = useState<MessageStyleExampleItem[]>([
    {
      id: 1,
      tenant_id: null,
      provider_id: null,
      intent: 'greeting',
      client_message: 'Hi, are you taking new clients at the clinic?',
      assistant_reply:
        'Hi there! Yes, we warmly welcome new clients. Which service or practitioner are you looking to book today?',
      category: 'procedural',
      tags: ['welcome', 'onboarding'],
      is_approved: true,
      is_active: true,
      source: 'assistant_ui_import',
      content_hash: '8f7a932d1e0c4b5a',
      created_at: '2026-09-28',
    },
    {
      id: 2,
      tenant_id: 1,
      provider_id: null,
      intent: 'cancellation',
      client_message: 'I need to cancel my appointment for this Friday.',
      assistant_reply:
        'I can certainly help you reschedule or cancel. Please note our 24-hour notice policy ensures no cancellation fee is incurred. Would you like me to find an alternative date next week?',
      category: 'procedural',
      tags: ['cancellation', 'policy'],
      is_approved: true,
      is_active: true,
      source: 'tenant_seed',
      content_hash: '1a2b3c4d5e6f7a8b',
      created_at: '2026-09-28',
    },
    {
      id: 3,
      tenant_id: 1,
      provider_id: 101,
      intent: 'pricing',
      client_message: 'How much is a 60 minute deep tissue session with Alex?',
      assistant_reply:
        'A 60-minute deep tissue consultation with Dr. Alex Mercer is $140 AUD. We also offer private health fund rebates via HICAPS on the day of your appointment.',
      category: 'procedural',
      tags: ['pricing', 'rebates'],
      is_approved: true,
      is_active: true,
      source: 'provider_override',
      content_hash: '4e5f6a7b8c9d0e1f',
      created_at: '2026-09-28',
    },
    {
      id: 4,
      tenant_id: null,
      provider_id: null,
      intent: 'location',
      client_message: 'Where are you located and is there parking nearby?',
      assistant_reply:
        'Our primary clinic is situated at Suite 4, 120 Castlereagh St in Sydney CBD. There is 2-hour parking along the adjacent street and a secure parking garage 50m away.',
      category: 'procedural',
      tags: ['parking', 'directions'],
      is_approved: true,
      is_active: true,
      source: 'assistant_ui_import',
      content_hash: '9d8c7b6a5f4e3d2c',
      created_at: '2026-09-28',
    },
    {
      id: 5,
      tenant_id: 1,
      provider_id: null,
      intent: 'booking_request',
      client_message: 'Do you have anything available next Tuesday morning?',
      assistant_reply:
        'Let me check our calendar for next Tuesday morning. We have slots open at 9:30 AM and 11:00 AM. Would either of those suit you?',
      category: 'procedural',
      tags: ['booking', 'availability'],
      is_approved: true,
      is_active: true,
      source: 'tenant_seed',
      content_hash: '5b6a7c8d9e0f1a2b',
      created_at: '2026-09-28',
    },
  ]);

  // Modal State
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<MessageStyleExampleItem | null>(null);
  const [formIntent, setFormIntent] = useState('greeting');
  const [formClientMsg, setFormClientMsg] = useState('');
  const [formAssistantReply, setFormAssistantReply] = useState('');
  const [formCategory, setFormCategory] = useState('procedural');

  const filteredExamples = examples.filter((ex) => {
    const matchesSearch =
      ex.client_message.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ex.assistant_reply.toLowerCase().includes(searchTerm.toLowerCase()) ||
      ex.intent.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesIntent = selectedIntent === 'all' || ex.intent === selectedIntent;

    let matchesScope = true;
    if (selectedScope === 'platform_seed') {
      matchesScope = ex.tenant_id === null && ex.provider_id === null;
    } else if (selectedScope === 'tenant_default') {
      matchesScope = ex.tenant_id !== null && ex.provider_id === null;
    } else if (selectedScope === 'provider_override') {
      matchesScope = ex.provider_id !== null;
    }

    return matchesSearch && matchesIntent && matchesScope;
  });

  const handleToggleActive = (id: number) => {
    setExamples((prev) =>
      prev.map((item) => (item.id === id ? { ...item, is_active: !item.is_active } : item))
    );
    toast.info('Example active status updated.');
  };

  const handleOpenAddDialog = () => {
    setEditingItem(null);
    setFormIntent('greeting');
    setFormClientMsg('');
    setFormAssistantReply('');
    setFormCategory('procedural');
    setIsDialogOpen(true);
  };

  const handleOpenEditDialog = (item: MessageStyleExampleItem) => {
    setEditingItem(item);
    setFormIntent(item.intent);
    setFormClientMsg(item.client_message);
    setFormAssistantReply(item.assistant_reply);
    setFormCategory(item.category);
    setIsDialogOpen(true);
  };

  const handleSaveItem = () => {
    if (!formClientMsg.trim() || !formAssistantReply.trim()) {
      toast.error('Both client message and assistant reply are required.');
      return;
    }

    if (editingItem) {
      setExamples((prev) =>
        prev.map((item) =>
          item.id === editingItem.id
            ? {
                ...item,
                intent: formIntent,
                client_message: formClientMsg.trim(),
                assistant_reply: formAssistantReply.trim(),
                category: formCategory,
              }
            : item
        )
      );
      toast.success('Style example updated.');
    } else {
      const newItem: MessageStyleExampleItem = {
        id: Date.now(),
        tenant_id: 1,
        provider_id: selectedProvider?.id || null,
        intent: formIntent,
        client_message: formClientMsg.trim(),
        assistant_reply: formAssistantReply.trim(),
        category: formCategory,
        tags: [formIntent],
        is_approved: true,
        is_active: true,
        source: selectedProvider?.id ? 'provider_override' : 'tenant_seed',
        content_hash: Math.random().toString(36).substring(2, 10),
        created_at: new Date().toISOString().split('T')[0],
      };
      setExamples((prev) => [newItem, ...prev]);
      toast.success('New style example added.');
    }

    setIsDialogOpen(false);
  };

  const handleDeleteItem = (id: number) => {
    setExamples((prev) => prev.filter((item) => item.id !== id));
    toast.success('Style example removed.');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b">
        <div>
          <h2 className="text-xl font-bold tracking-tight flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Message Style Example Library
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Curated conversational few-shot pairs (`MessageStyleExample`) used in Tier 8 to condition tone and phrasing.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={handleOpenAddDialog} className="gap-1.5 shadow-sm">
            <Plus className="h-4 w-4" />
            Add Style Example
          </Button>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 rounded-lg border bg-card/60">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search dialogue examples..."
            className="pl-8 text-xs h-9"
          />
        </div>

        <div className="flex items-center gap-2">
          <Label className="text-xs font-medium text-muted-foreground whitespace-nowrap">Intent:</Label>
          <select
            value={selectedIntent}
            onChange={(e) => setSelectedIntent(e.target.value)}
            className="w-full text-xs h-9 rounded-md border border-input bg-background px-3 py-1 text-foreground shadow-xs focus-visible:outline-none"
          >
            <option value="all">All Intents</option>
            <option value="greeting">Greeting</option>
            <option value="pricing">Pricing</option>
            <option value="location">Location & Directions</option>
            <option value="cancellation">Cancellation & Reschedule</option>
            <option value="booking_request">Booking Request</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <Label className="text-xs font-medium text-muted-foreground whitespace-nowrap">Scope:</Label>
          <select
            value={selectedScope}
            onChange={(e) => setSelectedScope(e.target.value)}
            className="w-full text-xs h-9 rounded-md border border-input bg-background px-3 py-1 text-foreground shadow-xs focus-visible:outline-none"
          >
            <option value="all">All Scopes</option>
            <option value="platform_seed">Platform Seeds (Global)</option>
            <option value="tenant_default">Tenant Default</option>
            <option value="provider_override">Provider Override</option>
          </select>
        </div>
      </div>

      {/* Results Count & Scope Notice */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Showing {filteredExamples.length} exemplars</span>
        <span className="flex items-center gap-1 text-[11px]">
          <BookOpen className="h-3.5 w-3.5 text-primary" />
          Max 3 most relevant examples are injected into Tier 8 at runtime
        </span>
      </div>

      {/* Exemplar Cards List */}
      <div className="space-y-3">
        {filteredExamples.map((ex) => (
          <Card key={ex.id} className={`border transition-all ${ex.is_active ? 'border-border/70' : 'opacity-60 bg-muted/20'}`}>
            <CardContent className="p-4 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b pb-2.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="secondary" className="font-mono text-xs uppercase tracking-wide">
                    {ex.intent}
                  </Badge>
                  {ex.provider_id ? (
                    <Badge variant="outline" className="bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/30 text-[11px]">
                      Provider Override (#{ex.provider_id})
                    </Badge>
                  ) : ex.tenant_id ? (
                    <Badge variant="outline" className="bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30 text-[11px]">
                      Tenant Default
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[11px]">
                      Platform Seed
                    </Badge>
                  )}
                  <span className="text-[10px] text-muted-foreground font-mono flex items-center gap-0.5">
                    <Hash className="h-3 w-3" /> {ex.content_hash}
                  </span>
                </div>

                <div className="flex items-center gap-1.5 self-end sm:self-auto">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleToggleActive(ex.id)}
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
                    onClick={() => handleOpenEditDialog(ex)}
                    className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  >
                    <Edit2 className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDeleteItem(ex.id)}
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>

              {/* Dialogue Turn Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="p-3 rounded-lg bg-muted/30 border space-y-1">
                  <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider">
                    Client Inbound Message:
                  </span>
                  <p className="text-foreground leading-relaxed font-sans">{ex.client_message}</p>
                </div>

                <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 space-y-1">
                  <span className="text-[10px] text-primary uppercase font-bold tracking-wider">
                    Exemplar Assistant Reply:
                  </span>
                  <p className="text-foreground leading-relaxed font-sans">{ex.assistant_reply}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {filteredExamples.length === 0 && (
          <div className="p-8 text-center rounded-lg border border-dashed bg-muted/10 text-muted-foreground text-xs">
            No style examples matched your search and filter criteria.
          </div>
        )}
      </div>

      {/* Add / Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingItem ? 'Edit Style Example' : 'Add New Style Example'}</DialogTitle>
            <DialogDescription className="text-xs">
              Conversational demonstration pairs teach the model how to reply with proper tone and structure.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs">Intent Tag</Label>
                <select
                  value={formIntent}
                  onChange={(e) => setFormIntent(e.target.value)}
                  className="w-full text-xs h-9 rounded-md border border-input bg-background px-3 py-1 text-foreground"
                >
                  <option value="greeting">Greeting</option>
                  <option value="pricing">Pricing</option>
                  <option value="location">Location & Directions</option>
                  <option value="cancellation">Cancellation & Reschedule</option>
                  <option value="booking_request">Booking Request</option>
                  <option value="general">General Inquiry</option>
                </select>
              </div>

              <div className="space-y-1">
                <Label className="text-xs">Category</Label>
                <Input
                  value={formCategory}
                  onChange={(e) => setFormCategory(e.target.value)}
                  className="text-xs h-9"
                  placeholder="procedural"
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label className="text-xs">Client Message (Inbound Query)</Label>
              <Textarea
                value={formClientMsg}
                onChange={(e) => setFormClientMsg(e.target.value)}
                rows={2}
                className="text-xs resize-y"
                placeholder="e.g. Can I cancel my appointment?"
              />
            </div>

            <div className="space-y-1">
              <Label className="text-xs">Exemplar Assistant Reply (Target Phrasing)</Label>
              <Textarea
                value={formAssistantReply}
                onChange={(e) => setFormAssistantReply(e.target.value)}
                rows={3}
                className="text-xs resize-y"
                placeholder="e.g. I can certainly help you reschedule. Please note our 24h policy..."
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setIsDialogOpen(false)} className="text-xs">
              Cancel
            </Button>
            <Button size="sm" onClick={handleSaveItem} className="text-xs">
              Save Example
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
