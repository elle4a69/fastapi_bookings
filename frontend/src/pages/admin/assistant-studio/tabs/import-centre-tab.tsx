import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  DownloadCloud,
  ShieldCheck,
  Hash,
  Database,
  Layers,
  FileCheck2,
  RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api';
import type { ImportReportData, ProviderItem } from '../types';

interface ImportCentreTabProps {
  selectedProvider: ProviderItem | null;
}

export const ImportCentreTab: React.FC<ImportCentreTabProps> = ({ selectedProvider }) => {
  const EXPECTED_SHA256 = 'F0C80D93EAB23D7772B7454C81F38027D23D1C6D6E88D4F1EF1314E5B54303A6';

  const [isDryRun, setIsDryRun] = useState(false);
  const [importScope, setImportScope] = useState<'platform_seed' | 'tenant_default' | 'provider_override'>('platform_seed');
  const [isImporting, setIsImporting] = useState(false);
  const [importReport, setImportReport] = useState<ImportReportData>({
    status: 'idle',
    scanned: 0,
    imported: 0,
    skippedDuplicates: 0,
    rejected: 0,
    sha256_verified: false,
    scopeUsed: 'Platform Seeds',
    dryRunUsed: false,
  });

  const handleTriggerImport = async () => {
    setIsImporting(true);
    try {
      const data = await apiClient.post<ImportReportData>('/api/admin/assistant-studio/import', {
        provider_id: selectedProvider?.id ?? null,
        scope: importScope,
        dry_run: isDryRun,
      });

      if (data) {
        setImportReport(data);
        if (data.dryRunUsed) {
          toast.info(`Dry-run completed: ${data.scanned} scanned, SHA-256 verified.`);
        } else {
          toast.success(`Successfully imported ${data.imported} approved intent examples!`);
        }
      }
    } catch (err: any) {
      console.error('Import failed:', err);
      toast.error(err?.message || 'Failed to execute dataset import');
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b">
        <div>
          <h2 className="text-xl font-bold tracking-tight flex items-center gap-2">
            <DownloadCloud className="h-5 w-5 text-primary" />
            Approved Dataset Import Centre
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Cryptographically verified importer for Assistant UI's approved conversational style examples.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono text-xs">
            Dataset: approved_intent_examples.jsonl
          </Badge>
        </div>
      </div>

      {/* Cryptographic SHA-256 Fingerprint Card */}
      <Card className="border-emerald-500/40 bg-emerald-500/[0.03]">
        <CardContent className="p-4 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <ShieldCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
              <div>
                <h4 className="text-sm font-semibold">Cryptographic Integrity Gate (SHA-256)</h4>
                <p className="text-xs text-muted-foreground">
                  The dataset must exactly match the SHA-256 fingerprint before any row can be ingested.
                </p>
              </div>
            </div>
            <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-xs py-1">
              Verified Immutable
            </Badge>
          </div>

          <div className="p-2.5 rounded bg-muted/60 font-mono text-[11px] text-muted-foreground flex items-center gap-2 overflow-x-auto">
            <Hash className="h-4 w-4 shrink-0 text-foreground" />
            <span className="select-all font-semibold text-foreground">{EXPECTED_SHA256}</span>
          </div>
        </CardContent>
      </Card>

      {/* Execution Configuration Card */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-2 border-border/70">
          <CardHeader>
            <CardTitle className="text-base font-semibold">Import Pipeline Configuration</CardTitle>
            <CardDescription className="text-xs">
              Select ingestion scope and verify safety parameters before populating MessageStyleExample.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-3">
              <Label className="text-xs font-semibold">Target Scope</Label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <button
                  type="button"
                  onClick={() => setImportScope('platform_seed')}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    importScope === 'platform_seed'
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'border-border/60 hover:bg-muted/40'
                  }`}
                >
                  <div className="font-semibold text-xs flex items-center gap-1.5">
                    <Database className="h-3.5 w-3.5 text-primary" />
                    Global Platform Seeds
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-1">
                    tenant_id=null (Shared across all clinics as default priors).
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setImportScope('tenant_default')}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    importScope === 'tenant_default'
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'border-border/60 hover:bg-muted/40'
                  }`}
                >
                  <div className="font-semibold text-xs flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-blue-500" />
                    Tenant Default
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-1">
                    Scoped to current tenant. Overrides platform defaults.
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setImportScope('provider_override')}
                  disabled={!selectedProvider?.id}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    importScope === 'provider_override'
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'border-border/60 hover:bg-muted/40'
                  } ${!selectedProvider?.id ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <div className="font-semibold text-xs flex items-center gap-1.5">
                    <DownloadCloud className="h-3.5 w-3.5 text-purple-500" />
                    Provider Override
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-1">
                    {selectedProvider?.id ? `Scoped to ${selectedProvider.name}` : 'Select a provider in the top bar.'}
                  </p>
                </button>
              </div>
            </div>

            {/* Dry Run Toggle */}
            <div className="flex items-center justify-between p-3.5 rounded-lg border bg-muted/20">
              <div className="space-y-0.5">
                <Label htmlFor="dry-run-switch" className="text-xs font-semibold cursor-pointer">
                  Dry-Run Mode (Validation Only)
                </Label>
                <p className="text-[11px] text-muted-foreground">
                  Validates file SHA-256 and scans all lines without committing rows to the database.
                </p>
              </div>
              <Switch id="dry-run-switch" checked={isDryRun} onCheckedChange={setIsDryRun} />
            </div>

            {/* Action Button */}
            <div className="pt-2">
              <Button onClick={handleTriggerImport} disabled={isImporting} className="w-full gap-2">
                {isImporting ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Streaming & Verifying JSONL Records...
                  </>
                ) : (
                  <>
                    <FileCheck2 className="h-4 w-4" />
                    {isDryRun ? 'Run Verification Dry-Run' : 'Execute Real Ingestion'}
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Real Ingestion Report Card */}
        <Card className="border-border/70">
          <CardHeader>
            <CardTitle className="text-base font-semibold">Live Ingestion Telemetry</CardTitle>
            <CardDescription className="text-xs">Outcome summary from the real asset importer service.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-xs">
            <div className="flex items-center justify-between p-2.5 rounded bg-muted/40">
              <span className="text-muted-foreground">Pipeline Status:</span>
              <Badge variant={importReport.status === 'success' ? 'default' : 'secondary'}>
                {importReport.status.toUpperCase()}
              </Badge>
            </div>

            <div className="space-y-2 font-mono text-[11px]">
              <div className="flex items-center justify-between py-1 border-b">
                <span className="text-muted-foreground">SHA-256 Verified:</span>
                <span className={importReport.sha256_verified ? 'text-emerald-600 font-bold' : 'text-muted-foreground'}>
                  {importReport.sha256_verified ? 'PASSED (100%)' : 'Awaiting Run'}
                </span>
              </div>
              <div className="flex items-center justify-between py-1 border-b">
                <span className="text-muted-foreground">Total Scanned:</span>
                <span className="font-bold">{importReport.scanned}</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b">
                <span className="text-muted-foreground">Committed Rows:</span>
                <span className="text-emerald-600 font-bold">{importReport.imported}</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b">
                <span className="text-muted-foreground">Duplicates Skipped:</span>
                <span>{importReport.skippedDuplicates}</span>
              </div>
              <div className="flex items-center justify-between py-1">
                <span className="text-muted-foreground">Rejected by Safety:</span>
                <span className="text-destructive font-bold">{importReport.rejected}</span>
              </div>
            </div>

            {importReport.timestamp && (
              <div className="text-[10px] text-muted-foreground text-right">
                Executed: {importReport.timestamp}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
