import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { Plus, Search, Trash2, ArrowLeft, Layers, Circle, CircleSlash, Eye, EyeOff, GripVertical } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { toast } from 'sonner';
import { useAutoSave } from '@/hooks/use-auto-save';
import { AutoSaveStatus } from '@/components/ui/auto-save-status';

interface Category {
  id: string;
  name: string;
  description: string | null;
  active: boolean;
  is_visible: boolean;
}

export default function CategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [draggedId, setDraggedId] = useState<string | null>(null);

  const navigate = useNavigate();
  const location = useLocation();

  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const defaultForm = { name: '', description: '', active: true, is_visible: true };
  const [formData, setFormData] = useState(defaultForm);

  const { saveState, triggerSave, retry } = useAutoSave({
    onSave: async (updatedData: any) => {
      const targetId = selectedCategoryId;
      if (!targetId) return;
      try {
        const res = await apiClient.put<any>(`/api/admin/categories/${targetId}`, updatedData);
        const dataObj = res?.data || res;
        setCategories(prev => prev.map(c => c.id === targetId ? { ...c, ...dataObj } : c));
      } catch (error: any) {
        toast.error(error.message || 'Failed to auto-save category');
        throw error;
      }
    },
    debounceMs: 500,
  });

  const updateCategoryQuick = async (id: string, updates: Partial<Category>) => {
    try {
      setCategories(prev => prev.map(c => c.id === id ? { ...c, ...updates } : c));
      await apiClient.put(`/api/admin/categories/${id}`, updates);
    } catch {
      toast.error('Failed to update category');
      fetchCategories();
    }
  };

  const fetchCategories = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<any>('/api/admin/categories');
      const arr = Array.isArray(data) ? data : (data?.data ?? []);
      setCategories(arr);
    } catch {
      toast.error('Failed to load categories');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCategories();
    if (location.state?.returnToServiceId) {
      setIsCreating(true);
      setSelectedCategoryId(null);
      setFormData(defaultForm);
    }
  }, [location.state]);

  const handleCreateNew = () => {
    setIsCreating(true);
    setSelectedCategoryId(null);
    setFormData(defaultForm);
  };

  const handleSelectCategory = (cat: Category) => {
    setSelectedCategoryId(cat.id);
    setIsCreating(false);
    setFormData({
      name: cat.name,
      description: cat.description || '',
      active: cat.active,
      is_visible: cat.is_visible ?? true,
    });
  };

  const handleSave = async () => {
    if (!formData.name.trim()) { toast.error('Name is required'); return; }
    try {
      if (isCreating) {
        const newCat = await apiClient.post<Category>('/api/admin/categories', formData);
        setCategories(prev => [...prev, newCat]);
        toast.success('Category created');
        handleSelectCategory(newCat);
        if (location.state?.returnToServiceId) {
          navigate('/admin/catalog/services', {
            state: { selectServiceId: location.state.returnToServiceId, openSection: location.state.section }
          });
        }
      } else if (selectedCategoryId) {
        const updated = await apiClient.put<Category>(`/api/admin/categories/${selectedCategoryId}`, formData);
        setCategories(prev => prev.map(c => c.id === selectedCategoryId ? updated : c));
        toast.success('Category updated');
        handleSelectCategory(updated);
      }
    } catch { toast.error('Failed to save category'); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this category?')) return;
    try {
      await apiClient.delete(`/api/admin/categories/${id}`);
      setCategories(prev => prev.filter(c => c.id !== id));
      if (selectedCategoryId === id) { setSelectedCategoryId(null); setIsCreating(false); }
      toast.success('Category deleted');
    } catch { toast.error('Failed to delete category'); }
  };

  const handleDragStart = (e: React.DragEvent, id: string) => { setDraggedId(id); e.dataTransfer.effectAllowed = 'move'; };
  const handleDrop = (e: React.DragEvent, targetId: string) => {
    e.preventDefault();
    if (!draggedId || draggedId === targetId) return;
    setCategories(prev => {
      const list = [...prev];
      const src = list.findIndex(c => c.id === draggedId);
      const dst = list.findIndex(c => c.id === targetId);
      if (src === -1 || dst === -1) return prev;
      const [moved] = list.splice(src, 1);
      list.splice(dst, 0, moved);
      return list;
    });
    setDraggedId(null);
  };

  const filtered = categories.filter(c => c.name.toLowerCase().includes(search.toLowerCase()));
  const selectedCategory = categories.find(c => c.id === selectedCategoryId);

  return (
    <div className="flex flex-col md:flex-row h-full w-full md:gap-4 overflow-hidden font-sans">
      {/* Left Pane */}
      <div className={`md:w-[35%] flex flex-col gap-4 border-r md:pr-4 transition-all duration-300 ${selectedCategoryId || isCreating ? 'hidden md:flex' : 'flex w-full'}`}>
        <div className="flex gap-2 items-center px-4 md:px-0">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3.5 md:top-2.5 h-4 w-4 text-muted-foreground" />
            <Input placeholder="Search categories..." className="pl-10 min-h-[44px]" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <Button variant="outline" size="icon" onClick={handleCreateNew} className="min-h-[44px] min-w-[44px] shrink-0" title="Add Category">
            <Plus className="w-5 h-5" />
          </Button>
        </div>

        <div className="flex items-center gap-2 px-4 md:px-0">
          <span className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Categories</span>
          <Badge variant="secondary">{filtered.length}</Badge>
        </div>

        <div className="flex-1 overflow-y-auto space-y-2 pb-12">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)
          ) : filtered.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">No categories found</div>
          ) : (
            filtered.map(cat => (
              <div
                key={cat.id}
                draggable
                onDragStart={e => handleDragStart(e, cat.id)}
                onDragOver={e => e.preventDefault()}
                onDrop={e => handleDrop(e, cat.id)}
                onClick={() => handleSelectCategory(cat)}
                className={`p-3 rounded-xl hover:scale-[1.01] hover:shadow-md flex flex-col justify-center border transition-all duration-200 cursor-pointer ${
                  selectedCategoryId === cat.id
                    ? 'border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20'
                    : 'border-border bg-card/50 hover:bg-muted/30 hover:border-border/60 dark:bg-card dark:border-border/60'
                }`}
              >
                <div className="flex gap-3 items-start min-w-0 w-full relative pr-[56px]">
                  <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center text-muted-foreground shrink-0">
                    <Layers className="w-4 h-4 opacity-35" />
                  </div>
                  <div className="flex-1 min-w-0 flex flex-col gap-0.5 justify-center py-0.5">
                    <span className="text-sm font-semibold text-foreground leading-tight truncate block text-left" title={cat.name}>{cat.name}</span>
                    <div className="text-xs text-muted-foreground mt-0.5 truncate text-left">{cat.description || 'No description'}</div>
                  </div>
                  <div className="absolute top-0 right-0 h-full flex flex-col justify-between items-end pb-0.5 pr-0.5">
                    <div className="cursor-grab active:cursor-grabbing text-muted-foreground/45 hover:text-muted-foreground p-0.5" onClick={e => e.stopPropagation()}>
                      <GripVertical className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex items-center gap-0.5" onClick={e => e.stopPropagation()}>
                      <button
                        onClick={() => updateCategoryQuick(cat.id, { active: !cat.active, ...(cat.active ? { is_visible: false } : {}) })}
                        className="p-0.5 hover:bg-muted rounded transition-colors"
                        title={cat.active ? 'Deactivate' : 'Activate'}
                      >
                        {cat.active ? <Circle className="w-3.5 h-3.5 fill-emerald-500 text-emerald-500" /> : <CircleSlash className="w-3.5 h-3.5 text-rose-500" />}
                      </button>
                      <button
                        disabled={!cat.active}
                        onClick={() => cat.active && updateCategoryQuick(cat.id, { is_visible: !cat.is_visible })}
                        className={`p-0.5 rounded transition-colors ${cat.active ? 'hover:bg-muted' : 'opacity-30 cursor-not-allowed'}`}
                        title={!cat.active ? 'Deactivated' : (cat.is_visible ? 'Hide' : 'Show')}
                      >
                        {cat.is_visible && cat.active ? <Eye className="w-3.5 h-3.5 text-emerald-500" /> : <EyeOff className="w-3.5 h-3.5 text-muted-foreground" />}
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
      <div className={`md:w-[65%] flex flex-col md:pl-4 transition-all duration-300 h-full ${selectedCategoryId || isCreating ? 'flex w-full absolute inset-0 z-50 bg-background md:relative md:z-auto' : 'hidden md:flex'}`}>
        {!selectedCategoryId && !isCreating ? (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground bg-muted/20">
            <div className="h-16 w-16 bg-muted rounded-full flex items-center justify-center mb-4">
              <Search className="h-8 w-8 opacity-50" />
            </div>
            <p>Select a category from the list or create a new one.</p>
          </div>
        ) : (
          <Card className="flex-1 flex flex-col h-full overflow-hidden border-0 shadow-none py-0 gap-0">
            <CardHeader className="flex flex-row items-center justify-between shrink-0 bg-background z-10 border-b p-4 sticky top-0">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={() => { setSelectedCategoryId(null); setIsCreating(false); }}>
                  <ArrowLeft className="w-5 h-5" />
                </Button>
                <div>
                  <CardTitle className="text-2xl font-bold font-heading">{isCreating ? 'New Category' : (selectedCategory?.name || 'Category Details')}</CardTitle>
                  <CardDescription className="mt-1">{isCreating ? 'Create a new service category' : 'Auto-saving changes'}</CardDescription>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {selectedCategoryId && <AutoSaveStatus state={saveState} onRetry={retry} />}
                {selectedCategoryId && (
                  <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" onClick={() => handleDelete(selectedCategoryId)}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </CardHeader>

            <CardContent className="flex-1 overflow-y-auto p-6">
              <Accordion type="multiple" defaultValue={['details', 'status']} className="space-y-3">

                <AccordionItem value="details" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">Category Details</AccordionTrigger>
                  <AccordionContent className="p-6">
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label className="text-base font-semibold">Name *</Label>
                        <Input
                          value={formData.name}
                          onChange={e => {
                            const next = { ...formData, name: e.target.value };
                            setFormData(next);
                            if (selectedCategoryId) triggerSave(next);
                          }}
                          placeholder="e.g. Massages, Facials"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-base font-semibold">Description</Label>
                        <Textarea
                          value={formData.description}
                          onChange={e => {
                            const next = { ...formData, description: e.target.value };
                            setFormData(next);
                            if (selectedCategoryId) triggerSave(next);
                          }}
                          placeholder="A brief description of this category..."
                          rows={4}
                        />
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="status" className="border rounded-lg bg-card overflow-hidden shadow-sm">
                  <AccordionTrigger className="hover:no-underline font-medium px-6 py-4 bg-muted/20">Visibility &amp; Status</AccordionTrigger>
                  <AccordionContent className="p-6">
                    <div className="space-y-4">
                      <div className="flex items-center justify-between p-3 border rounded-lg bg-card/45">
                        <Label htmlFor="cat-active" className="text-sm font-medium">Active</Label>
                        <Switch
                          id="cat-active"
                          checked={formData.active}
                          onCheckedChange={checked => {
                            const next = { ...formData, active: checked, ...(!checked ? { is_visible: false } : {}) };
                            setFormData(next);
                            if (selectedCategoryId) triggerSave(next, true);
                          }}
                        />
                      </div>
                      <div className="flex items-center justify-between p-3 border rounded-lg bg-card/45">
                        <Label htmlFor="cat-visible" className="text-sm font-medium">Visible to clients</Label>
                        <Switch
                          id="cat-visible"
                          checked={formData.is_visible}
                          disabled={!formData.active}
                          onCheckedChange={checked => {
                            const next = { ...formData, is_visible: checked };
                            setFormData(next);
                            if (selectedCategoryId) triggerSave(next, true);
                          }}
                        />
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

              </Accordion>
            </CardContent>

            {isCreating && (
              <CardFooter className="flex justify-end gap-2 border-t p-4 mt-auto shrink-0 sticky bottom-0 bg-background z-10 shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.1)]">
                <Button variant="outline" onClick={() => { setIsCreating(false); setSelectedCategoryId(null); }} className="min-h-[44px]">Cancel</Button>
                <Button onClick={handleSave} className="min-h-[44px]">Create Category</Button>
              </CardFooter>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
