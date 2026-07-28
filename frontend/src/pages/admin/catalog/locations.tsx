import { useEffect, useState, useRef } from "react";
import { Plus, Search, MapPin, Loader2, Save, Trash2, ArrowLeft, Upload, X, User, Globe, Sparkles, Layers, Box, ShoppingBag, Gift, Clock } from "lucide-react";
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
  service_ids?: string[];
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
  
  // Left pane modes & listings
  const [leftPaneMode, setLeftPaneMode] = useState<'locations' | 'providers' | 'services'>('locations');
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
    let baseProviders = providers;
    let baseServices = services;

    if (selectedLocation) {
      // Filter providers: only those assigned to the selected location
      const locationProviderIds = formData.provider_ids || [];
      baseProviders = providers.filter(p => locationProviderIds.includes(String(p.id)));

      // Filter services: only those performable by the providers assigned to the selected location
      const activeLocationProviders = providers.filter(p => locationProviderIds.includes(String(p.id)));
      const locationServiceIds = Array.from(
        new Set(activeLocationProviders.flatMap(p => p.service_ids || []).map(String))
      );
      baseServices = services.filter(s => locationServiceIds.includes(String(s.id)));
    }

    if (searchQuery.trim() === "") {
      setFilteredLocations(locations);
      setFilteredProviders(baseProviders);
      setFilteredServices(baseServices);
    } else {
      const lowerQuery = searchQuery.toLowerCase();
      setFilteredLocations(
        locations.filter(loc => loc && loc.name && loc.name.toLowerCase().includes(lowerQuery))
      );
      setFilteredProviders(
        baseProviders.filter(prov => prov && prov.name && prov.name.toLowerCase().includes(lowerQuery))
      );
      setFilteredServices(
        baseServices.filter(svc => svc && svc.name && svc.name.toLowerCase().includes(lowerQuery))
      );
    }
  }, [searchQuery, locations, providers, services, leftPaneMode, selectedLocation, formData.provider_ids]);

  // Ensure valid selection within filtered scopes
  useEffect(() => {
    if (leftPaneMode === 'providers' && filteredProviders.length > 0) {
      if (!selectedProviderId || !filteredProviders.some(p => String(p.id) === String(selectedProviderId))) {
        setSelectedProviderId(filteredProviders[0].id);
      }
    }
  }, [filteredProviders, leftPaneMode, selectedProviderId]);

  useEffect(() => {
    if (leftPaneMode === 'services' && filteredServices.length > 0) {
      if (!selectedServiceId || !filteredServices.some(s => String(s.id) === String(selectedServiceId))) {
        setSelectedServiceId(String(filteredServices[0].id));
      }
    }
  }, [filteredServices, leftPaneMode, selectedServiceId]);


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
      // Dynamic Left Pane Mode Switching depending on Accordion Tab
      if (value === "scheduling" || value === "services") {
        setLeftPaneMode("providers");
        if (providers.length > 0 && !selectedProviderId) {
          setSelectedProviderId(providers[0].id);
        }
      } else if (["categories", "addons", "resources", "products", "packages"].includes(value)) {
        setLeftPaneMode("services");
        if (services.length > 0 && !selectedServiceId) {
          setSelectedServiceId(String(services[0].id));
        }
      } else {
        setLeftPaneMode("locations");
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
              {leftPaneMode === 'locations' ? 'Locations' : leftPaneMode === 'providers' ? 'Providers List' : 'Services List'}
            </h2>
            {leftPaneMode === 'locations' ? (
              <Button size="sm" onClick={handleCreateNew} className="min-h-[40px] px-4 rounded-full">
                <Plus className="mr-1 h-4 w-4" /> Add Location
              </Button>
            ) : (
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => setLeftPaneMode('locations')} 
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
              placeholder={`Search ${leftPaneMode}...`}
              className="pl-10 bg-background min-h-[40px] text-sm"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>
        <ScrollArea className="flex-1 bg-muted/5">
          <div className="p-4 pb-20 md:pb-4 flex flex-col gap-2">
            {leftPaneMode === 'locations' && filteredLocations.map(location => (
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

            {leftPaneMode === 'providers' && filteredProviders.map(provider => (
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

            {leftPaneMode === 'services' && filteredServices.map(service => (
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

            {((leftPaneMode === 'locations' && filteredLocations.length === 0) ||
              (leftPaneMode === 'providers' && filteredProviders.length === 0) ||
              (leftPaneMode === 'services' && filteredServices.length === 0)) && (
              <div className="p-8 text-center text-sm text-muted-foreground">
                No {leftPaneMode} found.
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
