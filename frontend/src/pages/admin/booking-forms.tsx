import { useState, useEffect, useMemo, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
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
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Pencil,
  Trash2,
  Plus,
  ExternalLink,
  Code,
  FileInput,
  Copy,
  Check,
  Search,
  Layers,
  LayoutGrid,
  List,
  Sparkles,
  Calendar,
  MoreVertical,
  CheckCircle2,
  MapPin,
  User,
  ShoppingBag,
  Tag,
  ShieldCheck,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { useTenantModules } from "@/context/tenant-modules-context";

export interface BookingForm {
  id: number | string;
  name: string;
  slug: string;
  widget_type: "full" | "modal" | "inline";
  active: boolean;
  module_order?: string[];
  enabled_modules?: Record<string, boolean>;
  description?: string;
  predefined_values?: {
    location_id?: number | null;
    provider_id?: number | null;
    service_id?: number | null;
    category_id?: number | null;
  };
  appearance?: Record<string, any>;
  settings?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

const ALL_POSSIBLE_MODULES = [
  { id: "location", label: "Location", icon: MapPin, requiresModule: "locations" },
  { id: "provider", label: "Staff/Provider", icon: User, requiresModule: "multiple_providers" },
  { id: "category", label: "Category", icon: Tag, requiresModule: "categories" },
  { id: "service", label: "Service", icon: FileInput, isCore: true },
  { id: "addons", label: "Add-ons", icon: Sparkles, requiresModule: "addons" },
  { id: "products", label: "Products", icon: ShoppingBag, requiresModule: "products" },
  { id: "datetime", label: "Date & Time", icon: Calendar, isCore: true },
  { id: "intake", label: "Intake", icon: FileInput, isCore: true },
  { id: "client", label: "Client Details", icon: User, isCore: true },
  { id: "checkout", label: "Checkout", icon: ShieldCheck, isCore: true },
  { id: "outcome", label: "Confirmation", icon: CheckCircle2, isCore: true },
];

export default function BookingForms() {
  const navigate = useNavigate();
  const {
    multipleProvidersEnabled,
    locationsEnabled,
    categoriesEnabled,
    productsEnabled,
    addonsEnabled,
  } = useTenantModules();

  const [forms, setForms] = useState<BookingForm[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [bookingsCount, setBookingsCount] = useState<number>(0);

  // Relational options for embed code pre-selection
  const [locations, setLocations] = useState<any[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);

  // View & Filter states
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "draft">("all");
  const [widgetFilter, setWidgetFilter] = useState<string>("all");

  // Dialogs
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [embedDialogOpen, setEmbedDialogOpen] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | string | null>(null);

  const [selectedForm, setSelectedForm] = useState<BookingForm | null>(null);
  const [copiedSlug, setCopiedSlug] = useState<string | null>(null);
  const [copiedEmbed, setCopiedEmbed] = useState(false);

  // Pre-selection params for Embed Snippet Modal
  const [embedLocId, setEmbedLocId] = useState<string>("none");
  const [embedProvId, setEmbedProvId] = useState<string>("none");
  const [embedSvcId, setEmbedSvcId] = useState<string>("none");
  const [embedTab, setEmbedTab] = useState<"iframe" | "direct" | "modal">("iframe");

  // New Form Fields
  const [newFormName, setNewFormName] = useState("");
  const [newFormSlug, setNewFormSlug] = useState("");
  const [newFormDescription, setNewFormDescription] = useState("");
  const [newFormWidgetType, setNewFormWidgetType] = useState<"full" | "modal" | "inline">("full");
  const [newFormTemplate, setNewFormTemplate] = useState<"standard" | "express" | "consult">("standard");

  // Filter modules based on active tenant licenses
  const tenantActiveModuleIds = useMemo(() => {
    return ALL_POSSIBLE_MODULES.filter((m) => {
      if (m.isCore) return true;
      if (m.requiresModule === "locations") return locationsEnabled;
      if (m.requiresModule === "multiple_providers") return multipleProvidersEnabled;
      if (m.requiresModule === "categories") return categoriesEnabled;
      if (m.requiresModule === "products") return productsEnabled;
      if (m.requiresModule === "addons") return addonsEnabled;
      return true;
    }).map((m) => m.id);
  }, [locationsEnabled, multipleProvidersEnabled, categoriesEnabled, productsEnabled, addonsEnabled]);

  const loadForms = useCallback(async () => {
    try {
      const [fRes, lRes, pRes, sRes, bRes] = await Promise.all([
        apiClient.get<any>("/api/admin/booking-forms").catch(() => []),
        apiClient.get<any>("/api/admin/locations").catch(() => []),
        apiClient.get<any>("/api/admin/providers").catch(() => []),
        apiClient.get<any>("/api/admin/services").catch(() => []),
        apiClient.get<any>("/api/admin/bookings").catch(() => []),
      ]);

      const rawForms = Array.isArray(fRes) ? fRes : (fRes?.data ?? []);
      const locsArr = Array.isArray(lRes) ? lRes : (lRes?.data ?? []);
      const provsArr = Array.isArray(pRes) ? pRes : (pRes?.data ?? []);
      const svcsArr = Array.isArray(sRes) ? sRes : (sRes?.data ?? []);
      const bookingsArr = Array.isArray(bRes) ? bRes : (bRes?.data ?? []);

      setLocations(locsArr);
      setProviders(provsArr);
      setServices(svcsArr);
      setBookingsCount(bookingsArr.length);

      if (rawForms.length === 0) {
        await seedDefaultForms();
      } else {
        setForms(rawForms);
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load booking forms.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [tenantActiveModuleIds]);

  useEffect(() => {
    loadForms();
  }, [loadForms]);

  const seedDefaultForms = async () => {
    try {
      const defaultOrder = tenantActiveModuleIds;
      const defaultEnabled = defaultOrder.reduce((acc, k) => {
        acc[k] = true;
        return acc;
      }, {} as Record<string, boolean>);

      const form1Payload = {
        name: "Standard Booking Intake",
        slug: "standard",
        description: "Primary appointment booking funnel for customer intake.",
        widget_type: "full",
        active: true,
        module_order: defaultOrder,
        enabled_modules: defaultEnabled,
        predefined_values: {},
      };

      const f1 = await apiClient.post<any>("/api/admin/booking-forms", form1Payload).catch(() => null);
      if (f1) {
        setForms([f1]);
      } else {
        setForms([
          {
            id: 1,
            name: "Standard Booking Intake",
            slug: "standard",
            widget_type: "full",
            active: true,
            module_order: defaultOrder,
            enabled_modules: defaultEnabled,
          },
        ]);
      }
    } catch {
      setForms([
        {
          id: 1,
          name: "Standard Booking Intake",
          slug: "standard",
          widget_type: "full",
          active: true,
        },
      ]);
    }
  };

  const handleToggleActive = async (id: number | string, currentActive: boolean) => {
    const updated = forms.map((f) => (f.id === id ? { ...f, active: !currentActive } : f));
    setForms(updated);

    try {
      await apiClient.put(`/api/admin/booking-forms/${id}`, { active: !currentActive });
      toast.success(`Form marked as ${!currentActive ? "Active" : "Draft"}`);
    } catch {
      toast.error("Failed to update status.");
      loadForms();
    }
  };

  const handleDuplicateForm = async (form: BookingForm) => {
    try {
      const res: any = await apiClient.post(`/api/admin/booking-forms/${form.id}/duplicate`, {
        name: `${form.name} (Copy)`,
        slug: `${form.slug}-copy`,
      });
      const newForm = res?.data || res;
      toast.success(`Duplicated "${form.name}" successfully!`);
      loadForms();
      if (newForm?.id) {
        navigate(`/admin/booking-forms/${newForm.id}`);
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to duplicate booking form.");
    }
  };

  const handleDeleteForm = async (id: number | string) => {
    try {
      await apiClient.delete(`/api/admin/booking-forms/${id}`);
      setForms(forms.filter((f) => f.id !== id));
      toast.success("Booking form removed.");
      setDeleteConfirmId(null);
    } catch (err: any) {
      toast.error(err.message || "Failed to delete form.");
    }
  };

  const handleCreateFormSubmit = async () => {
    if (!newFormName.trim()) {
      toast.error("Form name is required.");
      return;
    }

    const slugToUse = (newFormSlug.trim() || newFormName.toLowerCase())
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");

    // Template configuration
    let templateModuleOrder = [...tenantActiveModuleIds];
    let templateEnabled: Record<string, boolean> = {};

    if (newFormTemplate === "express") {
      // Streamlined: Skip category/products, keep core fast path
      templateModuleOrder = templateModuleOrder.filter((m) => m !== "category" && m !== "products");
    } else if (newFormTemplate === "consult") {
      // Consultation only: Services, datetime, client, outcome
      templateModuleOrder = templateModuleOrder.filter((m) =>
        ["service", "datetime", "intake", "client", "outcome"].includes(m)
      );
    }

    templateModuleOrder.forEach((m) => {
      templateEnabled[m] = true;
    });

    try {
      const payload = {
        name: newFormName.trim(),
        slug: slugToUse,
        description: newFormDescription.trim() || undefined,
        widget_type: newFormWidgetType,
        active: true,
        module_order: templateModuleOrder,
        enabled_modules: templateEnabled,
        predefined_values: {},
        settings: {
          layout_mode: newFormTemplate === "express" ? "single_page" : "wizard",
        },
      };

      const res: any = await apiClient.post("/api/admin/booking-forms", payload);
      const created = res?.data || res;
      toast.success("New booking form created!");
      setCreateDialogOpen(false);
      setNewFormName("");
      setNewFormSlug("");
      setNewFormDescription("");
      loadForms();

      if (created?.id) {
        navigate(`/admin/booking-forms/${created.id}`);
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to create booking form.");
    }
  };

  const getEmbedQueryParams = () => {
    const params = new URLSearchParams();
    if (locationsEnabled && embedLocId !== "none") params.set("location_id", embedLocId);
    if (multipleProvidersEnabled && embedProvId !== "none") params.set("provider_id", embedProvId);
    if (embedSvcId !== "none") params.set("service_id", embedSvcId);
    const q = params.toString();
    return q ? `?${q}` : "";
  };

  const getEmbedSnippet = (slug: string) => {
    const host = window.location.origin;
    const q = getEmbedQueryParams();
    if (embedTab === "modal") {
      return `<!-- FastAPI Bookings Modal Trigger -->
<button onclick="window.FastAPIBookings.open('${slug}', { query: '${q.replace("?", "")}' })" style="padding: 12px 24px; background: #0f172a; color: #fff; border-radius: 8px; font-weight: 600; cursor: pointer; border: none;">
  Book Appointment
</button>
<script src="${host}/widget.js" async></script>`;
    }
    return `<iframe src="${host}/book/${slug}${q}" width="100%" height="720px" frameborder="0" style="border: none; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);" allow="payment"></iframe>`;
  };

  const getDirectUrl = (slug: string) => {
    const host = window.location.origin;
    const q = getEmbedQueryParams();
    return `${host}/book/${slug}${q}`;
  };

  const handleCopyLink = (slug: string) => {
    const url = getDirectUrl(slug);
    navigator.clipboard.writeText(url);
    setCopiedSlug(slug);
    toast.success("Direct booking link copied to clipboard!");
    setTimeout(() => setCopiedSlug(null), 2000);
  };

  const handleCopyEmbed = (slug: string) => {
    navigator.clipboard.writeText(getEmbedSnippet(slug));
    setCopiedEmbed(true);
    toast.success("Embed snippet copied to clipboard!");
    setTimeout(() => setCopiedEmbed(false), 2000);
  };

  // Filtered forms
  const filteredForms = useMemo(() => {
    return forms.filter((form) => {
      if (statusFilter === "active" && !form.active) return false;
      if (statusFilter === "draft" && form.active) return false;
      if (widgetFilter !== "all" && form.widget_type !== widgetFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          form.name.toLowerCase().includes(q) ||
          form.slug.toLowerCase().includes(q) ||
          (form.description && form.description.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [forms, statusFilter, widgetFilter, searchQuery]);

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
      {/* ── Top Header Bar ────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-primary/10 text-primary">
              <FileInput className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground">Booking Forms</h1>
              <p className="text-muted-foreground text-xs mt-0.5">
                Design custom public booking funnels, embed responsive widgets, and tailor step sequences.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setRefreshing(true);
              loadForms();
            }}
            disabled={refreshing}
            className="h-9 gap-1.5 text-xs font-semibold"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            onClick={() => setCreateDialogOpen(true)}
            className="h-9 gap-2 font-semibold shadow-xs bg-primary text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" /> New Booking Form
          </Button>
        </div>
      </div>

      {/* ── Metrics Cards ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="shadow-2xs border bg-card/60 backdrop-blur-xs">
          <CardContent className="p-4 flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Total Forms</p>
              <p className="text-2xl font-bold text-foreground">{forms.length}</p>
            </div>
            <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
              <Layers className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-2xs border bg-card/60 backdrop-blur-xs">
          <CardContent className="p-4 flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Active Forms</p>
              <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                {forms.filter((f) => f.active).length}
              </p>
            </div>
            <div className="h-10 w-10 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center">
              <CheckCircle2 className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-2xs border bg-card/60 backdrop-blur-xs">
          <CardContent className="p-4 flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Enabled Modules</p>
              <p className="text-2xl font-bold text-foreground">{tenantActiveModuleIds.length}</p>
            </div>
            <div className="h-10 w-10 rounded-xl bg-blue-500/10 text-blue-600 flex items-center justify-center">
              <Sparkles className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-2xs border bg-card/60 backdrop-blur-xs">
          <CardContent className="p-4 flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">Submissions Logged</p>
              <p className="text-2xl font-bold text-foreground">{bookingsCount}</p>
            </div>
            <div className="h-10 w-10 rounded-xl bg-purple-500/10 text-purple-600 flex items-center justify-center">
              <Calendar className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Search & Filter Controls ──────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3.5 rounded-xl border bg-card/50 shadow-2xs">
        <div className="flex flex-1 items-center gap-2.5">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search forms by name, slug or description..."
              className="pl-9 h-9 text-xs bg-background"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-2">
            <select
              aria-label="Filter forms by status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="h-9 text-xs rounded-md border border-input bg-background px-3 font-medium text-foreground"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active Only</option>
              <option value="draft">Draft Only</option>
            </select>

            <select
              aria-label="Filter forms by widget type"
              value={widgetFilter}
              onChange={(e) => setWidgetFilter(e.target.value)}
              className="h-9 text-xs rounded-md border border-input bg-background px-3 font-medium text-foreground hidden md:block"
            >
              <option value="all">All Form Types</option>
              <option value="full">Full Page</option>
              <option value="modal">Modal Popup</option>
              <option value="inline">Inline Embed</option>
            </select>
          </div>
        </div>

        <div className="flex items-center gap-1.5 self-end sm:self-auto border rounded-lg p-0.5 bg-muted/40">
          <Button
            variant={viewMode === "grid" ? "secondary" : "ghost"}
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => setViewMode("grid")}
            title="Grid View"
          >
            <LayoutGrid className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant={viewMode === "table" ? "secondary" : "ghost"}
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => setViewMode("table")}
            title="Table View"
          >
            <List className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* ── Main View (Grid or Table) ─────────────────────────────── */}
      {loading ? (
        <div className="flex flex-col items-center justify-center p-16 rounded-xl border border-dashed text-muted-foreground">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent mb-3" />
          <p className="text-sm font-medium">Loading booking forms...</p>
        </div>
      ) : filteredForms.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-16 rounded-2xl border border-dashed bg-card/30 text-center space-y-3">
          <div className="h-12 w-12 rounded-2xl bg-muted flex items-center justify-center text-muted-foreground">
            <FileInput className="h-6 w-6" />
          </div>
          <div className="space-y-1">
            <h3 className="font-semibold text-foreground text-sm">No booking forms match your criteria</h3>
            <p className="text-xs text-muted-foreground max-w-sm">
              Try adjusting your search terms or create a new booking intake form.
            </p>
          </div>
          <Button
            size="sm"
            onClick={() => {
              setSearchQuery("");
              setStatusFilter("all");
              setWidgetFilter("all");
            }}
            variant="outline"
            className="text-xs"
          >
            Reset Filters
          </Button>
        </div>
      ) : viewMode === "grid" ? (
        /* ── GRID CARD VIEW ────────────────────────────────────────── */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredForms.map((form) => {
            const rawOrder = form.module_order || [];
            // Gracefully filter active modules against tenant capabilities
            const activeStepNames = rawOrder
              .filter((m) => {
                if (form.enabled_modules && form.enabled_modules[m] === false) return false;
                return tenantActiveModuleIds.includes(m);
              })
              .map((m) => {
                const found = ALL_POSSIBLE_MODULES.find((mod) => mod.id === m);
                return found ? found.label : m;
              });

            const isWizard = form.settings?.layout_mode !== "single_page";

            return (
              <Card
                key={form.id}
                className="group relative flex flex-col justify-between overflow-hidden border bg-card hover:border-primary/40 hover:shadow-md transition-all duration-200"
              >
                <div className="p-5 space-y-4">
                  {/* Top card bar: status & widget mode */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={form.active ? "default" : "secondary"}
                        className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                          form.active
                            ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {form.active ? "Active" : "Draft"}
                      </Badge>
                      <Badge variant="outline" className="text-[10px] font-medium capitalize">
                        {form.widget_type === "full"
                          ? "Full Page"
                          : form.widget_type === "modal"
                          ? "Modal Popup"
                          : "Inline Embed"}
                      </Badge>
                      <Badge variant="secondary" className="text-[10px] font-normal text-muted-foreground">
                        {isWizard ? "Multi-Step" : "Single Page"}
                      </Badge>
                    </div>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-44">
                        <DropdownMenuItem asChild>
                          <Link to={`/admin/booking-forms/${form.id}`} className="cursor-pointer gap-2">
                            <Pencil className="h-3.5 w-3.5" /> Edit Builder
                          </Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => {
                            setSelectedForm(form);
                            setEmbedDialogOpen(true);
                          }}
                          className="cursor-pointer gap-2"
                        >
                          <Code className="h-3.5 w-3.5" /> Embed Snippet
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => handleDuplicateForm(form)}
                          className="cursor-pointer gap-2"
                        >
                          <Copy className="h-3.5 w-3.5" /> Duplicate Form
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => setDeleteConfirmId(form.id)}
                          className="cursor-pointer gap-2 text-destructive focus:text-destructive"
                        >
                          <Trash2 className="h-3.5 w-3.5" /> Delete Form
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>

                  {/* Form Title & Slug */}
                  <div className="space-y-1.5">
                    <Link
                      to={`/admin/booking-forms/${form.id}`}
                      className="font-bold text-base text-foreground group-hover:text-primary transition-colors line-clamp-1"
                    >
                      {form.name}
                    </Link>
                    <p className="text-xs text-muted-foreground line-clamp-2 min-h-[32px]">
                      {form.description || "Public client booking funnel configured for online self-service intake."}
                    </p>
                  </div>

                  {/* Public Link Box */}
                  <div className="flex items-center justify-between p-2 rounded-lg bg-muted/40 border border-muted text-xs">
                    <span className="font-mono text-muted-foreground truncate max-w-[190px]">
                      /book/{form.slug}
                    </span>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-muted-foreground hover:text-foreground"
                        onClick={() => handleCopyLink(form.slug)}
                        title="Copy direct link"
                      >
                        {copiedSlug === form.slug ? (
                          <Check className="h-3 w-3 text-emerald-600" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                      </Button>
                      <a
                        href={`/book/${form.slug}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-primary p-1"
                        title="Open in new window"
                      >
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  </div>

                  {/* Workflow Steps Preview */}
                  <div className="space-y-1.5">
                    <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block">
                      Workflow Steps ({activeStepNames.length})
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {activeStepNames.slice(0, 4).map((step, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center text-[10px] bg-secondary/70 text-secondary-foreground px-2 py-0.5 rounded-md font-medium"
                        >
                          {step}
                        </span>
                      ))}
                      {activeStepNames.length > 4 && (
                        <span className="text-[10px] text-muted-foreground font-medium px-1 py-0.5">
                          +{activeStepNames.length - 4} more
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Bottom Card Footer Actions */}
                <div className="flex items-center justify-between p-3.5 bg-muted/20 border-t">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={form.active}
                      onCheckedChange={() => handleToggleActive(form.id, form.active)}
                      aria-label="Toggle active status"
                    />
                    <span className="text-xs font-medium text-muted-foreground">
                      {form.active ? "Published" : "Draft"}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs gap-1.5 font-medium"
                      onClick={() => {
                        setSelectedForm(form);
                        setEmbedDialogOpen(true);
                      }}
                    >
                      <Code className="h-3.5 w-3.5" /> Embed
                    </Button>
                    <Link to={`/admin/booking-forms/${form.id}`}>
                      <Button size="sm" className="h-8 text-xs gap-1.5 font-semibold">
                        <Pencil className="h-3.5 w-3.5" /> Edit
                      </Button>
                    </Link>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        /* ── TABLE VIEW ────────────────────────────────────────────── */
        <div className="rounded-xl border bg-card overflow-hidden shadow-2xs">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40">
                <TableHead className="font-semibold text-xs">Form Name</TableHead>
                <TableHead className="font-semibold text-xs">Slug & Link</TableHead>
                <TableHead className="font-semibold text-xs">Display Type</TableHead>
                <TableHead className="font-semibold text-xs">Active Steps</TableHead>
                <TableHead className="font-semibold text-xs">Status</TableHead>
                <TableHead className="text-right font-semibold text-xs">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredForms.map((form) => {
                const rawOrder = form.module_order || [];
                const activeCount = rawOrder.filter((m) => {
                  if (form.enabled_modules && form.enabled_modules[m] === false) return false;
                  return tenantActiveModuleIds.includes(m);
                }).length;

                return (
                  <TableRow key={form.id} className="hover:bg-muted/30 transition-colors">
                    <TableCell>
                      <div className="space-y-0.5">
                        <Link
                          to={`/admin/booking-forms/${form.id}`}
                          className="font-bold text-sm text-foreground hover:text-primary transition-colors block"
                        >
                          {form.name}
                        </Link>
                        {form.description && (
                          <p className="text-xs text-muted-foreground line-clamp-1">{form.description}</p>
                        )}
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
                        <span>/book/{form.slug}</span>
                        <button
                          onClick={() => handleCopyLink(form.slug)}
                          className="p-1 hover:text-foreground text-muted-foreground rounded"
                          title="Copy link"
                        >
                          {copiedSlug === form.slug ? (
                            <Check className="h-3 w-3 text-emerald-600" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </button>
                      </div>
                    </TableCell>

                    <TableCell>
                      <Badge variant="outline" className="capitalize text-xs">
                        {form.widget_type === "full"
                          ? "Full Page"
                          : form.widget_type === "modal"
                          ? "Modal Popup"
                          : "Inline"}
                      </Badge>
                    </TableCell>

                    <TableCell>
                      <span className="text-xs font-semibold text-foreground">{activeCount} steps enabled</span>
                    </TableCell>

                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={form.active}
                          onCheckedChange={() => handleToggleActive(form.id, form.active)}
                        />
                        <span className="text-xs font-medium text-muted-foreground">
                          {form.active ? "Active" : "Draft"}
                        </span>
                      </div>
                    </TableCell>

                    <TableCell className="text-right">
                      <div className="flex justify-end items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 px-2.5 text-xs gap-1"
                          onClick={() => {
                            setSelectedForm(form);
                            setEmbedDialogOpen(true);
                          }}
                        >
                          <Code className="h-3.5 w-3.5" /> Embed
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => handleDuplicateForm(form)}
                          title="Duplicate"
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </Button>
                        <Link to={`/admin/booking-forms/${form.id}`}>
                          <Button variant="ghost" size="icon" className="h-8 w-8" title="Edit">
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:text-destructive"
                          onClick={() => setDeleteConfirmId(form.id)}
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {/* ── Create New Form Modal ────────────────────────────────────── */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="sm:max-w-[560px] rounded-2xl">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold flex items-center gap-2">
              <Plus className="w-5 h-5 text-primary" /> Create Booking Form
            </DialogTitle>
            <DialogDescription className="text-xs">
              Configure a new client intake flow. Modules disabled in your tenant plan are automatically suppressed.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Template Selector */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold">Choose a Flow Preset</Label>
              <div className="grid grid-cols-3 gap-2.5">
                <button
                  type="button"
                  onClick={() => setNewFormTemplate("standard")}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    newFormTemplate === "standard"
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border hover:bg-muted/40"
                  }`}
                >
                  <p className="text-xs font-bold text-foreground">Standard Flow</p>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Multi-step wizard with all active catalog steps.
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setNewFormTemplate("express")}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    newFormTemplate === "express"
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border hover:bg-muted/40"
                  }`}
                >
                  <p className="text-xs font-bold text-foreground">Express Scroll</p>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Fast single-page layout with essential steps.
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setNewFormTemplate("consult")}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    newFormTemplate === "consult"
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border hover:bg-muted/40"
                  }`}
                >
                  <p className="text-xs font-bold text-foreground">Quick Consult</p>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Short form focused on time slot and client notes.
                  </p>
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="new_form_name" className="text-xs font-semibold">
                Form Name *
              </Label>
              <Input
                id="new_form_name"
                placeholder="e.g. VIP Consultation Intake"
                value={newFormName}
                onChange={(e) => {
                  setNewFormName(e.target.value);
                  if (!newFormSlug) {
                    setNewFormSlug(
                      e.target.value
                        .toLowerCase()
                        .replace(/[^a-z0-9]+/g, "-")
                        .replace(/^-|-$/g, "")
                    );
                  }
                }}
                className="text-xs h-9"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="new_form_slug" className="text-xs font-semibold">
                Public URL Slug
              </Label>
              <div className="flex">
                <span className="inline-flex items-center px-2.5 rounded-l-md border border-r-0 bg-muted text-muted-foreground text-xs font-mono">
                  /book/
                </span>
                <Input
                  id="new_form_slug"
                  placeholder="e.g. vip-consultation"
                  value={newFormSlug}
                  onChange={(e) => setNewFormSlug(e.target.value)}
                  className="rounded-l-none font-mono text-xs h-9"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="new_form_desc" className="text-xs font-semibold">
                Description (Optional)
              </Label>
              <Input
                id="new_form_desc"
                placeholder="Brief internal or public overview of this form's purpose"
                value={newFormDescription}
                onChange={(e) => setNewFormDescription(e.target.value)}
                className="text-xs h-9"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="new_widget_type" className="text-xs font-semibold">
                Widget Display Mode
              </Label>
              <select
                id="new_widget_type"
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs text-foreground shadow-2xs font-medium"
                value={newFormWidgetType}
                onChange={(e) => setNewFormWidgetType(e.target.value as any)}
              >
                <option value="full">Full Page Experience (Standalone URL)</option>
                <option value="modal">Modal Popup (Triggered via click button)</option>
                <option value="inline">Inline Embedded Form (Within website page)</option>
              </select>
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" size="sm" onClick={() => setCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              className="bg-primary text-primary-foreground font-semibold"
              onClick={handleCreateFormSubmit}
            >
              Create & Open Designer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Embed Snippet Modal ────────────────────────────────────── */}
      <Dialog open={embedDialogOpen} onOpenChange={setEmbedDialogOpen}>
        <DialogContent className="sm:max-w-[620px] rounded-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg">
              <Code className="w-5 h-5 text-primary" /> Embed Form: {selectedForm?.name}
            </DialogTitle>
            <DialogDescription className="text-xs">
              Easily embed this booking flow onto WordPress, Squarespace, Webflow, Shopify, or any custom website.
            </DialogDescription>
          </DialogHeader>

          {selectedForm && (
            <div className="space-y-4 py-2">
              {/* Embed Format Switcher */}
              <div className="flex border rounded-lg p-1 bg-muted/30">
                <button
                  type="button"
                  onClick={() => setEmbedTab("iframe")}
                  className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${
                    embedTab === "iframe"
                      ? "bg-background shadow-xs text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Iframe Embed
                </button>
                <button
                  type="button"
                  onClick={() => setEmbedTab("modal")}
                  className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${
                    embedTab === "modal"
                      ? "bg-background shadow-xs text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Modal Button Trigger
                </button>
                <button
                  type="button"
                  onClick={() => setEmbedTab("direct")}
                  className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${
                    embedTab === "direct"
                      ? "bg-background shadow-xs text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Direct Shareable Link
                </button>
              </div>

              {/* Optional Pre-selection Controls (Filtered by Tenant Module Entitlements) */}
              <div className="p-3.5 rounded-xl border bg-muted/20 space-y-2.5">
                <span className="text-xs font-bold text-foreground block">
                  Optional URL Pre-selections (Bypasses steps for customer)
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  {locationsEnabled && (
                    <div className="space-y-1">
                      <Label className="text-[11px] font-medium text-muted-foreground">Location</Label>
                      <select
                        className="w-full text-xs h-8 rounded-md border bg-background px-2"
                        value={embedLocId}
                        onChange={(e) => setEmbedLocId(e.target.value)}
                      >
                        <option value="none">None (Customer chooses)</option>
                        {locations.map((l: any) => (
                          <option key={l.id} value={String(l.id)}>
                            {l.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {multipleProvidersEnabled && (
                    <div className="space-y-1">
                      <Label className="text-[11px] font-medium text-muted-foreground">Provider</Label>
                      <select
                        className="w-full text-xs h-8 rounded-md border bg-background px-2"
                        value={embedProvId}
                        onChange={(e) => setEmbedProvId(e.target.value)}
                      >
                        <option value="none">None (Customer chooses)</option>
                        {providers.map((p: any) => (
                          <option key={p.id} value={String(p.id)}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  <div className="space-y-1">
                    <Label className="text-[11px] font-medium text-muted-foreground">Service</Label>
                    <select
                      className="w-full text-xs h-8 rounded-md border bg-background px-2"
                      value={embedSvcId}
                      onChange={(e) => setEmbedSvcId(e.target.value)}
                    >
                      <option value="none">None (Customer chooses)</option>
                      {services.map((s: any) => (
                        <option key={s.id} value={String(s.id)}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* Code / Link Display Box */}
              {embedTab === "direct" ? (
                <div className="space-y-2">
                  <Label className="text-xs font-bold text-muted-foreground">DIRECT PUBLIC LINK</Label>
                  <div className="flex gap-2">
                    <Input
                      readOnly
                      value={getDirectUrl(selectedForm.slug)}
                      className="font-mono text-xs bg-muted/40 h-9"
                    />
                    <Button
                      size="sm"
                      className="h-9 text-xs gap-1.5 shrink-0"
                      onClick={() => handleCopyLink(selectedForm.slug)}
                    >
                      {copiedSlug === selectedForm.slug ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                      Copy Link
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-bold text-muted-foreground uppercase">
                      {embedTab === "modal" ? "HTML Button & Script Code" : "HTML Iframe Snippet"}
                    </Label>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 text-xs gap-1 text-primary hover:text-primary"
                      onClick={() => handleCopyEmbed(selectedForm.slug)}
                    >
                      {copiedEmbed ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      {copiedEmbed ? "Copied" : "Copy Code"}
                    </Button>
                  </div>
                  <div className="relative">
                    <textarea
                      readOnly
                      rows={embedTab === "modal" ? 5 : 4}
                      className="w-full font-mono text-xs p-3 rounded-xl border bg-muted/60 text-foreground resize-none leading-relaxed"
                      value={getEmbedSnippet(selectedForm.slug)}
                    />
                  </div>
                </div>
              )}

              {/* Direct Link Footnote */}
              <div className="flex items-center justify-between p-3 rounded-xl border bg-primary/5 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">Want to test right now?</span>
                <a
                  href={getDirectUrl(selectedForm.slug)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary font-semibold hover:underline flex items-center gap-1"
                >
                  Open in New Tab <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button size="sm" onClick={() => setEmbedDialogOpen(false)}>
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Delete Confirmation Dialog ─────────────────────────────── */}
      <Dialog open={deleteConfirmId !== null} onOpenChange={() => setDeleteConfirmId(null)}>
        <DialogContent className="sm:max-w-[400px] rounded-xl">
          <DialogHeader>
            <DialogTitle className="text-base text-destructive flex items-center gap-2">
              <Trash2 className="w-4 h-4" /> Delete Booking Form
            </DialogTitle>
            <DialogDescription className="text-xs">
              Are you sure you want to remove this booking form? Existing confirmed bookings will not be affected, but
              public links and widgets using this slug will no longer function.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" size="sm" onClick={() => setDeleteConfirmId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => deleteConfirmId && handleDeleteForm(deleteConfirmId)}
            >
              Delete Form
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
