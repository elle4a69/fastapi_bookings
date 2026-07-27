import { useState, useEffect } from 'react';
import { Plus, Search, Edit, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export interface AdditionalField {
  id: string;
  name: string;
  type: 'Text' | 'Textarea' | 'Select' | 'Checkbox';
  entity_type: 'Client' | 'Booking';
  required: boolean;
  placeholder?: string;
  options?: string[];
}

export default function AdditionalFieldsPage() {
  const [fields, setFields] = useState<AdditionalField[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  
  const [formData, setFormData] = useState<Partial<AdditionalField>>({
    name: '',
    type: 'Text',
    entity_type: 'Client',
    required: false,
    placeholder: '',
    options: [],
  });

  const [optionsText, setOptionsText] = useState('');

  const fetchFields = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<AdditionalField[]>('/api/admin/additional-fields');
      setFields(data || []);
    } catch (error) {
      toast.error('Failed to load additional fields');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFields();
  }, []);

  const handleCreateNew = () => {
    setIsCreating(true);
    setIsEditing(true);
    setSelectedFieldId(null);
    setFormData({ 
      name: '', 
      type: 'Text',
      entity_type: 'Client',
      required: false,
      placeholder: '',
      options: [],
    });
    setOptionsText('');
  };

  const handleSelectField = (field: AdditionalField) => {
    setSelectedFieldId(field.id);
    setIsCreating(false);
    setIsEditing(false);
    setFormData({
      name: field.name,
      type: field.type,
      entity_type: field.entity_type,
      required: field.required,
      placeholder: field.placeholder || '',
      options: field.options || [],
    });
    setOptionsText((field.options || []).join('\n'));
  };

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleCancel = () => {
    if (isCreating) {
      setIsCreating(false);
      setIsEditing(false);
    } else if (selectedFieldId) {
      const field = fields.find(f => f.id === selectedFieldId);
      if (field) {
        setFormData({
          name: field.name,
          type: field.type,
          entity_type: field.entity_type,
          required: field.required,
          placeholder: field.placeholder || '',
          options: field.options || [],
        });
        setOptionsText((field.options || []).join('\n'));
      }
      setIsEditing(false);
    }
  };

  const handleSave = async () => {
    if (!formData.name?.trim()) {
      toast.error('Name is required');
      return;
    }
    
    const optionsArray = formData.type === 'Select' 
      ? optionsText.split('\n').map(o => o.trim()).filter(o => o) 
      : [];

    const payload = {
      name: formData.name,
      type: formData.type,
      entity_type: formData.entity_type,
      required: formData.required,
      placeholder: formData.placeholder,
      options: optionsArray,
    };

    try {
      if (isCreating) {
        const newField = await apiClient.post<AdditionalField>('/api/admin/additional-fields', payload);
        setFields([...fields, newField]);
        toast.success('Field created successfully');
        handleSelectField(newField);
      } else if (selectedFieldId) {
        const updatedField = await apiClient.put<AdditionalField>(`/api/admin/additional-fields/${selectedFieldId}`, payload);
        setFields(fields.map(f => f.id === selectedFieldId ? updatedField : f));
        toast.success('Field updated successfully');
        handleSelectField(updatedField);
      }
    } catch (error) {
      toast.error('Failed to save field');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this field?')) return;
    try {
      await apiClient.delete(`/api/admin/additional-fields/${id}`);
      setFields(fields.filter(f => f.id !== id));
      if (selectedFieldId === id) {
        setSelectedFieldId(null);
        setIsEditing(false);
        setIsCreating(false);
      }
      toast.success('Field deleted');
    } catch (error) {
      toast.error('Failed to delete field');
    }
  };

  const filteredFields = fields.filter(f => f.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="flex h-full w-full gap-4">
      {/* Left Pane - List */}
      <div className="w-[35%] flex flex-col gap-4 border-r pr-4">
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-bold">Additional Fields</h2>
          <Button onClick={handleCreateNew} size="sm">
            <Plus className="w-4 h-4 mr-2" /> Add Field
          </Button>
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input 
            placeholder="Search fields..." 
            className="pl-8" 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        
        <div className="flex-1 overflow-y-auto space-y-2">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))
          ) : filteredFields.length === 0 ? (
            <div className="text-center text-muted-foreground py-8">No fields found</div>
          ) : (
            filteredFields.map((field) => (
              <div 
                key={field.id}
                onClick={() => handleSelectField(field)}
                className={`p-3 rounded-md cursor-pointer border transition-colors flex justify-between items-center ${
                  selectedFieldId === field.id 
                    ? 'border-primary bg-primary/10' 
                    : 'border-border hover:bg-muted/50'
                }`}
              >
                <div>
                  <div className="font-medium">{field.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {field.entity_type} • {field.type}
                  </div>
                </div>
                {field.required && (
                  <Badge variant="secondary">Required</Badge>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right Pane - Detail / Form */}
      <div className="w-[65%] flex flex-col pl-4">
        {!selectedFieldId && !isCreating ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            Select a field to view details or create a new one.
          </div>
        ) : (
          <Card className="flex-1 flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>{isCreating ? 'Create Field' : isEditing ? 'Edit Field' : 'Field Details'}</CardTitle>
                <CardDescription>
                  {isCreating ? 'Configure a new additional field.' : 'View and modify field settings.'}
                </CardDescription>
              </div>
              {!isCreating && !isEditing && (
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleEdit}>
                    <Edit className="w-4 h-4 mr-2" /> Edit
                  </Button>
                  <Button variant="destructive" size="sm" onClick={() => handleDelete(selectedFieldId!)}>
                    <Trash2 className="w-4 h-4 mr-2" /> Delete
                  </Button>
                </div>
              )}
            </CardHeader>
            
            <CardContent className="flex-1 space-y-6">
              <div className="space-y-2">
                <Label htmlFor="name">Field Name</Label>
                <Input 
                  id="name" 
                  value={formData.name || ''} 
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  disabled={!isEditing}
                  placeholder="e.g. Emergency Contact"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Type</Label>
                  <Select 
                    disabled={!isEditing} 
                    value={formData.type} 
                    onValueChange={(val: any) => setFormData({ ...formData, type: val })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Text">Text</SelectItem>
                      <SelectItem value="Textarea">Textarea</SelectItem>
                      <SelectItem value="Select">Select</SelectItem>
                      <SelectItem value="Checkbox">Checkbox</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Entity Type</Label>
                  <Select 
                    disabled={!isEditing} 
                    value={formData.entity_type} 
                    onValueChange={(val: any) => setFormData({ ...formData, entity_type: val })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select entity" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Client">Client</SelectItem>
                      <SelectItem value="Booking">Booking</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {formData.type !== 'Checkbox' && (
                <div className="space-y-2">
                  <Label htmlFor="placeholder">Placeholder</Label>
                  <Input 
                    id="placeholder" 
                    value={formData.placeholder || ''} 
                    onChange={(e) => setFormData({ ...formData, placeholder: e.target.value })}
                    disabled={!isEditing}
                    placeholder="Hint text for the user"
                  />
                </div>
              )}

              {formData.type === 'Select' && (
                <div className="space-y-2">
                  <Label htmlFor="options">Options (one per line)</Label>
                  <Textarea 
                    id="options" 
                    value={optionsText} 
                    onChange={(e) => setOptionsText(e.target.value)}
                    disabled={!isEditing}
                    placeholder={"Option 1\nOption 2\nOption 3"}
                    rows={4}
                  />
                </div>
              )}

              <div className="flex items-center space-x-2 pt-2">
                <Switch 
                  id="required" 
                  checked={formData.required} 
                  onCheckedChange={(checked) => setFormData({ ...formData, required: checked })}
                  disabled={!isEditing}
                />
                <Label htmlFor="required">Required Field</Label>
              </div>
            </CardContent>

            {isEditing && (
              <CardFooter className="flex justify-end gap-2 border-t pt-4 mt-auto">
                <Button variant="outline" onClick={handleCancel}>Cancel</Button>
                <Button onClick={handleSave}>Save</Button>
              </CardFooter>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
