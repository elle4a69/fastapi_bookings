import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Database,
  RefreshCw,
  Sparkles,
  Layers,
  Activity,
  ListFilter,
  CheckCircle,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import type {
  ProviderItem,
  CuratedMemoryItem,
  EpistemicGraphData,
  PipelineStatusData,
  DrawerDetailContext,
  KnowledgeProposalItem,
  GraphNode,
} from '../types';
import { LearningPipelineFlow } from '../components/learning-pipeline-flow';
import { EpistemicGraphCanvas } from '../components/epistemic-graph-canvas';
import { KnowledgeLedgerTable } from '../components/knowledge-ledger-table';
import { ProvenanceLifecycleDrawer } from '../components/provenance-lifecycle-drawer';

interface KnowledgeCuratorTabProps {
  selectedProvider: ProviderItem | null;
}

type SubViewKey = 'pipeline-graph' | 'ledger' | 'proposals';

export const KnowledgeCuratorTab: React.FC<KnowledgeCuratorTabProps> = ({ selectedProvider }) => {
  // Navigation / View Switcher
  const [activeView, setActiveView] = useState<SubViewKey>('pipeline-graph');

  // Stage filter selected from Pipeline Flow (Screen A)
  const [selectedStageId, setSelectedStageId] = useState<number | null>(null);

  // Drawer state (Screen D)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerContext, setDrawerContext] = useState<DrawerDetailContext | null>(null);

  // Live Backend Data States
  const [pipelineData, setPipelineData] = useState<PipelineStatusData | null>(null);
  const [graphData, setGraphData] = useState<EpistemicGraphData | null>(null);
  const [memories, setMemories] = useState<CuratedMemoryItem[]>([]);
  const [proposals, setProposals] = useState<KnowledgeProposalItem[]>([]);
  const [proposalFilter, setProposalFilter] = useState<string>('all');

  // Loading States
  const [isLoadingPipeline, setIsLoadingPipeline] = useState(false);
  const [isLoadingGraph, setIsLoadingGraph] = useState(false);
  const [isLoadingMemories, setIsLoadingMemories] = useState(false);
  const [isLoadingProposals, setIsLoadingProposals] = useState(false);
  const [curatingProposalId, setCuratingProposalId] = useState<number | null>(null);

  // 1. Fetch Pipeline Status (Screen A)
  const fetchPipelineStatus = useCallback(() => {
    setIsLoadingPipeline(true);
    const qs = selectedProvider?.id ? `?provider_id=${selectedProvider.id}` : '';
    apiClient
      .get<PipelineStatusData>(`/api/admin/assistant-studio/curator/pipeline-status${qs}`)
      .then((data) => {
        if (data && data.ok) {
          setPipelineData(data);
        }
      })
      .catch((err) => {
        console.error('Failed to load pipeline status:', err);
      })
      .finally(() => {
        setIsLoadingPipeline(false);
      });
  }, [selectedProvider?.id]);

  // 2. Fetch Epistemic Graph (Screen B)
  const fetchGraphData = useCallback(() => {
    setIsLoadingGraph(true);
    const qs = selectedProvider?.id ? `?provider_id=${selectedProvider.id}` : '';
    apiClient
      .get<EpistemicGraphData>(`/api/admin/assistant-studio/curator/graph-nodes${qs}`)
      .then((data) => {
        if (data && data.ok) {
          setGraphData(data);
        }
      })
      .catch((err) => {
        console.error('Failed to load graph nodes:', err);
      })
      .finally(() => {
        setIsLoadingGraph(false);
      });
  }, [selectedProvider?.id]);

  // 3. Fetch Curated Memories Ledger (Screen C)
  const fetchMemories = useCallback(() => {
    setIsLoadingMemories(true);
    const qs = selectedProvider?.id ? `?provider_id=${selectedProvider.id}` : '';
    apiClient
      .get<CuratedMemoryItem[]>(`/api/admin/assistant-studio/curator/memories${qs}`)
      .then((data) => {
        if (Array.isArray(data)) {
          setMemories(data);
        }
      })
      .catch((err) => {
        console.error('Failed to load memories:', err);
      })
      .finally(() => {
        setIsLoadingMemories(false);
      });
  }, [selectedProvider?.id]);

  // 4. Fetch Knowledge Proposals
  const fetchProposals = useCallback(() => {
    setIsLoadingProposals(true);
    const pParam = selectedProvider?.id ? `provider_id=${selectedProvider.id}` : '';
    const sParam = proposalFilter !== 'all' ? `status=${proposalFilter}` : '';
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
      })
      .finally(() => {
        setIsLoadingProposals(false);
      });
  }, [selectedProvider?.id, proposalFilter]);

  // Refresh All Data
  const refreshAll = useCallback(() => {
    fetchPipelineStatus();
    fetchGraphData();
    fetchMemories();
    fetchProposals();
  }, [fetchPipelineStatus, fetchGraphData, fetchMemories, fetchProposals]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // Open Drawer from Node Click (Screen B)
  const handleSelectNode = (node: GraphNode) => {
    const matchedMemory = node.curated_memory_id
      ? memories.find((m) => m.id === node.curated_memory_id)
      : null;
    setDrawerContext({
      itemType: 'node',
      node,
      memory: matchedMemory,
    });
    setIsDrawerOpen(true);
  };

  // Open Drawer from Memory Table (Screen C)
  const handleSelectMemoryForDrawer = (memory: CuratedMemoryItem) => {
    setDrawerContext({
      itemType: 'memory',
      memory,
    });
    setIsDrawerOpen(true);
  };

  // Handle Proposal Curation (Approve, Quarantine, Reject)
  const handleCurateProposal = async (
    id: number,
    action: 'approved' | 'quarantined' | 'rejected',
    isStyle: boolean
  ) => {
    setCuratingProposalId(id);
    try {
      await apiClient.post(`/api/admin/assistant-studio/curator/proposals/${id}/curate`, {
        action,
      });

      if (action === 'approved') {
        if (isStyle) {
          toast.success(`Proposal #${id} approved into MessageStyleExample (Tier 8 Guidance).`);
        } else {
          toast.success(`Proposal #${id} approved into CuratedMemory (Tier 7 Durable Fact).`);
        }
      } else if (action === 'quarantined') {
        toast.warning(`Proposal #${id} moved to quarantine.`);
      } else {
        toast.info(`Proposal #${id} marked as rejected.`);
      }
      refreshAll();
    } catch (err: any) {
      console.error('Failed to curate proposal:', err);
      toast.error(err?.message || 'Failed to curate proposal');
    } finally {
      setCuratingProposalId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & View Navigator */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight flex items-center gap-2">
              <Database className="h-5 w-5 text-primary" />
              Autonomous Knowledge Curator
            </h2>
            <Badge variant="outline" className="font-mono text-xs">
              Master Spec 54
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            Truthful, multi-tenant knowledge lifecycle management: 6-stage evolutionary pipeline, relational authority, Neo4j epistemic graph, and Redis dual-epoch invalidation.
          </p>
        </div>

        {/* View Switcher Controls */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg border bg-muted/30 self-start sm:self-auto">
          <button
            onClick={() => setActiveView('pipeline-graph')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition-colors ${
              activeView === 'pipeline-graph'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-muted-foreground hover:bg-muted'
            }`}
          >
            <Activity className="h-3.5 w-3.5" />
            Pipeline & Graph
          </button>

          <button
            onClick={() => setActiveView('ledger')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition-colors ${
              activeView === 'ledger'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-muted-foreground hover:bg-muted'
            }`}
          >
            <Layers className="h-3.5 w-3.5" />
            Knowledge Ledger ({memories.length})
          </button>

          <button
            onClick={() => setActiveView('proposals')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition-colors ${
              activeView === 'proposals'
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-muted-foreground hover:bg-muted'
            }`}
          >
            <ListFilter className="h-3.5 w-3.5" />
            Proposals Queue ({proposals.filter((p) => p.status === 'pending').length})
          </button>
        </div>
      </div>

      {/* Safety Invariant Notice */}
      <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/[0.03] flex items-start gap-3 text-xs">
        <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <span className="font-semibold text-foreground">Anti-Hallucination & Scope Invariant:</span>
          <p className="text-muted-foreground leading-relaxed">
            Dynamic operational facts (prices, real-time availability slots, client phone numbers, booking IDs) are strictly forbidden in CuratedMemory.
            Layer 2 Operational Tool Truth overrides Layer 6 Curated Factual Context. Partition isolation enforces provider-private (<code className="font-mono text-foreground">tenant:id:provider:id</code>) and tenant-shared (<code className="font-mono text-foreground">tenant:id:shared</code>) boundaries.
          </p>
        </div>
      </div>

      {/* Sub-View 1: Pipeline Flow (Screen A) & Epistemic Graph (Screen B) */}
      {activeView === 'pipeline-graph' && (
        <div className="space-y-6">
          {/* Screen A: Autonomous Learning Pipeline Flow */}
          <LearningPipelineFlow
            pipelineData={pipelineData}
            isLoading={isLoadingPipeline}
            selectedStageId={selectedStageId}
            onSelectStage={(stageId) => setSelectedStageId(stageId)}
            onRefresh={refreshAll}
          />

          {/* Screen B: Interactive Epistemic Graph Canvas */}
          <EpistemicGraphCanvas
            graphData={graphData}
            isLoading={isLoadingGraph}
            selectedProvider={selectedProvider}
            onSelectNode={handleSelectNode}
            onRefresh={refreshAll}
          />
        </div>
      )}

      {/* Sub-View 2: Knowledge Ledger Table (Screen C) */}
      {activeView === 'ledger' && (
        <KnowledgeLedgerTable
          memories={memories}
          isLoading={isLoadingMemories}
          selectedProvider={selectedProvider}
          onRefresh={refreshAll}
          onSelectMemoryForDrawer={handleSelectMemoryForDrawer}
        />
      )}

      {/* Sub-View 3: Human-in-the-Loop Curator Proposals Queue */}
      {activeView === 'proposals' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b">
            <div>
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                Human-in-the-Loop Review Queue
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Review candidate facts and style examples autonomously extracted from client conversations.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <select
                value={proposalFilter}
                onChange={(e) => setProposalFilter(e.target.value)}
                className="h-8 text-xs rounded-md border border-input bg-background px-2.5 py-1 text-foreground"
              >
                <option value="all">All Proposals</option>
                <option value="pending">Pending Review Only</option>
                <option value="accepted">Accepted / Approved</option>
                <option value="quarantined">Quarantined</option>
                <option value="rejected">Rejected</option>
              </select>

              <Button
                variant="outline"
                size="sm"
                onClick={fetchProposals}
                disabled={isLoadingProposals}
                className="h-8 text-xs gap-1"
              >
                <RefreshCw className={`h-3 w-3 ${isLoadingProposals ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
          </div>

          {/* Proposals List */}
          <div className="space-y-3">
            {isLoadingProposals && proposals.length === 0 ? (
              <div className="py-16 text-center text-muted-foreground">
                <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-primary" />
                <p className="text-xs">Loading curator proposals from database...</p>
              </div>
            ) : proposals.length === 0 ? (
              <div className="py-16 text-center text-muted-foreground border rounded-xl bg-card">
                <Database className="h-8 w-8 mx-auto mb-2 opacity-40" />
                <p className="text-sm font-medium">No proposals matching filter "{proposalFilter}".</p>
                <p className="text-xs mt-1">Proposals are surfaced autonomously by the conversational learning pipeline.</p>
              </div>
            ) : (
              proposals.map((p) => {
                const isPending = p.status === 'pending';
                const isProcessing = curatingProposalId === p.id;
                const isStyleGuidance =
                  p.knowledge_kind === 'style_example' ||
                  p.category === 'style' ||
                  p.proposal_type === 'style';

                return (
                  <Card key={p.id} className="border transition-all bg-card">
                    <CardContent className="p-4 space-y-3">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="outline" className="font-mono text-[11px] font-semibold">
                            Proposal #{p.id}
                          </Badge>
                          <Badge
                            variant="outline"
                            className={`text-[10px] uppercase font-bold font-mono ${
                              p.status === 'accepted' || p.status === 'approved'
                                ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                                : p.status === 'quarantined'
                                ? 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30'
                                : p.status === 'rejected'
                                ? 'bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-500/30'
                                : 'bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30'
                            }`}
                          >
                            {p.status}
                          </Badge>
                          {isStyleGuidance ? (
                            <Badge variant="outline" className="bg-purple-500/10 text-purple-600 border-purple-500/30 text-[10px] gap-1 font-medium">
                              <Sparkles className="h-3 w-3" />
                              Style Guidance → MessageStyleExample
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="bg-cyan-500/10 text-cyan-600 border-cyan-500/30 text-[10px] gap-1 font-medium">
                              <Layers className="h-3 w-3" />
                              Factual Proposal → CuratedMemory
                            </Badge>
                          )}
                          <Badge variant="secondary" className="text-[10px] font-mono">
                            Category: {p.category}
                          </Badge>
                        </div>
                        <span className="text-[11px] text-muted-foreground font-mono">
                          Confidence: {Math.round(p.confidence_score * 100)}%
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                        <div className="p-2.5 rounded-lg bg-muted/30 border space-y-1">
                          <span className="font-semibold text-primary font-mono text-[10px]">
                            Trigger / Context Query:
                          </span>
                          <p className="text-foreground whitespace-pre-wrap">{p.user_query || '(None)'}</p>
                        </div>
                        <div className="p-2.5 rounded-lg bg-primary/[0.03] border border-primary/20 space-y-1">
                          <span className="font-semibold text-primary font-mono text-[10px]">
                            Proposed Durable Fact / Response:
                          </span>
                          <p className="text-foreground font-medium whitespace-pre-wrap">{p.ideal_response || p.proposed_fact || '(None)'}</p>
                        </div>
                      </div>

                      {isPending && (
                        <div className="flex items-center justify-end gap-2 pt-2 border-t">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={isProcessing}
                            onClick={() => handleCurateProposal(p.id, 'rejected', isStyleGuidance)}
                            className="h-7 text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-500/10"
                          >
                            <XCircle className="h-3.5 w-3.5 mr-1" />
                            Reject
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={isProcessing}
                            onClick={() => handleCurateProposal(p.id, 'quarantined', isStyleGuidance)}
                            className="h-7 text-xs text-amber-600 hover:text-amber-700 hover:bg-amber-500/10"
                          >
                            <AlertTriangle className="h-3.5 w-3.5 mr-1" />
                            Quarantine
                          </Button>
                          <Button
                            size="sm"
                            disabled={isProcessing}
                            onClick={() => handleCurateProposal(p.id, 'approved', isStyleGuidance)}
                            className="h-7 text-xs gap-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                          >
                            <CheckCircle className="h-3.5 w-3.5" />
                            Approve Fact
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
      )}

      {/* Screen D: End-to-End Provenance & Lifecycle Drawer */}
      <ProvenanceLifecycleDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        context={drawerContext}
      />
    </div>
  );
};
