import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  Bot,
  Play,
  Pause,
  Square,
  RotateCcw,
  Sliders,
  Settings,
  AlertTriangle,
  Users,
  Save,
  Undo2
} from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import BootcampSettingsTab, {
  type BootcampStyleProfile,
  DEFAULT_STYLE_PROFILE,
} from "./bootcamp-settings-tab";
import { AssistantThreadPanel, type ThreadMessage } from "./assistant-thread-panel";

export interface PersonaDefinition {
  id: string;
  name: string;
  category: string;
  badgeClass: string;
  description: string;
  dialogueScript: { customer: string; toriBase: string }[];
  handoffTurn?: number;
  handoffReason?: string;
  handoffResolvedReply?: string;
}

export const PERSONAS: PersonaDefinition[] = [
  {
    id: "cranky-carl",
    name: "Cranky Carl",
    category: "DIFFICULT",
    badgeClass: "bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-800",
    description: "Impatient, critical, expects instant answers and zero friction.",
    handoffTurn: 2,
    handoffReason: "Specific policy exception authorization for same-day no-show refund request.",
    handoffResolvedReply: "Understood Carl. Staff has approved a one-time refund credit voucher for your account. Would you like me to book your make-up session for Thursday morning?",
    dialogueScript: [
      {
        customer: "I've been waiting 20 minutes for someone to reply. Is anyone even working there?",
        toriBase: "Hello Carl! Thanks for reaching out. We are right here and ready to help you schedule right away."
      },
      {
        customer: "I missed my appointment this morning and I demand a full cash refund right now.",
        toriBase: "Our standard policy is that same-day missed appointments require management approval."
      },
      {
        customer: "Fine, book me in for Thursday at 10 AM. And don't make me wait again.",
        toriBase: "You're all booked for Thursday at 10:00 AM! Confirmation text has been dispatched."
      },
      {
        customer: "Is parking going to cost me extra when I get there?",
        toriBase: "Not at all Carl, our rear customer lot is completely complimentary."
      },
      {
        customer: "Alright, good. See you Thursday.",
        toriBase: "We look forward to seeing you Thursday morning! Have a great day."
      }
    ]
  },
  {
    id: "sarcastic-sam",
    name: "Sarcastic Sam",
    category: "SARCASM",
    badgeClass: "bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-950 dark:text-purple-300 dark:border-purple-800",
    description: "Dry humor, ironic quips, constantly testing conversational resilience.",
    dialogueScript: [
      {
        customer: "Oh wonderful, an AI receptionist. Let me guess: you have availability every single day until I pick one?",
        toriBase: "Caught me! But seriously, our calendar is actually quite live and accurate. What day were you hoping for?"
      },
      {
        customer: "Let's see if your magic robot brain can handle Friday afternoon around 3 PM.",
        toriBase: "Miracles do happen—Friday at 3:00 PM is wide open with Sarah. Would you like me to hold that slot?"
      },
      {
        customer: "Only if you promise I won't be greeted by another robot when I walk in.",
        toriBase: "Guaranteed 100% human reception team at the door! Shall I confirm your details for Friday at 3?"
      },
      {
        customer: "Go ahead, lock it in. Let's see how this goes.",
        toriBase: "Done! Friday at 3:00 PM is officially yours. Looking forward to proving our human team is just as sharp."
      },
      {
        customer: "Thanks robot. You weren't half bad.",
        toriBase: "High praise! See you Friday afternoon!"
      }
    ]
  },
  {
    id: "deadpan-dave",
    name: "Deadpan Dave",
    category: "DIRECT",
    badgeClass: "bg-slate-200 text-slate-800 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
    description: "Monotone, ultra-terse, zero pleasantries, straight to the facts.",
    dialogueScript: [
      {
        customer: "Price. Tuesday 3pm.",
        toriBase: "Standard consult is $85. Tuesday 3:00 PM is available. Would you like to reserve it?"
      },
      {
        customer: "Yes. Hold it.",
        toriBase: "Reserved. What is your full name?"
      },
      {
        customer: "Dave Miller.",
        toriBase: "Confirmed: Dave Miller, Tuesday 3:00 PM. Reminder sent."
      },
      {
        customer: "Cancellation policy?",
        toriBase: "24 hours advance notice required for full refund."
      },
      {
        customer: "Understood. Thanks.",
        toriBase: "You're welcome. See you Tuesday."
      }
    ]
  },
  {
    id: "passive-paul",
    name: "Passive Paul",
    category: "INDECISIVE",
    badgeClass: "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800",
    description: "Hesitant, leaves decisions up in the air, needs gentle guidance.",
    dialogueScript: [
      {
        customer: "Maybe I want to book an appointment next week... or next month? I'm really not sure.",
        toriBase: "No problem at all Paul! We can take it one step at a time. What service were you considering?"
      },
      {
        customer: "Probably the 60-minute session, but Wednesday might be busy, or maybe Thursday morning?",
        toriBase: "Thursday at 10:30 AM is very quiet and relaxed here. Would you like to pencil that in?"
      },
      {
        customer: "I guess Thursday could work. Can I change it if my schedule shifts?",
        toriBase: "Absolutely, you can reschedule anytime with 24 hours notice. Shall I hold Thursday at 10:30 AM?"
      },
      {
        customer: "Okay, let's do Thursday at 10:30. That sounds safe.",
        toriBase: "Wonderful! You're booked for Thursday at 10:30 AM. We will send a reminder the day before."
      },
      {
        customer: "Thanks for being patient with me.",
        toriBase: "Always happy to help Paul. You're in good hands!"
      }
    ]
  },
  {
    id: "happy-harry",
    name: "Happy Harry",
    category: "FRIENDLY",
    badgeClass: "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800",
    description: "Super enthusiastic, upbeat, uses lots of exclamation marks and emojis.",
    dialogueScript: [
      {
        customer: "Hello wonderful people! 🎉 So excited to book my visit with you guys soon!!",
        toriBase: "Hello Harry! It's fantastic to hear from you! We'd love to get you on the schedule. What day works best?"
      },
      {
        customer: "How about Monday at 11 AM?! That would be an amazing start to my week! 🌟",
        toriBase: "Monday at 11:00 AM is wide open and sounds like the perfect start to the week! Shall I lock that in?"
      },
      {
        customer: "Yes please!! Woohoo!! What should I bring with me?! 🥳",
        toriBase: "Just yourself and comfortable clothing! We have refreshments and everything else ready for you."
      },
      {
        customer: "You guys are the best!! See you Monday! 🚀",
        toriBase: "Thank you Harry! We can't wait to see you Monday at 11:00 AM!"
      },
      {
        customer: "Have a gorgeous day!! ✨",
        toriBase: "You too Harry, stay awesome!"
      }
    ]
  },
  {
    id: "nervous-neil",
    name: "Nervous Neil",
    category: "ANXIOUS",
    badgeClass: "bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800",
    description: "Worried about policies, hidden charges, and unexpected fees.",
    dialogueScript: [
      {
        customer: "Are there any hidden fees or extra surcharges if I book online?",
        toriBase: "Hi Neil! No hidden fees whatsoever. The price you see ($85) is the total and inclusive amount."
      },
      {
        customer: "What if my train is delayed 5 minutes? Will my booking be cancelled on the spot?",
        toriBase: "Not at all, we hold your appointment with a 15-minute grace window and communicate closely."
      },
      {
        customer: "Okay, what about the therapist? Are they gentle and experienced?",
        toriBase: "All our therapists are fully licensed with over 5 years clinical experience and specialize in gentle care."
      },
      {
        customer: "That is reassuring. Could I book Wednesday at 2 PM then?",
        toriBase: "Wednesday at 2:00 PM is reserved for you Neil. We'll take wonderful care of you."
      },
      {
        customer: "Thank you for answering all my questions so clearly.",
        toriBase: "It's truly our pleasure Neil. Rest easy and we'll see you Wednesday!"
      }
    ]
  },
  {
    id: "time-waster-terry",
    name: "Time-Waster Terry",
    category: "DISENGAGED",
    badgeClass: "bg-zinc-200 text-zinc-800 border-zinc-300 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-700",
    description: "Asks endless speculative questions without committing to any booking.",
    dialogueScript: [
      {
        customer: "Hypothetically speaking, if someone wanted to visit in October 2027, what would the schedule be?",
        toriBase: "Hello Terry! We open our calendar 90 days in advance, so 2027 bookings will open in mid-2027."
      },
      {
        customer: "Interesting. What color are the walls in the third treatment room?",
        toriBase: "They are a soothing sage green! Was there a specific appointment you'd like to plan for this season?"
      },
      {
        customer: "Maybe if the weather is good next month. Do you give discounts if it rains?",
        toriBase: "Our rates remain consistent rain or shine, but we offer complimentary herbal tea when it pours!"
      },
      {
        customer: "I will think about it and maybe check back later this year.",
        toriBase: "Sounds good Terry! Reach back out whenever you're ready to pick a date."
      },
      {
        customer: "Thanks for the info.",
        toriBase: "Anytime! Have a wonderful day."
      }
    ]
  },
  {
    id: "chatty-charlie",
    name: "Chatty Charlie",
    category: "CHATTY",
    badgeClass: "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800",
    description: "Writes long paragraphs rambling about irrelevant personal backstory.",
    dialogueScript: [
      {
        customer: "Hi! My aunt Susan actually recommended you because my dog had hip dysplasia last summer and we were driving past your avenue on the way to the vet and I noticed your sign...",
        toriBase: "Hello Charlie! Give Susan and your pup our warmest wishes! We'd love to welcome you in. Were you looking for an appointment this week?"
      },
      {
        customer: "Yes! Because next week my cousin is graduating from nursing school in Ohio so we have to fly out on Thursday and pack all the luggage...",
        toriBase: "Congratulations to your cousin! To beat the travel rush, how does Tuesday at 1:00 PM sound before your flight?"
      },
      {
        customer: "Tuesday at 1:00 PM is perfect because I can drop the dry cleaning right across the street beforehand!",
        toriBase: "That works out wonderfully! Tuesday at 1:00 PM is reserved for you. Safe travels to Ohio afterwards!"
      },
      {
        customer: "Thank you so much! You are so sweet. I'll tell aunt Susan all about this.",
        toriBase: "Please do! We look forward to meeting you on Tuesday at 1:00 PM."
      },
      {
        customer: "Bye for now!",
        toriBase: "See you Tuesday Charlie!"
      }
    ]
  },
  {
    id: "budget-bob",
    name: "Budget Bob",
    category: "PRICE-SENSITIVE",
    badgeClass: "bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-950 dark:text-yellow-300 dark:border-yellow-800",
    description: "Aggressively hunts for discounts, promo codes, and special concessions.",
    dialogueScript: [
      {
        customer: "What discount codes do you have active right now? I saw a coupon online but it didn't apply.",
        toriBase: "Hi Bob! We offer a $10 first-visit welcome credit when booking online with code WELCOME10."
      },
      {
        customer: "Can you stack that with senior discount or student discount for 40% off?",
        toriBase: "Our system permits one discount code per appointment, but WELCOME10 gives you our best current rate!"
      },
      {
        customer: "What's the cheapest slot you have open this Thursday?",
        toriBase: "Our weekday morning slots (10:00 AM) are $75 with your coupon applied. Would you like to reserve that?"
      },
      {
        customer: "Alright, $75 works. Lock in Thursday at 10 AM with the coupon.",
        toriBase: "Done! Thursday at 10:00 AM reserved with WELCOME10 applied. Total balance due at visit: $75."
      },
      {
        customer: "Receipt confirmed, thanks.",
        toriBase: "You're welcome Bob, see you Thursday morning!"
      }
    ]
  },
  {
    id: "curious-colin",
    name: "Curious Colin",
    category: "TECHNICAL",
    badgeClass: "bg-cyan-100 text-cyan-800 border-cyan-300 dark:bg-cyan-950 dark:text-cyan-300 dark:border-cyan-800",
    description: "Asks deep questions about specific materials, sterilization, and equipment.",
    handoffTurn: 3,
    handoffReason: "Practitioner credential verification & medical-grade autoclave sterilization spec sheet.",
    handoffResolvedReply: "Thanks for waiting Colin. Our clinical director confirmed our Class-B Tuttnauer vacuum autoclave runs at 134°C with certified spore tests weekly, and Dr. Evans is dual-board certified. Can I book you for Friday?",
    dialogueScript: [
      {
        customer: "What exact sterilization protocol do you follow between client appointments?",
        toriBase: "Hi Colin! We use hospital-grade disinfectants on all contact surfaces with a mandatory 15-minute turnover buffer."
      },
      {
        customer: "Do you use medical-grade autoclave spore tests, and what is your practitioner's board certification number?",
        toriBase: "Let me check with our lead practitioner to provide the precise autoclave specs and certification ID."
      },
      {
        customer: "I need those specific manufacturer details verified before I commit to an appointment.",
        toriBase: "Understood Colin, I have flagged this for our clinic director to provide exact technical specifications."
      },
      {
        customer: "That answers my sterilization concerns. Book me for Friday at 4 PM.",
        toriBase: "You're confirmed for Friday at 4:00 PM. Spec sheets will also be available at the front desk!"
      },
      {
        customer: "Appreciated. Thank you.",
        toriBase: "You're very welcome Colin. See you Friday."
      }
    ]
  },
  {
    id: "discreet-dominic",
    name: "Discreet Dominic",
    category: "PRIVACY",
    badgeClass: "bg-indigo-100 text-indigo-800 border-indigo-300 dark:bg-indigo-950 dark:text-indigo-300 dark:border-indigo-800",
    description: "Guarded, refuses to share personal details or email upfront.",
    dialogueScript: [
      {
        customer: "Can I book a session under an alias without providing my personal email address?",
        toriBase: "Hello Dominic. We strictly require only a first name and phone number for SMS reminders. Email is completely optional."
      },
      {
        customer: "And you don't sell or share customer phone numbers with third-party advertisers?",
        toriBase: "Never. Your contact details are stored securely on HIPAA/SOC2 compliant servers solely for appointment reminders."
      },
      {
        customer: "Good. Put me down as 'D' for Friday at 5:30 PM.",
        toriBase: "You've got it, 'D'. Friday at 5:30 PM is booked under your private file. See you then!"
      },
      {
        customer: "Will SMS notifications show service descriptions?",
        toriBase: "No, our reminder SMS only states your appointment time and arrival address for total privacy."
      },
      {
        customer: "Perfect. Thank you.",
        toriBase: "You're very welcome Dominic. Have a restful week."
      }
    ]
  },
  {
    id: "pushy-pete",
    name: "Pushy Pete",
    category: "DEMANDING",
    badgeClass: "bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-800",
    description: "Demands immediate appointments outside hours and insists on exceptions.",
    dialogueScript: [
      {
        customer: "I need an appointment tonight at 9:30 PM. Make it happen.",
        toriBase: "Hi Pete! Our clinic closes at 7:00 PM tonight, but I can get you in first thing tomorrow at 8:00 AM."
      },
      {
        customer: "I don't care about closing hours. Call your manager and have someone stay late for me.",
        toriBase: "Our staff hours are strictly scheduled for safety, Pete. Our earliest available slot is tomorrow morning at 8:00 AM."
      },
      {
        customer: "Fine, then tomorrow at 8:00 AM sharp. But someone better be there at 7:55.",
        toriBase: "Our reception opens promptly at 7:45 AM. You are booked for tomorrow at 8:00 AM Pete!"
      },
      {
        customer: "I expect VIP treatment for the inconvenience.",
        toriBase: "We treat every client with top-tier care Pete. See you tomorrow at 8:00 AM."
      },
      {
        customer: "Understood.",
        toriBase: "Have a good night Pete."
      }
    ]
  }
];

