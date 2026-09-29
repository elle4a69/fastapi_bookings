import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  Save,
  ArrowLeft,
  Eye,
  ExternalLink,
  FileInput,
  Lock,
  Sliders,
  ChevronUp,
  ChevronDown,
  Smartphone,
  Tablet,
  Monitor,
  Layout,
  Layers,
  Settings2,
  Palette,
  CheckCircle2,
  Calendar,
  Clock,
  User,
  ShieldCheck,
  ShoppingBag,
  Tag,
  MapPin,
  Sparkles,
  Info,
  ChevronRight,
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { useTenantModules } from "@/context/tenant-modules-context";

export interface FormModuleDef {
  id: string;
  label: string;
  description: string;
  icon: any;
  enabled: boolean;
  stage: number; // 1: Selections, 2: Client Info & Checkout, 3: Confirmation
  requiresModule?: "locations" | "multiple_providers" | "categories" | "products" | "addons";
  isCore?: boolean;
}

const ALL_MASTER_MODULES: FormModuleDef[] = [
  {
    id: "location",
    label: "Location Selection",
    description: "Branch or facility selection for in-person service appointments.",
    icon: MapPin,
    enabled: true,
    stage: 1,
    requiresModule: "locations",
  },
  {
    id: "category",
    label: "Service Category",
    description: "Group services into logical departments or specialty categories.",
    icon: Tag,
    enabled: true,
    stage: 1,
    requiresModule: "categories",
  },
  {
    id: "provider",
    label: "Staff / Provider Selection",
    description: "Choose a specific practitioner or specialist for the appointment.",
    icon: User,
    enabled: true,
    stage: 1,
    requiresModule: "multiple_providers",
  },
  {
    id: "service",
    label: "Service Selection",
    description: "Core appointment service or treatment offered.",
    icon: FileInput,
    enabled: true,
    stage: 1,
    isCore: true,
  },
  {
    id: "addons",
    label: "Service Add-ons",
    description: "Up-sells, premium add-ons, or enhancements to the chosen service.",
    icon: Sparkles,
    enabled: true,
    stage: 1,
    requiresModule: "addons",
  },
  {
    id: "products",
    label: "Products & Packages",
    description: "Retail merchandise or pre-paid session bundles.",
    icon: ShoppingBag,
    enabled: true,
    stage: 1,
    requiresModule: "products",
  },
  {
    id: "datetime",
    label: "Date & Time Slots",
    description: "Interactive scheduling calendar with real-time slot availability.",
    icon: Calendar,
    enabled: true,
    stage: 1,
    isCore: true,
  },
  {
    id: "intake",
    label: "Intake & Custom Notes",
    description: "Client health questionnaire, appointment notes, or special requests.",
    icon: FileInput,
    enabled: true,
    stage: 1,
    isCore: true,
  },
  {
    id: "client",
    label: "Client Details",
    description: "Contact details (Full Name, Email, Phone Number).",
    icon: User,
    enabled: true,
    stage: 2,
    isCore: true,
  },
  {
    id: "checkout",
    label: "Review & Checkout",
    description: "Booking order summary, deposits, taxes, or payment gateway step.",
    icon: ShieldCheck,
    enabled: true,
    stage: 2,
    isCore: true,
  },
  {
    id: "outcome",
    label: "Confirmation & Receipt",
    description: "Final appointment confirmation, calendar invite, and booking receipt.",
    icon: CheckCircle2,
    enabled: true,
    stage: 3,
    isCore: true,
  },
];

const THEME_ACCENTS = [
  { id: "slate", name: "Modern Slate", hex: "#0f172a", bgClass: "bg-slate-900" },
  { id: "indigo", name: "Indigo Luxury", hex: "#4f46e5", bgClass: "bg-indigo-600" },
  { id: "violet", name: "Royal Violet", hex: "#7c3aed", bgClass: "bg-violet-600" },
  { id: "emerald", name: "Emerald Health", hex: "#059669", bgClass: "bg-emerald-600" },
  { id: "rose", name: "Rose Boutique", hex: "#e11d48", bgClass: "bg-rose-600" },
  { id: "amber", name: "Warm Amber", hex: "#d97706", bgClass: "bg-amber-600" },
];

