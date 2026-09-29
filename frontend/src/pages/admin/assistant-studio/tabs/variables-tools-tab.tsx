import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Wrench,
  Lock,
  Copy,
  Zap,
  RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import type { LiveToolItem, ProviderItem, VariableItem } from '../types';

interface VariablesToolsTabProps {
  selectedProvider: ProviderItem | null;
}

export const VariablesToolsTab: React.FC<VariablesToolsTabProps> = ({ selectedProvider }) => {
  const [activeSection, setActiveSection] = useState<'variables' | 'tools'>('tools');
  const [selectedToolIndex, setSelectedToolIndex] = useState(0);

  const [variables, setVariables] = useState<VariableItem[]>([]);
  const [tools, setTools] = useState<LiveToolItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const loadData = () => {
    setIsLoading(true);
    const params = selectedProvider?.id ? `?provider_id=${selectedProvider.id}` : '';

    Promise.all([
      apiClient.get<VariableItem[]>(`/api/admin/assistant-studio/variables${params}`),
      apiClient.get<LiveToolItem[]>('/api/admin/assistant-studio/tools'),
    ])
      .then(([varsData, toolsData]) => {
        if (Array.isArray(varsData)) setVariables(varsData);
        if (Array.isArray(toolsData)) setTools(toolsData);
      })
      .catch((err) => {
        console.error('Failed to load variables/tools:', err);
        toast.error('Failed to load variable and tool registries');
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    loadData();
  }, [selectedProvider?.id]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success(`Copied "${text}" to clipboard.`);
  };

  const selectedTool = tools[selectedToolIndex] || tools[0];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b">
        <div>
          <h2 className="text-xl font-bold tracking-tight flex items-center gap-2">
            <Zap className="h-5 w-5 text-primary" />
            Registered Variables & Live Tool Registry
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Strict server-enforced scoping boundaries. Variables interpolate securely without leaking cross-tenant data.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border bg-muted/40 p-1 text-xs">
            <button
              onClick={() => setActiveSection('tools')}
              className={`py-1.5 px-3 rounded-md font-medium transition-all ${
                activeSection === 'tools' ? 'bg-background shadow-xs text-foreground' : 'text-muted-foreground'
              }`}
            >
              Live Tools ({tools.length})
            </button>
            <button
              onClick={() => setActiveSection('variables')}
              className={`py-1.5 px-3 rounded-md font-medium transition-all ${
                activeSection === 'variables' ? 'bg-background shadow-xs text-foreground' : 'text-muted-foreground'
              }`}
            >
              Variables ({variables.length})
            </button>
          </div>
          <Button variant="outline" size="sm" onClick={loadData} disabled={isLoading} className="h-8 px-2.5">
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {isLoading && tools.length === 0 && variables.length === 0 ? (
        <div className="py-20 text-center text-muted-foreground">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-primary" />
          <p className="text-xs">Querying registered tool and variable endpoints...</p>
        </div>
      ) : activeSection === 'variables' ? (
        /* Variables View */
        <div className="space-y-4">
          <Card className="border-border/60">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold">Registered Template Variables</CardTitle>
              <CardDescription className="text-xs">
                Tokens recognized and interpolated by the PromptPolicyAssembler.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border overflow-hidden">
                <table className="w-full text-xs text-left">
                  <thead className="bg-muted/60 text-muted-foreground border-b font-mono">
                    <tr>
                      <th className="p-3">Variable Token</th>
                      <th className="p-3">Scope</th>
                      <th className="p-3">Resolver Source</th>
                      <th className="p-3">Live Resolved Value</th>
                      <th className="p-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {variables.map((v) => (
                      <tr key={v.name} className="hover:bg-muted/20 transition-colors">
                        <td className="p-3 font-mono font-semibold text-primary">{v.name}</td>
                        <td className="p-3">
                          <Badge variant="outline" className="text-[10px] uppercase font-mono">
                            {v.scope}
                          </Badge>
                        </td>
                        <td className="p-3 font-mono text-[11px] text-muted-foreground">{v.source}</td>
                        <td className="p-3">
                          <span className="font-semibold text-foreground bg-muted/60 px-2 py-0.5 rounded font-mono text-[11px]">
                            {v.resolved_value ?? '—'}
                          </span>
                        </td>
                        <td className="p-3 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => copyToClipboard(v.name)}
                            className="h-7 px-2 text-xs"
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        /* Tools View */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Tools List (4 Cols) */}
          <div className="lg:col-span-4 space-y-2">
            {tools.map((t, idx) => (
              <Card
                key={t.name}
                onClick={() => setSelectedToolIndex(idx)}
                className={`cursor-pointer transition-all border ${
                  selectedToolIndex === idx
                    ? 'border-primary bg-primary/5 ring-1 ring-primary'
                    : 'border-border/60 hover:bg-muted/40'
                }`}
              >
                <CardContent className="p-3 flex items-start justify-between">
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-1.5 font-bold font-mono text-xs text-foreground">
                      <Wrench className="h-3.5 w-3.5 text-primary" />
                      <span className="truncate">{t.name}</span>
                    </div>
                    <p className="text-[11px] text-muted-foreground line-clamp-2">{t.description}</p>
                  </div>
                  <Badge variant="outline" className="text-[9px] font-mono shrink-0 ml-2">
                    Read-Only
                  </Badge>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Tool Detail Contract Card (8 Cols) */}
          <div className="lg:col-span-8">
            {selectedTool && (
              <Card className="border-border/80 h-full">
                <CardHeader className="border-b pb-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base font-bold font-mono text-primary flex items-center gap-2">
                        <Wrench className="h-4 w-4" />
                        {selectedTool.name}
                      </CardTitle>
                      <CardDescription className="text-xs mt-1">{selectedTool.description}</CardDescription>
                    </div>
                    <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-xs py-1">
                      Server-Enforced Scope
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="p-4 space-y-4 text-xs font-mono">
                  {/* Server Invariants */}
                  <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/[0.03] space-y-1.5">
                    <span className="font-semibold text-foreground flex items-center gap-1 font-sans text-xs">
                      <Lock className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                      Authoritative Bound Parameters:
                    </span>
                    <p className="text-[11px] text-muted-foreground font-sans">
                      These parameters are resolved server-side from active session context. The LLM function schema deliberately omits them so the model cannot spoof tenant or provider boundaries.
                    </p>
                    <div className="flex gap-1.5 pt-1">
                      {selectedTool.server_enforced_scoping.map((p) => (
                        <Badge key={p} variant="secondary" className="text-[10px] font-mono">
                          🔒 {p}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Parameter Schema */}
                  <div className="space-y-1.5 font-sans">
                    <span className="font-semibold text-xs text-foreground">OpenAI Function Parameter Schema:</span>
                    <pre className="p-3 rounded-lg bg-muted text-[11px] font-mono overflow-x-auto">
                      {JSON.stringify(selectedTool.parameters, null, 2)}
                    </pre>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
