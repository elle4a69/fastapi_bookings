import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Save, ArrowLeft, GripVertical, Eye, Code, ExternalLink, FileInput, Lock, Filter, CheckCircle2, Sliders, ChevronUp, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";

const DEFAULT_MODULES = [
  { id: "location", label: "Location Selection", enabled: true },
  { id: "provider", label: "Provider Selection", enabled: true },
  { id: "service", label: "Service Selection", enabled: true },
  { id: "addons", label: "Service Add-ons", enabled: true },
  { id: "products", label: "Products & Packages", enabled: true },
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

  // Drag and drop state
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);

  // Entities for setup relational dropdowns
  const [locations, setLocations] = useState<any[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);

  // Form Global Settings
  const [formName, setFormName] = useState("Standard Booking");
  const [formSlug, setFormSlug] = useState("standard");
  const [widgetType, setWidgetType] = useState<"full" | "modal" | "inline">("full");
  const [modules, setModules] = useState(DEFAULT_MODULES);

  // Client Contact Field Configuration
  const [primaryIdentifier, setPrimaryIdentifier] = useState<"email" | "phone" | "both">("email");
  const [showEmailField, setShowEmailField] = useState(true);
  const [showPhoneField, setShowPhoneField] = useState(true);

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

          const storageKey = `booking_form_modules_${formId || 'default'}`;
          const localOrderRaw = localStorage.getItem(storageKey);
          let localOrderIds: string[] | null = null;
          if (localOrderRaw) {
            try { localOrderIds = JSON.parse(localOrderRaw); } catch {}
          }

          const loadedOrder: string[] = (data.module_order && Array.isArray(data.module_order) && data.module_order.length > 0)
            ? data.module_order
            : (localOrderIds || DEFAULT_MODULES.map(m => m.id));

          const orderedList: typeof DEFAULT_MODULES = [];

          // Add loaded modules in saved order
          loadedOrder.forEach(modId => {
            const defaultDef = DEFAULT_MODULES.find(m => m.id === modId);
            if (defaultDef) {
              orderedList.push({
                ...defaultDef,
                enabled: data.enabled_modules ? (data.enabled_modules[modId] ?? true) : true
              });
            }
          });

          // Append any new default modules not present in saved order
          DEFAULT_MODULES.forEach(def => {
            if (!orderedList.some(m => m.id === def.id)) {
              orderedList.push({
                ...def,
                enabled: data.enabled_modules ? (data.enabled_modules[def.id] ?? true) : true
              });
            }
          });

          setModules(orderedList);

          if (data.predefined_values) {
            const pv = data.predefined_values;
            setPresetLocationId(pv.location_id && String(pv.location_id) !== "none" && String(pv.location_id) !== "null" ? String(pv.location_id) : "none");
            setPresetProviderId(pv.provider_id && String(pv.provider_id) !== "none" && String(pv.provider_id) !== "null" ? String(pv.provider_id) : "none");
            setPresetServiceId(pv.service_id && String(pv.service_id) !== "none" && String(pv.service_id) !== "null" ? String(pv.service_id) : "none");
          } else {
            setPresetLocationId("none");
            setPresetProviderId("none");
            setPresetServiceId("none");
          }

          if (data.settings) {
            if (data.settings.primary_identifier) setPrimaryIdentifier(data.settings.primary_identifier);
            if (data.settings.show_email_field !== undefined) setShowEmailField(data.settings.show_email_field);
            if (data.settings.show_phone_field !== undefined) setShowPhoneField(data.settings.show_phone_field);
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

  const handleLocationPresetChange = async (locId: string) => {
    setPresetLocationId(locId);
    setPresetProviderId("none");
    setPresetServiceId("none");
    updateAutoNameAndSlug(locId, "none", "none");
    await persistPresetChanges(locId, "none", "none");
  };

  const handleProviderPresetChange = async (provId: string) => {
    setPresetProviderId(provId);
    setPresetServiceId("none");
    updateAutoNameAndSlug(presetLocationId, provId, "none");
    await persistPresetChanges(presetLocationId, provId, "none");
  };

  const handleServicePresetChange = async (svcId: string) => {
    setPresetServiceId(svcId);
    updateAutoNameAndSlug(presetLocationId, presetProviderId, svcId);
    await persistPresetChanges(presetLocationId, presetProviderId, svcId);
  };

  const persistPresetChanges = async (locId: string, provId: string, svcId: string) => {
    if (formId && formId !== "new") {
      try {
        const predefinedValues = {
          location_id: locId !== "none" ? parseInt(locId) : null,
          provider_id: provId !== "none" ? parseInt(provId) : null,
          service_id: svcId !== "none" ? parseInt(svcId) : null,
        };
        await apiClient.put(`/api/admin/booking-forms/${formId}`, {
          name: formName,
          slug: formSlug,
          widget_type: widgetType,
          active: true,
          module_order: modules.map(m => m.id),
          enabled_modules: modules.reduce((acc, m) => { acc[m.id] = m.enabled; return acc; }, {} as Record<string, boolean>),
          predefined_values: predefinedValues,
          provider_selection_mode: provId !== "none" ? "predefined" : "required",
        });
        toast.success("Pre-selection settings saved!");
      } catch {}
    }
  };

  // Logical Stages for Database & Booking Contract Safety
  const MODULE_STAGE_MAP: Record<string, number> = {
    location: 1,
    category: 1,
    service: 1,
    addons: 1,
    products: 1,
    provider: 1,
    datetime: 1,
    intake: 1,
    client: 2,
    checkout: 2,
    outcome: 3, // Confirmation & Receipt MUST ALWAYS BE LAST STAGE!
  };

  const moveModuleWithConstraints = async (currentIndex: number, targetIndex: number) => {
    if (targetIndex < 0 || targetIndex >= modules.length) return;

    const candidate = [...modules];
    const [movedItem] = candidate.splice(currentIndex, 1);
    candidate.splice(targetIndex, 0, movedItem);

    // Validate stage ordering constraint: Stage(N) <= Stage(N+1)
    let isValid = true;
    for (let i = 0; i < candidate.length - 1; i++) {
      const stageA = MODULE_STAGE_MAP[candidate[i].id] ?? 1;
      const stageB = MODULE_STAGE_MAP[candidate[i + 1].id] ?? 1;
      if (stageA > stageB) {
        isValid = false;
        break;
      }
    }

    if (!isValid) {
      toast.error("Invalid workflow order! (Selections must precede Client info, and Confirmation must remain last).");
      return;
    }

    setModules(candidate);
    await persistModuleChanges(candidate);
  };

  const moveModule = (index: number, direction: number) => {
    moveModuleWithConstraints(index, index + direction);
  };

  const toggleModule = async (id: string) => {
    const updated = modules.map(m => m.id === id ? { ...m, enabled: !m.enabled } : m);
    setModules(updated);
    await persistModuleChanges(updated);
  };

  const persistModuleChanges = async (updatedModules: typeof DEFAULT_MODULES) => {
    const moduleOrderIds = updatedModules.map(m => m.id);
    const enabledMap = updatedModules.reduce((acc, m) => {
      acc[m.id] = m.enabled;
      return acc;
    }, {} as Record<string, boolean>);

    try {
      const storageKey = `booking_form_modules_${formId || 'default'}`;
      localStorage.setItem(storageKey, JSON.stringify(moduleOrderIds));
    } catch {}

    if (formId && formId !== "new") {
      try {
        await apiClient.put(`/api/admin/booking-forms/${formId}`, {
          name: formName,
          slug: formSlug,
          widget_type: widgetType,
          active: true,
          module_order: moduleOrderIds,
          enabled_modules: enabledMap,
          predefined_values: {
            location_id: presetLocationId !== "none" ? parseInt(presetLocationId) : null,
            provider_id: presetProviderId !== "none" ? parseInt(presetProviderId) : null,
            service_id: presetServiceId !== "none" ? parseInt(presetServiceId) : null,
          },
          provider_selection_mode: presetProviderId !== "none" ? "predefined" : "required",
        });
        toast.success("Module order saved persistently!");
      } catch {}
    }
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
        provider_selection_mode: presetProviderId !== "none" ? "predefined" : "required",
        settings: {
          primary_identifier: primaryIdentifier,
          show_email_field: showEmailField,
          show_phone_field: showPhoneField,
        }
      };

      if (formId && formId !== "new") {
        await apiClient.put(`/api/admin/booking-forms/${formId}`, payload).catch(async () => {
          return await apiClient.post("/api/admin/booking-forms", payload);
        });
      } else {
        const existingForms: any = await apiClient.get("/api/admin/booking-forms").catch(() => []);
        const formsList = Array.isArray(existingForms) ? existingForms : (existingForms?.data ?? []);
        const found = formsList.find((f: any) => f.slug === formSlug);
        if (found) {
          await apiClient.put(`/api/admin/booking-forms/${found.id}`, payload);
        } else {
          await apiClient.post("/api/admin/booking-forms", payload);
        }
      }

      toast.success("Booking form setup saved with reordered layout!");
      navigate("/admin/booking-forms");
    } catch (err: any) {
      toast.error(err.message || "Failed to save form.");
    } finally {
      setSaving(false);
    }
  };

  const queryParamsString = (() => {
    const params = new URLSearchParams();
    if (presetLocationId !== "none") params.set("location_id", presetLocationId);
    if (presetProviderId !== "none") params.set("provider_id", presetProviderId);
    if (presetServiceId !== "none") params.set("service_id", presetServiceId);
    const q = params.toString();
    return q ? `?${q}` : "";
  })();

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
            <p className="text-xs text-muted-foreground">Configure pre-selections, drag to reorder modules, and save workflow.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <a href={`/book/${formSlug}${queryParamsString}`} target="_blank" rel="noopener noreferrer">
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
        {/* Left Column: Module Toggles & Reorder */}
        <div className="w-80 border-r bg-muted/20 p-5 overflow-y-auto shrink-0">
          <div className="mb-4">
            <h2 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
              Module Layout & Order
            </h2>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Drag grab handles or use arrows to reorder workflow sequence.
            </p>
          </div>

          <div className="space-y-2">
            {modules.map((module, idx) => {
              const isLockedByPreset = 
                (module.id === "location" && presetLocationId !== "none") ||
                (module.id === "provider" && presetProviderId !== "none") ||
                (module.id === "service" && presetServiceId !== "none");

              return (
                <div
                  key={module.id}
                  draggable
                  onDragStart={(e) => {
                    setDraggedIndex(idx);
                    e.dataTransfer.effectAllowed = "move";
                    e.dataTransfer.setData("text/plain", String(idx));
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    if (draggedIndex === null || draggedIndex === idx) return;
                    moveModuleWithConstraints(draggedIndex, idx);
                    setDraggedIndex(null);
                  }}
                  className={`flex items-center justify-between p-2.5 rounded-xl border transition-all ${
                    draggedIndex === idx
                      ? "opacity-40 border-primary ring-2 ring-primary/20 scale-[0.98]"
                      : isLockedByPreset 
                      ? "bg-amber-500/10 border-amber-500/30" 
                      : module.enabled 
                      ? "bg-card shadow-2xs border-border" 
                      : "bg-muted/40 opacity-60 border-dashed"
                  }`}
                >
                  <div className="flex items-center gap-1.5 min-w-0">
                    <div className="flex flex-col gap-0.5 shrink-0">
                      <button
                        type="button"
                        onClick={() => moveModule(idx, -1)}
                        disabled={idx === 0}
                        className="p-0.5 hover:bg-muted rounded disabled:opacity-30"
                        title="Move Up"
                      >
                        <ChevronUp className="h-3 w-3 text-muted-foreground" />
                      </button>
                      <button
                        type="button"
                        onClick={() => moveModule(idx, 1)}
                        disabled={idx === modules.length - 1}
                        className="p-0.5 hover:bg-muted rounded disabled:opacity-30"
                        title="Move Down"
                      >
                        <ChevronDown className="h-3 w-3 text-muted-foreground" />
                      </button>
                    </div>

                    {isLockedByPreset ? (
                      <Lock className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                    ) : (
                      <div className="cursor-grab active:cursor-grabbing p-0.5 hover:bg-muted rounded shrink-0">
                        <GripVertical className="h-4 w-4 text-muted-foreground" />
                      </div>
                    )}
                    <span className="text-xs font-semibold truncate">{module.label}</span>
                  </div>

                  {isLockedByPreset ? (
                    <Badge variant="outline" className="text-[9px] bg-amber-500/20 text-amber-700 border-amber-300 shrink-0">
                      Bypassed
                    </Badge>
                  ) : (
                    <Switch
                      checked={module.enabled}
                      onCheckedChange={() => toggleModule(module.id)}
                      className="shrink-0"
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
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <span className="text-xs font-bold uppercase tracking-wider text-primary bg-primary/10 px-2.5 py-1 rounded-full">
                  Live Form Preview ({widgetType === 'full' ? 'Full Page' : widgetType === 'modal' ? 'Modal Popup' : 'Inline'})
                </span>
                <h2 className="text-xl font-bold pt-1">{formName}</h2>
              </div>
              <Badge variant="outline" className="bg-card text-xs font-semibold py-1 px-3 border border-border shadow-2xs">
                Slug: /book/{formSlug}{queryParamsString}
              </Badge>
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
                  Customers landing on this form will bypass pre-selected steps and land directly on the remaining steps below!
                </p>
              </div>
            )}

            {/* Live Interactive iFrame Booking Engine Embed */}
            <div className="bg-card border rounded-2xl shadow-md overflow-hidden min-h-[620px]">
              <iframe
                key={`${formSlug}-${presetLocationId}-${presetProviderId}-${presetServiceId}`}
                src={`/book/${formSlug}${queryParamsString}`}
                className="w-full h-[620px] border-0"
                title="Live Booking Form Preview"
              />
            </div>
            
            {/* Embed Code Box */}
            <div className="mt-6 p-4 bg-black text-white rounded-lg font-mono text-[11px] overflow-x-auto">
              {`<iframe src="${window.location.origin}/book/${formSlug}${queryParamsString}" width="100%" height="600" frameborder="0"></iframe>`}
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

              {/* ── Client Identity & Contact Field Settings ────────────── */}
              <div className="space-y-3 pt-3 border-t">
                <div className="space-y-1">
                  <Label htmlFor="ed_identity" className="text-xs font-semibold text-foreground">Client Primary Identifier</Label>
                  <select
                    id="ed_identity"
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-2xs font-medium"
                    value={primaryIdentifier}
                    onChange={e => {
                      const val = e.target.value as "email" | "phone" | "both";
                      setPrimaryIdentifier(val);
                      if (val === "email") {
                        setShowEmailField(true);
                      } else if (val === "phone") {
                        setShowPhoneField(true);
                      } else if (val === "both") {
                        setShowEmailField(true);
                        setShowPhoneField(true);
                      }
                    }}
                  >
                    <option value="email">Email Required (Phone Optional)</option>
                    <option value="phone">Phone Number Required (Email Optional)</option>
                    <option value="both">Both Email & Phone Required</option>
                  </select>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <Label className="text-xs font-medium">Show Email Field</Label>
                  <Switch
                    checked={showEmailField}
                    disabled={primaryIdentifier === "email" || primaryIdentifier === "both"}
                    onCheckedChange={setShowEmailField}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <Label className="text-xs font-medium">Show Phone Field</Label>
                  <Switch
                    checked={showPhoneField}
                    disabled={primaryIdentifier === "phone" || primaryIdentifier === "both"}
                    onCheckedChange={setShowPhoneField}
                  />
                </div>
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
