import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info,
  Database,
  RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import type { KnowledgeProposalItem, ProviderItem } from '../types';

interface KnowledgeCuratorTabProps {
  selectedProvider: ProviderItem | null;
}

export const KnowledgeCuratorTab: React.FC<KnowledgeCuratorTabProps> = ({ selectedProvider }) => {
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [proposals, setProposals] = useState<KnowledgeProposalItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [curatingId, setCuratingId] = useState<number | null>(null);

  const loadProposals = () => {
    setIsLoading(true);
    const pParam = selectedProvider?.id ? `provider_id=${selectedProvider.id}` : '';
    const sParam = filterStatus !== 'all' ? `status=${filterStatus}` : '';
    const qs = [pParam, sParam].filter(Boolean).join('&');
    const url = `/api/admin/assistant-studio/curator/proposals${qs ? `?${qs}` : ''}`;

    apiClient
      .get<KnowledgeProposalItem[]>(url)
      .then((data) => {
        if (Array.isArray(data)) {
          setProposals(data);
        }
      })
      .catch((err) => {
        console.error('Failed to load proposals:', err);
        toast.error('Failed to load knowledge proposals');
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    loadProposals();
  }, [selectedProvider?.id, filterStatus]);

  const handleAction = async (id: number, action: 'approved' | 'quarantined' | 'rejected') => {
    setCuratingId(id);
    try {
      await apiClient.post(`/api/admin/assistant-studio/curator/proposals/${id}/curate`, {
        action,
      });

      if (action === 'approved') {
        toast.success(`Proposal #${id} approved and committed to CuratedMemory.`);
      } else if (action === 'quarantined') {
        toast.warning(`Proposal #${id} moved to quarantine.`);
      } else {
        toast.info(`Proposal #${id} rejected.`);
      }
      loadProposals();
    } catch (err: any) {
      console.error('Failed to curate proposal:', err);
      toast.error(err?.message || 'Failed to curate proposal');
    } finally {
      setCuratingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b">
        <div>
          <h2 className="text-xl font-bold tracking-tight flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            Knowledge Curator & Review Queue
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Human-in-the-loop review queue for candidate business facts. Approving a proposal promotes it to CuratedMemory (Tier 7).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono text-xs">
            Review Queue: {proposals.filter((p) => p.status === 'pending').length} Pending
          </Badge>
          <Button variant="outline" size="sm" onClick={loadProposals} disabled={isLoading} className="h-8 gap-1">
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Safety Invariant Notice */}
      <div className="p-3.5 rounded-lg border border-amber-500/30 bg-amber-500/[0.04] flex items-start gap-3 text-xs">
        <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-semibold text-foreground">Anti-Hallucination Guardrail (AGENTS.md):</span>
          <p className="text-muted-foreground leading-relaxed">
            Dynamic operational facts (prices, real-time available slots, client phone numbers, booking IDs) are strictly forbidden in CuratedMemory.
            They are calculated dynamically by server-enforced tools. Curation must reject or quarantine any proposal containing dynamic operational leaks.
          </p>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b pb-2 text-xs">
        {(['all', 'pending', 'quarantined', 'approved', 'rejected'] as const).map((st) => (
          <button
            key={st}
            onClick={() => setFilterStatus(st)}
            className={`px-3 py-1.5 rounded-md font-medium capitalize transition-colors ${
              filterStatus === st ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'
            }`}
          >
            {st}
          </button>
        ))}
      </div>

      {/* Proposals List */}
      <div className="space-y-4">
        {isLoading && proposals.length === 0 ? (
          <div className="py-16 text-center text-muted-foreground">
            <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-primary" />
            <p className="text-xs">Loading curator proposals from database...</p>
          </div>
        ) : proposals.length === 0 ? (
          <div className="py-16 text-center text-muted-foreground border rounded-xl bg-card">
            <Database className="h-8 w-8 mx-auto mb-2 opacity-40" />
            <p className="text-sm font-medium">No proposals in queue for this filter status.</p>
            <p className="text-xs mt-1">New proposals are surfaced autonomously by the learning pipeline.</p>
          </div>
        ) : (
          proposals.map((p) => {
            const isPending = p.status === 'pending';
            const isQuarantined = p.status === 'quarantined';
            const isApproved = p.status === 'approved' || p.status === 'accepted';
            const isProcessing = curatingId === p.id;

            return (
              <Card
                key={p.id}
                className={`border transition-all ${
                  isApproved
                    ? 'border-emerald-500/40 bg-emerald-500/[0.02]'
                    : isQuarantined
                    ? 'border-destructive/40 bg-destructive/[0.02]'
                    : 'border-border/70 bg-card'
                }`}
              >
                <CardContent className="p-4 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="font-mono text-[11px] font-semibold">
                        Proposal #{p.id}
                      </Badge>
                      <Badge variant="secondary" className="text-[10px]">
                        {p.proposal_type}
                      </Badge>
                      <Badge variant="outline" className="text-[10px]">
                        Category: {p.category}
                      </Badge>
                      {p.is_dynamic_risk && (
                        <Badge variant="destructive" className="text-[10px] animate-pulse">
                          Dynamic Leak Risk
                        </Badge>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-muted-foreground">
                        Confidence: {Math.round(p.confidence_score * 100)}%
                      </span>
                      <Badge
                        variant={
                          isApproved ? 'default' : isQuarantined ? 'destructive' : isPending ? 'secondary' : 'outline'
                        }
                        className="text-[10px] capitalize"
                      >
                        {p.status}
                      </Badge>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="p-3 rounded-lg bg-muted/30 border space-y-1">
                      <span className="font-semibold text-primary font-mono text-[11px]">Proposed Query / Trigger:</span>
                      <p className="text-foreground leading-relaxed">{p.user_query}</p>
                    </div>

                    <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 space-y-1">
                      <span className="font-semibold text-primary font-mono text-[11px]">Candidate Knowledge Fact:</span>
                      <p className="text-foreground leading-relaxed">{p.ideal_response}</p>
                    </div>
                  </div>

                  {p.reason_code && (
                    <div className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                      <Info className="h-3.5 w-3.5" />
                      <span>Curator Reason: {p.reason_code}</span>
                    </div>
                  )}

                  {isPending && (
                    <div className="flex items-center justify-end gap-2 pt-2 border-t">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={isProcessing}
                        onClick={() => handleAction(p.id, 'rejected')}
                        className="text-xs text-muted-foreground hover:text-destructive"
                      >
                        <XCircle className="h-3.5 w-3.5 mr-1" />
                        Reject
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={isProcessing}
                        onClick={() => handleAction(p.id, 'quarantined')}
                        className="text-xs text-amber-600 border-amber-500/30 hover:bg-amber-500/10"
                      >
                        <AlertTriangle className="h-3.5 w-3.5 mr-1" />
                        Quarantine
                      </Button>
                      <Button
                        size="sm"
                        disabled={isProcessing}
                        onClick={() => handleAction(p.id, 'approved')}
                        className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                      >
                        <CheckCircle className="h-3.5 w-3.5 mr-1" />
                        Approve to CuratedMemory
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
};
