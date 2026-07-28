import { useState, useEffect } from 'react';
import { Plus, Search, Edit, Trash2, GripVertical, Upload, X, Eye, EyeOff, Circle, CircleSlash, ImageIcon, Clock, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAutoSave } from '@/hooks/use-auto-save';
import { AutoSaveStatus } from '@/components/ui/auto-save-status';

import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';

import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

// Data Types
interface Service {
  id: string;
  name: string;
  description: string;
  active: boolean;
  is_visible: boolean;
  price: number;
  tax_rate_id: string | null;
  deposit_amount: number;
  duration: number;
  buffer_before: number;
  buffer_after: number;
  fixed_start_times: string;
  max_advance_days: number;
  min_group_size: number;
  max_group_size: number;
  has_groups?: boolean;
  category_ids: string[];
  provider_ids: string[];
  addon_ids: string[];
  product_ids: string[];
  requirements: Array<{ resource_type: string; quantity: number }>;
  image: string | null;
}

interface Category { id: string; name: string; description?: string; active: boolean; image?: string | null; }
interface Provider { id: string; name: string; email?: string; color?: string; avatar?: string; image?: string; }
interface Addon { id: string; name: string; price?: number; duration?: number; }
interface Product { id: string; name: string; price?: number; }

const generateHalfHourSlots = (): string[] => {
  const slots: string[] = [];
  const hours = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
  for (const period of ['AM', 'PM']) {
    for (const hour of hours) {
      slots.push(`${hour}:00 ${period}`);
      slots.push(`${hour}:30 ${period}`);
    }
  }
  return slots;
};
const HALF_HOUR_SLOTS = generateHalfHourSlots();

// Parse stored comma-string like "09:00, 13:30" <-> pill values
const to24h = (slot: string): string => {
  const [time, period] = slot.split(' ');
  let [h, m] = time.split(':').map(Number);
  if (period === 'AM' && h === 12) h = 0;
  if (period === 'PM' && h !== 12) h += 12;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
};
const to12h = (hhmm: string): string => {
  const [h, m] = hhmm.split(':').map(Number);
  const period = h < 12 ? 'AM' : 'PM';
  const hour = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${hour}:${String(m).padStart(2,'0')} ${period}`;
};
const parseSelectedSlots = (csv: string): string[] =>
  csv.split(',').map(s => s.trim()).filter(Boolean).map(s => {
    // If already in 12h format just return as-is, else convert
    return s.includes('AM') || s.includes('PM') ? s : to12h(s);
  });


function ImageUpload({ imagePreview, onImageSelect, onImageRemove, disabled }: { imagePreview: string | null; onImageSelect: (file: string) => void; onImageRemove: () => void; disabled?: boolean }) {
  const handleDrop = (e: React.DragEvent) => {
    if (disabled) return;
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith('image/')) handleFile(file);
  };
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (disabled) return;
    const file = e.target.files?.[0];
    if (file && file.type.startsWith('image/')) handleFile(file);
  };
  const handleFile = (file: File) => {
    // We import toast from 'sonner' in these files
    if (file.size > 5 * 1024 * 1024) { 
        alert('Image must be under 5MB'); 
        return; 
    }
    const reader = new FileReader();
    reader.onload = (e) => onImageSelect(e.target?.result as string);
    reader.readAsDataURL(file);
  };

  return (
    <div 
      onDragOver={e => e.preventDefault()} 
      onDrop={handleDrop}
      className={`relative h-[160px] w-full rounded-lg border-2 border-dashed border-muted-foreground/30 bg-muted/20 hover:bg-muted/40 transition-colors flex items-center justify-center overflow-hidden ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
      onClick={() => !disabled && document.getElementById('img-upload-input')?.click()}
    >
      <input id="img-upload-input" type="file" accept="image/jpeg, image/png, image/gif" className="hidden" onChange={handleChange} disabled={disabled} />
      {imagePreview ? (
        <>
          <img src={imagePreview} alt="Preview" className="w-full h-full object-cover" />
          {!disabled && (
            <button type="button" onClick={(e) => { e.stopPropagation(); onImageRemove(); }} className="absolute top-2 right-2 bg-black/50 hover:bg-black/70 text-white rounded-full p-1">
              <X className="w-4 h-4" />
            </button>
          )}
        </>
      ) : (
        <div className="flex flex-col items-center text-muted-foreground pointer-events-none">
          <Upload className="w-8 h-8 mb-2 opacity-50" />
          <span className="text-sm">Drag & drop image here or click to upload</span>
          <span className="text-xs opacity-70">JPG, PNG, GIF up to 5MB</span>
        </div>
      )}
    </div>
  );
}

interface Resource { id: number; name: string; type: string; }

