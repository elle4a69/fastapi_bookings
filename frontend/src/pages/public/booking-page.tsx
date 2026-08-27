import { useState, useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { 
  Calendar as CalendarIcon, 
  Clock, 
  CheckCircle2, 
  User, 
  MapPin, 
  Sparkles, 
  ArrowRight, 
  ArrowLeft,
  CalendarCheck,
  RotateCcw,
  AlertCircle,
  Lock,
  Building,
  Check,
  Package,
  PlusCircle,
  ShoppingBag
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

interface ServiceItem {
  id: number | string;
  name: string;
  description?: string;
  duration: number;
  price?: number;
  provider_ids?: (number | string)[];
  category_ids?: (number | string)[];
  addon_ids?: (number | string)[];
}

interface ProviderItem {
  id: number | string;
  name: string;
  email?: string;
  service_ids?: (number | string)[];
}

interface LocationItem {
  id: number | string;
  name: string;
  address?: string;
  provider_ids?: (number | string)[];
  service_ids?: (number | string)[];
}

interface AddonItem {
  id: number | string;
  name: string;
  description?: string;
  price?: number;
  duration?: number;
}

interface ProductItem {
  id: number | string;
  name: string;
  description?: string;
  price?: number;
}

// Helper to normalize IDs for robust comparison (e.g. "prov-1" -> "1", 1 -> "1")
const normId = (id: any): string => {
  if (id === null || id === undefined) return "";
  return String(id).trim().replace(/^(prov|loc|svc|cat|client)-/i, "");
};

// Helper to get local date string in YYYY-MM-DD format (timezone-safe)
const getLocalDateString = (d: Date = new Date()): string => {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

// Check if a service is provided by a provider
const isServiceProvidedByProvider = (svc: ServiceItem, prov: ProviderItem): boolean => {
  const provIdNorm = normId(prov.id);
  const svcIdNorm = normId(svc.id);

  const provSvcIds = (prov.service_ids || []).map(normId);
  const svcProvIds = (svc.provider_ids || []).map(normId);

  if (provSvcIds.length > 0 && !provSvcIds.includes(svcIdNorm)) {
    return false;
  }
  if (svcProvIds.length > 0 && !svcProvIds.includes(provIdNorm)) {
    return false;
  }
  return true;
};

// Check if a provider is associated with a location
const isProviderAtLocation = (prov: ProviderItem, loc: LocationItem | null): boolean => {
  if (!loc) return true;
  const locProvIds = (loc.provider_ids || []).map(normId);
  const provLocIds = ((prov as any).location_ids || []).map(normId);

  if (locProvIds.length > 0 && !locProvIds.includes(normId(prov.id))) {
    return false;
  }
  if (provLocIds.length > 0 && !provLocIds.includes(normId(loc.id))) {
    return false;
  }
  return true;
};

// Check if a location supports a service (when no specific provider is selected)
const isServiceAtLocation = (svc: ServiceItem, loc: LocationItem | null): boolean => {
  if (!loc) return true;
  const locSvcIds = (loc.service_ids || []).map(normId);
  const svcLocIds = ((svc as any).location_ids || []).map(normId);

  if (locSvcIds.length > 0 && !locSvcIds.includes(normId(svc.id))) {
    return false;
  }
  if (svcLocIds.length > 0 && !svcLocIds.includes(normId(loc.id))) {
    return false;
  }
  return true;
};

// Check if an add-on is compatible with a selected service
const isAddonCompatibleWithService = (addon: AddonItem, svc: ServiceItem | null): boolean => {
  if (!svc) return true;
  if (Array.isArray(svc.addon_ids) && svc.addon_ids.length === 0) {
    return false;
  }
  const svcAddonIds = (svc.addon_ids || []).map(normId);

  if (svcAddonIds.length > 0) {
    return svcAddonIds.includes(normId(addon.id));
  }

  const addonSvcIds = ((addon as any).service_ids || []).map(normId);
  if (addonSvcIds.length > 0) {
    return addonSvcIds.includes(normId(svc.id));
  }

  return true;
};

export default function PublicBookingPage() {
  const { slug } = useParams<{ slug?: string }>();
  const [searchParams] = useSearchParams();

  // Extract path slug safely from HashRouter, BrowserRouter, or searchParams
  const getExtractedSlug = () => {
    if (slug && slug !== "*") return slug;
    const hashMatch = window.location.hash.match(/#?\/(?:book|booking)\/([^?#]+)/);
    if (hashMatch && hashMatch[1]) return hashMatch[1];
    const pathMatch = window.location.pathname.match(/\/(?:book|booking)\/([^?#]+)/);
    if (pathMatch && pathMatch[1]) return pathMatch[1];
    return searchParams.get("form") || searchParams.get("slug") || "standard";
  };
  const formSlug = getExtractedSlug();

  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState<any>(null);
  const [allServices, setAllServices] = useState<ServiceItem[]>([]);
  const [allProviders, setAllProviders] = useState<ProviderItem[]>([]);
  const [allLocations, setAllLocations] = useState<LocationItem[]>([]);
  const [allAddons, setAllAddons] = useState<AddonItem[]>([]);
  const [allProducts, setAllProducts] = useState<ProductItem[]>([]);

  // Current Active Tab Index in wizard
  const [activeTabIndex, setActiveTabIndex] = useState(0);
  const [modalOpen, setModalOpen] = useState(false);

  // Active selections
  const [selectedLocation, setSelectedLocation] = useState<LocationItem | null>(null);
  const [selectedService, setSelectedService] = useState<ServiceItem | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<ProviderItem | null>(null);
  const [selectedAddonIds, setSelectedAddonIds] = useState<string[]>([]);
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);

  // Lock status (from form predefined_values or URL params)
  const [isLocationLocked, setIsLocationLocked] = useState(false);
  const [isProviderLocked, setIsProviderLocked] = useState(false);
  const [isServiceLocked, setIsServiceLocked] = useState(false);

  const [selectedDate, setSelectedDate] = useState<string>(getLocalDateString());
  const [selectedTime, setSelectedTime] = useState<string>("10:00");

  // Client info
  const [clientName, setClientName] = useState("");
  const [clientEmail, setClientEmail] = useState("");
  const [clientPhone, setClientPhone] = useState("");
  const [bookingNotes, setBookingNotes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [completedBooking, setCompletedBooking] = useState<any>(null);

  // ── Iframe postMessage Handshake for widget.js ──────────────────────
  useEffect(() => {
    if (typeof window !== "undefined" && window.parent && window.parent !== window) {
      window.parent.postMessage({ event: "appReady" }, "*");
    }

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const height = Math.ceil(entry.contentRect.height || document.body.scrollHeight);
        if (typeof window !== "undefined" && window.parent && window.parent !== window) {
          window.parent.postMessage({ event: "updateWidgetSize", height }, "*");
        }
      }
    });

    if (typeof document !== "undefined" && document.body) {
      resizeObserver.observe(document.body);
    }

    const handleMessage = (event: MessageEvent) => {
      if (event.data && (event.data.action === "closeWidget" || event.data.event === "closeWidget")) {
        if (typeof window !== "undefined" && window.parent && window.parent !== window) {
          window.parent.postMessage({ event: "closeWidget" }, "*");
        }
      }
    };

    window.addEventListener("message", handleMessage);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("message", handleMessage);
    };
  }, []);

  useEffect(() => {
    loadData();
  }, [formSlug]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [bootRes, formPublicRes, sRes, pRes, lRes, formsRes, addRes, prodRes] = await Promise.all([
        apiClient.get<any>("/api/public/bootstrap").catch(() => null),
        apiClient.get<any>(`/api/public/booking-forms/${formSlug}`).catch(() => null),
        apiClient.get<any>("/api/admin/services").catch(() => []),
        apiClient.get<any>("/api/admin/providers").catch(() => []),
        apiClient.get<any>("/api/admin/locations").catch(() => []),
        apiClient.get<any>("/api/admin/booking-forms").catch(() => []),
        apiClient.get<any>("/api/admin/add-ons").catch(() => []),
        apiClient.get<any>("/api/admin/products").catch(() => [])
      ]);

      const bootData = bootRes?.data ?? bootRes;
      const publicFormData = formPublicRes?.data?.form ?? formPublicRes?.form ?? null;

      let servicesArr = Array.isArray(sRes) ? sRes : (sRes?.data ?? []);
      let providersArr = Array.isArray(pRes) ? pRes : (pRes?.data ?? []);
      let locationsArr = Array.isArray(lRes) ? lRes : (lRes?.data ?? []);
      let formsArr = Array.isArray(formsRes) ? formsRes : (formsRes?.data ?? []);
      let addonsArr = Array.isArray(addRes) ? addRes : (addRes?.data ?? []);
      let productsArr = Array.isArray(prodRes) ? prodRes : (prodRes?.data ?? []);

      if (servicesArr.length === 0 && bootData?.services) {
        servicesArr = bootData.services;
      }
      if (providersArr.length === 0 && bootData?.providers) {
        providersArr = bootData.providers;
      }
      if (locationsArr.length === 0 && bootData?.locations) {
        locationsArr = bootData.locations;
      }

      setAllServices(servicesArr);
      setAllProviders(providersArr);
      setAllLocations(locationsArr);
      setAllAddons(addonsArr);
      setAllProducts(productsArr);

      const normalizeSlug = (str: string) => str.toLowerCase().replace(/[^a-z0-9]/g, "");
      const matchingForms = formsArr.filter((f: any) => 
        f.slug === formSlug || 
        normalizeSlug(f.slug) === normalizeSlug(formSlug)
      );
      
      const matched = publicFormData || (matchingForms.length > 0 
        ? matchingForms[matchingForms.length - 1]
        : {
            name: formSlug === 'quick-consult' ? 'Quick Consult' : 'Standard Booking Intake',
            slug: formSlug,
            widget_type: formSlug === 'quick-consult' ? 'modal' : 'full'
          });

      setFormData(matched);

      // Extract predefined values from backend setup or URL parameters
      const pv = matched.predefined_values || {};
      const paramLocId = searchParams.get("location_id") ?? (pv.location_id != null ? String(pv.location_id) : null);
      const paramProvId = searchParams.get("provider_id") ?? (pv.provider_id != null ? String(pv.provider_id) : null);
      const paramSvcId = searchParams.get("service_id") ?? (pv.service_id != null ? String(pv.service_id) : null);

      let activeLoc: LocationItem | null = null;
      let activeProv: ProviderItem | null = null;
      let activeSvc: ServiceItem | null = null;

      if (paramLocId && paramLocId !== "none" && paramLocId !== "null") {
        const found = locationsArr.find((l: LocationItem) => normId(l.id) === normId(paramLocId));
        if (found) {
          activeLoc = found;
          setIsLocationLocked(true);
        }
      }

      if (paramProvId && paramProvId !== "none" && paramProvId !== "null") {
        const found = providersArr.find((p: ProviderItem) => normId(p.id) === normId(paramProvId));
        if (found) {
          activeProv = found;
          setIsProviderLocked(true);
        }
      }

      // Filter eligible services for active provider ON LOAD
      let eligibleServices = servicesArr;
      if (activeProv) {
        eligibleServices = servicesArr.filter((svc: ServiceItem) => isServiceProvidedByProvider(svc, activeProv!));
      }

      if (paramSvcId && paramSvcId !== "none" && paramSvcId !== "null") {
        const found = eligibleServices.find((s: ServiceItem) => normId(s.id) === normId(paramSvcId));
        if (found) {
          activeSvc = found;
          setIsServiceLocked(true);
        }
      }

      setSelectedLocation(activeLoc);
      setSelectedProvider(activeProv);
      setSelectedService(activeSvc);

      if (matched.widget_type === 'modal') {
        setModalOpen(true);
      }
    } catch {
      toast.error("Failed to initialize booking form.");
    } finally {
      setLoading(false);
    }
  };

  // ── Reactive URL Parameter Synchronization ──────────────────────────
  // Dynamically syncs selectedLocation, selectedProvider, selectedService to URL search params
  useEffect(() => {
    if (loading) return;

    const params = new URLSearchParams(window.location.search);
    let changed = false;

    if (selectedLocation) {
      const locIdStr = String(normId(selectedLocation.id));
      if (params.get("location_id") !== locIdStr) {
        params.set("location_id", locIdStr);
        changed = true;
      }
    } else if (params.has("location_id") && !isLocationLocked) {
      params.delete("location_id");
      changed = true;
    }

    if (selectedProvider) {
      const provIdStr = String(normId(selectedProvider.id));
      if (params.get("provider_id") !== provIdStr) {
        params.set("provider_id", provIdStr);
        changed = true;
      }
    } else if (params.has("provider_id") && !isProviderLocked) {
      params.delete("provider_id");
      changed = true;
    }

    if (selectedService) {
      const svcIdStr = String(normId(selectedService.id));
      if (params.get("service_id") !== svcIdStr) {
        params.set("service_id", svcIdStr);
        changed = true;
      }
    } else if (params.has("service_id") && !isServiceLocked) {
      params.delete("service_id");
      changed = true;
    }

    if (changed) {
      const newSearch = params.toString() ? `?${params.toString()}` : "";
      const newUrl = window.location.pathname + newSearch + window.location.hash;
      window.history.replaceState(null, "", newUrl);
    }
  }, [selectedLocation, selectedProvider, selectedService, loading, isLocationLocked, isProviderLocked, isServiceLocked]);

  // ── Relational Calculation Filters ──────────────────────────────────

  const availableLocations = (() => {
    const activeList = allLocations.filter(loc => (loc as any).active !== false && (loc as any).is_visible !== false);
    return activeList.filter(loc => {
      if (selectedProvider && !isProviderAtLocation(selectedProvider, loc)) {
        return false;
      }
      if (selectedService && !isServiceAtLocation(selectedService, loc)) {
        return false;
      }
      return true;
    });
  })();

  const availableServices = (() => {
    const activeList = allServices.filter(svc => (svc as any).active !== false && (svc as any).is_visible !== false);
    return activeList.filter(svc => {
      if (selectedProvider) {
        if (!isServiceProvidedByProvider(svc, selectedProvider)) {
          return false;
        }
      }
      if (selectedLocation) {
        if (!isServiceAtLocation(svc, selectedLocation)) {
          return false;
        }
      }
      return true;
    });
  })();

  const availableProviders = (() => {
    const activeList = allProviders.filter(prov => (prov as any).active !== false && (prov as any).is_visible !== false);
    return activeList.filter(prov => {
      if (selectedLocation && !isProviderAtLocation(prov, selectedLocation)) {
        return false;
      }
      if (selectedService && !isServiceProvidedByProvider(selectedService, prov)) {
        return false;
      }
      return true;
    });
  })();

  const availableAddons = allAddons.filter(addon => {
    if ((addon as any).active === false || (addon as any).is_visible === false) return false;
    return isAddonCompatibleWithService(addon, selectedService);
  });

  // ── Construct Dynamic Active Tabs Pipeline ──────────────────────────
  // Rule: A tab ONLY appears if the module is enabled AND not pre-selected AND items exist!

  const getActiveWizardTabs = () => {
    const tabs: { id: string; label: string }[] = [];

    let rawOrder = formData?.module_order;
    if (typeof rawOrder === "string") {
      try {
        rawOrder = JSON.parse(rawOrder);
      } catch {
        rawOrder = null;
      }
    }

    // Canonical database module_order (no cross-tenant localStorage override)
    const moduleOrder: string[] = Array.isArray(rawOrder) && rawOrder.length > 0
      ? rawOrder
      : ["location", "provider", "service", "addons", "products", "datetime", "intake", "client", "checkout", "outcome"];

    let rawEnabled = formData?.enabled_modules;
    if (typeof rawEnabled === "string") {
      try {
        rawEnabled = JSON.parse(rawEnabled);
      } catch {
        rawEnabled = {};
      }
    }
    const enabledModules: Record<string, boolean> = rawEnabled || {};

    const pv = formData?.predefined_values || {};
    // Verify that predefined entities actually exist in resolved allLocations/allProviders/allServices (resolves Phantom Step Lock)
    const locPredefined = pv.location_id != null && pv.location_id !== 0 && String(pv.location_id) !== "none" && String(pv.location_id) !== "null" && allLocations.some(l => normId(l.id) === normId(pv.location_id));
    const provPredefined = pv.provider_id != null && pv.provider_id !== 0 && String(pv.provider_id) !== "none" && String(pv.provider_id) !== "null" && allProviders.some(p => normId(p.id) === normId(pv.provider_id));
    const svcPredefined = pv.service_id != null && pv.service_id !== 0 && String(pv.service_id) !== "none" && String(pv.service_id) !== "null" && allServices.some(s => normId(s.id) === normId(pv.service_id));

    const locLocked = isLocationLocked || locPredefined || (Boolean(searchParams.get("location_id")) && searchParams.get("location_id") !== "none");
    const provLocked = isProviderLocked || provPredefined || (Boolean(searchParams.get("provider_id")) && searchParams.get("provider_id") !== "none");
    const svcLocked = isServiceLocked || svcPredefined || (Boolean(searchParams.get("service_id")) && searchParams.get("service_id") !== "none");

    const compAddons = availableAddons;

    moduleOrder.forEach((modId: string) => {
      if (enabledModules[modId] === false) return;

      if (modId === "location") {
        if (!locLocked && availableLocations.length > 0) {
          tabs.push({ id: "location", label: "Select Location" });
        }
      } else if (modId === "service") {
        if (!svcLocked && availableServices.length > 0) {
          tabs.push({ id: "service", label: "Select Service" });
        }
      } else if (modId === "provider") {
        if (!provLocked && availableProviders.length > 0) {
          tabs.push({ id: "provider", label: "Select Provider" });
        }
      } else if (modId === "addons") {
        if (compAddons.length > 0) {
          tabs.push({ id: "addons", label: "Add-ons" });
        }
      } else if (modId === "products") {
        if (allProducts.length > 0) {
          tabs.push({ id: "products", label: "Products" });
        }
      } else if (modId === "datetime") {
        tabs.push({ id: "datetime", label: "Date & Time" });
      } else if (modId === "intake") {
        tabs.push({ id: "intake", label: "Intake Notes" });
      } else if (modId === "client") {
        tabs.push({ id: "client", label: "Client Details" });
      } else if (modId === "checkout") {
        tabs.push({ id: "checkout", label: "Checkout & Summary" });
      } else if (modId === "outcome") {
        if (enabledModules["outcome"] !== false) {
          tabs.push({ id: "outcome", label: "Confirmation" });
        }
      }
    });

    if (!tabs.some(t => t.id === "datetime") && enabledModules["datetime"] !== false) {
      tabs.push({ id: "datetime", label: "Date & Time" });
    }
    if (!tabs.some(t => t.id === "client") && enabledModules["client"] !== false) {
      tabs.push({ id: "client", label: "Client Details" });
    }

    return tabs;
  };

  const wizardTabs = getActiveWizardTabs();

  // Clamp activeTabIndex when wizardTabs shrinks dynamically
  useEffect(() => {
    if (wizardTabs.length > 0 && !completedBooking && activeTabIndex >= wizardTabs.length) {
      setActiveTabIndex(Math.min(activeTabIndex, wizardTabs.length - 1));
    }
  }, [wizardTabs.length, activeTabIndex, completedBooking]);
  const currentTab = wizardTabs[activeTabIndex] || wizardTabs[0];

  const handleSelectService = (svc: ServiceItem) => {
    setSelectedService(svc);

    if (!isProviderLocked) {
      const validProviders = allProviders.filter(prov =>
        isServiceProvidedByProvider(svc, prov) && isProviderAtLocation(prov, selectedLocation)
      );

      if (selectedProvider && !validProviders.some(p => normId(p.id) === normId(selectedProvider.id))) {
        setSelectedProvider(validProviders.length > 0 ? validProviders[0] : null);
      }
    }
  };

  const handleSelectProvider = (prov: ProviderItem) => {
    setSelectedProvider(prov);

    if (!isServiceLocked) {
      const validServices = allServices.filter(svc => isServiceProvidedByProvider(svc, prov));

      if (selectedService && !validServices.some(s => normId(s.id) === normId(selectedService.id))) {
        setSelectedService(validServices.length > 0 ? validServices[0] : null);
      }
    }
  };


  const toggleAddon = (addonId: string) => {
    if (selectedAddonIds.includes(addonId)) {
      setSelectedAddonIds(selectedAddonIds.filter(id => id !== addonId));
    } else {
      setSelectedAddonIds([...selectedAddonIds, addonId]);
    }
  };

  const toggleProduct = (productId: string) => {
    if (selectedProductIds.includes(productId)) {
      setSelectedProductIds(selectedProductIds.filter(id => id !== productId));
    } else {
      setSelectedProductIds([...selectedProductIds, productId]);
    }
  };

  const settings = formData?.settings || {};
  const primaryIdentifier = settings.primary_identifier || "email";
  const showEmail = settings.show_email_field !== false;
  const showPhone = settings.show_phone_field !== false;

  const selectedAddonsList = allAddons.filter((a) => selectedAddonIds.includes(String(a.id)));
  const selectedProductsList = allProducts.filter((p) => selectedProductIds.includes(String(p.id)));

  const addonsDuration = selectedAddonsList.reduce((sum, addon) => sum + Number(addon.duration || 0), 0);
  const totalDuration = (Number(selectedService?.duration) || 60) + addonsDuration;

  const handleCreateBookingSubmit = async () => {
    const isProviderRequired = wizardTabs.some((t) => t.id === "provider");
    if (!selectedService || (isProviderRequired && !selectedProvider) || !clientName) {
      toast.error(
        isProviderRequired
          ? "Please fill in your name, service, and provider."
          : "Please fill in your name and service."
      );
      return;
    }

    if ((primaryIdentifier === "email" || primaryIdentifier === "both") && !clientEmail) {
      toast.error("Email address is required.");
      return;
    }

    if ((primaryIdentifier === "phone" || primaryIdentifier === "both") && !clientPhone) {
      toast.error("Phone number is required.");
      return;
    }

    setSubmitting(true);
    try {
      let clientId = 1;
      const targetEmail = clientEmail || `${(clientPhone || "client").replace(/[^0-9a-zA-Z]/g, "")}@client.local`;

      try {
        const clientRes = await apiClient.post<any>("/api/admin/clients", {
          name: clientName,
          email: targetEmail,
          phone: clientPhone || null
        });
        clientId = clientRes?.id || clientRes?.data?.id || 1;
      } catch {
        clientId = 1;
      }

      const [hours, mins] = selectedTime.split(':').map(Number);
      const [year, month, day] = selectedDate.split('-').map(Number);
      const start = new Date(year, month - 1, day, hours, mins, 0, 0);

      // Duration calculation including selected add-ons
      const addonsDur = selectedAddonsList.reduce((sum, addon) => sum + Number(addon.duration || 0), 0);
      const computedTotalDuration = (Number(selectedService.duration) || 60) + addonsDur;
      const end = new Date(start.getTime() + computedTotalDuration * 60000);

      const payload = {
        client_id: Number(normId(clientId)),
        service_id: Number(normId(selectedService.id)),
        provider_id: selectedProvider ? Number(normId(selectedProvider.id)) : null,
        location_id: selectedLocation?.id ? Number(normId(selectedLocation.id)) : null,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        notes: bookingNotes || null,
        addon_ids: selectedAddonIds.map((id) => Number(normId(id))),
        product_ids: selectedProductIds.map((id) => Number(normId(id)))
      };

      const bookingRes: any = await apiClient.post("/api/public/bookings", payload);

      setCompletedBooking({
        id: bookingRes?.data?.id || bookingRes?.id || Math.floor(1000 + Math.random() * 9000),
        service: selectedService.name,
        provider: selectedProvider?.name || "Any Available Provider",
        location: selectedLocation?.name || "Main Branch",
        date: selectedDate,
        time: selectedTime,
        clientName,
        clientEmail
      });

      const outcomeIndex = wizardTabs.findIndex(t => t.id === "outcome");
      if (outcomeIndex !== -1) {
        setActiveTabIndex(outcomeIndex);
      } else {
        setActiveTabIndex(wizardTabs.length);
      }
      toast.success("Booking submitted!");
    } catch (err: any) {
      toast.error(err.message || "Failed to submit booking.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4">
        <div className="text-center space-y-3">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary mx-auto"></div>
          <p className="text-sm text-muted-foreground font-medium">Loading form...</p>
        </div>
      </div>
    );
  }

  const isIframe = typeof window !== "undefined" && (window.parent !== window || searchParams.get("embed") === "true" || searchParams.get("inline") === "true");
  const isModalWidget = formData?.widget_type === 'modal';
  const isInlineRender = !isModalWidget || isIframe;

  const renderBookingWizardContent = () => (
    <div className="space-y-6">

      {/* Dynamic Tab Stepper Header (Only active tabs are shown!) */}
      {activeTabIndex < wizardTabs.length && (
        <div className="flex items-center justify-between border-b pb-4 overflow-x-auto gap-2">
          {wizardTabs.map((tab, idx) => {
            const isActive = idx === activeTabIndex;
            const isCompleted = idx < activeTabIndex;

            return (
              <div key={tab.id} className="flex items-center gap-2 shrink-0">
                <div
                  className={`flex items-center gap-2 text-xs font-bold transition-all ${
                    isActive ? "text-primary" : isCompleted ? "text-foreground" : "text-muted-foreground opacity-60"
                  }`}
                >
                  <span
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] transition-all ${
                      isActive
                        ? "bg-primary text-primary-foreground shadow-xs font-bold"
                        : isCompleted
                        ? "bg-emerald-500 text-white font-bold"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {isCompleted ? <Check className="w-3.5 h-3.5" /> : idx + 1}
                  </span>
                  <span>{tab.label}</span>
                </div>
                {idx < wizardTabs.length - 1 && (
                  <div className="h-0.5 w-6 bg-muted shrink-0 hidden sm:block" />
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Tab: Location Selection */}
      {currentTab?.id === "location" && activeTabIndex < wizardTabs.length && (
        <div className="space-y-5">
          <div>
            <h3 className="text-sm font-bold text-foreground">Choose Branch / Location</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Select your preferred branch for this appointment.</p>
          </div>

          <div className="grid gap-3 max-h-[300px] overflow-y-auto pr-1">
            {availableLocations.map((loc) => {
              const isSelected = selectedLocation && String(selectedLocation.id) === String(loc.id);
              return (
                <div
                  key={loc.id}
                  onClick={() => setSelectedLocation(loc)}
                  className={`p-4 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                    isSelected
                      ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                      : "hover:border-primary/50 bg-card"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-sm shrink-0">
                      <Building className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="font-bold text-foreground text-sm">{loc.name}</div>
                      {loc.address && <div className="text-xs text-muted-foreground">{loc.address}</div>}
                    </div>
                  </div>
                  <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${isSelected ? "bg-primary text-white border-primary" : ""}`}>
                    {isSelected && <CheckCircle2 className="w-4 h-4" />}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="pt-3">
            <Button
              className="w-full h-11 text-sm font-bold gap-2"
              disabled={!selectedLocation}
              onClick={() => setActiveTabIndex(activeTabIndex + 1)}
            >
              Continue to {wizardTabs[activeTabIndex + 1]?.label || "Next"} <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Tab: Service Selection */}
      {currentTab?.id === "service" && activeTabIndex < wizardTabs.length && (
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-foreground">Select Service</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                {isProviderLocked ? `Services offered by ${selectedProvider?.name}` : "Choose the service you wish to book"}
              </p>
            </div>
            <Badge variant="outline" className="text-xs font-semibold">{availableServices.length} Options</Badge>
          </div>

          <div className="grid gap-3 max-h-[300px] overflow-y-auto pr-1">
            {availableServices.map((svc) => {
              const isSelected = selectedService && String(selectedService.id) === String(svc.id);
              return (
                <div
                  key={svc.id}
                  onClick={() => handleSelectService(svc)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                    isSelected
                      ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                      : "hover:border-primary/50 bg-card"
                  }`}
                >
                  <div>
                    <div className="font-bold text-foreground text-sm">{svc.name}</div>
                    <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-3">
                      <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {svc.duration} mins</span>
                      {svc.price && <span className="font-semibold text-emerald-600">${Number(svc.price).toFixed(2)}</span>}
                    </div>
                  </div>
                  <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${isSelected ? "bg-primary text-white border-primary" : ""}`}>
                    {isSelected && <CheckCircle2 className="w-4 h-4" />}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex gap-3 pt-3">
            {activeTabIndex > 0 && (
              <Button variant="outline" className="flex-1 h-11 font-semibold" onClick={() => setActiveTabIndex(activeTabIndex - 1)}>
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
              </Button>
            )}
            <Button
              className="flex-1 h-11 text-sm font-bold gap-2"
              disabled={!selectedService}
              onClick={() => setActiveTabIndex(activeTabIndex + 1)}
            >
              Continue to {wizardTabs[activeTabIndex + 1]?.label || "Next"} <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Tab: Provider Selection */}
      {currentTab?.id === "provider" && activeTabIndex < wizardTabs.length && (
        <div className="space-y-5">
          <div>
            <h3 className="text-sm font-bold text-foreground">Choose Provider</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Select the team member for your appointment ({availableProviders.length} available).
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[300px] overflow-y-auto pr-1">
            {availableProviders.map((p) => {
              const isSelected = selectedProvider && String(selectedProvider.id) === String(p.id);
              return (
                <div
                  key={p.id}
                  onClick={() => handleSelectProvider(p)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                    isSelected
                      ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                      : "hover:border-primary/50 bg-card"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Avatar className="w-9 h-9 rounded-full bg-primary/10 text-primary">
                      <AvatarFallback className="text-xs font-bold bg-primary/10 text-primary">
                        {p.name.charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="font-semibold text-sm">{p.name}</div>
                  </div>
                  <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${isSelected ? "bg-primary text-white border-primary" : ""}`}>
                    {isSelected && <CheckCircle2 className="w-4 h-4" />}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex gap-3 pt-3">
            {activeTabIndex > 0 && (
              <Button variant="outline" className="flex-1 h-11 font-semibold" onClick={() => setActiveTabIndex(activeTabIndex - 1)}>
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
              </Button>
            )}
            <Button
              className="flex-1 h-11 text-sm font-bold gap-2"
              disabled={!selectedProvider}
              onClick={() => setActiveTabIndex(activeTabIndex + 1)}
            >
              Continue to {wizardTabs[activeTabIndex + 1]?.label || "Next"} <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Tab: Service Add-ons (ONLY rendered if items exist!) */}
      {currentTab?.id === "addons" && activeTabIndex < wizardTabs.length && (
        <div className="space-y-5">
          <div>
            <h3 className="text-sm font-bold text-foreground">Enhance Your Session (Optional Add-ons)</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Select optional extras to add to your service.</p>
          </div>

          <div className="grid gap-3 max-h-[300px] overflow-y-auto pr-1">
            {availableAddons.map((addon) => {
              const isSelected = selectedAddonIds.includes(String(addon.id));
              return (
                <div
                  key={addon.id}
                  onClick={() => toggleAddon(String(addon.id))}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                    isSelected
                      ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                      : "hover:border-primary/50 bg-card"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                      <PlusCircle className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="font-bold text-foreground text-sm">{addon.name}</div>
                      {addon.description && <div className="text-xs text-muted-foreground">{addon.description}</div>}
                      {addon.price && <div className="text-xs font-semibold text-emerald-600 mt-0.5">+${Number(addon.price).toFixed(2)}</div>}
                    </div>
                  </div>
                  <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${isSelected ? "bg-primary text-white border-primary" : ""}`}>
                    {isSelected && <CheckCircle2 className="w-4 h-4" />}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex gap-3 pt-3">
            {activeTabIndex > 0 && (
              <Button variant="outline" className="flex-1 h-11 font-semibold" onClick={() => setActiveTabIndex(activeTabIndex - 1)}>
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
              </Button>
            )}
            <Button className="flex-1 h-11 font-bold gap-2" onClick={() => setActiveTabIndex(activeTabIndex + 1)}>
              Continue to {wizardTabs[activeTabIndex + 1]?.label || "Next"} <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Tab: Products & Packages (ONLY rendered if items exist!) */}
      {currentTab?.id === "products" && activeTabIndex < wizardTabs.length && (
        <div className="space-y-5">
          <div>
            <h3 className="text-sm font-bold text-foreground">Featured Products & Bundles</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Add products to your booking invoice.</p>
          </div>

          <div className="grid gap-3 max-h-[300px] overflow-y-auto pr-1">
            {allProducts.map((prod) => {
              const isSelected = selectedProductIds.includes(String(prod.id));
              return (
                <div
                  key={prod.id}
                  onClick={() => toggleProduct(String(prod.id))}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                    isSelected
                      ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                      : "hover:border-primary/50 bg-card"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-xs shrink-0">
                      <ShoppingBag className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="font-bold text-foreground text-sm">{prod.name}</div>
                      {prod.description && <div className="text-xs text-muted-foreground">{prod.description}</div>}
                      {prod.price && <div className="text-xs font-semibold text-emerald-600 mt-0.5">${Number(prod.price).toFixed(2)}</div>}
                    </div>
                  </div>
                  <div className={`w-5 h-5 rounded-full border flex items-center justify-center ${isSelected ? "bg-primary text-white border-primary" : ""}`}>
                    {isSelected && <CheckCircle2 className="w-4 h-4" />}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex gap-3 pt-3">
            {activeTabIndex > 0 && (
              <Button variant="outline" className="flex-1 h-11 font-semibold" onClick={() => setActiveTabIndex(activeTabIndex - 1)}>
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
              </Button>
            )}
            <Button className="flex-1 h-11 font-bold gap-2" onClick={() => setActiveTabIndex(activeTabIndex + 1)}>
              Continue to {wizardTabs[activeTabIndex + 1]?.label || "Next"} <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Tab: Date & Time Slots */}
      {currentTab?.id === "datetime" && activeTabIndex < wizardTabs.length && (
        <div className="space-y-5">
          <div>
            <Label className="text-sm font-bold mb-2 block">Appointment Date</Label>
            <Input
              type="date"
              min={getLocalDateString()}
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="h-10"
            />
          </div>

          <div>
            <Label className="text-sm font-bold mb-2 block">Available Start Time</Label>
            <div className="grid grid-cols-3 gap-2">
              {["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"].map((t) => (
                <Button
                  key={t}
                  type="button"
                  variant={selectedTime === t ? "default" : "outline"}
                  className="h-10 text-sm font-semibold"
                  onClick={() => setSelectedTime(t)}
                >
                  {t}
                </Button>
              ))}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-muted/40 border text-xs space-y-1.5">
            <div className="font-bold flex items-center gap-2 text-foreground">
              <CalendarCheck className="w-4 h-4 text-primary" /> Reservation Details
            </div>
            <div className="text-muted-foreground">{selectedService?.name} with {selectedProvider?.name}</div>
            <div className="text-foreground font-semibold pt-1">{selectedDate} at {selectedTime} ({totalDuration} mins)</div>
          </div>

          <div className="flex gap-3 pt-2">
            {activeTabIndex > 0 && (
              <Button variant="outline" className="flex-1 h-11 font-semibold" onClick={() => setActiveTabIndex(activeTabIndex - 1)}>
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
              </Button>
            )}
            <Button className="flex-1 h-11 font-bold" onClick={() => setActiveTabIndex(activeTabIndex + 1)}>
              Continue to {wizardTabs[activeTabIndex + 1]?.label || "Next"} <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* Tab: Intake Notes & Questions */}
      {currentTab?.id === "intake" && activeTabIndex < wizardTabs.length && (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-bold text-foreground">Intake Notes & Special Requests</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Provide any details or requests for your service provider.</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="intake_notes" className="text-xs font-semibold">Special Requests / Notes</Label>
            <Textarea
              id="intake_notes"
              placeholder="Notes or requirements for your provider..."
              value={bookingNotes}
              onChange={(e) => setBookingNotes(e.target.value)}
              rows={4}
            />
          </div>

          <div className="flex gap-3 pt-3">
            {activeTabIndex > 0 && (
              <Button variant="outline" className="flex-1 h-11 font-semibold" onClick={() => setActiveTabIndex(activeTabIndex - 1)}>
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
              </Button>
            )}
            <Button className="flex-1 h-11 font-bold gap-2" onClick={() => setActiveTabIndex(activeTabIndex + 1)}>
              Continue to {wizardTabs[activeTabIndex + 1]?.label || "Next"} <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Tab: Client Details */}
      {currentTab?.id === "client" && activeTabIndex < wizardTabs.length && (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="pub_name" className="text-xs font-semibold">Full Name *</Label>
            <Input id="pub_name" placeholder="John Doe" value={clientName} onChange={(e) => setClientName(e.target.value)} className="h-10" />
          </div>

          {showEmail && (
            <div className="space-y-1.5">
              <Label htmlFor="pub_email" className="text-xs font-semibold">
                Email Address {(primaryIdentifier === "email" || primaryIdentifier === "both") ? "*" : ""}
              </Label>
              <Input id="pub_email" type="email" placeholder="john@example.com" value={clientEmail} onChange={(e) => setClientEmail(e.target.value)} className="h-10" />
            </div>
          )}

          {showPhone && (
            <div className="space-y-1.5">
              <Label htmlFor="pub_phone" className="text-xs font-semibold">
                Phone Number {(primaryIdentifier === "phone" || primaryIdentifier === "both") ? "*" : ""}
              </Label>
              <Input id="pub_phone" placeholder="(555) 000-0000" value={clientPhone} onChange={(e) => setClientPhone(e.target.value)} className="h-10" />
            </div>
          )}

          {!wizardTabs.some(t => t.id === "intake") && (
            <div className="space-y-1.5">
              <Label htmlFor="pub_notes" className="text-xs font-semibold">Special Requests / Notes</Label>
              <Textarea id="pub_notes" placeholder="Notes for your provider..." value={bookingNotes} onChange={(e) => setBookingNotes(e.target.value)} rows={3} />
            </div>
          )}

          <div className="flex gap-3 pt-4">
            {activeTabIndex > 0 && (
              <Button variant="outline" className="flex-1 h-11 font-semibold" onClick={() => setActiveTabIndex(activeTabIndex - 1)}>
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
              </Button>
            )}
            {wizardTabs.some(t => t.id === "checkout") && wizardTabs.findIndex(t => t.id === "checkout") > activeTabIndex ? (
              <Button
                className="flex-1 h-11 font-bold gap-2"
                onClick={() => setActiveTabIndex(activeTabIndex + 1)}
              >
                Continue to {wizardTabs[activeTabIndex + 1]?.label || "Checkout"} <ArrowRight className="w-4 h-4" />
              </Button>
            ) : (
              <Button className="flex-1 h-11 font-bold bg-primary text-primary-foreground" disabled={submitting} onClick={handleCreateBookingSubmit}>
                {submitting ? "Booking..." : "Confirm & Book Now"}
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Tab: Checkout & Summary */}
      {currentTab?.id === "checkout" && activeTabIndex < wizardTabs.length && (
        <div className="space-y-5">
          <div>
            <h3 className="text-sm font-bold text-foreground">Review & Confirm Your Booking</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Please review your appointment summary before submitting.</p>
          </div>

          <div className="p-4 rounded-xl border bg-card space-y-3 text-xs">
            <div className="flex justify-between items-center border-b pb-2">
              <span className="font-bold text-foreground text-sm">{selectedService?.name || "Selected Service"}</span>
              <span className="font-bold text-emerald-600 text-sm">
                ${(
                  (Number(selectedService?.price) || 0) +
                  selectedAddonsList.reduce((acc, a) => acc + (Number(a.price) || 0), 0) +
                  selectedProductsList.reduce((acc, p) => acc + (Number(p.price) || 0), 0)
                ).toFixed(2)}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-muted-foreground">
              <div><span className="font-semibold text-foreground">Provider:</span> {selectedProvider?.name || "Any"}</div>
              <div><span className="font-semibold text-foreground">Location:</span> {selectedLocation?.name || "Main Branch"}</div>
              <div><span className="font-semibold text-foreground">Date:</span> {selectedDate}</div>
              <div><span className="font-semibold text-foreground">Time:</span> {selectedTime} ({totalDuration} mins)</div>
            </div>

            {selectedAddonsList.length > 0 && (
              <div className="border-t pt-2">
                <span className="font-semibold text-foreground block mb-1">Add-ons:</span>
                {selectedAddonsList.map(a => (
                  <div key={a.id} className="flex justify-between text-muted-foreground">
                    <span>+ {a.name}</span>
                    {a.price && <span>+${Number(a.price).toFixed(2)}</span>}
                  </div>
                ))}
              </div>
            )}

            {selectedProductsList.length > 0 && (
              <div className="border-t pt-2">
                <span className="font-semibold text-foreground block mb-1">Products:</span>
                {selectedProductsList.map(p => (
                  <div key={p.id} className="flex justify-between text-muted-foreground">
                    <span>+ {p.name}</span>
                    {p.price && <span>+${Number(p.price).toFixed(2)}</span>}
                  </div>
                ))}
              </div>
            )}

            <div className="border-t pt-2">
              <span className="font-semibold text-foreground block mb-1">Client Details:</span>
              <div className="text-muted-foreground space-y-0.5">
                <div>Name: {clientName}</div>
                {clientEmail && <div>Email: {clientEmail}</div>}
                {clientPhone && <div>Phone: {clientPhone}</div>}
                {bookingNotes && <div>Notes: {bookingNotes}</div>}
              </div>
            </div>
          </div>

          <div className="flex gap-3 pt-3">
            {activeTabIndex > 0 && (
              <Button variant="outline" className="flex-1 h-11 font-semibold" onClick={() => setActiveTabIndex(activeTabIndex - 1)}>
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
              </Button>
            )}
            <Button className="flex-1 h-11 font-bold bg-primary text-primary-foreground" disabled={submitting} onClick={handleCreateBookingSubmit}>
              {submitting ? "Booking..." : "Confirm & Book Now"}
            </Button>
          </div>
        </div>
      )}

      {/* Confirmation / Outcome Screen */}
      {(currentTab?.id === "outcome" || activeTabIndex >= wizardTabs.length) && completedBooking && (
        <div className="text-center space-y-5 py-4">
          <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-10 h-10" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-foreground">Booking Confirmed!</h2>
            <p className="text-xs text-muted-foreground mt-1">Thank you {completedBooking.clientName}. Your appointment has been registered.</p>
          </div>

          <div className="p-4 rounded-xl border bg-card text-left text-xs space-y-2 max-w-sm mx-auto shadow-xs">
            <div className="flex justify-between text-muted-foreground border-b pb-2">
              <span>Booking Ref</span>
              <span className="font-mono font-bold text-foreground">#{completedBooking.id}</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Service</span>
              <span className="font-semibold text-foreground">{completedBooking.service}</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Provider</span>
              <span className="font-semibold text-foreground">{completedBooking.provider}</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Date & Time</span>
              <span className="font-semibold text-primary">{completedBooking.date} at {completedBooking.time}</span>
            </div>
          </div>

          <Button
            className="w-full max-w-sm h-11 font-semibold"
            onClick={() => {
              setActiveTabIndex(0);
              setCompletedBooking(null);
              setModalOpen(false);
              if (typeof window !== "undefined" && window.parent && window.parent !== window) {
                window.parent.postMessage({ event: "closeWidget" }, "*");
              }
            }}
          >
            Book Another Session
          </Button>
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 font-sans text-foreground">
      {/* Top Banner Header */}
      <header className="bg-card border-b py-4 px-6 shadow-xs sticky top-0 z-30">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-primary text-primary-foreground flex items-center justify-center font-bold text-lg shadow-xs">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h1 className="font-bold text-lg leading-tight">{formData?.name || "Book an Appointment"}</h1>
              <p className="text-xs text-muted-foreground">Pre-configured Booking Intake Engine</p>
            </div>
          </div>
          {isModalWidget && (
            <Button onClick={() => setModalOpen(true)} className="gap-2 font-bold shadow-xs">
              <CalendarCheck className="w-4 h-4" /> Book Appointment
            </Button>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-4xl mx-auto p-4 md:p-8">
        {isInlineRender ? (
          /* Standard Full Page or Iframe Embedded Form */
          <Card className="border shadow-lg rounded-2xl overflow-hidden bg-card">
            <CardHeader className="bg-muted/30 border-b p-6">
              <CardTitle className="text-xl font-bold flex items-center gap-2">
                <CalendarIcon className="w-5 h-5 text-primary" /> {formData?.name || "Standard Booking Intake"}
              </CardTitle>
              <CardDescription>Select your desired service and appointment time.</CardDescription>
            </CardHeader>
            <CardContent className="p-6 md:p-8">
              {renderBookingWizardContent()}
            </CardContent>
          </Card>
        ) : (
          /* Modal Form Landing Preview */
          <div className="text-center py-16 space-y-6">
            <div className="w-20 h-20 rounded-3xl bg-primary/10 text-primary flex items-center justify-center mx-auto shadow-sm">
              <CalendarCheck className="w-10 h-10" />
            </div>
            <div className="max-w-xl mx-auto space-y-3">
              <Badge variant="outline" className="px-3 py-1 text-xs font-semibold uppercase tracking-wider text-primary bg-primary/5">
                Modal Widget Form
              </Badge>
              <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl">
                {formData?.name || "Quick Consult Booking"}
              </h2>
              <p className="text-muted-foreground text-base">
                Click below to launch the modal booking window and reserve your time slot instantly.
              </p>
            </div>

            <Button size="lg" className="h-12 px-8 text-base font-bold gap-2 shadow-md hover:shadow-lg transition-all" onClick={() => setModalOpen(true)}>
              Launch Booking Modal <ArrowRight className="w-5 h-5" />
            </Button>
          </div>
        )}
      </main>

      {/* Modal Widget Container */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="sm:max-w-[550px] p-6 rounded-2xl">
          <DialogHeader className="pb-3 border-b mb-4">
            <DialogTitle className="text-xl font-bold flex items-center gap-2">
              <CalendarIcon className="w-5 h-5 text-primary" /> {formData?.name || "Quick Booking"}
            </DialogTitle>
            <DialogDescription>Complete your appointment reservation below.</DialogDescription>
          </DialogHeader>

          {renderBookingWizardContent()}
        </DialogContent>
      </Dialog>
    </div>
  );
}
