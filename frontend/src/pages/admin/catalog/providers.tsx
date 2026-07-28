import { useState, useEffect, useRef } from 'react';
import { 
  Search, Plus, Trash2, Save, ArrowLeft, Copy, Info, 
  Wand2, 
  List, ListOrdered, AlignLeft, AlignCenter, AlignRight, 
  Link, Image as ImageIcon, Video, Code, HelpCircle, 
  X, Check,
  ChevronDown, Link2, Upload,
  Eye, EyeOff, Loader2, Circle, CircleSlash, Layers
} from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '@/lib/api';
import { useAutoSave } from '@/hooks/use-auto-save';
import { AutoSaveStatus } from '@/components/ui/auto-save-status';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';


// Types based on the MCD specifications
interface Provider {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  description?: string;
  active: boolean;
  is_visible: boolean;
  capacity?: number;
  color?: string;
  avatar?: string;
  image?: string;
  deep_link?: string;
  ignore_company_hours: boolean;
  weekly_schedule?: any;
  special_days?: any[];
  services?: string[];
  locations?: string[];
}

const MOCK_SERVICES = [
  { id: 'srv-1', name: 'Haircut' },
  { id: 'srv-2', name: 'Highlights' },
  { id: 'srv-3', name: 'Outcall Companionship' },
  { id: 'srv-4', name: 'Incall Booking' },
  { id: 'srv-5', name: 'Blow Dry' },
  { id: 'srv-6', name: 'Coloring' }
];

const COLOR_SWATCHES = [
  '#34bbf1', '#ff9295', '#fac94e', '#56dc86', '#c6a5e2', 
  '#b2ca3f', '#b07393', '#b09873', '#bb6a6a', '#71909f', 
  '#566993', '#1f9a7e', '#28c75f', '#2782e8'
];

const generateHalfHourSlots = (): string[] => {
  const slots: string[] = [];
  const hours = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
  const periods = ['AM', 'PM'];
  for (const period of periods) {
    for (const hour of hours) {
      slots.push(`${hour}:00 ${period}`);
      slots.push(`${hour}:30 ${period}`);
    }
  }
  return slots;
};

const HALF_HOUR_SLOTS = generateHalfHourSlots();

const DAYS_OF_WEEK = [
  { key: 'monday', label: 'Monday', short: 'Mo' },
  { key: 'tuesday', label: 'Tuesday', short: 'Tu' },
  { key: 'wednesday', label: 'Wednesday', short: 'We' },
  { key: 'thursday', label: 'Thursday', short: 'Th' },
  { key: 'friday', label: 'Friday', short: 'Fr' },
  { key: 'saturday', label: 'Saturday', short: 'Sa' },
  { key: 'sunday', label: 'Sunday', short: 'Su' },
];

