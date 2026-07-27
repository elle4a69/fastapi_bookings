import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Plus, Search, Trash2, Edit, Upload, X, Circle, ImageIcon, ArrowLeft } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface Service {
  id: string;
  name: string;
}

interface Location {
  id: string;
  name: string;
}

interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  sku: string;
  active: boolean;
  service_ids?: string[];
  location_ids?: string[];
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

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  
  const navigate = useNavigate();
  const location = useLocation();
  
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  
  const [formData, setFormData] = useState<Omit<Product, 'id'>>({
    name: '',
    description: '',
    price: 0,
    sku: '',
    active: true,
    service_ids: [],
    location_ids: [],
    image: null,
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      const [productsData, servicesData, locationsData] = await Promise.all([
        apiClient.get<Product[]>('/api/admin/products'),
        apiClient.get<any>('/api/admin/services'),
        apiClient.get<Location[]>('/api/admin/locations')
      ]);
      setProducts(productsData);
      setServices(Array.isArray(servicesData) ? servicesData : (servicesData?.data ?? []));
      setLocations(Array.isArray(locationsData) ? locationsData : (locationsData?.data ?? []));
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
        sku: '',
        active: true,
        service_ids: [String(location.state.returnToServiceId)],
        location_ids: [],
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
      sku: '',
      active: true,
      service_ids: [],
      location_ids: [],
      image: null,
    });
  };

  const handleSelect = (product: Product) => {
    setSelectedId(product.id);
    setIsEditing(false);
    setIsCreating(false);
    
    // Derive service_ids from loaded services array having this product id in product_ids
    const associatedServiceIds = (services || [])
      .filter(svc => (svc.product_ids || []).map(String).includes(String(product.id)))
      .map(svc => String(svc.id));

    setFormData({
      name: product.name || '',
      description: product.description || '',
      price: product.price || 0,
      sku: product.sku || '',
      active: product.active ?? true,
      service_ids: associatedServiceIds,
      location_ids: product.location_ids || [],
      image: product.image || null,
    });
  };

  const handleSave = async () => {
    if (!formData.name) {
      toast.error('Name is required');
      return;
    }
    
    try {
      let createdProduct: any = null;
      if (isCreating) {
        createdProduct = await apiClient.post('/api/admin/products', formData);
        toast.success('Product created successfully');
      } else if (selectedId) {
        await apiClient.put(`/api/admin/products/${selectedId}`, formData);
        toast.success('Product updated successfully');
      }

      // If we came from a service, assign this product to that service
      if (isCreating && createdProduct && location.state?.returnToServiceId) {
        await apiClient.post('/api/admin/products/assign', {
          service_id: parseInt(location.state.returnToServiceId),
          product_id: parseInt(createdProduct.id)
        });
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
      toast.error('Failed to save product');
    }
  };

  const updateProductQuick = async (id: string, updates: Partial<Product>) => {
    try {
      setProducts(prev => prev.map(p => p.id === id ? { ...p, ...updates } : p));
      await apiClient.put(`/api/admin/products/${id}`, updates);
      toast.success('Product updated');
    } catch {
      toast.error('Failed to update product');
      fetchData();
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this product?')) return;
    try {
      await apiClient.delete(`/api/admin/products/${id}`);
      toast.success('Product deleted');
      if (selectedId === id) {
        setSelectedId(null);
        setIsEditing(false);
        setIsCreating(false);
      }
      fetchData();
    } catch (error) {
      toast.error('Failed to delete product');
    }
  };

  const toggleService = (serviceId: string) => {
    const current = (formData.service_ids || []).map(String);
    const target = String(serviceId);
    if (current.includes(target)) {
      setFormData({ ...formData, service_ids: current.filter(id => id !== target) });
    } else {
      setFormData({ ...formData, service_ids: [...current, target] });
    }
  };

  const toggleLocation = (locationId: string) => {
    const current = formData.location_ids || [];
    if (current.includes(locationId)) {
      setFormData({ ...formData, location_ids: current.filter(id => id !== locationId) });
    } else {
      setFormData({ ...formData, location_ids: [...current, locationId] });
    }
  };

  const filteredProducts = products.filter(p => p.name.toLowerCase().includes(search.toLowerCase()) || (p.sku && p.sku.toLowerCase().includes(search.toLowerCase())));

  return (
    <TooltipProvider>
    <div className="flex flex-col md:flex-row h-[calc(100vh-65px)] font-sans">
      {/* Left Sidebar */}
      <div className={`md:w-[35%] border-r flex flex-col bg-muted/10 transition-all duration-300 ${selectedId || isCreating ? 'hidden md:flex' : 'flex w-full'}`}>
        <div className="p-4 border-b flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold font-heading">Products</h2>
            <Button size="sm" onClick={handleCreateNew} className="min-h-[44px] px-4">
              <Plus className="h-4 w-4 mr-2" />
              New Product
            </Button>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-3.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search products..."
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
          ) : filteredProducts.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground text-sm">
              No products found.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-1 gap-3">
              {filteredProducts.map((product) => (
                <div
                  key={product.id}
                  className={`flex items-start justify-between p-4 rounded-xl cursor-pointer transition-all duration-200 hover:scale-[1.01] hover:shadow-md border min-h-[60px] ${
                    selectedId === product.id
                      ? 'bg-gradient-to-r from-primary/10 via-primary/5 to-transparent text-primary border-primary'
                      : 'border-border/60 hover:bg-muted/50 dark:hover:bg-card'
                  }`}
                  onClick={() => handleSelect(product)}
                >
                  <div className="flex gap-3 items-start">
                    {product.image ? (
                      <img src={product.image} alt={product.name} className="w-[80px] h-[80px] object-cover rounded-md shrink-0" />
                    ) : (
                      <div className="w-[80px] h-[80px] bg-muted rounded-md flex items-center justify-center text-muted-foreground shrink-0"><ImageIcon className="w-6 h-6 opacity-20"/></div>
                    )}
                    <div className="flex flex-col gap-1 mt-1">
                      <span className="font-medium leading-none">{product.name}</span>
                      <span className="text-xs text-muted-foreground line-clamp-2">{product.description}</span>
                      <div className="text-xs text-muted-foreground mt-1">{product.sku || 'No SKU'} &bull; ${product.price}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button onClick={() => updateProductQuick(product.id, { active: !product.active })} className="p-2 hover:bg-muted rounded-full">
                          <Circle className={`w-4 h-4 ${product.active ? 'fill-emerald-500 text-emerald-500' : 'text-muted-foreground/40'}`} />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent>{product.active ? 'Active' : 'Inactive'}</TooltipContent>
                    </Tooltip>
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
            <p>Select a product to view details or create a new one.</p>
            <Button variant="outline" className="mt-4" onClick={handleCreateNew}>
              Create New Product
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
                  <CardTitle className="font-heading text-xl">{isCreating ? 'New Product' : 'Product Details'}</CardTitle>
                  <CardDescription className="hidden md:block">
                    {isCreating ? 'Create a new product to sell' : 'Manage product settings'}
                  </CardDescription>
                </div>
              </div>
              {!isCreating && !isEditing && (
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setIsEditing(true)} className="min-h-[44px]">
                    <Edit className="h-4 w-4 md:mr-2" />
                    <span className="hidden md:inline">Edit</span>
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => selectedId && handleDelete(selectedId)} className="min-h-[44px]">
                    <Trash2 className="h-4 w-4 md:mr-2" />
                    <span className="hidden md:inline">Delete</span>
                  </Button>
                </div>
              )}
            </CardHeader>
            <CardContent className="space-y-6 p-4 md:p-6 flex-1 overflow-auto">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2 space-y-2">
                  <Label>Image</Label>
                  <ImageUpload 
                    imagePreview={formData.image || null} 
                    onImageSelect={(file) => setFormData({ ...formData, image: file })} 
                    onImageRemove={() => setFormData({ ...formData, image: null })} 
                    disabled={!isEditing} 
                  />
                </div>
                <div className="col-span-2 space-y-2">
                  <Label>Name</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    disabled={!isEditing}
                    placeholder="e.g. Premium Massage Oil"
                  />
                </div>
                <div className="col-span-2 space-y-2">
                  <Label>Description</Label>
                  <Textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    disabled={!isEditing}
                    placeholder="Describe this product..."
                  />
                </div>
                <div className="space-y-2">
                  <Label>SKU</Label>
                  <Input
                    value={formData.sku}
                    onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                    disabled={!isEditing}
                    placeholder="e.g. OIL-001"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Price ($)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.price}
                    onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) || 0 })}
                    disabled={!isEditing}
                  />
                </div>
                <div className="col-span-2 flex items-center justify-between p-3 border rounded-lg">
                  <div className="space-y-0.5">
                    <Label className="text-base">Active Status</Label>
                    <div className="text-sm text-muted-foreground">
                      Enable or disable this product across the platform.
                    </div>
                  </div>
                  <Switch
                    checked={formData.active}
                    onCheckedChange={(c) => setFormData({ ...formData, active: c })}
                    disabled={!isEditing}
                  />
                </div>
              </div>

              <div className="space-y-4 pt-4 border-t">
                <div className="space-y-1">
                  <Label className="text-base">Associated Services</Label>
                  <p className="text-sm text-muted-foreground">
                    Select which services this product can be associated with.
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

              <div className="space-y-4 pt-4 border-t">
                <div className="space-y-1">
                  <Label className="text-base">Available Locations</Label>
                  <p className="text-sm text-muted-foreground">
                    Select which locations sell this product.
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3 mt-2">
                  {(locations || []).map(location => (
                    <div key={location.id} className="flex items-center space-x-2 border p-3 rounded-md">
                      <Checkbox 
                        id={`loc-${location.id}`}
                        checked={(formData.location_ids || []).includes(location.id)}
                        onCheckedChange={() => toggleLocation(location.id)}
                        disabled={!isEditing}
                      />
                      <label
                        htmlFor={`loc-${location.id}`}
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                      >
                        {location.name}
                      </label>
                    </div>
                  ))}
                  {locations.length === 0 && (
                    <div className="text-sm text-muted-foreground col-span-2">No locations found.</div>
                  )}
                </div>
              </div>
            </CardContent>
            {isEditing && (
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
                  if (isCreating) {
                    setIsCreating(false);
                  } else {
                    setIsEditing(false);
                    // Reset
                    const item = products.find(p => p.id === selectedId);
                    if (item) handleSelect(item);
                  }
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