export interface BootcampMessage {
  id: string;
  sender: "customer" | "tori" | "staff";
  authorName: string;
  text: string;
  timestamp: string;
  status?: "draft" | "queued" | "sent" | "delivered" | "received" | "discarded";
}

export interface BootcampConversation {
  id: string;
  personaId: string;
  personaName: string;
  currentTurn: number;
  maxTurns: number;
  status: "idle" | "running" | "paused" | "completed" | "needs_handoff";
  needsHandoff: boolean;
  handoffReason?: string;
  messages: BootcampMessage[];
  isPinned?: boolean;
  isBlocked?: boolean;
}

export interface BootcampScenarioItem {
  id: string;
  pack?: string;
  title: string;
  description: string;
  objective?: string;
  initialPrompt?: string;
  initial_prompt?: string;
  expectedOutcome?: string;
  expected_outcome?: string;
}

export interface BootcampScenarioPack {
  id: string;
  title: string;
  description: string;
  scenarios: BootcampScenarioItem[];
}

export const FALLBACK_SCENARIO_PACKS: BootcampScenarioPack[] = [
  {
    id: "basic_communication",
    title: "Basic Communication",
    description: "Standard baseline queries on pricing, services, availability, and location.",
    scenarios: [
      { id: "pricing_enquiry", title: "Price Enquiry", description: "Base pricing and session rates" },
      { id: "service_overview", title: "Service Overview", description: "Treatment and offering options" },
      { id: "availability_general", title: "General Availability", description: "Opening slots and days" },
      { id: "location_enquiry", title: "Location Enquiry", description: "Clinic address and parking options" },
    ]
  },
  {
    id: "booking",
    title: "Booking Workflows",
    description: "Direct appointment scheduling, slot negotiation, rescheduling, and cancellations.",
    scenarios: [
      { id: "available_slot_request", title: "Available Slot Request", description: "Specific appointment booking" },
      { id: "unavailable_slot_negotiation", title: "Unavailable Slot Negotiation", description: "Slot negotiation on busy day" },
      { id: "booking_reschedule", title: "Booking Reschedule", description: "Moving session to new date" },
      { id: "booking_cancellation", title: "Booking Cancellation", description: "Canceling appointment and terms" },
      { id: "late_arrival_notice", title: "Late Arrival Notice", description: "Transit delay arrival alert" },
    ]
  },
  {
    id: "knowledge_gaps",
    title: "Knowledge Gaps & Policy Uncertainty",
    description: "Scenarios probing unrecorded facts, personal preferences, and ambiguous requests.",
    scenarios: [
      { id: "unknown_personal_preference", title: "Unknown Personal Preference", description: "Probing unrecorded provider preference" },
      { id: "impatient_client", title: "Impatient Client", description: "Demands instant exception answers" },
      { id: "refund_policy_exception", title: "Refund Policy Exception", description: "Same-day refund authorization" },
    ]
  }
];

