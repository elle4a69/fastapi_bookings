import { useState, useEffect, useRef } from 'react';
import { 
  Search, 
  Loader2, 
  ArrowLeft, 
  RefreshCw, 
  Sparkles, 
  Layers, 
  GripVertical, 
  Eye, 
  EyeOff, 
  Circle, 
  CircleSlash, 
  Pencil, 
  Trash2, 
  Plus, 
  Save
} from 'lucide-react';
import { toast } from 'sonner';
import { Link } from 'react-router-dom';

import { apiClient } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';

interface EntityItem {
  id: number | string;
  name: string;
  active?: boolean;
  is_visible?: boolean;
  description?: string;
  price?: number;
  duration?: number;
  sku?: string;
  stock?: number;
  address?: string;
  timezone?: string;
  email?: string;
  phone?: string;
  image?: string;
}

type ColumnType = 'location' | 'provider' | 'service' | 'addon' | 'product' | 'category';

interface ColumnDef {
  id: ColumnType;
  label: string;
  apiEndpoint: string;
  plural: string;
}

const DEFAULT_COLUMNS: ColumnDef[] = [
  { id: 'location', label: 'Locations', apiEndpoint: '/api/admin/locations', plural: 'locations' },
  { id: 'provider', label: 'Service Providers', apiEndpoint: '/api/admin/providers', plural: 'providers' },
  { id: 'service', label: 'Services', apiEndpoint: '/api/admin/services', plural: 'services' },
  { id: 'addon', label: 'Service Add-ons', apiEndpoint: '/api/admin/add-ons', plural: 'add-ons' },
  { id: 'product', label: 'Products', apiEndpoint: '/api/admin/products', plural: 'products' },
  { id: 'category', label: 'Categories', apiEndpoint: '/api/admin/categories', plural: 'categories' },
];

const STORAGE_COL_ORDER_KEY = 'relationships_matrix_column_order';
const getItemOrderKey = (col: ColumnType) => `relationships_matrix_item_order_${col}`;

const normId = (id: any): number => {
  if (id === null || id === undefined) return 0;
  const str = String(id).replace(/^(prov|loc|svc|cat|add_on|addon|prod|product)-/i, '');
  return parseInt(str, 10) || 0;
};

const loadSavedColumns = (): ColumnDef[] => {
  try {
    const saved = localStorage.getItem(STORAGE_COL_ORDER_KEY);
    if (saved) {
      const savedIds: ColumnType[] = JSON.parse(saved);
      const reordered = savedIds
        .map(id => DEFAULT_COLUMNS.find(c => c.id === id))
        .filter(Boolean) as ColumnDef[];
      DEFAULT_COLUMNS.forEach(c => {
        if (!reordered.find(r => r.id === c.id)) reordered.push(c);
      });
      return reordered;
    }
  } catch {}
  return DEFAULT_COLUMNS;
};

const applySavedItemOrder = (col: ColumnType, items: EntityItem[]): EntityItem[] => {
  try {
    const saved = localStorage.getItem(getItemOrderKey(col));
    if (saved) {
      const savedIds: (number | string)[] = JSON.parse(saved);
      const itemMap = new Map(items.map(item => [normId(item.id), item]));
      const sorted: EntityItem[] = [];

      savedIds.forEach(id => {
        const item = itemMap.get(normId(id));
        if (item) {
          sorted.push(item);
          itemMap.delete(normId(id));
        }
      });

      itemMap.forEach(item => sorted.push(item));
      return sorted;
    }
  } catch {}
  return items;
};

