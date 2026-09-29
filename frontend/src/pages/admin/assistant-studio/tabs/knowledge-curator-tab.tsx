import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info,
  Database,
  Sparkles,
} from 'lucide-react';
import { toast } from 'sonner';
import type { KnowledgeProposalItem, ProviderItem } from '../types';

interface KnowledgeCuratorTabProps {
  selectedProvider: ProviderItem | null;
}

export const KnowledgeCuratorTab: React.FC<KnowledgeCuratorTabProps> = ({ selectedProvider }) => {
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const [proposals, setProposals] = useState<KnowledgeProposalItem[]>([
    {
      id: 101,
      tenant_id: 1,
      provider_id: null,
      proposal_type: 'business_fact',
      category: 'hours_and_facilities',
      user_query: 'Is wheelchair access available at the clinic building?',
      ideal_response: 'Yes, our clinic has ramp access at the main entrance and elevator service to Suite 4.',
      status: 'pending',
      confidence_score: 0.94,
      is_dynamic_risk: false,
      created_at: '2026-09-29 09:15',
    },
    {
      id: 102,
      tenant_id: 1,
      provider_id: 101,
      proposal_type: 'operational_leak_risk',
      category: 'pricing_schedule',
      user_query: 'Can you do a booking tomorrow at 3pm for $99 special?',
      ideal_response: 'We have an open slot tomorrow at 3pm for $99 discounted rate.',
      status: 'quarantined',
      reason_code: 'safety_violation',
      resolution_code: 'dynamic_date_price_detected',
      confidence_score: 0.62,
      is_dynamic_risk: true,
      created_at: '2026-09-29 11:30',
    },
    {
      id: 103,
      tenant_id: 1,
      provider_id: 101,
      proposal_type: 'provider_fact',
      category: 'practitioner_bio',
      user_query: 'What qualifications does Dr. Alex Mercer have?',
      ideal_response: 'Dr. Alex Mercer holds a Masters in Clinical Physiotherapy from USyd and specializes in musculoskeletal rehab.',
      status: 'pending',
      confidence_score: 0.98,
      is_dynamic_risk: false,
      created_at: '2026-09-29 13:45',
    },
    {
      id: 104,
      tenant_id: 1,
      provider_id: null,
      proposal_type: 'dialogue_style',
      category: 'procedural_greeting',
      user_query: 'Hey there are you open?',
      ideal_response: 'Hey! Yes, our doors are open and we are scheduling appointments today. How can I help?',
      status: 'pending',
      confidence_score: 0.88,
      is_dynamic_risk: false,
      created_at: '2026-09-29 14:10',
    },
  ]);

  const filteredProposals = proposals.filter((p) => {
    if (filterStatus === 'all') return true;
    return p.status === filterStatus;
  });

  const handleAction = (id: number, action: 'approved' | 'quarantined' | 'rejected') => {
    setProposals((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, status: action } : item
      )
    );

    if (action === 'approved') {
      toast.success(`Proposal #${id} approved and committed to CuratedMemory.`);
    } else if (action === 'quarantined') {
      toast.warning(`Proposal #${id} moved to quarantine.`);
    } else {
      toast.info(`Proposal #${id} rejected and purged.`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b">
        <div>
          <h2 className="text-xl font-bold tracking-tight flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            Autonomous Knowledge Curator & Review Queue
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Inspect, approve, or quarantine autonomous learned facts. Enforces strict provider boundaries.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono text-xs">
            {selectedProvider?.id ? `Scope: ${selectedProvider.name}` : 'Scope: All Providers'}
          </Badge>
        </div>
      </div>

      {/* Epistemic Architecture Separation Banner */}
      <Card className="border-blue-500/30 bg-blue-500/[0.03]">
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400 font-semibold text-sm">
            <Info className="h-4 w-4 shrink-0" />
            <span>Strict Epistemic Isolation Architecture</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-card border space-y-1">
              <span className="font-bold text-foreground flex items-center gap-1.5">
                <Database className="h-3.5 w-3.5 text-blue-500" />
                CuratedMemory (Factual)
              </span>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                Stores static, durable truths: clinic location, parking, practitioner bios, policy hours. Never stores slots or dynamic prices.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-card border space-y-1">
              <span className="font-bold text-foreground flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-purple-500" />
                MessageStyleExample (Procedural)
              </span>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                Stores conversational turns: tone, phrasing, polite declinations, empathy scripts. Never pollutes factual epistemic graphs.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-card border space-y-1">
              <span className="font-bold text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                Dynamic Operational Invariant
              </span>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                Live availability, travel fees, and quotes MUST come directly from Tier 2 Live Tools. Reject any proposal containing dates or prices!
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Review Queue Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg border bg-card/60">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-semibold text-muted-foreground">Filter Queue:</span>
          {(['all', 'pending', 'quarantined', 'approved', 'rejected'] as const).map((status) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium capitalize transition-colors ${
                filterStatus === status
                  ? 'bg-primary text-primary-foreground shadow-xs'
                  : 'bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground'
              }`}
            >
              {status} ({proposals.filter((p) => status === 'all' || p.status === status).length})
            </button>
          ))}
        </div>
      </div>

      {/* Proposal Cards List */}
      <div className="space-y-3">
        {filteredProposals.map((item) => (
          <Card key={item.id} className="border-border/70 hover:border-border transition-all">
            <CardContent className="p-4 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b pb-2.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant="outline" className="font-mono text-xs">
                    Proposal #{item.id}
                  </Badge>

                  {/* Provider Isolation Badge */}
                  {item.provider_id ? (
                    <Badge variant="secondary" className="bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/30 text-[11px]">
                      Provider Scoped (#{item.provider_id})
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30 text-[11px]">
                      Tenant Shared (All Providers)
                    </Badge>
                  )}

                  <span className="text-xs text-muted-foreground font-medium">Category: {item.category}</span>
                  <span className="text-[10px] text-muted-foreground">• {item.created_at}</span>
                </div>

                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className={`text-[11px] capitalize ${
                      item.status === 'approved'
                        ? 'border-emerald-500/30 text-emerald-600 bg-emerald-500/10'
                        : item.status === 'quarantined'
                        ? 'border-amber-500/30 text-amber-600 bg-amber-500/10'
                        : item.status === 'rejected'
                        ? 'border-red-500/30 text-red-600 bg-red-500/10'
                        : 'border-blue-500/30 text-blue-600 bg-blue-500/10'
                    }`}
                  >
                    {item.status}
                  </Badge>
                  <span className="text-xs font-mono text-muted-foreground">
                    Conf: {Math.round(item.confidence_score * 100)}%
                  </span>
                </div>
              </div>

              {/* Dynamic Warning Alert if detected */}
              {item.is_dynamic_risk && (
                <div className="p-3 rounded-lg border border-red-500/40 bg-red-500/10 text-xs text-red-900 dark:text-red-300 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold">Dynamic Date/Price Detected: Reject Recommended</span>
                    <p className="text-[11px] text-muted-foreground dark:text-red-200/80 mt-0.5">
                      This proposal contains specific booking times ("tomorrow 3pm") or price rates ("$99"). Approving this would cause the LLM to hallucinate stale appointment openings!
                    </p>
                  </div>
                </div>
              )}

              {/* Proposal Content */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div className="p-3 rounded-lg bg-muted/30 border space-y-1">
                  <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider">
                    Client Inbound Query:
                  </span>
                  <p className="text-foreground leading-relaxed">{item.user_query}</p>
                </div>

                <div className="p-3 rounded-lg bg-card border space-y-1">
                  <span className="text-[10px] text-primary uppercase font-bold tracking-wider">
                    Extracted Proposed Fact / Reply:
                  </span>
                  <p className="text-foreground leading-relaxed">{item.ideal_response}</p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t">
                {item.status === 'pending' && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleAction(item.id, 'rejected')}
                      className="h-8 text-xs text-destructive hover:text-destructive gap-1"
                    >
                      <XCircle className="h-3.5 w-3.5" /> Reject
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleAction(item.id, 'quarantined')}
                      className="h-8 text-xs text-amber-600 hover:text-amber-700 gap-1"
                    >
                      <AlertTriangle className="h-3.5 w-3.5" /> Quarantine
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleAction(item.id, 'approved')}
                      disabled={item.is_dynamic_risk}
                      className="h-8 text-xs gap-1"
                    >
                      <CheckCircle className="h-3.5 w-3.5" /> Accept & Curate
                    </Button>
                  </>
                )}

                {item.status === 'quarantined' && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleAction(item.id, 'rejected')}
                      className="h-8 text-xs text-destructive hover:text-destructive gap-1"
                    >
                      <XCircle className="h-3.5 w-3.5" /> Reject
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleAction(item.id, 'approved')}
                      className="h-8 text-xs gap-1"
                    >
                      <CheckCircle className="h-3.5 w-3.5" /> Force Approve
                    </Button>
                  </>
                )}

                {(item.status === 'approved' || item.status === 'rejected') && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleAction(item.id, 'quarantined')}
                    className="h-8 text-xs text-muted-foreground gap-1"
                  >
                    Move back to Quarantine
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}

        {filteredProposals.length === 0 && (
          <div className="p-8 text-center rounded-lg border border-dashed bg-muted/10 text-muted-foreground text-xs">
            No proposals found in the "{filterStatus}" queue.
          </div>
        )}
      </div>
    </div>
  );
};
