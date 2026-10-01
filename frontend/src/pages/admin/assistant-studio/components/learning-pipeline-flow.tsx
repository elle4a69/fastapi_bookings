import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowRight,
  Database,
  Network,
  Cpu,
  Zap,
  Activity,
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  Clock,
  Sparkles,
  Radio,
} from 'lucide-react';
import type { PipelineStatusData } from '../types';

interface LearningPipelineFlowProps {
  pipelineData: PipelineStatusData | null;
  isLoading: boolean;
  selectedStageId: number | null;
  onSelectStage: (stageId: number | null) => void;
  onRefresh: () => void;
}

export const LearningPipelineFlow: React.FC<LearningPipelineFlowProps> = ({
  pipelineData,
  isLoading,
  selectedStageId,
  onSelectStage,
  onRefresh,
}) => {
  const qc = pipelineData?.queue_counters || {
    pending_curation: 0,
    active_memories: 0,
    pending_projections: 0,
    neo4j_node_count: 0,
    redis_cache_hit_ratio: 0,
    dead_letters: 0,
  };

  const stageIcons: Record<number, React.ElementType> = {
    1: Radio,
    2: Sparkles,
    3: Database,
    4: Cpu,
    5: Network,
    6: Zap,
  };

  return (
    <div className="space-y-5">
      {/* Top Telemetry Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <Card className="border-border/60 bg-card/60 shadow-xs">
          <CardContent className="p-3">
            <div className="flex items-center justify-between text-muted-foreground text-xs">
              <span>Pending Curation</span>
              <Clock className="h-3.5 w-3.5 text-amber-500" />
            </div>
            <div className="text-xl font-bold font-mono mt-1 text-foreground">
              {qc.pending_curation}
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">Stage 1 & 2 Queue</div>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/60 shadow-xs">
          <CardContent className="p-3">
            <div className="flex items-center justify-between text-muted-foreground text-xs">
              <span>Active Memories</span>
              <Database className="h-3.5 w-3.5 text-emerald-500" />
            </div>
            <div className="text-xl font-bold font-mono mt-1 text-foreground">
              {qc.active_memories}
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">Relational Authority</div>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/60 shadow-xs">
          <CardContent className="p-3">
            <div className="flex items-center justify-between text-muted-foreground text-xs">
              <span>Pending Proj.</span>
              <Cpu className="h-3.5 w-3.5 text-blue-500" />
            </div>
            <div className="text-xl font-bold font-mono mt-1 text-foreground">
              {qc.pending_projections}
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">Outbox Worker Queue</div>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/60 shadow-xs">
          <CardContent className="p-3">
            <div className="flex items-center justify-between text-muted-foreground text-xs">
              <span>Graph Nodes</span>
              <Network className="h-3.5 w-3.5 text-indigo-500" />
            </div>
            <div className="text-xl font-bold font-mono mt-1 text-foreground">
              {qc.neo4j_node_count}
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">Neo4j Epistemic Graph</div>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/60 shadow-xs">
          <CardContent className="p-3">
            <div className="flex items-center justify-between text-muted-foreground text-xs">
              <span>Cache Hit Ratio</span>
              <Zap className="h-3.5 w-3.5 text-amber-500" />
            </div>
            <div className="text-xl font-bold font-mono mt-1 text-foreground">
              {Math.round(qc.redis_cache_hit_ratio * 100)}%
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">
              Epoch #{pipelineData?.redis_epoch ?? 1}
            </div>
          </CardContent>
        </Card>

        <Card className={`shadow-xs ${qc.dead_letters > 0 ? 'border-destructive/40 bg-destructive/5' : 'border-border/60 bg-card/60'}`}>
          <CardContent className="p-3">
            <div className="flex items-center justify-between text-muted-foreground text-xs">
              <span>Dead Letters</span>
              <AlertTriangle className={`h-3.5 w-3.5 ${qc.dead_letters > 0 ? 'text-destructive' : 'text-muted-foreground'}`} />
            </div>
            <div className={`text-xl font-bold font-mono mt-1 ${qc.dead_letters > 0 ? 'text-destructive' : 'text-foreground'}`}>
              {qc.dead_letters}
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">DLQ / Retry Exceeded</div>
          </CardContent>
        </Card>
      </div>

      {/* Pipeline 6-Stage Interactive Visualizer */}
      <Card className="border-border shadow-xs overflow-hidden">
        <div className="p-4 border-b bg-muted/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              <h3 className="font-semibold text-sm">Autonomous Learning Pipeline</h3>
              <Badge variant="outline" className="text-[10px] font-mono">
                Master Spec 54 Lifecycle
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              End-to-end 6-stage evolutionary pipeline from raw conversation trigger to low-latency Redis cache injection.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {selectedStageId !== null && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onSelectStage(null)}
                className="h-7 text-xs text-muted-foreground"
              >
                Clear Stage Filter
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={onRefresh}
              disabled={isLoading}
              className="h-7 text-xs gap-1"
            >
              <RefreshCw className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        <CardContent className="p-4 sm:p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-3 relative">
            {pipelineData?.stages?.map((stage, idx) => {
              const Icon = stageIcons[stage.stage_id] || Activity;
              const isSelected = selectedStageId === stage.stage_id;
              const isWarning = stage.status === 'warning' || (stage.stage_id === 4 && qc.dead_letters > 0);
              const isError = stage.status === 'error';

              return (
                <div
                  key={stage.stage_id}
                  onClick={() => onSelectStage(isSelected ? null : stage.stage_id)}
                  className={`group relative p-3.5 rounded-xl border text-left cursor-pointer transition-all duration-200 ${
                    isSelected
                      ? 'border-primary ring-2 ring-primary/20 bg-primary/[0.04] shadow-sm'
                      : 'border-border/70 hover:border-primary/50 hover:bg-muted/40 bg-card'
                  }`}
                >
                  {/* Stage Number Badge */}
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold font-mono uppercase tracking-wider text-muted-foreground">
                      Stage 0{stage.stage_id}
                    </span>
                    <Badge
                      variant="outline"
                      className={`text-[9px] px-1.5 py-0 font-mono capitalize ${
                        isError
                          ? 'border-destructive text-destructive bg-destructive/10'
                          : isWarning
                          ? 'border-amber-500 text-amber-600 bg-amber-500/10'
                          : stage.pending_count > 0
                          ? 'border-blue-500 text-blue-600 bg-blue-500/10'
                          : 'border-emerald-500/40 text-emerald-600 bg-emerald-500/10'
                      }`}
                    >
                      {isError ? 'Error' : isWarning ? 'Warning' : stage.pending_count > 0 ? `${stage.pending_count} Queued` : 'Healthy'}
                    </Badge>
                  </div>

                  {/* Icon & Title */}
                  <div className="flex items-center gap-2 mb-1.5">
                    <div className={`p-1.5 rounded-md ${
                      isSelected
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground group-hover:text-primary group-hover:bg-primary/10'
                    }`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="font-semibold text-xs text-foreground truncate">
                      {stage.name}
                    </div>
                  </div>

                  {/* Description / Subtext */}
                  <div className="text-[11px] text-muted-foreground line-clamp-2 mt-1">
                    {stage.stage_id === 1 && 'Conversations, Tool Output & Admin Input'}
                    {stage.stage_id === 2 && 'Dynamic leak scrubbing & PII stripping'}
                    {stage.stage_id === 3 && 'PostgreSQL CuratedMemory durable authority'}
                    {stage.stage_id === 4 && 'Asynchronous outbox with lease timeouts'}
                    {stage.stage_id === 5 && 'Neo4j / Graphiti typed epistemic nodes'}
                    {stage.stage_id === 6 && 'Dual-epoch Redis invalidation & injection'}
                  </div>

                  {/* Footnote details */}
                  <div className="mt-3 pt-2 border-t border-border/50 flex items-center justify-between text-[10px] font-mono text-muted-foreground">
                    <span>Processed:</span>
                    <span className="font-semibold text-foreground">{stage.total_processed}</span>
                  </div>

                  {/* Connecting Arrow for lg screens */}
                  {idx < 5 && (
                    <div className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 text-muted-foreground/40 pointer-events-none">
                      <ArrowRight className="h-3 w-3" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Active Stage Filter Info Banner */}
          {selectedStageId !== null && (
            <div className="mt-4 p-3 rounded-lg bg-primary/[0.04] border border-primary/20 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-primary shrink-0" />
                <span>
                  Filtering active view to <strong>Stage 0{selectedStageId}: {pipelineData?.stages?.find(s => s.stage_id === selectedStageId)?.name}</strong>.
                  Displaying relevant memories, graph entities, and review proposals.
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onSelectStage(null)}
                className="h-6 text-[11px] shrink-0"
              >
                Reset Filter
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
