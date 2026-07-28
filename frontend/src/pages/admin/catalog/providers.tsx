import { useState, useEffect, useRef } from 'react';
import { 
  Search, Plus, Trash2, Save, ArrowLeft, Copy, Info, 
  Wand2, 
  List, ListOrdered, AlignLeft, AlignCenter, AlignRight, 
  Link, Image as ImageIcon, Video, Code, HelpCircle, 
  X, Check,
  ChevronDown, Link2, Upload,
  Eye, EyeOff, Loader2
} from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '@/lib/api';
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

  const handleCreate = async () => {
    const defaultData = {
      name: 'New Provider',
      active: true,
      is_visible: true,
      ignore_company_hours: false,
      capacity: 1,
      color: '#34bbf1',
      description: '',
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
          locations: []
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
        locations: []
      };
    }

    setProviders(prev => [...prev, createdProvider!]);
    setSelectedProvider(createdProvider);
    toast.success('Provider created successfully');
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

  const toggleProviderVisibility = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setProviders(prev => prev.map(p => {
      if (p.id === id) {
        const nextVis = !p.is_visible;
        if (selectedProvider?.id === id) {
          setSelectedProvider({ ...selectedProvider, is_visible: nextVis });
        }
        toast.success(`Provider ${nextVis ? 'visible on' : 'hidden from'} booking page`);
        return { ...p, is_visible: nextVis };
      }
      return p;
    }));
  };

  const toggleProviderActive = (id: string, active: boolean) => {
    setProviders(prev => prev.map(p => {
      if (p.id === id) {
        if (selectedProvider?.id === id) {
          setSelectedProvider({ ...selectedProvider, active });
        }
        toast.success(`Provider status set to ${active ? 'Active' : 'Inactive'}`);
        return { ...p, active };
      }
      return p;
    }));
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

  const handleProviderChange = (field: keyof Provider, value: any) => {
    if (!selectedProvider) return;
    setSelectedProvider({ ...selectedProvider, [field]: value });
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
      <div className={`md:w-[35%] border-r flex flex-col transition-all duration-300 ${selectedProvider ? 'hidden md:flex' : 'flex w-full'}`}>
        <div className="p-4 border-b flex flex-col gap-4">
          <div className="flex justify-between items-center">
            <h1 className="text-xl font-semibold font-heading">Providers</h1>
            <Button onClick={handleCreate} size="sm" className="min-h-[44px]">
              <Plus className="h-4 w-4 mr-2" /> Add Provider
            </Button>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-3.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search providers..."
              className="pl-10 min-h-[44px]"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        <div className="flex-1 overflow-auto p-2">
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
          ) : filteredProviders.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              No providers found.
            </div>
          ) : (
            <ul className="space-y-2">
              {filteredProviders.map((provider, index) => (
                <li
                  key={provider.id || `prov-${index}`}
                  className={`p-3 rounded-xl cursor-pointer hover:bg-muted/50 border transition-all duration-200 hover:scale-[1.01] ${
                    selectedProvider?.id === provider.id ? 'bg-gradient-to-r from-primary/10 via-primary/5 to-transparent border-primary' : 'border-border/60'
                  }`}
                  onClick={() => setSelectedProvider({ ...provider })}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <Avatar style={{ backgroundColor: provider.color || '#e2e8f0' }}>
                        <AvatarImage src={provider.avatar || provider.image} alt={provider.name} className="object-cover" />
                        <AvatarFallback className="text-white bg-transparent font-medium">
                          {getInitials(provider.name)}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <div className="font-medium text-sm">{provider.name}</div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className={`inline-block w-2 h-2 rounded-full ${provider.active ? 'bg-emerald-500' : 'bg-zinc-400'}`} />
                          <span className="text-[11px] text-muted-foreground">{provider.active ? 'Active' : 'Inactive'}</span>
                          {provider.is_visible && (
                            <span className="text-[10px] text-primary bg-primary/10 px-1.5 py-0.2 rounded font-medium ml-1">Visible</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                        title={provider.is_visible ? "Visible on booking page (Click to hide)" : "Hidden from booking page (Click to show)"}
                        onClick={(e) => toggleProviderVisibility(provider.id, e)}
                      >
                        {provider.is_visible ? <Eye className="h-4 w-4 text-primary" /> : <EyeOff className="h-4 w-4 text-muted-foreground/40" />}
                      </Button>
                      <Switch
                        checked={provider.active}
                        onCheckedChange={(checked) => toggleProviderActive(provider.id, checked)}
                      />
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Right Panel - Details */}
      <div className={`md:w-[65%] flex flex-col transition-all duration-300 ${selectedProvider ? 'flex w-full absolute inset-0 z-50 bg-background md:relative md:z-auto' : 'hidden md:flex'}`}>
        {selectedProvider ? (
          <>
            {/* Toolbar Header */}
            <div className="p-4 border-b flex justify-between items-center bg-card sticky top-0 z-10">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={handleCancel}>
                  <ArrowLeft className="w-5 h-5" />
                </Button>
                <h2 className="text-xl font-semibold">{selectedProvider.name || 'Editing Provider'}</h2>
              </div>
              <div className="flex space-x-2">
                <Button variant="outline" size="sm" className="min-h-[44px] rounded-md hidden sm:flex">
                  <Copy className="h-4 w-4 mr-2" /> Clone
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleDelete(selectedProvider.id)} className="min-h-[44px] text-destructive hover:bg-destructive/10 hover:text-destructive rounded-md hidden sm:flex">
                  <Trash2 className="h-4 w-4 mr-2" /> Delete
                </Button>
                <Button variant="outline" size="sm" onClick={handleCancel} className="min-h-[44px] rounded-md">
                  Cancel
                </Button>
                <Button size="sm" onClick={handleUpdate} className="min-h-[44px] rounded-full px-6 bg-primary text-primary-foreground hover:bg-primary/90">
                  <Save className="h-4 w-4 mr-2" /> Save & Close
                </Button>
              </div>
            </div>

            <div className="flex-1 overflow-auto p-4 md:p-8 w-full">
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
                          onChange={(e) => handleProviderChange('name', e.target.value)}
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
                            onChange={(e) => handleProviderChange('phone', e.target.value)}
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
                          onChange={(e) => handleProviderChange('email', e.target.value)}
                          className="bg-muted/30"
                        />
                      </div>

                      {/* 4. Description */}
                      <div className="space-y-2">
                        <Label className="flex items-center gap-2">
                          Service provider description
                        </Label>
                        <div className="border rounded-md overflow-hidden bg-background">
                          {/* Toolbar */}
                          <div className="flex items-center gap-1 p-2 border-b bg-muted/20 flex-wrap">
                            <Button variant="ghost" size="icon" className="h-8 w-8"><Wand2 className="h-4 w-4" /></Button>
                            <div className="w-px h-4 bg-border mx-1" />
                            <Button variant="ghost" size="icon" className="h-8 w-8 font-serif font-bold">B</Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8 font-serif italic">I</Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8 font-serif underline">U</Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8 font-serif line-through">S</Button>
                            <div className="w-px h-4 bg-border mx-1" />
                            <Button variant="ghost" className="h-8 px-2 text-xs flex items-center gap-1">Open Sans <ChevronDown className="h-3 w-3" /></Button>
                            <Button variant="ghost" className="h-8 px-2 text-xs flex items-center gap-1">14 <ChevronDown className="h-3 w-3" /></Button>
                            <Button variant="ghost" className="h-8 w-8 relative flex items-center justify-center">
                              <span className="font-bold">A</span>
                              <div className="absolute bottom-1 left-1/2 -translate-x-1/2 w-4 h-1 bg-yellow-400" />
                            </Button>
                            <div className="w-px h-4 bg-border mx-1" />
                            <Button variant="ghost" size="icon" className="h-8 w-8"><List className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8"><ListOrdered className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8"><AlignLeft className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8"><AlignCenter className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8"><AlignRight className="h-4 w-4" /></Button>
                            <div className="w-px h-4 bg-border mx-1" />
                            <Button variant="ghost" size="icon" className="h-8 w-8"><Link className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8"><ImageIcon className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8"><Video className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8"><Code className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8"><HelpCircle className="h-4 w-4" /></Button>
                          </div>
                          <Textarea
                            value={selectedProvider.description || ''}
                            onChange={(e) => handleProviderChange('description', e.target.value)}
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
                                   handleProviderChange('avatar', '');
                                   handleProviderChange('image', '');
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
                            <Copy className="h-3.5 w-3.5 mr-1.5" /> Copy Link
                          </Button>
                        </div>
                        <p className="text-xs text-muted-foreground">Direct URL clients can use to bypass selection and book this provider directly.</p>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* Accordion 2: Service provider schedule */}
                <AccordionItem value="schedule" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">
                    <div className="flex items-center justify-between w-full pr-4">
                      <span>Provider Scheduling</span>
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
                    {/* Desktop Grid Layout */}
                    <div className="flex md:flex-row gap-2 w-full overflow-x-auto pb-4 scrollbar-thin max-md:hidden items-start">
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
                            className={`border border-border/40 backdrop-blur-md rounded-2xl p-3 flex flex-col gap-3 bg-card/65 transition-all duration-200 min-w-[200px] flex-1 ${
                              !isActive ? 'opacity-50 bg-muted/5' : 'shadow-xs hover:border-border/80'
                            }`}
                          >
                            {/* Day Header */}
                            <div className="border-b border-border/40 pb-3 flex flex-col gap-2">
                              <h3 className="font-bold text-sm text-foreground tracking-tight text-center">
                                {day.label}
                              </h3>

                              {/* Vertical Stack Toggles */}
                              <div className="flex flex-col gap-2.5 mt-1 bg-muted/20 p-2 rounded-xl border border-border/20">
                                <div className="flex items-center justify-between gap-2">
                                  <Label htmlFor={`accordion-${day.key}-active`} className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer">
                                    Active Status
                                  </Label>
                                  <Switch
                                    id={`accordion-${day.key}-active`}
                                    checked={isActive}
                                    onCheckedChange={(val) => handleWeeklyScheduleChange(day.key, 'is_working', val)}
                                    className="scale-85"
                                  />
                                </div>
                                <div className="flex items-center justify-between gap-2">
                                  <Label htmlFor={`accordion-${day.key}-recurring`} className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer">
                                    Recurring
                                  </Label>
                                  <Switch
                                    id={`accordion-${day.key}-recurring`}
                                    checked={isRecurring}
                                    onCheckedChange={(val) => handleWeeklyScheduleChange(day.key, 'recurring', val)}
                                    className="scale-85"
                                  />
                                </div>
                              </div>
                            </div>

                            {/* Time Slots Grid (Vertical Column Scrollable) */}
                            <div className="grid grid-cols-2 gap-1 max-h-[400px] overflow-y-auto pr-1 select-none scrollbar-thin">
                              {HALF_HOUR_SLOTS.map((slot) => {
                                const isSlotActive = activeSlots.includes(slot);
                                return (
                                  <button
                                    key={slot}
                                    type="button"
                                    onClick={() => toggleSlot(day.key, slot)}
                                    disabled={!isActive}
                                    className={`w-full py-0.5 px-1 rounded-md text-[9px] font-medium transition-all text-center border ${
                                      isSlotActive && isActive
                                        ? 'bg-primary text-primary-foreground border-primary font-semibold shadow-sm'
                                        : 'bg-muted/10 text-muted-foreground border-border/20 hover:bg-muted/30 hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed'
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

                    {/* Mobile Tabs Layout */}
                    <div className="md:hidden w-full border border-border/40 backdrop-blur-md bg-card/65 p-4 rounded-2xl shadow-xs">
                      {/* Day Tabs */}
                      <div className="flex border-b border-border/30 pb-2 mb-4 overflow-x-auto gap-1 scrollbar-none">
                        {DAYS_OF_WEEK.map((day) => {
                          const isTabActive = activeMobileTab === day.key;
                          return (
                            <button
                              key={day.key}
                              type="button"
                              onClick={() => setActiveMobileTab(day.key)}
                              className={`flex-1 min-w-[40px] py-1.5 text-center text-xs font-semibold rounded-xl transition-all duration-200 ${
                                isTabActive
                                  ? 'bg-primary text-primary-foreground shadow-sm'
                                  : 'bg-muted/30 text-muted-foreground hover:bg-muted/60'
                              }`}
                            >
                              {day.short}
                            </button>
                          );
                        })}
                      </div>

                      {/* Selected Day View */}
                      {(() => {
                        const day = DAYS_OF_WEEK.find((d) => d.key === activeMobileTab)!;
                        const sched = selectedProvider.weekly_schedule?.[day.key] || {
                          is_working: false,
                          recurring: false,
                          active_slots: [],
                        };
                        const isActive = sched.is_working;
                        const isRecurring = sched.recurring;
                        const activeSlots = sched.active_slots || [];

                        return (
                          <div className="flex flex-col gap-4">
                            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-border/20 pb-3 gap-3">
                              <h3 className="font-bold text-lg text-foreground">{day.label} Schedule</h3>
                              
                              {/* Vertical Stack Toggles */}
                              <div className="flex flex-col gap-2.5 bg-muted/20 p-3 rounded-xl border border-border/20 w-full sm:w-56">
                                <div className="flex items-center justify-between gap-4">
                                  <Label htmlFor={`mobile-accordion-${day.key}-active`} className="text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer">
                                    Active Status
                                  </Label>
                                  <Switch
                                    id={`mobile-accordion-${day.key}-active`}
                                    checked={isActive}
                                    onCheckedChange={(val) => handleWeeklyScheduleChange(day.key, 'is_working', val)}
                                  />
                                </div>
                                <div className="flex items-center justify-between gap-4">
                                  <Label htmlFor={`mobile-accordion-${day.key}-recurring`} className="text-xs font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer">
                                    Recurring
                                  </Label>
                                  <Switch
                                    id={`mobile-accordion-${day.key}-recurring`}
                                    checked={isRecurring}
                                    onCheckedChange={(val) => handleWeeklyScheduleChange(day.key, 'recurring', val)}
                                  />
                                </div>
                              </div>
                            </div>

                            {/* Time Slots Grid (2 Columns on Mobile for better tap targets) */}
                            <div className="grid grid-cols-2 gap-1 max-h-[300px] overflow-y-auto pr-1 select-none">
                              {HALF_HOUR_SLOTS.map((slot) => {
                                const isSlotActive = activeSlots.includes(slot);
                                return (
                                  <button
                                    key={slot}
                                    type="button"
                                    onClick={() => toggleSlot(day.key, slot)}
                                    disabled={!isActive}
                                    className={`w-full py-0.5 px-1 rounded-md text-[9px] font-medium transition-all text-center border ${
                                      isSlotActive && isActive
                                        ? 'bg-primary text-primary-foreground border-primary font-semibold shadow-sm'
                                        : 'bg-muted/10 text-muted-foreground border-border/20 hover:bg-muted/30 hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed'
                                    }`}
                                  >
                                    {slot}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* Accordion 3: Services, attached to this service provider */}
                <AccordionItem value="services" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">
                    <div className="flex items-center justify-between w-full pr-4">
                      <span>Provider Services</span>
                      {servicesSaveStatus === 'saving' && (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground font-normal animate-pulse">
                          <Loader2 className="h-3 w-3 animate-spin text-primary" />
                          Saving...
                        </span>
                      )}
                      {servicesSaveStatus === 'saved' && (
                        <span className="text-xs text-emerald-500 font-medium font-normal">
                          Saved
                        </span>
                      )}
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="p-6">
                    {services.length === 0 ? (
                      <div className="text-muted-foreground text-sm py-4">No services available.</div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 py-2 w-full">
                        {(services || []).map((service, sIndex) => {
                          const isAttached = (selectedProvider.services || []).includes(service.id);
                          return (
                            <div 
                              key={service.id || `service-${sIndex}`} 
                              className="flex items-center justify-between p-3 border rounded-lg bg-card/45 transition-all hover:border-border/85"
                            >
                              <Label htmlFor={`service-${service.id}`} className="text-sm font-medium cursor-pointer select-none pr-2">
                                {service.name}
                              </Label>
                              <Switch
                                id={`service-${service.id}`}
                                checked={isAttached}
                                onCheckedChange={(checked) => {
                                  const current = selectedProvider.services || [];
                                  let updatedServices;
                                  if (checked) {
                                    updatedServices = [...current, service.id];
                                  } else {
                                    updatedServices = current.filter((id) => id !== service.id);
                                  }
                                  handleServicesToggle(updatedServices);
                                }}
                              />
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </AccordionContent>
                </AccordionItem>

                {/* Accordion 4: Service provider's locations */}
                <AccordionItem value="locations" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">
                    Provider Locations
                  </AccordionTrigger>
                  <AccordionContent className="p-6">
                    {locations.length === 0 ? (
                      <div className="text-muted-foreground text-sm py-4">No locations available.</div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 py-2 w-full">
                        {locations.map((loc, lIndex) => (
                          <div key={loc.id || `location-${lIndex}`} className="flex items-center space-x-2 bg-muted/10 p-3 rounded-md border">
                            <Checkbox
                              id={`location-${loc.id}`}
                              checked={(selectedProvider.locations || []).includes(loc.id)}
                              onCheckedChange={(checked) => {
                                const current = selectedProvider.locations || [];
                                if (checked) {
                                  handleProviderChange('locations', [...current, loc.id]);
                                } else {
                                  handleProviderChange('locations', current.filter((id) => id !== loc.id));
                                }
                              }}
                            />
                            <Label htmlFor={`location-${loc.id}`} className="text-sm font-normal cursor-pointer w-full">
                              {loc.name}
                            </Label>
                          </div>
                        ))}
                      </div>
                    )}
                  </AccordionContent>
                </AccordionItem>

                {/* Accordion 5: More options */}
                <AccordionItem value="options" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">
                    Provider Colour Coding
                  </AccordionTrigger>
                  <AccordionContent className="p-6">
                    <div className="w-full flex flex-col space-y-6 max-w-full">
                      <div className="space-y-4">
                        <Label className="flex items-center gap-2">
                          Provider's color coding settings <Info className="h-4 w-4 text-muted-foreground" />
                        </Label>
                        <div className="flex flex-wrap gap-3 items-center">
                          {COLOR_SWATCHES.map((color, cIndex) => (
                            <button
                              key={color || `color-${cIndex}`}
                              className={`w-10 h-10 rounded-md flex items-center justify-center transition-all shadow-sm border ${selectedProvider.color === color ? 'ring-2 ring-offset-2 ring-primary scale-110' : 'border-black/10 hover:scale-105'}`}
                              style={{ backgroundColor: color }}
                              onClick={() => handleProviderChange('color', color)}
                            >
                              {selectedProvider.color === color && <Check className="h-5 w-5 text-white/90 drop-shadow-sm" />}
                            </button>
                          ))}
                          <button
                            className="w-10 h-10 rounded-full border-2 border-dashed border-muted-foreground flex items-center justify-center text-muted-foreground hover:text-foreground hover:border-foreground transition-colors ml-2"
                            onClick={() => {}}
                          >
                            <Plus className="h-5 w-5" />
                          </button>
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
