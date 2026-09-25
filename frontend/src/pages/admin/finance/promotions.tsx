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
import { MobilePageShell, MobileBackButton } from '@/components/ui/mobile-page-shell';
import { Plus, Save, Tag, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

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
  eligible_services: string[];
}

export function PromotionsPage() {
  const [promotions, setPromotions] = useState<Promotion[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [selectedPromoId, setSelectedPromoId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<Promotion>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isMobileDetailOpen, setIsMobileDetailOpen] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [promosData, servicesData] = await Promise.all([
        apiClient.get<any>('/api/admin/promotions').catch(() => []),
        apiClient.get<any>('/api/admin/services').catch(() => [])
      ]);
      const pList = Array.isArray(promosData) ? promosData : (promosData?.data || []);
      const sList = Array.isArray(servicesData) ? servicesData : (servicesData?.data || []);
      setPromotions(pList);
      setServices(sList);
      if (pList.length > 0 && !selectedPromoId) {
        handleSelectPromo(pList[0], false);
      }
    } catch (error) {
      toast.error('Failed to load promotions data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPromo = (promo: Promotion, openMobile = true) => {
    setSelectedPromoId(promo.id);
    setFormData({
      ...promo,
      expires_at: promo.expires_at ? new Date(promo.expires_at).toISOString().split('T')[0] : ''
    });
    if (openMobile) {
      setIsMobileDetailOpen(true);
    }
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
    setIsMobileDetailOpen(true);
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
        await apiClient.put(`/api/admin/promotions/${selectedPromoId}`, payload);
        toast.success('Promotion updated successfully');
      } else {
        await apiClient.post('/api/admin/promotions', payload);
        toast.success('Promotion created successfully');
      }
      fetchData();
      setIsMobileDetailOpen(false);
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
    <MobilePageShell
      title="Promotions"
      description="Create and manage coupon discount codes, percentage deals, and service-level offers"
      actions={
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchData}
            className="h-10 min-h-[44px] flex-1 sm:flex-initial touch-manipulation gap-1.5"
          >
            <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <Button
            size="sm"
            onClick={handleCreateNew}
            className="h-10 min-h-[44px] flex-1 sm:flex-initial touch-manipulation gap-1.5"
          >
            <Plus className="h-4 w-4" />
            <span>New Promotion</span>
          </Button>
        </div>
      }
    >
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 min-w-0">
        {/* Master Promotion List */}
        <div className={`col-span-1 md:col-span-4 ${isMobileDetailOpen ? 'hidden md:block' : 'block'}`}>
          <Card className="shadow-xs">
            <CardHeader className="pb-3 border-b">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base sm:text-lg">Promo Codes</CardTitle>
                  <CardDescription className="text-xs">Select code to view details</CardDescription>
                </div>
                <Badge variant="secondary" className="text-xs">{promotions.length}</Badge>
              </div>
            </CardHeader>
            <CardContent className="p-0 max-h-[calc(100vh-280px)] overflow-y-auto">
              {loading ? (
                <div className="p-8 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  <span>Loading promotions...</span>
                </div>
              ) : promotions.length === 0 ? (
                <div className="p-8 text-center text-sm text-muted-foreground">
                  No promotions found. Click "New Promotion" to create one.
                </div>
              ) : (
                <div className="divide-y">
                  {promotions.map(promo => (
                    <div
                      key={promo.id}
                      onClick={() => handleSelectPromo(promo, true)}
                      className={`flex items-start text-left p-3.5 sm:p-4 hover:bg-muted/50 transition-colors cursor-pointer touch-manipulation ${
                        selectedPromoId === promo.id ? 'bg-muted/70 border-l-4 border-l-primary' : ''
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="font-semibold text-sm truncate text-foreground">{promo.name}</span>
                          {promo.active ? (
                            <Badge variant="default" className="text-[10px] shrink-0">Active</Badge>
                          ) : (
                            <Badge variant="secondary" className="text-[10px] shrink-0">Inactive</Badge>
                          )}
                        </div>
                        <div className="flex items-center text-xs text-muted-foreground">
                          <Tag className="h-3 w-3 mr-1 shrink-0" />
                          <span className="font-mono font-semibold text-primary">{promo.code}</span>
                        </div>
                        <div className="text-xs font-medium text-foreground mt-1.5">
                          {promo.discount_type === 'Percentage' ? `${promo.value}% discount` : `$${promo.value} discount`}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Promotion Detail / Editor View */}
        <div className={`col-span-1 md:col-span-8 ${isMobileDetailOpen ? 'block' : 'hidden md:block'}`}>
          <Card className="shadow-xs">
            <CardHeader className="border-b pb-4">
              <div className="md:hidden mb-2">
                <MobileBackButton label="Promotions" onClick={() => setIsMobileDetailOpen(false)} />
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                  <CardTitle className="text-base sm:text-lg">
                    {selectedPromoId ? `Edit "${formData.name || 'Promotion'}"` : 'Create New Promotion'}
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Define discount logic, redemption criteria, and eligible services
                  </CardDescription>
                </div>
                <Button
                  onClick={handleSave}
                  disabled={saving}
                  className="h-10 min-h-[44px] w-full sm:w-auto touch-manipulation gap-2"
                >
                  <Save className="h-4 w-4" />
                  <span>{saving ? 'Saving...' : 'Save Promotion'}</span>
                </Button>
              </div>
            </CardHeader>
            
            <CardContent className="p-4 sm:p-6 space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="promo-name" className="text-xs font-semibold uppercase tracking-wider">Promotion Name</Label>
                  <Input 
                    id="promo-name" 
                    placeholder="e.g. Summer Flash Sale" 
                    value={formData.name || ''} 
                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                    className="h-11 min-h-[44px]"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="promo-code" className="text-xs font-semibold uppercase tracking-wider">Promo Code</Label>
                  <Input 
                    id="promo-code" 
                    placeholder="e.g. SUMMER2026" 
                    className="uppercase font-mono font-bold h-11 min-h-[44px]"
                    value={formData.code || ''} 
                    onChange={e => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="discount-type" className="text-xs font-semibold uppercase tracking-wider">Discount Type</Label>
                  <Select 
                    value={formData.discount_type} 
                    onValueChange={(val: 'Percentage' | 'Fixed Amount') => setFormData({ ...formData, discount_type: val })}
                  >
                    <SelectTrigger id="discount-type" className="h-11 min-h-[44px]">
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Percentage">Percentage (%)</SelectItem>
                      <SelectItem value="Fixed Amount">Fixed Amount ($)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="promo-value" className="text-xs font-semibold uppercase tracking-wider">Discount Value</Label>
                  <Input 
                    id="promo-value" 
                    type="number" 
                    min="0"
                    step="0.01"
                    value={formData.value ?? ''} 
                    onChange={e => setFormData({ ...formData, value: parseFloat(e.target.value) || 0 })}
                    className="h-11 min-h-[44px]"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="promo-expires" className="text-xs font-semibold uppercase tracking-wider">Expiration Date</Label>
                  <Input 
                    id="promo-expires" 
                    type="date" 
                    value={formData.expires_at || ''} 
                    onChange={e => setFormData({ ...formData, expires_at: e.target.value })}
                    className="h-11 min-h-[44px]"
                  />
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg border bg-muted/20">
                  <div className="space-y-0.5">
                    <Label htmlFor="promo-active" className="text-sm font-medium cursor-pointer">Active</Label>
                    <p className="text-xs text-muted-foreground">Code is currently redeemable</p>
                  </div>
                  <Switch 
                    id="promo-active" 
                    checked={formData.active !== false}
                    onCheckedChange={checked => setFormData({ ...formData, active: checked })}
                    className="touch-manipulation"
                  />
                </div>
              </div>

              {/* Service Eligibility Section */}
              <div className="space-y-3 pt-2 border-t">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-xs font-semibold uppercase tracking-wider">Eligible Services</Label>
                    <p className="text-xs text-muted-foreground mt-0.5">Select which catalog services this discount applies to</p>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => toggleAllServices((formData.eligible_services?.length || 0) < services.length)}
                    className="text-xs h-9 min-h-[36px] touch-manipulation"
                  >
                    {(formData.eligible_services?.length || 0) === services.length ? 'Deselect All' : 'Select All'}
                  </Button>
                </div>
                
                <div className="border rounded-md p-3 max-h-48 overflow-y-auto space-y-2 bg-muted/10">
                  {services.map(svc => {
                    const isChecked = formData.eligible_services?.includes(svc.id) ?? false;
                    return (
                      <label 
                        key={svc.id} 
                        className="flex items-center space-x-3 p-1.5 rounded hover:bg-muted/40 cursor-pointer touch-manipulation"
                      >
                        <Checkbox 
                          checked={isChecked}
                          onCheckedChange={() => toggleService(svc.id)}
                          className="h-5 w-5 rounded border-muted-foreground"
                        />
                        <span className="text-sm font-normal select-none">{svc.name}</span>
                      </label>
                    );
                  })}
                  {services.length === 0 && (
                    <p className="text-xs text-muted-foreground p-2">No services found.</p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </MobilePageShell>
  );
}

export default PromotionsPage;