export default function RelationshipsMatrixPage() {
  const [columns, setColumns] = useState<ColumnDef[]>(loadSavedColumns);
  const [draggedColIndex, setDraggedColIndex] = useState<number | null>(null);

  const columnsScrollRef = useRef<HTMLDivElement>(null);
  const [scrollPercentage, setScrollPercentage] = useState(0);

  const [data, setData] = useState<Record<ColumnType, EntityItem[]>>({
    location: [],
    provider: [],
    service: [],
    addon: [],
    product: [],
    category: [],
  });

  const [loading, setLoading] = useState<Record<ColumnType, boolean>>({
    location: true,
    provider: true,
    service: true,
    addon: true,
    product: true,
    category: true,
  });

  const [search, setSearch] = useState<Record<ColumnType, string>>({
    location: '',
    provider: '',
    service: '',
    addon: '',
    product: '',
    category: '',
  });

  const [focusColumn, setFocusColumn] = useState<ColumnType>('location');
  const [focusId, setFocusId] = useState<number | string | null>(null);

  const [linkedIds, setLinkedIds] = useState<Record<ColumnType, Set<number>>>({
    location: new Set(),
    provider: new Set(),
    service: new Set(),
    addon: new Set(),
    product: new Set(),
    category: new Set(),
  });

  const [updatingKeys, setUpdatingKeys] = useState<Set<string>>(new Set());
  const [draggedCardIndex, setDraggedCardIndex] = useState<{ col: ColumnType; index: number } | null>(null);

  const [createModalCol, setCreateModalCol] = useState<ColumnType | null>(null);
  const [editModalItem, setEditModalItem] = useState<{ col: ColumnType; item: EntityItem } | null>(null);

  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formPrice, setFormPrice] = useState('');
  const [formDuration, setFormDuration] = useState('');
  const [formAddress, setFormAddress] = useState('');
  const [formTimezone, setFormTimezone] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formPhone, setFormPhone] = useState('');
  const [formImage, setFormImage] = useState('');
  const [formSku, setFormSku] = useState('');
  const [formStock, setFormStock] = useState('');
  const [formActive, setFormActive] = useState(true);
  const [formVisible, setFormVisible] = useState(true);
  const [modalSaving, setModalSaving] = useState(false);

  useEffect(() => {
    fetchAllColumns();
  }, []);

  const fetchAllColumns = () => {
    DEFAULT_COLUMNS.forEach(async (col) => {
      setLoading(prev => ({ ...prev, [col.id]: true }));
      try {
        const res = await apiClient.get<any>(col.apiEndpoint);
        const raw = Array.isArray(res) ? res : (res?.data || res?.items || []);
        const ordered = applySavedItemOrder(col.id, raw);
        setData(prev => ({ ...prev, [col.id]: ordered }));
      } catch {
        toast.error(`Failed to load ${col.label}`);
      } finally {
        setLoading(prev => ({ ...prev, [col.id]: false }));
      }
    });
  };

  useEffect(() => {
    if (!focusId) {
      setLinkedIds({
        location: new Set(),
        provider: new Set(),
        service: new Set(),
        addon: new Set(),
        product: new Set(),
        category: new Set(),
      });
      return;
    }
    fetchFocusMappings();
  }, [focusColumn, focusId]);

  const fetchFocusMappings = async () => {
    if (!focusId) return;

    const sourcePlural = DEFAULT_COLUMNS.find(c => c.id === focusColumn)!.plural;
    const targetCols = DEFAULT_COLUMNS.filter(c => c.id !== focusColumn);

    const newLinked: Record<ColumnType, Set<number>> = {
      location: new Set(),
      provider: new Set(),
      service: new Set(),
      addon: new Set(),
      product: new Set(),
      category: new Set(),
    };

    await Promise.all(
      targetCols.map(async (targetCol) => {
        try {
          const url = `/api/admin/relationships/${sourcePlural}/${normId(focusId)}/${targetCol.plural}`;
          const res = await apiClient.get<any>(url);
          const list = Array.isArray(res) ? res : (res?.data || []);
          const idSet = new Set<number>(list.map((item: any) => normId(item.id)));
          newLinked[targetCol.id] = idSet;
        } catch {
          newLinked[targetCol.id] = new Set();
        }
      })
    );

    setLinkedIds(newLinked);
  };

  const handleContainerScroll = () => {
    const el = columnsScrollRef.current;
    if (!el) return;
    const maxScroll = el.scrollWidth - el.clientWidth;
    if (maxScroll > 0) {
      const pct = (el.scrollLeft / maxScroll) * 100;
      setScrollPercentage(pct);
    }
  };

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const pct = parseFloat(e.target.value);
    setScrollPercentage(pct);
    const el = columnsScrollRef.current;
    if (el) {
      const maxScroll = el.scrollWidth - el.clientWidth;
      el.scrollLeft = (pct / 100) * maxScroll;
    }
  };

  const handleToggleLink = async (targetCol: ColumnType, targetId: number | string, currentAssigned: boolean) => {
    if (!focusId) {
      toast.error('Select a source item first.');
      return;
    }

    const sourcePlural = DEFAULT_COLUMNS.find(c => c.id === focusColumn)!.plural;
    const targetPlural = DEFAULT_COLUMNS.find(c => c.id === targetCol)!.plural;
    const key = `link-${targetCol}-${targetId}`;

    setUpdatingKeys(prev => new Set(prev).add(key));

    const numericFocus = normId(focusId);
    const numericTarget = normId(targetId);

    try {
      const url = `/api/admin/relationships/${sourcePlural}/${numericFocus}/${targetPlural}/${numericTarget}`;
      if (currentAssigned) {
        await apiClient.delete(url);
        setLinkedIds(prev => {
          const updated = new Set(prev[targetCol]);
          updated.delete(numericTarget);
          return { ...prev, [targetCol]: updated };
        });
        toast.success('Unlinked');
      } else {
        await apiClient.post(url);
        setLinkedIds(prev => {
          const updated = new Set(prev[targetCol]);
          updated.add(numericTarget);
          return { ...prev, [targetCol]: updated };
        });
        toast.success('Linked');
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to update mapping.');
    } finally {
      setUpdatingKeys(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const toggleVisibility = async (col: ColumnType, item: EntityItem) => {
    const plural = DEFAULT_COLUMNS.find(c => c.id === col)!.plural;
    const newStatus = !(item.is_visible ?? true);
    const key = `vis-${col}-${item.id}`;
    setUpdatingKeys(prev => new Set(prev).add(key));

    try {
      await apiClient.put(`/api/admin/${plural}/${item.id}`, { is_visible: newStatus }).catch(async () => {
        return await apiClient.patch(`/api/admin/${plural}/${item.id}`, { is_visible: newStatus });
      });

      setData(prev => ({
        ...prev,
        [col]: prev[col].map(i => normId(i.id) === normId(item.id) ? { ...i, is_visible: newStatus } : i)
      }));
      toast.success(newStatus ? 'Item is now visible' : 'Item is now hidden');
    } catch {
      toast.error('Failed to toggle visibility');
    } finally {
      setUpdatingKeys(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const toggleActive = async (col: ColumnType, item: EntityItem) => {
    const plural = DEFAULT_COLUMNS.find(c => c.id === col)!.plural;
    const newStatus = !(item.active ?? true);
    const key = `act-${col}-${item.id}`;
    setUpdatingKeys(prev => new Set(prev).add(key));

    try {
      await apiClient.put(`/api/admin/${plural}/${item.id}`, { active: newStatus }).catch(async () => {
        return await apiClient.patch(`/api/admin/${plural}/${item.id}`, { active: newStatus });
      });

      setData(prev => ({
        ...prev,
        [col]: prev[col].map(i => normId(i.id) === normId(item.id) ? { ...i, active: newStatus } : i)
      }));
      toast.success(newStatus ? 'Item activated' : 'Item deactivated');
    } catch {
      toast.error('Failed to toggle active status');
    } finally {
      setUpdatingKeys(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const handleDeleteItem = async (col: ColumnType, item: EntityItem) => {
    if (!window.confirm(`Are you sure you want to delete "${item.name}"?`)) return;

    const plural = DEFAULT_COLUMNS.find(c => c.id === col)!.plural;
    try {
      await apiClient.delete(`/api/admin/${plural}/${item.id}`);
      setData(prev => ({
        ...prev,
        [col]: prev[col].filter(i => normId(i.id) !== normId(item.id))
      }));
      if (focusColumn === col && normId(focusId) === normId(item.id)) {
        setFocusId(null);
      }
      toast.success('Item deleted');
    } catch {
      toast.error('Failed to delete item');
    }
  };

  const resetFormFields = () => {
    setFormName('');
    setFormDesc('');
    setFormPrice('');
    setFormDuration('');
    setFormAddress('');
    setFormTimezone('UTC');
    setFormEmail('');
    setFormPhone('');
    setFormImage('');
    setFormSku('');
    setFormStock('');
    setFormActive(true);
    setFormVisible(true);
  };

  const openCreateModal = (col: ColumnType) => {
    resetFormFields();
    setCreateModalCol(col);
  };

  const openEditModal = (col: ColumnType, item: EntityItem) => {
    resetFormFields();
    setEditModalItem({ col, item });
    setFormName(item.name || '');
    setFormDesc(item.description || '');
    setFormPrice(item.price != null ? String(item.price) : '');
    setFormDuration(item.duration != null ? String(item.duration) : '');
    setFormAddress(item.address || '');
    setFormTimezone(item.timezone || 'UTC');
    setFormEmail(item.email || '');
    setFormPhone(item.phone || '');
    setFormImage(item.image || '');
    setFormSku(item.sku || '');
    setFormStock(item.stock != null ? String(item.stock) : '');
    setFormActive(item.active !== false);
    setFormVisible(item.is_visible !== false);
  };

  const handleSaveCreate = async () => {
    if (!createModalCol || !formName.trim()) {
      toast.error('Name is required');
      return;
    }
    setModalSaving(true);
    const colDef = DEFAULT_COLUMNS.find(c => c.id === createModalCol)!;
    const payload: any = {
      name: formName.trim(),
      description: formDesc.trim() || null,
      active: formActive,
      is_visible: formVisible,
    };

    if (formPrice) payload.price = parseFloat(formPrice) || 0;
    if (formDuration) payload.duration = parseInt(formDuration, 10) || 0;
    if (formImage.trim()) payload.image = formImage.trim();

    if (createModalCol === 'location') {
      payload.address = formAddress.trim() || null;
      payload.timezone = formTimezone.trim() || 'UTC';
    }
    if (createModalCol === 'provider') {
      payload.email = formEmail.trim() || null;
      payload.phone = formPhone.trim() || null;
    }
    if (createModalCol === 'product') {
      payload.sku = formSku.trim() || null;
      if (formStock) payload.stock = parseInt(formStock, 10) || 0;
    }

    try {
      const res: any = await apiClient.post(colDef.apiEndpoint, payload);
      const newItem = res?.data || res;
      
      const updatedList = [...data[createModalCol], newItem];
      setData(prev => ({ ...prev, [createModalCol]: updatedList }));

      try {
        localStorage.setItem(getItemOrderKey(createModalCol), JSON.stringify(updatedList.map(i => i.id)));
      } catch {}

      toast.success(`Created new ${colDef.label.slice(0, -1)}`);
      setCreateModalCol(null);
    } catch (err: any) {
      toast.error(err.message || 'Failed to create item');
    } finally {
      setModalSaving(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editModalItem || !formName.trim()) return;
    setModalSaving(true);
    const { col, item } = editModalItem;
    const colDef = DEFAULT_COLUMNS.find(c => c.id === col)!;
    const payload: any = {
      name: formName.trim(),
      description: formDesc.trim() || null,
      active: formActive,
      is_visible: formVisible,
    };

    if (formPrice) payload.price = parseFloat(formPrice) || 0;
    if (formDuration) payload.duration = parseInt(formDuration, 10) || 0;
    if (formImage.trim()) payload.image = formImage.trim();

    if (col === 'location') {
      payload.address = formAddress.trim() || null;
      payload.timezone = formTimezone.trim() || 'UTC';
    }
    if (col === 'provider') {
      payload.email = formEmail.trim() || null;
      payload.phone = formPhone.trim() || null;
    }
    if (col === 'product') {
      payload.sku = formSku.trim() || null;
      if (formStock) payload.stock = parseInt(formStock, 10) || 0;
    }

    try {
      await apiClient.put(`/api/admin/${colDef.plural}/${item.id}`, payload).catch(async () => {
        return await apiClient.patch(`/api/admin/${colDef.plural}/${item.id}`, payload);
      });
      setData(prev => ({
        ...prev,
        [col]: prev[col].map(i => normId(i.id) === normId(item.id) ? { ...i, ...payload } : i)
      }));
      toast.success('Updated successfully');
      setEditModalItem(null);
    } catch (err: any) {
      toast.error(err.message || 'Failed to update item');
    } finally {
      setModalSaving(false);
    }
  };

  const handleCardDragStart = (col: ColumnType, index: number) => {
    setDraggedCardIndex({ col, index });
  };

  const handleCardDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleCardDrop = (col: ColumnType, dropIndex: number) => {
    if (!draggedCardIndex || draggedCardIndex.col !== col) return;
    const srcIndex = draggedCardIndex.index;
    if (srcIndex === dropIndex) return;

    const list = [...data[col]];
    const [moved] = list.splice(srcIndex, 1);
    list.splice(dropIndex, 0, moved);

    setData(prev => ({ ...prev, [col]: list }));
    setDraggedCardIndex(null);

    try {
      const ids = list.map(item => item.id);
      localStorage.setItem(getItemOrderKey(col), JSON.stringify(ids));
    } catch {}

    toast.success('Item order saved!');
  };

  const handleColDragStart = (colIndex: number) => {
    setDraggedColIndex(colIndex);
  };

  const handleColDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleColDrop = (dropIndex: number) => {
    if (draggedColIndex === null || draggedColIndex === dropIndex) return;
    const nextCols = [...columns];
    const [moved] = nextCols.splice(draggedColIndex, 1);
    nextCols.splice(dropIndex, 0, moved);
    setColumns(nextCols);
    setDraggedColIndex(null);

    try {
      const ids = nextCols.map(c => c.id);
      localStorage.setItem(STORAGE_COL_ORDER_KEY, JSON.stringify(ids));
    } catch {}

    toast.success('Column layout saved!');
  };

  const handleSelectFocus = (col: ColumnType, id: number | string) => {
    if (focusColumn === col && focusId === id) {
      setFocusId(null);
    } else {
      setFocusColumn(col);
      setFocusId(id);
    }
  };

  const currentFocusItem = focusId
    ? data[focusColumn].find(item => normId(item.id) === normId(focusId))
    : null;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-background font-sans p-2 px-3 gap-2 overflow-hidden">
      {/* ── STREAMLINED COMPACT TOP HEADER ───────────────────────── */}
      <div className="flex items-center justify-between gap-2 border-b pb-1.5 shrink-0">
        <div className="flex items-center gap-2">
          <Link to="/admin/relationships">
            <Button variant="ghost" size="icon" className="h-7 w-7">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <h1 className="text-lg font-extrabold tracking-tight text-foreground">6-Column Relationship Matrix</h1>
        </div>

        <div className="flex items-center gap-2">
          {currentFocusItem && (
            <Badge variant="outline" className="bg-primary/10 border-primary/30 text-primary font-bold text-xs py-0.5 px-2 gap-1 hidden md:flex">
              <Sparkles className="w-3 h-3" />
              Focus: {currentFocusItem.name} ({DEFAULT_COLUMNS.find(c => c.id === focusColumn)?.label})
            </Badge>
          )}
          <Link to="/admin/relationships-tree">
            <Button variant="outline" size="sm" className="h-7 text-xs font-semibold gap-1.5 px-2.5">
              <Layers className="w-3.5 h-3.5 text-primary" /> Nested Tree
            </Button>
          </Link>
          <Button variant="outline" size="sm" onClick={fetchAllColumns} className="h-7 text-xs gap-1 px-2.5">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </Button>
        </div>
      </div>

      {/* ── PROMINENT CUSTOM HORIZONTAL SCROLL SLIDER BAR ──────────── */}
      <div className="flex items-center justify-between gap-3 px-3 py-1.5 bg-card/90 border border-border/70 rounded-xl shadow-2xs shrink-0">
        <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider whitespace-nowrap">
          Matrix Scroll Slider
        </span>
        <div className="relative flex-1 max-w-lg flex items-center">
          <input
            type="range"
            min="0"
            max="100"
            step="0.1"
            value={scrollPercentage}
            onChange={handleSliderChange}
            className="w-full h-2 bg-muted rounded-full appearance-none cursor-pointer accent-primary focus:outline-none shadow-inner"
            title="Drag slider to scroll columns left and right"
          />
        </div>
        <span className="text-xs font-semibold text-primary w-10 text-right">
          {Math.round(scrollPercentage)}%
        </span>
      </div>

      {/* ── 6 Columns Horizontally Scrollable Container ────────────── */}
      <div 
        ref={columnsScrollRef}
        onScroll={handleContainerScroll}
        className="flex-1 overflow-x-auto overflow-y-hidden scrollbar-thin pb-1"
      >
        <div className="flex gap-2.5 h-full min-w-[1380px]">
          {columns.map((col, colIndex) => {
            const items = data[col.id] || [];
            const isLoading = loading[col.id];
            const query = search[col.id] || '';
            const isFocusCol = focusColumn === col.id;
            const linkedSet = linkedIds[col.id];

            const filtered = items.filter(item => (item.name || '').toLowerCase().includes(query.toLowerCase()));

            return (
              <Card 
                key={col.id} 
                className="w-[225px] flex-shrink-0 h-full flex flex-col overflow-hidden border border-border/60 bg-card/80 shadow-xs"
              >
                {/* Column Header (Draggable left/right via Title Grab Handle) */}
                <CardHeader 
                  draggable
                  onDragStart={() => handleColDragStart(colIndex)}
                  onDragOver={handleColDragOver}
                  onDrop={() => handleColDrop(colIndex)}
                  className="p-2 pb-1.5 shrink-0 border-b border-border/30 bg-muted/20 cursor-grab active:cursor-grabbing select-none"
                  title="Drag header left or right to reorder columns"
                >
                  {/* Centered Column Title + Grab Handle */}
                  <div className="flex items-center justify-center gap-1.5 py-0.5">
                    <GripVertical className="h-3.5 w-3.5 text-muted-foreground/70 shrink-0" />
                    <CardTitle className="text-xs font-bold uppercase tracking-wider text-foreground text-center truncate">
                      {col.label}
                    </CardTitle>
                  </div>

                  {/* Single Compact Search + Badge Count + Plus Button Row */}
                  <div className="flex items-center gap-1 mt-1" onClick={(e) => e.stopPropagation()}>
                    <div className="relative flex-1 min-w-0">
                      <Search className="absolute left-2 top-2 h-3.5 w-3.5 text-muted-foreground" />
                      <Input
                        type="search"
                        placeholder="Filter..."
                        className="pl-7 h-7 text-xs rounded-lg bg-background w-full"
                        value={query}
                        onChange={(e) => setSearch(prev => ({ ...prev, [col.id]: e.target.value }))}
                      />
                    </div>
                    <Badge variant="secondary" className="text-[10px] h-7 px-1.5 font-bold shrink-0">
                      {filtered.length}
                    </Badge>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => openCreateModal(col.id)}
                      className="h-7 w-7 rounded-lg hover:bg-primary hover:text-primary-foreground transition-colors shrink-0"
                      title={`Add new ${col.label.slice(0, -1)}`}
                    >
                      <Plus className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardHeader>

                {/* Scrollable Cards Container */}
                <CardContent className="flex-1 overflow-y-auto p-1.5 space-y-1.5 scrollbar-thin">
                  {isLoading ? (
                    Array.from({ length: 6 }).map((_, i) => (
                      <Skeleton key={i} className="h-10 w-full rounded-lg" />
                    ))
                  ) : filtered.length === 0 ? (
                    <p className="text-center text-muted-foreground text-xs py-4">No items</p>
                  ) : (
                    filtered.map((item, index) => {
                      const numericItemId = normId(item.id);
                      const isSelected = isFocusCol && focusId !== null && normId(focusId) === numericItemId;
                      const isAssigned = !isSelected && focusId !== null && linkedSet.has(numericItemId);
                      const isVisible = item.is_visible !== false;
                      const isActive = item.active !== false;

                      const cardBase = "group w-full flex flex-col justify-between p-1 px-1.5 py-1 rounded-lg border text-left transition-all duration-150 select-none cursor-pointer gap-0.5 ";
                      const cardCls = isSelected
                        ? "border-primary bg-primary/10 ring-1 ring-primary/40 font-bold text-primary shadow-2xs"
                        : isAssigned
                        ? "border-emerald-500/40 bg-emerald-500/5 hover:bg-emerald-500/10 text-foreground"
                        : "border-border/40 hover:border-border/80 hover:bg-muted/30 text-foreground";

                      return (
                        <div
                          key={item.id}
                          draggable
                          onDragStart={(e) => { e.stopPropagation(); handleCardDragStart(col.id, index); }}
                          onDragOver={handleCardDragOver}
                          onDrop={(e) => { e.stopPropagation(); handleCardDrop(col.id, index); }}
                          onClick={() => handleSelectFocus(col.id, item.id)}
                          className={cardBase + cardCls}
                          title={item.name}
                        >
                          {/* Row 1: Item Name */}
                          <div className="flex items-center justify-between min-w-0 w-full">
                            <p className={'text-[11px] font-bold truncate leading-tight ' + (!isVisible ? 'opacity-40 line-through' : 'text-foreground')}>
                              {item.name || `Unnamed (ID: ${item.id})`}
                            </p>
                            {isSelected && (
                              <Badge className="bg-primary text-primary-foreground text-[8px] px-1 py-0 h-3.5 font-bold shrink-0 ml-1">
                                Focus
                              </Badge>
                            )}
                          </div>

                          {/* Row 2: Action Controls Toolbar */}
                          <div className="flex items-center justify-between w-full" onClick={(e) => e.stopPropagation()}>
                            <GripVertical className="h-3 w-3 shrink-0 text-muted-foreground/50 group-hover:text-muted-foreground transition-colors cursor-grab" />

                            <div className="flex items-center gap-0.5">
                              <button
                                type="button"
                                onClick={() => toggleVisibility(col.id, item)}
                                className="p-0.5 rounded hover:bg-muted/60 transition-colors text-muted-foreground hover:text-foreground"
                                title={isVisible ? "Visible (click to hide)" : "Hidden (click to show)"}
                              >
                                {isVisible ? <Eye className="h-3 w-3 text-emerald-500" /> : <EyeOff className="h-3 w-3 text-amber-500 opacity-70" />}
                              </button>

                              <button
                                type="button"
                                onClick={() => toggleActive(col.id, item)}
                                className="p-0.5 rounded hover:bg-muted/60 transition-colors text-muted-foreground hover:text-foreground"
                                title={isActive ? "Active (click to disable)" : "Disabled (click to activate)"}
                              >
                                {isActive ? <Circle className="h-3 w-3 text-emerald-500 fill-emerald-500/20" /> : <CircleSlash className="h-3 w-3 text-rose-500 opacity-70" />}
                              </button>

                              <button
                                type="button"
                                onClick={() => openEditModal(col.id, item)}
                                className="p-0.5 rounded hover:bg-muted/60 transition-colors text-muted-foreground hover:text-foreground"
                                title="Edit item"
                              >
                                <Pencil className="h-3 w-3" />
                              </button>

                              <button
                                type="button"
                                onClick={() => handleDeleteItem(col.id, item)}
                                className="p-0.5 rounded hover:bg-rose-500/10 transition-colors text-muted-foreground hover:text-rose-500"
                                title="Delete item"
                              >
                                <Trash2 className="h-3 w-3" />
                              </button>

                              {!isSelected && focusId !== null && !isFocusCol && (
                                <Switch
                                  id={`sw-${col.id}-${item.id}`}
                                  checked={isAssigned}
                                  onCheckedChange={() => handleToggleLink(col.id, item.id, isAssigned)}
                                  className="scale-75 cursor-pointer ml-0.5"
                                />
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* ── Comprehensive Create New Item Modal ────────────────────── */}
      <Dialog open={createModalCol !== null} onOpenChange={(open) => !open && setCreateModalCol(null)}>
        <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Add New {createModalCol ? DEFAULT_COLUMNS.find(c => c.id === createModalCol)?.label.slice(0, -1) : 'Item'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2 text-xs">
            <div className="space-y-1">
              <Label className="font-semibold">Name *</Label>
              <Input
                placeholder="Enter name..."
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label className="font-semibold">Description</Label>
              <Textarea
                placeholder="Detailed description..."
                rows={2}
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
              />
            </div>

            {(createModalCol === 'service' || createModalCol === 'addon' || createModalCol === 'product') && (
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="font-semibold">Price ($)</Label>
                  <Input
                    type="number"
                    placeholder="0.00"
                    value={formPrice}
                    onChange={(e) => setFormPrice(e.target.value)}
                  />
                </div>
                {(createModalCol === 'service' || createModalCol === 'addon') && (
                  <div className="space-y-1">
                    <Label className="font-semibold">Duration (Mins)</Label>
                    <Input
                      type="number"
                      placeholder="30"
                      value={formDuration}
                      onChange={(e) => setFormDuration(e.target.value)}
                    />
                  </div>
                )}
              </div>
            )}

            {createModalCol === 'location' && (
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="font-semibold">Address</Label>
                  <Input
                    placeholder="Full address..."
                    value={formAddress}
                    onChange={(e) => setFormAddress(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="font-semibold">Timezone</Label>
                  <Input
                    placeholder="UTC"
                    value={formTimezone}
                    onChange={(e) => setFormTimezone(e.target.value)}
                  />
                </div>
              </div>
            )}

            {createModalCol === 'provider' && (
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="font-semibold">Email</Label>
                  <Input
                    placeholder="provider@example.com"
                    value={formEmail}
                    onChange={(e) => setFormEmail(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="font-semibold">Phone</Label>
                  <Input
                    placeholder="+1 555 0199"
                    value={formPhone}
                    onChange={(e) => setFormPhone(e.target.value)}
                  />
                </div>
              </div>
            )}

            {createModalCol === 'product' && (
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="font-semibold">SKU</Label>
                  <Input
                    placeholder="PROD-001"
                    value={formSku}
                    onChange={(e) => setFormSku(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="font-semibold">Stock Quantity</Label>
                  <Input
                    type="number"
                    placeholder="100"
                    value={formStock}
                    onChange={(e) => setFormStock(e.target.value)}
                  />
                </div>
              </div>
            )}

            <div className="space-y-1">
              <Label className="font-semibold">Image / Avatar URL</Label>
              <Input
                placeholder="https://..."
                value={formImage}
                onChange={(e) => setFormImage(e.target.value)}
              />
            </div>

            <div className="flex items-center justify-between border-t pt-3 mt-2">
              <div className="flex items-center gap-2">
                <Switch id="c-act" checked={formActive} onCheckedChange={setFormActive} className="scale-75" />
                <Label htmlFor="c-act" className="cursor-pointer">Active</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch id="c-vis" checked={formVisible} onCheckedChange={setFormVisible} className="scale-75" />
                <Label htmlFor="c-vis" className="cursor-pointer">Visible</Label>
              </div>
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setCreateModalCol(null)}>Cancel</Button>
            <Button onClick={handleSaveCreate} disabled={modalSaving} className="gap-1.5">
              {modalSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save Item
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Comprehensive Edit Item Modal ──────────────────────────── */}
      <Dialog open={editModalItem !== null} onOpenChange={(open) => !open && setEditModalItem(null)}>
        <DialogContent className="sm:max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Edit {editModalItem ? DEFAULT_COLUMNS.find(c => c.id === editModalItem.col)?.label.slice(0, -1) : 'Item'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2 text-xs">
            <div className="space-y-1">
              <Label className="font-semibold">Name *</Label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label className="font-semibold">Description</Label>
              <Textarea
                rows={2}
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
              />
            </div>

            {(editModalItem?.col === 'service' || editModalItem?.col === 'addon' || editModalItem?.col === 'product') && (
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="font-semibold">Price ($)</Label>
                  <Input
                    type="number"
                    value={formPrice}
                    onChange={(e) => setFormPrice(e.target.value)}
                  />
                </div>
                {(editModalItem?.col === 'service' || editModalItem?.col === 'addon') && (
                  <div className="space-y-1">
                    <Label className="font-semibold">Duration (Mins)</Label>
                    <Input
                      type="number"
                      value={formDuration}
                      onChange={(e) => setFormDuration(e.target.value)}
                    />
                  </div>
                )}
              </div>
            )}

            {editModalItem?.col === 'location' && (
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="font-semibold">Address</Label>
                  <Input
                    value={formAddress}
                    onChange={(e) => setFormAddress(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="font-semibold">Timezone</Label>
                  <Input
                    value={formTimezone}
                    onChange={(e) => setFormTimezone(e.target.value)}
                  />
                </div>
              </div>
            )}

            {editModalItem?.col === 'provider' && (
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="font-semibold">Email</Label>
                  <Input
                    value={formEmail}
                    onChange={(e) => setFormEmail(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="font-semibold">Phone</Label>
                  <Input
                    value={formPhone}
                    onChange={(e) => setFormPhone(e.target.value)}
                  />
                </div>
              </div>
            )}

            {editModalItem?.col === 'product' && (
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="font-semibold">SKU</Label>
                  <Input
                    value={formSku}
                    onChange={(e) => setFormSku(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="font-semibold">Stock Quantity</Label>
                  <Input
                    type="number"
                    value={formStock}
                    onChange={(e) => setFormStock(e.target.value)}
                  />
                </div>
              </div>
            )}

            <div className="space-y-1">
              <Label className="font-semibold">Image / Avatar URL</Label>
              <Input
                value={formImage}
                onChange={(e) => setFormImage(e.target.value)}
              />
            </div>

            <div className="flex items-center justify-between border-t pt-3 mt-2">
              <div className="flex items-center gap-2">
                <Switch id="e-act" checked={formActive} onCheckedChange={setFormActive} className="scale-75" />
                <Label htmlFor="e-act" className="cursor-pointer">Active</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch id="e-vis" checked={formVisible} onCheckedChange={setFormVisible} className="scale-75" />
                <Label htmlFor="e-vis" className="cursor-pointer">Visible</Label>
              </div>
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setEditModalItem(null)}>Cancel</Button>
            <Button onClick={handleSaveEdit} disabled={modalSaving} className="gap-1.5">
              {modalSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
