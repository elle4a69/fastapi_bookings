import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Plus, Search, Trash2, ArrowLeft, Circle, CircleSlash, Eye, EyeOff, GripVertical, Package as PackageIcon } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { toast } from 'sonner';
import { useAutoSave } from '@/hooks/use-auto-save';
import { AutoSaveStatus } from '@/components/ui/auto-save-status';

interface Service { id: string; name: string; }

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
  is_visible: boolean;
  steps?: PackageStep[];
}

export default function PackagesPage() {
  const [packages, setPackages] = useState<Package[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [draggedId, setDraggedId] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const defaultForm: Omit<Package, 'id'> = { name: '', description: '', price: 0, active: true, is_visible: true, steps: [] };
  const [formData, setFormData] = useState(defaultForm);

  const { saveState, triggerSave, retry } = useAutoSave({
    onSave: async (updatedData: any) => {
      if (!selectedId) return;
      try {
        const res = await apiClient.put<any>(`/api/admin/packages/${selectedId}`, updatedData);
        const dataObj = res?.data || res;
        setPackages(prev => prev.map(p => p.id === selectedId ? { ...p, ...dataObj } : p));
      } catch (error: any) {
        toast.error(error.message || 'Failed to auto-save package');
        throw error;
      }
    },
    debounceMs: 500,
  });

  const updateQuick = async (id: string, updates: Partial<Package>) => {
    try {
      setPackages(prev => prev.map(p => p.id === id ? { ...p, ...updates } : p));
      await apiClient.put(`/api/admin/packages/${id}`, updates);
    } catch {
      toast.error('Failed to update package');
      fetchData();
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const [pkgRes, svcRes] = await Promise.all([
        apiClient.get<any>('/api/admin/packages').catch(() => ({ data: [] })),
        apiClient.get<any>('/api/admin/services').catch(() => ({ data: [] })),
      ]);
      setPackages(Array.isArray(pkgRes) ? pkgRes : (pkgRes?.data ?? []));
      setServices(Array.isArray(svcRes) ? svcRes : (svcRes?.data ?? []));
    } catch {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleSelect = (pkg: Package) => {
    setSelectedId(pkg.id);
    setIsCreating(false);
    setFormData({
      name: pkg.name,
      description: pkg.description || '',
      price: pkg.price || 0,
      active: pkg.active ?? true,
      is_visible: pkg.is_visible ?? true,
      steps: pkg.steps || [],
    });
  };

  const handleSave = async () => {
    if (!formData.name.trim()) { toast.error('Name is required'); return; }
    try {
      if (isCreating) {
        const newPkg = await apiClient.post<Package>('/api/admin/packages', formData);
        setPackages(prev => [...prev, newPkg]);
        toast.success('Package created');
        handleSelect(newPkg);
      } else if (selectedId) {
        const updated = await apiClient.put<Package>(`/api/admin/packages/${selectedId}`, formData);
        setPackages(prev => prev.map(p => p.id === selectedId ? updated : p));
        toast.success('Package updated');
        handleSelect(updated);
      }
    } catch { toast.error('Failed to save package'); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this package?')) return;
    try {
      await apiClient.delete(`/api/admin/packages/${id}`);
      setPackages(prev => prev.filter(p => p.id !== id));
      if (selectedId === id) { setSelectedId(null); setIsCreating(false); }
      toast.success('Package deleted');
    } catch { toast.error('Failed to delete package'); }
  };

  const handleDragStart = (e: React.DragEvent, id: string) => { setDraggedId(id); e.dataTransfer.effectAllowed = 'move'; };
  const handleDrop = (e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    if (!draggedId || draggedId === targetId) return;
    setPackages(prev => {
      const list = [...prev];
      const src = list.findIndex(p => p.id === draggedId);
      const dst = list.findIndex(p => p.id === targetId);
      if (src === -1 || dst === -1) return prev;
      const [moved] = list.splice(src, 1);
      list.splice(dst, 0, moved);
      return list;
    });
    setDraggedId(null);
  };

  const addStep = () => {
    const newStep: PackageStep = { service_id: services[0]?.id || '', offset_days: 0, price: 0, active: true };
    setFormData(prev => ({ ...prev, steps: [...(prev.steps || []), newStep] }));
  };

  const removeStep = (index: number) => {
    setFormData(prev => {
      const steps = [...(prev.steps || [])];
      steps.splice(index, 1);
      return { ...prev, steps };
    });
  };

  const updateStep = (index: number, updates: Partial<PackageStep>) => {
    setFormData(prev => {
      const steps = [...(prev.steps || [])];
      steps[index] = { ...steps[index], ...updates };
      const next = { ...prev, steps };
      if (selectedId) triggerSave(next);
      return next;
    });
  };

  const filtered = packages.filter(p => p.name.toLowerCase().includes(search.toLowerCase()));
  const selectedPackage = packages.find(p => p.id === selectedId);

  return (
    <div className="flex flex-col md:flex-row h-full w-full md:gap-4 overflow-hidden font-sans">
      {/* Left Pane */}
      <div className={`md:w-[35%] flex flex-col gap-4 border-r md:pr-4 transition-all duration-300 ${selectedId || isCreating ? 'hidden md:flex' : 'flex w-full'}`}>
        <div className="flex gap-2 items-center px-4 md:px-0">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3.5 md:top-2.5 h-4 w-4 text-muted-foreground" />
            <Input placeholder="Search packages..." className="pl-10 min-h-[44px]" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <Button variant="outline" size="icon" onClick={() => { setIsCreating(true); setSelectedId(null); setFormData(defaultForm); }} className="min-h-[44px] min-w-[44px] shrink-0" title="Add Package">
            <Plus className="w-5 h-5" />
          </Button>
        </div>

        <div className="flex items-center gap-2 px-4 md:px-0">
          <span className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Packages</span>
          <Badge variant="secondary">{filtered.length}</Badge>
        </div>

        <div className="flex-1 overflow-y-auto space-y-2 pb-12">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)
          ) : filtered.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">No packages found</div>
          ) : (
            filtered.map(pkg => (
              <div
                key={pkg.id}
                draggable
                onDragStart={e => handleDragStart(e, pkg.id)}
                onDragOver={e => e.preventDefault()}
                onDrop={e => handleDrop(e, pkg.id)}
                onClick={() => handleSelect(pkg)}
                className={`p-3 rounded-xl hover:scale-[1.01] hover:shadow-md flex flex-col justify-center border transition-all duration-200 cursor-pointer ${
                  selectedId === pkg.id
                    ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20'
                    : 'border-border bg-card/50 hover:bg-muted/30 hover:border-border/60 dark:bg-card dark:border-border/60'
                }`}
              >
                <div className="flex gap-3 items-start min-w-0 w-full relative pr-[56px]">
                  <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center text-muted-foreground shrink-0">
                    <PackageIcon className="w-4 h-4 opacity-35" />
                  </div>
                  <div className="flex-1 min-w-0 flex flex-col gap-0.5 justify-center py-0.5">
                    <span className="text-sm font-semibold text-foreground leading-tight truncate block text-left" title={pkg.name}>{pkg.name}</span>
                    <div className="text-xs text-muted-foreground mt-0.5 text-left">${pkg.price} &bull; {(pkg.steps || []).length} step{(pkg.steps || []).length !== 1 ? 's' : ''}</div>
                  </div>
                  <div className="absolute top-0 right-0 h-full flex flex-col justify-between items-end pb-0.5 pr-0.5">
                    <div className="cursor-grab active:cursor-grabbing text-muted-foreground/45 hover:text-muted-foreground p-0.5" onClick={e => e.stopPropagation()}>
                      <GripVertical className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex items-center gap-0.5" onClick={e => e.stopPropagation()}>
                      <button onClick={() => updateQuick(pkg.id, { active: !pkg.active, ...(!pkg.active ? {} : { is_visible: false }) })} className="p-0.5 hover:bg-muted rounded transition-colors" title={pkg.active ? 'Deactivate' : 'Activate'}>
                        {pkg.active ? <Circle className="w-3.5 h-3.5 fill-emerald-500 text-emerald-500" /> : <CircleSlash className="w-3.5 h-3.5 text-rose-500" />}
                      </button>
                      <button disabled={!pkg.active} onClick={() => pkg.active && updateQuick(pkg.id, { is_visible: !pkg.is_visible })} className={`p-0.5 rounded transition-colors ${pkg.active ? 'hover:bg-muted' : 'opacity-30 cursor-not-allowed'}`} title={!pkg.active ? 'Deactivated' : (pkg.is_visible ? 'Hide' : 'Show')}>
                        {pkg.is_visible && pkg.active ? <Eye className="w-3.5 h-3.5 text-emerald-500" /> : <EyeOff className="w-3.5 h-3.5 text-muted-foreground" />}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right Pane */}
      <div className={`md:w-[65%] flex flex-col md:pl-4 transition-all duration-300 h-full ${selectedId || isCreating ? 'flex w-full absolute inset-0 z-50 bg-background md:relative md:z-auto' : 'hidden md:flex'}`}>
        {!selectedId && !isCreating ? (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground bg-muted/20">
            <div className="h-16 w-16 bg-muted rounded-full flex items-center justify-center mb-4">
              <Search className="h-8 w-8 opacity-50" />
            </div>
            <p>Select a package from the list or create a new one.</p>
          </div>
        ) : (
          <Card className="flex-1 flex flex-col h-full overflow-hidden border-0 shadow-none py-0 gap-0">
            <CardHeader className="flex flex-row items-center justify-between shrink-0 bg-background z-10 border-b p-4 sticky top-0">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={() => { setSelectedId(null); setIsCreating(false); }}>
                  <ArrowLeft className="w-5 h-5" />
                </Button>
                <div>
                  <CardTitle className="text-2xl font-bold font-heading">{isCreating ? 'New Package' : (selectedPackage?.name || 'Package Details')}</CardTitle>
                  <CardDescription className="mt-1">{isCreating ? 'Create a new service package' : 'Auto-saving changes'}</CardDescription>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {selectedId && <AutoSaveStatus state={saveState} onRetry={retry} />}
                {selectedId && (
                  <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" onClick={() => handleDelete(selectedId)}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </CardHeader>

            <CardContent className="flex-1 overflow-y-auto p-6">
              <Accordion type="multiple" defaultValue={['details', 'status']} className="space-y-3">

                <AccordionItem value="details" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">Package Details</AccordionTrigger>
                  <AccordionContent className="p-6">
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label className="text-base font-semibold">Name *</Label>
                        <Input value={formData.name} onChange={e => { const next = { ...formData, name: e.target.value }; setFormData(next); if (selectedId) triggerSave(next); }} placeholder="e.g. Starter Pack" />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-base font-semibold">Description</Label>
                        <Textarea value={formData.description} onChange={e => { const next = { ...formData, description: e.target.value }; setFormData(next); if (selectedId) triggerSave(next); }} placeholder="Brief description..." rows={3} />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-base font-semibold">Package Price ($)</Label>
                        <Input type="number" min={0} step={0.01} value={formData.price} onChange={e => { const next = { ...formData, price: parseFloat(e.target.value) || 0 }; setFormData(next); if (selectedId) triggerSave(next); }} />
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="steps" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">Package Steps ({(formData.steps || []).length})</AccordionTrigger>
                  <AccordionContent className="p-6">
                    <div className="space-y-3">
                      {(formData.steps || []).map((step, index) => (
                        <div key={index} className="p-4 border rounded-lg bg-card/45 space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-semibold text-muted-foreground">Step {index + 1}</span>
                            <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive hover:text-destructive" onClick={() => removeStep(index)}>
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                          <div className="space-y-2">
                            <Label className="text-xs">Service</Label>
                            <Select value={step.service_id} onValueChange={val => updateStep(index, { service_id: val })}>
                              <SelectTrigger className="h-9"><SelectValue placeholder="Select service" /></SelectTrigger>
                              <SelectContent>
                                {services.map(svc => <SelectItem key={svc.id} value={svc.id}>{svc.name}</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-2">
                              <Label className="text-xs">Offset (days)</Label>
                              <Input type="number" min={0} value={step.offset_days} className="h-9" onChange={e => updateStep(index, { offset_days: parseInt(e.target.value) || 0 })} />
                            </div>
                            <div className="space-y-2">
                              <Label className="text-xs">Price ($)</Label>
                              <Input type="number" min={0} step={0.01} value={step.price} className="h-9" onChange={e => updateStep(index, { price: parseFloat(e.target.value) || 0 })} />
                            </div>
                          </div>
                        </div>
                      ))}
                      <Button variant="outline" size="sm" onClick={addStep} className="w-full" disabled={services.length === 0}>
                        <Plus className="w-4 h-4 mr-2" /> Add Step
                      </Button>
                      {services.length === 0 && <p className="text-xs text-muted-foreground text-center">Create services first to add steps.</p>}
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="status" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">Visibility &amp; Status</AccordionTrigger>
                  <AccordionContent className="p-6">
                    <div className="space-y-4">
                      <div className="flex items-center justify-between p-3 border rounded-lg bg-card/45">
                        <Label htmlFor="pkg-active" className="text-sm font-medium">Active</Label>
                        <Switch id="pkg-active" checked={formData.active} onCheckedChange={checked => { const next = { ...formData, active: checked, ...(!checked ? { is_visible: false } : {}) }; setFormData(next); if (selectedId) triggerSave(next, true); }} />
                      </div>
                      <div className="flex items-center justify-between p-3 border rounded-lg bg-card/45">
                        <Label htmlFor="pkg-visible" className="text-sm font-medium">Visible to clients</Label>
                        <Switch id="pkg-visible" checked={formData.is_visible} disabled={!formData.active} onCheckedChange={checked => { const next = { ...formData, is_visible: checked }; setFormData(next); if (selectedId) triggerSave(next, true); }} />
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

              </Accordion>
            </CardContent>

            {isCreating && (
              <CardFooter className="flex justify-end gap-2 border-t p-4 mt-auto shrink-0 sticky bottom-0 bg-background z-10 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.1)]">
                <Button variant="outline" onClick={() => { setIsCreating(false); setSelectedId(null); }} className="min-h-[44px]">Cancel</Button>
                <Button onClick={handleSave} className="min-h-[44px]">Create Package</Button>
              </CardFooter>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
