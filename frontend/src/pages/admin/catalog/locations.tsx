import { useEffect, useState, useRef } from "react";
import { Plus, Search, MapPin, Loader2, Save, Trash2, ArrowLeft, Upload, X, User, Globe, CalendarRange, Sparkles, Layers, Box, ShoppingBag, Gift, Clock } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { useAutoSave } from "@/hooks/use-auto-save";
import { AutoSaveStatus } from "@/components/ui/auto-save-status";


import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";

interface Location {
  id: string;
  name: string;
  address?: string;
  phone?: string;
  contact_person?: string;
  image?: string;
  timezone?: string;
  provider_ids?: string[];
  service_ids?: string[];
  category_ids?: string[];
  product_ids?: string[];
}

interface ItemBase {
  id: string;
  name: string;
  avatar?: string;
  image?: string;
  color?: string;
  price?: number;
  duration?: number;
}

interface Resource {
  id: string;
  name: string;
  type: string;
  location_id?: string | number;
  active: boolean;
}

interface DaySchedule {
  is_working: boolean;
  start_time: string;
  end_time: string;
}

interface Provider {
  id: string;
  name: string;
  email?: string;
  active: boolean;
  avatar?: string;
  image?: string;
  color?: string;
  weekly_schedule?: Record<string, DaySchedule>;
}

const DAYS_OF_WEEK = [
  { key: 'monday', label: 'Monday' },
  { key: 'tuesday', label: 'Tuesday' },
  { key: 'wednesday', label: 'Wednesday' },
  { key: 'thursday', label: 'Thursday' },
  { key: 'friday', label: 'Friday' },
  { key: 'saturday', label: 'Saturday' },
  { key: 'sunday', label: 'Sunday' },
];

const TIME_OPTIONS = [
  "06:00", "07:00", "08:00", "09:00", "10:00", "11:00", "12:00",
  "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00"
];

const createDefaultWeeklySchedule = (): Record<string, DaySchedule> => {
  const schedule: Record<string, DaySchedule> = {};
  DAYS_OF_WEEK.forEach((day) => {
    const isWeekend = day.key === 'saturday' || day.key === 'sunday';
    schedule[day.key] = {
      is_working: !isWeekend,
      start_time: "09:00",
      end_time: "17:00",
    };
  });
  return schedule;
};

