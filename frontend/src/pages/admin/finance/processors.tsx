import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';

interface ProcessorConfig {
  enabled: boolean;
  [key: string]: any;
}

interface ProcessorsData {
  currency: string;
  processors: {
    stripe: ProcessorConfig;
    paypal: ProcessorConfig;
    offline: ProcessorConfig;
  };
}

export default function ProcessorsPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  const [data, setData] = useState<ProcessorsData>({
    currency: 'USD',
    processors: {
      stripe: { enabled: false, public_key: '', secret_key: '' },
      paypal: { enabled: false, client_id: '', client_secret: '' },
      offline: { enabled: true, instructions: '' },
    }
  });

  const fetchProcessors = async () => {
    setIsLoading(true);
    try {
      // In case endpoint returns something different, we provide a fallback
      const result = await apiClient.get<ProcessorsData>('/api/admin/finance/processors');
      if (result && result.processors) {
        setData(result);
      }
    } catch (error) {
      toast.error('Failed to fetch processors');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProcessors();
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await apiClient.put('/api/admin/finance/processors', data);
      toast.success('Payment processors updated');
    } catch (error) {
      toast.error('Failed to save processors');
      console.error(error);
    } finally {
      setIsSaving(false);
    }
  };

  const updateProcessor = (processor: keyof ProcessorsData['processors'], field: string, value: any) => {
    setData((prev) => ({
      ...prev,
      processors: {
        ...prev.processors,
        [processor]: {
          ...prev.processors[processor],
          [field]: value
        }
      }
    }));
  };

  if (isLoading) {
    return <div className="p-6 text-center text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Payment Processors</h1>
          <p className="text-muted-foreground">Configure payment gateways and methods.</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Label className="whitespace-nowrap">Global Currency</Label>
            <Select 
              value={data.currency} 
              onValueChange={(val) => setData((prev) => ({ ...prev, currency: val }))}
            >
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="Currency" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="USD">USD ($)</SelectItem>
                <SelectItem value="EUR">EUR (€)</SelectItem>
                <SelectItem value="GBP">GBP (£)</SelectItem>
                <SelectItem value="AUD">AUD ($)</SelectItem>
                <SelectItem value="CAD">CAD ($)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save All Changes'}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        
        {/* Stripe Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Stripe</CardTitle>
                <CardDescription>Credit card processing</CardDescription>
              </div>
              <Switch 
                checked={data.processors.stripe.enabled}
                onCheckedChange={(checked) => updateProcessor('stripe', 'enabled', checked)}
              />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Publishable Key</Label>
              <Input 
                type="text" 
                placeholder="pk_test_..."
                value={data.processors.stripe.public_key || ''}
                onChange={(e) => updateProcessor('stripe', 'public_key', e.target.value)}
                disabled={!data.processors.stripe.enabled}
              />
            </div>
            <div className="space-y-2">
              <Label>Secret Key</Label>
              <Input 
                type="password" 
                placeholder="sk_test_..."
                value={data.processors.stripe.secret_key || ''}
                onChange={(e) => updateProcessor('stripe', 'secret_key', e.target.value)}
                disabled={!data.processors.stripe.enabled}
              />
            </div>
          </CardContent>
        </Card>

        {/* PayPal Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>PayPal</CardTitle>
                <CardDescription>PayPal checkout integration</CardDescription>
              </div>
              <Switch 
                checked={data.processors.paypal.enabled}
                onCheckedChange={(checked) => updateProcessor('paypal', 'enabled', checked)}
              />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Client ID</Label>
              <Input 
                type="text" 
                placeholder="PayPal Client ID"
                value={data.processors.paypal.client_id || ''}
                onChange={(e) => updateProcessor('paypal', 'client_id', e.target.value)}
                disabled={!data.processors.paypal.enabled}
              />
            </div>
            <div className="space-y-2">
              <Label>Client Secret</Label>
              <Input 
                type="password" 
                placeholder="PayPal Client Secret"
                value={data.processors.paypal.client_secret || ''}
                onChange={(e) => updateProcessor('paypal', 'client_secret', e.target.value)}
                disabled={!data.processors.paypal.enabled}
              />
            </div>
          </CardContent>
        </Card>

        {/* Offline / Cash Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Offline / Cash</CardTitle>
                <CardDescription>Manual payment processing</CardDescription>
              </div>
              <Switch 
                checked={data.processors.offline.enabled}
                onCheckedChange={(checked) => updateProcessor('offline', 'enabled', checked)}
              />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Payment Instructions</Label>
              <Textarea 
                placeholder="e.g. Please pay in cash upon arrival."
                rows={4}
                value={data.processors.offline.instructions || ''}
                onChange={(e) => updateProcessor('offline', 'instructions', e.target.value)}
                disabled={!data.processors.offline.enabled}
              />
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
