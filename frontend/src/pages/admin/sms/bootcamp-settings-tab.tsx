import { useState, useEffect, useRef } from "react";
import {
  Bot,
  Sparkles,
  Sliders,
  Save,
  RotateCcw,
  ArrowLeft,
  Info,
  BrainCircuit,
  SlidersHorizontal,
  FileCode2,
  BookOpen
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export interface BootcampStyleProfile {
  flirtiness: number; // 0 - 5
  cheerfulness: number; // 0 - 5
  wit: number; // 0 - 5
  sarcasm: number; // 0 - 5
  warmth: number; // 0 - 5
  directness: number; // 0 - 5
  chattiness: number; // 0 - 5
  patience: number; // 0 - 5
}

export interface BootcampSettingsData {
  agent_name: string;
  model: string;
  role_description: string;
  system_prompt_template: string;
  training_notes: string;
  learned_facts: string;
  active_profile: BootcampStyleProfile;
  previous_profile?: BootcampStyleProfile | null;
}

export const DEFAULT_STYLE_PROFILE: BootcampStyleProfile = {
  flirtiness: 1,
  cheerfulness: 4,
  wit: 3,
  sarcasm: 1,
  warmth: 4,
  directness: 3,
  chattiness: 2,
  patience: 4,
};

export const DEFAULT_BOOTCAMP_SETTINGS: BootcampSettingsData = {
  agent_name: "Tori",
  model: "gpt-4o-mini",
  role_description:
    "Warm, witty, and highly reliable simulated receptionist assisting customer booking inquiries and general questions.",
  system_prompt_template: `You are {agent_name}, the front-desk concierge for {business_name}.
Your behavioral traits are: {traits}.

Always remain welcoming, helpful, and concise. Prioritize booking appointments and answering customer questions accurately.
If an operational fact is unknown, escalate to staff immediately with an information request rather than guessing.`,
  training_notes: `Standard operating hours: Mon-Fri 9:00 AM - 5:00 PM, Sat 10:00 AM - 2:00 PM.
Deposit required for first-time bookings: $25.
Cancellations accepted with at least 24 hours notice.`,
  learned_facts: `• Parking is located behind the building off Elm Street (spaces 12-18).
• Wheelchair ramp entrance is available via the side courtyard.
• Wi-Fi network 'GuestNet' (no password required).`,
  active_profile: { ...DEFAULT_STYLE_PROFILE },
  previous_profile: {
    flirtiness: 0,
    cheerfulness: 3,
    wit: 2,
    sarcasm: 0,
    warmth: 3,
    directness: 4,
    chattiness: 2,
    patience: 3,
  },
};

type BootcampSettingsInput = Partial<Omit<BootcampSettingsData, "active_profile" | "previous_profile">> & {
  active_profile?: Partial<BootcampStyleProfile> | null;
  previous_profile?: Partial<BootcampStyleProfile> | null;
};

/**
 * API and local-storage settings can predate the style-profile fields. Always
 * hydrate them before rendering so a partial persona profile cannot crash the
 * behavioral-preview map.
 */
export function normalizeBootcampSettings(settings?: BootcampSettingsInput | null): BootcampSettingsData {
  return {
    ...DEFAULT_BOOTCAMP_SETTINGS,
    ...settings,
    active_profile: {
      ...DEFAULT_STYLE_PROFILE,
      ...(settings?.active_profile ?? {}),
    },
    previous_profile: settings?.previous_profile
      ? { ...DEFAULT_STYLE_PROFILE, ...settings.previous_profile }
      : null,
  };
}

const STORAGE_KEY = "fastapi_bookings_bootcamp_settings_v1";

interface BootcampSettingsTabProps {
  onBackToBootcamp?: () => void;
  initialProviderId?: number | null;
}

export default function BootcampSettingsTab({ onBackToBootcamp, initialProviderId = null }: BootcampSettingsTabProps) {
  const [providers, setProviders] = useState<{ id: number; name: string }[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<number | null>(initialProviderId);
  const [settings, setSettings] = useState<BootcampSettingsData>(() => {
    try {
      const storageKey = initialProviderId ? `${STORAGE_KEY}_prov_${initialProviderId}` : STORAGE_KEY;
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        return normalizeBootcampSettings(JSON.parse(saved));
      }
    } catch {
      // Fallback
    }
    return normalizeBootcampSettings(DEFAULT_BOOTCAMP_SETTINGS);
  });

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const promptRef = useRef<HTMLTextAreaElement>(null);

  // Fetch providers list on mount
  useEffect(() => {
    let isMounted = true;
    apiClient
      .get<any>("/api/admin/providers")
      .then((res) => {
        if (!isMounted) return;
        const list = Array.isArray(res) ? res : res?.data ?? [];
        setProviders(list);
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, []);

  // Fetch settings from API on mount and whenever selectedProviderId changes
  useEffect(() => {
    let isMounted = true;
    const fetchSettings = async () => {
      setLoading(true);
      try {
        const url = selectedProviderId !== null
          ? `/api/admin/sms/bootcamp/settings?provider_id=${selectedProviderId}`
          : "/api/admin/sms/bootcamp/settings";
        const res = await apiClient.get<any>(url);
        if (isMounted && res) {
          const normalizedSettings = normalizeBootcampSettings(res);
          setSettings(normalizedSettings);
          const storageKey = selectedProviderId ? `${STORAGE_KEY}_prov_${selectedProviderId}` : STORAGE_KEY;
          localStorage.setItem(storageKey, JSON.stringify(normalizedSettings));
        }
      } catch (err: any) {
        toast.error(err?.message || "Failed to load Bootcamp settings from server");
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    fetchSettings();
    return () => {
      isMounted = false;
    };
  }, [selectedProviderId]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        ...settings,
        provider_id: selectedProviderId,
      };
      const res = await apiClient.put<any>("/api/admin/sms/bootcamp/settings", payload);
      const normalized = res ? normalizeBootcampSettings(res) : settings;
      setSettings(normalized);
      const storageKey = selectedProviderId ? `${STORAGE_KEY}_prov_${selectedProviderId}` : STORAGE_KEY;
      localStorage.setItem(storageKey, JSON.stringify(normalized));
      toast.success("Bootcamp settings saved successfully");
    } catch (err: any) {
      toast.error(err?.message || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (window.confirm("Reset all Bootcamp settings to defaults?")) {
      setSaving(true);
      try {
        const payload = {
          ...DEFAULT_BOOTCAMP_SETTINGS,
          provider_id: selectedProviderId,
        };
        const res = await apiClient.put<any>("/api/admin/sms/bootcamp/settings", payload);
        const normalized = res ? normalizeBootcampSettings(res) : DEFAULT_BOOTCAMP_SETTINGS;
        setSettings(normalized);
        const storageKey = selectedProviderId ? `${STORAGE_KEY}_prov_${selectedProviderId}` : STORAGE_KEY;
        localStorage.setItem(storageKey, JSON.stringify(normalized));
        toast.info("Bootcamp settings reset to factory defaults");
      } catch (err: any) {
        toast.error(err?.message || "Failed to reset settings to defaults");
      } finally {
        setSaving(false);
      }
    }
  };

  const insertVariable = (variableName: string) => {
    const textarea = promptRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = settings.system_prompt_template;
    const newText = text.substring(0, start) + `{${variableName}}` + text.substring(end);
    setSettings((prev) => ({ ...prev, system_prompt_template: newText }));
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + variableName.length + 2, start + variableName.length + 2);
    }, 0);
  };

  const styleDimensions: { key: keyof BootcampStyleProfile; label: string; color: string }[] = [
    { key: "flirtiness", label: "Flirtiness", color: "bg-pink-500" },
    { key: "cheerfulness", label: "Cheerfulness", color: "bg-amber-500" },
    { key: "wit", label: "Wit", color: "bg-purple-500" },
    { key: "sarcasm", label: "Sarcasm", color: "bg-indigo-500" },
    { key: "warmth", label: "Warmth", color: "bg-rose-500" },
    { key: "directness", label: "Directness", color: "bg-blue-500" },
    { key: "chattiness", label: "Chattiness", color: "bg-teal-500" },
    { key: "patience", label: "Patience", color: "bg-emerald-500" },
  ];

  return (
    <div className="space-y-4 max-w-5xl mx-auto pb-12">
      {/* Top Banner & Navigation Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs">
        <div className="flex items-center gap-3">
          {onBackToBootcamp && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onBackToBootcamp}
              className="h-8 gap-1 text-xs"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back
            </Button>
          )}
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight">Bootcamp Agent Settings</h1>
              <Badge variant="outline" className="text-[10px] text-purple-700 bg-purple-50 border-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:border-purple-800 font-mono">
                Sandbox Isolated
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Isolated simulation settings for Tori. Changes here never modify production SMS or business calendars.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-center flex-wrap">
          {providers.length > 0 && (
            <div className="flex items-center gap-1.5 mr-1">
              <span className="text-xs text-muted-foreground font-medium">Provider:</span>
              <select
                value={selectedProviderId ?? ""}
                onChange={(e) => setSelectedProviderId(e.target.value ? Number(e.target.value) : null)}
                aria-label="Select provider"
                className="h-8 text-xs rounded-md border border-slate-200 dark:border-slate-800 bg-background px-2 py-1 font-medium text-foreground focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring cursor-pointer"
              >
                <option value="">Tenant Global</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleReset}
            disabled={loading || saving}
            className="h-8 text-xs gap-1 text-slate-600 dark:text-slate-400 hover:text-rose-600"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset Defaults
          </Button>

          <Button
            type="button"
            size="sm"
            onClick={handleSave}
            disabled={loading || saving}
            className="h-8 text-xs gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-xs"
          >
            <Save className="h-3.5 w-3.5" />
            {saving ? "Saving..." : "Save Settings"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 1. Agent Configuration */}
        <Card className="border border-slate-200 dark:border-slate-800 shadow-xs">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <BrainCircuit className="h-4 w-4 text-primary" />
                Agent Configuration
              </CardTitle>
              <Badge variant="secondary" className="text-[10px]">
                Identity
              </Badge>
            </div>
            <CardDescription className="text-xs">
              Agent identity parameters for simulation arenas.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3.5 text-xs">
            <div className="space-y-1.5">
              <Label htmlFor="agent_name" className="text-xs font-medium">
                Agent Name
              </Label>
              <Input
                id="agent_name"
                value={settings.agent_name}
                onChange={(e) => setSettings({ ...settings, agent_name: e.target.value })}
                placeholder="e.g. Tori"
                className="h-8 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="model_id" className="text-xs font-medium">
                Model Identifier
              </Label>
              <Input
                id="model_id"
                value={settings.model}
                onChange={(e) => setSettings({ ...settings, model: e.target.value })}
                placeholder="e.g. gpt-4o-mini"
                className="h-8 text-xs font-mono"
              />
              <p className="text-[11px] text-muted-foreground">
                Synthetic simulated engine or evaluation model target.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="role_desc" className="text-xs font-medium">
                Active Role Description
              </Label>
              <Textarea
                id="role_desc"
                value={settings.role_description}
                onChange={(e) => setSettings({ ...settings, role_description: e.target.value })}
                rows={3}
                placeholder="Describe Tori's core duties and role boundaries..."
                className="text-xs resize-none"
              />
            </div>
          </CardContent>
        </Card>

        {/* 2. Behavioral Settings Preview */}
        <Card className="border border-slate-200 dark:border-slate-800 shadow-xs">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Sliders className="h-4 w-4 text-purple-500" />
                Behavioral Settings Preview
              </CardTitle>
              <Badge variant="outline" className="text-[10px] text-primary border-primary/20 bg-primary/10">
                Style Lab Sync
              </Badge>
            </div>
            <CardDescription className="text-xs">
              Comparison between current active calibration and prior applied profile.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-2 text-[11px] font-semibold text-muted-foreground border-b pb-1.5">
              <span>Trait Dimension</span>
              <div className="flex justify-between">
                <span>Active (0-5)</span>
                <span>Prior (0-5)</span>
              </div>
            </div>

            <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
              {styleDimensions.map(({ key, label, color }) => {
                const activeProfile = settings?.active_profile ?? DEFAULT_STYLE_PROFILE;
                const previousProfile = settings?.previous_profile;
                const activeVal = activeProfile?.[key] ?? 0;
                const prevVal = previousProfile?.[key] ?? null;
                return (
                  <div key={key} className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800 last:border-0">
                    <span className="font-medium text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                      <span className={`h-2 w-2 rounded-full ${color}`} />
                      {label}
                    </span>
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono font-bold text-primary">
                          {activeVal} / 5
                        </span>
                        <div className="w-12 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary rounded-full transition-all"
                            style={{ width: `${(activeVal / 5) * 100}%` }}
                          />
                        </div>
                      </div>

                      <span className="font-mono text-xs text-muted-foreground w-8 text-right">
                        {prevVal !== null ? `${prevVal}` : "—"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="rounded-lg bg-primary/5 p-2.5 text-[11px] text-primary border border-primary/20 flex items-start gap-2">
              <Info className="h-4 w-4 shrink-0 text-primary mt-0.5" />
              <span>
                To tune these personality sliders with immediate feedback against customer personas, visit the Style Laboratory in Boot Camp.
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 3. System Prompt Template Editor */}
      <Card className="border border-slate-200 dark:border-slate-800 shadow-xs">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <FileCode2 className="h-4 w-4 text-emerald-500" />
              System Prompt Template
            </CardTitle>
            <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
              <Sparkles className="h-3 w-3 text-amber-500" />
              Template Variables Supported
            </div>
          </div>
          <CardDescription className="text-xs">
            The foundation instructions supplied to Tori in Boot Camp simulated runs.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2.5 text-xs">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] font-semibold text-slate-500">Insert tag:</span>
            {["agent_name", "traits", "business_name", "provider_name"].map((varName) => (
              <Button
                key={varName}
                type="button"
                variant="outline"
                size="xs"
                onClick={() => insertVariable(varName)}
                className="h-6 text-[10px] font-mono gap-1 border-dashed hover:border-primary hover:text-primary"
              >
                + &#123;{varName}&#125;
              </Button>
            ))}
          </div>

          <Textarea
            ref={promptRef}
            rows={7}
            value={settings.system_prompt_template}
            onChange={(e) => setSettings({ ...settings, system_prompt_template: e.target.value })}
            placeholder="Type your system prompt template..."
            className="font-mono text-xs leading-relaxed resize-y"
          />
        </CardContent>
      </Card>

      {/* 4. Training Notes & Learned Facts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="border border-slate-200 dark:border-slate-800 shadow-xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-amber-500" />
              Custom Training Notes
            </CardTitle>
            <CardDescription className="text-xs">
              Contextual guidance on business hours, deposit policies, and etiquette.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-xs">
            <Textarea
              rows={5}
              value={settings.training_notes}
              onChange={(e) => setSettings({ ...settings, training_notes: e.target.value })}
              placeholder="e.g. Standard operating hours, cancellation policy, deposit requirements..."
              className="text-xs resize-none"
            />
          </CardContent>
        </Card>

        <Card className="border border-slate-200 dark:border-slate-800 shadow-xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-cyan-500" />
              Bootcamp Learned Facts
            </CardTitle>
            <CardDescription className="text-xs">
              Answers captured from information requests during persona simulated conversations.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-xs">
            <Textarea
              rows={5}
              value={settings.learned_facts}
              onChange={(e) => setSettings({ ...settings, learned_facts: e.target.value })}
              placeholder="Learned facts submitted via Tori lesson requests..."
              className="text-xs resize-none font-mono"
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
