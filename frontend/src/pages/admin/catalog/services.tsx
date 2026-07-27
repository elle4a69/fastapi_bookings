import { useState, useEffect } from 'react';
import { Plus, Search, Edit, Trash2, GripVertical, Upload, X, Eye, EyeOff, Circle, CircleSlash, ImageIcon, Clock, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate, useLocation } from 'react-router-dom';

import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';

import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';
import { Checkbox } from '@/components/ui/checkbox';
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

interface Category { id: string; name: string; }
interface Provider { id: string; name: string; }
interface Addon { id: string; name: string; }
interface Product { id: string; name: string; }


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
  const [newEntityDialog, setNewEntityDialog] = useState<{type: string, open: boolean}>({type: '', open: false});
  const [newEntityName, setNewEntityName] = useState('');

  const [draggedServiceId, setDraggedServiceId] = useState<string | null>(null);
  const [draggedCategoryId, setDraggedCategoryId] = useState<string | null>(null);

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
    setIsEditing(false);
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
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3.5 md:top-2.5 h-4 w-4 text-muted-foreground" />
            <Input 
              placeholder="Search services..." 
              className="pl-10 min-h-[44px]" 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <Button variant="outline" size="icon" onClick={handleCreateNew} className="min-h-[44px] min-w-[44px] shrink-0" title="Add Service">
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
                  <div className="flex items-center gap-2">
                    <GripVertical className="w-4 h-4 text-muted-foreground cursor-grab active:cursor-grabbing" />
                    <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">{cat.name}</h3>
                  </div>
                  <div className={isListView ? "space-y-2" : "grid grid-cols-2 gap-2"}>
                    {groupedServices[cat.id].map(svc => (
                      <div 
                        key={`${cat.id}-${svc.id}`}
                        draggable
                        onDragStart={(e) => handleDragStartService(e, svc.id)}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => handleDropService(e, svc.id)}
                        onClick={() => handleSelectService(svc)}
                        className={`p-3 rounded-lg cursor-pointer border transition-all duration-150 flex flex-col justify-center min-h-[64px] ${
                          selectedServiceId === svc.id 
                            ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20' 
                            : 'border-border bg-card/50 hover:bg-muted/30 hover:border-border/60 dark:bg-card dark:border-border/60'
                        }`}
                      >
                        <div className="flex gap-3 items-start min-w-0 w-full relative pr-[56px]">
                          {svc.image ? (
                            <img src={svc.image} alt={svc.name} className="w-[48px] h-[48px] object-cover rounded shrink-0" />
                          ) : (
                            <div className="w-[48px] h-[48px] bg-muted rounded flex items-center justify-center text-muted-foreground shrink-0"><ImageIcon className="w-4 h-4 opacity-20"/></div>
                          )}
                          <div className="flex-1 min-w-0 flex flex-col gap-0.5 justify-center py-0.5">
                            <span className="font-semibold text-xs leading-tight truncate block text-foreground" title={svc.name}>{svc.name}</span>
                            <div className="text-[10px] text-muted-foreground">${svc.price} &bull; {svc.duration} mins</div>
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
                  <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider pl-6">Uncategorized</h3>
                  <div className={isListView ? "space-y-2" : "grid grid-cols-2 gap-2"}>
                    {uncategorizedServices.map(svc => (
                      <div 
                        key={`uncat-${svc.id}`}
                        draggable
                        onDragStart={(e) => handleDragStartService(e, svc.id)}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => handleDropService(e, svc.id)}
                        onClick={() => handleSelectService(svc)}
                        className={`p-3 rounded-lg cursor-pointer border transition-all duration-150 flex flex-col justify-center min-h-[64px] ${
                          selectedServiceId === svc.id 
                            ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20' 
                            : 'border-border bg-card/50 hover:bg-muted/30 hover:border-border/60 dark:bg-card dark:border-border/60'
                        }`}
                      >
                        <div className="flex gap-3 items-start min-w-0 w-full relative pr-[56px]">
                          {svc.image ? (
                            <img src={svc.image} alt={svc.name} className="w-[48px] h-[48px] object-cover rounded shrink-0" />
                          ) : (
                            <div className="w-[48px] h-[48px] bg-muted rounded flex items-center justify-center text-muted-foreground shrink-0"><ImageIcon className="w-4 h-4 opacity-20"/></div>
                          )}
                          <div className="flex-1 min-w-0 flex flex-col gap-0.5 justify-center py-0.5">
                            <span className="font-semibold text-xs leading-tight truncate block text-foreground" title={svc.name}>{svc.name}</span>
                            <div className="text-[10px] text-muted-foreground">${svc.price} &bull; {svc.duration} mins</div>
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
      <div className={`md:w-[65%] flex flex-col md:pl-4 transition-all duration-300 h-full ${selectedServiceId || isCreating ? 'flex w-full absolute inset-0 z-50 bg-background md:relative md:z-auto' : 'hidden md:flex'}`}>
        {!selectedServiceId && !isCreating ? (
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
              {!isCreating && !isEditing && (
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setIsEditing(true)} className="min-h-[44px]">
                    <Edit className="w-4 h-4 md:mr-2" /> <span className="hidden md:inline">Edit</span>
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => handleDelete(selectedServiceId!)} className="min-h-[44px]">
                    <Trash2 className="w-4 h-4 md:mr-2" /> <span className="hidden md:inline">Delete</span>
                  </Button>
                </div>
              )}
            </CardHeader>
            
            <CardContent className="flex-1 overflow-y-auto p-4 md:p-6 relative z-0">
              <Accordion 
                type="single" 
                collapsible 
                className="w-full space-y-2" 
                value={openSection} 
                onValueChange={(val) => setOpenSection(val || 'details')}
              >
                {/* 1. Service Details */}
                <AccordionItem value="details" className="border rounded-lg px-4 bg-card">
                  <AccordionTrigger className="hover:no-underline">1. Basic Info</AccordionTrigger>
                  <AccordionContent className="space-y-4 pt-2 pb-4">
                    <div className="space-y-2">
                      <Label htmlFor="service_name">Service Name *</Label>
                      <Input 
                        id="service_name" 
                        value={formData.name} 
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        disabled={!isEditing}
                        placeholder="e.g. Signature Massage"
                        className="min-h-[44px]"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Image</Label>
                      <ImageUpload 
                        imagePreview={formData.image} 
                        onImageSelect={(file) => setFormData({ ...formData, image: file })} 
                        onImageRemove={() => setFormData({ ...formData, image: null })} 
                        disabled={!isEditing} 
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="description">Description</Label>
                      <Textarea 
                        id="description" 
                        value={formData.description} 
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
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
                          onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) || 0 })}
                          disabled={!isEditing}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="deposit_amount">Deposit Amount</Label>
                        <Input 
                          id="deposit_amount" 
                          type="number"
                          value={formData.deposit_amount} 
                          onChange={(e) => setFormData({ ...formData, deposit_amount: parseFloat(e.target.value) || 0 })}
                          disabled={!isEditing}
                        />
                      </div>
                      <div className="space-y-2 col-span-2">
                        <Label htmlFor="tax_rate_id">Tax Rate</Label>
                        <Select 
                          disabled={!isEditing} 
                          value={formData.tax_rate_id || "none"}
                          onValueChange={(val) => setFormData({ ...formData, tax_rate_id: val === "none" ? null : val })}
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
                          onChange={(e) => setFormData({ ...formData, duration: parseInt(e.target.value) || 0 })}
                          disabled={!isEditing}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="buffer_before">Buffer Before (mins)</Label>
                        <Input 
                          id="buffer_before" 
                          type="number"
                          value={formData.buffer_before} 
                          onChange={(e) => setFormData({ ...formData, buffer_before: parseInt(e.target.value) || 0 })}
                          disabled={!isEditing}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="buffer_after">Buffer After (mins)</Label>
                        <Input 
                          id="buffer_after" 
                          type="number"
                          value={formData.buffer_after} 
                          onChange={(e) => setFormData({ ...formData, buffer_after: parseInt(e.target.value) || 0 })}
                          disabled={!isEditing}
                        />
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* 3. Fixed Start Times & Groups */}
                <AccordionItem value="fixed_times" className="border rounded-lg px-4 bg-card">
                  <AccordionTrigger className="hover:no-underline">3. Fixed Start Times &amp; Groups</AccordionTrigger>
                  <AccordionContent className="space-y-6 pt-2 pb-4">
                    <div className="space-y-4">
                      <h4 className="font-semibold text-sm">Fixed Start Times</h4>
                      <div className="space-y-2">
                        <Label htmlFor="fixed_start_times">Times (comma-separated)</Label>
                        <div className="flex gap-2">
                          <Input 
                            id="fixed_start_times" 
                            value={formData.fixed_start_times} 
                            onChange={(e) => setFormData({ ...formData, fixed_start_times: e.target.value })}
                            disabled={!isEditing}
                            placeholder="e.g. 09:00, 13:00, 15:30"
                          />
                          {isEditing && (
                            <Button variant="outline" onClick={() => {
                              const v = window.prompt('Add a time (HH:MM)');
                              if (v) {
                                const current = formData.fixed_start_times.trim();
                                setFormData({ ...formData, fixed_start_times: current ? current + ', ' + v : v });
                              }
                            }}>Add Time</Button>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    <div className="space-y-4 pt-4 border-t">
                      <div className="flex items-center justify-between">
                        <h4 className="font-semibold text-sm">Groups</h4>
                        <div className="flex items-center space-x-2">
                          <Switch 
                            checked={formData.has_groups} 
                            onCheckedChange={(c) => setFormData({ ...formData, has_groups: c })}
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
                              onChange={(e) => setFormData({ ...formData, min_group_size: parseInt(e.target.value) || 1 })}
                              disabled={!isEditing}
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="max_group_size">Max Group Size</Label>
                            <Input 
                              id="max_group_size" 
                              type="number"
                              value={formData.max_group_size} 
                              onChange={(e) => setFormData({ ...formData, max_group_size: parseInt(e.target.value) || 1 })}
                              disabled={!isEditing}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {/* 4. Categories */}
                <AccordionItem value="categories" className="border rounded-lg px-4 bg-card">
                  <AccordionTrigger className="hover:no-underline">4. Categories</AccordionTrigger>
                  <AccordionContent className="pt-2 pb-4 space-y-3">
                    {categories.length > 0 && (
                      <div className="flex flex-col gap-2.5">
                        {categories.map(c => (
                          <div key={c.id} className="flex items-center space-x-2">
                            <Checkbox 
                              id={`cat-${c.id}`} 
                              checked={formData.category_ids.includes(c.id)}
                              onCheckedChange={() => toggleArrayItem('category_ids', c.id)}
                              disabled={!isEditing}
                            />
                            <Label htmlFor={`cat-${c.id}`} className="font-normal">{c.name}</Label>
                          </div>
                        ))}
                      </div>
                    )}
                    {categories.length === 0 && (
                      <p className="text-sm text-muted-foreground">No categories available.</p>
                    )}
                    {isEditing && (
                      <Button variant="outline" size="sm" onClick={() => handleSaveAndNavigate('/admin/catalog/categories', 'categories')}>
                        <Plus className="w-4 h-4 mr-2" /> Add Category
                      </Button>
                    )}
                  </AccordionContent>
                </AccordionItem>

                {/* 5. Providers */}
                <AccordionItem value="providers" className="border rounded-lg px-4 bg-card">
                  <AccordionTrigger className="hover:no-underline">5. Providers</AccordionTrigger>
                  <AccordionContent className="pt-2 pb-4 space-y-3">
                    <p className="text-xs text-muted-foreground italic">
                      Note: If no providers are selected, this service will be available with all providers by default.
                    </p>
                    {providers.length > 0 && (
                      <div className="flex flex-col gap-2.5">
                        {providers.map(p => (
                          <div key={p.id} className="flex items-center space-x-2">
                            <Checkbox 
                              id={`prov-${p.id}`} 
                              checked={formData.provider_ids.includes(p.id)}
                              onCheckedChange={() => toggleArrayItem('provider_ids', p.id)}
                              disabled={!isEditing}
                            />
                            <Label htmlFor={`prov-${p.id}`} className="font-normal">{p.name}</Label>
                          </div>
                        ))}
                      </div>
                    )}
                    {providers.length === 0 && (
                      <p className="text-sm text-muted-foreground">No providers available.</p>
                    )}
                    {isEditing && (
                      <Button variant="outline" size="sm" onClick={() => handleSaveAndNavigate('/admin/catalog/providers', 'providers')}>
                        <Plus className="w-4 h-4 mr-2" /> Add Provider
                      </Button>
                    )}
                  </AccordionContent>
                </AccordionItem>

                {/* 6. Add-ons */}
                <AccordionItem value="addons" className="border rounded-lg px-4 bg-card">
                  <AccordionTrigger className="hover:no-underline">6. Add-ons</AccordionTrigger>
                  <AccordionContent className="pt-2 pb-4 space-y-3">
                    {addons.length > 0 && (
                      <div className="flex flex-col gap-1 border rounded-lg overflow-hidden divide-y divide-border/40">
                        {addons.map(a => (
                          <div key={a.id} className="flex items-center justify-between p-2.5 bg-card/30 hover:bg-muted/10 transition-colors">
                            <div className="flex items-center space-x-2 flex-1 min-w-0">
                              <Checkbox 
                                id={`addon-${a.id}`} 
                                checked={formData.addon_ids.includes(a.id)}
                                onCheckedChange={() => toggleArrayItem('addon_ids', a.id)}
                                disabled={!isEditing}
                              />
                              <Label htmlFor={`addon-${a.id}`} className="font-normal truncate">{a.name}</Label>
                            </div>
                            <div className="flex items-center gap-6 text-xs text-muted-foreground shrink-0 pl-4">
                              <span className="w-20 text-right">{a.duration > 0 ? `+${a.duration} mins` : ''}</span>
                              <span className="w-16 text-right font-medium text-foreground">${a.price || '0.00'}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {addons.length === 0 && (
                      <p className="text-sm text-muted-foreground">No add-ons available.</p>
                    )}
                    {isEditing && (
                      <Button variant="outline" size="sm" onClick={() => handleSaveAndNavigate('/admin/catalog/add-ons', 'addons')}>
                        <Plus className="w-4 h-4 mr-2" /> Add Add-on
                      </Button>
                    )}
                  </AccordionContent>
                </AccordionItem>

                {/* 7. Products */}
                <AccordionItem value="products" className="border rounded-lg px-4 bg-card">
                  <AccordionTrigger className="hover:no-underline">7. Products</AccordionTrigger>
                  <AccordionContent className="pt-2 pb-4 space-y-3">
                    {products.length > 0 && (
                      <div className="flex flex-col gap-1 border rounded-lg overflow-hidden divide-y divide-border/40">
                        {products.map(p => (
                          <div key={p.id} className="flex items-center justify-between p-2.5 bg-card/30 hover:bg-muted/10 transition-colors">
                            <div className="flex items-center space-x-2 flex-1 min-w-0">
                              <Checkbox 
                                id={`prod-${p.id}`} 
                                checked={formData.product_ids.includes(p.id)}
                                onCheckedChange={() => toggleArrayItem('product_ids', p.id)}
                                disabled={!isEditing}
                              />
                              <Label htmlFor={`prod-${p.id}`} className="font-normal truncate">{p.name}</Label>
                            </div>
                            <div className="shrink-0 text-xs font-medium text-foreground pl-4 w-16 text-right">
                              ${p.price || '0.00'}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {products.length === 0 && (
                      <p className="text-sm text-muted-foreground">No products available.</p>
                    )}
                    {isEditing && (
                      <Button variant="outline" size="sm" onClick={() => handleSaveAndNavigate('/admin/catalog/products', 'products')}>
                        <Plus className="w-4 h-4 mr-2" /> Add Product
                      </Button>
                    )}
                  </AccordionContent>
                </AccordionItem>

                {/* 8. Resource Requirements */}
                <AccordionItem value="resources" className="border rounded-lg px-4 bg-card relative z-50">
                  <AccordionTrigger className="hover:no-underline">8. Resource Requirements</AccordionTrigger>
                  <AccordionContent className="space-y-4 pt-2 pb-4 overflow-visible">
                    {formData.requirements.map((req, idx) => (
                      <div key={idx} className="flex gap-2 items-end">
                        <div className="space-y-2 flex-1">
                          <Label>Resource Type</Label>
                          {isEditing ? (
                            <Select 
                              value={req.resource_type} 
                              onValueChange={(val) => updateRequirement(idx, 'resource_type', val)}
                            >
                              <SelectTrigger className="w-full">
                                <SelectValue placeholder={distinctResourceTypes.length > 0 ? "Select resource type" : "No resource types configured"} />
                              </SelectTrigger>
                              <SelectContent>
                                {distinctResourceTypes.map((type) => (
                                  <SelectItem key={type} value={type}>
                                    {type}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          ) : (
                            <Input 
                              value={req.resource_type}
                              disabled={true}
                              placeholder="e.g. Room, Equipment"
                            />
                          )}
                        </div>
                        <div className="space-y-2 w-24">
                          <Label>Qty</Label>
                          <Input 
                            type="number"
                            value={req.quantity}
                            onChange={(e) => updateRequirement(idx, 'quantity', parseInt(e.target.value) || 1)}
                            disabled={!isEditing}
                          />
                        </div>
                        {isEditing && (
                          <Button variant="ghost" size="icon" onClick={() => removeRequirement(idx)} className="text-destructive">
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    ))}
                    {isEditing && (
                      <div className="space-y-3">
                        {distinctResourceTypes.length === 0 && (
                          <p className="text-xs text-amber-600 bg-amber-50 dark:bg-amber-950/30 p-2 rounded border border-amber-200/50">
                            No resource groups found. Please define resource groups on the Resources page first.
                          </p>
                        )}
                        <div className="relative z-50">
                          <Button variant="outline" size="sm" onClick={addRequirementRow} disabled={distinctResourceTypes.length === 0}>
                            <Plus className="w-4 h-4 mr-2" /> Add Requirement
                          </Button>
                        </div>
                      </div>
                    )}
                    {formData.requirements.length === 0 && !isEditing && (
                      <p className="text-sm text-muted-foreground">No resource requirements.</p>
                    )}
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </CardContent>

            {isEditing && (
              <CardFooter className="flex justify-end gap-2 border-t p-4 md:pt-4 mt-auto shrink-0 sticky bottom-0 bg-background z-10 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.1)] md:shadow-none">
                <Button variant="outline" onClick={handleCancel} className="min-h-[44px]">Cancel</Button>
                <Button onClick={handleSave} className="min-h-[44px]">Save</Button>
              </CardFooter>
            )}
          </Card>
        )}
      </div>

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