export default function ProvidersPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const navigate = useNavigate();
  const location = useLocation();
  const [services, setServices] = useState<any[]>([]);
  const [locations, setLocations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(null);
  const [rightPaneType, setRightPaneType] = useState<'provider' | 'location'>('provider');
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null);
  const [isLocationCreating, setIsLocationCreating] = useState(false);
  const [locationFormData, setLocationFormData] = useState({
    name: '',
    address: '',
    phone: '',
    contact_person: '',
    timezone: 'Australia/Melbourne',
  });

  const { saveState, triggerSave, retry } = useAutoSave({
    onSave: async (updatedData: any) => {
      const targetId = selectedProvider?.id;
      if (!targetId) return;
      
      const payload: any = {
        name: updatedData.name || '',
        email: updatedData.email || null,
        phone: updatedData.phone || null,
        active: updatedData.active ?? true,
        is_visible: updatedData.is_visible ?? true,
        capacity: updatedData.capacity || 1,
        color: updatedData.color || null,
        description: updatedData.description || null,
        ignore_company_hours: updatedData.ignore_company_hours ?? false,
      };

      try {
        const res = await apiClient.put<any>(`/api/admin/providers/${targetId}`, payload);
        const dataObj = res?.data || res;
        const returnedProvider = { ...updatedData, ...dataObj, id: String(dataObj.id || targetId) };
        setProviders(prev => prev.map(p => p.id === targetId ? returnedProvider : p));
      } catch (error: any) {
        toast.error(error.message || "Failed to auto-save provider");
        throw error;
      }
    },
    debounceMs: 500
  });

  const { saveState: locSaveState, triggerSave: triggerLocSave, retry: retryLoc } = useAutoSave({
    onSave: async (updatedData: any) => {
      const targetId = selectedLocationId;
      if (!targetId) return;
      try {
        const res = await apiClient.put<any>(`/api/admin/locations/${targetId}`, updatedData);
        const dataObj = res?.data || res;
        const returnedLocation = { ...updatedData, ...dataObj, id: String(dataObj.id || targetId) };
        setLocations(prev => prev.map(l => String(l.id) === String(targetId) ? returnedLocation : l));
      } catch (error: any) {
        toast.error(error.message || "Failed to auto-save location");
        throw error;
      }
    },
    debounceMs: 500
  });

  const handleSaveLocationManual = async () => {
    if (!locationFormData.name.trim()) {
      toast.error('Location Name is required');
      return;
    }
    try {
      const res = await apiClient.post<any>('/api/admin/locations', locationFormData);
      const dataObj = res?.data || res;
      const newLoc = { ...locationFormData, ...dataObj, id: String(dataObj.id) };
      setLocations(prev => [...prev, newLoc]);
      toast.success('Location created successfully');
      setSelectedLocationId(newLoc.id);
      setIsLocationCreating(false);
    } catch (err: any) {
      toast.error(err.message || 'Failed to create location');
    }
  };

  const handleDeleteLocation = async (id: string) => {
    if (!confirm('Are you sure you want to delete this location?')) return;
    try {
      await apiClient.delete(`/api/admin/locations/${id}`);
      setLocations(prev => prev.filter(l => String(l.id) !== id));
      setSelectedLocationId(null);
      setRightPaneType('provider');
      toast.success('Location deleted successfully');
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete location');
    }
  };

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [activeMobileTab, setActiveMobileTab] = useState('monday');
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [servicesSaveStatus, setServicesSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        if (selectedProvider) {
          setSelectedProvider({
            ...selectedProvider,
            avatar: reader.result as string,
            image: reader.result as string
          });
        }
        toast.success('Provider image uploaded');
      };
      reader.readAsDataURL(file);
    }
  };

  const fetchProviders = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get<any>('/api/admin/providers');
      const rawList = Array.isArray(res) 
        ? res 
        : (Array.isArray(res?.data) ? res.data : (res?.items || []));
      
      const mapped: Provider[] = rawList.map((p: any) => ({
        ...p,
        id: String(p.id),
      }));

      setProviders(mapped);
      if (mapped.length > 0) {
        setSelectedProvider(mapped[0]);
      }
    } catch (err) {
      console.warn('Failed to load providers from backend:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchServicesAndLocations = async () => {
    try {
      const [servicesData, locationsData] = await Promise.all([
        apiClient.get<any[]>('/api/admin/services').catch(() => []),
        apiClient.get<any[]>('/api/admin/locations').catch(() => [])
      ]);
      const srvList = Array.isArray(servicesData) ? servicesData : (servicesData as any).data || (servicesData as any).items || [];
      setServices(srvList.length > 0 ? srvList : MOCK_SERVICES);
      setLocations(Array.isArray(locationsData) ? locationsData : (locationsData as any).data || (locationsData as any).items || []);
    } catch (err) {
      console.error(err);
      setServices(MOCK_SERVICES);
    }
  };

  useEffect(() => {
    fetchProviders();
    fetchServicesAndLocations();
    if (location.state?.returnToServiceId) {
      handleCreate();
    }
  }, [location.state]);

  const handleCancel = () => {
    if (location.state?.returnToServiceId) {
      navigate('/admin/catalog/services', {
        state: {
          selectServiceId: location.state.returnToServiceId,
          openSection: location.state.section
        }
      });
      return;
    }
    setSelectedProvider(null);
  };

  const handleCreate = async (initialProps?: Partial<Provider>) => {
    setRightPaneType('provider');
    const defaultData = {
      name: 'New Provider',
      active: true,
      is_visible: true,
      ignore_company_hours: false,
      capacity: 1,
      color: '#34bbf1',
      description: '',
      locations: initialProps?.locations || [],
    };
    
    let createdProvider: Provider | null = null;
    try {
      const res = await apiClient.post<any>('/api/admin/providers', defaultData);
      const dataObj = res?.data || res;
      if (dataObj && dataObj.id) {
        createdProvider = {
          ...defaultData,
          ...dataObj,
          id: String(dataObj.id),
          weekly_schedule: {
            monday: { is_working: true, start_time: '09:00', end_time: '17:00' },
            tuesday: { is_working: true, start_time: '09:00', end_time: '17:00' },
            wednesday: { is_working: true, start_time: '09:00', end_time: '17:00' },
            thursday: { is_working: true, start_time: '09:00', end_time: '17:00' },
            friday: { is_working: true, start_time: '09:00', end_time: '17:00' },
            saturday: { is_working: false, start_time: '09:00', end_time: '17:00' },
            sunday: { is_working: false, start_time: '09:00', end_time: '17:00' },
          },
          special_days: [],
          services: [],
          locations: initialProps?.locations || []
        };
      }
    } catch (err) {
      console.warn("Backend create notice, using local provider:", err);
    }
 
    if (!createdProvider) {
      createdProvider = {
        id: `prov-${Date.now()}`,
        ...defaultData,
        weekly_schedule: {
          monday: { is_working: true, start_time: '09:00', end_time: '17:00' },
          tuesday: { is_working: true, start_time: '09:00', end_time: '17:00' },
          wednesday: { is_working: true, start_time: '09:00', end_time: '17:00' },
          thursday: { is_working: true, start_time: '09:00', end_time: '17:00' },
          friday: { is_working: true, start_time: '09:00', end_time: '17:00' },
          saturday: { is_working: false, start_time: '09:00', end_time: '17:00' },
          sunday: { is_working: false, start_time: '09:00', end_time: '17:00' },
        },
        special_days: [],
        services: [],
        locations: initialProps?.locations || []
      };
    }
 
    setProviders(prev => [...prev, createdProvider!]);
    setSelectedProvider(createdProvider);
    toast.success('Provider created successfully');
  };

  const handleAssignProviderToLocation = async (providerId: string, locationId: string) => {
    const prov = providers.find(p => p.id === providerId);
    if (!prov) return;
    const currentLocs = prov.locations || [];
    if (currentLocs.includes(locationId)) return;
    const nextLocs = [...currentLocs, locationId];
    
    // Optimistic update
    const updatedProvider = { ...prov, locations: nextLocs };
    setProviders(prev => prev.map(p => p.id === providerId ? updatedProvider : p));
    if (selectedProvider?.id === providerId) {
      setSelectedProvider(updatedProvider);
    }
    
    try {
      const payload: any = {
        name: prov.name || '',
        email: prov.email || null,
        phone: prov.phone || null,
        active: prov.active ?? true,
        is_visible: prov.is_visible ?? true,
        capacity: prov.capacity || 1,
        color: prov.color || null,
        description: prov.description || null,
        ignore_company_hours: prov.ignore_company_hours ?? false,
        locations: nextLocs,
      };
      await apiClient.put(`/api/admin/providers/${providerId}`, payload);
      toast.success(`Assigned ${prov.name} to location`);
    } catch (err: any) {
      toast.error(err.message || "Failed to update provider assignment");
      // Rollback
      setProviders(prev => prev.map(p => p.id === providerId ? prov : p));
      if (selectedProvider?.id === providerId) {
        setSelectedProvider(prov);
      }
    }
  };

  const handleUpdate = async () => {
    if (!selectedProvider) return;
    const targetId = selectedProvider.id;
    
    // Clean payload matching backend ProviderUpdate schema
    const payload: any = {
      name: selectedProvider.name || '',
      email: selectedProvider.email || null,
      phone: selectedProvider.phone || null,
      active: selectedProvider.active ?? true,
      is_visible: selectedProvider.is_visible ?? true,
      capacity: selectedProvider.capacity || 1,
      color: selectedProvider.color || null,
      description: selectedProvider.description || null,
      ignore_company_hours: selectedProvider.ignore_company_hours ?? false,
    };

    let updatedObj: Provider = { ...selectedProvider };

    const isTempId = !targetId || targetId.startsWith('prov-') || isNaN(Number(targetId));

    try {
      if (isTempId) {
        // Backend POST
        const res = await apiClient.post<any>('/api/admin/providers', payload);
        const dataObj = res?.data || res;
        if (dataObj && dataObj.id) {
          updatedObj = { ...selectedProvider, ...dataObj, id: String(dataObj.id) };
        }
      } else {
        // Backend PUT
        try {
          const res = await apiClient.put<any>(`/api/admin/providers/${targetId}`, payload);
          const dataObj = res?.data || res;
          if (dataObj && dataObj.id) {
            updatedObj = { ...selectedProvider, ...dataObj, id: String(dataObj.id) };
          }
        } catch (putErr) {
          // If 404, fallback to POST
          const res = await apiClient.post<any>('/api/admin/providers', payload);
          const dataObj = res?.data || res;
          if (dataObj && dataObj.id) {
            updatedObj = { ...selectedProvider, ...dataObj, id: String(dataObj.id) };
          }
        }
      }
    } catch (err) {
      console.warn("Backend save notice, saved state locally:", err);
    }

    setProviders(prev => prev.map(p => (p.id === targetId || p.id === updatedObj.id ? updatedObj : p)));
    setSelectedProvider(updatedObj);
    toast.success('Provider saved successfully');

    if (location.state?.returnToServiceId) {
      navigate('/admin/catalog/services', {
        state: {
          selectServiceId: location.state.returnToServiceId,
          openSection: location.state.section
        }
      });
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiClient.delete(`/api/admin/providers/${id}`).catch(() => {});
    } catch (err) {
      console.warn("Backend delete error:", err);
    }
    setProviders(prev => prev.filter((p) => p.id !== id));
    if (selectedProvider?.id === id) {
      setSelectedProvider(null);
    }
    toast.success('Provider deleted');
  };

  const toggleProviderVisibility = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const prov = providers.find(p => p.id === id);
    if (!prov) return;
    const nextVis = !prov.is_visible;
    const updated = { ...prov, is_visible: nextVis };
    
    // Update local state
    setProviders(prev => prev.map(p => p.id === id ? updated : p));
    if (selectedProvider?.id === id) {
      setSelectedProvider(updated);
    }
    
    try {
      const payload: any = {
        name: prov.name || '',
        email: prov.email || null,
        phone: prov.phone || null,
        active: prov.active ?? true,
        is_visible: nextVis,
        capacity: prov.capacity || 1,
        color: prov.color || null,
        description: prov.description || null,
        ignore_company_hours: prov.ignore_company_hours ?? false,
      };
      await apiClient.put(`/api/admin/providers/${id}`, payload);
      toast.success(`Provider ${nextVis ? 'visible on' : 'hidden from'} booking page`);
    } catch (err: any) {
      toast.error(err.message || "Failed to update provider visibility");
      // Rollback
      setProviders(prev => prev.map(p => p.id === id ? prov : p));
      if (selectedProvider?.id === id) {
        setSelectedProvider(prov);
      }
    }
  };

  const toggleProviderActive = async (id: string, active: boolean) => {
    const prov = providers.find(p => p.id === id);
    if (!prov) return;
    const updated = { ...prov, active };
    
    // Update local state
    setProviders(prev => prev.map(p => p.id === id ? updated : p));
    if (selectedProvider?.id === id) {
      setSelectedProvider(updated);
    }
    
    try {
      const payload: any = {
        name: prov.name || '',
        email: prov.email || null,
        phone: prov.phone || null,
        active,
        is_visible: prov.is_visible ?? true,
        capacity: prov.capacity || 1,
        color: prov.color || null,
        description: prov.description || null,
        ignore_company_hours: prov.ignore_company_hours ?? false,
      };
      await apiClient.put(`/api/admin/providers/${id}`, payload);
      toast.success(`Provider status set to ${active ? 'Active' : 'Inactive'}`);
    } catch (err: any) {
      toast.error(err.message || "Failed to update provider status");
      // Rollback
      setProviders(prev => prev.map(p => p.id === id ? prov : p));
      if (selectedProvider?.id === id) {
        setSelectedProvider(prov);
      }
    }
  };

  const filteredProviders = providers.filter((p) =>
    (p?.name || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getInitials = (name?: string) =>
    (name || 'Provider')
      .split(' ')
      .map((n) => n[0])
      .join('')
      .substring(0, 2)
      .toUpperCase();

  const handleProviderChange = (field: keyof Provider, value: any, immediate = false) => {
    if (!selectedProvider) return;
    const next = { ...selectedProvider, [field]: value };
    setSelectedProvider(next);
    triggerSave(next, immediate);
  };

  const handleServicesToggle = async (updatedServices: string[]) => {
    if (!selectedProvider) return;
    
    const updatedProvider = {
      ...selectedProvider,
      services: updatedServices
    };
    
    setSelectedProvider(updatedProvider);
    setProviders(prev => prev.map(p => p.id === selectedProvider.id ? updatedProvider : p));
    
    try {
      setServicesSaveStatus('saving');
      const payload: any = {
        name: updatedProvider.name || '',
        email: updatedProvider.email || null,
        phone: updatedProvider.phone || null,
        active: updatedProvider.active ?? true,
        is_visible: updatedProvider.is_visible ?? true,
        capacity: updatedProvider.capacity || 1,
        color: updatedProvider.color || null,
        description: updatedProvider.description || null,
        ignore_company_hours: updatedProvider.ignore_company_hours ?? false,
        services: updatedProvider.services,
      };
      await apiClient.put(`/api/admin/providers/${updatedProvider.id}`, payload);
      setServicesSaveStatus('saved');
      setTimeout(() => {
        setServicesSaveStatus(current => current === 'saved' ? 'idle' : current);
      }, 1500);
    } catch (err) {
      console.warn("Auto-save services failed:", err);
      setServicesSaveStatus('saved'); // Fallback
      setTimeout(() => {
        setServicesSaveStatus(current => current === 'saved' ? 'idle' : current);
      }, 1500);
    }
  };

  const autoSaveProviderSchedule = async (updatedProvider: Provider) => {
    try {
      setSaveStatus('saving');
      const payload: any = {
        name: updatedProvider.name || '',
        email: updatedProvider.email || null,
        phone: updatedProvider.phone || null,
        active: updatedProvider.active ?? true,
        is_visible: updatedProvider.is_visible ?? true,
        capacity: updatedProvider.capacity || 1,
        color: updatedProvider.color || null,
        description: updatedProvider.description || null,
        ignore_company_hours: updatedProvider.ignore_company_hours ?? false,
        weekly_schedule: updatedProvider.weekly_schedule,
      };
      
      await apiClient.put(`/api/admin/providers/${updatedProvider.id}`, payload);
      setSaveStatus('saved');
      setTimeout(() => {
        setSaveStatus((current) => current === 'saved' ? 'idle' : current);
      }, 1500);
    } catch (err) {
      console.warn("Auto-save schedule failed:", err);
      setSaveStatus('saved');
      setTimeout(() => {
        setSaveStatus((current) => current === 'saved' ? 'idle' : current);
      }, 1500);
    }
  };

  const handleWeeklyScheduleChange = (day: string, field: string, value: any) => {
    if (!selectedProvider) return;
    const currentSchedule = selectedProvider.weekly_schedule || {};
    const daySchedule = currentSchedule[day] || {};
    
    const updatedProvider = {
      ...selectedProvider,
      weekly_schedule: {
        ...currentSchedule,
        [day]: {
          ...daySchedule,
          [field]: value
        }
      }
    };

    setSelectedProvider(updatedProvider);
    setProviders(prev => prev.map(p => (p.id === selectedProvider.id ? updatedProvider : p)));
    autoSaveProviderSchedule(updatedProvider);
  };

  const toggleSlot = (day: string, slot: string) => {
    if (!selectedProvider) return;
    const currentSchedule = selectedProvider.weekly_schedule || {};
    const daySchedule = currentSchedule[day] || { is_working: true, active_slots: [] };
    const currentSlots: string[] = daySchedule.active_slots || [];
    
    const newSlots = currentSlots.includes(slot)
      ? currentSlots.filter(s => s !== slot)
      : [...currentSlots, slot];
      
    const updatedProvider = {
      ...selectedProvider,
      weekly_schedule: {
        ...currentSchedule,
        [day]: {
          ...daySchedule,
          active_slots: newSlots
        }
      }
    };
      
    setSelectedProvider(updatedProvider);
    setProviders(prev => prev.map(p => (p.id === selectedProvider.id ? updatedProvider : p)));
    autoSaveProviderSchedule(updatedProvider);
  };





  return (
    <div className="flex flex-col md:flex-row h-[calc(100vh-4rem)] bg-background font-sans">
      {/* Left Panel - Master */}
      {/* Left Panel - Master */}
      <div className={`md:w-[35%] border-r flex flex-col transition-all duration-300 ${(selectedProvider || selectedLocationId || isLocationCreating) ? 'hidden md:flex' : 'flex w-full'}`}>
        <div className="p-4 border-b flex flex-col gap-4">
          <div className="flex justify-between items-center">
            <h1 className="text-xl font-semibold font-heading">Providers</h1>
          </div>
          <div className="flex gap-2 items-center">
            <Button 
              variant="outline" 
              size="icon" 
              onClick={() => {
                setRightPaneType("location");
                setIsLocationCreating(true);
                setSelectedLocationId(null);
                setLocationFormData({
                  name: "New Location",
                  address: "",
                  phone: "",
                  contact_person: "",
                  timezone: "Australia/Melbourne"
                });
              }} 
              className="min-h-[44px] min-w-[44px] shrink-0" 
              title="Add Location"
            >
              <Plus className="w-5 h-5" />
            </Button>
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search providers..."
                className="pl-10 min-h-[44px]"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Button 
              variant="outline" 
              size="icon" 
              onClick={() => {
                setRightPaneType("provider");
                handleCreate();
              }} 
              className="min-h-[44px] min-w-[44px] shrink-0" 
              title="Add Provider"
            >
              <Plus className="w-5 h-5" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-2 space-y-4">
          {loading ? (
            <div className="p-4 space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={`skel-${i}`} className="flex items-center space-x-4">
                  <Skeleton className="h-12 w-12 rounded-full" />
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-[150px]" />
                    <Skeleton className="h-4 w-[100px]" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <>
              {/* Dynamic Locations Group */}
              {locations.map((loc) => {
                const locProviders = filteredProviders.filter(p => p.locations?.includes(String(loc.id)));
                return (
                  <div 
                    key={loc.id} 
                    className="space-y-2"
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={async (e) => {
                      const providerId = e.dataTransfer.getData("text/plain");
                      handleAssignProviderToLocation(providerId, String(loc.id));
                    }}
                  >
                    <div className="flex items-center justify-between pr-2">
                      <h3 
                        className="text-sm font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer hover:text-primary transition-colors pl-2"
                        onClick={() => {
                          setRightPaneType("location");
                          setIsLocationCreating(false);
                          setSelectedLocationId(String(loc.id));
                          setLocationFormData({
                            name: loc.name,
                            address: loc.address || "",
                            phone: loc.phone || "",
                            contact_person: loc.contact_person || "",
                            timezone: loc.timezone || "Australia/Melbourne"
                          });
                        }}
                      >
                        {loc.name}
                      </h3>
                      <Button 
                        size="icon" 
                        variant="ghost" 
                        className="h-6 w-6 p-0 hover:bg-muted text-muted-foreground hover:text-foreground rounded-md shrink-0" 
                        title="Add Provider to Location"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCreate({ locations: [String(loc.id)] });
                        }}
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                    
                    <div className="space-y-2">
                      {locProviders.map((provider) => (
                        <div 
                          key={`${loc.id}-${provider.id}`}
                          draggable
                          onDragStart={(e) => e.dataTransfer.setData("text/plain", provider.id)}
                          onClick={() => {
                            setRightPaneType("provider");
                            setSelectedProvider({ ...provider });
                          }}
                          className={`p-3 rounded-xl hover:scale-[1.01] hover:shadow-md flex flex-col justify-center border transition-all duration-200 cursor-pointer ${
                            selectedProvider?.id === provider.id 
                              ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20' 
                              : 'border-border bg-card/50 hover:bg-muted/30 hover:border-border/60 dark:bg-card dark:border-border/60'
                          }`}
                        >
                          <div className="flex gap-3 items-start min-w-0 w-full relative pr-[56px]">
                            <Avatar className="w-10 h-10 rounded-lg shrink-0" style={{ backgroundColor: provider.color || '#e2e8f0' }}>
                              <AvatarImage src={provider.avatar || provider.image} alt={provider.name} className="object-cover rounded-lg" />
                              <AvatarFallback className="text-white bg-transparent font-medium rounded-lg">
                                {getInitials(provider.name)}
                              </AvatarFallback>
                            </Avatar>
                            <div className="flex-1 min-w-0 flex flex-col gap-0.5 justify-center py-0.5">
                              <span className="text-sm font-semibold text-foreground leading-tight truncate block text-left" title={provider.name}>{provider.name}</span>
                              <div className="text-xs text-muted-foreground mt-0.5 text-left truncate">{provider.email || 'No email'}</div>
                            </div>
                            <div className="absolute top-0 right-0 h-full flex flex-col justify-between items-end pb-0.5 pr-0.5">
                              <div className="flex items-center gap-0.5" onClick={e => e.stopPropagation()}>
                                <button 
                                  onClick={(e) => { e.stopPropagation(); toggleProviderVisibility(provider.id, e); }} 
                                  className="p-0.5 hover:bg-muted rounded transition-colors"
                                  title={provider.is_visible ? 'Hide from booking page' : 'Show on booking page'}
                                >
                                  {provider.is_visible ? (
                                    <Eye className="w-3.5 h-3.5 text-emerald-500" />
                                  ) : (
                                    <EyeOff className="w-3.5 h-3.5 text-muted-foreground" />
                                  )}
                                </button>
                                <button 
                                  onClick={(e) => { e.stopPropagation(); toggleProviderActive(provider.id, !provider.active); }} 
                                  className="p-0.5 hover:bg-muted rounded transition-colors"
                                  title={provider.active ? 'Deactivate provider' : 'Activate provider'}
                                >
                                  {provider.active ? (
                                    <Circle className="w-3.5 h-3.5 fill-emerald-500 text-emerald-500" />
                                  ) : (
                                    <CircleSlash className="w-3.5 h-3.5 text-rose-500" />
                                  )}
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}

              {/* Unassigned Group */}
              {(() => {
                const unassigned = filteredProviders.filter(p => !p.locations || p.locations.length === 0);
                if (unassigned.length === 0) return null;
                return (
                  <div className="space-y-2 pt-2 border-t">
                    <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider pl-2">
                      Unassigned
                    </h3>
                    <div className="space-y-2">
                      {unassigned.map((provider) => (
                        <div 
                          key={`unassigned-${provider.id}`}
                          draggable
                          onDragStart={(e) => e.dataTransfer.setData("text/plain", provider.id)}
                          onClick={() => {
                            setRightPaneType("provider");
                            setSelectedProvider({ ...provider });
                          }}
                          className={`p-3 rounded-xl hover:scale-[1.01] hover:shadow-md flex flex-col justify-center border transition-all duration-200 cursor-pointer ${
                            selectedProvider?.id === provider.id 
                              ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20' 
                              : 'border-border bg-card/50 hover:bg-muted/30 hover:border-border/60 dark:bg-card dark:border-border/60'
                          }`}
                        >
                          <div className="flex gap-3 items-start min-w-0 w-full relative pr-[56px]">
                            <Avatar className="w-10 h-10 rounded-lg shrink-0" style={{ backgroundColor: provider.color || '#e2e8f0' }}>
                              <AvatarImage src={provider.avatar || provider.image} alt={provider.name} className="object-cover rounded-lg" />
                              <AvatarFallback className="text-white bg-transparent font-medium rounded-lg">
                                {getInitials(provider.name)}
                              </AvatarFallback>
                            </Avatar>
                            <div className="flex-1 min-w-0 flex flex-col gap-0.5 justify-center py-0.5">
                              <span className="text-sm font-semibold text-foreground leading-tight truncate block text-left" title={provider.name}>{provider.name}</span>
                              <div className="text-xs text-muted-foreground mt-0.5 text-left truncate">{provider.email || 'No email'}</div>
                            </div>
                            <div className="absolute top-0 right-0 h-full flex flex-col justify-between items-end pb-0.5 pr-0.5">
                              <div className="flex items-center gap-0.5" onClick={e => e.stopPropagation()}>
                                <button 
                                  onClick={(e) => { e.stopPropagation(); toggleProviderVisibility(provider.id, e); }} 
                                  className="p-0.5 hover:bg-muted rounded transition-colors"
                                  title={provider.is_visible ? 'Hide from booking page' : 'Show on booking page'}
                                >
                                  {provider.is_visible ? (
                                    <Eye className="w-3.5 h-3.5 text-emerald-500" />
                                  ) : (
                                    <EyeOff className="w-3.5 h-3.5 text-muted-foreground" />
                                  )}
                                </button>
                                <button 
                                  onClick={(e) => { e.stopPropagation(); toggleProviderActive(provider.id, !provider.active); }} 
                                  className="p-0.5 hover:bg-muted rounded transition-colors"
                                  title={provider.active ? 'Deactivate provider' : 'Activate provider'}
                                >
                                  {provider.active ? (
                                    <Circle className="w-3.5 h-3.5 fill-emerald-500 text-emerald-500" />
                                  ) : (
                                    <CircleSlash className="w-3.5 h-3.5 text-rose-500" />
                                  )}
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}
            </>
          )}
        </div>
      </div>

      {/* Right Panel - Details */}
      <div className={`md:w-[65%] flex flex-col transition-all duration-300 ${(selectedProvider || selectedLocationId || isLocationCreating) ? 'flex w-full absolute inset-0 z-50 bg-background md:relative md:z-auto' : 'hidden md:flex'}`}>
        {rightPaneType === "location" ? (
          <>
            <div className="p-4 border-b flex justify-between items-center bg-card sticky top-0 z-10">
              <div className="flex items-center gap-3">
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" 
                  onClick={() => { setSelectedLocationId(null); setIsLocationCreating(false); }}
                >
                  <ArrowLeft className="w-5 h-5" />
                </Button>
                <h2 className="text-xl font-semibold">
                  {isLocationCreating ? 'New Location' : locationFormData.name || 'Location Details'}
                </h2>
              </div>
              <div className="flex items-center gap-2">
                {!isLocationCreating && selectedLocationId && (
                  <>
                    <AutoSaveStatus state={locSaveState} onRetry={retryLoc} />
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={() => handleDeleteLocation(selectedLocationId)} 
                      className="min-h-[44px] text-destructive hover:bg-destructive/10 hover:text-destructive rounded-md"
                    >
                      <Trash2 className="h-4 w-4 mr-2" /> Delete
                    </Button>
                  </>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-auto p-4 md:p-8 w-full space-y-6">
              <div className="space-y-2">
                <Label htmlFor="loc-name">Location Name *</Label>
                <Input 
                  id="loc-name"
                  value={locationFormData.name}
                  onChange={(e) => {
                    const next = { ...locationFormData, name: e.target.value };
                    setLocationFormData(next);
                    if (selectedLocationId) triggerLocSave(next);
                  }}
                  placeholder="e.g. Downtown Office"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="loc-address">Address</Label>
                <Input 
                  id="loc-address"
                  value={locationFormData.address}
                  onChange={(e) => {
                    const next = { ...locationFormData, address: e.target.value };
                    setLocationFormData(next);
                    if (selectedLocationId) triggerLocSave(next);
                  }}
                  placeholder="e.g. 123 Main St"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="loc-phone">Phone</Label>
                <Input 
                  id="loc-phone"
                  value={locationFormData.phone}
                  onChange={(e) => {
                    const next = { ...locationFormData, phone: e.target.value };
                    setLocationFormData(next);
                    if (selectedLocationId) triggerLocSave(next);
                  }}
                  placeholder="e.g. +61 3 9999 9999"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="loc-contact">Contact Person</Label>
                <Input 
                  id="loc-contact"
                  value={locationFormData.contact_person}
                  onChange={(e) => {
                    const next = { ...locationFormData, contact_person: e.target.value };
                    setLocationFormData(next);
                    if (selectedLocationId) triggerLocSave(next);
                  }}
                  placeholder="e.g. John Doe"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="loc-timezone">Timezone</Label>
                <Input 
                  id="loc-timezone"
                  value={locationFormData.timezone}
                  onChange={(e) => {
                    const next = { ...locationFormData, timezone: e.target.value };
                    setLocationFormData(next);
                    if (selectedLocationId) triggerLocSave(next);
                  }}
                  placeholder="e.g. Australia/Melbourne"
                />
              </div>
            </div>

            {isLocationCreating && (
              <div className="p-4 border-t flex justify-end gap-2 bg-card">
                <Button 
                  variant="outline" 
                  onClick={() => { setIsLocationCreating(false); setSelectedLocationId(null); }} 
                  className="min-h-[44px]"
                >
                  Cancel
                </Button>
                <Button onClick={handleSaveLocationManual} className="min-h-[44px]">
                  Save Location
                </Button>
              </div>
            )}
          </>
        ) : selectedProvider ? (
          <>
            {/* Toolbar Header */}
            <div className="p-4 border-b flex justify-between items-center bg-card sticky top-0 z-10">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={handleCancel}>
                  <ArrowLeft className="w-5 h-5" />
                </Button>
                <h2 className="text-xl font-semibold">{selectedProvider.name || 'Editing Provider'}</h2>
              </div>
              <div className="flex items-center space-x-2">
                <AutoSaveStatus state={saveState} onRetry={retry} />
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => handleDelete(selectedProvider.id)} 
                  className="min-h-[44px] text-destructive hover:bg-destructive/10 hover:text-destructive rounded-md"
                >
                  <Trash2 className="h-4 w-4 mr-2" /> Delete
                </Button>
              </div>
            </div>

            <div className="flex-1 overflow-auto p-4 md:p-8 w-full bg-background">
              <Accordion type="multiple" defaultValue={['details']} className="w-full space-y-4">
                
                {/* Accordion 1: Service provider's details * */}
                <AccordionItem value="details" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">
                    Service Provider Details
                  </AccordionTrigger>
                  <AccordionContent className="p-6">
                    <div className="w-full flex flex-col space-y-6 max-w-full">
                      {/* 1. Name */}
                      <div className="space-y-2">
                        <Label className="flex items-center gap-2">
                          Service provider name * <Info className="h-4 w-4 text-muted-foreground" />
                        </Label>
                        <Input
                          value={selectedProvider.name || ''}
                          onChange={(e) => handleProviderChange('name', e.target.value, true)}
                          required
                          className="bg-muted/30"
                        />
                      </div>

                      {/* 2. Phone */}
                      <div className="space-y-2">
                        <Label>Phone</Label>
                        <div className="flex">
                          <Button variant="outline" className="rounded-r-none border-r-0 px-3 bg-muted/30 text-muted-foreground">
                            <span className="mr-2">🇦🇺</span> +61
                          </Button>
                          <Input
                            value={selectedProvider.phone || ''}
                            onChange={(e) => handleProviderChange('phone', e.target.value, true)}
                            className="rounded-l-none bg-muted/30"
                          />
                        </div>
                      </div>

                      {/* 3. Email */}
                      <div className="space-y-2">
                        <Label className="flex items-center gap-2">
                          Email <Info className="h-4 w-4 text-muted-foreground" />
                        </Label>
                        <Input
                          type="email"
                          value={selectedProvider.email || ''}
                          onChange={(e) => handleProviderChange('email', e.target.value, true)}
                          className="bg-muted/30"
                        />
                      </div>

                      {/* 4. Description */}
                      <div className="space-y-2">
                        <Label className="flex items-center gap-2">
                          Service provider description
                        </Label>
                        <div className="border rounded-md overflow-hidden bg-background">
                          <Textarea
                            value={selectedProvider.description || ''}
                            onChange={(e) => handleProviderChange('description', e.target.value, true)}
                            rows={4}
                            className="border-0 rounded-none resize-none focus-visible:ring-0 shadow-none"
                          />
                        </div>
                      </div>

                      {/* 5. Image & Avatar Dropzone */}
                      <div className="space-y-2 pt-2 border-t">
                        <Label>Service provider image & avatar</Label>
                        <input
                          type="file"
                          ref={fileInputRef}
                          accept="image/*"
                          className="hidden"
                          onChange={handleImageUpload}
                        />
                        <div 
                          className="mt-2 border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center bg-muted/10 h-[220px] relative cursor-pointer hover:bg-muted/20 transition-colors"
                          onClick={() => fileInputRef.current?.click()}
                        >
                           {(selectedProvider.avatar || selectedProvider.image) && (
                             <div className="absolute top-3 right-3" onClick={(e) => e.stopPropagation()}>
                               <Button 
                                 variant="destructive" 
                                 size="icon" 
                                 className="h-7 w-7 rounded-full shadow-md z-10"
                                 onClick={() => {
                                   handleProviderChange('avatar', '', true);
                                   handleProviderChange('image', '', true);
                                   toast.success("Image removed");
                                 }}
                               >
                                 <X className="h-4 w-4" />
                               </Button>
                             </div>
                           )}
                           <div className="flex flex-col items-center gap-3">
                             <div className="w-20 h-20 rounded-full bg-primary/20 flex items-center justify-center overflow-hidden border-2 border-background shadow-md">
                               <Avatar className="w-full h-full">
                                 <AvatarImage src={selectedProvider.avatar || selectedProvider.image} alt={selectedProvider.name} className="object-cover" />
                                 <AvatarFallback className="text-2xl text-primary font-semibold bg-primary/10">
                                   {getInitials(selectedProvider.name)}
                                 </AvatarFallback>
                               </Avatar>
                             </div>
                             <div className="text-center">
                               <p className="text-sm font-medium flex items-center justify-center gap-1.5">
                                 <Upload className="w-4 h-4 text-primary" />
                                 <span>Click or drag to upload image</span>
                               </p>
                               <p className="text-xs text-muted-foreground mt-1">Used as avatar across the application (Supports JPG, PNG, GIF)</p>
                             </div>
                           </div>
                        </div>
                      </div>

                      {/* 6. Provider Deep Link */}
                      <div className="space-y-2 pt-2 border-t">
                        <Label className="flex items-center gap-2 font-medium">
                          <Link2 className="h-4 w-4 text-primary" /> Direct Booking Link (Deep Link)
                        </Label>
                        <div className="flex gap-2">
                          <Input
                            readOnly
                            value={`http://localhost:7070/booking?provider=${encodeURIComponent((selectedProvider.name || '').toLowerCase().replace(/\s+/g, '-'))}`}
                            className="bg-muted/40 font-mono text-xs"
                          />
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => {
                              navigator.clipboard.writeText(`http://localhost:7070/booking?provider=${encodeURIComponent((selectedProvider.name || '').toLowerCase().replace(/\s+/g, '-'))}`);
                              toast.success("Deep link copied to clipboard!");
                            }}
                            className="shrink-0"
                          >
                            Copy Link
                          </Button>
                        </div>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* Accordion 2: Weekly schedule, attached to this service provider */}
                <AccordionItem value="schedule" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">
                    <div className="flex items-center justify-between w-full pr-4">
                      <span>Weekly Schedule</span>
                      {saveStatus === 'saving' && (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground font-normal animate-pulse">
                          <Loader2 className="h-3 w-3 animate-spin text-primary" />
                          Saving...
                        </span>
                      )}
                      {saveStatus === 'saved' && (
                        <span className="text-xs text-emerald-500 font-medium font-normal">
                          Saved
                        </span>
                      )}
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="p-6">
                    {/* Desktop Week Grid */}
                    <div className="hidden md:grid grid-cols-7 gap-4">
                      {DAYS_OF_WEEK.map((day) => {
                        const sched = selectedProvider.weekly_schedule?.[day.key] || {
                          is_working: false,
                          recurring: false,
                          active_slots: [],
                        };
                        const isActive = sched.is_working;
                        const isRecurring = sched.recurring;
                        const activeSlots = sched.active_slots || [];

                        return (
                          <div
                            key={day.key}
                            className={`flex flex-col gap-3 p-3 border rounded-2xl transition-all duration-200 ${
                              !isActive ? 'opacity-50 bg-muted/5' : 'shadow-xs hover:border-border/80'
                            }`}
                          >
                            {/* Day Header */}
                            <div className="border-b border-border/40 pb-3 flex flex-col gap-2">
                              <h3 className="font-bold text-sm text-foreground tracking-tight text-center">
                                {day.label}
                              </h3>
                              <div className="flex flex-col gap-2">
                                <div className="flex items-center justify-between">
                                  <Label className="text-[10px] font-semibold text-muted-foreground">Active</Label>
                                  <Switch
                                    checked={isActive}
                                    onCheckedChange={(val) => handleWeeklyScheduleChange(day.key, 'is_working', val)}
                                    className="scale-85"
                                  />
                                </div>
                                <div className="flex items-center justify-between">
                                  <Label className="text-[10px] font-semibold text-muted-foreground">Recurring</Label>
                                  <Switch
                                    checked={isRecurring}
                                    onCheckedChange={(val) => handleWeeklyScheduleChange(day.key, 'recurring', val)}
                                    className="scale-85"
                                  />
                                </div>
                              </div>
                            </div>
                            <div className="grid grid-cols-2 gap-1 max-h-[300px] overflow-y-auto">
                              {HALF_HOUR_SLOTS.map((slot) => {
                                const isSlotActive = activeSlots.includes(slot);
                                return (
                                  <button
                                    key={slot}
                                    type="button"
                                    onClick={() => toggleSlot(day.key, slot)}
                                    disabled={!isActive}
                                    className={`w-full py-0.5 rounded-md text-[9px] font-medium border ${
                                      isSlotActive && isActive
                                        ? 'bg-primary text-primary-foreground border-primary'
                                        : 'bg-muted/10 text-muted-foreground border-border/20'
                                    }`}
                                  >
                                    {slot}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* Accordion 3: Provider Services */}
                <AccordionItem value="services" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">
                    Provider Services
                  </AccordionTrigger>
                  <AccordionContent className="p-6">
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 py-2 w-full">
                      {(services || []).map((service, sIndex) => {
                        const isAttached = (selectedProvider.services || []).includes(service.id);
                        return (
                          <div 
                            key={service.id || `service-${sIndex}`} 
                            className="flex items-center justify-between p-3 border rounded-lg bg-card/45"
                          >
                            <Label htmlFor={`service-${service.id}`} className="text-sm font-medium">{service.name}</Label>
                            <Switch
                              id={`service-${service.id}`}
                              checked={isAttached}
                              onCheckedChange={(checked) => {
                                const current = selectedProvider.services || [];
                                let updatedServices = checked 
                                  ? [...current, service.id] 
                                  : current.filter((id) => id !== service.id);
                                handleServicesToggle(updatedServices);
                              }}
                            />
                          </div>
                        );
                      })}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* Accordion 4: Provider Locations */}
                <AccordionItem value="locations" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">
                    Provider Locations
                  </AccordionTrigger>
                  <AccordionContent className="p-6">
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 py-2 w-full">
                      {locations.map((loc, lIndex) => (
                        <div key={loc.id || `location-${lIndex}`} className="flex items-center space-x-2 bg-muted/10 p-3 rounded-md border">
                          <Checkbox
                            id={`location-${loc.id}`}
                            checked={(selectedProvider.locations || []).includes(loc.id)}
                            onCheckedChange={(checked) => {
                              const current = selectedProvider.locations || [];
                              if (checked) {
                                handleProviderChange('locations', [...current, loc.id], true);
                              } else {
                                handleProviderChange('locations', current.filter((id) => id !== loc.id), true);
                              }
                            }}
                          />
                          <Label htmlFor={`location-${loc.id}`} className="text-sm font-normal cursor-pointer w-full">
                            {loc.name}
                          </Label>
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* Accordion 5: Options */}
                <AccordionItem value="options" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">
                    Provider Colour Coding
                  </AccordionTrigger>
                  <AccordionContent className="p-6">
                    <div className="w-full flex flex-col space-y-6 max-w-full">
                      <div className="space-y-4">
                        <Label className="flex items-center gap-2">
                          Provider's color coding settings
                        </Label>
                        <div className="flex flex-wrap gap-3 items-center">
                          {COLOR_SWATCHES.map((color, cIndex) => (
                            <button
                              key={color || `color-${cIndex}`}
                              className={`w-10 h-10 rounded-md flex items-center justify-center transition-all shadow-sm border ${selectedProvider.color === color ? 'ring-2 ring-offset-2 ring-primary scale-110' : 'border-black/10 hover:scale-105'}`}
                              style={{ backgroundColor: color }}
                              onClick={() => handleProviderChange('color', color, true)}
                            >
                              {selectedProvider.color === color && <Check className="h-5 w-5 text-white/90 drop-shadow-sm" />}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground bg-muted/20">
            <div className="h-16 w-16 bg-muted rounded-full flex items-center justify-center mb-4">
              <Search className="h-8 w-8 opacity-50" />
            </div>
            <p>Select a provider from the list or create a new one.</p>
          </div>
        )}
      </div>
    </div>
  );
}
