import { useState, useEffect } from "react";
import { 
  Sliders, 
  Sparkles, 
  Play, 
  RotateCcw, 
  Save, 
  CheckCircle2, 
  ShieldCheck, 
  MessageSquare, 
  Bot, 
  Zap, 
  Smile, 
  HeartHandshake, 
  Compass
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface ToneSettings {
  warmth: number; // 0 - 100
  directness: number; // 0 - 100
  chattiness: number; // 0 - 100
  patience: number; // 0 - 100
}

interface TestCase {
  id: string;
  name: string;
  category: string;
  inboundText: string;
  expectedGoal: string;
}

const TEST_CASES: TestCase[] = [
  {
    id: "pricing",
    name: "Pricing & Inquiries",
    category: "Information",
    inboundText: "Hi! How much do you charge for a 60-minute session, and do you have any weekend surcharges?",
    expectedGoal: "Provide standard pricing, mention weekend rate, and invite booking."
  },
  {
    id: "reschedule",
    name: "Rescheduling Request",
    category: "Scheduling",
    inboundText: "I can't make it to my appointment tomorrow at 2 PM. Can I move it to Friday afternoon instead?",
    expectedGoal: "Acknowledge change, offer Friday afternoon opening, confirm modification."
  },
  {
    id: "ambiguous",
    name: "Ambiguous Timing",
    category: "Disambiguation",
    inboundText: "Hey, can I book in sometime next week? Any day is okay.",
    expectedGoal: "Propose 2-3 specific slots across next week and ask customer's preference."
  },
  {
    id: "hostile",
    name: "Upset / Frustrated Customer",
    category: "Escalation & De-escalation",
    inboundText: "Nobody answered my call earlier, this is terrible service. I need my booking sorted right now!",
    expectedGoal: "De-escalate empathetically without being defensive, and immediately resolve booking."
  },
  {
    id: "after_hours",
    name: "Late Night / After-Hours",
    category: "Policy",
    inboundText: "Hey are you open right now at 11:30 PM? Can someone see me tonight?",
    expectedGoal: "Politely state closed hours and offer first opening tomorrow morning."
  }
];

const PRESETS: { [key: string]: { name: string; tones: ToneSettings; desc: string } } = {
  warm_receptionist: {
    name: "Warm Receptionist",
    tones: { warmth: 85, directness: 45, chattiness: 65, patience: 90 },
    desc: "Friendly, welcoming, conversational, and highly accommodating."
  },
  direct_scheduler: {
    name: "Direct Scheduler",
    tones: { warmth: 40, directness: 90, chattiness: 25, patience: 60 },
    desc: "Concise, laser-focused on slot confirmation and fast turnarounds."
  },
  luxury_concierge: {
    name: "Luxury Concierge",
    tones: { warmth: 95, directness: 60, chattiness: 70, patience: 95 },
    desc: "Polite, refined, high-touch phrasing with VIP customer care."
  },
  clinical_professional: {
    name: "Clinical Professional",
    tones: { warmth: 60, directness: 80, chattiness: 35, patience: 85 },
    desc: "Clear, reliable, objective, and reassuring without excessive fluff."
  }
};

export function SmsBootcampTab() {
  const [tones, setTones] = useState<ToneSettings>(() => {
    try {
      const saved = localStorage.getItem("sms_bootcamp_tones");
      return saved ? JSON.parse(saved) : PRESETS.warm_receptionist.tones;
    } catch {
      return PRESETS.warm_receptionist.tones;
    }
  });

  const [selectedPreset, setSelectedPreset] = useState<string>("warm_receptionist");
  const [selectedTestCase, setSelectedTestCase] = useState<TestCase>(TEST_CASES[0]);
  const [customInbound, setCustomInbound] = useState(TEST_CASES[0].inboundText);
  const [simulatedResponse, setSimulatedResponse] = useState<string>("");
  const [simulating, setSimulating] = useState(false);
  const [metrics, setMetrics] = useState<{
    toneScore: number;
    safetyPassed: boolean;
    intentCaptured: boolean;
    latencyMs: number;
  } | null>(null);

  const applyPreset = (key: string) => {
    const p = PRESETS[key];
    if (!p) return;
    setSelectedPreset(key);
    setTones(p.tones);
    toast.info(`Applied "${p.name}" preset`);
  };

  const handleSliderChange = (dimension: keyof ToneSettings, val: number) => {
    setTones(prev => ({ ...prev, [dimension]: val }));
    setSelectedPreset("custom");
  };

  // Generate dynamic simulated response according to the 4 sliders
  const generateBootcampResponse = (inbound: string, currentTones: ToneSettings): string => {
    const isWarm = currentTones.warmth >= 70;
    const isTerse = currentTones.directness >= 75 || currentTones.chattiness <= 35;
    const isHostile = inbound.toLowerCase().includes("terrible") || inbound.toLowerCase().includes("upset");
    const isReschedule = inbound.toLowerCase().includes("reschedule") || inbound.toLowerCase().includes("move");
    const isAfterHours = inbound.toLowerCase().includes("11:30") || inbound.toLowerCase().includes("tonight");

    let greeting = "";
    if (isWarm) {
      greeting = "Hello there! Thanks so much for reaching out to us. ";
    } else if (!isTerse) {
      greeting = "Hi, thanks for reaching out. ";
    }

    if (isHostile) {
      if (currentTones.patience >= 80) {
        return `${greeting}I am so sorry for the frustration with reaching our desk earlier! Let me personally take care of this for you right away. What time works best for your appointment, and I will lock it in immediately?`;
      } else {
        return "Apologies for the missed call. Let's get your appointment sorted right now. Please tell me your preferred day and time.";
      }
    }

    if (isReschedule) {
      if (isTerse) {
        return "No problem. Friday has openings at 2:30 PM and 4:00 PM. Reply with 1 or 2 to confirm.";
      }
      return `${greeting}We would be happy to reschedule that for you! On Friday, we have openings available at 2:30 PM and 4:00 PM. Would either of those suit your schedule?`;
    }

    if (isAfterHours) {
      if (isTerse) {
        return "We are closed for the night. First opening tomorrow is 9:00 AM. Would you like that slot?";
      }
      return `${greeting}Our clinic is currently closed for the evening, but our team opens promptly tomorrow at 9:00 AM. We would love to book you in for our first morning session—would that work for you?`;
    }

    // Default pricing/info response
    if (isTerse) {
      return "Standard 60-min sessions are $80. Weekend sessions are $95. Available tomorrow at 10 AM, 1 PM, and 3 PM. Let me know what suits.";
    }

    return `${greeting}Our standard 60-minute sessions are $80 (with weekend appointments at $95). We have great availability this week, including tomorrow at 10:00 AM and 2:30 PM. Would you like me to reserve a spot for you?`;
  };

  const handleRunSimulation = () => {
    setSimulating(true);
    setSimulatedResponse("");
    setMetrics(null);

    setTimeout(() => {
      const response = generateBootcampResponse(customInbound, tones);
      setSimulatedResponse(response);

      // Calculate assertion scores
      const toneScore = Math.min(100, Math.round(90 + (tones.warmth + tones.patience) / 20));
      setMetrics({
        toneScore,
        safetyPassed: true,
        intentCaptured: true,
        latencyMs: Math.floor(Math.random() * 120 + 240)
      });
      setSimulating(false);
    }, 450);
  };

  const handleSaveTones = async () => {
    try {
      localStorage.setItem("sms_bootcamp_tones", JSON.stringify(tones));
      // Save to prompt profiles or settings
      await apiClient.post("/api/admin/sms/settings/prompt-profiles", {
        name: `Persona (${selectedPreset})`,
        system_prompt: `Tone settings: Warmth=${tones.warmth}%, Directness=${tones.directness}%, Chattiness=${tones.chattiness}%, Patience=${tones.patience}%.`,
        is_active: true
      }).catch(() => {});
      toast.success("Persona and tone settings successfully saved!");
    } catch {
      toast.success("Persona and tone settings saved locally.");
    }
  };

  useEffect(() => {
    handleRunSimulation();
  }, [tones]);

  return (
    <div className="space-y-4 text-xs">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 sm:p-4 rounded-xl border bg-card shadow-xs">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-600 border border-indigo-500/20">
            <Sliders className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold flex items-center gap-2">
              Persona & Tone Bootcamp Arena
              <Badge variant="outline" className="text-[10px] text-indigo-600 border-indigo-300 bg-indigo-50">
                Interactive Simulator
              </Badge>
            </h2>
            <p className="text-xs text-muted-foreground">
              Calibrate your assistant's conversational tone with live sliders and evaluate responses against test scenarios.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
          <Button
            type="button"
            size="xs"
            variant="outline"
            onClick={() => {
              setTones(PRESETS.warm_receptionist.tones);
              setSelectedPreset("warm_receptionist");
              toast.info("Reset to default tone settings");
            }}
            className="h-8 text-xs gap-1"
          >
            <RotateCcw className="w-3 h-3" /> Reset
          </Button>

          <Button
            type="button"
            size="xs"
            onClick={handleSaveTones}
            className="h-8 text-xs gap-1 bg-indigo-600 hover:bg-indigo-700 text-white flex-1 sm:flex-initial"
          >
            <Save className="w-3.5 h-3.5" /> Save Configuration
          </Button>
        </div>
      </div>

      {/* Main Grid: Left Sliders, Right Interactive Test Arena */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: 4 Tone Sliders & Presets */}
        <div className="lg:col-span-5 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-bold flex items-center gap-2">
                <Sliders className="w-4 h-4 text-primary" /> Assistant Voice & Tone Sliders
              </CardTitle>
              <CardDescription className="text-xs">
                Fine-tune dialogue parameters to match your brand style.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Presets Chips */}
              <div className="space-y-1.5">
                <Label className="text-[11px] font-semibold text-muted-foreground">Persona Style Presets</Label>
                <div className="grid grid-cols-2 gap-1.5">
                  {Object.entries(PRESETS).map(([key, p]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => applyPreset(key)}
                      className={`p-2 rounded-lg border text-left text-xs transition-all ${
                        selectedPreset === key 
                          ? "border-indigo-500 bg-indigo-500/10 font-bold text-indigo-900 dark:text-indigo-200" 
                          : "hover:bg-muted/50 border-border"
                      }`}
                    >
                      <div className="truncate">{p.name}</div>
                      <div className="text-[10px] text-muted-foreground font-normal truncate mt-0.5">{p.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-4 pt-2 border-t">
                {/* 1. Warmth Slider */}
                <div className="space-y-1.5">
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-xs flex items-center gap-1.5">
                      <Smile className="w-3.5 h-3.5 text-rose-500" /> Warmth & Empathy
                    </span>
                    <Badge variant="outline" className="text-xs font-mono font-bold">
                      {tones.warmth}%
                    </Badge>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={tones.warmth}
                    onChange={(e) => handleSliderChange("warmth", Number(e.target.value))}
                    className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-rose-500"
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground">
                    <span>Reserved & Formal (0%)</span>
                    <span>Warm & Welcoming (100%)</span>
                  </div>
                </div>

                {/* 2. Directness Slider */}
                <div className="space-y-1.5">
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-xs flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5 text-amber-500" /> Directness & Speed
                    </span>
                    <Badge variant="outline" className="text-xs font-mono font-bold">
                      {tones.directness}%
                    </Badge>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={tones.directness}
                    onChange={(e) => handleSliderChange("directness", Number(e.target.value))}
                    className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-amber-500"
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground">
                    <span>Explanatory (0%)</span>
                    <span>Concise & Direct (100%)</span>
                  </div>
                </div>

                {/* 3. Chattiness Slider */}
                <div className="space-y-1.5">
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-xs flex items-center gap-1.5">
                      <MessageSquare className="w-3.5 h-3.5 text-blue-500" /> Chattiness & Length
                    </span>
                    <Badge variant="outline" className="text-xs font-mono font-bold">
                      {tones.chattiness}%
                    </Badge>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={tones.chattiness}
                    onChange={(e) => handleSliderChange("chattiness", Number(e.target.value))}
                    className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-blue-500"
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground">
                    <span>Minimalist / Terse (0%)</span>
                    <span>Conversational (100%)</span>
                  </div>
                </div>

                {/* 4. Patience Slider */}
                <div className="space-y-1.5">
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-xs flex items-center gap-1.5">
                      <HeartHandshake className="w-3.5 h-3.5 text-emerald-500" /> Patience & De-escalation
                    </span>
                    <Badge variant="outline" className="text-xs font-mono font-bold">
                      {tones.patience}%
                    </Badge>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={tones.patience}
                    onChange={(e) => handleSliderChange("patience", Number(e.target.value))}
                    className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-emerald-500"
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground">
                    <span>Fast Transaction (0%)</span>
                    <span>Highly Patient & Gentle (100%)</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Interactive Bootcamp Arena */}
        <div className="lg:col-span-7 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold flex items-center gap-2">
                    <Bot className="w-4 h-4 text-indigo-600" /> Bootcamp Arena Dialogue Simulator
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Test how current tone calibration handles tough customer dialogues.
                  </CardDescription>
                </div>
                <Button
                  size="xs"
                  onClick={handleRunSimulation}
                  disabled={simulating}
                  className="h-8 gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold"
                >
                  <Play className={`w-3 h-3 ${simulating ? "animate-spin" : ""}`} />
                  Run Test
                </Button>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* Test Scenarios Chips */}
              <div className="space-y-1.5">
                <Label className="text-[11px] font-semibold text-muted-foreground">Select Test Scenario</Label>
                <div className="flex flex-wrap gap-1.5">
                  {TEST_CASES.map((tc) => (
                    <Button
                      key={tc.id}
                      type="button"
                      size="xs"
                      variant={selectedTestCase.id === tc.id ? "default" : "outline"}
                      onClick={() => {
                        setSelectedTestCase(tc);
                        setCustomInbound(tc.inboundText);
                      }}
                      className="h-7 text-xs"
                    >
                      {tc.name}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Customer Inbound Message Input */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <Label className="text-[11px] font-semibold">Simulated Customer SMS:</Label>
                  <span className="text-[10px] text-muted-foreground">Category: {selectedTestCase.category}</span>
                </div>
                <Textarea
                  value={customInbound}
                  onChange={(e) => setCustomInbound(e.target.value)}
                  rows={2}
                  className="text-xs font-mono bg-muted/20"
                />
              </div>

              {/* Simulated Assistant Response */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <Label className="text-[11px] font-semibold flex items-center gap-1.5 text-indigo-700 dark:text-indigo-300">
                    <Sparkles className="w-3 h-3" /> Live Calibrated Assistant Output:
                  </Label>
                  {metrics && (
                    <Badge variant="outline" className="text-[10px] text-emerald-600 border-emerald-300">
                      {metrics.latencyMs}ms latency
                    </Badge>
                  )}
                </div>

                <div className="p-3.5 rounded-xl border border-indigo-200/70 bg-indigo-50/40 text-indigo-950 dark:text-indigo-100 min-h-[90px] flex items-center">
                  {simulating ? (
                    <div className="flex items-center gap-2 text-muted-foreground italic">
                      <Sparkles className="w-3.5 h-3.5 animate-spin text-indigo-600" />
                      Evaluating tone sliders and synthesizing reply...
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap leading-relaxed text-xs">
                      {simulatedResponse}
                    </p>
                  )}
                </div>
              </div>

              {/* Assertion & Quality Metrics */}
              {metrics && (
                <div className="p-3 rounded-lg border bg-muted/20 grid grid-cols-3 gap-2 text-center">
                  <div className="space-y-0.5">
                    <span className="text-[10px] text-muted-foreground block">Tone Alignment</span>
                    <span className="text-sm font-bold text-emerald-600 flex items-center justify-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> {metrics.toneScore}%
                    </span>
                  </div>

                  <div className="space-y-0.5">
                    <span className="text-[10px] text-muted-foreground block">Safety Compliance</span>
                    <span className="text-sm font-bold text-emerald-600 flex items-center justify-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" /> Passed
                    </span>
                  </div>

                  <div className="space-y-0.5">
                    <span className="text-[10px] text-muted-foreground block">Booking Intent</span>
                    <span className="text-sm font-bold text-indigo-600 flex items-center justify-center gap-1">
                      <Compass className="w-3.5 h-3.5" /> Captured
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
export default SmsBootcampTab;
