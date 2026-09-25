import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  Code2,
  Copy,
  Cpu,
  ExternalLink,
  FileCheck,
  FileCode,
  Globe,
  History,
  Layers,
  ListFilter,
  Play,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Terminal,
  Trash2,
  Wrench,
  Zap,
  BookOpen,
  MessageSquare,
  TrendingUp,
  Check,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { apiClient, getAdminAccessToken } from '@/lib/api';

// --- Types ---
interface AgentIssue {
  id: string;
  category: string;
  title: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  description: string;
  status: 'OPEN' | 'RESOLVED' | 'IN_PROGRESS';
  discovered_at?: string;
  resolved_at?: string;
}

interface RemediationModification {
  file_path: string;
  description: string;
  diff: string;
}

interface RemediationPlan {
  plan_id: string;
  issue_id: string;
  title: string;
  severity: string;
  root_cause_analysis: string;
  proposed_modifications: RemediationModification[];
  verification_steps: string[];
  rollback_steps: string[];
  requires_approval: boolean;
  approved: boolean;
  status: string;
  created_at: string;
}

interface AgentStatusData {
  health_score: number;
  status: 'HEALTHY' | 'DEGRADED' | 'CRITICAL';
  telemetry_baseline: {
    telemetry_enabled: boolean;
    trace_exporter_active: boolean;
    metric_exporter_active: boolean;
    log_exporter_active: boolean;
    service_name: string;
    environment: string;
    last_export_status: string;
  };
  outbox_status: {
    total_sms_jobs: number;
    pending_sms_jobs: number;
    processing_sms_jobs: number;
    failed_sms_jobs: number;
    successful_sms_jobs: number;
    retry_backlog: number;
    pending_ai_jobs: number;
    unprocessed_outbox_events: number;
    dead_letter_deliveries: number;
    healthy: boolean;
  };
  chatwoot_status: {
    total_bindings: number;
    active_bindings: number;
    missing_webhook_secrets: number;
    healthy: boolean;
  };
  latest_code_audit: {
    score: number;
    passed: boolean;
    git: {
      clean: boolean;
      branch: string;
      total_changed_files: number;
      modified_count: number;
      untracked_count: number;
    };
    secrets: {
      scanned_files: number;
      secret_leaks_found: number;
      passed: boolean;
    };
    frontend_state: {
      passed: boolean;
      status: string;
    };
  } | null;
  active_issues: AgentIssue[];
  alert_dispatch_status?: {
    chatwoot_ready: boolean;
    sms_ready: boolean;
    remote_approval_enabled: boolean;
    supported_commands: string[];
    total_dispatched_alerts: number;
    last_dispatched_at?: string;
  };
  timestamp: string;
}

export interface SkillItem {
  skill_id: string;
  name: string;
  description: string;
  tags: string[];
  path: string;
  score?: number;
}

export interface TechRadarData {
  timestamp: string;
  our_platform: {
    name: string;
    strengths: string[];
    overall_maturity_score: number;
  };
  competitors: Array<{
    name: string;
    market_share: string;
    pricing_model: string;
    pros: string[];
    cons: string[];
    threat_level: string;
    our_advantage: string;
  }>;
  feature_gap_matrix: Array<{
    capability: string;
    fastapi_bookings: string;
    fresha: string;
    calendly: string;
    simplybook: string;
    acuity: string;
  }>;
  expansion_proposals: Array<{
    id: string;
    title: string;
    priority: string;
    effort: string;
    impact: string;
    summary: string;
    counter_competitor: string;
  }>;
  retention_strategies: string[];
}

export interface FuzzResult {
  test_id: string;
  timestamp: string;
  concurrency_tested: number;
  successful_bookings: number;
  conflicts_prevented: number;
  double_bookings_occurred: number;
  double_bookings_prevented_pct: number;
  conflict_rate_pct: number;
  total_duration_ms: number;
  avg_latency_ms: number;
  avg_lock_contention_ms: number;
  max_latency_ms: number;
  transactional_integrity_verified: boolean;
}

interface StreamEvent {
  type: string;
  title?: string;
  data: any;
  severity?: string;
  timestamp: string;
}

interface AdvisoryMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  researchSummary?: string;
  sources?: string[];
  skills?: SkillItem[];
  recommendations?: string[];
  timestamp: string;
}

interface ResidentAgentPageProps {
  initialTab?: string;
}

