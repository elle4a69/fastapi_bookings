import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Plus, Search, Trash2, Edit, ArrowUp, ArrowDown } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from '@/components/ui/card';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { toast } from 'sonner';

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
    setIsEditing(false);
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
    setFormData({
      ...formData,
      steps: [
        ...currentSteps,
        {
          service_id: '',
          offset_days: 0,
          price: 0,
          active: true
        }
      ]
    });
  };

  const removeStep = (index: number) => {
    const currentSteps = formData.steps || [];
    const newSteps = [...currentSteps];
    newSteps.splice(index, 1);
    setFormData({ ...formData, steps: newSteps });
  };

  const updateStep = (index: number, field: keyof PackageStep, value: any) => {
    const currentSteps = formData.steps || [];
    const newSteps = [...currentSteps];
    newSteps[index] = { ...newSteps[index], [field]: value };
    setFormData({ ...formData, steps: newSteps });
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
    
    setFormData({ ...formData, steps: newSteps });
  };

  const filteredPackages = packages.filter(p => p.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="flex h-[calc(100vh-65px)]">
      {/* Left Sidebar */}
      <div className="w-[35%] border-r flex flex-col bg-muted/10">
        <div className="p-4 border-b flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Packages</h2>
            <Button size="sm" onClick={handleCreateNew}>
              <Plus className="h-4 w-4 mr-2" />
              New Package
            </Button>
          </div>
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search packages..."
              className="pl-8"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
        
        <div className="flex-1 overflow-auto p-2">
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
            <div className="space-y-1">
              {filteredPackages.map((pkg) => (
                <div
                  key={pkg.id}
                  className={`flex items-center justify-between p-3 rounded-md cursor-pointer transition-colors ${
                    selectedId === pkg.id
                      ? 'bg-primary/10 text-primary hover:bg-primary/15'
                      : 'hover:bg-muted'
                  }`}
                  onClick={() => handleSelect(pkg)}
                >
                  <div>
                    <div className="font-medium">{pkg.name}</div>
                    <div className="text-xs text-muted-foreground flex gap-2 mt-1">
                      <span>${pkg.price}</span>
                      <span>•</span>
                      <span>{pkg.steps?.length || 0} steps</span>
                    </div>
                  </div>
                  <Badge variant={pkg.active ? 'default' : 'secondary'}>
                    {pkg.active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right Content */}
      <div className="w-[65%] flex flex-col bg-background overflow-auto p-6">
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
          <Card className="max-w-3xl w-full mx-auto">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>{isCreating ? 'New Package' : 'Package Details'}</CardTitle>
                <CardDescription>
                  {isCreating ? 'Create a multi-service package' : 'Manage package settings'}
                </CardDescription>
              </div>
              {!isCreating && !isEditing && (
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setIsEditing(true)}>
                    <Edit className="h-4 w-4 mr-2" />
                    Edit
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => selectedId && handleDelete(selectedId)}>
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete
                  </Button>
                </div>
              )}
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2 space-y-2">
                  <Label>Name</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    disabled={!isEditing}
                    placeholder="e.g. 6-Month Care Plan"
                  />
                </div>
                <div className="col-span-2 space-y-2">
                  <Label>Description</Label>
                  <Textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    disabled={!isEditing}
                    placeholder="Describe this package..."
                  />
                </div>
                <div className="space-y-2">
                  <Label>Package Price ($)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.price}
                    onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) || 0 })}
                    disabled={!isEditing}
                  />
                </div>
                <div className="flex items-center justify-between p-3 border rounded-lg h-[72px]">
                  <div className="space-y-0.5">
                    <Label className="text-base">Active Status</Label>
                  </div>
                  <Switch
                    checked={formData.active}
                    onCheckedChange={(c) => setFormData({ ...formData, active: c })}
                    disabled={!isEditing}
                  />
                </div>
              </div>

              <div className="space-y-4 pt-4 border-t">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-base">Package Steps</Label>
                    <p className="text-sm text-muted-foreground">
                      Define the sequence of services included in this package.
                    </p>
                  </div>
                  {isEditing && (
                    <Button variant="outline" size="sm" onClick={addStep}>
                      <Plus className="h-4 w-4 mr-2" />
                      Add Step
                    </Button>
                  )}
                </div>
                
                <div className="space-y-3 mt-4">
                  {(formData.steps || []).length === 0 ? (
                    <div className="text-center p-6 border border-dashed rounded-lg text-muted-foreground">
                      No steps added to this package yet.
                    </div>
                  ) : (
                    (formData.steps || []).map((step, index) => (
                      <div key={index} className="flex gap-4 items-start border p-4 rounded-lg bg-card">
                        <div className="flex flex-col gap-1 mt-1">
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            className="h-6 w-6" 
                            disabled={!isEditing || index === 0}
                            onClick={() => moveStep(index, 'up')}
                          >
                            <ArrowUp className="h-4 w-4" />
                          </Button>
                          <div className="text-center text-xs font-semibold">{index + 1}</div>
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            className="h-6 w-6"
                            disabled={!isEditing || index === (formData.steps?.length || 0) - 1}
                            onClick={() => moveStep(index, 'down')}
                          >
                            <ArrowDown className="h-4 w-4" />
                          </Button>
                        </div>
                        
                        <div className="flex-1 grid grid-cols-12 gap-3">
                          <div className="col-span-5 space-y-1">
                            <Label className="text-xs">Service</Label>
                            <Select 
                              disabled={!isEditing}
                              value={step.service_id}
                              onValueChange={(val) => updateStep(index, 'service_id', val)}
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="Select service..." />
                              </SelectTrigger>
                              <SelectContent>
                                {services.map(s => (
                                  <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          
                          <div className="col-span-3 space-y-1">
                            <Label className="text-xs">Offset (Days)</Label>
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
                          
                          <div className="col-span-1 flex flex-col items-center justify-center space-y-2 pt-5">
                            {isEditing && (
                              <Button 
                                variant="ghost" 
                                size="icon" 
                                className="h-8 w-8 text-destructive hover:text-destructive/90"
                                onClick={() => removeStep(index)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </CardContent>
            {isEditing && (
              <CardFooter className="flex justify-end gap-2 border-t pt-4">
                <Button variant="ghost" onClick={() => {
                  if (isCreating) {
                    setIsCreating(false);
                  } else {
                    setIsEditing(false);
                    // Reset
                    const item = packages.find(p => p.id === selectedId);
                    if (item) handleSelect(item);
                  }
                }}>
                  Cancel
                </Button>
                <Button onClick={handleSave}>
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
