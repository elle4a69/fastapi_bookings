import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  CheckCircle2,
  ShieldCheck,
  Zap,
  Radio,
  Sparkles,
  MessageSquare,
  CheckCircle,
  ArrowRight,
  TrendingUp,
  Cpu,
  Layers,
} from 'lucide-react';
import type { ChannelType, ProviderItem, StudioTabKey } from '../types';

interface OverviewTabProps {
  selectedProvider: ProviderItem | null;
  activeChannel: ChannelType;
  onNavigateTab: (tab: StudioTabKey) => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  selectedProvider,
  activeChannel,
  onNavigateTab,
}) => {
  const readinessChecklist = [
    { title: 'Base Agent Policy v1 Activated', passed: true, tier: 'Tier 4' },
    { title: 'Server-Enforced Tool Scoping Verified', passed: true, tier: 'Tier 2' },
    { title: 'Platform Safety Rules Enforced', passed: true, tier: 'Tier 1' },
    { title: 'Style Lab Prior Matrix Initialized', passed: true, tier: 'Tier 6' },
    { title: 'Curated Knowledge Base Synchronized', passed: true, tier: 'Tier 7' },
    {
      title: selectedProvider?.id
        ? `Provider Overlay Configured for ${selectedProvider.name}`
        : 'Tenant Default Overlay Active',
      passed: true,
      tier: 'Tier 5',
    },
  ];

  const readinessScore = Math.round(
    (readinessChecklist.filter((c) => c.passed).length / readinessChecklist.length) * 100
  );

  return (
    <div className="space-y-6">
      {/* Top Banner: Status & Quick Info */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-border/60 bg-gradient-to-br from-card to-muted/20">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription className="text-xs uppercase tracking-wider font-semibold">
                Assistant Engine
              </CardDescription>
              <Radio className="h-4 w-4 text-emerald-500 animate-pulse" />
            </div>
            <CardTitle className="text-2xl font-bold flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-emerald-500 ring-4 ring-emerald-500/20" />
              Online & Ready
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center justify-between pt-1">
            <span>Latency: ~340ms</span>
            <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[11px]">
              Channel-Neutral
            </Badge>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-gradient-to-br from-card to-muted/20">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription className="text-xs uppercase tracking-wider font-semibold">
                Provider Readiness
              </CardDescription>
              <TrendingUp className="h-4 w-4 text-blue-500" />
            </div>
            <CardTitle className="text-2xl font-bold flex items-center gap-2">
              {readinessScore}%
              <span className="text-xs font-normal text-muted-foreground">Optimal</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground pt-1">
            <div className="w-full bg-muted rounded-full h-2 mb-1 overflow-hidden">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${readinessScore}%` }}
              />
            </div>
            <span>All 6 runtime tiers fully operational</span>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-gradient-to-br from-card to-muted/20">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription className="text-xs uppercase tracking-wider font-semibold">
                Monthly Throughput
              </CardDescription>
              <MessageSquare className="h-4 w-4 text-purple-500" />
            </div>
            <CardTitle className="text-2xl font-bold">1,284</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center justify-between pt-1">
            <span>94.2% Auto-Resolved</span>
            <Badge variant="outline" className="text-purple-600 dark:text-purple-400 border-purple-500/30 text-[11px]">
              5.8% Escalated
            </Badge>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-gradient-to-br from-card to-muted/20">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription className="text-xs uppercase tracking-wider font-semibold">
                Safety & Guardrails
              </CardDescription>
              <ShieldCheck className="h-4 w-4 text-emerald-500" />
            </div>
            <CardTitle className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
              100% Pass
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center justify-between pt-1">
            <span>0 PII Leaks</span>
            <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[11px]">
              Tier 1 Immutable
            </Badge>
          </CardContent>
        </Card>
      </div>

      {/* Active Channels & Routing State */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-2 border-border/70">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <Radio className="h-5 w-5 text-primary" />
                  Active Channel Orchestration
                </CardTitle>
                <CardDescription>
                  Normalized message pipelines serving provider bookings across all supported transports.
                </CardDescription>
              </div>
              <Badge variant="secondary" className="font-mono text-xs">
                Current Channel: {activeChannel.toUpperCase()}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="flex items-start gap-3 p-3.5 rounded-lg border bg-card/60 hover:bg-card transition-colors">
                <div className="h-9 w-9 rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
                  <MessageSquare className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-medium">SMS (Twilio / MessageMedia)</h4>
                    <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Bidirectional conversational SMS with automatic link generation and arrival notifications.
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <Badge variant="outline" className="text-[10px] py-0">Active Route</Badge>
                    <span className="text-[11px] text-muted-foreground">392 messages today</span>
                  </div>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3.5 rounded-lg border bg-card/60 hover:bg-card transition-colors">
                <div className="h-9 w-9 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
                  <Radio className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-medium">WhatsApp Cloud API</h4>
                    <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Rich messaging with template approvals, location pins, and quick-reply action buttons.
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <Badge variant="outline" className="text-[10px] py-0">Active Route</Badge>
                    <span className="text-[11px] text-muted-foreground">214 messages today</span>
                  </div>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3.5 rounded-lg border bg-card/60 hover:bg-card transition-colors">
                <div className="h-9 w-9 rounded-md bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center shrink-0">
                  <Cpu className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-medium">Webchat Booking Widget</h4>
                    <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Embedded portal assistant with zero-latency streaming and real-time slot preview.
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <Badge variant="outline" className="text-[10px] py-0">Active Route</Badge>
                    <span className="text-[11px] text-muted-foreground">580 messages today</span>
                  </div>
                </div>
              </div>

              <div className="flex items-start gap-3 p-3.5 rounded-lg border bg-card/60 hover:bg-card transition-colors">
                <div className="h-9 w-9 rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-medium">Simulator Sandbox</h4>
                    <span className="flex h-2 w-2 rounded-full bg-blue-500" />
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Synthetic test bench with instant multi-tier prompt inspection and server-bound tool validation.
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <Badge variant="outline" className="text-[10px] py-0">Dev & QA</Badge>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-5 px-1.5 text-[11px] text-primary hover:text-primary"
                      onClick={() => onNavigateTab('simulator')}
                    >
                      Open Simulator <ArrowRight className="ml-1 h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Readiness Checklist */}
        <Card className="border-border/70">
          <CardHeader>
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
              Runtime Readiness
            </CardTitle>
            <CardDescription>
              {selectedProvider?.id ? `Scoping: ${selectedProvider.name}` : 'Scoping: Tenant Default'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {readinessChecklist.map((check, idx) => (
              <div key={idx} className="flex items-center justify-between p-2 rounded-md bg-muted/40 text-xs">
                <div className="flex items-center gap-2 min-w-0">
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                  <span className="font-medium truncate">{check.title}</span>
                </div>
                <Badge variant="secondary" className="text-[10px] shrink-0 font-mono">
                  {check.tier}
                </Badge>
              </div>
            ))}

            <div className="pt-2">
              <Button
                variant="outline"
                className="w-full text-xs justify-between"
                onClick={() => onNavigateTab('prompt-composer')}
              >
                <span>Edit Prompt & Style Lab</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bottom Section: Rapid Navigation Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <Card
          className="cursor-pointer hover:border-primary/50 transition-all hover:shadow-sm"
          onClick={() => onNavigateTab('prompt-composer')}
        >
          <CardContent className="p-4 flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-sm font-semibold">10-Tier Composer</h4>
              <p className="text-xs text-muted-foreground">Inspect safety layers & tune Style Lab traits.</p>
            </div>
          </CardContent>
        </Card>

        <Card
          className="cursor-pointer hover:border-primary/50 transition-all hover:shadow-sm"
          onClick={() => onNavigateTab('example-library')}
        >
          <CardContent className="p-4 flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-sm font-semibold">Example Library</h4>
              <p className="text-xs text-muted-foreground">Manage approved conversational style pairs.</p>
            </div>
          </CardContent>
        </Card>

        <Card
          className="cursor-pointer hover:border-primary/50 transition-all hover:shadow-sm"
          onClick={() => onNavigateTab('variables-tools')}
        >
          <CardContent className="p-4 flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center shrink-0">
              <Zap className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-sm font-semibold">Live Tool Catalog</h4>
              <p className="text-xs text-muted-foreground">Inspect 5 server-enforced binding contracts.</p>
            </div>
          </CardContent>
        </Card>

        <Card
          className="cursor-pointer hover:border-primary/50 transition-all hover:shadow-sm"
          onClick={() => onNavigateTab('evaluation-safety')}
        >
          <CardContent className="p-4 flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-sm font-semibold">Safety Benchmarks</h4>
              <p className="text-xs text-muted-foreground">Run injection & travel edge case suites.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