export default function BookingFormEditorPage() {
  const { formId } = useParams<{ formId: string }>();

  // Tenant modules context
  const {
    multipleProvidersEnabled,
    locationsEnabled,
    categoriesEnabled,
    productsEnabled,
    addonsEnabled,
  } = useTenantModules();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeStudioTab, setActiveStudioTab] = useState<"flow" | "presets" | "fields" | "appearance">("flow");

  // Canvas Viewport & Preview Mode
  const [viewportMode, setViewportMode] = useState<"desktop" | "tablet" | "mobile">("desktop");
  const [previewKind, setPreviewKind] = useState<"interactive" | "iframe">("interactive");
  const [previewStepIndex, setPreviewStepIndex] = useState<number>(0);

  // Entities for setup relational dropdowns
  const [locations, setLocations] = useState<any[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);

  // Drag and drop state
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);

  // Form Global Settings
  const [formName, setFormName] = useState("Standard Booking");
  const [formSlug, setFormSlug] = useState("standard");
  const [formDescription, setFormDescription] = useState("");
  const [formActive, setFormActive] = useState(true);
  const [widgetType, setWidgetType] = useState<"full" | "modal" | "inline">("full");
  const [layoutMode, setLayoutMode] = useState<"wizard" | "single_page">("wizard");

  // Step custom labels dictionary: { [moduleId]: { title?: string, subtitle?: string } }
  const [stepCustomLabels, setStepCustomLabels] = useState<Record<string, { title?: string; subtitle?: string }>>({});
  const [expandedStepId, setExpandedStepId] = useState<string | null>(null);

  // Appearance
  const [accentTheme, setAccentTheme] = useState<string>("indigo");
  const [borderRadius, setBorderRadius] = useState<"subtle" | "rounded" | "pill">("rounded");

  // Client Contact Field Configuration
  const [primaryIdentifier, setPrimaryIdentifier] = useState<"email" | "phone" | "both">("email");
  const [showEmailField, setShowEmailField] = useState(true);
  const [showPhoneField, setShowPhoneField] = useState(true);
  const [intakeRequired, setIntakeRequired] = useState(false);

  // Pre-selection / Presets State
  const [presetLocationId, setPresetLocationId] = useState<string>("none");
  const [presetProviderId, setPresetProviderId] = useState<string>("none");
  const [presetServiceId, setPresetServiceId] = useState<string>("none");

  // Raw module ordering list
  const [modules, setModules] = useState<FormModuleDef[]>(ALL_MASTER_MODULES);

  // Filter modules strictly based on tenant package entitlements
  const allowedModules = useMemo(() => {
    return modules.filter((mod) => {
      if (mod.isCore) return true;
      if (mod.requiresModule === "locations") return locationsEnabled;
      if (mod.requiresModule === "multiple_providers") return multipleProvidersEnabled;
      if (mod.requiresModule === "categories") return categoriesEnabled;
      if (mod.requiresModule === "products") return productsEnabled;
      if (mod.requiresModule === "addons") return addonsEnabled;
      return true;
    });
  }, [modules, locationsEnabled, multipleProvidersEnabled, categoriesEnabled, productsEnabled, addonsEnabled]);

  // List of disabled modules due to tenant package
  const disabledTenantCapabilities = useMemo(() => {
    const list: string[] = [];
    if (!locationsEnabled) list.push("Locations");
    if (!multipleProvidersEnabled) list.push("Multiple Providers / Staff");
    if (!categoriesEnabled) list.push("Categories");
    if (!productsEnabled) list.push("Products & Packages");
    if (!addonsEnabled) list.push("Service Add-ons");
    return list;
  }, [locationsEnabled, multipleProvidersEnabled, categoriesEnabled, productsEnabled, addonsEnabled]);

  const loadSetupData = useCallback(async () => {
    setLoading(true);
    try {
      const [lRes, pRes, sRes] = await Promise.all([
        apiClient.get<any>("/api/admin/locations").catch(() => []),
        apiClient.get<any>("/api/admin/providers").catch(() => []),
        apiClient.get<any>("/api/admin/services").catch(() => []),
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
          setFormDescription(data.description || "");
          setFormActive(data.active !== false);
          setWidgetType(data.widget_type || "full");

          const loadedOrder: string[] =
            data.module_order && Array.isArray(data.module_order) && data.module_order.length > 0
              ? data.module_order
              : ALL_MASTER_MODULES.map((m) => m.id);

          const orderedList: FormModuleDef[] = [];

          // Add loaded modules in saved order
          loadedOrder.forEach((modId) => {
            const defaultDef = ALL_MASTER_MODULES.find((m) => m.id === modId);
            if (defaultDef) {
              orderedList.push({
                ...defaultDef,
                enabled: data.enabled_modules ? (data.enabled_modules[modId] ?? true) : true,
              });
            }
          });

          // Append any remaining master modules not in saved order
          ALL_MASTER_MODULES.forEach((def) => {
            if (!orderedList.some((m) => m.id === def.id)) {
              orderedList.push({
                ...def,
                enabled: data.enabled_modules ? (data.enabled_modules[def.id] ?? true) : true,
              });
            }
          });

          setModules(orderedList);

          if (data.predefined_values) {
            const pv = data.predefined_values;
            setPresetLocationId(
              pv.location_id && String(pv.location_id) !== "none" && String(pv.location_id) !== "null"
                ? String(pv.location_id)
                : "none"
            );
            setPresetProviderId(
              pv.provider_id && String(pv.provider_id) !== "none" && String(pv.provider_id) !== "null"
                ? String(pv.provider_id)
                : "none"
            );
            setPresetServiceId(
              pv.service_id && String(pv.service_id) !== "none" && String(pv.service_id) !== "null"
                ? String(pv.service_id)
                : "none"
            );
          }

          if (data.appearance) {
            if (data.appearance.theme) setAccentTheme(data.appearance.theme);
            if (data.appearance.border_radius) setBorderRadius(data.appearance.border_radius);
          }

          if (data.settings) {
            if (data.settings.layout_mode) setLayoutMode(data.settings.layout_mode);
            if (data.settings.primary_identifier) setPrimaryIdentifier(data.settings.primary_identifier);
            if (data.settings.show_email_field !== undefined) setShowEmailField(data.settings.show_email_field);
            if (data.settings.show_phone_field !== undefined) setShowPhoneField(data.settings.show_phone_field);
            if (data.settings.intake_required !== undefined) setIntakeRequired(data.settings.intake_required);
            if (data.settings.step_labels) setStepCustomLabels(data.settings.step_labels);
          }
        }
      }
    } catch {
      toast.error("Could not load form configuration.");
    } finally {
      setLoading(false);
    }
  }, [formId]);

  useEffect(() => {
    loadSetupData();
  }, [loadSetupData]);

  // Stage validation rule: Selection steps (stage 1) <= Client/Checkout (stage 2) <= Outcome (stage 3)
  const moveModuleWithConstraints = (currentIndex: number, targetIndex: number) => {
    if (targetIndex < 0 || targetIndex >= allowedModules.length) return;

    const sourceModule = allowedModules[currentIndex];
    const targetModule = allowedModules[targetIndex];

    if (!sourceModule || !targetModule) return;

    // Map within full modules list
    const fullSourceIdx = modules.findIndex((m) => m.id === sourceModule.id);
    const fullTargetIdx = modules.findIndex((m) => m.id === targetModule.id);

    if (fullSourceIdx === -1 || fullTargetIdx === -1) return;

    const candidate = [...modules];
    const [movedItem] = candidate.splice(fullSourceIdx, 1);
    candidate.splice(fullTargetIdx, 0, movedItem);

    // Validate stage sequence: Stage(N) <= Stage(N+1)
    let isValid = true;
    for (let i = 0; i < candidate.length - 1; i++) {
      if (candidate[i].stage > candidate[i + 1].stage) {
        isValid = false;
        break;
      }
    }

    if (!isValid) {
      toast.error("Invalid workflow order! (Selections must precede Client info, and Confirmation must remain last).");
      return;
    }

    setModules(candidate);
  };

  const toggleModuleEnabled = (id: string) => {
    setModules((prev) => prev.map((m) => (m.id === id ? { ...m, enabled: !m.enabled } : m)));
  };

  // Setup relational cascading filters
  const setupAvailableProviders = useMemo(() => {
    if (!multipleProvidersEnabled) return [];
    return providers.filter((p) => {
      if (presetLocationId !== "none") {
        const loc = locations.find((l) => String(l.id) === presetLocationId);
        if (loc && loc.provider_ids && loc.provider_ids.length > 0) {
          return loc.provider_ids.includes(p.id);
        }
      }
      return true;
    });
  }, [providers, presetLocationId, locations, multipleProvidersEnabled]);

  const setupAvailableServices = useMemo(() => {
    return services.filter((s) => {
      if (multipleProvidersEnabled && presetProviderId !== "none") {
        const prov = providers.find((p) => String(p.id) === presetProviderId);
        if (prov && prov.service_ids && prov.service_ids.length > 0) {
          if (!prov.service_ids.includes(s.id)) return false;
        }
        if (s.provider_ids && s.provider_ids.length > 0 && !s.provider_ids.includes(parseInt(presetProviderId))) {
          return false;
        }
      }
      if (locationsEnabled && presetLocationId !== "none") {
        const loc = locations.find((l) => String(l.id) === presetLocationId);
        if (loc && loc.service_ids && loc.service_ids.length > 0) {
          if (!loc.service_ids.includes(s.id)) return false;
        }
      }
      return true;
    });
  }, [services, presetProviderId, presetLocationId, providers, locations, multipleProvidersEnabled, locationsEnabled]);

  const updateAutoNameAndSlug = (locId: string, provId: string, svcId: string) => {
    const partsName: string[] = [];
    const partsSlug: string[] = [];

    if (locationsEnabled && locId !== "none") {
      const loc = locations.find((l) => String(l.id) === locId);
      if (loc) {
        partsName.push(loc.name);
        partsSlug.push(loc.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
      }
    }

    if (multipleProvidersEnabled && provId !== "none") {
      const prov = providers.find((p) => String(p.id) === provId);
      if (prov) {
        partsName.push(prov.name);
        partsSlug.push(prov.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
      }
    }

    if (svcId !== "none") {
      const svc = services.find((s) => String(s.id) === svcId);
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

  const handleSaveForm = async () => {
    setSaving(true);
    try {
      const enabledModulesMap: Record<string, boolean> = {};
      allowedModules.forEach((m) => {
        enabledModulesMap[m.id] = m.enabled;
      });

      const predefinedValues = {
        location_id: locationsEnabled && presetLocationId !== "none" ? parseInt(presetLocationId) : null,
        provider_id: multipleProvidersEnabled && presetProviderId !== "none" ? parseInt(presetProviderId) : null,
        service_id: presetServiceId !== "none" ? parseInt(presetServiceId) : null,
      };

      const payload = {
        name: formName.trim(),
        slug: formSlug.trim().toLowerCase(),
        description: formDescription.trim() || undefined,
        widget_type: widgetType,
        active: formActive,
        module_order: allowedModules.map((m) => m.id),
        enabled_modules: enabledModulesMap,
        predefined_values: predefinedValues,
        provider_selection_mode: presetProviderId !== "none" ? "predefined" : "required",
        appearance: {
          theme: accentTheme,
          border_radius: borderRadius,
        },
        settings: {
          layout_mode: layoutMode,
          primary_identifier: primaryIdentifier,
          show_email_field: showEmailField,
          show_phone_field: showPhoneField,
          intake_required: intakeRequired,
          step_labels: stepCustomLabels,
        },
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

      toast.success("Booking form configuration saved successfully!");
    } catch (err: any) {
      toast.error(err.message || "Failed to save booking form.");
    } finally {
      setSaving(false);
    }
  };

  // Keyboard shortcut Ctrl+S / Cmd+S
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        handleSaveForm();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  const queryParamsString = useMemo(() => {
    const params = new URLSearchParams();
    if (locationsEnabled && presetLocationId !== "none") params.set("location_id", presetLocationId);
    if (multipleProvidersEnabled && presetProviderId !== "none") params.set("provider_id", presetProviderId);
    if (presetServiceId !== "none") params.set("service_id", presetServiceId);
    const q = params.toString();
    return q ? `?${q}` : "";
  }, [locationsEnabled, presetLocationId, multipleProvidersEnabled, presetProviderId, presetServiceId]);

  const activeStepsForCustomer = useMemo(() => {
    return allowedModules.filter((m) => {
      if (!m.enabled) return false;
      // Filter out steps locked by presets
      if (m.id === "location" && locationsEnabled && presetLocationId !== "none") return false;
      if (m.id === "provider" && multipleProvidersEnabled && presetProviderId !== "none") return false;
      if (m.id === "service" && presetServiceId !== "none") return false;
      return true;
    });
  }, [allowedModules, locationsEnabled, presetLocationId, multipleProvidersEnabled, presetProviderId, presetServiceId]);

  if (loading) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center flex-col gap-3">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <p className="text-xs font-semibold text-muted-foreground">Loading Studio Form Designer...</p>
      </div>
    );
  }

  const lockedLocName = locationsEnabled && presetLocationId !== "none"
    ? locations.find((l) => String(l.id) === presetLocationId)?.name
    : null;
  const lockedProvName = multipleProvidersEnabled && presetProviderId !== "none"
    ? providers.find((p) => String(p.id) === presetProviderId)?.name
    : null;
  const lockedSvcName = presetServiceId !== "none"
    ? services.find((s) => String(s.id) === presetServiceId)?.name
    : null;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-background overflow-hidden">
      {/* ── TOP HEADER / TOOLBAR ───────────────────────────────────── */}
      <header className="flex items-center justify-between border-b px-4 py-2.5 bg-card/90 backdrop-blur-xs shrink-0 z-20">
        <div className="flex items-center gap-3">
          <Link to="/admin/booking-forms">
            <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
              <FileInput className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="font-bold text-sm bg-transparent border-none focus:outline-none focus:ring-1 focus:ring-primary rounded px-1 -ml-1 text-foreground"
                />
                <Badge
                  variant={formActive ? "default" : "secondary"}
                  className={`text-[10px] font-semibold cursor-pointer select-none px-2 py-0.2`}
                  onClick={() => setFormActive(!formActive)}
                >
                  {formActive ? "Published" : "Draft"}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground font-mono">
                /book/{formSlug}
              </p>
            </div>
          </div>
        </div>

        {/* Center: Device Viewport Switcher */}
        <div className="hidden md:flex items-center gap-1 border rounded-lg p-0.5 bg-muted/30">
          <Button
            variant={viewportMode === "desktop" ? "secondary" : "ghost"}
            size="sm"
            className="h-7 px-2.5 gap-1.5 text-xs font-medium"
            onClick={() => setViewportMode("desktop")}
          >
            <Monitor className="h-3.5 w-3.5" /> Desktop
          </Button>
          <Button
            variant={viewportMode === "tablet" ? "secondary" : "ghost"}
            size="sm"
            className="h-7 px-2.5 gap-1.5 text-xs font-medium"
            onClick={() => setViewportMode("tablet")}
          >
            <Tablet className="h-3.5 w-3.5" /> Tablet
          </Button>
          <Button
            variant={viewportMode === "mobile" ? "secondary" : "ghost"}
            size="sm"
            className="h-7 px-2.5 gap-1.5 text-xs font-medium"
            onClick={() => setViewportMode("mobile")}
          >
            <Smartphone className="h-3.5 w-3.5" /> Mobile
          </Button>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-2">
          <a
            href={`/book/${formSlug}${queryParamsString}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs font-semibold">
              <Eye className="w-3.5 h-3.5" /> Test Live <ExternalLink className="w-3 h-3 ml-0.5" />
            </Button>
          </a>

          <Button
            onClick={handleSaveForm}
            disabled={saving}
            size="sm"
            className="h-8 gap-1.5 text-xs font-bold bg-primary text-primary-foreground shadow-xs hover:bg-primary/90"
          >
            <Save className="w-3.5 h-3.5" />
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </header>

      {/* ── MAIN STUDIO SPLIT CANVAS ──────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* LEFT COLUMN: STUDIO PALETTE & INSPECTOR */}
        <aside className="w-96 border-r bg-card flex flex-col shrink-0 overflow-hidden">
          {/* Studio Tabs Navigation */}
          <div className="flex border-b bg-muted/20 shrink-0">
            <button
              type="button"
              onClick={() => setActiveStudioTab("flow")}
              className={`flex-1 py-3 text-xs font-bold border-b-2 flex items-center justify-center gap-1.5 transition-all ${
                activeStudioTab === "flow"
                  ? "border-primary text-primary bg-background"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Layers className="w-3.5 h-3.5" /> Steps & Flow
            </button>
            <button
              type="button"
              onClick={() => setActiveStudioTab("presets")}
              className={`flex-1 py-3 text-xs font-bold border-b-2 flex items-center justify-center gap-1.5 transition-all ${
                activeStudioTab === "presets"
                  ? "border-primary text-primary bg-background"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Sliders className="w-3.5 h-3.5" /> Funnel Locks
            </button>
            <button
              type="button"
              onClick={() => setActiveStudioTab("fields")}
              className={`flex-1 py-3 text-xs font-bold border-b-2 flex items-center justify-center gap-1.5 transition-all ${
                activeStudioTab === "fields"
                  ? "border-primary text-primary bg-background"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Settings2 className="w-3.5 h-3.5" /> Fields
            </button>
            <button
              type="button"
              onClick={() => setActiveStudioTab("appearance")}
              className={`flex-1 py-3 text-xs font-bold border-b-2 flex items-center justify-center gap-1.5 transition-all ${
                activeStudioTab === "appearance"
                  ? "border-primary text-primary bg-background"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Palette className="w-3.5 h-3.5" /> Theme
            </button>
          </div>

          {/* STUDIO TAB CONTENT PANELS */}
          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            {/* ── TAB 1: STEPS & FLOW ────────────────────────────── */}
            {activeStudioTab === "flow" && (
              <div className="space-y-5">
                {/* Flow Layout Mode Switcher */}
                <div className="space-y-2">
                  <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <Layout className="w-3.5 h-3.5 text-primary" /> Booking Flow Layout Mode
                  </Label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setLayoutMode("wizard")}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        layoutMode === "wizard"
                          ? "border-primary bg-primary/5 ring-1 ring-primary"
                          : "border-border hover:bg-muted/30"
                      }`}
                    >
                      <p className="text-xs font-bold text-foreground">Multi-Step Wizard</p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        Clean step-by-step cards with progress tracking.
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={() => setLayoutMode("single_page")}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        layoutMode === "single_page"
                          ? "border-primary bg-primary/5 ring-1 ring-primary"
                          : "border-border hover:bg-muted/30"
                      }`}
                    >
                      <p className="text-xs font-bold text-foreground">Single Page Scroll</p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        All sections visible on one scrollable form.
                      </p>
                    </button>
                  </div>
                </div>

                {/* Disabled Modules Notice */}
                {disabledTenantCapabilities.length > 0 && (
                  <div className="p-3 rounded-xl border border-muted bg-muted/30 text-xs space-y-1.5">
                    <div className="flex items-center gap-1.5 font-bold text-muted-foreground">
                      <Info className="w-3.5 h-3.5 text-primary" /> Suppressed Inactive Modules
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      {disabledTenantCapabilities.join(", ")} are turned OFF in your package and automatically
                      hidden from this form.
                    </p>
                    <Link
                      to="/admin/settings/modules"
                      className="text-[11px] text-primary font-semibold hover:underline inline-flex items-center gap-1 pt-0.5"
                    >
                      Manage Plan in Settings &gt; Modules <ChevronRight className="w-3 h-3" />
                    </Link>
                  </div>
                )}

                {/* Steps List */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-bold text-foreground uppercase tracking-wider">
                      Workflow Steps ({allowedModules.length})
                    </Label>
                    <span className="text-[10px] text-muted-foreground">Re-order & Configure</span>
                  </div>

                  <div className="space-y-2">
                    {allowedModules.map((module, idx) => {
                      const IconComponent = module.icon;
                      const isLockedByPreset =
                        (module.id === "location" && locationsEnabled && presetLocationId !== "none") ||
                        (module.id === "provider" && multipleProvidersEnabled && presetProviderId !== "none") ||
                        (module.id === "service" && presetServiceId !== "none");

                      const isExpanded = expandedStepId === module.id;
                      const customLabel = stepCustomLabels[module.id]?.title || module.label;

                      return (
                        <div
                          key={module.id}
                          draggable={!isLockedByPreset}
                          onDragStart={(e) => {
                            setDraggedIndex(idx);
                            e.dataTransfer.effectAllowed = "move";
                          }}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={(e) => {
                            e.preventDefault();
                            if (draggedIndex === null || draggedIndex === idx) return;
                            moveModuleWithConstraints(draggedIndex, idx);
                            setDraggedIndex(null);
                          }}
                          className={`rounded-xl border transition-all ${
                            draggedIndex === idx
                              ? "opacity-30 border-primary ring-2 ring-primary/20"
                              : isLockedByPreset
                              ? "bg-amber-500/5 border-amber-500/30"
                              : module.enabled
                              ? "bg-card shadow-2xs border-border"
                              : "bg-muted/30 opacity-60 border-dashed"
                          }`}
                        >
                          <div className="p-2.5 flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              {/* Reorder Buttons */}
                              <div className="flex flex-col -my-1">
                                <button
                                  type="button"
                                  onClick={() => moveModuleWithConstraints(idx, idx - 1)}
                                  disabled={idx === 0 || isLockedByPreset}
                                  className="p-0.5 hover:bg-muted rounded disabled:opacity-20 text-muted-foreground"
                                  title="Move Up"
                                >
                                  <ChevronUp className="h-3 w-3" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => moveModuleWithConstraints(idx, idx + 1)}
                                  disabled={idx === allowedModules.length - 1 || isLockedByPreset}
                                  className="p-0.5 hover:bg-muted rounded disabled:opacity-20 text-muted-foreground"
                                  title="Move Down"
                                >
                                  <ChevronDown className="h-3 w-3" />
                                </button>
                              </div>

                              <div className="p-1.5 rounded-lg bg-muted/60 text-muted-foreground shrink-0">
                                <IconComponent className="h-3.5 w-3.5" />
                              </div>

                              <div className="min-w-0">
                                <p className="text-xs font-semibold text-foreground truncate">{customLabel}</p>
                                <p className="text-[10px] text-muted-foreground line-clamp-1">{module.description}</p>
                              </div>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              {isLockedByPreset ? (
                                <Badge
                                  variant="outline"
                                  className="text-[9px] bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-400 gap-1 font-semibold"
                                >
                                  <Lock className="w-2.5 h-2.5" /> Locked
                                </Badge>
                              ) : (
                                <Switch
                                  checked={module.enabled}
                                  onCheckedChange={() => toggleModuleEnabled(module.id)}
                                  aria-label={`Toggle ${module.label}`}
                                />
                              )}

                              <button
                                type="button"
                                onClick={() => setExpandedStepId(isExpanded ? null : module.id)}
                                className="p-1 text-muted-foreground hover:text-foreground rounded"
                                title="Step settings"
                              >
                                <Settings2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>

                          {/* Expandable Step Settings */}
                          {isExpanded && (
                            <div className="p-3 bg-muted/20 border-t space-y-2 text-xs">
                              <div>
                                <Label className="text-[11px] font-medium text-muted-foreground">Custom Step Heading</Label>
                                <Input
                                  placeholder={module.label}
                                  value={stepCustomLabels[module.id]?.title || ""}
                                  onChange={(e) => {
                                    setStepCustomLabels((prev) => ({
                                      ...prev,
                                      [module.id]: { ...prev[module.id], title: e.target.value },
                                    }));
                                  }}
                                  className="h-8 text-xs mt-1 bg-background"
                                />
                              </div>
                              <div>
                                <Label className="text-[11px] font-medium text-muted-foreground">Custom Instruction Note</Label>
                                <Input
                                  placeholder={module.description}
                                  value={stepCustomLabels[module.id]?.subtitle || ""}
                                  onChange={(e) => {
                                    setStepCustomLabels((prev) => ({
                                      ...prev,
                                      [module.id]: { ...prev[module.id], subtitle: e.target.value },
                                    }));
                                  }}
                                  className="h-8 text-xs mt-1 bg-background"
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* ── TAB 2: FUNNEL PRESETS & LOCKS ─────────────────── */}
            {activeStudioTab === "presets" && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-xs font-bold text-foreground uppercase tracking-wider">
                    Relational Funnel Locks
                  </h3>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    Pre-selecting an item locks it and automatically skips that step for the customer.
                  </p>
                </div>

                {/* Pre-select Location */}
                {locationsEnabled ? (
                  <div className="space-y-1.5 p-3 rounded-xl border bg-muted/15">
                    <div className="flex justify-between items-center">
                      <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-primary" /> 1. Pre-select Location
                      </Label>
                      {presetLocationId !== "none" && (
                        <Badge variant="outline" className="text-[9px] bg-primary/10 text-primary border-primary/30">
                          Step Locked
                        </Badge>
                      )}
                    </div>
                    <Select
                      value={presetLocationId}
                      onValueChange={(val) => {
                        setPresetLocationId(val);
                        setPresetProviderId("none");
                        setPresetServiceId("none");
                        updateAutoNameAndSlug(val, "none", "none");
                      }}
                    >
                      <SelectTrigger className="h-9 text-xs bg-background">
                        <SelectValue placeholder="None (Customer chooses)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">None (Customer chooses freely)</SelectItem>
                        {locations.map((l) => (
                          <SelectItem key={l.id} value={String(l.id)}>
                            {l.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ) : (
                  <div className="p-3 rounded-xl border border-dashed text-[11px] text-muted-foreground">
                    Location selector is disabled on your current tenant package.
                  </div>
                )}

                {/* Pre-select Provider */}
                {multipleProvidersEnabled ? (
                  <div className="space-y-1.5 p-3 rounded-xl border bg-muted/15">
                    <div className="flex justify-between items-center">
                      <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                        <User className="w-3.5 h-3.5 text-primary" /> 2. Pre-select Staff/Practitioner
                      </Label>
                      <Badge variant="outline" className="text-[9px]">
                        {setupAvailableProviders.length} Available
                      </Badge>
                    </div>
                    <Select
                      value={presetProviderId}
                      onValueChange={(val) => {
                        setPresetProviderId(val);
                        setPresetServiceId("none");
                        updateAutoNameAndSlug(presetLocationId, val, "none");
                      }}
                    >
                      <SelectTrigger className="h-9 text-xs bg-background">
                        <SelectValue placeholder="None (Customer chooses)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">None (Customer chooses freely)</SelectItem>
                        {setupAvailableProviders.map((p) => (
                          <SelectItem key={p.id} value={String(p.id)}>
                            {p.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ) : (
                  <div className="p-3 rounded-xl border border-dashed text-[11px] text-muted-foreground">
                    Multiple Providers / Staff selector is disabled on your current tenant package.
                  </div>
                )}

                {/* Pre-select Service */}
                <div className="space-y-1.5 p-3 rounded-xl border bg-muted/15">
                  <div className="flex justify-between items-center">
                    <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                      <FileInput className="w-3.5 h-3.5 text-primary" /> 3. Pre-select Service
                    </Label>
                    <Badge variant="outline" className="text-[9px]">
                      {setupAvailableServices.length} Available
                    </Badge>
                  </div>
                  <Select
                    value={presetServiceId}
                    onValueChange={(val) => {
                      setPresetServiceId(val);
                      updateAutoNameAndSlug(presetLocationId, presetProviderId, val);
                    }}
                  >
                    <SelectTrigger className="h-9 text-xs bg-background">
                      <SelectValue placeholder="None (Customer chooses)" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None (Customer chooses freely)</SelectItem>
                      {setupAvailableServices.map((s) => (
                        <SelectItem key={s.id} value={String(s.id)}>
                          {s.name} ({s.duration}m)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="p-3 rounded-xl bg-primary/5 border border-primary/20 text-xs space-y-1 text-muted-foreground">
                  <p className="font-semibold text-foreground">Pro-Tip for Campaigns:</p>
                  <p className="text-[11px]">
                    Pre-selecting a practitioner or service creates focused high-converting links (e.g. for Instagram bio
                    or specific staff Google Business profile).
                  </p>
                </div>
              </div>
            )}

            {/* ── TAB 3: FORM FIELDS & INTAKE ───────────────────── */}
            {activeStudioTab === "fields" && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-xs font-bold text-foreground uppercase tracking-wider">
                    Client Contact & Identification
                  </h3>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    Specify which contact identifier is required for client account matching.
                  </p>
                </div>

                <div className="space-y-2 p-3 rounded-xl border bg-muted/15">
                  <Label className="text-xs font-semibold">Primary Client Identifier</Label>
                  <select
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-2xs font-medium text-foreground"
                    value={primaryIdentifier}
                    onChange={(e) => {
                      const val = e.target.value as "email" | "phone" | "both";
                      setPrimaryIdentifier(val);
                      if (val === "email") setShowEmailField(true);
                      if (val === "phone") setShowPhoneField(true);
                      if (val === "both") {
                        setShowEmailField(true);
                        setShowPhoneField(true);
                      }
                    }}
                  >
                    <option value="email">Email Required (Phone is optional)</option>
                    <option value="phone">Phone Number Required (Email is optional)</option>
                    <option value="both">Both Email & Phone are Required</option>
                  </select>
                </div>

                <div className="space-y-2.5 p-3 rounded-xl border bg-card">
                  <span className="text-xs font-bold text-foreground block">Field Visibility Controls</span>

                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium">Show Email Field</p>
                      <p className="text-[10px] text-muted-foreground">Customer email address</p>
                    </div>
                    <Switch
                      checked={showEmailField}
                      disabled={primaryIdentifier === "email" || primaryIdentifier === "both"}
                      onCheckedChange={setShowEmailField}
                    />
                  </div>

                  <div className="flex items-center justify-between pt-1 border-t">
                    <div>
                      <p className="text-xs font-medium">Show Phone Field</p>
                      <p className="text-[10px] text-muted-foreground">Mobile/SMS contact number</p>
                    </div>
                    <Switch
                      checked={showPhoneField}
                      disabled={primaryIdentifier === "phone" || primaryIdentifier === "both"}
                      onCheckedChange={setShowPhoneField}
                    />
                  </div>

                  <div className="flex items-center justify-between pt-1 border-t">
                    <div>
                      <p className="text-xs font-medium">Require Intake Questionnaire Notes</p>
                      <p className="text-[10px] text-muted-foreground">Mandate notes before booking</p>
                    </div>
                    <Switch checked={intakeRequired} onCheckedChange={setIntakeRequired} />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-xs font-semibold">Form URL Slug</Label>
                  <div className="flex">
                    <span className="inline-flex items-center px-2.5 rounded-l-md border border-r-0 bg-muted text-muted-foreground text-xs font-mono">
                      /book/
                    </span>
                    <Input
                      value={formSlug}
                      onChange={(e) => setFormSlug(e.target.value)}
                      className="rounded-l-none font-mono text-xs h-9"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* ── TAB 4: THEME & APPEARANCE ─────────────────────── */}
            {activeStudioTab === "appearance" && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-xs font-bold text-foreground uppercase tracking-wider">
                    Branding & Widget Styling
                  </h3>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    Match the booking widget styling to your company brand.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label className="text-xs font-semibold">Brand Accent Color</Label>
                  <div className="grid grid-cols-3 gap-2">
                    {THEME_ACCENTS.map((th) => (
                      <button
                        key={th.id}
                        type="button"
                        onClick={() => setAccentTheme(th.id)}
                        className={`p-2.5 rounded-xl border flex items-center gap-2 transition-all ${
                          accentTheme === th.id
                            ? "border-primary bg-primary/5 ring-1 ring-primary"
                            : "border-border hover:bg-muted/40"
                        }`}
                      >
                        <span className={`h-4 w-4 rounded-full ${th.bgClass} shrink-0 shadow-xs`} />
                        <span className="text-[11px] font-semibold truncate text-foreground">{th.name}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-xs font-semibold">Corner Curvature</Label>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => setBorderRadius("subtle")}
                      className={`p-2 rounded-xl border text-center text-xs font-medium ${
                        borderRadius === "subtle" ? "border-primary bg-primary/5" : "border-border hover:bg-muted/30"
                      }`}
                    >
                      Subtle (6px)
                    </button>
                    <button
                      type="button"
                      onClick={() => setBorderRadius("rounded")}
                      className={`p-2 rounded-xl border text-center text-xs font-medium ${
                        borderRadius === "rounded" ? "border-primary bg-primary/5" : "border-border hover:bg-muted/30"
                      }`}
                    >
                      Modern (14px)
                    </button>
                    <button
                      type="button"
                      onClick={() => setBorderRadius("pill")}
                      className={`p-2 rounded-xl border text-center text-xs font-medium ${
                        borderRadius === "pill" ? "border-primary bg-primary/5" : "border-border hover:bg-muted/30"
                      }`}
                    >
                      Pill (24px)
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-xs font-semibold">Widget Embed Type</Label>
                  <select
                    className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs shadow-2xs font-medium text-foreground"
                    value={widgetType}
                    onChange={(e) => setWidgetType(e.target.value as any)}
                  >
                    <option value="full">Full Page Experience (Standalone)</option>
                    <option value="modal">Modal Popup (Trigger Button)</option>
                    <option value="inline">Inline Embedded Form</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          {/* Studio Footer Save Button */}
          <div className="p-4 border-t bg-card shrink-0">
            <Button
              onClick={handleSaveForm}
              disabled={saving}
              className="w-full h-10 font-bold gap-2 text-xs bg-primary text-primary-foreground shadow-xs hover:bg-primary/90"
            >
              <Save className="w-4 h-4" /> {saving ? "Saving Changes..." : "Save Configuration"}
            </Button>
          </div>
        </aside>

        {/* RIGHT COLUMN: LIVE INTERACTIVE CANVAS */}
        <main className="flex-1 bg-muted/15 p-4 sm:p-6 overflow-y-auto flex flex-col items-center">
          {/* Canvas Mode Header Bar */}
          <div className="w-full max-w-4xl flex items-center justify-between pb-4">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-foreground">Canvas Preview</span>
              <div className="flex border rounded-lg p-0.5 bg-background shadow-2xs">
                <button
                  type="button"
                  onClick={() => setPreviewKind("interactive")}
                  className={`px-2.5 py-1 text-[11px] font-semibold rounded-md transition-all ${
                    previewKind === "interactive"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Blueprint Flow
                </button>
                <button
                  type="button"
                  onClick={() => setPreviewKind("iframe")}
                  className={`px-2.5 py-1 text-[11px] font-semibold rounded-md transition-all ${
                    previewKind === "iframe"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Live Widget iFrame
                </button>
              </div>
            </div>

            {/* Locked summary indicator */}
            {(lockedLocName || lockedProvName || lockedSvcName) && (
              <div className="flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-300 bg-amber-500/10 px-2.5 py-1 rounded-full border border-amber-500/20">
                <Lock className="w-3 h-3 text-amber-600" />
                <span>Funnel Locked: {[lockedLocName, lockedProvName, lockedSvcName].filter(Boolean).join(" • ")}</span>
              </div>
            )}
          </div>

          {/* DEVICE PREVIEW CONTAINER */}
          <div
            className={`transition-all duration-300 w-full ${
              viewportMode === "mobile"
                ? "max-w-[390px]"
                : viewportMode === "tablet"
                ? "max-w-[768px]"
                : "max-w-4xl"
            }`}
          >
            {/* Device Shell Wrap */}
            <div
              className={`bg-card border shadow-lg overflow-hidden flex flex-col ${
                viewportMode === "mobile"
                  ? "rounded-[38px] border-4 border-slate-800 ring-4 ring-slate-900/10 shadow-2xl min-h-[720px]"
                  : viewportMode === "tablet"
                  ? "rounded-[24px] border-2 border-slate-700/50 shadow-xl min-h-[680px]"
                  : "rounded-2xl border shadow-md min-h-[640px]"
              }`}
            >
              {/* Smartphone Notch / Browser Bar */}
              {viewportMode === "mobile" ? (
                <div className="h-7 bg-slate-900 flex items-center justify-center shrink-0">
                  <div className="w-20 h-4 bg-black rounded-b-xl" />
                </div>
              ) : (
                <div className="h-9 bg-muted/40 border-b flex items-center px-3 gap-2 shrink-0">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
                  </div>
                  <div className="flex-1 max-w-xs mx-auto text-center font-mono text-[10px] text-muted-foreground bg-background px-3 py-0.5 rounded-md border truncate">
                    https://yourdomain.com/book/{formSlug}
                  </div>
                </div>
              )}

              {/* CANVAS BODY */}
              <div className="flex-1 flex flex-col bg-background p-4 sm:p-6 overflow-y-auto">
                {previewKind === "iframe" ? (
                  <iframe
                    key={`${formSlug}-${presetLocationId}-${presetProviderId}-${presetServiceId}-${layoutMode}-${accentTheme}`}
                    src={`/book/${formSlug}${queryParamsString}`}
                    className="w-full flex-1 min-h-[580px] border-0"
                    title="Live Booking Engine Widget Preview"
                  />
                ) : (
                  /* ── BLUEPRINT DYNAMIC INTERACTIVE PREVIEW ──────────── */
                  <div className="space-y-6 flex-1 flex flex-col justify-between">
                    <div className="space-y-5">
                      {/* Form Header in Preview */}
                      <div className="border-b pb-4 space-y-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-primary">
                          {layoutMode === "wizard" ? "Multi-Step Booking Flow" : "Single Page Booking Flow"}
                        </span>
                        <h2 className="text-xl font-bold text-foreground">{formName}</h2>
                        {formDescription && (
                          <p className="text-xs text-muted-foreground">{formDescription}</p>
                        )}
                      </div>

                      {/* Active Steps Progress Bar in Wizard Mode */}
                      {layoutMode === "wizard" && (
                        <div className="space-y-2">
                          <div className="flex items-center justify-between text-[11px] font-semibold text-muted-foreground">
                            <span>
                              Step {Math.min(previewStepIndex + 1, activeStepsForCustomer.length)} of{" "}
                              {activeStepsForCustomer.length}
                            </span>
                            <span className="text-primary font-bold">
                              {activeStepsForCustomer[previewStepIndex]?.label || "Complete"}
                            </span>
                          </div>
                          <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary transition-all duration-300"
                              style={{
                                width: `${
                                  activeStepsForCustomer.length > 0
                                    ? ((previewStepIndex + 1) / activeStepsForCustomer.length) * 100
                                    : 100
                                }%`,
                              }}
                            />
                          </div>

                          {/* Step Pills Bar */}
                          <div className="flex items-center gap-1.5 overflow-x-auto py-1">
                            {activeStepsForCustomer.map((s, idx) => (
                              <button
                                key={s.id}
                                type="button"
                                onClick={() => setPreviewStepIndex(idx)}
                                className={`text-[10px] font-semibold px-2 py-1 rounded-md shrink-0 transition-all ${
                                  previewStepIndex === idx
                                    ? "bg-primary text-primary-foreground shadow-2xs"
                                    : "bg-muted text-muted-foreground hover:bg-muted/70"
                                }`}
                              >
                                {idx + 1}. {s.label}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* SIMULATED STEP CONTENT */}
                      <div className="p-4 sm:p-5 rounded-2xl border bg-card/60 shadow-2xs space-y-4">
                        {layoutMode === "wizard" ? (
                          /* Current active wizard step mockup */
                          (() => {
                            const cur = activeStepsForCustomer[previewStepIndex];
                            if (!cur) {
                              return <p className="text-xs text-muted-foreground">All steps configured.</p>;
                            }

                            if (cur.id === "service") {
                              return (
                                <div className="space-y-3">
                                  <h3 className="text-sm font-bold text-foreground">Select a Service</h3>
                                  <div className="grid grid-cols-1 gap-2">
                                    {(services.length > 0 ? services.slice(0, 3) : [
                                      { id: 1, name: "Initial Consultation", duration: 45, price: 95 },
                                      { id: 2, name: "Follow-up Session", duration: 30, price: 65 },
                                    ]).map((svc: any) => (
                                      <div
                                        key={svc.id}
                                        className="p-3 rounded-xl border hover:border-primary/50 bg-background flex items-center justify-between cursor-pointer transition-all"
                                      >
                                        <div>
                                          <p className="font-semibold text-xs text-foreground">{svc.name}</p>
                                          <p className="text-[10px] text-muted-foreground flex items-center gap-1">
                                            <Clock className="w-3 h-3" /> {svc.duration} mins
                                          </p>
                                        </div>
                                        {svc.price && (
                                          <span className="text-xs font-bold text-foreground">${svc.price}</span>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              );
                            }

                            if (cur.id === "datetime") {
                              return (
                                <div className="space-y-3">
                                  <h3 className="text-sm font-bold text-foreground">Select Date & Time</h3>
                                  <div className="p-3 rounded-xl border bg-background grid grid-cols-4 gap-2 text-center text-xs">
                                    {["10:00 AM", "11:30 AM", "02:00 PM", "03:30 PM"].map((slot, i) => (
                                      <div
                                        key={i}
                                        className={`py-2 px-1 rounded-lg border font-semibold cursor-pointer ${
                                          i === 0 ? "border-primary bg-primary/10 text-primary" : "hover:bg-muted"
                                        }`}
                                      >
                                        {slot}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              );
                            }

                            if (cur.id === "client") {
                              return (
                                <div className="space-y-3">
                                  <h3 className="text-sm font-bold text-foreground">Your Contact Information</h3>
                                  <div className="space-y-2">
                                    <Input placeholder="Full Name *" className="h-8 text-xs bg-background" disabled />
                                    {showEmailField && (
                                      <Input
                                        placeholder={`Email Address ${primaryIdentifier === "email" || primaryIdentifier === "both" ? "*" : "(Optional)"}`}
                                        className="h-8 text-xs bg-background"
                                        disabled
                                      />
                                    )}
                                    {showPhoneField && (
                                      <Input
                                        placeholder={`Mobile Number ${primaryIdentifier === "phone" || primaryIdentifier === "both" ? "*" : "(Optional)"}`}
                                        className="h-8 text-xs bg-background"
                                        disabled
                                      />
                                    )}
                                  </div>
                                </div>
                              );
                            }

                            return (
                              <div className="space-y-2 py-4 text-center">
                                <cur.icon className="w-8 h-8 text-primary mx-auto opacity-70" />
                                <h3 className="text-sm font-bold text-foreground">{cur.label}</h3>
                                <p className="text-xs text-muted-foreground">{cur.description}</p>
                              </div>
                            );
                          })()
                        ) : (
                          /* Single Page Scroll Mockup */
                          <div className="space-y-5">
                            {activeStepsForCustomer.map((st) => (
                              <div key={st.id} className="p-3 rounded-xl border bg-background/50 space-y-2">
                                <div className="flex items-center gap-2">
                                  <st.icon className="w-4 h-4 text-primary" />
                                  <h4 className="font-bold text-xs text-foreground">{st.label}</h4>
                                </div>
                                <p className="text-[11px] text-muted-foreground">{st.description}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Preview Wizard Navigation Footer */}
                    {layoutMode === "wizard" && activeStepsForCustomer.length > 0 && (
                      <div className="flex items-center justify-between border-t pt-3">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={previewStepIndex === 0}
                          onClick={() => setPreviewStepIndex((prev) => Math.max(0, prev - 1))}
                          className="h-8 text-xs"
                        >
                          Back
                        </Button>
                        <Button
                          size="sm"
                          disabled={previewStepIndex >= activeStepsForCustomer.length - 1}
                          onClick={() => setPreviewStepIndex((prev) => Math.min(activeStepsForCustomer.length - 1, prev + 1))}
                          className="h-8 text-xs font-semibold bg-primary text-primary-foreground"
                        >
                          Next Step
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
