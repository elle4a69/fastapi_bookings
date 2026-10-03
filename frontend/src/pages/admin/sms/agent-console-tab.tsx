import { ShieldAlert, Terminal } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function SmsAgentConsoleTab() {
  return (
    <div className="space-y-4 text-xs">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 sm:p-4 rounded-xl border bg-card shadow-xs">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-zinc-900 text-amber-400 border border-zinc-800 shrink-0">
            <Terminal className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-bold text-foreground">Coding Worker Status</h2>
              <Badge variant="secondary" className="gap-1.5 text-[10px]">Unavailable</Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              This application does not currently have a connected coding worker.
            </p>
          </div>
        </div>
      </div>

      <div
        data-testid="coding-worker-unavailable"
        className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-muted-foreground"
      >
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" aria-hidden="true" />
          <div className="space-y-2">
            <p className="font-medium text-foreground">No coding worker is available from this screen.</p>
            <p>
              The previous console did not represent a connected worker. It has been disabled rather than
              presenting generated activity, command results, or execution success.
            </p>
            <p>
              Use the operational SMS tools for their supported workflows. Engineering work must remain in
              review until a separately approved isolated worker and ticket handoff are available.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
export default SmsAgentConsoleTab;
