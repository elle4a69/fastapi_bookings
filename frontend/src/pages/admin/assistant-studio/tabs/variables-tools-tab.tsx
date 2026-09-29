import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Code,
  Wrench,
  Lock,
  CheckCircle2,
  Copy,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import type { LiveToolItem, ProviderItem, VariableItem } from '../types';

interface VariablesToolsTabProps {
  selectedProvider: ProviderItem | null;
}

export const VariablesToolsTab: React.FC<VariablesToolsTabProps> = ({ selectedProvider }) => {
  const [activeSection, setActiveSection] = useState<'variables' | 'tools'>('tools');
  const [selectedToolIndex, setSelectedToolIndex] = useState(0);

  const variables: VariableItem[] = [
    {
      name: '{{business_name}}',
      scope: 'tenant',
      source: 'Tenant.name',
      resolved_value: 'Sydney Wellness & Recovery Clinic',
      description: 'The primary operating trade name of the active clinic.',
    },
    {
      name: '{{provider_name}}',
      scope: 'provider',
      source: 'Provider.name',
      resolved_value: selectedProvider?.name || 'Dr. Alex Mercer',
      description: 'The currently selected practitioner or default clinic provider.',
    },
    {
      name: '{{location_name}}',
      scope: 'runtime',
      source: 'Location.name',
      resolved_value: 'CBD Main Clinic',
      description: 'Operating premises name associated with the conversation.',
    },
    {
      name: '{{location_address}}',
      scope: 'runtime',
      source: 'Location.address',
      resolved_value: 'Suite 4, 120 Castlereagh St, Sydney NSW 2000',
      description: 'Physical street address for clinic visits and directions.',
    },
    {
      name: '{{channel}}',
      scope: 'system',
      source: 'RuntimeContext.channel_type',
      resolved_value: 'sms',
      description: 'Active inbound transport protocol (sms, whatsapp, webchat).',
    },
    {
      name: '{{current_date}}',
      scope: 'runtime',
      source: 'ZoneInfo("Australia/Sydney")',
      resolved_value: '2026-09-29',
      description: 'Location-aware local calendar date for temporal reasoning.',
    },
    {
      name: '{{current_time}}',
      scope: 'runtime',
      source: 'ZoneInfo("Australia/Sydney")',
      resolved_value: '04:35 PM',
      description: 'Location-aware local clock time.',
    },
    {
      name: '{{booking_link}}',
      scope: 'tenant',
      source: 'Tenant.slug + public_route',
      resolved_value: 'https://bookings.app/sydney-wellness/book',
      description: 'Direct authenticated portal booking link.',
    },
  ];

  const tools: LiveToolItem[] = [
    {
      name: 'check_availability',
      description:
        'Calculates real-time availability slots using 5-segment operational windows, practitioner workdays, and existing holds.',
      server_bound_params: ['tenant_id', 'provider_id', 'location_id'],
      client_allowed_params: ['service_id', 'start_date', 'end_date', 'duration_minutes'],
      execution_mode: 'read_only',
      example_input: {
        service_id: 301,
        start_date: '2026-09-30',
        end_date: '2026-09-30',
      },
      example_output: {
        available_slots: [
          { start: '10:00', end: '11:00' },
          { start: '14:00', end: '15:00' },
          { start: '16:30', end: '17:30' },
        ],
        buffer_minutes: 15,
        timezone: 'Australia/Sydney',
      },
    },
    {
      name: 'quote_travel',
      description:
        'Computes dual-route transit distance, chargeable road travel fees, and operational window duration for mobile bookings.',
      server_bound_params: ['tenant_id', 'provider_id', 'origin_location_id'],
      client_allowed_params: ['destination_postcode', 'client_suburb', 'client_address'],
      execution_mode: 'read_only',
      example_input: {
        destination_postcode: '2026',
        client_suburb: 'Bondi Beach',
      },
      example_output: {
        chargeable_distance_km: 8.4,
        transit_duration_mins: 22,
        operational_window_mins: 45,
        travel_fee_aud: 35.0,
        within_operating_radius: true,
      },
    },
    {
      name: 'service_lookup',
      description:
        'Searches and returns tenant-isolated services, durations, prices, and required preparatory instructions.',
      server_bound_params: ['tenant_id'],
      client_allowed_params: ['service_id', 'query', 'category_id'],
      execution_mode: 'read_only',
      example_input: { query: 'physiotherapy' },
      example_output: {
        services: [
          { id: 301, name: 'Initial Assessment', duration_min: 60, price_aud: 160.0 },
          { id: 302, name: 'Follow-Up Treatment', duration_min: 45, price_aud: 120.0 },
        ],
      },
    },
    {
      name: 'provider_lookup',
      description:
        'Retrieves verified practitioner profiles, specialties, and bio details strictly within the authenticated tenant.',
      server_bound_params: ['tenant_id'],
      client_allowed_params: ['provider_id', 'query'],
      example_input: { query: 'Alex' },
      example_output: {
        providers: [
          {
            id: 101,
            name: 'Dr. Alex Mercer',
            specialties: ['Sports Rehab', 'Spinal Manipulation'],
            is_active: true,
          },
        ],
      },
      execution_mode: 'read_only',
    },
    {
      name: 'address_validation',
      description:
        'Validates Australian street addresses and postal centroids to ensure they fall within the provider’s travel boundary.',
      server_bound_params: ['tenant_id'],
      client_allowed_params: ['postcode', 'suburb', 'street_address'],
      example_input: { postcode: '2026', suburb: 'Bondi Beach' },
      example_output: {
        is_valid: true,
        state: 'NSW',
        centroid_lat: -33.891,
        centroid_lon: 151.277,
        serviceable: true,
      },
      execution_mode: 'read_only',
    },
  ];

  const copyVariable = (name: string) => {
    navigator.clipboard.writeText(name);
    toast.success(`Copied ${name} to clipboard!`);
  };

  const currentTool = tools[selectedToolIndex];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b">
        <div>
          <h2 className="text-xl font-bold tracking-tight flex items-center gap-2">
            <Zap className="h-5 w-5 text-primary" />
            Live Variables & Server-Enforced Tools
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Interpolation dictionary and allowlisted live tools with server-side tenant/provider binding.
          </p>
        </div>

        {/* Section Toggle */}
        <div className="flex items-center gap-1 p-1 rounded-lg border bg-muted/30 text-xs">
          <button
            onClick={() => setActiveSection('tools')}
            className={`px-3 py-1.5 rounded-md font-medium transition-colors flex items-center gap-1.5 ${
              activeSection === 'tools'
                ? 'bg-card text-foreground shadow-xs font-semibold'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Wrench className="h-3.5 w-3.5" />
            Tool Catalog (5)
          </button>
          <button
            onClick={() => setActiveSection('variables')}
            className={`px-3 py-1.5 rounded-md font-medium transition-colors flex items-center gap-1.5 ${
              activeSection === 'variables'
                ? 'bg-card text-foreground shadow-xs font-semibold'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Code className="h-3.5 w-3.5" />
            Variable Dictionary ({variables.length})
          </button>
        </div>
      </div>

      {/* SECTION 1: Tools */}
      {activeSection === 'tools' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Tool List (4 cols) */}
          <div className="lg:col-span-4 space-y-2">
            <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              Server-Enforced Tools
            </div>
            {tools.map((t, idx) => (
              <div
                key={t.name}
                onClick={() => setSelectedToolIndex(idx)}
                className={`p-3 rounded-lg border cursor-pointer transition-all ${
                  selectedToolIndex === idx
                    ? 'border-primary bg-primary/5 shadow-xs'
                    : 'bg-card hover:bg-muted/30 border-border/70'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-foreground">{t.name}()</span>
                  <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                    Read-Only
                  </Badge>
                </div>
                <p className="text-[11px] text-muted-foreground line-clamp-2 mt-1">{t.description}</p>
              </div>
            ))}

            <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-900 dark:text-blue-300 text-xs space-y-1 mt-4">
              <div className="flex items-center gap-1 font-semibold">
                <ShieldCheck className="h-4 w-4" />
                <span>Anti-Spoofing Architecture</span>
              </div>
              <p className="text-[11px] leading-relaxed text-muted-foreground dark:text-blue-200/80">
                The model cannot supply <code>tenant_id</code> or <code>provider_id</code>. All execution calls forcefully bind these values directly from the authenticated session context.
              </p>
            </div>
          </div>

          {/* Right Column: Tool Detail & JSON Spec (8 cols) */}
          <div className="lg:col-span-8">
            <Card className="border-border/70">
              <CardHeader className="pb-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <CardTitle className="text-lg font-mono font-bold flex items-center gap-2">
                      <Wrench className="h-5 w-5 text-primary" />
                      {currentTool.name}()
                    </CardTitle>
                    <CardDescription className="text-xs mt-1">{currentTool.description}</CardDescription>
                  </div>
                  <Badge variant="secondary" className="font-mono text-xs self-start sm:self-auto">
                    Tier 2 Live Ground Truth
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4 text-xs">
                {/* Server-bound vs Client-allowed parameters */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="p-3 rounded-lg bg-red-500/[0.04] border border-red-500/30 space-y-1.5">
                    <span className="font-bold text-red-600 dark:text-red-400 text-xs flex items-center gap-1">
                      <Lock className="h-3.5 w-3.5" /> Server-Bound (Stripped from LLM)
                    </span>
                    <p className="text-[11px] text-muted-foreground">
                      Parameters forcefully resolved by backend:
                    </p>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {currentTool.server_bound_params.map((p) => (
                        <Badge key={p} variant="outline" className="font-mono text-[10px] bg-card text-foreground">
                          {p}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-emerald-500/[0.04] border border-emerald-500/30 space-y-1.5">
                    <span className="font-bold text-emerald-600 dark:text-emerald-400 text-xs flex items-center gap-1">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Client-Allowed Arguments
                    </span>
                    <p className="text-[11px] text-muted-foreground">
                      Parameters LLM may formulate:
                    </p>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {currentTool.client_allowed_params.map((p) => (
                        <Badge key={p} variant="outline" className="font-mono text-[10px] bg-card text-foreground">
                          {p}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Example Payload */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <span className="font-semibold text-xs block mb-1 text-muted-foreground">
                      Sample Input Arguments
                    </span>
                    <pre className="p-3 rounded-lg bg-muted/40 border font-mono text-[11px] text-muted-foreground overflow-x-auto">
                      {JSON.stringify(currentTool.example_input, null, 2)}
                    </pre>
                  </div>

                  <div>
                    <span className="font-semibold text-xs block mb-1 text-muted-foreground">
                      Authoritative Return Payload
                    </span>
                    <pre className="p-3 rounded-lg bg-card border font-mono text-[11px] text-foreground overflow-x-auto shadow-xs">
                      {JSON.stringify(currentTool.example_output, null, 2)}
                    </pre>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* SECTION 2: Variables Dictionary */}
      {activeSection === 'variables' && (
        <Card className="border-border/70">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Code className="h-4 w-4 text-primary" />
              Interpolation Variable Dictionary
            </CardTitle>
            <CardDescription className="text-xs">
              All registered placeholders supported in prompts, policies, and notifications.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b bg-muted/40 text-muted-foreground">
                    <th className="p-3 font-semibold">Placeholder</th>
                    <th className="p-3 font-semibold">Scope</th>
                    <th className="p-3 font-semibold">Resolver Source</th>
                    <th className="p-3 font-semibold">Resolved Value (Current Scope)</th>
                    <th className="p-3 font-semibold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {variables.map((v) => (
                    <tr key={v.name} className="hover:bg-muted/20 transition-colors">
                      <td className="p-3 font-mono font-bold text-primary">{v.name}</td>
                      <td className="p-3">
                        <Badge variant="secondary" className="capitalize text-[10px]">
                          {v.scope}
                        </Badge>
                      </td>
                      <td className="p-3 font-mono text-muted-foreground text-[11px]">{v.source}</td>
                      <td className="p-3 font-medium text-foreground">
                        <span className="bg-muted/40 px-2 py-0.5 rounded border border-border/50">
                          {v.resolved_value}
                        </span>
                      </td>
                      <td className="p-3 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyVariable(v.name)}
                          className="h-7 px-2 text-xs gap-1"
                        >
                          <Copy className="h-3 w-3" />
                          Copy
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