export type RunStatus = "idle" | "running" | "paused" | "stopped" | "completed" | "failed";

interface AssistantBootcampPageProps {
  onNavigate?: (tabId: string) => void;
}

export default function AssistantBootcampPage({ onNavigate }: AssistantBootcampPageProps) {
  // Run State
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<string[]>([
    "cranky-carl",
    "sarcastic-sam",
    "deadpan-dave",
    "happy-harry",
    "curious-colin"
  ]);
  const [activePersonaId, setActivePersonaId] = useState<string>("cranky-carl");
  const [turns, setTurns] = useState<number>(5);
  const [notice, setNotice] = useState<{ type: "info" | "error"; text: string } | null>(null);

  // Master Spec 37: Autonomy Level State (1 = Review Every Turn, 2 = Semi-Autonomous, 3 = Full Sim)
  const [autonomyLevel, setAutonomyLevel] = useState<1 | 2 | 3>(2);

  // Master Spec 33, 34: Scenario Packs State
  const [scenarioPacks, setScenarioPacks] = useState<BootcampScenarioPack[]>(FALLBACK_SCENARIO_PACKS);
  const [selectedScenarios, setSelectedScenarios] = useState<string[]>([]);

  // Conversations Map
  const [conversations, setConversations] = useState<Record<string, BootcampConversation>>({});

  // Style Laboratory Sliders (0 - 5)
  const [styleProfile, setStyleProfile] = useState<BootcampStyleProfile>(DEFAULT_STYLE_PROFILE);
  const [previousProfile, setPreviousProfile] = useState<BootcampStyleProfile | null>(null);
  const [canUndo, setCanUndo] = useState(false);

  // Settings sheet open state
  const [settingsSheetOpen, setSettingsSheetOpen] = useState(false);

  // Polling ref for pacing simulation turns
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Helper to get active conversation
  const activeConversation = conversations[activePersonaId] || null;

  // Fetch available scenario packs
  const loadScenarios = useCallback(async () => {
    try {
      const res = await apiClient.get<any>("/api/admin/sms/bootcamp/scenarios");
      const packs = Array.isArray(res) ? res : res?.packs || [];
      if (packs.length > 0) {
        setScenarioPacks(packs);
      }
    } catch {
      // Retain fallback packs on error
    }
  }, []);

  // Initialize or reset conversations
  const initializeConversations = useCallback((personaIds: string[], maxTurns: number) => {
    const newConvs: Record<string, BootcampConversation> = {};
    personaIds.forEach((pid) => {
      const persona = PERSONAS.find((p) => p.id === pid);
      if (!persona) return;
      const initialScript = persona.dialogueScript[0];
      newConvs[pid] = {
        id: `bootcamp-conv-${pid}`,
        personaId: pid,
        personaName: persona.name,
        currentTurn: 1,
        maxTurns,
        status: "idle",
        needsHandoff: false,
        handoffReason: persona.handoffReason,
        messages: [
          {
            id: `msg-${pid}-init`,
            sender: "customer",
            authorName: persona.name,
            text: initialScript.customer,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            status: "received"
          }
        ]
      };
    });
    setConversations(newConvs);
  }, []);

  // Initial setup on mount
  useEffect(() => {
    initializeConversations(selectedPersonaIds, turns);
    loadScenarios();
  }, [initializeConversations, loadScenarios, selectedPersonaIds, turns]);

  // Adjust reply wording based on style laboratory sliders
  const applyStyleToResponse = (baseReply: string, profile: BootcampStyleProfile): string => {
    let result = baseReply;
    if (profile.directness >= 4) {
      result = result.replace(/Hello [^!.]+! /i, "").replace(/Thanks for reaching out. /i, "");
    }
    if (profile.warmth >= 4 && !result.includes("❤️") && !result.includes("pleasure")) {
      result = `We really care about taking great care of you! ${result}`;
    }
    if (profile.wit >= 4 && profile.sarcasm >= 3) {
      result = `${result} (And yes, we actually keep our promises!)`;
    } else if (profile.cheerfulness >= 4 && !result.includes("!")) {
      result = `${result} 😊`;
    }
    return result;
  };

  // Run action: START
  const handleStart = async () => {
    setNotice(null);
    try {
      await apiClient.post("/api/admin/sms/bootcamp/runs", {
        persona_ids: selectedPersonaIds,
        turns,
        max_turns: turns,
        style_profile: styleProfile,
        autonomy_level: autonomyLevel,
        scenario_ids: selectedScenarios.length ? selectedScenarios : undefined,
      }).catch(async () => {
        // Fallback to legacy path if /runs route is unavailable
        await apiClient.post("/api/admin/sms/bootcamp/runs/start", {
          data: {
            personas: selectedPersonaIds,
            turns,
            styleProfile,
            autonomyLevel,
            scenarios: selectedScenarios,
          }
        }).catch(() => {});
      });
    } catch {
      // Ignored for standalone mode
    }

    // Reset turn progress if starting afresh
    setConversations((prev) => {
      const next = { ...prev };
      selectedPersonaIds.forEach((pid) => {
        const persona = PERSONAS.find((p) => p.id === pid);
        if (!persona) return;
        const initialText = persona.dialogueScript[0].customer;

        if (!next[pid] || next[pid].status === "completed") {
          next[pid] = {
            id: `bootcamp-conv-${pid}`,
            personaId: pid,
            personaName: persona.name,
            currentTurn: 1,
            maxTurns: turns,
            status: "running",
            needsHandoff: false,
            handoffReason: persona.handoffReason,
            messages: [
              {
                id: `msg-${pid}-init`,
                sender: "customer",
                authorName: persona.name,
                text: initialText,
                timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                status: "received"
              }
            ]
          };
        } else {
          next[pid] = { ...next[pid], status: "running" };
        }
      });
      return next;
    });

    setRunStatus("running");
    toast.success("Tori Boot Camp started! Generating simulated interactions...");
  };

  // Run action: PAUSE
  const handlePause = async () => {
    try {
      await apiClient.post("/api/admin/sms/bootcamp/runs/pause", {}).catch(() => {});
    } catch {
      // Standalone fallback
    }
    setRunStatus("paused");
    setConversations((prev) => {
      const next = { ...prev };
      Object.keys(next).forEach((k) => {
        if (next[k].status === "running") {
          next[k] = { ...next[k], status: "paused" };
        }
      });
      return next;
    });
    toast.info("Boot Camp paused.");
  };

  // Run action: RESUME
  const handleResume = async () => {
    try {
      await apiClient.post("/api/admin/sms/bootcamp/runs/resume", {}).catch(() => {});
    } catch {
      // Standalone fallback
    }
    setRunStatus("running");
    setConversations((prev) => {
      const next = { ...prev };
      Object.keys(next).forEach((k) => {
        if (next[k].status === "paused") {
          next[k] = { ...next[k], status: "running" };
        }
      });
      return next;
    });
    toast.success("Boot Camp resumed.");
  };

  // Run action: STOP
  const handleStop = async () => {
    try {
      await apiClient.post("/api/admin/sms/bootcamp/runs/stop", {}).catch(() => {});
    } catch {
      // Standalone fallback
    }
    setRunStatus("stopped");
    setConversations((prev) => {
      const next = { ...prev };
      Object.keys(next).forEach((k) => {
        if (next[k].status === "running" || next[k].status === "paused") {
          next[k] = { ...next[k], status: "idle" };
        }
      });
      return next;
    });
    toast.info("Boot Camp stopped.");
  };

  // Run action: RESET
  const handleReset = async () => {
    try {
      await apiClient.delete("/api/admin/sms/bootcamp/runs").catch(() => {});
    } catch {
      // Standalone fallback
    }
    initializeConversations(selectedPersonaIds, turns);
    setRunStatus("idle");
    setNotice(null);
    toast.info("Cleared all Boot Camp test run threads.");
  };

  // Live Simulation Pacing & Polling (Every 2.5 seconds when active)
  useEffect(() => {
    if (runStatus !== "running") {
      if (pollingRef.current) clearInterval(pollingRef.current);
      return;
    }

    pollingRef.current = setInterval(async () => {
      // Attempt backend poll first
      try {
        const latest = await apiClient.get<any>("/api/admin/sms/bootcamp/runs/latest").catch(() => null);
        if (latest && latest.conversations) {
          setConversations(latest.conversations);
          if (latest.status) setRunStatus(latest.status);
          return;
        }
      } catch {
        // Fallback to client paced stepping
      }

      // Progress local simulation by one message/turn
      setConversations((prev) => {
        const next = { ...prev };
        let allCompleted = true;
        let madeProgress = false;

        for (const pid of selectedPersonaIds) {
          const conv = next[pid];
          if (!conv) continue;

          // If blocked by handoff, skip this thread until resolved
          if (conv.needsHandoff || conv.status === "needs_handoff") {
            allCompleted = false;
            continue;
          }

          if (conv.currentTurn <= conv.maxTurns && conv.status === "running") {
            allCompleted = false;
            const persona = PERSONAS.find((p) => p.id === pid);
            if (!persona) continue;

            const scriptTurn = persona.dialogueScript[conv.currentTurn - 1];
            const lastMsg = conv.messages[conv.messages.length - 1];

            // If last message was from customer, Tori answers
            if (lastMsg && lastMsg.sender === "customer") {
              // Level 2 (Semi-Autonomous): Check if handoff should trigger this turn
              if (autonomyLevel === 2 && persona.handoffTurn === conv.currentTurn) {
                next[pid] = {
                  ...conv,
                  needsHandoff: true,
                  status: "needs_handoff",
                  handoffReason: persona.handoffReason
                };
                madeProgress = true;
                break;
              }

              // Tori produces reply
              const toriText = applyStyleToResponse(
                scriptTurn ? scriptTurn.toriBase : "Thank you for confirming. Your appointment has been secured!",
                styleProfile
              );

              // Level 1: Review Every Turn generates a draft and pauses for operator sign-off
              const isLevel1Draft = autonomyLevel === 1;

              next[pid] = {
                ...conv,
                status: isLevel1Draft ? "paused" : conv.status,
                messages: [
                  ...conv.messages,
                  {
                    id: `msg-${pid}-tori-${conv.currentTurn}`,
                    sender: "tori",
                    authorName: "Tori",
                    text: toriText,
                    timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                    status: isLevel1Draft ? "draft" : "sent"
                  }
                ]
              };
              madeProgress = true;
              break;
            } else if (lastMsg && lastMsg.sender === "tori") {
              // In Level 1, if draft is not yet approved, do not advance turn
              if (lastMsg.status === "draft") {
                continue;
              }

              // If last was Tori and sent, next turn begins: customer speaks if turns remain
              const nextTurn = conv.currentTurn + 1;
              if (nextTurn <= conv.maxTurns) {
                const nextScript = persona.dialogueScript[nextTurn - 1];
                if (nextScript) {
                  next[pid] = {
                    ...conv,
                    currentTurn: nextTurn,
                    messages: [
                      ...conv.messages,
                      {
                        id: `msg-${pid}-cust-${nextTurn}`,
                        sender: "customer",
                        authorName: persona.name,
                        text: nextScript.customer,
                        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                        status: "received"
                      }
                    ]
                  };
                  madeProgress = true;
                  break;
                }
              } else {
                next[pid] = { ...conv, status: "completed" };
              }
            }
          } else if (conv.status !== "completed") {
            next[pid] = { ...conv, status: "completed" };
          }
        }

        if (allCompleted && !madeProgress) {
          setRunStatus("completed");
          toast.success("All persona test runs have completed!");
        }

        return next;
      });
    }, 2500);

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [runStatus, selectedPersonaIds, turns, styleProfile, autonomyLevel]);

  // Handle owner lesson response to information request
  const handleResolveLesson = async (answer: string) => {
    if (!activeConversation) return;
    const pid = activeConversation.personaId;
    const persona = PERSONAS.find((p) => p.id === pid);

    try {
      await apiClient.post(
        `/api/admin/sms/bootcamp/conversations/${activeConversation.id}/information-request/respond`,
        { information: answer }
      ).catch(() => {});
    } catch {
      // Standalone fallback
    }

    // Clear handoff on the conversation, add lesson resolved reply from Tori, and advance
    const resolvedReply =
      persona?.handoffResolvedReply ||
      `Got it! Based on your update: "${answer}". I've recorded this lesson and will proceed with the booking!`;

    setConversations((prev) => {
      const next = { ...prev };
      const conv = next[pid];
      if (!conv) return prev;

      next[pid] = {
        ...conv,
        needsHandoff: false,
        status: "running",
        messages: [
          ...conv.messages,
          {
            id: `msg-${pid}-tori-resolved-${Date.now()}`,
            sender: "tori",
            authorName: "Tori",
            text: resolvedReply,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            status: "sent",
          }
        ]
      };
      return next;
    });

    toast.success("Lesson saved! Tori retried the message with the new knowledge.");
  };

  const handleDismissHandoff = async () => {
    if (!activeConversation) return;
    const pid = activeConversation.personaId;
    setConversations((prev) => {
      const next = { ...prev };
      const conv = next[pid];
      if (!conv) return prev;
      next[pid] = {
        ...conv,
        needsHandoff: false,
        status: conv.status === "needs_handoff" ? "running" : conv.status,
      };
      return next;
    });
    toast.info("Information request dismissed.");
  };

  // Staff message injection
  const handleSendMessage = async (text: string) => {
    if (!activeConversation) return;
    const convId = activeConversation.id;
    const pid = activeConversation.personaId;

    try {
      await apiClient.post(`/api/admin/sms/bootcamp/conversations/${convId}/messages`, {
        body: text,
        author_type: "staff",
      }).catch(() => {});
    } catch {
      // Standalone fallback
    }

    setConversations((prev) => {
      const next = { ...prev };
      const conv = next[pid];
      if (!conv) return prev;
      next[pid] = {
        ...conv,
        messages: [
          ...conv.messages,
          {
            id: `msg-${pid}-staff-${Date.now()}`,
            sender: "staff",
            authorName: "Staff",
            text,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            status: "sent",
          },
        ],
      };
      return next;
    });
  };

  // AI Correction Flag submission
  const handleSubmitCorrection = async (
    target: { messageId: string | number; text: string },
    reason: string,
    correctedWording?: string
  ) => {
    if (!activeConversation) return;
    const convId = activeConversation.id;
    const pid = activeConversation.personaId;

    try {
      await apiClient.post(`/api/admin/sms/bootcamp/conversations/${convId}/corrections`, {
        message_id: target.messageId,
        reason,
        corrected_wording: correctedWording,
      }).catch(() => {});
    } catch {
      // Standalone fallback
    }

    toast.success("Correction saved to learning queue");

    if (correctedWording && correctedWording.trim()) {
      setConversations((prev) => {
        const next = { ...prev };
        const conv = next[pid];
        if (!conv) return prev;
        next[pid] = {
          ...conv,
          messages: conv.messages.map((m) =>
            m.id === target.messageId ? { ...m, text: correctedWording.trim() } : m
          ),
        };
        return next;
      });
    }
  };

  // Draft Actions
  const handleApproveDraft = async (msgId: string | number) => {
    if (!activeConversation) return;
    const convId = activeConversation.id;
    const pid = activeConversation.personaId;

    try {
      await apiClient.post(`/api/admin/sms/bootcamp/conversations/${convId}/drafts/${msgId}/review`, {
        action: "approve"
      }).catch(() => {});
    } catch {
      // Standalone fallback
    }

    setConversations((prev) => {
      const next = { ...prev };
      const conv = next[pid];
      if (!conv) return prev;

      const persona = PERSONAS.find((p) => p.id === pid);
      const updatedMessages = conv.messages.map((m) =>
        m.id === msgId ? { ...m, status: "sent" as const } : m
      );

      // Advance simulation turn upon draft approval (Requirement 1.4)
      const nextTurn = conv.currentTurn + 1;
      let nextMessages = updatedMessages;
      let newTurn = conv.currentTurn;
      let newStatus: typeof conv.status = "running";

      if (nextTurn <= conv.maxTurns && persona) {
        const nextScript = persona.dialogueScript[nextTurn - 1];
        if (nextScript) {
          newTurn = nextTurn;
          nextMessages = [
            ...updatedMessages,
            {
              id: `msg-${pid}-cust-${nextTurn}`,
              sender: "customer",
              authorName: persona.name,
              text: nextScript.customer,
              timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              status: "received"
            }
          ];
        } else {
          newStatus = "completed";
        }
      } else {
        newStatus = "completed";
      }

      next[pid] = {
        ...conv,
        currentTurn: newTurn,
        status: newStatus,
        messages: nextMessages,
      };
      return next;
    });

    if (runStatus === "paused") {
      setRunStatus("running");
    }
    toast.success("Draft approved and sent. Turn advanced.");
  };

  const handleDiscardDraft = async (msgId: string | number) => {
    if (!activeConversation) return;
    const convId = activeConversation.id;
    const pid = activeConversation.personaId;

    try {
      await apiClient.post(`/api/admin/sms/bootcamp/conversations/${convId}/drafts/${msgId}/review`, {
        action: "discard"
      }).catch(() => {});
    } catch {
      // Standalone fallback
    }

    setConversations((prev) => {
      const next = { ...prev };
      const conv = next[pid];
      if (!conv) return prev;
      next[pid] = {
        ...conv,
        messages: conv.messages.filter((m) => m.id !== msgId),
      };
      return next;
    });
    toast.info("Draft discarded.");
  };

  const handleEditAndSendDraft = async (msgId: string | number, text: string) => {
    if (!activeConversation) return;
    const convId = activeConversation.id;
    const pid = activeConversation.personaId;

    try {
      await apiClient.post(`/api/admin/sms/bootcamp/conversations/${convId}/drafts/${msgId}/review`, {
        action: "approve",
        text
      }).catch(() => {});
    } catch {
      // Standalone fallback
    }

    setConversations((prev) => {
      const next = { ...prev };
      const conv = next[pid];
      if (!conv) return prev;

      const persona = PERSONAS.find((p) => p.id === pid);
      const updatedMessages = conv.messages.map((m) =>
        m.id === msgId ? { ...m, text, status: "sent" as const } : m
      );

      // Advance simulation turn upon edited draft approval
      const nextTurn = conv.currentTurn + 1;
      let nextMessages = updatedMessages;
      let newTurn = conv.currentTurn;
      let newStatus: typeof conv.status = "running";

      if (nextTurn <= conv.maxTurns && persona) {
        const nextScript = persona.dialogueScript[nextTurn - 1];
        if (nextScript) {
          newTurn = nextTurn;
          nextMessages = [
            ...updatedMessages,
            {
              id: `msg-${pid}-cust-${nextTurn}`,
              sender: "customer",
              authorName: persona.name,
              text: nextScript.customer,
              timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              status: "received"
            }
          ];
        } else {
          newStatus = "completed";
        }
      } else {
        newStatus = "completed";
      }

      next[pid] = {
        ...conv,
        currentTurn: newTurn,
        status: newStatus,
        messages: nextMessages,
      };
      return next;
    });

    if (runStatus === "paused") {
      setRunStatus("running");
    }
    toast.success("Edited draft sent. Turn advanced.");
  };

  const handleToggleAi = async () => {
    if (runStatus === "running") {
      handlePause();
    } else {
      handleResume();
    }
  };

  const handleTogglePin = async () => {
    if (!activeConversation) return;
    const pid = activeConversation.personaId;
    const newPinned = !activeConversation.isPinned;
    setConversations((prev) => {
      const next = { ...prev };
      if (!next[pid]) return prev;
      next[pid] = { ...next[pid], isPinned: newPinned };
      return next;
    });
    toast.success(newPinned ? "Thread pinned." : "Thread unpinned.");
  };

  const handleToggleBlock = async () => {
    if (!activeConversation) return;
    const pid = activeConversation.personaId;
    const newBlocked = !activeConversation.isBlocked;
    setConversations((prev) => {
      const next = { ...prev };
      if (!next[pid]) return prev;
      next[pid] = { ...next[pid], isBlocked: newBlocked };
      return next;
    });
    toast.success(newBlocked ? "Contact blocked in simulation." : "Contact unblocked.");
  };

  // Map active conversation messages to ThreadMessage[]
  const mappedMessages: ThreadMessage[] = useMemo(() => {
    if (!activeConversation) return [];
    return activeConversation.messages.map((m) => {
      const isCustomer = m.sender === "customer";
      const isAi = m.sender === "tori";
      return {
        id: m.id,
        kind: "message",
        direction: isCustomer ? "inbound" : "outbound",
        authorType: isCustomer ? "customer" : isAi ? "ai" : "staff",
        authorName: m.authorName,
        body: m.text,
        status: m.status || (isCustomer ? "received" : "sent"),
        occurredAt: m.timestamp,
      };
    });
  }, [activeConversation]);

  // Toggle Persona selection
  const togglePersona = (pid: string) => {
    if (selectedPersonaIds.includes(pid)) {
      if (selectedPersonaIds.length === 1) {
        toast.warning("Keep at least one persona selected.");
        return;
      }
      const updated = selectedPersonaIds.filter((id) => id !== pid);
      setSelectedPersonaIds(updated);
      if (activePersonaId === pid) {
        setActivePersonaId(updated[0]);
      }
    } else {
      const updated = [...selectedPersonaIds, pid];
      setSelectedPersonaIds(updated);
      initializeConversations(updated, turns);
    }
  };

  // Select all / clear personas
  const selectAllPersonas = () => {
    const allIds = PERSONAS.map((p) => p.id);
    setSelectedPersonaIds(allIds);
    initializeConversations(allIds, turns);
  };

  const clearPersonas = () => {
    const single = [PERSONAS[0].id];
    setSelectedPersonaIds(single);
    setActivePersonaId(single[0]);
    initializeConversations(single, turns);
  };

  // Style Laboratory Sliders Change
  const handleSliderChange = (dim: keyof BootcampStyleProfile, val: number) => {
    setStyleProfile((prev) => ({ ...prev, [dim]: val }));
  };

  // Apply to Tori
  const handleApplyProfile = async () => {
    try {
      await apiClient.post("/api/admin/sms/bootcamp/profile/apply", {
        data: { profile: styleProfile }
      }).catch(() => {});
      setPreviousProfile({ ...styleProfile });
      setCanUndo(true);
      toast.success("Style profile applied to Tori!");
    } catch {
      toast.error("Failed to apply style profile");
    }
  };

  // Undo profile
  const handleUndoProfile = async () => {
    if (!previousProfile) return;
    try {
      await apiClient.post("/api/admin/sms/bootcamp/profile/undo", {}).catch(() => {});
      setStyleProfile({ ...previousProfile });
      setCanUndo(false);
      toast.info("Reverted to previous style profile.");
    } catch {
      toast.error("Failed to undo style profile");
    }
  };

  // Status Pill component
  const renderStatusPill = () => {
    switch (runStatus) {
      case "running":
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Running</span>
          </div>
        );
      case "paused":
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <span className="h-2 w-2 rounded-full bg-amber-500" />
            <span>Paused</span>
          </div>
        );
      case "failed":
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <span className="h-2 w-2 rounded-full bg-rose-500" />
            <span>Failed</span>
          </div>
        );
      case "completed":
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20">
            <span className="h-2 w-2 rounded-full bg-slate-400" />
            <span>Completed</span>
          </div>
        );
      case "stopped":
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20">
            <span className="h-2 w-2 rounded-full bg-slate-400" />
            <span>Stopped</span>
          </div>
        );
      default:
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-500 border border-slate-200 dark:border-slate-700">
            <span className="h-2 w-2 rounded-full bg-slate-400" />
            <span>Idle</span>
          </div>
        );
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-background text-foreground">
      {/* 1. Header Toolbar */}
      <header className="flex flex-wrap items-center justify-between gap-3 p-3 sm:px-4 sm:py-3 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-indigo-600 text-white shadow-xs">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base sm:text-lg font-bold tracking-tight">Tori Boot Camp</h1>
              {renderStatusPill()}
            </div>
            <p className="text-[11px] sm:text-xs text-muted-foreground">
              Simulated only · paced updates · no SMS or bookings
            </p>
          </div>
        </div>

        {/* Toolbar Action Buttons */}
        <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
          {/* Start / Pause / Resume / Stop Controls */}
          {runStatus === "idle" || runStatus === "stopped" || runStatus === "completed" ? (
            <Button
              type="button"
              size="sm"
              onClick={handleStart}
              className="h-8 text-xs gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold shadow-xs"
            >
              <Play className="h-3.5 w-3.5 fill-current" />
              <span>Start</span>
            </Button>
          ) : runStatus === "running" ? (
            <>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handlePause}
                className="h-8 text-xs gap-1.5 border-amber-300 text-amber-700 hover:bg-amber-50 dark:border-amber-700 dark:text-amber-300"
              >
                <Pause className="h-3.5 w-3.5" />
                <span>Pause</span>
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleStop}
                className="h-8 text-xs gap-1.5 border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300"
              >
                <Square className="h-3.5 w-3.5" />
                <span>Stop</span>
              </Button>
            </>
          ) : (
            /* Paused */
            <>
              <Button
                type="button"
                size="sm"
                onClick={handleResume}
                className="h-8 text-xs gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold shadow-xs"
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                <span>Resume</span>
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleStop}
                className="h-8 text-xs gap-1.5 border-slate-300 text-slate-700 hover:bg-slate-100"
              >
                <Square className="h-3.5 w-3.5" />
                <span>Stop</span>
              </Button>
            </>
          )}

          {/* Reset Button */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleReset}
            className="h-8 text-xs gap-1 text-slate-600 dark:text-slate-400 hover:text-rose-600"
            title="Clear all test run threads"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Reset</span>
          </Button>

          {/* Bootcamp Settings Shortcut Button */}
          <Sheet open={settingsSheetOpen} onOpenChange={setSettingsSheetOpen}>
            <SheetTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1.5 border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300 bg-indigo-50/50 dark:bg-indigo-950/30 hover:bg-indigo-100"
              >
                <Settings className="h-3.5 w-3.5" />
                <span>Settings</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-full sm:max-w-xl md:max-w-2xl overflow-y-auto p-4 sm:p-6">
              <SheetHeader className="mb-4">
                <SheetTitle className="text-base font-bold flex items-center gap-2">
                  <Bot className="h-4 w-4 text-indigo-600" />
                  Bootcamp Isolated Settings
                </SheetTitle>
              </SheetHeader>
              <BootcampSettingsTab onBackToBootcamp={() => setSettingsSheetOpen(false)} />
            </SheetContent>
          </Sheet>

          {onNavigate && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onNavigate("bootcamp-settings")}
              className="h-8 text-[11px] text-muted-foreground hover:text-primary hidden md:inline-flex"
            >
              Full Tab View
            </Button>
          )}
        </div>
      </header>

      {/* Real-Time Notice / Error Banner */}
      {notice && (
        <div
          className={`px-4 py-2 text-xs flex items-center justify-between shrink-0 ${
            notice.type === "error"
              ? "bg-rose-50 dark:bg-rose-950/40 border-b border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-200"
              : "bg-indigo-50 dark:bg-indigo-950/40 border-b border-indigo-200 dark:border-indigo-900 text-indigo-800 dark:text-indigo-200"
          }`}
        >
          <span>{notice.text}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            className="text-[10px] font-bold underline ml-2 cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 2. Responsive 3-Column Layout */}
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row overflow-hidden">
        {/* LEFT COLUMN: Personas & Turn Controls */}
        <aside className="w-full lg:w-72 xl:w-80 shrink-0 border-b lg:border-b-0 lg:border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col min-h-0">
          {/* Header Controls */}
          <div className="p-3 border-b border-slate-200 dark:border-slate-800 space-y-2.5 shrink-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700 dark:text-slate-300">
                <Users className="h-4 w-4 text-indigo-500" />
                <span>Threads {selectedPersonaIds.length}/{PERSONAS.length}</span>
              </div>
              <div className="flex items-center gap-1 text-[11px]">
                <button
                  type="button"
                  onClick={selectAllPersonas}
                  className="text-indigo-600 hover:text-indigo-700 font-medium px-1 cursor-pointer"
                >
                  Select all
                </button>
                <span className="text-slate-300 dark:text-slate-700">|</span>
                <button
                  type="button"
                  onClick={clearPersonas}
                  className="text-slate-500 hover:text-slate-700 font-medium px-1 cursor-pointer"
                >
                  Clear
                </button>
              </div>
            </div>

            {/* Mobile Responsive Selector (Visible on small screens) */}
            <div className="block lg:hidden">
              <label htmlFor="mobile-persona-select" className="text-[10px] font-bold uppercase text-slate-500 mb-1 block">
                Active Thread View
              </label>
              <select
                id="mobile-persona-select"
                value={activePersonaId}
                onChange={(e) => setActivePersonaId(e.target.value)}
                className="w-full h-8 px-2 text-xs rounded-md border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-foreground"
              >
                {selectedPersonaIds.map((pid) => {
                  const p = PERSONAS.find((item) => item.id === pid);
                  const conv = conversations[pid];
                  const handoffFlag = conv?.needsHandoff ? " ⚠️ (Needs Handoff)" : "";
                  return (
                    <option key={pid} value={pid}>
                      {p?.name} [{p?.category}]{handoffFlag}
                    </option>
                  );
                })}
              </select>
            </div>

            {/* Turns Slider */}
            <div className="space-y-1 pt-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                  Turns per Thread
                </span>
                <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400">
                  {turns} turns
                </span>
              </div>
              <input
                type="range"
                min="2"
                max="12"
                step="1"
                value={turns}
                disabled={runStatus === "running"}
                onChange={(e) => {
                  const val = Number(e.target.value);
                  setTurns(val);
                  initializeConversations(selectedPersonaIds, val);
                }}
                className="w-full h-1.5 bg-slate-100 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-600 disabled:opacity-50"
              />
              <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>2 min</span>
                <span>12 max</span>
              </div>
            </div>

            {/* Autonomy Level Selector (Spec 37) */}
            <div className="space-y-1.5 pt-1 border-t border-slate-100 dark:border-slate-800">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                  Autonomy Level
                </span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800">
                  {autonomyLevel === 1 ? "Level 1" : autonomyLevel === 2 ? "Level 2" : "Level 3"}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1 p-0.5 rounded-lg bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setAutonomyLevel(1)}
                  disabled={runStatus === "running"}
                  className={`h-7 text-xs px-2 rounded-md font-medium transition-all text-center flex items-center justify-center cursor-pointer disabled:opacity-50 ${
                    autonomyLevel === 1
                      ? "bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 font-bold shadow-xs border border-slate-200 dark:border-slate-700"
                      : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                  }`}
                  title="Level 1: Review Every Turn — Pauses on drafts for human sign-off"
                >
                  Level 1
                </button>
                <button
                  type="button"
                  onClick={() => setAutonomyLevel(2)}
                  disabled={runStatus === "running"}
                  className={`h-7 text-xs px-2 rounded-md font-medium transition-all text-center flex items-center justify-center cursor-pointer disabled:opacity-50 ${
                    autonomyLevel === 2
                      ? "bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 font-bold shadow-xs border border-slate-200 dark:border-slate-700"
                      : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                  }`}
                  title="Level 2: Semi-Autonomous (Default) — Pauses on handoffs & knowledge gaps"
                >
                  Level 2
                </button>
                <button
                  type="button"
                  onClick={() => setAutonomyLevel(3)}
                  disabled={runStatus === "running"}
                  className={`h-7 text-xs px-2 rounded-md font-medium transition-all text-center flex items-center justify-center cursor-pointer disabled:opacity-50 ${
                    autonomyLevel === 3
                      ? "bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 font-bold shadow-xs border border-slate-200 dark:border-slate-700"
                      : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                  }`}
                  title="Level 3: Full Simulation — Executes all turns completely autonomously"
                >
                  Level 3
                </button>
              </div>
              <p className="text-[10px] text-muted-foreground leading-tight">
                {autonomyLevel === 1 && "Review Every Turn — Pauses on drafts for operator sign-off."}
                {autonomyLevel === 2 && "Semi-Autonomous — Pauses on handoffs and knowledge gaps."}
                {autonomyLevel === 3 && "Full Simulation — Executes all turns autonomously."}
              </p>
            </div>

            {/* Scenario Pack Selector (Specs 33, 34) */}
            <div className="space-y-1.5 pt-1 border-t border-slate-100 dark:border-slate-800">
              <div className="flex items-center justify-between text-xs">
                <label htmlFor="bootcamp-scenario-select" className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                  Test Scenario
                </label>
                {selectedScenarios.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setSelectedScenarios([])}
                    className="text-[10px] text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 font-medium cursor-pointer"
                  >
                    Reset
                  </button>
                )}
              </div>
              <select
                id="bootcamp-scenario-select"
                value={selectedScenarios[0] || ""}
                disabled={runStatus === "running"}
                onChange={(e) => {
                  const val = e.target.value;
                  setSelectedScenarios(val ? [val] : []);
                }}
                className="w-full h-8 px-2 text-xs rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-foreground cursor-pointer focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
              >
                <option value="">All Scenarios (Random / Balanced)</option>
                {scenarioPacks.map((pack) => (
                  <optgroup key={pack.id} label={pack.title}>
                    {(pack.scenarios || []).map((sc) => (
                      <option key={sc.id} value={sc.id}>
                        {sc.title}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              {selectedScenarios.length > 0 ? (
                (() => {
                  const activeSc = scenarioPacks
                    .flatMap((p) => p.scenarios || [])
                    .find((s) => s.id === selectedScenarios[0]);
                  return activeSc ? (
                    <div className="p-1.5 rounded bg-indigo-50/60 dark:bg-indigo-950/30 border border-indigo-200/60 dark:border-indigo-800/60 text-[10px] text-indigo-900 dark:text-indigo-200">
                      <span className="font-semibold block">{activeSc.title}</span>
                      <span className="text-muted-foreground">{activeSc.description}</span>
                    </div>
                  ) : null;
                })()
              ) : (
                <p className="text-[10px] text-muted-foreground leading-tight">
                  Default: Dynamically tests balanced scenarios across all packs.
                </p>
              )}
            </div>
          </div>

          {/* 12 Persona Cards List (Hidden on mobile dropdown unless desktop) */}
          <div className="hidden lg:flex flex-1 flex-col overflow-y-auto p-2 space-y-1.5 no-scrollbar">
            {PERSONAS.map((persona) => {
              const isSelected = selectedPersonaIds.includes(persona.id);
              const isActive = activePersonaId === persona.id;
              const conv = conversations[persona.id];
              const needsHandoff = conv?.needsHandoff === true;

              return (
                <div
                  key={persona.id}
                  onClick={() => {
                    setActivePersonaId(persona.id);
                    if (!isSelected) {
                      togglePersona(persona.id);
                    }
                  }}
                  className={`p-2.5 rounded-lg border transition-all cursor-pointer text-xs relative ${
                    isActive
                      ? "border-indigo-500 bg-indigo-50/70 dark:bg-indigo-950/40 shadow-xs"
                      : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-start justify-between gap-1.5 mb-1">
                    <div className="flex items-center gap-2 min-w-0">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => {
                          e.stopPropagation();
                          togglePersona(persona.id);
                        }}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 h-3.5 w-3.5 cursor-pointer"
                      />
                      <span className="font-bold truncate text-slate-900 dark:text-slate-100">
                        {persona.name}
                      </span>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      {needsHandoff && (
                        <span title="Action required: Missing information handoff">
                          <AlertTriangle className="h-3.5 w-3.5 text-amber-500 animate-pulse" />
                        </span>
                      )}
                      <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded border ${persona.badgeClass}`}>
                        {persona.category}
                      </span>
                    </div>
                  </div>

                  <p className="text-[11px] text-muted-foreground line-clamp-1 ml-5.5">
                    {persona.description}
                  </p>

                  {conv && (
                    <div className="mt-1 ml-5.5 flex items-center justify-between text-[10px] text-slate-400">
                      <span>Turn {conv.currentTurn}/{conv.maxTurns}</span>
                      <span className="capitalize">{conv.status.replace("_", " ")}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </aside>

        {/* MIDDLE COLUMN: Interactive Conversation Stream */}
        <main className="flex-1 min-w-0 flex flex-col h-full bg-[#f8fafc] dark:bg-slate-950 min-h-0 overflow-hidden">
          {activeConversation ? (
            <AssistantThreadPanel
              mode="bootcamp"
              conversationId={activeConversation.id}
              title={activeConversation.personaName}
              subtitle={`Bootcamp · Turn ${activeConversation.currentTurn} of ${activeConversation.maxTurns}`}
              statusBadge={
                activeConversation.needsHandoff
                  ? "Information Required"
                  : activeConversation.status.replace("_", " ")
              }
              isPinned={activeConversation.isPinned}
              isBlocked={activeConversation.isBlocked}
              aiActive={runStatus === "running"}
              isGenerating={activeConversation.status === "running" && runStatus === "running"}
              messages={mappedMessages}
              infoRequest={{
                hasRequest: activeConversation.needsHandoff,
                prompt:
                  activeConversation.handoffReason ||
                  "Tori needs operational clarification to continue this dialogue.",
              }}
              onSubmitInfoAnswer={handleResolveLesson}
              onDismissInfoRequest={handleDismissHandoff}
              onSendMessage={handleSendMessage}
              onToggleAi={handleToggleAi}
              onTogglePin={handleTogglePin}
              onToggleBlock={handleToggleBlock}
              onApproveDraft={handleApproveDraft}
              onDiscardDraft={handleDiscardDraft}
              onEditAndSendDraft={handleEditAndSendDraft}
              onSubmitCorrection={handleSubmitCorrection}
              customerName={activeConversation.personaName}
            />
          ) : (
            <div className="m-auto text-center text-xs text-muted-foreground py-12">
              Select a persona to view interaction.
            </div>
          )}
        </main>

        {/* RIGHT COLUMN: Style Laboratory */}
        <aside className="w-full lg:w-72 xl:w-80 shrink-0 border-t lg:border-t-0 lg:border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col min-h-0">
          <div className="p-3 border-b border-slate-200 dark:border-slate-800 shrink-0">
            <div className="flex items-center justify-between mb-1">
              <h2 className="text-sm font-bold flex items-center gap-1.5 text-slate-900 dark:text-slate-100">
                <Sliders className="h-4 w-4 text-indigo-600" />
                Tori style laboratory
              </h2>
            </div>
            <p className="text-[11px] text-muted-foreground leading-snug">
              These values affect Boot Camp only until you deliberately apply the complete combination.
            </p>
          </div>

          {/* 8 Sliders (0 - 5) */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3.5 no-scrollbar text-xs">
            {(
              [
                { key: "flirtiness", label: "Flirtiness", desc: "Playfulness & charismatic warmth" },
                { key: "cheerfulness", label: "Cheerfulness", desc: "Sunny optimism & enthusiastic tone" },
                { key: "wit", label: "Wit", desc: "Clever phrasing & quick repartee" },
                { key: "sarcasm", label: "Sarcasm", desc: "Dry humor & ironic wit" },
                { key: "warmth", label: "Warmth", desc: "Empathy & emotional reassurance" },
                { key: "directness", label: "Directness", desc: "Concise brevity & fast booking" },
                { key: "chattiness", label: "Chattiness", desc: "Descriptive background context" },
                { key: "patience", label: "Patience", desc: "Gentle understanding for hesitations" }
              ] as const
            ).map(({ key, label, desc }) => {
              const val = styleProfile[key];
              return (
                <div key={key} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-semibold text-slate-800 dark:text-slate-200">{label}</span>
                      <span className="text-[10px] text-muted-foreground block">{desc}</span>
                    </div>
                    <span className="font-mono font-bold text-xs px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800">
                      {val} / 5
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="5"
                    step="1"
                    value={val}
                    onChange={(e) => handleSliderChange(key, Number(e.target.value))}
                    className="w-full h-1.5 bg-slate-100 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                  />
                  <div className="flex justify-between text-[9px] text-muted-foreground">
                    <span>0 (None)</span>
                    <span>5 (Maximum)</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Action Buttons: Apply & Undo */}
          <div className="p-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 shrink-0 flex items-center justify-between gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!canUndo}
              onClick={handleUndoProfile}
              className="h-8 text-xs gap-1"
            >
              <Undo2 className="h-3.5 w-3.5" />
              Undo
            </Button>

            <Button
              type="button"
              size="sm"
              onClick={handleApplyProfile}
              className="h-8 text-xs gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold shadow-xs"
            >
              <Save className="h-3.5 w-3.5" />
              Apply to Tori
            </Button>
          </div>
        </aside>
      </div>
    </div>
  );
}
