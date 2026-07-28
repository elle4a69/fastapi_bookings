import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Plus, Search, Trash2, Edit, ArrowUp, ArrowDown, Circle, CircleSlash, ArrowLeft, Layers } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from '@/components/ui/card';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { toast } from 'sonner';
import { useAutoSave } from '@/hooks/use-auto-save';
import { AutoSaveStatus } from '@/components/ui/auto-save-status';

interface Service {
  id: string;
  name: string;
}

interface PackageStep {
  id?: string;
  service_id: string;
  offset_days: number;
  price: number;
  active: boolean;
}

interface Package {
  id: string;
  name: string;
  description: string;
  price: number;
  active: boolean;
  steps?: PackageStep[];
}

export default function PackagesPage() {
  const [packages, setPackages] = useState<Package[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  
  const [formData, setFormData] = useState<Omit<Package, 'id'>>({
    name: '',
    description: '',
    price: 0,
    active: true,
    steps: [],
  });

  const { saveState, triggerSave, retry } = useAutoSave({
    onSave: async (updatedData: any) => {
      const targetId = selectedId;
      if (!targetId) return;
      
      const payload: any = {
        name: updatedData.name,
        description: updatedData.description,
        price: updatedData.price,
        active: updatedData.active,
        steps: updatedData.steps,
      };

      try {
        await apiClient.put(`/api/admin/packages/${targetId}`, payload);
        setPackages(prev => prev.map(p => p.id === targetId ? { ...p, ...updatedData, id: targetId } : p));
      } catch (error: any) {
        toast.error(error.message || "Failed to auto-save package");
        throw error;
      }
    },
    debounceMs: 500
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      const [packagesData, servicesData] = await Promise.all([
        apiClient.get<Package[]>('/api/admin/packages'),
        apiClient.get<Service[]>('/api/admin/services')
      ]);
      setPackages(packagesData);
      setServices(servicesData);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateNew = () => {
    setIsCreating(true);
    setIsEditing(true);
    setSelectedId(null);
    setFormData({
      name: '',
      description: '',
      price: 0,
      active: true,
      steps: [],
    });
  };

  const handleSelect = (pkg: Package) => {
    setSelectedId(pkg.id);
    setIsEditing(true);
    setIsCreating(false);
    setFormData({
      name: pkg.name || '',
      description: pkg.description || '',
      price: pkg.price || 0,
      active: pkg.active ?? true,
      steps: pkg.steps ? [...pkg.steps] : [],
    });
  };

  const handleSave = async () => {
    if (!formData.name) {
      toast.error('Name is required');
      return;
    }
    
    try {
      if (isCreating) {
        await apiClient.post('/api/admin/packages', formData);
        toast.success('Package created successfully');
      } else if (selectedId) {
        await apiClient.put(`/api/admin/packages/${selectedId}`, formData);
        toast.success('Package updated successfully');
      }
      setIsEditing(false);
      setIsCreating(false);
      fetchData();
    } catch (error) {
      toast.error('Failed to save package');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this package?')) return;
    try {
      await apiClient.delete(`/api/admin/packages/${id}`);
      toast.success('Package deleted');
      if (selectedId === id) {
        setSelectedId(null);
        setIsEditing(false);
        setIsCreating(false);
      }
      fetchData();
    } catch (error) {
      toast.error('Failed to delete package');
    }
  };

  const addStep = () => {
    const currentSteps = formData.steps || [];
    const nextSteps = [
      ...currentSteps,
      {
        service_id: '',
        offset_days: 0,
        price: 0,
        active: true
      }
    ];
    const nextData = { ...formData, steps: nextSteps };
    setFormData(nextData);
    if (selectedId) {
      triggerSave(nextData, true);
    }
  };

  const removeStep = (index: number) => {
    const currentSteps = formData.steps || [];
    const newSteps = [...currentSteps];
    newSteps.splice(index, 1);
    const nextData = { ...formData, steps: newSteps };
    setFormData(nextData);
    if (selectedId) {
      triggerSave(nextData, true);
    }
  };

  const updateStep = (index: number, field: keyof PackageStep, value: any) => {
    const currentSteps = formData.steps || [];
    const newSteps = [...currentSteps];
    newSteps[index] = { ...newSteps[index], [field]: value };
    const nextData = { ...formData, steps: newSteps };
    setFormData(nextData);
    if (selectedId) {
      const immediate = field === 'service_id' || field === 'active';
      triggerSave(nextData, immediate);
    }
  };

  const moveStep = (index: number, direction: 'up' | 'down') => {
    const currentSteps = formData.steps || [];
    if (direction === 'up' && index === 0) return;
    if (direction === 'down' && index === currentSteps.length - 1) return;
    
    const newSteps = [...currentSteps];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    
    const temp = newSteps[index];
    newSteps[index] = newSteps[targetIndex];
    newSteps[targetIndex] = temp;
    
    const nextData = { ...formData, steps: newSteps };
    setFormData(nextData);
    if (selectedId) {
      triggerSave(nextData, true);
    }
  };

  const filteredPackages = packages.filter(p => p.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="flex flex-col md:flex-row h-[calc(100vh-65px)] font-sans">
      {/* Left Sidebar */}
      <div className={`md:w-[35%] border-r flex flex-col bg-muted/10 transition-all duration-300 ${selectedId || isCreating ? 'hidden md:flex' : 'flex w-full'}`}>
        <div className="p-4 border-b flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold font-heading">Packages</h2>
            <Button size="sm" onClick={handleCreateNew} className="min-h-[44px] px-4">
              <Plus className="h-4 w-4 mr-2" />
              New Package
            </Button>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-3.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search packages..."
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
          ) : filteredPackages.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground text-sm">
              No packages found.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-1 gap-3">
              {filteredPackages.map((pkg) => (
                <div
                  key={pkg.id}
                  onClick={() => handleSelect(pkg)}
                  className={`p-3 rounded-xl cursor-pointer border transition-all duration-200 hover:scale-[1.01] hover:shadow-md flex justify-between items-center ${
                    selectedId === pkg.id 
                      ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20' 
                      : 'border-border bg-card/50 hover:bg-muted/30 hover:border-border/60 dark:bg-card dark:border-border/60'
                  }`}
                >
                  <div className="flex gap-3 items-start min-w-0 w-full relative pr-[56px]">
                    <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center text-muted-foreground shrink-0">
                      <Layers className="w-4 h-4 opacity-35" />
                    </div>
                    <div className="flex-1 min-w-0 flex flex-col gap-0.5 justify-center py-0.5">
                      <span className="text-sm font-semibold text-foreground leading-tight truncate block text-left" title={pkg.name}>{pkg.name}</span>
                      <div className="text-xs text-muted-foreground mt-0.5 text-left">${pkg.price} &bull; {pkg.steps?.length || 0} steps</div>
                    </div>
                    <div className="absolute top-0 right-0 h-full flex flex-col justify-between items-end pb-0.5 pr-0.5">
                      <div className="flex items-center gap-0.5" onClick={e => e.stopPropagation()}>
                        <button 
                          onClick={() => {
                            const nextActive = !pkg.active;
                            setPackages(prev => prev.map(p => p.id === pkg.id ? { ...p, active: nextActive } : p));
                            apiClient.put(`/api/admin/packages/${pkg.id}`, { ...pkg, active: nextActive }).catch(() => {});
                          }} 
                          className="p-0.5 hover:bg-muted rounded transition-colors"
                          title={pkg.active ? 'Deactivate package' : 'Activate package'}
                        >
                          {pkg.active ? (
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
            <p>Select a package to view details or create a new one.</p>
            <Button variant="outline" className="mt-4" onClick={handleCreateNew}>
              Create New Package
            </Button>
          </div>
        ) : (
          <Card className="max-w-3xl w-full mx-auto shadow-none md:shadow-sm border-0 md:border min-h-full md:min-h-0 rounded-none md:rounded-xl flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between sticky top-0 bg-background z-10 border-b md:border-none p-4 md:p-6 shrink-0">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={() => { setSelectedId(null); setIsCreating(false); setIsEditing(false); }}>
                  <ArrowLeft className="w-5 h-5" />
                </Button>
                <div>
                  <CardTitle className="font-heading text-xl">{isCreating ? 'New Package' : 'Package Details'}</CardTitle>
                  <CardDescription className="hidden md:block">
                    {isCreating ? 'Create a multi-service package' : 'Manage package settings'}
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
            <CardContent className="space-y-6 p-4 md:p-6 flex-1 overflow-auto bg-background">
              <div className="grid grid-cols-2 gap-4">
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
                    placeholder="e.g. 6-Month Care Plan"
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
                    placeholder="Describe this package..."
                  />
                </div>
                <div className="space-y-2">
                  <Label>Total Package Price ($)</Label>
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
                <div className="flex items-center justify-between p-3 border rounded-lg col-span-2">
                  <div className="space-y-0.5">
                    <Label className="text-base">Active Status</Label>
                    <div className="text-sm text-muted-foreground">
                      Enable or disable this package across the platform.
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

              {/* Package Steps / Services Sequence */}
              <div className="space-y-4 pt-4 border-t">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-base">Services Sequence (Steps)</Label>
                    <p className="text-xs text-muted-foreground mt-0.5">Define services and interval offsets for this package.</p>
                  </div>
                  {isEditing && (
                    <Button type="button" variant="outline" size="sm" onClick={addStep} className="min-h-[44px]">
                      <Plus className="h-4 w-4 mr-2" /> Add Step
                    </Button>
                  )}
                </div>

                <div className="space-y-3">
                  {(formData.steps || []).length === 0 ? (
                    <div className="text-center py-6 border border-dashed rounded-lg text-sm text-muted-foreground">
                      No steps defined yet. Click "Add Step" to begin.
                    </div>
                  ) : (
                    (formData.steps || []).map((step, index) => (
                      <div key={index} className="p-4 border rounded-lg bg-card/40 relative space-y-4">
                        <div className="flex items-center justify-between border-b pb-2">
                          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Step {index + 1}</span>
                          <div className="flex items-center gap-1">
                            <Button 
                              type="button" 
                              variant="ghost" 
                              size="icon" 
                              disabled={index === 0 || !isEditing} 
                              onClick={() => moveStep(index, 'up')}
                              className="h-8 w-8"
                            >
                              <ArrowUp className="h-4 w-4" />
                            </Button>
                            <Button 
                              type="button" 
                              variant="ghost" 
                              size="icon" 
                              disabled={index === (formData.steps || []).length - 1 || !isEditing} 
                              onClick={() => moveStep(index, 'down')}
                              className="h-8 w-8"
                            >
                              <ArrowDown className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>

                        <div className="grid grid-cols-12 gap-3 items-end">
                          <div className="col-span-5 space-y-1">
                            <Label className="text-xs">Service</Label>
                            <Select 
                              disabled={!isEditing} 
                              value={step.service_id} 
                              onValueChange={(val) => updateStep(index, 'service_id', val)}
                            >
                              <SelectTrigger className="h-10">
                                <SelectValue placeholder="Select service" />
                              </SelectTrigger>
                              <SelectContent>
                                {(services || []).map(svc => (
                                  <SelectItem key={svc.id} value={String(svc.id)}>{svc.name}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>

                          <div className="col-span-3 space-y-1">
                            <Label className="text-xs">Interval (Days Offset)</Label>
                            <Input 
                              type="number" 
                              disabled={!isEditing}
                              value={step.offset_days}
                              onChange={(e) => updateStep(index, 'offset_days', parseInt(e.target.value) || 0)}
                            />
                          </div>
                          
                          <div className="col-span-3 space-y-1">
                            <Label className="text-xs">Price ($)</Label>
                            <Input 
                              type="number" 
                              step="0.01"
                              disabled={!isEditing}
                              value={step.price}
                              onChange={(e) => updateStep(index, 'price', parseFloat(e.target.value) || 0)}
                            />
                          </div>

                          <div className="col-span-1 pb-1">
                            <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => removeStep(index)}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </CardContent>
            {isCreating && (
              <CardFooter className="flex justify-end gap-2 border-t p-4 md:pt-4 sticky bottom-0 bg-background z-10 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.1)] md:shadow-none shrink-0">
                <Button variant="ghost" className="min-h-[44px]" onClick={() => {
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
  );
}