export default function LocationsPage() {
  const [locations, setLocations] = useState<Location[]>([]);
  const [filteredLocations, setFilteredLocations] = useState<Location[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedLocation, setSelectedLocation] = useState<Location | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  
  // Sidebar modes & listings
  const [sidebarMode, setSidebarMode] = useState<'locations' | 'providers' | 'services'>('locations');
  const [providers, setProviders] = useState<Provider[]>([]);
  const [filteredProviders, setFilteredProviders] = useState<Provider[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);
  
  const [services, setServices] = useState<any[]>([]);
  const [filteredServices, setFilteredServices] = useState<any[]>([]);
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(null);
  
  const [categories, setCategories] = useState<ItemBase[]>([]);
  const [addOns, setAddOns] = useState<ItemBase[]>([]);
  const [resources, setResources] = useState<Resource[]>([]);
  const [products, setProducts] = useState<ItemBase[]>([]);
  const [packages, setPackages] = useState<ItemBase[]>([]);
  
  const [resourceLocationIds, setResourceLocationIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUpdatingRelation, setIsUpdatingRelation] = useState(false);

  // Form State
  const [formData, setFormData] = useState<Partial<Location>>({});

  const { triggerSave, saveState, retry } = useAutoSave<Partial<Location>>({
    onSave: async (payload) => {
      if (!selectedLocation) return;
      try {
        const res = await apiClient.put<any>(`/api/admin/locations/${selectedLocation.id}`, payload);
        const savedLocation = res?.data || res;
        
        // Update local lists
        setLocations(prev => prev.map(l => String(l.id) === String(savedLocation.id) ? savedLocation : l));
        // Keep selectedLocation fresh
        setSelectedLocation(savedLocation);
      } catch (error: any) {
        toast.error(error.message || "Failed to auto-save changes.");
        throw error;
      }
    },
    debounceMs: 500
  });

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (searchQuery.trim() === "") {
      setFilteredLocations(locations);
      setFilteredProviders(providers);
      setFilteredServices(services);
    } else {
      const lowerQuery = searchQuery.toLowerCase();
      setFilteredLocations(
        locations.filter(loc => loc && loc.name && loc.name.toLowerCase().includes(lowerQuery))
      );
      setFilteredProviders(
        providers.filter(prov => prov && prov.name && prov.name.toLowerCase().includes(lowerQuery))
      );
      setFilteredServices(
        services.filter(svc => svc && svc.name && svc.name.toLowerCase().includes(lowerQuery))
      );
    }
  }, [searchQuery, locations, providers, services, sidebarMode]);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [locsRes, provsRes, servsRes, catsRes, addonsRes, resourcesRes, productsRes, packagesRes] = await Promise.all([
        apiClient.get<any>("/api/admin/locations").catch(() => ({ data: [] })),
        apiClient.get<any>("/api/admin/providers").catch(() => ({ data: [] })),
        apiClient.get<any>("/api/admin/services").catch(() => ({ data: [] })),
        apiClient.get<any>("/api/admin/categories").catch(() => ({ data: [] })),
        apiClient.get<any>("/api/admin/add-ons").catch(() => []),
        apiClient.get<any>("/api/admin/resources").catch(() => []),
        apiClient.get<any>("/api/admin/products").catch(() => []),
        apiClient.get<any>("/api/admin/packages").catch(() => []),
      ]);

      setLocations(Array.isArray(locsRes) ? locsRes : (locsRes?.data ?? []));
      setCategories(Array.isArray(catsRes) ? catsRes : (catsRes?.data ?? []));
      setAddOns(Array.isArray(addonsRes) ? addonsRes : (addonsRes?.data ?? []));
      setResources(Array.isArray(resourcesRes) ? resourcesRes : (resourcesRes?.data ?? []));
      setProducts(Array.isArray(productsRes) ? productsRes : (productsRes?.data ?? []));
      setPackages(Array.isArray(packagesRes) ? packagesRes : (packagesRes?.data ?? []));

      const rawProviders = Array.isArray(provsRes) ? provsRes : (provsRes?.data ?? []);
      const mappedProviders = rawProviders.map((p: any) => ({
        ...p,
        id: String(p.id),
        weekly_schedule: p.weekly_schedule || createDefaultWeeklySchedule()
      }));
      setProviders(mappedProviders);
      if (mappedProviders.length > 0) {
        setSelectedProviderId(mappedProviders[0].id);
      }

      const rawServices = Array.isArray(servsRes) ? servsRes : (servsRes?.data ?? []);
      setServices(rawServices);
      if (rawServices.length > 0) {
        setSelectedServiceId(String(rawServices[0].id));
      }

    } catch (error: any) {
      toast.error(error.message || "Failed to load data.");
    } finally {
      setIsLoading(false);
    }
  };

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        const updated = { ...formData, image: reader.result as string };
        setFormData(updated);
        toast.success("Location image uploaded");
        if (selectedLocation) {
          triggerSave(updated, true);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSelectLocation = (location: Location) => {
    setSelectedLocation(location);
    setFormData({
      name: location.name,
      address: location.address || "",
      phone: location.phone || "",
      contact_person: location.contact_person || "",
      image: location.image || "",
      timezone: location.timezone || "Australia/Melbourne",
      provider_ids: (location.provider_ids || []).map(String),
      service_ids: (location.service_ids || []).map(String),
      category_ids: (location.category_ids || []).map(String),
      product_ids: (location.product_ids || []).map(String),
    });
    
    const assignedResourceIds = resources
      .filter(r => String(r.location_id) === String(location.id))
      .map(r => String(r.id));
    setResourceLocationIds(assignedResourceIds);
    setIsEditing(true);
  };

  const handleCreateNew = () => {
    setSelectedLocation(null);
    setFormData({
      name: "",
      address: "",
      phone: "",
      contact_person: "",
      image: "",
      timezone: "Australia/Melbourne",
      provider_ids: [],
      service_ids: [],
      category_ids: [],
      product_ids: [],
    });
    setResourceLocationIds([]);
    setIsEditing(true);
  };

  const handleSave = async () => {
    if (!formData.name) {
      toast.error("Name is required.");
      return;
    }

    setIsSaving(true);
    try {
      let savedLocation: Location;
      if (selectedLocation) {
        // Update
        const res = await apiClient.put<any>(`/api/admin/locations/${selectedLocation.id}`, formData);
        savedLocation = res?.data || res;
        setLocations(locations.map(l => String(l.id) === String(savedLocation.id) ? savedLocation : l));
        setSelectedLocation(savedLocation);
        toast.success("Location updated successfully.");
      } else {
        // Create
        const res = await apiClient.post<any>("/api/admin/locations", formData);
        savedLocation = res?.data || res;
        setLocations([...locations, savedLocation]);
        setSelectedLocation(savedLocation);
        toast.success("Location created successfully.");
      }

      // Sync physical resources location_id field
      const targetLocationId = savedLocation.id;
      for (const res of resources) {
        const isCurrentlyAssigned = String(res.location_id) === String(targetLocationId);
        const shouldBeAssigned = resourceLocationIds.includes(String(res.id));
        
        if (shouldBeAssigned && !isCurrentlyAssigned) {
          await apiClient.put(`/api/admin/resources/${res.id}`, {
            ...res,
            location_id: parseInt(targetLocationId)
          });
        } else if (!shouldBeAssigned && isCurrentlyAssigned) {
          await apiClient.put(`/api/admin/resources/${res.id}`, {
            ...res,
            location_id: null
          });
        }
      }

      // Refresh data to fetch updated resource locations
      const refreshedResources = await apiClient.get<any>("/api/admin/resources").catch(() => []);
      setResources(Array.isArray(refreshedResources) ? refreshedResources : (refreshedResources?.data ?? []));

      setIsEditing(true);
    } catch (error: any) {
      toast.error(error.message || "Failed to save location.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedLocation) return;
    if (!window.confirm("Are you sure you want to delete this location?")) return;

    setIsDeleting(true);
    try {
      await apiClient.delete(`/api/admin/locations/${selectedLocation.id}`);
      setLocations(locations.filter(l => l.id !== selectedLocation.id));
      setSelectedLocation(null);
      setFormData({});
      toast.success("Location deleted successfully.");
    } catch (error: any) {
      toast.error(error.message || "Failed to delete location.");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCheckboxChange = (field: 'provider_ids' | 'service_ids' | 'category_ids' | 'product_ids', id: string, checked: boolean) => {
    setFormData(prev => {
      const currentList = prev[field] || [];
      const updatedList = checked 
        ? [...currentList, String(id)] 
        : currentList.filter(itemId => String(itemId) !== String(id));
      
      const updated = { ...prev, [field]: updatedList };
      if (selectedLocation) {
        triggerSave(updated, true);
      }
      return updated;
    });
  };

  const handleResourceCheckboxChange = async (id: string, checked: boolean) => {
    if (checked) {
      setResourceLocationIds(prev => [...prev, String(id)]);
    } else {
      setResourceLocationIds(prev => prev.filter(rid => String(rid) !== String(id)));
    }

    if (selectedLocation) {
      try {
        const resObj = resources.find(r => String(r.id) === String(id));
        if (resObj) {
          await apiClient.put(`/api/admin/resources/${id}`, {
            ...resObj,
            location_id: checked ? parseInt(selectedLocation.id) : null
          });
          toast.success("Resource assignment updated");
          
          const refreshedResources = await apiClient.get<any>("/api/admin/resources").catch(() => []);
          setResources(Array.isArray(refreshedResources) ? refreshedResources : (refreshedResources?.data ?? []));
        }
      } catch (error: any) {
        toast.error(error.message || "Failed to update resource assignment.");
      }
    }
  };

  const handleAccordionChange = (value: string) => {
    if (value) {
      // Dynamic Left Sidebar Switching depending on Accordion Tab
      if (value === "scheduling") {
        setSidebarMode("providers");
        if (providers.length > 0 && !selectedProviderId) {
          setSelectedProviderId(providers[0].id);
        }
      } else if (["addons", "resources", "products", "packages"].includes(value)) {
        setSidebarMode("services");
        if (services.length > 0 && !selectedServiceId) {
          setSelectedServiceId(String(services[0].id));
        }
      } else {
        setSidebarMode("locations");
      }

      setTimeout(() => {
        const itemElement = document.getElementById(`item-${value}`);
        const scrollContainer = document.getElementById("details-scroll-container");
        if (itemElement && scrollContainer) {
          const containerTop = scrollContainer.getBoundingClientRect().top;
          const elementTop = itemElement.getBoundingClientRect().top;
          const relativeOffset = elementTop - containerTop;
          scrollContainer.scrollBy({
            top: relativeOffset - 8, // 8px spacing offset
            behavior: 'smooth'
          });
        }
      }, 250);
    }
  };

  // Provider schedule update
  const handleSaveProviderSchedule = async (providerId: string, schedule: Record<string, DaySchedule>) => {
    setIsUpdatingRelation(true);
    try {
      const provider = providers.find(p => String(p.id) === String(providerId));
      if (!provider) return;
      
      const payload = {
        name: provider.name,
        active: provider.active,
        weekly_schedule: schedule
      };
      
      await apiClient.put(`/api/admin/providers/${providerId}`, payload);
      setProviders(providers.map(p => String(p.id) === String(providerId) ? { ...p, weekly_schedule: schedule } : p));
      toast.success("Provider schedule updated successfully.");
    } catch (err: any) {
      toast.error(err.message || "Failed to update schedule.");
    } finally {
      setIsUpdatingRelation(false);
    }
  };

  const updateProviderWorkDay = (dayKey: string, isWorking: boolean, startTime: string, endTime: string) => {
    if (!selectedProviderId) return;
    const provider = providers.find(p => String(p.id) === String(selectedProviderId));
    if (!provider) return;

    const currentSchedule = provider.weekly_schedule || createDefaultWeeklySchedule();
    const updatedSchedule = {
      ...currentSchedule,
      [dayKey]: { is_working: isWorking, start_time: startTime, end_time: endTime }
    };

    handleSaveProviderSchedule(selectedProviderId, updatedSchedule);
  };

  // Service relationships updates
  const handleSaveServiceAddOns = async (serviceId: string, addonIds: string[]) => {
    setIsUpdatingRelation(true);
    try {
      const service = services.find(s => String(s.id) === String(serviceId));
      if (!service) return;
      
      const payload = {
        ...service,
        addon_ids: addonIds.map(Number)
      };
      
      await apiClient.put(`/api/admin/services/${serviceId}`, payload);
      setServices(services.map(s => String(s.id) === String(serviceId) ? { ...s, addon_ids: addonIds.map(Number) } : s));
      toast.success("Service add-ons updated successfully.");
    } catch (err: any) {
      toast.error(err.message || "Failed to update add-ons.");
    } finally {
      setIsUpdatingRelation(false);
    }
  };

  const handleSaveServiceProducts = async (serviceId: string, productIds: string[]) => {
    setIsUpdatingRelation(true);
    try {
      const service = services.find(s => String(s.id) === String(serviceId));
      if (!service) return;
      
      const payload = {
        ...service,
        product_ids: productIds.map(Number)
      };
      
      await apiClient.put(`/api/admin/services/${serviceId}`, payload);
      setServices(services.map(s => String(s.id) === String(serviceId) ? { ...s, product_ids: productIds.map(Number) } : s));
      toast.success("Service products updated successfully.");
    } catch (err: any) {
      toast.error(err.message || "Failed to update products.");
    } finally {
      setIsUpdatingRelation(false);
    }
  };

  const handleSaveServiceResources = async (serviceId: string, requirements: any[]) => {
    setIsUpdatingRelation(true);
    try {
      const service = services.find(s => String(s.id) === String(serviceId));
      if (!service) return;
      
      const payload = {
        ...service,
        requirements: requirements
      };
      
      await apiClient.put(`/api/admin/services/${serviceId}`, payload);
      setServices(services.map(s => String(s.id) === String(serviceId) ? { ...s, requirements: requirements } : s));
      toast.success("Service resource requirements updated successfully.");
    } catch (err: any) {
      toast.error(err.message || "Failed to update resource requirements.");
    } finally {
      setIsUpdatingRelation(false);
    }
  };

  const activeProvider = providers.find(p => String(p.id) === String(selectedProviderId));
  const activeService = services.find(s => String(s.id) === String(selectedServiceId));

  const resourcesByType = resources.reduce<Record<string, Resource[]>>((acc, res) => {
    if (!acc[res.type]) acc[res.type] = [];
    acc[res.type].push(res);
    return acc;
  }, {});

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-2 text-sm text-muted-foreground">Loading Locations...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col md:flex-row h-[calc(100vh-65px)] w-full overflow-hidden bg-background font-sans">
      {/* LEFT PANE: List */}
      <div className={`flex flex-col md:w-[35%] border-r bg-muted/20 transition-all duration-300 ${selectedLocation || isEditing ? 'hidden md:flex' : 'flex w-full'}`}>
        <div className="p-4 flex flex-col gap-4 border-b bg-card">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold tracking-tight font-heading">
              {sidebarMode === 'locations' ? 'Locations' : sidebarMode === 'providers' ? 'Providers List' : 'Services List'}
            </h2>
            {sidebarMode === 'locations' ? (
              <Button size="sm" onClick={handleCreateNew} className="min-h-[40px] px-4 rounded-full">
                <Plus className="mr-1 h-4 w-4" /> Add Location
              </Button>
            ) : (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => setSidebarMode('locations')} 
                className="text-xs text-primary font-medium hover:bg-primary/5 min-h-[36px] px-3 border border-primary/20 rounded-lg"
              >
                ← Back to Locations
              </Button>
            )}
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder={`Search ${sidebarMode}...`}
              className="pl-10 bg-background min-h-[40px] text-sm"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>
        <ScrollArea className="flex-1 bg-muted/5">
          <div className="p-4 pb-20 md:pb-4 flex flex-col gap-2">
            {sidebarMode === 'locations' && filteredLocations.map(location => (
              <button
                key={location.id}
                onClick={() => handleSelectLocation(location)}
                className={`flex items-center gap-3 rounded-xl px-4 py-3.5 text-left text-sm transition-all duration-200 hover:scale-[1.01] hover:shadow-md min-h-[60px] border ${
                  selectedLocation?.id === location.id 
                    ? "bg-gradient-to-r from-primary/10 via-primary/5 to-transparent text-foreground border-primary" 
                    : "bg-card text-muted-foreground hover:bg-muted/50 border-transparent hover:border-border/60"
                }`}
              >
                <MapPin className="h-4 w-4 shrink-0 text-primary" />
                <div className="flex flex-col overflow-hidden">
                  <span className="truncate font-semibold text-foreground">{location.name}</span>
                  {location.address && <span className="truncate text-xs opacity-75 mt-0.5">{location.address}</span>}
                </div>
              </button>
            ))}

            {sidebarMode === 'providers' && filteredProviders.map(provider => (
              <button
                key={provider.id}
                onClick={() => setSelectedProviderId(provider.id)}
                className={`flex items-center gap-3 rounded-xl px-4 py-3.5 text-left text-sm transition-all duration-200 hover:scale-[1.01] hover:shadow-md min-h-[60px] border ${
                  selectedProviderId === provider.id 
                    ? "bg-gradient-to-r from-primary/10 via-primary/5 to-transparent text-foreground border-primary" 
                    : "bg-card text-muted-foreground hover:bg-muted/50 border-transparent hover:border-border/60"
                }`}
              >
                <Avatar className="h-8 w-8 shrink-0 border" style={{ backgroundColor: provider.color || '#e2e8f0' }}>
                  <AvatarImage src={provider.avatar || provider.image} alt={provider.name} className="object-cover" />
                  <AvatarFallback className="text-xs font-bold text-white bg-primary/20">
                    {provider.name ? provider.name[0].toUpperCase() : 'P'}
                  </AvatarFallback>
                </Avatar>
                <div className="flex flex-col overflow-hidden">
                  <span className="truncate font-semibold text-foreground">{provider.name}</span>
                  {provider.email && <span className="truncate text-xs opacity-75 mt-0.5">{provider.email}</span>}
                </div>
              </button>
            ))}

            {sidebarMode === 'services' && filteredServices.map(service => (
              <button
                key={service.id}
                onClick={() => setSelectedServiceId(String(service.id))}
                className={`flex items-center gap-3 rounded-xl px-4 py-3.5 text-left text-sm transition-all duration-200 hover:scale-[1.01] hover:shadow-md min-h-[60px] border ${
                  selectedServiceId === String(service.id) 
                    ? "bg-gradient-to-r from-primary/10 via-primary/5 to-transparent text-foreground border-primary" 
                    : "bg-card text-muted-foreground hover:bg-muted/50 border-transparent hover:border-border/60"
                }`}
              >
                <Box className="h-4 w-4 shrink-0 text-primary" />
                <div className="flex flex-col overflow-hidden">
                  <span className="truncate font-semibold text-foreground">{service.name}</span>
                  {service.price && <span className="truncate text-xs opacity-75 mt-0.5">${service.price}</span>}
                </div>
              </button>
            ))}

            {((sidebarMode === 'locations' && filteredLocations.length === 0) ||
              (sidebarMode === 'providers' && filteredProviders.length === 0) ||
              (sidebarMode === 'services' && filteredServices.length === 0)) && (
              <div className="p-8 text-center text-sm text-muted-foreground">
                No {sidebarMode} found.
              </div>
            )}
          </div>
        </ScrollArea>
      </div>

      {/* RIGHT PANE: Detail / Edit */}
      <div className={`flex flex-col bg-background md:w-[65%] transition-all duration-300 h-full ${selectedLocation || isEditing ? 'flex w-full absolute inset-0 z-50 md:relative md:z-auto' : 'hidden md:flex'}`}>
        {selectedLocation || isEditing ? (
          <>
            <div className="flex items-center justify-between border-b px-4 md:px-6 py-4 sticky top-0 bg-background z-10 min-h-[65px]">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={() => { setSelectedLocation(null); setIsEditing(false); }}>
                  <ArrowLeft className="w-5 h-5" />
                </Button>
                <div>
                  <h3 className="text-xl font-semibold font-heading">
                    {isEditing && !selectedLocation ? "New Location" : formData.name || "Unnamed Location"}
                  </h3>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {selectedLocation ? (
                  <>
                    <AutoSaveStatus state={saveState} onRetry={retry} />
                    <Button variant="destructive" size="sm" onClick={handleDelete} disabled={isDeleting} className="min-h-[40px] rounded-md px-4 ml-2">
                      {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4 mr-1" />}
                      Delete
                    </Button>
                  </>
                ) : (
                  <>
                    <Button variant="ghost" size="sm" onClick={() => {
                      setSelectedLocation(null);
                      setIsEditing(false); // Cancel create
                    }} className="min-h-[40px] rounded-md px-4">
                      Cancel
                    </Button>
                    <Button size="sm" onClick={handleSave} disabled={isSaving} className="min-h-[40px] rounded-full px-6 bg-primary text-primary-foreground hover:bg-primary/90">
                      {isSaving ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Save className="mr-1 h-4 w-4" />}
                      Save & Close
                    </Button>
                  </>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6 scroll-smooth" id="details-scroll-container">
              <div className="max-w-3xl mx-auto">
                <Accordion type="single" collapsible defaultValue="details" className="space-y-2" onValueChange={handleAccordionChange}>
                  
                  {/* Accordion 1: Location Details */}
                  <AccordionItem value="details" id="item-details" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="text-base font-semibold py-4 hover:no-underline font-heading">
                      Location Details & Live Map
                    </AccordionTrigger>
                    <AccordionContent className="pt-2 pb-6 space-y-6">
                      <div className="grid gap-2">
                        <Label htmlFor="name" className="text-sm font-medium">Location Name *</Label>
                        <Input 
                          id="name" 
                          value={formData.name || ""} 
                          onChange={(e) => {
                            const updated = { ...formData, name: e.target.value };
                            setFormData(updated);
                            if (selectedLocation && e.target.value.trim() !== "") {
                              triggerSave(updated);
                            }
                          }}
                          disabled={!isEditing}
                          placeholder="e.g. Downtown Wellness Clinic"
                          className="min-h-[40px]"
                        />
                      </div>

                      <div className="grid gap-2">
                        <Label htmlFor="address" className="text-sm font-medium">Location Address</Label>
                        <div className="relative">
                          <MapPin className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                          <Input 
                            id="address" 
                            value={formData.address || ""} 
                            onChange={(e) => {
                              const updated = { ...formData, address: e.target.value };
                              setFormData(updated);
                              if (selectedLocation) {
                                triggerSave(updated);
                              }
                            }}
                            disabled={!isEditing}
                            placeholder="e.g. 73 Market Street, Sydney NSW 2000, Australia"
                            className="pl-10 min-h-[40px]"
                          />
                        </div>
                      </div>

                      <div className="grid gap-2">
                        <Label htmlFor="phone" className="text-sm font-medium">Location Phone Number</Label>
                        <div className="flex">
                          <Button variant="outline" disabled className="rounded-r-none border-r-0 px-3 bg-muted/30 text-muted-foreground min-h-[40px]">
                            <span className="mr-2">🇦🇺</span> +61
                          </Button>
                          <Input 
                            id="phone" 
                            value={formData.phone || ""} 
                            onChange={(e) => {
                              const updated = { ...formData, phone: e.target.value };
                              setFormData(updated);
                              if (selectedLocation) {
                                triggerSave(updated);
                              }
                            }}
                            disabled={!isEditing}
                            placeholder="e.g. 02 9876 5432"
                            className="rounded-l-none min-h-[40px]"
                          />
                        </div>
                      </div>

                      <div className="grid gap-2">
                        <Label htmlFor="contact_person" className="text-sm font-medium">Location Contact Person / Manager</Label>
                        <div className="relative">
                          <User className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                          <Input 
                            id="contact_person" 
                            value={formData.contact_person || ""} 
                            onChange={(e) => {
                              const updated = { ...formData, contact_person: e.target.value };
                              setFormData(updated);
                              if (selectedLocation) {
                                triggerSave(updated);
                              }
                            }}
                            disabled={!isEditing}
                            placeholder="e.g. Sarah Jenkins (Location Director)"
                            className="pl-10 min-h-[40px]"
                          />
                        </div>
                      </div>

                      <div className="grid gap-2">
                        <Label htmlFor="timezone" className="text-sm font-medium">Timezone</Label>
                        <Select
                          disabled={!isEditing}
                          value={formData.timezone || "Australia/Melbourne"}
                          onValueChange={(val) => {
                            const updated = { ...formData, timezone: val };
                            setFormData(updated);
                            if (selectedLocation) {
                              triggerSave(updated, true);
                            }
                          }}
                        >
                          <SelectTrigger id="timezone" className="min-h-[40px]">
                            <SelectValue placeholder="Select a timezone" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Australia/Sydney">Australia/Sydney</SelectItem>
                            <SelectItem value="Australia/Melbourne">Australia/Melbourne</SelectItem>
                            <SelectItem value="Australia/Brisbane">Australia/Brisbane</SelectItem>
                            <SelectItem value="Australia/Perth">Australia/Perth</SelectItem>
                            <SelectItem value="UTC">UTC</SelectItem>
                            <SelectItem value="America/New_York">America/New_York</SelectItem>
                            <SelectItem value="Europe/London">Europe/London</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="grid gap-2 pt-4 border-t">
                        <Label className="text-sm font-medium">Location Image</Label>
                        <input
                          type="file"
                          ref={fileInputRef}
                          accept="image/*"
                          className="hidden"
                          onChange={handleImageUpload}
                        />
                        <div 
                          className={`mt-1 border border-dashed rounded-xl p-6 flex flex-col items-center justify-center bg-muted/5 h-[180px] relative transition-colors ${isEditing ? 'cursor-pointer hover:bg-muted/15' : ''}`}
                          onClick={() => isEditing && fileInputRef.current?.click()}
                        >
                           {formData.image && formData.image.trim() !== "" && (
                             <div className="absolute top-3 right-3" onClick={(e) => e.stopPropagation()}>
                               {isEditing && (
                                 <Button 
                                   variant="destructive" 
                                   size="icon" 
                                   className="h-7 w-7 rounded-full shadow-md z-10"
                                   onClick={() => {
                                     const updated = { ...formData, image: "" };
                                     setFormData(updated);
                                     toast.success("Location image removed");
                                     if (selectedLocation) {
                                       triggerSave(updated, true);
                                     }
                                   }}
                                 >
                                   <X className="h-4 w-4" />
                                 </Button>
                                )}
                             </div>
                           )}
                           <div className="flex flex-col items-center gap-3">
                             {formData.image ? (
                               <img src={formData.image} alt={formData.name} className="w-24 h-24 object-cover rounded-lg shadow-md border" />
                             ) : (
                               <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                                 <Upload className="w-6 h-6" />
                               </div>
                             )}
                             <div className="text-center">
                               <p className="text-sm font-medium">
                                 {formData.image ? "Click to change location image" : "Click to upload location image"}
                               </p>
                               <p className="text-xs text-muted-foreground mt-0.5">Supports JPG, PNG, WEBP</p>
                             </div>
                           </div>
                        </div>
                      </div>

                      <div className="grid gap-2 pt-4 border-t">
                        <Label className="text-sm font-medium flex items-center gap-2">
                          <Globe className="h-4 w-4 text-primary animate-pulse" /> Live Google Map (Derived from Address)
                        </Label>
                        <div className="w-full h-[260px] rounded-xl overflow-hidden border bg-muted/20 relative shadow-inner">
                          <iframe
                            title="Google Maps Location Preview"
                            width="100%"
                            height="100%"
                            frameBorder="0"
                            scrolling="no"
                            marginHeight={0}
                            marginWidth={0}
                            src={`https://maps.google.com/maps?q=${encodeURIComponent(formData.address || 'Sydney, Australia')}&t=&z=14&ie=UTF8&iwloc=&output=embed`}
                            className="w-full h-full border-0"
                          />
                        </div>
                        <p className="text-xs text-muted-foreground">Map updates automatically as you type the location address.</p>
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* Accordion 2: Location Resources */}
                  <AccordionItem value="location_resources" id="item-location_resources" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="text-base font-semibold py-4 hover:no-underline font-heading">
                      Location Resources
                    </AccordionTrigger>
                    <AccordionContent className="pt-2 pb-6">
                      <Accordion type="multiple" className="w-full space-y-2">
                        {Object.keys(resourcesByType).map(type => {
                          const typeResources = resourcesByType[type];
                          return (
                            <AccordionItem key={type} value={type} className="border rounded-md px-3 bg-muted/5">
                              <AccordionTrigger className="text-sm font-semibold py-3 hover:no-underline font-heading">
                                <div className="flex items-center gap-2">
                                  <Box className="h-4 w-4 text-primary shrink-0" />
                                  <span>{type}</span>
                                  <span className="text-xs text-muted-foreground font-normal">
                                    ({typeResources.length} {typeResources.length === 1 ? 'resource' : 'resources'})
                                  </span>
                                </div>
                              </AccordionTrigger>
                              <AccordionContent className="pt-1 pb-3 divide-y divide-border/30">
                                {typeResources.map(resource => (
                                  <div key={resource.id} className="flex items-center justify-between py-2 hover:bg-muted/10 transition-colors">
                                    <Label htmlFor={`loc-resource-${resource.id}`} className="cursor-pointer text-sm font-medium flex-1 pl-1">
                                      {resource.name}
                                    </Label>
                                    <Checkbox 
                                      id={`loc-resource-${resource.id}`} 
                                      disabled={!isEditing}
                                      checked={resourceLocationIds.includes(String(resource.id))}
                                      onCheckedChange={(checked) => handleResourceCheckboxChange(String(resource.id), checked as boolean)}
                                      className="h-4 w-4 rounded"
                                    />
                                  </div>
                                ))}
                              </AccordionContent>
                            </AccordionItem>
                          );
                        })}
                        {resources.length === 0 && (
                          <p className="text-sm text-muted-foreground italic p-4">No resources found.</p>
                        )}
                      </Accordion>
                    </AccordionContent>
                  </AccordionItem>

                  {/* Accordion 3: Location Providers */}
                  <AccordionItem value="providers" id="item-providers" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="text-base font-semibold py-4 hover:no-underline font-heading">
                      Location Providers
                    </AccordionTrigger>
                    <AccordionContent className="pt-2 pb-6">
                      <div className="border rounded-lg overflow-hidden divide-y divide-border/40">
                        {providers.length > 0 ? providers.map(provider => (
                          <div key={provider.id} className="flex items-center justify-between p-3.5 hover:bg-muted/10 transition-colors">
                            <Label htmlFor={`provider-${provider.id}`} className="flex items-center gap-3 cursor-pointer font-medium flex-1">
                              <Avatar className="h-8 w-8 shrink-0 border" style={{ backgroundColor: provider.color || '#e2e8f0' }}>
                                <AvatarImage src={provider.avatar || provider.image} alt={provider.name} className="object-cover" />
                                <AvatarFallback className="text-xs font-bold text-white bg-primary/20">
                                  {provider.name ? provider.name[0].toUpperCase() : 'P'}
                                </AvatarFallback>
                              </Avatar>
                              <span className="text-sm">{provider.name}</span>
                            </Label>
                            <Checkbox 
                              id={`provider-${provider.id}`} 
                              disabled={!isEditing}
                              checked={(formData.provider_ids || []).includes(String(provider.id))}
                              onCheckedChange={(checked) => handleCheckboxChange('provider_ids', provider.id, checked as boolean)}
                              className="h-5 w-5 rounded-md"
                            />
                          </div>
                        )) : (
                          <p className="text-sm text-muted-foreground italic p-4">No providers found.</p>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* Accordion 3: Provider Scheduling */}
                  <AccordionItem value="scheduling" id="item-scheduling" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="text-base font-semibold py-4 hover:no-underline font-heading">
                      Provider Scheduling
                    </AccordionTrigger>
                    <AccordionContent className="pt-2 pb-6 space-y-6">
                      {activeProvider ? (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between border-b pb-2">
                            <div className="flex items-center gap-2">
                              <Avatar className="h-7 w-7 border" style={{ backgroundColor: activeProvider.color || '#e2e8f0' }}>
                                <AvatarFallback className="text-xs font-bold text-white bg-primary/20">
                                  {activeProvider.name[0].toUpperCase()}
                                </AvatarFallback>
                              </Avatar>
                              <span className="font-semibold text-sm">Working Hours: {activeProvider.name}</span>
                            </div>
                            <Button 
                              size="xs" 
                              onClick={() => handleSaveProviderSchedule(activeProvider.id, activeProvider.weekly_schedule || createDefaultWeeklySchedule())} 
                              disabled={isUpdatingRelation}
                              className="text-xs min-h-[30px]"
                            >
                              {isUpdatingRelation ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Save className="h-3 w-3 mr-1" />}
                              Save Hours
                            </Button>
                          </div>
                          
                          <div className="space-y-3">
                            {DAYS_OF_WEEK.map((day) => {
                              const sched = (activeProvider.weekly_schedule || {})[day.key] || { is_working: false, start_time: "09:00", end_time: "17:00" };
                              return (
                                <div key={day.key} className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-3 border rounded-lg bg-muted/5 gap-3">
                                  <div className="flex items-center gap-3">
                                    <Switch 
                                      id={`schedule-day-${day.key}`}
                                      checked={sched.is_working}
                                      onCheckedChange={(checked) => updateProviderWorkDay(day.key, checked, sched.start_time, sched.end_time)}
                                    />
                                    <Label htmlFor={`schedule-day-${day.key}`} className="font-semibold text-sm min-w-[80px]">{day.label}</Label>
                                  </div>
                                  
                                  {sched.is_working ? (
                                    <div className="flex items-center gap-2">
                                      <Clock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                                      <Select
                                        value={sched.start_time || "09:00"}
                                        onValueChange={(val) => updateProviderWorkDay(day.key, true, val, sched.end_time)}
                                      >
                                        <SelectTrigger className="w-[95px] h-[34px] text-xs">
                                          <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                          {TIME_OPTIONS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                                        </SelectContent>
                                      </Select>
                                      <span className="text-xs text-muted-foreground">to</span>
                                      <Select
                                        value={sched.end_time || "17:00"}
                                        onValueChange={(val) => updateProviderWorkDay(day.key, true, sched.start_time, val)}
                                      >
                                        <SelectTrigger className="w-[95px] h-[34px] text-xs">
                                          <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                          {TIME_OPTIONS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                                        </SelectContent>
                                      </Select>
                                    </div>
                                  ) : (
                                    <span className="text-xs font-semibold text-red-500 pr-4">Closed (Not Working)</span>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ) : (
                        <div className="p-6 text-center border border-dashed rounded-lg">
                          <p className="text-sm text-muted-foreground">Please select a provider from the left sidebar to edit their working schedule.</p>
                        </div>
                      )}
                    </AccordionContent>
                  </AccordionItem>

                  {/* Accordion 4: Provider Services */}
                  <AccordionItem value="services" id="item-services" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="text-base font-semibold py-4 hover:no-underline font-heading">
                      Provider Services
                    </AccordionTrigger>
                    <AccordionContent className="pt-2 pb-6">
                      <div className="border rounded-lg overflow-hidden divide-y divide-border/40">
                        {services.length > 0 ? services.map(service => (
                          <div key={service.id} className="flex items-center justify-between p-3.5 hover:bg-muted/10 transition-colors">
                            <Label htmlFor={`service-${service.id}`} className="flex items-center gap-3 cursor-pointer font-medium flex-1">
                              <Box className="h-4 w-4 text-muted-foreground shrink-0" />
                              <span className="text-sm">{service.name}</span>
                            </Label>
                            <Checkbox 
                              id={`service-${service.id}`} 
                              disabled={!isEditing}
                              checked={(formData.service_ids || []).includes(String(service.id))}
                              onCheckedChange={(checked) => handleCheckboxChange('service_ids', service.id, checked as boolean)}
                              className="h-5 w-5 rounded-md"
                            />
                          </div>
                        )) : (
                          <p className="text-sm text-muted-foreground italic p-4">No services found.</p>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* Accordion 5: Service Categories */}
                  <AccordionItem value="categories" id="item-categories" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="text-base font-semibold py-4 hover:no-underline font-heading">
                      Service Categories
                    </AccordionTrigger>
                    <AccordionContent className="pt-2 pb-6">
                      <div className="border rounded-lg overflow-hidden divide-y divide-border/40">
                        {categories.length > 0 ? categories.map(category => (
                          <div key={category.id} className="flex items-center justify-between p-3.5 hover:bg-muted/10 transition-colors">
                            <Label htmlFor={`category-${category.id}`} className="flex items-center gap-3 cursor-pointer font-medium flex-1">
                              <Layers className="h-4 w-4 text-muted-foreground shrink-0" />
                              <span className="text-sm">{category.name}</span>
                            </Label>
                            <Checkbox 
                              id={`category-${category.id}`} 
                              disabled={!isEditing}
                              checked={(formData.category_ids || []).includes(String(category.id))}
                              onCheckedChange={(checked) => handleCheckboxChange('category_ids', category.id, checked as boolean)}
                              className="h-5 w-5 rounded-md"
                            />
                          </div>
                        )) : (
                          <p className="text-sm text-muted-foreground italic p-4">No categories found.</p>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* Accordion 6: Service Add-ons */}
                  <AccordionItem value="addons" id="item-addons" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="text-base font-semibold py-4 hover:no-underline font-heading">
                      Service Add-ons
                    </AccordionTrigger>
                    <AccordionContent className="pt-2 pb-6 space-y-4">
                      {activeService ? (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between border-b pb-2">
                            <span className="font-semibold text-sm">Add-ons for: {activeService.name}</span>
                            <Button 
                              size="xs" 
                              onClick={() => handleSaveServiceAddOns(activeService.id, activeService.addon_ids || [])} 
                              disabled={isUpdatingRelation}
                              className="text-xs min-h-[30px]"
                            >
                              {isUpdatingRelation ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Save className="h-3 w-3 mr-1" />}
                              Update Add-ons
                            </Button>
                          </div>
                          
                          <div className="border rounded-lg overflow-hidden divide-y divide-border/40">
                            {addOns.length > 0 ? addOns.map(addon => (
                              <div key={addon.id} className="flex items-center justify-between p-3.5 hover:bg-muted/10 transition-colors">
                                <Label htmlFor={`addons-rel-${addon.id}`} className="flex items-center gap-3 cursor-pointer font-medium flex-1">
                                  <Sparkles className="h-4 w-4 text-muted-foreground shrink-0" />
                                  <span className="text-sm">{addon.name}</span>
                                </Label>
                                <Checkbox 
                                  id={`addons-rel-${addon.id}`} 
                                  checked={(activeService.addon_ids || []).includes(Number(addon.id))}
                                  onCheckedChange={(checked) => {
                                    const currentAddons = activeService.addon_ids || [];
                                    const updated = checked 
                                      ? [...currentAddons, Number(addon.id)] 
                                      : currentAddons.filter((id: number) => id !== Number(addon.id));
                                    setServices(services.map(s => String(s.id) === String(activeService.id) ? { ...s, addon_ids: updated } : s));
                                  }}
                                  className="h-5 w-5 rounded-md"
                                />
                              </div>
                            )) : (
                              <p className="text-sm text-muted-foreground italic p-4">No add-ons found.</p>
                            )}
                          </div>
                        </div>
                      ) : (
                        <div className="p-6 text-center border border-dashed rounded-lg">
                          <p className="text-sm text-muted-foreground">Please select a service from the left sidebar to edit its service add-ons.</p>
                        </div>
                      )}
                    </AccordionContent>
                  </AccordionItem>

                  {/* Accordion 7: Service Resources */}
                  <AccordionItem value="resources" id="item-resources" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="text-base font-semibold py-4 hover:no-underline font-heading">
                      Service Resources
                    </AccordionTrigger>
                    <AccordionContent className="pt-2 pb-6 space-y-4">
                      {activeService ? (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between border-b pb-2">
                            <span className="font-semibold text-sm">Resource Requirements: {activeService.name}</span>
                            <Button 
                              size="xs" 
                              onClick={() => handleSaveServiceResources(activeService.id, activeService.requirements || [])} 
                              disabled={isUpdatingRelation}
                              className="text-xs min-h-[30px]"
                            >
                              {isUpdatingRelation ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Save className="h-3 w-3 mr-1" />}
                              Update Requirements
                            </Button>
                          </div>
                          
                          <div className="border rounded-lg overflow-hidden divide-y divide-border/40">
                            {Array.from(new Set(resources.map(r => r.type))).map(type => {
                              const requirement = (activeService.requirements || []).find((req: any) => req.resource_type === type);
                              const isChecked = !!requirement;
                              const quantity = requirement ? requirement.quantity : 1;
                              
                              return (
                                <div key={type} className="flex items-center justify-between p-3.5 hover:bg-muted/10 transition-colors gap-4">
                                  <div className="flex items-center gap-3 flex-1">
                                    <Checkbox 
                                      id={`resource-req-${type}`}
                                      checked={isChecked}
                                      onCheckedChange={(checked) => {
                                        const currentReqs = activeService.requirements || [];
                                        const updated = checked 
                                          ? [...currentReqs, { resource_type: type, quantity: 1 }]
                                          : currentReqs.filter((req: any) => req.resource_type !== type);
                                        setServices(services.map(s => String(s.id) === String(activeService.id) ? { ...s, requirements: updated } : s));
                                      }}
                                      className="h-5 w-5 rounded-md"
                                    />
                                    <Label htmlFor={`resource-req-${type}`} className="text-sm font-semibold cursor-pointer">{type}</Label>
                                  </div>
                                  
                                  {isChecked && (
                                    <div className="flex items-center gap-2">
                                      <span className="text-xs text-muted-foreground">Qty:</span>
                                      <Input 
                                        type="number"
                                        min="1"
                                        value={quantity}
                                        onChange={(e) => {
                                          const val = parseInt(e.target.value) || 1;
                                          const currentReqs = activeService.requirements || [];
                                          const updated = currentReqs.map((req: any) => req.resource_type === type ? { ...req, quantity: val } : req);
                                          setServices(services.map(s => String(s.id) === String(activeService.id) ? { ...s, requirements: updated } : s));
                                        }}
                                        className="w-[60px] h-[30px] text-center text-xs p-1"
                                      />
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                            {resources.length === 0 && (
                              <p className="text-sm text-muted-foreground italic p-4">No resource groups configured in system.</p>
                            )}
                          </div>
                        </div>
                      ) : (
                        <div className="p-6 text-center border border-dashed rounded-lg">
                          <p className="text-sm text-muted-foreground">Please select a service from the left sidebar to edit its resource requirements.</p>
                        </div>
                      )}
                    </AccordionContent>
                  </AccordionItem>

                  {/* Accordion 8: Service Products */}
                  <AccordionItem value="products" id="item-products" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="text-base font-semibold py-4 hover:no-underline font-heading">
                      Service Products
                    </AccordionTrigger>
                    <AccordionContent className="pt-2 pb-6 space-y-4">
                      {activeService ? (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between border-b pb-2">
                            <span className="font-semibold text-sm">Products for: {activeService.name}</span>
                            <Button 
                              size="xs" 
                              onClick={() => handleSaveServiceProducts(activeService.id, activeService.product_ids || [])} 
                              disabled={isUpdatingRelation}
                              className="text-xs min-h-[30px]"
                            >
                              {isUpdatingRelation ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Save className="h-3 w-3 mr-1" />}
                              Update Products
                            </Button>
                          </div>
                          
                          <div className="border rounded-lg overflow-hidden divide-y divide-border/40">
                            {products.length > 0 ? products.map(prod => (
                              <div key={prod.id} className="flex items-center justify-between p-3.5 hover:bg-muted/10 transition-colors">
                                <Label htmlFor={`products-rel-${prod.id}`} className="flex items-center gap-3 cursor-pointer font-medium flex-1">
                                  <ShoppingBag className="h-4 w-4 text-muted-foreground shrink-0" />
                                  <span className="text-sm">{prod.name}</span>
                                </Label>
                                <Checkbox 
                                  id={`products-rel-${prod.id}`} 
                                  checked={(activeService.product_ids || []).includes(Number(prod.id))}
                                  onCheckedChange={(checked) => {
                                    const currentProds = activeService.product_ids || [];
                                    const updated = checked 
                                      ? [...currentProds, Number(prod.id)] 
                                      : currentProds.filter((id: number) => id !== Number(prod.id));
                                    setServices(services.map(s => String(s.id) === String(activeService.id) ? { ...s, product_ids: updated } : s));
                                  }}
                                  className="h-5 w-5 rounded-md"
                                />
                              </div>
                            )) : (
                              <p className="text-sm text-muted-foreground italic p-4">No products found.</p>
                            )}
                          </div>
                        </div>
                      ) : (
                        <div className="p-6 text-center border border-dashed rounded-lg">
                          <p className="text-sm text-muted-foreground">Please select a service from the left sidebar to edit its service products.</p>
                        </div>
                      )}
                    </AccordionContent>
                  </AccordionItem>

                  {/* Accordion 9: Service Packages */}
                  <AccordionItem value="packages" id="item-packages" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="text-base font-semibold py-4 hover:no-underline font-heading">
                      Service Packages
                    </AccordionTrigger>
                    <AccordionContent className="pt-2 pb-6">
                      <div className="border rounded-lg overflow-hidden divide-y divide-border/40">
                        {packages.length > 0 ? packages.map(pkg => (
                          <div key={pkg.id} className="flex items-center justify-between p-3.5 hover:bg-muted/10 transition-colors">
                            <Label htmlFor={`package-${pkg.id}`} className="flex items-center gap-3 cursor-pointer font-medium flex-1">
                              <Gift className="h-4 w-4 text-muted-foreground shrink-0" />
                              <span className="text-sm">{pkg.name}</span>
                            </Label>
                            <Checkbox 
                              id={`package-${pkg.id}`} 
                              disabled={true} // Packages follow services implicitly 
                              checked={true}
                              className="h-5 w-5 rounded-md opacity-60"
                            />
                          </div>
                        )) : (
                          <p className="text-sm text-muted-foreground italic p-4">No packages found.</p>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                </Accordion>
              </div>
            </div>
            {isEditing && !selectedLocation && (
              <div className="md:hidden sticky bottom-0 bg-background z-10 p-4 border-t flex gap-2 justify-end">
                <Button variant="ghost" size="sm" className="min-h-[44px] flex-1" onClick={() => {
                  setSelectedLocation(null);
                  setIsEditing(false); // Cancel create
                }}>
                  Cancel
                </Button>
                <Button size="sm" className="min-h-[44px] flex-1" onClick={handleSave} disabled={isSaving}>
                  {isSaving ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Save className="mr-1 h-4 w-4" />}
                  Save
                </Button>
              </div>
            )}
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center text-center p-8">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-muted/50 mb-4">
              <MapPin className="h-10 w-10 text-muted-foreground/50" />
            </div>
            <h3 className="text-xl font-semibold tracking-tight">No Location Selected</h3>
            <p className="text-sm text-muted-foreground mt-2 max-w-sm">
              Select a location from the list on the left to view and edit its details, or click 'Add Location' to create a new one.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
