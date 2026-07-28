import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Plus, Search, Trash2, ArrowLeft, Circle, CircleSlash, Eye, EyeOff, GripVertical, Gift } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { toast } from 'sonner';
import { useAutoSave } from '@/hooks/use-auto-save';
import { AutoSaveStatus } from '@/components/ui/auto-save-status';

interface Service { id: string; name: string; }

interface AddOn {
  id: string;
  name: string;
  description: string;
  price: number;
  duration: number;
  active: boolean;
  is_visible: boolean;
  service_ids?: string[];
}

export default function AddOnsPage() {
  const [addons, setAddons] = useState<AddOn[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [draggedId, setDraggedId] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const defaultForm = { name: '', description: '', price: 0, duration: 0, active: true, is_visible: true, service_ids: [] as string[] };
  const [formData, setFormData] = useState(defaultForm);

  const { saveState, triggerSave, retry } = useAutoSave({
    onSave: async (updatedData: any) => {
      if (!selectedId) return;
      try {
        const res = await apiClient.put<any>(`/api/admin/add-ons/${selectedId}`, updatedData);
        const dataObj = res?.data || res;
        setAddons(prev => prev.map(a => a.id === selectedId ? { ...a, ...dataObj } : a));
      } catch (error: any) {
        toast.error(error.message || 'Failed to auto-save add-on');
        throw error;
      }
    },
    debounceMs: 500,
  });

  const updateQuick = async (id: string, updates: Partial<AddOn>) => {
    try {
      setAddons(prev => prev.map(a => a.id === id ? { ...a, ...updates } : a));
      await apiClient.put(`/api/admin/add-ons/${id}`, updates);
    } catch {
      toast.error('Failed to update add-on');
      fetchData();
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const [addonRes, svcRes] = await Promise.all([
        apiClient.get<any>('/api/admin/add-ons').catch(() => ({ data: [] })),
        apiClient.get<any>('/api/admin/services').catch(() => ({ data: [] })),
      ]);
      setAddons(Array.isArray(addonRes) ? addonRes : (addonRes?.data ?? []));
      setServices(Array.isArray(svcRes) ? svcRes : (svcRes?.data ?? []));
    } catch {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleSelect = (addon: AddOn) => {
    setSelectedId(addon.id);
    setIsCreating(false);
    setFormData({
      name: addon.name,
      description: addon.description || '',
      price: addon.price || 0,
      duration: addon.duration || 0,
      active: addon.active ?? true,
      is_visible: addon.is_visible ?? true,
      service_ids: addon.service_ids || [],
    });
  };

  const handleSave = async () => {
    if (!formData.name.trim()) { toast.error('Name is required'); return; }
    try {
      if (isCreating) {
        const newAddon = await apiClient.post<AddOn>('/api/admin/add-ons', formData);
        setAddons(prev => [...prev, newAddon]);
        toast.success('Add-on created');
        handleSelect(newAddon);
      } else if (selectedId) {
        const updated = await apiClient.put<AddOn>(`/api/admin/add-ons/${selectedId}`, formData);
        setAddons(prev => prev.map(a => a.id === selectedId ? updated : a));
        toast.success('Add-on updated');
        handleSelect(updated);
      }
    } catch { toast.error('Failed to save add-on'); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this add-on?')) return;
    try {
      await apiClient.delete(`/api/admin/add-ons/${id}`);
      setAddons(prev => prev.filter(a => a.id !== id));
      if (selectedId === id) { setSelectedId(null); setIsCreating(false); }
      toast.success('Add-on deleted');
    } catch { toast.error('Failed to delete add-on'); }
  };

  const handleDragStart = (e: React.DragEvent, id: string) => { setDraggedId(id); e.dataTransfer.effectAllowed = 'move'; };
  const handleDrop = (e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    if (!draggedId || draggedId === targetId) return;
    setAddons(prev => {
      const list = [...prev];
      const src = list.findIndex(a => a.id === draggedId);
      const dst = list.findIndex(a => a.id === targetId);
      if (src === -1 || dst === -1) return prev;
      const [moved] = list.splice(src, 1);
      list.splice(dst, 0, moved);
      return list;
    });
    setDraggedId(null);
  };

  const filtered = addons.filter(a => a.name.toLowerCase().includes(search.toLowerCase()));
  const selectedAddon = addons.find(a => a.id === selectedId);

  return (
    <div className="flex flex-col md:flex-row h-full w-full md:gap-4 overflow-hidden font-sans">
      {/* Left Pane */}
      <div className={`md:w-[35%] flex flex-col gap-4 border-r md:pr-4 transition-all duration-300 ${selectedId || isCreating ? 'hidden md:flex' : 'flex w-full'}`}>
        <div className="flex gap-2 items-center px-4 md:px-0">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3.5 md:top-2.5 h-4 w-4 text-muted-foreground" />
            <Input placeholder="Search add-ons..." className="pl-10 min-h-[44px]" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <Button variant="outline" size="icon" onClick={() => { setIsCreating(true); setSelectedId(null); setFormData(defaultForm); }} className="min-h-[44px] min-w-[44px] shrink-0" title="Add Add-on">
            <Plus className="w-5 h-5" />
          </Button>
        </div>

        <div className="flex items-center gap-2 px-4 md:px-0">
          <span className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Add-ons</span>
          <Badge variant="secondary">{filtered.length}</Badge>
        </div>

        <div className="flex-1 overflow-y-auto space-y-2 pb-12">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)
          ) : filtered.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">No add-ons found</div>
          ) : (
            filtered.map(addon => (
              <div
                key={addon.id}
                draggable
                onDragStart={e => handleDragStart(e, addon.id)}
                onDragOver={e => e.preventDefault()}
                onDrop={e => handleDrop(e, addon.id)}
                onClick={() => handleSelect(addon)}
                className={`p-3 rounded-xl hover:scale-[1.01] hover:shadow-md flex flex-col justify-center border transition-all duration-200 cursor-pointer ${
                  selectedId === addon.id
                    ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20'
                    : 'border-border bg-card/50 hover:bg-muted/30 hover:border-border/60 dark:bg-card dark:border-border/60'
                }`}
              >
                <div className="flex gap-3 items-start min-w-0 w-full relative pr-[56px]">
                  <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center text-muted-foreground shrink-0">
                    <Gift className="w-4 h-4 opacity-35" />
                  </div>
                  <div className="flex-1 min-w-0 flex flex-col gap-0.5 justify-center py-0.5">
                    <span className="text-sm font-semibold text-foreground leading-tight truncate block text-left" title={addon.name}>{addon.name}</span>
                    <div className="text-xs text-muted-foreground mt-0.5 text-left">${addon.price} &bull; {addon.duration} mins</div>
                  </div>
                  <div className="absolute top-0 right-0 h-full flex flex-col justify-between items-end pb-0.5 pr-0.5">
                    <div className="cursor-grab active:cursor-grabbing text-muted-foreground/45 hover:text-muted-foreground p-0.5" onClick={e => e.stopPropagation()}>
                      <GripVertical className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex items-center gap-0.5" onClick={e => e.stopPropagation()}>
                      <button onClick={() => updateQuick(addon.id, { active: !addon.active, ...(!addon.active ? {} : { is_visible: false }) })} className="p-0.5 hover:bg-muted rounded transition-colors" title={addon.active ? 'Deactivate' : 'Activate'}>
                        {addon.active ? <Circle className="w-3.5 h-3.5 fill-emerald-500 text-emerald-500" /> : <CircleSlash className="w-3.5 h-3.5 text-rose-500" />}
                      </button>
                      <button disabled={!addon.active} onClick={() => addon.active && updateQuick(addon.id, { is_visible: !addon.is_visible })} className={`p-0.5 rounded transition-colors ${addon.active ? 'hover:bg-muted' : 'opacity-30 cursor-not-allowed'}`} title={!addon.active ? 'Deactivated' : (addon.is_visible ? 'Hide' : 'Show')}>
                        {addon.is_visible && addon.active ? <Eye className="w-3.5 h-3.5 text-emerald-500" /> : <EyeOff className="w-3.5 h-3.5 text-muted-foreground" />}
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
            <p>Select an add-on from the list or create a new one.</p>
          </div>
        ) : (
          <Card className="flex-1 flex flex-col h-full overflow-hidden border-0 shadow-none py-0 gap-0">
            <CardHeader className="flex flex-row items-center justify-between shrink-0 bg-background z-10 border-b p-4 sticky top-0">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={() => { setSelectedId(null); setIsCreating(false); }}>
                  <ArrowLeft className="w-5 h-5" />
                </Button>
                <div>
                  <CardTitle className="text-2xl font-bold font-heading">{isCreating ? 'New Add-on' : (selectedAddon?.name || 'Add-on Details')}</CardTitle>
                  <CardDescription className="mt-1">{isCreating ? 'Create a new service add-on' : 'Auto-saving changes'}</CardDescription>
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
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">Add-on Details</AccordionTrigger>
                  <AccordionContent className="p-6">
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label className="text-base font-semibold">Name *</Label>
                        <Input value={formData.name} onChange={e => { const next = { ...formData, name: e.target.value }; setFormData(next); if (selectedId) triggerSave(next); }} placeholder="e.g. Deep Conditioning" />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-base font-semibold">Description</Label>
                        <Textarea value={formData.description} onChange={e => { const next = { ...formData, description: e.target.value }; setFormData(next); if (selectedId) triggerSave(next); }} placeholder="Brief description..." rows={3} />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-base font-semibold">Price ($)</Label>
                          <Input type="number" min={0} step={0.01} value={formData.price} onChange={e => { const next = { ...formData, price: parseFloat(e.target.value) || 0 }; setFormData(next); if (selectedId) triggerSave(next); }} />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-base font-semibold">Duration (mins)</Label>
                          <Input type="number" min={0} value={formData.duration} onChange={e => { const next = { ...formData, duration: parseInt(e.target.value) || 0 }; setFormData(next); if (selectedId) triggerSave(next); }} />
                        </div>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                {!isCreating && services.length > 0 && (
                  <AccordionItem value="services" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                    <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">Linked Services</AccordionTrigger>
                    <AccordionContent className="p-6">
                      <div className="space-y-2">
                        {services.map(svc => {
                          const linked = (formData.service_ids || []).includes(svc.id);
                          return (
                            <div key={svc.id} className="flex items-center justify-between p-3 border rounded-lg bg-card/45">
                              <Label htmlFor={`svc-${svc.id}`} className="text-sm font-medium">{svc.name}</Label>
                              <Switch id={`svc-${svc.id}`} checked={linked} onCheckedChange={checked => {
                                const current = formData.service_ids || [];
                                const next = { ...formData, service_ids: checked ? [...current, svc.id] : current.filter(id => id !== svc.id) };
                                setFormData(next);
                                if (selectedId) triggerSave(next, true);
                              }} />
                            </div>
                          );
                        })}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                )}

                <AccordionItem value="status" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">Visibility &amp; Status</AccordionTrigger>
                  <AccordionContent className="p-6">
                    <div className="space-y-4">
                      <div className="flex items-center justify-between p-3 border rounded-lg bg-card/45">
                        <Label htmlFor="addon-active" className="text-sm font-medium">Active</Label>
                        <Switch id="addon-active" checked={formData.active} onCheckedChange={checked => { const next = { ...formData, active: checked, ...(!checked ? { is_visible: false } : {}) }; setFormData(next); if (selectedId) triggerSave(next, true); }} />
                      </div>
                      <div className="flex items-center justify-between p-3 border rounded-lg bg-card/45">
                        <Label htmlFor="addon-visible" className="text-sm font-medium">Visible to clients</Label>
                        <Switch id="addon-visible" checked={formData.is_visible} disabled={!formData.active} onCheckedChange={checked => { const next = { ...formData, is_visible: checked }; setFormData(next); if (selectedId) triggerSave(next, true); }} />
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

              </Accordion>
            </CardContent>

            {isCreating && (
              <CardFooter className="flex justify-end gap-2 border-t p-4 mt-auto shrink-0 sticky bottom-0 bg-background z-10 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.1)]">
                <Button variant="outline" onClick={() => { setIsCreating(false); setSelectedId(null); }} className="min-h-[44px]">Cancel</Button>
                <Button onClick={handleSave} className="min-h-[44px]">Create Add-on</Button>
              </CardFooter>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
