import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Plus, Search, Trash2, Edit, Upload, X, Circle, ImageIcon, ArrowLeft, CircleSlash } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useAutoSave } from '@/hooks/use-auto-save';
import { AutoSaveStatus } from '@/components/ui/auto-save-status';

interface Service {
  id: string;
  name: string;
}

interface AddOn {
  id: string;
  name: string;
  description: string;
  price: number;
  duration: number;
  active: boolean;
  service_ids?: string[];
  image?: string | null;
}

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
    if (file.size > 5 * 1024 * 1024) { toast.error('Image must be under 5MB'); return; }
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

export default function AddOnsPage() {
  const [addOns, setAddOns] = useState<AddOn[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  
  const navigate = useNavigate();
  const location = useLocation();
  
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  
  const [formData, setFormData] = useState<Omit<AddOn, 'id'>>({
    name: '',
    description: '',
    price: 0,
    duration: 0,
    active: true,
    service_ids: [],
    image: null,
  });

  const { saveState, triggerSave, retry } = useAutoSave({
    onSave: async (updatedData: any) => {
      const targetId = selectedId;
      if (!targetId) return;
      
      const payload: any = {
        name: updatedData.name,
        description: updatedData.description,
        price: updatedData.price,
        duration: updatedData.duration,
        active: updatedData.active,
        image: updatedData.image,
      };

      if (updatedData.service_ids && updatedData.service_ids.length > 0) {
        payload.service_id = parseInt(updatedData.service_ids[0]);
      }

      try {
        await apiClient.put(`/api/admin/add-ons/${targetId}`, payload);
        setAddOns(prev => prev.map(a => a.id === targetId ? { ...a, ...updatedData, id: targetId } : a));
      } catch (error: any) {
        toast.error(error.message || "Failed to auto-save add-on");
        throw error;
      }
    },
    debounceMs: 500
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      const [addonsData, servicesData] = await Promise.all([
        apiClient.get<AddOn[]>('/api/admin/add-ons'),
        apiClient.get<any>('/api/admin/services')
      ]);
      setAddOns(addonsData);
      setServices(Array.isArray(servicesData) ? servicesData : (servicesData?.data ?? []));
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    if (location.state?.returnToServiceId) {
      setIsCreating(true);
      setIsEditing(true);
      setSelectedId(null);
      setFormData({
        name: '',
        description: '',
        price: 0,
        duration: 15,
        active: true,
        service_ids: [String(location.state.returnToServiceId)],
        image: null,
      });
    }
  }, [location.state]);

  const handleCreateNew = () => {
    setIsCreating(true);
    setIsEditing(true);
    setSelectedId(null);
    setFormData({
      name: '',
      description: '',
      price: 0,
      duration: 0,
      active: true,
      service_ids: [],
      image: null,
    });
  };

  const handleSelect = (addon: AddOn) => {
    setSelectedId(addon.id);
    setIsEditing(true);
    setIsCreating(false);
    setFormData({
      name: addon.name || '',
      description: addon.description || '',
      price: addon.price || 0,
      duration: addon.duration || 0,
      active: addon.active ?? true,
      service_ids: addon.service_id ? [String(addon.service_id)] : (addon as any).service_ids || [],
      image: addon.image || null,
    });
  };

  const handleSave = async () => {
    if (!formData.name) {
      toast.error('Name is required');
      return;
    }
    
    try {
      const payload: any = {
        name: formData.name,
        description: formData.description,
        price: formData.price,
        duration: formData.duration,
        active: formData.active,
        image: formData.image,
      };

      if (location.state?.returnToServiceId) {
        payload.service_id = parseInt(location.state.returnToServiceId);
      } else if (formData.service_ids && formData.service_ids.length > 0) {
        payload.service_id = parseInt(formData.service_ids[0]);
      }

      if (isCreating) {
        await apiClient.post('/api/admin/add-ons', payload);
        toast.success('Add-on created successfully');
      } else if (selectedId) {
        await apiClient.put(`/api/admin/add-ons/${selectedId}`, payload);
        toast.success('Add-on updated successfully');
      }
      setIsEditing(false);
      setIsCreating(false);
      fetchData();

      if (location.state?.returnToServiceId) {
        navigate('/admin/catalog/services', {
          state: {
            selectServiceId: location.state.returnToServiceId,
            openSection: location.state.section
          }
        });
      }
    } catch (error) {
      toast.error('Failed to save add-on');
    }
  };

  const updateAddonQuick = async (id: string, updates: Partial<AddOn>) => {
    try {
      setAddOns(prev => prev.map(a => a.id === id ? { ...a, ...updates } : a));
      await apiClient.put(`/api/admin/add-ons/${id}`, updates);
      toast.success('Add-on updated');
    } catch {
      toast.error('Failed to update add-on');
      fetchData();
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this add-on?')) return;
    try {
      await apiClient.delete(`/api/admin/add-ons/${id}`);
      toast.success('Add-on deleted');
      if (selectedId === id) {
        setSelectedId(null);
        setIsEditing(false);
        setIsCreating(false);
      }
      fetchData();
    } catch (error) {
      toast.error('Failed to delete add-on');
    }
  };

  const toggleService = (serviceId: string) => {
    const current = (formData.service_ids || []).map(String);
    const target = String(serviceId);
    const nextList = current.includes(target)
      ? current.filter(id => id !== target)
      : [...current, target];
    const nextData = { ...formData, service_ids: nextList };
    setFormData(nextData);
    if (selectedId) {
      triggerSave(nextData, true);
    }
  };
  const filteredAddOns = addOns.filter(a => a.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <TooltipProvider>
    <div className="flex flex-col md:flex-row h-[calc(100vh-65px)] font-sans">
      {/* Left Sidebar */}
      <div className={`md:w-[35%] border-r flex flex-col bg-muted/10 transition-all duration-300 ${selectedId || isCreating ? 'hidden md:flex' : 'flex w-full'}`}>
        <div className="p-4 border-b flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold font-heading">Add-ons</h2>
            <Button size="sm" onClick={handleCreateNew} className="min-h-[44px] px-4">
              <Plus className="h-4 w-4 mr-2" />
              New Add-on
            </Button>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-3.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search add-ons..."
              className="pl-10 min-h-[44px]"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
        
        <div className="flex-1 overflow-auto p-4 pb-20 md:pb-4">
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : filteredAddOns.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground text-sm">
              No add-ons found.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-1 gap-3">
              {filteredAddOns.map((addon) => (
                <div
                  key={addon.id}
                  onClick={() => handleSelect(addon)}
                  className={`p-3 rounded-xl cursor-pointer border transition-all duration-200 hover:scale-[1.01] hover:shadow-md flex justify-between items-center ${
                    selectedId === addon.id 
                      ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20' 
                      : 'border-border bg-card/50 hover:bg-muted/30 hover:border-border/60 dark:bg-card dark:border-border/60'
                  }`}
                >
                  <div className="flex gap-3 items-start min-w-0 w-full relative pr-[56px]">
                    {addon.image ? (
                      <img src={addon.image} alt={addon.name} className="w-10 h-10 object-cover rounded-lg shrink-0" />
                    ) : (
                      <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center text-muted-foreground shrink-0">
                        <ImageIcon className="w-4 h-4 opacity-35" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0 flex flex-col gap-0.5 justify-center py-0.5">
                      <span className="text-sm font-semibold text-foreground leading-tight truncate block text-left" title={addon.name}>{addon.name}</span>
                      <div className="text-xs text-muted-foreground mt-0.5 text-left">${addon.price} &bull; {addon.duration} mins</div>
                    </div>
                    <div className="absolute top-0 right-0 h-full flex flex-col justify-between items-end pb-0.5 pr-0.5">
                      <div className="flex items-center gap-0.5" onClick={e => e.stopPropagation()}>
                        <button 
                          onClick={() => updateAddonQuick(addon.id, { active: !addon.active })} 
                          className="p-0.5 hover:bg-muted rounded transition-colors"
                          title={addon.active ? 'Deactivate add-on' : 'Activate add-on'}
                        >
                          {addon.active ? (
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
          )}
        </div>
      </div>

      {/* Right Content */}
      <div className={`md:w-[65%] flex flex-col bg-background overflow-auto p-0 md:p-6 transition-all duration-300 h-full ${selectedId || isCreating ? 'flex w-full absolute inset-0 z-50 md:relative md:z-auto' : 'hidden md:flex'}`}>
        {(!selectedId && !isCreating) ? (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground">
            <div className="h-16 w-16 bg-muted rounded-full flex items-center justify-center mb-4">
              <Plus className="h-8 w-8 text-muted-foreground/50" />
            </div>
            <p>Select an add-on to view details or create a new one.</p>
            <Button variant="outline" className="mt-4" onClick={handleCreateNew}>
              Create New Add-on
            </Button>
          </div>
        ) : (
          <Card className="max-w-2xl w-full mx-auto shadow-none md:shadow-sm border-0 md:border min-h-full md:min-h-0 rounded-none md:rounded-xl flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between sticky top-0 bg-background z-10 border-b md:border-none p-4 md:p-6 shrink-0">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={() => { setSelectedId(null); setIsCreating(false); setIsEditing(false); }}>
                  <ArrowLeft className="w-5 h-5" />
                </Button>
                <div>
                  <CardTitle className="font-heading text-xl">{isCreating ? 'New Add-on' : 'Add-on Details'}</CardTitle>
                  <CardDescription className="hidden md:block">
                    {isCreating ? 'Create a new add-on for your services' : 'Manage add-on settings'}
                  </CardDescription>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {selectedId && (
                  <AutoSaveStatus state={saveState} onRetry={retry} />
                )}
                <Button variant="destructive" size="sm" onClick={() => selectedId && handleDelete(selectedId)} className="min-h-[44px]">
                  <Trash2 className="h-4 w-4 md:mr-2" />
                  <span className="hidden md:inline">Delete</span>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6 p-4 md:p-6 flex-1 overflow-auto">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2 space-y-2">
                  <Label>Image</Label>
                  <ImageUpload 
                    imagePreview={formData.image || null} 
                    onImageSelect={(file) => {
                      const next = { ...formData, image: file };
                      setFormData(next);
                      if (selectedId) triggerSave(next, true);
                    }} 
                    onImageRemove={() => {
                      const next = { ...formData, image: null };
                      setFormData(next);
                      if (selectedId) triggerSave(next, true);
                    }} 
                    disabled={!isEditing} 
                  />
                </div>
                <div className="col-span-2 space-y-2">
                  <Label>Name</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => {
                      const next = { ...formData, name: e.target.value };
                      setFormData(next);
                      if (selectedId) triggerSave(next);
                    }}
                    disabled={!isEditing}
                    placeholder="e.g. Extra Massage Time"
                  />
                </div>
                <div className="col-span-2 space-y-2">
                  <Label>Description</Label>
                  <Textarea
                    value={formData.description}
                    onChange={(e) => {
                      const next = { ...formData, description: e.target.value };
                      setFormData(next);
                      if (selectedId) triggerSave(next);
                    }}
                    disabled={!isEditing}
                    placeholder="Describe this add-on..."
                  />
                </div>
                <div className="space-y-2">
                  <Label>Price ($)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.price}
                    onChange={(e) => {
                      const next = { ...formData, price: parseFloat(e.target.value) || 0 };
                      setFormData(next);
                      if (selectedId) triggerSave(next);
                    }}
                    disabled={!isEditing}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Duration (mins)</Label>
                  <Input
                    type="number"
                    value={formData.duration}
                    onChange={(e) => {
                      const next = { ...formData, duration: parseInt(e.target.value) || 0 };
                      setFormData(next);
                      if (selectedId) triggerSave(next);
                    }}
                    disabled={!isEditing}
                  />
                </div>
                <div className="col-span-2 flex items-center justify-between p-3 border rounded-lg">
                  <div className="space-y-0.5">
                    <Label className="text-base">Active Status</Label>
                    <div className="text-sm text-muted-foreground">
                      Enable or disable this add-on across the platform.
                    </div>
                  </div>
                  <Switch
                    checked={formData.active}
                    onCheckedChange={(c) => {
                      const next = { ...formData, active: c };
                      setFormData(next);
                      if (selectedId) triggerSave(next, true);
                    }}
                    disabled={!isEditing}
                  />
                </div>
              </div>

              <div className="space-y-3 pt-4 border-t">
                <div className="space-y-1">
                  <Label className="text-base">Associated Services</Label>
                  <p className="text-sm text-muted-foreground">
                    Select which services this add-on can be applied to.
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3 mt-2">
                  {(services || []).map(service => (
                    <div key={service.id} className="flex items-center space-x-2 border p-3 rounded-md">
                      <Checkbox 
                        id={`service-${service.id}`}
                        checked={(formData.service_ids || []).map(String).includes(String(service.id))}
                        onCheckedChange={() => toggleService(String(service.id))}
                        disabled={!isEditing}
                      />
                      <label
                        htmlFor={`service-${service.id}`}
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                      >
                        {service.name}
                      </label>
                    </div>
                  ))}
                  {services.length === 0 && (
                    <div className="text-sm text-muted-foreground col-span-2">No services found.</div>
                  )}
                </div>
              </div>
            </CardContent>
            {isCreating && (
              <CardFooter className="flex justify-end gap-2 border-t p-4 md:pt-4 sticky bottom-0 bg-background z-10 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.1)] md:shadow-none shrink-0">
                <Button variant="ghost" className="min-h-[44px]" onClick={() => {
                  if (location.state?.returnToServiceId) {
                    navigate('/admin/catalog/services', {
                      state: {
                        selectServiceId: location.state.returnToServiceId,
                        openSection: location.state.section
                      }
                    });
                    return;
                  }
                  setIsCreating(false);
                }}>
                  Cancel
                </Button>
                <Button onClick={handleSave} className="min-h-[44px]">
                  Save Changes
                </Button>
              </CardFooter>
            )}
          </Card>
        )}
      </div>
    </div>
    </TooltipProvider>
  );
}
