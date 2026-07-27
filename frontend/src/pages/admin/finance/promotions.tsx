import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Plus, Save, Tag } from 'lucide-react';
import { toast } from 'sonner';
import { ScrollArea } from '@/components/ui/scroll-area';

interface Service {
  id: string;
  name: string;
}

interface Promotion {
  id: string;
  name: string;
  code: string;
  discount_type: 'Percentage' | 'Fixed Amount';
  value: number;
  active: boolean;
  expires_at: string;
  eligible_services: string[]; // array of service IDs
}

export function PromotionsPage() {
  const [promotions, setPromotions] = useState<Promotion[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [selectedPromoId, setSelectedPromoId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<Promotion>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [promosData, servicesData] = await Promise.all([
        apiClient.get<Promotion[]>('/api/admin/finance/promotions').catch(() => []),
        apiClient.get<Service[]>('/api/admin/services').catch(() => []) // Adjust endpoint if needed
      ]);
      setPromotions(promosData);
      setServices(servicesData);
      if (promosData.length > 0) {
        handleSelectPromo(promosData[0]);
      }
    } catch (error) {
      toast.error('Failed to load data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPromo = (promo: Promotion) => {
    setSelectedPromoId(promo.id);
    setFormData({
      ...promo,
      expires_at: promo.expires_at ? new Date(promo.expires_at).toISOString().split('T')[0] : ''
    });
  };

  const handleCreateNew = () => {
    setSelectedPromoId(null);
    setFormData({
      name: '',
      code: '',
      discount_type: 'Percentage',
      value: 0,
      active: true,
      expires_at: '',
      eligible_services: []
    });
  };

  const handleSave = async () => {
    if (!formData.name || !formData.code || formData.value === undefined) {
      toast.error('Please fill in all required fields');
      return;
    }

    try {
      setSaving(true);
      const payload = {
        ...formData,
        code: formData.code.toUpperCase()
      };

      if (selectedPromoId) {
        await apiClient.put(`/api/admin/finance/promotions/${selectedPromoId}`, payload);
        toast.success('Promotion updated successfully');
      } else {
        await apiClient.post('/api/admin/finance/promotions', payload);
        toast.success('Promotion created successfully');
      }
      fetchData();
    } catch (error) {
      toast.error('Failed to save promotion');
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  const toggleService = (serviceId: string) => {
    const currentServices = formData.eligible_services || [];
    if (currentServices.includes(serviceId)) {
      setFormData({ ...formData, eligible_services: currentServices.filter(id => id !== serviceId) });
    } else {
      setFormData({ ...formData, eligible_services: [...currentServices, serviceId] });
    }
  };

  const toggleAllServices = (checked: boolean) => {
    if (checked) {
      setFormData({ ...formData, eligible_services: services.map(s => s.id) });
    } else {
      setFormData({ ...formData, eligible_services: [] });
    }
  };

  return (
    <div className="p-6 h-[calc(100vh-4rem)] flex flex-col space-y-6">
      <div className="flex justify-between items-center shrink-0">
        <h1 className="text-3xl font-bold tracking-tight">Promotions</h1>
        <Button onClick={handleCreateNew}>
          <Plus className="mr-2 h-4 w-4" />
          New Promotion
        </Button>
      </div>

      <div className="flex gap-6 flex-1 min-h-0">
        {/* Master List (Sidebar) */}
        <Card className="w-1/3 flex flex-col min-h-0">
          <CardHeader className="pb-3 shrink-0">
            <CardTitle>Active Promotions</CardTitle>
            <CardDescription>Manage discount codes and offers</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 overflow-auto p-0">
            {loading ? (
              <div className="p-4 text-center text-muted-foreground">Loading...</div>
            ) : promotions.length === 0 ? (
              <div className="p-4 text-center text-muted-foreground">No promotions found.</div>
            ) : (
              <div className="flex flex-col">
                {promotions.map(promo => (
                  <button
                    key={promo.id}
                    onClick={() => handleSelectPromo(promo)}
                    className={`flex items-start text-left p-4 border-b hover:bg-muted/50 transition-colors ${
                      selectedPromoId === promo.id ? 'bg-muted border-l-4 border-l-primary' : ''
                    }`}
                  >
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold">{promo.name}</span>
                        {promo.active ? (
                          <Badge variant="default" className="text-[10px]">Active</Badge>
                        ) : (
                          <Badge variant="secondary" className="text-[10px]">Inactive</Badge>
                        )}
                      </div>
                      <div className="flex items-center text-sm text-muted-foreground">
                        <Tag className="h-3 w-3 mr-1" />
                        <span className="font-mono">{promo.code}</span>
                      </div>
                      <div className="text-sm mt-2">
                        {promo.discount_type === 'Percentage' ? `${promo.value}% off` : `$${promo.value} off`}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Detail View */}
        <Card className="flex-1 flex flex-col min-h-0">
          <CardHeader className="shrink-0 border-b">
            <CardTitle>{selectedPromoId ? 'Edit Promotion' : 'Create Promotion'}</CardTitle>
          </CardHeader>
          
          <ScrollArea className="flex-1">
            <CardContent className="p-6 space-y-8">
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label htmlFor="name">Promotion Name</Label>
                  <Input 
                    id="name" 
                    placeholder="e.g. Summer Sale" 
                    value={formData.name || ''} 
                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="code">Promo Code</Label>
                  <Input 
                    id="code" 
                    placeholder="e.g. SUMMER2026" 
                    className="uppercase font-mono"
                    value={formData.code || ''} 
                    onChange={e => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="discountType">Discount Type</Label>
                  <Select 
                    value={formData.discount_type} 
                    onValueChange={(val: 'Percentage' | 'Fixed Amount') => setFormData({ ...formData, discount_type: val })}
                  >
                    <SelectTrigger id="discountType">
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Percentage">Percentage (%)</SelectItem>
                      <SelectItem value="Fixed Amount">Fixed Amount ($)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="value">Discount Value</Label>
                  <Input 
                    id="value" 
                    type="number" 
                    min="0"
                    step="0.01"
                    value={formData.value || ''} 
                    onChange={e => setFormData({ ...formData, value: parseFloat(e.target.value) || 0 })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="expiresAt">Expiration Date</Label>
                  <Input 
                    id="expiresAt" 
                    type="date" 
                    value={formData.expires_at || ''} 
                    onChange={e => setFormData({ ...formData, expires_at: e.target.value })}
                  />
                </div>

                <div className="flex items-center space-x-2 pt-8">
                  <Switch 
                    id="active" 
                    checked={formData.active !== false}
                    onCheckedChange={checked => setFormData({ ...formData, active: checked })}
                  />
                  <Label htmlFor="active">Active Promotion</Label>
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex justify-between items-center border-b pb-2">
                  <div className="space-y-1">
                    <h3 className="font-medium leading-none">Eligible Services</h3>
                    <p className="text-sm text-muted-foreground">Select which services this promotion applies to.</p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox 
                      id="selectAll" 
                      checked={formData.eligible_services?.length === services.length && services.length > 0}
                      onCheckedChange={(checked) => toggleAllServices(checked as boolean)}
                    />
                    <Label htmlFor="selectAll" className="font-normal cursor-pointer">Select All</Label>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4 bg-muted/30 p-4 rounded-md border">
                  {services.length === 0 ? (
                    <div className="col-span-2 text-sm text-muted-foreground italic">No services available.</div>
                  ) : (
                    services.map(service => (
                      <div key={service.id} className="flex items-center space-x-2">
                        <Checkbox 
                          id={`service-${service.id}`} 
                          checked={formData.eligible_services?.includes(service.id) || false}
                          onCheckedChange={() => toggleService(service.id)}
                        />
                        <Label htmlFor={`service-${service.id}`} className="font-normal cursor-pointer">
                          {service.name}
                        </Label>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </CardContent>
          </ScrollArea>
          
          <div className="p-6 border-t mt-auto shrink-0 flex justify-end">
            <Button onClick={handleSave} disabled={saving}>
              <Save className="mr-2 h-4 w-4" />
              {saving ? 'Saving...' : 'Save Promotion'}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default PromotionsPage;
