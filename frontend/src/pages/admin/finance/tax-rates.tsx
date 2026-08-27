import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { apiClient } from '@/lib/api';
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

  // Form state
  const [formData, setFormData] = useState<TaxRate>({
    name: '',
    rate: 0,
    is_active: true,
  });

  const fetchTaxRates = async () => {
    setIsLoading(true);
    try {
      const data = await apiClient.get<TaxRate[]>('/api/admin/finance/tax-rates');
      setTaxRates(Array.isArray(data) ? data : []);
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
  };

  const handleCreateNew = () => {
    setSelectedRate(null);
    setFormData({
      name: '',
      rate: 0,
      is_active: true,
    });
  };

  const handleSave = async () => {
    if (!formData.name) {
      toast.error('Name is required');
      return;
    }

    setIsSaving(true);
    try {
      if (selectedRate?.id) {
        await apiClient.put(`/api/admin/finance/tax-rates/${selectedRate.id}`, formData);
        toast.success('Tax rate updated');
      } else {
        await apiClient.post('/api/admin/finance/tax-rates', formData);
        toast.success('Tax rate created');
      }
      fetchTaxRates();
      handleCreateNew();
    } catch (error) {
      toast.error('Failed to save tax rate');
      console.error(error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Tax Rates</h1>
        <p className="text-muted-foreground">Manage applicable tax rates for your bookings.</p>
      </div>

      <div className="flex flex-col md:flex-row gap-6">
        {/* Left Side: Table (35%) */}
        <Card className="w-full md:w-[35%] flex flex-col">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Tax Rates List</CardTitle>
                <CardDescription>All configured tax rates</CardDescription>
              </div>
              <Button size="sm" onClick={handleCreateNew}>New</Button>
            </div>
          </CardHeader>
          <CardContent className="flex-1">
            {isLoading ? (
              <div className="p-4 text-center text-sm text-muted-foreground">Loading...</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Rate</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {taxRates.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={3} className="text-center text-muted-foreground">
                        No tax rates found
                      </TableCell>
                    </TableRow>
                  ) : (
                    taxRates.map((rate) => (
                      <TableRow 
                        key={rate.id} 
                        className={`cursor-pointer hover:bg-muted/50 ${selectedRate?.id === rate.id ? 'bg-muted' : ''}`}
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
                    ))
                  )}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Right Side: Form (65%) */}
        <Card className="w-full md:w-[65%]">
          <CardHeader>
            <CardTitle>{selectedRate ? 'Edit Tax Rate' : 'Create Tax Rate'}</CardTitle>
            <CardDescription>
              {selectedRate ? 'Modify the selected tax rate.' : 'Add a new tax rate.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name <span className="text-red-500">*</span></Label>
              <Input 
                id="name" 
                placeholder="e.g. VAT, Sales Tax" 
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="rate">Rate (%)</Label>
              <Input 
                id="rate" 
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
                value={formData.rate}
                onChange={(e) => setFormData({ ...formData, rate: parseFloat(e.target.value) || 0 })}
              />
            </div>

            <div className="flex items-center space-x-2 pt-2">
              <Switch 
                id="active" 
                checked={formData.is_active}
                onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
              />
              <Label htmlFor="active">Active</Label>
            </div>
          </CardContent>
          <CardFooter className="flex justify-end gap-2">
            <Button variant="outline" onClick={handleCreateNew}>Cancel</Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? 'Saving...' : 'Save'}
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
