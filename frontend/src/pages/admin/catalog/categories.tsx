import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Plus, Search, Trash2, Edit, ArrowLeft } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from '@/components/ui/card';
import { toast } from 'sonner';

interface Category {
  id: string;
  name: string;
  description: string | null;
  active: boolean;
}

export default function CategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  
  const navigate = useNavigate();
  const location = useLocation();
  
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  
  // Form State
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    active: true,
  });

  const fetchCategories = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<Category[]>('/api/admin/categories');
      setCategories(data);
    } catch (error) {
      toast.error('Failed to load categories');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCategories();
    if (location.state?.returnToServiceId) {
      setIsCreating(true);
      setIsEditing(true);
      setSelectedCategoryId(null);
      setFormData({ name: '', description: '', active: true });
    }
  }, [location.state]);

  const handleCreateNew = () => {
    setIsCreating(true);
    setIsEditing(true);
    setSelectedCategoryId(null);
    setFormData({ name: '', description: '', active: true });
  };

  const handleSelectCategory = (cat: Category) => {
    setSelectedCategoryId(cat.id);
    setIsCreating(false);
    setIsEditing(false);
    setFormData({
      name: cat.name,
      description: cat.description || '',
      active: cat.active,
    });
  };

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleCancel = () => {
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
      setIsEditing(false);
    } else if (selectedCategoryId) {
      const cat = categories.find(c => c.id === selectedCategoryId);
      if (cat) {
        setFormData({
          name: cat.name,
          description: cat.description || '',
          active: cat.active,
        });
      }
      setIsEditing(false);
    }
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      toast.error('Name is required');
      return;
    }

    try {
      let savedCat: Category | null = null;
      if (isCreating) {
        const newCat = await apiClient.post<Category>('/api/admin/categories', {
          name: formData.name,
          description: formData.description,
          active: formData.active,
        });
        setCategories([...categories, newCat]);
        toast.success('Category created successfully');
        handleSelectCategory(newCat);
        savedCat = newCat;
      } else if (selectedCategoryId) {
        const updatedCat = await apiClient.put<Category>(`/api/admin/categories/${selectedCategoryId}`, {
          name: formData.name,
          description: formData.description,
          active: formData.active,
        });
        setCategories(categories.map(c => c.id === selectedCategoryId ? updatedCat : c));
        toast.success('Category updated successfully');
        handleSelectCategory(updatedCat);
        savedCat = updatedCat;
      }

      if (savedCat && location.state?.returnToServiceId) {
        navigate('/admin/catalog/services', {
          state: {
            selectServiceId: location.state.returnToServiceId,
            openSection: location.state.section
          }
        });
      }
    } catch (error) {
      toast.error('Failed to save category');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this category?')) return;
    try {
      await apiClient.delete(`/api/admin/categories/${id}`);
      setCategories(categories.filter(c => c.id !== id));
      if (selectedCategoryId === id) {
        setSelectedCategoryId(null);
        setIsEditing(false);
        setIsCreating(false);
      }
      toast.success('Category deleted');
    } catch (error) {
      toast.error('Failed to delete category');
    }
  };

  const filteredCategories = categories.filter(c => c.name.toLowerCase().includes(search.toLowerCase()));



  return (
    <div className="flex flex-col md:flex-row h-full w-full md:gap-4 overflow-hidden font-sans">
      {/* Left Pane - List */}
      <div className={`md:w-[35%] flex flex-col gap-4 border-r md:pr-4 transition-all duration-300 ${selectedCategoryId || isCreating ? 'hidden md:flex' : 'flex w-full'}`}>
        <div className="flex justify-between items-center p-4 md:p-0">
          <h2 className="text-2xl font-bold font-heading">Categories</h2>
          <Button onClick={handleCreateNew} size="sm" className="min-h-[44px] px-4">
            <Plus className="w-4 h-4 mr-2" /> Add Category
          </Button>
        </div>
        <div className="relative px-4 md:px-0">
          <Search className="absolute left-6 md:left-2.5 top-3.5 md:top-2.5 h-4 w-4 text-muted-foreground" />
          <Input 
            placeholder="Search categories..." 
            className="pl-10 md:pl-8 min-h-[44px]" 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        
        <div className="flex-1 overflow-y-auto space-y-2 px-4 md:px-0 pb-20 md:pb-0">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))
          ) : filteredCategories.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">No categories found</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-1 gap-3">
              {filteredCategories.map((category) => (
                <div 
                  key={category.id}
                  onClick={() => handleSelectCategory(category)}
                  className={`p-3 rounded-xl cursor-pointer border transition-all duration-200 hover:scale-[1.01] hover:shadow-md flex justify-between items-center min-h-[60px] ${
                    selectedCategoryId === category.id 
                      ? 'border-primary bg-gradient-to-r from-primary/10 via-primary/5 to-transparent' 
                      : 'border-border/60 hover:bg-muted/50 dark:bg-card dark:border-border/60'
                  }`}
                >
                  <div>
                    <div className="font-medium font-heading">{category.name}</div>
                    <div className="text-xs text-muted-foreground truncate max-w-[150px]">
                      {category.description || 'No description'}
                    </div>
                  </div>
                  <Badge variant={category.active ? 'default' : 'secondary'}>
                    {category.active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right Pane - Detail / Form */}
      <div className={`md:w-[65%] flex flex-col md:pl-4 transition-all duration-300 h-full ${selectedCategoryId || isCreating ? 'flex w-full absolute inset-0 z-50 bg-background md:relative md:z-auto' : 'hidden md:flex'}`}>
        {!selectedCategoryId && !isCreating ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            Select a category to view details or create a new one.
          </div>
        ) : (
          <Card className="flex-1 flex flex-col shadow-none md:shadow-sm border-0 md:border">
            <CardHeader className="flex flex-row items-center justify-between sticky top-0 bg-background z-10 border-b md:border-b-0 pb-4 md:pb-6 p-4 md:p-6">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="md:hidden shrink-0 min-h-[44px] min-w-[44px]" onClick={() => { setSelectedCategoryId(null); setIsCreating(false); setIsEditing(false); }}>
                  <ArrowLeft className="w-5 h-5" />
                </Button>
                <div>
                  <CardTitle className="font-heading text-xl">{isCreating ? 'Create Category' : isEditing ? 'Edit Category' : 'Category Details'}</CardTitle>
                  <CardDescription>
                    {isCreating ? 'Fill out the form below to create a new category.' : 'View and manage category details.'}
                  </CardDescription>
                </div>
              </div>
              {!isCreating && !isEditing && (
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleEdit}>
                    <Edit className="w-4 h-4 mr-2" /> Edit
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => handleDelete(selectedCategoryId!)}>
                    <Trash2 className="w-4 h-4 mr-2" /> Delete
                  </Button>
                </div>
              )}
            </CardHeader>
            
            <CardContent className="flex-1 space-y-6">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input 
                  id="name" 
                  value={formData.name} 
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  disabled={!isEditing}
                  placeholder="e.g. Guided Tours"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea 
                  id="description" 
                  value={formData.description} 
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  disabled={!isEditing}
                  placeholder="A brief description of this category..."
                  rows={4}
                />
              </div>

              <div className="flex items-center space-x-2">
                <Switch 
                  id="active" 
                  checked={formData.active} 
                  onCheckedChange={(checked) => setFormData({ ...formData, active: checked })}
                  disabled={!isEditing}
                />
                <Label htmlFor="active">Active (visible in catalog)</Label>
              </div>
            </CardContent>

            {isEditing && (
              <CardFooter className="flex justify-end gap-2 border-t p-4 md:pt-4 mt-auto sticky bottom-0 bg-background z-10 md:static shadow-[0_-10px_20px_-10px_rgba(0,0,0,0.1)] md:shadow-none">
                <Button variant="outline" onClick={handleCancel} className="min-h-[44px]">Cancel</Button>
                <Button onClick={handleSave} className="min-h-[44px]">Save</Button>
              </CardFooter>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
