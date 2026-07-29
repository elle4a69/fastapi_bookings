import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Save, ArrowLeft, GripVertical, Eye, Code, ExternalLink, FileInput, Lock, Filter, CheckCircle2, Sliders } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";

const DEFAULT_MODULES = [
  { id: "location", label: "Location Selection", enabled: true },
  { id: "service", label: "Service Selection", enabled: true },
  { id: "provider", label: "Provider Selection", enabled: true },
  { id: "datetime", label: "Date & Time Slots", enabled: true },
  { id: "intake", label: "Intake Notes & Questions", enabled: true },
  { id: "client", label: "Client Details", enabled: true },
  { id: "checkout", label: "Checkout & Summary", enabled: true },
  { id: "outcome", label: "Confirmation & Receipt", enabled: true },
];

export default function BookingFormEditorPage() {
  const { formId } = useParams<{ formId: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Entities for setup relational dropdowns
  const [locations, setLocations] = useState<any[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);

  // Form Global Settings
  const [formName, setFormName] = useState("Standard Booking");
  const [formSlug, setFormSlug] = useState("standard");
  const [widgetType, setWidgetType] = useState<"full" | "modal" | "inline">("full");
  const [modules, setModules] = useState(DEFAULT_MODULES);
  const [themeJson, setThemeJson] = useState('{\n  "primaryColor": "#0d9488",\n  "borderRadius": "12px"\n}');

  // Pre-selection / Presets State
  const [presetLocationId, setPresetLocationId] = useState<string>("none");
  const [presetProviderId, setPresetProviderId] = useState<string>("none");
  const [presetServiceId, setPresetServiceId] = useState<string>("none");

  useEffect(() => {
    loadSetupData();
  }, [formId]);

  const loadSetupData = async () => {
    setLoading(true);
    try {
      const [lRes, pRes, sRes] = await Promise.all([
        apiClient.get<any>("/api/admin/locations").catch(() => []),
        apiClient.get<any>("/api/admin/providers").catch(() => []),
        apiClient.get<any>("/api/admin/services").catch(() => [])
      ]);

      const locsArr = Array.isArray(lRes) ? lRes : (lRes?.data ?? []);
      const provsArr = Array.isArray(pRes) ? pRes : (pRes?.data ?? []);
      const svcsArr = Array.isArray(sRes) ? sRes : (sRes?.data ?? []);

      setLocations(locsArr);
      setProviders(provsArr);
      setServices(svcsArr);

      if (formId && formId !== "new") {
        const formDataRes: any = await apiClient.get(`/api/admin/booking-forms/${formId}`).catch(() => null);
        const data = formDataRes?.data || formDataRes;
        if (data) {
          setFormName(data.name || "Standard Booking");
          setFormSlug(data.slug || "standard");
          setWidgetType(data.widget_type || "full");

          if (data.enabled_modules) {
            setModules(DEFAULT_MODULES.map(m => ({
              ...m,
              enabled: data.enabled_modules[m.id] ?? true
            })));
          }

          if (data.predefined_values) {
            const pv = data.predefined_values;
            if (pv.location_id) setPresetLocationId(String(pv.location_id));
            if (pv.provider_id) setPresetProviderId(String(pv.provider_id));
            if (pv.service_id) setPresetServiceId(String(pv.service_id));
          }
        }
      }
    } catch {
      toast.error("Could not load form configuration.");
    } finally {
      setLoading(false);
    }
  };

  // ── Auto-generate Form Name and URL Slug ────────────────────────────

  const updateAutoNameAndSlug = (locId: string, provId: string, svcId: string) => {
    const partsName: string[] = [];
    const partsSlug: string[] = [];

    if (locId !== "none") {
      const loc = locations.find(l => String(l.id) === locId);
      if (loc) {
        partsName.push(loc.name);
        partsSlug.push(loc.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
      }
    }

    if (provId !== "none") {
      const prov = providers.find(p => String(p.id) === provId);
      if (prov) {
        partsName.push(prov.name);
        partsSlug.push(prov.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
      }
    }

    if (svcId !== "none") {
      const svc = services.find(s => String(s.id) === svcId);
      if (svc) {
        partsName.push(svc.name);
        partsSlug.push(svc.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
      }
    }

    if (partsName.length > 0) {
      setFormName(partsName.join(" - "));
      setFormSlug(partsSlug.join("/"));
    }
  };

  const handleLocationPresetChange = (locId: string) => {
    setPresetLocationId(locId);
    setPresetProviderId("none");
    setPresetServiceId("none");
    updateAutoNameAndSlug(locId, "none", "none");
  };

  const handleProviderPresetChange = (provId: string) => {
    setPresetProviderId(provId);
    setPresetServiceId("none");
    updateAutoNameAndSlug(presetLocationId, provId, "none");
  };

  const handleServicePresetChange = (svcId: string) => {
    setPresetServiceId(svcId);
    updateAutoNameAndSlug(presetLocationId, presetProviderId, svcId);
  };

  // ── Setup Relational Cascading Filters ──────────────────────────────

  const setupAvailableProviders = providers.filter(p => {
    if (presetLocationId !== "none") {
      const loc = locations.find(l => String(l.id) === presetLocationId);
      if (loc && loc.provider_ids && loc.provider_ids.length > 0) {
        return loc.provider_ids.includes(p.id);
      }
    }
    return true;
  });

  const setupAvailableServices = services.filter(s => {
    if (presetProviderId !== "none") {
      const prov = providers.find(p => String(p.id) === presetProviderId);
      if (prov && prov.service_ids && prov.service_ids.length > 0) {
        if (!prov.service_ids.includes(s.id)) return false;
      }
      if (s.provider_ids && s.provider_ids.length > 0 && !s.provider_ids.includes(parseInt(presetProviderId))) {
        return false;
      }
    }
    if (presetLocationId !== "none") {
      const loc = locations.find(l => String(l.id) === presetLocationId);
      if (loc && loc.service_ids && loc.service_ids.length > 0) {
        if (!loc.service_ids.includes(s.id)) return false;
      }
    }
    return true;
  });

  const toggleModule = (id: string) => {
    setModules(modules.map(m => m.id === id ? { ...m, enabled: !m.enabled } : m));
  };

  const handleSaveForm = async () => {
    setSaving(true);
    try {
      const enabledModulesMap = modules.reduce((acc, m) => {
        acc[m.id] = m.enabled;
        return acc;
      }, {} as Record<string, boolean>);

      const predefinedValues = {
        location_id: presetLocationId !== "none" ? parseInt(presetLocationId) : null,
        provider_id: presetProviderId !== "none" ? parseInt(presetProviderId) : null,
        service_id: presetServiceId !== "none" ? parseInt(presetServiceId) : null,
      };

      const payload = {
        name: formName,
        slug: formSlug,
        widget_type: widgetType,
        active: true,
        module_order: modules.map(m => m.id),
        enabled_modules: enabledModulesMap,
        predefined_values: predefinedValues,
        provider_selection_mode: presetProviderId !== "none" ? "predefined" : "required"
      };

      if (formId && formId !== "new") {
        await apiClient.put(`/api/admin/booking-forms/${formId}`, payload).catch(async () => {
          return await apiClient.post("/api/admin/booking-forms", payload);
        });
      } else {
        await apiClient.post("/api/admin/booking-forms", payload);
      }

      toast.success("Booking form setup saved!");
      navigate("/admin/booking-forms");
    } catch (err: any) {
      toast.error(err.message || "Failed to save form.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center">
        <p className="text-sm text-muted-foreground font-medium">Loading form editor setup...</p>
      </div>
    );
  }

  const lockedLocName = presetLocationId !== "none" ? locations.find(l => String(l.id) === presetLocationId)?.name : null;
  const lockedProvName = presetProviderId !== "none" ? providers.find(p => String(p.id) === presetProviderId)?.name : null;
  const lockedSvcName = presetServiceId !== "none" ? services.find(s => String(s.id) === presetServiceId)?.name : null;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-background">
      {/* ── Top Header Bar ────────────────────────────────────────── */}
      <div className="flex items-center justify-between border-b p-4 bg-card shrink-0 shadow-xs">
        <div className="flex items-center gap-3">
          <Link to="/admin/booking-forms">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-lg font-bold flex items-center gap-2">
              <FileInput className="w-5 h-5 text-primary" /> Setup Booking Form: {formName}
            </h1>
            <p className="text-xs text-muted-foreground">Configure pre-selections, relational constraints, and customer workflow.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <a href={`/book/${formSlug}`} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm" className="gap-1.5 h-9">
              <Eye className="w-4 h-4" /> Test Public Form <ExternalLink className="w-3 h-3 ml-0.5" />
            </Button>
          </a>
          <Button onClick={handleSaveForm} disabled={saving} className="gap-1.5 h-9 font-semibold">
            <Save className="w-4 h-4" /> {saving ? "Saving..." : "Save Setup"}
          </Button>
        </div>
      </div>

      {/* ── Main 3-Column Layout ──────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Column: Module Toggles & Order */}
        <div className="w-72 border-r bg-muted/20 p-5 overflow-y-auto shrink-0">
          <h2 className="font-bold text-xs uppercase tracking-wider text-muted-foreground mb-4">
            Module Layout & Order
          </h2>
          <div className="space-y-2.5">
            {modules.map((module) => {
              const isLockedByPreset = 
                (module.id === "location" && presetLocationId !== "none") ||
                (module.id === "provider" && presetProviderId !== "none") ||
                (module.id === "service" && presetServiceId !== "none");

              return (
                <div
                  key={module.id}
                  className={`flex items-center justify-between p-3 rounded-xl border transition-all ${
                    isLockedByPreset 
                      ? "bg-amber-500/10 border-amber-500/30" 
                      : module.enabled 
                      ? "bg-card shadow-2xs border-border" 
                      : "bg-muted/40 opacity-60 border-dashed"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {isLockedByPreset ? (
                      <Lock className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                    ) : (
                      <GripVertical className="h-4 w-4 text-muted-foreground cursor-grab shrink-0" />
                    )}
                    <span className="text-xs font-semibold truncate">{module.label}</span>
                  </div>
                  {isLockedByPreset ? (
                    <Badge variant="outline" className="text-[9px] bg-amber-500/20 text-amber-700 border-amber-300">
                      Bypassed
                    </Badge>
                  ) : (
                    <Switch
                      checked={module.enabled}
                      onCheckedChange={() => toggleModule(module.id)}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Center Column: Live Layout & Presets Preview */}
        <div className="flex-1 bg-muted/10 p-6 overflow-y-auto">
          <div className="max-w-xl mx-auto space-y-4">
            <div className="text-center space-y-1">
              <span className="text-xs font-bold uppercase tracking-wider text-primary bg-primary/10 px-2.5 py-1 rounded-full">
                Form Setup Preview ({widgetType === 'full' ? 'Full Page' : widgetType === 'modal' ? 'Modal Popup' : 'Inline'})
              </span>
              <h2 className="text-xl font-bold pt-1">{formName}</h2>
              <p className="text-xs text-muted-foreground">What the customer sees when accessing this pre-configured form</p>
            </div>

            {/* Presets Locked Banner Preview */}
            {(lockedLocName || lockedProvName || lockedSvcName) && (
              <div className="p-4 rounded-xl border bg-amber-50 dark:bg-amber-950/30 border-amber-300 text-amber-900 dark:text-amber-200 text-xs space-y-1 shadow-2xs">
                <div className="font-bold flex items-center gap-1.5">
                  <Lock className="w-4 h-4 text-amber-600" /> Active Form Pre-selections (Bypassed for Customer)
                </div>
                <div className="flex flex-wrap gap-2 pt-1">
                  {lockedLocName && <Badge className="bg-amber-200 text-amber-900 border-amber-300 font-semibold">Location: {lockedLocName}</Badge>}
                  {lockedProvName && <Badge className="bg-amber-200 text-amber-900 border-amber-300 font-semibold">Provider: {lockedProvName}</Badge>}
                  {lockedSvcName && <Badge className="bg-amber-200 text-amber-900 border-amber-300 font-semibold">Service: {lockedSvcName}</Badge>}
                </div>
                <p className="text-[11px] text-amber-700 dark:text-amber-400 pt-1">
                  Customers landing on this form will bypass these pre-selected steps and land directly on the remaining steps below!
                </p>
              </div>
            )}

            {/* Customer Layout Steps Preview */}
            <div className="bg-card border rounded-2xl shadow-md p-6 space-y-4">
              {modules.filter(m => {
                if (!m.enabled) return false;
                if (m.id === "location" && presetLocationId !== "none") return false;
                if (m.id === "provider" && presetProviderId !== "none") return false;
                if (m.id === "service" && presetServiceId !== "none") return false;
                return true;
              }).map((module, idx) => (
                <div key={`preview-${module.id}`} className="p-4 rounded-xl border bg-muted/20 space-y-1.5">
                  <div className="font-bold text-xs text-primary flex items-center justify-between">
                    <span>Step {idx + 1}: {module.label}</span>
                    <span className="text-[10px] text-muted-foreground font-normal">Customer Action Required</span>
                  </div>
                  <div className="h-10 bg-background rounded-lg border border-dashed flex items-center justify-center text-xs text-muted-foreground font-medium">
                    [ Customer Selects {module.label} ]
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Pre-selections & Settings */}
        <div className="w-80 border-l bg-card p-5 overflow-y-auto shrink-0 space-y-6 flex flex-col justify-between">
          <div className="space-y-6">
            {/* ── Pre-selections Section ──────────────────────────── */}
            <div className="space-y-4">
              <h2 className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Sliders className="w-4 h-4 text-primary" /> Relational Pre-selections
              </h2>
              <p className="text-[11px] text-muted-foreground">
                Pre-select a Location, Provider, or Service. Selecting a location automatically filters providers at that location and generates the form name and slug.
              </p>

              {/* Step 1: Pre-select Location */}
              <div className="space-y-1.5">
                <Label className="text-xs font-bold text-foreground">1. Pre-select Location</Label>
                <Select value={presetLocationId} onValueChange={handleLocationPresetChange}>
                  <SelectTrigger className="h-9 text-xs"><SelectValue placeholder="None (Customer chooses)" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None (Customer chooses)</SelectItem>
                    {locations.map(l => <SelectItem key={l.id} value={String(l.id)}>{l.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              {/* Step 2: Pre-select Provider */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <Label className="text-xs font-bold text-foreground">2. Pre-select Provider</Label>
                  <Badge variant="outline" className="text-[9px]">{setupAvailableProviders.length} Available</Badge>
                </div>
                <Select value={presetProviderId} onValueChange={handleProviderPresetChange}>
                  <SelectTrigger className="h-9 text-xs"><SelectValue placeholder="None (Customer chooses)" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None (Customer chooses)</SelectItem>
                    {setupAvailableProviders.map(p => <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>

              {/* Step 3: Pre-select Service */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <Label className="text-xs font-bold text-foreground">3. Pre-select Service</Label>
                  <Badge variant="outline" className="text-[9px]">{setupAvailableServices.length} Available</Badge>
                </div>
                <Select value={presetServiceId} onValueChange={handleServicePresetChange}>
                  <SelectTrigger className="h-9 text-xs"><SelectValue placeholder="None (Customer chooses)" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None (Customer chooses)</SelectItem>
                    {setupAvailableServices.map(s => <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* General Form Options */}
            <div className="border-t pt-5 space-y-4">
              <h2 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
                General Form Options
              </h2>

              <div className="space-y-1.5">
                <Label htmlFor="ed_name" className="text-xs font-semibold">Form Name (Auto-generated)</Label>
                <Input
                  id="ed_name"
                  value={formName}
                  onChange={e => setFormName(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="ed_slug" className="text-xs font-semibold">URL Slug (Auto-generated)</Label>
                <div className="flex">
                  <span className="inline-flex items-center px-2.5 rounded-l-md border border-r-0 bg-muted text-muted-foreground text-xs font-mono">
                    /book/
                  </span>
                  <Input
                    id="ed_slug"
                    className="rounded-l-none h-9 text-xs font-mono"
                    value={formSlug}
                    onChange={e => setFormSlug(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="ed_widget" className="text-xs font-semibold">Widget Display Mode</Label>
                <select
                  id="ed_widget"
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-2xs"
                  value={widgetType}
                  onChange={e => setWidgetType(e.target.value as any)}
                >
                  <option value="full">Full Page (Standard)</option>
                  <option value="modal">Modal Popup</option>
                  <option value="inline">Inline Embedded Form</option>
                </select>
              </div>
            </div>
          </div>

          {/* ── Save Form Setup Button at Bottom ──────────────────── */}
          <div className="pt-6 border-t mt-6 shrink-0">
            <Button
              onClick={handleSaveForm}
              disabled={saving}
              className="w-full h-11 text-sm font-bold gap-2 bg-primary text-primary-foreground shadow-md hover:shadow-lg transition-all"
            >
              <Save className="w-4 h-4" /> {saving ? "Saving Setup..." : "Save Form Setup"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
