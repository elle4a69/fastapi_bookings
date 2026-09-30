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
  Sparkles,
  FileCode,
  Tag,
  Shield,
  Layers,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import type { KnowledgeProposalItem, ProviderItem } from '../types';

interface KnowledgeCuratorTabProps {
  selectedProvider: ProviderItem | null;
}

type CanonicalDecisionCode =
  | 'accepted'
  | 'evidence_only'
  | 'pending_review'
  | 'quarantined'
  | 'rejected'
  | 'superseded'
  | 'other';

interface CanonicalDecisionInfo {
  code: CanonicalDecisionCode;
  label: string;
  badgeClass: string;
}

export const KnowledgeCuratorTab: React.FC<KnowledgeCuratorTabProps> = ({ selectedProvider }) => {
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [proposals, setProposals] = useState<KnowledgeProposalItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [curatingId, setCuratingId] = useState<number | null>(null);

  const loadProposals = () => {
    setIsLoading(true);
    const pParam = selectedProvider?.id ? `provider_id=${selectedProvider.id}` : '';
    // If filterStatus is not 'all', send status param to API
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

  const handleAction = async (id: number, action: 'approved' | 'quarantined' | 'rejected', isStyle: boolean) => {
    setCuratingId(id);
    try {
      await apiClient.post(`/api/admin/assistant-studio/curator/proposals/${id}/curate`, {
        action,
      });

      if (action === 'approved') {
        if (isStyle) {
          toast.success(`Proposal #${id} approved into MessageStyleExample (Tier 8 Procedural Guidance).`);
        } else {
          toast.success(`Proposal #${id} approved into CuratedMemory (Tier 7 Factual Knowledge).`);
        }
      } else if (action === 'quarantined') {
        toast.warning(`Proposal #${id} moved to quarantine.`);
      } else {
        toast.info(`Proposal #${id} marked as rejected.`);
      }
      loadProposals();
    } catch (err: any) {
      console.error('Failed to curate proposal:', err);
      toast.error(err?.message || 'Failed to curate proposal');
    } finally {
      setCuratingId(null);
    }
  };

  const getCanonicalDecision = (p: KnowledgeProposalItem): CanonicalDecisionInfo => {
    const rawRes = (p.resolution_code || '').toLowerCase();
    const rawReason = (p.reason_code || '').toLowerCase();
    const rawStatus = (p.status || '').toLowerCase();
    const rawType = (p.proposal_type || '').toLowerCase();

    // 1. Accepted / Approved
    if (
      rawStatus === 'accepted' ||
      rawStatus === 'approved' ||
      rawRes.includes('approved') ||
      rawRes.includes('accepted')
    ) {
      return {
        code: 'accepted',
        label: 'accepted',
        badgeClass: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30',
      };
    }

    // 2. Evidence Only
    if (
      rawRes === 'evidence_only' ||
      rawReason === 'evidence_only' ||
      rawStatus === 'evidence_only'
    ) {
      return {
        code: 'evidence_only',
        label: 'evidence_only',
        badgeClass: 'bg-sky-500/15 text-sky-700 dark:text-sky-300 border-sky-500/30',
      };
    }

    // 3. Quarantined
    if (
      rawStatus === 'quarantined' ||
      rawType === 'quarantine' ||
      rawReason === 'quarantined' ||
      rawRes.includes('quarantine')
    ) {
      return {
        code: 'quarantined',
        label: 'quarantined',
        badgeClass: 'bg-orange-500/15 text-orange-700 dark:text-orange-400 border-orange-500/30',
      };
    }

    // 4. Superseded
    if (
      rawStatus === 'superseded' ||
      rawRes === 'superseded' ||
      rawType === 'supersede'
    ) {
      return {
        code: 'superseded',
        label: 'superseded',
        badgeClass: 'bg-slate-500/15 text-slate-700 dark:text-slate-400 border-slate-500/30',
      };
    }

    // 5. Rejected
    if (
      rawStatus === 'rejected' ||
      rawReason.includes('reject') ||
      rawRes.includes('reject')
    ) {
      return {
        code: 'rejected',
        label: 'rejected',
        badgeClass: 'bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-500/30',
      };
    }

    // 6. Pending Review
    if (
      rawStatus === 'pending' ||
      rawStatus === 'pending_review' ||
      !p.resolution_code
    ) {
      return {
        code: 'pending_review',
        label: 'pending_review',
        badgeClass: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30',
      };
    }

    return {
      code: 'other',
      label: p.status || 'unknown',
      badgeClass: 'bg-muted text-muted-foreground border-border',
    };
  };

  const extractVariables = (item: KnowledgeProposalItem): string[] => {
    const found = new Set<string>();

    if (item.extracted_variables) {
      if (Array.isArray(item.extracted_variables)) {
        item.extracted_variables.forEach((v) => found.add(String(v)));
      } else if (typeof item.extracted_variables === 'object') {
        Object.keys(item.extracted_variables).forEach((k) => found.add(k));
      }
    }

    if (item.variables) {
      if (Array.isArray(item.variables)) {
        item.variables.forEach((v) => found.add(String(v)));
      } else if (typeof item.variables === 'object') {
        Object.keys(item.variables).forEach((k) => found.add(k));
      }
    }

    const combined = `${item.proposed_fact || ''} ${item.ideal_response || ''} ${item.user_query || ''}`;
    const regex = /\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g;
    let match: RegExpExecArray | null;
    while ((match = regex.exec(combined)) !== null) {
      found.add(match[1]);
    }

    return Array.from(found);
  };

  const filterOptions = [
    { key: 'all', label: 'All Proposals' },
    { key: 'pending', label: 'Pending Review' },
    { key: 'accepted', label: 'Accepted' },
    { key: 'evidence_only', label: 'Evidence Only' },
    { key: 'quarantined', label: 'Quarantined' },
    { key: 'rejected', label: 'Rejected' },
    { key: 'superseded', label: 'Superseded' },
  ];

  // Client-side fallback filter matching canonical decision code or raw status
  const displayedProposals = proposals.filter((p) => {
    if (filterStatus === 'all') return true;
    const dec = getCanonicalDecision(p);
    if (filterStatus === 'pending' && dec.code === 'pending_review') return true;
    if (filterStatus === dec.code) return true;
    return p.status === filterStatus;
  });

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
            Truthful human-in-the-loop review queue for candidate knowledge. Dispatches factual proposals to CuratedMemory (Tier 7) and procedural style to MessageStyleExample (Tier 8).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono text-xs">
            Queue: {proposals.filter((p) => getCanonicalDecision(p).code === 'pending_review').length} Pending Review
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
      <div className="flex items-center gap-1.5 border-b pb-2 text-xs overflow-x-auto">
        {filterOptions.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setFilterStatus(opt.key)}
            className={`px-3 py-1.5 rounded-md font-medium whitespace-nowrap transition-colors ${
              filterStatus === opt.key
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-muted-foreground hover:bg-muted'
            }`}
          >
            {opt.label}
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
        ) : displayedProposals.length === 0 ? (
          <div className="py-16 text-center text-muted-foreground border rounded-xl bg-card">
            <Database className="h-8 w-8 mx-auto mb-2 opacity-40" />
            <p className="text-sm font-medium">No proposals in queue matching "{filterStatus}".</p>
            <p className="text-xs mt-1">Proposals are surfaced autonomously by the conversational learning pipeline.</p>
          </div>
        ) : (
          displayedProposals.map((p) => {
            const decisionInfo = getCanonicalDecision(p);
            const isPending = decisionInfo.code === 'pending_review';
            const isProcessing = curatingId === p.id;
            const isStyleGuidance =
              p.knowledge_kind === 'style_example' ||
              p.category === 'style' ||
              p.category === 'tone' ||
              p.proposal_type === 'style';

            const proposedFact = p.proposed_fact || p.ideal_response || '';
            const extractedVars = extractVariables(p);

            return (
              <Card
                key={p.id}
                className={`border transition-all ${
                  isStyleGuidance
                    ? 'border-purple-500/30 bg-purple-500/[0.015]'
                    : decisionInfo.code === 'accepted'
                    ? 'border-emerald-500/40 bg-emerald-500/[0.02]'
                    : decisionInfo.code === 'quarantined'
                    ? 'border-orange-500/40 bg-orange-500/[0.02]'
                    : decisionInfo.code === 'rejected'
                    ? 'border-rose-500/40 bg-rose-500/[0.02]'
                    : 'border-border/70 bg-card'
                }`}
              >
                <CardContent className="p-4 space-y-3.5">
                  {/* Top Bar: Proposal ID, Canonical Decision Badge, Type, Target Destination */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="font-mono text-[11px] font-semibold">
                        Proposal #{p.id}
                      </Badge>

                      {/* Canonical Decision Code Badge */}
                      <Badge variant="outline" className={`font-mono text-[10px] uppercase font-bold ${decisionInfo.badgeClass}`}>
                        {decisionInfo.label}
                      </Badge>

                      {/* Destination Visual Distinction */}
                      {isStyleGuidance ? (
                        <Badge variant="outline" className="bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/30 text-[10px] gap-1 font-medium">
                          <Sparkles className="h-3 w-3" />
                          Style Guidance → MessageStyleExample (Tier 8)
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/30 text-[10px] gap-1 font-medium">
                          <Layers className="h-3 w-3" />
                          Factual Proposal → CuratedMemory (Tier 7)
                        </Badge>
                      )}

                      <Badge variant="secondary" className="text-[10px] font-mono">
                        Type: {p.proposal_type}
                      </Badge>

                      <Badge variant="outline" className="text-[10px] font-mono">
                        <Tag className="h-2.5 w-2.5 mr-1 text-muted-foreground" />
                        Category: {p.category}
                      </Badge>

                      {p.is_dynamic_risk && (
                        <Badge variant="destructive" className="text-[10px] animate-pulse">
                          Dynamic Leak Risk
                        </Badge>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[11px] text-muted-foreground font-mono">
                        Confidence: {Math.round((p.confidence_score || 0) * 100)}%
                      </span>
                      {p.created_at && (
                        <span className="text-[10px] text-muted-foreground">
                          {p.created_at}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Main Grid: Query Trigger vs Proposed Fact */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="p-3 rounded-lg bg-muted/30 border space-y-1">
                      <span className="font-semibold text-primary font-mono text-[11px] flex items-center gap-1">
                        <FileCode className="h-3.5 w-3.5 text-primary" />
                        Proposed Trigger / User Query:
                      </span>
                      <p className="text-foreground leading-relaxed whitespace-pre-wrap">{p.user_query || '(No explicit query trigger recorded)'}</p>
                    </div>

                    <div className={`p-3 rounded-lg border space-y-1 ${
                      isStyleGuidance
                        ? 'bg-purple-500/[0.04] border-purple-500/25'
                        : 'bg-primary/5 border-primary/20'
                    }`}>
                      <span className="font-semibold text-primary font-mono text-[11px] flex items-center gap-1">
                        {isStyleGuidance ? (
                          <>
                            <Sparkles className="h-3.5 w-3.5 text-purple-600 dark:text-purple-400" />
                            Proposed Conversational Style Response:
                          </>
                        ) : (
                          <>
                            <Shield className="h-3.5 w-3.5 text-primary" />
                            Proposed Durable Fact:
                          </>
                        )}
                      </span>
                      <p className="text-foreground leading-relaxed whitespace-pre-wrap font-sans font-medium">{proposedFact}</p>
                    </div>
                  </div>

                  {/* Extracted Variables Group if Present */}
                  {extractedVars.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap pt-1 text-xs">
                      <span className="text-[11px] font-semibold text-muted-foreground font-sans">
                        Extracted Variables:
                      </span>
                      {extractedVars.map((v) => (
                        <Badge
                          key={v}
                          variant="secondary"
                          className="font-mono text-[10px] bg-primary/10 text-primary border-primary/20"
                        >
                          {`{{${v}}}`}
                        </Badge>
                      ))}
                    </div>
                  )}

                  {/* Resolution & Reason Code Ledger */}
                  {(p.resolution_code || p.reason_code) && (
                    <div className="p-2.5 rounded-md bg-muted/40 border text-[11px] font-mono flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Info className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        <span className="text-muted-foreground">Resolution Reason:</span>
                        <span className="font-semibold text-foreground">
                          {p.resolution_code || p.reason_code}
                        </span>
                      </div>
                      {p.reason_code && p.resolution_code && p.reason_code !== p.resolution_code && (
                        <span className="text-muted-foreground text-[10px]">
                          Trigger Code: {p.reason_code}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Review Actions for Pending Items */}
                  {isPending && (
                    <div className="flex items-center justify-end gap-2 pt-2 border-t">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={isProcessing}
                        onClick={() => handleAction(p.id, 'rejected', isStyleGuidance)}
                        className="text-xs text-muted-foreground hover:text-destructive"
                      >
                        <XCircle className="h-3.5 w-3.5 mr-1" />
                        Reject
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={isProcessing}
                        onClick={() => handleAction(p.id, 'quarantined', isStyleGuidance)}
                        className="text-xs text-orange-600 border-orange-500/30 hover:bg-orange-500/10"
                      >
                        <AlertTriangle className="h-3.5 w-3.5 mr-1" />
                        Quarantine
                      </Button>
                      <Button
                        size="sm"
                        disabled={isProcessing}
                        onClick={() => handleAction(p.id, 'approved', isStyleGuidance)}
                        className={`text-xs text-white shadow-xs ${
                          isStyleGuidance
                            ? 'bg-purple-600 hover:bg-purple-700'
                            : 'bg-emerald-600 hover:bg-emerald-700'
                        }`}
                      >
                        <CheckCircle className="h-3.5 w-3.5 mr-1" />
                        {isStyleGuidance ? 'Approve to Style Examples' : 'Approve to CuratedMemory'}
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
