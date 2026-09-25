import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { MobilePageShell, MobileBackButton } from '@/components/ui/mobile-page-shell';
import { apiClient } from '@/lib/api';
import { Plus, RefreshCw, Save } from 'lucide-react';
import { toast } from 'sonner';

interface TaxRate {
  id?: number;
  name: string;
  rate: number;
  is_active: boolean;
}

export default function TaxRatesPage() {
  const [taxRates, setTaxRates] = useState<TaxRate[]>([]);
  const [selectedRate, setSelectedRate] = useState<TaxRate | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isMobileDetailOpen, setIsMobileDetailOpen] = useState(false);

  // Form state
  const [formData, setFormData] = useState<TaxRate>({
    name: '',
    rate: 0,
    is_active: true,
  });

  const fetchTaxRates = async () => {
    setIsLoading(true);
    try {
      const data = await apiClient.get<any>('/api/admin/tax-rates');
      setTaxRates(Array.isArray(data) ? data : (data?.data || []));
    } catch (error) {
      toast.error('Failed to fetch tax rates');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTaxRates();
  }, []);

  const handleSelectRate = (rate: TaxRate) => {
    setSelectedRate(rate);
    setFormData(rate);
    setIsMobileDetailOpen(true);
  };

  const handleCreateNew = () => {
    setSelectedRate(null);
    setFormData({
      name: '',
      rate: 0,
      is_active: true,
    });
    setIsMobileDetailOpen(true);
  };

  const handleCloseDetail = () => {
    setIsMobileDetailOpen(false);
  };

  const handleSave = async () => {
    if (!formData.name) {
      toast.error('Name is required');
      return;
    }

    setIsSaving(true);
    try {
      if (selectedRate?.id) {
        await apiClient.put(`/api/admin/tax-rates/${selectedRate.id}`, formData);
        toast.success('Tax rate updated');
      } else {
        await apiClient.post('/api/admin/tax-rates', formData);
        toast.success('Tax rate created');
      }
      fetchTaxRates();
      setIsMobileDetailOpen(false);
      setSelectedRate(null);
    } catch (error) {
      toast.error('Failed to save tax rate');
      console.error(error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <MobilePageShell
      title="Tax Rates"
      description="Configure tax rates applicable to bookings, products, and services"
      actions={
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchTaxRates}
            className="h-10 min-h-[44px] flex-1 sm:flex-initial touch-manipulation gap-1.5"
          >
            <RefreshCw className={isLoading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <Button
            size="sm"
            onClick={handleCreateNew}
            className="h-10 min-h-[44px] flex-1 sm:flex-initial touch-manipulation gap-1.5"
          >
            <Plus className="h-4 w-4" />
            <span>New Rate</span>
          </Button>
        </div>
      }
    >
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 min-w-0">
        {/* Left Side: Tax Rates List (hidden on mobile when editing/creating) */}
        <div className={`col-span-1 md:col-span-5 ${isMobileDetailOpen ? 'hidden md:block' : 'block'}`}>
          <Card className="shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base sm:text-lg">Tax Rates List</CardTitle>
                  <CardDescription className="text-xs">Select to view or edit details</CardDescription>
                </div>
                <Badge variant="secondary" className="text-xs">
                  {taxRates.length} configured
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="p-0 sm:p-4">
              {isLoading ? (
                <div className="p-8 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  <span>Loading tax rates...</span>
                </div>
              ) : taxRates.length === 0 ? (
                <div className="p-8 text-center text-sm text-muted-foreground">
                  No tax rates found. Tap "New Rate" to add one.
                </div>
              ) : (
                <div className="divide-y md:divide-y-0">
                  {/* Desktop Table View */}
                  <div className="hidden md:block">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Name</TableHead>
                          <TableHead>Rate</TableHead>
                          <TableHead>Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {taxRates.map((rate) => (
                          <TableRow 
                            key={rate.id} 
                            className={`cursor-pointer hover:bg-muted/50 ${selectedRate?.id === rate.id ? 'bg-muted font-medium' : ''}`}
                            onClick={() => handleSelectRate(rate)}
                          >
                            <TableCell className="font-medium">{rate.name}</TableCell>
                            <TableCell>{rate.rate}%</TableCell>
                            <TableCell>
                              <Badge variant={rate.is_active ? 'default' : 'secondary'}>
                                {rate.is_active ? 'Active' : 'Inactive'}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  {/* Mobile Tap-Safe List Items */}
                  <div className="md:hidden divide-y">
                    {taxRates.map((rate) => (
                      <div
                        key={rate.id}
                        onClick={() => handleSelectRate(rate)}
                        className={`p-3.5 flex items-center justify-between touch-manipulation active:bg-accent/50 cursor-pointer ${
                          selectedRate?.id === rate.id ? 'bg-muted/60' : ''
                        }`}
                      >
                        <div>
                          <p className="font-semibold text-sm text-foreground">{rate.name}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">{rate.rate}% tax</p>
                        </div>
                        <Badge variant={rate.is_active ? 'default' : 'secondary'} className="text-xs">
                          {rate.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Side: Form (visible on mobile when item selected or new rate clicked) */}
        <div className={`col-span-1 md:col-span-7 ${isMobileDetailOpen ? 'block' : 'hidden md:block'}`}>
          <Card className="shadow-xs">
            <CardHeader className="pb-4">
              <div className="md:hidden mb-2">
                <MobileBackButton label="Tax Rates" onClick={handleCloseDetail} />
              </div>
              <CardTitle className="text-base sm:text-lg">
                {selectedRate ? `Edit "${selectedRate.name}"` : 'Create Tax Rate'}
              </CardTitle>
              <CardDescription className="text-xs">
                {selectedRate ? 'Update percentage rate and availability' : 'Configure a new jurisdiction tax or surcharge'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="tax-name" className="text-xs font-semibold uppercase tracking-wider">
                  Name <span className="text-destructive">*</span>
                </Label>
                <Input 
                  id="tax-name" 
                  placeholder="e.g. VAT, GST, State Sales Tax" 
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="h-11 min-h-[44px]"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="tax-rate" className="text-xs font-semibold uppercase tracking-wider">Rate (%)</Label>
                <Input 
                  id="tax-rate" 
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="0.00"
                  value={formData.rate}
                  onChange={(e) => setFormData({ ...formData, rate: parseFloat(e.target.value) || 0 })}
                  className="h-11 min-h-[44px]"
                />
              </div>

              <div className="flex items-center justify-between p-3 rounded-lg border bg-muted/20">
                <div className="space-y-0.5">
                  <Label htmlFor="tax-active" className="text-sm font-medium cursor-pointer">Active Status</Label>
                  <p className="text-xs text-muted-foreground">Enabled rates are automatically calculated on invoices</p>
                </div>
                <Switch 
                  id="tax-active" 
                  checked={formData.is_active}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                  className="touch-manipulation"
                />
              </div>
            </CardContent>
            <CardFooter className="flex flex-col-reverse sm:flex-row justify-end gap-2 pt-2 border-t mt-4">
              <Button 
                variant="outline" 
                onClick={handleCloseDetail}
                className="h-11 min-h-[44px] w-full sm:w-auto touch-manipulation"
              >
                Cancel
              </Button>
              <Button 
                onClick={handleSave} 
                disabled={isSaving}
                className="h-11 min-h-[44px] w-full sm:w-auto touch-manipulation gap-2"
              >
                <Save className="h-4 w-4" />
                <span>{isSaving ? 'Saving...' : 'Save Tax Rate'}</span>
              </Button>
            </CardFooter>
          </Card>
        </div>
      </div>
    </MobilePageShell>
  );
}
