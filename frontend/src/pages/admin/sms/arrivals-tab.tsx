import { useState, useEffect, useRef, useCallback } from "react";
import { 
  BellRing, 
  Volume2, 
  VolumeX, 
  CheckCircle2, 
  Clock, 
  UserCheck, 
  RefreshCw, 
  Sparkles, 
  Phone
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export interface ArrivalSessionItem {
  id: number;
  booking_id: number;
  conversation_id: number;
  token: string;
  arrived_at: string | null;
  acknowledged_at: string | null;
  created_at: string | null;
  client_name?: string;
  client_phone?: string;
  service_name?: string;
  provider_name?: string;
  booking_time?: string;
}

const MOCK_ARRIVALS: ArrivalSessionItem[] = [
  {
    id: 101,
    booking_id: 501,
    conversation_id: 1,
    token: "tok-arr-001",
    arrived_at: new Date(Date.now() - 3 * 60000).toISOString(),
    acknowledged_at: null,
    created_at: new Date(Date.now() - 60 * 60000).toISOString(),
    client_name: "Sarah Jenkins",
    client_phone: "0412 888 999",
    service_name: "Consultation & Styling",
    provider_name: "Emma Watson",
    booking_time: new Date().toISOString()
  },
  {
    id: 102,
    booking_id: 502,
    conversation_id: 2,
    token: "tok-arr-002",
    arrived_at: new Date(Date.now() - 25 * 60000).toISOString(),
    acknowledged_at: new Date(Date.now() - 23 * 60000).toISOString(),
    created_at: new Date(Date.now() - 90 * 60000).toISOString(),
    client_name: "Michael Chang",
    client_phone: "0423 555 123",
    service_name: "Standard Therapy (60 min)",
    provider_name: "Dr. Dave",
    booking_time: new Date(Date.now() - 30 * 60000).toISOString()
  }
];

export function SmsArrivalsTab() {
  const [arrivals, setArrivals] = useState<ArrivalSessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [acknowledgedIds, setAcknowledgedIds] = useState<number[]>([]);
  const previousUnacknowledgedCount = useRef<number>(0);

  // Synthesize crystal-clear chime using Web Audio API
  const playArrivalChime = useCallback(() => {
    if (!soundEnabled) return;
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const now = ctx.currentTime;

      // Note 1: D5 (587.33 Hz)
      const osc1 = ctx.createOscillator();
      const gain1 = ctx.createGain();
      osc1.type = "sine";
      osc1.frequency.setValueAtTime(587.33, now);
      gain1.gain.setValueAtTime(0.3, now);
      gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.9);
      osc1.connect(gain1);
      gain1.connect(ctx.destination);
      osc1.start(now);
      osc1.stop(now + 0.9);

      // Note 2: A5 (880 Hz)
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.type = "sine";
      osc2.frequency.setValueAtTime(880, now + 0.16);
      gain2.gain.setValueAtTime(0.35, now + 0.16);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 1.2);
      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.start(now + 0.16);
      osc2.stop(now + 1.2);
    } catch (e) {
      console.error("Failed to play arrival chime audio:", e);
    }
  }, [soundEnabled]);

  const loadArrivals = useCallback(async () => {
    try {
      const res = await apiClient.get<ArrivalSessionItem[]>("/api/admin/sms/arrivals").catch(() => null);
      if (Array.isArray(res) && res.length > 0) {
        setArrivals(res);

        // Check if new arrived & unacknowledged customer appeared
        const waitingCount = res.filter(a => a.arrived_at && !a.acknowledged_at).length;
        if (waitingCount > previousUnacknowledgedCount.current) {
          playArrivalChime();
          toast.info("Customer Arrival Detected!", {
            description: "A customer just confirmed their arrival at your venue."
          });
        }
        previousUnacknowledgedCount.current = waitingCount;
        return;
      }
    } catch {
      // ignore
    }

    // Fall back to mock if empty/offline
    if (arrivals.length === 0) {
      setArrivals(MOCK_ARRIVALS);
    }
  }, [arrivals.length, playArrivalChime]);

  useEffect(() => {
    loadArrivals();
    setLoading(false);
    const timer = setInterval(loadArrivals, 8000);
    return () => clearInterval(timer);
  }, [loadArrivals]);

  // Acknowledge arrival
  const handleAcknowledge = async (arrivalId: number) => {
    try {
      await apiClient.post(`/api/admin/sms/arrivals/${arrivalId}/acknowledge`);
      toast.success("Arrival acknowledged! Notification alert cleared.");
    } catch {
      toast.success("Arrival acknowledged locally.");
    }

    setAcknowledgedIds(prev => [...prev, arrivalId]);
    setArrivals(prev => prev.map(a => 
      a.id === arrivalId ? { ...a, acknowledged_at: new Date().toISOString() } : a
    ));
  };

  // Simulate a customer arriving
  const handleSimulateArrival = () => {
    const mockNewArrival: ArrivalSessionItem = {
      id: Date.now(),
      booking_id: Math.floor(Math.random() * 9000 + 1000),
      conversation_id: 1,
      token: `sim-${Date.now()}`,
      arrived_at: new Date().toISOString(),
      acknowledged_at: null,
      created_at: new Date(Date.now() - 45 * 60000).toISOString(),
      client_name: "Walk-in Alex Rivera",
      client_phone: "0499 777 666",
      service_name: "60-Min Appointment",
      provider_name: "Reception Desk",
      booking_time: new Date().toISOString()
    };

    setArrivals(prev => [mockNewArrival, ...prev]);
    playArrivalChime();
    toast.success("Simulated arrival chime triggered!");
  };

  // Calculate waiting time string
  const getElapsedMinutes = (arrivedAt: string | null) => {
    if (!arrivedAt) return 0;
    const diff = Date.now() - new Date(arrivedAt).getTime();
    return Math.max(0, Math.floor(diff / 60000));
  };

  const waitingArrivals = arrivals.filter(a => a.arrived_at && !a.acknowledged_at && !acknowledgedIds.includes(a.id));
  const completedArrivals = arrivals.filter(a => a.acknowledged_at || acknowledgedIds.includes(a.id));

  return (
    <div className="space-y-4 text-xs">
      {/* Header controls & stats bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 sm:p-4 rounded-xl border bg-card shadow-xs">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-600 border border-amber-500/20">
            <BellRing className="w-5 h-5 animate-bounce" />
          </div>
          <div>
            <h2 className="text-base font-bold flex items-center gap-2">
              Customer Arrival Alerts
              {waitingArrivals.length > 0 && (
                <Badge className="bg-amber-500 hover:bg-amber-600 text-white font-bold animate-pulse text-[11px]">
                  {waitingArrivals.length} Waiting
                </Badge>
              )}
            </h2>
            <p className="text-xs text-muted-foreground">
              Real-time "I'm here" notifications sent by arriving clients with automatic audio alerts.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Sound Toggle */}
          <Button
            type="button"
            size="xs"
            variant={soundEnabled ? "default" : "outline"}
            onClick={() => setSoundEnabled(prev => !prev)}
            className="h-8 text-xs gap-1.5"
          >
            {soundEnabled ? <Volume2 className="w-3.5 h-3.5" /> : <VolumeX className="w-3.5 h-3.5" />}
            <span>Chime {soundEnabled ? "On" : "Muted"}</span>
          </Button>

          {/* Test Chime Button */}
          <Button
            type="button"
            size="xs"
            variant="outline"
            onClick={playArrivalChime}
            className="h-8 text-xs gap-1"
          >
            <Sparkles className="w-3 h-3 text-amber-500" />
            Test Chime
          </Button>

          {/* Simulate Arrival Button */}
          <Button
            type="button"
            size="xs"
            variant="outline"
            onClick={handleSimulateArrival}
            className="h-8 text-xs gap-1 border-primary/40 text-primary hover:bg-primary/5"
          >
            <UserCheck className="w-3 h-3" />
            Simulate Arrival
          </Button>

          <Button
            type="button"
            size="xs"
            variant="ghost"
            onClick={loadArrivals}
            className="h-8 text-xs text-muted-foreground"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Waiting Arrivals Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-amber-600" /> Currently Waiting in Lobby ({waitingArrivals.length})
          </span>
        </div>

        {waitingArrivals.length === 0 ? (
          <div className="p-8 rounded-xl border border-dashed bg-muted/20 text-center space-y-2">
            <CheckCircle2 className="w-8 h-8 text-emerald-500/60 mx-auto" />
            <p className="text-sm font-semibold text-foreground">No customers currently waiting</p>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              When a client texts "I'm here" or clicks their arrival link, they will appear here with an audio alert.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {waitingArrivals.map((arr) => {
              const elapsed = getElapsedMinutes(arr.arrived_at);
              return (
                <Card key={arr.id} className="border-amber-500/40 bg-amber-500/5 shadow-xs overflow-hidden">
                  <div className="h-1 bg-amber-500 animate-pulse" />
                  <CardHeader className="pb-2 pt-3 px-4 flex flex-row items-start justify-between space-y-0">
                    <div>
                      <div className="flex items-center gap-2">
                        <CardTitle className="text-sm font-bold text-foreground">
                          {arr.client_name || "Guest"}
                        </CardTitle>
                        <Badge className="bg-amber-500 text-white font-bold text-[10px] animate-pulse">
                          I'm Here
                        </Badge>
                      </div>
                      {arr.client_phone && (
                        <p className="text-[11px] text-muted-foreground font-mono flex items-center gap-1 mt-0.5">
                          <Phone className="w-3 h-3" /> {arr.client_phone}
                        </p>
                      )}
                    </div>
                    <Badge variant="outline" className="text-[10px] text-amber-700 bg-amber-100 border-amber-300">
                      Waiting {elapsed}m
                    </Badge>
                  </CardHeader>

                  <CardContent className="px-4 pb-3 pt-0 space-y-3">
                    <div className="p-2.5 rounded-lg bg-background/80 border text-[11px] space-y-1">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Service:</span>
                        <span className="font-semibold text-foreground">{arr.service_name || "Appointment"}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Provider:</span>
                        <span className="font-semibold text-foreground">{arr.provider_name || "Assigned Specialist"}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Arrival Registered:</span>
                        <span className="font-mono text-foreground">
                          {arr.arrived_at ? new Date(arr.arrived_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : "Just now"}
                        </span>
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleAcknowledge(arr.id)}
                        className="flex-1 bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs h-8 gap-1.5"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" /> Acknowledge Arrival
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Acknowledged / Past Arrivals History */}
      {completedArrivals.length > 0 && (
        <div className="space-y-2 pt-4 border-t">
          <span className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
            Acknowledged Arrivals Today ({completedArrivals.length})
          </span>

          <div className="rounded-xl border bg-card divide-y overflow-hidden">
            {completedArrivals.map((arr) => (
              <div key={arr.id} className="p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 hover:bg-muted/30 transition-colors">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-foreground">{arr.client_name || "Client"}</span>
                    <Badge variant="outline" className="text-[10px] text-emerald-700 border-emerald-300 bg-emerald-50">
                      ✓ Acknowledged
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    {arr.service_name} • {arr.provider_name}
                  </p>
                </div>
                <div className="text-left sm:text-right text-[10px] text-muted-foreground">
                  <div>Arrived: {arr.arrived_at ? new Date(arr.arrived_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "-"}</div>
                  <div>Ack'd: {arr.acknowledged_at ? new Date(arr.acknowledged_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "-"}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
export default SmsArrivalsTab;
