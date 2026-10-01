import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Database,
  Search,
  Plus,
  Edit3,
  Archive,
  AlertTriangle,
  RefreshCw,
  Cpu,
  Sparkles,
  Eye,
  CheckCircle2,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import type { CuratedMemoryItem, ProviderItem } from '../types';

interface KnowledgeLedgerTableProps {
  memories: CuratedMemoryItem[];
  isLoading: boolean;
  selectedProvider: ProviderItem | null;
  onRefresh: () => void;
  onSelectMemoryForDrawer: (memory: CuratedMemoryItem) => void;
}

export const KnowledgeLedgerTable: React.FC<KnowledgeLedgerTableProps> = ({
  memories,
  isLoading,
  selectedProvider,
  onRefresh,
  onSelectMemoryForDrawer,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [kindFilter, setKindFilter] = useState<string>('all');
  const [scopeFilter, setScopeFilter] = useState<'all' | 'shared' | 'provider'>('all');

  // Add Fact Modal State
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [addCategory, setAddCategory] = useState('general');
  const [addUserQuery, setAddUserQuery] = useState('');
  const [addIdealResponse, setAddIdealResponse] = useState('');
  const [addKnowledgeKind, setAddKnowledgeKind] = useState('durable_fact');
  const [isAdding, setIsAdding] = useState(false);

  // Edit / Supersede Modal State
  const [editingMemory, setEditingMemory] = useState<CuratedMemoryItem | null>(null);
  const [editResponse, setEditResponse] = useState('');
  const [editQuery, setEditQuery] = useState('');
  const [editCategory, setEditCategory] = useState('');
  const [isSubmittingEdit, setIsSubmittingEdit] = useState(false);

  // Processing state for inline actions
  const [actionProcessingId, setActionProcessingId] = useState<number | null>(null);

  // Filtered Memories
  const displayedMemories = memories.filter((m) => {
    // Status filter
    if (statusFilter !== 'all' && m.status !== statusFilter) return false;
    // Kind filter
    if (kindFilter !== 'all' && m.knowledge_kind !== kindFilter) return false;
    // Scope filter
    if (scopeFilter === 'shared' && !m.is_tenant_shared) return false;
    if (scopeFilter === 'provider' && m.is_tenant_shared) return false;
    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchQuery = m.user_query.toLowerCase().includes(q);
      const matchResp = m.ideal_response.toLowerCase().includes(q);
      const matchCat = m.category.toLowerCase().includes(q);
      const matchId = String(m.id).includes(q);
      return matchQuery || matchResp || matchCat || matchId;
    }
    return true;
  });

  // Action: Create Memory
  const handleCreateMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addUserQuery.trim() || !addIdealResponse.trim()) {
      toast.error('Query trigger and ideal fact response are required');
      return;
    }

    setIsAdding(true);
    try {
      await apiClient.post('/api/admin/assistant-studio/curator/memories', {
        category: addCategory.trim().toLowerCase(),
        user_query: addUserQuery.trim(),
        ideal_response: addIdealResponse.trim(),
        knowledge_kind: addKnowledgeKind,
        provider_id: selectedProvider?.id ?? null,
        authority: 'owner_verified',
      });
      toast.success('Curated memory created and scheduled for graph projection!');
      setIsAddOpen(false);
      setAddUserQuery('');
      setAddIdealResponse('');
      onRefresh();
    } catch (err: any) {
      console.error('Failed to create memory:', err);
      toast.error(err?.message || 'Failed to create memory (check for dynamic leaks or PII)');
    } finally {
      setIsAdding(false);
    }
  };

  // Action: Open Edit / Supersede Modal
  const openEditModal = (memory: CuratedMemoryItem) => {
    setEditingMemory(memory);
    setEditResponse(memory.ideal_response);
    setEditQuery(memory.user_query);
    setEditCategory(memory.category);
  };

  // Action: Submit Edit with Immutable Supersession
  const handleSupersedeMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingMemory) return;

    setIsSubmittingEdit(true);
    try {
      const resp = await apiClient.put<any>(
        `/api/admin/assistant-studio/curator/memories/${editingMemory.id}`,
        {
          user_query: editQuery.trim(),
          ideal_response: editResponse.trim(),
          category: editCategory.trim().toLowerCase(),
          action: 'supersede',
        }
      );
      toast.success(
        `Memory #${editingMemory.id} superseded by new version #${resp?.new_memory_id ?? 'active'}!`
      );
      setEditingMemory(null);
      onRefresh();
    } catch (err: any) {
      console.error('Failed to supersede memory:', err);
      toast.error(err?.message || 'Failed to supersede memory');
    } finally {
      setIsSubmittingEdit(false);
    }
  };

  // Action: Quarantine Memory
  const handleQuarantine = async (memory: CuratedMemoryItem) => {
    setActionProcessingId(memory.id);
    try {
      await apiClient.put(`/api/admin/assistant-studio/curator/memories/${memory.id}`, {
        action: 'quarantine',
      });
      toast.warning(`Memory #${memory.id} quarantined safely.`);
      onRefresh();
    } catch (err: any) {
      toast.error(err?.message || 'Failed to quarantine memory');
    } finally {
      setActionProcessingId(null);
    }
  };

  // Action: Retract Memory
  const handleRetract = async (memory: CuratedMemoryItem) => {
    if (!confirm(`Are you sure you want to retract fact #${memory.id}? It will be purged from the active cache.`)) {
      return;
    }
    setActionProcessingId(memory.id);
    try {
      await apiClient.delete(`/api/admin/assistant-studio/curator/memories/${memory.id}`);
      toast.info(`Memory #${memory.id} retracted and purged from active cache.`);
      onRefresh();
    } catch (err: any) {
      toast.error(err?.message || 'Failed to retract memory');
    } finally {
      setActionProcessingId(null);
    }
  };

  // Action: Re-Project Memory
  const handleReproject = async (memory: CuratedMemoryItem) => {
    setActionProcessingId(memory.id);
    try {
      await apiClient.post(`/api/admin/assistant-studio/curator/memories/${memory.id}/reproject`);
      toast.success(`Memory #${memory.id} scheduled for graph re-projection.`);
      onRefresh();
    } catch (err: any) {
      toast.error(err?.message || 'Failed to schedule re-projection');
    } finally {
      setActionProcessingId(null);
    }
  };

  return (
    <Card className="border-border shadow-xs">
      {/* Table Header and Filter Bar */}
      <div className="p-4 border-b bg-muted/20 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-primary" />
          <h3 className="font-semibold text-sm">Curated Knowledge Ledger</h3>
          <Badge variant="outline" className="font-mono text-xs">
            {displayedMemories.length} entries
          </Badge>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Search Box */}
          <div className="relative w-48">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search facts..."
              className="h-8 text-xs pl-8"
            />
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-8 text-xs rounded-md border border-input bg-background px-2.5 py-1 text-foreground"
          >
            <option value="all">All Statuses</option>
            <option value="active">Active Only</option>
            <option value="quarantined">Quarantined</option>
            <option value="superseded">Superseded</option>
          </select>

          {/* Kind Filter */}
          <select
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value)}
            className="h-8 text-xs rounded-md border border-input bg-background px-2.5 py-1 text-foreground"
          >
            <option value="all">All Kinds</option>
            <option value="durable_fact">Durable Fact</option>
            <option value="policy_guidance">Policy Guidance</option>
            <option value="preference">Preference</option>
            <option value="response_guidance">Response Guidance</option>
            <option value="style_example">Style Example</option>
          </select>

          {/* Scope Filter */}
          <div className="flex items-center rounded-md border p-0.5 bg-background text-xs">
            <button
              onClick={() => setScopeFilter('all')}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                scopeFilter === 'all' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setScopeFilter('provider')}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                scopeFilter === 'provider' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'
              }`}
            >
              Provider
            </button>
            <button
              onClick={() => setScopeFilter('shared')}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                scopeFilter === 'shared' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'
              }`}
            >
              Shared
            </button>
          </div>

          {/* Add Fact Button */}
          <Button
            size="sm"
            onClick={() => setIsAddOpen(true)}
            className="h-8 text-xs gap-1"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Fact
          </Button>

          {/* Refresh Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={isLoading}
            className="h-8 text-xs gap-1"
          >
            <RefreshCw className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Table Content */}
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="text-[11px] bg-muted/40">
                <TableHead className="w-14">ID</TableHead>
                <TableHead className="w-28">Kind & Scope</TableHead>
                <TableHead className="w-24">Category</TableHead>
                <TableHead className="min-w-[180px]">Trigger / Query</TableHead>
                <TableHead className="min-w-[240px]">Curated Fact Response</TableHead>
                <TableHead className="w-24">Status</TableHead>
                <TableHead className="w-28">Graph State</TableHead>
                <TableHead className="w-24 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && memories.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="py-12 text-center text-muted-foreground">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-primary" />
                    <p className="text-xs">Loading curated knowledge ledger...</p>
                  </TableCell>
                </TableRow>
              ) : displayedMemories.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="py-12 text-center text-muted-foreground">
                    <Database className="h-8 w-8 mx-auto mb-2 opacity-40" />
                    <p className="text-sm font-medium">No curated memories found.</p>
                    <p className="text-xs mt-1">Add a new verified fact or approve proposals from the curator queue.</p>
                  </TableCell>
                </TableRow>
              ) : (
                displayedMemories.map((m) => {
                  const isProcessing = actionProcessingId === m.id;
                  const isSuperseded = m.status === 'superseded';
                  const isQuarantined = m.status === 'quarantined';

                  return (
                    <TableRow
                      key={m.id}
                      className={`text-xs hover:bg-muted/30 transition-colors ${
                        isSuperseded ? 'opacity-55 bg-muted/10' : ''
                      }`}
                    >
                      {/* ID */}
                      <TableCell className="font-mono text-muted-foreground">
                        #{m.id}
                      </TableCell>

                      {/* Kind & Scope */}
                      <TableCell className="space-y-1">
                        <Badge
                          variant="outline"
                          className="text-[9px] font-mono capitalize block w-fit"
                        >
                          {m.knowledge_kind.replace('_', ' ')}
                        </Badge>
                        {m.is_tenant_shared ? (
                          <Badge
                            variant="outline"
                            className="text-[9px] font-mono bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30"
                          >
                            Shared
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="text-[9px] font-mono bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                          >
                            Provider #{m.provider_id}
                          </Badge>
                        )}
                      </TableCell>

                      {/* Category */}
                      <TableCell>
                        <Badge variant="secondary" className="font-mono text-[10px]">
                          {m.category}
                        </Badge>
                      </TableCell>

                      {/* Trigger / Query */}
                      <TableCell className="font-sans text-muted-foreground line-clamp-2 max-w-xs">
                        {m.user_query}
                      </TableCell>

                      {/* Ideal Response Fact */}
                      <TableCell>
                        <div className="font-sans font-medium text-foreground line-clamp-2 max-w-md">
                          {m.ideal_response}
                        </div>
                        {m.supersedes_id && (
                          <span className="text-[10px] text-muted-foreground font-mono block mt-0.5">
                            ↳ Supersedes #{m.supersedes_id}
                          </span>
                        )}
                      </TableCell>

                      {/* Status */}
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`text-[10px] uppercase font-bold font-mono ${
                            m.status === 'active'
                              ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                              : isQuarantined
                              ? 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30'
                              : 'bg-slate-500/15 text-slate-700 dark:text-slate-400 border-slate-500/30'
                          }`}
                        >
                          {m.status}
                        </Badge>
                      </TableCell>

                      {/* Graph Projection State */}
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`text-[9px] font-mono capitalize ${
                            m.graph_projection_status === 'projected'
                              ? 'border-emerald-500/30 text-emerald-600 bg-emerald-500/5'
                              : m.graph_projection_status === 'pending'
                              ? 'border-blue-500/30 text-blue-600 bg-blue-500/5'
                              : m.graph_projection_status === 'dead_letter'
                              ? 'border-destructive text-destructive bg-destructive/10'
                              : 'border-muted text-muted-foreground'
                          }`}
                        >
                          <Cpu className="h-2.5 w-2.5 mr-1" />
                          {m.graph_projection_status}
                        </Badge>
                      </TableCell>

                      {/* Actions */}
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-muted-foreground hover:text-foreground"
                            onClick={() => onSelectMemoryForDrawer(m)}
                            title="View Lifecycle & Provenance"
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </Button>

                          {!isSuperseded && (
                            <>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-muted-foreground hover:text-primary"
                                onClick={() => openEditModal(m)}
                                disabled={isProcessing}
                                title="Edit Fact (Immutable Supersession)"
                              >
                                <Edit3 className="h-3.5 w-3.5" />
                              </Button>

                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-muted-foreground hover:text-amber-600"
                                onClick={() => handleQuarantine(m)}
                                disabled={isProcessing || isQuarantined}
                                title="Quarantine Fact"
                              >
                                <AlertTriangle className="h-3.5 w-3.5" />
                              </Button>

                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-muted-foreground hover:text-blue-600"
                                onClick={() => handleReproject(m)}
                                disabled={isProcessing}
                                title="Re-project to Graph"
                              >
                                <RefreshCw className={`h-3.5 w-3.5 ${isProcessing ? 'animate-spin' : ''}`} />
                              </Button>

                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                                onClick={() => handleRetract(m)}
                                disabled={isProcessing}
                                title="Retract Fact"
                              >
                                <Archive className="h-3.5 w-3.5" />
                              </Button>
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>

      {/* Modal 1: Add Verified Fact */}
      <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base flex items-center gap-2">
              <Plus className="h-4 w-4 text-primary" />
              Add Curated Knowledge Fact
            </DialogTitle>
            <DialogDescription className="text-xs">
              Directly persist a durable, verified business fact. Anti-hallucination guardrails prevent dynamic pricing or live availability leaks.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreateMemory} className="space-y-3.5 py-1">
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="space-y-1">
                <label className="font-semibold text-foreground">Category Topic</label>
                <Input
                  value={addCategory}
                  onChange={(e) => setAddCategory(e.target.value)}
                  placeholder="e.g. parking, facilities"
                  required
                  className="h-8 text-xs"
                />
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-foreground">Scope</label>
                <Input
                  value={
                    selectedProvider?.id
                      ? `Provider: ${selectedProvider.name}`
                      : 'Tenant Default (All Providers)'
                  }
                  disabled
                  className="h-8 text-xs bg-muted/40 font-mono"
                />
              </div>
            </div>

            <div className="space-y-1 text-xs">
              <label className="font-semibold text-foreground">Knowledge Kind</label>
              <select
                value={addKnowledgeKind}
                onChange={(e) => setAddKnowledgeKind(e.target.value)}
                className="w-full h-8 text-xs rounded-md border border-input bg-background px-2 text-foreground"
              >
                <option value="durable_fact">Durable Fact (Tier 7)</option>
                <option value="response_guidance">Response Guidance</option>
                <option value="style_example">Style Example (Tier 8)</option>
              </select>
            </div>

            <div className="space-y-1 text-xs">
              <label className="font-semibold text-foreground">Query Trigger / User Question</label>
              <Input
                value={addUserQuery}
                onChange={(e) => setAddUserQuery(e.target.value)}
                placeholder="e.g. Is there parking on site?"
                required
                className="h-8 text-xs"
              />
            </div>

            <div className="space-y-1 text-xs">
              <label className="font-semibold text-foreground">Ideal Fact Response (Durable Truth)</label>
              <textarea
                value={addIdealResponse}
                onChange={(e) => setAddIdealResponse(e.target.value)}
                placeholder="e.g. Yes, free validated parking is located in basement level B2."
                required
                rows={3}
                className="w-full text-xs rounded-md border border-input bg-background p-2 text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsAddOpen(false)}
                disabled={isAdding}
                className="h-8 text-xs"
              >
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={isAdding} className="h-8 text-xs gap-1">
                {isAdding ? <RefreshCw className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
                Persist Fact
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Modal 2: Edit Fact with Immutable Supersession */}
      <Dialog open={!!editingMemory} onOpenChange={(open) => !open && setEditingMemory(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base flex items-center gap-2">
              <Edit3 className="h-4 w-4 text-primary" />
              Edit Fact #{editingMemory?.id} (Immutable Supersession)
            </DialogTitle>
            <DialogDescription className="text-xs">
              In accordance with Master Spec 54, existing facts are never overwritten destructively. Editing marks #{editingMemory?.id} as superseded and generates a new active fact with cryptographic link and projection outbox event.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSupersedeMemory} className="space-y-3.5 py-1">
            <div className="space-y-1 text-xs">
              <label className="font-semibold text-foreground">Category</label>
              <Input
                value={editCategory}
                onChange={(e) => setEditCategory(e.target.value)}
                required
                className="h-8 text-xs"
              />
            </div>

            <div className="space-y-1 text-xs">
              <label className="font-semibold text-foreground">Trigger / Query</label>
              <Input
                value={editQuery}
                onChange={(e) => setEditQuery(e.target.value)}
                required
                className="h-8 text-xs"
              />
            </div>

            <div className="space-y-1 text-xs">
              <label className="font-semibold text-foreground">Updated Fact Response</label>
              <textarea
                value={editResponse}
                onChange={(e) => setEditResponse(e.target.value)}
                required
                rows={3}
                className="w-full text-xs rounded-md border border-input bg-background p-2 text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
            </div>

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setEditingMemory(null)}
                disabled={isSubmittingEdit}
                className="h-8 text-xs"
              >
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={isSubmittingEdit} className="h-8 text-xs gap-1">
                {isSubmittingEdit ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                Supersede Fact
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
};
