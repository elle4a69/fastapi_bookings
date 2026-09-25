import { useState, useEffect, useCallback } from "react";
import { 
  MessageSquareCode, 
  ArrowRight, 
  Play, 
  CheckCircle2, 
  ShieldAlert,
  Sparkles,
  BellRing,
  RefreshCw,
  Layers,
  Users,
  CalendarCheck,
  DollarSign,
  Clock,
  MapPin,
  HelpCircle,
  Inbox
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";

interface SmsAccount {
  id: number;
  public_id: string;
  display_name: string;
  sender_address: string;
  transport_type: string;
}

interface ScenarioSeedResult {
  success: boolean;
  scenarios_count: number;
  conversations_count: number;
  arrivals_count: number;
  drafts_count: number;
  message: string;
}

interface SmsSimulatorTabProps {
  onNavigate?: (tabId: string) => void;
}

const PREVIEW_CLIENT_SCENARIOS = [
  {
    client: "Client 1 - Alice Walker",
    phone: "0411000001",
    provider: "Provider 1 (Dr. Bennett)",
    color: "border-sky-500/30 bg-sky-500/5",
    items: [
      { type: "Booking", icon: CalendarCheck, text: "Hi Provider 1, I'd like to book Service 1 - Standard Consultation 60m with Dr. Sarah Bennett for tomorrow at 10:00 AM please." },
      { type: "Add-on", icon: Sparkles, text: "Could I also add Add-on 1 - Extended Care (15m) to my consultation session?" },
      { type: "Arrival", icon: BellRing, text: "I'm here! Just arrived at Location 1 - Main Center for my 10 AM consultation.", isArrival: true }
    ]
  },
  {
    client: "Client 2 - Bob Taylor",
    phone: "0411000002",
    provider: "Provider 1 (Dr. Bennett)",
    color: "border-emerald-500/30 bg-emerald-500/5",
    items: [
      { type: "Pricing", icon: DollarSign, text: "Hello, what is the price difference between Service 2 - Express Follow-up 30m and Service 3 - Premium Assessment 90m?" },
      { type: "Availability", icon: Clock, text: "Do you have any available slots this Thursday afternoon between 2:00 PM and 4:00 PM?" },
      { type: "Reschedule", icon: RefreshCw, text: "Can I reschedule my appointment on Friday to next Tuesday morning at 10:30 AM instead?" }
    ]
  },
  {
    client: "Client 3 - Charlie Evans",
    phone: "0411000003",
    provider: "Provider 2 (Marcus Vance)",
    color: "border-amber-500/30 bg-amber-500/5",
    items: [
      { type: "Cancel", icon: ShieldAlert, text: "Please cancel my booking for tomorrow at 2:00 PM, something unexpected came up." },
      { type: "Arrival", icon: BellRing, text: "I'm here in the parking lot at Location 1 - Main Center, walking into reception now.", isArrival: true },
      { type: "Product", icon: Layers, text: "Do you have Product 1 - Essential Kit and Product 2 - Recovery Balm available for purchase after my session?" }
    ]
  },
  {
    client: "Client 4 - Diana Prince",
    phone: "0411000004",
    provider: "Provider 2 (Marcus Vance)",
    color: "border-purple-500/30 bg-purple-500/5",
    items: [
      { type: "Advisory", icon: HelpCircle, text: "Hi there! I have lower back tension and fatigue. Should I book Service 1 - Standard Consultation or Service 4 - Holistic Wellness 45m?" },
      { type: "Access", icon: MapPin, text: "Can I request a ground floor room and wheelchair accessibility for Location 1?" },
      { type: "Policy", icon: Clock, text: "Are you open on Sundays or do you take evening appointments after 6:00 PM?" }
    ]
  },
  {
    client: "Client 5 - Evan Wright",
    phone: "0411000005",
    provider: "Provider 2 (Marcus Vance)",
    color: "border-indigo-500/30 bg-indigo-500/5",
    items: [
      { type: "Directions", icon: MapPin, text: "Where is Location 1 - Main Center located and is customer parking free?" },
      { type: "Urgent", icon: Clock, text: "I need urgent Service 5 - Rapid Triage 15m today if there is any cancellation!" },
      { type: "Arrival", icon: BellRing, text: "I'm here in the main lobby for my 3:45 PM appointment.", isArrival: true },
      { type: "Feedback", icon: CheckCircle2, text: "Thank you for seeing me so quickly today, the triage advice helped tremendously!" }
    ]
  }
];

export default function SmsSimulatorTab({ onNavigate }: SmsSimulatorTabProps) {
  const [accounts, setAccounts] = useState<SmsAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [sender, setSender] = useState("0411000001");
  const [message, setMessage] = useState("Hi Provider 1, I'd like to book Service 1 - Standard Consultation 60m with Dr. Sarah Bennett for tomorrow at 10:00 AM please.");
  const [loading, setLoading] = useState(false);
  const [simResult, setSimResult] = useState<any | null>(null);

  // Batch preloader state
  const [batchLoading, setBatchLoading] = useState(false);
  const [clearExisting, setClearExisting] = useState(true);
  const [batchResult, setBatchResult] = useState<ScenarioSeedResult | null>(null);

  const navigateTo = useCallback((tabId: string) => {
    if (onNavigate) {
      onNavigate(tabId);
    } else {
      window.dispatchEvent(new CustomEvent("sms-navigate-tab", { detail: tabId }));
    }
  }, [onNavigate]);

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

  const handleBatchPreload = async () => {
    setBatchLoading(true);
    setBatchResult(null);
    try {
      const payload = {
        account_id: selectedAccountId ? Number(selectedAccountId) : undefined,
        clear_existing: clearExisting
      };
      const res = await apiClient.post<ScenarioSeedResult>(
        "/api/admin/sms/conversations/seed-scenarios",
        payload
      );
      setBatchResult(res);
      toast.success("Batch Scenarios Preloaded!", {
        description: `Successfully created ${res.scenarios_count} scenarios across ${res.conversations_count} clients with ${res.arrivals_count} arrivals.`
      });
    } catch (err: any) {
      toast.error(err.message || "Failed to preload batch test scenarios.");
    } finally {
      setBatchLoading(false);
    }
  };

  return (
    <div className="space-y-4 text-xs">
      {/* 1-Click Batch Preload Header Card */}
      <Card className="border-primary/20 bg-linear-to-r from-primary/5 via-card to-background shadow-xs">
        <CardHeader className="pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-primary text-primary-foreground shadow-xs">
                  <Sparkles className="w-4 h-4" />
                </div>
                <CardTitle className="text-base font-bold">1-Click Batch Scenario Preloader</CardTitle>
                <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20 text-[10px] font-mono">
                  16 Scenarios • Client 1..5
                </Badge>
              </div>
              <CardDescription className="text-xs">
                Inject 16 numbered scenarios (Bookings, Pricing, Arrivals with chime, Rescheduling, Cancellations, Ambiguous & After-hours) mapped to Client 1 through Client 5.
              </CardDescription>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center space-x-2 bg-background/80 px-2.5 py-1.5 rounded-md border text-[11px]">
                <Checkbox 
                  id="clear-existing" 
                  checked={clearExisting} 
                  onCheckedChange={(checked) => setClearExisting(Boolean(checked))} 
                />
                <label htmlFor="clear-existing" className="cursor-pointer select-none text-muted-foreground">
                  Reset previous test conversations
                </label>
              </div>

              <Button 
                onClick={handleBatchPreload} 
                disabled={batchLoading} 
                className="gap-2 shadow-xs font-semibold"
              >
                {batchLoading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Injecting 16 Scenarios...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current" />
                    Generate 16 Test Scenarios
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardHeader>

        {/* Post-execution Feedback Banner */}
        {batchResult && (
          <div className="px-6 pb-4">
            <div className="p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span className="font-semibold text-emerald-900 dark:text-emerald-300">
                    {batchResult.message}
                  </span>
                </div>
                <Badge className="bg-emerald-600 text-white font-mono text-[10px]">
                  ✓ System Ready
                </Badge>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                <div className="bg-background/90 p-2 rounded border border-emerald-500/20 text-center">
                  <div className="text-[10px] text-muted-foreground uppercase font-semibold">Scenarios</div>
                  <div className="text-base font-bold text-foreground">{batchResult.scenarios_count}</div>
                </div>
                <div className="bg-background/90 p-2 rounded border border-emerald-500/20 text-center">
                  <div className="text-[10px] text-muted-foreground uppercase font-semibold">Conversations</div>
                  <div className="text-base font-bold text-foreground">{batchResult.conversations_count} (Clients 1..5)</div>
                </div>
                <div className="bg-background/90 p-2 rounded border border-emerald-500/20 text-center">
                  <div className="text-[10px] text-muted-foreground uppercase font-semibold">Lobby Arrivals</div>
                  <div className="text-base font-bold text-amber-600 flex items-center justify-center gap-1">
                    <BellRing className="w-3.5 h-3.5 animate-bounce" />
                    {batchResult.arrivals_count} Active
                  </div>
                </div>
                <div className="bg-background/90 p-2 rounded border border-emerald-500/20 text-center">
                  <div className="text-[10px] text-muted-foreground uppercase font-semibold">Triage Drafts</div>
                  <div className="text-base font-bold text-indigo-600">{batchResult.drafts_count} Ready</div>
                </div>
              </div>

              {/* Quick Navigation Links */}
              <div className="flex flex-wrap gap-2 pt-1 border-t border-emerald-500/20">
                <Button 
                  size="sm" 
                  variant="default" 
                  className="h-8 gap-1.5 text-xs"
                  onClick={() => navigateTo("inbox")}
                >
                  <Inbox className="w-3.5 h-3.5" /> Open Inbox
                </Button>
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="h-8 gap-1.5 text-xs border-amber-500/40 text-amber-600 hover:bg-amber-500/10"
                  onClick={() => navigateTo("arrivals")}
                >
                  <BellRing className="w-3.5 h-3.5" /> View Arrivals Tab (Lobby Chime)
                </Button>
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="h-8 gap-1.5 text-xs border-indigo-500/40 text-indigo-600 hover:bg-indigo-500/10"
                  onClick={() => navigateTo("triage")}
                >
                  <Sparkles className="w-3.5 h-3.5" /> Open Draft Triage ({batchResult.drafts_count})
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Client Scenario Matrix Preview */}
        <CardContent className="pt-0">
          <div className="text-[11px] font-semibold text-muted-foreground mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5" /> Structured Client Scenarios (Click any chip to populate the single simulator):
            </span>
            <span className="font-mono text-[10px]">Traceable Numbered Entities</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
            {PREVIEW_CLIENT_SCENARIOS.map((cs) => (
              <div key={cs.phone} className={`p-2.5 rounded-lg border ${cs.color} space-y-2 flex flex-col justify-between`}>
                <div>
                  <div className="font-bold text-foreground text-xs truncate">{cs.client}</div>
                  <div className="font-mono text-[10px] text-muted-foreground">{cs.phone} • {cs.provider}</div>
                </div>

                <div className="space-y-1.5 pt-1">
                  {cs.items.map((item, idx) => {
                    const Icon = item.icon;
                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => {
                          setSender(cs.phone);
                          setMessage(item.text);
                          toast.info(`Loaded scenario: ${item.type} (${cs.client})`);
                        }}
                        className="w-full text-left p-1.5 rounded bg-background/80 hover:bg-background border border-border/60 hover:border-primary transition-all text-[10px] flex items-start gap-1.5 group"
                      >
                        <Icon className={`w-3 h-3 shrink-0 mt-0.5 ${item.isArrival ? "text-amber-500" : "text-primary"}`} />
                        <div className="min-w-0 flex-1">
                          <span className="font-semibold block truncate group-hover:text-primary">{item.type}</span>
                          <span className="text-muted-foreground line-clamp-2 leading-tight">{item.text}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Manual Single Inbound Simulator Panel */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <MessageSquareCode className="w-5 h-5 text-primary" /> Individual Message Simulator
            </CardTitle>
            <CardDescription>Simulate a single live incoming SMS webhook from any mobile number.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3.5">
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
              <Label>Customer Mobile Number</Label>
              <Input placeholder="0411 000 001" value={sender} onChange={e => setSender(e.target.value)} />
            </div>

            <div className="space-y-1">
              <Label>Message Body</Label>
              <Input placeholder="Hi there, are you open tomorrow?" value={message} onChange={e => setMessage(e.target.value)} />
            </div>

            <div className="space-y-1.5">
              <Label className="text-[10px] text-muted-foreground font-semibold uppercase">Quick-Action Preset Chips</Label>
              <div className="flex flex-wrap gap-1.5">
                {[
                  { label: "Pricing Inquiry", text: "Hello, how much is Service 1 - Standard Consultation 60m?" },
                  { label: "Book Slot", text: "Can I book Service 2 - Express Follow-up 30m for tomorrow at 10:00 AM?" },
                  { label: "I'm Here / Arrival", text: "I'm here! Just arrived at Location 1 - Main Center for my consultation." },
                  { label: "Reschedule", text: "I need to reschedule my Friday booking to next Tuesday at 10:30 AM." },
                  { label: "Cancellation", text: "Please cancel my booking for tomorrow, something urgent came up." }
                ].map(chip => (
                  <Button
                    key={chip.label}
                    type="button"
                    size="xs"
                    variant="outline"
                    className="h-6 text-[10px] px-2"
                    onClick={() => setMessage(chip.text)}
                  >
                    {chip.label}
                  </Button>
                ))}
              </div>
            </div>

            <div className="pt-2">
              <Button size="sm" onClick={handleSimulate} disabled={loading || accounts.length === 0} className="w-full">
                <Play className="w-4 h-4 mr-2" /> {loading ? "Simulating..." : "Simulate Inbound SMS Webhook"}
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
              <div className="text-center text-muted-foreground space-y-1">
                <MessageSquareCode className="w-12 h-12 text-muted-foreground/20 mx-auto mb-2" />
                <p className="font-medium text-foreground">Simulator Ready</p>
                <p className="text-[11px]">Click "Generate 16 Test Scenarios" above or "Simulate Inbound SMS" to process messages.</p>
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

                <div className="pt-4 grid grid-cols-2 gap-2">
                  <Button variant="default" size="sm" onClick={() => navigateTo("inbox")} className="w-full">
                    Go to Inbox <ArrowRight className="w-3.5 h-3.5 ml-2" />
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => navigateTo("arrivals")} className="w-full text-amber-600 border-amber-500/30">
                    View Arrivals <BellRing className="w-3.5 h-3.5 ml-2" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
