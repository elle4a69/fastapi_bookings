import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Activity, AlertTriangle, Clock, Database, ExternalLink, Server, ShieldCheck, Trash2, Wifi } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '../../lib/api';

// ── Types aligned with SystemHealthResponse schema ──────────────────────────

interface ServiceHealthCheck {
  status: 'ok' | 'degraded' | 'down';
  latency_ms: number | null;
  detail: string | null;
}

interface SystemHealthResponse {
  api_status: 'operational' | 'degraded' | 'down';
  postgres: ServiceHealthCheck;
  redis: ServiceHealthCheck;
  neo4j: ServiceHealthCheck | null;
  background_workers: ServiceHealthCheck | null;
  checked_at: string; // ISO-8601 datetime
}

interface GovernanceLinks {
  ok: boolean;
  super_admin_url: string;
  account_url?: string | null;
  chatwoot_account_id?: number | null;
  base_url: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function statusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'ok' || status === 'operational') return 'default';
  if (status === 'degraded') return 'secondary';
  return 'destructive';
}

function LatencyBadge({ latency_ms }: { latency_ms: number | null }) {
  if (latency_ms === null) return <span className="text-xs text-muted-foreground">—</span>;
  return <span className="text-xs font-mono">{latency_ms} ms</span>;
}

function ServiceRow({ label, check }: { label: string; check: ServiceHealthCheck }) {
  return (
    <div className="flex items-center justify-between py-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-3">
        <LatencyBadge latency_ms={check.latency_ms} />
        <Badge variant={statusVariant(check.status)} className="uppercase text-xs">
          {check.status}
        </Badge>
      </div>
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function SystemPage() {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [govLinks, setGovLinks] = useState<GovernanceLinks | null>(null);
  const [, setLoading] = useState(false);
  const [cleaning, setCleaning] = useState(false);

  useEffect(() => {
    fetchHealth();
    fetchGovernance();
  }, []);

  const fetchGovernance = async () => {
    try {
      const res: any = await apiClient.get('/api/admin/governance/chatwoot-links');
      setGovLinks(res?.data ?? res);
    } catch {
      console.warn('Failed to fetch governance links');
    }
  };

  const fetchHealth = async () => {
    setLoading(true);
    setHealthError(null);
    try {
      const res: any = await apiClient.get('/api/admin/system/health');
      setHealth(res?.data ?? res);
    } catch (err: any) {
      // Display a real error state — never fall back to fake data.
      setHealth(null);
      const message =
        err?.response?.data?.error?.message ??
        err?.message ??
        'Could not reach the server';
      setHealthError(`Health check unavailable — ${message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCleanup = async () => {
    setCleaning(true);
    try {
      await apiClient.post('/api/admin/system/cleanup');
      toast.success('System cleanup executed successfully');
    } catch {
      console.error('Operation failed');
      toast.error('Failed to execute cleanup');
    } finally {
      setCleaning(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">System Diagnostics</h1>
        <p className="text-muted-foreground mt-2">Monitor platform health and perform maintenance tasks.</p>
      </div>

      {/* ── Error banner ── */}
      {healthError && (
        <div className="flex items-center gap-3 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {healthError}
        </div>
      )}

      {/* ── Top-level status cards ── */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">API Status</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {health ? (
                <Badge variant={statusVariant(health.api_status)} className="uppercase">
                  {health.api_status}
                </Badge>
              ) : healthError ? (
                <Badge variant="destructive" className="uppercase">unavailable</Badge>
              ) : '...'}
            </div>
            {health?.checked_at && (
              <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {new Date(health.checked_at).toLocaleTimeString()}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Database</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {health ? (
                <Badge variant={statusVariant(health.postgres.status)} className="uppercase">
                  {health.postgres.status}
                </Badge>
              ) : healthError ? (
                <Badge variant="outline" className="uppercase">—</Badge>
              ) : '...'}
            </div>
            {health && (
              <p className="text-xs text-muted-foreground mt-1">
                PostgreSQL{health.postgres.latency_ms !== null ? ` · ${health.postgres.latency_ms} ms` : ''}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Cache</CardTitle>
            <Wifi className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {health ? (
                <Badge variant={statusVariant(health.redis.status)} className="uppercase">
                  {health.redis.status}
                </Badge>
              ) : healthError ? (
                <Badge variant="outline" className="uppercase">—</Badge>
              ) : '...'}
            </div>
            {health && (
              <p className="text-xs text-muted-foreground mt-1">
                Redis{health.redis.latency_ms !== null ? ` · ${health.redis.latency_ms} ms` : ''}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Detailed service breakdown ── */}
      {health && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary" />
              Service Details
            </CardTitle>
            <CardDescription>Live latency measurements from the last health check.</CardDescription>
          </CardHeader>
          <CardContent className="divide-y">
            <ServiceRow label="PostgreSQL" check={health.postgres} />
            <ServiceRow label="Redis" check={health.redis} />
            {health.neo4j && <ServiceRow label="Neo4j" check={health.neo4j} />}
            {health.background_workers && (
              <ServiceRow label="Background Workers" check={health.background_workers} />
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-primary" />
              Platform Owner Governance &amp; Chatwoot
            </CardTitle>
            <CardDescription>
              Direct deep links for platform SuperAdmin operations and Chatwoot inbox management.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Chatwoot Instance:</span>
              <Badge variant="outline" className="font-mono text-xs">
                {govLinks?.base_url || 'http://localhost:4000'}
              </Badge>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Tenant Chatwoot ID:</span>
              <Badge variant={govLinks?.chatwoot_account_id ? 'secondary' : 'outline'} className="font-mono text-xs">
                {govLinks?.chatwoot_account_id ? `#${govLinks.chatwoot_account_id}` : 'Not provisioned'}
              </Badge>
            </div>
            <div className="pt-2 flex flex-wrap gap-2">
              <Button
                variant="default"
                size="sm"
                className="gap-2"
                onClick={() => {
                  if (govLinks?.super_admin_url) {
                    window.open(govLinks.super_admin_url, '_blank', 'noopener,noreferrer');
                  }
                }}
                disabled={!govLinks?.super_admin_url}
              >
                <ExternalLink className="h-4 w-4" />
                Open SuperAdmin Console
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={() => {
                  if (govLinks?.account_url) {
                    window.open(govLinks.account_url, '_blank', 'noopener,noreferrer');
                  }
                }}
                disabled={!govLinks?.account_url}
              >
                <ExternalLink className="h-4 w-4" />
                Open Tenant Workspace
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Maintenance Actions</CardTitle>
            <CardDescription>Execute manual system cleanup procedures.</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              Running a historic cleanup will purge old logs, temporary exports, and expired sessions from the database to reclaim space.
            </p>
            <Button variant="destructive" onClick={handleCleanup} disabled={cleaning}>
              <Trash2 className="h-4 w-4 mr-2" />
              {cleaning ? 'Cleaning...' : 'Run Historic Cleanup'}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