export default function ServicesPage() {
  const [services, setServices] = useState<Service[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [addons, setAddons] = useState<Addon[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [availableResources, setAvailableResources] = useState<Resource[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isListView, setIsListView] = useState(true);
  
  const [openSection, setOpenSection] = useState<string>('details');
  const [rightPaneType, setRightPaneType] = useState<"service" | "category">("service");
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null);
  const [categoryFormData, setCategoryFormData] = useState<{ name: string; description: string; active: boolean }>({ name: "", description: "", active: true });
  const [isCategoryEditing, setIsCategoryEditing] = useState(false);
  const [isCategoryCreating, setIsCategoryCreating] = useState(false);

  const [newEntityDialog, setNewEntityDialog] = useState<{type: string, open: boolean}>({type: '', open: false});
  const [newEntityName, setNewEntityName] = useState('');

  const [draggedServiceId, setDraggedServiceId] = useState<string | null>(null);
  const [draggedCategoryId, setDraggedCategoryId] = useState<string | null>(null);

  const { saveState, triggerSave, retry } = useAutoSave({
    onSave: async (updatedData: any) => {
      const targetId = selectedServiceId;
      if (!targetId) return;
      try {
        const res = await apiClient.put<any>(`/api/admin/services/${targetId}`, updatedData);
        const dataObj = res?.data || res;
        const returnedService = { ...updatedData, ...dataObj, id: String(dataObj.id || targetId) };
        setServices(prev => prev.map(s => s.id === targetId ? returnedService : s));
      } catch (error: any) {
        toast.error(error.message || "Failed to auto-save service");
        throw error;
      }
    },
    debounceMs: 500
  });

  const defaultFormData: Omit<Service, 'id'> = {
    name: '',
    description: '',
    active: true,
    is_visible: true,
    price: 0,
    tax_rate_id: null,
    deposit_amount: 0,
    duration: 60,
    buffer_before: 0,
    buffer_after: 0,
    fixed_start_times: '',
    max_advance_days: 30,
    min_group_size: 1,
    max_group_size: 1,
    has_groups: false,
    category_ids: [],
    provider_ids: [],
    addon_ids: [],
    product_ids: [],
    requirements: [],
    image: null
  };

  const [formData, setFormData] = useState<Omit<Service, 'id'>>(defaultFormData);

  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (location.state?.selectServiceId) {
      const targetServiceId = String(location.state.selectServiceId);
      const targetSection = location.state.openSection;
      
      setSelectedServiceId(targetServiceId);
      setIsEditing(true);
      setIsCreating(false);
      if (targetSection) {
        setOpenSection(targetSection);
      }
      
      // Clear navigation state so it doesn't trigger on subsequent reloads
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, navigate, location.pathname]);

  useEffect(() => {
    fetchInitialData();
  }, []);

  const fetchInitialData = async () => {
    setLoading(true);
    try {
      const [svcRes, catRes, provRes, addonRes, prodRes, resRes] = await Promise.all([
        apiClient.get<any>('/api/admin/services').catch(() => ({ data: [] })),
        apiClient.get<any>('/api/admin/categories').catch(() => ({ data: [] })),
        apiClient.get<any>('/api/admin/providers').catch(() => ({ data: [] })),
        apiClient.get<any>('/api/admin/add-ons').catch(() => ({ data: [] })),
        apiClient.get<any>('/api/admin/products').catch(() => ({ data: [] })),
        apiClient.get<any>('/api/admin/resources').catch(() => ({ data: [] })),
      ]);
      setServices(Array.isArray(svcRes) ? svcRes : (svcRes?.data ?? []));
      setCategories(Array.isArray(catRes) ? catRes : (catRes?.data ?? []));
      setProviders(Array.isArray(provRes) ? provRes : (provRes?.data ?? []));
      setAddons(Array.isArray(addonRes) ? addonRes : (addonRes?.data ?? []));
      setProducts(Array.isArray(prodRes) ? prodRes : (prodRes?.data ?? []));
      setAvailableResources(Array.isArray(resRes) ? resRes : (resRes?.data ?? []));
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateNew = () => {
    setIsCreating(true);
    setIsEditing(true);
    setSelectedServiceId(null);
    setFormData(defaultFormData);
    setOpenSection('details');
  };

  const handleSelectService = (svc: Service) => {
    setSelectedServiceId(svc.id);
    setIsCreating(false);
    setIsEditing(true);
    setOpenSection('details');
    setFormData({
      name: svc.name || '',
      description: svc.description || '',
      active: svc.active ?? true,
      is_visible: svc.is_visible ?? true,
      price: svc.price || 0,
      tax_rate_id: svc.tax_rate_id || null,
      deposit_amount: svc.deposit_amount || 0,
      duration: svc.duration || 60,
      buffer_before: svc.buffer_before || 0,
      buffer_after: svc.buffer_after || 0,
      fixed_start_times: svc.fixed_start_times || '',
      max_advance_days: svc.max_advance_days || 30,
      min_group_size: svc.min_group_size || 1,
      max_group_size: svc.max_group_size || 1,
      has_groups: (svc.max_group_size || 1) > 1,
      category_ids: svc.category_ids || [],
      provider_ids: svc.provider_ids || [],
      addon_ids: svc.addon_ids || [],
      product_ids: svc.product_ids || [],
      requirements: svc.requirements || [],
      image: svc.image || null
    });
  };

  const handleCancel = () => {
    if (isCreating) {
      setIsCreating(false);
      setIsEditing(false);
    } else if (selectedServiceId) {
      const svc = services.find(s => s.id === selectedServiceId);
      if (svc) {
        handleSelectService(svc);
      }
      setIsEditing(false);
    }
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      toast.error('Name is required');
      return null;
    }

    try {
      if (isCreating) {
        const newSvc = await apiClient.post<Service>('/api/admin/services', formData);
        setServices(prev => [...prev, newSvc]);
        toast.success('Service created successfully');
        handleSelectService(newSvc);
        return newSvc;
      } else if (selectedServiceId) {
        const updatedSvc = await apiClient.put<Service>(`/api/admin/services/${selectedServiceId}`, formData);
        setServices(prev => prev.map(s => s.id === selectedServiceId ? updatedSvc : s));
        toast.success('Service updated successfully');
        handleSelectService(updatedSvc);
        return updatedSvc;
      }
      return null;
    } catch (error) {
      toast.error('Failed to save service');
      return null;
    }
  };

  const handleSaveAndNavigate = async (targetPath: string, section: string) => {
    if (!formData.name.trim()) {
      toast.error('Service Name is required before creating a new option.');
      return;
    }
    
    const savedService = await handleSave();
    if (!savedService) return;
    
    navigate(targetPath, { 
      state: { 
        returnToServiceId: savedService.id, 
        section 
      } 
    });
  };

  const updateServiceQuick = async (id: string, updates: Partial<Service>) => {
    try {
      setServices(prev => prev.map(s => s.id === id ? { ...s, ...updates } : s));
      await apiClient.put(`/api/admin/services/${id}`, updates);
      toast.success('Service updated');
    } catch {
      toast.error('Failed to update service');
      fetchInitialData();
    }
  };

  const handleToggleActive = (svc: Service) => {
    const nextActive = !svc.active;
    const updates: Partial<Service> = { active: nextActive };
    if (!nextActive) {
      updates.is_visible = false;
    }
    updateServiceQuick(svc.id, updates);
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this service?')) return;
    try {
      await apiClient.delete(`/api/admin/services/${id}`);
      setServices(services.filter(s => s.id !== id));
      if (selectedServiceId === id) {
        setSelectedServiceId(null);
        setIsEditing(false);
        setIsCreating(false);
      }
      toast.success('Service deleted');
    } catch (error) {
      toast.error('Failed to delete service');
    }
  };

  const toggleArrayItem = (key: keyof Omit<Service, 'id'>, id: string) => {
    if (!isEditing) return;
    setFormData(prev => {
      const arr = prev[key] as string[];
      if (arr.includes(id)) {
        return { ...prev, [key]: arr.filter(i => i !== id) };
      } else {
        return { ...prev, [key]: [...arr, id] };
      }
    });
  };

  const handleSaveCategory = async () => {
    if (!categoryFormData.name.trim()) {
      toast.error('Category Name is required');
      return;
    }

    try {
      if (isCategoryCreating) {
        const newCat = await apiClient.post<Category>('/api/admin/categories', categoryFormData);
        setCategories(prev => [...prev, newCat]);
        toast.success('Category created successfully');
        setSelectedCategoryId(newCat.id);
        setCategoryFormData({ name: newCat.name, description: newCat.description || "", active: newCat.active });
        setIsCategoryCreating(false);
        setIsCategoryEditing(false);
      } else if (selectedCategoryId) {
        const updatedCat = await apiClient.put<Category>(`/api/admin/categories/${selectedCategoryId}`, categoryFormData);
        setCategories(prev => prev.map(c => c.id === selectedCategoryId ? updatedCat : c));
        toast.success('Category updated successfully');
        setCategoryFormData({ name: updatedCat.name, description: updatedCat.description || "", active: updatedCat.active });
        setIsCategoryEditing(false);
      }
    } catch (error) {
      toast.error('Failed to save category');
    }
  };

  const handleDeleteCategory = async () => {
    if (!selectedCategoryId) return;
    if (!window.confirm('Are you sure you want to delete this category?')) return;

    try {
      await apiClient.delete(`/api/admin/categories/${selectedCategoryId}`);
      setCategories(prev => prev.filter(c => c.id !== selectedCategoryId));
      toast.success('Category deleted successfully');
      setRightPaneType("service");
      setSelectedCategoryId(null);
      setIsCategoryEditing(false);
      setIsCategoryCreating(false);
    } catch (error) {
      toast.error('Failed to delete category');
    }
  };

  const addRequirementRow = () => {
    if (!isEditing) return;
    setFormData(prev => ({
      ...prev,
      requirements: [...prev.requirements, { resource_type: '', quantity: 1 }]
    }));
  };

  const updateRequirement = (index: number, field: 'resource_type' | 'quantity', value: any) => {
    if (!isEditing) return;
    setFormData(prev => {
      const reqs = [...prev.requirements];
      reqs[index] = { ...reqs[index], [field]: value };
      return { ...prev, requirements: reqs };
    });
  };

  const removeRequirement = (index: number) => {
    if (!isEditing) return;
    setFormData(prev => {
      const reqs = [...prev.requirements];
      reqs.splice(index, 1);
      return { ...prev, requirements: reqs };
    });
  };

  const handleDragStartService = (e: React.DragEvent, id: string) => {
    e.stopPropagation();
    setDraggedServiceId(id);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDropService = (e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!draggedServiceId || draggedServiceId === targetId) return;
    
    setServices(prev => {
      const newList = [...prev];
      const srcIdx = newList.findIndex(s => s.id === draggedServiceId);
      const dstIdx = newList.findIndex(s => s.id === targetId);
      if (srcIdx === -1 || dstIdx === -1) return prev;
      
      const [moved] = newList.splice(srcIdx, 1);
      newList.splice(dstIdx, 0, moved);
      return newList;
    });
    setDraggedServiceId(null);
  };

  const handleDragStartCategory = (e: React.DragEvent, catId: string) => {
    setDraggedCategoryId(catId);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDropCategory = (e: React.DragEvent, targetCatId: string) => {
    e.preventDefault();
    if (!draggedCategoryId || draggedCategoryId === targetCatId) return;
    
    setCategories(prev => {
      const newList = [...prev];
      const srcIdx = newList.findIndex(c => c.id === draggedCategoryId);
      const dstIdx = newList.findIndex(c => c.id === targetCatId);
      if (srcIdx === -1 || dstIdx === -1) return prev;
      
      const [moved] = newList.splice(srcIdx, 1);
      newList.splice(dstIdx, 0, moved);
      return newList;
    });
    setDraggedCategoryId(null);
  };

  const handleCreateEntity = async () => {
    if (!newEntityName.trim()) return;
    try {
      let endpoint = '';
      if (newEntityDialog.type === 'categories') endpoint = '/api/admin/categories';
      if (newEntityDialog.type === 'providers') endpoint = '/api/admin/providers';
      if (newEntityDialog.type === 'addons') endpoint = '/api/admin/add-ons';
      if (newEntityDialog.type === 'products') endpoint = '/api/admin/products';
      if (newEntityDialog.type === 'resources') return;

      const newEnt = await apiClient.post<any>(endpoint, { name: newEntityName });
      
      if (newEntityDialog.type === 'categories') setCategories([...categories, newEnt]);
      if (newEntityDialog.type === 'providers') setProviders([...providers, newEnt]);
      if (newEntityDialog.type === 'addons') setAddons([...addons, newEnt]);
      if (newEntityDialog.type === 'products') setProducts([...products, newEnt]);

      toast.success('Created successfully');
      setNewEntityDialog({ type: '', open: false });
      setNewEntityName('');
    } catch {
      toast.error('Failed to create');
    }
  };

  const filteredServices = services.filter(s => (s.name || '').toLowerCase().includes((search || '').toLowerCase()));

  const distinctResourceTypes = Array.from(
    new Set([
      ...availableResources.map(r => r.type),
      ...formData.requirements.map(req => req.resource_type)
    ])
  ).filter(Boolean);

  // Group services
  const groupedServices: Record<string, Service[]> = {};
  const uncategorizedServices: Service[] = [];
  
  filteredServices.forEach(s => {
    if (!s.category_ids || s.category_ids.length === 0) {
      uncategorizedServices.push(s);
    } else {
      s.category_ids.forEach(cid => {
        if (!groupedServices[cid]) groupedServices[cid] = [];
        if (!groupedServices[cid].find(es => es.id === s.id)) {
            groupedServices[cid].push(s);
        }
      });
    }
  });

  return (
    <TooltipProvider>
    <div className="flex flex-col md:flex-row h-full w-full md:gap-4 overflow-hidden font-sans">
      {/* Left Pane - Master List */}
      <div className={`md:w-[35%] flex flex-col gap-4 border-r md:pr-4 transition-all duration-300 ${selectedServiceId || isCreating ? 'hidden md:flex' : 'flex w-full'}`}>
        <div className="flex gap-2 items-center px-4 md:px-0">
          <Button 
            variant="outline" 
            size="icon" 
            onClick={() => {
              setRightPaneType("category");
              isCategoryCreating || setIsCategoryCreating(true);
              isCategoryEditing || setIsCategoryEditing(true);
              setSelectedCategoryId(null);
              setCategoryFormData({ name: "New Category", description: "", active: true });
            }} 
            className="min-h-[44px] min-w-[44px] shrink-0" 
            title="Add Category"
          >
            <Plus className="w-5 h-5" />
          </Button>
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3.5 md:top-2.5 h-4 w-4 text-muted-foreground" />
            <Input 
              placeholder="Search services..." 
              className="pl-10 min-h-[44px]" 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <Button 
            variant="outline" 
            size="icon" 
            onClick={() => {
              setRightPaneType("service");
              handleCreateNew();
            }} 
            className="min-h-[44px] min-w-[44px] shrink-0" 
            title="Add Service"
          >
            <Plus className="w-5 h-5" />
          </Button>
        </div>
        
        <div className="flex-1 overflow-y-auto space-y-4 pb-12">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))
          ) : filteredServices.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">No services found</div>
          ) : (
            <>
              {categories.filter(c => groupedServices[c.id]).map((cat) => (
                <div 
                  key={cat.id} 
                  className="space-y-2"
                  draggable
                  onDragStart={(e) => handleDragStartCategory(e, cat.id)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => handleDropCategory(e, cat.id)}
                >
                  <div className="flex items-center justify-between pr-2">
                    <div className="flex items-center gap-2">
                      <GripVertical className="w-4 h-4 text-muted-foreground cursor-grab active:cursor-grabbing" />
                      <h3 
                        className="text-sm font-semibold text-muted-foreground uppercase tracking-wider cursor-pointer hover:text-primary transition-colors"
                        onClick={() => {
                          setRightPaneType("category");
                          setIsCategoryCreating(false);
                          setIsCategoryEditing(false);
                          setSelectedCategoryId(cat.id);
                          setCategoryFormData({
                            name: cat.name,
                            description: cat.description || "",
                            active: cat.active
                          });
                        }}
                      >
                        {cat.name}
                      </h3>
                    </div>
                    <Button 
                      size="icon" 
                      variant="ghost" 
                      className="h-6 w-6 p-0 hover:bg-muted text-muted-foreground hover:text-foreground rounded-md shrink-0" 
                      title="Add Service to Category"
                      onClick={(e) => {
                        e.stopPropagation();
                        setRightPaneType("service");
                        setIsCreating(true);
                        setIsEditing(true);
                        setSelectedServiceId(null);
                        setFormData({ ...defaultFormData, category_ids: [cat.id] });
                      }}
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                  <div className={isListView ? "space-y-2" : "grid grid-cols-2 gap-2"}>
                    {groupedServices[cat.id].map(svc => (
                      <div 
                        key={`${cat.id}-${svc.id}`}
                        draggable
                        onDragStart={(e) => handleDragStartService(e, svc.id)}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => handleDropService(e, svc.id)}
                        onClick={() => {
                          setRightPaneType("service");
                          handleSelectService(svc);
                        }}
                        className={`p-3 rounded-xl hover:scale-[1.01] hover:shadow-md flex flex-col justify-center border transition-all duration-200 cursor-pointer ${
                          selectedServiceId === svc.id 
                            ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20' 
                            : 'border-border bg-card/50 hover:bg-muted/30 hover:border-border/60 dark:bg-card dark:border-border/60'
                        }`}
                      >
                        <div className="flex gap-3 items-start min-w-0 w-full relative pr-[56px]">
                          {svc.image ? (
                            <img src={svc.image} alt={svc.name} className="w-10 h-10 object-cover rounded-lg shrink-0" />
                          ) : (
                            <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center text-muted-foreground shrink-0"><ImageIcon className="w-4 h-4 opacity-20"/></div>
                          )}
                          <div className="flex-1 min-w-0 flex flex-col gap-0.5 justify-center py-0.5">
                            <span className="text-sm font-semibold text-foreground leading-tight truncate block" title={svc.name}>{svc.name}</span>
                            <div className="text-xs text-muted-foreground mt-0.5">${svc.price} &bull; {svc.duration} mins</div>
                          </div>
                          <div className="absolute top-0 right-0 h-full flex flex-col justify-between items-end pb-0.5 pr-0.5">
                            <div 
                              className="cursor-grab active:cursor-grabbing text-muted-foreground/45 hover:text-muted-foreground p-0.5"
                              onClick={e => e.stopPropagation()}
                            >
                              <GripVertical className="w-3.5 h-3.5" />
                            </div>
                            <div className="flex items-center gap-0.5" onClick={e => e.stopPropagation()}>
                              <button 
                                onClick={() => handleToggleActive(svc)} 
                                className="p-0.5 hover:bg-muted rounded transition-colors"
                                title={svc.active ? 'Deactivate service' : 'Activate service'}
                              >
                                {svc.active ? (
                                  <Circle className="w-3.5 h-3.5 fill-emerald-500 text-emerald-500" />
                                ) : (
                                  <CircleSlash className="w-3.5 h-3.5 text-rose-500" />
                                )}
                              </button>
                              <button 
                                disabled={!svc.active}
                                onClick={() => svc.active && updateServiceQuick(svc.id, { is_visible: !svc.is_visible })} 
                                className={`p-0.5 rounded transition-colors ${svc.active ? 'hover:bg-muted' : 'opacity-30 cursor-not-allowed'}`}
                                title={!svc.active ? 'Deactivated' : (svc.is_visible ? 'Hide' : 'Show')}
                              >
                                {svc.is_visible && svc.active ? (
                                  <Eye className="w-3.5 h-3.5 text-emerald-500" />
                                ) : (
                                  <EyeOff className="w-3.5 h-3.5 text-muted-foreground" />
                                )}
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              
              {uncategorizedServices.length > 0 && (
                <div className="space-y-2">
                  <h3 
                    className="text-sm font-semibold text-muted-foreground uppercase tracking-wider pl-6 cursor-pointer hover:text-primary transition-colors"
                    onClick={() => setOpenSection('categories')}
                  >
                    Uncategorized
                  </h3>
                  <div className={isListView ? "space-y-2" : "grid grid-cols-2 gap-2"}>
                    {uncategorizedServices.map(svc => (
                      <div 
                        key={`uncat-${svc.id}`}
                        draggable
                        onDragStart={(e) => handleDragStartService(e, svc.id)}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => handleDropService(e, svc.id)}
                        onClick={() => {
                          setRightPaneType("service");
                          handleSelectService(svc);
                        }}
                        className={`p-3 rounded-xl hover:scale-[1.01] hover:shadow-md flex flex-col justify-center border transition-all duration-200 cursor-pointer ${
                          selectedServiceId === svc.id 
                            ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20' 
                            : 'border-border bg-card/50 hover:bg-muted/30 hover:border-border/60 dark:bg-card dark:border-border/60'
                        }`}
                      >
                        <div className="flex gap-3 items-start min-w-0 w-full relative pr-[56px]">
                          {svc.image ? (
                            <img src={svc.image} alt={svc.name} className="w-10 h-10 object-cover rounded-lg shrink-0" />
                          ) : (
                            <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center text-muted-foreground shrink-0"><ImageIcon className="w-4 h-4 opacity-20"/></div>
                          )}
                          <div className="flex-1 min-w-0 flex flex-col gap-0.5 justify-center py-0.5">
                            <span className="text-sm font-semibold text-foreground leading-tight truncate block" title={svc.name}>{svc.name}</span>
                            <div className="text-xs text-muted-foreground mt-0.5">${svc.price} &bull; {svc.duration} mins</div>
                          </div>
                          <div className="absolute top-0 right-0 h-full flex flex-col justify-between items-end pb-0.5 pr-0.5">
                            <div 
                              className="cursor-grab active:cursor-grabbing text-muted-foreground/45 hover:text-muted-foreground p-0.5"
                              onClick={e => e.stopPropagation()}
                            >
                              <GripVertical className="w-3.5 h-3.5" />
                            </div>
                            <div className="flex items-center gap-0.5" onClick={e => e.stopPropagation()}>
                              <button 
                                onClick={() => handleToggleActive(svc)} 
                                className="p-0.5 hover:bg-muted rounded transition-colors"
                                title={svc.active ? 'Deactivate service' : 'Activate service'}
                              >
                                {svc.active ? (
                                  <Circle className="w-3.5 h-3.5 fill-emerald-500 text-emerald-500" />
                                ) : (
                                  <CircleSlash className="w-3.5 h-3.5 text-rose-500" />
                                )}
                              </button>
                              <button 
                                disabled={!svc.active}
                                onClick={() => svc.active && updateServiceQuick(svc.id, { is_visible: !svc.is_visible })} 
                                className={`p-0.5 rounded transition-colors ${svc.active ? 'hover:bg-muted' : 'opacity-30 cursor-not-allowed'}`}
                                title={!svc.active ? 'Deactivated' : (svc.is_visible ? 'Hide' : 'Show')}
                              >
                                {svc.is_visible && svc.active ? (
                                  <Eye className="w-3.5 h-3.5 text-emerald-500" />
                                ) : (
                                  <EyeOff className="w-3.5 h-3.5 text-muted-foreground" />
                                )}
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Right Pane - Detail / Form */}
      <div className={`md:w-[65%] flex flex-col md:pl-4 transition-all duration-300 h-full ${(selectedServiceId || isCreating || (rightPaneType === "category" && (selectedCategoryId || isCategoryCreating))) ? 'flex w-full absolute inset-0 z-50 bg-background md:relative md:z-auto' : 'hidden md:flex'}`}>
        {rightPaneType === "category" ? (
          !selectedCategoryId && !isCategoryCreating ? (
            <div className="flex-1 flex items-center justify-center text-muted-foreground bg-card/10 rounded-xl border border-dashed p-8">
              Select a category to view details or create a new one.
            </div>
          ) : isCategoryCreating || isCategoryEditing ? (
            <Card className="flex-1 flex flex-col h-full overflow-hidden border-0 shadow-none py-0 gap-0">
              <CardHeader className="flex flex-row items-center justify-between shrink-0 bg-background z-10 border-b p-4 md:pb-4 sticky top-0">
                <div className="flex items-center gap-3">
                  <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={() => { setIsCategoryCreating(false); setIsCategoryEditing(false); }}>
                    <ArrowLeft className="w-5 h-5" />
                  </Button>
                  <div>
                    <CardTitle className="text-2xl font-bold font-heading">
                      {isCategoryCreating ? 'Add New Category' : 'Edit Category'}
                    </CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                      {isCategoryCreating ? 'Create a new service category' : 'Update category details'}
                    </p>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto p-6 space-y-6">
                <div className="space-y-2">
                  <Label className="text-base font-semibold">Category Name *</Label>
                  <Input 
                    value={categoryFormData.name}
                    onChange={e => setCategoryFormData({ ...categoryFormData, name: e.target.value })}
                    placeholder="e.g. Massages, Facials"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-base font-semibold">Description</Label>
                  <Textarea 
                    value={categoryFormData.description}
                    onChange={e => setCategoryFormData({ ...categoryFormData, description: e.target.value })}
                    placeholder="Describe the category..."
                    rows={4}
                  />
                </div>
                <div className="flex items-center space-x-2 pt-2">
                  <Switch 
                    id="category-active" 
                    checked={categoryFormData.active}
                    onCheckedChange={checked => setCategoryFormData({ ...categoryFormData, active: checked })}
                  />
                  <Label htmlFor="category-active" className="text-base font-semibold cursor-pointer">Active Status</Label>
                </div>
              </CardContent>
              <CardFooter className="flex justify-end gap-2 border-t p-4 md:pt-4 mt-auto shrink-0 sticky bottom-0 bg-background z-10 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.1)] md:shadow-none">
                <Button variant="outline" onClick={() => { setIsCategoryCreating(false); setIsCategoryEditing(false); }} className="min-h-[44px]">Cancel</Button>
                <Button onClick={handleSaveCategory} className="min-h-[44px]">Save</Button>
              </CardFooter>
            </Card>
          ) : (
            <Card className="flex-1 flex flex-col h-full overflow-hidden shadow-none md:shadow-sm border-0 md:border py-0 gap-0">
              <CardHeader className="flex flex-row items-center justify-between shrink-0 bg-background z-10 border-b sticky top-0 p-4 md:p-6">
                <div className="flex items-center gap-3 flex-1">
                  <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={() => setSelectedCategoryId(null)}>
                    <ArrowLeft className="w-5 h-5" />
                  </Button>
                  <div className="flex-1">
                    <CardTitle className="text-xl font-heading">Category Details</CardTitle>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setIsCategoryEditing(true)} className="min-h-[44px]">
                    <Edit className="w-4 h-4 md:mr-2" /> <span className="hidden md:inline">Edit</span>
                  </Button>
                  <Button variant="destructive" size="sm" onClick={handleDeleteCategory} className="min-h-[44px]">
                    <Trash2 className="w-4 h-4 md:mr-2" /> <span className="hidden md:inline">Delete</span>
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto p-6 space-y-6">
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Category Name</div>
                  <div className="text-xl font-bold flex items-center gap-3">
                    {categoryFormData.name}
                    <Badge variant={categoryFormData.active ? "default" : "secondary"}>
                      {categoryFormData.active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                </div>
                <div className="space-y-1 pt-2">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Description</div>
                  <div className="text-sm bg-muted/20 p-3 rounded-lg border min-h-[80px] whitespace-pre-wrap">
                    {categoryFormData.description || <span className="text-muted-foreground italic">No description provided.</span>}
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        ) : (
          !selectedServiceId && !isCreating ? (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              Select a service to view details or create a new one.
            </div>
          ) : isCreating ? (
            <Card className="flex-1 flex flex-col h-full overflow-hidden border-0 shadow-none py-0 gap-0">
              <CardHeader className="flex flex-row items-center justify-between shrink-0 bg-background z-10 border-b p-4 md:pb-4 sticky top-0">
                <div className="flex items-center gap-3">
                  <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={handleCancel}>
                    <ArrowLeft className="w-5 h-5" />
                  </Button>
                  <div>
                    <CardTitle className="text-2xl font-bold font-heading">Add New Service</CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">Create a new service offering for your clients</p>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto p-6 space-y-6">
                <div className="space-y-2">
                  <Label className="text-base font-semibold">Service Name</Label>
                  <Input 
                    value={formData.name}
                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g. Signature Massage"
                  />
                  <p className="text-sm text-muted-foreground">This will be displayed to clients when booking</p>
                </div>
                <div className="space-y-2">
                  <Label className="text-base font-semibold">Description</Label>
                  <Textarea 
                    value={formData.description}
                    onChange={e => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Describe the service..."
                    rows={4}
                  />
                  <p className="text-sm text-muted-foreground">Provide details about what clients can expect</p>
                </div>
                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label className="text-base font-semibold">Duration (mins)</Label>
                    <div className="relative">
                      <Clock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                      <Input 
                        type="number"
                        className="pl-9"
                        value={formData.duration}
                        onChange={e => setFormData({ ...formData, duration: parseInt(e.target.value) || 0 })}
                      />
                    </div>
                    <p className="text-sm text-muted-foreground">How long the service takes</p>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-base font-semibold">Price ($)</Label>
                    <div className="relative">
                      <span className="absolute left-3 top-2.5 text-muted-foreground text-sm font-medium">$</span>
                      <Input 
                        type="number"
                        className="pl-7"
                        value={formData.price}
                        onChange={e => setFormData({ ...formData, price: parseFloat(e.target.value) || 0 })}
                      />
                    </div>
                    <p className="text-sm text-muted-foreground">The cost of this service</p>
                  </div>
                </div>
              </CardContent>
              <CardFooter className="flex justify-end gap-2 border-t p-4 md:pt-4 mt-auto shrink-0 sticky bottom-0 bg-background z-10 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.1)] md:shadow-none">
                <Button variant="outline" onClick={handleCancel} className="min-h-[44px]">Cancel</Button>
                <Button onClick={handleSave} className="min-h-[44px]">Save</Button>
              </CardFooter>
            </Card>
          ) : (
            <Card className="flex-1 flex flex-col h-full overflow-hidden shadow-none md:shadow-sm border-0 md:border py-0 gap-0">
              <CardHeader className="flex flex-row items-center justify-between shrink-0 bg-background z-10 border-b sticky top-0 p-4 md:p-6">
                <div className="flex items-center gap-3 flex-1">
                  <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={handleCancel}>
                    <ArrowLeft className="w-5 h-5" />
                  </Button>
                  <div className="flex-1">
                    <CardTitle className="text-xl font-heading">Service Details</CardTitle>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {rightPaneType === "service" && selectedServiceId && (
                    <AutoSaveStatus state={saveState} onRetry={retry} />
                  )}
                  <Button variant="destructive" size="sm" onClick={() => handleDelete(selectedServiceId!)} className="min-h-[44px]">
                    <Trash2 className="w-4 h-4 md:mr-2" /> <span className="hidden md:inline">Delete</span>
                  </Button>
                </div>
              </CardHeader>
              
              <CardContent className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 md:space-y-6">
                <Accordion 
                  type="single" 
                  collapsible 
                  className="w-full space-y-2" 
                  value={openSection} 
                  onValueChange={(val) => setOpenSection(val || 'details')}
                >
                  <AccordionItem value="details" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="hover:no-underline">Service Details</AccordionTrigger>
                    <AccordionContent className="space-y-4 pt-2 pb-4">
                      <div className="space-y-2">
                        <Label htmlFor="service_name">Service Name *</Label>
                        <Input 
                          id="service_name" 
                          value={formData.name} 
                          onChange={(e) => {
                            const next = { ...formData, name: e.target.value };
                            setFormData(next);
                            triggerSave(next);
                          }}
                          disabled={!isEditing}
                          placeholder="e.g. Signature Massage"
                          className="min-h-[44px]"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Image</Label>
                        <ImageUpload 
                          imagePreview={formData.image} 
                          onImageSelect={(file) => {
                            const next = { ...formData, image: file };
                            setFormData(next);
                            triggerSave(next, true);
                          }} 
                          onImageRemove={() => {
                            const next = { ...formData, image: null };
                            setFormData(next);
                            triggerSave(next, true);
                          }} 
                          disabled={!isEditing} 
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="description">Description</Label>
                        <Textarea 
                          id="description" 
                          value={formData.description} 
                          onChange={(e) => {
                            const next = { ...formData, description: e.target.value };
                            setFormData(next);
                            triggerSave(next);
                          }}
                          disabled={!isEditing}
                          placeholder="Detailed description of the service..."
                          rows={3}
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="price">Price</Label>
                          <Input 
                            id="price" 
                            type="number"
                            value={formData.price} 
                            onChange={(e) => {
                              const val = parseFloat(e.target.value) || 0;
                              const next = { ...formData, price: val };
                              setFormData(next);
                              triggerSave(next);
                            }}
                            disabled={!isEditing}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="deposit_amount">Deposit Amount</Label>
                          <Input 
                            id="deposit_amount" 
                            type="number"
                            value={formData.deposit_amount} 
                            onChange={(e) => {
                              const val = parseFloat(e.target.value) || 0;
                              const next = { ...formData, deposit_amount: val };
                              setFormData(next);
                              triggerSave(next);
                            }}
                            disabled={!isEditing}
                          />
                        </div>
                        <div className="space-y-2 col-span-2">
                          <Label htmlFor="tax_rate_id">Tax Rate</Label>
                          <Select 
                            disabled={!isEditing} 
                            value={formData.tax_rate_id || "none"}
                            onValueChange={(val) => {
                              const next = { ...formData, tax_rate_id: val === "none" ? null : val };
                              setFormData(next);
                              triggerSave(next, true);
                            }}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select tax rate" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="none">None</SelectItem>
                              <SelectItem value="gst_10">GST 10%</SelectItem>
                              <SelectItem value="gst_free">GST-free</SelectItem>
                              <SelectItem value="pst_5">PST 5%</SelectItem>
                              <SelectItem value="hst_13">HST 13%</SelectItem>
                            </SelectContent>
                          </Select>
                          <p className="text-[10px] text-muted-foreground">Tax rates are configured in Settings &gt; Tax Rates</p>
                        </div>
                      </div>

                      <div className="grid grid-cols-3 gap-4 pt-4 border-t">
                        <div className="space-y-2">
                          <Label htmlFor="duration">Duration (mins)</Label>
                          <Input 
                            id="duration" 
                            type="number"
                            value={formData.duration} 
                            onChange={(e) => {
                              const val = parseInt(e.target.value) || 0;
                              const next = { ...formData, duration: val };
                              setFormData(next);
                              triggerSave(next);
                            }}
                            disabled={!isEditing}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="buffer_before">Buffer Before (mins)</Label>
                          <Input 
                            id="buffer_before" 
                            type="number"
                            value={formData.buffer_before} 
                            onChange={(e) => {
                              const val = parseInt(e.target.value) || 0;
                              const next = { ...formData, buffer_before: val };
                              setFormData(next);
                              triggerSave(next);
                            }}
                            disabled={!isEditing}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="buffer_after">Buffer After (mins)</Label>
                          <Input 
                            id="buffer_after" 
                            type="number"
                            value={formData.buffer_after} 
                            onChange={(e) => {
                              const val = parseInt(e.target.value) || 0;
                              const next = { ...formData, buffer_after: val };
                              setFormData(next);
                              triggerSave(next);
                            }}
                            disabled={!isEditing}
                          />
                        </div>
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* Service Schedule */}
                  <AccordionItem value="fixed_times" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="hover:no-underline">Service Schedule</AccordionTrigger>
                    <AccordionContent className="space-y-6 pt-2 pb-4">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold text-sm">Fixed Start Times</h4>
                          {isEditing && (
                            <button
                              type="button"
                              onClick={() => {
                                const next = { ...formData, fixed_start_times: '' };
                                setFormData(next);
                                triggerSave(next, true);
                              }}
                              className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
                            >
                              Clear all
                            </button>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-1 max-h-[300px] overflow-y-auto pr-0.5">
                          {HALF_HOUR_SLOTS.map((slot) => {
                            const selectedSlots = parseSelectedSlots(formData.fixed_start_times);
                            const isSelected = selectedSlots.includes(slot);
                            return (
                              <button
                                key={slot}
                                type="button"
                                disabled={!isEditing}
                                onClick={() => {
                                  const current = parseSelectedSlots(formData.fixed_start_times);
                                  const updated = isSelected
                                    ? current.filter(s => s !== slot)
                                    : [...current, slot];
                                  // Store as 24h comma string for backend compatibility
                                  const csv = updated.map(to24h).join(', ');
                                  const next = { ...formData, fixed_start_times: csv };
                                  setFormData(next);
                                  triggerSave(next, true);
                                }}
                                className={`w-full py-0.5 rounded-md text-[9px] font-medium border transition-colors ${
                                  isSelected && isEditing
                                    ? 'bg-primary text-primary-foreground border-primary'
                                    : 'bg-muted/10 text-muted-foreground border-border/20'
                                } disabled:opacity-50 disabled:cursor-not-allowed`}
                              >
                                {slot}
                              </button>
                            );
                          })}
                        </div>
                        {formData.fixed_start_times && (
                          <p className="text-[10px] text-muted-foreground">
                            {parseSelectedSlots(formData.fixed_start_times).length} time{parseSelectedSlots(formData.fixed_start_times).length !== 1 ? 's' : ''} selected
                          </p>
                        )}
                      </div>

                      <div className="space-y-4 pt-4 border-t">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold text-sm">Groups</h4>
                          <div className="flex items-center space-x-2">
                            <Switch 
                              checked={formData.has_groups} 
                              onCheckedChange={(c) => {
                                const next = { ...formData, has_groups: c };
                                setFormData(next);
                                triggerSave(next, true);
                              }}
                              disabled={!isEditing}
                            />
                            <Label>Enable Groups</Label>
                          </div>
                        </div>
                        {formData.has_groups && (
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                              <Label htmlFor="min_group_size">Min Group Size</Label>
                              <Input 
                                id="min_group_size" 
                                type="number"
                                value={formData.min_group_size} 
                                onChange={(e) => {
                                  const val = parseInt(e.target.value) || 1;
                                  const next = { ...formData, min_group_size: val };
                                  setFormData(next);
                                  triggerSave(next);
                                }}
                                disabled={!isEditing}
                              />
                            </div>
                            <div className="space-y-2">
                              <Label htmlFor="max_group_size">Max Group Size</Label>
                              <Input 
                                id="max_group_size" 
                                type="number"
                                value={formData.max_group_size} 
                                onChange={(e) => {
                                  const val = parseInt(e.target.value) || 1;
                                  const next = { ...formData, max_group_size: val };
                                  setFormData(next);
                                  triggerSave(next);
                                }}
                                disabled={!isEditing}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {/* Service Categories */}
                  <AccordionItem value="categories" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="hover:no-underline">Service Categories</AccordionTrigger>
                    <AccordionContent className="pt-2 pb-4 space-y-3">
                      {categories.length === 0 && (
                        <p className="text-sm text-muted-foreground">No categories available.</p>
                      )}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {categories.map(c => {
                          const isLinked = formData.category_ids.includes(c.id);
                          return (
                            <div
                              key={c.id}
                              className={`flex items-center gap-2.5 p-2.5 rounded-lg border transition-colors ${
                                isLinked ? 'border-primary bg-primary/5 ring-1 ring-primary/20' : 'border-border bg-card/50'
                              }`}
                            >
                              {c.image ? (
                                <img src={c.image} alt={c.name} className="w-8 h-8 object-cover rounded-md shrink-0" />
                              ) : (
                                <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
                                  <span className="text-xs font-bold text-primary">{c.name[0]?.toUpperCase()}</span>
                                </div>
                              )}
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{c.name}</p>
                                {c.description && <p className="text-[10px] text-muted-foreground truncate">{c.description}</p>}
                              </div>
                              <Switch
                                checked={isLinked}
                                disabled={!isEditing}
                                onCheckedChange={(checked) => {
                                  const current = formData.category_ids || [];
                                  const updated = checked ? [...current, c.id] : current.filter(id => id !== c.id);
                                  const next = { ...formData, category_ids: updated };
                                  setFormData(next);
                                  triggerSave(next, true);
                                }}
                              />
                            </div>
                          );
                        })}
                      </div>
                      {isEditing && (
                        <Button variant="outline" size="sm" onClick={() => handleSaveAndNavigate('/admin/catalog/categories', 'categories')}>
                          <Plus className="w-4 h-4 mr-2" /> Add Category
                        </Button>
                      )}
                    </AccordionContent>
                  </AccordionItem>

                  {/* Service Providers */}
                  <AccordionItem value="providers" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="hover:no-underline">Service Providers</AccordionTrigger>
                    <AccordionContent className="pt-2 pb-4 space-y-3">
                      <p className="text-xs text-muted-foreground italic">
                        Note: If no providers are selected, this service will be available with all providers by default.
                      </p>
                      {providers.length === 0 && (
                        <p className="text-sm text-muted-foreground">No providers available.</p>
                      )}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {providers.map(p => {
                          const isLinked = formData.provider_ids.includes(p.id);
                          return (
                            <div
                              key={p.id}
                              className={`flex items-center gap-2.5 p-2.5 rounded-lg border transition-colors ${
                                isLinked ? 'border-primary bg-primary/5 ring-1 ring-primary/20' : 'border-border bg-card/50'
                              }`}
                            >
                              <Avatar className="h-8 w-8 shrink-0 border" style={{ backgroundColor: p.color || '#e2e8f0' }}>
                                <AvatarImage src={p.avatar || p.image} alt={p.name} className="object-cover" />
                                <AvatarFallback className="text-xs font-bold bg-transparent text-white">
                                  {p.name ? p.name[0].toUpperCase() : 'P'}
                                </AvatarFallback>
                              </Avatar>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{p.name}</p>
                                {p.email && <p className="text-[10px] text-muted-foreground truncate">{p.email}</p>}
                              </div>
                              <Switch
                                checked={isLinked}
                                disabled={!isEditing}
                                onCheckedChange={(checked) => {
                                  const current = formData.provider_ids || [];
                                  const updated = checked ? [...current, p.id] : current.filter(id => id !== p.id);
                                  const next = { ...formData, provider_ids: updated };
                                  setFormData(next);
                                  triggerSave(next, true);
                                }}
                              />
                            </div>
                          );
                        })}
                      </div>
                      {isEditing && (
                        <Button variant="outline" size="sm" onClick={() => handleSaveAndNavigate('/admin/catalog/providers', 'providers')}>
                          <Plus className="w-4 h-4 mr-2" /> Add Provider
                        </Button>
                      )}
                    </AccordionContent>
                  </AccordionItem>

                  {/* Products */}
                  <AccordionItem value="products" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="hover:no-underline">Products</AccordionTrigger>
                    <AccordionContent className="pt-2 pb-4 space-y-3">
                      {products.length === 0 && (
                        <p className="text-sm text-muted-foreground">No products available.</p>
                      )}
                      <div className="flex flex-col gap-1 border rounded-lg overflow-hidden divide-y divide-border/40">
                        {products.map(p => (
                          <div key={p.id} className="flex items-center justify-between p-2.5 bg-card/30 hover:bg-muted/10 transition-colors">
                            <Label className="font-normal truncate flex-1">{p.name}</Label>
                            <div className="flex items-center gap-3 shrink-0 pl-4">
                              <span className="text-xs font-medium text-foreground w-14 text-right">${p.price || '0.00'}</span>
                              <Switch
                                checked={formData.product_ids.includes(p.id)}
                                disabled={!isEditing}
                                onCheckedChange={(checked) => {
                                  const current = formData.product_ids || [];
                                  const updated = checked ? [...current, p.id] : current.filter(id => id !== p.id);
                                  const next = { ...formData, product_ids: updated };
                                  setFormData(next);
                                  triggerSave(next, true);
                                }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                      {isEditing && (
                        <Button variant="outline" size="sm" onClick={() => handleSaveAndNavigate('/admin/catalog/products', 'products')}>
                          <Plus className="w-4 h-4 mr-2" /> Add Product
                        </Button>
                      )}
                    </AccordionContent>
                  </AccordionItem>

                  {/* Add-ons */}
                  <AccordionItem value="addons" className="border rounded-lg px-4 bg-card">
                    <AccordionTrigger className="hover:no-underline">Add-ons</AccordionTrigger>
                    <AccordionContent className="pt-2 pb-4 space-y-3">
                      {addons.length === 0 && (
                        <p className="text-sm text-muted-foreground">No add-ons available.</p>
                      )}
                      <div className="flex flex-col gap-1 border rounded-lg overflow-hidden divide-y divide-border/40">
                        {addons.map(a => (
                          <div key={a.id} className="flex items-center justify-between p-2.5 bg-card/30 hover:bg-muted/10 transition-colors">
                            <Label className="font-normal truncate flex-1">{a.name}</Label>
                            <div className="flex items-center gap-3 shrink-0 pl-4">
                              {a.duration != null && a.duration > 0 && <span className="text-xs text-muted-foreground">+{a.duration} mins</span>}
                              <span className="text-xs font-medium text-foreground w-14 text-right">${a.price || '0.00'}</span>
                              <Switch
                                checked={formData.addon_ids.includes(a.id)}
                                disabled={!isEditing}
                                onCheckedChange={(checked) => {
                                  const current = formData.addon_ids || [];
                                  const updated = checked ? [...current, a.id] : current.filter(id => id !== a.id);
                                  const next = { ...formData, addon_ids: updated };
                                  setFormData(next);
                                  triggerSave(next, true);
                                }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                      {isEditing && (
                        <Button variant="outline" size="sm" onClick={() => handleSaveAndNavigate('/admin/catalog/add-ons', 'addons')}>
                          <Plus className="w-4 h-4 mr-2" /> Add Add-on
                        </Button>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
              </CardContent>

              {isCreating && (
                <CardFooter className="flex justify-end gap-2 border-t p-4 md:pt-4 mt-auto shrink-0 sticky bottom-0 bg-background z-10 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.1)] md:shadow-none">
                  <Button variant="outline" onClick={handleCancel} className="min-h-[44px]">Cancel</Button>
                  <Button onClick={handleSave} className="min-h-[44px]">Save</Button>
                </CardFooter>
              )}
            </Card>
        ))
      }</div>

      <Dialog open={newEntityDialog.open} onOpenChange={(o) => setNewEntityDialog({type: '', open: o})}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New {newEntityDialog.type}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Label>Name</Label>
            <Input value={newEntityName} onChange={e => setNewEntityName(e.target.value)} placeholder="Enter name" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNewEntityDialog({type: '', open: false})}>Cancel</Button>
            <Button onClick={handleCreateEntity}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
    </TooltipProvider>
  );
}
