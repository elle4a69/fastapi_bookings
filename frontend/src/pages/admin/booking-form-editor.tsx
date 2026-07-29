import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Save, ArrowLeft, GripVertical, Eye, Code, ExternalLink, FileInput } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";

const DEFAULT_MODULES = [
  { id: "service", label: "Service Selection", enabled: true },
  { id: "provider", label: "Provider Selection", enabled: true },
  { id: "location", label: "Location Selection", enabled: true },
  { id: "datetime", label: "Date/Time Selection", enabled: true },
  { id: "intake", label: "Intake Notes & Questions", enabled: true },
  { id: "client", label: "Client Details", enabled: true },
  { id: "checkout", label: "Checkout & Summary", enabled: true },
  { id: "outcome", label: "Outcome & Confirmation", enabled: true },
];

export default function BookingFormEditorPage() {
  const { formId } = useParams<{ formId: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [formName, setFormName] = useState("Standard Booking");
  const [formSlug, setFormSlug] = useState("standard");
  const [widgetType, setWidgetType] = useState<"full" | "modal" | "inline">("full");
  const [modules, setModules] = useState(DEFAULT_MODULES);
  const [themeJson, setThemeJson] = useState('{\n  "primaryColor": "#0d9488",\n  "borderRadius": "12px"\n}');

  useEffect(() => {
    if (formId && formId !== "new") {
      loadFormData(formId);
    } else {
      setLoading(false);
    }
  }, [formId]);

  const loadFormData = async (id: string) => {
    setLoading(true);
    try {
      const res: any = await apiClient.get(`/api/admin/booking-forms/${id}`).catch(() => null);
      const data = res?.data || res;
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
      }
    } catch {
      toast.error("Could not fetch form configuration.");
    } finally {
      setLoading(false);
    }
  };

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

      const payload = {
        name: formName,
        slug: formSlug,
        widget_type: widgetType,
        active: true,
        module_order: modules.map(m => m.id),
        enabled_modules: enabledModulesMap,
        predefined_values: {}
      };

      if (formId && formId !== "new") {
        await apiClient.put(`/api/admin/booking-forms/${formId}`, payload).catch(async () => {
          return await apiClient.post("/api/admin/booking-forms", payload);
        });
      } else {
        await apiClient.post("/api/admin/booking-forms", payload);
      }

      toast.success("Booking form configuration saved!");
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
        <p className="text-sm text-muted-foreground font-medium">Loading form editor...</p>
      </div>
    );
  }

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
              <FileInput className="w-5 h-5 text-primary" /> Edit Booking Form: {formName}
            </h1>
            <p className="text-xs text-muted-foreground">Customize intake steps, module layout, and widget styles.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <a href={`/book/${formSlug}`} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm" className="gap-1.5 h-9">
              <Eye className="w-4 h-4" /> Live Preview <ExternalLink className="w-3 h-3 ml-0.5" />
            </Button>
          </a>
          <Button onClick={handleSaveForm} disabled={saving} className="gap-1.5 h-9 font-semibold">
            <Save className="w-4 h-4" /> {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </div>

      {/* ── Main 3-Column Layout ──────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Column: Module Toggles */}
        <div className="w-72 border-r bg-muted/20 p-5 overflow-y-auto shrink-0">
          <h2 className="font-bold text-xs uppercase tracking-wider text-muted-foreground mb-4">
            Enabled Modules & Order
          </h2>
          <div className="space-y-2.5">
            {modules.map((module) => (
              <div
                key={module.id}
                className={`flex items-center justify-between p-3 rounded-xl border transition-all ${
                  module.enabled ? "bg-card shadow-2xs border-border" : "bg-muted/40 opacity-60 border-dashed"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <GripVertical className="h-4 w-4 text-muted-foreground cursor-grab shrink-0" />
                  <span className="text-xs font-semibold truncate">{module.label}</span>
                </div>
                <Switch
                  checked={module.enabled}
                  onCheckedChange={() => toggleModule(module.id)}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Center Column: Live Form Layout Preview */}
        <div className="flex-1 bg-muted/10 p-6 overflow-y-auto">
          <div className="max-w-xl mx-auto space-y-4">
            <div className="text-center">
              <span className="text-xs font-bold uppercase tracking-wider text-primary bg-primary/10 px-2.5 py-1 rounded-full">
                Interactive Preview ({widgetType === 'full' ? 'Full Page' : widgetType === 'modal' ? 'Modal Popup' : 'Inline'})
              </span>
              <h2 className="text-xl font-bold mt-2">{formName}</h2>
              <p className="text-xs text-muted-foreground">Client View Layout</p>
            </div>

            <div className="bg-card border rounded-2xl shadow-md p-6 space-y-4">
              {modules.filter(m => m.enabled).map((module) => (
                <div key={`preview-${module.id}`} className="p-4 rounded-xl border bg-muted/20 space-y-1.5">
                  <div className="font-bold text-xs text-primary flex items-center justify-between">
                    <span>{module.label}</span>
                    <span className="text-[10px] text-muted-foreground font-normal">Active Step</span>
                  </div>
                  <div className="h-10 bg-background rounded-lg border border-dashed flex items-center justify-center text-xs text-muted-foreground">
                    [ Live {module.label} Component ]
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Properties & Global Settings */}
        <div className="w-80 border-l bg-card p-5 overflow-y-auto shrink-0 space-y-5">
          <h2 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
            Global Form Settings
          </h2>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="ed_name" className="text-xs font-semibold">Form Name</Label>
              <Input
                id="ed_name"
                value={formName}
                onChange={e => setFormName(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ed_slug" className="text-xs font-semibold">URL Slug</Label>
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

            <div className="pt-2 border-t space-y-1.5">
              <Label htmlFor="ed_theme" className="text-xs font-semibold">Custom Appearance (JSON)</Label>
              <Textarea
                id="ed_theme"
                className="font-mono text-[11px] h-36"
                value={themeJson}
                onChange={e => setThemeJson(e.target.value)}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
