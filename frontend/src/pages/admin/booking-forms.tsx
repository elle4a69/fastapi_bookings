import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Pencil, Trash2, Plus, ExternalLink, Code, FileInput, Copy, Check } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";

interface BookingForm {
  id: number | string;
  name: string;
  slug: string;
  widget_type: "full" | "modal" | "inline";
  active: boolean;
  module_order?: string[];
  enabled_modules?: Record<string, boolean>;
  description?: string;
}

const DEFAULT_MODULE_ORDER = ["location", "provider", "service", "addons", "products", "datetime", "intake", "client", "checkout", "outcome"];
const DEFAULT_ENABLED_MODULES = {
  location: true,
  service: true,
  addons: true,
  products: true,
  provider: true,
  datetime: true,
  intake: true,
  client: true,
  checkout: true,
  outcome: true,
};

export default function BookingForms() {
  const [forms, setForms] = useState<BookingForm[]>([]);
  const [loading, setLoading] = useState(true);
  const [locations, setLocations] = useState<any[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);

  // Dialogs
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [embedDialogOpen, setEmbedDialogOpen] = useState(false);

  const [selectedForm, setSelectedForm] = useState<any | null>(null);
  const [copiedEmbed, setCopiedEmbed] = useState(false);

  // Pre-selection params for Embed Snippet Modal
  const [embedLocId, setEmbedLocId] = useState<string>("none");
  const [embedProvId, setEmbedProvId] = useState<string>("none");
  const [embedSvcId, setEmbedSvcId] = useState<string>("none");

  // New Form Fields
  const [newFormName, setNewFormName] = useState("");
  const [newFormSlug, setNewFormSlug] = useState("");
  const [newFormWidgetType, setNewFormWidgetType] = useState<"full" | "modal" | "inline">("full");

  useEffect(() => {
    loadForms();
  }, []);

  const loadForms = async () => {
    setLoading(true);
    try {
      const [fRes, lRes, pRes, sRes] = await Promise.all([
        apiClient.get<any>("/api/admin/booking-forms").catch(() => []),
        apiClient.get<any>("/api/admin/locations").catch(() => []),
        apiClient.get<any>("/api/admin/providers").catch(() => []),
        apiClient.get<any>("/api/admin/services").catch(() => []),
      ]);
      const rawForms = Array.isArray(fRes) ? fRes : (fRes?.data ?? []);
      const locsArr = Array.isArray(lRes) ? lRes : (lRes?.data ?? []);
      const provsArr = Array.isArray(pRes) ? pRes : (pRes?.data ?? []);
      const svcsArr = Array.isArray(sRes) ? sRes : (sRes?.data ?? []);

      setLocations(locsArr);
      setProviders(provsArr);
      setServices(svcsArr);

      if (rawForms.length === 0) {
        await seedDefaultForms();
      } else {
        setForms(rawForms);
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load booking forms.");
    } finally {
      setLoading(false);
    }
  };

  const seedDefaultForms = async () => {
    try {
      const form1Payload = {
        name: "Standard Booking",
        slug: "standard",
        widget_type: "full",
        active: true,
        module_order: DEFAULT_MODULE_ORDER,
        enabled_modules: DEFAULT_ENABLED_MODULES,
        predefined_values: {}
      };

      const form2Payload = {
        name: "Quick Consult",
        slug: "quick-consult",
        widget_type: "modal",
        active: true,
        module_order: DEFAULT_MODULE_ORDER,
        enabled_modules: DEFAULT_ENABLED_MODULES,
        predefined_values: {}
      };

      const f1 = await apiClient.post<any>("/api/admin/booking-forms", form1Payload).catch(() => null);
      const f2 = await apiClient.post<any>("/api/admin/booking-forms", form2Payload).catch(() => null);

      const combined: BookingForm[] = [];
      if (f1) combined.push(f1);
      if (f2) combined.push(f2);

      if (combined.length > 0) {
        setForms(combined);
      } else {
        // Fallback UI objects if DB insert skips
        setForms([
          { id: 1, name: "Standard Booking", slug: "standard", widget_type: "full", active: true },
          { id: 2, name: "Quick Consult", slug: "quick-consult", widget_type: "modal", active: true }
        ]);
      }
    } catch {
      setForms([
        { id: 1, name: "Standard Booking", slug: "standard", widget_type: "full", active: true },
        { id: 2, name: "Quick Consult", slug: "quick-consult", widget_type: "modal", active: true }
      ]);
    }
  };

  const handleToggleActive = async (id: number | string, currentActive: boolean) => {
    const updated = forms.map(f => f.id === id ? { ...f, active: !currentActive } : f);
    setForms(updated);

    try {
      await apiClient.put(`/api/admin/booking-forms/${id}`, { active: !currentActive }).catch(() => {});
      toast.success("Form status updated!");
    } catch {
      toast.error("Failed to update status.");
    }
  };

  const handleCreateFormSubmit = async () => {
    if (!newFormName.trim()) {
      toast.error("Form name is required.");
      return;
    }

    const slugToUse = newFormSlug.trim() || newFormName.toLowerCase().replace(/[^a-z0-9]+/g, "-");

    try {
      const payload = {
        name: newFormName,
        slug: slugToUse,
        widget_type: newFormWidgetType,
        active: true,
        module_order: DEFAULT_MODULE_ORDER,
        enabled_modules: DEFAULT_ENABLED_MODULES,
        predefined_values: {}
      };

      await apiClient.post("/api/admin/booking-forms", payload);
      toast.success("New booking form created!");
      setCreateDialogOpen(false);
      setNewFormName("");
      setNewFormSlug("");
      loadForms();
    } catch (err: any) {
      toast.error(err.message || "Failed to create form.");
    }
  };

  const handleDeleteForm = async (id: number | string) => {
    try {
      await apiClient.delete(`/api/admin/booking-forms/${id}`).catch(() => {});
      setForms(forms.filter(f => f.id !== id));
      toast.success("Booking form deleted.");
    } catch (err: any) {
      toast.error(err.message || "Failed to delete form.");
    }
  };

  const getEmbedQueryParams = () => {
    const params = new URLSearchParams();
    if (embedLocId !== "none") params.set("location_id", embedLocId);
    if (embedProvId !== "none") params.set("provider_id", embedProvId);
    if (embedSvcId !== "none") params.set("service_id", embedSvcId);
    const q = params.toString();
    return q ? `?${q}` : "";
  };

  const getEmbedSnippet = (slug: string) => {
    const host = window.location.origin;
    const q = getEmbedQueryParams();
    return `<iframe src="${host}/book/${slug}${q}" width="100%" height="700px" frameborder="0" allow="payment"></iframe>`;
  };

  const getDirectUrl = (slug: string) => {
    const host = window.location.origin;
    const q = getEmbedQueryParams();
    return `${host}/book/${slug}${q}`;
  };

  const handleCopyEmbed = (slug: string) => {
    navigator.clipboard.writeText(getEmbedSnippet(slug));
    setCopiedEmbed(true);
    toast.success("Embed code copied to clipboard!");
    setTimeout(() => setCopiedEmbed(false), 2000);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <FileInput className="w-6 h-6 text-primary" /> Booking Forms
          </h1>
          <p className="text-muted-foreground text-xs mt-1">Configure customer intake forms, widget embed codes, and public booking URLs.</p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)} className="gap-2 font-semibold">
          <Plus className="h-4 w-4" /> New Booking Form
        </Button>
      </div>

      <div className="rounded-xl border bg-card overflow-hidden shadow-xs">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30">
              <TableHead>Form Name</TableHead>
              <TableHead>Slug</TableHead>
              <TableHead>Widget Type</TableHead>
              <TableHead>Active</TableHead>
              <TableHead>Public Link</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground text-sm">
                  Loading booking forms...
                </TableCell>
              </TableRow>
            ) : forms.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground text-sm">
                  No booking forms found. Click "New Booking Form" to create one.
                </TableCell>
              </TableRow>
            ) : (
              forms.map((form) => (
                <TableRow key={form.id} className="hover:bg-muted/30 transition-colors">
                  <TableCell className="font-bold text-sm">{form.name}</TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">/book/{form.slug}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="capitalize font-semibold text-xs px-2.5 py-0.5">
                      {form.widget_type === "full" ? "Full Page" : form.widget_type === "modal" ? "Modal Popup" : "Inline Embed"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Switch
                      checked={form.active}
                      onCheckedChange={() => handleToggleActive(form.id, form.active)}
                    />
                  </TableCell>
                  <TableCell>
                    <a
                      href={`/book/${form.slug}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center text-primary font-semibold text-xs hover:underline gap-1"
                    >
                      /book/{form.slug}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 px-2 text-xs gap-1"
                        onClick={() => { setSelectedForm(form); setEmbedDialogOpen(true); }}
                      >
                        <Code className="h-3.5 w-3.5" /> Embed
                      </Button>
                      <Link to={`/admin/booking-forms/${form.id}`}>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </Link>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={() => handleDeleteForm(form.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* ── Create New Form Modal ────────────────────────────────────── */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="sm:max-w-[450px] rounded-xl">
          <DialogHeader>
            <DialogTitle>Create Booking Form</DialogTitle>
            <DialogDescription>Add a new public booking intake form configuration.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="new_form_name">Form Name *</Label>
              <Input
                id="new_form_name"
                placeholder="e.g. VIP Consultation"
                value={newFormName}
                onChange={e => setNewFormName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new_form_slug">URL Slug</Label>
              <Input
                id="new_form_slug"
                placeholder="e.g. vip-consult"
                value={newFormSlug}
                onChange={e => setNewFormSlug(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new_widget_type">Widget Display Mode</Label>
              <select
                id="new_widget_type"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background"
                value={newFormWidgetType}
                onChange={e => setNewFormWidgetType(e.target.value as any)}
              >
                <option value="full">Full Page (Standard)</option>
                <option value="modal">Modal Popup Widget</option>
                <option value="inline">Inline Embedded Form</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
            <Button className="bg-primary text-primary-foreground font-semibold" onClick={handleCreateFormSubmit}>
              Save & Configure
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Embed Snippet Modal ────────────────────────────────────── */}
      <Dialog open={embedDialogOpen} onOpenChange={setEmbedDialogOpen}>
        <DialogContent className="sm:max-w-[550px] rounded-xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Code className="w-5 h-5 text-primary" /> Embed Code for {selectedForm?.name}
            </DialogTitle>
            <DialogDescription>
              Copy this HTML snippet to embed this booking widget into any external website.
            </DialogDescription>
          </DialogHeader>
          {selectedForm && (
            <div className="space-y-4 py-2">
              {/* Optional Pre-selection Controls */}
              <div className="p-3.5 rounded-xl border bg-muted/20 space-y-3">
                <span className="text-xs font-bold text-foreground block">Optional Embed Pre-selections</span>
                <div className="grid grid-cols-3 gap-2">
                  <div className="space-y-1">
                    <Label className="text-[11px] font-medium text-muted-foreground">Location</Label>
                    <select
                      className="w-full text-xs h-8 rounded-md border bg-background px-2"
                      value={embedLocId}
                      onChange={e => setEmbedLocId(e.target.value)}
                    >
                      <option value="none">None</option>
                      {locations.map((l: any) => <option key={l.id} value={String(l.id)}>{l.name}</option>)}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[11px] font-medium text-muted-foreground">Provider</Label>
                    <select
                      className="w-full text-xs h-8 rounded-md border bg-background px-2"
                      value={embedProvId}
                      onChange={e => setEmbedProvId(e.target.value)}
                    >
                      <option value="none">None</option>
                      {providers.map((p: any) => <option key={p.id} value={String(p.id)}>{p.name}</option>)}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-[11px] font-medium text-muted-foreground">Service</Label>
                    <select
                      className="w-full text-xs h-8 rounded-md border bg-background px-2"
                      value={embedSvcId}
                      onChange={e => setEmbedSvcId(e.target.value)}
                    >
                      <option value="none">None</option>
                      {services.map((s: any) => <option key={s.id} value={String(s.id)}>{s.name}</option>)}
                    </select>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-xs font-bold text-muted-foreground">HTML IFRAME CODE</Label>
                <div className="relative">
                  <textarea
                    readOnly
                    rows={4}
                    className="w-full font-mono text-xs p-3 rounded-lg border bg-muted/50 text-foreground"
                    value={getEmbedSnippet(selectedForm.slug)}
                  />
                  <Button
                    size="sm"
                    className="absolute top-2 right-2 h-7 text-xs gap-1"
                    onClick={() => handleCopyEmbed(selectedForm.slug)}
                  >
                    {copiedEmbed ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    {copiedEmbed ? "Copied" : "Copy Code"}
                  </Button>
                </div>
              </div>

              <div className="p-3 rounded-lg border bg-primary/5 text-xs text-muted-foreground space-y-1">
                <div className="font-bold text-foreground">Direct Deep-Linked Public URL:</div>
                <a href={getDirectUrl(selectedForm.slug)} target="_blank" rel="noopener noreferrer" className="text-primary underline font-mono break-all">
                  {getDirectUrl(selectedForm.slug)}
                </a>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setEmbedDialogOpen(false)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
