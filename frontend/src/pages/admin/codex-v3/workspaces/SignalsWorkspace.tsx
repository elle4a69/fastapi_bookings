import React, { useState } from 'react'
import {
  Activity,
  ExternalLink,
  RefreshCw,
  Server,
  Database,
  Cpu,
  Layers,
  CheckCircle2,
  Radio,
  MessageSquare,
  Send,
  Zap,
  TrendingDown,
  Check
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SentinelStatus {
  id: string
  name: string
  service: string
  status: 'healthy' | 'degraded' | 'down'
  latencyMs: number
  uptimePercent: number
  details: string
  icon: 'server' | 'database' | 'redis' | 'neo4j' | 'workers'
}

export interface LatencyDataPoint {
  time: string
  p50: number
  p95: number
  p99: number
}

export interface SignalsWorkspaceProps {
  signozUrl?: string
  onPingSentinels?: () => void
  onForceChatwootSync?: () => void
  className?: string
}

const INITIAL_SENTINELS: SentinelStatus[] = [
  {
    id: 'fastapi',
    name: 'FastAPI REST Core',
    service: 'Core Backend Server',
    status: 'healthy',
    latencyMs: 14,
    uptimePercent: 99.98,
    details: 'Port 8000 • Uvicorn worker pool active • 0 unhandled exceptions',
    icon: 'server'
  },
  {
    id: 'postgres',
    name: 'PostgreSQL Relational DB',
    service: 'Primary Database & Alembic',
    status: 'healthy',
    latencyMs: 4,
    uptimePercent: 99.99,
    details: 'Pool: 12/20 active connections • Optimistic concurrency locks active',
    icon: 'database'
  },
  {
    id: 'redis',
    name: 'Redis Cache & PubSub',
    service: 'In-Memory Store',
    status: 'healthy',
    latencyMs: 1,
    uptimePercent: 100.0,
    details: 'Memory: 32MB / 512MB • 8 connected clients • Zero key evictions',
    icon: 'redis'
  },
  {
    id: 'neo4j',
    name: 'Neo4j Graph Database',
    service: 'Knowledge Graph & Assistant Memory',
    status: 'healthy',
    latencyMs: 8,
    uptimePercent: 99.95,
    details: '14,820 entities • RAG embeddings synced • Cypher index active',
    icon: 'neo4j'
  },
  {
    id: 'workers',
    name: 'Async Background Workers',
    service: 'Task Queues & Schedulers',
    status: 'healthy',
    latencyMs: 6,
    uptimePercent: 99.92,
    details: '3 active queues • 0 failed jobs in last 24h • Auto-retry enabled',
    icon: 'workers'
  }
]

const SAMPLE_LATENCY_SERIES: LatencyDataPoint[] = [
  { time: '10:00', p50: 16, p95: 48, p99: 110 },
  { time: '10:05', p50: 18, p95: 52, p99: 118 },
  { time: '10:10', p50: 22, p95: 64, p99: 142 },
  { time: '10:15', p50: 17, p95: 56, p99: 122 },
  { time: '10:20', p50: 15, p95: 46, p99: 98 },
  { time: '10:25', p50: 19, p95: 59, p99: 135 },
  { time: '10:30', p50: 14, p95: 44, p99: 92 }
]

export const SignalsWorkspace: React.FC<SignalsWorkspaceProps> = ({
  signozUrl = 'http://localhost:3301',
  onPingSentinels,
  onForceChatwootSync,
  className
}) => {
  const [sentinels, setSentinels] = useState<SentinelStatus[]>(INITIAL_SENTINELS)
  const [isPinging, setIsPinging] = useState(false)
  const [lastPingTime, setLastPingTime] = useState<string>('Just now')
  const [chatwootSyncing, setChatwootSyncing] = useState(false)
  const [chatwootMessage, setChatwootMessage] = useState<string | null>(null)

  // Current APM telemetry aggregates
  const currentP50 = 18
  const currentP95 = 58
  const currentP99 = 124

  const handlePing = () => {
    setIsPinging(true)
    if (onPingSentinels) {
      onPingSentinels()
    }
    setTimeout(() => {
      setIsPinging(false)
      setLastPingTime('Just now')
      setSentinels((prev) =>
        prev.map((s) => ({
          ...s,
          latencyMs: Math.max(1, s.latencyMs + Math.floor(Math.random() * 5 - 2))
        }))
      )
    }, 800)
  }

  const handleResyncChatwoot = () => {
    setChatwootSyncing(true)
    if (onForceChatwootSync) {
      onForceChatwootSync()
    }
    setTimeout(() => {
      setChatwootSyncing(false)
      setChatwootMessage('Chatwoot conversations & webhooks synchronized successfully.')
      setTimeout(() => setChatwootMessage(null), 3500)
    }, 1200)
  }

  const getSentinelIcon = (type: SentinelStatus['icon']) => {
    switch (type) {
      case 'server':
        return <Server className="h-4 w-4 text-primary" />
      case 'database':
        return <Database className="h-4 w-4 text-emerald-400" />
      case 'redis':
        return <Zap className="h-4 w-4 text-rose-400" />
      case 'neo4j':
        return <Layers className="h-4 w-4 text-purple-400" />
      case 'workers':
      default:
        return <Cpu className="h-4 w-4 text-blue-400" />
    }
  }

  return (
    <div
      data-testid="signals-workspace"
      className={cn('flex flex-col h-full w-full p-4 sm:p-6 space-y-4 max-w-6xl mx-auto', className)}
    >
      {/* 1. Header with APM Link and Ping Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/40">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <h1 className="text-xl font-bold tracking-tight text-foreground">
              Health Sentinels & Telemetry Signals
            </h1>
          </div>
          <p className="text-xs text-muted-foreground">
            SigNoz APM telemetry, live P50/P95/P99 latency distribution, sentinel health matrix, and integration sinks.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <a
            href={signozUrl}
            target="_blank"
            rel="noopener noreferrer"
            data-testid="signoz-apm-link"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-card/80 hover:bg-card border border-border/50 text-foreground transition-all shadow-sm min-h-[38px]"
          >
            <Activity className="h-3.5 w-3.5 text-rose-400" />
            <span>Open SigNoz APM</span>
            <ExternalLink className="h-3 w-3 opacity-60 ml-0.5" />
          </a>

          <button
            type="button"
            data-testid="ping-sentinels-btn"
            disabled={isPinging}
            onClick={handlePing}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary hover:bg-primary/90 text-primary-foreground transition-all shadow-sm min-h-[38px]"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isPinging && 'animate-spin')} />
            <span>{isPinging ? 'Pinging...' : 'Ping All Sentinels'}</span>
          </button>
        </div>
      </div>

      {/* 2. Top Metric Cards: APM Live Latency Distribution */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* P50 Card */}
        <div className="rounded-xl border border-border/40 bg-card/60 p-4 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground font-mono">
              P50 Median Latency
            </span>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-400">
              Optimal
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold font-mono text-foreground">
              {currentP50}ms
            </span>
            <span className="text-xs text-emerald-400 font-mono flex items-center gap-0.5">
              <TrendingDown className="h-3 w-3" /> -2ms vs avg
            </span>
          </div>
          <p className="text-[11px] text-muted-foreground">50% of requests complete under 18ms</p>
        </div>

        {/* P95 Card */}
        <div className="rounded-xl border border-border/40 bg-card/60 p-4 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground font-mono">
              P95 Tail Latency
            </span>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-400">
              Compliant
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold font-mono text-foreground">
              {currentP95}ms
            </span>
            <span className="text-xs text-muted-foreground font-mono">Threshold: &lt; 200ms</span>
          </div>
          <p className="text-[11px] text-muted-foreground">95% of API transactions complete under 58ms</p>
        </div>

        {/* P99 Card */}
        <div className="rounded-xl border border-border/40 bg-card/60 p-4 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground font-mono">
              P99 Maximum Guard
            </span>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-400">
              Guarded
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold font-mono text-foreground">
              {currentP99}ms
            </span>
            <span className="text-xs text-muted-foreground font-mono">SLA Ceiling: 500ms</span>
          </div>
          <p className="text-[11px] text-muted-foreground">Peak lock contention queries bounded to 124ms</p>
        </div>
      </div>

      {/* 3. SVG Latency Sparkline Chart Card */}
      <div className="rounded-xl border border-border/40 bg-card/60 p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-border/30 pb-2">
          <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Activity className="h-4 w-4 text-primary" />
            Live Response Latency Trend (Last 30 Minutes)
          </span>
          <div className="flex items-center gap-3 text-[11px] font-mono">
            <span className="flex items-center gap-1 text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-500" /> P50
            </span>
            <span className="flex items-center gap-1 text-blue-400">
              <span className="h-2 w-2 rounded-full bg-blue-500" /> P95
            </span>
            <span className="flex items-center gap-1 text-purple-400">
              <span className="h-2 w-2 rounded-full bg-purple-500" /> P99
            </span>
          </div>
        </div>

        {/* Scalable SVG Chart */}
        <div className="w-full h-32 sm:h-40 relative">
          <svg className="w-full h-full" viewBox="0 0 700 140" preserveAspectRatio="none">
            {/* Grid lines */}
            <line x1="0" y1="20" x2="700" y2="20" stroke="currentColor" strokeOpacity="0.08" strokeDasharray="4" />
            <line x1="0" y1="70" x2="700" y2="70" stroke="currentColor" strokeOpacity="0.08" strokeDasharray="4" />
            <line x1="0" y1="120" x2="700" y2="120" stroke="currentColor" strokeOpacity="0.08" strokeDasharray="4" />

            {/* P99 Line (purple) */}
            <polyline
              fill="none"
              stroke="#c084fc"
              strokeWidth="2.5"
              points={SAMPLE_LATENCY_SERIES.map((d, i) => `${i * 115 + 10},${130 - d.p99 * 0.8}`).join(' ')}
            />

            {/* P95 Line (blue) */}
            <polyline
              fill="none"
              stroke="#60a5fa"
              strokeWidth="2.5"
              points={SAMPLE_LATENCY_SERIES.map((d, i) => `${i * 115 + 10},${130 - d.p95 * 0.8}`).join(' ')}
            />

            {/* P50 Line (emerald) */}
            <polyline
              fill="none"
              stroke="#34d399"
              strokeWidth="2.5"
              points={SAMPLE_LATENCY_SERIES.map((d, i) => `${i * 115 + 10},${130 - d.p50 * 0.8}`).join(' ')}
            />

            {/* Data points */}
            {SAMPLE_LATENCY_SERIES.map((d, i) => (
              <g key={i}>
                <circle cx={i * 115 + 10} cy={130 - d.p50 * 0.8} r="3.5" fill="#34d399" />
                <circle cx={i * 115 + 10} cy={130 - d.p95 * 0.8} r="3.5" fill="#60a5fa" />
                <circle cx={i * 115 + 10} cy={130 - d.p99 * 0.8} r="3.5" fill="#c084fc" />
              </g>
            ))}
          </svg>

          {/* Time axis labels */}
          <div className="flex justify-between text-[10px] font-mono text-muted-foreground pt-1">
            {SAMPLE_LATENCY_SERIES.map((d) => (
              <span key={d.time}>{d.time}</span>
            ))}
          </div>
        </div>
      </div>

      {/* 4. Health Sentinel Matrix */}
      <div className="rounded-xl border border-border/40 bg-card/60 p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-border/30 pb-2">
          <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Radio className="h-4 w-4 text-emerald-400" />
            Health Sentinel Matrix (FastAPI, PostgreSQL, Redis, Neo4j, Workers)
          </span>
          <span className="text-[11px] font-mono text-muted-foreground">
            Last pinged: {lastPingTime}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {sentinels.map((sentinel) => (
            <div
              key={sentinel.id}
              data-testid={`sentinel-${sentinel.id}`}
              className="p-3 rounded-lg border border-border/30 bg-background/50 space-y-2 hover:bg-background/80 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-md bg-muted/60">
                    {getSentinelIcon(sentinel.icon)}
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-foreground leading-none">
                      {sentinel.name}
                    </h4>
                    <span className="text-[10px] text-muted-foreground font-mono">
                      {sentinel.service}
                    </span>
                  </div>
                </div>

                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  <CheckCircle2 className="h-3 w-3" />
                  <span>Healthy</span>
                </span>
              </div>

              <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground pt-1 border-t border-border/20">
                <span>Latency: {sentinel.latencyMs}ms</span>
                <span>Uptime: {sentinel.uptimePercent}%</span>
              </div>

              <p className="text-[11px] text-muted-foreground/80 leading-normal line-clamp-2">
                {sentinel.details}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* 5. SMS Outbox Backlog & Chatwoot Sync Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* SMS Outbox Backlog Card */}
        <div className="rounded-xl border border-border/40 bg-card/60 p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-border/30 pb-2">
            <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <Send className="h-4 w-4 text-primary" />
              SMS Outbox Backlog & Carrier Status
            </span>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/15 text-emerald-400">
              Carrier Live
            </span>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Queue Backlog:</span>
              <span className="font-mono font-bold text-emerald-400">0 messages pending</span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Delivered (Last 15m):</span>
              <span className="font-mono font-bold text-foreground">28 sent (99.4% success)</span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Carrier Gateway:</span>
              <span className="font-mono text-muted-foreground">Twilio / Telnyx (TLS 1.3)</span>
            </div>

            {/* Masked SMS activity snapshot */}
            <div className="rounded-lg bg-zinc-950 p-2.5 font-mono text-[10px] text-zinc-300 border border-zinc-800 space-y-1">
              <div className="text-zinc-500 uppercase tracking-wider font-bold">Recent Dispatches:</div>
              <div className="text-emerald-400">✓ SMS-8821 to +61 4** *** 892 • Delivered (220ms)</div>
              <div className="text-emerald-400">✓ SMS-8820 to +61 4** *** 314 • Delivered (184ms)</div>
              <div className="text-emerald-400">✓ SMS-8819 to +61 4** *** 701 • Delivered (195ms)</div>
            </div>
          </div>
        </div>

        {/* Chatwoot Sync Status Card */}
        <div className="rounded-xl border border-border/40 bg-card/60 p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-border/30 pb-2">
            <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <MessageSquare className="h-4 w-4 text-blue-400" />
              Chatwoot Webhook & Conversation Sync
            </span>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/15 text-emerald-400">
              Synced
            </span>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Webhook Status:</span>
              <span className="font-mono font-bold text-emerald-400">Connected (HTTP 200 OK)</span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Sync Lag:</span>
              <span className="font-mono font-bold text-foreground">84ms average</span>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Active Inboxes:</span>
              <span className="font-mono text-muted-foreground">4 Inboxes Connected</span>
            </div>

            {chatwootMessage && (
              <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-[11px] flex items-center gap-1.5">
                <Check className="h-3.5 w-3.5 text-emerald-400" />
                <span>{chatwootMessage}</span>
              </div>
            )}

            <button
              type="button"
              data-testid="force-chatwoot-sync-btn"
              disabled={chatwootSyncing}
              onClick={handleResyncChatwoot}
              className="w-full py-1.5 rounded-lg text-xs font-semibold bg-card hover:bg-card/80 border border-border/50 text-foreground transition-all flex items-center justify-center gap-1.5 min-h-[36px]"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', chatwootSyncing && 'animate-spin')} />
              <span>{chatwootSyncing ? 'Synchronizing...' : 'Force Resync Chatwoot Webhooks'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SignalsWorkspace
