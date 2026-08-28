import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';

interface PaymentProcessorConfig {
  id?: number;
  provider: string;
  enabled: boolean;
  display_name?: string | null;
  public_key?: string | null;
  config_json?: string | null;
}

interface ProcessorFormState {
  id?: number;
  enabled: boolean;
  public_key: string;
  secret_key: string;
  client_id: string;
  client_secret: string;
  instructions: string;
}

export default function ProcessorsPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  const [stripeState, setStripeState] = useState<ProcessorFormState>({
    enabled: false,
    public_key: '',
    secret_key: '',
    client_id: '',
    client_secret: '',
    instructions: '',
  });

  const [paypalState, setPaypalState] = useState<ProcessorFormState>({
    enabled: false,
    public_key: '',
    secret_key: '',
    client_id: '',
    client_secret: '',
    instructions: '',
  });

  const [offlineState, setOfflineState] = useState<ProcessorFormState>({
    enabled: true,
    public_key: '',
    secret_key: '',
    client_id: '',
    client_secret: '',
    instructions: '',
  });

  const parseConfigJson = (jsonStr?: string | null): Record<string, any> => {
    if (!jsonStr) return {};
    try {
      return JSON.parse(jsonStr);
    } catch {
      return {};
    }
  };

  const fetchProcessors = async () => {
    setIsLoading(true);
    try {
      const res = await apiClient.get<PaymentProcessorConfig[] | { data: PaymentProcessorConfig[] }>(
        '/api/admin/payment-processor/configs'
      );
      const list: PaymentProcessorConfig[] = Array.isArray(res) ? res : (res as any)?.data || [];
      
      const stripeConfig = list.find((c) => c.provider === 'stripe');
      if (stripeConfig) {
        const parsed = parseConfigJson(stripeConfig.config_json);
        setStripeState({
          id: stripeConfig.id,
          enabled: stripeConfig.enabled,
          public_key: stripeConfig.public_key || '',
          secret_key: parsed.secret_key || '',
          client_id: '',
          client_secret: '',
          instructions: '',
        });
      }

      const paypalConfig = list.find((c) => c.provider === 'paypal');
      if (paypalConfig) {
        const parsed = parseConfigJson(paypalConfig.config_json);
        setPaypalState({
          id: paypalConfig.id,
          enabled: paypalConfig.enabled,
          public_key: '',
          secret_key: '',
          client_id: parsed.client_id || '',
          client_secret: parsed.client_secret || '',
          instructions: '',
        });
      }

      const offlineConfig = list.find((c) => c.provider === 'offline');
      if (offlineConfig) {
        const parsed = parseConfigJson(offlineConfig.config_json);
        setOfflineState({
          id: offlineConfig.id,
          enabled: offlineConfig.enabled,
          public_key: '',
          secret_key: '',
          client_id: '',
          client_secret: '',
          instructions: parsed.instructions || '',
        });
      }
    } catch (error) {
      toast.error('Failed to fetch payment processor configurations');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProcessors();
  }, []);

  const saveProcessorConfig = async (
    provider: string,
    state: ProcessorFormState,
    displayName: string
  ) => {
    let configJson = '{}';
    if (provider === 'stripe') {
      configJson = JSON.stringify({ secret_key: state.secret_key });
    } else if (provider === 'paypal') {
      configJson = JSON.stringify({ client_id: state.client_id, client_secret: state.client_secret });
    } else if (provider === 'offline') {
      configJson = JSON.stringify({ instructions: state.instructions });
    }

    const payload = {
      provider,
      enabled: state.enabled,
      display_name: displayName,
      public_key: provider === 'stripe' ? state.public_key : null,
      config_json: configJson,
    };

    if (state.id) {
      const res: any = await apiClient.put(`/api/admin/payment-processor/configs/${state.id}`, {
        enabled: payload.enabled,
        display_name: payload.display_name,
        public_key: payload.public_key,
        config_json: payload.config_json,
      });
      return res?.id || state.id;
    } else {
      const res: any = await apiClient.post('/api/admin/payment-processor/configs', payload);
      return res?.id || res?.data?.id;
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const [stripeId, paypalId, offlineId] = await Promise.all([
        saveProcessorConfig('stripe', stripeState, 'Stripe'),
        saveProcessorConfig('paypal', paypalState, 'PayPal'),
        saveProcessorConfig('offline', offlineState, 'Offline / Cash'),
      ]);

      if (stripeId) setStripeState((prev) => ({ ...prev, id: stripeId }));
      if (paypalId) setPaypalState((prev) => ({ ...prev, id: paypalId }));
      if (offlineId) setOfflineState((prev) => ({ ...prev, id: offlineId }));

      toast.success('Payment processor configurations saved successfully');
    } catch (error) {
      toast.error('Failed to save payment processor configurations');
      console.error(error);
    } finally {
      setIsSaving(false);
    }
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
                checked={stripeState.enabled}
                onCheckedChange={(checked) => setStripeState((prev) => ({ ...prev, enabled: checked }))}
              />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Publishable Key</Label>
              <Input 
                type="text" 
                placeholder="pk_test_..."
                value={stripeState.public_key}
                onChange={(e) => setStripeState((prev) => ({ ...prev, public_key: e.target.value }))}
                disabled={!stripeState.enabled}
              />
            </div>
            <div className="space-y-2">
              <Label>Secret Key</Label>
              <Input 
                type="password" 
                placeholder="sk_test_..."
                value={stripeState.secret_key}
                onChange={(e) => setStripeState((prev) => ({ ...prev, secret_key: e.target.value }))}
                disabled={!stripeState.enabled}
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
                checked={paypalState.enabled}
                onCheckedChange={(checked) => setPaypalState((prev) => ({ ...prev, enabled: checked }))}
              />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Client ID</Label>
              <Input 
                type="text" 
                placeholder="PayPal Client ID"
                value={paypalState.client_id}
                onChange={(e) => setPaypalState((prev) => ({ ...prev, client_id: e.target.value }))}
                disabled={!paypalState.enabled}
              />
            </div>
            <div className="space-y-2">
              <Label>Client Secret</Label>
              <Input 
                type="password" 
                placeholder="PayPal Client Secret"
                value={paypalState.client_secret}
                onChange={(e) => setPaypalState((prev) => ({ ...prev, client_secret: e.target.value }))}
                disabled={!paypalState.enabled}
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
                checked={offlineState.enabled}
                onCheckedChange={(checked) => setOfflineState((prev) => ({ ...prev, enabled: checked }))}
              />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Payment Instructions</Label>
              <Textarea 
                placeholder="e.g. Please pay in cash upon arrival."
                rows={4}
                value={offlineState.instructions}
                onChange={(e) => setOfflineState((prev) => ({ ...prev, instructions: e.target.value }))}
                disabled={!offlineState.enabled}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
