import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { MobilePageShell } from '@/components/ui/mobile-page-shell';
import { apiClient } from '@/lib/api';
import { Save, RefreshCw, CreditCard, Banknote, HelpCircle } from 'lucide-react';
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

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const payloads = [
        {
          provider: 'stripe',
          enabled: stripeState.enabled,
          display_name: 'Stripe',
          public_key: stripeState.public_key,
          config_json: JSON.stringify({ secret_key: stripeState.secret_key }),
        },
        {
          provider: 'paypal',
          enabled: paypalState.enabled,
          display_name: 'PayPal',
          public_key: null,
          config_json: JSON.stringify({
            client_id: paypalState.client_id,
            client_secret: paypalState.client_secret,
          }),
        },
        {
          provider: 'offline',
          enabled: offlineState.enabled,
          display_name: 'Offline Payment',
          public_key: null,
          config_json: JSON.stringify({ instructions: offlineState.instructions }),
        },
      ];

      await Promise.all(
        payloads.map((p) => apiClient.post('/api/admin/payment-processor/configs', p))
      );

      toast.success('Payment processor configurations saved successfully');
    } catch (error) {
      toast.error('Failed to save payment processor configurations');
      console.error(error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <MobilePageShell
      title="Payment Processors"
      description="Configure checkout gateways, merchant keys, and cash-on-arrival terms"
      actions={
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchProcessors}
            className="h-10 min-h-[44px] flex-1 sm:flex-initial touch-manipulation gap-1.5"
          >
            <RefreshCw className={isLoading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
          <Button 
            onClick={handleSave} 
            disabled={isSaving}
            className="h-10 min-h-[44px] flex-1 sm:flex-initial touch-manipulation gap-2"
          >
            <Save className="h-4 w-4" />
            <span>{isSaving ? 'Saving...' : 'Save All'}</span>
          </Button>
        </div>
      }
    >
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 min-w-0">
        {/* Stripe Card */}
        <Card className="shadow-xs flex flex-col justify-between">
          <div>
            <CardHeader className="pb-3 border-b">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-md bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 flex items-center justify-center shrink-0">
                    <CreditCard className="h-4 w-4" />
                  </div>
                  <div>
                    <CardTitle className="text-base font-semibold">Stripe</CardTitle>
                    <CardDescription className="text-xs">Credit & debit cards</CardDescription>
                  </div>
                </div>
                <Switch 
                  checked={stripeState.enabled}
                  onCheckedChange={(checked) => setStripeState((prev) => ({ ...prev, enabled: checked }))}
                  className="touch-manipulation"
                />
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Publishable Key</Label>
                <Input 
                  type="text" 
                  placeholder="pk_live_... or pk_test_..."
                  value={stripeState.public_key}
                  onChange={(e) => setStripeState((prev) => ({ ...prev, public_key: e.target.value }))}
                  disabled={!stripeState.enabled}
                  className="h-11 min-h-[44px] font-mono text-xs"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Secret Key</Label>
                <Input 
                  type="password" 
                  placeholder="sk_live_... or sk_test_..."
                  value={stripeState.secret_key}
                  onChange={(e) => setStripeState((prev) => ({ ...prev, secret_key: e.target.value }))}
                  disabled={!stripeState.enabled}
                  className="h-11 min-h-[44px] font-mono text-xs"
                />
              </div>
            </CardContent>
          </div>
        </Card>

        {/* PayPal Card */}
        <Card className="shadow-xs flex flex-col justify-between">
          <div>
            <CardHeader className="pb-3 border-b">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-md bg-blue-50 dark:bg-blue-950/40 text-blue-600 flex items-center justify-center shrink-0">
                    <Banknote className="h-4 w-4" />
                  </div>
                  <div>
                    <CardTitle className="text-base font-semibold">PayPal</CardTitle>
                    <CardDescription className="text-xs">PayPal digital wallet</CardDescription>
                  </div>
                </div>
                <Switch 
                  checked={paypalState.enabled}
                  onCheckedChange={(checked) => setPaypalState((prev) => ({ ...prev, enabled: checked }))}
                  className="touch-manipulation"
                />
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Client ID</Label>
                <Input 
                  type="text" 
                  placeholder="PayPal Client ID"
                  value={paypalState.client_id}
                  onChange={(e) => setPaypalState((prev) => ({ ...prev, client_id: e.target.value }))}
                  disabled={!paypalState.enabled}
                  className="h-11 min-h-[44px] font-mono text-xs"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Client Secret</Label>
                <Input 
                  type="password" 
                  placeholder="PayPal Client Secret"
                  value={paypalState.client_secret}
                  onChange={(e) => setPaypalState((prev) => ({ ...prev, client_secret: e.target.value }))}
                  disabled={!paypalState.enabled}
                  className="h-11 min-h-[44px] font-mono text-xs"
                />
              </div>
            </CardContent>
          </div>
        </Card>

        {/* Offline Payment Card */}
        <Card className="shadow-xs flex flex-col justify-between">
          <div>
            <CardHeader className="pb-3 border-b">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-md bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 flex items-center justify-center shrink-0">
                    <HelpCircle className="h-4 w-4" />
                  </div>
                  <div>
                    <CardTitle className="text-base font-semibold">Cash / Offline</CardTitle>
                    <CardDescription className="text-xs">Pay in person or wire</CardDescription>
                  </div>
                </div>
                <Switch 
                  checked={offlineState.enabled}
                  onCheckedChange={(checked) => setOfflineState((prev) => ({ ...prev, enabled: checked }))}
                  className="touch-manipulation"
                />
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Payment Instructions</Label>
                <Textarea 
                  placeholder="Provide instructions displayed during checkout (e.g. Please pay cash upon arrival)."
                  value={offlineState.instructions}
                  onChange={(e) => setOfflineState((prev) => ({ ...prev, instructions: e.target.value }))}
                  disabled={!offlineState.enabled}
                  className="min-h-[108px] text-xs resize-y"
                />
              </div>
            </CardContent>
          </div>
        </Card>
      </div>
    </MobilePageShell>
  );
}
