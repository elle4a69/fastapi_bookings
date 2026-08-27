import { useState, useEffect } from "react";
import { MessageSquareCode, ArrowRight, Play, CheckCircle2, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface SmsAccount {
  id: number;
  public_id: string;
  display_name: string;
  sender_address: string;
  transport_type: string;
}

export default function SmsSimulatorTab() {
  const [accounts, setAccounts] = useState<SmsAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [sender, setSender] = useState("0412345678");
  const [message, setMessage] = useState("Hello! I want to book a service tomorrow.");
  const [loading, setLoading] = useState(false);
  const [simResult, setSimResult] = useState<any | null>(null);

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    try {
      const res = await apiClient.get<SmsAccount[]>("/api/admin/sms/accounts");
      setAccounts(res);
      if (res.length > 0) {
        setSelectedAccountId(String(res[0].id));
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load accounts.");
    }
  };

  const handleSimulate = async () => {
    const acc = accounts.find(a => String(a.id) === selectedAccountId);
    if (!acc) {
      toast.error("Please select an active SMS account.");
      return;
    }
    if (!sender || !message) {
      toast.error("Please provide both sender number and message text.");
      return;
    }

    setLoading(true);
    setSimResult(null);
    try {
      // Simulate by calling the public webhook endpoint directly
      const payload = {
        message_id: `sim-${Date.now()}`,
        sender: sender,
        to: acc.sender_address,
        message: message,
        received_at: new Date().toISOString()
      };
      
      const res = await apiClient.post<any>(
        `/api/sms/webhooks/${acc.transport_type}/${acc.public_id}`, 
        payload
      );
      
      setSimResult(res);
      toast.success("Inbound SMS simulated successfully!");
    } catch (err: any) {
      toast.error(err.message || "Simulation failed.");
      setSimResult({
        status: "error",
        error: err.message || "Failed to deliver simulated webhook."
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquareCode className="w-5 h-5 text-primary" /> SMS Simulator Panel
          </CardTitle>
          <CardDescription>Simulate incoming SMS messages from client phone numbers to your configured lines.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label>Select Target Line / Account</Label>
            <Select value={selectedAccountId} onValueChange={setSelectedAccountId}>
              <SelectTrigger>
                <SelectValue placeholder="Select Account" />
              </SelectTrigger>
              <SelectContent>
                {accounts.map(acc => (
                  <SelectItem key={acc.id} value={String(acc.id)}>
                    {acc.display_name} ({acc.sender_address} - {acc.transport_type})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label>Customer Mobile Number (E.g. E.164 or Local AU)</Label>
            <Input placeholder="0412 345 678" value={sender} onChange={e => setSender(e.target.value)} />
          </div>

          <div className="space-y-1">
            <Label>Message Body</Label>
            <Input placeholder="Hi there, are you open tomorrow?" value={message} onChange={e => setMessage(e.target.value)} />
          </div>

          <div className="pt-2">
            <Button size="sm" onClick={handleSimulate} disabled={loading || accounts.length === 0} className="w-full">
              <Play className="w-4 h-4 mr-2" /> {loading ? "Simulating..." : "Simulate Inbound SMS"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="flex flex-col">
        <CardHeader>
          <CardTitle className="text-base">Simulation Outcome</CardTitle>
          <CardDescription>View intake pipeline results, autoresponder actions, and enqueued AI jobs.</CardDescription>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col justify-center items-center p-6 border-t">
          {!simResult ? (
            <div className="text-center text-muted-foreground">
              <MessageSquareCode className="w-12 h-12 text-muted-foreground/20 mx-auto mb-2" />
              <p>Ready. Set up a message and click "Simulate" to see processing details.</p>
            </div>
          ) : simResult.error ? (
            <div className="text-center space-y-2">
              <ShieldAlert className="w-10 h-10 text-red-500 mx-auto" />
              <h4 className="font-semibold text-red-500">Pipeline Error</h4>
              <p className="text-muted-foreground">{simResult.error}</p>
            </div>
          ) : (
            <div className="w-full space-y-3">
              <div className="flex justify-between items-center pb-2 border-b">
                <span className="font-semibold">Pipeline Status</span>
                <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Success
                </Badge>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono leading-relaxed">
                <span className="text-muted-foreground">Duplicate Event:</span>
                <span className="text-right font-bold">{simResult.duplicate ? "YES (Deduplicated)" : "NO"}</span>

                <span className="text-muted-foreground">Conversation ID:</span>
                <span className="text-right font-bold">{simResult.conversation_id || "None"}</span>

                <span className="text-muted-foreground">Autoresponder Sent:</span>
                <span className="text-right font-bold">{simResult.autoresponder_sent ? "YES" : "NO"}</span>

                <span className="text-muted-foreground">AI Job Enqueued:</span>
                <span className="text-right font-bold">{simResult.ai_job_enqueued ? "YES" : "NO"}</span>
              </div>

              {simResult.conversation_id && (
                <div className="pt-4 text-center">
                  <Button variant="outline" size="sm" onClick={() => window.location.reload()} className="w-full">
                    Go to Inbox <ArrowRight className="w-3.5 h-3.5 ml-2" />
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
