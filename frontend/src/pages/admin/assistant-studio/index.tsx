import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiClient } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import {
  Activity,
  Sliders,
  Bot,
  Sparkles,
  Database,
  DownloadCloud,
  Zap,
  ShieldCheck,
  UserCheck,
  Radio,
  MessageSquare,
  Globe,
  MonitorCheck,
} from 'lucide-react';
import { toast } from 'sonner';

import type { StudioTabKey, ChannelType, ProviderItem } from './types';
import { OverviewTab } from './tabs/overview-tab';
import { PromptComposerTab } from './tabs/prompt-composer-tab';
import { SimulatorTab } from './tabs/simulator-tab';
import { ExampleLibraryTab } from './tabs/example-library-tab';
import { KnowledgeCuratorTab } from './tabs/knowledge-curator-tab';
import { ImportCentreTab } from './tabs/import-centre-tab';
import { VariablesToolsTab } from './tabs/variables-tools-tab';
import { EvaluationSafetyTab } from './tabs/evaluation-safety-tab';

export default function AssistantStudioPage() {
  const navigate = useNavigate();
  const { tab: urlTab } = useParams<{ tab?: string }>();

  // Valid tab keys
  const validTabs: StudioTabKey[] = [
    'overview',
    'prompt-composer',
    'simulator',
    'example-library',
    'knowledge-curator',
    'import-centre',
    'variables-tools',
    'evaluation-safety',
  ];

  const currentTab: StudioTabKey = validTabs.includes(urlTab as StudioTabKey)
    ? (urlTab as StudioTabKey)
    : 'overview';

  // Provider Scoping State
  const [providers, setProviders] = useState<ProviderItem[]>([
    { id: null, name: 'Tenant Default (All Providers)', is_active: true },
  ]);
  const [selectedProviderId, setSelectedProviderId] = useState<number | null>(null);

  // Channel Neutrality Indicator & Selector
  const [activeChannel, setActiveChannel] = useState<ChannelType>('sms');

  // Load live providers from backend if reachable
  useEffect(() => {
    let isMounted = true;
    apiClient
      .get<any>('/api/admin/providers')
      .then((res) => {
        if (!isMounted) return;
        const list = Array.isArray(res) ? res : res?.data || [];
        if (list.length > 0) {
          const mapped: ProviderItem[] = [
            { id: null, name: 'Tenant Default (All Providers)', is_active: true },
            ...list.map((p: any) => ({
              id: Number(p.id),
              name: p.name || `Provider #${p.id}`,
              email: p.email,
              is_active: p.active ?? true,
            })),
          ];
          setProviders(mapped);
        }
      })
      .catch(() => {
        // Retain synthetic defaults
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleTabChange = (key: StudioTabKey) => {
    navigate(`/admin/assistant-studio/${key}`);
  };

  const selectedProvider = providers.find((p) => p.id === selectedProviderId) || providers[0];

  const tabsConfig = [
    { key: 'overview' as const, label: 'Overview', icon: Activity },
    { key: 'prompt-composer' as const, label: 'Prompt Composer', icon: Sliders },
    { key: 'simulator' as const, label: 'Simulator Sandbox', icon: Bot },
    { key: 'example-library' as const, label: 'Example Library', icon: Sparkles },
    { key: 'knowledge-curator' as const, label: 'Knowledge Curator', icon: Database },
    { key: 'import-centre' as const, label: 'Import Centre', icon: DownloadCloud },
    { key: 'variables-tools' as const, label: 'Variables & Tools', icon: Zap },
    { key: 'evaluation-safety' as const, label: 'Evaluation & Safety', icon: ShieldCheck },
  ];

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto w-full pb-16">
      {/* Top Header & Context Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="outline" className="text-primary border-primary/30 text-[11px] font-semibold uppercase tracking-wider">
              Autonomous Assistant Control
            </Badge>
            <span className="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              Runtime Active
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Assistant Studio</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Channel-neutral, multi-provider AI assistant orchestration, prompt policy hierarchy, and live tool binding.
          </p>
        </div>

        {/* Controls: Provider Selector & Channel Selector */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Provider Scoping Selector */}
          <div className="flex items-center gap-1.5 bg-card border rounded-lg p-1.5 shadow-xs">
            <UserCheck className="h-4 w-4 text-muted-foreground ml-1" />
            <select
              value={selectedProviderId ?? ''}
              onChange={(e) => {
                const val = e.target.value === '' ? null : Number(e.target.value);
                setSelectedProviderId(val);
                toast.info(
                  val
                    ? `Studio scoping switched to ${providers.find((p) => p.id === val)?.name}`
                    : 'Studio scoping switched to Tenant-Wide Default'
                );
              }}
              className="text-xs font-medium bg-transparent border-0 focus:ring-0 text-foreground cursor-pointer pr-2"
            >
              {providers.map((p) => (
                <option key={String(p.id)} value={p.id ?? ''}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* Channel Selector Pills */}
          <div className="flex items-center gap-1 bg-muted/40 p-1 rounded-lg border text-xs">
            <button
              onClick={() => setActiveChannel('sms')}
              className={`px-2.5 py-1 rounded-md transition-colors flex items-center gap-1 ${
                activeChannel === 'sms'
                  ? 'bg-card text-foreground font-semibold shadow-xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <MessageSquare className="h-3 w-3" /> SMS
            </button>
            <button
              onClick={() => setActiveChannel('whatsapp')}
              className={`px-2.5 py-1 rounded-md transition-colors flex items-center gap-1 ${
                activeChannel === 'whatsapp'
                  ? 'bg-card text-foreground font-semibold shadow-xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Radio className="h-3 w-3" /> WhatsApp
            </button>
            <button
              onClick={() => setActiveChannel('webchat')}
              className={`px-2.5 py-1 rounded-md transition-colors flex items-center gap-1 ${
                activeChannel === 'webchat'
                  ? 'bg-card text-foreground font-semibold shadow-xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Globe className="h-3 w-3" /> Webchat
            </button>
            <button
              onClick={() => setActiveChannel('simulated')}
              className={`px-2.5 py-1 rounded-md transition-colors flex items-center gap-1 ${
                activeChannel === 'simulated'
                  ? 'bg-card text-foreground font-semibold shadow-xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <MonitorCheck className="h-3 w-3" /> Simulated
            </button>
          </div>
        </div>
      </div>

      {/* Primary 8-Tab Navigation Bar */}
      <div className="border-b bg-card/40 rounded-xl p-1 shadow-xs overflow-x-auto">
        <div className="flex items-center gap-1 min-w-max">
          {tabsConfig.map((t) => {
            const Icon = t.icon;
            const isActive = currentTab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => handleTabChange(t.key)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-primary text-primary-foreground shadow-xs font-semibold'
                    : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? 'text-primary-foreground' : 'text-muted-foreground'}`} />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Panels */}
      <div>
        {currentTab === 'overview' && (
          <OverviewTab
            selectedProvider={selectedProvider}
            activeChannel={activeChannel}
            onNavigateTab={handleTabChange}
          />
        )}

        {currentTab === 'prompt-composer' && (
          <PromptComposerTab selectedProvider={selectedProvider} />
        )}

        {currentTab === 'simulator' && (
          <SimulatorTab
            selectedProvider={selectedProvider}
            activeChannel={activeChannel}
          />
        )}

        {currentTab === 'example-library' && (
          <ExampleLibraryTab selectedProvider={selectedProvider} />
        )}

        {currentTab === 'knowledge-curator' && (
          <KnowledgeCuratorTab selectedProvider={selectedProvider} />
        )}

        {currentTab === 'import-centre' && (
          <ImportCentreTab selectedProvider={selectedProvider} />
        )}

        {currentTab === 'variables-tools' && (
          <VariablesToolsTab selectedProvider={selectedProvider} />
        )}

        {currentTab === 'evaluation-safety' && (
          <EvaluationSafetyTab selectedProvider={selectedProvider} />
        )}
      </div>
    </div>
  );
}