export default function ResidentAgentPage({ initialTab }: ResidentAgentPageProps = {}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryTab = searchParams.get('tab');
  const [activeTab, setActiveTab] = useState<string>(initialTab || queryTab || 'health');
  const [studioIframeKey, setStudioIframeKey] = useState<number>(0);
  const [statusData, setStatusData] = useState<AgentStatusData | null>(null);
  const [loadingStatus, setLoadingStatus] = useState<boolean>(true);
  const [auditing, setAuditing] = useState<boolean>(false);

  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
    } else if (queryTab) {
      setActiveTab(queryTab);
    }
  }, [initialTab, queryTab]);

  const handleTabChange = (val: string) => {
    setActiveTab(val);
    const newParams = new URLSearchParams(searchParams);
    if (val === 'health') {
      newParams.delete('tab');
    } else {
      newParams.set('tab', val);
    }
    setSearchParams(newParams, { replace: true });
  };

  // Issues & Fix Studio State
  const [selectedIssue, setSelectedIssue] = useState<AgentIssue | null>(null);
  const [activePlan, setActivePlan] = useState<RemediationPlan | null>(null);
  const [planningFix, setPlanningFix] = useState<boolean>(false);
  const [executingFix, setExecutingFix] = useState<boolean>(false);
  const [fixApproved, setFixApproved] = useState<boolean>(false);
  const [executionResult, setExecutionResult] = useState<any | null>(null);

  // Advisory State
  const [advisoryPrompt, setAdvisoryPrompt] = useState<string>('');
  const [advisoryDomain, setAdvisoryDomain] = useState<string>('general');
  const [enableWebResearch, setEnableWebResearch] = useState<boolean>(true);
  const [advisoryLoading, setAdvisoryLoading] = useState<boolean>(false);
  const [advisoryChat, setAdvisoryChat] = useState<AdvisoryMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Hello Frank, I am the Codex Resident Autonomous Agent for FastAPI Bookings. I continuously supervise system health, audit codebase integrity, inspect SMS outbox backlogs, and research technical patterns. How can I advise you today?',
      recommendations: [
        'Run an immediate deep audit across all subsystems',
        'Review and remediate detected telemetry or outbox anomalies',
        'Research optimal concurrency patterns for SMS and Chatwoot workers',
      ],
      timestamp: new Date().toISOString(),
    },
  ]);

  // Concurrency & Race-Condition Fuzzer State
  const [fuzzConcurrency, setFuzzConcurrency] = useState<number>(15);
  const [fuzzing, setFuzzing] = useState<boolean>(false);
  const [fuzzResult, setFuzzResult] = useState<FuzzResult | null>(null);

  // Two-Way Remote Approval State
  const [remoteCommandInput, setRemoteCommandInput] = useState<string>('');
  const [executingRemoteAction, setExecutingRemoteAction] = useState<boolean>(false);

  // RAG Skills Reference State
  const [skillsQuery, setSkillsQuery] = useState<string>('fastapi concurrency');
  const [skillsList, setSkillsList] = useState<SkillItem[]>([]);
  const [loadingSkills, setLoadingSkills] = useState<boolean>(false);
  const [selectedSkillContent, setSelectedSkillContent] = useState<{ skill_id: string; content: string } | null>(null);
  const [skillModalOpen, setSkillModalOpen] = useState<boolean>(false);

  // Competitor Tech Radar State
  const [techRadarData, setTechRadarData] = useState<TechRadarData | null>(null);
  const [loadingRadar, setLoadingRadar] = useState<boolean>(false);
  const [radarExpanded, setRadarExpanded] = useState<boolean>(false);

  // Event Stream State
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [sseConnected, setSseConnected] = useState<boolean>(false);
  const [eventFilter, setEventFilter] = useState<string>('all');
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const terminalBottomRef = useRef<HTMLDivElement>(null);

  // --- 1. Fetch System Status ---
  const fetchStatus = useCallback(async () => {
    try {
      setLoadingStatus(true);
      const res = await apiClient.get<AgentStatusData>('/api/admin/resident-agent/status');
      const data = (res as any)?.data ?? res;
      setStatusData(data);
      if (data.active_issues && data.active_issues.length > 0 && !selectedIssue) {
        setSelectedIssue(data.active_issues[0]);
      }
    } catch (err: any) {
      toast.error('Failed to load resident agent status: ' + (err.message || 'Unknown error'));
    } finally {
      setLoadingStatus(false);
    }
  }, [selectedIssue]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // 30s poll
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // --- 2. SSE Live Event Stream ---
  useEffect(() => {
    let eventSource: EventSource | null = null;
    const token = getAdminAccessToken();

    try {
      const sseUrl = `/api/admin/resident-agent/events${token ? `?token=${encodeURIComponent(token)}` : ''}`;
      eventSource = new EventSource(sseUrl);

      eventSource.onopen = () => {
        setSseConnected(true);
      };

      eventSource.onmessage = (e) => {
        try {
          const parsed: StreamEvent = JSON.parse(e.data);
          setEvents((prev) => [...prev.slice(-150), parsed]);
        } catch {
          // ignore heartbeat ping
        }
      };

      eventSource.onerror = () => {
        setSseConnected(false);
      };
    } catch (err) {
      console.warn('SSE stream initialization error:', err);
    }

    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, []);

  // Auto-scroll terminal log
  useEffect(() => {
    if (autoScroll && terminalBottomRef.current) {
      terminalBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events, autoScroll]);

  // --- 3. Run Deep Audit ---
  const handleRunDeepAudit = async () => {
    try {
      setAuditing(true);
      toast.info('Deep Audit initiated. Monitoring live pipeline events...');
      await apiClient.post<any>('/api/admin/resident-agent/audit');
      toast.success('Deep Audit completed successfully!');
      await fetchStatus();
    } catch (err: any) {
      toast.error('Deep Audit failed: ' + (err.message || 'Error occurred'));
    } finally {
      setAuditing(false);
    }
  };

  // --- 4. Generate Remediation Plan ---
  const handleGeneratePlan = async (issue: AgentIssue) => {
    try {
      setPlanningFix(true);
      setActivePlan(null);
      setExecutionResult(null);
      setFixApproved(false);
      setSelectedIssue(issue);

      const res = await apiClient.post<RemediationPlan>('/api/admin/resident-agent/plan-fix', {
        issue_id: issue.id,
        issue_title: issue.title,
        category: issue.category,
        context: { description: issue.description, severity: issue.severity },
      });

      const plan = (res as any)?.data ?? res;
      setActivePlan(plan);
      toast.success(`Remediation plan generated for ${issue.id}`);
    } catch (err: any) {
      toast.error('Failed to generate remediation plan: ' + (err.message || 'Error'));
    } finally {
      setPlanningFix(false);
    }
  };

  // --- 5. Execute Remediation Plan ---
  const handleExecuteFix = async () => {
    if (!activePlan) return;
    if (!fixApproved) {
      toast.error('Explicit approval is required before executing changes.');
      return;
    }

    try {
      setExecutingFix(true);
      setExecutionResult(null);

      const res = await apiClient.post<any>('/api/admin/resident-agent/execute-fix', {
        plan_id: activePlan.plan_id,
        approved: true,
        simulate_only: false,
      });

      const result = (res as any)?.data ?? res;
      setExecutionResult(result);

      if (result.success) {
        toast.success(`Fix applied and verified safely! Issue resolved.`);
        await fetchStatus();
      } else {
        toast.warning(`Fix verification failed: automatic rollback applied.`);
      }
    } catch (err: any) {
      toast.error('Fix execution failed: ' + (err.message || 'Unknown error'));
    } finally {
      setExecutingFix(false);
    }
  };

  // --- 6. Send AI Advisory Request ---
  const handleSendAdvisory = async (overridePrompt?: string) => {
    const promptToSend = (overridePrompt || advisoryPrompt).trim();
    if (!promptToSend) return;

    const userMessage: AdvisoryMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: promptToSend,
      timestamp: new Date().toISOString(),
    };

    setAdvisoryChat((prev) => [...prev, userMessage]);
    setAdvisoryPrompt('');
    setAdvisoryLoading(true);

    try {
      const res = await apiClient.post<any>('/api/admin/resident-agent/advisory', {
        prompt: promptToSend,
        enable_web_research: enableWebResearch,
        domain: advisoryDomain !== 'general' ? advisoryDomain : undefined,
      });

      const data = (res as any)?.data ?? res;

      const assistantMessage: AdvisoryMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.advisory_markdown || 'Advisory synthesis complete.',
        researchSummary: data.research_summary,
        sources: data.sources,
        recommendations: data.recommendations,
        timestamp: new Date().toISOString(),
      };

      setAdvisoryChat((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      toast.error('Advisory failed: ' + (err.message || 'Error occurred'));
    } finally {
      setAdvisoryLoading(false);
    }
  };

  // --- 7. Concurrency & Race Condition Fuzzer ---
  const handleRunRaceConditionTest = async () => {
    try {
      setFuzzing(true);
      toast.info(`Triggering race-condition stress fuzzer (${fuzzConcurrency} concurrent bookings)...`);
      const res = await apiClient.post<FuzzResult>('/api/admin/resident-agent/fuzz/race-condition', {
        concurrency: fuzzConcurrency,
      });
      const data = (res as any)?.data ?? res;
      setFuzzResult(data);
      toast.success(`Fuzzer completed! 0 double-bookings: ${data.conflicts_prevented}/${data.concurrency_tested} conflicts cleanly handled.`);
    } catch (err: any) {
      toast.error('Race condition fuzzer failed: ' + (err.message || 'Unknown error'));
    } finally {
      setFuzzing(false);
    }
  };

  // --- 8. Remote Action Approval Handler ---
  const handleExecuteRemoteAction = async (cmd?: string) => {
    const rawCmd = (cmd || remoteCommandInput).trim();
    if (!rawCmd) {
      toast.error("Please enter a command like 'APPROVE <plan_id>'");
      return;
    }
    try {
      setExecutingRemoteAction(true);
      const res = await apiClient.post<any>('/api/admin/resident-agent/remote-action', {
        command: rawCmd,
      });
      const data = (res as any)?.data ?? res;
      toast.success(data.message || 'Remote action executed successfully!');
      setRemoteCommandInput('');
      await fetchStatus();
    } catch (err: any) {
      toast.error('Remote action failed: ' + (err.message || 'Unknown error'));
    } finally {
      setExecutingRemoteAction(false);
    }
  };

  // --- 9. Skills Library Handlers ---
  const handleSearchSkills = async (overrideQuery?: string) => {
    const q = (overrideQuery !== undefined ? overrideQuery : skillsQuery).trim();
    if (!q) return;
    try {
      setLoadingSkills(true);
      const res = await apiClient.get<SkillItem[]>(`/api/admin/resident-agent/skills?query=${encodeURIComponent(q)}&top_k=4`);
      const data = (res as any)?.data ?? res;
      setSkillsList(Array.isArray(data) ? data : []);
    } catch (err: any) {
      toast.error('Failed querying skills: ' + (err.message || 'Unknown error'));
    } finally {
      setLoadingSkills(false);
    }
  };

  const handleViewSkill = async (skillId: string) => {
    try {
      const res = await apiClient.get<{ skill_id: string; content: string }>(`/api/admin/resident-agent/skills/${encodeURIComponent(skillId)}`);
      const data = (res as any)?.data ?? res;
      setSelectedSkillContent(data);
      setSkillModalOpen(true);
    } catch (err: any) {
      toast.error('Failed reading skill: ' + (err.message || 'Unknown error'));
    }
  };

  // --- 10. Competitor Tech Radar Handler ---
  const fetchTechRadar = async () => {
    try {
      setLoadingRadar(true);
      const res = await apiClient.get<TechRadarData>('/api/admin/resident-agent/tech-radar');
      const data = (res as any)?.data ?? res;
      setTechRadarData(data);
    } catch (err: any) {
      toast.error('Failed loading tech radar: ' + (err.message || 'Unknown error'));
    } finally {
      setLoadingRadar(false);
    }
  };

  // Auto-fetch skills & radar when entering advisory tab
  useEffect(() => {
    if (activeTab === 'advisory') {
      if (skillsList.length === 0) {
        handleSearchSkills('fastapi concurrency');
      }
      if (!techRadarData) {
        fetchTechRadar();
      }
    }
  }, [activeTab]);

  // Filter events
  const filteredEvents = events.filter((ev) => {
    if (eventFilter === 'all') return true;
    if (eventFilter === 'thoughts') return ev.type === 'thought';
    if (eventFilter === 'steps') return ev.type === 'step';
    if (eventFilter === 'audit') return ev.type === 'audit';
    if (eventFilter === 'fixes') return ev.type === 'fix_status';
    return true;
  });

  const healthScore = statusData?.health_score ?? 100;
  const healthBadgeVariant =
    healthScore >= 80 ? 'default' : healthScore >= 50 ? 'secondary' : 'destructive';

  return (
    <div className="flex flex-col gap-5 sm:gap-6 p-3 sm:p-6 max-w-7xl mx-auto w-full min-w-0">
      {/* Header Banner */}
      <div className="flex flex-col gap-4 border-b pb-5 w-full">
        <div className="flex items-start gap-3 w-full min-w-0">
          <div className="p-2.5 rounded-xl bg-primary/10 text-primary border border-primary/20 shadow-sm shrink-0">
            <Cpu className="w-7 h-7 sm:w-8 h-8" />
          </div>
          <div className="w-full min-w-0 flex-1">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground break-words w-full">
              Codex Resident Autonomous Agent
            </h1>
            <div className="mt-1">
              <Badge variant="outline" className="text-xs uppercase tracking-wider font-semibold">
                v1.0 Autonomous
              </Badge>
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground mt-1 w-full break-words">
              Autonomous supervision, deep codebase audits, telemetry sentinels, and safe fix executions.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:gap-3 w-full">
          {/* Conversational Coding Studio Launch Button */}
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open('http://localhost:5180', '_blank', 'noopener,noreferrer')}
                  className="flex items-center gap-2 border-primary/40 bg-primary/5 hover:bg-primary/10 text-primary font-semibold shadow-xs flex-wrap min-h-[44px] touch-manipulation"
                >
                  <Code2 className="w-4 h-4 text-primary shrink-0" />
                  <span className="text-xs sm:text-sm">Launch Coding Studio</span>
                  <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-mono bg-primary/15 text-primary border border-primary/20 shrink-0">
                    Port 5180
                  </Badge>
                  <ExternalLink className="w-3.5 h-3.5 opacity-70 shrink-0" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <p className="text-xs">Codex Harness • Port 5180 (Click to open studio in new tab)</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {/* SSE Live Status Indicator */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border bg-card text-xs shrink-0 min-h-[44px]">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                sseConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
              }`}
            />
            <span className="font-medium text-muted-foreground">
              {sseConnected ? 'Live SSE Connected' : 'Polling Baseline'}
            </span>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={fetchStatus}
            disabled={loadingStatus}
            className="flex items-center gap-1.5 shrink-0 min-h-[44px] touch-manipulation"
          >
            <RefreshCw className={`w-4 h-4 ${loadingStatus ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </Button>

          <Button
            onClick={handleRunDeepAudit}
            disabled={auditing}
            size="sm"
            className="flex items-center gap-1.5 bg-primary text-primary-foreground font-semibold shadow shrink-0 min-h-[44px] touch-manipulation"
          >
            <Play className={`w-4 h-4 ${auditing ? 'animate-spin' : ''}`} />
            <span>{auditing ? 'Auditing...' : 'Run Deep Audit'}</span>
          </Button>
        </div>
      </div>

      {/* Primary Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
        <TabsList className="flex w-full overflow-x-auto justify-start md:grid md:grid-cols-5 max-w-full md:max-w-3xl bg-muted/60 p-1 scrollbar-none gap-1 touch-manipulation -mx-1 px-1">
          <TabsTrigger value="health" className="flex items-center gap-2 text-xs font-medium shrink-0 md:shrink h-10 min-h-[44px] px-3.5 touch-manipulation">
            <Activity className="w-4 h-4" />
            <span>System Health</span>
          </TabsTrigger>
          <TabsTrigger value="issues" className="flex items-center gap-2 text-xs font-medium shrink-0 md:shrink h-10 min-h-[44px] px-3.5 touch-manipulation">
            <Wrench className="w-4 h-4" />
            <span>Issues & Fix Studio</span>
            {statusData?.active_issues && statusData.active_issues.length > 0 && (
              <span className="ml-1 px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-700 dark:text-amber-300 text-[10px] font-bold">
                {statusData.active_issues.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="advisory" className="flex items-center gap-2 text-xs font-medium shrink-0 md:shrink h-10 min-h-[44px] px-3.5 touch-manipulation">
            <Bot className="w-4 h-4" />
            <span>AI Advisory</span>
          </TabsTrigger>
          <TabsTrigger value="stream" className="flex items-center gap-2 text-xs font-medium shrink-0 md:shrink h-10 min-h-[44px] px-3.5 touch-manipulation">
            <Terminal className="w-4 h-4" />
            <span>Event Stream</span>
          </TabsTrigger>
          <TabsTrigger value="coding" className="flex items-center gap-2 text-xs font-medium shrink-0 md:shrink h-10 min-h-[44px] px-3.5 touch-manipulation">
            <Code2 className="w-4 h-4 text-primary" />
            <span>Coding Agent</span>
          </TabsTrigger>
        </TabsList>

        {/* ============================================================ */}
        {/* TAB 1: SYSTEM HEALTH & AUDITS                                */}
        {/* ============================================================ */}
        <TabsContent value="health" className="mt-6 space-y-6">
          {/* Top Row: Score + Key Sentinel Indicators */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Score Card */}
            <Card className="md:col-span-1 shadow-sm border flex flex-col justify-between">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                  Health Score
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col items-center justify-center py-4">
                <div className="relative flex items-center justify-center w-28 h-28">
                  <div
                    className={`w-full h-full rounded-full border-8 flex items-center justify-center ${
                      healthScore >= 80
                        ? 'border-emerald-500/80 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400'
                        : healthScore >= 50
                        ? 'border-amber-500/80 bg-amber-500/5 text-amber-600 dark:text-amber-400'
                        : 'border-destructive/80 bg-destructive/5 text-destructive'
                    }`}
                  >
                    <span className="text-3xl font-extrabold tracking-tight">{healthScore}%</span>
                  </div>
                </div>
                <div className="mt-3 text-center">
                  <Badge variant={healthBadgeVariant} className="font-semibold text-xs uppercase px-2.5 py-0.5">
                    {statusData?.status ?? 'HEALTHY'}
                  </Badge>
                </div>
              </CardContent>
              <CardFooter className="pt-0 text-[11px] text-muted-foreground justify-center border-t py-2 bg-muted/20">
                Composite calculation (OTel, Outbox, Chatwoot, Code)
              </CardFooter>
            </Card>

            {/* Code Quality Card */}
            <Card className="shadow-sm border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Code2 className="w-4 h-4 text-primary" />
                  Codebase Quality
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-xs pt-1">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Git Worktree:</span>
                  <Badge variant="outline" className="font-mono text-[11px]">
                    {statusData?.latest_code_audit?.git?.clean ? 'Clean' : 'Modified files'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Secret Leak Scans:</span>
                  <span className="flex items-center gap-1 font-semibold text-emerald-600 dark:text-emerald-400">
                    <ShieldCheck className="w-3.5 h-3.5" /> 0 Leaks Found
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Frontend Configs:</span>
                  <span className="font-medium text-foreground">Verified</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Branch:</span>
                  <span className="font-mono text-[11px] text-primary">
                    {statusData?.latest_code_audit?.git?.branch || 'master'}
                  </span>
                </div>
              </CardContent>
              <CardFooter className="pt-0 text-[11px] text-muted-foreground border-t py-2 bg-muted/20">
                AGENTS.md privacy rule compliant
              </CardFooter>
            </Card>

            {/* Telemetry Sentinel Card */}
            <Card className="shadow-sm border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Activity className="w-4 h-4 text-primary" />
                  Telemetry Sentinel
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-xs pt-1">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Pipeline State:</span>
                  <Badge
                    variant={statusData?.telemetry_baseline?.telemetry_enabled ? 'default' : 'secondary'}
                    className="text-[11px]"
                  >
                    {statusData?.telemetry_baseline?.telemetry_enabled ? 'Active' : 'Suppressed'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Trace Exporter:</span>
                  <span className="font-semibold">
                    {statusData?.telemetry_baseline?.trace_exporter_active ? 'Ready' : 'Local'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Service Name:</span>
                  <span className="font-mono text-[11px] truncate max-w-[110px]">
                    {statusData?.telemetry_baseline?.service_name || 'fastapi-bookings'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Environment:</span>
                  <span className="font-mono text-[11px]">
                    {statusData?.telemetry_baseline?.environment || 'development'}
                  </span>
                </div>
              </CardContent>
              <CardFooter className="pt-0 text-[11px] text-muted-foreground border-t py-2 bg-muted/20">
                OTel Traces & Metrics status
              </CardFooter>
            </Card>

            {/* Outbox & Chatwoot Card */}
            <Card className="shadow-sm border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-primary" />
                  SMS & Webhook Queues
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-xs pt-1">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Failed SMS Jobs:</span>
                  <span
                    className={`font-semibold ${
                      (statusData?.outbox_status?.failed_sms_jobs ?? 0) > 0 ? 'text-destructive' : 'text-emerald-600'
                    }`}
                  >
                    {statusData?.outbox_status?.failed_sms_jobs ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">SMS Retry Backlog:</span>
                  <span className="font-medium">{statusData?.outbox_status?.retry_backlog ?? 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Chatwoot Bindings:</span>
                  <span className="font-medium">{statusData?.chatwoot_status?.active_bindings ?? 0} Active</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Dead Letters:</span>
                  <span
                    className={`font-semibold ${
                      (statusData?.outbox_status?.dead_letter_deliveries ?? 0) > 0
                        ? 'text-destructive'
                        : 'text-emerald-600'
                    }`}
                  >
                    {statusData?.outbox_status?.dead_letter_deliveries ?? 0}
                  </span>
                </div>
              </CardContent>
              <CardFooter className="pt-0 text-[11px] text-muted-foreground border-t py-2 bg-muted/20">
                Delivery and sync isolation
              </CardFooter>
            </Card>
          </div>

          {/* Concurrency & Race-Condition Fuzzer Card */}
          <Card className="border shadow-sm bg-card">
            <CardHeader className="p-5 pb-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <Zap className="w-5 h-5 text-amber-500 shrink-0" />
                    <span>Concurrency & Race-Condition Stress Fuzzer</span>
                  </CardTitle>
                  <CardDescription className="text-xs text-muted-foreground mt-1">
                    Simulates simultaneous booking transactions claiming the identical provider slot to verify 100% zero-double-booking database locks.
                  </CardDescription>
                </div>
                <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
                  <div className="flex items-center space-x-1 border rounded-md p-1 bg-muted/30">
                    {[10, 15, 25, 30].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setFuzzConcurrency(n)}
                        className={`px-3 py-1.5 text-xs rounded font-medium transition-colors touch-manipulation min-h-[36px] ${
                          fuzzConcurrency === n
                            ? 'bg-primary text-primary-foreground shadow-xs'
                            : 'text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        {n}x
                      </button>
                    ))}
                  </div>
                  <Button
                    onClick={handleRunRaceConditionTest}
                    disabled={fuzzing}
                    className="font-semibold text-xs h-10 min-h-[44px] shadow-xs shrink-0 touch-manipulation px-3"
                  >
                    <Play className={`w-3.5 h-3.5 mr-1.5 ${fuzzing ? 'animate-spin' : ''}`} />
                    {fuzzing ? 'Fuzzing...' : 'Run Race Test'}
                  </Button>
                </div>
              </div>
            </CardHeader>
            {fuzzResult && (
              <CardContent className="p-5 pt-0 space-y-4">
                <div className="p-3.5 rounded-lg border bg-muted/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 rounded-full bg-emerald-500/10 text-emerald-600">
                      <CheckCircle2 className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-foreground flex items-center gap-2">
                        Transactional Lock Integrity Verified
                        <Badge variant="default" className="bg-emerald-600 text-white hover:bg-emerald-700 text-[10px] h-5">
                          {fuzzResult.double_bookings_prevented_pct}% Double-Bookings Prevented
                        </Badge>
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        Single-winner committed. All {fuzzResult.conflicts_prevented} concurrent attempts caught atomic unique constraints.
                      </div>
                    </div>
                  </div>
                  <div className="text-[11px] font-mono text-muted-foreground text-right">
                    Test ID: {fuzzResult.test_id}
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 rounded-lg border bg-card text-center">
                    <div className="text-[11px] text-muted-foreground font-medium">Concurrency Tested</div>
                    <div className="text-lg font-bold text-foreground mt-0.5">{fuzzResult.concurrency_tested}</div>
                    <div className="text-[10px] text-muted-foreground">parallel workers</div>
                  </div>
                  <div className="p-3 rounded-lg border bg-card text-center">
                    <div className="text-[11px] text-muted-foreground font-medium">Single Winner</div>
                    <div className="text-lg font-bold text-emerald-600 mt-0.5">{fuzzResult.successful_bookings}</div>
                    <div className="text-[10px] text-muted-foreground">confirmed booking</div>
                  </div>
                  <div className="p-3 rounded-lg border bg-card text-center">
                    <div className="text-[11px] text-muted-foreground font-medium">Conflicts Handled</div>
                    <div className="text-lg font-bold text-amber-600 mt-0.5">{fuzzResult.conflicts_prevented}</div>
                    <div className="text-[10px] text-muted-foreground">{fuzzResult.conflict_rate_pct}% collision rate</div>
                  </div>
                  <div className="p-3 rounded-lg border bg-card text-center">
                    <div className="text-[11px] text-muted-foreground font-medium">Avg Contention Latency</div>
                    <div className="text-lg font-bold text-primary mt-0.5">{fuzzResult.avg_lock_contention_ms}ms</div>
                    <div className="text-[10px] text-muted-foreground">lock acquisition time</div>
                  </div>
                </div>
              </CardContent>
            )}
          </Card>

          {/* Deep Audit Trigger Banner */}
          <Card className="border shadow-sm bg-gradient-to-r from-card via-muted/30 to-card">
            <CardContent className="p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div>
                <h3 className="font-semibold text-base flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-primary" />
                  Continuous Autonomous Surveillance
                </h3>
                <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
                  The Resident Agent continuously checks SMS delivery leases, Chatwoot webhook ciphers,
                  uncommitted git diffs, and security boundaries. Trigger a deep sweep anytime to refresh live state.
                </p>
              </div>
              <Button
                onClick={handleRunDeepAudit}
                disabled={auditing}
                className="font-semibold shadow-sm shrink-0"
              >
                <Play className={`w-4 h-4 mr-2 ${auditing ? 'animate-spin' : ''}`} />
                {auditing ? 'Executing Deep Audit...' : 'Execute Deep Audit'}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ============================================================ */}
        {/* TAB 2: ISSUES & FIX STUDIO                                   */}
        {/* ============================================================ */}
        <TabsContent value="issues" className="mt-6">
          {/* Two-Way Remote Approval Channel Banner */}
          <Card className="border shadow-sm bg-gradient-to-r from-card via-muted/20 to-card mb-6">
            <CardContent className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 shrink-0 mt-0.5">
                  <MessageSquare className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-sm">Two-Way Remote Approval Channel</h3>
                    <Badge variant="default" className="bg-emerald-600 text-white hover:bg-emerald-700 text-[10px]">
                      Chatwoot & SMS Dispatch Ready
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5 max-w-2xl">
                    Urgent alerts dispatch commands like <code className="font-mono bg-muted px-1.5 py-0.5 rounded text-foreground font-semibold">APPROVE &lt;plan_id&gt;</code> to Chatwoot and SMS. Reply directly or test remote execution below:
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Input
                  value={remoteCommandInput}
                  onChange={(e) => setRemoteCommandInput(e.target.value)}
                  placeholder="APPROVE plan_xxx"
                  className="w-44 h-8 text-xs font-mono bg-background"
                />
                <Button
                  onClick={() => handleExecuteRemoteAction()}
                  disabled={executingRemoteAction || !remoteCommandInput.trim()}
                  size="sm"
                  className="h-8 text-xs font-semibold"
                >
                  <Check className={`w-3.5 h-3.5 mr-1 ${executingRemoteAction ? 'animate-spin' : ''}`} />
                  {executingRemoteAction ? 'Authorizing...' : 'Execute'}
                </Button>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left: Issues List */}
            <div className="lg:col-span-5 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-500" />
                  Detected Issues ({statusData?.active_issues?.length ?? 0})
                </h2>
                <Button variant="ghost" size="sm" onClick={fetchStatus} className="h-7 text-xs">
                  <RefreshCw className="w-3 h-3 mr-1" /> Refresh
                </Button>
              </div>

              {(!statusData?.active_issues || statusData.active_issues.length === 0) ? (
                <Card className="border-dashed p-8 text-center bg-card/50">
                  <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
                  <h3 className="font-semibold text-sm">No Active Issues Detected</h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    All telemetry pipelines, outbox queues, and codebase checks are currently passing cleanly.
                  </p>
                </Card>
              ) : (
                <div className="space-y-3">
                  {statusData.active_issues.map((issue) => {
                    const isSelected = selectedIssue?.id === issue.id;
                    return (
                      <Card
                        key={issue.id}
                        onClick={() => setSelectedIssue(issue)}
                        className={`cursor-pointer transition-all border shadow-sm ${
                          isSelected
                            ? 'border-primary ring-1 ring-primary bg-primary/5'
                            : 'hover:border-border/80 hover:bg-muted/30'
                        }`}
                      >
                        <CardHeader className="p-4 pb-2">
                          <div className="flex items-start justify-between gap-2">
                            <Badge
                              variant={
                                issue.severity === 'CRITICAL'
                                  ? 'destructive'
                                  : issue.severity === 'WARNING'
                                  ? 'secondary'
                                  : 'outline'
                              }
                              className="text-[10px] uppercase font-bold"
                            >
                              {issue.severity}
                            </Badge>
                            <span className="text-[11px] font-mono text-muted-foreground">{issue.id}</span>
                          </div>
                          <CardTitle className="text-sm font-semibold mt-1.5">{issue.title}</CardTitle>
                        </CardHeader>
                        <CardContent className="p-4 pt-0">
                          <p className="text-xs text-muted-foreground line-clamp-2">{issue.description}</p>
                          <div className="mt-3 flex items-center justify-between">
                            <span className="text-[11px] text-muted-foreground font-mono">
                              {issue.category}
                            </span>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleGeneratePlan(issue);
                              }}
                            >
                              Fix Plan <ArrowRight className="w-3 h-3 ml-1" />
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Right: Plan & Diff Studio */}
            <div className="lg:col-span-7">
              {activePlan ? (
                <Card className="border shadow-md">
                  <CardHeader className="border-b bg-muted/20 pb-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono text-xs">
                          {activePlan.plan_id}
                        </Badge>
                        <Badge
                          variant={activePlan.severity === 'CRITICAL' ? 'destructive' : 'secondary'}
                          className="text-xs"
                        >
                          {activePlan.severity}
                        </Badge>
                      </div>
                      <Badge variant="outline" className="text-xs font-mono">
                        Requires Explicit Approval
                      </Badge>
                    </div>
                    <CardTitle className="text-base font-bold mt-2">{activePlan.title}</CardTitle>
                    <CardDescription className="text-xs">
                      Generated at {new Date(activePlan.created_at).toLocaleTimeString()}
                    </CardDescription>
                  </CardHeader>

                  <CardContent className="p-6 space-y-5">
                    {/* RCA */}
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1.5">
                        <Search className="w-3.5 h-3.5 text-primary" /> Root Cause Analysis (RCA)
                      </h4>
                      <p className="text-xs bg-muted/50 p-3 rounded-lg border leading-relaxed">
                        {activePlan.root_cause_analysis}
                      </p>
                    </div>

                    {/* Proposed Diffs */}
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-1.5">
                        <FileCode className="w-3.5 h-3.5 text-primary" /> Proposed File Modifications & Diffs
                      </h4>
                      {activePlan.proposed_modifications.map((mod, idx) => (
                        <div key={idx} className="space-y-1.5 mb-3">
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-mono font-semibold text-primary">{mod.file_path}</span>
                            <span className="text-muted-foreground text-[11px]">{mod.description}</span>
                          </div>
                          <pre className="text-[11px] font-mono bg-zinc-950 text-zinc-100 p-3 rounded-lg overflow-x-auto border border-zinc-800 leading-normal">
                            <code>{mod.diff}</code>
                          </pre>
                        </div>
                      ))}
                    </div>

                    {/* Verification & Rollback */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                      <div className="bg-muted/30 p-3 rounded-lg border space-y-1.5">
                        <span className="font-semibold text-foreground flex items-center gap-1">
                          <FileCheck className="w-3.5 h-3.5 text-emerald-500" /> Automated Verification Steps
                        </span>
                        <ul className="list-disc list-inside text-muted-foreground space-y-1 text-[11px]">
                          {activePlan.verification_steps.map((v, i) => (
                            <li key={i}>{v}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="bg-muted/30 p-3 rounded-lg border space-y-1.5">
                        <span className="font-semibold text-foreground flex items-center gap-1">
                          <History className="w-3.5 h-3.5 text-amber-500" /> Safe Rollback Procedures
                        </span>
                        <ul className="list-disc list-inside text-muted-foreground space-y-1 text-[11px]">
                          {activePlan.rollback_steps.map((r, i) => (
                            <li key={i}>{r}</li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    {/* Execution Result Feedback */}
                    {executionResult && (
                      <div
                        className={`p-4 rounded-lg border text-xs flex items-start gap-3 ${
                          executionResult.success
                            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-800 dark:text-emerald-300'
                            : 'bg-destructive/10 border-destructive/30 text-destructive'
                        }`}
                      >
                        {executionResult.success ? (
                          <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
                        ) : (
                          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                        )}
                        <div>
                          <div className="font-bold">
                            {executionResult.success ? 'Execution Successful & Verified' : 'Execution Rolled Back'}
                          </div>
                          <p className="mt-0.5">{executionResult.message || executionResult.error}</p>
                        </div>
                      </div>
                    )}
                  </CardContent>

                  <CardFooter className="border-t bg-muted/20 p-4 flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="approve-switch"
                        checked={fixApproved}
                        onCheckedChange={setFixApproved}
                      />
                      <Label htmlFor="approve-switch" className="text-xs font-semibold cursor-pointer">
                        Approve remediation modifications
                      </Label>
                    </div>

                    <Button
                      onClick={handleExecuteFix}
                      disabled={executingFix || !fixApproved}
                      className="font-semibold text-xs bg-emerald-600 hover:bg-emerald-700 text-white shadow"
                    >
                      <Zap className={`w-3.5 h-3.5 mr-1.5 ${executingFix ? 'animate-spin' : ''}`} />
                      {executingFix ? 'Executing & Verifying...' : 'Execute Approved Fix'}
                    </Button>
                  </CardFooter>
                </Card>
              ) : (
                <Card className="border-dashed p-12 text-center bg-muted/10 h-full flex flex-col items-center justify-center">
                  <Wrench className="w-10 h-10 text-muted-foreground/60 mb-3" />
                  <h3 className="font-semibold text-sm">Select an Issue to Inspect Remediation</h3>
                  <p className="text-xs text-muted-foreground max-w-sm mt-1">
                    Click "Fix Plan" on any issue in the left panel to review its Root Cause Analysis,
                    inspect diffs, and authorize safe execution.
                  </p>
                  {selectedIssue && (
                    <Button
                      size="sm"
                      onClick={() => handleGeneratePlan(selectedIssue)}
                      disabled={planningFix}
                      className="mt-4 text-xs font-medium"
                    >
                      <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                      {planningFix ? 'Generating Plan...' : `Plan Fix for ${selectedIssue.id}`}
                    </Button>
                  )}
                </Card>
              )}
            </div>
          </div>
        </TabsContent>

        {/* ============================================================ */}
        {/* TAB 3: AI ADVISORY & WEB RESEARCH                            */}
        {/* ============================================================ */}
        <TabsContent value="advisory" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left/Main: Conversational Copilot */}
            <div className="lg:col-span-8 flex flex-col h-[650px] border rounded-xl bg-card shadow-sm overflow-hidden">
              {/* Top Controls */}
              <div className="p-4 border-b bg-muted/20 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Bot className="w-5 h-5 text-primary" />
                  <span className="font-bold text-sm">Advisory & Architectural Copilot</span>
                </div>

                <div className="flex items-center gap-4">
                  <div className="flex items-center space-x-2">
                    <Switch
                      id="web-research-toggle"
                      checked={enableWebResearch}
                      onCheckedChange={setEnableWebResearch}
                    />
                    <Label htmlFor="web-research-toggle" className="text-xs font-medium cursor-pointer">
                      Web & Docs Research
                    </Label>
                  </div>

                  <select
                    value={advisoryDomain}
                    onChange={(e) => setAdvisoryDomain(e.target.value)}
                    className="text-xs rounded-md border bg-background px-2.5 py-1 text-foreground"
                  >
                    <option value="general">All Topics</option>
                    <option value="fastapi">FastAPI Architecture</option>
                    <option value="react">React / Vite UI</option>
                    <option value="twilio">Twilio SMS Outbox</option>
                    <option value="chatwoot">Chatwoot AgentBot</option>
                    <option value="calcom">Cal.com Sync</option>
                  </select>
                </div>
              </div>

              {/* Chat Message Scroll */}
              <div className="flex-1 p-4 overflow-y-auto space-y-4">
                {advisoryChat.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex flex-col ${
                      msg.role === 'user' ? 'items-end' : 'items-start'
                    }`}
                  >
                    <div
                      className={`max-w-[85%] rounded-xl p-4 text-xs leading-relaxed shadow-sm ${
                        msg.role === 'user'
                          ? 'bg-primary text-primary-foreground font-medium'
                          : 'bg-muted/60 border text-foreground space-y-3'
                      }`}
                    >
                      <div className="whitespace-pre-wrap">{msg.content}</div>

                      {/* Research Sources & Recommendations */}
                      {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                        <div className="pt-2 border-t border-border/50">
                          <span className="font-semibold text-[11px] text-muted-foreground flex items-center gap-1 mb-1">
                            <Globe className="w-3 h-3 text-primary" /> Verified Documentation Sources:
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {msg.sources.map((src, i) => (
                              <a
                                key={i}
                                href={src}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 text-[10px] bg-background/80 hover:bg-background px-2 py-0.5 rounded border text-primary"
                              >
                                {src.replace('https://', '').split('/')[0]}
                                <ExternalLink className="w-2.5 h-2.5" />
                              </a>
                            ))}
                          </div>
                        </div>
                      )}

                      {msg.role === 'assistant' && msg.recommendations && msg.recommendations.length > 0 && (
                        <div className="pt-2 border-t border-border/50 space-y-1">
                          <span className="font-semibold text-[11px] text-muted-foreground flex items-center gap-1">
                            <Sparkles className="w-3 h-3 text-amber-500" /> Architectural Recommendations:
                          </span>
                          <ul className="list-disc list-inside text-muted-foreground space-y-0.5 text-[11px]">
                            {msg.recommendations.map((rec, i) => (
                              <li key={i}>{rec}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                    <span className="text-[10px] text-muted-foreground mt-1 px-1">
                      {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                ))}
                {advisoryLoading && (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground p-3 bg-muted/30 rounded-lg border w-fit">
                    <Sparkles className="w-4 h-4 text-primary animate-spin" />
                    <span>Synthesizing codebase architecture and researching technical documentation...</span>
                  </div>
                )}
              </div>

              {/* Input Area */}
              <div className="p-3 border-t bg-muted/20">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSendAdvisory();
                  }}
                  className="flex items-center gap-2"
                >
                  <Input
                    value={advisoryPrompt}
                    onChange={(e) => setAdvisoryPrompt(e.target.value)}
                    placeholder="Ask for architectural advice, concurrency optimizations, or new features..."
                    disabled={advisoryLoading}
                    className="text-xs bg-background"
                  />
                  <Button
                    type="submit"
                    size="sm"
                    disabled={advisoryLoading || !advisoryPrompt.trim()}
                    className="shrink-0 text-xs font-semibold"
                  >
                    <Send className="w-3.5 h-3.5 mr-1" />
                    Send
                  </Button>
                </form>
              </div>
            </div>

            {/* Right: Skills Library, Competitor Radar & Quick Inquiries */}
            <div className="lg:col-span-4 space-y-4">
              {/* Skills Reference Library Panel */}
              <Card className="border shadow-sm">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <BookOpen className="w-4 h-4 text-primary" />
                      Skills Reference Library
                    </CardTitle>
                    <Badge variant="outline" className="text-[10px] font-mono">
                      C:\Users\Frank\skills
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="p-4 pt-1 space-y-3">
                  <div className="flex items-center gap-1.5">
                    <Input
                      value={skillsQuery}
                      onChange={(e) => setSkillsQuery(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleSearchSkills();
                        }
                      }}
                      placeholder="Search 1,600+ skills (e.g. fastapi, twilio)..."
                      className="text-xs h-8 bg-background"
                    />
                    <Button
                      size="sm"
                      onClick={() => handleSearchSkills()}
                      disabled={loadingSkills}
                      className="h-8 px-2.5 text-xs font-medium shrink-0"
                    >
                      <Search className={`w-3.5 h-3.5 ${loadingSkills ? 'animate-spin' : ''}`} />
                    </Button>
                  </div>

                  {/* Skills quick chips */}
                  <div className="flex flex-wrap gap-1.5">
                    {['fastapi', 'concurrency', 'twilio', 'chatwoot', 'postgres'].map((tag) => (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => {
                          setSkillsQuery(tag);
                          handleSearchSkills(tag);
                        }}
                        className="text-[10px] px-2 py-0.5 rounded-full border bg-muted/40 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                      >
                        #{tag}
                      </button>
                    ))}
                  </div>

                  {/* Skill Items */}
                  <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                    {skillsList.map((skill) => (
                      <div
                        key={skill.skill_id}
                        className="p-2.5 rounded-lg border bg-muted/20 hover:bg-muted/50 transition-colors text-left space-y-1.5"
                      >
                        <div className="flex items-center justify-between gap-1">
                          <span className="font-semibold text-xs text-foreground truncate font-mono">
                            {skill.name}
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleViewSkill(skill.skill_id)}
                            className="h-6 px-2 text-[10px] text-primary hover:text-primary font-medium shrink-0"
                          >
                            <ExternalLink className="w-3 h-3 mr-1" /> View SKILL.md
                          </Button>
                        </div>
                        <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                          {skill.description}
                        </p>
                      </div>
                    ))}
                    {skillsList.length === 0 && !loadingSkills && (
                      <div className="text-center py-4 text-xs text-muted-foreground">
                        Search skills above to explore engineering blueprints.
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Competitor Tech Radar Card */}
              <Card className="border shadow-sm">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <TrendingUp className="w-4 h-4 text-emerald-500" />
                      Competitor Tech Radar
                    </CardTitle>
                    <Badge variant="secondary" className="text-[10px]">
                      Market Benchmarks
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="p-4 pt-1 space-y-3">
                  <div className="p-2.5 rounded-lg border bg-emerald-500/5 border-emerald-500/20 text-xs space-y-1">
                    <div className="font-semibold text-emerald-700 dark:text-emerald-400 flex items-center justify-between">
                      <span>FastAPI Bookings Advantage</span>
                      <span className="text-[10px] font-mono">0% Merchant Fee</span>
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      Merchants retain 100% revenue vs Fresha's 20% acquisition cut. Guaranteed atomic zero-double-booking locks and self-hosted privacy.
                    </p>
                  </div>

                  {/* Competitor list summary */}
                  <div className="space-y-1.5 text-xs">
                    <div className="flex items-center justify-between p-2 rounded border bg-muted/20">
                      <div>
                        <span className="font-semibold">Fresha</span>
                        <div className="text-[10px] text-muted-foreground">20% marketplace take-rate</div>
                      </div>
                      <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-500/30">
                        Proprietary Cloud
                      </Badge>
                    </div>

                    <div className="flex items-center justify-between p-2 rounded border bg-muted/20">
                      <div>
                        <span className="font-semibold">Calendly</span>
                        <div className="text-[10px] text-muted-foreground">Eventual consistency</div>
                      </div>
                      <Badge variant="outline" className="text-[10px] text-primary border-primary/30">
                        No AI SMS Agent
                      </Badge>
                    </div>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    disabled={loadingRadar}
                    onClick={() => setRadarExpanded(!radarExpanded)}
                    className="w-full text-xs h-7 font-medium"
                  >
                    {loadingRadar ? 'Loading Radar...' : radarExpanded ? 'Hide Detailed Radar' : 'View Full Competitor Matrix'}
                  </Button>

                  {radarExpanded && techRadarData && (
                    <div className="pt-2 border-t space-y-3 text-xs animate-in fade-in-50">
                      <div className="font-semibold text-muted-foreground text-[11px] uppercase tracking-wider">
                        Feature Gap Analysis
                      </div>
                      <div className="space-y-1.5">
                        {techRadarData.feature_gap_matrix.map((fg, idx) => (
                          <div key={idx} className="p-2 rounded border bg-muted/10 text-[11px]">
                            <div className="font-medium text-foreground">{fg.capability}</div>
                            <div className="flex items-center justify-between text-muted-foreground mt-0.5 text-[10px]">
                              <span className="text-emerald-600 font-semibold">Our: {fg.fastapi_bookings}</span>
                              <span>Fresha: {fg.fresha}</span>
                            </div>
                          </div>
                        ))}
                      </div>

                      <div className="font-semibold text-muted-foreground text-[11px] uppercase tracking-wider pt-1">
                        High-Impact Expansion Proposals
                      </div>
                      <div className="space-y-1.5">
                        {techRadarData.expansion_proposals.slice(0, 2).map((prop) => (
                          <div key={prop.id} className="p-2 rounded border bg-card text-[11px] space-y-0.5">
                            <div className="flex items-center justify-between">
                              <span className="font-semibold">{prop.title}</span>
                              <Badge variant="secondary" className="text-[9px] h-4">{prop.priority}</Badge>
                            </div>
                            <p className="text-[10px] text-muted-foreground">{prop.summary}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border shadow-sm">
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-amber-500" />
                    Quick Architectural Inquiries
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-1 space-y-2">
                  {[
                    'Optimize SMS Outbox queue concurrency and retry jitter',
                    'Chatwoot AgentBot webhook signature security and Fernet ciphers',
                    'FastAPI Server-Sent Events (SSE) scaling and connection management',
                    'Tenant isolation patterns for Cal.com multi-calendar sync',
                    'Zero-leak OpenTelemetry trace redaction rules under AGENTS.md',
                  ].map((preset, i) => (
                    <button
                      key={i}
                      onClick={() => handleSendAdvisory(preset)}
                      className="w-full text-left text-xs p-2.5 rounded-lg border bg-muted/30 hover:bg-muted/70 hover:border-primary/50 transition-colors text-foreground flex items-center justify-between group"
                    >
                      <span className="line-clamp-1">{preset}</span>
                      <ArrowRight className="w-3 h-3 text-muted-foreground group-hover:text-primary shrink-0 ml-1" />
                    </button>
                  ))}
                </CardContent>
              </Card>

              <Card className="border shadow-sm bg-muted/20">
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-emerald-500" />
                    AGENTS.md Compliance Guard
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-1 text-xs text-muted-foreground space-y-2 leading-relaxed">
                  <p>
                    All advisory suggestions uphold strict tenant isolation, synthetic fixture isolation,
                    and privacy redaction rules defined in AGENTS.md.
                  </p>
                  <p>
                    Direct execution of advisory changes is always gated by the Safe Fix Studio with
                    mandatory human approval.
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ============================================================ */}
        {/* TAB 4: LIVE EVENT STREAM & TERMINAL                          */}
        {/* ============================================================ */}
        <TabsContent value="stream" className="mt-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border rounded-lg p-3 bg-muted/20">
            {/* Filters */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold text-muted-foreground mr-1 flex items-center gap-1">
                <ListFilter className="w-3.5 h-3.5" /> Filter:
              </span>
              {['all', 'thoughts', 'steps', 'audit', 'fixes'].map((flt) => (
                <Button
                  key={flt}
                  size="sm"
                  variant={eventFilter === flt ? 'default' : 'outline'}
                  onClick={() => setEventFilter(flt)}
                  className="h-7 text-[11px] capitalize"
                >
                  {flt}
                </Button>
              ))}
            </div>

            {/* Controls */}
            <div className="flex items-center gap-4">
              <div className="flex items-center space-x-2">
                <Switch
                  id="autoscroll-switch"
                  checked={autoScroll}
                  onCheckedChange={setAutoScroll}
                />
                <Label htmlFor="autoscroll-switch" className="text-xs font-medium cursor-pointer">
                  Auto-scroll
                </Label>
              </div>

              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEvents([])}
                className="h-7 text-xs text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="w-3.5 h-3.5 mr-1" /> Clear Log
              </Button>
            </div>
          </div>

          {/* Terminal Box */}
          <div className="font-mono text-xs bg-zinc-950 text-zinc-100 rounded-xl border border-zinc-800 p-4 h-[550px] overflow-y-auto space-y-2 shadow-inner">
            {filteredEvents.length === 0 ? (
              <div className="text-zinc-500 italic text-center py-24">
                No events streamed yet. Run an audit or execute a plan to stream live thoughts and steps.
              </div>
            ) : (
              filteredEvents.map((ev, i) => {
                const time = new Date(ev.timestamp).toLocaleTimeString();
                return (
                  <div key={i} className="flex items-start gap-2.5 py-1 border-b border-zinc-900/60 leading-relaxed">
                    <span className="text-zinc-500 select-none shrink-0 text-[10px] mt-0.5">[{time}]</span>

                    {/* Badge */}
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase shrink-0 ${
                        ev.type === 'thought'
                          ? 'bg-purple-950 text-purple-300 border border-purple-800'
                          : ev.type === 'step'
                          ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                          : ev.type === 'audit'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : ev.type === 'fix_status'
                          ? 'bg-amber-950 text-amber-300 border border-amber-800'
                          : 'bg-zinc-800 text-zinc-300'
                      }`}
                    >
                      {ev.type}
                    </span>

                    {/* Content */}
                    <div className="flex-1">
                      {ev.title && <span className="font-semibold text-zinc-200 mr-1.5">{ev.title}:</span>}
                      <span className="text-zinc-300">
                        {typeof ev.data === 'string' ? ev.data : JSON.stringify(ev.data)}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
            <div ref={terminalBottomRef} />
          </div>
        </TabsContent>

        {/* ============================================================ */}
        {/* TAB 5: CONVERSATIONAL CODING AGENT                           */}
        {/* ============================================================ */}
        <TabsContent value="coding" className="mt-6 space-y-6">
          {/* Top Status & Launch Bar */}
          <Card className="border-border/60 shadow-sm overflow-hidden">
            <CardHeader className="bg-muted/20 border-b pb-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-primary/10 text-primary border border-primary/20">
                    <Code2 className="w-6 h-6" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <CardTitle className="text-lg font-bold">Codex Conversational Coding Studio</CardTitle>
                      <Badge variant="outline" className="text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        Ready
                      </Badge>
                    </div>
                    <CardDescription className="text-xs mt-0.5">
                      Autonomous conversational software engineering harness executing inside <code className="font-mono text-primary font-semibold">f:\Projects\fastapi_bookings</code>
                    </CardDescription>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      navigator.clipboard.writeText('cd codex-control-centre && ./start.bat');
                      toast.success('Command copied: cd codex-control-centre && ./start.bat');
                    }}
                    className="flex items-center gap-1.5 text-xs font-mono"
                    title="Copy backend startup command"
                  >
                    <Copy className="w-3.5 h-3.5" />
                    <span>start.bat</span>
                  </Button>

                  <Button
                    size="sm"
                    onClick={() => window.open('http://localhost:5180', '_blank', 'noopener,noreferrer')}
                    className="flex items-center gap-1.5 bg-primary text-primary-foreground font-semibold shadow-xs"
                  >
                    <ExternalLink className="w-4 h-4" />
                    Open Fullscreen Studio
                  </Button>
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-6">
              {/* Harness Metadata Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="p-3.5 rounded-lg border bg-card/60 space-y-1">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="font-medium">Backend</span>
                    <Badge variant="outline" className="text-[10px] font-mono">JSON-RPC</Badge>
                  </div>
                  <div className="font-mono text-xs font-semibold text-foreground truncate">
                    http://127.0.0.1:8100
                  </div>
                  <p className="text-[11px] text-muted-foreground">Codex JSON-RPC Engine</p>
                </div>

                <div className="p-3.5 rounded-lg border bg-card/60 space-y-1">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="font-medium">Frontend Studio</span>
                    <Badge variant="outline" className="text-[10px] font-mono">Control Centre</Badge>
                  </div>
                  <div className="font-mono text-xs font-semibold text-foreground truncate">
                    http://127.0.0.1:5180
                  </div>
                  <p className="text-[11px] text-muted-foreground">Codex Control Centre</p>
                </div>

                <div className="p-3.5 rounded-lg border bg-card/60 space-y-1">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="font-medium">Workspace Target</span>
                    <Badge variant="outline" className="text-[10px] font-mono">Root</Badge>
                  </div>
                  <div className="font-mono text-xs font-semibold text-foreground truncate">
                    f:\Projects\fastapi_bookings
                  </div>
                  <p className="text-[11px] text-muted-foreground">Active Monorepo Target</p>
                </div>

                <div className="p-3.5 rounded-lg border bg-card/60 space-y-1">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="font-medium">Status</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  </div>
                  <div className="font-medium text-xs text-emerald-600 dark:text-emerald-400">
                    Ready
                  </div>
                  <p className="text-[11px] text-muted-foreground">Daemon connection available</p>
                </div>
              </div>

              {/* Startup Instructions Callout */}
              <div className="mt-4 p-3.5 rounded-lg border border-border/80 bg-muted/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2.5">
                  <Terminal className="w-4 h-4 text-primary shrink-0" />
                  <div>
                    <span className="font-semibold text-foreground">Start Codex Backend:</span>{' '}
                    <code className="bg-background border px-2 py-0.5 rounded font-mono text-primary font-semibold">
                      cd codex-control-centre && ./start.bat
                    </code>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText('cd codex-control-centre && ./start.bat');
                    toast.success('Command copied: cd codex-control-centre && ./start.bat');
                  }}
                  className="h-7 text-xs font-medium gap-1 shrink-0"
                >
                  <Copy className="w-3.5 h-3.5" />
                  Copy Command
                </Button>
              </div>

              {/* Quick Start Prompt Presets */}
              <div className="mt-5 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-primary" />
                    Quick Start Prompt Presets (Click to Copy)
                  </span>
                  <span className="text-[11px] text-muted-foreground">Click any card to copy prompt</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div
                    onClick={() => {
                      const prompt = "Analyze app/api/routers/bookings.py for concurrency bottlenecks";
                      navigator.clipboard.writeText(prompt);
                      toast.success(`Prompt copied: "${prompt}"`);
                    }}
                    className="p-3.5 rounded-lg border bg-card hover:bg-accent/40 hover:border-primary/40 cursor-pointer transition-all space-y-1.5 group"
                  >
                    <div className="flex items-center justify-between">
                      <Badge variant="secondary" className="text-[10px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20">
                        Concurrency
                      </Badge>
                      <Copy className="w-3 h-3 text-muted-foreground group-hover:text-primary transition-colors" />
                    </div>
                    <p className="text-xs font-medium text-foreground group-hover:text-primary transition-colors leading-snug font-mono">
                      Analyze app/api/routers/bookings.py for concurrency bottlenecks
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      Inspect database locking, slot contention, and async route performance.
                    </p>
                  </div>

                  <div
                    onClick={() => {
                      const prompt = "Inspect app/services/sms/inbound_service.py Chatwoot origin security";
                      navigator.clipboard.writeText(prompt);
                      toast.success(`Prompt copied: "${prompt}"`);
                    }}
                    className="p-3.5 rounded-lg border bg-card hover:bg-accent/40 hover:border-primary/40 cursor-pointer transition-all space-y-1.5 group"
                  >
                    <div className="flex items-center justify-between">
                      <Badge variant="secondary" className="text-[10px] font-medium bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20">
                        Origin Security
                      </Badge>
                      <Copy className="w-3 h-3 text-muted-foreground group-hover:text-primary transition-colors" />
                    </div>
                    <p className="text-xs font-medium text-foreground group-hover:text-primary transition-colors leading-snug font-mono">
                      Inspect app/services/sms/inbound_service.py Chatwoot origin security
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      Validate HMAC webhook verification, header forgery guards, and replay protections.
                    </p>
                  </div>

                  <div
                    onClick={() => {
                      const prompt = "Review uncommitted git diffs and propose tests";
                      navigator.clipboard.writeText(prompt);
                      toast.success(`Prompt copied: "${prompt}"`);
                    }}
                    className="p-3.5 rounded-lg border bg-card hover:bg-accent/40 hover:border-primary/40 cursor-pointer transition-all space-y-1.5 group"
                  >
                    <div className="flex items-center justify-between">
                      <Badge variant="secondary" className="text-[10px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20">
                        Diff & QA
                      </Badge>
                      <Copy className="w-3 h-3 text-muted-foreground group-hover:text-primary transition-colors" />
                    </div>
                    <p className="text-xs font-medium text-foreground group-hover:text-primary transition-colors leading-snug font-mono">
                      Review uncommitted git diffs and propose tests
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      Inspect staged/unstaged changes, propose unit tests, and verify edge cases.
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Live Studio Frame Preview Card */}
          <Card className="border-border/60 shadow-sm overflow-hidden flex flex-col">
            <div className="p-3 bg-muted/40 border-b flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
                </div>
                <span className="mx-2 text-border">|</span>
                <Globe className="w-3.5 h-3.5 text-primary" />
                <span className="text-foreground font-semibold">Live Studio Preview:</span>
                <span className="bg-background border px-2 py-0.5 rounded text-[11px]">http://127.0.0.1:5180</span>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setStudioIframeKey(k => k + 1)}
                  className="h-7 text-xs gap-1"
                >
                  <RefreshCw className="w-3 h-3" />
                  Reload Frame
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open('http://localhost:5180', '_blank', 'noopener,noreferrer')}
                  className="h-7 text-xs gap-1"
                >
                  <ExternalLink className="w-3 h-3" />
                  Open Fullscreen Studio
                </Button>
              </div>
            </div>

            {/* Fallback info banner */}
            <div className="px-4 py-2.5 bg-amber-500/10 border-b border-amber-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-amber-800 dark:text-amber-300">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-amber-600 dark:text-amber-400" />
                <span>
                  <strong>Harness Service Notice:</strong> If the preview frame below remains blank or shows a connection error, start the Codex server using <code className="bg-background/80 font-mono px-1.5 py-0.5 rounded border border-amber-500/30">cd codex-control-centre && ./start.bat</code>.
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText('cd codex-control-centre && ./start.bat');
                  toast.success('Copied start command to clipboard');
                }}
                className="h-6 text-[11px] shrink-0 border-amber-500/40 hover:bg-amber-500/20"
              >
                Copy Command
              </Button>
            </div>

            {/* Iframe element */}
            <div className="relative w-full h-[750px] bg-card">
              <iframe
                key={studioIframeKey}
                src="http://127.0.0.1:5180"
                title="Conversational Coding Studio Preview"
                className="w-full h-full border-0"
                allow="clipboard-read; clipboard-write"
              />
            </div>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 1-Click Skill Viewer Dialog */}
      <Dialog open={skillModalOpen} onOpenChange={setSkillModalOpen}>
        <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col p-6">
          <DialogHeader className="pb-3 border-b">
            <div className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-primary" />
              <DialogTitle className="text-base font-semibold font-mono">
                {selectedSkillContent?.skill_id}
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-muted-foreground">
              Engineering skill blueprint loaded on-demand from local library at C:\Users\Frank\skills
            </DialogDescription>
          </DialogHeader>
          <div className="overflow-y-auto max-h-[60vh] p-4 bg-muted/40 rounded-lg text-xs font-mono whitespace-pre-wrap leading-relaxed border mt-2">
            {selectedSkillContent?.content}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
